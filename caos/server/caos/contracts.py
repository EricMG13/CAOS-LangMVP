from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator


class Role(StrEnum):
    ANALYST = "ANALYST"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"
    READER = "READER"


class Depth(StrEnum):
    SCREEN = "screen"
    FULL = "full"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NodeStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"  # in flight when the run failed elsewhere; abandoned, not failed


class SystemSignal(StrEnum):
    ATTRACTIVE = "ATTRACTIVE"
    FAIR = "FAIR"
    UNATTRACTIVE = "UNATTRACTIVE"


class Recommendation(StrEnum):
    OVERWEIGHT = "OVERWEIGHT"
    MARKET_WEIGHT = "MARKET WEIGHT"
    UNDERWEIGHT = "UNDERWEIGHT"
    NA = "N/A"


class WorkspaceTheme(StrEnum):
    DARK = "dark"
    LIGHT = "light"


PATHWAYS = {
    "FULL_CREDIT": "Full Credit",
    "EARNINGS_UPDATE": "Earnings Update",
    "COVENANT_REFINANCING": "Covenant & Refinancing",
    "RELATIVE_VALUE": "Relative Value",
    "DISTRESSED_RESTRUCTURING": "Distressed & Restructuring",
    "DEEP_RESEARCH": "Deep Research",
}

INTERNAL_PATHWAYS = (*PATHWAYS.keys(), "PORTFOLIO_DECISION", "DECISION_LEDGER")

DESTINATIONS = (
    "Cases",
    "Sources",
    "Run Console",
    "Deep-Dive",
    "RV Screener",
    "Command Center",
    "Model Builder",
    "Report Studio",
)


# Bidirectional embedding, override and isolate controls (CVE-2021-42574,
# "Trojan Source"). These reorder how text DISPLAYS without changing a byte, so
# a narrative can render one way to the approver binding its preview digest and
# another to whoever reads the filed PDF. Directional MARKS (U+200E/U+200F,
# U+061C) are deliberately not here: ordinary Arabic and Hebrew issuer names
# need them, and they cannot reorder surrounding runs.
BIDI_CONTROLS = frozenset(
    "\u202a\u202b\u202c\u202d\u202e"  # LRE RLE PDF LRO RLO
    "\u2066\u2067\u2068\u2069"          # LRI RLI FSI PDI
)


def validate_boundary_text(value: str) -> str:
    """Unicode boundary (DECISIONS §12.3): strings that can enter pinned state
    or events must UTF-8-encode (no lone surrogates), carry no control bytes or
    bidirectional overrides, and are NFC-normalized before any pin is computed."""
    import unicodedata

    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text contains unencodable code points") from exc
    if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value):
        raise ValueError("text contains control characters")
    if not BIDI_CONTROLS.isdisjoint(value):
        raise ValueError("text contains bidirectional override characters")
    return unicodedata.normalize("NFC", value)


def _boundary_before(value: Any) -> Any:
    """Normalize BEFORE the length constraint, not after.

    NFC can lengthen a string: U+0958 DEVANAGARI KA WITH NUKTA is a composition
    exclusion that folds to two code points, so a max_length=160 field validated
    first and folded second stores up to 320 characters — its declared bound
    silently bypassed. Running first means min_length/max_length see exactly
    what gets stored.

    Running first also means this sees the RAW input, so it must cover every
    shape pydantic will accept as a string. `bytes` is one: in lax mode pydantic
    decodes it, so guarding on `isinstance(value, str)` alone let a control byte
    or an un-normalized form in through a door the AfterValidator form had shut.
    Anything else — an int, a list — passes through untouched for the str schema
    to refuse, so `name: 123` still fails as string_type rather than raising from
    inside this validator.
    """
    if isinstance(value, (bytes, bytearray)):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return value  # let the str schema refuse it
    return validate_boundary_text(value) if isinstance(value, str) else value


# Every string that can enter pinned state or an event carries this: it must
# UTF-8-encode, hold no control bytes, and be NFC-normalized BEFORE any digest
# is taken, so two spellings of the same issuer cannot mint two lineages.
BoundaryText = Annotated[str, BeforeValidator(_boundary_before)]


