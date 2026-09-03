#!/usr/bin/env python3
"""Capacity harness for the declared enterprise profile (ENTERPRISE_TESTING_
READINESS "Test the declared enterprise profile", PERF-001–015, SEC-012; Phase
6 items 10–13).

Four commands, one HTTP client, no framework:

    capacity.py limits   --url URL [--edge-url URL] [--out limits.json]
    capacity.py profile  --url URL --subjects 25 --jobs 20 --streams 4 --previews 2
                         --rpm 300 --cases 100 --documents 100 --duration SECONDS
                         [--compose-project NAME] [--restart-every SECONDS
                         --restart-command CMD] --out DIR
    capacity.py baseline --url URL --out baseline.json
    capacity.py compare  BEFORE.json AFTER.json

`limits` runs one below, one exactly-at and one above probe for every
admission and size ceiling the application declares (request rate, event
streams, model previews, active jobs, source bytes, request bytes, intake file
count, manifest rows) and reports whether above-limit work was refused before
the application spent anything on it. It is safe to run against a development
server bound to the host-control provider; the numbers it records describe
that server. `profile` drives the declared enterprise profile (25 subjects, 20
active jobs, four streams and two previews per subject, 300 requests per
subject per minute, 100 cases of 100 documents, 25 MiB sources, 32 MiB
requests) and retains latency, throughput, error classes, cross-case leakage
checks and — when `--compose-project` names the running stack — CPU, memory,
database connections, checkpoint and vault growth. With `--duration 28800`,
`--restart-every` and `--restart-command` it is the eight-hour soak (PERF-013);
`baseline` and `compare` are the pre- and post-soak authority comparison
(PERF-015). The full profile, the mixed workload and the soak are candidate
evidence only (Task 13): nothing this file measures is a production capacity or
availability claim.

Identity: with CAOS_EDGE_SECRET set the harness speaks the production edge
contract (x-edge-authorization + x-forwarded-user/-email/-groups); otherwise
the development role headers. Every subject is `capacity-<n>@caos.invalid`.

ponytail: httpx + threads, JSON out, plain asserts; add a metrics sink when a
second consumer of these numbers exists.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shlex
import statistics
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

MIB = 1024 * 1024
DECLARED = {
    "subjects": 25, "jobs": 20, "streams": 4, "previews": 2, "rpm": 300,
    "cases": 100, "documents": 100, "source_bytes": 25 * MIB, "request_bytes": 32 * MIB,
    "intake_files": 40, "manifest_rows": 2_000,
}
MAX_BLOCKS_PER_SOURCE = 320   # sources/domain.py: one block per line up to here
EDGE_SECRET = os.getenv("CAOS_EDGE_SECRET", "")


# --- identity and transport -----------------------------------------------------------

def headers(subject: str, groups: str = "caos-analyst", role: str = "ANALYST") -> dict[str, str]:
    email = f"{subject}@caos.invalid"
    if EDGE_SECRET:
        return {"x-edge-authorization": EDGE_SECRET, "x-forwarded-user": email,
                "x-forwarded-email": email, "x-forwarded-groups": groups}
    return {"x-caos-role": role, "x-forwarded-user": email, "x-forwarded-email": email}


def client(url: str, timeout: float = 120.0) -> httpx.Client:
    return httpx.Client(base_url=url, timeout=timeout)


class Stopwatch:
    """Per-class latency samples and error classes, thread-safe."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.samples: dict[str, list[float]] = {}
        self.statuses: dict[str, dict[str, int]] = {}

    def record(self, kind: str, started: float, status: int | str) -> None:
        with self.lock:
            self.samples.setdefault(kind, []).append(time.perf_counter() - started)
            bucket = self.statuses.setdefault(kind, {})
            bucket[str(status)] = bucket.get(str(status), 0) + 1

    def summary(self) -> dict[str, dict]:
        with self.lock:
            return {
                kind: {
                    "count": len(values),
                    "p50_ms": round(statistics.median(values) * 1000, 1),
                    "p95_ms": round(sorted(values)[max(0, int(len(values) * 0.95) - 1)] * 1000, 1),
                    "max_ms": round(max(values) * 1000, 1),
                    "statuses": self.statuses.get(kind, {}),
                }
                for kind, values in self.samples.items() if values
            }


