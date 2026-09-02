"""Source ingestion contracts (invariant 1 boundary): ported per TEST_INVENTORY briefs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import HTTPException

from caos.sources import domain as sources_domain
from caos.sources.domain import Vault, ingest_upload

from helpers import blank_pdf_bytes, make_upload, xlsx_bytes


@pytest.fixture()
def vault(settings):
    return Vault(settings)


@pytest.fixture()
def case_id(store):
    return store.create_case("Case", "Issuer", "Services", "analyst")["id"]


async def ingest(store, vault, case_id, filename, content, content_type="application/octet-stream"):
    upload = make_upload(filename, content, content_type)
    try:
        return await ingest_upload(
            store, vault, case_id, "analyst", upload, max_bytes=vault.settings.max_upload_bytes,
        )
    finally:
        await upload.close()


async def assert_rejected(store, vault, case_id, filename, content, status=422):
    before = store.current_source_set(case_id)
    with pytest.raises(HTTPException) as excinfo:
        await ingest(store, vault, case_id, filename, content)
    assert excinfo.value.status_code == status
    assert store.current_source_set(case_id) == before, "rejection must leave no source-set delta"
    return excinfo.value


async def test_zero_byte_source_is_rejected_before_source_set_creation(store, vault, case_id):
    await assert_rejected(store, vault, case_id, "empty.txt", b"")
    assert store.list_sources(case_id) == []


async def test_evidence_free_text_csv_and_xlsx_are_rejected(store, vault, case_id):
    await assert_rejected(store, vault, case_id, "ws.txt", b"   \n\t\n")
    await assert_rejected(store, vault, case_id, "ws.md", b" \n \n")
    await assert_rejected(store, vault, case_id, "empty.csv", b",,,\n,,,\n")
    await assert_rejected(store, vault, case_id, "blank.xlsx", xlsx_bytes([[None, None]]))


@pytest.mark.parametrize("payload", [
    b'{"amount":NaN}', b'{"amount":Infinity}', b'{"amount":-Infinity}',
    b'{"amount":1e999}', b'{"amount":-1e999}',
])
async def test_non_finite_json_values_are_rejected(store, vault, case_id, payload):
    await assert_rejected(store, vault, case_id, "figures.json", payload)


@pytest.mark.parametrize("payload", [
    b'{"a":1,"a":2}', b'{"outer":{"a":1,"a":2}}',
])
async def test_duplicate_json_keys_are_rejected(store, vault, case_id, payload):
    await assert_rejected(store, vault, case_id, "dupe.json", payload)


@pytest.mark.parametrize("payload", [b"{}", b"[]", b'""', b'"   "', b"null"])
async def test_evidence_free_json_values_are_rejected(store, vault, case_id, payload):
    await assert_rejected(store, vault, case_id, "empty.json", payload)


async def test_json_scalar_values_are_accepted(store, vault, case_id):
    for name, payload in (("zero.json", b"0"), ("false.json", b"false"), ("big.json", b"1e308")):
        result = await ingest(store, vault, case_id, name, payload)
        assert result["sha256"]
    assert store.current_source_set(case_id)["version"] == 3


@pytest.mark.parametrize("name", ["bad.txt", "bad.md", "bad.csv"])
async def test_non_utf8_text_sources_are_rejected(store, vault, case_id, name):
    await assert_rejected(store, vault, case_id, name, b"\xff\xfe\x00bad")


async def test_invalid_pdf_is_rejected(store, vault, case_id):
    await assert_rejected(store, vault, case_id, "fake.pdf", b"not a pdf at all")


async def test_valid_no_text_pdf_is_accepted(store, vault, case_id):
    result = await ingest(store, vault, case_id, "scan.pdf", blank_pdf_bytes(), "application/pdf")
    assert result["source_set"]["version"] == 1
    assert sources_domain.pathway_fit(store, case_id)["fit"] == "READY"


async def test_pathway_fit_never_reads_the_blocks_column(store, vault, case_id):
    """pathway_fit runs once per case on the case-list route, so what it reads is
    a performance contract, not an implementation detail. list_sources selects the
    whole source row - blocks column included - which made GET /api/cases 12x
    slower and made its cost scale with evidence volume rather than case count.
    Fail loudly if the cheap read is ever swapped back for the wide one."""
    await ingest(store, vault, case_id, "doc.txt", b"Revenue rose 12 percent.\n", "text/plain")

    def refuse(*args, **kwargs):
        raise AssertionError(
            "pathway_fit must use list_source_filenames; list_sources carries every "
            "evidence block of every source into a route that needs only suffixes"
        )

    store.list_sources = refuse
    assert sources_domain.pathway_fit(store, case_id)["fit"] == "READY"
    assert sources_domain.pathway_fit(store, case_id)["source_count"] == 1


async def test_non_empty_xlsx_is_accepted(store, vault, case_id):
    result = await ingest(store, vault, case_id, "book.xlsx", xlsx_bytes([["Revenue", 100]]))
    assert result["source_set"]["version"] == 1


async def test_unsupported_type_is_rejected_415(store, vault, case_id):
    await assert_rejected(store, vault, case_id, "prog.exe", b"MZ", status=415)


async def test_oversize_upload_is_rejected_413(store, vault, case_id, settings):
    small = Vault(type(settings)(storage_dir=settings.storage_dir, max_upload_bytes=10))
    upload = make_upload("big.txt", b"x" * 11)
    try:
        with pytest.raises(HTTPException) as excinfo:
            await ingest_upload(store, small, case_id, "analyst", upload, max_bytes=10)
    finally:
        await upload.close()
    assert excinfo.value.status_code == 413


async def test_xlsx_extraction_caps_fail_closed(store, vault, case_id, monkeypatch):
    monkeypatch.setattr(sources_domain, "MAX_XLSX_EXTRACT_ROWS", 2)
    await assert_rejected(store, vault, case_id, "rows.xlsx", xlsx_bytes([["a"], ["b"], ["c"]]))
    monkeypatch.setattr(sources_domain, "MAX_XLSX_EXTRACT_ROWS", 25_000)
    monkeypatch.setattr(sources_domain, "MAX_XLSX_EXTRACT_WORKSHEETS", 1)
    await assert_rejected(store, vault, case_id, "sheets.xlsx", xlsx_bytes([["a"]], sheets=2))


async def test_over_wide_line_is_split_into_bounded_blocks_rather_than_refused(store, vault, case_id):
    """An inline-XBRL filing is a whole document on one line. Refusing it loses
    a real filing over its whitespace, so the extractor splits: every block
    stays quotable, and no character of the evidence is dropped on the way."""
    line = "".join(f"fact-{index:06d} " for index in range(6_000))
    assert len(line) > sources_domain.MAX_BLOCK_CHARS
    result = await ingest(store, vault, case_id, "inline.txt", line.encode())

    blocks = result["blocks"]
    assert len(blocks) > 1
    assert max(len(block["text"]) for block in blocks) <= sources_domain.MAX_BLOCK_CHARS
    assert "".join(block["text"] for block in blocks) == line, "split dropped evidence"
    assert [block["locator"] for block in blocks] == [
        {"line": 1, "part": part} for part in range(1, len(blocks) + 1)
    ]
    assert {block["extractor_version"] for block in blocks} == {"builtin-v2"}


async def test_large_document_keeps_block_count_inside_the_run_manifest_ceiling(store, vault, case_id):
    """A 300-page credit agreement indexed line by line costs more context than
    a module is given to think with — the run manifest carries one row per block
    into every module prompt. Block count therefore has to stay bounded whatever
    the document's size, and several such documents must still pin one run."""
    from caos.engine.budget import MAX_MANIFEST_BLOCKS, bound_manifest

    paragraph = "The Borrower shall not permit the Total Net Leverage Ratio to exceed 4.50:1.00. "
    document = "\n".join(f"{index}. {paragraph * 12}" for index in range(12_000))
    assert len(document) > 8_000_000

    sources = []
    for copy in range(3):
        body = f"{copy}{document}"
        source = await ingest(store, vault, case_id, f"agreement-{copy}.txt", body.encode())
        blocks = source["blocks"]
        # ~585 blocks for ~11.7 MB: count is set by MAX_BLOCK_CHARS, not by the
        # 12,000 lines, so it does not track the document's length.
        assert len(blocks) < len(document.splitlines()) / 15, "block count tracked document size"
        assert max(len(block["text"]) for block in blocks) <= sources_domain.MAX_BLOCK_CHARS
        assert "\n".join(block["text"] for block in blocks) == body, "grouping dropped evidence"
        assert [block["locator"]["lines"][0] for block in blocks] == \
            sorted(block["locator"]["lines"][0] for block in blocks), "line ranges are out of order"
        sources.append(source)

    manifest = [
        {
            "source_id": source["id"], "sha256": source["sha256"],
            "filename": source["filename"], "media_type": source["media_type"],
            "blocks": [
                {key: block.get(key) for key in ("block_id", "locator", "extractor_version", "confidence")}
                for block in source["blocks"]
            ],
        }
        for source in sources
    ]
    rows = len(manifest) + sum(len(entry["blocks"]) for entry in manifest)
    assert rows <= MAX_MANIFEST_BLOCKS
    bound_manifest(manifest)  # the ceiling that used to fail the run before its first provider call


