"""Deterministic host modules: the typed SYSTEM_ANALYSIS payload contract.

A payload is a pure function of (module_id, pinned plan context, pinned inputs)
— no clock, no run identity — so replays from the same pin produce identical
artifact digests (invariant 10; §12.4 single time authority).
"""

from __future__ import annotations

from typing import Any


_SUMMARIES = {
    "CP-PARSE": "Source preparation: pinned source set parsed into typed blocks.",
    "CP-0": "Source readiness gate evaluated over the pinned source set.",
    "CP-L10": "Financial change screen computed from pinned sources.",
    "CP-1": "Canonical data foundation assembled from pinned sources.",
    "CP-1A": "Business and transaction fact pack assembled.",
    "CP-1B": "Earnings delta computed from pinned periods.",
    "CP-1C": "Peer benchmark over supplied-only disclosed peers.",
    "CP-1D": "Earnings quality assessment over pinned actuals.",
    "CP-2": "Fundamental credit synthesis over validated upstream artifacts.",
    "CP-2A": "Downside pathway analysis over validated upstream artifacts.",
    "CP-2E": "Macro, FX and hedging sensitivity screen.",
    "CP-2G": "Forward credit model handoff prepared for Model Builder; no workbook values computed here.",
    "CP-2H": "Ratings migration triggers evaluated.",
    "CP-3": "Relative value and security selection screen.",
    "CP-4": "Legal and covenant interpretation over pinned documents.",
    "CP-4C": "Restructuring fulcrum analysis.",
    "CP-5": "Evidence trace validation over upstream artifacts (deterministic severity engine).",
    "CP-6": "IC debate and challenge register.",
}


def build_deterministic_payload(
    module_id: str,
    plan_context: dict[str, Any],
    *,
    input_fingerprint: str = "unavailable",
    upstream_digests: list[str] | None = None,
    loan_universe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _SUMMARIES.get(module_id, f"{module_id} deterministic host analysis.")
    if loan_universe is not None:
        # CP-3 binds the pinned normalized loan universe: the identity triple
        # rides lineage AND provenance; the artifact consumes exactly the
        # pinned rows.
        identity = {
            "id": loan_universe["id"],
            "universe_digest": loan_universe["universe_digest"],
            "source_id": loan_universe["source_id"],
        }
        return {
            **build_deterministic_payload(
                module_id, plan_context,
                input_fingerprint=input_fingerprint, upstream_digests=upstream_digests,
            ),
            "lineage": {
                "input_fingerprint": input_fingerprint,
                "upstream_digests": list(upstream_digests or []),
                "loan_universe": identity,
            },
            "provenance": {
                "executor": "caos.engine.deterministic",
                "profile_id": plan_context.get("profile_id"),
                "selection_id": plan_context.get("selection_id"),
                "loan_universe": identity,
            },
            "inputs": {"loan_universe": {"identity": identity, "rows": loan_universe["rows"]}},
        }
    return {
        "module_id": module_id,
        "schema_version": "caos.system_analysis.v1",
        "status": "COMPLETE",
        "summary": summary,
        "evidence_refs": [],
        "lineage": {
            "input_fingerprint": input_fingerprint,
            "upstream_digests": list(upstream_digests or []),
        },
        "narrative": {
            "takeaway": summary,
            "basis": f"Deterministic host execution against the pinned plan for pathway {plan_context.get('pathway', 'unknown')}.",
            "exceptions": "",
        },
        "authority": "SYSTEM_ANALYSIS",
        "confidence": {"band": "SYSTEM", "qa_status": "Passed"},
        "provenance": {
            "executor": "caos.engine.deterministic",
            "profile_id": plan_context.get("profile_id"),
            "selection_id": plan_context.get("selection_id"),
        },
    }
