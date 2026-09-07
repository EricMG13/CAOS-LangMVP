# Live failure remediation — 2026-09-07

The confirmed runtime and provider-contract defects are patched. The latest
signed-in Codex probes pass transport/schema validation and one passes CP-PARSE,
but full-pathway evaluation still fails QA. This is development diagnosis, not
production qualification or a replacement for the original 111-cell matrix.

## Root causes and fixes

| Cause | Evidence | Fix |
| --- | --- | --- |
| Codex counted UTF-8 bytes as tokens | The original adapter returned prompt byte length plus 32,768; large prompts exhausted reservations prematurely | Use installed tokenization with a declared margin and allowance; reconcile actual returned usage |
| One source per read made large-pack preparation impossible within ten reads | Original public-pack runs reached the read ceiling; a 30-document pack needs at least 30 single-source calls | One bounded batch can read up to 50 distinct source/block pairs; existing read, byte and citation ceilings remain |
| JSON strings bypassed native schema constraints | Both canonical output and tool arguments were embedded as unrestricted strings | Native schema-constrained objects, resolvable canonical definitions and bounded tool choices |
| CP-PARSE received CP-0's competing profile and standalone packaging requirements | Both runnable profiles shared a verified skill; preparation also attempted readiness/transcription/ZIP obligations | Select the requested profile after full integrity verification; describe the existing managed evidence representation and its actual limitations |
| Model-facing canonical instructions omitted exact host expectations | Live outputs failed headings, citation-set or source-table validation | Explicit six-heading, exact delivered-reference and source-ID contracts |
| Strict schema projection exposed an unsupported keyword | A minimal live Codex request reproduced HTTP 400 on array `uniqueItems` | Remove it only from copied provider wire schemas, including direct OpenAI tool schemas; keep host duplicate validation |
| New budget metadata initially changed immutable artifact identity | Focused and backend tests reproduced persistence rejection after canonical validation | Put evidence ceilings in a separate request field; identity stays exact |

Changes share the existing provider port. OpenAI and Codex adapter versions and
tool/authority digests move with the implementation. No dependency was added.
Vendored methodology, QA arithmetic, source authorization and answer keys were
not changed.

## Measured live result

| Probe | Result |
| --- | --- |
| C01 / screen / gpt-5.4-mini | Three evidence reads, four provider calls, about 106 seconds; canonical validation succeeded, preparation QA remained Restricted |
| C02 / full / gpt-5.6-sol | CP-PARSE Passed with 8/8 field coverage; CP-0 then refused partial financial coverage, 14/24; about 178 seconds |
| C03 / full / gpt-5.6-sol | One batch delivered 49 references; canonical validation succeeded with pass source gate and 8/8 coverage; material QA finding restricted execution; about 158 seconds |

For C03, the material-count cause follows from the unchanged confidence function:
with pass source gate, complete coverage and Restricted status, a positive
MATERIAL count is the only matching branch. Exact finding text was not logged.
This pack deliberately contains conflicting debt figures; its machine-authored
host-control key expects a completed model. That expectation and the provider's
classification require independent review. They are not resolved by lowering
the QA threshold or altering the expected answer after observing a run.

The original matrix remains 17 passed, 79 failed and 15 blocked. It has not been
rerun or rewritten. Earlier GPT-6 Astra probes still hit the request timeout;
smaller/faster model probes demonstrate progress, not a universal latency fix.

## Verification

- Backend suite: **1,307 passed, 32 skipped** before the final native-tool/schema
  and profile refinements.
- Final affected Python 3.14 tests: **220 passed** after those refinements and
  the applied rewrite winners.
- Python 3.12 affected tests: **191 passed** before layout-only, AST-equivalent
  rewrite winners.
- Ruff over server/tests and `git diff --check`: **passed**.
- Confidence review and two rewrite-tournament passes completed; parent
  verification caught and fixed the artifact-identity regression.

Local diagnostic files, logs, code-state receipts and detailed reviews are in
`qa/evidence/failure-remediation-2026-09-07/`:
`confidence-review.md`, `rewrite-review.md`, `final-focused-tests.log`,
`backend-verified-tests.log`, `python312-tests.log`, and each probe's
`diagnostics.json` / `result.json`. Diagnostic records contain scalar metadata,
not prompts, source text, model output or source-derived exception messages.

## Remaining work

Passing full-pathway live evaluation remains unproven. Source fidelity and
financial completeness must be established from real evidence; extraction alone
does not attest visual, OCR or table fidelity. C20–C22 packs and independently
approved answer keys remain unavailable or unpinned after the earlier folder
search. Signed-in Codex does not qualify either direct enterprise API adapter.

Codex token counting remains an estimate, with no hard output-token cap. One
observed call used 133,025 input tokens versus 112,081 reserved, so the margin
must not be described as an upper bound. It remains development-only. Final
enterprise acceptance needs a frozen candidate, approved complete corpus and
model-specific direct OpenAI/Claude qualification.