def _nonblank_after(value: str) -> str:
    if not value.strip():
        raise ValueError("text must contain a non-whitespace character")
    return value


NonBlankBoundaryText = Annotated[BoundaryText, AfterValidator(_nonblank_after)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCaseRequest(StrictModel):
    name: NonBlankBoundaryText = Field(min_length=1, max_length=160)
    issuer: NonBlankBoundaryText = Field(min_length=1, max_length=160)
    sector: BoundaryText = Field(default="Unclassified", max_length=120)


class MemberRequest(StrictModel):
    subject: str = Field(min_length=1, max_length=200)
    role: Role = Role.READER


class MethodologyDraftRequest(StrictModel):
    expected_build_id: str = Field(min_length=64, max_length=64)
    module_id: str = Field(min_length=3, max_length=40)
    field: Literal["reader_question", "required_decision_drivers", "prohibited_conclusions", "visual_recipe"]
    before: str = Field(min_length=1, max_length=4000)
    after: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)


class ConfirmDraftRequest(StrictModel):
    confirmation: Literal["CONFIRM_DRAFT"]


# The brief reaches pinned run state (the plan digest binds its digest), so
# every string is BoundaryText, never a bare str.
ResearchBriefItem = Annotated[BoundaryText, Field(min_length=1, max_length=200)]
ResearchBriefText = Annotated[BoundaryText, Field(min_length=1, max_length=400)]
# Item-level caps for the other wire string lists. A `max_length` on the list
# bounds the count only; without these each element is unbounded.
FocusQuestion = Annotated[BoundaryText, Field(min_length=1, max_length=400)]
ThesisItem = Annotated[str, Field(min_length=1, max_length=400)]
IdentifierItem = Annotated[str, Field(min_length=1, max_length=120)]


class ResearchBrief(StrictModel):
    research_question: ResearchBriefText
    decision_context: ResearchBriefText
    as_of_date: date
    time_horizon: Annotated[BoundaryText, Field(min_length=1, max_length=200)]
    must_answer: list[ResearchBriefItem] = Field(default_factory=list, max_length=10)
    exclusions: list[ResearchBriefItem] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def combined_item_cap(self) -> ResearchBrief:
        if not all(value.strip() for value in (self.research_question, self.decision_context, self.time_horizon, *self.must_answer, *self.exclusions)):
            raise ValueError("research brief text must not be blank")
        if len(self.must_answer) + len(self.exclusions) > 10:
            raise ValueError("must_answer and exclusions may contain at most 10 entries combined")
        return self


class StartRunRequest(StrictModel):
    pathway: str
    depth: Depth
    focus_questions: list[FocusQuestion] = Field(default_factory=list, max_length=5)
    research_brief: ResearchBrief | None = None

    @field_validator("pathway")
    @classmethod
    def known_pathway(cls, value: str) -> str:
        if value not in PATHWAYS:
            raise ValueError("unknown pathway")
        return value

    @model_validator(mode="after")
    def research_pathway_contract(self) -> StartRunRequest:
        if self.pathway == "DEEP_RESEARCH":
            if self.depth is not Depth.FULL:
                raise ValueError("DEEP_RESEARCH requires full depth")
            if self.research_brief is None:
                raise ValueError("DEEP_RESEARCH requires a research brief")
        elif self.research_brief is not None:
            raise ValueError("research_brief is only valid for DEEP_RESEARCH")
        return self


class ApproveResearchPlanRequest(StrictModel):
    plan_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ThesisRequest(StrictModel):
    expected_version: int = Field(ge=0)
    core_thesis: str = Field(min_length=1, max_length=4000)
    drivers: list[ThesisItem] = Field(default_factory=list, max_length=12)
    risks: list[ThesisItem] = Field(default_factory=list, max_length=12)
    catalysts: list[ThesisItem] = Field(default_factory=list, max_length=12)
    unresolved_questions: list[ThesisItem] = Field(default_factory=list, max_length=12)
    evidence_ids: list[IdentifierItem] = Field(default_factory=list, max_length=50)


