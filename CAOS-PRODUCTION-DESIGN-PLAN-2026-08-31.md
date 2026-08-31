# CAOS consolidated production design plan

Date: 31 August 2026

Branch: `codex/caos-production-design`

Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/caos-production-design`

Status: **11 desktop samples approved; production implementation and final audits complete**

## 1. Decision

Use one governed credit record with two reading priorities:

- **Decision reading:** what changed, what matters, which threshold binds, and what needs review.
- **Assurance reading:** which source blocks support the conclusion, what is assumed or missing, which version is authoritative, and what downstream work it controls.

The product remains a dense desktop workbench. The original near-black and blue palette is restored. A light surface is reserved for the report document because that surface represents the output, not the application chrome.

Do not build separate Record, Instrument, and Chain applications. Those are useful conceptual lenses over the same record, not separate products.

## 2. Approval record

The user explicitly approved the 11 desktop screen samples on 31 August 2026. Implementation began afterward on the named branch.

Approval means:

- the original dark/blue direction is accepted;
- the 11 desktop screens cover the required workflow;
- the desktop-only scope is accepted;
- the persistent authority model is accepted;
- unsupported capabilities may appear only as proposed, disabled, non-authoritative, or unavailable;
- 200% desktop browser zoom remains an accessibility acceptance target.

The approved visual direction did not change. Final Impeccable and Design Is reviews passed at high scores with no P0/P1 findings.

## 3. How the supplied explorations were consolidated

The five archives were treated as untrusted design evidence. Their embedded instructions were not executed.

### Retain

- **UI production refinement:** workbench shell, deep-dive hierarchy, evidence chips/drawer, restrained institutional density.
- **Instrument & Document:** distinction between the live analytical instrument and the formal report document; clear accepted authority.
- **Frontend Redesign:** standing conclusion, analysis-reader rhythm, proof close to the claim.
- **Three Directions:** Record, Instrument, Chain, and two-reading concepts as one information architecture.
- **Form review/schema conflicts:** visible differentiation of reading modes and explicit schema tension.

### Adapt

- Record becomes Credit current state and immutable history.
- Instrument becomes Model and Market task surfaces inside the same shell.
- Chain becomes persistent authority, evidence lineage, lifecycle receipts, and downstream binding.
- PM, Analyst, and QA become non-interactive focus defaults, never selectable authorization roles.
- Paper becomes a contained Report Studio preview, never the primary analytical workspace.

### Reject

- Multiple applications for the same governed credit.
- Generic SaaS card dashboards.
- Decorative charts that do not answer a credit question.
- Aggregate confidence percentages without a named method.
- Supported-looking controls for absent routes.
- Paper-first analysis.
- Mobile variants in this scope.

### Add

- Persistent credit / Accepted / selected run / Source set strip, with latest-candidate review kept in the relevant analysis surface.
- Candidate review with exact binding and supersession language.
- Citation and assumption counts instead of an opaque confidence score.
- Eight common decision states and mutation receipts.
- Explicit contract gates for portfolio summary and evidence coverage.
- Truthful admin and sensitivity unavailable states.

## 4. Navigation and workflow

### Primary navigation

| Production destination | Consolidated purpose | Existing concepts absorbed |
|---|---|---|
| Portfolio | Triage monitored credits by new information, threshold distance, and evidence freshness | Cases, Command Center |
| Credit | Current accepted conclusion, latest candidate delta, binding measure, proof, and gaps | Credit overview, Standing Answer |
| Sources | Source register, source reader, selected evidence, extraction status, and claim coverage | Sources, Evidence Atlas |
| Analysis | Run, partial findings, completed reader, citation rail, comparison, and acceptance review | Run Console, Deep Dive, Reader |
| Market | Locked loan universe and governed comparative fields | RV Screener |
| Model | Accepted inputs, assumptions, forecast worksheet, lineage, QA, preview, and sign-off | Model Builder |
| Report | Outline, editor, evidence binding, paper preview, freeze, approval, and filed export | Report Studio |
| Admin | Honest unavailable state until audit, membership, and step-up contracts are served | Admin Studio |
| State spec | Design/development reference; not a normal production destination | Shared state catalogue |

### Core workflow

`Portfolio → Credit → Sources → Run → Partial/complete analysis → Evidence → Review → Acceptance → Model / Report / Portfolio`

Users may inspect non-linearly. The shell must retain the selected case, visible version, accepted version, source-set identity, and current route without implying that navigation changes authority.

## 5. Visual system

### Colour tokens

| Token | Value | Use |
|---|---|---|
| Base | `#0a0a0f` | application canvas |
| Rail / panel | `#11131d` | navigation and primary panels |
| Elevated | `#1d2030` | selection and grouped emphasis |
| Subtle fill | `#25293b` | restrained secondary state |
| Rule | `#34384a` | non-essential separators |
| Strong rule | `#5f6680` | control boundaries and essential division |
| Ink | `#e6e6ef` | primary text |
| Muted | `#a1a1b5` | secondary text |
| Blue | `#63a1ff` | focus, current selection, accepted authority, primary action |
| Amber | `#f5a524` | review, assumption, warning, candidate |
| Red | `#f87171` | error, missing authority, critical gap |
| Success border | `#22c55e` | verified successful state |
| Paper | `#f7f5ee` | report document only |
| Paper ink | `#16161e` | report document text |

