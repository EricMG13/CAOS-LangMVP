# Task 2 report — Restore hierarchy and repair shell polish

## Summary

- Reduced the frontend label taxonomy to the intended roles: uppercase tracked `nav-label`, compact uppercase table headers, sentence-case `panel-meta`, and `meta-label` data captions.
- Removed production `.eyebrow` markup/selectors, including the stacked Model Builder section labels, while retaining the useful “forward periods only” meaning in helper copy.
- Removed the redundant shell `Reading:` element and the unused `DestinationMeta.reading` field.
- Rendered the command shortcut as `<kbd aria-hidden="true">⌘K</kbd>` and shared the command-palette key styling with a non-colliding gap.
- Preserved report outline numbering, exact raw identifiers, conditional tool navigation, drawer/palette focus behavior, and Model Builder export-polling WIP of uncertain origin that appeared after the task's clean starting check.
- The initial implementation inherited Task 1's full-border DAG status hues; the review correction below makes the container border neutral and moves state semantics to the existing shape-coded visible status treatment.

## Files committed

- `caos/frontend/app/globals.css`
- `caos/frontend/app/not-found.tsx`
- `caos/frontend/src/components/WorkbenchShell.tsx`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/model/ModelBuilder.tsx`
- `caos/frontend/src/components/model/ModelBuilder.test.ts`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/lib/workbench.ts`
- `caos/frontend/src/lib/workbench.test.ts`

## Tests and verification

- TDD red: `node --test src/lib/workbench.test.ts src/components/model/ModelBuilder.test.ts` — expected 2 failures before implementation (obsolete `reading` data/shell copy and Model Builder eyebrows), 20 passed.
- Focused green: same command — 22/22 passed immediately after implementation; final rerun with concurrent WIP tests present — 24/24 passed.
- `npm run lint -- --max-warnings=0` — passed.
- `./node_modules/.bin/tsc --noEmit -p .` — passed using the repository-local TypeScript binary.
- `npm run test:unit` — 84/84 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- `npm run build` — passed with Next.js 16.3.3 static production output.
- `git diff --check` and staged-diff check — passed.
- Source checks — no production `.eyebrow`, `.reading-label`, `Reading:`, or `meta.reading` use; report `01`, `02`, … numbering remains; conditional `activeWorkflow.tools?.length` rendering remains; live DAG uses a neutral full border plus shape-coded visible status and no DAG `border-left` rule.
- Focused Playwright probe — passed real `<kbd>` rendering and spacing, Meta+K open, search, ArrowDown, ArrowUp, Escape, focus restoration, and Enter navigation to Model Builder. The probe then timed out on an overly strict case-id assertion because the live shell normalized to a newly created case, so it did not complete the requested 1440×1000 and 720×900 screenshots.
- Full `npm run test:workbench` — manually stopped after a silent, bounded wait. Investigation showed the process defaulted to port 8000 while that local process served backend routes only (`/cases/` returned `{"detail":"Not Found"}`). The final combined-app verification task should rerun this suite against a correctly assembled server.
- `rewrite-tournament` — skipped under its trivial-edit exemption: Task 2 changes are declarative markup/CSS/data-field deletions and do not alter an algorithmic function or branch structure.
- `confidence-review` — completed. Ranked risks checked: dead taxonomy selectors/callers, shortcut semantics/focus/spacing, report numbering/raw IDs/conditional tools, Model Builder primary-action exclusivity, and DAG stripe state. No confirmed Task 2 defect remained.

## Commit

- Task 2 implementation: `1d7e80068f1a0954ad370fac18d6896ad7a09989` (`feat(frontend): restore terminal label hierarchy`)
- Task 2 review correction: `02cf9bcf37a6c94493d315449b853878a1f11f9c` (`fix(frontend): complete label and DAG semantics`)
- Task 2 second review correction: `2bbbccbe746dff8daa635bda01944c45daab1b6f` (`fix(frontend): align captions and DAG states`)

## Review correction

- Palette group headers now use `nav-label` in markup; `.palette-group-label` retains only sticky layout/surface rules.
- QA drawer definition terms and the Report Studio model-authority caption now use `meta-label`; their bespoke uppercase/tracked selectors were removed.
- DAG node containers now retain a neutral border. Exact raw node status text remains visible and uses the shared shape-coded `status` roles.
- TDD red: `node --test src/lib/workbench.test.ts` — expected 2 failures and 10 passes before the correction.
- Focused green: the same command — 12/12 passed.
- `npm run lint -- --max-warnings=0` — passed.
- `./node_modules/.bin/tsc --noEmit -p .` — passed.
- `npm run test:unit` — 88/88 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- `git diff --check` and correction staged-diff checks — passed.
- `rewrite-tournament` — skipped under the trivial/declarative-edit exemption.
- `confidence-review` — completed against taxonomy inheritance, caption markup coverage, conditional palette groups, all served node states, neutral DAG borders, visible raw status text, and external WIP isolation. No confirmed correction defect remained.

## Second review correction

- Leveraged-loan authority and accepted-analysis provenance definition terms now use `meta-label`; their bespoke uppercase/tracked `dt` selectors were removed.
- The source assertion now rejects any stylesheet rule that adds tracking or uppercase transformation to a `dt`, covering future caption duplicates rather than only named selectors.
- A small pure `nodeStatusTone` helper explicitly covers the server `NodeStatus` contract: `pending`/`ready` → idle, `running` → running, `blocked`/`cancelled` → warning, `failed` → critical/error, and `succeeded` → success. Unknown future states fail safe to warning.
- Running status now has the live accent glyph/tone, while every DAG status retains exact visible raw text.
- TDD red: `node --test src/lib/workbench.test.ts` — expected 2 failures and 10 passes before the correction.
- Focused green: the same command — 12/12 passed.
- `npm run lint -- --max-warnings=0` — passed.
- `./node_modules/.bin/tsc --noEmit -p .` — passed.
- `npm run test:unit` — 88/88 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- `git diff --check` and correction staged-diff checks — passed.
- `rewrite-tournament` — skipped because the helper is a straightforward contract-to-tone mapping below the skill's trivial-function threshold.
- `confidence-review` — completed against all seven server states, unknown-state fallback, raw visible labels, running styling, global `dt` typography duplication, and preservation of starting checkpoint `5b425a2c3024f453edf7caab8c7a4d8235d20b17`. No confirmed defect remained.

## Remaining risks

- Visual inspection at 1440×1000 and 720×900 remains unverified because the focused live fixture changed the selected case before the viewport stage. Source/unit/build verification covers the hierarchy, but the final combined-app browser task should capture both viewports.
- The full browser journey remains unverified in this task because the available port-8000 process was backend-only. This is an environment assembly issue, not a captured application assertion failure.
- The original Task 2 worktree was clean at `9874a68c8b51473706bce1ed73a3e73fc022474a`. The separately reviewed Model Builder export-polling work is now preserved in checkpoint `5b425a2c3024f453edf7caab8c7a4d8235d20b17`; the second review correction started from that commit and did not alter it.
