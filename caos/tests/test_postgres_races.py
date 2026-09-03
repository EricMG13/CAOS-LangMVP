"""Two-connection PostgreSQL races (ENTERPRISE_READINESS_PLAN Phase 5 items 1–3;
ETR-B07; SIM-012 to SIM-017; SPEC_RECONCILIATION deferral D3).

Every test opens TWO SQLAlchemy engines over one freshly created database —
two backend PIDs, asserted — and drives the same governed write from both.
The interleaving is forced, not hoped for: a `before_cursor_execute` listener
on each engine parks that connection mid-transaction at a named statement, so
both writers have passed their pre-checks before either commits. Exactly one
commits; the other receives the typed loser the contract names — never a raw
IntegrityError, never a lost update, never two heads — and the audit chain
verifies afterwards.

The SQLite thread races elsewhere in the suite and the compiled `FOR UPDATE`
check in test_store.py stay as fast mechanism tests; this module is the
PostgreSQL behavioural proof and the only place that may be called one.

Requires CAOS_TEST_POSTGRES_URL naming a role that may CREATE DATABASE (the CI
service's `caos` superuser, or the local QA container's `postgres`). CI sets
CAOS_REQUIRE_POSTGRES=1 so an unset URL fails instead of skipping.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import pytest
import sqlalchemy as sa

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.contracts import digest  # noqa: E402
from caos.storage.deliverables import (  # noqa: E402
    DeliverableStore,
    DeliverableVersionConflict,
    OpinionHeadConflict,
)
from caos.storage.models import ModelRevisionConflict, ModelStore  # noqa: E402
from caos.storage.runs import RunStore, StoreConflict, run_nodes, runs  # noqa: E402
from caos.storage.store import DomainStore, new_id, now_iso  # noqa: E402

pytestmark = pytest.mark.postgres

PARK_TIMEOUT = 20.0


# --- fixtures -----------------------------------------------------------------


@pytest.fixture(scope="session")
def postgres_admin_url() -> str:
    url = os.getenv("CAOS_TEST_POSTGRES_URL")
    if not url:
        if os.getenv("CAOS_REQUIRE_POSTGRES"):
            pytest.fail("CAOS_REQUIRE_POSTGRES is set but CAOS_TEST_POSTGRES_URL is not: the "
                        "two-connection races must run, not skip")
        pytest.skip("set CAOS_TEST_POSTGRES_URL to run the two-connection PostgreSQL races")
    return url


@pytest.fixture()
def pg_url(postgres_admin_url: str):
    """One database per test, created and dropped here, so every race starts
    from the fresh schema the store creates and leaves nothing behind."""
    name = f"caos_race_{uuid4().hex[:12]}"
    admin = sa.create_engine(postgres_admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
        yield sa.engine.make_url(postgres_admin_url).set(database=name).render_as_string(hide_password=False)
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


@pytest.fixture()
def stores(pg_url: str):
    """Two DomainStores, two engines, two pools: nothing is shared above the
    database itself."""
    a = DomainStore.from_url(pg_url)
    b = DomainStore.from_url(pg_url)
    try:
        yield a, b
    finally:
        a.close()
        b.close()


def _backend_pid(store: DomainStore) -> int:
    with store.engine.connect() as conn:
        return conn.execute(sa.text("SELECT pg_backend_pid()")).scalar_one()


# --- interleaving control -----------------------------------------------------


class Park:
    """Parks one engine the first time a statement matching `pattern` is about
    to execute — inside its open transaction, holding whatever locks it has —
    until `release()`. The other engine keeps running."""

    def __init__(self, engine: sa.Engine, pattern: str) -> None:
        self.engine = engine
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.arrived = threading.Event()
        self._release = threading.Event()
        self._armed = True
        sa.event.listen(engine, "before_cursor_execute", self._hook)

    def _hook(self, conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool) -> None:
        if self._armed and self.pattern.search(" ".join(statement.split())):
            self._armed = False
            self.arrived.set()
            if not self._release.wait(PARK_TIMEOUT):
                raise TimeoutError("race choreography stalled: park never released")

    def release(self) -> None:
        self._release.set()

    def remove(self) -> None:
        self.release()
        sa.event.remove(self.engine, "before_cursor_execute", self._hook)


Outcome = tuple[str, Any]


def race(a_call: Callable[[], Any], a_park: Park, b_call: Callable[[], Any], b_park: Park, *,
         release_first: str = "a") -> tuple[Outcome, Outcome]:
    """Run `a_call` until it parks, start `b_call`, then release the parks in
    the requested order. A writer blocked behind the other's row lock never
    reaches its park; releasing it early is harmless, it passes through when
    it gets there. Returns ("ok", value) or ("error", exc) per side."""
    results: dict[str, Outcome] = {}

    def runner(name: str, call: Callable[[], Any]) -> None:
        try:
            results[name] = ("ok", call())
        except Exception as exc:  # noqa: BLE001 — the loser's typed refusal is the assertion
            results[name] = ("error", exc)

    threads = {
        "a": threading.Thread(target=runner, args=("a", a_call), name="race-a"),
        "b": threading.Thread(target=runner, args=("b", b_call), name="race-b"),
    }
    parks = {"a": a_park, "b": b_park}
    try:
        threads["a"].start()
        assert a_park.arrived.wait(PARK_TIMEOUT), "writer A never reached its park"
        threads["b"].start()
        b_park.arrived.wait(2.0)
        second = "b" if release_first == "a" else "a"
        parks[release_first].release()
        threads[release_first].join(5.0)
        parks[second].release()
        for thread in threads.values():
            thread.join(PARK_TIMEOUT)
            assert not thread.is_alive(), f"writer {thread.name} did not finish"
    finally:
        a_park.remove()
        b_park.remove()
    return results["a"], results["b"]


def _one_winner(outcomes: tuple[Outcome, Outcome]) -> tuple[Any, Exception]:
    winners = [value for kind, value in outcomes if kind == "ok"]
    losers = [value for kind, value in outcomes if kind == "error"]
    assert len(winners) == 1 and len(losers) == 1, f"exactly one writer commits: {outcomes!r}"
    return winners[0], losers[0]


def _chain_intact(store: DomainStore) -> None:
    assert store.verify_audit_chain() == {}, "the audit chain must verify after every race"


def _audit_actions(store: DomainStore, action: str) -> list[dict[str, Any]]:
    return [row for row in store.audit_trail(limit=1000) if row["action"] == action]


# --- seeds --------------------------------------------------------------------


def _source(case_id: str, body: str, *, filename: str = "doc.txt") -> dict[str, Any]:
    import hashlib

    return {
        "case_id": case_id, "filename": filename, "media_type": "text/plain", "bytes": len(body),
        "sha256": hashlib.sha256(body.encode()).hexdigest(), "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body, "extractor_version": "builtin-v1",
                    "confidence": "MEDIUM", "untrusted_data": True}],
    }


def _seed_case(store: DomainStore) -> dict[str, Any]:
    return store.create_case("Race", "Issuer", "Services", "analyst")


def _seed_run(store: DomainStore, case_id: str, modules: tuple[str, ...] = ("CP-0", "CP-1")) -> tuple[RunStore, dict[str, Any]]:
    run_store = RunStore(store.engine)
    run = run_store.create_run(case_id, "FULL_CREDIT", "screen", "analyst")
    with store.engine.begin() as conn:
        for stage, module_id in enumerate(modules):
            conn.execute(run_nodes.insert().values(
                id=new_id("node"), run_id=run["id"], case_id=case_id, module_id=module_id,
                stage=stage, dependencies=[], status="pending", attempt=0,
            ))
    return run_store, run


def _succeeded_run(store: DomainStore, case_id: str) -> str:
    run_store, run = _seed_run(store, case_id)
    with store.engine.begin() as conn:
        conn.execute(sa.update(runs).where(runs.c.id == run["id"]).values(status="succeeded"))
    return run["id"]


def _snapshot(case_id: str, run_id: str, *, previous: str | None = None) -> dict[str, Any]:
    record = {
        "id": new_id("snap"), "case_id": case_id, "run_id": run_id, "source_set_id": "set-race",
        "source_set_version": 1, "artifacts": [], "previous_snapshot_id": previous,
        "accepted_at": now_iso(), "provider_identity": None,
    }
    record["digest"] = digest({key: value for key, value in record.items() if key not in {"digest", "id"}})
    return record


def _revision_record(case_id: str, build_id: str, note: str) -> dict[str, Any]:
    assumptions = [{"assumption_id": "growth", "value": 0.02, "note": note}]
    outputs = {"leverage": 3.1}
    return {
        "case_id": case_id, "build_id": build_id, "effective_assumptions": assumptions,
        "assumptions_digest": digest(assumptions), "outputs": outputs, "outputs_digest": digest(outputs),
    }


def _opinion_record(case_id: str, revision_id: str, text: str) -> dict[str, Any]:
    return {
        "case_id": case_id, "pathway": "FULL_CREDIT", "draft_id": "dldraft-race", "revision_id": revision_id,
        "draft_version": 1, "draft_digest": "d" * 64, "binding": {"revision_id": revision_id},
        "opinion": text, "limitations": "none", "material_overrides": "none", "rationale": "cited",
    }


def _frozen_record(case_id: str, deliverable_id: str, *, created_by: str = "analyst") -> dict[str, Any]:
    return {
        "deliverable_id": deliverable_id, "thread_id": f"thread-{deliverable_id}", "case_id": case_id,
        "pathway": "FULL_CREDIT", "status": "FROZEN", "preview_digest": "p" * 64,
        "input_fingerprint": "f" * 64, "build_id": "build-race", "payload": {"preview_digest": "p" * 64},
        "exports": {"md": {"sha256": "e" * 64}}, "authority": {"snapshot_id": "snap-race"},
        "draft_version": 1, "draft_digest": "d" * 64, "created_by": created_by,
        "opinion_id": "opn-race", "signed_by": "signer",
    }


def _loan_record(case_id: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id, "source_id": source["id"], "source_filename": source["filename"],
        "source_sha256": source["sha256"], "workbook_date": None, "template_version": "v1",
        "importer_version": "v1", "universe_digest": "u" * 64, "row_count": 1, "status": "ACTIVE",
        "findings": [], "rows": [{"issuer": "X"}], "created_by": "analyst",
    }


# --- the two connections are two connections ------------------------------------


def test_two_stores_are_two_independent_backends(stores):
    a, b = stores
    assert a.engine is not b.engine
    assert _backend_pid(a) != _backend_pid(b), "each store owns its own pool and server backend"


# --- duplicate and concurrent ingestion (SIM-013), source-set allocation ----------


def test_duplicate_upload_race_admits_one_active_source_and_one_set_version(stores):
    """SIM-013: two identical uploads pass the duplicate pre-check together; the
    partial unique index elects one, the loser is the typed 409 refusal."""
    a, b = stores
    case = _seed_case(a)
    body = "identical bytes"
    park_a = Park(a.engine, r"^INSERT INTO sources")
    park_b = Park(b.engine, r"^INSERT INTO sources")
    winner, loser = _one_winner(race(
        lambda: a.ingest(_source(case["id"], body), "analyst-a"), park_a,
        lambda: b.ingest(_source(case["id"], body, filename="again.txt"), "analyst-b"), park_b,
    ))
    assert isinstance(loser, ValueError) and str(loser) == "source content already active"
    active = [row for row in a.list_sources(case["id"]) if not row.get("withdrawn")]
    assert [row["id"] for row in active] == [winner["id"]]
    assert a.current_source_set(case["id"])["version"] == 1, "one source-set transition"
    assert len(_audit_actions(a, "source.ingested")) == 1
    _chain_intact(a)


def test_concurrent_distinct_uploads_allocate_monotonic_source_set_versions(stores):
    """Source-set allocation: the case row is locked before the version is read,
    so two different uploads get versions 1 and 2 and the later set carries
    both sources (the FOR UPDATE test_store.py only pins as compiled SQL)."""
    a, b = stores
    case = _seed_case(a)
    park_a = Park(a.engine, r"^INSERT INTO source_sets")
    park_b = Park(b.engine, r"^INSERT INTO source_sets")
    outcomes = race(
        lambda: a.ingest(_source(case["id"], "first document"), "analyst-a"), park_a,
        lambda: b.ingest(_source(case["id"], "second document", filename="two.txt"), "analyst-b"), park_b,
    )
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    with a.engine.connect() as conn:
        sets = conn.execute(sa.text(
            "SELECT version, source_ids FROM source_sets WHERE case_id = :c ORDER BY version"
        ), {"c": case["id"]}).all()
    assert [version for version, _ in sets] == [1, 2]
    assert set(sets[0][1]) < set(sets[1][1]), "the later version carries every earlier live source"
    assert set(sets[1][1]) == {outcomes[0][1]["id"], outcomes[1][1]["id"]}
    _chain_intact(a)


def test_concurrent_identical_intake_packs_admit_one_pack(stores):
    """Document-first intake admits a whole pack or none; two identical packs
    racing into one case leave one intake, one source and one set version."""
    a, b = stores
    case = _seed_case(a)
    pack = [_source(case["id"], "pack document")]
    park_a = Park(a.engine, r"^INSERT INTO sources")
    park_b = Park(b.engine, r"^INSERT INTO sources")

    def admit(store: DomainStore, actor: str):
        return store.admit_intake(actor=actor, case_id=case["id"], new_case=None,
                                  prepared=[dict(item) for item in pack], intake_key=new_id("key"),
                                  status="ADMITTED", record={"pack": 1})

    winner, loser = _one_winner(race(lambda: admit(a, "a"), park_a, lambda: admit(b, "b"), park_b))
    assert isinstance(loser, ValueError) and str(loser) == "source content already active"
    assert len(a.intakes_for_case(case["id"])) == 1 and a.intakes_for_case(case["id"])[0]["id"] == winner["id"]
    assert len(a.list_sources(case["id"])) == 1
    assert a.current_source_set(case["id"])["version"] == 1
    assert len(_audit_actions(a, "intake.admitted")) == 1
    _chain_intact(a)


# --- upload and withdrawal interleave (SIM-014) ----------------------------------


@pytest.mark.parametrize("release_first", ["a", "b"])
def test_upload_and_withdrawal_interleave_yield_monotonic_history_under_both_orders(stores, release_first):
    """SIM-014: whichever commits first, versions are contiguous, each version is
    derived from its predecessor, and the final set holds exactly the live sources."""
    a, b = stores
    case = _seed_case(a)
    first = a.ingest(_source(case["id"], "to be withdrawn"), "analyst")
    park_a = Park(a.engine, r"^INSERT INTO source_sets")
    park_b = Park(b.engine, r"^UPDATE sources SET withdrawn")
    outcomes = race(
        lambda: a.ingest(_source(case["id"], "arrives during withdrawal", filename="late.txt"), "analyst-a"), park_a,
        lambda: b.withdraw(case["id"], first["id"], "analyst-b"), park_b,
        release_first=release_first,
    )
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    with a.engine.connect() as conn:
        sets = conn.execute(sa.text(
            "SELECT version, source_ids FROM source_sets WHERE case_id = :c ORDER BY version"
        ), {"c": case["id"]}).all()
    assert [version for version, _ in sets] == [1, 2, 3], "one version per governed transition, no gap or fork"
    late_id = outcomes[0][1]["id"]
    assert sets[2][1] == [late_id], "the final set holds exactly the live source"
    assert a.get_source_private(first["id"])["withdrawn"] is True
    assert sets[1][1] in ([first["id"], late_id], []), "the middle version is one of the two legal intermediate states"
    _chain_intact(a)


def test_duplicate_withdrawal_race_withdraws_once(stores):
    """Withdrawal is a governed transition: two racing withdrawals of one source
    yield one withdrawn row, one new set version and one audit event; the loser
    is told the source is no longer active (None), not handed a second success."""
    a, b = stores
    case = _seed_case(a)
    source = a.ingest(_source(case["id"], "withdraw me"), "analyst")
    park_a = Park(a.engine, r"^UPDATE sources SET withdrawn")
    park_b = Park(b.engine, r"^UPDATE sources SET withdrawn")
    outcomes = race(
        lambda: a.withdraw(case["id"], source["id"], "analyst-a"), park_a,
        lambda: b.withdraw(case["id"], source["id"], "analyst-b"), park_b,
    )
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    values = sorted((value is not None for _, value in outcomes))
    assert values == [False, True], "exactly one withdrawal wins; the other sees an already-withdrawn source"
    assert a.current_source_set(case["id"])["version"] == 2, "one source-set transition for one withdrawal"
    assert len(_audit_actions(a, "source.withdrawn")) == 1
    _chain_intact(a)


# --- assumption creation and withdrawal (SPEC_RECONCILIATION D3) -------------------


@pytest.mark.parametrize("release_first", ["assumption", "withdrawal"])
def test_assumption_creation_and_withdrawal_serialize(stores, release_first):
    """An assumption never ends READY while citing a withdrawn source: either
    the save refuses (EVIDENCE_SOURCE_WITHDRAWN) or the withdrawal stales it."""
    a, b = stores
    case = _seed_case(a)
    source = a.ingest(_source(case["id"], "cited evidence"), "analyst")
    park_a = Park(a.engine, r"^INSERT INTO assumptions")
    park_b = Park(b.engine, r"^UPDATE sources SET withdrawn")
    outcomes = race(
        lambda: a.save_assumption(case["id"], {"k": "v"}, [source["id"]], "analyst-a"), park_a,
        lambda: b.withdraw(case["id"], source["id"], "analyst-b"), park_b,
        release_first="a" if release_first == "assumption" else "b",
    )
    assumption_outcome, withdrawal_outcome = outcomes
    assert withdrawal_outcome[0] == "ok" and withdrawal_outcome[1] is not None
    kind, value = assumption_outcome
    if kind == "error":
        assert isinstance(value, ValueError) and str(value) == "EVIDENCE_SOURCE_WITHDRAWN"
        assert a.list_assumptions(case["id"]) == []
    else:
        stored = a.list_assumptions(case["id"])
        assert len(stored) == 1 and stored[0]["id"] == value["id"]
        assert stored[0]["stale"] is True and stored[0]["status"] == "STALE", \
            "an assumption citing a withdrawn source is never READY"
    _chain_intact(a)


# --- loan-universe import and withdrawal (SPEC_RECONCILIATION D3) -----------------


@pytest.mark.parametrize("release_first", ["import", "withdrawal"])
def test_loan_universe_import_and_withdrawal_serialize(stores, release_first):
    """The other deferred D3 row: no ACTIVE universe ever outlives its source."""
    a, b = stores
    case = _seed_case(a)
    source = a.ingest(_source(case["id"], "loan workbook", filename="loans.xlsx"), "analyst")
    park_a = Park(a.engine, r"^INSERT INTO loan_universes")
    park_b = Park(b.engine, r"^UPDATE sources SET withdrawn")
    outcomes = race(
        lambda: a.save_loan_universe(_loan_record(case["id"], source), "analyst-a"), park_a,
        lambda: b.withdraw(case["id"], source["id"], "analyst-b"), park_b,
        release_first="a" if release_first == "import" else "b",
    )
    import_outcome, withdrawal_outcome = outcomes
    assert withdrawal_outcome == ("ok", withdrawal_outcome[1]) and withdrawal_outcome[1] is not None
    kind, value = import_outcome
    if kind == "error":
        assert "RV_SOURCE_NOT_ACTIVE" in str(value)
        assert a.list_loan_universes(case["id"]) == []
    else:
        universes = a.list_loan_universes(case["id"])
        assert [u["status"] for u in universes] == ["WITHDRAWN"]
    assert a.active_loan_universe(case["id"]) is None
    _chain_intact(a)


# --- run-event sequence allocation --------------------------------------------------


def test_event_sequence_allocation_serializes_two_writers_on_one_run(stores):
    """Two connections transitioning two nodes of one run: both events land,
    `seq` stays gap-free and unique, no raw primary-key violation."""
    a, b = stores
    case = _seed_case(a)
    run_store_a, run = _seed_run(a, case["id"], ("CP-0", "CP-1"))
    run_store_b = RunStore(b.engine)
    before = [event["id"] for event in run_store_a.events_after(run["id"], 0)]
    park_a = Park(a.engine, r"^INSERT INTO run_events")
    park_b = Park(b.engine, r"^INSERT INTO run_events")
    outcomes = race(
        lambda: run_store_a.node_running(run["id"], "CP-0"), park_a,
        lambda: run_store_b.node_running(run["id"], "CP-1"), park_b,
    )
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    events = run_store_a.events_after(run["id"], 0)
    seqs = [event["id"] for event in events]
    assert seqs == list(range(1, len(before) + 3)), "contiguous, unique, monotonic sequence"
    assert sorted(event["data"]["module_id"] for event in events if event["event"] == "node.running") == ["CP-0", "CP-1"]


# --- budget reserve, reconcile and charge (invariant 8) --------------------------


def _budget_run(store: DomainStore, limits: dict[str, Any]) -> tuple[RunStore, str]:
    case = _seed_case(store)
    run_store, run = _seed_run(store, case["id"])
    run_store.init_budget(run["id"], limits)
    return run_store, run["id"]


def test_budget_reserve_race_has_one_reservation_and_one_typed_refusal(stores):
    """Two reservations for one run: one holds the in-flight digest, the other
    is refused before overspend; `used` reflects exactly one turn."""
    a, b = stores
    run_store_a, run_id = _budget_run(a, {"turns": 10, "input_tokens": 1000, "output_tokens": 1000})
    run_store_b = RunStore(b.engine)
    park_a = Park(a.engine, r"^UPDATE run_budgets")
    park_b = Park(b.engine, r"^UPDATE run_budgets")
    outcomes = race(
        lambda: run_store_a.reserve_provider(run_id, "a" * 64, 100, 100, False), park_a,
        lambda: run_store_b.reserve_provider(run_id, "b" * 64, 100, 100, False), park_b,
    )
    _winner, loser = _one_winner(outcomes)
    assert isinstance(loser, StoreConflict) and loser.code == "AGENT_BUDGET_EXCEEDED"
    budget = run_store_a.get_budget(run_id)
    winner_digest = "a" * 64 if outcomes[0][0] == "ok" else "b" * 64
    assert budget["inflight_request_digest"] == winner_digest
    assert budget["used"] == {"turns": 1, "input_tokens": 100, "output_tokens": 100}


def test_budget_reconcile_race_applies_the_true_up_exactly_once(stores):
    a, b = stores
    run_store_a, run_id = _budget_run(a, {"turns": 10, "input_tokens": 1000, "output_tokens": 1000})
    run_store_b = RunStore(b.engine)
    run_store_a.reserve_provider(run_id, "c" * 64, 100, 100, False)
    park_a = Park(a.engine, r"^UPDATE run_budgets")
    park_b = Park(b.engine, r"^UPDATE run_budgets")
    _winner, loser = _one_winner(race(
        lambda: run_store_a.reconcile_provider(run_id, "c" * 64, 100, 100, 130, 70), park_a,
        lambda: run_store_b.reconcile_provider(run_id, "c" * 64, 100, 100, 130, 70), park_b,
    ))
    assert isinstance(loser, StoreConflict) and loser.code == "AGENT_AUTHORITY_MISMATCH"
    budget = run_store_a.get_budget(run_id)
    assert budget["inflight_request_digest"] is None
    assert budget["used"] == {"turns": 1, "input_tokens": 130, "output_tokens": 70}, "the true-up lands once"


def test_budget_charge_race_refuses_the_ceiling_before_overspend(stores):
    a, b = stores
    run_store_a, run_id = _budget_run(a, {"turns": 10, "input_tokens": 1000, "output_tokens": 1000, "active_minutes": 8})
    run_store_b = RunStore(b.engine)
    park_a = Park(a.engine, r"^UPDATE run_budgets")
    park_b = Park(b.engine, r"^UPDATE run_budgets")
    _winner, loser = _one_winner(race(
        lambda: run_store_a.charge_budget(run_id, "active_minutes", 5), park_a,
        lambda: run_store_b.charge_budget(run_id, "active_minutes", 5), park_b,
    ))
    assert isinstance(loser, StoreConflict) and loser.code == "AGENT_BUDGET_EXCEEDED"
    assert run_store_a.get_budget(run_id)["used"]["active_minutes"] == 5, "no lost update, no overspend"


# --- run acceptance (SIM-007 atomicity, SIM-012 one winner) ---------------------------


def test_snapshot_acceptance_race_moves_the_case_and_run_pointers_once(stores):
    a, b = stores
    case = _seed_case(a)
    run_one = _succeeded_run(a, case["id"])
    run_two = _succeeded_run(a, case["id"])
    run_store_a, run_store_b = RunStore(a.engine), RunStore(b.engine)
    park_a = Park(a.engine, r"^UPDATE cases SET accepted_snapshot_id")
    park_b = Park(b.engine, r"^UPDATE cases SET accepted_snapshot_id")
    snapshot_one, snapshot_two = _snapshot(case["id"], run_one), _snapshot(case["id"], run_two)
    outcomes = race(
        lambda: run_store_a.accept_snapshot(snapshot_one, actor="analyst-a", audit=a._audit), park_a,
        lambda: run_store_b.accept_snapshot(snapshot_two, actor="analyst-b", audit=b._audit), park_b,
    )
    winner, loser = _one_winner(outcomes)
    assert isinstance(loser, StoreConflict) and loser.code == "SNAPSHOT_AUTHORITY_CHANGED"
    assert a.get_case(case["id"])["accepted_snapshot_id"] == winner["id"]
    accepted = {run_store_a.get_run(run_one)["accepted_snapshot_id"], run_store_a.get_run(run_two)["accepted_snapshot_id"]}
    assert accepted == {winner["id"], None}, "the losing run keeps its acceptance available; nothing half-moved"
    assert run_store_a.get_snapshot(winner["id"]) is not None and run_store_a.snapshot_for_run(loser_run := (run_two if winner["run_id"] == run_one else run_one)) is None
    assert loser_run in (run_one, run_two)
    assert len(_audit_actions(a, "snapshot.accepted")) == 1
    _chain_intact(a)


# --- model build claim and queue (SIM-015) --------------------------------------------


def test_model_build_claim_race_has_one_executor(stores):
    a, b = stores
    case = _seed_case(a)
    models_a, models_b = ModelStore(a.engine), ModelStore(b.engine)
    build = models_a.insert_build_row({
        "id": new_id("mdl"), "case_id": case["id"], "status": "QUEUED", "accepted_run_id": "run-x",
        "snapshot_id": "snap-x", "input_fingerprint": "f" * 64, "queued_at": now_iso(), "created_by": "analyst",
    })
    park_a = Park(a.engine, r"^UPDATE model_builds")
    park_b = Park(b.engine, r"^UPDATE model_builds")
    outcomes = race(
        lambda: models_a.update_build(build["id"], expected_status=("QUEUED", "FAILED"), status="BUILDING"), park_a,
        lambda: models_b.update_build(build["id"], expected_status=("QUEUED", "FAILED"), status="BUILDING"), park_b,
    )
    assert sorted(value for kind, value in outcomes) == [False, True], "one executor claims, one exits without mutation"
    assert models_a.get_build(build["id"])["status"] == "BUILDING"


def test_model_queue_race_is_idempotent_with_one_attributed_winner(stores):
    a, b = stores
    case = _seed_case(a)
    models_a, models_b = ModelStore(a.engine), ModelStore(b.engine)
    spec = {"case_id": case["id"], "accepted_run_id": "run-x", "snapshot_id": "snap-x", "input_fingerprint": "f" * 64}
    park_a = Park(a.engine, r"^INSERT INTO model_builds")
    park_b = Park(b.engine, r"^INSERT INTO model_builds")
    outcomes = race(lambda: models_a.queue_build(spec, "analyst-a"), park_a,
                    lambda: models_b.queue_build(spec, "analyst-b"), park_b)
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    (build_a, created_a), (build_b, created_b) = outcomes[0][1], outcomes[1][1]
    assert sorted([created_a, created_b]) == [False, True]
    assert build_a["id"] == build_b["id"]
    assert len(models_a.list_builds(case["id"])) == 1


# --- model sign-off (SIM-016) ------------------------------------------------------


@pytest.mark.parametrize("existing_head", [False, True])
def test_model_sign_off_race_has_one_revision_and_one_typed_conflict(stores, existing_head):
    a, b = stores
    case = _seed_case(a)
    models_a, models_b = ModelStore(a.engine), ModelStore(b.engine)
    expected_head = None
    if existing_head:
        head = models_a.sign_off_revision(case["id"], _revision_record(case["id"], "build-race", "base"), "analyst",
                                          None, a._audit)
        expected_head = head["id"]
    park_a = Park(a.engine, r"^INSERT INTO model_revisions")
    park_b = Park(b.engine, r"^INSERT INTO model_revisions")
    winner, loser = _one_winner(race(
        lambda: models_a.sign_off_revision(case["id"], _revision_record(case["id"], "build-race", "writer A"),
                                           "analyst-a", expected_head, a._audit), park_a,
        lambda: models_b.sign_off_revision(case["id"], _revision_record(case["id"], "build-race", "writer B"),
                                           "analyst-b", expected_head, b._audit), park_b,
    ))
    assert isinstance(loser, ModelRevisionConflict), f"the loser is the typed conflict, got {loser!r}"
    assert loser.current is not None and loser.current["id"] == winner["id"], "the conflict names the winner"
    head = models_a.head_revision(case["id"])
    assert head["id"] == winner["id"] and head["revision_number"] == (2 if existing_head else 1)
    assert models_a.revision_order(case["id"]) == list(range(1, head["revision_number"] + 1))
    assert len(_audit_actions(a, "model.revision.signed")) == head["revision_number"]
    _chain_intact(a)


# --- opinion sign-off, draft save, freeze, publication, filing (SIM-017) ---------------


def test_opinion_sign_off_race_leaves_one_head(stores):
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    park_a = Park(a.engine, r"^INSERT INTO deliverable_opinions")
    park_b = Park(b.engine, r"^INSERT INTO deliverable_opinions")
    winner, loser = _one_winner(race(
        lambda: deliverables_a.sign_opinion(_opinion_record(case["id"], "rev-1", "A signs"), None, "analyst-a", a._audit), park_a,
        lambda: deliverables_b.sign_opinion(_opinion_record(case["id"], "rev-1", "B signs"), None, "analyst-b", b._audit), park_b,
    ))
    assert isinstance(loser, OpinionHeadConflict), f"the loser is the typed head conflict, got {loser!r}"
    assert loser.current is not None and loser.current["opinion_id"] == winner["opinion_id"]
    history = deliverables_a.opinion_history(case["id"], "FULL_CREDIT")
    assert [row["opinion_id"] for row in history] == [winner["opinion_id"]], "one head, never two"
    assert len(_audit_actions(a, "deliverable.opinion.signed")) == 1
    _chain_intact(a)


def test_draft_save_race_conflict_carries_the_committed_head(stores):
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    content_a, content_b = {"blocks": ["A"]}, {"blocks": ["B"]}
    park_a = Park(a.engine, r"^INSERT INTO deliverable_revisions")
    park_b = Park(b.engine, r"^INSERT INTO deliverable_revisions")
    winner, loser = _one_winner(race(
        lambda: deliverables_a.append_revision(case["id"], "FULL_CREDIT", 0, content_a, digest(content_a), "analyst-a", a._audit), park_a,
        lambda: deliverables_b.append_revision(case["id"], "FULL_CREDIT", 0, content_b, digest(content_b), "analyst-b", b._audit), park_b,
    ))
    assert isinstance(loser, DeliverableVersionConflict)
    assert loser.current is not None and loser.current["revision_id"] == winner["revision_id"], \
        "the 409 carries the head that actually committed, so the client can rebase once"
    assert [row["version"] for row in deliverables_a.revision_history(case["id"], "FULL_CREDIT")] == [1]
    _chain_intact(a)


def test_freeze_request_race_converges_on_one_job(stores):
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    record = _frozen_record(case["id"], "dlv-race")
    park_a = Park(a.engine, r"^INSERT INTO deliverable_freeze_jobs")
    park_b = Park(b.engine, r"^INSERT INTO deliverable_freeze_jobs")
    outcomes = race(lambda: deliverables_a.request_freeze(record, "analyst-a", a._audit), park_a,
                    lambda: deliverables_b.request_freeze(record, "analyst-b", b._audit), park_b)
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    assert outcomes[0][1]["job_id"] == outcomes[1][1]["job_id"], "racing freeze requests converge on one job"
    assert len(deliverables_a.pending_freeze_jobs(case["id"])) == 1
    assert len(_audit_actions(a, "deliverable.freeze_queued")) == 1
    _chain_intact(a)


def test_freeze_claim_race_has_one_renderer(stores):
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    job = deliverables_a.request_freeze(_frozen_record(case["id"], "dlv-claim"), "analyst", a._audit)
    park_a = Park(a.engine, r"^UPDATE deliverable_freeze_jobs")
    park_b = Park(b.engine, r"^UPDATE deliverable_freeze_jobs")
    outcomes = race(lambda: deliverables_a.claim_freeze_job(job["job_id"]), park_a,
                    lambda: deliverables_b.claim_freeze_job(job["job_id"]), park_b)
    assert sorted(value is not None for _, value in outcomes) == [False, True]
    assert deliverables_a.freeze_job(job["job_id"])["status"] == "RENDERING"


def test_publish_frozen_race_converges_on_one_record_and_one_thread(stores):
    """Two renders of one freeze identity (a worker restarted under its own
    claim, or a duplicate worker) converge: one record, one parked thread."""
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    record = _frozen_record(case["id"], "dlv-publish")
    job = deliverables_a.request_freeze(record, "analyst", a._audit)
    assert deliverables_a.claim_freeze_job(job["job_id"]) is not None
    park_a = Park(a.engine, r"^INSERT INTO deliverable_frozen")
    park_b = Park(b.engine, r"^INSERT INTO deliverable_frozen")
    outcomes = race(lambda: deliverables_a.publish_frozen(job["job_id"], record, "worker-a", a._audit), park_a,
                    lambda: deliverables_b.publish_frozen(job["job_id"], record, "worker-b", b._audit), park_b)
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    created = sorted(created for _, (_frozen, created) in outcomes)
    assert created == [False, True], "one render publishes, the other converges on it"
    assert deliverables_a.frozen_record(case["id"], "dlv-publish")["status"] == "FROZEN"
    with a.engine.connect() as conn:
        threads = conn.execute(sa.text("SELECT count(*) FROM deliverable_threads WHERE deliverable_id = 'dlv-publish'")).scalar_one()
    assert threads == 1
    assert len(_audit_actions(a, "deliverable.frozen")) == 1
    _chain_intact(a)


def test_filing_race_files_once_with_one_receipt(stores):
    """SIM-017: two approvers file the same digest; one FILED record, one receipt,
    one `deliverable.filed` event; the loser gets None (RESUME_NOT_APPLIED upstream)."""
    a, b = stores
    case = _seed_case(a)
    deliverables_a, deliverables_b = DeliverableStore(a.engine), DeliverableStore(b.engine)
    record = _frozen_record(case["id"], "dlv-file")
    job = deliverables_a.request_freeze(record, "analyst", a._audit)
    deliverables_a.claim_freeze_job(job["job_id"])
    deliverables_a.publish_frozen(job["job_id"], record, "worker", a._audit)
    park_a = Park(a.engine, r"^UPDATE deliverable_frozen")
    park_b = Park(b.engine, r"^UPDATE deliverable_frozen")
    outcomes = race(lambda: deliverables_a.file_record("dlv-file", "approver-a", a._audit), park_a,
                    lambda: deliverables_b.file_record("dlv-file", "approver-b", b._audit), park_b)
    assert [kind for kind, _ in outcomes] == ["ok", "ok"], outcomes
    filed = [value for _, value in outcomes if value is not None]
    assert len(filed) == 1 and filed[0]["status"] == "FILED"
    receipts = deliverables_a.filing_receipts(case["id"])
    assert len(receipts) == 1 and receipts[0]["approved_by"] == filed[0]["filed_by"]
    assert len(_audit_actions(a, "deliverable.filed")) == 1
    _chain_intact(a)


# --- SIM-011: the connection drops after the write was acknowledged ---------------------


def test_disconnect_after_an_acknowledged_write_is_resolved_by_idempotent_retry(stores):
    """SIM-011: the client commits, then its backend dies before it reads the
    acknowledgement. On a fresh connection the same request converges on the
    committed state — the same freeze job, the acceptance already consumed with
    the committed snapshot in place — and nothing is written twice."""
    a, b = stores
    case = _seed_case(a)
    deliverables_a = DeliverableStore(a.engine)
    record = _frozen_record(case["id"], "dlv-ack")
    first = deliverables_a.request_freeze(record, "analyst", a._audit)

    def kill_every_backend_of(store: DomainStore) -> None:
        with b.engine.connect() as conn:
            pids = conn.execute(sa.text(
                "SELECT pid FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = current_database()"
            )).scalars().all()
            for pid in pids:
                if pid != _backend_pid(b):
                    conn.execute(sa.text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})

    kill_every_backend_of(a)
    outcomes = []
    for _attempt in range(3):
        try:
            outcomes.append(("ok", deliverables_a.request_freeze(record, "analyst", a._audit)))
            break
        except sa.exc.DBAPIError as exc:  # the dropped connection surfaces once, typed by the driver, then the pool recovers
            outcomes.append(("disconnect", type(exc).__name__))
    assert outcomes[-1][0] == "ok", outcomes
    assert outcomes[-1][1]["job_id"] == first["job_id"], "the retry converges on the committed job"
    assert len(deliverables_a.pending_freeze_jobs(case["id"])) == 1
    assert len(_audit_actions(a, "deliverable.freeze_queued")) == 1

    run_id = _succeeded_run(a, case["id"])
    run_store = RunStore(a.engine)
    snapshot = _snapshot(case["id"], run_id)
    accepted = run_store.accept_snapshot(snapshot, actor="analyst", audit=a._audit)
    kill_every_backend_of(a)
    for _attempt in range(3):
        try:
            with pytest.raises(StoreConflict) as conflict:
                run_store.accept_snapshot(snapshot, actor="analyst", audit=a._audit)
            break
        except sa.exc.DBAPIError:
            continue
    assert conflict.value.code == "RUN_NOT_READY", "the acceptance was consumed by the committed write"
    assert run_store.snapshot_for_run(run_id)["id"] == accepted["id"]
    assert a.get_case(case["id"])["accepted_snapshot_id"] == accepted["id"]
    assert len(_audit_actions(a, "snapshot.accepted")) == 1
    _chain_intact(a)
