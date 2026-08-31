from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from .config import Settings
from .storage.store import DomainStore


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    role: str
    groups: tuple[str, ...] = ()


def _role_from_groups(groups: tuple[str, ...]) -> str:
    normalized = {group.strip().lower() for group in groups}
    for group, role in (
        ("caos-admin", "ADMIN"),
        ("caos-approver", "APPROVER"),
        ("caos-analyst", "ANALYST"),
        ("caos-reader", "READER"),
    ):
        if group in normalized:
            return role
    return "READER"


def _edge_bytes(value: str | None) -> bytes:
    """Bytes, not str, for the edge-secret comparison.

    `compare_digest` is the point — `!=` leaks the secret's prefix through
    timing — but its str form accepts ASCII only, and Starlette decodes headers
    as latin-1, so a single high byte in the client's header would turn a 401
    into a TypeError. Encoding both sides first is injective and total.
    """
    return (value or "").encode("utf-8", "surrogateescape")


def _trusted_header(request: Request, name: str, *, production: bool) -> str | None:
    values = request.headers.getlist(name)
    if production and len(values) > 1:
        raise HTTPException(status_code=401, detail="trusted edge identity required")
    return values[0] if values else None


def identity_from_request(request: Request, settings: Settings) -> Identity:
    if settings.environment not in {"development", "production"}:
        raise HTTPException(status_code=401, detail="trusted edge identity required")
    production = settings.environment == "production"
    edge_authorization = _trusted_header(
        request, "x-edge-authorization", production=production
    )
    subject_header = _trusted_header(request, "x-forwarded-user", production=production)
    email_header = _trusted_header(request, "x-forwarded-email", production=production)
    groups_header = _trusted_header(request, "x-forwarded-groups", production=production)
    if production and not hmac.compare_digest(
        _edge_bytes(edge_authorization),
        _edge_bytes(settings.edge_proxy_secret),
    ):
        raise HTTPException(status_code=401, detail="trusted edge identity required")
    subject = subject_header or email_header
    email = email_header or subject
    groups = tuple(filter(None, (groups_header or "").split(",")))
    role = (
        _role_from_groups(groups)
        if production
        else request.headers.get("x-caos-role", "ANALYST").upper()
    )
    if production and not subject:
        raise HTTPException(status_code=401, detail="OIDC identity required")
    if not subject:
        # Dev default matches the seeded-case actor so headerless local calls
        # act as the same analyst the fixtures created the case with.
        subject, email = "analyst", "analyst@local"
    if role not in {"ANALYST", "APPROVER", "ADMIN", "READER"}:
        raise HTTPException(status_code=403, detail="unknown role")
    return Identity(subject=subject, email=email, role=role, groups=groups)


def require_case(
    store: DomainStore, case_id: str, identity: Identity, write: bool = False
) -> dict:
    case = store.get_case(case_id)
    member = store.is_member(case_id, identity.subject)
    if not case or not member:
        raise HTTPException(status_code=404, detail="case not found")
    writer_roles = {"ANALYST", "APPROVER", "ADMIN"}
    if write and (
        identity.role not in writer_roles
        or not store.is_member(case_id, identity.subject, roles=writer_roles)
    ):
        raise HTTPException(status_code=403, detail="analyst authority required")
    return case


def require_role(identity: Identity, *roles: str) -> None:
    if identity.role not in set(roles):
        raise HTTPException(status_code=403, detail="insufficient role")


class EdgeIdentityGate:
    """Authentication precedes request-shape validation.

    FastAPI validates the body before the handler runs, so a body-required
    route would answer an unauthenticated caller with 422 — which a route audit
    cannot tell apart from a route that checks nothing at all. This gate refuses
    at the ASGI edge instead, so every non-public `/api` route answers 401 and
    "422 is acceptable evidence" stops being a hole the audit has to whitelist.

    Pure ASGI on purpose: it reads headers only and never touches the receive
    channel, so the run-events tail keeps streaming. In development
    `identity_from_request` cannot fail, which makes this a no-op there.
    """

    PUBLIC_PATHS = frozenset({"/api/health"})

    def __init__(self, app: Any, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if path.startswith("/api/") and path not in self.PUBLIC_PATHS:
            try:
                identity_from_request(Request(scope), self.settings)
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
