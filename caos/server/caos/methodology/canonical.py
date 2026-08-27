"""Canonical module output validation and host-owned canonicalization.

Ported from LEGACY methodology/canonical.py per DECISIONS §5: the validators,
canonicalization, and envelope stamping copy; the runner halves (anything
driving the loop) are rewritten in caos.engine. Invariants 2, 3, 9: the host
owns identity, evidence trace, registry, and confidence — provider assertions
never survive.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings


_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_HEADINGS = (
    "Audit Summary",
    "Analysis",
    "Evidence Trace",
    "Source Registry",
    "Gaps & Conflicts",
    "QA Validation",
)


class CanonicalValidationError(ValueError):
    pass


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=160)
    block_id: str = Field(min_length=1, max_length=160)


class CanonicalModuleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=2 * 1024 * 1024)
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=200)
    lineage_counts: dict[str, int]
    fields_present: int = Field(ge=0, le=10_000)
    fields_total: int = Field(ge=1, le=10_000)
    source_gate: Literal["pass", "partial", "fail"]
    findings: dict[Literal["CRITICAL", "MATERIAL", "MINOR"], int] = Field(default_factory=dict)


def _sections(body: str) -> dict[str, str]:
    matches = list(_H2.finditer(body))
    if tuple(match.group(1) for match in matches) != _HEADINGS:
        raise CanonicalValidationError("canonical H2 headings are missing, duplicated, or out of order")
    return {
        match.group(1): body[match.end() : matches[index + 1].start() if index + 1 < len(matches) else len(body)].strip()
        for index, match in enumerate(matches)
    }


def _model_source_ids(markdown: str) -> set[str]:
    """Source IDs used by model-facing Markdown tables (ported verbatim)."""
    source_ids: set[str] = set()
    lines = markdown.splitlines()
    for index, line in enumerate(lines[:-2]):
        if not line.lstrip().startswith("|"):
            continue
        header = [cell.strip().casefold() for cell in line.strip().strip("|").split("|")]
        if "source_id" not in header:
            continue
        separator = lines[index + 1].strip()
        if not separator.startswith("|") or set(separator.replace("|", "").replace("-", "").replace(":", "").strip()):
            continue
        source_column = header.index("source_id")
        for row in lines[index + 2 :]:
            if not row.lstrip().startswith("|"):
                break
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if len(cells) != len(header):
                break
            for source_id in re.split(r"\s*[;,]\s*", cells[source_column]):
                if source_id and source_id not in {"-", "—"}:
                    source_ids.add(source_id)
    return source_ids


def validate_model_sources(markdown: str, returned_source_ids: set[str]) -> None:
    cited = _model_source_ids(markdown)
    if not cited or not cited <= returned_source_ids:
        raise CanonicalValidationError("model-facing tables cite evidence outside returned pinned sources")


def validate_citations(declared: list[dict[str, str]], delivered: set[tuple[str, str]]) -> None:
    """§12.10: the citation contract is the delivered-evidence exact set."""
    pairs = [(ref["source_id"], ref["block_id"]) for ref in declared]
    if len(pairs) != len(set(pairs)) or set(pairs) != set(delivered):
        raise CanonicalValidationError("provider evidence references do not match returned pinned evidence")


def require_qa_passed(confidence: dict[str, Any]) -> None:
    """§12.26: non-Passed module QA is terminal."""
    if confidence.get("qa_status") != "Passed":
        raise CanonicalValidationError("canonical module output is not QA Passed")


def recompute_confidence(declared_inputs: dict[str, Any], provider_asserted: dict[str, Any] | None = None) -> dict[str, Any]:
    """Host-recomputed confidence from host-attested provenance only. The
    provider_asserted mapping is accepted and discarded — nothing in it enters
    the computation (re-hosts the CP-DR host-provenance contractual row)."""
    del provider_asserted  # invariant: never consulted
    lineage = declared_inputs.get("lineage_counts") or {}
    findings = declared_inputs.get("findings") or {}
    fields_total = max(1, int(declared_inputs.get("fields_total", 1)))
    coverage = max(0.0, min(1.0, int(declared_inputs.get("fields_present", 0)) / fields_total))
    sourced = int(lineage.get("directly_sourced", 0))
    gate = declared_inputs.get("source_gate", "fail")
    score = round(100 * (0.6 * coverage + 0.4 * (1.0 if sourced else 0.0)))
    if gate == "fail" or int(findings.get("CRITICAL", 0)):
        qa_status = "Blocked"
    elif gate == "partial" or int(findings.get("MATERIAL", 0)) or coverage < 1.0:
        qa_status = "Restricted"
    else:
        qa_status = "Passed"
    band = "HIGH" if score >= 80 and qa_status == "Passed" else "MEDIUM" if score >= 50 else "LOW"
    return {"confidence_score": score, "confidence_band": band, "qa_status": qa_status}


@lru_cache(maxsize=1)
def _default_build_id() -> str:
    manifest = json.loads((Settings().deploy_v_root / "DEPLOY_V_INTEGRITY_v1.json").read_text(encoding="utf-8"))
    return manifest["build_id"]


def strip_provider_frontmatter(markdown: str) -> str:
    """Provider-claimed frontmatter identity never survives (invariant 3)."""
    if markdown.startswith("---\n"):
        end = markdown.find("\n---\n", 4)
        if end != -1:
            return markdown[end + len("\n---\n") :]
        if markdown.rstrip().endswith("\n---"):
            return ""
    return markdown


def canonicalize_for_tests(
    *,
    module_id: str,
    provider_markdown: str,
    run_identity: dict[str, Any],
    delivered: set[tuple[str, str]],
    build_id: str | None = None,
) -> dict[str, Any]:
    """Envelope stamping with host-owned identity: provider frontmatter is
    discarded and the envelope is rebuilt from pinned state."""
    body = strip_provider_frontmatter(provider_markdown).strip()
    sections = _sections(body)
    host_frontmatter = "\n".join(
        (
            "---",
            f"module_id: {module_id}",
            f"run_id: {json.dumps(run_identity.get('run_id', ''))}",
            f"issuer_id: {json.dumps(run_identity.get('issuer_id', ''))}",
            f"reporting_period: {json.dumps(run_identity.get('reporting_period', ''))}",
            "---",
        )
    )
    markdown = host_frontmatter + "\n\n" + "\n\n".join(f"## {heading}\n\n{sections[heading]}" for heading in _HEADINGS) + "\n"
    return {
        "schema_version": "caos.canonical.artifact.v1",
        "module_id": module_id,
        "canonical_output": {
            "markdown": markdown,
            "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        },
        "methodology": {"build_id": build_id or _default_build_id()},
        "host_identity": dict(run_identity),
        "evidence_refs": [
            {"source_id": source_id, "block_id": block_id} for source_id, block_id in sorted(delivered)
        ],
    }
