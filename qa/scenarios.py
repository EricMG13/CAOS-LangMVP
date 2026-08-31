"""Realistic analyst journeys driven end to end against a running server.

`qa/probe.py` checks one acceptance criterion at a time. This drives the whole
workflow an analyst actually performs — upload, run, accept, draft, review,
file, export — and asserts what each step leaves behind. Defects that live in
the seams between routes only show up here: F-10 was found because nothing
asserted what Model Builder *says* after an accepted Earnings Update, only that
it refuses to build.

ponytail: plain asserts, no framework. Exit code is the number of failures.

    python caos/server/dev.py                       # terminal 1
    CAOS_APP_URL=http://127.0.0.1:8000 python qa/scenarios.py

Deterministic routes only — no ANTHROPIC_API_KEY required, and therefore no
FULL_CREDIT agent run, which is exactly the state F-10 lives in.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import zipfile

import httpx

BASE = os.getenv("CAOS_APP_URL", "http://127.0.0.1:8000")


def head(subject: str, role: str) -> dict[str, str]:
    # Dev trusts x-caos-role; the subject still arrives on the OIDC-shaped
    # header, so these personas are the same shape production sees.
    return {"x-forwarded-user": subject, "x-forwarded-email": f"{subject}@caos.invalid",
            "x-caos-role": role}


ANALYST = head("scenario-analyst", "ANALYST")
APPROVER = head("scenario-approver", "APPROVER")
READER = head("scenario-reader", "READER")

failures: list[str] = []
checks = 0
client = httpx.Client(base_url=BASE, timeout=180)


def check(criterion: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  PASS {criterion}")
    else:
        failures.append(f"{criterion}: {detail}")
        print(f"  FAIL {criterion} — {detail}")


def upload(case_id: str, filename: str, text: str) -> httpx.Response:
    return client.post(f"/api/cases/{case_id}/sources",
                       files={"file": (filename, text.encode("utf-8"), "text/plain")},
                       headers=ANALYST)


def wait_terminal(run_id: str, budget_s: float = 180) -> dict:
    deadline = time.time() + budget_s
    run: dict = {}
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}", headers=ANALYST).json()
        if run.get("status") in {"succeeded", "failed", "paused"}:
            return run
        time.sleep(0.4)
    return run


def grant(case_id: str, member: str, role: str) -> None:
    """No HTTP route grants case membership (qa/FINDINGS.md observations), so
    the approver and reader personas are seeded through the store."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "caos", "server"))
    from caos.storage.store import DomainStore

    # Mirrors dev.py's own default so the harness works with no env set.
    data_dir = os.environ.get("CAOS_DATA_DIR", ".dev-data")
    url = os.environ.get("DATABASE_URL") or f"sqlite+pysqlite:///{os.path.abspath(data_dir)}/caos.db"
    DomainStore.from_url(url).add_member(case_id, "scenario-analyst", member, role, actor_role="ADMIN")


Q3_RELEASE = """Northwind Holdings reports Q3 results

Organic revenue growth of 3.4% in the quarter.
Adjusted EBITDA margin of 18.2%, -60bps year on year.
Net leverage of 5.85x, against a covenant level of 7.50x tested quarterly.

Outlook: management reiterates full-year guidance and expects free cash flow
conversion of approximately 62% of adjusted EBITDA.
"""

ANNUAL_REPORT = """Northwind Holdings - Annual Report and Accounts, financial year 2025

SECTION 1. OPERATING AND FINANCIAL REVIEW

Revenue for the period was EUR 1240.0m against EUR 1190.0m in the prior year.
Adjusted EBITDA of EUR 226.0m represents a margin of 18.2%.
Net debt at the balance sheet date was EUR 1322.0m, equivalent to 5.85x adjusted EBITDA.

SECTION 2. SUMMARY FINANCIALS (EUR m)
Metric,FY,Prior FY
Revenue,1240.0,1190.0
Adjusted EBITDA,226.0,231.0
Net debt,1322.0,1281.0
Cash interest,92.0,84.0

SECTION 3. PRINCIPAL RISKS

3.1 The senior facilities agreement contains a springing net leverage covenant tested quarterly.
"""

