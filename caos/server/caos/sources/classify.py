"""Host classification of prepared documents (Task 8; DECISIONS §14.2, §14.3).

Everything here is a deterministic projection of prepared evidence: document
type, period, revision status, issuer candidate and the pack's route decision
are read from bounded block text and filenames through fixed signal tables.
Every value carries the signals that produced it and a confidence, and the
wire labels the whole set `host_classification` so the analyst reviews it as
a machine suggestion. Instructions inside a document are inert: nothing here
executes text, and the route depends on structural signals (a form heading,
a legal instrument, a parseable brief or workbook), never on imperative prose.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from ..engine.provider import AgentError
from ..engine.research import validate_brief

MAX_SCAN_BLOCKS = 80
MAX_SCAN_CHARS = 40_000
HEADING_CHARS = 600
TEXTLESS_PDF_MARKER = "no text layer was available"  # the extractor's own placeholder (domain.py)

DOCUMENT_TYPE_PRECEDENCE = (
    "restructuring", "amendment", "credit_agreement", "annual_report",
    "quarterly_report", "earnings_release", "management_guidance",
)

# (document_type, signal name, pattern) — matched case-insensitively; a hit in
# the heading zone weighs three, elsewhere one.
_SIGNALS: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    (kind, name, re.compile(pattern, re.IGNORECASE))
    for kind, name, pattern in (
        ("restructuring", "transaction_support_agreement",
         r"\btransaction support agreement\b|\brestructuring support agreement\b"),
        ("restructuring", "exchange_offer", r"\bexchange offer"),
        ("restructuring", "forbearance", r"\bforbearance\b"),
        ("restructuring", "chapter_11", r"\bchapter 11\b"),
        ("amendment", "amendment_heading", r"\bamendment no\.?\s*\d+\b|\bamendment to (?:the )?credit agreement\b"),
        ("credit_agreement", "credit_agreement_heading", r"\bcredit agreement\b"),
        ("credit_agreement", "indenture", r"\bindenture\b"),
        ("credit_agreement", "facility_terms", r"\bterm loan\b|\brevolving credit\b|\bfinancial covenants?\b"),
        ("annual_report", "form_10k", r"\bform 10-k\b"),
        ("annual_report", "annual_report_heading", r"\bannual report\b"),
        ("annual_report", "fiscal_year_ended", r"\bfiscal year ended\b|\bfor the year ended\b"),
        ("quarterly_report", "form_10q", r"\bform 10-q\b"),
        ("quarterly_report", "quarterly_report_heading", r"\bquarterly report\b|\bquarterly period ended\b"),
        ("quarterly_report", "interim_period", r"\b(?:three|six|nine) months ended\b"),
        ("earnings_release", "earnings_release", r"\bearnings release\b|\breports (?:first|second|third|fourth) quarter\b|\bquarter(?:ly)? results\b"),
        ("management_guidance", "guidance", r"\bguidance\b|\boutlook\b|\bmanagement forecast\b"),
    )
)

_CONSUMERS = {
    "annual_report": ["CP-PARSE", "CP-0", "CP-1", "CP-2", "CP-MODEL"],
    "quarterly_report": ["CP-PARSE", "CP-0", "CP-1", "CP-1B", "CP-MODEL"],
    "earnings_release": ["CP-PARSE", "CP-0", "CP-1B"],
    "management_guidance": ["CP-PARSE", "CP-0", "CP-1B", "CP-MODEL"],
    "credit_agreement": ["CP-PARSE", "CP-0", "CP-4"],
    "amendment": ["CP-PARSE", "CP-0", "CP-4"],
    "restructuring": ["CP-PARSE", "CP-0", "CP-4C"],
    "market_marks": ["CP-3"],
    "research_brief": ["CP-DR"],
    "other": ["CP-PARSE", "CP-0"],
}

_LEGAL_SUFFIXES = {
    "corporation", "corp", "incorporated", "inc", "plc", "ltd", "limited", "holdings",
    "holding", "group", "company", "co", "llc", "lp", "l.p", "nv", "n.v", "sa", "s.a",
    "ag", "se", "partners",
}
_SUFFIX_PATTERN = (
    r"Corporation|Corp\.?|Incorporated|Inc\.?|plc|PLC|Ltd\.?|Limited|Holdings|Holding|Group|"
    r"Company|Co\.|LLC|L\.P\.|LP|N\.V\.|S\.A\.|AG|SE|Partners"
)
# A cover-page line that names a legal entity: the candidate is the prefix up to
# its last legal-form token ("Carnival Corporation & plc Investor Relations" →
# "Carnival Corporation & plc"); trailing words are not part of the name.
_ISSUER_LINE = re.compile(
    rf"^(?P<name>[A-Z][A-Za-z0-9&'\-]*(?:\s+[A-Za-z0-9&'\-]+){{0,6}}?\s+(?:{_SUFFIX_PATTERN})(?:\s+&\s+(?:plc|PLC))?(?:\s+(?:plc|PLC))?)\b"
)
_BORROWER = re.compile(r"\bamong\s+(?P<name>[A-Z][^,\n]{2,90}?),\s+as\s+(?:the\s+)?Borrower\b")
_REPORTS = re.compile(r"^(?P<name>[A-Z][A-Za-z0-9&'\-]*(?:\s+[A-Za-z0-9&'\-]+){0,6})\s+Reports\s+(?:First|Second|Third|Fourth)\s+Quarter\b")

_FISCAL_YEAR = re.compile(
    r"(?:fiscal year ended|for the year ended|year ended)\s+(?:[A-Z][a-z]+\s+\d{1,2},?\s+)?(?P<year>(?:19|20)\d{2})"
    r"|\bfiscal\s+(?P<year2>(?:19|20)\d{2})\b|\bFY\s?(?P<year3>(?:19|20)\d{2})\b|\bfull year\s+(?P<year4>(?:19|20)\d{2})\b",
    re.IGNORECASE,
)
_QUARTER_PERIOD = re.compile(
    r"(?:quarterly period ended|(?:three|six|nine) months ended)\s+(?P<month>[A-Z][a-z]+)\s+\d{1,2},?\s+(?P<year>(?:19|20)\d{2})",
    re.IGNORECASE,
)
_QUARTER_WORD = re.compile(r"\b(?P<word>first|second|third|fourth)\s+quarter\b(?:\s+(?:of\s+)?(?:fiscal\s+)?(?P<year>(?:19|20)\d{2}))?", re.IGNORECASE)
_MONTHS = {name: index for index, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), start=1)}
_QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_RESTATED = re.compile(r"\brestated\b|\bamended and restated\b", re.IGNORECASE)
_SECTOR_HINTS = (
    ("Leisure & Travel", re.compile(r"\bcruise|\bhotel|\bresort|\bairline", re.IGNORECASE)),
    ("Technology", re.compile(r"\bsoftware\b|\bsemiconductor|\bcloud services", re.IGNORECASE)),
    ("Healthcare", re.compile(r"\bhospital|\bpharma|\bmedical device", re.IGNORECASE)),
    ("Energy", re.compile(r"\boil and gas\b|\bupstream\b|\bmidstream\b", re.IGNORECASE)),
)


def bounded_text(blocks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    total = 0
    for block in blocks[:MAX_SCAN_BLOCKS]:
        text = str(block.get("text") or "")
        if total + len(text) > MAX_SCAN_CHARS:
            parts.append(text[: MAX_SCAN_CHARS - total])
            break
        parts.append(text)
        total += len(text)
    return "\n".join(parts)


def normalize_issuer(name: str) -> str:
    tokens = [token for token in re.sub(r"[^\w\s]", " ", name.casefold()).split() if token]
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _issuer_candidate(text: str) -> tuple[str | None, str | None]:
    heading = text[:HEADING_CHARS]
    for line in (line.strip() for line in heading.splitlines()[:8]):
        match = _ISSUER_LINE.match(line)
        if match:
            return match.group("name").strip(), "issuer_heading_line"
        match = _REPORTS.match(line)
        if match:
            return match.group("name").strip(), "earnings_headline"
    match = _BORROWER.search(text)
    if match:
        return match.group("name").strip(), "borrower_clause"
    return None, None


def _period(text: str, document_type: str) -> tuple[dict[str, Any] | None, list[str]]:
    signals: list[str] = []
    fiscal_year: int | None = None
    quarter: int | None = None
    quarter_match = _QUARTER_PERIOD.search(text)
    if quarter_match:
        month = _MONTHS.get(quarter_match.group("month").casefold())
        if month:
            quarter = (month - 1) // 3 + 1
            fiscal_year = int(quarter_match.group("year"))
            signals.append("interim_period_end")
    word_match = _QUARTER_WORD.search(text)
    if word_match and quarter is None:
        quarter = _QUARTER_WORDS[word_match.group("word").casefold()]
        signals.append("quarter_word")
        if word_match.group("year"):
            fiscal_year = int(word_match.group("year"))
    year_match = _FISCAL_YEAR.search(text)
    if year_match and (fiscal_year is None or document_type == "annual_report"):
        fiscal_year = int(next(value for value in year_match.groups() if value))
        signals.append("fiscal_year_end")
    if fiscal_year is None:
        return None, signals
    if document_type in {"annual_report", "credit_agreement", "amendment", "restructuring", "management_guidance"}:
        quarter = None
    label = f"FY{fiscal_year}" if quarter is None else f"FY{fiscal_year}-Q{quarter}"
    return {"fiscal_year": fiscal_year, "quarter": quarter, "label": label}, signals


def _research_brief(filename: str, text: str) -> tuple[dict[str, Any] | None, str | None]:
    """A JSON document carrying exactly the brief contract is the analyst's
    brief supplied as a file; anything else is not a brief, however it is named."""
    if not filename.lower().endswith((".json", ".md", ".txt")):
        return None, None
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None, None
    try:
        decoded = json.loads(stripped)
    except ValueError:
        return None, None
    if not isinstance(decoded, dict) or set(decoded) != {
        "research_question", "decision_context", "as_of_date", "time_horizon", "must_answer", "exclusions",
    }:
        return None, None
    try:
        return validate_brief(decoded), None
    except AgentError as exc:
        return None, exc.code


def _market_marks(filename: str, content: bytes, sha256: str) -> bool:
    if not filename.lower().endswith(".xlsx"):
        return False
    from ..artifacts.loan_universe import LoanWorkbookValidationError, parse_loan_workbook

    try:
        parse_loan_workbook(content, source_id="intake-candidate", source_sha256=sha256)
    except LoanWorkbookValidationError:
        return False
    except Exception:  # noqa: BLE001 — any other parser failure is "not a loan universe", never a crash
        return False
    return True


def classify_document(filename: str, content: bytes, sha256: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    text = bounded_text(blocks)
    heading = text[:HEADING_CHARS]
    signals: list[str] = []
    textless = TEXTLESS_PDF_MARKER in text.casefold() and len(text.strip()) < 200
    if textless:
        return {
            "document_type": "other", "period": None, "version_status": "original",
            "issuer": None, "issuer_basis": None, "text_layer": False, "signals": ["no_text_layer"],
            "confidence": "low", "brief": None, "brief_error": None,
        }
    brief, brief_error = _research_brief(filename, text)
    if brief is not None or brief_error is not None:
        return {
            "document_type": "research_brief", "period": None, "version_status": "original",
            "issuer": None, "issuer_basis": None, "text_layer": True,
            "signals": ["research_brief_contract" if brief else f"research_brief_invalid:{brief_error}"],
            "confidence": "high" if brief else "low", "brief": brief, "brief_error": brief_error,
        }
    if _market_marks(filename, content, sha256):
        return {
            "document_type": "market_marks", "period": None, "version_status": "original",
            "issuer": None, "issuer_basis": None, "text_layer": True,
            "signals": ["loan_universe_template"], "confidence": "high", "brief": None, "brief_error": None,
        }
    scores: Counter[str] = Counter()
    for kind, name, pattern in _SIGNALS:
        in_heading = pattern.search(heading) is not None
        if in_heading or pattern.search(text):
            scores[kind] += 3 if in_heading else 1
            signals.append(f"{name}{':heading' if in_heading else ''}")
    document_type = "other"
    if scores:
        best = max(scores.values())
        document_type = next(kind for kind in DOCUMENT_TYPE_PRECEDENCE if scores.get(kind) == best)
    period, period_signals = _period(text, document_type)
    signals.extend(period_signals)
    issuer, issuer_basis = _issuer_candidate(text)
    if issuer_basis:
        signals.append(issuer_basis)
    version_status = "original"
    if document_type == "amendment":
        version_status = "amendment"
    elif _RESTATED.search(heading):
        version_status = "restated"
        signals.append("restated")
    confidence = "high" if scores and best >= 3 else "medium" if scores else "low"
    return {
        "document_type": document_type, "period": period, "version_status": version_status,
        "issuer": issuer, "issuer_basis": issuer_basis, "text_layer": True, "signals": signals,
        "confidence": confidence, "brief": None, "brief_error": None,
    }


def suggest_sector(texts: list[str]) -> str:
    joined = "\n".join(text[:HEADING_CHARS * 4] for text in texts)
    for sector, pattern in _SECTOR_HINTS:
        if pattern.search(joined):
            return sector
    return "Unclassified"


def _period_key(period: dict[str, Any] | None) -> tuple[int, int]:
    if not period:
        return (0, 0)
    return (period["fiscal_year"], period["quarter"] or 0)


def coverage(documents: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [document for document in documents if document["disposition"] in {"used", "superseded"} and document.get("period")]
    fiscal_years = sorted({document["period"]["fiscal_year"] for document in evidence if document["period"]["quarter"] is None})
    quarters = sorted(
        {document["period"]["label"] for document in evidence if document["period"]["quarter"] is not None},
        key=lambda label: (int(label[2:6]), int(label[-1])),
    )
    latest = max((document["period"] for document in evidence), key=_period_key, default=None)
    gaps: list[str] = []
    if latest and latest["quarter"]:
        present = {document["period"]["quarter"] for document in evidence
                   if document["period"]["fiscal_year"] == latest["fiscal_year"] and document["period"]["quarter"]}
        gaps = [f"FY{latest['fiscal_year']}-Q{quarter}" for quarter in range(1, latest["quarter"]) if quarter not in present]
    return {
        "fiscal_years": fiscal_years,
        "quarters": quarters,
        "latest_period": latest["label"] if latest else None,
        "gaps": gaps,
    }


def select_route(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Full Credit at full depth unless the pack proves a narrower objective.
    The decision cites the signals it relied on; a brief or a workbook counts
    only when it parsed against its own contract."""
    used = [document for document in documents if document["disposition"] == "used"]
    types = Counter(document["document_type"] for document in used)
    by_type = lambda kind: [document["filename"] for document in used if document["document_type"] == kind]  # noqa: E731

    if types.get("research_brief") == 1:
        return {"pathway": "DEEP_RESEARCH", "depth": "full", "selected_by": "host_classification",
                "reason": "One research brief satisfying the brief contract was supplied with the pack; the run is scoped to that question.",
                "evidence": [f"research_brief:{name}" for name in by_type("research_brief")]}
    if types.get("market_marks"):
        return {"pathway": "RELATIVE_VALUE", "depth": "full", "selected_by": "host_classification",
                "reason": "A loan-universe workbook in the CP-3 template was supplied alongside issuer evidence; market marks prove the relative-value objective.",
                "evidence": [f"market_marks:{name}" for name in by_type("market_marks")]}
    if types.get("restructuring"):
        return {"pathway": "DISTRESSED_RESTRUCTURING", "depth": "full", "selected_by": "host_classification",
                "reason": "A restructuring instrument (support agreement, exchange offer or forbearance) is in the pack.",
                "evidence": [f"restructuring:{name}" for name in by_type("restructuring")]}
    financial = {"annual_report", "quarterly_report", "earnings_release", "management_guidance"}
    legal = {"credit_agreement", "amendment"}
    present = set(types)
    if present and present <= {"quarterly_report", "earnings_release", "management_guidance"} and "annual_report" not in present:
        return {"pathway": "EARNINGS_UPDATE", "depth": "full", "selected_by": "host_classification",
                "reason": "Only earnings-period material (quarterly report, earnings release, guidance) was supplied; the objective is an earnings update.",
                "evidence": [f"{document['document_type']}:{document['filename']}" for document in used]}
    if present and present <= legal:
        return {"pathway": "COVENANT_REFINANCING", "depth": "full", "selected_by": "host_classification",
                "reason": "Only legal instruments (credit agreement, amendments) were supplied; the objective is covenant and refinancing analysis.",
                "evidence": [f"{document['document_type']}:{document['filename']}" for document in used]}
    reason = "Default governed route: no narrower objective is proven by the supplied documents."
    if present & financial and present & legal:
        reason = "Default governed route: financial statements and legal instruments together support a full credit assessment."
    return {"pathway": "FULL_CREDIT", "depth": "full", "selected_by": "host_classification",
            "reason": reason, "evidence": [f"{document['document_type']}:{document['filename']}" for document in used]}


def consumers_for(document_type: str) -> list[str]:
    return list(_CONSUMERS.get(document_type, _CONSUMERS["other"]))
