# Task 7 I1 fix report

## Scope and baseline

- Base: `c7a9015f5133dbaa61a4143f2ccb1dcc2828d385` (`c7a9015`), clean implementation worktree on `codex/analyst-workbench-capabilities`.
- Read the complete independent findings and global constraints. I1 alone changes production behavior: supported cross-module evidence can exceed a single document origin's 500 IDs. The controller additionally authorized explicit v1 selection in two legacy publication test files after baseline reproduction (below). No Task 8/9 implementation, UI change, methodology change, live/paid provider call, dependency change, limit widening or truncation.
- Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex`. Every shell command used this exact worktree. One attempted suite launch had an invalid relative workdir and did not execute; corrected immediately.

## Changed files and interface

- `caos/server/caos/deliverables/document.py`: adds private `_report_evidence_sections(citations, authority_id)` and changes the v2 `_module_document` register call from append to extend. Reuses `_evidence_section`, `citation_union`, and Python 3.12+ standard-library `itertools.batched`.
- `caos/tests/spec/test_deliverables_spec.py`: one 600-ref integration regression, 18 parameterized boundary/pair cases and one preexisting bounded-shape compatibility case.
- `caos/tests/spec/test_publication_spec.py`: negative and positive historical narrative-judgment fixtures now explicitly select v1; assertions unchanged. Positive cases also need the pin, otherwise no narrative would actually be tested under evidence-only v2.
- `caos/tests/spec/test_publication_goldens_spec.py`: historical `_build` fixture explicitly selects v1; every assertion and golden file remains unchanged. New v2 chart goldens remain Task 9.
- This report. Ignored scratch backup: `.superpowers/sdd/analyst-workbench-task-7-fix-document-backup.py`; never staged.

The helper first returns the original register unchanged when both its distinct origin IDs and table rows fit 500. Overflow is split into batches of at most 500 reference occurrences, then regrouped by the existing exact source/claim union helper. Consequently each section has at most 500 rows and 500 distinct origin IDs. IDs are deterministic: `evidence_register`, `evidence_register.2`, etc.; all remain on the Evidence page, with a continued heading after the first.

There is no report document-list section-count ceiling in `compose_document` or `ReportPreviewResponse`; the 500-section module-presentation response bound is a different interface, not modified here. Register section count is one for a bounded register, otherwise `ceil(reference occurrences / 500)`, under the existing input ceilings. The 600-reference fixture produces two sections (500, 100), and the 2,000-reference fixture produces four. No arbitrary section-count truncation was introduced.

## TDD and checks

All commands below run from the implementation worktree, using the existing pytest framework and `.venv314` runtime.

- RED: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k large_generated_evidence` → **1 failed, 120 deselected in 0.37s**. Before the production patch, workspace returned an empty citation union rather than the expected 600 IDs, reproducing the swallowed composition failure.
- Initial GREEN: same command → **1 passed, 120 deselected in 22.83s**, including actual render/freeze and offline verification.
- Boundary GREEN: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k evidence_register_bounds` → **19 passed, 121 deselected in 0.33s**.
- Broader backend check: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_module_presentation_spec.py -q` → **715 passed, 1 warning in 249.64s**. This process loaded the helper before the final readability-only rewrite and before the missing-tail refusal assertions; final owner coverage below checks those last changes. Includes the separate existing actual-accepted FC/RV first-open tests, without presenting the seeded 600-ref fixture as actual accepted-run qualification.
- Final owner verification after selected rewrite, missing-tail assertions and explicit legacy fixture pins: `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_publication_goldens_spec.py -q -k 'v2 or v1_identity or v1_upgrade or citation or publication'` → **87 passed, 94 deselected, 1 warning in 110.82s**. All original publication/golden assertions passed without regenerating any golden.
- Warning on both backend runs: existing `StarletteDeprecationWarning` from `fastapi/testclient.py:1`, “Using httpx with starlette.testclient is deprecated; install httpx2 instead.” No dependency change was made. Node/frontend checks were not run for this backend-only fix.
- `git diff --check`: clean (rerun before commit).

The integration uses **seeded service authority and an accepted-artifact retrieval seam**, not an actual accepted live run. CP-1, CP-2 and CP-1A each pass `CanonicalModuleOutput` validation with 200 disjoint references; fixtures use the existing disposable report answer keys. The source is actually ingested with all 600 blocks. Source checks, selected-model request validation, saved citation union, opinion Sign-Off, freeze re-composition, worker rendering, frozen evidence and package verifier are real. The test asserts exact union in preview/save and exact frozen evidence, plus unchanged saved/frozen document sections. A missing final block (`b00600`, outside the first register) must refuse both sign and freeze; withdrawing the source also refuses both. This is composition/authority regression coverage, **not analytical qualification**.

