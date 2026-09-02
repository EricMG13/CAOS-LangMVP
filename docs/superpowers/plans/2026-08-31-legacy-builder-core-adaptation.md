# Legacy Builder Core Adaptation Implementation Plan

> **Status (2026-09-01, `ba97a89`):** Tasks 1–7 were implemented by `e2faa9d`, `e098fa7`, `57253a9`, `33d9d61`, `e9d33ff`, and `874b087`. This file is retained as design history. Its host/browser tests must be rerun and retained on the enterprise candidate; implementation here does not close an enterprise gate by itself.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore the legacy report-document quality and useful model worksheet interaction on top of the current application's governed model, revision, deliverable, freeze, filing, and export authority.

**Architecture:** Keep `DeliverableBlock` as the only client-authored report input and the current `ModelService` as the only calculator. Expose the service methods the frontend already expects; treat worksheet cells as an immutable view and the assumption registry as the only forecast edit surface. Add one server-composed, versioned `document_sections` projection to every deliverable revision and frozen payload, then render that same projection in React and every export.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLite/PostgreSQL domain stores, React 19, Next.js 16 static export, TypeScript 5.8, native CSS, pytest, Node test runner, Playwright/axe.

## Global Constraints

- Preserve all ten invariants in `CLAUDE.md`, especially pinned authority, strict canonical module output, pure finite model calculations, and digest-bound approvals.
- Do not edit `caos/server/caos/methodology/vendor/` or import legacy persistence, fixtures, routes, calculation logic, or state management.
- Historical/source/snapshot/calculated worksheet cells are never writable. The only writable model values are `READY` assumption-registry rows for forecast periods.
- The browser never supplies generated report content. It sends current `DeliverableBlock` inputs; the server composes `document_sections` from stored blocks and pinned authority.
- Draft preview, frozen review, Markdown, PDF, and XLSX consume the same ordered semantic sections.
- Preserve the unrelated untracked `caos-visual-audit.mjs` file.
- Use test-first changes. After non-trivial code changes run `rewrite-tournament`, then run `confidence-review` before declaring the implementation complete.

---

### Task 1: Serve the model capabilities that already exist

**Files:**

- Modify: `caos/server/caos/api/__init__.py:20-45,733-900`
- Modify: `caos/server/caos/responses.py:290-320`
- Test: `caos/tests/spec/test_model_builder_spec.py:1220-1490`
- Test: `caos/tests/spec/test_http_contracts_spec.py:240-360`

**Step 1: Write failing HTTP tests**

Add a single async route-coverage test beside the existing HTTP preview test. Reuse `_built_case`, `_preview_request`, `_sign_off_request`, and `_one_way_request` already defined in the file:

```python
async def test_http_extended_model_routes_expose_existing_service(
    client, models, engine, store,
) -> None:
    case, build = await _built_case(models, engine, store)
    registry = models.assumption_registry(case["id"], build["id"])
    available = next(
        row for row in registry["defaults"]
        if row["status"] == "READY" and row["case"] == "BASE"
    )
    definition = next(
        row for row in registry["definitions"]
        if row["assumption_id"] == available["assumption_id"]
    )
    step = float(definition["sensitivity_default"]["step"])

    worksheet = client.get(
        f"/api/cases/{case['id']}/models/{build['id']}/worksheet",
        headers=_ANALYST,
    )
    assert worksheet.status_code == 200
    assert worksheet.json()["payload"]["schema_version"] == "caos.model.worksheet.v1"

    sensitivity = client.post(
        f"/api/cases/{case['id']}/models/sensitivities/one-way",
        json=_one_way_request(
            registry,
            build["id"],
            available,
            minimum=float(available["value"]),
            maximum=float(available["value"]) + step,
            step=step,
        ).model_dump(mode="json"),
        headers=_ANALYST,
    )
    assert sensitivity.status_code == 200
    assert sensitivity.json()["build_id"] == build["id"]

    preview = models.preview(case["id"], _preview_request(registry, build["id"]))
    revision = models.sign_off(
        case["id"],
        _sign_off_request(registry, build["id"], preview),
    )
    rebase = client.post(
        f"/api/cases/{case['id']}/model-revisions/rebase-preview",
        json={"revision_id": revision["id"], "build_id": build["id"], "draft_generation": 2},
        headers=_ANALYST,
    )
    assert rebase.status_code == 200

    assert client.post(
        f"/api/cases/{case['id']}/models/{build['id']}/export", headers=_ANALYST,
    ).status_code == 202
    assert client.post(
        f"/api/cases/{case['id']}/model-revisions/{revision['id']}/export", headers=_ANALYST,
    ).status_code == 202
```

