"""Development-only host-control provider binding (DECISIONS §14 D8).

It follows each module's advertised tools exactly as an ordinary provider
would: one evidence read of the first pinned block, every assigned calculator
run with a fixed answer key, then a canonical envelope that cites what was
delivered. That exercises the whole host path (evidence boundary, calculation
pinning, canonicalization, acceptance) without a model, which is what the
keyless browser gates need. Its identity is ``host_control`` and production
refuses it at the provider builder and at ``Engine`` construction (§14.6): it
proves orchestration, never analysis.
"""

from __future__ import annotations

import json
from typing import Any

from .budget import EVIDENCE_READS_PER_MODULE
from .provider import ProviderBlock, ProviderMessage, ProviderUsage, host_control_identity

ADAPTER_VERSION = "caos.host-control.dev.v1"

# Fixed answer-key inputs that make every allowlisted calculator complete.
# They are fixtures, not evidence: the numbers are not the issuer's.
ANSWER_KEY_INPUTS: dict[str, dict[str, Any]] = {
    "credit_metrics": {"periods": {"FY2025": {
        "revenue": 1_000, "adjusted_ebitda": 200, "total_debt": 600, "cash_and_equivalents": 100,
    }}},
    "peer_statistics": {"metric": "EV/EBITDA", "peers": [
        {"name": "A", "value": 5, "comparability": "Comparable"},
        {"name": "B", "value": 6, "comparability": "Comparable"},
    ]},
    "rate_fx_sensitivity": {
        "gross_floating_rate_debt": 500, "hedged_floating_rate_debt": 300, "total_debt": 1_000,
    },
    "liquidity_bridge": {
        "beginning_accessible_liquidity": 100, "operating_cash_flow": 20,
        "working_capital_movement": 0, "cash_interest": 5, "cash_taxes": 2,
        "mandatory_capex": 3, "debt_amortisation_and_maturities": 4,
        "other_cash_uses": 1, "committed_inflows": 0, "period_months": 12,
    },
    "bond_analytics": {"price": 98.5, "coupon": 6, "years_to_maturity": 5},
    "covenant_headroom": {"tests": [{
        "test": "Leverage", "test_type": "max-ratio", "threshold": 5, "current_ratio": 4,
    }]},
    "recovery_waterfall": {"enterprise_value": 100, "claims": [{"claim_id": "Notes", "amount": 200}]},
    "funding_gap": {
        "horizon_years": 2, "cash": 100, "forecast_fcf": 50,
        "instruments": [{"instrument": "Notes", "amount": 300, "years_to_maturity": 1}],
    },
}

_HEADINGS = ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry", "Gaps & Conflicts", "QA Validation")
_REF_FIELDS = ("calculator_id", "script_digest", "calculator_digest", "input_digest", "output_digest")


def _tool_results(messages: list[dict[str, Any]]) -> list[Any]:
    return [
        json.loads(block["content"])
        for message in messages
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]


def _pinned_blocks(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """The first block of every source in the host-built manifest, in manifest
    order. One read per source is what makes a host-control run source-complete:
    every supplied document is delivered and cited, never only the first."""
    header, _, payload = str(messages[0]["content"]).partition("\n")
    del header
    manifest = json.loads(payload)["source_metadata_manifest"]
    return [
        (source["source_id"], source["blocks"][0]["block_id"])
        for source in manifest
        if source.get("blocks")
    ]


class HostControlProvider:
    """Implements the provider port with a fixed, host-shaped script."""

    def __init__(self) -> None:
        self.identity = host_control_identity(adapter_version=ADAPTER_VERSION)
        self.calls = 0

    def count_tokens(self, request: Any) -> int:
        return 1_000

    def create_message(self, request: Any) -> ProviderMessage:
        self.calls += 1
        results = _tool_results(request.messages)
        evidence_results = [result for result in results if isinstance(result, list)]
        delivered_sources = {row["source_id"] for result in evidence_results for row in result}
        remaining = [
            (source_id, block_id)
            for source_id, block_id in _pinned_blocks(request.messages)
            if source_id not in delivered_sources
        ]
        # Bounded by the module's read allowance (invariant 8): a pack wider
        # than the allowance leaves its tail sources unread, and the model's
        # source-lineage check then says so instead of reading READY.
        if remaining and len(evidence_results) < EVIDENCE_READS_PER_MODULE:
            source_id, block_id = remaining[0]
            return self._tool_call("read_evidence", {"source_id": source_id, "block_ids": [block_id]})
        evidence = [row for result in evidence_results for row in result]
        if not evidence:
            source_id, block_id = _pinned_blocks(request.messages)[0]
            return self._tool_call("read_evidence", {"source_id": source_id, "block_ids": [block_id]})
        records = [result for result in results if isinstance(result, dict) and "output_digest" in result]
        attempted = {
            result["calculator_id"] for result in results
            if isinstance(result, dict) and isinstance(result.get("calculator_id"), str)
        }
        calculation_tool = next(
            (tool for tool in request.effective_tools() if tool["name"] == "run_methodology_calculation"),
            None,
        )
        if calculation_tool is not None:
            assigned = calculation_tool["input_schema"]["properties"]["calculator_id"]["enum"]
            remaining = [calculator_id for calculator_id in assigned if calculator_id not in attempted]
            if remaining:
                calculator_id = remaining[0]
                return self._tool_call("run_methodology_calculation", {
                    "calculator_id": calculator_id,
                    "input_json": json.dumps(ANSWER_KEY_INPUTS.get(calculator_id, {}), sort_keys=True),
                })
        source_id = evidence[0]["source_id"]
        table = f"\n\n| source_id | value |\n| --- | --- |\n| {source_id} | host control |"
        markdown = "\n\n".join(
            f"## {heading}\n\n{'Host-control orchestration proof; not analysis.'}" for heading in _HEADINGS
        ) + table
        body = {
            "markdown": markdown,
            "evidence_refs": [{"source_id": row["source_id"], "block_id": row["block_id"]} for row in evidence],
            "calculation_refs": [{field: record[field] for field in _REF_FIELDS} for record in records],
            "lineage_counts": {"directly_sourced": len(evidence)},
            "fields_present": 1,
            "fields_total": 1,
            "source_gate": "pass",
            "findings": {},
        }
        return ProviderMessage(
            content=[ProviderBlock(type="text", text=json.dumps(body, sort_keys=True))],
            stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=200),
            request_id=f"host-control-{self.calls}",
        )

    def _tool_call(self, name: str, arguments: dict[str, Any]) -> ProviderMessage:
        return ProviderMessage(
            content=[ProviderBlock(type="tool_use", id=f"host-control-tool-{self.calls}", name=name, input=arguments)],
            stop_reason="tool_use",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
            request_id=f"host-control-{self.calls}",
        )
