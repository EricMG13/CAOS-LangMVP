"""Deterministic semantic document projection for deliverable previews and exports."""

from __future__ import annotations

import json
import math
import re
from itertools import batched
from typing import Any

from pydantic import TypeAdapter

from ..contracts import CanonicalDocumentSection
from ..artifacts.presentation import CURRENT_MAPPING_VERSION, PresentationError, _unit, project_artifact, project_model_outputs
from ..methodology.canonical import _scanned_lines, _sections, strip_provider_frontmatter
from .layouts import CHARTS_V2, LAYOUTS_V2, OPTIONAL_SECTIONS_V2, TEMPLATE_V2

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
    model_tables = [table]
    for effect_index, effect in enumerate((model or {}).get("pathway_effects") or [], 1):
        for calculation_index, calculation in enumerate(effect.get("calculations") or [], 1):
            calculator_id = str(calculation.get("calculator_id") or "calculation")
            calculation_rows = _model_rows(
                calculation.get("canonical_output") or {}, (calculator_id,),
            )
            for part, start in enumerate(range(0, len(calculation_rows), 500), 1):
                model_tables.append({
                    "kind": "table",
                    "section_id": _slug(
                        f"{section_id}_pathway_{effect_index}_{calculation_index}_{part}_{calculator_id}"
                    ),
                    "title": (
                        f"Calculated Pathway Effect · {calculator_id}"
                        + (f" · Part {part}" if len(calculation_rows) > 500 else "")
                    ),
                    "page": page,
                    "editable": False,
                    "origin": _origin("MODEL", authority_id),
                    "columns": ["Calculator / Field", "Value"],
                    "rows": calculation_rows[start:start + 500],
                    "note": "Deterministic pathway calculations pinned to the selected model authority.",
                })
    return {
        "kind": "columns",
        "section_id": section_id,
        "title": title,
        "page": page,
        "editable": False,
        "origin": _origin("MODEL" if model else "SYSTEM", authority_id),
        "items": [
            [_analyst_text(f"{section_id}_commentary", analyst_title, page, _required(by_title, title))],
            model_tables,
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
        if block["kind"] == "NARRATIVE":
            sections.append(_analyst_text(block["block_id"], f"Analyst commentary · {suffix}", "Commentary", block))
        elif block["kind"] == "GENERATED_METRIC":
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


def citation_union(blocks, sections, artifacts):
    """One union, retaining exact source/block pairs from validated envelopes.

    Bare origin block IDs are never paired across sources. A chart may narrow
    the artifact refs only by its declared sources and the origin block IDs.
    """
    citations = [citation for block in blocks for citation in block.get("citations", [])]
    by_id = {artifact.get("id"): artifact for artifact in artifacts.values()}
    for section in sections:
        origin = section["origin"]
        artifact = by_id.get(origin["authority_id"])
        if origin["kind"] != "ARTIFACT" or artifact is None:
            continue
        chart_sources = None
        if section["kind"] == "chart":
            chart_sources = {
                source
                for point in section["recipe"].get("points", [])
                for source in point["source_ids"]
            }
        for ref in (artifact.get("payload") or {}).get("evidence_refs", []):
            if ref["block_id"] not in origin["block_ids"]:
                continue
            if chart_sources is not None and ref["source_id"] not in chart_sources:
                continue
            citations.append({
                "source_id": ref["source_id"],
                "block_ids": [ref["block_id"]],
                "claim": "Accepted module evidence",
            })
    grouped = {}
    for citation in citations:
        key = citation["source_id"], citation["claim"]
        grouped.setdefault(key, set()).update(citation["block_ids"])
    return [
        {"source_id": source, "block_ids": sorted(ids), "claim": claim}
        for (source, claim), ids in sorted(grouped.items())
    ]


def _report_evidence_sections(citations, authority_id):
    """Bound v2 display sections, never the authoritative citation union."""
    register = _evidence_section([{"citations": citations}], authority_id)
    if len(register["origin"]["block_ids"]) <= 500 and len(register["rows"]) <= 500:
        return [register]

    # One reference per entry bounds both distinct origin IDs and table rows.
    single_reference_blocks = (
        {"citations": [{**citation, "block_ids": [block_id]}]}
        for citation in citations
        for block_id in citation["block_ids"]
    )
    sections = []
    for section_number, batch in enumerate(batched(single_reference_blocks, 500), 1):
        batch_citations = citation_union(batch, [], {})
        section = _evidence_section([{"citations": batch_citations}], authority_id)
        if section_number > 1:
            section["section_id"] = f"evidence_register.{section_number}"
            section["title"] = "Evidence Register · continued"
        sections.append(section)
    return sections


def document_blockers(sections):
    return [{"code": "REPORT_INPUT_UNAVAILABLE", "section_id": s["section_id"], "detail": s["body"]}
            for s in sections if s["origin"]["kind"] == "SYSTEM" and s["section_id"].endswith(".unavailable")]


def _report_narrative(artifact, selector):
    heading, _, subsection = selector[1:].partition("/")
    body = _sections(strip_provider_frontmatter(artifact.get("markdown") or "")).get(heading, "")
    if artifact["module_id"] == "CP-DR" and heading == "Analysis":
        # Exact module-owned subsection, never a second synthesis or a duplicate
        # Findings paragraph relabelled as Implications.
        headings = []
        offset = 0
        for raw_line, line, visible in _scanned_lines(body):
            if visible and (match := re.fullmatch(r" {0,3}### +(.+?)(?: +#+)? *", line)):
                headings.append((match[1].strip(), offset, offset + len(raw_line)))
            offset += len(raw_line)
        implications = [(start, content, headings[index + 1][1] if index + 1 < len(headings) else len(body))
                        for index, (title, start, content) in enumerate(headings) if title.casefold() in {"implications", "implications and scenarios"}]
        if len(implications) != 1:
            body = "" if subsection else body
        else:
            start, content, end = implications[0]
            body = body[content:end] if subsection else body[:start] + body[end:]
        # Generated module prose keeps heading words, not literal Markdown
        # decoration. Analyst plain-text overlays never pass through here.
        return "".join(re.sub(r"^ {0,3}#{1,6} +(.+?)(?: +#+)?[ \t]*(\r?\n|$)", r"\1\2", raw) if visible else raw
                       for raw, _, visible in _scanned_lines(body)).strip()
    if artifact["module_id"] != "CP-DR":
        body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith(("|", "<!-- table-id:", "#"))).strip()
    return body


def _module_document(pathway, blocks, artifacts, model, mapping_version, included_optional_section_ids):
    presentations = {module: project_artifact(artifact, mapping_version=mapping_version).model_dump()
                   for module, artifact in artifacts.items() if not module.startswith("__")}
    projections = {module: p["sections"] for module, p in presentations.items()}
    period_tables = [s for s in projections.get("CP-1", []) if s["kind"] == "table" and s["title"] in {"cp1.model_period_register", "T4.14"}]
    try:
        model_unit = _unit([dict(zip(s["columns"], row, strict=True)) for s in period_tables for row in s["rows"]])
    except PresentationError:
        model_unit = ""  # Shared projector emits UNIT_MISMATCH beside the exact model table.
    result = []
    used = set()
    layout = list(LAYOUTS_V2[pathway])
    if model and pathway in {"RELATIVE_VALUE", "DEEP_RESEARCH"}:
        layout.append(("model_effects", "Selected model and pathway effects", [("MODEL", "outputs")]))
    for optional in OPTIONAL_SECTIONS_V2:
        if optional["section_id"] in included_optional_section_ids:
            layout.append((optional["section_id"], optional["title"], [(optional["module_id"], optional["selector"])]))
    for slot_id, title, bindings in layout:
        for index, (module, selector) in enumerate(bindings):
            section_id = f"report.{slot_id}.{index}"
            artifact = artifacts.get(module)
            selected = []
            if module == "MODEL" and model:
                authority = _model_authority(model)
                effects = model.get("pathway_effects") or []
                model_title = "Selected model outputs"
                model_note = "Locked to the selected model authority."
                if effects:
                    model_title = ("Signed-Off Revision outputs" if model["kind"] == "ANALYST_REVISION"
                                   else "Unchanged prior-model base values")
                    model_note = (
                        "Outputs reflect the selected analyst assumptions on the inherited Full Credit model. "
                        if model["kind"] == "ANALYST_REVISION" else
                        "The application overlay inherits the prior Full Credit worksheet unchanged. "
                    ) + "Accepted pathway effects are shown separately; they do not recalculate the complete forecast."
                    selected.append({"kind": "text", "section_id": f"{section_id}.scope", "title": model_title,
                                     "page": title, "editable": False, "origin": _origin("MODEL", authority), "body": model_note})
                rows = _model_rows(model.get("outputs") or {})
                for offset in range(0, len(rows), 500):
                    selected.append({"kind": "table", "section_id": f"{section_id}.{offset // 500}", "title": model_title, "page": title,
                                     "editable": False, "origin": _origin("MODEL", authority), "columns": ["Case / Period / Metric", "Value"],
                                     "rows": rows[offset:offset + 500], "note": model_note})
                selection = {"kind": model["kind"], "build_id": model["build_id"]}
                selection.update({"revision_id": model["revision_id"]} if model["kind"] == "ANALYST_REVISION" else {"fallback_acknowledged": True})
                model_presentation = project_model_outputs(selection=selection, outputs=model.get("outputs") or {}, unit=model_unit, mapping_version=mapping_version).model_dump()
                selected.extend(model_presentation["sections"])
                for unavailable in model_presentation["unavailable"]:
                    selected.append({"kind": "text", "section_id": unavailable["view_id"] + ".warning", "title": "Chart unavailable · exact model table retained", "page": title,
                                     "editable": False, "origin": _origin("SYSTEM", authority), "body": f"{unavailable['view_id']}: {unavailable['code']}. No unit or missing value has been inferred."})
                for effect_index, effect in enumerate(effects):
                    selected.append({"kind": "text", "section_id": f"{section_id}.effect.{effect_index}.scope",
                                     "title": "Accepted pathway effect scope", "page": title, "editable": False,
                                     "origin": _origin("MODEL", authority), "body": effect.get("scope") or model_note})
                    for field in ("period_updates", "forecast_variance", "covenant_updates", "refinancing_updates", "assumption_updates", "market_marks", "time_alignment", "numeric_effect", "limitations"):
                        if field not in effect:
                            continue
                        rows = _model_rows(effect[field])
                        for offset in range(0, len(rows), 500):
                            selected.append({"kind": "table", "section_id": f"{section_id}.effect.{effect_index}.{field}.{offset // 500}",
                                             "title": f"Accepted pathway effect · {field}", "page": title, "editable": False,
                                             "origin": _origin("MODEL", authority), "columns": ["Field", "Value"], "rows": rows[offset:offset + 500], "note": None})
                    for calc_index, calculation in enumerate(effect.get("calculations") or []):
                        rows = _model_rows(calculation.get("canonical_output") or {})
                        for offset in range(0, len(rows), 500):
                            selected.append({"kind": "table", "section_id": f"{section_id}.effect.{effect_index}.{calc_index}.{offset // 500}",
                                             "title": f"Accepted pathway effect · {calculation['calculator_id']}", "page": title, "editable": False,
                                             "origin": _origin("MODEL", authority), "columns": ["Field", "Value"], "rows": rows[offset:offset + 500], "note": None})
                if pathway in {"EARNINGS_UPDATE", "COVENANT_REFINANCING"} and not effects:
                    selected.append({"kind": "text", "section_id": f"{section_id}.effect.unavailable", "title": "Unavailable · accepted pathway model effects",
                                     "page": title, "editable": False, "origin": _origin("SYSTEM", authority),
                                     "body": "Accepted incremental effects are unavailable. A validated accepted pathway overlay is required."})
            elif artifact and selector.startswith("@") and projections.get(module):
                body = _report_narrative(artifact, selector)
                for offset in range(0, len(body), 20_000):
                    selected.append({"kind": "text", "section_id": f"{section_id}.{offset // 20_000}", "title": f"{module} · {selector[1:]}", "page": title,
                                     "editable": False, "origin": projections[module][0]["origin"],
                                     "body": body[offset:offset + 20_000]})
            else:
                for alias in selector.split("|"):
                    selected = [s for s in projections.get(module, []) if (s["kind"] == "table" and s["title"] == alias) or s["section_id"] == f"{module}.{alias}"]
                    if selected:
                        selected.extend(s for s in projections.get(module, []) if s["kind"] == "chart" and s["section_id"] == f"{module}.{alias}.v1")
                        break
            if not selected:
                selected = [{"kind": "text", "section_id": f"{section_id}.unavailable", "title": f"Unavailable · {title}", "page": title,
                             "editable": False, "origin": _origin("SYSTEM", _artifact_authority(artifacts)),
                             "body": f"Required input unavailable: {module} / {selector}. Inspect accepted analysis and its source coverage."}]
            for section in selected:
                if section["section_id"] not in used:
                    result.append({**section, "page": title})
                    used.add(section["section_id"])
        for module_sections in projections.values():
            for section in module_sections:
                if section["kind"] == "chart" and any(section["section_id"] == prefix or section["section_id"].startswith(prefix + ".") for prefix in CHARTS_V2.get(slot_id, ())):
                    if section["section_id"] not in used:
                        result.append({**section, "page": title})
                        used.add(section["section_id"])
        for presentation in presentations.values():
            for unavailable in presentation["unavailable"]:
                if any(unavailable["view_id"] == prefix or unavailable["view_id"].startswith(prefix + ".") for prefix in CHARTS_V2.get(slot_id, ())):
                    result.append({"kind": "text", "section_id": unavailable["view_id"] + ".warning", "title": "Chart unavailable · source table retained", "page": title,
                                   "editable": False, "origin": _origin("SYSTEM", presentation["artifact_id"]), "body": f"{unavailable['view_id']}: {unavailable['code']}. Inspect the exact module table for available values."})
    for optional in OPTIONAL_SECTIONS_V2:
        if optional["section_id"] not in included_optional_section_ids:
            result.append({"kind": "text", "section_id": f"report.{optional['section_id']}.omitted", "title": f"Omitted · {optional['title']}", "page": "Limitations",
                           "editable": False, "origin": _origin("SYSTEM", _artifact_authority(artifacts)), "body": optional["omission_reason"]})
    result.extend(_appendix_sections(blocks[1:], model))
    result.extend(_report_evidence_sections(citation_union(blocks, result, artifacts), _artifact_authority(artifacts)))
    return result


def compose_document(
    *,
    pathway: str,
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
    mapping_version: str | None = None,
    included_optional_section_ids: list[str] | None = None,
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
    if template["template_version"] == TEMPLATE_V2:
        raw = _module_document(pathway, blocks, artifacts, model, mapping_version or CURRENT_MAPPING_VERSION, included_optional_section_ids or [])
    else:
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
