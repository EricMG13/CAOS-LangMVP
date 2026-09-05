# FE-D1 — Workbench information-architecture directions (canvas and decision)

Date: 2026-09-05. Worktree `.claude/worktrees/caos-workbench-ia-directions-07795b` at `afb93ab` (main after PR #61); committed on `claude/fe-design-directions`. Design session, interactive: the decision owner was present, answered one round of questions and picked the direction on the canvas. No source, style, test, script or plan file changed. Inputs: the FRONTEND ADDENDUM in `docs/superpowers/plans/2026-09-03-frontend-audit-and-ia-redesign-prompt-series.md`, `ia-design-brief.md`, `frontend-a2-design-truth.md`, and the "Decisions" section of `frontend-a1-ia-audit.md`.

## 1. Canvas

- URL: https://claude.ai/code/artifact/5de66539-7954-45fd-8f8f-d40349fe736e (title "CAOS Workbench Directions"; private artifact; the same URL was republished after the pick).
- Working files: `docs/design/canvas/workbench-directions/` — `Main.dc.html` (page 1), `Alternatives.dc.html` (page 2), thirteen artboard files (one per artboard, listed below) and `canvas.json` (pages, notes, artboard positions, the decision). The `.dc.html` files reference `./support.js`, the Claude Design runtime, which is not committed (addendum: "never the seeded payload"); they render standalone in a browser without it.
- Matched from source, one line: `caos/frontend/app/globals.css` at `afb93ab` (the `:root` tokens and every rule the drawn classes use, copied verbatim and scoped to the frame; the 900px block re-emitted for the 720 frame), `WorkbenchShell.tsx` (rail order, glyphs, top bar, authority strip), `Workspace.tsx` (the Credit, Run and reader markup) and `states.tsx` (`IdentityValue`, `Unavailable`, `MutationReceipt`), with the running app's own copy from `evidence/a1/` (screenshots 22, 26, 27, 34, 36 and the traces).
- Every artboard is a static mockup: real `select`, `button` and `details` elements made inert by the frame (`pointer-events: none`, `tabindex="-1"`). No control is drawn for an unserved capability; the Credit shell carries the `Unavailable` block "Binding measure and claim gaps — Not available in this deployment." exactly as the app does.

### Artboards (names fixed for the rest of the series)

| Direction | Page | Artboards | Tab · URL shown above the frame |
|---|---|---|---|
| Align (recommended, chosen) | 1 | Align — Shell 1440 · Align — Shell 720 · Align — Analysis paused | CAOS — Credit · `/credit/?case=…`; CAOS — Run · `/run/?case=…&run=…` |
| Absorb | 2 | Absorb — Shell 1440 · Absorb — Shell 720 · Absorb — Analysis paused · Absorb — Analysis reader | CAOS — Credit · `/credit/`; CAOS — Analysis · `/analysis/?case=…&run=…` (both modes) |
| Lifecycle | 2 | Lifecycle — Shell 1440 · Lifecycle — Shell 720 · Lifecycle — Analysis paused | CAOS — Credit · `/credit/`; CAOS — Run · `/run/` |
| Labels | 2 | Labels — Shell 1440 · Labels — Shell 720 · Labels — Analysis paused | CAOS — Credit · `/command-center/`; CAOS — Run · `/run-console/` |

Beside each direction sits a sticky note with its motivation and main trade-off (verbatim from `frontend-a1-ia-audit.md` §5 and `ia-design-brief.md` §4) plus a "Drawn with" line; the must-not lines of the brief (§6) sit on a paper note at the top right of page 1. The shells show the Credit surface on the golden case (Goldenpack-7d2kd Holdings, accepted snapshot `snap-343b23e…82f0`, source set v1); the Analysis artboards show the Researchpack-7d2kd Holdings Deep Research run `run-a2b92d71…92e7` paused on `PLAN_APPROVAL_REQUIRED` with the persisted plan (plan hash, methodology build, brief digest, source set, upstream artifact, scope, three workstreams) and "Approve research plan" as the one primary.

## 2. The one round of questions and the answers

1. Which surface fills the shell artboards? **Credit** (PM landing; its "Review latest run" is the Align trade-off the audit names).
2. How does Absorb show its mode switch? **A fourth artboard**, "Absorb — Analysis reader", beside the paused one; both carry a mode callout.
3. The compile form on the paused artboard? **Collapsed per D11** to "Advanced: compile a route", because the run came from intake.

Calls made without asking: the Run tool renders on every surface for Align and Lifecycle (D12) and Lifecycle's "Loan universe" follows the same rule; Labels keeps the Run tool Analysis-scoped, so its Credit shell has no tools group; Absorb's kicker follows the mode ("Analysis / Execution" while a run is selected, "Analysis / Reader" otherwise); the analyst-boundary line reads "versioned in Report" on all four (the aligned vocabulary); Absorb's two mode callouts ("Showing execution." / "Showing the accepted reader.") are new copy because that surface does not exist today.

## 3. Decision

- **Direction chosen: Align.** Recorded 2026-09-05 by the decision owner, in their words: "Align, no changes — record it and commit".
- Changes asked for: none.
- Canvas after the pick: page 1 (`Main.dc.html`) holds Align, the header with the decision line and the must-not note; page 2 (`Alternatives.dc.html`) holds Absorb, Lifecycle and Labels unchanged. `canvas.json` records `chosen`, the decision and each artboard's page and position.
- What this binds (brief §9): layout, hierarchy, states and copy of the Align artboards. Tokens stay in `globals.css`; the wire contract and authorization are untouched. FE-G2 writes the `DESIGN.md` addendum and the `docs/DECISIONS.md` §14 entry (D6) from this record.

## 4. Exports

PNG exports of each direction's main artboard (the Shell 1440 frame, 1440 × 1000 at 1×, Chromium via the frontend's Playwright), retained under `.superpowers/sdd/frontend/design/`:

| File | SHA-256 |
|---|---|
| `fe-d1-align-shell-1440.png` | `45ea2f8ffa4bfe72b88acba992fe561664986c1af2c0dc3de4108d49cb9cb51e` |
| `fe-d1-absorb-shell-1440.png` | `663d8fc385a526b07ce3d94163e78943b712e578683b39241e9190b5e9ee4ab2` |
| `fe-d1-lifecycle-shell-1440.png` | `1d54a1f770088a93eb7c1105dddad3b89db32d1c50b29c260dbcb9f3f430b8af` |
| `fe-d1-labels-shell-1440.png` | `663d8fc385a526b07ce3d94163e78943b712e578683b39241e9190b5e9ee4ab2` |

Absorb and Labels share a digest by construction: on the Credit surface neither draws a tools group, so their shell frames are byte-identical; they differ only in the URL line above the frame (`/credit/` against `/command-center/`) and on their Analysis artboards.

## 5. Notes for FE-D2 and FE-G2

- Fidelity: the artboards use the app's class names and verbatim rules, so what differs from the atlas is layout at a given width, not style. Measured delta: at 720 the rail band is 136px here against the truth sheet's 121px, because the `rail-meta` issuer and "Desktop workbench" lines wrap in the flex row; same CSS, no override involved. Model, Report, "Analysis tools · Run", Governance · Admin and the rail meta sit past the right edge of the 720 strip, as F-07 records.
- The published artifact renders inside a cross-origin iframe the desktop browser pane cannot capture; the identical HTML was verified locally in Chromium (three viewport screenshots of the artifact, full-page screenshots of five artboards).
- The artboards, the two canvas pages, `canvas.json` and the artifact were generated from one scratch script that read `globals.css` and the markup builders; the script lives in the session scratchpad and is not retained. The committed files are the outputs; regenerating them means re-deriving the builders from the components named in §1.

## 6. Commands run

```
node build.mjs                                   # scratchpad generator → 13 artboards, Main.dc.html, Alternatives.dc.html, canvas.json, the artifact HTML
node shot.cjs / export.cjs                       # Playwright (main checkout's caos/frontend/node_modules) — local look, PNG exports; pageerror/console errors: none
shasum -a 256 .superpowers/sdd/frontend/design/fe-d1-*.png
```

Not run: lint, tsc, unit, build, smoke, a11y — no source, style, test or script changed.