### Legacy publication-fixture follow-up discovered by owner verification

First selected-rewrite run:

`caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_publication_goldens_spec.py -q -k 'v2 or v1_identity or v1_upgrade or citation or publication'`

Result: **12 failed, 75 passed, 94 deselected, 1 warning in 57.53s**. Every I1 regression, including missing-tail and withdrawal refusal, passed. Five legacy uncited-judgment parameter cases created no narrative under the evidence-only v2 default and therefore did not raise. Seven historical publication-golden cases reached the correct `REPORT_INPUT_UNAVAILABLE` gate because their seeded legacy fixtures contain no required v2 module tables.

Baseline proof ran the sole changed production module from `c7a9015` in memory, without resetting or editing any working-tree file; all other production files remained at that base. The two failing test files were also unchanged at this point. Exact command:

```sh
caos/server/.venv314/bin/python -c 'import subprocess, sys; sys.path.insert(0, "caos/server"); import caos.deliverables.document as document; baseline = subprocess.check_output(["git", "show", "c7a9015:caos/server/caos/deliverables/document.py"], text=True); exec(compile(baseline, "c7a9015/document.py", "exec"), document.__dict__); import pytest; raise SystemExit(pytest.main(["caos/tests/spec/test_publication_spec.py", "caos/tests/spec/test_publication_goldens_spec.py", "-q", "--tb=short", "-k", "analyst_judgment_cannot_carry or every_format_carries or held_and_filed_bytes"]))'
```

Result: **the same 12 failed, 29 deselected in 1.13s**. The controller authorized the narrowly scoped test-only compatibility repair. Three template-selection expressions now request `caos.deliverable-template.v1`: the negative/positive narrative tests and golden builder. No golden regeneration, assertion removal, default-v2 production change or readiness weakening. The separate genuine v2 default/first-open and 600-ref tests remain v2. Final complete 87-test rerun is recorded above.

## Confidence review — I1 diff

Least confident about (ranked):

1. **Display chunking could truncate the authority union.** Investigated `workspace` and `save_draft` recomputing `citation_union` from original artifacts and section origins; `sign_opinion` and `freeze` use `_citation_blocks(content)`; `_frozen_evidence` reads the complete stored union; publication inventory reads `payload.evidence`. Verdict: verified fine by exact 600-ID saved/frozen assertions, offline verifier, missing-tail and withdrawal refusal probes. These authority functions are unchanged.
2. **One citation can exceed 500 IDs; many sources sharing an ID can exceed 500 rows.** The confirmed original bug affected the first case, and simply batching citation rows would miss it. The chosen reference-level batches bound both dimensions. Verdict: fixed at the v2 composition seam, verified at 0/499/500/501/600/2000 across one source, distinct sources, and shared block IDs. Every section validates against the unchanged `DocumentTableSection` contract.
3. **Valid historical v2 sections could change despite fitting the contract.** Counting raw reference occurrences alone would split previously valid reports when 500 IDs repeat across source/claim rows. The unchanged-register fast path checks the actual origin and row counts. Verdict: verified fine by exact helper equality for bounded inputs, including 1,000 occurrences in two rows sharing 500 IDs. V1 calls still invoke the untouched legacy helper and dispatcher.
4. **Regrouping could cross-pair sources or drop claims.** Existing `citation_union` groups by `(source_id, claim)` and each atom retains its original block. No synthetic cross product. Verdict: exact source/block/claim-set tests pass, including distinct sources sharing a block ID; existing chart-source narrowing regression remains included. Input deep-copy comparison and repeated calls verify nonmutation/determinism.
5. **Continuation IDs/page grouping could collide or fail freeze recompilation.** Helper generates unique fixed IDs; `compose_document` validates uniqueness; publishing `_pages` groups all same-page sections without discarding continuations. Verdict: boundary unique-ID assertions and 600-ref save/freeze exact-section comparison verify the shared path. No UI code or recovery/navigation state changed.
6. **Resource growth, unsupported Python API or schema broadening.** `batched` is native on the declared Python >=3.12 runtime; only the overflow path creates a lazy reference generator and bounded 500-entry batches. Existing inputs bound output growth; no new document limits. Verdict: verified fine by pyproject, contract and caller inspection plus 2,000-reference checks. Initial raw-register allocation is retained to preserve bounded output exactly; no performance claims.
7. **Passing or failing legacy tests could be testing an empty v2 fixture instead of historical semantics.** The expanded publication run confirmed the default-selection fixture bug, independently reproduced using the base composer. Controller-authorized test-only pins restore actual narrative inputs and the recorded golden identity. Original assertions and golden bytes stay intact. This confidence follow-up is test-only and therefore rewrite-tournament-exempt; final publication/golden results below decide verification, not the fixture explanation alone.

