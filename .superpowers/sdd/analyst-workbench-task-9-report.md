# Analyst Workbench Task9 — frozen chart exports

Date:2026-09-07. Scope base:`85859f37fdee0353fc23de48473e68a7b39674ed`, branch`codex/analyst-workbench-capabilities`. Tasks0–8 retained; Task10 not advanced. This is implementation evidence for independent review, not live analytical qualification.

## Delivered

New freezes record`caos.deliverable-renderer.v4`, independent of template version. Recorded v4 renders the exact frozen publication's closed line/bar/stacked_bar/scatter recipes through existing pypdf vector content streams and pinned Pango labels, native openpyxl charts with canonical numeric helper cells and exact equivalent tables, and explicit Markdown text/table representation. No provider/model call, live model read, browser worker, SVG parser, new dependency, vendor or methodology edit was introduced. Frontend G2 remains unchanged at5.4.8.

Absent/historical renderer markers preserve old interpretation, including historical field recipes labelled`caos.chart.v1`. Queued v3 workers and rebuilt exports dispatch recorded identity, not the current default. Existing stored bytes are served unchanged. The six historical v1 fixtures explicitly freeze under v3; none of their18 golden files changed. Separate v4 chart goldens retain renderer identity and complete chart OOXML settings/references/cells.

Full DocumentChartSection/ChartRecipe validation and exact accessible-table equality precede drawing. Charts use canonical`y`/`x_value`, never parsed display text. Values outside finite Excel range or15-significant-digit precision fall back explicitly to the exact table; repeated/inconsistently ordered categories likewise retain a table without inventing geometry. Formula-looking accessible values remain exact OOXML text, while metadata is escaped through existing safe-cell handling. Signs, zeros, sparse series gaps and independent signed stacks are preserved.

PDF reservations are indivisible240pt blocks in existing measured pagination. V4 measures the absolute reservation, retains legends with plots, repeats table headers only at page boundaries, aligns labels to coordinates, and preserves the underlaid approval watermark. Final v4 Pango shaping uses its measured natural height: fixed-height final shaping was proven to drop trailing legend lines despite a fitting measurement. Legacy v3 shaping is unchanged. Native charts explicitly disable smoothing/connecting scatter, set negative-bar inversion off, place category ticks below plots, keep zero visible for one-sided bars, and retain full chart titles independently of Excel's31-character sheet-name bound.

New Control register sections partition all supplied source/evidence rows into<=500-row tables rather than truncating them. Task7's complete citation_union→payload.evidence→offline verifier path remains untouched. Task8 model/overlay/ancestry authority is unchanged.

## Qualification seams

- New v2 service test saves reviewed sections, freezes, exports MD/PDF/XLSX, files, withdraws a source and changes the default renderer; exact retained bytes, reviewed sections, selected model identity and full generated+analyst citation union remain identical. This uses seeded model records and an accepted-artifact retrieval seam with valid fixture tables, not an actual accepted v2 analytical journey.
- Existing actual accepted Distressed v1 publication test now compares all three retained export byte strings after withdrawal instead of MD only. Its isolated final test result is recorded below.
- Task10 still owes actual accepted v2 incremental journey/freeze/export integration and the complete final-state mixed acceptance gate. No live-provider or real-case qualification is claimed.

## Tests and attribution

Commands use`caos/server/.venv314/bin/python -m pytest` from this worktree. Logs below are retained under ignored`qa/evidence/task9/`.

