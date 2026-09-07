# Analyst Workbench Capabilities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not start implementation or dispatch agents merely because this plan exists.

**Goal:** Carry forward legacy's complete cash-flow modelling experience, developer-designed module-driven reports, insightful live pipeline, and analytical visualizations on the current CAOS-LangMVP application.

**Architecture:** Keep the current execution engine, module steps, accepted-artifact authority, Model Build calculation boundary, revisions and publication controls. Add explicit, versioned presentation mappings from validated module tables to analytical views and report sections; share those mappings and chart components between Analysis and Report. Make the complete existing model and actual execution graph visible through focused changes to their current surfaces.

**Tech Stack:** Existing Python/FastAPI/Pydantic services, React 19/Next.js 16 static export/TypeScript frontend, CSS/SVG, pytest, Node test runner and Playwright/axe. Use AntV G2 v5 for analytical charts, guided by the linked AntVis skills; use native SVG/CSS for the small staged run graph. Preserve the existing pango/pypdf/openpyxl publication stack.

**Status:** Tasks 0–9 were implemented and independently approved in their
sequential implementer/reviewer cycles. Task 10 owner qualification completed on
2026-09-07 with durable evidence in
`.superpowers/sdd/analyst-workbench-task-10-report.md`; its fresh independent
task review and final whole-branch Astra review remain separate. This status does
not claim live-provider qualification, merge, deployment or release.

## Global Constraints

- “legacy is inferior to current” — current CAOS-LangMVP remains the foundation.
- “complete cash flow model” — evaluate the full operating, investing, financing and closing-cash chain, not only FCF or summary metrics.
- “IC memo not required, report input derived directly from modules and report design was created by the developer” — developer-owned layouts, module-owned analytical content, optional analyst commentary.
- “live run pipeline (legacy visually better and insightful)” — visualize actual execution state and dependencies.
- “given module steps are unchanged there will always be certain table and data to produce visulisations from” — bind known outputs to known views; do not add an agent that invents charts at runtime.
- Preserve all ten invariants in `CLAUDE.md`, including source pinning, byte-verified methodology, strict canonical module envelopes, finite calculations, static route edges and digest-bound human decisions.
- Keep the six existing pathways and the current route names: `/model/`, `/report/`, `/run/`, `/analysis/`. No workflow engine or navigation redesign.
- Preserve `Workspace.tsx` as the workspace-authority state machine. Extract presentational children only; do not duplicate case/run/snapshot state.
- Historical and calculated model values remain locked. Only `READY` Assumption Registry rows in forward periods are editable.
- Generated report values are computed or selected server-side from validated authority. Browser requests never become a source of analytical facts.
- Missing, unavailable, conflicting and zero values remain distinct. Never fabricate a trend, normalize incompatible units, sum overlapping periods, or infer security seniority.
- Existing Frozen and Filed Deliverables remain byte-identical. Template or renderer upgrades never silently rewrite saved history.
- An IC memo is not a prerequisite for report composition. This does not remove CP-6 from an existing execution route or remove applicable opinion Sign-Off, freeze or independent filing controls.
- Reuse the established dark workspace, light report paper, typography, evidence drawer and state components in `DESIGN.md` and `.impeccable.md`; meet WCAG 2.1 AA and reduced-motion requirements.
- Do not edit the vendored methodology for presentation work. If a model-coverage test proves a methodology defect, stop that slice and obtain a separately recorded methodology decision rather than hiding a formula change in a UI task.
- After writing or modifying code, run `confidence-review` before declaring the
  task done or committing: enumerate doubts, trace callers to root causes,
  adversarially verify suspicions and patch confirmed issues. Non-trivial
  production code also requires `rewrite-tournament` in no-argument post-edit
  mode. Documentation/config/test-only changes are tournament-exempt; preserve
  the repository's test framework.

---

## Baseline and relationship to existing work

Execution is pinned to remote-main commit
`31482a7912c9e58017c2784bf098a6868978cd01` in the already-created isolated
worktree `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex`
on branch `codex/analyst-workbench-capabilities`. Do not create another
worktree, reuse the original checkout's untracked environments, or copy
unrelated work to make line numbers match this plan. The verified Deploy V
methodology build at this baseline is
`237bf4bc56b616b1c679a32c3733a2d9baf580b113758329320478e0226bae9d`.

The durable execution ledger is
`.superpowers/sdd/analyst-workbench-progress.md`; task briefs and reports use
the `analyst-workbench-task-N-` prefix. Preserve all inherited enterprise
history. Use one fresh implementer for each Task 0–10, followed by a fresh
read-only spec and quality reviewer; execute tasks sequentially. Default
implementers are `gpt-5.6-sol` for Tasks 0–4, 6 and 10, and `gpt-6-astra` for
Tasks 5 and 7–9 plus the final whole-branch review, with reviewers matched to
risk.

Scoped local checkpoint commits are authorized after required checks. No push,
merge, PR, deployment, paid provider run, real-case mutation, automatic
acceptance/filing, credential copying or vendored-methodology edit is
authorized. Diagnose environment failures before calling them product
regressions.

The implemented `2026-08-31-legacy-builder-core-adaptation.md` is history, not an unbuilt backlog. Worksheet endpoints, semantic report sections, preview, exports, model revisions and the six pathway composers already exist. This plan closes the remaining capability gaps.

The legacy URLs are seeded reference views. They establish useful layout and interaction patterns, not live-calculation correctness. Current-side review findings were source/test verified; final browser qualification remains a task below.

### Four independently shippable workstreams

| Workstream | Tasks | Complete when |
|---|---|---|
| A. Complete Model experience | 1–3 | Full cash-flow coverage reconciles; the worksheet is navigable; lineage opens evidence; minimum cash is distinct from closing cash. |
| B. Module-driven Report | 7–9 | A designed report populates from modules without manually drafting each section or creating an IC memo; selected model effects reach the report and exports. |
| C. Live Run insight | 4 | The displayed graph equals the served dependencies and explains current progress, blockers and outputs. |
| D. Visual Analysis | 5–6 | Accepted module outputs drive predictable, source-linked visualizations and tables, including honest missing-data states. |

