# Production-configured probes: intake, scanning and identity — 2026-09-06

Candidate `2026-09-04-b88c0f8`, images `caos-cand-20260904-app:b88c0f8` and
`caos-cand-20260904-worker:b88c0f8`, run under **`ENVIRONMENT=production`** in a
throwaway Compose project (`caos-prod-20260906`, fresh volumes,
`127.0.0.1:18400`). Torn down with `down -v` after the run; the long-running
`caos-cand-20260904` stack was not touched.

## Why this exists

The eight-hour soak and its eighteen-tick watch
(`.superpowers/sdd/loops/soak-watch.md`, plus the independent observation in
`soak-watch-external-observer.md`) ran against `caos-cand-20260904`, which
sets `ENVIRONMENT=development`. That is a recorded trade-off, not an oversight —
`config.py:139` refuses `CAOS_PROVIDER=host_control` in production, and
host-control is the only binding with a qualification record, so the candidate
stack chose development to get any run execution at all.

The consequence was never carried forward into what the soak claimed:
`sources/domain.py::scan_content` returns immediately after its EICAR substring
check when `settings.environment != "production"`, so **the clamd socket is
never opened on that stack**. Uploads kept returning 201 with clamd OOM-killed
for two days (issue #57). This run closes that gap for the intake, scanning and
identity half.

## Scope and its limit

Proven here: the production identity edge, source admission, and the real clamd
scan path including its failure mode.

**Not proven here, by construction: no run executed.** Production refuses
host_control and the qualified Anthropic key is BLOCKED EXTERNAL, so the stack
ran with `AGENT_EXECUTION_ENABLED=false`. Run execution, the model and
publication paths, and the soak itself remain unproven under production
configuration.

## Identity edge — role from OIDC groups only

| Check | Expected | Observed |
|---|---|---|
| No edge secret | 401 | **401** `trusted edge identity required` |
| Wrong edge secret | 401 | **401** `trusted edge identity required` |
| Valid edge headers | 200 | **200** |
| Client `x-caos-role: ADMINISTRATOR` | no escalation | **`ANALYST`** |
| Unknown case | 404 | **404** `case not found` |
| Another subject's case | 404 | **404** — same shape, no existence leak |

## Intake and the real clamd

| Check | Expected | Observed |
|---|---|---|
| Clean upload | 201 | **201** |
| EICAR | 422 | **422** `malware detected` |
| Empty file | 422 | **422** `source is empty` |
| `payload.exe` | (expected 422) | **415** `unsupported source type` — the probe's expectation was wrong; the refusal is typed and lands before scanning |
| 26 MiB source | 413 | **413** `source exceeds upload limit` |

## The scanner-down refusal path

This is the one that had never been exercised, and the only probe that proves
clamd is genuinely in the path: EICAR alone proves nothing, because
`scan_content` catches that substring *before* it opens the socket. clamd was
stopped on this throwaway stack and a clean file uploaded:

```
scanner DOWN: 503 {"detail":"malware scanner unavailable"}
scanner BACK: 201 {"id":"src-988e061c0f604a4eb5ec", ...}
```

It fails closed — no unscanned bytes are admitted — and admission recovers when
the scanner returns.

**This also corrects the ER-L4 soak log.** `soak-watch.md` records, of the
clamav OOM, that "Uploads have failed closed since then." They did not. On that
stack `ENVIRONMENT=development`, so `scan_content` never opens the clamd socket:
probed on 2026-09-06 with clamd still dead for two days, a clean upload returned
**201 in 0.02 s** and EICAR still returned **422**. Failing closed is real, but
it is what the probes above show under `ENVIRONMENT=production`, and only there.

**Bearing on issue #57:** in production this defect is availability-only. A dead
clamd refuses every upload with a typed 503 rather than admitting anything. Its
severity is that the container stays `Up` and `unhealthy` indefinitely (PID 1 is
tini running `tail -f /dev/null`, so `restart: unless-stopped` never fires and
nothing consumes the healthcheck), while `/api/health` keeps reporting `ok`.

## Raw probe results

```json
[
  {
    "check": "no edge secret -> 401",
    "expected": 401,
    "got": 401,
    "pass": true,
    "detail": "{\"detail\":\"trusted edge identity required\"}"
  },
  {
    "check": "wrong edge secret -> 401",
    "expected": 401,
    "got": 401,
    "pass": true,
    "detail": "{\"detail\":\"trusted edge identity required\"}"
  },
  {
    "check": "valid edge -> 200",
    "expected": 200,
    "got": 200,
    "pass": true,
    "detail": ""
  },
  {
    "check": "client x-caos-role never escalates",
    "expected": "ANALYST",
    "got": "ANALYST",
    "pass": true,
    "detail": "{\"subject\":\"analyst@caos.invalid\",\"email\":\"analyst@caos.invalid\",\"role\":\"ANALYST\"}"
  },
  {
    "check": "unknown case -> 404",
    "expected": 404,
    "got": 404,
    "pass": true,
    "detail": "{\"detail\":\"case not found\"}"
  },
  {
    "check": "create case (owner) -> 201",
    "expected": 201,
    "got": 201,
    "pass": true,
    "detail": "{\"id\":\"case-e91cb13b65c84bd29b9a\",\"name\":\"Prod probe\",\"issuer\":\"Probe Holdings\",\"sector\":\"Unclassified\",\"created_by\":\"owner@caos.invalid\",\"created_at\":\"2026-09-"
  },
  {
    "check": "other subject's case -> 404",
    "expected": 404,
    "got": 404,
    "pass": true,
    "detail": "{\"detail\":\"case not found\"}"
  },
  {
    "check": "clean upload -> 201 (scanned by clamd)",
    "expected": 201,
    "got": 201,
    "pass": true,
    "detail": "{\"id\":\"src-bc5590de544f4d15ba4c\",\"case_id\":\"case-e91cb13b65c84bd29b9a\",\"filename\":\"clean.txt\",\"media_type\":\"text/plain\",\"bytes\":37,\"sha256\":\"e02991f32415a17e4db"
  },
  {
    "check": "EICAR -> 422",
    "expected": 422,
    "got": 422,
    "pass": true,
    "detail": "{\"detail\":\"malware detected\"}"
  },
  {
    "check": "empty file refused",
    "expected": 422,
    "got": 422,
    "pass": true,
    "detail": "{\"detail\":\"source is empty\"}"
  },
  {
    "check": "executable refused",
    "expected": 422,
    "got": 415,
    "pass": false,
    "detail": "{\"detail\":\"unsupported source type\"}"
  },
  {
    "check": "26 MiB source refused (>25 MiB ceiling)",
    "expected": 413,
    "got": 413,
    "pass": true,
    "detail": "{\"detail\":\"source exceeds upload limit\"}"
  }
]```

## Reproducing

Compose override used (scratch; secrets came from a generated `.env` holding
`POSTGRES_PASSWORD`, `EDGE_PROXY_SECRET` and `SESSION_SECRET`, plus placeholder
`OAUTH2_PROXY_*`/`CAOS_DOMAIN`/`CAOS_EMAIL_DOMAIN` values that exist only so
Compose can interpolate service blocks it never starts):

```yaml
services:
  app:
    image: caos-cand-20260904-app:b88c0f8
    pull_policy: never
    ports: ["127.0.0.1:18400:8000"]
    environment:
      ENVIRONMENT: production
      AGENT_EXECUTION_ENABLED: "false"
      CAOS_DATA_DIR: /vault
    command:
      - python
      - -c
      - |
        from pathlib import Path
        import run
        from caos.config import Settings
        from caos.instance_lock import checkpoint_lock
        settings = Settings.from_env()
        app, engine = run.build(settings, Path("/vault"))
        with checkpoint_lock(engine.checkpoint_path), engine.store.single_instance("app"):
            run.serve(app, engine, host="0.0.0.0", port=settings.port)
  worker:
    image: caos-cand-20260904-worker:b88c0f8
    pull_policy: never
```

```bash
docker compose -p caos-prod-20260906 --env-file .env \
  -f caos/deploy/docker-compose.yml -f override.yml up -d db clamav app
```

clamav takes ~90 s to become healthy: it loads ~175 MB of signatures under
qemu-x86_64 emulation and settles at ~1.0 GiB RSS, which is what OOM-killed it
on the candidate stack.