async def test_text_beyond_the_extraction_ceiling_is_still_refused(store, vault, case_id, monkeypatch):
    """Bounded blocks are not an excuse to accept an unbounded document."""
    monkeypatch.setattr(sources_domain, "MAX_SOURCE_TEXT", 100)
    await assert_rejected(store, vault, case_id, "huge.txt", b"x " * 200)


async def test_eicar_content_is_rejected(store, vault, case_id):
    await assert_rejected(store, vault, case_id, "sig.txt", b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")


async def test_duplicate_active_content_rejected_and_withdrawal_reopens(store, vault, case_id):
    first = await ingest(store, vault, case_id, "doc.txt", b"material evidence")
    assert first["source_set"]["version"] == 1
    error = await assert_rejected(store, vault, case_id, "again.txt", b"material evidence", status=409)
    assert "already active" in str(error.detail)
    assert store.current_source_set(case_id)["version"] == 1
    assert store.withdraw(case_id, first["id"], "analyst") is not None
    assert store.current_source_set(case_id)["version"] == 2
    third = await ingest(store, vault, case_id, "doc2.txt", b"material evidence")
    assert third["source_set"]["version"] == 3
    assert store.current_source_set(case_id)["source_ids"] == [third["id"]]


async def test_ingestion_rolls_back_atomically_when_persistence_fails(store, vault, case_id, monkeypatch):
    audit_before = store.audit_trail()

    def failing_audit(conn, action, actor, **details):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(store, "_audit", failing_audit)
    with pytest.raises(RuntimeError):
        await ingest(store, vault, case_id, "doc.txt", b"good evidence")
    monkeypatch.undo()
    assert store.list_sources(case_id) == []
    assert store.current_source_set(case_id) is None
    assert store.audit_trail() == audit_before, "failed write must append no audit"
    recovered = await ingest(store, vault, case_id, "doc.txt", b"good evidence")
    assert recovered["source_set"]["version"] == 1


async def test_public_source_reads_hide_storage_private_fields(store, vault, case_id):
    result = await ingest(store, vault, case_id, "doc.txt", b"the evidence")
    assert "vault_path" not in result
    listed = store.list_sources(case_id)[0]
    assert "vault_path" not in listed and "withdrawn_at" not in listed
    fetched = store.get_source(result["id"])
    assert "vault_path" not in fetched
    raw = store.read_source_bytes(result["id"], limit=1024)
    assert raw == b"the evidence"


async def test_existing_source_vault_corruption_is_never_reused_or_read(
    store,
    vault,
    case_id,
):
    content = b"the evidence"
    result = await ingest(store, vault, case_id, "doc.txt", content)
    private = store.get_source_private(result["id"])
    path = Path(private["vault_path"])
    path.write_bytes(b"bad evidence")

    with pytest.raises(ValueError, match="source vault integrity mismatch"):
        vault.verify(private)
    with pytest.raises(ValueError, match="existing source identity mismatch"):
        vault.put(content, hashlib.sha256(content).hexdigest())
    with pytest.raises(ValueError, match="SOURCE_BYTES_INTEGRITY_MISMATCH"):
        store.read_source_bytes(result["id"], limit=1024)
