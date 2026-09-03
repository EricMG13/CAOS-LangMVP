"""Route security audit (CI: Server job; release gate).

Boots the app in production identity mode, discovers every route from the
OpenAPI document (and refuses to run if a route is missing from it), and
asserts the authorization matrix `ENTERPRISE_TESTING_READINESS.md` IAM-001 to
IAM-020 describes:

- an unauthenticated request (no trusted-edge header) is refused with 401
  before body validation. A pre-handler 422 is NOT accepted: FastAPI validates
  the body before the handler, so "422" from a body-required route says nothing
  about whether that route authenticates anyone;
- role comes from OIDC groups only; a client-supplied x-caos-role, a forged
  edge secret, a duplicated trusted header or a confusable group name never
  escalates (IAM-002/003/005);
- Caddy strips every identity header the application trusts and oauth2-proxy
  exposes exactly the public route the gate does (IAM-001/004);
- every case- and run-scoped route answers an outsider, a removed member and a
  global administrator who is not a member with the same 404 an unknown id
  receives, and never names the case (IAM-006/009/010/011);
- a stored READER, and a stored writer whose IdP group was downgraded, read but
  never write (403); analysts write; only case APPROVER/ADMIN standing files,
  requests changes or provisions members (IAM-007/008);
- a cross-case identifier in a body or a sub-resource path never changes the
  path-scoped case: the response is byte-identical to an unknown id and the
  other case's audit chain does not move (IAM-013, SEC-006);
- undeclared identity, status, digest, authority, actor and version fields are
  refused on every JSON body (IAM-014);
- standing is rechecked inside the freeze transaction, so a revocation that
  lands after the route's check is a typed 403 (IAM-012);
- the framework's documentation surface is closed in production (SEC-011),
  the hardening headers ride every refusal and download (SEC-010), and a
  gzip-encoded or duplicate-key JSON body is handled typed (SEC-009).

Exit code is non-zero on any violation, with one line per offending route.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "caos" / "server"))
sys.path.insert(0, str(ROOT / "caos" / "tests" / "spec"))

import sqlalchemy as sa  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from caos.api import SecurityHeaders, create_app  # noqa: E402
from caos.config import Settings  # noqa: E402
from caos.engine.runtime import Engine  # noqa: E402
from caos.identity import EdgeIdentityGate, identity_from_request  # noqa: E402
from caos.storage.models import ModelStore  # noqa: E402
from caos.storage.store import DomainStore, case_members, now_iso  # noqa: E402

PUBLIC = {("GET", "/api/health")}
EDGE_SECRET = "audit-edge-secret"
ZERO_DIGEST = "0" * 64
UNKNOWN_CASE = "case-does-not-exist-audit"
UNKNOWN_RUN = "run-does-not-exist-audit"
# Only case APPROVER/ADMIN standing (plus a current global writer role) reaches
# these; research-plan approval is the run writer's own action and stays out.
APPROVER_ONLY = re.compile(r"/(members|deliverables/by-id/\{deliverable_id\}/(approve|request-changes))$")
# Undeclared fields a caller might try to mass-assign (IAM-014). None is declared
# by any request model; every JSON body route must refuse all of them.
MASS_ASSIGNMENT = {
    "actor": "attacker", "created_by": "attacker", "approved_by": "attacker", "filed_by": "attacker",
    "status": "FILED", "digest": ZERO_DIGEST, "authority": "granted", "identity": "admin",
    "version": 99, "role_override": "ADMIN",
}
BODY_PROBES = {
    ("POST", "/api/cases"): {"name": "Audit", "issuer": "Audit", "sector": "Audit"},
    ("POST", "/api/cases/{case_id}/notes"): {"body": "audit"},
    ("POST", "/api/cases/{case_id}/rv"): {
        "rows": [{"issuer": "Audit", "instrument": "TL-B", "currency": "USD"}],
    },
    ("POST", "/api/cases/{case_id}/rv/loan-universes"): {"source_id": "foreign-source"},
    ("POST", "/api/cases/{case_id}/runs"): {"pathway": "FULL_CREDIT", "depth": "screen"},
    ("POST", "/api/cases/{case_id}/snapshot/switch"): {"snapshot_id": "foreign-snapshot"},
    ("POST", "/api/runs/{run_id}/research-plan/approve"): {"plan_hash": f"sha256:{ZERO_DIGEST}"},
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
    ("POST", "/api/cases/{case_id}/deliverables/{pathway}/opinion"): {
        "draft_id": "foreign-draft", "draft_version": 1, "draft_digest": ZERO_DIGEST,
        "expected_head_opinion_id": None, "opinion": "audit", "limitations": "audit",
        "material_overrides": "audit", "rationale": "audit",
    },
    ("POST", "/api/cases/{case_id}/members"): {"subject": "audit-member", "role": "APPROVER"},
    ("POST", "/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/approve"): {
        "preview_digest": ZERO_DIGEST, "input_fingerprint": ZERO_DIGEST,
    },
    ("POST", "/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/request-changes"): {
        "preview_digest": ZERO_DIGEST, "input_fingerprint": ZERO_DIGEST, "comment": "audit",
    },
}
# Multipart routes carry no OpenAPI requestBody (they read the form themselves);
# the audit still drives them with a real file so the writer gate is exercised.
MULTIPART = {
    ("POST", "/api/intake"): [("files", ("audit.txt", b"audit evidence line\n", "text/plain"))],
    ("POST", "/api/cases/{case_id}/sources"): [("file", ("audit.txt", b"audit evidence line\n", "text/plain"))],
}
# Actor -> (OIDC groups, stored case standing on case A). "REMOVED" means the
# membership row existed and was deleted (no route removes members yet, so the
# audit removes the row directly — the same state an IdP-driven revocation
# leaves behind once operators act on it).
ACTORS = {
    "outsider": ("caos-analyst", None),
    "admin-outsider": ("caos-admin", None),
    "removed": ("caos-analyst", "REMOVED"),
    "reader": ("caos-reader", "READER"),
    "admin-stored-reader": ("caos-admin", "READER"),
    "downgraded": ("caos-reader", "ANALYST"),
    "analyst": ("caos-analyst", "ANALYST"),
    "approver": ("caos-approver", "APPROVER"),
    "administrator": ("caos-admin", "ADMIN"),
}
NON_MEMBERS = ("outsider", "admin-outsider", "removed")
READ_ONLY = ("reader", "admin-stored-reader", "downgraded")
WRITERS = ("analyst", "approver", "administrator")
APPROVERS = ("approver", "administrator")


def _path(template: str, **values: str) -> str:
    defaults = {"pathway": "FULL_CREDIT", "format_name": "md"}
    return re.sub(
        r"\{([^}]+)\}",
        lambda match: values.get(match.group(1), defaults.get(match.group(1), f"unknown-{match.group(1)}-audit")),
        template,
    )


def _headers(subject: str, groups: str) -> dict[str, str]:
    return {
        "x-edge-authorization": EDGE_SECRET,
        "x-forwarded-user": subject,
        "x-forwarded-email": f"{subject}@example.com",
        "x-forwarded-groups": groups,
    }


def _request(client: TestClient, method: str, template: str, headers: dict[str, str],
             body: object = None, form: dict[str, str] | None = None, **values: str):
    """One request against a route template. `body` overrides the probe; SSE
    tails are opened for their status only and closed (a live run holds them
    open forever)."""
    kwargs: dict[str, object] = {"headers": headers}
    probe = BODY_PROBES.get((method, template)) if body is None else body
    if probe is not None:
        kwargs["json"] = probe
    if (method, template) in MULTIPART:
        kwargs["files"] = MULTIPART[(method, template)]
        if form:
            kwargs["data"] = form
    if template.endswith("/models/assumption-registry"):
        kwargs["params"] = {"build_id": values.get("build_id", "unknown-build-audit")}
    url = _path(template, **values)
    if template.endswith("/events"):
        with client.stream(method, url, **kwargs) as response:
            return _Snapshot(response.status_code, None, dict(response.headers))
    response = client.request(method, url, **kwargs)
    return _Snapshot(response.status_code, response, dict(response.headers))


class _Snapshot:
    def __init__(self, status: int, response, headers: dict[str, str]) -> None:
        self.status_code = status
        self._response = response
        self.headers = headers
        self.text = response.text if response is not None else ""
        content_type = headers.get("content-type", "")
        self.json = response.json() if response is not None and content_type.startswith("application/json") else None

    def identity(self) -> tuple:
        """What a caller can observe, minus the clock."""
        return (self.status_code, self.json if self.json is not None else self.text,
                tuple(sorted((k, v) for k, v in self.headers.items() if k != "date")))


def _route_key(template: str) -> str:
    return "run" if "{run_id}" in template else "case" if "{case_id}" in template else "global"


def _discover(app) -> list[tuple[str, str]]:
    """Every (method, path) from OpenAPI, cross-checked against the registered
    routes so a route hidden from the schema cannot hide from the audit."""
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method, operation in operations.items()
        if isinstance(operation, dict)
    }
    registered = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}
        if getattr(route, "path", "").startswith("/api/")
    }
    if documented != registered:
        raise SystemExit(f"FAIL OpenAPI and registered routes differ: {sorted(documented ^ registered)}")
    return sorted(documented - PUBLIC)


def edge_configuration_checks(failures: list[str]) -> None:
    proxy_config = (ROOT / "caos" / "deploy" / "oauth2-proxy.cfg").read_text()
    for required in ("pass_user_headers = true", "skip_auth_strip_headers = true",
                     "cookie_secure = true", "cookie_httponly = true", "pass_access_token = false",
                     'skip_auth_routes = ["GET=^/api/health$"]'):
        if not re.search(rf"(?m)^\s*{re.escape(required)}\s*$", proxy_config):
            failures.append(f"oauth2-proxy.cfg must explicitly set {required!r}")
    caddyfile = (ROOT / "caos" / "deploy" / "Caddyfile").read_text()
    for name in ("X-Forwarded-User", "X-Forwarded-Email", "X-Forwarded-Groups", "X-Edge-Authorization"):
        if not re.search(rf"(?m)^\s*request_header -{name}\s*$", caddyfile):
            failures.append(f"Caddyfile must strip the client-supplied {name} header (IAM-004)")
    if not re.search(r"(?m)^\s*header_up X-Edge-Authorization \{\$EDGE_PROXY_SECRET\}\s*$", caddyfile):
        failures.append("Caddyfile must inject the edge secret on every proxied request")


def environment_checks(failures: list[str]) -> None:
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


def identity_parsing_checks(settings: Settings, failures: list[str]) -> None:
    """IAM-005: group case, whitespace, duplicates, multiple roles, confusables,
    missing subject and missing groups, on the production edge."""
    def resolve(headers: list[tuple[bytes, bytes]]):
        request = Request({"type": "http", "method": "GET", "path": "/api/me", "query_string": b"",
                           "headers": [(b"x-edge-authorization", EDGE_SECRET.encode()), *headers]})
        try:
            return identity_from_request(request, settings)
        except HTTPException as exc:
            return exc.status_code

    user = (b"x-forwarded-user", b"auditor")
    cases = {
        "exact": ([user, (b"x-forwarded-groups", b"caos-admin")], "ADMIN"),
        "upper case": ([user, (b"x-forwarded-groups", b"CAOS-ADMIN")], "ADMIN"),
        "whitespace": ([user, (b"x-forwarded-groups", b"  caos-approver , caos-reader ")], "APPROVER"),
        "duplicates": ([user, (b"x-forwarded-groups", b"caos-reader,caos-reader")], "READER"),
        "multiple roles pick the highest": ([user, (b"x-forwarded-groups", b"caos-reader,caos-analyst,caos-admin")], "ADMIN"),
        "unknown group": ([user, (b"x-forwarded-groups", b"engineering")], "READER"),
        "missing groups": ([user], "READER"),
        "empty groups": ([user, (b"x-forwarded-groups", b"")], "READER"),
        "unicode hyphen confusable": ([user, (b"x-forwarded-groups", "caos‐admin".encode("latin-1", "replace"))], "READER"),
        "zero-width joiner confusable": ([user, (b"x-forwarded-groups", "caos-ad‍min".encode("latin-1", "replace"))], "READER"),
        "subject from email": ([(b"x-forwarded-email", b"auditor@example.com"), (b"x-forwarded-groups", b"caos-analyst")], "ANALYST"),
    }
    for label, (headers, expected) in cases.items():
        outcome = resolve(headers)
        role = getattr(outcome, "role", outcome)
        if role != expected:
            failures.append(f"identity parsing {label!r} -> {role} (expected {expected})")
    if resolve([(b"x-forwarded-groups", b"caos-admin")]) != 401:
        failures.append("missing subject and email was not refused with 401")
    subject = resolve([(b"x-forwarded-email", b"auditor@example.com"), (b"x-forwarded-groups", b"caos-analyst")])
    if getattr(subject, "subject", None) != "auditor@example.com":
        failures.append("a missing x-forwarded-user did not fall back to the email subject")


def unauthenticated_checks(client: TestClient, routes: list[tuple[str, str]], failures: list[str]) -> int:
    audited = 0
    for method, path in routes:
        probe = re.sub(r"\{[^}]+\}", "audit", path)
        audited += 1
        status = client.request(method, probe).status_code
        if status != 401:
            failures.append(f"{method} {path}: unauthenticated -> {status} (expected 401)")
        # A valid body must not buy a way past the gate either — this is
        # the probe that a 422-accepting audit could never make.
        with_body = client.request(method, probe, json={"probe": "audit"}).status_code
        if with_body != 401:
            failures.append(f"{method} {path}: unauthenticated with a body -> {with_body} (expected 401)")
    return audited


def forged_identity_checks(client: TestClient, settings: Settings, failures: list[str]) -> None:
    me = client.get("/api/me", headers={**_headers("auditor", "caos-reader"), "X-Caos-Role": "ADMIN"}).json()
    if me.get("role") != "READER":
        failures.append(f"x-caos-role escalated the OIDC-derived role: {me}")
    wrong_edge = client.get("/api/me", headers={"x-edge-authorization": "not-the-secret", "x-forwarded-user": "auditor"})
    if wrong_edge.status_code != 401:
        failures.append(f"wrong edge secret -> {wrong_edge.status_code} (expected 401)")
    no_edge = client.get("/api/me", headers={"x-forwarded-user": "auditor", "x-forwarded-groups": "caos-admin"})
    if no_edge.status_code != 401:
        failures.append(f"missing edge secret with forged group -> {no_edge.status_code} (expected 401)")
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
        request = Request({"type": "http", "method": "GET", "path": "/api/me", "query_string": b"",
                           "headers": [*trusted, extra]})
        try:
            identity_from_request(request, settings)
        except HTTPException as exc:
            if exc.status_code != 401:
                failures.append(f"duplicate trusted {name} header -> {exc.status_code}")
        else:
            failures.append(f"duplicate trusted {name} header was accepted")


def framework_surface_checks(client: TestClient, analyst: dict[str, str], case_id: str, failures: list[str]) -> None:
    """SEC-011 (docs closed), SEC-010 (headers on refusals and downloads), SEC-009."""
    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
        status = client.get(path, headers=analyst).status_code
        if status != 404:
            failures.append(f"framework surface {path} -> {status} in production (expected 404)")
    expected = dict(SecurityHeaders(None, production=True).headers)
    samples = {
        "401 refusal": client.get("/api/cases"),
        "404 for a hidden case": client.get(f"/api/cases/{UNKNOWN_CASE}", headers=analyst),
        "422 validation": client.post("/api/cases", json={"probe": 1}, headers=analyst),
        "200 json": client.get("/api/cases", headers=analyst),
        "200 download": client.get(f"/api/cases/{case_id}/audit-package", headers=analyst),
        "404 static": client.get("/no-such-page"),
    }
    for label, response in samples.items():
        for name, value in expected.items():
            if response.headers.get(name) != value:
                failures.append(f"{label}: header {name} missing or wrong ({response.status_code})")
    if samples["200 download"].status_code != 200:
        failures.append(f"audit package download -> {samples['200 download'].status_code}")
    encoded = client.post("/api/cases", content=gzip.compress(json.dumps(BODY_PROBES[("POST", "/api/cases")]).encode()),
                          headers={**analyst, "content-type": "application/json", "content-encoding": "gzip"})
    # An encoding the app does not decode is a typed client error (FastAPI's 400
    # "error parsing the body"), never a 500 and never a created case.
    if encoded.status_code not in {400, 415, 422}:
        failures.append(f"gzip-encoded JSON body -> {encoded.status_code} (expected a typed 4xx)")
    before = {case["id"] for case in client.get("/api/cases", headers=analyst).json()}
    duplicate = client.post("/api/cases", content=b'{"name":"first","name":"second","issuer":"Audit","sector":"Audit"}',
                            headers={**analyst, "content-type": "application/json"})
    created = {case["id"] for case in client.get("/api/cases", headers=analyst).json()} - before
    # Recorded behaviour: the JSON parser keeps the last duplicate key and exactly
    # one case results; no second parser (the edge does not read JSON) can disagree.
    if duplicate.status_code != 201 or duplicate.json().get("name") != "second" or len(created) != 1:
        failures.append(f"duplicate JSON keys -> {duplicate.status_code} {duplicate.text[:80]} ({len(created)} cases)")


def main() -> int:
    failures: list[str] = []
    edge_configuration_checks(failures)
    environment_checks(failures)

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
        identity_parsing_checks(settings, failures)
        store = DomainStore.from_url(f"sqlite:///{tmp / 'audit.db'}")
        engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp / "checkpoints.db")
        app = create_app(settings=settings, store=store, engine=engine)
        client = TestClient(app, raise_server_exceptions=False)
        routes = _discover(app)

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
        expected_queries = {("GET", "/api/cases/{case_id}/models/assumption-registry", "build_id")}
        if openapi_queries != expected_queries:
            failures.append(
                f"query probe drift: missing={sorted(openapi_queries - expected_queries)} "
                f"stale={sorted(expected_queries - openapi_queries)}"
            )

        audited = unauthenticated_checks(client, routes, failures)
        forged_identity_checks(client, settings, failures)

        # --- the fixture world: case A (audited), case B (foreign), one run each ---
        owner_a, owner_b = "owner-a", "owner-b"
        case_a = store.create_case("Case A", "Issuer A", "Audit", owner_a)
        case_b = store.create_case("Case B", "Issuer B", "Audit", owner_b)
        run_a = engine.runs.create_run(case_a["id"], "FULL_CREDIT", "screen", owner_a)
        # Terminal on purpose: the events tail of a live run never closes, and
        # every write on a failed run still passes the authority gate before it
        # is refused typed — which is exactly what the matrix asserts.
        engine.runs.finalize_failure(run_a["id"], "AUDIT_FIXTURE_TERMINAL", None)
        run_b = engine.runs.create_run(case_b["id"], "FULL_CREDIT", "screen", owner_b)
        headers: dict[str, dict[str, str]] = {}
        for actor, (groups, standing) in ACTORS.items():
            subject = f"matrix-{actor}"
            headers[actor] = _headers(subject, groups)
            if standing == "REMOVED":
                store.add_member(case_a["id"], owner_a, subject, "ANALYST", actor_role="ADMIN")
                with store.engine.begin() as conn:
                    conn.execute(sa.delete(case_members).where(case_members.c.case_id == case_a["id"],
                                                               case_members.c.subject == subject))
            elif standing is not None:
                store.add_member(case_a["id"], owner_a, subject, standing, actor_role="ADMIN")
        analyst = headers["analyst"]
        framework_surface_checks(client, analyst, case_a["id"], failures)

        # --- IAM-006/007/008/009/010/011: the actor matrix on every route -------
        membership_checks: list[tuple[str, str]] = []
        real_is_member = store.is_member

        def audited_is_member(case_id: str, actor: str, roles=None):
            membership_checks.append((case_id, actor))
            return real_is_member(case_id, actor, roles=roles)

        store.is_member = audited_is_member
        matrix_cells = 0
        for method, path in routes:
            scope = _route_key(path)
            is_write = method != "GET"
            approver_only = APPROVER_ONLY.search(path) is not None
            if scope == "global":
                # /api/me, /api/cases, /api/intake: the writer gate and the outsider's empty world.
                if path == "/api/cases" and method == "GET":
                    listed = _request(client, method, path, headers["outsider"]).json or []
                    if any(item["id"] == case_a["id"] for item in listed):
                        failures.append("an outsider's case list names a case they are not a member of")
                    for actor in ("reader", "analyst"):
                        if not any(item["id"] == case_a["id"] for item in (_request(client, method, path, headers[actor]).json or [])):
                            failures.append(f"{actor} does not see their own case in the list")
                if is_write:
                    # A global route sees the current global role only: stored case
                    # standing neither helps a global reader nor hinders a global admin.
                    for actor in ("reader", "downgraded"):
                        status = _request(client, method, path, headers[actor]).status_code
                        matrix_cells += 1
                        if status != 403:
                            failures.append(f"{method} {path}: {actor} -> {status} (expected 403)")
                    for actor in WRITERS + ("admin-stored-reader",):
                        status = _request(client, method, path, headers[actor]).status_code
                        matrix_cells += 1
                        if status in {401, 403, 404}:
                            failures.append(f"{method} {path}: {actor} -> {status} (a writer must pass the gate)")
                    if path == "/api/intake":
                        # A case_id in the form is a case boundary like any path parameter.
                        hidden = _request(client, method, path, headers["outsider"], form={"case_id": case_a["id"]})
                        unknown = _request(client, method, path, headers["outsider"], form={"case_id": UNKNOWN_CASE})
                        if hidden.status_code != 404 or hidden.identity() != unknown.identity():
                            failures.append(f"{method} {path}: outsider naming a hidden case in the form is distinguishable from an unknown case")
                continue
            values = {"case_id": case_a["id"], "run_id": run_a["id"]}
            unknown_values = {"case_id": UNKNOWN_CASE, "run_id": UNKNOWN_RUN}
            unknown = _request(client, method, path, headers["outsider"], **unknown_values)
            if unknown.status_code != 404:
                failures.append(f"{method} {path}: unknown {scope} -> {unknown.status_code} (expected 404)")
            for actor in NON_MEMBERS:
                membership_checks.clear()
                hidden = _request(client, method, path, headers[actor], **values)
                matrix_cells += 1
                if hidden.identity() != unknown.identity():
                    failures.append(f"{method} {path}: {actor} on a hidden {scope} -> {hidden.status_code}, distinguishable from unknown")
                if case_a["id"] in hidden.text or run_a["id"] in hidden.text:
                    failures.append(f"{method} {path}: {actor} response leaked a hidden identifier")
                if (case_a["id"], f"matrix-{actor}") not in membership_checks:
                    failures.append(f"{method} {path}: {actor} never reached the membership boundary")
            member_reads: dict[str, _Snapshot] = {}
            for actor in READ_ONLY + WRITERS:
                seen = _request(client, method, path, headers[actor], **values)
                matrix_cells += 1
                if seen.identity() == unknown.identity():
                    failures.append(f"{method} {path}: member {actor} received the unknown-{scope} response")
                if not is_write:
                    member_reads[actor] = seen
                    if seen.status_code in {401, 403}:
                        failures.append(f"{method} {path}: member {actor} read -> {seen.status_code}")
                elif actor in READ_ONLY:
                    if seen.status_code != 403:
                        failures.append(f"{method} {path}: {actor} write -> {seen.status_code} (expected 403)")
                elif approver_only and actor not in APPROVERS:
                    if seen.status_code != 403:
                        failures.append(f"{method} {path}: {actor} on an approver-only route -> {seen.status_code} (expected 403)")
                elif seen.status_code in {401, 403}:
                    failures.append(f"{method} {path}: {actor} write -> {seen.status_code} (a writer must pass the gate)")
            if member_reads:
                # Every member sees the same read: JSON compared exactly, a binary
                # download (the audit package names its requester) by status.
                def visible(seen: _Snapshot):
                    return seen.identity() if seen.json is not None else seen.status_code
                baseline = visible(member_reads["analyst"])
                for actor, seen in member_reads.items():
                    if visible(seen) != baseline:
                        failures.append(f"{method} {path}: {actor} reads differently from analyst ({seen.status_code} vs {member_reads['analyst'].status_code})")
        store.is_member = real_is_member

        # --- IAM-013 / SEC-006: cross-case identifiers in bodies and sub-paths ---
        foreign_source = store.ingest({
            "case_id": case_b["id"], "filename": "foreign.txt", "media_type": "text/plain", "bytes": 7,
            "sha256": "f" * 64, "vault_path": None, "withdrawn": False,
            "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": "foreign", "extractor_version": "builtin-v1",
                        "confidence": "MEDIUM", "untrusted_data": True}],
        }, owner_b)
        foreign_build = ModelStore(store.engine).insert_build_row({
            "id": "mdl-foreign-audit", "case_id": case_b["id"], "status": "READY",
            "input_fingerprint": ZERO_DIGEST, "queued_at": now_iso(), "created_by": owner_b,
        })
        from test_deliverables_spec import draft_request, freeze_request, http_seed, sign_min  # noqa: E402

        seed_service, case_c, source_c, template_c = http_seed(settings, store)  # owned by "analyst"
        foreign_revision = seed_service.save_draft(case_c["id"], "FULL_CREDIT", draft_request(template_c, source_c), actor="analyst")
        foreign = {
            "source_id": foreign_source["id"], "build_id": foreign_build["id"], "run_id": run_b["id"],
            "draft_id": foreign_revision["draft_id"], "revision_id": foreign_revision["revision_id"],
        }
        foreign_case_ids = {case_b["id"], case_c["id"]}

        def audit_rows(case_id: str) -> int:
            return sum(1 for event in store.audit_trail(limit=10_000) if event.get("case_id") == case_id)

        cross_case_probes = 0
        for method, path in routes:
            if "{case_id}" not in path:
                continue
            probe = BODY_PROBES.get((method, path)) or {}
            targets = [name for name in re.findall(r"\{([^}]+)\}", path) if name in foreign]
            targets += [key for key in probe if key in foreign]
            for name in targets:
                before = {case_id: audit_rows(case_id) for case_id in foreign_case_ids}
                if name in probe:
                    with_foreign = _request(client, method, path, analyst, body={**probe, name: foreign[name]}, case_id=case_a["id"])
                    with_unknown = _request(client, method, path, analyst, body={**probe, name: f"unknown-{name}-audit"}, case_id=case_a["id"])
                else:
                    with_foreign = _request(client, method, path, analyst, case_id=case_a["id"], **{name: foreign[name]})
                    with_unknown = _request(client, method, path, analyst, case_id=case_a["id"])
                cross_case_probes += 1
                if with_foreign.identity() != with_unknown.identity():
                    failures.append(f"{method} {path}: foreign {name} is distinguishable from an unknown one ({with_foreign.status_code} vs {with_unknown.status_code})")
                if 200 <= with_foreign.status_code < 300:
                    failures.append(f"{method} {path}: foreign {name} was accepted on the path-scoped case")
                if any(case_id in with_foreign.text for case_id in foreign_case_ids):
                    failures.append(f"{method} {path}: foreign {name} response leaked the other case")
                if before != {case_id: audit_rows(case_id) for case_id in foreign_case_ids}:
                    failures.append(f"{method} {path}: foreign {name} moved the other case's audit chain")
        foreign_query = _request(client, "GET", "/api/cases/{case_id}/models/assumption-registry", analyst,
                                 case_id=case_a["id"], build_id=foreign_build["id"])
        unknown_query = _request(client, "GET", "/api/cases/{case_id}/models/assumption-registry", analyst,
                                 case_id=case_a["id"], build_id="mdl-unknown-audit")
        cross_case_probes += 1
        if foreign_query.identity() != unknown_query.identity() or case_b["id"] in foreign_query.text:
            failures.append("foreign and unknown build query substitutions are distinguishable")
        if cross_case_probes < 12:
            failures.append(f"cross-case probes covered only {cross_case_probes} substitutions")

        # --- IAM-014: mass assignment is refused on every JSON body -------------
        for (method, path), probe in BODY_PROBES.items():
            response = _request(client, method, path, analyst, body={**probe, **MASS_ASSIGNMENT},
                                case_id=case_a["id"], run_id=run_a["id"])
            refused = response.status_code == 422 and any(
                error.get("type") == "extra_forbidden" for error in (response.json or {}).get("detail", [])
                if isinstance(error, dict)
            )
            if not refused:
                failures.append(f"{method} {path}: undeclared identity/status/digest fields -> {response.status_code}, not refused as extra")

        # --- IAM-012: standing is rechecked inside the freeze commit -------------
        from caos.deliverables import service as deliverable_service_module

        sign_min(seed_service, case_c["id"], foreign_revision)
        real_request_freeze = deliverable_service_module.DeliverableStore.request_freeze

        def revoke_then_request(self, frozen_record, actor, audit, authorize=None):
            with store.engine.begin() as conn:
                conn.execute(sa.delete(case_members).where(case_members.c.case_id == case_c["id"],
                                                           case_members.c.subject == actor))
            return real_request_freeze(self, frozen_record, actor, audit, authorize)

        deliverable_service_module.DeliverableStore.request_freeze = revoke_then_request
        try:
            revoked = client.post(f"/api/cases/{case_c['id']}/deliverables/FULL_CREDIT/freeze",
                                  json=freeze_request(foreign_revision).model_dump(mode="json"),
                                  headers=_headers("analyst", "caos-analyst"))
        finally:
            deliverable_service_module.DeliverableStore.request_freeze = real_request_freeze
        if revoked.status_code != 403 or revoked.json() != {"detail": {"code": "CASE_STANDING_REVOKED"}}:
            failures.append(f"freeze after a mid-request revocation -> {revoked.status_code} {revoked.text[:80]} (expected 403 CASE_STANDING_REVOKED)")
        if seed_service.records.pending_freeze_jobs(case_c["id"]):
            failures.append("a freeze job was queued with revoked standing")
        if store.is_member(case_c["id"], "analyst"):
            failures.append("the revocation hook did not fire — the commit-time recheck was never exercised")

        # --- unknown and foreign runs share one envelope and one lookup class ----
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
        unknown = client.get(f"/api/runs/{UNKNOWN_RUN}", headers=headers["reader"])
        unknown_trace = tuple(calls)
        calls.clear()
        hidden = client.get(f"/api/runs/{run_b['id']}", headers=headers["reader"])
        hidden_trace = tuple(calls)
        engine.get_run, store.get_case, store.is_member = get_run, get_case, is_member
        if (
            unknown.status_code, unknown.json(), dict(unknown.headers), unknown_trace,
        ) != (
            hidden.status_code, hidden.json(), dict(hidden.headers), hidden_trace,
        ) or unknown_trace != ("run", "case", "member"):
            failures.append("unknown and foreign runs differ in envelope, headers, or lookup class")

    for line in failures:
        print(f"FAIL {line}")
    print({
        "audited_routes": audited,
        "matrix_cells": matrix_cells,
        "cross_case_probes": cross_case_probes,
        "failures": len(failures),
    })
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
