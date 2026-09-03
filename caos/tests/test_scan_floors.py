"""The scanner floors refuse an empty or mis-targeted scan (SEC-002): each
subcommand is driven with a report at and below its floor, a gitleaks log
that never scanned a history, and a Trivy report of a different image."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "caos" / "scripts"))

import scan_floors  # noqa: E402


def _write(tmp_path: Path, name: str, payload) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return str(path)


def test_bandit_refuses_parse_errors_and_a_thin_scan(tmp_path):
    clean = _write(tmp_path, "b.json", {"errors": [], "metrics": {"_totals": {"loc": 5000}}})
    assert scan_floors.main(["bandit", clean]) == 0
    assert scan_floors.main(["bandit", _write(tmp_path, "thin.json", {"errors": [], "metrics": {"_totals": {"loc": 4999}}})]) == 1
    skipped = {"errors": [{"filename": "x.py"}], "metrics": {"_totals": {"loc": 9000}}}
    assert scan_floors.main(["bandit", _write(tmp_path, "skip.json", skipped)]) == 1


def test_pip_audit_and_npm_audit_refuse_an_empty_dependency_set(tmp_path):
    deps = [{"name": f"pkg{i}", "version": "1", "vulns": []} for i in range(40)]
    assert scan_floors.main(["pip-audit", _write(tmp_path, "pa.json", {"dependencies": deps})]) == 0
    assert scan_floors.main(["pip-audit", _write(tmp_path, "pa39.json", {"dependencies": deps[:39]})]) == 1
    vulnerable = [{**deps[0], "vulns": [{"id": "PYSEC-1"}]}, *deps[1:]]
    assert scan_floors.main(["pip-audit", _write(tmp_path, "pav.json", {"dependencies": vulnerable})]) == 1
    npm = {"metadata": {"dependencies": {"total": 100}, "vulnerabilities": {"high": 0, "critical": 0}}}
    assert scan_floors.main(["npm-audit", _write(tmp_path, "npm.json", npm)]) == 0
    npm["metadata"]["dependencies"]["total"] = 99
    assert scan_floors.main(["npm-audit", _write(tmp_path, "npm99.json", npm)]) == 1


def test_gitleaks_refuses_a_scan_that_never_saw_a_history(tmp_path):
    good = tmp_path / "good.log"
    good.write_text("INF 216 commits scanned.\nINF no leaks found\n")
    absent = str(tmp_path / "no-report.json")   # gitleaks writes no report when nothing was found
    assert scan_floors.main(["gitleaks", absent, "--log", str(good)]) == 0
    # The exact shape observed on a worktree: git failed, exit code stayed 0.
    broken = tmp_path / "broken.log"
    broken.write_text("ERR [git] fatal: not a git repository\nERR error=\"stderr is not empty\"\nINF no leaks found\n")
    assert scan_floors.main(["gitleaks", absent, "--log", str(broken)]) == 1
    silent = tmp_path / "silent.log"
    silent.write_text("INF no leaks found\n")
    assert scan_floors.main(["gitleaks", absent, "--log", str(silent)]) == 1
    assert scan_floors.main(["gitleaks", _write(tmp_path, "leak.json", [{"RuleID": "x"}]), "--log", str(good)]) == 1


def test_trivy_and_sbom_are_bound_to_the_built_image(tmp_path):
    packages = [{"Name": f"p{i}"} for i in range(100)]
    report = {"Metadata": {"ImageID": "sha256:abc"}, "Results": [{"Packages": packages}]}
    assert scan_floors.main(["trivy", _write(tmp_path, "t.json", report), "--image-id", "sha256:abc"]) == 0
    assert scan_floors.main(["trivy", _write(tmp_path, "t.json", report), "--image-id", "sha256:other"]) == 1
    report["Results"][0]["Packages"] = packages[:99]
    assert scan_floors.main(["trivy", _write(tmp_path, "t99.json", report), "--image-id", "sha256:abc"]) == 1
    bom = {"bomFormat": "CycloneDX", "metadata": {"component": {"name": "caos-app:ci"}},
           "components": [{"name": f"c{i}"} for i in range(100)]}
    assert scan_floors.main(["sbom", _write(tmp_path, "s.json", bom), "--image", "caos-app:ci"]) == 0
    assert scan_floors.main(["sbom", _write(tmp_path, "s.json", bom), "--image", "caos-worker:ci"]) == 1
    bom["components"] = bom["components"][:99]
    assert scan_floors.main(["sbom", _write(tmp_path, "s99.json", bom), "--image", "caos-app:ci"]) == 1


def test_manifest_binds_reports_to_the_commit_and_images_and_refuses_empties(tmp_path):
    report = tmp_path / "trivy-app.json"
    report.write_text("{}")
    out = tmp_path / "manifest.json"
    assert scan_floors.main(["manifest", str(out), "--commit", "a" * 40, "--image", "app=sha256:1",
                             "--report", f"trivy-app={report}"]) == 0
    payload = json.loads(out.read_text())
    assert payload["images"] == {"app": "sha256:1"} and payload["reports"]["trivy-app"]["bytes"] == 2
    empty = tmp_path / "empty.json"
    empty.write_text("")
    assert scan_floors.main(["manifest", str(out), "--commit", "a" * 40, "--image", "app=sha256:1",
                             "--report", f"empty={empty}"]) == 1
    with pytest.raises(SystemExit):
        scan_floors.main(["manifest", str(out)])
