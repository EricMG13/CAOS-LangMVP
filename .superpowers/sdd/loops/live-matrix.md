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
