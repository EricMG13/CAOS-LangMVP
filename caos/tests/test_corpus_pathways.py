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

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cp_model"
MODEL_FIXTURES = {
    "CP-1": "cp1.md", "CP-1A": "cp1a.md", "CP-1B": "cp1b.md",
    "CP-2": "cp2.md", "CP-2A": "cp2a.md", "CP-2G": "cp2g.md",
}
# What each accepted (pathway, depth) must read as in Model Builder under host
# control: the complete model, one overlay effect, or the typed precondition.
# Relative Value has no market-marks workbook in this pack (licensed marks are
# an external input), so its full route reads the typed missing-marks state.
MODEL_EFFECTS = {
    ("FULL_CREDIT", "full"): "FULL_MODEL",
    ("EARNINGS_UPDATE", "full"): "EARNINGS_PERIOD_FORECAST_VARIANCE",
    ("COVENANT_REFINANCING", "full"): "COVENANT_REFINANCING_ASSUMPTIONS",
    ("RELATIVE_VALUE", "full"): "RELATIVE_VALUE_MARKET_MARKS_REQUIRED",
    ("DISTRESSED_RESTRUCTURING", "full"): "DISTRESSED_SCENARIO_RECOVERY",
    ("DISTRESSED_RESTRUCTURING", "screen"): "DISTRESSED_SCENARIO_RECOVERY",
    ("DEEP_RESEARCH", "full"): "DEEP_RESEARCH_REVALIDATION",
}

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
        # Sources read so far in each run: the double spreads one read of every
        # pinned source across the route (the read allowance is per module, so
        # thirty documents cannot all be read in one), which is what lets every
        # supplied document reach the cited analysis.
        self.read_by_run: dict[str, set[str]] = {}

    def bind(self, sources: list[dict]) -> None:
        self.evidence = [(source["id"], source["blocks"][0]["block_id"]) for source in sources]
        self.sha256_by_source = {source["id"]: source["sha256"] for source in sources}

    def count_tokens(self, request) -> int:
        return 1_000

    def create_message(self, request):
        from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

        assert self.evidence, "CorpusProvider used before bind()"
        self.calls += 1
        from caos.engine.budget import EVIDENCE_READS_PER_MODULE

        prompt = json.loads(str(request.messages[0]["content"]).split("\n", 1)[1])
        identity = prompt["host_identity"]
        module_id, run_id = identity["module_id"], identity["run_id"]
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
        evidence_results = [result for result in tool_results if isinstance(result, list)]
        read_here = {row["source_id"] for result in evidence_results for row in result}
        read_so_far = self.read_by_run.setdefault(run_id, set())
        read_so_far.update(read_here)
        remaining = [pair for pair in self.evidence if pair[0] not in read_so_far]
        if (remaining and len(evidence_results) < EVIDENCE_READS_PER_MODULE) or not evidence_results:
            if remaining and len(evidence_results) < EVIDENCE_READS_PER_MODULE:
                source_id, block_id = remaining[0]
            else:
                source_id, block_id = self.evidence[self.reads % len(self.evidence)]
            self.reads += 1
            block = ProviderBlock(
                type="tool_use", id=f"tool-{self.calls}", name="read_evidence",
                input={"source_id": source_id, "block_ids": [block_id]},
            )
            return ProviderMessage(
                content=[block], stop_reason="tool_use",
                usage=ProviderUsage(input_tokens=1_000, output_tokens=50),
                request_id="req-corpus-tool",
            )
        returned = {(row["source_id"], row["block_id"]) for result in evidence_results for row in result}
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
        rows = sorted(returned)
        source_id, block_id = rows[0]
        if module_id in MODEL_FIXTURES:
            # The canonical modules emit the golden CP-MODEL fixtures re-identified
            # to this run and to the first source delivered here, so the host-control
            # Full Credit run yields a buildable model and every later route an overlay.
            markdown = (
                (FIXTURES / MODEL_FIXTURES[module_id]).read_text(encoding="utf-8")
                .replace('"run-cp-model-fixture"', json.dumps(run_id))
                .replace("SRC-1", source_id)
                .replace("block-1", block_id)
                .replace("b" * 64, self.sha256_by_source[source_id])
                .replace("Acme Credit Ltd", identity["issuer_name"])
                .replace("Acme-Credit", identity["issuer_id"])
            )
        else:
            markdown = CANONICAL_BODY + "\n\n| source_id | value |\n| --- | --- |\n" + "\n".join(
                f"| {cited_source} | scripted |" for cited_source, _block in rows
            )
        envelope = json.dumps({
            "markdown": markdown,
            "evidence_refs": [{"source_id": cited_source, "block_id": cited_block} for cited_source, cited_block in rows],
            "calculation_refs": [
                {field: record[field] for field in (
                    "calculator_id", "script_digest", "calculator_digest", "input_digest", "output_digest",
                )}
                for record in calculation_records
            ],
            "lineage_counts": {"directly_sourced": len(rows)},
            "fields_present": len(rows),
            "fields_total": len(rows),
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
    """Every startable route on the whole pack: the run completes, every pinned
    document is cited by the run's artifacts, and the accepted snapshot reads
    in Model Builder as its pathway's declared model effect (Task 9) — the
    complete model, an overlay bound to that model, or the typed precondition.
    Host control proves orchestration and lineage, never analysis."""
    from caos.models.service import ModelService

    models = ModelService(store=store, vault_dir=engine.settings.storage_dir, engine=engine)
    case_id = open_case(client, "Carnival complete pack")
    sources = seed(client, case_id)
    provider.bind(sources)
    pinned = store.current_source_set(case_id)
    admitted_blocks = {
        (source["id"], block["block_id"])
        for source in sources for block in source["blocks"]
    }
    source_ids = {source["id"] for source in sources}
    base_build = None

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
        # Source-complete lineage: every pinned document reaches the cited analysis.
        assert {source_id for source_id, _block in cited_blocks} == source_ids, (pathway, depth)
        cp4c = next((artifact for artifact in artifacts if artifact["module_id"] == "CP-4C"), None)
        if cp4c is not None:
            assert {record["calculator_id"] for record in cp4c["payload"]["calculations"]} == {
                "funding_gap", "recovery_waterfall",
            }

        # The accepted snapshot's declared model effect (DECISIONS §14.18).
        snapshot = await engine.accept(run_id, actor="analyst")
        expected = MODEL_EFFECTS.get((pathway, depth.value), "FULL_DEPTH_REQUIRED")
        readiness = models.readiness(case_id)
        if expected in {"FULL_DEPTH_REQUIRED", "RELATIVE_VALUE_MARKET_MARKS_REQUIRED"}:
            assert readiness["status"] == "NOT_READY", (pathway, depth, readiness)
            assert [blocker["code"] for blocker in readiness["blockers"]] == [expected]
            continue
        assert readiness["status"] == "READY_TO_BUILD", (pathway, depth, readiness)
        queued = next(build for build in models.list_builds(case_id) if build["snapshot_id"] == snapshot["id"])
        build = models.run_build_for_tests(queued["id"])
        assert build["status"] == "READY", (pathway, depth, build.get("error"))
        lineage = build["payload"]["source_lineage"]
        assert {row["source_id"] for row in lineage} == source_ids
        assert {row["binding"] for row in lineage} <= {"MODEL_INPUT", "CITED_ANALYSIS"}
        if expected == "FULL_MODEL":
            assert "pathway_effects" not in build["payload"]
            base_build = build
        else:
            assert base_build is not None
            effect, = build["payload"]["pathway_effects"]
            assert effect["effect_id"] == expected
            assert effect["base_model"]["build_id"] == base_build["id"]
            assert build["payload"]["tabs"] == base_build["payload"]["tabs"]


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


@requires_corpus
@pytest.mark.skipif(not CORPUS_FULL, reason="the harness cell over the whole pack is nightly (CORPUS_FULL=1) evidence")
def test_qualification_harness_scores_the_carnival_pack_under_host_control(tmp_path: Path):
    """Task 11: one qualification cell (C01, Full Credit, full) runs end to end
    through the harness under the answer-keyed host control — intake refusal
    observed and scored, the pack admitted, the run driven, accepted and built,
    every dimension scored, the result bound to identity, corpus, build, date,
    expiry and reviewer. Orchestration proof only: the result reads
    host_control and can never read QUALIFIED."""
    out = tmp_path / "evidence"
    completed = subprocess.run(
        [sys.executable, str(CORPUS / "qualify.py"), "cell", "--binding", "host_control", "--pack", "C01",
         "--pathway", "FULL_CREDIT", "--depth", "full", "--reviewer", "suite", "--out", str(out)],
        cwd=CORPUS.parents[2],
        env={**os.environ, "ANTHROPIC_API_KEY": "", "OPENROUTER_API_KEY": "", "CAOS_PROVIDER": ""},
        capture_output=True, text=True, check=False,
    )
    summary = json.loads(completed.stdout[completed.stdout.index("{"):])
    assert completed.returncode == 0, summary
    retained = json.loads(next(out.rglob("rep-*.json")).read_text())
    dimensions = retained["scores"]["dimensions"]
    assert retained["verdict"] == "pass" and retained["binding"]["qualification_status"] == "host_control"
    assert dimensions["document_use"]["detail"]["problems"] == []
    assert dimensions["facts"]["detail"]["required_failed"] == []
    assert dimensions["model_effect"]["detail"]["build_status"] == "READY"
    assert dimensions["citations"]["pass"] and dimensions["unsupported_claims"]["pass"]
    assert retained["corpus"]["approval"]["scope"] == "host_control"
