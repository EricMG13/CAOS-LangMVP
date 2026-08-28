# Workbench plan — one consolidated track

Date: 2026-08-27. Supersedes the separate handoffs in `DESIGN-IS-2026-08-27/04-handoff-prompt.md` and the Recommended Actions in `IMPECCABLE-CRITIQUE-2026-08-27.md`. Those two documents remain the evidence of record; **this is the only plan to execute.**

Merged inputs: the Rams audit (13/30, verdict REDESIGN, `#2 useful` scored 0) and the /impeccable critique (19/40, Poor band, 2×P0 + 2×P1). The two agreed: the visual system and accessibility floor are the product's strongest assets; the failures are the **analysis payoff** and the **truthfulness of the surface map**.

---

## Correction notice — read before anything else

Both audits were measured against this worktree's base, `45e9063`. That base is **stale**. Current truth is `main` (`91fea8f`) plus one newer pushed commit `6e35038` (branch `claude/frontend-docs-v0-1-0-88cc3d`). Re-verified by route table, source read, and a live run against `6e35038`:

| Audit finding | Status now | Evidence |
|---|---|---|
| Command Center double-404 (lens unserved) — half of critique P0 #2 | **ALREADY FIXED** | `GET /api/cases/{case_id}/lens` is served at `api/__init__.py:470`, present on `main` |
| Report Studio 404s on every visit — half of critique P0 #2 | **ALREADY FIXED** | `GET`/`PUT /deliverables/{pathway}/draft` served (`api/__init__.py:764,774`); `6e35038` repointed the client |
| Multi-driver scenarios unserved | **ALREADY FIXED** | `POST /models/scenarios` added by `6e35038` |
| "No citation chip can ever render" (all artifacts had empty `evidence_refs`) | **ALREADY FIXED — audit saw stale seed data** | `6e35038` changed `deterministic.py` `"evidence_refs": []` → `list(source_ids or [])`. **Verified by execution:** a fresh screen-depth run at `6e35038` returns `evidence_refs: ['src-3b4a…', 'src-137e…']` on all four artifacts |
| Model Builder crash | **STILL OPEN — root cause now exact** | Readiness lives at `GET /api/cases/{id}/model` (singular). `ModelBuilder.tsx:253` fetches `/models` (plural → `{"builds":[…]}` only) and dereferences `.readiness` at `:288`. Frontend-only fix |
| Inert DAG / no reader / blind accept | **STILL OPEN** | `Workspace.tsx:698`, `:504` unchanged at `6e35038` |
| Paused runs have no resume | **STILL OPEN** | Route served (`api/__init__.py:426`); zero "resume" hits in the frontend |
| Admin, research-plan approve, model worksheet, one-way sensitivity, rebase, revision export/download, build export | **STILL DEAD** | No route at `main` or `6e35038` |

**Three CLAUDE.md "Known gaps" entries are now stale** (lens, deliverables workspace, and the missing CI entrypoints — `run.py`, `worker.py`, `requirements*.txt`, `build_frontend.sh` all exist). Fixing that file is Phase 6.

**Branch guidance:** plan work targets `main` **after** `6e35038` merges (PR is open on `claude/frontend-docs-v0-1-0-88cc3d`). Do not start Phase 1 on this audit worktree — rebase onto the merged main first.

---

## Phase 0 — Discovery output (already performed; do not re-derive)

Two discovery agents read the tree at `6e35038`. Treat this section as the **Allowed APIs list**. Anything not here must be verified before use.

### Verified server contract (43 routes, all in `caos/server/caos/api/__init__.py`; no routers, no sub-apps)

**Artifact envelope** — `GET /api/cases/{case_id}/artifacts/{artifact_id}` → `ArtifactResponse` (`responses.py:198-208`):
`id, case_id, run_id, module_id, payload (Any), markdown (str|None), digest, input_fingerprint, created_by, created_at`.
There is **no `sections`/`narrative`/`citations` field on the envelope** — those live inside `payload`.

