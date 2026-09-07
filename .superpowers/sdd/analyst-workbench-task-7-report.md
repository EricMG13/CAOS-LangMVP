# Task 7 — Module-populated, developer-designed Report

## Baseline and scope

- Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex`.
- Branch: `codex/analyst-workbench-capabilities`; clean starting HEAD `2c4ae3d12ce689129ff6256d89ecb41492c2e928`.
- Task 7 only. No original-checkout edits, methodology changes, external provider calls, model-resolver rewrite, new dependencies, chart editor, workflow framework, deployment or remote Git action.
- Read Task 7 brief, global constraints, review focus, applicable root/frontend instructions, frontend product/design context, installed Next client-component guidance and the relevant Workbench compatibility decision (`docs/DECISIONS.md`, decision 26). No prior task reports were used as implementation requirements.

## Outcome and interfaces

New reports use `caos.deliverable-template.v2`. The only required client block is the Evidence Register; the server composes fixed sections from accepted module presentations and validated selected model outputs. Full Credit is titled **Credit Report**. The other five titles and all pathway identities remain unchanged. Optional commentary and limitations are explicitly analyst-authored overlays. Declared optional `ic_context` defaults omitted with a stored explanation; no CP-6 or IC memo prerequisite was added.

`DeliverableDraftRequest` adds only bounded `included_optional_section_ids` (at most 20 declared unique IDs; `None` retains the prior choice, `[]` deliberately omits). Generated point recipes and analytical content are not accepted as client facts. V2 revision content records `mapping_version`, `included_optional_section_ids`, `citation_union`, and `publication_blockers`. V1 revision content does not acquire these fields.

Workspace GET adds a typed server preview and latest template metadata. With no saved draft it composes accepted module content before an explicit save. Accepted-route/source failures expose no partial analytical content. Model-only failure can leave valid modules visible, with a model-specific code and/or `MODEL_SELECTION_REQUIRED`; selection remains explicit. The inner model boundary covers the existing selection errors (`MODEL_REVISION_STALE`, `MODEL_BUILD_STALE`, `MODEL_FALLBACK_INELIGIBLE`, `MODEL_SELECTION_INVALID`) and existing pathway-model authority refusals; it does not suppress accepted route/source validation, which runs separately first. Composition additionally produces `REPORT_INPUT_UNAVAILABLE` for each missing required section. Save/sign/freeze retain their strict model/source boundaries.

Both freeze-time template lookups, workspace, save and composition dispatch recorded template identity. V2 recomposition uses its recorded mapping. Missing mapping fails with `MAPPING_VERSION_UNSUPPORTED`; no fallback reinterprets retained content. A future mapping adoption requires an explicit new revision/version decision; no automatic migration mechanism was added.

The citation union groups exact artifact evidence `(source_id, block_id)` pairs and analyst citations, narrowing chart references by the chart's declared sources. It drives the visible Evidence Register, sign authority, frozen `payload.evidence`, publication inventory/status, and offline verification. Source navigation uses saved content after the unsaved preview becomes null. V2 does not copy optional commentary claims into the client register, so omission cannot accidentally retain that copied claim; the server owns the union. V1's existing client preparation is retained.

## Changed files

| Files | Change |
| --- | --- |
| `caos/server/caos/deliverables/layouts.py` | Immutable six-layout and optional-section binding declarations; same chart identities as Analysis. |
| `caos/server/caos/deliverables/document.py` | V2 composition, exact narrative/table selection, validated origins, chart warnings, model effects, optional overlays and citation union; original v1 composers retained. |
| `caos/server/caos/deliverables/service.py` | Version dispatch, preview, recorded mapping/choices, union validation/sign/freeze evidence, required-input blockers. |
| `caos/server/caos/contracts.py` | Bounded optional-section request IDs only. |
| `caos/server/caos/responses.py`, `api/__init__.py` | Typed preview/blocker response and workspace plumbing. |
| `caos/frontend/src/components/report/ReportStudio.tsx` | Paper-first generated section navigation, source union, optional choices/overlays, explicit v2 revision action, complete replacement hydration and visible recovery/error state. |
| `DeliverableDocument.tsx`, `documentTypes.ts` | Paper ChartExhibit context, exact source links, inline commentary action and unsaved optional-overlay rendering/removal. |
| `reportRecovery.ts`, `reportStudioState.ts` | Persist/validate optional IDs; exact deduplicated source/block navigation refs. |
| `caos/frontend/app/globals.css` | Existing-token paper-first grid, responsive controls, correctly full-width generated section buttons. |
| Report component/type/state/recovery tests | Overlay lifecycle, optional IDs, source pairs and caller contracts. |
| `caos/tests/spec/test_deliverables_spec.py`, `test_http_contracts_spec.py` | V2 default/real acceptance, six layouts, source authority/offline evidence, mapping/legacy/optional/error regressions. Legacy fixtures now explicitly request v1. |
| `caos/tests/fixtures/deliverables/report_modules.json` | Clearly disposable canonical report table answer keys. |
| `qa/browser_fixture_provider.py`, `qa/serve_browser_integration.py` | Opt-in `--report-fixtures` canonical supplement; default fixture behavior unchanged. |
| `docs/ANALYST_VIEW_COVERAGE.md` | Exact section/module/table selectors, optional policy, shared chart IDs and missing-input behavior. |

## TDD and verification evidence

Initial RED: the evidence-only default-v2 test and v1 identity-dispatch test failed because the default was v1 and `_template_for` had no recorded-version parameter. After implementation both passed. Six-layout fixture expansion initially failed (`TABLE_HIDDEN`) because the disposable test fixture emitted invalid uppercase stable-table markers; the fixture was corrected to canonical table headings, not the validator weakened. All six layout tests then passed with concrete known values and origins.

Confidence RED/GREEN: missing recorded mapping reproduced `KeyError` instead of typed refusal. Deep Research fenced `### Implications` reproduced a false subsection selection. Added tests before fixes; the selector now reuses the canonical scanner and only recognizes one declared visible heading. Both pass. The wide-origin test initially used a long source ID rather than the document-origin block ID; corrected the fixture to the actual 130-character block-ID boundary, then verified visible unavailable narrative sections. A frontend caller-contract RED pinned independent v2 citation inputs before removing the unwanted client-side union copy.

