#!/usr/bin/env python3
"""Regenerate the shipped Deploy V bundle's integrity identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


BUNDLE = Path("caos/server/caos/methodology/vendor/deploy_v")
MANIFEST = "DEPLOY_V_MANIFEST.json"
BASELINE = "DEPLOY_V_BASELINE.json"
INTEGRITY = "DEPLOY_V_INTEGRITY_v1.json"
RETRIEVAL = "CP_DEPLOY_V_RETRIEVAL_INDEX_v1.json"
PROMPTS = ("DEPLOY_V_COPILOT_MEMORY_PROMPT.md", "DEPLOY_V_COPILOT_MEMORY_PROMPT_URL_BOUND.md")
ROOT_ENTRIES = {
    "CANON_SHARED.md",
    "CP_DEPLOY_V_CHILD_SCHEMA_REGISTRY_v1.json",
    "CP_DEPLOY_V_EXECUTION_PROFILES_v1.json",
    "CP_DEPLOY_V_LITE_MODULE_PAYLOAD_BASE_v1.schema.txt",
    RETRIEVAL,
    "CP_MODULE_PAYLOAD_BASE.schema.txt",
    BASELINE,
    "DEPLOY_V_COPILOT_MEMORY_PROMPT.md",
    "DEPLOY_V_COPILOT_MEMORY_PROMPT_URL_BOUND.md",
    INTEGRITY,
    MANIFEST,
    "README.md",
    "skills",
}


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json_without(value: dict[str, Any], omitted_key: str) -> str:
    canonical = {key: item for key, item in value.items() if key != omitted_key}
    return digest_bytes(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode())


def file_inventory(folder: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not valid bundle input: {path}")
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        data = path.read_bytes()
        inventory[path.relative_to(folder).as_posix()] = {
            "bytes": len(data),
            "sha256": digest_bytes(data),
        }
    return inventory


def load_json(name: str) -> dict[str, Any]:
    return json.loads((BUNDLE / name).read_text(encoding="utf-8"))


def validate_bundle_tree() -> None:
    if BUNDLE.is_symlink():
        raise ValueError(f"symlink is not valid bundle input: {BUNDLE}")
    entries = list(BUNDLE.iterdir())
    if {path.name for path in entries} != ROOT_ENTRIES:
        raise ValueError("bundle root entries do not match the managed tree")
    for path in BUNDLE.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink is not valid bundle input: {path}")
    if any(not path.is_file() for path in entries if path.name != "skills"):
        raise ValueError("bundle root contains a non-file entry")
    skills_root = BUNDLE / "skills"
    if not skills_root.is_dir() or any(not path.is_dir() for path in skills_root.iterdir()):
        raise ValueError("skills must contain only declared skill directories")


def generated_files() -> dict[Path, bytes]:
    validate_bundle_tree()
    manifest = load_json(MANIFEST)
    baseline = load_json(BASELINE)
    integrity = load_json(INTEGRITY)
    retrieval = load_json(RETRIEVAL)
    skills_root = BUNDLE / "skills"
    skill_entries = list(skills_root.iterdir())

    manifest_slugs = [skill["folder_slug"] for skill in manifest["skills"]]
    integrity_slugs = [skill["folder_slug"] for skill in integrity["skills"]]
    declared_slugs = set(manifest_slugs)
    actual_slugs = {path.name for path in skill_entries if path.is_dir()}
    if (
        len(declared_slugs) != len(manifest_slugs)
        or len(set(integrity_slugs)) != len(integrity_slugs)
        or set(integrity_slugs) != declared_slugs
        or actual_slugs != declared_slugs
    ):
        raise ValueError("skill directories, manifest, and integrity membership must match")

    inventories = {}
    integrity_by_slug = {skill["folder_slug"]: skill for skill in integrity["skills"]}
    for skill in manifest["skills"]:
        slug = skill["folder_slug"]
        files = file_inventory(skills_root / slug)
        inventories[slug] = files
        inventory_fields = dict(
            companion_count=len(files) - 1,
            entry_bytes=files["SKILL.md"]["bytes"],
            entry_sha256=files["SKILL.md"]["sha256"],
            relative_file_hashes=files,
        )
        skill.update(inventory_fields)
        integrity_by_slug[slug].update(inventory_fields)
    manifest_data = json_bytes(manifest)

    baseline["packages"] = {
        slug: {"files": files} for slug, files in inventories.items()
    }
    baseline["baseline_digest"] = digest_json_without(baseline, "baseline_digest")
    baseline_data = json_bytes(baseline)

    integrity["source_hashes"] = {
        "deployed_baseline": digest_bytes(baseline_data),
        "deployed_child_schema_registry": digest_bytes(
            (BUNDLE / "CP_DEPLOY_V_CHILD_SCHEMA_REGISTRY_v1.json").read_bytes()
        ),
        "deployed_manifest": digest_bytes(manifest_data),
    }
    integrity["build_id"] = digest_json_without(integrity, "build_id")
    integrity_data = json_bytes(integrity)

    retrieval["build_id"] = integrity["build_id"]
    generated = {
        BUNDLE / MANIFEST: manifest_data,
        BUNDLE / BASELINE: baseline_data,
        BUNDLE / INTEGRITY: integrity_data,
        BUNDLE / RETRIEVAL: json_bytes(retrieval),
    }
    for name in PROMPTS:
        path = BUNDLE / name
        text, replacements = re.subn(
            r"(INDEX_BUILD_ID:\s*)[0-9a-f]{64}",
            rf"\g<1>{integrity['build_id']}",
            path.read_text(encoding="utf-8"),
        )
        if replacements != 1:
            raise ValueError(f"expected one INDEX_BUILD_ID in {path}")
        generated[path] = text.encode()
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    if not BUNDLE.is_dir():
        parser.error("run from the repository root")

    generated = generated_files()
    stale = [path for path, data in generated.items() if path.read_bytes() != data]
    if check:
        if stale:
            print("stale Deploy V integrity files:", *(f"\n- {path}" for path in stale), sep="")
            return 1
        print("Deploy V integrity is current")
        return 0
    for path in stale:
        path.write_bytes(generated[path])
    print("Deploy V integrity regenerated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
