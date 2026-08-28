# 03 — Verdict

## REDESIGN

**Verdict sentence:** The CAOS workbench scores 13/30 with a 0 on the load-bearing principle #2 (useful) — the visual system is committed, durable, and worth keeping wholesale, but the product's information architecture must be redesigned from its purpose, because the shipped surfaces cannot deliver the primary task (no analysis output is readable anywhere, the Publish surface is dead, and acceptance is demanded blind) and the navigation promises capabilities the server does not have.

Both triggers of the Phase 3 rule fire independently: total 13 < 20, and principle #2 scored 0. The verdict follows mechanically from `02-scorecard.md`; no re-scoring.

**Scope guard (anti-pattern check):** this is not "redesign because one screen is ugly" — aesthetics and longevity are the *strongest* dimensions (#7 = 3, system discipline confirmed by every agent). Nor is it softened to REFINE because ~5,200 LOC already exist — sunk cost is not a design principle. What must be redesigned is the **analysis-payoff architecture and the truthfulness of the surface map**: what an analyst sees after a run succeeds, in what order inspection and acceptance happen, and which destinations are presented as live. The token system, panel idiom, and accessibility plumbing are preserved as-is.

## Highest-leverage moves

1. **(#2 useful — E2)** Build the artifact reader as the center of the product: module outputs opened from the DAG tiles and the artifact register (render narrative, sections, and `EvidenceChip` citations — component and CSS already exist), available *before* acceptance; move "Accept analytical snapshot" to the end of the reading flow so acceptance binds something the analyst has seen. Evidence: inert `div.dag-node` at [Workspace.tsx:698](../caos/frontend/src/components/Workspace.tsx:698); Accessibility §2.3 "no control exists for any modality"; Assessment A P0.

2. **(#6 honest — E6)** Make the surface map truthful: capability-gate every destination against what the deployment actually serves — an honest "Not available in this deployment" state (DESIGN.md already specifies `unavailable`) for Report Studio, Admin Studio, the sensitivities tab, and rebase/export; split the `Promise.all` so Command Center's served "What changed" panel survives the unserved lens ([Workspace.tsx:932](../caos/frontend/src/components/Workspace.tsx:932)); make the "LIVE" badge conditional; fix the lying "Pathway fit" chip and hardcoded "QA unavailable" label; surface the served `resume` capability on paused runs.

3. **(#4 understandable — E4)** One vocabulary: human module names beside CP-* ids (the registry has them), humanize every enum shown to users (`PLAN_APPROVAL_REQUIRED`, `ANALYST_JUDGMENT`), purge "worker/Python/envelope/payload/digest-as-label" from chrome, collapse the nav-label/page-title double naming, and pick one product name ("Credit Operating System" vs "Credit Agent OS").

4. **(#8 thorough — E8)** One error-and-ceremony idiom: a single styled refusal/error component (typed message + next step; never raw `caught.message`, never a TypeError as analyst copy), a styled digest-bound acceptance dialog replacing `window.confirm` (which the embedded browser silently suppressed), an acknowledged post-accept state, and real rendered `disabled` states (starting with RV's dead filter grid).

5. **(#9/#10 — E9, E10)** Cut the dead weight: serve the export compressed, drop the 112 KB `nomodule` fallback and the unreferenced chunk, delete `FiledProof`/`filedMarkdown` (82 dead lines), and collapse the run console to one home instead of three.
