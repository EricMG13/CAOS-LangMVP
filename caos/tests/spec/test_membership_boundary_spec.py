"""Membership boundary and role-change refusals (adversarial review 2026-09-06,
findings C2 and W8).

C2: `MemberRequest.subject` reaches `case_members` and the hash-chained
`case.member_added` audit row, so it is BoundaryText like every other string
that enters pinned state — refused at the wire for control bytes, bidirectional
overrides and lone surrogates, NFC-normalized before it is stored — and the
identity edge presents the subject in the same form, so stored standing and
presented identity compare equal.

W8: `DomainStore.add_member` refuses a member changing their own role and a
change that would leave the case with no ADMIN, typed, inside the transaction
that would have written the audit row — so a refused change writes nothing.
"""

from __future__ import annotations

import json

import pytest

ADMIN_H = {"x-caos-role": "ADMIN", "x-forwarded-user": "case-admin"}
NFC = "Am\u00e9lie"
NFD = "Ame\u0301lie"


def _case_with_admin(store) -> str:
    """The creator holds ANALYST standing; `case-admin` is the case's only ADMIN."""
    case = store.create_case("Case", "Issuer", "Services", "analyst")
    assert store.add_member(case["id"], "analyst", "case-admin", "ADMIN", actor_role="ADMIN")
    return case["id"]


def _members(store, case_id: str) -> dict[str, str]:
    return store.get_case(case_id)["members"]


def _member_rows(store, case_id: str) -> list[dict]:
    return [row for row in store.audit_chain(case_id) if row["action"] == "case.member_added"]


# --- C2: the subject is BoundaryText at the wire and at the identity edge ------------