**Two mutually incompatible payload shapes under `payload`:**
- **Deterministic** `caos.system_analysis.v1` (`engine/deterministic.py:73-97`): `module_id, schema_version, status, summary, evidence_refs (list[str] of src-… ids), lineage{input_fingerprint, upstream_digests}, narrative{takeaway, basis, exceptions}, authority, confidence{band, qa_status}, provenance{executor, profile_id, selection_id}`. CP-3 adds `inputs.loan_universe.rows`.
- **Agent** `caos.canonical.artifact.v1` (`methodology/canonical.py:174-186` + `runtime.py:489-493`): `canonical_output{markdown, markdown_sha256}, evidence_refs (list of OBJECTS {source_id, block_id}), methodology, host_identity, host_confidence, source_set, upstream_artifacts`.

**Empirically confirmed (live run at `6e35038`, screen depth, EARNINGS_UPDATE):**
```
CP-PARSE  markdown=NULL  evidence_refs=['src-3b4a…','src-137e…']  summary='Source preparation: pinned source set parsed into typed bl…'
CP-0      markdown=NULL  evidence_refs=['src-3b4a…','src-137e…']  summary='Source readiness gate evaluated over the pinned source set…'
CP-L10    markdown=NULL  evidence_refs=['src-3b4a…','src-137e…']  summary='Financial change screen computed from pinned sources.'
CP-5      markdown=NULL  evidence_refs=['src-3b4a…','src-137e…']  summary='Evidence trace validation over upstream artifacts (determi…'
```
**Consequence that shapes Phase 2:** every module is deterministic at screen depth (`runtime.py:318`, `registry.py:19` — no `MODULES` entry overrides `mode_screen`), and the deterministic branch sets `markdown, qa_status = None, "Passed"` (`runtime.py:339`). **Narrative markdown exists only for agent runs at full depth** (9 modules: CP-1, CP-1A/B/C/D, CP-2, CP-2A, CP-2G, CP-5) with `AGENT_EXECUTION_ENABLED=true` + an API key. The reader must be designed for the deterministic payload first and degrade gracefully to markdown when present — not the reverse.

**`node.artifact_id` is already on the wire** (`api.ts:5`, `responses.py:113`) — a DAG tile can open its artifact with **no API change and no extra fetch**.

### Anti-patterns — APIs and assumptions that DO NOT exist

- `payload.visual` / `.freshness` / `.units` — declared in `api.ts:7`, **exists in neither server shape**. Dead field; do not build on it.
- `evidence_refs?: string[]` in `api.ts:7` is correct only for deterministic artifacts. Agent artifacts return objects; passing those to `EvidenceChip` (which takes `evidenceId: string`) renders `[object Object]`.
- `.tabular`, `.transition-caos`, `.caos-running`, `.caos-enter`, `<Panel>`, the tranche-colour ramp — named in `.impeccable.md:77-82` but **not defined in `globals.css`**. `globals.css` is ground truth.
- No route supplies the **incoming** snapshot digest before acceptance. `RunRecord` does not declare `accepted_snapshot_id` even though the server serves it (`responses.py:133`). See Phase 3's binding decision.
- `filedMarkdown.ts` + `FiledProof.tsx` are **not** the reader's missing half. Their grammar was reverse-engineered from `publishing/domain.py::render_markdown`, a different producer. Canonical markdown opens with `---` frontmatter that this parser has no rule for — every frontmatter line, delimiters included, would render as a visible paragraph. Do not revive it for the reader.
- `ModelBuilder.tsx` mocks `/models/{buildId}/worksheet` in the a11y fixture (`a11y-axe.mjs:121`) — a route that does not exist. A capability gate must be fixture-visible or that fixture will keep passing over a gated surface.

### Binding constraints (violating these breaks green tests or shipped rules)

