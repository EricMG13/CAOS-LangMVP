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
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
            for row in _model_rows(child, (*prefix, str(key)))
        ]
    if isinstance(value, list):
        return [
            row
            for index, child in enumerate(value, start=1)
            for row in _model_rows(child, (*prefix, str(index)))
        ]
    return [[" / ".join(prefix) or "Value", _display(value)]]


def model_metric_values(outputs: dict[str, Any], metric: str) -> Any:
    if metric in outputs:
        return outputs[metric]
    return {
        case: {
            period: period_values[metric]
            for period, period_values in case_values.items()
            if isinstance(period_values, dict) and metric in period_values
        }
        for case, case_values in outputs.items()
        if isinstance(case_values, dict)
    }


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


def _narratives(template: dict[str, Any], blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        definition["title"]: block
        for definition, block in zip(template["blocks"], blocks[:len(template["blocks"])], strict=True)
        if block["kind"] == "NARRATIVE"
    }


def _required(by_title: dict[str, dict[str, Any]], title: str) -> dict[str, Any]:
    return by_title[title]


def _artifact_authority(artifacts: dict[str, dict[str, Any]]) -> str:
    return (artifacts.get("__authority__") or {}).get("id") or "analysis-pending"


def _model_authority(model: dict[str, Any] | None) -> str:
    return (model or {}).get("revision_id") or (model or {}).get("build_id") or "model-unavailable"


def _accepted_analysis(
    artifacts: dict[str, dict[str, Any]], page: str, *, section_id: str = "accepted_analysis",
) -> dict[str, Any]:
    authority_id = _artifact_authority(artifacts)
    rows = _artifact_summary_rows(artifacts)
    return {
        "kind": "profile",
        "section_id": section_id,
        "title": "Accepted Analysis",
        "page": page,
        "editable": False,
        "origin": _origin("ARTIFACT", authority_id),
        "rows": rows or [{"label": "Snapshot", "value": authority_id}],
    }


