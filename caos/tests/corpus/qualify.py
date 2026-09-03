#!/usr/bin/env python3
"""The enterprise qualification harness (Task 11, DECISIONS §14.20).

One parameterized matrix: binding × pathway × depth × pack × cold repetition.
Every cell is one fresh process over one fresh store, driven through the
ordinary provider path (`run.build_provider` for a live binding; the local
answer-keyed double for host control), the public API for admission and
runs, the engine for waiting and acceptance, and the worker's build function
for the model effect. Each result is scored against the pack's attested
answer key and bound to the provider identity (model, provider, adapter,
parameter/policy digest), the corpus digest, the build (commit, methodology
build id), the date, an expiry and the reviewer.

Fail-closed by construction: a missing byte, credential, answer key,
attestation or cell is a typed non-zero exit, never a skip; a refusal passes
only where the pack's answer key declares it; a host-control result is
labelled ORCHESTRATION_PROOF and can never read QUALIFIED.

    qualify.py plan    --binding host_control|live
    qualify.py cell    --binding … --pack C01 --pathway FULL_CREDIT --depth full --repetition 1 --reviewer NAME
    qualify.py matrix  --binding … --reviewer NAME [--repetitions 3] [--packs C01,C03]
    qualify.py verdict --binding …
    qualify.py pin     --reviewer NAME [--packs C02,…]
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
SERVER = TESTS.parent / "server"
ROOT = TESTS.parent.parent
for entry in (str(TESTS), str(SERVER)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from corpus import manifests as M  # noqa: E402
from corpus.answer_keyed_provider import ADAPTER_VERSION, MODEL_FIXTURES, AnswerKeyedProvider  # noqa: E402
from corpus.scoring import aggregate, score_cell  # noqa: E402

POLICY = {
    "schema_version": "caos.qualification-policy.v1",
    "live_repetitions": 3,
    "review_days": 90,
    "refusal_proves_pathway": False,
    "averaging": False,
    "host_control_is_qualification": False,
}
POLICY_DIGEST = hashlib.sha256(M.canonical(POLICY)).hexdigest()
RESULT_SCHEMA = "caos.qualification-result.v1"
DEFAULT_OUT = HERE / "evidence"
ANALYST = {"x-forwarded-user": "qualification-analyst"}
BINDINGS = ("host_control", "live")
EXIT_PASS, EXIT_FAIL, EXIT_BLOCKED = 0, 1, 2
Blocked = M.CorpusError


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_view() -> dict[str, Any]:
    from caos.config import Settings
    from caos.engine.provider import methodology_binding

    commit = os.environ.get("CAOS_BUILD_COMMIT", "").strip()
    if not commit:
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                    check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "unknown"
    build_id, manifest_digest = methodology_binding(Settings().deploy_v_root)
    return {
        "commit": commit,
        "methodology_build_id": build_id,
        "methodology_manifest_digest": manifest_digest,
        "image_digest": os.environ.get("CAOS_IMAGE_DIGEST") or None,
        "python": platform.python_version(),
    }


# --- bindings -------------------------------------------------------------------------


def cell_settings(kind: str, workdir: Path):
    from caos.config import Settings

    base = Settings.from_env()
    if kind == "live":
        if base.environment == "production":
            raise Blocked("ENVIRONMENT_INVALID", "the harness produces qualification evidence; it does not run in production")
        if base.provider_binding:
            raise Blocked("BINDING_CONFLICT", "CAOS_PROVIDER must be unset for a live binding")
        if not base.anthropic_api_key.strip():
            raise Blocked("CREDENTIALS_MISSING", "ANTHROPIC_API_KEY is not set; the live binding cannot be built")
    elif base.anthropic_api_key.strip() or base.openrouter_api_key.strip():
        raise Blocked("CREDENTIALS_PRESENT", "host control excludes provider credentials; unset them")
    return dataclasses.replace(
        base, storage_dir=workdir / "vault", database_url="", agent_execution_enabled=True, provider_binding="",
    )


def _tool_results(messages: list[dict[str, Any]]) -> list[Any]:
    return [
        json.loads(block["content"])
        for message in messages
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
    ]


class RecordingProvider:
    """Wraps any provider port and records what the host offered and what
    was delivered — the scorer's independent view of tools, prompts, evidence
    and calculation outputs. It changes nothing on the way through."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.identity = inner.identity
        self.calls: list[dict[str, Any]] = []
        self.delivered: dict[str, str] = {}
        self.calculation_outputs: list[str] = []

    def bind(self, sources: list[dict[str, Any]]) -> None:
        if hasattr(self.inner, "bind"):
            self.inner.bind(sources)

    def reset_observations(self) -> None:
        """Forget deliveries and calculation outputs (the per-run identity and
        call records stay); a paired run scores against its own evidence only."""
        self.delivered = {}
        self.calculation_outputs = []

    def count_tokens(self, request: Any) -> int:
        return self.inner.count_tokens(request)

    def create_message(self, request: Any) -> Any:
        prompt = json.loads(str(request.messages[0]["content"]).split("\n", 1)[1])
        identity = prompt["host_identity"]
        for result in _tool_results(request.messages):
            if isinstance(result, list):
                for row in result:
                    self.delivered[f"{row['source_id']}/{row['block_id']}"] = str(row.get("text") or "")
            elif isinstance(result, dict) and "output_digest" in result:
                self.calculation_outputs.append(json.dumps(result, sort_keys=True))
        response = self.inner.create_message(request)
        self.calls.append({
            "run_id": identity["run_id"],
            "module_id": identity["module_id"],
            "system_digest": hashlib.sha256(request.system.encode("utf-8")).hexdigest(),
            "tools": sorted(tool["name"] for tool in request.effective_tools()),
            "tool_calls": [block.name for block in response.content if block.type == "tool_use"],
            "host_identity": {field: identity.get(field) for field in ("issuer_name", "profile_id", "selection_id")},
        })
        return response

    def view(self, run_id: str) -> dict[str, Any]:
        calls = [call for call in self.calls if call["run_id"] == run_id]
        tools: dict[str, list[str]] = {}
        digests: dict[str, str] = {}
        for call in calls:
            tools.setdefault(call["module_id"], call["tools"])
            digests.setdefault(call["module_id"], call["system_digest"])
        return {
            "tools_by_module": tools, "system_digests": digests,
            "tool_calls": sorted({name for call in calls for name in call["tool_calls"]}),
            "host_identity": calls[0]["host_identity"] if calls else None,
            "identity_digest": self.identity.identity_digest,
        }


