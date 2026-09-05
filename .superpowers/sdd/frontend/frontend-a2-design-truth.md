# FE-A2 — Design-system truth sheet

Date: 2026-09-05. Tree: `claude/frontend-design-truth-ca9b32` at `ea42a2d` (clean; this report, the atlas and two scripts are the only additions, all under `.superpowers/sdd/frontend/`). Assessment only: no source, style, test or plan file changed.

Truth here means **what `caos/frontend/app/globals.css` and `src/components/**` do**, measured in Chromium against the built static export served by the host-control server (`python caos/server/dev.py`, port 8773, `CAOS_PROVIDER=host_control`, `AGENT_EXECUTION_ENABLED=true`, worker beside it). Every value below carries the `globals.css` line that defines it (written `:NNN`), or the component `file:line` that renders it. Where a document says something else, the document is the defect (frontend addendum), and the delta table at the end tells FE-G4 what to write.

Scope note on tooling: the impeccable skill's `document` command is an interview (it stops to ask for a north star, colour names and elevation philosophy) and `extract` is a refactoring flow, so neither was run as a command. I applied `document`'s scan-mode steps 1–2 by hand (custom properties, component library, rendered output) and ran the skill's mechanical detector as a draft; its two findings are assessed in §9. The `.impeccable/design.json` sidecar was read and is stale (§10).

