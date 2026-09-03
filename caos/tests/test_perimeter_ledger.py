"""docs/PERIMETER_LEDGER.csv maps IAM-001–020, SEC-001–030, WEB-001–015 and
PERF-001–015 (ENTERPRISE_TESTING_READINESS) to a retained check, a release
gate, a candidate-only harness invocation, a structural pin, a manual
checklist, or an explicit BLOCKED EXTERNAL input. It is only evidence while
every row is present, every named test exists, and no external blocker hides
behind a mechanism that claims to run."""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs" / "PERIMETER_LEDGER.csv"
COLUMNS = ["check_id", "family", "condition", "mechanism", "evidence", "atlas_owasp", "notes", "recorded"]
MECHANISMS = {"retained-test", "release-gate", "candidate-harness", "structural", "manual-checklist", "BLOCKED EXTERNAL"}
EXPECTED = [f"IAM-{i:03d}" for i in range(1, 21)] + [f"SEC-{i:03d}" for i in range(1, 31)] \
    + [f"WEB-{i:03d}" for i in range(1, 16)] + [f"PERF-{i:03d}" for i in range(1, 16)]


def _rows() -> list[dict[str, str]]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == COLUMNS, reader.fieldnames
        return list(reader)


def test_every_check_is_present_once_with_a_declared_mechanism():
    rows = _rows()
    assert [row["check_id"] for row in rows] == EXPECTED
    for row in rows:
        assert row["mechanism"] in MECHANISMS, f"{row['check_id']}: {row['mechanism']!r}"
        for column in ("condition", "evidence", "recorded"):
            assert row[column].strip(), f"{row['check_id']} leaves {column} empty"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["recorded"])
        if row["mechanism"] == "BLOCKED EXTERNAL":
            assert row["notes"].strip(), f"{row['check_id']} must say what external input is needed"


def _references(row: dict[str, str]) -> list[str]:
    return [item.strip() for item in row["evidence"].split(";") if item.strip()]


def test_every_referenced_file_and_test_exists():
    for row in _rows():
        for reference in _references(row):
            if reference.startswith("none") or reference.startswith("ENTERPRISE_") or reference.startswith("DESIGN"):
                continue
            path, _, name = reference.partition("::")
            path = re.sub(r"\s*\(.*$", "", path)
            file = REPO / path
            assert file.exists(), f"{row['check_id']} names a missing path: {path}"
            if not name or file.is_dir():
                continue
            name = re.sub(r"\s*\(.*$", "", name)
            text = file.read_text(encoding="utf-8")
            if path.endswith(".py"):
                assert re.search(rf"^\s*(async )?def {re.escape(name)}\(", text, re.MULTILINE), \
                    f"{row['check_id']}: no function {name} in {path}"
            elif path.endswith(".ts"):
                assert f'test("{name}"' in text or f"test('{name}'" in text, f"{row['check_id']}: no test {name!r} in {path}"
            else:
                assert name in text, f"{row['check_id']}: {name!r} not found in {path}"


def test_every_security_row_carries_a_framework_mapping():
    for row in _rows():
        if row["family"] in {"IAM", "SEC"} and row["mechanism"] != "structural":
            assert row["atlas_owasp"].strip() and row["atlas_owasp"] != "—", f"{row['check_id']} has no OWASP/ATLAS mapping (SEC-029)"


def test_blocked_external_rows_are_exactly_the_declared_inputs():
    blocked = {row["check_id"] for row in _rows() if row["mechanism"] == "BLOCKED EXTERNAL"}
    assert blocked == {"SEC-023", "SEC-024", "SEC-025", "SEC-028"}, blocked
    text = LEDGER.read_text(encoding="utf-8")
    # The live halves that also wait on the enterprise identity provider say so in their notes.
    for check in ("IAM-016", "WEB-013", "SEC-022"):
        row = next(r for r in _rows() if r["check_id"] == check)
        assert "BLOCKED EXTERNAL" in row["notes"], check
    assert text.count("BLOCKED EXTERNAL") >= 7


def test_every_fixed_defect_names_a_regression_test_that_exists():
    """SEC-030: a closed security or integrity defect keeps a permanent test."""
    with (REPO / "docs" / "QUALITY_DEFECTS.csv").open(newline="", encoding="utf-8") as handle:
        defects = list(csv.DictReader(handle))
    assert defects, "the defects ledger is not empty"
    for defect in defects:
        if not defect["Status"].startswith("FIXED"):
            continue
        regression = defect["Regression Test"]
        assert regression.strip(), f"{defect['Defect ID']} names no regression test"
        for match in re.finditer(r"(caos/tests/[\w/]+\.py)::(test_\w+)", regression):
            file = REPO / match.group(1)
            assert file.is_file(), f"{defect['Defect ID']}: {match.group(1)} is missing"
            assert re.search(rf"^(async )?def {match.group(2)}\(", file.read_text(encoding="utf-8"), re.MULTILINE), \
                f"{defect['Defect ID']}: {match.group(2)} no longer exists"
