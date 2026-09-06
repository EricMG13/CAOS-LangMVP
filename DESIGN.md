---
name: "CAOS - Credit Agent OS"
description: "A precise, defensible, alert leveraged-finance credit workspace."
colors:
  # The live tokens are caos/frontend/app/globals.css :root; this block names them
  # minus the `--caos-` prefix (FE-A2 §1.2). When the two disagree, the CSS is truth.
  bg: "#0a0c10"
  panel: "#101319"
  elevated: "#181d28"
  subtle: "#202632"
  border: "#242b38"
  border-strong: "#606b7e"
  text: "#e9edf4"
  muted: "#99a3b4"
  accent: "#8b93f8"
  accent-strong: "#a5abfa"
  warning: "#fbbf24"
  critical: "#f87171"
  success: "#34d399"
  paper: "#f7f4ec"
  ink: "#191922"
  paper-meta: "#5d5d68"
  paper-rule: "#a8a498"
  paper-rule-strong: "#6f6c62"
  paper-link: "#2f54c9"
  paper-soft: "#6a6a72"
  paper-success: "#166534"
  paper-warning: "#a24310"
  paper-watermark: "#be5410"
  paper-critical: "#b91c1c"
typography:
  # All families are native stacks (enterprise Task 3 removed the web fonts):
  # --font-display "Avenir Next", "Segoe UI", system-ui; --font-sans the platform
  # sans; --font-mono the platform mono. Sizes are what globals.css renders.
  display:
    fontFamily: "var(--font-display), system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.04
    letterSpacing: "-0.01em"
    note: "Standing answer. The reader and admin display headings use 1.05 with no tracking."
  headline:
    fontFamily: "var(--font-display), system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
    note: "Page title."
  title:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.55
    note: "Panel header, sentence case."
  body:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 650
    lineHeight: 1.35
    note: "Kicker (.meta-label) and field labels, sentence case."
  label-uppercase:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0.09em"
    note: "Table heads and rail group labels; tracking runs .09–.14em by site. Chrome floor is 9px (TOC ids, evidence digests, forecast labels)."
  mono-meta:
    fontFamily: "var(--font-mono), ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.5
    note: "Authority strip, ids, chips, rail meta; 10–11px by site. Mono is for identifiers, digests, timestamps and numerics, never for labels."
  output-title:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "21px"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  output-section:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "0.08em"
    note: "Uppercase."
  output-body:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.62
  output-subtitle:
    fontFamily: "var(--font-mono), ui-monospace, monospace"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1.5
  output-meta:
    fontFamily: "var(--font-mono), ui-monospace, monospace"
    fontSize: "8.5px"
    fontWeight: 500
    lineHeight: 1.45
  output-table-label:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "9px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "0.06em"
    note: "Uppercase."
  output-table-body:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.4
  output-list:
    fontFamily: "var(--font-sans), system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
  output-watermark:
    fontFamily: "var(--font-mono), ui-monospace, monospace"
    fontSize: "26px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.32em"
    note: "16 % alpha, rotated −16°. The full-model appendix scale belongs to the worker's PDF/XLSX renderers and is not in globals.css."
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  pill: "999px"
  note: "2px survives only on the paper's .rd-mark and the critical status square."
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  note: "--space-2xl is declared and read by no rule; hairlines are the literal 1px; the page gutter is the literal 28px."
components:
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "12px"
    note: "Hairline border, --shadow-panel, 46px min-height sentence-case header (13px/600) with 10px 14px padding."
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.bg}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
    note: "min-height 36px (renders 40px), weight 700; hover moves to accent-strong; disabled is 55 % opacity (2.96:1, FE-A2 F-04)."
  button-quiet:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.muted}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  button-small:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.text}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
    note: "min-height 30px, 11px text. A pressed toggle (.is-active, aria-pressed) takes an accent border on a 16 % accent tint with accent-strong text."
  input:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "8px"
    note: "Border {colors.border-strong}; focus is an accent border plus a 3px accent-22 % halo."
  chip-linked:
    backgroundColor: "{colors.accent} at 16%"
    textColor: "{colors.accent-strong}"
    rounded: "{rounded.pill}"
    padding: "0 8px"
    note: "24px evidence chips, mono 10px; at rest accent-strong on a 7 % accent tint with a 65 % accent border; linked adds a 2px accent outline. Chips never invert."
  nav-link-active:
    backgroundColor: "{colors.elevated}"
    textColor: "{colors.accent-strong}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
    note: "Hairline border and a 2px accent leading bar; every rail link shows its 14px stroke glyph and label at every width."