class RecommendationRow(StrictModel):
    instrument_id: str = Field(min_length=1, max_length=120)
    instrument: str = Field(min_length=1, max_length=160)
    recommendation: Recommendation
    rationale: str = Field(min_length=1, max_length=2000)
    primary: bool = False


class RecommendationMatrixRequest(StrictModel):
    expected_version: int = Field(ge=0)
    market_snapshot_id: str = Field(min_length=1, max_length=120)
    rows: list[RecommendationRow] = Field(min_length=1, max_length=50)
    analytical_dependency_ids: list[IdentifierItem] = Field(default_factory=list, max_length=50)

    @field_validator("rows")
    @classmethod
    def complete_rows(cls, value: list[RecommendationRow]) -> list[RecommendationRow]:
        if any(not row.recommendation for row in value):
            raise ValueError("blank recommendations are not allowed")
        primaries = sum(row.primary for row in value)
        if primaries != 1:
            raise ValueError("select exactly one primary instrument")
        return value


class ReportInputsRequest(StrictModel):
    thesis: ThesisRequest
    recommendations: RecommendationMatrixRequest


class NoteRequest(StrictModel):
    body: BoundaryText = Field(min_length=1, max_length=12000)


class AssumptionRequest(StrictModel):
    statement: str = Field(min_length=1, max_length=2000)
    supporting_claim: str = Field(default="", max_length=2000)
    conflicting_claim: str = Field(default="", max_length=2000)
    evidence_ids: list[IdentifierItem] = Field(default_factory=list, max_length=50)
    affected_module_ids: list[IdentifierItem] = Field(default_factory=list, max_length=30)


class ModelAssumptionSourceRef(StrictModel):
    source_id: str = Field(min_length=1, max_length=200)
    source_locator: str = Field(min_length=1, max_length=1000)
    as_of: str = Field(min_length=1, max_length=40)


class ModelAssumptionSourceContext(StrictModel):
    authority_module: Literal["CP-2G"]
    gap_code: str = Field(max_length=160)
    provenance: list[ModelAssumptionSourceRef] = Field(max_length=8)


class ModelAssumptionValue(StrictModel):
    assumption_id: str = Field(min_length=1, max_length=160)
    case: Literal["BASE", "DOWNSIDE"]
    period_id: str = Field(pattern=r"^FY[0-9]{4}$")
    unit: str = Field(min_length=1, max_length=40)
    status: Literal["READY", "UNAVAILABLE", "NOT_APPLICABLE"]
    value: float | None
    gap_code: str | None = Field(default=None, max_length=160)
    default_value: float | None = None
    default_status: Literal["READY", "UNAVAILABLE", "NOT_APPLICABLE"] | None = None
    default_gap_code: str | None = Field(default=None, max_length=160)
    source_context: ModelAssumptionSourceContext | None = None
    source_context_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )

    @field_validator("value", "default_value")
    @classmethod
    def finite_value(cls, value: float | None) -> float | None:
        return finite_or_none(value)


class ModelPreviewRequest(StrictModel):
    build_id: str = Field(min_length=1, max_length=120)
    parent_revision_id: str | None = Field(default=None, max_length=120)
    registry_version: str = Field(min_length=1, max_length=160)
    registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assumptions: list[ModelAssumptionValue] = Field(min_length=1, max_length=256)
    draft_generation: int = Field(default=0, ge=0, le=2_147_483_647)


class ModelTornadoRequest(ModelPreviewRequest):
    case: Literal["BASE", "DOWNSIDE"] = "BASE"
    output_period_id: str = Field(pattern=r"^(BASE|DOWNSIDE)::FY[0-9]{4}$")
    output_id: str = Field(default="net_leverage", min_length=1, max_length=120)
    intensity: float = Field(default=1, gt=0, le=2)

    @field_validator("intensity")
    @classmethod
    def finite_intensity(cls, value: float) -> float:
        checked = finite_or_none(value)
        assert checked is not None
        return checked


class ModelSignOffRequest(ModelPreviewRequest):
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_head_revision_id: str | None = Field(default=None, max_length=120)
    note: BoundaryText = Field(min_length=1, max_length=2000)

    @field_validator("note")
    @classmethod
    def nonblank_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sign-off note must not be blank")
        return value


