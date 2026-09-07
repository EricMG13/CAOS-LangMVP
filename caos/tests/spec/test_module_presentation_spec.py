"""Host presentation never changes module, evidence or selected model authority."""
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from caos.contracts import digest


def artifact(module="CP-1", markdown=None):
    if markdown is None:
        markdown = (Path(__file__).parents[1] / "fixtures/cp_model" / f"{module.lower().replace('-', '')}.md").read_text()
    payload = {"schema_version": "caos.canonical.artifact.v1", "canonical_output": {"markdown": markdown},
               "evidence_refs": [{"source_id": "SRC-1", "block_id": "block-42"}]}
    return {"id": "artifact-1", "module_id": module, "digest": digest(payload), "payload": payload, "markdown": markdown}


def project(value, **kwargs):
    from caos.artifacts.presentation import project_artifact
    return project_artifact(value, **kwargs).model_dump()


def charts(result):
    return {section["recipe"]["recipe_id"]: section for section in result["sections"] if section["kind"] == "chart"}


def test_cp1_projection_is_deterministic_separate_and_source_bound():
    value = artifact()
    before = deepcopy(value)
    result = project(value)
    assert result == project(value, mapping_version=result["mapping_version"])
    assert value == before
    revenue = charts(result)["cp1.revenue.v1"]
    assert [point["y"] for point in revenue["recipe"]["points"]] == ["100", "110", "120", "130"]
    assert revenue["origin"] == {"kind": "ARTIFACT", "authority_id": "artifact-1", "block_ids": ["block-42"]}
    assert all(point["source_ids"] == ["SRC-1"] for point in revenue["recipe"]["points"])
    assert len([s for s in result["sections"] if s["kind"] == "table"]) >= 8


def test_unknown_recorded_version_refused():
    from caos.artifacts.presentation import PresentationError
    with pytest.raises(PresentationError, match="MAPPING_VERSION_UNSUPPORTED"):
        project(artifact(), mapping_version="future")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e999", "1,000", "-0", "01", "1.00"])
def test_chart_numeric_strings_are_finite_canonical_decimals(value):
    from caos.contracts import ChartRecipe
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(recipe(value))


def recipe(y="1", kind="line"):
    return {"schema_version": "caos.chart.v1", "recipe_id": "test.v1", "kind": kind, "unit": "USD millions",
            "points": [{"x": "2024", "y": y, "display": y, "series": "Revenue", "source_ids": ["SRC-1"]}]}


def test_chart_closed_scatter_and_accessible_table_contract():
    from caos.contracts import ChartRecipe, DocumentChartSection
    from caos.artifacts.presentation import chart_section
    section = chart_section("test", "Revenue", "Financial performance", {"kind": "ARTIFACT", "authority_id": "a", "block_ids": []}, recipe())
    assert DocumentChartSection.model_validate(section)
    section["accessible_rows"][0][2] = "999"
    with pytest.raises(ValidationError):
        DocumentChartSection.model_validate(section)
    for extra in ({"html": "<b>"}, {"options": {}}, {"url": "https://example.org"}):
        with pytest.raises(ValidationError):
            ChartRecipe.model_validate({**recipe(), **extra})
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(recipe(kind="scatter"))
    scatter = recipe(kind="scatter")
    scatter["points"][0]["x_value"] = "2"
    assert ChartRecipe.model_validate(scatter)
    scatter["kind"] = "bar"
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(scatter)


def test_origin_cannot_be_replaced_in_presentation_response():
    from caos.responses import ModulePresentationResponse
    result = project(artifact())
    result["sections"][0]["origin"]["authority_id"] = "another-artifact"
    with pytest.raises(ValidationError):
        ModulePresentationResponse.model_validate(result)


@pytest.mark.parametrize("replacement,code", [("EUR | MILLIONS", "UNIT_MISMATCH"), ("USD | THOUSANDS", "UNIT_MISMATCH")])
def test_incompatible_units_leave_tables(replacement, code):
    value = artifact()
    value = artifact(markdown=value["markdown"].replace("USD | MILLIONS", replacement, 1))
    result = project(value)
    assert "cp1.revenue.v1" not in charts(result)
    assert {"view_id": "cp1.revenue.v1", "code": code} in result["unavailable"]
    assert any(s["kind"] == "table" for s in result["sections"])


