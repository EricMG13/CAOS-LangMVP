# CAOS — Base44 Development Notes

## Architecture
- **Backend**: Python 3.12 FastAPI server in `caos/server/`. Dev entrypoint is `python dev.py` (SQLite under `.dev-data`, no external secrets needed).
- **Frontend**: Next.js 16 app in `caos/frontend/`. Dev server proxies `/api/*` to the backend via `next.config.js` rewrites.
- **Single-origin wiring**: Only port 3000 (frontend) is public. The Next.js dev server proxies all `/api/*` requests to the internal backend on port 8000.

## Running
```bash
docker compose -f docker-compose.base44.yml up -d --build
```
- Backend installs deps from `caos/server/requirements.txt` (pinned with hashes), then runs `python dev.py` binding to `0.0.0.0:8000`.
- Frontend runs `npm ci && npm run dev -- -H 0.0.0.0` on port 3000.
- First boot takes several minutes (pip install + npm ci). Subsequent restarts use cached volumes.

## Key env vars
- `ENVIRONMENT=development` — required by `dev.py`.
- `HOST=0.0.0.0` — makes the backend reachable from the frontend container.
- `API_PROXY_URL=http://backend:8000` — server-side rewrite target in `next.config.js` (not exposed to client code; client uses relative `/api/` URLs).
- `BASE44_PUBLIC_HOST_SUFFIX` — used for Next.js `allowedDevOrigins`.

## Dev mode identity
In development, the backend's identity gate is a no-op — requests default to the "analyst" user with ANALYST role. No auth headers needed from the frontend.

## Agent execution
LLM agent execution is OFF by default (`AGENT_EXECUTION_ENABLED=false`). Screen runs work without any provider key. To enable agent execution, set `AGENT_EXECUTION_ENABLED=true` and provide a provider key (Anthropic/OpenAI).

## No external secrets required
The dev mode boots without any external credentials. SQLite is used for both the domain store and LangGraph checkpoints.