Tasks 1 and 4 are logically independent, but the approved workflow implements
all tasks sequentially. Task 5 supplies the shared data projection for Tasks 6
and 7. Task 6 supplies the chart component reused by Tasks 7 and 9. Task 8 must
land before the incremental-report acceptance gate. Task 10 integrates all
four workstreams.

## File ownership map

Paths below are repository-relative so the plan works in the requested isolated worktree. Existing files are retained unless explicitly marked Create.

| Area | Files | Responsibility |
|---|---|---|
| Decisions and vocabulary | `docs/DECISIONS.md`, `CONTEXT.md`, `DESIGN.md`, `SPEC_RECONCILIATION.md` | Record module-populated reports, optional IC presentation, template compatibility and acceptance tests. |
| Model | `caos/server/caos/models/engine.py`, `caos/server/caos/models/service.py`, `caos/frontend/src/components/model/ModelBuilder.tsx`, `ModelBuilder.module.css`, `modelBuilderState.ts` | Existing calculator/workbook boundary, structured lineage, horizon sensitivity and worksheet interaction. |
| Run | `caos/frontend/src/lib/api.ts`, `caos/frontend/src/components/Workspace.tsx`; Create `caos/frontend/src/components/run/RunGraph.tsx`, `RunGraph.module.css`, `runGraph.ts`, `runGraph.test.ts` | Served graph projection, layout, selection and inline node inspection. |
| Module presentation | Create `caos/server/caos/artifacts/presentation.py`, `caos/tests/spec/test_module_presentation_spec.py`; modify `caos/server/caos/contracts.py`, `responses.py`, `api/__init__.py` | Bounded, versioned views derived from validated artifacts, outside the canonical module envelope. |
| Shared charts | Create `caos/frontend/src/components/charts/ChartExhibit.tsx`, `chartRecipe.ts`, `chartRecipe.test.ts`; modify `caos/frontend/package.json`, `package-lock.json` | Controlled G2 rendering, accessible table, unit/source labels and lifecycle cleanup. |
| Analysis | Create `caos/frontend/src/components/analysis/ModulePresentation.tsx`; modify `Workspace.tsx`, `lib/api.ts`, `app/globals.css` | Module-specific analytical reading surface under the shell's accepted snapshot. |
| Report | `caos/server/caos/deliverables/service.py`, `document.py`; `caos/frontend/src/components/report/ReportStudio.tsx`, `DeliverableDocument.tsx`, `documentTypes.ts` | Versioned developer layouts, generated sections and optional analyst overlays. |
| Publication | `caos/server/caos/publishing/document.py`, `renderers.py`, `markdown.py`, `caos/server/caos/audit/verify_package.py`; Create `caos/server/caos/publishing/charts.py` | Frozen chart/data rendering and independent verification. |
| Integration | Existing model/deliverable/publication/HTTP spec tests; `caos/frontend/scripts/workbench-smoke.mjs`, `a11y-axe.mjs` | Full workflow and authority regression checks. |

No new database, background service, workflow framework, chart editor, arbitrary layout DSL or runtime chart-generation agent is required. Keep the new presentation mapping as one small module until real size justifies splitting it.

## Task 0: Record the new product contract and pin the baseline

**Files:** Modify `docs/DECISIONS.md`, `CONTEXT.md`,
`SPEC_RECONCILIATION.md` and this implementation plan; create
`docs/ANALYST_VIEW_COVERAGE.md` as the implementation's coverage ledger.

**Interfaces:** The ledger maps `(methodology build, module ID, table/section ID, required columns)` to an Analysis view, a Report section, or an explicit table-only presentation. It is documentation and test input, not a second execution registry.

- [x] Read the existing engineering/design contracts and relevant installed Next.js documentation. Record the execution worktree's branch, commit and bundle build ID.
- [x] Provision that worktree's test dependencies using the repository's declared runtimes. An untracked `.venv314` or `node_modules` in the original checkout will not appear automatically in a new worktree. Create the Python 3.14 environment with `python3.14 -m venv caos/server/.venv314`, install the hashed development lock with `caos/server/.venv314/bin/python -m pip install --require-hashes -r caos/server/requirements-dev.txt`, and run `npm ci` from `caos/frontend`. Use the Node version declared by the repository's CI configuration. Do not copy credentials or connect these checks to the original application's data directory.
- [x] Run the clean focused baseline before application changes: the existing
  model specification on Python 3.14 and the existing frontend unit suite on
  Node 24. Diagnose dependency/environment failures before reporting a product
  regression.
- [x] Record the report decision: default Full Credit output title is **Credit Report**; existing six pathway identities stay unchanged; IC-specific content may be included when present but is not a separate prerequisite.
- [x] Record template v2 as module-populated sections plus optional analyst commentary. Preserve v1 saved/frozen content through explicit version dispatch.
- [x] Populate the coverage ledger from the current registered modules and their pinned references. Full Credit currently includes CP-PARSE, CP-0, CP-1, CP-1A, CP-1B, CP-1D, CP-1C, CP-2, CP-2A, CP-2G, CP-2E, CP-2H, CP-3, CP-4, CP-4C, CP-5 and CP-6; Deep Research adds CP-DR. Use actual current identities, not legacy aliases.
- [x] Include `CP-L10` and its exact pinned nested profile tables because it is
  active on SCREEN routes even though it is absent from the FULL route list.
- [x] Keep all required analytical tables available. Use narrative, evidence matrices and status registers for qualitative modules; a decorative chart is not a coverage requirement.

Baseline commands, from the execution worktree:

```bash
git status --short
git branch --show-current
git rev-parse HEAD
PYTHONPATH=caos/server caos/server/.venv314/bin/python -c 'from caos.engine.graphs import compiled_route; from caos.contracts import PATHWAYS; print({p: list(compiled_route(p, "full").nodes) for p in PATHWAYS})'
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py -q
(cd caos/frontend && npm run test:unit)
```