Fixed: I1 production boundary and the additionally authorized legacy publication fixture identity pins. Verified fine: authority union, exact pairs, both limits, deterministic section count/identity, prior bounded representation, v1 dispatch, nonmutation, source refusal paths and historical publication goldens as above. By design: this changes presentation only; the complete authority inventory remains separate. Still open: the preexisting Task 8 incremental model resolver, Task 9 actual PDF/XLSX chart drawing, and Task 10 whole-branch/live analytical qualification are unchanged.

## Mandatory skills and bounded rewrite tournament

Read `confidence-review`, `rewrite-tournament`, `ponytail` and project `commit` instructions completely. Applied Ponytail full: one v2-only helper using existing union/rendering helpers and native batching, no new dependencies/framework/limit changes. Project Impeccable does not trigger for this backend-only fix; no UI files or visual states were changed and no browser/build rerun is claimed.

No-argument post-edit discovery used `git diff --stat`. Only material symbol selected: `_report_evidence_sections`, `document.py:561–581`; `_module_document` has a one-line mechanical call-site replacement and is covered by the selected symbol's callers. No unrelated branch functions were tournamented. GitNexus has no indexed CAOS repository per constraints, so scoped `rg` references supplied the impact set: v2 `_module_document` → `compose_document` → service preview/save/freeze re-composition → publication and existing render consumers. V1's six legacy helpers and dispatch remain untouched.

Fresh own roles ran sequentially: `fix_i1_incumbent`, `fix_i1_speed`, `fix_i1_memory`, `fix_i1_readability`, `fix_i1_arbiter`. No root/reviewer agents reused. All received the real code, impact set and invariant list; challengers were read-only. Incumbent defended exact bounded bytes and shared helper reuse. Speed candidate replaced wrapper dictionaries with tuples and duplicated sorted grouping; memory candidate added `del register`; readability candidate named the single-reference and regrouping stages. The blind arbiter received complete anonymous function bodies.

Bracket:

- A (speed) vs B (memory): **B** — reuse existing grouping; retain exact batches/IDs; less maintenance than duplicate normalization despite explicit deletion noise.
- B vs C (readability): **C** — explicit intermediate data shapes; no deletion noise; same batching, limits and metadata.
- C vs D (incumbent): **C** — names expose batching units; separate normalization/rendering calls; extra local adds no abstraction or semantic change.

**Winner: Snippet C (readability), replacing `document.py:561–578` incumbent with lines 561–581.**

Justification:

- Names distinguish individual references from regrouped citations.
- Preserves native bounded batching and authoritative helper reuse.
- Keeps exact fast-path and overflow behavior with no signature or side-effect change.

Final code:

```python
def _report_evidence_sections(citations, authority_id):
    """Bound v2 display sections, never the authoritative citation union."""
    register = _evidence_section([{"citations": citations}], authority_id)
    if len(register["origin"]["block_ids"]) <= 500 and len(register["rows"]) <= 500:
        return [register]

    # One reference per entry bounds both distinct origin IDs and table rows.
    single_reference_blocks = (
        {"citations": [{**citation, "block_ids": [block_id]}]}
        for citation in citations
        for block_id in citation["block_ids"]
    )
    sections = []
    for section_number, batch in enumerate(batched(single_reference_blocks, 500), 1):
        batch_citations = citation_union(batch, [], {})
        section = _evidence_section([{"citations": batch_citations}], authority_id)
        if section_number > 1:
            section["section_id"] = f"evidence_register.{section_number}"
            section["title"] = "Evidence Register · continued"
        sections.append(section)
    return sections
```

Owner verification: backed up the full target to the ignored analyst-prefixed scratch file before applying the winner. Final focused command above passed all 87 tests, including the 600-ref exact union/freeze/offline and missing-tail refusal case, all boundary matrices, both actual-accepted first-open paths, v1 history, publication and original goldens. Owner inspected actual production/test diff and traced every listed caller; `git diff --check` is clean and `git diff --name-only -- caos/tests/fixtures` is empty. The selected candidate's signature/return shape and all caller contracts remain unchanged. No candidate was accepted solely on the arbiter's judgment.

## Handoff

Checks complete; scoped local checkpoint contains only the four code/test paths listed above plus this report. No unrelated WIP was present or staged, and the scratch backup remains ignored. Exact commit SHA is supplied in the handoff message. No push/merge/deploy; independent review follows. Existing warning noise is recorded with final outputs, not hidden. No browser harness or duplicate worker was started for this backend-only correction.
