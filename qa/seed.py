"""Production-scale sanitized data for local QA.

Everything here is synthetic. Issuers are invented names in the shape a
leveraged-finance desk would see; the document text is generated from
templates, never copied from a filing; no real company, person, price or
credential appears. The point is *shape and volume* — enough cases that a list
has to paginate mentally, sources large enough that `pack_blocks` takes its
grouped branch, runs in every terminal state — not realistic content.

Seeds through the HTTP API with the production edge headers, so every row is
written by the same code path a real analyst would drive. Membership is the one
exception: no route grants case membership (see qa/INVENTORY.md), so approver
and reader standing is written through the store directly.

    python qa/seed.py                 # against http://127.0.0.1:8099
"""

from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import httpx

BASE = os.getenv("CAOS_APP_URL", "http://127.0.0.1:8099")
EDGE_SECRET = os.environ["EDGE_PROXY_SECRET"]
ANALYST = "analyst.qa@caos.invalid"
APPROVER = "approver.qa@caos.invalid"
READER = "reader.qa@caos.invalid"
ADMIN = "admin.qa@caos.invalid"

# Scale knobs. Defaults are "a desk that has been running for two quarters".
CASES = int(os.getenv("QA_CASES", "48"))
RUNS = int(os.getenv("QA_RUNS", "18"))

rng = random.Random(20260830)


def headers(subject: str, groups: str) -> dict[str, str]:
    return {
        "x-edge-authorization": EDGE_SECRET,
        "x-forwarded-user": subject,
        "x-forwarded-email": subject,
        "x-forwarded-groups": groups,
    }


ANALYST_HEADERS = headers(ANALYST, "caos-analyst")

# Invented issuers: a real desk's book is mid-cap sponsor-owned borrowers, so the
# names read that way without naming anyone. Sector strings match what the RV and
# Command Center surfaces group by.
STEMS = [
    "Northwind", "Calder", "Brightmoor", "Vantage Hollow", "Ironvale", "Marchfield",
    "Ashcombe", "Rookery", "Thornbury", "Pelham Reach", "Cadence Peak", "Wexford",
    "Silverkeep", "Draycott", "Halloway", "Merristone", "Fenwick", "Aldergate",
    "Quillon", "Ravensmoor", "Stonebridge", "Larkspur", "Tallowick", "Ambervale",
]
FORMS = ["Holdings", "Group", "Industries", "Partners", "Bidco", "Midco", "Topco", "Logistics"]
SECTORS = [
    "Business Services", "Healthcare", "Chemicals", "Packaging", "Software",
    "Building Products", "Consumer", "Leisure", "Telecom", "Auto Components",
]
PATHWAYS = ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE",
            "DISTRESSED_RESTRUCTURING"]


def annual_report(issuer: str, year: int, paragraphs: int) -> str:
    """A filing-shaped document: headed sections, a numeric table, prose. Numbers
    are drawn from the PRNG, so they are internally consistent per call and
    reproducible across seeds, and mean nothing."""
    revenue = rng.randint(400, 4200)
    margin = rng.uniform(0.11, 0.29)
    ebitda = round(revenue * margin, 1)
    debt = round(ebitda * rng.uniform(3.4, 6.8), 1)
    lines = [
        f"{issuer} — Annual Report and Accounts, financial year {year}",
        "",
        "SECTION 1. OPERATING AND FINANCIAL REVIEW",
        "",
        f"Revenue for the period was EUR {revenue}.0m against EUR {round(revenue * rng.uniform(0.88, 1.06), 1)}m "
        f"in the prior year. Adjusted EBITDA of EUR {ebitda}m represents a margin of {margin:.1%}.",
        f"Net debt at the balance sheet date was EUR {debt}m, equivalent to {debt / ebitda:.2f}x adjusted EBITDA.",
        "",
        "SECTION 2. SUMMARY FINANCIALS (EUR m)",
        "Metric,FY,Prior FY",
        f"Revenue,{revenue}.0,{round(revenue * rng.uniform(0.88, 1.06), 1)}",
        f"Adjusted EBITDA,{ebitda},{round(ebitda * rng.uniform(0.85, 1.1), 1)}",
        f"Net debt,{debt},{round(debt * rng.uniform(0.9, 1.15), 1)}",
        f"Cash interest,{round(debt * rng.uniform(0.05, 0.09), 1)},{round(debt * rng.uniform(0.04, 0.08), 1)}",
        "",
        "SECTION 3. PRINCIPAL RISKS",
        "",
    ]
    risks = [
        "Input cost inflation may not be recoverable through contractual pass-through in all regions.",
        "A concentration of revenue in the group's five largest customers persists.",
        "The senior facilities agreement contains a springing net leverage covenant tested quarterly.",
        "Foreign exchange translation exposure arises on the group's non-euro operating subsidiaries.",
        "Working capital is seasonally weighted to the second half of the financial year.",
    ]
    for index in range(paragraphs):
        lines.append(f"3.{index + 1} {rng.choice(risks)}")
        lines.append(
            f"Management assesses the residual exposure as {rng.choice(['low', 'moderate', 'elevated'])} "
            f"and reviews it at each meeting of the Audit Committee. "
            f"The sensitivity disclosed in note {rng.randint(9, 31)} assumes a "
            f"{rng.randint(25, 300)} basis point movement."
        )
        lines.append("")
    return "\n".join(lines)