**Gate:** Every requested capability maps to a task and every active module maps to a view policy. No method, route or governance invariant is removed by the vocabulary update.

## Task 1: Prove full cash-flow coverage end to end

**Files:** Test `caos/tests/spec/test_model_builder_spec.py`, `test_source_complete_modelling_spec.py`; modify model wrappers only if the tests identify a real omission. Read, but do not change, the vendored `cp_model_v3/calculations.py` and `workbook.py`.

**Interfaces:** Reuse `CpModelBundle.calculate`, `serialize_workbook`, `_bundle`, `_forecast_paths`, `_built_case`, existing preview/Sign-Off/export helpers and worksheet semantic IDs. No new model API.

- [x] Add a coverage test to the existing model spec file:

```python
def test_cash_flow_rows_are_present_in_the_authoritative_worksheet():
    bundle = _bundle()
    model, calculations = bundle.calculate(_forecast_paths())
    result = bundle.serialize_workbook(model, calculations)
    tab = next(t for t in result["payload"]["tabs"] if t["title"] == "Model")
    observed = {cell["semantic_id"] for cell in tab["cells"]}
    required = {
        "cash_flow_adjusted_ebitda", "cash_interest_paid", "cash_lease_payments",
        "cash_taxes_paid", "ffo_other", "ffo", "working_capital_change",
        "cfo_calc", "cfo_reported", "cfo_variance",
        "capex_and_intangible_investment", "fcf", "acquisitions_disposals",
        "net_debt_issue_repay", "net_equity_issue_repay", "dividends_paid",
        "other_investing_financing", "ncf", "net_cash_change", "ncf_variance",
        "cash_and_equivalents",
    }
    assert required <= observed
    for column in calculations.columns:
        values = calculations.for_column(column.column_id).values
        assert values["fcf"] == values["cfo_calc"] + values["capex_and_intangible_investment"]
        assert values["ncf"] == sum(values[key] for key in (
            "fcf", "acquisitions_disposals", "net_debt_issue_repay",
            "net_equity_issue_repay", "dividends_paid", "other_investing_financing",
        ))
```

- [x] Apply the CFO/FCF/NCF identities to every applicable available period,
  including reported FY, quarterly, YTD, LTM and pro-forma columns. Historical
  closing cash is a sourced balance: do **not** assert prior cash + NCF for any
  reported column, and do not treat PF as a historical cash-flow reconciliation.
  Assert the cash roll-forward only for Base/Downside forecast columns, following
  each exact `rollforward_column_id`.
- [x] Preserve `RenderedWorkbook.formula_values`, which contains every rendered
  formula expectation. `formulas`/`CellExpectation` remains the narrower
  decision-output parity set. Extend the existing cross-sheet serializer
  regression rather than replacing either contract.
- [x] Extend the service journey: accepted artifacts → Model Build → changed forward assumption → preview → Signed-Off Revision → exact XLSX. Assert unchanged historical cells, matching selected-revision values and source/model identities throughout.
- [x] Run the coverage tests before changing production code. A passing coverage test means that calculation capability already exists; keep the test and make no unnecessary engine change.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_source_complete_modelling_spec.py -q
```

**Gate:** Every required row is present or has an explicit input/readiness refusal. A missing row or unreconciled cash movement blocks Model completion; summary metrics do not substitute for this gate.

## Task 2: Make the complete worksheet usable and source-linked

**Files:** Modify `models/service.py` at the model-authority boundary and
`models/engine.py` only where serialization requires it; modify
`frontend/src/lib/api.ts`, `components/model/ModelBuilder.tsx`,
`ModelBuilder.module.css`, `modelBuilderState.ts` and its test; extend
model/HTTP spec tests and the workbench smoke.

**Interfaces:** Keep raw `WorksheetCell.source_refs` unchanged for compatibility.
Add host-resolved `source_links: { source_id: string; block_id: string | null }[]`
at the model-service authority boundary after `_resolved_inputs`/snapshot
validation in `_compute_build_result` and preview, using pinned live sources from
`_live_snapshot_sources`. The workbook serializer cannot authorize source IDs.
Parse only the vendor's fixed reference serialization: exact pinned source IDs
permit source-only navigation and only an exact pinned `block_id` permits block
navigation. Free-form locators remain visible and source-only. Malformed,
ambiguous, unpinned or withdrawn refs have no clickable target. The UI continues
to consume the existing worksheet endpoint.

- [x] Add serializer tests for a known source/block, a source-only locator, multiple references and an unresolved reference. Unresolved text remains visible, but no invented clickable target is returned.
- [x] Add pure UI tests for selected period families and row groups using real worksheet cells; keep selection tied to `(tab ID, cell address)` rather than the filtered array index.
- [x] Add explicit controls for assumptions, sensitivity and history panels; allow the worksheet to dominate when those panels are closed. Add period-family selection, section navigation and collapsible business/debt groups derived from worksheet metadata.
- [x] Keep business row labels and period headers visible during scrolling. Expose each served semantic ID as `data-semantic-id` on its worksheet cell for stable interaction tests. Do not hide reconciliation rows merely because their value is zero. At 720px, use controlled worksheet scrolling and stacked controls, not page-wide overflow.
- [x] Connect valid lineage targets to the existing evidence drawer or `/sources/` deep links. Pass the actual opener element; Escape returns focus to it. Calculated cells show their formula and producing authority.
- [x] Pass an authority-safe evidence opener from `Workspace` into
  `ModelBuilder` with the actual opener element. Scope asynchronous evidence
  fetches by case and generation; do not duplicate workspace authority. Preserve
  `WorkbenchShell` stale-close protection and direct state clearing during
  full-source navigation.
- [x] Preserve serialized `queueCalculation`, skipped invalidated queued work,
  case-wide `nextRevisions.at(-1)` head tracking,
  `expectedHeadRevisionId`/Sign-Off CAS and `modelDisplayStatus` for queued
  builds. Include their existing regressions in the focused check.
- [x] Verify keyboard cell/tab navigation and that collapsing/filtering a group moves focus to a remaining visible control.

Browser acceptance assertions to add after the existing Model journey has loaded its worksheet:

```javascript
await page.getByRole("button", { name: "Hide assumptions", exact: true }).click();
for (const semanticId of ["ffo", "cfo_calc", "fcf", "ncf", "cash_and_equivalents"]) {
  assert.equal(await page.locator(`[data-semantic-id="${semanticId}"]`).first().isVisible(), true);
}
await page.getByRole("button", { name: "Show lineage for cash_and_equivalents", exact: true }).first().click();
const sourceAction = page.locator("#model-cell-lineage").getByRole("button", { name: /^Open evidence / }).first();
await sourceAction.click();
await page.keyboard.press("Escape");
await sourceAction.waitFor({ state: "visible" });
assert.equal(await sourceAction.evaluate((element) => element === document.activeElement), true);
```

Run these assertions with the Cash Flow and Balance Sheet groups expanded. Use served fixture IDs for source assertions, never legacy E-103 values.

```bash
cd caos/frontend
node --test src/components/model/modelBuilderState.test.ts
npm run lint
npx tsc --noEmit
```

**Gate:** The whole cash-flow chain is easy to inspect, source navigation works with mouse and keyboard, and changing presentation state never edits model authority.

## Task 3: Restore minimum-cash sensitivity with an explicit horizon

**Files:** Modify `models/service.py`, `contracts.py`, `ModelBuilder.tsx`, model state tests and `test_model_builder_spec.py`.

**Interfaces:** Add output ID `minimum_cash` to `TORNADO_METRICS` and extend
`TornadoResult` with `output_period_ids`. Existing `cash_and_equivalents`
remains period-end Cash. Ordinary metrics return
`output_period_ids: [output_period_id]`; `minimum_cash` returns the selected
case's ordered available forecast columns through the exact endpoint, inclusive.
Use the same horizon for baseline, low and high. Read raw Decimal cash through
`calculations.for_column(column_id)` before `_annual_outputs` serializes it; the
pinned `finite_operand` guard accepts finite Decimals, not serialized strings or
ordinary integer fixtures.

- [x] Add the smallest pure selector beside the existing annual-output helpers, and test it before integrating it:

```python
def minimum_cash_value(calculations, column_ids: list[str]):
    values = [
        finite_operand(
            calculations.for_column(column_id).values["cash_and_equivalents"],
            "minimum cash",
        )
        for column_id in column_ids
    ]
    return min(values)
