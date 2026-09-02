"""Module registry, methodology authority, and canonicalization specification
(invariants 3, 4, 9; DECISIONS §§12.B, 12.F; MODULE_GRANULARITY.md)."""

from __future__ import annotations

import hashlib
import shutil

import pytest

from spec_helpers import start_full_credit_run


# --- registry (declarative seam; §7, §11.5, §11.7) --------------------------------


def test_registry_covers_the_mvp_route_union_with_provider_backed_semantics():
    from caos.modules.registry import MODULES

    union = {"CP-PARSE", "CP-0", "CP-1", "CP-1A", "CP-1B", "CP-1C", "CP-1D", "CP-2",
             "CP-2A", "CP-2E", "CP-2G", "CP-2H", "CP-3", "CP-4", "CP-4C", "CP-5", "CP-6", "CP-L10"}
    assert set(MODULES) >= union, "every MVP route module has a registered mode (CP-6 included)"
    assert all(MODULES[module_id].mode_full == "agent" for module_id in union)
    assert all(MODULES[module_id].mode_screen == "agent" for module_id in union), \
        "SCREEN still requires source-derived semantic interpretation"
    assert all(MODULES[module_id].skill_slug for module_id in union)
    assert all(MODULES[module_id].reference_files for module_id in union)
    assert all(MODULES[module_id].max_output_tokens > 0 for module_id in union)


def test_superseded_aliases_resolve_without_absorbing_cp_parse():
    from caos.modules.registry import resolve_alias

    assert resolve_alias("CP-2B") == "CP-2A"
    assert resolve_alias("CP-4D") == "CP-4"  # two-hop chain via CP-4B
    assert resolve_alias("CP-PARSE") == "CP-PARSE", "CP-PARSE addresses its own stage-0 node, never CP-0"
    assert resolve_alias("CP-1E") == "CP-1D"
    assert resolve_alias("CP-L30") == "CP-L10"


def test_cp2a_declares_the_derived_cp2b_projection():
    from caos.modules.registry import MODULES

    assert MODULES["CP-2A"].derived_projections == ("CP-2B",)


def test_registry_pins_each_module_calculator_allowlist():
    from caos.modules.registry import MODULES

    assigned = {module_id: spec.calculators for module_id, spec in MODULES.items() if spec.calculators}
    assert assigned == {
        "CP-1": ("credit_metrics",),
        "CP-1B": ("credit_metrics",),
        "CP-1C": ("peer_statistics",),
        "CP-2E": ("rate_fx_sensitivity",),
        "CP-2G": ("credit_metrics", "liquidity_bridge"),
        "CP-2H": ("bond_analytics", "covenant_headroom"),
        "CP-3": ("recovery_waterfall",),
        "CP-4": ("covenant_headroom",),
        "CP-4C": ("funding_gap", "recovery_waterfall"),
    }


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
    assert digest.hexdigest() == "9905f67b31bd5fb5c80ec101e402916f9adbfc6e0725f5939dd5ec378140ccf4"


def test_authority_assembly_matches_golden_digests():
    """The wrapper text, reference order, and join are methodology surface — pinned by digest."""
    from caos.contracts import digest
    from caos.engine.authority import assemble_authority
    from caos.modules.registry import MODULES

    for module_id in MODULES:
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


def test_verify_at_use_rejects_self_rehashed_but_unapproved_authority(tmp_path, settings):
    """A mutable manifest cannot promote new prompt authority past the registry golden."""
    from caos.engine.authority import assemble_authority
    from caos.methodology.bundle import DeployVBundle

    copy = tmp_path / "deploy_v"
    shutil.copytree(settings.deploy_v_root, copy)
    bundle = DeployVBundle(copy)
    target = copy / "skills" / "cp-1-canonical-data-foundation" / "SKILL.md"
    changed = target.read_bytes() + b"\n<!-- internally rehashed but not approved -->\n"
    target.write_bytes(changed)
    entry = next(
        skill for skill in bundle.integrity["skills"]
        if skill["folder_slug"] == "cp-1-canonical-data-foundation"
    )
    entry["relative_file_hashes"]["SKILL.md"] = {
        "bytes": len(changed),
        "sha256": hashlib.sha256(changed).hexdigest(),
    }

    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        assemble_authority("CP-1", root=copy, pinned_manifest=bundle.integrity)


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
    for invalid in (
        {**good, "lineage_counts": {"directly_sourced": -1}},
        {**good, "findings": {"CRITICAL": -1}},
        {**good, "fields_present": 2, "fields_total": 1},
        {**good, "lineage_counts": {"invented": 1}},
        {**good, "limitation_flags": ["flag"] * 51},
        {**good, "limitation_flags": ["   "]},
        {**good, "validation_warnings": ["warning\x07"]},
    ):
        with pytest.raises(ValidationError):
            CanonicalModuleOutput.model_validate(invalid)


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