def test_table_reader_duplicates_hidden_rows_escaped_pipes():
    from caos.artifacts.presentation import read_tables
    text = "<!-- table-id: cp1.example -->\n| name | value |\n|---|---|\n| A\\|B | 1 |\n"
    tables, unavailable = read_tables(text)
    assert tables["cp1.example"][1] == [["A|B", "1"]]
    assert not unavailable
    for malformed in (text + text, "```\n" + text + "```", text.replace("A\\|B | 1", "A | 1 | extra")):
        tables, unavailable = read_tables(malformed)
        assert "cp1.example" not in tables
        assert unavailable


def test_debt_uses_one_period_and_carrying_value_not_undrawn_commitment():
    result = project(artifact())
    chart = charts(result)["cp1.debt_maturity.v1"]
    assert sorted(p["y"] for p in chart["recipe"]["points"]) == ["0", "185", "50"]
    assert "FY2024_Q4" in chart["title"] and "carrying" in chart["title"].lower()


def test_comparator_cannot_invent_missing_unit_or_recompute_unavailable_change():
    result = project(artifact("CP-1B"))
    assert not charts(result)
    assert any(item["code"] == "UNIT_MISMATCH" for item in result["unavailable"])
    assert any("absolute_change" in s.get("columns", []) for s in result["sections"])


@pytest.mark.parametrize("version", [None, "legacy-v1", "caos.chart.v1"])
def test_historical_field_recipes_retain_original_table_semantics(version):
    from caos.contracts import DocumentChartSection, GeneratedChartBlock
    from caos.publishing.recipes import validate_recipe
    value = {"kind": "line", "fields": ["fcf"], "units": "USD m"}
    if version is not None:
        value["schema_version"] = version
    assert validate_recipe(value, {"fcf"})
    block = {"block_id": "chart", "slot_id": "appendix", "kind": "GENERATED_CHART", "recipe": value}
    assert GeneratedChartBlock.model_validate(block).model_dump() == block
    section = {"section_id": "chart", "title": "FCF", "page": "Model", "kind": "chart", "editable": False,
               "origin": {"kind": "MODEL", "authority_id": "build", "block_ids": []}, "recipe": value,
               "accessible_columns": ["Metric", "Value"], "accessible_rows": [["fcf", "10"]]}
    assert DocumentChartSection.model_validate(section).model_dump() == section
    with pytest.raises(ValidationError):
        GeneratedChartBlock.model_validate({**block, "recipe": {**value, "points": recipe()["points"]}})


def test_unknown_point_recipe_version_and_missing_version_cannot_bypass_closure():
    from caos.contracts import GeneratedChartBlock
    for version in (None, "caos.chart.v2", "legacy-v1"):
        value = recipe()
        if version is None:
            value.pop("schema_version")
        else:
            value["schema_version"] = version
        with pytest.raises(ValidationError):
            GeneratedChartBlock.model_validate({"block_id": "a", "slot_id": "a", "kind": "GENERATED_CHART", "recipe": value})


@pytest.mark.parametrize("kind", ["line", "bar", "stacked_bar", "scatter"])
def test_recipe_point_ceiling_and_text_content_are_closed(kind):
    from caos.contracts import ChartRecipe
    value = recipe(kind=kind)
    if kind == "scatter":
        value["points"][0]["x_value"] = "0"
    point = value["points"][0]
    value["points"] = [{**point, "x": str(n)} for n in range(500)]
    assert len(ChartRecipe.model_validate(value).points) == 500
    value["points"].append(point)
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(value)
    for label in ("<b>Revenue</b>", "https://example.org", "javascript:alert(1)"):
        value["points"] = [{**point, "series": label}]
        with pytest.raises(ValidationError):
            ChartRecipe.model_validate(value)


def test_not_calculable_comparator_retains_supplied_changes_without_recalculation():
    value = artifact("CP-1B")
    text = value["markdown"].replace("120 | 10 | 0.083333 | Calculated", "0 | 130 | null | Not Calculable")
    result = project(artifact("CP-1B", text))
    assert {"view_id": "CP-1B.cp1b.model_comparator_register.v1", "code": "VALUE_UNAVAILABLE"} in result["unavailable"]
    assert any("Not Calculable" in row and "null" in row for section in result["sections"] if section["kind"] == "table" for row in section["rows"])


