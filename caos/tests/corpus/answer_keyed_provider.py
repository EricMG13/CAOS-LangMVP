"""The local answer-keyed provider: a host control, never live qualification.

It implements the provider port the way a cooperative model would, driven by
a pack's answer key: it reads the block that carries each expected fact and
one block of every other pinned source (source-complete lineage across the
route, bounded by the per-module read allowance), runs every assigned
calculator with the key's inputs, and returns a canonical envelope that
states exactly the key's facts, conflicts and gaps with citations to what was
delivered. That lets the harness prove its own scoring end to end: a cell that
scores green under this provider proves the pipeline, not the analysis. Its
identity is ``host_control`` (DECISIONS §14.6) and the harness labels every
result it produces ORCHESTRATION_PROOF.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from caos.engine.budget import EVIDENCE_READS_PER_MODULE
from caos.engine.evidence import MAX_EVIDENCE_BLOCKS_PER_READ
from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage, host_control_identity

ADAPTER_VERSION = "caos.answer-keyed.host-control.v1"
HEADINGS = ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry", "Gaps & Conflicts", "QA Validation")
REF_FIELDS = ("calculator_id", "script_digest", "calculator_digest", "input_digest", "output_digest")
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cp_model"
MODEL_FIXTURES = {
    "CP-1": "cp1.md", "CP-1A": "cp1a.md", "CP-1B": "cp1b.md",
    "CP-2": "cp2.md", "CP-2A": "cp2a.md", "CP-2G": "cp2g.md",
}


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def find_block(source: dict[str, Any], matches: list[str]) -> tuple[str, str] | None:
    """The first block of ``source`` whose text carries one of ``matches``."""
    for block in source["blocks"]:
        text = normalize(str(block.get("text") or ""))
        for candidate in matches:
            if normalize(candidate) in text:
                return block["block_id"], candidate
    return None


def _tool_results(messages: list[dict[str, Any]]) -> list[Any]:
    return [
        json.loads(block["content"])
        for message in messages
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]


class AnswerKeyedProvider:
    def __init__(self, key: dict[str, Any], cell_id: str) -> None:
        self.key = key
        self.cell_id = cell_id
        self.cell = key["cells"][cell_id]
        self.control = dict(self.cell.get("host_control") or {})
        self.identity = host_control_identity(adapter_version=ADAPTER_VERSION)
        self.calls = 0
        self.sources: list[dict[str, Any]] = []
        self.by_id: dict[str, dict[str, Any]] = {}
        self.facts: list[tuple[dict[str, Any], str, str, str]] = []  # fact, source_id, block_id, matched
        self.read_by_run: dict[str, set[tuple[str, str]]] = {}

    # -- binding to the admitted pack --------------------------------------------

    def use_cell(self, cell_id: str) -> None:
        """Switch the answer-key cell that scripts this provider. A cell's
        prerequisite Full Credit run executes under that cell's expectations
        when the key declares it, else under the current cell's script with
        the buildable model tables switched on (a prerequisite exists to
        leave a validated model behind)."""
        self.cell_id = cell_id
        declared = self.key["cells"].get(cell_id)
        if declared is None:
            declared = {**self.cell, "host_control": {**self.control, "model_fixtures": True}}
        self.cell = declared
        self.control = dict(self.cell.get("host_control") or {})
        if self.sources:
            self.bind(self.sources)

    def bind(self, sources: list[dict[str, Any]]) -> None:
        self.sources = [source for source in sources if source.get("blocks")]
        self.by_id = {source["id"]: source for source in self.sources}
        by_filename = {source["filename"]: source for source in self.sources}
        self.facts = []
        for fact in self.key["expected_facts"]:
            if fact.get("cells") is not None and self.cell_id not in fact["cells"]:
                continue
            source = by_filename.get(fact["source"])
            if source is None:
                continue
            located = find_block(source, list(fact["match"]))
            if located is not None:
                self.facts.append((fact, source["id"], located[0], located[1]))

    # -- the provider port ------------------------------------------------------------

    def count_tokens(self, request: Any) -> int:
        return 1_000

    def create_message(self, request: Any) -> ProviderMessage:
        assert self.sources, "AnswerKeyedProvider used before bind()"
        self.calls += 1
        prompt = json.loads(str(request.messages[0]["content"]).split("\n", 1)[1])
        identity = prompt["host_identity"]
        module_id, run_id = identity["module_id"], identity["run_id"]
        results = _tool_results(request.messages)
        evidence_results = [result for result in results if isinstance(result, list)]
        delivered_here = {(row["source_id"], row["block_id"]) for result in evidence_results for row in result}
        read_so_far = self.read_by_run.setdefault(run_id, set())
        read_so_far |= delivered_here
        canonical_fixture = module_id in MODEL_FIXTURES and bool(self.control.get("model_fixtures"))

        if len(evidence_results) < EVIDENCE_READS_PER_MODULE:
            # One read per source carries every block that source owes the
            # run — its first block plus the blocks that carry answer-key facts
            # — so a short route (three modules, thirty reads) still reaches
            # every pinned document and every fact. Unread sources come first.
            wanted: dict[str, list[str]] = {}
            for source in self.sources:
                wanted[source["id"]] = [source["blocks"][0]["block_id"]]
            if not canonical_fixture:
                for _fact, source_id, block_id, _m in self.facts:
                    if block_id not in wanted.setdefault(source_id, []):
                        wanted[source_id].append(block_id)
            read_sources = {source_id for source_id, _block in read_so_far}
            pending = [
                (source_id, [block_id for block_id in block_ids if (source_id, block_id) not in read_so_far])
                for source_id, block_ids in wanted.items()
            ]
            pending = [(source_id, block_ids) for source_id, block_ids in pending if block_ids]
            pending.sort(key=lambda item: item[0] in read_sources)  # unread sources first
            if pending:
                source_id, block_ids = pending[0]
                return self._tool_call("read_evidence", {
                    "source_id": source_id, "block_ids": block_ids[:MAX_EVIDENCE_BLOCKS_PER_READ],
                })
        if not evidence_results:
            source = self.sources[0]
            return self._tool_call("read_evidence", {"source_id": source["id"], "block_ids": [source["blocks"][0]["block_id"]]})

        records = [result for result in results if isinstance(result, dict) and "output_digest" in result]
        attempted = {result["calculator_id"] for result in results
                     if isinstance(result, dict) and isinstance(result.get("calculator_id"), str)}
        # An incomplete calculation is the host's typed outcome for inputs the
        # documents cannot support; it is stated as a gap, never retried here.
        skipped_gaps: list[str] = [
            f"{result['calculator_id']}: {result.get('code')} — the pinned calculator returned no usable result "
            "for the inputs the supplied documents support"
            for result in results
            if isinstance(result, dict) and result.get("complete") is False
        ]
        calculation_tool = next(
            (tool for tool in request.effective_tools() if tool["name"] == "run_methodology_calculation"), None,
        )
        if calculation_tool is not None:
            for calculator_id in calculation_tool["input_schema"]["properties"]["calculator_id"]["enum"]:
                if calculator_id in attempted:
                    continue
                inputs = self._calculator_inputs(calculator_id)
                if inputs is None:
                    skipped_gaps.append(f"{calculator_id}: inputs insufficient in the supplied documents; not calculated")
                    continue
                return self._tool_call("run_methodology_calculation", {
                    "calculator_id": calculator_id, "input_json": json.dumps(inputs, sort_keys=True),
                })

        rows = sorted(delivered_here)
        if canonical_fixture:
            markdown = self._fixture_markdown(module_id, run_id, identity, rows[0])
        else:
            markdown = self._narrative_markdown(module_id, rows, skipped_gaps)
        body = {
            "markdown": markdown,
            "evidence_refs": [{"source_id": source_id, "block_id": block_id} for source_id, block_id in rows],
            "calculation_refs": [{field: record[field] for field in REF_FIELDS} for record in records],
            "lineage_counts": {"directly_sourced": len(rows)},
            "fields_present": len(rows),
            "fields_total": len(rows),
            "source_gate": self.control.get("source_gate", "pass") if module_id == "CP-0" else "pass",
        }
        return ProviderMessage(
            content=[ProviderBlock(type="text", text=json.dumps(body, sort_keys=True))],
            stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=200),
            request_id=f"answer-keyed-{self.calls}",
        )

    # -- helpers ------------------------------------------------------------------------

    def _calculator_inputs(self, calculator_id: str) -> dict[str, Any] | None:
        from calculator_fixtures import VALID_CALCULATION_INPUTS

        calculators = self.control.get("calculators", "fixtures")
        if isinstance(calculators, dict):
            # The key overrides named calculators (an input the documents cannot
            # support, or null to withhold the call); the rest use the fixtures.
            return calculators.get(calculator_id, VALID_CALCULATION_INPUTS.get(calculator_id))
        return VALID_CALCULATION_INPUTS.get(calculator_id)

    def _tool_call(self, name: str, arguments: dict[str, Any]) -> ProviderMessage:
        return ProviderMessage(
            content=[ProviderBlock(type="tool_use", id=f"answer-keyed-tool-{self.calls}", name=name, input=arguments)],
            stop_reason="tool_use",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
            request_id=f"answer-keyed-{self.calls}",
        )

    def _fixture_markdown(self, module_id: str, run_id: str, identity: dict[str, Any], row: tuple[str, str]) -> str:
        source_id, block_id = row
        return (
            (FIXTURES / MODEL_FIXTURES[module_id]).read_text(encoding="utf-8")
            .replace('"run-cp-model-fixture"', json.dumps(run_id))
            .replace("SRC-1", source_id)
            .replace("block-1", block_id)
            .replace("b" * 64, self.by_id[source_id]["sha256"])
            .replace("Acme Credit Ltd", identity["issuer_name"])
            .replace("Acme-Credit", identity["issuer_id"])
        )

    def _narrative_markdown(self, module_id: str, rows: list[tuple[str, str]], skipped_gaps: list[str]) -> str:
        delivered = set(rows)
        stated = [(fact, source_id, block_id, matched) for fact, source_id, block_id, matched in self.facts
                  if (source_id, block_id) in delivered]
        analysis = [
            f"- {fact['id']}: {fact['statement']}: {matched} ({fact.get('period') or 'n/a'}; "
            f"source {self.by_id[source_id]['filename']})"
            for fact, source_id, block_id, matched in stated
        ] or ["- No answer-key fact is carried by the evidence delivered to this module."]
        trace = ["| source_id | block_id | fact |", "| --- | --- | --- |"] + [
            f"| {source_id} | {block_id} | {fact['id']} |" for fact, source_id, block_id, _m in stated
        ]
        registry = ["| source_id | filename |", "| --- | --- |"] + [
            f"| {source_id} | {self.by_id[source_id]['filename']} |" for source_id, _block in rows
        ]
        gaps = [
            f"- {conflict['id']}: {conflict['description']} ({' vs '.join(conflict['match'])})"
            for conflict in self.key["conflicts"]
            if conflict.get("cells") is None or self.cell_id in conflict["cells"]
        ] + [f"- {gap}" for gap in list(self.control.get("gaps") or []) + skipped_gaps]
        sections = {
            "Audit Summary": [f"Host-control orchestration proof for {module_id} keyed to the attested "
                              f"{self.key['pack_id']} answer key; not analysis."],
            "Analysis": analysis,
            "Evidence Trace": trace,
            "Source Registry": registry,
            "Gaps & Conflicts": gaps or ["- None recorded by the answer key."],
            "QA Validation": [f"Canonical envelope; QA status is host-owned. Answer key version {self.key['version']}."],
        }
        return "\n\n".join(f"## {heading}\n\n" + "\n".join(sections[heading]) for heading in HEADINGS)