def credit_agreement(issuer: str, paragraphs: int) -> str:
    lines = [
        f"SENIOR FACILITIES AGREEMENT — {issuer.upper()} BIDCO S.A.R.L.",
        "",
        "CLAUSE 1. DEFINITIONS AND INTERPRETATION",
        "",
    ]
    for index in range(paragraphs):
        lines.append(f"1.{index + 1} \"Consolidated EBITDA\" means, in respect of any Relevant Period, "
                     f"the consolidated operating profit of the Group before taxation, adjusted by adding back "
                     f"amounts attributable to the amortisation of acquired intangibles and by excluding "
                     f"exceptional items not exceeding EUR {rng.randint(5, 60)}.0m in aggregate.")
        lines.append(f"1.{index + 1}.1 The Permitted Payment basket shall not exceed the greater of "
                     f"EUR {rng.randint(10, 120)}.0m and {rng.randint(5, 25)}% of Consolidated EBITDA.")
        lines.append("")
    return "\n".join(lines)


def earnings_release(issuer: str, quarter: str) -> str:
    return "\n".join([
        f"{issuer} reports {quarter} results",
        "",
        f"Organic revenue growth of {rng.uniform(-4, 11):.1f}% in the quarter.",
        f"Adjusted EBITDA margin of {rng.uniform(11, 29):.1f}%, {rng.randint(-180, 210)}bps year on year.",
        f"Net leverage of {rng.uniform(3.2, 7.4):.2f}x, against a covenant level of 7.50x tested quarterly.",
        "",
        "Outlook: management reiterates full-year guidance and expects free cash flow conversion "
        f"of approximately {rng.randint(45, 90)}% of adjusted EBITDA.",
    ])


def upload(client: httpx.Client, case_id: str, filename: str, text: str) -> dict | None:
    response = client.post(
        f"/api/cases/{case_id}/sources",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
        headers=ANALYST_HEADERS,
        timeout=180,
    )
    if response.status_code != 201:
        print(f"  ! upload {filename} -> {response.status_code} {response.text[:200]}", file=sys.stderr)
        return None
    return response.json()


def wait_terminal(client: httpx.Client, run_id: str, budget_s: float = 120) -> dict:
    deadline = time.time() + budget_s
    run: dict = {}
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}", headers=ANALYST_HEADERS, timeout=30).json()
        if run.get("status") in {"succeeded", "failed", "paused"}:
            return run
        time.sleep(0.5)
    return run


