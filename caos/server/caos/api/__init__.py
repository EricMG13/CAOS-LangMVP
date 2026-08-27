"""HTTP surface for the run engine. Rewritten against FastAPI — nothing from
LEGACY http.py. The legacy auth edge model is unchanged (identity.py): dev
trusts x-caos-role; production derives role from OIDC groups only and client
role headers never escalate. Every JSON success serves a named strict wire
model (caos.responses); nothing undeclared is ever served.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import responses as wire
from ..artifacts.loan_universe import (
    LoanUniverseImportRejected,
    LoanUniverseSourceError,
    import_loan_source,
)
from ..config import Settings
from ..contracts import (
    CreateCaseRequest,
    DeliverableDraftRequest,
    FileDeliverableRequest,
    FreezeDeliverableRequest,
    LoanUniverseImportRequest,
    ModelPreviewRequest,
    ModelSignOffRequest,
    NoteRequest,
    RequestDeliverableChangesRequest,
    StartRunRequest,
)
from ..identity import identity_from_request, require_case
from ..storage.store import DomainStore

WORKSHEET_SCHEMA_VERSION = "caos.model.worksheet.v1"
RUNTIME_KEYS = (
    "name", "version", "sha256",
    "assumption_registry_version", "assumption_registry_digest", "calculation_contract_version",
)
_SOURCE_BLOCK_KEYS = ("block_id", "text", "locator", "confidence", "untrusted_data", "extractor_version")
_RUN_NODE_KEYS = ("id", "run_id", "case_id", "module_id", "stage", "dependencies", "status", "attempt", "artifact_id", "error")
# Schemas the wire contract names but no route references directly.
_UNROUTED_SCHEMAS = (
    wire.ThesisResponse,
    wire.VisualRecipeValidationResponse,
    wire.CanonicalGenerationProgressResponse,
    wire.AuditEventResponse,
)


class QueueModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SwitchSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=64)


class RVQuickRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuer: str = Field(min_length=1, max_length=160)
    instrument: str = Field(min_length=1, max_length=160)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    price: float | None = None
    yield_bps: float | None = None
    spread_bps: float | None = None
    duration: float | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class RVSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: list[RVQuickRow] = Field(min_length=1, max_length=500)


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

    @app.get("/api/health", response_model=wire.HealthResponse)
    def health() -> dict[str, Any]:
        return {"status": "ok"}

    @app.get("/api/me", response_model=wire.IdentityResponse)
    def me(request: Request) -> dict[str, Any]:
        who = identity(request)
        return {"subject": who.subject, "email": who.email, "role": who.role}

    def _wire_case(case: dict[str, Any]) -> dict[str, Any]:
        # ponytail: one current-set read per case (N+1 on the list route);
        # denormalize a count onto the case row if the register ever gets slow.
        current = store.current_source_set(case["id"])
        return {
            **case,
            "source_count": len(current["source_ids"]) if current else 0,
            "deep_research_available": False,
            "deep_research_unavailable_reason": "Deep Research is disabled for this deployment.",
        }

    @app.post("/api/cases", status_code=201, response_model=wire.CaseDetailResponse)
    def create_case(request: Request, body: CreateCaseRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        return _wire_case(store.create_case(body.name, body.issuer, body.sector, who.subject))

    @app.get("/api/cases", response_model=list[wire.CaseResponse])
    def list_cases(request: Request) -> list[dict[str, Any]]:
        return [_wire_case(case) for case in store.list_cases(identity(request).subject)]

    @app.get("/api/cases/{case_id}", response_model=wire.CaseDetailResponse)
    def get_case(case_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        return _wire_case(require_case(store, case_id, who))

    # -- sources ------------------------------------------------------------

    def _wire_source(source: dict[str, Any], *, source_set: dict[str, Any] | None = None) -> dict[str, Any]:
        projected = {
            key: source.get(key)
            for key in ("id", "case_id", "filename", "media_type", "bytes", "sha256", "created_by", "created_at", "withdrawn")
        }
        projected["blocks"] = [
            {key: block.get(key) for key in _SOURCE_BLOCK_KEYS} for block in source.get("blocks") or []
        ]
        if source.get("source_kind") is not None:
            projected["source_kind"] = source["source_kind"]
        if source_set is not None:
            projected["source_set"] = source_set
        return projected

    @app.post("/api/cases/{case_id}/sources", status_code=201,
              response_model=wire.SourceResponse, response_model_exclude_unset=True)
    async def upload_source(case_id: str, request: Request) -> dict[str, Any]:
        import hashlib as _hashlib

        from ..sources.domain import Vault, extract_blocks, scan_content, validate_archive

        who = identity(request)
        require_case(store, case_id, who, write=True)
        form = await request.form()
        upload = form.get("file")
        if upload is None or isinstance(upload, str):
            raise HTTPException(status_code=422, detail="multipart field 'file' is required")
        content = await upload.read()
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload exceeds the size limit")
        scan_content(content, settings)
        validate_archive(content)
        sha256 = _hashlib.sha256(content).hexdigest()
        vault_path = Vault(settings).put(content, sha256)
        blocks = extract_blocks(upload.filename, content)
        try:
            saved = store.ingest({
                "case_id": case_id,
                "filename": upload.filename,
                "media_type": upload.content_type or "application/octet-stream",
                "bytes": len(content),
                "sha256": sha256,
                "vault_path": vault_path,
                "blocks": blocks,
                "withdrawn": False,
            }, who.subject)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _wire_source(saved, source_set=saved["source_set"])

    def visible_source(case_id: str, source_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        source = store.get_source(source_id)
        if source is None or source["case_id"] != case_id:
            raise HTTPException(status_code=404, detail="source not found")
        return source

    @app.get("/api/cases/{case_id}/sources", response_model=list[wire.SourceResponse],
             response_model_exclude_unset=True)
    def list_sources(case_id: str, request: Request) -> list[dict[str, Any]]:
        require_case(store, case_id, identity(request))
        return [_wire_source(source) for source in store.list_sources(case_id)]

    @app.get("/api/cases/{case_id}/sources/{source_id}", response_model=wire.SourceResponse,
             response_model_exclude_unset=True)
    def get_source(case_id: str, source_id: str, request: Request) -> dict[str, Any]:
        return _wire_source(visible_source(case_id, source_id, request))

    @app.post("/api/cases/{case_id}/sources/{source_id}/withdraw", response_model=wire.SourceResponse,
              response_model_exclude_unset=True)
    def withdraw_source(case_id: str, source_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        withdrawn = store.withdraw(case_id, source_id, who.subject)
        if withdrawn is None:
            source = store.get_source(source_id)
            if source is None or source["case_id"] != case_id:
                raise HTTPException(status_code=404, detail="source not found")
            return _wire_source(source)  # idempotent: already withdrawn
        return _wire_source(withdrawn)

    # -- notes --------------------------------------------------------------

    @app.post("/api/cases/{case_id}/notes", status_code=201, response_model=wire.NoteResponse)
    def create_note(case_id: str, request: Request, body: NoteRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        return store.create_note(case_id, body.body, who.subject)

    @app.get("/api/cases/{case_id}/notes", response_model=list[wire.NoteResponse])
    def list_notes(case_id: str, request: Request) -> list[dict[str, Any]]:
        require_case(store, case_id, identity(request))
        return store.list_notes(case_id)

    @app.post("/api/cases/{case_id}/notes/{note_id}/promote", response_model=wire.NoteResponse)
    def promote_note(case_id: str, note_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return store.promote_note(case_id, note_id, who.subject)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="note not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # -- relative value ------------------------------------------------------

    @app.post("/api/cases/{case_id}/rv", status_code=201, response_model=wire.RVUniverseVersionResponse)
    def save_rv(case_id: str, request: Request, body: RVSaveRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        return store.save_rv_universe(case_id, [row.model_dump() for row in body.rows], who.subject)

    @app.get("/api/cases/{case_id}/rv", response_model=wire.RVWorkspaceResponse)
    def get_rv(case_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        return {"universe": store.get_rv_universe(case_id)}

    # -- loan universes (CP-3 RV) -------------------------------------------

    @app.post("/api/cases/{case_id}/rv/loan-universes", status_code=201,
              response_model=wire.LoanUniverseResponse,
              responses={200: {"model": wire.LoanUniverseResponse}})
    def import_loan_universe(case_id: str, request: Request, response: Response,
                             body: LoanUniverseImportRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            record, created = import_loan_source(store, case_id, body.source_id, who.subject)
        except LoanUniverseSourceError as exc:
            status = 404 if exc.code == "RV_SOURCE_NOT_FOUND" else 409
            raise HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail}) from exc
        except LoanUniverseImportRejected as exc:
            raise HTTPException(status_code=422, detail={
                "code": "RV_WORKBOOK_INVALID",
                "universe_id": exc.record["id"],
                "findings": exc.record["findings"],
            }) from exc
        except ValueError as exc:
            code = str(exc).split(":", 1)[0]
            raise HTTPException(status_code=409, detail={"code": code}) from exc
        response.status_code = 201 if created else 200
        return record

    @app.get("/api/cases/{case_id}/rv/loan-universes/active", response_model=wire.LoanUniverseActiveResponse)
    def active_loan_universe(case_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        active = store.active_loan_universe(case_id)
        if active is None:
            return {"status": "NO_ACTIVE_UNIVERSE", "universe": None, "rows": []}
        rows = active.pop("rows")
        return {"status": "ACTIVE", "universe": active, "rows": rows}

    # -- runs ----------------------------------------------------------------

    def _generation_state(run: dict[str, Any]) -> dict[str, Any] | None:
        budget = engine.runs.get_budget(run["id"])
        if budget is None:
            return None
        from ..modules.registry import MODULES

        agent_modules = [
            node["module_id"] for node in (run.get("plan") or {}).get("nodes", [])
            if MODULES.get(node["module_id"]) and MODULES[node["module_id"]].mode_full == "agent"
        ]
        dimensions = ("turns", "evidence_reads", "evidence_bytes", "input_tokens",
                      "output_tokens", "active_minutes", "provider_retries", "repairs")
        state = {
            "phase": "generating" if run["status"] == "running" else "complete",
            "model": settings.anthropic_model,
            "reporting_period": run["created_at"][:10],
            "module_output_tokens": {
                module_id: MODULES[module_id].max_output_tokens for module_id in agent_modules
            },
            "budget_limits": {key: budget["limits"].get(key, 0) for key in dimensions},
            "budget_used": {key: budget["used"].get(key, 0) for key in dimensions},
            "inflight_request_digest": budget["inflight_request_digest"],
            "attempts": budget["attempts"],
        }
        completed = [module_id for module_id in engine.runs.executed_modules(run["id"]) if module_id in agent_modules]
        if completed:
            state["completed_modules"] = completed
        return state

    def _wire_run(run: dict[str, Any]) -> dict[str, Any]:
        nodes = [{key: node.get(key) for key in _RUN_NODE_KEYS} for node in run.get("nodes") or []]
        projected = {
            "id": run["id"],
            "case_id": run["case_id"],
            "status": run["status"],
            "plan": run.get("plan") or {},
            "node_ids": run.get("node_ids") or [node["id"] for node in nodes],
            "nodes": nodes,
            "events": engine.events_after(run["id"], 0),
            "current_node_id": next((node["id"] for node in nodes if node["status"] == "running"), None),
            "accepted_snapshot_id": run.get("accepted_snapshot_id"),
            "upgraded_from_run_id": run.get("upgraded_from_run_id"),
            "created_by": run["created_by"],
            "created_at": run["created_at"],
            "error": run.get("error"),
        }
        generation = _generation_state(run)
        if generation is not None:
            projected["canonical_generation"] = generation
        return projected

    @app.post("/api/cases/{case_id}/runs", status_code=201,
              response_model=wire.CanonicalRunResponse, response_model_exclude_unset=True)
    async def start_run(case_id: str, request: Request, body: StartRunRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            run = await engine.start_run(
                case_id=case_id, pathway=body.pathway, depth=body.depth.value,
                actor=who.subject, focus_questions=list(body.focus_questions),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            code = getattr(exc, "code", "RUN_START_FAILED")
            status = 409 if code == "ADMISSION_BUSY" else 422
            raise HTTPException(status_code=status, detail={"code": code}) from exc
        return _wire_run(run)

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

    @app.get("/api/runs/{run_id}", response_model=wire.CanonicalRunResponse, response_model_exclude_unset=True)
    def get_run(run_id: str, request: Request) -> dict[str, Any]:
        return _wire_run(visible_run(run_id, identity(request)))

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request) -> StreamingResponse:
        """Thin SSE tail of the append-only run_events log (DECISIONS §5): legacy
        event names verbatim, `id:` carries the per-run sequence so Last-Event-ID
        reconnects resume without replay. The stream closes once a terminal run is
        fully delivered; live runs hold it open with keepalive comments."""
        visible_run(run_id, identity(request))
        try:
            cursor = int(request.headers.get("last-event-id", "0"))
        except ValueError:
            cursor = 0

        # ponytail: per-connection 0.4s DB poll, not a wakeup bus — run_events is
        # tiny and Run Console holds one stream; add a notify hook if fan-out grows.
        poll_seconds, keepalive_seconds = 0.4, 15.0

        async def tail(after: int) -> AsyncIterator[str]:
            idle = 0.0
            while not await request.is_disconnected():
                events = engine.events_after(run_id, after)
                for item in events:
                    after = item["id"]
                    yield f"id: {item['id']}\nevent: {item['event']}\ndata: {json.dumps(item['data'], separators=(',', ':'))}\n\n"
                if events:
                    idle = 0.0
                # State and event commit in one transaction, so an empty tail on a
                # terminal run means everything (the terminal event included) is out.
                elif (engine.get_run(run_id) or {}).get("status") in ("succeeded", "failed"):
                    return
                else:
                    idle += poll_seconds
                    if idle >= keepalive_seconds:
                        idle = 0.0
                        yield ": keepalive\n\n"
                await asyncio.sleep(poll_seconds)

        return StreamingResponse(tail(cursor), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})

    @app.post("/api/runs/{run_id}/resume", response_model=wire.CanonicalRunResponse, response_model_exclude_unset=True)
    async def resume_run(run_id: str, request: Request) -> dict[str, Any]:
        visible_run(run_id, identity(request), write=True)
        return _wire_run(await engine.resume(run_id))

    @app.post("/api/runs/{run_id}/upgrade", response_model=wire.CanonicalRunResponse, response_model_exclude_unset=True)
    async def upgrade_run(run_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        visible_run(run_id, who, write=True)
        return _wire_run(await engine.upgrade(run_id, actor=who.subject))

    def _wire_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            key: snapshot.get(key)
            for key in ("id", "case_id", "run_id", "source_set_id", "source_set_version",
                        "artifacts", "digest", "previous_snapshot_id", "accepted_at")
        }

    @app.post("/api/runs/{run_id}/accept", response_model=wire.SnapshotResponse)
    async def accept_run(run_id: str, request: Request) -> dict[str, Any]:
        who = identity(request)
        visible_run(run_id, who, write=True)
        try:
            snapshot = await engine.accept(run_id, actor=who.subject)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail={"code": getattr(exc, "code", "RUN_NOT_READY")}) from exc
        return _wire_snapshot(snapshot)

    def _snapshot_diff(visible: dict[str, Any] | None, latest: dict[str, Any] | None) -> dict[str, Any] | None:
        if visible is None or latest is None or visible["id"] == latest["id"]:
            return None
        visible_digests = {ref["module_id"]: ref["digest"] for ref in visible["artifacts"]}
        latest_digests = {ref["module_id"]: ref["digest"] for ref in latest["artifacts"]}
        added = [{"module_id": m, "digest": d} for m, d in sorted(latest_digests.items()) if m not in visible_digests]
        removed = [{"module_id": m, "digest": d} for m, d in sorted(visible_digests.items()) if m not in latest_digests]
        modified = [{"module_id": m, "digest": d} for m, d in sorted(latest_digests.items())
                    if m in visible_digests and visible_digests[m] != d]
        source_set_changed = visible["source_set_id"] != latest["source_set_id"]
        return {
            "changed": bool(added or removed or modified or source_set_changed),
            "added": added, "removed": removed, "modified": modified,
            "source_set_changed": source_set_changed,
        }

    @app.get("/api/cases/{case_id}/lens", response_model=wire.CaseLensResponse)
    def case_lens(case_id: str, request: Request) -> dict[str, Any]:
        """Case-scoped issuer lens: identity plus the visible snapshot's authority
        identifiers (the visible lens follows the accepted pointer until pinned)."""
        require_case(store, case_id, identity(request))
        case = store.get_case(case_id)
        visible_id = case.get("visible_snapshot_id") or case.get("accepted_snapshot_id")
        snapshot = engine.runs.get_snapshot(visible_id) if visible_id else None
        return {
            "issuer": case["issuer"],
            "sector": case["sector"],
            "accepted_snapshot_id": snapshot["id"] if snapshot else None,
            "source_set": {"version": snapshot["source_set_version"]} if snapshot else None,
        }

    @app.get("/api/cases/{case_id}/snapshot", response_model=wire.SnapshotViewResponse)
    def case_snapshot_view(case_id: str, request: Request) -> dict[str, Any]:
        """The case's snapshot lens: `accepted` is what the analyst sees now,
        `latest_accepted` the newest acceptance. Until an explicit switch pins a
        snapshot, the visible lens follows the accepted pointer; once pinned,
        only /snapshot/switch moves it and divergence surfaces as switch_required."""
        require_case(store, case_id, identity(request))
        case = store.get_case(case_id)
        accepted_id = case.get("accepted_snapshot_id")
        visible_id = case.get("visible_snapshot_id") or accepted_id
        visible = _wire_snapshot(engine.runs.get_snapshot(visible_id)) if visible_id else None
        latest = _wire_snapshot(engine.runs.get_snapshot(accepted_id)) if accepted_id else None
        return {
            "accepted": visible,
            "latest_accepted": latest,
            "switch_required": bool(accepted_id) and visible_id != accepted_id,
            "diff": _snapshot_diff(visible, latest),
        }

    @app.post("/api/cases/{case_id}/snapshot/switch", response_model=wire.SnapshotResponse)
    async def switch_snapshot(case_id: str, request: Request, body: SwitchSnapshotRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            await engine.switch_visible(case_id, body.snapshot_id, actor=who.subject)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail="snapshot not found") from exc
        return _wire_snapshot(engine.runs.get_snapshot(body.snapshot_id))

    @app.get("/api/cases/{case_id}/artifacts/{artifact_id}", response_model=wire.ArtifactResponse)
    def get_artifact(case_id: str, artifact_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        artifact = engine.runs.get_artifact(artifact_id)
        if artifact is None or artifact["case_id"] != case_id:
            raise HTTPException(status_code=404, detail="artifact not found")
        return {
            key: artifact.get(key)
            for key in ("id", "case_id", "run_id", "module_id", "payload", "markdown",
                        "digest", "input_fingerprint", "created_by", "created_at")
        }

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

    def _wire_build(build: dict[str, Any]) -> dict[str, Any]:
        runtime = build.get("calculation_runtime")
        export = build.get("export")
        projected = {
            "id": build["id"],
            "case_id": build["case_id"],
            "accepted_run_id": build.get("accepted_run_id"),
            "accepted_snapshot_id": build.get("snapshot_id"),
            "source_set_id": build.get("source_set_id"),
            "input_fingerprint": build["input_fingerprint"],
            "status": build["status"],
            "queued_at": build["queued_at"],
            "started_at": build.get("started_at"),
            "completed_at": build.get("completed_at"),
            "error": build.get("error"),
            "export": {"status": export["status"], "error": export.get("error")} if export else None,
            "worksheet_schema_version": build.get("worksheet_schema_version"),
            "calculation_runtime": {key: runtime.get(key) for key in RUNTIME_KEYS} if runtime else None,
        }
        if build.get("payload") is not None:
            projected["payload"] = build["payload"]
            projected["payload_digest"] = build.get("payload_digest")
            projected["qa"] = build.get("qa")
        return projected

    @app.post("/api/cases/{case_id}/models", status_code=202, response_model=wire.ModelQueueResponse)
    def queue_model(case_id: str, request: Request, body: QueueModelRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return models().queue_build(case_id, who.subject)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/models", response_model=wire.ModelListResponse,
             response_model_exclude_unset=True)
    def list_models(case_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        return {"builds": [_wire_build(build) for build in models().list_builds(case_id)]}

    def visible_build(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        build = models().build(build_id)
        if build is None or build["case_id"] != case_id:
            raise HTTPException(status_code=404, detail="model build not found")
        return build

    @app.get("/api/cases/{case_id}/model", response_model=wire.ModelReadinessResponse,
             response_model_exclude_unset=True)
    def model_readiness(case_id: str, request: Request) -> dict[str, Any]:
        from ..models.service import CANONICAL_MODULES

        require_case(store, case_id, identity(request))
        readiness = models().readiness(case_id)
        build = readiness.get("build")
        requirements = readiness.get("requirements") or [
            {"module_id": module_id, "status": "MISSING"} for module_id in (*CANONICAL_MODULES, "CP-2B")
        ]
        return {
            "status": readiness["status"],
            "module_id": readiness.get("module_id", "CP-MODEL"),
            "accepted_snapshot": readiness.get("accepted_snapshot"),
            "source_set": readiness.get("source_set"),
            "requirements": [{"module_id": item["module_id"], "status": item["status"]} for item in requirements],
            "calculation_runtime": readiness.get("calculation_runtime"),
            "worksheet_schema_version": WORKSHEET_SCHEMA_VERSION,
            "blockers": [{"code": item["code"], "detail": item.get("detail")} for item in readiness.get("blockers") or []],
            "build": _wire_build(build) if build else None,
        }

    @app.get("/api/cases/{case_id}/models/assumption-registry", response_model=wire.ModelAssumptionRegistryResponse)
    def model_registry(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        try:
            return models().assumption_registry(case_id, build_id)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/models/{build_id}", response_model=wire.ModelBuildResponse,
             response_model_exclude_unset=True)
    def get_model(case_id: str, build_id: str, request: Request) -> dict[str, Any]:
        return _wire_build(visible_build(case_id, build_id, request))

    @app.get("/api/cases/{case_id}/models/{build_id}/download")
    def download_model(case_id: str, build_id: str, request: Request):
        from fastapi.responses import Response as _Response

        visible_build(case_id, build_id, request)
        try:
            content, sha256 = models().download(case_id, build_id)
        except ValueError as exc:
            code = str(exc).split(":", 1)[0]
            raise HTTPException(status_code=409, detail=code) from exc
        return _Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"cache-control": "no-store", "x-caos-sha256": sha256},
        )

    @app.post("/api/cases/{case_id}/models/previews", response_model=wire.ModelPreviewResponse)
    def model_preview(case_id: str, request: Request, body: ModelPreviewRequest = Body(...)) -> dict[str, Any]:
        require_case(store, case_id, identity(request), write=True)
        try:
            return models().preview(case_id, body)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.post("/api/cases/{case_id}/model-revisions/sign-off", status_code=201,
              response_model=wire.ModelRevisionResponse)
    def model_sign_off(case_id: str, request: Request, body: ModelSignOffRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return models().sign_off(case_id, body, actor=who.subject)
        except ValueError as exc:
            raise model_error(exc) from exc

    @app.get("/api/cases/{case_id}/model-revisions", response_model=wire.ModelRevisionListResponse)
    def model_revisions(case_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        return {"revisions": models().revisions(case_id)}

    # -- deliverables --------------------------------------------------------

    _deliverables: dict[str, Any] = {}

    def deliverables() -> Any:
        from ..deliverables.service import DeliverableService

        if "service" not in _deliverables:
            _deliverables["service"] = DeliverableService(store=store, vault_dir=settings.storage_dir, engine=engine)
        return _deliverables["service"]

    def require_case_approver(case_id: str, request: Request) -> Any:
        """Filing is approver-gated by CASE standing (DECISIONS §2): global
        roles never escalate, non-members never learn the case exists."""
        who = identity(request)
        if store.get_case(case_id) is None or not store.is_member(case_id, who.subject):
            raise HTTPException(status_code=404, detail="case not found")
        if not store.is_member(case_id, who.subject, roles={"APPROVER", "ADMIN"}):
            raise HTTPException(status_code=403, detail="case approver authority required")
        return who

    def deliverable_error(exc: ValueError) -> HTTPException:
        from ..deliverables.service import ResumeNotApplied
        from ..storage.deliverables import DeliverableVersionConflict

        if isinstance(exc, ResumeNotApplied):
            return HTTPException(status_code=409, detail={
                "code": "RESUME_NOT_APPLIED", "current_interrupt_id": exc.current_interrupt_id,
            })
        if isinstance(exc, DeliverableVersionConflict):
            return HTTPException(status_code=409, detail={
                "code": "DELIVERABLE_VERSION_CONFLICT", "current": exc.current,
            })
        code = str(exc).split(":", 1)[0]
        status = 404 if "NOT_FOUND" in code else 409 if ("STALE" in code or "CONFLICT" in code or "CHANGED" in code or "INTEGRITY" in code) else 422
        return HTTPException(status_code=status, detail={"code": code})

    @app.get("/api/cases/{case_id}/deliverables/{pathway}/draft",
             response_model=wire.DeliverableWorkspaceResponse)
    def get_deliverable_draft(case_id: str, pathway: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        return deliverables().workspace(case_id, pathway)

    @app.put("/api/cases/{case_id}/deliverables/{pathway}/draft", status_code=201,
             response_model=wire.DeliverableRevisionResponse)
    def put_deliverable_draft(case_id: str, pathway: str, request: Request,
                              body: DeliverableDraftRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return deliverables().save_draft(case_id, pathway, body, actor=who.subject)
        except ValueError as exc:
            raise deliverable_error(exc) from exc

    @app.get("/api/cases/{case_id}/deliverables/revisions/{revision_id}",
             response_model=wire.DeliverableRevisionResponse)
    def get_deliverable_revision(case_id: str, revision_id: str, request: Request) -> dict[str, Any]:
        require_case(store, case_id, identity(request))
        revision = deliverables().revision_by_id(case_id, revision_id)
        if revision is None:
            raise HTTPException(status_code=404, detail="revision not found")
        return revision

    @app.post("/api/cases/{case_id}/deliverables/{pathway}/freeze", status_code=201,
              response_model=wire.FrozenDeliverableResponse)
    def freeze_deliverable(case_id: str, pathway: str, request: Request,
                           body: FreezeDeliverableRequest = Body(...)) -> dict[str, Any]:
        who = identity(request)
        require_case(store, case_id, who, write=True)
        try:
            return deliverables().freeze(case_id, body, actor=who.subject)
        except ValueError as exc:
            raise deliverable_error(exc) from exc

    @app.post("/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/approve",
              response_model=wire.FrozenDeliverableResponse)
    def approve_deliverable(case_id: str, deliverable_id: str, request: Request,
                            body: FileDeliverableRequest = Body(...)) -> dict[str, Any]:
        who = require_case_approver(case_id, request)
        try:
            return deliverables().approve_filing(case_id, deliverable_id, body, actor=who.subject)
        except ValueError as exc:
            raise deliverable_error(exc) from exc

    @app.post("/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/request-changes",
              response_model=wire.FrozenDeliverableResponse)
    def request_deliverable_changes(case_id: str, deliverable_id: str, request: Request,
                                    body: RequestDeliverableChangesRequest = Body(...)) -> dict[str, Any]:
        who = require_case_approver(case_id, request)
        try:
            return deliverables().request_changes(case_id, deliverable_id, body, actor=who.subject)
        except ValueError as exc:
            raise deliverable_error(exc) from exc

    @app.get("/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/export/{format_name}")
    def export_deliverable(case_id: str, deliverable_id: str, format_name: str, request: Request):
        from fastapi.responses import Response as _Response

        require_case(store, case_id, identity(request))
        service = deliverables()
        record = service.frozen_record(case_id, deliverable_id)
        if record is None:
            raise HTTPException(status_code=404, detail="deliverable not found")
        if record["status"] != "FILED":
            raise HTTPException(status_code=409, detail={"code": "DELIVERABLE_NOT_FILED"})
        try:
            content, sha256 = service.export(deliverable_id, format_name)
        except ValueError as exc:
            raise deliverable_error(exc) from exc
        return _Response(content=content, media_type="application/octet-stream",
                         headers={"cache-control": "no-store", "x-caos-sha256": sha256})

    # -- OpenAPI: named component schemas for the whole declared contract ----

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi
        from pydantic.json_schema import models_json_schema

        schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
        _, definitions = models_json_schema(
            [(model, "serialization") for model in _UNROUTED_SCHEMAS],
            ref_template="#/components/schemas/{model}",
        )
        for name, definition in definitions.get("$defs", {}).items():
            schema.setdefault("components", {}).setdefault("schemas", {}).setdefault(name, definition)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    return app