def test_host_rebuilds_complete_cp_model_handoff_metadata(engine):
    from caos.methodology.canonical import canonicalize_for_tests

    body = "\n".join(
        f"## {heading}\nverified"
        for heading in (
            "Audit Summary", "Analysis", "Evidence Trace", "Source Registry",
            "Gaps & Conflicts", "QA Validation",
        )
    )
    identity = {
        "module_id": "CP-1",
        "module_name": "CanonicalDataFoundation",
        "run_id": "run-1",
        "issuer_name": "Acme Credit Ltd",
        "issuer_id": "case-1",
        "analysis_date": "2026-09-01",
        "reporting_period": "2026-09-01",
    }
    metadata = {
        "module_id": "CP-1",
        "module_name": "CanonicalDataFoundation",
        "run_id": "run-1",
        "reporting_period": "2026-09-01",
        "analysis_date": "2026-09-01",
        "confidence_score": 100,
        "confidence_band": "High",
        "qa_status": "Passed",
        "committee_status": "Draft Only",
        "limitation_flags": [],
        "validation_warnings": [],
        "upstream_artifacts_used": [{
            "module_id": "CP-0",
            "run_id": "run-1",
            "period": "2026-09-01",
            "artifact_digest": "a" * 64,
        }],
        "downstream_consumers": ["CP-MODEL"],
        "issuer_name": "Acme Credit Ltd",
        "issuer_id": "case-1",
    }

    envelope = canonicalize_for_tests(
        module_id="CP-1",
        provider_markdown="---\nissuer_name: forged\n---\n" + body,
        run_identity=identity,
        delivered={("source-1", "block-1")},
        handoff_metadata=metadata,
    )
    validation = engine.bundle.validate_handoff(
        envelope["canonical_output"]["markdown"],
        module_id="CP-1",
        run_id="run-1",
        reporting_period="2026-09-01",
    )

    assert not validation.errors
    assert not validation.identity_mismatches
    assert validation.fields == metadata
    assert "forged" not in envelope["canonical_output"]["markdown"]


def test_canonicalization_rejects_render_deception_but_accepts_normal_rtl(monkeypatch):
    from caos.methodology import canonical
    from caos.methodology.canonical import MAX_CANONICAL_MARKDOWN_CHARS, canonicalize_for_tests

    body = "\n".join(
        f"## {heading}\nشركة النور"
        for heading in (
            "Audit Summary", "Analysis", "Evidence Trace", "Source Registry",
            "Gaps & Conflicts", "QA Validation",
        )
    )
    envelope = canonicalize_for_tests(
        module_id="CP-1",
        provider_markdown=body,
        run_identity={"run_id": "run-1"},
        delivered={("source-1", "block-1")},
    )
    assert "شركة النور" in envelope["canonical_output"]["markdown"]
    for dangerous in ("\x07", "\u202e", "\u2066"):
        with pytest.raises(ValueError):
            canonicalize_for_tests(
                module_id="CP-1",
                provider_markdown=body + dangerous,
                run_identity={"run_id": "run-1"},
                delivered={("source-1", "block-1")},
            )
    expansion = body + "\u0958" * (MAX_CANONICAL_MARKDOWN_CHARS - len(body))
    with pytest.raises(ValueError, match="normalized size"):
        canonicalize_for_tests(
            module_id="CP-1",
            provider_markdown=expansion,
            run_identity={"run_id": "run-1"},
            delivered={("source-1", "block-1")},
        )

    fenced = body.replace(
        "شركة النور\n## Analysis",
        "شركة النور\n```text\n## Analysis",
        1,
    )
    with pytest.raises(ValueError, match="canonical H2 headings"):
        canonicalize_for_tests(
            module_id="CP-1",
            provider_markdown=fenced,
            run_identity={"run_id": "run-1"},
            delivered={("source-1", "block-1")},
        )

    monkeypatch.setattr(canonical, "MAX_CANONICAL_MARKDOWN_CHARS", len(body))
    with pytest.raises(ValueError, match="final size"):
        canonicalize_for_tests(
            module_id="CP-1",
            provider_markdown=body,
            run_identity={"run_id": "run-1"},
            delivered={("source-1", "block-1")},
        )


