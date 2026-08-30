"""Model Builder specification (CP-MODEL chain). Every test must fail until phase 4 exists.

Sources: TEST_INVENTORY.md contractual rows from test_cp_model.py (all), the six
test_model_acceptance_queue.py rows, the test_model_store.py append-only-ledger row,
and the model_* rows of test_ledger_contracts.py; DECISIONS.md §§10-12 (esp. §10.6:
validate_bundle only for accepted FULL_CREDIT; §12: digest preimage rules; Sign-Off
stays a store CAS, never an interrupt).

Future API pinned here (imports live INSIDE test bodies/fixtures so each test fails
individually with ModuleNotFoundError today):

    caos.models.engine   — the ported pure calculation engine:
                           CpModelBundle(deploy_v_root) with .validate(*markdowns),
                           .calculate(paths, effective_assumptions=None) -> (model,
                           calculations), .calculate_model(model), .render_workbook,
                           .serialize_workbook, .assumption_registry,
                           .calculation_runtime, .verify_integrity(),
                           .resolve_declared_file(); plus module-level calculate,
                           is_finite_number, safe_ratio, finite_operand, json_value,
                           project_cp2b, CpModelV3Error, ModelInputError.
    caos.models.service  — ModelService(store=..., vault_dir=..., engine=...):
                           queue_build, readiness, build, list_builds, current_build,
                           worksheet, assumption_registry, preview, sign_off,
                           revisions, head_revision, rebase_preview, scenario,
                           one_way, queue_export, download. Constructing it registers
                           it as the engine's model hook so acceptance auto-queues
                           through THIS instance.

Names ending in `_for_tests` are spec'd test seams the build must provide; inventing
them here is deliberate (see task rules). Golden fixtures carry forward byte-identical
from legacy `caos/tests/fixtures/cp_model/` to the same path in this repo.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from spec_helpers import seed_case_with_source

SERVER = Path(__file__).resolve().parents[2] / "server"
DEPLOY_V = SERVER / "caos" / "methodology" / "vendor" / "deploy_v"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cp_model"
_ANALYST = {"x-forwarded-user": "analyst", "x-caos-role": "ANALYST"}
_FORECAST_FIXTURES = {
    "CP-1": "cp1.md",
    "CP-1A": "cp1a.md",
    "CP-1B": "cp1b.md",
    "CP-2": "cp2.md",
    "CP-2B": "cp2b.md",
    "CP-2G": "cp2g.md",
}


# --- pure helpers (no unbuilt imports at module level) ----------------------------


def _digest(value):
    from caos.contracts import digest

    return digest(value)


def _bundle():
    from caos.models.engine import CpModelBundle

    return CpModelBundle(DEPLOY_V)


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _validate(bundle, **replacements):
    docs = [replacements.get(name, _read(f"{name}.md")) for name in ("cp1", "cp1a", "cp1b", "cp2", "cp2b", "cp2g")]
    return tuple(bundle.validate(*docs).errors)


def _forecast_paths(tmp_path: Path | None = None, overrides: dict[str, str] | None = None) -> dict[str, Path]:
    paths = {module: FIXTURES / name for module, name in _FORECAST_FIXTURES.items()}
    for module, markdown in (overrides or {}).items():
        assert tmp_path is not None
        target = tmp_path / f"{module.lower()}-variant.md"
        target.write_text(markdown, encoding="utf-8")
        paths[module] = target
    return paths


def _mutate_cp2g_assumption(markdown: str, assumption_id: str, *, case: str = "BASE", period_id: str = "FY2025", **updates: str) -> str:
    lines = markdown.splitlines()
    header: list[str] | None = None
    changed = False
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if "assumption_id" in cells and "period_id" in cells:
            header = cells
            continue
        if header is None or len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        if row.get("assumption_id") != assumption_id or row.get("case") != case or row.get("period_id") != period_id:
            continue
        row.update(updates)
        lines[index] = "| " + " | ".join(row[column] for column in header) + " |"
        changed = True
        break
    assert changed, (assumption_id, case, period_id)
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _drop_cp2g_assumption(markdown: str, assumption_id: str, *, case: str | None = None, period_id: str | None = None) -> str:
    lines: list[str] = []
    header: list[str] | None = None
    for line in markdown.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if "assumption_id" in cells and "period_id" in cells:
                header = cells
            elif header is not None and len(cells) == len(header):
                row = dict(zip(header, cells))
                if (
                    row.get("assumption_id") == assumption_id
                    and (case is None or row.get("case") == case)
                    and (period_id is None or row.get("period_id") == period_id)
                ):
                    continue
        lines.append(line)
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _empty_stable_table(markdown: str, table_id: str) -> str:
    lines = markdown.splitlines()
    marker_index = lines.index(f"<!-- table-id: {table_id} -->")
    body_start = marker_index + 3
    end = body_start
    while end < len(lines) and not lines[end].startswith("### "):
        end += 1
    del lines[body_start:end]
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _without_stable_table(markdown: str, table_id: str) -> str:
    lines = markdown.splitlines()
    marker_index = lines.index(f"<!-- table-id: {table_id} -->")
    start = marker_index
    while start > 0 and not lines[start].startswith("### "):
        start -= 1
    end = marker_index + 1
    while end < len(lines) and not lines[end].startswith("### "):
        end += 1
    del lines[start:end]
    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _unsegmented_cp1() -> str:
    markdown = _empty_stable_table(_read("cp1.md"), "cp1.segment_revenue_schedule")
    markdown = _without_stable_table(markdown, "cp1.cp_model_segment_allocation")
    for quarter, revenue in enumerate((100, 110, 120, 130), 1):
        markdown = markdown.replace(
            f"| segment-q{quarter} | FY2024_Q{quarter} | SEGMENT_REVENUE | "
            f"{revenue} | {revenue} | 0 | 0 | PASS | Segment equals reported revenue | SRC-1 |",
            f"| segment-q{quarter} | FY2024_Q{quarter} | SEGMENT_REVENUE | "
            f"{revenue} | - | - | 0 | WARN | No disclosed segment schedule | SRC-1 |",
            1,
        )
    return markdown


def _unsegmented_cp2g() -> str:
    markdown = _read("cp2g.md")
    for case in ("BASE", "DOWNSIDE"):
        for fiscal_year in (2025, 2026, 2027):
            period_id = f"FY{fiscal_year}"
            markdown = _mutate_cp2g_assumption(
                markdown, "operating.revenue_growth.division_1", case=case, period_id=period_id,
                status="NOT_APPLICABLE", value="", source_id="", source_locator="", as_of="", gap_code="",
            )
            markdown = _mutate_cp2g_assumption(
                markdown, "operating.consolidated_revenue_growth", case=case, period_id=period_id,
                status="READY", value="0.05", source_id="SRC-1", source_locator="page:42", as_of="2025-02-15", gap_code="",
            )
    return markdown


def _cp2g_with_ready_covenant(limit: str = "1") -> str:
    markdown = _read("cp2g.md")
    for case in ("BASE", "DOWNSIDE"):
        for fiscal_year in (2025, 2026, 2027):
            markdown = _mutate_cp2g_assumption(
                markdown, "covenant.max_total_leverage", case=case, period_id=f"FY{fiscal_year}",
                status="READY", value=limit, source_id="SRC-1", source_locator="page:42", as_of="2025-02-15", gap_code="",
            )
    return markdown


def _tab(payload: dict, title: str) -> str:
    return json.dumps(next(tab for tab in payload["payload"]["tabs"] if tab["title"] == title))


# --- service-side request builders and fixtures -----------------------------------


@pytest.fixture()
def models(settings, store, engine):
    """The future ModelService; constructing it registers it as the engine's model
    hook so `engine.accept(...)` queues builds through this exact instance."""
    from caos.models.service import ModelService

    return ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)


def _preview_request(registry, build_id, *, assumptions=None, parent=None, generation=1):
    from caos.contracts import ModelPreviewRequest

    return ModelPreviewRequest.model_validate({
        "build_id": build_id,
        "parent_revision_id": parent,
        "registry_version": registry["version"],
        "registry_digest": registry["digest"],
        "assumptions": assumptions if assumptions is not None else registry["defaults"],
        "draft_generation": generation,
    })


def _sign_off_request(registry, build_id, preview, *, assumptions=None, parent=None, expected_head=None, generation=1, note="Reviewed model assumptions"):
    from caos.contracts import ModelSignOffRequest

    return ModelSignOffRequest.model_validate({
        "build_id": build_id,
        "parent_revision_id": parent,
        "registry_version": registry["version"],
        "registry_digest": registry["digest"],
        "assumptions": assumptions if assumptions is not None else registry["defaults"],
        "draft_generation": generation,
        "preview_digest": preview["preview_digest"],
        "expected_head_revision_id": expected_head,
        "note": note,
    })


def _scenario_request(registry, build_id, shocks, *, generation=3):
    from caos.contracts import ModelScenarioRequest

    return ModelScenarioRequest.model_validate({
        "build_id": build_id,
        "base_revision_id": None,
        "registry_version": registry["version"],
        "registry_digest": registry["digest"],
        "shocks": shocks,
        "draft_generation": generation,
    })


def _one_way_request(registry, build_id, available, *, minimum, maximum, step, output_id="total_leverage", generation=4):
    from caos.contracts import OneWaySensitivityRequest

    return OneWaySensitivityRequest.model_validate({
        "build_id": build_id,
        "base_revision_id": None,
        "registry_version": registry["version"],
        "registry_digest": registry["digest"],
        "assumption_id": available["assumption_id"],
        "case": available["case"],
        "period_scope": available["period_id"],
        "minimum": minimum,
        "maximum": maximum,
        "step": step,
        "output_id": output_id,
        "draft_generation": generation,
    })


def _shifted_defaults(registry, delta: float = 0.001):
    rows = copy.deepcopy(registry["defaults"])
    target = next(row for row in rows if row["status"] == "READY" and row["case"] == "BASE")
    target["value"] = float(target["value"]) + delta
    return rows


async def _accepted_case(engine, store):
    """Seed a case, run FULL_CREDIT with scripted canonical outputs (spec hook), accept."""
    case, _source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"])
    snapshot = await engine.accept(run["id"], actor="analyst")
    return case, run, snapshot


async def _built_case(models, engine, store):
    case, _run, _snapshot = await _accepted_case(engine, store)
    queued = models.queue_build(case["id"], "analyst")
    build = models.run_build_for_tests(queued["id"])
    return case, build


async def _second_build(models, engine, case):
    run = await engine.run_scripted_for_tests(case["id"])
    await engine.accept(run["id"], actor="analyst")
    queued = models.queue_build(case["id"], "analyst")
    return models.run_build_for_tests(queued["id"])


# --- pure calculation guards (invariant 7) ----------------------------------------


def test_finite_guards_reject_non_finite_and_zero_denominators():
    """NaN/Inf never propagate; falsy-but-real numbers (0, False) are accepted."""
    from caos.models.engine import is_finite_number, safe_ratio

    assert is_finite_number(0) and is_finite_number(False) and is_finite_number(1e308)
    for bad in (float("nan"), float("inf"), float("-inf"), "1", None, [1]):
        assert not is_finite_number(bad)
    assert safe_ratio(3, 2) == 1.5
    assert safe_ratio(1, 0) is None
    assert safe_ratio(float("nan"), 2) is None
    assert safe_ratio(2, float("inf")) is None


def test_json_value_rejects_decimal_that_overflows_float():
    from caos.models.engine import json_value

    with pytest.raises(Exception):
        json_value(Decimal("1e9999"))
    assert json_value(Decimal("1.5")) == 1.5


@pytest.mark.parametrize("operand", ["total_debt", "ffo", "adjusted_ebitda", "segment_growth"])
def test_finite_operand_guard_names_the_offending_operand(operand):
    """Calculation-boundary finiteness guard raises a typed error naming the operand class."""
    from caos.models.engine import CpModelV3Error, finite_operand

    with pytest.raises(CpModelV3Error, match=operand):
        finite_operand(Decimal("NaN"), operand)
    with pytest.raises(CpModelV3Error, match=operand):
        finite_operand(Decimal("Infinity"), operand)
    assert finite_operand(Decimal("1.5"), operand) == Decimal("1.5")


# --- methodology bundle and assumption registry -----------------------------------


def test_deploy_v_bundle_verifies_pinned_digests_and_rejects_symlink_paths(tmp_path):
    from caos.models.engine import CpModelBundle

    assert CpModelBundle(DEPLOY_V).verify_integrity() == [], "zero digest mismatches"
    mirror = tmp_path / "deploy_v"
    shutil.copytree(DEPLOY_V, mirror)
    outside = tmp_path / "outside.md"
    outside.write_text("evil", encoding="utf-8")
    target = mirror / "skills" / "cp-model" / "SKILL.md"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(Exception, match="symlink"):
        CpModelBundle(mirror).resolve_declared_file("cp-model", "SKILL.md")


def test_golden_cp_model_fixtures_pass_vendor_validation():
    assert _validate(_bundle()) == ()


def test_assumption_registry_is_versioned_complete_and_explicit_about_gaps():
    registry = _bundle().assumption_registry

    assert registry["version"] == "cp-model-assumptions.v1"
    assert len(registry["digest"]) == 64
    definitions = registry["definitions"]
    assert len({item["assumption_id"] for item in definitions}) == len(definitions)
    assert {item["family"] for item in definitions} == {"OPERATING", "CASH_FLOW", "RATES", "CAPITAL", "LIQUIDITY", "COVENANT"}
    assert all(item["cases"] == ["BASE", "DOWNSIDE"] for item in definitions)
    required_keys = {"unit", "hard_min", "hard_max", "sensitivity_default", "required_authority", "allowed_statuses", "degradation", "affected_outputs"}
    assert all(required_keys <= item.keys() for item in definitions)
    covenant = next(item for item in definitions if item["assumption_id"] == "covenant.max_total_leverage")
    assert covenant["degradation"]["gap_code"] == "COVENANT_DEFINITION_UNAVAILABLE"


def test_assumption_registry_reads_are_defensive_copies_with_stable_digest():
    bundle = _bundle()
    exposed = bundle.assumption_registry
    pinned_digest = exposed["digest"]
    original = exposed["definitions"][0]["degradation"]["gap_code"]
    exposed["definitions"][0]["degradation"]["gap_code"] = "MUTATED"

    fresh = _bundle().assumption_registry
    assert fresh["definitions"][0]["degradation"]["gap_code"] == original
    assert fresh["digest"] == pinned_digest
    assert bundle.calculation_runtime["assumption_registry_digest"] == pinned_digest


def test_cp2g_docs_publish_one_registry_interface():
    from caos.models.engine import CpModelBundle  # noqa: F401 — spec anchor: the doc-lint rides the ported bundle

    header = (
        "driver_id | slot_id | case | period_id | fiscal_year | value | unit | "
        "assumption_id | status | source_id | source_locator | as_of | gap_code"
    )
    cp2g = DEPLOY_V / "skills" / "cp-2g-forward-credit-model"
    documents = (
        cp2g / "SKILL.md",
        cp2g / "references" / "REF_CP-2G_STEPS.md",
        cp2g / "references" / "CP-2G_ForwardCreditModel.schema.md",
    )
    for document in documents:
        text = document.read_text(encoding="utf-8")
        assert header in text, document
        assert "cp-model-assumptions.v1" in text, document
        assert "exactly three forecast years" in text.casefold(), document
        assert "COVENANT_DEFINITION_UNAVAILABLE" in text, document
    cp_model_skill = (DEPLOY_V / "skills" / "cp-model" / "SKILL.md").read_text(encoding="utf-8")
    assert "**Required upstream:** CP-1, CP-1A, CP-1B, CP-2, CP-2B, CP-2G" in cp_model_skill


# --- fail-closed input validation -------------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("| PERCENT_DECIMAL | operating.revenue_growth.division_1 |", "| CURRENCY_MM | operating.revenue_growth.division_1 |", "unit"),
        ("| 0.05 | PERCENT_DECIMAL | operating.revenue_growth.division_1 |", "| NaN | PERCENT_DECIMAL | operating.revenue_growth.division_1 |", "finite"),
        ("| 0.05 | PERCENT_DECIMAL | operating.revenue_growth.division_1 |", "| 9 | PERCENT_DECIMAL | operating.revenue_growth.division_1 |", "bounds"),
    ],
)
def test_assumption_inputs_fail_closed_on_unit_nonfinite_and_bounds(old, new, message):
    errors = _validate(_bundle(), cp2g=_read("cp2g.md").replace(old, new, 1))
    assert any(message in error.casefold() for error in errors)


@pytest.mark.parametrize(
    ("assumption_id", "status", "gap_code"),
    [
        ("operating.adjusted_ebitda_margin", "NOT_APPLICABLE", ""),
        ("capital.contractual_amortization", "UNAVAILABLE", "ASSUMPTION_AUTHORITY_UNAVAILABLE"),
    ],
)
def test_required_assumptions_reject_non_ready_statuses(assumption_id, status, gap_code):
    cp2g = _mutate_cp2g_assumption(
        _read("cp2g.md"), assumption_id,
        status=status, value="", source_id="", source_locator="", as_of="", gap_code=gap_code,
    )
    errors = _validate(_bundle(), cp2g=cp2g)
    assert any("status" in error and "allowed" in error for error in errors)


def test_segment_slot_discipline_is_enforced_at_validation_and_calculation(tmp_path):
    """Rows 129+130 merged (one guarantee): segment slot discipline holds independently
    at validate() and at the calculate() boundary — the calc node trusts nothing."""
    from caos.models.engine import CpModelV3Error

    bundle = _bundle()
    model, calculations = bundle.calculate(_forecast_paths())
    assert calculations.for_column("BASE::FY2025").values
    assert model.segment_forecast_slots == {"services": "DIVISION_1"}

    na_active = _mutate_cp2g_assumption(
        _read("cp2g.md"), "operating.revenue_growth.division_1",
        status="NOT_APPLICABLE", value="", source_id="", source_locator="", as_of="", gap_code="",
    )
    assert any("active slot DIVISION_1 must be READY" in error for error in _validate(bundle, cp2g=na_active))
    with pytest.raises(CpModelV3Error, match="active slot DIVISION_1"):
        bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-2G": na_active}))

    ready_inactive = _mutate_cp2g_assumption(
        _read("cp2g.md"), "operating.revenue_growth.division_2",
        status="READY", value="0", source_id="SRC-1", source_locator="page:42", as_of="2025-02-15", gap_code="",
    )
    assert any("inactive slot DIVISION_2 must be NOT_APPLICABLE" in error for error in _validate(bundle, cp2g=ready_inactive))
    with pytest.raises(CpModelV3Error, match="inactive slot DIVISION_2"):
        bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-2G": ready_inactive}))


def test_unsegmented_issuers_forecast_from_consolidated_growth_only(tmp_path):
    """Rows 131+132 merged (one guarantee): unsegmented slot mapping fails closed both
    ways — READY consolidated calculates, division growth or NA consolidated rejects."""
    from caos.models.engine import CpModelV3Error

    bundle = _bundle()
    cp1 = _unsegmented_cp1()
    good_cp2g = _unsegmented_cp2g()
    assert _validate(bundle, cp1=cp1, cp2g=good_cp2g) == ()
    model, calculations = bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-1": cp1, "CP-2G": good_cp2g}))
    assert model.segments == ()
    assert calculations.for_column("BASE::FY2025").values["revenue"] > 0

    bad_errors = _validate(bundle, cp1=cp1)  # golden CP-2G: division growth READY, consolidated NA
    assert any("inactive slot DIVISION_1 must be NOT_APPLICABLE" in error for error in bad_errors)
    assert any("unsegmented issuer requires READY consolidated growth" in error for error in bad_errors)
    with pytest.raises(CpModelV3Error, match="unsegmented issuer"):
        bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-1": cp1}))


# --- calculation boundary ---------------------------------------------------------


@pytest.mark.parametrize(
    "tamper",
    ["segment_missing", "segment_not_ready", "segment_nan", "consolidated_missing", "consolidated_not_ready", "consolidated_infinity"],
)
def test_calculation_boundary_rejects_invalid_active_growth(tmp_path, tamper):
    """Rows 133+134 merged: the calc boundary raises a typed error naming the slot for
    missing, not-READY, and non-finite active growth — without relying on validate()."""
    from caos.models.engine import CpModelV3Error

    bundle = _bundle()
    overrides: dict[str, str] = {}
    if tamper.startswith("segment"):
        slot, assumption_id, cp2g = "DIVISION_1", "operating.revenue_growth.division_1", _read("cp2g.md")
    else:
        slot, assumption_id = "CONSOLIDATED", "operating.consolidated_revenue_growth"
        overrides["CP-1"] = _unsegmented_cp1()
        cp2g = _unsegmented_cp2g()
    if tamper.endswith("missing"):
        cp2g = _drop_cp2g_assumption(cp2g, assumption_id, case="BASE", period_id="FY2025")
    elif tamper.endswith("not_ready"):
        cp2g = _mutate_cp2g_assumption(cp2g, assumption_id, status="NOT_APPLICABLE", value="", source_id="", source_locator="", as_of="", gap_code="")
    else:
        cp2g = _mutate_cp2g_assumption(cp2g, assumption_id, value="NaN" if tamper == "segment_nan" else "Infinity")
    overrides["CP-2G"] = cp2g

    with pytest.raises(CpModelV3Error, match=slot):
        bundle.calculate(_forecast_paths(tmp_path, overrides=overrides))


def test_allowed_unavailable_liquidity_degrades_to_named_nulls_not_zeros(tmp_path):
    bundle = _bundle()
    cp2g = _mutate_cp2g_assumption(
        _read("cp2g.md"), "liquidity.minimum_operating_cash",
        status="UNAVAILABLE", value="", source_id="", source_locator="", as_of="",
        gap_code="MINIMUM_CASH_DEFINITION_UNAVAILABLE",
    )
    assert _validate(bundle, cp2g=cp2g) == ()
    model, calculations = bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-2G": cp2g}))
    forecast = calculations.for_column("BASE::FY2025")

    assert "MINIMUM_CASH_DEFINITION_UNAVAILABLE" in model.assumption_gaps
    assert forecast.values["minimum_operating_cash"] is None
    assert forecast.values["accessible_liquidity"] is None
    assert forecast.values["liquidity_headroom"] is None
    rendered = bundle.render_workbook(model, calculations, tmp_path / "unavailable.xlsx")
    for output in ("minimum_operating_cash", "accessible_liquidity", "liquidity_headroom"):
        assert (output, "BASE::FY2025") not in rendered.model_cells, "omitted, never zero-filled"


def test_missing_required_forecast_driver_raises_typed_error(tmp_path):
    """Absent required drivers are never defaulted — a typed error names the driver."""
    bundle = _bundle()
    cp2g = _drop_cp2g_assumption(_read("cp2g.md"), "operating.adjusted_ebitda_margin")
    with pytest.raises(Exception, match="adjusted_ebitda_margin"):
        bundle.calculate(_forecast_paths(tmp_path, overrides={"CP-2G": cp2g}))


def test_effective_overlay_recalculates_decision_outputs_consistently():
    bundle = _bundle()
    model, baseline = bundle.calculate(_forecast_paths())
    effective = [dataclasses.asdict(item) for item in model.effective_assumptions]
    for item in effective:
        if item["assumption_id"] == "operating.adjusted_ebitda_margin" and item["case"] == "BASE" and item["period_id"] == "FY2025":
            item["value"] = Decimal("0.30")
        if item["assumption_id"] == "liquidity.minimum_operating_cash" and item["case"] == "BASE" and item["period_id"] == "FY2025":
            item["value"] += Decimal("10")
    adjusted_model, adjusted = bundle.calculate(_forecast_paths(), effective_assumptions=effective)
    base = baseline.for_column("BASE::FY2025")
    changed = adjusted.for_column("BASE::FY2025")

    assert changed.values["revenue"] == base.values["revenue"], "revenue untouched by margin overlay"
    assert changed.values["adjusted_ebitda_calc"] > base.values["adjusted_ebitda_calc"]
    assert changed.values["fcf"] > base.values["fcf"]
    assert changed.values["liquidity_headroom"] == (
        base.values["liquidity_headroom"] + changed.values["fcf"] - base.values["fcf"] - 10
    ), "headroom identity holds under the overlay"
    assert changed.values["net_debt"] < base.values["net_debt"]
    assert changed.credit_metrics["total_leverage"] < base.credit_metrics["total_leverage"]
    assert changed.credit_metrics["interest_coverage"] > base.credit_metrics["interest_coverage"]
    assert changed.credit_metrics["covenant_headroom"] is None
    assert "COVENANT_DEFINITION_UNAVAILABLE" in adjusted_model.assumption_gaps


def test_zero_denominators_yield_none_metrics_and_nonfinite_cp1_fails_validation(tmp_path):
    """Row 138: zero denominators give None (never NaN/Inf), rendered cells omit the
    metric, no IFERROR masking anywhere, and a NaN CP-1 operand fails validation."""
    bundle = _bundle()
    model, _ = bundle.calculate(_forecast_paths())
    effective = [dataclasses.asdict(item) for item in model.effective_assumptions]
    for item in effective:
        if item["case"] == "BASE" and item["period_id"] == "FY2025" and item["assumption_id"] in {
            "operating.adjusted_ebitda_margin", "rates.base_rate", "rates.debt_spread",
        }:
            item["value"] = Decimal("0")
    zero_model, zero_calculations = bundle.calculate(_forecast_paths(), effective_assumptions=effective)
    zero = zero_calculations.for_column("BASE::FY2025")
    assert zero.values["adjusted_ebitda_calc"] == Decimal("0")
    assert zero.credit_metrics["total_leverage"] is None
    assert zero.credit_metrics["net_leverage"] is None
    assert zero.credit_metrics["interest_coverage"] is None

    rendered = bundle.render_workbook(zero_model, zero_calculations, tmp_path / "zero.xlsx")
    for metric in ("total_leverage", "net_leverage", "interest_coverage"):
        assert (metric, "BASE::FY2025") not in rendered.model_cells
    assert all("IFERROR" not in item.formula for item in rendered.formulas), "no error masking"

    invalid = _validate(
        bundle,
        cp1=_read("cp1.md").replace("| adjusted_ebitda | FY2024_Q4 | 27 |", "| adjusted_ebitda | FY2024_Q4 | NaN |", 1),
    )
    assert any("finite" in error.casefold() for error in invalid)


def test_first_breach_identity_family_sign_and_committee_visibility(tmp_path):
    """Rows 140+142 merged: breach records pin threshold identity with the family sign
    convention, and both cases' breach ids surface in snapshot, audit, and checks."""
    bundle = _bundle()
    paths = _forecast_paths(tmp_path, overrides={"CP-2G": _cp2g_with_ready_covenant("1")})
    model, _ = bundle.calculate(paths)
    effective = [dataclasses.asdict(item) for item in model.effective_assumptions]
    for item in effective:
        if item["assumption_id"] == "liquidity.minimum_operating_cash" and item["case"] == "BASE" and item["period_id"] == "FY2025":
            item["value"] = Decimal("1000")
    breached_model, calculations = bundle.calculate(paths, effective_assumptions=effective)

    base_breaches = calculations.first_breaches["BASE"]
    assert {item.threshold_id for item in base_breaches} == {"liquidity.minimum_operating_cash", "covenant.max_total_leverage"}
    for item in base_breaches:
        assert item.case == "BASE"
        expected = item.actual - item.limit if item.threshold_id == "liquidity.minimum_operating_cash" else item.limit - item.actual
        assert item.headroom == expected, "family-correct headroom sign"
    downside_breaches = calculations.first_breaches["DOWNSIDE"]
    assert downside_breaches, "the covenant cap must also breach in DOWNSIDE"

    payload = bundle.serialize_workbook(breached_model, calculations)
    for title in ("Credit Snapshot", "_AUDIT", "_CHECKS"):
        tab = _tab(payload, title)
        for item in (*base_breaches, *downside_breaches):
            assert item.threshold_id in tab, (title, item.threshold_id)


