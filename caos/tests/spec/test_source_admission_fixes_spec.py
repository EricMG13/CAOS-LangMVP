"""Source admission behaviours the 2026-09-06 adversarial review found missing
(W1, W2, W4), each pinned by the smallest test that fails if the defect returns:

- W1: `prepare_upload` and the intake keep the event loop free while a document
  is scanned, extracted and vaulted (DECISIONS §10.8, no event-loop starvation);
- W2: a refused intake pack — and a failed single-source commit — leaves no vault
  file the store does not reference, while bytes another case admitted survive
  (DECISIONS §14.17, admit every file or none);
- W4: the grouped block count is bounded for any line shape, so a run of several
  worst-shape 12 MB documents still pins inside `MAX_MANIFEST_BLOCKS`, while the
  small-document path and the `builtin-v2` locator shape stay exactly as pinned.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import sys
import time
from pathlib import Path

import pytest
import sqlalchemy as sa

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from helpers import make_upload  # noqa: E402

from test_intake_spec import (  # noqa: E402
    GOLDEN_PACK,
    OTHER_ANALYST,
    TEXT,
    annual_report,
    guidance,
    submit,
)

EXE = ("notes.exe", b"MZ\x90\x00", "application/octet-stream")


# --- helpers ------------------------------------------------------------------------


def _vault_files(settings) -> list[Path]:
    root = settings.storage_dir / "sources"
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.exists() else []


def _referenced(store) -> set[Path]:
    from caos.storage.store import sources

    with store.engine.connect() as conn:
        rows = conn.execute(sa.select(sources.c.vault_path)).scalars().all()
    return {Path(row) for row in rows if row}


def _assert_no_orphan(settings, store) -> None:
    on_disk = set(_vault_files(settings))
    assert on_disk <= _referenced(store), f"vault files nothing references: {sorted(on_disk - _referenced(store))}"


async def _count_ticks(coroutine, *, period: float = 0.02) -> tuple[object, int]:
    """Run `coroutine` while a sibling coroutine ticks every `period` seconds;
    the tick count is how often the loop got a turn during the call."""
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(period)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        result = await coroutine
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    return result, ticks


def _slow_extractor(monkeypatch, seconds: float = 0.5):
    from caos.sources import domain

    real = domain.extract_blocks

    def slow(filename: str, content: bytes):
        time.sleep(seconds)
        return real(filename, content)

    monkeypatch.setattr(domain, "extract_blocks", slow)


# --- W1: admission does not starve the loop --------------------------------------------


async def test_prepare_upload_keeps_the_event_loop_free_while_it_extracts(settings, monkeypatch):
    """A 2.4 MB workbook inside every ceiling froze the instance for ~6 s and timed
    out the readiness probe: the scan, extraction and fsync ran on the loop. With
    a 0.5 s extractor the loop must still turn every 20 ms."""
    from caos.sources.domain import Vault, prepare_upload

    _slow_extractor(monkeypatch)
    upload = make_upload("doc.txt", b"Revenue rose 12 percent.\n", "text/plain")
    started = time.monotonic()
    try:
        prepared, ticks = await _count_ticks(prepare_upload(Vault(settings), upload, max_bytes=1024))
    finally:
        await upload.close()
    assert time.monotonic() - started < 2.0
    assert ticks >= 10, f"the loop turned {ticks} times during a 0.5 s admission"
    assert prepared["sha256"] == hashlib.sha256(b"Revenue rose 12 percent.\n").hexdigest()
    assert prepared["blocks"][0]["text"] == "Revenue rose 12 percent."


async def test_the_intake_keeps_the_event_loop_free_across_a_whole_pack(store, settings, monkeypatch):
    """The intake loops up to 40 files through admission and then commits the
    pack: the whole submission, admission and commit included, has to leave the
    loop serving."""
    from caos.intake.service import IntakeService

    _slow_extractor(monkeypatch, seconds=0.25)
    uploads = [make_upload(name, content, content_type) for name, content, content_type in GOLDEN_PACK[:2]]
    service = IntakeService(store=store, engine=None, settings=settings)
    started = time.monotonic()
    try:
        (intake, created), ticks = await _count_ticks(service.submit(actor="analyst", uploads=uploads, case_id=None))
    finally:
        for upload in uploads:
            await upload.close()
    assert time.monotonic() - started < 2.0
    assert created and intake["status"] == "execution_unavailable"
    assert ticks >= 10, f"the loop turned {ticks} times during a 0.5 s intake"
    assert len(store.list_sources(intake["case_id"])) == 2
    _assert_no_orphan(settings, store)


# --- W2: a refused pack leaves no unreferenced vault file -----------------------------------


def test_a_refused_pack_leaves_no_vault_file_behind(client, store, settings):
    """Every refusal after preparation: one refused file (INTAKE_ADMISSION_REFUSED),
    two documents under one name (INTAKE_SOURCE_CONFLICT), and two issuers
    (INTAKE_ISSUER_AMBIGUOUS, refused after classification). Before the fix each
    left every prepared document in the content-addressed vault with no row."""
    refused = submit(client, [*GOLDEN_PACK, EXE])
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "INTAKE_ADMISSION_REFUSED"
    assert _vault_files(settings) == [], "the three admissible documents were vaulted and then abandoned"

    conflict = submit(client, [
        ("northstar-10k-fy2024.txt", annual_report(), TEXT),
        ("northstar-10k-fy2024.txt", annual_report(restated=True), TEXT),
    ])
    assert conflict.status_code == 422 and conflict.json()["detail"]["code"] == "INTAKE_SOURCE_CONFLICT"
    assert _vault_files(settings) == []

    ambiguous = submit(client, [
        ("northstar-10k.txt", annual_report(), TEXT),
        ("acme-10k.txt", annual_report("Acme Corporation"), TEXT),
    ])
    assert ambiguous.status_code == 422 and ambiguous.json()["detail"]["code"] == "INTAKE_ISSUER_AMBIGUOUS"
    assert _vault_files(settings) == []
    assert store.list_cases("analyst") == [] and _referenced(store) == set()
    assert [event["action"] for event in store.audit_trail()] == ["intake.refused"] * 3


def test_bytes_another_case_admitted_survive_a_refused_pack_that_shares_them(client, store, settings):
    """Content addressing means one file can belong to several cases: a refused
    pack must drop only what nothing references."""
    admitted = submit(client, GOLDEN_PACK)
    assert admitted.status_code == 201, admitted.text
    files = _vault_files(settings)
    assert len(files) == 3 and set(files) == _referenced(store)

    shared = ("northstar-10k-fy2024.txt", annual_report(), TEXT)
    refused = submit(client, [shared, ("guidance.txt", guidance(), TEXT), EXE], headers=OTHER_ANALYST)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "INTAKE_ADMISSION_REFUSED"
    assert _vault_files(settings) == files, "the shared document survived; the guidance note did not"

    conflict = submit(client, [shared, ("northstar-10k-fy2024.txt", annual_report(restated=True), TEXT)], headers=OTHER_ANALYST)
    assert conflict.status_code == 422 and conflict.json()["detail"]["code"] == "INTAKE_SOURCE_CONFLICT"
    assert _vault_files(settings) == files

    from caos.sources.domain import Vault

    ten_k = next(document for document in admitted.json()["documents"] if document["filename"] == shared[0])
    assert Vault(settings).verify(store.get_source_private(ten_k["source_id"])) == annual_report()
    _assert_no_orphan(settings, store)


def test_a_refusal_at_commit_unpublishes_only_what_this_pack_published(client, store, settings, monkeypatch):
    """The last refusal is the store's own (`source content already active`,
    raised inside `admit_intake`): by then the pack's files are at their content
    addresses, so the ones this pack put there come out again and the ones
    another case owns stay."""
    admitted = submit(client, GOLDEN_PACK)
    assert admitted.status_code == 201, admitted.text
    files = _vault_files(settings)

    def refuse(**_kwargs):
        raise ValueError("source content already active")

    monkeypatch.setattr(store, "admit_intake", refuse)
    refused = submit(client, [("northstar-10k-fy2024.txt", annual_report(), TEXT), ("guidance.txt", guidance(), TEXT)],
                     headers=OTHER_ANALYST)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "INTAKE_SOURCE_CONFLICT"
    assert _vault_files(settings) == files, "the guidance note was unpublished; the shared 10-K stayed"

    def crash(**_kwargs):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(store, "admit_intake", crash)
    with pytest.raises(RuntimeError):
        submit(client, [("guidance.txt", guidance(), TEXT)], headers=OTHER_ANALYST)
    assert _vault_files(settings) == files
    monkeypatch.undo()

    recovered = submit(client, [("guidance.txt", guidance(), TEXT)], headers=OTHER_ANALYST)
    assert recovered.status_code == 201, recovered.text
    assert len(_vault_files(settings)) == 4
    _assert_no_orphan(settings, store)


async def test_a_failed_single_source_commit_leaves_no_vault_file(store, settings, monkeypatch):
    """The single-source route shares the seam: a persistence failure after the
    bytes reached their content address takes them out again, and the retry
    re-admits the same bytes."""
    from caos.sources.domain import Vault, ingest_upload

    case_id = store.create_case("Case", "Issuer", "Services", "analyst")["id"]
    vault = Vault(settings)

    def failing_audit(conn, action, actor, **details):
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(store, "_audit", failing_audit)
    upload = make_upload("doc.txt", b"good evidence")
    try:
        with pytest.raises(RuntimeError):
            await ingest_upload(store, vault, case_id, "analyst", upload, max_bytes=1024)
    finally:
        await upload.close()
    assert _vault_files(settings) == [] and store.list_sources(case_id) == []
    monkeypatch.undo()

    upload = make_upload("doc.txt", b"good evidence")
    try:
        saved = await ingest_upload(store, vault, case_id, "analyst", upload, max_bytes=1024)
    finally:
        await upload.close()
    assert saved["source_set"]["version"] == 1
    assert len(_vault_files(settings)) == 1
    assert vault.verify(store.get_source_private(saved["id"])) == b"good evidence"


# --- W4: the grouped block count is bounded for any line shape -------------------------------


def _document(line_length: int, total: int) -> str:
    """`total` characters of `line_length`-character lines, every character
    evidence (no blank line, no trailing newline)."""
    lines: list[str] = []
    size = 0
    index = 0
    while size < total:
        stem = f"{index:07d} "
        body = stem + ("x" * (line_length - len(stem)))
        room = total - size - (1 if lines else 0)
        if room <= 0:
            break
        line = body[:room]
        lines.append(line)
        size += len(line) + (1 if len(lines) > 1 else 0)
        index += 1
    return "\n".join(lines)


def _assert_evidence_preserved(text: str, blocks: list[dict]) -> None:
    """Every character of every non-blank line is in some block, in order, with
    nothing repeated: the blocks tile the document except for line breaks."""
    position = 0
    for block in blocks:
        while position < len(text) and text[position] == "\n":
            position += 1
        assert text.startswith(block["text"], position), f"{block['block_id']} is not the next slice of the document"
        position += len(block["text"])
    assert text[position:].strip() == "", "the tail of the document is in no block"


def _grouped_width(text: str) -> int:
    from caos.sources import domain

    return min(domain.MAX_BLOCK_CHARS,
               max(domain.TARGET_BLOCK_CHARS, math.ceil(len(text) / domain.MAX_BLOCKS_PER_SOURCE)))


def _bound(text: str) -> int:
    from caos.sources import domain

    width = _grouped_width(text)
    return math.ceil(len(text) / (width - width // domain.BLOCK_SLACK_DIVISOR)) + 1


@pytest.mark.parametrize("line_length, total", [
    pytest.param(10_000, 12_000_000, id="12MB-of-10k-lines"),
    pytest.param(12_000, 12_000_000, id="12MB-of-12k-lines"),
    pytest.param(19_000, 12_000_000, id="12MB-of-19k-lines"),
    pytest.param(20_000, 12_000_000, id="12MB-of-20k-lines"),
    pytest.param(1_010, 12_000_000, id="12MB-of-1k-lines"),
    pytest.param(2_100, 1_300_000, id="1.3MB-of-2100-char-paragraphs"),
    pytest.param(3_000, 1_300_000, id="1.3MB-of-3000-char-paragraphs"),
    pytest.param(50, 1_500_000, id="1.5MB-of-50-char-lines"),
])
def test_grouped_block_count_is_bounded_for_any_line_shape(line_length, total):
    """Before the fix any line wider than the room left in a block flushed the
    block, so lines in (width/2, width] became their own blocks: 12 MB of
    10-20k-character lines was 1 199 blocks and 1.3 MB of 2 100-character
    paragraphs was 620. Now no block but the last is more than width/16 short."""
    from caos.sources import domain

    text = _document(line_length, total)
    assert len(text) <= domain.MAX_SOURCE_TEXT and len(text) >= total - line_length
    blocks = domain.pack_blocks(text)

    assert len(blocks) <= _bound(text), (len(blocks), _bound(text))
    assert max(len(block["text"]) for block in blocks) <= domain.MAX_BLOCK_CHARS
    assert max(len(block["text"]) for block in blocks) <= _grouped_width(text)
    _assert_evidence_preserved(text, blocks)
    assert [block["block_id"] for block in blocks] == [f"b{index:05d}" for index in range(1, len(blocks) + 1)]
    assert {block["extractor_version"] for block in blocks} == {"builtin-v2"}
    line_count = text.count("\n") + 1
    for block in blocks:
        first, last = block["locator"]["lines"]
        assert set(block["locator"]) == {"lines"} and 1 <= first <= last <= line_count
    starts = [block["locator"]["lines"][0] for block in blocks]
    assert starts == sorted(starts)


def test_two_and_three_worst_shape_documents_still_pin_one_run():
    """The run manifest carries one row per block of every pinned source into
    every module prompt; the 2 000-row ceiling used to fail two 12 MB documents
    of 10k-character lines (2 × 1 199 + 2) as AGENT_BUDGET_EXCEEDED before the
    first provider call."""
    from caos.engine.budget import MAX_MANIFEST_BLOCKS, bound_manifest
    from caos.sources import domain

    text = _document(10_000, 12_000_000)
    blocks = domain.pack_blocks(text)
    assert len(blocks) <= math.ceil(len(text) / domain.MAX_BLOCK_CHARS) + 1 == 601

    def entry(index: int) -> dict:
        return {"source_id": f"src-{index}", "filename": f"filing-{index}.txt", "media_type": "text/plain",
                "sha256": hashlib.sha256(f"{index}".encode()).hexdigest(),
                "blocks": [{key: block[key] for key in ("block_id", "locator", "extractor_version", "confidence")}
                           for block in blocks]}

    for copies in (2, 3):
        manifest = [entry(index) for index in range(copies)]
        assert copies + copies * len(blocks) <= MAX_MANIFEST_BLOCKS
        bound_manifest(manifest)


def test_the_small_document_path_is_byte_identical_to_the_line_extractor():
    """One block per non-blank line, `builtin-v1`, `{"line": n}` locators and the
    line's own id — the shape every ordinary document has carried since the
    first ingestion contract."""
    from caos.sources import domain

    lines = [f"line {index} of an ordinary document" for index in range(1, domain.MAX_BLOCKS_PER_SOURCE + 1)]
    text = "\n".join(lines[:5]) + "\n\n" + "\n".join(lines[5:])
    blocks = domain.pack_blocks(text)
    assert len(blocks) == domain.MAX_BLOCKS_PER_SOURCE
    expected_lines = [index for index in range(1, domain.MAX_BLOCKS_PER_SOURCE + 2) if index != 6]
    assert [block["locator"] for block in blocks] == [{"line": index} for index in expected_lines]
    assert [block["block_id"] for block in blocks] == [f"b{index:05d}" for index in expected_lines]
    assert [block["text"] for block in blocks] == lines
    assert {block["extractor_version"] for block in blocks} == {"builtin-v1"}


async def test_failed_pack_cannot_delete_a_concurrent_intakes_shared_source(store, settings):
    from caos.intake.service import IntakeRefused, IntakeService
    from caos.sources.domain import Vault

    ready, release = asyncio.Event(), asyncio.Event()

    class DelayedEmptyUpload:
        filename = "empty.txt"
        content_type = "text/plain"

        async def read(self, _limit):
            ready.set()
            await release.wait()
            return b""

    service = IntakeService(store=store, engine=None, settings=settings)
    first = make_upload("annual.txt", annual_report())
    second = make_upload("annual.txt", annual_report())
    failed = asyncio.create_task(service.submit(actor="first", uploads=[first, DelayedEmptyUpload()], case_id=None))
    try:
        await asyncio.wait_for(ready.wait(), 5)
        admitted, created = await service.submit(actor="second", uploads=[second], case_id=None)
        assert created
    finally:
        release.set()
        with pytest.raises(IntakeRefused):
            await failed
        await first.close()
        await second.close()
    source = store.list_sources(admitted["case_id"])[0]
    assert Vault(settings).verify(store.get_source_private(source["id"])) == annual_report()
    _assert_no_orphan(settings, store)


async def test_post_commit_intake_failure_preserves_committed_bytes(store, settings, monkeypatch):
    from caos.intake.service import IntakeService
    from caos.sources.domain import Vault

    service = IntakeService(store=store, engine=None, settings=settings)

    def fail_after_commit(*_args):
        raise RuntimeError("post-commit failure")

    monkeypatch.setattr(service, "_import_market_marks", fail_after_commit)
    upload = make_upload("annual.txt", annual_report())
    try:
        with pytest.raises(RuntimeError, match="post-commit"):
            await service.submit(actor="analyst", uploads=[upload], case_id=None)
    finally:
        await upload.close()
    case = store.list_cases("analyst")[0]
    source = store.list_sources(case["id"])[0]
    assert Vault(settings).verify(store.get_source_private(source["id"])) == annual_report()
    _assert_no_orphan(settings, store)


async def test_concurrent_identical_intakes_converge_while_commit_is_slow(store, settings, monkeypatch):
    from caos.intake.service import IntakeService

    service = IntakeService(store=store, engine=None, settings=settings)
    original = store.admit_intake

    def slow_commit(**kwargs):
        time.sleep(0.1)
        return original(**kwargs)

    monkeypatch.setattr(store, "admit_intake", slow_commit)
    uploads = [make_upload("annual.txt", annual_report()) for _ in range(2)]
    try:
        results = await asyncio.gather(*(service.submit(actor="analyst", uploads=[upload], case_id=None) for upload in uploads))
    finally:
        for upload in uploads:
            await upload.close()
    assert len({record["id"] for record, _created in results}) == 1
    assert sorted(created for _record, created in results) == [False, True]
    assert len(store.list_cases("analyst")) == 1
    _assert_no_orphan(settings, store)


async def test_single_upload_rechecks_standing_at_commit(store, settings, monkeypatch):
    from fastapi import HTTPException
    from caos.sources.domain import Vault, ingest_upload
    from caos.storage.store import case_members

    case = store.create_case("Case", "Issuer", "Services", "analyst")
    original = store.ingest

    def revoke_then_commit(source, actor):
        with store.engine.begin() as conn:
            conn.execute(sa.update(case_members).where(case_members.c.case_id == case["id"]).values(role="READER"))
        return original(source, actor)

    monkeypatch.setattr(store, "ingest", revoke_then_commit)
    upload = make_upload("annual.txt", annual_report())
    try:
        with pytest.raises(HTTPException) as refusal:
            await ingest_upload(store, Vault(settings), case["id"], "analyst", upload, max_bytes=1024)
        assert refusal.value.status_code == 403
    finally:
        await upload.close()
    assert store.list_sources(case["id"]) == [] and _vault_files(settings) == []
