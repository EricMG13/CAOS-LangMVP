"""Deliverables service (invariant 5; DECISIONS §2, §10.5/10.7, §12.21-23).

Drafts are append-only CAS revisions validated against the pathway template;
freeze renders every export once and parks a filing gate whose thread identity
includes build_id; filing is a store-CAS resume that re-validates the exact
preview digest, input fingerprint, payload integrity, and current upstream
authority — and never re-renders. The store remains the final arbiter under
concurrent approvals (§10.7); the gate is a store-backed parked thread rather
than a LangGraph thread (recorded deviation — the checkpointer adds no
arbitration the CAS does not already provide, and §12.21/22 semantics are
asserted against this seam by the spec suite).
"""

from __future__ import annotations

import copy
import hashlib
import threading
from pathlib import Path
from typing import Any, Callable

from ..contracts import (
    DeliverableDraftRequest,
    FileDeliverableRequest,
    FreezeDeliverableRequest,
    digest,
)
from ..publishing.renderers import render_frozen_export
from ..storage.deliverables import DeliverableStore, DeliverableVersionConflict  # noqa: F401 — conflict re-raised to callers
from ..storage.store import DomainStore, new_id
from .graph import canonical_approval_hash, filing_thread_id, validate_approval_hash

PATHWAY_TEMPLATES = (
    "FULL_CREDIT",
    "EARNINGS_UPDATE",
    "COVENANT_REFINANCING",
    "RELATIVE_VALUE",
    "DISTRESSED_RESTRUCTURING",
    "DEEP_RESEARCH",
)
EXPORT_FORMATS = ("md", "pdf", "xlsx")
REQUIRED_KINDS = {"HEADING", "NARRATIVE", "EVIDENCE_REGISTER", "LIMITATIONS"}
MODEL_DEPENDENT_KINDS = {"GENERATED_METRIC", "GENERATED_TABLE", "GENERATED_CHART", "SCENARIO_EXHIBIT", "MODEL_APPENDIX"}
GOVERNED_TABLES = {"debt_schedule": {"instrument", "amount", "maturity", "margin"}}

_OPTIONAL_POLICY = (
    {"kind": "GENERATED_METRIC", "slot_stem": "metric", "max": 4, "order": 1, "model_dependent": True},
    {"kind": "GENERATED_TABLE", "slot_stem": "table", "max": 4, "order": 2, "model_dependent": True},
    {"kind": "GENERATED_CHART", "slot_stem": "chart", "max": 4, "order": 3, "model_dependent": True},
    {"kind": "SCENARIO_EXHIBIT", "slot_stem": "scenario", "max": 4, "order": 4, "model_dependent": True},
    {"kind": "MODEL_APPENDIX", "slot_stem": "model-appendix", "max": 1, "order": 5, "model_dependent": True},
    {"kind": "LIMITATIONS", "slot_stem": "limitations-appendix", "max": 2, "order": 6, "model_dependent": False},
)


def _template(pathway: str) -> dict[str, Any]:
    return {
        "pathway": pathway,
        "template_id": f"tmpl-{pathway.lower().replace('_', '-')}",
        "template_version": "deliverable-template.v1",
        "slots": [
            {"slot_id": "headline", "kind": "HEADING"},
            {"slot_id": "thesis", "kind": "NARRATIVE"},
            {"slot_id": "evidence", "kind": "EVIDENCE_REGISTER"},
        ],
        "optional_blocks": [dict(entry) for entry in _OPTIONAL_POLICY],
        "allowed_appendices": [entry["kind"] for entry in _OPTIONAL_POLICY],
    }


class ScenarioCalculationForbidden(AssertionError):
    pass


