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

> **Superseded binding.** Ticks 1–12 below bound to candidate
> `2026-09-03-c4f0270`, which the section above supersedes. They executed no
> cell and retained no result, so nothing needs re-running; the live matrix
> restarts from zero under `2026-09-04-b88c0f8`.

### 2026-09-03 tick 1 — no cell runnable

- **Candidate identity**: commit `c4f0270`, methodology build
  `237bf4bc…6bae9d`, corpus digest `460e3ad6…0ae7e3`, policy digest
  `986e6523…98f3f`, `live_repetitions` = 3, Python 3.14.6.
- **Command**: `caos/server/.venv314/bin/python caos/tests/corpus/qualify.py plan --binding live`
- **Result**: 37 required cells, 0 runnable. All 22 packs C01–C22 are
  BLOCKED EXTERNAL.
- **Verdict**: no cell executed; no scores; budget spent 0.

Missing, per pack:

| Packs | Missing |
| --- | --- |
| C01–C19 | analyst-scope approval on the answer key (reviewer, date, digest) |
| C20 | the above + 1 licensed-marks document under `$CAOS_CORPUS_EXTERNAL_DIR/C20/` |
| C21 | the above + 24 Lumen documents under `$CAOS_CORPUS_EXTERNAL_DIR/C21/` |
| C22 | the above + 2 research-pack documents under `$CAOS_CORPUS_EXTERNAL_DIR/C22/` |

Also unset in this shell: `ANTHROPIC_API_KEY`, `CAOS_CORPUS_EXTERNAL_DIR`,
`CAOS_QUALIFICATION_REVIEWER`. `caos/tests/corpus/evidence/` does not exist —
nothing retained yet. Every answer key carries `host_control` scope only, so
`verdict --binding live` is UNQUALIFIED by construction until an analyst signs
the keys. Nothing skipped, averaged or marked passed.

### 2026-09-03 tick 2 — unchanged, no cell runnable

Identity unchanged (`c4f0270` / `237bf4bc…` / corpus `460e3ad6…` / policy
`986e6523…`). `plan --binding live`: 37 required cells, 22 packs still
BLOCKED EXTERNAL, same missing inputs as tick 1. `ANTHROPIC_API_KEY`,
`CAOS_CORPUS_EXTERNAL_DIR`, `CAOS_QUALIFICATION_REVIEWER` still unset;
`caos/tests/corpus/evidence/` still absent. No cell executed, no scores,
budget spent 0.

### 2026-09-03 tick 3 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. Credentials and `$CAOS_CORPUS_EXTERNAL_DIR` still unset, evidence
directory still absent. No cell executed, no scores, budget spent 0.

### 2026-09-03 tick 4 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-03 tick 5 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-03 tick 6 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-03 tick 7 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-04 tick 8 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-04 tick 9 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-04 tick 10 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-04 tick 11 — unchanged, no cell runnable

Identity unchanged. 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.

### 2026-09-06 tick 12 — unchanged, no cell runnable

Identity unchanged (`c4f0270` / `237bf4bc…` / corpus `460e3ad6…` / policy
`986e6523…`). 37 required cells, 22 packs BLOCKED EXTERNAL, same missing
inputs. No cell executed, no scores, budget spent 0.