def timed(watch: Stopwatch, kind: str, call):
    started = time.perf_counter()
    try:
        response = call()
    except httpx.HTTPError as exc:
        watch.record(kind, started, type(exc).__name__)
        raise
    watch.record(kind, started, response.status_code)
    return response


# --- documents --------------------------------------------------------------------------

def text_document(tag: str, lines: int = 12) -> bytes:
    body = [f"{tag} annual report", "Revenue 1,250 million; EBITDA 310 million; net debt 900 million."]
    body += [f"Note {index}: {tag} covenant headroom line {index}." for index in range(lines - 2)]
    return ("\n".join(body[:lines]) + "\n").encode()


def padded_pdf(size: int) -> bytes:
    """A PDF of exactly `size` bytes with no text layer: the padding is a
    content-stream comment, so extraction stores the textless placeholder and
    the byte ceiling is the only thing the upload exercises."""
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, StreamObject

    pad = max(size - 1_200, 16)
    for _ in range(6):
        writer = PdfWriter()
        page = writer.add_blank_page(width=200, height=200)
        stream = StreamObject()
        stream._data = b"% " + b"x" * pad + b"\n"
        page[NameObject("/Contents")] = writer._add_object(stream)
        buffer = io.BytesIO()
        writer.write(buffer)
        data = buffer.getvalue()
        if len(data) == size:
            return data
        pad += size - len(data)
    raise RuntimeError(f"could not pad a PDF to exactly {size} bytes (got {len(data)})")


# --- fixtures over the API ----------------------------------------------------------------

def create_case(http: httpx.Client, who: dict[str, str], name: str) -> dict:
    response = http.post("/api/cases", json={"name": name, "issuer": f"{name} Holdings", "sector": "Services"}, headers=who)
    response.raise_for_status()
    return response.json()


def upload(http: httpx.Client, who: dict[str, str], case_id: str, filename: str, content: bytes,
           media_type: str = "text/plain") -> httpx.Response:
    return http.post(f"/api/cases/{case_id}/sources", files={"file": (filename, content, media_type)}, headers=who)


def start_run(http: httpx.Client, who: dict[str, str], case_id: str, pathway: str = "FULL_CREDIT",
              depth: str = "screen") -> httpx.Response:
    return http.post(f"/api/cases/{case_id}/runs", json={"pathway": pathway, "depth": depth}, headers=who)


