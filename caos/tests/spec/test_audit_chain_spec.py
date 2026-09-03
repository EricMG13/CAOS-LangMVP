"""Audit append-only integrity chain (Task 10; ENTERPRISE_READINESS_PLAN Phase 4
items 14–15; ETR AUD-011, AUD-012).

The audit log is append-only at the database boundary and every row is linked
to its predecessor by digest inside a per-case chain, so mutation, deletion,
insertion and reordering are all detectable — by the store and by the offline
verifier working from a case-scoped package alone. The wire shape of
`audit_trail()` is unchanged: chain fields never reach the pinned key sets.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from spec_helpers import seed_case_with_source


def _chain_module():
    from caos.audit import chain

    return chain


def test_governed_writes_extend_a_contiguous_per_case_hash_chain(store):
    chain = _chain_module()
    case, _source = seed_case_with_source(store)
    store.create_note(case["id"], "chained observation", "analyst")

    rows = store.audit_chain(case["id"])
    assert [row["action"] for row in rows] == ["case.created", "source.ingested", "note.created"]
    assert [row["chain_seq"] for row in rows] == [1, 2, 3], "chain sequence is contiguous from one"
    assert rows[0]["prev_digest"] == chain.GENESIS
    for previous, row in zip(rows, rows[1:], strict=False):
        assert row["prev_digest"] == previous["digest"], "each row links to its predecessor"
    for row in rows:
        preimage = {field: row[field] for field in chain.CHAIN_FIELDS}
        expected = hashlib.sha256(
            json.dumps(preimage, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        assert row["digest"] == expected == chain.event_digest(row), "row digest is the stdlib canonical form"
    head = store.audit_chain_head(case["id"])
    assert head == {"chain_key": case["id"], "chain_seq": 3, "digest": rows[-1]["digest"]}
    assert store.verify_audit_chain() == {}, "every chain in the store verifies"

    for event in store.audit_trail():
        assert not {"digest", "prev_digest", "chain_seq", "chain_key", "seq"} & set(event), \
            "chain fields never reach the audit wire shape"


def test_events_without_a_case_ride_the_global_chain(store):
    chain = _chain_module()
    store.refuse_intake("analyst", "INTAKE_ADMISSION_REFUSED", case_id=None)
    rows = store.audit_chain(chain.GLOBAL_CHAIN)
    assert [row["action"] for row in rows] == ["intake.refused"]
    assert rows[0]["chain_seq"] == 1 and rows[0]["prev_digest"] == chain.GENESIS
    assert store.verify_audit_chain() == {}


def test_audit_rows_refuse_update_and_delete_at_the_database_boundary(store):
    from caos.storage.store import audit_events

    case, _source = seed_case_with_source(store)
    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.update(audit_events).where(audit_events.c.action == "case.created").values(actor="forger"))
    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.delete(audit_events).where(audit_events.c.action == "case.created"))
    assert [row["actor"] for row in store.audit_chain(case["id"])] == ["analyst", "analyst"]
    assert store.verify_audit_chain() == {}


@pytest.mark.parametrize("tamper", ["mutate", "delete", "insert", "reorder", "head"])
def test_tampering_under_disarmed_triggers_is_detected(store, tamper):
    """A privileged actor can drop the triggers; the chain still convicts."""
    from caos.storage.store import audit_chain_heads, audit_events

    chain = _chain_module()
    case, _source = seed_case_with_source(store)
    store.create_note(case["id"], "first", "analyst")
    store.create_note(case["id"], "second", "analyst")
    rows = store.audit_chain(case["id"])
    assert len(rows) == 4 and store.verify_audit_chain(case["id"]) == {}
    store.disarm_audit_triggers_for_tests()

    with store.engine.begin() as conn:
        if tamper == "mutate":
            conn.execute(sa.update(audit_events).where(
                audit_events.c.chain_key == case["id"], audit_events.c.chain_seq == 2,
            ).values(actor="forger"))
            expected = {"AUDIT_EVENT_DIGEST_MISMATCH"}
        elif tamper == "delete":
            conn.execute(sa.delete(audit_events).where(
                audit_events.c.chain_key == case["id"], audit_events.c.chain_seq == 3,
            ))
            expected = {"AUDIT_CHAIN_SEQUENCE_BROKEN", "AUDIT_CHAIN_LINK_BROKEN"}
        elif tamper == "insert":
            forged = {
                "id": "aud-forged", "action": "source.withdrawn", "actor": "forger", "at": rows[-1]["at"],
                "data": {"case_id": case["id"], "source_id": "src-forged"},
                "chain_key": case["id"], "chain_seq": 5, "prev_digest": rows[-1]["digest"],
            }
            forged["digest"] = chain.event_digest(forged)
            conn.execute(audit_events.insert().values(**forged))
            expected = {"AUDIT_CHAIN_HEAD_MISMATCH"}
        elif tamper == "reorder":
            conn.execute(sa.update(audit_events).where(
                audit_events.c.chain_key == case["id"], audit_events.c.chain_seq == 3,
            ).values(chain_seq=99))
            conn.execute(sa.update(audit_events).where(
                audit_events.c.chain_key == case["id"], audit_events.c.chain_seq == 4,
            ).values(chain_seq=3))
            conn.execute(sa.update(audit_events).where(
                audit_events.c.chain_key == case["id"], audit_events.c.chain_seq == 99,
            ).values(chain_seq=4))
            expected = {"AUDIT_CHAIN_LINK_BROKEN", "AUDIT_EVENT_DIGEST_MISMATCH"}
        else:
            conn.execute(sa.update(audit_chain_heads).where(
                audit_chain_heads.c.chain_key == case["id"],
            ).values(digest="f" * 64))
            expected = {"AUDIT_CHAIN_HEAD_MISMATCH"}

    findings = store.verify_audit_chain(case["id"])
    assert set(findings) == {case["id"]}
    assert {finding["code"] for finding in findings[case["id"]]} >= expected


def test_legacy_unchained_rows_are_backfilled_once_and_idempotently(tmp_path):
    from caos.storage.store import DomainStore

    chain = _chain_module()
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(path)
    raw.executescript(
        "CREATE TABLE audit_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id VARCHAR NOT NULL, "
        "action VARCHAR NOT NULL, actor VARCHAR NOT NULL, at VARCHAR NOT NULL, data JSON NOT NULL);"
        "INSERT INTO audit_events (id, action, actor, at, data) VALUES "
        "('aud-1', 'case.created', 'analyst', '2026-01-01T00:00:00+00:00', '{\"case_id\": \"case-a\"}'),"
        "('aud-2', 'intake.refused', 'analyst', '2026-01-01T00:00:01+00:00', '{\"case_id\": null, \"code\": \"X\"}'),"
        "('aud-3', 'note.created', 'analyst', '2026-01-01T00:00:02+00:00', '{\"case_id\": \"case-a\", \"note_id\": \"n\"}');"
    )
    raw.commit()
    raw.close()

    first = DomainStore.from_url(f"sqlite:///{path}")
    try:
        case_rows = first.audit_chain("case-a")
        assert [row["id"] for row in case_rows] == ["aud-1", "aud-3"]
        assert [row["chain_seq"] for row in case_rows] == [1, 2]
        assert [row["id"] for row in first.audit_chain(chain.GLOBAL_CHAIN)] == ["aud-2"]
        assert first.verify_audit_chain() == {}
        digests = [row["digest"] for row in case_rows]
        first.audit_event("case.member_added", "admin", case_id="case-a", member="approver", role="APPROVER")
    finally:
        first.close()

    second = DomainStore.from_url(f"sqlite:///{path}")
    try:
        rows = second.audit_chain("case-a")
        assert [row["digest"] for row in rows[:2]] == digests, "reopening never re-chains existing rows"
        assert [row["chain_seq"] for row in rows] == [1, 2, 3]
        assert second.verify_audit_chain() == {}
        with pytest.raises(DBAPIError, match="APPEND_ONLY"), second.engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM audit_events WHERE id = 'aud-1'")
    finally:
        second.close()


def test_concurrent_governed_writes_never_fork_the_chain(store):
    case, _source = seed_case_with_source(store)
    errors: list[BaseException] = []

    def write(index: int) -> None:
        try:
            store.create_note(case["id"], f"note {index}", "analyst")
        except BaseException as exc:  # noqa: BLE001 — surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(index,)) for index in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    rows = store.audit_chain(case["id"])
    assert len(rows) == 14 and [row["chain_seq"] for row in rows] == list(range(1, 15))
    assert store.verify_audit_chain() == {}


def test_a_failed_governed_write_leaves_no_chain_gap(store, monkeypatch):
    case, _source = seed_case_with_source(store)
    before = store.audit_chain(case["id"])
    original = store._audit

    def audit_then_fail(conn, action, actor, **details):
        original(conn, action, actor, **details)
        raise RuntimeError("injected failure after the audit insert")

    monkeypatch.setattr(store, "_audit", audit_then_fail)
    with pytest.raises(RuntimeError):
        store.create_note(case["id"], "rolled back", "analyst")
    monkeypatch.undo()
    assert store.audit_chain(case["id"]) == before
    store.create_note(case["id"], "after rollback", "analyst")
    assert [row["chain_seq"] for row in store.audit_chain(case["id"])] == [1, 2, 3]
    assert store.verify_audit_chain() == {}
