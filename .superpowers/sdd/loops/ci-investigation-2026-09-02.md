# CI investigation — 2026-09-02

Asked to find the cause of the repository's CI issues. There is not one cause.
There are **four independent failure modes**: one already fixed (in two commits,
for two manifestations of a single root cause), one open and tracked, one that
had never been recorded because it disguises itself as a routine cancellation,
and one that is a process pattern rather than a defect.

Evidence is workflow-run logs and a local reproduction; every claim below names
the run or job it came from. Where a reading turned out to be wrong under a
larger sample, the correction is kept rather than the first impression.

## Summary

| # | Failure | Job | Status |
|---|---------|-----|--------|
| A | Unicode PDF path: missing shaper, then font ligatures | `Server` (both legs) | **Fixed and confirmed green** — `4b2195e`, `1013d47` |
| B | Dirty-draft focus-restoration race | `Browser` | **Open** — issue #38, red on main now |
| C | Suite passes, process never exits, job burns to the 360-min cap | `Server` | **Root-caused and fixed** — teardown race in `Engine._drain_tasks` |
| D | Consecutive pushes to main cancel their own CI | all | **Open, process** |

The recurring theme in A and C is the same: **CI does not fail loudly enough**.
A shipped a runtime dependency CI never had; C spends six hours looking like a
cancellation.

---

## A. The Unicode PDF path — fixed, but the interesting part is why it took two commits

`346748f` added a Unicode PDF path that shells out to `pango-view`.
`caos/deploy/Dockerfile` installs `fonts-noto-cjk` and `pango1.0-tools`; the CI
`server` job did not. So the suite was exercising a **thinner environment than
the one that ships**, and the gap was invisible on a developer Mac where Homebrew
supplies `pango-view`.

It surfaced twice, as two different red states with one root cause:

1. **Run 33630627451** (`a28c68c`), both matrix legs:
   `test_canonical_document_is_the_only_cross_format_export_source`
   → `ValueError: PDF_UNICODE_RENDERER_UNAVAILABLE` — the binary was absent.
   Fixed by `4b2195e`, which installs the two packages in CI.

2. **Run 33644890370** (`e7e42ea`), both matrix legs — installing the shaper
   *unmasked* the next layer:

   ```
   At index 7 diff: 'Risks, Catalysts, and Falsiﬁers' != 'Risks, Catalysts, and Falsifiers'
   ```

   The Linux sans font shapes `fi` into U+FB01, `pypdf` extracts the ligature, so
   the shipped PDF text no longer equals the canonical document byte for byte and
   the word is not searchable. Fixed by `1013d47` (Pango markup with
   `liga/clig/dlig` off).

**Confirmed closed.** Both fixes are in `main` as of `91d9038`, and run
33649802750 finished green on both server legs — 3.14 in 24 m 42 s (job
100313637508), 3.12 in 31 m 28 s (job 100313637515). Both processes exited
cleanly, so this run is also a negative observation for finding C.

**The durable lesson is not the ligature.** It is that a new *runtime* dependency
landed with no gate asserting CI and the image agree. `verify_image_resources.py`
checks resources inside the image; nothing checks that the test environment has
what the image has. Until something does, the next runtime binary added to the
Dockerfile will repeat this exactly.

## B. The dirty-draft focus-restoration race — open, red on main right now

`Browser — workbench journey and accessibility` →
`page.waitForFunction: Timeout 30000ms exceeded` at
`caos/frontend/scripts/workbench-smoke.mjs:1099` (`:1095` before the merge shifted
the line). The wait expects focus back on the `Revenue growth, FY2025, BASE`
input after Escape dismisses the discard-draft dialog raised by `history.back()`.

**Update 2026-09-02, later the same day: the previously recorded root cause is
wrong, and so is the mechanism detail this section originally added.** Both are
kept below, struck through, because the correction is the useful part. See
`focus-race-findings.md` for the measurement; the short version is in the next
subsection.

`DraftDiscardDialog.dismiss()` (`Workspace.tsx:1187`) restores focus through three
strategies in order — the captured node, `getElementById(trigger.id)`, then an
`aria-label` match — retrying 10×/50 ms and **returning on first success**:

```js
if (focus(trigger)) return;              // <- wins on a node React is about to discard
if (trigger?.id) { ... }
const label = trigger?.getAttribute("aria-label"); ...
```

