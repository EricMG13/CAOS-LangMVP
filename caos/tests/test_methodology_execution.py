from __future__ import annotations

import dataclasses
import json
import math
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest

from caos.contracts import digest
from caos.methodology import execution
from caos.methodology.execution import (
    MethodologyCalculationError,
    MethodologyCalculationRuntime,
    calculation_output_complete,
)


DEPLOY_V = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "caos"
    / "methodology"
    / "vendor"
    / "deploy_v"
)


def _manifest(root: Path) -> dict:
    return json.loads((root / "DEPLOY_V_INTEGRITY_v1.json").read_text(encoding="utf-8"))


@pytest.fixture()
def copied_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "deploy_v"
    shutil.copytree(DEPLOY_V, root)
    return root


def test_static_allowlist_and_credit_metrics_execute_with_exact_digests():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    inputs = {
        "periods": {
            "FY2025": {
                "revenue": 1000,
                "adjusted_ebitda": 200,
                "total_debt": 600,
                "cash_and_equivalents": 100,
            }
        }
    }

    result = runtime.execute("CP-1", "credit_metrics", inputs)

    assert runtime.calculator_ids("CP-1") == ("credit_metrics",)
    assert runtime.calculator_ids("CP-2G") == ("credit_metrics", "liquidity_bridge")
    assert runtime.calculator_ids("CP-0") == ()
    assert result["schema_version"] == "caos.methodology-calculation.v1"
    assert result["module_id"] == "CP-1"
    assert result["calculator_id"] == "credit_metrics"
    assert result["canonical_input"] == inputs
    assert result["input_digest"] == digest(result["canonical_input"])
    assert result["input_digest"] == digest(inputs)
    assert result["output_digest"] == digest(result["canonical_output"])
    assert result["canonical_output"]["periods"]["FY2025"]["kpis"]["total_leverage"] == 3.0
    assert result["canonical_output"]["periods"]["FY2025"]["kpis"]["net_leverage"] == 2.5
    assert len(result["script_digest"]) == 64
    assert result["dependency_digests"].keys() == {"scripts/cp_tables.py"}
    assert len(result["calculator_digest"]) == 64


def test_allowlist_rejects_cross_module_or_unknown_calculators():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    with pytest.raises(MethodologyCalculationError) as cross_module:
        runtime.execute("CP-1", "funding_gap", {})
    assert cross_module.value.code == "METHODOLOGY_CALCULATOR_NOT_ALLOWED"

    with pytest.raises(MethodologyCalculationError) as unknown_module:
        runtime.execute("CP-NOT-REAL", "credit_metrics", {})
    assert unknown_module.value.code == "METHODOLOGY_CALCULATOR_NOT_ALLOWED"


@pytest.mark.parametrize("module_id", ["CP-3", "CP-4C"])
def test_recovery_waterfall_refuses_input_driven_unbounded_work(module_id):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    inputs = {
        "claims": [
            {"claim_id": f"claim-{index}", "amount": 1}
            for index in range(200)
        ],
        "ev_cases": [
            {"label": f"case-{index}", "enterprise_value": index}
            for index in range(300)
        ],
    }

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute(module_id, "recovery_waterfall", inputs)

    assert caught.value.code == "METHODOLOGY_INPUT_INVALID"


def test_distressed_completion_requires_numeric_funding_gap_and_recovery():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    funding = runtime.execute("CP-4C", "funding_gap", {
        "horizon_years": 2,
        "cash": 100,
        "forecast_fcf": 50,
        "instruments": [{"instrument": "Notes", "amount": 300, "years_to_maturity": 1}],
    })
    recovery = runtime.execute("CP-4C", "recovery_waterfall", {
        "enterprise_value": 100,
        "claims": [{"claim_id": "Notes", "amount": 200}],
    })
    incomplete_funding = runtime.execute("CP-4C", "funding_gap", {
        "horizon_years": 2,
        "cash": None,
        "instruments": [{"instrument": "Notes", "amount": None, "years_to_maturity": 1}],
    })
    incomplete_recovery = runtime.execute("CP-4C", "recovery_waterfall", {
        "enterprise_value": 100,
        "claims": [{"claim_id": "Notes", "amount": None}],
    })

    assert calculation_output_complete("CP-4C", "funding_gap", funding["canonical_output"])
    assert calculation_output_complete("CP-4C", "recovery_waterfall", recovery["canonical_output"])
    assert not calculation_output_complete(
        "CP-4C", "funding_gap", incomplete_funding["canonical_output"],
    )
    assert not calculation_output_complete(
        "CP-4C", "recovery_waterfall", incomplete_recovery["canonical_output"],
    )


