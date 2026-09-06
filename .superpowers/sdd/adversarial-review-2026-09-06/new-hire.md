# THE NEW HIRE — adversarial review of CAOS (maintainability, naming, conventions)
(Saved by the parent from the sub-agent's final message; the sub-agent's own write was refused by its sandbox.)

Tree reviewed: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/fe-followup` at `18dccbb` (FE-G4), read-only. Counts: 0 CRITICAL, 11 WARNING (N1–N11), 6 NOTE (N12–N17).

## Part 1 — the three traces

(a) "Add a field to the case wire and show it on Credit" — 9 files opened, lost twice: `responses.py:81` → `api/__init__.py:362–392` (`_wire_case` spreads `**case`) → `storage/store.py:49–60,574` → `test_http_contracts_spec.py:78–96` → `frontend/src/lib/api.ts:1` → `workbench.ts:85–107` → `Workspace.tsx:1109,1849` (`CommandView` reads issuer/sector from `/lens`, not the case) → `responses.py:113` → `api/__init__.py:818`.
(b) "A module refuses with a new typed code — make Run show it" — 10 files, lost three times: codes are string literals in five server files; `RunResponse.error` is `Any`; the frontend renders `run.error.message || "Run exception"`, `message` exists only for `PLAN_APPROVAL_REQUIRED`.
(c) "Change how a freeze renders the PDF" — 8 files, one trap: the renderer version `caos.deliverable-renderer.v3` is a literal in `deliverables/service.py:960`, not in `renderers.py`; the goldens test self-approves a missing golden.

## Part 2 — findings

N1 · WARNING · `api/__init__.py:904–905`, `:1242–1250`, `:584`, `:1038` — typed refusals are `ValueError` string prefixes; HTTP status chosen by substring (`409 if "CONFLICT" in code or "STALE" in code else 422`). `models/service.py` 44 `raise ValueError(`, 13 with a `CODE:` prefix; `deliverables/service.py` 65/46. Fix: one `TypedRefusal(ValueError)` with `code` and `status`.
N2 · WARNING · `responses.py:163,187` + `frontend/src/lib/api.ts:13` + `Workspace.tsx:1243,1572` — run failure shape is `Any` on the wire; the frontend declares `{code?, message?}`, never renders `module_id`, and shows `<CODE>: Run exception` while Portfolio copy promises "which module refused and why". Fix: `RunErrorResponse(code, module_id, message | None)`.
N3 · WARNING (borders CRITICAL) · `caos/tests/spec/test_publication_goldens_spec.py:288–291` — `if REGENERATE or not path.exists(): path.write_text(text)` then compare: a missing golden is created from the current render and passes uninspected; nothing pins the file set. Fix: `assert path.exists() or REGENERATE`; pin `STATES × formats`.
N4 · WARNING · `deliverables/service.py:960` vs `publishing/renderers.py` — renderer version literal lives in the service; a renderer change regenerates goldens without a version bump, so two deployments render different bytes under the same `v3`. Fix: `RENDERER_VERSION` in `renderers.py`.
N5 · WARNING · `api/__init__.py:378` — `_wire_case` returns `{**case, …}`: any new `cases` column reaches `extra="forbid"` → 500 on every case route, three files away from the cause. Fix: explicit projection.
N6 · WARNING · `Workspace.tsx:1849–1850` — Credit ignores the `CaseRecord` it renders and fetches `/lens` into an inline anonymous type; `CaseLensResponse` is absent from `KEY_SETS`. Fix: pass `selectedCase`; a named `CaseLens` type.
N7 · WARNING · `ModelBuilder.test.ts`, `ReportStudio.test.ts`, `workbench.test.ts` — source-regex tests pin identifiers, literals (`setTimeout(poll, 1500)`, `/850/`, `rows={8}`), inline style text and the smoke's own source; refactors fail them, behaviour breaks pass. Fix: pin served contract strings and `data-*` hooks only.
N8 · WARNING · `engine/runtime.py` (28), `models/service.py` (19), `deliverables/service.py` (16), `storage/store.py` (7) — 76 `_for_tests` methods and a fixture-reading path (`parents[3]/"tests"/"fixtures"/"cp_model"`) on production classes. Fix: test seams in `caos/tests/seams.py` or one mixin; inject the fixture dir.
N9 · WARNING · `config.py:29–58` vs `:60–95` — every default exists twice (dataclass and `os.getenv(NAME, "<literal>")`, 20 of them); only the dataclass copy is pinned. Fix: `from_env` passes only set values.
N10 · WARNING · `Workspace.tsx:901`, `WorkbenchShell.tsx:251,256`, `Workspace.tsx:1314`, `ModelBuilder.tsx:510,512` — client ceilings are bare literals (brief bounds `10/10/10/200` in UTF-16 units vs server NFC code points; drawer cap `20` after a cited-first sort so "Showing the first 20 blocks" is wrong and >20 cited blocks are dropped unlabelled; `maxRows = 80`; `1500` polls). Fix: name every cap; show all cited blocks, cap only the uncited remainder.
N11 · WARNING · `README.md:16–22` — describes four MVP pathways and deterministic screen executors; runtime has six and screen depth is provider-backed (DECISIONS §14.1, §14.12). Fix: rewrite from `startable_routes()`.
N12 · NOTE · `CLAUDE.md:55–60` says six `OpenWireModel` envelopes; `responses.py` has eleven.
N13 · NOTE · `CLAUDE.md:165–170` names `mode` and `aliases`; `ModuleSpec` has `mode_full`/`mode_screen` (both `"agent"`), aliases live in `_ALIASES`; `calculators`/`derived_projections`/`source_mode`/`plan_approval` omitted; a stale "recorded 2026-09-01" comment on `GOLDEN_AUTHORITY_DIGESTS`.
N14 · NOTE · `Workspace.tsx:1517` "Drop documents on **Cases**" (pinned by `workbench-smoke.mjs:451`); `workbench.ts:130–135` comment says CP-PARSE has no slug and CP-DR is not in the registry — both false, so Run labels the Deep Research node "CP-DR"; `responses.py:73` "Cases screen"; `workbench.ts:103` "Cases page"; `test_http_contracts_spec.py:7–10` boilerplate "FAILS today".
N15 · NOTE · `CLAUDE.md:151–154` "seven log points" vs 17 distinct event names; `worker.py:37–41` docstring order (builds, exports, freezes) vs code (freezes first).
N16 · NOTE · one act, four names: `/approve` route, `FileDeliverableRequest`, `approve_filing`, `deliverable.filed`; CONTEXT.md's avoid-list includes "Approval". Also `GET …/model` (readiness) beside `/models` (builds).
N17 · NOTE · `Any`-typed seams: `IntakeService(store: Any, engine: Any, settings: Any)`, `ModelService(engine: Any)`, `Engine(provider: Any)`, five `_*_effect` methods with seven untyped positionals, `plan: Any`, `data: Any` on the run wire.

## Part 3 — coverage: read and found clear
`observability.py`; `engine/loop.py`; `engine/budget.py` (Appendix A literals match §14.7); `lib/workbench.ts` route tables, `app/[destination]/page.tsx`, `RouteForwarder.tsx`; `states.tsx`, `api.ts`; `workspaceAuthority.ts`; `config.py` placeholder rejection; `intake/service.py` `_NEXT_ACTIONS`; `sources/classify.py`; `_wire_source`; `control-capability-map.md` matches the route list; DECISIONS §14.

## Part 4 — commands run
Reads via `cat`/`sed -n`/`grep` across the files above; `grep -rc 'def [a-z_]*_for_tests'`; `grep -rhoE 'log_event\("[a-z_.]+"'`; Python scripts counting `raise ValueError(` prefixes and comparing `Settings` defaults with `from_env` literals; `npm run test:unit` → 141 pass, 268.8 ms; `pytest test_http_contracts_spec.py::test_family_models_reject_an_injected_unknown_top_level_key test_limits_spec.py::test_declared_enterprise_ceilings_are_the_configured_defaults` → 10 passed.
