"""read_evidence host boundary (invariants 1, 2; DECISIONS §12.9–11).

Order inside one read: budget ceiling -> argument bounds -> live authority
(case / pinned set membership / withdrawn, re-checked on EVERY call) -> block
existence -> charge -> delivered-set update -> return, as one ordered unit.
Authority failures always outrank block-existence (AGENT_AUTHORITY_MISMATCH
before AGENT_OUTPUT_INVALID). A rejected read leaves no citation expectation.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from ..storage.store import DomainStore
from .budget import EVIDENCE_BYTES_PER_SIX, EVIDENCE_READS_PER_MODULE
from .provider import AgentError


def render_tool_result(rows: list[dict[str, Any]]) -> str:
    """The identical serialization sent to the model as the tool_result."""
    return json.dumps(rows, sort_keys=True)


def evidence_payload_bytes(rows: list[dict[str, Any]]) -> int:
    """Appendix A: the byte ceiling counts the tool_result serialization."""
    return len(render_tool_result(rows))


class EvidenceReader:
    def __init__(
        self,
        store: DomainStore,
        case_id: str,
        source_set_id: str,
        run_id: str,
        *,
        read_limit: int = 6 * EVIDENCE_READS_PER_MODULE,
        byte_limit: int = EVIDENCE_BYTES_PER_SIX,
        on_read: Callable[[str, list[str], int], None] | None = None,
    ) -> None:
        self.store = store
        self.case_id = case_id
        self.source_set_id = source_set_id
        self.run_id = run_id
        self.read_limit = read_limit
        self.byte_limit = byte_limit
        self.reads_used = 0
        self.bytes_used = 0
        self._delivered: dict[tuple[str, str], dict[str, str]] = {}
        self._on_read = on_read

    def delivered(self) -> set[tuple[str, str]]:
        return set(self._delivered)

    def delivered_rows(self) -> dict[tuple[str, str], dict[str, str]]:
        return dict(self._delivered)

    def exhaust_read_budget_for_tests(self) -> None:
        self.reads_used = self.read_limit

    def _authorized_source(self, source_id: str) -> dict[str, Any]:
        """Live authority, re-established from the store on every call — a
        checkpoint or prior read never stands in for these checks (§11.3).
        Any failure is AGENT_AUTHORITY_MISMATCH, always ahead of block lookup."""
        def refuse() -> None:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned evidence is unavailable")

        pinned_set = self.store.source_set(self.source_set_id)
        if pinned_set is None or pinned_set.get("case_id") != self.case_id:
            refuse()
        if source_id not in (pinned_set.get("source_ids") or []):
            refuse()  # never reachable outside the pinned membership
        source = self.store.get_source(source_id)
        if source is None or source.get("case_id") != self.case_id:
            refuse()  # foreign-case source
        if source.get("withdrawn"):
            refuse()  # withdrawal is checked live, even after resume
        return source

    def read(self, source_id: str, block_ids: list[str]) -> list[dict[str, Any]]:
        if self.reads_used + 1 > self.read_limit:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "evidence read budget exhausted")
        if (
            not isinstance(source_id, str)
            or not isinstance(block_ids, list)
            or not block_ids
            or len(block_ids) > 50
            # Element types are checked BEFORE the dedup set is built: an
            # unhashable block id (a list, a dict) would otherwise leave the
            # boundary as a bare TypeError instead of a typed refusal.
            or any(not isinstance(item, str) for item in block_ids)
            or len(block_ids) != len(set(block_ids))
        ):
            raise AgentError("AGENT_OUTPUT_INVALID", "evidence block IDs must be unique and bounded")

        source = self._authorized_source(source_id)

        blocks = {block.get("block_id"): block for block in source.get("blocks") or []}
        if any(block_id not in blocks for block_id in block_ids):
            raise AgentError("AGENT_OUTPUT_INVALID", "evidence block is absent")

        rows = [
            {
                "source_id": source_id,
                "source_digest": source["sha256"],
                "origin_family": source.get("origin_family", source["sha256"]),
                "authority_class": source.get("authority_class", "unclassified"),
                "block_id": block_id,
                "locator": blocks[block_id].get("locator"),
                "extractor_version": blocks[block_id].get("extractor_version"),
                "confidence": blocks[block_id].get("confidence"),
                "text": blocks[block_id].get("text"),
            }
            for block_id in block_ids
        ]
        returned_bytes = evidence_payload_bytes(rows)
        if self.bytes_used + returned_bytes > self.byte_limit:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "evidence byte budget exhausted")

        # §12.10: charge -> delivered-set update -> return, one ordered unit.
        # The run-wide ledger charge comes FIRST, ahead of the reader's own
        # counters: the per-node read_limit is `limits - used` read at node
        # entry, so concurrent module nodes each think the whole remainder is
        # theirs and one of them is refused here rather than by the local guard
        # above. Updating the delivered set before that charge would leave a
        # citation expectation for rows this call never returns.
        if self._on_read is not None:
            self._on_read(source_id, block_ids, returned_bytes)
        self.reads_used += 1
        self.bytes_used += returned_bytes
        self._delivered.update(
            {
                (source_id, row["block_id"]): {
                    "source_digest": row["source_digest"],
                    "origin_family": row["origin_family"],
                    "authority_class": row["authority_class"],
                    "locator": json.dumps(row["locator"], sort_keys=True, separators=(",", ":")),
                    "extractor_version": str(row["extractor_version"]),
                    "confidence": str(row["confidence"]),
                }
                for row in rows
            }
        )
        return rows
