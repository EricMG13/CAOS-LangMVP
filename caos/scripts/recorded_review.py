#!/usr/bin/env python3
"""Recorded, read-only review of a pull-request diff (ENTERPRISE_TESTING_READINESS
ETR-B06, SEC-004, SEC-005; Phase 6 item 4).

Replaces the AI pull-request review. The diff under review is attacker-
controlled text, so nothing here interprets it: the script holds no secret,
has no network, writes nothing but its own record, and is invoked by a
workflow whose token is `contents: read`. Every added line is matched against
a fixed rule table; the record lists what was examined and what matched, and
the job fails on a BLOCK rule. A diff with changes that yields zero examined
files is a vacuous review and exits 2, never 0 — a green check that looked at
nothing is the failure this replaces.

    python caos/scripts/recorded_review.py --diff pr.diff --out recorded-review.json \
        --base <sha> --head <sha>

Exit codes: 0 recorded (REVIEW findings at most), 1 a BLOCK rule matched,
2 the review was vacuous.

ponytail: stdlib regexes over `+` lines, no AST. Bandit, ruff, the route
audit and the contract tests own the deep checks; this is the recorded
supply-chain and authority tripwire that runs on every PR without a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "caos.recorded-review.v1"
WORKFLOW = re.compile(r"^\.github/workflows/.*\.ya?ml$")
VENDOR = "caos/server/caos/methodology/vendor/"
TEST_PATHS = ("caos/tests/", "caos/frontend/src/", "qa/", "caos/frontend/scripts/")

# (rule id, severity, path filter, added-line pattern, note). The path filter is
# a predicate over the repository path; None means every file.
RULES: list[tuple[str, str, object, re.Pattern[str], str]] = [
    ("workflow-pull-request-target", "BLOCK", WORKFLOW.match,
     re.compile(r"\bpull_request_target\b"),
     "pull_request_target runs fork code with the base repository's token"),
    ("workflow-unpinned-action", "BLOCK", WORKFLOW.match,
     re.compile(r"^\s*-?\s*uses:\s*(?!\./)[^@\s]+(?:@(?![0-9a-f]{40}\b)\S*)?\s*(?:#.*)?$"),
     "every third-party action is pinned to a 40-hex commit (SEC-003)"),
    ("workflow-write-permission", "BLOCK", WORKFLOW.match,
     re.compile(r"^\s*(contents|pull-requests|issues|packages|id-token|actions|deployments|statuses|checks):\s*write\b"),
     "workflows are read-only; a write token beside untrusted input is the risk ETR-B06 names"),
    ("workflow-event-in-run", "BLOCK", WORKFLOW.match,
     re.compile(r"\$\{\{\s*github\.event\.(?!pull_request\.(?:base|head)\.sha\b)[^}]*\}\}"),
     "event payload text interpolated into a workflow is script injection (SEC-004); bind it through env"),
    ("workflow-ai-agent", "BLOCK", WORKFLOW.match,
     re.compile(r"uses:\s*anthropics/claude-code|claude-code-action|openai/|codex-action"),
     "no AI agent receives the diff, a secret or a write token (SEC-005)"),
    ("workflow-secret", "REVIEW", WORKFLOW.match,
     re.compile(r"\$\{\{\s*secrets\."),
     "a secret reference: confirm the job is dispatch-only on a protected environment"),
    ("curl-pipe-shell", "BLOCK", None,
     re.compile(r"\b(curl|wget)\b[^|\n]*\|\s*(sudo\s+)?(ba|z|da)?sh\b"),
     "an installer fetched and executed unverified"),
    ("private-key", "BLOCK", None,
     re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "a private key in the tree"),
    ("credential-literal", "BLOCK", None,
     re.compile(r"\b(AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
     "a credential-shaped literal"),
    ("vendored-bundle-edit", "BLOCK", lambda p: p.startswith(VENDOR),
     re.compile(r".*"),
     "the vendored methodology bundle changed: DECISIONS.md §14 entry and regenerated manifests required in the same change"),
    ("client-role-trusted", "BLOCK",
     lambda p: not p.startswith(TEST_PATHS) and p != "caos/server/caos/identity.py" and p != "run_sec_audit.py",
     re.compile(r"x-caos-role"),
     "the development role header must never be read outside identity.py"),
    ("public-path-change", "REVIEW", lambda p: p == "caos/server/caos/identity.py",
     re.compile(r"PUBLIC_PATHS|_role_from_groups|compare_digest"),
     "the identity edge changed: re-run run_sec_audit.py and review the oauth2-proxy skip list"),
    ("new-route", "REVIEW", lambda p: p == "caos/server/caos/api/__init__.py",
     re.compile(r"@app\.(get|post|put|patch|delete)\("),
     "a new or moved route: membership, role, strict request and response, ledger row, audit, ceiling (IAM-020)"),
    ("open-wire-model", "REVIEW", lambda p: p.startswith("caos/server/"),
     re.compile(r'extra\s*=\s*"allow"'),
     "an open wire model: only the six service-owned envelopes may be open (CLAUDE.md)"),
    ("shell-true", "REVIEW", lambda p: p.endswith(".py"),
     re.compile(r"shell\s*=\s*True"),
     "a shell-interpreted subprocess"),
    ("dynamic-code", "REVIEW", lambda p: p.endswith(".py"),
     re.compile(r"\b(eval|exec)\(|pickle\.loads?\(|yaml\.load\((?![^)]*SafeLoader)|marshal\.loads?\("),
     "dynamic code or unsafe deserialisation"),
    ("tls-verify-off", "REVIEW", None,
     re.compile(r"verify\s*=\s*False|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*0|--insecure\b"),
     "TLS verification disabled"),
    ("inner-html", "BLOCK", lambda p: p.startswith("caos/frontend/") and ".test." not in p and "/scripts/" not in p,
     re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*=|document\.write\("),
     "raw HTML injection in the frontend (SEC-008, WEB-012)"),
    ("deploy-change", "REVIEW",
     lambda p: p.startswith("caos/deploy/") or p == "caos/.env.example",
     re.compile(r".*"),
     "the deployment topology or edge changed: re-run the deploy checks and the audit"),
    ("dependency-lock", "REVIEW",
     lambda p: p in {"caos/server/requirements.txt", "caos/server/requirements-dev.txt",
                     "caos/server/requirements-security.txt", "caos/frontend/package-lock.json",
                     "caos/server/pyproject.toml", "caos/frontend/package.json"},
     re.compile(r".*"),
     "a dependency lock changed: pip-audit, npm audit and the hashed-install gates must stay green"),
]
REDACT = re.compile(r"(AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----.*)")
# Line rules read code. Prose and ledgers describe the patterns without executing
# them, the rule table and its test necessarily contain them, and a comment line
# cannot run anything — so none of those are matched (the path rules still apply).
PROSE_SUFFIXES = (".md", ".csv", ".txt", ".rst")
SELF = {"caos/scripts/recorded_review.py", "caos/tests/test_recorded_review.py"}
COMMENT = re.compile(r"^\s*(#|//|/\*|\*)")


def parse_diff(text: str) -> dict[str, list[tuple[int, str]]]:
    """Path -> added (line number in the new file, text). Handles `git diff`
    output at any unified context, renames and new files; deletions are
    examined as files with no added lines."""
    files: dict[str, list[tuple[int, str]]] = {}
    path: str | None = None
    new_line = 0
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            match = re.match(r'diff --git "?a/(.*?)"? "?b/(.*?)"?$', raw)
            path = match.group(2) if match else raw.split(" b/", 1)[-1]
            files.setdefault(path, [])
            continue
        if path is None:
            continue
        if raw.startswith("+++ "):
            if raw != "+++ /dev/null":
                # git appends a TAB and a (usually empty) timestamp when the
                # path contains a space; without cutting there the same file is
                # registered twice, once with a trailing tab.
                path = raw[4:].split("\t", 1)[0].removeprefix("b/").strip('"')
                files.setdefault(path, [])
            continue
        if raw.startswith("--- ") or raw.startswith("index ") or raw.startswith("rename ") \
                or raw.startswith("similarity ") or raw.startswith("new file") or raw.startswith("deleted file") \
                or raw.startswith("Binary files") or raw.startswith("old mode") or raw.startswith("new mode"):
            continue
        hunk = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if raw.startswith("+"):
            files[path].append((new_line, raw[1:]))
            new_line += 1
        elif raw.startswith(" "):
            new_line += 1
    return files


def review(files: dict[str, list[tuple[int, str]]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path, added in files.items():
        for rule, severity, applies, pattern, note in RULES:
            if applies is not None and not applies(path):
                continue
            if pattern.pattern == ".*":
                if added or path.startswith(VENDOR):
                    findings.append({"rule": rule, "severity": severity, "path": path, "line": None,
                                     "excerpt": "", "note": note})
                continue
            if path.endswith(PROSE_SUFFIXES) or path in SELF:
                continue
            for line_number, text in added:
                if COMMENT.match(text):
                    continue
                if pattern.search(text):
                    findings.append({"rule": rule, "severity": severity, "path": path, "line": line_number,
                                     "excerpt": REDACT.sub("[REDACTED]", text.strip())[:160], "note": note})
    # The bundle rule is satisfied only when the same change carries its decision.
    if any(f["rule"] == "vendored-bundle-edit" for f in findings) and "docs/DECISIONS.md" in files:
        for finding in findings:
            if finding["rule"] == "vendored-bundle-edit":
                finding["severity"] = "REVIEW"
                finding["note"] = "the vendored bundle changed with a DECISIONS.md change in the same diff; confirm the manifests were regenerated"
    return findings


def record(diff_text: str, *, base: str, head: str) -> tuple[dict[str, object], int]:
    files = parse_diff(diff_text)
    findings = review(files)
    added = sum(len(lines) for lines in files.values())
    vacuous = bool(diff_text.strip()) and not files
    blocked = any(f["severity"] == "BLOCK" for f in findings)
    payload = {
        "schema_version": SCHEMA,
        "base": base,
        "head": head,
        "diff_sha256": hashlib.sha256(diff_text.encode("utf-8", "surrogateescape")).hexdigest(),
        "files_examined": len(files),
        "added_lines_examined": added,
        "rules": [rule for rule, *_ in RULES],
        "findings": findings,
        "verdict": "VACUOUS" if vacuous else "BLOCKED" if blocked else "RECORDED",
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return payload, 2 if vacuous else 1 if blocked else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--diff", required=True, help="unified diff file, or - for stdin")
    parser.add_argument("--out", required=True, help="where the JSON record is written")
    parser.add_argument("--base", default="", help="base commit")
    parser.add_argument("--head", default="", help="head commit")
    args = parser.parse_args(argv)
    diff_text = sys.stdin.read() if args.diff == "-" else Path(args.diff).read_text(encoding="utf-8", errors="surrogateescape")
    payload, code = record(diff_text, base=args.base, head=args.head)
    Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"recorded review: {payload['verdict']} — {payload['files_examined']} files, "
          f"{payload['added_lines_examined']} added lines, {len(payload['findings'])} findings")
    for finding in payload["findings"]:
        location = f"{finding['path']}:{finding['line']}" if finding["line"] else finding["path"]
        print(f"  {finding['severity']} {finding['rule']} {location} — {finding['note']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
