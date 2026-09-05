# CAOS workbench: information-architecture design brief for Claude Design

Date: 2026-09-05. Source: `.superpowers/sdd/frontend/frontend-a1-ia-audit.md` (FE-A1). This brief stands alone; the audit carries the evidence.

## 1. Purpose

CAOS is a credit-analysis workspace for institutional leveraged-finance credit specialists. It turns source documents, market marks, module outputs and evidence trails into committee-ready credit conclusions. A specialist must inspect dense credit information quickly, trace every material number back to evidence, and defend the resulting view under scrutiny. Register: product, not brand. Personality: precise, defensible, alert. It should feel like a refined institutional terminal: calm enough for committee work, live enough for market posture, exact enough that numbers read as audited rather than decorative.

The MVP standard is enterprise-testing readiness. Source documents are the only required analytical input. CAOS prepares the evidence, executes the governed analysis, presents a reviewable interpretation, preserves the analyst's ownership of the opinion, and publishes exact approver-authorized files.

## 2. The three personas (from PRODUCT.md)

- **Buy-side credit analyst (primary).** Builds a defensible credit view across the analysis reader, Model and Report. Drops documents, reviews the machine analysis, accepts it, adjusts model assumptions and signs a revision, composes the deliverable, signs the opinion and freezes. When a trade-off forces a choice, optimise for this person.
- **PM / CIO (secondary).** Scans posture and change: which credit needs attention, what changed since the last accepted analysis, and the evidence behind the change. Reads, rarely writes.
- **Head of Research / QA (secondary).** Oversees coverage health, evidence quality and governance: source coverage, the audit trail, member provisioning, the audit package.

Personas are presentation preferences. They never grant or deny authorization; authorization comes only from identity and case membership.

## 3. What exists today (one paragraph)

Nine static routes: `/cases/`, `/command-center/`, `/sources/`, `/run-console/`, `/deep-dive/`, `/rv-screener/`, `/model-builder/`, `/report-studio/`, `/admin-studio/`. The rail already uses eight words: Portfolio, Credit, Sources, Analysis (with a "Run" tool link beneath it), Market, Model, Report, and Admin under a separate Governance group. The page kickers and titles use a third vocabulary ("Portfolio / Surveillance — Monitored credits", "Analysis / Execution — Run and acceptance", "Analysis / Reader — Accepted analysis"), the browser tab a fourth ("CAOS — Cases", "CAOS — Run Console", "CAOS — Deep-Dive"). The shell carries a persistent authority strip (Credit, Visible snapshot, Selected run, Source set), a case selector, a "Sources & evidence" shortcut and a ⌘K command palette (groups: Cases, Workflows, Tools). Every human gate has its own identity: the research-plan approval and the acceptance dialog on the run console; the opinion sign-off, the freeze and the filing on Report.

## 4. Directions to draw

Draw each direction as its own artboard set: the shell with rail and authority strip at 1440 wide, the same shell at 720 wide (200 % zoom), and the Analysis surface paused for research-plan approval. Put the recommended direction in `Main.dc.html`. Keep these names for the rest of the series.

### Direction "Align" (recommended)

Eight destinations plus one tool, one vocabulary end to end: URL, rail, kicker, page title and browser tab all use the same word. Portfolio `/portfolio/`, Credit `/credit/`, Sources `/sources/`, Analysis `/analysis/` (the accepted reader) with its tool Run `/run/` (execution, the research-plan gate and acceptance), Market `/market/`, Model `/model/`, Report `/report/`, Admin `/admin/`. Nothing merges; every surface keeps its interior.

- Motivation: the audit found four vocabularies for nine surfaces and the rail's is already the approved one; renaming closes the seam without redrawing a single interior, and every human gate keeps the home it has today.
- Trade-off: Analysis stays two surfaces (reader and run), so the PM's "Review latest run" still leaves the reader, and the analyst still arrives at a run console whose compile form shows defaults unrelated to the run on screen.

### Direction "Absorb"

