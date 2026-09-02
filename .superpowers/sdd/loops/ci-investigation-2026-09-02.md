# CI investigation — 2026-09-02

Asked to find the cause of the repository's CI issues. There is not one cause.
There are **four independent failure modes**, two of them already fixed, one open
and tracked, and one that had never been recorded because it disguises itself as
a routine cancellation.

Evidence is workflow-run logs and a local reproduction; every claim below names
the run or job it came from. Where a reading turned out to be wrong under a
larger sample, the correction is kept rather than the first impression.

## Summary

| # | Failure | Job | Status |
|---|---------|-----|--------|
| A | Unicode PDF path: missing shaper, then font ligatures | `Server` (both legs) | **Fixed** — `4b2195e`, `1013d47` |
| B | Dirty-draft focus-restoration race | `Browser` | **Open** — issue #38, red on main now |
| C | Suite passes, process never exits, job burns to the 360-min cap | `Server` | **Open, previously unrecorded** |
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

Both fixes are in `main` as of `91d9038`. The confirming run (33649802750) was
still executing its server legs when this was written, so A is recorded as fixed
on the strength of the two commits and the author's Debian-container
verification, not on a green run on main. **Check that run before treating A as
closed.**

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

Root cause was already established in `focus-race-findings.md` and issue #38, and
this investigation confirms it rather than restating it. One mechanism detail is
worth adding, because it explains why the existing fallbacks do not save the case.

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
**Stated as the leading hypothesis, not as proven**: the proven part is that the
suite passed and the process did not exit.

Two things follow, independent of which connection is at fault:

- The `server` job has **no `timeout-minutes`**, so it inherits the 360-minute
  default. `frontend` (15) and `browser` (20) have one; `server`, `deploy-assets`,
  `image` and `security` do not. A cap of ~40 min would turn six wasted hours
  into a fast, clearly-labelled timeout.
- PR #25 has therefore **never had a completed server run** since it was opened on
  2026-08-29. Dependency PRs are not being verified at all.

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

| | Before (run 33609642643) | After (run 33644890370) |
|---|---|---|
| Server 3.12 backend suite | 4 m 24 s | 20 m 57 s |
| Server 3.14 backend suite | 8 m 13 s | 27 m 32 s |
| Tests | 655 passed, 2 skipped | 946 passed, 2 skipped |

Tests +45 %, wall time +235 %. That is expected — every module is now
provider-backed and calculations replay — and it is not a defect. But it has a
consequence nobody has adjusted for:

**`nightly.yml`'s `regression` job has `timeout-minutes: 30` and runs
`CORPUS_FULL=1`**, which classifies every corpus document and runs every
executable route — strictly *more* work than CI's subset, which alone now takes
27 m 32 s. The same job then also runs lint, the frontend suite, a build,
Playwright install, the workbench journey and the accessibility sweep. The last
nightly (run 33618906258, pre-merge) took 14 m 25 s end to end.

**Prediction: the next scheduled nightly (06:00 UTC) will exceed its 30-minute
cap.** This is the one finding here that is not yet observable in a log, and it
should be checked tomorrow rather than assumed.

## Recommendations, in the order I would do them

1. **Cap the unguarded jobs.** `timeout-minutes` on `server` (~40),
   `deploy-assets`, `image`, `security`. Cheapest possible change; converts
   finding C from six silent hours into a labelled failure.
2. **Raise nightly's cap** to match the suite's real runtime, or split the
   regression job. Do this before 06:00 UTC.
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