1. **Dark Workspace Rule** — `DESIGN.md:275`: analytical surfaces stay dark; light/paper is reserved for filed output. `.impeccable.md:88-93`: the paper/appendix type scale "must not leak into workspace chrome or analytical UI." So a reader mounted on Run Console/Deep-Dive/Sources must not use `.paper*`, `.filed-*`, `.deliverable-paper-*`, `.report-citations`, `.report-generated-table`, or any `--caos-paper-*` token.
2. **One page-level primary action** — `DESIGN.md:348`. `/cases/` currently renders three (`Workspace.tsx:616-619, 688, 700`).
3. **Status never by colour alone** — `DESIGN.md:363`, `.impeccable.md:110-112`.
4. **Flat-until-floating** — `DESIGN.md:315`: panels get borders, not shadows; shadow means floating. Modal Shadow `0 24px 80px -24px rgba(0,0,0,0.9)` is specified at `DESIGN.md:309` and is **currently absent** from `globals.css`.
5. **Wire strictness** — adding a field to any response model requires editing the pinned key set in `caos/tests/spec/test_http_contracts_spec.py` (artifacts: `:133-144`) or the spec test fails.
6. **Source-text regex tests** — `ModelBuilder.test.ts` (9) and `ReportStudio.test.ts` (10) `readFileSync` the components and assert literal strings (e.g. `ReportStudio.test.ts:72` requires `Scenario registry unavailable` to be present). **Moving a string into a shared component silently breaks them**; update in lockstep.
7. **`api.test.ts:21-27`** pins `api()` rejecting with exactly `new Error("Case access denied")` for `{detail:"Case access denied"}` @403. Any error-idiom refactor must satisfy or update it.
8. **`workbench-smoke.mjs:634`** does `page.once("dialog", d => d.accept())` immediately before clicking accept — replacing `window.confirm` **will break this step** and it must be rewritten in the same commit.
9. **`workbench-smoke.mjs:333` and `:345`** assert `getByRole("button", {name: "Accept analytical snapshot"}).count() === 0` — the accept button's accessible name is load-bearing; renaming it breaks two assertions.
10. **`workbench-smoke.mjs:381-382`** locates `getByRole("heading", {name:"Evidence focus"}).locator("../..")` — that heading name and its two-ancestor DOM depth are load-bearing.
11. **Navigation guards cannot become `<dialog>`** — `Workspace.tsx:127,135,286` run inside `click`-capture and `popstate` listeners and must return synchronously; `guardUnload` (`:300-304`) uses `beforeunload`. **Only `Workspace.tsx:504` (accept) and arguably `ReportStudio.tsx:417` are safely convertible.**
12. **`a11y-axe.mjs:222`** prints a literal combination count (`routes:9, viewports:3, combinations:43…`); adding a route or viewport requires updating it.

---

## Phase 1 — Unblock Model Builder (smallest change, largest unblock)

**What to implement.** In `ModelBuilder.tsx`, replace the single inventory fetch with a merge of the two served routes. Today `:253` does `request<ModelInventory>('/api/cases/{id}/models')` and `:288-289` dereferences `.readiness`, but that route returns `{"builds": [...]}` only.

Copy the `Promise.all` fetch shape already used at `ModelBuilder.tsx:398-399`:
```ts
const [readiness, inventory] = await Promise.all([
  request<ModelReadiness>(`/api/cases/${caseId}/model`, {}, signal),
  request<{ builds: ModelBuild[] }>(`/api/cases/${caseId}/models`, {}, signal),
]);
const next: ModelInventory = { readiness, builds: inventory.builds };
```
Apply at both call sites: `:253` (`ApplicationModelBuild.refresh`) and `:391` (the main `refresh`). `readiness.build` is absent from `ModelReadinessResponse` but every consumer already falls back (`readiness.build || builds[0] || null`, `:255`, `:289`, `:393`), so no shape change is needed beyond the merge.

**Documentation references.** Route: `api/__init__.py` `GET /api/cases/{case_id}/model` → `wire.ModelReadinessResponse` (`responses.py:255-263`: `status, module_id, accepted_snapshot, source_set, requirements, calculation_runtime, worksheet_schema_version, blockers`). Consumers to satisfy: `ModelBuilder.tsx:255, 288-289, 331, 393, 411, 476-477, 704`.

**Verification checklist.**
- `curl -s $BASE/api/cases/$CID/model | python3 -m json.tool` returns the eight readiness fields (run this **first** — it is the one assumption this phase rests on).
- `/model-builder/?case=…` renders the authority panel instead of `role=alert`; grep the page for "Cannot read properties of undefined" → zero hits.
- `npx tsc --noEmit` clean; `npm run test:unit` green.
- `npm run a11y` still 0 violations.

**Anti-pattern guards.** Do **not** add `readiness` to the `/models` response — that is a wire-model change requiring a pinned-key-set edit (constraint 5) for a problem the client can fix. Do not silence the crash with deeper optional chaining; that would trade a visible error for a silently empty surface.