def test_forecast_addbacks_are_driver_sourced_and_history_invariant():
    bundle = _bundle()
    model, _ = bundle.calculate(_forecast_paths())
    driver = next(
        item for item in model.effective_assumptions
        if item.assumption_id.endswith("identified_addbacks") and item.case == "BASE" and item.period_id == "FY2025"
    )
    totals = set()
    for addbacks in ((), tuple(model.addbacks)):
        variant = dataclasses.replace(model, addbacks=addbacks)
        forecast = bundle.calculate_model(variant).for_column("BASE::FY2025")
        assert forecast.values["total_addbacks"] == driver.value
        assert forecast.values["adjusted_ebitda_variance"] == 0
        totals.add(forecast.values["total_addbacks"])
    assert len(totals) == 1, "forecast addbacks are invariant to the historical series"


def test_workbook_pins_registry_identity_and_cell_expectations_match_engine(tmp_path):
    bundle = _bundle()
    model, calculations = bundle.calculate(_forecast_paths())
    rendered = bundle.render_workbook(model, calculations, tmp_path / "parity.xlsx")
    for item in rendered.formulas:
        assert item.expected == calculations.for_column(item.column_id).values[item.semantic_id], (
            "every decision-output cell expectation equals the Python calculation"
        )
    assert ("covenant_headroom", "BASE::FY2025") not in rendered.model_cells, "unavailable covenant cell omitted"

    payload = bundle.serialize_workbook(model, calculations)
    registry = bundle.assumption_registry
    audit_tab = _tab(payload, "_AUDIT")
    assert registry["version"] in audit_tab and registry["digest"] in audit_tab
    assert str(bundle.calculation_runtime["version"]) in audit_tab
    inputs_tab = _tab(payload, "_INPUTS")
    for item in model.effective_assumptions:
        assert item.assumption_id in inputs_tab, "_INPUTS rows carry every effective assumption"