SECTIONS = {
    "section.01": "Northwind remains a business-services credit at 5.85x net leverage with adequate liquidity.",
    "section.02": "Q3 organic growth of 3.4% slowed from the first half; margin fell 60bps on pass-through lag.",
    "section.03": "Reported adjusted EBITDA of EUR 226m against EUR 231m prior year, a EUR 5m bridge driven by mix.",
    "section.04": "No change to the base model; FY26 EBITDA held at EUR 230m pending the Q4 print.",
    "section.05": "Net debt of EUR 1,322m equates to 5.85x, 165bps of headroom to the 7.50x springing test.",
    "section.06": "Thesis unchanged: hold. The covenant is not at risk within four quarters on management guidance.",
    "section.07": "Monitor Q4 pricing actions and the January interest reset; a 200bps rate move is the key catalyst.",
}
ANSWERED_SECTION_05 = (
    "Net debt of EUR 1,322m equates to 5.85x, 165bps of headroom to the 7.50x springing test. "
    "The January reset lifts cash interest by approximately EUR 11m annualised, taking pro-forma "
    "leverage to 5.92x and headroom to 158bps."
)


def scenario_earnings_update() -> str:
    """An analyst screens a Q3 print: upload, run, accept, read the snapshot."""
    print("\n== scenario 1: Q3 earnings update, screen depth ==")
    case = client.post("/api/cases", json={"name": "Q3 earnings update", "issuer": "Northwind Holdings",
                                           "sector": "Business Services"}, headers=ANALYST).json()
    case_id = case["id"]
    responses = [upload(case_id, "northwind-q3-2025.txt", Q3_RELEASE),
                 upload(case_id, "northwind-ar-2025.txt", ANNUAL_REPORT)]
    check("both filings are admitted", all(r.status_code == 201 for r in responses),
          f"{[r.status_code for r in responses]}")

    started = client.post(f"/api/cases/{case_id}/runs",
                          json={"pathway": "EARNINGS_UPDATE", "depth": "screen",
                                "focus_questions": ["Is the springing covenant at risk within four quarters?"]},
                          headers=ANALYST)
    check("the run starts and returns its plan immediately", started.status_code == 201,
          f"{started.status_code} {started.text[:300]}")
    if started.status_code != 201:
        return case_id
    run = wait_terminal(started.json()["id"])
    check("the run succeeds", run.get("status") == "succeeded", json.dumps(run)[:300])

    source_ids = {source["id"] for source in client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()}
    for node in run.get("nodes") or []:
        artifact_id = node.get("artifact_id")
        check(f"{node['module_id']} produced a readable artifact", bool(artifact_id), json.dumps(node)[:200])
        if not artifact_id:
            continue
        artifact = client.get(f"/api/cases/{case_id}/artifacts/{artifact_id}", headers=ANALYST)
        check(f"{node['module_id']} artifact served", artifact.status_code == 200,
              f"{artifact.status_code} {artifact.text[:200]}")
        if artifact.status_code != 200:
            continue
        for citation in (artifact.json().get("payload") or {}).get("citations") or []:
            check("every citation names a delivered source", citation.get("source_id") in source_ids,
                  json.dumps(citation)[:200])

    accepted = client.post(f"/api/runs/{started.json()['id']}/accept", json={}, headers=ANALYST)
    check("the analyst accepts the run", accepted.status_code == 200,
          f"{accepted.status_code} {accepted.text[:300]}")
    check("the case now names an accepted snapshot",
          bool(client.get(f"/api/cases/{case_id}", headers=ANALYST).json()["accepted_snapshot_id"]))
    check("the snapshot view is served",
          client.get(f"/api/cases/{case_id}/snapshot", headers=ANALYST).status_code == 200)
    return case_id