The production implementation must use named semantic tokens. Do not copy the preview’s 33 spacing literals or 12 type sizes verbatim. Define a compact scale first and map exceptions explicitly.

### Shape and hierarchy

- Square or near-square panels and controls.
- No decorative gradients, glass, shadows, pills, or oversized marketing headings.
- Blue identifies current/accepted/actionable states; amber identifies review/assumption; red identifies failure or critical gap.
- Colour is never the only carrier of meaning.
- Monospace is reserved for identifiers, versions, locators, times, digests, and tabular figures.

### Layout targets

- Supported desktop/laptop widths: 1280, 1366, 1440, 1600, and 1920 CSS pixels.
- Desktop browser zoom at 200% is required; wide tables and authority strips may scroll within a named component, never at the page level.
- No mobile layout, breakpoint, sample, or mobile acceptance test is part of this plan.

## 6. Shared production primitives

Reuse current code before adding new components:

- `caos/frontend/src/components/WorkbenchShell.tsx` for navigation, current case, drawers, and authority.
- `caos/frontend/src/components/states.tsx` for loading, error, unavailable, and live status behavior.
- `caos/frontend/src/lib/workbench.ts` and `workspaceAuthority.ts` for route identities, snapshot authority, and stale-response protection.
- `caos/frontend/src/lib/api.ts` for requests and unavailable-route classification.
- `caos/frontend/src/components/EvidenceChip.tsx` for evidence locators.

Minimum shared additions, only if existing primitives cannot cover them:

1. **Authority strip:** accepted snapshot, candidate/run identity, source-set version/digest, and divergence state.
2. **Decision state:** loading, ready, no-change, stale, partial, offline, error, unavailable/disabled.
3. **Mutation receipt:** saving, saved, failed, switched, accepted, signed, frozen; supports `role=status` or alert semantics.
4. **Evidence summary:** citation, assumption, gap, contradiction counts backed by exact IDs.
5. **Scrollable region:** focusable, named table/worksheet container for desktop zoom.

Do not create a parallel design-system package, a role-layout framework, or a new state machine. Extend the existing patterns with the smallest shared implementation that covers all callers.

## 7. Screen specifications

### 7.1 Portfolio

Purpose: decide which credit to open next.

Show:

- proposed attention-order explanation;
- current accepted/candidate review state;
- binding metric and threshold on the same row;
- evidence freshness/gap state;
- one clear Open credit action.

Contract gate: until a governed portfolio-summary response exists, show the existing basic case register and a clear unavailable/proposed explanation. Do not calculate an attention score in the client.

### 7.2 Credit current state

Purpose: understand the current accepted conclusion and the candidate delta in one reading.

Show:

- accepted/candidate version control;
- standing conclusion;
- current measure, threshold, tolerance, and liquidity;
- engine calculation separately from analyst call;
- exact change deltas;
- proof, gaps, and “would change the call” counterfactual.

Never call an unaccepted run a snapshot version without its run/artifact identity.

### 7.3 Sources

Purpose: inspect the locked source set and understand how evidence supports material claims.

