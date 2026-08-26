"""HTTP surface for the run engine. Rewritten against FastAPI — nothing from
LEGACY http.py. The legacy auth edge model is unchanged (identity.py): dev
trusts x-caos-role; production derives role from OIDC groups only and client
role headers never escalate.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request

from ..config import Settings
from ..contracts import StartRunRequest
from ..identity import identity_from_request, require_case
from ..storage.store import DomainStore


def create_app(*, settings: Settings, store: DomainStore, engine: Any) -> FastAPI:
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    app = FastAPI(title="caos")

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo rejected input: boundary-refused bytes (lone surrogates,
        # control chars) must not ride back through the response encoder.
        detail = [
            {"loc": list(error.get("loc", ())), "msg": str(error.get("msg", "")), "type": str(error.get("type", ""))}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    def identity(request: Request):
        return identity_from_request(request, settings)

    @app.get("/api/me")
    def me(request: Request) -> dict[str, Any]:
        who = identity(request)
        return {"subject": who.subject, "email": who.email, "role": who.role}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        return require_case(store, case_id, who)

    @app.post("/api/cases/{case_id}/runs", status_code=201)
    async def start_run(case_id: str, request: Request, body: StartRunRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return await engine.start_run(
                case_id=case_id, pathway=body.pathway, depth=body.depth.value,
                actor=who.subject, focus_questions=list(body.focus_questions),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            code = getattr(exc, "code", "RUN_START_FAILED")
            status = 409 if code == "ADMISSION_BUSY" else 422
            raise HTTPException(status_code=status, detail={"code": code}) from exc

    def visible_run(run_id: str, who: Any, *, write: bool = False) -> dict[str, Any]:
        """One uniform 404 for unknown runs AND runs in cases the caller cannot
        see — the detail string must not become a run-existence oracle."""
        run = engine.get_run(run_id) if engine is not None else None
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        try:
            require_case(store, run["case_id"], who, write=write)
        except HTTPException as exc:
            if exc.status_code == 404:
                raise HTTPException(status_code=404, detail="run not found") from None
            raise
        return run

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, request: Request) -> dict[str, Any]:
        return visible_run(run_id, identity(request))

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str, request: Request) -> dict[str, Any]:
        visible_run(run_id, identity(request), write=True)
        # ponytail: §12.22 effect verification (RESUME_NOT_APPLIED on stale/dup
        # resumes) lands with the deliverable gate; unknown runs 404 here.
        return await engine.resume(run_id)

    @app.post("/api/runs/{run_id}/upgrade")
    async def upgrade_run(run_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        visible_run(run_id, who, write=True)
        return await engine.upgrade(run_id, actor=who.subject)

    return app
