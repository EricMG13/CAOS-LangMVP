# Task 2 report — user-upload-only methodology

Base: `1993172`

Branch: `codex/enterprise-readiness`

## Preserved failing baseline

Added `caos/tests/test_user_upload_only.py` before changing methodology, then ran:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_user_upload_only.py -q`

- Exit 1: 33 forbidden acquisition references across exactly the four brief-owned CP-4 files.
- The failures included the named provider, retrieval-map references, public retrieval hosts/endpoints, `EDGAR_USER_AGENT`, `/api/edgar`, nonexistent server/MCP modules, and instructions to search, pull, fetch, or vault filing exhibits.

## Implementation

- Deleted the complete external filing acquisition map from `CP-4_RUNBOOK.md` and `REF_CP-4_STEPS.md`.
- Removed every acquisition-map companion reference from `SKILL.md` and both acquisition-lane gate instructions from the consolidated CP-4/CP-4B steps.
- Replaced only the affected gates: supplied executed governing documents remain authoritative; absence produces a typed evidence gap and `Blocked`; summaries/snippets cannot pass.
- Preserved the six-rank supplied-document authority hierarchy, every provision-level legal rule, scoring rule, downstream register, and stop/fail-closed semantic unrelated to acquisition.
- Proved the original `build/build_package.py` is absent from the checkout and all git history; the distributed README also says the builder is not shipped.
- Added the minimal stdlib `caos/scripts/regenerate_deploy_v_integrity.py`. It preserves the shipped sorted-JSON format, exact byte/SHA inventories, compact canonical baseline/build digests, rejects symlinks and membership drift, synchronizes the retrieval index and both memory prompts, is idempotent, and has a non-mutating `--check` mode.
- Regenerated `DEPLOY_V_MANIFEST.json`, `DEPLOY_V_BASELINE.json`, `DEPLOY_V_INTEGRITY_v1.json`, `CP_DEPLOY_V_RETRIEVAL_INDEX_v1.json`, and both memory prompts.
- New build ID: `cc8decc567c55037db1b54573f836ea3e0326e2cdd1337ca657d8b49af910aa9`.
- Updated the independent release pin without weakening it: 319 files, digest `0df950e68e0e8caaa5d825ed382c6090c1bc8e8e4bd673a6effd147777461d67`.
- Corrected the execution plan to name the replacement generator instead of a nonexistent existing command.
- Added the single narrow quality-ledger file mapping required when the new command became tracked: existing features `F-RUN-11` and `F-RUN-15`; no new feature or exclusion was added.

## Acceptance results

All commands ran from the isolated Task 2 worktree.

1. `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_bundle.py caos/tests/spec/test_modules_spec.py -q`
   - Exit 0: `25 passed in 0.77s`.
2. `/private/tmp/caos-enterprise-baseline-20260901/bin/python caos/scripts/regenerate_deploy_v_integrity.py --check`
   - Exit 0: `Deploy V integrity is current`.
3. `/usr/bin/env python3 "Modular OS/tools/check_module_consistency.py"`
   - Exit 0: `26 modules checked, 0 with drift.`
4. `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor`
   - Exit 0: `All checks passed!`
5. `/usr/bin/env python3 docs/quality_ledger_coverage.py`
   - Exit 0: 45 routes, 230 product files, 120 features; every route and product file documented.
6. `git diff --check`
   - Exit 0.
7. Tracked-source prohibition test after adding all Task 2 files.
   - Exit 0; zero forbidden product/runtime/methodology/test-fixture references.
8. Adversarial regeneration check in a temporary copied bundle.
   - `--check` returned 1 after byte drift and left every identity file unchanged; normal regeneration repaired the copy; a second `--check` passed; an extra symlinked skill directory was rejected.

## Rewrite tournament

**Winner:** Readability challenger, replacing `caos/scripts/regenerate_deploy_v_integrity.py` lines 22–144.

**Justification:**

- Computes one immutable generated snapshot instead of scanning twice across a time-of-check/time-of-write gap.
- Rejects duplicate, missing, or extra skill membership across disk, manifest, and integrity metadata.
- Centralizes the established “canonical JSON excluding the identity field” rule without changing output bytes.

**Final code:** `caos/scripts/regenerate_deploy_v_integrity.py`.

**Verification:** the exact Task 2 pytest command passed 25/25; `--check` passed; the only caller remains `caos/tests/test_bundle.py`; all bundle consumers continue to receive the same schema and synchronized identity fields.

## Confidence review — Task 2 diff

Least confident about (ranked):

1. The replacement generator might use a different canonicalization than the omitted original.
   - Investigated: reproduced the pre-change `baseline_digest` and integrity `build_id` exactly from the checked-in JSON using compact, sorted JSON with only the identity field omitted; reproduced the existing pretty-printed files byte-for-byte with sorted two-space JSON plus newline.
   - Verdict: fine; regenerated bundle verification, identity agreement, independent byte pin, and idempotent `--check` all pass.
2. A bundle path might escape or be silently omitted.
   - Investigated: adversarially added a symlinked extra skill directory and reviewed manifest/integrity membership handling.
   - Verdict: confirmed risk in the first draft; fixed at the root by rejecting symlinks and requiring disk, manifest, and integrity membership to match exactly.
3. `--check` might mutate files or normal mode might use a different snapshot.
   - Investigated: drifted a temporary bundle, hashed every identity file before/after `--check`, regenerated, and checked again.
   - Verdict: confirmed double-scan risk in the first draft; fixed by generating once. `--check` left all identity bytes unchanged and normal mode was idempotent.
4. The prohibition test might be narrowly tailored to the current strings.
   - Investigated: expanded it across tracked CAOS text/code suffixes with provider, host, endpoint, environment, nonexistent-module, named-map, and bidirectional acquisition-instruction patterns; no broad vendored-methodology exclusion exists.
   - Verdict: fine; the red baseline named all four files and the final tracked-source run is green.
5. Removing the acquisition section might weaken unrelated CP-4 authority or legal gates.
   - Investigated: reviewed the actual diff and retained hierarchy, provision-analysis steps, registers, scoring, blocked semantics, and supplied executed-document primacy.
   - Verdict: fine; only acquisition content and its direct references changed.
6. Updating the release pin could accidentally weaken independent verification.
   - Investigated: count remains exactly 319 and the test still hashes every shipped byte independently of self-authored metadata.
   - Verdict: fine; the strict new digest passes.
7. Mapping the new command could conceal it through a broad tooling exclusion.
   - Investigated: staged-file discovery failed first, then the acceptance correction mapped only the exact script path to existing methodology-integrity features `F-RUN-11` and `F-RUN-15`.
   - Verdict: fine; no exclusion, wildcard script mapping, or feature row was added.

Fixed: ignored/mismatched skill membership and the double-generation race in the initial regeneration script.

Verified fine: canonicalization, check-only behavior, idempotency, symlink rejection, prohibition coverage, legal-gate preservation, bundle verification, independent pin, and narrow ledger coverage.

By design: the offline regeneration command writes six identity files sequentially; `--check` detects an interrupted partial run. Add staged directory replacement only if concurrent release builders/readers are introduced.

Still open: none for Task 2.

## Reviewer P1 corrections

The first review identified two real coverage gaps:

1. The prohibition gate used a text-suffix allowlist and line-by-line matching, so tracked extensionless text, multiline instructions, and several common acquisition phrasings could evade it.
2. The standalone integrity checker did not reject every undeclared tree shape: a direct file under `skills`, undeclared root entries, nested symlinks, and a symlink at the bundle root required explicit validation.

Corrections:

- Enumerate every tracked path below `caos` with NUL-delimited `git ls-files`; read bytes; skip only NUL-containing or non-UTF-8 files; and scan each complete decoded file.
- Match real `sec.gov` hosts with hostname boundaries, without rejecting lookalikes such as `notsec.gov.example.com`.
- Add sentence-bounded, order-independent acquisition detection for SEC/EDGAR filing objects and bounded public/external filing acquisition, including passive download wording.
- Pin the reviewer's four exact false-negative cases, two tournament challenge cases, and the lookalike-host negative case in a self-scannable detector test.
- Validate an exact managed bundle-root membership, reject the bundle itself when it is a symlink, reject every symlink below it, and require every direct `skills` entry to be a directory whose slug agrees with manifest and integrity membership.
- Add deterministic temporary-copy regressions for a direct undeclared skills file, an extra root file, an extra root symlink, a nested symlink, and a symlinked bundle root.

### Follow-up rewrite tournament

**Winner:** challenger, narrowly.

The challenger demonstrated four concrete gaps: a symlinked bundle root passed, newline-containing tracked filenames were not safely enumerated, the first hostname pattern overmatched a lookalike domain, and acquisition wording could evade verb-first rules. Those corrections were adopted. The challenger did not replace canonical digest formulas or generated identity semantics.

### Follow-up acceptance

1. Focused adversarial suite: `3 passed in 39.98s`.
2. Exact bundle/spec suite: `26 passed in 1.85s`.
3. Standalone integrity check: `Deploy V integrity is current`.
4. Module consistency: `26 modules checked, 0 with drift.`
5. Ruff over server/tests excluding vendored methodology: `All checks passed!`
6. Quality-ledger coverage: 45 routes, 230 product files, 120 features; all documented.
7. `git diff --check`: exit 0.
8. Generated bundle identity files: no byte changes in the P1 correction.

### Follow-up confidence review

Least-confident areas were the regex boundary, ordering/newline behavior, tracked-file enumeration, tree validation order, and accidental identity drift. The focused positive and negative cases verified the detector boundary and order independence; NUL-delimited enumeration and full-text decoding were reviewed directly; temporary repositories exercised every rejected tree shape from pristine passing copies; and both standalone `--check` and an empty generated-identity diff confirmed that canonical identities did not change.

Residual maintenance constraint: `ROOT_ENTRIES` is deliberately closed. Any intentional new bundle-root file must be added to that set and covered by the normal regeneration review.

## Remaining re-review blocker and CP-1C authority correction

The next re-review proved that the generic detector was not fully order-independent and that the deployed CP-1C authority contradicted the runtime's existing `supplied_only` pin. Shared canon granted a CP-1C public-research exception, and CP-1C instructions still directed automatic peer discovery, external-source queries, scraping provenance, and provisional externally sourced tiers.

Detector corrections:

- Give acquisition verb, generic public/external location, and filing/exhibit object their own independent sentence-bounded lookaheads.
- Correct the verb family to match `browse`, `browses`, `browsed`, and `browsing`.
- Pin `Search filings from external sources.`, `Filings from external sources should be downloaded.`, and `Browsing SEC exhibits is required.` through source-safe composition.
- Preserve the negative `public-private` peer-profile case, which the stronger generic matcher initially exposed as a false positive.
- Add a direct all-files assertion over the deployed CP-1C slug for discovery/scraping vocabulary, automatic discovery defaults, externally sourced tiers, and external filing-query instructions.

CP-1C authority corrections:

- Replace the shared-canon public-research exception with a supplied-evidence boundary aligned to `MODULES["CP-1C"].source_mode == "supplied_only"`.
- Limit candidate selection to analyst-uploaded peer lists and peer entities disclosed in supplied bytes. A peer list remains selection input, not metric evidence.
- Require every peer metric to resolve to a supplied source file and locator. Public/regulatory filings and other source types remain usable only when their exact bytes were supplied to the active run.
- Replace automatic discovery and scraping tables with a supplied Peer Candidate Source Register. No peer evidence produces `PEER_SET_NOT_SUPPLIED` and `Blocked`; insufficient benchmark data produces a typed limitation or blocked dependent calculation.
- Replace scraping-specific provenance tiers, exclusion rules, validation wording, and script comments with supplied-primary/supplied-secondary evidence rules.
- Preserve all substantive peer analysis: the 15 core formulas, 16 comparability dimensions, alignment standard, minimum-N rules, outlier analysis, valuation calculations/tables, creditor implications, gaps ledger, and downstream handoffs.

Regenerated identities:

- Deploy V build ID: `1912cb03a21a750ec995e623de9b9a8973aa6e0160cc4b0d8c36f4a863c5c001`.
- Independent approved-release pin: 319 files, `1f1a71d3388070f57cfeafd220c060c411fff426cf21b8c1b02a5270e5718200`.
- CP-1C assembled-authority pin: `6a472b9802a1fc21784d1fee1f306b051701860c80e57f459819b46d9600ce42`.

### Final acceptance after CP-1C correction

1. Focused detector and direct CP-1C authority tests: `3 passed in 38.26s`.
2. Exact bundle/spec suite: `26 passed in 1.70s`.
3. Standalone integrity check: `Deploy V integrity is current`.
4. Module consistency: `26 modules checked, 0 with drift.`
5. Ruff over server/tests excluding vendored methodology: `All checks passed!`
6. Quality-ledger coverage: 45 routes, 230 product files, 120 features; all documented.
7. CP-1C acquisition-vocabulary search: zero matches.
8. `git diff --check`: exit 0.

### Final confidence review

Least-confident areas were detector false positives, incomplete removal through shared authority, accidental loss of peer-analysis rules, and hand-updated identity mistakes. The `public-private` regression now proves the generic boundary; the tracked-tree detector plus direct recursive CP-1C assertion and zero-result search cover the complete authority surface; diff review confirmed the formulas, registers, thresholds, valuation/outlier logic, and downstream semantics remain; and the exact suite independently verifies the regenerated bundle bytes and assembled authority. A second non-mutating regeneration check is current.

The only remaining `web_only`/`hybrid` tokens inside the CP-1C directory belong to a generic validator branch explicitly gated on `module_id == "CP-DR"`, duplicated across methodology packages. They are not CP-1C authority or an acquisition instruction and were deliberately left unchanged to avoid creating a divergent validator clone outside this correction's scope.

Rewrite tournament was skipped under the skill's test-only/trivial-change exception: no non-trivial executable function changed in this correction. The peer-statistics edits are comments, the registry edit is a regenerated literal pin, and the detector change is test-policy logic covered by the adversarial cases above.

## Final generic-location boundary correction

The final re-review found that excluding every hyphen after `public` or `external` was too broad: acquisition instructions using `public-company`, `external-regulatory`, or `external-facing` could evade the generic detector. The matcher now exempts only benign `public-private` comparability wording; `external` has no hyphen exception.

Pinned source-safe positives:

- `Search public-company filings on the web.`
- `Search filings from public-company sources.`
- `Download external-regulatory filings.`
- `Search filings from external-facing databases.`

The existing `public-private` peer-comparability sentence remains a pinned negative.

Final verification:

- Focused detector/direct CP-1C suite: `3 passed in 38.60s`.
- Exact Task 2 bundle/spec suite: `26 passed in 1.96s`.
- Integrity check: current.
- Module consistency: 26 modules, zero drift.
- Ruff and quality-ledger coverage: clean.
- `git diff --check`: exit 0.

Confidence review focused on the sole semantic distinction introduced here. Case-insensitive `public(?!-private\b)` rejects the intended benign compound while allowing other hyphenated public source descriptions; unqualified `external` covers both ordinary and hyphenated external-source descriptions. The four positive cases, the existing negative case, full tracked-tree self-scan, and unchanged bundle identities all pass.

Rewrite tournament was explicitly skipped because this commit changes only test-policy regex/data and task records; it changes no product or methodology executable function.