Extend the binary-download test after running the existing export worker seam:

```python
service.run_export_for_tests(revision["id"])
download = client.get(
    f"/api/cases/{case['id']}/model-revisions/{revision['id']}/download",
    headers=_ANALYST,
)
assert download.status_code == 200
assert download.headers["content-type"] == XLSX_MEDIA_TYPE
```

Add the new JSON paths to the named-response/open-schema assertions in `test_http_contracts_spec.py`.

**Step 2: Run the focused tests and confirm 404 failures**

Run:

```bash
python -m pytest caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_http_contracts_spec.py -q
```

Expected: new assertions fail with `404 Not Found`; existing model tests remain green.

**Step 3: Add only the three missing open response envelopes**

In `responses.py` add:

```python
class ModelWorksheetResponse(OpenWireModel):
    pass


class ModelSensitivityResponse(OpenWireModel):
    pass


class ModelRebasePreviewResponse(OpenWireModel):
    pass
```

Reuse `ModelBuildResponse`, `ModelRevisionResponse`, and binary responses for export routes; do not add redundant schemas.

**Step 4: Wire the existing methods through case-scoped authorization**

Import `ModelRebasePreviewRequest` and `OneWaySensitivityRequest`, then add the routes below. Keep reads read-authorized and calculations/queues write-authorized.

```python
@app.get(
    "/api/cases/{case_id}/models/{build_id}/worksheet",
    response_model=wire.ModelWorksheetResponse,
)
def model_worksheet(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
    visible_build(case_id, build_id, request)
    worksheet = models().worksheet(build_id)
    if worksheet is None:
        raise HTTPException(status_code=409, detail={"code": "MODEL_WORKSHEET_NOT_READY"})
    return worksheet


@app.post(
    "/api/cases/{case_id}/models/sensitivities/one-way",
    response_model=wire.ModelSensitivityResponse,
)
def model_one_way(
    case_id: str,
    request: Request,
    body: OneWaySensitivityRequest = Body(...),
) -> dict[str, Any]:
    require_case(store, case_id, identity(request), write=True)
    try:
        return models().one_way(case_id, body)
    except ValueError as exc:
        raise model_error(exc) from exc


@app.post(
    "/api/cases/{case_id}/model-revisions/rebase-preview",
    response_model=wire.ModelRebasePreviewResponse,
)
def model_rebase_preview(
    case_id: str,
    request: Request,
    body: ModelRebasePreviewRequest = Body(...),
) -> dict[str, Any]:
    require_case(store, case_id, identity(request), write=True)
    try:
        return models().rebase_preview(case_id, body)
    except ValueError as exc:
        raise model_error(exc) from exc
```

Add a `visible_revision` helper mirroring `visible_build`, then use one shared binary response helper for both build and revision downloads. Queue exports with `models().queue_export(target_id, who.subject)` and return status 202 through the existing build/revision wire envelopes.

**Step 5: Run focused tests**

Run the command from Step 2.

Expected: all model and HTTP-contract tests pass.

**Step 6: Commit**

```bash
git add caos/server/caos/api/__init__.py caos/server/caos/responses.py caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_http_contracts_spec.py
git commit -m "feat: expose governed model builder capabilities"
```

---

### Task 2: Make model edit authority explicit in the worksheet UI

**Files:**

- Modify: `caos/frontend/src/components/model/modelBuilderState.ts:1-330`
- Modify: `caos/frontend/src/components/model/ModelBuilder.tsx:45-330,560-750`
- Modify: `caos/frontend/src/app/globals.css` (existing model worksheet rules)
- Test: `caos/frontend/src/components/model/modelBuilderState.test.ts`
- Test: `caos/frontend/src/components/model/ModelBuilder.test.ts`

