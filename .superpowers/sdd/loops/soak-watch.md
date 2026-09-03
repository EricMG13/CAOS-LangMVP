# Soak watch — ER-L4 log

Candidate `2026-09-03-c4f0270` (tag `enterprise-candidate-2026-09-03`, app
image `sha256:cae0ed6b5c55…`, worker `sha256:61283796a3d6…`). Stack: Compose
project `caos-cand-20260903` (db, clamav, app on `127.0.0.1:18200`, worker;
`ENVIRONMENT=development`, `CAOS_PROVIDER=host_control`). Soak attempt 3 started
`2026-09-03T21:02:31Z` at a REDUCED profile: `--streams 0 --rpm 100`, everything
else declared (attempts 1 and 2 at the declared profile died on the app's own 429s
within minutes — every job driver and the sampler; retained under
`soak/attempt-1-aborted/` and `soak/attempt-2-aborted/`; PERF-013 at the declared
profile is OPEN on this candidate), pid in
`.superpowers/sdd/candidates/2026-09-03-c4f0270/soak/profile.pid`; harness
`qa/capacity.py profile --duration 28800 --streams 0 --rpm 100 --large-every 500 --sample-every 30
--compose-project caos-cand-20260903 --restart-every 7200 --restart-command
"docker compose -p caos-cand-20260903 restart -t 0 worker"` from the
candidate clone `/private/tmp/claude-501/…/scratchpad/candidate` (do not
delete that clone before the soak ends). Outputs:
`soak/profile.log`, `soak/profile/samples.jsonl` (one sample per 30 s:
latency summary, container CPU/memory, db connections, vault KiB,
checkpoint bytes), `soak/profile/profile.json` at the end. Pre-soak
baseline: `soak/baseline-pre.json` (harness, 0 capacity cases) and
`soak/pre-soak-authority.json` (whole-store snapshot from
`soak/authority_snapshot.sh`; rerun it identically after the soak and diff).
Expected end: `2026-09-04T05:02Z` plus the seed time (about three minutes). Known harness shapes, not findings: seed uploads read `409` for duplicate documents (21 distinct documents per case); readers record `429` counts; a job driver that dies logs a Python traceback in `profile.log` — count `Traceback` lines each tick and report any increase as a finding. Do not restart, scale
or reconfigure the stack; the harness restarts the worker on its own every
two hours (that is the injected fault, not an incident).

## Log

_(one entry per tick: timestamp, latest sample, deltas since the previous tick, findings)_
