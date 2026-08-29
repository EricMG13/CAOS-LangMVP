#!/usr/bin/env bash
# Download the pinned corpus. Re-running skips what is already on disk.
#
#   SEC_USER_AGENT="Your Name you@example.com" caos/tests/corpus/fetch.sh
#
# EDGAR refuses undeclared clients and asks for under 10 requests/second.
set -euo pipefail
cd "$(dirname "$0")"
: "${SEC_USER_AGENT:?set SEC_USER_AGENT=\"Your Name you@example.com\" — EDGAR refuses undeclared clients}"
mkdir -p documents
failed=0
while read -r name url; do
  if [ -s "documents/$name" ]; then
    echo "cached  $name"
    continue
  fi
  if curl -fsSL --max-time 300 -A "$SEC_USER_AGENT" -o "documents/$name.part" "$url"; then
    mv "documents/$name.part" "documents/$name"
    echo "$(wc -c <"documents/$name" | tr -d ' ')  $name"
  else
    echo "FAILED  $name  $url"
    failed=$((failed + 1))
  fi
  rm -f "documents/$name.part"
  sleep 0.2
done < <(grep -Ev '^[[:space:]]*(#|$)' sources.txt)
[ "$failed" -eq 0 ] || echo "$failed document(s) did not download; the suite will skip what is missing"
exit "$failed"