def test_raw_id_bounds_and_heading_marker_aliases_remain_safe():
    from caos.artifacts.presentation import read_tables
    text = "### T4.14 Model period register\n" + table("cp1.model_period_register", ["A", "B"], [["1", "2"]])
    tables, failures = read_tables(text)
    assert "cp1.model_period_register" in tables and not failures
    text = table("cp1." + "a" * 200, ["A", "B"], [["1", "2"]])
    result = project(artifact(markdown=text))
    assert any(row["code"] == "TABLE_MALFORMED" for row in result["unavailable"])


@pytest.mark.parametrize("missing_start", ["", "null", "N/A", "Not Available", "Not Calculable", "-"])
def test_period_end_without_start_does_not_poison_quarterly_trends(missing_start):
    from caos.artifacts.presentation import read_tables
    tables, _ = read_tables(artifact()["markdown"])
    columns, rows = tables["cp1.model_period_register"]
    rows.append(["FY2024_END", "2024", "-", "PERIOD_END", missing_start, "2024-12-31", "-", "AUDITED",
                 "USD", "MILLIONS", "IFRS", "Consolidated", "SRC-1", "annual", "-"])
    markdown = table("cp1.model_period_register", columns, rows) + table("cp1.model_account_register", *tables["cp1.model_account_register"])
    result = project(artifact(markdown=markdown))
    assert "cp1.revenue.v1.quarter" in charts(result)


def test_v1_dispatch_is_not_affected_by_new_projection_default(monkeypatch):
    import caos.artifacts.presentation as presentation
    value = artifact()
    expected = project(value)
    monkeypatch.setattr(presentation, "CURRENT_MAPPING_VERSION", "future")
    assert project(value, mapping_version="caos.module-presentation.v1") == expected
    with pytest.raises(presentation.PresentationError):
        project(value)


def test_full_292_binding_inventory_preserves_tables_for_all_19_active_modules():
    from caos.artifacts.presentation_bindings import BINDINGS_V1
    from caos.modules.registry import MODULES
    from caos.artifacts.presentation import read_tables
    assert len(BINDINGS_V1) == 292
    assert {row[0] for row in BINDINGS_V1} == set(MODULES)
    for module in MODULES:
        ids = list(dict.fromkeys(name for mod, names, _, _ in BINDINGS_V1 if mod == module for name in names))
        text = "## Analysis\n\nAll governed narrative remains available.\n\n"
        for name in ids:
            text += f"### {name}\n\n| Evidence | Value |\n|---|---|\n| SRC-1 | Observed |\n\n"
        tables, failures = read_tables(text)
        assert not failures, (module, failures)
        assert set(ids) <= set(tables), module
        result = project(artifact(module, text))
        rendered = {s["title"] for s in result["sections"] if s["kind"] == "table"}
        assert set(ids) <= rendered, module
        assert any("All governed narrative" in s.get("body", "") for s in result["sections"])
        for mod, names, policy, _ in BINDINGS_V1:
            if mod == module and names and policy == "V+T":
                assert result["unavailable"], (module, names)


def table(name, columns, rows):
    identity = f"<!-- table-id: {name} -->" if name.startswith("cp") else f"### {name}"
    return f"{identity}\n\n| " + " | ".join(columns) + " |\n|" + "|".join("---" for _ in columns) + "|\n" + "".join("| " + " | ".join(row) + " |\n" for row in rows) + "\n"


def test_non_cp1_numeric_comparison_uses_fixed_binding_and_same_points():
    text = table("T4.3", ["Entity", "EBITDA Margin", "Period", "Currency", "Calc Status", "Comp Status", "Unit"],
                 [["Issuer", "15", "FY2024", "USD", "Calculated", "Comparable", "%"],
                  ["Peer", "20", "FY2024", "USD", "Calculated", "Comparable", "%"]])
    result = project(artifact("CP-1C", text))
    chart = charts(result)["CP-1C.T4.3.v1"]
    assert chart["recipe"]["unit"] == "%"
    assert [p["y"] for p in chart["recipe"]["points"]] == ["15", "20"]
    assert [row[2] for row in chart["accessible_rows"]] == ["15", "20"]
    result = project(artifact("CP-1C", text.replace("Peer | 20 | FY2024", "Peer | 20 | FY2023")))
    assert "CP-1C.T4.3.v1" not in charts(result)
    assert {"view_id": "CP-1C.T4.3.v1", "code": "PERIOD_BASIS_MISMATCH"} in result["unavailable"]


