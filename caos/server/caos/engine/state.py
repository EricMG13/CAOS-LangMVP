"""RunState schema and pin discipline (DECISIONS §3, §11.1–2, §12.A).

Channel values are JSON-native plain data only. The plan is an immutable blob;
its digest travels outside it and is re-asserted on every node entry. Digests
checkpointed in state are expectations — consumers re-read the store record and
recompute before trusting them.
"""

from __future__ import annotations

import copy
from operator import or_
from typing import Annotated, Any, TypedDict

from ..contracts import digest, validate_boundary_text  # noqa: F401  (spec surface re-export)
from ..storage.store import DomainStore
from .provider import AgentError


SCHEMA_VERSION = "caos-state-v1"


class RunState(TypedDict, total=False):
    schema_version: str
    run_id: str
    case_id: str
    plan: dict[str, Any] | None
    plan_digest: str | None
    artifacts: Annotated[dict[str, Any], or_]
    node_status: Annotated[dict[str, Any], or_]
    error: dict[str, Any] | None


def plan_preimage(plan: dict[str, Any]) -> dict[str, Any]:
    """§12.1: the digest is carried outside the digested blob."""
    return {key: value for key, value in plan.items() if key != "plan_digest"}


def pin_plan(plan: dict[str, Any]) -> dict[str, Any]:
    pinned = copy.deepcopy(plan_preimage(plan))
    return {"plan": pinned, "plan_digest": digest(pinned)}


def assert_plan_integrity(plan: dict[str, Any], plan_digest: str) -> None:
    if digest(plan_preimage(plan)) != plan_digest:
        raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned plan digest mismatch")


def source_set_preimage(source_set: dict[str, Any]) -> dict[str, Any]:
    """§12.5: the digested source-set identity is the pinned six-field projection."""
    return {key: source_set[key] for key in ("id", "case_id", "version", "source_ids", "created_by", "created_at")}


def source_set_digest(source_set: dict[str, Any]) -> str:
    return digest(source_set_preimage(source_set))


def verify_source_set_expectation(store: DomainStore, source_set_id: str, expected_digest: str) -> dict[str, Any]:
    """§11.2: re-read the store record by id, recompute, compare — never trust
    the checkpointed value."""
    record = store.source_set(source_set_id)
    if record is None or source_set_digest(record) != expected_digest:
        raise AgentError("AGENT_AUTHORITY_MISMATCH", "SOURCE_SET digest expectation failed")
    return record


def example_state_for_tests() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": "run-1",
        "case_id": "case-1",
        "plan": {
            "build_id": "deploy-v-build",
            "pathway": "FULL_CREDIT",
            "depth": "full",
            "profile_id": "FULL_CREDIT_32",
            "selection_id": "FULL_CREDIT_ASSESSMENT",
            "source_set_id": "set-1",
            "source_set_version": 1,
            "source_set_digest": "0" * 64,
            "focus_questions": [],
            "nodes": [{"module_id": "CP-PARSE", "stage": 0, "dependencies": []}],
        },
        "plan_digest": "0" * 64,
        "artifacts": {"CP-PARSE": {"artifact_id": "art-1", "digest": "0" * 64}},
        "node_status": {"CP-PARSE": "succeeded"},
        "error": None,
    }
