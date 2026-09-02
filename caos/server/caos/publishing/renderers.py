"""Frozen-deliverable export renderers (md / pdf / xlsx).

Structure follows LEGACY publishing/renderers.py (DECISIONS §5: export
renderers copy as domain code), rebuilt lean on the libraries actually pinned:
openpyxl for xlsx and a minimal deterministic PDF writer (reportlab is not a
dependency of this build). Every export renders exclusively from the frozen
payload; analyst text with a formula prefix is neutralized to a literal.
"""

from __future__ import annotations

import io
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import zlib
from decimal import Decimal
from pathlib import Path
from typing import Any

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _block_title(block: dict[str, Any], titles: dict[str, str] | None = None) -> str:
    return (titles or {}).get(block["block_id"]) or block.get("title") or block["kind"].replace("_", " ").title()


def _citation_lines(block: dict[str, Any]) -> list[str]:
    return [
        f"{citation['claim']} [{citation['source_id']}: {', '.join(citation['block_ids'])}]"
        for citation in block.get("citations") or []
    ]


def _flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_flatten(child, f"{prefix}[{index}]"))
    else:
        items.append((prefix, value))
    return items


def _document_sections(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    return payload["content"].get("document_sections")


def _walk_sections(
    sections: list[dict[str, Any]], depth: int = 0,
):
    for section in sections:
        yield section, depth
        if section["kind"] == "columns":
            for column in section["items"]:
                yield from _walk_sections(column, depth + 1)


def _section_rows(section: dict[str, Any]) -> list[list[str]]:
    if section["kind"] == "table":
        return [section["columns"], *section["rows"]]
    if section["kind"] == "profile":
        return [[row["label"], row["value"]] for row in section["rows"]]
    if section["kind"] == "list":
        return [[item] for item in section["items"]]
    if section["kind"] == "chart":
        return [section["accessible_columns"], *section["accessible_rows"]]
    if section["kind"] == "text":
        return [[section["body"]]]
    return []


def _document_text_lines(payload: dict[str, Any], sections: list[dict[str, Any]]) -> list[str]:
    def markdown_row(row: list[str]) -> str:
        return "| " + " | ".join(str(cell).replace("|", r"\|") for cell in row) + " |"

    lines = [f"{payload['pathway']} Deliverable", ""]
    for section, depth in _walk_sections(sections):
        lines.append(f"{'#' * min(2 + depth, 6)} {section['title']}")
        rows = _section_rows(section)
        if section["kind"] in {"table", "chart"} and rows:
            lines.append(markdown_row(rows[0]))
            lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
            lines.extend(markdown_row(row) for row in rows[1:])
        elif section["kind"] == "profile":
            lines.extend(f"- {label}: {value}" for label, value in rows)
        elif section["kind"] == "list":
            lines.extend(f"- {row[0]}" for row in rows)
        else:
            lines.extend(row[0] for row in rows)
        if section.get("note"):
            lines.append(section["note"])
        lines.append("")
    lines.extend([
        "# Revision Record",
        f"- Draft version: {payload['draft']['version']}",
        f"- Draft digest: {payload['draft']['digest']}",
        f"- Content digest: {payload['preview_digest']}",
        f"- Input fingerprint: {payload['input_fingerprint']}",
        f"- Methodology build: {payload['methodology']['build_id']}",
    ])
    return lines


def _text_lines(payload: dict[str, Any]) -> list[str]:
    """The shared textual projection of a frozen payload (md and pdf bodies)."""
    sections = _document_sections(payload)
    if sections is not None:
        return _document_text_lines(payload, sections)
    lines = [f"{payload['pathway']} Deliverable", ""]
    model = payload.get("model")
    if model:
        lines.append("Model authority outputs:")
        for key, value in _flatten(model.get("outputs") or {}):
            lines.append(f"- {key}: {value}")
        lines.append("")
    titles = (payload.get("template") or {}).get("block_titles") or {}
    for block in payload["content"]["blocks"]:
        lines.append(f"## {_block_title(block, titles)}" if block["kind"] != "HEADING" else f"# {block['text']}")
        if block["kind"] == "HEADING":
            lines.append(block["text"])
        elif block["kind"] in {"NARRATIVE", "LIMITATIONS"}:
            lines.append(block["text"])
        elif block["kind"] == "EVIDENCE_REGISTER":
            lines.extend(f"- {line}" for line in _citation_lines(block))
        elif block["kind"] == "SCENARIO_EXHIBIT":
            for key, value in _flatten(block["scenario"].get("outputs") or {}):
                lines.append(f"- {key}: {value}")
        else:
            for key, value in _flatten({k: v for k, v in block.items() if k in ("values", "table", "recipe", "metric_ids", "field_ids")}):
                lines.append(f"- {key}: {value}")
        lines.append("")
    lines.extend([
        "## Revision Record",
        f"- Draft version: {payload['draft']['version']}",
        f"- Draft digest: {payload['draft']['digest']}",
        f"- Content digest: {payload['preview_digest']}",
        f"- Input fingerprint: {payload['input_fingerprint']}",
        f"- Methodology build: {payload['methodology']['build_id']}",
    ])
    return lines


def render_frozen_markdown(payload: dict[str, Any]) -> bytes:
    return ("\n".join(_text_lines(payload)) + "\n").encode("utf-8")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _unicode_pdf(pages_of_lines: list[list[str]]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    executable = shutil.which("pango-view")
    if executable is None:
        for candidate in (Path("/opt/homebrew/bin/pango-view"), Path("/usr/local/bin/pango-view")):
            if candidate.is_file():
                executable = str(candidate)
                break
    if executable is None:
        raise ValueError("PDF_UNICODE_RENDERER_UNAVAILABLE")
    environment = {**os.environ, "SOURCE_DATE_EPOCH": "0"}
    writer = PdfWriter()
    with tempfile.TemporaryDirectory(prefix="caos-pdf-") as directory:
        workspace = Path(directory)
        for index, lines in enumerate(pages_of_lines):
            source = workspace / f"page-{index:04d}.txt"
            rendered = workspace / f"page-{index:04d}.pdf"
            source.write_text("\n".join(lines), encoding="utf-8")
            try:
                subprocess.run(
                    [
                        executable,
                        "--no-display",
                        "--font=sans 10",
                        "--margin=54",
                        "--width=504",
                        "--height=684",
                        "--wrap=word-char",
                        f"--output={rendered}",
                        str(source),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                    env=environment,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise ValueError("PDF_UNICODE_RENDERER_FAILED") from exc
            for page in PdfReader(rendered).pages:
                writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
    return output.getvalue()


def render_frozen_pdf(payload: dict[str, Any]) -> bytes:
    """Minimal deterministic PDF: one Helvetica text column per page, plain
    Tj operators — structurally a PDF with extractable text."""
    text_lines = _text_lines(payload)
    try:
        "\n".join(text_lines).encode("cp1252")
        unicode_required = False
    except UnicodeEncodeError:
        unicode_required = True
    wrap_width, lines_per_page = ((80, 24) if unicode_required else (110, 48))
    pages_of_lines: list[list[str]] = []
    current: list[str] = []
    for raw_line in text_lines:
        for physical_line in raw_line.splitlines() or [""]:
            for line in textwrap.wrap(
                physical_line,
                width=wrap_width,
                break_on_hyphens=False,
            ) or [""]:
                current.append(line)
                if len(current) >= lines_per_page:
                    pages_of_lines.append(current)
                    current = []
    if current or not pages_of_lines:
        pages_of_lines.append(current or [""])

    if unicode_required:
        return _unicode_pdf(pages_of_lines)

    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    content_ids = []
    for lines in pages_of_lines:
        body = "BT /F1 10 Tf 54 756 Td 14 TL\n"
        for line in lines:
            body += f"({_pdf_escape(line)}) Tj T*\n"
        body += "ET"
        stream = zlib.compress(body.encode("cp1252"))
        content_ids.append(add(
            b"<< /Length " + str(len(stream)).encode() + b" /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream"
        ))
    pages_id = len(objects) + len(pages_of_lines) + 1
    page_ids = []
    for content_id in content_ids:
        page_ids.append(add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        ))
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    # The object must be ADDED outside the assert: under `python -O` the whole
    # expression vanishes, the /Pages object is never written, and every page
    # dangles against a missing parent — a silently corrupt PDF whose sha256
    # still matches the frozen record.
    written_pages_id = add(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode())
    assert written_pages_id == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    output = io.BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_at = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode())
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return output.getvalue()


def _safe_cell(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, Decimal)):
        return value
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


_PLAIN_NUMBER = re.compile(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def _document_cell(value: str, *, model_value: bool) -> Any:
    if model_value and _PLAIN_NUMBER.fullmatch(value):
        number = float(value)
        if math.isfinite(number):
            return number if any(character in value for character in ".eE") else int(value)
    return _safe_cell(value)


def _append_document_section(sheet: Any, section: dict[str, Any], depth: int = 0) -> None:
    kind = section["kind"]
    section_id = section["section_id"]
    sheet.append([
        "SECTION" if depth == 0 else "SUBSECTION",
        _safe_cell(section_id),
        _safe_cell(section["title"]),
        _safe_cell(section["page"]),
        _safe_cell(section["origin"]["kind"]),
    ])
    if kind == "columns":
        for column in section["items"]:
            for item in column:
                _append_document_section(sheet, item, depth + 1)
        return

    rows = _section_rows(section)
    if kind in {"table", "chart"} and rows:
        sheet.append(["HEADER", section_id, *(_safe_cell(value) for value in rows[0])])
        model_owned = section["origin"]["kind"] == "MODEL"
        for row in rows[1:]:
            sheet.append([
                "ROW",
                section_id,
                *(
                    _document_cell(value, model_value=model_owned and index > 0)
                    for index, value in enumerate(row)
                ),
            ])
    elif kind == "profile":
        for label, value in rows:
            sheet.append(["ROW", section_id, _safe_cell(label), _safe_cell(value)])
    elif kind == "list":
        for row in rows:
            sheet.append(["ITEM", section_id, _safe_cell(row[0])])
    elif rows:
        sheet.append(["CONTENT", section_id, _safe_cell(rows[0][0])])
    note = section.get("note")
    if note:
        sheet.append(["NOTE", section_id, _safe_cell(note)])


def render_frozen_xlsx(payload: dict[str, Any]) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    cover = workbook.active
    cover.title = "Cover"
    for row in (
        ("Pathway", payload["pathway"]),
        ("Content digest", payload["preview_digest"]),
        ("Input fingerprint", payload["input_fingerprint"]),
        ("Methodology build", payload["methodology"]["build_id"]),
    ):
        cover.append([_safe_cell(value) for value in row])

    reviewed = workbook.create_sheet("Reviewed Deliverable")
    register = workbook.create_sheet("Evidence Register")
    sections = _document_sections(payload)
    if sections is not None:
        register.append(["Source", "Blocks", "Claim"])
        reviewed.append(["Record", "Section ID", "Title / field", "Content", "Authority"])
        for section in sections:
            _append_document_section(reviewed, section)
        for section, _depth in _walk_sections(sections):
            if section["kind"] == "table" and section["title"] == "Evidence Register":
                for row in section["rows"]:
                    register.append([_safe_cell(value) for value in row])
    else:
        register.append(["Claim", "Source", "Blocks"])
        reviewed.append(["Block", "Kind", "Content"])
        for block in payload["content"]["blocks"]:
            text = block.get("text") or ""
            reviewed.append([_safe_cell(block["slot_id"]), _safe_cell(block["kind"]), _safe_cell(text)])
            if block["kind"] in {"GENERATED_METRIC", "SCENARIO_EXHIBIT"}:
                values = block.get("values") or (block.get("scenario") or {}).get("outputs") or {}
                for key, value in _flatten(values):
                    # Generated model numbers stay typed numbers, never text.
                    reviewed.append([_safe_cell(f"{block['slot_id']}::{key}"), "MODEL_VALUE",
                                     float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else _safe_cell(value)])
        for block in payload["content"]["blocks"]:
            for citation in block.get("citations") or []:
                register.append([
                    _safe_cell(citation["claim"]), _safe_cell(citation["source_id"]),
                    _safe_cell(", ".join(citation["block_ids"])),
                ])

    record = workbook.create_sheet("Revision Record")
    for row in (
        ("Draft version", payload["draft"]["version"]),
        ("Draft digest", payload["draft"]["digest"]),
        ("Content digest", payload["preview_digest"]),
    ):
        record.append([_safe_cell(value) for value in row])

    # Renders are content-addressed: identical payloads must yield identical
    # bytes, so nothing below the pin may read the clock (§12.4 spirit; the
    # freeze-conflict discriminator depends on it).
    from datetime import datetime

    workbook.properties.created = datetime(2026, 1, 1)
    workbook.properties.modified = datetime(2026, 1, 1)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return _deterministic_zip(output.getvalue())


def _deterministic_zip(content: bytes) -> bytes:
    """Re-pack an xlsx with sorted entries, fixed zip metadata, and pinned
    document timestamps — openpyxl stamps entry mtimes AND rewrites
    docProps/core.xml created/modified from the wall clock at save time."""
    import zipfile

    source = zipfile.ZipFile(io.BytesIO(content))
    output = io.BytesIO()
    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for name in sorted(source.namelist()):
                data = source.read(name)
                if name == "docProps/core.xml":
                    data = re.sub(
                        rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:(?:created|modified)>)",
                        rb"\g<1>2026-01-01T00:00:00Z\g<2>",
                        data,
                    )
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(info, data)
    finally:
        source.close()
    return output.getvalue()


def render_frozen_export(payload: dict[str, Any], format_name: str) -> bytes:
    if format_name == "md":
        return render_frozen_markdown(payload)
    if format_name == "pdf":
        return render_frozen_pdf(payload)
    if format_name == "xlsx":
        return render_frozen_xlsx(payload)
    raise ValueError(f"DELIVERABLE_EXPORT_UNAVAILABLE: unknown format {format_name!r}")