**Step 1: Write the failing authority test**

Add one table-driven test around the worksheet metadata already returned by the server:

```typescript
test("worksheet authority locks history and calculations", () => {
  assert.deepEqual(worksheetCellAuthority({ write_class: "SOURCE", period_id: "FY2024" }), {
    editable: false,
    label: "Historical source — locked",
  });
  assert.deepEqual(worksheetCellAuthority({ write_class: "CALCULATED", period_id: "FY2027" }), {
    editable: false,
    label: "Calculated formula — locked",
  });
  assert.deepEqual(worksheetCellAuthority({ write_class: "ASSUMPTION", period_id: "FY2027" }), {
    editable: false,
    label: "Forecast assumption — edit in Assumptions",
  });
});
```

This deliberately keeps worksheet cells read-only: forecast edits continue through the complete registry request, never an ad-hoc cell patch.

**Step 2: Run the unit test and confirm the missing helper**

```bash
cd caos/frontend && npm run test:unit
```

Expected: the new import/function assertion fails.

**Step 3: Add the minimal authority helper**

```typescript
export function worksheetCellAuthority(cell: Pick<WorksheetCell, "write_class" | "period_id">) {
  if (cell.write_class === "CALCULATED") {
    return { editable: false, label: "Calculated formula — locked" } as const;
  }
  if (cell.write_class === "ASSUMPTION") {
    return { editable: false, label: "Forecast assumption — edit in Assumptions" } as const;
  }
  return { editable: false, label: "Historical source — locked" } as const;
}
```

If `WorksheetCell` is currently local to `api.ts`, export/reuse that type rather than duplicating it.

**Step 4: Apply the helper to each worksheet cell**

Use a native `<button type="button">` only for inspectable cells; show the authority label in `aria-label`, `title`, and the lineage panel. Add `data-write-class` for CSS. Do not add an `onChange` path to `WorksheetGrid`.

Keep the existing Assumptions tab as the sole edit surface. It already renders the registry's starting value, case, period, unit, limits, and gap status and posts the complete effective set to `/models/previews`. With Task 1's routes available, rebase, sensitivity, export, and download should stop entering their unavailable fallback.

Add a short visible note above the grid:

```tsx
<p className="model-sheet-authority" role="note">
  Historical and calculated cells are locked. Change forward inputs in Assumptions;
  previews recalculate forecast periods only.
</p>
```

Use the current CSS palette: a lock glyph/text marker plus border/typography differences, not color alone.

**Step 5: Verify the frontend**

```bash
cd caos/frontend
npm run test:unit
npx tsc --noEmit
npm run lint
```

Expected: all pass; no worksheet-cell mutation function exists.

**Step 6: Commit**

```bash
git add caos/frontend/src/components/model/modelBuilderState.ts caos/frontend/src/components/model/modelBuilderState.test.ts caos/frontend/src/components/model/ModelBuilder.tsx caos/frontend/src/components/model/ModelBuilder.test.ts caos/frontend/src/app/globals.css
git commit -m "feat: enforce forecast-only model worksheet interaction"
```

---

### Task 3: Define the canonical report document grammar

**Files:**

- Modify: `caos/server/caos/contracts.py:400-520`
- Modify: `caos/server/caos/responses.py:400-470`
- Create: `caos/server/caos/deliverables/document.py`
- Test: `caos/tests/spec/test_deliverables_spec.py`
- Test: `caos/tests/spec/test_http_contracts_spec.py`

**Step 1: Write a failing Full Credit composition test**

Use the existing deliverable fixture and accepted canonical artifacts. Save the required Full Credit blocks and assert:

```python
sections = revision["content"]["document_sections"]
assert revision["content"]["document_schema_version"] == "caos.deliverable.document.v1"
assert [section["section_id"] for section in sections] == [
    "credit_snapshot",
    "recommendation",
    "thesis_variant",
    "business_industry",
    "capital_structure",
    "base_downside_model",
    "liquidity_covenants",
    "risks_catalysts_falsifiers",
    "monitoring",
    "evidence_register",
]
assert sections[0]["origin"]["kind"] == "ARTIFACT"
assert sections[1]["editable"] is True
assert sections[5]["editable"] is False
```

