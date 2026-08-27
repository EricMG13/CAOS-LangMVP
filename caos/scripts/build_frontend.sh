#!/usr/bin/env sh
# Build the static frontend export (caos/frontend/out) that run.py and the
# Docker image serve. CI's browser job and the Dockerfile frontend stage both
# perform exactly this.
set -eu
cd "$(dirname "$0")/../frontend"
npm ci
npm run build
