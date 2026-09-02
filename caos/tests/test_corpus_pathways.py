"""Host-path checks on one real 30-document leveraged-credit case.

The fixtures are acquired from Carnival Corporation's investor-relations site,
then uploaded through the same multipart endpoint a user uses. The application
does not fetch or reshape them. A scripted provider deliberately isolates host
controls; these tests prove upload, extraction, pinning, routing and citation
validation, not live-model analytical quality.

Default runs the cheaper document-classification subset plus Full Credit and
Distressed at both depths. ``CORPUS_FULL=1`` classifies every document and runs
every executable route. Routes outside the current MVP cut must still refuse
without pinning.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.contracts import INTERNAL_PATHWAYS, PATHWAYS, Depth  # noqa: E402
from caos.engine.graphs import compiled_route  # noqa: E402
from caos.engine.runtime import MVP_PATHWAYS, EngineError, startable_routes  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402

from calculator_fixtures import VALID_CALCULATION_INPUTS  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus"
DOCUMENTS = CORPUS / "documents"
SOURCES = CORPUS / "sources.txt"
FETCH = "caos/tests/corpus/fetch.sh"
APPROVED_HOSTS = {"www.carnivalcorp.com", "www.carnivalcorporation.com"}
MEDIA_TYPES = {".pdf": "application/pdf"}


def _source_rows() -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name, sha256, document_type, period, url = line.split()
            rows.append((name, sha256, document_type, period, url))
    return rows


SOURCE_ROWS = _source_rows()
PACK_NAMES = tuple(name for name, _sha256, _document_type, _period, _url in SOURCE_ROWS)
PACK_DIGESTS = {
    name: sha256 for name, sha256, _document_type, _period, _url in SOURCE_ROWS
}


def _corpus() -> list[Path]:
    present = [DOCUMENTS / name for name in PACK_NAMES if (DOCUMENTS / name).is_file()]
    return sorted(present, key=lambda path: path.stat().st_size)


DOCS = _corpus()
CORPUS_FULL = os.environ.get("CORPUS_FULL") == "1"
SMOKE_MAX_BYTES = 1_000_000
INGEST_DOCS = DOCS if CORPUS_FULL else [doc for doc in DOCS if doc.stat().st_size <= SMOKE_MAX_BYTES]
requires_corpus = pytest.mark.skipif(len(DOCS) != len(PACK_NAMES), reason=f"corpus incomplete — run: {FETCH}")
pytestmark = pytest.mark.corpus_run

GOLDEN = [(pathway, depth) for pathway in INTERNAL_PATHWAYS for depth in (Depth.SCREEN, Depth.FULL)]
# The engine's own startable list: every cut pathway at every depth it runs
# (Deep Research is full-depth only, §14.1).
LIVE_ROUTES = [route for route in GOLDEN if (route[0], route[1].value) in set(startable_routes())]
CUT_ROUTES = [route for route in GOLDEN if route[0] not in MVP_PATHWAYS]
DEPTH_CUT_ROUTES = [route for route in GOLDEN if route[0] in MVP_PATHWAYS and route not in LIVE_ROUTES]
# A fixture brief for the Deep Research host control: orchestration proof only
# — it proves the brief, the approval gate and the route complete on a supplied
# pack, not that any research question about Carnival was answered.
RESEARCH_BRIEF = {
    "research_question": "How resilient is liquidity through the next refinancing?",
    "decision_context": "Committee review of an existing position.",
    "as_of_date": "2026-01-01",
    "time_horizon": "12 months",
    "must_answer": ["Nearest maturity"],
    "exclusions": [],
}
ROUTES = LIVE_ROUTES if CORPUS_FULL else [
    route for route in LIVE_ROUTES if route[0] in {"FULL_CREDIT", "DISTRESSED_RESTRUCTURING"}
]

CANONICAL_BODY = "\n".join(
    f"## {heading}\n\nscripted"
    for heading in ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry", "Gaps & Conflicts", "QA Validation")
)


def test_manifest_is_one_complete_user_upload_pack():
    assert len(SOURCE_ROWS) == 30, "an enterprise case must exercise the 20–30 document operating range"
    assert len(set(PACK_NAMES)) == len(PACK_NAMES)
    assert all(name.startswith("CCL_") and name.endswith(".pdf") for name in PACK_NAMES)
    for _name, sha256, document_type, period, url in SOURCE_ROWS:
        assert len(sha256) == 64 and all(character in "0123456789abcdef" for character in sha256)
        assert document_type in {
            "annual_report", "form_10k", "quarterly_report", "management_guidance",
            "management_forecast", "quarterly_legal",
        }
        assert period.startswith("FY20")
        parsed = urlsplit(url)
        assert parsed.scheme == "https" and parsed.hostname in APPROVED_HOSTS
    for year in ("2023", "2024", "2025"):
        assert any(
            document_type in {"annual_report", "form_10k"} and period == f"FY{year}"
            for _name, _sha256, document_type, period, _url in SOURCE_ROWS
        )
        for quarter in ("Q1", "Q2", "Q3"):
            assert any(
                document_type in {"quarterly_report", "quarterly_legal"}
                and period == f"FY{year}-{quarter}"
                for _name, _sha256, document_type, period, _url in SOURCE_ROWS
            )
        for quarter in ("Q1", "Q2", "Q3", "Q4"):
            assert any(
                document_type in {"management_guidance", "management_forecast"}
                and period == f"FY{year}-{quarter}"
                for _name, _sha256, document_type, period, _url in SOURCE_ROWS
            )
    assert any(document_type == "quarterly_legal" for _, _, document_type, _, _ in SOURCE_ROWS)


def test_fetcher_refuses_redirect_without_requesting_the_target(tmp_path: Path):
    script = tmp_path / "fetch.sh"
    shutil.copy2(CORPUS / "fetch.sh", script)
    (tmp_path / "sources.txt").write_text(
        "fixture.pdf " + "0" * 64
        + " annual_report FY2025 https://www.carnivalcorp.com/fixture.pdf\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -eu
output=
follow=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) output="$2"; shift 2 ;;
    -*L*|--location) follow=1; shift ;;
    *) shift ;;
  esac
done
if [ "$follow" -eq 1 ]; then
  touch "$FAKE_REDIRECT_MARKER"
  printf '%%PDF-fake' > "$output"
else
  printf '<html>redirect</html>' > "$output"
fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    marker = tmp_path / "redirect-requested"
    result = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}", "FAKE_REDIRECT_MARKER": str(marker)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "REFUSED non-PDF response" in result.stderr
    assert not marker.exists()


class CorpusProvider:
    """Provider-port double for host controls; it is not an LLM qualification."""

    def __init__(self) -> None:
        from caos.engine.provider import host_control_identity

        self.evidence: list[tuple[str, str]] = []
        self.delivered: set[tuple[str, str]] = set()
        self.delivery_log: list[set[tuple[str, str]]] = []
        self.calls = 0
        self.reads = 0
        self.identity = host_control_identity()

    def bind(self, sources: list[dict]) -> None:
        self.evidence = [(source["id"], source["blocks"][0]["block_id"]) for source in sources]

    def count_tokens(self, request) -> int:
        return 1_000

    def create_message(self, request):
        from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

        assert self.evidence, "CorpusProvider used before bind()"
        self.calls += 1
        tool_results = [
            json.loads(block["content"])
            for message in request.messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        calculation_tool = next(
            (tool for tool in request.effective_tools()
             if tool["name"] == "run_methodology_calculation"),
            None,
        )
        if not tool_results:
            current = self.evidence[self.reads % len(self.evidence)]
            self.reads += 1
            source_id, block_id = current
            block = ProviderBlock(
                type="tool_use", id=f"tool-{self.calls}", name="read_evidence",
                input={"source_id": source_id, "block_ids": [block_id]},
            )
            return ProviderMessage(
                content=[block], stop_reason="tool_use",
                usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
                request_id="req-corpus-tool",
            )
        evidence_result = next(result for result in tool_results if isinstance(result, list))
        returned = {(row["source_id"], row["block_id"]) for row in evidence_result}
        self.delivered.update(returned)
        self.delivery_log.append(returned)
        calculation_records = [result for result in tool_results if isinstance(result, dict)]
        if calculation_tool is not None:
            calculator_ids = calculation_tool["input_schema"]["properties"]["calculator_id"]["enum"]
            if len(calculation_records) < len(calculator_ids):
                calculator_id = calculator_ids[len(calculation_records)]
                return ProviderMessage(
                    content=[ProviderBlock(
                        type="tool_use",
                        id=f"tool-{self.calls}",
                        name="run_methodology_calculation",
                        input={
                            "calculator_id": calculator_id,
                            "input_json": json.dumps(self._calculation_input(calculator_id)),
                        },
                    )],
                    stop_reason="tool_use",
                    usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
                    request_id="req-corpus-calculation",
                )
        source_id, block_id = next(iter(returned))
        envelope = json.dumps({
            "markdown": (
                CANONICAL_BODY
                + f"\n\n| source_id | value |\n| --- | --- |\n| {source_id} | scripted |"
            ),
            "evidence_refs": [{"source_id": source_id, "block_id": block_id}],
            "calculation_refs": [
                {field: record[field] for field in (
                    "calculator_id", "script_digest", "calculator_digest", "input_digest", "output_digest",
                )}
                for record in calculation_records
            ],
            "lineage_counts": {"directly_sourced": 1},
            "fields_present": 1,
            "fields_total": 1,
            "source_gate": "pass",
        })
        return ProviderMessage(
            content=[ProviderBlock(type="text", text=envelope)], stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1_000, output_tokens=200),
            request_id="req-corpus-final",
        )

    @staticmethod
    def _calculation_input(calculator_id: str) -> dict:
        # Answer-keyed inputs for every assigned calculator: the host control
        # proves the tool path completes, not that these numbers are Carnival's.
        return VALID_CALCULATION_INPUTS[calculator_id]


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)


@pytest.fixture()
def store(tmp_path: Path) -> DomainStore:
    value = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    try:
        yield value
    finally:
        value.close()


@pytest.fixture()
def provider() -> CorpusProvider:
    return CorpusProvider()


@pytest.fixture()
async def engine(tmp_path: Path, settings: Settings, store: DomainStore, provider: CorpusProvider):
    from caos.engine.runtime import Engine

    value = Engine.create(
        settings=settings, store=store,
        checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
    )
    try:
        yield value
    finally:
        await value.aclose()


@pytest.fixture()
def client(settings: Settings, store: DomainStore, engine):
    from fastapi.testclient import TestClient

    from caos.api import create_app

    with TestClient(create_app(settings=settings, store=store, engine=engine)) as test_client:
        yield test_client


def open_case(client, name: str) -> str:
    response = client.post("/api/cases", json={"name": name, "issuer": "Carnival Corporation", "sector": "Travel"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, case_id: str, document: Path):
    return client.post(
        f"/api/cases/{case_id}/sources",
        files={"file": (document.name, document.read_bytes(), MEDIA_TYPES[document.suffix])},
    )


def seed(client, case_id: str) -> list[dict]:
    sources = []
    for name in PACK_NAMES:
        document = DOCUMENTS / name
        assert document.is_file(), f"{name} missing — run: {FETCH}"
        response = upload(client, case_id, document)
        assert response.status_code == 201, f"{name}: {response.status_code} {response.text[:200]}"
        sources.append(response.json())
    assert 20 <= len(sources) <= 30
    return sources


@requires_corpus
@pytest.mark.parametrize("document", INGEST_DOCS, ids=lambda path: path.name)
def test_user_uploaded_document_is_admitted_with_blocks(client, store, document: Path):
    assert hashlib.sha256(document.read_bytes()).hexdigest() == PACK_DIGESTS[document.name]
    case_id = open_case(client, document.stem)
    response = upload(client, case_id, document)
    assert response.status_code == 201, f"{document.name}: {response.status_code} {response.text[:200]}"
    body = response.json()
    assert body["blocks"], "admitted without extractable blocks"
    assert body["sha256"] == hashlib.sha256(document.read_bytes()).hexdigest()
    assert store.current_source_set(case_id)["source_ids"] == [body["id"]]


@requires_corpus
async def test_supported_routes_complete_host_path_on_30_document_upload(client, store, engine, provider):
    case_id = open_case(client, "Carnival complete pack")
    sources = seed(client, case_id)
    provider.bind(sources)
    pinned = store.current_source_set(case_id)
    admitted_blocks = {
        (source["id"], block["block_id"])
        for source in sources for block in source["blocks"]
    }
    source_ids = {source["id"] for source in sources}

    for pathway, depth in ROUTES:
        calls_before = provider.calls
        deliveries_before = len(provider.delivery_log)
        started = await engine.start_run(
            case_id=case_id, pathway=pathway, depth=depth.value, actor="analyst",
            research_brief=RESEARCH_BRIEF if pathway == "DEEP_RESEARCH" else None,
        )
        run_id = started["id"]
        run = await engine.wait(run_id)
        if pathway == "DEEP_RESEARCH":
            # The governed gate: the run parks on the host-proposed plan and
            # resumes only on the exact approved hash (invariant 5).
            assert run["status"] == "paused" and run["error"]["code"] == "PLAN_APPROVAL_REQUIRED"
            assert run["research"]["brief"] == RESEARCH_BRIEF
            await engine.approve_research_plan(
                run_id, plan_hash=run["research"]["proposed_plan_hash"], actor="analyst",
            )
            run = await engine.wait(run_id)
            assert run["research"]["approved_plan_hash"] == run["research"]["proposed_plan_hash"]
        assert run["status"] == "succeeded", run.get("error")
        assert provider.calls > calls_before
        assert tuple(node["module_id"] for node in run["nodes"]) == compiled_route(pathway, depth.value).nodes
        assert run["plan"]["source_set_id"] == pinned["id"]
        artifacts = engine.artifacts_for_run(run_id)
        assert artifacts
        cited_blocks: set[tuple[str, str]] = set()
        for artifact in artifacts:
            for ref in artifact["payload"]["evidence_refs"]:
                if isinstance(ref, str):
                    assert ref in source_ids
                else:
                    cited = (ref["source_id"], ref["block_id"])
                    assert cited in admitted_blocks
                    cited_blocks.add(cited)
        delivered_this_route = set().union(*provider.delivery_log[deliveries_before:])
        assert delivered_this_route
        assert delivered_this_route <= cited_blocks
        cp4c = next((artifact for artifact in artifacts if artifact["module_id"] == "CP-4C"), None)
        if cp4c is not None:
            assert {record["calculator_id"] for record in cp4c["payload"]["calculations"]} == {
                "funding_gap", "recovery_waterfall",
            }


@requires_corpus
async def test_unavailable_routes_refuse_without_pinning_30_document_case(client, store, engine):
    case_id = open_case(client, "Carnival unavailable routes")
    seed(client, case_id)
    pinned = store.current_source_set(case_id)

    for pathway, depth in CUT_ROUTES:
        with pytest.raises(EngineError, match="PATHWAY_NOT_AVAILABLE"):
            await engine.start_run(case_id=case_id, pathway=pathway, depth=depth.value, actor="analyst")
        assert store.current_source_set(case_id) == pinned
        assert engine.active_execution_count() == 0

        if pathway in PATHWAYS:
            response = client.post(f"/api/cases/{case_id}/runs", json={"pathway": pathway, "depth": depth.value})
            assert response.status_code == 422, response.text
            assert response.json()["detail"] == {"code": "PATHWAY_NOT_AVAILABLE"}

    # A cut pathway at a depth the engine does not run (Deep Research at
    # screen) is refused by the depth rule, again without pinning.
    assert DEPTH_CUT_ROUTES == [("DEEP_RESEARCH", Depth.SCREEN)]
    for pathway, depth in DEPTH_CUT_ROUTES:
        with pytest.raises(EngineError, match="DEPTH_NOT_SUPPORTED"):
            await engine.start_run(
                case_id=case_id, pathway=pathway, depth=depth.value, actor="analyst",
                research_brief=RESEARCH_BRIEF,
            )
        assert store.current_source_set(case_id) == pinned
        assert engine.active_execution_count() == 0
        response = client.post(
            f"/api/cases/{case_id}/runs",
            json={"pathway": pathway, "depth": depth.value, "research_brief": RESEARCH_BRIEF},
        )
        assert response.status_code == 422, response.text