Add a request-forgery assertion: an undeclared `document_sections` key in `DeliverableDraftRequest` returns 422 because `StrictModel` continues to forbid it.

**Step 2: Run focused tests and confirm the field is absent**

```bash
python -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_http_contracts_spec.py -q
```

Expected: composition assertions fail; existing request forgery is rejected.

**Step 3: Define one discriminated section union**

Add strict section models in `contracts.py`; every user-visible string uses `BoundaryText`:

```python
class DocumentOrigin(StrictModel):
    kind: Literal["ARTIFACT", "MODEL", "ANALYST", "SYSTEM"]
    authority_id: IdentifierItem
    block_ids: list[IdentifierItem] = Field(default_factory=list, max_length=500)


class DocumentSection(StrictModel):
    section_id: IdentifierItem
    title: BoundaryText
    page: BoundaryText
    editable: bool
    origin: DocumentOrigin


class DocumentTextSection(DocumentSection):
    kind: Literal["text"]
    body: BoundaryText


class DocumentProfileRow(StrictModel):
    label: BoundaryText
    value: BoundaryText


class DocumentProfileSection(DocumentSection):
    kind: Literal["profile"]
    rows: list[DocumentProfileRow] = Field(max_length=100)


class DocumentTableSection(DocumentSection):
    kind: Literal["table"]
    columns: list[BoundaryText] = Field(min_length=1, max_length=40)
    rows: list[list[BoundaryText]] = Field(max_length=500)
    note: BoundaryText | None = None


class DocumentListSection(DocumentSection):
    kind: Literal["list"]
    items: list[BoundaryText] = Field(max_length=200)


class DocumentChartSection(DocumentSection):
    kind: Literal["chart"]
    recipe: dict[str, Any]
    accessible_columns: list[BoundaryText]
    accessible_rows: list[list[BoundaryText]]


DocumentLeafSection = Annotated[
    DocumentTextSection
    | DocumentProfileSection
    | DocumentTableSection
    | DocumentListSection
    | DocumentChartSection,
    Field(discriminator="kind"),
]


class DocumentColumnsSection(DocumentSection):
    kind: Literal["columns"]
    items: list[list[DocumentLeafSection]] = Field(min_length=2, max_length=3)


CanonicalDocumentSection = Annotated[
    DocumentLeafSection | DocumentColumnsSection,
    Field(discriminator="kind"),
]
```

Use stringified, already-formatted values at this boundary so React, Markdown, PDF, and XLSX cannot disagree about number/unit formatting. Validate each table row width and forbid an editable section whose origin is not `ANALYST`.

**Step 4: Implement the deterministic composer**

Create `document.py` with one public function:

```python
DOCUMENT_SCHEMA_VERSION = "caos.deliverable.document.v1"


def compose_document(
    *,
    pathway: str,
    template: dict[str, Any],
    blocks: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    model: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if pathway != "FULL_CREDIT":
        return compose_template_document(template=template, blocks=blocks, model=model)
    return compose_full_credit(blocks=blocks, artifacts=artifacts, model=model)
```

`compose_full_credit` is an ordered recipe. It looks up canonical artifacts by module ID, reads explicit fields only, and uses the matching authored narrative block for editable text. Required missing values raise `DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:<identity>`. Optional gaps become a limitation row only where the recipe declares `optional=True`.

Use small module-level lookup/format helpers, not a framework or recipe language:

```python
def _required(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ValueError(
                "DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:" + ".".join(path)
            )
        value = value[key]
    return value
```

Read artifact records from the currently accepted snapshot by resolving its artifact refs through `engine.runs.get_artifact`; key them by `module_id`. Never inspect Markdown and never fall back to a different module.

Update `seed_accepted_authority_for_tests` to seed the minimal canonical artifact map used by deliverable-only tests, or pass that map explicitly through its existing test seam. Do not add an `engine is None` production bypass: the composer must behave the same in service and HTTP tests.

**Step 5: Attach sections to draft content**

In `DeliverableService.save_draft`, compose after block enrichment and model resolution:

