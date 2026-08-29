"""Every route driven on documents the SEC and the issuers actually served.

The corpus is real files — annual reports, shareholder letters, complete EDGAR
submissions, XBRL company facts — downloaded once by `corpus/fetch.sh` and
pushed through the real upload endpoint. Nothing here is synthesised, and
nothing is reshaped on the way in: what the boundary sees is what the issuer
filed. The suite skips until the corpus is on disk; it never touches the
network itself.

What it asserts, which is what the `corpus_run` marker is for (property
assertions, no numeric oracle):

  * every real document is either admitted with extracted blocks or refused
    with a typed status that leaves no source-set delta (invariants 1, 2);
  * every route the engine will run reaches `succeeded` on that real evidence,
    keeps the shape `compiled_route` pins, and cites only evidence the host
    delivered (invariants 9, 10);
  * the routes the bundle compiles but the MVP cut excludes refuse by name
    without pinning anything;
  * a real 300-page annual report runs at full depth — bounded block packing
    keeps its source manifest inside the run ceiling (invariant 8) while the
    evidence itself stays readable.

Default is the smoke subset: the cheap end of the corpus and one pathway.
`CORPUS_FULL=1` classifies every document and runs every live route.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.contracts import INTERNAL_PATHWAYS, PATHWAYS, Depth  # noqa: E402
from caos.engine.budget import MAX_MANIFEST_BLOCKS  # noqa: E402
from caos.engine.graphs import compiled_route  # noqa: E402
from caos.engine.runtime import MVP_PATHWAYS, EngineError  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus"
DOCUMENTS = CORPUS / "documents"
SOURCES = CORPUS / "sources.txt"
FETCH = 'SEC_USER_AGENT="Your Name you@example.com" caos/tests/corpus/fetch.sh'

MEDIA_TYPES = {".pdf": "application/pdf", ".json": "application/json", ".txt": "text/plain"}

# Four real issuers, named rather than picked by size so a failure names a
# document rather than a slice. Small enough that the route matrix stays quick;
# the large documents are exercised by the annual-report test below.
SEED = (
    "THC_8-K_2016-03-09.txt",
    "KHC_8-K_2015-06-18.txt",
    "CCL_8-K_2016-04-13.txt",
    "BRK_shareholder_letter_2023.pdf",
)
# A real 300-page annual report: 3 MB of PDF, ~1 MB of extracted text.
ANNUAL_REPORT = "BRK_annual_report_2023.pdf"

CANONICAL_BODY = "\n".join(
    f"## {heading}\n\nscripted"
    for heading in ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry", "Gaps & Conflicts", "QA Validation")
)


def _corpus() -> list[Path]:
    """Downloaded documents, smallest first, so the smoke subset is a prefix."""
    if not SOURCES.is_file():
        return []
    names = [
        line.split()[0]
        for line in SOURCES.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    present = [DOCUMENTS / name for name in names if (DOCUMENTS / name).is_file()]
    return sorted(present, key=lambda path: path.stat().st_size)


DOCS = _corpus()
CORPUS_FULL = os.environ.get("CORPUS_FULL") == "1"

# Extraction cost, not a product limit: the multi-megabyte PDFs take seconds
# each in the extractor, so the per-PR smoke run classifies the cheap end of
# the corpus and CORPUS_FULL=1 classifies all of it.
SMOKE_MAX_BYTES = 1_000_000
INGEST_DOCS = DOCS if CORPUS_FULL else [doc for doc in DOCS if doc.stat().st_size <= SMOKE_MAX_BYTES]

pytestmark = [
    pytest.mark.corpus_run,
    pytest.mark.skipif(not DOCS, reason=f"corpus not downloaded — run: {FETCH}"),
]


# The bundle compiles sixteen routes; the engine runs the MVP cut. Both halves
# are covered — the live ones by execution, the cut ones by refusal.
GOLDEN = [(pathway, depth) for pathway in INTERNAL_PATHWAYS for depth in (Depth.SCREEN, Depth.FULL)]
LIVE_ROUTES = [route for route in GOLDEN if route[0] in MVP_PATHWAYS]
CUT_ROUTES = [route for route in GOLDEN if route[0] not in MVP_PATHWAYS]

# Per-PR smoke: one pathway across both depths, which is the deterministic path
# and the agent path — where a real document breaks something, it breaks it on
# one of those two. CORPUS_FULL=1 runs every live route.
ROUTES = LIVE_ROUTES if CORPUS_FULL else [route for route in LIVE_ROUTES if route[0] == "FULL_CREDIT"]


def route_ids(routes) -> list[str]:
    return [f"{pathway}-{depth.value}" for pathway, depth in routes]


class CorpusProvider:
    """Provider-port double: one read_evidence call, then the canonical
    envelope, for as many agent modules as the route happens to hold.

    These tests are about the host path — real bytes through ingestion,
    pinning and citation validation — so the model's prose is scripted while
    its citations point at a block the host really delivered. `bind` is called
    after seeding, because the block id is not known until the real document
    has been through the real extractor.
    """

    def __init__(self) -> None:
        self.source_id = ""
        self.block_id = ""
        self.calls = 0

    def bind(self, source_id: str, block_id: str) -> None:
        self.source_id, self.block_id = source_id, block_id

    def count_tokens(self, request) -> int:
        return 1_000

    def create_message(self, request):
        from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

        assert self.source_id, "CorpusProvider used before bind()"
        self.calls += 1
        if self.calls % 2:
            block = ProviderBlock(type="tool_use", id="tool-1", name="read_evidence",
                                  input={"source_id": self.source_id, "block_ids": [self.block_id]})
            return ProviderMessage(content=[block], stop_reason="tool_use",
                                   usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
                                   request_id="req-corpus-tool")
        envelope = json.dumps({
            "markdown": CANONICAL_BODY,
            "evidence_refs": [{"source_id": self.source_id, "block_id": self.block_id}],
            "lineage_counts": {"directly_sourced": 1},
            "fields_present": 1,
            "fields_total": 1,
            "source_gate": "pass",
        })
        return ProviderMessage(content=[ProviderBlock(type="text", text=envelope)], stop_reason="end_turn",
                               usage=ProviderUsage(input_tokens=1_000, output_tokens=200),
                               request_id="req-corpus-final")


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)


@pytest.fixture()
def store(tmp_path: Path) -> DomainStore:
    return DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")


@pytest.fixture()
def provider() -> CorpusProvider:
    return CorpusProvider()


@pytest.fixture()
def engine(tmp_path: Path, settings: Settings, store: DomainStore, provider: CorpusProvider):
    from caos.engine.runtime import Engine

    return Engine.create(settings=settings, store=store,
                         checkpoint_path=tmp_path / "checkpoints.db", provider=provider)


@pytest.fixture()
def client(settings: Settings, store: DomainStore, engine):
    from fastapi.testclient import TestClient

    from caos.api import create_app

    return TestClient(create_app(settings=settings, store=store, engine=engine))


def open_case(client, name: str) -> str:
    response = client.post("/api/cases", json={"name": name, "issuer": "Issuer", "sector": "Services"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, case_id: str, document: Path):
    return client.post(
        f"/api/cases/{case_id}/sources",
        files={"file": (document.name, document.read_bytes(),
                        MEDIA_TYPES.get(document.suffix, "application/octet-stream"))},
    )


def seed(client, case_id: str, names=SEED) -> list[dict]:
    """Upload the named real documents and return their source records."""
    sources = []
    for name in names:
        document = DOCUMENTS / name
        if not document.is_file():
            pytest.skip(f"{name} missing from the corpus — run: {FETCH}")
        response = upload(client, case_id, document)
        assert response.status_code == 201, f"{name}: {response.status_code} {response.text[:200]}"
        sources.append(response.json())
    return sources


@pytest.mark.parametrize("document", INGEST_DOCS, ids=lambda path: path.name)
def test_real_document_is_admitted_with_blocks_or_refused_typed(client, store, document: Path):
    case_id = open_case(client, document.stem)
    before = store.current_source_set(case_id)
    response = upload(client, case_id, document)

    if response.status_code == 201:
        body = response.json()
        assert body["blocks"], "admitted without extractable blocks"
        assert body["sha256"] == hashlib.sha256(document.read_bytes()).hexdigest(), \
            "the stored digest is not the digest of the bytes the issuer served"
        after = store.current_source_set(case_id)
        assert after["source_ids"] == [body["id"]], "the admitted source did not land in the pinned set"
        return

    # 413 upload ceiling, 415 suffix allowlist, 422 extraction limits or
    # unparseable content. Anything else is the boundary failing open.
    assert response.status_code in {413, 415, 422}, \
        f"untyped failure: {response.status_code} {response.text[:200]}"
    assert isinstance(response.json()["detail"], str)
    assert store.current_source_set(case_id) == before, "refusal left a source-set delta"


@pytest.mark.parametrize("pathway,depth", ROUTES, ids=route_ids(ROUTES))
async def test_route_runs_to_completion_on_real_issuer_evidence(client, store, engine, provider, pathway: str, depth: Depth):
    case_id = open_case(client, f"{pathway} {depth.value}")
    sources = seed(client, case_id)
    provider.bind(sources[0]["id"], sources[0]["blocks"][0]["block_id"])
    pinned = store.current_source_set(case_id)

    started = client.post(f"/api/cases/{case_id}/runs", json={"pathway": pathway, "depth": depth.value})
    assert started.status_code == 201, started.text
    run_id = started.json()["id"]
    await engine.wait(run_id)
    run = engine.get_run(run_id)
    assert run["status"] == "succeeded", run.get("error")

    assert (provider.calls > 0) is (depth is Depth.FULL), \
        "full depth must reach the provider and screen depth must never reach it"

    expected = compiled_route(pathway, depth.value)
    assert tuple(node["module_id"] for node in run["nodes"]) == expected.nodes, \
        "real evidence moved the route; the node set is a pure function of (pathway, depth)"
    assert run["plan"]["source_set_id"] == pinned["id"], "the run drifted off the source set it pinned"

    delivered = {(source["id"], block["block_id"]) for source in sources for block in source["blocks"]}
    source_ids = {source["id"] for source in sources}
    artifacts = engine.artifacts_for_run(run_id)
    assert artifacts, "a succeeded run produced no artifacts"
    for artifact in artifacts:
        for ref in artifact["payload"]["evidence_refs"]:
            # Deterministic modules cite the source; agent modules cite a block.
            if isinstance(ref, str):
                assert ref in source_ids, f"{artifact['module_id']} cited an unpinned source {ref}"
            else:
                assert (ref["source_id"], ref["block_id"]) in delivered, \
                    f"{artifact['module_id']} cited evidence the host never delivered: {ref}"


async def test_real_annual_report_runs_at_full_depth(client, store, engine, provider):
    """A real 300-page annual report, pinned alongside four other real filings,
    runs the agent path end to end.

    This is the case bounded block packing exists for. Indexed line by line the
    report alone is 7,119 blocks against a MAX_MANIFEST_BLOCKS of 2,000 for the
    whole run, so the run used to die in `bound_manifest` before its first
    provider call. Packing keeps the index affordable without making the
    evidence unreadable — the blocks the agent reads still carry real text.
    """
    from caos.engine.evidence import EvidenceReader

    case_id = open_case(client, "annual report")
    sources = seed(client, case_id, names=(*SEED, ANNUAL_REPORT))
    report = sources[-1]
    assert report["filename"] == ANNUAL_REPORT

    rows = len(sources) + sum(len(source["blocks"]) for source in sources)
    assert rows <= MAX_MANIFEST_BLOCKS, f"{rows} manifest rows for five real documents"
    assert len(report["blocks"]) > 100, "the report was packed down to a summary, not an index"

    provider.bind(report["id"], report["blocks"][0]["block_id"])
    run = await engine.start_run(case_id=case_id, pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "succeeded", record.get("error")
    assert provider.calls > 0

    # The evidence behind the citations is real text, not an empty placeholder.
    reader = EvidenceReader(store, case_id, record["plan"]["source_set_id"], run["id"])
    block_ids = [block["block_id"] for block in report["blocks"][:5]]
    delivered = reader.read(report["id"], block_ids)
    assert len(delivered) == len(block_ids)
    assert min(len(row["text"]) for row in delivered) > 200, "packed blocks came back near-empty"


@pytest.mark.parametrize("pathway,depth", CUT_ROUTES, ids=route_ids(CUT_ROUTES))
async def test_route_outside_the_mvp_cut_refuses_without_pinning(client, store, engine, pathway: str, depth: Depth):
    """A compiled route is not an executable one. The eight routes outside the
    MVP cut must refuse by name and pin nothing — the corpus is already
    uploaded when they are asked for, so a route that half-started would leave
    real evidence pinned to a run that can never finish."""
    case_id = open_case(client, f"{pathway} {depth.value}")
    seed(client, case_id)
    pinned = store.current_source_set(case_id)

    with pytest.raises(EngineError, match="PATHWAY_NOT_AVAILABLE"):
        await engine.start_run(case_id=case_id, pathway=pathway, depth=depth.value, actor="analyst")
    assert store.current_source_set(case_id) == pinned
    assert engine.active_execution_count() == 0

    if pathway in PATHWAYS and not (pathway == "DEEP_RESEARCH" and depth is Depth.SCREEN):
        # The wire admits the pathway name, so the refusal has to survive the
        # HTTP edge as a typed 422 rather than a 500. DEEP_RESEARCH carries a
        # complete brief so that what stops it is the engine's cut and not a
        # missing field at the wire.
        body = {"pathway": pathway, "depth": depth.value}
        if pathway == "DEEP_RESEARCH":
            body["research_brief"] = {
                "research_question": "How resilient is the issuer's liquidity through the next refinancing?",
                "decision_context": "Committee review of an existing position.",
                "as_of_date": "2026-01-01",
                "time_horizon": "12 months",
                "must_answer": ["Nearest maturity"],
                "exclusions": [],
            }
        response = client.post(f"/api/cases/{case_id}/runs", json=body)
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == {"code": "PATHWAY_NOT_AVAILABLE"}
