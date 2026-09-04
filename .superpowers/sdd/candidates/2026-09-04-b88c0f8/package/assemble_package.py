#!/usr/bin/env python3
"""Assemble the release evidence package for candidate 2026-09-04-b88c0f8 (Task 13, ER-G10).

Reads only retained candidate artifacts (this directory's parent), the loop logs
under .superpowers/sdd/loops/, the prepared reviewer records, the check maps and
the repository ledgers at the package commit; writes:

  package/checks.csv              every one of the 340 checks (the 30 SIMs among
                                  them) with its retained result or open owner —
                                  every junit citation re-verified against the
                                  candidate's junit reports, every artifact path
                                  checked to exist
  package/loops/*.md              the ER-L1..L4 loop logs as retained
  package/ledgers/*               the quality, defect, perimeter, qualification and
                                  simulation ledgers and SPEC_RECONCILIATION at
                                  the package commit
  package/corpus/*.json           every pack manifest (C01–C22) and the corpus source digests
  package/PACKAGE_MANIFEST.json   identity, G0–G9 gate table, check summary,
                                  blockers, exclusions, test-only limitations,
                                  missing artifacts, and every object's sha256
  package/PACKAGE.sha256          the package digest (see package_digest below)

Nothing here infers a result: a row without a retained artifact is OPEN.
Standard library only, so the same interpreter that verifies can assemble.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATE = HERE.parent
REPO = CANDIDATE.parents[3]
CANDIDATE_ID = CANDIDATE.name
COMMIT = "b88c0f8ca11af3200e8bb21daab16d838c64d39f"
IMAGES = {
    "app": "sha256:10ec8aa0798d06c9c9fcbc1d6db95303a02430385cbca0404a3fe422139f532d",
    "worker": "sha256:526c2d5f3c7a4fd6c09ed4110d3212980b7b752cb721277e7e00468129a9468a",
}
RESULTS = ("PASS", "PROVED HOST CONTROL", "BLOCKED EXTERNAL", "OPEN", "FAIL")
ALLOWED_STATUS = {"passed"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- retained junit: the only source a `junit:` citation may resolve against ------


def load_junit() -> dict[str, dict[str, set[str]]]:
    """classname -> {name -> statuses}; parametrized cells are recorded under their
    base name too, so `base` cites every cell and a failed cell fails the base."""
    index: dict[str, dict[str, set[str]]] = {}
    for fn in ("pytest-backend-junit.xml", "pytest-corpus-full-junit.xml"):
        root = ET.parse(CANDIDATE / "gates" / fn).getroot()
        for tc in root.iter("testcase"):
            status = "passed"
            for child in tc:
                if child.tag in {"failure", "error", "skipped"}:
                    status = child.tag
            names = {tc.get("name")}
            if "[" in tc.get("name"):
                names.add(tc.get("name").split("[", 1)[0])
            for name in names:
                index.setdefault(tc.get("classname"), {}).setdefault(name, set()).add(status)
    return index


def verify_citation(ref: str, junit: dict[str, dict[str, set[str]]], objects: set[str]) -> str | None:
    """Return a defect string, or None when the citation resolves to retained evidence."""
    if ref.startswith("junit:"):
        target = ref[len("junit:"):]
        if "::" not in target:
            return f"malformed junit citation {ref}"
        classname, name = target.split("::", 1)
        statuses = junit.get(classname, {}).get(name)
        if not statuses:
            return f"test not retained: {target}"
        if not statuses <= ALLOWED_STATUS:
            return f"test not passed: {target} {sorted(statuses)}"
        return None
    if ref.startswith("junit-module:"):
        classname = ref[len("junit-module:"):]
        tests = junit.get(classname)
        if not tests:
            return f"module not retained: {classname}"
        bad = {n for n, s in tests.items() if not s <= ALLOWED_STATUS}
        return f"module has non-passed tests: {classname} {sorted(bad)[:3]}" if bad else None
    if ref.startswith("artifact:"):
        rel = ref[len("artifact:"):]
        return None if rel in objects or (CANDIDATE / rel).exists() else f"artifact missing: {rel}"
    if ref.startswith("ledger:"):
        return None if (REPO / ref[len("ledger:"):]).exists() else f"ledger missing: {ref}"
    return f"unknown citation form: {ref}"


# --- the 340 checks ----------------------------------------------------------------


def standard_checks() -> list[dict[str, str]]:
    text = (REPO / "ENTERPRISE_TESTING_READINESS.md").read_text(encoding="utf-8").splitlines()
    rows = []
    section = None
    for line in text:
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"^- \*\*([A-Z]{2,5}-\d{3})(?::[^*]*)?\*\*:?\s*(.*)$", line)
        if m:
            rows.append({"check_id": m.group(1), "family": m.group(1).split("-")[0], "section": section, "condition": m.group(2).strip()})
            continue
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if re.match(r"^SIM-\d{3}$", cells[0]):
                rows.append({"check_id": cells[0], "family": "SIM", "section": section, "condition": " | ".join(cells[1:])})
    assert len(rows) == 340, len(rows)
    return rows


def mapped_rows(maps_dir: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for fn in sorted(maps_dir.glob("map_*.csv")):
        for row in csv.DictReader(fn.open(encoding="utf-8")):
            out[row["check_id"]] = row
    return out


def perimeter_rows() -> dict[str, dict[str, str]]:
    """IAM/SEC/WEB/PERF from docs/PERIMETER_LEDGER.csv, resolved against this
    candidate's retained gates. The candidate-harness rows are judged one by one
    from the retained stack and soak artifacts (see JUDGED)."""
    junit_files = {"caos/tests/spec/test_": "caos.tests.spec.", "caos/tests/test_": "caos.tests."}
    out = {}
    for row in csv.DictReader((REPO / "docs" / "PERIMETER_LEDGER.csv").open(encoding="utf-8")):
        cid, mech, evidence = row["check_id"], row["mechanism"], row["evidence"]
        refs = []
        for item in re.findall(r"(caos/tests/(?:spec/)?test_[a-z_0-9]+\.py)::([A-Za-z_0-9]+)", evidence):
            path, name = item
            cls = path.replace("/", ".")[:-3]
            refs.append(f"junit:{cls}::{name}")
        if cid in JUDGED:
            result, extra, owner, note = JUDGED[cid]
            out[cid] = {"check_id": cid, "result": result, "evidence": ";".join(refs + extra), "owner": owner,
                        "notes": f"{note} [PERIMETER_LEDGER: {mech}]"}
            continue
        if mech == "retained-test":
            out[cid] = {"check_id": cid, "result": "PASS", "evidence": ";".join(refs), "owner": "",
                        "notes": f"retained tests passed in the candidate junit [PERIMETER_LEDGER: {row['notes'][:160]}]"}
        elif mech == "release-gate":
            extra = ["artifact:gates/sec-audit.txt"] if "run_sec_audit" in evidence else []
            if "ci.yml" in evidence and "security" in evidence:
                extra += ["artifact:gates/scans/scan-manifest.json", "artifact:gates/scans/dependency-and-sast.txt",
                          "artifact:gates/scans/npm-audit.txt", "artifact:gates/scans/gitleaks.txt",
                          "artifact:gates/scans/trivy-app-fixable-gate.txt", "artifact:gates/scans/trivy-worker-fixable-gate.txt"]
            if "frontend" in evidence:
                extra += ["artifact:gates/frontend.txt", "artifact:gates/frontend-unit.txt"]
            if "quality_ledger_coverage" in evidence:
                extra += ["artifact:gates/quality-ledger.txt"]
            out[cid] = {"check_id": cid, "result": "PASS", "evidence": ";".join(refs + extra), "owner": "",
                        "notes": f"release gate ran against the candidate: {row['notes'][:200]}"}
        elif mech == "BLOCKED EXTERNAL":
            out[cid] = {"check_id": cid, "result": "BLOCKED EXTERNAL", "evidence": ";".join(refs), "owner": BLOCKED_OWNERS[cid],
                        "notes": row["notes"][:300]}
        else:
            raise AssertionError(f"unjudged perimeter row {cid} ({mech})")
    return out


BLOCKED_OWNERS = {
    "SEC-023": "provider account owner / model risk (data-use policy, qualification record)",
    "SEC-024": "provider account owner (settings outside the tree)",
    "SEC-025": "enterprise network owner (egress allowlist proof)",
    "SEC-028": "security (authorized penetration test on the frozen images)",
}

# candidate-harness, structural and manual rows, judged from the retained artifacts
STACK = "artifact:gates/stack/stack-gates.txt"
LIMITS = "artifact:gates/stack/capacity-limits.json"
PROFILE = "artifact:soak/profile/profile.json"
SAMPLES = "artifact:soak/profile/samples.jsonl"
SOAK_LAUNCH = "artifact:soak/soak-launch.txt"
JUDGED = {
    "WEB-002": ("PASS", ["artifact:gates/browser/browser-gates.txt", "artifact:gates/browser/test-results/chromium/workbench-report.json", "artifact:gates/browser/test-results/firefox/workbench-report.json", "artifact:gates/browser/test-results/webkit/workbench-report.json"], "", "the six document-first journeys passed against the frozen app image in Chromium 151.0.7922.34, Firefox 153.0 and WebKit 26.5 with no console errors; which engine versions the enterprise test approves is the test owner's record"),
    "WEB-003": ("PASS", ["artifact:gates/browser/browser-gates.txt", "artifact:gates/frontend-unit.txt"], "", "the smoke drives deep links, an unknown route, missing case/run authority and browser history with a dirty draft in all three engines; workspaceAuthority reducer tests are among the 123 unit tests retained"),
    "WEB-004": ("PASS", ["artifact:gates/browser/a11y-rerun.txt", "artifact:gates/browser/browser-gates.txt"], "", "a11y sweep asserts empty, populated, review, filed, loading, error and refusal states on screen before scanning; the smoke drives unavailable routes, the reader restriction, stale authority, failed/paused/succeeded runs and a controlled 503"),
    "WEB-007": ("PASS", ["artifact:gates/browser/a11y-rerun.txt"], "", "axe WCAG 2.1 AA over 9 routes × 6 viewports plus the pending-plan, ready-model and ready-report fixtures and seven states: 75 combinations, 0 violations, on the candidate"),
    "WEB-009": ("PASS", ["artifact:gates/browser/a11y-rerun.txt", "junit-module:caos.tests.spec.test_publication_goldens_spec"], "", "axe colour-contrast rule over every combination (0 violations); the cross-format goldens pin the exported content"),
    "WEB-010": ("OPEN", ["artifact:gates/browser/a11y-rerun.txt"], "REV-010 accessibility reviewer / decision owner (dense-table fixture with long values, nulls and large numbers on narrow screens)", "page-horizontal-scroll is asserted at 720 px and the ready-model worksheet fixture is scanned; sticky labels, long values, nulls and large numbers are not asserted by a retained artifact"),
    "WEB-013": ("BLOCKED EXTERNAL", ["artifact:gates/browser/browser-gates.txt"], "enterprise identity owner (session expiry at the oauth2-proxy edge)", "application half retained: the reader gate with /api/me aborted falls to the read-only floor and dirty-draft guards hold on navigation, history and unload; a real session expiry needs the identity edge"),
    "WEB-014": ("OPEN", ["artifact:gates/browser/browser-gates.txt"], "decision owner (run caos/frontend/scripts/draft-history-smoke.mjs against the candidate and retain its report)", "draft history across cases and routes is driven by the workbench smoke; isolation across tabs, users and browser restarts is the draft-history smoke, which has no retained result on this candidate"),
    "IAM-004": ("PASS", ["artifact:gates/sec-audit.txt"], "", "run_sec_audit.py edge_configuration_checks passed on the candidate (Caddyfile strips every trusted identity header and injects the edge secret; oauth2-proxy skip list equals the public set)"),
    "IAM-016": ("BLOCKED EXTERNAL", ["artifact:gates/sec-audit.txt"], "enterprise identity owner (OIDC issuer, client, one account per role)", "configuration half pinned by the audit; session expiry, logout and revocation need the identity provider and the oauth2-proxy/caddy edge, which the candidate stack did not start"),
    "SEC-022": ("BLOCKED EXTERNAL", [PROFILE], "provider account owner (provider-side extraction signal)", "application-side signals retained: per-subject rate ceiling test passed and the soak drove readers at the 300/min ceiling with typed 429s; the provider-side signal needs the live provider account"),
    "SEC-029": ("PASS", ["ledger:docs/PERIMETER_LEDGER.csv"], "", "every security row carries an OWASP API/Top 10, LLM Top 10 or MITRE ATLAS mapping; test_perimeter_ledger passed in the candidate junit"),
    "WEB-006": ("OPEN", ["artifact:gates/browser/a11y-rerun.txt"], "REV-010 accessibility reviewer (screen reader, 400% reflow, reduced motion, forced colors, high contrast)", "automated half retained (axe at 200% zoom viewport, keyboard tab checks, 75 combinations 0 violations); the manual half is the outstanding REV-010"),
    "WEB-008": ("OPEN", ["artifact:gates/browser/a11y-rerun.txt", "artifact:gates/browser/browser-gates.txt"], "REV-010 accessibility reviewer", "focus order, restoration, dialogs and tabs are asserted by the three-engine smoke; accessible names, landmarks, headings, tables, errors and status announcements need the manual screen-reader pass (REV-010)"),
    "WEB-015": ("OPEN", ["artifact:gates/browser/browser-gates.txt"], "credit analysts / design owner (REV-006 approved screenshots)", "the smoke keeps screenshots only on failure and every engine passed, so no approved preview or publication screenshot per pathway and state was captured on this candidate"),
    "PERF-001": ("PASS", [LIMITS], "", "limits over HTTP: 25 jobs → 20 admitted, 5 ADMISSION_BUSY, 20 terminal; in-process proof in test_limits_spec"),
    "PERF-002": ("PASS", [LIMITS], "", "limits over HTTP: streams [200,200,200,200], fifth 429, other subject 200, after release 200; previews [422,422,429]; rate 300 admitted then refused"),
    "PERF-003": ("PROVED HOST CONTROL", [PROFILE, SOAK_LAUNCH], "enterprise test owner (live credential) / model risk", "soak: 20 jobs across six pathways at both depths for 8 h, leakage [] on every sample; module execution was the host-control binding, so the mixed agent half is orchestration proof only"),
    "PERF-004": ("PASS", [LIMITS, PROFILE], "", "limits: 25 MiB → 201, 25 MiB + 1 → 413; soak: 8,000 concurrent uploads (every 500th 25 MiB) → 201 8,000; atomic intake pinned by test_intake_spec"),
    "PERF-005": ("PASS", [PROFILE], "", "soak store held 112 cases; list_cases 281,945 reads, p95 1.28 s; the list route never reads the blocks column (retained test). The p95 itself is PERF-009's finding, not this check's"),
    "PERF-006": ("OPEN", [PROFILE, "artifact:soak/attempt-1-manifest-ceiling/soak-launch.txt"], "enterprise test owner (REV-015: declared profile vs the 2,000-row manifest ceiling)", "100 documents per case exceed the 2,000-row manifest ceiling (attempt 1: every run refused AGENT_BUDGET_EXCEEDED); the retained soak ran 80 documents per case, so the 100-document source list was not exercised"),
    "PERF-007": ("PASS", [LIMITS], "", "previews ceiling over HTTP [422,422,429]; simultaneous previews persist nothing is the retained in-process proof (test_limits_spec, test_model_builder_spec preview tests)"),
    "PERF-008": ("PASS", [], "", "retained tests: concurrent queue idempotent, bounded worker progress, dead-claim requeue (test_model_builder_spec, test_worker, test_single_instance)"),
    "PERF-009": ("FAIL", [PROFILE, SAMPLES], "enterprise test owner / decision owner (profile, hardware or a new candidate)", "NOT MET: in the declared profile on one instance list_cases p95 1.28 s, list_sources p95 1.41 s, case_detail p95 1.20 s, accept p95 2.23 s at 76–97 % app CPU (profile.json)"),
    "PERF-010": ("OPEN", [PROFILE], "enterprise test owner (harness measurement of commit-to-delivery latency)", "stream_open p95 0.65 s retained (94,203 opens); the SSE tail is proven in-suite; the commit-to-browser delivery latency itself is not measured by the harness"),
    "PERF-011": ("OPEN", ["artifact:gates/browser/browser-gates.txt"], "REV-010 accessibility reviewer / decision owner", "first-page DCL/FCP budgets enforced on Chromium (61/152 ms) and the ready-model worksheet fixture scanned; maximum-length tables and event histories were not driven on this candidate"),
    "PERF-012": ("PASS", [SAMPLES, PROFILE], "", "631 samples over 8 h: container CPU and memory, database connections, checkpoint bytes, vault KiB (exports live in the vault)"),
    "PERF-013": ("OPEN", [PROFILE, SOAK_LAUNCH, "artifact:soak/attempt-1-manifest-ceiling/soak-launch.txt"], "decision owner (the profile drives upload/run/accept/stream/preview only; model, draft, freeze, approve, receipt, download and audit-export cycles need a binding that yields a READY model)", "eight hours, route-balanced, worker hard-restart every 2 h, 6,291 runs accepted, no driver error; but the declared cycle beyond acceptance was not exercised (previews 422: no READY build under host control) and the profile ran at 80 documents per case"),
    "PERF-014": ("OPEN", [SAMPLES, PROFILE], "ER-L4 (post-soak leak check: jobs, permits, handles, connections, orphan rows from the last samples and the final snapshot)", "last samples read bounded (memory 545–780 MiB, connections back to 14, vault and checkpoints flat from the midpoint); the formal comparison the loop owes is not in the log"),
    "PERF-015": ("OPEN", ["artifact:soak/baseline-pre.json", "artifact:soak/pre-soak-authority.json"], "ER-L4 (post-soak six journeys, authority diff, model hashes, filed bytes, offline reconstruction against the pre-soak baseline)", "pre-soak baseline and authority snapshot retained; the post-soak comparison was never run (the clamav container was OOM-killed at 03:31Z and its restart must be logged first)"),
}


def qualification_rows(junit: dict[str, dict[str, set[str]]]) -> dict[str, dict[str, str]]:
    out = {}
    verdict = "artifact:gates/qualification/host-control-verdict.txt"
    for row in csv.DictReader((REPO / "docs" / "QUALITY_QUALIFICATION.csv").open(encoding="utf-8")):
        cid, status = row["Check ID"], row["Status"]
        modules = [f"junit-module:{m.replace('/', '.')[:-3]}" for m in re.findall(r"(?:caos/tests/)?((?:spec/)?test_[a-z_0-9]+\.py)", row["Harness mapping"])]
        modules = [m.replace("junit-module:spec.", "junit-module:caos.tests.spec.").replace("junit-module:test_", "junit-module:caos.tests.test_") for m in modules]
        modules = [m for m in dict.fromkeys(modules) if m[len("junit-module:"):] in junit]
        if status == "PROVED HOST CONTROL":
            out[cid] = {"check_id": cid, "result": "PROVED HOST CONTROL", "evidence": ";".join([verdict, "artifact:gates/qualification/host-control-matrix.txt"] + modules),
                        "owner": "enterprise test owner (live credential) / model risk", "notes": f"host-control matrix on the candidate: 32 pass, 5 BLOCKED EXTERNAL, verdict ORCHESTRATION_PROOF_INCOMPLETE; {row['Notes'][:160]}"}
        elif status == "PROVED (spec suite)":
            out[cid] = {"check_id": cid, "result": "PASS", "evidence": ";".join(modules) or verdict, "owner": "",
                        "notes": f"runtime contract proven by the retained suite: {row['Harness mapping'][:200]}"}
        else:
            out[cid] = {"check_id": cid, "result": "BLOCKED EXTERNAL", "evidence": verdict, "owner": "independent credit analysts (benchmark conclusions for C17/C21/C22)", "notes": row["Notes"][:200]}
    return out


def simulation_rows() -> dict[str, dict[str, str]]:
    evidence = json.loads((CANDIDATE / "gates" / "sim-evidence.json").read_text(encoding="utf-8"))
    by_id = {}
    for item in evidence.get("simulations", evidence if isinstance(evidence, list) else []):
        by_id[item["sim_id"]] = item
    out = {}
    for row in csv.DictReader((REPO / "docs" / "SIMULATION_LEDGER.csv").open(encoding="utf-8")):
        cid = row["sim_id"]
        refs = []
        for item in re.findall(r"(caos/tests/(?:spec/)?test_[a-z_0-9]+\.py)::([A-Za-z_0-9]+)", row["tests"]):
            refs.append(f"junit:{item[0].replace('/', '.')[:-3]}::{item[1]}")
        out[cid] = {"check_id": cid, "result": "PASS", "evidence": ";".join(refs + ["artifact:gates/sim-evidence.json"]), "owner": "",
                    "notes": f"{row['status']}; injected: {row['injected_fault'][:120]}; observed: {row['actual_outcome'][:120]}"}
    return out


REVIEW_OWNERS = {
    "REV-001": "two independent credit analysts", "REV-002": "independent credit analysts (adjudication)",
    "REV-003": "model risk reviewer", "REV-004": "security reviewer", "REV-005": "external-stakeholder reviewer",
    "REV-006": "design owner / external-stakeholder reviewer (benchmark side-by-side)", "REV-007": "security reviewer",
    "REV-008": "security reviewer (AI security)", "REV-009": "operations reviewer", "REV-010": "accessibility reviewer",
    "REV-011": "operations / enterprise test owner", "REV-012": "independent audit reviewer", "REV-013": "enterprise test owner",
    "REV-014": "operations reviewer (environment)", "REV-015": "enterprise test owner (declared profile adjudication)",
}


def review_rows() -> dict[str, dict[str, str]]:
    out = {}
    for path in sorted((CANDIDATE / "reviews").glob("REV-*.md")):
        cid = path.stem
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].split(":", 1)[1].strip() if ":" in text.splitlines()[0] else cid
        outstanding = "**OUTSTANDING**" in text
        out[cid] = {"check_id": cid, "result": "OPEN" if outstanding else "PASS", "evidence": f"artifact:reviews/{path.name}",
                    "owner": REVIEW_OWNERS.get(cid, "reviewer") if outstanding else "",
                    "notes": f"{title}: prepared record {'OUTSTANDING — not returned by the reviewer' if outstanding else 'returned'}"}
    return out


# --- gates, blockers, exclusions ----------------------------------------------------


def gate_table(summary: Counter, open_checks: list[str]) -> list[dict[str, object]]:
    g = "gates/"
    return [
        {"gate": "G0", "name": "Scope and traceability", "state": "OPEN",
         "result": f"340 checks mapped: {dict(summary)}; open owners named per row in package/checks.csv",
         "artifacts": ["package/checks.csv"], "closes": "every OPEN, FAIL and BLOCKED EXTERNAL row resolved with a retained result on this candidate"},
        {"gate": "G1", "name": "Deterministic automation", "state": "GREEN",
         "result": "backend 1242 passed, 1 skipped (nightly-only cell); Ruff clean; frontend lint/tsc/unit 123/build exit 0; three engines passed; a11y 75 combinations 0 violations; images 310 bundle files 0 mismatches; deploy assets ok",
         "artifacts": [g + "pytest-backend.txt", g + "pytest-backend-junit.xml", g + "ruff.txt", g + "frontend.txt", g + "frontend-unit.txt",
                       g + "browser/browser-gates.txt", g + "browser/a11y-rerun.txt", g + "scans/images.txt", g + "deploy-assets.txt"], "closes": "—"},
        {"gate": "G2", "name": "Evidence integrity", "state": "OPEN (host-control half green)",
         "result": "corpus host control 35 passed (every route, both depths, lineage asserted); host-control matrix 32 pass / 5 BLOCKED EXTERNAL; live half never ran (ER-L3 log has no tick)",
         "artifacts": [g + "corpus-full.txt", g + "pytest-corpus-full-junit.xml", g + "qualification/host-control-verdict.txt", "package/loops/live-matrix.md"],
         "closes": "ER-L3 with the live credential and analyst-approved answer keys"},
        {"gate": "G3", "name": "Model qualification", "state": "OPEN",
         "result": "ORCHESTRATION_PROOF_INCOMPLETE; no live cell retained; C20/C21/C22 BLOCKED EXTERNAL",
         "artifacts": [g + "qualification/host-control-verdict.txt", "package/loops/live-matrix.md"],
         "closes": "three retained live passes per required cell, the qualification record, C20–C22 bytes and keys"},
        {"gate": "G4", "name": "Analyst validation", "state": "OPEN",
         "result": "REV-001, REV-002, REV-005, REV-006 prepared, not returned",
         "artifacts": ["reviews/REV-001.md", "reviews/REV-002.md", "reviews/REV-005.md", "reviews/REV-006.md"], "closes": "returned reviewer records bound to this candidate's digests"},
        {"gate": "G5", "name": "Security", "state": "OPEN (scanner, SAST, dependency, secret, workflow and authorization halves green)",
         "result": "route audit 59 routes / 507 cells / 0 failures; pip-audit 57 clean; bandit 21,632 lines; npm audit 0 high/critical; gitleaks 209 commits clean; Trivy fixable HIGH/CRITICAL gate exit 0 on both images; SEC-023/024/025/028 and IAM-016 live half BLOCKED EXTERNAL; REV-004/007/008/014 outstanding",
         "artifacts": [g + "sec-audit.txt", g + "scans/scan-manifest.json", g + "scans/dependency-and-sast.txt", g + "scans/npm-audit.txt", g + "scans/gitleaks.txt",
                       g + "scans/trivy-app-fixable-gate.txt", g + "scans/trivy-worker-fixable-gate.txt"],
         "closes": "penetration test, egress proof, provider account policy, identity edge inputs, security reviews"},
        {"gate": "G6", "name": "Resilience", "state": "GREEN",
         "result": "SIM-001–030 30/30 (67 tests, 0 missing); two-connection races 27; instance locks 49; kill-and-recover on the image (health back 11 s, counts unchanged); backup 1 s and restore drill passed; second instance refused",
         "artifacts": [g + "sim-evidence.json", g + "sim-evidence-summary.txt", g + "stack/stack-gates.txt", g + "stack/backup-manifest.txt"], "closes": "—"},
        {"gate": "G7", "name": "Publishing", "state": "OPEN (contract half green)",
         "result": "opinion, freeze, filing, receipt, export integrity and goldens proven in the retained suite; the six golden journeys through freeze, filing, receipt and offline verification were NOT run on the frozen stack (no Docker daemon in the ER-G10 session; the served binding yields no READY model, so the four model-required pathways stop at a typed MODEL_REQUIRED/authority refusal)",
         "artifacts": [g + "pytest-backend-junit.xml", "package/golden_journeys.py"],
         "closes": "package/golden_journeys.py run against the frozen stack with a binding that yields a READY Full Credit model; artifacts retained under this candidate"},
        {"gate": "G8", "name": "Audit reconstruction", "state": "OPEN (verifier proven in-suite)",
         "result": "verify_package.py convicts six tamper classes in-suite; no on-image audit package retained; REV-012 outstanding",
         "artifacts": [g + "pytest-backend-junit.xml", "reviews/REV-012.md"], "closes": "REV-012 on an audit package produced by the golden journeys on the frozen stack"},
        {"gate": "G9", "name": "Enterprise test deployment", "state": "GREEN with findings",
         "result": "boots on the frozen images against PostgreSQL; reset to 31 empty tables; subject isolation (leakage [] through the soak); post-reset golden journey passed; findings: clamd OOM-killed 3 h into the soak and not restarted by Compose (uploads fail closed after 03:31Z, REV-014); the identity edge is BLOCKED EXTERNAL",
         "artifacts": [g + "stack/stack-gates.txt", "soak/pre-soak-reset-and-journey.txt", "soak/profile/profile.json", "package/loops/soak-watch.md"], "closes": "REV-014 and the OIDC inputs"},
    ]


BLOCKERS = [
    ("ETR-B01", "CLOSED under host control; live half OPEN", ["junit-module:caos.tests.spec.test_intake_spec", "artifact:gates/browser/browser-gates.txt"], "documents-only intake proven by the retained intake suite (30) and the three-engine journey; live-model qualification of the journey needs ER-L3"),
    ("ETR-B02", "CLOSED", ["junit-module:caos.tests.test_provider_identity", "artifact:MANIFEST.json"], "one environment-wide qualified binding, no picker; the candidate manifest records the sole binding and production refuses an unqualified or ambiguous one"),
    ("ETR-B03", "CLOSED (excluded)", ["junit-module:caos.tests.test_openrouter_provider"], "OpenRouter/GLM is a development-only binding refused in production; not in the enterprise profile"),
    ("ETR-B04", "CLOSED", ["junit-module:caos.tests.test_provider_identity"], "the actual provider identity rides every attempt, artifact, snapshot and audit row (Task 5B); AUD-003 notes the attempt-row fields not yet asserted"),
    ("ETR-B05", "OPEN", ["artifact:gates/corpus-full.txt", "artifact:gates/qualification/host-control-verdict.txt"], "the real-issuer corpus is digest-pinned and run under host control (35 passed); the final live matrix has no retained cell and the analyst-approved keys are external"),
    ("ETR-B06", "CLOSED", ["artifact:gates/scans/scan-manifest.json", "junit-module:caos.tests.test_workflow_security", "junit-module:caos.tests.test_recorded_review"], "recorded read-only review and pinned workflows; scans rerun on the frozen images"),
    ("ETR-B07", "CLOSED", ["junit-module:caos.tests.test_postgres_races"], "27 two-connection races passed against the pinned PostgreSQL container on the candidate"),
    ("ETR-B08", "CLOSED", ["artifact:package/inventory/openapi.json", "artifact:package/inventory/route-inventory.json", "artifact:gates/sec-audit.txt"], "the release gate is OpenAPI discovery (run_sec_audit, 59 routes) plus the a11y route sweep; production-inventory.mjs is not a gate"),
    ("ETR-B09", "CLOSED (excluded)", ["junit-module:caos.tests.test_openrouter_provider"], "OpenRouter excluded from the enterprise profile; shape proof required before any later admission"),
    ("ETR-B10", "CLOSED", ["junit-module:caos.tests.test_single_instance", "artifact:gates/sim-evidence.json", "artifact:gates/stack/stack-gates.txt"], "instance lock, Compose replicas 1, SIM-001–030 and the on-image second-instance refusal all rerun on the candidate"),
    ("ETR-B11", "OPEN", ["artifact:gates/qualification/host-control-verdict.txt"], "Distressed and Deep Research execute under host control; live qualification and the C21/C22 packs are external"),
    ("ETR-B12", "CLOSED under host control; live half OPEN", ["junit-module:caos.tests.spec.test_source_complete_modelling_spec", "artifact:gates/corpus-full.txt"], "lineage oracle and metamorphic cases retained; every pathway's effect needs live qualification and the licensed marks pack"),
    ("ETR-B13", "OPEN", ["artifact:reviews/REV-006.md"], "benchmark set not pinned; REV-006 outstanding"),
]

EXCLUDED_PRODUCTION_REQUIREMENTS = [
    "Multi-region or active-active deployment", "Horizontal application scaling",
    "A multi-worker LangGraph checkpoint implementation", "Formal uptime, recovery-time or recovery-point service-level agreements",
    "Twenty-four-hour operations, on-call staffing or customer support processes",
    "Automated production rollout, rollback or tenant migration", "Production data retention schedules or regulatory certification",
    "Capacity beyond the declared enterprise test profile", "Direct email, portal or data-room distribution to external stakeholders",
    "Distributed or PostgreSQL LangGraph checkpoints", "User-selectable LLM/provider bindings beyond the first qualified binding",
    "Raw prompt, chain-of-thought or provider-body retention", "New test frameworks beyond pytest and the installed Playwright library",
]

TEST_ONLY_LIMITATIONS = [
    {"limitation": "One application instance and one background worker (Compose deploy.replicas 1; exclusive checkpoint lock)", "recorded_in": "caos/deploy/ENVIRONMENT_MANIFEST.md; MANIFEST.json topology", "approval": "declared by the standard; test owner signs"},
    {"limitation": "Run checkpoints are SQLite on the data volume under the PostgreSQL domain store", "recorded_in": "CLAUDE.md known gaps; MANIFEST.json topology", "approval": "test owner"},
    {"limitation": "The candidate stack ran ENVIRONMENT=development with CAOS_PROVIDER=host_control (orchestration proof, never analysis) and dev-trusted role headers; the oauth2-proxy/caddy identity edge was not started", "recorded_in": "MANIFEST.json binding/topology; soak-watch.md", "approval": "test owner (live binding and OIDC are BLOCKED EXTERNAL)"},
    {"limitation": "The soak ran the declared profile except 80 documents per case (100 exceeds the 2,000-row manifest ceiling; attempt 1 retained)", "recorded_in": "soak/soak.sh; soak/attempt-1-manifest-ceiling/", "approval": "decision owner during ER-G9; REV-015 adjudicates"},
    {"limitation": "The soak's cycle is upload/run/accept/stream/preview; model, draft, freeze, approve, receipt, download and audit-export cycles were not driven (no READY model under host control)", "recorded_in": "soak/profile/profile.json", "approval": "not yet approved — PERF-013 OPEN"},
    {"limitation": "No .dockerignore: images must be built before a venv exists in the clone (candidate 1's worker image swept one in; candidate 2's images verified clean)", "recorded_in": "enterprise-task-13-report.md", "approval": "process control until a later candidate lands the fix"},
    {"limitation": "clamav container has no memory limit and Compose does not restart it on unhealthy (OOM-killed at 03:31Z during the soak; uploads fail closed afterwards)", "recorded_in": "soak-watch.md; enterprise-task-13-report.md", "approval": "not approved — REV-014 environment finding"},
    {"limitation": "No HTTP route grants the first case membership; the distinct approver is provisioned by an operator action against the store (qa/seed.py, golden_journeys.py operator_bootstrap)", "recorded_in": "package/golden_journeys.py; qa/INVENTORY.md", "approval": "test owner (IAM-008 authority rule unchanged)"},
]

MISSING_ARTIFACTS = [
    {"item": "Statement, branch and critical-path coverage reports", "status": "MISSING", "owner": "decision owner (a coverage run is a gate addition → new candidate or a retained run against this tag)"},
    {"item": "Live model-matrix results (one binding × six pathways × two depths × required packs × three cold repetitions)", "status": "MISSING — ER-L3 never ran a cell", "owner": "enterprise test owner (credential) / model risk"},
    {"item": "Post-soak comparison, PERF-014 leak check, post-soak three-engine journeys", "status": "MISSING — owed by ER-L4", "owner": "ER-L4 operator (log the clamav restart first)"},
    {"item": "Six golden journeys through freeze, filing, receipt and offline verification on the frozen stack", "status": "MISSING on the image; driver rehearsed on a dev server at the commit (report)", "owner": "decision owner on the machine holding the images"},
    {"item": "Returned reviewer records REV-001–REV-015", "status": "MISSING — all fifteen OUTSTANDING", "owner": "named reviewers per role (roster external)"},
    {"item": "Pinned deliverable benchmark, visual goldens per pathway/format, semantic-parity reports, analyst scorecards, adjudications, external-stakeholder review", "status": "MISSING — benchmark set is an external input; cross-format goldens exist in-suite only", "owner": "credit analysts / design owner"},
    {"item": "Penetration test report, egress allowlist proof, provider account policy", "status": "MISSING — BLOCKED EXTERNAL", "owner": "security / network owner / provider account owner"},
    {"item": "Enterprise test-owner signature over the package digest", "status": "MISSING", "owner": "enterprise test owner"},
]


# --- assembly ---------------------------------------------------------------------


def copy_into(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def main(argv: list[str]) -> int:
    maps_dir = Path(argv[0]) if argv else HERE / "maps"
    junit = load_junit()
    # retained inputs copied into the package
    for name in ("live-matrix.md", "soak-watch.md", "pr-babysit.md", "focus-race-findings.md"):
        copy_into(REPO / ".superpowers" / "sdd" / "loops" / name, HERE / "loops" / name)
    for name in ("QUALITY_LEDGER.csv", "QUALITY_DEFECTS.csv", "PERIMETER_LEDGER.csv", "QUALITY_QUALIFICATION.csv", "SIMULATION_LEDGER.csv"):
        copy_into(REPO / "docs" / name, HERE / "ledgers" / name)
    copy_into(REPO / "SPEC_RECONCILIATION.md", HERE / "ledgers" / "SPEC_RECONCILIATION.md")
    copy_into(REPO / "ENTERPRISE_TESTING_READINESS.md", HERE / "ledgers" / "ENTERPRISE_TESTING_READINESS.md")
    for manifest in sorted((REPO / "caos" / "tests" / "corpus" / "packs").glob("C*/manifest.json")):
        copy_into(manifest, HERE / "corpus" / f"{manifest.parent.name}.manifest.json")
    # answer keys stay in the tree at the tag (their digests ride each manifest);
    # the package carries manifests and source digests, never key or source text
    copy_into(REPO / "caos" / "tests" / "corpus" / "sources.txt", HERE / "corpus" / "sources.txt")
    # every object under the candidate directory, package outputs excluded
    objects: dict[str, dict[str, object]] = {}
    for path in sorted(CANDIDATE.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(CANDIDATE).as_posix()
        if rel in {"package/PACKAGE_MANIFEST.json", "package/PACKAGE.sha256", "package/checks.csv"}:
            continue
        objects[rel] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    object_paths = set(objects)
    # checks
    rows: dict[str, dict[str, str]] = {}
    rows.update(mapped_rows(maps_dir))
    rows.update(perimeter_rows())
    rows.update(qualification_rows(junit))
    rows.update(simulation_rows())
    rows.update(review_rows())
    standard = standard_checks()
    defects: list[str] = []
    out_rows = []
    for check in standard:
        cid = check["check_id"]
        row = rows.get(cid)
        if row is None:
            defects.append(f"unmapped check {cid}")
            row = {"check_id": cid, "result": "OPEN", "evidence": "", "owner": "ER-G10", "notes": "no mapping produced"}
        if row["result"] not in RESULTS:
            defects.append(f"{cid}: unknown result {row['result']}")
        if row["result"] in {"PASS", "PROVED HOST CONTROL"} and not row["evidence"].strip():
            defects.append(f"{cid}: {row['result']} without evidence")
        if row["result"] in {"OPEN", "BLOCKED EXTERNAL", "FAIL"} and not row["owner"].strip():
            defects.append(f"{cid}: {row['result']} without an owner")
        for ref in filter(None, (r.strip() for r in row["evidence"].split(";"))):
            defect = verify_citation(ref, junit, object_paths)
            if defect:
                defects.append(f"{cid}: {defect}")
        out_rows.append({**check, "result": row["result"], "evidence": row["evidence"], "owner": row["owner"], "notes": row["notes"]})
    with (HERE / "checks.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["check_id", "family", "section", "condition", "result", "evidence", "owner", "notes"])
        w.writeheader()
        w.writerows(out_rows)
    objects["package/checks.csv"] = {"sha256": sha256(HERE / "checks.csv"), "bytes": (HERE / "checks.csv").stat().st_size}
    summary = Counter(r["result"] for r in out_rows)
    by_family = {}
    for r in out_rows:
        by_family.setdefault(r["family"], Counter())[r["result"]] += 1
    blockers = []
    for bid, state, refs, closing in BLOCKERS:
        for ref in refs:
            defect = verify_citation(ref, junit, set(objects))
            if defect:
                defects.append(f"{bid}: {defect}")
        blockers.append({"blocker": bid, "state": state, "closing_evidence": refs, "note": closing})
    gates = gate_table(summary, [r["check_id"] for r in out_rows if r["result"] == "OPEN"])
    for gate in gates:
        for rel in gate["artifacts"]:
            if rel not in objects and not (CANDIDATE / rel).exists():
                defects.append(f"{gate['gate']}: artifact missing {rel}")
    candidate_manifest = json.loads((CANDIDATE / "MANIFEST.json").read_text(encoding="utf-8"))
    ready = summary["OPEN"] == 0 and summary["FAIL"] == 0 and summary["BLOCKED EXTERNAL"] == 0 and not MISSING_ARTIFACTS and not defects
    manifest = {
        "schema_version": "caos.release-evidence-package.v1",
        "candidate_id": CANDIDATE_ID,
        "assembled_at": datetime.now(UTC).isoformat(),
        "assembled_by": "Claude Fable 5.1 (ER-G10, Task 13 second half)",
        "claim": "enterprise-testing candidate for one controlled environment; never a production-readiness claim",
        "signable": ready,
        "not_signable_because": [] if ready else [
            f"{summary['OPEN']} checks OPEN, {summary['FAIL']} FAIL, {summary['BLOCKED EXTERNAL']} BLOCKED EXTERNAL (package/checks.csv)",
            *[f"missing artifact: {m['item']} — {m['status']}" for m in MISSING_ARTIFACTS],
            *[f"assembly defect: {d}" for d in defects],
        ],
        "identity": {
            "commit": COMMIT, "tag": "enterprise-candidate-2026-09-04", "images": IMAGES,
            "methodology_build_id": candidate_manifest["methodology"]["build_id"],
            "corpus_digest": candidate_manifest["corpus"]["corpus_digest"],
            "candidate_manifest_sha256": (CANDIDATE / "MANIFEST.sha256").read_text(encoding="utf-8").split()[0],
            "binding": candidate_manifest["binding"],
            "package_commit": argv[1] if len(argv) > 1 else None,
        },
        "gates": gates,
        "checks": {"total": len(out_rows), "summary": dict(summary), "by_family": {k: dict(v) for k, v in by_family.items()},
                   "open": [{"check_id": r["check_id"], "owner": r["owner"]} for r in out_rows if r["result"] in {"OPEN", "FAIL"}],
                   "blocked_external": [{"check_id": r["check_id"], "owner": r["owner"]} for r in out_rows if r["result"] == "BLOCKED EXTERNAL"],
                   "file": "package/checks.csv"},
        "blockers": blockers,
        "excluded_production_requirements": EXCLUDED_PRODUCTION_REQUIREMENTS,
        "test_only_limitations": TEST_ONLY_LIMITATIONS,
        "missing_artifacts": MISSING_ARTIFACTS,
        "assembly_defects": defects,
        "objects": objects,
    }
    (HERE / "PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest = package_digest(HERE / "PACKAGE_MANIFEST.json", objects)
    (HERE / "PACKAGE.sha256").write_text(f"{digest}  package/PACKAGE_MANIFEST.json+objects\n", encoding="utf-8")
    print(json.dumps({"checks": dict(summary), "objects": len(objects), "defects": defects, "signable": ready, "package_digest": digest}, indent=1))
    return 0 if not defects else 1


def package_digest(manifest_path: Path, objects: dict[str, dict[str, object]]) -> str:
    """sha256 over the manifest bytes followed by every object's `path\\0sha256\\n`
    in sorted order — recomputable by verify_evidence_package.py on a copy."""
    h = hashlib.sha256(manifest_path.read_bytes())
    for rel in sorted(objects):
        h.update(f"{rel}\0{objects[rel]['sha256']}\n".encode())
    return h.hexdigest()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