@pytest.mark.parametrize(
    ("module_id", "calculator_id"),
    [
        ("CP-1", "credit_metrics"),
        ("CP-1B", "credit_metrics"),
        ("CP-1C", "peer_statistics"),
        ("CP-2E", "rate_fx_sensitivity"),
        ("CP-2G", "credit_metrics"),
        ("CP-2G", "liquidity_bridge"),
        ("CP-2H", "bond_analytics"),
        ("CP-2H", "covenant_headroom"),
        ("CP-4", "covenant_headroom"),
    ],
)
def test_empty_calculator_results_are_never_complete(module_id, calculator_id):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    result = runtime.execute(module_id, calculator_id, {})

    assert not calculation_output_complete(module_id, calculator_id, result["canonical_output"])


@pytest.mark.parametrize(
    ("module_id", "calculator_id", "inputs"),
    [
        ("CP-1", "credit_metrics", {"periods": {"FY2025": {
            "revenue": 1_000, "adjusted_ebitda": 200, "total_debt": 600,
            "cash_and_equivalents": 100,
        }}}),
        ("CP-1B", "credit_metrics", {"periods": {"FY2025": {
            "revenue": 1_000, "adjusted_ebitda": 200, "total_debt": 600,
            "cash_and_equivalents": 100,
        }}}),
        ("CP-1C", "peer_statistics", {"metric": "EV/EBITDA", "peers": [
            {"name": "A", "value": 5, "comparability": "Comparable"},
            {"name": "B", "value": 6, "comparability": "Comparable"},
        ]}),
        ("CP-2E", "rate_fx_sensitivity", {
            "gross_floating_rate_debt": 500, "hedged_floating_rate_debt": 300,
            "total_debt": 1_000,
        }),
        ("CP-2G", "credit_metrics", {"periods": {"FY2025": {
            "revenue": 1_000, "adjusted_ebitda": 200, "total_debt": 600,
            "cash_and_equivalents": 100,
        }}}),
        ("CP-2G", "liquidity_bridge", {
            "beginning_accessible_liquidity": 100, "operating_cash_flow": 20,
            "working_capital_movement": 0, "cash_interest": 5, "cash_taxes": 2,
            "mandatory_capex": 3, "debt_amortisation_and_maturities": 4,
            "other_cash_uses": 1, "committed_inflows": 0, "period_months": 12,
        }),
        ("CP-2H", "bond_analytics", {"price": 98.5, "coupon": 6, "years_to_maturity": 5}),
        ("CP-2H", "covenant_headroom", {"tests": [{
            "test": "Leverage", "test_type": "max-ratio", "threshold": 5,
            "current_ratio": 4,
        }]}),
        ("CP-3", "recovery_waterfall", {
            "enterprise_value": 100, "claims": [{"claim_id": "Notes", "amount": 200}],
        }),
        ("CP-4", "covenant_headroom", {"tests": [{
            "test": "Leverage", "test_type": "max-ratio", "threshold": 5,
            "current_ratio": 4,
        }]}),
    ],
)
def test_usable_calculator_results_are_complete(module_id, calculator_id, inputs):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    result = runtime.execute(module_id, calculator_id, inputs)

    assert calculation_output_complete(module_id, calculator_id, result["canonical_output"])


