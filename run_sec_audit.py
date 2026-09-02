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

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from caos.api import create_app  # noqa: E402
from caos.config import Settings  # noqa: E402
from caos.engine.runtime import Engine  # noqa: E402
from caos.identity import EdgeIdentityGate, identity_from_request  # noqa: E402
from caos.storage.models import ModelStore  # noqa: E402
from caos.storage.store import DomainStore, now_iso  # noqa: E402

PUBLIC = {("GET", "/api/health")}
EDGE_SECRET = "audit-edge-secret"
ZERO_DIGEST = "0" * 64
BODY_PROBES = {
    ("POST", "/api/cases"): {"name": "Audit", "issuer": "Audit", "sector": "Audit"},
    ("POST", "/api/cases/{case_id}/notes"): {"body": "audit"},
    ("POST", "/api/cases/{case_id}/rv"): {
        "rows": [{"issuer": "Audit", "instrument": "TL-B", "currency": "USD"}],
    },
    ("POST", "/api/cases/{case_id}/rv/loan-universes"): {"source_id": "foreign-source"},
    ("POST", "/api/cases/{case_id}/runs"): {"pathway": "FULL_CREDIT", "depth": "screen"},
    ("POST", "/api/cases/{case_id}/snapshot/switch"): {"snapshot_id": "foreign-snapshot"},
    ("POST", "/api/cases/{case_id}/models"): {},
    ("POST", "/api/cases/{case_id}/models/previews"): {
        "build_id": "foreign-build", "registry_version": "audit", "registry_digest": ZERO_DIGEST,
        "assumptions": [{"assumption_id": "audit", "case": "BASE", "period_id": "FY2026",
                         "unit": "x", "status": "READY", "value": 1}],
    },
    ("POST", "/api/cases/{case_id}/model-revisions/sign-off"): {
        "build_id": "foreign-build", "registry_version": "audit", "registry_digest": ZERO_DIGEST,
        "assumptions": [{"assumption_id": "audit", "case": "BASE", "period_id": "FY2026",
                         "unit": "x", "status": "READY", "value": 1}],
        "preview_digest": ZERO_DIGEST, "note": "audit",
    },
    ("POST", "/api/cases/{case_id}/model-revisions/rebase-preview"): {
        "revision_id": "foreign-revision", "build_id": "foreign-build",
    },
    ("POST", "/api/cases/{case_id}/models/scenarios"): {
        "build_id": "foreign-build", "registry_version": "audit", "registry_digest": ZERO_DIGEST,
        "shocks": [{"assumption_id": "audit", "case": "BASE", "period_id": "FY2026", "value": 1}],
    },
    ("POST", "/api/cases/{case_id}/models/tornado"): {
        "build_id": "foreign-build", "registry_version": "audit", "registry_digest": ZERO_DIGEST,
        "assumptions": [{"assumption_id": "audit", "case": "BASE", "period_id": "FY2026",
                         "unit": "x", "status": "READY", "value": 1}],
        "output_period_id": "BASE::FY2026",
    },
    ("POST", "/api/cases/{case_id}/models/sensitivities/one-way"): {
        "build_id": "foreign-build", "registry_version": "audit", "registry_digest": ZERO_DIGEST,
        "assumption_id": "audit", "case": "BASE", "period_scope": "FY2026",
    },
    ("PUT", "/api/cases/{case_id}/deliverables/{pathway}/draft"): {
        "expected_version": 0, "template_id": "audit", "template_version": "audit",
        "blocks": [{"kind": "HEADING", "block_id": "audit", "slot_id": "audit", "text": "Audit"}],
    },
    ("POST", "/api/cases/{case_id}/deliverables/{pathway}/freeze"): {
        "draft_id": "foreign-draft", "draft_version": 1, "draft_digest": ZERO_DIGEST,
    },
    ("POST", "/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/approve"): {
        "preview_digest": ZERO_DIGEST, "input_fingerprint": ZERO_DIGEST,
    },
    ("POST", "/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/request-changes"): {
        "preview_digest": ZERO_DIGEST, "input_fingerprint": ZERO_DIGEST, "comment": "audit",
    },
}


def _path(template: str, **values: str) -> str:
    defaults = {"pathway": "FULL_CREDIT", "format_name": "md"}
    return re.sub(
        r"\{([^}]+)\}",
        lambda match: values.get(match.group(1), defaults.get(match.group(1), f"foreign-{match.group(1)}")),
        template,
    )


def _request(client: TestClient, method: str, template: str, headers: dict[str, str], **values: str):
    kwargs: dict[str, object] = {"headers": headers}
    body = BODY_PROBES.get((method, template))
    if body is not None:
        kwargs["json"] = body
    if template.endswith("/models/assumption-registry"):
        kwargs["params"] = {"build_id": values.get("build_id", "foreign-build")}
    return client.request(method, _path(template, **values), **kwargs)