```python
document_sections = compose_document(
    pathway=pathway,
    template=template,
    blocks=stored,
    artifacts=self._accepted_artifacts(case_id),
    model=model,
)
content = {
    "template_id": template["template_id"],
    "template_version": template["template_version"],
    "document_schema_version": DOCUMENT_SCHEMA_VERSION,
    "document_sections": document_sections,
    "model_selection": selection.model_dump(mode="json") if selection else None,
    "model_identity": identity,
    "blocks": stored,
    "generated_blocks": self._generated_blocks(stored, model),
}
```

Keep `generated_blocks` for compatibility during this slice. Remove it only after every consumer has moved and a separate migration decision approves the removal.

**Step 6: Recompose at freeze**

Before digesting/rendering, compose again from the stored blocks and current pinned identities and compare it to the revision's stored `document_sections`. Refuse `DELIVERABLE_COMPOSITION_MISMATCH` before creating any frozen record if they differ. Include the schema version and exact sections in the frozen payload.

**Step 7: Run focused tests**

Run the command from Step 2.

Expected: all pass, including forged input rejection and missing-required-value failure with no new revision/frozen record.

**Step 8: Commit**

```bash
git add caos/server/caos/contracts.py caos/server/caos/responses.py caos/server/caos/deliverables/document.py caos/server/caos/deliverables/service.py caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_http_contracts_spec.py
git commit -m "feat: compose governed deliverable document sections"
```

---

### Task 4: Render the canonical document with legacy report quality

**Files:**

- Create: `caos/frontend/src/components/report/documentTypes.ts`
- Replace: `caos/frontend/src/components/report/DeliverableDocument.tsx`
- Modify: `caos/frontend/src/components/report/ReportStudio.tsx:20-45,475-525`
- Modify: `caos/frontend/src/app/globals.css`
- Test: `caos/frontend/src/components/report/ReportStudio.test.ts`
- Create: `caos/frontend/src/components/report/DeliverableDocument.test.ts`

**Step 1: Write the failing document-shape test**

Test pure exports rather than brittle source-string matching:

```typescript
test("groups canonical sections into stable document pages", () => {
  assert.deepEqual(
    groupDocumentPages([
      section("snapshot", "Decision"),
      section("model", "Financials"),
      section("risk", "Decision"),
    ]).map((page) => [page.name, page.sections.map((item) => item.section_id)]),
    [["Decision", ["snapshot", "risk"]], ["Financials", ["model"]]],
  );
});

test("only analyst text sections are editable", () => {
  assert.equal(canEditDocumentSection(section("recommendation", "Decision", true, "ANALYST")), true);
  assert.equal(canEditDocumentSection(section("model", "Financials", false, "MODEL")), false);
});
```

**Step 2: Run the test and confirm the exports do not exist**

```bash
cd caos/frontend && npm run test:unit
```

**Step 3: Port the legacy presentation core, not its edit model**

Define TypeScript discriminated unions matching the server section grammar. Replace the current flattened `DeliverableDocument` renderer with the legacy renderer's useful pieces:

- `RDHead`, `RDTable`, `RDProfile`, `RDText`, `RDList`, `RDChart`, `RDCols`
- stable page grouping and mastheads
- sources/evidence register
- print/footer/watermark behavior
- semantic table headers and chart-accessible tables

Do not port the legacy `contentEditable` override map. `ReportStudio`'s textarea and existing `DeliverableBlock` updates remain the only authoring UI. The document preview receives sections and renders all of them read-only.

The root API is:

```tsx
export default function DeliverableDocument({
  title,
  issuer,
  status,
  version,
  digest,
  sections,
}: {
  title: string;
  issuer: string;
  status: string;
  version?: number;
  digest?: string;
  sections: DocumentSection[];
}) {
  const pages = groupDocumentPages(sections);
  return <article className="rd-paper">{/* masthead, pages, footer */}</article>;
}
```

**Step 4: Port only the required legacy CSS rules**

Copy the `rd-*` paper variables/rules used by the new component from the legacy `globals.css`, adapt them to the current design tokens, and keep current dark workspace framing. Do not copy unrelated Deep Research, chart library, or legacy model page rules.

**Step 5: Wire Report Studio to sections**

