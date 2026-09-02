"""Model Builder store: builds and the append-only revision ledger.

Fresh code — the legacy ModelLedger implementations are not ported. Contracts
kept: queueing is idempotent per (case, input_fingerprint) with the winner
attributed; authority order is a server-assigned monotonic sequence never
exposed; sign-off is a CAS-guarded append with a separate head pointer and its
audit event in the same transaction; revisions are immutable once written.
"""

from __future__ import annotations

import threading
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from ..contracts import digest
from .store import new_id, now_iso, sources

model_metadata = sa.MetaData()

model_builds = sa.Table(
    "model_builds", model_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("accepted_run_id", sa.String),
    sa.Column("snapshot_id", sa.String),
    sa.Column("source_set_id", sa.String),
    sa.Column("input_fingerprint", sa.String),
    sa.Column("methodology_build_id", sa.String),
    sa.Column("calculation_runtime", sa.JSON),
    sa.Column("registry_version", sa.String),
    sa.Column("registry_digest", sa.String),
    sa.Column("assumptions_digest", sa.String),
    sa.Column("outputs_digest", sa.String),
    sa.Column("payload", sa.JSON),
    sa.Column("payload_digest", sa.String),
    sa.Column("qa", sa.JSON),
    sa.Column("error", sa.JSON),
    sa.Column("export", sa.JSON),
    sa.Column("queued_at", sa.String, nullable=False),
    sa.Column("started_at", sa.String),
    sa.Column("completed_at", sa.String),
    sa.Column("worksheet_schema_version", sa.String),
    sa.Column("created_by", sa.String, nullable=False),
    sa.UniqueConstraint("case_id", "input_fingerprint", name="uq_model_builds_case_fingerprint"),
)

model_revisions = sa.Table(
    "model_revisions", model_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.String, nullable=False, unique=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("revision_number", sa.Integer, nullable=False),
    sa.Column("build_id", sa.String, nullable=False),
    sa.Column("record", sa.JSON, nullable=False),
    sa.Column("record_digest", sa.String, nullable=False),
    sa.Column("export", sa.JSON),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.UniqueConstraint("case_id", "revision_number", name="uq_model_revisions_case_number"),
)

MODEL_REVISION_IMMUTABLE_COLUMNS = (
    "seq", "id", "case_id", "revision_number", "build_id", "record",
    "record_digest", "created_by", "created_at",
)

SQLITE_MODEL_REVISION_UPDATE_DDL = (
    "CREATE TRIGGER model_revisions_append_only "
    f"BEFORE UPDATE OF {', '.join(MODEL_REVISION_IMMUTABLE_COLUMNS)} "
    "ON model_revisions BEGIN "
    "SELECT RAISE(ABORT, 'APPEND_ONLY: model revisions are immutable'); "
    "END"
)
SQLITE_MODEL_REVISION_DELETE_DDL = (
    "CREATE TRIGGER model_revisions_no_delete "
    "BEFORE DELETE ON model_revisions BEGIN "
    "SELECT RAISE(ABORT, 'APPEND_ONLY: model revisions cannot be deleted'); "
    "END"
)
POSTGRES_MODEL_REVISION_FUNCTION_DDL = """
CREATE OR REPLACE FUNCTION caos_model_revision_immutable() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'APPEND_ONLY: model revisions cannot be deleted';
    END IF;
    IF NEW.seq IS DISTINCT FROM OLD.seq
       OR NEW.id IS DISTINCT FROM OLD.id
       OR NEW.case_id IS DISTINCT FROM OLD.case_id
       OR NEW.revision_number IS DISTINCT FROM OLD.revision_number
       OR NEW.build_id IS DISTINCT FROM OLD.build_id
       OR NEW.record::text IS DISTINCT FROM OLD.record::text
       OR NEW.record_digest IS DISTINCT FROM OLD.record_digest
       OR NEW.created_by IS DISTINCT FROM OLD.created_by
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'APPEND_ONLY: model revisions are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
""".strip()
POSTGRES_MODEL_REVISION_TRIGGER_DDL = """
CREATE TRIGGER model_revisions_append_only
BEFORE UPDATE OR DELETE ON model_revisions
FOR EACH ROW EXECUTE FUNCTION caos_model_revision_immutable()
""".strip()

model_revision_heads = sa.Table(
    "model_revision_heads", model_metadata,
    sa.Column("case_id", sa.String, primary_key=True),
    sa.Column("revision_id", sa.String, nullable=False),
    sa.Column("revision_number", sa.Integer, nullable=False),
)


PUBLIC_BUILD_KEYS = (
    "id", "case_id", "status", "accepted_run_id", "snapshot_id", "source_set_id",
    "input_fingerprint", "methodology_build_id", "calculation_runtime",
    "registry_version", "registry_digest", "assumptions_digest", "outputs_digest",
    "payload", "payload_digest", "qa", "error", "export", "queued_at",
    "started_at", "completed_at", "worksheet_schema_version", "created_by",
)