| Command / check | Result |
| --- | --- |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_http_contracts_spec.py -q` | 217 passed, 1 warning, 216.44s (intermediate expanded run). |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'v2 or v1_identity'` | 20 passed, 95 deselected, 1 warning, 14.77s, owner verification after selected rewrite and mapping refusal. |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_module_presentation_spec.py -q` | 690 passed, 1 warning, 227.27s. |
| Same full backend trio after final unit/heading/upgrade regressions | **695 passed, 1 existing warning, 227.91s** on final production code. |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k v1_upgrade` | 1 passed, 115 deselected, 1.59s; additional explicit upgrade regression after the 690-test run. |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_module_presentation_spec.py -q -k 'v2 or v1_identity or v1_upgrade or unit or model'` | 223 passed, 366 deselected, 1 warning, 116.08s; final component-wise money-unit follow-up. |
| `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'six_layout or implications_are or model_money_units'` | 11 passed, 109 deselected, 0.45s; generated heading syntax and invalid-unit fallbacks. |
| `npm run lint`, `npx tsc --noEmit`, `npm run build` in `caos/frontend` | Passed on final frontend code; all 20 static pages built. |
| `npm run test:unit` in `caos/frontend` | 181 passed, zero failed; final run 468.40ms. |
| Four focused Report node suites, including `reportRecovery.test.ts` | 38 passed. |
| Scoped `ruff check` over modified Python/server/tests/QA files | Passed. |
| `git diff --check` | Passed. |

Warnings are existing Starlette TestClient/httpx deprecation and Node `MODULE_TYPELESS_PACKAGE_JSON` reparsing warnings. No new dependency/config change was made to silence them. One lint pass caught an event handler named `useSharedDraft`, which looked like a Hook; renamed it `acceptSharedDraft` and reran lint/typecheck/build successfully. Full Python and full frontend suites were not run concurrently.

## Six-layout fixtures and visual evidence

Every layout uses the exact ledger bindings, with known fixture facts rather than `Governed output pinned`: Full Credit recurring-service-contract driver and CP-1 exact financial/chart points; Earnings `FY2024 Q4 versus FY2023 Q4`; Covenant `Agreement section 7.1`; Relative Value `Unsecured spread compensates for subordination`; Distress `Unverified consent threshold`; Deep Research `Monitor retention before extending`. Generated sections are locked and origins reference the accepted fixture artifacts. Findings and Implications are distinct, not repeated narrative.

Visual artifacts live in `.superpowers/sdd/analyst-task7-visuals/` (ignored, retained locally):

- `full_credit-canonical-layout-fixture.png`
- `earnings_update-canonical-layout-fixture.png`
- `covenant_refinancing-canonical-layout-fixture.png`
- `relative_value-canonical-layout-fixture.png`
- `distressed_restructuring-canonical-layout-fixture.png`
- `deep_research-canonical-layout-fixture.png`
- Actual accepted-route paths: `relative-value-first-open.png`, `full-credit-accepted-preview-unacknowledged.png`.
- Mounted failure/recovery/overlay paths: `failed-optional-save-visible.png`, `initial-recovery-visible.png`, `optional-commentary.png`, plus `narrow-layout-fixture.png`.
- Machine-readable evidence and exact cases: `evidence.json`. Reproduction script: `.superpowers/sdd/analyst-task7-browser.mjs`; server-composed fixture payloads: `analyst-task7-visual-fixtures.json`.

The real accepted RV fixture has no CP-6, saves with zero narrative blocks, retains generated-only source links after `preview=null`, and proves collapsed optional-save refusal makes controls actionable. Reload exposes the initial browser recovery copy; restore retains `ic_context`, then explicit omission persists. Inline commentary adds/saves/removes separately. A real CAS conflict's “Use shared” adopts server optional IDs. Real accepted Full Credit first-open retains module facts without automatically acknowledging a model fallback. Six complete layout screenshots use server-composed canonical presentation fixtures; their selected-model/effect objects are explicitly synthetic, not a claim of live incremental model qualification.

The initial mounted run had zero scoped WCAG 2.1 AA axe violations, zero page errors and no document overflow at 680px. Visual inspection found inherited numbered-button grid columns crushing the new generated labels; full-width block buttons fixed this and a mounted geometry assertion was added. The final browser run status is recorded below before handoff.

Harness policy: production frontend build completed before startup; local port 19187 only, never user port 8000; new `/private/tmp/analyst-task7-integration-0907*` SQLite/vault fixtures; built-in single worker only; development scanner/provider explicitly labelled. Sandbox initially denied binding; approved scoped escalation permitted localhost testing. Harness was stopped and rebuilt/restarted after UI fixes. No real cases, credentials, paid providers or live qualification were involved.

## Legacy compatibility

V1 template fixtures are explicitly v1, separate from new default/real-accepted first-open assertions. Tests retain v1 read, save, restore and both freeze paths under recorded identity; original frozen payload digests and export metadata remain byte-identical after restore and subsequent freeze. The additional explicit v1→v2 test proves a new revision, retained old content/exports and stale old opinion until renewed sign-off. Existing filing/export, detached receipt, model-selection, source withdrawal, unsigned-opinion, cloned-tab and guarded-navigation checks remain in the broader suites. No historical stored renderer or template bytes are rewritten.

## Confidence review — Task 7 diff

Least confident about (ranked):

1. **Generated evidence only appearing visually.** Traced union through compose/save, `_citation_blocks`, actual sign route, freeze `_frozen_evidence`, publication and isolated offline verifier. Confirmed original paths needed explicit union propagation; patched all named callers. Exact repeated block IDs across distinct sources do not cross-pair. Generated-only withdrawal refuses actual sign route with 422 and freeze refuses too. **Verified.**
2. **Template/mapping reinterpretation.** Traced workspace, autosave, restore, both freeze lookups, request-changes and recovery. Fixed recorded dispatch; missing mapping RED now typed refusal. Explicit v1/new-v2 tests preserve old frozen payload/export identity. **Verified.**
3. **Replacement paths retaining old optional IDs or old template metadata.** Parent review identified Use shared/request-changes. They now adopt the full authoritative workspace, synchronize state and save/recovery refs, and pass the new template to recovery while preserving unsigned opinion text. Cross-template conflict overwrite is disabled until shared adoption. Real CAS browser proof and static caller tests cover the branch. A separate mounted Request changes race loaded an omitted choice, then advanced the real server head to included `ic_context`, requested changes from its frozen review, observed the included choice adopted, and immediately omitted it into the next successful autosave. **Verified, including mounted replacement and next save.**
4. **Preview conflating model failure with accepted-source authority.** Parent review identified the shared catch. Accepted route/source validation now precedes a separate model-only boundary; tests preserve module facts for stale model and expose no sections on accepted-authority failure. Save/sign/freeze are not weakened. **Verified.**
5. **Narrative duplication, fenced headings and unrepresentable origins.** Findings/Implications originally selected the same H2. Exact scanner-aware distinct H3 extraction fixes it; ambiguous/missing H3 is unavailable. Validated projection origins preserve the 120-character document limit and deduplicate block IDs. Final image inspection showed literal `### Findings` in generated prose; a RED regression now passes after stripping only visible canonical heading decoration while preserving the heading words. Analyst plain text and fenced examples are not rewritten. **Verified with adversarial tests and refreshed fixture capture.**
6. **Silently absent or falsely present money charts.** Parent review found empty model unit plus discarded warnings, then a final concrete probe found `USD unknown` slipping through because concatenation preceded component validation. Four regression cases (unknown/null currency, unknown/N/A unit) failed as predicted. The final code calls the existing shared `presentation._unit` on separate period fields before joining, catches only `PresentationError`, and leaves shared `UNIT_MISMATCH` warnings/exact tables with ratio charts still available. No normalization or inferred values. **Fixed with final focused verification; Task 9 rendering limitation remains explicit.**
7. **Hidden autosave/recovery/freeze feedback and broken layout.** Mounted refusal/reload tests confirm actionable states open controls; ordinary save state stays visible. Screenshot inspection caught and fixed crushed navigation labels. Scoped axe and narrow overflow checks passed. **Verified.**
8. **Optional commentary omission retaining copied citations.** V2 now submits separately authored block citations; union remains server-owned. This prevents a copied commentary claim persisting in the client register after omission, while keeping v1 preparation unchanged. **Fixed with caller-contract regression.**
9. **Async authority regression.** Existing lifecycle generation/in-flight gate, serialized autosave, receipt AbortController and case/deliverable checks, Workspace authority state, tab-claim locks and unsigned-opinion navigation/freeze guards remain in place. Full frontend tests and mounted recovery/CAS checks pass. No new authority state machine. **Verified within Task 7 checks, not a claim of every cross-browser timing interleaving.**
10. **Synthetic fixtures mistaken for analytical coverage.** Real accepted RV/FC exercise actual engine/store/API paths but use disposable canonical answer keys. Other layout/model-effect fixtures prove composition, not live analytical qualification. No required binding was made optional to pass a fixture. **By design; Task 10 qualification follow-up.**

