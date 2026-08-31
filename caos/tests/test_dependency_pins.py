"""The lock files are generated from pyproject.toml — this proves they still are.

`caos/server/requirements*.txt` are compiled by
`uv pip compile pyproject.toml [--extra dev] --universal --python-version 3.12
--generate-hashes`. Adding a dependency to pyproject without recompiling would
leave the Docker image and CI installing the old set, and `--require-hashes`
turns any unhashed line into a deploy-time build failure rather than a test one.
Both are cheap to assert here.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

SERVER = Path(__file__).resolve().parents[1] / "server"
PIN = re.compile(r"^([A-Za-z0-9._-]+)==([^\s;\\]+)")


def _locked(name: str) -> dict[str, str]:
    lines = (SERVER / name).read_text().splitlines()
    return {canonicalize_name(m[1]): m[2] for line in lines if (m := PIN.match(line))}


def _declared() -> dict[str, list[str]]:
    project = tomllib.loads((SERVER / "pyproject.toml").read_text())["project"]
    runtime = project["dependencies"]
    return {
        "requirements.txt": runtime,
        "requirements-dev.txt": runtime + project["optional-dependencies"]["dev"],
    }


@pytest.mark.parametrize(("lock_name", "declared"), _declared().items())
def test_lock_covers_pyproject(lock_name: str, declared: list[str]) -> None:
    locked = _locked(lock_name)
    for spec in declared:
        req = Requirement(spec)
        version = locked.get(canonicalize_name(req.name))
        assert version is not None, f"{req.name} declared in pyproject is absent from {lock_name}"
        assert req.specifier.contains(version), (
            f"{lock_name} pins {req.name}=={version}, which pyproject's '{spec}' rejects"
        )


@pytest.mark.parametrize("lock_name", ["requirements.txt", "requirements-dev.txt"])
def test_every_pin_carries_a_hash(lock_name: str) -> None:
    """--require-hashes refuses the whole install if one line lacks a hash."""
    text = (SERVER / lock_name).read_text()
    blocks = re.split(r"\n(?=[A-Za-z0-9._-]+==)", text)
    missing = [
        m[1] for block in blocks if (m := PIN.match(block)) and "--hash=sha256:" not in block
    ]
    assert not missing, f"{lock_name} pins without a hash: {missing}"