def main() -> int:
    failures: list[str] = []
    proxy_config = (Path(__file__).resolve().parent / "caos" / "deploy" / "oauth2-proxy.cfg").read_text()
    for required in ("pass_user_headers = true", "skip_auth_strip_headers = true"):
        if not re.search(rf"(?m)^\s*{re.escape(required)}\s*$", proxy_config):
            failures.append(f"oauth2-proxy.cfg must explicitly set {required!r}")

    for environment in ("Production", "PRODUCTION", "prod", "staging", ""):
        invalid = Settings(environment=environment)
        try:
            invalid.validate_runtime()
        except RuntimeError:
            pass
        else:
            failures.append(f"ENVIRONMENT={environment!r} did not fail startup validation")
        request = Request({
            "type": "http", "method": "GET", "path": "/api/me", "query_string": b"",
            "headers": [(b"x-caos-role", b"ADMIN")],
        })
        try:
            identity_from_request(request, invalid)
        except HTTPException as exc:
            if exc.status_code != 401:
                failures.append(f"ENVIRONMENT={environment!r} identity refusal -> {exc.status_code}")
        else:
            failures.append(f"ENVIRONMENT={environment!r} selected development identity mode")

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

        public_paths = frozenset(path for method, path in PUBLIC if method == "GET")
        if EdgeIdentityGate.PUBLIC_PATHS != public_paths:
            failures.append(
                f"public route drift: gate={sorted(EdgeIdentityGate.PUBLIC_PATHS)} audit={sorted(public_paths)}"
            )
        openapi_bodies = {
            (method.upper(), path)
            for path, operations in app.openapi()["paths"].items()
            for method, operation in operations.items()
            if isinstance(operation, dict) and "requestBody" in operation
        }
        if openapi_bodies != set(BODY_PROBES):
            failures.append(
                f"body probe drift: missing={sorted(openapi_bodies - set(BODY_PROBES))} "
                f"stale={sorted(set(BODY_PROBES) - openapi_bodies)}"
            )
        openapi_queries = {
            (method.upper(), path, parameter["name"])
            for path, operations in app.openapi()["paths"].items()
            for method, operation in operations.items()
            if isinstance(operation, dict)
            for parameter in operation.get("parameters", [])
            if parameter.get("in") == "query"
        }
        expected_queries = {
            ("GET", "/api/cases/{case_id}/models/assumption-registry", "build_id"),
        }
        if openapi_queries != expected_queries:
            failures.append(
                f"query probe drift: missing={sorted(openapi_queries - expected_queries)} "
                f"stale={sorted(expected_queries - openapi_queries)}"
            )

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
            "X-Edge-Authorization": EDGE_SECRET,
            "X-Forwarded-User": "auditor",
            "X-Forwarded-Email": "auditor@example.com",
            "X-Forwarded-Groups": "caos-reader",
            "X-Caos-Role": "ADMIN",  # casing cannot make it authoritative
        }).json()
        if me.get("role") != "READER":
            failures.append(f"x-caos-role escalated the OIDC-derived role: {me}")

        wrong_edge = client.get("/api/me", headers={
            "x-edge-authorization": "not-the-secret",
            "x-forwarded-user": "auditor",
        }).status_code
        if wrong_edge != 401:
            failures.append(f"wrong edge secret -> {wrong_edge} (expected 401)")

        trusted = [
            (b"x-edge-authorization", EDGE_SECRET.encode()),
            (b"x-forwarded-user", b"auditor"),
            (b"x-forwarded-email", b"auditor@example.com"),
            (b"x-forwarded-groups", b"caos-reader"),
        ]
        for name, extra in (
            ("edge", (b"x-edge-authorization", b"wrong")),
            ("user", (b"x-forwarded-user", b"admin")),
            ("email", (b"x-forwarded-email", b"admin@example.com")),
            ("groups", (b"x-forwarded-groups", b"caos-admin")),
        ):
            request = Request({
                "type": "http", "method": "GET", "path": "/api/me", "query_string": b"",
                "headers": [*trusted, extra],
            })
            try:
                identity_from_request(request, settings)
            except HTTPException as exc:
                if exc.status_code != 401:
                    failures.append(f"duplicate trusted {name} header -> {exc.status_code}")
            else:
                failures.append(f"duplicate trusted {name} header was accepted")

        owner_a, owner_b, reader = "owner-a", "owner-b", "case-a-reader"
        case_a = store.create_case("Case A", "Issuer A", "Audit", owner_a)
        case_b = store.create_case("Case B", "Issuer B", "Audit", owner_b)
        store.add_member(case_a["id"], owner_a, reader, "READER", actor_role="ADMIN")
        foreign_run = engine.runs.create_run(case_b["id"], "FULL_CREDIT", "screen", owner_b)
        foreign_build = ModelStore(store.engine).insert_build_row({
            "id": "mdl-foreign-audit", "case_id": case_b["id"], "status": "READY",
            "input_fingerprint": ZERO_DIGEST, "queued_at": now_iso(), "created_by": owner_b,
        })
        reader_headers = {
            "x-edge-authorization": EDGE_SECRET,
            "x-forwarded-user": reader,
            # A current global admin role must not override the stored READER standing.
            "x-forwarded-groups": "caos-admin",
            "x-caos-role": "ADMIN",
        }

        case_boundary_routes = 0
        membership_checks: list[tuple[str, str]] = []
        real_is_member = store.is_member

        def audited_is_member(case_id: str, actor: str, roles=None):
            membership_checks.append((case_id, actor))
            return real_is_member(case_id, actor, roles=roles)

        store.is_member = audited_is_member
        for route in app.routes:
            path = getattr(route, "path", "")
            if "{case_id}" not in path:
                continue
            for method in sorted((getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}):
                case_boundary_routes += 1
                membership_checks.clear()
                foreign = _request(client, method, path, reader_headers, case_id=case_b["id"])
                if foreign.status_code != 404:
                    failures.append(
                        f"{method} {path}: foreign case path -> {foreign.status_code} (expected 404)"
                    )
                if case_b["id"] in foreign.text:
                    failures.append(f"{method} {path}: foreign case id leaked in response")
                if (case_b["id"], reader) not in membership_checks:
                    failures.append(f"{method} {path}: foreign case membership boundary was not reached")
                if method not in {"GET", "HEAD", "OPTIONS"}:
                    own = _request(client, method, path, reader_headers, case_id=case_a["id"])
                    if own.status_code != 403:
                        failures.append(
                            f"{method} {path}: stored reader write -> {own.status_code} (expected 403)"
                        )
        store.is_member = real_is_member

        for route in app.routes:
            path = getattr(route, "path", "")
            if "{run_id}" not in path:
                continue
            for method in sorted((getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}):
                response = _request(
                    client, method, path, reader_headers, run_id=foreign_run["id"]
                )
                if response.status_code != 404 or case_b["id"] in response.text:
                    failures.append(
                        f"{method} {path}: foreign run -> {response.status_code} or leaked its case"
                    )

        foreign_query = _request(
            client, "GET", "/api/cases/{case_id}/models/assumption-registry",
            reader_headers, case_id=case_a["id"], build_id=foreign_build["id"],
        )
        unknown_query = _request(
            client, "GET", "/api/cases/{case_id}/models/assumption-registry",
            reader_headers, case_id=case_a["id"], build_id="mdl-unknown-audit",
        )
        if (
            foreign_query.status_code,
            foreign_query.json(),
            dict(foreign_query.headers),
        ) != (
            unknown_query.status_code,
            unknown_query.json(),
            dict(unknown_query.headers),
        ) or case_b["id"] in foreign_query.text:
            failures.append("foreign and unknown build query substitutions are distinguishable")

        calls: list[str] = []
        get_run, get_case, is_member = engine.get_run, store.get_case, store.is_member

        def traced_run(run_id: str):
            calls.append("run")
            return get_run(run_id)

        def traced_case(case_id: str):
            calls.append("case")
            return get_case(case_id)

        def traced_member(case_id: str, actor: str, roles=None):
            calls.append("member")
            return is_member(case_id, actor, roles=roles)

        engine.get_run, store.get_case, store.is_member = traced_run, traced_case, traced_member
        unknown = client.get("/api/runs/run-does-not-exist", headers=reader_headers)
        unknown_trace = tuple(calls)
        calls.clear()
        foreign = client.get(f"/api/runs/{foreign_run['id']}", headers=reader_headers)
        foreign_trace = tuple(calls)
        engine.get_run, store.get_case, store.is_member = get_run, get_case, is_member
        if (
            unknown.status_code,
            unknown.json(),
            dict(unknown.headers),
            unknown_trace,
        ) != (
            foreign.status_code,
            foreign.json(),
            dict(foreign.headers),
            foreign_trace,
        ) or unknown_trace != ("run", "case", "member"):
            failures.append("unknown and foreign runs differ in envelope, headers, or lookup class")

    for line in failures:
        print(f"FAIL {line}")
    print({
        "audited_routes": audited,
        "case_boundary_routes": case_boundary_routes,
        "failures": len(failures),
    })
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
