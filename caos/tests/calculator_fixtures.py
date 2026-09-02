"""Answer-keyed inputs that make every allowlisted methodology calculator
return a *complete* result. Every provider double that follows a module's
advertised tools feeds these, so a host-control run exercises the same
calculation path an ordinary provider would. They are fixtures, not evidence:
a scripted double citing them proves orchestration only (DECISIONS §14.6).
"""

from __future__ import annotations

from typing import Any

VALID_CALCULATION_INPUTS: dict[str, dict[str, Any]] = {
    "credit_metrics": {"periods": {"FY2025": {
        "revenue": 1_000, "adjusted_ebitda": 200, "total_debt": 600,
        "cash_and_equivalents": 100,
    }}},
    "peer_statistics": {"metric": "EV/EBITDA", "peers": [
        {"name": "A", "value": 5, "comparability": "Comparable"},
        {"name": "B", "value": 6, "comparability": "Comparable"},
    ]},
    "rate_fx_sensitivity": {
        "gross_floating_rate_debt": 500, "hedged_floating_rate_debt": 300,
        "total_debt": 1_000,
    },
    "liquidity_bridge": {
        "beginning_accessible_liquidity": 100, "operating_cash_flow": 20,
        "working_capital_movement": 0, "cash_interest": 5, "cash_taxes": 2,
        "mandatory_capex": 3, "debt_amortisation_and_maturities": 4,
        "other_cash_uses": 1, "committed_inflows": 0, "period_months": 12,
    },
    "bond_analytics": {"price": 98.5, "coupon": 6, "years_to_maturity": 5},
    "covenant_headroom": {"tests": [{
        "test": "Leverage", "test_type": "max-ratio", "threshold": 5,
        "current_ratio": 4,
    }]},
    "recovery_waterfall": {
        "enterprise_value": 100, "claims": [{"claim_id": "Notes", "amount": 200}],
    },
    "funding_gap": {
        "horizon_years": 2, "cash": 100, "forecast_fcf": 50,
        "instruments": [{"instrument": "Notes", "amount": 300, "years_to_maturity": 1}],
    },
}


def calculation_ref(record: dict[str, Any]) -> dict[str, Any]:
    """The five-field reference a provider declares for one delivered record."""
    return {
        field: record[field]
        for field in (
            "calculator_id", "script_digest", "calculator_digest",
            "input_digest", "output_digest",
        )
    }