def wait_terminal(http: httpx.Client, who: dict[str, str], run_id: str, timeout: float = 600.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = http.get(f"/api/runs/{run_id}", headers=who)
        run = response.json()
        if "status" not in run:
            raise RuntimeError(f"run {run_id} unreadable for this subject: {response.status_code} {response.text[:120]}")
        if run["status"] in {"succeeded", "failed", "paused"}:
            return run
        time.sleep(1.0)
    raise TimeoutError(run_id)


# --- limits -------------------------------------------------------------------------------

def limit_rate(http: httpx.Client, out: list[dict]) -> None:
    who = headers("capacity-rate")
    declared = DECLARED["rpm"]
    with ThreadPoolExecutor(max_workers=32) as pool:
        burst = list(pool.map(lambda _: http.get("/api/me", headers=who).status_code, range(declared)))
        above = list(pool.map(lambda _: http.get("/api/me", headers=who).status_code, range(30)))
    other = http.get("/api/me", headers=headers("capacity-rate-other")).status_code
    refused = above.count(429)
    out.append({
        "limit": "requests per subject per minute", "declared": declared,
        "below_and_at": {"sent": declared, "admitted": burst.count(200), "refused": burst.count(429)},
        "above": {"sent": 30, "refused": refused, "note": "the bucket refills at declared/60 per second, so a few of the 30 may be admitted"},
        "other_subject": other,
        "verdict": "PASS" if burst.count(429) == 0 and refused >= 1 and other == 200 else "FAIL",
    })


def limit_streams(http: httpx.Client, url: str, out: list[dict], run_id: str, who: dict[str, str]) -> None:
    """Four tails for one subject, the fifth refused, a second subject's tail on
    its own run admitted while the first is saturated (the other subject must
    own a run it can see: a stream on someone else's run is the 404 the
    authorization matrix requires, not a ceiling observation)."""
    declared = DECLARED["streams"]
    other_who = headers("capacity-stream-other")
    other_case = create_case(http, other_who, "Capacity streams other")
    assert upload(http, other_who, other_case["id"], "seed.txt", text_document("Streams Holdings")).status_code == 201
    other_started = start_run(http, other_who, other_case["id"])
    assert other_started.status_code == 201, other_started.text
    other_run_id = other_started.json()["id"]
    opened: list[httpx.Response] = []
    held = [client(url, timeout=None) for _ in range(declared + 1)]
    try:
        for index in range(declared):
            response = held[index].send(held[index].build_request("GET", f"/api/runs/{run_id}/events", headers=who), stream=True)
            opened.append(response)
        at = [response.status_code for response in opened]
        above = held[declared].send(held[declared].build_request("GET", f"/api/runs/{run_id}/events", headers=who), stream=True)
        above_status = above.status_code
        above.close()
        other = client(url, timeout=None)
        other_response = other.send(other.build_request("GET", f"/api/runs/{other_run_id}/events", headers=other_who), stream=True)
        other_status = other_response.status_code
    finally:
        for response in opened:
            response.close()
        for holder in held:
            holder.close()
    # A closed stream returns its slot: the next open for the same subject is admitted.
    again = client(url, timeout=None)
    again_response = again.send(again.build_request("GET", f"/api/runs/{run_id}/events", headers=who), stream=True)
    again_status = again_response.status_code
    again_response.close()
    again.close()
    other_response.close()
    other.close()
    out.append({
        "limit": "event streams per subject", "declared": declared,
        "below_and_at": at, "above": above_status, "other_subject": other_status, "after_release": again_status,
        "verdict": "PASS" if at == [200] * declared and above_status == 429 and other_status == 200 and again_status == 200 else "FAIL",
    })


def limit_previews(http: httpx.Client, out: list[dict], case_id: str, who: dict[str, str]) -> None:
    """The preview slot is held only while the server computes; against a case
    with no READY build the route refuses in microseconds, so the concurrency
    window is not reliably observable over HTTP. The exact at/above proof is
    the in-process test named below; this records what HTTP showed."""
    declared = DECLARED["previews"]
    body = {"build_id": "capacity-no-build", "registry_version": "capacity", "registry_digest": "0" * 64,
            "assumptions": [{"assumption_id": "capacity", "case": "BASE", "period_id": "FY2026", "unit": "x", "status": "READY", "value": 1}]}
    with ThreadPoolExecutor(max_workers=declared + 1) as pool:
        statuses = list(pool.map(lambda _: http.post(f"/api/cases/{case_id}/models/previews", json=body, headers=who).status_code, range(declared + 1)))
    out.append({
        "limit": "model previews per subject", "declared": declared,
        "observed_statuses": statuses,
        "proof": "caos/tests/spec/test_limits_spec.py::test_preview_ceiling_at_and_above_is_per_subject_and_returned",
        "verdict": "IN_PROCESS_PROOF" if 429 not in statuses else "PASS",
    })


def limit_jobs(http: httpx.Client, out: list[dict], cases: list[tuple[dict[str, str], str]]) -> None:
    """Start more runs than the instance admits at once; the surplus is refused
    typed (409 ADMISSION_BUSY) and admitted runs still complete."""
    declared = DECLARED["jobs"]
    started_at = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(cases)) as pool:
        responses = list(pool.map(lambda pair: start_run(http, pair[0], pair[1], depth="full"), cases))
    burst_seconds = time.monotonic() - started_at
    admitted = [(who, r.json()["id"]) for (who, _case), r in zip(cases, responses) if r.status_code == 201]
    refused = [r.json().get("detail") for r in responses if r.status_code == 409]
    other = [r.status_code for r in responses if r.status_code not in {201, 409}]
    completed = 0
    for who, run_id in admitted:
        if wait_terminal(http, who, run_id)["status"] in {"succeeded", "failed", "paused"}:
            completed += 1
    out.append({
        "limit": "active jobs per instance", "declared": declared,
        "sent": len(cases), "admitted": len(admitted), "refused_typed": len(refused), "other_statuses": other,
        "burst_seconds": round(burst_seconds, 2), "admitted_runs_reached_a_terminal_state": completed,
        "refusal": refused[0] if refused else None,
        "verdict": "PASS" if len(admitted) <= declared and refused and all(d == {"code": "ADMISSION_BUSY"} for d in refused) and not other and completed == len(admitted) else "FAIL",
        "note": "admitted may be below the declared ceiling when a run finished inside the burst window",
    })


