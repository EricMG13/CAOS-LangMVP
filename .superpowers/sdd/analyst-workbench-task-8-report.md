# Analyst Workbench Task 8 report

Date: 2026-09-07. Base: `d25616f0f22e1816cc9cf3b7b4451363ff9615cb`.
Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex`.
Branch: `codex/analyst-workbench-capabilities`. Task 8 only; no push, PR, merge, deployment, live provider, credentials, real cases, methodology or renderer implementation.

## Result and boundaries

The shared ModelService publication resolver selects the accepted Earnings/Covenant overlay, or a compatible current Signed-Off Revision, instead of the prior Full Credit build alone. Existing current-build replay resolves/recomputes the nearest Full Credit ancestor, accepted calculations, source lineage and worksheet payload. The selected overlay authority includes that exact replayed effect's `base_model`; the content/model/frozen digests bind both. Missing/current-mismatched overlays raise typed stale/not-ready refusal and eligibility offers no historical fallback.

The resolver rejects a case whose accepted pointer names another case's valid snapshot, and validates selected build accepted-run/source-set/registry-version metadata. DeliverableService validates the accepted effect/snapshot/run/pathway relationship and accepts only ACTIVE revisions with exact build/registry/assumptions/output identity. The previous special STALE prior-Full-Credit revision allowance is removed.

V2 composition distinguishes unchanged inherited application worksheet values, selected Signed-Off Revision outputs reflecting analyst assumptions, and accepted pathway calculations/effect tables. It retains existing validated `_unit` behavior; no guessed currency, unit, trend, or forecast recalculation. Optional RV selection includes supplied marks/calculations; DR selection records revalidation and `numeric_effect: NONE`. Both remain usable without a selected model.

Distressed/RV/DR retain their existing `CURRENT_ACCEPTED_MODEL` publication identity shape. Their exact prior ancestry already rides their frozen `pathway_effects` and payload digest, so adding unrelated identity metadata would unnecessarily stale existing filing selections. V1 composer functions and frozen/queued worker rendering stay unchanged. Earnings/Covenant old prior-base selections must be replaced/re-signed under current authority; historical frozen/filed reads and exports use frozen integrity, never live model resolution.

## Caller and impact trace

- `_validated_prior_full_credit_publication_build` has one caller: `validated_publication_build`.
- Public resolver callers: `DeliverableService._live_build`, `_live_revision`, `model_eligibility`.
- Selection flows through save_draft, opinion binding/staleness, freeze payload construction and independent filing. The source authority and sign-off guards/CAS/audit transaction boundaries were not changed.
- `_require_current` resolves the current accepted snapshot; `_validate_build_identity` compares recomputed payload/QA/default assumption/output digests. Overlay replay uses `_prior_full_credit_snapshot` and `_validated_base_build`, and reexecutes accepted calculation records.
- `_compute_build_result` preserves legacy/current worksheet schema dispatch; response-only worksheet_navigation remains outside payload/revision identities.
- Frozen worker publishes the queued payload after digest verification. Frozen retrieval/export verifies retained payload/export digests; filing additionally revalidates current authority.
- GitNexus was unavailable per controller constraints; scoped rg references and real Python/test checks were used.

## TDD and fixture evidence

1. Before production edits, updated existing incremental test failed at queued eligibility: prior Full Credit was incorrectly offered (`1 failed, 136 deselected in 5.70s`).
2. Before production edits, actual accepted Earnings metamorphic test failed because resolver returned the base ID instead of the accepted overlay (`1 failed, 27 deselected, 1 warning in 10.63s`).
3. Initial scripted fixture adaptation reached missing queued overlay: that scripted run has no valid incremental calculator coverage. The existing test was moved to the already-established AnswerKeyProvider harness at the ordinary provider port, retaining every freeze/file identity assertion. This is actual acceptance/build/report orchestration over fixture analytical inputs, not live analysis.
4. Metamorphic accepted runs change Earnings revenue from 1000 to 1200 and Covenant threshold from 5 to 6. Their report effect tables/model identities/digests change while the stored Full Credit build and worksheet remain equal. A prior signed overlay becomes STALE and is refused after new acceptance. Both pathways are exercised.
5. Existing incremental publication covers both application and analyst selections. The analyst branch changes a READY forward growth assumption and proves signed output digest differs from the application build. V2 composition uses these exact selected outputs and appropriate labels. Actual freeze/retry/independent filing is explicitly v1.
6. Refusal probe uses actual accepted/storage authority: wrong accepted run, case, registry version/digest, unknown worksheet version, self-consistently rehashed forged effect/ancestry/source links, rehashed accepted ancestry change, source withdrawal and successful retry after restoration. Signed-head corruption is explicitly a returned-head monkeypatch seam isolating fingerprint/registry/state checks; it is not a claimed store tamper integration.
7. Confidence review reproduced an actual corrupted case pointer: create another case, point it to the valid overlay snapshot, call public resolver for the other case. Before the case check: `DID NOT RAISE ValueError`, 1 failed/29 deselected/1 warning in 26.39s. After the guard: complete refusal test 1 passed/29 deselected/1 warning in 62.96s. Refusals leave audit unchanged.
8. Actual accepted RV and DR compose both with no model and with explicitly selected model. RV includes supplied bid_points 88 and calculator tables. DR engine always declares NONE; no nonexistent numeric DR effect is claimed.
9. New actual accepted Distressed v1 freeze/file test proves original identity shape, both funding_gap/recovery_waterfall, prior ancestry, and exact retained exports after withdrawal: 1 passed/30 deselected/1 warning in 34.45s.

## Confidence review — Task 8 complete diff

Least confident about (ranked):

1. Cross-case accepted pointer — helper used snapshot case rather than requested case.
   Investigated: actual store pointer corruption reproduced successful wrong-case resolution.
   Verdict: CONFIRMED bug.
   Patch: reject missing or cross-case accepted snapshot before selecting a model; no writes on refusal.

2. Selecting a READY historical base during an overlay queue — current_build returns latest READY even while newer build is QUEUED.
   Investigated: failing original eligibility and metamorphic tests, actual current-build storage query and all resolver callers.
   Verdict: CONFIRMED bug.
   Patch: require candidate snapshot to equal accepted snapshot, then full existing current-build validation; no prior-base fallback.

3. Forged effect/base/source links with matching outer digest and stale selected model metadata.
   Investigated: actual storage mutation/recompute adversarial probe and worksheet legacy replay tests.
   Verdict: verified fine after shared replay and accepted-run/registry-version checks. Exact replay remains authoritative; payload_digest alone is insufficient.

4. Stale signed revision incorrectly governs later overlay, or fallback escapes a current signed revision.
   Investigated: real Sign-Off followed by accepted effect change; four publication selection branches; current head registry/fingerprint corruption probe.
   Verdict: verified fine. ACTIVE plus exact selected overlay identity required; current signed revision still blocks application fallback.

5. Non-Earnings/Covenant historical identity changing solely because ancestry metadata was newly exposed.
   Investigated: independent filing compares exact current vs frozen model identity; worker and export only validate frozen bytes.
   Verdict: confirmed compatibility risk in initial implementation, corrected before completion.
   Patch: retain existing CURRENT_ACCEPTED_MODEL shape for Distressed/RV/DR, with exact existing ancestry retained in pathway_effects. No historical mutation.

6. Mislabelled full reforecast or analyst adjustment.
   Investigated: engine copies base worksheets; analyst preview recalculates selected assumptions. Real changed growth assumption produces different outputs. Composer uses selected outputs, locked explanatory scope and separate effect sections.
   Verdict: verified fine within v2 composition. V1 formatting is deliberately unchanged for stored/frozen compatibility.

7. Model-optional pathways and units.
   Investigated: actual RV/DR saves both with and without model; DR implementation has no numeric calculator effect; projector still calls existing _unit and warns on unavailable units.
   Verdict: by design. DR NONE is explicit; no synthetic numeric DR claim.

8. Apparent Distressed publication regression.
   Investigated: broad test run failed only ordinary_distressed_e2e's legacy narrative fixture at v2 `REPORT_INPUT_UNAVAILABLE`; both parameterizations reach the same missing-table gate. Baseline module replay at d25616f0 produced the same failure. This is a Task7-default integration regression at the Task8 base, not a preexisting-main defect or Task8 authority failure.
   Patch: controller authorized narrow test-only v1 template pin; all original assertions remain. rg shows _required_deliverable_blocks is used only by _publish_overlay, used by the one two-parameter ordinary test; no other callers silently rely on that fixture. Separate accepted v1 retention check is added above.

9. Concurrency, retries, partial publication and historical reads.
   Investigated: existing guards/CAS calls unchanged, exact freeze retry assertion and independent filing retained, stored-export-after-withdrawal assertion. Broader model/wire tests below.
   Verdict: verified within disposable SQLite orchestration. No new PostgreSQL race/availability claim.

Fixed: prior-base selection, stale-base signed selection, cross-case pointer, selected metadata coherence, compatibility identity overreach, and legacy Distressed test template pin.
By design: unchanged inherited model worksheet; DR NONE; v1 renderer identity preservation; typed v2 missing-input blockers.
Still open: no live analytical qualification; no genuine complete-v2 incremental Sign-Off/freeze case because fixture module tables are incomplete; Task9 actual PDF/XLSX chart drawing not performed.

## Rewrite tournament (no-argument post-edit mode)

Skills read completely: /Users/ericguei/.codex/skills/confidence-review/SKILL.md and /Users/ericguei/.codex/skills/rewrite-tournament/SKILL.md.

Targets selected from own git diff, capped at two material authority symbols: ModelService._validated_prior_full_credit_publication_build and validated_publication_build. Composer _module_document and DeliverableService._validate_pathway_authority were skipped by the two-symbol cap, but covered by owner confidence review and integration checks. Signed revision predicate removal is small simplification; tests/docs are tournament-exempt.

Fresh own roles: t8_incumbent, t8_speed, t8_memory, t8_readability, t8_arbiter. No other root/reviewer agents reused. Roles read complete actual scoped functions and impact contracts; original and complete normalized candidates retained in sibling tournament files. All candidates received identical owner safety/compatibility corrections after the cross-case finding; those are not competing rewrites.

Complete scratch evidence remains ignored and local, not part of the checkpoint (controller-requested packaging):

- [Incumbent defense](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-incumbent.md)
- [Speed candidate](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-speed.md)
- [Memory candidate](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-memory.md)
- [Readability candidate](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-readability.md)
- [Complete normalized blind packet](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-blind.md)
- [Blind bracket](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex/.superpowers/sdd/analyst-workbench-task-8-tournament-bracket.md)

Blind bracket: S1 speed vs S2 memory -> S1; S1 vs S3 readability -> S3; S3 vs S4 incumbent -> S3.
Winner: Snippet A (S3) in final match, replacing the two functions at models/service.py:1051 and :2329.

Justification:
- Direct helper-result assignment removes unnecessary nesting.
- Consistent local authority naming and explicit singleton unpacking improve readability.
- No change to execution/allocation complexity, validation order, calls, signatures, side effects or exceptions.

Backup before applying: /private/tmp/analyst-task8-rewrite.5dY4SK/service.py.
Owner applied the full winning code, re-read the actual diff/callers, ran compileall and real focused tests. Exact final-symbol check: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_source_complete_modelling_spec.py -q -k 'accepted_incremental or incremental_publication_refuses'` -> 3 passed, 27 deselected, 1 warning in 148.53s. Concrete invariant spot-check: two changed accepted calculator effects, identical stored Full Credit model, and no stale/cross-case publication.

