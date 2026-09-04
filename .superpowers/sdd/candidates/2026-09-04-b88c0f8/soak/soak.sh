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
url=${CAOS_URL:-http://127.0.0.1:18300}
project=${COMPOSE_PROJECT_NAME:-caos-cand-20260904}
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
# DECLARED PROFILE. The first candidate (2026-09-03-c4f0270) could not run this
# soak: the harness of that commit died on the application's own 429s within
# minutes (D-013, D-014, D-015). This candidate carries the repaired harness
# (admitted() retries, one held stream per 30 s window, a sampler that skips a
# refused listing, distinct seed documents), so the soak runs every declared
# value: 25 subjects, 20 active jobs, 4 streams and 2 previews per subject,
# the reader at 300 rpm, 100 cases x 100 documents (every 500th a 25 MiB
# source), a hard worker restart every two hours as the injected fault. The
# application's typed 429s under this load are expected and are recorded on
# the watch, never fatal.
# --documents 80, not the declared 100 (attempt 1, retained under
# attempt-1-manifest-ceiling/, ran the declared 100): the harness's seed
# documents are 12..31 lines, one evidence block per line, so a 100-document
# case pins a run manifest of about 2,150 rows and the application refuses
# every run typed AGENT_BUDGET_EXCEEDED at its 2,000-row ceiling (proven
# below/at/above by `capacity.py limits`). 80 documents pin about 1,800 rows.
# The application is right to refuse; the declared "100 retained documents"
# and "2,000 manifest rows" are jointly satisfiable only for documents that
# average under ~19 blocks. Recorded for ER-G10 and REV-015.
# macOS has no setsid; nohup + disown detaches the soak from this shell.
nohup $PY qa/capacity.py profile --url "$url" --duration 28800 --documents 80 --large-every 500 --sample-every 30 \
  --compose-project "$project" \
  --restart-every 7200 --restart-command "docker compose -p $project restart -t 0 worker" \
  --out "$out/profile" > "$out/profile.log" 2>&1 < /dev/null &
echo $! > "$out/profile.pid"
disown
date -u +%Y-%m-%dT%H:%M:%SZ > "$out/started-at.txt"
echo "soak pid $(cat "$out/profile.pid") started $(cat "$out/started-at.txt"); log $out/profile.log; samples $out/profile/samples.jsonl"
