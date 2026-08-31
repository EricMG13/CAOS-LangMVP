#!/usr/bin/env python3
"""Phase-1 exit criterion, made mechanical.

`docs/QUALITY_LEDGER.csv` claims every feature in this repo is documented. That
claim decays the moment someone adds a route or a file, so it is checked here
rather than asserted. Two checks, deliberately different in kind:

  * ROUTES — fully automatic. Every path in `@app.<method>("...")` must appear
    verbatim in the ledger. Nothing to maintain: add a route without documenting
    it and this fails.
  * FILES — a hand-written prefix table. Every tracked product file must match
    one entry. Adding a subsystem means adding a line here AND a ledger row,
    which is the forcing function; agent tooling, docs and the vendored
    methodology bundle are excluded by name.

Run: python docs/quality_ledger_coverage.py   (exit 0 = the ledger is complete)
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs" / "QUALITY_LEDGER.csv"
API = ROOT / "caos" / "server" / "caos" / "api" / "__init__.py"

# Checked-in but not the product: agent skills, review notes, design history.
EXCLUDED_PREFIXES = (".agents/", ".claude/", ".github/skills/", ".github/hooks/",
                     "notes/", "DESIGN-IS-2026-08-27/", ".agent-reviews/", ".impeccable/")
EXCLUDED_FILES = {".gitattributes", ".gitignore", ".fallowrc.json", ".gitleaks.toml", "LICENSE",
                  "caos/tests/corpus/.gitignore"}

FILE_MAP = {
    r"^caos/server/caos/api/": "F-CASE-*, F-SRC-*, F-RUN-*, F-MODEL-*, F-DELIV-*, F-SEC-01..06",
    r"^caos/server/caos/identity\.py": "F-AUTH-01..06",
    r"^caos/server/caos/config\.py": "F-CFG-01, F-CFG-02",
    r"^caos/server/caos/(contracts|responses)\.py": "F-SEC-07, F-SEC-08",
    r"^caos/server/caos/sources/": "F-SRC-01..14",
    r"^caos/server/caos/storage/": "F-CASE-*, F-SRC-13, F-RUN-04, F-RUN-12, F-MODEL-02, F-DELIV-02",
    r"^caos/server/caos/engine/": "F-RUN-02..20",
    r"^caos/server/caos/methodology/": "F-RUN-11, F-RUN-15",
    r"^caos/server/caos/modules/": "F-RUN-02, F-RUN-16",
    r"^caos/server/caos/models/": "F-MODEL-01..12",
    r"^caos/server/caos/deliverables/": "F-DELIV-01..12",
    r"^caos/server/caos/publishing/": "F-DELIV-10, F-DELIV-11",
    r"^caos/server/caos/artifacts/": "F-LU-01..03, F-RV-03",
    r"^caos/server/caos/atomic_files\.py": "F-SRC-09",
    r"^caos/server/caos/__init__\.py": "package marker",
    r"^caos/server/dev\.py": "F-OPS-01",
    r"^caos/server/run\.py": "F-OPS-02, F-RUN-20",
    r"^caos/server/worker\.py": "F-OPS-03, F-MODEL-11",
    r"^caos/server/(pyproject\.toml|requirements)": "F-OPS-09",
    r"^caos/tests/": "the executing suite for every feature",
    # Same standing as caos/tests: a harness that exercises the surface rather
    # than a subsystem a feature owns. It drives the production-configured
    # stack (qa/INVENTORY.md) instead of the in-process app the suite uses.
    r"^qa/": "the production-configured QA harness for every feature",
    r"^caos/frontend/app/": "F-UI-01, F-UI-13, F-UI-14, F-UI-15",
    r"^caos/frontend/src/": "F-UI-01..12",
    r"^caos/frontend/scripts/a11y-axe": "F-UI-14, F-UI-15",
    r"^caos/frontend/scripts/workbench-smoke": "F-UI-02, F-UI-04",
    r"^caos/frontend/scripts/production-inventory": "F-OPS-02 (D-009)",
    r"^caos/frontend/(next\.config|eslint\.config|tsconfig|package)": "F-OPS-04, F-OPS-09",
    r"^caos/scripts/build_frontend\.sh": "F-OPS-04",
    r"^caos/deploy/(backup|restore_drill)\.sh": "F-OPS-05",
    r"^caos/deploy/verify_image_resources\.py": "F-OPS-06",
    r"^caos/deploy/Dockerfile": "F-OPS-06, F-OPS-11",
    r"^caos/deploy/docker-compose\.yml": "F-CFG-03, F-OPS-08",
    r"^caos/deploy/(Caddyfile|oauth2-proxy\.cfg|clamd\.conf)": "F-OPS-08",
    r"^caos/\.env\.example": "F-CFG-03",
    r"^\.github/workflows/ci\.yml": "F-OPS-07, F-OPS-09, F-OPS-11",
    r"^\.github/workflows/nightly\.yml": "F-OPS-07",
    r"^\.github/workflows/security-review\.yml": "F-OPS-10",
    r"^\.github/dependabot\.yml": "F-OPS-09",
    r"^run_sec_audit\.py": "F-SEC-09",
    r"^(pytest\.ini|ruff\.toml)": "F-OPS-07",
    # The quality process's own artifacts. Named rather than excluded, because
    # "docs/ is not product" would also hide a future doc that IS a feature —
    # and because this check first went red on exactly these three files, which
    # were untracked when it was written and tracked the moment it was committed.
    r"^docs/(QUALITY_[A-Z]+\.csv|quality_ledger_coverage\.py)$": "the ledger itself",
    r"^Modular OS/tools/": "F-OPS-07 (module consistency check)",
    r"^Modular OS/": "F-RUN-15 (methodology corpus the vendored bundle is built from)",
}


def product_files() -> list[str]:
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.splitlines()
    return sorted(
        path for path in tracked
        if not path.startswith(EXCLUDED_PREFIXES)
        and "methodology/vendor/" not in path
        and not path.endswith((".md", ".b64"))
        and path not in EXCLUDED_FILES
    )


def main() -> int:
    ledger_text = LEDGER.read_text()
    rows = list(csv.DictReader(LEDGER.open()))
    failures: list[str] = []

    routes = sorted(set(re.findall(r'@app\.(?:get|post|put|patch|delete)\(\s*"([^"]+)"',
                                   API.read_text())))
    undocumented = [route for route in routes if route not in ledger_text]
    failures += [f"route not in the ledger: {route}" for route in undocumented]

    files = product_files()
    unmapped = [f for f in files if not any(re.search(k, f) for k in FILE_MAP)]
    failures += [f"product file maps to no feature: {f}" for f in unmapped]

    ids = [row["Feature ID"] for row in rows]
    if len(ids) != len(set(ids)):
        failures.append("duplicate Feature IDs in the ledger")

    print(f"routes checked: {len(routes)}   product files: {len(files)}   "
          f"features: {len(ids)}")
    for failure in failures:
        print(f"  FAIL {failure}")
    if failures:
        return 1
    print("the ledger documents every route and every product file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
