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

_(one entry per tick: timestamp, latest sample, deltas since the previous tick, findings)_