The `aria-label` fallback is exactly the one that would find the remounted input.
It is unreachable in the losing interleaving: `ForecastScrubber`'s React key
embeds `draftGeneration` (`model/ModelBuilder.tsx:750`,
`` key={`${assumptionKey(row)}:${draftGeneration}`} ``), so a generation bump
unmounts and remounts every scrubber. When `focus(trigger)` succeeds on the
*outgoing* node, `restore()` returns satisfied, React then discards that node,
focus falls to `<body>`, and nothing is left watching.

### Corrected root cause — focus is already wrong before the dialog opens

An instrumented copy of the smoke (focusin + MutationObserver timeline, plus a
snapshot of `document.activeElement` immediately before `history.back()`) run 12
times against isolated servers on stock code:

| | remount before `history.back()` | focus before `history.back()` | result |
|---|---|---|---|
| PASS (8) | no | `Revenue growth, FY2025, BASE` | pass |
| FAIL (4) | **yes** | **`Open command palette`** | fail |

12/12, no exceptions. Every failing run enters the navigation with focus already
on the command-palette button from an earlier dialog. `DraftDiscardDialog`
faithfully restores what was focused; what was focused was already wrong. And
the `ForecastScrubber` remount — named as the cause in `focus-race-findings.md`
and issue #38 — is **protective**: it is present in all 8 passes, because a
remount during the dialog forces the `aria-label` fallback onto the correct
replacement node. It only harms when it lands *before* `history.back()`, where it
strands focus and lets the workspace repair effect restore a stale trigger.

