"""Model Builder service: readiness, build queue, previews, Sign-Off, scenarios,
sensitivities, rebase, and hash-verified exports (DECISIONS §§1, 10.6, 12).

Rewritten against the framework store — nothing from LEGACY models/runtime.py
or revisions.py machinery (leases, heartbeats, fences) ports; the calculation
authority is caos.models.engine over the pinned Deploy V bundle. Sign-Off stays
a store CAS transaction, never an interrupt (§2). Calculation runs in-process
under the legacy 30s aggregate request deadline — a recorded deviation from
§10.8's process isolation (DECISIONS entry 2026-08-27): golden-input
calculations complete in well under a second and nothing here executes
untrusted code.
"""

from __future__ import annotations

import copy
import tempfile
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from ..contracts import (
    ModelPreviewRequest,
    ModelRebasePreviewRequest,
    ModelScenarioRequest,
    ModelSignOffRequest,
    OneWaySensitivityRequest,
    digest,
)
from ..atomic_files import (
    MAX_EXPORT_BYTES,
    VaultFileIntegrityError,
    VaultFileUnavailable,
    publish_hash_addressed_bytes,
    read_verified_vault_bytes,
)
from ..storage.models import ModelStore
from ..storage.store import DomainStore, now_iso
from .engine import CpModelBundle, ModelInputError, json_value, project_cp2b

CANONICAL_MODULES = ("CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2G")
MAX_EFFECTIVE_ASSUMPTIONS = 256
MAX_SENSITIVITY_POINTS = 41
MAX_CALCULATION_SECONDS = 30.0
MAX_ERROR_DETAIL_CHARS = 2_000
# ponytail: the per-build caches hold a whole resolved snapshot (six canonical
# documents plus the assumption rows), and this service lives as long as the
# process. Work is newest-build-first, so a handful of entries covers every
# real access pattern; without a bound the API and the worker retain every
# build they ever resolved. Raise it if a workload proves it needs to.
MAX_CACHED_BUILDS = 8
BUILD_ERROR_CODES = {
    "MODEL_INPUT_INVALID",
    "MODEL_CALCULATION_FAILED",
    "MODEL_EXPORT_FAILED",
    "MODEL_REVISION_EXPORT_FAILED",
    "MODEL_REVISION_EXPORT_RUNTIME_UNAVAILABLE",
}


class ModelBuildStale(ValueError):
    """MODEL_BUILD_STALE — the refusal names the current build authority."""

    def __init__(self, current_build: dict[str, Any] | None) -> None:
        self.current_build = current_build
        super().__init__("MODEL_BUILD_STALE")


class BuildIdentityChanged(ValueError):
    """The build row no longer carries the identity this result was computed
    from — a re-point requeued it, or another executor already published."""


class ModelCalculationTimeout(ValueError):
    def __init__(self) -> None:
        super().__init__("MODEL_CALCULATION_TIMEOUT")


# Model Builder renders each readiness blocker as humanizeCode(code) over
# `detail`; a null detail draws a heading above a blank line. These are written
# here rather than taken from the exception because ModelInputError messages
# interpolate host internals (bundle paths, table ids).
NO_ACCEPTED_AUTHORITY_DETAIL = "Accept a completed Full Credit run before building a model."
WRONG_PATHWAY_AUTHORITY_DETAIL = (
    "This case's accepted authority is not a Full Credit run. "
    "Accept a completed Full Credit run before building a model."
)
INPUTS_INVALID_DETAIL = (
    "The accepted Full Credit artifacts are missing, superseded, or fail "
    "CP-MODEL validation. Re-run Full Credit and accept it again."
)


