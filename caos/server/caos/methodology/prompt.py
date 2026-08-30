"""InvocationPlan bounding: the case-focus surface an analyst can influence.

The plan is allowlisted and bounded here so nothing case-derived can reach a
prompt as authority. Prompt assembly itself lives in engine/authority.py — the
compilers that used to sit beside this were scaffolding for the unbuilt
Deep Research route and had no caller.
"""

from __future__ import annotations

from typing import Any

ALLOWED_INVOCATION_KEYS = {"qualifiers", "optional_method_ids", "upstream_artifact_ids", "focus_questions", "gaps", "conflicts", "evidence_refs"}
FORBIDDEN_PROMPT_KEYS = {"system_prompt", "developer_prompt", "tools", "schema", "dependencies", "pathway", "profile_id", "module_id"}


def validate_invocation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    unknown = set(plan) - ALLOWED_INVOCATION_KEYS
    if unknown or FORBIDDEN_PROMPT_KEYS.intersection(plan):
        raise ValueError("InvocationPlan contains an unallowlisted authority field")
    for key in ("qualifiers", "optional_method_ids", "upstream_artifact_ids", "gaps", "conflicts", "evidence_refs"):
        values = plan.get(key, [])
        if not isinstance(values, list) or len(values) > 50 or any(not isinstance(value, str) or len(value) > 400 for value in values):
            raise ValueError(f"InvocationPlan field {key} is not bounded")
    questions = plan.get("focus_questions", [])
    if not isinstance(questions, list) or len(questions) > 5 or any(not isinstance(value, str) or len(value) > 400 for value in questions):
        raise ValueError("focus_questions are not bounded")
    return {key: list(plan.get(key, [])) for key in sorted(ALLOWED_INVOCATION_KEYS)}