```

Reuse the existing `finite_operand` calculation guard from `caos.models.engine` rather than a new numeric parser. Required checks:

```python
from decimal import Decimal

assert minimum_cash_value(calculations, ["BASE::FY2025", "BASE::FY2026"]) == Decimal("-20")
```

- [x] Route baseline, low and high tornado outputs through one selector. Build
  the horizon directly from `calculations.columns` for the requested case through
  the exact endpoint. Unknown, wrong-case or unavailable endpoints and any
  missing intermediate or shocked value fail `MODEL_TORNADO_OUTPUT_INVALID`;
  never continue by dropping an adverse bar.
- [x] Keep deadlines, registry checks, assumption bounds, stale revision refusal and finite-value guards unchanged. Add tests for negative minimum cash, final-year cash differing from the minimum, a missing intermediate value, non-finite values and Base/Downside isolation.
- [x] Display `Minimum cash · FY2025–FY2027` using the returned horizon. Keep the final-year cash metric separately labelled. Do not claim a quarterly minimum when only annual forecast outputs exist.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py -q -k 'tornado or minimum_cash'
```

**Gate:** The baseline and every bar use the disclosed horizon; missing data cannot improve apparent liquidity.

## Task 4: Render the real live run graph and node inspector

**Files:** Modify `frontend/src/lib/api.ts`, `Workspace.tsx`; create the four `components/run/` files listed above. Reuse the existing RunRecord refetch and SSE lifecycle.

**Interfaces:** `RunNodeResponse` and `_wire_run` already serve `stage` and
`dependencies`; add them to frontend `RunRecord` and replace only `RunStatus`'s
false linear rendering. `runGraph(nodes)` returns stage groups and exact
`(source module ID, target module ID)` edges. No server graph or control changes.

- [x] Add a branch/merge regression test:

```typescript
import assert from "node:assert/strict";
import test from "node:test";
import { runGraph } from "./runGraph.ts";

test("siblings are not displayed as dependencies", () => {
  const result = runGraph([
    { module_id: "A", stage: 0, dependencies: [] },
    { module_id: "B", stage: 1, dependencies: ["A"] },
    { module_id: "C", stage: 1, dependencies: ["A"] },
    { module_id: "D", stage: 2, dependencies: ["B", "C"] },
  ]);
  assert.deepEqual(result.edges, [["A", "B"], ["A", "C"], ["B", "D"], ["C", "D"]]);
});
```

- [x] Implement the pure projection without inferring adjacent-node edges:

```typescript
type GraphInput = { module_id: string; stage: number; dependencies: string[] };

export function runGraph(nodes: GraphInput[]) {
  const ids = new Set(nodes.map((node) => node.module_id));
  if (ids.size !== nodes.length) throw new Error("RUN_GRAPH_INVALID");
  const stages = new Map<number, GraphInput[]>();
  const edges: [string, string][] = [];
  for (const node of nodes) {
    if (!Number.isInteger(node.stage) || node.stage < 0) throw new Error("RUN_GRAPH_INVALID");
    stages.set(node.stage, [...(stages.get(node.stage) || []), node]);
    for (const dependency of node.dependencies) {
      if (!ids.has(dependency) || dependency === node.module_id) throw new Error("RUN_GRAPH_INVALID");
      edges.push([dependency, node.module_id]);
    }
  }
  return { stages: [...stages.entries()].sort(([a], [b]) => a - b), edges };
}
```