---

# Design System: CAOS - Credit Agent OS

## 1. Overview

**Creative North Star: "The Committee Terminal"**

CAOS is a refined institutional terminal for buy-side credit analysts. It should feel calm enough for investment committee work, live enough for desk posture, and exact enough that every number reads as traceable rather than decorative.

The workspace is dark, dense, and single-mode. Density is earned with fixed panel chrome, aligned numerics, small labels, and restrained state color. The Report Studio and research documents deliberately invert the workspace into light paper: ink on cream, file-ready, and visually distinct from the live analytical surface.

CAOS explicitly rejects friendly consumer SaaS, oversized marketing dashboards, pastel card layouts, decorative gradients, glow effects, and raw terminal dumps. The product can be dense, but it must always be organized.

**Key Characteristics:**
- Dense analytical hierarchy with a 46px sentence-case panel header (13px/600) as the structural unit.
- Color reserved for state, selection, seniority, and evidence lineage.
- Mono numerics and small uppercase labels for desk-readable precision.
- Motion only for live, running, selected, or changed state.
- Light paper output only inside Report Studio and research deliverables.

## 2. Colors

The palette is a restrained dark desk: graphite workspace, cool panels, hairline borders, one iris accent (`accent`, with `accent-strong` for text on elevated surfaces), and semantic colors used only as signal.

### Primary
- **Desk Accent**: Primary action, current selection, active navigation, linked lineage, and live-query affordance.

### Secondary
- **Downstream Consumer**: not implemented — no token and no rule exists in the code (FE-A2 §11). Do not draw it until a token lands in `globals.css`.

### Tertiary
- **Tranche Ramp**: not implemented — seniority is text in the loan table; no tranche colour ramp exists in the code (FE-A2 §11).

### Neutral
- **Graphite Workspace** (`bg`): Page background and deepest table/model canvas.
- **Panel Surface**: Primary framed work surface.
- **Elevated Surface**: Hover, selected resting state, menu background, and nested tools.
- **Hairline Border**: Panel, table, chip, modal, and nav separation.
- **Desk Text**: Primary readable text.
- **Muted Label**: Metadata, labels, inactive controls, and secondary copy.
- **Paper Surface**: Report and research output background only.
- **Paper Ink**: Report and research output primary text.
- **Paper Meta**: Report and research output masthead and supporting metadata.

### Named Rules

**The Signal-Only Color Rule.** Accent and semantic colors are forbidden as decoration. They mean action, selection, status, seniority, or lineage.

**The Dark Workspace Rule.** Analytical surfaces stay in the dark single-mode palette. Light surfaces are reserved for filed output and research paper views.

## 3. Typography

**Display Font:** `--font-display` (Avenir Next on macOS, Segoe UI on Windows, `system-ui` elsewhere) — wordmark, page title, standing answer, reader and admin display headings.
**Body Font:** `--font-sans` (`-apple-system` … `sans-serif`, the platform sans).
**Label/Mono Font:** `--font-mono` (`ui-monospace` … `monospace`, the platform mono).

No web font is shipped (enterprise Task 3 removed the external font dependency; `workbench.test.ts` forbids Google-hosted fonts).

**Character:** One platform sans plus one platform mono. The sans carries all UI prose and labels; the mono carries numerics, ids, digests, timestamps, and desk metadata.

### Hierarchy
- **Display** (600, 30px, 1.04, −.01em, display face): Single focal answer on a surface — the standing answer. Never use for routine labels.
- **Headline** (600, 21px, 1.2, −.01em, display face): The page title.
- **Title** (600, 13px, 1.55, sentence case): Panel headers, dialog headings.
- **Body** (400, 14px, 1.55): Workspace copy, state detail, rail text, and tool bodies.
- **Label** (sans, 10–11px): sentence case at 11px/650 for kickers and field labels; uppercase and tracked (.09–.14em) at 10px/700 for table heads, rail group labels, worksheet tabs and report rail labels. Mono is for identifiers, digests, timestamps and numerics, not for labels. The chrome floor is 9px (TOC ids, evidence digests, forecast labels — FE-A2 F-06).

