# 04 — /make-plan handoff

Copy-paste the fenced prompt below into a fresh session. It is self-contained: the verdict and moves are quoted in full because the next session will not see this audit.

````
/make-plan Redesign the CAOS workbench's analysis-payoff architecture and surface map (frontend: caos/frontend). Current design failed a Dieter Rams audit at 13/30 with critical gaps in principles #2 (useful — scored 0), #4 (understandable — 1), #6 (honest — 1), #8 (thorough — 1).

Verdict paragraph (quoted from 03-verdict.md):
> The CAOS workbench scores 13/30 with a 0 on the load-bearing principle #2 (useful) — the visual system is committed, durable, and worth keeping wholesale, but the product's information architecture must be redesigned from its purpose, because the shipped surfaces cannot deliver the primary task (no analysis output is readable anywhere, the Publish surface is dead, and acceptance is demanded blind) and the navigation promises capabilities the server does not have.

Why redesign and not refine: principle #2 (useful) scored 0 — with a succeeded run on real earnings text, no reachable screen renders any analytical content, Report Studio 404s on every visit, Model Builder crashes on load against this server, and "Accept analytical snapshot" is offered before inspection is possible — and the total (13/30) is also below the 20-point refine threshold.

Preserve from current design (non-negotiable):
- The complete visual token system and dark-terminal world: surface ladder / semantic colors / typography roles in caos/frontend/app/globals.css:2-33 and DESIGN.md; zero-ornament discipline (0 gradients, 0 @keyframes, 2 shadows).
- The accessibility plumbing, verified green twice by the shipped axe harness (43 route×viewport combos, 0 violations): skip link + universal 2px :focus-visible ring (globals.css:38,136-137), dialog focus capture/trap/restore (WorkbenchShell.tsx:97-116), combobox command palette with aria-activedescendant (WorkbenchShell.tsx:283-357), roving-tabindex tab strips (ModelBuilder.tsx:320-327), aria-sort + colgroup + sr-only captions in tables (Workspace.tsx:922), reduced-motion kill with its explanatory comment (globals.css:419-422), 44px coarse-pointer targets (globals.css:416-418).
- The authority spine as structure: the four worded authority-strip states (WorkbenchShell.tsx:154-166,258-262), immutable source intake with SHA identity (Workspace.tsx:618,675 area), typed refusal callouts ("Material exception: upload governed source material before execution.", Workspace.tsx:701), the RV screener's desk-genuine table (unit-labeled columns, signed deltas, workbook locators, "SOURCE DATA · UNANALYZED", Workspace.tsx:824-829,920-922), and the coded deliverable-paper language ("Evidence-bound"/"Analyst judgment" stamps, DeliverableDocument.tsx:105).
- CONTEXT.md's governed vocabulary as the only product language.

Discard (structural patterns that caused the failures):
- The digest-only payoff: inert, unopenable DAG tiles (div.dag-node, Workspace.tsx:698) and artifact tables with no reader. Caused the 0 on principle #2.
- Accept-before-inspect: window.confirm as the acceptance ceremony (Workspace.tsx:504) with no bound content shown, silent success, and the Accept button persisting enabled afterwards. Caused failures on #2, #5, #8. (The embedded-browser session also showed native confirm can be suppressed entirely.)
- Port-ahead-of-server surfaces presented as live: permanent nav to Report Studio (read route unserved — 404 card every visit, ReportStudio.tsx:195,401), Command Center's Promise.all coupling that kills the served "What changed" panel with the unserved lens (Workspace.tsx:932), Admin Studio with no backing routes, Model Builder's readiness dereference crash (inventory?.readiness.status, ModelBuilder.tsx:288-289 and :255,:331,:476-477,:704), sensitivities/rebase/export controls calling unregistered routes, and a bare download link that 404s with no in-app message. Caused failures on #6 and #2.
- Engine vocabulary in analyst chrome: CP-MODEL ×6 (ModelBuilder.tsx:82,332,654,669,702,714), "worker…Python" (ModelBuilder.tsx:332), "envelope" (DeliverableDocument.tsx:80), digest/fingerprint/payload as bare labels, raw PLAN_APPROVAL_REQUIRED heading (Workspace.tsx:758) and ANALYST_JUDGMENT radio (ReportStudio.tsx:430), b00004 · {"line":4} locators (Workspace.tsx:674), nav-label/page-title double naming (workbench.ts:53-58), split product name (layout.tsx:11 vs WorkbenchShell.tsx:228). Caused the 1 on #4.
- The tripled run console (the full form+DAG+accept replicated on Cases, Run Console, and Deep-Dive) and three simultaneous .button.primary actions on /cases/ (Workspace.tsx:616-619,688,700). Caused failures on #5, #9 (cognitive load), #10.

