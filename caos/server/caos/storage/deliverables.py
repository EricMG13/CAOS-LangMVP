"""Deliverables store: append-only draft revisions, content-addressed frozen
records, filing-gate thread rows, seeded upstream/model authority.

Fresh code — nothing from LEGACY publishing/domain.py machinery. Contracts
kept: revisions append with a CAS on (case, pathway, version); the frozen
record's status transitions are conditional updates and its audit event rides
the same transaction; threads are terminalized with typed outcomes (§10.5).
"""

from __future__ import annotations

import threading
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from .store import new_id, now_iso

deliverable_metadata = sa.MetaData()

deliverable_revisions = sa.Table(
    "deliverable_revisions", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("revision_id", sa.String, nullable=False, unique=True),
    sa.Column("draft_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("digest", sa.String, nullable=False),
    sa.Column("content", sa.JSON, nullable=False),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.UniqueConstraint("case_id", "pathway", "version", name="uq_deliverable_revision_version"),
)

deliverable_frozen = sa.Table(
    "deliverable_frozen", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("deliverable_id", sa.String, nullable=False, unique=True),
    sa.Column("thread_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("preview_digest", sa.String, nullable=False),
    sa.Column("input_fingerprint", sa.String, nullable=False),
    sa.Column("build_id", sa.String, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("exports", sa.JSON, nullable=False),
    sa.Column("authority", sa.JSON, nullable=False),
    sa.Column("draft_version", sa.Integer, nullable=False),
    sa.Column("draft_digest", sa.String, nullable=False),
    sa.Column("superseded_by_id", sa.String),
    sa.Column("filed_by", sa.String),
    sa.Column("filed_at", sa.String),
    sa.Column("change_request", sa.JSON),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
)

deliverable_threads = sa.Table(
    "deliverable_threads", deliverable_metadata,
    sa.Column("thread_id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("deliverable_id", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("outcome", sa.String),
    sa.Column("interrupt_id", sa.String, nullable=False),
)

deliverable_authorities = sa.Table(
    "deliverable_authorities", deliverable_metadata,
    sa.Column("case_id", sa.String, primary_key=True),
    sa.Column("snapshot_id", sa.String, nullable=False),
    sa.Column("build_id", sa.String, nullable=False),
)

deliverable_models = sa.Table(
    "deliverable_models", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("kind", sa.String, nullable=False),
    sa.Column("build_id", sa.String, nullable=False, unique=True),
    sa.Column("revision_id", sa.String, unique=True),
    sa.Column("outputs", sa.JSON, nullable=False),
    sa.Column("assumptions", sa.JSON, nullable=False),
    sa.Column("build_payload", sa.JSON, nullable=False),
    sa.Column("build_qa", sa.JSON, nullable=False),
    sa.Column("calculation_runtime", sa.JSON, nullable=False),
)


class DeliverableStore:
    _WRITE_LOCK = threading.Lock()

    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine
        deliverable_metadata.create_all(engine)

    # -- revisions ----------------------------------------------------------

    @staticmethod
    def _revision(row: dict[str, Any]) -> dict[str, Any]:
        return {key: row[key] for key in ("draft_id", "revision_id", "case_id", "pathway", "version",
                                          "digest", "content", "created_by", "created_at")}

    def append_revision(self, case_id: str, pathway: str, expected_version: int,
                        content: dict[str, Any], content_digest: str, actor: str, audit: Any) -> dict[str, Any]:
        with self._WRITE_LOCK, self.engine.begin() as conn:
            head = conn.execute(
                sa.select(deliverable_revisions)
                .where(deliverable_revisions.c.case_id == case_id, deliverable_revisions.c.pathway == pathway)
                .order_by(deliverable_revisions.c.version.desc()).limit(1)
            ).mappings().first()
            current_version = head["version"] if head else 0
            if expected_version != current_version:
                raise DeliverableVersionConflict(self._revision(dict(head)) if head else None)
            row = {
                "revision_id": new_id("dlrev"),
                "draft_id": head["draft_id"] if head else new_id("dldraft"),
                "case_id": case_id,
                "pathway": pathway,
                "version": current_version + 1,
                "digest": content_digest,
                "content": content,
                "created_by": actor,
                "created_at": now_iso(),
            }
            try:
                conn.execute(deliverable_revisions.insert().values(**row))
            except IntegrityError as exc:  # pragma: no cover — lock serialises
                raise DeliverableVersionConflict(self._revision(dict(head)) if head else None) from exc
            audit(conn, "deliverable.draft.saved", actor, case_id=case_id,
                  pathway=pathway, revision_id=row["revision_id"], version=row["version"])
            return self._revision(row)

    def head_revision(self, case_id: str, pathway: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_revisions)
                .where(deliverable_revisions.c.case_id == case_id, deliverable_revisions.c.pathway == pathway)
                .order_by(deliverable_revisions.c.version.desc()).limit(1)
            ).mappings().first()
        return self._revision(dict(row)) if row else None

    def revision_history(self, case_id: str, pathway: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(deliverable_revisions)
                .where(deliverable_revisions.c.case_id == case_id, deliverable_revisions.c.pathway == pathway)
                .order_by(deliverable_revisions.c.version)
            ).mappings().all()
        return [self._revision(dict(row)) for row in rows]

    def revision_by_id(self, case_id: str, revision_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_revisions).where(deliverable_revisions.c.revision_id == revision_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return self._revision(dict(row))

    # -- frozen records and threads -----------------------------------------

    _FROZEN_KEYS = (
        "deliverable_id", "thread_id", "case_id", "pathway", "status", "preview_digest",
        "input_fingerprint", "build_id", "payload", "exports", "authority",
        "draft_version", "draft_digest", "superseded_by_id", "filed_by", "filed_at",
        "change_request", "created_by", "created_at",
    )

    def _frozen(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: row.get(key) for key in self._FROZEN_KEYS}

    def insert_frozen(self, record: dict[str, Any], actor: str, audit: Any) -> tuple[dict[str, Any], bool]:
        with self._WRITE_LOCK, self.engine.begin() as conn:
            existing = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == record["deliverable_id"])
            ).mappings().first()
            if existing is not None:
                return self._frozen(dict(existing)), False
            row = {**record, "superseded_by_id": None, "filed_by": None, "filed_at": None,
                   "change_request": None, "created_at": now_iso()}
            conn.execute(deliverable_frozen.insert().values(**row))
            conn.execute(deliverable_threads.insert().values(
                thread_id=record["thread_id"], case_id=record["case_id"],
                deliverable_id=record["deliverable_id"], status="PARKED", outcome=None,
                interrupt_id=new_id("int"),
            ))
            audit(conn, "deliverable.frozen", actor, case_id=record["case_id"],
                  deliverable_id=record["deliverable_id"], preview_digest=record["preview_digest"])
            return self._frozen(row), True

    def frozen_record(self, case_id: str, deliverable_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return self._frozen(dict(row))

    def frozen_for_pathway(self, case_id: str, pathway: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(deliverable_frozen)
                .where(deliverable_frozen.c.case_id == case_id, deliverable_frozen.c.pathway == pathway)
                .order_by(deliverable_frozen.c.seq)
            ).mappings().all()
        return [self._frozen(dict(row)) for row in rows]

    def thread_state(self, thread_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_threads).where(deliverable_threads.c.thread_id == thread_id)
            ).mappings().first()
        return dict(row) if row else None

    def terminate_thread(self, thread_id: str, outcome: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(sa.update(deliverable_threads).where(deliverable_threads.c.thread_id == thread_id)
                         .values(status="TERMINATED", outcome=outcome))

    def file_record(self, deliverable_id: str, actor: str, audit: Any) -> dict[str, Any] | None:
        """The one-shot filing CAS (§12.21): FROZEN -> FILED wins exactly once;
        the same transaction supersedes every sibling record of the pathway and
        terminalizes their parked threads with the typed outcome (§10.5)."""
        with self._WRITE_LOCK, self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(deliverable_frozen)
                .where(deliverable_frozen.c.deliverable_id == deliverable_id,
                       deliverable_frozen.c.status == "FROZEN")
                .values(status="FILED", filed_by=actor, filed_at=now_iso())
            ).rowcount
            if not changed:
                return None
            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
            conn.execute(sa.update(deliverable_threads).where(deliverable_threads.c.thread_id == row["thread_id"])
                         .values(status="FILED", outcome="FILED"))
            siblings = conn.execute(
                sa.select(deliverable_frozen)
                .where(deliverable_frozen.c.case_id == row["case_id"],
                       deliverable_frozen.c.pathway == row["pathway"],
                       deliverable_frozen.c.deliverable_id != deliverable_id,
                       deliverable_frozen.c.status.in_(("FROZEN", "FILED", "CHANGES_REQUESTED")))
            ).mappings().all()
            for sibling in siblings:
                conn.execute(sa.update(deliverable_frozen)
                             .where(deliverable_frozen.c.deliverable_id == sibling["deliverable_id"])
                             .values(status="SUPERSEDED", superseded_by_id=deliverable_id))
                conn.execute(sa.update(deliverable_threads)
                             .where(deliverable_threads.c.thread_id == sibling["thread_id"])
                             .values(status="TERMINATED", outcome="SUPERSEDED"))
            audit(conn, "deliverable.filed", actor, case_id=row["case_id"], deliverable_id=deliverable_id)
            return self._frozen(dict(row))

    def mark_changes_requested(self, deliverable_id: str, actor: str, comment: str, audit: Any) -> dict[str, Any] | None:
        with self._WRITE_LOCK, self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(deliverable_frozen)
                .where(deliverable_frozen.c.deliverable_id == deliverable_id,
                       deliverable_frozen.c.status == "FROZEN")
                .values(status="CHANGES_REQUESTED", change_request={
                    "comment": comment, "requested_by": actor, "requested_at": now_iso(),
                })
            ).rowcount
            if not changed:
                return None
            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
            conn.execute(sa.update(deliverable_threads).where(deliverable_threads.c.thread_id == row["thread_id"])
                         .values(status="TERMINATED", outcome="CHANGES_REQUESTED"))
            audit(conn, "deliverable.changes_requested", actor, case_id=row["case_id"],
                  deliverable_id=deliverable_id, comment=comment[:300])
            return self._frozen(dict(row))

    def tamper_frozen_payload(self, deliverable_id: str) -> None:
        with self.engine.begin() as conn:
            row = conn.execute(
                sa.select(deliverable_frozen.c.payload).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
            payload = dict(row["payload"])
            payload["tampered_after_freeze"] = True
            conn.execute(sa.update(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
                         .values(payload=payload))

    # -- seeded authority ----------------------------------------------------

    def set_authority(self, case_id: str, snapshot_id: str, build_id: str) -> dict[str, Any]:
        with self.engine.begin() as conn:
            conn.execute(sa.delete(deliverable_authorities).where(deliverable_authorities.c.case_id == case_id))
            conn.execute(deliverable_authorities.insert().values(
                case_id=case_id, snapshot_id=snapshot_id, build_id=build_id,
            ))
        return {"case_id": case_id, "snapshot_id": snapshot_id, "build_id": build_id}

    def authority(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_authorities).where(deliverable_authorities.c.case_id == case_id)
            ).mappings().first()
        return dict(row) if row else None

    # -- seeded model authority ----------------------------------------------

    def insert_model(self, record: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as conn:
            conn.execute(deliverable_models.insert().values(**record))
        return record

    def model_by_revision(self, case_id: str, revision_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_models).where(deliverable_models.c.revision_id == revision_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return dict(row)

    def model_by_build(self, case_id: str, build_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_models).where(deliverable_models.c.build_id == build_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return dict(row)

    def head_model_revision(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_models)
                .where(deliverable_models.c.case_id == case_id, deliverable_models.c.revision_id.isnot(None))
                .order_by(deliverable_models.c.seq.desc()).limit(1)
            ).mappings().first()
        return dict(row) if row else None


class DeliverableVersionConflict(ValueError):
    """DELIVERABLE_VERSION_CONFLICT — carries the current head for rebase."""

    def __init__(self, current: dict[str, Any] | None) -> None:
        self.current = current
        super().__init__("DELIVERABLE_VERSION_CONFLICT")