### Filed Output Scale

Report Studio, research exhibits, print views, and research deliverables use a deliberate paper scale rather than workspace labels: **Output Title** (650, 21px, −.01em), **Output Section** (700, 11px, uppercase, .08em), **Output Body** (400, 12px, 1.62), **Output Subtitle** (600, 10px, mono), **Output Meta** (500, 8.5px, mono), **Output Table Label** (650, 9px, uppercase), **Output Table Body** (400, 10px), **Output List** (400, 11px), and a 26px/700 mono filed-copy watermark at 16 % alpha rotated −16°. The full-model appendix scale belongs to the worker's PDF/XLSX renderers and is not in `globals.css`. These sizes are valid only inside paper/output roots; they must not leak into navigation, buttons, panel headers, or analytical tables.

### Named Rules

**The Numeric Truth Rule.** Financial values, ids, ratings, dates, and confidence scores use mono tabular styling so columns scan and decimals align.

**The No Display Labels Rule.** Product labels, buttons, table headers, and nav chips never use display sizing or decorative typography.

**The Filed Output Exception.** Paper output may use the explicit filed-output scale above to preserve print hierarchy and committee readability. A larger paper title is not a workspace display label.

## 4. Elevation

Depth comes from the `bg` → `panel` → `elevated` → `subtle` ramp, hairlines, 2px inset accent selection bars, and one faint resting panel shadow; the larger shadows mean the object floats above the workflow.

### Shadow Vocabulary
- **Panel Shadow** (`--shadow-panel`, `0 1px 2px rgb(0 0 0 / .25)`): every resting panel.
- **Modal Shadow** (`--shadow-modal`, `0 24px 80px -24px rgb(0 0 0 / .85)`): dialogs and the context drawer. Dialog backdrops are 60 % black with a 3px blur.
- **Popover Shadow** (`--shadow-pop`, `0 12px 32px -12px rgb(0 0 0 / .7)`): declared for a popover the product does not have; no rule reads it.
- **Paper Shadow** (`--shadow-paper`, `0 24px 70px -24px rgb(0 0 0 / .8)`): Report Studio and research document sheets over the dark gutter.

### Named Rules

**The Resting Panel Rule.** A resting panel carries a hairline and `--shadow-panel`, nothing larger; a larger shadow means the object floats above the workflow. (Supersedes the Flat-Until-Floating rule, retired by the 31 Aug addendum.)

## 5. Components

