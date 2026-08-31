# CAOS implemented desktop audit — evidence

Date: 31 August 2026

## Implemented product evidence

- One persistent workbench exposes Portfolio, Credit, Sources, Analysis, Market, Model, Report, and Admin while preserving selected credit, accepted authority, selected run, and source-set identity.
- The original palette is implemented through semantic tokens: base `#0a0a0f`, panel `#11131d`, elevated `#1d2030`, ink `#e6e6ef`, blue `#63a1ff`, amber `#f5a524`, and red `#f87171`. The report document alone uses the light paper surface.
- The implementation has no gradients, shadows, decorative illustration, idle animation, or keyframes. Two 160 ms interaction transitions remain, and reduced motion collapses them to `.01ms`.
- Unsupported functionality is not simulated: Portfolio labels its enhanced contract proposed; claim coverage, Admin governance, and one-way sensitivity render unavailable; market percentile is absent.
- Reader authorization now fails closed. Identity-fetch failure reaches a terminal Reader state, and write-gated model assumptions, scenarios, preview, sign-off, rebase, and shared mutations are not presented as usable Reader actions.
- Source search no longer keeps a filtered-out document selected. Zero-block sources say `No blocks`; extracted status is reserved for sources with blocks.
- Report Studio distinguishes local unsaved preview from exact saved identity, searches every served evidence block without silent truncation, persists a scope-bound browser recovery copy, rejects malformed recovery data, retries saves, and clears recovery only after a server save.
- Analysis snapshot switching reloads the switched snapshot's artifacts and generation-fences overlapping case/load/switch completions. New authority and old artifacts are never committed as one visible state.

## Visual and accessibility evidence

- All nine production destinations were measured at six desktop viewport sizes. Across the 54 base combinations, `document.scrollWidth === document.clientWidth`.
- Populated pending-plan, Model Builder, and Report Studio fixtures expanded the final automated matrix to 70 combinations. Axe reported zero violations; model and report keyboard checks passed at normal desktop sizes and 200% zoom.
- The lowest measured visible text contrast was 6.20:1: active blue navigation on the elevated panel.
- Focus is a two-pixel blue outline with a two-pixel offset. Loading, empty, error, unavailable, warning, success, and receipt components are implemented.
- At 720 CSS pixels, the desktop rail becomes a horizontal scroller and content stacks without page-level overflow. This is desktop zoom behavior, not a mobile layout.
- Control density is stable: 12–18 controls per route. Sources, Analysis, Model, and Report use internal scroll regions for dense comparison rather than widening the page.

## System and weight evidence

- The production export is 1,371,352 bytes across 83 files. Initial modern-desktop JavaScript is seven requests, 649,584 raw bytes, about 155,921 Brotli-equivalent bytes; CSS is 53,440 bytes.
- A cold local `/cases/` load made 29 requests: one document, two fonts, one stylesheet, seven scripts, two API calls, twelve exported RSC prefetches, and four route HEAD prefetches. No duplicate method/path pair occurred.
- Local median readiness was 10.2 ms to DOMContentLoaded, 36.5 ms to load, and 46.3 ms to hydrated case selection; this is not a production-network TTI claim.
- Thirteen font files are packaged while two load initially. Snapshot data is refetched independently by shell, Deep Dive, and Command Center; active model/run states poll or stream intentionally.

## Verification evidence

- `npm run test:unit`: 73/73 passing.
- `npm run lint`: passing.
- `npm run build`: TypeScript and 12 static routes passing.
- `CAOS_URL=http://127.0.0.1:8123 npm run a11y`: 70 combinations, zero violations.
- `git diff --check`: clean.

## Known gaps

- No five-product peer survey was run, so innovation cannot score 3.
- Dense Model and Report workspaces remain cognitively heavier than the simpler record screens.
- Saved views, recent credits, and task-oriented help are absent because their product/contracts are not yet defined.
- The packaged font count and repeated snapshot fetches leave measurable weight debt, although idle animation is zero and local readiness is fast.
- The production-inventory script is not a gate for this branch: it targets routes intentionally absent from the current deployment. The combined-app workbench and accessibility suites are the applicable standing browser gates.
