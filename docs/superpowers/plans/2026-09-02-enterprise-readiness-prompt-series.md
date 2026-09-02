---
meta:
  contentType: How-to
  audience: The decision owner running the enterprise-readiness plan through Claude Code sessions
---

# Run the enterprise-readiness plan as Claude Code prompts

This page turns `ENTERPRISE_READINESS_PLAN.md`, `ENTERPRISE_TESTING_READINESS.md`, and the Codex execution plan (`docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`, Tasks 1–13) into eleven goal prompts for Claude Fable 5.1 and four recurring loop prompts for Claude Opus 5, starting with an adversarial review of the uncommitted Task 6 work. It tells you the order to run them, which checkout each one runs in, which model and effort to use, and what you must decide between prompts. The prompts follow Anthropic's [Prompting Claude Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1) guidance: a goal, the reason behind it, binding constraints, and a definition of done, rather than a step list.

## What the codebase looked like on 2026-09-02

This review was taken in the `enterprise-readiness` worktree before any prompt ran. The first goal prompt re-verifies each item; do not treat the list as settled findings.

- **Branch**: `codex/enterprise-readiness-review` is 38 commits ahead of `main` and 28 commits behind it (merge-base `ba97a89`). Nothing on the branch has been rebased onto the `main` commits that landed after 2026-09-01.
- **Working tree**: 55 files uncommitted, +7,253/−814 lines, seven new files (`caos/server/caos/methodology/execution.py` and six test modules). `.superpowers/sdd/progress.md` marks Tasks 1–5 complete and Task 6 in progress.
- **Suite**: `16 failed, 900 passed, 2 skipped, 1 error in 765.72s` with `--continue-on-collection-errors`; without that flag collection stops because `caos/tests/test_finalization_metering.py` imports `_agent_turns` from `test_module_wiring.py`, which the working tree removed. Ruff passes. Twelve of the failures share one shape: the run terminates as `SOURCE_EVIDENCE_INSUFFICIENT` where the spec expects `AGENT_OUTPUT_INVALID` or success, including seven prompt-injection tests (`test_smuggled_envelope_fields_are_refused_not_ignored`, `test_citation_to_an_undelivered_block_is_refused`, and five more), three observability tests, and the rewritten corpus host control (CP-1C). The rest: four model-builder tests (`model-facing source table has no visible rows`; invalid active growth no longer rejected) and one audit regression (`MODEL_REVISION_INTEGRITY_FAILED: signed revision record is invalid`).
- **Vendored bundle**: the working tree changes the Deploy V build id from `1912cb03…` to `237bf4bc…` (`cp-0-source-readiness/SKILL.md` split into separately runnable CP-PARSE and CP-0 profiles, work-factor bounds in `bond_analytics.py`, the module catalog's CP-PARSE relationship changed from `alias` to `runnable_profile`, regenerated manifests). `docs/DECISIONS.md` is untouched, and §14.11 requires a dated entry for every further bundle change.
- **Registry**: `ModuleSpec.mode_screen` now defaults to `agent`, and every module, including CP-PARSE and CP-0, executes through the provider at both depths. `docs/DECISIONS.md` §14.3 supports this; `ENTERPRISE_TESTING_READINESS.md` RUN-030 and `ENTERPRISE_READINESS_PLAN.md` scope decision 4 still require a deterministic screen artifact.
- **Availability**: `MVP_PATHWAYS` in `caos/server/caos/engine/runtime.py` now includes `DISTRESSED_RESTRUCTURING`; `caos/server/caos/api/__init__.py:353` still hard-codes `deep_research_available: False`; `Workspace.tsx` is untouched although Task 6 lists it.
- **Provider surface**: a second host tool, `run_methodology_calculation`, lets the model submit `input_json` to allowlisted, digest-pinned vendor calculators; the corpus host control now drives runs through the ordinary `engine.start_run` path and no longer requests the placeholder capability.
- **Runtime**: the local `caos/server/.venv` is Python 3.13.15; the plan and nightly declare 3.14; CI runs 3.12 and 3.14. The 30-document Carnival corpus is present locally but gitignored.
- **Process**: the execution plan records that the user disabled rewrite tournaments for this execution; the session hooks in this environment still announce them as active.

## How to run the series

### Models and effort

Use `claude-fable-5-1` for every goal prompt (`ER-G0` to `ER-G10`) and `claude-opus-5` for every loop prompt (`ER-L1` to `ER-L4`). Switch with `/model claude-fable-5-1` or `/model claude-opus-5` at the start of the session. Fable 5.1 does the long-horizon implementation and review work because it holds a whole task in one turn and self-verifies; Opus 5 runs the loops because a loop tick is mechanical verification on an interval and costs half as much per token.

Keep Claude Code's default effort (`xhigh`) for goal prompts: the claude-api reference recommends it for agentic coding, and each goal here is a multi-hour task with the full specification given up front. If your build exposes an effort control, drop loops to `medium`; the loop prompts are written so a tick has nothing to reason about beyond the commands it runs.

A goal prompt turn can run for a long time. Do not interrupt it to ask for status: the standing preamble asks for a line before work starts and a re-grounding summary at the end, and the task report in `.superpowers/sdd/` is written as the work proceeds, so you can read progress there from another device.

### Where each prompt runs

Every goal prompt runs in a git worktree under `.claude/worktrees/`, never in the primary checkout, and one session owns a worktree at a time. Two sessions editing one worktree corrupt each other's runs, and two `uv run` invocations against one `caos/server` block on the project lock with no output.

- **`ER-G0` and `ER-G1`**: the existing worktree `.claude/worktrees/enterprise-readiness` on `codex/enterprise-readiness-review`, because the uncommitted work lives there. Open the session with `EnterWorktree` on that path or start Claude Code inside it.
- **`ER-G2` to `ER-G8`**: a fresh worktree each, branched from `main` after the previous task's pull request merges: `git worktree add .claude/worktrees/er-task-07-deep-research -b claude/er-task-07-deep-research main`, then enter it. Each task lands through its own pull request, which keeps `docs/DECISIONS.md` §9's one-branch-per-phase rule and keeps reviews small.
- **`ER-G9` and `ER-G10`** (the candidate): the primary checkout on `main` at the candidate tag, because images are built once from the frozen commit and the Compose stack, backups, and restore drill run from there. Check where `main` is checked out first; the primary checkout normally holds it.
- **`ER-L1`** (branch health): a detached verify worktree that no goal session ever edits. Create it once:

```bash
git worktree add --detach .claude/worktrees/verify-enterprise codex/enterprise-readiness-review
```

Then, inside `.claude/worktrees/verify-enterprise`, build its interpreter and frontend dependencies once and copy the gitignored corpus bytes in:

```bash
uv run --project caos/server --extra dev python -m pytest --version && (cd caos/frontend && npm ci) && cp -R ../enterprise-readiness/caos/tests/corpus/documents caos/tests/corpus/
```

Remove `caos/server/uv.lock` afterwards with `git clean -f caos/server/uv.lock`; it must never be committed.

- **`ER-L2`** (pull-request babysit): the worktree that owns the branch under review, and only while no goal session is active there, because the loop pushes fixes.
- **`ER-L3`** (live qualification matrix) and **`ER-L4`** (soak watch): the primary checkout at the candidate tag, alongside the running Compose stack, with the protected credentials exported in that shell only.

### Session hygiene

- Run the backend suite as `caos/server/.venv/bin/python -m pytest caos/tests -q -p no:cacheprovider`. `python -m pytest` from `CLAUDE.md` does not resolve on this machine, and `uv run` takes a project lock that another session may hold.
- Never run bare `git stash` or `git stash pop`; the stash is shared across every worktree.
- Commit with the repository's `/commit` skill; it stages only files the session touched and never the user's parallel work.
- Keep `.superpowers/sdd/progress.md` and the per-task report current. The report doubles as the model's memory across context compaction.
- Rewrite tournaments stay disabled for this execution (decision D4 below); `confidence-review` runs before every task is declared done.

### Run order

| Step | Prompt | Model | Where | Proceed when |
|---|---|---|---|---|
| 1 | `ER-G0` adversarial review of the WIP and the plan | Fable 5.1 | `enterprise-readiness` worktree | The review file exists and you have read its verdict, contradictions, and decisions |
| 2 | Decisions D1–D5 (below) | You | Append a `## Decisions` section to the review file | Every decision has one recorded answer |
| 3 | `ER-G1` land Task 6 and open the pull request | Fable 5.1 | `enterprise-readiness` worktree | Draft PR to `main` exists; gates quoted green |
| 4 | `ER-L2` babysit that PR; you merge when it reports ready | Opus 5, `/loop` | `enterprise-readiness` worktree | PR merged; branch deleted |
| 5 | `ER-L1` branch health, start during step 3 and keep it running through step 12 | Opus 5, `/loop 20m` | `verify-enterprise` worktree | Runs continuously; watch `codex/enterprise-readiness-review` until step 4, then restart it on `main` |
| 6 | `ER-G2` Task 7 Deep Research | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 7 | `ER-G3` Task 8 documents-only journey | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 8 | `ER-G4` Task 9 source-complete modelling | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 9 | `ER-G5` Task 10 opinion, publication, audit package | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 10 | `ER-G6` Task 11 corpus manifests and qualification harness | Fable 5.1 | new worktree from `main` | PR merged; external inputs listed as BLOCKED EXTERNAL |
| 11 | `ER-G7` Task 12a database truth, simulations, single instance, backup | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 12 | `ER-G8` Task 12b security, identity, browsers, accessibility, capacity harness | Fable 5.1 | new worktree from `main` | PR merged via `ER-L2` |
| 13 | `ER-G9` Task 13, freeze the candidate and run the automated gates | Fable 5.1 | primary checkout at candidate tag | Candidate manifest written; deterministic gates quoted; soak started |
| 14 | `ER-L3` live qualification matrix and `ER-L4` soak watch, in two sessions | Opus 5, `/loop 45m` and `/loop 30m` | primary checkout, Compose stack running | Every required cell has three retained results (or a cell failed twice); post-soak comparison recorded |
| 15 | `ER-G10` Task 13, assemble and verify the evidence package | Fable 5.1 | primary checkout at candidate tag | Package hashed; open items listed with owners |

Steps 6 to 12 are sequential because each task edits `runtime.py`, `api/__init__.py`, the stores, or `Workspace.tsx`, and a parallel branch would spend its time on conflicts. `ER-G7` and `ER-G8` may run in parallel worktrees if you accept one rebase at the end; nothing else should.

### Decisions you must make after `ER-G0`

Record each answer under `## Decisions` at the end of `.superpowers/sdd/enterprise-task-6-adversarial-review.md`; `ER-G1` reads them there. The recommendation is listed first.

- **D1 Screen depth**: adopt `docs/DECISIONS.md` §14.3 (provider-backed execution at both depths) and amend `ENTERPRISE_TESTING_READINESS.md` RUN-030 and plan scope decision 4 so screen determinism means identical host-validated identity (plan digest, source pins, calculation refs, canonical schema) for identical pins, matching AUD-019's rule that prose is compared by validated contract; or keep RUN-030 as written and revert screen depth to deterministic modules. The first keeps the working tree; the second discards most of it.
- **D2 Bundle edits**: accept the CP-PARSE/CP-0 profile split and the `bond_analytics.py` bounds as a dated §14.12 entry that names the new build id, the changed files, and why the wrapper or registry seam could not carry them; or require the split to move to the registry and the bounds to a host-side guard before the bundle change is reverted.
- **D3 Python**: rebuild `caos/server/.venv` on 3.14 (`uv python install 3.14`, remove the venv, then `uv run --python 3.14 --project caos/server --extra dev python -m pytest --version`) so local evidence matches the declared runtime; or declare 3.13 an accepted development interpreter in `CLAUDE.md`.
- **D4 Rewrite tournaments**: keep them disabled for this execution, as the Codex plan records, and rely on `confidence-review`; or re-enable them, accepting longer turns and more churn on files the task did not need to touch.
- **D5 Landing strategy**: merge `codex/enterprise-readiness-review` to `main` as soon as Task 6 is green and start every later task from `main`; or keep accumulating on the one branch until the candidate.

## Standing preamble

Every goal prompt begins by pointing at this section, so paste the prompt as written; do not paste the preamble separately. The first paragraph is Anthropic's autonomy block and is kept as written because its opening sentence carries most of the effect.

```text
STANDING PREAMBLE

You are operating autonomously. The user is not watching in real time and cannot answer questions mid-task, so asking "Want me to…?" or "Shall I…?" will block the work. For reversible actions that follow from the original request, proceed without asking. Stop only for destructive actions or genuine scope changes the user must decide. Offering follow-ups after the task is done is fine; asking permission before doing the work is not.

Exception: when the task asks for an assessment, the deliverable is the assessment. Report your findings and stop; do not apply a fix until asked.

Before ending your turn, check your last paragraph. If it is a plan, an analysis, a question, a list of next steps, or a promise about work you have not done ("I'll…", "let me know when…"), do that work now with tool calls. That includes retrying after errors and gathering missing information yourself. Do not stop because the context or session is long. End your turn only when the task is complete or you are blocked on input only the user can provide.

Before running a command that changes system state (restarts, deletes, config edits, force pushes), check that the evidence actually supports that specific action. A signal that pattern-matches to a known failure may have a different cause.

# Delivering work
The user's request, or the plan they approved, sets the scope, and the scope is the deliverable: don't quietly narrow, widen, or swap it. Read ambiguity the way a careful colleague would: make routine judgment calls yourself, and check in only when different readings would lead to materially different work. If you see a real problem with the task as specified, say so in a sentence or two and keep building under stated assumptions. If a question comes up partway, first do everything that doesn't depend on the answer; then state the assumption you made, or, when going ahead on a wrong guess would be unsafe or would make the work useless, put the question at the end of a turn that also delivers that progress. If one part turns out to be blocked, complete every other part in full and say exactly what you left out and why; scaling the work down is the user's call, not yours. A step you have decided on is something to run, not to announce.

# Changes and tests
If, while working or testing, you find a pre-existing bug, a performance concern, or behavior the task doesn't mention, don't fix, optimize or extend it in this change unless the requested behavior cannot work without it; report it as a follow-up in your summary. Where the task is ambiguous, implement the reading its wording and the surrounding code most directly support, state that assumption in your summary, and don't build for the other readings as well. Verify your work however you like; scratch scripts and quick checks need not be kept. Commit tests only where the task asks for them or this repository already keeps tests for this kind of change, sized like the neighboring test files, roughly one focused test per stated behavior, and don't turn scratch checks into additional permanent test files. This is about extras only: implement every behavior the task asks for, completely.

Don't add features, refactor, or introduce abstractions beyond what the task requires. Do the simplest thing that works well, and avoid half-finished implementations too. Only validate at system boundaries (uploads, provider output, HTTP bodies, document text); trust internal code and framework guarantees. Edit files surgically rather than rewriting them when the result would be the same.

# Truthfulness
Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when something is done and verified, state it plainly without hedging. A typed refusal from the application can be a correct outcome. A skipped, waived, not-run, or historical required check never is, and a host-control result (scripted provider, golden output, placeholder capability) is never live-model qualification.

# Repository contract
CLAUDE.md is the engineering contract. docs/DECISIONS.md is the binding decision record; later sections override earlier ones and §14 is current. SPEC_RECONCILIATION.md maps the ten invariants to their named failing tests. CONTEXT.md fixes the vocabulary. The ten invariants are never weakened, and a change that makes one of their named tests pass vacuously is wrong even if the suite stays green. Every JSON success serves a named model from caos/server/caos/responses.py; a new field means a model change plus the pinned key sets in caos/tests/spec/test_http_contracts_spec.py. Every string that can reach pinned state or an event is BoundaryText. Any change under caos/server/caos/methodology/vendor/ needs its own dated entry in docs/DECISIONS.md §14 and manifests regenerated with caos/scripts/regenerate_deploy_v_integrity.py; prefer the wrapper or registry seam when it can carry the behavior. Adding or upgrading a module touches caos/server/caos/modules/registry.py alone.

# Working in this environment
- Backend suite: caos/server/.venv/bin/python -m pytest caos/tests -q -p no:cacheprovider. Lint: caos/server/.venv/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor. Do not use `uv run` while another session may hold the project lock, and never commit caos/server/uv.lock.
- Release gates: python run_sec_audit.py and python docs/quality_ledger_coverage.py with the same interpreter. Corpus host control: CORPUS_FULL=1 with the same pytest command on caos/tests/test_corpus_pathways.py.
- Frontend, from caos/frontend: npm run lint, npx tsc --noEmit, npm run test:unit, npm run build; then, against the combined app on :8000 (python caos/server/dev.py), npm run test:workbench and npm run a11y.
- Never use bare `git stash` or `git stash pop`; the stash is shared across worktrees. Commit with the repository's /commit skill, which stages only the files you touched. Do not push to main directly.
- Keep .superpowers/sdd/progress.md current and write the task report to .superpowers/sdd/enterprise-task-<n>-report.md in the shape of the existing reports there. Write the report as you go, recording decisions, exact commands with their results, and open items: it is your memory across context compaction, and it is what the user reads while you work.
- Delegate independent verification, long searches, and fresh-context review to subagents and keep working while they run; intervene if one drifts or lacks context. Before requesting tools, privately list what you need next, then request every item that doesn't depend on another's result in one response.
- Do not run rewrite tournaments; the user disabled them for this execution. Run confidence-review before declaring the task done.
- Final message: open with the outcome in one sentence, then the one or two things you need from the user, in complete sentences without working shorthand; give each file, commit, or flag its own plain-language clause.
```

## Goal prompts for Claude Fable 5.1

Paste each prompt as the first message of a fresh session in the checkout named in the run order. Each prompt is self-contained: it points at the standing preamble, gives the reason for the work, the goal, the binding constraints, and what done means. Wait for the turn to end before doing anything else in that worktree.

### ER-G0: adversarial review of the current WIP and the plan

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble"). This task is an assessment: change no source, test, vendored, or plan file, create no commits, and do not stash. You may run tests, scripts, and read-only git commands, and you may write the report and scratch files.

Why: I am the decision owner for making CAOS enterprise-testing ready. A Codex session left about 7,300 uncommitted lines on branch codex/enterprise-readiness-review (this worktree) implementing Task 6 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md: provider-backed semantic execution for every module and the Distressed pathway end to end. Before I spend more on this branch I need to know whether that work is sound, whether to land it as is, split it, or discard parts of it, and whether the plan that follows it (Tasks 7–13, the phase plan in ENTERPRISE_READINESS_PLAN.md, and the binding standard in ENTERPRISE_TESTING_READINESS.md) still holds against what the code actually does. Your report becomes the implementer's brief for landing the work, so it has to be actionable without you in the room.

Goal: an adversarial review of (1) the uncommitted working tree plus the 38 commits since main, and (2) the plan, written to .superpowers/sdd/enterprise-task-6-adversarial-review.md.

Review the work the way a hostile reviewer would. Assume the working tree contains a false-success path, a weakened invariant, a test that passes vacuously, a boundary where model or document text can choose host behavior, and a contradiction between the code, docs/DECISIONS.md §14, and the two plan documents. Try to prove each one with a reproduction (a failing assertion, a command with its output, a concrete input) rather than by argument. Cover at least: each of the ten invariants in CLAUDE.md against the diff; the new run_methodology_calculation host tool, where model-authored input_json reaches verified vendor calculators (bounds, non-finite values, work-factor limits, digest binding, replay on resume, audit records); the switch of every module, including CP-PARSE and CP-0, to provider-backed execution at both depths; the test-only placeholder capability (_placeholder_deterministic_runs, run_scripted_for_tests, _allow_placeholder_deterministic_for_tests) and whether any ordinary or API path can reach it; acceptance and snapshot revalidation (validated_run_artifact, _accept_locked, the get_artifact 404 path); the Distressed model overlay and its CP-4C calculator records; the rewritten corpus host control in caos/tests/test_corpus_pathways.py; and the vendored bundle edit (build 1912cb03… to 237bf4bc…).

Starting hypotheses from my own pass. Confirm or refute each with evidence; none is a finding until you have reproduced it:
- The suite does not collect: caos/tests/test_finalization_metering.py imports _agent_turns from test_module_wiring, which the working tree removed. With --continue-on-collection-errors the result on 2026-09-02 was 16 failed, 900 passed, 2 skipped, 1 error.
- Twelve of those sixteen failures terminate as SOURCE_EVIDENCE_INSUFFICIENT where the spec expects AGENT_OUTPUT_INVALID or success: seven in caos/tests/spec/test_injection_spec.py (smuggled envelope fields, citation to an undelivered block, forged frontmatter, a document talking a blocked module into qa_passed, a copied focus question), three in test_observability_spec.py, one in test_audit_regressions.py, and the rewritten corpus host control on CP-1C. Decide whether DECISIONS.md §14.10 (analytical insufficiency is not malformed output) is being applied correctly or whether the working tree now classifies adversarial and malformed output as insufficiency, which would change the typed refusal the injection defence is pinned on and make SPEC_RECONCILIATION.md's anti-vacuity ledger for that file stale. Four model-builder failures ("model-facing source table has no visible rows"; invalid active growth no longer rejected) need the same treatment: stale test or weakened boundary.
- The working tree edits the vendored bundle (cp-0-source-readiness/SKILL.md split into CP-PARSE and CP-0 runnable profiles, bond_analytics.py bounds, the module catalog's alias relationship changed to runnable_profile, regenerated manifests) with no dated DECISIONS.md §14 entry; §14.11 requires one for every further bundle change and prefers the wrapper or registry seam.
- ModuleSpec.mode_screen now defaults to agent, so screen depth is provider-backed everywhere. ENTERPRISE_TESTING_READINESS.md RUN-030 and ENTERPRISE_READINESS_PLAN.md scope decision 4 still require a deterministic screen artifact, while DECISIONS.md §14.3 supports provider execution at every depth. Say which text should win and what must change in the others.
- Deep Research stays hard-coded unavailable in caos/server/caos/api/__init__.py while MVP_PATHWAYS in caos/server/caos/engine/runtime.py now includes DISTRESSED_RESTRUCTURING, and Workspace.tsx is untouched although Task 6 lists it.
- The branch is 38 commits ahead of and 28 behind main (merge-base ba97a89) and has not been rebased onto what landed on main after 2026-09-01.
- The local venv is Python 3.13.15 while the plan and nightly declare 3.14 and CI runs 3.12 and 3.14.
- The 30-document corpus is present locally but gitignored, so the corpus host control depends on the environment without saying so.
- .superpowers/sdd/progress.md marks Tasks 1–5 complete on Codex self-review; sample two of those tasks' evidence claims against the code and the current test results.

Deliverable shape, one file, in this order: a verdict paragraph (land, split, or discard, per file group, with the reason); findings ranked by severity, each with file:line, the failure scenario, the reproduction, and the invariant or plan clause it violates; an invariant table (1–10: intact, weakened, or unproven, naming the test that proves it); the contradictions between code, DECISIONS §14, ENTERPRISE_TESTING_READINESS.md, and ENTERPRISE_READINESS_PLAN.md, each with a recommended resolution; the decisions only the user can make, each stated as a question with your recommendation first; a commit plan that splits the working tree into isolated, test-first commits in dependency order; and a plan delta for Tasks 6–13 (what to add, drop, or reorder, naming the ETR blocker and G-gate each change affects). Close with the exact commands you ran and their results.

Use the adversarial-reviewer, security-review, and confidence-review skills where they help, and gitnexus for impact tracing if the index exists. Run the suite yourself and quote its summary line; any claim that something passes needs the command and its output beside it. Spend the reasoning space on finding what is wrong, and write the report once, in the file, not first in your head and again in the output.
```

### ER-G1: land Task 6 as reviewable commits and open the pull request

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: the adversarial review in .superpowers/sdd/enterprise-task-6-adversarial-review.md has been adjudicated; my decisions are recorded at its end under "## Decisions" (D1 screen depth, D2 bundle edits, D3 Python, D4 rewrite tournaments, D5 landing strategy, plus any the review raised). I need Task 6 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md landed as reviewable commits on codex/enterprise-readiness-review so the branch can go to main as one pull request and every later task can start from main.

Goal: this branch is green, truthful, rebased on main, with an empty working tree, a draft pull request open against main, and Task 6 recorded as complete in .superpowers/sdd/progress.md and .superpowers/sdd/enterprise-task-6-report.md.

Done means every item below holds and is evidenced in the report with the command and its output:
- Every finding the review ranked critical or high is fixed, or deferred with the user's decision quoted; no finding is dropped silently. Findings ranked lower are fixed when the fix is inside a file the commit plan already touches, and listed as follow-ups otherwise.
- The working tree is split into isolated commits in the review's commit-plan order, each carrying its tests, committed with the /commit skill. The vendored bundle change is its own commit paired with a new dated docs/DECISIONS.md §14 entry naming the new build id, the changed files, why the wrapper or registry seam could not carry the behavior, and the regenerated manifests; if D2 says the change must move to the registry or a host-side guard instead, the bundle is restored to build 1912cb03… byte for byte and the entry records that.
- D1 is applied consistently: the registry, ENTERPRISE_TESTING_READINESS.md RUN-030, ENTERPRISE_READINESS_PLAN.md scope decision 4, SPEC_RECONCILIATION.md, and CLAUDE.md say the same thing about screen depth, and the test that pins it fails when screen determinism (as D1 defines it) is broken.
- Availability comes from runtime truth: Distressed is in the served available set only because both depths and the downstream model, deliverable, and reconstruction contracts pass, Deep Research is reported from the same source rather than a literal False, and Workspace.tsx renders whatever the capability response says.
- The branch is rebased onto main, not merged, with conflicts resolved through the resolving-merge-conflicts skill and linear history preserved.
- On the final commit, all of these pass and are quoted from this session: the backend suite, Ruff, python run_sec_audit.py, python docs/quality_ledger_coverage.py, the corpus host control with CORPUS_FULL=1, and the frontend gates (lint, tsc, unit, build, workbench smoke, a11y against the combined app).
- Nothing passes vacuously: for each invariant test in SPEC_RECONCILIATION.md that the diff touches, the report shows the mutation that makes it fail.
- A draft pull request to main exists (gh pr create --draft), its body lists the commits, the decisions applied, the gates with their results, and what remains BLOCKED EXTERNAL, and it ends with the repository's generated-with line.

Scope: Task 6 only. Do not start Tasks 7–13, do not touch corpus bytes, credentials, or CI secrets, and do not merge the pull request.
```

### ER-G2: Task 7, Deep Research with a governed brief and approval gate

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: enterprise scope is six pathways (docs/DECISIONS.md §14.1). Deep Research is exposed by the contracts and the frontend and has a governed-brief and approval-gate contract, but the API discards the brief and the runtime reports the pathway unavailable. Analysts need to run a bounded research question against a supplied pack, approve the exact plan that will execute, and receive a source-grounded memo with the same acceptance, model, deliverable, and reconstruction guarantees as every other route. This is Task 7 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read the Task 7 text and the Phase 2 and Phase 4 Deep Research rows of ENTERPRISE_READINESS_PLAN.md before starting.

Goal: on this branch from main, a Deep Research run can be created from a validated brief, pauses at a digest-bound plan approval, resumes only on the exact approved plan, completes through the ordinary provider path at full depth, is accepted, revalidates the model or declares no numeric effect, and flows through draft, freeze, file, and reconstruction, with availability reported from runtime truth.

Binding constraints: the route is static (invariant 10), so the brief selects nothing about the node set or edges. The approval is a digest-bound interrupt (invariant 5) with expected-hash compare-and-swap and case authorization on read and approve. The brief, its digest, the proposed plan, the approval hash, actor, and timestamp survive restart (invariant 6) and are bound into run authority. No web, email, filesystem, or network evidence exists (invariant 1). Every new wire field goes through a named response model and the pinned key sets. Reuse the existing research-plan contracts and the frontend's existing approval surface; Deep Research has no screen depth, and you do not invent one.

Done means: failing-first tests for brief persistence, approval CAS, replay by pin after restart, and refusal of a missing or full-depth-incompatible brief now pass; the corpus host control runs DEEP_RESEARCH at full depth on the Carnival pack with a fixture brief and is labelled orchestration proof only; injection-bearing, ambiguous, and insufficient briefs follow answer-keyed typed refusal or limitation paths; deep_research_available is derived, never literal; the backend suite, Ruff, the two release gates, and the frontend gates pass and are quoted; .superpowers/sdd/progress.md and enterprise-task-7-report.md are written; a draft pull request to main is open with the same body shape as the previous task's. The question-specific C22 pack and live-model qualification are external inputs: record them as BLOCKED EXTERNAL with exactly what is needed, never as passed.
```

### ER-G3: Task 8, document upload as the complete analytical journey

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: blocker ETR-B01. Today an analyst creates a case, chooses a pathway, compiles, starts, accepts, and sets up a report. The enterprise promise in ENTERPRISE_TESTING_READINESS.md is that supplied documents are the only analytical input and every analytical field is derived server-side. This is Task 8 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 8, Phase 3 of ENTERPRISE_READINESS_PLAN.md, and the UX-001 to UX-020 and SRC-001 to SRC-030 checks before starting. The frontend's visual language is fixed by DESIGN.md and .impeccable.md: inherit it, do not reinvent it.

Goal: on this branch from main, an analyst drops one or more documents on the entry surface and CAOS creates or resolves the case, admits every file or none, builds the server-owned source-disposition and period-coverage manifest, selects the route from host classification (Full Credit at full depth unless host evidence proves a narrower objective), pins and starts the run with the qualified provider identity, streams progress from the persisted run events, and opens either the review result or one typed clarification or refusal, and all of that survives refresh, reconnect, double submit, back navigation, and process restart.

Binding constraints: one strict multipart intake endpoint that orchestrates ingest_upload and the existing domain services, with no endpoint calling another endpoint and no duplicated validation; a partial admission never leaves a runnable case or an invisible accepted source, and its audit trail is complete; issuer, label, document types, periods, and pathway fit are machine suggestions from prepared evidence, labelled and auditable, never authority taken from document instructions; existing-case resolution never crosses membership; provider, model, digests, confidence, and route nodes are never accepted from the browser or a document; workspaceAuthority.ts stays the sole stale-response guard and every intake response is bound to the current generation; the run console remains the one home for run progress and acceptance; the drop zone is keyboard accessible and every state (empty, loading, evidence, model gap, refusal, review) passes WCAG 2.1 AA; advanced APIs stay for tests but are not required user actions.

Done means: each UX-001 to UX-020 check maps to a retained server test or a data-driven browser journey in the workbench smoke, with the six pathway selections proven as data cases of one journey rather than six implementations; 20 to 30 document cases cover success, partial failure, duplicate, wrong issuer, scanned no-text refusal, restatement, conflict, and add-the-missing-source recovery; the golden journey asks for no source fact, pathway, depth, model, or budget; success opens a source-grounded review and never presents the machine output as the analyst's opinion; the backend suite, Ruff, the release gates, and the frontend gates including workbench and a11y pass and are quoted; the progress row and enterprise-task-8-report.md are written; a draft pull request to main is open.
```

### ER-G4: Task 9, source-complete modelling for all six pathways

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: blocker ETR-B12. No candidate evidence proves that every relevant annual, quarterly/interim, forecast, and forecast-revision document feeds the analysis and the financial model, and no pathway other than Full Credit has a declared model effect. This is Task 9 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 9, Phase 3 items 9 and 10, the CALC-001 to CALC-020 checks, and the metamorphic rule in "Test deterministic models and scenarios" before starting.

Goal: on this branch from main, every pathway's declared model effect is implemented and proven from the complete relevant manifest: Full Credit builds the complete model; Earnings Update updates periods and forecast variance; Covenant and Refinancing updates covenant and refinancing assumptions; Relative Value attaches time-aligned market marks supplied by upload; Distressed updates scenarios and recovery; Deep Research revalidates or declares no numeric effect. Every used source reaches model inputs, assumptions, calculations, or cited analysis, and every other supplied file carries an explicit disposition with a bounded reason.

Binding constraints: model calculation stays pure and finite (invariant 7), with non-finite values and zero denominators refused before use; null, unavailable, not calculable, and not disclosed are never zero; a derived period never overwrites a reported one; reported actuals, external forecasts, and analyst scenarios keep distinct authority; Model Builder remains the governed seam (preview digest, expected-head CAS, sign-off) and no pathway fabricates an unrelated standalone model; no source-complete claim relies on run_scripted_for_tests or any placeholder capability; loan-workbook and other document-derived text passes BoundaryText before it reaches CP-3, a model, or a renderer.

Done means: metamorphic tests remove or change one annual, one quarterly/interim, and one forecast source in turn, add an irrelevant source, add a restatement or conflict, and withdraw or corrupt a bound source, and each asserts the answer-keyed change in input, artifact, model fingerprint, output, limitation or refusal, and audit lineage, while an irrelevant file changes nothing and is never silently discarded; all six route and depth host controls pass with the lineage assertions; CALC-001 to CALC-020 each map to a retained test; the backend suite, Ruff, the release gates, and the frontend gates pass and are quoted; the progress row and enterprise-task-9-report.md are written; a draft pull request to main is open. Licensed market marks for Relative Value are an external input: build the intake and lineage against a synthetic time-aligned fixture and record the licensed pack as BLOCKED EXTERNAL.
```

### ER-G5: Task 10, opinion ownership, institutional publication, and reconstruction

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: gates G7 and G8 and blocker ETR-B13. External stakeholders must receive files that a human analyst owns, a separate approver authorized, and an independent reviewer can reconstruct, at a presentation standard no worse than Credit Operating System commit e566c1b. Today freeze and file are separate and digest-bound, but there is no opinion sign-off, no separation of duties, no filing receipt, the PDF is a single-column text export, XLSX is a flat dump, and audit is not append-only at the database boundary. This is Task 10 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 10 and all of Phase 4 in ENTERPRISE_READINESS_PLAN.md, including the minimum pathway output contract table, before starting.

Goal: on this branch from main, every pathway publishes a decision-first report, its model appendix or workbook, and an Evidence & QA Control Sheet from one server-frozen typed payload; an analyst signs an append-only, digest-bound opinion before freeze; a distinct, provisioned approver files the exact frozen bytes and receives an immutable detached filing receipt; browser, Markdown, PDF, and XLSX carry the same facts, numbers, units, citations, origin labels, limitations, model identity, and opinion; audit is append-only with an integrity chain; and a case-scoped audit package with an offline verifier reconstructs sampled outputs without the application or its secrets.

Binding constraints: every gate where execution waits on a human is a digest-bound interrupt or a store CAS transaction (invariant 5); approved bytes are never rerendered, not even to insert an approver name; the opinion signer cannot approve or file the same output; ANALYST_JUDGMENT never carries an uncited documentary fact; the module output envelope stays strict (invariant 9); frozen and filed records are created only after hash-addressed atomic publication and verified reads, and a rendering failure never leaves a frozen or filed record; XLSX rendering lives in the worker and nowhere else; the package holds no secret, prompt, hidden reasoning, provider error body, or unauthorized full source text; the deliverable export's media types remain a wire-visible decision, so change them only with the matching response-model and gzip-exclusion updates; the benchmark is a presentation and content reference, and none of its seeded data, fixture conclusions, browser-owned composition, or tiny appendix type is copied.

Done means: every Phase 4 verify item in ENTERPRISE_READINESS_PLAN.md maps to a retained test, including the concurrent-filer race with one winner and a typed loser, tamper detection on download, the approver-provisioning path without database seeding, and audit insertion, update, deletion, and reordering detection; cross-format goldens exist for normal, dense, long-text, multilingual, held, and filed states and every affected PDF page and XLSX sheet was inspected; the offline verifier reconstructs a sampled claim and byte set from the package in a clean directory; the backend suite, Ruff, the release gates, and the frontend gates pass and are quoted; the progress row and enterprise-task-10-report.md are written; a draft pull request to main is open. The blind rubric review by two analysts and an external-stakeholder reviewer is candidate-only work: record its inputs as prepared and its result as BLOCKED EXTERNAL.
```

### ER-G6: Task 11, the qualification corpus and the live matrix harness

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: blockers ETR-B05 and ETR-B11 close only when one binding runs six pathways at both depths against answer-keyed packs with three cold repetitions per cell, and nothing in the repository can run that matrix yet. This is Task 11 of docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 11, Phase 2 of ENTERPRISE_READINESS_PLAN.md including the corpus coverage decision of 2026-08-31, the C01 to C22 pack table, and the MOD-001 to MOD-025 checks before starting.

Goal: on this branch from main, versioned corpus manifests describe C01 to C22 (Carnival shared for C01, C17, C18, and C19; one licensed market-marks pack for C20; one 20 to 30 document stressed or restructuring pack for C21 built from the official issuer materials the plan names; one question-specific pack for C22; C02 to C16 as small composable synthetic fixtures), each with retained filename, provenance, licence class, SHA-256, document type, period, supersession status, expected facts, conflicts, forbidden conclusions, route expectation, and answer-key version; and one parameterized qualification harness runs binding × six pathways × supported depths × required positive and negative packs × cold repetitions through the ordinary provider path, scores facts, citation correctness, unsupported claims, conflict handling, document use, model effects, refusal behavior, latency, and budget against the answer keys, binds every result to model, provider, adapter, policy, corpus digest, build, date, expiry, and reviewer, and fails closed.

Binding constraints: network retrieval stays outside pytest and the fetch step verifies every digest; no licensed byte enters git; no continue-on-error, skip-on-missing, or unsigned answer key; a refusal-only cell never proves a pathway works; one failed required cell makes the binding unqualified; scripted providers remain host controls and are never labelled live qualification; the protected workflow job uses the existing CI conventions and pinned actions; prompt-injection pack C12 exercises the exact live provider path when credentials exist and asserts that document instructions change no tool, prompt, route, budget, authority, or output.

Done means: the harness runs end to end against the Carnival pack with a local answer-keyed provider as orchestration proof and exits non-zero when a required byte, credential, answer key, or cell is missing; ledger rows map every MOD check to the harness; the protected workflow exists and is dispatchable; the backend suite, Ruff, and the release gates pass and are quoted; the progress row and enterprise-task-11-report.md are written; a draft pull request to main is open. Licensed marks, the stressed pack bytes, the research pack, analyst-approved answer keys, and provider credentials are external inputs: list each as BLOCKED EXTERNAL with the owner, the artifact needed, and where it goes, so the ER-L3 loop can run the live matrix the moment they exist.
```

### ER-G7: Task 12a, database truth, simulations, single instance, and recovery

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: blockers ETR-B07 and ETR-B10 and gate G6. Concurrency evidence is still SQLite thread races, two-connection PostgreSQL coverage is deferred in SPEC_RECONCILIATION.md, nothing enforces the single application instance, and the restore drill exposed fresh-schema, vault-discovery, and cross-store snapshot defects. This is the data-truth half of Task 12 in docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md (steps 1, 2, and 5); read Task 12, Phase 5 of ENTERPRISE_READINESS_PLAN.md, and the SIM-001 to SIM-030 table before starting. A PostgreSQL 17 QA container exists locally and the CI PostgreSQL service is digest-pinned; reuse both.

Goal: on this branch from main, every governed race listed in Phase 5 (duplicate and concurrent ingestion, source-set allocation and withdrawal, assumption and model revision and sign-off, run acceptance, event-sequence allocation, budget reserve and reconcile, draft save and freeze, opinion sign-off and filing) has a test on two independent PostgreSQL connections with exactly one winner and a typed loser; SIM-001 to SIM-030 each map to a retained simulation built on the existing kill-after-module, commit-gap, unresolved-spend, stale-worker, renderer-tamper, and route-injection seams, with new hooks only for the faults those seams cannot express; a second application instance fails startup on an exclusive lock over the durable checkpoint location before serving traffic; and backup, restore, paused and in-flight recovery, and reset pass under active writes on the enterprise image.

Binding constraints: execution stays durable and exactly-once (invariant 6) and budgets fail closed (invariant 8); an operation whose provider spend or publication result is unknown is never retried; no distributed checkpointer, shared fleet, or high-availability control plane; SQLite races and compiled FOR UPDATE checks stay as fast mechanism tests and are never labelled PostgreSQL proof; after every simulation the assertion covers domain data, checkpoints, files, budget, events, audit, and user-visible status, before and after restart, not only the HTTP result; storage and lifecycle code changes only where a failing simulation proves a defect; no first-party ResourceWarning survives.

Done means: the two-connection target runs in CI against the pinned container and locally against the QA container, with the deferral removed from SPEC_RECONCILIATION.md only on evidence; every SIM row records injected fault, expected outcome, actual outcome, and post-restart state; the exclusive lock is proven by a second process; Compose creates exactly one app and one worker and the environment manifest records the ceiling; the three restore-drill defects have regression tests; the backend suite, Ruff, and the release gates pass and are quoted; the progress row and enterprise-task-12a-report.md are written; a draft pull request to main is open. The eight-hour soak and saturation faults are candidate-only work and are not run here.
```

### ER-G8: Task 12b, security, identity, browsers, accessibility, and the capacity harness

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble").

Why: blocker ETR-B06 and gates G1, G5, and G9. The security audit covers unauthenticated and spoofed-role checks only, the AI pull-request review is unexecuted and unsafe as configured, browser evidence is Chromium only, and no harness can drive the declared enterprise profile. This is the perimeter half of Task 12 in docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md (steps 3 and 4); read Task 12, Phase 6 of ENTERPRISE_READINESS_PLAN.md, and the IAM, SEC, WEB, and PERF check families before starting.

Goal: on this branch from main, run_sec_audit.py discovers every route from OpenAPI and tests the full outsider, reader, analyst, approver, administrator, removed-member, and forged-identity matrix including cross-case identifiers in bodies and commit-time standing rechecks; the AI pull-request review is replaced by a protected, read-only recorded review whose non-vacuity is testable and which can expose no secret or write token to untrusted diff text; SAST, dependency, secret, workflow, container, and image scans retain non-empty results bound to the image digest with an SBOM; the Playwright journey is parameterized for Chromium, Firefox, and WebKit with traces and screenshots on failure; WCAG 2.1 AA automation covers empty, loading, populated, error, refusal, review, and filed states; and a checked-in capacity harness can run the declared profile (25 subjects, 20 active jobs, four streams and two previews per subject, 300 requests per subject per minute, 100 cases of 100 documents, 25 MB sources, 32 MB requests) and the below, at, and above checks for every admission and size limit.

Binding constraints: production derives role from OIDC groups only and client role headers never escalate; unknown and unauthorized resources return the same 404; frontend role visibility is never authorization; a green scanner that scanned nothing fails, as the bandit Python pin in CLAUDE.md already illustrates; third-party actions and installers are pinned by digest; no second browser framework; nothing here claims production capacity or availability; limit-boundary tests stay in development and the full declared profile, mixed workload, and soak run only as candidate evidence.

Done means: IAM-001 to IAM-020, SEC-001 to SEC-030, WEB-001 to WEB-015, and PERF-001 to PERF-012 each map to a retained check or a candidate-only harness invocation; the three-browser journey passes locally for all six documents-only pathways; above-limit work refuses before consuming provider or worker capacity; the backend suite, Ruff, the release gates, and the frontend gates pass and are quoted; the progress row and enterprise-task-12b-report.md are written; a draft pull request to main is open. The enterprise identity provider, test accounts, malware scanner, egress allowlist, and authorized penetration test are external inputs: list each as BLOCKED EXTERNAL with what is needed.
```

### ER-G9: Task 13, freeze the candidate and run the automated gates

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble"). This task runs in the primary checkout on main and against the real Compose stack; it adds no product code.

Why: every gate in ENTERPRISE_TESTING_READINESS.md must pass on one commit, image, binding, corpus, and environment. Nothing that runs before the candidate is frozen counts, so freezing comes first and every automated gate then runs against the frozen identities. This is the first half of Task 13 in docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 13 and Phase 7 of ENTERPRISE_READINESS_PLAN.md before starting. The live matrix (ER-L3) and the soak watch (ER-L4) run as separate loops after this task starts the stack and the soak.

Goal: one immutable candidate is frozen and recorded in a candidate manifest (commit, clean-tree result, tag, application and worker image digests built once from that commit, dependency locks, SBOM, runtime versions, one-app-one-worker topology, corpus manifest and answer-key digests, the qualified binding and its qualification record, methodology build id, environment manifest, and reviewer roster); the Compose stack runs from those images; every automated gate that needs no live provider and no eight hours runs from checked-in scripts or workflow steps against those identities with its result retained under the candidate identity (deterministic CI, corpus host controls, two-connection PostgreSQL races, the mapped SIM-001 to SIM-030 evidence, three-browser journeys, accessibility, security scans, limit boundaries, backup and restore, reset, single-instance enforcement); and the eight-hour soak is started from the capacity harness with its pre-soak baseline recorded, so ER-L4 can watch it.

Binding constraints: evidence from different commits, images, corpus versions, model policies, or environments is never combined; any code, corpus, model-policy, image, methodology, or environment change after freezing creates a new candidate, and you say so rather than patching; no core gate is waived; a typed refusal the answer key requires is a pass and a missing test is never a refusal; nothing is marked from historical prose, a skipped or not-run check, or scripted-model output; the terminal claim is enterprise-testing ready for one controlled candidate, never production ready.

Done means: the candidate manifest exists and is hashed; each automated gate above has a retained artifact and a quoted result under the candidate identity, or a BLOCKED EXTERNAL entry with the owner and the artifact needed; the stack is up on the frozen images and the soak is running with its baseline recorded; the report lists exactly what ER-L3, ER-L4, the human reviewers (REV-001 to REV-015, each prepared with build digest, corpus version, and the questions to answer), and ER-G10 still owe before the package can be signed.
```

### ER-G10: Task 13, assemble and verify the evidence package

```text
Follow the STANDING PREAMBLE in docs/superpowers/plans/2026-09-02-enterprise-readiness-prompt-series.md (section "Standing preamble"). This task runs in the primary checkout on main at the candidate tag; it adds no product code and changes no candidate identity.

Why: the enterprise test owner signs one hashed package, and the release exit criteria in ENTERPRISE_TESTING_READINESS.md allow no unresolved required skip, waiver, missing artifact, or unknown status. ER-G9 froze the candidate and ran the automated gates; the ER-L3 and ER-L4 loops have finished and logged their results under .superpowers/sdd/loops/; the reviewer records have been returned or are outstanding. This is the second half of Task 13 in docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md; read Task 13, Phase 7 of ENTERPRISE_READINESS_PLAN.md, "Produce a release evidence package", and "Enforce release exit criteria" before starting.

Goal: the six golden journeys run against the frozen stack from documents through source-disposition review, execution, model creation or update, deliverable review, analyst opinion sign-off, separate approval, exact filed download with filing receipt, and offline audit verification, and their artifacts are retained; the evidence package listed in the standard is assembled from the retained candidate artifacts, the loop logs, and the reviewer records, verified object by object on a separate directory with the offline verifier, and hashed; and docs/QUALITY_LEDGER.csv, docs/QUALITY_DEFECTS.csv, SPEC_RECONCILIATION.md, and the blocker table in ENTERPRISE_TESTING_READINESS.md are updated only from retained candidate evidence.

Binding constraints: nothing is combined across candidates; a gate, cell, simulation, review, or blocker without a retained result is recorded as open, never inferred; a missing reviewer record stays missing until the reviewer returns it; the package holds no secret, prompt, hidden reasoning, provider error body, or unauthorized source text; the terminal claim is enterprise-testing ready for one controlled candidate and nothing more.

Done means: the package manifest lists every G0 to G9 gate with its artifact and result, every one of the 340 checks and 30 simulations with its retained result or its open owner, every blocker with its closing evidence, and every excluded production requirement and approved test-only limitation; the package digest is recorded; the final report opens with whether the candidate can be signed, then the exact commands, the digest, and the open items with owners. If anything required is missing, the candidate is not ready and the report says so in its first sentence.
```

## Loop prompts for Claude Opus 5

Loops run with the `/loop` skill in a session whose model is `claude-opus-5`. Give an explicit interval for predictable cost; leave it out only for `ER-L2`, where the pull request's own events are the wake signal. Each loop keeps an append-only log under `.superpowers/sdd/loops/` so a tick can tell what changed since the last one after compaction. To reuse a loop without pasting it, save its text as `.claude/commands/<name>.md` and run `/loop 20m /<name>`.

### ER-L1: branch health

Run as `/loop 20m` followed by the text below, in the `verify-enterprise` worktree. Replace `<REF>` with the branch or tag to watch (`codex/enterprise-readiness-review` until it merges, then `main`, then the candidate tag); stop and restart the loop to change it.

```text
You are the verification loop for <REF>. Work only in this detached verify worktree; no other session edits it, and you edit nothing but the log at .superpowers/sdd/loops/branch-health.md.

Each tick: run git fetch --all --prune, then git checkout --detach <REF>. If the head SHA equals the one recorded in the log's last entry, append one line saying so and stop. Otherwise run, in order, each with caos/server/.venv/bin/python: -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor; -m pytest caos/tests -q -p no:cacheprovider; run_sec_audit.py; docs/quality_ledger_coverage.py; then from caos/frontend, npm run lint, npx tsc --noEmit, npm run test:unit. Do not use `uv run`; the interpreter already exists.

Append one entry per tick: timestamp, head SHA, each command with its summary line, and for any red the failing test name, the first assertion message, and your diagnosis to root cause (bisect between the last green head and this one when the cause is not visible in the diff). Re-run a failure once before calling it red; a failure that passes on re-run is flaky and is logged as flaky, never as green. Do not edit source, tests, or docs, do not commit, and do not touch any other worktree: another session owns the branch and will read your log. Send a push notification only when the state changes (green to red, red to green, a collection error, or a flaky test) with the head SHA and the failing name; otherwise say nothing beyond the log entry.
```

### ER-L2: pull-request babysit

Run as `/loop` with no interval, followed by the text below, in the worktree that owns the branch, and only when no goal session is active there.

```text
Keep the open pull request for the current branch ready to merge pending human review only. Find it with gh pr view; if none exists, say so and stop. Each tick: check CI status, unresolved review threads, and whether the branch has fallen behind main. Diagnose a failing job from its logs before acting: re-enqueue only a run whose failure is flaky-shaped (timeout, runner lost, transient network); reproduce a real failure locally with caos/server/.venv/bin/python -m pytest on the failing test, fix the smallest thing that makes it pass without weakening any assertion, run Ruff and the touched test files, and commit with the /commit skill. Address each review thread with a change or a reply, then resolve it. Rebase onto main (never merge) when the branch is behind, resolving conflicts with the resolving-merge-conflicts skill; before every push, check that nobody else pushed to the branch since you fetched. Never force-push over someone else's commits, never edit the vendored bundle, and never mark a gate green that you did not run. Log each tick to .superpowers/sdd/loops/pr-babysit.md with the PR number, head SHA, what you found, and what you did. When CI is green, threads are clear, and the branch is current, send one push notification saying the PR is ready for review and merge, and stop the loop; do not merge it yourself.
```

### ER-L3: live qualification matrix

Run as `/loop 45m` followed by the text below, in the primary checkout at the candidate tag, in a shell where the protected provider credentials and the corpus location are exported. Requires the harness from `ER-G6`.

```text
Advance the enterprise qualification matrix built by Task 11 (see .superpowers/sdd/enterprise-task-11-report.md for the harness command and the evidence location). Each tick: read .superpowers/sdd/loops/live-matrix.md to find the next required cell (binding × pathway × depth × pack × repetition) without three retained results, run exactly that cell through the harness with a cold process, and store its scored result in the evidence location under the candidate identity. A cell whose bytes, answer key, or credentials are missing is logged as BLOCKED EXTERNAL with what is missing and is never skipped, averaged, or marked passed; a refusal is a pass only when the pack's answer key designates refusal. Log every run with the cell, the command, the scores, the budget spent, and the pass or fail verdict. Stop the loop and send a push notification when every required cell has three retained results, when one cell has failed twice, or when the candidate identity changes underneath you; otherwise say nothing beyond the log entry. Never modify the harness, the answer keys, or the corpus manifest; if the harness is wrong, log it as a finding and stop.
```

### ER-L4: soak and capacity watch

Run as `/loop 30m` followed by the text below, in the primary checkout with the Compose stack up, after starting the PERF-013 soak from the checked-in capacity harness (`ER-G8`).

```text
Watch the running eight-hour soak against the candidate Compose stack and record whether it stays inside the declared profile. Each tick: sample CPU, memory, database connections, open file handles, active jobs and permits, checkpoint size, vault growth, export storage, provider usage, success and refusal counts, and error classifications from the harness output, the containers, and the database, and append them with a timestamp to .superpowers/sdd/loops/soak-watch.md. Compare each value with the previous ticks: a monotonically growing count of connections, handles, jobs, permits, or orphan rows, a cross-case event in any stream, or a fault that produced an untyped error is a finding; log it with the evidence and send a push notification. Do not restart, scale, or reconfigure anything: the soak is evidence, and touching it invalidates the run. When the harness reports the soak complete, run the post-soak six documents-only journeys from the harness, compare authorities, model hashes, filed bytes, and offline reconstruction against the pre-soak baseline the harness recorded, log the comparison, send one push notification with the verdict, and stop the loop.
```

## How the Fable 5.1 guidance shaped these prompts

- **Goal and reason over steps**: each goal prompt gives the outcome, who it is for, and what it enables (the "give the reason" pattern), then binding constraints and a definition of done. The plan's numbered implementation steps are referenced by task number rather than restated, because prescriptive scaffolding written for earlier models lowers Fable 5.1's output quality.
- **Autonomy and scope blocks**: the standing preamble carries Anthropic's autonomy block with its opening sentence unchanged, the delivering-work block, and the changes-and-tests block that cuts unrequested fixes and committed test sprawl.
- **Grounded progress**: every prompt requires the command and its output beside any pass claim; the preamble carries the audit-against-tool-results instruction that removes fabricated status reports on long runs.
- **Tool batching**: the preamble ends the tool-use guidance with the one-sentence batching nudge, since coding loops otherwise issue one call per turn.
- **A memory surface**: the per-task report in `.superpowers/sdd/` is named as the model's memory across compaction and is written as work proceeds, which is where Fable 5.1 performs best on long runs.
- **Delegation**: verification and fresh-context review go to subagents that run while the lead keeps working.
- **Assessment mode**: `ER-G0` states that the deliverable is the assessment, so the model reports and stops instead of fixing.
- **Effort**: goals stay at `xhigh` because they are long-horizon coding with the full spec up front; the review prompt asks the model to reason about what is wrong and write the report once, which is the recommended shape for long deliverables at high effort.
- **Loops on Opus**: a tick is a fixed command sequence plus a diff against the last log entry, work that does not repay Fable's effort or price; the loop prompts state boundaries explicitly (edit nothing, never mark green what was not run) because that is where a cheaper autonomous model needs the fence.