@pytest.mark.parametrize("table_id,column", [("T4.3", "EBITDA Margin"), ("T4.4", "FCF Conversion")])
def test_peer_ratio_scale_is_explicit_never_inferred_from_magnitude(table_id, column):
    columns = ["Entity", column, "Period", "Currency", "Calc Status", "Comp Status"]
    rows = [["Issuer", "0.2", "FY2024", "USD", "Calculated", "Comparable"],
            ["Peer", "0.3", "FY2024", "USD", "Calculated", "Comparable"]]
    result = project(artifact("CP-1C", table(table_id, columns, rows)))
    assert not charts(result)
    assert {"view_id": f"CP-1C.{table_id}.v1", "code": "UNIT_MISMATCH"} in result["unavailable"]
    for unit in ("decimal", "%"):
        result = project(artifact("CP-1C", table(table_id, columns + ["Unit"], [row + [unit] for row in rows])))
        chart = charts(result)[f"CP-1C.{table_id}.v1"]
        assert chart["recipe"]["unit"] == unit
        assert [point["y"] for point in chart["recipe"]["points"]] == ["0.2", "0.3"]
    percentage_rows = [[r[0], r[1] + "%", *r[2:]] for r in rows]
    result = project(artifact("CP-1C", table(table_id, columns, percentage_rows)))
    chart = charts(result)[f"CP-1C.{table_id}.v1"]
    assert chart["recipe"]["unit"] == "%"
    assert [point["y"] for point in chart["recipe"]["points"]] == ["0.2", "0.3"]


def test_explicit_dimensionless_units_need_no_currency_and_cannot_conflict():
    text = table("revenue_business_mix", ["Business line", "Revenue mix", "Period", "Status", "Unit"],
                 [["Services", "70", "FY2024", "Verified", "%"], ["Products", "30", "FY2024", "Verified", "%"]])
    assert "CP-1A.revenue_business_mix.v1" in charts(project(artifact("CP-1A", text)))
    text = table("T3.3", ["Factor", "Weighted Score", "Unit"], [["A", "1", "USD"], ["B", "2", "USD"]])
    result = project(artifact("CP-3", text))
    assert {"view_id": "CP-3.T3.3.v1", "code": "UNIT_MISMATCH"} in result["unavailable"]


def test_pinned_peer_multiple_notation_preserves_display_and_numeric_scale():
    text = table("T4.8", ["Entity", "EV/EBITDA", "Period", "Metric Def", "Comp Status", "Date"],
                 [["Issuer", "5.2x", "FY2024", "Adjusted EBITDA", "Comparable", "2025-01-01"],
                  ["Peer", "6x", "FY2024", "Adjusted EBITDA", "Comparable", "2025-01-01"]])
    chart = charts(project(artifact("CP-1C", text)))["CP-1C.T4.8.v1"]
    assert [(p["y"], p["display"]) for p in chart["recipe"]["points"]] == [("5.2", "5.2x"), ("6", "6x")]


def test_point_limit_does_not_truncate_raw_tables():
    text = table("T3.3", ["Factor", "Weighted Score"], [[f"F{n}", str(n)] for n in range(501)])
    result = project(artifact("CP-3", text))
    assert not charts(result)
    assert {"view_id": "CP-3.T3.3.v1", "code": "POINT_LIMIT"} in result["unavailable"]
    assert sum(len(s["rows"]) for s in result["sections"] if s["kind"] == "table") == 501


def test_mixed_annual_and_quarterly_periods_produce_separate_compatible_trends():
    from caos.artifacts.presentation import read_tables
    value = artifact()
    tables, _ = read_tables(value["markdown"])
    periods, period_rows = tables["cp1.model_period_register"]
    accounts, account_rows = tables["cp1.model_account_register"]
    for year in (2023, 2024):
        period_rows.append([f"FY{year}", str(year), "-", "FY", f"{year}-01-01", f"{year}-12-31", "365", "AUDITED",
                            "USD", "MILLIONS", "IFRS", "Consolidated", "SRC-1", "annual", "-"])
        account_rows.append(["revenue", f"FY{year}", "400" if year == 2023 else "460", "SIGNED_AS_REPORTED",
                             "SOURCED", "Verified", "SRC-1", "annual", "-", "-"])
    markdown = table("cp1.model_period_register", periods, period_rows) + table("cp1.model_account_register", accounts, account_rows)
    result = project(artifact(markdown=markdown))
    assert [p["y"] for p in charts(result)["cp1.revenue.v1.fy"]["recipe"]["points"]] == ["400", "460"]
    assert [p["y"] for p in charts(result)["cp1.revenue.v1.quarter"]["recipe"]["points"]] == ["100", "110", "120", "130"]


