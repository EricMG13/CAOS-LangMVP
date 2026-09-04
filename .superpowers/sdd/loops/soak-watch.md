# Soak watch — ER-L4 log

Candidate `2026-09-04-b88c0f8` (tag `enterprise-candidate-2026-09-04`, app
image `sha256:10ec8aa0798d…`, worker `sha256:526c2d5f3c7a…`). Stack: Compose
project `caos-cand-20260904` (db, clamav, app on `127.0.0.1:18300`, worker;
`ENVIRONMENT=development`, `CAOS_PROVIDER=host_control`). Soak attempt 2 started
`2026-09-04T00:19:33Z` (attempt 1 at the declared 100 documents per case was
stopped at 9 min: every run was refused typed `AGENT_BUDGET_EXCEEDED` because
2,139 blocks + 100 source rows per case exceed the 2,000-row manifest ceiling;
retained under `soak/attempt-1-manifest-ceiling/`); this run is the declared
profile except `--documents 80`, pid in
`.superpowers/sdd/candidates/2026-09-04-b88c0f8/soak/profile.pid`; harness
`qa/capacity.py profile --duration 28800 --documents 80 --large-every 500 --sample-every 30
--compose-project caos-cand-20260904 --restart-every 7200 --restart-command
"docker compose -p caos-cand-20260904 restart -t 0 worker"` (25 subjects, 20
jobs, 4 streams, 2 previews, 300 rpm, 100 cases × 80 documents) from the
candidate clone `/private/tmp/claude-501/…/scratchpad/candidate2` (do not
delete that clone before the soak ends). Outputs: `soak/profile.log`,
`soak/profile/samples.jsonl` (one sample per ~30–40 s: latency summary per
request class incl. `driver_error`, `leakage_check` and `stream_open`
classes, container CPU/memory, db connections, vault KiB, checkpoint bytes),
`soak/profile/profile.json` at the end. Pre-soak baseline:
`soak/baseline-pre.json` (harness, 0 capacity cases) and
`soak/pre-soak-authority.json` (whole-store snapshot from
`soak/authority_snapshot.sh`; rerun it identically after the soak and diff:
the 12 pre-soak cases must be unchanged). Expected end: about
`2026-09-04T08:23Z`. Do not restart, scale or reconfigure the stack; the
harness restarts the worker on its own every two hours (that is the injected
fault, not an incident). Expected shapes, not findings: `429` counts on the
reader, holder and driver classes (the subjects drive at the 300/min
ceiling); a `driver_error` entry names a cycle that gave up after retries — a
rising count is a finding; a Python traceback in `profile.log` is a finding
(the repaired harness should log none).

The superseded candidate `2026-09-03-c4f0270` ran three soak attempts (two
at the declared profile that died on 429s, one reduced-profile run stopped at
2 h 18 m); they are retained under its `soak/` directory and are not this
candidate's evidence.

## Log

- 2026-09-04T10:30Z (ER-G9, after the fact): the soak completed on its own at
  `2026-09-04T08:20Z` — `profile.json` written; `leakage []`; restarts at
  02:20:43Z, 04:21:19Z, 06:22:01Z; 631 samples; 6,291 runs accepted; no
  `driver_error`, no traceback; app memory 545–780 MiB bounded; db
  connections back to 14; vault and checkpoints flat from the midpoint.
  FINDING: `caos-cand-20260904-clamav-1` was OOM-killed between 03:30:50Z and
  03:31:36Z (memory 1 010 → 45 MiB, `OOMKilled true`, no container limit) and
  is still up-but-unhealthy (`clamd` zombie; 836 failed health checks; Compose
  does not restart on unhealthy). Uploads have failed closed since then.
  Still owed by ER-L4: restart the clamav container (log it as an operator
  action with the time), then `qa/capacity.py baseline` + `compare` against
  `soak/baseline-pre.json`, `authority_snapshot.sh` diffed against
  `soak/pre-soak-authority.json` (the 12 pre-soak cases unchanged), the three
  post-soak journeys compared with `gates/browser/test-results/*`, and the
  PERF-014 leak check from `soak/profile/samples.jsonl`.
