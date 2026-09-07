"""The qualification corpus and harness (Task 11, DECISIONS §14.20).

Three things are pinned here: the manifests describe C01–C22 completely and
reproducibly; the harness fails closed on every missing input; and one cell
runs end to end under the local answer-keyed host control and scores green
— which proves the pipeline, never analysis. Live qualification is BLOCKED
EXTERNAL and nothing here claims it.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
SERVER = TESTS.parent / "server"
ROOT = TESTS.parent.parent
for entry in (str(TESTS), str(SERVER)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from corpus import manifests as M  # noqa: E402
from corpus import qualify  # noqa: E402
from corpus import scoring  # noqa: E402
from corpus import synthetic  # noqa: E402

HOST_CONTROL_ENV = {**os.environ, "ANTHROPIC_API_KEY": "", "OPENROUTER_API_KEY": "", "CAOS_PROVIDER": "",
                    "OPENAI_API_KEY": "", "CAOS_PROVIDER_CATALOG_PATH": "", "CAOS_DEFAULT_PROVIDER_BINDING": "",
                    "CAOS_CORPUS_EXTERNAL_DIR": ""}


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_recorder_awaits_real_ports_and_closes_ownership_once(asynchronous):
    from types import SimpleNamespace
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage, host_control_identity

    response = ProviderMessage(content=[ProviderBlock(type="text", text='{}')], stop_reason="end_turn",
                               usage=ProviderUsage(input_tokens=1, output_tokens=1))

    class Inner:
        identity = host_control_identity()
        closes = 0

        def create_message(self, request):
            async def answered():
                return response
            return answered() if asynchronous else response

        async def aclose(self):
            self.closes += 1

    inner = Inner()
    recorder = qualify.RecordingProvider(inner)
    request = SimpleNamespace(system="system", effective_tools=lambda: (), messages=[{
        "role": "user", "content": 'HOST\n{"host_identity":{"run_id":"r","module_id":"m"}}',
    }])
    assert await recorder.create_message(request) is response
    assert recorder.calls[0]["module_id"] == "m"
    await recorder.aclose()
    await recorder.aclose()
    assert inner.closes == 1


def _cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TESTS / "corpus" / "qualify.py"), *args], cwd=ROOT,
                          env=env or HOST_CONTROL_ENV, capture_output=True, text=True, check=False)


def _json(stdout: str) -> dict:
    return json.loads(stdout[stdout.index("{"):])


# --- the manifests -----------------------------------------------------------------------------


def test_every_pack_c01_to_c22_is_described_completely():
    for pack_id in M.PACK_IDS:
        manifest = M.load_manifest(pack_id)
        key, _raw = M.load_answer_key(pack_id)
        rows = M.document_rows(manifest)
        assert rows, pack_id
        for row in rows:
            assert set(row) == M._DOCUMENT_KEYS
        assert manifest["applies_to"] and set(key["cells"]) == {
            f"{cell['pathway']}/{cell['depth']}" for cell in manifest["applies_to"]}
    plan = qualify.plan_cells()
    routes = {(cell["pathway"], cell["depth"]) for cell in plan if cell["proves_pathway"]}
    from caos.engine.runtime import startable_routes

    assert routes == set(startable_routes()), "every startable route needs a positive pack that proves it"


def test_carnival_manifest_is_the_pinned_sources_manifest():
    manifest = M.load_manifest("C01")
    by_name = {row["filename"]: row for row in manifest["documents"]}
    rows = M.source_rows()
    assert len(rows) == 30 and set(by_name) == {name for name, *_ in rows}
    for name, digest, document_type, period, url in rows:
        row = by_name[name]
        assert (row["sha256"], row["document_type"], row["period"], row["provenance"]) == (digest, document_type, period, url)
    for borrower in ("C17", "C18", "C19", "C20"):
        assert M.load_manifest(borrower)["documents_from"] == "C01"


def test_synthetic_packs_reproduce_their_pinned_digests():
    for pack_id, builder in synthetic.PACKS.items():
        manifest = M.load_manifest(pack_id)
        pinned = {row["filename"]: row["sha256"] for row in manifest["documents"]}
        built = {name: M.sha256(content) for name, content, _media in builder()}
        assert built == pinned, pack_id
        assert all(document.sha256 == pinned[document.filename] for document in M.resolve_documents(manifest))


def test_external_packs_are_unpinned_and_fail_closed(monkeypatch):
    monkeypatch.delenv(M.EXTERNAL_ENV, raising=False)

    def no_byte_may_be_read(self):
        raise AssertionError(f"resolve_documents read {self} before refusing the unpinned digest")

    # The unpinned digest is refused before any byte is read, so the code is the
    # same on a machine without the Carnival corpus (the 3.12 CI leg) as with it.
    monkeypatch.setattr(Path, "read_bytes", no_byte_may_be_read)
    for pack_id in ("C20", "C21", "C22"):
        manifest = M.load_manifest(pack_id)
        assert manifest["bytes"]["source"] == "external" and manifest["bytes"]["owner"]
        with pytest.raises(M.CorpusError) as refused:
            M.resolve_documents(manifest)
        assert refused.value.code == "CORPUS_BYTES_UNACQUIRED"
        with pytest.raises(M.CorpusError) as unsigned:
            M.attest_answer_key(manifest, b"{}", "host_control")
        assert unsigned.value.code == "ANSWER_KEY_UNSIGNED"
    blocked = {row["pack_id"]: row for row in qualify.blocked_external()}
    assert {"C20", "C21", "C22"} <= set(blocked)
    assert len(blocked["C21"]["unpinned_documents"]) >= 20


def test_answer_key_attestation_is_digest_bound_and_scoped():
    manifest = M.load_manifest("C03")
    key, raw = M.load_answer_key("C03")
    assert M.attest_answer_key(manifest, raw, "host_control")["scope"] == "host_control"
    assert M.attest_answer_key(manifest, raw, "live_evaluation")["scope"] == "host_control"
    with pytest.raises(M.CorpusError) as scope:
        M.attest_answer_key(manifest, raw, "live")
    assert scope.value.code == "ANSWER_KEY_SCOPE_INSUFFICIENT"
    with pytest.raises(M.CorpusError) as drift:
        M.attest_answer_key(manifest, raw + b"\n", "host_control")
    assert drift.value.code == "ANSWER_KEY_DIGEST_MISMATCH"
    with pytest.raises(M.CorpusError, match="ANSWER_KEY_DIGEST_MISMATCH"):
        M.attest_answer_key(manifest, raw + b"\n", "live_evaluation")
    with pytest.raises(M.CorpusError, match="BINDING_INVALID"):
        M.attest_answer_key(manifest, raw, "typo")


def test_pin_never_resigns_an_analyst_approved_key(tmp_path, monkeypatch):
    import shutil

    packs = tmp_path / "packs"
    shutil.copytree(M.PACKS / "C03", packs / "C03")
    monkeypatch.setattr(M, "PACKS", packs)
    manifest_path = packs / "C03" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["answer_key"]["approvals"].append({"scope": "analyst", "reviewer": "an analyst", "approved_at": "2026-09-03", "note": ""})
    manifest_path.write_text(json.dumps(manifest))
    key_path = packs / "C03" / "answer_key.json"
    key_path.write_text(key_path.read_text() + "\n")
    with pytest.raises(M.CorpusError) as refused:
        M.pin("C03", reviewer="tool", approved_at="2026-09-03")
    assert refused.value.code == "ANSWER_KEY_ANALYST_REAPPROVAL_REQUIRED"


def test_corpus_digest_moves_with_any_key_or_document(tmp_path, monkeypatch):
    import shutil

    before = M.corpus_digest()
    packs = tmp_path / "packs"
    shutil.copytree(M.PACKS, packs)
    monkeypatch.setattr(M, "PACKS", packs)
    assert M.corpus_digest() == before
    key_path = packs / "C05" / "answer_key.json"
    key_path.write_text(key_path.read_text() + "\n")
    assert M.corpus_digest() != before


# --- fail-closed exits ----------------------------------------------------------------------


def test_missing_reviewer_credential_and_byte_each_exit_non_zero(tmp_path):
    out = tmp_path / "evidence"
    result = _cli("cell", "--binding", "host_control", "--pack", "C03", "--pathway", "FULL_CREDIT", "--depth", "full",
                  "--reviewer", "", "--out", str(out))
    assert result.returncode == qualify.EXIT_BLOCKED and _json(result.stdout)["blocked_code"] == "REVIEWER_MISSING"

    result = _cli("cell", "--binding", "live", "--pack", "C03", "--pathway", "FULL_CREDIT", "--depth", "full",
                  "--reviewer", "r", "--out", str(out))
    assert result.returncode == qualify.EXIT_BLOCKED and _json(result.stdout)["blocked_code"] == "CREDENTIALS_MISSING"

    result = _cli("cell", "--binding", "host_control", "--pack", "C21", "--pathway", "DISTRESSED_RESTRUCTURING",
                  "--depth", "full", "--reviewer", "r", "--out", str(out))
    assert result.returncode == qualify.EXIT_BLOCKED and _json(result.stdout)["blocked_code"] == "ANSWER_KEY_UNSIGNED"

    result = _cli("cell", "--binding", "host_control", "--pack", "C03", "--pathway", "DEEP_RESEARCH", "--depth", "full",
                  "--reviewer", "r", "--out", str(out))
    assert result.returncode == qualify.EXIT_BLOCKED and _json(result.stdout)["blocked_code"] == "CELL_UNDECLARED"

    result = _cli("cell", "--binding", "host_control", "--pack", "C03", "--pathway", "FULL_CREDIT", "--depth", "full",
                  "--reviewer", "r", "--out", str(out), env={**HOST_CONTROL_ENV, "ANTHROPIC_API_KEY": "sk-present"})
    assert result.returncode == qualify.EXIT_BLOCKED and _json(result.stdout)["blocked_code"] == "CREDENTIALS_PRESENT"

    blocked = [json.loads(path.read_text()) for path in out.rglob("rep-*.json")]
    assert blocked and all(item["verdict"] == "blocked" and item["reviewer"] is not None for item in blocked)


def test_verdict_is_unqualified_while_any_required_cell_is_missing(tmp_path):
    result = _cli("verdict", "--binding", "host_control", "--out", str(tmp_path / "empty"))
    assert result.returncode == qualify.EXIT_FAIL
    summary = _json(result.stdout)
    assert summary["verdict"] == "ORCHESTRATION_PROOF_INCOMPLETE" and summary["complete"] is False
    assert {cell["status"] for cell in summary["cells"]} == {"missing"}
    assert not any(entry["qualified"] for entry in summary["pathways"].values())


# --- the scorer's fail-closed rules ------------------------------------------------------------


def _plan(*cells):
    return [{"cell_key": f"{pack}/{pathway}/{depth}", "pack_id": pack, "pathway": pathway, "depth": depth,
             "outcome": "succeeded", "proves_pathway": proves} for pack, pathway, depth, proves in cells]


def _result(cell_key, verdict, current, *, expires_in_days=90, blocked_code=None, repetition=1):
    return {"cell_key": cell_key, "verdict": verdict, "binding_view": dict(current), "result_id": f"{cell_key}:{verdict}:{repetition}", "repetition": repetition,
            "binding_kind": current.get("binding_kind", "live"),
            "expires_at": (datetime.now(UTC) + timedelta(days=expires_in_days)).isoformat(), "blocked_code": blocked_code}


def test_aggregate_never_averages_and_a_refusal_never_proves_a_pathway():
    current = {"identity_digest": "a", "commit": "b", "corpus_digest": "c"}
    plan = _plan(("C01", "FULL_CREDIT", "full", True), ("C02", "FULL_CREDIT", "full", False))
    passes = [_result("C01/FULL_CREDIT/full", "pass", current, repetition=rep) for rep in range(1, 4)]
    negative = [_result("C02/FULL_CREDIT/full", "pass", current, repetition=rep) for rep in range(1, 4)]
    live = scoring.aggregate(plan, passes + negative, repetitions=3, binding_kind="live", current=current)
    assert live["verdict"] == "QUALIFIED" and live["pathways"]["FULL_CREDIT/full"]["proven_by"] == ["C01"]

    one_failure = scoring.aggregate(plan, passes + negative + [_result("C01/FULL_CREDIT/full", "fail", current)],
                                    repetitions=3, binding_kind="live", current=current)
    assert one_failure["verdict"] == "UNQUALIFIED" and one_failure["blocking"][0]["status"] == "failed"

    two_passes = scoring.aggregate(plan, passes[:2] + negative, repetitions=3, binding_kind="live", current=current)
    assert two_passes["verdict"] == "UNQUALIFIED" and two_passes["blocking"][0]["status"] == "missing"

    refusal_only = scoring.aggregate(_plan(("C02", "FULL_CREDIT", "full", False)), negative, repetitions=3,
                                     binding_kind="live", current=current)
    assert refusal_only["verdict"] == "UNQUALIFIED" and not refusal_only["pathways"]["FULL_CREDIT/full"]["qualified"]

    host_results = [{**item, "binding_kind": "host_control"} for item in passes + negative]
    host = scoring.aggregate(plan, host_results, repetitions=3, binding_kind="host_control", current=current)
    assert host["verdict"] == "ORCHESTRATION_PROOF" and host["verdict"] != "QUALIFIED"

    crashed = {"cell_key": "C01/FULL_CREDIT/full", "verdict": "error", "binding_view": None, "result_id": "crash",
               "expires_at": None, "blocked_code": None, "binding_kind": "live"}
    with_crash = scoring.aggregate(plan, passes + negative + [crashed], repetitions=3, binding_kind="live", current=current)
    assert with_crash["verdict"] == "UNQUALIFIED" and with_crash["blocking"][0]["fails"] == 1


def test_aggregate_discards_stale_and_expired_results():
    current = {"identity_digest": "a", "commit": "b", "corpus_digest": "c"}
    plan = _plan(("C01", "FULL_CREDIT", "full", True))
    stale = [_result("C01/FULL_CREDIT/full", "pass", {**current, "commit": "old"}, repetition=rep) for rep in range(1, 4)]
    expired = [_result("C01/FULL_CREDIT/full", "pass", current, expires_in_days=-1, repetition=rep) for rep in range(1, 4)]
    summary = scoring.aggregate(plan, stale + expired, repetitions=3, binding_kind="live", current=current)
    assert summary["verdict"] == "UNQUALIFIED"
    assert len(summary["stale_results"]) == 3 and len(summary["expired_results"]) == 3
    blocked = [_result("C01/FULL_CREDIT/full", "blocked", current, blocked_code="CORPUS_BYTES_UNACQUIRED")]
    summary = scoring.aggregate(plan, blocked, repetitions=3, binding_kind="live", current=current)
    assert summary["cells"][0]["status"] == "blocked_external" and summary["cells"][0]["blocked"] == ["CORPUS_BYTES_UNACQUIRED"]


def test_injection_scoring_accepts_batch_reads_but_rejects_undeclared_tools():
    control = {"status": "succeeded"}
    injected = {**control, "tool_calls": ["read_evidence_batch"]}
    observed = {"artifacts": [], "injection": {"control": control, "injected": injected}}
    assert scoring.score_injection({}, observed)["pass"]
    injected["tool_calls"].append("shell")
    assert not scoring.score_injection({}, observed)["pass"]


def test_unsupported_claim_and_forbidden_conclusion_fail_a_cell():
    key = {"expected_facts": [], "forbidden_conclusions": [{"id": "X1", "description": "", "match": ["no refinancing risk"]}],
           "cells": {"FULL_CREDIT/full": {"outcome": "succeeded"}}}
    clean = {"artifacts": [{"module_id": "CP-0", "markdown": "## Analysis\n\nRevenue 1,160 [src_1/b00006]\n", "evidence_refs": []}],
             "evidence_text": ["Revenue 1,160"], "calculation_outputs": []}
    assert scoring.score_unsupported_claims(key, "FULL_CREDIT/full", clean)["pass"]
    invented = {**clean, "artifacts": [{"module_id": "CP-0", "markdown": "## Analysis\n\nRevenue 9,999\n", "evidence_refs": []}]}
    assert scoring.score_unsupported_claims(key, "FULL_CREDIT/full", invented)["detail"]["untraceable"] == ["CP-0:9,999"]
    forbidden = {**clean, "artifacts": [{"module_id": "CP-0", "markdown": "## Analysis\n\nThere is no refinancing risk.\n", "evidence_refs": []}]}
    assert scoring.score_unsupported_claims(key, "FULL_CREDIT/full", forbidden)["detail"]["forbidden"] == ["CP-0:X1"]


# --- end to end under the answer-keyed host control -----------------------------------------------


@pytest.mark.parametrize("pack_id, pathway, depth", [
    ("C03", "FULL_CREDIT", "full"),   # conflict flagged, model built, every relevant document in lineage
    ("C12", "FULL_CREDIT", "full"),   # injection: control and injected runs are host-identical, no marker leaks
    ("C13", "FULL_CREDIT", "full"),   # boundary uploads
    ("C15", "FULL_CREDIT", "full"),   # malformed files and the whole-pack intake refusal
])
def test_synthetic_cells_score_green_under_the_answer_keyed_host_control(tmp_path, pack_id, pathway, depth):
    out = tmp_path / "evidence"
    result = _cli("cell", "--binding", "host_control", "--pack", pack_id, "--pathway", pathway, "--depth", depth,
                  "--reviewer", "suite", "--out", str(out))
    summary = _json(result.stdout)
    assert result.returncode == qualify.EXIT_PASS, summary
    retained = json.loads(next(out.rglob("rep-*.json")).read_text())
    assert retained["verdict"] == "pass" and retained["binding_kind"] == "host_control"
    assert retained["binding"]["qualification_status"] == "host_control"
    for field in ("identity_digest", "commit", "methodology_build_id", "corpus_digest", "policy_digest"):
        assert retained["binding_view"][field]
    assert retained["expires_at"] > retained["date"] and retained["reviewer"] == "suite"
    assert retained["corpus"]["approval"]["scope"] == "host_control"
    dimensions = retained["scores"]["dimensions"]
    if pack_id == "C03":
        assert dimensions["conflicts"]["detail"]["handled"] == ["K1"]
        assert dimensions["facts"]["detail"]["linked"] == ["F1", "F2", "F3"]
        assert dimensions["model_effect"]["detail"]["build_status"] == "READY"
        assert dimensions["unsupported_claims"]["detail"]["exempt_modules"] == sorted(qualify.MODEL_FIXTURES)
    if pack_id == "C12":
        assert dimensions["injection"]["applicable"] and dimensions["injection"]["detail"]["problems"] == []
    if pack_id in {"C13", "C15"}:
        assert dimensions["ingest"]["applicable"] and dimensions["ingest"]["detail"]["problems"] == []


def test_a_refusal_cell_passes_only_with_its_declared_code(tmp_path):
    out = tmp_path / "evidence"
    result = _cli("cell", "--binding", "host_control", "--pack", "C02", "--pathway", "EARNINGS_UPDATE", "--depth", "full",
                  "--reviewer", "suite", "--out", str(out))
    summary = _json(result.stdout)
    assert result.returncode == qualify.EXIT_PASS, summary
    assert summary["run"]["error_code"] == "SOURCE_EVIDENCE_INSUFFICIENT"
    retained = json.loads(next(out.rglob("rep-*.json")).read_text())
    assert retained["proves_pathway"] is False and retained["kind"] == "negative"


# --- the MOD ledger --------------------------------------------------------------------------------


def test_every_mod_check_maps_to_the_harness_or_an_external_input():
    with (ROOT / "docs" / "QUALITY_QUALIFICATION.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["Check ID"] for row in rows] == [f"MOD-{index:03d}" for index in range(1, 26)]
    for row in rows:
        assert row["Harness mapping"].strip() and row["Status"] in {"PROVED HOST CONTROL", "PROVED (spec suite)", "BLOCKED EXTERNAL"}
        if row["Status"] == "BLOCKED EXTERNAL":
            assert "owner" in row["Notes"]
    assert not any("QUALIFIED" == row["Status"] for row in rows), "no MOD row may claim live qualification"


def test_unavailable_catalog_closes_allocated_ports_and_returns_typed_block(monkeypatch):
    from types import SimpleNamespace
    from caos.config import Settings
    from caos.engine.catalog import ProviderCatalog
    from caos.engine.provider import host_control_identity
    import run

    closed = []
    async def close():
        closed.append(True)
    port = SimpleNamespace(identity=host_control_identity(), aclose=close)
    catalog = ProviderCatalog({"other": port}, "missing", settings=Settings(), unavailable={"missing": {}})
    monkeypatch.setattr(run, "build_provider", lambda settings: catalog)
    with pytest.raises(qualify.Blocked, match="BINDING_REFUSED"):
        qualify.build_binding("live", Settings(), {}, "test")
    assert closed == [True]


async def test_harness_closes_provider_and_store_when_engine_initialization_fails(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from caos.config import Settings
    from caos.engine.runtime import Engine
    from caos.storage.store import DomainStore

    closed = []
    async def close():
        closed.append("provider")
    def fail(**kwargs):
        raise RuntimeError("engine init failed")
    monkeypatch.setattr(DomainStore, "from_url", lambda url: SimpleNamespace(close=lambda: closed.append("store")))
    monkeypatch.setattr(Engine, "create", fail)
    cell = object.__new__(qualify.CellRun)
    cell.workdir, cell.settings = tmp_path, Settings()
    cell.provider = SimpleNamespace(aclose=close)
    cell.engine = cell.store = None
    with pytest.raises(RuntimeError, match="engine init failed"):
        await cell.execute()
    assert closed == ["provider", "store"]


def test_development_evaluation_cannot_qualify_even_when_all_cells_pass():
    plan = _plan(("C01", "FULL_CREDIT", "full", True))
    current = {"identity_digest": "actual-provider", "binding_kind": "live_evaluation"}
    results = [_result(plan[0]["cell_key"], "pass", current, repetition=rep) for rep in range(1, 4)]
    summary = scoring.aggregate(plan, results, repetitions=3, binding_kind="live_evaluation", current=current)
    assert summary["complete"] and summary["verdict"] == "DEVELOPMENT_EVALUATION"
    assert not any(route["qualified"] for route in summary["pathways"].values())
    # Even copying draft results into a live output directory cannot promote them.
    summary = scoring.aggregate(plan, results, repetitions=3, binding_kind="live", current=current)
    assert summary["verdict"] == "UNQUALIFIED" and len(summary["stale_results"]) == 3
    assert not summary["complete"]
    live_view = {**current, "binding_kind": "live"}
    renamed = [{**result, "binding_kind": "live"} for result in results]
    summary = scoring.aggregate(plan, renamed, repetitions=3, binding_kind="live", current=live_view)
    assert summary["verdict"] == "UNQUALIFIED" and len(summary["stale_results"]) == 3


def test_development_binding_uses_real_provider_and_preserves_credential_guards(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from dataclasses import replace
    from caos.config import Settings
    import run

    base = Settings(provider_binding="codex")
    monkeypatch.setattr(Settings, "from_env", lambda: base)
    settings = qualify.cell_settings("live_evaluation", tmp_path)
    assert settings.provider_binding == "codex" and settings.storage_dir == tmp_path / "vault"
    called = []
    port = SimpleNamespace(identity=SimpleNamespace(identity_digest="actual-provider"))
    def actual_provider(selected):
        called.append(selected)
        return port
    def no_answer_keyed_double(*args):
        raise AssertionError("draft key was exposed to an answer-keyed provider")
    monkeypatch.setattr(run, "build_provider", actual_provider)
    monkeypatch.setattr(qualify, "AnswerKeyedProvider", no_answer_keyed_double)
    cell = qualify.CellRun(qualify.CellSpec("C03", "FULL_CREDIT", "full", 1), "live_evaluation", tmp_path, "Codex")
    assert cell.provider.inner is port and called == [settings]
    assert cell.approval["scope"] == "host_control"
    base = replace(base, provider_binding="")
    with pytest.raises(qualify.Blocked, match="CREDENTIALS_MISSING"):
        qualify.cell_settings("live_evaluation", tmp_path)
    base = replace(base, environment="production", provider_binding="codex")
    with pytest.raises(qualify.Blocked, match="ENVIRONMENT_INVALID"):
        qualify.cell_settings("live_evaluation", tmp_path)
    with pytest.raises(qualify.Blocked, match="BINDING_INVALID"):
        qualify.cell_settings("typo", tmp_path)


def test_development_plan_retains_full_matrix_and_three_repetitions():
    result = _cli("plan", "--binding", "live_evaluation")
    assert result.returncode == 0
    plan = _json(result.stdout)
    assert len(plan["cells"]) == 37 and plan["repetitions"] == 3
    assert plan["policy"]["live_evaluation_is_qualification"] is False
    assert {row["pack_id"] for row in plan["blocked_external"]} == {"C20", "C21", "C22"}


def test_aggregate_requires_distinct_cold_repetitions_and_a_nonempty_plan():
    plan = _plan(("C01", "FULL_CREDIT", "full", True))
    current = {"identity_digest": "actual-provider", "binding_kind": "live"}
    result = _result(plan[0]["cell_key"], "pass", current)
    for copies in ([result] * 3, [{**result, 'repetition': rep} for rep in range(1, 4)]):
        summary = scoring.aggregate(plan, copies, repetitions=3, binding_kind="live", current=current)
        assert summary["verdict"] == "UNQUALIFIED" and summary["cells"][0]["passes"] == 1
    assert not scoring.aggregate([], [], repetitions=3, binding_kind="live", current=current)["complete"]
    for count in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="positive integer"):
            scoring.aggregate(plan, [], repetitions=count, binding_kind="live", current=current)


def test_invalid_repetition_counts_fail_before_any_provider_call(tmp_path):
    for count in ('0', '-1'):
        for command in ('matrix', 'verdict'):
            result = _cli(command, '--binding', 'live_evaluation', '--repetitions', count,
                          '--out', str(tmp_path), *(['--reviewer', 'Codex'] if command=='matrix' else []))
            assert result.returncode == qualify.EXIT_BLOCKED
            assert _json(result.stdout)['blocked_code'] == 'REPETITIONS_INVALID'


def test_refreshed_keys_pin_every_fact_and_preserve_analyst_approval_boundary():
    import unicodedata

    total = 0
    for pid in M.PACK_IDS[:19]:
        manifest = M.load_manifest(pid)
        key, raw = M.load_answer_key(pid)
        assert key['version'] == '1.1.0' and key['status'] == 'draft-machine-authored-source-grounded'
        rows = {row['filename']: row for row in M.document_rows(manifest)}
        assert key['revision']['documents'] == {name: row['sha256'] for name, row in rows.items()}
        assert M.attest_answer_key(manifest, raw, 'live_evaluation')['scope'] == 'host_control'
        with pytest.raises(M.CorpusError, match='ANSWER_KEY_SCOPE_INSUFFICIENT'):
            M.attest_answer_key(manifest, raw, 'live')
        synthetic_docs = {d.filename:d.content for d in M.resolve_documents(manifest)} if manifest['bytes']['source']=='synthetic' else {}
        for fact in key['expected_facts']:
            proof = fact['source_evidence']
            assert proof['sha256'] == rows[fact['source']]['sha256']
            assert any(unicodedata.normalize('NFC',value) in proof['quote'] for value in fact['match'])
            if fact['source'] in synthetic_docs:
                assert proof['quote'] in unicodedata.normalize('NFC',synthetic_docs[fact['source']].decode())
            else:
                assert proof['locator']['kind']=='pdf_page' and proof['locator']['page']>=1
            total += 1
    assert total == 63