@pytest.mark.parametrize("mutation,code", [
    (lambda text: text.replace("2024-04-01", "2024-03-01"), "PERIOD_BASIS_MISMATCH"),
    (lambda text: text.replace("USD | MILLIONS | IFRS", "USD | MILLIONS | GAAP", 1), "PERIOD_BASIS_MISMATCH"),
    (lambda text: text.replace("revenue | FY2024_Q1 | 100", "revenue | UNKNOWN | 100"), "PERIOD_BASIS_MISMATCH"),
    (lambda text: text.replace("revenue | FY2024_Q1 | 100", "revenue | FY2024_Q1 | NaN"), "VALUE_UNAVAILABLE"),
    (lambda text: text.replace("revenue | FY2024_Q1 | 100", "revenue | FY2024_Q1 | -"), "VALUE_UNAVAILABLE"),
    (lambda text: text.replace("Verified | SRC-1", "Conflicting | SRC-1", 1), "VALUE_UNAVAILABLE"),
    (lambda text: text.replace("FY2024_Q2 | 110", "FY2024_Q1 | 110", 1), "DUPLICATE_ID"),
])
def test_chart_refuses_incompatible_or_missing_points_without_bridging_gaps(mutation, code):
    value = artifact()
    result = project(artifact(markdown=mutation(value["markdown"])))
    assert "cp1.revenue.v1" not in charts(result)
    assert {"view_id": "cp1.revenue.v1", "code": code} in result["unavailable"]


def test_missing_source_and_long_valid_evidence_ids_cannot_be_fabricated():
    value = artifact()
    value["payload"]["evidence_refs"] = []
    result = project(value)
    assert not charts(result)
    assert any(r["code"] == "EVIDENCE_UNAVAILABLE" for r in result["unavailable"])
    value["payload"]["evidence_refs"] = [{"source_id": "SRC-1", "block_id": "b" * 160}]
    assert project(value)["sections"] == []  # canonical evidence bound exceeds document identifier bound


def test_anonymous_and_explicit_table_ids_cannot_overwrite_each_other():
    from caos.artifacts.presentation import read_tables
    raw = "| name | value |\n|---|---|\n| A | 1 |\n\n<!-- table-id: table_1 -->\n| name | value |\n|---|---|\n| B | 2 |\n"
    tables, failures = read_tables(raw)
    assert "table_1" not in tables
    assert {"view_id": "table_1", "code": "DUPLICATE_ID"} in failures


def test_abandoned_stable_table_identity_is_explicitly_unavailable():
    from caos.artifacts.presentation import read_tables
    tables, failures = read_tables("### T1\n### T2\n| A | B |\n|---|---|\n| 1 | 2 |")
    assert "T2" in tables
    assert {"view_id": "T1", "code": "TABLE_MISSING"} in failures


def test_absent_middle_account_row_cannot_bridge_a_period_gap():
    value = artifact()
    markdown = "\n".join(line for line in value["markdown"].splitlines() if not line.startswith("| revenue | FY2024_Q2 |"))
    result = project(artifact(markdown=markdown))
    assert "cp1.revenue.v1" not in charts(result)
    assert {"view_id": "cp1.revenue.v1", "code": "VALUE_UNAVAILABLE"} in result["unavailable"]


def test_many_malformed_tables_stay_bounded_without_breaking_artifact_fallback():
    value = artifact(markdown="\n".join(f"<!-- table-id: bad_{n} -->\n| a | b |\n| malformed |" for n in range(600)))
    result = project(value)
    assert len(result["unavailable"]) <= 500
    assert {"view_id": "CP-1", "code": "SECTION_LIMIT"} in result["unavailable"]


@pytest.fixture(scope="module")
def presentation_bundle():
    from caos.methodology.bundle import DeployVBundle
    import caos.methodology.bundle as bundle_module
    return DeployVBundle(Path(bundle_module.__file__).parent / "vendor/deploy_v")