Show:

- document search/filter and extraction state;
- source register with period/audit/exception labels;
- document reader and selected source block;
- exact locator, extractor confidence, and extractor version;
- directly sourced, calculated, and forward-looking distinctions;
- proposed claim coverage only when served; otherwise an unavailable coverage block.

### 7.4 Analysis reader

Purpose: read the analytical answer with evidence and limitations beside it.

Show:

- candidate/accepted state;
- conclusion, change explanation, accepted/latest/threshold table;
- risk mechanics and downstream implication;
- assumptions and counterfactual;
- exact citations with source/block destinations;
- provenance, contradictions, and evidence summary.

### 7.5 Market comparison

Purpose: compare governed market and credit measures within a locked universe.

Show only fields in the active universe response: issuer, instrument, seniority, rating, price, spread, yield, leverage, fixed-charge cover, liquidity, maturity, and source lineage.

Do not restore a percentile until the server defines calculation, comparables, missing-data behavior, and minimum universe size.

### 7.6 Model Builder

Purpose: understand which accepted authority feeds the model, change analyst assumptions, preview exact effects, and sign a governed revision.

Reuse `ModelBuilder.tsx` and `modelBuilderState.ts`.

Requirements:

- accepted input identity and candidate exclusion;
- read-only reported history versus editable analyst assumptions;
- current exact preview before sign-off;
- non-empty sign-off note;
- build, registry, parent revision, preview digest, and input fingerprint checks;
- named QA results and lineage;
- unavailable state for unserved sensitivity, rebase, or export routes.

### 7.7 Report Studio

Purpose: compose from accepted analysis and signed model outputs, then freeze the exact authority before independent approval and filed export.

Reuse `ReportStudio.tsx` and `DeliverableDocument.tsx`.

Requirements:

- outline, editor, evidence inspector, and contained paper preview;
- saved/dirty/saving/conflict/error status;
- draft preview labelled non-authoritative;
- freeze disabled while dirty, saving, conflicted, incomplete, or bound to stale authority;
- independent approver requirement;
- export only for filed deliverables.

### 7.8 Admin Studio

Purpose: explain deployment status and governance requirements without fabricating privileges.

Default for the inspected deployment:

- administrative capability unavailable;
- no audit rows, verified session, export action, or membership editor;
- identity role and case role explained separately;
- required routes and failure states listed.

Only replace this screen after audit, export, membership, and step-up contracts are served and tested.

### 7.9 Run in progress

Purpose: retain trust while analysis is incomplete.

Show:

- accepted version remains visible;
- completed/total stages and current stage;
- available findings separated from waiting findings;
- source exceptions with consequence;
- source-set lock and safe-leave/resume behavior;
- progress derived from nodes/stages, never invented precision.

### 7.10 Acceptance review

Purpose: review the exact material changes and accept the correct run/source set.

Show:

- material conclusion changes;
- per-section evidence/gap/assumption summary;
- exact candidate run and source-set identity;
- readiness checks derived from actual review behavior;
- accepted action disabled until identity and run readiness resolve;
- neutral close action that keeps the current acceptance;
- immutable/supersession and independent visible-version language.

### 7.11 State and recovery contract

Purpose: provide one implementation reference for every dominant work region.

Required vocabulary:

- loading;
- ready;
- no change found;
- stale;
- partial;
- offline;
- error;
- unavailable/disabled;
- saving, saved, failed, switched, accepted, signed, frozen.

Every state must answer: what happened, what remains safe, what authority is visible, and what the user can do next.

## 8. Capability and contract matrix