Final code:

```python
    def _validated_prior_full_credit_publication_build(
        self,
        build_id: str | None,
        accepted_snapshot: dict[str, Any],
        accepted_run: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if accepted_run.get("pathway") not in PRIOR_FULL_CREDIT_PUBLICATION_PATHWAYS:
            raise ModelInputError("accepted pathway cannot overlay a prior Full Credit model")
        candidate = (
            self.builds.get_build(build_id)
            if build_id is not None
            else self.builds.current_build(accepted_snapshot["case_id"])
        )
        if candidate is None or candidate.get("snapshot_id") != accepted_snapshot["id"]:
            raise ModelBuildStale(None)
        # Current-build replay resolves the nearest Full Credit ancestor and
        # recomputes its payload, the overlay calculations and source lineage.
        build = self.validated_build(accepted_snapshot["case_id"], candidate["id"])
        (effect,) = build["payload"]["pathway_effects"]
        authority = self._publication_model_authority(
            accepted_snapshot,
            build,
            relationship="CURRENT_ACCEPTED_OVERLAY",
        )
        authority["base_model"] = copy.deepcopy(effect["base_model"])
        return build, authority

    def validated_publication_build(
        self,
        case_id: str,
        build_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve the model a deliverable may publish under current authority.

        Overlay identity includes its recomputed nearest Full Credit ancestry;
        the inherited worksheets and accepted pathway effects stay distinct.
        """
        try:
            accepted_snapshot = self._accepted_snapshot(case_id)
            if accepted_snapshot is None or accepted_snapshot.get("case_id") != case_id:
                raise ModelInputError("accepted model authority is unavailable")
            accepted_run = self._validated_snapshot_run(accepted_snapshot)
            if accepted_run["pathway"] in PRIOR_FULL_CREDIT_PUBLICATION_PATHWAYS:
                build, authority = self._validated_prior_full_credit_publication_build(
                    build_id,
                    accepted_snapshot,
                    accepted_run,
                )
            else:
                candidate = (
                    self.builds.get_build(build_id)
                    if build_id is not None
                    else self.builds.current_build(case_id)
                )
                if candidate is None:
                    raise ModelBuildStale(None)
                build = self._require_current(case_id, candidate["id"])
                self._validate_build_identity(case_id, build, self._new_deadline())
                authority = self._publication_model_authority(
                    accepted_snapshot,
                    build,
                    relationship="CURRENT_ACCEPTED_MODEL",
                )
            if (
                build.get("accepted_run_id") != accepted_snapshot["run_id"]
                or build.get("source_set_id") != accepted_snapshot["source_set_id"]
                or build.get("registry_version") != self.bundle.assumption_registry["version"]
            ):
                raise ModelInputError("selected model identity differs from accepted authority")
            _defaults_rows, outputs = self._defaults(build, self._new_deadline())
            return {
                "build": build,
                "outputs": outputs,
                "model_authority": authority,
            }
        except ModelBuildStale:
            raise
        except ValueError as exc:
            if str(exc).startswith("MODEL_REVISION_INVALID"):
                raise
            raise ValueError(
                "MODEL_REVISION_INVALID: accepted model authority is invalid"
            ) from exc
```