- [x] Render stage columns with SVG dependency connectors and HTML node buttons. Keep an accessible ordered stage/node list that states upstream dependencies. Catch `RUN_GRAPH_INVALID` at the presentational boundary and show the served node list with an unavailable-graph notice; never draw guessed edges. Selected nodes expose an inline inspector, not a second global drawer.
- [x] Key `RunGraph` by `run.id`. Preserve selection across node updates and
  clear it on run switches. Actual node statuses are `pending`, `ready`,
  `running`, `succeeded`, `failed` and `cancelled`; a blocked run is a run-level
  pause plus `run.error`, never an invented node status.
- [x] Inspector fields: module, stage, served status, upstream inputs, exact-edge
  downstream consumers, run-level error/research pause, output link and
  `provider_identity` where served. Do not fabricate durations, percentages, QA
  results or event history absent from the wire.
- [x] Preserve event-name-triggered refetch and add connection freshness:
  `onopen` marks live and refetches, `onerror` marks stale/disconnected without
  changing execution state, and case/run switches reset connection state.
- [x] Test pending, ready, running siblings, success, run-level blocked, failed,
  cancelled, research approval, reconnect and cross-case/run switches. Add an
  HTTP test over all six pathways and both depths comparing served edges to
  `compiled_route.edges`; UI tests cover projection and the accessible invalid-
  graph fallback.

```bash
cd caos/frontend
node --test src/components/run/runGraph.test.ts src/lib/workspaceAuthority.test.ts
```

**Gate:** Displayed edges equal served dependencies. The graph explains the run without moving compile, accept or research approval controls out of Run.

## Task 5: Project validated module outputs into reusable sections and chart data

**Files:** Create `artifacts/presentation.py`, `test_module_presentation_spec.py`; modify `contracts.py`, `responses.py`, `api/__init__.py`, `frontend/src/lib/api.ts` and HTTP contract tests.

**Interfaces:** Define server-owned, bounded mapping-version dispatch around
`project_artifact(artifact, *, mapping_version)`. New projections use the
current mapping; saved revisions request their recorded `mapping_version`, and
unsupported recorded versions explicitly refuse. The caller must first complete
existing artifact/snapshot authority validation. Return a named, strict
`ModulePresentationResponse` with `schema_version`, `artifact_id`,
`artifact_digest`, `mapping_version`, `sections: list[CanonicalDocumentSection]`
and bounded `unavailable` entries `{view_id, code}`. Add typed host presentation
to `ArtifactResponse`; do not alter the provider's canonical envelope.

- [x] Start with the pinned CP-1 fixtures. Use stable identities, not headings chosen by a model:

| Source | Binding | Initial view |
|---|---|---|
| `cp1.model_period_register` + `cp1.model_account_register` | Join on `period_id`; use `metric_id`, `value`, period dates, currency and unit. | Separate revenue/EBITDA trends; CFO and cash trends where supplied. |
| `cp1.adjusted_ebitda_bridge` | `period_id`, `addback_id`, `value`, realization/status fields. | EBITDA adjustments and realization table/visual. |
| `cp1.debt_facility_register` | Select one disclosed period; preserve `facility_id`, principal/carrying-value basis, maturity, currency and seniority. | Maturity distribution and capital-structure table. |
| `cp1b.model_comparator_register` | Explicit current/reference periods, comparison basis and supplied changes. | Earnings comparison; no recomputed change when the contract marks it unavailable. |
| Model Build/Analyst Model Revision outputs | Selected model identity, Base/Downside, available annual periods. | Cash, FCF, leverage and coverage paths in Model/Report. |

- [x] Implement the Task 0 coverage ledger for CP-PARSE, CP-0, CP-1,
  CP-1A/1B/1C/1D, CP-2/2A/2G/2E/2H, CP-3/4/4C/5/6, CP-DR and screen-only
  CP-L10 using their verified current tables. Retain all required tables; add
  charts only where a numeric comparison, trajectory, distribution or matrix
  conveys an actual relationship.
- [x] Reuse existing canonical table parsing/visibility and finite-number guards. The pinned `cp_tables.py` parsers are reference implementations; do not execute a copied parser without the existing integrity boundary. If a host-side table reader is needed, reuse `canonical.py`'s scanner/cell splitter and test duplicate IDs, hidden tables, malformed rows and escaped pipes.
- [x] Keep raw artifact rendering available when a presentation mapping is unavailable. Emit typed view-level reasons such as `TABLE_MISSING`, `COLUMN_MISSING`, `PERIOD_BASIS_MISMATCH`, `UNIT_MISMATCH` and `INSUFFICIENT_POINTS`; do not replace missing data with fixture values.
- [x] Use a closed chart recipe inside the existing `DocumentChartSection.recipe`. The new recipe format is `caos.chart.v1`; supported kinds are `line`, `bar`, `stacked_bar` and `scatter`. Every point carries an unformatted finite numeric value, its display value, category/period, series and source references. The accessible table is derived from those same points. Chart configuration cannot contain JavaScript, HTML, remote URLs or arbitrary G2 options.

Representative complete recipe fixture:

```json
{
  "schema_version": "caos.chart.v1",
  "recipe_id": "cp1.revenue.v1",
  "kind": "line",
  "unit": "USD millions",
  "points": [
    {"x": "FY2024_Q1", "y": "100", "display": "100", "series": "Revenue", "source_ids": ["SRC-1"]},
    {"x": "FY2024_Q2", "y": "110", "display": "110", "series": "Revenue", "source_ids": ["SRC-1"]}
  ]
}
```

For scatter recipes require a separate finite `x_value` in addition to the display label; other kinds reject it. Numeric strings use canonical decimal notation, not locale-formatted text. Bound points to the existing document-table limit of 500; exceeding it produces a declared unavailable view rather than silent truncation.

Retain existing unversioned chart recipes as table exhibits, including scenario
and appendix recipes; do not reinterpret them as `caos.chart.v1`.