@pytest.mark.parametrize(
    "inputs",
    [
        {"not_json": (1, 2)},
        {"not_finite": math.nan},
        {"integer_too_wide": 10**101},
        {"string_too_wide": "x" * (execution.MAX_CALCULATION_STRING_CHARS + 1)},
        {"normalised_string_too_wide": "\u0958" * (execution.MAX_CALCULATION_STRING_CHARS // 2 + 1)},
    ],
)
def test_input_must_be_bounded_json_native(inputs):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-1", "credit_metrics", inputs)

    assert caught.value.code == "METHODOLOGY_INPUT_INVALID"


def test_input_depth_and_canonical_byte_limits_are_enforced():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    too_deep: dict = {}
    cursor = too_deep
    for _ in range(execution.MAX_CALCULATION_DEPTH + 1):
        cursor["next"] = {}
        cursor = cursor["next"]

    with pytest.raises(MethodologyCalculationError) as depth_error:
        runtime.execute("CP-1", "credit_metrics", too_deep)
    assert depth_error.value.code == "METHODOLOGY_INPUT_INVALID"

    too_large = {
        str(index): "x" * execution.MAX_CALCULATION_STRING_CHARS
        for index in range(execution.MAX_CALCULATION_INPUT_BYTES // execution.MAX_CALCULATION_STRING_CHARS + 2)
    }
    with pytest.raises(MethodologyCalculationError) as byte_error:
        runtime.execute("CP-1", "credit_metrics", too_large)
    assert byte_error.value.code == "METHODOLOGY_INPUT_INVALID"


def test_vendor_calculation_failure_is_collapsed_to_a_typed_code():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-4C", "funding_gap", {})

    assert caught.value.code == "METHODOLOGY_CALCULATION_FAILED"
    assert str(caught.value) == "METHODOLOGY_CALCULATION_FAILED"


def test_non_json_or_oversized_vendor_output_fails_closed(monkeypatch):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    original = runtime._load_compute
    monkeypatch.setattr(
        runtime,
        "_load_compute",
        lambda spec: (lambda _inputs: {"bad": math.inf}, original(spec)[1]),
    )
    with pytest.raises(MethodologyCalculationError) as nonfinite:
        runtime.execute("CP-1", "credit_metrics", {})
    assert nonfinite.value.code == "METHODOLOGY_OUTPUT_INVALID"

    monkeypatch.setattr(
        runtime,
        "_load_compute",
        lambda spec: (
            lambda _inputs: {"too_large": "x" * (execution.MAX_CALCULATION_OUTPUT_BYTES + 1)},
            original(spec)[1],
        ),
    )
    with pytest.raises(MethodologyCalculationError) as oversized:
        runtime.execute("CP-1", "credit_metrics", {})
    assert oversized.value.code == "METHODOLOGY_OUTPUT_INVALID"


def test_calculator_mutation_cannot_rewrite_the_audited_input(monkeypatch):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    original = runtime._load_compute

    def mutating_compute(inputs):
        inputs["amount"] = 999
        return {"observed": inputs["amount"]}

    monkeypatch.setattr(
        runtime,
        "_load_compute",
        lambda spec: (mutating_compute, original(spec)[1]),
    )

    result = runtime.execute("CP-1", "credit_metrics", {"amount": 100})

    assert result["canonical_input"] == {"amount": 100}
    assert result["input_digest"] == digest({"amount": 100})
    assert result["canonical_output"] == {"observed": 999}


@pytest.mark.parametrize(
    "relative_path",
    ("scripts/credit_metrics.py", "scripts/cp_tables.py"),
)
def test_changed_calculator_or_dependency_bytes_are_rejected_before_execution(
    copied_bundle: Path, relative_path: str
):
    script = (
        copied_bundle
        / "skills"
        / "cp-1-canonical-data-foundation"
        / relative_path
    )
    changed = bytearray(script.read_bytes())
    changed[0] ^= 1
    script.write_bytes(changed)
    runtime = MethodologyCalculationRuntime(copied_bundle, _manifest(copied_bundle))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-1", "credit_metrics", {})

    assert caught.value.code == "METHODOLOGY_AUTHORITY_MISMATCH"


def test_symlinked_script_is_rejected_even_when_target_bytes_match(copied_bundle: Path):
    script = (
        copied_bundle
        / "skills"
        / "cp-1-canonical-data-foundation"
        / "scripts"
        / "credit_metrics.py"
    )
    target = copied_bundle.parent / "matching-credit-metrics.py"
    target.write_bytes(script.read_bytes())
    script.unlink()
    script.symlink_to(target)
    runtime = MethodologyCalculationRuntime(copied_bundle, _manifest(copied_bundle))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-1", "credit_metrics", {})

    assert caught.value.code == "METHODOLOGY_AUTHORITY_MISMATCH"


def test_symlinked_bundle_root_is_rejected(copied_bundle: Path):
    linked_root = copied_bundle.parent / "linked-deploy-v"
    linked_root.symlink_to(copied_bundle, target_is_directory=True)
    runtime = MethodologyCalculationRuntime(linked_root, _manifest(copied_bundle))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-1", "credit_metrics", {})

    assert caught.value.code == "METHODOLOGY_AUTHORITY_MISMATCH"


@pytest.mark.parametrize(
    "relative_path",
    ("scripts/not-in-the-manifest.py", "../outside.py"),
)
def test_unmanifested_or_escaping_static_spec_fails_closed(
    copied_bundle: Path, monkeypatch, relative_path: str
):
    original = execution._CALCULATORS[("CP-1", "credit_metrics")]
    calculators = dict(execution._CALCULATORS)
    calculators[("CP-1", "credit_metrics")] = dataclasses.replace(
        original, relative_path=relative_path
    )
    monkeypatch.setattr(execution, "_CALCULATORS", calculators)

    with pytest.raises(MethodologyCalculationError) as caught:
        MethodologyCalculationRuntime(copied_bundle, _manifest(copied_bundle))

    assert caught.value.code == "METHODOLOGY_AUTHORITY_MISMATCH"


def test_binding_manifest_verifies_every_allowlisted_script_and_is_stable():
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    first = runtime.binding_manifest()
    second = runtime.binding_manifest()

    assert first == second
    assert len(first) == len(execution._CALCULATORS)
    assert first == sorted(first, key=lambda item: (item["module_id"], item["calculator_id"]))
    assert all(len(item["calculator_digest"]) == 64 for item in first)
    assert all(item["script_bytes"] > 0 for item in first)


def test_every_allowlisted_script_exports_compute_and_loader_restores_globals(monkeypatch):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    sentinel = ModuleType("sentinel_cp_tables")
    original_path = list(sys.path)
    monkeypatch.setitem(sys.modules, "cp_tables", sentinel)

    for spec in execution._CALCULATORS.values():
        compute, binding = runtime._load_compute(spec)
        assert callable(compute)
        assert len(binding["calculator_digest"]) == 64
        assert sys.modules["cp_tables"] is sentinel
        assert sys.path == original_path


def test_concurrent_execution_is_stable_and_does_not_leak_import_state(monkeypatch):
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))
    sentinel = ModuleType("sentinel_cp_tables")
    original_path = list(sys.path)
    monkeypatch.setitem(sys.modules, "cp_tables", sentinel)
    inputs = {
        "periods": {
            "FY2025": {
                "adjusted_ebitda": 200,
                "total_debt": 600,
                "cash_and_equivalents": 100,
            }
        }
    }

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _index: runtime.execute("CP-1", "credit_metrics", inputs),
                range(32),
            )
        )

    assert all(result == results[0] for result in results)
    assert sys.modules["cp_tables"] is sentinel
    assert sys.path == original_path


