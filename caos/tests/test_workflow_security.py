"""Every workflow is read-only, digest-pinned and free of untrusted event text
in shell (ENTERPRISE_TESTING_READINESS SEC-003, SEC-004, SEC-005; Phase 6
items 4 and 6). A rule here is a tripwire on the mechanism: the review in
`caos/scripts/recorded_review.py` catches the same shapes on a diff, this
catches them on the tree."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
SHA_PIN = re.compile(r"@[0-9a-f]{40}$")
# Registry images a workflow may pull; a locally built `caos-*:ci` tag is not one.
REGISTRY_IMAGE = re.compile(r"(?<![\w/@.-])((?:ghcr\.io|quay\.io|docker\.io)/[\w./-]+:[\w.-]+|postgres:[\w.-]+|clamav/[\w./-]+:[\w.-]+)(@sha256:[0-9a-f]{64})?")
# Recorded exceptions to "installers pinned by digest": apt (archive-signed,
# CLAUDE.md records the trade-off) and the Playwright browser builds, which are
# pinned by the package-lock's playwright version and build number but are not
# digest-verified by the installer. Both are listed in the Task 12b report.
ACCEPTED_UNPINNED = ("apt-get install", "npx playwright install")


def _runs(workflow: dict) -> list[tuple[str, dict, str]]:
    return [(job_name, step, step.get("run", "") or "")
            for job_name, job in workflow["jobs"].items() for step in job.get("steps", [])]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_token_is_read_only(path):
    workflow = yaml.safe_load(path.read_text())
    assert workflow.get("permissions") == {"contents": "read"}, f"{path.name} must declare contents: read only"
    for name, job in workflow["jobs"].items():
        assert job.get("permissions", {"contents": "read"}) == {"contents": "read"}, f"{path.name}:{name} widens the token"
    assert "write" not in re.findall(r":\s*(write)\b", path.read_text()), f"{path.name} grants a write scope"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit(path):
    workflow = yaml.safe_load(path.read_text())
    for name, step, _ in _runs(workflow):
        uses = step.get("uses")
        if not uses or uses.startswith("./"):
            continue
        assert SHA_PIN.search(uses), f"{path.name}:{name} uses {uses!r} without a 40-hex pin"
        assert not uses.startswith(("anthropics/claude-code", "openai/")), f"{path.name}:{name} hands the token to an AI agent"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_pulled_image_and_installer_is_pinned_by_digest(path):
    text = path.read_text()
    workflow = yaml.safe_load(text)
    for match in REGISTRY_IMAGE.finditer(text):
        assert match.group(2), f"{path.name} pulls {match.group(1)} without an @sha256 digest"
    for name, step, run in _runs(workflow):
        for line in run.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "pip install" in stripped:
                assert "--require-hashes" in stripped, f"{path.name}:{name} installs Python packages without hashes: {stripped}"
            if re.search(r"\b(curl|wget)\b", stripped) and "127.0.0.1" not in stripped and "localhost" not in stripped:
                assert "sha256sum -c" in run, f"{path.name}:{name} downloads without a sha256 check: {stripped}"
            assert not re.search(r"\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(ba|z|da)?sh\b", stripped), f"{path.name}:{name} pipes a download into a shell"
            for installer in ("apt-get install", "npx playwright install"):
                if installer in stripped:
                    assert installer in ACCEPTED_UNPINNED


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_no_untrusted_event_text_reaches_a_shell_or_an_agent(path):
    text = path.read_text()
    workflow = yaml.safe_load(text)
    triggers = workflow.get(True) or workflow.get("on")  # PyYAML reads the bare key `on` as True
    assert "pull_request_target" not in triggers, f"{path.name} runs fork code with the base token"
    for name, step, run in _runs(workflow):
        # Commit identities are the only event fields a run block may carry, and
        # only through env; free text (titles, bodies, branch names) never.
        assert "${{ github.event." not in run, f"{path.name}:{name} interpolates event data into a run block"
        for key, value in (step.get("env") or {}).items():
            if "github.event." in str(value):
                assert re.fullmatch(r"\$\{\{\s*github\.event\.pull_request\.(base|head)\.sha\s*\}\}", str(value).strip()), \
                    f"{path.name}:{name} binds event text {key}={value!r}"
        assert "github.event.pull_request.title" not in str(step) and "github.event.pull_request.body" not in str(step)


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_secrets_are_reachable_only_from_dispatch_only_protected_jobs(path):
    text = path.read_text()
    if "secrets." not in text:
        return
    workflow = yaml.safe_load(text)
    triggers = workflow.get(True) or workflow.get("on")  # PyYAML reads the bare key `on` as True
    assert set(triggers) == {"workflow_dispatch"}, f"{path.name} references secrets on a non-dispatch trigger"
    for name, job in workflow["jobs"].items():
        if "secrets." in str(job):
            assert job.get("environment"), f"{path.name}:{name} reads a secret outside a protected environment"


def test_the_ai_review_action_is_gone_and_the_recorded_review_is_the_pr_check():
    review = (REPO / ".github" / "workflows" / "security-review.yml").read_text()
    assert "anthropics/claude-code-security-review" not in review
    assert "recorded_review.py" in review
    assert "secrets." not in review
    scripts = REPO / "caos" / "scripts"
    assert (scripts / "recorded_review.py").is_file() and (scripts / "scan_floors.py").is_file()


def test_the_security_job_installs_its_scanners_from_the_hashed_lock():
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "requirements-security.txt" in ci
    lock = (REPO / "caos" / "server" / "requirements-security.txt").read_text()
    for tool in ("pip-audit==", "bandit=="):
        assert tool in lock
    assert lock.count("--hash=sha256:") >= 40, "the scanner lock must be transitively hashed"
