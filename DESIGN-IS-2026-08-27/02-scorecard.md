# 02 — Scorecard

Scored by the orchestrator only, against the per-principle anchors, on the evidence in `01-evidence.md`. Rules applied: worst instance (not mean), tie-breaker to the lower score, 0–3 integers, equal weights.

1. Good design is **innovative** — Score: **2/3**
   Evidence: E1 — custody-chain-as-UI (SHA identities, worded authority states, digest-bound approval copy, evidence-bound block stamps) is a pattern no mainstream analyst tool ships, delivered with restraint.
   Justification: the pattern is real and visible on shipped surfaces (a clear refresh-plus of the analyst-terminal form), but its fullest expressions (paper deliverable, evidence chips, plan approval) are unreachable on this deployment, so it does not yet earn the "ships it" bar of a 3; it is far more than minor variation, so not a 1.

2. Good design makes a product **useful** — Score: **0/3**
   Evidence: E2 — module output is unopenable by any input modality (inert DAG divs, Workspace.tsx:698), no reachable screen renders analytical content, Report Studio (the Publish endpoint of the task) 404s on every visit, Model Builder crashes on load, and acceptance is demanded before inspection is possible.
   Justification: the primary task — inspect the analysis and carry it to a committee-ready deliverable — is not directly supported on the audited surfaces, which is the 0 anchor verbatim; a 1 ("unnecessary detours") would imply the task is completable, and it is not.

3. Good design is **aesthetic** — Score: **1/3**
   Evidence: E3 — one disciplined system (surface ladder, hairlines, AAA contrast, zero decoration) but three live orphan-style defects (unstyled 14.04px heading, browser-default centered caption, 0px-gap Accept button) plus two divergent error treatments.
   Justification: ≥3 concrete inconsistencies on the audited surface lands the 1 anchor by count despite the strength of the underlying system; it is nowhere near "no visible system," and the tie-breaker forbids rounding up to 2.

4. Good design makes a product **understandable** — Score: **1/3**
   Evidence: E4 — engine vocabulary throughout analyst chrome (CP-MODEL ×6, "worker…Python", "envelope", digest/fingerprint/payload, raw PLAN_APPROVAL_REQUIRED and ANALYST_JUDGMENT enums, JSON block locators), dual nav-vs-page naming for every workflow, and a split product name.
   Justification: well beyond "1 control needs a tooltip" — multiple controls and labels are unclear and jargon is pervasive (the 1 anchor); not a 0 because the primary actions themselves ("Compile and run", "Accept analytical snapshot") are identifiable without help.

5. Good design is **unobtrusive** — Score: **2/3**
   Evidence: E5 — zero idle motion, zero notifications, flat quiet chrome; but the full run console is replicated on three surfaces and the rail double-highlights two destinations at once.
   Justification: chrome is visible but genuinely quiet (the 2 anchor); it does not fully recede into "content is the figure" because on several screens the chrome is nearly all there is (60–75% empty viewports, digest walls as content), and duplicated affordances pull attention.

6. Good design is **honest** — Score: **1/3**
   Evidence: E6 — zero marketing inflation and zero dark patterns, but four permanent nav destinations promise surfaces the server cannot serve, an unconditional "LIVE" badge, a hardcoded "QA unavailable" label, a "Pathway fit" chip contradicting on-screen facts, Retry buttons that can never succeed, and one silently-404ing download link.
   Justification: the 3 anchor ("every claim, badge, and label maps 1:1 to actual behavior") is failed many times over, which is more than the single minor inflation a 2 allows; it is not a 0 because nothing is a deceptive flow in the dark-pattern sense — these are broken promises, not manipulations.

7. Good design is **long-lasting** — Score: **3/3**
   Evidence: E7 — no dated trend markers found by any agent: no gradients, glow, glassmorphism, spot art, or trend typography; a desk-terminal genre and print-classical paper counterpoint that have been stable for decades.
   Justification: zero markers is the 3 anchor; nothing observed would date this to a specific year in three years' time.

8. Good design is **thorough down to the last detail** — Score: **1/3**
   Evidence: E8 — empty/focus/paused/unavailable states are genuinely considered and the axe harness is green, but error is rough (raw TypeError as user copy, two divergent treatments), success is rough (silent acceptance via an OS confirm that the embedded browser suppressed outright), and disabled never manifests live (RV's dead filter grid renders enabled).
   Justification: three states rough or unrealized lands the 2–3-missing band (the 1 anchor); the strong a11y floor keeps it off 0, and the tie-breaker rules out crediting the intent behind the 50 unexercised `disabled=` sites as a 2.

9. Good design is **environmentally friendly** — Score: **1/3**
   Evidence: E9 — 623 KB of JS on the wire, uncompressed, with 127 KB of never-fetched build weight; offset by exemplary attention economics (0 idle animation, 0 polling, 0 load-time notifications, reduced-motion honored) and a HIGH cognitive-load result (6/8 checklist failures).
   Justification: bytes sit in the 500 KB–2 MB band of the 1 anchor and cognitive load — part of this principle's software gloss — is high; motion being fully gated argues for 2, and the tie-breaker resolves the split downward.

10. Good design is **as little design as possible** — Score: **1/3**
    Evidence: E10 — ornament is essentially zero, yet five-plus removable elements ship: the run console duplicated onto two extra surfaces, permanent nav to dead destinations, a fully enabled filter grid on an empty universe, a triplicated link, and 112 KB of dead script on every page.
    Justification: 3–5 removable elements is the 1 anchor; the restraint in ornament is real but the principle scores what could be removed without breaking the task, and here that list is long — while far from a page "dominated by decoration" (0).

## Total: **13/30**