def scenario_withdrawal() -> None:
    """Legal pulls a third-party note after it has already been pinned."""
    print("\n== scenario 2: a source is withdrawn between two runs ==")
    case = client.post("/api/cases", json={"name": "Watchlist deep-dive", "issuer": "Ironvale Bidco",
                                           "sector": "Chemicals"}, headers=ANALYST).json()
    case_id = case["id"]
    note = upload(case_id, "ironvale-broker-note.txt",
                  "Third-party broker note on Ironvale Bidco.\nEstimated FY26 EBITDA EUR 150m.\n")
    upload(case_id, "ironvale-ar-2025.txt",
           "Ironvale Bidco - Annual Report 2025\n\nRevenue EUR 880.0m. Adjusted EBITDA EUR 141.0m.\n")
    check("the broker note is admitted", note.status_code == 201, f"{note.status_code} {note.text[:200]}")
    if note.status_code != 201:
        return
    note_id = note.json()["id"]

    first = client.post(f"/api/cases/{case_id}/runs",
                        json={"pathway": "EARNINGS_UPDATE", "depth": "screen", "focus_questions": []},
                        headers=ANALYST)
    check("the first run pins all sources", first.status_code == 201, f"{first.status_code} {first.text[:300]}")
    if first.status_code != 201:
        return
    run_id = first.json()["id"]
    before = wait_terminal(run_id)
    check("the first run succeeds", before.get("status") == "succeeded", json.dumps(before)[:300])

    withdrawn = client.post(f"/api/cases/{case_id}/sources/{note_id}/withdraw", headers=ANALYST)
    check("the withdrawal is accepted", withdrawn.status_code == 200,
          f"{withdrawn.status_code} {withdrawn.text[:200]}")
    check("the source reports itself withdrawn", withdrawn.json().get("withdrawn") is True,
          json.dumps(withdrawn.json())[:200])
    check("withdrawing twice is idempotent",
          client.post(f"/api/cases/{case_id}/sources/{note_id}/withdraw", headers=ANALYST).status_code == 200)
    check("a withdrawn source leaves the supplied set",
          note_id not in {s["id"] for s in client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()})

    later = client.post(f"/api/cases/{case_id}/runs",
                        json={"pathway": "EARNINGS_UPDATE", "depth": "screen", "focus_questions": []},
                        headers=ANALYST)
    check("a later run still starts", later.status_code == 201, f"{later.status_code} {later.text[:300]}")
    if later.status_code == 201:
        after = wait_terminal(later.json()["id"])
        check("the later run succeeds", after.get("status") == "succeeded", json.dumps(after)[:300])
        check("the withdrawn source is nowhere in the later run's pin",
              note_id not in json.dumps(after), "the withdrawn source id appears in the run payload")

    # Invariant 6: resume never restarts. A terminal run must resume to itself,
    # with the same artifacts and no second terminal event.
    resumed = client.post(f"/api/runs/{run_id}/resume", json={}, headers=ANALYST)
    check("resuming a finished run is a no-op", resumed.status_code == 200,
          f"{resumed.status_code} {resumed.text[:200]}")
    after_resume = client.get(f"/api/runs/{run_id}", headers=ANALYST).json()
    check("resume produced no second execution",
          [n.get("artifact_id") for n in after_resume["nodes"]] == [n.get("artifact_id") for n in before["nodes"]],
          "artifact set changed across a resume")
    # Invariant 6: one terminal event per run, however many times it is resumed.
    terminal = [e for e in after_resume.get("events") or []
                if e.get("event") in {"run.succeeded", "run.failed"}]
    check("exactly one terminal run event survives the resume", len(terminal) == 1,
          json.dumps(terminal)[:300])


