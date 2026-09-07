# PR babysit loop — PR #37

## 2026-09-02 — PR #37, head 215c6d6 — tick 1

- PR #37 `codex/enterprise-readiness-review` → main. OPEN, **draft**, MERGEABLE,
  mergeStateStatus UNSTABLE. Local HEAD == origin head (215c6d6).
- Behind main: 0 (44 ahead). No rebase needed.
- Review threads: none (0 unresolved).
- CI run 33629028442: pass — frontend, deploy, image, security, security-review.
  **fail** — "Browser — workbench journey and accessibility" (job 100243596026).
  pending — Server tests 3.12 and 3.14.
  Run still in progress, so `--log-failed` is unavailable; cannot yet classify the
  browser failure as flaky vs real.
- **Blocker for autonomous fixes:** the worktree has uncommitted changes I did not
  make (runtime.py, storage/runs.py, test_runtime_calculations.py, docs/DECISIONS.md).
  Not touching them; any fix I commit must stage only my own files.
- Action: none. Waiting for the run to finish before diagnosing.

## 2026-09-02 — PR #37, head 215c6d6 → local a28c68c — tick 2

- Branch still 0 behind main; still 0 review threads.
- Server tests (3.12 and 3.14) have been `in_progress` since 12:16Z — ~75 min.
  Not yet classifiable; left alone.
- **Diagnosed the browser failure — real, not flaky.** Pulled the completed job's
  log through `gh api .../actions/jobs/100243596026/logs` (works while the run is
  still in progress, unlike `gh run view --log-failed`):

      RuntimeError: run.py requires ENVIRONMENT=production; use dev.py for development

  Root cause is a collision between two commits on this branch:
  - `41bbafe feat(startup): enforce qualified enterprise provider` made
    `run.py::main` refuse any environment but `production`.
  - `4b7f5b5 feat(dev): host-control provider binding` added
    `CAOS_PROVIDER=host_control` to the browser job but kept `run.py`, and
    `config.py:138` refuses `host_control` *in* production.

  So the job asked for two mutually exclusive things. It died at "Start combined
  app"; no Playwright check on this branch has ever executed.

- **Fix (commit `a28c68c`):** both keyless browser gates now launch
  `caos/server/dev.py` instead of `run.py` — dev.py is where the host-control
  binding is legal. Applied to `.github/workflows/ci.yml` (browser job) and
  `.github/workflows/nightly.yml`, which carried the same launch, still keyless
  and now also environment-refused.
- **Verified locally**, not assumed: ran the exact CI command line
  (`ANTHROPIC_API_KEY="" CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true
  … dev.py`, PORT=8123) and curled the health probe →
  `{"status":"ok","store":true,"bundle":true,"checkpointer":true}`.
  YAML re-parsed for both workflows. No Python changed, so no Ruff run and no
  test files touched. The Playwright steps themselves are still unproven — they
  will run for the first time on the next CI run.
- Staged only the two workflow files. The other session's WIP from tick 1 is gone
  from the working tree; it landed as local commit
  `20557e1 fix(engine): refuse forged host limitation flags`.
- **Not pushed.** `origin` is still at `215c6d6`; pushing would also publish
  `20557e1`, an unpushed commit from another session. Escalated to the user
  rather than deciding for them. **User's answer: hold — do not push until told.**
  Loop continues, but origin stays red on the browser job until the push is
  unblocked.

## 2026-09-02 — PR #37, head a28c68c — tick 3

- The hold is moot: `origin/codex/enterprise-readiness-review` is already at
  `a28c68c`. Both `20557e1` and my `a28c68c` were pushed by the parallel session
  between my fetch and the user's "push it". Nothing left for me to push; I did
  not push anything.
- New CI run 33630627451 on `a28c68c`. Pass: frontend, deploy, image, security,
  security-review. Server 3.12/3.14 pending again. Browser **still fails**.
- **The workflow fix worked.** The browser job now runs 2m37s instead of 1m32s
  and its log carries
  `{"status":"ok","store":true,"bundle":true,"checkpointer":true}` — the app
  starts, and Playwright now executes for the first time on this branch.
- New failure, one step later, in the workbench smoke:

      page.waitForFunction: Timeout 30000ms exceeded.
        at caos/frontend/scripts/workbench-smoke.mjs:1099

  Line 1099 waits for focus to return to the dirty assumption editor
  (`aria-label === "Revenue growth, FY2025, BASE"`) after Escape dismisses the
  discard-draft dialog raised by `history.back()`.

- **Not this PR's regression — it pre-exists on main.** main's own CI run
  33609642643 (`0458f10`, current main tip) fails its browser job at
  `workbench-smoke.mjs:1095`, which is byte-identical to branch line 1099; the
  4-line offset is this branch's unrelated edits earlier in the file. The
  branch's diff to `workbench-smoke.mjs` touches Google-font request watching
  and acceptance-region geometry only — nothing in the focus path.
- **Flaky, not deterministic.** main alternates on this job: 612cf3d fail,
  8bcfb4e pass, 6b79e6a fail, 14c49ec pass, 0458f10 fail. `14c49ec → 0458f10` is
  the tell — 0458f10 is `chore: gitignore the dev run-state directories`, which
  cannot touch focus restoration, yet it flipped green to red. Same frontend
  code, both outcomes. This is a genuine race in focus restoration, not a
  transient-infrastructure timeout.
