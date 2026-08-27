"""HTTP surface for the run engine. Rewritten against FastAPI — nothing from
LEGACY http.py. The legacy auth edge model is unchanged (identity.py): dev
trusts x-caos-role; production derives role from OIDC groups only and client
role headers never escalate.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request

from ..config import Settings
from ..contracts import ModelPreviewRequest, ModelSignOffRequest, StartRunRequest
from ..identity import identity_from_request, require_case
from ..storage.store import DomainStore
from pydantic import BaseModel, ConfigDict


class QueueModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


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

    # -- Model Builder ------------------------------------------------------

    def models() -> Any:
        service = getattr(engine, "_model_service", None)
        if service is None:
            from ..models.service import ModelService

            service = ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)
        return service

    def model_error(exc: ValueError) -> HTTPException:
        from ..models.service import ModelBuildStale
        from ..storage.models import ModelRevisionConflict

        if isinstance(exc, ModelRevisionConflict):
            return HTTPException(status_code=409, detail={"code": "MODEL_REVISION_CONFLICT", "current": exc.current})
        if isinstance(exc, ModelBuildStale):
            return HTTPException(status_code=409, detail={"code": "MODEL_BUILD_STALE", "current_build": exc.current_build})
        code = str(exc).split(":", 1)[0]
        status = 409 if "CONFLICT" in code or "STALE" in code else 422
        return HTTPException(status_code=status, detail={"code": code})

    @app.post("/api/cases/{case_id}/models", status_code=202)
    def queue_model(case_id: str, request: Request, body: QueueModelRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return models().queue_build(case_id, who.subject)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/models")
    def list_models(case_id: str, request: Request) -> list[dict[str, Any]]:
        require_case(store, case_id, identity(request))
        return models().list_builds(case_id)

    def visible_build(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        build = models().build(build_id)
        if build is None or build["case_id"] != case_id:
            raise HTTPException(status_code=404, detail="model build not found")
        return build

    @app.get("/api/cases/{case_id}/models/assumption-registry")
    def model_registry(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        try:
            return models().assumption_registry(case_id, build_id)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/models/{build_id}")
    def get_model(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        return visible_build(case_id, build_id, request)

    @app.get("/api/cases/{case_id}/models/{build_id}/download")
    def download_model(case_id: str, build_id: str, request: Request):
        from fastapi.responses import Response

        visible_build(case_id, build_id, request)
        try:
            content, sha256 = models().download(case_id, build_id)
        except ValueError as exc:
            code = str(exc).split(":", 1)[0]
            raise HTTPException(status_code=409, detail=code) from exc
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"cache-control": "no-store", "x-caos-sha256": sha256},
        )

    @app.post("/api/cases/{case_id}/models/previews")
    def model_preview(case_id: str, request: Request, body: ModelPreviewRequest = Body(...)) -> dict[str, Any]:
        require_case(store, case_id, identity(request), write=True)
        try:
            return models().preview(case_id, body)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.post("/api/cases/{case_id}/model-revisions/sign-off", status_code=201)
    def model_sign_off(case_id: str, request: Request, body: ModelSignOffRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return models().sign_off(case_id, body, actor=who.subject)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/model-revisions")
    def model_revisions(case_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        return {"revisions": models().revisions(case_id)}

    return app
