# CAOS — Base44 Development Notes

## Architecture
- **Backend**: Python 3.12 FastAPI server in `caos/server/`. Entry point `python dev.py` (ENVIRONMENT=development; SQLite under `caos/.dev-data`, no external secrets needed).
- **Frontend**: Next.js 16 app in `caos/frontend/`, statically exported (`output: "export"`).

## Current topology: combined app (production frontend build)
`docker-compose.base44.yml` runs:
1. **frontend-build** (one-shot, exits): `npm ci && npm run build` → static export in `caos/frontend/out/` (gitignored).
2. **backend**: installs pinned deps from `caos/server/requirements.txt`, runs `python dev.py` on 0.0.0.0:8000, mapped to host **port 3000**.

The backend serves the API and, because `caos/frontend/out/` exists, mounts the static export at `/` (API routes registered first, so `/api/*` wins — see `build()` in `caos/server/run.py`). One origin, no proxy needed.

## Running / rebuilding
```bash
docker compose -f docker-compose.base44.yml up -d --remove-orphans   # build + serve
docker compose -f docker-compose.base44.yml run --rm frontend-build  # frontend-only rebuild
```
After a frontend rebuild, the running backend serves the new files on the next request (StaticFiles reads from disk per request) — no backend restart needed.

## Key env vars (backend service)
- `ENVIRONMENT=development` — required by `dev.py`. True production mode (`run.py`) requires PostgreSQL + real edge/session secrets + OIDC identity via oauth2-proxy, none of which exist here.
- `HOST=0.0.0.0` — binds all interfaces so port mapping works.
- `CAOS_DATA_DIR=/app/caos/.dev-data` — SQLite store + LangGraph checkpoints.

## Dev mode identity
In development the backend's identity gate is a no-op — requests default to the "analyst" user with ANALYST role. No auth headers needed.

## Agent execution
LLM agent execution is OFF by default (`AGENT_EXECUTION_ENABLED=false`). Screen runs work without any provider key. To enable, set `AGENT_EXECUTION_ENABLED=true` plus a provider key (Anthropic/OpenAI/OpenRouter).

## Hot-reload alternative
The previous dev wiring (Next.js dev server on 3000 proxying `/api/*` to the backend) can be restored; it needs `API_PROXY_URL=http://backend:8000` (server-side rewrite target in `next.config.js`) and `BASE44_PUBLIC_HOST_SUFFIX` for `allowedDevOrigins`. Those code hooks are already in place.

## No external secrets required
The dev mode boots without any external credentials. SQLite is used for both the domain store and LangGraph checkpoints.
