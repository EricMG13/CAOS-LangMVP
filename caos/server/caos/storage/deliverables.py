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

from ..contracts import digest
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
    # Task 10: the opinion this freeze binds and who signed it, so the filing
    # CAS can refuse the signer and the receipt can name them (nullable only
    # for records frozen before the columns existed).
    sa.Column("opinion_id", sa.String),
    sa.Column("signed_by", sa.String),
)

# Append-only analyst opinion sign-offs (Task 10, DECISIONS §14.19). One row
# per signing; the head for (case, pathway) is the highest seq. Never updated,
# never deleted — the triggers below make that a database fact.
deliverable_opinions = sa.Table(
    "deliverable_opinions", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("opinion_id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("draft_id", sa.String, nullable=False),
    sa.Column("revision_id", sa.String, nullable=False),
    sa.Column("draft_version", sa.Integer, nullable=False),
    sa.Column("draft_digest", sa.String, nullable=False),
    sa.Column("binding", sa.JSON, nullable=False),
    sa.Column("opinion", sa.Text, nullable=False),
    sa.Column("limitations", sa.Text, nullable=False),
    sa.Column("material_overrides", sa.Text, nullable=False),
    sa.Column("rationale", sa.Text, nullable=False),
    sa.Column("supersedes_opinion_id", sa.String),
    sa.Column("signed_by", sa.String, nullable=False),
    sa.Column("signed_at", sa.String, nullable=False),
    sa.Column("opinion_digest", sa.String, nullable=False),
)

# Freeze requests wait here for the worker. The row is keyed by the freeze
# thread identity so racing and retried requests converge on one job; the
# frozen record is inserted by the worker only after every export has been
# published hash-addressed and read back verified.
deliverable_freeze_jobs = sa.Table(
    "deliverable_freeze_jobs", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("job_id", sa.String, nullable=False, unique=True),
    sa.Column("thread_id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("frozen_record", sa.JSON, nullable=False),
    sa.Column("deliverable_id", sa.String),
    sa.Column("error", sa.JSON),
    sa.Column("requested_by", sa.String, nullable=False),
    sa.Column("requested_at", sa.String, nullable=False),
    sa.Column("claimed_at", sa.String),
    sa.Column("completed_at", sa.String),
)

# Detached, immutable filing receipts: the approver's identity and time live
# here and in the audit log, never in the approved bytes.
deliverable_filing_receipts = sa.Table(
    "deliverable_filing_receipts", deliverable_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("receipt_id", sa.String, nullable=False, unique=True),
    sa.Column("deliverable_id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("receipt", sa.JSON, nullable=False),
    sa.Column("receipt_digest", sa.String, nullable=False),
)

_APPEND_ONLY_TABLES = ("deliverable_opinions", "deliverable_filing_receipts")


def _sqlite_append_only_ddl(table: str) -> tuple[str, str]:
    return (
        f"CREATE TRIGGER {table}_append_only BEFORE UPDATE ON {table} BEGIN "
        f"SELECT RAISE(ABORT, 'APPEND_ONLY: {table} rows are immutable'); END",
        f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} BEGIN "
        f"SELECT RAISE(ABORT, 'APPEND_ONLY: {table} rows cannot be deleted'); END",
    )


POSTGRES_APPEND_ONLY_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION caos_deliverable_row_immutable() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'APPEND_ONLY: % rows cannot be deleted', TG_TABLE_NAME;
    END IF;
    RAISE EXCEPTION 'APPEND_ONLY: % rows are immutable', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql
""".strip()

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
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Add the Task 10 frozen-record columns to a pre-existing table and arm
        the append-only triggers on opinions and receipts. Idempotent."""
        dialect = self.engine.dialect.name
        if dialect == "postgresql":
            with self.engine.begin() as conn:
                for column in ("opinion_id", "signed_by"):
                    conn.exec_driver_sql(f"ALTER TABLE deliverable_frozen ADD COLUMN IF NOT EXISTS {column} VARCHAR")
                conn.exec_driver_sql(POSTGRES_APPEND_ONLY_FUNCTION_DDL)
                for table in _APPEND_ONLY_TABLES:
                    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
                    conn.exec_driver_sql(
                        f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
                        "FOR EACH ROW EXECUTE FUNCTION caos_deliverable_row_immutable()"
                    )
            return
        if dialect != "sqlite":
            raise RuntimeError(f"unsupported deliverable-store dialect: {dialect}")
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                columns = {row[1] for row in conn.exec_driver_sql('PRAGMA table_info("deliverable_frozen")')}
                for column in ("opinion_id", "signed_by"):
                    if column not in columns:
                        conn.exec_driver_sql(f"ALTER TABLE deliverable_frozen ADD COLUMN {column} VARCHAR")
                for table in _APPEND_ONLY_TABLES:
                    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_append_only")
                    conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {table}_no_delete")
                    for statement in _sqlite_append_only_ddl(table):
                        conn.exec_driver_sql(statement)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    # -- opinions (append-only, expected-head CAS) ---------------------------

    _OPINION_KEYS = (
        "opinion_id", "case_id", "pathway", "draft_id", "revision_id", "draft_version", "draft_digest",
        "binding", "opinion", "limitations", "material_overrides", "rationale", "supersedes_opinion_id",
        "signed_by", "signed_at", "opinion_digest",
    )

    def _opinion(self, row: dict[str, Any]) -> dict[str, Any]:
        record = {key: row.get(key) for key in self._OPINION_KEYS}
        preimage = {key: value for key, value in record.items() if key != "opinion_digest"}
        if record["opinion_digest"] != digest(preimage):
            raise ValueError("OPINION_INTEGRITY_FAILED: stored opinion does not match its digest")
        return record

    def head_opinion(self, case_id: str, pathway: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_opinions)
                .where(deliverable_opinions.c.case_id == case_id, deliverable_opinions.c.pathway == pathway)
                .order_by(deliverable_opinions.c.seq.desc()).limit(1)
            ).mappings().first()
        return self._opinion(dict(row)) if row else None

    def opinion_by_id(self, case_id: str, opinion_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_opinions).where(deliverable_opinions.c.opinion_id == opinion_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return self._opinion(dict(row))

    def opinion_history(self, case_id: str, pathway: str | None = None) -> list[dict[str, Any]]:
        query = sa.select(deliverable_opinions).where(deliverable_opinions.c.case_id == case_id)
        if pathway is not None:
            query = query.where(deliverable_opinions.c.pathway == pathway)
        with self.engine.connect() as conn:
            rows = conn.execute(query.order_by(deliverable_opinions.c.seq)).mappings().all()
        return [self._opinion(dict(row)) for row in rows]

    def sign_opinion(self, record: dict[str, Any], expected_head_opinion_id: str | None,
                     actor: str, audit: Any) -> dict[str, Any]:
        """Expected-head CAS: the caller names the opinion it believes is current
        (or None); anything else is OpinionHeadConflict carrying the real head."""
        with self._WRITE_LOCK, self.engine.begin() as conn:
            head_row = conn.execute(
                sa.select(deliverable_opinions)
                .where(deliverable_opinions.c.case_id == record["case_id"],
                       deliverable_opinions.c.pathway == record["pathway"])
                .order_by(deliverable_opinions.c.seq.desc()).limit(1)
            ).mappings().first()
            head = self._opinion(dict(head_row)) if head_row else None
            if (head["opinion_id"] if head else None) != expected_head_opinion_id:
                raise OpinionHeadConflict(head)
            row = {
                **record,
                "opinion_id": new_id("opn"),
                "supersedes_opinion_id": head["opinion_id"] if head else None,
                "signed_by": actor,
                "signed_at": now_iso(),
            }
            row["opinion_digest"] = digest({key: row[key] for key in self._OPINION_KEYS if key != "opinion_digest"})
            conn.execute(deliverable_opinions.insert().values(**row))
            audit(conn, "deliverable.opinion.signed", actor, case_id=record["case_id"],
                  pathway=record["pathway"], opinion_id=row["opinion_id"], revision_id=record["revision_id"],
                  version=record["draft_version"], sha256=row["opinion_digest"])
            return self._opinion(row)

    # -- freeze jobs (worker-side publication) --------------------------------

    _JOB_KEYS = (
        "job_id", "thread_id", "case_id", "pathway", "status", "frozen_record", "deliverable_id",
        "error", "requested_by", "requested_at", "claimed_at", "completed_at",
    )

    def _job(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: row.get(key) for key in self._JOB_KEYS}

    def request_freeze(self, frozen_record: dict[str, Any], actor: str, audit: Any) -> dict[str, Any]:
        """One job per freeze identity. A QUEUED/RENDERING/PUBLISHED job is
        returned as is; a FAILED job is requeued; racing requests converge."""
        thread_id = frozen_record["thread_id"]
        with self._WRITE_LOCK, self.engine.begin() as conn:
            existing = conn.execute(
                sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.thread_id == thread_id)
            ).mappings().first()
            if existing is not None:
                if existing["status"] != "FAILED":
                    return self._job(dict(existing))
                conn.execute(
                    sa.update(deliverable_freeze_jobs)
                    .where(deliverable_freeze_jobs.c.job_id == existing["job_id"],
                           deliverable_freeze_jobs.c.status == "FAILED")
                    .values(status="QUEUED", error=None, frozen_record=frozen_record,
                            requested_by=actor, requested_at=now_iso(), claimed_at=None, completed_at=None)
                )
                audit(conn, "deliverable.freeze_queued", actor, case_id=frozen_record["case_id"],
                      pathway=frozen_record["pathway"], deliverable_id=frozen_record["deliverable_id"])
                row = conn.execute(
                    sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.job_id == existing["job_id"])
                ).mappings().first()
                return self._job(dict(row))
            row = {
                "job_id": new_id("frz"), "thread_id": thread_id, "case_id": frozen_record["case_id"],
                "pathway": frozen_record["pathway"], "status": "QUEUED", "frozen_record": frozen_record,
                "deliverable_id": None, "error": None, "requested_by": actor, "requested_at": now_iso(),
                "claimed_at": None, "completed_at": None,
            }
            conn.execute(deliverable_freeze_jobs.insert().values(**row))
            audit(conn, "deliverable.freeze_queued", actor, case_id=frozen_record["case_id"],
                  pathway=frozen_record["pathway"], deliverable_id=frozen_record["deliverable_id"])
            return self._job(row)

    def freeze_job(self, job_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.job_id == job_id)
            ).mappings().first()
        return self._job(dict(row)) if row else None

    def freeze_job_for_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.thread_id == thread_id)
            ).mappings().first()
        return self._job(dict(row)) if row else None

    def pending_freeze_jobs(self, case_id: str | None = None, pathway: str | None = None) -> list[dict[str, Any]]:
        """QUEUED, RENDERING and FAILED jobs — everything a workspace must show
        and everything a worker pass may still owe."""
        query = sa.select(deliverable_freeze_jobs).where(
            deliverable_freeze_jobs.c.status.in_(("QUEUED", "RENDERING", "FAILED"))
        )
        if case_id is not None:
            query = query.where(deliverable_freeze_jobs.c.case_id == case_id)
        if pathway is not None:
            query = query.where(deliverable_freeze_jobs.c.pathway == pathway)
        with self.engine.connect() as conn:
            rows = conn.execute(query.order_by(deliverable_freeze_jobs.c.seq)).mappings().all()
        return [self._job(dict(row)) for row in rows]

    def queued_freeze_job_ids(self) -> list[str]:
        with self.engine.connect() as conn:
            return [row for (row,) in conn.execute(
                sa.select(deliverable_freeze_jobs.c.job_id)
                .where(deliverable_freeze_jobs.c.status == "QUEUED")
                .order_by(deliverable_freeze_jobs.c.seq)
            )]

    def claim_freeze_job(self, job_id: str) -> dict[str, Any] | None:
        """QUEUED -> RENDERING wins exactly once; a loser gets None and renders nothing."""
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(deliverable_freeze_jobs)
                .where(deliverable_freeze_jobs.c.job_id == job_id, deliverable_freeze_jobs.c.status == "QUEUED")
                .values(status="RENDERING", claimed_at=now_iso())
            ).rowcount
            if not changed:
                return None
            row = conn.execute(
                sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.job_id == job_id)
            ).mappings().first()
            return self._job(dict(row))

    def fail_freeze_job(self, job_id: str, code: str, actor: str, audit: Any) -> bool:
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(deliverable_freeze_jobs)
                .where(deliverable_freeze_jobs.c.job_id == job_id, deliverable_freeze_jobs.c.status == "RENDERING")
                .values(status="FAILED", error={"code": code}, completed_at=now_iso())
            ).rowcount
            if changed:
                row = conn.execute(
                    sa.select(deliverable_freeze_jobs).where(deliverable_freeze_jobs.c.job_id == job_id)
                ).mappings().first()
                audit(conn, "deliverable.freeze_failed", actor, case_id=row["case_id"],
                      pathway=row["pathway"], deliverable_id=row["frozen_record"]["deliverable_id"], code=code)
            return bool(changed)

    def recover_freeze_jobs(self) -> int:
        """RENDERING -> QUEUED for every job a dead worker left behind. Only the
        single-instance worker calls this, at start, so no live render is stolen."""
        with self.engine.begin() as conn:
            return conn.execute(
                sa.update(deliverable_freeze_jobs)
                .where(deliverable_freeze_jobs.c.status == "RENDERING")
                .values(status="QUEUED", claimed_at=None)
            ).rowcount

    def publish_frozen(self, job_id: str, record: dict[str, Any], actor: str, audit: Any) -> tuple[dict[str, Any], bool]:
        """The worker's one transaction: frozen record + parked thread + audit +
        job PUBLISHED. An existing record for the identity is returned unchanged
        (created=False) so the caller can judge conflict versus convergence."""
        with self._WRITE_LOCK, self.engine.begin() as conn:
            existing = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == record["deliverable_id"])
            ).mappings().first()
            if existing is None:
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
                frozen = self._frozen(row)
                created = True
            else:
                frozen = self._frozen(dict(existing))
                created = False
                if frozen["preview_digest"] != record["preview_digest"]:
                    # The gate's own render is the only render: a divergent
                    # render for the same identity is a conflict, never an
                    # overwrite — the transaction rolls back and the job fails.
                    raise ValueError("DELIVERABLE_FREEZE_CONFLICT: a divergent render exists for this freeze identity")
            conn.execute(
                sa.update(deliverable_freeze_jobs)
                .where(deliverable_freeze_jobs.c.job_id == job_id, deliverable_freeze_jobs.c.status == "RENDERING")
                .values(status="PUBLISHED", deliverable_id=frozen["deliverable_id"], error=None, completed_at=now_iso())
            )
            return frozen, created

    # -- filing receipts --------------------------------------------------------

    def filing_receipt(self, case_id: str, deliverable_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_filing_receipts)
                .where(deliverable_filing_receipts.c.deliverable_id == deliverable_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        receipt = dict(row["receipt"])
        if row["receipt_digest"] != digest({key: value for key, value in receipt.items() if key != "receipt_digest"}) \
                or receipt.get("receipt_digest") != row["receipt_digest"]:
            raise ValueError("FILING_RECEIPT_INTEGRITY_FAILED: stored receipt does not match its digest")
        return receipt

    def filing_receipts(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(deliverable_filing_receipts)
                .where(deliverable_filing_receipts.c.case_id == case_id)
                .order_by(deliverable_filing_receipts.c.seq)
            ).mappings().all()
        return [dict(row["receipt"]) for row in rows]

    # -- revisions ----------------------------------------------------------

    @staticmethod
    def _revision(row: dict[str, Any], **expected_identity: Any) -> dict[str, Any]:
        keys = (
            "draft_id", "revision_id", "case_id", "pathway", "version",
            "digest", "content", "created_by", "created_at",
        )
        try:
            revision = {key: row[key] for key in keys}
            valid = (
                isinstance(revision["content"], dict)
                and revision["digest"] == digest(revision["content"])
                and type(revision["version"]) is int
                and revision["version"] >= 1
                and all(
                    isinstance(revision[key], str) and bool(revision[key])
                    for key in (
                        "draft_id", "revision_id", "case_id", "pathway",
                        "digest", "created_by", "created_at",
                    )
                )
                and all(revision.get(key) == value for key, value in expected_identity.items())
            )
        except (KeyError, TypeError, ValueError):
            valid = False
            revision = {}
        if not valid:
            raise ValueError(
                "DELIVERABLE_REVISION_INTEGRITY_FAILED: stored revision envelope is invalid"
            )
        return revision

    def _append_revision(
        self,
        conn: Any,
        case_id: str,
        pathway: str,
        expected_version: int,
        content: dict[str, Any],
        content_digest: str,
        actor: str,
        audit: Any,
    ) -> dict[str, Any]:
        head = conn.execute(
            sa.select(deliverable_revisions)
            .where(
                deliverable_revisions.c.case_id == case_id,
                deliverable_revisions.c.pathway == pathway,
            )
            .order_by(deliverable_revisions.c.version.desc()).limit(1)
        ).mappings().first()
        current = (
            self._revision(dict(head), case_id=case_id, pathway=pathway)
            if head else None
        )
        current_version = current["version"] if current else 0
        if expected_version != current_version:
            raise DeliverableVersionConflict(current)
        row = {
            "revision_id": new_id("dlrev"),
            "draft_id": current["draft_id"] if current else new_id("dldraft"),
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
            raise DeliverableVersionConflict(current) from exc
        audit(conn, "deliverable.draft.saved", actor, case_id=case_id,
              pathway=pathway, revision_id=row["revision_id"], version=row["version"])
        return self._revision(
            row,
            case_id=case_id,
            pathway=pathway,
            draft_id=row["draft_id"],
            version=current_version + 1,
        )

    def append_revision(self, case_id: str, pathway: str, expected_version: int,
                        content: dict[str, Any], content_digest: str, actor: str, audit: Any) -> dict[str, Any]:
        with self._WRITE_LOCK, self.engine.begin() as conn:
            return self._append_revision(
                conn, case_id, pathway, expected_version, content, content_digest, actor, audit,
            )

    def head_revision(self, case_id: str, pathway: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_revisions)
                .where(deliverable_revisions.c.case_id == case_id, deliverable_revisions.c.pathway == pathway)
                .order_by(deliverable_revisions.c.version.desc()).limit(1)
            ).mappings().first()
        return self._revision(dict(row), case_id=case_id, pathway=pathway) if row else None

    def revision_history(self, case_id: str, pathway: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(deliverable_revisions)
                .where(deliverable_revisions.c.case_id == case_id, deliverable_revisions.c.pathway == pathway)
                .order_by(deliverable_revisions.c.version)
            ).mappings().all()
        if not rows:
            return []
        draft_id = rows[0]["draft_id"]
        return [
            self._revision(
                dict(row),
                case_id=case_id,
                pathway=pathway,
                draft_id=draft_id,
                version=version,
            )
            for version, row in enumerate(rows, start=1)
        ]

    def revision_by_id(self, case_id: str, revision_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_revisions).where(deliverable_revisions.c.revision_id == revision_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return self._revision(dict(row), case_id=case_id, revision_id=revision_id)

    def revision_for_freeze(
        self,
        case_id: str,
        draft_id: str,
        version: int,
    ) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(deliverable_revisions).where(
                    deliverable_revisions.c.case_id == case_id,
                    deliverable_revisions.c.draft_id == draft_id,
                    deliverable_revisions.c.version == version,
                ).limit(2)
            ).mappings().all()
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError(
                "DELIVERABLE_REVISION_INTEGRITY_FAILED: draft identity is ambiguous"
            )
        return self._revision(
            dict(rows[0]), case_id=case_id, draft_id=draft_id, version=version,
        )

    # -- frozen records and threads -----------------------------------------

    _FROZEN_KEYS = (
        "deliverable_id", "thread_id", "case_id", "pathway", "status", "preview_digest",
        "input_fingerprint", "build_id", "payload", "exports", "authority",
        "draft_version", "draft_digest", "superseded_by_id", "filed_by", "filed_at",
        "change_request", "created_by", "created_at", "opinion_id", "signed_by",
    )

    def _frozen(self, row: dict[str, Any]) -> dict[str, Any]:
        return {key: row.get(key) for key in self._FROZEN_KEYS}

    def frozen_record(self, case_id: str, deliverable_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
        if row is None or row["case_id"] != case_id:
            return None
        return self._frozen(dict(row))

    def frozen_by_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.thread_id == thread_id)
            ).mappings().first()
        return self._frozen(dict(row)) if row else None

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
            filed = self._frozen(dict(row))
            # The detached receipt rides the filing transaction (Task 10): the
            # approver is named here and in the audit row, never in the bytes.
            receipt = {
                "schema_version": "caos.filing-receipt.v1",
                "receipt_id": new_id("rcpt"),
                "deliverable_id": deliverable_id,
                "case_id": filed["case_id"],
                "pathway": filed["pathway"],
                "draft_version": filed["draft_version"],
                "draft_digest": filed["draft_digest"],
                "preview_digest": filed["preview_digest"],
                "input_fingerprint": filed["input_fingerprint"],
                "approval_hash": f"sha256:{filed['preview_digest']}",
                "content_digest": (filed["payload"] or {}).get("preview_digest"),
                "exports": {fmt: meta["sha256"] for fmt, meta in sorted((filed["exports"] or {}).items())},
                "opinion_id": filed.get("opinion_id"),
                "signed_by": filed.get("signed_by"),
                "frozen_by": filed["created_by"],
                "frozen_at": filed["created_at"],
                "approved_by": actor,
                "approved_at": filed["filed_at"],
            }
            receipt["receipt_digest"] = digest(receipt)
            conn.execute(deliverable_filing_receipts.insert().values(
                receipt_id=receipt["receipt_id"], deliverable_id=deliverable_id, case_id=filed["case_id"],
                pathway=filed["pathway"], receipt=receipt, receipt_digest=receipt["receipt_digest"],
            ))
            audit(conn, "deliverable.filed", actor, case_id=row["case_id"], deliverable_id=deliverable_id,
                  sha256=receipt["receipt_digest"])
            return filed

    def request_changes_and_append_revision(
        self,
        deliverable_id: str,
        expected_version: int,
        content: dict[str, Any],
        content_digest: str,
        actor: str,
        comment: str,
        audit: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
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
            revision = self._append_revision(
                conn,
                row["case_id"],
                row["pathway"],
                expected_version,
                content,
                content_digest,
                actor,
                audit,
            )
            return self._frozen(dict(row)), revision

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


class OpinionHeadConflict(ValueError):
    """OPINION_HEAD_CONFLICT — the sign-off named a stale head; carries the real one."""

    def __init__(self, current: dict[str, Any] | None) -> None:
        self.current = current
        super().__init__("OPINION_HEAD_CONFLICT")
