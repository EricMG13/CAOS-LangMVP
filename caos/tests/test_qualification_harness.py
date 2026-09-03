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
                    "CAOS_CORPUS_EXTERNAL_DIR": ""}


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
    with pytest.raises(M.CorpusError) as scope:
        M.attest_answer_key(manifest, raw, "live")
    assert scope.value.code == "ANSWER_KEY_SCOPE_INSUFFICIENT"
    with pytest.raises(M.CorpusError) as drift:
        M.attest_answer_key(manifest, raw + b"\n", "host_control")
    assert drift.value.code == "ANSWER_KEY_DIGEST_MISMATCH"


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


def _result(cell_key, verdict, current, *, expires_in_days=90, blocked_code=None):
    return {"cell_key": cell_key, "verdict": verdict, "binding_view": dict(current), "result_id": f"{cell_key}:{verdict}",
            "expires_at": (datetime.now(UTC) + timedelta(days=expires_in_days)).isoformat(), "blocked_code": blocked_code}


def test_aggregate_never_averages_and_a_refusal_never_proves_a_pathway():
    current = {"identity_digest": "a", "commit": "b", "corpus_digest": "c"}
    plan = _plan(("C01", "FULL_CREDIT", "full", True), ("C02", "FULL_CREDIT", "full", False))
    passes = [_result("C01/FULL_CREDIT/full", "pass", current) for _ in range(3)]
    negative = [_result("C02/FULL_CREDIT/full", "pass", current) for _ in range(3)]
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

    host = scoring.aggregate(plan, passes + negative, repetitions=3, binding_kind="host_control", current=current)
    assert host["verdict"] == "ORCHESTRATION_PROOF" and host["verdict"] != "QUALIFIED"

    crashed = {"cell_key": "C01/FULL_CREDIT/full", "verdict": "error", "binding_view": None, "result_id": "crash",
               "expires_at": None, "blocked_code": None}
    with_crash = scoring.aggregate(plan, passes + negative + [crashed], repetitions=3, binding_kind="live", current=current)
    assert with_crash["verdict"] == "UNQUALIFIED" and with_crash["blocking"][0]["fails"] == 1


def test_aggregate_discards_stale_and_expired_results():
    current = {"identity_digest": "a", "commit": "b", "corpus_digest": "c"}
    plan = _plan(("C01", "FULL_CREDIT", "full", True))
    stale = [_result("C01/FULL_CREDIT/full", "pass", {**current, "commit": "old"}) for _ in range(3)]
    expired = [_result("C01/FULL_CREDIT/full", "pass", current, expires_in_days=-1) for _ in range(3)]
    summary = scoring.aggregate(plan, stale + expired, repetitions=3, binding_kind="live", current=current)
    assert summary["verdict"] == "UNQUALIFIED"
    assert len(summary["stale_results"]) == 3 and len(summary["expired_results"]) == 3
    blocked = [_result("C01/FULL_CREDIT/full", "blocked", current, blocked_code="CORPUS_BYTES_UNACQUIRED")]
    summary = scoring.aggregate(plan, blocked, repetitions=3, binding_kind="live", current=current)
    assert summary["cells"][0]["status"] == "blocked_external" and summary["cells"][0]["blocked"] == ["CORPUS_BYTES_UNACQUIRED"]


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