@pytest.mark.parametrize(
    "bad", ["\u202e", "\u0007", "\ud800"], ids=["bidi-override", "control-byte", "lone-surrogate"],
)
def test_member_subject_is_boundary_text_at_the_wire(client, store, bad):
    case_id = _case_with_admin(store)
    before = (_members(store, case_id), store.audit_chain(case_id))
    # Pre-encoded body: httpx cannot UTF-8-encode a raw lone surrogate, so every
    # probe rides the wire as its ASCII JSON escape, which the server decodes back
    # into the character before the boundary check — the contract under test.
    body = json.dumps({"subject": f"probe-{bad}-subject", "role": "APPROVER"}, ensure_ascii=True).encode("ascii")
    response = client.post(
        f"/api/cases/{case_id}/members", content=body,
        headers={**ADMIN_H, "content-type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert [error["loc"] for error in response.json()["detail"]] == [["body", "subject"]]
    escaped = json.dumps(bad, ensure_ascii=True).strip('"')
    assert bad not in response.text and escaped not in response.text and "probe-" not in response.text, \
        "rejected input must not be echoed back through the response encoder"
    assert (_members(store, case_id), store.audit_chain(case_id)) == before, "a refused subject writes nothing"


def test_member_subject_is_stored_and_audited_nfc_and_the_presented_identity_matches(client, store):
    case_id = _case_with_admin(store)
    url = f"/api/cases/{case_id}/members"
    created = client.post(url, json={"subject": NFD, "role": "APPROVER"}, headers=ADMIN_H)
    assert created.status_code == 201, created.text
    assert NFC in created.json()["members"] and NFD not in created.json()["members"]
    assert store.is_member(case_id, NFC, roles={"APPROVER"})
    assert not store.is_member(case_id, NFD), "one spelling, one standing: the decomposed form is not a second member"

    rows = _member_rows(store, case_id)
    assert [row["data"]["member"] for row in rows if row["actor"] == "case-admin"] == [NFC]
    assert NFD not in json.dumps(rows, ensure_ascii=False), "the hash-chained audit row carries the NFC form"
    assert store.verify_audit_chain(case_id) == {}

    # The identity edge: Starlette reads header values as latin-1 while the trusted
    # edge writes the subject's UTF-8 bytes, and an IdP may spell the subject either
    # way — both spellings present as the one stored member.
    for presented in (NFC, NFD):
        headers = {"x-caos-role": "APPROVER", "x-forwarded-user": presented.encode("utf-8")}
        assert client.get("/api/me", headers=headers).json()["subject"] == NFC
        assert client.get(f"/api/cases/{case_id}", headers=headers).status_code == 200, presented.encode("utf-8")
    stranger = {"x-caos-role": "APPROVER", "x-forwarded-user": "Amelie"}
    assert client.get(f"/api/cases/{case_id}", headers=stranger).status_code == 404


def test_the_identity_edge_presents_the_subject_nfc_in_both_environments(tmp_path):
    """Development (`x-forwarded-user` trusted as sent) and production (OIDC
    behind the edge secret) present one NFC subject for either spelling; the
    role derivation and the edge-secret check are untouched, and identity
    bytes that are not UTF-8 were not written by the trusted edge — 401."""
    from fastapi import HTTPException
    from starlette.requests import Request

    from caos.config import Settings
    from caos.identity import identity_from_request

    secret = "e" * 40
    development = Settings(storage_dir=tmp_path / "vault")
    production = Settings(storage_dir=tmp_path / "vault", environment="production", edge_proxy_secret=secret)
    edge = (b"x-edge-authorization", secret.encode())
    groups = (b"x-forwarded-groups", b"caos-approver")

    def presented(settings, *headers):
        scope = {"type": "http", "method": "GET", "path": "/api/me", "query_string": b"", "headers": list(headers)}
        return identity_from_request(Request(scope), settings)

    for raw in (NFC.encode("utf-8"), NFD.encode("utf-8")):
        assert presented(development, (b"x-forwarded-user", raw)).subject == NFC
        who = presented(production, edge, groups, (b"x-forwarded-user", raw))
        assert (who.subject, who.role) == (NFC, "APPROVER")
        by_email = presented(production, edge, groups, (b"x-forwarded-email", raw + b"@example.com"))
        assert (by_email.subject, by_email.email) == (NFC + "@example.com", NFC + "@example.com")
    for settings in (development, production):
        with pytest.raises(HTTPException) as refused:
            presented(settings, edge, groups, (b"x-forwarded-user", b"Am\xe9lie"))
        assert refused.value.status_code == 401
    assert presented(development).subject == "analyst", "the headerless development default is unchanged"


# --- W8: role changes that dissolve the case's own governance are refused ------------


def test_a_member_cannot_change_their_own_role(app, store):
    from fastapi.testclient import TestClient

    case_id = _case_with_admin(store)
    assert store.add_member(case_id, "case-admin", "approver-a", "APPROVER")
    before = (_members(store, case_id), store.audit_chain(case_id))
    with pytest.raises(ValueError, match="^MEMBER_SELF_ROLE_CHANGE"):
        store.add_member(case_id, "approver-a", "approver-a", "ADMIN")  # an approver promoting themselves
    with pytest.raises(ValueError, match="^MEMBER_SELF_ROLE_CHANGE"):
        store.add_member(case_id, "case-admin", "case-admin", "READER")  # the admin stepping down alone
    with pytest.raises(ValueError, match="^MEMBER_SELF_ROLE_CHANGE"):
        store.add_member(case_id, "case-admin", "case-admin", "ADMIN", actor_role="ADMIN")  # global ADMIN, same subject
    assert (_members(store, case_id), store.audit_chain(case_id)) == before, "a refused change writes nothing"

    # Over the route the refusal is typed in-process and the transaction rolls
    # back before the audit row; the route serves no 2xx and moves nothing. The
    # route does not yet map the typed code to 403 (it has no `except ValueError`),
    # so the status is not pinned here — the store seam above is.
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/api/cases/{case_id}/members", json={"subject": "approver-a", "role": "ADMIN"},
            headers={"x-caos-role": "APPROVER", "x-forwarded-user": "approver-a"},
        )
    assert not 200 <= response.status_code < 300, response.text
    assert (_members(store, case_id), store.audit_chain(case_id)) == before
    assert store.verify_audit_chain(case_id) == {}

    # The rule is about standing, not spelling: a subject with no row yet is
    # provisioned as before, whoever the actor is.
    assert store.add_member(case_id, "platform-admin", "platform-admin", "READER", actor_role="ADMIN")
    assert _members(store, case_id)["platform-admin"] == "READER"


def test_the_last_admin_cannot_be_demoted(store):
    case_id = _case_with_admin(store)
    assert store.add_member(case_id, "case-admin", "approver-a", "APPROVER")
    before = (_members(store, case_id), store.audit_chain(case_id))
    with pytest.raises(ValueError, match="^MEMBER_LAST_ADMIN_DEMOTION"):
        store.add_member(case_id, "approver-a", "case-admin", "APPROVER")
    with pytest.raises(ValueError, match="^MEMBER_LAST_ADMIN_DEMOTION"):
        store.add_member(case_id, "platform-admin", "case-admin", "READER", actor_role="ADMIN")
    assert (_members(store, case_id), store.audit_chain(case_id)) == before, "a refused change writes nothing"

    # "Last" counts stored ADMIN rows — the creator's ANALYST standing is not one.
    # With a second ADMIN the first can step down; the second then becomes the last.
    assert store.add_member(case_id, "case-admin", "case-admin-2", "ADMIN")
    assert store.add_member(case_id, "case-admin-2", "case-admin", "APPROVER")
    assert _members(store, case_id)["case-admin"] == "APPROVER"
    with pytest.raises(ValueError, match="^MEMBER_LAST_ADMIN_DEMOTION"):
        store.add_member(case_id, "case-admin", "case-admin-2", "APPROVER")
    assert store.add_member(case_id, "case-admin", "case-admin-2", "ADMIN"), "confirming ADMIN at ADMIN is not a demotion"
    assert _members(store, case_id)["case-admin-2"] == "ADMIN"
    assert store.verify_audit_chain(case_id) == {}


def test_an_admin_demotes_an_approver_and_an_approver_still_provisions_an_approver(client, store):
    case_id = _case_with_admin(store)
    url = f"/api/cases/{case_id}/members"
    approver_h = {"x-caos-role": "APPROVER", "x-forwarded-user": "approver-a"}
    assert client.post(url, json={"subject": "approver-a", "role": "APPROVER"}, headers=ADMIN_H).status_code == 201

    # An APPROVER provisions a new APPROVER — the publication spec depends on it.
    minted = client.post(url, json={"subject": "approver-b", "role": "APPROVER"}, headers=approver_h)
    assert minted.status_code == 201, minted.text
    assert minted.json()["members"]["approver-b"] == "APPROVER"

    # An ADMIN demotes an APPROVER: the change and its audit row land together.
    chain_before = store.audit_chain(case_id)
    demoted = client.post(url, json={"subject": "approver-a", "role": "READER"}, headers=ADMIN_H)
    assert demoted.status_code == 201, demoted.text
    assert demoted.json()["members"]["approver-a"] == "READER"
    assert store.is_member(case_id, "approver-a", roles={"READER"})
    appended = store.audit_chain(case_id)[len(chain_before):]
    assert [(row["action"], row["actor"], row["data"]["member"], row["data"]["role"]) for row in appended] == [
        ("case.member_added", "case-admin", "approver-a", "READER"),
    ]
    assert store.verify_audit_chain(case_id) == {}
    assert client.post(url, json={"subject": "approver-c", "role": "APPROVER"}, headers=approver_h).status_code == 403, \
        "the demoted approver no longer provisions"