class ModelRebasePreviewRequest(StrictModel):
    revision_id: str = Field(min_length=1, max_length=120)
    build_id: str = Field(min_length=1, max_length=120)
    draft_generation: int = Field(default=0, ge=0, le=2_147_483_647)


class ModelShock(StrictModel):
    assumption_id: str = Field(min_length=1, max_length=160)
    case: Literal["BASE", "DOWNSIDE"]
    period_id: str = Field(pattern=r"^FY[0-9]{4}$")
    value: float

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float) -> float:
        checked = finite_or_none(value)
        assert checked is not None
        return checked


class ModelScenarioRequest(StrictModel):
    build_id: str = Field(min_length=1, max_length=120)
    base_revision_id: str | None = Field(default=None, max_length=120)
    registry_version: str = Field(min_length=1, max_length=160)
    registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    shocks: list[ModelShock] = Field(min_length=1, max_length=256)
    draft_generation: int = Field(default=0, ge=0, le=2_147_483_647)


class OneWaySensitivityRequest(StrictModel):
    build_id: str = Field(min_length=1, max_length=120)
    base_revision_id: str | None = Field(default=None, max_length=120)
    registry_version: str = Field(min_length=1, max_length=160)
    registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    assumption_id: str = Field(min_length=1, max_length=160)
    case: Literal["BASE", "DOWNSIDE"]
    period_scope: str = Field(pattern=r"^(ALL|FY[0-9]{4})$")
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    output_id: str = Field(default="total_leverage", min_length=1, max_length=120)
    draft_generation: int = Field(default=0, ge=0, le=2_147_483_647)

    @field_validator("minimum", "maximum", "step")
    @classmethod
    def finite_range(cls, value: float | None) -> float | None:
        return finite_or_none(value)


class EvidenceCitation(StrictModel):
    source_id: str = Field(min_length=1, max_length=120)
    block_ids: list[IdentifierItem] = Field(min_length=1, max_length=50)
    claim: BoundaryText = Field(min_length=1, max_length=1000)


class AnalystRevisionSelection(StrictModel):
    kind: Literal["ANALYST_REVISION"]
    build_id: str = Field(min_length=1, max_length=120)
    revision_id: str = Field(min_length=1, max_length=120)


class ApplicationBuildSelection(StrictModel):
    kind: Literal["APPLICATION_BUILD"]
    build_id: str = Field(min_length=1, max_length=120)
    fallback_acknowledged: Literal[True]


DeliverableModelSelection = Annotated[
    AnalystRevisionSelection | ApplicationBuildSelection,
    Field(discriminator="kind"),
]


class DeliverableBlock(StrictModel):
    block_id: str = Field(min_length=1, max_length=160)
    slot_id: str = Field(min_length=1, max_length=160)


class HeadingBlock(DeliverableBlock):
    kind: Literal["HEADING"]
    text: BoundaryText = Field(min_length=1, max_length=240)


class NarrativeBlock(DeliverableBlock):
    kind: Literal["NARRATIVE"]
    text: BoundaryText = Field(min_length=1, max_length=20_000)
    content_mode: Literal["EVIDENCE", "ANALYST_JUDGMENT"]
    citations: list[EvidenceCitation] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def material_claim_has_authority(self) -> NarrativeBlock:
        if not self.text.strip():
            raise ValueError("narrative text must not be blank")
        if self.content_mode == "EVIDENCE" and not self.citations:
            raise ValueError("evidence narrative requires a citation")
        return self


class GeneratedMetricBlock(DeliverableBlock):
    kind: Literal["GENERATED_METRIC"]
    metric_ids: list[IdentifierItem] = Field(min_length=1, max_length=40)


class GeneratedTableBlock(DeliverableBlock):
    kind: Literal["GENERATED_TABLE"]
    table_id: str = Field(min_length=1, max_length=120)
    field_ids: list[IdentifierItem] = Field(min_length=1, max_length=80)


class GeneratedChartBlock(DeliverableBlock):
    kind: Literal["GENERATED_CHART"]
    recipe: dict[str, Any]


