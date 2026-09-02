"""Strict wire response contracts: nothing undeclared is ever served.

Shapes carry forward from LEGACY responses.py trimmed to the MVP surface.
Optional-omitted fields (a queued build's payload, a run's generation state, a
source's source_set) dump exactly as they validated — omission is preserved,
never fabricated (model_dump defaults to exclude_unset).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts import CanonicalDocumentSection


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # noqa: D102 — omission-preserving dump
        kwargs.setdefault("exclude_unset", True)
        return super().model_dump(**kwargs)


class OpenWireModel(WireModel):
    """Named component for surfaces whose payload shape is service-owned."""

    model_config = ConfigDict(extra="allow")


class IdentityResponse(WireModel):
    subject: str
    email: str | None
    role: str


class ProviderIdentityResponse(WireModel):
    provider_name: str
    model: str
    provider_version: str | None
    adapter_version: str
    parameter_context_digest: str
    qualification_record_id: str | None
    qualification_record_digest: str | None
    qualification_status: str
    qualification_expires_at: str | None
    identity_digest: str

    @model_validator(mode="after")
    def verify_identity(self) -> "ProviderIdentityResponse":
        from .engine.provider import AgentError, ProviderIdentity

        try:
            ProviderIdentity.from_dict(super().model_dump(mode="python"))
        except AgentError as exc:
            raise ValueError("provider identity is invalid") from exc
        return self


class HealthResponse(WireModel):
    """Liveness *and* readiness on one route. The booleans name which subsystem
    is down and nothing more — /api/health is the only unauthenticated route, so
    it never serves a path, a DSN, a build id, or an exception message."""

    status: Literal["ok", "degraded"]
    store: bool
    bundle: bool
    checkpointer: bool


class CasePathwayFitResponse(WireModel):
    """The source-coverage signal the Cases screen renders. Only the two fields
    the frontend declares are served; sources.domain.pathway_fit computes more,
    and the rest stay internal rather than widening the wire speculatively."""

    fit: Literal["READY", "NEEDS_SOURCE"]
    message: str


class CaseResponse(WireModel):
    id: str
    name: str
    issuer: str
    sector: str
    created_by: str
    created_at: str
    members: dict[str, str]
    accepted_snapshot_id: str | None
    visible_snapshot_id: str | None
    current_execution_id: str | None
    source_count: int
    # The engine's own MVP cut, served so a client never offers a route the
    # engine will refuse. Deep Research keeps its separate, actor-specific gate
    # below: this list answers "will this deployment start it", not "may you".
    available_pathways: list[str]
    deep_research_available: bool
    deep_research_unavailable_reason: str | None
    pathway_fit: CasePathwayFitResponse


class CaseDetailResponse(CaseResponse):
    pass


class CaseLensSourceSetResponse(WireModel):
    version: int


class CaseLensResponse(WireModel):
    issuer: str
    sector: str
    accepted_snapshot_id: str | None
    source_set: CaseLensSourceSetResponse | None


class SourceSetResponse(WireModel):
    id: str
    case_id: str
    version: int
    source_ids: list[str]
    created_by: str
    created_at: str


class SourceBlockResponse(WireModel):
    block_id: str
    text: str
    locator: Any
    confidence: str | None
    untrusted_data: bool
    extractor_version: str | None


class SourceResponse(WireModel):
    id: str
    case_id: str
    filename: str
    media_type: str
    bytes: int
    sha256: str
    created_by: str
    created_at: str
    blocks: list[SourceBlockResponse]
    withdrawn: bool
    source_kind: str | None = None
    source_set: SourceSetResponse | None = None


class RunNodeResponse(WireModel):
    id: str
    run_id: str
    case_id: str
    module_id: str
    stage: int
    dependencies: list[str]
    status: str
    attempt: int
    artifact_id: str | None
    error: Any


class RunEventResponse(WireModel):
    id: int
    event: str
    at: str
    data: Any


class RunResponse(WireModel):
    id: str
    case_id: str
    status: str
    plan: Any
    node_ids: list[str]
    nodes: list[RunNodeResponse]
    events: list[RunEventResponse]
    current_node_id: str | None
    accepted_snapshot_id: str | None
    upgraded_from_run_id: str | None
    created_by: str
    created_at: str
    error: Any
    provider_identity: ProviderIdentityResponse | None


class ProviderAttemptResponse(WireModel):
    run_id: str
    module_id: str
    kind: str
    provider_identity: ProviderIdentityResponse | None
    request_digest: str | None = None
    response_digest: str | None = None
    provider_request_id: str | None = None
    observed_model: str | None = None
    observed_provider_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    stop_reason: str | None = None
    retry_index: int | None = None
    terminal_code: str | None = None
    operation: str | None = None


class CanonicalGenerationResponse(WireModel):
    phase: str
    model: str | None
    provider_identity: ProviderIdentityResponse | None
    reporting_period: str
    module_output_tokens: dict[str, int]
    budget_limits: dict[str, Any]
    budget_used: dict[str, Any]
    inflight_request_digest: str | None
    attempts: list[ProviderAttemptResponse]
    completed_modules: list[str] | None = None


class CanonicalGenerationProgressResponse(CanonicalGenerationResponse):
    pass


class ResearchBriefResponse(WireModel):
    research_question: str
    decision_context: str
    as_of_date: str
    time_horizon: str
    must_answer: list[str]
    exclusions: list[str]


class ResearchWorkstreamResponse(WireModel):
    id: str
    kind: str
    question: str
    assigned_questions: list[str]
    perspective: str
    hypothesis: str
    evidence_needs: list[str]
    source_classes: list[str]
    disconfirming_test: str
    completion_test: str
    effort_cap: str


class ResearchPlanSourceSetResponse(WireModel):
    id: str
    version: int


class ResearchPlanUpstreamResponse(WireModel):
    module_id: str
    artifact_id: str
    digest: str


class ResearchPlanScopeResponse(WireModel):
    type: str
    key: str
    source_mode: str


class ResearchPlanResponse(WireModel):
    """The host-proposed plan exactly as reviewed; its canonical digest is the
    approval hash (invariant 5). Served only on DEEP_RESEARCH runs."""

    schema_version: str
    methodology_build_id: str
    run_plan_digest: str
    brief_digest: str
    source_set: ResearchPlanSourceSetResponse
    upstream_artifacts: list[ResearchPlanUpstreamResponse]
    scope: ResearchPlanScopeResponse
    workstreams: list[ResearchWorkstreamResponse]


class ResearchStateResponse(WireModel):
    phase: Literal["brief_locked", "awaiting_approval", "approved"]
    brief: ResearchBriefResponse
    brief_digest: str
    proposed_plan_hash: str | None
    approved_plan_hash: str | None
    approved_by: str | None
    approved_at: str | None
    proposed_plan: ResearchPlanResponse | None


class CanonicalRunResponse(RunResponse):
    canonical_generation: CanonicalGenerationResponse | None = None
    # Present on DEEP_RESEARCH runs only; omitted (never null) elsewhere, so the
    # pinned run key set does not move for the five other pathways.
    research: ResearchStateResponse | None = None


class SnapshotArtifactRefResponse(WireModel):
    id: str
    module_id: str
    digest: str


class SnapshotResponse(WireModel):
    id: str
    case_id: str
    run_id: str
    source_set_id: str
    source_set_version: int
    artifacts: list[SnapshotArtifactRefResponse]
    digest: str
    previous_snapshot_id: str | None
    accepted_at: str
    provider_identity: ProviderIdentityResponse | None


class SnapshotDiffEntryResponse(WireModel):
    module_id: str
    digest: str


class SnapshotDiffResponse(WireModel):
    changed: bool
    added: list[SnapshotDiffEntryResponse]
    removed: list[SnapshotDiffEntryResponse]
    modified: list[SnapshotDiffEntryResponse]
    source_set_changed: bool


class SnapshotViewResponse(WireModel):
    accepted: SnapshotResponse | None
    latest_accepted: SnapshotResponse | None
    switch_required: bool
    diff: SnapshotDiffResponse | None


class ArtifactResponse(WireModel):
    id: str
    case_id: str
    run_id: str
    module_id: str
    payload: Any
    markdown: str | None
    digest: str
    input_fingerprint: str
    created_by: str
    created_at: str
    provider_identity: ProviderIdentityResponse | None


class CalculationRuntimeResponse(WireModel):
    name: str
    version: str
    sha256: str
    assumption_registry_version: str | None
    assumption_registry_digest: str | None
    calculation_contract_version: str | None


class ModelExportStateResponse(WireModel):
    status: str
    error: Any


class ModelBuildResponse(WireModel):
    id: str
    case_id: str
    accepted_run_id: str | None
    accepted_snapshot_id: str | None
    source_set_id: str | None
    input_fingerprint: str
    status: str
    queued_at: str
    started_at: str | None
    completed_at: str | None
    error: Any
    export: ModelExportStateResponse | None
    worksheet_schema_version: str | None
    calculation_runtime: CalculationRuntimeResponse | None
    payload: Any = None
    payload_digest: str | None = None
    qa: Any = None


class ModelReadinessRequirementResponse(WireModel):
    module_id: str
    status: str


class ModelReadinessBlockerResponse(WireModel):
    code: str
    detail: str | None


class ModelReadinessResponse(WireModel):
    status: str
    module_id: str
    accepted_snapshot: Any
    source_set: Any
    requirements: list[ModelReadinessRequirementResponse]
    calculation_runtime: Any
    worksheet_schema_version: str | None
    blockers: list[ModelReadinessBlockerResponse]
    build: ModelBuildResponse | None


class ModelListResponse(WireModel):
    builds: list[ModelBuildResponse]


class ModelQueueResponse(OpenWireModel):
    id: str
    created: bool


class ModelAssumptionRegistryResponse(OpenWireModel):
    pass


class ModelWorksheetResponse(OpenWireModel):
    pass


class ModelPreviewResponse(OpenWireModel):
    pass


class ModelRebasePreviewResponse(OpenWireModel):
    pass


class ModelRevisionResponse(OpenWireModel):
    pass


class ModelRevisionListResponse(WireModel):
    revisions: list[Any]


class ModelRevisionExportStateResponse(WireModel):
    status: Literal["NOT_REQUESTED", "QUEUED", "EXPORTING", "READY", "FAILED"]
    error: Any | None = None
    filename: str | None = None
    sha256: str | None = None
    size: int | None = None


class ModelRevisionExportStatusResponse(WireModel):
    revision_id: str
    export: ModelRevisionExportStateResponse


class ModelRevisionExportStatusListResponse(WireModel):
    exports: list[ModelRevisionExportStatusResponse]


class AuditEventResponse(WireModel):
    id: str
    actor: str
    at: str
    action: str
    case_id: str | None = None
    member: str | None = None
    role: str | None = None
    source_id: str | None = None
    sha256: str | None = None
    snapshot_id: str | None = None
    run_id: str | None = None
    note_id: str | None = None
    assumption_id: str | None = None
    build_id: str | None = None
    model_id: str | None = None
    report_id: str | None = None
    plan_hash: str | None = None
    code: str | None = None
    version: int | None = None
    revision_id: str | None = None
    revision_number: int | None = None
    assumptions_digest: str | None = None
    deliverable_id: str | None = None
    preview_digest: str | None = None
    pathway: str | None = None
    comment: str | None = None
    provider_identity_digest: str | None = None


class ThesisResponse(WireModel):
    id: str
    case_id: str
    thesis: str
    updated_by: str
    updated_at: str


class VisualRecipeValidationResponse(WireModel):
    kind: str
    fields: list[str]
    units: str
    metric_ids: list[str]
    polarity: str
    accessible_table: bool


class NoteResponse(WireModel):
    id: str
    case_id: str
    body: str
    created_by: str
    created_at: str
    promoted: bool
    promoted_source_id: str | None


class LoanUniverseFindingResponse(WireModel):
    code: str
    detail: str
    sheet: str | None
    row: int | None
    column: str | None


class LoanUniverseResponse(WireModel):
    id: str
    case_id: str
    source_id: str
    source_filename: str
    source_sha256: str
    workbook_date: str | None
    template_version: str
    importer_version: str
    universe_digest: str | None
    row_count: int
    status: str
    findings: list[LoanUniverseFindingResponse]
    created_at: str
    created_by: str
    version: int | None
    activated_at: str | None
    superseded_at: str | None
    withdrawn_at: str | None


class LoanUniverseActiveResponse(WireModel):
    status: str
    universe: LoanUniverseResponse | None
    rows: list[Any]


class RVUniverseVersionResponse(WireModel):
    id: str
    case_id: str
    version: int
    rows: list[Any]
    created_by: str
    created_at: str


class RVWorkspaceResponse(WireModel):
    universe: RVUniverseVersionResponse | None


class DeliverableContentResponse(OpenWireModel):
    template_id: str
    template_version: str
    document_schema_version: str | None = None
    document_sections: list[CanonicalDocumentSection] | None = None
    model_selection: Any | None
    model_identity: Any | None
    blocks: list[Any]
    generated_blocks: dict[str, Any]


class DeliverableRevisionResponse(WireModel):
    id: str
    # The draft this revision belongs to. FreezeDeliverableRequest is keyed on it,
    # and `id` is the revision — serving only the revision left every client
    # sending the wrong identity and every freeze refused as an unknown draft.
    draft_id: str
    case_id: str
    pathway: str
    version: int
    author: str
    created_at: str
    template_id: str
    template_version: str
    digest: str
    content: DeliverableContentResponse


class ModelEligibilityResponse(WireModel):
    active_revision: Any | None
    application_build: Any | None
    fallback_acknowledgement_required: bool
    default_model_selection: Any | None


class DeliverableWorkspaceResponse(WireModel):
    template: Any
    current: DeliverableRevisionResponse | None
    history: list[DeliverableRevisionResponse]
    frozen_history: list[Any]
    model_eligibility: ModelEligibilityResponse


class FrozenDeliverableResponse(OpenWireModel):
    id: str
    case_id: str
    pathway: str
    status: str
    draft_version: int
    preview_digest: str
    input_fingerprint: str


class DeliverableChangeRequestResponse(WireModel):
    frozen: FrozenDeliverableResponse
    draft: DeliverableRevisionResponse


class ModelScenarioResponse(OpenWireModel):
    draft_generation: int
    scenario: Any
    scenario_digest: str


class ModelTornadoResponse(OpenWireModel):
    pass


class ModelSensitivityResponse(OpenWireModel):
    pass
