"""Filing-gate identity (DECISIONS §10.7, §12.21-23).

The thread identity is a deterministic digest over the freeze identity —
including build_id, so a methodology or model change can never resume another
freeze's gate. The gate-level approval hash is the canonical sha256 form bound
to the exact frozen preview digest.
"""

from __future__ import annotations

import re
from typing import Any

from ..contracts import digest

APPROVAL_HASH_PATTERN = r"^sha256:[0-9a-f]{64}$"


def filing_thread_id(*, case_id: str, pathway: str, draft_version: int, draft_digest: str, build_id: str) -> str:
    return "dth-" + digest({
        "case_id": case_id,
        "pathway": pathway,
        "draft_version": draft_version,
        "draft_digest": draft_digest,
        "build_id": build_id,
    })


def canonical_approval_hash(frozen: dict[str, Any]) -> str:
    return f"sha256:{frozen['preview_digest']}"


def validate_approval_hash(value: str, frozen: dict[str, Any]) -> None:
    if not re.fullmatch(APPROVAL_HASH_PATTERN, value) or value != canonical_approval_hash(frozen):
        raise ValueError("DELIVERABLE_APPROVAL_HASH_INVALID: only the canonical sha256 form resumes the gate")