| Check | Exact result | Evidence |
|---|---|---|
| Initial chart TDD |8failed/1passed, then4failed/5passed (missing drawings/fallback, then exact-text apostrophe) | focused development output and new regression tests |
| Sparse/closed/hostile/zero cases |10passed,11deselected,6.55s | development focused run |
| Control register/reservations |2passed,21deselected,1warning,2.71s | focused development run |
| Initial publication/golden/audit/deliverables suite |194passed/2failed,1warning,456.05s |`publication-baseline-check.log` |
| Six layout assertions after attribution |6passed,134deselected,1warning,0.66s |`task8-fixture-correction.log` |
| Approved separate v4 golden regeneration |1passed,22deselected,2.77s |`golden-regeneration.log` |
| Post-tournament chart/service suite |23passed,1warning,37.75s |`owner-winner-tests.log` |
| Full seeded legend regression before remedy |1failed,22deselected,1warning,25.99s; missing rcf/term-loan/notes |`legend-failure.log` |
| One-sided/all-zero baseline and full-title regressions before remedy |6failed |`native-baseline-red.log` |
| Final post-remedy chart/service suite |29passed,1warning,38.51s |`complete-fix-tests.log` |
| Final historical v1/v3 golden suite |9passed,1warning,57.16s |`historical-goldens-final.log` |
| Verifier bounds standalone |6passed,0.21s |`verifier-bounds.log` |
| Final root audit regressions + verifier bounds |10passed,4.53s |`root-gate-final.log` |
| Actual accepted Distress v1 retained MD/PDF/XLSX after withdrawal |1passed,30deselected,1warning,35.09s |`accepted-distress-retention-final.log` |
| Final isolated source-complete modelling suite |31passed,1warning,330.88s |`source-complete-isolated.log` |
| Pre-final-remedy broad gate |699passed/24failed,1warning,505.88s |`final-gate.log` |

The broad gate explicitly ran publication_spec, publication_goldens_spec, publication_charts_spec, audit_package_spec, deliverables_spec, module_presentation_spec, test_audit_regressions and source_complete_modelling_spec in that order. It imported renderer code before the final natural-height/axis/title remedies and is NOT complete final-code verification. Publication/freeze/filing/union/compatibility checks passed there; final focused checks cover the later remedies.

Two original layout failures were Task8-base fixture drift: RelativeValue/DeepResearch supplied a selected model but expected5 logical pages, omitting Task8's MODEL-owned 'Selected model and pathway effects' page. The compose_document code SHA was`5636a57d39dd86db25c50ca697d9a403607aea9dfa8dbf71b548addfe6daf45a` both at base and current. Counts are now6 with an explicit substantive page assertion; no model logic changed.

The24 broad failures were investigated, not suppressed.23 source-complete failures came from pytest fixture resolution: spec/root/spec path ordering resolves later spec settings to parent`caos/tests/conftest.py:17` (execution disabled), while root-first/separate invocation resolves`spec/conftest.py:39` (enabled). `minimal-mixed-fixtures.log`, `full-mixed-fixtures.log` and `mixed-fixtures.log` reproduce this using`--fixtures-per-test` without execution. `root-first-full-fixtures.log` verifies the full reordered command also resolves the correct spec fixture. Task10 must put both root-level paths before all spec paths or use separate invocations; production execution authority was not relaxed. The final isolated31-case source-complete suite passes on current production code.

The remaining audit retry fixture selected the Task7 new default v2 without required accepted report artifacts and failed at signoff before renderer invocation. Its file SHA was`7507f11a02701fbf647b6321ea0b77189bb67f184bb2374aea41c577ad1e2f11` at Task9 base and before correction. It now explicitly selects historical v1, preserving all original time-boundary/retry/identity assertions. This is Task7-default fixture drift, not a renderer defect or remote-main attribution. Isolated red evidence:`audit-retry-isolated.log`.

Only recurring test warning: StarletteDeprecationWarning for httpx with testclient (recommends httpx2); no dependency change. Installed LibreOffice read-only conversion exited0 with benign macOS 'Task policy set failed:4' diagnostic. Ruff final scoped check is clean. Staged diff-check reports five trailing spaces in the new generated Markdown golden's empty revision metadata lines73–75/77–78; these are exact existing renderer output and intentionally retained, not trimmed or normalized. All other staged paths pass diff-check.

## Visual/export evidence

All paths below are relative to this worktree, intentionally ignored scratch, and retained for review. Full [export inventory](../../qa/evidence/task9/export-inventory.json) records hashes, all42 PDF page/chart/legend counts and all26 XLSX sheet titles/dimensions/chart metadata. [Owner visual review](../../qa/evidence/task9/visual-owner-review.md) records every page/sheet group and findings.