def build_binding(kind: str, settings: Any, key: dict[str, Any], cell_id: str) -> RecordingProvider:
    if kind == "host_control":
        return RecordingProvider(AnswerKeyedProvider(key, cell_id))
    from caos.engine.provider import AgentError
    from run import build_provider

    try:
        provider = build_provider(settings)
    except AgentError as refused:
        # The one binding builder refused (dual credentials, development-only
        # adapter, qualification record problems): a typed block, never a crash.
        raise Blocked("BINDING_REFUSED", refused.code) from refused
    if provider is None:
        raise Blocked("CREDENTIALS_MISSING", "no provider could be built from the environment")
    return RecordingProvider(provider)


def binding_identity_digest(kind: str) -> str:
    """The identity digest the current environment binds to, without a run."""
    from caos.engine.provider import host_control_identity

    if kind == "host_control":
        return host_control_identity(adapter_version=ADAPTER_VERSION).identity_digest
    from run import build_provider

    settings = cell_settings(kind, Path(os.environ.get("TMPDIR", "/tmp")) / "caos-qualification-identity")
    provider = build_provider(settings)
    if provider is None:
        raise Blocked("CREDENTIALS_MISSING", "no provider could be built from the environment")
    return provider.identity.identity_digest


# --- the plan --------------------------------------------------------------------------


def plan_cells() -> list[dict[str, Any]]:
    """Every required cell: each pack's applies_to rows, in pack order."""
    cells: list[dict[str, Any]] = []
    for pack_id in M.PACK_IDS:
        manifest = M.load_manifest(pack_id)
        for cell in manifest["applies_to"]:
            cells.append({
                "cell_key": f"{pack_id}/{cell['pathway']}/{cell['depth']}",
                "pack_id": pack_id, "pathway": cell["pathway"], "depth": cell["depth"],
                "outcome": cell["outcome"], "proves_pathway": cell["proves_pathway"],
                "kind": manifest["kind"], "stage": manifest["stage"],
                "bytes": manifest["bytes"]["source"] if manifest["documents"] or manifest["documents_from"] is None
                else M.load_manifest(manifest["documents_from"])["bytes"]["source"],
            })
    return cells


def blocked_external() -> list[dict[str, Any]]:
    rows = []
    for pack_id in M.PACK_IDS:
        manifest = M.load_manifest(pack_id)
        owner = manifest if manifest["documents"] or manifest["documents_from"] is None \
            else M.load_manifest(manifest["documents_from"])
        unpinned = [row["filename"] for row in M.document_rows(manifest) if row["sha256"] is None]
        scopes = sorted({approval["scope"] for approval in manifest["answer_key"]["approvals"]})
        if unpinned or "analyst" not in scopes:
            rows.append({
                "pack_id": pack_id, "bytes": owner["bytes"], "unpinned_documents": unpinned,
                "answer_key_scopes": scopes,
                "needs": ([f"{len(unpinned)} document(s) acquired, digest-pinned and placed under "
                           f"${M.EXTERNAL_ENV}/{owner['pack_id']}/"] if unpinned else [])
                + ([] if "analyst" in scopes else ["an analyst-scope approval on the answer key (reviewer, date, digest)"]),
            })
    return rows