def validated_fixture_projection(markdown, bundle):
    """These malformed chart inputs remain valid artifacts at the existing seam."""
    from caos.methodology.canonical import validate_model_sources
    from caos.artifacts.presentation import read_tables
    bundle.validate_handoff(markdown, module_id="CP-1", run_id="run-cp-model-fixture", reporting_period="FY2024")
    validate_model_sources(markdown, returned_source_ids={"SRC-1"})
    value = artifact(markdown=markdown)
    before = deepcopy(value)
    result = project(value)
    assert value == before
    assert "".join(s["body"] for s in result["sections"] if s["kind"] == "text").endswith(markdown.split("---", 2)[-1].lstrip())
    assert any(s["kind"] == "table" and s["title"] == "cp1.model_account_register" for s in result["sections"])
    assert {s["title"]: (s["columns"], s["rows"]) for s in result["sections"] if s["kind"] == "table"} == read_tables(markdown)[0]
    return result


def test_full_fixture_bare_pipe_table_is_unavailable_without_losing_valid_sections(presentation_bundle):
    from caos.artifacts.presentation import read_tables
    tables, failures = read_tables("|\n|\n")
    assert not tables
    assert failures and all(item["code"] == "TABLE_MALFORMED" for item in failures)
    markdown = artifact()["markdown"].replace("## Analysis\n", "## Analysis\n\n|\n|\n", 1)
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert len(charts(result)) == 7
    assert any(r["code"] == "TABLE_MALFORMED" for r in result["unavailable"])


@pytest.mark.parametrize("omitted", ["FY2024_Q2", "FY2024_Q3"])
def test_full_fixture_segment_interior_gap_is_not_joined(omitted, presentation_bundle):
    original = artifact()["markdown"]
    # A second complete series must not conceal Services' missing observation.
    markdown = "\n".join(line + "\n" + line.replace("services | Services", "products | Products")
                         if line.startswith("| services |") else line for line in original.splitlines())
    markdown = "\n".join(line for line in markdown.splitlines()
                         if not (line.startswith("| services |") and omitted in line))
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert "cp1.segments.v1" not in charts(result)
    assert {"view_id": "cp1.segments.v1", "code": "VALUE_UNAVAILABLE"} in result["unavailable"]
    assert "cp1.revenue.v1" in charts(result)


@pytest.mark.parametrize("omitted", ["FY2024_Q1", "FY2024_Q4"])
def test_full_fixture_segment_edge_activity_needs_no_fabricated_zeros(omitted, presentation_bundle):
    markdown = "\n".join(line for line in artifact()["markdown"].splitlines()
                         if not (line.startswith("| services |") and omitted in line))
    markdown = markdown.replace("FY2024_Q2 | 110 | Verified", "FY2024_Q2 | 0 | Verified")
    markdown = markdown.replace("FY2024_Q3 | 120 | Verified", "FY2024_Q3 | -5 | Verified")
    result = validated_fixture_projection(markdown, presentation_bundle)
    points = charts(result)["cp1.segments.v1"]["recipe"]["points"]
    assert omitted not in {point["x"] for point in points}
    assert {"0", "-5"} <= {point["y"] for point in points}
    assert len(points) == 3


@pytest.mark.parametrize("field,original", [("accounting_basis", "IFRS"), ("entity_perimeter", "Consolidated")])
@pytest.mark.parametrize("missing", ["", "null", "N/A", "Not Available", "Not Calculable", "-"])
def test_full_fixture_equal_missing_period_basis_is_not_compatibility(field, original, missing, presentation_bundle):
    markdown = artifact()["markdown"].replace(f"| {original} |", f"| {missing} |")
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert not charts(result), field
    assert {"view_id": "cp1.revenue.v1", "code": "PERIOD_BASIS_MISMATCH"} in result["unavailable"]


@pytest.mark.parametrize("kind", ["X" * 121, "MONTH", "quarter", "-", ""])
def test_full_fixture_unsupported_period_kind_cannot_escape_into_public_ids(kind, presentation_bundle):
    markdown = artifact()["markdown"].replace("| QUARTER |", f"| {kind} |", 1)
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert not charts(result)
    assert {"view_id": "cp1.revenue.v1", "code": "PERIOD_BASIS_MISMATCH"} in result["unavailable"]
    assert all(len(row["view_id"]) <= 120 for row in result["unavailable"])


