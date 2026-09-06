# FE-G4 — design QA, contract sync and the closing critique

Date: 2026-09-06 (started). Implementer: Claude Fable 5.1. Branch
`claude/enterprise-readiness-frontend-g4-fa7188`, worktree
`target-consolidation-checklist-b86b72`, from `main` at `bfeda07` (PR #72) plus the
three FE-G3 second-pass commits of PR #74 (`d29d716`, `bbf6916`, `ef27525`), which
were on this branch when the session opened and which #74 has not yet merged.

Worktree: the session opened in `target-consolidation-checklist-b86b72` (a worktree named for
another task) and moved, at the user's instruction mid-task, to `.claude/worktrees/fe-task-04-design-qa`
on the same branch: the working changes were carried over as a patch, the old worktree was left
detached at `ef27525` with the two remaining assessment sub-agents still running there against
`:8791`, and the export rebuilt here was compared with the one that server serves: the same 111
files, CSS and JS chunks byte-identical, differing only in Next's build id and the HTML/RSC
payloads that embed it (§9), so the assessments and the captures on `:8791` are evidence about
this tree. The gates server on `:8792` was restarted from this worktree.

Prompt: FE-G4 in `docs/superpowers/plans/2026-09-03-frontend-audit-and-ia-redesign-prompt-series.md`.
Standing preamble and frontend addendum followed. The impeccable skill's
`AUTONOMY_DIRECTIVE_CHECK` asks for one interactive probe before proceeding; the
user's own prompt points at the standing preamble ("the user is not watching in real
time"), so the critique's "Ask the User" step is replaced by the decision rules the
prompt carries (fix P0/P1, record P2), and that substitution is stated here at the top.

## Status

(written as the task proceeds; every claim below points at a command in §9)

## 1. Measuring instrument

- `node ~/.claude/skills/impeccable/scripts/context.mjs --target caos/frontend/app/globals.css`
  loaded PRODUCT.md and DESIGN.md (no surface brief; no `CONTEXT_STALE` directive).
- Critique (`reference/critique.md`): Assessment A (design review) and Assessment B
  (detector + browser evidence) as two isolated sub-agents, plus the audit
  (`reference/audit.md`) as a third, all against the combined app on `:8791`
  (host-control, fresh data directory, seeded by the Chromium workbench smoke).
- Target: every destination (`/portfolio/ /credit/ /sources/ /analysis/ /run/ /market/
  /model/ /report/ /admin/`) in every drawn state at 1440×1000 and 720×900.

## 2. Critique and audit results

The three sub-agent reports are retained in the session scratchpad
(`agents/a/report.md`, `agents/b/report.md`, `agents/c/report.md`; B and C wrote their
own files, A's body was saved by this session because its sandbox refused the write)
and their scores and detector output are quoted verbatim in
`IMPECCABLE-CRITIQUE-2026-09-06.md`. Headline figures:

| Instrument | Result | Where |
|---|---|---|
| Critique, Assessment A (design review, isolated sub-agent; 86 page states at 1440 and 720, 10 keyboard walks, 16 focus-return probes; 0 × 429, 0 page errors) | **25/40 — Acceptable**; design-specificity: authored in the shell and the ceremonies, category-interchangeable in the worklists; cognitive load Model 4/8, Report 5/8, Run 2/8 failures; 7 P1, 12 P2, 3 P3 | critique file, heuristic table and §Priority issues |
| Critique, Assessment B (detector + browser overlay, isolated sub-agent) | CLI `detect.mjs --json` exit 2: `border-accent-on-rounded` globals.css:178 (false positive, CSS triangle) and `layout-transition` globals.css:248 (minor, live progress width); overlay console groups `[impeccable] 27/21/23/18/72` (1440) and `26/22/22/17/70` (720) for Portfolio/Credit/Run/Model/Report, classified rule by rule; strict CSP blocked the cross-origin script and the overlay stylesheet, so the bytes were injected inline and the full overlay read under `bypassCSP` | critique file, §Anti-pattern verdict |
| Audit (isolated sub-agent; 29 axe scans, 3 width probes, 2 focus walks, 2 reduced-motion probes, export measurements) | **14/20 — Good**: Accessibility 3, Performance 3, Responsive 2, Theming 3, Implementation integrity 3 (PASS); P0 0 · P1 1 · P2 6 · P3 12; lowest enabled-text contrast 5.71:1; 0 axe violations; 0 undefined tokens | critique file, §Audit health score |

Where the two design assessments and the audit agreed: the intake checkbox (A P1, audit P2-1),
the Model "Open Run" orphan (A P1, audit P3-12), the rail at 720 (A P1, audit P2-6), the
Report copy `vUnavailable` / `v—` (A P2, audit P2-2, FE-G3 §10.6). Where the detector
caught what the reviewers missed: the `.report-section-nav` 7 px padding, the 157–166 ch
helper paragraphs, the 12 px gutters at 720. Where the detector was wrong: every
`text-occlusion` hit (the overlay measuring itself), `overused-font` (Roboto as a listed
fallback), `em-dash-overuse` (the case selector's option labels), `all-caps-body` (paper
section heads), the CSS-triangle glyph.

## 3. Findings fixed (P0/P1) and recorded (P2)

Rule applied: a P0/P1 is fixed in the file the finding names, its paired test edit is
named beside it, and no test is weakened; a P2 is recorded in the critique file with the
file and what it needs.

| # | Finding (severity, source) | Fix | Files | Paired test edit | Proof |
|---|---|---|---|---|---|
| 1 | Model: the first assumption edit inserts the sign-off panel above the worksheet and displaces the grid ~650 px (P1, A) | the approval panel renders as its own `panel span-12` below the worksheet | `caos/frontend/src/components/model/ModelBuilder.tsx` | `ModelBuilder.test.ts` pins `dirty && canWrite ? <section className="panel span-12" data-model-approval` (the old pin named the old class string) and asserts the panel follows `${styles.workspace}` | unit 141/141; `evidence/g4/fixture-ready-model-*` |
| 2 | Model: every blank worksheet cell renders `is-selected` on first paint — `undefined === undefined` (P1, A) | `cell && selected?.address === cell.address` | `ModelBuilder.tsx` | `ModelBuilder.test.ts` pins the expression | `evidence/g4/fixture-ready-model-desktop-1440.png` (only the clicked cell is selected) |
| 3 | Model NOT_READY: a floating `Open Run` button outside `.panel-body`, a generic block duplicating (and for Northstar contradicting) the server's typed blocker (P1, A; P3-12, audit) | the notices render inside a `panel-body`; the server's blockers are `StateBlock`s with `Open Run` as the first blocker's action; the generic block appears only when the server names none | `ModelBuilder.tsx` (`Link` import dropped) | none needed (no literal pinned) | `evidence/g4/populated-model-desktop-1440.png` |
| 4 | Evidence drawer denies the block locator the chip shows and never lands on the cited block (P1, A; FE-G3 F-04 deferred to FE-G4) | `DrawerState.blockIds` threaded from the chip's `ref.blockIds`; the drawer lists cited blocks first, marks them `Cited` with `data-cited-block`, and shows the source-level sentence only when the citation named no block | `WorkbenchShell.tsx`, `Workspace.tsx` | `scripts/workbench-smoke.mjs` waits for `[data-cited-block=<first block id>]` and asserts the old sentence is absent (it used to wait for the wrong sentence) | smoke passed in three engines (§7) |
| 5 | Intake "Add to this case" checkbox stretched to 748 px and severed from its label (P1, A; P2-1, audit) | `.field input:not([type="checkbox"])` | `caos/frontend/app/globals.css:155` | `workbench.test.ts` pins the selector | `evidence/g4/populated-portfolio-desktop-1440.png` |
| 6 | Report's paper column clipped with no scroll between 901 and ~1283 px (P1, audit) | `.report-studio` third column `minmax(0, 5.5fr)` | `globals.css:465` | `workbench.test.ts` pins `minmax(0, 5.5fr)` and forbids `minmax(440px` | probe after the fix: `clipped: false` at 1024, 1100, 1280 and 1366 (`studioScroll === studioClient`; before: 1004 vs 812/888/1000) |
| 7 | Rail at ≤ 900 px hides Model, Report and Admin with no cue (P1, A; P2-6, audit; FE-A2 F-07) | a styled `::-webkit-scrollbar` thumb on `.rail` (Chromium, WebKit) and `scrollbar-width: thin; scrollbar-color` scoped by `@supports not selector(::-webkit-scrollbar)` to Firefox — the first attempt set both on the element and Chromium then ignored the pseudo-element, measured as `offsetHeight − clientHeight = 1` (the border) | `globals.css` (the 900 px block) | none (no literal pinned) | rail probe with `ignoreDefaultArgs: ["--hide-scrollbars"]`: `offsetHeight − clientHeight` 7 in Chromium and WebKit (6 px thumb + the border), clip screenshot `rail-720-chromium.png`; Firefox reads `scrollbar-width: none` on every element under Playwright headless, so its thin overlay cue is unverified (§9) |
| 8 | Portfolio: twelve filled `Open credit` primaries per screen, post-intake `Open review` a small button (P1, A) | **not fixed** — `workbench.test.ts` ("Cases makes opening the selected credit primary and keeps portfolio limits secondary") pins the row primary as a product decision; overturning it is the decision owner's call | — | — | recorded in the critique file |

Recorded P2s (the critique file, §Priority issues) — 17 items with file:line and what each
needs, including the two the audit ranked P2 that are performance work (route-level
`next/dynamic`, `WorksheetGrid` memoisation) and the fuller 720 px rail remedy the
approved artboard does not draw.

## 4. Design contracts regenerated

Method: every value comes from a measurement in this session, not from memory —
`caos/frontend/app/globals.css` (`:root` tokens, the rules named), the route
tables in `caos/frontend/src/lib/workbench.ts`, `GET /openapi.json` on the
combined app (the served route list) and the client's own `/api/…` call
inventory (`grep` over `caos/frontend/src`). The FE-A2 §11 delta tables had
been applied by FE-G1 (`d7f834b`); what remained stale was the body prose that
still named pre-Align surfaces, the two 31 Aug addenda that the bodies now
duplicate, the anatomy rules FE-A1 D-I retired, PRODUCT.md's user sentence, the
capability map's route wording, and the `.impeccable/design.json` sidecar (still
the pre-reskin palette from 2026-08-22).

A check script asserts that every `#rrggbb`, every `--caos-*`/`--radius-*`/
`--shadow-*`/`--space-*`/`--font-*`/`--ease-*` token and every `` `/slug/` ``
route named in DESIGN.md, .impeccable.md, PRODUCT.md and the capability map
exists in the CSS `:root` or the route tables (result: no unknown hex, token or
route in any of the four; the sidecar's five extra hexes are the resolved
`color-mix()` accent tints it declares as a tonal ramp and labels as derived).

Measured corrections beyond the A2 delta: uppercase-label tracking is
.08–.14em (`.worksheet-tab`, `.report-optional summary` and `.report-section-nav
small` are .08em; A2 wrote .09–.14em); the coarse-pointer rule at
`globals.css:637` (44px minimum height under `pointer: coarse`) was documented
nowhere; the rail's three groups ("Workspace", "<workflow> tools", "Governance")
and the 1100px/900px breakpoints are now in DESIGN.md §5; `.status::before`
shapes are named in the Status Glyphs rule; the 31 Aug addenda are folded into
DESIGN.md §1/§4/§5 and .impeccable.md's aesthetic section (their facts were
already the bodies' facts), and the dated FE-G2 addendum is kept with its one
cross-reference corrected.

### 4.1 DESIGN.md

```diff
diff --git a/DESIGN.md b/DESIGN.md
index d16b1be..5b2d756 100644
--- a/DESIGN.md
+++ b/DESIGN.md
@@ -71,3 +71,3 @@ typography:
     letterSpacing: "0.09em"
-    note: "Table heads and rail group labels; tracking runs .09–.14em by site. Chrome floor is 9px (TOC ids, evidence digests, forecast labels)."
+    note: "Table heads and rail group labels; tracking runs .08–.14em by site. Chrome floor is 9px (TOC ids, evidence digests, forecast labels)."
   mono-meta:
@@ -197,3 +197,5 @@ CAOS is a refined institutional terminal for buy-side credit analysts. It should
 
-The workspace is dark, dense, and single-mode. Density is earned with fixed panel chrome, aligned numerics, small labels, and restrained state color. The Report Studio and research documents deliberately invert the workspace into light paper: ink on cream, file-ready, and visually distinct from the live analytical surface.
+The workspace is dark, dense, and single-mode. Density is earned with fixed panel chrome, aligned numerics, small labels, and restrained state color. Report and research documents deliberately invert the workspace into light paper: ink on cream, file-ready, and visually distinct from the live analytical surface.
+
+The current design is the modern dark terminal adopted on 31 August 2026 at the product owner's instruction: the graphite ramp (`bg` → `panel` → `elevated` → `subtle`), one iris accent, retuned semantic colours, a 6–14px radius scale, faint resting panel shadows, the native display face for chrome headings only, and severity-shaped status glyphs. It replaced the earlier blue accent, all-square geometry and flat panels; those pre-reskin rules are not carried anywhere in this document.
 
@@ -206,3 +208,3 @@ CAOS explicitly rejects friendly consumer SaaS, oversized marketing dashboards,
 - Motion only for live, running, selected, or changed state.
-- Light paper output only inside Report Studio and research deliverables.
+- Light paper output only inside Report and research deliverables.
 
@@ -253,3 +255,3 @@ No web font is shipped (enterprise Task 3 removed the external font dependency;
 - **Body** (400, 14px, 1.55): Workspace copy, state detail, rail text, and tool bodies.
-- **Label** (sans, 10–11px): sentence case at 11px/650 for kickers and field labels; uppercase and tracked (.09–.14em) at 10px/700 for table heads, rail group labels, worksheet tabs and report rail labels. Mono is for identifiers, digests, timestamps and numerics, not for labels. The chrome floor is 9px (TOC ids, evidence digests, forecast labels — FE-A2 F-06).
+- **Label** (sans, 10–11px): sentence case at 11px/650 for kickers and field labels; uppercase and tracked (.08–.14em) at 10px/700 for table heads, rail group labels, worksheet tabs and report rail labels. Mono is for identifiers, digests, timestamps and numerics, not for labels. The chrome floor is 9px (TOC ids, evidence digests, forecast labels — FE-A2 F-06).
 
@@ -257,3 +259,3 @@ No web font is shipped (enterprise Task 3 removed the external font dependency;
 
-Report Studio, research exhibits, print views, and research deliverables use a deliberate paper scale rather than workspace labels: **Output Title** (650, 21px, −.01em), **Output Section** (700, 11px, uppercase, .08em), **Output Body** (400, 12px, 1.62), **Output Subtitle** (600, 10px, mono), **Output Meta** (500, 8.5px, mono), **Output Table Label** (650, 9px, uppercase), **Output Table Body** (400, 10px), **Output List** (400, 11px), and a 26px/700 mono filed-copy watermark at 16 % alpha rotated −16°. The full-model appendix scale belongs to the worker's PDF/XLSX renderers and is not in `globals.css`. These sizes are valid only inside paper/output roots; they must not leak into navigation, buttons, panel headers, or analytical tables.
+Report, research exhibits, print views, and research deliverables use a deliberate paper scale rather than workspace labels: **Output Title** (650, 21px, −.01em), **Output Section** (700, 11px, uppercase, .08em), **Output Body** (400, 12px, 1.62), **Output Subtitle** (600, 10px, mono), **Output Meta** (500, 8.5px, mono), **Output Table Label** (650, 9px, uppercase), **Output Table Body** (400, 10px), **Output List** (400, 11px), and a 26px/700 mono filed-copy watermark at 16 % alpha rotated −16°. The full-model appendix scale belongs to the worker's PDF/XLSX renderers and is not in `globals.css`. These sizes are valid only inside paper/output roots; they must not leak into navigation, buttons, panel headers, or analytical tables.
 
@@ -275,3 +277,3 @@ Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairline
 - **Popover Shadow** (`--shadow-pop`, `0 12px 32px -12px rgb(0 0 0 / .7)`): declared for a popover the product does not have; no rule reads it.
-- **Paper Shadow** (`--shadow-paper`, `0 24px 70px -24px rgb(0 0 0 / .8)`): Report Studio and research document sheets over the dark gutter.
+- **Paper Shadow** (`--shadow-paper`, `0 24px 70px -24px rgb(0 0 0 / .8)`): the Report paper and research document sheets over the dark gutter.
 
@@ -279,3 +281,3 @@ Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairline
 
-**The Resting Panel Rule.** A resting panel carries a hairline and `--shadow-panel`, nothing larger; a larger shadow means the object floats above the workflow. (Supersedes the Flat-Until-Floating rule, retired by the 31 Aug addendum.)
+**The Resting Panel Rule.** A resting panel carries a hairline and `--shadow-panel`, nothing larger; a larger shadow means the object floats above the workflow. (The pre-reskin flat-until-floating rule is retired.)
 
@@ -290,2 +292,3 @@ Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairline
 - **Disabled:** 55 % opacity; the primary variant reads 2.96:1 (exempt from 1.4.3, below this document's own "remains readable" bar — FE-A2 F-04, open).
+- **Targets:** 36px buttons, 30px small buttons and 24px chips under a fine pointer; under `pointer: coarse` every button, rail link, select, input, chip, worksheet tab and cell link takes a 44px minimum height (`globals.css`, the one coarse-pointer rule).
 
@@ -308,3 +311,3 @@ Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairline
 ### Navigation
-- **Style:** Rail links show a 14px stroke glyph and the label at every width; no tooltips. Below 900px the rail is a horizontally scrolling strip (Model, Report, Governance and the rail meta sit off-canvas at 720px — FE-A2 F-07, open).
+- **Style:** Rail links show a 14px stroke glyph and the label at every width; no tooltips. The rail has three groups: "Workspace" (the seven workflows Portfolio, Credit, Sources, Analysis, Market, Model, Report), "Analysis tools" (Run, carrying a mono `LIVE` badge while a run is in progress, rendered on every surface) and "Governance" (Admin). The rail is 224px wide, 156px below 1100px, and below 900px a horizontally scrolling strip (Model, Report, Governance and the rail meta sit off-canvas at 720px and are reached by scrolling or by the active link's `scrollIntoView` — FE-A2 F-07, open).
 - **Typography:** Sans; the group labels are 10px uppercase tracked; the rail meta is mono 10px.
@@ -314,3 +317,3 @@ Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairline
 
-Every route uses the same ordered contract: the authority strip (credit, visible snapshot, selected run, source set), exactly one page-level primary action, one dominant work region, contextual evidence (evidence chips open the context drawer; Deep-Dive and Command Center carry evidence rails), and sticky approval panels where a governed action waits. Surface kinds preserve specialist behavior: worklists own filter anatomy; analytical objects own conclusion state; Model Builder and Report Studio retain their editor overflow.
+Every destination uses the same ordered contract: the authority strip (credit, visible snapshot, selected run, source set), exactly one page-level primary action, one dominant work region, contextual evidence (evidence chips open the context drawer; Analysis carries an evidence rail and Credit a proof column), and sticky approval panels where a governed action waits. Surface kinds preserve specialist behavior: worklists own filter anatomy; analytical objects own conclusion state; Model and Report retain their editor overflow.
 
@@ -318,6 +321,5 @@ Every route uses the same ordered contract: the authority strip (credit, visible
 - **Authority:** Every ready conclusion carries observation time, origin, method, approval/ratification, and freshness. `LIVE` describes source origin only. Every surface on a screen renders the shell's one snapshot; no surface mints a second accepted identity (FE-G1).
-- **Worklists:** The Cases toolbar is search plus one filter, one action per row; the five-action toolbar and batch state are not implemented (FE-A2 §11; FE-G4 decides whether the rule or the product moves).
-- **Utilities:** Not implemented — there is no utility drawer; the one drawer is the evidence context drawer, whose opener is passed from the click and regains focus on Escape.
-- **Evidence Atlas:** Not implemented as one inspector; the context drawer and the per-surface evidence rails are what exist. Never show a duplicate inspector.
-- **Role composition:** Not implemented — the rail shows the served role read-only; there is no `View: Analyst / PM / QA` switch and it must never grant permission or approval authority if drawn.
+- **Worklists:** The Portfolio register is search plus one filter and one action per row; batch state does not exist (FE-A1 D-I retired the five-action toolbar rule in FE-G4).
+- **Drawer:** The one drawer is the evidence context drawer, whose opener is passed from the click and regains focus on Escape; there is no utility drawer and no second inspector (the context drawer and the per-surface evidence rail are the whole evidence surface).
+- **Role:** The rail shows the served role read-only. No view switch exists; a role control, if ever drawn, never grants permission or approval authority.
 
@@ -329,3 +331,3 @@ The shared panel is the signature CAOS frame: Panel Surface, hairline border, 10
 
-Status meaning must never be color alone. Pair severity color with a drawn glyph, text label, position, or all three. Emoji are forbidden in product chrome.
+Status meaning must never be color alone. Severity is shape plus hue: success and running are a 7px disc, warning a triangle, critical a 7px rounded square, idle a flat 8×3 dot (`.status::before`). Pair severity color with the glyph, a 700 text label, position, or all three. Emoji are forbidden in product chrome.
 
@@ -339,3 +341,3 @@ Status meaning must never be color alone. Pair severity color with a drawn glyph
 - **Do** honor reduced motion. The only animation is the loading shimmer, confined to `prefers-reduced-motion: no-preference`; the only non-hover transition is the live progress width. There is no running pulse, no flash cue and no dialog entrance motion.
-- **Do** reserve Paper Surface and Paper Ink for Report Studio and research deliverables.
+- **Do** reserve Paper Surface and Paper Ink for Report and research deliverables.
 
@@ -352,20 +354,2 @@ Status meaning must never be color alone. Pair severity color with a drawn glyph
 
-## 2026-08-31 reskin addendum (supersedes where noted)
-
-At the product owner's instruction the workspace moved to the **modern dark
-terminal**: a graphite ramp (`#0a0c10` → `#101319` → `#181d28`), iris accent
-`#8b93f8`, retuned semantics (emerald `#34d399`, amber `#fbbf24`, red
-`#f87171`), a 6–14px radius scale, faint resting panel shadows, `--font-display`
-(`"Avenir Next", "Segoe UI", system-ui`; no web font since enterprise Task 3) as
-the display face (wordmark, page titles, display headings only), and
-severity-*shaped* status glyphs (disc / triangle / rounded square / flat dot).
-
-This addendum supersedes, for the current design: the all-square geometry, the
-flat-until-floating rule (panels now carry `--shadow-panel`; floating surfaces
-keep the larger shadows), the old blue accent `#63a1ff`, and the uniform status
-dot. Everything else in this document still governs: density with hierarchy,
-color as signal, mono numerics, motion only for live state, the light-paper
-filed-output counterpoint, and every Don't above except the two rules this
-paragraph names.
-
 ## 2026-09-06 information-architecture addendum (FE-G2; records the approved "Align" canvas)
@@ -413,3 +397,3 @@ decision owner's instruction of 2026-09-06 (FE-A1 decision D13): this addendum
 is the complete approval record, and FE-G3 builds the surfaces from the Align
-artboards named above. Everything else in this document and the 31 Aug
-addendum still governs.
+artboards named above. Everything else in this document still governs (the 31
+Aug reskin addendum is folded into §1–§5 by FE-G4, 2026-09-06).
```

### 4.2 .impeccable.md

```diff
diff --git a/.impeccable.md b/.impeccable.md
index cd8eddd..b9be55e 100644
--- a/.impeccable.md
+++ b/.impeccable.md
@@ -67,3 +67,8 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
 
-**Established visual system (inherit, don't reinvent):**
+**Established visual system (inherit, don't reinvent):** the modern dark terminal
+adopted on 31 August 2026 at the product owner's instruction (graphite ramp, iris
+accent, retuned semantics, a 6–14px radius scale, faint resting panel shadows, the
+native display face for chrome headings only, severity-shaped status glyphs). It
+replaced the earlier blue accent, all-square geometry and flat panels, none of which
+survive in `globals.css` or in this file.
 
@@ -74,3 +79,7 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
   `--caos-muted #99a3b4`, iris accent `--caos-accent #8b93f8` with
-  `--caos-accent-strong #a5abfa` for text on elevated surfaces.
+  `--caos-accent-strong #a5abfa` for text on elevated surfaces. Radii run
+  6/8/10/14px (`--radius-sm` … `--radius-xl`) with `--radius-pill` for chips and
+  status dots; a resting panel carries `--shadow-panel`, dialogs and the context
+  drawer `--shadow-modal`, the report paper `--shadow-paper`; the 3px dialog
+  backdrop blur is the one sanctioned blur.
 - **Semantic color is signal, never decoration:** warning `#fbbf24`,
@@ -89,3 +98,4 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
   skeletons inside `prefers-reduced-motion: no-preference`. No pulse, no enter
-  animation, no dialog entrance motion. Always honor `prefers-reduced-motion`.
+  animation, no dialog entrance motion. Always honor `prefers-reduced-motion`
+  (a global `.01ms` pin on every transition and animation, `.app-shell` paused).
 - **Output aesthetic (Report) is a deliberate counterpoint:** a light
@@ -119,3 +129,4 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
   with a non-color cue: a glyph/shape, a text label, or position. Every
-  `.status` tone draws a distinct glyph shape.
+  `.status` tone draws a distinct glyph shape: success and running a disc,
+  warning a triangle, critical a rounded square, idle a flat dot.
 - Honor `prefers-reduced-motion` for every animation (already wired — keep it
@@ -123,3 +134,5 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
 - Interactive surfaces are keyboard-reachable with a visible focus ring; the
-  cross-pane "Evidence Sync" selection should be operable without a mouse.
+  evidence-chip to context-drawer link (`.evidence-chip.is-linked`) is operable
+  without a mouse, and under `pointer: coarse` every control takes a 44px
+  minimum height.
 
@@ -143,12 +156 @@ toward generic SaaS and not to degrade into raw utilitarian clutter.
     *ornamented*.
-
-## 2026-08-31 reskin addendum
-
-At the product owner's instruction the workspace is now the **modern dark
-terminal**: graphite ramp, iris accent `#8b93f8`, 6–14px radius scale, faint
-resting panel shadows, `--font-display` (`"Avenir Next", "Segoe UI",
-system-ui`; no web font since enterprise Task 3) for chrome headings only, and
-severity-shaped status glyphs. The "Established visual system" palette and the
-flat/all-square details above are superseded for the current design; the
-principles, the paper counterpoint, and the accessibility bar are not. See the
-matching addendum in `DESIGN.md`.
```

### 4.3 PRODUCT.md

```diff
diff --git a/PRODUCT.md b/PRODUCT.md
index 4b01dbb..ab93486 100644
--- a/PRODUCT.md
+++ b/PRODUCT.md
@@ -8,3 +8,3 @@ product
 
-CAOS serves institutional leveraged-finance credit specialists. The primary user is the buy-side credit analyst building a defensible credit view across Deep-Dive, Model Builder, Report Studio, and Command Center. Secondary users are PMs/CIOs scanning posture and change, plus Heads of Research/QA overseeing coverage health, evidence quality, and governance.
+CAOS serves institutional leveraged-finance credit specialists. The primary user is the buy-side credit analyst building a defensible credit view across Portfolio, Credit, Sources, Analysis and its Run tool, Market, Model, Report and Admin (the eight destinations plus Run of `DESIGN.md`'s 2026-09-06 addendum). Secondary users are PMs/CIOs scanning posture and change, plus Heads of Research/QA overseeing coverage health, evidence quality, and governance.
 
```

### 4.4 caos/frontend/docs/control-capability-map.md

Every row now names its served route verbatim from OpenAPI; two rows were
wrong or imprecise: the research-plan row implied the client reads
`GET …/research-plan` (it reads the plan from the run record and posts only to
`…/approve`), and "Review" was not a surface (accept lives on Run, the snapshot
switch on Analysis). Rows added for served routes the surfaces own: `POST
/api/cases` (advanced create), `POST …/runs` (advanced compile), `POST
/api/runs/{id}/upgrade`, `GET`/`POST …/rv`, `POST …/notes/{id}/promote`, the
model export and download routes, and `GET …/deliverables/revisions/{id}`.

```diff
diff --git a/caos/frontend/docs/control-capability-map.md b/caos/frontend/docs/control-capability-map.md
index 31cb553..88a3fe7 100644
--- a/caos/frontend/docs/control-capability-map.md
+++ b/caos/frontend/docs/control-capability-map.md
@@ -2,11 +2,13 @@
 
-This map binds the approved desktop screens to the current production API. It
-is intentionally conservative: an absent contract produces an unavailable
-state, never a browser-derived substitute, and no control is drawn for a route
-the server does not serve. "Served, not drawn" names a contract the server
-serves that no surface renders yet; drawing it is an information-architecture
-decision, not a capability gap. FE-G3 drew the two governance contracts the
-approved Align canvas and FE-A1 D7 assigned (member provisioning and the case
-audit package, both on Admin); withdrawal and notes stay "served, not drawn"
-because no approved artboard draws them.
+This map binds the approved screens (the Align destinations of `DESIGN.md`'s
+2026-09-06 addendum) to the routes the server actually serves (`GET /openapi.json`
+on the combined app; re-checked by FE-G4 on 2026-09-06). It is intentionally
+conservative: an absent contract produces an unavailable state, never a
+browser-derived substitute, and no control is drawn for a route the server does
+not serve. "Served, not drawn" names a contract the server serves that no surface
+renders yet; drawing it is an information-architecture decision, not a capability
+gap. FE-G3 drew the two governance contracts the approved Align canvas and FE-A1 D7
+assigned (member provisioning and the case audit package, both on Admin);
+withdrawal and notes stay "served, not drawn" because no approved artboard draws
+them.
 
@@ -15,4 +17,5 @@ because no approved artboard draws them.
 | Portfolio | Case register and open-credit action | `GET /api/cases` | Served |
-| Portfolio | Document-first intake (files only; issuer, label, types, periods, dispositions and the route come back as labelled machine suggestions) | `POST /api/intake`, `GET /api/cases/{case_id}/intake` | Served |
-| Portfolio | Attention ordering, threshold distance, freshness score | No governed portfolio-summary response | Unavailable; no client ranking |
+| Portfolio | Document-first intake (files only; issuer, label, types, periods, dispositions and the route come back as labelled machine suggestions) | `POST /api/intake`, `GET /api/cases/{case_id}/intake` | Served; the page's one primary action |
+| Portfolio | Create a case by hand | `POST /api/cases` | Served as the advanced control beside intake; the ambiguous-issuer refusal links to it (FE-G3 D10) |
+| Portfolio | Attention ordering, threshold distance, freshness score | No governed portfolio-summary route is served | Unavailable; no client ranking |
 | Credit | Accepted and latest snapshot identity | `GET /api/cases/{case_id}/snapshot`, read once by the shell and rendered by every surface (one authority per screen) | Served |
@@ -20,16 +23,21 @@ because no approved artboard draws them.
 | Credit | Accepted module conclusions and evidence counts | Snapshot artifact ids plus `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served as exact module output |
-| Credit | Normalized binding metric, threshold, tolerance and gap summary | No normalized credit-summary response | Unavailable; no inferred values |
-| Sources | List, read and upload source objects | Existing case source routes | Served |
-| Sources | Withdraw a source | `POST /api/cases/{case_id}/sources/{source_id}/withdraw` | Served, not drawn (D-G; no approved artboard draws it — deferred past FE-G3) |
-| Sources | Analyst notes | `GET`/`POST /api/cases/{case_id}/notes` | Served, not drawn (D-G) |
-| Sources | Claim-to-source coverage matrix | No normalized claim-map response | Unavailable |
-| Analysis | Run stages, live progress, resume and exact artifact output | Existing run, event and artifact routes | Served |
-| Analysis | Deep Research plan review and digest-bound approval | `GET /api/runs/{run_id}/research-plan`, `POST /api/runs/{run_id}/research-plan/approve` | Served and drawn on Run (`/run/`) |
-| Review | Accept exact run snapshot and switch visible accepted snapshot | Existing accept and snapshot-switch routes | Served |
-| Market | Active loan universe, filters, values and source locators | Existing active-universe route | Served |
-| Market | Relative percentile | No deterministic percentile contract | Omitted |
-| Model | Build, worksheet, assumptions, preview, scenario and sign-off | Existing model routes | Served with existing guards |
+| Credit | Normalized binding metric, threshold, tolerance and gap summary | No normalized credit-summary route is served | Unavailable; no inferred values |
+| Sources | List and upload source objects; the immutable source reader renders the listed source's blocks | `GET`/`POST /api/cases/{case_id}/sources` (`GET …/sources/{source_id}` is served and not called) | Served; the upload form is the one write |
+| Sources | Withdraw a source | `POST /api/cases/{case_id}/sources/{source_id}/withdraw` | Served, not drawn (D-G; no approved artboard draws it) |
+| Sources | Analyst notes | `GET`/`POST /api/cases/{case_id}/notes`, `POST …/notes/{note_id}/promote` | Served, not drawn (D-G) |
+| Sources | Claim-to-source coverage matrix | No normalized claim-map route is served | Unavailable |
+| Run | Compile a route by hand | `POST /api/cases/{case_id}/runs` | Served; collapsed to "Advanced: compile a route" on an intake-created run (FE-G3 D11) |
+| Run | Run stages, live progress, resume and exact artifact output | `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/events` (SSE; event names trigger a refetch, payloads are never read), `POST /api/runs/{run_id}/resume`, `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served |
+| Run | Upgrade a run | `POST /api/runs/{run_id}/upgrade` | Served, not drawn (no approved artboard) |
+| Run | Deep Research plan review and digest-bound approval | The persisted plan and its hash are read from the run record; `POST /api/runs/{run_id}/research-plan/approve` (`GET /api/runs/{run_id}/research-plan` is served and not called) | Served and drawn on Run (`/run/`) |
+| Run | Accept the exact run snapshot | `POST /api/runs/{run_id}/accept` | Served; a completed intake run is opened for review and never accepted on the analyst's behalf |
+| Analysis | Accepted artifacts, reader and evidence rail; switch the visible accepted snapshot | `GET /api/cases/{case_id}/artifacts/{artifact_id}`, `POST /api/cases/{case_id}/snapshot/switch` | Served |
+| Market | Active loan universe, filters, values and source locators; workbook upload | `GET /api/cases/{case_id}/rv/loan-universes/active`, `POST /api/cases/{case_id}/rv/loan-universes` | Served |
+| Market | Relative Value record | `GET`/`POST /api/cases/{case_id}/rv` | Served, not drawn (the Relative Value route runs through Run) |
+| Market | Relative percentile | No deterministic percentile contract | Omitted; stated in words |
+| Model | Build, worksheet, assumptions, preview, scenario, revisions, rebase preview and sign-off | `GET`/`POST /api/cases/{case_id}/models`, `GET …/models/{build_id}`, `GET …/models/{build_id}/worksheet`, `GET …/models/assumption-registry`, `POST …/models/previews`, `POST …/models/scenarios`, `GET …/model`, `GET …/model-revisions`, `POST …/model-revisions/rebase-preview`, `POST …/model-revisions/sign-off` | Served with existing guards |
+| Model | Export and download | `POST …/model-revisions/{revision_id}/export`, `GET …/model-revisions/export-statuses`, `GET …/model-revisions/{revision_id}/download`, `GET …/models/{build_id}/download` (`POST …/models/{build_id}/export` is served and not called) | Served and drawn |
 | Model | Tornado (four legacy drivers against the complete current forecast) | `POST /api/cases/{case_id}/models/tornado` | Served and drawn; the sensitivity control |
 | Model | One-way sensitivity | `POST /api/cases/{case_id}/models/sensitivities/one-way` | Served, not drawn (D-F): the tornado is the sensitivity control and covers the same drivers |
-| Report | Draft, autosave, scenario, freeze, filing and export | Existing deliverable routes | Served; client gates global role and server enforces case approver standing |
+| Report | Draft, autosave, scenario, freeze, filing and export | `GET`/`PUT …/deliverables/{pathway}/draft`, `POST …/deliverables/{pathway}/freeze`, `POST …/deliverables/by-id/{id}/approve`, `GET …/deliverables/by-id/{id}/export/{format}` (md, pdf, xlsx links unlock after filing) | Served; client gates global role and server enforces case approver standing |
 | Report | Opinion sign-off on the exact saved revision | `POST /api/cases/{case_id}/deliverables/{pathway}/opinion` | Served |
@@ -37,6 +45,7 @@ because no approved artboard draws them.
 | Report | Filing receipt and request-changes | `GET …/deliverables/by-id/{id}/receipt`, `POST …/by-id/{id}/request-changes` | Served |
-| Admin | Member provisioning (a distinct APPROVER or ADMIN) | `POST /api/cases/{case_id}/members` | Served and drawn on Admin (FE-G3, D7); the control renders only for a current APPROVER/ADMIN role with stored APPROVER/ADMIN case standing, a reader sees the reason, and the filing gate stays on Report |
+| Report | Saved revision read by id | `GET …/deliverables/revisions/{revision_id}` | Served, not drawn |
 | Report | Browser recovery copy | Browser `localStorage`, one slot per subject, case, pathway and browser tab | Served as recovery only; never authority; never offered to another subject |
+| Admin | Member provisioning (a distinct APPROVER or ADMIN) | `POST /api/cases/{case_id}/members` | Served and drawn on Admin (FE-G3, D7); the control renders only for a current APPROVER/ADMIN role with stored APPROVER/ADMIN case standing, a reader sees the reason, and the filing gate stays on Report |
 | Admin | Case audit package | `GET /api/cases/{case_id}/audit-package` | Served and drawn on Admin (FE-G3, D7): a download whose receipt names the `x-caos-sha256` digest; a 404 renders the unavailable state |
-| Admin | Audit rows, bundle integrity, step-up operations | Routes absent in this deployment | Unavailable; requirements only |
+| Admin | Audit rows, bundle integrity, step-up operations | Routes absent in this deployment (the page probes `GET /api/admin/bundle` and renders its 404) | Unavailable; requirements only |
 
```

### 4.5 .impeccable/design.json (sidecar)

Regenerated by a script from `globals.css` (`git diff --stat`: 463 lines):
schemaVersion 2, `colorMeta` for the 24 tokens (neutral ladder and derived
accent tints as tonal ramps), `typographyMeta` for the 16 front-matter roles,
the four shadow tokens, the motion facts (160ms channels, 240ms progress width,
1.6s shimmer, the reduced-motion pin), the five breakpoints, eight component
snippets whose CSS is copied rule-for-rule from `globals.css` (with a `:host`
block carrying the `:root` tokens so each snippet is self-contained), and the
narrative pulled from DESIGN.md §1, the Named Rules and §6.

## 5. Evidence set (WEB-015 shape)

Retained under `.superpowers/sdd/frontend/evidence/g4/`: **270 PNGs** over
**45 labels** at the accessibility sweep's six viewports (1280×800, 1366×768,
1440×1000, 1600×1000, 1920×1080 and 720×900 as the 200 % desktop-zoom target), with
`SHA256SUMS` and `manifest.json` (per capture: label, viewport, URL, digest, page-level
overflow, page errors). Captured by `caos/frontend/test-results/g4-capture.mjs`
(gitignored scratch, one page load per state and six viewport resizes — the 720
captures are the full page, the others the viewport) against the seeded host-control
server on `:8791` after the P1 fixes were built. Every capture reported `overflow: false`
and no page error; the server log shows 0 × 429. Total size 42 MB
(≈ 42 MB measured), the cost of six viewports per state; the set is the one WEB-015 asks
Task 13 to reuse, so nothing was downsampled.

Fixture states reuse the sweep's own route fixtures (`g4-fixtures.mjs`, extracted
verbatim from `scripts/a11y-axe.mjs`); live states come from the smoke-seeded cases and
from this session's own keyless publication (below). The 720 captures were taken by
resizing a loaded page, so the rail strip is not scrolled to the active destination the
way a fresh load scrolls it (`WorkbenchShell.tsx` `scrollIntoView`); the a11y sweep and the
FE-G3 set show the loaded state.

| State | Labels | How the state was reached |
|---|---|---|
| Empty (no run) — every destination | `empty-<destination>` (9) | issuer `Idle` |
| Populated (accepted snapshot) — every destination | `populated-<destination>` (9), `populated-market-rv` | `Northstar-5b9b393b` (accepted Earnings Update run); Market on the Relative Value case with the CP-3 workbook |
| Paused on `PLAN_APPROVAL_REQUIRED` | `paused-run` | `Researchpack-5b9b393b Holdings`, live Deep Research intake |
| Published (keyless Deep Research, WEB-015 publication) | `published-credit`, `published-analysis`, `published-admin`, `published-report-draft`, `published-report-filed` | `ApiResearchpack-5b9b393b Holdings`: plan approved by hash → run succeeded → accepted → draft (digit-free `ANALYST_JUDGMENT` narratives, one evidence citation, model omitted) → opinion signed → freeze queued and rendered by the worker (`PUBLISHED`) → case admin seeded through the store → independent approver provisioned via `POST …/members` → filed as that approver → receipt `rcpt-05af5cb91c1f4db3a0cf`; the filed paper carries the `PENDING APPROVAL` watermark and the FILED review names the receipt digest |
| Report per pathway (draft state as served) | `pathway-<pathway>-report` (6) | each intake case's Report with its pathway template selected; every pathway but Deep Research stays a draft with its model blocker under host control (no READY model keyless) |
| Refusal, live | `refusal-ambiguous-portfolio` | an `alpha`/`beta` two-issuer pack dropped through the surface: `INTAKE_ISSUER_AMBIGUOUS` with the advanced-path sentence (D10) |
| Reader (UX-015) | `reader-portfolio`, `reader-run`, `reader-model`, `reader-admin` | `x-caos-role: READER` |
| Sweep fixtures | `fixture-pending-plan-run`, `fixture-admin-governance`, `fixture-ready-model`, `fixture-ready-report`, `fixture-review-report`, `fixture-filed-report`, `fixture-loading-credit`, `fixture-error-credit`, `fixture-refusal-portfolio` | the a11y sweep's route mocks |

Labels: `empty-admin`, `empty-analysis`, `empty-credit`, `empty-market`, `empty-model`, `empty-portfolio`, `empty-report`, `empty-run`, `empty-sources`, `fixture-admin-governance`, `fixture-error-credit`, `fixture-filed-report`, `fixture-loading-credit`, `fixture-pending-plan-run`, `fixture-ready-model`, `fixture-ready-report`, `fixture-refusal-portfolio`, `fixture-review-report`, `pathway-covenant_refinancing-report`, `pathway-deep_research-report`, `pathway-distressed_restructuring-report`, `pathway-earnings_update-report`, `pathway-full_credit-report`, `pathway-relative_value-report`, `paused-run`, `populated-admin`, `populated-analysis`, `populated-credit`, `populated-market`, `populated-market-rv`, `populated-model`, `populated-portfolio`, `populated-report`, `populated-run`, `populated-sources`, `published-admin`, `published-analysis`, `published-credit`, `published-report-draft`, `published-report-filed`, `reader-admin`, `reader-model`, `reader-portfolio`, `reader-run`, `refusal-ambiguous-portfolio`.

## 6. The three P2s of 31 August

- **Reduce dense Model/Report control groups** — partly closed: FE-G3 moved provisioning to
  Admin and collapsed Run's compile form; this pass moves the Model sign-off panel below
  the worksheet. Assessment A's checklist still scores Model 4/8 and Report 5/8 failures
  (the Report compose column stacks narrative, claim authority, model authority, evidence
  inspector, scenario insert, the six-row bind checklist, four opinion fields and freeze).
  Needs: a progressive-disclosure design for the compose column — a canvas decision (FE-D2
  was skipped by D13).
- **Define task-oriented help** — open; heuristic 10 scored 1/4, no help surface exists,
  the palette searches places only. Needs: a product decision on where help lives (A's
  concrete gap list: "visible snapshot", "source set", "authority slot") and a content
  owner; no served contract is required.
- **Saved views / recent credits only with served contracts** — open with evidence:
  `GET /openapi.json` on this build serves no saved-view, recent-credit or
  portfolio-summary route, so the capability map's "Attention ordering" row stays
  Unavailable and nothing can be drawn. Needs: server routes and a DECISIONS §14 entry.

## 7. Gates

All on the final tree (commit below), from `caos/frontend`:

| Gate | Result |
|---|---|
| `npm run lint` | ESLint: No issues found |
| `npx tsc --noEmit` | TypeScript: No errors found |
| `npm run test:unit` | tests 141, pass 141, fail 0 (140 before this pass; one test added pinning the Report grid and the checkbox rule; two pins added to the Model sign-off test) |
| `npm run build` | Next.js 16.3.3, compiled, 20/20 static pages |
| `npm run a11y` against a fresh-data host-control server on `:8792` built from this tree | `{"routes": 17, "forwarders": 8, "viewports": 6, "combinations": 125, "pendingPlanFixture": true, "adminGovernanceAxeChecks": 2, "readyModelFixture": true, "readyReportFixture": true, "states": ["empty", "populated", "review", "filed", "loading", "error", "refusal"], "modelBuilderAxeChecks": 12, "modelBuilderKeyboardTabChecks": 3, "reportStudioAxeChecks": 3, "reportStudioKeyboardTabChecks": 3, "violations": 0}`; 0 × 429 in the server log |
| `npm run test:workbench` (`CAOS_BROWSER=chromium`, `firefox`, `webkit`, in sequence on `:8792` after the sweep) | chromium 151.0.7922.34 passed 141,939 ms / firefox 153.0 passed 151,011 ms / webkit 26.5 passed 150,039 ms |
| Backend suite and Ruff | not run: no server file changed (`git diff --stat` below) |

Earlier runs in the session, before the last CSS patch (the rail scrollbar gate): the same
a11y result on `:8792`, Chromium smoke passed 142,366 ms and Firefox 151,858 ms; they were
rerun above on the final build.

## 8. Confidence review

Least confident about (ranked), each investigated to the code or a measurement:

1. The relocated Model sign-off panel (the JSX was moved by string surgery) — probed with
   the READY fixture, an assumption edited: `[data-model-approval]` renders below the
   worksheet at 1440 (grid top 415, panel top 735) and 720 (960 / 1392), outside
   `.model-builder-command`, 0 `is-selected` cells on first paint; the smoke's Model
   journey (edit → recalculate → note → save → 409 → rebase → save) passed in three
   engines. Verdict: fine.
2. The evidence-drawer change could break the smoke's chip flow if the host-control CP-0
   artifact cited no block — checked the artifact payload on the seeded server
   (`evidence_refs: [{"block_id": "b00001", "source_id": …}]`) and the smoke passed with
   the new `[data-cited-block]` assertion in three engines. The "Open evidence context"
   button passes no block ids and keeps the source-level sentence by design. Verdict: fine.
3. The rail scroll cue — first patch measured no scrollbar (root cause: inherited
   `scrollbar-color` from `html` disables `::-webkit-scrollbar` in Chromium; Playwright
   also hides scrollbars headless). Fixed at the root (reset to `auto` on the strip) and
   measured with `--hide-scrollbars` disabled: 6 px thumb in Chromium and WebKit. Firefox
   cannot be observed headless (`scrollbar-width: none` on every element under
   Playwright). Verdict: fine in Chromium/WebKit, open in Firefox (platform overlay
   scrollbar; the standard properties are set for it).
4. `.field input:not([type="checkbox"])` — radios: the two radio groups on Report sit in
   labels inside a fieldset, not under `.field` (the audit measured them 13×13 px, not
   stretched), so no radio exclusion was needed. Verdict: fine.
5. `.report-studio` `minmax(0, 5.5fr)` — the paper column becomes 248 px at 1024;
   readable only by the stage's own scroll, but nothing is clipped (probe: `clipped:
   false` at 1024/1100/1280/1366, page overflow false). Verdict: fine; the Model
   workspace has the same shape (recorded).
6. Sub-agent scores are quoted, not re-derived; A's 25/40 is lower than the 31 Aug 34/40
   partly because the instruments differ (pre-correction measurement vs post-correction),
   stated in the critique so the numbers are not read as a regression of the same reading.
7. The 3 FE-G3 second-pass commits are on this branch and #74 has not merged: the PR to
   `main` will show them until #74 lands (or this branch is rebased after it). Open, the
   babysit loop's call.
8. Documents: every hex, token and route named in the four contracts was checked against
   `:root` and the route tables by script (no unknowns); the sidecar's five extra hexes are
   labelled derived tints.

Fixed: the rail patch's root cause (inherited `scrollbar-color`). Verified fine: 1, 2, 4, 5,
8. By-design: the source-level drawer sentence when no block is cited; the 720 captures
   taken by resize (rail unscrolled). Still open: Firefox's rail cue (unobservable
   headless); the unmerged #74 commits on this branch; the Portfolio row primary (a
   pinned decision).

Rewrite tournaments were not run: the standing preamble disables them for this series.

## 9. Commands run and results

```
npm run build                                   # Next.js 16.3.3, 20/20 static pages (three builds this session: baseline, after the P1 fixes, after the rail patch)
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true PORT=8791 CAOS_DATA_DIR=$S/data .venv314/bin/python dev.py   # + worker.py; restarted from this worktree after the move
curl /api/health                                # {"status":"ok","store":true,"bundle":true,"checkpointer":true}
CAOS_URL=http://127.0.0.1:8791 npm run test:workbench   # seeding step: chromium 151.0.7922.34 passed 143,117 ms
node ~/.claude/skills/impeccable/scripts/context.mjs --target caos/frontend/app/globals.css
Agent × 3 (A design review, B detector + overlay, C audit) against :8791; reports under $S/agents/<a|b|c>/report.md
$S/publish.py                                    # approve plan → run succeeded → accept → draft → opinion → freeze PUBLISHED (ApiResearchpack)
DomainStore.add_member(...) + POST /members + POST …/approve as APPROVER   # FILED, receipt rcpt-05af5cb91c1f4db3a0cf
git checkout --detach; git worktree add .claude/worktrees/fe-task-04-design-qa <branch>; git apply $S/wip/tracked.patch; npm ci; npm run build   # the move
find out -type f | shasum                       # chunks byte-identical between the two worktrees' builds; only the build id differs
$S/apply-p1-fixes.py; $S/add-test-pins.py; $S/patch-rail.py; $S/patch-rail2.py
npm run lint / npx tsc --noEmit / npm run test:unit   # 0 issues / no errors / 141 pass
node test-results/g4-report-clip-probe.mjs      # clipped:false at 1024/1100/1280/1366
node test-results/g4-rail-probe.mjs             # chromium/webkit scrollbarHeight 7; firefox scrollbar-width none (headless)
node test-results/g4-dirty-probe.mjs            # approvalBelowGrid true at 1440 and 720; selectedCells 0
CAOS_URL=http://127.0.0.1:8792 npm run a11y     # {"routes": 17, "forwarders": 8, "viewports": 6, "combinations": 125, "pendingPlanFixture": true, "adminGovernanceAxeChecks": 2, "readyModelFixture": true, "readyReportFixture": true, "states": ["empty", "populated", "review", "filed", "loading", "error", "refusal"], "modelBuilderAxeChecks": 12, "modelBuilderKeyboardTabChecks": 3, "reportStudioAxeChecks": 3, "reportStudioKeyboardTabChecks": 3, "violations": 0}
CAOS_URL=http://127.0.0.1:8792 CAOS_BROWSER=<engine> npm run test:workbench   # chromium 151.0.7922.34 passed 141,939 ms / firefox 153.0 passed 151,011 ms / webkit 26.5 passed 150,039 ms
CAOS_URL=http://127.0.0.1:8791 OUT=…/evidence/g4 CASES=… node test-results/g4-capture.mjs   # {"captures": 270, "labels": 45, "overflow": [], "pageErrors": [], "notes": []}
```

`git diff --stat HEAD` before the commit:

```
.impeccable.md                                     |  34 +-
 .impeccable/design.json                            | 473 ++++++++++++++++-----
 DESIGN.md                                          |  54 +--
 PRODUCT.md                                         |   2 +-
 caos/frontend/app/globals.css                      |  16 +-
 caos/frontend/docs/control-capability-map.md       |  59 +--
 caos/frontend/scripts/workbench-smoke.mjs          |   5 +-
 caos/frontend/src/components/WorkbenchShell.tsx    |  12 +-
 caos/frontend/src/components/Workspace.tsx         |  12 +-
 .../src/components/model/ModelBuilder.test.ts      |   6 +-
 .../frontend/src/components/model/ModelBuilder.tsx |  53 +--
 caos/frontend/src/lib/workbench.test.ts            |  11 +
 12 files changed, 511 insertions(+), 226 deletions(-)
```

## 10. What the enterprise candidate still owes (WEB-002, WEB-006, WEB-015)

| Requirement | What this pass leaves | Still owed by the candidate (Task 13) | Owner |
|---|---|---|---|
| WEB-002 — all six document-first pathway journeys in Chromium, Firefox and WebKit at the approved versions | the one Playwright journey green in all three engines on this tree (§7), with the retained per-engine reports under `test-results/<browser>/`; the six intake packs admitted through `POST /api/intake` in the smoke | the journeys **through publication** for every pathway in every engine on the enterprise browser versions: five pathways cannot reach a READY model or a freeze keyless (host control emits no CP-MODEL inputs), so they need the live provider binding and the qualification credential (BLOCKED EXTERNAL, Task 11) | enterprise test owner with the provider credential; CI owner for pinning the approved engine versions in `run-browsers.mjs` |
| WEB-006 — every form with keyboard, screen reader, 200 % and 400 % zoom, reduced motion, forced colors, high contrast | keyboard: the smoke's journeys and focus-return checks (16/16 in A); 200 %: the 720 captures and the a11y sweep, no overflow; reduced motion: the audit's probe (shimmer off, transitions 1e-05 s, state preserved) | screen-reader passes (VoiceOver, NVDA) on every form — A's Sam walk found the rail overflow unannounced, run-on accessible names (`rd-h`, wordmark, evidence `summary`), unnamed complementary landmarks; 400 % reflow; `forced-colors` and high-contrast (no `forced-colors` rule exists in `globals.css`, so status glyphs and the accent focus ring need a manual check) | accessibility reviewer on the candidate build (manual, WEB-006/008); frontend owner for the `forced-colors` block if the review finds a gap |
| WEB-015 — approved preview and publication screenshots for every pathway and representative dense, long-text, multilingual, conditional, held and filed state | this set: every destination and drawn state at six viewports (§5), one real filed publication (Deep Research), held (paused plan) and filed (fixture and live) states, dense (Market loan universe, Model READY fixture) | publication screenshots for the other five pathways (need the live binding above); long-text and multilingual states (no fixture drives them yet — the CJK/Arabic fallback fonts are the host's, `CLAUDE.md` known gaps); conditional states; and the analyst-scope **approval** of each screenshot, which no session can grant | enterprise test owner for approval and the live runs; frontend owner for a long-text/multilingual fixture pack |