## Validation ledger

The full source-complete suite was repeated after fixture/refusal fixes rather than declaring the intermediate 1 failed/29 passed run successful. All final affected checks passed; the broad run's two legacy-fixture failures were reproduced at the Task8 base and then resolved by the authorized test-only v1 pin.

- Initial named deliverables subset: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'incremental or model or authority'` -> 30 passed, 110 deselected, 1 warning in 181.33s. Final latest additions rerun below.
- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py -q -k 'pre_source_link or source_links or unknown_worksheet or publishing_identity or signed_revision_digest'` -> 5 passed, 137 deselected in 44.97s.
- Broad regressions before the legacy fixture pin: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_ordinary_distressed_e2e.py caos/tests/spec/test_distressed_model_overlay.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_module_presentation_spec.py -q` -> 2 failed, 588 passed, 1 warning in 152.02s. Both failures explained above; affected cases rerun after pin.
- Baseline proof: load each of the three changed production modules using `git show d25616f0f22e1816cc9cf3b7b4451363ff9615cb:caos/server/<module>.py`, compile/exec those exact bytes in a fresh Python process, then pytest ordinary_distressed_e2e -q --maxfail=1. The unchanged ordinary test failed at the same REPORT_INPUT_UNAVAILABLE gate: 1 failed, 1 warning in 16.38s. No source file was replaced during this diagnostic.
- `caos/server/.venv314/bin/python -m compileall -q caos/server/caos/models/service.py caos/server/caos/deliverables/service.py caos/server/caos/deliverables/document.py` passed.
- Scoped ruff and git diff --check passed; final rerun recorded below.
- Warning in suites importing FastAPI TestClient: StarletteDeprecationWarning, using httpx with starlette.testclient is deprecated; install httpx2 instead. No dependency changes made.

Final follow-up results (latest code and tests):

- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'incremental or model or authority'` — 30 passed, 110 deselected, 1 warning in 227.94s.
- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'v1 or live_incremental'` — 6 passed, 134 deselected, 1 warning in 205.48s. Includes actual adjusted revision labels, exact frozen publication retry, independent filing, and stored v1 identity compatibility.
- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_ordinary_distressed_e2e.py -q` — 2 passed, 1 warning in 142.33s after the authorized test-only v1 pin; all original full/screen model, publication, filing, reopen/export assertions preserved.
- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py -q -k 'current_worksheet_version or sign_off_validates_exact or legacy_revision_navigation'` — 8 passed, 134 deselected in 49.83s.
- `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_source_complete_modelling_spec.py -q` — final complete collection: **31 passed, 1 warning in 317.12s (0:05:17)**. Includes all accepted effects, optional selections, metadata/source/ancestry refusals, retained Distressed exports and existing source-complete regressions. Earlier full run before the added retained-export case: 30 passed, 1 warning in 299.10s.
- Final scoped `ruff check --config ruff.toml` over all six changed Python files and `git diff --check` — passed. Python compileall of the three production modules — passed.

Exact baseline reproduction command (all shell calls used the declared worktree):

```sh
caos/server/.venv314/bin/python -c 'import importlib, subprocess, sys; sys.path[:0] = ["caos/server", "caos/tests", "caos/tests/spec"]; modules = ["caos.deliverables.document", "caos.models.service", "caos.deliverables.service"]; [(lambda m, source: exec(compile(source, m.__file__, "exec"), m.__dict__))(importlib.import_module(name), subprocess.check_output(["git", "show", "d25616f0f22e1816cc9cf3b7b4451363ff9615cb:caos/server/" + name.replace(".", "/") + ".py"], cwd="/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex")) for name in modules]; import pytest; sys.exit(pytest.main(["caos/tests/spec/test_ordinary_distressed_e2e.py", "-q", "--maxfail=1"]))'
```