- [x] Bind generated section origins to actual artifact IDs and evidence block IDs. Add a test proving projection is deterministic for the same artifact digest/mapping version, and a test that another artifact's ID cannot be substituted into its origin.
- [x] Update named HTTP response keys and cross-case/withdrawn/tampered-artifact tests. Do not introduce a new unauthenticated data endpoint.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_module_presentation_spec.py caos/tests/spec/test_http_contracts_spec.py -q
```

**Gate:** The same validated module output produces the same bounded presentation; the current canonical envelope and module prompts remain unchanged.

## Task 6: Add shared AntV charts and visual Analysis

**Files:** Create `components/charts/ChartExhibit.tsx`, `chartRecipe.ts`, `chartRecipe.test.ts`, `components/analysis/ModulePresentation.tsx`; modify `Workspace.tsx`, `app/globals.css`, frontend package/lock files.

**Interfaces:** `ChartExhibit({section, theme})` consumes the existing `DocumentChartSection` with the closed Task 5 recipe; `theme` is `"workspace" | "paper"`. `ModulePresentation({presentation})` renders projected sections without making its own snapshot request. `chartRecipe.ts` validates and converts the closed recipe to developer-owned G2 options.

- [x] Read the relevant G2 skill and references from [antvis/chart-visualization-skills](https://github.com/antvis/chart-visualization-skills) at implementation time and record the exact source revision. This is developer-time guidance only; do not send issuer data to a remote chart service or add runtime skill retrieval or a chart-generating agent.
- [x] Add G2 v5 as the one chart runtime dependency, resolve and review one
  exact `5.x.y` version, then commit that exact package version with its lockfile:

```bash
cd caos/frontend
npm install --save-exact @antv/g2@<reviewed-5.x.y>
```

- [x] Write adapter tests for line/bar/stacked-bar/scatter recipes, negative and zero values, canonical numeric parsing, mixed units, missing values, unsupported kinds and malicious configuration fields. Tests must assert the data points and encodings, not merely that a component name appears in source.
- [x] Initialize G2 only in the client component; lazy-load it for surfaces displaying a chart. Disable decorative animation. Resize to the containing panel, destroy the chart and observers on unmount, and handle rapid artifact switches without stale rendering.
- [x] Show a meaningful title, period/basis, units, legend where needed, source actions and a keyboard-accessible data table for each chart. Render table-only with a visible explanation if the chart cannot load; chart failure must not hide the module content.
- [x] Place summary and visual exhibits before the detailed stable tables and narrative for the selected module. Keep module navigation and the existing evidence rail; retain artifact digest, accepted snapshot and input fingerprint.
- [x] Add visual coverage for the numeric modules inventoried in Task 5. Qualitative modules receive structured decision/evidence tables and narrative hierarchy, not arbitrary numeric scoring.
- [x] Verify 1440px, 1024px and 720px, reduced motion, keyboard access, dark workspace contrast and source navigation. Switching accepted snapshots must update content, charts and evidence together.

```bash
cd caos/frontend
node --test src/components/charts/chartRecipe.test.ts src/lib/artifactReader.test.ts src/lib/workspaceAuthority.test.ts
npm run lint
npx tsc --noEmit
npm run build
```

**Gate:** Analysis becomes a module-specific visual workbench using accepted data, not a generic chart playground. Charts and accessible tables carry identical values.

## Task 7: Make Report module-populated and developer-designed

**Files:** Modify `deliverables/service.py`, `deliverables/document.py`, `responses.py`, report frontend components/types/state tests, `test_deliverables_spec.py`; use Task 5 projections and Task 6 ChartExhibit.

**Interfaces:** Preserve `DeliverableDraftRequest` as analyst-authored inputs
only, extending it only with a bounded list of declared optional-section IDs for
include/omit choices. Template v2 has server-owned presentation slots plus
optional Narrative/Limitations overlays; its required client block is the
Evidence Register. Dispatch stored template versions consistently through
`DeliverableService._template_for`, workspace, `save_draft`, both freeze
template lookups and `compose_document`. Existing v1 interpretation remains
available by stored identity. Persist the server-selected `mapping_version` in
v2 revision content; recomposition uses that recorded version, and an explicit
new revision is required to adopt a newer mapping.

- [x] Write a failing v2 test: save a draft with its Evidence Register and zero Narrative Blocks; assert the server composes populated module sections. Require real known fixture facts, section origins and source references, not the fallback text `Governed output pinned`.
- [x] Write compatibility tests before changing templates: v1 draft read, save,
  restore, browser recovery and both freeze paths remain under v1; Frozen/Filed
  v1 payloads and export hashes remain byte-identical. Moving to v2 is an
  explicit new revision requiring renewed Sign-Off; never silently recompose v1
  content under v2.
- [x] On the first unsaved opening, `workspace` returns a server-composed preview
  while preserving explicit model-selection acknowledgement.
- [x] Implement fixed report layouts by pathway:

| Pathway | Developer-designed sections, populated from accepted outputs |
|---|---|
| Full Credit → Credit Report | Credit summary; business/transaction; financial performance and earnings quality; capital structure; Base/Downside model; liquidity/covenants; relative value; risks/catalysts/monitoring; evidence/QA. |
| Earnings Update | Period/comparator context; reported-versus-prior changes; earnings quality; accepted pathway model effects; leverage/liquidity; implications and monitoring. |
| Covenant & Refinancing | Debt/maturity profile; covenant definitions and headroom; liquidity; refinancing/restructuring findings; model effects; actions and evidence. |
| Relative Value | Pinned instrument universe; peer/issuer comparison; structure/seniority; compensation/ranking; catalysts, freshness and trade gates. |
| Distressed & Restructuring | Priority stack; liquidity runway; scenario/breakpoint outputs; recovery/fulcrum; legal/process milestones; recommendations and limitations. |
| Deep Research | Research question/scope; findings; evidence and counterevidence; implications; unresolved questions. |

- [x] Treat generated narrative as module content, with artifact/source origins; analyst amendments are separately labelled overlays. Do not recast provider text as an analyst opinion, invent recommendations, or create a second analytical synthesis call.
- [x] For every section, declare its exact source module/table binding in the coverage ledger. Missing required inputs produce a visible unavailable section and a typed publication blocker; intentionally optional inputs can be omitted with a reason. Reports for pathways without CP-6 must work without CP-6 or an IC memo.
- [x] Rework ReportStudio navigation around generated document sections rather than required textareas. Open the populated paper preview by default; provide inline “Add commentary”, include/omit controls for declared optional sections, source inspection and model selection. Persist optional-section IDs through autosave, recovery and freeze. Layout geometry remains developer-owned; no drag-and-drop page designer.
- [x] Use one validated citation union across included generated sections and
  analyst citations. It populates both the visible Evidence Register and
  `DeliverableService._frozen_evidence`; `publishing.build_publication` evidence
  inventory/status reads `payload.evidence`. Test generated-only source and block
  citations through freeze and offline verification.
- [x] Preserve analyst-text claim-authority checks, current model-selection
  acknowledgements, `ReportStudio.retainRecovery`, cloned-tab ownership through
  `reportRecovery.claimBrowserTabId`, unsigned-opinion protection, guarded
  navigation/freeze, and receipt-request abort plus case/deliverable identity
  checks. Include `reportRecovery.test.ts` in focused checks.
- [x] Render chart sections through ChartExhibit in paper mode. Reuse exact data and recipe identities from Analysis where the same module view is selected.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'template or document or narrative or evidence or draft'
cd caos/frontend
node --test src/components/report/documentTypes.test.ts src/components/report/reportStudioState.test.ts src/components/report/ReportStudio.test.ts
node --test src/components/report/reportRecovery.test.ts
```

