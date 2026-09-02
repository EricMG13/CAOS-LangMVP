"""Methodology integrity and deterministic route compilation (invariants 4 and 10)."""

from __future__ import annotations

import hashlib
import json
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


def test_regeneration_rejects_undeclared_tree_entries(tmp_path: Path):
    script = REPO / "caos/scripts/regenerate_deploy_v_integrity.py"
    bundle_relative = ROOT.relative_to(REPO)
    cases = (
        ("skills-file", bundle_relative / "skills/UNDECLARED.txt", False, "skills must contain only"),
        ("root-file", bundle_relative / "UNDECLARED.txt", False, "bundle root entries"),
        ("root-entry-symlink", bundle_relative / "UNDECLARED", True, "bundle root entries"),
        (
            "nested-symlink",
            bundle_relative / "skills/cp-4-legal-covenant-interpreter/UNDECLARED",
            True,
            "symlink is not valid",
        ),
    )
    for name, relative, symlink, expected in cases:
        repo = tmp_path / name
        copy = repo / bundle_relative
        copy.parent.mkdir(parents=True)
        shutil.copytree(ROOT, copy)
        command = [sys.executable, script, "--check"]
        subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)
        target = repo / relative
        if symlink:
            target.symlink_to(copy / "README.md")
        else:
            target.write_text("undeclared", encoding="utf-8")
        result = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, name
        assert expected in result.stderr, name

    repo = tmp_path / "bundle-root-symlink"
    real_bundle = repo / "real-deploy-v"
    shutil.copytree(ROOT, real_bundle)
    linked_bundle = repo / bundle_relative
    linked_bundle.parent.mkdir(parents=True)
    linked_bundle.symlink_to(real_bundle, target_is_directory=True)
    result = subprocess.run(
        [sys.executable, script, "--check"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "symlink is not valid" in result.stderr


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


def test_handoff_validator_is_reverified_from_the_bytes_executed(tmp_path: Path):
    copy = tmp_path / "deploy_v"
    shutil.copytree(ROOT, copy)
    bundle = DeployVBundle(copy)
    target = copy / "skills" / "cp-model" / "scripts" / "validate_handoff.py"
    target.write_bytes(target.read_bytes() + b"\n# swapped after startup\n")

    with pytest.raises(MethodologyError, match="integrity mismatch"):
        bundle.validate_handoff(
            "",
            module_id="CP-1",
            run_id="run-1",
            reporting_period="2026-09-01",
        )


def test_rehashed_calculator_cannot_retain_the_prior_build_identity(tmp_path: Path):
    copy = tmp_path / "deploy_v"
    shutil.copytree(ROOT, copy)
    relative = "scripts/credit_metrics.py"
    target = copy / "skills" / "cp-1-canonical-data-foundation" / relative
    changed = target.read_bytes() + b"\n# unapproved calculator change\n"
    target.write_bytes(changed)
    integrity_path = copy / "DEPLOY_V_INTEGRITY_v1.json"
    integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
    entry = next(
        skill for skill in integrity["skills"]
        if skill["folder_slug"] == "cp-1-canonical-data-foundation"
    )
    entry["relative_file_hashes"][relative] = {
        "bytes": len(changed),
        "sha256": hashlib.sha256(changed).hexdigest(),
    }
    integrity_path.write_text(
        json.dumps(integrity, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(MethodologyError, match="build identity mismatch"):
        DeployVBundle(copy)


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


def test_source_preparation_and_readiness_are_separate_runnable_profiles():
    bundle = DeployVBundle(ROOT)
    skill = (ROOT / "skills" / "cp-0-source-readiness" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    cp0, cp_parse = skill.split("## CP-PARSE runnable profile", maxsplit=1)
    cp0_contract = next(
        module["artifact_contract"]
        for module in bundle.catalog["modules"]
        if module["module_id"] == "CP-0"
    )

    assert bundle.catalog["preparation_stage"] == {
        "module_id": "CP-PARSE",
        "module_name": "DataPreparation",
        "owned_object": "document_parse_manifest",
        "required_before": "CP-0",
        "runnable": True,
    }
    assert "CP-PARSE" not in bundle.catalog["superseded_module_ids"]
    logical = {
        entry["entry_id"]: entry for entry in bundle.manifest["logical_entries"]
    }
    assert logical["CP-PARSE"]["relationship"] == "runnable_profile"
    physical = next(
        entry for entry in bundle.manifest["skills"]
        if entry["folder_slug"] == "cp-0-source-readiness"
    )
    assert physical["aliases"] == []
    assert physical["runnable_module_ids"] == ["CP-PARSE", "CP-0"]
    pinned = next(
        entry for entry in bundle.integrity["skills"]
        if entry["folder_slug"] == "cp-0-source-readiness"
    )
    assert pinned["aliases"] == []
    assert pinned["runnable_module_ids"] == ["CP-PARSE", "CP-0"]
    retrieval = {
        entry["module_id"]: entry for entry in bundle.retrieval["skills"]
    }
    assert retrieval["CP-PARSE"] == {
        "aliases": [],
        "folder_slug": "cp-0-source-readiness",
        "module_id": "CP-PARSE",
        "skill_md": "skills/cp-0-source-readiness/SKILL.md",
    }
    assert retrieval["CP-0"]["aliases"] == []
    assert cp0_contract["required_table_count"] == 8
    assert cp0_contract["required_table_ids"] == [f"T{index}" for index in range(1, 9)]
    assert "**Owned object:** `source_readiness_register`" in cp0
    assert "`[IssuerID]_CP-0_[YYYYMMDD].md`" in cp0
    assert "**Owned object:** `document_parse_manifest`" in cp_parse
    assert "`[PackKey]_CP-PARSE_[YYYYMMDD].md`" in cp_parse
    assert "## Output profile — binding on CP-PARSE" in cp_parse
    assert "CP-PARSE is no longer a separate stage" not in skill
    assert "Also answers `Run CP-PARSE`" not in skill


def test_distressed_routes_match_the_required_causal_graph():
    bundle = DeployVBundle(ROOT)
    full_edges = bundle.catalog["profiles"]["FULL_CREDIT_32"]["edges"]
    lite_edges = bundle.catalog["profiles"]["LITE_CREDIT_22"]["edges"]
    assert {
        "source": "CP-4C", "target": "CP-6", "type": "REQUIRED",
    } in full_edges
    assert {
        "accepted_object_id": "lite_fundamental_credit_screen",
        "allowed_use": "SCREENING_ONLY",
        "source": "CP-L10",
        "target": "CP-2A",
        "type": "REQUIRED",
    } in lite_edges

    screen = bundle.compile(
        "DISTRESSED_RESTRUCTURING", Depth.SCREEN, "set-1", source_set_version=1
    )
    assert [node["module_id"] for node in screen["nodes"]] == [
        "CP-PARSE", "CP-0", "CP-L10", "CP-2A", "CP-2H", "CP-4C",
    ]
    screen_by_id = {node["module_id"]: node for node in screen["nodes"]}
    assert screen_by_id["CP-2A"]["dependencies"] == ["CP-L10"]
    assert screen_by_id["CP-4C"]["dependencies"] == ["CP-2A", "CP-L10"]

    full = bundle.compile(
        "DISTRESSED_RESTRUCTURING", Depth.FULL, "set-1", source_set_version=1
    )
    expected = [
        "CP-PARSE", "CP-0", "CP-1", "CP-2", "CP-2A", "CP-2G", "CP-2H",
        "CP-4", "CP-4C", "CP-3", "CP-6",
    ]
    assert [node["module_id"] for node in full["nodes"]] == expected
    full_by_id = {node["module_id"]: node for node in full["nodes"]}
    assert full_by_id["CP-6"]["dependencies"] == [
        "CP-1", "CP-2", "CP-2A", "CP-3", "CP-4C",
    ]
    for stage, node in enumerate(full["nodes"]):
        assert node["stage"] == stage
        assert node["route_node_id"] == (
            f"RN-FULL_CREDIT_32-DISTRESSED_RESTRUCTURING-{stage:02d}-{node['module_id']}"
        )


def test_unknown_pathway_and_route_fail_closed():
    bundle = DeployVBundle(ROOT)
    with pytest.raises(MethodologyError):
        bundle.compile("NOT_A_PATHWAY", Depth.FULL, None)


# --- route goldens: drift in the compiled bundle fails loudly --------------------------


ROUTE_GOLDENS = {
    # digest({"nodes": [...], "edges": sorted(...)}) per (pathway, depth) for Deploy V
    # build 237bf4bc… (DECISIONS §14.12). A bundle change that moves a route moves
    # this table in the same commit, with the reason recorded in DECISIONS.
    ("FULL_CREDIT", "screen"): "fc8c7d00d8de0235c5fc448a4035ef81267e3d510ccff050694968b47f91cae4",
    ("FULL_CREDIT", "full"): "a136490f29dbc2ab37ebd5b88959a454933249a35599fb6303d90890b93b1482",
    ("EARNINGS_UPDATE", "screen"): "f6dc80f6d3112528fb1ea13ae8ea8a0a9346d0c5c26ea94a62c12cdc88d83210",
    ("EARNINGS_UPDATE", "full"): "d7ae6f00b15b0b9a531f19cfdce7f6612c54e83fd192f7e729f9a95b73c183cc",
    ("COVENANT_REFINANCING", "screen"): "01eeda176b7750fb6509d395b805836d0ec98ccc638f1eeb2113d73376283583",
    ("COVENANT_REFINANCING", "full"): "778e23c9aba02a3ea18a5d0b7654aa01a379644b73761ed6e35a07bc76cc4be1",
    ("RELATIVE_VALUE", "screen"): "29f9e5c1a0d2cf26183492466a5609301781f3b01669d1aabc1b29a31baf1d69",
    ("RELATIVE_VALUE", "full"): "cf65aff78c977246b3a35ff9be34cb1bc4785adf2b84d1b4127d98c385ef1b7b",
    ("DISTRESSED_RESTRUCTURING", "screen"): "89d9f1349bc77274817e916d1a5ada97fd0b1f76eda48400b68abe2efc683f21",
    ("DISTRESSED_RESTRUCTURING", "full"): "db295cc68ac2684b76b6569752a55213972f66368c8876e0376f4f4996f23783",
    ("DEEP_RESEARCH", "screen"): "aa119a7665f540a33b992f0da6847ea18453b138069e1d24a3d10281b58ad114",
    ("DEEP_RESEARCH", "full"): "aa119a7665f540a33b992f0da6847ea18453b138069e1d24a3d10281b58ad114",
}


@pytest.mark.parametrize(("pathway", "depth"), sorted(ROUTE_GOLDENS))
def test_compiled_route_matches_its_pinned_golden(pathway, depth):
    """Invariant 10's purity test compares two compilations of the same route
    and passes on any bundle; this pin catches a catalog edit that moves a
    node or an edge, which then has to be a deliberate, recorded change."""
    from caos.contracts import digest
    from caos.engine.graphs import compiled_route

    route = compiled_route(pathway, depth)
    actual = digest({"nodes": list(route.nodes), "edges": sorted(list(edge) for edge in route.edges)})
    assert actual == ROUTE_GOLDENS[(pathway, depth)], (
        f"{pathway}/{depth} compiled to a different node or edge set: "
        f"nodes={list(route.nodes)} edges={sorted(route.edges)}"
    )