### Buttons
- **Shape:** Compact rectangular controls with 8px corners (6px for `.button.small`, 30px tall with 11px text).
- **Primary:** Accent fill with `bg`-coloured 700 text for committed actions; hover moves to `accent-strong`.
- **Hover / Focus:** 160ms border, background and transform channels; visible focus ring for keyboard users.
- **Quiet:** `.button.quiet` keeps the elevated fill and mutes the text.
- **Pressed toggle:** `.button.is-active` (with `aria-pressed`) takes an accent border on a 16 % accent tint with `accent-strong` text — the linked-chip idiom.
- **Disabled:** 55 % opacity; the primary variant reads 2.96:1 (exempt from 1.4.3, below this document's own "remains readable" bar — FE-A2 F-04, open).

### Chips
- **Style:** Evidence chips are 24px pills in mono 10px: `accent-strong` on a 7 % accent tint with a 65 % accent border.
- **State:** The linked state adds a 2px accent outline and a 16 % tint. Chips never invert. Status is a shape glyph plus a 700 label.

### Cards / Containers
- **Corner Style:** 10px corners, hairline border, `--shadow-panel`.
- **Background:** Panels use Panel Surface; contained tools may use the workspace ground or Elevated Surface.
- **Shadow Strategy:** `--shadow-panel` at rest. Modal, drawer, and paper surfaces use the larger shadow vocabulary.
- **Border:** Hairline Border is mandatory for framed panels.
- **Internal Padding:** 12px body; 46px header.

### Inputs / Fields
- **Style:** Workspace-ground fill, `border-strong` border, Desk Text, muted placeholder, 8px radius, 8px padding.
- **Focus:** Accent border plus a 3px accent-22 % halo (no outline); hover shifts the border 55 % toward text. The focus treatment must survive dark panels and scrollable containers.
- **Error / Disabled:** Error is semantic Critical with text or glyph. Disabled is 55 % opacity (the primary button reads 2.96:1 — FE-A2 F-04).

### Navigation
- **Style:** Rail links show a 14px stroke glyph and the label at every width; no tooltips. Below 900px the rail is a horizontally scrolling strip (Model, Report, Governance and the rail meta sit off-canvas at 720px — FE-A2 F-07, open).
- **Typography:** Sans; the group labels are 10px uppercase tracked; the rail meta is mono 10px.
- **State:** Active is elevated fill, hairline border, `accent-strong` text and a 2px accent leading bar. Hover is elevated fill and text colour without changing layout.

### Enterprise Workbench Anatomy

Every route uses the same ordered contract: the authority strip (credit, visible snapshot, selected run, source set), exactly one page-level primary action, one dominant work region, contextual evidence (evidence chips open the context drawer; Deep-Dive and Command Center carry evidence rails), and sticky approval panels where a governed action waits. Surface kinds preserve specialist behavior: worklists own filter anatomy; analytical objects own conclusion state; Model Builder and Report Studio retain their editor overflow.

- **Decision states:** `loading` (skeleton), `observed-empty`, `error`, `unavailable` (observed 404), `stale` (Model and Report authority changed) and `offline` (a request that never reached the server renders one sentence in the page-level alert, never engine text — FE-G1) render distinctly. `ready` carries no marker of its own, and `partial` renders through warning statuses and inline notes; neither has a dedicated component (FE-A2 F-08). "No material change" is legal only for a successful timestamped `observed-empty` response.
- **Authority:** Every ready conclusion carries observation time, origin, method, approval/ratification, and freshness. `LIVE` describes source origin only. Every surface on a screen renders the shell's one snapshot; no surface mints a second accepted identity (FE-G1).
- **Worklists:** The Cases toolbar is search plus one filter, one action per row; the five-action toolbar and batch state are not implemented (FE-A2 §11; FE-G4 decides whether the rule or the product moves).
- **Utilities:** Not implemented — there is no utility drawer; the one drawer is the evidence context drawer, whose opener is passed from the click and regains focus on Escape.
- **Evidence Atlas:** Not implemented as one inspector; the context drawer and the per-surface evidence rails are what exist. Never show a duplicate inspector.
- **Role composition:** Not implemented — the rail shows the served role read-only; there is no `View: Analyst / PM / QA` switch and it must never grant permission or approval authority if drawn.

### Panel

The shared panel is the signature CAOS frame: Panel Surface, hairline border, 10px radius, `--shadow-panel`, a 46px sentence-case header (13px/600), a 12px body, and — where a region is declared — a focusable scrollable body (`table-wrap`, the worksheet, the loan table are `role="region"` containers). A panel is a section, not a decorative card.

### Status Glyphs

Status meaning must never be color alone. Pair severity color with a drawn glyph, text label, position, or all three. Emoji are forbidden in product chrome.

## 6. Do's and Don'ts

### Do:
- **Do** use `bg`, `panel`, `elevated`, `subtle` and `border` as the core surface ladder.
- **Do** keep dense financial values in mono tabular type.
- **Do** pair every semantic color with a label, glyph, or spatial convention.
- **Do** use the shared class idioms — `.panel`, `.field`, `.status`, `.button`, `.nav-link`, `.evidence-chip`, `.state-block` — and the `StateBlock`, `StateNote`, `LoadState`, `Unavailable` and `MutationReceipt` components before inventing new chrome.
- **Do** honor reduced motion. The only animation is the loading shimmer, confined to `prefers-reduced-motion: no-preference`; the only non-hover transition is the live progress width. There is no running pulse, no flash cue and no dialog entrance motion.
- **Do** reserve Paper Surface and Paper Ink for Report Studio and research deliverables.

### Don't:
- **Don't** drift toward friendly consumer SaaS.
- **Don't** create oversized marketing dashboards.
- **Don't** use pastel card layouts.
- **Don't** add decorative gradients, glow effects, or glassmorphism (the 3px dialog backdrop blur is the one sanctioned blur).
- **Don't** ship raw terminal dumps. Density must stay organized.
- **Don't** encode status or tranche meaning by color alone.
- **Don't** use emoji in product chrome.
- **Don't** add shadows to ordinary panels or cards.
- **Don't** use side-stripe borders, gradient text, huge rounded cards, or identical decorative card grids.

## 2026-08-31 reskin addendum (supersedes where noted)

At the product owner's instruction the workspace moved to the **modern dark
terminal**: a graphite ramp (`#0a0c10` → `#101319` → `#181d28`), iris accent
`#8b93f8`, retuned semantics (emerald `#34d399`, amber `#fbbf24`, red
`#f87171`), a 6–14px radius scale, faint resting panel shadows, `--font-display`
(`"Avenir Next", "Segoe UI", system-ui`; no web font since enterprise Task 3) as
the display face (wordmark, page titles, display headings only), and
severity-*shaped* status glyphs (disc / triangle / rounded square / flat dot).

This addendum supersedes, for the current design: the all-square geometry, the
flat-until-floating rule (panels now carry `--shadow-panel`; floating surfaces
keep the larger shadows), the old blue accent `#63a1ff`, and the uniform status
dot. Everything else in this document still governs: density with hierarchy,
color as signal, mono numerics, motion only for live state, the light-paper
filed-output counterpoint, and every Don't above except the two rules this
paragraph names.

## 2026-09-06 information-architecture addendum (FE-G2; records the approved "Align" canvas)

The workbench's destinations are the rail's eight words plus Run, the tool of
Analysis, with one vocabulary in the URL, the rail, the kicker, the page title
and the tab title (FE-A1 decision D1, "Align"; `docs/DECISIONS.md` §14.23):

| Destination | Route | Kicker | Page title | Tab |
|---|---|---|---|---|
| Portfolio | `/portfolio/` | Portfolio / Surveillance | Monitored credits | CAOS — Portfolio |
| Credit | `/credit/` | Credit / Current state | Current state and what changed | CAOS — Credit |
| Sources | `/sources/` | Sources / Evidence | Documents, extraction and coverage | CAOS — Sources |
| Analysis | `/analysis/` | Analysis / Reader | Accepted analysis | CAOS — Analysis |
| Run (tool of Analysis) | `/run/` | Analysis / Run | Run and acceptance | CAOS — Run |
| Market | `/market/` | Market / Comparison | Governed loan universe | CAOS — Market |
| Model | `/model/` | Model / Forecast | Assumptions, lineage and sign-off | CAOS — Model |
| Report | `/report/` | Report / Publication | Compose, freeze and file | CAOS — Report |
| Admin | `/admin/` | Admin / Governance | Deployment capability | CAOS — Admin |

Route map (D2): `/cases/` → `/portfolio/`, `/command-center/` → `/credit/`,
`/deep-dive/` → `/analysis/`, `/run-console/` → `/run/`, `/rv-screener/` →
`/market/`, `/model-builder/` → `/model/`, `/report-studio/` → `/report/`,
`/admin-studio/` → `/admin/`. Every earlier slug stays a static forwarding page
that replaces history to its new home with the query string intact.

One-home rules: run progress, compilation, acceptance and research-plan
approval live on Run; sign-off, freeze and filing on Report; intake on
Portfolio, posting files only; Analysis reads accepted artifacts; Admin is an
unavailable-capability surface with no control drawn for an unserved route.
The Run tool link and its LIVE badge render on every surface (D12).

Approved canvas: FE-D1 "CAOS Workbench Directions",
https://claude.ai/code/artifact/5de66539-7954-45fd-8f8f-d40349fe736e, direction
Align chosen 2026-09-05 by the decision owner ("Align, no changes — record it
and commit"; `.superpowers/sdd/frontend/frontend-d1-directions.md` §3).
Artboards: "Align — Shell 1440", "Align — Shell 720", "Align — Analysis
paused" on page 1 (`docs/design/canvas/workbench-directions/Main.dc.html`,
with one working file per artboard beside it and `canvas.json`). Retained
export: `.superpowers/sdd/frontend/design/fe-d1-align-shell-1440.png`, SHA-256
`45ea2f8ffa4bfe72b88acba992fe561664986c1af2c0dc3de4108d49cb9cb51e`. The canvas
binds the layout, hierarchy, states and copy of those artboards; tokens stay in
`caos/frontend/app/globals.css`. FE-D2 (hi-fi screens) is skipped by the
decision owner's instruction of 2026-09-06 (FE-A1 decision D13): this addendum
is the complete approval record, and FE-G3 builds the surfaces from the Align
artboards named above. Everything else in this document and the 31 Aug
addendum still governs.
