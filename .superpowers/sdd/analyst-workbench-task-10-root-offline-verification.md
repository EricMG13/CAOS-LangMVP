# Task 10 independent controller offline verification

Read-only command run by root against each retained actual accepted-v2 journey audit package, with worktree `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex` and unchanged backend source at `90403c7ce94e6384fd1f4595eff893935e5530f9`:

```sh
caos/server/.venv314/bin/python caos/server/caos/audit/verify_package.py AUDIT_PACKAGE_PATH --json
```

| Browser / attempt | Audit package path | Exit | Tool wall seconds |
|---|---|---|---|
| Chromium / 4 | `/private/tmp/caos-task10.j0GTQN/evidence/qualification-chromium-attempt-4/task10-qualification/chromium/audit-package-case-fd7c7a44f18141ac967e.zip` | 0 | 0.027133042 |
| Firefox / 1 | `/private/tmp/caos-task10.j0GTQN/evidence/qualification-firefox-attempt-1/task10-qualification/firefox/audit-package-case-883b3cf46e67415b91b3.zip` | 0 | 0.017024 |
| WebKit / 3 | `/private/tmp/caos-task10.j0GTQN/evidence/qualification-webkit-attempt-3/task10-qualification/webkit/audit-package-case-611bfdf6cb1b45db8eea.zip` | 0 | 0.018097333 |

Actual stdout, in the same order:

```json
{"case_id": "case-fd7c7a44f18141ac967e", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
{"case_id": "case-883b3cf46e67415b91b3", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
{"case_id": "case-611bfdf6cb1b45db8eea", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
```

No server calls, package edits or live-provider activity. These checks prove the retained fixture packages pass the existing independent offline audit contract, including reconstructed Markdown, frozen export identities and detached independent receipts. They do not prove live analytical quality, native XLSX visual fidelity, future modified packages or the separately owed incremental-v2 journey.

## Retained downloads independently matched to receipts

Root additionally ran a read-only Node assertion check against the same three successful `qualification.json` records: read all nine retained MD/PDF/XLSX files, recompute SHA-256, compare each with both recorded export metadata and `receipt.exports[format]`, compare byte lengths, and assert approver differs from both signer and freezer. Exit0; all9formats matched and all3approvers were independent. This closes the distinction between verifying the ZIP's stored exports and the separately retained download files. No package or export file was modified.

## Actual accepted-v2 incremental publication

Root read the successful final-harness FC→Earnings Update `incremental-qualification.json`, with prior build `mdl-6e9a4b8878f842b3a913`, accepted overlay `mdl-f27dcf570ee84aa5bece`, and separately filed deliverable `dlv-33460c5a7f9a0819de1ca6c63ce557c9f9f4f3e76b77c79eea4b36cbdfe96bc5`.

Root ran the same offline CLI against `/private/tmp/caos-task10-final.cPQ6nz/evidence/incremental-attempt-1/task10-incremental/audit-package-case-e8643dec0d194296a1dd.zip`: exit0, tool wall0.053643708seconds. Actual stdout:

```json
{"case_id": "case-e8643dec0d194296a1dd", "checked": {"audit_events": 22, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 2, "objects": 34, "receipts": 1, "runs": 2}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
```

The independent read-only Node receipt/download check also passed for all3incremental MD/PDF/XLSX files and independent approver identity. The ZIP is SHA-256 `b5e4b0afe3f04cf3336933289cb9f4d11aceb39b0c879899d6149882be0c8c86`; PDF `661b3313be0afa0e1277c641ee0e2db3cd5495330046038e4bb379ec1cd83003`; XLSX `4994569a80548b95632896a9a0c8d9d9437076dc485426bdf81f79946bb842b5`. This closes the prior actual-v2 incremental freeze/file/offline-verification gap, within the same explicit host-control fixture-only limit.

## Definitive post-responsive-fix Chromium package

Root independently verified the durable `.superpowers/sdd/evidence/task10/qualification-final/chromium/audit-package-case-1a63f2328b8842b58d2f.zip` with the same existing CLI and `--json`: exit 0, shell wall 0.148s, full output retained at `/private/tmp/caos-task10-root-axe.MO0LkI/final-chromium-offline.log`.

```json
{"case_id": "case-1a63f2328b8842b58d2f", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
```

Root separately read every retained downloaded byte: Markdown 42340B, PDF 2838082B and XLSX 58904B all match both qualification metadata and detached receipt SHA-256s. ZIP bytes match their recorded size/digest; the approver differs from both signer and freezer. This package binds `snap-b6b42d2e8cbd491ca5d3`, build `mdl-f773d355038a4aa1aa5f`, revision `rev-a297103ff3724ce38c9e`, deliverable `dlv-7e5b00ba600ae98c0f3fe0057dff35e3d56acdc9d7e97ebe546c6f089cf4c22d` and receipt `rcpt-029d719497764894a287`.

These are newly generated case/identity-specific export bytes. The complete 46-page PDF / 30-sheet native XLSX visual review remains the earlier explicitly identified Chromium example, produced by the byte-identical backend/renderer. Do not relabel that visual review as a separate rendering of this new package.

## Definitive Firefox and WebKit packages

Root independently ran the same offline CLI on both durable `qualification-final/<engine>/audit-package-<case>.zip` files:

```json
{"case_id": "case-3e9dc09192ce4fcdb758", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
{"case_id": "case-720942fe4d974f5d80fe", "checked": {"audit_events": 19, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 1, "objects": 29, "receipts": 1, "runs": 1}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
```

Both exit 0; tool wall times 0.023611292s (Firefox) and 0.036184542s (WebKit). Root also independently hashed all six retained MD/PDF/XLSX files and checked byte lengths, qualification metadata, detached receipt digests and distinct approvers; all passed. Firefox binds `snap-2e9d6152e814470e8d3f` / `mdl-5540bfa8c01e48d7ada5` / `rev-f62cb8d43a6b4fdcb4ef` / `rcpt-5e70b0b97646401881b1`. WebKit binds `snap-d40e52df8a0c4f4a9f18` / `mdl-3f3f02c71bb84d69b29c` / `rev-ce433740b16f4e988cef` / `rcpt-84d949d49c7b4cb489a6`.

## Definitive incremental-v2 package

Root read `evidence/task10/incremental-v2-final/incremental-qualification.json`, independently checked the recorded previous-snapshot equality and all3retained download byte lengths/hashes against both metadata and the distinct approver's receipt, then ran the existing offline CLI against `audit-package-case-3d9fe216d658493aac03.zip`: exit0, tool wall0.047320125s.

```json
{"case_id": "case-3d9fe216d658493aac03", "checked": {"audit_events": 22, "frozen_deliverables": 1, "markdown_reconstructed": 1, "model_builds": 2, "objects": 34, "receipts": 1, "runs": 2}, "findings": [], "ok": true, "schema_version": "caos.audit-package.v1"}
```

The accepted FullCredit base is `snap-9080b1e7d2cb45b0ad96` / `mdl-bd4fa29c1bc8471f876e`; the accepted EarningsUpdate overlay is `snap-44a2dfa945c84b5bb297` / `mdl-011288b9e9c0441ab1bf`, filed as `dlv-0cfc56376e3c4a95a3c97dd1b9dcdfc90dcf7a239aaeec8eeaf19c86dfc3e411`. This final-harness run has no page errors and preserves the fixture-only analytical qualification limit.