Extend `DraftRevision.content` and frozen payload types with `document_schema_version` and `document_sections`. Pass only `previewSections` to `DeliverableDocument`; retain `blocks` in the editor pane. Empty/older drafts may use the existing block preview through one compatibility adapter until reopened/saved, matching the no-migration decision.

**Step 6: Verify frontend behavior**

```bash
cd caos/frontend
npm run test:unit
npx tsc --noEmit
npm run lint
npm run build
```

Expected: all pass; required report tables retain `<th scope="row">`; generated sections have no editing event handler.

**Step 7: Commit**

```bash
git add caos/frontend/src/components/report/documentTypes.ts caos/frontend/src/components/report/DeliverableDocument.tsx caos/frontend/src/components/report/DeliverableDocument.test.ts caos/frontend/src/components/report/ReportStudio.tsx caos/frontend/src/components/report/ReportStudio.test.ts caos/frontend/src/app/globals.css
git commit -m "feat: restore committee-ready report document rendering"
```

---

### Task 5: Make every frozen export consume the same sections

**Files:**

- Modify: `caos/server/caos/publishing/renderers.py`
- Modify: `caos/server/caos/deliverables/service.py:450-535`
- Test: `caos/tests/spec/test_deliverables_spec.py:720-850`

**Step 1: Write a cross-format parity test**

Freeze the Full Credit revision and parse each existing export with the installed test libraries. Assert the same ordered section IDs/titles and representative governed values are present in Markdown, PDF, and XLSX:

```python
expected_titles = [section["title"] for section in frozen["payload"]["content"]["document_sections"]]
assert markdown_titles(md_bytes) == expected_titles
assert pdf_titles(pdf_bytes) == expected_titles
assert xlsx_titles(xlsx_bytes) == expected_titles
assert "FY2027" in md_bytes.decode()
assert "FY2027" in pdf_text(pdf_bytes)
assert "FY2027" in xlsx_cells(xlsx_bytes)
```

Also assert `render_frozen_export` never reads `generated_blocks` when `document_sections` exists.

**Step 2: Run the export tests and confirm drift**

```bash
python -m pytest caos/tests/spec/test_deliverables_spec.py -q
```

Expected: the new title/value parity assertions fail.

**Step 3: Centralize one section iterator**

Add a private iterator in `renderers.py` that yields semantic rows from the canonical union:

```python
def _section_rows(section: dict[str, Any]) -> list[list[str]]:
    if section["kind"] == "table":
        return [section["columns"], *section["rows"]]
    if section["kind"] == "profile":
        return [[row["label"], row["value"]] for row in section["rows"]]
    if section["kind"] == "list":
        return [[item] for item in section["items"]]
    if section["kind"] == "chart":
        return [section["accessible_columns"], *section["accessible_rows"]]
    if section["kind"] == "text":
        return [[section["body"]]]
    return []
```

Use it from Markdown, PDF, and XLSX renderers. Recurse through `columns` in document order. Keep format-specific layout code separate, but never re-derive content.

**Step 4: Version the renderer**

Increment the deliverable renderer version in the frozen payload. Older frozen/filed records continue to download their already-published immutable bytes.

**Step 5: Run export and full backend tests**

```bash
python -m pytest caos/tests/spec/test_deliverables_spec.py -q
python -m pytest caos/tests -q
ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
```

Expected: all pass.

**Step 6: Commit**

```bash
git add caos/server/caos/publishing/renderers.py caos/server/caos/deliverables/service.py caos/tests/spec/test_deliverables_spec.py
git commit -m "feat: render frozen exports from canonical document sections"
```

---

### Task 6: Reuse the grammar for the remaining pathways

**Files:**

- Modify: `caos/server/caos/deliverables/document.py`
- Create: `caos/tests/fixtures/deliverables/golden/*.json`
- Test: `caos/tests/spec/test_deliverables_spec.py`

**Step 1: Add one parameterized golden test**

For every `PATHWAY_TEMPLATES` member, compare section order, kind, page, editability, and stable field labels against a checked-in fixture. Values come from current canonical test artifacts, never legacy fixture data.

```python
@pytest.mark.parametrize("pathway", PATHWAY_TEMPLATES)
def test_document_recipe_matches_approved_structure(pathway: str, deliverable_case: Case) -> None:
    actual = structural_projection(deliverable_case.save(pathway)["content"]["document_sections"])
    expected = json.loads((GOLDEN_DIR / f"{pathway.lower()}.json").read_text())
    assert actual == expected
```

