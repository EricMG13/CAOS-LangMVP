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
    def __init__(self) -> None:
        super().__init__()
        self.identity = host_control_identity(adapter_version="caos.browser-model-fixture.v1")

    def create_message(self, request: Any) -> ProviderMessage:
        message = super().create_message(request)
        if message.stop_reason != "end_turn":
            return message
        identity = json.loads(str(request.messages[0]["content"]).split("\n", 1)[1])["host_identity"]
        filename = MODEL_FIXTURES.get(identity["module_id"])
        if filename is None:
            return message
        delivered = [row for result in _tool_results(request.messages) if isinstance(result, list) for row in result]
        row = delivered[0]
        body = json.loads(message.content[0].text)
        body["markdown"] = (
            (FIXTURES / filename).read_text(encoding="utf-8")
            .replace('"run-cp-model-fixture"', json.dumps(identity["run_id"]))
            .replace("SRC-1", row["source_id"])
            .replace("block-1", row["block_id"])
            .replace("b" * 64, row["source_digest"])
            .replace("Acme Credit Ltd", identity["issuer_name"])
            .replace("Acme-Credit", identity["issuer_id"])
        )
        return replace(message, content=[ProviderBlock(type="text", text=json.dumps(body, sort_keys=True))])
