"""Route security audit (CI: Server job).

Boots the app in production identity mode and asserts, for every registered
/api route except the public health check:

- an unauthenticated request (no trusted-edge header) is refused with 401. A
  pre-handler 422 is NOT accepted: FastAPI validates the body before the
  handler, so "422" from a body-required route says nothing about whether that
  route authenticates anyone. EdgeIdentityGate refuses at the ASGI edge so
  every non-public route can be held to 401;
- a client-supplied x-caos-role never escalates the OIDC-group-derived role.

Exit code is non-zero on any violation, with one line per offending route.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "caos" / "server"))

from fastapi.testclient import TestClient  # noqa: E402

from caos.api import create_app  # noqa: E402
from caos.config import Settings  # noqa: E402
from caos.engine.runtime import Engine  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402

PUBLIC = {("GET", "/api/health")}
EDGE_SECRET = "audit-edge-secret"


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="caos-sec-audit-") as temporary:
        tmp = Path(temporary)
        settings = Settings(
            environment="production",
            # validate_runtime is deliberately not called: the audit needs the
            # production *identity* edge, not a reachable PostgreSQL.
            edge_proxy_secret=EDGE_SECRET,
            session_secret="audit-session-secret",
            storage_dir=tmp / "vault",
        )
        store = DomainStore.from_url(f"sqlite:///{tmp / 'audit.db'}")
        engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp / "checkpoints.db")
        app = create_app(settings=settings, store=store, engine=engine)
        client = TestClient(app, raise_server_exceptions=False)

        audited = 0
        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", None) or set()
            if not path.startswith("/api/"):
                continue
            probe = re.sub(r"\{[^}]+\}", "audit", path)
            for method in sorted(methods - {"HEAD", "OPTIONS"}):
                if (method, path) in PUBLIC:
                    continue
                audited += 1
                status = client.request(method, probe).status_code
                if status != 401:
                    failures.append(f"{method} {path}: unauthenticated -> {status} (expected 401)")
                # A valid body must not buy a way past the gate either — this is
                # the probe that a 422-accepting audit could never make.
                with_body = client.request(method, probe, json={"probe": "audit"}).status_code
                if with_body != 401:
                    failures.append(f"{method} {path}: unauthenticated with a body -> {with_body} (expected 401)")

        me = client.get("/api/me", headers={
            "x-edge-authorization": EDGE_SECRET,
            "x-forwarded-user": "auditor",
            "x-forwarded-email": "auditor@example.com",
            "x-forwarded-groups": "caos-reader",
            "x-caos-role": "ADMIN",  # must be ignored in production
        }).json()
        if me.get("role") != "READER":
            failures.append(f"x-caos-role escalated the OIDC-derived role: {me}")

        wrong_edge = client.get("/api/me", headers={
            "x-edge-authorization": "not-the-secret",
            "x-forwarded-user": "auditor",
        }).status_code
        if wrong_edge != 401:
            failures.append(f"wrong edge secret -> {wrong_edge} (expected 401)")

    for line in failures:
        print(f"FAIL {line}")
    print({"audited_routes": audited, "failures": len(failures)})
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