Top 5 moves from the audit (verbatim from 03-verdict.md):
1. (#2 useful) Build the artifact reader as the center of the product: module outputs opened from the DAG tiles and the artifact register (render narrative, sections, and EvidenceChip citations — component and CSS already exist), available BEFORE acceptance; move "Accept analytical snapshot" to the end of the reading flow so acceptance binds something the analyst has seen. Evidence: Workspace.tsx:698.
2. (#6 honest) Make the surface map truthful: capability-gate every destination against what the deployment actually serves — an honest "Not available in this deployment" state for Report Studio, Admin Studio, the sensitivities tab, and rebase/export; split the Promise.all at Workspace.tsx:932; conditional "LIVE" badge; fix the lying "Pathway fit" chip and hardcoded "QA unavailable" aria-label (WorkbenchShell.tsx:271); surface the served POST /api/runs/{id}/resume on paused runs.
3. (#4 understandable) One vocabulary: human module names beside CP-* ids, humanize every user-visible enum, purge worker/Python/envelope/payload/digest-as-label from chrome, collapse the double naming, pick one product name.
4. (#8 thorough) One error-and-ceremony idiom: a single styled refusal/error component (typed message + next step; never raw caught.message or a TypeError as analyst copy), a styled digest-bound acceptance dialog replacing window.confirm, an acknowledged post-accept state, real rendered disabled states (starting with RV's dead filter grid on the empty universe).
5. (#9/#10) Cut dead weight: serve the export compressed (uvicorn currently sends 623 KB of JS with no content-encoding), drop the 112 KB nomodule fallback and the unreferenced 14 KB chunk, delete FiledProof.tsx + filedMarkdown.ts (82 dead lines, zero importers), collapse the run console to one home.

Redesign principles in priority order:
1. #2 Useful — success means: from a succeeded run, the analyst reads the actual analysis (narrative, numbers, citations) in ≤2 clicks, and cannot be asked to accept authority they have not been shown.
2. #6 Honest — success means: every visible nav entry, badge, and button maps 1:1 to something this deployment can actually do; degraded capability is stated, never simulated.
3. #4 Understandable — success means: an analyst can name every control in CONTEXT.md vocabulary; no engine term appears in chrome; one name per destination and per product.

Deliverables for the plan:
- New information architecture for the analysis payoff (run → inspect → accept → publish), not derived from the current digest-table structure; include the capability-gating map (which surfaces render live vs. unavailable per served route).
- New primary flow (low-fi, labeled), compared side-by-side with the current flow (run → green DAG → blind confirm → digests).
- States checklist per surface: empty, loading, error (one idiom), success (acknowledged), focus, disabled — with the refusal/ceremony components named.
- Migration path: which existing components carry over unchanged (WorkbenchShell chrome, palette, tables, EvidenceChip, panel CSS) and which are replaced (window.confirm ceremony, LoadState triplication, inert DAG).
- Cutover criteria: the old accept-before-inspect flow and dead-route navs are retired when the artifact reader and capability gates ship; npm run a11y stays green and the workspace-authority unit tests stay the behavioral gate (per CLAUDE.md, Workspace.tsx changes go through them).

Constraints: dark institutional terminal is committed (DESIGN.md, .impeccable.md — inherit, don't reinvent); static export (output: "export", trailing slashes — hrefs keep the trailing slash); WCAG 2.1 AA floor with the shipped axe harness as the check; Workspace.tsx is deliberately one file arbitrated by lib/workspaceAuthority.ts — behavior changes go through the authority unit tests and the workbench smoke; server routes are out of scope for the frontend plan, but the plan must degrade honestly wherever a route is absent (CLAUDE.md "Known gaps" is the authoritative list).

Anti-patterns to guard against (specific to REDESIGN):
- Porting the old digest-wall structure under new styling — the payoff IA must start from "what does the analyst read," not from what the store returns.
- Keeping both acceptance flows behind a flag indefinitely.
- Redesigning the visual language — it is on the Preserve list and scored as the product's strongest dimension.
- Treating the Preserve list as optional — the token system, a11y plumbing, authority spine, and CONTEXT.md vocabulary must survive verbatim.
````