Fixed: citation propagation, recorded dispatch and typed missing mapping, replacement optional/template synchronization, preview boundary, distinct narrative extraction/origins, model chart warnings, hidden controls, generated-nav geometry, and optional citation-copy residue.

Verified fine: strict client chart contract remains unchanged; no browser point recipes enter generated authority. Frozen payloads and exports retain identity. Existing source/model/opinion and independent filing restrictions remain enforced.

By design / still open: Task 8 owns actual accepted incremental model resolution; Earnings/Covenant reports visibly block publication when required effects are absent. Task 9 owns real chart graphics in PDF/XLSX; exact tables/recipes persist. Task 10 must qualify complete six-pathway analytical fixture/live journeys. These are not hidden or presented as Task 7 accomplishments.

## Mandatory skills and rewrite tournament

Used project Impeccable with product register, existing dark workspace/light paper tokens and semantic controls. Context setup ran once; no theme or dependency was added. It drove paper-first hierarchy, native optional checkboxes/details, source links, responsive grid and screenshot/a11y verification. Ponytail full drove reuse of Task 5 projection, Task 6 ChartExhibit, canonical Markdown scanner, existing validators, native browser recovery locks and existing request/state machinery. No invented synthesis or workflow layer.

Confidence-review was read fully and executed over the actual diff/callers; ranked doubts and concrete tests are above. No-argument post-edit rewrite-tournament was read fully and run on the two most material symbols: `DeliverableService.save_draft` and `citation_union`. The cap deliberately skipped `_module_document`, `_report_narrative`, `workspace` and frontend event/render helpers; they received direct confidence/testing/visual review rather than widening the tournament.

