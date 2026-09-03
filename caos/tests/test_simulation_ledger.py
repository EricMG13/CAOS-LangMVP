"""docs/SIMULATION_LEDGER.csv is only evidence while it is complete and every
row points at a test that exists (ENTERPRISE_TESTING_READINESS SIM-001–030;
Phase 5 item 6). A renamed or deleted simulation turns this red instead of
leaving a ledger row that names nothing."""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs" / "SIMULATION_LEDGER.csv"
COLUMNS = ["sim_id", "condition", "seam", "tests", "injected_fault", "expected_outcome",
           "actual_outcome", "post_restart_state", "status", "recorded"]


def _rows() -> list[dict[str, str]]:
    with LEDGER.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == COLUMNS, reader.fieldnames
        return list(reader)


def test_every_simulation_row_is_present_once_and_complete():
    rows = _rows()
    assert [row["sim_id"] for row in rows] == [f"SIM-{index:03d}" for index in range(1, 31)]
    for row in rows:
        for column in COLUMNS:
            assert row[column].strip(), f"{row['sim_id']} leaves {column} empty"
        assert row["status"].startswith("PASS"), f"{row['sim_id']} is not a retained pass: {row['status']}"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["recorded"])


def test_every_referenced_simulation_test_exists():
    for row in _rows():
        for reference in row["tests"].split(";"):
            path, _, name = reference.strip().partition("::")
            file = REPO / path
            assert file.is_file(), f"{row['sim_id']} names a missing file: {path}"
            text = file.read_text(encoding="utf-8")
            if path.endswith(".ts"):
                assert f'test("{name}"' in text, f"{row['sim_id']}: no test named {name!r} in {path}"
            else:
                assert re.search(rf"^(async )?def {re.escape(name)}\(", text, re.MULTILINE), \
                    f"{row['sim_id']}: no test named {name} in {path}"


def test_ledger_rows_that_fixed_a_defect_name_the_fix():
    fixed = [row for row in _rows() if "defect fixed" in row["status"]]
    assert {row["sim_id"] for row in fixed} == {"SIM-008", "SIM-010", "SIM-012", "SIM-014", "SIM-016", "SIM-020"}
    for row in fixed:
        assert "before Task 12a" in row["actual_outcome"], f"{row['sim_id']} must record what the simulation found"
