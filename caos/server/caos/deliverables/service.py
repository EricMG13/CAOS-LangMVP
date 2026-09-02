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
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Callable

from ..atomic_files import (
    MAX_EXPORT_BYTES,
    VaultFileIntegrityError,
    VaultFileUnavailable,
    publish_hash_addressed_bytes,
    read_verified_vault_bytes,
)
from ..contracts import (
    AnalystRevisionSelection,
    ApplicationBuildSelection,
    DeliverableDraftRequest,
    FileDeliverableRequest,
    FreezeDeliverableRequest,
    digest,
)
from ..engine.provider import AgentError
from ..engine.state import source_set_digest
from ..publishing.renderers import render_frozen_export
from ..storage.deliverables import DeliverableStore, DeliverableVersionConflict  # noqa: F401 — conflict re-raised to callers
from ..storage.runs import RunStore
from ..storage.store import DomainStore, new_id
from .document import DOCUMENT_SCHEMA_VERSION, compose_document, model_metric_values
from .graph import (
    canonical_approval_hash,
    filing_thread_id,
    frozen_approval_digest,
    validate_approval_hash,
)

PATHWAY_TEMPLATES = (
    "FULL_CREDIT",
    "EARNINGS_UPDATE",
    "COVENANT_REFINANCING",
    "RELATIVE_VALUE",
    "DISTRESSED_RESTRUCTURING",
    "DEEP_RESEARCH",
)
EXPORT_FORMATS = ("md", "pdf", "xlsx")
MODEL_DEPENDENT_KINDS = {"GENERATED_METRIC", "GENERATED_TABLE", "GENERATED_CHART", "SCENARIO_EXHIBIT", "MODEL_APPENDIX"}
GOVERNED_TABLES = {
    "annual_model": {"revenue", "adjusted_ebitda_calc", "fcf", "total_leverage"},
    "debt_schedule": {"instrument", "amount", "maturity", "margin"},
}

# Deliverable templates are the workbench contract: titled required sections per
# pathway, then the mandatory Evidence Register, then optional appendices.
PATHWAY_TITLES = {
    "FULL_CREDIT": "Investment Committee Credit Memo",
    "EARNINGS_UPDATE": "Earnings Update",
    "COVENANT_REFINANCING": "Covenant and Refinancing Brief",
    "RELATIVE_VALUE": "Relative Value Note",
    "DISTRESSED_RESTRUCTURING": "Scenario and Recovery Pack",
    "DEEP_RESEARCH": "Evidence-Bound Research Memorandum",
}
PATHWAY_SECTIONS = {
    "FULL_CREDIT": ("Credit Snapshot", "Recommendation", "Thesis and Variant View", "Business and Industry", "Capital Structure", "Base and Downside Model", "Liquidity and Covenants", "Risks, Catalysts, and Falsifiers", "Monitoring"),
    "EARNINGS_UPDATE": ("Credit Snapshot", "What Changed", "Reported Versus Prior Bridge", "Model Impact", "Leverage and Liquidity", "Thesis and Recommendation Impact", "Risks, Catalysts, and Monitoring"),
    "COVENANT_REFINANCING": ("Credit Snapshot", "Capital Structure and Maturity Wall", "Covenant Definitions and Headroom", "Liquidity", "Refinancing Options", "Base and Downside Breakpoints", "Actions and Monitoring"),
    "RELATIVE_VALUE": ("Credit Snapshot", "Instrument Comparison", "Structure and Seniority", "Relative Compensation", "Catalysts and Risks", "Recommendation and Trade Gates", "Market Freshness"),
    "DISTRESSED_RESTRUCTURING": ("Credit Snapshot", "Capital Structure and Priority", "Liquidity Runway", "Base, Downside, and Scenario Exhibits", "Recovery", "Covenant, Default, and Refinancing Milestones", "Catalysts and Process Risks", "Recommendation"),
    "DEEP_RESEARCH": ("Research Question and Scope", "Executive Findings", "Evidence Synthesis", "Counterevidence and Gaps", "Implications for Thesis, Model, and Recommendation", "Unresolved Questions"),
}
MODEL_OPTIONAL_PATHWAYS = {"RELATIVE_VALUE", "DEEP_RESEARCH"}

_OPTIONAL_POLICY = (
    {"kind": "GENERATED_METRIC", "slot_stem": "appendix.generated-metric", "max_items": 4, "order": 1, "model_dependent": True},
    {"kind": "GENERATED_TABLE", "slot_stem": "appendix.generated-table", "max_items": 4, "order": 2, "model_dependent": True},
    {"kind": "GENERATED_CHART", "slot_stem": "appendix.generated-chart", "max_items": 4, "order": 3, "model_dependent": True},
    {"kind": "SCENARIO_EXHIBIT", "slot_stem": "appendix.scenario", "max_items": 4, "order": 4, "model_dependent": True},
    {"kind": "MODEL_APPENDIX", "slot_stem": "appendix.model-appendix", "max_items": 1, "order": 5, "model_dependent": True},
    {"kind": "LIMITATIONS", "slot_stem": "appendix.limitations", "max_items": 2, "order": 6, "model_dependent": False},
)


