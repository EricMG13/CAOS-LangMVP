"""Settings fail-closed parsing and vault file primitives."""

from __future__ import annotations

import hashlib

import pytest

from caos.atomic_files import (
    VaultFileIntegrityError,
    publish_hash_addressed_bytes,
    read_verified_vault_bytes,
)
from caos.config import Settings, _strict_bool


@pytest.mark.parametrize("raw", ["1", "TRUE", "yes", "False", "on"])
def test_agent_flag_rejects_noncanonical_boolean(monkeypatch, raw):
    monkeypatch.setenv("AGENT_EXECUTION_ENABLED", raw)
    with pytest.raises(ValueError):
        _strict_bool("AGENT_EXECUTION_ENABLED", False)


def test_agent_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("AGENT_EXECUTION_ENABLED", raising=False)
    assert Settings.from_env().agent_execution_enabled is False


def test_production_fails_closed_without_postgres_and_secrets():
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        Settings(environment="production").validate_runtime()
    with pytest.raises(RuntimeError, match="EDGE_PROXY_SECRET"):
        Settings(environment="production", database_url="postgresql://x/y").validate_runtime()


def test_vault_publish_and_verified_read_round_trip(tmp_path):
    content = b"immutable artifact bytes"
    sha = hashlib.sha256(content).hexdigest()
    _, key, size = publish_hash_addressed_bytes(
        tmp_path, ("models", "ab"), "xlsx", content, expected_sha256=sha, max_bytes=1024,
    )
    assert read_verified_vault_bytes(tmp_path, key, expected_sha256=sha, expected_size=size, max_bytes=1024) == content


def test_vault_read_fails_closed_on_tamper(tmp_path):
    content = b"immutable artifact bytes"
    sha = hashlib.sha256(content).hexdigest()
    target, key, size = publish_hash_addressed_bytes(
        tmp_path, ("models", "ab"), "xlsx", content, expected_sha256=sha, max_bytes=1024,
    )
    target.write_bytes(b"tampered artifact bytes!")
    with pytest.raises(VaultFileIntegrityError):
        read_verified_vault_bytes(tmp_path, key, expected_sha256=sha, expected_size=size, max_bytes=1024)


def test_vault_publish_rejects_digest_mismatch(tmp_path):
    with pytest.raises(ValueError, match="digest mismatch"):
        publish_hash_addressed_bytes(
            tmp_path, ("models",), "xlsx", b"content", expected_sha256="0" * 64, max_bytes=1024,
        )
