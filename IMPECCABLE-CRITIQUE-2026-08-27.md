# /impeccable critique — CAOS workbench, all surfaces

Date: 2026-08-27 · Companion audit: `DESIGN-IS-2026-08-27/` (Dieter Rams ten-principle audit of the same evidence; verdict REDESIGN at 13/30)

Method: dual-agent (A: design-review subagent · B: detector/browser-evidence subagent, isolated until synthesis)

Target: all surfaces of the CAOS workbench (`caos/frontend`), reviewed as source and live against the seeded combined app (static export + FastAPI on `:54351`; one populated case with a succeeded deterministic EARNINGS_UPDATE run, one empty case). Mode: **Operate** on every surface. The dev server exited on its own near the end of evidence gathering; all findings below were captured before that.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Authority strip and pending labels excellent; but acceptance succeeds silently (Accept button persists enabled), "LIVE" badge is unconditional (`WorkbenchShell.tsx:249`), and "Pathway fit" said NEEDS_SOURCE beside a visible 2-source succeeded run |
| 2 | Match System / Real World | 2 | Pathways and screener speak fluent credit; "Persisted DAG", CP-* ids, `b00004 · {"line":4}` locators, and a raw TypeError as analyst copy do not |
| 3 | User Control and Freedom | 2 | Draft-discard confirms use correct vocabulary; but paused runs have no resume/cancel (the server route exists), acceptance has no path back, Retry is a full page reload |
| 4 | Consistency and Standards | 2 | Panel/status/type systems rigorously consistent; but every nav label differs from its page title, two date formats for one value, native OS confirms beside styled dialogs, `not-found.tsx` drops the mandated trailing slash |
| 5 | Error Prevention | 2 | Research-brief bounds enforced pre-submit; but "Compile and run" on a 0-source case mints a permanently paused run, and acceptance shows nothing it binds |
| 6 | Recognition Rather Than Recall | 1 | CP-PARSE/CP-0/CP-L10/CP-5 never expanded or tooltipped; no run identity echoed on Run Console/Deep-Dive; palette's best trick needs an exact evidence id from memory |
| 7 | Flexibility and Efficiency | 2 | Real ⌘K combobox palette and sortable/paginated screener; but palette is navigation-only (no verbs), no run history, ⌘K is the only shortcut |
| 8 | Aesthetic and Minimalist Design | 3 | The dark ladder, hairlines, mono numerics, zero decoration honor DESIGN.md; deductions for digest walls as primary content and the run console tripled across surfaces |
| 9 | Error Recovery | 2 | Typed refusals are a real strength (SOURCE_SET_EMPTY callout; workbook findings with code/sheet/row); but raw `caught.message` reaches users on five surfaces and Retry renders on permanently unserved routes |
| 10 | Help and Documentation | 1 | A few good inline explanations; otherwise no tooltips, no glossary (CONTEXT.md's vocabulary never surfaces in-product), no onboarding |
| **Total** | | **19/40** | **Poor (12–19): major UX overhaul required at the moments of truth; the visual system itself is solid** |

## Design Specificity Verdict

**LLM assessment (unanchored):** The chrome is authored for this product; the payoff is not. The authority strip's four worded states, "2 immutable objects" with SHA identities, "Ingest safely" under a BOUNDARY panel, the run form explaining its own pinning model, the Command Center's "Analyst boundary" refusal to show system recommendations, and the RV screener's 27 unit-labeled columns with per-row workbook locators could not belong to another product. But the product's center — the analysis — is category-absent: after a succeeded run on real earnings text, the analyst's entire visible reward is a table of SHA-256 digests and four one-line module descriptions. No revenue, no leverage, no citation renders on any reachable screen. Where specificity should peak, the product shows plumbing, and the plumbing speaks engineering, not credit.

**Deterministic scan:** Near-clean — the CLI detector found exactly **1 finding across 24 files**: a `side-tab` accent left-border at `globals.css:253` (`.model-authority-strip`, used once in `ModelBuilder.tsx:714`); the same stylesheet uses left-border marking as an established pattern elsewhere, so this is plausibly design language rather than slop. The in-page runtime pass found 5–8 anti-patterns per page, but almost all collapse to three systematic items: 10px rail/section labels ("Cases", "Workflows", "Tools" — one intentional label style counted on every page), flush panel-header bottom padding on CASE REGISTER and SOURCE INTAKE, and one case-title `strong` flagged as overflowing 352px on all five pages — a **false positive** (deliberate `text-overflow: ellipsis` truncation of a long case name in the shared header). On /report-studio/ the detector measured the 404 error card, not the intended paper preview, because the surface never loads. Where the two assessments agree: the label/type floor sits at the edge (detector's undersized-text hits ↔ A's #8 deductions), and the error surfaces are the weakest pages both saw. What the detector caught that the review missed: the flush panel-header padding. What it cannot see: everything load-bearing — the dead routes, the blind acceptance, the inert DAG.

**Visual overlays:** Injection succeeded on all 5 representative pages; amber overlays with labels are rendered and still visible in the open browser tab ("cramped padding" on the CASE REGISTER and SOURCE INTAKE panel headers, "content overflowing its container" on the header case strip, "wide letter spacing" on the "immutable · versioned" badge). The console reported 8 findings on /cases/, 5–6 on the other pages, matching the DOM overlay count.

## Overall Impression

A genuinely designed institutional terminal — disciplined tokens, real accessibility, honest copy at the boundary — wrapped around a hollow center. The custody chain (sources → digests → acceptance → authority) is beautifully surfaced; the *analysis* it exists to certify is never shown. Three of six workflows dead-end in 404s or a raw TypeError on this deployment, and the product's most authoritative act is a native OS confirm that binds content the analyst has never seen. The single biggest opportunity: make the payoff readable — an artifact reader between "run succeeded" and "accept" would convert the product's strongest idea (traceable authority) from ceremony into utility.

## What's Working

1. **The authority spine is structure, not decoration.** Idle/loading/error/ready are distinct worded states in the case strip (`WorkbenchShell.tsx:154-166,258-262`); views pin to an accepted snapshot until an explicit switch; freeze microcopy explains its own preconditions (`ReportStudio.tsx:434`). "Numbers read as audited" is executed architecturally.
2. **Accessibility far above the norm — and verified.** Skip link, universal 2px `:focus-visible` ring, dialog focus capture/trap/restore, a true combobox palette with `aria-activedescendant`, roving-tabindex tab strips with Home/End, `aria-sort` on all screener columns, 44px coarse-pointer targets, a correctly-reasoned reduced-motion kill — and the shipped axe harness runs green twice (43 combos, 0 violations, including seeded data).
3. **The RV screener and the (coded) deliverable paper are authentically institutional.** Unit-bearing columns, signed deltas, workbook locators, "SOURCE DATA · UNANALYZED"; the paper inverts to cream with "Evidence-bound / Analyst judgment" stamps and an exact-identity digest line. These could not belong to any other product.

## Priority Issues

- **[P0] The primary flow has no payoff and demands blind acceptance.** No reachable screen renders module output content: DAG tiles are inert `<div>`s (`Workspace.tsx:698` — unopenable by mouse or keyboard), Deep-Dive shows only digests, and all four seeded artifacts carry empty narrative and empty `evidence_refs`. The only post-success action is "Accept analytical snapshot" — before inspection is possible, inverting PRODUCT.md's "Show the work behind every conclusion." **Why it matters:** the analyst is asked to certify authority they cannot read; the product's core promise fails at its peak moment. **Fix:** an artifact reader (narrative, sections, `EvidenceChip` citations — component and CSS already exist) opened from DAG nodes and the artifact register, pre-acceptance; move Accept to the end of that reading flow. **Suggested command:** /impeccable shape
- **[P0] Three of six primary nav destinations are dead on arrival, one with a raw stack message.** Command Center (the default landing) double-404s because a `Promise.all` couples the unserved lens to the served snapshot diff (`Workspace.tsx:932`); Report Studio 404s on every visit (`ReportStudio.tsx:195,401`); Model Builder crashes on `inventory?.readiness.status` (`ModelBuilder.tsx:288-289`) and shows "Cannot read properties of undefined (reading 'build')" as analyst-facing copy. **Why it matters:** first impression is a broken terminal; trust — the product's entire currency — evaporates on click one. **Fix:** capability-gate unserved surfaces with an honest "Not available in this deployment" state (DESIGN.md already specifies `unavailable`), split the `Promise.all`, and never pass `caught.message` to users. **Suggested command:** /impeccable harden
- **[P1] The acceptance moment is an unstylable OS dialog with no bound content and no aftermath.** `window.confirm` (`Workspace.tsx:504`) cannot show the digest/run/pathway being made authoritative; success produces no acknowledgment and the Accept CTA persists enabled (observed live post-accept; the embedded browser suppressed the confirm entirely — native dialogs are also environmentally fragile). **Why it matters:** peak-end — the product's most authoritative act is its least designed moment, and double-clicks re-fire it. **Fix:** a styled digest-bound `<dialog>` (the pattern already exists in the app) showing snapshot digest, source-set version, pathway/depth; on success swap the CTA to an "Accepted — visible authority" state. **Suggested command:** /impeccable shape
- **[P1] Paused runs are dead ends.** The SOURCE_SET_EMPTY callout links nowhere, and no resume/cancel exists although `POST /api/runs/{id}/resume` is served (frontend-wide grep for "resume": zero hits). **Why it matters:** a recoverable state is presented as terminal; the analyst's only exit is confusion. **Fix:** action-state callout with "Open Sources" + "Resume run" once sources exist. **Suggested command:** /impeccable harden
- **[P2] Engineering vocabulary leaks into analyst chrome.** "Persisted DAG" (`Workspace.tsx:757`), unexplained CP-* ids everywhere, `b00004 · {"line":4}` locators (`:674`), "worker…Python" (`ModelBuilder.tsx:332`), raw `PLAN_APPROVAL_REQUIRED` / `ANALYST_JUDGMENT` enums beside humanized siblings, dual nav/page naming for every workflow, and two product names ("Credit Operating System" vs "Credit Agent OS"). **Why it matters:** the product demands recall of a vocabulary it never teaches, and its committee-ready voice cracks. **Fix:** human module names beside ids (the registry has them), one naming scheme, humanize every user-visible enum. **Suggested command:** /impeccable clarify

## Persona Red Flags

**Alex (impatient power user):** The ⌘K palette cannot *do* anything — navigation only, no "accept / run / upload" verbs (`WorkbenchShell.tsx:304-355`); typing "cov" yields "No authorized matches," which reads as a permissions problem rather than a miss; no run list or history exists, so a second run silently replaces the console's only view; after Accept, nothing acknowledges success and the button stays — Alex will click twice; the same run form on three surfaces makes "where do I run from" a decision every time.

**Sam (screen reader + keyboard):** The QA button's hardcoded `aria-label="QA unavailable — open QA status"` (`WorkbenchShell.tsx:271`) will lie the moment QA exists and diverges from the visible label (WCAG 2.5.3); two rail links announce `aria-current="page"` simultaneously on /cases/, making "where am I" ambiguous; the rail's Run link reads out as "RunLIVE" (badge span not aria-hidden, `:249`); Model Builder's failure reads a JavaScript TypeError verbatim; the acceptance decision is one spoken sentence with no digest to verify by ear.

**Priya (PM/CIO scanning posture — project persona from PRODUCT.md):** Her surface is the broken one — Command Center's "What changed" diff (exactly her scan) 404s even though its data endpoint returns 200; "Pathway fit" reporting NEEDS_SOURCE on an accepted 2-source case would misinform a coverage scan; and no viewer-role presentation exists, so she sees Accept/Compile operator controls indistinguishable from an analyst's view.

## Minor Observations

- No budget/cost/spend indicator anywhere despite budget-fail-closed being invariant 8 — a budget refusal will surface as an unexplained error.
- Two date formats for the same value: `toLocaleString()` in the strip vs "27 Aug 2026, 10:56" in panels.
- `not-found.tsx:4` links `/cases` without the trailing slash its own `withQuery` comment mandates, drops case context, and the 404 page keeps h1 "Cases" with the default tab title.
- Transient fetch failure collapses to "No case selected" + raw "Failed to fetch" with false guidance to create a case; no `offline` state despite DESIGN.md listing one.
- `.dag-node.running` is a static border — no pulse exists despite DESIGN.md's "running pulse" language; during execution nothing visibly lives, and the reduced-motion guards protect animations that don't exist.
- Deep-Dive's "Open Run Console" links drop the `&run=` param the sidebar preserves; Deep-Dive also carries the app's only unstyled heading (browser-default 14.04px) and only centered text (default table caption).
- Flush panel-header bottom padding on CASE REGISTER / SOURCE INTAKE (detector-confirmed); "Accept analytical snapshot" abuts the DAG at 0px.
- Generated blocks in the frozen paper render as "Field / Value" dumps with slash-path labels (`DeliverableDocument.tsx:49-61`) — functional, not committee typography.
- 623 KB of JS served uncompressed with a 112 KB `nomodule` fallback and a 14 KB unreferenced chunk; `FiledProof.tsx` + `filedMarkdown.ts` are 82 lines of dead code.
- Register rows and topbar disagreed live about acceptance (list payload stale after accept) — two contradicting authority statements on one screen.

## Questions to Consider

1. If the committee would never sign a memo it hasn't read, why does CAOS ask its analyst to accept an analysis whose only visible property is its hash — and what does that teach users about how seriously to take its confirmations?
2. The rail says Analyse, the page says Deep-Dive, the palette says "Open Analyse", the URL says deep-dive: which name is an analyst supposed to say to a colleague?
3. Is "CP-L10" meant to become desk shorthand the way "8-K" did — vocabulary earned through familiarity — or is it a leak? If the former, where does the product teach it?

---

**Trend for `caos-frontend`: first run for this target, no trend yet (19/40).**
Snapshot: `.impeccable/critique/2026-08-27T10-28-16Z__caos-frontend.md`.

## Recommended Actions

The interactive priority interview was skipped (session ran autonomously); the ordering below follows issue severity. Run these one at a time, all at once, or in any order:

1. **`/impeccable shape` — the analysis payoff**: design the artifact reader (module narrative + sections + EvidenceChip citations, opened from DAG tiles and the artifact register) and the digest-bound acceptance ceremony that replaces `window.confirm`, so inspection precedes acceptance. (P0 + P1)
2. **`/impeccable harden` — truthful degradation**: capability-gate Report Studio / Admin Studio / sensitivities / rebase-export behind an honest "Not available in this deployment" state; split the Command Center `Promise.all`; guard the Model Builder readiness dereference; one styled error idiom (never raw `caught.message`); resume control for paused runs; real disabled states. (P0 + P1)
3. **`/impeccable clarify` — one vocabulary**: human module names beside CP-* ids, humanized enums, one product name, nav labels matching page titles, "line 4" instead of JSON locators. (P2)
4. **`/impeccable polish`** — after the above land: the flush panel headers, 0px Accept gap, unstyled Deep-Dive heading/caption, date-format unification, `not-found` link.

Re-run `/impeccable critique` after fixes to see the score move.
