"""Canonical module output validation and host-owned canonicalization.

Ported from LEGACY methodology/canonical.py per DECISIONS §5: the validators,
canonicalization, and envelope stamping copy; the runner halves (anything
driving the loop) are rewritten in caos.engine. Invariants 2, 3, 9: the host
owns identity, evidence trace, registry, and confidence — provider assertions
never survive.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..config import Settings
from ..contracts import BoundaryText, NonBlankBoundaryText, validate_boundary_text


_H2 = re.compile(r"^##\s+(.+?)\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_RAW_CONTENT_TAG = re.compile(r"^<(script|pre|style|textarea)(?:[ \t>]|$)", re.IGNORECASE)
_RAW_HTML_TAG = re.compile(r"^</?[A-Za-z][A-Za-z0-9-]*(?:[ \t]|/?>|$)")
_STABLE_TABLE_MARKER = re.compile(
    r"^\s*<!--\s*table-id:\s*([a-z0-9_.-]+)\s*-->\s*$",
)
_HEADINGS = (
    "Audit Summary",
    "Analysis",
    "Evidence Trace",
    "Source Registry",
    "Gaps & Conflicts",
    "QA Validation",
)
MAX_CANONICAL_MARKDOWN_CHARS = 2 * 1024 * 1024
MAX_EVIDENCE_REFS_PER_MODULE = 200
MAX_EVIDENCE_ID_CHARS = 160
MAX_HANDOFF_LIST_ITEMS = 50
MAX_HANDOFF_TEXT_CHARS = 500
BoundedCount = Annotated[int, Field(strict=True, ge=0, le=10_000)]
BoundedHandoffText = Annotated[
    NonBlankBoundaryText,
    Field(min_length=1, max_length=MAX_HANDOFF_TEXT_CHARS),
]
ReportingPeriod = Annotated[NonBlankBoundaryText, Field(min_length=1, max_length=80)]
ModuleId = Annotated[
    BoundaryText,
    Field(pattern=r"^CP-(?:\d+[A-Z]?|[A-Z][A-Z0-9-]*)$", max_length=40),
]
_LINEAGE_KEYS = frozenset({
    "directly sourced", "directly_sourced", "calculated", "assumption-based",
    "assumption_based", "analyst inference", "analyst_inference", "weak lineage",
    "weak_lineage", "untraced", "conflicting", "insufficient information",
    "insufficient_information",
})


class CanonicalValidationError(ValueError):
    pass


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=MAX_EVIDENCE_ID_CHARS)
    block_id: str = Field(min_length=1, max_length=MAX_EVIDENCE_ID_CHARS)


class CalculationRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    calculator_id: str = Field(min_length=1, max_length=160)
    script_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    calculator_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class HandoffUpstreamArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: ModuleId
    run_id: BoundedHandoffText
    period: ReportingPeriod
    artifact_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CanonicalHandoffMetadata(BaseModel):
    """Restricted frontmatter rebuilt from host state plus bounded analysis labels."""

    model_config = ConfigDict(extra="forbid")

    module_id: ModuleId
    module_name: BoundedHandoffText
    run_id: BoundedHandoffText
    reporting_period: ReportingPeriod
    analysis_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    confidence_score: int = Field(strict=True, ge=0, le=100)
    confidence_band: Literal["High", "Medium", "Low", "Insufficient Information"]
    qa_status: Literal["Passed", "Restricted", "Blocked"]
    committee_status: Literal[
        "Committee Ready", "Draft Only", "Requires More Work",
        "Insufficient Information", "Restricted", "Blocked",
    ]
    limitation_flags: list[BoundedHandoffText] = Field(max_length=MAX_HANDOFF_LIST_ITEMS)
    validation_warnings: list[BoundedHandoffText] = Field(max_length=MAX_HANDOFF_LIST_ITEMS)
    upstream_artifacts_used: list[HandoffUpstreamArtifact] = Field(max_length=MAX_HANDOFF_LIST_ITEMS)
    downstream_consumers: list[ModuleId] = Field(max_length=MAX_HANDOFF_LIST_ITEMS)
    issuer_name: Annotated[NonBlankBoundaryText, Field(min_length=1, max_length=160)]
    issuer_id: Annotated[
        BoundaryText,
        Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$", max_length=200),
    ]
    # CP-DR research envelope (Task 7): every value host-derived from the
    # approved plan, the pinned brief and the validated contract fields; the
    # pinned common validator requires all nine on CP-DR. Absent — never null —
    # on every other module, so no other artifact's frontmatter moves.
    scope_type: Literal["issuer", "sector"] | None = None
    scope_key: Annotated[
        BoundaryText,
        Field(pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$", max_length=200),
    ] | None = None
    subject_name: Annotated[NonBlankBoundaryText, Field(min_length=1, max_length=160)] | None = None
    research_question: BoundedHandoffText | None = None
    source_mode: Literal["supplied_only"] | None = None
    approved_plan_hash: Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")] | None = None
    coverage_score: Annotated[int, Field(strict=True, ge=0, le=100)] | None = None
    research_status: Literal["Complete", "Complete with Gaps", "Blocked"] | None = None
    research_stop_reason: Literal[
        "coverage_satisfied", "budget_exhausted", "sources_exhausted", "blocked", "user_stopped",
    ] | None = None


# The CP-DR envelope fields (schema: CP-DR_DeepResearch.schema.md § Required
# output-envelope extension): stamped by the host on plan-approval modules,
# listed in the artifact's host-derived provenance, absent everywhere else.
RESEARCH_HANDOFF_FIELDS = (
    "scope_type", "scope_key", "subject_name", "research_question", "source_mode",
    "approved_plan_hash", "coverage_score", "research_status", "research_stop_reason",
)


class CanonicalModuleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=MAX_CANONICAL_MARKDOWN_CHARS)
    evidence_refs: list[EvidenceRef] = Field(min_length=1, max_length=MAX_EVIDENCE_REFS_PER_MODULE)
    calculation_refs: list[CalculationRef] = Field(default_factory=list, max_length=200)
    lineage_counts: dict[str, BoundedCount]
    fields_present: int = Field(strict=True, ge=0, le=10_000)
    fields_total: int = Field(strict=True, ge=1, le=10_000)
    source_gate: Literal["pass", "partial", "fail"]
    findings: dict[Literal["CRITICAL", "MATERIAL", "MINOR"], BoundedCount] = Field(default_factory=dict)
    limitation_flags: list[BoundedHandoffText] = Field(default_factory=list, max_length=MAX_HANDOFF_LIST_ITEMS)
    validation_warnings: list[BoundedHandoffText] = Field(default_factory=list, max_length=MAX_HANDOFF_LIST_ITEMS)

    @field_validator("lineage_counts")
    @classmethod
    def known_lineage_classes(cls, value: dict[str, int]) -> dict[str, int]:
        if len(value) > 8 or any(key.casefold() not in _LINEAGE_KEYS for key in value):
            raise ValueError("lineage_counts contains an unknown lineage class")
        return value

    @model_validator(mode="after")
    def valid_coverage(self) -> "CanonicalModuleOutput":
        if self.fields_present > self.fields_total:
            raise ValueError("fields_present cannot exceed fields_total")
        return self


def _without_html_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    visible = list(line)
    cursor = 0
    while cursor < len(line):
        if in_comment:
            end = line.find("-->", cursor)
            stop = len(line) if end < 0 else end + 3
            visible[cursor:stop] = " " * (stop - cursor)
            cursor = stop
            if end < 0:
                break
            in_comment = False
            continue
        start = line.find("<!--", cursor)
        if start < 0:
            break
        end = line.find("-->", start + 4)
        stop = len(line) if end < 0 else end + 3
        visible[start:stop] = " " * (stop - start)
        cursor = stop
        in_comment = end < 0
    return "".join(visible), in_comment


def _is_indented_code(line: str) -> bool:
    columns = 0
    for character in line:
        if character == " ":
            columns += 1
        elif character == "\t":
            columns += 4 - (columns % 4)
        else:
            break
        if columns >= 4:
            return True
    return False


def _container_content(line: str) -> str:
    """Remove visible GFM quote/list markers while preserving code indentation."""
    content = line
    while match := re.match(r"^ {0,3}>[ \t]?", content):
        content = content[match.end():]
    list_item = re.match(
        r"^ {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]",
        content,
    )
    return content[list_item.end():] if list_item else content


def _scanned_lines(body: str):
    fence_char: str | None = None
    fence_length = 0
    in_comment = False
    raw_content_tag: str | None = None
    raw_terminator: str | None = None
    raw_until_blank = False
    for raw_line in body.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        container_content = _container_content(line)
        if fence_char is not None:
            stripped = container_content.lstrip(" ")
            if len(container_content) - len(stripped) <= 3 and re.fullmatch(
                re.escape(fence_char) + "{" + str(fence_length) + ",}[ \t]*",
                stripped,
            ):
                fence_char = None
                fence_length = 0
            visible = False
        elif raw_content_tag is not None:
            if re.search(
                rf"</{re.escape(raw_content_tag)}\s*>",
                container_content,
                re.IGNORECASE,
            ):
                raw_content_tag = None
            visible = False
        elif raw_terminator is not None:
            if raw_terminator in line:
                raw_terminator = None
            visible = False
        elif raw_until_blank:
            raw_until_blank = bool(line.strip())
            visible = False
        else:
            control_marker = not in_comment and _STABLE_TABLE_MARKER.fullmatch(line)
            if not control_marker:
                line, in_comment = _without_html_comments(line, in_comment)
            container_content = _container_content(line)
            fence = _FENCE.match(container_content) if not in_comment else None
            if fence:
                fence_char = fence.group(1)[0]
                fence_length = len(fence.group(1))
                visible = False
            elif _is_indented_code(container_content):
                visible = False
            else:
                stripped = container_content.lstrip(" \t")
                content_tag = _RAW_CONTENT_TAG.match(stripped)
                if content_tag:
                    tag = content_tag.group(1)
                    if not re.search(rf"</{re.escape(tag)}\s*>", stripped, re.IGNORECASE):
                        raw_content_tag = tag
                    visible = False
                elif stripped.startswith("<?"):
                    raw_terminator = None if "?>" in stripped[2:] else "?>"
                    visible = False
                elif stripped.startswith("<![CDATA["):
                    raw_terminator = None if "]]>" in stripped[9:] else "]]>"
                    visible = False
                elif re.match(r"^<![A-Z]", stripped):
                    raw_terminator = None if ">" in stripped[2:] else ">"
                    visible = False
                elif _RAW_HTML_TAG.match(stripped):
                    raw_until_blank = True
                    visible = False
                else:
                    visible = True
        yield raw_line, line, visible


def _top_level(line: str) -> bool:
    """Return whether a structural Markdown line is outside quote/list containers."""
    return _container_content(line) == line


def visible_top_level_markdown(body: str) -> str:
    """Mask non-rendered/container Markdown without changing string offsets."""
    return "".join(
        raw_line if visible and _top_level(line) else re.sub(r"[^\r\n]", " ", raw_line)
        for raw_line, line, visible in _scanned_lines(body)
    )


def validate_visible_stable_tables(markdown: str) -> None:
    """Refuse control tables whose vendor parser would read non-rendered bytes."""
    records = list(_scanned_lines(markdown))
    for index, (raw_line, line, visible) in enumerate(records):
        if _STABLE_TABLE_MARKER.fullmatch(raw_line.rstrip("\r\n")) is None:
            continue
        if not visible or not _top_level(line):
            raise CanonicalValidationError("stable table marker is not visible top-level Markdown")
        cursor = index + 1
        while cursor < len(records) and not records[cursor][0].strip():
            cursor += 1
        if cursor + 1 >= len(records):
            continue  # the pinned schema validator reports the missing table
        for row_index in (cursor, cursor + 1):
            _raw, row, row_visible = records[row_index]
            if not row_visible or not _top_level(row):
                raise CanonicalValidationError("stable table structure is not visible top-level Markdown")
        cursor += 2
        while cursor < len(records) and records[cursor][0].lstrip().startswith("|"):
            _raw, row, row_visible = records[cursor]
            if not row_visible or not _top_level(row):
                raise CanonicalValidationError("stable table row is not visible top-level Markdown")
            cursor += 1


def _sections(body: str) -> dict[str, str]:
    matches: list[tuple[str, int, int]] = []
    offset = 0
    for raw_line, line, outside_fence in _scanned_lines(body):
        if outside_fence and (heading := _H2.fullmatch(line)):
            matches.append((heading.group(1), offset, offset + len(line)))
        offset += len(raw_line)
    if tuple(match[0] for match in matches) != _HEADINGS:
        raise CanonicalValidationError("canonical H2 headings are missing, duplicated, or out of order")
    return {
        match[0]: body[match[2] : matches[index + 1][1] if index + 1 < len(matches) else len(body)].strip()
        for index, match in enumerate(matches)
    }


def _table_content(line: str) -> str:
    return line.lstrip(" \t").strip()


def _closing_backticks(line: str, start: int, length: int) -> int | None:
    marker = "`" * length
    cursor = start + length
    while (found := line.find(marker, cursor)) >= 0:
        if (
            (found == 0 or line[found - 1] != "`")
            and (found + length == len(line) or line[found + length] != "`")
        ):
            return found
        cursor = found + 1
    return None


def _table_cells(line: str) -> list[str] | None:
    """Split one visible GFM table row without treating rendered cell pipes as delimiters."""
    content = _table_content(line)
    delimiters: list[int] = []
    index = 0
    while index < len(content):
        if content[index] == "`":
            end = index + 1
            while end < len(content) and content[end] == "`":
                end += 1
            closing = _closing_backticks(content, index, end - index)
            if closing is not None:
                index = closing + end - index
                continue
            index = end
            continue
        if content[index] == "|":
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and content[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                delimiters.append(index)
        index += 1
    if not delimiters:
        return None
    boundaries = [-1, *delimiters, len(content)]
    cells = [
        content[boundaries[position] + 1:boundaries[position + 1]].strip()
        for position in range(len(boundaries) - 1)
    ]
    if delimiters[0] == 0:
        cells.pop(0)
    if delimiters[-1] == len(content) - 1:
        cells.pop()
    return [cell.replace(r"\|", "|") for cell in cells]


def _header_name(cell: str) -> str:
    value = html.unescape(re.sub(r"<[^>]*>", "", cell)).strip()
    value = re.sub(r"^\[([^]]+)]\([^)]*\)$", r"\1", value)
    value = re.sub(r"^\[([^]]+)]\[[^]]*]$", r"\1", value)
    value = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])", r"\1", value)
    changed = True
    while changed:
        changed = False
        for marker in ("**", "__", "~~", "*", "_", "`"):
            if value.startswith(marker) and value.endswith(marker) and len(value) > 2 * len(marker):
                value = value[len(marker):-len(marker)].strip()
                changed = True
                break
    return value.casefold()


def _model_source_ids(
    markdown: str,
    source_headers: frozenset[str] = frozenset({"source_id"}),
) -> set[str]:
    """Source IDs used by visible model-facing GFM tables."""
    source_ids: set[str] = set()
    records = list(_scanned_lines(markdown))

    def source_header(line: str) -> tuple[list[str], int] | None:
        cells = _table_cells(line)
        if cells is None:
            return None
        header = [_header_name(cell) for cell in cells]
        source_columns = [
            position for position, name in enumerate(header)
            if name in source_headers
        ]
        if not source_columns:
            return None
        if len(source_columns) != 1:
            raise CanonicalValidationError("model-facing source table has ambiguous source columns")
        return header, source_columns[0]

    def separator(line: str, columns: int) -> bool:
        cells = _table_cells(line)
        return (
            cells is not None
            and len(cells) == columns
            and all(re.fullmatch(r":?-+:?", cell) is not None for cell in cells)
        )

    # A source table may not manufacture one rendered table out of lines that
    # belong to different GFM containers, nor hide an alternate source table.
    for index, (raw_line, line, visible) in enumerate(records[:-1]):
        raw = raw_line.rstrip("\r\n")
        parsed = source_header(_container_content(raw))
        if parsed is None or not separator(
            _container_content(records[index + 1][0].rstrip("\r\n")),
            len(parsed[0]),
        ):
            continue
        next_line = records[index + 1][1]
        if not (
            visible
            and records[index + 1][2]
            and _top_level(line)
            and _top_level(next_line)
        ):
            raise CanonicalValidationError("model-facing source table crosses a hidden or nested container")

    index = 0
    while index + 1 < len(records):
        _raw, line, visible = records[index]
        parsed = source_header(line) if visible and _top_level(line) else None
        if parsed is None:
            index += 1
            continue
        header, source_column = parsed
        next_line = records[index + 1][1]
        if not records[index + 1][2] or not _top_level(next_line) or not separator(next_line, len(header)):
            raise CanonicalValidationError("model-facing source table has a malformed separator")
        row_count = 0
        cursor = index + 2
        while cursor < len(records):
            raw_row, row, row_visible = records[cursor]
            nested_cells = _table_cells(_container_content(raw_row.rstrip("\r\n")))
            if not row_visible or not _top_level(row):
                if nested_cells is not None:
                    raise CanonicalValidationError("model-facing source table crosses a hidden or nested container")
                break
            cells = _table_cells(row)
            if cells is None:
                break
            if len(cells) != len(header):
                raise CanonicalValidationError("model-facing source table has a malformed row")
            for source_id in re.split(r"\s*[;,]\s*", cells[source_column]):
                if source_id and source_id not in {"-", "—"}:
                    source_ids.add(source_id)
            row_count += 1
            cursor += 1
        # A header-only table is a declared absence (an issuer with no segment
        # disclosure, an empty schedule): it cites nothing and contributes no
        # source id. Malformed rows and hidden containers are refused above.
        index = cursor
    return source_ids


def model_source_ids(markdown: str) -> set[str]:
    """Return the exact IDs in ordinary ``source_id`` model tables."""
    return _model_source_ids(markdown)


def _cp2a_register_source_ids(markdown: str) -> set[str]:
    source_ids: set[str] = set()
    lines = [
        line if visible and _top_level(line) else ""
        for _raw, line, visible in _scanned_lines(markdown)
    ]
    for index, line in enumerate(lines[:-1]):
        header_cells = _table_cells(line)
        separator_cells = _table_cells(lines[index + 1])
        if header_cells is None or separator_cells is None:
            continue
        headers = [_header_name(cell) for cell in header_cells]
        source_columns = [
            position for position, header in enumerate(headers)
            if header in {"source", "source document"}
        ]
        if (
            len(source_columns) != 1
            or len(separator_cells) != len(headers)
            or any(re.fullmatch(r":?-+:?", cell) is None for cell in separator_cells)
        ):
            continue
        source_column = source_columns[0]
        for row in lines[index + 2:]:
            cells = _table_cells(row)
            if cells is None:
                break
            if len(cells) != len(headers):
                raise CanonicalValidationError("CP-2A source register has a malformed row")
            value = re.sub(r"<br\s*/?>", ";", cells[source_column], flags=re.IGNORECASE)
            for reference in re.split(r"[;,]", value):
                reference = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", reference).strip()
                if reference in {"", "-", "—"}:
                    continue
                match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._:-]*)", reference)
                source_ids.add(match.group(1) if match else reference)
                source_ids.update(
                    re.findall(
                        r"(?i)(?<![A-Za-z0-9._:-])src-[A-Za-z0-9][A-Za-z0-9._:-]*",
                        reference[match.end():] if match else "",
                    )
                )
    return source_ids


def validate_model_sources(
    markdown: str,
    returned_source_ids: set[str],
    *,
    module_id: str | None = None,
) -> None:
    cited = _model_source_ids(markdown)
    cited.update(_model_source_ids(
        markdown,
        frozenset({"source_refs", "source_or_conflict_ref"}),
    ))
    if module_id == "CP-2A":
        cited.update(_cp2a_register_source_ids(markdown))
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
    """Host-recomputed arithmetic over bounded provider-declared counts.

    This verifies the score calculation, not the truth of the declarations.
    The separate provider_asserted score is discarded entirely.
    """
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
    return {
        "confidence_score": score,
        "confidence_band": band,
        "qa_status": qa_status,
        "basis": "provider_declared_bounded_counts",
        "arithmetic": "host_recomputed",
        "analyst_review_required": True,
    }


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


def _render_frontmatter(metadata: CanonicalHandoffMetadata) -> str:
    # The optional CP-DR fields are omitted, never rendered as null (§12.1).
    fields = metadata.model_dump(exclude_none=True)
    lines = ["---"]
    for key, value in fields.items():
        if key != "upstream_artifacts_used" or not value:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=True)}")
            continue
        lines.append(f"{key}:")
        for artifact in value:
            lines.append(f"  - module_id: {json.dumps(artifact['module_id'])}")
            for field in ("run_id", "period", "artifact_digest"):
                lines.append(f"    {field}: {json.dumps(artifact[field])}")
    lines.append("---")
    return "\n".join(lines)


def canonicalize_for_tests(
    *,
    module_id: str,
    provider_markdown: str,
    run_identity: dict[str, Any],
    delivered: set[tuple[str, str]],
    build_id: str | None = None,
    handoff_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Envelope stamping with host-owned identity: provider frontmatter is
    discarded and the envelope is rebuilt from pinned state."""
    normalized = validate_boundary_text(provider_markdown)
    if len(normalized) > MAX_CANONICAL_MARKDOWN_CHARS:
        raise CanonicalValidationError("canonical Markdown exceeds its normalized size bound")
    body = strip_provider_frontmatter(normalized).strip()
    sections = _sections(body)
    metadata = None
    if handoff_metadata is None:
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
    else:
        metadata = CanonicalHandoffMetadata.model_validate(handoff_metadata)
        expected = {
            "module_id": module_id,
            "run_id": run_identity.get("run_id"),
            "module_name": run_identity.get("module_name"),
            "reporting_period": run_identity.get("reporting_period"),
            "analysis_date": run_identity.get("analysis_date"),
            "issuer_name": run_identity.get("issuer_name"),
            "issuer_id": run_identity.get("issuer_id"),
        }
        if any(getattr(metadata, key) != value for key, value in expected.items()):
            raise CanonicalValidationError("handoff metadata differs from host-owned identity")
        host_frontmatter = _render_frontmatter(metadata)
    markdown = host_frontmatter + "\n\n" + "\n\n".join(f"## {heading}\n\n{sections[heading]}" for heading in _HEADINGS) + "\n"
    if len(markdown) > MAX_CANONICAL_MARKDOWN_CHARS:
        raise CanonicalValidationError("canonical Markdown exceeds its final size bound")
    return {
        "schema_version": "caos.canonical.artifact.v1",
        "module_id": module_id,
        "canonical_output": {
            "markdown": markdown,
            "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        },
        "methodology": {"build_id": build_id or _default_build_id()},
        "host_identity": dict(run_identity),
        **({"handoff_metadata": metadata.model_dump(exclude_none=True)} if metadata is not None else {}),
        "evidence_refs": [
            {"source_id": source_id, "block_id": block_id} for source_id, block_id in sorted(delivered)
        ],
    }
