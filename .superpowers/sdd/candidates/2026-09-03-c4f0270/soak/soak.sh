#!/usr/bin/env bash
# Start the PERF-013 eight-hour soak against the candidate stack from the
# checked-in capacity harness (qa/capacity.py at the candidate tag), after
# recording the pre-soak baseline: the harness's own `baseline` (capacity
# subjects) and the subject-independent authority snapshot of the whole store.
#
#   bash soak.sh <candidate-clone> <out-dir>
#
# The profile runs the declared enterprise test profile (25 subjects, 20 active
# jobs, 4 streams and 2 previews per subject, 300 rpm per subject, 100 cases of
# 100 documents, every 500th seeded document a 25 MiB source) for 28 800 s,
# sampling containers every 30 s (PERF-012), and restarts the WORKER hard
# (`restart -t 0`, i.e. SIGKILL) every two hours as the representative fault
# under saturation. The app is not restarted by the harness: qa/capacity.py's
# job drivers do not survive an unreachable API (wait_terminal has no retry),
# so an app restart would silently thin the workload — recorded as an open
# harness limitation in the report, not patched (the harness is frozen with
# the candidate).
set -euo pipefail
clone=${1:?candidate clone}
out=${2:?out dir}
url=${CAOS_URL:-http://127.0.0.1:18200}
project=${COMPOSE_PROJECT_NAME:-caos-cand-20260903}
mkdir -p "$out"
cd "$clone"
PY=caos/server/.venv314/bin/python
export ANTHROPIC_API_KEY= OPENROUTER_API_KEY= GEMINI_API_KEY= CAOS_EDGE_SECRET=
echo "# pre-soak baseline (harness): capacity.py baseline"
$PY qa/capacity.py baseline --url "$url" --out "$out/baseline-pre.json"
echo "# pre-soak authority snapshot (whole store)"
COMPOSE_PROJECT_NAME=$project bash "$(dirname "$0")/authority_snapshot.sh" > "$out/pre-soak-authority.json"
$PY -c "import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d['counts']))" "$out/pre-soak-authority.json"
echo "# soak: capacity.py profile --duration 28800"
# REDUCED PROFILE — not the declared 25/20/4/2/300. Attempts 1 and 2 (retained
# under attempt-1-aborted/ and attempt-2-aborted/) ran the declared profile and
# the harness destroyed its own workload inside four minutes: the application
# enforced its 300/min per-subject bucket exactly as designed, and the harness's
# threads died on the 429s — the four stream holders per subject reopen the
# events stream in a tight loop once a run is terminal (draining the bucket),
# wait_terminal re-raises on any non-run body so every job driver died, and
# leakage_check indexes an error body so the sampler died too. With no drivers
# and no sampler an eight-hour run measures nothing. This launch keeps 25
# subjects, 20 active jobs, 2 previews, 100 cases × 100 seeded documents and
# the two-hourly worker fault, but runs ZERO stream holders and the reader at
# 100 rpm so the same subject's driver never sees a 429. The 300/min and
# 4-stream ceilings are proven by `capacity.py limits`; PERF-013 at the declared
# profile stays OPEN on this candidate (harness fix = new candidate).
# macOS has no setsid; nohup + disown detaches the soak from this shell.
nohup $PY qa/capacity.py profile --url "$url" --duration 28800 --streams 0 --rpm 100 --large-every 500 --sample-every 30 \
  --compose-project "$project" \
  --restart-every 7200 --restart-command "docker compose -p $project restart -t 0 worker" \
  --out "$out/profile" > "$out/profile.log" 2>&1 < /dev/null &
echo $! > "$out/profile.pid"
disown
date -u +%Y-%m-%dT%H:%M:%SZ > "$out/started-at.txt"
echo "soak pid $(cat "$out/profile.pid") started $(cat "$out/started-at.txt"); log $out/profile.log; samples $out/profile/samples.jsonl"
