#!/usr/bin/env bash
# Acquire the pinned issuer-hosted fixtures. The application does not execute
# this script: tests upload the retained bytes through the public source API.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p documents
trap 'rm -f documents/*.part' EXIT

digest() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

while read -r name expected_sha document_type period url; do
  test -n "$document_type" && test -n "$period"
  case "$url" in
    https://www.carnivalcorp.com/*|https://www.carnivalcorporation.com/*) ;;
    *) echo "REFUSED unapproved corpus host: $url" >&2; exit 1 ;;
  esac
  if [ -s "documents/$name" ] && [ "$(digest "documents/$name")" = "$expected_sha" ]; then
    echo "cached  $name"
    continue
  fi
  rm -f "documents/$name"
  curl -fsS --retry 3 --retry-all-errors --max-time 300 \
    -o "documents/$name.part" "$url"
  if [ "$(head -c 5 "documents/$name.part")" != "%PDF-" ]; then
    echo "REFUSED non-PDF response: $url" >&2
    rm -f "documents/$name.part"
    exit 1
  fi
  if [ "$(digest "documents/$name.part")" != "$expected_sha" ]; then
    echo "REFUSED digest mismatch: $name" >&2
    exit 1
  fi
  mv "documents/$name.part" "documents/$name"
  echo "$(wc -c <"documents/$name" | tr -d ' ')  $name"
done < <(grep -Ev '^[[:space:]]*(#|$)' sources.txt)