def scenario_deliverable(case_id: str) -> None:
    """The memo goes out: draft, a concurrent editor, review, filing, export."""
    print("\n== scenario 3: the earnings-update memo, drafted to filed ==")
    pathway = "EARNINGS_UPDATE"
    grant(case_id, "scenario-approver", "APPROVER")
    grant(case_id, "scenario-reader", "READER")

    workspace = client.get(f"/api/cases/{case_id}/deliverables/{pathway}/draft", headers=ANALYST).json()
    template = workspace["template"]
    sources = client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()
    release = next(s for s in sources if "q3" in s["filename"])
    citation = {"source_id": release["id"], "block_ids": [release["blocks"][0]["block_id"]],
                "claim": "Net leverage of 5.85x against a 7.50x covenant."}

    blocks = []
    for block in template["blocks"]:
        common = {"block_id": block["block_id"], "slot_id": block["slot_id"], "kind": block["kind"]}
        if block["kind"] == "NARRATIVE":
            blocks.append({**common, "text": SECTIONS[block["slot_id"]],
                           "content_mode": "EVIDENCE", "citations": [citation]})
        elif block["kind"] == "EVIDENCE_REGISTER":
            blocks.append({**common, "citations": [citation]})

    def draft_body(version: int, content: list[dict]) -> dict:
        return {"expected_version": version, "template_id": template["template_id"],
                "template_version": template["template_version"], "blocks": content}

    base_version = (workspace.get("current") or {}).get("version", 0)
    saved = client.put(f"/api/cases/{case_id}/deliverables/{pathway}/draft",
                       json=draft_body(base_version, blocks), headers=ANALYST)
    check("the analyst saves the first draft", saved.status_code == 201,
          f"{saved.status_code} {saved.text[:300]}")
    if saved.status_code != 201:
        return
    draft = saved.json()["current"]

    stale = client.put(f"/api/cases/{case_id}/deliverables/{pathway}/draft",
                       json=draft_body(base_version, blocks), headers=ANALYST)
    check("a colleague's stale save is refused", stale.status_code == 409,
          f"{stale.status_code} {stale.text[:300]}")
    if stale.status_code == 409:
        detail = stale.json().get("detail") or {}
        check("the refusal names DELIVERABLE_VERSION_CONFLICT",
              detail.get("code") == "DELIVERABLE_VERSION_CONFLICT", json.dumps(detail)[:200])
        check("the refusal returns the current revision to rebase onto",
              bool(detail.get("current")), json.dumps(detail)[:300])

    check("a reader cannot write a draft",
          client.put(f"/api/cases/{case_id}/deliverables/{pathway}/draft",
                     json=draft_body(draft["version"], blocks), headers=READER).status_code == 403)

    frozen = client.post(f"/api/cases/{case_id}/deliverables/{pathway}/freeze",
                         json={"draft_id": draft["draft_id"], "draft_version": draft["version"],
                               "draft_digest": draft["digest"]}, headers=ANALYST)
    check("the analyst freezes the memo", frozen.status_code == 201,
          f"{frozen.status_code} {frozen.text[:300]}")
    if frozen.status_code != 201:
        return
    first = frozen.json()
    binding = {"preview_digest": first["preview_digest"], "input_fingerprint": first["input_fingerprint"]}

    check("the author cannot file their own memo",
          client.post(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/approve",
                      json=binding, headers=ANALYST).status_code == 403)
    check("a reader cannot file",
          client.post(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/approve",
                      json=binding, headers=READER).status_code == 403)
    check("filing a digest that was never reviewed is refused",
          client.post(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/approve",
                      json={**binding, "preview_digest": "0" * 64}, headers=APPROVER).status_code >= 400)
    check("an unfiled memo cannot be exported",
          client.get(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/export/md",
                     headers=ANALYST).status_code == 409)

    sent_back = client.post(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/request-changes",
                            json={**binding, "comment": "Quantify the January interest reset in section 5."},
                            headers=APPROVER)
    check("the approver can send the memo back", sent_back.status_code == 200,
          f"{sent_back.status_code} {sent_back.text[:300]}")
    if sent_back.status_code == 200:
        check("sending back returns both the frozen record and a fresh draft",
              bool(sent_back.json().get("frozen")) and bool(sent_back.json().get("draft")),
              json.dumps(sent_back.json())[:200])
        check("a memo sent back can no longer be filed",
              client.post(f"/api/cases/{case_id}/deliverables/by-id/{first['id']}/approve",
                          json=binding, headers=APPROVER).status_code >= 400)

    current = client.get(f"/api/cases/{case_id}/deliverables/{pathway}/draft", headers=ANALYST).json()["current"]
    answered = [dict(block, text=ANSWERED_SECTION_05) if block["slot_id"] == "section.05" else block
                for block in current["content"]["blocks"]]
    revised = client.put(f"/api/cases/{case_id}/deliverables/{pathway}/draft",
                         json=draft_body(current["version"], answered), headers=ANALYST)
    check("the analyst answers the comment", revised.status_code == 201,
          f"{revised.status_code} {revised.text[:300]}")
    if revised.status_code != 201:
        return
    second_draft = revised.json()["current"]
    refrozen = client.post(f"/api/cases/{case_id}/deliverables/{pathway}/freeze",
                           json={"draft_id": second_draft["draft_id"], "draft_version": second_draft["version"],
                                 "draft_digest": second_draft["digest"]}, headers=ANALYST)
    check("the analyst re-freezes", refrozen.status_code == 201,
          f"{refrozen.status_code} {refrozen.text[:300]}")
    if refrozen.status_code != 201:
        return
    second = refrozen.json()
    filed = client.post(f"/api/cases/{case_id}/deliverables/by-id/{second['id']}/approve",
                        json={"preview_digest": second["preview_digest"],
                              "input_fingerprint": second["input_fingerprint"]}, headers=APPROVER)
    check("the approver files the revised memo", filed.status_code == 200,
          f"{filed.status_code} {filed.text[:300]}")
    if filed.status_code != 200:
        return
    check("the filing is recorded with its signer and time",
          filed.json()["status"] == "FILED" and bool(filed.json()["approved_by"])
          and bool(filed.json()["approved_at"]), json.dumps(filed.json())[:300])

    exports = {}
    for form in ("md", "pdf", "xlsx"):
        response = client.get(f"/api/cases/{case_id}/deliverables/by-id/{second['id']}/export/{form}",
                              headers=ANALYST)
        exports[form] = response
        check(f"the filed memo exports as {form}", response.status_code == 200,
              f"{response.status_code} {response.text[:200]}")
        if response.status_code != 200:
            continue
        check(f"the {form} digest header matches the bytes served",
              response.headers.get("x-caos-sha256") == hashlib.sha256(response.content).hexdigest(),
              f"{response.headers.get('x-caos-sha256')}")
        check(f"the {form} export is not cached by intermediaries",
              "no-store" in (response.headers.get("cache-control") or ""),
              f"{response.headers.get('cache-control')}")
    if all(response.status_code == 200 for response in exports.values()):
        check("the markdown carries the revision the approver asked for",
              b"158bps" in exports["md"].content, exports["md"].content[:200].decode("utf-8", "replace"))
        check("the pdf is a real PDF", exports["pdf"].content[:5] == b"%PDF-", f"{exports['pdf'].content[:20]!r}")
        check("the xlsx is a real workbook", zipfile.is_zipfile(io.BytesIO(exports["xlsx"].content)),
              f"{exports['xlsx'].content[:20]!r}")
        check("re-exporting a filed memo is byte-identical",
              client.get(f"/api/cases/{case_id}/deliverables/by-id/{second['id']}/export/md",
                         headers=ANALYST).content == exports["md"].content)
    check("a reader may download the filed memo",
          client.get(f"/api/cases/{case_id}/deliverables/by-id/{second['id']}/export/md",
                     headers=READER).status_code == 200)


