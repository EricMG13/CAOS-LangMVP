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
