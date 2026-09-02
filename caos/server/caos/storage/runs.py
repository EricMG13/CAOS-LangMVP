"""Run-engine store: runs, nodes, artifacts, events, snapshots, budget ledger,
resume tickets, execution counters.

Fresh code — nothing from LEGACY store.py/ledgers is ported. Contracts kept:
state+event commit in one transaction; every event insert rides a conditional
state transition (zero rows updated -> no event), so terminal events are
exactly-once by construction (§12.13); complete_node is validate-then-replace
on the (run_id, module_id, input_fingerprint) unique key (§12.8).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import sqlalchemy as sa

from ..contracts import digest
from ..engine.budget import MAX_ATTEMPT_RECORDS
from ..engine.provider import AgentError, ProviderIdentity
from ..methodology.canonical import (
    MAX_CANONICAL_MARKDOWN_CHARS,
    CanonicalHandoffMetadata,
    canonicalize_for_tests,
    validate_model_sources,
)
from ..methodology.execution import calculation_output_complete
from ..observability import log_event
from .store import cases, new_id, now_iso

run_metadata = sa.MetaData()

runs = sa.Table(
    "runs", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("pathway", sa.String, nullable=False),
    sa.Column("depth", sa.String, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("plan", sa.JSON, nullable=False),
    sa.Column("plan_digest", sa.String),
    sa.Column("error", sa.JSON),
    sa.Column("focus_questions", sa.JSON, nullable=False, default=list),
    sa.Column("accepted_snapshot_id", sa.String),
    sa.Column("upgraded_from_run_id", sa.String),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("schema_version", sa.String, nullable=False),
    sa.Column("provider_identity", sa.JSON),
)

run_nodes = sa.Table(
    "run_nodes", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
    sa.Column("stage", sa.Integer, nullable=False),
    sa.Column("dependencies", sa.JSON, nullable=False),
    sa.Column("status", sa.String, nullable=False),
    sa.Column("attempt", sa.Integer, nullable=False, default=0),
    sa.Column("artifact_id", sa.String),
    sa.Column("error", sa.JSON),
    sa.UniqueConstraint("run_id", "module_id", name="uq_run_nodes_run_module"),
)

run_artifacts = sa.Table(
    "run_artifacts", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
    sa.Column("input_fingerprint", sa.String, nullable=False),
    sa.Column("payload", sa.JSON, nullable=False),
    sa.Column("markdown", sa.Text),
    sa.Column("digest", sa.String, nullable=False),
    sa.Column("qa_status", sa.String),
    sa.Column("created_by", sa.String, nullable=False),
    sa.Column("created_at", sa.String, nullable=False),
    sa.Column("provider_identity", sa.JSON),
    sa.UniqueConstraint("run_id", "module_id", "input_fingerprint", name="uq_artifact_exec_key"),
)

run_events = sa.Table(
    "run_events", run_metadata,
    sa.Column("run_id", sa.String, primary_key=True),
    sa.Column("seq", sa.Integer, primary_key=True),
    sa.Column("event", sa.String, nullable=False),
    sa.Column("at", sa.String, nullable=False),
    sa.Column("data", sa.JSON, nullable=False),
)

run_snapshots = sa.Table(
    "run_snapshots", run_metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("case_id", sa.String, nullable=False),
    sa.Column("run_id", sa.String, nullable=False, unique=True),
    sa.Column("source_set_id", sa.String, nullable=False),
    sa.Column("source_set_version", sa.Integer, nullable=False),
    sa.Column("artifacts", sa.JSON, nullable=False),
    sa.Column("digest", sa.String, nullable=False),
    sa.Column("previous_snapshot_id", sa.String),
    sa.Column("accepted_at", sa.String, nullable=False),
    sa.Column("provider_identity", sa.JSON),
)

run_budgets = sa.Table(
    "run_budgets", run_metadata,
    sa.Column("run_id", sa.String, primary_key=True),
    sa.Column("limits", sa.JSON, nullable=False),
    sa.Column("used", sa.JSON, nullable=False),
    sa.Column("inflight_request_digest", sa.String),
    sa.Column("attempts", sa.JSON, nullable=False),
)

resume_tickets = sa.Table(
    "resume_tickets", run_metadata,
    sa.Column("thread_id", sa.String, primary_key=True),
    sa.Column("interrupt_id", sa.String, primary_key=True),
    sa.Column("consumed", sa.Integer, nullable=False, default=0),
    sa.Column("created_at", sa.String, nullable=False),
)

executions = sa.Table(
    "executions", run_metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("run_id", sa.String, nullable=False),
    sa.Column("module_id", sa.String, nullable=False),
)


class StoreConflict(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


_UNSET = object()
MAX_ARTIFACT_PAYLOAD_BYTES = 8 * 1024 * 1024
_ARTIFACT_SCHEMAS = {"caos.canonical.artifact.v1", "caos.system_analysis.v1"}
_SYSTEM_ARTIFACT_FIELDS = {
    "artifact_identity", "authority", "confidence", "evidence_refs", "lineage",
    "methodology", "module_id", "narrative", "provenance", "provider_identity",
    "schema_version", "status", "summary",
}
_CANONICAL_ARTIFACT_FIELDS = {
    "artifact_identity", "calculation_limitations", "calculations", "canonical_output", "evidence_refs",
    "handoff_metadata", "handoff_metadata_provenance", "host_confidence",
    "host_identity", "lineage", "methodology", "module_id", "provider_identity",
    "schema_version", "source_set", "upstream_artifacts",
}
_CALCULATION_FIELDS = {
    "schema_version", "methodology_build_id", "module_id", "calculator_id",
    "script_digest", "script_bytes", "dependency_digests", "calculator_digest",
    "canonical_input", "input_digest", "output_digest", "canonical_output",
}


def _is_nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_calculation_limitations(limitations: Any, calculator_ids: Any) -> bool:
    """Host-declared incomplete calculators: bounded, unique, assigned, typed."""
    if not isinstance(limitations, list) or not isinstance(calculator_ids, list):
        return False
    seen: set[str] = set()
    for item in limitations:
        if (
            not isinstance(item, dict)
            or set(item) != {"calculator_id", "code"}
            or item.get("code") != "METHODOLOGY_CALCULATION_INCOMPLETE"
            or not _is_nonblank(item.get("calculator_id"))
            or item["calculator_id"] in seen
            or item["calculator_id"] not in calculator_ids
        ):
            return False
        seen.add(item["calculator_id"])
    return True


def _valid_calculation_records(
    records: Any,
    module_id: str,
    build_id: str,
    bindings: Any = _UNSET,
    limited_calculator_ids: frozenset[str] = frozenset(),
) -> bool:
    if not isinstance(records, list):
        return False
    if bindings is not _UNSET:
        if not isinstance(bindings, list) or any(not isinstance(binding, dict) for binding in bindings):
            return False
        binding_by_id = {binding.get("calculator_id"): binding for binding in bindings}
        if None in binding_by_id or len(binding_by_id) != len(bindings):
            return False
    else:
        binding_by_id = None
    calculator_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _CALCULATION_FIELDS:
            return False
        calculator_id = record.get("calculator_id")
        if (
            record.get("schema_version") != "caos.methodology-calculation.v1"
            or record.get("methodology_build_id") != build_id
            or record.get("module_id") != module_id
            or not _is_nonblank(calculator_id)
            or calculator_id in calculator_ids
            or not _is_sha256(record.get("script_digest"))
            or type(record.get("script_bytes")) is not int
            or record["script_bytes"] < 0
            or not isinstance(record.get("dependency_digests"), dict)
            or not all(_is_nonblank(key) and _is_sha256(value)
                       for key, value in record["dependency_digests"].items())
            or not _is_sha256(record.get("calculator_digest"))
            or not isinstance(record.get("canonical_input"), dict)
            or not _is_sha256(record.get("input_digest"))
            or digest(record["canonical_input"]) != record["input_digest"]
            or not _is_sha256(record.get("output_digest"))
            or digest(record.get("canonical_output")) != record["output_digest"]
            or not calculation_output_complete(
                module_id,
                calculator_id,
                record.get("canonical_output"),
            )
        ):
            return False
        if binding_by_id is not None:
            binding = binding_by_id.get(calculator_id)
            if binding is None or any(
                record.get(field) != binding.get(field)
                for field in (
                    "methodology_build_id", "module_id", "calculator_id", "script_digest",
                    "script_bytes", "dependency_digests", "calculator_digest",
                )
            ):
                return False
        calculator_ids.add(calculator_id)
    if calculator_ids & limited_calculator_ids:
        return False
    return binding_by_id is None or calculator_ids | limited_calculator_ids == set(binding_by_id)


def _valid_system_payload(
    payload: dict[str, Any],
    identity: dict[str, Any],
    *,
    source_set: Any = _UNSET,
    upstream_artifacts: Any = _UNSET,
    calculator_bindings: Any = _UNSET,
    expected_payload: Any = _UNSET,
) -> bool:
    optional = set(payload) - _SYSTEM_ARTIFACT_FIELDS
    if not optional <= {"calculations", "inputs"}:
        return False
    lineage = payload.get("lineage")
    narrative = payload.get("narrative")
    provenance = payload.get("provenance")
    evidence_refs = payload.get("evidence_refs")
    unbound_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"artifact_identity", "calculations", "methodology", "provider_identity"}
    }
    if (
        not isinstance(expected_payload, dict)
        or unbound_payload != expected_payload
        or not _SYSTEM_ARTIFACT_FIELDS <= set(payload)
        or payload.get("status") != "COMPLETE"
        or not _is_nonblank(payload.get("summary"))
        or payload.get("authority") != "SYSTEM_ANALYSIS"
        or payload.get("confidence") != {"band": "SYSTEM", "qa_status": "Passed"}
        or not isinstance(evidence_refs, list)
        or any(not _is_nonblank(reference) for reference in evidence_refs)
        or len(set(evidence_refs)) != len(evidence_refs)
        or not isinstance(lineage, dict)
        or set(lineage) not in ({"input_fingerprint", "upstream_digests"},
                                {"input_fingerprint", "upstream_digests", "loan_universe"})
        or lineage.get("input_fingerprint") != identity["input_fingerprint"]
        or not isinstance(lineage.get("upstream_digests"), list)
        or any(not _is_sha256(value) for value in lineage["upstream_digests"])
        or not isinstance(narrative, dict)
        or set(narrative) != {"takeaway", "basis", "exceptions"}
        or not _is_nonblank(narrative.get("takeaway"))
        or not _is_nonblank(narrative.get("basis"))
        or not isinstance(narrative.get("exceptions"), str)
        or not isinstance(provenance, dict)
        or set(provenance) not in ({"executor", "profile_id", "selection_id"},
                                   {"executor", "profile_id", "selection_id", "loan_universe"})
        or provenance.get("executor") != "caos.engine.deterministic"
        or any(value is not None and not _is_nonblank(value)
               for value in (provenance.get("profile_id"), provenance.get("selection_id")))
    ):
        return False
    loan_identity = lineage.get("loan_universe")
    if loan_identity is None:
        if "inputs" in payload or "loan_universe" in provenance:
            return False
    elif (
        identity["module_id"] != "CP-3"
        or not isinstance(loan_identity, dict)
        or set(loan_identity) != {"id", "universe_digest", "source_id"}
        or not _is_nonblank(loan_identity.get("id"))
        or not _is_sha256(loan_identity.get("universe_digest"))
        or not _is_nonblank(loan_identity.get("source_id"))
        or provenance.get("loan_universe") != loan_identity
        or not isinstance(payload.get("inputs"), dict)
        or set(payload["inputs"]) != {"loan_universe"}
        or not isinstance(payload["inputs"]["loan_universe"], dict)
        or payload["inputs"]["loan_universe"].get("identity") != loan_identity
        or not isinstance(payload["inputs"]["loan_universe"].get("rows"), list)
    ):
        return False
    if source_set is not _UNSET and (
        not isinstance(source_set, dict)
        or evidence_refs != source_set.get("source_ids")
    ):
        return False
    if upstream_artifacts is not _UNSET and (
        not isinstance(upstream_artifacts, list)
        or lineage["upstream_digests"] != [artifact.get("digest") for artifact in upstream_artifacts]
    ):
        return False
    records = payload.get("calculations", [])
    return _valid_calculation_records(
        records,
        identity["module_id"],
        identity["methodology_build_id"],
        calculator_bindings,
    )


def _valid_canonical_payload(
    payload: dict[str, Any],
    identity: dict[str, Any],
    markdown: str,
    *,
    expected_source_set: Any,
    upstream_artifacts: Any,
    handoff_artifacts: Any,
    calculator_bindings: Any,
    expected_host_identity: Any,
    evidence_blocks: Any,
    downstream_consumers: Any,
) -> bool:
    if (
        set(payload) != _CANONICAL_ARTIFACT_FIELDS
        or expected_source_set is _UNSET
        or upstream_artifacts is _UNSET
        or handoff_artifacts is _UNSET
        or calculator_bindings is _UNSET
        or not isinstance(expected_source_set, dict)
        or not isinstance(upstream_artifacts, list)
        or not isinstance(handoff_artifacts, list)
        or not isinstance(expected_host_identity, dict)
        or not isinstance(evidence_blocks, set)
        or not isinstance(downstream_consumers, list)
    ):
        return False
    host_identity = payload.get("host_identity")
    payload_source_set = payload.get("source_set")
    lineage = payload.get("lineage")
    confidence = payload.get("host_confidence")
    provenance = payload.get("handoff_metadata_provenance")
    evidence_refs = payload.get("evidence_refs")
    upstream = payload.get("upstream_artifacts")
    try:
        handoff = CanonicalHandoffMetadata.model_validate(payload.get("handoff_metadata"))
    except ValueError:
        return False
    if (
        not isinstance(host_identity, dict)
        or set(host_identity) != {
            "module_id", "module_name", "run_id", "case_id", "issuer_name", "issuer_id",
            "reporting_period", "analysis_date", "profile_id", "selection_id", "source_set_id",
            "source_set_version", "calculator_ids", "upstream_digests",
        }
        or host_identity.get("run_id") != identity["run_id"]
        or host_identity.get("case_id") != identity["case_id"]
        or host_identity.get("module_id") != identity["module_id"]
        or handoff.module_id != identity["module_id"]
        or handoff.run_id != identity["run_id"]
        or handoff.module_name != host_identity.get("module_name")
        or handoff.reporting_period != host_identity.get("reporting_period")
        or handoff.analysis_date != host_identity.get("analysis_date")
        or handoff.issuer_name != host_identity.get("issuer_name")
        or handoff.issuer_id != host_identity.get("issuer_id")
        or host_identity != expected_host_identity
        or handoff.downstream_consumers != downstream_consumers
        or handoff.qa_status != "Passed"
        or not isinstance(evidence_refs, list)
        or any(not isinstance(reference, dict) or set(reference) != {"source_id", "block_id"}
               or not _is_nonblank(reference.get("source_id"))
               or not _is_nonblank(reference.get("block_id")) for reference in evidence_refs)
        or len({(reference["source_id"], reference["block_id"]) for reference in evidence_refs})
        != len(evidence_refs)
        or not isinstance(lineage, dict)
        or set(lineage) != {"input_fingerprint", "upstream_digests"}
        or lineage.get("input_fingerprint") != identity["input_fingerprint"]
        or not isinstance(lineage.get("upstream_digests"), list)
        or any(not _is_sha256(value) for value in lineage["upstream_digests"])
        or not isinstance(payload_source_set, dict)
        or set(payload_source_set) != {"id", "version", "digest"}
        or payload_source_set != {
            "id": host_identity.get("source_set_id"),
            "version": host_identity.get("source_set_version"),
            "digest": payload_source_set.get("digest"),
        }
        or not _is_sha256(payload_source_set.get("digest"))
        or not isinstance(upstream, list)
        or any(not isinstance(item, dict) or set(item) != {"module_id", "artifact_id", "digest"}
               or not _is_nonblank(item.get("module_id"))
               or not _is_nonblank(item.get("artifact_id"))
               or not _is_sha256(item.get("digest")) for item in upstream)
        or [item["digest"] for item in upstream] != lineage["upstream_digests"]
        or host_identity.get("upstream_digests") != lineage["upstream_digests"]
        or not isinstance(host_identity.get("calculator_ids"), list)
        or any(not _is_nonblank(value) for value in host_identity["calculator_ids"])
        or not isinstance(confidence, dict)
        or set(confidence) != {
            "confidence_score", "confidence_band", "qa_status", "basis", "arithmetic",
            "analyst_review_required",
        }
        or confidence.get("confidence_score") != handoff.confidence_score
        or str(confidence.get("confidence_band", "")).title() != handoff.confidence_band
        or confidence.get("qa_status") != "Passed"
        or confidence.get("basis") != "provider_declared_bounded_counts"
        or confidence.get("arithmetic") != "host_recomputed"
        or confidence.get("analyst_review_required") is not True
        or provenance != {
            "host_derived_fields": [
                "module_id", "module_name", "run_id", "analysis_date", "confidence_score",
                "confidence_band", "qa_status", "committee_status", "upstream_artifacts_used",
                "downstream_consumers", "issuer_name", "issuer_id",
                "calculation_limitations",
            ],
            "provider_declared_bounded_fields": ["limitation_flags", "validation_warnings"],
            "reporting_period_basis": "host_pinned_run_date",
        }
        or not _valid_calculation_limitations(
            payload.get("calculation_limitations"), host_identity.get("calculator_ids"),
        )
        or not _valid_calculation_records(
            payload.get("calculations"), identity["module_id"], identity["methodology_build_id"],
            calculator_bindings,
            frozenset(item["calculator_id"] for item in payload["calculation_limitations"]),
        )
        or set(host_identity["calculator_ids"])
        != {record["calculator_id"] for record in payload["calculations"]}
        | {item["calculator_id"] for item in payload["calculation_limitations"]}
        or any(
            f"host:calculation_incomplete:{item['calculator_id']}" not in handoff.limitation_flags
            for item in payload["calculation_limitations"]
        )
    ):
        return False
    expected_source_projection = {
        "id": expected_source_set.get("id"),
        "version": expected_source_set.get("version"),
        "digest": expected_source_set.get("digest"),
    }
    expected_upstream = [{
        "module_id": artifact.get("module_id"),
        "artifact_id": artifact.get("id"),
        "digest": artifact.get("digest"),
    } for artifact in upstream_artifacts]
    expected_handoff = [{
        "module_id": artifact.get("module_id"),
        "run_id": artifact.get("run_id"),
        "period": (
            (artifact.get("payload") or {}).get("handoff_metadata") or {}
        ).get("reporting_period", expected_host_identity["reporting_period"]),
        "artifact_digest": artifact.get("digest"),
    } for artifact in handoff_artifacts]
    actual_handoff = [{
        "module_id": artifact.module_id,
        "run_id": artifact.run_id,
        "period": artifact.period,
        "artifact_digest": artifact.artifact_digest,
    } for artifact in handoff.upstream_artifacts_used]
    delivered = {(reference["source_id"], reference["block_id"]) for reference in evidence_refs}
    if (
        payload_source_set != expected_source_projection
        or payload["upstream_artifacts"] != expected_upstream
        or actual_handoff != expected_handoff
        or not delivered <= evidence_blocks
    ):
        return False
    validate_model_sources(
        markdown,
        {source_id for source_id, _block_id in delivered},
        module_id=identity["module_id"],
    )
    rebuilt = canonicalize_for_tests(
        module_id=identity["module_id"],
        provider_markdown=markdown,
        run_identity=host_identity,
        delivered=delivered,
        build_id=identity["methodology_build_id"],
        handoff_metadata=handoff.model_dump(),
    )
    return all(payload.get(key) == rebuilt[key] for key in (
        "schema_version", "module_id", "canonical_output", "methodology", "host_identity",
        "handoff_metadata", "evidence_refs",
    ))


def _artifact_payload_bytes(payload: dict[str, Any]) -> bytes:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_ARTIFACT_PAYLOAD_BYTES:
        raise ValueError("artifact payload exceeds its size bound")
    return encoded


def _bind_artifact_payload(
    payload: dict[str, Any],
    *,
    run_id: str,
    case_id: str,
    module_id: str,
    input_fingerprint: str,
    qa_status: str | None,
    methodology_build_id: str,
    provider_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **payload,
        "methodology": {"build_id": methodology_build_id},
        "provider_identity": provider_identity,
        "artifact_identity": {
            "run_id": run_id,
            "case_id": case_id,
            "module_id": module_id,
            "input_fingerprint": input_fingerprint,
            "qa_status": qa_status,
            "methodology_build_id": methodology_build_id,
        },
    }


def artifact_input_fingerprint(
    plan: dict[str, Any],
    plan_digest: str,
    module_id: str,
    upstream_digests: list[str],
) -> str:
    return digest({
        "plan_digest": plan_digest,
        "module_id": module_id,
        "upstream_artifact_digests": upstream_digests,
        "source_set_digest": plan.get("source_set_digest"),
        "provider_identity_digest": (plan.get("provider_identity") or {}).get("identity_digest"),
    })


def verify_artifact_content(
    artifact: dict[str, Any],
    *,
    run_id: str | None = None,
    case_id: str | None = None,
    module_id: str | None = None,
    input_fingerprint: str | None = None,
    methodology_build_id: str | None = None,
    qa_status: Any = _UNSET,
    provider_identity: Any = _UNSET,
    source_set: Any = _UNSET,
    upstream_artifacts: Any = _UNSET,
    handoff_artifacts: Any = _UNSET,
    calculator_bindings: Any = _UNSET,
    expected_system_payload: Any = _UNSET,
    expected_host_identity: Any = _UNSET,
    evidence_blocks: Any = _UNSET,
    downstream_consumers: Any = _UNSET,
) -> bool:
    """Verify payload bytes and every separately indexed artifact authority."""
    try:
        if not isinstance(artifact, dict):
            return False
        if artifact.get("qa_status") != "Passed":
            return False
        payload = artifact.get("payload")
        if not isinstance(payload, dict) or payload.get("schema_version") not in _ARTIFACT_SCHEMAS:
            return False
        encoded = _artifact_payload_bytes(payload)
        if hashlib.sha256(encoded).hexdigest() != artifact.get("digest"):
            return False
        if run_id is not None and artifact.get("run_id") != run_id:
            return False
        if case_id is not None and artifact.get("case_id") != case_id:
            return False
        if module_id is not None and artifact.get("module_id") != module_id:
            return False
        if input_fingerprint is not None and artifact.get("input_fingerprint") != input_fingerprint:
            return False
        if qa_status is not _UNSET and artifact.get("qa_status") != qa_status:
            return False
        if payload.get("provider_identity") != artifact.get("provider_identity"):
            return False
        if provider_identity is not _UNSET and artifact.get("provider_identity") != provider_identity:
            return False
        identity = payload.get("artifact_identity")
        if (
            not isinstance(identity, dict)
            or not isinstance(identity.get("methodology_build_id"), str)
            or not identity["methodology_build_id"]
        ):
            return False
        expected_identity = {
            "run_id": artifact.get("run_id"),
            "case_id": artifact.get("case_id"),
            "module_id": artifact.get("module_id"),
            "input_fingerprint": artifact.get("input_fingerprint"),
            "qa_status": artifact.get("qa_status"),
            "methodology_build_id": methodology_build_id or identity["methodology_build_id"],
        }
        if identity != expected_identity:
            return False
        if payload.get("module_id") != identity["module_id"]:
            return False
        if payload.get("methodology") != {"build_id": identity["methodology_build_id"]}:
            return False
        lineage = payload.get("lineage")
        if not isinstance(lineage, dict) or lineage.get("input_fingerprint") != identity["input_fingerprint"]:
            return False
        canonical = payload.get("canonical_output")
        if payload["schema_version"] == "caos.system_analysis.v1":
            return (
                canonical is None
                and artifact.get("markdown") is None
                and _valid_system_payload(
                    payload,
                    identity,
                    source_set=source_set,
                    upstream_artifacts=upstream_artifacts,
                    calculator_bindings=calculator_bindings,
                    expected_payload=expected_system_payload,
                )
            )
        if not isinstance(canonical, dict):
            return False
        markdown = canonical.get("markdown")
        return (
            isinstance(markdown, str)
            and len(markdown) <= MAX_CANONICAL_MARKDOWN_CHARS
            and artifact.get("markdown") == markdown
            and canonical.get("markdown_sha256")
            == hashlib.sha256(markdown.encode("utf-8")).hexdigest()
            and _valid_canonical_payload(
                payload,
                identity,
                markdown,
                expected_source_set=source_set,
                upstream_artifacts=upstream_artifacts,
                handoff_artifacts=handoff_artifacts,
                calculator_bindings=calculator_bindings,
                expected_host_identity=expected_host_identity,
                evidence_blocks=evidence_blocks,
                downstream_consumers=downstream_consumers,
            )
        )
    except (AttributeError, OverflowError, RecursionError, TypeError, UnicodeError, ValueError):
        return False


TERMINAL = {"succeeded", "failed"}
_IDENTITY_TABLES = ("runs", "run_artifacts", "run_snapshots")


def _provider_identity(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        identity = value if isinstance(value, ProviderIdentity) else ProviderIdentity.from_dict(value)
        identity.verify()
    except (AgentError, TypeError, ValueError) as exc:
        raise StoreConflict("AGENT_IDENTITY_MISMATCH", "provider identity is invalid") from exc
    return identity.as_dict()


class RunStore:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine
        run_metadata.create_all(engine)
        self._ensure_provider_identity_columns()

    def _ensure_provider_identity_columns(self) -> None:
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                for table in _IDENTITY_TABLES:
                    conn.exec_driver_sql(
                        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS provider_identity JSON'
                    )
            return
        if self.engine.dialect.name != "sqlite":
            raise RuntimeError(f"unsupported run-store dialect: {self.engine.dialect.name}")
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                for table in _IDENTITY_TABLES:
                    columns = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table}")')}
                    if "provider_identity" not in columns:
                        conn.exec_driver_sql(
                            f'ALTER TABLE "{table}" ADD COLUMN provider_identity JSON'
                        )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    # -- events (always inside a caller transaction) ----------------------

    def _emit(self, conn: sa.Connection, run_id: str, event: str, **data: Any) -> None:
        try:
            identity = _provider_identity(conn.execute(
                sa.select(runs.c.provider_identity).where(runs.c.id == run_id)
            ).scalar())
        except StoreConflict:
            # An invalid identity must not roll back the terminal transition
            # whose purpose is to quarantine that exact invalid identity.
            if event != "run.failed" or data.get("code") != "AGENT_IDENTITY_MISMATCH":
                raise
            identity = None
        if identity is not None:
            data = {**data, "provider_identity_digest": identity["identity_digest"]}
        next_seq = conn.execute(
            sa.select(sa.func.coalesce(sa.func.max(run_events.c.seq), 0) + 1).where(run_events.c.run_id == run_id)
        ).scalar_one()
        conn.execute(run_events.insert().values(run_id=run_id, seq=next_seq, event=event, at=now_iso(), data=data))
        # Every durable run/node transition passes through here and nowhere
        # else, so one line here is the whole "which run is stuck" answer.
        # `data` is host-owned identifiers only — never anything a document
        # produced. Merged as a dict rather than **kwargs so a future event
        # carrying its own `run_id` cannot raise TypeError and take the state
        # transition down with it: logging never breaks a run. It does ride
        # inside the caller's transaction, so a failing commit leaves one line
        # describing a transition that rolled back — the run dies in the same
        # breath, and the single seam is worth that much drift.
        log_event(event, **{**data, "run_id": run_id, "seq": next_seq})

    def events_after(self, run_id: str, after_seq: int) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(run_events).where(run_events.c.run_id == run_id, run_events.c.seq > after_seq).order_by(run_events.c.seq)
            ).mappings().all()
        return [{"id": r["seq"], "event": r["event"], "at": r["at"], "data": r["data"]} for r in rows]

    # -- runs ---------------------------------------------------------------

    def create_run(self, case_id: str, pathway: str, depth: str, actor: str, *,
                   focus_questions: list[str] | None = None,
                   upgraded_from_run_id: str | None = None,
                   provider_identity: ProviderIdentity | dict[str, Any] | None = None,
                   schema_version: str = "caos-state-v1") -> dict[str, Any]:
        run_id = new_id("run")
        identity = _provider_identity(provider_identity)
        with self.engine.begin() as conn:
            conn.execute(runs.insert().values(
                id=run_id, case_id=case_id, pathway=pathway, depth=depth, status="queued",
                plan={}, plan_digest=None, error=None, focus_questions=list(focus_questions or []),
                accepted_snapshot_id=None, upgraded_from_run_id=upgraded_from_run_id,
                created_by=actor, created_at=now_iso(), schema_version=schema_version,
                provider_identity=identity,
            ))
            self._emit(conn, run_id, "run.created", case_id=case_id, pathway=pathway, depth=depth)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(runs).where(runs.c.id == run_id)).mappings().first()
            if row is None:
                return None
            node_rows = conn.execute(
                sa.select(run_nodes).where(run_nodes.c.run_id == run_id).order_by(run_nodes.c.stage, run_nodes.c.module_id)
            ).mappings().all()
        record = dict(row)
        record["nodes"] = [dict(node) for node in node_rows]
        record["node_ids"] = [node["id"] for node in node_rows]
        return record

    def non_terminal_runs(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.select(runs).where(runs.c.status.notin_(TERMINAL))).mappings().all()
        return [dict(row) for row in rows]

    def active_admission_count(self) -> int:
        """§12: derived, never stored. Interrupt-paused threads hold no slot."""
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(sa.func.count()).where(runs.c.status.in_(("queued", "running")))
            ).scalar_one()

    def pause_run(self, run_id: str, code: str) -> str:
        """Pause at the entry gate; writes the one-shot resume ticket (§12.21).
        A re-pause supersedes any stale unconsumed ticket (no stranded ticket
        population) and emits run.paused only on a real status transition."""
        with self.engine.begin() as conn:
            previous = conn.execute(sa.select(runs.c.status).where(runs.c.id == run_id)).scalar()
            if previous in TERMINAL or previous is None:
                raise StoreConflict("RESUME_NOT_APPLIED", "run is terminal")
            conn.execute(sa.update(runs).where(runs.c.id == run_id).values(status="paused", error={"code": code}))
            conn.execute(
                sa.update(resume_tickets)
                .where(resume_tickets.c.thread_id == run_id, resume_tickets.c.consumed == 0)
                .values(consumed=1)
            )
            ticket = f"int-{new_id('t')[2:]}"
            conn.execute(resume_tickets.insert().values(
                thread_id=run_id, interrupt_id=ticket, consumed=0, created_at=now_iso(),
            ))
            if previous != "paused":
                self._emit(conn, run_id, "run.paused", code=code, interrupt_id=ticket)
            return ticket

    def latest_ticket(self, run_id: str) -> str | None:
        with self.engine.connect() as conn:
            return conn.execute(
                sa.select(resume_tickets.c.interrupt_id)
                .where(resume_tickets.c.thread_id == run_id, resume_tickets.c.consumed == 0)
                .order_by(resume_tickets.c.created_at.desc())
                .limit(1)
            ).scalar()

    def consume_ticket(self, run_id: str, interrupt_id: str) -> bool:
        with self.engine.begin() as conn:
            return bool(conn.execute(
                sa.update(resume_tickets)
                .where(
                    resume_tickets.c.thread_id == run_id,
                    resume_tickets.c.interrupt_id == interrupt_id,
                    resume_tickets.c.consumed == 0,
                )
                .values(consumed=1)
            ).rowcount)

    def pin_plan(self, run_id: str, plan: dict[str, Any], plan_digest: str) -> None:
        """Gate-exit pin: written exactly once (CAS on unpinned), node rows
        created, run leaves paused/queued for running."""
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs)
                .where(runs.c.id == run_id, runs.c.plan_digest.is_(None), runs.c.status.notin_(TERMINAL))
                .values(plan=plan, plan_digest=plan_digest, status="running", error=None)
            ).rowcount
            if not changed:
                # Re-executed gate after crash: pin already written; just leave paused state.
                conn.execute(
                    sa.update(runs)
                    .where(runs.c.id == run_id, runs.c.status == "paused", runs.c.plan_digest.isnot(None))
                    .values(status="running", error=None)
                )
                return
            case_id = conn.execute(sa.select(runs.c.case_id).where(runs.c.id == run_id)).scalar_one()
            for node in plan["nodes"]:
                conn.execute(run_nodes.insert().values(
                    id=new_id("node"), run_id=run_id, case_id=case_id, module_id=node["module_id"],
                    stage=node["stage"], dependencies=node["dependencies"], status="pending",
                    attempt=0, artifact_id=None, error=None,
                ))
            self._emit(conn, run_id, "run.running")

    def node_running(self, run_id: str, module_id: str) -> None:
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(run_nodes)
                .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id,
                       run_nodes.c.status.in_(("pending", "ready")))
                .values(status="running", attempt=run_nodes.c.attempt + 1)
            ).rowcount
            if changed:
                self._emit(conn, run_id, "node.running", module_id=module_id)

    def find_valid_artifact(
        self,
        run_id: str,
        module_id: str,
        input_fingerprint: str,
        *,
        content_expectations: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            authority = conn.execute(
                sa.select(
                    runs.c.case_id, runs.c.provider_identity, runs.c.plan, runs.c.plan_digest,
                ).where(runs.c.id == run_id)
            ).mappings().first()
            row = conn.execute(
                sa.select(run_artifacts).where(
                    run_artifacts.c.run_id == run_id,
                    run_artifacts.c.module_id == module_id,
                    run_artifacts.c.input_fingerprint == input_fingerprint,
                )
            ).mappings().first()
            authoritative_fingerprint = self._authoritative_input_fingerprint(
                conn,
                run_id,
                authority.get("plan") or {} if authority is not None else {},
                authority.get("plan_digest") if authority is not None else None,
                module_id,
            )
        if row is None or authority is None:
            return None
        plan = authority.get("plan") or {}
        methodology_build_id = plan.get("build_id")
        if (
            digest(plan) != authority.get("plan_digest")
            or not isinstance(methodology_build_id, str)
            or not methodology_build_id
            or authoritative_fingerprint != input_fingerprint
        ):
            return None
        artifact = dict(row)
        if not verify_artifact_content(
            artifact,
            run_id=run_id,
            case_id=authority["case_id"],
            module_id=module_id,
            input_fingerprint=input_fingerprint,
            methodology_build_id=methodology_build_id,
            provider_identity=_provider_identity(authority["provider_identity"]),
            **(content_expectations or {}),
        ):
            return None
        return artifact

    def complete_node(
        self,
        run_id: str,
        case_id: str,
        module_id: str,
        input_fingerprint: str,
        payload: dict[str, Any],
        markdown: str | None,
        qa_status: str | None,
        actor: str,
        *,
        content_expectations: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """§12.8 validate-then-replace, one transaction: artifact link/relink,
        node completion, execution marker, node.succeeded event (conditional)."""
        with self.engine.begin() as conn:
            authority = conn.execute(
                sa.select(
                    runs.c.case_id, runs.c.provider_identity, runs.c.plan, runs.c.plan_digest,
                ).where(runs.c.id == run_id)
            ).mappings().one()
            identity = _provider_identity(authority["provider_identity"])
            plan = authority.get("plan") or {}
            methodology_build_id = plan.get("build_id")
            if (
                digest(plan) != authority.get("plan_digest")
                or not isinstance(methodology_build_id, str)
                or not methodology_build_id
            ):
                raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "run methodology identity is unavailable")
            if authority["case_id"] != case_id:
                raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "artifact case differs from run")
            if qa_status != "Passed":
                raise StoreConflict("AGENT_OUTPUT_INVALID", "artifact QA must be Passed")
            node = conn.execute(
                sa.select(run_nodes.c.case_id, run_nodes.c.status).where(
                    run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id,
                )
            ).mappings().first()
            if (
                node is None
                or node["case_id"] != case_id
                or not any(
                    isinstance(plan_node, dict) and plan_node.get("module_id") == module_id
                    for plan_node in plan.get("nodes") or []
                )
            ):
                raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "artifact module differs from the run plan")
            authoritative_fingerprint = self._authoritative_input_fingerprint(
                conn,
                run_id,
                plan,
                authority["plan_digest"],
                module_id,
            )
            if authoritative_fingerprint != input_fingerprint:
                raise StoreConflict(
                    "AGENT_AUTHORITY_MISMATCH",
                    "artifact input fingerprint differs from the run graph",
                )
            if not isinstance(payload, dict):
                raise StoreConflict("AGENT_OUTPUT_INVALID", "artifact payload must be an object")
            existing = conn.execute(
                sa.select(run_artifacts).where(
                    run_artifacts.c.run_id == run_id,
                    run_artifacts.c.module_id == module_id,
                    run_artifacts.c.input_fingerprint == input_fingerprint,
                )
            ).mappings().first()
            if (
                existing is not None
                and _provider_identity(existing["provider_identity"]) != identity
            ):
                raise StoreConflict("AGENT_IDENTITY_MISMATCH", "artifact identity differs from run")
            if existing is not None and verify_artifact_content(
                dict(existing),
                run_id=run_id,
                case_id=case_id,
                module_id=module_id,
                input_fingerprint=input_fingerprint,
                methodology_build_id=methodology_build_id,
                qa_status=qa_status,
                provider_identity=identity,
                **(content_expectations or {}),
            ):
                artifact = dict(existing)  # relink: discard candidate, keep stored ids
            else:
                if existing is not None:
                    conn.execute(sa.delete(run_artifacts).where(run_artifacts.c.id == existing["id"]))
                bound_payload = _bind_artifact_payload(
                    payload,
                    run_id=run_id,
                    case_id=case_id,
                    module_id=module_id,
                    input_fingerprint=input_fingerprint,
                    qa_status=qa_status,
                    methodology_build_id=methodology_build_id,
                    provider_identity=identity,
                )
                try:
                    payload_digest = hashlib.sha256(_artifact_payload_bytes(bound_payload)).hexdigest()
                except (OverflowError, RecursionError, TypeError, UnicodeError, ValueError) as exc:
                    raise StoreConflict("AGENT_OUTPUT_INVALID", "artifact payload is not bounded JSON") from exc
                artifact = {
                    "id": new_id("art"), "run_id": run_id, "case_id": case_id, "module_id": module_id,
                    "input_fingerprint": input_fingerprint, "payload": bound_payload, "markdown": markdown,
                    "digest": payload_digest, "qa_status": qa_status,
                    "created_by": actor, "created_at": now_iso(),
                    "provider_identity": identity,
                }
                if not verify_artifact_content(
                    artifact,
                    run_id=run_id,
                    case_id=case_id,
                    module_id=module_id,
                    input_fingerprint=input_fingerprint,
                    methodology_build_id=methodology_build_id,
                    qa_status=qa_status,
                    provider_identity=identity,
                    **(content_expectations or {}),
                ):
                    raise StoreConflict("AGENT_OUTPUT_INVALID", "payload and Markdown differ")
                conn.execute(run_artifacts.insert().values(**artifact))
                conn.execute(executions.insert().values(run_id=run_id, module_id=module_id))
            # The node always follows the artifact it was completed with: a
            # replaced row relinks a node that already succeeded, while the
            # node.succeeded event stays exactly-once on the status transition.
            conn.execute(
                sa.update(run_nodes)
                .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id)
                .values(status="succeeded", artifact_id=artifact["id"], error=None)
            )
            if node["status"] != "succeeded":
                self._emit(conn, run_id, "node.succeeded", module_id=module_id, artifact_id=artifact["id"])
            return artifact

    @staticmethod
    def _authoritative_input_fingerprint(
        conn: sa.Connection,
        run_id: str,
        plan: dict[str, Any],
        plan_digest: str | None,
        module_id: str,
    ) -> str | None:
        plan_node = next(
            (node for node in plan.get("nodes") or []
             if isinstance(node, dict) and node.get("module_id") == module_id),
            None,
        )
        dependencies = plan_node.get("dependencies") if plan_node is not None else None
        if not isinstance(plan_digest, str) or not isinstance(dependencies, list):
            return None
        upstream_digests: list[str] = []
        for dependency in dependencies:
            row = conn.execute(
                sa.select(run_nodes.c.artifact_id, run_artifacts.c.digest)
                .select_from(run_nodes.outerjoin(
                    run_artifacts,
                    run_artifacts.c.id == run_nodes.c.artifact_id,
                ))
                .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == dependency)
            ).mappings().first()
            if row is None or not isinstance(row["artifact_id"], str) or not _is_sha256(row["digest"]):
                return None
            upstream_digests.append(row["digest"])
        return artifact_input_fingerprint(plan, plan_digest, module_id, upstream_digests)

    def finalize_success(self, run_id: str) -> bool:
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs).where(runs.c.id == run_id, runs.c.status == "running").values(status="succeeded", error=None)
            ).rowcount
            if changed:
                self._emit(conn, run_id, "run.succeeded")
            return bool(changed)

    def finalize_failure(self, run_id: str, code: str, module_id: str | None) -> bool:
        error = {"code": code}
        if module_id:
            error["module_id"] = module_id
        with self.engine.begin() as conn:
            changed = conn.execute(
                sa.update(runs).where(runs.c.id == run_id, runs.c.status.notin_(TERMINAL)).values(status="failed", error=error)
            ).rowcount
            if changed:
                if module_id:
                    conn.execute(
                        sa.update(run_nodes)
                        .where(run_nodes.c.run_id == run_id, run_nodes.c.module_id == module_id)
                        .values(status="failed", error=error)
                    )
                # Siblings of the blamed module were mid-superstep; the run is over, so
                # their work is abandoned, not failed (the error belongs to one module).
                # ponytail: only `running` lies on a terminal record — `pending` stays
                # true forever, and recover() never revisits a terminal run.
                conn.execute(
                    sa.update(run_nodes)
                    .where(run_nodes.c.run_id == run_id, run_nodes.c.status == "running")
                    .values(status="cancelled")
                )
                conn.execute(
                    sa.update(resume_tickets)
                    .where(resume_tickets.c.thread_id == run_id, resume_tickets.c.consumed == 0)
                    .values(consumed=1)
                )
                self._emit(conn, run_id, "run.failed", **error)
            return bool(changed)

    # -- artifacts ---------------------------------------------------------

    def artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(run_artifacts).where(run_artifacts.c.run_id == run_id).order_by(run_artifacts.c.created_at)
            ).mappings().all()
        return [dict(row) for row in rows]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_artifacts).where(run_artifacts.c.id == artifact_id)).mappings().first()
        return dict(row) if row else None

    def update_artifact_for_tests(self, run_id: str, module_id: str, **values: Any) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                sa.update(run_artifacts)
                .where(run_artifacts.c.run_id == run_id, run_artifacts.c.module_id == module_id)
                .values(**values)
            )

    # -- execution counters (test observability) ---------------------------

    def executed_modules(self, run_id: str) -> list[str]:
        with self.engine.connect() as conn:
            return list(conn.execute(
                sa.select(executions.c.module_id).where(executions.c.run_id == run_id).order_by(executions.c.seq)
            ).scalars().all())

    def execution_counts(self, run_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for module_id in self.executed_modules(run_id):
            counts[module_id] = counts.get(module_id, 0) + 1
        return counts

    # -- budget ledger ------------------------------------------------------

    def init_budget(self, run_id: str, limits: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(sa.select(run_budgets.c.run_id).where(run_budgets.c.run_id == run_id)).first()
            if existing is None:
                conn.execute(run_budgets.insert().values(
                    run_id=run_id, limits=limits, used={key: 0 for key in limits},
                    inflight_request_digest=None, attempts=[],
                ))

    def get_budget(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_budgets).where(run_budgets.c.run_id == run_id)).mappings().first()
        return dict(row) if row else None

    def _budget_locked(self, conn: sa.Connection, run_id: str) -> dict[str, Any]:
        row = conn.execute(sa.select(run_budgets).where(run_budgets.c.run_id == run_id)).mappings().first()
        if row is None:
            raise StoreConflict("AGENT_BUDGET_EXCEEDED", "budget ledger missing")
        return dict(row)

    def reserve_provider(self, run_id: str, request_digest: str, input_tokens: int, output_tokens: int, retry: bool) -> None:
        """§12.12: reserve persists the inflight digest before create; a retry
        requires inflight == digest and is budget-free."""
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            used, limits = dict(budget["used"]), budget["limits"]
            inflight = budget["inflight_request_digest"]
            if retry:
                if inflight != request_digest:
                    raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "provider retry request changed")
                log_event("budget.reserved", run_id=run_id, request_digest=request_digest,
                          retry=True, used=used)
                return
            if inflight:
                raise StoreConflict("AGENT_BUDGET_EXCEEDED", "unresolved in-flight request")
            for key, amount in (("turns", 1), ("input_tokens", input_tokens), ("output_tokens", output_tokens)):
                if used.get(key, 0) + amount > limits.get(key, 0):
                    raise StoreConflict("AGENT_BUDGET_EXCEEDED", f"{key} budget exhausted")
            for key, amount in (("turns", 1), ("input_tokens", input_tokens), ("output_tokens", output_tokens)):
                used[key] = used.get(key, 0) + amount
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(
                used=used, inflight_request_digest=request_digest,
            ))
            log_event("budget.reserved", run_id=run_id, request_digest=request_digest, retry=False,
                      input_tokens=input_tokens, output_tokens=output_tokens, used=used)

    def reconcile_provider(self, run_id: str, request_digest: str, reserved_input: int, reserved_output: int,
                           actual_input: int, actual_output: int) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            if budget["inflight_request_digest"] != request_digest:
                raise StoreConflict("AGENT_AUTHORITY_MISMATCH", "in-flight request digest mismatch")
            used, limits = dict(budget["used"]), budget["limits"]
            used["input_tokens"] = used.get("input_tokens", 0) + actual_input - reserved_input
            used["output_tokens"] = used.get("output_tokens", 0) + actual_output - reserved_output
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(
                used=used, inflight_request_digest=None,
            ))
        # `used` after the true-up is the whole "what has it spent" answer.
        log_event("budget.reconciled", run_id=run_id, request_digest=request_digest,
                  input_tokens=actual_input, output_tokens=actual_output, used=used)
        # The correction commits BEFORE the refusal. Raising inside the
        # transaction rolled the true-up back on the one path where it matters:
        # the ledger kept showing the reservation instead of the tokens the
        # provider actually billed, and the request stayed in flight forever.
        if used["input_tokens"] > limits.get("input_tokens", 0) or used["output_tokens"] > limits.get("output_tokens", 0):
            raise StoreConflict("AGENT_BUDGET_EXCEEDED", "actual token usage exceeded the run budget")

    def charge_budget(self, run_id: str, dimension: str, amount: int | float) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            used, limits = dict(budget["used"]), budget["limits"]
            if used.get(dimension, 0) + amount > limits.get(dimension, 0):
                raise StoreConflict("AGENT_BUDGET_EXCEEDED", f"{dimension} budget exhausted")
            used[dimension] = used.get(dimension, 0) + amount
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(used=used))

    def record_attempt(self, run_id: str, row: dict[str, Any], terminal: bool) -> None:
        with self.engine.begin() as conn:
            budget = self._budget_locked(conn, run_id)
            attempts = list(budget["attempts"])
            if terminal:
                attempts.append(row)
                attempts = attempts[-MAX_ATTEMPT_RECORDS:]
            else:
                if len(attempts) >= MAX_ATTEMPT_RECORDS:
                    raise StoreConflict("AGENT_BUDGET_EXCEEDED", "attempt metadata budget exhausted")
                attempts.append(row)
            conn.execute(sa.update(run_budgets).where(run_budgets.c.run_id == run_id).values(attempts=attempts))

    # -- snapshots ----------------------------------------------------------

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_snapshots).where(run_snapshots.c.id == snapshot_id)).mappings().first()
        return dict(row) if row else None

    def snapshot_for_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(sa.select(run_snapshots).where(run_snapshots.c.run_id == run_id)).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _snapshot_record(conn: sa.Connection, snapshot: dict[str, Any]) -> dict[str, Any]:
        run_identity = _provider_identity(conn.execute(
            sa.select(runs.c.provider_identity).where(runs.c.id == snapshot["run_id"])
        ).scalar_one())
        snapshot_identity = _provider_identity(snapshot.get("provider_identity"))
        if snapshot_identity != run_identity:
            raise StoreConflict("AGENT_IDENTITY_MISMATCH", "snapshot identity differs from run")
        record = {**snapshot, "provider_identity": run_identity}
        preimage = {
            key: value for key, value in record.items()
            if key not in {"digest", "id"}
        }
        if record.get("digest") != digest(preimage):
            raise StoreConflict("AGENT_IDENTITY_MISMATCH", "snapshot digest does not bind provider identity")
        return record

    def create_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Low-level fixture seam; ordinary acceptance uses accept_snapshot."""
        with self.engine.begin() as conn:
            record = self._snapshot_record(conn, snapshot)
            conn.execute(run_snapshots.insert().values(**record))
            conn.execute(sa.update(runs).where(runs.c.id == record["run_id"]).values(accepted_snapshot_id=record["id"]))
        return record

    def accept_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        actor: str,
        audit: Any,
    ) -> dict[str, Any]:
        """Atomically publish snapshot, run/case pointers, and audit event."""
        with self.engine.begin() as conn:
            record = self._snapshot_record(conn, snapshot)
            run = conn.execute(
                sa.select(runs).where(runs.c.id == record["run_id"])
            ).mappings().one()
            if (
                run["case_id"] != record["case_id"]
                or run["status"] != "succeeded"
                or run["accepted_snapshot_id"] is not None
            ):
                raise StoreConflict("RUN_NOT_READY", "run cannot publish an accepted snapshot")
            case_pointer = cases.c.accepted_snapshot_id
            expected_previous = record.get("previous_snapshot_id")
            changed = conn.execute(
                sa.update(cases)
                .where(
                    cases.c.id == record["case_id"],
                    case_pointer.is_(None)
                    if expected_previous is None
                    else case_pointer == expected_previous,
                )
                .values(accepted_snapshot_id=record["id"])
            ).rowcount
            if changed != 1:
                raise StoreConflict(
                    "SNAPSHOT_AUTHORITY_CHANGED",
                    "case accepted snapshot moved during acceptance",
                )
            conn.execute(run_snapshots.insert().values(**record))
            changed = conn.execute(
                sa.update(runs)
                .where(
                    runs.c.id == record["run_id"],
                    runs.c.accepted_snapshot_id.is_(None),
                )
                .values(accepted_snapshot_id=record["id"])
            ).rowcount
            if changed != 1:
                raise StoreConflict("RUN_NOT_READY", "run acceptance was already consumed")
            audit(
                conn,
                "snapshot.accepted",
                actor,
                case_id=record["case_id"],
                snapshot_id=record["id"],
                run_id=record["run_id"],
                provider_identity_digest=(record.get("provider_identity") or {}).get("identity_digest"),
            )
        return record

    def serialize_all_for_run(self, run_id: str) -> str:
        chunks: list[Any] = [self.get_run(run_id), self.events_after(run_id, 0), self.artifacts_for_run(run_id), self.get_budget(run_id)]
        return json.dumps(chunks, sort_keys=True, default=str)