---

## Phase 2 — The artifact reader (P0; Rams #2, the 0-scored principle)

**What to implement.** A reader that renders a completed module's output, reachable in ≤2 clicks from a succeeded run, **before** acceptance.

Design for the deterministic payload (the only thing a keyless deployment produces): render `summary`, `narrative.takeaway`, `narrative.basis`, `narrative.exceptions` when non-empty, `status` + `authority` + `confidence.band` as a provenance line, `lineage.input_fingerprint` + `upstream_digests`, and `evidence_refs` as `EvidenceChip`s. When `markdown` is non-null (agent runs), render it as the body instead — **strip the `---` frontmatter first** (mirror `canonical.py:140-148`) and expect exactly six `##` sections (`canonical.py:24-31`).

Mount points, in dependency order:
1. **Make the DAG tile open its artifact.** Replace the inert `<div className="dag-node">` at `Workspace.tsx:698` with a `<button>` when `node.artifact_id` is present. `RunStatus` is shared by three call sites (`:713` InlineRun on Cases and Deep-Dive, `:758` RunConsole) — thread `caseId` (both callers already have it: `:708`, `:718`) and an `onOpenArtifact` callback.
2. **Extend the Deep-Dive artifact register** (`Workspace.tsx:821`) so each row opens the reader, not just the source rail.

**Documentation references / copy-ready.**
- Kind-dispatch renderer → copy the `renderBlock` if-chain from `DeliverableDocument.tsx:102-113`; swap `.deliverable-paper-section` → `.panel-body`/`.flow`, `.deliverable-paper-heading` → `.section-heading` (`globals.css:321-323`).
- Recursive object → accessible table → copy `flatten` + `displayValue` + `DataTable` from `DeliverableDocument.tsx:39-62`; use the bare `.table-wrap` + `table` at `globals.css:89-93`, **not** `.report-generated-table`.
- Provenance tag → copy the pattern at `DeliverableDocument.tsx:105` ("Evidence-bound" / "Analyst judgment"); the deterministic equivalents are `payload.authority` (`"SYSTEM_ANALYSIS"`) + `payload.confidence.band`.
- Citation chips wired to the drawer → copy `Workspace.tsx:673` (the `.evidence-list` fragment) plus `openEvidence` (`:646-655`), `sourceById` (`:644`), `activeEvidenceId` (`:645`). **`evidenceId` must be a source id present in `/api/cases/{id}/sources`** — the lookup is caller-side.
- Threading the drawer opener to a new view → `Workspace.tsx:562` (`setDrawer({kind:"evidence", evidenceId, source})`) + the `DrawerState` union at `WorkbenchShell.tsx:15-27`.
- Fact grid → `.state-facts` (`globals.css:196-198`) or `ModelBuilder.tsx:331`'s `<dl className="state-facts">`.
- Abort-safe artifact fetch → `Workspace.tsx:633-642`.
- Fix `ArtifactRecord` (`api.ts:7`) while here: drop `payload.visual`, type `evidence_refs` as `string[] | {source_id: string; block_id?: string}[]`, add `canonical_output`, `status`, `authority`, `confidence`, `lineage`, `provenance`.

**Verification checklist.**
- **Re-seed first** — any pre-`6e35038` database has empty `evidence_refs` and will make a correct reader look broken.
- From a succeeded run: DAG tile → reader shows CP-L10's summary, basis, provenance, and two evidence chips; clicking a chip opens the drawer at the right source.
- Keyboard-only: tile is focusable, Enter opens, chip is reachable, drawer traps and restores focus.
- `npm run a11y` 0 violations; `npm run test:workbench` no new failures; smoke's "Evidence focus" locator (constraint 10) still resolves.

**Anti-pattern guards.** Do not use paper CSS (constraint 1). Do not revive `filedMarkdown` for this. Do not add a server route or wire field — everything needed is already served. Do not assume markdown exists: at screen depth it is always `NULL`, so a markdown-first reader renders an empty box on the only runs a keyless deployment can produce.

---

## Phase 3 — Acceptance ceremony (P1; Rams #8, #5)

**What to implement.** Replace the `window.confirm` at `Workspace.tsx:504` with a styled `<dialog>` that shows what is being made authoritative, and give success a visible aftermath.

