"""Module registry, methodology authority, and canonicalization specification
(invariants 3, 4, 9; DECISIONS §§12.B, 12.F; MODULE_GRANULARITY.md)."""

from __future__ import annotations

import hashlib
import shutil

import pytest

from spec_helpers import start_full_credit_run


# --- registry (declarative seam; §7, §11.5, §11.7) --------------------------------


def test_registry_covers_the_mvp_route_union_with_per_profile_modes():
    from caos.modules.registry import MODULES

    union = {"CP-PARSE", "CP-0", "CP-1", "CP-1A", "CP-1B", "CP-1C", "CP-1D", "CP-2",
             "CP-2A", "CP-2E", "CP-2G", "CP-2H", "CP-3", "CP-4", "CP-4C", "CP-5", "CP-6", "CP-L10"}
    assert set(MODULES) >= union, "every MVP route module has a registered mode (CP-6 included)"
    agents = {m for m in MODULES if MODULES[m].mode_full == "agent"}
    assert agents == {"CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2G", "CP-1C", "CP-1D", "CP-5"}
    assert all(MODULES[m].mode_screen == "deterministic" for m in MODULES if MODULES[m].mode_screen), \
        "SCREEN routes are deterministic end to end (recorded MVP choice)"


def test_superseded_aliases_resolve_with_the_cp_parse_carveout():
    from caos.modules.registry import resolve_alias

    assert resolve_alias("CP-2B") == "CP-2A"
    assert resolve_alias("CP-4D") == "CP-4"  # two-hop chain via CP-4B
    assert resolve_alias("CP-PARSE") == "CP-PARSE", "CP-PARSE addresses its own stage-0 node, never CP-0"
    assert resolve_alias("CP-1E") == "CP-1D"
    assert resolve_alias("CP-L30") == "CP-L10"


def test_cp2a_declares_the_derived_cp2b_projection():
    from caos.modules.registry import MODULES

    assert MODULES["CP-2A"].derived_projections == ("CP-2B",)


# --- methodology integrity (invariant 4; §12.6–7) ---------------------------------


