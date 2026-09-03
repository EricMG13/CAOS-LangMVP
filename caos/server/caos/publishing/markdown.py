"""Markdown export and the shared publication projection (Task 10).

Standard library only and free of intra-package imports on purpose: the
offline audit-package verifier (`caos/server/caos/audit/verify_package.py`)
carries a verbatim copy of everything between the BEGIN/END markers below so a
reviewer can re-render the Markdown export from a frozen payload with no
application import, and `test_audit_package_spec.py` pins the two copies
byte-equal. Change this file and the verifier together.
"""

from __future__ import annotations

import re
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
