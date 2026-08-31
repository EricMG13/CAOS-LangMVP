"""Deterministic semantic document projection for deliverable previews and exports."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from pydantic import TypeAdapter

from ..contracts import CanonicalDocumentSection

DOCUMENT_SCHEMA_VERSION = "caos.deliverable.document.v1"
_DOCUMENT_ADAPTER = TypeAdapter(list[CanonicalDocumentSection])


def _display(value: Any) -> str:
    if value is None or value == "":
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return format(value, ",.12g") if math.isfinite(value) else "Unavailable"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")[:120] or "section"


def _origin(kind: str, authority_id: str, block_ids: list[str] | None = None) -> dict[str, Any]:
    return {"kind": kind, "authority_id": authority_id, "block_ids": list(dict.fromkeys(block_ids or []))}


def _citation_block_ids(block: dict[str, Any]) -> list[str]:
    return [
        block_id
        for citation in block.get("citations") or []
        for block_id in citation.get("block_ids") or []
    ]


def _analyst_text(section_id: str, title: str, page: str, block: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "text",
        "section_id": section_id,
        "title": title,
        "page": page,
        "editable": True,
        "origin": _origin("ANALYST", block["block_id"], _citation_block_ids(block)),
        "body": block["text"],
    }


def _artifact_summary_rows(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for module_id, artifact in artifacts.items():
        if module_id.startswith("__"):
            continue
        payload = artifact.get("payload") or {}
        narrative = payload.get("narrative") if isinstance(payload, dict) else None
        summary = payload.get("summary") if isinstance(payload, dict) else None
        if not summary and isinstance(narrative, dict):
            summary = narrative.get("takeaway")
        rows.append({"label": module_id, "value": _display(summary or "Governed output pinned")})
    return rows


def _model_rows(value: Any, prefix: tuple[str, ...] = ()) -> list[list[str]]:
    if isinstance(value, dict):
        return [
            row
            for key, child in value.items()
            for row in _model_rows(child, (*prefix, str(key)))
        ]
    if isinstance(value, list):
        return [
            row
            for index, child in enumerate(value, start=1)
            for row in _model_rows(child, (*prefix, str(index)))
        ]
    return [[" / ".join(prefix) or "Value", _display(value)]]


def _evidence_section(blocks: list[dict[str, Any]], authority_id: str) -> dict[str, Any]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    rows: list[list[str]] = []
    block_ids: list[str] = []
    for block in blocks:
        for citation in block.get("citations") or []:
            evidence_ids = tuple(citation.get("block_ids") or [])
            key = (citation["source_id"], evidence_ids, citation.get("claim") or "")
            if key in seen:
                continue
            seen.add(key)
            block_ids.extend(evidence_ids)
            rows.append([citation["source_id"], ", ".join(evidence_ids), citation.get("claim") or "Pinned evidence"])
    return {
        "kind": "table",
        "section_id": "evidence_register",
        "title": "Evidence Register",
        "page": "Evidence",
        "editable": False,
        "origin": _origin("ARTIFACT", authority_id, block_ids),
        "columns": ["Source", "Blocks", "Claim"],
        "rows": rows,
        "note": None,
    }


def _full_credit(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = {
        definition["title"]: block
        for definition, block in zip(template["blocks"], blocks[:len(template["blocks"])], strict=True)
        if block["kind"] == "NARRATIVE"
    }
    artifact_authority = (artifacts.get("__authority__") or {}).get("id") or "analysis-pending"
    model_authority = (
        (model or {}).get("revision_id")
        or (model or {}).get("build_id")
        or "model-unavailable"
    )
    snapshot_block = by_title["Credit Snapshot"]
    artifact_rows = _artifact_summary_rows(artifacts)
    snapshot_profile = {
        "kind": "profile",
        "section_id": "credit_snapshot_authority",
        "title": "Accepted Analysis",
        "page": "Decision",
        "editable": False,
        "origin": _origin("ARTIFACT", artifact_authority),
        "rows": artifact_rows or [{"label": "Snapshot", "value": artifact_authority}],
    }
    model_rows = _model_rows((model or {}).get("outputs") or {})[:500]
    model_table = {
        "kind": "table",
        "section_id": "base_downside_model_outputs",
        "title": "Calculated Base and Downside Outputs",
        "page": "Financials",
        "editable": False,
        "origin": _origin("MODEL" if model else "SYSTEM", model_authority),
        "columns": ["Case / Period / Metric", "Value"],
        "rows": model_rows or [["Model outputs", "Unavailable"]],
        "note": "Generated values are locked to the selected model authority.",
    }
    sections = [
        {
            "kind": "columns",
            "section_id": "credit_snapshot",
            "title": "Credit Snapshot",
            "page": "Decision",
            "editable": False,
            "origin": _origin("ARTIFACT", artifact_authority),
            "items": [[snapshot_profile], [_analyst_text("credit_snapshot_commentary", "Analyst Snapshot", "Decision", snapshot_block)]],
        },
        _analyst_text("recommendation", "Recommendation", "Decision", by_title["Recommendation"]),
        _analyst_text("thesis_variant", "Thesis and Variant View", "Decision", by_title["Thesis and Variant View"]),
        _analyst_text("business_industry", "Business and Industry", "Business", by_title["Business and Industry"]),
        _analyst_text("capital_structure", "Capital Structure", "Financials", by_title["Capital Structure"]),
        {
            "kind": "columns",
            "section_id": "base_downside_model",
            "title": "Base and Downside Model",
            "page": "Financials",
            "editable": False,
            "origin": _origin("MODEL" if model else "SYSTEM", model_authority),
            "items": [[_analyst_text("base_downside_commentary", "Analyst Model View", "Financials", by_title["Base and Downside Model"])], [model_table]],
        },
        _analyst_text("liquidity_covenants", "Liquidity and Covenants", "Financials", by_title["Liquidity and Covenants"]),
        _analyst_text("risks_catalysts_falsifiers", "Risks, Catalysts, and Falsifiers", "Risk", by_title["Risks, Catalysts, and Falsifiers"]),
        _analyst_text("monitoring", "Monitoring", "Risk", by_title["Monitoring"]),
        _evidence_section(blocks, artifact_authority),
    ]
    return sections


def _template_document(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    artifact_authority = (artifacts.get("__authority__") or {}).get("id") or "analysis-pending"
    sections: list[dict[str, Any]] = []
    for definition, block in zip(template["blocks"], blocks[:len(template["blocks"])], strict=True):
        if block["kind"] == "NARRATIVE":
            sections.append(_analyst_text(_slug(definition["title"]), definition["title"], "Analysis", block))
    sections.append(_evidence_section(blocks, artifact_authority))
    return sections


def compose_document(
    *,
    pathway: str,
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Return the one validated, JSON-ready document used by every consumer."""
    raw = (
        _full_credit(template, blocks, artifacts, model)
        if pathway == "FULL_CREDIT"
        else _template_document(template, blocks, artifacts)
    )
    validated = _DOCUMENT_ADAPTER.validate_python(raw)
    return _DOCUMENT_ADAPTER.dump_python(validated, mode="json")
