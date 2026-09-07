from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import signal
import sys
import threading

import pytest

from caos.engine import codex
from caos.engine.loop import ProviderSlots, run_agent_module
from caos.engine.provider import AgentError, ProviderRequest


FAKE_CLI = r'''
import json, os, pathlib, subprocess, sys, time
if '--version' in sys.argv:
    print('codex-cli 0.153.4')
    raise SystemExit
control = pathlib.Path(CONTROL)
mode = (control / 'mode').read_text()
raw = sys.stdin.read()
request = json.loads(raw[raw.index('{"system"'):])
record = {'pid':os.getpid(), 'cwd':os.getcwd(), 'args':sys.argv[1:], 'env':sorted(os.environ), 'raw':raw,
          'schema':json.loads(pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).read_text())}
if mode in ('sleep', 'native', 'orphan'):
    child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)'])
    record['child'] = child.pid
with (control / 'calls.jsonl').open('a') as out:
    out.write(json.dumps(record)+'\n')
if mode == 'orphan': raise SystemExit
def emit(value): print(json.dumps(value), flush=True)
emit({'type':'thread.started','thread_id':'thread-synthetic'})
if mode == 'native':
    emit({'type':'item.started','item':{'type':'command_execution','command':'forbidden'}})
if mode in ('sleep', 'native'): time.sleep(30)
if mode == 'large':
    print('x' * (2 * 1024 * 1024), flush=True)
    raise SystemExit
if mode == 'tool' and len(request['messages']) == 1:
    action = {'action':'tool','tool_name':'read_evidence','arguments':{'source_id':'s','block_ids':['b']},'output':None}
else:
    action = {'action':'final','tool_name':None,'arguments':None,'output':{'ok':True}}
if mode == 'bad-action': action['tool_name'] = 'not-a-host-tool'
emit({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(action)}})
emit({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':20,'cached_input_tokens':10,'reasoning_output_tokens':10}})
'''


def request(**changes):
    return ProviderRequest(system="host authority", messages=[{"role": "user", "content": "synthetic evidence"}],
                           schema={"type": "object", "properties": {"ok": {"type": "boolean"}},
                                   "required": ["ok"], "additionalProperties": False},
                           tools_enabled=True, max_tokens=1000, **changes)


@pytest.fixture
async def provider(tmp_path, monkeypatch):
    executable = tmp_path / "codex"
    executable.write_text(f"#!{sys.executable}\n" + FAKE_CLI.replace("CONTROL", repr(str(tmp_path))))
    executable.chmod(0o700)
    (tmp_path / "mode").write_text("final")
    monkeypatch.setattr(codex, "_executable", lambda: str(executable))
    value = codex.CodexProvider("configured-model")
    try:
        yield value, tmp_path
    finally:
        await value.aclose()


async def test_isolated_process_shape_identity_and_usage(provider, monkeypatch):
    value, directory = provider
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    monkeypatch.setenv("CODEX_THREAD_ID", "must-not-inherit")
    counted = value.count_tokens(request())
    result = await value.create_message(request(timeout=5))
    call = json.loads((directory / "calls.jsonl").read_text())
    measured = len(value._encoding.encode(call["raw"] + json.dumps(call["schema"], ensure_ascii=False), disallowed_special=()))
    assert counted == math.ceil(measured * codex.TOKEN_ESTIMATE_MARGIN) + codex.CLI_INPUT_ALLOWANCE
    assert call["schema"]["properties"]["output"]["anyOf"][0]["properties"] == request().schema["properties"]
    assert "timeout" not in call["raw"]
    assert "OPENAI_API_KEY" not in call["env"] and "CODEX_THREAD_ID" not in call["env"]
    assert not Path(call["cwd"]).exists(), "ephemeral input/schema directory was removed"
    assert {"--ignore-user-config", "--strict-config", "--ephemeral", "--sandbox", "read-only"} <= set(call["args"])
    assert not any("dangerously" in argument or argument == "--ignore-rules" for argument in call["args"])
    for feature in codex.DISABLED_FEATURES:
        assert ["--disable", feature] in [call["args"][i:i + 2] for i in range(len(call["args"]) - 1)]
    assert result.content[0].text == '{"ok":true}'
    assert result.usage.input_tokens == 100 and result.usage.output_tokens == 20
    assert result.observed_model == "configured-model" and result.observed_provider_version == "0.153.4"
    assert value.identity.provider_name == "codex" and value.identity.qualification_status == "unqualified"


def test_canonical_output_is_constrained_as_an_object_with_resolvable_references():
    from caos.methodology.canonical import CanonicalModuleOutput

    value = replace(request(), schema=CanonicalModuleOutput.model_json_schema())
    schema = codex.CodexProvider._action_schema(value)
    output = schema["properties"]["output"]["anyOf"][0]
    assert output["type"] == "object" and output["additionalProperties"] is False
    assert set(output["required"]) == set(output["properties"])
    for name in ("EvidenceRef", "CalculationRef"):
        assert name in schema["$defs"]
    assert output["properties"]["evidence_refs"]["items"]["$ref"] == "#/$defs/EvidenceRef"