The 31 August plan taken literally: eight destinations, no tool. Analysis is one surface with two modes chosen by the authority in the strip: when the selected run is unaccepted, live or paused, Analysis shows execution and the gate; when the visible snapshot is accepted and no live run is selected, it shows the reader. Run progress, compilation and acceptance keep exactly one home: Analysis.

- Motivation: one word, one route, one place for the analyst's whole review-and-accept loop; the reader and the run stop competing for the name "Analysis".
- Trade-off: the surface's primary mode is chosen by data (which run is selected, whether it is accepted), so the artboard set must show the mode switch explicitly and the implementation must merge two views and move twelve smoke steps and the accessibility fixture; the riskiest of the four.

### Direction "Lifecycle"

"Align" plus two moves: Market becomes a tool under Sources ("Loan universe": the CP-3 workbook is uploaded source material, labelled "Source data · unanalyzed" today), and the served governance controls move to Admin: member provisioning (served, today hidden inside Report) and the audit-package download (served, today reachable by no surface at all). The unserved Admin rows (audit rows, bundle integrity, step-up) stay "Not served".

- Motivation: the rail reads as the workflow in order (Portfolio → Credit → Sources → Analysis → Model → Report → Admin) and QA's tasks stop being scattered across Report and the API.
- Trade-off: Relative Value analysts lose a one-click Market destination, and Admin stops being purely "unavailable", so its state design must distinguish served from unserved rows honestly.

### Direction "Labels"

No route change. Kickers, page titles and tab titles adopt the rail's words; slugs stay as they are (`/run-console/`, `/deep-dive/`, …).

- Motivation: cheapest close of the visible seam, zero risk to retained deep links.
- Trade-off: the URL is what an analyst pastes to a colleague, and it keeps saying Deep-Dive, Command Center and RV Screener.

## 5. Screens and states every direction must show

Each artboard uses real product copy (section 7), the tokens in section 8, one page-level primary action, the authority strip, and a glyph or text beside every status colour.

1. **Portfolio with intake.** The "Analyze documents" drop zone (empty, uploading, refused with the typed code and per-file findings, admitted with the host-classification facts and the source disposition manifest), the monitored-credit register with "Open credit", the create-case form as an advanced control, "Portfolio ordering is not yet governed." Show the paused-for-approval and analysis-in-progress blocks that appear inside the panel.
2. **The Credit reading.** Accepted conclusion, accepted snapshot / source set / module outputs / evidence references, "What changed" (the snapshot diff, including the no-change wording "No material module or source-set change is present in the served snapshot diff."), "Read accepted analysis" as the primary action, "Review latest run", the Proof and gaps rail with "Binding measure and claim gaps — Not available in this deployment." Also the no-snapshot state: "Credit state unavailable".
3. **Analysis, four states.** Running (progress bar "n of 17 modules complete", module tiles with "Open output"); paused for approval (the proposed research plan with plan hash, methodology build, brief digest, source set, workstreams, "Approve research plan"); succeeded and unaccepted ("Ready for acceptance", "Accept analytical snapshot", and the dialog naming run, pathway, source set, slots added/replaced/removed, the snapshot digest it replaces); accepted ("Latest accepted authority", the visible-lens sentence). For "Absorb", show how the reader and the run share the surface.
4. **Sources with the evidence drawer open.** Evidence focus (a module output with its lineage and evidence chips), the source register, the source reader with block locators ("line 4", "lines 12–40"), the evidence-support rail, "Claim coverage — Not available in this deployment.", and the drawer (Source ID, SHA-256, Visible snapshot, Visible source set, available source text, "Open full source").
5. **Market.** The governed loan universe: workbook upload, "Active authority · v1", the 27-column screener, "Relative percentile unavailable". For "Lifecycle" draw it as a Sources tool.
6. **Model with a stale revision.** The model versions table with the Application version, an ACTIVE revision and a STALE revision (with "Rebase"), the assumptions worksheet, the sign-off panel ("What will bind", preview digest, accepted snapshot, application build, "Sign-Off Note", "Save model version"). Also the not-ready state with its way out ("Accepted analysis required" → "Open Run Console"), and the dead-end state the audit found ("CANONICAL MODEL INPUTS INVALID" with no link out).
7. **Report with an unsigned opinion and a filed deliverable.** The three-column studio (Structure, Compose, paper preview): the freeze checklist with the opinion row "Blocked — No signed opinion yet.", the opinion form (Opinion, Limitations, Material overrides, Rationale, "Sign opinion on saved vN"); the immutable review of a FROZEN record ("Pending approval · the frozen bytes never name an approver", separation-of-duties line, "File exact Frozen version", "Request changes"); the FILED record with the detached receipt and MD/PDF/XLSX downloads; "Stale model identity" when the authority moved. Paper stays light. Show how the pathway template is chosen and how an approver arriving from a link finds the pending FROZEN record: today the studio opens on Full Credit and the Draft, Frozen and Filed histories belong to the selected template.
8. **Admin unavailable.** "UNAVAILABLE — Administrative authority is not served by this application build." with the required-contracts table. For "Lifecycle", add the served rows (member provisioning, audit package) as controls and keep the rest "Not served".
9. **The shell at 1440 and at 720.** At 720 the rail becomes a horizontal strip that scrolls to keep the active entry visible, the authority strip scrolls inside itself, and no page scrolls horizontally.
10. **Shell edge states.** Unknown route ("Page not found" with the case selection kept), no case selected ("Create or select a case before entering an analytical workspace."), identity failure ("Authority unavailable"), reader view (write panels replaced by "Reader access: … is an analyst action.").