def scenario_model_readiness(case_id: str) -> None:
    """F-10. The accepted authority here is an Earnings Update, so Model Builder
    must say which pathway it needs — not that the inputs are corrupt."""
    print("\n== scenario 4: Model Builder after an accepted Earnings Update ==")
    readiness = client.get(f"/api/cases/{case_id}/model", headers=ANALYST)
    check("model readiness is served", readiness.status_code == 200,
          f"{readiness.status_code} {readiness.text[:200]}")
    if readiness.status_code != 200:
        return
    body = readiness.json()
    # Model Builder draws its "Open Run Console" way out on NOT_READY only, and
    # a build button on READY_TO_BUILD/FAILED only. Any other status is a screen
    # with no action on it at all.
    check("the wrong pathway reads as NOT_READY, not as invalid inputs",
          body["status"] == "NOT_READY", f"status={body['status']} blockers={json.dumps(body['blockers'])}")
    check("the blocker names the pathway the analyst must run",
          [blocker["code"] for blocker in body["blockers"]] == ["ACCEPTED_FULL_CREDIT_REQUIRED"],
          json.dumps(body["blockers"]))
    check("the blocker carries the detail the callout renders",
          all(blocker.get("detail") for blocker in body["blockers"]), json.dumps(body["blockers"]))
    queued = client.post(f"/api/cases/{case_id}/models", headers=ANALYST)
    check("building refuses as not-ready, not as an invalid build",
          (queued.json().get("detail") or {}).get("code") == "MODEL_NOT_READY",
          f"{queued.status_code} {queued.text[:200]}")


COMPARABLES = [
    # issuer, instrument, currency, price, yield_bps, spread_bps, duration
    ("Northwind Holdings", "Northwind 2029 TLB", "EUR", 98.25, 612.0, 585.0, 3.6),
    ("Calder Group", "Calder 2028 TLB", "EUR", 99.10, 548.0, 521.0, 2.9),
    ("Brightmoor Industries", "Brightmoor 2030 SSN", "EUR", 94.75, 703.0, 676.0, 4.1),
    ("Ashcombe Partners", "Ashcombe 2027 SUN", "EUR", 89.50, 941.0, 914.0, 2.2),
]


