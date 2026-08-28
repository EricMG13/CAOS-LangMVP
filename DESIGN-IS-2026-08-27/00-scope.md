# 00 — Scope

Audit date: 2026-08-27
Auditor: design-is (Dieter Rams ten-principle audit) + /impeccable critique (dual-agent), run together; exported as separate documents.

## What is being audited

All user-facing surfaces of the CAOS workbench frontend (`caos/frontend`), inspected as source **and** live against the combined app (`python caos/server/dev.py` on `127.0.0.1:8000`, serving the static export from `caos/frontend/out` with a seeded SQLite dev store).

Surfaces (from `src/lib/workbench.ts:53-58` workflow → destination map):

| Workflow | Destinations | Route |
|---|---|---|
| Overview | Cases, Command Center | `/cases/`, `/command-center/` |
| Sources | Sources | `/sources/` |
| Analyse | Run Console, Deep-Dive | `/run-console/`, `/deep-dive/` |
| Compare | RV Screener | `/rv-screener/` |
| Model | Model Builder | `/model-builder/` |
| Publish | Report Studio | `/report-studio/` |

Plus the shared chrome: `WorkbenchShell.tsx` (nav, palette, case switcher), `app/not-found.tsx`, `app/layout.tsx`, `app/globals.css` (454 lines of tokens/utility CSS), and the components under `src/components/` (`Workspace.tsx` 941 LOC, `ModelBuilder.tsx` 723 LOC, `ReportStudio.tsx` 442 LOC, `DeliverableDocument.tsx`, `EvidenceChip.tsx`, `FiledProof.tsx`). ~5,167 LOC total frontend.

## Primary user and task

Buy-side leveraged-finance credit analyst (per `PRODUCT.md`). Primary task: run a pathway against pinned evidence, inspect the module outputs with citations, and carry the result to a committee-ready deliverable — inspect dense credit information quickly, trace every material number to evidence, defend the view under scrutiny.

Secondary: PM/CIO scanning posture; Head of Research overseeing governance.

## Constraints

- Visual language is committed: dark institutional terminal, semantic color only, motion only for live state (`DESIGN.md`, `.impeccable.md`, PRODUCT.md anti-references). This is a REFINE-vs-REDESIGN constraint, not an open brief.
- Stack: Next.js static export (trailing slashes), FastAPI server, strict wire models. No client routing tricks; hrefs keep trailing slash.
- Accessibility floor: WCAG 2.1 AA (PRODUCT.md); `npm run a11y` is the pinned check.
- Mode (impeccable): **Operate** on every audited surface.

## Known-degraded context (scored as shipped, per "score what is")

`CLAUDE.md` "Known gaps" records that the ported frontend calls routes this server does not serve (Command Center lens, Admin Studio, deliverables workspace reads, model scenarios/sensitivities/worksheet, deep-research plan approval) and that a paused run has no resume control in the UI. Design is what ships: those surfaces are audited in the degraded state the user actually sees.

## Input materials

- Source tree at commit `45e9063` (branch `claude/design-critique-export-d9156d`).
- Live instance on `:8000`, seeded: one case, uploaded text sources, one deterministic `EARNINGS_UPDATE` @ `screen` run driven to a terminal state (no API key required).
- `PRODUCT.md`, `DESIGN.md`, `.impeccable.md`, `CONTEXT.md` vocabulary.

## Out of scope

Server-side API design, run-engine semantics, test suite quality, CI. Copy inside vendored methodology bundle. Non-UI documentation.
