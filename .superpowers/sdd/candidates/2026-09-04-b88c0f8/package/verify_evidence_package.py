#!/usr/bin/env python3
"""Offline verifier for the release evidence package (standard library only).

    python verify_evidence_package.py <copy-of-candidate-directory> [--json]

Run it on a SEPARATE copy of the candidate directory: it recomputes every object's
sha256 against package/PACKAGE_MANIFEST.json, refuses a missing or extra object,
recomputes the package digest and compares it with package/PACKAGE.sha256,
re-verifies every junit citation in package/checks.csv against the retained junit
reports inside the copy, checks that every gate and blocker artifact exists, and
reports the signable flag the manifest carries. Exit 0 only when every object
verifies AND the manifest is signable; exit 1 when the objects verify but the
package is not signable; exit 2 on any integrity finding.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def junit_index(root: Path) -> dict[str, dict[str, set[str]]]:
    index: dict[str, dict[str, set[str]]] = {}
    for fn in ("pytest-backend-junit.xml", "pytest-corpus-full-junit.xml"):
        path = root / "gates" / fn
        if not path.exists():
            continue
        for tc in ET.parse(path).getroot().iter("testcase"):
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


def verify(root: Path) -> dict:
    findings: list[dict] = []
    manifest_path = root / "package" / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    objects = manifest["objects"]
    excluded = {"package/PACKAGE_MANIFEST.json", "package/PACKAGE.sha256"}
    present = set()
    for path in sorted(root.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        present.add(rel)
        if rel not in objects:
            findings.append({"code": "OBJECT_NOT_IN_MANIFEST", "object": rel})
            continue
        digest = sha256(path)
        if digest != objects[rel]["sha256"]:
            findings.append({"code": "OBJECT_DIGEST_MISMATCH", "object": rel})
    for rel in objects:
        if rel not in present:
            findings.append({"code": "OBJECT_MISSING", "object": rel})
    h = hashlib.sha256(manifest_path.read_bytes())
    for rel in sorted(objects):
        h.update(f"{rel}\0{objects[rel]['sha256']}\n".encode())
    recorded = (root / "package" / "PACKAGE.sha256").read_text(encoding="utf-8").split()[0]
    if h.hexdigest() != recorded:
        findings.append({"code": "PACKAGE_DIGEST_MISMATCH", "recorded": recorded, "recomputed": h.hexdigest()})
    junit = junit_index(root)
    checks = list(csv.DictReader((root / "package" / "checks.csv").open(encoding="utf-8")))
    if len(checks) != 340:
        findings.append({"code": "CHECK_COUNT_MISMATCH", "count": len(checks)})
    for row in checks:
        for ref in filter(None, (r.strip() for r in row["evidence"].split(";"))):
            if ref.startswith("junit:"):
                cls, name = ref[6:].split("::", 1)
                statuses = junit.get(cls, {}).get(name)
                if not statuses or not statuses <= {"passed"}:
                    findings.append({"code": "CITED_TEST_NOT_PASSED", "check_id": row["check_id"], "test": ref[6:]})
            elif ref.startswith("junit-module:"):
                tests = junit.get(ref[13:])
                if not tests or any(not s <= {"passed"} for s in tests.values()):
                    findings.append({"code": "CITED_MODULE_NOT_PASSED", "check_id": row["check_id"], "module": ref[13:]})
            elif ref.startswith("artifact:"):
                if ref[9:] not in objects and not (root / ref[9:]).exists():
                    findings.append({"code": "CITED_ARTIFACT_MISSING", "check_id": row["check_id"], "artifact": ref[9:]})
        if row["result"] in {"PASS", "PROVED HOST CONTROL"} and not row["evidence"].strip():
            findings.append({"code": "RESULT_WITHOUT_EVIDENCE", "check_id": row["check_id"]})
        if row["result"] in {"OPEN", "BLOCKED EXTERNAL", "FAIL"} and not row["owner"].strip():
            findings.append({"code": "OPEN_WITHOUT_OWNER", "check_id": row["check_id"]})
    for gate in manifest["gates"]:
        for rel in gate["artifacts"]:
            if rel not in objects and not (root / rel).exists():
                findings.append({"code": "GATE_ARTIFACT_MISSING", "gate": gate["gate"], "artifact": rel})
    for blocker in manifest["blockers"]:
        for ref in blocker["closing_evidence"]:
            if ref.startswith("artifact:") and ref[9:] not in objects:
                findings.append({"code": "BLOCKER_ARTIFACT_MISSING", "blocker": blocker["blocker"], "artifact": ref[9:]})
    return {
        "candidate_id": manifest["candidate_id"], "objects_verified": len(objects), "checks": len(checks),
        "signable": bool(manifest.get("signable")), "not_signable_because": manifest.get("not_signable_because", []),
        "package_digest": recorded, "findings": findings, "ok": not findings,
    }


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 2
    report = verify(Path(argv[0]))
    if "--json" in argv[1:]:
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"candidate {report['candidate_id']}: {'VERIFIED' if report['ok'] else 'FINDINGS'} · objects {report['objects_verified']} · checks {report['checks']} · signable {report['signable']} · digest {report['package_digest']}")
        for item in report["findings"][:50]:
            print("  " + json.dumps(item, sort_keys=True))
        for reason in report["not_signable_because"][:40]:
            print("  not signable: " + reason)
    if report["findings"]:
        return 2
    return 0 if report["signable"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