def test_tool_arguments_have_native_bounds_and_repairs_remove_them():
    from caos.engine.provider import READ_EVIDENCE_BATCH_TOOL, READ_EVIDENCE_TOOL

    value = request(tools=(READ_EVIDENCE_BATCH_TOOL,))
    schema = codex.CodexProvider._action_schema(value)
    arguments = schema["properties"]["arguments"]["anyOf"][0]
    assert arguments["properties"]["references"]["maxItems"] == 50
    assert arguments["properties"]["references"]["items"]["additionalProperties"] is False
    assert schema["properties"]["tool_name"]["enum"] == [None, "read_evidence_batch"]
    repair = codex.CodexProvider._action_schema(replace(value, tools_enabled=False))
    assert repair["properties"]["arguments"]["anyOf"] == [{"type": "null"}]
    assert repair["properties"]["tool_name"]["enum"] == [None]
    single = codex.CodexProvider._action_schema(request())
    blocks = single["properties"]["arguments"]["anyOf"][0]["properties"]["block_ids"]
    assert "uniqueItems" not in blocks and blocks["maxItems"] == 50
    assert READ_EVIDENCE_TOOL["input_schema"]["properties"]["block_ids"]["uniqueItems"] is True


async def test_host_loop_dispatches_evidence_and_returns_final_json(provider):
    value, directory = provider
    (directory / "mode").write_text("tool")
    reads, reconciled = [], []

    def read(source, blocks):
        reads.append((source, blocks))
        return [{"block_id": "b", "text": "synthetic supplied evidence"}]

    result = await run_agent_module(
        provider=value, system="host authority", user="read evidence", schema=request().schema,
        max_tokens=1000, read_evidence=read, validate=lambda output: output,
        reserve=lambda *args: None, reconcile=lambda *args: reconciled.append(args),
        record=lambda *args, **kwargs: None, slots=ProviderSlots(2), expected_identity=value.identity,
    )
    assert result == {"ok": True} and reads == [("s", ["b"])]
    calls = [json.loads(line) for line in (directory / "calls.jsonl").read_text().splitlines()]
    assert len(calls) == 2 and len(reconciled) == 2
    assert "tool_result" in calls[1]["raw"] and "synthetic supplied evidence" in calls[1]["raw"]


async def test_invalid_action_preserves_known_spend_for_host_reconciliation(provider):
    value, directory = provider
    (directory / "mode").write_text("bad-action")
    result = await value.create_message(request())
    assert result.content[0].type == "refusal" and result.usage.output_tokens == 20


@pytest.mark.parametrize("event", [{"type": []}, {"type": "item.completed", "item": {"type": []}}])
async def test_malformed_event_discriminators_fail_with_a_typed_error(event):
    stream = asyncio.StreamReader()
    stream.feed_data(json.dumps(event).encode() + b"\n")
    stream.feed_eof()
    with pytest.raises(AgentError) as refusal:
        await codex.CodexProvider._read_events(stream)
    assert refusal.value.code == "AGENT_OUTPUT_INVALID"


@pytest.mark.parametrize("mode, code", [("native", "AGENT_OUTPUT_INVALID"),
                                      ("large", "AGENT_OUTPUT_INVALID"),
                                      ("sleep", "AGENT_PROVIDER_TIMEOUT")])
async def test_native_tools_oversized_output_and_timeout_are_refused_and_reaped(provider, mode, code):
    value, directory = provider
    (directory / "mode").write_text(mode)
    with pytest.raises(AgentError) as refusal:
        await value.create_message(request(timeout=0.4 if mode == "sleep" else 5))
    assert refusal.value.code == code and not value._processes
    record = json.loads((directory / "calls.jsonl").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(record["pid"], 0)


async def test_cancellation_reaps_the_cli(provider):
    value, directory = provider
    (directory / "mode").write_text("sleep")
    task = asyncio.create_task(value.create_message(request()))
    for _ in range(200):
        if (directory / "calls.jsonl").exists():
            break
        await asyncio.sleep(0.01)
    assert (directory / "calls.jsonl").exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not value._processes
    record = json.loads((directory / "calls.jsonl").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(record["pid"], 0)


async def test_timeout_also_kills_descendants_after_cli_parent_already_exited(provider):
    value, directory = provider
    (directory / "mode").write_text("orphan")
    with pytest.raises(AgentError):
        await value.create_message(request(timeout=0.4))
    record = json.loads((directory / "calls.jsonl").read_text())
    try:
        for _ in range(100):
            try:
                os.kill(record["child"], 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("the orphaned CLI descendant is still alive")
    finally:
        try:
            os.kill(record["child"], signal.SIGKILL)
        except ProcessLookupError:
            pass


async def test_close_during_version_check_prevents_later_process_spawn(provider, monkeypatch):
    value, directory = provider
    entered, release = threading.Event(), threading.Event()

    def delayed_version(_):
        entered.set()
        assert release.wait(2)
        return codex.SUPPORTED_CLI_VERSION

    monkeypatch.setattr(codex, "_version", delayed_version)
    task = asyncio.create_task(value.create_message(request()))
    while not entered.is_set():
        await asyncio.sleep(0.01)
    await value.aclose()
    release.set()
    with pytest.raises(AgentError) as refusal:
        await task
    assert refusal.value.code == "AGENT_PROVIDER_UNAVAILABLE"
    assert not (directory / "calls.jsonl").exists()