def add_members(case_ids: list[str]) -> None:
    """No HTTP route grants membership, so this reaches the store. Seeding
    concern only — the finding that the product cannot do it is logged, not
    papered over."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "caos" / "server"))
    from caos.storage.store import DomainStore

    store = DomainStore.from_url(os.environ["DATABASE_URL"])
    for case_id in case_ids:
        for member, role in ((APPROVER, "APPROVER"), (READER, "READER"), (ADMIN, "ADMIN")):
            store.add_member(case_id, ANALYST, member, role, actor_role="ADMIN")


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=60)
    health = client.get("/api/health").json()
    print(f"server: {health}")

    created: list[dict] = []
    for index in range(CASES):
        issuer = f"{STEMS[index % len(STEMS)]} {FORMS[index % len(FORMS)]}"
        if index >= len(STEMS):
            issuer = f"{issuer} II"
        sector = SECTORS[index % len(SECTORS)]
        name = rng.choice([
            "Annual credit review", "Q3 earnings update", "Refinancing assessment",
            "Covenant reset review", "New money underwrite", "Watchlist deep-dive",
        ])
        response = client.post(
            "/api/cases",
            json={"name": name, "issuer": issuer, "sector": sector},
            headers=ANALYST_HEADERS,
        )
        if response.status_code != 201:
            print(f"! case {issuer} -> {response.status_code} {response.text[:200]}", file=sys.stderr)
            continue
        created.append(response.json())
    print(f"cases: {len(created)}")

    source_total = 0
    for index, case in enumerate(created):
        issuer = case["issuer"]
        # Most cases carry a normal working set; a few carry the volume a
        # long-running name accumulates, and one carries a document large
        # enough to force pack_blocks onto its grouped branch.
        count = 2 if index % 5 == 0 else rng.randint(3, 6)
        docs: list[tuple[str, str]] = [
            (f"{issuer.split()[0].lower()}-annual-report-2025.txt", annual_report(issuer, 2025, 12)),
            (f"{issuer.split()[0].lower()}-sfa-extract.txt", credit_agreement(issuer, 10)),
        ]
        for extra in range(count - 2):
            docs.append((
                f"{issuer.split()[0].lower()}-q{extra + 1}-2026-release.txt",
                earnings_release(issuer, f"Q{extra + 1} 2026"),
            ))
        if index == 0:
            docs.append((f"{issuer.split()[0].lower()}-annual-report-large.txt",
                         annual_report(issuer, 2024, 9000)))
        for filename, text in docs:
            if upload(client, case["id"], filename, text):
                source_total += 1
        # A withdrawn source on some cases: the source-set version must move on.
        if index % 7 == 3:
            sources = client.get(f"/api/cases/{case['id']}/sources", headers=ANALYST_HEADERS).json()
            if sources:
                client.post(
                    f"/api/cases/{case['id']}/sources/{sources[-1]['id']}/withdraw",
                    headers=ANALYST_HEADERS,
                )
        if index % 3 == 0:
            note = client.post(
                f"/api/cases/{case['id']}/notes",
                json={"body": f"Desk note: {issuer} covenant headroom reviewed against the "
                              f"quarterly test; no action pending the next compliance certificate."},
                headers=ANALYST_HEADERS,
            )
            if note.status_code == 201 and index % 6 == 0:
                client.post(
                    f"/api/cases/{case['id']}/notes/{note.json()['id']}/promote",
                    headers=ANALYST_HEADERS,
                )
        if index % 4 == 1:
            rows = [
                {
                    "issuer": f"{STEMS[(index + offset) % len(STEMS)]} {FORMS[offset % len(FORMS)]}",
                    "instrument": f"TLB {2029 + offset % 4}",
                    "currency": rng.choice(["EUR", "USD", "GBP"]),
                    "price": round(rng.uniform(82, 101), 3),
                    "yield_bps": round(rng.uniform(420, 1450), 1),
                    "spread_bps": round(rng.uniform(310, 1180), 1),
                    "duration": round(rng.uniform(1.8, 5.4), 2),
                }
                for offset in range(rng.randint(6, 18))
            ]
            client.post(f"/api/cases/{case['id']}/rv", json={"rows": rows}, headers=ANALYST_HEADERS)
    print(f"sources: {source_total}")

    accepted = 0
    for index, case in enumerate(created[:RUNS]):
        pathway = PATHWAYS[index % len(PATHWAYS)]
        depth = "screen"
        response = client.post(
            f"/api/cases/{case['id']}/runs",
            json={"pathway": pathway, "depth": depth},
            headers=ANALYST_HEADERS,
            timeout=120,
        )
        if response.status_code != 201:
            print(f"  ! run {case['issuer']} {pathway} -> {response.status_code} {response.text[:300]}",
                  file=sys.stderr)
            continue
        run = wait_terminal(client, response.json()["id"])
        print(f"  run {case['issuer'][:22]:<22} {pathway:<26} {run.get('status')}")
        if run.get("status") == "succeeded" and index % 2 == 0:
            acceptance = client.post(f"/api/runs/{run['id']}/accept", headers=ANALYST_HEADERS, timeout=60)
            if acceptance.status_code == 200:
                accepted += 1
    print(f"accepted snapshots: {accepted}")

    # Half the cases get the full role cast so approver/reader journeys have
    # somewhere to land; the rest stay analyst-only, which is the shape a real
    # deployment has for a case nobody has shared yet.
    add_members([case["id"] for case in created[::2]])
    print(f"members granted on {len(created[::2])} cases")


if __name__ == "__main__":
    main()