No GitNexus index existed for this repository; scoped `rg` references built the impact set: save API PUT → autosave/restore/explicit upgrade → SQLite CAS append; citation union → preview/save document → Evidence Register → sign/freeze → payload evidence/publication/offline audit. Invariants: signatures and validation order, no source/model authority relaxation, v1 exact fields, stored v2 mapping, `None` versus `[]`, deterministic exact source/block pairs and chart source narrowing.

Fresh own roles ran sequentially: `rewrite_incumbent`, `rewrite_speed`, `rewrite_memory`, `rewrite_readability`, `rewrite_arbiter`. They did not alter production or reuse the root's reviewer. Artifacts: `analyst-task7-{speed,memory,readability}-candidate.md`, `analyst-task7-anonymous-bracket.md`, `analyst-task7-arbiter.md` and source backups `analyst-task7-backup-{service,document}.py.txt`. Memory's isolated 500-case/three-exception equivalence and synthetic traced allocation reduction were challenger evidence only, not a production performance claim.

**Winner: Snippet C (readability), both functions.** Bracket: A (speed) beat B (memory); C beat A; C beat D (incumbent).

- Explicit local validation/mapping branches expose trust boundaries without adding abstractions.
- Same asymptotic work and deterministic grouping; micro-allocation claims did not justify extra representation/logic.
- Same callers, signatures, side effects and evaluation order; no v1 content or exact citation semantics change.