class DeliverableService:
    def __init__(
        self,
        *,
        store: DomainStore,
        vault_dir: Path,
        engine: Any = None,
        renderer_for_tests: Callable[[dict[str, Any], str], bytes] | None = None,
    ) -> None:
        self.store = store
        self.vault_dir = Path(vault_dir)
        self.engine = engine
        self.records = DeliverableStore(store.engine)
        self._render = renderer_for_tests or render_frozen_export
        self._forbid_scenario_calculation = False
        self._freeze_lock = threading.Lock()

    # -- templates -----------------------------------------------------------

    def templates(self) -> dict[str, dict[str, Any]]:
        return {pathway: _template(pathway) for pathway in PATHWAY_TEMPLATES}

    def _template_for(self, pathway: str) -> dict[str, Any]:
        if pathway not in PATHWAY_TEMPLATES:
            raise ValueError(f"DELIVERABLE_PATHWAY_INVALID: no template for {pathway!r}")
        return _template(pathway)

    # -- draft save ----------------------------------------------------------

    def save_draft(self, case_id: str, pathway: str, request: DeliverableDraftRequest, *, actor: str) -> dict[str, Any]:
        template = self._template_for(pathway)
        blocks = [block.model_dump(mode="json") for block in request.blocks]
        self._validate_layout(template, blocks)
        self._validate_citations(case_id, blocks)
        selection = request.model_selection
        model = self._resolve_selection(case_id, selection)
        identity = self._model_identity(model, selection) if model else None
        needs_model = [block for block in blocks if block["kind"] in MODEL_DEPENDENT_KINDS]
        if needs_model and identity is None:
            raise ValueError("MODEL_REQUIRED: model-dependent blocks need a selected model")
        stored = [self._enrich_block(block, model, identity, selection) for block in blocks]
        content = {"blocks": stored, "model_identity": identity}
        return self.records.append_revision(
            case_id, pathway, request.expected_version, content, digest(content), actor, self.store._audit,
        )

    def _validate_layout(self, template: dict[str, Any], blocks: list[dict[str, Any]]) -> None:
        required = {slot["slot_id"]: slot["kind"] for slot in template["slots"]}
        required_order = [slot["slot_id"] for slot in template["slots"]]
        policy_by_stem = {entry["slot_stem"]: entry for entry in template["optional_blocks"]}
        seen_required: list[str] = []
        seen_slots: set[str] = set()
        optional_orders: list[int] = []
        stem_counts: dict[str, int] = {}
        past_required = False
        for block in blocks:
            slot_id = block["slot_id"]
            if slot_id in seen_slots:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} appears more than once")
            seen_slots.add(slot_id)
            if slot_id in required:
                if past_required:
                    raise ValueError("DELIVERABLE_TEMPLATE_ORDER_INVALID: required slots precede appendices")
                if block["kind"] != required[slot_id]:
                    raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} requires {required[slot_id]}")
                seen_required.append(slot_id)
                continue
            past_required = True
            stem, _, index = slot_id.rpartition("-")
            policy = policy_by_stem.get(stem)
            # Canonical index only (no zero-padded aliases of the same slot).
            if policy is None or not index.isdigit() or index != str(int(index)) or not 1 <= int(index) <= policy["max"]:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} is not a declared optional slot")
            if block["kind"] != policy["kind"]:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} carries {policy['kind']} blocks only")
            stem_counts[stem] = stem_counts.get(stem, 0) + 1
            if stem_counts[stem] > policy["max"]:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: more than {policy['max']} {policy['kind']} blocks")
            optional_orders.append(policy["order"])
        if seen_required != required_order:
            raise ValueError("DELIVERABLE_TEMPLATE_ORDER_INVALID: required slots must appear once, in template order")
        if optional_orders != sorted(optional_orders):
            raise ValueError("DELIVERABLE_TEMPLATE_ORDER_INVALID: optional blocks follow the template's declared order")

    def _validate_citations(self, case_id: str, blocks: list[dict[str, Any]]) -> None:
        for block in blocks:
            for citation in block.get("citations") or []:
                source = self.store.get_source(citation["source_id"])
                if source is None or source["case_id"] != case_id:
                    raise ValueError("EVIDENCE_CASE_MISMATCH: citation resolves outside this case")
                if source["withdrawn"]:
                    raise ValueError("EVIDENCE_SOURCE_WITHDRAWN: cited source is withdrawn")
                known = {item["block_id"] for item in source["blocks"] or []}
                missing = [block_id for block_id in citation["block_ids"] if block_id not in known]
                if missing:
                    raise ValueError(f"EVIDENCE_BLOCK_MISMATCH: unknown evidence blocks {missing}")

    # -- model selection -----------------------------------------------------

    def _resolve_selection(self, case_id: str, selection: Any) -> dict[str, Any] | None:
        if selection is None:
            return None
        if selection.kind == "ANALYST_REVISION":
            record = self.records.model_by_revision(case_id, selection.revision_id)
            head = self.records.head_model_revision(case_id)
            if (
                record is None
                or record["build_id"] != selection.build_id
                or head is None
                or head["revision_id"] != selection.revision_id
            ):
                raise ValueError("MODEL_REVISION_STALE: selection must pin the current signed revision")
            return record
        if self.records.head_model_revision(case_id) is not None:
            raise ValueError("MODEL_FALLBACK_INELIGIBLE: a signed REVISION exists — select it instead of the FALLBACK build")
        record = self.records.model_by_build(case_id, selection.build_id)
        if record is None or record["kind"] != "APPLICATION_BUILD":
            raise ValueError("MODEL_BUILD_STALE: fallback build does not resolve to a stored record")
        return record

    @staticmethod
    def _model_identity(model: dict[str, Any], selection: Any) -> dict[str, Any]:
        if selection.kind == "ANALYST_REVISION":
            return {
                "kind": "ANALYST_REVISION",
                "build_id": model["build_id"],
                "revision_id": model["revision_id"],
                "calculation_runtime": dict(model["calculation_runtime"]),
            }
        return {
            "kind": "APPLICATION_BUILD",
            "build_id": model["build_id"],
            "calculation_runtime": dict(model["calculation_runtime"]),
        }

    def _enrich_block(self, block: dict[str, Any], model: dict[str, Any] | None,
                      identity: dict[str, Any] | None, selection: Any) -> dict[str, Any]:
        if block["kind"] not in MODEL_DEPENDENT_KINDS:
            return block
        assert model is not None and identity is not None
        stored = dict(block)
        stored["model_digest"] = digest(identity)
        governed = set((model["outputs"] or {}).keys())
        if block["kind"] == "GENERATED_METRIC":
            rogue = [metric for metric in block["metric_ids"] if metric not in governed]
            if rogue:
                raise ValueError(f"GENERATED_FIELD_INVALID: ungoverned metric ids {rogue}")
            stored["values"] = {metric: model["outputs"][metric] for metric in block["metric_ids"]}
        elif block["kind"] == "GENERATED_TABLE":
            allowed = GOVERNED_TABLES.get(block["table_id"])
            if allowed is None or any(field not in allowed for field in block["field_ids"]):
                raise ValueError("GENERATED_FIELD_INVALID: ungoverned table or fields")
        elif block["kind"] == "GENERATED_CHART":
            from ..publishing.recipes import validate_recipe

            validate_recipe(block["recipe"], available_fields=governed)
        elif block["kind"] == "SCENARIO_EXHIBIT":
            self._validate_scenario_block(stored, model, selection)
        return stored

    def _validate_scenario_block(self, block: dict[str, Any], model: dict[str, Any], selection: Any) -> None:
        scenario = block["scenario"]
        expected_base = model["revision_id"] if selection.kind == "ANALYST_REVISION" else None
        # Identity binds BEFORE any calculation runs (zero residue on mismatch).
        if scenario["build_id"] != model["build_id"] or scenario["base_revision_id"] != expected_base:
            raise ValueError("SCENARIO_EXHIBIT_IDENTITY_MISMATCH: scenario base does not bind the selected model")
        recomputed = self._scenario_outputs(model["outputs"], block["shocks"])
        if scenario["outputs"] != recomputed:
            raise ValueError("SCENARIO_EXHIBIT_CALCULATION_MISMATCH: outputs do not match the server recomputation")
        if block["scenario_digest"] != digest(scenario):
            raise ValueError("SCENARIO_EXHIBIT_DIGEST_INVALID: digest does not match the server computation")

    def _scenario_outputs(self, base_outputs: dict[str, Any], shocks: list[dict[str, Any]]) -> dict[str, Any]:
        if self._forbid_scenario_calculation:
            raise ScenarioCalculationForbidden("scenario calculator invoked where identity should have failed first")
        factor = 1.0 + sum(float(shock["value"]) for shock in shocks)
        return {key: round(float(value) * factor, 9) for key, value in (base_outputs or {}).items()}

    # -- workspace reads -----------------------------------------------------

    def workspace(self, case_id: str, pathway: str) -> dict[str, Any]:
        return {
            "template": self._template_for(pathway),
            "draft": self.records.head_revision(case_id, pathway),
            "frozen": self.records.frozen_for_pathway(case_id, pathway),
        }

    def revision_history(self, case_id: str, pathway: str) -> list[dict[str, Any]]:
        return self.records.revision_history(case_id, pathway)

    def revision_by_id(self, case_id: str, revision_id: str) -> dict[str, Any] | None:
        return self.records.revision_by_id(case_id, revision_id)

    # -- freeze --------------------------------------------------------------

    def freeze(self, case_id: str, request: FreezeDeliverableRequest, *, actor: str) -> dict[str, Any]:
        revision = self._revision_for_freeze(case_id, request)
        pathway = self._pathway_of(case_id, request.draft_id)
        # Invariant 1 holds at the freeze boundary, not only at draft save: a
        # source withdrawn since the revision was written refuses the freeze.
        self._validate_citations(case_id, revision["content"]["blocks"])
        authority = self.records.authority(case_id)
        if authority is None:
            raise ValueError("DELIVERABLE_UPSTREAM_AUTHORITY_REQUIRED: no accepted upstream SNAPSHOT identity is pinned")
        source_set = self.store.current_source_set(case_id) or {"id": None, "version": 0}
        identity = revision["content"].get("model_identity")
        model_payload = None
        if identity is not None:
            record = (
                self.records.model_by_revision(case_id, identity["revision_id"])
                if identity["kind"] == "ANALYST_REVISION"
                else self.records.model_by_build(case_id, identity["build_id"])
            )
            model_payload = {
                "identity": identity,
                "outputs": record["outputs"],
                "assumptions": record["assumptions"],
                "build": {"payload": record["build_payload"], "qa": record["build_qa"]},
            }
        build_id = identity["build_id"] if identity else authority["build_id"]
        frozen_authority = {
            "snapshot_id": authority["snapshot_id"],
            "source_set_id": source_set["id"],
            "source_set_version": source_set["version"],
            "build_id": build_id,
        }
        input_fingerprint = digest(frozen_authority)
        payload = {
            "pathway": pathway,
            "template": {"template_id": revision["content"].get("template_id") or _template(pathway)["template_id"],
                         "template_version": _template(pathway)["template_version"]},
            "draft": {"id": request.draft_id, "version": revision["version"], "digest": revision["digest"]},
            "content": revision["content"],
            "model": model_payload,
            "authority": frozen_authority,
            "methodology": {"build_id": build_id},
            "input_fingerprint": input_fingerprint,
        }
        payload["preview_digest"] = digest({key: value for key, value in payload.items() if key != "preview_digest"})
        thread_id = filing_thread_id(
            case_id=case_id, pathway=pathway, draft_version=revision["version"],
            draft_digest=revision["digest"], build_id=build_id,
        )
        with self._freeze_lock:
            rendered = {format_name: self._render(payload, format_name) for format_name in EXPORT_FORMATS}
            exports = {
                format_name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
                for format_name, content in rendered.items()
            }
            record, created = self.records.insert_frozen({
                "deliverable_id": f"dlv-{thread_id[4:]}",
                "thread_id": thread_id,
                "case_id": case_id,
                "pathway": pathway,
                "status": "FROZEN",
                "preview_digest": payload["preview_digest"],
                "input_fingerprint": input_fingerprint,
                "build_id": build_id,
                "payload": payload,
                "exports": exports,
                "authority": frozen_authority,
                "draft_version": revision["version"],
                "draft_digest": revision["digest"],
                "created_by": actor,
            }, actor, self.store._audit)
            if created:
                directory = self.vault_dir / "deliverables" / thread_id
                directory.mkdir(parents=True, exist_ok=True)
                for format_name, content in rendered.items():
                    (directory / format_name).write_bytes(content)
        if not created and record["exports"] != exports:
            # The gate's own render is the only render: a divergent render for
            # the same freeze identity is a conflict, never an overwrite.
            raise ValueError("DELIVERABLE_FREEZE_CONFLICT: a divergent render exists for this freeze identity")
        return record

    def _revision_for_freeze(self, case_id: str, request: FreezeDeliverableRequest) -> dict[str, Any]:
        for pathway in PATHWAY_TEMPLATES:
            head = self.records.head_revision(case_id, pathway)
            if head and head["draft_id"] == request.draft_id:
                if head["version"] != request.draft_version or head["digest"] != request.draft_digest:
                    target = next(
                        (r for r in self.records.revision_history(case_id, pathway)
                         if r["version"] == request.draft_version and r["digest"] == request.draft_digest),
                        None,
                    )
                    if target is None:
                        raise ValueError("DELIVERABLE_DRAFT_STALE: freeze identity does not match a stored revision")
                    return target
                return head
        raise ValueError("DELIVERABLE_DRAFT_STALE: unknown draft")

    def _pathway_of(self, case_id: str, draft_id: str) -> str:
        for pathway in PATHWAY_TEMPLATES:
            head = self.records.head_revision(case_id, pathway)
            if head and head["draft_id"] == draft_id:
                return pathway
        raise ValueError("DELIVERABLE_DRAFT_STALE: unknown draft")

    # -- filing gate ---------------------------------------------------------

    def frozen_record(self, case_id: str, deliverable_id: str) -> dict[str, Any] | None:
        return self.records.frozen_record(case_id, deliverable_id)

    def approve_filing(self, case_id: str, deliverable_id: str, request: FileDeliverableRequest, *, actor: str) -> dict[str, Any]:
        record = self.records.frozen_record(case_id, deliverable_id)
        if record is None:
            raise ValueError("DELIVERABLE_NOT_FOUND")
        thread = self.records.thread_state(record["thread_id"])
        interrupt_id = thread["interrupt_id"] if thread else None
        if record["status"] != "FROZEN" or thread is None or thread["status"] != "PARKED":
            raise ResumeNotApplied(interrupt_id if thread and thread["status"] == "PARKED" else None)
        payload = dict(record["payload"])
        stored_preview = payload.pop("preview_digest", None)
        if stored_preview != record["preview_digest"] or digest(payload) != record["preview_digest"]:
            raise ValueError("DELIVERABLE_PREVIEW_INTEGRITY_FAILED: frozen content does not match its digest")
        if request.preview_digest != record["preview_digest"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: approval binds the exact frozen PREVIEW digest")
        if request.input_fingerprint != record["input_fingerprint"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: approval FINGERPRINT does not match the frozen identity")
        authority = self.records.authority(case_id)
        if authority is None or authority["snapshot_id"] != record["authority"]["snapshot_id"]:
            raise ValueError("FROZEN_AUTHORITY_STALE: the accepted upstream authority moved after freeze")
        current_set = self.store.current_source_set(case_id) or {"id": None, "version": 0}
        if (current_set["id"], current_set["version"]) != (
            record["authority"]["source_set_id"], record["authority"]["source_set_version"],
        ):
            raise ValueError("SOURCE_SET_CHANGED: the evidence base moved while the gate was parked")
        filed = self.records.file_record(deliverable_id, actor, self.store._audit)
        if filed is None:
            raise ResumeNotApplied(None)
        return filed

    def request_changes(self, case_id: str, deliverable_id: str, request: Any, *, actor: str) -> dict[str, Any]:
        record = self.records.frozen_record(case_id, deliverable_id)
        if record is None:
            raise ValueError("DELIVERABLE_NOT_FOUND")
        if request.preview_digest != record["preview_digest"] or request.input_fingerprint != record["input_fingerprint"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: change requests bind the exact frozen preview")
        updated = self.records.mark_changes_requested(deliverable_id, actor, request.comment, self.store._audit)
        if updated is None:
            raise ResumeNotApplied(None)
        head = self.records.head_revision(case_id, record["pathway"])
        content = copy.deepcopy(head["content"])
        content["change_request"] = {
            "comment": request.comment,
            "requested_by": actor,
            "deliverable_id": deliverable_id,
        }
        self.records.append_revision(
            case_id, record["pathway"], head["version"], content, digest(content), actor, self.store._audit,
        )
        return updated

    # -- exports -------------------------------------------------------------

    def export(self, deliverable_id: str, format_name: str) -> tuple[bytes, str]:
        record = self._frozen_by_id(deliverable_id)
        recorded = (record["exports"] or {}).get(format_name)
        path = self.vault_dir / "deliverables" / record["thread_id"] / format_name
        if recorded is None or not path.is_file():
            raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: no stored export for this format")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != recorded["sha256"] or len(content) != recorded["size"]:
            raise ValueError("DELIVERABLE_EXPORT_INTEGRITY_FAILED: stored bytes do not match the frozen record")
        return content, recorded["sha256"]

    def _frozen_by_id(self, deliverable_id: str) -> dict[str, Any]:
        with self.records.engine.connect() as conn:
            import sqlalchemy as sa

            from ..storage.deliverables import deliverable_frozen

            row = conn.execute(
                sa.select(deliverable_frozen).where(deliverable_frozen.c.deliverable_id == deliverable_id)
            ).mappings().first()
        if row is None:
            raise ValueError("DELIVERABLE_NOT_FOUND")
        return self.records._frozen(dict(row))

    # -- test seams ----------------------------------------------------------

    def seed_accepted_authority_for_tests(self, case_id: str) -> dict[str, Any]:
        return self.records.set_authority(case_id, new_id("snap"), f"deploy-v-{new_id('bld')[4:]}")

    def supersede_accepted_authority_for_tests(self, case_id: str) -> dict[str, Any]:
        current = self.records.authority(case_id)
        build_id = current["build_id"] if current else f"deploy-v-{new_id('bld')[4:]}"
        return self.records.set_authority(case_id, new_id("snap"), build_id)

    def seed_signed_revision_for_tests(self, case_id: str, *, outputs: dict[str, Any]) -> dict[str, Any]:
        record = {
            "case_id": case_id,
            "kind": "ANALYST_REVISION",
            "build_id": new_id("dlbld"),
            "revision_id": new_id("dlrevn"),
            "outputs": dict(outputs),
            "assumptions": [
                {"assumption_id": "revenue_growth", "case": "DOWNSIDE", "period_id": "FY2026", "value": 0.02},
                {"assumption_id": "revenue_growth", "case": "BASE", "period_id": "FY2026", "value": 0.04},
            ],
            "build_payload": {"tabs": [{"title": "Model", "cells": []}]},
            "build_qa": {"status": "PASS"},
            "calculation_runtime": {"name": "cp_model_v3_python", "version": "3", "sha256": "a" * 64},
        }
        self.records.insert_model(record)
        return {
            "build_id": record["build_id"],
            "revision_id": record["revision_id"],
            "outputs": record["outputs"],
            "assumptions": record["assumptions"],
            "build_payload": record["build_payload"],
            "build_qa": record["build_qa"],
        }

    def seed_application_build_for_tests(self, case_id: str, *, outputs: dict[str, Any]) -> dict[str, Any]:
        record = {
            "case_id": case_id,
            "kind": "APPLICATION_BUILD",
            "build_id": new_id("dlbld"),
            "revision_id": None,
            "outputs": dict(outputs),
            "assumptions": [],
            "build_payload": {"tabs": [{"title": "Model", "cells": []}]},
            "build_qa": {"status": "PASS"},
            "calculation_runtime": {"name": "cp_model_v3_python", "version": "3", "sha256": "b" * 64},
        }
        self.records.insert_model(record)
        return {"build_id": record["build_id"], "outputs": record["outputs"]}

    def preview_scenario_for_tests(self, case_id: str, *, build_id: str, base_revision_id: str | None,
                                   shocks: list[dict[str, Any]]) -> dict[str, Any]:
        record = (
            self.records.model_by_revision(case_id, base_revision_id)
            if base_revision_id
            else self.records.model_by_build(case_id, build_id)
        )
        if record is None or record["build_id"] != build_id:
            raise ValueError("MODEL_REVISION_STALE: scenario base does not resolve")
        outputs = self._scenario_outputs(record["outputs"], shocks)
        effective = copy.deepcopy(record["assumptions"]) or [dict(shock) for shock in shocks]
        scenario = {
            "case_id": case_id,
            "build_id": build_id,
            "base_revision_id": base_revision_id,
            "registry_version": "cp-model-assumptions.v1",
            "registry_digest": "c" * 64,
            "draft_generation": 0,
            "effective_assumptions": effective,
            "assumptions_digest": digest(effective),
            "outputs": outputs,
            "outputs_digest": digest(outputs),
            "deltas": {},
        }
        return {"shocks": [dict(shock) for shock in shocks], "scenario": scenario, "scenario_digest": digest(scenario)}

    def forbid_scenario_calculation_for_tests(self) -> None:
        self._forbid_scenario_calculation = True

    def audit_events_for_tests(self, case_id: str) -> list[dict[str, Any]]:
        return [event for event in self.store.audit_trail(limit=2_000) if event.get("case_id") == case_id]

    def tamper_frozen_payload_for_tests(self, deliverable_id: str) -> None:
        self.records.tamper_frozen_payload(deliverable_id)

    def tamper_export_for_tests(self, deliverable_id: str, format_name: str) -> None:
        record = self._frozen_by_id(deliverable_id)
        path = self.vault_dir / "deliverables" / record["thread_id"] / format_name
        path.write_bytes(path.read_bytes() + b"tampered")

    def delete_export_for_tests(self, deliverable_id: str, format_name: str) -> None:
        record = self._frozen_by_id(deliverable_id)
        (self.vault_dir / "deliverables" / record["thread_id"] / format_name).unlink(missing_ok=True)

    def terminate_filing_thread_for_tests(self, thread_id: str) -> None:
        self.records.terminate_thread(thread_id, "TERMINATED_FOR_TESTS")

    def thread_state_for_tests(self, thread_id: str) -> dict[str, Any]:
        state = self.records.thread_state(thread_id)
        if state is None:
            raise ValueError("DELIVERABLE_THREAD_NOT_FOUND")
        return state

    def resume_filing_with_hash_for_tests(self, thread_id: str, approval_hash: str) -> dict[str, Any]:
        state = self.thread_state_for_tests(thread_id)
        record = self._frozen_by_id(state["deliverable_id"])
        validate_approval_hash(approval_hash, record)
        assert approval_hash == canonical_approval_hash(record)
        return self.approve_filing(record["case_id"], record["deliverable_id"], FileDeliverableRequest(
            preview_digest=record["preview_digest"], input_fingerprint=record["input_fingerprint"],
        ), actor="approver-user")

    def export_text_for_tests(self, deliverable_id: str, format_name: str) -> str:
        content, _ = self.export(deliverable_id, format_name)
        if format_name == "md":
            return content.decode("utf-8")
        if format_name == "pdf":
            import io

            from pypdf import PdfReader

            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: text extraction supports md and pdf")


class ResumeNotApplied(ValueError):
    """RESUME_NOT_APPLIED (§12.22): a resume that advances nothing never
    surfaces as success; carries the currently parked interrupt id, if any."""

    def __init__(self, current_interrupt_id: str | None) -> None:
        self.current_interrupt_id = current_interrupt_id
        super().__init__("RESUME_NOT_APPLIED")
