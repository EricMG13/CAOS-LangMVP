"""Case-scoped audit package (Task 10; ENTERPRISE_READINESS_PLAN Phase 4 items
16–17; ETR AUD-016–AUD-019).

One zip per case: manifests and bounded metadata for sources and dispositions
(block ids and text digests, never block text), source sets, intakes, every
run with its plan, nodes, events, budget ledger, snapshot and validated
artifacts, model builds and revisions with their published workbooks,
deliverable revisions, opinions, freeze jobs, frozen records, filing receipts
and the exact filed bytes, the case's audit chain and head, and the
methodology and runtime identity. `caos/server/caos/audit/verify_package.py`
checks all of it offline with the standard library alone.

What never enters the package: vault paths, source text, provider request or
response bodies (the store keeps digests and usage only), prompts, hidden
reasoning, secrets. `_scrub` enforces the text rule structurally on every
section that can carry document-derived text.
"""

from __future__ import annotations

import hashlib
import io
import json
import platform
import sys
import zipfile
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from ..atomic_files import MAX_EXPORT_BYTES, VaultFileIntegrityError, VaultFileUnavailable, read_verified_vault_bytes
from ..contracts import canonical_json, digest
from ..storage.deliverables import (
    DeliverableStore,
    deliverable_filing_receipts,
    deliverable_freeze_jobs,
    deliverable_frozen,
    deliverable_opinions,
    deliverable_revisions,
)
from ..storage.models import model_builds, model_revisions
from ..storage.runs import run_artifacts, run_budgets, run_events, run_nodes, run_snapshots, runs
from ..storage.store import DomainStore, case_intakes, source_sets, sources

PACKAGE_SCHEMA_VERSION = "caos.audit-package.v1"
VERIFIER_PATH = "caos/server/caos/audit/verify_package.py"
README = """CAOS audit package

Verify offline, on any machine with Python 3.12+ and no CAOS install:

    python verify_package.py <this zip>

The verifier (caos/server/caos/audit/verify_package.py in the CAOS repository)
recomputes every object digest in manifest.json, the per-case audit chain,
every frozen deliverable's content and approval digests, every filing receipt
and its cross-references, the signer/approver separation, the exact filed
export bytes, the run plan and snapshot digests, the model payload digests,
and re-renders each Markdown export from its frozen payload byte for byte.

Nothing in this package is a secret, a prompt, a provider message body or
source-document text: sources carry block ids and text digests only.
"""


def _text_digest(text: Any) -> dict[str, Any]:
    encoded = str(text or "").encode("utf-8")
    return {"text_sha256": hashlib.sha256(encoded).hexdigest(), "text_length": len(str(text or ""))}


def _scrub(value: Any) -> Any:
    """Replace every `text` field with its digest and drop vault paths, at any depth."""
    if isinstance(value, dict):
        scrubbed: dict[str, Any] = {}
        for key, child in value.items():
            if key == "vault_path":
                continue
            if key == "text" and isinstance(child, str):
                scrubbed.update(_text_digest(child))
                continue
            scrubbed[key] = _scrub(child)
        return scrubbed
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _rows(engine: sa.Engine, table: sa.Table, *clauses: Any, order: Any = None) -> list[dict[str, Any]]:
    query = sa.select(table).where(*clauses)
    if order is not None:
        query = query.order_by(order)
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query).mappings().all()]


def _vault_bytes(vault_dir: Path, meta: dict[str, Any] | None) -> tuple[bytes | None, str | None]:
    if not meta or not meta.get("vault_key"):
        return None, "EXPORT_METADATA_MISSING"
    try:
        return read_verified_vault_bytes(
            vault_dir, meta["vault_key"], expected_sha256=meta["sha256"], expected_size=meta["size"],
            max_bytes=MAX_EXPORT_BYTES,
        ), None
    except VaultFileUnavailable:
        return None, "EXPORT_UNAVAILABLE"
    except VaultFileIntegrityError:
        return None, "EXPORT_INTEGRITY_FAILED"