**Gate:** Each pathway yields a substantive designed report from accepted modules without manually writing every section. “No mandatory IC memo” is proven with pathways that contain no CP-6, while current execution and publication controls still hold.

## Task 8: Bind incremental reports to their actual model effects

**Files:** Modify `deliverables/service.py`, `document.py`,
`models/service.py::validated_publication_build` and
`models/service.py::_validated_prior_full_credit_publication_build`,
model-selection types only where needed, `test_deliverables_spec.py`,
`test_source_complete_modelling_spec.py`, `docs/DECISIONS.md`, and `CLAUDE.md`
known-gap entries.

**Interfaces:** Retain validated prior Full Credit ancestry, but select the accepted pathway's overlay Model Build or a compatible Signed-Off Revision when the report displays its effects. Bind both the overlay identity and its prior-model ancestry into the frozen payload and digest.

- [x] Add a failing regression to the existing live-incremental publication test: change an accepted Earnings Update calculation effect while leaving the prior Full Credit model unchanged; assert that the new report's effect section and model identity change. Repeat for Covenant & Refinancing.
- [x] Fix the shared model-authority resolver before composition: current
  resolution selects the prior Full Credit build too early. Select the accepted
  pathway overlay Model Build or a compatible Signed-Off Revision while
  preserving its validated Full Credit ancestry, model recomputation and source-
  lineage checks; do not patch renderers independently.
- [x] Distinguish **unchanged prior-model base values** from **new pathway effects**. The existing overlay may carry effects without recalculating every base worksheet cell; never label unchanged base values as an updated forecast.
- [x] Verify Relative Value and Deep Research effect inclusion where an eligible numeric overlay exists; model-optional reports remain usable without one. Preserve the already-supported Distressed binding.
- [x] Test wrong ancestry, wrong accepted run, stale Signed-Off Revision, withdrawn source, missing overlay, changed effect after Sign-Off, and a publication retry. A required missing overlay is a typed readiness blocker, not silent fallback.
- [x] Remove only the known-gap entries actually closed by passing tests; retain explicit limitations on effects that do not recalculate the full forecast.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_deliverables_spec.py -q -k 'incremental or model or authority'
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_source_complete_modelling_spec.py -q
```

**Gate:** Published model effects match the selected accepted pathway authority, and base-versus-effect distinctions are explicit.

## Task 9: Preserve report charts and data through freeze, filing and export

**Files:** Modify `publishing/document.py`, `renderers.py`, `markdown.py`, `audit/verify_package.py`, publication and golden spec tests; create `publishing/charts.py` for the closed chart kinds. Update renderer-version pins and reviewed goldens together.

**Interfaces:** All renderers consume frozen `publication` sections and closed
chart recipes only. No renderer fetches current artifacts, model state, web
resources or a newer mapping. `publishing/charts.py` converts trusted finite
recipe values into deterministic vector marks; financial calculations remain
elsewhere. Reuse the installed pango/pypdf/openpyxl stack; add no browser worker
or provider SVG parser.

- [x] Add a publication fixture with positive, negative and zero values, long labels, multiple series and source references. Assert the frozen recipe, accessible rows and origin IDs are identical to the reviewed draft.
- [x] Extend the existing PDF renderer with chart blocks: reserve measured chart space, draw the closed kinds through the installed pypdf vector/content-stream primitives, retain pango for pinned-font labels, and place the equivalent table after the chart. Do not add a browser process to the worker or parse provider-supplied SVG.
- [x] Add native openpyxl charts bound to the exported numeric cells; preserve the underlying data sheets, safe-cell handling, sources and model identity. Markdown retains chart title/type, period/unit, sources and the equivalent table; explicitly treat it as the text representation.
- [x] Keep freeze asynchronous and hash-addressed. Increment `RENDERER_VERSION`; preserve existing stored exports. If Markdown changes, update its verbatim copy in the standalone audit verifier and the copy-parity test.
- [x] Verify charts cannot overprint footers, source notes or watermarks, and that tables paginate with repeated headers. Inspect every changed PDF page and XLSX sheet before regenerating goldens.
- [x] Assert filing serves the exact already-frozen bytes, including after an
  application/template update. Preserve opinion-bound `filing_thread_id`
  including legacy identities, independent signer/freezer checks,
  `audit/package.py`'s single transaction snapshot, and verifier refusal of
  invalid/missing sections or missing frozen authority. Keep the Markdown
  renderer and standalone verifier copy in parity.

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_publication_spec.py caos/tests/spec/test_publication_goldens_spec.py -q
```

