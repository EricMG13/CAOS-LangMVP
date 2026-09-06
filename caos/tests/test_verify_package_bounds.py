"""The offline audit-package verifier bounds every member it reads (the
2026-09-06 adversarial review's X3): a member whose central-directory size
exceeds what the manifest declares is refused with a typed finding before a
byte of it is inflated, and every read is capped, so a crafted package cannot
inflate into the review machine's memory. Standard library only, as before."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from caos.audit import verify_package


def _package(members: dict[str, bytes], *, replace: dict[str, bytes] | None = None) -> bytes:
    """A minimal, internally consistent package; `replace` swaps member bytes
    after the manifest was computed, the way a crafted package would."""
    objects = {name: {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
               for name, content in sorted(members.items())}
    manifest = {"schema_version": "caos.audit-package.v1", "case_id": "case-verify", "audit_chain_head": None,
                "objects": objects, "package_digest": verify_package.digest(objects)}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, content in sorted(members.items()):
            archive.writestr(name, (replace or {}).get(name, content))
    return output.getvalue()


@pytest.fixture()
def opened(monkeypatch) -> list[str]:
    """Every member the verifier opens, by name. `ZipFile.read` goes through
    `ZipFile.open`, so wrapping both observes every way of reaching the bytes."""
    names: list[str] = []
    real_open, real_read = zipfile.ZipFile.open, zipfile.ZipFile.read

    def recording_open(self, name, *args, **kwargs):
        names.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
        return real_open(self, name, *args, **kwargs)

    def recording_read(self, name, *args, **kwargs):
        names.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
        return real_read(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", recording_open)
    monkeypatch.setattr(zipfile.ZipFile, "read", recording_read)
    return names


HONEST = {"README.txt": b"review notes\n", "case/case.json": b'{"id": "case-verify"}\n'}


def test_an_honest_package_still_verifies(tmp_path: Path, opened: list[str]):
    path = tmp_path / "honest.zip"
    path.write_bytes(_package(HONEST))
    report = verify_package.verify(str(path))
    assert report["ok"] is True and report["findings"] == [], report
    assert set(opened) >= {"manifest.json", "README.txt", "case/case.json"}


def test_a_member_that_inflates_past_its_declared_size_is_refused_before_it_is_read(tmp_path: Path, opened: list[str]):
    """The manifest says README.txt is 13 bytes; the zip's central directory
    says 8 MiB (a few kilobytes deflated). Before the fix `archive.read` inflated
    the whole member before the size comparison ran."""
    path = tmp_path / "crafted.zip"
    path.write_bytes(_package(HONEST, replace={"README.txt": b"\0" * (8 * 1024 * 1024)}))
    with zipfile.ZipFile(path) as archive:
        assert archive.getinfo("README.txt").file_size == 8 * 1024 * 1024
        assert archive.getinfo("README.txt").compress_size < 64 * 1024
    opened.clear()

    report = verify_package.verify(str(path))

    assert report["ok"] is False
    refused = [item for item in report["findings"] if item["code"] == "OBJECT_SIZE_EXCEEDED"]
    assert refused and refused[0]["path"] == "README.txt", report["findings"]
    assert refused[0]["declared"] == 8 * 1024 * 1024 and refused[0]["limit"] == len(HONEST["README.txt"])
    assert "README.txt" not in opened, "the oversized member was opened"
    assert "manifest.json" in opened and "case/case.json" in opened, "the honest members were still verified"
    assert not any(item["code"] == "OBJECT_DIGEST_MISMATCH" and item["path"] == "README.txt" for item in report["findings"])


def test_a_member_the_later_steps_need_is_refused_without_a_crash(tmp_path: Path, opened: list[str]):
    """Step 1 convicts the member; the audit-chain step then asks for it. The
    verifier reports rather than raising, and never inflates it."""
    members = {**HONEST, "audit/events.jsonl": b"", "audit/head.json": b"null\n"}
    path = tmp_path / "crafted-chain.zip"
    path.write_bytes(_package(members, replace={"audit/events.jsonl": b"\0" * (4 * 1024 * 1024)}))
    opened.clear()

    report = verify_package.verify(str(path))

    assert report["ok"] is False
    codes = [(item["code"], item.get("path")) for item in report["findings"]]
    assert ("OBJECT_SIZE_EXCEEDED", "audit/events.jsonl") in codes, codes
    assert "audit/events.jsonl" not in opened


def test_a_manifest_size_that_is_not_a_number_falls_back_to_the_hard_ceiling(tmp_path: Path, opened: list[str], monkeypatch):
    """A crafted manifest cannot widen the read by declaring a non-numeric size:
    the ceiling applies, and a member above it is refused unread."""
    monkeypatch.setattr(verify_package, "MAX_MEMBER_BYTES", 1024)
    package = _package(HONEST, replace={"README.txt": b"\0" * 4096})
    with zipfile.ZipFile(io.BytesIO(package)) as source:
        manifest = json.loads(source.read("manifest.json"))
        manifest["objects"]["README.txt"]["size"] = "13"
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            target.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
            for name in source.namelist():
                if name != "manifest.json":
                    target.writestr(name, source.read(name))
    path = tmp_path / "crafted-size.zip"
    path.write_bytes(output.getvalue())
    opened.clear()

    report = verify_package.verify(str(path))

    refused = [item for item in report["findings"] if item["code"] == "OBJECT_SIZE_EXCEEDED"]
    assert refused and refused[0]["path"] == "README.txt" and refused[0]["limit"] == 1024
    assert "README.txt" not in opened


def test_the_command_line_reports_the_refusal_as_findings(tmp_path: Path, capsys):
    path = tmp_path / "crafted.zip"
    path.write_bytes(_package(HONEST, replace={"README.txt": b"\0" * (2 * 1024 * 1024)}))
    assert verify_package.main([str(path), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert any(item["code"] == "OBJECT_SIZE_EXCEEDED" for item in report["findings"])
