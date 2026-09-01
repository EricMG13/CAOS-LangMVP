"""Methodology integrity and deterministic route compilation (invariants 4 and 10)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from caos.config import Settings
from caos.contracts import Depth
from caos.methodology.bundle import DeployVBundle, MethodologyError

ROOT = Settings().deploy_v_root
REPO = Path(__file__).resolve().parents[2]


def test_vendored_bundle_integrity_passes():
    bundle = DeployVBundle(ROOT)
    report = bundle.verify()
    assert report["mismatches"] == 0
    assert report["checked"] > 0
    assert report["logical_entries"] == 41
    assert report["physical_skills"] == 22
    assert bundle.build_id == bundle.integrity["build_id"]


def test_bundle_identity_files_are_current_and_agree():
    bundle = DeployVBundle(ROOT)
    assert bundle.retrieval["build_id"] == bundle.build_id
    for name in ("DEPLOY_V_COPILOT_MEMORY_PROMPT.md", "DEPLOY_V_COPILOT_MEMORY_PROMPT_URL_BOUND.md"):
        prompt = (ROOT / name).read_text(encoding="utf-8")
        assert "INDEX_BUILD_ID:" in prompt and prompt.count(bundle.build_id) == 1
    subprocess.run(
        [sys.executable, "caos/scripts/regenerate_deploy_v_integrity.py", "--check"],
        cwd=REPO,
        check=True,
    )


def test_tampered_bundle_fails_closed(tmp_path: Path):
    copy = tmp_path / "deploy_v"
    shutil.copytree(ROOT, copy)
    target = copy / "skills" / "cp-1-canonical-data-foundation" / "SKILL.md"
    target.write_bytes(target.read_bytes() + b"\n<!-- tampered -->\n")
    with pytest.raises(MethodologyError, match="integrity mismatch"):
        DeployVBundle(copy).verify()


def test_missing_authority_file_fails_closed(tmp_path: Path):
    copy = tmp_path / "deploy_v"
    shutil.copytree(ROOT, copy)
    (copy / "skills" / "cp-1-canonical-data-foundation" / "SKILL.md").unlink()
    with pytest.raises(MethodologyError, match="integrity mismatch"):
        DeployVBundle(copy).verify()


def test_all_golden_routes_compile_parse_first_and_deterministically():
    bundle = DeployVBundle(ROOT)
    cases = bundle.route_golden_cases()
    assert len(cases) == 16
    for pathway, depth in cases:
        plan = bundle.compile(pathway, depth, source_set_id="set-1", source_set_version=1)
        again = bundle.compile(pathway, depth, source_set_id="set-1", source_set_version=1)
        assert plan == again, f"non-deterministic plan for {pathway}/{depth}"
        nodes = plan["nodes"]
        assert nodes[0]["module_id"] == "CP-PARSE" and nodes[0]["dependencies"] == []
        assert nodes[1]["module_id"] == "CP-0" and nodes[1]["dependencies"] == ["CP-PARSE"]
        module_ids = [node["module_id"] for node in nodes]
        assert len(module_ids) == len(set(module_ids)), "duplicate module in route"
        seen: set[str] = set()
        for node in nodes:
            assert set(node["dependencies"]) <= seen, f"forward dependency in {pathway}/{depth}"
            seen.add(node["module_id"])
        assert plan["plan_digest"]
        assert plan["build_id"] == bundle.build_id


def test_plan_digest_pins_source_set_identity():
    bundle = DeployVBundle(ROOT)
    one = bundle.compile("FULL_CREDIT", Depth.FULL, "set-1", source_set_version=1)
    two = bundle.compile("FULL_CREDIT", Depth.FULL, "set-2", source_set_version=1)
    three = bundle.compile("FULL_CREDIT", Depth.FULL, "set-1", source_set_version=2)
    assert len({one["plan_digest"], two["plan_digest"], three["plan_digest"]}) == 3


def test_full_credit_full_route_matches_catalog():
    bundle = DeployVBundle(ROOT)
    plan = bundle.compile("FULL_CREDIT", Depth.FULL, "set-1", source_set_version=1)
    assert [node["module_id"] for node in plan["nodes"]] == [
        "CP-PARSE", "CP-0", "CP-1", "CP-1A", "CP-1B", "CP-1D", "CP-1C", "CP-2",
        "CP-2A", "CP-2G", "CP-2E", "CP-2H", "CP-3", "CP-4", "CP-4C", "CP-5", "CP-6",
    ]


def test_unknown_pathway_and_route_fail_closed():
    bundle = DeployVBundle(ROOT)
    with pytest.raises(MethodologyError):
        bundle.compile("NOT_A_PATHWAY", Depth.FULL, None)