def test_model_facing_tables_may_cite_only_returned_sources():
    from caos.methodology.canonical import CanonicalValidationError, validate_model_sources

    markdown = "| metric | source_id |\n|---|---|\n| ebitda | FORGED-SRC |\n"
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(markdown, returned_source_ids={"real-src"})
    with pytest.raises(CanonicalValidationError):
        validate_model_sources("Narrative without a source table", returned_source_ids={"real-src"})
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(
            "```text\n| metric | source_id |\n|---|---|\n| ebitda | real-src |\n```",
            returned_source_ids={"real-src"},
        )
    for hidden_table in (
        "<!--\n| metric | source_id |\n|---|---|\n| ebitda | real-src |\n-->",
        "    | metric | source_id |\n    |---|---|\n    | ebitda | real-src |",
        " \t| metric | source_id |\n \t|---|---|\n \t| ebitda | real-src |",
        "  \t| metric | source_id |\n  \t|---|---|\n  \t| ebitda | real-src |",
        "   \t| metric | source_id |\n   \t|---|---|\n   \t| ebitda | real-src |",
        ">     | metric | source_id |\n>     |---|---|\n>     | ebitda | real-src |",
        "> -     | metric | source_id |\n>       |---|---|\n>       | ebitda | real-src |",
        "| metric | source_id |\n| | |\n| ebitda | real-src |",
        "| metric | source_id |\n| : | : |\n| ebitda | real-src |",
        "| metric | source_id |\n|---|\n| ebitda | real-src |",
        "> ```text\n> | metric | source_id |\n> |---|---|\n> | ebitda | real-src |\n> ```",
        "- ```text\n  | metric | source_id |\n  |---|---|\n  | ebitda | real-src |\n  ```",
        "> <div>\n> | metric | source_id |\n> |---|---|\n> | ebitda | real-src |\n> </div>",
        *(
            f"<{tag}>\n| metric | source_id |\n|---|---|\n| ebitda | real-src |\n</{tag}>"
            for tag in ("pre", "script", "style", "textarea", "div")
        ),
    ):
        with pytest.raises(CanonicalValidationError):
            validate_model_sources(hidden_table, returned_source_ids={"real-src"})
    validate_model_sources(
        "| metric | source_id |\n|---|---|\n| ebitda | real-src |\n",
        returned_source_ids={"real-src"},
    )
    for valid_table in (
        "metric | source_id\n--- | ---\nebitda | real-src",
        "| metric | source_id\n| --- | ---\n| ebitda | real-src",
        "metric | source_id |\n--- | --- |\nebitda | real-src |",
        "| metric | `source_id` |\n| --- | --- |\n| a `|` b | real-src |",
    ):
        validate_model_sources(valid_table, returned_source_ids={"real-src"})

    authorized = "| source_id | value |\n| --- | --- |\n| real-src | 1 |"
    for unauthorized_table in (
        "source_id | value\n--- | ---\nforged-src | 999",
        "| source_id | claim |\n| --- | --- |\n| forged-src | foo \\| bar |",
        "| source_id | claim |\n| --- | --- |\n| forged-src | `foo | bar` |",
        "> | source_id | value |\n> | --- | --- |\n> | forged-src | 9 |",
        "- source_id | value\n  --- | ---\n  forged-src | 9",
        "| [source_id](https://example.invalid) | value |\n| --- | --- |\n| forged-src | 9 |",
        "| source&#95;id | value |\n| --- | --- |\n| forged-src | 9 |",
        "> | source_id |\n> | --- |\n| real-src |",
        "> | source_id |\n| --- |\n| real-src |",
        "| source_id |\n| --- |\n- | real-src |",
    ):
        with pytest.raises(CanonicalValidationError):
            validate_model_sources(
                f"{authorized}\n\n{unauthorized_table}",
                returned_source_ids={"real-src"},
            )
    cp2a_register = (
        f"{authorized}\n\n"
        "| Event ID | Source Document | Event Description |\n"
        "| --- | --- | --- |\n"
        "| EVT-1 | forged-src fabricated filing | Covenant test |"
    )
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(
            cp2a_register,
            returned_source_ids={"real-src"},
            module_id="CP-2A",
        )
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(
            cp2a_register.replace(
                "forged-src fabricated filing",
                "real-src, forged-src fabricated filing",
            ),
            returned_source_ids={"real-src"},
            module_id="CP-2A",
        )
    with pytest.raises(CanonicalValidationError):
        validate_model_sources(
            f"{authorized}\n\n"
            "| check_id | source_refs |\n"
            "| --- | --- |\n"
            "| CHECK-1 | forged-src |",
            returned_source_ids={"real-src"},
            module_id="CP-1",
        )


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