def limit_source_size(http: httpx.Client, out: list[dict], case_id: str, who: dict[str, str], edge: httpx.Client | None) -> None:
    declared = DECLARED["source_bytes"]
    results = {}
    for label, size in (("below", 1024), ("at", declared), ("above", declared + 1)):
        response = upload(http, who, case_id, f"pad-{label}.pdf", padded_pdf(size), "application/pdf")
        results[label] = {"bytes": size, "status": response.status_code, "detail": response.json().get("detail") if response.status_code != 201 else None}
    out.append({
        "limit": "source bytes", "declared": declared, **results,
        "verdict": "PASS" if results["below"]["status"] == 201 and results["at"]["status"] == 201 and results["above"]["status"] == 413 else "FAIL",
    })
    declared = DECLARED["request_bytes"]
    if edge is None:
        out.append({"limit": "request bytes", "declared": declared, "verdict": "NOT_EXERCISED",
                    "note": "the request-body ceiling is the edge's (Caddy max_size); pass --edge-url to probe it"})
        return
    results = {}
    for label, size in (("below", 1024), ("at", declared), ("above", declared + 1)):
        # A multipart body of the requested size whose file is under the source cap.
        boundary = "capacityboundary"
        head = f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"pad.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        file_size = min(size - len(head) - len(tail), DECLARED["source_bytes"])
        body = head + padded_pdf(file_size) + tail
        body = body + b" " * (size - len(body)) if len(body) < size else body
        response = edge.post(f"/api/cases/{case_id}/sources", content=body,
                             headers={**who, "content-type": f"multipart/form-data; boundary={boundary}"})
        results[label] = {"bytes": len(body), "status": response.status_code}
    out.append({
        "limit": "request bytes", "declared": declared, **results,
        "verdict": "PASS" if results["above"]["status"] == 413 and results["below"]["status"] in {201, 422} and results["at"]["status"] != 413 else "FAIL",
    })


def limit_intake_files(http: httpx.Client, out: list[dict]) -> None:
    declared = DECLARED["intake_files"]
    who = headers("capacity-intake")
    before = len(http.get("/api/cases", headers=who).json())
    results = {}
    for label, count in (("below", declared - 1), ("at", declared), ("above", declared + 1)):
        tag = f"Intake{label.title()}"
        files = [("files", (f"{tag}-{index:02d}.txt", text_document(f"{tag} Holdings", 8 + index % 5), "text/plain")) for index in range(count)]
        response = http.post("/api/intake", files=files, headers=who)
        detail = response.json().get("detail") if response.status_code >= 400 else None
        results[label] = {"files": count, "status": response.status_code,
                          "code": detail.get("code") if isinstance(detail, dict) else None}
    after = len(http.get("/api/cases", headers=who).json())
    out.append({
        "limit": "documents per intake", "declared": declared, **results, "cases_created": after - before,
        "verdict": "PASS" if results["above"]["code"] == "INTAKE_TOO_MANY_FILES" and results["at"]["code"] != "INTAKE_TOO_MANY_FILES"
        and results["below"]["code"] != "INTAKE_TOO_MANY_FILES" else "FAIL",
        "note": "at and below may still refuse typed for another reason (issuer ambiguity, clarification); only the file-count code is asserted",
    })


