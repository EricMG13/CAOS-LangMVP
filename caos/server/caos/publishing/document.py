"""The publication document: one server-frozen typed structure every renderer
reads (Task 10; ENTERPRISE_READINESS_PLAN Phase 4 items 6–10).

Built once at freeze from the frozen payload, the signed opinion, the accepted
run's identity and the case's source register. Browser, Markdown, PDF and XLSX
walk `payload["publication"]` and nothing else, so the same facts, numbers,
units, citations, origin labels, limitations, model identity and opinion reach
every format by construction. Sections reuse `CanonicalDocumentSection`, so the
browser renderer that already draws the draft draws the publication too.

The approval state in frozen bytes is always `PENDING APPROVAL`: the approver
is named only in the detached filing receipt and the audit chain (item 6).
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import TypeAdapter

from ..contracts import CanonicalDocumentSection

PUBLICATION_SCHEMA_VERSION = "caos.deliverable.publication.v1"
CONTROL_PAGE = "Control"
PENDING_APPROVAL = "PENDING APPROVAL"
MAX_TABLE_ROWS = 500
_ADAPTER = TypeAdapter(list[CanonicalDocumentSection])

# Model outputs and calculator records surface these; every renderer shows the
# same word for the same absence (Phase 4 verify: one tested convention).
UNAVAILABLE = "Unavailable"


def _text(value: Any) -> str:
    if value is None or value == "":
        return UNAVAILABLE
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _origin(kind: str, authority_id: str) -> dict[str, Any]:
    return {"kind": kind, "authority_id": authority_id, "block_ids": []}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")[:120] or "section"


def _walk(sections: list[dict[str, Any]]):
    for section in sections:
        yield section
        if section["kind"] == "columns":
            for column in section["items"]:
                yield from _walk(column)


def _pages(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    by_name: dict[str, dict[str, Any]] = {}
    for section in sections:
        page = by_name.get(section["page"])
        if page is None:
            page = {"name": section["page"], "sections": []}
            by_name[section["page"]] = page
            pages.append(page)
        page["sections"].append(section)
    return pages


def _opinion_sections(opinion: dict[str, Any], page: str) -> list[dict[str, Any]]:
    authority = opinion["opinion_id"]
    return [
        {
            "kind": "text", "section_id": "analyst_opinion", "title": "Analyst Opinion", "page": page,
            "editable": False, "origin": _origin("ANALYST", authority), "body": opinion["opinion"],
        },
        {
            "kind": "profile", "section_id": "opinion_sign_off", "title": "Opinion Sign-Off", "page": page,
            "editable": False, "origin": _origin("ANALYST", authority),
            "rows": [
                {"label": "Limitations", "value": opinion["limitations"]},
                {"label": "Material overrides", "value": opinion["material_overrides"]},
                {"label": "Rationale", "value": opinion["rationale"]},
                {"label": "Signed by", "value": opinion["signed_by"]},
                {"label": "Signed at", "value": opinion["signed_at"]},
                {"label": "Opinion digest", "value": opinion["opinion_digest"]},
                {"label": "Approval state", "value": PENDING_APPROVAL},
            ],
        },
    ]


def _model_identity_text(model_identity: dict[str, Any] | None) -> str:
    if not model_identity:
        return "No model authority (pathway permits omission)"
    parts = [str(model_identity.get("kind") or UNAVAILABLE), f"build {model_identity.get('build_id') or UNAVAILABLE}"]
    if model_identity.get("revision_id"):
        parts.append(f"revision {model_identity['revision_id']}")
    runtime = model_identity.get("calculation_runtime") or {}
    if runtime.get("name"):
        parts.append(f"runtime {runtime['name']} {runtime.get('version') or ''}".strip())
    if model_identity.get("methodology_build_id"):
        parts.append(f"methodology {model_identity['methodology_build_id']}")
    relationship = (model_identity.get("model_authority") or {}).get("relationship")
    if relationship:
        parts.append(str(relationship))
    return " · ".join(parts)


def _machine_assistance_text(provider_identity: dict[str, Any] | None) -> str:
    if not provider_identity:
        return "Provider identity unavailable for the accepted analysis"
    return (
        f"Provider {provider_identity.get('provider_name') or UNAVAILABLE} · model "
        f"{provider_identity.get('model') or UNAVAILABLE} · adapter "
        f"{provider_identity.get('adapter_version') or UNAVAILABLE} · qualification "
        f"{provider_identity.get('qualification_status') or UNAVAILABLE}"
    )


def _limitation_texts(payload: dict[str, Any], opinion: dict[str, Any]) -> list[str]:
    texts = [f"Analyst limitations: {opinion['limitations']}"]
    for block in payload["content"].get("blocks") or []:
        if block.get("kind") == "LIMITATIONS" and block.get("text"):
            texts.append(f"Declared limitation: {block['text']}")
    qa = ((payload.get("model") or {}).get("application_build") or {}).get("qa") or {}
    for flag in qa.get("limitation_flags") or []:
        texts.append(f"Model limitation flag: {flag}")
    for warning in qa.get("validation_warnings") or []:
        texts.append(f"Model validation warning: {warning}")
    return texts


def _source_register(
    sources: list[dict[str, Any]],
    dispositions: dict[str, dict[str, Any]],
    cited_source_ids: set[str],
) -> list[list[str]]:
    rows: list[list[str]] = []
    for source in sources:
        manifest = dispositions.get(source.get("sha256") or "", {})
        disposition = manifest.get("disposition") or "used"
        reason = manifest.get("reason") or ""
        rows.append([
            _text(source.get("id")),
            _text(source.get("filename")),
            _text(source.get("sha256")),
            _text(manifest.get("document_type") or "unclassified"),
            _text(manifest.get("period") or UNAVAILABLE),
            f"{disposition}{' — ' + reason if reason else ''}",
            "Yes" if source.get("id") in cited_source_ids else "No",
        ])
    return rows[:MAX_TABLE_ROWS]


def _origin_counts(sections: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"ANALYST": 0, "MODEL": 0, "ARTIFACT": 0, "SYSTEM": 0}
    for section in _walk(sections):
        counts[section["origin"]["kind"]] = counts.get(section["origin"]["kind"], 0) + 1
    return counts


def build_publication(
    *,
    payload: dict[str, Any],
    opinion: dict[str, Any],
    case: dict[str, Any],
    deliverable_id: str,
    provider_identity: dict[str, Any] | None,
    accepted_at: str | None,
    run_id: str | None,
    sources: list[dict[str, Any]],
    dispositions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compose masthead, pages (opinion first, then the pathway's canonical
    sections, then the Evidence & QA Control Sheet) and disclosures."""
    content = payload["content"]
    sections = list(content.get("document_sections") or [])
    pages = _pages(sections)
    first_page = pages[0]["name"] if pages else "Decision"
    opinion_sections = _opinion_sections(opinion, first_page)
    if pages:
        pages[0]["sections"] = [*opinion_sections, *pages[0]["sections"]]
    else:
        pages.append({"name": first_page, "sections": opinion_sections})

    model_identity = content.get("model_identity")
    authority = payload["authority"]
    cited = {row["source_id"] for row in payload.get("evidence") or []}
    evidence_rows = [
        [row["source_id"], ", ".join(row["block_ids"]), "withdrawn" if row.get("withdrawn") else "live"]
        for row in payload.get("evidence") or []
    ][:MAX_TABLE_ROWS]
    limitation_texts = _limitation_texts(payload, opinion)
    counts = _origin_counts(sections)
    masthead = {
        "issuer": _text(case.get("issuer")),
        "case_name": _text(case.get("name")),
        "case_id": payload["case_id"],
        "report_type": payload["template"]["title"],
        "pathway": payload["pathway"],
        "deliverable_id": deliverable_id,
        "draft_version": payload["draft"]["version"],
        "draft_digest": payload["draft"]["digest"],
        "input_fingerprint": payload["input_fingerprint"],
        "as_of_date": (accepted_at or "")[:10] or UNAVAILABLE,
        "run_id": _text(run_id),
        "accepted_snapshot_id": _text(authority.get("accepted_snapshot_id")),
        "source_set": f"{_text(authority.get('source_set_id'))} v{_text(authority.get('source_set_version'))}",
        "model_identity": _model_identity_text(model_identity),
        "methodology_build_id": _text(payload["methodology"]["build_id"]),
        "machine_assistance": _machine_assistance_text(provider_identity),
        "approval_state": PENDING_APPROVAL,
        "watermark": PENDING_APPROVAL,
        "opinion_owner": opinion["signed_by"],
        "opinion_signed_at": opinion["signed_at"],
        "opinion_id": opinion["opinion_id"],
        "renderer_version": payload["renderer"]["version"],
    }
    control_sections = [
        {
            "kind": "profile", "section_id": "control_status", "title": "Control Status", "page": CONTROL_PAGE,
            "editable": False, "origin": _origin("SYSTEM", deliverable_id),
            "rows": [
                {"label": "Approval state", "value": PENDING_APPROVAL},
                {"label": "Opinion owner", "value": f"{opinion['signed_by']} · {opinion['signed_at']}"},
                {"label": "Freeze identity", "value": f"{deliverable_id} · Draft v{payload['draft']['version']} · {payload['draft']['digest']}"},
                {"label": "Input fingerprint", "value": payload["input_fingerprint"]},
                {"label": "Accepted snapshot", "value": masthead["accepted_snapshot_id"]},
                {"label": "Source set", "value": masthead["source_set"]},
                {"label": "As-of date", "value": masthead["as_of_date"]},
                {"label": "Model identity", "value": masthead["model_identity"]},
                {"label": "Methodology build", "value": masthead["methodology_build_id"]},
                {"label": "Machine assistance", "value": masthead["machine_assistance"]},
                {"label": "Renderer", "value": masthead["renderer_version"]},
                {"label": "Approver identity", "value": "Recorded in the detached filing receipt and the audit chain, never in these bytes"},
            ],
        },
        {
            "kind": "table", "section_id": "source_document_register", "title": "Source Document Register",
            "page": CONTROL_PAGE, "editable": False, "origin": _origin("ARTIFACT", masthead["accepted_snapshot_id"]),
            "columns": ["Source", "Filename", "SHA-256", "Type", "Period", "Disposition", "Cited"],
            "rows": _source_register(sources, dispositions, cited),
            "note": "Every supplied document in the pinned source set with its host disposition; cited means referenced by this deliverable's evidence register.",
        },
        {
            "kind": "table", "section_id": "registered_evidence_inventory", "title": "Registered Evidence Inventory",
            "page": CONTROL_PAGE, "editable": False, "origin": _origin("ARTIFACT", masthead["accepted_snapshot_id"]),
            "columns": ["Source", "Blocks", "Status"],
            "rows": evidence_rows,
            "note": None,
        },
        {
            "kind": "list", "section_id": "limitations_and_open_qa", "title": "Limitations and Open QA",
            "page": CONTROL_PAGE, "editable": False, "origin": _origin("ANALYST", opinion["opinion_id"]),
            "items": limitation_texts,
        },
        {
            "kind": "profile", "section_id": "content_origin", "title": "Content Origin", "page": CONTROL_PAGE,
            "editable": False, "origin": _origin("SYSTEM", deliverable_id),
            "rows": [
                {"label": "Analyst-owned sections", "value": str(counts.get("ANALYST", 0))},
                {"label": "Model-locked sections", "value": str(counts.get("MODEL", 0))},
                {"label": "Artifact-locked sections", "value": str(counts.get("ARTIFACT", 0))},
                {"label": "System sections", "value": str(counts.get("SYSTEM", 0))},
                {"label": "Convention", "value": "Analyst judgment is labelled as such; locked sections carry the authority id they were generated from; Unavailable marks a value the sources or the model did not provide."},
            ],
        },
    ]
    pages.append({"name": CONTROL_PAGE, "sections": control_sections})
    all_sections = [section for page in pages for section in page["sections"]]
    validated = _ADAPTER.dump_python(_ADAPTER.validate_python(all_sections), mode="json")
    by_id = {section["section_id"]: section for section in validated}
    pages = [
        {"name": page["name"], "sections": [by_id[section["section_id"]] for section in page["sections"]]}
        for page in pages
    ]
    disclosures = {
        "content_origin": "Sections are labelled by origin: analyst judgment, model calculation, accepted analysis artifact, or system control record.",
        "sources": f"{len(sources)} supplied documents in the pinned source set; {len(cited)} cited.",
        "limitations": limitation_texts,
        "machine_assistance": masthead["machine_assistance"],
        "analyst_opinion_owner": opinion["signed_by"],
        "approval_state": PENDING_APPROVAL,
        "as_of_date": masthead["as_of_date"],
        "version": f"{deliverable_id} · Draft v{payload['draft']['version']}",
        "digests": {"draft_digest": payload["draft"]["digest"], "input_fingerprint": payload["input_fingerprint"]},
    }
    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "masthead": masthead,
        "pages": pages,
        "disclosures": disclosures,
    }