## 6. Rules ("must not" lines)

- Must not give run progress, compilation or acceptance more than one home.
- Must not add any field to the intake surface: it posts files and nothing else. Issuer, label, document types, periods, dispositions and the route are labelled machine suggestions.
- Must not merge, hide or rename away any human gate: research-plan approval, acceptance, opinion sign-off, freeze and filing each keep a visible identity and their digest-bound facts.
- Must not draw a control for a route the server does not serve (attention ordering, claim coverage, binding measure, relative percentile, audit rows, bundle integrity, step-up, one-way sensitivity where absent).
- Must not remove the authority strip (Credit, Visible snapshot, Selected run, Source set) from any surface, or let navigation imply a change of authority.
- Must not redesign the visual language: the dark workspace and the light paper counterpoint are settled; tokens stay in `caos/frontend/app/globals.css`.
- Must not turn Analyst / PM / QA into roles, tabs that grant anything, or a selector that changes what a user may do.
- Must not encode status by colour alone, use emoji in chrome, or add motion that is not live state.
- Must not use placeholder text; every string is product copy from section 7 or from the running app.

## 7. Copy that must appear verbatim

From `CONTEXT.md` (use these terms and never their "avoid" equivalents):

- Model Build (not base model, system model, canonical workbook); Analyst Model Revision (not edited model); Checkpoint; Draft Revision (not unsaved model); Signed-Off Revision (not approved model, published model); Sign-Off (not approval, ratification, publication); Active Analyst Model (not latest model, current build); Sign-Off Note (not assumption note, change message); Assumption Registry; Assumption Guardrail; Base Case; Downside Case; Stale Revision (not expired model, old model); Rebase Candidate (not migrated model); Scenario Run (not saved scenario); One-Way Sensitivity; Multi-Driver Scenario; Apply to Draft; Liquidity Headroom; Covenant Headroom; Breakpoint.
- Deliverable (not report type, output pack); Pathway Template: Investment Committee Credit Memo, Earnings Update, Covenant and Refinancing Brief, Relative Value Note, Scenario and Recovery Pack, Evidence-Bound Research Memorandum; Credit Snapshot (the opening section of a Deliverable, not a separate Deliverable); Deliverable Appendix; Deliverable Draft (not report draft, working paper); Generated Block (not locked text); Narrative Block (not free text); Scenario Exhibit; Evidence Citation (not footnote); Analyst Judgment (not unsupported claim); Frozen Deliverable (not final draft, report snapshot); Filed Deliverable (not published report, final report).

