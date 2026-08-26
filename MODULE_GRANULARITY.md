# Module Granularity Record

Decision date: 2026-08-26 (phase 1). Sources: Deploy V catalog `CREDIT_OS_V_MODULE_CATALOG_v2.json` (`superseded_module_ids`), `DEPLOY_V_MANIFEST.json` (41 logical = 22 physical + 19 aliases), and the pre-consolidation corpus `Modular OS/` (seeded in this repo, identical to legacy).

**The call: register nodes at live-module granularity; split none of the 19 absorbed IDs.** Every superseded ID resolves through the registry alias map, so both forms address the same node. Registration is data (`modules/registry.py`): a later split is a registry change — add an entry, point the alias at it, declare its edges — not a graph-code change.

Why no splits: the test for a split is a *named graph property purchased* (independent parallel branch, distinct checkpoint/retry unit, separate human gate, separate evidence ownership) plus a *stated* output contract. No absorbed ID passes both. The route DAGs already expose all the parallelism the catalog declares at live granularity; no absorbed phase carries its own human gate; evidence ownership is per live artifact envelope. And where ancestor contracts exist they conflict with Deploy V naming (documented below) — Deploy V wins, so a split node would need a Deploy-V-conformant phase contract that the catalog does not state (`artifact_contract` is per live module). Deriving one would be inventing methodology.

Two structural notes that are *not* splits:
- **CP-PARSE** runs as its own stage-0 route node because `bundle.compile()` already emits it that way in every compiled route (host-prepended, `cp0_requires: CP-PARSE_DIGEST`). Preserved, not split.
- **CP-2B** is emitted as a deterministic projection derived from CP-2A at completion time (legacy `project_cp2b`), digest-chained to its parent and consumed by CP-MODEL's bundle validation. Kept exactly as legacy: a derived artifact declared on CP-2A's registry entry, not a node.

## The 19 absorbed IDs

| Absorbed | Live parent (transitive) | Ancestor in Modular OS/ | Split? | Reason |
|---|---|---|---|---|
| CP-1E | CP-1D | no | no | No stated contract anywhere; CP-1D itself has no ancestor folder. |
| CP-2B | CP-2A | yes (T2B.1–9, downside pathway register) | no | Already materialised as CP-2A's derived projection artifact with a parent-digest chain (legacy semantics kept); promoting it to a node buys no checkpoint value for a deterministic in-process derivation. Ancestor's CP-2B-prefixed namespaces and deps (CP-5B/CP-RENDER) conflict with Deploy V — Deploy V wins. |
| CP-2C | CP-1A | yes (event/catalyst register — but tables numbered T5.x, colliding with the 5-series) | no | Cross-family absorption (2-series event module into the CP-1A fact pack) with a table-ID scheme Deploy V's CP-1A contract does not carry; no graph property purchased. |
| CP-2D | CP-2G | yes (governance/sponsor score T2D.1–11) | no | Three-way naming drift: legacy CP-2G was ESG, Deploy V cp-2g is forward-credit-model, ancestor CP-2D is governance — the ancestor contract cannot be reconciled to a Deploy V phase without invention. Deploy V wins. |
| CP-2F | CP-2E | yes (macro/FX/hedging T2F.1–9) | no | Deploy V's physical CP-2E *kept CP-2E's ID but carries CP-2F's name* (legacy CP-2E was the liquidity module). The live module already IS the ancestor's content under the parent ID; nothing to separate. |
| CP-3A | CP-3 | no | no | No stated contract (no ancestor folder). |
| CP-3B | CP-3 | yes (recovery/instrument preference T3B.*, numbering skips T3B.9) | no | Ancestor upstream edges cross three consolidated parents (CP-4C, CP-4D, CP-3D as then named) and it is FULL_INPUTS_ONLY/non-executable in LITE; CP-3 runs deterministically in MVP, so a split buys no retry or parallel unit. |
| CP-3C | CP-4C | yes (portfolio fit/sizing T3C.*) | no | Semantic mismatch documented: ancestor is portfolio sizing, Deploy V cp-4c is restructuring-fulcrum, legacy CP-4C was covenant capacity. Unreconcilable without invention; Deploy V wins. |
| CP-3D | CP-2H | yes (refinancing/LME risk T3D.*, `cp3d_*` records) | no | Parent CP-2H has no ancestor contract of its own anywhere, so the phase boundary inside it is unstated; CP-2H is deterministic in MVP. |
| CP-4A | CP-4 | no | no | No stated contract. |
| CP-4B | CP-4 | no | no | No stated contract; exists only as the chain hop for CP-4D. |
| CP-4D | CP-4 (via CP-4B) | yes (restricted group / guarantee map T4D.1–8, owns `structural_priority_map`) | no | Only PROPOSED-status ancestor schema, only dual-export (docx + md handoff) contract, and a documented CP-3B↔CP-4D ordering conflict — the divergence line this file owes: **ancestor says CP-3B consumes CP-4D's `structural_priority_map` yet runs before it; Deploy V resolves this by absorbing both into parents whose route order (CP-3 → CP-4 → CP-4C) inverts the ancestor edge. Deploy V wins.** |
| CP-5A | CP-5 | no | no | No stated contract. |
| CP-6A | CP-6 | yes (IC debate, T6A.*; the sole documented ancestor of CP-6) | no | CP-6 is out of MVP routes (DISTRESSED/PORTFOLIO cut) and non-executable in LITE; no property purchased. Note: legacy corpus has no CP-6 folder — if CP-6 is ever wired for agent execution, CP-6A's ancestor text is the closest stated contract, with Deploy V's CP-6 `artifact_contract` (T6A.4/6/7/11 + T6E.4/6/7/11) governing. |
| CP-L20 | CP-L10 | no | no | No stated contract (L-series ancestors absent, as the brief anticipated). |
| CP-L23 | CP-L10 | no | no | Same. |
| CP-L30 | CP-L10 | no | no | Same. |
| CP-L40 | CP-L10 | no | no | Same. |
| CP-PARSE | CP-0 | no | no (but runs as its own route node) | Already stage 0 of every compiled route — preserved structurally without needing a phase contract; its output obligation (`CP-PARSE_DIGEST` feeding CP-0's `cp0_requires`) is stated in host_rules. |

## Recorded divergences (ancestor vs Deploy V — Deploy V wins)

1. Name/slug swaps: Deploy V cp-2e carries legacy CP-2F's name (legacy CP-2E = liquidity); Deploy V cp-5 carries legacy CP-5B's name (legacy CP-5 = QA/clearance); Deploy V cp-2g matches neither legacy CP-2G (ESG) nor absorbed CP-2D (governance); Deploy V cp-4c matches neither legacy CP-4C (covenant capacity) nor absorbed CP-3C (portfolio sizing).
2. CP-2C's ancestor tables are numbered T5.x (collides with the 5-series), not T2C.x.
3. CP-3B's ancestor skips T3B.9; CP-4D↔CP-3B ordering conflict as tabled above.
4. **CP-5B and CP-6E** exist in Modular OS/ with full contracts but are absent from the Deploy V manifest entirely — neither physical nor alias. They are not among the 19 and are not registered; nothing in the runtime may address them. If methodology ever reinstates them it is a Deploy V bundle change, not a registry change.
5. CP-MON, CP-SR, CP-X (Modular OS layers 7/orchestration) are likewise outside the catalog; CP-X's dispatch role is exactly what the compiled route DAG replaces.