Owner backed up both source files, applied the full C pair, inspected the diff and ran focused real tests. The initial owner pass exposed a test-fixture assertion error about long source IDs versus long block IDs, not candidate behavior; corrected it to the actual contract boundary. The separately tested missing-mapping typed refusal was then added. Owner final verification: 20 targeted passes and the 690-test backend run, plus explicit v1-upgrade pass, compiler/frontend suite and concrete repeated-source/block invariant. Final exact code is included below.

## Final handoff

Final browser script completed successfully: actual RV accepted/generated-only save, optional refusal/recovery, real shared CAS replacement, analyst commentary lifecycle, opinion/sign and single-worker freeze, then distinct operator bootstrap and independent approver filing plus stored MD/PDF/XLSX downloads. Actual FC preview remains unacknowledged; all six server-composed fixture layouts captured. Scoped axe violations: 0; page errors: 0; 680px document overflow: false. Final visual inspection confirms the navigation correction and readable paper-first/narrow layouts.

An expanded fixture pass initially expected PUT 200 instead of the documented 201; fixed only the test. Independent filing setup correctly refused ordinary analyst membership provisioning and refused bootstrap by the opinion signer (`BOOTSTRAP_NOT_INDEPENDENT`). The successful final harness uses distinct `analyst.qa@local.invalid`, `task7-operator`, and `task7-approver` actors with existing routes/gates; no production check was changed. The six-pathway presentation fixture title retains its disposable case identity even when the selected layout changes.

Final component-unit guard follow-up reran confidence review against `_unit` and `project_model_outputs`, retained the bounded tournament's unchanged `save_draft`/`citation_union` winners, and kept `_module_document` outside that two-symbol cap. The four-line unit-guard reuse added no custom validator or schema. Final unit-focused counts and shutdown/commit details are appended below. Independent reviewer follows implementation before Task 8.

Mounted Request changes follow-up: `node .superpowers/sdd/analyst-task7-request-changes.mjs` passed on disposable case `case-bd6d4bf6ffd54ad78224`, ending at Draft v11. Evidence: `analyst-task7-visuals/request-changes-evidence.json` and `request-changes-optional-replacement.png`. An initial test locator used “Frozen” while the existing UI label is uppercase “FROZEN”; only the locator was corrected. No application behavior changed for the test. The final harness and its owned worker stopped cleanly with exit 0; no fixture service remains running. Disposable databases/screenshots remain locally for review, not product data.

The project commit skill was read fully and used for explicit-file staging on the existing `codex/` branch, with no push. Only Task 7 files and this named report are staged; ignored scratch/candidate/browser artifacts remain untracked. No unrelated user WIP was present or removed.

Final pre-commit confidence closure: all named confirmed bugs have focused regressions or mounted evidence, all selected rewrite callers pass the final 695-test backend run, and the final report UI passes 181 frontend unit tests, lint/typecheck/build and browser checks. `ruff`, working/staged diff checks are clean. This report is included in the scoped implementation checkpoint; the exact commit SHA is returned in the handoff. Git index access required a scoped sandbox escalation because linked-worktree metadata is outside its default write boundary.

## Verified tournament final code

`caos/server/caos/deliverables/service.py:212-283`

