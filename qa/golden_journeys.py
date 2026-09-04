#!/usr/bin/env python3
"""Six golden journeys over HTTP against a running CAOS stack (Task 13, ER-G10).

Drives, for each of the six pathways, the full chain the standard names:
documents in through ``POST /api/intake`` → source-disposition review
(``GET /api/cases/{id}/intake``) → execution (the Deep Research plan gate is
approved on its exact hash) → acceptance → model creation (``POST /models`` and
the worker) → analyst model sign-off → deliverable draft → analyst opinion
sign-off → freeze (worker-rendered md/pdf/xlsx) → separate approval by a
distinct approver → exact filed download of every format, digest-checked
against the frozen record → filing receipt → audit package → offline
verification with ``caos/server/caos/audit/verify_package.py``.

Every step records its HTTP status and typed code; a typed refusal is recorded,
never raised, and the journey continues with whatever the refusal still allows.
The script changes nothing in the repository and holds no secret: it reads the
dev-trusted ``x-caos-role``/``x-forwarded-user`` headers the candidate stack
serves under ``ENVIRONMENT=development``.

No HTTP route grants the first case membership (qa/INVENTORY.md), so the
distinct approver is provisioned by an operator action against the store with
``--database-url`` (recorded in the journey record as ``operator_bootstrap``)
or is assumed to exist when ``--approver-preprovisioned`` is given.

Usage:
  python golden_journeys.py --base-url http://127.0.0.1:18300 \
      --server-path caos/server --database-url postgresql+psycopg://… \
      --out journeys/ [--pathways FULL_CREDIT,…]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ANALYST = {"x-caos-role": "ANALYST", "x-forwarded-user": "journey-analyst"}
APPROVER_SUBJECT = "journey-approver"
APPROVER = {"x-caos-role": "APPROVER", "x-forwarded-user": APPROVER_SUBJECT}
ISSUER = "Northstar Holdings"
TEXT = "text/plain"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FORMATS = ("md", "pdf", "xlsx")
OPINION = {
    "opinion": "Hold: the credit remains adequately covered through the forecast horizon.",
    "limitations": "Covenant definitions were not disclosed in the supplied pack.",
    "material_overrides": "None",
    "rationale": "Leverage and liquidity conclusions rest on the cited annual and interim filings.",
}


# --- the synthetic packs (byte-identical to caos/tests/spec/test_intake_spec.py) ---


def annual_report(issuer: str = ISSUER, fiscal_year: int = 2024) -> bytes:
    return (
        f"{issuer}\nFORM 10-K\nANNUAL REPORT\n"
        f"For the fiscal year ended November 30, {fiscal_year}\n"
        f"{issuer} reports consolidated results for fiscal {fiscal_year}.\n"
        "Revenue 1,160\nEBITDA 222\nTotal debt 3,400\nCash and cash equivalents 410\n"
        "Item 7. Management's discussion and analysis of financial condition.\n"
    ).encode()


def quarterly_report(issuer: str = ISSUER, fiscal_year: int = 2025, quarter: int = 3) -> bytes:
    month = {1: "February 28", 2: "May 31", 3: "August 31", 4: "November 30"}[quarter]
    return (
        f"{issuer}\nFORM 10-Q\nQUARTERLY REPORT\n"
        f"For the quarterly period ended {month}, {fiscal_year}\n"
        f"Three months ended {month}, {fiscal_year}\n"
        "Revenue 310\nEBITDA 61\nNet debt 2,990\n"
    ).encode()


def earnings_release(issuer: str = ISSUER, fiscal_year: int = 2025) -> bytes:
    return (
        f"{issuer} Reports Third Quarter {fiscal_year} Results\n"
        f"EARNINGS RELEASE\nThree months ended August 31, {fiscal_year}\n"
        "Adjusted EBITDA 64\nNet yields increased 3.2 percent.\n"
    ).encode()


def guidance(issuer: str = ISSUER, fiscal_year: int = 2025) -> bytes:
    return (
        f"{issuer}\nBUSINESS UPDATE AND GUIDANCE\nFull year {fiscal_year} outlook\n"
        "Management forecast: adjusted EBITDA guidance of 250 to 260.\n"
    ).encode()


def credit_agreement(issuer: str = ISSUER) -> bytes:
    return (
        f"CREDIT AGREEMENT\ndated as of March 15, 2023\namong {issuer}, as Borrower,\n"
        "the Lenders party hereto and the Administrative Agent.\n"
        "Section 6.10 Financial Covenants. Term Loan B. Revolving Credit Facility.\n"
        "Maturity date: March 15, 2030.\n"
    ).encode()


def amendment(issuer: str = ISSUER) -> bytes:
    return (
        "AMENDMENT NO. 2 TO CREDIT AGREEMENT\ndated as of June 1, 2025\n"
        f"among {issuer}, as Borrower, and the Lenders.\nAmended and Restated Section 6.10.\n"
    ).encode()


def restructuring(issuer: str = ISSUER) -> bytes:
    return (
        f"{issuer}\nTRANSACTION SUPPORT AGREEMENT\n"
        "Exchange offer for the senior unsecured notes; restructuring support agreement\n"
        "with the ad hoc group of lenders. Forbearance through December 2025.\n"
    ).encode()


def research_brief() -> bytes:
    return json.dumps({
        "research_question": "How resilient is liquidity through the next refinancing?",
        "decision_context": "Committee review of an existing position.",
        "as_of_date": "2026-01-01",
        "time_horizon": "12 months",
        "must_answer": ["Nearest maturity"],
        "exclusions": [],
    }).encode()


def market_marks(server_path: Path) -> bytes:
    """The CP-3 sector workbook fixture the loan-universe importer accepts."""
    fixture = server_path.parent / "tests" / "fixtures" / "documents" / "REF_CP-3_Sector_RV.xlsx"
    return fixture.read_bytes()


def packs(server_path: Path, issuer: str) -> dict[str, list[tuple[str, bytes, str]]]:
    golden = [
        ("northstar-10k-fy2024.txt", annual_report(issuer), TEXT),
        ("northstar-10q-q3-2025.txt", quarterly_report(issuer), TEXT),
        ("northstar-credit-agreement.txt", credit_agreement(issuer), TEXT),
    ]
    return {
        "FULL_CREDIT": golden,
        "EARNINGS_UPDATE": [
            ("northstar-q3-earnings.txt", earnings_release(issuer), TEXT),
            ("northstar-guidance.txt", guidance(issuer), TEXT),
        ],
        "COVENANT_REFINANCING": [
            ("northstar-credit-agreement.txt", credit_agreement(issuer), TEXT),
            ("northstar-amendment-2.txt", amendment(issuer), TEXT),
        ],
        "RELATIVE_VALUE": [*golden, ("REF_CP-3_Sector_RV.xlsx", market_marks(server_path), XLSX)],
        "DISTRESSED_RESTRUCTURING": [*golden, ("northstar-tsa.txt", restructuring(issuer), TEXT)],
        "DEEP_RESEARCH": [*golden, ("research-brief.json", research_brief(), "application/json")],
    }


# --- HTTP ---------------------------------------------------------------------------


class Client:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def call(self, method: str, path: str, *, body: Any = None, headers: dict[str, str] | None = None,
             content_type: str = "application/json", raw: bytes | None = None) -> tuple[int, bytes, dict[str, str]]:
        h = dict(headers or ANALYST)
        data = None
        if raw is not None:
            data = raw
            h["Content-Type"] = content_type
        elif body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, response.read(), {k.lower(): v for k, v in response.headers.items()}
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}

    def json(self, method: str, path: str, **kwargs: Any) -> tuple[int, Any, dict[str, str]]:
        status, content, headers = self.call(method, path, **kwargs)
        try:
            return status, json.loads(content) if content else None, headers
        except json.JSONDecodeError:
            return status, {"_non_json": content[:200].decode("utf-8", "replace")}, headers


def multipart(files: list[tuple[str, bytes, str]], fields: dict[str, str] | None = None) -> tuple[bytes, str]:
    boundary = "----caos-golden-journey"
    out = io.BytesIO()
    for name, content, content_type in files:
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{name}\"\r\n"
                  f"Content-Type: {content_type}\r\n\r\n".encode())
        out.write(content)
        out.write(b"\r\n")
    for key, value in (fields or {}).items():
        out.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def typed_code(payload: Any) -> str | None:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return detail.get("code")
        if isinstance(payload.get("error"), dict):
            return payload["error"].get("code")
        if isinstance(payload.get("refusal"), dict):
            return payload["refusal"].get("code")
    return None


# --- the journey ---------------------------------------------------------------------


class Journey:
    def __init__(self, client: Client, pathway: str, out_dir: Path, args: argparse.Namespace) -> None:
        self.client = client
        self.pathway = pathway
        self.out = out_dir / pathway
        self.out.mkdir(parents=True, exist_ok=True)
        self.args = args
        self.steps: list[dict[str, Any]] = []
        self.case_id: str | None = None

    def record(self, step: str, status: int | None, payload: Any = None, **extra: Any) -> dict[str, Any]:
        entry = {"step": step, "at": datetime.now(UTC).isoformat(), "http_status": status,
                 "typed_code": typed_code(payload), **extra}
        self.steps.append(entry)
        return entry

    def retain(self, name: str, content: bytes) -> str:
        path = self.out / name
        path.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    def wait_run(self, run_id: str, budget_seconds: float) -> dict[str, Any]:
        deadline = time.monotonic() + budget_seconds
        run: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, run, _ = self.client.json("GET", f"/api/runs/{run_id}")
            if status != 200:
                return {"status": "unreachable", "http_status": status}
            if run["status"] in {"succeeded", "failed", "paused"}:
                return run
            time.sleep(2)
        return run

    def run(self, files: list[tuple[str, bytes, str]], case_id: str | None = None) -> dict[str, Any]:
        c = self.client
        # 1. documents in — the only analytical input. The overlay pathways drop
        # into the Full Credit case (their model effect needs its validated model).
        body, content_type = multipart(files, {"case_id": case_id} if case_id else None)
        status, intake, _ = c.json("POST", "/api/intake", raw=body, content_type=content_type)
        self.record("intake", status, intake, intake_status=(intake or {}).get("status"),
                    route=(intake or {}).get("route"), refusal=(intake or {}).get("refusal"))
        # 201 = admitted and started; 200 = the same pack re-dropped converges
        # on the existing intake and run (idempotent), which the journey reuses.
        if status not in {200, 201} or not isinstance(intake, dict) or intake.get("run") is None:
            return self.finish("intake did not start a run")
        self.case_id = intake["case_id"]
        run_id = intake["run"]["id"]
        # 2. source-disposition review (served as labelled machine suggestions)
        status, review, _ = c.json("GET", f"/api/cases/{self.case_id}/intake")
        self.record("disposition_review", status, review, dispositions={
            d["filename"]: {"disposition": d["disposition"], "document_type": d["document_type"], "reason": d["reason"]}
            for d in (review or {}).get("documents", [])
        })
        # 3. execution (Deep Research parks on its plan; approve the exact proposed hash)
        run = self.wait_run(run_id, self.args.run_budget)
        if run.get("status") == "paused" and (run.get("error") or {}).get("code") == "PLAN_APPROVAL_REQUIRED":
            status, plan, _ = c.json("GET", f"/api/runs/{run_id}/research-plan")
            self.record("research_plan", status, plan, proposed_plan_hash=(plan or {}).get("proposed_plan_hash"))
            status, approved, _ = c.json("POST", f"/api/runs/{run_id}/research-plan/approve",
                                         body={"plan_hash": plan["proposed_plan_hash"]})
            self.record("research_plan_approve", status, approved)
            run = self.wait_run(run_id, self.args.run_budget)
        self.record("execution", 200 if run.get("status") else None, run, run_status=run.get("status"),
                    error=run.get("error"), nodes=[f"{n['module_id']}:{n['status']}" for n in run.get("nodes", [])])
        if run.get("status") != "succeeded":
            return self.finish("run did not succeed")
        # 4. acceptance (a human action; never on the analyst's behalf)
        status, snapshot, _ = c.json("POST", f"/api/runs/{run_id}/accept")
        self.record("accept", status, snapshot, snapshot_id=(snapshot or {}).get("id"))
        if status != 200:
            return self.finish("acceptance refused")
        # 5. model creation or update
        status, readiness, _ = c.json("GET", f"/api/cases/{self.case_id}/model")
        self.record("model_readiness", status, readiness, readiness_status=(readiness or {}).get("status"),
                    blockers=(readiness or {}).get("blockers"))
        status, queued, _ = c.json("POST", f"/api/cases/{self.case_id}/models")
        self.record("model_queue", status, queued)
        build = None
        if status == 202:
            build_id = queued["build"]["id"]
            deadline = time.monotonic() + self.args.worker_budget
            while time.monotonic() < deadline:
                status, build, _ = c.json("GET", f"/api/cases/{self.case_id}/models/{build_id}")
                if (build or {}).get("status") in {"READY", "FAILED"}:
                    break
                time.sleep(3)
            self.record("model_build", status, build, build_status=(build or {}).get("status"),
                        error=(build or {}).get("error"))
        model_selection = None
        if build and build.get("status") == "READY":
            status, registry, _ = c.json("GET", f"/api/cases/{self.case_id}/models/assumption-registry?build_id={build['id']}")
            self.record("assumption_registry", status, registry)
            preview_request = {"build_id": build["id"], "parent_revision_id": None,
                               "registry_version": registry["version"], "registry_digest": registry["digest"],
                               "assumptions": registry["defaults"], "draft_generation": 0}
            status, preview, _ = c.json("POST", f"/api/cases/{self.case_id}/models/previews", body=preview_request)
            self.record("model_preview", status, preview, preview_digest=(preview or {}).get("preview_digest"))
            if status == 200:
                status, signed, _ = c.json("POST", f"/api/cases/{self.case_id}/model-revisions/sign-off", body={
                    **preview_request, "preview_digest": preview["preview_digest"],
                    "expected_head_revision_id": None, "note": "Golden journey: signed on the registry defaults.",
                })
                self.record("model_sign_off", status, signed, revision_id=(signed or {}).get("id"))
                if status == 201:
                    model_selection = {"kind": "ANALYST_REVISION", "build_id": build["id"], "revision_id": signed["id"]}
        # 6. deliverable draft
        url = f"/api/cases/{self.case_id}/deliverables/{self.pathway}"
        status, workspace, _ = c.json("GET", f"{url}/draft")
        self.record("deliverable_workspace", status, workspace,
                    model_requirement=((workspace or {}).get("template") or {}).get("model_requirement"),
                    model_eligibility=(workspace or {}).get("model_eligibility"))
        if status != 200:
            return self.finish("deliverable workspace unavailable")
        template = workspace["template"]
        source_id = next(d["source_id"] for d in review["documents"] if d["disposition"] == "used")
        blocks = []
        for item in template["blocks"]:
            base = {"block_id": item["block_id"], "slot_id": item["slot_id"]}
            if item["kind"] == "NARRATIVE":
                blocks.append({**base, "kind": "NARRATIVE", "text": "Leverage is manageable.",
                               "content_mode": "ANALYST_JUDGMENT", "citations": []})
            elif item["kind"] == "EVIDENCE_REGISTER":
                blocks.append({**base, "kind": "EVIDENCE_REGISTER", "citations": [
                    {"source_id": source_id, "block_ids": ["b00001"], "claim": "Pinned evidence line supports the opinion."}]})
            elif item["kind"] == "LIMITATIONS":
                blocks.append({**base, "kind": "LIMITATIONS", "text": "Scope-limited review.", "citations": []})
        draft_body = {"expected_version": 0, "template_id": template["template_id"],
                      "template_version": template["template_version"], "model_selection": model_selection,
                      "blocks": blocks}
        status, saved, _ = c.json("PUT", f"{url}/draft", body=draft_body)
        self.record("deliverable_draft", status, saved, draft_version=((saved or {}).get("current") or {}).get("version"))
        if status not in {200, 201}:
            return self.finish("draft refused")
        revision = saved["current"]
        # 7. analyst opinion sign-off on the exact revision
        status, opinion, _ = c.json("POST", f"{url}/opinion", body={
            "draft_id": revision["draft_id"], "draft_version": revision["version"], "draft_digest": revision["digest"],
            "expected_head_opinion_id": None, **OPINION})
        self.record("opinion_sign_off", status, opinion, opinion_id=(opinion or {}).get("opinion_id"))
        if status not in {200, 201}:
            return self.finish("opinion refused")
        # 8. freeze: queued here, rendered and published by the worker
        status, job, _ = c.json("POST", f"{url}/freeze", body={
            "draft_id": revision["draft_id"], "draft_version": revision["version"], "draft_digest": revision["digest"]})
        self.record("freeze_request", status, job, job_id=(job or {}).get("job_id"))
        if status not in {200, 202}:
            return self.finish("freeze refused")
        frozen = None
        deadline = time.monotonic() + self.args.worker_budget
        while time.monotonic() < deadline:
            status, tracked, _ = c.json("GET", f"/api/cases/{self.case_id}/deliverables/freeze-jobs/{job['job_id']}")
            if (tracked or {}).get("status") in {"FROZEN", "FAILED", "CONFLICT"}:
                break
            time.sleep(3)
        self.record("freeze_job", status, tracked, job_status=(tracked or {}).get("status"), error=(tracked or {}).get("error"))
        status, workspace, _ = c.json("GET", f"{url}/draft")
        frozen = next((f for f in (workspace or {}).get("frozen_history", []) if f.get("status") in {"FROZEN", "FILED"}), None)
        self.record("frozen_record", status, workspace, frozen=frozen and {k: frozen.get(k) for k in (
            "id", "deliverable_id", "status", "preview_digest", "input_fingerprint", "opinion_id", "signed_by", "frozen_by", "exports")})
        if not frozen:
            return self.finish("no frozen record")
        deliverable_id = frozen.get("deliverable_id") or frozen.get("id")
        # 9. separation of duties: the signer cannot file; a distinct approver files
        status, refused, _ = c.json("POST", f"/api/cases/{self.case_id}/deliverables/by-id/{deliverable_id}/approve",
                                    body={"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]},
                                    headers={"x-caos-role": "APPROVER", "x-forwarded-user": ANALYST["x-forwarded-user"]})
        self.record("filing_by_signer_refused", status, refused)
        self.provision_approver()
        status, filed, _ = c.json("POST", f"/api/cases/{self.case_id}/deliverables/by-id/{deliverable_id}/approve",
                                  body={"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]},
                                  headers=APPROVER)
        self.record("filing", status, filed, filed_status=(filed or {}).get("status"), approved_by=(filed or {}).get("approved_by"))
        if status != 200:
            return self.finish("filing refused")
        # 10. filing receipt (detached, immutable)
        status, receipt, _ = c.json("GET", f"/api/cases/{self.case_id}/deliverables/by-id/{deliverable_id}/receipt")
        self.record("receipt", status, receipt, receipt_digest=(receipt or {}).get("receipt_digest"))
        if status == 200:
            self.retain("filing-receipt.json", json.dumps(receipt, indent=1, sort_keys=True).encode())
        # 11. exact filed download of every format, digest-checked against the frozen record
        exports = {}
        for fmt in FORMATS:
            status, content, headers = c.call("GET", f"/api/cases/{self.case_id}/deliverables/by-id/{deliverable_id}/export/{fmt}")
            digest = hashlib.sha256(content).hexdigest()
            expected = ((frozen.get("exports") or {}).get(fmt) or {}).get("sha256")
            served = headers.get("x-caos-sha256")
            exact = status == 200 and digest == expected == served
            exports[fmt] = {"http_status": status, "sha256": digest, "expected": expected, "served_header": served, "exact": exact,
                            "bytes": len(content)}
            if status == 200:
                self.retain(f"filed.{fmt}", content)
            self.record(f"filed_download_{fmt}", status, None, **exports[fmt])
        # 12. audit package and offline verification
        status, package, _ = c.call("GET", f"/api/cases/{self.case_id}/audit-package")
        self.record("audit_package", status, None, bytes=len(package), sha256=hashlib.sha256(package).hexdigest())
        if status == 200:
            path = self.out / "audit-package.zip"
            path.write_bytes(package)
            verifier = Path(self.args.server_path) / "caos" / "audit" / "verify_package.py"
            proc = subprocess.run([sys.executable, str(verifier), str(path), "--json"], capture_output=True, text=True)
            report = None
            try:
                report = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None
            except json.JSONDecodeError:
                report = {"_stdout": proc.stdout[-500:]}
            self.retain("verify_package.json", json.dumps(report, indent=1, sort_keys=True).encode())
            self.record("offline_verification", None, None, exit_code=proc.returncode, ok=(report or {}).get("ok"),
                        checked=(report or {}).get("checked"), findings=(report or {}).get("findings"))
        return self.finish("complete")

    def provision_approver(self) -> None:
        """No HTTP route grants the first case membership; the operator does it."""
        if self.args.approver_preprovisioned:
            self.record("operator_bootstrap", None, None, note="approver assumed pre-provisioned by the operator")
            return
        if not self.args.database_url:
            self.record("operator_bootstrap", None, None, note="no --database-url: approver not provisioned")
            return
        sys.path.insert(0, str(Path(self.args.server_path).resolve()))
        from caos.storage.store import DomainStore  # type: ignore

        store = DomainStore.from_url(self.args.database_url)
        try:
            granted = store.add_member(self.case_id, ANALYST["x-forwarded-user"], APPROVER_SUBJECT, "APPROVER", actor_role="ADMIN")
        finally:
            store.close()
        self.record("operator_bootstrap", None, None, granted=granted, member=APPROVER_SUBJECT, role="APPROVER",
                    note="operator action against the store (no HTTP route grants the first case membership)")

    def finish(self, outcome: str) -> dict[str, Any]:
        record = {"pathway": self.pathway, "case_id": self.case_id, "outcome": outcome, "steps": self.steps}
        (self.out / "journey.json").write_text(json.dumps(record, indent=1, sort_keys=True))
        return record


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--server-path", required=True, help="path to caos/server (verify_package.py, fixtures)")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""),
                        help="store URL for the operator bootstrap of the distinct approver")
    parser.add_argument("--approver-preprovisioned", action="store_true")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pathways", default="FULL_CREDIT,EARNINGS_UPDATE,COVENANT_REFINANCING,RELATIVE_VALUE,DISTRESSED_RESTRUCTURING,DEEP_RESEARCH")
    parser.add_argument("--issuer", default=ISSUER, help="issuer named by every document (one case per issuer per analyst)")
    parser.add_argument("--run-budget", type=float, default=900.0)
    parser.add_argument("--worker-budget", type=float, default=600.0)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    client = Client(args.base_url)
    status, health, _ = client.json("GET", "/api/health", headers={})
    summary: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(), "base_url": args.base_url,
        "health": {"http_status": status, "body": health}, "journeys": {},
    }
    server_path = Path(args.server_path)
    shared_case: str | None = None
    for pathway in args.pathways.split(","):
        files = packs(server_path, args.issuer)[pathway]
        record = Journey(client, pathway, out, args).run(files, case_id=shared_case)
        if record["case_id"] and shared_case is None:
            shared_case = record["case_id"]
        summary["journeys"][pathway] = {
            "case_id": record["case_id"], "outcome": record["outcome"],
            "steps": [{k: s.get(k) for k in ("step", "http_status", "typed_code")} for s in record["steps"]],
        }
        print(f"{pathway}: {record['outcome']} — " + ", ".join(
            f"{s['step']}={s.get('http_status')}{'/' + s['typed_code'] if s.get('typed_code') else ''}" for s in record["steps"]))
    summary["finished_at"] = datetime.now(UTC).isoformat()
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))
    complete = sum(1 for j in summary["journeys"].values() if j["outcome"] == "complete")
    print(f"{complete}/{len(summary['journeys'])} journeys complete through offline verification")
    return 0 if complete == len(summary["journeys"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
