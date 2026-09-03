"""Acceptance-criteria probe for the production-configured app.

One assertion per criterion in `qa/INVENTORY.md` that is observable at the HTTP
boundary. Browser-observable criteria (focus order, modals, keyboard) are
covered by `npm run test:workbench` and `npm run a11y`, and by the manual pass
recorded in `qa/FINDINGS.md`.

ponytail: plain asserts, no framework. Exit code is the number of failures.

    python qa/probe.py            # against http://127.0.0.1:8099
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.getenv("CAOS_APP_URL", "http://127.0.0.1:8099")
EDGE = os.environ["EDGE_PROXY_SECRET"]

PERSONAS = {
    "ANALYST": ("analyst.qa@caos.invalid", "caos-analyst"),
    "APPROVER": ("approver.qa@caos.invalid", "caos-approver"),
    "ADMIN": ("admin.qa@caos.invalid", "caos-admin"),
    "READER": ("reader.qa@caos.invalid", "caos-reader"),
    "NOGROUP": ("stranger.qa@caos.invalid", ""),
    "OUTSIDER": ("outsider.qa@caos.invalid", "caos-analyst"),
}

failures: list[str] = []
checks = 0


def head(persona: str) -> dict[str, str]:
    email, groups = PERSONAS[persona]
    return {
        "x-edge-authorization": EDGE,
        "x-forwarded-user": email,
        "x-forwarded-email": email,
        "x-forwarded-groups": groups,
    }


def check(criterion: str, condition: bool, detail: str = "") -> None:
    global checks
    checks += 1
    if condition:
        print(f"  PASS {criterion}")
    else:
        failures.append(f"{criterion}: {detail}")
        print(f"  FAIL {criterion} — {detail}")


def main() -> None:
    client = httpx.Client(base_url=BASE, timeout=60)

    print("\n== identity and roles ==")
    for persona, expected in (("ANALYST", "ANALYST"), ("APPROVER", "APPROVER"),
                              ("ADMIN", "ADMIN"), ("READER", "READER"), ("NOGROUP", "READER")):
        served = client.get("/api/me", headers=head(persona)).json()
        check(f"AC-ROLE-1 {persona}", served.get("role") == expected, f"served {served}")

    forged = client.get("/api/me", headers={**head("READER"), "x-caos-role": "ADMIN"}).json()
    check("AC-ROLE-2", forged.get("role") == "READER", f"served {forged}")

    unauth = client.get("/api/cases")
    check("AC-EDGE-1 no edge secret refused", unauth.status_code == 401, f"{unauth.status_code}")
    bad_secret = client.get("/api/cases", headers={**head("ANALYST"), "x-edge-authorization": "x" * 64})
    check("AC-EDGE-2 wrong edge secret refused", bad_secret.status_code == 401, f"{bad_secret.status_code}")
    check("AC-EDGE-3 health stays public", client.get("/api/health").status_code == 200)

    cases = client.get("/api/cases", headers=head("ANALYST")).json()
    check("seed present", len(cases) >= 40, f"{len(cases)} cases")
    shared = next((c for c in cases if c["id"]), None)
    assert shared is not None
    case_id = shared["id"]

    print("\n== case visibility ==")
    unknown = client.get("/api/cases/case-does-not-exist-0000", headers=head("ANALYST"))
    outsider = client.get(f"/api/cases/{case_id}", headers=head("OUTSIDER"))
    check("AC-ROLE-3 unknown == unauthorised",
          unknown.status_code == outsider.status_code == 404,
          f"unknown {unknown.status_code}, outsider {outsider.status_code}")
    check("AC-ROLE-3b outsider list is empty",
          client.get("/api/cases", headers=head("OUTSIDER")).json() == [])

    print("\n== reader is read-only ==")
    reader_case = next((c["id"] for c in client.get("/api/cases", headers=head("READER")).json()), None)
    check("reader sees seeded member cases", reader_case is not None, "reader has no case")
    if reader_case:
        for label, response in (
            ("upload", client.post(f"/api/cases/{reader_case}/sources",
                                   files={"file": ("x.txt", b"line", "text/plain")}, headers=head("READER"))),
            ("note", client.post(f"/api/cases/{reader_case}/notes",
                                 json={"body": "x"}, headers=head("READER"))),
            ("run", client.post(f"/api/cases/{reader_case}/runs",
                                json={"pathway": "EARNINGS_UPDATE", "depth": "screen"}, headers=head("READER"))),
            ("rv", client.post(f"/api/cases/{reader_case}/rv",
                               json={"rows": [{"issuer": "A", "instrument": "B", "currency": "EUR"}]},
                               headers=head("READER"))),
            ("model", client.post(f"/api/cases/{reader_case}/models", json={}, headers=head("READER"))),
        ):
            check(f"AC-ROLE-4 reader {label} refused", response.status_code == 403, f"{response.status_code}")
        check("AC-ROLE-4 reader can read",
              client.get(f"/api/cases/{reader_case}/sources", headers=head("READER")).status_code == 200)

    print("\n== source admission ==")
    probe_case = client.post("/api/cases", json={"name": "Probe", "issuer": "Probe Issuer", "sector": "QA"},
                             headers=head("ANALYST")).json()["id"]
    admission = [
        ("oversized", ("big.txt", b"x" * (26 * 1024 * 1024), "text/plain"), 413, 422),
        ("disallowed suffix", ("payload.exe", b"MZ binary", "application/octet-stream"), 415, 422),
        ("empty file", ("empty.txt", b"", "text/plain"), 422, 422),
        ("whitespace only", ("blank.txt", b"   \n\t\n", "text/plain"), 422, 422),
        ("eicar", ("v.txt", rb"X5O!P%@AP[4\PZX54(P^)7CC)7}EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*", "text/plain"), 422, 422),
    ]
    for label, upload, *accepted in admission:
        response = client.post(f"/api/cases/{probe_case}/sources", files={"file": upload},
                               headers=head("ANALYST"), timeout=180)
        check(f"AC-CASES-3 {label} refused", response.status_code in accepted,
              f"{response.status_code} {response.text[:120]}")

    before = client.get(f"/api/cases/{probe_case}", headers=head("ANALYST")).json()
    check("AC-CASES-3b refusals did not version the set", before.get("source_count", 0) == 0,
          f"source_count {before.get('source_count')}")

    print("\n== boundary text ==")
    for label, value, expect in (
        ("control byte", "Bad\x07Issuer", 422),
        ("bidi override", "Bad\u202eIssuer", 422),
        # CVE-2021-42574 bans overrides and isolates, not marks: an RTL issuer
        # name legitimately carries U+200F and must still be accepted.
        ("directional mark stays legal", "\u200f\u0634\u0631\u0643\u0629", 201),
        ("over-length", "x" * 161, 422),
    ):
        response = client.post("/api/cases", json={"name": "Boundary", "issuer": value, "sector": "QA"},
                               headers=head("ANALYST"))
        check(f"AC-X-7 {label}", response.status_code == expect, f"{response.status_code} {response.text[:120]}")

    print("\n== wire strictness ==")
    extra = client.post("/api/cases", json={"name": "X", "issuer": "Y", "sector": "Z", "unexpected": 1},
                        headers=head("ANALYST"))
    check("AC-X-1 undeclared request field refused", extra.status_code == 422, f"{extra.status_code}")

    print("\n== pathway availability ==")
    # The criterion is agreement, not a fixed list: whatever the case wire offers
    # must start, and nothing else may. That is what drifted (F-1) — the menu held
    # its own copy of the cut.
    case_wire = client.get(f"/api/cases/{probe_case}", headers=head("ANALYST")).json()
    offered = set(case_wire["available_pathways"])
    outcomes = {}
    # Deep Research runs at full depth only and needs a brief; every other
    # pathway is probed at screen depth. Availability is derived server-side.
    research_brief = {
        "research_question": "How resilient is liquidity through the next refinancing?",
        "decision_context": "Probe of the deployment's research route.",
        "as_of_date": "2026-01-01", "time_horizon": "12 months",
        "must_answer": [], "exclusions": [],
    }
    for pathway in ("FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING",
                    "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING", "DEEP_RESEARCH"):
        body = ({"pathway": pathway, "depth": "full", "research_brief": research_brief}
                if pathway == "DEEP_RESEARCH" else {"pathway": pathway, "depth": "screen"})
        response = client.post(f"/api/cases/{probe_case}/runs", json=body,
                               headers=head("ANALYST"), timeout=60)
        outcomes[pathway] = response.status_code
    startable = {pathway for pathway in offered if pathway != "DEEP_RESEARCH"}
    if case_wire.get("deep_research_available") is True:
        startable.add("DEEP_RESEARCH")
    check("AC-RUN-5 offered pathways are exactly the startable ones",
          all((code == 201) is (pathway in startable) for pathway, code in outcomes.items()),
          f"offered={sorted(offered)} deep_research_available={case_wire.get('deep_research_available')} outcomes={outcomes}")

    print("\n== security headers ==")
    page = client.get("/cases/")
    for header in ("content-security-policy", "x-content-type-options", "referrer-policy",
                   "permissions-policy", "cross-origin-opener-policy", "strict-transport-security"):
        check(f"AC-X-3 {header}", header in page.headers, "absent")

    print("\n== admission ceilings ==")
    codes = [client.get("/api/health").status_code for _ in range(5)]
    check("AC-X-4 health unmetered", set(codes) == {200}, f"{codes}")

    print("\n== model / deliverable reachability ==")
    ready = [c for c in cases if c.get("accepted_snapshot_id")]
    check("accepted snapshots seeded", len(ready) >= 3, f"{len(ready)}")
    model_ready = []
    blocked = []
    misfiled = []
    for candidate in ready:
        readiness = client.get(f"/api/cases/{candidate['id']}/model", headers=head("ANALYST")).json()
        status = readiness.get("status")
        # NOT_READY belongs in the exclusion set: a case whose accepted
        # authority is the wrong pathway now reports NOT_READY, and counting it
        # as "reachable" would let AC-MB pass with nothing model-ready at all.
        if status not in {"CANONICAL_MODEL_INPUTS_INVALID", "NO_ACCEPTED_SNAPSHOT", "NOT_READY"}:
            model_ready.append((candidate["id"], status))
        blocked.extend(readiness.get("blockers") or [])
        # CANONICAL_MODEL_INPUTS_INVALID now means what it says: the accepted
        # FULL_CREDIT artifacts are missing, mismatched or fail bundle
        # validation. A healthy deployment never reaches it — a wrong-pathway
        # authority is a precondition (NOT_READY), not corruption, and only
        # NOT_READY keeps Model Builder's "Open Run Console" way out on screen.
        if status == "CANONICAL_MODEL_INPUTS_INVALID":
            misfiled.append((candidate["id"], readiness.get("blockers")))
    check("AC-MB reachable", bool(model_ready), "no case reaches model readiness")
    # Every readiness blocker is rendered by Model Builder as
    # `humanizeCode(code)` over `detail`; a null detail draws a bare heading
    # above a blank line, which is what a wrong-pathway analyst used to get.
    check("AC-MB every readiness blocker carries a detail the callout can render",
          all(item.get("detail") for item in blocked),
          f"{[item for item in blocked if not item.get('detail')]}")
    check("AC-MB no accepted authority reads as corrupt canonical inputs", not misfiled, f"{misfiled}")

    print(f"\n{checks - len(failures)}/{checks} criteria passed")
    for failure in failures:
        print(f"  - {failure}")
    sys.exit(len(failures))


if __name__ == "__main__":
    main()
