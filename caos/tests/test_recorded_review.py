"""The recorded diff review is non-vacuous and cannot be talked out of a
finding (ETR-B06, SEC-004, SEC-005): planted diffs must be reported, an
unparseable diff must exit 2 rather than 0, and the workflow that runs it must
hold no secret and no write token."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "caos" / "scripts" / "recorded_review.py"
WORKFLOW = REPO / ".github" / "workflows" / "security-review.yml"
sys.path.insert(0, str(SCRIPT.parent))

import recorded_review  # noqa: E402


def _diff(path: str, *added: str, old: str = "") -> str:
    body = "".join(f"+{line}\n" for line in added)
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,0 +1,{len(added)} @@\n{body}")


def test_planted_block_findings_are_reported_and_fail_the_review(tmp_path):
    diff = (
        _diff(".github/workflows/ci.yml", "      - uses: actions/checkout@v4")
        + _diff(".github/workflows/nightly.yml", "on: [pull_request_target]", "  pull-requests: write",
                "        run: echo ${{ github.event.pull_request.title }}")
        + _diff("caos/server/caos/api/__init__.py", '    role = request.headers.get("x-caos-role")')
        + _diff("caos/scripts/install.sh", "curl -sSf https://example.invalid/install.sh | sh")
        + _diff("caos/server/caos/methodology/vendor/x/SKILL.md", "changed")
        + _diff("caos/frontend/src/components/Workspace.tsx", "<div dangerouslySetInnerHTML={{ __html: text }} />")
        + _diff("caos/server/caos/config.py", 'KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"')
    )
    payload, code = recorded_review.record(diff, base="b", head="h")
    rules = {(f["rule"], f["path"]) for f in payload["findings"]}
    assert code == 1 and payload["verdict"] == "BLOCKED"
    assert payload["files_examined"] == 7 and payload["added_lines_examined"] == 9
    for expected in (
        ("workflow-unpinned-action", ".github/workflows/ci.yml"),
        ("workflow-pull-request-target", ".github/workflows/nightly.yml"),
        ("workflow-write-permission", ".github/workflows/nightly.yml"),
        ("workflow-event-in-run", ".github/workflows/nightly.yml"),
        ("client-role-trusted", "caos/server/caos/api/__init__.py"),
        ("curl-pipe-shell", "caos/scripts/install.sh"),
        ("vendored-bundle-edit", "caos/server/caos/methodology/vendor/x/SKILL.md"),
        ("inner-html", "caos/frontend/src/components/Workspace.tsx"),
        ("credential-literal", "caos/server/caos/config.py"),
    ):
        assert expected in rules, expected
    secret = next(f for f in payload["findings"] if f["rule"] == "credential-literal")
    assert "sk-ant-api03" not in secret["excerpt"] and "[REDACTED]" in secret["excerpt"]
    assert "sk-ant-api03" not in json.dumps(payload)


def test_prose_ledgers_comments_and_the_rule_table_itself_are_not_findings():
    """The rules read code: a ledger row or report that names `x-caos-role` or
    `curl | sh`, a YAML comment that names them, the rule table and this test
    (which must contain every pattern) never fire; the same text on a code
    line does."""
    diff = (
        _diff("docs/QUALITY_LEDGER.csv", 'F-AUTH-01,Dev-mode role header,"x-caos-role is ignored in production; curl | sh is refused"')
        + _diff(".superpowers/sdd/report.md", "the audit found x-caos-role trusted nowhere; AKIAABCDEFGHIJKLMNOP is a fixture")
        + _diff(".github/workflows/ci.yml", "      # never curl | sh an installer; never read x-caos-role here")
        + _diff("caos/scripts/recorded_review.py", '    re.compile(r"x-caos-role"),')
        + _diff("caos/tests/test_recorded_review.py", '    _diff("x.py", "curl https://x | sh")')
    )
    payload, code = recorded_review.record(diff, base="b", head="h")
    assert code == 0 and [f["rule"] for f in payload["findings"]] == [], payload["findings"]
    assert payload["files_examined"] == 5
    live, code = recorded_review.record(_diff("caos/server/caos/api/__init__.py", '    request.headers.get("x-caos-role")  # dev only'), base="b", head="h")
    assert code == 1 and [f["rule"] for f in live["findings"]] == ["client-role-trusted"]


def test_a_pinned_action_and_the_sha_binding_are_not_findings():
    diff = _diff(".github/workflows/ci.yml",
                 "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
                 "      - uses: ./.github/actions/local",
                 "          BASE: ${{ github.event.pull_request.base.sha }}")
    payload, code = recorded_review.record(diff, base="b", head="h")
    assert code == 0 and payload["findings"] == [], payload["findings"]


def test_a_bundle_change_with_its_decision_is_review_not_block():
    diff = _diff("caos/server/caos/methodology/vendor/x/SKILL.md", "changed") + _diff("docs/DECISIONS.md", "23. entry")
    payload, code = recorded_review.record(diff, base="b", head="h")
    assert code == 0
    assert [f["severity"] for f in payload["findings"] if f["rule"] == "vendored-bundle-edit"] == ["REVIEW"]


def test_a_vacuous_review_exits_two_never_zero(tmp_path):
    payload, code = recorded_review.record("this is not a diff at all\n", base="b", head="h")
    assert code == 2 and payload["verdict"] == "VACUOUS" and payload["files_examined"] == 0
    out = tmp_path / "record.json"
    completed = subprocess.run([sys.executable, str(SCRIPT), "--diff", "-", "--out", str(out)],
                               input="garbage\n", text=True, capture_output=True, check=False)
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert json.loads(out.read_text())["verdict"] == "VACUOUS"


def test_an_empty_diff_is_recorded_as_empty():
    payload, code = recorded_review.record("", base="b", head="h")
    assert code == 0 and payload["files_examined"] == 0 and payload["verdict"] == "RECORDED"


def test_the_script_reviews_this_repository_head_without_a_block(tmp_path):
    """Non-vacuity on real input: the last commit's own diff parses to the
    files git reports, and the tree as committed carries no BLOCK finding."""
    diff = subprocess.run(["git", "diff", "HEAD~1", "HEAD", "--unified=0"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout
    names = subprocess.run(["git", "diff", "HEAD~1", "HEAD", "--name-only"], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    payload, code = recorded_review.record(diff, base="HEAD~1", head="HEAD")
    assert payload["files_examined"] == len(names), (payload["files_examined"], len(names))
    assert code != 2


def test_the_workflow_is_read_only_holds_no_secret_and_runs_the_script():
    text = WORKFLOW.read_text()
    workflow = yaml.safe_load(text)
    assert workflow["permissions"] == {"contents": "read"}
    assert "secrets." not in text and "anthropics/" not in text and "claude" not in text.lower().replace("claude-", "x")
    (job,) = workflow["jobs"].values()
    assert "permissions" not in job or job["permissions"] == {"contents": "read"}
    steps = job["steps"]
    for step in steps:
        uses = step.get("uses", "")
        assert not uses or re.search(r"@[0-9a-f]{40}$", uses.split(" #")[0]), uses
        run = step.get("run", "")
        assert "${{ github.event." not in run, "event text in a run block"
    assert any("caos/scripts/recorded_review.py" in step.get("run", "") for step in steps)
    upload = next(step for step in steps if "upload-artifact" in step.get("uses", ""))
    assert upload.get("if") == "always()", "the record is retained whether the review is red or green"
