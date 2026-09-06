"""Operator authority, durable one-shot bootstrap, and atomic policy changes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from caos.api import create_app
from caos.storage.store import DomainStore


def headers(subject="operator", groups="caos-admin", **extra):
    return {"x-edge-authorization": "test-edge", "x-forwarded-user": subject,
            "x-forwarded-groups": groups, **extra}


def test_bootstrap_http_requires_independent_operator_and_never_grants_visibility(store, settings):
    case = store.create_case("Case", "Issuer", "Services", "creator")["id"]
    settings = replace(settings, environment="production", edge_proxy_secret="test-edge",
                       enterprise_operator_subjects=("operator", "creator"))
    with TestClient(create_app(settings=settings, store=store, engine=None)) as client:
        route = f"/api/admin/cases/{case}/bootstrap-approver"
        body = {"subject": "approver", "rationale": "Independent filing review"}
        for subject, group in (("ordinary-admin", "caos-admin"), ("operator", "caos-reader"),
                               ("operator", "caos-analyst")):
            auth = headers(subject, group, **{"x-caos-role": "ADMIN"})
            assert client.post(route, headers=auth, json=body).status_code == 403
            assert not client.get("/api/me", headers=auth).json()["can_bootstrap_approver"]
        assert client.post(route, json=body).status_code == 401
        for subject in ("operator", "creator"):
            assert client.post(route, headers=headers(), json={**body, "subject": subject}).status_code == 403
        assert client.post(route, headers=headers("creator"), json=body).status_code == 403
        assert client.post(route, headers=headers(), json={**body, "role": "ADMIN"}).status_code == 422
        receipt = client.post(route, headers=headers(), json=body)
        assert receipt.status_code == 201, receipt.text
        assert set(receipt.json()) == {"case_id", "subject", "role", "actor", "at"}
        assert client.post(route, headers=headers(), json=body).json() == receipt.json()
        assert client.get(f"/api/cases/{case}", headers=headers()).status_code == 404
        assert client.get(f"/api/cases/{case}/sources", headers=headers()).status_code == 404
        assert client.get("/api/me", headers=headers()).json()["can_manage_providers"]
        assert store.add_member(case, "approver", "approver", "READER")
        assert client.post(route, headers=headers(), json=body).json() == receipt.json()
        assert store.is_member(case, "approver", {"READER"})
        assert client.post(route, headers=headers(), json={**body, "subject": "other"}).status_code == 409
        events = [event for event in store.audit_trail() if event["action"] == "case.approver_bootstrapped"]
        assert len(events) == 1


def test_bootstrap_race_and_audit_failure_are_atomic(store, monkeypatch):
    case = store.create_case("Case", "Issuer", "Services", "creator")["id"]
    original = DomainStore._audit
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(DomainStore, "_audit", fail)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            store.bootstrap_approver(case, "operator", "first", "review")
    assert not store.is_member(case, "first")
    assert DomainStore._audit is original
    def attempt(subject):
        try:
            return store.bootstrap_approver(case, "operator", subject, "review")
        except ValueError as error:
            return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("first", "second")))
    assert sum(isinstance(item, dict) for item in results) == 1
    assert "APPROVER_ALREADY_BOOTSTRAPPED" in results
    assert sum(store.is_member(case, person, {"APPROVER"}) for person in ("first", "second")) == 1


def test_provider_policy_compare_and_swap_and_audit_rollback(store, monkeypatch):
    assert store.get_provider_policy("claude") == {"binding_id": "claude", "version": 0}
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    with monkeypatch.context() as patch:
        patch.setattr(DomainStore, "_audit", fail)
        with pytest.raises(RuntimeError):
            store.set_provider_default("openai", "operator", 0, "claude")
    assert store.get_provider_policy("claude")["version"] == 0
    assert store.set_provider_default("openai", "operator", 0, "claude") == {"binding_id": "openai", "version": 1}
    with pytest.raises(ValueError, match="PROVIDER_POLICY_STALE"):
        store.set_provider_default("claude", "operator", 0, "claude")
    assert store.set_provider_default("openai", "operator", 1, "claude")["version"] == 1
    assert len([e for e in store.audit_trail() if e["action"] == "provider.default_changed"]) == 1
