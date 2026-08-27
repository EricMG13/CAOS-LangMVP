from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(storage_dir=tmp_path / "vault")


@pytest.fixture()
def store(tmp_path: Path) -> DomainStore:
    return DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