A candidate fix (drop the `previousFocusedRef` inversion in
`guardBrowserHistory`'s trigger ternary, use the live `activeElement`) was
applied, rebuilt and run 14 times: 13 passed and the single no-remount run
**failed identically**. Refuted — by then focus is already lost. Recorded so
nobody spends the afternoon on it again.

The two unverified directions worth trying are in `focus-race-findings.md`.

### Correction on frequency — it is intermittent, not deterministic

Four consecutive CI browser jobs failed at this assertion (runs 33609642643,
33630627451, 33644890370, 33649802750), the last green being run 33608798822 on
2026-09-02 08:27. That pattern initially read as "now deterministic", and the
first two local iterations agreed. **A larger sample does not support that.**

Seven local iterations against a purpose-built harness (fresh server and data dir
per run, isolated port, no rebuild mid-flight — the traps
`focus-race-findings.md` warns about):

| Outcome | Count |
|---|---|
| Fail at `:1099` (the focus assertion) | 3 |
| Pass | 2 |
| Fail at `:1517` (`discardDraftDialog().waitFor()`, Report Studio Back) | 1 |
| Fail at `:258` (DCL 388 ms > 250 ms budget — local hardware, not a defect) | 1 |

So: a genuine race currently losing often, not a deterministic break. Note that
`:1517` is the **same discard-dialog machinery at a different call site**, which
says the flakiness belongs to the dirty-draft/discard-dialog subsystem as a whole
rather than to one assertion.

Caveat on the harness: local Chromium is 141.0.7390.37 against CI's 151, and the
DCL failure shows the smoke is also sensitive to machine speed. The `:1099`
signal is consistent across both environments; the timing-budget one is not
evidence of anything.

The recommended fix is unchanged from `focus-race-findings.md`: give focus
restoration **one owner** instead of adding a fourth referee between the two
existing systems.

## C. The suite passes and the job still burns six hours — previously unrecorded

This is the finding worth acting on, because nothing in the repo describes it and
its symptom is indistinguishable from a routine cancellation.

On PR #25 (run 33385731195, job 99467792821, `Server 3.12`) the backend suite
**completed successfully**:

```
556 passed, 12 skipped, 231 warnings in 147.96s (0:02:27)     11:13:16Z
##[error]The operation was canceled.                           17:10:40Z
...
Terminate orphan process: pid (2427) (python)
```

pytest printed its summary at 11:13:16 and the step sat there until **17:10:40 —
exactly 360 minutes**, GitHub's default job timeout. The process never exited.
Both matrix legs did this, and the earlier run 33264033292 on the same PR shows
the identical ~6-hour signature.

Cost: ~12 runner-hours per occurrence, and the run is reported as `cancelled`,
which is the same word `cancel-in-progress` produces (finding D) — so it reads as
routine and nobody looks.

Immediately before the summary the log carries:

```
aiosqlite/core.py:102: ResourceWarning: <aiosqlite.core.Connection object ...>
was deleted before being closed.
```

aiosqlite runs each connection on its own non-daemon `threading.Thread`, and
CPython joins non-daemon threads at interpreter shutdown — an unclosed connection
is therefore a coherent mechanism for "tests finished, interpreter will not
exit", and the `Terminate orphan process: (python)` line is consistent with it.
That was recorded as the leading hypothesis. **It is now the confirmed root
cause, and the connection is not leaked by accident — `aclose()` is aborted
before it ever closes the savers.** See the next subsection.

Two things follow, independent of which connection is at fault:

- The `server` job had **no `timeout-minutes`**, so it inherited the 360-minute
  default; `deploy-assets`, `image`, `security`, `nightly.operational` and
  `security-review` were the same. **Fixed** — see recommendation 1. This bounds
  the symptom; it does not fix the leak.
- PR #25 has therefore **never had a completed server run** since it was opened on
  2026-08-29. Dependency PRs are not being verified at all.

### Root cause found: a teardown race in `Engine._drain_tasks`

The lead came from an unrelated CI failure on PR #39
(run 33670291048, `Server 3.12`):

```
FAILED caos/tests/spec/test_runs_spec.py::test_engine_close_drains_foreign_loop_continuation
  - RuntimeError: cannot close a task without a runnable owner loop
```

`Engine._drain_tasks` cancels a continuation that lives on a *foreign* event
loop, then re-checks that the loop is still runnable before waiting on it:

```python
if cancel:
    owner.call_soon_threadsafe(task.cancel)     # ends the foreign loop
...
owner.call_soon_threadsafe(wait_on_owner)
if not self._owner_loop_runnable(owner, loop):  # ...and then complains it ended
    raise RuntimeError("cannot close a task without a runnable owner loop")
```

**The cancel is what ends the owner loop.** Once the task is cancelled its
`run_until_complete` returns and the thread closes the loop, so "the loop is
gone" and "the task finished" are the same event observed from two threads. The
window between issuing the cancel and re-checking liveness is exactly the window
in which the loop legitimately dies, which is why it shows up on contended CI
runners and not on an idle laptop.

Two landing points, same race:

- loop closes **before** `call_soon_threadsafe(wait_on_owner)` → `RuntimeError:
  Event loop is closed`
- loop closes **between** that and the re-check → `RuntimeError: cannot close a
  task without a runnable owner loop` (what CI hit)

**Reproduced twice, locally, on stock code:**

| method | result |
|---|---|
| the CI test run 60× unmodified | **1 failure**, the exact CI error |
| window widened 150 ms (slowing the first statement after the cancel; no logic changed) | **fails every time**, with `aclose outcome='RuntimeError: Event loop is closed'`, `cancelled=True`, `engine._closed=False` |

`cancelled=True` with `engine._closed=False` is the whole bug in one line: the
drain **succeeded** — the task really was cancelled — and the code reported that
success as a failure.

### Why this is finding C

`aclose()` drains continuations *before* it closes savers, in the same `try`:

```python
if continuations:
    await self._drain_tasks(continuations, cancel=True)   # <- raises here
...
for key, saver in savers:
    await saver.conn.close()                              # <- never reached
```

`self._savers` holds `AsyncSqliteSaver` instances wrapping `aiosqlite.connect`
connections, and **aiosqlite runs each connection on a non-daemon thread**. So
the chain is:

1. the drain race makes `aclose()` raise,
2. the raise skips every `saver.conn.close()` and never sets `_closed`,
3. the aiosqlite connections stay open on non-daemon threads,
4. CPython joins non-daemon threads at interpreter shutdown, so the process
   hangs after pytest has already printed its summary,
5. the job burns to the 360-minute cap and reports as `cancelled`.

That is finding C exactly, including the unclosed-`aiosqlite` ResourceWarning
and the `Terminate orphan process: (python)` line.

### The fix

A task that has finished is a drained task. `_drain_tasks` now treats "the owner
loop is gone" as a failure **only while the task is still pending**, and the two
`call_soon_threadsafe` calls that can race the loop's close are guarded the same
way. The genuine error is preserved: `test_engine_close_refuses_owner_loop_stopped_during_waiter_handoff`
stops the owner loop while its task is still pending and still expects the
`RuntimeError`, and it passes.

| check | before | after |
|---|---|---|
| CI test, 60 / 200 runs | 1 failure in 60 | **0 failures in 200** |
| widened-window probe | raises, `_closed=False` | **clean, `_closed=True`** |
| `caos/tests/spec/test_runs_spec.py` | — | 77 passed |
| suite minus corpus | — | see the commit |

Landed in `caos/server/caos/engine/runtime.py`. Note what this does **not**
prove: no CI job has yet been observed hanging *and then* recovering under the
fix, because the hang is rare. The mechanism is evidenced end to end and the
race is closed; the six-hour symptom should not recur, and the 45-minute cap
from recommendation 1 now bounds it if some other path produces one.

## D. Consecutive pushes to main cancel their own CI

Of the last 30 CI runs, **15 were cancelled — 13 of them direct pushes to main**.
On 2026-09-01 between 11:55 and 13:18 there were ~14 consecutive pushes to main
(runs 96–109, `fix(frontend): …`, `test(frontend): …`), each cancelling the
previous run under `concurrency: ci-${{ github.ref }}` with
`cancel-in-progress: true`.

Nothing is broken here — the configuration does what it says. The consequence is
that main went through that window with **no completed CI verification at all**,
and the cancellations camouflage finding C.

## Observation: the suite outgrew its budgets

The merge of PR #37 changed the shape of the pipeline:

| | Before (run 33609642643) | After (run 33644890370) | On main, green (run 33649802750) |
|---|---|---|---|
| Server 3.12 backend suite | 4 m 24 s | 20 m 57 s | **31 m 28 s** |
| Server 3.14 backend suite | 8 m 13 s | 27 m 32 s | 24 m 42 s |
| Tests | 655 passed, 2 skipped | 946 passed, 2 skipped | — |

Tests +45 %, wall time +235 %. The 31 m 28 s leg is the important number: it is
the *smaller* matrix leg (no corpus) on a slower runner, so runner variance alone
spans 25–31 minutes for work nightly has to beat. That is expected — every module is now
provider-backed and calculations replay — and it is not a defect. But it has a
consequence nobody has adjusted for:

**`nightly.yml`'s `regression` job has `timeout-minutes: 30` and runs
`CORPUS_FULL=1`**, which classifies every corpus document and runs every
executable route — strictly *more* work than CI's subset, which alone now takes
27 m 32 s. The same job then also runs lint, the frontend suite, a build,
Playwright install, the workbench journey and the accessibility sweep. The last
nightly (run 33618906258, pre-merge) took 14 m 25 s end to end.

**Prediction: the next scheduled nightly (06:00 UTC) will exceed its 30-minute
cap.** A single observed server leg on main already took 31 m 28 s doing *less*
than nightly does. This is the one finding here not yet observable in a log, so
it should be checked against tomorrow's run rather than assumed.

## Recommendations, in the order I would do them

1. ~~**Cap the unguarded jobs.**~~ **Done.** Every job in all three workflows
   now carries `timeout-minutes`: `server` 45, `image` 20, `security` 15,
   `deploy-assets` 10, `nightly.operational` 30, `security-review` 30. Finding
   C now costs 45 minutes and reports as a timeout instead of costing six hours
   and reporting as `cancelled`.
2. ~~**Raise nightly's cap.**~~ **Done.** `nightly.regression` 30 → 90. It runs
   `CORPUS_FULL=1` plus lint, frontend, build, Playwright and both browser
   sweeps, against a CI subset that alone measured 24m42s/31m28s. Deliberately
   loose — a scheduled job pays nothing for headroom, and too tight a cap is
   the failure being fixed.
3. **Fix the focus race properly** (issue #38) — one owner for focus
   restoration. Not a fourth referee.
4. **Root-cause the non-exit** — find the unclosed aiosqlite connection. With
   (1) in place this stops being urgent, but it is still a real leak.
5. **Gate CI-vs-image parity** so the next runtime binary added to the Dockerfile
   cannot land untested, as `pango-view` did.

## What was checked and deliberately left alone

- No fix was pushed for B: `focus-race-findings.md` records three attempts that
  failed and warns that an unverified fix is worse than none. The correct fix is
  architectural and belongs to a change with its own verification budget.
- No CI policy was changed. The timeouts in (1) and (2) are the decision owner's
  call on cost and cadence, not a documentation chore.
- PR #3 and PR #25 (both Dependabot) were read but not touched.