- Action: none taken on it. Did **not** re-enqueue — the run is still in progress
  (server jobs), and re-running a job that is red on main too would only mask a
  known-flaky gate rather than tell us anything about this PR.
- Incidental observation, not acted on: the `server` job in ci.yml has no
  `timeout-minutes`, so it inherits the 360-minute default. That is why the
  server jobs sat "in_progress" for 80+ minutes on the previous run without
  being cut off. `frontend` caps at 15 and `browser` at 20.

## 2026-09-02 — PR #37, head a28c68c → 4b2195e — tick 4

- Still 0 behind main (46 ahead), still 0 review threads, still draft.
- **Focus-race work reverted at the user's direction.** Three fix iterations on
  `Workspace.tsx` never reached a verified result, and the flake pre-exists on
  main, so it is not #37's to carry. Working tree restored to committed source,
  scratch `workbench-smoke.repro.mjs` deleted, `caos/frontend/out` rebuilt from
  clean source. Findings preserved in `focus-race-findings.md` — root cause,
  the three attempts, and the five ways the local harness produced false
  readings. WIP patch kept in the session scratchpad, marked do-not-apply.
- **Server jobs finished and both FAILED** (they were pending at tick 3):
  - 3.12: 2 failed, 921 passed — `PDF_UNICODE_RENDERER_UNAVAILABLE` and
    `test_engine_close_drains_foreign_loop_continuation`.
  - 3.14: 1 failed, 946 passed — `PDF_UNICODE_RENDERER_UNAVAILABLE`.
- **PDF failure: real, branch-introduced, fixed.** `346748f` added a Unicode PDF
  path that shells out to `pango-view`; `render_frozen_pdf` refuses when the
  binary is missing. `caos/deploy/Dockerfile:13` installs `fonts-noto-cjk` and
  `pango1.0-tools`, but the CI server job never did — CI was testing a thinner
  environment than the one that ships. `origin/main`'s renderers.py has no
  `pango-view` reference at all, which is why main's server legs stayed green.
  Invisible locally because Homebrew supplies `pango-view`: verified the test
  passes here (`/opt/homebrew/bin/pango-view` present) and that the CI refusal is
  exactly the missing-binary branch. Fixed in `4b2195e` by installing the same
  two packages in the server job. Pushed (origin was still at `a28c68c`; only my
  commit went up).
- **Engine-close failure: not reproduced, left alone deliberately.** 3.12 only.
  Reproduced attempts: passes standalone on 3.14 and on 3.12 (via
  `uv run --python 3.12`), and the whole `test_runs_spec.py` passes on 3.12
  (77 passed). So it needs full-suite context — order-dependent event-loop
  teardown, ~21 min to reproduce. Did **not** patch it blind and did **not**
  re-enqueue in isolation; `4b2195e` re-runs the whole matrix anyway, which is
  the cheap experiment. If it fails again on the new head it is reproducible in
  CI and earns the full-suite local repro.
- Note: `uv run --python 3.12` **replaces** `caos/server/.venv` in place. Restored
  it to 3.14.6 afterwards. No `uv.lock` was left behind.


## 2026-09-05 tick 9 — PR #61 @ d51ebb4 — DONE
Found: all 11 checks pass; PR already MERGED at 11:49:31Z by EricMG13 (squash afb93ab) outside this session — I did not merge it.
Did: removed worktree frontend-ia-audit-84c3b6, deleted the local branch, stopped the loop.

## 2026-09-05 tick 10 — PR #62 @ 314e73b -> 037641a
Found: Server 3.12 and 3.14 both fail, same step: "Quality ledger covers every route and product file". Real failure, not flaky — FE-D1's sixteen docs/design/canvas/ records match no FILE_MAP prefix in docs/quality_ledger_coverage.py.
Did: reproduced locally in a scratch worktree at the PR head (16 FAIL lines), added one named FILE_MAP entry for ^docs/design/canvas/ (named, not a docs/ blanket exclusion), re-ran the check green (54 routes, 373 files), pushed 037641a. Ruff on that file reports two PRE-EXISTING F601 duplicate-key warnings (lines 77-78) outside CI's caos/server+caos/tests scope; left alone.

## 2026-09-05 tick 12 — PR #62 @ 037641a -> 7590ad2
Found: the quality-ledger fix worked (both server jobs got past it), but both then failed on caos/tests/test_recorded_review.py::test_the_script_reviews_this_repository_head_without_a_block — AssertionError: 36 == 62. Real failure, not flaky.
Diagnosis: FE-D1 is the first commit with spaces in filenames. Two latent defects. (1) git appends "\t<timestamp>" to the "+++ b/<path>" header when the path has a space, so parse_diff registered every such file twice — once from "diff --git", once as "<path>\t" (23 real + 13 dupes = 36). (2) The test built its expected list with .stdout.split(), splitting --name-only output on every space (23 files -> 62 tokens).
Did: reproduced directly against origin/main...037641a (files_examined 36 vs 23 real paths), cut the +++ header at the first tab, switched the test to .splitlines(); re-verified parse_diff yields exactly the 23 paths git reports (sets identical). test_recorded_review 8 passed, test_workflow_security + test_scan_floors 27 passed, ruff clean on both files. Pushed 7590ad2.