Pure four-kind fixture: final`qa/evidence/task9/visual-complete/reviewed-charts.{md,pdf,xlsx}`, PDF rasters`complete-fixture-pages/page-1.png` through4, native rasters`lo-render-final/sheet-1.png` through7. Root independently reviewed all final PDF pages and all native sheets. Final geometry approval on2026-09-07 followed actual raster review, not text extraction. PDF SHA`d7e3bd28d361d82afc656287097611f8c97b9191ce7324f601d05c987fcdd9e3`; XLSX SHA`d86d6237e51f6d4b6f917c9edd1a06b957719e811dd1263628a77024fd129651`. Prior approved PDF SHA`146cf0556220c1560de17d56fff73e8f32456838fe53d0b38e2eba6919be7fb4` changed only after natural-height correction and was reviewed afresh. Current text/XML goldens are unchanged by that remedy and pass without regeneration.

Seeded v2 export: final`visual-complete/v2-frozen.{md,pdf,xlsx}` and full payload JSON; PDF SHA`968c0c8b8b33cd2be066626562dd44027a921f86bbd3c1d73bd149ce6b32ca92`; XLSX SHA`8982f393f4f2d42056fa82767773db33fcd6c594aa7f5db5101ed0d50d3e6e5e`, identical before/after LibreOffice conversion.42 PDF pages at`complete-pages/page-01.png` through42,26 native sheets at`lo-render-complete/sheet-01.png` through26. Owner reviewed all through seven PDF/five XLSX contact sheets plus detailed chart/carry samples. Root independently reviewed chart pages31/32/33/34/38/40 and surrounding30/35/39/41/42; refreshed38/39/41/42 closed the legend defect. Native chart sheets7Revenue,8Ebitda,9CfoNcfo,10Adjustments,12Debt maturities,18Composite Score were independently checked; refreshed12/18 closed title/baseline issues. Dense native registers require normal workbook zoom; SinglePageSheets conversion is inspection evidence, not a redesigned print layout.

Failed attempts remain in`visual`, `lo-render`, `lo-render-v3`, `legend-failure`, `visual-owner` and original full-v2 rasters. Native root cause probes show invertIfNegative=False alone repairs signed bars, while axes autoZero alone does not. Every corrected chart retains exact adjacent table/source values, no hidden formula execution, and no provider access.

## Mandatory review workflows

Ponytail full: reused existing frozen renderer, paginator/font bundle, deterministic ZIP, contracts and openpyxl primitives; skipped new chart service, browser runtime, dependency and provider/model work. Impeccable/project guidance was inspected; this backend task reused the existing paper palette and literal chart style. PDF skill was used for read-only raster inspection; requested existing implementation/output paths took precedence over standalone artifact authoring defaults.

[Confidence review](../../qa/evidence/task9/confidence-review.md) ranks10 doubts, traces confirmed native defaults/PDF clipping/carry/safety/register/test-fixture issues to root causes, and separates verified behavior, explicit fallback and open qualification limits.

No-argument rewrite tournament selected the two material helpers`vector_chart` and`add_xlsx_chart`; other changed functions were bounded out and covered by confidence review. Fresh own roles task9_incumbent/speed/memory/readability/arbiter were separate from root/independent reviewer, with at most2 concurrently. Full ignored candidate files, advocacy, anonymous A–D snippets, bracket, runnable differential checks and owner verification are retained and linked from [tournament owner verification](../../qa/evidence/task9/tournament-owner-verification.md). Winner C(Readability): ordered indices, explicit endpoints/native branches. Owner applied via apply_patch, personally re-read callers/diff, verified48 differential recipes' vector/labels/callbacks/all ZIP members and ran23 focused checks. Later correctness deltas and29 post-remedy checks are explicitly distinguished there; no benchmark is claimed as product performance. The [final arbiter addendum](../../qa/evidence/task9/tournament-arbiter-final.md), read personally by owner, reapplies the shared required title/baseline contract to all candidates and confirms B>A, C>B, C>D; no materially simpler equivalent correction was justified.

No credentials, real cases, paid providers, external writes, push, PR, merge or deployment were used. Independent final review and Task10 complete integration remain outstanding.
