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

### Direction 1 tried: the remount is gone, the failure is not

`ForecastScrubber` no longer re-keys on `draftGeneration`
(`model/ModelBuilder.tsx`). It takes `generation` as a prop and syncs its local
input state when the generation or the authoritative value changes, so the reset
semantics are identical but the DOM node — and focus — survives.

Verified with the harness: **12/12 runs show no remount at all**, and the dirty
value `0.06` is preserved in all 12, so the reset behaviour is intact. `tsc`,
`eslint --max-warnings=0` and the 116 unit tests are green.

**It does not fix the CI failure.** Full smoke, 8 runs: 5 pass, 3 fail — two of
them still `:1099`. Against a stock baseline of roughly 2 passes in 7 that is not
a regression and may be an improvement, but the sample is far too small to claim
one. Worth keeping on its own merits — every draft generation used to destroy
every scrubber, and any focused one with it — but it is not a fix for this issue.

### What actually pulls focus away — measured, still unfixed

Instrumenting `focusout` with the target's `disabled` state, 10 runs:

- **`disabled` is `false` on every focusout.** The "the input gets disabled and
  the browser blurs it" hypothesis is refuted.
- In the failing run, focus reaches the assumption input at t=13 ms and **leaves
  it again at t=16 ms**, landing back on `Open command palette`, where it stays
  through the whole 2500 ms settle window. Passing runs keep focus on the input
  until `history.back()` at t≈2545 ms.

So something re-focuses the previous dialog's trigger ~3 ms after the journey
legitimately moved focus. `DraftDiscardDialog.dismiss()`'s restore chain retries
for up to 500 ms after the dialog closed and never checks whether anyone else has
since taken focus, which fits exactly.

**A guard for that was tried and regressed the suite.** Aborting `restore()` when
`document.activeElement` is neither `<body>`, the trigger, nor inside the dialog
took the smoke to **10/10 failures at `:1502`** — the pathway-selector restore
after "Keep editing" is a legitimate repair the guard suppresses. Reverted. Any
fix has to separate "focus moved on" from "focus is mid-handoff during dialog
close", and that distinction is the whole problem.

### 2026-09-03: the yank is the browser's native modal-close restore

This is the finding that reframes the issue, and it explains why every fix
attempted so far — three before today, one more today — has failed.

Instrumenting the whole journey (focusin/focusout, `<dialog>` `close`/`cancel`,
and a patched `HTMLElement.prototype.focus`) over 20 isolated runs, 4 of which
failed:

```
t=957  MARK       POST-assumption-focus     <- journey focuses the input
t=982  DLG-close  discard-dialog-title      <- the dialog's close fires LATE
t=988  out        Revenue growth, FY2025, BASE
t=989  in         Open command palette      <- focus taken, no .focus() call
```

**No `FOCUS-CALL` is ever recorded at the yank.** The patched
`HTMLElement.prototype.focus` captures every application call and sees none. So
nothing in the app moves focus here: closing a modal `<dialog>` makes the
*browser* restore focus to whatever was focused before `showModal()`, which for
this dialog is the command-palette button it was raised from.

That is why handler-level fixes cannot work, and it retro-explains the failures:

- guarding `dismiss()`'s retry chain — no effect, the chain is not the mover
- `guardBrowserHistory`'s trigger ternary — refuted earlier, same reason
- removing the `ForecastScrubber` remount — reduced churn, did not touch this
- guarding `WorkbenchShell`'s palette `onClose` — no effect; the palette's own
  handler is not what fires either

The remaining variable is **when** the discard dialog's `close` lands. When it
fires while the dialog still owns focus, the native restore is correct and the
run passes. When it fires a render later — after `dismiss()` has already restored
focus and the journey has moved on — the native restore is a theft.

Attempted today and **reverted, because it reduced without eliminating**:
remembering the last focused element and re-focusing it after a close that moved
focus from outside the dialog. Measured 1 failure in 13 against a baseline of 4
in 20 — better, but n=13 cannot carry that claim, and this is WCAG-governed focus
code where a partial fix is not worth the risk. `tsc`, `eslint` and the 123 unit
tests were green on it; the change is recoverable from this session if wanted.

### That "stop the late close" plan was wrong, and so was its successor

Both were tried and both are refuted. Recorded so the next person starts from
what is left rather than from here.

**"Close exactly once, synchronously" is not implementable — it already is.**
Wrapping `HTMLDialogElement.prototype.close` shows one call per dismissal:

```
t=788  close-CALL   discard-dialog-title  wasOpen=True   <- dismiss(), once
t=795  in           Open command palette                 <- dismiss()'s restore
t=828  in           Revenue growth, FY2025, BASE         <- journey moves focus
t=848  close-EVENT  discard-dialog-title                 <- event fires 60ms later
t=855  in           Open command palette                 <- native restore wins
```

There is no second call site. `close()` **queues** the `close` event rather than
firing it, and the platform's focus restoration rides that deferred dispatch. The
"late close" was never a second code path; it is the browser.

**Restoring on the `close` event instead does not work either.** The obvious
consequence of the above is to stop restoring inside `dismiss()` and restore from
a `close` listener, so the app runs after the platform. Implemented, built (with
the bundle's mtime checked against the source — an earlier attempt silently
measured a stale build), and run 40 times: **6 failures in 26 dumps, against a
baseline of about 4 in 20.** No improvement.

That failure is informative. Had the listener run after the platform's
restoration, it would have won. It did not, so **the restoration lands after
`close` handlers too, and no handler-based ordering can beat it.** Every
remaining idea of the form "restore later" or "restore harder" is dead.

**What that leaves.** The browser restores to whatever was focused before
`showModal()`, and `DraftDiscardDialog` is a *single element reused for every
prompt* (mounted once in `Workspace`). Its restore target is therefore whatever
preceded its most recent `showModal()` — and when dispatch is deferred, a stale
association from an earlier prompt is still live. In the failing runs the
offending target is the command-palette button, which is what preceded the
*earlier* prompt in the same journey, not the current one.

So the direction worth trying next is to stop reusing the element: give the
dialog a React `key` per prompt so each prompt gets a fresh `<dialog>` with no
inherited restore target. Untested — it is a hypothesis with a mechanism behind
it, not a fix.

Remaining direction, still unverified:

- Make the repair effect and the dialog restore re-find the element that just
  lost focus (by `aria-label`/`id`) rather than restoring a remembered one, and
  make a late retry a no-op once focus has settled elsewhere — without breaking
  the dialog-close handoff above.

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
