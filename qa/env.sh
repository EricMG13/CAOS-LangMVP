# Production-like local QA environment. Source from the repo root.
#
# The two long secrets are generated on first use into qa/.secrets (gitignored)
# rather than written here: this repo gates on gitleaks in CI, and a committed
# 64-hex literal fails that gate whether or not it is real. The Postgres
# password below is deliberately low-entropy and fixed — the same string the
# `docker run` line in qa/INVENTORY.md sets on a loopback-only container, so it
# has to be readable in both places to be usable at all.
if [ ! -f qa/.secrets ]; then
  ( umask 077
    printf 'export EDGE_PROXY_SECRET=%s\nexport SESSION_SECRET=%s\n' \
      "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > qa/.secrets )
fi
. qa/.secrets

export ENVIRONMENT=production
export DATABASE_URL="postgresql+psycopg://postgres:qa-local-only-not-a-secret-0000@127.0.0.1:55433/caos"
export PORT=8099
export HOST=127.0.0.1
export MAX_UPLOAD_MB=32
export MAX_SOURCE_MB=25
export AGENT_EXECUTION_ENABLED=false
export CAOS_EDGE_PORT=8100
export CAOS_UPSTREAM_PORT=8099
export CLAMAV_HOST=127.0.0.1
export CLAMAV_PORT=33100
