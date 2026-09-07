"""Host-owned presentation of already validated artifacts; no execution authority.

Callers must complete artifact/snapshot or selected-model validation first. V1
is immutable: saved documents dispatch with their recorded mapping version.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from ..contracts import ChartRecipe, DocumentChartSection, finite_or_none
from ..methodology.canonical import _scanned_lines, _table_cells, _top_level, strip_provider_frontmatter
from ..responses import ModelPresentationResponse, ModulePresentationResponse
from .presentation_bindings import BINDINGS_V1

CURRENT_MAPPING_VERSION = "caos.module-presentation.v1"
_MARKER = re.compile(r"^\s*<!--\s*table-id:\s*([a-zA-Z0-9_.-]+)\s*-->\s*$")
_TABLE_HEADING = re.compile(r"^#{1,6}\s+(T(?:L)?\d+[A-Z]?(?:\.[0-9A-Z]+)?|P\d+)(?=\s|[:.—-]|$)")
_NAMED_TABLES = {name for _, names, _, _ in BINDINGS_V1 for name in names}
_CP1_ALIASES = dict(zip(
    (f"T4.{n}" for n in range(14, 20)),
    ("cp1.model_period_register", "cp1.model_account_register", "cp1.segment_revenue_schedule",
     "cp1.adjusted_ebitda_bridge", "cp1.debt_facility_register", "cp1.model_reconciliation_register"), strict=True,
))


class PresentationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def read_tables(markdown: str) -> tuple[dict[str, tuple[list[str], list[list[str]]]], list[dict[str, str]]]:
    """Read visible GFM tables once, retaining exact cells and rejecting ambiguity."""
    records = enumerate(_scanned_lines(markdown), start=1)
    current = next(records, None)
    tables = {}
    failures = {}
    seen = set()
    pending = None
    pending_is_heading = False
    while current is not None:
        line_number, (raw, line, visible) = current
        marker = _MARKER.fullmatch(raw.rstrip("\r\n"))
        heading = _TABLE_HEADING.match(line)
        named = re.sub(r"^#{1,6}\s+", "", line).strip()
        identity = marker.group(1) if marker else heading.group(1) if heading else named if named in _NAMED_TABLES else None
        if identity is not None:
            if len(identity) > 90:
                identity = f"table_{line_number}"
                failures[identity] = "TABLE_MALFORMED"
            same_heading = marker is not None and pending_is_heading and pending == identity
            if pending and pending != identity and _CP1_ALIASES.get(pending) != identity:
                failures.setdefault(pending, "TABLE_MISSING")
            if identity in seen and not same_heading:
                failures[identity] = "DUPLICATE_ID"
                tables.pop(identity, None)
            seen.add(identity)
            pending = identity
            pending_is_heading = marker is None
            if not visible or not _top_level(line):
                failures[identity] = "TABLE_HIDDEN"
            current = next(records, None)
            continue
        columns = _table_cells(line) if visible and _top_level(line) else None
        if columns is None:
            if raw.strip() and pending:
                failures.setdefault(pending, "TABLE_MISSING")
                pending = None
            current = next(records, None)
            continue
        table_id = pending or f"table_{line_number}"
        if pending is None:
            if table_id in seen:
                failures[table_id] = "DUPLICATE_ID"
                tables.pop(table_id, None)
            seen.add(table_id)
        pending = None
        current = next(records, None)
        separator = _table_cells(current[1][1]) if current is not None else None
        if (separator is None or len(separator) != len(columns)
                or any(re.fullmatch(r":?-+:?", cell) is None for cell in separator)
                or not current[1][2] or not _top_level(current[1][1])):
            failures.setdefault(table_id, "TABLE_MALFORMED")
            continue
        if len(columns) > 40 or len(set(columns)) != len(columns):
            failures.setdefault(table_id, "TABLE_MALFORMED")
        rows = []
        current = next(records, None)
        while current is not None:
            _line_number, (_raw, row, row_visible) = current
            cells = _table_cells(row)
            if cells is None:
                break
            if not row_visible or not _top_level(row) or len(cells) != len(columns):
                failures.setdefault(table_id, "TABLE_MALFORMED")
            rows.append(cells)
            current = next(records, None)
        if table_id not in failures:
            tables[table_id] = (columns, rows)
    if pending:
        failures.setdefault(pending, "TABLE_MISSING")
    return tables, [{"view_id": key, "code": value} for key, value in sorted(failures.items())]


def _number(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        raise PresentationError("VALUE_UNAVAILABLE")
    text = str(value)
    if len(text) > 128 or not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", text):
        raise PresentationError("VALUE_UNAVAILABLE")
    try:
        number = Decimal(text)
        finite_or_none(float(number))
    except (ValueError, InvalidOperation, OverflowError) as exc:
        raise PresentationError("VALUE_UNAVAILABLE") from exc
    return "0" if number == 0 else format(number, "f").rstrip("0").rstrip(".") if "." in text else text


def _rows(tables, table_id, required=()):
    if table_id not in tables:
        raise PresentationError("TABLE_MISSING")
    columns, rows = tables[table_id]
    if not set(required) <= set(columns):
        raise PresentationError("COLUMN_MISSING")
    if len(rows) > 500:
        raise PresentationError("POINT_LIMIT")
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _unit(rows, fields=("currency", "unit")):
    values = {tuple(row.get(field, "").strip() for field in fields) for row in rows}
    if len(values) != 1 or any(v.casefold() in {"", "-", "n/a", "null", "unavailable", "not available"} for v in next(iter(values), ())):
        raise PresentationError("UNIT_MISMATCH")
    return " ".join(next(iter(values)))


def _point(row, x, y, series, evidence):
    declared = row.get("source_id")
    sources = sorted({ref["source_id"] for ref in evidence})
    if declared is not None:
        selected = re.split(r"\s*[;,]\s*", declared)
        if not selected or not set(selected) <= set(sources):
            raise PresentationError("EVIDENCE_UNAVAILABLE")
        sources = sorted(set(selected))
    if not sources:
        raise PresentationError("EVIDENCE_UNAVAILABLE")
    return {"x": x, "y": _number(y), "display": str(y), "series": series, "source_ids": sources}


def chart_section(section_id, title, page, origin, recipe):
    parsed = ChartRecipe.model_validate(recipe)
    columns, rows = parsed.accessible_table()
    return DocumentChartSection(
        kind="chart", section_id=section_id, title=title, page=page, editable=False,
        origin=origin, recipe=recipe, accessible_columns=columns, accessible_rows=rows,
    ).model_dump()


def _chart(view_id, title, page, origin, kind, unit, points):
    if len(points) > 500:
        raise PresentationError("POINT_LIMIT")
    if len(points) < 2:
        raise PresentationError("INSUFFICIENT_POINTS")
    coordinates = [(p["x"], p["series"]) for p in points]
    if len(set(coordinates)) != len(coordinates):
        raise PresentationError("DUPLICATE_ID")
    return chart_section(view_id, title, page, origin, {
        "schema_version": "caos.chart.v1", "recipe_id": view_id, "kind": kind,
        "unit": unit, "points": points,
    })


def _periods(tables):
    rows = _rows(tables, "cp1.model_period_register", (
        "period_id", "start_date", "end_date", "period_type", "currency", "unit", "accounting_basis", "entity_perimeter",
    ))
    result = {}
    for row in rows:
        if row["period_id"] in result:
            raise PresentationError("DUPLICATE_ID")
        try:
            end = date.fromisoformat(row["end_date"])
            start = None if row["start_date"].casefold() in {"", "-", "null", "n/a"} else date.fromisoformat(row["start_date"])
        except ValueError as exc:
            raise PresentationError("PERIOD_BASIS_MISMATCH") from exc
        if start is not None and start > end:
            raise PresentationError("PERIOD_BASIS_MISMATCH")
        result[row["period_id"]] = row
    return result


def _compatible_periods(rows, periods):
    try:
        selected = [periods[p] for p in {r["period_id"] for r in rows}]
    except KeyError as exc:
        raise PresentationError("PERIOD_BASIS_MISMATCH") from exc
    unit = _unit(selected)
    _basis = {(p["period_type"], p["accounting_basis"], p["entity_perimeter"]) for p in selected}
    if len(_basis) != 1:
        raise PresentationError("PERIOD_BASIS_MISMATCH")
    ordered = sorted(selected, key=lambda p: (p["end_date"], p["period_id"]))
    if selected[0]["period_type"] != "PERIOD_END" and (
        any(p["start_date"].casefold() in {"", "-", "null", "n/a"} for p in selected)
        or any(a["end_date"] >= b["start_date"] for a, b in zip(ordered, ordered[1:]))
    ):
        raise PresentationError("PERIOD_BASIS_MISMATCH")
    return unit


def _cp1_chart(tables, metric, evidence, origin):
    periods = _periods(tables)
    if metric == "debt_maturity":
        rows = _rows(tables, "cp1.debt_facility_register", (
            "facility_id", "period_id", "carrying_value", "principal", "currency", "maturity_date", "seniority",
        ))
        if any(row["period_id"] not in periods for row in rows):
            raise PresentationError("PERIOD_BASIS_MISMATCH")
        if not rows:
            raise PresentationError("INSUFFICIENT_POINTS")
        latest_row = max(rows, key=lambda r: periods[r["period_id"]]["end_date"])
        selected = periods[latest_row["period_id"]]
        if any(r["period_id"] != selected["period_id"] and periods[r["period_id"]]["end_date"] == selected["end_date"] for r in rows):
            raise PresentationError("PERIOD_BASIS_MISMATCH")
        rows = [r for r in rows if r["period_id"] == selected["period_id"]]
        unit = _unit([selected])
        if any(r["currency"] != selected["currency"] for r in rows):
            raise PresentationError("UNIT_MISMATCH")
        if len({r["facility_id"] for r in rows}) != len(rows):
            raise PresentationError("DUPLICATE_ID")
        for row in rows:
            try:
                date.fromisoformat(row["maturity_date"])
            except ValueError as exc:
                raise PresentationError("PERIOD_BASIS_MISMATCH") from exc
        rows.sort(key=lambda r: (r["maturity_date"], r["facility_id"]))
        points = [_point(r, r["maturity_date"], r["carrying_value"], r["facility_id"], evidence) for r in rows]
        return _chart("cp1.debt_maturity.v1", f"Debt maturities — carrying value, {selected['period_id']}",
                      "Capital structure", origin, "stacked_bar", unit, points)
    if metric == "segments":
        rows = _rows(tables, "cp1.segment_revenue_schedule", ("period_id", "segment_id", "revenue", "status", "source_id"))
        value_key, series_key, status_key = "revenue", "segment_id", "status"
    elif metric == "adjustments":
        rows = _rows(tables, "cp1.adjusted_ebitda_bridge", (
            "period_id", "addback_id", "value", "status", "realization_status", "source_id", "source_definition",
        ))
        value_key, series_key, status_key = "value", "addback_id", "status"
    else:
        rows = _rows(tables, "cp1.model_account_register", (
            "period_id", "metric_id", "value", "calculation_status", "source_id", "conflict_refs", "limitation_refs",
        ))
        rows = [row for row in rows if row["metric_id"] == metric]
        value_key, series_key, status_key = "value", "metric_id", "calculation_status"
    if not rows:
        raise PresentationError("INSUFFICIENT_POINTS")
    if any(r[status_key] not in {"Verified", "Calculated"} or r.get("conflict_refs", "-") != "-" for r in rows):
        raise PresentationError("VALUE_UNAVAILABLE")
    if metric == "adjustments":
        definitions = {}
        for row in rows:
            if definitions.setdefault(row[series_key], row["source_definition"]) != row["source_definition"]:
                raise PresentationError("PERIOD_BASIS_MISMATCH")
    unit = _compatible_periods(rows, periods)
    identities = [(row["period_id"], row[series_key]) for row in rows]
    if len(set(identities)) != len(identities):
        raise PresentationError("DUPLICATE_ID")
    if metric not in {"adjustments", "segments"} and {r["period_id"] for r in rows} != set(periods):
        raise PresentationError("VALUE_UNAVAILABLE")
    rows.sort(key=lambda r: (periods[r["period_id"]]["end_date"], r[series_key]))
    points = [_point(r, r["period_id"], r[value_key], r[series_key] + (
        f" ({r['realization_status']})" if metric == "adjustments" else ""), evidence)
        for r in rows]
    return _chart(f"cp1.{metric}.v1", metric.replace("_", " ").title(), "Financial performance", origin,
                  "bar" if metric == "adjustments" else "line", unit, points)


# Explicit numeric comparisons in non-CP1 ledger tables. No numeric-column guessing.
# Ratio/percent/score units come from the exact named column; money requires an
# explicit unit column. Unsupported dimensions stay complete tables with a reason.
_COMPARISONS = {
    ("CP-1A", "revenue_business_mix"): ("Business line", "Revenue mix", None, ("Period", "Status")),
    ("CP-1A", "operating_model"): ("Operating driver", "Measure", None, ("Period", "Status")),
    ("CP-1C", "T4.3"): ("Entity", "EBITDA Margin", None, ("Period", "Currency", "Calc Status", "Comp Status")),
    ("CP-1C", "T4.4"): ("Entity", "FCF Conversion", None, ("Period", "Currency", "Calc Status", "Comp Status")),
    ("CP-1C", "T4.8"): ("Entity", "EV/EBITDA", "x", ("Period", "Metric Def", "Comp Status", "Date")),
    ("CP-1C", "T4.9"): ("Txn Name", "TV/EBITDA", "x", ("Period", "Metric Def", "Comp Status", "Date")),
    ("CP-1D", "T1D.4"): ("Step", "Amount", None, ("Basis",)),
    ("CP-1D", "T1D.5"): ("Period", "Conversion %", "%", ()),
    ("CP-1D", "T1D.6"): ("Metric", "Delta (turns)", "x", ()),
    ("CP-2A", "T2B.6"): ("Sensitivity", "Result", None, ("Input Basis", "Status")),
    ("CP-2E", "T2F.2"): ("Debt Instrument", "Amount", None, ("Currency",)),
    ("CP-2E", "T2F.3"): ("Instrument Covered", "Notional", None, ()),
    ("CP-2E", "T2F.4"): ("Metric", "Amount", None, ("Status",)),
    ("CP-2E", "T2F.5"): ("Sensitivity", "Estimated Cash Impact", None, ("Status",)),
    ("CP-2G", "T2H.4"): ("period", "EBITDA", None, ("case",)),
    ("CP-2G", "T2H.6"): ("period", "coverage", "x", ("case", "definition IDs")),
    ("CP-2H", "T2R.4"): ("agency", "headroom", None, ("metric", "status")),
    ("CP-2H", "T3E.2"): ("security_id", "duration", None, ("benchmark",)),
    ("CP-2H", "T3E.4"): ("comparator", "difference", None, ("period", "alignment basis")),
    ("CP-3", "T3.3"): ("Factor", "Weighted Score", "score", ()),
    ("CP-3", "T3.7"): ("Security / Tranche", "Composite Score /100", "score /100", ()),
    ("CP-3", "T3B.2"): ("Instrument", "Amount", None, ("Currency",)),
    ("CP-3", "T3C.5"): ("Exposure Dimension", "Current Exposure", None, ("Evidence Status",)),
    ("CP-4", "T4C.4"): ("Test", "Headroom", None, ("Current Basis", "Status")),
    ("CP-4", "T4C.5"): ("Basket / Test", "Remaining Capacity", None, ("Status",)),
    ("CP-4C", "T4E.3"): ("scenario", "EV", None, ("valuation date",)),
    ("CP-4C", "T4E.5"): ("entity", "allocation", None, ("scenario",)),
    ("CP-4C", "T4E.7"): ("class/instrument", "total recovery", None, ("scenario", "timing", "currency")),
    ("CP-4C", "T3D.2"): ("Instrument", "Amount", None, ("Currency",)),
}


def _comparison_chart(module, table_id, tables, evidence, origin, page):
    if (module, table_id) not in _COMPARISONS:
        raise PresentationError("MAPPING_UNAVAILABLE")
    category, value, fixed_unit, required = _COMPARISONS[module, table_id]
    rows = _rows(tables, table_id, (category, value, *required))
    if not rows:
        raise PresentationError("INSUFFICIENT_POINTS")
    for row in rows:
        for key in ("Status", "status", "Calc Status", "Comp Status", "Calc/Comp Status", "Evidence Status"):
            if key in row and row[key].casefold() not in {"verified", "calculated", "reported", "derived", "comparable", "ready", "pass"}:
                raise PresentationError("VALUE_UNAVAILABLE")
    for field in ("Period", "Currency", "Basis", "scenario", "timing", "Metric Def", "Date", "case", "definition IDs",
                  "valuation date", "period", "alignment basis", "Current Basis", "metric", "benchmark"):
        if field in rows[0] and category != field and (len({r[field] for r in rows}) != 1 or not rows[0][field].strip()):
            raise PresentationError("PERIOD_BASIS_MISMATCH")
    unit_field = "unit" if "unit" in rows[0] else "Unit"
    if fixed_unit:
        if unit_field in rows[0] and _unit(rows, (unit_field,)) != fixed_unit:
            raise PresentationError("UNIT_MISMATCH")
        unit = fixed_unit
    elif unit_field not in rows[0] and all(row[value].endswith("%") for row in rows):
        unit = "%"  # explicit cell notation, never a guess from numeric magnitude
    else:
        unit = _unit(rows, (unit_field,))
        if unit not in {"%", "x", "bps", "score", "decimal", "ratio"}:
            unit = _unit(rows, ("currency" if "currency" in rows[0] else "Currency", unit_field))
    points = []
    for row in rows:
        raw_value = row[value]
        number = raw_value[:-1] if unit in {"%", "x"} and raw_value.endswith(unit) else raw_value
        point = _point(row, row[category], number, value, evidence)
        point["display"] = raw_value
        points.append(point)
    return _chart(f"{module}.{table_id}.v1", value, page, origin, "bar", unit, points)


def _comparator_chart(tables):
    table_id = "cp1b.model_comparator_register"
    rows = _rows(tables, table_id, ("metric_id", "current_period_id", "reference_period_id", "comparison_basis",
        "current_value", "reference_value", "absolute_change", "percentage_change", "calculation_status",
        "restatement_flag", "basis_change_flag", "perimeter_change_flag", "definition_change_flag"))
    if any(r["calculation_status"] != "Calculated" or any(r[f] != "false" for f in (
            "restatement_flag", "basis_change_flag", "perimeter_change_flag", "definition_change_flag")) for r in rows):
        raise PresentationError("VALUE_UNAVAILABLE")
    # REF_CP-1B_STEPS.md defines null/zero-denominator behavior, but gives no
    # monetary unit or fraction-vs-percent encoding (the fixture uses .083333).
    # No dimensional claim or recomputed change can follow from this register.
    raise PresentationError("UNIT_MISMATCH")


def _cp1_cohorts(tables):
    periods = _periods(tables)
    kinds = sorted({p["period_type"] for p in periods.values()})
    if len(kinds) < 2:
        return [(None, tables)]
    result = []
    for kind in kinds:
        selected = {key for key, row in periods.items() if row["period_type"] == kind}
        cohort = {}
        for name, (columns, rows) in tables.items():
            if "period_id" in columns:
                position = columns.index("period_id")
                rows = [row for row in rows if row[position] in selected or row[position] not in periods]
            cohort[name] = (columns, rows)
        result.append((kind, cohort))
    return result


def _project_v1(artifact):
    payload = artifact.get("payload") or {}
    module = artifact["module_id"]
    evidence = payload.get("evidence_refs", [])
    evidence = [ref for ref in evidence if isinstance(ref, dict) and ref.get("source_id") and ref.get("block_id")]
    if any(len(r["block_id"]) > 120 or len(r["source_id"]) > 120 for r in evidence):
        return [], [{"view_id": module, "code": "MAPPING_UNAVAILABLE"}]
    origin = {"kind": "ARTIFACT", "authority_id": artifact["id"], "block_ids": sorted({r["block_id"] for r in evidence})}
    markdown = artifact.get("markdown") or ""
    tables, unavailable = read_tables(markdown)
    sections = []
    bindings = [row for row in BINDINGS_V1 if row[0] == module]
    if not bindings or payload.get("schema_version") != "caos.canonical.artifact.v1":
        unavailable.append({"view_id": module, "code": "MAPPING_UNAVAILABLE"})
        return sections, unavailable
    if module == "CP-DR":
        metadata = payload.get("handoff_metadata") or {}
        fields = ("scope_type", "scope_key", "subject_name", "research_question", "source_mode",
                  "approved_plan_hash", "coverage_score", "research_status", "research_stop_reason")
        rows = [{"label": key, "value": str(metadata[key])} for key in fields if metadata.get(key) is not None]
        if rows:
            sections.append({"kind": "profile", "section_id": "CP-DR.scope", "title": "Research scope",
                             "page": "Deep Research scope", "editable": False, "origin": origin, "rows": rows})
        else:
            unavailable.append({"view_id": "CP-DR.scope", "code": "COLUMN_MISSING"})
    # Narrative includes every canonical subsection, including qualitative-only
    # bindings and CP-DR. Chunk without deleting bytes when the document bound is
    # smaller than the provider envelope's bound. Raw HTTP Markdown also survives.
    body = strip_provider_frontmatter(markdown)
    for offset in range(0, len(body), 20_000):
        sections.append({"kind": "text", "section_id": f"{module}.narrative.{offset // 20_000}",
                         "title": f"{module} analysis", "page": "Analysis", "editable": False,
                         "origin": origin, "body": body[offset:offset + 20_000]})
    pages = {}
    chart_tables = []
    for _, names, policy, page in bindings:
        if not names:
            continue
        names = list(dict.fromkeys(names + [_CP1_ALIASES[n] for n in names if module == "CP-1" and n in _CP1_ALIASES]))
        present = [name for name in names if name in tables]
        if not present:
            unavailable.append({"view_id": names[-1], "code": "TABLE_MISSING"})
        for name in present:
            pages[name] = page[:120]
            if policy == "V+T":
                chart_tables.append((name, page[:120]))
    for name, (columns, rows) in tables.items():
        for offset in range(0, max(1, len(rows)), 500):
            sections.append({"kind": "table", "section_id": f"{module}.{name}.{offset // 500}",
                             "title": name, "page": pages.get(name, "Analysis"), "editable": False,
                             "origin": origin, "columns": columns, "rows": rows[offset:offset + 500], "note": None})
    if module == "CP-1":
        chart_data = dict(tables)
        for display_id, stable_id in _CP1_ALIASES.items():
            if display_id in tables and stable_id not in tables:
                chart_data[stable_id] = tables[display_id]
        for metric in ("revenue", "ebitda", "cfo_ncfo", "cash_and_equivalents", "segments", "adjustments", "debt_maturity"):
            try:
                cohorts = [(None, chart_data)] if metric == "debt_maturity" else _cp1_cohorts(chart_data)
                for basis, data in cohorts:
                    view_id = f"cp1.{metric}.v1" + (f".{basis.lower()}" if basis else "")
                    try:
                        section = _cp1_chart(data, metric, evidence, origin)
                        section["section_id"] = section["recipe"]["recipe_id"] = view_id
                        if basis:
                            section["title"] += f" — {basis}"
                        sections.append(section)
                    except PresentationError as exc:
                        unavailable.append({"view_id": view_id, "code": exc.code})
            except PresentationError as exc:
                unavailable.append({"view_id": f"cp1.{metric}.v1", "code": exc.code})
            except ValidationError:
                unavailable.append({"view_id": f"cp1.{metric}.v1", "code": "MAPPING_UNAVAILABLE"})
    handled = {"cp1.model_account_register", "cp1.adjusted_ebitda_bridge", "cp1.debt_facility_register", "cp1.segment_revenue_schedule"}
    for name, page in chart_tables:
        if module == "CP-1" and _CP1_ALIASES.get(name, name) in handled:
            continue
        view_id = f"{module}.{name}.v1"
        try:
            if module == "CP-1B" and name == "cp1b.model_comparator_register":
                _comparator_chart(tables)
            else:
                sections.append(_comparison_chart(module, name, tables, evidence, origin, page))
        except PresentationError as exc:
            unavailable.append({"view_id": view_id, "code": exc.code})
        except ValidationError:
            unavailable.append({"view_id": view_id, "code": "MAPPING_UNAVAILABLE"})
    if len(sections) > 500:
        sections = sections[:500]
        unavailable.append({"view_id": module, "code": "SECTION_LIMIT"})
    for section in sections:
        if section["kind"] == "chart":
            sources = {source for point in section["recipe"]["points"] for source in point["source_ids"]}
            section["origin"] = {**origin, "block_ids": sorted({r["block_id"] for r in evidence if r["source_id"] in sources})}
    unavailable = list({(r["view_id"], r["code"]): r for r in unavailable}.values())
    if len(unavailable) > 500:
        unavailable = unavailable[:499] + [{"view_id": module, "code": "SECTION_LIMIT"}]
    return sections, unavailable


_MAPPINGS = {"caos.module-presentation.v1": _project_v1}


def project_artifact(artifact: dict[str, Any], *, mapping_version: str | None = None) -> ModulePresentationResponse:
    """Project after existing authority validation; never substitute a saved version."""
    version = CURRENT_MAPPING_VERSION if mapping_version is None else mapping_version
    mapping = _MAPPINGS.get(version)
    if mapping is None:
        raise PresentationError("MAPPING_VERSION_UNSUPPORTED")
    sections, unavailable = mapping(artifact)
    return ModulePresentationResponse(schema_version="caos.module-presentation.v1", artifact_id=artifact["id"],
        artifact_digest=artifact["digest"], mapping_version=version, sections=sections, unavailable=unavailable)


def project_model_outputs(*, selection: dict[str, Any], outputs: dict[str, Any], unit: str,
                          mapping_version: str | None = None) -> ModelPresentationResponse:
    """Selected, already validated annual model outputs; no model lookup or fallback.

    ModelService.default_outputs and validated Analyst Model Revision.outputs
    supply BASE/DOWNSIDE annual columns. Selection is the existing deliverable
    selection contract and is preserved in every MODEL origin.
    """
    from pydantic import TypeAdapter
    from ..contracts import DeliverableModelSelection

    version = CURRENT_MAPPING_VERSION if mapping_version is None else mapping_version
    if version != "caos.module-presentation.v1":
        raise PresentationError("MAPPING_VERSION_UNSUPPORTED")
    selected = TypeAdapter(DeliverableModelSelection).validate_python(selection)
    authority_id = selected.revision_id if selected.kind == "ANALYST_REVISION" else selected.build_id
    origin = {"kind": "MODEL", "authority_id": authority_id, "block_ids": []}
    result = []
    unavailable = []
    for metric in ("cash_and_equivalents", "fcf", "net_leverage", "interest_coverage"):
        points = []
        view_id = f"model.{metric}.v1"
        try:
            for case in ("BASE", "DOWNSIDE"):
                periods = outputs.get(case, {})
                if not periods:
                    raise PresentationError("INSUFFICIENT_POINTS")
                years = []
                for period, values in sorted(periods.items()):
                    if re.fullmatch(rf"{case}::FY[0-9]{{4}}", period) is None:
                        raise PresentationError("PERIOD_BASIS_MISMATCH")
                    years.append(int(period[-4:]))
                    points.append({"x": period.split("::", 1)[1], "y": _number(values.get(metric)),
                                   "display": str(values.get(metric)), "series": case, "source_ids": []})
                if any(b != a + 1 for a, b in zip(years, years[1:])):
                    raise PresentationError("PERIOD_BASIS_MISMATCH")
            result.append(_chart(view_id, metric.replace("_", " ").title(), "Base / Downside model", origin,
                                 "line", "x" if metric in {"net_leverage", "interest_coverage"} else unit, points))
        except PresentationError as exc:
            unavailable.append({"view_id": view_id, "code": exc.code})
        except ValidationError:
            unavailable.append({"view_id": view_id, "code": "UNIT_MISMATCH"})
    return ModelPresentationResponse(schema_version="caos.model-presentation.v1", selection=selected,
                                     mapping_version=version, sections=result, unavailable=unavailable)