Atlas: `.superpowers/sdd/frontend/design/atlas/` — 122 PNGs, named `<viewport>-<NN>-<screen>.png` for full pages and `<viewport>-c-<component>.png` for element clips; `1440` is 1440×1000 and `720` is 720×900 (the a11y sweep's 200 % desktop-zoom viewport). Index in §12. Computed styles, rendered platform fonts and element geometry are in `design/atlas-measurements.json`; the two scripts that produced everything are `design/atlas.mjs` and `design/contrast.mjs`.

---

## 1. Tokens in `globals.css` (`:root`, lines 1–48)

Only one stylesheet defines tokens. `ModelBuilder.module.css` consumes them and defines none. No TSX carries a hex literal except `themeColor: "#0a0c10"` in `app/layout.tsx:15`, and only two inline styles exist, both live geometry (`Workspace.tsx:1494` progress width, `ModelBuilder.tsx:289` tornado bar position).

### 1.1 Font stacks (`:2–4`)

| Token | Value | Rendered on this Mac (Chromium 1.62 / CDP platform fonts) | DESIGN.md / .impeccable.md |
|---|---|---|---|
| `--font-sans` | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` | `.SF NS` (San Francisco) | **Contradicts** DESIGN.md §3 "Inter via `var(--font-sans)`" and .impeccable.md:77 "Inter (sans)". Enterprise Task 3 (`92626bf`) removed Inter. |
| `--font-display` | `"Avenir Next", "Segoe UI", system-ui, sans-serif` | `Avenir Next Demi Bold` for weight 600 (h1, standing answer, admin display) | **Contradicts** both 31 Aug addenda ("Space Grotesk as the display face"). Space Grotesk never shipped after Task 3; on Windows this resolves to Segoe UI, on Linux to `system-ui`. |
| `--font-mono` | `ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace` | `Menlo` (Chromium maps `ui-monospace` to Menlo here; SF Mono is not installed system-wide) | **Contradicts** DESIGN.md §3 "JetBrains Mono" and .impeccable.md:77. |

Body composes `var(--font-sans), ui-sans-serif, system-ui, sans-serif` (`:53`); display headings compose `var(--font-display), var(--font-sans), ui-sans-serif, sans-serif` (`:69`, `:100`, `:363`, `:394`, `:409`).

Cross-platform caveat that FE-D1/D2 must design for: the display face is **whatever the host has**. Weights 650 (`.meta-label` `:101`, `.rd-title` `:536`, `.rd-table thead th` `:546`) and 750 (`.worksheet-cell.is-bold` `:441`) are real intermediate instances only on variable system faces (SF renders them; measured `fontWeight: 650` on `.meta-label`); Segoe UI and Liberation snap them to 700. Figma has no 650, so the canvas must state "Semibold + 50" or pick 600/700 and say which.

### 1.2 Colour (`:8–31`)

| Token | Value | Role in the CSS | DESIGN.md front matter (`:5–38`) | .impeccable.md (`:66–72`) |
|---|---|---|---|---|
| `--caos-bg` | `#0a0c10` | page, inputs, dag tiles, source blocks, worksheet scroll, authority strip, dropzone | `workspace-bg #0a0a0f` — contradicts (addendum `:389` corroborates) | `#0a0a0f` — contradicts (addendum `:141` "graphite ramp" corroborates without values) |
| `--caos-panel` | `#101319` | panels, dialogs, worksheet cells, palette group labels | `panel #11131d` — contradicts (addendum corroborates) | `#11131d` — contradicts |
| `--caos-elevated` | `#181d28` | hover/selected fills, buttons, worksheet heads, skeleton bars, assumptions/tornado asides | `elevated #1d2030` — contradicts (addendum corroborates) | `#1d2030` — contradicts |
| `--caos-subtle` | `#202632` | button hover fill (`:138`), shimmer highlight (`:204`) | absent | absent |
| `--caos-border` | `#242b38` | every hairline | `border #34384a` — contradicts | `#34384a` — contradicts |
| `--caos-border-strong` | `#606b7e` | input/button/dialog borders, scrollbar thumb, standing-answer rule | absent | absent |
| `--caos-text` | `#e9edf4` | text | `text #e6e6ef` — contradicts | `#e6e6ef` — contradicts |
| `--caos-muted` | `#99a3b4` | labels, meta, idle status, muted copy | `muted #a1a1b5` — contradicts | `#a1a1b5` — contradicts |
| `--caos-accent` | `#8b93f8` | primary button, focus ring, selection bar, running status, progress, brand mark, chips | `accent #63a1ff` — contradicts; addendum `:390` corroborates | `:69` `#63a1ff` contradicts; addendum `:141` corroborates |
| `--caos-accent-strong` | `#a5abfa` | active nav text, link hover, chip text, lineage code, primary hover | absent | absent |
| `--caos-warning` | `#fbbf24` | warning status, flag, callout.warning, worksheet input fill | `warning #f5a524` contradicts; `warning-bright #fbbf24` matches the value under the wrong name; addendum "amber #fbbf24" corroborates | contradicts (`#f5a524`) |
| `--caos-critical` | `#f87171` | critical status, `.error`, danger button, global error | `critical #ef4444` contradicts; `critical-bright #f87171` matches; addendum corroborates | contradicts (`#ef4444`) |
| `--caos-success` | `#34d399` | success status, receipt, loan positive | `success #22c55e` contradicts; `success-bright #4ade80` also wrong; addendum "emerald #34d399" corroborates | contradicts (`#22c55e`) |
| `--caos-paper` | `#f7f4ec` | paper surface, rd-mark text | `paper #f7f5ee` — contradicts | absent (says "cream") |
| `--caos-ink` | `#191922` | paper text, mast rules, rd-mark | `paper-ink #16161e` — contradicts | `:85` "ink #16161e" — contradicts |
| `--caos-paper-meta` | `#5d5d68` | paper meta, muted, idle status on paper | `paper-meta #5c5c66` — contradicts | absent |
| `--caos-paper-rule` | `#a8a498` | paper border, table head rule, page divider | `paper-rule #9c998e` — contradicts | absent |
| `--caos-paper-rule-strong` | `#6f6c62` | paper button border | corroborates | absent |
| `--caos-paper-link` | `#2f54c9` | paper buttons, paper focus ring | `paper-link #1f4fa0` — contradicts | absent |
| `--caos-paper-soft` | `#6a6a72` | **defined, used by no rule** | corroborates the value | absent |
| `--caos-paper-success` | `#166534` | paper status success | corroborates | absent |
| `--caos-paper-warning` | `#a24310` | paper status warning | corroborates | absent |
| `--caos-paper-watermark` | `#be5410` | watermark at 16 % alpha | corroborates | absent |
| `--caos-paper-critical` | `#b91c1c` | paper `.error`, critical status | corroborates | absent |

Doc-only colours with **no token and no rule**: `consumer #c4b5fd`, `idle #3f3f46` (idle status uses `--caos-muted`, `:170/:176`), `success-bright`, `warning-bright`, `critical-bright` as separate roles, `scroll-shadow`, the five `tranche-*` hues, `paper-note`, `paper-subhead`. The tranche ramp is not implemented anywhere in the frontend (`grep tranche` returns nothing); the loan table encodes ranking as text and signed changes as success/critical/muted (`:324–326`).

Derived colours: 35 `color-mix(in srgb, …)` expressions compose every tint from the tokens above (chip fill accent 7 %, callout accent 6 % over elevated, worksheet fills 10–28 %, receipt success 8 %, focus halo accent 22 %, selection accent 34 %, rail and top bar `panel 82 % + bg` = `#0f1217`). Their resolved values are in the contrast table (§7).

### 1.3 Spacing (`:32–37`)

| Token | Value | Uses | DESIGN.md `spacing:` (`:193–199`) | .impeccable.md |
|---|---|---|---|---|
| `--space-xs` | 4px | gaps, small padding | `xs 4px` corroborates | — |
| `--space-sm` | 8px | control padding, grid gaps | `sm 8px` corroborates | — |
| `--space-md` | 12px | panel body, callouts, button inline padding | `md 12px` corroborates | — |
| `--space-lg` | 16px | grid gap, dialog body, rail padding | `lg 16px` corroborates | — |
| `--space-xl` | 24px | content padding-top, section rhythm | `xl 24px` corroborates | — |
| `--space-2xl` | 32px | **defined, used by no rule** | absent | — |
| — | `hairline 1px` in DESIGN.md | no token; borders are literal `1px` | doc-only | — |

Literal spacings outside the scale that the layout depends on: content gutter 28px (`:113`, `:98`, `:108`), rail width 224px (`:67`) / 156px below 1100px (`:570`), top bar min-height 76px (`:98`; renders 83px at 1440 because the kicker+title stack is 13+3+25 plus padding), panel header min-height 46px (`:124`), authority strip min-height 36px (`:108`), drawer width `min(440px, 100vw)` (`:257`), dialog width `min(680px, calc(100% − 32px))` (`:239`), worksheet cell height 23px (`:431`), loan cell padding `5px 7px` (`:319`), reader column max 780px (`:393`), content max 1600px / report 1800px (`:113–114`), grid 12 columns with 16px gap (`:118`).

### 1.4 Radius (`:38–42`)

| Token | Value | Uses | DESIGN.md `rounded:` (`:189–192`) | .impeccable.md |
|---|---|---|---|---|
| `--radius-sm` | 6px | `.button.small`, `kbd`, scrubber, tornado track, `.report-paper` | `sm 2px` — contradicts | addendum `:141` "6–14px radius scale" corroborates |
| `--radius-md` | 8px | buttons, inputs, nav links, dag tiles, brand mark, lineage code | `md 6px` — contradicts | — |
| `--radius-lg` | 10px | panels, callouts, dropzone, receipts, action states, report cards | absent | — |
| `--radius-xl` | 14px | dialogs, drawer (left corners only `:257`) | absent | — |
| `--radius-pill` | 999px | chips, status dots, progress track, scrollbar thumb | `pill 999px` corroborates | — |
| literal | 2px | `.rd-mark` (`:534`), critical status square (`:174`) | `sm 2px` matches these two literals only | — |
| literal | 50 % | disc glyphs, authority dot | — | — |

DESIGN.md prose "modest corners (6px)" (`:320`, `:330`, `:359`) describes the pre-reskin geometry; the addendum (`:391`) supersedes it without giving the mapping above.

### 1.5 Shadow (`:43–46`)

| Token | Value | Uses | DESIGN.md §4 (`:308–311`) |
|---|---|---|---|
| `--shadow-panel` | `0 1px 2px rgb(0 0 0 / .25)` | `.panel` (`:120`), `.source-workspace` (`:284`) | absent from §4; addendum `:396` "panels now carry `--shadow-panel`" corroborates and supersedes "Flat-Until-Floating" |
| `--shadow-pop` | `0 12px 32px -12px rgb(0 0 0 / .7)` | **defined, used by no rule** | "Popover Shadow `0 8px 28px -10px rgba(0,0,0,0.8)`" — contradicts the value; there is no popover in the product |
| `--shadow-modal` | `0 24px 80px -24px rgb(0 0 0 / .85)` | `dialog` (`:228`) — palette, accept, discard, drawer | "Modal Shadow … 0.9" — alpha contradicts |
| `--shadow-paper` | `0 24px 70px -24px rgb(0 0 0 / .8)` | `.report-paper` (`:469`) | "Paper Shadow … 0.85" — alpha contradicts |
| literal | `inset 2px 0 0 var(--caos-accent)` | selected rows/toc/blocks (`:293`, `:301`, `:338`, `:389`) | not documented; this is the selection bar idiom |
| literal | `inset 0 0 0 2px var(--caos-accent)` | selected worksheet cell (`:443`) | — |
| literal | `0 0 0 3px accent 22 %` | input focus halo (`:152`; module `:124`) | §5 "visible focus ring" corroborates loosely |
| literal | `0 0 0 3px accent 18 %` | authority dot halo (`:112`) | — |
| backdrop | `rgb(0 0 0 / .6)` + `backdrop-filter: blur(3px)` (`:229`) | dialogs | not documented; note the .impeccable.md ban on glassmorphism (`:379`) — a 3px backdrop blur behind modals is the one place the product blurs |

### 1.6 Easing and duration (`:47`)

| Token | Value | Uses |
|---|---|---|
| `--ease-out` | `cubic-bezier(.25, 1, .5, 1)` | every `transition` (ten rules in `globals.css` plus one in the module CSS, all 160ms except the 240ms progress width) and `caos-dialog-in` |
| literal | `ease-out` | `caos-fade-in` backdrop (`:235`) |
| literal | `linear` | `caos-shimmer` 1.6s infinite (`:204`) |

No `--duration-*` token exists; 160ms is written eleven times. `color-scheme: dark` (`:48`) is the only scheme; there is no light theme and no `prefers-color-scheme` rule.

---

## 2. Type ramp as used

Measured from `getComputedStyle` at 1440 (`atlas-measurements.json`); family column is the resolved stack head. `body` is 14px / 1.55 (21.7px) `-apple-system` (`:54`), which is the base every unset element inherits. Weights marked ★ are intermediate and platform-dependent (§1.1).

### 2.1 Workspace (dark chrome)

| Role | Element / class | Size | Weight | Line height | Tracking | Family | Case | Defined |
|---|---|---|---|---|---|---|---|---|
| Wordmark | `.wordmark` "CAOS" | 17px | 600 | 1 (17px) | .1em | display (Avenir Next) | as written | `:69` |
| Wordmark sub | `.wordmark small` "Credit Agent OS" | 9.5px | 500 | 1.3 | .12em | sans | uppercase | `:71` |
| Brand mark glyph box | `.brand-mark` | 12px (font, unused: SVG) | 700 | 1 | — | mono | — | `:72` |
| Rail group label | `.nav-label` | 10px | 700 | 1.55 (inherited) | .14em | sans | uppercase | `:75` |
| Rail link | `.nav-link` | 14px | 400 | 1.55 | — | sans | as written | `:79` (inherits body) |
| Rail shortcut / LIVE | `.nav-link .shortcut` | 10px | 400 | normal | — | mono | as written | `:93` |
| Rail meta | `.rail-meta` | 10px | 400 | 1.5 | — | mono | as written | `:96` |
| Kicker | `.meta-label` | 11px | 650★ | 1.35 | — | sans | as written | `:101` |
| Page title | `.topbar-heading h1` | 21px | 600 | 1.2 | −.01em | display | as written | `:100` |
| Authority strip | `.authority-strip` / `b` | 11px | 400 / 600 | 1.4 | — | mono | as written | `:108/:111` |
| Panel header | `.panel-header h2, h3` | 13px | 600 | 1.55 | 0 | sans | **sentence case** (`text-transform: none` explicit) | `:125` |
| Panel meta | `.panel-meta` | 10px | 600 | 1.35 | — | sans | as written | `:126` |
| Body | `body`, `td`, `p` | 14px | 400 | 1.55 | — | sans | — | `:54` |
| Muted / hint | `.muted` | inherits (14px; 12px inside `.dropzone label span` `:347`) | 400 | — | — | sans | — | `:134` |
| Field label | `.field label` | 14px | 700 | 1.55 | .06em | sans | as written | `:149` |
| Table head | `th` | 10px | 700 (UA bold) | 1.55 | .09em | sans | uppercase | `:159` |
| Caption | `caption` | 10px | 600 | — | .06em | sans | as written | `:166` |
| Status | `.status` | inherits (14px) | 700 | — | — | sans | as written (`ACTIVE · v1`, `0 CHANGES` are authored caps) | `:169` |
| Mono meta / ids | `.mono`, `.num` | inherits | 400 | — | — | mono, `tabular-nums` on `.num` | — | `:135–136` |
| Evidence chip | `.evidence-chip` | 10px | 400 | 1.3 | — | mono | as written | `:190` |
| Button | `.button` | 14px | 400 (primary 700) | 1.55 | — | sans | as written | `:137/:142` |
| Small button | `.button.small` | 11px | 400 | 1.55 | — | sans | as written | `:147` |
| kbd | `.palette-hint kbd`, `.top-actions kbd` | 10px | 600 | 1.4 | — | mono | — | `:254` |
| Palette hint | `.palette-hint` | 10px | 400 | — | — | sans | — | `:252` |
| Drawer title | `.drawer-header h2` | 16px | 700 (UA) | 1.55 | — | sans | — | `:259` |
| Flag | `.flag` (UNAVAILABLE, RECOVERY COPY) | 10px | 700 | 1 | .08em | mono | authored caps | `:337` |
| Section heading | `.section-heading h3` / `span` | 11px / 10px | 600 / 400 | — | — | sans | — | `:505–506` |
| DAG edge | `.dag-edge` "→" | 12px | 400 | 1 | — | mono | — | `:645` |
| DAG open cue | `.dag-node-open` | 10px | 700 | — | .06em | sans | uppercase | `:275` |
| Standing answer (display) | `.standing-answer > h2` | 30px | 600 | 1.04 | −.01em | display | as written, max 30ch | `:363` |
| Standing answer basis | `.standing-answer > p` | 14px | 400 | 1.55 | — | sans (measured Menlo for the `.mono.muted` line) | max 76ch | `:364` |
| Credit head | `.credit-authority-head h2` | 18px | 700 (UA) | 1.55 | — | sans | — | `:361` |
| Authority metric | `.authority-metrics strong` | 16px | 700 | 1.55 | — | sans (`.mono`/`.num` on two of four) | — | `:368` |
| Proof register count | `.proof-register strong` | 22px | 700 | — | — | mono, accent | — | `:379` |
| Reader title (display) | `.analysis-reader > h2`, `.admin-intro h2` | 30px | 600 | 1.05 | none | display | max 32ch (admin) | `:394/:409` |
| Reader lead | `.analysis-lead` | 16px | 400 | 1.55 | — | sans, muted | — | `:395` |
| Reader copy | `.analysis-copy p` / `h3` | 14px / 16px | 400 / 700 | 1.72 / 1.55 | — | sans | — | `:397–398` |
| TOC id | `.analysis-toc button .mono` | **9px** | 400 | — | — | mono | — | `:390` |
| Evidence card id / authority digest | `.analysis-evidence-card .mono`, `.analysis-evidence-authority .mono` | **9px** | 400 | — | — | mono | — | `:404/:406` |
| Source reader title | `.source-reader > h2` | 22px | 700 (UA) | 1.55 | — | sans | — | `:296` |
| Source region head | `.source-region-head h2`, `.source-support h2`, `.credit-proof > h2`, `.analysis-evidence > h2` | 15px | 700 (UA) | 1.55 | — | sans | — | `:290/:375/:402` |
| Source block | `.source-document-block button` | 14px | 400 | 1.7 | — | sans | — | `:299` |
| Worksheet tab | `.worksheet-tab` | 10px | 700 | — | .08em | sans | uppercase | `:424` |
| Worksheet grid | `.worksheet-grid` | 10px | 400 (750★ `.is-bold`) | 1.3 | — | mono, `tabular-nums` | — | `:429/:441` |
| Worksheet note | `.worksheet-authority-note` | 11px | 400 | — | — | sans, muted | — | `:427` |
| Lineage code | `.lineage-code` | 14px | 400 | — | — | mono, accent-strong on bg | — | `:454` |
| Loan table | `.loan-table` | 10px | 400 | 1.35 | — | mono, `tabular-nums` | heads uppercase .09em via `th` | `:318` |
| Forecast labels (module) | `.forecastValues label`, `.control`, `.signOff label` | **9px** | 700 | — | .04em | sans | uppercase | `ModelBuilder.module.css:86–97` |
| Scrubber / model select | `.scrubber`, `.control select` | 11px | 600 | 1.2 | — | mono | — | module `:111` |
| Report section nav | `.report-section-nav button` / `> span` / `small` | 14px / 10px / **9px** | 400 | — | — / — / .08em | sans / mono / sans | — / — / uppercase | `:475–479` |
| Report rail labels | `.report-history h3`, `.report-optional summary` | 10px | 700 / 600 | — | .12em / .08em | sans | uppercase | `:481/:484` |
| Report field meta | `.field-meta`, `.history-entry > span`, `.report-actions > span` | 10px | 400 | — | — | mono / sans / sans | — | `:498/:486/:471` |
| Evidence source code | `.evidence-source-list summary code` | **9px** | 400 | — | — | mono | — | `:510` |

Five chrome rules sit **below DESIGN.md's "explicit 10px floor on desktop"** (`:290`): `:390`, `:404`, `:406`, `:479`, `:510` in `globals.css` and `:93`, `:99` in the module CSS. Recorded as truth (9px is the real chrome floor) and as finding F-06 for the rule owner.

### 2.2 Paper scale (Report Studio proof stage; `.paper .deliverable-document .rd-*`, `:520–565`)

| Role | Class | Size | Weight | Line height | Tracking | Family | Case | DESIGN.md `output-*` (`:73–188`) |
|---|---|---|---|---|---|---|---|---|
| Masthead brand | `.rd-mast-brand` | 10px | 700 | 1.35 | .15em | mono, ink | uppercase | no entry |
| Masthead mark | `.rd-mark` "C" | 10px | 700 | 1 | 0 | mono, paper on ink, 14×14, r2 | uppercase | no entry |
| Masthead meta | `.rd-mast-meta` | 9px | 600 | 1.35 | .1em | mono, paper-meta | uppercase | no entry |
| Title | `.rd-title` | 21px | 650★ | 1.2 | −.01em | sans, ink | as written | `output-title 21/650/1.2` **corroborates** |
| Subtitle | `.rd-subtitle` | 10px | 600 | 1.5 | — | mono, paper-meta | — | `output-subtitle 9.5/600/1.45` contradicts |
| Identity line | `.rd-identity` | 8px | 400 | 1.45 | — | mono (via `.mono`), paper-meta | — | no entry |
| Masthead facts | `.rd-masthead-facts` / `dt` / `dd` | 8.5px | 500 / 700 / 500 | 1.45 | — | mono, paper-meta; `dd` **also paper-meta** because `:527` references the undefined `--caos-paper-ink` (the token is `--caos-ink`), so the declaration is dropped and the value inherits (F-11) | — | `output-meta 8.5/500/1.45/.08em` corroborates size, weight, leading; tracking is not set in CSS |
| Page band | `.rd-band` | 8.5px | 700 | 1.4 | .12em | mono, paper-meta | uppercase | no entry |
| Section head | `.rd-h` | 11px | 700 | 1.55 | .08em | sans, ink, 1px ink rule | uppercase | `output-section 14/650/1.3` **contradicts** |
| Section authority | `.rd-h-sub` | 8px | 600 | 1.4 | .04em | mono, paper-meta | as written | no entry |
| Column head (inside `.rd-cols`) | `.rd-col .rd-h` | 9px | 700 | — | .08em | sans, paper-rule underline | uppercase | no entry |
| Body | `.rd-body` | 12px | 400 | 1.62 | — | sans, ink, max 72ch, `text-wrap: pretty` | — | `output-body 13/400/1.6` **contradicts** (12px); `output-prose 9.4/1.62` matches leading only |
| Table head | `.rd-table thead th` | 9px | 650★ | 1.3 | .06em | sans, paper-meta | uppercase | `output-table-label 7.8/600/1.25 mono` **contradicts** |
| Table body | `.rd-table tbody th, td` | 10px | 400 | 1.4 | — | sans, ink | — | `output-table-body 9.3/400/1.45` contradicts |
| Profile row | `.rd-prow` / `.rd-plbl` | 11px | 400 / 550★ | 1.45 | — | sans | — | no entry |
| List item | `.rd-list li` (4px square ink bullet) | 11px | 400 | 1.5 | — | sans | — | `output-list 9.2/400/1.5` contradicts |
| Note | `.rd-note`, `.rd-chart-label` | 9px | 400 italic | — | — | sans, paper-meta | — | no entry |
| Footer | `.rd-foot` | 8px | 600 | 1.4 | .06em | mono, paper-meta | uppercase | no entry |
| Empty | `.rd-empty` | 12px | 400 | — | — | sans, paper-meta | — | no entry |
| Watermark | `.rd-wm span` | 26px | 700 | 1 | .32em | mono, watermark 16 % alpha, rotated −16° | authored caps | `output-watermark 26/700/1` corroborates |

Not in the web CSS at all: every `appendix-*` entry (5.2–7px; the model appendix is rendered by the worker's PDF/XLSX renderers, not by this stylesheet), the three `emergency-*` entries (there is no fatal error boundary component; `app/` has `layout`, `page`, `not-found` only), `mobile-readable-min` (no phone breakpoint forces 12px), `narrative-subhead 0.95rem` (no rule). The paper scale stays inside `.paper`/`.deliverable-document` roots — the "must not leak into chrome" rule holds: no `.rd-*` class is used outside `DeliverableDocument.tsx`.

---

## 3. Component anatomy

Class names are the CSS contract (the frontend has no component library; DESIGN.md's `Panel`, `TextInput`, `ScopeToggle`, `StatusGlyph`, `ConceptNav` `:371` and .impeccable.md's `<Panel>`, `.tabular`, `.transition-caos`, `.caos-running`, `.caos-enter` `:78–83` do not exist in `src/` or the CSS). Screenshots: `1440-…` and `720-…` prefixes in the atlas.

### 3.1 Shell (`WorkbenchShell.tsx`)

**App shell** `div.app-shell` — grid `224px minmax(0,1fr)` (`:67`); 156px rail below 1100px (`:570`); block flow below 900px (`:575`). Shots `1440-01-cases`, `720-01-cases`.

**Rail** `aside.rail[aria-label="Primary navigation"]` (`:68`, `WorkbenchShell.tsx:257`) — sticky, `100dvh`, background `panel 82 % over bg` (`#0f1217`), right hairline, padding `24 12 16`. Children in order: `a.wordmark` → `nav.nav-group[aria-label=Workflows]` (`div.nav-label` "Workspace" + seven `a.nav-link`) → optional `nav.nav-group[aria-label="<Workflow> tools"]` ("Analysis tools" with the `Run` link, on Analysis routes) → `div.rail-spacer` → `nav.nav-group.governance-nav` ("Governance" + `Admin`) → `div.rail-meta` (role, issuer, "Desktop workbench"; three mono 10px lines). Clip `1440-c-rail`. **At 720 the rail becomes a horizontal strip** (`:576–582`): flex row, `overflow-x: auto`, thin scrollbar, `wordmark small` hidden; measured geometry shows the rail 121px tall with `rail-meta` at x = 1113, i.e. Model, Report, Governance and the meta sit off-canvas to the right and are reached only by horizontal scroll or by the active link's `scrollIntoView` (`WorkbenchShell.tsx:151`) — see `720-13-model-builder-ready`, where the wordmark is scrolled to "AOS". Finding F-07.

**Wordmark** `a.wordmark` (`:69`, `WorkbenchShell.tsx:258`) — `span.brand-mark` (30×30, 1px accent border, r8, accent stroke SVG `>_`, hover fills accent 16 %) + `span` "CAOS" 17px display .1em + `small` "CREDIT AGENT OS" 9.5px .12em uppercase muted. Clip `1440-c-wordmark`.

**Nav link** `a.nav-link` (`:79–86`) — `min-height 38px` (renders 40), flex, r8, transparent border, muted text; `span.nav-glyph` (14×14 SVG, currentColor) + `span.nav-text` (ellipsis) + optional `span.shortcut` (mono 10px; carries `LIVE` for a running run). Hover: elevated fill, text colour. Active (`.active` / `[aria-current=page]`): hairline border, elevated fill, accent-strong text, and a 2px accent bar at `left:-1px; top/bottom 8px` (`:85`) — selection is shape + position + hue. Clip `1440-c-nav-hover`.

**Top bar** `header.topbar` (`:98`, `WorkbenchShell.tsx:291`) — `min-height 76px` (measures 83 at 1440, 123 at 720), same 82 % panel fill as the rail, bottom hairline, grid `1fr auto`, padding `16 28`. Left `div.topbar-heading`: `span.meta-label` kicker ("Portfolio / Surveillance") + `h1` (21px display). Right `div.top-actions`: optional `a.button.quiet` "Sources & evidence" (hidden on Sources), `select#case-select` (36px, r8, bg fill, border-strong, 180–260px wide), `button#command-palette-trigger.button.small` "Command ⌘K" (`kbd` 10px mono). Clip `1440-c-topbar`, `720-c-topbar`.

**Authority strip** `div.authority-strip[role=region][aria-label="Visible authority"][tabindex=0]` (`:108–112`, `WorkbenchShell.tsx:306`) — 36px, bg fill, bottom hairline, mono 11px muted with `b` in text colour weight 600, `overflow-x: auto`, `white-space: nowrap`; items separated by a 1px × 12px rule via `span + span::before`. Leading `span.authority-dot` 6px accent disc with an 18 % halo (static; no pulse). Four facts: Credit, Visible snapshot (`IdentityValue` compact id with `title` and sr-only full value), Selected run (`· live` suffix when the run is live), Source set; then an optional `span.status.warning` "Latest accepted differs" (switch required) or "Review required" (diff changed). Loading reads "Loading authority…", failure "Authority unavailable", no case "No case selected" / "Not applicable". Clips `1440-c-authority-strip`, `-loading`, `-error`, `-stale`.

**Main** `main.content#main-content[tabindex=-1]` (`:113`) — `max-width 1600px` (1800 on Report Studio via `.report-content`), padding `24 28 44`; `div.error.global-error[role=alert]` banner (`:115`) above the route when the workspace holds an error (critical border 55 %, critical 8 % fill, r10) — shot `1440-22-state-error`.

**Skip link** `a.skip-link` (`:226`) — fixed top-left, elevated fill, r8, revealed on focus only (`translateY(-150 %)` otherwise). Visible in `1440-02`, `1440-03` and `720-13` because keyboard focus landed on it during capture.

**Command palette** `dialog[aria-labelledby=palette-title]` (`WorkbenchShell.tsx:328–413`; `:228–256`) — opened by ⌘K/Ctrl+K or the top-bar button; `dialog` 680px max, panel fill, border-strong, r14, modal shadow, 60 % backdrop with 3px blur. `div.dialog-body` (16px grid gap 12) → `div.panel-header` (h2 "Command palette" + `button.button.small` Close) → `div.field` (label + `input#command-search[role=combobox]`) → `div#command-results[role=listbox]` (max-height `min(420px, 55dvh)`) with sticky `div.nav-label.palette-group-label` groups "Cases", "Workflows", "Tools", the evidence-id row, or `p.muted` "No matches"; results are `button.nav-link[role=option]` / `a.nav-link[role=option]` with `aria-selected` (accent-strong on elevated) → `div.palette-hint` (aria-hidden `kbd` ↑ ↓ ↵ Esc). Shots `1440-19-command-palette`, `1440-20-command-palette-query`, clip `1440-c-dialog-palette`.

**Evidence drawer** `dialog.context-drawer#context-drawer` (`WorkbenchShell.tsx:414–426`; `:257–260`) — fixed right, `min(440px, 100vw)` wide, `100dvh`, left hairline only, r14 on the left corners, `overflow: hidden`. `div.drawer-header` (56px, h2 16px filename, Close) → `div.drawer-body` (scroll, 16px) → `div.state-block` containing `dl` (four `dt.meta-label` / `dd` rows: Source ID, SHA-256, Visible snapshot, Visible source set), `p.status.warning` "Source-level reference; no block locator supplied by this artifact.", `h3` "Available source text", `div.source-blocks` of `article.source-block` (bg fill, hairline, r8, `div.meta-label` block id + `p` text), and `a.button.small` "Open full source". Opened from an `EvidenceChip`; the opener is captured from `document.activeElement` (`:164`, the known WebKit gap in CLAUDE.md). Shots `1440-04-evidence-drawer`, `720-04`, clip `1440-c-drawer`.

### 3.2 Panel (`:120–128`)

`section.panel` — panel fill, hairline, r10, `--shadow-panel`. `div.panel-header` (min-height 46px, bottom hairline, flex space-between, padding `10 14`; `h2` 13px/600 sentence case; right slot is `span.panel-meta` 10px muted or a `span.status`). `div.panel-body` (padding 12; `.flow` adds a 12px grid rhythm and zeroes child margins). Variants: `.evidence-focus` (accent 60 % border `:265`), `.source-toolbar`, `.cases-intake/register/create/fit`, `.model-builder-command`, `.report-outline/compose` (grid rows `32px 1fr` `:465` — the 32px row is the header slot inside Report Studio's two panels, but the header still renders 46px; measured header 144–190 and body top 176, a 14px overlap, so the body's first content starts under the header's rule — F-12). DESIGN.md's "32px uppercase header" (`:241`, `:359`) and .impeccable.md's (`:79`) describe a header the CSS does not have: it is 46px and sentence case. Clips `1440-c-panel-register-table`, `-create-form-inputs`, `-fit-status`, `-artifact-reader-chips`, `-compile-form-selects`, `-execution-route-dag`.

**Context strip** `section.context-strip` (`:333`) — full-width, block hairlines, `strong` + `p.muted`; the boundary/notice idiom under every route ("Portfolio ordering is not yet governed.", "Analyst boundary", "Relative percentile unavailable", "Authorization boundary"). Clip `1440-c-context-strip`.

### 3.3 Buttons (`:137–147`)

`button.button` / `a.button` — inline-flex, `min-height 36px` (renders 40 at 14px body), border-strong, elevated fill, text, r8, padding `8 12`, 160ms border/background/transform. Hover: accent border + subtle fill. Active: `translateY(1px)`. Disabled: `opacity .55`, `not-allowed`, hover suppressed. Focus: global 2px accent outline offset 2 (`:66`).
- `.primary` — accent fill, accent border, **bg-coloured text** (`#0a0c10`), weight 700; hover accent-strong. Renders 162×40 for "Analyze documents".
- `.quiet` — muted text (top-bar "Sources & evidence").
- `.danger` — critical border and text (`:146`); **no component uses it**.
- `.small` — `min-height 30px`, r6, padding `4 8`, 11px (Close, Retry, Open credit, Cancel, Keep editing, toggles).
- `.is-active` on `.button.small` (`ModelBuilder.tsx:743`, `:763`: Base/Downside and ±0.5×/±1×/±1.5×) — **no CSS rule exists**; selected toggles look identical to unselected ones (`1440-13-model-builder-ready`). Finding F-01.
- Coarse pointer: every button, nav link, select, input, chip, worksheet tab and cell link takes `min-height 44px` (`:632`; measured 44 under `hasTouch`).
- Paper variant (`:213–216`): transparent fill, paper-link text, paper-rule-strong border; primary inverts to paper-link fill with paper text.
Clips `1440-c-buttons-primary-secondary`, `1440-c-button-focus-ring`.

### 3.4 Chips and status

**Evidence chip** `button.evidence-chip[aria-label="Open evidence <id>"]` (`EvidenceChip.tsx:11–23`; `:189–192`) — pill (r999), `min-height 24px`, mono 10px, accent-strong text, accent 65 %-mixed border, accent 7 % fill, padding `3 8`; hover accent border + 12 % fill; `.is-linked` is set while the chip is hovered or focused (its `onPreview` lifts the id into the reader, which tints the matching source block `.evidence-match` `:277`) and adds a 2px accent outline offset 1, accent 16 % fill and text colour; click opens the drawer. Rendered inside `span.evidence-ref` with a trailing `span.mono.muted` of block ids, inside `div.evidence-list`. DESIGN.md's "selected chips invert to accent background and dark text" (`:327`) and front-matter `chip-active` do not happen anywhere. Clips `1440-c-evidence-chips`, `1440-c-evidence-chip-hover-linked`.

**Status** `span.status` (`:167–176`) — inline-flex, weight 700, gap 6px, with a `::before` glyph whose *shape* carries severity: `success` 7px disc emerald; `running` 7px disc accent; `warning` 8px-tall amber triangle (CSS borders); `critical` 7px rounded square (r2) red; `idle`/default 8×3 muted pill. Text colour matches. Paper recolours all five (`:218–225`). Several dozen uses across the three surfaces; the run badge `RunStatusBadge` (`Workspace.tsx:1288`) is a `.status` with `role=status`. Clip `1440-c-panel-fit-status`, `1440-c-approval-panel-*`.

**Flag** `span.flag` (`:337`) — amber mono 10px .08em caps: `UNAVAILABLE` (Admin), `RECOVERY COPY` (Report Studio). Clip `1440-c-admin-intro-flag`.

**kbd** (`:254`) — inline-grid, hairline, r6, bg fill, mono 10px/600.

### 3.5 Inputs (`:148–154`, `:344–349`, module `:101–128`)

`div.field` (grid gap 4, margin-bottom 12) → `label` (14px/700/.06em muted) → `input | select | textarea` (100 %, border-strong, bg fill, text, r8, padding 8, 160ms border + box-shadow). Hover: border mixes 55 % toward text. Focus-visible: outline removed, accent border, 3px accent 22 % halo. Textarea `min-height 100px`, vertical resize. `.form-row` three columns. Placeholder muted (`:62`), caret accent (`:61`). Top-bar select: padding `6 10`, `min-height 36`. Checkbox label (`.intake-bind label` `:352`) resets weight/tracking/case. Dropzone `div.dropzone` (`:344`) — dashed border-strong, r10, bg fill, padding 16; `.is-dragging`/`:focus-within` accent border + accent 6 % fill. Model scrubber / select / sign-off textarea (module `:101`) — r6, mono 11px/600, padding `7 8`, `cursor: ew-resize`. Search inputs use `type=search` (`#case-search`, `#source-search`, `#loan-search`, `#report-evidence-search`). Clips `1440-c-input-focus`, `1440-c-intake-dropzone`, `1440-c-panel-create-form-inputs`, `1440-c-forecast-assumptions-scrubber`.

### 3.6 Tables (`:155–166`)

`div.table-wrap[tabindex=0][role=region]` (horizontal scroll, `overscroll-behavior-inline: contain`) → `table` (100 %, collapsed) → `th, td` (bottom hairline, padding 8, top-aligned, left) — `th` is 10px/uppercase/.09em muted **for both column and row headers** (`:159`), so `th[scope=row]` in the Admin contracts table and the Model versions table renders as a small caps label rather than a body cell (`1440-c-admin-contracts-table`); the cases register avoids this by using `td` for the credit name. Finding F-05. Rows have `content-visibility: auto` with a 36px intrinsic size (`:157`); hover tints rows inside `.table-wrap` (`:162`); `caption` is left-aligned 10px label (`:166`). Cases register adds `div.worklist-toolbar` (`:642`) above the table and `.selected-row` (elevated + 2px inset accent bar `:338`). Clip `1440-c-panel-register-table`.

### 3.7 Worksheet grid (`ModelBuilder.tsx:143–223`; `:423–453`)

`div.worksheet-tabs[role=tablist]` (bg fill, bottom hairline, horizontal scroll) → `button.worksheet-tab[role=tab]` (10px/700/.08em uppercase muted; selected: 2px accent underline, elevated fill, text colour) → `div[role=tabpanel]` → `div.worksheet-scroll[role=region]` (`max-height min(680px, 100dvh − 250px)`, bg fill) → `p.worksheet-authority-note` (sticky left, elevated, muted 11px) → `table.worksheet-grid` (separate borders, spacing 0, `table-layout: fixed`, mono 10px/1.3 tabular): `thead th` sticky top z3 elevated muted centred letters; `tbody th[scope=row]` sticky left 42px elevated muted right-aligned; `td.worksheet-cell` 23px tall, right/bottom hairlines, padding `3 6`, nowrap ellipsis, panel fill. Authority classes from `modelBuilderState.ts:19`: `.is-source` 2px muted left border, `.is-calculated` double bottom border, `.is-assumption` dashed bottom border, `.is-locked` (no rule). Excel fill map (`ModelBuilder.tsx:58`) → `.worksheet-fill-section` accent 28 %, `-header` accent 20 %, `-subheader` accent 10 % over elevated, `-label` elevated, `-input` amber 15 %, `-positive` emerald 13 %, `-negative` red 13 %, `-muted` elevated + muted text. `.num` right-aligned, `.is-bold` 750, `.is-italic`, `.is-selected` 2px inset accent ring. Cells with lineage render `button.worksheet-cell-link` (hover accent underline). Below: `section.lineage` (module `:140`) with `dl.state-facts` and `code.lineage-code` (accent-strong mono on bg, r8). Shots `1440-13`, `720-13`; clips `1440-c-worksheet-grid`, `-worksheet-tabs`, `-cell-lineage`, `-tornado` (`.tornadoRow` 10px grid, accent bar on bg track r6, 1px text baseline tick).

### 3.8 Loan table (`Workspace.tsx:1697–1784`; `:305–327`)

`div.loan-filters` (six 120px+ columns of `.field`, bottom hairline) + `details.loan-advanced-filters` → `div.loan-table-wrap` (`max-height min(680px, 100dvh − 280px)`, 2-D scroll) → `table.loan-table` (`width: max-content`, mono 10px/1.35 tabular; cells `max-width 260px`, padding `5 7`, wrap anywhere): `thead .loan-groups th` sticky top 0, 26px, bg fill, centred, text colour, right hairline ("ISSUER PROFILE", "IDENTIFIERS", …); second head row sticky at 26px, elevated, with `button.loan-sort` (transparent, inherits caps, hover underline, "↑"/"↓" text arrow); body `td.positive` emerald, `.negative` red, `.flat` muted for signed change columns. `div.loan-pagination` (top hairline, right-aligned buttons) and `div.loan-authority dl` (five label/value pairs) above. Shot `1440-11-rv-screener`; clips `1440-c-loan-table`, `-loan-filters`, `-loan-authority`.

### 3.9 Dialogs (`:228–245`)

All four are native `<dialog>` opened with `showModal()`: panel fill, border-strong, r14, modal shadow, backdrop 60 % + 3px blur, 180ms rise (no-preference only). `div.dialog-body` grid gap 12 padding 16; a `.panel-header` inside is pulled to the edges with top radii (`:241`). Trigger captured before open, heading focused on the next frame, focus returned on close.
- **Accept analytical snapshot** (`Workspace.tsx:1307–1362`) — h2, `dl.state-facts` (Run, Pathway, Source set with id/digest in `.mono.muted`, New authority slots / Existing replaced / Slots removed each `strong.num` + `.mono.muted` list, Replaces snapshot digest), explanatory `p`, `div.top-actions` with `button.button.primary` "Accept analytical snapshot" + `button.button.small` Cancel. Shots `1440-07`, `720-07`; clip `1440-c-dialog-accept`.
- **Discard draft changes?** (`Workspace.tsx:1364–1437`) — h2, `p` detail, `p.muted`, primary "Discard changes" + small "Keep editing". Shot `1440-16`; clip `1440-c-dialog-discard`.
- Command palette and evidence drawer (§3.1).

### 3.10 Receipts and approval panels

**MutationReceipt** `div.mutation-receipt[role=status][aria-live=polite][aria-atomic]` (`states.tsx:136`; `:116–117`) — flex, emerald 55 %-mixed border, emerald 8 % fill, r10, padding `8 12`; first child is a text `✓` (U+2713, aria-hidden) in emerald mono 12px/700. Appears after accept, snapshot switch, loan import. Shot `1440-08-run-console-receipt`; clip `1440-c-mutation-receipt`.

**Approval panel** `section.approval-panel` (`:499`, `:514`) — bg fill, hairline, r10, padding 12, grid gap 12; the "What will bind" idiom: `span.meta-label` + `h3`, `dl.state-facts` of readiness rows each with a `span.status.success|warning` "Ready"/"Blocked", then actions. Used for run acceptance (`.run-acceptance`, reserved 133px `:244`), model sign-off (`[data-model-approval]`) and freeze (`[data-freeze-approval]`). Clips `1440-c-approval-panel-accepted/-ready/-blocked/-model-dirty/-freeze`.

**Opinion record** `div.opinion-record` (`:517`), **freeze job** `p.status.warning.freeze-job` (`:519`), **report authority strip** `div.report-authority-strip` (`:489`, bg fill, r10, label + `strong`), **report recovery** `section.report-recovery` (`:491`, amber 55 % border, amber 7 % fill, `.flag` RECOVERY COPY).

### 3.11 Run console pieces

`div.run-progress[role=progressbar]` (`:246–249`; label row muted + `.mono` count; `span.run-progress-track` 4px pill border-coloured with an accent fill whose width transitions 240ms) → `div.dag` (`:181`) of `div.dag-step` (`span.dag-edge` "→" mono 12px muted + `a|div.dag-node` 120–200px, bg fill, hairline, r8, padding 8: `ModuleIdentity` name + `.mono` id, `.status`, `span.dag-node-open` "OPEN ARTIFACT" 10px accent caps) → `div.approval-panel.run-acceptance`. Compile panel: `div.field` selects for Purpose and Depth, `fieldset.research-brief` (`:646`, hairline r10, `legend` muted 700 .06em) for Deep Research, `button.button.primary` "Compile and run", `div.callout` note. Research plan (`Workspace.tsx:1556`): `div.research-plan` with `dl.research-plan-facts` and `ol.research-workstreams` (`h5` 12px), full-width primary "Approve research plan". Shots `1440-05`, `1440-06`, `1440-09`; clips `1440-c-dag-tiles`, `-run-progress`, `-research-brief-fieldset`, `-research-plan`.

### 3.12 Command Center pieces

`div.credit-authority-head` (kicker + `h2` 18px + `.status.success` "Accepted <date>") → `div.standing-answer` (`:362–364`; top border-strong, `span.meta-label`, `h2` 30px display max 30ch, `p` basis max 76ch, `p.mono.muted` module · digest) → `div.authority-metrics` (`:365–368`; four cells, block border-strong rules, inner hairlines, `meta-label` + `strong` 16px) → `section.credit-change-section` (`.section-heading` + `p.callout` "No material module or source-set change is present in the served snapshot diff." or `p.callout.warning` + `ul.credit-change-list`) → `div.top-actions.credit-actions` (primary "Read accepted analysis" + secondary "Review latest run"). Aside `aside.credit-proof` (`:374`; sticky, left hairline, `dl.state-facts` one column, `div.proof-register` with 22px accent mono count, `Unavailable` block). Shots `1440-12`, `1440-24`; clips `1440-c-standing-answer`, `-authority-metrics`, `-credit-proof`, `-what-changed-list`.

### 3.13 State components (`states.tsx`, all 141 lines)

| Export | Markup | Classes | Where rendered (examples) | Atlas |
|---|---|---|---|---|
| `IdentityValue` | `span.mono[title=full]` > aria-hidden compact + `.sr-only` spoken | `mono` (or caller's) | every digest/id | any strip clip |
| `StateBlock` (`shape=callout`) | `div` > `strong` + `p` + children + action | neutral `callout` (`:177` accent 55 % border, accent 6 % over elevated, r10); warning `callout warning` (`:178` amber); critical `empty error-state` (`:262–263` muted, padding `24 10`, left-aligned) | intake refusal (`Workspace.tsx:1118`, critical, `role=alert`), Model Builder NOT_READY/FAILED (`ModelBuilder.tsx:716–719`), Report conflict | `1440-c-state-critical-intake-refusal`, `1440-c-callout-neutral` |
| `StateBlock` (`shape=action`) | same | `action-state` (`:330` bg fill, hairline, r10, `justify-items: start`), `action-state warning` (amber border) | intake outcomes (`Workspace.tsx:1143–1152`), "Credit state unavailable", "Analysis unavailable" (`:1668`, `:1836`) | `1440-25-state-empty-no-case` (EmptyPanel), `1440-c-approval-panel-*` |
| `StateNote` | `p` | `callout` / `callout warning` / `error` (`:261` critical text) | run failed/paused notes (`:1497–1499`), artifact errors, freeze failure | `1440-09` (paused note absent because the plan slot replaces it) |
| `StateSkeleton` | `div.state-skeleton[role=status][aria-live=polite][aria-label=Loading]` > three `span` | `:196–206` 8px pills, elevated, widths 100/74/88 %, shimmer under no-preference | every `LoadState loading`, root `Suspense` fallback (`layout.tsx:19`) | `1440-21-state-loading-skeleton`, `1440-c-state-skeleton` |
| `EmptyBlock` | `div.empty` | `:262` muted, centred, padding `24 10` | `LoadState` empty, `WriteBlocked` (`Workspace.tsx:32`), "The saved model has no worksheet tabs." | `1440-c-state-write-blocked`, `1440-27` |
| `EmptyPanel` | `div.panel > div.empty > p + action` | as above inside a panel | "Create or select a case before entering an analytical workspace." (`:1013`) | `1440-25`, `1440-c-state-empty-panel` |
| `LoadState` | skeleton → `StateBlock critical live=alert` with Retry (`button.button.small`) → `EmptyBlock` | | run/snapshot/report/model loads | `1440-22-state-error`, `1440-c-state-critical-error-retry` |
| `Unavailable` | `div.state-block.unavailable` > `strong` + `p` "Not available in this deployment." + `p.muted` context | `:207–208` muted text, 1.5 leading; no Retry by design | Sources claim coverage, Credit "Binding measure and claim gaps", Deep-Dive evidence citations, Model worksheet/tornado/rebase on 404, research-plan approval on 404 | `1440-c-state-unavailable-coverage`, `1440-c-credit-proof` |
| `MutationReceipt` | §3.10 | `mutation-receipt` | | `1440-c-mutation-receipt` |

Not in `states.tsx` but state-bearing: `AdminView` (`Workspace.tsx:1850`; `div.admin-capability` > `section.admin-intro` with `.flag` + `h2` 30px display + `p` muted; contracts table with `.status.warning` "Not served"; context strip) — shot `1440-17`; `NotFound` (`app/not-found.tsx`; `section.panel > .panel-body.flow > p.muted + a.button.small`) — shot `1440-18`; `WriteBlocked` (`div.empty`); `global-error` banner (§3.1).

---

## 4. DESIGN.md's eight decision states against what renders

DESIGN.md `:350` names `loading, ready, observed-empty, stale, partial, offline, error, unavailable` and says "No material change" is legal only for a successful timestamped `observed-empty` response.

| State | Renders as | Component / file:line | Distinct? |
|---|---|---|---|
| loading | shimmer skeleton; authority strip "Loading authority…"; case select "Loading cases…"; panel-meta "Loading…"; `WriteBlocked` "Confirming your access…"; buttons "Compiling…/Accepting…/Freezing…" | `StateSkeleton` (`states.tsx:97`), `WorkbenchShell.tsx:213/300`, `Workspace.tsx:33/1065` | yes — motion (no-preference) + copy + `role=status` |
| ready | ordinary panels; `.status.success` "Accepted", "READY", "Ready", "Latest accepted authority"; `MutationReceipt` after a write | `Workspace.tsx:1458`, `ModelBuilder.tsx:297` | yes — emerald disc + text |
| observed-empty | `EmptyBlock`/`EmptyPanel` copy ("No source objects in this credit.", "No current execution…", "No matches"); Command Center "No material module or source-set change is present in the served snapshot diff." in `p.callout` beside the `Accepted <timestamp>` status | `states.tsx:101–108`, `Workspace.tsx:1840` | yes; the "no material change" line sits under a timestamped accepted status, satisfying the rule |
| stale | authority strip `.status.warning` "Latest accepted differs" / "Review required"; Deep-Dive `.analysis-switch.callout.warning` "New accepted execution available." with "Switch visible snapshot"; Command Center `p.callout.warning` + change list; Model Builder `.callout.warning` "Model authority changed"; Report Studio freeze row "Current model selection · Blocked"; revision state `STALE` → `.status.warning` | `WorkbenchShell.tsx:312–314`, `Workspace.tsx:1671/1840`, `ModelBuilder.tsx:732/770`, `ReportStudio.tsx:638` | yes — amber triangle + warning callout; shots `1440-23`, `1440-24` |
| partial | **no dedicated component**. The nearest renders: intake refusal `INTAKE_ADMISSION_REFUSED` "1 of 1 documents failed admission; the pack was not admitted." as a critical `StateBlock` with a findings list (`Workspace.tsx:1118`) — the product refuses partial admission by contract; source rows "No blocks" `.status.warning`; artifact status ≠ COMPLETE → `.status.warning`; run progress "n of m modules". | | partially — expressed through warning statuses and counts, not a named state |
| offline | **no dedicated component and no detector** (`navigator.onLine` unused). A transport failure surfaces as the `global-error` banner with the typed code, the authority strip "Authority unavailable", and `LoadState` error with Retry | `WorkbenchShell.tsx:323`, `states.tsx:121` | no — offline is indistinguishable from error |
| error | `LoadState` error (`.empty.error-state` + `strong` + `p` + Retry, `role=alert`); `StateNote critical` (`p.error`); `global-error` banner; `.status.critical` "Acceptance blocked", "Unavailable" (Model Builder header) | `states.tsx:113–121`, `Workspace.tsx:1474`, `ModelBuilder.tsx:703` | yes — red rounded square / red text; shot `1440-22` |
| unavailable | `Unavailable` block "Not available in this deployment."; `AdminView` with `.flag` UNAVAILABLE and "Not served" rows; context strips "Relative percentile unavailable", "Portfolio ordering is not yet governed."; disabled `option`s outside the deployment cut with the `p.muted` explanation (`Workspace.tsx:1528–1529`) | `states.tsx:128`, `Workspace.tsx:1850` | yes — muted text, no Retry, amber flag |

Six of eight are visually and semantically distinct; `partial` and `offline` are not. Recorded as F-08 (doc rule without a component; owner decides whether the rule or the component set changes).

---

## 5. Paper counterpoint (Report Studio and `DeliverableDocument`)

Report Studio is the one route with `main.content.report-content` (1800px). Its grid `div.report-studio` (`:462`) is three columns `2.5fr 4fr 5.5fr` at `calc(100dvh − 145px)`; below 900px it becomes two columns with the proof stage spanning both (`:625–628`). Left `aside.panel.report-outline` (Structure: pathway select, `nav.report-section-nav` with numbered buttons — `span` 10px mono index, title, `small` "REQUIRED" 9px — `details.report-optional`, `div.report-history`). Middle `section.panel.report-compose` (Compose: `.status` save state in the header; narrative `textarea` with `span.field-meta` character count; `fieldset` "Claim authority" radios; `.report-authority-strip`; `fieldset.report-model-picker`; `details.evidence-inspector` and `details.scenario-insert` (`:499–502`, bg fill r10, `summary` with a right-floated muted count); `section.approval-panel[data-freeze-approval]`). Right `section.report-proof-stage` (`:468`; bg fill, hairline, r10, padding 24, scroll) holding the paper.

`article.paper.report-paper.deliverable-document.rd-paper` (`DeliverableDocument.tsx:174`; `:211`, `:469`, `:528`) — `min(100 %, 980px)`, paper fill `#f7f4ec`, ink text, paper-rule border, **r6**, `--shadow-paper`, `container-type: inline-size`, padding `40 46 26`, sans family. Each `section.rd-page-container` (relative; page 2+ gets a dashed paper-rule top border `:530`): optional `div.rd-wm` watermark (absolute, centred, rotated −16°, 26px mono .32em, watermark colour at 16 % — aria-hidden) → `header.rd-mast` (2px ink bottom rule; `span.rd-mast-brand` with `span.rd-mark` "C" 14px ink square + "CAOS · <pathway> · <page>"; `span.rd-mast-meta` "<state> · PAGE n OF m") → on page 1 `h2.rd-title` + `p.rd-subtitle` + `dl.rd-masthead-facts` (nine facts, `auto-fit minmax(180px,1fr)`) + `p.rd-identity.mono` → `p.rd-band` page name → `div.rd-secs` (18px gaps) of `section.rd-sec[data-section-id]`: `h3.rd-h` (title + `span.rd-h-sub` "Analyst judgment" | "Locked · <origin>") then `p.rd-body` | `dl.rd-profile` of `div.rd-prow` (`dt.rd-plbl` 152px + `dd`) | `ul.rd-list` | `div.rd-table-wrap[role=region][tabindex=0]` > `table.rd-table` (`caption.visually-hidden`, `thead th` paper-rule underline, body rows ink 8 % rules, `th[scope=row]` first cell) | `div.rd-cols.rd-cols-2|3` (22px gap; single column under a 660px container `:566`) → `footer.rd-foot` ("Generated by CAOS · governed document", "Internal committee use only" | "Approver recorded in the detached filing receipt"). Empty template → `p.rd-empty`. Paper buttons and statuses recolour per `:213–225`; paper focus rings use paper-link (`:529`).

Truth for FE-D2: the paper shipped in the atlas is the **draft** state ("DRAFT · PAGE 1 OF 1", "Not yet drafted." bodies, no watermark, no masthead facts) — `1440-15-report-studio`, `1440-c-paper-draft`, `1440-c-paper-masthead`, `720-15`. The frozen/filed state (watermark `PENDING APPROVAL`, masthead facts, `rd-band`) needs a worker-published freeze on a case with a READY model; host control yields none (Task 13 golden journeys), so it is **not in the atlas**. Its markup is fully specified above and its CSS at `:520–527`; the workbench smoke exercises it with fixtures (`workbench-smoke.mjs:1607`). One caveat for the canvas: because of F-11 the masthead fact *values* currently render in paper-meta grey, not ink; draw them as the CSS intends (ink) only once FE-G1 fixes the token name, otherwise match the grey.

---

## 6. Navigation glyph set (`WorkbenchShell.tsx:57–78`, `:287`, `:258`)

All rail glyphs share `viewBox 0 0 16 16`, `fill: none`, `stroke: currentColor`, `stroke-width 1.5`, round caps and joins, `aria-hidden`, `focusable=false`; the SVG attribute says 13×13 but CSS wins at **14×14** (`:91`). The brand mark SVG is 16×16 in a 30×30 bordered box.

| Destination | Glyph | Path summary |
|---|---|---|
| Brand mark | terminal prompt `>_` | `m4.5 5 3 3-3 3` chevron + `M8.5 11h3.5` underscore |
| Portfolio | register | rounded rect 11×10 with a header rule at y 6.25 and a column rule at x 6 |
| Credit | pulse | polyline `2 8.25 → 4.75 → 6.5,4.25 → 9.5,11.75 → 11.25,8.25 → 14` |
| Sources | stacked layers | diamond top face + two chevron layers below |
| Analysis | reader page | rounded rect 9.5×11.5 with three text rules (two long, one short) |
| Market | comparison bars | baseline + three bars of heights 4, 10, 6.5 |
| Model | worksheet | rounded rect 11×11 with a header rule and a column rule |
| Report | filed page | page with a folded top-right corner (`M9 1.75V5.5h4`) |
| Admin | shield with check | shield outline + `m5.75 7.75 1.5 1.5 2.75-2.75` |

Other marks in chrome are **text glyphs**, not SVG: `→` DAG edge (`Workspace.tsx:1495`), `✓` U+2713 receipt (`states.tsx:138`), `↑`/`↓` loan sort, `↑ ↓ ↵` palette hints and `⌘K` (`WorkbenchShell.tsx:303/408–410`), `·` separators throughout, `—` in the accept dialog and intake copy, `*` required marker in the sign-off label. Non-text marks are pure CSS: status glyphs (§3.4), authority dot, the 2px selection bar, the 4px square list bullet on paper (`:558`), the `.rd-mark` box. No icon font, no image assets, no emoji (the only U+2713 is a dingbat, not an emoji-presentation code point).

---

## 7. Contrast (WCAG 2.1, computed by `design/contrast.mjs`)

`color-mix(in srgb, A p%, B)` is per-channel linear interpolation; mixing with `transparent` yields A at alpha p composited over the surface beneath. Every text pair the workspace uses:

| Pair | Foreground | Surface | Ratio | 4.5:1 | Where used | globals.css |
|---|---|---|---|---|---|---|
| body text on bg | #e9edf4 | #0a0c10 | 16.67:1 | AA | 14px normal | :53 |
| body text on panel | #e9edf4 | #101319 | 15.84:1 | AA | 14px normal | :53/:120 |
| body text on elevated | #e9edf4 | #181d28 | 14.36:1 | AA | 14px normal | :80/:137 |
| body text on subtle (button hover) | #e9edf4 | #202632 | 12.92:1 | AA | 14px normal | :138 |
| muted on bg | #99a3b4 | #0a0c10 | 7.69:1 | AA | 10–11px labels | :75/:108 |
| muted on panel | #99a3b4 | #101319 | 7.31:1 | AA | 10px panel-meta | :126 |
| muted on elevated | #99a3b4 | #181d28 | 6.63:1 | AA | 10px worksheet heads | :432/:451 |
| muted on rail (panel 82 % over bg) | #99a3b4 | #0f1217 | 7.38:1 | AA | 14px nav-link, 10px nav-label | :68/:79 |
| accent on bg | #8b93f8 | #0a0c10 | 7.11:1 | AA | 10px dag-node-open | :275 |
| accent on panel | #8b93f8 | #101319 | 6.75:1 | AA | 22px proof-register | :379 |
| accent on elevated (active shortcut, history strong) | #8b93f8 | #181d28 | 6.12:1 | AA | 10px | :86/:487 |
| accent-strong on elevated (active nav) | #a5abfa | #181d28 | 7.87:1 | AA | 14px | :81/:82 |
| accent-strong on bg (lineage-code) | #a5abfa | #0a0c10 | 9.14:1 | AA | 14px mono | :454 |
| accent-strong on chip (accent 7 % over panel) | #a5abfa | #191c29 | 7.92:1 | AA | 10px mono | :190 |
| accent-strong on chip (accent 7 % over bg) | #a5abfa | #131520 | 8.46:1 | AA | 10px mono | :190 |
| text on linked chip (accent 16 % over panel) | #e9edf4 | #24273d | 12.44:1 | AA | 10px mono | :192 |
| bg on accent (primary button) | #0a0c10 | #8b93f8 | 7.11:1 | AA | 14px bold | :142 |
| bg on accent-strong (primary hover) | #0a0c10 | #a5abfa | 9.14:1 | AA | 14px bold | :143 |
| **primary button disabled** (.55 opacity, both layers over panel) | #0d0f14 | #545994 | **2.96:1** | **FAIL** (below 3:1 even for large text) | 14px bold | :140/:142 |
| secondary button disabled (.55, over panel) | #878b91 | #141921 | 5.17:1 | AA | 14px | :140/:137 |
| warning on bg | #fbbf24 | #0a0c10 | 11.72:1 | AA | 10px flag / 14px status | :337/:175 |
| warning on panel | #fbbf24 | #101319 | 11.14:1 | AA | 14px status | :175 |
| warning on elevated | #fbbf24 | #181d28 | 10.10:1 | AA | 14px status | :175 |
| critical on bg | #f87171 | #0a0c10 | 7.08:1 | AA | 14px error | :261 |
| critical on panel | #f87171 | #101319 | 6.72:1 | AA | 14px error | :261 |
| critical on elevated | #f87171 | #181d28 | 6.10:1 | AA | 14px | :175 |
| critical on global-error (critical 8 % over bg) | #f87171 | #1d1418 | 6.51:1 | AA | 14px | :115 |
| success on bg | #34d399 | #0a0c10 | 10.18:1 | AA | 14px status | :175 |
| success on panel | #34d399 | #101319 | 9.67:1 | AA | 14px status | :175 |
| success on receipt (success 8 % over bg) | #34d399 | #0d1c1b | 9.11:1 | AA | 12px mono bold | :116/:117 |
| text on callout (accent 6 % over elevated) | #e9edf4 | #1f2434 | 13.13:1 | AA | 14px | :177 |
| muted on callout | #99a3b4 | #1f2434 | 6.06:1 | AA | 14px | :177/:332 |
| text on callout.warning (warning 6 % over elevated) | #e9edf4 | #262728 | 12.79:1 | AA | 14px | :178 |
| muted on report-recovery (warning 7 % over bg) | #99a3b4 | #1b1911 | 6.94:1 | AA | 14px | :491/:493 |
| text on worksheet cell (panel) | #e9edf4 | #101319 | 15.84:1 | AA | 10px mono | :436 |
| text on worksheet-fill-section (accent 28 %) | #e9edf4 | #323757 | 9.82:1 | AA | 10px mono | :444 |
| text on worksheet-fill-header (accent 20 %) | #e9edf4 | #292d46 | 11.54:1 | AA | 10px mono | :445 |
| text on worksheet-fill-subheader (accent 10 % over elevated) | #e9edf4 | #24293d | 12.30:1 | AA | 10px mono | :446 |
| text on worksheet-fill-input (warning 15 %) | #e9edf4 | #332d1b | 11.69:1 | AA | 10px mono | :448 |
| text on worksheet-fill-positive (success 13 %) | #e9edf4 | #152c2a | 12.56:1 | AA | 10px mono | :449 |
| text on worksheet-fill-negative (critical 13 %) | #e9edf4 | #2e1f24 | 13.33:1 | AA | 10px mono | :450 |
| muted on worksheet-fill-muted (elevated) | #99a3b4 | #181d28 | 6.63:1 | AA | 10px mono | :451 |
| loan positive on panel | #34d399 | #101319 | 9.67:1 | AA | 10px mono | :324 |
| loan negative on panel | #f87171 | #101319 | 6.72:1 | AA | 10px mono | :325 |
| muted on evidence-match (accent 9 % over panel) | #99a3b4 | #1b1f2d | 6.47:1 | AA | 14px | :277 |
| text on dropzone focus (accent 6 % over bg) | #e9edf4 | #12141e | 15.62:1 | AA | 12px | :345 |
| border-strong on bg (input border, non-text) | #606b7e | #0a0c10 | 3.64:1 | meets 3:1 UI | | :150 |
| **border on panel (hairline, non-text)** | #242b38 | #101319 | **1.31:1** | below 3:1 — hairlines are not the sole boundary of any control (inputs use border-strong) | | :120 |
| accent focus ring on bg / on panel | #8b93f8 | #0a0c10 / #101319 | 7.11:1 / 6.75:1 | meets 3:1 UI | | :66 |
| ink on paper | #191922 | #f7f4ec | 15.88:1 | AA | 12px rd-body | :211/:543 |
| paper-meta on paper | #5d5d68 | #f7f4ec | 5.91:1 | AA | 8–10px mono meta | :520/:535/:546 |
| paper-link on paper | #2f54c9 | #f7f4ec | 5.91:1 | AA | 14px button | :213 |
| paper on paper-link (paper primary) | #f7f4ec | #2f54c9 | 5.91:1 | AA | 14px bold | :216 |
| paper on ink (rd-mark) | #f7f4ec | #191922 | 15.88:1 | AA | 10px mono bold | :534 |
| paper-soft on paper (unused token) | #6a6a72 | #f7f4ec | 4.88:1 | AA | — | :27 |
| paper-success on paper | #166534 | #f7f4ec | 6.49:1 | AA | 14px status | :218 |
| paper-warning on paper | #a24310 | #f7f4ec | 5.71:1 | AA | 14px status | :220 |
| paper-critical on paper | #b91c1c | #f7f4ec | 5.89:1 | AA | 14px error | :217 |
| paper-watermark 16 % over paper (decorative, aria-hidden) | #eedac9 | #f7f4ec | 1.23:1 | n/a | 26px | :522 |
| paper-rule on paper (border) | #a8a498 | #f7f4ec | 2.27:1 | below 3:1 — decorative rule | | :211/:469 |
| paper-rule-strong on paper (paper button border) | #6f6c62 | #f7f4ec | 4.78:1 | meets 3:1 UI | | :213 |
| ink 8 % over paper (table row rule) | #e5e2dc | #f7f4ec | 1.17:1 | decorative | | :547 |

Every enabled text pair clears 4.5:1, including the 8–10px paper meta (5.91:1) and the 9px chrome mono (muted 6.6–7.7:1). The one failing text pair is the **disabled primary button** (2.96:1) — a disabled control is exempt from 1.4.3, so this is a legibility observation, not a violation (F-04). DESIGN.md `:339` "Disabled lowers opacity only when the control remains readable" is not met by the primary variant.

---

## 8. Motion rules and reduced-motion fallbacks

| Motion | Rule | Trigger | Under `prefers-reduced-motion: reduce` |
|---|---|---|---|
| Hover/focus colour transitions, 160ms `--ease-out` | `.brand-mark :72`, `.nav-link :79`, `select :106`, `.button :137`, inputs `:150`, `.evidence-chip :190`, `.source-register-row :291`, `.dropzone :344`, `.analysis-toc button :387`, module `:112` | pointer/keyboard | duration `.01ms` (`:637`; measured `transitionDuration: 1e-05s`) |
| Button press | `.button:active { transform: translateY(1px) }` `:139` | press | instant |
| Progress fill width, 240ms | `.run-progress-track > span :249` | live run events | `.01ms` |
| Skeleton shimmer, 1.6s linear infinite | `.state-skeleton span :204` (**inside** `@media (prefers-reduced-motion: no-preference)`) | loading | rule never applies; bars are flat elevated pills (`:197`) |
| Dialog rise 6px + fade, 180ms | `dialog[open] :234`, `::backdrop :235` (no-preference only) | open | no animation |
| Global pin | `:634`, `:637` | — | `animation-duration/transition-duration .01ms`, `iteration-count 1`, `play-state paused`, `scroll-behavior auto`, all `!important`; `.app-shell` additionally pinned so a nested infinite animation cannot cycle |

There is **no pulse, flash or enter animation** in the code. DESIGN.md `:244`/`:372` ("Running pulse and flash cues") and .impeccable.md `:81–83` (`.caos-running` pulse, `.caos-enter`) describe idioms that were never ported. The authority dot's halo is static. The "motion only for live state" rule holds: the two animations are loading and modal entry; the one transition beyond hover is the live progress width. The detector's `layout-transition` warning on `:249` is that width transition on a 4px bar — recorded, not endorsed as a defect (F-09).

---

## 9. Findings for FE-G1 (code-level inconsistencies; no visual-language proposals)

| Id | Severity | Where | What | Evidence |
|---|---|---|---|---|
| F-01 | High | `ModelBuilder.tsx:743`, `:763`; `globals.css` has no `.button.is-active` rule | Toggle buttons (Base/Downside; ±0.5×/±1×/±1.5×) set `className="button small is-active"` and `aria-pressed`, but no rule styles `.is-active` on a button; the pressed toggle is visually identical to the others. `is-active` is styled only for `.source-register-row :293`, `.analysis-toc button :389`, `.report-section-nav button :476–477`. | `1440-13-model-builder-ready` — Base and Downside render alike |
| F-02 | Low | `globals.css:44`, `:37`, `:27` | `--shadow-pop`, `--space-2xl`, `--caos-paper-soft` are defined and used by no rule; `.button.danger :146` and `.evidence-option :632` are rules with no consumer. Dead tokens mislead a designer reading the CSS as the palette. | grep counts in this session |
| F-03 | Low | `Workspace.tsx:1231` (`artifact-reader`), `:1776` (`loan-rv`), `ReportStudio.tsx:606` (`report-studio-structured`), `DeliverableDocument.tsx:174` (`rd-paper`) | Class names with no CSS rule (hooks or leftovers). Harmless, but a canvas built from class names will look for them. | grep |
| F-04 | Medium | `globals.css:140`, `:142` | Disabled primary button: `opacity .55` on an accent fill with bg-coloured text yields 2.96:1. Exempt from 1.4.3 but below DESIGN.md `:339`'s own "remains readable" rule; "Analyze documents" sits disabled on Cases at first paint. | §7; `1440-01-cases` |
| F-05 | Low | `globals.css:159` | `th` styling (10px uppercase muted) applies to `th[scope=row]`, so row headers in the Admin contracts table and the Model versions table render as column-label chrome. | `1440-c-admin-contracts-table` |
| F-06 | Low (doc-vs-code) | `globals.css:390`, `:404`, `:406`, `:479`, `:510`; `ModelBuilder.module.css:93`, `:99` | Seven chrome rules at 9px versus DESIGN.md `:290`'s "10px floor on desktop". Contrast still passes (§7). The rule owner decides; the truth sheet records 9px as the floor. | measurements |
| F-07 | Medium (200 % zoom) | `globals.css:576–582` | At 720 CSS px the rail is a horizontally scrolling strip with a thin scrollbar; Model, Report, Governance/Admin and `rail-meta` sit off-canvas (rail-meta measured at x = 1113) and are reached only by scroll or the active link's `scrollIntoView`. The page itself does not overflow (the a11y sweep's check passes), but the primary navigation does. | `720-13-model-builder-ready`, geometry in `atlas-measurements.json` |
| F-08 | Low (doc-vs-code) | DESIGN.md `:350` | `partial` and `offline` are named decision states with no rendering component or detector (§4). | §4 |
| F-09 | Info | `globals.css:173`, `:249` | The impeccable detector flags `border-bottom: 8px solid` (the CSS triangle glyph) as "border accent on rounded element" and the progress width transition as a layout animation. Both are deliberate: the triangle is a shape glyph, the width is live state on a 4px bar. No change proposed. | detector JSON |
| F-10 | Medium (doc) | `caos/frontend/docs/control-capability-map.md:21`, `:24` | The map says one-way sensitivity is "Route absent" and Admin membership "Routes absent"; `CLAUDE.md` lists one-way and tornado as served, and Report Studio renders a member-provisioning form against `POST /api/cases/{id}/members` (`ReportStudio.tsx:651`). The frontend draws no one-way control today. | code |
| F-11 | Medium | `globals.css:527` | `.rd-masthead-facts dd { color: var(--caos-paper-ink) }` references a custom property that is never defined (the token is `--caos-ink`, `:22`). The declaration is invalid at computed-value time, so the value inherits paper-meta grey: on a frozen or filed paper every masthead fact value renders in the label colour instead of ink. The only undefined `var()` reference in either stylesheet. | grep of every `var(--…)` against `:root` |
| F-12 | Medium | `globals.css:465` vs `:124` | `.report-outline, .report-compose { grid-template-rows: 32px minmax(0,1fr) }` reserves 32px for a `.panel-header` whose `min-height` is 46px. Measured on `/report-studio/`: header 144–190, body top 176 — the body overlaps the header by 14px, so "Pathway template" and the Compose textarea label start under the header rule. The 32px is the pre-reskin header height (DESIGN.md `:359`). | Playwright `getBoundingClientRect` probe, this session |

---

## 10. "Do not draw" list (capability map, as the running app honours it)

Controls that FE-D1/FE-D2 must not put on a canvas, because the served contract is absent and the app renders an unavailable state instead (`control-capability-map.md`, verified against the routes the frontend calls):

- **Portfolio**: attention ordering, threshold distance, freshness score, any ranking or sort-by-risk (`:10`; the register is unranked — context strip "Portfolio ordering is not yet governed.").
- **Credit / Command Center**: normalized binding metric, threshold, tolerance, gap summary, counterfactuals (`:13`; renders `Unavailable` "Binding measure and claim gaps").
- **Sources**: claim-to-source coverage matrix (`:15`; renders `Unavailable` "Claim coverage").
- **Market / RV Screener**: relative percentile or any relative-position score (`:19`; context strip "Relative percentile unavailable").
- **Model**: one-way sensitivity control (`:21` — see F-10: served by the API but not drawn; do not draw until the map is corrected and FE-G1 decides).
- **Admin Studio**: audit log viewer, membership management, export, step-up/privileged session, token prompts, simulated audit rows (`:24`; the route renders the four "Not served" contracts and the UNAVAILABLE flag). Note the map is stale on membership and audit package (F-10), but the Admin surface itself stays an unavailable state by design (CLAUDE.md known gaps).
- **Any mobile layout, breakpoint, fixture or acceptance target** (`:26–27`; 720 is 200 % desktop zoom, not a phone product).
- **Any tranche or seniority colour ramp, "consumer" colour, `View: Analyst / PM / QA` switch, utility drawer, popover menus, tooltips-for-icons, or a running pulse** — none exist in the code (§1.2, §3, §8); drawing them would invent chrome the CSS cannot honour.
- **Deep Research on a case whose wire says `deep_research_available: false`** (option disabled with the served reason) and any pathway outside the served `available_pathways` cut.

Also served-but-unavailable states that a canvas must depict *as states*, not as working controls: research-plan approval when the route 404s (`Unavailable` "Research plan approval"), worksheet/tornado/rebase on 404, filing for the signer/freezer (`APPROVER_NOT_INDEPENDENT`), reader-role `WriteBlocked` blocks.

---

## 11. Delta table for FE-G4 (DESIGN.md and .impeccable.md)

Section references are line numbers in the current files. "Truth" is what §1–§8 measured; "Proposed wording" is what the regenerated document should say. Nothing here changes the visual language; it makes the documents describe the CSS.

### 11.1 DESIGN.md

| Section | Current text | Truth | Proposed wording |
|---|---|---|---|
| front matter `colors:` `:5–38` | pre-reskin palette (`#0a0a0f`, `#11131d`, `#1d2030`, `#34384a`, `#e6e6ef`, `#a1a1b5`, `#63a1ff`, `#f5a524`, `#ef4444`, `#22c55e`, `#3f3f46`, `*-bright`, `scroll-shadow`, five `tranche-*`, `consumer`, `paper #f7f5ee`, `paper-ink #16161e`, `paper-meta #5c5c66`, `paper-note`, `paper-rule #9c998e`, `paper-subhead`, `paper-link #1f4fa0`) | the 24 tokens in §1.2 | Replace the block with exactly the `:root` tokens, keyed by their CSS names minus the prefix: `bg #0a0c10, panel #101319, elevated #181d28, subtle #202632, border #242b38, border-strong #606b7e, text #e9edf4, muted #99a3b4, accent #8b93f8, accent-strong #a5abfa, warning #fbbf24, critical #f87171, success #34d399, paper #f7f4ec, ink #191922, paper-meta #5d5d68, paper-rule #a8a498, paper-rule-strong #6f6c62, paper-link #2f54c9, paper-soft #6a6a72, paper-success #166534, paper-warning #a24310, paper-watermark #be5410, paper-critical #b91c1c`. Drop `consumer`, `idle`, the `*-bright` trio, `scroll-shadow`, `tranche-*`, `paper-note`, `paper-subhead`. |
| front matter `typography:` `:39–188` | `display 30/700`, `headline 22/600/1.1`, `title 16/600/1.15`, `body 12/400/1.5`, `label 11/500 mono uppercase .08em`, `micro 10/600 mono .06em`, `output-section 14/650`, `output-body 13`, `output-subtitle 9.5`, `output-prose 9.4`, `output-table-body 9.3`, `output-list 9.2`, `output-table-label 7.8 mono`, `appendix-*`, `emergency-*`, `mobile-readable-min`, `narrative-subhead` | §2.1–2.2 | `display: var(--font-display) 30/600/1.04/−.01em` (standing answer; reader and admin display 1.05, no tracking); `headline: display 21/600/1.2/−.01em` (page title); `title: sans 13/600/1.55` (panel header, sentence case); `body: sans 14/400/1.55`; `label: sans 11/650/1.35` (kicker `.meta-label`) and `sans 10/700 uppercase .09–.14em` (table heads, rail group labels); `mono-meta: mono 10–11/400` (authority strip, ids, chips, rail meta); `output-title 21/650/1.2/−.01em`; `output-section: sans 11/700 uppercase .08em`; `output-body: sans 12/400/1.62`; `output-subtitle: mono 10/600/1.5`; `output-meta: mono 8.5/500/1.45`; `output-table-label: sans 9/650 uppercase .06em`; `output-table-body: sans 10/400/1.4`; `output-list: sans 11/400/1.5`; `output-watermark: mono 26/700/1/.32em`. Remove `appendix-*` (worker renderers), `emergency-*` (no error boundary), `mobile-readable-min`, `narrative-subhead`, `output-prose`. State that all families are native stacks (§1.1). |
| front matter `rounded:` `:189–192` | `sm 2px, md 6px, pill 999px` | `sm 6, md 8, lg 10, xl 14, pill 999` (2px only on `.rd-mark` and the critical square) | `sm: "6px", md: "8px", lg: "10px", xl: "14px", pill: "999px"` |
| front matter `spacing:` `:193–199` | `hairline 1px, xs..xl` | `xs 4, sm 8, md 12, lg 16, xl 24, 2xl 32 (unused)`; gutter 28 literal | Keep xs–xl; add `2xl: "32px"` only if FE-G1 keeps the token; drop `hairline` (no token) or note it is literal `1px`. |
| front matter `components:` `:200–225` | `panel rounded md padding 0`; `button-primary padding 4px 8px`; `button-ghost bg panel text muted`; `input padding 6px 10px`; `chip-active accent bg dark text` | panel r10, body padding 12, header 46; primary padding `8px 12px` min-height 36 (renders 40), text `{colors.bg}`; `.button.quiet` bg elevated text muted; `.button.small` padding `4px 8px` r6 min-height 30; input padding 8 r8 bg `{colors.bg}` border `{colors.border-strong}`; chip rest = accent-strong text on accent 7 %, linked = 2px accent outline + accent 16 % fill, never inverted | Rewrite the five entries to those values; rename `button-ghost` → `button-quiet`, add `button-small`, replace `chip-active` with `chip-linked`, add `nav-link-active` (elevated fill, accent-strong text, 2px accent bar). |
| §1 Overview `:241` | "32px panel header as the structural unit" | 46px min-height, 13px/600 sentence case | "a 46px sentence-case panel header (13px/600) as the structural unit" |
| §2 Colors `:249`, `:252–258` | "one blue accent"; Secondary "Downstream Consumer"; Tertiary "Tranche Ramp" | iris accent + accent-strong; no consumer or tranche colour exists | "one iris accent (`accent`, with `accent-strong` for text on elevated surfaces)"; delete Secondary and Tertiary or mark them "not implemented — no token, no rule". |
| §3 Typography `:279–281` | Inter / Inter / JetBrains Mono | native stacks; display `"Avenir Next", "Segoe UI", system-ui` | "Display: `--font-display` (Avenir Next on macOS, Segoe UI on Windows, `system-ui` elsewhere) — wordmark, page title, standing answer, reader and admin display. Body: `--font-sans` (`-apple-system` … `sans-serif`). Mono: `--font-mono` (`ui-monospace` … `monospace`). No web font is shipped (enterprise Task 3)." |
| §3 Hierarchy `:286–290` | Display 700; Headline 22; Title 16; Body 12; Label mono uppercase; "10px floor" | §2.1 | Rewrite to the front-matter values above; "Label: sans, 10–11px; uppercase and tracked for table heads and rail group labels, sentence case for kickers and field labels; mono is for identifiers, digests, timestamps and numerics, not for labels. Chrome floor is 9px (TOC ids, evidence digests, forecast labels)." |
| §3 Filed Output Scale `:294` | 14px/650 sections, 13px body, 7.8px mono table labels, appendix 5.2–7px, 12px phone minimum, 0.95rem subhead, emergency 1.125rem | §2.2 | "Output Title 21/650, Output Section 11/700 uppercase, Output Body 12/400/1.62, Output Subtitle mono 10/600, Output Meta mono 8.5/500, Output Table Label 9/650 uppercase, Output Table Body 10/400, Output List 11/400, watermark mono 26/700 at 16 % alpha rotated −16°. The full-model appendix scale belongs to the worker's PDF/XLSX renderers and is not in `globals.css`." Delete the phone, subhead and emergency sentences. |
| §4 Elevation `:306–315` | flat by default; Modal .9; Popover `0 8px 28px -10px .8`; Paper .85; Flat-Until-Floating | panel `0 1px 2px .25`; modal `.85`; pop `0 12px 32px -12px .7` unused; paper `.8` | "Panels carry `--shadow-panel` (0 1px 2px rgb(0 0 0 / .25)); dialogs and the drawer `--shadow-modal` (0 24px 80px -24px / .85); the report paper `--shadow-paper` (0 24px 70px -24px / .8). `--shadow-pop` (0 12px 32px -12px / .7) is defined for a popover the product does not have. Depth otherwise comes from the bg → panel → elevated → subtle ramp, hairlines and 2px inset accent selection bars. Dialog backdrops are 60 % black with a 3px blur." Retire the Flat-Until-Floating rule (already superseded by the addendum). |
| §5 Buttons `:320–323` | 6px corners; "shadow" channel; ghost "border plus muted text" | r8 (small r6); channels border/background/transform; quiet = muted text on elevated | "8px corners (6px small); 160ms border, background and transform; primary is accent fill with bg-coloured 700 text; quiet keeps the fill and mutes the text; small is 30px/11px; disabled is 55 % opacity." |
| §5 Chips `:326–327` | mono, glyphs, selected chips invert to accent | §3.4 | "Evidence chips: 24px pills, mono 10px, accent-strong on a 7 % accent tint with a 65 % accent border; linked state adds a 2px accent outline and a 16 % tint. Chips never invert. Status is a shape glyph plus a 700 label." |
| §5 Cards `:330–334` | 6px; no shadow at rest | r10 + panel shadow; body 12px | "10px corners, hairline, `--shadow-panel`; body padding 12px; header 46px." |
| §5 Inputs `:337–339` | compact radius; disabled "remains readable" | r8, padding 8, focus accent border + 3px 22 % halo; disabled primary 2.96:1 | "8px radius, 8px padding, bg fill, border-strong; focus is an accent border plus a 3px accent-22 % halo (no outline); hover shifts the border 55 % toward text. Disabled is 55 % opacity (primary reads 2.96:1)." |
| §5 Navigation `:342–344` | chips with icons; compact headers show only the active label; tooltips; "Active equals Accent fill" | rail links always show glyph + label; active = elevated fill, hairline, accent-strong text, 2px accent bar; no tooltips | "Rail links show a 14px stroke glyph and the label at every width; active is elevated fill, hairline border, accent-strong text and a 2px accent leading bar; hover is elevated fill and text colour. Below 900px the rail is a horizontally scrolling strip." |
| §5 Enterprise Workbench Anatomy `:346–355` | utility drawer; `View: Analyst / PM / QA`; five visible worklist actions; Evidence Atlas inspector | one evidence context drawer; role shown read-only in `rail-meta`; register has one action per row; evidence rails per surface | Reduce to what exists: identity strip (authority strip), one page-level primary action, one dominant work region, contextual evidence (evidence chips → context drawer; evidence rails on Deep-Dive and Command Center), sticky approval panels. Delete the utility drawer, the View switch and the five-action rule or mark them "not implemented". |
| §5 Panel `:359` | "6px radius, 32px uppercase header, focusable scrollable body" | r10, 46px sentence-case, body scroll only where a region is declared | "Panel Surface, hairline, 10px radius, 46px sentence-case header (13px/600), 12px body; scroll regions (`table-wrap`, worksheet, loan table) are focusable `role=region` containers." |
| §5 Decision states `:350` | eight states incl. `partial`, `offline` | six render distinctly; two have no component | Keep the list but add "`partial` and `offline` currently render through warning statuses and the global error banner; no dedicated component exists (FE-A2 F-08)." |
| §6 Do's `:371–372` | "shared Panel, TextInput, ScopeToggle, StatusGlyph, ConceptNav patterns"; "Running pulse and flash cues must stop" | no such components; no pulse | "use the shared class idioms — `.panel`, `.field`, `.status`, `.button`, `.nav-link`, `.evidence-chip`, `.state-block`, `StateBlock/StateNote/LoadState/Unavailable/MutationReceipt` — before inventing chrome"; "the only animations are the loading shimmer and the dialog rise, both confined to `prefers-reduced-motion: no-preference`; the only non-hover transition is the live progress width." |
| §6 Don'ts `:379` | "no glassmorphism" | 3px backdrop blur behind modals | Add "(the 3px dialog backdrop blur is the one sanctioned blur)". |
| Addendum `:386–401` | "Space Grotesk as the display face" | Avenir Next / Segoe UI / system-ui | Replace with "`--font-display` = `"Avenir Next", "Segoe UI", system-ui` (no web font; enterprise Task 3)". Keep the rest. |

### 11.2 .impeccable.md

| Section | Current text | Truth | Proposed wording |
|---|---|---|---|
| Users `:14–17` | "eight destinations: Cases, Sources, Run Console, Deep-Dive, RV Screener, Command Center, Model Builder, and Report Studio" | nine routes (`workbench.ts:21–30`, `a11y-axe.mjs` route list) | "nine destinations … Report Studio and Admin Studio (an unavailable-capability surface)". Note the rail groups them as seven workflows (Portfolio, Credit, Sources, Analysis, Market, Model, Report) plus Governance/Admin. |
| Aesthetic `:66–69` | `#0a0a0f → #11131d → #1d2030`, border `#34384a`, text `#e6e6ef`, muted `#a1a1b5`, accent blue `#63a1ff` | §1.2 | "`--caos-bg #0a0c10 → --caos-panel #101319 → --caos-elevated #181d28 → --caos-subtle #202632`, hairline `--caos-border #242b38`, control border `--caos-border-strong #606b7e`, text `#e9edf4`, muted `#99a3b4`, iris accent `#8b93f8` with `--caos-accent-strong #a5abfa` for text." |
| `:70–72` | warning `#f5a524`, critical `#ef4444`, success `#22c55e`, idle `#3f3f46` | amber `#fbbf24`, red `#f87171`, emerald `#34d399`; idle = muted | "warning `#fbbf24`, critical `#f87171`, success `#34d399`; idle uses `--caos-muted`." |
| `:73–76` | tranche ramp | not implemented | Delete, or "Seniority is text in the loan table; no tranche colour ramp exists in the code." |
| `:77–80` | Inter + JetBrains Mono; `.tabular`; "9–12px uppercase letter-spaced labels"; "32px uppercase panel header (`<Panel>`)" | native stacks; `.num` carries `tabular-nums`; labels 9–11px, some uppercase; 46px sentence-case `.panel-header` | "Native system stacks (`--font-sans`, `--font-display`, `--font-mono`); numerics use `.num` (`tabular-nums`) or `.mono`; labels are 9–11px sans, uppercase and tracked only for table heads, rail group labels, worksheet tabs and report rail labels; the 46px sentence-case `.panel-header` is the structural unit." |
| `:81–83` | `.transition-caos`, `.caos-running` pulse, `.caos-enter` | none exist; 160ms `--ease-out` transitions inline; no pulse; shimmer + dialog rise only | "160ms `--ease-out` transitions on hover/focus channels; a 240ms width transition on the live progress bar; a 1.6s shimmer on loading skeletons and a 180ms dialog rise, both inside `prefers-reduced-motion: no-preference`; no pulse or enter animation." |
| `:84–87` | "ink `#16161e` on cream" | `#191922` on `#f7f4ec` | "ink `--caos-ink #191922` on `--caos-paper #f7f4ec`, mono mastheads, hairline paper rules" |
| `:88–93` | 21/650, 14/650, 13/400/1.6, 8.5/500, 7.8/600; appendix 14/7/6.5/5.2–5.9 | §2.2 | "paper titles 21px/650, section heads 11px/700 uppercase, body 12px/400/1.62, mono metadata 8.5px/500, table labels 9px/650 uppercase; the appendix scale lives in the worker renderers, not in the web CSS." |
| Accessibility `:107–109` | "Validate the small muted labels (`--caos-muted` on `--caos-panel`) specifically — they sit near the line" | 7.31:1 | "muted on panel measures 7.31:1; the lowest enabled text pair is critical on elevated at 6.10:1; disabled primary buttons read 2.96:1." |
| Addendum `:138–146` | Space Grotesk display | Avenir Next / Segoe UI / system-ui | as DESIGN.md addendum row |

### 11.3 Sidecar

`.impeccable/design.json` (`generatedAt 2026-08-22`) carries the pre-reskin palette (`#0a0a0f`, `#63a1ff`, `#f5a524`, …) and component snippets from that era. FE-G4 regenerates it from the new DESIGN.md or deletes it; as it stands the live panel would render the wrong system.

---

## 12. Atlas index

Full pages (each at `1440-` and `720-`): `01-cases` (Portfolio: intake dropzone, register table, create form, fit panel, context strip) · `02-cases-intake-refusal` (real typed refusal `INTAKE_ADMISSION_REFUSED` for an `.exe`; critical StateBlock with findings list) · `03-sources-evidence-focus` (artifact reader, evidence chips, three-column source workspace, `Unavailable` coverage gate) · `04-evidence-drawer` (viewport) · `05-run-console-accepted` (DAG, progress, "Latest accepted authority") · `06-run-console-ready-for-acceptance` (a real succeeded, unaccepted run) · `07-accept-dialog` (viewport) · `08-run-console-receipt` (after a real accept: `MutationReceipt`) · `09-run-console-paused-plan-approval` (paused `PLAN_APPROVAL_REQUIRED` with the research plan — a11y fixture shapes on a real case; this is the FE-D1 "paused-for-approval" surface) · `10-deep-dive` (reader shell: toc, 780px reader, evidence rail) · `11-rv-screener` (real active loan universe; loan table) · `12-command-center` (standing answer, authority metrics, proof aside) · `13-model-builder-ready` (a11y-style READY fixture: three tabs, fills, selected cell, lineage, tornado) · `14-model-builder-dirty` (1440 only; "What will bind" sign-off panel after editing an assumption) · `15-report-studio` (draft paper) · `16-discard-dialog` (viewport) · `17-admin-studio` · `18-not-found` · `19-command-palette` / `20-command-palette-query` (viewport) · `21-state-loading-skeleton` (snapshot request held; viewport) · `22-state-error` (snapshot 500: global banner, authority strip "Authority unavailable", LoadState error) · `23-state-stale-switch-required` (snapshot fixture with `switch_required`) · `24-command-center-what-changed` (diff list) · `25-state-empty-no-case` (`/api/cases` → `[]`; EmptyPanel) · `26-cases-empty-register` · `27-run-console-reader` (the identity read `/api/me` fixtured to READER; WriteBlocked).

Element clips at 1440 (`1440-c-*`): rail, wordmark, topbar, authority-strip (+ `-loading`, `-error`, `-stale`), nav-hover, input-focus, button-focus-ring, buttons-primary-secondary, panel-register-table, panel-create-form-inputs, panel-fit-status, panel-compile-form-selects, panel-execution-route-dag, panel-artifact-reader-chips, intake-dropzone, context-strip, evidence-chips, evidence-chip-hover-linked, source-workspace, state-unavailable-coverage, state-critical-intake-refusal, state-critical-error-retry, state-empty-panel, state-skeleton, state-write-blocked, drawer, dialog-accept, dialog-discard, dialog-palette, mutation-receipt, dag-tiles, run-progress, callout-neutral, callout-warning-stale, approval-panel-accepted/-ready/-blocked/-model-dirty/-freeze, research-brief-fieldset, research-plan, analysis-toc, analysis-evidence-rail, loan-table, loan-filters, loan-authority, standing-answer, authority-metrics, credit-proof, what-changed-list, worksheet-grid, worksheet-tabs, cell-lineage, forecast-assumptions-scrubber, tornado, report-outline, report-compose, report-authority-strip, paper-draft, paper-masthead, admin-intro-flag, admin-contracts-table. At 720: rail, topbar, authority-strip, state-critical-intake-refusal.

Capture notes: the visible "Skip to content" pill in `1440-02`, `1440-03` and `720-13` is the focused skip link (`:227`), revealed by keyboard focus during automation — it is the skip-link component's own focus state, not a layout defect. Model Builder READY and the paused research plan are Playwright route fixtures in the shapes `scripts/a11y-axe.mjs` uses, because host control yields no READY model and no live approval gate on a seeded case; everything else is real server state seeded by the workbench smoke. The frozen/filed paper (watermark, masthead facts) is not captured (§5).

---

## 13. Commands run and results

From `caos/frontend` unless noted; `$R` is this worktree, `$S` the session scratchpad. Python is the main checkout's 3.14 venv (`/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/.venv/bin/python`, 3.14.6); `caos` imported from this worktree because `dev.py` runs from `$R/caos/server`.

```
node ~/.claude/skills/impeccable/scripts/context.mjs --target caos/frontend/app/globals.css   # PRODUCT.md + DESIGN.md loaded; no surface brief
npm ci --no-audit --no-fund                                    # added 351 packages in 4s
npm run build                                                  # Next.js 16.3.3, compiled 2.2s, 12/12 static pages, out/ present
ENVIRONMENT=development CAOS_PROVIDER=host_control PORT=8773 CAOS_DATA_DIR=$S/data python dev.py
   # first start without AGENT_EXECUTION_ENABLED: POST …/runs → 503 {"detail":{"code":"AGENT_EXECUTION_DISABLED"}}; smoke failed at workbench-smoke.mjs:75
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true PORT=8773 CAOS_DATA_DIR=$S/data python dev.py   # /api/health {"status":"ok","store":true,"bundle":true,"checkpointer":true}
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true CAOS_DATA_DIR=$S/data python worker.py
CAOS_URL=http://127.0.0.1:8773 CAOS_RESULTS_DIR=$S/smoke-results npm run test:workbench
   # exit 0; {"browser":"chromium","timing":{"domContentLoaded":65.4,"firstContentfulPaint":164},"budgetEnforced":true,"caseRequests":1}; 12 cases seeded
node ~/.claude/skills/impeccable/scripts/detect.mjs --json <globals.css, WorkbenchShell.tsx, states.tsx, ModelBuilder.module.css, DeliverableDocument.tsx>
   # 2 warnings: border-accent-on-rounded (globals.css:173), layout-transition (globals.css:249) — assessed in F-09
node .superpowers/sdd/frontend/design/contrast.mjs            # 65 pairs; table in §7
ATLAS_DIR=$R/.superpowers/sdd/frontend/design/atlas CAOS_URL=http://127.0.0.1:8773 node .superpowers/sdd/frontend/design/atlas.mjs
   # {"shots":122,"notes":[]}; measurements → design/atlas-measurements.json
   # The script sends no role header: dev's identity edge treats headerless calls as ANALYST, and the reader
   # capture fixtures /api/me. A first version sent the header and the recorded review blocked it (client-role-trusted);
   # the atlas was regenerated from the header-free script before the pull request was marked ready.
git status --short                                            # only ?? .superpowers/sdd/frontend/
```

Not run (out of scope for an assessment that changed no source): lint, tsc, unit, a11y sweep. The smoke ran once as the seeding step and passed on this build.
