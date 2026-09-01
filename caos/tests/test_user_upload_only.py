"""User-upload-only source-ingestion policy."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".cfg", ".cjs", ".css", ".graphql", ".html", ".ini", ".js", ".json", ".jsx",
    ".md", ".mjs", ".py", ".sh", ".sql", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml",
}
ACQUISITION_VERBS = "search|fetch|pull|retrieve|acquire|vault"
FILING_SOURCES = "external|public|regulatory|SEC"
FORBIDDEN = re.compile("|".join((
    "Octa" + "gon",
    "EDGAR" + "_USER_AGENT",
    "/api/" + "edgar",
    r"(?:data|efts|www)?\.?sec\.gov/(?:Archives|LATEST|cgi-bin|submissions)",
    "EDGAR" + "CovenantSourceMap",
    r"free (?:SEC )?EDGAR " + "lane",
    "pulled-and-" + "vaulted",
    "pull and " + "vault",
    "vault-" + "exhibit",
    r"caos/server/" + r"(?:routes/)?edgar\.py",
    "caos/mcp/" + "edgar/",
    rf"\b(?:{ACQUISITION_VERBS})\b.{{0,100}}\b(?:{FILING_SOURCES})\b.{{0,40}}\bfilings?\b",
    rf"\b(?:{FILING_SOURCES})\b.{{0,40}}\bfilings?\b.{{0,100}}\b(?:{ACQUISITION_VERBS})\b",
)), re.IGNORECASE)


def test_tracked_product_sources_prohibit_external_filing_acquisition():
    tracked = subprocess.run(
        ["git", "ls-files", "--", "caos"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    matches = []
    for relative in tracked:
        path = REPO / relative
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                matches.append(f"{relative}:{line_number}: {line.strip()}")
    assert not matches, "external filing acquisition is forbidden:\n" + "\n".join(matches)