def _snapshot_section(
    by_title: dict[str, dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    *,
    title: str,
    page: str,
    analyst_title: str,
) -> dict[str, Any]:
    section_id = _slug(title)
    authority_id = _artifact_authority(artifacts)
    return {
        "kind": "columns",
        "section_id": section_id,
        "title": title,
        "page": page,
        "editable": False,
        "origin": _origin("ARTIFACT", authority_id),
        "items": [
            [_accepted_analysis(artifacts, page)],
            [_analyst_text(f"{section_id}_commentary", analyst_title, page, _required(by_title, title))],
        ],
    }


def _model_section(
    by_title: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
    *,
    title: str,
    page: str,
    analyst_title: str,
    table_title: str,
) -> dict[str, Any]:
    section_id = _slug(title)
    authority_id = _model_authority(model)
    rows = _model_rows((model or {}).get("outputs") or {})[:500]
    table = {
        "kind": "table",
        "section_id": f"{section_id}_outputs",
        "title": table_title,
        "page": page,
        "editable": False,
        "origin": _origin("MODEL" if model else "SYSTEM", authority_id),
        "columns": ["Case / Period / Metric", "Value"],
        "rows": rows or [["Model outputs", "Unavailable"]],
        "note": "Generated values are locked to the selected model authority.",
    }
    return {
        "kind": "columns",
        "section_id": section_id,
        "title": title,
        "page": page,
        "editable": False,
        "origin": _origin("MODEL" if model else "SYSTEM", authority_id),
        "items": [
            [_analyst_text(f"{section_id}_commentary", analyst_title, page, _required(by_title, title))],
            [table],
        ],
    }


def _analyst_section(
    by_title: dict[str, dict[str, Any]], title: str, page: str,
) -> dict[str, Any]:
    return _analyst_text(_slug(title), title, page, _required(by_title, title))


def _full_credit(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    artifact_authority = _artifact_authority(artifacts)
    model_authority = _model_authority(model)
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


def compose_earnings_update(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    return [
        _snapshot_section(by_title, artifacts, title="Credit Snapshot", page="Decision", analyst_title="Analyst Snapshot"),
        _analyst_section(by_title, "What Changed", "Decision"),
        _analyst_section(by_title, "Reported Versus Prior Bridge", "Performance"),
        _model_section(
            by_title, model, title="Model Impact", page="Model",
            analyst_title="Analyst Model Impact", table_title="Calculated Model Impact",
        ),
        _analyst_section(by_title, "Leverage and Liquidity", "Model"),
        _analyst_section(by_title, "Thesis and Recommendation Impact", "View"),
        _analyst_section(by_title, "Risks, Catalysts, and Monitoring", "View"),
        _evidence_section(blocks, _artifact_authority(artifacts)),
    ]


def compose_covenant_refinancing(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    return [
        _snapshot_section(by_title, artifacts, title="Credit Snapshot", page="Decision", analyst_title="Analyst Snapshot"),
        _analyst_section(by_title, "Capital Structure and Maturity Wall", "Capital"),
        _analyst_section(by_title, "Covenant Definitions and Headroom", "Capital"),
        _analyst_section(by_title, "Liquidity", "Liquidity"),
        _analyst_section(by_title, "Refinancing Options", "Liquidity"),
        _model_section(
            by_title, model, title="Base and Downside Breakpoints", page="Downside",
            analyst_title="Analyst Breakpoint View", table_title="Calculated Base and Downside Breakpoints",
        ),
        _analyst_section(by_title, "Actions and Monitoring", "Actions"),
        _evidence_section(blocks, _artifact_authority(artifacts)),
    ]


def compose_relative_value(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    _model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    return [
        _snapshot_section(by_title, artifacts, title="Credit Snapshot", page="Decision", analyst_title="Analyst Snapshot"),
        _analyst_section(by_title, "Instrument Comparison", "Comparison"),
        _analyst_section(by_title, "Structure and Seniority", "Comparison"),
        _analyst_section(by_title, "Relative Compensation", "Comparison"),
        _analyst_section(by_title, "Catalysts and Risks", "Risk"),
        _analyst_section(by_title, "Recommendation and Trade Gates", "Trade"),
        _analyst_section(by_title, "Market Freshness", "Trade"),
        _evidence_section(blocks, _artifact_authority(artifacts)),
    ]


def compose_distressed_restructuring(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    return [
        _snapshot_section(by_title, artifacts, title="Credit Snapshot", page="Decision", analyst_title="Analyst Snapshot"),
        _analyst_section(by_title, "Capital Structure and Priority", "Capital"),
        _analyst_section(by_title, "Liquidity Runway", "Capital"),
        _model_section(
            by_title, model, title="Base, Downside, and Scenario Exhibits", page="Scenarios",
            analyst_title="Analyst Scenario View", table_title="Calculated Base, Downside, and Scenario Outputs",
        ),
        _analyst_section(by_title, "Recovery", "Scenarios"),
        _analyst_section(by_title, "Covenant, Default, and Refinancing Milestones", "Milestones"),
        _analyst_section(by_title, "Catalysts and Process Risks", "Milestones"),
        _analyst_section(by_title, "Recommendation", "Recommendation"),
        _evidence_section(blocks, _artifact_authority(artifacts)),
    ]


def compose_deep_research(
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    _model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    by_title = _narratives(template, blocks)
    return [
        _snapshot_section(
            by_title, artifacts, title="Research Question and Scope", page="Scope", analyst_title="Analyst Scope",
        ),
        _analyst_section(by_title, "Executive Findings", "Findings"),
        _analyst_section(by_title, "Evidence Synthesis", "Evidence"),
        _analyst_section(by_title, "Counterevidence and Gaps", "Evidence"),
        _analyst_section(by_title, "Implications for Thesis, Model, and Recommendation", "Implications"),
        _analyst_section(by_title, "Unresolved Questions", "Implications"),
        {**_evidence_section(blocks, _artifact_authority(artifacts)), "page": "Sources"},
    ]


def _appendix_sections(
    blocks: list[dict[str, Any]], model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    authority_id = _model_authority(model)
    outputs = (model or {}).get("outputs") or {}
    for block in blocks:
        suffix = block["slot_id"].rsplit(".", 1)[-1]
        origin = _origin("MODEL", authority_id)
        common = {
            "section_id": block["block_id"],
            "page": "Appendix",
            "editable": False,
            "origin": origin,
        }
        if block["kind"] == "GENERATED_METRIC":
            sections.append({
                **common,
                "kind": "table",
                "title": f"Generated Metrics · {suffix}",
                "columns": ["Metric / Case / Period", "Value"],
                "rows": _model_rows(block.get("values") or {})[:500],
                "note": "Generated values are locked to the selected model authority.",
            })
        elif block["kind"] == "GENERATED_TABLE":
            fields = block["field_ids"]
            if block["table_id"] == "annual_model":
                columns = ["Case", "Period", *(field.replace("_", " ").title() for field in fields)]
                rows = [
                    [_display(case), _display(period.rsplit("::", 1)[-1]), *(_display(record.get(field)) for field in fields)]
                    for case, case_values in sorted(outputs.items())
                    if isinstance(case_values, dict)
                    for period, record in sorted(case_values.items())
                    if isinstance(record, dict)
                ][:500]
            else:
                value = outputs.get(block["table_id"])
                records = value if isinstance(value, list) else list(value.values()) if isinstance(value, dict) and all(isinstance(row, dict) for row in value.values()) else [value] if isinstance(value, dict) else []
                columns = [field.replace("_", " ").title() for field in fields]
                rows = [[_display(record.get(field)) for field in fields] for record in records[:500]]
            sections.append({
                **common,
                "kind": "table",
                "title": f"{block['table_id'].replace('_', ' ').title()} · {suffix}",
                "columns": columns,
                "rows": rows,
                "note": "Generated rows are locked to the selected model authority.",
            })
        elif block["kind"] == "GENERATED_CHART":
            values = {field: model_metric_values(outputs, field) for field in block["recipe"]["fields"]}
            sections.append({
                **common,
                "kind": "chart",
                "title": f"Generated Chart · {suffix}",
                "recipe": block["recipe"],
                "accessible_columns": ["Metric / Case / Period", "Value"],
                "accessible_rows": _model_rows(values)[:500],
            })
        elif block["kind"] == "SCENARIO_EXHIBIT":
            sections.append({
                **common,
                "kind": "chart",
                "title": block["title"],
                "origin": _origin("MODEL", block["scenario_digest"]),
                "recipe": {"chart_kind": "scenario", "shocks": block["shocks"]},
                "accessible_columns": ["Scenario / Metric", "Value"],
                "accessible_rows": _model_rows(block["scenario"].get("outputs") or {})[:500],
            })
        elif block["kind"] == "MODEL_APPENDIX":
            sections.append({
                **common,
                "kind": "table",
                "title": "Model Appendix",
                "columns": ["Case / Period / Metric", "Value"],
                "rows": _model_rows(outputs)[:500],
                "note": "Complete calculated output projection for review.",
            })
        elif block["kind"] == "LIMITATIONS":
            sections.append({
                **common,
                "kind": "text",
                "title": f"Limitations · {suffix}",
                "editable": True,
                "origin": _origin("ANALYST", block["block_id"], _citation_block_ids(block)),
                "body": block["text"],
            })
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
    composers = {
        "FULL_CREDIT": _full_credit,
        "EARNINGS_UPDATE": compose_earnings_update,
        "COVENANT_REFINANCING": compose_covenant_refinancing,
        "RELATIVE_VALUE": compose_relative_value,
        "DISTRESSED_RESTRUCTURING": compose_distressed_restructuring,
        "DEEP_RESEARCH": compose_deep_research,
    }
    raw = composers[pathway](template, blocks, artifacts, model)
    evidence = raw.pop()
    raw.extend(_appendix_sections(blocks[len(template["blocks"]):], model))
    raw.append(evidence)
    pending = list(raw)
    section_ids: list[str] = []
    while pending:
        section = pending.pop()
        section_ids.append(section["section_id"])
        if section["kind"] == "columns":
            pending.extend(item for column in section["items"] for item in column)
    if len(section_ids) != len(set(section_ids)):
        raise ValueError("DELIVERABLE_SECTION_ID_DUPLICATE: canonical section ids must be unique")
    validated = _DOCUMENT_ADAPTER.validate_python(raw)
    return _DOCUMENT_ADAPTER.dump_python(validated, mode="json")