```python
    def save_draft(self, case_id: str, pathway: str, request: DeliverableDraftRequest, *, actor: str) -> dict[str, Any]:
        template = self._template_for(pathway, request.template_version)
        if request.template_id != template["template_id"] or request.template_version != template["template_version"]:
            raise ValueError("DELIVERABLE_TEMPLATE_STALE: the draft binds a different template identity")
        blocks = [block.model_dump(mode="json") for block in request.blocks]
        self._validate_layout(template, blocks)
        self._validate_citations(case_id, blocks)
        self._validate_judgment_facts(blocks)
        selection = request.model_selection
        model = self._resolve_selection(case_id, selection)
        self._validate_pathway_authority(case_id, pathway, model)
        identity = self._model_identity(model, selection) if model else None
        needs_model = [block for block in blocks if block["kind"] in MODEL_DEPENDENT_KINDS]
        if identity is None and (template["model_requirement"] == "REQUIRED" or needs_model):
            raise ValueError(
                "MODEL_REQUIRED: this deliverable template or its model-dependent blocks "
                "need a selected model"
            )
        stored = [self._enrich_block(case_id, block, model, identity, selection) for block in blocks]
        artifacts = self._accepted_artifacts(case_id)
        head = self.records.head_revision(case_id, pathway)
        previous = (head or {}).get("content") or {}
        v2 = template["template_version"] == TEMPLATE_V2
        optional_ids = request.included_optional_section_ids
        if optional_ids is not None and (
            not v2
            or len(optional_ids) != len(set(optional_ids))
            or set(optional_ids) - {s["section_id"] for s in OPTIONAL_SECTIONS_V2}
        ):
            raise ValueError("DELIVERABLE_OPTIONAL_SECTION_INVALID: only declared v2 section IDs are accepted")
        if v2 and optional_ids is None:
            optional_ids = previous.get("included_optional_section_ids", [])
        mapping_version = None
        if v2:
            if previous.get("template_version") == TEMPLATE_V2 and not previous.get("mapping_version"):
                raise ValueError("MAPPING_VERSION_UNSUPPORTED: the recorded v2 mapping identity is missing")
            mapping_version = (
                previous["mapping_version"]
                if previous.get("template_version") == TEMPLATE_V2
                else CURRENT_MAPPING_VERSION
            )
        document_sections = compose_document(
            pathway=pathway,
            template=template,
            blocks=stored,
            artifacts=artifacts,
            model=model,
            mapping_version=mapping_version,
            included_optional_section_ids=optional_ids,
        )
        content = {
            "template_id": template["template_id"],
            "template_version": template["template_version"],
            "document_schema_version": DOCUMENT_SCHEMA_VERSION,
            "document_sections": document_sections,
            "model_selection": selection.model_dump(mode="json") if selection else None,
            "model_identity": identity,
            "blocks": stored,
            "generated_blocks": self._generated_blocks(stored, model),
        }
        if v2:
            citations = citation_union(stored, document_sections, artifacts)
            self._validate_citations(case_id, [{"citations": citations}])
            content.update(
                mapping_version=mapping_version,
                included_optional_section_ids=optional_ids,
                citation_union=citations,
                publication_blockers=document_blockers(document_sections),
            )
        return self.records.append_revision(
            case_id, pathway, request.expected_version, content, digest(content), actor, self.store._audit,
        )

```

`caos/server/caos/deliverables/document.py:520-557`

```python
def citation_union(blocks, sections, artifacts):
    """One union, retaining exact source/block pairs from validated envelopes.

    Bare origin block IDs are never paired across sources. A chart may narrow
    the artifact refs only by its declared sources and the origin block IDs.
    """
    citations = [citation for block in blocks for citation in block.get("citations", [])]
    by_id = {artifact.get("id"): artifact for artifact in artifacts.values()}
    for section in sections:
        origin = section["origin"]
        artifact = by_id.get(origin["authority_id"])
        if origin["kind"] != "ARTIFACT" or artifact is None:
            continue
        chart_sources = None
        if section["kind"] == "chart":
            chart_sources = {
                source
                for point in section["recipe"].get("points", [])
                for source in point["source_ids"]
            }
        for ref in (artifact.get("payload") or {}).get("evidence_refs", []):
            if ref["block_id"] not in origin["block_ids"]:
                continue
            if chart_sources is not None and ref["source_id"] not in chart_sources:
                continue
            citations.append({
                "source_id": ref["source_id"],
                "block_ids": [ref["block_id"]],
                "claim": "Accepted module evidence",
            })
    grouped = {}
    for citation in citations:
        key = citation["source_id"], citation["claim"]
        grouped.setdefault(key, set()).update(citation["block_ids"])
    return [
        {"source_id": source, "block_ids": sorted(ids), "claim": claim}
        for (source, claim), ids in sorted(grouped.items())
    ]

```