# --- one cell ------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CellSpec:
    pack_id: str
    pathway: str
    depth: str
    repetition: int

    @property
    def cell_id(self) -> str:
        return f"{self.pathway}/{self.depth}"

    @property
    def cell_key(self) -> str:
        return f"{self.pack_id}/{self.pathway}/{self.depth}"


class CellRun:
    def __init__(self, spec: CellSpec, kind: str, workdir: Path, reviewer: str) -> None:
        self.spec = spec
        self.kind = kind
        self.workdir = workdir
        self.reviewer = reviewer
        # Environment first (credentials, binding), then the corpus (manifest,
        # key attestation, cell, bytes): the cheapest missing input names itself.
        self.settings = cell_settings(kind, workdir)
        self.manifest = M.load_manifest(spec.pack_id)
        self.key, self.raw_key = M.load_answer_key(spec.pack_id)
        self.rows = M.document_rows(self.manifest)
        self.approval = M.attest_answer_key(self.manifest, self.raw_key, kind)
        if spec.cell_id not in self.key["cells"]:
            raise Blocked("CELL_UNDECLARED", f"{spec.pack_id} declares no expectation for {spec.cell_id}")
        self.cell = self.key["cells"][spec.cell_id]
        self.documents = M.resolve_documents(self.manifest)
        self.provider = build_binding(kind, self.settings, self.key, spec.cell_id)
        self.store: Any = None
        self.engine: Any = None
        self.models: Any = None
        self.client: Any = None

    # -- lifecycle ------------------------------------------------------------------

    async def execute(self) -> dict[str, Any]:
        from fastapi.testclient import TestClient

        from caos.api import create_app
        from caos.engine.runtime import Engine
        from caos.models.service import ModelService
        from caos.storage.store import DomainStore

        self.workdir.mkdir(parents=True, exist_ok=True)
        self.store = DomainStore.from_url(f"sqlite:///{self.workdir / 'caos.db'}")
        self.engine = Engine.create(settings=self.settings, store=self.store,
                                    checkpoint_path=self.workdir / "checkpoints.db", provider=self.provider)
        self.models = ModelService(store=self.store, vault_dir=self.settings.storage_dir, engine=self.engine)
        try:
            with TestClient(create_app(settings=self.settings, store=self.store, engine=self.engine)) as client:
                self.client = client
                if self.manifest["stage"] == "ingest":
                    observed = self._ingest_stage()
                elif self.key.get("injection"):
                    observed = await self._injection_stage()
                else:
                    observed = await self._run_stage()
        finally:
            await self.engine.aclose()
            self.store.close()
        return observed

    # -- admission --------------------------------------------------------------------

    def _open_case(self, label: str) -> str:
        response = self.client.post("/api/cases", headers=ANALYST, json={
            "name": f"{self.spec.pack_id} {label}", "issuer": self.manifest["issuer"], "sector": "Qualification",
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    def _upload(self, case_id: str, document: M.ResolvedDocument) -> Any:
        return self.client.post(f"/api/cases/{case_id}/sources", headers=ANALYST,
                                files={"file": (document.filename, document.content, document.media_type)})

    def _intake(self, documents: list[M.ResolvedDocument], case_id: str | None = None) -> Any:
        return self.client.post(
            "/api/intake", headers=ANALYST,
            files=[("files", (document.filename, document.content, document.media_type)) for document in documents],
            data={"case_id": case_id} if case_id else None,
        )

    def _sources_view(self, source_ids: list[str]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
        sources = [self.store.get_source(source_id) for source_id in dict.fromkeys(source_ids)]
        blocks = {f"{source['id']}/{block['block_id']}": str(block.get("text") or "")
                  for source in sources for block in source.get("blocks") or []}
        by_filename = {source["filename"]: source["id"] for source in sources}
        return sources, blocks, by_filename

    def _admit(self, documents: list[M.ResolvedDocument], *, via_intake: bool) -> dict[str, Any]:
        """Admit the pack: the document-first intake when the answer key says
        the host classifies this pack onto the cell's route, else the advanced
        create-case and source routes (the intake never takes a route)."""
        if via_intake:
            response = self._intake(documents)
            if response.status_code != 201:
                detail = response.json().get("detail")
                code = detail.get("code") if isinstance(detail, dict) else None
                return {"case_id": None, "intake": {"status": "refused", "route": None, "dispositions": {},
                                                    "refusal_code": code, "http_status": response.status_code},
                        "run_id": None, "sources": [], "blocks": {}, "by_filename": {}}
            body = response.json()
            source_ids = [document["source_id"] for document in body["documents"] if document["source_id"]]
            sources, blocks, by_filename = self._sources_view(source_ids)
            by_filename.update({document["filename"]: document["source_id"] for document in body["documents"]
                                if document["source_id"]})
            return {
                "case_id": body["case_id"],
                "intake": {"status": body["status"], "route": [body["route"]["pathway"], body["route"]["depth"]],
                           "dispositions": {document["filename"]: document["disposition"] for document in body["documents"]},
                           "refusal_code": (body.get("refusal") or {}).get("code")},
                "run_id": (body.get("run") or {}).get("id"),
                "sources": sources, "blocks": blocks, "by_filename": by_filename,
            }
        case_id = self._open_case(self.spec.cell_id)
        source_ids = []
        for document in documents:
            response = self._upload(case_id, document)
            if response.status_code == 201:
                source_ids.append(response.json()["id"])
        sources, blocks, by_filename = self._sources_view(source_ids)
        return {"case_id": case_id, "intake": None, "run_id": None,
                "sources": sources, "blocks": blocks, "by_filename": by_filename}

    # -- runs ---------------------------------------------------------------------------------

    async def _drive(self, case_id: str, pathway: str, depth: str, run_id: str | None) -> tuple[dict[str, Any], float, str | None]:
        """Start (unless the intake already did) and wait for one run; approve
        a Deep Research plan on its exact proposed hash. Returns the terminal
        run, the wall-clock latency and a typed start refusal if any."""
        started = time.monotonic()
        if run_id is None:
            body: dict[str, Any] = {"pathway": pathway, "depth": depth}
            if pathway == "DEEP_RESEARCH":
                body["research_brief"] = self.key.get("research_brief")
            response = self.client.post(f"/api/cases/{case_id}/runs", headers=ANALYST, json=body)
            if response.status_code != 201:
                detail = response.json().get("detail")
                code = detail.get("code") if isinstance(detail, dict) else str(detail)[:80]
                return {"status": "refused", "error": {"code": code}, "nodes": [], "id": None}, time.monotonic() - started, code
            run_id = response.json()["id"]
        run = await self.engine.wait(run_id)
        if run["status"] == "paused" and (run.get("error") or {}).get("code") == "PLAN_APPROVAL_REQUIRED":
            await self.engine.approve_research_plan(
                run_id, plan_hash=run["research"]["proposed_plan_hash"], actor=ANALYST["x-forwarded-user"],
            )
            run = await self.engine.wait(run_id)
        return run, time.monotonic() - started, None

    async def _accept_and_build(self, case_id: str, run_id: str) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any]]:
        snapshot = await self.engine.accept(run_id, actor=ANALYST["x-forwarded-user"])
        readiness = self.models.readiness(case_id)
        build = None
        if readiness["status"] == "READY_TO_BUILD":
            queued = next(item for item in self.models.list_builds(case_id) if item["snapshot_id"] == snapshot["id"])
            self.models.run_build(queued["id"])
            build = self.models.builds.get_build(queued["id"])
        return snapshot, build, readiness

    def _outcome(self, run: dict[str, Any], pathway: str, depth: str) -> dict[str, Any]:
        from caos.engine.graphs import compiled_route

        expected_nodes: list[str] = []
        try:
            expected_nodes = list(compiled_route(pathway, depth).nodes)
        except Exception:  # noqa: BLE001 — a route the catalog cannot compile has no static shape to compare
            expected_nodes = []
        return {
            "status": run["status"], "error_code": (run.get("error") or {}).get("code"),
            "nodes": [node["module_id"] for node in run.get("nodes") or []], "expected_nodes": expected_nodes,
            "run_id": run.get("id"),
        }

    def _artifacts(self, run_id: str | None) -> list[dict[str, Any]]:
        if run_id is None:
            return []
        return [{
            "module_id": artifact["module_id"], "markdown": artifact.get("markdown") or "",
            "evidence_refs": (artifact.get("payload") or {}).get("evidence_refs") or [],
            "calculation_refs": (artifact.get("payload") or {}).get("calculation_refs") or [],
        } for artifact in self.engine.artifacts_for_run(run_id)]

    def _budget(self, run_id: str | None) -> dict[str, Any] | None:
        if run_id is None:
            return None
        budget = self.engine.runs.get_budget(run_id)
        return None if budget is None else {"used": dict(budget["used"]), "limits": dict(budget["limits"])}

    def _observe_intake_refusal(self) -> dict[str, Any]:
        """The answer key says the document-first intake refuses this pack
        (a typed clarification on the real bytes); observe it on a case of its
        own so the refusal is scored, then admit through the source routes."""
        response = self._intake(self.documents)
        detail = response.json().get("detail") if response.status_code != 201 else response.json().get("refusal")
        code = detail.get("code") if isinstance(detail, dict) else None
        return {"status": "refused" if response.status_code != 201 else response.json()["status"],
                "route": None, "dispositions": {}, "refusal_code": code, "http_status": response.status_code}

    async def _run_stage(self) -> dict[str, Any]:
        spec, cell = self.spec, self.cell
        intake_key = self.key.get("intake") or {}
        intake_route = intake_key.get("route")
        via_intake = intake_route is not None and list(intake_route) == [spec.pathway, spec.depth] \
            and cell.get("prerequisite") is None
        observed_refusal = self._observe_intake_refusal() if intake_key.get("status") == "refused" else None
        admitted = self._admit(self.documents, via_intake=via_intake)
        if observed_refusal is not None:
            admitted["intake"] = observed_refusal
        observed: dict[str, Any] = {
            "intake": admitted["intake"], "sources": admitted["by_filename"], "blocks": admitted["blocks"],
            "artifacts": [], "delivered": set(), "evidence_text": [], "calculation_outputs": [],
            "readiness": None, "build": None, "latency_seconds": 0.0, "budget": None,
            "exempt_modules": sorted(MODEL_FIXTURES) if self.kind == "host_control"
            and (cell.get("host_control") or {}).get("model_fixtures") else [],
        }
        if admitted["case_id"] is None:
            observed["outcome"] = {"status": "refused", "error_code": admitted["intake"]["refusal_code"],
                                   "nodes": [], "expected_nodes": [], "run_id": None}
            return observed
        case_id = admitted["case_id"]
        self.provider.bind(admitted["sources"])

        prerequisite = cell.get("prerequisite")
        if prerequisite:
            pathway, depth = prerequisite.split("/")
            if hasattr(self.provider.inner, "use_cell"):
                self.provider.inner.use_cell(prerequisite)
            run, _latency, _code = await self._drive(case_id, pathway, depth, None)
            if hasattr(self.provider.inner, "use_cell"):
                self.provider.inner.use_cell(spec.cell_id)
            if run["status"] != "succeeded":
                observed["outcome"] = {"status": "prerequisite_failed", "error_code": (run.get("error") or {}).get("code"),
                                       "nodes": [], "expected_nodes": [], "run_id": run.get("id"),
                                       "prerequisite": prerequisite}
                return observed
            _snapshot, build, readiness = await self._accept_and_build(case_id, run["id"])
            if build is None or build.get("status") != "READY":
                observed["outcome"] = {"status": "prerequisite_failed", "error_code": "PREREQUISITE_MODEL_NOT_READY",
                                       "nodes": [], "expected_nodes": [], "run_id": run.get("id"),
                                       "prerequisite": prerequisite, "readiness": readiness.get("status")}
                return observed

        run, latency, _code = await self._drive(case_id, spec.pathway, spec.depth, admitted["run_id"])
        observed["outcome"] = self._outcome(run, spec.pathway, spec.depth)
        observed["latency_seconds"] = latency
        run_id = run.get("id")
        observed["artifacts"] = self._artifacts(run_id)
        observed["delivered"] = set(self.provider.delivered)
        observed["evidence_text"] = list(self.provider.delivered.values())
        observed["calculation_outputs"] = list(self.provider.calculation_outputs)
        observed["budget"] = self._budget(run_id)
        if run["status"] == "succeeded" and cell["outcome"] == "succeeded" and (
            cell.get("model_effect") is not None or cell.get("readiness") is not None
        ):
            snapshot, build, readiness = await self._accept_and_build(case_id, run_id)
            observed["readiness"] = readiness
            observed["build"] = build
            observed["snapshot"] = snapshot
        observed["after_run"] = await self._after_run(case_id, run, observed)
        return observed

    async def _after_run(self, case_id: str, run: dict[str, Any], observed: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for step in self.cell.get("after_run") or []:
            name = step["step"]
            if name == "withdraw":
                source_id = observed["sources"].get(step["filename"])
                response = self.client.post(f"/api/cases/{case_id}/sources/{source_id}/withdraw", headers=ANALYST)
                results.append({"step": name, "pass": response.status_code == 200 and response.json()["withdrawn"] is True,
                                "detail": f"{step['filename']}: HTTP {response.status_code}"})
            elif name == "start_run_excludes":
                source_id = observed["sources"].get(step["filename"])
                pinned_before = run["plan"]["source_set_id"]
                fresh, _latency, code = await self._drive(case_id, step["pathway"], step["depth"], None)
                current = self.store.current_source_set(case_id)
                snapshot = observed.get("snapshot") or {}
                ok = (
                    code is None and (fresh.get("plan") or {}).get("source_set_id") not in (None, pinned_before)
                    and source_id not in current["source_ids"]
                    and (not snapshot or snapshot.get("source_set_id") == pinned_before)
                )
                results.append({"step": name, "pass": ok,
                                "detail": f"new set {current['version']} excludes {step['filename']}: {source_id not in current['source_ids']}; "
                                          f"start refusal {code}; earlier snapshot still on {pinned_before[:12]}"})
            else:
                results.append({"step": name, "pass": False, "detail": "unknown after_run step"})
        return results

    async def _injection_stage(self) -> dict[str, Any]:
        """C12: the same route over the pack with and without its hostile
        documents; the host must offer the same tools, the same verified
        authority, the same budget and the same identity, and no injected
        marker may reach an artifact."""
        spec = self.spec
        hostile = {row["filename"] for row in self.rows if row["analytical_role"] == "hostile"}
        control_documents = [document for document in self.documents if document.filename not in hostile]
        views: dict[str, dict[str, Any]] = {}
        observed: dict[str, Any] = {}
        for label, documents in (("control", control_documents), ("injected", self.documents)):
            admitted = self._admit(documents, via_intake=False)
            self.provider.reset_observations()
            self.provider.bind(admitted["sources"])
            run, latency, _code = await self._drive(admitted["case_id"], spec.pathway, spec.depth, None)
            run_id = run.get("id")
            view = self.provider.view(run_id) if run_id else {}
            budget = self._budget(run_id)
            views[label] = {**view, "nodes": [node["module_id"] for node in run.get("nodes") or []],
                            "budget_limits": (budget or {}).get("limits"), "status": run["status"]}
            if label == "injected":
                observed = {
                    "intake": None, "sources": admitted["by_filename"], "blocks": admitted["blocks"],
                    "outcome": self._outcome(run, spec.pathway, spec.depth), "latency_seconds": latency,
                    "artifacts": self._artifacts(run_id), "delivered": set(self.provider.delivered),
                    "evidence_text": list(self.provider.delivered.values()),
                    "calculation_outputs": list(self.provider.calculation_outputs), "budget": budget,
                    "readiness": None, "build": None, "exempt_modules": sorted(MODEL_FIXTURES)
                    if self.kind == "host_control" and (self.cell.get("host_control") or {}).get("model_fixtures") else [],
                }
        observed["injection"] = views
        return observed

    # -- ingest stage -----------------------------------------------------------------------

    def _ingest_stage(self) -> dict[str, Any]:
        by_name = {document.filename: document for document in self.documents}
        case_id = self._open_case("ingest")
        results: list[dict[str, Any]] = []
        for step in self.key["ingest_steps"]:
            via = step["via"]
            record: dict[str, Any] = {"filename": step.get("filename") or ",".join(step.get("files") or []),
                                      "via": via, "expect": step["expect"]}
            if via == "intake":
                documents = [by_name[name] for name in step["files"]]
                response = self._intake(documents)
                record["status"] = response.status_code
                body = response.json()
                if response.status_code == 201:
                    record["code"] = (body.get("refusal") or {}).get("code")
                    record["dispositions"] = {document["filename"]: document["disposition"] for document in body["documents"]}
                    target = step.get("filename")
                    if target:
                        row = next(document for document in body["documents"] if document["filename"] == target)
                        record["disposition"], record["document_type"] = row["disposition"], row["document_type"]
                else:
                    detail = body.get("detail")
                    record["code"] = detail.get("code") if isinstance(detail, dict) else None
                    record["detail"] = detail
                    record["findings"] = sorted({finding.get("code") for finding in (detail or {}).get("findings") or []}
                                                - {None}) if isinstance(detail, dict) else []
            else:
                document = by_name[step["filename"]]
                response = self._upload(case_id, document)
                record["status"] = response.status_code
                body = response.json()
                if response.status_code == 201:
                    record["blocks_at_least"] = len(body.get("blocks") or [])
                    record["source_id"] = body["id"]
                else:
                    detail = body.get("detail")
                    record["detail"] = detail
                    record["code"] = detail.get("code") if isinstance(detail, dict) else None
                if via == "loan_universe" and response.status_code == 201:
                    imported = self.client.post(f"/api/cases/{case_id}/rv/loan-universes", headers=ANALYST,
                                                json={"source_id": body["id"]})
                    record["status"] = imported.status_code
                    detail = imported.json().get("detail") if imported.status_code >= 400 else imported.json()
                    record["detail"] = detail
                    record["code"] = detail.get("code") if isinstance(detail, dict) else None
                    record["findings"] = sorted({finding.get("code") for finding in (detail or {}).get("findings") or []}
                                                - {None}) if isinstance(detail, dict) else []
            results.append(record)
        return {
            "intake": None, "sources": {}, "blocks": {}, "artifacts": [], "delivered": set(), "evidence_text": [],
            "calculation_outputs": [], "readiness": None, "build": None, "latency_seconds": 0.0, "budget": None,
            "outcome": {"status": "ingest", "error_code": None, "nodes": [], "expected_nodes": []},
            "ingest_results": results,
        }


# --- results ------------------------------------------------------------------------------


def _result_path(out: Path, kind: str, spec: CellSpec) -> Path:
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    directory = out / kind / spec.pack_id / f"{spec.pathway}-{spec.depth}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"rep-{spec.repetition}-{stamp}.json"


def _binding_view(identity_digest: str, build: dict[str, Any], corpus: str) -> dict[str, str]:
    return {
        "identity_digest": identity_digest, "commit": build["commit"],
        "methodology_build_id": build["methodology_build_id"],
        "methodology_manifest_digest": build["methodology_manifest_digest"],
        "corpus_digest": corpus, "policy_digest": POLICY_DIGEST,
    }


def run_cell(spec: CellSpec, kind: str, out: Path, reviewer: str, workdir: Path | None = None) -> tuple[int, dict[str, Any]]:
    import asyncio
    import tempfile

    if not reviewer.strip():
        raise Blocked("REVIEWER_MISSING", "every result binds a reviewer; pass --reviewer or set CAOS_QUALIFICATION_REVIEWER")
    started = _now()
    build = build_view()
    corpus = M.corpus_digest()
    base: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA, "cell_key": spec.cell_key, "cell_id": spec.cell_id,
        "pack_id": spec.pack_id, "pathway": spec.pathway, "depth": spec.depth, "repetition": spec.repetition,
        "binding_kind": kind, "policy": POLICY, "build": build, "date": _iso(started),
        "expires_at": _iso(started + timedelta(days=POLICY["review_days"])), "reviewer": reviewer,
        "corpus": {"corpus_digest": corpus},
    }
    workdir = workdir or Path(tempfile.mkdtemp(prefix=f"caos-qual-{spec.pack_id}-"))
    try:
        cell_run = CellRun(spec, kind, workdir, reviewer)
    except Blocked as blocked:
        identity = None
        try:
            identity = binding_identity_digest(kind)
        except Blocked:
            pass
        result = {**base, "verdict": "blocked", "blocked_code": blocked.code, "blocked_detail": blocked.detail,
                  "binding": None, "binding_view": _binding_view(identity or "unbound", build, corpus),
                  "result_id": None, "scores": None, "run": None}
        return EXIT_BLOCKED, result
    manifest = cell_run.manifest
    observed = asyncio.run(cell_run.execute())
    scores = score_cell(cell_run.key, cell_run.rows, spec.cell_id, observed)
    identity = cell_run.provider.identity.as_dict()
    result = {
        **base,
        "proves_pathway": cell_run.cell["proves_pathway"], "kind": manifest["kind"], "stage": manifest["stage"],
        "verdict": "pass" if scores["pass"] else "fail",
        "blocked_code": None, "blocked_detail": None,
        "binding": identity,
        "binding_view": _binding_view(identity["identity_digest"], build, corpus),
        "corpus": {
            "corpus_digest": corpus, "pack_version": manifest["version"],
            "manifest_digest": M.manifest_digest(spec.pack_id),
            "answer_key_version": manifest["answer_key"]["version"],
            "answer_key_digest": manifest["answer_key"]["sha256"], "approval": cell_run.approval,
        },
        "run": {
            "run_id": observed["outcome"].get("run_id"), "status": observed["outcome"]["status"],
            "error_code": observed["outcome"].get("error_code"),
            "latency_seconds": round(float(observed.get("latency_seconds") or 0.0), 3),
            "budget_used": (observed.get("budget") or {}).get("used"),
            "provider_calls": len(cell_run.provider.calls),
        },
        "scores": scores,
    }
    result["result_id"] = hashlib.sha256(M.canonical({key: value for key, value in result.items()
                                                      if key != "result_id"})).hexdigest()
    return (EXIT_PASS if scores["pass"] else EXIT_FAIL), result


def _write(out: Path, kind: str, spec: CellSpec, result: dict[str, Any]) -> Path:
    path = _result_path(out, kind, spec)
    path.write_text(json.dumps(result, indent=2, sort_keys=True, default=sorted) + "\n", encoding="utf-8")
    return path


def load_results(out: Path, kind: str) -> list[dict[str, Any]]:
    results = []
    for path in sorted((out / kind).rglob("rep-*.json")) if (out / kind).is_dir() else []:
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return results


def verdict(out: Path, kind: str, repetitions: int | None = None) -> dict[str, Any]:
    repetitions = repetitions or (POLICY["live_repetitions"] if kind == "live" else 1)
    current = _binding_view(binding_identity_digest(kind), build_view(), M.corpus_digest())
    summary = aggregate(plan_cells(), load_results(out, kind), repetitions=repetitions, binding_kind=kind,
                        current=current)
    summary["current"] = current
    summary["blocked_external"] = blocked_external()
    return summary


# --- CLI ---------------------------------------------------------------------------------------


def _print(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=sorted))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser, *, binding: bool = True) -> None:
        if binding:
            command.add_argument("--binding", choices=BINDINGS, required=True)
        command.add_argument("--out", type=Path, default=DEFAULT_OUT)

    common(sub.add_parser("plan"))
    cell = sub.add_parser("cell")
    common(cell)
    cell.add_argument("--pack", required=True)
    cell.add_argument("--pathway", required=True, choices=M.PATHWAYS)
    cell.add_argument("--depth", required=True, choices=M.DEPTHS)
    cell.add_argument("--repetition", type=int, default=1)
    cell.add_argument("--reviewer", default=os.environ.get("CAOS_QUALIFICATION_REVIEWER", ""))
    cell.add_argument("--workdir", type=Path, default=None)
    matrix = sub.add_parser("matrix")
    common(matrix)
    matrix.add_argument("--repetitions", type=int, default=None)
    matrix.add_argument("--packs", default="")
    matrix.add_argument("--reviewer", default=os.environ.get("CAOS_QUALIFICATION_REVIEWER", ""))
    verdict_parser = sub.add_parser("verdict")
    common(verdict_parser)
    verdict_parser.add_argument("--repetitions", type=int, default=None)
    pin = sub.add_parser("pin")
    pin.add_argument("--packs", default="")
    pin.add_argument("--reviewer", default=os.environ.get("CAOS_QUALIFICATION_REVIEWER", ""))
    pin.add_argument("--date", default=_now().date().isoformat())
    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            _print({"binding": args.binding, "policy": POLICY, "policy_digest": POLICY_DIGEST,
                    "repetitions": POLICY["live_repetitions"] if args.binding == "live" else 1,
                    "corpus_digest": M.corpus_digest(), "build": build_view(),
                    "cells": plan_cells(), "blocked_external": blocked_external()})
            return EXIT_PASS
        if args.command == "cell":
            spec = CellSpec(args.pack, args.pathway, args.depth, args.repetition)
            try:
                code, result = run_cell(spec, args.binding, args.out, args.reviewer, args.workdir)
            except Blocked:
                raise
            except Exception as exc:  # noqa: BLE001 — a crashed cell is retained as a failed result, never lost
                code, result = EXIT_FAIL, {
                    "schema_version": RESULT_SCHEMA, "cell_key": spec.cell_key, "cell_id": spec.cell_id,
                    "pack_id": spec.pack_id, "pathway": spec.pathway, "depth": spec.depth,
                    "repetition": spec.repetition, "binding_kind": args.binding, "verdict": "error",
                    "error_class": type(exc).__name__, "blocked_code": None, "blocked_detail": None,
                    "date": _iso(_now()), "reviewer": args.reviewer, "binding_view": None, "scores": None,
                    "run": None, "result_id": None,
                }
            path = _write(args.out, args.binding, spec, result)
            _print({"cell": spec.cell_key, "repetition": spec.repetition, "verdict": result["verdict"],
                    "blocked_code": result.get("blocked_code"), "blocked_detail": result.get("blocked_detail"),
                    "failed_dimensions": (result.get("scores") or {}).get("failed_dimensions"),
                    "run": result.get("run"), "result": str(path)})
            return code
        if args.command == "matrix":
            if not args.reviewer.strip():
                raise Blocked("REVIEWER_MISSING", "pass --reviewer or set CAOS_QUALIFICATION_REVIEWER")
            repetitions = args.repetitions or (POLICY["live_repetitions"] if args.binding == "live" else 1)
            selected = {pack for pack in args.packs.split(",") if pack}
            cells = [cell for cell in plan_cells() if not selected or cell["pack_id"] in selected]
            codes: dict[str, int] = {}
            for cell in cells:
                for repetition in range(1, repetitions + 1):
                    command = [sys.executable, str(Path(__file__).resolve()), "cell", "--binding", args.binding,
                               "--pack", cell["pack_id"], "--pathway", cell["pathway"], "--depth", cell["depth"],
                               "--repetition", str(repetition), "--reviewer", args.reviewer, "--out", str(args.out)]
                    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
                    codes[f"{cell['cell_key']}#{repetition}"] = completed.returncode
                    # One line per cell on stderr; stdout stays the summary JSON alone.
                    print(f"{cell['cell_key']} rep {repetition}: exit {completed.returncode}", file=sys.stderr)
                    if completed.returncode != EXIT_PASS:
                        print(completed.stdout[-1500:], file=sys.stderr)
                        print(completed.stderr[-1500:], file=sys.stderr)
            summary = verdict(args.out, args.binding, repetitions)
            summary["selected_packs"] = sorted(selected) or "all"
            summary["cell_exit_codes"] = codes
            _print(summary)
            if selected:
                return EXIT_PASS if all(code == EXIT_PASS for code in codes.values()) else max(codes.values(), default=EXIT_FAIL)
            return EXIT_PASS if summary["complete"] else EXIT_FAIL
        if args.command == "verdict":
            summary = verdict(args.out, args.binding, args.repetitions)
            _print(summary)
            return EXIT_PASS if summary["complete"] else EXIT_FAIL
        if args.command == "pin":
            if not args.reviewer.strip():
                raise Blocked("REVIEWER_MISSING", "pass --reviewer or set CAOS_QUALIFICATION_REVIEWER")
            packs = [pack for pack in args.packs.split(",") if pack] or list(M.PACK_IDS)
            for pack_id in packs:
                M.pin(pack_id, reviewer=args.reviewer, approved_at=args.date)
                print(f"pinned {pack_id}")
            return EXIT_PASS
    except Blocked as blocked:
        _print({"verdict": "blocked", "blocked_code": blocked.code, "blocked_detail": blocked.detail})
        return EXIT_BLOCKED
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