@pytest.mark.parametrize("inputs", [
    {"price": 98.5, "coupon": 6, "years_to_maturity": 101},
    {"price": 98.5, "coupon": 6, "years_to_maturity": 5,
     "call_schedule": [{"year": index + 1, "price": 100} for index in range(101)]},
])
def test_bond_work_factor_is_bounded_by_the_host_before_vendor_code_runs(inputs):
    """§14.8: work-factor bounds are host-owned. The vendored script carries
    its own guard as defence in depth, but the host refuses first, as an input
    refusal, so a swapped or looser vendor script can never widen the bound."""
    runtime = MethodologyCalculationRuntime(DEPLOY_V, _manifest(DEPLOY_V))

    with pytest.raises(MethodologyCalculationError) as caught:
        runtime.execute("CP-2H", "bond_analytics", inputs)

    assert caught.value.code == "METHODOLOGY_INPUT_INVALID"
    # The vendored script keeps its own guard (DECISIONS §14.13); the host bound
    # is what execute() enforces, so the vendor guard is observable only here.
    vendored = (
        DEPLOY_V / "skills" / "cp-2h-ratings-migration-trigger" / "scripts" / "bond_analytics.py"
    ).read_text(encoding="utf-8")
    assert "MAX_BOND_YEARS = 100" in vendored and "MAX_CALL_SCHEDULE_ITEMS = 100" in vendored
