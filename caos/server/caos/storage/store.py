"""Domain store: cases, sources, source sets, notes, assumptions, audit.

Fresh code (the legacy ledger implementations are not ported). Guarantees kept
from the legacy contracts:
- every governed write commits domain state and its audit event in ONE transaction;
- source ingest is content-addressed per case (active sha256 unique, DB-enforced);
- source-set versions are immutable history rows — a source_set_id pins membership;
- withdrawal atomically versions the set, stales citing assumptions, and audits;
- public source reads never expose storage-private fields (vault_path, withdrawn_at).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import Future
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..atomic_files import (
    MAX_EXPORT_BYTES,
    VaultFileIntegrityError,
    VaultFileUnavailable,
    read_verified_vault_bytes,
)


logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:20]}"


metadata = sa.MetaData()

cases = sa.Table(
    "cases", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("issuer", sa.String, nullable=False),
    sa.Column("sector", sa.String, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("accepted_snapshot_id", sa.String),
    sa.Column("visible_snapshot_id", sa.String),
    sa.Column("current_execution_id", sa.String),
)

case_members = sa.Table(
    "case_members", metadata,
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), primary_key=True),
    sa.Column("subject", sa.String, primary_key=True),
    sa.Column("role", sa.String, nullable=False),
)

sources = sa.Table(
    "sources", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("filename", sa.String, nullable=False),
    sa.Column("media_type", sa.String, nullable=False),
    sa.Column("bytes", sa.Integer, nullable=False),
    sa.Column("sha256", sa.String(64), nullable=False),
    sa.Column("vault_path", sa.String),
    sa.Column("blocks", sa.JSON, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("withdrawn", sa.Boolean, nullable=False, default=False),
    sa.Column("withdrawn_at", sa.String),
    sa.Column("source_kind", sa.String),
    # One ACTIVE source per (case, content). Partial unique index on both dialects.
    sa.Index(
        "ix_sources_active_content", "case_id", "sha256",
        unique=True,
        sqlite_where=sa.text("NOT withdrawn"),
        postgresql_where=sa.text("NOT withdrawn"),
    ),
)

source_sets = sa.Table(
    "source_sets", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("source_ids", sa.JSON, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.UniqueConstraint("case_id", "version", name="uq_source_sets_case_version"),
)

notes = sa.Table(
    "notes", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("promoted", sa.Boolean, nullable=False, default=False),
    sa.Column("promoted_source_id", sa.String),
)

assumptions = sa.Table(
    "assumptions", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
    sa.Column("evidence_ids", sa.JSON, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("stale", sa.Boolean, nullable=False, default=False),
)

loan_universes = sa.Table(
    "loan_universes", metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("source_id", sa.String, nullable=False),
    sa.Column("source_filename", sa.String, nullable=False),
    sa.Column("source_sha256", sa.String(64), nullable=False),
    sa.Column("workbook_date", sa.String),
    sa.Column("template_version", sa.String, nullable=False),
    sa.Column("importer_version", sa.String, nullable=False),
    sa.Column("universe_digest", sa.String),
    sa.Column("row_count", sa.Integer, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("findings", sa.JSON, nullable=False),
    sa.Column("rows", sa.JSON, nullable=False),
    sa.Column("version", sa.Integer),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("activated_at", sa.String),
    sa.Column("superseded_at", sa.String),
    sa.Column("withdrawn_at", sa.String),
)

rv_universes = sa.Table(
    "rv_universes", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("rows", sa.JSON, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
)

# Document-first intake (Task 8): one row per submitted pack — the manifest,
# the host route decision, the suggestions, the run it started and any typed
# clarification — written in the same transaction as the sources it admitted,
# so refresh and restart read exactly what the analyst was shown.
case_intakes = sa.Table(
    "case_intakes", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, sa.ForeignKey("cases.id"), nullable=False),
    sa.Column("intake_key", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("record", sa.JSON, nullable=False),
    sa.Column("run_id", sa.String),
    sa.Column("refusal", sa.JSON),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("updated_at", sa.String, nullable=False),
)

audit_events = sa.Table(
    "audit_events", metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.String, nullable=False),
    sa.Column("action", sa.String, nullable=False),
    sa.Column("actor", sa.String, nullable=False),
    sa.Column("at", sa.String, nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
)

PUBLIC_SOURCE_HIDDEN = {"vault_path", "withdrawn_at"}
_INSTANCE_LOCK_NAMESPACE = int.from_bytes(b"CAOS", "big")
_INSTANCE_LOCK_ROLES = {"app": 1, "worker": 2}
_INSTANCE_LOCK_HEARTBEAT_SECONDS = 5.0
# ponytail: the app is deliberately single-instance; one process-wide lock
# makes accepted analysis, source-set mutation, and filing linearizable. Move
# this to per-case DB advisory locks if multi-app-instance throughput is added.
_AUTHORITY_MUTATION_LOCK = threading.RLock()


def _terminate_process(role: str) -> None:
    try:
        logger.critical("lost PostgreSQL advisory lock for CAOS %s; terminating", role)
    finally:
        os._exit(1)


def _public_source(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in PUBLIC_SOURCE_HIDDEN}


class DomainStore:
    def __init__(self, engine: sa.Engine, *, owns_engine: bool = False) -> None:
        self.engine = engine
        self._owns_engine = owns_engine
        self._closed = False

    @classmethod
    def from_url(cls, url: str) -> "DomainStore":
        engine = sa.create_engine(url, json_serializer=lambda value: json.dumps(value, sort_keys=True))
        try:
            metadata.create_all(engine)
        except Exception:
            engine.dispose()
            raise
        return cls(engine, owns_engine=True)

    def close(self) -> None:
        if self._closed:
            return
        if self._owns_engine:
            self.engine.dispose()
        self._closed = True

    def authority_guard(self):
        return _AUTHORITY_MUTATION_LOCK

    @contextmanager
    def single_instance(self, role: str) -> Iterator[None]:
        """Hold one PostgreSQL session lock for this process role or fail closed."""
        if self.engine.dialect.name != "postgresql":
            yield
            return

        parameters = {"namespace": _INSTANCE_LOCK_NAMESPACE, "role": _INSTANCE_LOCK_ROLES[role]}
        startup: Future[None] = Future()
        stop = threading.Event()

        def own_lock() -> None:
            try:
                with self.engine.connect() as connection:
                    acquired = bool(connection.execute(
                        sa.text("SELECT pg_try_advisory_lock(:namespace, :role)"), parameters,
                    ).scalar_one())
                    connection.commit()
                    if not acquired:
                        raise RuntimeError(
                            f"another CAOS {role} instance is already running against this database"
                        )
                    startup.set_result(None)
                    try:
                        while not stop.wait(_INSTANCE_LOCK_HEARTBEAT_SECONDS):
                            connection.execute(sa.text("SELECT 1")).scalar_one()
                            connection.commit()
                        connection.execute(
                            sa.text("SELECT pg_advisory_unlock(:namespace, :role)"), parameters,
                        )
                        connection.commit()
                    except Exception:
                        connection.invalidate()
                        raise
            except Exception as exc:
                if not startup.done():
                    startup.set_exception(exc)
                elif not stop.is_set():
                    _terminate_process(role)

        lock_thread = threading.Thread(
            target=own_lock,
            name=f"caos-{role}-instance-lock",
            daemon=True,
        )
        lock_thread.start()
        try:
            startup.result()
        except Exception:
            lock_thread.join()
            raise
        try:
            yield
        finally:
            stop.set()
            lock_thread.join()

    # -- audit ------------------------------------------------------------

    def _audit(self, conn: sa.Connection, action: str, actor: str, **details: Any) -> None:
        conn.execute(audit_events.insert().values(
            id=new_id("aud"), action=action, actor=actor, at=now_iso(), data=details,
        ))

    def audit_event(self, action: str, actor: str, **details: Any) -> None:
        with self.engine.begin() as conn:
            self._audit(conn, action, actor, **details)

    def audit_trail(self, limit: int = 500) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(audit_events).order_by(audit_events.c.seq.desc()).limit(limit)
            ).mappings().all()
        return [{"id": r["id"], "action": r["action"], "actor": r["actor"], "at": r["at"], **r["data"]} for r in rows]

    # -- cases ------------------------------------------------------------

    def create_case(self, name: str, issuer: str, sector: str, actor: str) -> dict[str, Any]:
        case_id = new_id("case")
        with self.engine.begin() as conn:
            conn.execute(cases.insert().values(
                id=case_id, name=name, issuer=issuer, sector=sector,
                created_by=actor, created_at=now_iso(),
            ))
            conn.execute(case_members.insert().values(case_id=case_id, subject=actor, role="ANALYST"))
            self._audit(conn, "case.created", actor, case_id=case_id)
        return self.get_case(case_id)  # type: ignore[return-value]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(cases).where(cases.c.id == case_id)).mappings().first()
            if row is None:
                return None
            members = conn.execute(
                sa.select(case_members).where(case_members.c.case_id == case_id)
            ).mappings().all()
        case = dict(row)
        case["members"] = {m["subject"]: m["role"] for m in members}
        return case

    def list_cases(self, actor: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            ids = conn.execute(
                sa.select(case_members.c.case_id).where(case_members.c.subject == actor)
            ).scalars().all()
        return [case for case_id in ids if (case := self.get_case(case_id))]

    def is_member(self, case_id: str, actor: str, roles: set[str] | None = None) -> bool:
        with self.engine.connect() as conn:
            role = conn.execute(
                sa.select(case_members.c.role).where(
                    case_members.c.case_id == case_id, case_members.c.subject == actor
                )
            ).scalar()
        return role is not None and (roles is None or role in roles)

    def add_member(self, case_id: str, actor: str, member: str, role: str, actor_role: str | None = None) -> bool:
        with self.engine.begin() as conn:
            case = conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id)).first()
            actor_case_role = conn.execute(
                sa.select(case_members.c.role).where(
                    case_members.c.case_id == case_id, case_members.c.subject == actor
                )
            ).scalar()
            if case is None or (actor_role != "ADMIN" and actor_case_role not in {"ADMIN", "APPROVER"}):
                return False
            existing = conn.execute(
                sa.select(case_members.c.subject).where(
                    case_members.c.case_id == case_id, case_members.c.subject == member
                )
            ).first()
            if existing:
                conn.execute(sa.update(case_members).where(
                    case_members.c.case_id == case_id, case_members.c.subject == member
                ).values(role=role))
            else:
                conn.execute(case_members.insert().values(case_id=case_id, subject=member, role=role))
            self._audit(conn, "case.member_added", actor, case_id=case_id, member=member, role=role)
        return True

    def update_case(self, case_id: str, **changes: Any) -> None:
        allowed = {"accepted_snapshot_id", "visible_snapshot_id", "current_execution_id"}
        bad = set(changes) - allowed
        if bad:
            raise ValueError(f"unsupported case update: {sorted(bad)}")
        guard = _AUTHORITY_MUTATION_LOCK if "accepted_snapshot_id" in changes else nullcontext()
        with guard, self.engine.begin() as conn:
            conn.execute(sa.update(cases).where(cases.c.id == case_id).values(**changes))

    # -- sources / source sets --------------------------------------------

    def _current_set_locked(self, conn: sa.Connection, case_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            sa.select(source_sets).where(source_sets.c.case_id == case_id)
            .order_by(source_sets.c.version.desc()).limit(1)
        ).mappings().first()
        return dict(row) if row else None

    def _active_ids(self, conn: sa.Connection, ids: list[str]) -> list[str]:
        if not ids:
            return []
        active = set(conn.execute(
            sa.select(sources.c.id).where(sources.c.id.in_(ids), sources.c.withdrawn.is_(False))
        ).scalars().all())
        return [source_id for source_id in ids if source_id in active]

    def _next_source_set(self, conn: sa.Connection, case_id: str, actor: str, add: list[str], remove: set[str]) -> dict[str, Any]:
        # Version allocation is read-max-then-insert against a UNIQUE
        # (case_id, version). Under READ COMMITTED two concurrent ingests both
        # read N and both insert N+1; the loser's IntegrityError surfaced from
        # `ingest` as "source content already active" — a wrong refusal for
        # content that is not a duplicate, and an upload the analyst is never
        # told to retry. Lock the CASE row, not the set row: `FOR UPDATE` on the
        # ORDER BY … LIMIT 1 set row would re-read the same unchanged row and
        # still compute N+1. No-op on SQLite, which serialises writers already.
        conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update())
        current = self._current_set_locked(conn, case_id)
        base = self._active_ids(conn, [s for s in (current["source_ids"] if current else []) if s not in remove])
        source_set = {
            "id": new_id("set"),
            "case_id": case_id,
            "version": (current["version"] + 1) if current else 1,
            "source_ids": [*base, *add],
            "created_by": actor,
            "created_at": now_iso(),
        }
        conn.execute(source_sets.insert().values(**source_set))
        return source_set

    def ingest(self, source: dict[str, Any], actor: str) -> dict[str, Any]:
        saved = dict(source)
        saved.setdefault("id", new_id("src"))
        saved.setdefault("created_by", actor)
        saved.setdefault("created_at", now_iso())
        saved.setdefault("withdrawn", False)
        try:
            with _AUTHORITY_MUTATION_LOCK, self.engine.begin() as conn:
                duplicate = conn.execute(
                    sa.select(sources.c.id).where(
                        sources.c.case_id == saved["case_id"],
                        sources.c.sha256 == saved["sha256"],
                        sources.c.withdrawn.is_(False),
                    )
                ).first()
                if duplicate:
                    raise ValueError("source content already active")
                conn.execute(sources.insert().values(**{k: saved.get(k) for k in (
                    "id", "case_id", "filename", "media_type", "bytes", "sha256",
                    "vault_path", "blocks", "created_by", "created_at", "withdrawn", "source_kind",
                )}))
                source_set = self._next_source_set(conn, saved["case_id"], actor, add=[saved["id"]], remove=set())
                self._audit(conn, "source.ingested", actor, case_id=saved["case_id"], source_id=saved["id"], sha256=saved.get("sha256"))
        except IntegrityError as exc:
            raise ValueError("source content already active") from exc
        return {**_public_source(saved), "source_set": source_set}

    # -- document-first intake (Task 8) ----------------------------------------

    def admit_intake(
        self,
        *,
        actor: str,
        case_id: str | None,
        new_case: dict[str, Any] | None,
        prepared: list[dict[str, Any]],
        intake_key: str,
        status: str,
        record: dict[str, Any],
        refusal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Admit a whole pack in ONE transaction: the case when it is new (with
        its creator's membership and `case.created`), every source row, one
        source-set version carrying all of them, one `source.ingested` audit row
        per source, the intake row, and `intake.admitted`. Nothing here can be
        half-done: a duplicate or a failing insert rolls the whole pack back."""
        intake_id = new_id("intk")
        now = now_iso()
        try:
            with _AUTHORITY_MUTATION_LOCK, self.engine.begin() as conn:
                if case_id is None:
                    if new_case is None:
                        raise ValueError("intake needs a case or a new case")
                    case_id = new_id("case")
                    conn.execute(cases.insert().values(
                        id=case_id, name=new_case["name"], issuer=new_case["issuer"],
                        sector=new_case["sector"], created_by=actor, created_at=now,
                    ))
                    conn.execute(case_members.insert().values(case_id=case_id, subject=actor, role="ANALYST"))
                    self._audit(conn, "case.created", actor, case_id=case_id)
                admitted_ids: list[str] = []
                for source in prepared:
                    saved = {
                        **source, "id": source.get("id") or new_id("src"), "case_id": case_id,
                        "created_by": actor, "created_at": now, "withdrawn": False,
                    }
                    source["id"] = saved["id"]
                    duplicate = conn.execute(
                        sa.select(sources.c.id).where(
                            sources.c.case_id == case_id,
                            sources.c.sha256 == saved["sha256"],
                            sources.c.withdrawn.is_(False),
                        )
                    ).first()
                    if duplicate:
                        raise ValueError("source content already active")
                    conn.execute(sources.insert().values(**{k: saved.get(k) for k in (
                        "id", "case_id", "filename", "media_type", "bytes", "sha256",
                        "vault_path", "blocks", "created_by", "created_at", "withdrawn", "source_kind",
                    )}))
                    admitted_ids.append(saved["id"])
                    self._audit(conn, "source.ingested", actor, case_id=case_id, source_id=saved["id"], sha256=saved["sha256"])
                if admitted_ids:
                    self._next_source_set(conn, case_id, actor, add=admitted_ids, remove=set())
                conn.execute(case_intakes.insert().values(
                    id=intake_id, case_id=case_id, intake_key=intake_key, status=status,
                    record=record, run_id=None, refusal=refusal, created_by=actor,
                    created_at=now, updated_at=now,
                ))
                self._audit(conn, "intake.admitted", actor, case_id=case_id, intake_id=intake_id,
                            source_count=len(admitted_ids))
        except IntegrityError as exc:
            raise ValueError("source content already active") from exc
        return self.get_intake(intake_id)  # type: ignore[return-value]

    def refuse_intake(self, actor: str, code: str, *, case_id: str | None) -> None:
        """A refused pack persists nothing but its audit row; the case, if any,
        is untouched."""
        with self.engine.begin() as conn:
            self._audit(conn, "intake.refused", actor, case_id=case_id, code=code)

    def update_intake(self, intake_id: str, **changes: Any) -> dict[str, Any] | None:
        allowed = {"status", "run_id", "refusal", "record"}
        bad = set(changes) - allowed
        if bad:
            raise ValueError(f"unsupported intake update: {sorted(bad)}")
        with self.engine.begin() as conn:
            conn.execute(sa.update(case_intakes).where(case_intakes.c.id == intake_id)
                         .values(**changes, updated_at=now_iso()))
        return self.get_intake(intake_id)

    def record_intake_run(self, intake_id: str, actor: str, *, run_id: str, pathway: str) -> dict[str, Any] | None:
        with self.engine.begin() as conn:
            case_id = conn.execute(sa.select(case_intakes.c.case_id).where(case_intakes.c.id == intake_id)).scalar()
            conn.execute(sa.update(case_intakes).where(case_intakes.c.id == intake_id)
                         .values(status="started", run_id=run_id, refusal=None, updated_at=now_iso()))
            self._audit(conn, "intake.run_started", actor, case_id=case_id, intake_id=intake_id,
                        run_id=run_id, pathway=pathway)
        return self.get_intake(intake_id)

    def get_intake(self, intake_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(case_intakes).where(case_intakes.c.id == intake_id)).mappings().first()
        return dict(row) if row else None

    def latest_intake(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(case_intakes).where(case_intakes.c.case_id == case_id)
                .order_by(case_intakes.c.created_at.desc(), case_intakes.c.id.desc()).limit(1)
            ).mappings().first()
        return dict(row) if row else None

    def intakes_for_case(self, case_id: str) -> list[dict[str, Any]]:
        """Every intake admitted into a case, oldest first: together their
        manifests carry the host disposition of each source the case pinned,
        which the model's lineage record reads (a later intake's row for the
        same source supersedes an earlier one)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(case_intakes).where(case_intakes.c.case_id == case_id)
                .order_by(case_intakes.c.created_at.asc(), case_intakes.c.id.asc())
            ).mappings().all()
        return [dict(row) for row in rows]

    def find_intake_by_key(self, actor: str, intake_key: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(case_intakes).where(
                    case_intakes.c.intake_key == intake_key, case_intakes.c.created_by == actor,
                ).order_by(case_intakes.c.created_at.desc()).limit(1)
            ).mappings().first()
        return dict(row) if row else None

    def withdraw(self, case_id: str, source_id: str, actor: str) -> dict[str, Any] | None:
        with _AUTHORITY_MUTATION_LOCK, self.engine.begin() as conn:
            row = conn.execute(sa.select(sources).where(sources.c.id == source_id)).mappings().first()
            if row is None or row["case_id"] != case_id or row["withdrawn"]:
                return None
            withdrawn_at = now_iso()
            conn.execute(sa.update(sources).where(sources.c.id == source_id).values(withdrawn=True, withdrawn_at=withdrawn_at))
            if self._current_set_locked(conn, case_id):
                self._next_source_set(conn, case_id, actor, add=[], remove={source_id})
            citing = conn.execute(sa.select(assumptions).where(assumptions.c.case_id == case_id)).mappings().all()
            for assumption in citing:
                if source_id in (assumption["evidence_ids"] or []):
                    conn.execute(sa.update(assumptions).where(assumptions.c.id == assumption["id"]).values(stale=True, status="STALE"))
            # Derived artifacts cannot outlive their evidence: withdrawal
            # deactivates every ACTIVE loan universe pinned to this source.
            conn.execute(
                sa.update(loan_universes)
                .where(loan_universes.c.case_id == case_id, loan_universes.c.source_id == source_id,
                       loan_universes.c.status == "ACTIVE")
                .values(status="WITHDRAWN", withdrawn_at=withdrawn_at)
            )
            self._audit(conn, "source.withdrawn", actor, case_id=case_id, source_id=source_id)
            result = dict(row)
            result.update(withdrawn=True)
            return _public_source(result)

    def list_source_filenames(self, case_id: str) -> list[str]:
        """Filenames of the live sources, and nothing else.

        `list_sources` selects the whole row, and the row carries the `blocks`
        JSON column — every evidence block of every source. A caller that only
        needs suffixes (pathway_fit, on the case-list route) would otherwise
        parse megabytes of block text per case to produce one word."""
        with self.engine.connect() as conn:
            return list(conn.execute(sa.select(sources.c.filename).where(
                sources.c.case_id == case_id, sources.c.withdrawn.is_(False)
            ).order_by(sources.c.created_at)).scalars())

    def list_sources(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(sources).where(
                sources.c.case_id == case_id, sources.c.withdrawn.is_(False)
            ).order_by(sources.c.created_at)).mappings().all()
        return [_public_source(dict(row)) for row in rows]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(sources).where(sources.c.id == source_id)).mappings().first()
        return _public_source(dict(row)) if row else None

    def get_source_private(self, source_id: str) -> dict[str, Any] | None:
        """Full row including vault_path — host-side use only, never serialized out."""
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(sources).where(sources.c.id == source_id)).mappings().first()
        return dict(row) if row else None

    def read_source_bytes(self, source_id: str, limit: int) -> bytes:
        row = self.get_source_private(source_id)
        vault_path = row.get("vault_path") if row else None
        path = Path(vault_path) if isinstance(vault_path, str) else None
        sha256 = row.get("sha256") if row else None
        expected_parts = ("sources", sha256[:2], sha256) if isinstance(sha256, str) else ()
        if (
            path is None
            or tuple(path.parts[-3:]) != expected_parts
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit <= 0
        ):
            raise FileNotFoundError("SOURCE_BYTES_UNAVAILABLE")
        try:
            content = read_verified_vault_bytes(
                path.parents[2],
                "/".join(expected_parts),
                expected_sha256=sha256,
                expected_size=row.get("bytes"),
                max_bytes=MAX_EXPORT_BYTES,
            )
        except VaultFileUnavailable as exc:
            raise FileNotFoundError("SOURCE_BYTES_UNAVAILABLE") from exc
        except VaultFileIntegrityError as exc:
            raise ValueError("SOURCE_BYTES_INTEGRITY_MISMATCH") from exc
        return content[:limit]

    def current_source_set(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            return self._current_set_locked(conn, case_id)

    def source_set(self, source_set_id: str | None) -> dict[str, Any] | None:
        if not source_set_id:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(source_sets).where(source_sets.c.id == source_set_id)).mappings().first()
        return dict(row) if row else None

    def sources_for_live_set(
        self,
        case_id: str,
        source_set_id: str | None,
        version: int | None = None,
    ) -> list[dict[str, Any]] | None:
        """Resolve every member from live source rows, or fail the whole set."""
        if not source_set_id:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(source_sets).where(source_sets.c.id == source_set_id)
            ).mappings().first()
            if (
                row is None
                or row["case_id"] != case_id
                or (version is not None and row["version"] != version)
                or not row["source_ids"]
            ):
                return None
            source_rows = conn.execute(
                sa.select(sources).where(sources.c.id.in_(row["source_ids"]))
            ).mappings().all()
        by_id = {source["id"]: dict(source) for source in source_rows}
        if len(by_id) != len(row["source_ids"]) or any(
            source_id not in by_id
            or by_id[source_id]["case_id"] != case_id
            or by_id[source_id]["withdrawn"]
            for source_id in row["source_ids"]
        ):
            return None
        return [_public_source(by_id[source_id]) for source_id in row["source_ids"]]

    # -- notes -------------------------------------------------------------

    def create_note(self, case_id: str, body: str, actor: str) -> dict[str, Any]:
        note = {
            "id": new_id("note"), "case_id": case_id, "body": body,
            "created_by": actor, "created_at": now_iso(),
            "promoted": False, "promoted_source_id": None,
        }
        with self.engine.begin() as conn:
            conn.execute(notes.insert().values(**note))
            self._audit(conn, "note.created", actor, case_id=case_id, note_id=note["id"])
        return note

    def list_notes(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(notes).where(notes.c.case_id == case_id).order_by(notes.c.created_at)).mappings().all()
        return [dict(row) for row in rows]

    def promote_note(self, case_id: str, note_id: str, actor: str) -> dict[str, Any]:
        import hashlib

        with _AUTHORITY_MUTATION_LOCK, self.engine.begin() as conn:
            note_row = conn.execute(sa.select(notes).where(notes.c.id == note_id)).mappings().first()
            if note_row is None or note_row["case_id"] != case_id:
                raise KeyError("note not found")
            note = dict(note_row)
            if note["promoted"] and note["promoted_source_id"]:
                promoted = conn.execute(
                    sa.select(sources).where(sources.c.id == note["promoted_source_id"])
                ).mappings().first()
                if promoted is not None and not promoted["withdrawn"]:
                    return note  # idempotent replay while the promoted source stays active
            body: str = note["body"]
            body_bytes = body.encode()
            sha256 = hashlib.sha256(body_bytes).hexdigest()
            duplicate = conn.execute(
                sa.select(sources.c.id).where(
                    sources.c.case_id == case_id,
                    sources.c.sha256 == sha256,
                    sources.c.withdrawn.is_(False),
                )
            ).first()
            if duplicate:
                raise ValueError("source content already active")
            source_id = new_id("src-note")
            conn.execute(sources.insert().values(
                id=source_id, case_id=case_id,
                filename=f"analyst-note-{note['id']}.md", media_type="text/markdown",
                bytes=len(body_bytes), sha256=sha256, vault_path=None,
                blocks=[{
                    "block_id": "b00001", "locator": {"note_id": note["id"]}, "text": body,
                    "extractor_version": "analyst-note-v1", "confidence": "HIGH", "untrusted_data": True,
                }],
                created_by=actor, created_at=now_iso(), withdrawn=False, source_kind="analyst_note",
            ))
            self._next_source_set(conn, case_id, actor, add=[source_id], remove=set())
            conn.execute(sa.update(notes).where(notes.c.id == note_id).values(promoted=True, promoted_source_id=source_id))
            self._audit(conn, "note.promoted", actor, case_id=case_id, note_id=note_id, source_id=source_id)
            note.update(promoted=True, promoted_source_id=source_id)
            return note

    # -- loan universes (CP-3 RV) ------------------------------------------

    _LOAN_PUBLIC_KEYS = (
        "id", "case_id", "source_id", "source_filename", "source_sha256", "workbook_date",
        "template_version", "importer_version", "universe_digest", "row_count", "status",
        "findings", "created_at", "created_by", "version", "activated_at", "superseded_at", "withdrawn_at",
    )

    def _public_loan_universe(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: row.get(key) for key in self._LOAN_PUBLIC_KEYS}

    def save_loan_universe(self, record: dict[str, Any], actor: str) -> dict[str, Any]:
        """One transaction: supersede the prior ACTIVE, insert the candidate,
        audit the versioning. The source's active flag is re-checked inside the
        transaction so a racing withdrawal can never leave an active universe."""
        now = now_iso()
        row = {
            "id": new_id("rvloan"),
            **record,
            "created_at": now,
            "activated_at": now if record["status"] == "ACTIVE" else None,
            "superseded_at": None,
            "withdrawn_at": None,
            "version": None,
        }
        with self.engine.begin() as conn:
            if self._before_universe_write is not None:
                interpose, self._before_universe_write = self._before_universe_write, None
                interpose()
            # Row-locked re-check: on Postgres a racing withdrawal must not
            # slip between this read and the insert (no-op on SQLite, whose
            # writer serialization already guarantees it).
            active_source = conn.execute(
                sa.select(sources.c.withdrawn).where(sources.c.id == record["source_id"]).with_for_update()
            ).scalar()
            if record["status"] == "ACTIVE" and active_source is not False:
                raise ValueError("RV_SOURCE_NOT_ACTIVE: source was withdrawn during import")
            if record["status"] == "ACTIVE":
                version = (conn.execute(
                    sa.select(sa.func.coalesce(sa.func.max(loan_universes.c.version), 0))
                    .where(loan_universes.c.case_id == record["case_id"])
                ).scalar_one()) + 1
                row["version"] = version
                conn.execute(
                    sa.update(loan_universes)
                    .where(loan_universes.c.case_id == record["case_id"], loan_universes.c.status == "ACTIVE")
                    .values(status="SUPERSEDED", superseded_at=now)
                )
            conn.execute(loan_universes.insert().values(**row))
            if record["status"] == "ACTIVE":
                self._audit(conn, "rv.universe_versioned", actor, case_id=record["case_id"], version=row["version"])
        return self._public_loan_universe(row)

    _before_universe_write: Any = None

    def interpose_before_universe_write_for_tests(self, callback: Any) -> None:
        self._before_universe_write = callback

    def find_loan_universe(self, case_id: str, source_sha256: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(loan_universes)
                .where(loan_universes.c.case_id == case_id, loan_universes.c.source_sha256 == source_sha256,
                       loan_universes.c.status.in_(("ACTIVE", "REJECTED")))
                .order_by(loan_universes.c.seq.desc()).limit(1)
            ).mappings().first()
        return self._public_loan_universe(dict(row)) if row else None

    def list_loan_universes(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(loan_universes).where(loan_universes.c.case_id == case_id).order_by(loan_universes.c.seq)
            ).mappings().all()
        return [self._public_loan_universe(dict(row)) for row in rows]

    def active_loan_universe(self, case_id: str) -> dict[str, Any] | None:
        """The full active record including its pinned normalized rows."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(loan_universes)
                .where(loan_universes.c.case_id == case_id, loan_universes.c.status == "ACTIVE")
                .order_by(loan_universes.c.seq.desc()).limit(1)
            ).mappings().first()
        if row is None:
            return None
        return {**self._public_loan_universe(dict(row)), "rows": row["rows"]}

    def loan_universe(self, universe_id: str) -> dict[str, Any] | None:
        """One record by id, rows included, whatever its status.

        A run pins a universe at gate exit; a later import supersedes it
        case-wide but must not change what that run binds, so the pinned lookup
        is by id and deliberately status-blind. Withdrawal is not: it withdraws
        the underlying source, which the pinned-source check refuses first."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(loan_universes).where(loan_universes.c.id == universe_id)
            ).mappings().first()
        if row is None:
            return None
        return {**self._public_loan_universe(dict(row)), "rows": row["rows"]}

    def replace_vault_bytes_for_tests(self, source_id: str, content: bytes) -> None:
        row = self.get_source_private(source_id)
        Path(row["vault_path"]).write_bytes(content)

    # -- rv quick universes -------------------------------------------------

    def save_rv_universe(self, case_id: str, rows: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        with self.engine.begin() as conn:
            version = (conn.execute(
                sa.select(sa.func.coalesce(sa.func.max(rv_universes.c.version), 0))
                .where(rv_universes.c.case_id == case_id)
            ).scalar_one()) + 1
            record = {"id": new_id("rvu"), "case_id": case_id, "version": version, "rows": rows,
                      "created_by": actor, "created_at": now_iso()}
            conn.execute(rv_universes.insert().values(**record))
            self._audit(conn, "rv.universe_versioned", actor, case_id=case_id, version=version)
        return record

    def get_rv_universe(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(rv_universes).where(rv_universes.c.case_id == case_id)
                .order_by(rv_universes.c.version.desc()).limit(1)
            ).mappings().first()
        return dict(row) if row else None

    # -- model build seams (http-contract surface) --------------------------

    def queue_model_build(self, spec: dict[str, Any], actor: str) -> tuple[dict[str, Any], bool]:
        from .models import ModelStore

        record, created = ModelStore(self.engine).queue_build({
            "case_id": spec["case_id"],
            "accepted_run_id": spec.get("accepted_run_id"),
            "snapshot_id": spec.get("accepted_snapshot_id"),
            "source_set_id": spec.get("source_set_id"),
            "input_fingerprint": spec["input_fingerprint"],
            "calculation_runtime": spec.get("calculation_runtime"),
            "worksheet_schema_version": spec.get("worksheet_schema_version"),
        }, actor)
        return record, created

    def fail_model_build_for_tests(self, build_id: str, error: dict[str, Any]) -> None:
        from .models import ModelStore

        ModelStore(self.engine).update_build(build_id, status="FAILED", error=error)

    def complete_model_build_for_tests(self, build_id: str, result: dict[str, Any]) -> None:
        from .models import ModelStore

        ModelStore(self.engine).update_build(
            build_id, status="READY", payload=result["payload"],
            payload_digest=result["payload_digest"], qa=result["qa"], completed_at=now_iso(),
        )

    def list_audit(self, limit: int = 500) -> list[dict[str, Any]]:
        return self.audit_trail(limit)

    # -- model revision ledger seams (spec: append-only is store-enforced) --

    def model_revision_order_for_tests(self, case_id: str) -> list[int]:
        from .models import ModelStore

        return ModelStore(self.engine).revision_order(case_id)

    def mutate_model_revision_for_tests(self, revision_id: str, changes: dict[str, Any]) -> None:
        """Enforcement witness: attempt a REAL update — the store's append-only
        trigger aborts it. This must never succeed."""
        from sqlalchemy.exc import DBAPIError

        from .models import ModelStore

        try:
            ModelStore(self.engine).mutate_revision(revision_id, changes)
        except DBAPIError as exc:
            raise ValueError(f"APPEND_ONLY: model revision {revision_id} is immutable") from exc
        raise AssertionError("append-only trigger failed to refuse a revision mutation")

    # -- assumptions (write surface lands in phase 5; staleness is live now) --

    def save_assumption(self, case_id: str, data: dict[str, Any], evidence_ids: list[str], actor: str) -> dict[str, Any]:
        with self.engine.begin() as conn:
            active = set(conn.execute(
                sa.select(sources.c.id).where(
                    sources.c.id.in_(evidence_ids or []), sources.c.withdrawn.is_(False),
                    sources.c.case_id == case_id,
                )
            ).scalars().all()) if evidence_ids else set()
            missing = [evidence_id for evidence_id in (evidence_ids or []) if evidence_id not in active]
            if missing:
                raise ValueError("EVIDENCE_SOURCE_WITHDRAWN")
            record = {
                "id": new_id("asm"), "case_id": case_id, "data": data,
                "evidence_ids": evidence_ids, "status": "READY", "stale": False,
            }
            conn.execute(assumptions.insert().values(**record))
            self._audit(conn, "assumption.saved", actor, case_id=case_id, assumption_id=record["id"])
        return record

    def list_assumptions(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(assumptions).where(assumptions.c.case_id == case_id)).mappings().all()
        return [dict(row) for row in rows]