def scenario_relative_value_and_notes() -> None:
    """The analyst screens the name against comparables and promotes a desk note
    into the supplied set — the one route that mints evidence rather than
    admitting an upload, so invariant 1 has to hold on it too."""
    print("\n== scenario 5: relative value comparables and a promoted desk note ==")
    case = client.post("/api/cases", json={"name": "Refinancing assessment", "issuer": "Calder Group",
                                           "sector": "Packaging"}, headers=ANALYST).json()
    case_id = case["id"]

    rows = [{"issuer": issuer, "instrument": instrument, "currency": currency, "price": price,
             "yield_bps": yield_bps, "spread_bps": spread, "duration": duration}
            for issuer, instrument, currency, price, yield_bps, spread, duration in COMPARABLES]
    saved = client.post(f"/api/cases/{case_id}/rv", json={"rows": rows}, headers=ANALYST)
    check("the comparables sheet is saved", saved.status_code == 201,
          f"{saved.status_code} {saved.text[:300]}")
    if saved.status_code != 201:
        return

    workspace = client.get(f"/api/cases/{case_id}/rv", headers=ANALYST)
    check("the comparables read back", workspace.status_code == 200,
          f"{workspace.status_code} {workspace.text[:200]}")
    if workspace.status_code == 200:
        universe = workspace.json()["universe"]
        served = {row["instrument"]: row for row in (universe or {}).get("rows") or []}
        check("every comparable survives the round trip", len(served) == len(COMPARABLES),
              f"{sorted(served)}")
        widest = max(COMPARABLES, key=lambda row: row[5])
        check("the widest spread is preserved exactly, not re-rounded",
              served.get(widest[1], {}).get("spread_bps") == widest[5],
              f"{served.get(widest[1], {}).get('spread_bps')} != {widest[5]}")

    # Invariant 7: a non-finite mark must be refused at the boundary, not
    # carried into a screen where it would poison every relative comparison.
    # json.dumps writes bare `Infinity`, which is what a careless client sends.
    poisoned = json.dumps({"rows": [{**rows[0], "spread_bps": float("inf")}]})
    refused = client.post(f"/api/cases/{case_id}/rv", content=poisoned,
                          headers={**ANALYST, "content-type": "application/json"})
    check("a non-finite spread is refused", refused.status_code == 422,
          f"{refused.status_code} {refused.text[:200]}")
    after = client.get(f"/api/cases/{case_id}/rv", headers=ANALYST).json()["universe"]
    check("the refused sheet did not replace the saved one",
          len((after or {}).get("rows") or []) == len(COMPARABLES), json.dumps(after)[:200])

    note = client.post(f"/api/cases/{case_id}/notes",
                       json={"body": "Call with the sponsor, 29 Aug: refinancing is targeted for Q1, "
                                     "with the revolver upsized to EUR 150m and the springing test reset to 8.00x."},
                       headers=ANALYST)
    check("the desk note is recorded", note.status_code == 201, f"{note.status_code} {note.text[:200]}")
    if note.status_code != 201:
        return
    note_id = note.json()["id"]
    before = {source["id"] for source in client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()}

    promoted = client.post(f"/api/cases/{case_id}/notes/{note_id}/promote", headers=ANALYST)
    check("the note is promoted into evidence", promoted.status_code == 200,
          f"{promoted.status_code} {promoted.text[:300]}")
    sources = client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()
    minted = [source for source in sources if source["id"] not in before]
    check("promotion mints exactly one source", len(minted) == 1, f"{[s['id'] for s in minted]}")
    if minted:
        check("the minted source carries the note's text as blocks",
              bool(minted[0]["blocks"]), json.dumps(minted[0])[:200])
    check("promoting the same note twice mints nothing further",
          client.post(f"/api/cases/{case_id}/notes/{note_id}/promote", headers=ANALYST).status_code == 200
          and len(client.get(f"/api/cases/{case_id}/sources", headers=ANALYST).json()) == len(sources),
          "a replayed promotion changed the supplied set")

    run = client.post(f"/api/cases/{case_id}/runs",
                      json={"pathway": "EARNINGS_UPDATE", "depth": "screen", "focus_questions": []},
                      headers=ANALYST)
    check("a run pins the promoted note alongside the uploads", run.status_code == 201,
          f"{run.status_code} {run.text[:300]}")
    if run.status_code == 201:
        check("that run succeeds", wait_terminal(run.json()["id"]).get("status") == "succeeded")

    check("another desk's case is invisible, not merely forbidden",
          client.get(f"/api/cases/{case_id}", headers=head("stranger", "ANALYST")).status_code == 404)
    check("its notes are invisible too",
          client.get(f"/api/cases/{case_id}/notes", headers=head("stranger", "ANALYST")).status_code == 404)


def main() -> None:
    print(f"server: {client.get('/api/health').json()}")
    case_id = scenario_earnings_update()
    scenario_withdrawal()
    scenario_deliverable(case_id)
    scenario_model_readiness(case_id)
    scenario_relative_value_and_notes()
    print(f"\n{checks - len(failures)}/{checks} assertions passed")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(len(failures))


if __name__ == "__main__":
    main()