def limit_manifest_rows(http: httpx.Client, out: list[dict]) -> None:
    """Rows = sources + blocks. Eight documents of 249 lines (250 rows each)
    reach exactly 2 000; one more one-line document takes the run to 2 002 and
    the first module refuses typed before its provider call."""
    declared = DECLARED["manifest_rows"]
    who = headers("capacity-manifest")
    results = {}
    for label, extra in (("at", 0), ("above", 1)):
        case = create_case(http, who, f"Manifest {label}")
        per_document = declared // 8 - 1
        for index in range(8):
            lines = "\n".join(f"Manifest {label} document {index} line {line}: revenue 1" for line in range(per_document)) + "\n"
            response = upload(http, who, case["id"], f"manifest-{index}.txt", lines.encode())
            assert response.status_code == 201, response.text
            assert len(response.json()["blocks"]) == per_document, (len(response.json()["blocks"]), per_document)
        for index in range(extra):
            assert upload(http, who, case["id"], f"extra-{index}.txt", b"one more line\n").status_code == 201
        started = start_run(http, who, case["id"])
        run = wait_terminal(http, who, started.json()["id"]) if started.status_code == 201 else None
        results[label] = {"rows": 8 * (per_document + 1) + 2 * extra, "start_status": started.status_code,
                          "run_status": run["status"] if run else None, "error": (run or {}).get("error")}
    out.append({
        "limit": "manifest rows per run", "declared": declared, **results,
        "verdict": "PASS" if results["at"]["run_status"] in {"succeeded", "paused"}
        and results["above"]["run_status"] == "failed" and (results["above"]["error"] or {}).get("code") == "AGENT_BUDGET_EXCEEDED" else "FAIL",
    })


def limits(args: argparse.Namespace) -> int:
    http = client(args.url)
    edge = client(args.edge_url) if args.edge_url else None
    out: list[dict] = []
    who = headers("capacity-limits")
    case = create_case(http, who, "Capacity limits")
    assert upload(http, who, case["id"], "seed.txt", text_document("Capacity Holdings")).status_code == 201
    started = start_run(http, who, case["id"])
    assert started.status_code == 201, started.text
    run_id = started.json()["id"]
    limit_rate(http, out)
    limit_streams(http, args.url, out, run_id, who)
    limit_previews(http, out, case["id"], who)
    job_cases = []
    for index in range(DECLARED["jobs"] + 5):
        actor = headers(f"capacity-job-{index}")
        job_case = create_case(http, actor, f"Capacity job {index}")
        assert upload(http, actor, job_case["id"], "seed.txt", text_document(f"Job{index} Holdings", 40)).status_code == 201
        job_cases.append((actor, job_case["id"]))
    limit_jobs(http, out, job_cases)
    limit_source_size(http, out, case["id"], who, edge)
    limit_intake_files(http, out)
    limit_manifest_rows(http, out)
    payload = {"schema_version": "caos.capacity-limits.v1", "url": args.url, "edge_url": args.edge_url,
               "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "declared": DECLARED, "limits": out}
    Path(args.out).write_text(json.dumps(payload, indent=2) + "\n")
    failed = [item["limit"] for item in out if item["verdict"] == "FAIL"]
    for item in out:
        print(f"{item['verdict']:>17}  {item['limit']} (declared {item['declared']})")
    print(f"written {args.out}")
    return 1 if failed else 0


# --- profile and soak -----------------------------------------------------------------------

def docker_stats(project: str) -> dict:
    """Resource sample from the running Compose project (PERF-012)."""
    stats = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], capture_output=True, text=True, check=False)
    rows = [json.loads(line) for line in stats.stdout.splitlines() if line.strip()]
    sample = {row["Name"]: {"cpu": row["CPUPerc"], "memory": row["MemUsage"]} for row in rows if row["Name"].startswith(project)}
    connections = subprocess.run(["docker", "compose", "-p", project, "exec", "-T", "db", "psql", "-Atq", "-U", "caos", "-d", "caos",
                                  "-c", "SELECT count(*) FROM pg_stat_activity"], capture_output=True, text=True, check=False)
    vault = subprocess.run(["docker", "compose", "-p", project, "exec", "-T", "app", "sh", "-c",
                            "du -sk /vault | cut -f1; stat -c %s /vault/checkpoints.db 2>/dev/null || echo 0"],
                           capture_output=True, text=True, check=False)
    vault_lines = vault.stdout.split()
    sample["db_connections"] = int(connections.stdout.strip() or 0)
    sample["vault_kib"] = int(vault_lines[0]) if vault_lines else None
    sample["checkpoints_bytes"] = int(vault_lines[1]) if len(vault_lines) > 1 else None
    return sample