def test_debt_schedule_reconciles_with_a_disclosed_unallocated_line():
    bundle = _bundle()
    _model, calculations = bundle.calculate(_forecast_paths())
    forecast = calculations.for_column("BASE::FY2025")
    rows = forecast.debt_schedule
    assert sum(row.value for row in rows) == forecast.values["total_debt_reported"]
    unallocated = [row for row in rows if "unallocated" in row.label.casefold()]
    assert len(unallocated) == 1 and unallocated[0].value != 0, "the plug is a separate disclosed line"
    assert "not inferred" in unallocated[0].caption.casefold(), "security/seniority never inferred"


def test_worksheet_serialization_requires_no_external_binaries(monkeypatch):
    monkeypatch.setenv("PATH", "")
    bundle = _bundle()
    model, calculations = bundle.calculate(_forecast_paths())
    payload = bundle.serialize_workbook(model, calculations)
    assert payload["qa"]["status"] == "PASS"
    titles = {tab["title"] for tab in payload["payload"]["tabs"]}
    assert {"Credit Snapshot", "Model", "KPIs", "Assumptions"} <= titles
    model_tab = next(tab for tab in payload["payload"]["tabs"] if tab["title"] == "Model")
    assert model_tab["cells"]
    assert all("semantic_id" in cell for cell in model_tab["cells"])
    assert any("SRC-1" in json.dumps(cell.get("source_refs", [])) for cell in model_tab["cells"])