class ScenarioEnvelope(StrictModel):
    case_id: str = Field(min_length=1, max_length=120)
    build_id: str = Field(min_length=1, max_length=120)
    base_revision_id: str | None = Field(default=None, max_length=120)
    registry_version: str = Field(min_length=1, max_length=160)
    registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    draft_generation: int = Field(ge=0, le=2_147_483_647)
    effective_assumptions: list[dict[str, Any]] = Field(min_length=1, max_length=256)
    assumptions_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    outputs: dict[str, Any]
    outputs_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    deltas: dict[str, Any]


class ScenarioExhibitBlock(DeliverableBlock):
    kind: Literal["SCENARIO_EXHIBIT"]
    title: BoundaryText = Field(min_length=1, max_length=240)
    shocks: list[ModelShock] = Field(min_length=1, max_length=256)
    scenario: ScenarioEnvelope
    scenario_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceRegisterBlock(DeliverableBlock):
    kind: Literal["EVIDENCE_REGISTER"]
    citations: list[EvidenceCitation] = Field(default_factory=list, max_length=500)


class ModelAppendixBlock(DeliverableBlock):
    kind: Literal["MODEL_APPENDIX"]


class LimitationsBlock(DeliverableBlock):
    kind: Literal["LIMITATIONS"]
    text: BoundaryText = Field(min_length=1, max_length=10_000)
    citations: list[EvidenceCitation] = Field(default_factory=list, max_length=100)


CanonicalDeliverableBlock = Annotated[
    HeadingBlock
    | NarrativeBlock
    | GeneratedMetricBlock
    | GeneratedTableBlock
    | GeneratedChartBlock
    | ScenarioExhibitBlock
    | EvidenceRegisterBlock
    | ModelAppendixBlock
    | LimitationsBlock,
    Field(discriminator="kind"),
]


class DocumentOrigin(StrictModel):
    kind: Literal["ARTIFACT", "MODEL", "ANALYST", "SYSTEM"]
    authority_id: IdentifierItem
    block_ids: list[IdentifierItem] = Field(default_factory=list, max_length=500)


class DocumentSection(StrictModel):
    section_id: IdentifierItem
    title: BoundaryText = Field(min_length=1, max_length=240)
    page: BoundaryText = Field(min_length=1, max_length=120)
    editable: bool
    origin: DocumentOrigin

    @model_validator(mode="after")
    def editable_sections_are_analyst_owned(self) -> DocumentSection:
        if self.editable and self.origin.kind != "ANALYST":
            raise ValueError("editable document sections must be analyst-owned")
        return self


class DocumentTextSection(DocumentSection):
    kind: Literal["text"]
    body: BoundaryText = Field(min_length=1, max_length=20_000)


class DocumentProfileRow(StrictModel):
    label: BoundaryText = Field(min_length=1, max_length=240)
    value: BoundaryText = Field(min_length=1, max_length=20_000)


class DocumentProfileSection(DocumentSection):
    kind: Literal["profile"]
    rows: list[DocumentProfileRow] = Field(min_length=1, max_length=100)


class DocumentTableSection(DocumentSection):
    kind: Literal["table"]
    columns: list[BoundaryText] = Field(min_length=1, max_length=40)
    rows: list[list[BoundaryText]] = Field(max_length=500)
    note: BoundaryText | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def rows_match_columns(self) -> DocumentTableSection:
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("document table rows must match the declared column count")
        return self


class DocumentListSection(DocumentSection):
    kind: Literal["list"]
    items: list[BoundaryText] = Field(min_length=1, max_length=200)


class DocumentChartSection(DocumentSection):
    kind: Literal["chart"]
    recipe: dict[str, Any]
    accessible_columns: list[BoundaryText] = Field(min_length=1, max_length=40)
    accessible_rows: list[list[BoundaryText]] = Field(max_length=500)

    @model_validator(mode="after")
    def accessible_rows_match_columns(self) -> DocumentChartSection:
        if any(len(row) != len(self.accessible_columns) for row in self.accessible_rows):
            raise ValueError("document chart rows must match the accessible column count")
        return self


