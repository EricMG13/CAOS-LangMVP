from __future__ import annotations

import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[2] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.storage.store import DomainStore  # noqa: E402


class ScriptedProvider:
    """Deterministic provider double implementing the provider port.

    `script` is a list of callables (request -> ProviderMessage) or ProviderMessage
    values consumed in order by create_message. count_tokens returns a fixed count
    unless `count` is overridden. Records every request for congruence assertions.
    """

    def __init__(self, script=(), count: int = 1_000):
        from caos.engine.provider import host_control_identity

        self.script = list(script)
        self.count = count
        self.count_requests = []
        self.create_requests = []
        self.identity = host_control_identity()

    def count_tokens(self, request) -> int:
        self.count_requests.append(request)
        return self.count

    def create_message(self, request):
        self.create_requests.append(request)
        if not self.script:
            raise AssertionError("ScriptedProvider script exhausted")
        step = self.script.pop(0)
        return step(request) if callable(step) else step


def text_message(text: str, *, stop_reason: str = "end_turn", input_tokens: int = 1_000, output_tokens: int = 200):
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

    return ProviderMessage(
        content=[ProviderBlock(type="text", text=text)],
        stop_reason=stop_reason,
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        request_id="req-scripted",
        observed_model="deterministic",
    )


def tool_call_message(source_id: str, block_ids: list[str], *, input_tokens: int = 1_000, output_tokens: int = 50):
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

    return ProviderMessage(
        content=[ProviderBlock(type="tool_use", id="tool-1", name="read_evidence", input={"source_id": source_id, "block_ids": block_ids})],
        stop_reason="tool_use",
        usage=ProviderUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        request_id="req-tool",
        observed_model="deterministic",
    )


def seed_case_with_source(store: DomainStore, body: bytes = b"pinned evidence line", actor: str = "analyst"):
    import hashlib

    case = store.create_case("Case", "Issuer", "Services", actor)
    source = store.ingest({
        "case_id": case["id"],
        "filename": "doc.txt",
        "media_type": "text/plain",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body.decode(), "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, actor)
    return case, source


async def start_full_credit_run(engine, store, *, depth: str = "full"):
    case, source = seed_case_with_source(store)
    run = await engine.start_run_for_tests(
        case_id=case["id"], pathway="FULL_CREDIT", depth=depth, actor="analyst",
        allow_placeholder_deterministic=True,
    )
    return case, source, run
