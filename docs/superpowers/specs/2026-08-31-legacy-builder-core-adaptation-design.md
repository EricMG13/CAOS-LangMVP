---
meta:
  contentType: Conceptual
  title: How should the current application adopt the legacy builder core functions?
  navLabel: Legacy Builder Adaptation
  category: Architecture
---

# How should the current application adopt the legacy builder core functions?

The current application should retain its case, authority, revision, freeze, filing, and export controls. It should adopt the legacy report renderer and model worksheet experience. Reports should regain the legacy document quality. Models should open in the required workbook template with starting forecast assumptions. Historical accounts and all calculated cells must remain immutable.

## Design plan

- **Goal**: define how to port the legacy report and model builder core functions without porting their operational architecture
- **Audience**: engineers implementing Report Studio, Model Builder, model services, deliverable composition, and export rendering
- **Content plan**: record the product boundaries, selected approach, contracts, data flow, failure behavior, compatibility rules, and acceptance tests
- **Open questions**: none; the product boundaries in this specification are approved

## Product decision

This design treats the legacy builders as presentation and workflow references. The current application remains the system of record.

The report decision has four parts:

- Restore the legacy document structure, typography, pagination, tables, charts, columns, source presentation, and print layout
- Compose module and agent outputs into decision-ready documents instead of displaying flattened payloads
- Permit edits only in narrative and analyst-judgment fields
- Keep generated figures, evidence, historical values, model exhibits, and scenario outputs locked

In this specification, the same documents means the same approved section order, decision content, table and chart structure, page grouping, visual hierarchy, source presentation, and print behavior. Current case data replaces legacy fixture values.

The model decision has four parts:

- Open the generated model inside the required workbook template
- Preserve source-derived historical accounts and historical calculations without modification
- Initialize forecast controls from the current assumption registry
- Apply analyst changes only to forward projections through preview and sign-off

## Approaches considered

Three approaches were considered:

| Approach | Benefit | Cost | Decision |
| --- | --- | --- | --- |
| Port the legacy pages and their state management | Preserves the legacy experience with fewer visual changes | Imports legacy operational coupling and creates a second authority model | Reject |
| Rebuild both builders from current components | Keeps current conventions | Recreates mature document and worksheet behavior | Reject |
| Port the legacy presentation cores onto current contracts | Preserves the useful legacy behavior and current authority guarantees | Requires explicit adapters and golden parity tests | Select |

The selected approach ports the legacy report section grammar and worksheet interaction. It does not port legacy fixtures, persistence, runs, checkpoints, leases, routing, or publication state.

## Preserve current authority boundaries

The current application owns every durable transition. The adaptation must continue to use the existing accepted snapshot, application model build, analyst revision, deliverable draft, frozen deliverable, and filed deliverable records.

The following current behaviors remain unchanged:

- Accepted Full Credit snapshots create application model builds
- Model previews remain transient and server-calculated
- Model sign-off creates immutable analyst revisions through compare-and-swap checks
- Deliverable drafts remain append-only revisions with template and citation validation
- Freeze binds the exact draft, evidence, model identity, methodology build, and input fingerprint
- Filing approves the exact frozen preview
- Exports render only from the frozen payload

Legacy state must never become an alternate source of truth.

## Compose decision-ready reports

Report composition should produce one canonical `document_sections` value. This value contains the semantic document that every preview and export renders.

### Port the legacy section grammar

Port the useful legacy section types into a current deliverable contract:

- `text` for narrative and analyst judgment
- `profile` for compact decision and identity facts
- `table` for financials, capital structure, risks, actions, and evidence registers
- `list` for strengths, weaknesses, catalysts, falsifiers, and required actions
- `chart` for model paths and decision-relevant comparisons
- `columns` for paired sections
- `page` metadata for stable document grouping and pagination

Each section must include a stable section ID, title, source block IDs, editability, and origin. Generated sections must identify the accepted artifact or signed model revision that supplied their values.

### Keep current blocks as the authoring contract