def build_case_package(
    *,
    store: DomainStore,
    vault_dir: Path,
    case_id: str,
    methodology_build_id: str | None,
    generated_by: str,
    generated_at: str,
) -> bytes:
    case = store.get_case(case_id)
    if case is None:
        raise ValueError("CASE_NOT_FOUND")
    engine = store.engine
    records = DeliverableStore(engine)
    objects: dict[str, bytes] = {}

    def put_json(path: str, value: Any) -> None:
        objects[path] = (canonical_json(value) + "\n").encode("utf-8")

    put_json("case/case.json", {**case, "members": dict(case.get("members") or {})})
    put_json("case/sources.json", _scrub(_rows(engine, sources, sources.c.case_id == case_id, order=sources.c.created_at)))
    put_json("case/source_sets.json", _rows(engine, source_sets, source_sets.c.case_id == case_id, order=source_sets.c.version))
    put_json("case/intakes.json", _scrub(_rows(engine, case_intakes, case_intakes.c.case_id == case_id, order=case_intakes.c.created_at)))

    run_rows = _rows(engine, runs, runs.c.case_id == case_id, order=runs.c.created_at)
    run_index = []
    for run in run_rows:
        run_id = run["id"]
        run_index.append({"run_id": run_id, "pathway": run["pathway"], "depth": run["depth"], "status": run["status"]})
        put_json(f"runs/{run_id}/run.json", _scrub(run))
        put_json(f"runs/{run_id}/nodes.json", _rows(engine, run_nodes, run_nodes.c.run_id == run_id, order=run_nodes.c.stage))
        put_json(f"runs/{run_id}/artifacts.json", _rows(engine, run_artifacts, run_artifacts.c.run_id == run_id, order=run_artifacts.c.created_at))
        put_json(f"runs/{run_id}/events.json", _rows(engine, run_events, run_events.c.run_id == run_id, order=run_events.c.seq))
        put_json(f"runs/{run_id}/budget.json", _rows(engine, run_budgets, run_budgets.c.run_id == run_id))
        put_json(f"runs/{run_id}/snapshot.json", _rows(engine, run_snapshots, run_snapshots.c.run_id == run_id))
    put_json("runs/index.json", run_index)

    builds = _rows(engine, model_builds, model_builds.c.case_id == case_id, order=model_builds.c.seq)
    put_json("models/builds.json", builds)
    revisions = _rows(engine, model_revisions, model_revisions.c.case_id == case_id, order=model_revisions.c.seq)
    put_json("models/revisions.json", revisions)
    model_exports = []
    for record in [*builds, *revisions]:
        export = record.get("export") or {}
        if export.get("status") != "READY":
            continue
        content, problem = _vault_bytes(vault_dir, export)
        entry = {"target_id": record["id"], "sha256": export.get("sha256"), "size": export.get("size"), "problem": problem}
        if content is not None:
            objects[f"models/exports/{record['id']}.xlsx"] = content
            entry["path"] = f"models/exports/{record['id']}.xlsx"
        model_exports.append(entry)
    put_json("models/exports.json", model_exports)

    put_json("deliverables/revisions.json", _rows(engine, deliverable_revisions, deliverable_revisions.c.case_id == case_id, order=deliverable_revisions.c.seq))
    put_json("deliverables/opinions.json", _rows(engine, deliverable_opinions, deliverable_opinions.c.case_id == case_id, order=deliverable_opinions.c.seq))
    put_json("deliverables/freeze_jobs.json", [
        {key: value for key, value in job.items() if key != "frozen_record"}
        for job in _rows(engine, deliverable_freeze_jobs, deliverable_freeze_jobs.c.case_id == case_id, order=deliverable_freeze_jobs.c.seq)
    ])
    frozen_rows = _rows(engine, deliverable_frozen, deliverable_frozen.c.case_id == case_id, order=deliverable_frozen.c.seq)
    put_json("deliverables/frozen.json", [records._frozen(row) for row in frozen_rows])
    put_json("deliverables/receipts.json", [row["receipt"] for row in _rows(engine, deliverable_filing_receipts, deliverable_filing_receipts.c.case_id == case_id, order=deliverable_filing_receipts.c.seq)])
    export_index = []
    for row in frozen_rows:
        for format_name, meta in sorted((row.get("exports") or {}).items()):
            content, problem = _vault_bytes(vault_dir, meta)
            entry = {"deliverable_id": row["deliverable_id"], "format": format_name, "sha256": meta.get("sha256"),
                     "size": meta.get("size"), "status": row["status"], "problem": problem}
            if content is not None:
                path = f"deliverables/exports/{row['deliverable_id']}.{format_name}"
                objects[path] = content
                entry["path"] = path
            export_index.append(entry)
    put_json("deliverables/exports.json", export_index)

    chain = store.audit_chain(case_id)
    objects["audit/events.jsonl"] = ("".join(canonical_json(row) + "\n" for row in chain)).encode("utf-8")
    put_json("audit/head.json", store.audit_chain_head(case_id))
    put_json("methodology.json", {"build_id": methodology_build_id})
    put_json("environment.json", {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "verifier": VERIFIER_PATH,
    })
    objects["README.txt"] = README.encode("utf-8")

    manifest_objects = {
        path: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        for path, content in sorted(objects.items())
    }
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "case_id": case_id,
        "generated_at": generated_at,
        "generated_by": generated_by,
        "methodology_build_id": methodology_build_id,
        "audit_chain_head": store.audit_chain_head(case_id),
        "objects": manifest_objects,
    }
    manifest["package_digest"] = digest(manifest_objects)
    objects["manifest.json"] = (canonical_json(manifest) + "\n").encode("utf-8")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(objects):
            info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, objects[path])
    return output.getvalue()


def package_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def manifest_of(content: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return json.loads(archive.read("manifest.json"))