# --- CP-2B derived projection -----------------------------------------------------


def test_cp2b_projection_preserves_registers_and_pins_upstream_digest():
    from caos.models.engine import project_cp2b

    bundle = _bundle()
    cp2a = _read("cp2a.md")
    upstream_digest = "a" * 64
    projected = project_cp2b(cp2a, run_id="run-cp-model-fixture", cp2a_artifact_digest=upstream_digest, bundle=bundle)

    assert upstream_digest in projected
    source_region = cp2a[cp2a.index("### T5.1"): cp2a.index("## Evidence Trace")]
    assert source_region in projected, "the register region carries over byte-for-byte"
    for table_id in ("T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "T5.6", "T5.7"):
        assert projected.count(f"### {table_id}") == 1
    result = bundle.validate(_read("cp1.md"), _read("cp1a.md"), _read("cp1b.md"), _read("cp2.md"), projected)
    assert tuple(result.errors) == ()


@pytest.mark.parametrize("defect", ["incomplete", "malformed"])
def test_cp2b_projection_fails_closed_on_incomplete_or_malformed_registers(defect):
    """Rows 148+149 merged: the projection rejects missing registers and rows whose
    cell arity disagrees with the header — no partial projection ever exists."""
    from caos.models.engine import ModelInputError, project_cp2b

    cp2a = _read("cp2a.md")
    if defect == "incomplete":
        start, end = cp2a.index("### T5.6"), cp2a.index("### T5.7")
        cp2a, match = cp2a[:start] + cp2a[end:], "T5.1 through T5.7"
    else:
        cp2a = cp2a.replace(
            "| EVT-1 | Covenant test | Medium | High | Medium High |",
            "| EVT-1 | Covenant test | Medium | High |",
        )
        match = "row has 4 cells; expected 5"
    with pytest.raises(ModelInputError, match=match):
        project_cp2b(cp2a, run_id="run-cp-model-fixture", cp2a_artifact_digest="a" * 64, bundle=_bundle())


def test_cp2b_projection_never_escalates_restricted_qa():
    from caos.models.engine import ModelInputError, project_cp2b

    cp2a = (
        _read("cp2a.md")
        .replace("confidence_score: 85", "confidence_score: 50", 1)
        .replace("confidence_band: High", "confidence_band: Low", 1)
        .replace("qa_status: Passed", "qa_status: Restricted", 1)
    )
    with pytest.raises(ModelInputError, match="not ready for CP-MODEL"):
        project_cp2b(cp2a, run_id="run-cp-model-fixture", cp2a_artifact_digest="a" * 64, bundle=_bundle())


# --- build queue, readiness, and build authority ----------------------------------


async def test_accepted_full_credit_queues_and_builds_an_idempotent_content_addressed_model(models, engine, store):
    """Rows 154 (+165's model half): queueing is idempotent per accepted snapshot, the
    built payload is content-addressed, QA gates READY, and the accepted snapshot
    carries every canonical module artifact."""
    models.fail_next_queue_for_tests()  # suppress the accept-time auto-queue so created flags are observable
    case, _run, snapshot = await _accepted_case(engine, store)
    assert {a["module_id"] for a in snapshot["artifacts"]} >= {"CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2G"}
    assert models.readiness(case["id"])["status"] == "READY_TO_BUILD"

    first = models.queue_build(case["id"], "analyst")
    duplicate = models.queue_build(case["id"], "analyst")
    assert first["created"] is True and duplicate["created"] is False
    assert duplicate["id"] == first["id"]
    assert len(models.list_builds(case["id"])) == 1

    built = models.run_build_for_tests(first["id"])
    assert built["status"] == "READY"
    assert built["payload_digest"] == _digest(built["payload"])
    assert built["qa"]["status"] == "PASS"
    assert models.readiness(case["id"])["status"] == "READY"


async def test_readiness_binds_to_the_latest_accepted_snapshot(models, engine, store):
    case, _run1, snap1 = await _accepted_case(engine, store)
    store.update_case(case["id"], visible_snapshot_id=snap1["id"])
    run2 = await engine.run_scripted_for_tests(case["id"])
    snap2 = await engine.accept(run2["id"], actor="analyst")

    readiness = models.readiness(case["id"])
    assert readiness["status"] == "READY_TO_BUILD"
    assert readiness["snapshot_id"] == snap2["id"], "readiness follows the latest ACCEPTED snapshot"
    assert store.get_case(case["id"])["visible_snapshot_id"] == snap1["id"], "the visible pointer is untouched"


async def test_provider_failure_is_bounded_and_leaks_nothing_into_the_run(engine, store, provider):
    case, _source = seed_case_with_source(store)

    def boom(request):
        raise RuntimeError("provider-secret-XYZZY: internal stack")

    provider.script = [boom]
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "CANONICAL_GENERATION_FAILED"
    assert record["error"].get("module_id")
    assert "XYZZY" not in json.dumps(record), "provider internals never persist"


async def test_queue_build_rejects_cross_case_and_superseded_authority(models, engine, store):
    case_a, _run_a, snap_a1 = await _accepted_case(engine, store)
    _case_b, _run_b, snap_b = await _accepted_case(engine, store)

    with pytest.raises(Exception, match="MODEL_BUILD_INVALID"):
        models.queue_build_pinned_for_tests(case_a["id"], snapshot_id=snap_b["id"])

    run_a2 = await engine.run_scripted_for_tests(case_a["id"])
    await engine.accept(run_a2["id"], actor="analyst")  # supersedes snap_a1
    with pytest.raises(Exception, match="MODEL_BUILD_INVALID"):
        models.queue_build_pinned_for_tests(case_a["id"], snapshot_id=snap_a1["id"])

    cited = {build.get("snapshot_id") for build in models.list_builds(case_a["id"])}
    assert snap_b["id"] not in cited and snap_a1["id"] not in cited, "no build record for either refusal"


async def test_model_and_workflow_jobs_share_one_admission_budget(models, engine, store):
    from caos.engine.budget import MAX_ACTIVE_JOBS

    models.fail_next_queue_for_tests()
    case, _run, _snapshot = await _accepted_case(engine, store)
    engine.fill_admission_slots_for_tests(MAX_ACTIVE_JOBS - 1)
    queued = models.queue_build(case["id"], "analyst")  # the model job takes the last slot
    other, _ = seed_case_with_source(store)
    with pytest.raises(Exception, match="ADMISSION|BUSY"):
        await engine.start_run(case_id=other["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    models.run_build_for_tests(queued["id"])  # completion returns the capacity
    run = await engine.start_run(case_id=other["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    assert run["id"]


# --- acceptance queue (accept -> commit -> queue -> dispatch) ---------------------


async def test_manual_model_request_reschedules_the_existing_queued_build(client, models, engine, store):
    case, _run, _snapshot = await _accepted_case(engine, store)  # accept auto-queues one build
    builds = models.list_builds(case["id"])
    assert [b["status"] for b in builds] == ["QUEUED"]

    response = client.post(f"/api/cases/{case['id']}/models", json={}, headers=_ANALYST)
    assert response.status_code == 202
    assert response.json()["created"] is False
    assert response.json()["id"] == builds[0]["id"]
    assert len(models.list_builds(case["id"])) == 1, "no duplicate build"
    assert models.dispatch_log_for_tests().count(builds[0]["id"]) == 2, "the existing job is re-dispatched"


async def test_acceptance_commits_before_queueing_and_duplicate_accept_is_idempotent(models, engine, store):
    observed: list[str | None] = []
    models.on_queue_for_tests(lambda case_id: observed.append(store.get_case(case_id)["accepted_snapshot_id"]))
    case, run, snapshot = await _accepted_case(engine, store)
    assert observed == [snapshot["id"]], "acceptance is durable before the queue step runs"

    again = await engine.accept(run["id"], actor="analyst")
    assert again["id"] == snapshot["id"]
    builds = models.list_builds(case["id"])
    assert len(builds) == 1
    assert models.dispatch_log_for_tests().count(builds[0]["id"]) == 1, "dispatched exactly once"


async def test_acceptance_survives_queue_failure_and_manual_retry(models, engine, store):
    models.fail_next_queue_for_tests()
    case, _run, snapshot = await _accepted_case(engine, store)
    assert store.get_case(case["id"])["accepted_snapshot_id"] == snapshot["id"], "queue failure never rolls back acceptance"
    assert models.list_builds(case["id"]) == []
    assert models.readiness(case["id"])["status"] == "READY_TO_BUILD"

    retried = models.queue_build(case["id"], "analyst")
    assert retried["created"] is True
    assert len(models.list_builds(case["id"])) == 1


async def test_acceptance_survives_dispatch_failure_with_a_retryable_queued_build(models, engine, store):
    models.fail_next_dispatch_for_tests()
    case, _run, snapshot = await _accepted_case(engine, store)
    assert store.get_case(case["id"])["accepted_snapshot_id"] == snapshot["id"]
    builds = models.list_builds(case["id"])
    assert [b["status"] for b in builds] == ["QUEUED"], "one durable QUEUED build survives the dispatch crash"

    retried = models.queue_build(case["id"], "analyst")
    assert retried["created"] is False and retried["id"] == builds[0]["id"]
    assert models.dispatch_log_for_tests()[-1] == builds[0]["id"], "retry re-dispatches, never duplicates"
    assert len(models.list_builds(case["id"])) == 1


async def test_accepting_non_full_credit_queues_nothing(models, engine, store):
    """Row 120 + §10.6: only accepted FULL_CREDIT feeds model builds, and the
    six-module validate_bundle never runs for any other pathway."""
    case, _source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"], pathway="EARNINGS_UPDATE")
    await engine.accept(run["id"], actor="analyst")

    assert models.list_builds(case["id"]) == []
    assert models.validate_bundle_calls_for_tests() == []
    with pytest.raises(Exception, match="MODEL_BUILD_INVALID|NOT_READY"):
        models.queue_build(case["id"], "analyst")


async def test_invalid_canonical_inputs_commit_acceptance_but_never_queue(models, engine, store):
    case, _source = seed_case_with_source(store)
    models.force_readiness_for_tests(case["id"], "CANONICAL_MODEL_INPUTS_INVALID")
    run = await engine.run_scripted_for_tests(case["id"])
    snapshot = await engine.accept(run["id"], actor="analyst")

    assert store.get_case(case["id"])["accepted_snapshot_id"] == snapshot["id"], "the accept write still commits"
    assert models.list_builds(case["id"]) == [], "invalid canonical model inputs are never queued"
    assert models.readiness(case["id"])["status"] == "CANONICAL_MODEL_INPUTS_INVALID"


# --- build completion, failure records, and authority order -----------------------


@pytest.mark.parametrize(
    "corruption",
    ["missing_qa", "digest_mismatch", "unknown_field", "malformed_tabs", "incomplete_cells", "non_finite_value"],
)
async def test_build_completion_refuses_invalid_results_and_stays_building(models, engine, store, corruption):
    models.fail_next_queue_for_tests()
    case, _run, _snapshot = await _accepted_case(engine, store)
    queued = models.queue_build(case["id"], "analyst")
    result = models.valid_build_result_for_tests(queued["id"])
    if corruption == "missing_qa":
        result.pop("qa")
    elif corruption == "digest_mismatch":
        result["payload_digest"] = "0" * 64
    elif corruption == "unknown_field":
        result["forged_authority"] = True
    elif corruption == "malformed_tabs":
        result["payload"]["tabs"] = "not-a-list"
    elif corruption == "incomplete_cells":
        result["payload"]["tabs"][0]["cells"] = [{"incomplete": True}]
    else:
        result["payload"]["tabs"][0]["cells"][0]["value"] = float("nan")

    with pytest.raises(Exception, match="MODEL_RESULT_INVALID"):
        models.complete_build_for_tests(queued["id"], result)
    record = models.build(queued["id"])
    assert record["status"] in {"QUEUED", "BUILDING"}, "no partial completion"
    assert record.get("payload") is None


async def test_stored_build_results_are_isolated_from_caller_mutation(models, engine, store):
    models.fail_next_queue_for_tests()
    case, _run, _snapshot = await _accepted_case(engine, store)
    queued = models.queue_build(case["id"], "analyst")
    result = models.valid_build_result_for_tests(queued["id"])
    models.complete_build_for_tests(queued["id"], result)
    stored = copy.deepcopy(models.worksheet(queued["id"]))

    result["payload"]["tabs"][0]["title"] = "TAMPERED"
    result["qa"]["status"] = "FAIL"
    assert models.worksheet(queued["id"]) == stored, "post-completion caller mutation is invisible"


async def test_failure_records_are_bounded_and_export_failure_never_demotes_the_build(models, engine, store):
    case, build = await _built_case(models, engine, store)
    with pytest.raises(Exception, match="MODEL_ERROR_INVALID"):
        models.fail_build_for_tests(build["id"], code="MODEL_CALCULATION_FAILED", detail="d" * 100_000)
    assert models.build(build["id"])["status"] == "READY", "an oversized failure record changes nothing"

    models.queue_export(build["id"], "analyst")
    models.fail_next_export_for_tests()
    models.run_export_for_tests(build["id"])
    record = models.build(build["id"])
    assert record["status"] == "READY", "export failure never demotes calculation authority"
    assert record["export"]["status"] == "FAILED"
    requeued = models.queue_export(build["id"], "analyst")
    assert requeued["export"]["status"] == "QUEUED"


def test_build_authority_order_is_server_assigned_and_unexposed(models, store):
    case = store.create_case("Order", "Issuer", "Services", "analyst")
    same_instant = "2026-08-26T00:00:00+00:00"
    models.insert_ready_build_for_tests(case["id"], build_id="zzz-created-first", queued_at=same_instant)
    models.insert_ready_build_for_tests(case["id"], build_id="aaa-created-second", queued_at=same_instant)

    current = models.current_build(case["id"])
    assert current["id"] == "aaa-created-second", "creation order wins over timestamps and id collation"
    assert "authority_order" not in current
    assert all("authority_order" not in build for build in models.list_builds(case["id"]))


async def test_queue_build_rejects_caller_supplied_authority_fields(client, models, engine, store):
    case, _run, _snapshot = await _accepted_case(engine, store)
    before_builds = models.list_builds(case["id"])
    before_audit = store.audit_trail()

    response = client.post(f"/api/cases/{case['id']}/models", json={"authority_order": 99}, headers=_ANALYST)
    assert response.status_code == 422
    assert models.list_builds(case["id"]) == before_builds
    assert store.audit_trail() == before_audit


async def test_concurrent_queue_is_idempotent_and_attributes_the_winner(models, engine, store):
    models.fail_next_queue_for_tests()
    case, _run, _snapshot = await _accepted_case(engine, store)
    first, second = await asyncio.gather(
        asyncio.to_thread(models.queue_build, case["id"], "analyst-a"),
        asyncio.to_thread(models.queue_build, case["id"], "analyst-b"),
    )
    assert first["id"] == second["id"]
    assert [first["created"], second["created"]].count(True) == 1, "created exactly once"
    winner = "analyst-a" if first["created"] else "analyst-b"
    assert models.build(first["id"])["created_by"] == winner
    assert len(models.list_builds(case["id"])) == 1


# --- previews, sign-off, revisions ------------------------------------------------


async def test_preview_and_signoff_share_exact_calculation_and_previews_persist_nothing(models, engine, store):
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    for row in registry["defaults"]:
        assert row["source_context"] is not None
        assert row["source_context_digest"] == _digest(row["source_context"])
        assert row["default_value"] == row["value"] and row["default_status"] == row["status"]

    before_audit = store.audit_trail()
    preview = models.preview(case["id"], _preview_request(registry, build["id"], generation=7))
    assert preview["draft_generation"] == 7 and preview["build_id"] == build["id"]
    assert preview["assumptions_digest"] == _digest(registry["defaults"])
    assert preview["outputs_digest"] == _digest(preview["outputs"])
    assert models.revisions(case["id"]) == [], "previews persist nothing"
    assert store.audit_trail() == before_audit

    signed = models.sign_off(case["id"], _sign_off_request(registry, build["id"], preview, generation=7))
    assert signed["preview_digest"] == preview["preview_digest"]
    assert signed["outputs"] == preview["outputs"], "what you previewed is what you signed"
    assert signed["export"]["status"] == "QUEUED"
    assert len(models.revisions(case["id"])) == 1


async def test_scenario_and_one_way_are_transient_with_registry_guardrails(models, engine, store):
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    available = next(row for row in registry["defaults"] if row["status"] == "READY" and row["case"] == "BASE")
    definition = next(item for item in registry["definitions"] if item["assumption_id"] == available["assumption_id"])
    step = float(definition["sensitivity_default"]["step"])
    shocked_value = float(available["value"]) + 0.001
    before_audit = store.audit_trail()

    scenario = models.scenario(case["id"], _scenario_request(registry, build["id"], [{
        "assumption_id": available["assumption_id"], "case": available["case"],
        "period_id": available["period_id"], "value": shocked_value,
    }]))
    direct_rows = copy.deepcopy(registry["defaults"])
    for row in direct_rows:
        if (row["assumption_id"], row["case"], row["period_id"]) == (available["assumption_id"], available["case"], available["period_id"]):
            row["value"] = shocked_value
    direct = models.preview(case["id"], _preview_request(registry, build["id"], assumptions=direct_rows, generation=3))
    assert scenario["scenario_digest"] == _digest(scenario["scenario"])
    assert scenario["scenario"]["outputs"] == direct["outputs"], "scenario recomputes via the same calc path"

    sensitivity = models.one_way(case["id"], _one_way_request(
        registry, build["id"], available, minimum=float(available["value"]), maximum=float(available["value"]) + step, step=step,
    ))
    assert len(sensitivity["points"]) == 2

    with pytest.raises(Exception, match="MODEL_SENSITIVITY_INVALID"):
        models.one_way(case["id"], _one_way_request(
            registry, build["id"], available, minimum=float(definition["hard_min"]) - 1, maximum=float(available["value"]), step=step,
        ))
    with pytest.raises(Exception, match="MODEL_SENSITIVITY_POINT_LIMIT"):
        models.one_way(case["id"], _one_way_request(
            registry, build["id"], available, minimum=float(available["value"]), maximum=float(available["value"]) + 0.05, step=0.0001,
        ))
    with pytest.raises(Exception, match="MODEL_SENSITIVITY_OUTPUT_INVALID"):
        models.one_way(case["id"], _one_way_request(
            registry, build["id"], available, minimum=float(available["value"]), maximum=float(available["value"]), step=step,
            output_id="not-a-real-output",
        ))
    assert models.revisions(case["id"]) == []
    assert store.audit_trail() == before_audit


async def test_calculations_share_one_aggregate_deadline_without_persistence(models, engine, store):
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    available = next(row for row in registry["defaults"] if row["status"] == "READY" and row["case"] == "BASE")
    step = float(next(d for d in registry["definitions"] if d["assumption_id"] == available["assumption_id"])["sensitivity_default"]["step"])
    before_audit = store.audit_trail()
    models.exceed_calculation_deadline_for_tests()

    with pytest.raises(Exception, match="MODEL_CALCULATION_TIMEOUT"):
        models.preview(case["id"], _preview_request(registry, build["id"]))
    with pytest.raises(Exception, match="MODEL_CALCULATION_TIMEOUT"):
        models.scenario(case["id"], _scenario_request(registry, build["id"], [{
            "assumption_id": available["assumption_id"], "case": available["case"],
            "period_id": available["period_id"], "value": float(available["value"]) + 0.001,
        }]))
    with pytest.raises(Exception, match="MODEL_CALCULATION_TIMEOUT"):
        models.one_way(case["id"], _one_way_request(
            registry, build["id"], available, minimum=float(available["value"]), maximum=float(available["value"]) + step, step=step,
        ))
    assert models.revisions(case["id"]) == []
    assert store.audit_trail() == before_audit


async def test_http_preview_signoff_history_and_stale_head_conflict(client, models, engine, store):
    case, build = await _built_case(models, engine, store)
    registry_response = client.get(
        f"/api/cases/{case['id']}/models/assumption-registry", params={"build_id": build["id"]}, headers=_ANALYST,
    )
    assert registry_response.status_code == 200
    registry = registry_response.json()

    preview_request = {
        "build_id": build["id"], "parent_revision_id": None,
        "registry_version": registry["version"], "registry_digest": registry["digest"],
        "assumptions": registry["defaults"], "draft_generation": 5,
    }
    preview_response = client.post(f"/api/cases/{case['id']}/models/previews", json=preview_request, headers=_ANALYST)
    assert preview_response.status_code == 200

    signoff_request = {
        **preview_request,
        "preview_digest": preview_response.json()["preview_digest"],
        "expected_head_revision_id": None,
        "note": "Signed after earnings review",
    }
    signed_response = client.post(f"/api/cases/{case['id']}/model-revisions/sign-off", json=signoff_request, headers=_ANALYST)
    assert signed_response.status_code == 201
    signed = signed_response.json()
    assert signed["state"] == "ACTIVE"
    assert signed["export"]["status"] == "QUEUED"
    history = client.get(f"/api/cases/{case['id']}/model-revisions", headers=_ANALYST)
    assert history.status_code == 200
    assert history.json()["revisions"] == [signed]

    conflict = client.post(f"/api/cases/{case['id']}/model-revisions/sign-off", json=signoff_request, headers=_ANALYST)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "MODEL_REVISION_CONFLICT"
    assert conflict.json()["detail"]["current"]["id"] == signed["id"], "the conflict carries the head to rebase on"


async def test_sign_off_cas_is_append_only_with_separate_head_and_monotonic_order(models, engine, store):
    """Rows 100+167 merged (one guarantee): the revision ledger is an append-only,
    CAS-guarded chain — head is a separate pointer, numbers are unique-monotonic per
    case, ordering is an explicit server-side authority sequence, stored rows are
    immutable, and exactly one audit event exists per signed revision."""
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    preview1 = models.preview(case["id"], _preview_request(registry, build["id"]))
    signed = models.sign_off(case["id"], _sign_off_request(registry, build["id"], preview1))
    assert signed["revision_number"] == 1 and signed["state"] == "ACTIVE"
    assert len([e for e in store.audit_trail() if e["action"] == "model.revision.signed"]) == 1

    shifted = _shifted_defaults(registry)
    preview2 = models.preview(case["id"], _preview_request(registry, build["id"], assumptions=shifted, parent=signed["id"], generation=2))
    audit_before = store.audit_trail()
    with pytest.raises(Exception, match="MODEL_REVISION_CONFLICT") as conflict:
        models.sign_off(case["id"], _sign_off_request(
            registry, build["id"], preview2, assumptions=shifted, parent=signed["id"], expected_head=None, generation=2,
        ))
    assert conflict.value.current["id"] == signed["id"], "the loser learns the head"
    assert [r["id"] for r in models.revisions(case["id"])] == [signed["id"]], "a losing CAS appends nothing"
    assert store.audit_trail() == audit_before

    second = models.sign_off(case["id"], _sign_off_request(
        registry, build["id"], preview2, assumptions=shifted, parent=signed["id"], expected_head=signed["id"], generation=2,
    ))
    assert second["revision_number"] == 2, "head + 1"
    assert models.head_revision(case["id"])["id"] == second["id"], "head is a separate pointer advanced only by appends"
    assert sorted(r["revision_number"] for r in models.revisions(case["id"])) == [1, 2]
    assert all("authority_order" not in r for r in models.revisions(case["id"]))
    order = store.model_revision_order_for_tests(case["id"])
    assert order == sorted(order) and len(set(order)) == len(order), "explicit monotonic authority sequence"
    with pytest.raises(Exception, match="APPEND_ONLY"):
        store.mutate_model_revision_for_tests(signed["id"], {"note": "rewritten history"})


@pytest.mark.parametrize(
    "field",
    ["input_fingerprint", "payload_digest", "registry_digest", "snapshot_id", "assumptions_digest", "outputs_digest"],
)
async def test_sign_off_validates_exact_current_build_identity(models, engine, store, field):
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    preview = models.preview(case["id"], _preview_request(registry, build["id"]))
    request = _sign_off_request(registry, build["id"], preview)

    models.tamper_build_identity_for_tests(build["id"], field)
    before_audit = store.audit_trail()
    with pytest.raises(Exception, match="MODEL_REVISION_INVALID"):
        models.sign_off(case["id"], request)
    assert models.revisions(case["id"]) == []
    assert store.audit_trail() == before_audit


async def test_sign_off_against_superseded_build_reports_current_build_identity(models, engine, store):
    case, build1 = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build1["id"])
    preview = models.preview(case["id"], _preview_request(registry, build1["id"]))
    build2 = await _second_build(models, engine, case)
    before_audit = store.audit_trail()

    with pytest.raises(Exception, match="MODEL_BUILD_STALE|MODEL_REVISION_CONFLICT") as err:
        models.sign_off(case["id"], _sign_off_request(registry, build1["id"], preview))
    current = err.value.current_build
    assert current["id"] == build2["id"] and current["status"] == "READY", "the refusal names the current authority"
    assert models.revisions(case["id"]) == []
    assert store.audit_trail() == before_audit


async def test_sign_off_serializes_with_a_concurrent_newer_build_completion(models, engine, store):
    """Row 105: sign-off is linearizable with build completion — it either strictly
    precedes the newer build (and is then staled) or observes it and conflicts.
    Never a revision committed from a stale current-build read."""
    case, build1 = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build1["id"])
    preview = models.preview(case["id"], _preview_request(registry, build1["id"]))
    run2 = await engine.run_scripted_for_tests(case["id"])
    await engine.accept(run2["id"], actor="analyst")
    queued2 = models.queue_build(case["id"], "analyst")
    request = _sign_off_request(registry, build1["id"], preview)

    completion, signoff = await asyncio.gather(
        asyncio.to_thread(models.run_build_for_tests, queued2["id"]),
        asyncio.to_thread(models.sign_off, case["id"], request),
        return_exceptions=True,
    )
    assert not isinstance(completion, Exception)
    revisions = models.revisions(case["id"])
    if isinstance(signoff, Exception):
        assert "MODEL" in str(signoff), "the loser gets a typed conflict"
        assert revisions == []
    else:
        assert [r["id"] for r in revisions] == [signoff["id"]]
        assert revisions[0]["build_id"] == build1["id"]
        assert revisions[0]["state"] == "STALE", "a pre-completion revision is staled, never left pinned as current"


async def test_two_concurrent_sign_offs_have_one_atomic_winner(models, engine, store):
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    preview = models.preview(case["id"], _preview_request(registry, build["id"]))
    request_a = _sign_off_request(registry, build["id"], preview, note="Writer A releases")
    request_b = _sign_off_request(registry, build["id"], preview, note="Writer B releases")

    results = await asyncio.gather(
        asyncio.to_thread(models.sign_off, case["id"], request_a),
        asyncio.to_thread(models.sign_off, case["id"], request_b),
        return_exceptions=True,
    )
    winners = [r for r in results if not isinstance(r, Exception)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert losers[0].current["id"] == winners[0]["id"], "the conflict names the winner"
    assert [r["id"] for r in models.revisions(case["id"])] == [winners[0]["id"]]
    assert len([e for e in store.audit_trail() if e["action"] == "model.revision.signed"]) == 1


async def test_signed_export_is_runtime_pinned_hash_verified_and_never_demotes(models, engine, store, settings):
    """Rows 159+160+106 merged (one guarantee cluster): exports run only under the
    signed revision's pinned calculation runtime, failures are bounded and never touch
    the revision's state or head, artifacts are immutable once READY, and only bytes
    matching the recorded sha256 are ever served."""
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    effective = _shifted_defaults(registry)
    preview = models.preview(case["id"], _preview_request(registry, build["id"], assumptions=effective))
    signed = models.sign_off(case["id"], _sign_off_request(registry, build["id"], preview, assumptions=effective))

    models.set_calculation_runtime_for_tests(sha256="f" * 64)  # swap the runtime under the revision
    models.run_export_for_tests(signed["id"])
    failed = models.head_revision(case["id"])
    assert failed["export"]["status"] == "FAILED"
    assert failed["export"]["error"]["code"] == "MODEL_REVISION_EXPORT_RUNTIME_UNAVAILABLE"
    assert models.export_input_reads_for_tests() == 0, "the pin is verified before any input is read"
    assert failed["id"] == signed["id"] and failed["state"] == "ACTIVE", "failure never demotes the revision"
    assert failed["outputs_digest"] == signed["outputs_digest"]

    models.set_calculation_runtime_for_tests(sha256=None)  # restore the pinned runtime
    requeued = models.queue_export(signed["id"], "analyst")
    assert requeued["export"]["status"] == "QUEUED"
    models.run_export_for_tests(signed["id"])
    export = models.head_revision(case["id"])["export"]
    assert export["status"] == "READY"
    stored = (settings.storage_dir / export["vault_key"]).read_bytes()
    assert hashlib.sha256(stored).hexdigest() == export["sha256"]
    assert len(stored) == export["size"]

    unchanged = models.queue_export(signed["id"], "analyst")
    assert unchanged["export"]["status"] == "READY", "re-queue after READY is a no-op"
    assert (settings.storage_dir / export["vault_key"]).read_bytes() == stored, "never re-rendered"

    content, sha = models.download(case["id"], signed["id"])
    assert content == stored and sha == export["sha256"]
    (settings.storage_dir / export["vault_key"]).write_bytes(stored + b"tamper")
    with pytest.raises(Exception, match="MODEL_REVISION_EXPORT_INTEGRITY_FAILED"):
        models.download(case["id"], signed["id"])


async def test_newer_accepted_build_stales_revisions_and_rebase_preview_is_transient(models, engine, store):
    from caos.contracts import ModelRebasePreviewRequest

    case, build1 = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build1["id"])
    preview = models.preview(case["id"], _preview_request(registry, build1["id"]))
    signed = models.sign_off(case["id"], _sign_off_request(registry, build1["id"], preview))
    build2 = await _second_build(models, engine, case)

    assert models.revisions(case["id"])[0]["state"] == "STALE", "newer accepted authority stales the revision"
    with pytest.raises(Exception, match="MODEL_BUILD_STALE"):
        models.preview(case["id"], _preview_request(registry, build1["id"], parent=signed["id"], generation=2))

    before_revisions = models.revisions(case["id"])
    before_audit = store.audit_trail()
    candidate = models.rebase_preview(case["id"], ModelRebasePreviewRequest.model_validate({
        "revision_id": signed["id"], "build_id": build2["id"], "draft_generation": 3,
    }))
    assert candidate["source_revision_id"] == signed["id"]
    assert candidate["build_id"] == build2["id"]
    assert candidate["invalidated"] == []
    assert candidate["preview"] is not None
    assert models.revisions(case["id"]) == before_revisions
    assert store.audit_trail() == before_audit


async def test_rebase_reports_source_context_drift_and_unmapped_assumptions(models, engine, store):
    from caos.contracts import ModelRebasePreviewRequest

    case, build1 = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build1["id"])
    preview = models.preview(case["id"], _preview_request(registry, build1["id"]))
    signed = models.sign_off(case["id"], _sign_off_request(registry, build1["id"], preview))
    build2 = await _second_build(models, engine, case)
    models.evolve_registry_for_tests(
        build2["id"],
        removed=("capital.contractual_amortization",),
        source_context_changed=("operating.adjusted_ebitda_margin",),
    )

    before_revisions = models.revisions(case["id"])
    before_audit = store.audit_trail()
    candidate = models.rebase_preview(case["id"], ModelRebasePreviewRequest.model_validate({
        "revision_id": signed["id"], "build_id": build2["id"], "draft_generation": 3,
    }))
    assert any(item["identity"][0] == "operating.adjusted_ebitda_margin" for item in candidate["changed"])
    invalidated = {item["identity"][0]: item["reason"] for item in candidate["invalidated"]}
    assert invalidated["capital.contractual_amortization"] == "ASSUMPTION_NO_LONGER_MAPS"
    assert candidate["preview"] is None, "auto-preview is suppressed while invalidations exist"
    assert models.revisions(case["id"]) == before_revisions
    assert store.audit_trail() == before_audit


async def test_model_reads_are_case_scoped_and_downloads_are_verified(client, models, engine, store, settings):
    case, build = await _built_case(models, engine, store)
    models.queue_export(build["id"], "analyst")
    models.run_export_for_tests(build["id"])

    assert client.get(f"/api/cases/{case['id']}/models", headers=_ANALYST).status_code == 200
    outsider = {"x-forwarded-user": "stranger", "x-caos-role": "ANALYST"}
    assert client.get(f"/api/cases/{case['id']}/models/{build['id']}", headers=outsider).status_code == 404
    other, _ = seed_case_with_source(store)
    assert client.get(f"/api/cases/{other['id']}/models/{build['id']}", headers=_ANALYST).status_code == 404

    downloaded = client.get(f"/api/cases/{case['id']}/models/{build['id']}/download", headers=_ANALYST)
    assert downloaded.status_code == 200
    export = models.build(build["id"])["export"]
    assert hashlib.sha256(downloaded.content).hexdigest() == export["sha256"]
    assert "no-store" in downloaded.headers.get("cache-control", "")

    (settings.storage_dir / export["vault_key"]).write_bytes(downloaded.content + b"x")
    tampered = client.get(f"/api/cases/{case['id']}/models/{build['id']}/download", headers=_ANALYST)
    assert tampered.status_code == 409
    assert tampered.json()["detail"] == "MODEL_EXPORT_INTEGRITY_FAILED"

    # Anything that is not the recorded regular file is refused with the same
    # typed code. A plain read_bytes raised IsADirectoryError here — an OSError
    # the route's ValueError handler never saw, so this answered 500.
    stored = settings.storage_dir / export["vault_key"]
    stored.unlink()
    stored.mkdir()
    not_a_file = client.get(f"/api/cases/{case['id']}/models/{build['id']}/download", headers=_ANALYST)
    assert not_a_file.status_code == 409
    assert not_a_file.json()["detail"] == "MODEL_EXPORT_INTEGRITY_FAILED"

    stored.rmdir()
    stored.symlink_to(settings.storage_dir / "elsewhere.xlsx")
    symlinked = client.get(f"/api/cases/{case['id']}/models/{build['id']}/download", headers=_ANALYST)
    assert symlinked.status_code == 409, "a symlink standing in for the export is never followed"


# ROW MAPPING
# test_cp_model.py rows:
# test_deploy_v_regeneration_is_current_and_rejects_symlink_paths -> test_deploy_v_bundle_verifies_pinned_digests_and_rejects_symlink_paths
# test_cp_model_fixture_passes_vendor_validation -> test_golden_cp_model_fixtures_pass_vendor_validation
# test_assumption_registry_is_versioned_complete_and_explicit_about_gaps -> test_assumption_registry_is_versioned_complete_and_explicit_about_gaps
# test_assumption_registry_copies_do_not_mutate_methodology_authority -> test_assumption_registry_reads_are_defensive_copies_with_stable_digest
# test_cp2g_methodology_contracts_publish_one_registry_interface -> test_cp2g_docs_publish_one_registry_interface
# test_assumption_registry_inputs_fail_closed -> test_assumption_inputs_fail_closed_on_unit_nonfinite_and_bounds
# test_required_forecast_assumptions_reject_non_ready_statuses -> test_required_assumptions_reject_non_ready_statuses
# test_segmented_forecast_rejects_na_active_slot_before_calculation -> test_segment_slot_discipline_is_enforced_at_validation_and_calculation (merged: one slot-discipline guarantee)
# test_segmented_forecast_requires_inactive_slots_and_consolidated_to_be_na -> test_segment_slot_discipline_is_enforced_at_validation_and_calculation
# test_unsegmented_forecast_requires_consolidated_growth_and_calculates -> test_unsegmented_issuers_forecast_from_consolidated_growth_only (merged: one mapping guarantee)
# test_unsegmented_forecast_rejects_division_growth_and_na_consolidated -> test_unsegmented_issuers_forecast_from_consolidated_growth_only
# test_direct_calculation_rejects_invalid_active_segment_growth -> test_calculation_boundary_rejects_invalid_active_growth (merged with consolidated twin)
# test_direct_calculation_rejects_invalid_active_consolidated_growth -> test_calculation_boundary_rejects_invalid_active_growth
# test_allowed_unavailable_liquidity_degrades_to_named_null_outputs -> test_allowed_unavailable_liquidity_degrades_to_named_nulls_not_zeros
# test_forecast_missing_required_driver_raises_typed_input_error -> test_missing_required_forecast_driver_raises_typed_error
# test_effective_assumption_overlay_recalculates_all_decision_outputs -> test_effective_overlay_recalculates_decision_outputs_consistently
# test_forecast_ratios_and_nonfinite_cp1_operands_fail_closed -> test_zero_denominators_yield_none_metrics_and_nonfinite_cp1_fails_validation, test_finite_guards_reject_non_finite_and_zero_denominators
# test_forecast_calculation_boundary_rejects_nonfinite_operands_locally -> test_finite_operand_guard_names_the_offending_operand, test_calculation_boundary_rejects_invalid_active_growth (non-finite arms)
# test_first_breach_preserves_threshold_identity_for_each_breach_family -> test_first_breach_identity_family_sign_and_committee_visibility (merged: one first-breach guarantee)
# test_forecast_identified_addbacks_are_independent_of_historical_series -> test_forecast_addbacks_are_driver_sourced_and_history_invariant
# test_first_breach_is_visible_and_audited_for_base_and_downside -> test_first_breach_identity_family_sign_and_committee_visibility
# test_registry_workbook_inputs_formulas_checks_and_audit_match_python -> test_workbook_pins_registry_identity_and_cell_expectations_match_engine
# test_forecast_debt_schedule_discloses_and_reconciles_unallocated_movement -> test_debt_schedule_reconciles_with_a_disclosed_unallocated_line
# test_python_runtime_serializes_visible_worksheets_without_libreoffice -> test_worksheet_serialization_requires_no_external_binaries
# test_json_value_rejects_decimal_that_overflows_float -> test_json_value_rejects_decimal_that_overflows_float
# test_cp2b_projection_preserves_complete_registers_and_validates -> test_cp2b_projection_preserves_registers_and_pins_upstream_digest
# test_cp2b_projection_rejects_incomplete_registers -> test_cp2b_projection_fails_closed_on_incomplete_or_malformed_registers (merged: one fail-closed projection guarantee)
# test_cp2b_projection_rejects_malformed_rows -> test_cp2b_projection_fails_closed_on_incomplete_or_malformed_registers
# test_cp2b_projection_does_not_escalate_restricted_qa -> test_cp2b_projection_never_escalates_restricted_qa
# test_canonical_runner_host_owns_identity_lineage_and_bundle_validation -> NOT re-expressed here: host identity stamping is already pinned by test_modules_spec.py::test_host_owns_identity_and_discards_provider_frontmatter; the CP-MODEL bundle-validation half is pinned by test_golden_cp_model_fixtures_pass_vendor_validation + the §10.6 scope assert in test_accepting_non_full_credit_queues_nothing
# test_canonical_runner_rejects_unreturned_model_table_source -> NOT re-expressed here: already pinned by test_modules_spec.py::test_model_facing_tables_may_cite_only_returned_sources
# test_canonical_turn_budget_covers_all_bounded_interactions -> NOT re-expressed here: the turns >= evidence_reads + N + repairs arithmetic is already pinned by test_budget_spec.py::test_route_envelopes_scale_per_module_and_reproduce_legacy_at_n6
# test_accepted_full_credit_queues_and_builds_idempotent_python_model -> test_accepted_full_credit_queues_and_builds_an_idempotent_content_addressed_model
# test_revision_preview_and_signoff_share_exact_calculation_without_transient_rows -> test_preview_and_signoff_share_exact_calculation_and_previews_persist_nothing
# test_scenario_and_sensitivity_are_transient_and_use_registry_guardrails -> test_scenario_and_one_way_are_transient_with_registry_guardrails
# test_preview_and_one_way_share_one_aggregate_request_deadline_without_persistence -> test_calculations_share_one_aggregate_deadline_without_persistence
# test_model_revision_http_preview_signoff_history_and_conflict -> test_http_preview_signoff_history_and_stale_head_conflict (export-scheduling-failure half re-hosted in test_signed_export_is_runtime_pinned_hash_verified_and_never_demotes)
# test_signed_revision_export_uses_overlay_and_stores_hash_verified_workbook -> test_signed_export_is_runtime_pinned_hash_verified_and_never_demotes (merged: one export-integrity guarantee cluster)
# test_revision_download_serves_only_the_verified_buffer -> test_signed_export_is_runtime_pinned_hash_verified_and_never_demotes
# test_new_accepted_build_stales_revision_and_rebase_preview_is_transient -> test_newer_accepted_build_stales_revisions_and_rebase_preview_is_transient
# test_rebase_marks_source_context_changes_and_removed_assumptions_without_persistence -> test_rebase_reports_source_context_drift_and_unmapped_assumptions
# test_latest_accepted_full_credit_uses_validated_canonical_cp2g -> test_readiness_binds_to_the_latest_accepted_snapshot
# test_model_api_is_case_scoped_downloads_verified_export_and_freezes_identity -> test_model_reads_are_case_scoped_and_downloads_are_verified (PARTIAL: the freeze/approval half — freeze pins build id + export sha, approval binds preview_digest + input_fingerprint — re-hosts on the deliverables freeze/filing surface per DECISIONS §1/§11.9 and belongs to the deliverables spec file; the legacy report-era freeze it exercised is cut)
# test_full_credit_fake_provider_run_is_accepted_with_canonical_model_inputs -> test_accepted_full_credit_queues_and_builds_an_idempotent_content_addressed_model (snapshot-completeness + readiness half; per-module execution/token accounting is run-engine surface owned by test_runs_spec.py)
# test_canonical_provider_failure_uses_bounded_run_error -> test_provider_failure_is_bounded_and_leaks_nothing_into_the_run
#
# test_model_acceptance_queue.py rows:
# test_manual_model_request_reschedules_existing_queued_job -> test_manual_model_request_reschedules_the_existing_queued_build
# test_accepting_model_ready_full_credit_queues_after_commit_once -> test_acceptance_commits_before_queueing_and_duplicate_accept_is_idempotent
# test_acceptance_survives_queue_failure_and_manual_retry -> test_acceptance_survives_queue_failure_and_manual_retry
# test_acceptance_survives_schedule_failure_with_retryable_queued_job -> test_acceptance_survives_dispatch_failure_with_a_retryable_queued_build
# test_acceptance_does_not_queue_non_full_credit -> test_accepting_non_full_credit_queues_nothing
# test_acceptance_does_not_queue_not_ready_full_credit -> test_invalid_canonical_inputs_commit_acceptance_but_never_queue
#
# test_model_store.py row:
# test_model_revision_migration_is_append_only_with_separate_head_and_export -> test_sign_off_cas_is_append_only_with_separate_head_and_monotonic_order (merged with the sign-off CAS row: one append-only-ledger guarantee)
#
# test_ledger_contracts.py model rows:
# test_model_result_validation_matrix_and_copy_isolation -> test_build_completion_refuses_invalid_results_and_stays_building, test_stored_build_results_are_isolated_from_caller_mutation
# test_model_errors_and_export_failure_requeue_are_bounded -> test_failure_records_are_bounded_and_export_failure_never_demotes_the_build
# test_model_revision_signoff_is_append_only_atomic_and_cas_guarded -> test_sign_off_cas_is_append_only_with_separate_head_and_monotonic_order
# test_model_revision_signoff_validates_exact_current_build_identity -> test_sign_off_validates_exact_current_build_identity
# test_model_revision_signoff_cas_rejects_newer_ready_build_without_partial_state -> test_sign_off_against_superseded_build_reports_current_build_identity
# test_model_build_authority_order_ignores_equal_timestamps_and_opposed_ids -> test_build_authority_order_is_server_assigned_and_unexposed
# test_model_build_authority_order_rejects_caller_supplied_values -> test_queue_build_rejects_caller_supplied_authority_fields
# test_postgres_model_revision_signoff_serializes_with_newer_build_completion -> test_sign_off_serializes_with_a_concurrent_newer_build_completion
# test_model_revision_export_failure_is_retryable_without_demoting_revision -> test_signed_export_is_runtime_pinned_hash_verified_and_never_demotes
# test_model_build_rejects_cross_case_and_superseded_authority -> test_queue_build_rejects_cross_case_and_superseded_authority
# test_model_and_workflow_claims_share_one_active_job_budget -> test_model_and_workflow_jobs_share_one_admission_budget
# test_postgres_concurrent_model_queue_is_idempotent_and_preserves_actor -> test_concurrent_queue_is_idempotent_and_attributes_the_winner
# test_postgres_two_writer_revision_cas_has_one_atomic_winner -> test_two_concurrent_sign_offs_have_one_atomic_winner