From the running app (accessible names that tests pin; keep them unless the audit's decisions rename them): "Accept analytical snapshot" (button and dialog title), "Approve research plan", "Analyze documents", "Open review", "Open credit", "Read accepted analysis", "Review latest run", "Sources & evidence", "Open command palette", "Evidence focus", "Source register", "Latest accepted authority", "Ready for acceptance", "Sign opinion on saved vN", "Freeze saved vN", "File exact Frozen version", "Request changes", "Provision member", "Not available in this deployment.", "Reader access: … is an analyst action."

Pathway names: Full Credit, Earnings Update, Covenant & Refinancing, Relative Value, Distressed & Restructuring, Deep Research.

## 8. Tokens and components to match

Match from source, pixel for pixel. Say in one line what you matched.

- Tokens: `caos/frontend/app/globals.css` `:root`. Surfaces `--caos-bg #0a0c10`, `--caos-panel #101319`, `--caos-elevated #181d28`, `--caos-subtle #202632`; borders `--caos-border #242b38`, `--caos-border-strong #606b7e`; text `--caos-text #e9edf4`, `--caos-muted #99a3b4`; accent `--caos-accent #8b93f8`, `--caos-accent-strong #a5abfa`; semantics `--caos-warning #fbbf24`, `--caos-critical #f87171`, `--caos-success #34d399`; paper `--caos-paper #f7f4ec`, `--caos-ink #191922` and the paper meta/rule/link/success/warning/watermark/critical set; spacing 4/8/12/16/24/32; radii 6/8/10/14 and pill; shadows panel/pop/modal/paper; `--ease-out cubic-bezier(.25,1,.5,1)`; fonts: native sans stack, display "Avenir Next"/"Segoe UI"/system-ui, mono ui-monospace stack. Body 14px/1.55.
- Shell: `caos/frontend/src/components/WorkbenchShell.tsx` and the matching rules in `globals.css`. `.app-shell` grid 224px rail + workspace; `.rail` sticky, `.wordmark` ("CAOS / Credit Agent OS"), `.nav-group` with `.nav-label` (10px uppercase, .14em tracking) and `.nav-link` (38px min height, 8px radius; active entry: elevated fill, accent-strong text, a 2px accent bar on the leading edge, `aria-current="page"`); `.governance-nav`; `.rail-meta` (role, credit, "Desktop workbench"); `.topbar` (76px min, kicker `.meta-label` 11px/650 + `h1` 21px display); `.top-actions` (quiet button, case `<select>`, "Command ⌘K"); `.authority-strip` (36px, mono 11px, four labelled facts and a warning status); `main.content` (max 1600px, 24px/28px padding; `.report-content` 1800px); the palette `<dialog>` (combobox + listbox with group labels) and the `dialog.context-drawer`.
- States: `caos/frontend/src/components/states.tsx`: `StateBlock` (callout / action shapes; neutral, warning, critical tones), `StateNote`, `StateSkeleton`, `EmptyBlock`, `EmptyPanel`, `LoadState`, `Unavailable` ("Not available in this deployment."), `MutationReceipt` (✓ line), `IdentityValue` (12…4 compact identity).
- Panels and controls: `.panel` (10px radius, panel shadow), `.panel-header` (46px min, 13px/600 title, `.panel-meta` 10px), `.panel-body` 12px, `.button` / `.button.primary` / `.button.small` / `.button.quiet`, `.status` chips with glyphs, `.state-facts` definition lists, `.table-wrap` focusable scroll regions, `.dag` route tiles, `.approval-panel`, `.callout`, `.context-strip`.
- Report paper: `caos/frontend/src/components/report/DeliverableDocument.tsx` and the `.report-*` / paper rules in `globals.css`.

## 9. What the canvas decides and what it does not

The canvas binds layout, hierarchy, states and copy for the chosen direction. It does not bind tokens (they stay in `globals.css`), does not change the wire contract, and does not decide authorization. A canvas is a proposal until the user records approval in the design report.
