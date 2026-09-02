# Workbench smoke: dirty-draft focus-restoration race

**Tracked as https://github.com/EricMG13/CAOS-LangMVP/issues/38** — that issue
carries the same analysis in public form. Keep the two in step: if this file
gains anything a fixer would need, say so on the issue.

Investigated 2026-09-02 while babysitting PR #37. **Not caused by that PR** —
reproduced on `main` independently. Deliberately left unfixed there; this file
is the handoff so a follow-up does not start from zero.

## The failing gate

`Browser — workbench journey and accessibility` → `npm run test:workbench`:

```
page.waitForFunction: Timeout 30000ms exceeded.
  at caos/frontend/scripts/workbench-smoke.mjs:1099   (main: :1095, same assertion)
```

That wait expects focus back on the `Revenue growth, FY2025, BASE` assumption
input after Escape dismisses the discard-draft dialog raised by `history.back()`.

**Pre-exists on main.** Main's CI run 33609642643 (`0458f10`, then-current tip)
fails the identical assertion. Main alternates pass/fail with no relevant code
change — `14c49ec` (green) → `0458f10` (red) is a *gitignore-only* commit. Same
code, both outcomes.

## SUPERSEDED 2026-09-02 — the root cause below is wrong

Measured with an instrumented copy of the smoke (focusin/MutationObserver
timeline plus a snapshot of `document.activeElement` immediately before
`history.back()`), 12 isolated runs, stock code:

| | remount before `history.back()` | focus before `history.back()` | result |
|---|---|---|---|
| PASS (8) | no | `Revenue growth, FY2025, BASE` | pass |
| FAIL (4) | **yes** | **`Open command palette`** | fail |

12/12, no exceptions. Two conclusions, both opposite to what this file said:

1. **Focus is already on the wrong element before the dialog exists.** Every
   failing run enters `history.back()` with focus on `Open command palette` —
   the trigger of the command-palette dialog dismissed earlier in the journey.
   `DraftDiscardDialog.dismiss()` then does its job correctly: it restores what
   was focused. The dialog is not the defect.
2. **The remount is protective, not causal.** In all 8 passing runs the
   `ForecastScrubber` remount lands *while the dialog is open*: that destroys
   the captured node, `focus(trigger)` fails on `!isConnected`, and the
   `aria-label` fallback finds the replacement — the correct input. The remount
   only breaks things when it lands *before* `history.back()`.

The actual chain in a failing run: the 2500 ms settle window lets a
`draftGeneration` bump remount the scrubber → the focused input is destroyed →
focus drops to `<body>` → the **workspace-level repair effect** restores focus
from `focusedBeforeRef`/`previousFocusedRef`, which still hold the palette
button (seeded there by `099fa10`'s `focusedBeforeRef.current = prompt.trigger`)
→ the journey proceeds with focus on the wrong control.

So the defect is in the repair effect re-focusing a **stale** element after a
remount steals focus, not in the dialog's restore and not in the retry budget.

**A fix was tried and refuted.** Replacing the trigger-selection ternary in
`guardBrowserHistory` with "if something is genuinely focused, that is the
trigger" (dropping the `previousFocusedRef` inversion) rebuilt and ran 14 times:
13 passed, and the one run that took the no-remount path **still failed
identically**. Correct as a simplification, useless as a fix — by that point
focus is already wrong. Do not re-attempt it.

Two directions worth trying instead, neither verified:
- Stop `ForecastScrubber` re-keying on `draftGeneration`
  (`model/ModelBuilder.tsx:750`). The remount is what steals focus; a controlled
  value would reset without unmounting.
- Make the repair effect re-find the element that just lost focus (by
  `aria-label`/`id`) rather than restoring a remembered unrelated one.

Everything below is the original 2026-09-02 analysis, kept for the record. Its
mechanism claims are superseded by the table above; its **harness warnings
remain accurate and valuable**.

## Root cause (superseded — see above)

`DraftDiscardDialog.dismiss()` in `caos/frontend/src/components/Workspace.tsx`
restores focus to the control that opened the dialog. That control is routinely
destroyed while the dialog is up: `ForecastScrubber`'s React key embeds
`draftGeneration` (`model/ModelBuilder.tsx:750`), so the captured node is
unmounted and an equivalent one takes its place. Confirmed by tagging the node
before `history.back()` and re-checking after — `nodeWasReplaced: true`.

The shipped code retries 10 times at 50ms and returns on first success. Two ways
that loses:

- The replacement lands after the 500ms budget → nothing retries → focus stranded
  on `<body>`. Reproduced deterministically by replacing the node at a controlled
  delay: 800ms ⇒ `FOCUS_STRANDED`.
- The first attempt succeeds on a node React is about to discard → it returns →
  the replacement arrives unfocused, with nothing watching.

There is also a **second focus-restore system** — the workspace-level repair
effect (`Workspace.tsx`, the `focusedBeforeRef` / landmark-fallback effect). It
cannot cover this case (none of its deps change on this transition, and it
declines while a dialog is open), but the two mechanisms *can* both act, which
is what makes the failure mode order-dependent.

## Three fixes attempted, none verified — and why

1. **Condition-driven watch** (`MutationObserver`, retry until restored).
   Exposed: `DraftDiscardDialog` is ONE persistent instance reused for every
   prompt (mounted once at `Workspace.tsx:955`), and this journey dismisses four
   dialogs in seconds — so several watches ran concurrently, each holding a
   different stale trigger.
2. **Supersession** (`pendingRestoreRef`; a new dismissal tears down the prior
   watch). Still failed: a *single* surviving watch fires on unrelated DOM churn.
   Marker timeline caught it exactly — `firstAssumption.focus()` lands at
   t=38581, focus flips to `Open command palette` (an already-dismissed dialog's
   trigger) at t=38592, no dialog open, nothing asking for it.
3. **Target discrimination** (tear down unless the `focusin` is this restore's own
   target). Inconclusive; see measurement problem below.

WIP patch for attempt 3 saved at (session scratchpad, not in the repo):
`focus-race-wip.patch`. Do not apply it unverified.

## Measurement problem — read this before trusting any local run

Every "this made it worse" reading turned out to be harness noise:

- **Rate limiting.** `RequestCeilings` is in-process, so a long batch of
  back-to-back smokes against one long-lived dev server starts returning 429 and
  the smoke fails at unrelated assertions. Boot a fresh server per iteration.
- **Concurrent hunts.** Two harness scripts on port 8123 corrupt each other.
- **Rebuild mid-flight.** Running `build_frontend.sh` while a smoke is executing
  swaps static chunks under the running page and fails at random assertions.
- **`pkill -f` self-match.** A wrapper shell whose own command line contains the
  pattern kills itself (exit 144). Use `[p]attern`.
- **Playwright's `locator.focus()` bypasses `HTMLElement.prototype.focus`** (it
  goes through CDP), so monkey-patching that method will not observe it. It does
  still fire real `focusin`, so listen for the event instead.

The smoke also flakes at several *other* unrelated points under load
(`isDisabled` on an assumption field, `.evidence-source-list details` summary,
`Saved v5`), so a red run is not necessarily this bug.

## Recommended next approach

Do not add a fourth referee between the two restore systems. Give focus
restoration **one owner**: delete `DraftDiscardDialog`'s private retry and extend
the workspace-level repair effect to cover dialog dismissal, or vice versa. The
race class disappears instead of being arbitrated.

Build a trustworthy harness first — isolated port, fresh server per run, no
concurrent runs, no rebuilds mid-flight — or the result cannot be believed.