**Binding decision to make first (open constraint):** no route supplies the *incoming* snapshot digest pre-accept. Two options — pick one and record it:
- **(a) Frontend-only:** bind the dialog to `run.id`, `plan.pathway`, `plan.depth`, `plan.profile_id`, `plan.selection_id`, the module/`artifact_id` list, and the *outgoing* snapshot it replaces (`authority.accepted.digest`). Ships now, no wire change.
- **(b) Exact:** declare `accepted_snapshot_id` on `RunRecord` (`api.ts:5`) — the field is **already served** (`responses.py:133`, projected `api/__init__.py:340`), so this is a type-only change on the client, no server work and no pinned-key edit.

Recommended: **(b) then (a)** — take the already-served id, and fill the rest from the plan.

After success, the button must stop being a live primary action: the render condition at `Workspace.tsx:700` is `run.status === "succeeded"`, which stays true post-accept, so today it remains enabled and re-clickable. Swap it for an "Accepted — visible authority" state keyed on the accepted snapshot id.

**Copy-ready.** Dialog opened from state → `WorkbenchShell.tsx:103-116` (capture `document.activeElement` before `showModal()`, rAF-focus a `tabIndex={-1}` heading, `cancelAnimationFrame` cleanup) + `:97-101` (close with rAF focus restore) + `:360-375` (markup, `aria-labelledby`). Dialog opened from a handler → `WorkbenchShell.tsx:87-95` + `:284` (`onClose` resets and restores focus). CSS already exists: `globals.css:138-142` (`dialog`, `::backdrop`, width clamp, `.dialog-body`, `.dialog-body .panel-header`). Identity block → `dl.state-facts`.

**Verification checklist.**
- **Rewrite `workbench-smoke.mjs:634` in the same commit** (constraint 8) to click the new dialog's confirm control.
- Keep the accessible name "Accept analytical snapshot" (constraint 9) or update `:333` and `:345` together.
- Escape closes and returns focus to the trigger; the acceptance-race assertions at `:603-650` still pass.
- Post-accept: the primary button is gone/disabled and the new state names the accepted snapshot.
- Add a `workspaceAuthority.test.ts` case for any new `pendingAction` scope.

**Anti-pattern guards.** Do **not** convert the navigation guards at `Workspace.tsx:127,135,286` or `ReportStudio.tsx:417` — they must return synchronously (constraint 11), and five smoke assertions depend on native dialogs (`:976, :980, :986-988, :1274-1276, :1357`). Scope this phase to the accept confirm only.

---

## Phase 4 — Honest capability gating + resume (P0/P1; Rams #6)

**What to implement.**

*(a) Gate the nine confirmed-dead controls* behind the `unavailable` state that `DESIGN.md:350` already names. Copy the only existing implementation: `WorkbenchShell.tsx:176-180` (`<div className="state-block unavailable">` + `globals.css:121`).

| Dead route | Control to gate |
|---|---|
| `GET /api/admin/audit`, `/api/admin/bundle` | "Verify authority" (`Workspace.tsx:940`) — whole Admin Studio |
| `POST /api/runs/{id}/research-plan/approve` | "Approve research plan" (`Workspace.tsx:795`) |
| `GET /models/{build_id}/worksheet` | auto-fires on READY (`ModelBuilder.tsx:264`) — no control |
| `POST /models/sensitivities/one-way` | "Run one-way" (`ModelBuilder.tsx:718`) |
| `POST /model-revisions/rebase-preview` | "Rebase" (`:720`) and "Review and rebase local Draft" (`:706`) |
| `POST /model-revisions/{id}/export` | "Queue exact export" (`:720`) |
| `GET /model-revisions/{id}/download` | "Download exact XLSX" (`:720`) — the only control that 404s silently |
| `POST /models/{build_id}/export` | "Export XLSX" (`:332`) |