def _template(pathway: str) -> dict[str, Any]:
    prefix = pathway.lower()
    blocks = [
        {"block_id": f"{prefix}.section.{index:02d}", "slot_id": f"section.{index:02d}",
         "kind": "NARRATIVE", "title": title, "required": True, "order": index}
        for index, title in enumerate(PATHWAY_SECTIONS[pathway], start=1)
    ]
    blocks.append({
        "block_id": f"{prefix}.evidence-register", "slot_id": "appendix.evidence-register",
        "kind": "EVIDENCE_REGISTER", "title": "Evidence Register", "required": True, "order": len(blocks) + 1,
    })
    return {
        "pathway": pathway,
        "template_id": f"caos.{prefix.replace('_', '-')}.v1",
        "template_version": "caos.deliverable-template.v1",
        "title": PATHWAY_TITLES[pathway],
        "model_requirement": "OPTIONAL" if pathway in MODEL_OPTIONAL_PATHWAYS else "REQUIRED",
        "blocks": blocks,
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
        models: Any = None,
        renderer_for_tests: Callable[[dict[str, Any], str], bytes] | None = None,
    ) -> None:
        self.store = store
        self.vault_dir = Path(vault_dir)
        self.engine = engine
        self.models = models
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
        if request.template_id != template["template_id"] or request.template_version != template["template_version"]:
            raise ValueError("DELIVERABLE_TEMPLATE_STALE: the draft binds a different template identity")
        blocks = [block.model_dump(mode="json") for block in request.blocks]
        self._validate_layout(template, blocks)
        self._validate_citations(case_id, blocks)
        selection = request.model_selection
        model = self._resolve_selection(case_id, selection)
        self._validate_pathway_authority(case_id, pathway, model)
        identity = self._model_identity(model, selection) if model else None
        needs_model = [block for block in blocks if block["kind"] in MODEL_DEPENDENT_KINDS]
        if identity is None and (template["model_requirement"] == "REQUIRED" or needs_model):
            raise ValueError(
                "MODEL_REQUIRED: this deliverable template or its model-dependent blocks "
                "need a selected model"
            )
        stored = [self._enrich_block(case_id, block, model, identity, selection) for block in blocks]
        document_sections = compose_document(
            pathway=pathway,
            template=template,
            blocks=stored,
            artifacts=self._accepted_artifacts(case_id),
            model=model,
        )
        content = {
            "template_id": template["template_id"],
            "template_version": template["template_version"],
            "document_schema_version": DOCUMENT_SCHEMA_VERSION,
            "document_sections": document_sections,
            "model_selection": selection.model_dump(mode="json") if selection else None,
            "model_identity": identity,
            "blocks": stored,
            "generated_blocks": self._generated_blocks(stored, model),
        }
        return self.records.append_revision(
            case_id, pathway, request.expected_version, content, digest(content), actor, self.store._audit,
        )

    @staticmethod
    def _generated_blocks(blocks: list[dict[str, Any]], model: dict[str, Any] | None) -> dict[str, Any]:
        generated: dict[str, Any] = {}
        for block in blocks:
            if block["kind"] not in MODEL_DEPENDENT_KINDS:
                continue
            if block["kind"] == "GENERATED_METRIC":
                outputs = block.get("values") or {}
            elif block["kind"] == "SCENARIO_EXHIBIT":
                outputs = (block.get("scenario") or {}).get("outputs") or {}
            else:
                outputs = (model or {}).get("outputs") or {}
            generated[block["block_id"]] = {"status": "READY", "outputs": outputs}
        return generated

    def _validate_layout(self, template: dict[str, Any], blocks: list[dict[str, Any]]) -> None:
        slot_ids = [block["slot_id"] for block in blocks]
        if len(set(slot_ids)) != len(slot_ids):
            raise ValueError("DELIVERABLE_SLOT_INVALID: a slot appears more than once")
        required = template["blocks"]
        head, tail = blocks[: len(required)], blocks[len(required):]
        expected = [(item["block_id"], item["slot_id"], item["kind"]) for item in required]
        if [(block["block_id"], block["slot_id"], block["kind"]) for block in head] != expected:
            raise ValueError("DELIVERABLE_TEMPLATE_ORDER_INVALID: required blocks must appear once, in template order")
        policy_by_stem = {entry["slot_stem"]: entry for entry in template["optional_blocks"]}
        optional_orders: list[int] = []
        for block in tail:
            slot_id = block["slot_id"]
            stem, _, index = slot_id.rpartition(".")
            policy = policy_by_stem.get(stem)
            # Canonical two-digit index only (no aliases of the same slot); slot
            # uniqueness plus the index cap bounds each stem to max_items blocks.
            if policy is None or not index.isdigit() or index != f"{int(index):02d}" or not 1 <= int(index) <= policy["max_items"]:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} is not a declared optional slot")
            if block["kind"] != policy["kind"]:
                raise ValueError(f"DELIVERABLE_SLOT_INVALID: {slot_id} carries {policy['kind']} blocks only")
            optional_orders.append(policy["order"])
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
            if record is None and head is None:
                return self._live_revision(case_id, selection)
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
        if record is None:
            return self._live_build(case_id, selection)
        if record["kind"] != "APPLICATION_BUILD":
            raise ValueError("MODEL_BUILD_STALE: fallback build does not resolve to a stored record")
        return record

    def _resolve_stored_selection(
        self,
        case_id: str,
        stored: Any,
    ) -> tuple[dict[str, Any] | None, Any]:
        if stored is None:
            return None, None
        if not isinstance(stored, dict):
            raise ValueError("MODEL_SELECTION_INVALID")
        selection_model = (
            AnalystRevisionSelection
            if stored.get("kind") == "ANALYST_REVISION"
            else ApplicationBuildSelection
        )
        selection = selection_model.model_validate(stored)
        return self._resolve_selection(case_id, selection), selection

    # -- live model authority (Model Builder is the system of record) --------

    @staticmethod
    def _revision_targets_publication_build(
        head: dict[str, Any] | None,
        build: dict[str, Any] | None,
        model_authority: dict[str, Any],
    ) -> bool:
        return bool(
            head is not None
            and build is not None
            and head.get("build_id") == build.get("id")
            and head.get("snapshot_id") == model_authority.get("snapshot_id")
        )

    @staticmethod
    def _signed_revision_matches_publication_build(
        head: dict[str, Any] | None,
        build: dict[str, Any] | None,
        model_authority: dict[str, Any],
    ) -> bool:
        if head is None or build is None:
            return False
        prior_full_credit = (
            model_authority.get("relationship") == "PRIOR_FULL_CREDIT_BASE"
        )
        return (
            head.get("build_id") == build.get("id")
            and head.get("snapshot_id") == model_authority.get("snapshot_id")
            and head.get("build_input_fingerprint") == build.get("input_fingerprint")
            and head.get("build_payload_digest") == build.get("payload_digest")
            and head.get("registry_version") == build.get("registry_version")
            and head.get("registry_digest") == build.get("registry_digest")
            and head.get("calculation_contract_version")
            == (build.get("calculation_runtime") or {}).get(
                "calculation_contract_version"
            )
            and head.get("assumptions_digest")
            == digest(head.get("effective_assumptions"))
            and head.get("outputs_digest") == digest(head.get("outputs"))
            and (
                head.get("state") == "ACTIVE"
                or (prior_full_credit and head.get("state") == "STALE")
            )
        )

    def _live_revision(self, case_id: str, selection: Any) -> dict[str, Any]:
        head = self.models.head_revision(case_id) if self.models is not None else None
        context = (
            self.models.validated_publication_build(case_id, selection.build_id)
            if self.models is not None
            else None
        )
        build = context["build"] if context is not None else None
        model_authority = context["model_authority"] if context is not None else {}
        if (
            head is None
            or head["id"] != selection.revision_id
            or head["build_id"] != selection.build_id
            or build is None
            or build.get("status") != "READY"
            or not self._signed_revision_matches_publication_build(
                head,
                build,
                model_authority,
            )
        ):
            raise ValueError("MODEL_REVISION_STALE: selection must pin the current signed revision")
        payload = build.get("payload") or {}
        return {
            "kind": "ANALYST_REVISION",
            "build_id": head["build_id"],
            "revision_id": head["id"],
            "outputs": head["outputs"],
            "assumptions": head["effective_assumptions"],
            "build_payload": {"build_payload_digest": head.get("build_payload_digest")},
            "build_qa": {"status": "SIGNED"},
            "calculation_runtime": {
                "calculation_contract_version": head.get("calculation_contract_version"),
                "assumption_registry_version": head.get("registry_version"),
            },
            "methodology_build_id": build.get("methodology_build_id"),
            "pathway_effects": copy.deepcopy(payload.get("pathway_effects") or []),
            "model_authority": copy.deepcopy(model_authority),
        }

    def _live_build(self, case_id: str, selection: Any) -> dict[str, Any]:
        head = self.models.head_revision(case_id) if self.models is not None else None
        context = (
            self.models.validated_publication_build(case_id, selection.build_id)
            if self.models is not None
            else None
        )
        build = context["build"] if context is not None else None
        model_authority = context["model_authority"] if context is not None else {}
        signed_revision_governs = self._revision_targets_publication_build(
            head,
            build,
            model_authority,
        )
        if signed_revision_governs:
            raise ValueError("MODEL_FALLBACK_INELIGIBLE: a signed REVISION exists — select it instead of the FALLBACK build")
        if build is None or build["id"] != selection.build_id or build.get("status") != "READY":
            raise ValueError("MODEL_BUILD_STALE: fallback build does not resolve to a stored record")
        payload = build.get("payload") or {}
        return {
            "kind": "APPLICATION_BUILD",
            "build_id": build["id"],
            "revision_id": None,
            "outputs": context["outputs"],
            "assumptions": [],
            "build_payload": {"payload_digest": build.get("payload_digest")},
            "build_qa": dict(build.get("qa") or {}),
            "calculation_runtime": dict(build.get("calculation_runtime") or {}),
            "methodology_build_id": build.get("methodology_build_id"),
            "pathway_effects": copy.deepcopy(payload.get("pathway_effects") or []),
            "model_authority": copy.deepcopy(model_authority),
        }

    def model_eligibility(self, case_id: str) -> dict[str, Any]:
        active = None
        application_build = None
        head_targets_build = False
        if self.models is not None:
            head = self.models.head_revision(case_id)
            try:
                context = self.models.validated_publication_build(case_id)
            except ValueError:
                context = None
            build = context["build"] if context is not None else None
            model_authority = context["model_authority"] if context is not None else {}
            head_is_publishable = self._signed_revision_matches_publication_build(
                head,
                build,
                model_authority,
            )
            head_targets_build = self._revision_targets_publication_build(
                head,
                build,
                model_authority,
            )
            if head_is_publishable:
                active = {
                    "revision_id": head["id"], "build_id": head["build_id"],
                    "revision_number": head["revision_number"],
                    "signed_by": head.get("created_by", ""), "signed_at": head.get("created_at", ""),
                }
            if build is not None and build.get("status") == "READY":
                application_build = {
                    "build_id": build["id"], "accepted_snapshot_id": build.get("snapshot_id"),
                    "input_fingerprint": build.get("input_fingerprint"),
                    "payload_digest": build.get("payload_digest"), "status": "READY",
                }
        else:
            seeded = self.records.head_model_revision(case_id)
            if seeded is not None:
                active = {
                    "revision_id": seeded["revision_id"], "build_id": seeded["build_id"],
                    "revision_number": 1, "signed_by": "analyst", "signed_at": "",
                }
        default = (
            {"kind": "ANALYST_REVISION", "build_id": active["build_id"], "revision_id": active["revision_id"]}
            if active else None
        )
        # Fallback is never auto-selected: acknowledging it is a human act.
        return {
            "active_revision": active,
            "application_build": application_build,
            "fallback_acknowledgement_required": (
                active is None
                and application_build is not None
                and not head_targets_build
            ),
            "default_model_selection": default,
        }

    @staticmethod
    def _model_identity(model: dict[str, Any], selection: Any) -> dict[str, Any]:
        if selection.kind == "ANALYST_REVISION":
            identity = {
                "kind": "ANALYST_REVISION",
                "build_id": model["build_id"],
                "revision_id": model["revision_id"],
                "calculation_runtime": dict(model["calculation_runtime"]),
            }
        else:
            identity = {
                "kind": "APPLICATION_BUILD",
                "build_id": model["build_id"],
                "calculation_runtime": dict(model["calculation_runtime"]),
            }
        if model.get("methodology_build_id"):
            identity["methodology_build_id"] = model["methodology_build_id"]
        if model.get("model_authority"):
            identity["model_authority"] = copy.deepcopy(model["model_authority"])
        return identity

    @staticmethod
    def _governed_metric_ids(outputs: dict[str, Any]) -> set[str]:
        """Metric ids at the top level (seeded flat records) plus the leaf level
        of the CASE/period/metric shape the calculation engine emits."""
        governed = set(outputs or {})
        for case_values in (outputs or {}).values():
            if isinstance(case_values, dict):
                for period_values in case_values.values():
                    if isinstance(period_values, dict):
                        governed.update(period_values)
        return governed

    def _enrich_block(self, case_id: str, block: dict[str, Any], model: dict[str, Any] | None,
                      identity: dict[str, Any] | None, selection: Any) -> dict[str, Any]:
        if block["kind"] not in MODEL_DEPENDENT_KINDS:
            return block
        assert model is not None and identity is not None
        stored = dict(block)
        stored["model_digest"] = digest(identity)
        governed = self._governed_metric_ids(model["outputs"] or {})
        if block["kind"] == "GENERATED_METRIC":
            rogue = [metric for metric in block["metric_ids"] if metric not in governed]
            if rogue:
                raise ValueError(f"GENERATED_FIELD_INVALID: ungoverned metric ids {rogue}")
            stored["values"] = {metric: model_metric_values(model["outputs"], metric) for metric in block["metric_ids"]}
        elif block["kind"] == "GENERATED_TABLE":
            allowed = GOVERNED_TABLES.get(block["table_id"])
            if allowed is None or any(field not in allowed for field in block["field_ids"]):
                raise ValueError("GENERATED_FIELD_INVALID: ungoverned table or fields")
        elif block["kind"] == "GENERATED_CHART":
            from ..publishing.recipes import validate_recipe

            validate_recipe(block["recipe"], available_fields=governed)
        elif block["kind"] == "SCENARIO_EXHIBIT":
            self._validate_scenario_block(case_id, stored, model, selection)
        return stored

    def _validate_scenario_block(self, case_id: str, block: dict[str, Any], model: dict[str, Any], selection: Any) -> None:
        scenario = block["scenario"]
        expected_base = model["revision_id"] if selection.kind == "ANALYST_REVISION" else None
        # Identity binds BEFORE any calculation runs (zero residue on mismatch).
        if scenario["build_id"] != model["build_id"] or scenario["base_revision_id"] != expected_base:
            raise ValueError("SCENARIO_EXHIBIT_IDENTITY_MISMATCH: scenario base does not bind the selected model")
        if self.models is not None:
            from ..contracts import ModelScenarioRequest

            try:
                recomputed = self.models.scenario(case_id, ModelScenarioRequest(
                    build_id=scenario["build_id"], base_revision_id=scenario["base_revision_id"],
                    registry_version=scenario["registry_version"], registry_digest=scenario["registry_digest"],
                    shocks=block["shocks"], draft_generation=scenario["draft_generation"],
                ))["scenario"]["outputs"]
            except ValueError as exc:
                raise ValueError(f"SCENARIO_EXHIBIT_IDENTITY_MISMATCH: {exc}") from exc
        else:
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

    def _authority_for(self, case_id: str) -> dict[str, Any] | None:
        """Resolve application and methodology authority without conflating them."""
        seeded = self.records.authority(case_id)
        if seeded is not None:
            return {**seeded, "methodology_build_id": seeded["build_id"]}
        case = self.store.get_case(case_id) or {}
        snapshot_id = case.get("accepted_snapshot_id")
        if snapshot_id is None:
            return None
        runs = self.engine.runs if self.engine is not None else RunStore(self.store.engine)
        snapshot = runs.get_snapshot(snapshot_id)
        run = runs.get_run(snapshot.get("run_id")) if snapshot is not None else None
        snapshot_preimage = {
            key: value
            for key, value in (snapshot or {}).items()
            if key not in {"digest", "id"}
        }
        if (
            snapshot is None
            or run is None
            or snapshot.get("case_id") != case_id
            or run.get("case_id") != case_id
            or run.get("status") != "succeeded"
            or run.get("accepted_snapshot_id") != snapshot_id
            or snapshot.get("provider_identity") != run.get("provider_identity")
            or digest(snapshot_preimage) != snapshot.get("digest")
            or digest(run.get("plan") or {}) != run.get("plan_digest")
            or not isinstance((run.get("plan") or {}).get("build_id"), str)
            or not run["plan"]["build_id"]
        ):
            raise ValueError("DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:accepted_snapshot")
        source_set = self.store.source_set(snapshot["source_set_id"])
        if (
            source_set is None
            or source_set.get("case_id") != case_id
            or source_set.get("version") != snapshot.get("source_set_version")
            or run["plan"].get("source_set_id") != source_set["id"]
            or run["plan"].get("source_set_version") != source_set["version"]
            or source_set_digest(source_set) != run["plan"].get("source_set_digest")
            or self.store.sources_for_live_set(
                case_id,
                source_set["id"],
                source_set["version"],
            ) is None
        ):
            raise ValueError("DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:accepted_source_set")
        build = (self.models.readiness(case_id) or {}).get("build") if self.models is not None else None
        return {
            "case_id": case_id,
            "snapshot_id": snapshot_id,
            "source_set_id": source_set["id"],
            "source_set_version": source_set["version"],
            "build_id": (build or {}).get("id") or "unbuilt",
            "methodology_build_id": run["plan"]["build_id"],
        }

    def _validate_pathway_authority(
        self,
        case_id: str,
        pathway: str,
        model: dict[str, Any] | None,
    ) -> None:
        # Seeded records are an isolated test seam. Ordinary publication always
        # resolves the accepted snapshot and run below.
        if self.records.authority(case_id) is not None:
            return
        authority = self._authority_for(case_id)
        if authority is None:
            raise ValueError(
                "DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH: no accepted pathway authority"
            )
        runs = self.engine.runs if self.engine is not None else RunStore(self.store.engine)
        snapshot = runs.get_snapshot(authority["snapshot_id"])
        run = runs.get_run(snapshot["run_id"]) if snapshot is not None else None
        if run is None or run.get("pathway") != pathway:
            raise ValueError(
                "DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH: accepted analysis does not match the deliverable pathway"
            )
        effects = (model or {}).get("pathway_effects") or []
        if pathway == "FULL_CREDIT" and effects:
            raise ValueError(
                "DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH: Full Credit cannot publish a Distressed overlay"
            )
        if pathway in {"EARNINGS_UPDATE", "COVENANT_REFINANCING"}:
            model_authority = (model or {}).get("model_authority") or {}
            if model_authority.get("relationship") != "PRIOR_FULL_CREDIT_BASE":
                raise ValueError(
                    "DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH: incremental publication requires a validated prior Full Credit model"
                )
        if pathway != "DISTRESSED_RESTRUCTURING":
            return
        effect = effects[0] if len(effects) == 1 and isinstance(effects[0], dict) else {}
        distressed = effect.get("distressed_authority") or {}
        calculations = effect.get("calculations") or []
        if (
            effect.get("schema_version") != "caos.model-pathway-effect.v1"
            or effect.get("pathway") != pathway
            or distressed.get("snapshot_id") != snapshot["id"]
            or distressed.get("snapshot_digest") != snapshot["digest"]
            or not isinstance(calculations, list)
            or {item.get("calculator_id") for item in calculations if isinstance(item, dict)}
            != {"funding_gap", "recovery_waterfall"}
        ):
            raise ValueError(
                "DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH: Distressed publication requires the current CP-4C overlay"
            )

    def _accepted_artifacts(self, case_id: str) -> dict[str, dict[str, Any]]:
        authority = self._authority_for(case_id)
        if authority is None:
            return {}
        artifacts: dict[str, dict[str, Any]] = {"__authority__": {"id": authority["snapshot_id"]}}
        runs = self.engine.runs if self.engine is not None else RunStore(self.store.engine)
        snapshot = runs.get_snapshot(authority["snapshot_id"])
        if snapshot is None:
            return artifacts
        snapshot_preimage = {
            key: value
            for key, value in snapshot.items()
            if key not in {"digest", "id"}
        }
        if snapshot["case_id"] != case_id or digest(snapshot_preimage) != snapshot["digest"]:
            raise ValueError("DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:accepted_snapshot")
        runtime_engine = self.engine or getattr(self.models, "engine", None)
        run = runs.get_run(snapshot["run_id"])
        if runtime_engine is None or run is None:
            raise ValueError("DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:accepted_snapshot")
        try:
            validated = runtime_engine.validated_snapshot_artifacts(snapshot, run)
        except AgentError as exc:
            missing = (
                f"artifact.{exc.module_id}"
                if getattr(exc, "module_id", None)
                else "accepted_snapshot"
            )
            raise ValueError(
                f"DELIVERABLE_COMPOSITION_REQUIRED_VALUE_MISSING:{missing}"
            ) from exc
        for artifact in validated:
            artifacts[artifact["module_id"]] = artifact
        return artifacts

    def _frozen_evidence(self, case_id: str, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for block in blocks:
            for citation in block.get("citations") or []:
                source = self.store.get_source(citation["source_id"]) or {}
                row = rows.setdefault(citation["source_id"], {
                    "source_id": citation["source_id"], "sha256": source.get("sha256"),
                    "block_ids": [], "withdrawn": bool(source.get("withdrawn")),
                })
                row["block_ids"].extend(b for b in citation["block_ids"] if b not in row["block_ids"])
        return [rows[key] for key in sorted(rows)]

    def freeze(self, case_id: str, request: FreezeDeliverableRequest, *, actor: str) -> dict[str, Any]:
        revision = self._revision_for_freeze(case_id, request)
        pathway = revision["pathway"]
        # Invariant 1 holds at the freeze boundary, not only at draft save: a
        # source withdrawn since the revision was written refuses the freeze.
        self._validate_citations(case_id, revision["content"]["blocks"])
        authority = self._authority_for(case_id)
        if authority is None:
            raise ValueError("DELIVERABLE_UPSTREAM_AUTHORITY_REQUIRED: no accepted upstream SNAPSHOT identity is pinned")
        source_set = self.store.current_source_set(case_id) or {"id": None, "version": 0}
        if authority.get("source_set_id") is not None and (
            source_set["id"], source_set["version"]
        ) != (
            authority["source_set_id"], authority["source_set_version"]
        ):
            raise ValueError("SOURCE_SET_CHANGED: accepted analysis does not cover the current evidence base")
        identity = revision["content"].get("model_identity")
        record = None
        model_payload = None
        document_model = None
        if identity is not None:
            record = (
                self.records.model_by_revision(case_id, identity["revision_id"])
                if identity["kind"] == "ANALYST_REVISION"
                else self.records.model_by_build(case_id, identity["build_id"])
            )
            if record is None:
                # Live Model Builder authority: rehydrate the stored selection
                # and re-pin it, so freeze refuses a stale model like save does.
                stored_selection = revision["content"]["model_selection"]
                record, _selection = self._resolve_stored_selection(case_id, stored_selection)
            document_model = record
            model_payload = {
                **identity,
                "outputs": record["outputs"],
                "effective_assumptions": record["assumptions"],
                "application_build": {"payload": record["build_payload"], "qa": record["build_qa"]},
                "pathway_effects": copy.deepcopy(record.get("pathway_effects") or []),
            }
        self._validate_pathway_authority(case_id, pathway, document_model)
        expected_sections = compose_document(
            pathway=pathway,
            template=_template(pathway),
            blocks=revision["content"]["blocks"],
            artifacts=self._accepted_artifacts(case_id),
            model=document_model,
        )
        if (
            revision["content"].get("document_schema_version") != DOCUMENT_SCHEMA_VERSION
            or revision["content"].get("document_sections") != expected_sections
        ):
            raise ValueError("DELIVERABLE_COMPOSITION_MISMATCH: draft document no longer matches pinned inputs")
        build_id = identity["build_id"] if identity else authority["build_id"]
        methodology_build_id = (
            (identity or {}).get("methodology_build_id")
            or (record or {}).get("methodology_build_id")
            or authority["methodology_build_id"]
        )
        frozen_authority = {
            "snapshot_id": authority["snapshot_id"],
            "source_set_id": source_set["id"],
            "source_set_version": source_set["version"],
            "build_id": build_id,
            "methodology_build_id": methodology_build_id,
        }
        input_fingerprint = digest(frozen_authority)
        template = _template(pathway)
        draft_digest = digest(revision["content"])
        if draft_digest != revision["digest"]:
            raise ValueError(
                "DELIVERABLE_REVISION_INTEGRITY_FAILED: draft digest does not match its content"
            )
        payload = {
            "schema_version": "caos.frozen-deliverable.v1",
            "case_id": case_id,
            "pathway": pathway,
            "template": {"title": template["title"], "template_id": template["template_id"],
                         "template_version": template["template_version"],
                         "block_titles": {item["block_id"]: item["title"] for item in template["blocks"]}},
            "draft": {
                "id": revision["draft_id"],
                "version": revision["version"],
                "digest": draft_digest,
            },
            "content": revision["content"],
            "model": model_payload,
            "authority": {
                "accepted_snapshot_id": frozen_authority["snapshot_id"],
                "source_set_id": frozen_authority["source_set_id"],
                "source_set_version": frozen_authority["source_set_version"],
                "build_id": build_id,
            },
            "evidence": self._frozen_evidence(case_id, revision["content"]["blocks"]),
            "methodology": {"build_id": methodology_build_id},
            "renderer": {"version": "caos.deliverable-renderer.v2"},
            "input_fingerprint": input_fingerprint,
        }
        payload["preview_digest"] = digest({key: value for key, value in payload.items() if key != "preview_digest"})
        thread_id = filing_thread_id(
            case_id=case_id, pathway=pathway, draft_version=revision["version"],
            draft_digest=draft_digest, build_id=build_id,
        )
        with self._freeze_lock:
            rendered = {format_name: self._render(payload, format_name) for format_name in EXPORT_FORMATS}
            exports = {}
            for format_name, content in rendered.items():
                sha256 = hashlib.sha256(content).hexdigest()
                _path, vault_key, size = publish_hash_addressed_bytes(
                    self.vault_dir,
                    ("deliverables", thread_id),
                    format_name,
                    content,
                    expected_sha256=sha256,
                    max_bytes=MAX_EXPORT_BYTES,
                )
                exports[format_name] = {
                    "vault_key": vault_key,
                    "sha256": sha256,
                    "size": size,
                }
            frozen_record = {
                "deliverable_id": f"dlv-{thread_id[4:]}",
                "thread_id": thread_id,
                "case_id": case_id,
                "pathway": pathway,
                "status": "FROZEN",
                "input_fingerprint": input_fingerprint,
                "build_id": build_id,
                "payload": payload,
                "exports": exports,
                "authority": frozen_authority,
                "draft_version": revision["version"],
                "draft_digest": draft_digest,
                "created_by": actor,
            }
            frozen_record["preview_digest"] = frozen_approval_digest(frozen_record)
            self._validate_frozen_integrity(frozen_record)
            record, created = self.records.insert_frozen(
                frozen_record, actor, self.store._audit
            )
        self._validate_frozen_integrity(record)
        if not created and record["preview_digest"] != frozen_record["preview_digest"]:
            # The gate's own render is the only render: a divergent render for
            # the same freeze identity is a conflict, never an overwrite.
            raise ValueError("DELIVERABLE_FREEZE_CONFLICT: a divergent render exists for this freeze identity")
        return record

    def _revision_for_freeze(self, case_id: str, request: FreezeDeliverableRequest) -> dict[str, Any]:
        revision = self.records.revision_for_freeze(
            case_id, request.draft_id, request.draft_version,
        )
        if revision is None or revision["digest"] != request.draft_digest:
            raise ValueError(
                "DELIVERABLE_DRAFT_STALE: freeze identity does not match a stored revision"
            )
        return revision

    # -- filing gate ---------------------------------------------------------

    def frozen_record(self, case_id: str, deliverable_id: str) -> dict[str, Any] | None:
        return self.records.frozen_record(case_id, deliverable_id)

    @staticmethod
    def _validate_frozen_integrity(record: dict[str, Any]) -> None:
        try:
            payload = dict(record["payload"])
            payload_digest = payload.pop("preview_digest", None)
            draft = payload["draft"]
            authority = payload["authority"]
            thread_id = filing_thread_id(
                case_id=record["case_id"],
                pathway=record["pathway"],
                draft_version=record["draft_version"],
                draft_digest=record["draft_digest"],
                build_id=record["build_id"],
            )
            valid = (
                isinstance(draft, dict)
                and isinstance(payload["content"], dict)
                and isinstance(draft.get("id"), str)
                and bool(draft["id"])
                and type(record["draft_version"]) is int
                and type(draft["version"]) is int
                and payload["case_id"] == record["case_id"]
                and payload["pathway"] == record["pathway"]
                and draft["version"] == record["draft_version"]
                and draft["digest"] == record["draft_digest"]
                and record["draft_digest"] == digest(payload["content"])
                and payload["input_fingerprint"] == record["input_fingerprint"]
                and authority["build_id"] == record["build_id"]
                and record["authority"]["build_id"] == record["build_id"]
                and record["thread_id"] == thread_id
                and record["deliverable_id"] == f"dlv-{thread_id[4:]}"
                and payload_digest == digest(payload)
                and frozen_approval_digest(record) == record["preview_digest"]
            )
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise ValueError(
                "DELIVERABLE_PREVIEW_INTEGRITY_FAILED: frozen content or export manifest does not match its digest"
            )

    def approve_filing(self, case_id: str, deliverable_id: str, request: FileDeliverableRequest, *, actor: str) -> dict[str, Any]:
        record = self.records.frozen_record(case_id, deliverable_id)
        if record is None:
            raise ValueError("DELIVERABLE_NOT_FOUND")
        thread = self.records.thread_state(record["thread_id"])
        interrupt_id = thread["interrupt_id"] if thread else None
        if record["status"] != "FROZEN" or thread is None or thread["status"] != "PARKED":
            raise ResumeNotApplied(interrupt_id if thread and thread["status"] == "PARKED" else None)
        self._validate_frozen_integrity(record)
        if request.preview_digest != record["preview_digest"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: approval binds the exact frozen PREVIEW digest")
        if request.input_fingerprint != record["input_fingerprint"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: approval FINGERPRINT does not match the frozen identity")
        guard = self.models.publication_guard() if self.models is not None else nullcontext()
        with self.store.authority_guard(), guard:
            content = record["payload"].get("content") or {}
            try:
                current_model, selection = self._resolve_stored_selection(
                    case_id,
                    content.get("model_selection"),
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "FROZEN_MODEL_AUTHORITY_STALE: the selected model moved after freeze"
                ) from exc
            frozen_identity = content.get("model_identity")
            current_identity = (
                self._model_identity(current_model, selection)
                if current_model is not None and selection is not None
                else None
            )
            if current_identity != frozen_identity:
                raise ValueError(
                    "FROZEN_MODEL_AUTHORITY_STALE: the selected model moved after freeze"
                )
            self._validate_pathway_authority(case_id, record["pathway"], current_model)
            authority = self._authority_for(case_id)
            if (
                authority is None
                or authority["snapshot_id"] != record["authority"]["snapshot_id"]
                or authority["methodology_build_id"] != record["authority"]["methodology_build_id"]
                or authority.get("source_set_id") not in {
                    None,
                    record["authority"]["source_set_id"],
                }
                or authority.get("source_set_version") not in {
                    None,
                    record["authority"]["source_set_version"],
                }
            ):
                raise ValueError("FROZEN_AUTHORITY_STALE: the accepted upstream authority moved after freeze")
            current_set = self.store.current_source_set(case_id) or {"id": None, "version": 0}
            if (current_set["id"], current_set["version"]) != (
                record["authority"]["source_set_id"], record["authority"]["source_set_version"],
            ):
                raise ValueError("SOURCE_SET_CHANGED: the evidence base moved while the gate was parked")
            self._accepted_artifacts(case_id)
            self._verify_frozen_exports(record)
            filed = self.records.file_record(deliverable_id, actor, self.store._audit)
        if filed is None:
            raise ResumeNotApplied(None)
        return filed

    def request_changes(self, case_id: str, deliverable_id: str, request: Any, *, actor: str) -> dict[str, Any]:
        record = self.records.frozen_record(case_id, deliverable_id)
        if record is None:
            raise ValueError("DELIVERABLE_NOT_FOUND")
        self._validate_frozen_integrity(record)
        if request.preview_digest != record["preview_digest"] or request.input_fingerprint != record["input_fingerprint"]:
            raise ValueError("DELIVERABLE_STALE_PREVIEW: change requests bind the exact frozen preview")
        head = self.records.head_revision(case_id, record["pathway"])
        content = copy.deepcopy(head["content"])
        content["change_request"] = {
            "comment": request.comment,
            "requested_by": actor,
            "deliverable_id": deliverable_id,
        }
        outcome = self.records.request_changes_and_append_revision(
            deliverable_id,
            head["version"],
            content,
            digest(content),
            actor,
            request.comment,
            self.store._audit,
        )
        if outcome is None:
            raise ResumeNotApplied(None)
        updated, draft = outcome
        return {"frozen": updated, "draft": draft}

    # -- exports -------------------------------------------------------------

    def _verified_export(self, record: dict[str, Any], format_name: str) -> bytes:
        recorded = (record["exports"] or {}).get(format_name)
        if recorded is None:
            raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: no stored export for this format")
        try:
            return read_verified_vault_bytes(
                self.vault_dir,
                recorded.get("vault_key", f"deliverables/{record['thread_id']}/{format_name}"),
                expected_sha256=recorded["sha256"],
                expected_size=recorded["size"],
                max_bytes=MAX_EXPORT_BYTES,
            )
        except VaultFileUnavailable as exc:
            raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: no stored export for this format") from exc
        except VaultFileIntegrityError as exc:
            raise ValueError(
                "DELIVERABLE_EXPORT_INTEGRITY_FAILED: stored bytes do not match the frozen record"
            ) from exc

    def _verify_frozen_exports(self, record: dict[str, Any]) -> None:
        if set(record["exports"] or {}) != set(EXPORT_FORMATS):
            raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: frozen export set is incomplete")
        for format_name in EXPORT_FORMATS:
            self._verified_export(record, format_name)

    def export(self, deliverable_id: str, format_name: str) -> tuple[bytes, str]:
        record = self._frozen_by_id(deliverable_id)
        self._validate_frozen_integrity(record)
        recorded = (record["exports"] or {}).get(format_name)
        if recorded is None:
            raise ValueError("DELIVERABLE_EXPORT_UNAVAILABLE: no stored export for this format")
        # Read through the no-follow descriptor chain, verified against the
        # frozen record's digest AND length, so a symlink or a non-regular file
        # standing where the export should be is refused rather than followed.
        content = self._verified_export(record, format_name)
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
        with self.store.authority_guard():
            return self.records.set_authority(case_id, new_id("snap"), f"deploy-v-{new_id('bld')[4:]}")

    def supersede_accepted_authority_for_tests(self, case_id: str) -> dict[str, Any]:
        with self.store.authority_guard():
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
        path = self.vault_dir / record["exports"][format_name]["vault_key"]
        path.write_bytes(path.read_bytes() + b"tampered")

    def delete_export_for_tests(self, deliverable_id: str, format_name: str) -> None:
        record = self._frozen_by_id(deliverable_id)
        (self.vault_dir / record["exports"][format_name]["vault_key"]).unlink(missing_ok=True)

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
