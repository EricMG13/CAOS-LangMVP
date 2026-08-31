# CAOS implemented desktop — final Impeccable critique

Date: 31 August 2026

Target: production export and source on `codex/caos-production-design`; desktop/laptop only

Method: two independent assessments, final root-cause correction pass, live browser inspection, and one CLI detector run

## Result

**34/40 — Good/high. AI-slop: PASS. P0: 0. P1: 0.**

| Nielsen heuristic | Score | Final evidence |
|---|---:|---|
| Visibility of system status | 4/4 | Loading, run progress, authority, save state, conflicts, recovery, mutation receipts, and unavailable states are visible and announced appropriately. |
| Match between system and real world | 4/4 | Credit, source, accepted snapshot, selected run, model revision, and deliverable language now matches served authority rather than mock concepts. |
| User control and freedom | 3/4 | Explicit switch, restore, retry, discard, conflict, and draft-navigation protections exist; dense governed flows still require deliberate steps. |
| Consistency and standards | 4/4 | Shared dark/blue tokens, status language, focus, buttons, tables, and route labels are consistent; false boxed affordances were removed. |
| Error prevention | 4/4 | Reader writes fail closed, model/report prerequisites are gated, stale async completions are rejected, and recovery input is validated at the trust boundary. |
| Recognition rather than recall | 4/4 | Authority stays visible; evidence search covers filename, source ID, block ID/text, and locator without silent result truncation. |
| Flexibility and efficiency | 2/4 | Command search and dense direct access help experts, but saved views, recent credits, and batch operations are not served. |
| Aesthetic and minimalist design | 3/4 | Restrained institutional visual language with no gradients, shadows, idle animation, or decorative charts; Model and Report remain necessarily dense. |
| Error recognition and recovery | 4/4 | Errors explain the safe state and next action; report recovery supports restore, retry, download, discard, and automatic retry. |
| Help and documentation | 2/4 | Labels and unavailable explanations are strong, but there is no searchable task-oriented help surface. |
| **Total** | **34/40** | **High; no P0/P1 issues remain.** |

## Anti-pattern verdict

PASS. The final detector returned `[]`. Manual review found no gradient, glass, pill-field, oversized marketing-heading, decorative chart, fake confidence score, or visible repeated em-dash cadence pattern.

## Corrections completed

- Added terminal no-case and identity-failure states; Reader behavior now stays read-only.
- Made authority labels honest (`Selected run`, unsaved report status, exact digest only after save).
- Removed hidden evidence-result truncation and expanded search across every served evidence block.
- Replaced clipped 720-pixel navigation behavior with active-item scrolling; removed page-level overflow.
- Corrected placeholder/focus/lead contrast and increased small evidence/sort targets.
- Made loan values wrap rather than ellipsize and removed misleading portfolio/ranking language.
- Replaced source `Extracted` status when no blocks exist and prevented filtered-out source selection.
- Removed claims of independent filing, ready model availability, and temporary Reader calculations where the contracts did not support them.
- Added scoped report recovery validation and generation-fenced Analysis snapshot switching.

## Priority issues

- P0: none.
- P1: none.
- P2: reduce dense Model/Report control groups; define task-oriented help; add saved views/recent credits only with served contracts.

## Persona red flags

- Analyst: no blocker; Model/Report density remains the main learning cost.
- Portfolio manager: no blocker; saved/recent credit shortcuts are absent.
- QA/audit: no blocker; exact identities and recovery are visible, but help is distributed in context rather than centrally searchable.

## Minor observations

- At desktop 200% zoom, the horizontal rail intentionally scrolls its wordmark off-screen to keep the active destination visible.
- Thirteen font files are packaged although two load initially.
- Shell, Deep Dive, and Command Center independently fetch snapshot state.

## Questions

No blocking questions. Future saved views, help, portfolio summary, and claim coverage require explicit product/API decisions before implementation.

## Verification

- 70 desktop route/state combinations; zero axe violations and no page-level horizontal overflow.
- 73 unit tests, lint, TypeScript production build, and focused post-review suites pass.
- Desktop widths 1280/1366/1440/1600/1920 plus 720 CSS pixels for 200% desktop zoom.
