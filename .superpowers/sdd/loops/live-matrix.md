# Live qualification matrix — ER-L3 log

Harness: `caos/tests/corpus/qualify.py` (Task 11). Evidence location:
`caos/tests/corpus/evidence/<binding>/<pack>/<PATHWAY>-<depth>/rep-<n>-<stamp>.json`
(gitignored; retain the directory under the candidate identity).

Each tick:

```bash
export ANTHROPIC_API_KEY=…            # the protected credential, this shell only
export CAOS_CORPUS_EXTERNAL_DIR=…     # C20/C21/C22 bytes, digest-pinned in their manifests
export CAOS_QUALIFICATION_REVIEWER="<reviewer>"
caos/server/.venv314/bin/python caos/tests/corpus/qualify.py plan --binding live       # the required cells
caos/server/.venv314/bin/python caos/tests/corpus/qualify.py cell --binding live \
  --pack C01 --pathway FULL_CREDIT --depth full --repetition 1                        # one cold cell
caos/server/.venv314/bin/python caos/tests/corpus/qualify.py verdict --binding live   # retained results → verdict
```

A cell needs three retained `pass` results (policy `live_repetitions` = 3)
bound to the current commit, methodology build, corpus digest and binding
identity; a blocked cell logs its typed code and stays blocked; a refusal
passes only where the pack's answer key declares it.

## Required cells (from `qualify.py plan`)

| Pack | Pathway / depth | Proves | State on 2026-09-03 |
| --- | --- | --- | --- |
| C01 | FULL_CREDIT screen, full (+ nine orchestration cells) | FC | answer key host-control attested; analyst approval BLOCKED EXTERNAL |
| C02–C16 | one or two cells each (negative) | — | synthetic, host-control attested; analyst approval BLOCKED EXTERNAL |
| C17 | FULL_CREDIT full | FC | benchmark conclusion BLOCKED EXTERNAL |
| C18 | EARNINGS_UPDATE screen, full | EU | analyst approval BLOCKED EXTERNAL |
| C19 | COVENANT_REFINANCING screen, full | CR | analyst approval BLOCKED EXTERNAL |
| C20 | RELATIVE_VALUE screen, full | RV | licensed marks BLOCKED EXTERNAL (bytes + key unsigned) |
| C21 | DISTRESSED_RESTRUCTURING screen, full | DR | Lumen pack BLOCKED EXTERNAL (24 documents unpinned + key unsigned) |
| C22 | DEEP_RESEARCH full | DeepR | research pack BLOCKED EXTERNAL (brief + evidence + key unsigned) |

## Log

_(one entry per tick: cell, command, scores, budget, verdict)_

## Candidate binding (ER-G9, 2026-09-03)

Every live cell must bind to candidate `2026-09-04-b88c0f8` (the first
candidate `2026-09-03-c4f0270` is superseded): run from a checkout of tag
`enterprise-candidate-2026-09-04` (commit
`b88c0f8ca11af3200e8bb21daab16d838c64d39f`) with
`CAOS_BUILD_COMMIT=b88c0f8ca11af3200e8bb21daab16d838c64d39f` and
`CAOS_IMAGE_DIGEST=sha256:10ec8aa0798d06c9c9fcbc1d6db95303a02430385cbca0404a3fe422139f532d`
exported; methodology build `237bf4bc56b616b1c679a32c3733a2d9baf580b113758329320478e0226bae9d`,
corpus digest `460e3ad6a64c8f78632862921f4d181f0fcb866160a6aa2f44b8c476d70ae7e3`.
The host-control results for this candidate (32 pass, 5 blocked external)
are under `.superpowers/sdd/candidates/2026-09-04-b88c0f8/gates/qualification/`;
copy the live results there under `evidence/live/` when they exist. A cell
whose binding view names a different commit, build or corpus digest is not
this candidate's evidence.
