"""Case audit package and offline verifier (Task 10; ENTERPRISE_READINESS_PLAN
Phase 4 items 16–18; ETR AUD-016–AUD-019, PUB-030).

The package is built from the store alone, holds no secret, prompt, provider
body or source text, and is verified in a clean directory by a stdlib-only
script that reconstructs the Markdown export byte for byte and recomputes
every digest, link and cross-reference it carries.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from test_deliverables_spec import ANALYST_H, APPROVER_H, add_approver, draft_request, file_request, freeze_now, http_seed

SERVER = Path(__file__).resolve().parents[2] / "server"
VERIFIER = SERVER / "caos" / "audit" / "verify_package.py"


def _filed_case(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = freeze_now(svc, case["id"], revision)
    add_approver(store, case)
    filed = client.post(f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve",
                        json=file_request(frozen).model_dump(mode="json"), headers=APPROVER_H)
    assert filed.status_code == 200, filed.text
    client.get(f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/export/md", headers=ANALYST_H)
    return svc, case, source, frozen


def _download(client, case_id, headers=ANALYST_H):
    response = client.get(f"/api/cases/{case_id}/audit-package", headers=headers)
    return response


def _run_verifier(tmp_path: Path, package: bytes, *args: str) -> tuple[int, dict]:
    """A clean directory, isolated interpreter (-I), no PYTHONPATH, only the
    verifier file and the zip: the application is not importable here."""
    clean = tmp_path / "review-machine"
    clean.mkdir()
    (clean / "verify_package.py").write_bytes(VERIFIER.read_bytes())
    (clean / "package.zip").write_bytes(package)
    completed = subprocess.run(
        [sys.executable, "-I", "verify_package.py", "package.zip", "--json", *args],
        cwd=clean, capture_output=True, text=True,
        env={key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "VIRTUAL_ENV"}},
    )
    report = json.loads(completed.stdout) if completed.stdout.strip() else {}
    return completed.returncode, report


def _retamper(package: bytes, mutate) -> bytes:
    """Rewrite one member of the zip through `mutate(name, bytes) -> bytes`."""
    source = zipfile.ZipFile(io.BytesIO(package))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            target.writestr(name, mutate(name, source.read(name)))
    return output.getvalue()


@pytest.mark.parametrize("manifest", [[], {"schema_version": "unknown", "case_id": "missing-case", "objects": {},
                                         "package_digest": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"}])
def test_verifier_refuses_structurally_empty_archives(tmp_path, manifest):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
    code, report = _run_verifier(tmp_path, output.getvalue())
    assert code != 0 and report.get("ok") is False, report


@pytest.mark.parametrize("remove_section", [True, False])
def test_verifier_requires_frozen_authority_even_if_object_digests_are_rewritten(
    client, settings, store, tmp_path, remove_section,
):
    from caos.audit.verify_package import digest
    import hashlib

    _, case, _, _ = _filed_case(client, settings, store)
    with zipfile.ZipFile(io.BytesIO(_download(client, case["id"]).content)) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(contents.pop("manifest.json"))
    if remove_section:
        del contents["deliverables/frozen.json"]
    else:
        contents["deliverables/frozen.json"] = b"[]"
    manifest["objects"] = {name: {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body)}
                           for name, body in contents.items()}
    manifest["package_digest"] = digest(manifest["objects"])
    contents["manifest.json"] = json.dumps(manifest).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, body in contents.items():
            archive.writestr(name, body)
    code, report = _run_verifier(tmp_path, output.getvalue())
    assert code == 1 and report["ok"] is False, report
    assert "FROZEN_RECORD_MISSING" in {item["code"] for item in report["findings"]}


def test_package_uses_one_snapshot_while_case_and_audit_change(client, settings, store, tmp_path, monkeypatch):
    from caos.audit import package
    from caos.storage.store import case_intakes

    _, case, _, _ = _filed_case(client, settings, store)
    with store.engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    original = package._rows
    changed = False

    def read_then_change(connection, table, *clauses, **kwargs):
        nonlocal changed
        rows = original(connection, table, *clauses, **kwargs)
        if table is case_intakes and not changed:
            changed = True
            store.audit_event("test.concurrent_change", "analyst", case_id=case["id"])
        return rows

    monkeypatch.setattr(package, "_rows", read_then_change)
    response = _download(client, case["id"])
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert b"test.concurrent_change" not in archive.read("audit/events.jsonl")
    assert changed
    code, report = _run_verifier(tmp_path, response.content)
    assert code == 0 and report["ok"], report


def test_package_is_case_authorized_audited_and_offline_verifiable_in_a_clean_directory(client, settings, store, tmp_path):
    svc, case, source, frozen = _filed_case(client, settings, store)
    assert _download(client, case["id"], {"x-caos-role": "ADMIN", "x-forwarded-user": "outsider"}).status_code == 404
    response = _download(client, case["id"])
    assert response.status_code == 200 and response.headers["content-type"].startswith("application/zip")
    package = response.content
    import hashlib

    assert response.headers["x-caos-sha256"] == hashlib.sha256(package).hexdigest()
    exported = [e for e in svc.audit_events_for_tests(case["id"]) if e["action"] == "audit.package_exported"]
    assert len(exported) == 1 and exported[0]["sha256"] == response.headers["x-caos-sha256"]

    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert {"case/case.json", "case/sources.json", "case/source_sets.json", "case/intakes.json", "runs/index.json",
                "models/builds.json", "models/revisions.json", "deliverables/revisions.json", "deliverables/opinions.json",
                "deliverables/frozen.json", "deliverables/receipts.json", "deliverables/exports.json",
                f"deliverables/exports/{frozen['deliverable_id']}.md", f"deliverables/exports/{frozen['deliverable_id']}.pdf",
                f"deliverables/exports/{frozen['deliverable_id']}.xlsx", "audit/events.jsonl", "audit/head.json",
                "methodology.json", "environment.json", "README.txt"} <= names
        assert set(manifest["objects"]) == names - {"manifest.json"}
        receipts = json.loads(archive.read("deliverables/receipts.json"))
        assert receipts[0]["approved_by"] == "approver-user" and receipts[0]["signed_by"] == "analyst"
        filed_bytes = archive.read(f"deliverables/exports/{frozen['deliverable_id']}.md")
    assert filed_bytes == svc.export(frozen["deliverable_id"], "md")[0], "the package carries the exact filed bytes"

    code, report = _run_verifier(tmp_path, package)
    assert code == 0, report
    assert report["ok"] is True and report["findings"] == []
    assert report["checked"]["frozen_deliverables"] == 1 and report["checked"]["markdown_reconstructed"] == 1
    assert report["checked"]["receipts"] == 1 and report["checked"]["audit_events"] >= 6


@pytest.mark.parametrize("tamper", ["export_bytes", "audit_reorder", "audit_mutate", "receipt_approver", "frozen_payload", "manifest_gap"])
def test_offline_verifier_convicts_every_tamper_class(client, settings, store, tmp_path, tamper):
    svc, case, source, frozen = _filed_case(client, settings, store)
    package = _download(client, case["id"]).content
    export_path = f"deliverables/exports/{frozen['deliverable_id']}.md"

    def mutate(name, content):
        if tamper == "export_bytes" and name == export_path:
            return content.replace(b"Leverage is manageable.", b"Leverage is not manageable.")
        if tamper == "audit_reorder" and name == "audit/events.jsonl":
            rows = content.decode().splitlines()
            rows[1], rows[2] = rows[2], rows[1]
            return ("\n".join(rows) + "\n").encode()
        if tamper == "audit_mutate" and name == "audit/events.jsonl":
            return content.replace(b'"actor":"approver-user"', b'"actor":"someone-else"')
        if tamper == "receipt_approver" and name == "deliverables/receipts.json":
            return content.replace(b'"approved_by":"approver-user"', b'"approved_by":"analyst"')
        if tamper == "frozen_payload" and name == "deliverables/frozen.json":
            return content.replace(b"Leverage is manageable.", b"Leverage is comfortable.")
        return content

    tampered = _retamper(package, mutate)
    if tamper == "manifest_gap":
        with zipfile.ZipFile(io.BytesIO(package)) as source_zip:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as target:
                for name in source_zip.namelist():
                    if name != "deliverables/receipts.json":
                        target.writestr(name, source_zip.read(name))
        tampered = output.getvalue()
    code, report = _run_verifier(tmp_path, tampered)
    assert code == 1, report
    codes = {item["code"] for item in report["findings"]}
    expected = {
        "export_bytes": {"OBJECT_DIGEST_MISMATCH", "EXPORT_DIGEST_MISMATCH", "MARKDOWN_RECONSTRUCTION_MISMATCH"},
        "audit_reorder": {"AUDIT_CHAIN_SEQUENCE_BROKEN", "AUDIT_CHAIN_LINK_BROKEN"},
        "audit_mutate": {"AUDIT_EVENT_DIGEST_MISMATCH"},
        "receipt_approver": {"RECEIPT_DIGEST_MISMATCH", "RECEIPT_FIELD_MISMATCH", "APPROVER_NOT_INDEPENDENT"},
        "frozen_payload": {"FROZEN_CONTENT_DIGEST_MISMATCH", "FROZEN_DRAFT_DIGEST_MISMATCH"},
        "manifest_gap": {"OBJECT_MISSING", "RECEIPT_MISSING"},
    }[tamper]
    assert expected <= codes, (tamper, codes)


def test_package_holds_no_source_text_vault_path_secret_or_provider_body(client, settings, store, tmp_path):
    body = b"CONFIDENTIAL-SOURCE-LINE the covenant text that must never leave the vault"
    from test_deliverables_spec import ingest_second_source

    svc, case, source, frozen = _filed_case(client, settings, store)
    ingest_second_source(store, case["id"], body)
    package = _download(client, case["id"]).content
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        everything = b"".join(archive.read(name) for name in archive.namelist())
        sources = json.loads(archive.read("case/sources.json"))
    assert b"CONFIDENTIAL-SOURCE-LINE" not in everything, "source block text never enters the package"
    assert b"pinned evidence line" not in everything
    assert b"vault_path" not in everything and b"vault/" not in everything.replace(b"deliverables/exports", b"")
    for row in sources:
        for block in row["blocks"]:
            assert "text" not in block and len(block["text_sha256"]) == 64
    for secret in (settings.session_secret, settings.edge_proxy_secret):
        if secret:
            assert secret.encode() not in everything
    lowered = everything.lower()
    assert b"api_key" not in lowered and b"authorization" not in lowered
    assert b'"prompt"' not in lowered and b'"system_prompt"' not in lowered and b'"messages"' not in lowered, "no prompt or provider message body"


def test_verifier_renderer_copy_is_byte_identical_to_the_application_renderer():
    begin = "# --- BEGIN SHARED RENDERER (copied verbatim into audit/verify_package.py) ---\n"
    end = "# --- END SHARED RENDERER ---\n"
    application = (SERVER / "caos" / "publishing" / "markdown.py").read_text()
    verifier = VERIFIER.read_text()
    shared = application[application.index(begin) + len(begin): application.index(end)]
    copied = verifier[verifier.index(begin) + len(begin): verifier.index(end)]
    assert shared == copied, "the offline verifier's Markdown renderer drifted from caos/publishing/markdown.py"
    assert "import caos" not in verifier and "from caos" not in verifier and "from .." not in verifier, "the verifier imports no application code"


def test_verifier_reports_an_unreadable_package_without_a_traceback(tmp_path):
    code, report = _run_verifier(tmp_path, b"not a zip")
    assert code == 2 and report["findings"][0]["code"] == "PACKAGE_UNREADABLE"
