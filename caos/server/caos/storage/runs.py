"""Run-engine store: runs, nodes, artifacts, events, snapshots, budget ledger,
resume tickets, execution counters.

Fresh code — nothing from LEGACY store.py/ledgers is ported. Contracts kept:
state+event commit in one transaction; every event insert rides a conditional
state transition (zero rows updated -> no event), so terminal events are
exactly-once by construction (§12.13); complete_node is validate-then-replace
on the (run_id, module_id, input_fingerprint) unique key (§12.8).
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from ..contracts import digest
from ..observability import log_event
from .store import new_id, now_iso

run_metadata = sa.MetaData()

runs = sa.Table(
    "runs", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("depth", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("plan", sa.JSON, nullable=False),
    sa.Column("plan_digest", sa.String),
    sa.Column("error", sa.JSON),
    sa.Column("focus_questions", sa.JSON, nullable=False, default=list),
    sa.Column("accepted_snapshot_id", sa.String),
    sa.Column("upgraded_from_run_id", sa.String),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("schema_version", sa.String, nullable=False),
)

run_nodes = sa.Table(
    "run_nodes", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
    sa.Column("stage", sa.Integer, nullable=False),
    sa.Column("dependencies", sa.JSON, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("attempt", sa.Integer, nullable=False, default=0),
    sa.Column("artifact_id", sa.String),
    sa.Column("error", sa.JSON),
    sa.UniqueConstraint("run_id", "module_id", name="uq_run_nodes_run_module"),
)

run_artifacts = sa.Table(
    "run_artifacts", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
    sa.Column("input_fingerprint", sa.String, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("markdown", sa.Text),
    sa.Column("digest", sa.String, nullable=False),
    sa.Column("qa_status", sa.String),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.UniqueConstraint("run_id", "module_id", "input_fingerprint", name="uq_artifact_exec_key"),
)

run_events = sa.Table(
    "run_events", run_metadata,
    sa.Column("run_id", sa.String, primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("event", sa.String, nullable=False),
    sa.Column("at", sa.String, nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
)

run_snapshots = sa.Table(
    "run_snapshots", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("run_id", sa.String, nullable=False, unique=True),
    sa.Column("source_set_id", sa.String, nullable=False),
    sa.Column("source_set_version", sa.Integer, nullable=False),
    sa.Column("artifacts", sa.JSON, nullable=False),
    sa.Column("digest", sa.String, nullable=False),
    sa.Column("previous_snapshot_id", sa.String),
    sa.Column("accepted_at", sa.String, nullable=False),
)

run_budgets = sa.Table(
    "run_budgets", run_metadata,
    sa.Column("run_id", sa.String, primary_key=True),
    sa.Column("limits", sa.JSON, nullable=False),
    sa.Column("used", sa.JSON, nullable=False),
    sa.Column("inflight_request_digest", sa.String),
    sa.Column("attempts", sa.JSON, nullable=False),
)

resume_tickets = sa.Table(
    "resume_tickets", run_metadata,
    sa.Column("thread_id", sa.String, primary_key=True),
    sa.Column("interrupt_id", sa.String, primary_key=True),
    sa.Column("consumed", sa.Integer, nullable=False, default=0),
    sa.Column("created_at", sa.String, nullable=False),
)

executions = sa.Table(
    "executions", run_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
)


class StoreConflict(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


TERMINAL = {"succeeded", "failed"}


class RunStore:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine
        run_metadata.create_all(engine)

    # -- events (always inside a caller transaction) ----------------------

    def _emit(self, conn: sa.Connection, run_id: str, event: str, **data: Any) -> None:
        next_seq = conn.execute(
            sa.select(sa.func.coalesce(sa.func.max(run_events.c.seq), 0) + 1).where(run_events.c.run_id == run_id)
        ).scalar_one()
        conn.execute(run_events.insert().values(run_id=run_id, seq=next_seq, event=event, at=now_iso(), data=data))
        # Every durable run/node transition passes through here and nowhere
        # else, so one line here is the whole "which run is stuck" answer.
        # `data` is host-owned identifiers only — never anything a document
        # produced. Merged as a dict rather than **kwargs so a future event
        # carrying its own `run_id` cannot raise TypeError and take the state
        # transition down with it: logging never breaks a run. It does ride
        # inside the caller's transaction, so a failing commit leaves one line
        # describing a transition that rolled back — the run dies in the same
        # breath, and the single seam is worth that much drift.
        log_event(event, **{**data, "run_id": run_id, "seq": next_seq})

    def events_after(self, run_id: str, after_seq: int) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(run_events).where(run_events.c.run_id == run_id, run_events.c.seq > after_seq).order_by(run_events.c.seq)
            ).mappings().all()
        return [{"id": r["seq"], "event": r["event"], "at": r["at"], "data": r["data"]} for r in rows]

    # -- runs ---------------------------------------------------------------

    def create_run(self, case_id: str, pathway: str, depth: str, actor: str, *,
                   focus_questions: list[str] | None = None,
                   upgraded_from_run_id: str | None = None,
                   schema_version: str = "caos-state-v1") -> dict[str, Any]:
        run_id = new_id("run")
        with self.engine.begin() as conn:
            conn.execute(runs.insert().values(
                id=run_id, case_id=case_id, pathway=pathway, depth=depth, status="queued",
                plan={}, plan_digest=None, error=None, focus_questions=list(focus_questions or []),
                accepted_snapshot_id=None, upgraded_from_run_id=upgraded_from_run_id,
                created_by=actor, created_at=now_iso(), schema_version=schema_version,
            ))
            self._emit(conn, run_id, "run.created", case_id=case_id, pathway=pathway, depth=depth)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(runs).where(runs.c.id == run_id)).mappings().first()
            if row is None:
                return None
            node_rows = conn.execute(
                sa.select(run_nodes).where(run_nodes.c.run_id == run_id).order_by(run_nodes.c.stage, run_nodes.c.module_id)
            ).mappings().all()
        record = dict(row)
        record["nodes"] = [dict(node) for node in node_rows]
        record["node_ids"] = [node["id"] for node in node_rows]
        return record

    def non_terminal_runs(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(runs).where(runs.c.status.notin_(TERMINAL))).mappings().all()
        return [dict(row) for row in rows]

    def active_admission_count(self) -> int:
        """§12: derived, never stored. Interrupt-paused threads hold no slot."""
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count()).where(runs.c.status.in_(("queued", "running")))
            ).scalar_one()

    def pause_run(self, run_id: str, code: str) -> str:
        """Pause at the entry gate; writes the one-shot resume ticket (§12.21).
        A re-pause supersedes any stale unconsumed ticket (no stranded ticket
        population) and emits run.paused only on a real status transition."""
        with self.engine.begin() as conn:
            previous = conn.execute(sa.select(runs.c.status).where(runs.c.id == run_id)).scalar()
            if previous in TERMINAL or previous is None:
                raise StoreConflict("RESUME_NOT_APPLIED", "run is terminal")
            conn.execute(sa.update(runs).where(runs.c.id == run_id).values(status="paused", error={"code": code}))
            conn.execute(
                sa.update(resume_tickets)
                .where(resume_tickets.c.thread_id == run_id, resume_tickets.c.consumed == 0)
                .values(consumed=1)
            )
            ticket = f"int-{new_id('t')[2:]}"
            conn.execute(resume_tickets.insert().values(
                thread_id=run_id, interrupt_id=ticket, consumed=0, created_at=now_iso(),
            ))
            if previous != "paused":
                self._emit(conn, run_id, "run.paused", code=code, interrupt_id=ticket)
            return ticket

    def latest_ticket(self, run_id: str) -> str | None:
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(resume_tickets.c.interrupt_id)
                .where(resume_tickets.c.thread_id == run_id, resume_tickets.c.consumed == 0)
                .order_by(resume_tickets.c.created_at.desc())
                .limit(1)
            ).scalar()

    def consume_ticket(self, run_id: str, interrupt_id: str) -> bool:
        with self.engine.begin() as conn:
            return bool(conn.execute(
                sa.update(resume_tickets)
                .where(
                    resume_tickets.c.thread_id == run_id,
                    resume_tickets.c.interrupt_id == interrupt_id,
                    resume_tickets.c.consumed == 0,
                )
                .values(consumed=1)
            ).rowcount)

    def pin_plan(self, run_id: str, plan: dict[str, Any], plan_digest: str) -> None:
        """Gate-exit pin: written exactly once (CAS on unpinned), node rows
        created, run leaves paused/queued for running."""
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs)
                .where(runs.c.id == run_id, runs.c.plan_digest.is_(None), runs.c.status.notin_(TERMINAL))
                .values(plan=plan, plan_digest=plan_digest, status="running", error=None)
            ).rowcount
            if not changed:
                # Re-executed gate after crash: pin already written; just leave paused state.
                conn.execute(
                    sa.update(runs)
                    .where(runs.c.id == run_id, runs.c.status == "paused", runs.c.plan_digest.isnot(None))
                    .values(status="running", error=None)
                )
                return
            case_id = conn.execute(sa.select(runs.c.case_id).where(runs.c.id == run_id)).scalar_one()
            for node in plan["nodes"]:
                conn.execute(run_nodes.insert().values(
                    id=new_id("node"), run_id=run_id, case_id=case_id, module_id=node["module_id"],
                    stage=node["stage"], dependencies=node["dependencies"], status="pending",
                    attempt=0, artifact_id=None, error=None,
                ))
            self._emit(conn, run_id, "run.running")

    def node_running(self, run_id: str, module_id: str) -> None:
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(run_nodes)
                .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id,
                       run_nodes.c.status.in_(("pending", "ready")))
                .values(status="running", attempt=run_nodes.c.attempt + 1)
            ).rowcount
            if changed:
                self._emit(conn, run_id, "node.running", module_id=module_id)

    def find_valid_artifact(self, run_id: str, module_id: str, input_fingerprint: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(run_artifacts).where(
                    run_artifacts.c.run_id == run_id,
                    run_artifacts.c.module_id == module_id,
                    run_artifacts.c.input_fingerprint == input_fingerprint,
                )
            ).mappings().first()
        if row is None:
            return None
        artifact = dict(row)
        if digest(artifact["payload"]) != artifact["digest"]:
            return None
        return artifact

    def complete_node(
        self,
        run_id: str,
        case_id: str,
        module_id: str,
        input_fingerprint: str,
        payload: dict[str, Any],
        markdown: str | None,
        qa_status: str | None,
        actor: str,
    ) -> dict[str, Any]:
        """§12.8 validate-then-replace, one transaction: artifact link/relink,
        node completion, execution marker, node.succeeded event (conditional)."""
        with self.engine.begin() as conn:
            existing = conn.execute(
                sa.select(run_artifacts).where(
                    run_artifacts.c.run_id == run_id,
                    run_artifacts.c.module_id == module_id,
                    run_artifacts.c.input_fingerprint == input_fingerprint,
                )
            ).mappings().first()
            if existing is not None and digest(existing["payload"]) == existing["digest"]:
                artifact = dict(existing)  # relink: discard candidate, keep stored ids
            else:
                if existing is not None:
                    conn.execute(sa.delete(run_artifacts).where(run_artifacts.c.id == existing["id"]))
                artifact = {
                    "id": new_id("art"), "run_id": run_id, "case_id": case_id, "module_id": module_id,
                    "input_fingerprint": input_fingerprint, "payload": payload, "markdown": markdown,
                    "digest": digest(payload), "qa_status": qa_status,
                    "created_by": actor, "created_at": now_iso(),
                }
                conn.execute(run_artifacts.insert().values(**artifact))
                conn.execute(executions.insert().values(run_id=run_id, module_id=module_id))
            changed = conn.execute(
                sa.update(run_nodes)
                .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id,
                       run_nodes.c.status != "succeeded")
                .values(status="succeeded", artifact_id=artifact["id"], error=None)
            ).rowcount
            if changed:
                self._emit(conn, run_id, "node.succeeded", module_id=module_id, artifact_id=artifact["id"])
            return artifact

    def finalize_success(self, run_id: str) -> bool:
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs).where(runs.c.id == run_id, runs.c.status == "running").values(status="succeeded", error=None)
            ).rowcount
            if changed:
                self._emit(conn, run_id, "run.succeeded")
            return bool(changed)

    def finalize_failure(self, run_id: str, code: str, module_id: str | None) -> bool:
        error = {"code": code}
        if module_id:
            error["module_id"] = module_id
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs).where(runs.c.id == run_id, runs.c.status.notin_(TERMINAL)).values(status="failed", error=error)
            ).rowcount
            if changed:
                if module_id:
                    conn.execute(
                        sa.update(run_nodes)
                        .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id)
                        .values(status="failed", error=error)
                    )
                # Siblings of the blamed module were mid-superstep; the run is over, so
                # their work is abandoned, not failed (the error belongs to one module).
                # ponytail: only `running` lies on a terminal record — `pending` stays
                # true forever, and recover() never revisits a terminal run.
                conn.execute(
                    sa.update(run_nodes)
                    .where(run_nodes.c.run_id == run_id, run_nodes.c.status == "running")
                    .values(status="cancelled")
                )
                self._emit(conn, run_id, "run.failed", **error)
            return bool(changed)

    # -- artifacts ---------------------------------------------------------

    def artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(run_artifacts).where(run_artifacts.c.run_id == run_id).order_by(run_artifacts.c.created_at)
            ).mappings().all()
        return [dict(row) for row in rows]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_artifacts).where(run_artifacts.c.id == artifact_id)).mappings().first()
        return dict(row) if row else None

    def update_artifact_for_tests(self, run_id: str, module_id: str, **values: Any) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                sa.update(run_artifacts)
                .where(run_artifacts.c.run_id == run_id, run_artifacts.c.module_id == module_id)
                .values(**values)
            )

    # -- execution counters (test observability) ---------------------------

    def executed_modules(self, run_id: str) -> list[str]:
        with self.engine.connect() as conn:
            return list(conn.execute(
                sa.select(executions.c.module_id).where(executions.c.run_id == run_id).order_by(executions.c.seq)
            ).scalars().all())

    def execution_counts(self, run_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for module_id in self.executed_modules(run_id):
            counts[module_id] = counts.get(module_id, 0) + 1
        return counts

    # -- budget ledger ------------------------------------------------------

    def init_budget(self, run_id: str, limits: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(sa.select(run_budgets.c.run_id).where(run_budgets.c.run_id == run_id)).first()
            if existing is None:
                conn.execute(run_budgets.insert().values(
                    run_id=run_id, limits=limits, used={key: 0 for key in limits},
                    inflight_request_digest=None, attempts=[],
                ))

    def get_budget(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_budgets).where(run_budgets.c.run_id == run_id)).mappings().first()
        return dict(row) if row else None

    def _budget_locked(self, conn: sa.Connection, run_id: str) -> dict[str, Any]:
        row = conn.execute(sa.select(run_budgets).where(run_budgets.c.run_id == run_id)).mappings().first()
        if row is None:
            raise StoreConflict("AGENT_BUDGET_EXCEEDED", "budget ledger missing")
        return dict(row)

    def reserve_provider(self, run_id: str, request_digest: str, input_tokens: int, output_tokens: int, retry: bool) -> None:
        """§12.12: reserve persists the inflight digest before create; a retry
        requires inflight == digest and is budget-free."""
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            used, limits = dict(budget["used"]), budget["limits"]
            inflight = budget["inflight_request_digest"]
            if retry:
                if inflight != request_digest:
                    raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "provider retry request changed")
                log_event("budget.reserved", run_id=run_id, request_digest=request_digest,
                          retry=True, used=used)
                return
            if inflight:
                raise StoreConflict("AGENT_BUDGET_EXCEEDED", "unresolved in-flight request")
            for key, amount in (("turns", 1), ("input_tokens", input_tokens), ("output_tokens", output_tokens)):
                if used.get(key, 0) + amount > limits.get(key, 0):
                    raise StoreConflict("AGENT_BUDGET_EXCEEDED", f"{key} budget exhausted")
            for key, amount in (("turns", 1), ("input_tokens", input_tokens), ("output_tokens", output_tokens)):
                used[key] = used.get(key, 0) + amount
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(
                used=used, inflight_request_digest=request_digest,
            ))
            log_event("budget.reserved", run_id=run_id, request_digest=request_digest, retry=False,
                      input_tokens=input_tokens, output_tokens=output_tokens, used=used)

    def reconcile_provider(self, run_id: str, request_digest: str, reserved_input: int, reserved_output: int,
                           actual_input: int, actual_output: int) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            if budget["inflight_request_digest"] != request_digest:
                raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "in-flight request digest mismatch")
            used, limits = dict(budget["used"]), budget["limits"]
            used["input_tokens"] = used.get("input_tokens", 0) + actual_input - reserved_input
            used["output_tokens"] = used.get("output_tokens", 0) + actual_output - reserved_output
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(
                used=used, inflight_request_digest=None,
            ))
        # `used` after the true-up is the whole "what has it spent" answer.
        log_event("budget.reconciled", run_id=run_id, request_digest=request_digest,
                  input_tokens=actual_input, output_tokens=actual_output, used=used)
        # The correction commits BEFORE the refusal. Raising inside the
        # transaction rolled the true-up back on the one path where it matters:
        # the ledger kept showing the reservation instead of the tokens the
        # provider actually billed, and the request stayed in flight forever.
        if used["input_tokens"] > limits.get("input_tokens", 0) or used["output_tokens"] > limits.get("output_tokens", 0):
            raise StoreConflict("AGENT_BUDGET_EXCEEDED", "actual token usage exceeded the run budget")

    def charge_budget(self, run_id: str, dimension: str, amount: int | float) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            used, limits = dict(budget["used"]), budget["limits"]
            if used.get(dimension, 0) + amount > limits.get(dimension, 0):
                raise StoreConflict("AGENT_BUDGET_EXCEEDED", f"{dimension} budget exhausted")
            used[dimension] = used.get(dimension, 0) + amount
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(used=used))

    def record_attempt(self, run_id: str, row: dict[str, Any], terminal: bool) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            attempts = list(budget["attempts"])
            if terminal:
                attempts.append(row)
                attempts = attempts[-100:]
            else:
                if len(attempts) >= 100:
                    raise StoreConflict("AGENT_BUDGET_EXCEEDED", "attempt metadata budget exhausted")
                attempts.append(row)
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(attempts=attempts))

    # -- snapshots ----------------------------------------------------------

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_snapshots).where(run_snapshots.c.id == snapshot_id)).mappings().first()
        return dict(row) if row else None

    def snapshot_for_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_snapshots).where(run_snapshots.c.run_id == run_id)).mappings().first()
        return dict(row) if row else None

    def create_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as conn:
            conn.execute(run_snapshots.insert().values(**snapshot))
            conn.execute(sa.update(runs).where(runs.c.id == snapshot["run_id"]).values(accepted_snapshot_id=snapshot["id"]))
        return snapshot

    def serialize_all_for_run(self, run_id: str) -> str:
        chunks: list[Any] = [self.get_run(run_id), self.events_after(run_id, 0), self.artifacts_for_run(run_id), self.get_budget(run_id)]
        return json.dumps(chunks, sort_keys=True, default=str)