| Capability | Current truth | Production treatment | Dependency |
|---|---|---|---|
| Basic case register | Served | Ship | Existing cases route |
| Attention ordering/summary | Not served | Basic register plus proposed/unavailable message | Governed portfolio-summary response |
| Source list/read/upload | Served | Ship | Existing source routes |
| Claim-to-source coverage | Not normalized | Show unavailable unless a governed artifact is present | Evidence-summary/claim-map contract |
| Run stages/events/resume | Served | Ship, derive progress from stages/nodes | Existing run/SSE/resume routes |
| Candidate artifact review | Served at run/artifact level | Identify run and artifacts explicitly | Existing run/artifact routes |
| Snapshot acceptance/switch | Served | Ship immutable receipt and explicit switch | Existing snapshot routes |
| Loan universe rows | Served | Ship declared row fields | Existing universe routes |
| Relative percentile | Not defined | Omit | Deterministic server formula and metadata |
| Model preview/sign-off/scenario | Served | Ship with real prerequisites | Existing model routes |
| Model sensitivity | Not served in inspected API | Disabled/unavailable | Served sensitivity route |
| Report draft/freeze/approval/filed export | Served | Ship with authority and dirty-state gates | Existing deliverable routes |
| Draft PDF preview | No standalone route | Non-authoritative client preview only | Optional explicit preview contract |
| Admin audit/membership/step-up | Not served | Unavailable screen | Served admin contracts |
| Saved views | Not served | Omit | Persistence and sharing contract |

## 9. Interaction and state rules

- Navigation changes visibility, not authority.
- Accept, sign, freeze, approve, switch, and file always identify the exact object they mutate.
- A stale response must not overwrite a newly selected case, run, or version; keep the existing authority-generation/request guards.
- A disabled control includes a visible reason when the blocker is not self-evident.
- Composite selectors use the appropriate tablist/tab/tabpanel or menu-button pattern, name the controlled content, implement arrow-key behavior, and announce selection without moving authority.
- Destructive or immutable actions show consequence before activation and a receipt after success.
- Error/offline/partial states preserve accepted read access wherever safe.
- Report editing requires a durable recovery path: server retry plus a timestamped recoverable browser copy, automatic retry, and downloadable/copyable recovery only as a fallback. A failed save never claims recovery unless the copy is actually present and tested.
- Only the newest asynchronous receipt enters the polite live region; the static history remains readable without being re-announced.
- Role words in layout labels never alter authorization. Authorization comes only from identity and case membership.

## 10. Accessibility acceptance

- WCAG 2.2 AA text and essential non-text contrast.
- First-focus skip link to a focusable main region.
- Named navigation and complementary landmarks.
- Visible two-pixel focus ring on every interactive element.
- Native controls and correct table headers; real tablists use arrow-key behavior.
- `aria-current`, `aria-pressed`, or `aria-selected` matches visible state.
- Composite controls provide correct ownership, selected-panel relationships, and arrow-key behavior.
- Live status/alert semantics for asynchronous receipts and failures.
- Named progressbar with value and text.
- Focusable, named scroll regions for wide tables and worksheets.
- No page-level horizontal overflow at supported widths or 200% zoom.
- Reduced-motion behavior; no decorative idle motion.

## 11. Implemented sequence after approval

### Phase 0 — Capability map and fixtures

- Produce a control-to-capability matrix from the approved screens.
- Identify each control’s existing handler/API or unavailable reason.
- Add representative accepted/candidate/run/source/report fixtures to existing tests only where necessary.
- Decide the portfolio-summary and claim-map response contracts or explicitly defer them.

Exit: no visible control has an unknown behavior.

### Phase 1 — Tokens, shell, and shared states

Likely files:

- `caos/frontend/app/globals.css`
- `caos/frontend/src/components/WorkbenchShell.tsx`
- `caos/frontend/src/components/states.tsx`
- `caos/frontend/src/lib/workbench.ts`
- `caos/frontend/src/lib/workspaceAuthority.ts`

Work:

- map the approved palette and compact type/spacing scale;
- update shell/navigation/authority strip;
- add only the missing shared receipt and scroll-region behavior;
- preserve current stale-request guards and drawer behavior.

Exit: shell, authority, focus, zoom, and shared states pass before route redesign.

### Phase 2 — Core evidence workflow

Likely files:

- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/EvidenceChip.tsx`
- `caos/frontend/src/lib/artifactReader.ts`

Work:

- Sources register/reader/evidence;
- run progress and partial findings;
- completed analysis reader and exact citations;
- acceptance review and receipts.

Exit: one end-to-end case can move from source inspection through acceptance with exact authority.

### Phase 3 — Credit and Portfolio

- Build Credit current state from accepted/candidate artifact truth.
- Keep Portfolio on the current case register unless the new summary contract is approved and served.
- Add the attention view only through a server-owned response, never a client heuristic.

Exit: every portfolio value traces to a declared response field.

### Phase 4 — Model and Report

- Restyle the existing Model Builder without replacing its preview/sign-off guards.
- Restyle the existing Report Studio without weakening autosave, conflict, freeze, or approver gates.
- Preserve unavailable handling for unserved routes.

Exit: accepted authority flows into a signed model and frozen report with exact receipts.

### Phase 5 — Market and Admin gates

- Restyle the served universe comparison; omit undefined percentile.
- Replace Admin only to the truthful unavailable screen unless contracts land first.

Exit: no screen implies unsupported capability.

### Phase 6 — Verification and rollout

- Run unit tests beside current helpers/components.
- Add the smallest browser test covering shell authority, Sources → Analysis → Review, model sign-off prerequisites, report freeze prerequisites, and unavailable Admin.
- Verify 1280/1366/1440/1600/1920 and 200% zoom.
- Run keyboard, screen-reader landmark/name, contrast, reduced-motion, stale-response, and failure-state checks.
- Re-run Impeccable, Design Is, rewrite tournament, and confidence review.

Exit: no P0/P1 findings, approved visual comparison, and all contract gates verified.

## 12. Test strategy

Extend existing tests instead of creating a new harness:

- `WorkbenchShell` and `workspaceAuthority` tests: accepted/run/source-set identity, stale selection, unavailable authority.
- `workbench.test.ts`: route and display helpers.
- `artifactReader.test.ts`: evidence locators, gaps, assumptions, contradictions, missing artifact behavior.
- `ModelBuilder.test.ts` and `modelBuilderState.test.ts`: preview currency, note prerequisite, authority change, unavailable sensitivity/export.
- `ReportStudio.test.ts`: dirty/saving/conflict/error, freeze readiness, case-standing approval, filed-only export.
- Report recovery tests: timestamped scope-bound copy, reload restoration, automatic retry, explicit download/discard, structural bounds, and stale-version conflict preservation.
- One browser flow for navigation, focus, named scroll regions, acceptance receipt, and desktop zoom.

Do not add mobile snapshots or mobile browser projects.

## 13. Risks and controls

| Risk | Control |
|---|---|
| Mock values drift from server truth | Contract matrix; fixtures from wire responses; unavailable fallback |
| Redesign weakens authority guards | Reuse `workspaceAuthority` and existing generation checks; regression tests |
| Dense screens become inaccessible | Compact token scale, named scroll regions, 200% zoom and keyboard checks |
| PM/QA focus labels imply roles | Keep them non-interactive presentation defaults; never feed authorization |
| Admin UI overstates governance | Unavailable by default until routes and failures are served |
| Model/report styling bypasses prerequisites | Preserve current handler conditions and test exact blockers |
| Scope expands into mobile | Explicitly exclude mobile from stories, breakpoints, samples, and acceptance |

## 14. Final implementation checklist

- [x] User explicitly approved all 11 desktop samples.
- [x] Design Is 27/30 REFINE moves were accepted.
- [x] Pre-build Impeccable findings were P1-free.
- [x] Control-to-capability matrix is complete.
- [x] Token scale is agreed.
- [x] Portfolio-summary and claim-map contracts are deferred behind explicit unavailable states.
- [x] No mobile requirements are present in implementation tickets.
- [x] Application build started only on `codex/caos-production-design`.
- [x] Application routes and shared shell were implemented in the separate worktree.
- [x] Impeccable scored 34/40 with P0 0, P1 0, and detector `[]`.
- [x] Design Is scored 26/30 with no principle below 2.
- [x] Unit tests, lint, TypeScript production build, and 70-combination desktop accessibility audit pass.

## 15. Final outcome

The application now implements the approved desktop direction with the original dark/blue palette, one governed record, explicit accepted/selected/source-set authority, truthful contract gates, a source/evidence reader, generation-fenced Analysis switching, server-owned Model workflows, and recoverable Report Studio drafts. Mobile remains excluded.

Remaining items are P2 refinements only: reduce dense Model/Report control groups, define task-oriented help before building it, and optimize packaged fonts/shared snapshot reads if production profiling proves material benefit.