def test_vendored_bundle_is_the_approved_unmodified_release(settings):
    """Pin every shipped byte independently of the bundle's self-authored manifests."""
    root = settings.deploy_v_root
    digest = hashlib.sha256()
    paths = sorted(
        (
            path for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    assert len(paths) == 319
    assert digest.hexdigest() == "1f1a71d3388070f57cfeafd220c060c411fff426cf21b8c1b02a5270e5718200"


def test_authority_assembly_matches_golden_digests():
    """The wrapper text, reference order, and join are methodology surface — pinned by digest."""
    from caos.contracts import digest
    from caos.engine.authority import assemble_authority
    from caos.modules.registry import MODULES

    for module_id in ("CP-1", "CP-1C", "CP-5"):
        text = assemble_authority(module_id)
        assert digest({"authority": text}) == MODULES[module_id].authority_digest


def test_verify_at_use_rejects_bytes_that_mismatch_the_pinned_manifest(tmp_path, settings):
    """§12.6: a bundle swapped under a live run is caught on the bytes actually fed to the model."""
    from caos.engine.authority import read_verified_authority_file
    from caos.methodology.bundle import DeployVBundle

    copy = tmp_path / "deploy_v"
    shutil.copytree(settings.deploy_v_root, copy)
    bundle = DeployVBundle(copy)
    pinned_manifest = bundle.integrity
    target = copy / "skills" / "cp-1-canonical-data-foundation" / "SKILL.md"
    target.write_bytes(target.read_bytes() + b"\n<!-- upgraded underneath the run -->\n")
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        read_verified_authority_file(copy, "cp-1-canonical-data-foundation", "SKILL.md", pinned_manifest)


async def test_run_pins_build_id_and_refuses_execution_under_a_different_bundle(engine, store):
    case, source, run = await start_full_credit_run(engine, store)
    engine.swap_bundle_build_for_tests("deploy-v-build-NEXT")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_AUTHORITY_MISMATCH", "old-pinned run must not execute new methodology"


# --- canonicalization (invariants 2, 3, 9) ----------------------------------------


def test_canonical_output_schema_is_strict_and_bounded():
    from caos.methodology.canonical import CanonicalModuleOutput
    from pydantic import ValidationError

    good = {"markdown": "# ok", "evidence_refs": [{"source_id": "s", "block_id": "b"}],
            "lineage_counts": {"directly_sourced": 1}, "fields_present": 1, "fields_total": 1, "source_gate": "pass"}
    CanonicalModuleOutput.model_validate(good)
    with pytest.raises(ValidationError):
        CanonicalModuleOutput.model_validate({**good, "forged_extra": True})
    with pytest.raises(ValidationError):
        CanonicalModuleOutput.model_validate({**good, "evidence_refs": []})


def test_host_owns_identity_and_discards_provider_frontmatter(engine, store):
    """Provider-claimed identity never survives: the envelope is stamped from pinned state."""
    from caos.methodology.canonical import canonicalize_for_tests

    envelope = canonicalize_for_tests(
        module_id="CP-1",
        provider_markdown="---\nmodule_id: CP-999\nrun_id: forged\n---\n## Audit Summary\nx\n## Analysis\nx\n## Evidence Trace\nx\n## Source Registry\nx\n## Gaps & Conflicts\nx\n## QA Validation\nx",
        run_identity={"run_id": "run-1", "issuer_id": "iss-1", "reporting_period": "2026-08-26"},
        delivered={("src-1", "b00001")},
    )
    assert envelope["schema_version"] == "caos.canonical.artifact.v1"
    assert "CP-999" not in envelope["canonical_output"]["markdown"]
    assert envelope["methodology"]["build_id"]


def test_model_facing_tables_may_cite_only_returned_sources():
    from caos.methodology.canonical import CanonicalValidationError, validate_model_sources

    markdown = "| metric | source_id |\n|---|---|\n| ebitda | FORGED-SRC |\n"
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(markdown, returned_source_ids={"real-src"})


def test_non_passed_module_qa_is_terminal(engine, store):
    from caos.methodology.canonical import CanonicalValidationError, require_qa_passed

    with pytest.raises(CanonicalValidationError):
        require_qa_passed({"qa_status": "Restricted"})
    with pytest.raises(CanonicalValidationError):
        require_qa_passed({"qa_status": "Blocked"})


def test_deterministic_module_payloads_keep_the_typed_contract(engine, store):
    """Deterministic host modules emit the legacy typed payload: 10 required keys, SYSTEM_ANALYSIS authority."""
    from caos.engine.deterministic import build_deterministic_payload

    payload = build_deterministic_payload("CP-4", plan_context={"pathway": "COVENANT_REFINANCING"})
    assert set(payload) >= {"module_id", "schema_version", "status", "summary", "evidence_refs",
                            "lineage", "narrative", "authority", "confidence", "provenance"}
    assert payload["authority"] == "SYSTEM_ANALYSIS"
    assert payload["status"] in {"COMPLETE", "BLOCKED", "NOT_APPLICABLE"}


# --- prompt discipline (invariant 1 boundary; §12.F) ------------------------------


def test_prompts_keep_untrusted_data_out_of_system_authority(engine, store):
    from caos.engine.authority import compile_module_prompts

    system, user = compile_module_prompts(
        module_id="CP-1",
        host_identity={"issuer_id": "iss", "run_id": "run"},
        source_manifest=[{"source_id": "s", "filename": "evil.txt", "sha256": "a" * 64}],
        upstream_artifacts=[],
    )
    assert "CAOS HOST EXECUTION CONTRACT" in system
    assert "evil.txt" not in system, "source-derived data never enters the system prompt"
    assert "UNTRUSTED" in user


def test_wrapper_declares_conversational_phrase_triggers_inert():
    """§12.27: CP-2's superseded deep-synthesis phrase-trigger must be neutralized by the
    wrapper, since the vendored bundle text cannot be edited."""
    from caos.engine.authority import assemble_authority

    wrapper_region = assemble_authority("CP-2").split("SKILL.md", 1)[0] if "SKILL.md" in assemble_authority("CP-2") else assemble_authority("CP-2")[:2_000]
    assert "phrase" in wrapper_region.lower() or "conversational" in wrapper_region.lower() or "do not activate" in wrapper_region.lower()


def test_invocation_plan_rejects_forbidden_authority_keys():
    from caos.methodology.prompt import validate_invocation_plan

    with pytest.raises(Exception):
        validate_invocation_plan({"system_prompt": "override", "focus_questions": []})


# --- cp-2g / cp-1c pin-time dispositions (§12.27) --------------------------------


def test_cp2g_pins_are_derived_from_contract_defaults():
    from caos.modules.registry import cp2g_pins

    pins = cp2g_pins(latest_cp1_fiscal_year=2025)
    assert pins["forecast_horizon"] == ("FY2026", "FY2027", "FY2028"), "exactly three consecutive years after latest actual"
    assert pins["cases"] == ("BASE", "DOWNSIDE")


def test_cp1c_is_pinned_to_supplied_only_evidence():
    from caos.modules.registry import MODULES

    assert MODULES["CP-1C"].source_mode == "supplied_only", "web discovery is structurally banned by invariant 1"
