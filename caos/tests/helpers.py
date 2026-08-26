from __future__ import annotations

import io


def make_upload(filename: str, content: bytes, content_type: str = "application/octet-stream"):
    from starlette.datastructures import Headers, UploadFile

    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def blank_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def xlsx_bytes(rows: list[list[object]], sheets: int = 1) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    for extra in range(sheets - 1):
        workbook.create_sheet(f"s{extra}")
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
