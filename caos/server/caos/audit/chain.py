"""Audit integrity chain (Task 10; DECISIONS §14.19).

Every audit row carries `digest` over its own content and `prev_digest`, the
digest of the previous row in the same chain. Chains are keyed per case
(`chain_key` = case id) with one `__global__` chain for events that belong to
no case, so a case-scoped audit package can be verified on its own. Row
digests are sha256 over canonical JSON (sorted keys, compact separators,
ASCII-escaped) of the host-owned fields only.

Stdlib only, by design: `caos/server/caos/audit/verify_package.py` re-states
these two functions verbatim so the offline verifier needs no application
import, and a test pins the two copies equal.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS = "0" * 64
GLOBAL_CHAIN = "__global__"
CHAIN_FIELDS = ("chain_key", "chain_seq", "id", "action", "actor", "at", "data", "prev_digest")


def event_digest(row: dict[str, Any]) -> str:
    preimage = {field: row[field] for field in CHAIN_FIELDS}
    encoded = json.dumps(preimage, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_chain(rows: list[dict[str, Any]], head: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Findings for one chain, ascending `chain_seq`. Empty means intact.

    Detects mutation (row digest), deletion and insertion (contiguous
    `chain_seq` from 1 and `prev_digest` links), reordering (both), and a head
    that does not name the last row. `head` is None only for an empty chain.
    """
    findings: list[dict[str, Any]] = []
    previous = GENESIS
    expected_seq = 1
    for row in rows:
        seq = row.get("chain_seq")
        if seq != expected_seq:
            findings.append({"code": "AUDIT_CHAIN_SEQUENCE_BROKEN", "chain_seq": seq, "expected": expected_seq})
            expected_seq = seq if isinstance(seq, int) else expected_seq
        if row.get("prev_digest") != previous:
            findings.append({"code": "AUDIT_CHAIN_LINK_BROKEN", "chain_seq": seq})
        try:
            recomputed = event_digest(row)
        except (KeyError, TypeError, ValueError):
            recomputed = None
        if recomputed != row.get("digest"):
            findings.append({"code": "AUDIT_EVENT_DIGEST_MISMATCH", "chain_seq": seq})
        previous = row.get("digest") if isinstance(row.get("digest"), str) else GENESIS
        expected_seq += 1
    if rows:
        last = rows[-1]
        if head is None or head.get("chain_seq") != last.get("chain_seq") or head.get("digest") != last.get("digest"):
            findings.append({"code": "AUDIT_CHAIN_HEAD_MISMATCH", "chain_seq": last.get("chain_seq")})
    elif head is not None:
        findings.append({"code": "AUDIT_CHAIN_HEAD_MISMATCH", "chain_seq": None})
    return findings