def public_build(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in PUBLIC_BUILD_KEYS}


def model_revision_record_digest(row: dict[str, Any]) -> str:
    return digest({
        "schema_version": "caos.model-revision-record.v1",
        "id": row["id"],
        "case_id": row["case_id"],
        "revision_number": row["revision_number"],
        "build_id": row["build_id"],
        "record": row["record"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    })


class ModelRevisionConflict(ValueError):
    """MODEL_REVISION_CONFLICT — carries the current head for the loser."""

    def __init__(self, current: dict[str, Any] | None) -> None:
        self.current = current
        super().__init__("MODEL_REVISION_CONFLICT")


class ModelStore:
    # ponytail: one process-wide write lock serialises sign-off CAS on SQLite;
    # Postgres would use SELECT ... FOR UPDATE on the head row instead.
    _WRITE_LOCK = threading.Lock()

    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine
        model_metadata.create_all(engine)
        self._ensure_revision_schema()

    def _backfill_revision_digests(self, conn: sa.Connection) -> None:
        rows = conn.execute(
            sa.select(model_revisions).where(model_revisions.c.record_digest.is_(None))
        ).mappings().all()
        for stored in rows:
            row = dict(stored)
            conn.execute(
                sa.update(model_revisions)
                .where(model_revisions.c.seq == row["seq"])
                .values(record_digest=model_revision_record_digest(row))
            )

    def _ensure_revision_schema(self) -> None:
        dialect = self.engine.dialect.name
        if dialect == "postgresql":
            with self.engine.begin() as conn:
                conn.exec_driver_sql(
                    "DROP TRIGGER IF EXISTS model_revisions_append_only ON model_revisions"
                )
                conn.exec_driver_sql(
                    "ALTER TABLE model_revisions ADD COLUMN IF NOT EXISTS record_digest VARCHAR"
                )
                self._backfill_revision_digests(conn)
                conn.exec_driver_sql(
                    "ALTER TABLE model_revisions ALTER COLUMN record_digest SET NOT NULL"
                )
                conn.exec_driver_sql(POSTGRES_MODEL_REVISION_FUNCTION_DDL)
                conn.exec_driver_sql(POSTGRES_MODEL_REVISION_TRIGGER_DDL)
            return
        if dialect != "sqlite":
            raise RuntimeError(f"unsupported model-store dialect: {dialect}")
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                conn.exec_driver_sql("DROP TRIGGER IF EXISTS model_revisions_append_only")
                conn.exec_driver_sql("DROP TRIGGER IF EXISTS model_revisions_no_delete")
                columns = {
                    row[1]
                    for row in conn.exec_driver_sql('PRAGMA table_info("model_revisions")')
                }
                if "record_digest" not in columns:
                    conn.exec_driver_sql(
                        "ALTER TABLE model_revisions ADD COLUMN record_digest VARCHAR"
                    )
                self._backfill_revision_digests(conn)
                conn.exec_driver_sql(SQLITE_MODEL_REVISION_UPDATE_DDL)
                conn.exec_driver_sql(SQLITE_MODEL_REVISION_DELETE_DDL)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def mutate_revision(self, revision_id: str, changes: dict[str, Any]) -> None:
        """The only mutation path over revision rows; the DB trigger refuses
        every protected column (export job state goes via update_revision_export)."""
        allowed = {"id", "case_id", "revision_number", "build_id", "record", "created_by", "created_at"}
        values = {key: value for key, value in changes.items() if key in allowed} or {"record": changes}
        with self.engine.begin() as conn:
            conn.execute(sa.update(model_revisions).where(model_revisions.c.id == revision_id).values(**values))

    # -- builds ------------------------------------------------------------

    def queue_build(self, build: dict[str, Any], actor: str) -> tuple[dict[str, Any], bool]:
        row = {
            "id": build.get("id") or new_id("mdl"),
            "status": "QUEUED",
            "queued_at": build.get("queued_at") or now_iso(),
            "created_by": actor,
            "export": None,
            **{key: build.get(key) for key in (
                "case_id", "accepted_run_id", "snapshot_id", "source_set_id",
                "input_fingerprint", "methodology_build_id", "calculation_runtime",
                "registry_version", "registry_digest", "worksheet_schema_version",
            )},
        }
        try:
            with self.engine.begin() as conn:
                conn.execute(model_builds.insert().values(**row))
            return self.get_build(row["id"]), True  # type: ignore[return-value]
        except IntegrityError:
            existing = self.build_for_fingerprint(build["case_id"], build["input_fingerprint"])
            if existing is None:
                raise
            return existing, False

    def insert_build_row(self, row: dict[str, Any]) -> dict[str, Any]:
        with self.engine.begin() as conn:
            conn.execute(model_builds.insert().values(**row))
        return self.get_build(row["id"])  # type: ignore[return-value]

    def get_build(self, build_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(model_builds).where(model_builds.c.id == build_id)).mappings().first()
        return public_build(dict(row)) if row else None

    def build_for_fingerprint(self, case_id: str, input_fingerprint: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(model_builds).where(
                model_builds.c.case_id == case_id,
                model_builds.c.input_fingerprint == input_fingerprint,
            )).mappings().first()
        return public_build(dict(row)) if row else None

    def list_builds(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(model_builds).where(model_builds.c.case_id == case_id).order_by(model_builds.c.seq)
            ).mappings().all()
        return [public_build(dict(row)) for row in rows]

    def current_build(self, case_id: str) -> dict[str, Any] | None:
        """Latest READY build by the server-assigned creation sequence —
        timestamps and id collation never participate."""
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(model_builds)
                .where(model_builds.c.case_id == case_id, model_builds.c.status == "READY")
                .order_by(model_builds.c.seq.desc()).limit(1)
            ).mappings().first()
        return public_build(dict(row)) if row else None

    @staticmethod
    def _live_sources_condition(source_ids: list[str]):
        """Publication is conditional on every pinned source still being live
        inside the same statement: a withdrawal that commits first makes the
        UPDATE match nothing, so a revoked authority never becomes READY."""
        withdrawn = sa.select(sa.literal(1)).where(
            sources.c.id.in_(list(source_ids)), sources.c.withdrawn.is_(True),
        )
        present = sa.select(sa.func.count()).where(sources.c.id.in_(list(source_ids))).scalar_subquery()
        return sa.and_(~sa.exists(withdrawn), present == len(set(source_ids)))

    def update_build(self, build_id: str, *, expected_status: tuple[str, ...] | None = None,
                     expected_input_fingerprint: str | None = None,
                     expected_export_status: str | None = None,
                     expected_live_source_ids: list[str] | None = None, **values: Any) -> bool:
        with self.engine.begin() as conn:
            where = [model_builds.c.id == build_id]
            if expected_status is not None:
                where.append(model_builds.c.status.in_(expected_status))
            if expected_input_fingerprint is not None:
                # An executor may only publish under the identity it computed from.
                where.append(model_builds.c.input_fingerprint == expected_input_fingerprint)
            if expected_export_status is not None:
                where.append(model_builds.c.export["status"].as_string() == expected_export_status)
            if expected_live_source_ids is not None:
                where.append(self._live_sources_condition(expected_live_source_ids))
            return bool(conn.execute(sa.update(model_builds).where(*where).values(**values)).rowcount)

    def active_build_count(self) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count()).where(model_builds.c.status.in_(("QUEUED", "BUILDING")))
            ).scalar_one()

    def queued_work(self) -> dict[str, list[str]]:
        """Worker poll: build ids QUEUED for calculation, then build/revision ids
        whose export is QUEUED — each in server-assigned creation order. Claiming
        stays with the executor's CAS (update_build expected_status)."""
        with self.engine.connect() as conn:
            builds = [row for (row,) in conn.execute(
                sa.select(model_builds.c.id)
                .where(model_builds.c.status == "QUEUED").order_by(model_builds.c.seq))]
            build_exports = [row for (row,) in conn.execute(
                sa.select(model_builds.c.id)
                .where(model_builds.c.export["status"].as_string() == "QUEUED")
                .order_by(model_builds.c.seq))]
            revision_exports = [row for (row,) in conn.execute(
                sa.select(model_revisions.c.id)
                .where(model_revisions.c.export["status"].as_string() == "QUEUED")
                .order_by(model_revisions.c.seq))]
        return {"builds": builds, "exports": build_exports + revision_exports}

    # -- revisions (append-only) -------------------------------------------

    def sign_off_revision(
        self,
        case_id: str,
        record: dict[str, Any],
        actor: str,
        expected_head_revision_id: str | None,
        audit: Any,
    ) -> dict[str, Any]:
        """CAS append: head must equal the caller's expectation; the revision
        row, head advance, and audit event commit in one transaction."""
        with self._WRITE_LOCK, self.engine.begin() as conn:
            head = conn.execute(
                sa.select(model_revision_heads).where(model_revision_heads.c.case_id == case_id)
            ).mappings().first()
            head_id = head["revision_id"] if head else None
            if head_id != expected_head_revision_id:
                current = None
                if head_id:
                    row = conn.execute(sa.select(model_revisions).where(model_revisions.c.id == head_id)).mappings().first()
                    current = (
                        self._public(
                            dict(row), case_id=case_id, id=head_id,
                            revision_number=head["revision_number"],
                        )
                        if row else None
                    )
                raise ModelRevisionConflict(current)
            number = (head["revision_number"] if head else 0) + 1
            row = {
                "id": new_id("rev"),
                "case_id": case_id,
                "revision_number": number,
                "build_id": record["build_id"] if isinstance(record, dict) else None,
                "record": record,
                "export": {"status": "QUEUED"},
                "created_by": actor,
                "created_at": now_iso(),
            }
            row["record_digest"] = model_revision_record_digest(row)
            # Validate the record before anything is written: an invalid signed
            # record is refused up front, never inserted and rolled back.
            public = self._public(row)
            conn.execute(model_revisions.insert().values(**row))
            if head:
                conn.execute(sa.update(model_revision_heads).where(model_revision_heads.c.case_id == case_id)
                             .values(revision_id=row["id"], revision_number=number))
            else:
                conn.execute(model_revision_heads.insert().values(
                    case_id=case_id, revision_id=row["id"], revision_number=number,
                ))
            audit(conn, "model.revision.signed", actor, case_id=case_id, revision_id=row["id"],
                  revision_number=number, assumptions_digest=record.get("assumptions_digest"))
            return public

    @staticmethod
    def _public(row: dict[str, Any], **expected_identity: Any) -> dict[str, Any]:
        try:
            record = row["record"]
            valid = (
                isinstance(record, dict)
                and row["record_digest"] == model_revision_record_digest(row)
                and record.get("case_id") == row["case_id"]
                and record.get("build_id") == row["build_id"]
                and record.get("assumptions_digest")
                == digest(record.get("effective_assumptions"))
                and record.get("outputs_digest") == digest(record.get("outputs"))
                and not {
                    "id", "revision_number", "record_digest", "export",
                    "created_by", "created_at",
                }.intersection(record)
                and type(row["revision_number"]) is int
                and row["revision_number"] >= 1
                and all(
                    isinstance(row[key], str) and bool(row[key])
                    for key in (
                        "id", "case_id", "build_id", "record_digest",
                        "created_by", "created_at",
                    )
                )
                and all(row.get(key) == value for key, value in expected_identity.items())
            )
        except (KeyError, TypeError, ValueError):
            valid = False
            record = {}
        if not valid:
            raise ValueError(
                "MODEL_REVISION_INTEGRITY_FAILED: signed revision record is invalid"
            )
        return {
            **record,
            "id": row["id"],
            "revision_number": row["revision_number"],
            "export": row.get("export"),
            "created_by": row["created_by"],
            "created_at": row["created_at"],
        }

    def get_revision(self, revision_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(model_revisions).where(model_revisions.c.id == revision_id)).mappings().first()
        return self._public(dict(row), id=revision_id) if row else None

    def list_revisions(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(model_revisions).where(model_revisions.c.case_id == case_id).order_by(model_revisions.c.revision_number)
            ).mappings().all()
        return [self._public(dict(row), case_id=case_id) for row in rows]

    def list_revision_exports(self, case_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(model_revisions)
                .where(model_revisions.c.case_id == case_id)
                .order_by(model_revisions.c.revision_number)
            ).mappings().all()
        return [
            {"revision_id": revision["id"], "export": revision["export"]}
            for revision in (
                self._public(dict(row), case_id=case_id) for row in rows
            )
        ]

    def head_revision(self, case_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            head = conn.execute(
                sa.select(model_revision_heads).where(model_revision_heads.c.case_id == case_id)
            ).mappings().first()
        if head is None:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(model_revisions).where(
                    model_revisions.c.id == head["revision_id"]
                )
            ).mappings().first()
        if row is None:
            raise ValueError("MODEL_REVISION_INTEGRITY_FAILED: revision head is missing")
        return self._public(
            dict(row),
            id=head["revision_id"],
            case_id=case_id,
            revision_number=head["revision_number"],
        )

    def update_revision_export(self, revision_id: str, export: dict[str, Any], *,
                               expected_export_status: str | None = None,
                               expected_live_source_ids: list[str] | None = None) -> bool:
        # The export pointer is job state riding beside the immutable record.
        with self.engine.begin() as conn:
            where = [model_revisions.c.id == revision_id]
            if expected_export_status is not None:
                where.append(model_revisions.c.export["status"].as_string() == expected_export_status)
            if expected_live_source_ids is not None:
                where.append(self._live_sources_condition(expected_live_source_ids))
            return bool(conn.execute(sa.update(model_revisions).where(*where).values(export=export)).rowcount)

    def revision_order(self, case_id: str) -> list[int]:
        with self.engine.connect() as conn:
            return list(conn.execute(
                sa.select(model_revisions.c.seq).where(model_revisions.c.case_id == case_id)
                .order_by(model_revisions.c.revision_number)
            ).scalars().all())


def build_result_digest(payload: dict[str, Any]) -> str:
    return digest(payload)