**Step 2: Run and confirm only Full Credit passes**

```bash
python -m pytest caos/tests/spec/test_deliverables_spec.py -q
```

**Step 3: Add direct pathway functions**

Add `compose_earnings_update`, `compose_covenant_refinancing`, `compose_relative_value`, `compose_distressed_restructuring`, and `compose_deep_research`. Each function returns the shared strict section union and uses the same `_required`, origin, model-table, citations, and formatting helpers. Do not introduce a generic recipe engine.

**Step 4: Verify all pathway goldens**

Run the command from Step 2, then the full backend suite and frontend unit/build commands from Tasks 4 and 5.

**Step 5: Commit**

```bash
git add caos/server/caos/deliverables/document.py caos/tests/fixtures/deliverables/golden caos/tests/spec/test_deliverables_spec.py
git commit -m "feat: compose every deliverable pathway as a governed document"
```

---

### Task 7: Prove the approved end-to-end journey and open the live preview

**Files:**

- Modify: `caos/frontend/scripts/workbench-smoke.mjs`
- Modify: `caos/frontend/scripts/a11y-axe.mjs`
- Test: `caos/frontend/src/components/model/ModelBuilder.test.ts`
- Test: `caos/frontend/src/components/report/ReportStudio.test.ts`

**Step 1: Extend the browser journey**

Against a retained deterministic fixture, cover:

1. Accept a Full Credit run.
2. Queue/run the application model build.
3. Open the worksheet and assert a historical source cell and calculated cell are visibly locked.
4. Change one READY forecast assumption through the assumption control.
5. Preview and assert historical values are unchanged while forward output changes.
6. Sign the analyst revision.
7. Open Report Studio and assert the signed revision is selected.
8. Save, freeze, file, and download the exact memo.
9. Assert the report preview contains the decision sections and the model revision identity.

Use accessible roles/labels rather than CSS selectors.

**Step 2: Run post-edit quality workflows**

Run `rewrite-tournament` in no-argument post-edit mode on every non-trivial function changed. Apply only behavior-preserving simplifications. Then run `confidence-review`, investigate every low-confidence point to root cause, patch confirmed problems, and repeat focused tests for any patched area.

**Step 3: Run the full verification matrix**

```bash
python -m pytest caos/tests -q
ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
cd caos/frontend
npm run lint
npx tsc --noEmit
npm run test:unit
npm run build
```

Start the combined application and run browser checks:

```bash
python caos/server/dev.py
CAOS_URL=http://127.0.0.1:8000 npm --prefix caos/frontend run a11y
CAOS_URL=http://127.0.0.1:8000 npm --prefix caos/frontend run test:workbench
```

Expected: all commands pass; the app serves `GET /api/health` with 200.

**Step 4: Open the live preview**

Open `http://127.0.0.1:8000/model/` and the Full Credit Report Studio route for the seeded case in the Codex browser panel. Verify the worksheet authority labels, forecast controls, report pages, tables, source register, and freeze state visually.

**Step 5: Commit the proof**

```bash
git add caos/frontend/scripts/workbench-smoke.mjs caos/frontend/scripts/a11y-axe.mjs caos/frontend/src/components/model/ModelBuilder.test.ts caos/frontend/src/components/report/ReportStudio.test.ts
git commit -m "test: prove governed builder journey"
```

## Completion Criteria

- All model endpoints used by `ModelBuilder.tsx` are served, authorized, and tested.
- Worksheet history and formulas have no mutation path; READY forecast registry rows are the only edit controls.
- Preview/sign-off tests prove history is invariant and forecast changes affect forward projections only.
- Every saved and frozen deliverable carries versioned canonical `document_sections` composed on the server.
- Browser preview and all frozen exports use the same ordered sections and governed values.
- Full Credit matches the approved legacy-quality document structure without legacy issuer fixtures.
- Remaining pathways reuse the same grammar and pass structural golden tests.
- Backend, frontend, accessibility, and workbench checks pass.
- A retained browser-test artifact records the Model Builder and Report Studio preview on the candidate.