Only after visual inspection and approval of the changed output:

```bash
CAOS_REGENERATE_GOLDENS=1 caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_publication_goldens_spec.py -q
```

**Gate:** Browser, PDF and XLSX contain the intended chart and its authoritative data; Markdown contains the equivalent data. Every format retains the same facts, evidence, selected model and frozen identity.

## Task 10: Qualify the four-capability analyst journey

**Files:** Extend `frontend/scripts/workbench-smoke.mjs`, `a11y-axe.mjs`,
relevant spec tests and `SPEC_RECONCILIATION.md`; add
`caos/tests/spec/test_audit_package_spec.py` and
`caos/tests/test_verify_package_bounds.py` to the acceptance suites; retain
results under the existing test-results conventions.

**Interfaces:** Use public application routes with
`qa/serve_browser_integration.py`, an isolated data directory and matching
`CAOS_URL`. The harness starts its own worker; do not start a duplicate worker.
Never use the user's legacy port or case data. Host-control fixtures prove
orchestration, not live analytical quality.

- [x] Run one seeded current-app journey through intake/run → inspect branching pipeline → accept → inspect visual Analysis → build/edit/sign off Model → open module-populated Report → add commentary → sign opinion → freeze → independently file → verify exports and audit package.
- [x] Assert the same case, accepted snapshot, artifact/model identities and source references throughout. Switch cases, selected runs and accepted snapshots mid-load; stale data must never flash as current.
- [x] Compare exact served and displayed dependency pairs for the 11 supported pathway/depth combinations. Retain Deep Research/screen as the existing API 422 plus UI-disabled negative contract; do not fabricate or claim a twelfth displayed DAG.
- [x] Exercise Base/Downside, negative minimum cash, missing source/table/period, partial analysis, failed/cancelled modules, research-plan pause, stale revision, autosave conflict, browser recovery and export failure.
- [x] Capture Model, Report, Run and Analysis at 1440px, 1024px and 720px in Chromium, Firefox and WebKit. Inspect hierarchy, table/worksheet scrolling, actual graph edges, chart labels, print layout and focus restoration; run axe on populated and refusal states.
- [x] Run the complete relevant suites and existing performance tripwires. Record actual measurements; do not relax timing limits to accommodate eager chart loading without a separately reviewed reason.

Backend, from repository root:

```bash
caos/server/.venv314/bin/python -m pytest caos/tests/test_audit_regressions.py caos/tests/test_verify_package_bounds.py caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_source_complete_modelling_spec.py caos/tests/spec/test_module_presentation_spec.py caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_publication_charts_spec.py caos/tests/spec/test_publication_goldens_spec.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_audit_package_spec.py caos/tests/spec/test_distressed_model_overlay.py caos/tests/spec/test_ordinary_distressed_e2e.py -q
```

Frontend preparation, from `caos/frontend`, before starting the disposable harness:

```bash
npm run lint
npx tsc --noEmit
npm run test:unit
npm run build
```

Then start the fresh disposable harness, which owns its worker, and run:

```bash
node scripts/fault-regressions.mjs
npm run a11y
npm run test:browsers
```

Run the browser journey explicitly in Chromium, Firefox and WebKit at 1440,
1024 and 720 widths, including keyboard/focus, reduced-motion, axe, authority
races, recovery/refusals and exports/audit. `test:browsers` runs only the
workbench smoke, so the explicit fault-regression command above is mandatory.
Set `CAOS_URL` to the disposable harness and `CAOS_RESULTS_DIR` to an isolated
results directory before browser commands. Capture screenshots and export
examples. Do not run `test:production-inventory`: its known deployment-specific
routes are not part of this build.

Qualification result: all Task 10 checkboxes below are backed by
`.superpowers/sdd/analyst-workbench-task-10-report.md` and its SHA-256-manifested
evidence. The 11-graph plus Deep Research/screen-negative distinction follows
the current route/API contract; no unsupported route was invented.

- [x] Run the required `rewrite-tournament` and `confidence-review` gates on changed code. Record suspected defects, root-cause checks and repaired findings, not just a claim that the skills ran.
- [x] Deliver a completion report with per-workstream acceptance status, command results, screenshots, export examples, remaining limitations and explicit separation of fixture orchestration proof from live analytical qualification. No live-provider qualification is authorized.

**Gate:** All four capability rows in the workstream table pass. A successful build or unit suite alone is not completion.

## Commit and execution checkpoints

Keep reviewable checkpoints after each task. Suggested commit subjects, when implementation includes commit authorization:

1. `docs: define module-driven analyst workbench contract`
2. `test: pin complete cash-flow worksheet coverage`
3. `feat: improve model navigation and evidence lineage`
4. `feat: add horizon minimum-cash sensitivity`
5. `feat: show actual run dependencies and node context`
6. `feat: project accepted module outputs into analytical views`
7. `feat: add source-bound visual analysis`
8. `feat: compose reports directly from accepted modules`
9. `fix: bind incremental reports to accepted model effects`
10. `feat: preserve report charts in frozen exports`
11. `test: qualify the complete analyst workbench journey`

Do not commit unrelated changes. Task checkpoints do not authorize a merge, production deployment, real-case mutation, paid provider run or an automatic acceptance/filing action.

## Explicit non-goals

- Replacing the current application with legacy code or importing legacy fixture values, persistence, runtime state or calculation engines.
- Changing module steps, dynamically selecting execution edges, or removing CP-6 from existing routes.
- Requiring an IC memo or adding another report-generation model call.
- Building a general-purpose chart/layout editor, plugin system, graph editor or remote chart service.
- Inferring missing financial data, treating unavailable as zero, or presenting a methodology change as a styling fix.
- Claiming enterprise/live-analysis qualification from these development fixtures.