*(b) Surface resume.* `POST /api/runs/{run_id}/resume` (`api/__init__.py:426-429`) takes **no body**, requires case-member + `{ANALYST, APPROVER, ADMIN}`, and may legitimately no-op (`runtime.py:607-621`, §12.21) — so re-read the returned `status` rather than assuming it advanced. Render the control in the generic paused branch at `Workspace.tsx:703`, valid when `run.status === "paused"` and the code is neither `SOURCE_SET_EMPTY` (upload first) nor `PLAN_APPROVAL_REQUIRED` (gated by (a)). Mirror `acceptRun`'s guard/`requestContext`/`pendingAction`/`matchesAuthority` shape (`Workspace.tsx:499-519`). Give `SOURCE_SET_EMPTY` an "Open Sources" link.

*(c) Stop the remaining label lies.* Make the "LIVE" badge conditional and `aria-hidden` its span so the rail link stops announcing "RunLIVE" (`WorkbenchShell.tsx:249`). Replace the hardcoded `aria-label="QA unavailable — open QA status"` (`:271`) with state-derived text. Fix the "Pathway fit" chip that showed `NEEDS_SOURCE` beside a 2-source succeeded run. Fix the double `aria-current="page"` (`:236` vs `:246`).

**Verification checklist.** Every gated control is either absent or visibly `unavailable` with a reason — no control 404s on click. `a11y-axe.mjs:121` mocks the worksheet route: make the gate fixture-visible or that fixture will pass over a gated surface. Exactly one `aria-current="page"` per page. Resume advances a genuinely paused run, and a no-op resume leaves a truthful status.

**Anti-pattern guards.** Do not implement the missing server routes here — this phase makes the UI honest about what exists. Do not delete the surfaces; gate them, so they light up when routes land.

---

## Phase 5 — One error idiom, one vocabulary (Rams #4, #8)

**What to implement.**

*(a) One refusal component.* Reconcile the three divergent load/error primitives — `Workspace.tsx:591-603` (`EmptyState`/`LoadState`/`ActionState`), the near-duplicate `ModelBuilder.tsx:46-49` (no `empty` branch — it shows the error card even when `error` is `""`), and the inlined copy at `ReportStudio.tsx:421`. It must cover: three severities (`callout`, `callout warning`, `error`); two shapes (bordered container **and** bare inline paragraph); an optional `code.replaceAll("_"," ")` line; an action slot taking either a `Link` or a caller-supplied retry fn (`window.location.reload()` vs `load()` vs `refresh()`); selectable `role` (`alert` vs `status`+`aria-live=polite`); and the `unavailable` variant from Phase 4.

*(b) Never show a raw exception.* Lift `firstErrorMessage` (`ModelBuilder.tsx:229-235`) into `lib/api.ts` and route every catch through it. `api()` (`api.ts:26-33`) passes `body.detail` straight into `new Error()`, but several routes serve **object** details (`api/__init__.py:451`, `748-758`) and 422 serves an array — these currently stringify to `[object Object]`. ~40 sites currently do raw `caught.message`; ReportStudio has no unwrapper at all.

*(c) One vocabulary.* Human module names beside CP-* ids (the registry has them); humanize `PLAN_APPROVAL_REQUIRED` (`Workspace.tsx:758`) and `ANALYST_JUDGMENT` (`ReportStudio.tsx:430`) the way sibling code already does; remove "worker"/"Python" (`ModelBuilder.tsx:332`), "envelope" (`DeliverableDocument.tsx:80`), and CP-MODEL ×6 from analyst-facing copy; render `b00004 · {"line":4}` as "line 4" (`Workspace.tsx:674`); pick one product name ("CAOS — Credit Operating System" `layout.tsx:11` vs "Credit Agent OS" `WorkbenchShell.tsx:228`); collapse nav-label vs page-title double naming (`workbench.ts:53-58`); unify the two date formats; use one label for the upload action.

**Verification checklist.** `npm run test:unit` — expect `ModelBuilder.test.ts` / `ReportStudio.test.ts` source-regex breaks (constraint 6) and update them deliberately; keep `api.test.ts:21-27` green (constraint 7). Grep for `caught.message` reaching `setError`/`setMessage` → zero. No `[object Object]` for an object-detail refusal. Follow the `modelBuilderState.ts` + `.test.ts` pattern: extract the message logic to a testable module rather than a source-regex test.

**Anti-pattern guards.** Do not rename destinations without updating `routeDestinations` (`workbench.ts:1-11`), which feeds `generateStaticParams()` — and keep trailing slashes (`workbench.test.ts` pins them).

---