class ModelService:
    def __init__(self, *, store: DomainStore, vault_dir: Path, engine: Any) -> None:
        self.store = store
        self.vault_dir = Path(vault_dir)
        self.engine = engine
        self.bundle = CpModelBundle(engine.settings.deploy_v_root)
        self.builds = ModelStore(store.engine)
        self._sign_off_lock = threading.Lock()
        # test seams
        self._dispatch_log: list[str] = []
        self._on_queue: list[Callable[[str], None]] = []
        self._fail_next_queue = False
        self._fail_next_dispatch = False
        self._fail_next_export = False
        self._forced_readiness: dict[str, str] = {}
        self._validate_bundle_calls: list[dict[str, Any]] = []
        self._runtime_sha_override: str | None = None
        self._deadline_exceeded = False
        self._export_input_reads = 0
        self._evolutions: dict[str, dict[str, tuple[str, ...]]] = {}
        self._resolved_cache: dict[str, dict[str, Any]] = {}
        self._defaults_cache: dict[str, tuple[list[dict[str, Any]], dict[str, Any]]] = {}
        engine.register_model_service(self)

    # -- engine hooks -------------------------------------------------------

    def on_accepted(self, run: dict[str, Any], actor: str) -> None:
        """Accept-time auto-queue. Acceptance is already durable; any failure
        here (readiness, queue, dispatch) leaves it standing."""
        if run.get("pathway") != "FULL_CREDIT":
            return
        self.queue_build(run["case_id"], actor)

    def active_job_count(self) -> int:
        """Model jobs share the run engine's MAX_ACTIVE_JOBS admission budget."""
        return self.builds.active_build_count()

    def _current_runtime(self) -> dict[str, Any]:
        runtime = dict(self.bundle.calculation_runtime)
        if self._runtime_sha_override is not None:
            runtime["sha256"] = self._runtime_sha_override
        return runtime

    # -- readiness and resolve ---------------------------------------------

    def _accepted_snapshot(self, case_id: str) -> dict[str, Any] | None:
        case = self.store.get_case(case_id)
        if case is None or not case.get("accepted_snapshot_id"):
            return None
        return self.engine.runs.get_snapshot(case["accepted_snapshot_id"])

    def _resolve_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """§10.6: only accepted FULL_CREDIT feeds model builds; the pathway
        check precedes any validate_bundle invocation."""
        runs = self.engine.runs
        run = runs.get_run(snapshot["run_id"])
        if run is None or run["pathway"] != "FULL_CREDIT":
            raise ModelInputError("accepted FULL_CREDIT run required",
                                  code="ACCEPTED_FULL_CREDIT_REQUIRED")
        by_module: dict[str, dict[str, Any]] = {}
        for reference in snapshot["artifacts"]:
            if reference["module_id"] not in CANONICAL_MODULES:
                continue
            artifact = runs.get_artifact(reference["id"])
            if artifact is None or artifact.get("digest") != reference.get("digest"):
                raise ModelInputError("canonical artifact is unavailable")
            by_module[reference["module_id"]] = artifact
        if set(by_module) != set(CANONICAL_MODULES):
            raise ModelInputError("canonical artifacts are incomplete")
        markdown = {module_id: by_module[module_id]["markdown"] for module_id in ("CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2G")}
        if any(text is None for text in markdown.values()) or by_module["CP-2A"]["markdown"] is None:
            raise ModelInputError("canonical markdown is unavailable")
        # CP-2B is CP-2A's registry-declared derived projection, recomputed
        # byte-identically from the pinned artifact (§12.7, MODULE_GRANULARITY).
        markdown["CP-2B"] = project_cp2b(
            by_module["CP-2A"]["markdown"],
            run_id=snapshot["run_id"],
            cp2a_artifact_digest=by_module["CP-2A"]["digest"],
            bundle=self.bundle,
        )
        validation = self.bundle.validate(
            markdown["CP-1"], markdown["CP-1A"], markdown["CP-1B"],
            markdown["CP-2"], markdown["CP-2B"], markdown["CP-2G"],
        )
        self._validate_bundle_calls.append({"case_id": snapshot["case_id"], "snapshot_id": snapshot["id"]})
        if validation.errors:
            raise ModelInputError("CP-MODEL bundle validation failed")
        source_set = self.store.source_set(snapshot["source_set_id"])
        if source_set is None or source_set.get("case_id") != snapshot["case_id"]:
            raise ModelInputError("accepted source set is unavailable")
        inventory = [
            {"module_id": module_id, "artifact_id": by_module[module_id]["id"], "digest": by_module[module_id]["digest"], "status": "READY"}
            for module_id in CANONICAL_MODULES
        ]
        inventory.append({
            "module_id": "CP-2B",
            "artifact_id": by_module["CP-2A"]["id"],
            "digest": digest(markdown["CP-2B"]),
            "derived_from": by_module["CP-2A"]["digest"],
            "status": "READY",
        })
        fingerprint = digest({
            "case_id": snapshot["case_id"],
            "accepted_run_id": snapshot["run_id"],
            "accepted_snapshot_id": snapshot["id"],
            "accepted_snapshot_digest": snapshot.get("digest"),
            "source_set": {"id": source_set["id"], "version": source_set["version"]},
            "artifacts": [{"module_id": item["module_id"], "digest": item["digest"]} for item in inventory],
            "methodology_build_id": self.engine.bundle.build_id,
            "calculation_runtime": self.bundle.calculation_runtime,
        })
        return {
            "snapshot": snapshot,
            "source_set": {"id": source_set["id"], "version": source_set["version"]},
            "artifact_inventory": inventory,
            "markdown": markdown,
            "input_fingerprint": fingerprint,
        }

    def readiness(self, case_id: str) -> dict[str, Any]:
        forced = self._forced_readiness.get(case_id)
        if forced:
            return {"status": forced, "module_id": "CP-MODEL", "snapshot_id": None, "blockers": [{"code": forced}]}
        snapshot = self._accepted_snapshot(case_id)
        if snapshot is None:
            return {"status": "NOT_READY", "module_id": "CP-MODEL", "snapshot_id": None,
                    "blockers": [{"code": "ACCEPTED_FULL_CREDIT_REQUIRED",
                                  "detail": NO_ACCEPTED_AUTHORITY_DETAIL}]}
        try:
            resolved = self._resolve_snapshot(snapshot)
        except (ModelInputError, ValueError) as exc:
            # A wrong-pathway precondition is not input corruption, and the two
            # need different statuses: only NOT_READY offers Model Builder's
            # "Open Run Console" way out, so collapsing them dead-ended the
            # commonest journey (accept an Earnings Update, open Model Builder)
            # behind an alarming, detail-less callout. Both details are written
            # here, never taken from the exception: the messages raised below
            # interpolate bundle paths and table ids.
            if getattr(exc, "code", None) == "ACCEPTED_FULL_CREDIT_REQUIRED":
                return {"status": "NOT_READY", "module_id": "CP-MODEL", "snapshot_id": snapshot["id"],
                        "blockers": [{"code": "ACCEPTED_FULL_CREDIT_REQUIRED",
                                      "detail": WRONG_PATHWAY_AUTHORITY_DETAIL}]}
            return {"status": "CANONICAL_MODEL_INPUTS_INVALID", "module_id": "CP-MODEL",
                    "snapshot_id": snapshot["id"],
                    "blockers": [{"code": "CANONICAL_MODEL_INPUTS_INVALID",
                                  "detail": INPUTS_INVALID_DETAIL}]}
        build = self.builds.build_for_fingerprint(case_id, resolved["input_fingerprint"])
        return {
            # A queued/building/failed job does not change what the accepted
            # authority is ready for — only a READY build advances the status.
            "status": "READY" if build and build["status"] == "READY" else "READY_TO_BUILD",
            "module_id": "CP-MODEL",
            "snapshot_id": snapshot["id"],
            # The wire's own name for the same fact. The route read this key and
            # the service never produced it, so Model Builder's authority panel
            # read "Not accepted" beside a build derived from that very snapshot.
            "accepted_snapshot": {"id": snapshot["id"], "run_id": snapshot["run_id"],
                                  "digest": snapshot.get("digest")},
            "input_fingerprint": resolved["input_fingerprint"],
            "source_set": resolved["source_set"],
            "requirements": resolved["artifact_inventory"],
            "calculation_runtime": self.bundle.calculation_runtime,
            "blockers": [],
            "build": build,
        }

    # -- queue --------------------------------------------------------------

    def queue_build(self, case_id: str, actor: str) -> dict[str, Any]:
        for callback in list(self._on_queue):
            callback(case_id)
        if self._fail_next_queue:
            self._fail_next_queue = False
            raise ValueError("MODEL_QUEUE_FAILED: injected queue failure")
        if self._forced_readiness.get(case_id):
            raise ValueError(f"MODEL_NOT_READY: {self._forced_readiness[case_id]}")
        snapshot = self._accepted_snapshot(case_id)
        if snapshot is None:
            raise ValueError("MODEL_NOT_READY: accept a completed Full Credit run first")
        try:
            resolved = self._resolve_snapshot(snapshot)
        except (ModelInputError, ValueError) as exc:
            if getattr(exc, "code", None) == "ACCEPTED_FULL_CREDIT_REQUIRED":
                raise ValueError("MODEL_NOT_READY: accept a completed Full Credit run first") from exc
            raise ValueError("MODEL_BUILD_INVALID: canonical model inputs are invalid") from exc
        registry = self.bundle.assumption_registry
        identity = {
            "accepted_run_id": snapshot["run_id"],
            "snapshot_id": snapshot["id"],
            "source_set_id": snapshot["source_set_id"],
            "input_fingerprint": resolved["input_fingerprint"],
            "methodology_build_id": self.engine.bundle.build_id,
            "calculation_runtime": self.bundle.calculation_runtime,
            "registry_version": registry["version"],
            "registry_digest": registry["digest"],
        }
        # At most one active (queued/building) job per case: a newer accepted
        # snapshot re-points the standing job rather than stacking a second.
        active = next((b for b in self.builds.list_builds(case_id) if b["status"] in ("QUEUED", "BUILDING")), None)
        if active is not None:
            if active["input_fingerprint"] != resolved["input_fingerprint"]:
                # Re-pointing a BUILDING row abandons that computation: it goes
                # back to QUEUED so a worker recomputes under the new identity,
                # and the abandoned executor's fingerprint-bound completion
                # no-ops instead of publishing a stale calculation.
                self.builds.update_build(active["id"], expected_status=("QUEUED", "BUILDING"),
                                         status="QUEUED", **identity)
                self._resolved_cache.pop(active["id"], None)
                self._defaults_cache.pop(active["id"], None)
            record, created = self.builds.get_build(active["id"]), False
        else:
            # Model jobs and runs share one admission budget (Appendix A:
            # MAX_ACTIVE_JOBS checked at run AND build start). Re-pointing an
            # existing job never consumes a new slot.
            from ..engine.budget import MAX_ACTIVE_JOBS

            occupied = (
                self.engine.runs.active_admission_count()
                + getattr(self.engine, "_admission_offset", 0)
                + self.builds.active_build_count()
            )
            if occupied >= MAX_ACTIVE_JOBS:
                raise ValueError("ADMISSION_BUSY: active job ceiling reached")
            record, created = self.builds.queue_build({"case_id": case_id, **identity}, actor)
        self._dispatch(record["id"])
        return {**record, "created": created}

    def queue_build_pinned_for_tests(self, case_id: str, *, snapshot_id: str) -> dict[str, Any]:
        snapshot = self.engine.runs.get_snapshot(snapshot_id)
        case = self.store.get_case(case_id)
        if (
            snapshot is None
            or case is None
            or snapshot["case_id"] != case_id
            or case.get("accepted_snapshot_id") != snapshot_id
        ):
            raise ValueError("MODEL_BUILD_INVALID: snapshot is not this case's accepted authority")
        return self.queue_build(case_id, "analyst")

    def _dispatch(self, build_id: str) -> None:
        if self._fail_next_dispatch:
            self._fail_next_dispatch = False
            raise ValueError("MODEL_DISPATCH_FAILED: injected dispatch failure")
        self._dispatch_log.append(build_id)

    # -- reads --------------------------------------------------------------

    def build(self, build_id: str) -> dict[str, Any] | None:
        return self.builds.get_build(build_id)

    def list_builds(self, case_id: str) -> list[dict[str, Any]]:
        return self.builds.list_builds(case_id)

    def current_build(self, case_id: str) -> dict[str, Any] | None:
        return self.builds.current_build(case_id)

    def worksheet(self, build_id: str) -> dict[str, Any] | None:
        build = self.builds.get_build(build_id)
        return build.get("payload") if build else None

    # -- build execution -----------------------------------------------------

    def _resolved_inputs(self, build: dict[str, Any]) -> dict[str, Any]:
        cached = self._resolved_cache.get(build["id"])
        if cached is not None:
            return cached
        snapshot = self.engine.runs.get_snapshot(build["snapshot_id"])
        if snapshot is None or snapshot["case_id"] != build["case_id"]:
            raise ModelInputError("model snapshot is unavailable")
        resolved = self._resolve_snapshot(snapshot)
        if resolved["input_fingerprint"] != build["input_fingerprint"]:
            raise ModelInputError("model inputs changed")
        _remember(self._resolved_cache, build["id"], resolved)
        return resolved

    @staticmethod
    def _write_inputs(directory: Path, markdown: dict[str, str]) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        for module_id, content in markdown.items():
            path = directory / f"{module_id.lower()}.md"
            path.write_text(content, encoding="utf-8")
            paths[module_id] = path
        return paths

    def _calculate(self, build: dict[str, Any], effective: list[dict[str, Any]] | None, deadline: float) -> tuple[Any, Any]:
        self._check_deadline(deadline)
        if effective is not None and len(effective) > MAX_EFFECTIVE_ASSUMPTIONS:
            raise ValueError("MODEL_ASSUMPTION_LIMIT")
        resolved = self._resolved_inputs(build)
        with tempfile.TemporaryDirectory(prefix="caos-model-") as temporary:
            paths = self._write_inputs(Path(temporary), resolved["markdown"])
            model, calculations = self.bundle.calculate(paths, effective_assumptions=effective)
        self._check_deadline(deadline)
        return model, calculations

    def _defaults(self, build: dict[str, Any], deadline: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        cached = self._defaults_cache.get(build["id"])
        if cached is None:
            model, calculations = self._calculate(build, None, deadline)
            rows = _assumption_rows(model)
            rows = self._apply_evolution(build["id"], rows)
            cached = (rows, _annual_outputs(calculations))
            _remember(self._defaults_cache, build["id"], cached)
        return copy.deepcopy(cached[0]), copy.deepcopy(cached[1])

    def _apply_evolution(self, build_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evolution = self._evolutions.get(build_id)
        if not evolution:
            return rows
        removed = set(evolution.get("removed", ()))
        changed = set(evolution.get("source_context_changed", ()))
        result = []
        for row in rows:
            if row["assumption_id"] in removed:
                continue
            if row["assumption_id"] in changed:
                row = copy.deepcopy(row)
                row["source_context"]["gap_code"] = "SOURCE_CONTEXT_EVOLVED"
                row["source_context_digest"] = digest(row["source_context"])
            result.append(row)
        return result

    def run_build_for_tests(self, build_id: str) -> dict[str, Any]:
        build = self.builds.get_build(build_id)
        if build is None:
            raise ValueError("MODEL_BUILD_NOT_FOUND")
        if build["status"] == "READY":
            return build
        if not self.builds.update_build(build_id, expected_status=("QUEUED", "FAILED"), status="BUILDING"):
            # Lost the claim: another executor owns this row. Losing is not a
            # failure — never compute, never touch the winner's state.
            return self.builds.get_build(build_id)  # type: ignore[return-value]
        # The CLAIMED row is the authority; the pre-claim read may already be stale.
        build = self.builds.get_build(build_id)
        fingerprint = build["input_fingerprint"]  # type: ignore[index]
        try:
            result, identity = self._compute_build_result(build)
            self._complete(build_id, result, identity, expected_fingerprint=fingerprint)
        except BuildIdentityChanged:
            # Re-pointed mid-flight: the requeued row wins, this calculation dies.
            pass
        except ModelInputError:
            self._fail(build_id, "MODEL_INPUT_INVALID", "The accepted model inputs are invalid.", fingerprint)
        except ModelCalculationTimeout:
            raise
        except ValueError:
            raise
        except Exception:
            self._fail(build_id, "MODEL_CALCULATION_FAILED", "The model calculation did not complete.", fingerprint)
        return self.builds.get_build(build_id)  # type: ignore[return-value]

    def _compute_build_result(self, build: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        deadline = self._new_deadline()
        model, calculations = self._calculate(build, None, deadline)
        serialized = self.bundle.serialize_workbook(model, calculations)
        result = {
            "payload": serialized["payload"],
            "payload_digest": digest(serialized["payload"]),
            "qa": serialized["qa"],
        }
        rows = self._apply_evolution(build["id"], _assumption_rows(model))
        outputs = _annual_outputs(calculations)
        _remember(self._defaults_cache, build["id"], (rows, outputs))
        identity = {"assumptions_digest": digest(rows), "outputs_digest": digest(outputs)}
        return result, identity

    def valid_build_result_for_tests(self, build_id: str) -> dict[str, Any]:
        build = self.builds.get_build(build_id)
        if build is None:
            raise ValueError("MODEL_BUILD_NOT_FOUND")
        result, _identity = self._compute_build_result(build)
        return result

    def complete_build_for_tests(self, build_id: str, result: dict[str, Any]) -> dict[str, Any]:
        self._validate_result(result)
        self._complete(build_id, copy.deepcopy(result), {})
        return self.builds.get_build(build_id)  # type: ignore[return-value]

    def _complete(self, build_id: str, result: dict[str, Any], identity: dict[str, Any],
                  *, expected_fingerprint: str | None = None) -> None:
        self._validate_result(result)
        changed = self.builds.update_build(
            build_id, expected_status=("QUEUED", "BUILDING"),
            expected_input_fingerprint=expected_fingerprint,
            status="READY", payload=result["payload"], payload_digest=result["payload_digest"],
            qa=result["qa"], error=None, completed_at=now_iso(), **identity,
        )
        if not changed:
            raise BuildIdentityChanged("MODEL_RESULT_INVALID: build is not completable")

    @staticmethod
    def _validate_result(result: dict[str, Any]) -> None:
        def invalid(reason: str) -> ValueError:
            return ValueError(f"MODEL_RESULT_INVALID: {reason}")

        if not isinstance(result, dict) or set(result) != {"payload", "payload_digest", "qa"}:
            raise invalid("result must carry exactly payload, payload_digest, qa")
        payload, qa = result["payload"], result["qa"]
        if not isinstance(qa, dict) or not isinstance(qa.get("status"), str):
            raise invalid("qa status is missing")
        if not isinstance(payload, dict) or not isinstance(payload.get("tabs"), list):
            raise invalid("payload tabs must be a list")
        for tab in payload["tabs"]:
            if not isinstance(tab, dict) or not isinstance(tab.get("cells"), list):
                raise invalid("malformed worksheet tab")
            for cell in tab["cells"]:
                if not isinstance(cell, dict) or not {"address", "row", "column", "value", "value_type"} <= set(cell):
                    raise invalid("incomplete worksheet cell")
                value = cell["value"]
                if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                    raise invalid("non-finite worksheet value")
        if result["payload_digest"] != digest(payload):
            raise invalid("payload digest mismatch")

    def _fail(self, build_id: str, code: str, detail: str, expected_fingerprint: str | None = None) -> None:
        self._validate_error(code, detail)
        self.builds.update_build(build_id, expected_status=("QUEUED", "BUILDING"),
                                 expected_input_fingerprint=expected_fingerprint,
                                 status="FAILED", error={"code": code, "detail": detail})

    @staticmethod
    def _validate_error(code: str, detail: str) -> None:
        if code not in BUILD_ERROR_CODES or not isinstance(detail, str) or len(detail) > MAX_ERROR_DETAIL_CHARS:
            raise ValueError("MODEL_ERROR_INVALID: failure records are bounded")

    def fail_build_for_tests(self, build_id: str, *, code: str, detail: str) -> None:
        self._validate_error(code, detail)
        changed = self.builds.update_build(build_id, expected_status=("QUEUED", "BUILDING"),
                                           status="FAILED", error={"code": code, "detail": detail})
        if not changed:
            raise ValueError("MODEL_ERROR_INVALID: build is not failable")

    def insert_ready_build_for_tests(self, case_id: str, *, build_id: str, queued_at: str) -> dict[str, Any]:
        return self.builds.insert_build_row({
            "id": build_id, "case_id": case_id, "status": "READY",
            "input_fingerprint": f"fixture-{build_id}", "queued_at": queued_at,
            "created_by": "test", "calculation_runtime": self.bundle.calculation_runtime,
        })

    # -- deadline -----------------------------------------------------------

    def _new_deadline(self) -> float:
        if self._deadline_exceeded:
            return time.monotonic() - 1.0
        return time.monotonic() + MAX_CALCULATION_SECONDS

    @staticmethod
    def _check_deadline(deadline: float) -> None:
        if deadline - time.monotonic() <= 0:
            raise ModelCalculationTimeout()

    # -- registry, previews, sign-off ---------------------------------------

    def _require_current(self, case_id: str, build_id: str) -> dict[str, Any]:
        build = self.builds.get_build(build_id)
        if build is None or build["case_id"] != case_id or build["status"] != "READY":
            raise ValueError("MODEL_BUILD_NOT_READY")
        current = self.builds.current_build(case_id)
        if current is None or current["id"] != build_id:
            raise ModelBuildStale(current)
        return build

    def _validate_registry(self, registry_version: str, registry_digest: str) -> None:
        registry = self.bundle.assumption_registry
        if registry_version != registry["version"] or registry_digest != registry["digest"]:
            raise ValueError("MODEL_REGISTRY_STALE")

    def _parent(self, case_id: str, revision_id: str | None) -> dict[str, Any] | None:
        if revision_id is None:
            return None
        parent = self.builds.get_revision(revision_id)
        if parent is None or parent.get("case_id") != case_id:
            raise ValueError("MODEL_REVISION_NOT_FOUND")
        return parent

    def assumption_registry(self, case_id: str, build_id: str) -> dict[str, Any]:
        build = self._require_current(case_id, build_id)
        defaults, _outputs = self._defaults(build, self._new_deadline())
        registry = copy.deepcopy(self.bundle.assumption_registry)
        return {
            **registry,
            "build_id": build_id,
            "snapshot_id": build["snapshot_id"],
            "input_fingerprint": build["input_fingerprint"],
            "defaults": defaults,
        }

    def preview(self, case_id: str, request: ModelPreviewRequest, *, _deadline: float | None = None) -> dict[str, Any]:
        deadline = _deadline if _deadline is not None else self._new_deadline()
        self._check_deadline(deadline)
        build = self._require_current(case_id, request.build_id)
        self._validate_registry(request.registry_version, request.registry_digest)
        parent = self._parent(case_id, request.parent_revision_id)
        if parent is not None and parent.get("build_id") != request.build_id:
            raise ValueError("MODEL_REVISION_STALE")
        rows = [item.model_dump() for item in request.assumptions]
        defaults, default_outputs = self._defaults(build, deadline)
        model, calculations = self._calculate(build, rows, deadline)
        normalized = _with_default_context(self._apply_evolution(build["id"], _assumption_rows(model)), defaults)
        outputs = _annual_outputs(calculations)
        baseline = parent["outputs"] if parent is not None else default_outputs
        envelope = {
            "case_id": case_id,
            "build_id": request.build_id,
            "snapshot_id": build["snapshot_id"],
            "build_input_fingerprint": build["input_fingerprint"],
            "build_payload_digest": build["payload_digest"],
            "registry_version": request.registry_version,
            "registry_digest": request.registry_digest,
            "calculation_contract_version": self.bundle.calculation_runtime["calculation_contract_version"],
            "parent_revision_id": request.parent_revision_id,
            "draft_generation": request.draft_generation,
            "effective_assumptions": normalized,
            "assumptions_digest": digest(normalized),
            "outputs": outputs,
            "outputs_digest": digest(outputs),
            "deltas": _output_deltas(baseline, outputs),
        }
        envelope["preview_digest"] = digest(envelope)
        return envelope

    def _validate_build_identity(self, case_id: str, build: dict[str, Any], deadline: float) -> None:
        """Sign-off validates the exact current build identity — every pinned
        field recomputed, any mismatch refused as MODEL_REVISION_INVALID."""

        def invalid(field: str) -> ValueError:
            return ValueError(f"MODEL_REVISION_INVALID: build identity mismatch on {field}")

        if build["payload_digest"] != digest(build["payload"]):
            raise invalid("payload_digest")
        if build["registry_digest"] != self.bundle.assumption_registry["digest"]:
            raise invalid("registry_digest")
        case = self.store.get_case(case_id)
        if case is None or build["snapshot_id"] != case.get("accepted_snapshot_id"):
            raise invalid("snapshot_id")
        snapshot = self.engine.runs.get_snapshot(build["snapshot_id"])
        if snapshot is None:
            raise invalid("snapshot_id")
        try:
            resolved = self._resolve_snapshot(snapshot)
        except (ModelInputError, ValueError) as exc:
            raise invalid("input_fingerprint") from exc
        if resolved["input_fingerprint"] != build["input_fingerprint"]:
            raise invalid("input_fingerprint")
        defaults, outputs = self._defaults(build, deadline)
        if digest(defaults) != build["assumptions_digest"]:
            raise invalid("assumptions_digest")
        if digest(outputs) != build["outputs_digest"]:
            raise invalid("outputs_digest")

    def sign_off(self, case_id: str, request: ModelSignOffRequest, *, actor: str = "analyst") -> dict[str, Any]:
        deadline = self._new_deadline()
        with self._sign_off_lock:
            build = self._require_current(case_id, request.build_id)
            self._validate_build_identity(case_id, build, deadline)
            preview = self.preview(case_id, request, _deadline=deadline)
            if preview["preview_digest"] != request.preview_digest:
                raise ValueError("MODEL_PREVIEW_STALE")
            record = {key: preview[key] for key in (
                "case_id", "build_id", "snapshot_id", "build_input_fingerprint", "build_payload_digest",
                "registry_version", "registry_digest", "calculation_contract_version",
                "effective_assumptions", "assumptions_digest", "outputs", "outputs_digest",
                "preview_digest", "parent_revision_id",
            )}
            record["note"] = request.note
            current = self.builds.current_build(case_id)
            if current is None or current["id"] != request.build_id:
                raise ModelBuildStale(current)
            signed = self.builds.sign_off_revision(
                case_id, record, actor, request.expected_head_revision_id, self.store._audit,
            )
        return {**signed, "state": self._revision_state(case_id, signed)}

    def _revision_state(self, case_id: str, revision: dict[str, Any]) -> str:
        current = self.builds.current_build(case_id)
        if current is None or revision.get("build_id") != current["id"]:
            return "STALE"
        head = self.builds.head_revision(case_id)
        return "ACTIVE" if head is not None and head["id"] == revision["id"] else "SUPERSEDED"

    def revisions(self, case_id: str) -> list[dict[str, Any]]:
        return [
            {**revision, "state": self._revision_state(case_id, revision)}
            for revision in self.builds.list_revisions(case_id)
        ]

    def head_revision(self, case_id: str) -> dict[str, Any] | None:
        head = self.builds.head_revision(case_id)
        if head is None:
            return None
        return {**head, "state": self._revision_state(case_id, head)}

    def default_outputs(self, case_id: str, build_id: str) -> dict[str, Any]:
        """The current build's outputs under registry defaults (the fallback
        model authority a Deliverable may pin when no revision is signed)."""
        build = self._require_current(case_id, build_id)
        _defaults_rows, outputs = self._defaults(build, self._new_deadline())
        return outputs

    # -- transient calculations ---------------------------------------------

    def scenario(self, case_id: str, request: ModelScenarioRequest) -> dict[str, Any]:
        deadline = self._new_deadline()
        self._check_deadline(deadline)
        build = self._require_current(case_id, request.build_id)
        self._validate_registry(request.registry_version, request.registry_digest)
        parent = self._parent(case_id, request.base_revision_id)
        if parent is not None and parent.get("build_id") != request.build_id:
            raise ValueError("MODEL_REVISION_STALE")
        defaults, default_outputs = self._defaults(build, deadline)
        baseline_assumptions = copy.deepcopy(parent["effective_assumptions"] if parent else defaults)
        baseline_outputs = parent["outputs"] if parent else default_outputs
        by_key = {(row["assumption_id"], row["case"], row["period_id"]): row for row in baseline_assumptions}
        seen: set[tuple[str, str, str]] = set()
        for shock in request.shocks:
            key = (shock.assumption_id, shock.case, shock.period_id)
            if key in seen or key not in by_key or by_key[key]["status"] != "READY":
                raise ValueError("MODEL_SCENARIO_INVALID")
            seen.add(key)
            by_key[key]["value"] = shock.value
        model, calculations = self._calculate(build, baseline_assumptions, deadline)
        normalized = _with_default_context(self._apply_evolution(build["id"], _assumption_rows(model)), defaults)
        outputs = _annual_outputs(calculations)
        scenario = {
            "case_id": case_id,
            "build_id": request.build_id,
            "base_revision_id": request.base_revision_id,
            "registry_version": request.registry_version,
            "registry_digest": request.registry_digest,
            "draft_generation": request.draft_generation,
            "effective_assumptions": normalized,
            "assumptions_digest": digest(normalized),
            "outputs": outputs,
            "outputs_digest": digest(outputs),
            "deltas": _output_deltas(baseline_outputs, outputs),
        }
        return {
            "draft_generation": request.draft_generation,
            "baseline": baseline_outputs,
            "scenario": scenario,
            "scenario_digest": digest(scenario),
        }

    def one_way(self, case_id: str, request: OneWaySensitivityRequest) -> dict[str, Any]:
        deadline = self._new_deadline()
        self._check_deadline(deadline)
        build = self._require_current(case_id, request.build_id)
        self._validate_registry(request.registry_version, request.registry_digest)
        parent = self._parent(case_id, request.base_revision_id)
        if parent is not None and parent.get("build_id") != request.build_id:
            raise ValueError("MODEL_REVISION_STALE")
        defaults, default_outputs = self._defaults(build, deadline)
        baseline_assumptions = copy.deepcopy(parent["effective_assumptions"] if parent else defaults)
        baseline_outputs = parent["outputs"] if parent else default_outputs
        if not _has_output(baseline_outputs, request.case, request.output_id):
            raise ValueError("MODEL_SENSITIVITY_OUTPUT_INVALID")
        definition = next(
            (item for item in self.bundle.assumption_registry["definitions"] if item["assumption_id"] == request.assumption_id),
            None,
        )
        selected = [
            row for row in baseline_assumptions
            if row["assumption_id"] == request.assumption_id and row["case"] == request.case
            and (request.period_scope == "ALL" or row["period_id"] == request.period_scope)
        ]
        if definition is None or not selected or any(row["status"] != "READY" for row in selected):
            raise ValueError("MODEL_SENSITIVITY_INVALID")
        base_value = Decimal(str(selected[0]["value"]))
        default_range = Decimal(str(definition["sensitivity_default"]["range"]))
        try:
            chosen_step = Decimal(str(request.step)) if request.step is not None else Decimal(str(definition["sensitivity_default"]["step"]))
            lower = Decimal(str(request.minimum)) if request.minimum is not None else base_value - default_range
            upper = Decimal(str(request.maximum)) if request.maximum is not None else base_value + default_range
        except InvalidOperation as exc:
            raise ValueError("MODEL_SENSITIVITY_INVALID") from exc
        hard_min = Decimal(str(definition["hard_min"]))
        hard_max = Decimal(str(definition["hard_max"]))
        if chosen_step <= 0 or lower > upper or lower < hard_min or upper > hard_max:
            raise ValueError("MODEL_SENSITIVITY_INVALID")
        point_count = int((upper - lower) / chosen_step) + 1
        if point_count > MAX_SENSITIVITY_POINTS or lower + chosen_step * (point_count - 1) != upper:
            raise ValueError("MODEL_SENSITIVITY_POINT_LIMIT")
        selected_keys = {(row["assumption_id"], row["case"], row["period_id"]) for row in selected}
        points: list[dict[str, Any]] = []
        breakpoint_record: dict[str, Any] | None = None
        for index in range(point_count):
            value = lower + chosen_step * index
            effective = copy.deepcopy(baseline_assumptions)
            for row in effective:
                if (row["assumption_id"], row["case"], row["period_id"]) in selected_keys:
                    row["value"] = float(value)
            _model, calculations = self._calculate(build, effective, deadline)
            outputs = _annual_outputs(calculations)
            point = {"value": format(value, "f"), "outputs": outputs, "deltas": _output_deltas(baseline_outputs, outputs)}
            points.append(point)
            breaches = [
                breach for breach in outputs.get(f"{request.case}_first_breaches", [])
                if _breach_matches_output(breach, request.output_id)
            ]
            if breakpoint_record is None and breaches:
                breakpoint_record = {"value": point["value"], "threshold": breaches[0]}
        return {
            "case_id": case_id,
            "build_id": request.build_id,
            "base_revision_id": request.base_revision_id,
            "registry_version": request.registry_version,
            "registry_digest": request.registry_digest,
            "assumption_id": request.assumption_id,
            "case": request.case,
            "period_scope": request.period_scope,
            "output_id": request.output_id,
            "draft_generation": request.draft_generation,
            "points": points,
            "breakpoint": breakpoint_record,
        }

    def rebase_preview(self, case_id: str, request: ModelRebasePreviewRequest) -> dict[str, Any]:
        deadline = self._new_deadline()
        source = self._parent(case_id, request.revision_id)
        if source is None:
            raise ValueError("MODEL_REVISION_NOT_FOUND")
        build = self._require_current(case_id, request.build_id)
        new_defaults, _outputs = self._defaults(build, deadline)
        source_by_key = {
            (row["assumption_id"], row["case"], row["period_id"]): row
            for row in source["effective_assumptions"]
        }
        definitions = {item["assumption_id"]: item for item in self.bundle.assumption_registry["definitions"]}
        candidate = copy.deepcopy(new_defaults)
        candidate_by_key = {(row["assumption_id"], row["case"], row["period_id"]): row for row in candidate}
        compatible: list[dict[str, Any]] = []
        changed: list[dict[str, Any]] = []
        invalidated: list[dict[str, Any]] = []
        for key in sorted(set(source_by_key).difference(candidate_by_key)):
            invalidated.append({"identity": list(key), "reason": "ASSUMPTION_NO_LONGER_MAPS"})
        for row in candidate:
            key = (row["assumption_id"], row["case"], row["period_id"])
            prior = source_by_key.get(key)
            definition = definitions.get(row["assumption_id"])
            invalid_reason = None
            if prior is None:
                invalid_reason = "ASSUMPTION_ADDED"
            elif definition is None:
                invalid_reason = "ASSUMPTION_NO_LONGER_MAPS"
            elif prior["unit"] != row["unit"] or prior["status"] != row["status"]:
                invalid_reason = "ASSUMPTION_METADATA_CHANGED"
            elif not isinstance(prior.get("source_context_digest"), str):
                invalid_reason = "ASSUMPTION_CONTEXT_UNAVAILABLE"
            elif prior["status"] == "READY":
                value = Decimal(str(prior["value"]))
                if value < Decimal(str(definition["hard_min"])) or value > Decimal(str(definition["hard_max"])):
                    invalid_reason = "ASSUMPTION_OUTSIDE_NEW_BOUNDS"
            if invalid_reason:
                invalidated.append({"identity": list(key), "reason": invalid_reason})
                continue
            row["value"] = prior["value"]
            row["gap_code"] = prior.get("gap_code", "")
            item = {"identity": list(key), "value": prior["value"]}
            if any(
                prior.get(field) != row.get(field)
                for field in ("default_value", "default_status", "default_gap_code", "source_context_digest")
            ):
                changed.append(item)
            else:
                compatible.append(item)
        preview = None
        if not invalidated:
            registry = self.bundle.assumption_registry
            preview = self.preview(case_id, ModelPreviewRequest.model_validate({
                "build_id": request.build_id,
                "parent_revision_id": None,
                "registry_version": registry["version"],
                "registry_digest": registry["digest"],
                "assumptions": candidate,
                "draft_generation": request.draft_generation,
            }), _deadline=deadline)
        return {
            "case_id": case_id,
            "source_revision_id": request.revision_id,
            "source_build_id": source["build_id"],
            "build_id": request.build_id,
            "draft_generation": request.draft_generation,
            "compatible": compatible,
            "changed": changed,
            "invalidated": invalidated,
            "candidate_assumptions": candidate,
            "preview": preview,
        }

    # -- exports -------------------------------------------------------------

    def queue_export(self, target_id: str, actor: str) -> dict[str, Any]:
        build = self.builds.get_build(target_id)
        if build is not None:
            if (build.get("export") or {}).get("status") == "READY":
                return build
            self.builds.update_build(target_id, export={"status": "QUEUED"})
            return self.builds.get_build(target_id)  # type: ignore[return-value]
        revision = self.builds.get_revision(target_id)
        if revision is None:
            raise ValueError("MODEL_EXPORT_TARGET_NOT_FOUND")
        if (revision.get("export") or {}).get("status") == "READY":
            return revision
        self.builds.update_revision_export(target_id, {"status": "QUEUED"})
        return self.builds.get_revision(target_id)  # type: ignore[return-value]

    def _publish(self, case_id: str, target_id: str, content: bytes) -> dict[str, Any]:
        import hashlib

        # Hash-addressed atomic publish: O_EXCL + fsync + rename, identity
        # characters checked, and an already-present target verified byte for
        # byte rather than overwritten. A plain write_bytes left a truncated
        # file behind on a crash for `download` to refuse later.
        sha256 = hashlib.sha256(content).hexdigest()
        _path, vault_key, size = publish_hash_addressed_bytes(
            self.vault_dir, ("models", case_id, target_id), "xlsx", content,
            expected_sha256=sha256, max_bytes=MAX_EXPORT_BYTES,
        )
        return {"status": "READY", "vault_key": vault_key, "filename": f"{target_id}.xlsx",
                "sha256": sha256, "size": size}

    def _render_bytes(self, build: dict[str, Any], effective: list[dict[str, Any]] | None) -> bytes:
        deadline = self._new_deadline()
        model, calculations = self._calculate(build, effective, deadline)
        with tempfile.TemporaryDirectory(prefix="caos-model-export-") as temporary:
            output = Path(temporary) / "model.xlsx"
            self.bundle.render_workbook(model, calculations, output)
            return output.read_bytes()

    def run_export_for_tests(self, target_id: str) -> dict[str, Any]:
        build = self.builds.get_build(target_id)
        if build is not None:
            if self._fail_next_export:
                self._fail_next_export = False
                self.builds.update_build(target_id, export={
                    "status": "FAILED", "error": {"code": "MODEL_EXPORT_FAILED", "detail": "The XLSX export did not complete."},
                })
                return self.builds.get_build(target_id)  # type: ignore[return-value]
            self._export_input_reads += 1
            export = self._publish(build["case_id"], target_id, self._render_bytes(build, None))
            self.builds.update_build(target_id, export=export)
            return self.builds.get_build(target_id)  # type: ignore[return-value]
        revision = self.builds.get_revision(target_id)
        if revision is None:
            raise ValueError("MODEL_EXPORT_TARGET_NOT_FOUND")
        if (revision.get("export") or {}).get("status") == "READY":
            return revision  # exports are immutable once READY — never re-rendered
        source_build = self.builds.get_build(revision["build_id"])
        if source_build is None or source_build.get("calculation_runtime") != self._current_runtime():
            # §12: the runtime pin is verified before any input is read.
            self.builds.update_revision_export(target_id, {
                "status": "FAILED",
                "error": {"code": "MODEL_REVISION_EXPORT_RUNTIME_UNAVAILABLE",
                          "detail": "The signed revision's pinned calculation runtime is unavailable."},
            })
            return self.builds.get_revision(target_id)  # type: ignore[return-value]
        if self._fail_next_export:
            self._fail_next_export = False
            self.builds.update_revision_export(target_id, {
                "status": "FAILED", "error": {"code": "MODEL_REVISION_EXPORT_FAILED", "detail": "The signed revision XLSX export did not complete."},
            })
            return self.builds.get_revision(target_id)  # type: ignore[return-value]
        self._export_input_reads += 1
        content = self._render_bytes(source_build, revision["effective_assumptions"])
        export = self._publish(revision["case_id"], target_id, content)
        self.builds.update_revision_export(target_id, export)
        return self.builds.get_revision(target_id)  # type: ignore[return-value]

    # The worker's entry points. The `_for_tests` suffix on the underlying
    # methods is historical — the spec suite pinned those names before
    # worker.py existed; the execution path is the production one.
    run_build = run_build_for_tests
    run_export = run_export_for_tests

    def download(self, case_id: str, target_id: str) -> tuple[bytes, str]:
        record = self.builds.get_build(target_id) or self.builds.get_revision(target_id)
        is_revision = record is not None and "revision_number" in record
        if record is None or record.get("case_id") != case_id:
            raise ValueError("MODEL_EXPORT_TARGET_NOT_FOUND")
        export = record.get("export") or {}
        if export.get("status") != "READY":
            raise ValueError("MODEL_EXPORT_NOT_READY")
        # Read through the no-follow descriptor chain: the stored bytes are
        # verified against the recorded digest AND length, and a symlink or a
        # non-regular file where the export should be is refused outright.
        try:
            content = read_verified_vault_bytes(
                self.vault_dir, export["vault_key"], expected_sha256=export["sha256"],
                expected_size=export["size"], max_bytes=MAX_EXPORT_BYTES,
            )
        except (VaultFileUnavailable, VaultFileIntegrityError) as exc:
            raise ValueError(
                "MODEL_REVISION_EXPORT_INTEGRITY_FAILED" if is_revision else "MODEL_EXPORT_INTEGRITY_FAILED"
            ) from exc
        return content, export["sha256"]

    # -- test seams ----------------------------------------------------------

    def fail_next_queue_for_tests(self) -> None:
        self._fail_next_queue = True

    def fail_next_dispatch_for_tests(self) -> None:
        self._fail_next_dispatch = True

    def fail_next_export_for_tests(self) -> None:
        self._fail_next_export = True

    def on_queue_for_tests(self, callback: Callable[[str], None]) -> None:
        self._on_queue.append(callback)

    def dispatch_log_for_tests(self) -> list[str]:
        return list(self._dispatch_log)

    def force_readiness_for_tests(self, case_id: str, code: str) -> None:
        self._forced_readiness[case_id] = code

    def validate_bundle_calls_for_tests(self) -> list[dict[str, Any]]:
        return list(self._validate_bundle_calls)

    def set_calculation_runtime_for_tests(self, *, sha256: str | None) -> None:
        self._runtime_sha_override = sha256

    def export_input_reads_for_tests(self) -> int:
        return self._export_input_reads

    def exceed_calculation_deadline_for_tests(self) -> None:
        self._deadline_exceeded = True

    def evolve_registry_for_tests(self, build_id: str, *, removed: tuple[str, ...] = (), source_context_changed: tuple[str, ...] = ()) -> None:
        self._evolutions[build_id] = {"removed": tuple(removed), "source_context_changed": tuple(source_context_changed)}
        self._defaults_cache.pop(build_id, None)

    def tamper_build_identity_for_tests(self, build_id: str, field: str) -> None:
        assert field in {"input_fingerprint", "payload_digest", "registry_digest", "snapshot_id", "assumptions_digest", "outputs_digest"}
        self.builds.update_build(build_id, **{field: "0" * 64})


def _remember(cache: dict[str, Any], key: str, value: Any) -> Any:
    """Insert, then evict the oldest entries past MAX_CACHED_BUILDS.
    Plain dicts keep insertion order, so the first key is the oldest."""
    cache.pop(key, None)
    cache[key] = value
    while len(cache) > MAX_CACHED_BUILDS:
        del cache[next(iter(cache))]
    return value


# -- pure row/output projections (shape shared with the assumption contract) --


def _assumption_rows(model: Any) -> list[dict[str, Any]]:
    rows = []
    for driver in model.effective_assumptions:
        value = json_value(driver.value) if driver.value is not None else None
        row: dict[str, Any] = {
            "assumption_id": driver.assumption_id,
            "case": driver.case,
            "period_id": driver.period_id,
            "unit": driver.unit,
            "status": driver.status,
            "value": value,
            "gap_code": driver.gap_code,
            "default_value": value,
            "default_status": driver.status,
            "default_gap_code": driver.gap_code,
            "source_context": {
                "authority_module": "CP-2G",
                "gap_code": driver.gap_code,
                "provenance": [
                    {"source_id": item.source_id, "source_locator": item.source_locator, "as_of": item.as_of}
                    for item in driver.provenance
                ],
            },
        }
        row["source_context_digest"] = digest(row["source_context"])
        rows.append(row)
    return sorted(rows, key=lambda row: (row["case"], row["period_id"], row["assumption_id"]))


def _with_default_context(effective: list[dict[str, Any]], defaults: list[dict[str, Any]]) -> list[dict[str, Any]]:
    default_by_key = {(row["assumption_id"], row["case"], row["period_id"]): row for row in defaults}
    if len(default_by_key) != len(defaults):
        raise ValueError("MODEL_ASSUMPTION_DEFAULT_INVALID")
    result = copy.deepcopy(effective)
    for row in result:
        default = default_by_key.get((row["assumption_id"], row["case"], row["period_id"]))
        if default is None:
            raise ValueError("MODEL_ASSUMPTION_DEFAULT_INVALID")
        row.update(
            default_value=default["value"],
            default_status=default["status"],
            default_gap_code=default["gap_code"],
            source_context=copy.deepcopy(default["source_context"]),
            source_context_digest=default["source_context_digest"],
        )
    return result


def _json_number(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ModelInputError("non-finite model output")
        return format(value, "f")
    raise ModelInputError("unexpected model output type")


_OUTPUT_VALUE_IDS = (
    "revenue", "adjusted_ebitda_calc", "fcf", "cumulative_fcf", "cash_and_equivalents",
    "accessible_liquidity", "liquidity_headroom", "total_debt_reported", "net_debt",
)
_OUTPUT_METRIC_IDS = (
    "adjusted_ebitda_margin", "total_leverage", "net_leverage", "interest_coverage", "covenant_headroom",
)


def _annual_outputs(calculations: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case in ("BASE", "DOWNSIDE"):
        periods: dict[str, Any] = {}
        for column in calculations.columns:
            if column.group != case:
                continue
            calculation = calculations.for_column(column.column_id)
            periods[column.column_id] = {
                **{output_id: _json_number(calculation.values.get(output_id)) for output_id in _OUTPUT_VALUE_IDS},
                **{output_id: _json_number(calculation.credit_metrics.get(output_id)) for output_id in _OUTPUT_METRIC_IDS},
            }
        result[case] = periods
        result[f"{case}_first_breaches"] = [
            {
                "period_id": breach.period_id,
                "threshold_id": breach.threshold_id,
                "metric_id": breach.metric_id,
                "limit": _json_number(breach.limit),
                "actual": _json_number(breach.actual),
                "headroom": _json_number(breach.headroom),
            }
            for breach in calculations.first_breaches[case]
        ]
    return result


def _output_deltas(baseline: dict[str, Any], changed: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for case in ("BASE", "DOWNSIDE"):
        result[case] = {}
        for period_id, values in changed.get(case, {}).items():
            base_values = baseline.get(case, {}).get(period_id, {})
            result[case][period_id] = {}
            for output_id, value in values.items():
                base = base_values.get(output_id)
                result[case][period_id][output_id] = (
                    format(Decimal(value) - Decimal(base), "f") if value is not None and base is not None else None
                )
    return result


def _has_output(outputs: dict[str, Any], case: str, output_id: str) -> bool:
    return any(output_id in values for values in outputs.get(case, {}).values() if isinstance(values, dict))


def _breach_matches_output(breach: dict[str, Any], output_id: str) -> bool:
    threshold_outputs = {
        "covenant.max_total_leverage": {"covenant_headroom", "total_leverage"},
        "liquidity.minimum_operating_cash": {"accessible_liquidity", "liquidity_headroom"},
    }
    return breach.get("metric_id") == output_id or output_id in threshold_outputs.get(breach.get("threshold_id"), set())