Current `DeliverableBlock` records remain the saved authoring input. `document_sections` is a deterministic projection of those blocks and their pinned authority.

This separation keeps edit scope narrow:

- Narrative and limitations blocks may update their corresponding editable sections
- Evidence-backed narrative still requires valid citations
- Generated metric, table, chart, scenario, and model appendix sections are read-only
- A client cannot submit generated section values

The service recomposes `document_sections` after each accepted draft save. Freeze recomposes from the stored revision and verifies the same result before calculating its digest.

### Map module output into the document

Each pathway should define a composition recipe beside its existing template. A recipe maps stable canonical artifact fields, table IDs, and model output IDs into ordered document sections.

Recipes must read current canonical artifacts. They must not copy the legacy Atlas Forge fixture data or scrape rendered browser text.

Required values fail closed. Optional unavailable values render an explicit limitation only when the pathway recipe permits one. The composer must never invent a value, infer an unstated unit, or substitute a different module.

The result should answer the decision task directly. For example, the Full Credit memo should place the recommendation, supporting evidence, financial history, forward model, liquidity, covenants, risks, falsifiers, and monitoring actions in their approved legacy-quality layout.

### Render the same semantic document everywhere

Draft preview, frozen review, filed review, Markdown, Portable Document Format (PDF), and spreadsheet exports must consume `document_sections`.

The React renderer should reuse the legacy `ReportDoc` layout and accessibility behavior. Server exporters should render the same section order, headings, values, units, citations, page groups, and locked-state markers. Format-specific typography may differ, but content and structure must not drift.

Golden fixtures should detect drift between the approved legacy documents, the browser preview, and frozen exports.

## Restore the useful model worksheet

The current model service already owns the required calculation behavior. It generates a workbook payload, exposes an assumption registry, calculates previews and sensitivities, rebases revisions, and signs revisions. This design does not introduce another model engine.

### Display the generated required template

Model Builder should load the current application model build and display its worksheet payload with the legacy worksheet interaction and formatting.

The worksheet metadata already identifies semantic IDs, owners, write classes, periods, formulas, and source references. The interface should use this metadata to explain every locked value.

Historical source cells, snapshot-derived cells, and calculated cells remain locked. Formula inspection and lineage remain available.

### Edit forecast assumptions only

The forecast controls should reproduce the legacy worksheet experience while using the current assumption registry as authority.

Each control should show its starting value, case, period, unit, allowed range, and affected outputs. Only registry rows with `READY` status may change. Gap rows remain visible and disabled.

Analyst changes update an in-memory draft assumption set. They do not modify the application build or worksheet history. The server must reject any submitted identity that is absent from the registry, targets a nonforecast period, changes a unit, or exceeds its declared bounds.

### Recalculate forward projections

A preview sends the complete effective assumption set with the build identity, registry identity, parent revision, and draft generation. The current model service calculates the result.

The preview must preserve historical values and historical calculations. Only forecast columns and outputs derived from forecast assumptions may differ from the application build.

The interface should place preview values into the forecast columns and mark changed forecast inputs. Derived forecast cells remain locked. The analyst reviews deltas before sign-off.

Sign-off stores the effective assumptions, outputs, digests, model identity, parent revision, and analyst note in the existing immutable revision record.

### Bind reports to signed model outputs

Report composition should select either the active signed analyst revision or the acknowledged application build fallback. It must never read an unsaved browser preview.

A frozen deliverable records the selected model identity and exact outputs. A later model revision cannot change an existing frozen or filed document.

## Data flow

The adaptation uses one authority path:

```text
accepted snapshot
  -> application model build and required worksheet
  -> forecast assumption draft
  -> server preview
  -> signed analyst revision
  -> deliverable composition from artifacts, narrative, evidence, and model
  -> document_sections
  -> draft preview
  -> frozen exports
  -> independent filing
```

No legacy persistence or client-generated calculation enters this path.

## Expose the required application interfaces

The current service methods should be exposed through the existing case-scoped Application Programming Interface (API). The first implementation plan should confirm the final paths against current tests.

The required model surfaces are:

- Read the application build worksheet
- Read the versioned assumption registry
- Calculate a forecast preview
- Sign an analyst revision
- Calculate one-way sensitivity and scenarios
- Calculate a rebase preview
- Queue and download application build and revision exports

The current user interface already calls several of these paths and handles unavailable routes. Implementation should connect those calls to the existing `ModelService` methods instead of adding replacement services.

The deliverable draft response should add `document_sections` and its schema version. Frozen payloads should pin the same fields and include their digest through the existing content digest.

## Failure behavior

The system should preserve useful work while refusing invalid authority transitions.

Report failures follow these rules:

- A missing required artifact field blocks composition and freeze
- A missing optional value produces only a recipe-approved limitation
- A withdrawn or mismatched citation blocks save or freeze through existing validation
- A composition version mismatch requires recomposition before freeze
- A render failure leaves the prior draft intact and creates no frozen record

Model failures follow these rules:

- An attempt to edit a historical, calculated, unknown, unavailable, or out-of-range assumption fails server validation
- A calculation error leaves the forecast draft in browser memory
- A stale build preserves the draft and offers the existing rebase flow
- A preview digest mismatch blocks sign-off
- An unsigned preview never feeds report composition

Errors should name the missing identity or invalid field. They should not expose host paths, internal exceptions, or partial exports.

## Compatibility and migration

Existing deliverable drafts do not need a data migration. The service can derive `document_sections` from their stored blocks and pinned inputs when the draft opens or saves.

Existing model builds already contain worksheet payloads and assumption defaults. The adaptation should expose and render those records before changing their storage schema.

Template and renderer versions must increase when composition or layout changes. Existing frozen and filed deliverables continue to render from their pinned payload and renderer version.

## Verification

Verification should focus on the two approved product guarantees.

### Report acceptance tests

- Every current pathway produces its required ordered sections from canonical test artifacts
- Approved reference documents match the legacy section order, tables, charts, page groups, labels, and decision content
- Browser and frozen exports contain the same section IDs, values, units, citations, and model identity
- Only narrative and analyst-judgment sections expose edit controls
- Generated and evidence sections reject submitted value changes
- Missing required values block freeze with a typed error
- A filed document remains unchanged after later source, model, template, or renderer changes

### Model acceptance tests

- A completed build opens in the required worksheet template with starting forecast assumptions
- Historical source values and historical calculated values remain identical across build, preview, and sign-off
- The server rejects historical and calculated-cell mutations even when a client constructs the request manually
- Changing one forecast assumption changes only eligible forward inputs and derived forecast outputs
- Gap assumptions remain visible and disabled
- Preview, sensitivity, rebase, and sign-off preserve the current identity and digest checks
- Report composition reads the signed revision, never the local forecast draft

### Visual and accessibility tests

- Approved desktop and print captures match the legacy report hierarchy and worksheet readability
- Tables retain row and column semantics at narrow and zoomed layouts
- Charts include accessible summaries and equivalent data tables
- Locked and editable cells remain distinguishable without relying on color
- Keyboard navigation reaches report edit fields, worksheet cells, forecast controls, lineage, preview, and sign-off

## Implementation boundary

Implementation should proceed in this order:

1. Expose the existing model service methods and restore the required worksheet with forecast-only editing
2. Define `document_sections` and compose the Full Credit pathway from canonical artifacts and signed model outputs
3. Port the legacy report renderer and connect it to the canonical sections
4. Make frozen exporters consume the same sections
5. Add the remaining pathway recipes and their golden documents

The first slice should prove one complete Full Credit case. It should include a generated worksheet, forecast edit, signed revision, actionable memo, frozen PDF, and filing. Additional pathways should reuse the same section grammar and authority flow.

## Out of scope

This design excludes:

- Legacy report and model persistence
- Legacy run selection, checkpoints, leases, heartbeats, routing, and publication state
- Legacy hardcoded issuer and report fixture data
- Free-form historical overrides
- Arbitrary formula editing
- Client-side model calculations
- A second report or model authority layer
