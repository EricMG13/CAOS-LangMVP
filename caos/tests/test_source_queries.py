"""Metadata-only inventory and bounded, case-scoped full evidence search."""
from fastapi.testclient import TestClient

from caos.api import create_app


def add_source(store, case, source_id, text, filename="evidence.txt"):
    return store.ingest({"id": source_id, "case_id": case, "filename": filename,
                         "media_type": "text/plain", "bytes": len(text), "sha256": source_id,
                         "blocks": [{"block_id": f"b{index}", "text": text + f" {index}",
                                     "locator": {"page": index, "worksheet": "RÉSUMÉ: data"}, "confidence": "HIGH",
                                     "untrusted_data": True, "extractor_version": "test"}
                                    for index in range(3)]}, "analyst")


def test_inventory_search_pagination_privacy_and_historical_detail(store, settings):
    case = store.create_case("Case", "Issuer", "Services", "analyst")["id"]
    foreign = store.create_case("Other", "Other", "Services", "other")["id"]
    add_source(store, case, "src-a", "prefix " * 500 + "Unique 100%_needle suffix")
    add_source(store, case, "src-b", "Another unopened document ÉNERGIE", "debt.csv")
    add_source(store, foreign, "src-c", "Unique 100%_needle private")
    with TestClient(create_app(settings=settings, store=store, engine=None)) as client:
        base = f"/api/cases/{case}"
        first = client.get(base + "/source-summaries", params={"limit": 1}).json()
        assert first["sources"][0]["id"] == "src-a"
        assert first["sources"][0]["block_count"] == 3
        assert "blocks" not in first["sources"][0] and "vault_path" not in first["sources"][0]
        second = client.get(base + "/source-summaries", params={"cursor": first["next_cursor"]}).json()
        assert [s["id"] for s in second["sources"]] == ["src-b"] and second["next_cursor"] is None
        search = base + "/evidence-search"
        found = client.get(search, params={"q": "100%_needle", "limit": 2}).json()
        assert len(found["matches"]) == 2
        assert all(m["source_id"] == "src-a" and "100%_needle" in m["text"]
                   and len(m["text"]) <= 1200 for m in found["matches"])
        final = client.get(search, params={"q": "100%_needle", "cursor": found["next_cursor"]}).json()
        assert [m["block_id"] for m in final["matches"]] == ["b2"] and final["next_cursor"] is None
        assert len(client.get(search, params={"q": "debt.csv"}).json()["matches"]) == 3
        assert len(client.get(search, params={"q": "énergie"}).json()["matches"]) == 3
        assert len(client.get(search, params={"q": '"page":2'}).json()["matches"]) == 2
        assert len(client.get(search, params={"q": '"worksheet":"résumé: data"'}).json()["matches"]) == 6
        assert client.get(search, params={"cursor": "!invalid"}).status_code == 422
        assert client.get(search, params={"limit": 0}).status_code == 422
        outsider = {"x-forwarded-user": "other"}
        for route in ("source-summaries", "evidence-search", "sources/src-a"):
            assert client.get(base + "/" + route, headers=outsider).status_code == 404
        assert client.get(base + "/sources/src-c").status_code == 404
        store.withdraw(case, "src-a", "analyst")
        assert not client.get(search, params={"q": "100%_needle"}).json()["matches"]
        assert client.get(base + "/sources/src-a").json()["withdrawn"] is True
