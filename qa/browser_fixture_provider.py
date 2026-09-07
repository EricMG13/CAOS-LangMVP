"""Test-only model-shaped provider output for browser orchestration proof.

All evidence and calculator turns come from the development host controller.
The final model-facing Markdown reuses the canonical model answer key, as
caos/tests/corpus/answer_keyed_provider.py does. These figures are fixtures,
never facts extracted from an issuer or live-provider qualification evidence.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from caos.engine.host_control import HostControlProvider, _tool_results
from caos.engine.provider import ProviderBlock, ProviderMessage, host_control_identity

FIXTURES = Path(__file__).resolve().parents[1] / "caos" / "tests" / "fixtures" / "cp_model"
MODEL_FIXTURES = {"CP-1": "cp1.md", "CP-1A": "cp1a.md", "CP-1B": "cp1b.md",
                  "CP-2": "cp2.md", "CP-2A": "cp2a.md", "CP-2G": "cp2g.md"}


class BrowserFixtureProvider(HostControlProvider):
    def __init__(self, *, report_fixtures: bool = False) -> None:
        super().__init__()
        self.report_fixtures = report_fixtures
        self.identity = host_control_identity(adapter_version="caos.browser-model-fixture.v1")

    def create_message(self, request: Any) -> ProviderMessage:
        message = super().create_message(request)
        if message.stop_reason != "end_turn":
            return message
        identity = json.loads(str(request.messages[0]["content"]).split("\n", 1)[1])["host_identity"]
        filename = MODEL_FIXTURES.get(identity["module_id"])
        if filename is None and not self.report_fixtures:
            return message
        delivered = [row for result in _tool_results(request.messages) if isinstance(result, list) for row in result]
        row = delivered[0]
        body = json.loads(message.content[0].text)
        body["markdown"] = (
            ((FIXTURES / filename).read_text(encoding="utf-8") if filename else body["markdown"])
            .replace('"run-cp-model-fixture"', json.dumps(identity["run_id"]))
            .replace("SRC-1", row["source_id"])
            .replace("block-1", row["block_id"])
            .replace("b" * 64, row["source_digest"])
            .replace("Acme Credit Ltd", identity["issuer_name"])
            .replace("Acme-Credit", identity["issuer_id"])
        )
        if self.report_fixtures:
            body["markdown"] = report_fixture_markdown(identity["module_id"], body["markdown"], row["source_id"])
        return replace(message, content=[ProviderBlock(type="text", text=json.dumps(body, sort_keys=True))])


def report_fixture_markdown(module: str, markdown: str, source_id: str) -> str:
    """Declared disposable answer key; never an issuer analysis or qualification."""
    fixture = json.loads((FIXTURES.parent / "deliverables" / "report_modules.json").read_text())
    tables = []
    for table_id, (columns, *rows) in fixture.get(module, {}).items():
        tables.append(f"### {table_id}\n| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n" + "\n".join("| " + " | ".join(row) + " |" for row in rows))
    prose = "Disposable report fixture: recurring contracts support revenue visibility; indicative pricing requires confirmation."
    if module == "CP-DR":
        prose = "### Findings\n\nContract renewals support recurring cash flow.\n\n### Implications and scenarios\n\nMonitor retention before extending the debt maturity profile."
    return markdown.replace("## Analysis\n", "## Analysis\n\n" + prose + "\n\n" + "\n\n".join(tables) + "\n", 1).replace("SRC-1", source_id)
