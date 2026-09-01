"""User-upload-only source-ingestion policy."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CP1C_ROOT = (
    REPO
    / "caos/server/caos/methodology/vendor/deploy_v/skills/cp-1c-peer-benchmark"
)
ACQUISITION_VERBS = "|".join((
    "sear" + "ch(?:es|ed|ing)?", "fet" + "ch(?:es|ed|ing)?",
    "down" + "load(?:s|ed|ing)?", "pu" + "ll(?:s|ed|ing)?",
    "retr" + "iev(?:e|es|ed|ing)", "acq" + "uir(?:e|es|ed|ing)",
    "va" + "ult(?:s|ed|ing)?", "brow" + "s(?:e|es|ed|ing)",
    "que" + "ry|queries|queried|querying", "loc" + "at(?:e|es|ed|ing)",
))
FILING_LOCATIONS = "|".join(("S" + "EC(?:\\s+(?:web\\s+)?site)?", "ED" + "GAR"))
GENERIC_LOCATIONS = "|".join(("pub" + r"lic(?!-)", "exter" + r"nal(?!-)"))
FILING_OBJECTS = "|".join(("fil" + "ings?", "exhi" + "bits?", "10-[KQ]"))
SEC_HOST = (
    r"(?<![A-Za-z0-9-])(?:[A-Za-z0-9-]+\.)*s" + r"ec\.gov"
    r"(?=$|[/?#:\s),;]|\.(?![A-Za-z0-9-]))"
)
RETRIEVAL_CLAUSE = (
    rf"(?=[^.!?]{{0,240}}\b(?:{ACQUISITION_VERBS})\b)"
    rf"(?=[^.!?]{{0,240}}\b(?:{FILING_LOCATIONS})\b)"
    rf"(?=[^.!?]{{0,240}}\b(?:{FILING_OBJECTS})\b)[^.!?]{{1,240}}"
)
GENERIC_RETRIEVAL_CLAUSE = (
    rf"(?=[^.!?]{{0,120}}\b(?:{ACQUISITION_VERBS})\b)"
    rf"(?=[^.!?]{{0,120}}\b(?:{GENERIC_LOCATIONS})\b)"
    rf"(?=[^.!?]{{0,120}}\b(?:{FILING_OBJECTS})\b)"
    r"[^.!?]{1,120}"
)
FORBIDDEN = re.compile("|".join((
    "Octa" + "gon",
    "ED" + "GAR_USER_AGENT",
    "/api/e" + "dgar",
    SEC_HOST,
    "ED" + "GARCovenantSourceMap",
    r"free (?:SEC )?ED" + "GAR lane",
    "pul" + "led-and-va" + "ulted",
    "pu" + "ll and va" + "ult",
    "va" + "ult-exhi" + "bit",
    r"caos/server/(?:routes/)?e" + r"dgar\.py",
    "caos/mcp/e" + "dgar/",
    RETRIEVAL_CLAUSE,
    GENERIC_RETRIEVAL_CLAUSE,
)), re.IGNORECASE | re.DOTALL)
CP1C_FORBIDDEN = re.compile("|".join((
    r"w" + r"eb\s*-?\s*discovery",
    r"w" + r"eb\s*-?\s*scrap\w*",
    r"scr" + r"ape\s+URL",
    "auto_" + "discover",
    "reputable_" + "public_web",
    r"w" + r"eb\s*-?\s*sourced",
    rf"\b(?:{ACQUISITION_VERBS})\b[^.!?]{{0,120}}"
    rf"\b(?:{GENERIC_LOCATIONS})\b[^.!?]{{0,120}}\b(?:{FILING_OBJECTS})\b",
)), re.IGNORECASE | re.DOTALL)


def test_detector_catches_reviewer_variants():
    variants = (
        "Sear" + "ch sec" + ".gov for the issuer latest 10-K and use its exhibits.",
        "Down" + "load the issuer public filing from sec" + ".gov.",
        "Sear" + "ch the S" + "EC site for the issuer\nfiling exhibits.",
        "Retr" + "ieve from https://www.sec" + ".gov/ixviewer/doc/action?doc=x",
        "Pub" + "lic fil" + "ings may be down" + "loaded.",
        "Sear" + "ch for fil" + "ings on the S" + "EC site.",
        "Sear" + "ch fil" + "ings from exter" + "nal sources.",
        "Fil" + "ings from exter" + "nal sources should be down" + "loaded.",
        "Brow" + "sing S" + "EC exhi" + "bits is required.",
    )
    assert all(FORBIDDEN.search(variant) for variant in variants)
    assert not FORBIDDEN.search("not" + "sec.gov.example.com")
    assert not FORBIDDEN.search(
        "Que" + "ry a pub" + "lic-private peer set from regulatory fil" + "ings."
    )


def test_deployed_cp1c_has_no_external_peer_acquisition_lane():
    matches = []
    for path in sorted(CP1C_ROOT.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for match in CP1C_FORBIDDEN.finditer(text):
            relative = path.relative_to(REPO)
            line_number = text.count("\n", 0, match.start()) + 1
            matches.append(f"{relative}:{line_number}: {' '.join(match.group().split())}")
    assert not matches, "CP-1C external peer acquisition is forbidden:\n" + "\n".join(matches)


def test_tracked_product_sources_prohibit_external_filing_acquisition():
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "caos"],
        cwd=REPO,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    matches = []
    for raw_relative in filter(None, tracked):
        relative = os.fsdecode(raw_relative)
        path = REPO / relative
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for match in FORBIDDEN.finditer(text):
            line_number = text.count("\n", 0, match.start()) + 1
            snippet = " ".join(match.group().split())[:200]
            matches.append(f"{relative}:{line_number}: {snippet}")
    assert not matches, "external filing acquisition is forbidden:\n" + "\n".join(matches)
