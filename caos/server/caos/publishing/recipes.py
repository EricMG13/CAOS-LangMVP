"""Declarative visual recipes: a bounded grammar over governed fields only —
no executable or remote content ever enters a recipe (fails closed)."""

from __future__ import annotations

from typing import Any

ALLOWED_KINDS = {
    "line", "bar", "scatter", "trend", "variance_bridge", "scenario_path",
    "rv_scatter", "debt_stack", "maturity_wall", "covenant_headroom",
    "recovery_waterfall", "risk_horizon", "dag",
}
ALLOWED_KEYS = {"kind", "chart_kind", "schema_version", "fields", "units", "metric_ids", "polarity", "accessible_table"}
ALLOWED_UNITS = {"", "%", "USD", "USD m", "bps", "x", "governed source units"}
ALLOWED_POLARITIES = {"", "higher_is_better", "higher_is_worse", "neutral"}
FORBIDDEN_TOKENS = ("javascript", "<script", "</", "eval(", "http://", "https://", "expression")


def validate_recipe(recipe: dict[str, Any], available_fields: set[str]) -> dict[str, Any]:
    if not isinstance(recipe, dict):
        raise ValueError("RECIPE_INVALID: recipe must be a mapping")
    kind = recipe.get("kind") or recipe.get("chart_kind")
    if kind not in ALLOWED_KINDS:
        raise ValueError("RECIPE_INVALID: unknown visual kind")
    if set(recipe) - ALLOWED_KEYS:
        raise ValueError("RECIPE_INVALID: recipe contains an unknown field")
    fields = recipe.get("fields", [])
    if not isinstance(fields, list) or not fields or len(fields) > 20 or any(
        not isinstance(field, str) or field not in available_fields for field in fields
    ):
        raise ValueError("GENERATED_FIELD_INVALID: recipe field is not governed")
    units = recipe.get("units", "")
    polarity = recipe.get("polarity", "")
    metric_ids = recipe.get("metric_ids", [])
    if units not in ALLOWED_UNITS or polarity not in ALLOWED_POLARITIES or not isinstance(metric_ids, list) or len(metric_ids) > 20:
        raise ValueError("RECIPE_INVALID: units, polarity or metrics are not governed")
    serialized = repr(recipe).lower()
    if any(token in serialized for token in FORBIDDEN_TOKENS) or len(serialized) > 8_000:
        raise ValueError("RECIPE_INVALID: executable, remote, or oversized content")
    return {"kind": kind, "fields": list(fields), "units": units, "metric_ids": list(metric_ids),
            "polarity": polarity, "accessible_table": True}
