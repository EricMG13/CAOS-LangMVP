"""Deep Research: brief validation and the host-proposed, digest-bound plan
(Task 7; DECISIONS §14.1, §14.16; CP-DR method steps A and B).

The brief is analyst input that reaches pinned state, so every string is
BoundaryText. The proposed plan is a pure function of the pinned run plan, the
brief and the upstream artifacts CP-DR will consume: identical pins and brief
yield identical workstreams, and the approval hash is the canonical digest of
exactly the plan the analyst reviewed. The brief selects nothing about the
route (invariant 10) — it scopes the module's work, never the node set.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..contracts import ResearchBrief, digest, validate_boundary_text
from ..methodology.canonical import RESEARCH_HANDOFF_FIELDS  # noqa: F401  (re-exported for the runtime)
from .provider import AgentError

RESEARCH_PLAN_SCHEMA = "caos.research_plan.v1"
SOURCE_MODE = "supplied_only"  # invariant 1: the pack is the only evidence
SOURCE_CLASSES = ["supplied_case_sources"]
EFFORT_CAP = "Standard research budget: two focused gap loops per workstream, inside the run's active-time ceiling."


def validate_brief(raw: Any) -> dict[str, Any]:
    """The wire contract plus the boundary-text rules, applied once at run
    creation so a programmatic caller gets the same refusal as the HTTP edge."""
    try:
        brief = ResearchBrief.model_validate(raw)
    except ValidationError as exc:
        raise AgentError("RESEARCH_BRIEF_INVALID", "research brief does not satisfy the contract") from exc
    canonical = brief.model_dump(mode="json")
    try:
        for value in (canonical["research_question"], canonical["decision_context"], canonical["time_horizon"],
                      *canonical["must_answer"], *canonical["exclusions"]):
            validate_boundary_text(value)
    except ValueError as exc:
        raise AgentError("RESEARCH_BRIEF_INVALID", "research brief text violates the boundary rules") from exc
    return canonical


def brief_digest(brief: dict[str, Any]) -> str:
    return digest(brief)


def research_handoff_fields(
    *,
    brief: dict[str, Any],
    approved_plan_hash: str,
    subject_name: str,
    scope_key: str,
    fields_present: int,
    fields_total: int,
) -> dict[str, Any]:
    """Host projection of the research envelope. A module reaches storage only
    with a passed source gate (a partial or failed gate is a typed refusal in
    the validate step), so a stored CP-DR artifact is always `Complete` with
    `coverage_satisfied`; coverage is the validated field-coverage ratio."""
    return {
        "scope_type": "issuer",
        "scope_key": scope_key,
        "subject_name": subject_name,
        "research_question": brief["research_question"],
        "source_mode": SOURCE_MODE,
        "approved_plan_hash": approved_plan_hash,
        "coverage_score": round(100 * fields_present / fields_total),
        "research_status": "Complete",
        "research_stop_reason": "coverage_satisfied",
    }


def research_plan_hash(plan: dict[str, Any]) -> str:
    return f"sha256:{digest(plan)}"


def build_research_plan(
    *,
    build_id: str,
    run_plan_digest: str,
    brief: dict[str, Any],
    source_set_id: str,
    source_set_version: int,
    upstream_artifacts: list[dict[str, Any]],
    scope_key: str,
) -> dict[str, Any]:
    """Three bounded workstreams (method step B: 3–5, with a synthesis lane and
    an adversarial lane), every field a deterministic projection of the brief."""
    question = brief["research_question"]
    as_of, horizon = brief["as_of_date"], brief["time_horizon"]
    exclusions = list(brief["exclusions"])
    boundary = (
        f"Answer only within the decision context ({brief['decision_context']}) as of {as_of} "
        f"over {horizon}; excluded: {'; '.join(exclusions) if exclusions else 'none stated'}."
    )
    workstreams = [
        {
            "id": "WS-1",
            "kind": "primary",
            "question": question,
            "assigned_questions": list(brief["must_answer"]),
            "perspective": "Committee credit analyst answering the approved research question",
            "hypothesis": "The supplied source pack answers the research question within the stated boundary.",
            "evidence_needs": [
                "Supplied case sources cited by file and locator",
                f"Facts dated on or before the as-of date {as_of}",
            ],
            "source_classes": list(SOURCE_CLASSES),
            "disconfirming_test": "Identify supplied evidence that contradicts the working answer or shows the question cannot be answered from the pack.",
            "completion_test": "Every assigned question is answered with source locators or recorded as an evidence gap.",
            "effort_cap": EFFORT_CAP,
        },
        {
            "id": "WS-2",
            "kind": "adversarial",
            "question": f"What supplied evidence would make the opposite answer to '{question}' win?",
            "assigned_questions": [],
            "perspective": "Adversarial reviewer arguing the strongest supported contrary case",
            "hypothesis": "The strongest contrary evidence in the pack changes conviction, implementation or monitoring.",
            "evidence_needs": [
                "Contradicting figures, restatements and subsequent events in the supplied sources",
                "Source disagreements preserved as conflicts, never averaged",
            ],
            "source_classes": list(SOURCE_CLASSES),
            "disconfirming_test": "Show the contrary case cannot be supported by any supplied source locator.",
            "completion_test": "The contrary case is stated with its evidence, or its absence from the pack is recorded as a gap.",
            "effort_cap": EFFORT_CAP,
        },
        {
            "id": "WS-3",
            "kind": "synthesis",
            "question": "What is the direct evidence-weighted answer, and which unknown could change it?",
            "assigned_questions": [boundary],
            "perspective": "Cross-workstream synthesis for the committee decision",
            "hypothesis": "The claim ledger supports one bounded answer with explicit unknowns and a coverage score.",
            "evidence_needs": [
                "Claims drawn only from WS-1 and WS-2 evidence with locators",
                "Coverage gaps and follow-up questions listed explicitly",
            ],
            "source_classes": list(SOURCE_CLASSES),
            "disconfirming_test": "Any material claim without adequate supplied evidence lowers coverage and confidence rather than being smoothed over.",
            "completion_test": "The executive answer, the disagreement, the causal findings and the unknowns are each stated from the ledger.",
            "effort_cap": EFFORT_CAP,
        },
    ]
    return {
        "schema_version": RESEARCH_PLAN_SCHEMA,
        "methodology_build_id": build_id,
        "run_plan_digest": run_plan_digest,
        "brief_digest": brief_digest(brief),
        "source_set": {"id": source_set_id, "version": source_set_version},
        "upstream_artifacts": [
            {"module_id": a["module_id"], "artifact_id": a["artifact_id"], "digest": a["digest"]}
            for a in upstream_artifacts
        ],
        "scope": {"type": "issuer", "key": scope_key, "source_mode": SOURCE_MODE},
        "workstreams": workstreams,
    }
