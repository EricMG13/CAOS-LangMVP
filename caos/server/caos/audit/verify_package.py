#!/usr/bin/env python3
"""Offline verifier for a CAOS case audit package (Task 10; ETR AUD-017–019).

Standard library only, no CAOS import: copy this file next to the zip on any
review machine and run

    python verify_package.py <package.zip> [--json]

It recomputes every object digest in `manifest.json`, the per-case audit
chain (contiguous sequence, digest links, head), every frozen deliverable's
content digest and approval digest, every filing receipt and its
cross-references (approver ≠ signer, approver ≠ freeze actor, receipt named by
the filing audit row), the exact filed export bytes, the run plan and
snapshot digests, the model payload digests, and re-renders each Markdown
export from its frozen payload byte for byte — the reconstruction of a
published document from retained inputs alone.

Exit status 0 means no finding; 1 means at least one typed finding; 2 means
the package could not be read. The report is JSON with `--json`, otherwise a
short human summary followed by the findings.

The block between the BEGIN/END SHARED RENDERER markers is a verbatim copy of
`caos/server/caos/publishing/markdown.py`; `test_audit_package_spec.py` pins
the two byte-equal so the reconstruction can never drift from the application.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from typing import Any

# --- BEGIN SHARED RENDERER (copied verbatim into audit/verify_package.py) ---
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
PENDING_APPROVAL = "PENDING APPROVAL"
_PLAIN_NUMBER = re.compile(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
_NUMERIC_CELL = re.compile(r"^\s*[+-−(]?[£$€¥]?\s?\d[\d,]*(?:\.\d+)?\s?(?:%|x|bps|bn|m|mm|k)?\)?\s*$", re.IGNORECASE)

MASTHEAD_FIELDS = (
    ("Issuer", "issuer"),
    ("Case", "case_name"),
    ("Report type", "report_type"),
    ("Pathway", "pathway"),
    ("As-of date", "as_of_date"),
    ("Deliverable", "deliverable_id"),
    ("Draft version", "draft_version"),
    ("Accepted run", "run_id"),
    ("Accepted snapshot", "accepted_snapshot_id"),
    ("Source set", "source_set"),
    ("Model identity", "model_identity"),
    ("Methodology build", "methodology_build_id"),
    ("Machine assistance", "machine_assistance"),
    ("Opinion owner", "opinion_owner"),
    ("Opinion signed at", "opinion_signed_at"),
    ("Approval state", "approval_state"),
)


# --- the one projection every format reads ---------------------------------------


def _origin_label(section: dict[str, Any]) -> str:
    origin = section.get("origin") or {}
    if section.get("editable") and origin.get("kind") == "ANALYST":
        return "Analyst judgment"
    if origin.get("kind") == "ANALYST":
        return f"Analyst judgment · {origin.get('authority_id', '')}".rstrip(" ·")
    return f"Locked · {str(origin.get('kind', 'system')).lower()} · {origin.get('authority_id', '')}".rstrip(" ·")


def _legacy_publication(payload: dict[str, Any]) -> dict[str, Any]:
    """A frozen payload predating `publication` (or a bare renderer probe)
    still renders: pages from its canonical sections, else one text section
    per block, with a masthead from the fields the payload does carry."""
    content = payload.get("content") or {}
    sections = list(content.get("document_sections") or [])
    if not sections:
        titles = (payload.get("template") or {}).get("block_titles") or {}
        for index, block in enumerate(content.get("blocks") or [], start=1):
            body = block.get("text") or ""
            if not body:
                continue
            sections.append({
                "kind": "text", "section_id": f"block_{index}",
                "title": titles.get(block.get("block_id")) or block.get("title") or str(block.get("kind", "Block")).replace("_", " ").title(),
                "page": "Document", "editable": block.get("kind") in {"NARRATIVE", "LIMITATIONS"},
                "origin": {"kind": "ANALYST" if block.get("kind") in {"NARRATIVE", "LIMITATIONS", "HEADING"} else "SYSTEM",
                           "authority_id": block.get("block_id", "block"), "block_ids": []},
                "body": body,
            })
    pages: list[dict[str, Any]] = []
    for section in sections:
        if not pages or pages[-1]["name"] != section["page"]:
            pages.append({"name": section["page"], "sections": []})
        pages[-1]["sections"].append(section)
    draft = payload.get("draft") or {}
    return {
        "schema_version": "caos.deliverable.publication.legacy",
        "masthead": {
            "issuer": "Unavailable", "case_name": "Unavailable",
            "report_type": (payload.get("template") or {}).get("title") or f"{payload.get('pathway', '')} Deliverable",
            "pathway": payload.get("pathway", ""), "deliverable_id": "Unavailable",
            "draft_version": draft.get("version", ""), "draft_digest": draft.get("digest", ""),
            "input_fingerprint": payload.get("input_fingerprint", ""), "as_of_date": "Unavailable",
            "run_id": "Unavailable", "accepted_snapshot_id": "Unavailable", "source_set": "Unavailable",
            "model_identity": "Unavailable", "methodology_build_id": (payload.get("methodology") or {}).get("build_id", ""),
            "machine_assistance": "Unavailable", "approval_state": PENDING_APPROVAL, "watermark": PENDING_APPROVAL,
            "opinion_owner": "Unavailable", "opinion_signed_at": "Unavailable", "opinion_id": "",
            "renderer_version": (payload.get("renderer") or {}).get("version", ""),
        },
        "pages": pages,
        "disclosures": {},
    }


def publication_view(payload: dict[str, Any]) -> dict[str, Any]:
    publication = payload.get("publication") or _legacy_publication(payload)
    masthead = publication["masthead"]
    return {
        "masthead": masthead,
        "pages": publication["pages"],
        "disclosures": publication.get("disclosures") or {},
        "revision": [
            ("Deliverable", str(masthead.get("deliverable_id", ""))),
            ("Draft version", str(masthead.get("draft_version", ""))),
            ("Draft digest", str(masthead.get("draft_digest", ""))),
            ("Content digest", str(payload.get("preview_digest", ""))),
            ("Input fingerprint", str(masthead.get("input_fingerprint", ""))),
            ("Methodology build", str(masthead.get("methodology_build_id", ""))),
            ("Renderer", str(masthead.get("renderer_version", ""))),
        ],
    }


def _walk_sections(sections: list[dict[str, Any]], depth: int = 0):
    for section in sections:
        yield section, depth
        if section["kind"] == "columns":
            for column in section["items"]:
                yield from _walk_sections(column, depth + 1)


def _section_rows(section: dict[str, Any]) -> list[list[str]]:
    if section["kind"] == "table":
        return [list(section["columns"]), *[list(row) for row in section["rows"]]]
    if section["kind"] == "profile":
        return [[row["label"], row["value"]] for row in section["rows"]]
    if section["kind"] == "list":
        return [[item] for item in section["items"]]
    if section["kind"] == "chart":
        return [list(section["accessible_columns"]), *[list(row) for row in section["accessible_rows"]]]
    if section["kind"] == "text":
        return [[section["body"]]]
    return []


def _is_numeric(text: str) -> bool:
    return bool(_NUMERIC_CELL.match(text)) and any(ch.isdigit() for ch in text)


def _short_id(value: Any) -> str:
    """Masthead and footer lines show the first 16 characters of the deliverable
    id; the full id is in the Control Status and the Revision Record."""
    text = str(value or "")
    return text if len(text) <= 20 else text[:16] + "..."


def _masthead_line(masthead: dict[str, Any], page_name: str) -> str:
    # ASCII separators only: a middle dot falls back to a proportional font
    # inside monospace lines and breaks the column arithmetic.
    return " / ".join(str(part) for part in (
        "CAOS", str(masthead.get("pathway", "")).replace("_", " "), page_name.upper(),
        masthead.get("approval_state", PENDING_APPROVAL), f"AS OF {masthead.get('as_of_date', '')}",
        _short_id(masthead.get("deliverable_id", "")), f"DRAFT v{masthead.get('draft_version', '')}",
    ))


# --- Markdown --------------------------------------------------------------------


def _md_cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _md_section(section: dict[str, Any], depth: int, lines: list[str]) -> None:
    level = "#" * min(3 + depth, 6)
    lines.append(f"{level} {section['title']} · {_origin_label(section)}")
    kind = section["kind"]
    if kind == "columns":
        for column in section["items"]:
            for item in column:
                _md_section(item, depth + 1, lines)
        return
    rows = _section_rows(section)
    if kind in {"table", "chart"}:
        if kind == "chart":
            lines.append(f"Chart exhibit · {section.get('recipe', {}).get('chart_kind', 'chart')} · authoritative data table follows")
        header = rows[0]
        lines.append("| " + " | ".join(_md_cell(cell) for cell in header) + " |")
        lines.append("| " + " | ".join("---:" if all(_is_numeric(row[index]) for row in rows[1:] if index < len(row)) and len(rows) > 1 else "---" for index, _ in enumerate(header)) + " |")
        lines.extend("| " + " | ".join(_md_cell(cell) for cell in row) + " |" for row in rows[1:])
        if not rows[1:]:
            lines.append("_No rows._")
    elif kind == "profile":
        lines.extend(f"- **{_md_cell(label)}:** {_md_cell(value)}" for label, value in rows)
    elif kind == "list":
        lines.extend(f"- {_md_cell(row[0])}" for row in rows)
    else:
        lines.append(section["body"])
    if section.get("note"):
        lines.append(f"_{section['note']}_")
    lines.append("")


def render_frozen_markdown(payload: dict[str, Any]) -> bytes:
    view = publication_view(payload)
    masthead = view["masthead"]
    lines = [
        f"# {masthead.get('issuer', '')} — {masthead.get('report_type', '')}",
        "",
        _masthead_line(masthead, "MASTHEAD"),
        "",
        "| Field | Value |",
        "| --- | --- |",
        *[f"| {label} | {_md_cell(masthead.get(key, ''))} |" for label, key in MASTHEAD_FIELDS],
        "",
        f"> {masthead.get('watermark', PENDING_APPROVAL)} — the approver is recorded in the detached filing receipt, never in these bytes.",
        "",
    ]
    for index, page in enumerate(view["pages"], start=1):
        lines.append(f"## {page['name']} · Page {index} of {len(view['pages'])}")
        lines.append("")
        for section in page["sections"]:
            _md_section(section, 0, lines)
    lines.append("## Revision Record")
    lines.extend(f"- {label}: {value}" for label, value in view["revision"])
    return ("\n".join(lines) + "\n").encode("utf-8")
# --- END SHARED RENDERER ---


# --- audit chain (verbatim algorithm of caos/server/caos/audit/chain.py) ----------

GENESIS = "0" * 64
CHAIN_FIELDS = ("chain_key", "chain_seq", "id", "action", "actor", "at", "data", "prev_digest")


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def event_digest(row: dict[str, Any]) -> str:
    return hashlib.sha256(canonical({field: row[field] for field in CHAIN_FIELDS}).encode("utf-8")).hexdigest()


def verify_chain(rows: list[dict[str, Any]], head: dict[str, Any] | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    previous = GENESIS
    expected_seq = 1
    for row in rows:
        seq = row.get("chain_seq")
        if seq != expected_seq:
            findings.append({"code": "AUDIT_CHAIN_SEQUENCE_BROKEN", "chain_seq": seq, "expected": expected_seq})
            expected_seq = seq if isinstance(seq, int) else expected_seq
        if row.get("prev_digest") != previous:
            findings.append({"code": "AUDIT_CHAIN_LINK_BROKEN", "chain_seq": seq})
        try:
            recomputed = event_digest(row)
        except (KeyError, TypeError, ValueError):
            recomputed = None
        if recomputed != row.get("digest"):
            findings.append({"code": "AUDIT_EVENT_DIGEST_MISMATCH", "chain_seq": seq})
        previous = row.get("digest") if isinstance(row.get("digest"), str) else GENESIS
        expected_seq += 1
    if rows:
        last = rows[-1]
        if head is None or head.get("chain_seq") != last.get("chain_seq") or head.get("digest") != last.get("digest"):
            findings.append({"code": "AUDIT_CHAIN_HEAD_MISMATCH", "chain_seq": last.get("chain_seq")})
    elif head is not None:
        findings.append({"code": "AUDIT_CHAIN_HEAD_MISMATCH", "chain_seq": None})
    return findings


# --- the verifier ------------------------------------------------------------------


class Package:
    def __init__(self, path: str) -> None:
        self.archive = zipfile.ZipFile(path)
        self.names = set(self.archive.namelist())

    def bytes(self, name: str) -> bytes:
        return self.archive.read(name)

    def json(self, name: str) -> Any:
        return json.loads(self.bytes(name).decode("utf-8"))

    def jsonl(self, name: str) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.bytes(name).decode("utf-8").splitlines() if line.strip()]


def frozen_approval_digest(frozen: dict[str, Any]) -> str:
    return digest({
        "schema_version": "caos.frozen-approval.v1",
        "deliverable_id": frozen["deliverable_id"],
        "thread_id": frozen["thread_id"],
        "case_id": frozen["case_id"],
        "pathway": frozen["pathway"],
        "build_id": frozen["build_id"],
        "draft_version": frozen["draft_version"],
        "draft_digest": frozen["draft_digest"],
        "content_digest": frozen["payload"]["preview_digest"],
        "input_fingerprint": frozen["input_fingerprint"],
        "exports": frozen["exports"],
        "authority": frozen["authority"],
    })


OPINION_KEYS = (
    "opinion_id", "case_id", "pathway", "draft_id", "revision_id", "draft_version", "draft_digest",
    "binding", "opinion", "limitations", "material_overrides", "rationale", "supersedes_opinion_id",
    "signed_by", "signed_at", "opinion_digest",
)


def verify(path: str) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    checked: dict[str, int] = {}

    def finding(code: str, **detail: Any) -> None:
        findings.append({"code": code, **detail})

    package = Package(path)
    manifest = package.json("manifest.json")
    objects = manifest.get("objects") or {}
    # 1. every object named, present, digest and size exact; nothing extra.
    for name, meta in objects.items():
        if name not in package.names:
            finding("OBJECT_MISSING", path=name)
            continue
        content = package.bytes(name)
        if hashlib.sha256(content).hexdigest() != meta.get("sha256") or len(content) != meta.get("size"):
            finding("OBJECT_DIGEST_MISMATCH", path=name)
    for name in sorted(package.names - set(objects) - {"manifest.json"}):
        finding("OBJECT_UNDECLARED", path=name)
    if manifest.get("package_digest") != digest(objects):
        finding("PACKAGE_DIGEST_MISMATCH")
    checked["objects"] = len(objects)

    # 2. the audit chain.
    chain = package.jsonl("audit/events.jsonl") if "audit/events.jsonl" in package.names else []
    head = package.json("audit/head.json") if "audit/head.json" in package.names else None
    for item in verify_chain(chain, head):
        finding(**item)
    if manifest.get("audit_chain_head") != head:
        finding("AUDIT_CHAIN_HEAD_MISMATCH", chain_seq=None, detail="manifest head differs from audit/head.json")
    for row in chain:
        if row.get("chain_key") != manifest.get("case_id"):
            finding("AUDIT_CHAIN_FOREIGN_ROW", chain_seq=row.get("chain_seq"))
    checked["audit_events"] = len(chain)
    actions = {}
    for row in chain:
        actions.setdefault(row.get("action"), []).append(row)

    # 3. runs: plan and snapshot digests.
    for entry in package.json("runs/index.json") if "runs/index.json" in package.names else []:
        run_id = entry["run_id"]
        run = package.json(f"runs/{run_id}/run.json")
        if run.get("plan_digest") and digest(run.get("plan")) != run.get("plan_digest"):
            finding("RUN_PLAN_DIGEST_MISMATCH", run_id=run_id)
        for snapshot in package.json(f"runs/{run_id}/snapshot.json"):
            preimage = {key: value for key, value in snapshot.items() if key not in {"digest", "id"}}
            if digest(preimage) != snapshot.get("digest"):
                finding("SNAPSHOT_DIGEST_MISMATCH", run_id=run_id, snapshot_id=snapshot.get("id"))
        checked["runs"] = checked.get("runs", 0) + 1

    # 4. models: payload digests and published workbooks.
    builds = package.json("models/builds.json") if "models/builds.json" in package.names else []
    for build in builds:
        if build.get("payload") is not None and build.get("payload_digest") and digest(build["payload"]) != build["payload_digest"]:
            finding("MODEL_PAYLOAD_DIGEST_MISMATCH", build_id=build.get("id"))
    for entry in package.json("models/exports.json") if "models/exports.json" in package.names else []:
        if entry.get("problem"):
            finding("MODEL_EXPORT_" + entry["problem"], target_id=entry.get("target_id"))
        elif entry.get("path") in package.names and hashlib.sha256(package.bytes(entry["path"])).hexdigest() != entry.get("sha256"):
            finding("MODEL_EXPORT_DIGEST_MISMATCH", target_id=entry.get("target_id"))
    checked["model_builds"] = len(builds)

    # 5. deliverables: frozen records, opinions, receipts, filed bytes, reconstruction.
    frozen_records = package.json("deliverables/frozen.json") if "deliverables/frozen.json" in package.names else []
    opinions = {row["opinion_id"]: row for row in (package.json("deliverables/opinions.json") if "deliverables/opinions.json" in package.names else [])}
    receipts = {row["deliverable_id"]: row for row in (package.json("deliverables/receipts.json") if "deliverables/receipts.json" in package.names else [])}
    exports = package.json("deliverables/exports.json") if "deliverables/exports.json" in package.names else []
    sources = {row["id"]: row for row in (package.json("case/sources.json") if "case/sources.json" in package.names else [])}
    for row in opinions.values():
        if digest({key: row.get(key) for key in OPINION_KEYS if key != "opinion_digest"}) != row.get("opinion_digest"):
            finding("OPINION_DIGEST_MISMATCH", opinion_id=row.get("opinion_id"))
    reconstructed = 0
    for record in frozen_records:
        deliverable_id = record["deliverable_id"]
        payload = record.get("payload") or {}
        payload_preimage = {key: value for key, value in payload.items() if key != "preview_digest"}
        if digest(payload_preimage) != payload.get("preview_digest"):
            finding("FROZEN_CONTENT_DIGEST_MISMATCH", deliverable_id=deliverable_id)
        if frozen_approval_digest(record) != record.get("preview_digest"):
            finding("FROZEN_APPROVAL_DIGEST_MISMATCH", deliverable_id=deliverable_id)
        if record.get("draft_digest") != digest(payload.get("content")):
            finding("FROZEN_DRAFT_DIGEST_MISMATCH", deliverable_id=deliverable_id)
        opinion = opinions.get(record.get("opinion_id") or "")
        pinned = payload.get("opinion") or {}
        if opinion is None:
            finding("OPINION_MISSING", deliverable_id=deliverable_id)
        else:
            if opinion.get("draft_digest") != record.get("draft_digest") or opinion.get("signed_by") != record.get("signed_by"):
                finding("OPINION_BINDING_MISMATCH", deliverable_id=deliverable_id)
            if pinned.get("opinion_digest") != opinion.get("opinion_digest"):
                finding("OPINION_PAYLOAD_MISMATCH", deliverable_id=deliverable_id)
        masthead = (payload.get("publication") or {}).get("masthead") or {}
        if masthead.get("approval_state") != PENDING_APPROVAL:
            finding("FROZEN_BYTES_NAME_APPROVAL", deliverable_id=deliverable_id)
        for citation in payload.get("evidence") or []:
            source = sources.get(citation.get("source_id"))
            if source is None or source.get("sha256") != citation.get("sha256"):
                finding("EVIDENCE_SOURCE_MISMATCH", deliverable_id=deliverable_id, source_id=citation.get("source_id"))
            else:
                known = {block.get("block_id") for block in source.get("blocks") or []}
                if any(block_id not in known for block_id in citation.get("block_ids") or []):
                    finding("EVIDENCE_BLOCK_MISMATCH", deliverable_id=deliverable_id, source_id=citation.get("source_id"))
        # exports: exact bytes, and the Markdown reconstruction.
        for format_name, meta in (record.get("exports") or {}).items():
            entry = next((item for item in exports if item["deliverable_id"] == deliverable_id and item["format"] == format_name), None)
            if entry is None or entry.get("problem") or not entry.get("path"):
                finding("EXPORT_BYTES_MISSING", deliverable_id=deliverable_id, format=format_name)
                continue
            content = package.bytes(entry["path"])
            if hashlib.sha256(content).hexdigest() != meta.get("sha256") or len(content) != meta.get("size"):
                finding("EXPORT_DIGEST_MISMATCH", deliverable_id=deliverable_id, format=format_name)
            if format_name == "md":
                if render_frozen_markdown(payload) != content:
                    finding("MARKDOWN_RECONSTRUCTION_MISMATCH", deliverable_id=deliverable_id)
                else:
                    reconstructed += 1
                # a sampled claim: the first analyst text section reads back from the bytes
                text = content.decode("utf-8")
                for section, _depth in _walk_sections(publication_view(payload)["pages"][0]["sections"] if publication_view(payload)["pages"] else []):
                    if section.get("kind") == "text":
                        if section["body"] not in text:
                            finding("CLAIM_NOT_IN_EXPORT", deliverable_id=deliverable_id, section_id=section.get("section_id"))
                        break
        # filed: the receipt, the approver, the audit row.
        if record.get("filed_by"):
            receipt = receipts.get(deliverable_id)
            if receipt is None:
                finding("RECEIPT_MISSING", deliverable_id=deliverable_id)
            else:
                if digest({key: value for key, value in receipt.items() if key != "receipt_digest"}) != receipt.get("receipt_digest"):
                    finding("RECEIPT_DIGEST_MISMATCH", deliverable_id=deliverable_id)
                expected = {
                    "preview_digest": record.get("preview_digest"), "input_fingerprint": record.get("input_fingerprint"),
                    "opinion_id": record.get("opinion_id"), "signed_by": record.get("signed_by"),
                    "frozen_by": record.get("created_by"), "approved_by": record.get("filed_by"), "approved_at": record.get("filed_at"),
                    "exports": {fmt: meta["sha256"] for fmt, meta in sorted((record.get("exports") or {}).items())},
                    "approval_hash": f"sha256:{record.get('preview_digest')}",
                }
                for key, value in expected.items():
                    if receipt.get(key) != value:
                        finding("RECEIPT_FIELD_MISMATCH", deliverable_id=deliverable_id, field=key)
                if receipt.get("approved_by") in {receipt.get("signed_by"), receipt.get("frozen_by")}:
                    finding("APPROVER_NOT_INDEPENDENT", deliverable_id=deliverable_id)
                filed_rows = [row for row in actions.get("deliverable.filed", []) if (row.get("data") or {}).get("deliverable_id") == deliverable_id]
                if not any(row.get("actor") == receipt.get("approved_by") and (row.get("data") or {}).get("sha256") == receipt.get("receipt_digest") for row in filed_rows):
                    finding("FILING_AUDIT_ROW_MISSING", deliverable_id=deliverable_id)
        frozen_rows = [row for row in actions.get("deliverable.frozen", []) if (row.get("data") or {}).get("deliverable_id") == deliverable_id]
        if not any((row.get("data") or {}).get("preview_digest") == record.get("preview_digest") for row in frozen_rows):
            finding("FREEZE_AUDIT_ROW_MISSING", deliverable_id=deliverable_id)
    checked["frozen_deliverables"] = len(frozen_records)
    checked["markdown_reconstructed"] = reconstructed
    checked["receipts"] = len(receipts)
    return {"ok": not findings, "case_id": manifest.get("case_id"), "schema_version": manifest.get("schema_version"),
            "checked": checked, "findings": findings}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 2
    try:
        report = verify(argv[0])
    except (OSError, zipfile.BadZipFile, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "findings": [{"code": "PACKAGE_UNREADABLE", "detail": type(exc).__name__}]}))
        return 2
    if "--json" in argv[1:]:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"case {report['case_id']}: {'VERIFIED' if report['ok'] else 'FINDINGS'} · " + ", ".join(f"{key} {value}" for key, value in sorted(report["checked"].items())))
        for item in report["findings"]:
            print("  " + json.dumps(item, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