def profile(args: argparse.Namespace) -> int:
    http = client(args.url)
    watch = Stopwatch()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    subjects = [f"capacity-{index}" for index in range(args.subjects)]
    who = {subject: headers(subject) for subject in subjects}
    leakage: list[str] = []
    stop = threading.Event()

    # Seed: cases and documents spread across subjects; a seeded case is the
    # unit of isolation, so every case belongs to exactly one subject.
    seeded: dict[str, list[str]] = {subject: [] for subject in subjects}
    seed_started = time.monotonic()

    def seed_case(index: int) -> None:
        subject = subjects[index % len(subjects)]
        case = create_case(http, who[subject], f"Profile case {index}")
        for document in range(args.documents):
            size = DECLARED["source_bytes"] if args.large_every and document % args.large_every == 0 else None
            content = padded_pdf(size) if size else text_document(f"Profile{index} Holdings", 12 + document % 20)
            name = f"doc-{document:03d}.{'pdf' if size else 'txt'}"
            response = timed(watch, "upload", lambda: upload(http, who[subject], case["id"], name, content, "application/pdf" if size else "text/plain"))
            if response.status_code != 201:
                watch.record("upload_refused", time.perf_counter(), response.status_code)
        seeded[subject].append(case["id"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(seed_case, range(args.cases)))
    seed_seconds = time.monotonic() - seed_started

    def leakage_check() -> None:
        for subject in subjects:
            listed = {case["id"] for case in http.get("/api/cases", headers=who[subject]).json()}
            foreign = listed - set(seeded[subject])
            if foreign:
                leakage.append(f"{subject} sees {len(foreign)} foreign case(s)")

    def job_driver(slot: int) -> None:
        pathways = ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING", "FULL_CREDIT"]
        cycle = 0
        while not stop.is_set():
            subject = subjects[(slot + cycle) % len(subjects)]
            if not seeded[subject]:
                time.sleep(1)
                cycle += 1
                continue
            case_id = seeded[subject][cycle % len(seeded[subject])]
            pathway = pathways[(slot + cycle) % len(pathways)]
            depth = "full" if cycle % 2 else "screen"
            response = timed(watch, "start_run", lambda: start_run(http, who[subject], case_id, pathway, depth))
            if response.status_code == 201:
                run = wait_terminal(http, who[subject], response.json()["id"])
                watch.record(f"run:{run['status']}", time.perf_counter(), (run.get("error") or {}).get("code", "ok"))
                if run["status"] == "succeeded":
                    timed(watch, "accept", lambda: http.post(f"/api/runs/{run['id']}/accept", headers=who[subject]))
            cycle += 1

    def stream_holder(subject: str) -> None:
        while not stop.is_set():
            cases = seeded[subject]
            if not cases:
                time.sleep(1)
                continue
            case = http.get(f"/api/cases/{cases[0]}", headers=who[subject]).json()
            run_id = case.get("current_execution_id")
            if not run_id:
                time.sleep(2)
                continue
            holder = client(args.url, timeout=None)
            try:
                started = time.perf_counter()
                response = holder.send(holder.build_request("GET", f"/api/runs/{run_id}/events", headers=who[subject]), stream=True)
                watch.record("stream_open", started, response.status_code)
                deadline = time.monotonic() + 30
                for _line in response.iter_lines():
                    if stop.is_set() or time.monotonic() > deadline:
                        break
                response.close()
            except httpx.HTTPError as exc:
                watch.record("stream_open", time.perf_counter(), type(exc).__name__)
            finally:
                holder.close()

    def reader(subject: str) -> None:
        interval = 60.0 / args.rpm
        preview_body = {"build_id": "profile-no-build", "registry_version": "profile", "registry_digest": "0" * 64,
                        "assumptions": [{"assumption_id": "p", "case": "BASE", "period_id": "FY2026", "unit": "x", "status": "READY", "value": 1}]}
        tick = 0
        while not stop.is_set():
            cases = seeded[subject]
            case_id = cases[tick % len(cases)] if cases else None
            kind, call = "list_cases", lambda: http.get("/api/cases", headers=who[subject])
            if case_id and tick % 3 == 1:
                kind, call = "list_sources", lambda: http.get(f"/api/cases/{case_id}/sources", headers=who[subject])
            elif case_id and tick % 3 == 2:
                kind, call = "case_detail", lambda: http.get(f"/api/cases/{case_id}", headers=who[subject])
            if case_id and tick % 50 == 25:
                for _ in range(args.previews):
                    timed(watch, "preview", lambda: http.post(f"/api/cases/{case_id}/models/previews", json=preview_body, headers=who[subject]))
            try:
                timed(watch, kind, call)
            except httpx.HTTPError:
                pass
            tick += 1
            time.sleep(interval)

    samples: list[dict] = []
    restarts: list[str] = []

    def sampler() -> None:
        next_restart = time.monotonic() + args.restart_every if args.restart_every else None
        while not stop.is_set():
            sample = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "latency": watch.summary()}
            if args.compose_project:
                try:
                    sample["resources"] = docker_stats(args.compose_project)
                except (OSError, ValueError) as exc:
                    sample["resources"] = {"error": type(exc).__name__}
            leakage_check()
            samples.append(sample)
            (out_dir / "samples.jsonl").open("a").write(json.dumps(sample) + "\n")
            if next_restart and time.monotonic() >= next_restart and args.restart_command:
                subprocess.run(shlex.split(args.restart_command), check=False)
                restarts.append(sample["at"])
                next_restart = time.monotonic() + args.restart_every
            stop.wait(args.sample_every)

    threads = [threading.Thread(target=job_driver, args=(slot,), daemon=True) for slot in range(args.jobs)]
    threads += [threading.Thread(target=stream_holder, args=(subject,), daemon=True) for subject in subjects for _ in range(args.streams)]
    threads += [threading.Thread(target=reader, args=(subject,), daemon=True) for subject in subjects]
    threads.append(threading.Thread(target=sampler, daemon=True))
    started_at = time.monotonic()
    for thread in threads:
        thread.start()
    try:
        while time.monotonic() - started_at < args.duration:
            time.sleep(1)
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=60)
    summary = watch.summary()
    report = {
        "schema_version": "caos.capacity-profile.v1", "url": args.url, "declared": DECLARED,
        "requested": {key: getattr(args, key) for key in ("subjects", "jobs", "streams", "previews", "rpm", "cases", "documents", "duration")},
        "seed_seconds": round(seed_seconds, 1), "cases_seeded": sum(len(v) for v in seeded.values()),
        "latency": summary, "leakage": leakage, "restarts": restarts, "samples": len(samples),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": "enterprise test profile measurement only; not a production capacity or availability figure",
    }
    (out_dir / "profile.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("cases_seeded", "seed_seconds", "leakage", "restarts", "samples")}))
    for kind, values in sorted(summary.items()):
        print(f"{kind:>16}  n={values['count']:<6} p50={values['p50_ms']:>8} p95={values['p95_ms']:>8} max={values['max_ms']:>8} {values['statuses']}")
    print(f"written {out_dir / 'profile.json'}")
    return 1 if leakage else 0


# --- baseline and compare -------------------------------------------------------------------

def baseline(args: argparse.Namespace) -> int:
    """Every authority a subject can see: accepted snapshot, model builds,
    frozen deliverable exports and the audit chain head — the pre/post-soak
    comparison (PERF-015) diffs two of these."""
    http = client(args.url)
    subjects = [f"capacity-{index}" for index in range(args.subjects)]
    record: dict[str, dict] = {}
    for subject in subjects:
        who = headers(subject)
        for case in http.get("/api/cases", headers=who).json():
            case_id = case["id"]
            snapshot = http.get(f"/api/cases/{case_id}/snapshot", headers=who).json()
            builds = http.get(f"/api/cases/{case_id}/models", headers=who).json().get("builds", [])
            frozen = []
            for pathway in ("FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING", "DEEP_RESEARCH"):
                workspace = http.get(f"/api/cases/{case_id}/deliverables/{pathway}/draft", headers=who)
                if workspace.status_code == 200:
                    frozen += [{"id": item["id"], "status": item["status"], "digest": item["digest"],
                                "exports": {fmt: meta.get("sha256") for fmt, meta in (item.get("exports") or {}).items()}}
                               for item in workspace.json().get("frozen_history", [])]
            package = http.get(f"/api/cases/{case_id}/audit-package", headers=who)
            head = None
            if package.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
                    names = [name for name in archive.namelist() if name.endswith("audit/head.json")]
                    head = json.loads(archive.read(names[0])) if names else None
            record[case_id] = {
                "subject": subject,
                "accepted": (snapshot.get("accepted") or {}).get("digest"),
                "builds": sorted(b.get("payload_digest") or "" for b in builds),
                "frozen": sorted(frozen, key=lambda item: item["id"]),
                "audit_head": head,
            }
    payload = {"schema_version": "caos.capacity-baseline.v1", "url": args.url, "cases": record,
               "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"baseline of {len(record)} cases written to {args.out}")
    return 0


def compare(args: argparse.Namespace) -> int:
    before = json.loads(Path(args.before).read_text())["cases"]
    after = json.loads(Path(args.after).read_text())["cases"]
    changed = []
    for case_id, then in before.items():
        now = after.get(case_id)
        if now is None:
            changed.append(f"{case_id}: missing after")
            continue
        for key in ("accepted", "builds", "frozen"):
            if then[key] != now[key]:
                changed.append(f"{case_id}: {key} changed")
        if (then["audit_head"] or {}) != (now["audit_head"] or {}) and not args.allow_audit_growth:
            changed.append(f"{case_id}: audit head moved")
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]  # noqa: E731
    print(json.dumps({"before": digest(args.before), "after": digest(args.after), "cases": len(before), "changed": changed}, indent=2))
    return 1 if changed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    lim = commands.add_parser("limits")
    lim.add_argument("--url", default="http://127.0.0.1:8000")
    lim.add_argument("--edge-url", default=None)
    lim.add_argument("--out", default="capacity-limits.json")
    pro = commands.add_parser("profile")
    pro.add_argument("--url", default="http://127.0.0.1:8000")
    for key in ("subjects", "jobs", "streams", "previews", "rpm", "cases", "documents"):
        pro.add_argument(f"--{key}", type=int, default=DECLARED[key])
    pro.add_argument("--duration", type=float, default=600.0, help="seconds; 28800 is the soak")
    pro.add_argument("--large-every", type=int, default=0, help="every Nth seeded document is a 25 MiB source")
    pro.add_argument("--sample-every", type=float, default=30.0)
    pro.add_argument("--compose-project", default=None)
    pro.add_argument("--restart-every", type=float, default=0.0)
    pro.add_argument("--restart-command", default=None)
    pro.add_argument("--out", default="capacity-profile")
    base = commands.add_parser("baseline")
    base.add_argument("--url", default="http://127.0.0.1:8000")
    base.add_argument("--subjects", type=int, default=DECLARED["subjects"])
    base.add_argument("--out", default="capacity-baseline.json")
    cmp = commands.add_parser("compare")
    cmp.add_argument("before")
    cmp.add_argument("after")
    cmp.add_argument("--allow-audit-growth", action="store_true", help="the soak appends audit rows; compare authorities only")
    args = parser.parse_args(argv)
    return {"limits": limits, "profile": profile, "baseline": baseline, "compare": compare}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
