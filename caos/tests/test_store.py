"""Domain-store contracts: atomic audited writes, promotion, staleness, pinning."""

from __future__ import annotations

import pytest


@pytest.fixture()
def case_id(store):
    return store.create_case("Case", "Issuer", "Services", "analyst")["id"]


def seed_source(store, case_id, body: bytes, name="doc.txt"):
    import hashlib

    return store.ingest({
        "case_id": case_id,
        "filename": name,
        "media_type": "text/plain",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body.decode(), "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, "analyst")


def test_governed_writes_commit_state_and_audit_together(store, case_id):
    seed_source(store, case_id, b"evidence one")
    actions = [event["action"] for event in store.audit_trail()]
    assert "source.ingested" in actions and "case.created" in actions
    before = store.audit_trail()
    with pytest.raises(ValueError, match="already active"):
        seed_source(store, case_id, b"evidence one", name="copy.txt")
    assert store.audit_trail() == before


def test_source_set_id_pins_immutable_membership(store, case_id):
    first = seed_source(store, case_id, b"one")
    pinned_id = first["source_set"]["id"]
    pinned_members = list(first["source_set"]["source_ids"])
    seed_source(store, case_id, b"two")
    seed_source(store, case_id, b"three")
    historical = store.source_set(pinned_id)
    assert historical["version"] == 1
    assert historical["source_ids"] == pinned_members
    assert store.current_source_set(case_id)["version"] == 3


def test_note_promotion_is_idempotent_and_content_addressed(store, case_id):
    note = store.create_note(case_id, "analyst observation", "analyst")
    promoted = store.promote_note(case_id, note["id"], "analyst")
    source_id = promoted["promoted_source_id"]
    assert source_id
    assert store.current_source_set(case_id)["version"] == 1
    replay = store.promote_note(case_id, note["id"], "analyst")
    assert replay["promoted_source_id"] == source_id
    assert store.current_source_set(case_id)["version"] == 1, "replay must not version the set"
    second = store.create_note(case_id, "analyst observation", "analyst")
    with pytest.raises(ValueError, match="already active"):
        store.promote_note(case_id, second["id"], "analyst")
    assert store.current_source_set(case_id)["version"] == 1


def test_promotion_after_withdrawal_mints_new_identity_without_resurrection(store, case_id):
    note = store.create_note(case_id, "recurring observation", "analyst")
    first = store.promote_note(case_id, note["id"], "analyst")
    old_source = first["promoted_source_id"]
    store.withdraw(case_id, old_source, "analyst")
    assert store.current_source_set(case_id)["version"] == 2
    again = store.promote_note(case_id, note["id"], "analyst")
    new_source = again["promoted_source_id"]
    assert new_source != old_source, "withdrawn source id must never be resurrected"
    current = store.current_source_set(case_id)
    assert current["version"] == 3
    assert current["source_ids"] == [new_source]


def test_promotion_rolls_back_atomically_on_downstream_failure(store, case_id, monkeypatch):
    note = store.create_note(case_id, "atomic observation", "analyst")
    audit_before = store.audit_trail()

    def failing_audit(conn, action, actor, **details):
        raise RuntimeError("injected failure after source insert")

    monkeypatch.setattr(store, "_audit", failing_audit)
    with pytest.raises(RuntimeError):
        store.promote_note(case_id, note["id"], "analyst")
    monkeypatch.undo()
    assert store.list_sources(case_id) == []
    assert store.current_source_set(case_id) is None
    assert store.audit_trail() == audit_before
    fresh = store.list_notes(case_id)[0]
    assert fresh["promoted"] is False and fresh["promoted_source_id"] is None
    retry = store.promote_note(case_id, note["id"], "analyst")
    assert retry["promoted_source_id"]


def test_note_promotion_serializes_with_snapshot_and_publication_authority(store, case_id):
    import threading

    note = store.create_note(case_id, "concurrent observation", "analyst")
    started = threading.Event()
    finished = threading.Event()
    errors = []

    def promote():
        started.set()
        try:
            store.promote_note(case_id, note["id"], "analyst")
        except Exception as exc:  # noqa: BLE001 — surfaced in the test thread
            errors.append(exc)
        finally:
            finished.set()

    worker = threading.Thread(target=promote)
    with store.authority_guard():
        worker.start()
        assert started.wait(2)
        assert not finished.wait(0.05), "promotion bypassed the held authority guard"
        assert store.current_source_set(case_id) is None
    assert finished.wait(2)
    worker.join()
    assert errors == []
    assert store.current_source_set(case_id)["version"] == 1


def test_withdrawal_stales_citing_assumptions_and_bans_new_citations(store, case_id):
    source = seed_source(store, case_id, b"assumption evidence")
    assumption = store.save_assumption(case_id, {"name": "margin"}, [source["id"]], "analyst")
    assert assumption["status"] == "READY"
    store.withdraw(case_id, source["id"], "analyst")
    stale = store.list_assumptions(case_id)[0]
    assert stale["stale"] is True and stale["status"] == "STALE"
    with pytest.raises(ValueError, match="EVIDENCE_SOURCE_WITHDRAWN"):
        store.save_assumption(case_id, {"name": "coverage"}, [source["id"]], "analyst")


def test_membership_and_roles_gate_access(store):
    case = store.create_case("Case", "Issuer", "Services", "creator")
    case_id = case["id"]
    assert store.is_member(case_id, "creator")
    assert store.is_member(case_id, "creator", roles={"ANALYST", "APPROVER", "ADMIN"})
    assert not store.is_member(case_id, "outsider")
    assert not store.add_member(case_id, "outsider", "friend", "ANALYST")
    assert store.add_member(case_id, "platform-admin", "reviewer", "READER", actor_role="ADMIN")
    assert store.is_member(case_id, "reviewer", roles={"READER"})
    assert not store.is_member(case_id, "reviewer", roles={"ANALYST", "APPROVER", "ADMIN"})
    assert [c["id"] for c in store.list_cases("reviewer")] == [case_id]


def test_store_close_is_idempotent_and_disposes_only_its_owned_engine(tmp_path):
    import sqlalchemy as sa

    from caos.storage.store import DomainStore

    owned = DomainStore.from_url(f"sqlite:///{tmp_path / 'owned.db'}")
    original_owned_pool = owned.engine.pool
    owned.close()
    disposed_owned_pool = owned.engine.pool
    owned.close()
    assert disposed_owned_pool is not original_owned_pool
    assert owned.engine.pool is disposed_owned_pool, "double-close must be a no-op"

    borrowed_engine = sa.create_engine(f"sqlite:///{tmp_path / 'borrowed.db'}")
    borrowed_pool = borrowed_engine.pool
    try:
        DomainStore(borrowed_engine).close()
        assert borrowed_engine.pool is borrowed_pool, "the store must not dispose a caller-owned engine"
    finally:
        borrowed_engine.dispose()

    class FailingEngine:
        def __init__(self):
            self.attempts = 0

        def dispose(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("dispose failed")

    retryable_engine = FailingEngine()
    retryable = DomainStore(retryable_engine, owns_engine=True)
    with pytest.raises(RuntimeError, match="dispose failed"):
        retryable.close()
    retryable.close()
    assert retryable_engine.attempts == 2, "a failed owned dispose must remain retryable"


def test_source_set_version_allocation_locks_the_case_row(tmp_path):
    """Version allocation is read-max-then-insert against UNIQUE(case_id, version).
    Under READ COMMITTED two concurrent ingests both read N and both insert N+1,
    and the loser's IntegrityError surfaced as "source content already active" —
    a wrong refusal for content that is not a duplicate. The case row is locked
    first; locking the set row would not help, because `ORDER BY … LIMIT 1
    FOR UPDATE` re-reads the same unchanged row and still computes N+1."""
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    from caos.storage.store import DomainStore, cases

    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'lock.db'}")
    try:
        case = store.create_case("Lock", "Issuer", "Sector", "analyst")

        statements: list[str] = []
        sa.event.listen(store.engine, "before_cursor_execute",
                        lambda conn, cursor, statement, *rest: statements.append(" ".join(statement.split())))
        store.ingest({"case_id": case["id"], "filename": "a.txt", "media_type": "text/plain",
                      "bytes": 1, "sha256": "a" * 64, "vault_path": None, "blocks": []}, "analyst")
        lock_at = next(i for i, s in enumerate(statements) if "SELECT cases.id FROM cases WHERE cases.id" in s)
        insert_at = next(i for i, s in enumerate(statements) if "INSERT INTO source_sets" in s)
        assert lock_at < insert_at, "the case row is claimed before a version is allocated"

        # The clause itself, on the dialect that needs it (SQLite emits nothing).
        locked = sa.select(cases.c.id).where(cases.c.id == case["id"]).with_for_update()
        assert "FOR UPDATE" in str(locked.compile(dialect=postgresql.dialect()))
    finally:
        store.close()