## Phase 6 — Weight, dead code, stale docs (Rams #9, #10)

- **Serve the export compressed.** 623 KB of JS goes over the wire uncompressed today (bare uvicorn sends no `content-encoding` even when the client advertises gzip/br). Highest-ratio single fix in the plan.
- **Drop dead payload:** the 112,594-byte `nomodule` legacy fallback referenced in every route's HTML, and the 14,377-byte chunk nothing references.
- **Delete `FiledProof.tsx` + `filedMarkdown.ts`** (82 lines, zero importers) — Phase 0 established they are not the reader's missing half. Keep `filedMarkdown.test.ts`'s hardening cases as the reference if a parser is ever needed. Also remove the 12 zero-consumer exports and the duplicate `AuthorityStatus` declaration (`workspaceAuthority.ts:1` vs `WorkbenchShell.tsx:29`).
- **Collapse the tripled run console** to one home, satisfying `DESIGN.md:348` (one primary action per page) on `/cases/`.
- **Fix the polish defects:** flush panel-header padding (detector-confirmed, `globals.css` panel-header), the 0px gap above "Accept analytical snapshot", the browser-default 14.04px heading and `-webkit-center` caption in Deep-Dive's Artifact register, `not-found.tsx:4`'s missing trailing slash and dropped case context, and the 404 page's stale `h1 "Cases"` + default tab title.
- **Update `CLAUDE.md`'s "Known gaps"** — the lens, deliverables-workspace, and CI-entrypoint entries are stale (Correction notice). Leave the genuinely-still-dead routes listed.
- **Do not** add motion to satisfy `DESIGN.md`'s "running pulse" language: there are zero `@keyframes` in the tree today and the reduced-motion guards currently protect nothing. If a live-run pulse is wanted, it is a deliberate scope decision, not cleanup.

---

## Phase 7 — Final verification

Run against the combined build (static export served by FastAPI) — **not** `next dev`; `a11y-axe.mjs:1-5` warns the pending-plan fixture only behaves correctly against the combined app.

```bash
npm run lint --prefix caos/frontend && npx tsc --noEmit -p caos/frontend
```
```bash
npm run test:unit --prefix caos/frontend && npm run build --prefix caos/frontend
```
```bash
CAOS_URL=http://127.0.0.1:8000 npm run a11y --prefix caos/frontend
```
```bash
npm run test:workbench --prefix caos/frontend
```
```bash
python -m pytest caos/tests -q
```

Acceptance criteria:
1. `a11y` reports **0 violations** across 9 routes × 3 viewports plus the three fixtures; update the printed combination literal (`a11y-axe.mjs:222`) only if routes/viewports actually changed.
2. `test:workbench` has **no new** failures; the accept step passes against the styled dialog. (CLAUDE.md records the Report Studio scenario-exhibit step as a known red — confirm whether `6e35038` cleared it rather than assuming either way.)
3. Grep gates: zero `caught.message` reaching a user-visible setter; zero `[object Object]`; zero controls calling a route absent from the 43-route table; exactly one `aria-current="page"` per page.
4. Manual, on a **freshly seeded** database: succeeded run → open a module's output → read summary/basis/provenance → click a citation → land on the cited source → then accept, via a dialog naming what is bound → see an acknowledged accepted state.
5. Re-run `/impeccable critique` and the Rams scorecard. Targets: `#2 useful` off 0 (the redesign trigger), total ≥ 20/30, critique ≥ 28/40.

---

## Sequencing and effort

| Phase | Blocks | Rough size | Principle moved |
|---|---|---|---|
| 1 Model Builder seam | nothing | ~10 lines | #2, #8 |
| 2 Artifact reader | Phase 3 | largest | **#2 (the 0)**, #4 |
| 3 Acceptance ceremony | — | medium | #8, #5, #1 |
| 4 Gating + resume | — | medium | **#6**, #3 |
| 5 Error idiom + vocabulary | — | medium, wide blast radius | #4, #8 |
| 6 Weight + dead code + docs | — | small | #9, #10 |
| 7 Verification | — | — | all |

Phases 1, 4, 5, 6 are independent and parallelizable. Phase 3 depends on Phase 2 (acceptance moves to the end of the reading flow). Land each as its own commit with its verification evidence, per the repo's isolated-commit convention.