DocumentLeafSection = Annotated[
    DocumentTextSection
    | DocumentProfileSection
    | DocumentTableSection
    | DocumentListSection
    | DocumentChartSection,
    Field(discriminator="kind"),
]


class DocumentColumnsSection(DocumentSection):
    kind: Literal["columns"]
    items: list[list[DocumentLeafSection]] = Field(min_length=2, max_length=3)

    @model_validator(mode="after")
    def columns_are_not_empty(self) -> DocumentColumnsSection:
        if any(not column for column in self.items):
            raise ValueError("document columns must each contain a section")
        return self


CanonicalDocumentSection = Annotated[
    DocumentLeafSection | DocumentColumnsSection,
    Field(discriminator="kind"),
]


class DeliverableDraftRequest(StrictModel):
    expected_version: int = Field(ge=0)
    template_id: str = Field(min_length=1, max_length=160)
    template_version: str = Field(min_length=1, max_length=160)
    model_selection: DeliverableModelSelection | None = None
    blocks: list[CanonicalDeliverableBlock] = Field(min_length=1, max_length=120)


class FreezeDeliverableRequest(StrictModel):
    draft_id: str = Field(min_length=1, max_length=120)
    draft_version: int = Field(ge=1)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class FileDeliverableRequest(StrictModel):
    preview_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class SignOpinionRequest(StrictModel):
    """Analyst opinion sign-off (Task 10, DECISIONS §14.19): binds the exact
    draft revision; every statement is required and explicit ("None" is written,
    never left blank); the head CAS is the caller's expected current opinion."""

    draft_id: str = Field(min_length=1, max_length=120)
    draft_version: int = Field(ge=1)
    draft_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_head_opinion_id: str | None = Field(default=None, max_length=120)
    opinion: NonBlankBoundaryText = Field(min_length=1, max_length=4000)
    limitations: NonBlankBoundaryText = Field(min_length=1, max_length=4000)
    material_overrides: NonBlankBoundaryText = Field(min_length=1, max_length=4000)
    rationale: NonBlankBoundaryText = Field(min_length=1, max_length=8000)


class RequestDeliverableChangesRequest(FileDeliverableRequest):
    comment: BoundaryText = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def non_blank_comment(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("change-request comment must not be blank")
        return value.strip()


class RVRow(StrictModel):
    instrument: str = Field(min_length=1, max_length=160)
    observation_date: str = Field(min_length=10, max_length=10)
    source_version: str = Field(min_length=1, max_length=120)
    currency: str = Field(min_length=3, max_length=3)
    price: float | None = None
    yield_bps: float | None = None
    spread_bps: float | None = None
    seniority: str = Field(min_length=1, max_length=40)
    maturity: str = Field(min_length=10, max_length=10)
    duration: float | None = None

    @field_validator("price", "yield_bps", "spread_bps", "duration")
    @classmethod
    def finite_number(cls, value: float | None) -> float | None:
        return finite_or_none(value)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class RVUniverseRequest(StrictModel):
    source_version: str = Field(min_length=1, max_length=120)
    rows: list[RVRow] = Field(min_length=1, max_length=500)


class LoanUniverseImportRequest(StrictModel):
    source_id: str = Field(min_length=1, max_length=120)


class FreezeReportRequest(StrictModel):
    thesis_version: int = Field(ge=1)
    recommendation_version: int = Field(ge=1)
    model_build_id: str | None = Field(default=None, min_length=1, max_length=120)
    include_model_export: bool = False
    include_model: Literal[False] = False


class ApproveRequest(StrictModel):
    expected_status: Literal["PENDING_APPROVAL"] = "PENDING_APPROVAL"
    preview_digest: str | None = None
    input_fingerprint: str | None = None
    comment: str = Field(default="", max_length=2000)


class SnapshotSwitchRequest(StrictModel):
    snapshot_id: str = Field(min_length=1, max_length=120)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def clean_json(value: Any) -> Any:
    """Reject non-finite values before they can reach an API or artifact."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite numeric values are not serializable")
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_json(v) for v in value]
    return value


def finite_or_none(value: float | None) -> float | None:
    if value is not None and not math.isfinite(value):
        raise ValueError("non-finite numeric value")
    return value
