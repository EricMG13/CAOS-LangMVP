"""The DECISIONS §7 demonstration: wiring a module for agent execution is a
declarative registry entry. Each test here lands in the same commit as the
registry-only diff that turns it green; the orchestrator core is untouched.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402


CANONICAL_BODY = "\n".join(
    f"## {heading}\n\nscripted"
    for heading in ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry", "Gaps & Conflicts", "QA Validation")
)


class ScriptedProvider:
    """Same provider-port double the spec suite uses: an ordered script of
    ProviderMessage steps; every request is recorded."""

    def __init__(self, script=(), count: int = 1_000):
        from caos.engine.provider import host_control_identity

        self.script = list(script)
        self.count = count
        self.create_requests = []
        self.identity = host_control_identity()

    def count_tokens(self, request) -> int:
        return self.count

    def create_message(self, request):
        self.create_requests.append(request)
        if not self.script:
            raise AssertionError("ScriptedProvider script exhausted")
        return self.script.pop(0)


def _agent_turns(source_id: str, modules: int):
    """Per agent module: one read_evidence tool call, then the canonical JSON."""
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

    final = json.dumps({
        "markdown": CANONICAL_BODY,
        "evidence_refs": [{"source_id": source_id, "block_id": "b00001"}],
        "lineage_counts": {"directly_sourced": 1},
        "fields_present": 1,
        "fields_total": 1,
        "source_gate": "pass",
    })
    turns = []
    for _ in range(modules):
        turns.append(ProviderMessage(
            content=[ProviderBlock(type="tool_use", id="tool-1", name="read_evidence",
                                   input={"source_id": source_id, "block_ids": ["b00001"]})],
            stop_reason="tool_use",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
            request_id="req-tool",
        ))
        turns.append(ProviderMessage(
            content=[ProviderBlock(type="text", text=final)],
            stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=200),
            request_id="req-final",
        ))
    return turns


def _seed_case(store: DomainStore):
    body = b"pinned evidence line"
    case = store.create_case("Case", "Issuer", "Services", "analyst")
    source = store.ingest({
        "case_id": case["id"],
        "filename": "doc.txt",
        "media_type": "text/plain",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, "analyst")
    return case, source


async def _run_pathway(tmp_path: Path, pathway: str):
    from caos.engine.runtime import Engine

    settings = Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed_case(store)
        provider = ScriptedProvider(script=_agent_turns(source["id"], modules=10))
        engine = Engine.create(settings=settings, store=store,
                               checkpoint_path=tmp_path / "ck.db", provider=provider)
        run = await engine.start_run_for_tests(
            case_id=case["id"], pathway=pathway, depth="full", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await engine.wait(run["id"])
        record = engine.get_run(run["id"])
        assert record["status"] == "succeeded", record.get("error")
        artifacts = {a["module_id"]: a for a in engine.artifacts_for_run(run["id"])}
        return artifacts, provider
    finally:
        try:
            if engine is not None:
                await engine.aclose()
        finally:
            store.close()


def _assert_agent_executed(artifacts, provider, module_id: str):
    from caos.engine.authority import assemble_authority

    payload = artifacts[module_id]["payload"]
    assert payload["schema_version"] == "caos.canonical.artifact.v1", \
        f"{module_id} must produce the agent envelope, not {payload.get('authority', payload['schema_version'])}"
    authority = assemble_authority(module_id)
    assert any(request.system == authority for request in provider.create_requests), \
        f"no provider request carried {module_id}'s exact assembled skill authority"


async def test_cp1c_agent_wiring_is_registry_only(tmp_path):
    """CP-1C PeerBenchmark executes as an agent on RELATIVE_VALUE full depth."""
    artifacts, provider = await _run_pathway(tmp_path, "RELATIVE_VALUE")
    _assert_agent_executed(artifacts, provider, "CP-1C")


async def test_cp1d_agent_wiring_is_registry_only(tmp_path):
    """CP-1D EarningsQuality executes as an agent on FULL_CREDIT full depth."""
    artifacts, provider = await _run_pathway(tmp_path, "FULL_CREDIT")
    _assert_agent_executed(artifacts, provider, "CP-1D")


async def test_cp5_agent_wiring_is_registry_only(tmp_path):
    """CP-5 EvidenceTraceValidator executes as an agent on COVENANT_REFINANCING
    full depth — the QA terminal the pathway gains from this wiring."""
    artifacts, provider = await _run_pathway(tmp_path, "COVENANT_REFINANCING")
    _assert_agent_executed(artifacts, provider, "CP-5")