def test_full_fixture_compact_iso_dates_keep_chronological_period_and_latest_debt_order(presentation_bundle):
    markdown = artifact()["markdown"].replace("2024-01-01", "20240101").replace("2024-03-31", "20240331")
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert [p["x"] for p in charts(result)["cp1.revenue.v1"]["recipe"]["points"]] == [f"FY2024_Q{q}" for q in range(1, 5)]
    debt = charts(result)["cp1.debt_maturity.v1"]
    assert "FY2024_Q4" in debt["title"]
    assert sorted(p["y"] for p in debt["recipe"]["points"]) == ["0", "185", "50"]


def test_full_fixture_compact_iso_dates_cannot_hide_overlap(presentation_bundle):
    markdown = artifact()["markdown"].replace("2024-04-01", "20240301")
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert {"view_id": "cp1.revenue.v1", "code": "PERIOD_BASIS_MISMATCH"} in result["unavailable"]


def test_full_fixture_compact_iso_maturity_dates_use_chronological_order(presentation_bundle):
    markdown = artifact()["markdown"].replace("2027-06-30", "20280101")
    result = validated_fixture_projection(markdown, presentation_bundle)
    assert [p["x"] for p in charts(result)["cp1.debt_maturity.v1"]["recipe"]["points"]] == ["2028-01-01", "2028-06-30", "2029-06-30"]


def test_model_projection_preserves_selection_and_never_fills_missing_values():
    from caos.artifacts.presentation import project_model_outputs
    selected = {"kind": "ANALYST_REVISION", "build_id": "build-1", "revision_id": "revision-1"}
    outputs = {case: {f"{case}::FY2025": {"cash_and_equivalents": 0, "fcf": 10, "net_leverage": 2, "interest_coverage": 3},
                      f"{case}::FY2026": {"cash_and_equivalents": 20, "fcf": 15, "net_leverage": 1, "interest_coverage": 4}}
               for case in ("BASE", "DOWNSIDE")}
    result = project_model_outputs(selection=selected, outputs=outputs, unit="USD millions").model_dump()
    assert result["selection"] == selected
    assert len(result["sections"]) == 4 and not result["unavailable"]
    assert {s["origin"]["authority_id"] for s in result["sections"]} == {"revision-1"}
    assert result["sections"][0]["recipe"]["points"][0]["y"] == "0"
    outputs["BASE"]["BASE::FY2025"]["fcf"] = None
    result = project_model_outputs(selection=selected, outputs=outputs, unit="USD millions").model_dump()
    assert {"view_id": "model.fcf.v1", "code": "VALUE_UNAVAILABLE"} in result["unavailable"]
    assert len(result["sections"]) == 3
    outputs["BASE"]["BASE::FY2028"] = outputs["BASE"].pop("BASE::FY2026")
    result = project_model_outputs(selection=selected, outputs=outputs, unit="USD millions").model_dump()
    assert {"view_id": "model.cash_and_equivalents.v1", "code": "PERIOD_BASIS_MISMATCH"} in result["unavailable"]
    with pytest.raises(ValueError, match="MAPPING_VERSION_UNSUPPORTED"):
        project_model_outputs(selection=selected, outputs=outputs, unit="USD millions", mapping_version="unknown")


async def test_http_projection_follows_authority_and_refuses_cross_case_withdrawal_tampering(client, engine, store, monkeypatch):
    from spec_helpers import seed_case_with_source, start_full_credit_run
    import caos.artifacts.presentation as presentation
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    value = engine.artifacts_for_run(run["id"])[0]
    url = f"/api/cases/{case['id']}/artifacts/{value['id']}"
    headers = {"x-forwarded-user": "analyst"}
    calls = []
    original = presentation.project_artifact
    monkeypatch.setattr(presentation, "project_artifact", lambda value: (calls.append(value["id"]) or original(value)))
    response = client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["presentation"]["artifact_id"] == value["id"]
    other, _ = seed_case_with_source(store)
    assert client.get(url.replace(case["id"], other["id"]), headers=headers).status_code == 404
    store.withdraw(case["id"], source["id"], "analyst")
    assert client.get(url, headers=headers).status_code == 404
    assert calls == [value["id"]]
    case2, _, run2 = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run2["id"])
    value2 = engine.artifacts_for_run(run2["id"])[0]
    engine.runs.update_artifact_for_tests(run2["id"], value2["module_id"], payload={"forged": True}, digest=digest({"forged": True}))
    assert client.get(f"/api/cases/{case2['id']}/artifacts/{value2['id']}", headers=headers).status_code == 404
    assert calls == [value["id"]]
