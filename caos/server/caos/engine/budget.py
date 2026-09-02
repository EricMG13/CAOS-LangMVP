"""Budget constants, envelope, ledger, manifest bounding, attempt recorder.

Invariant 8 / DECISIONS §12.D and Appendix A: every ceiling is host-enforced and
fails BEFORE overspend. Legacy values remain literal unless a dated enterprise
amendment records the replacement (DECISIONS §14).
"""

from __future__ import annotations

import math
from typing import Any

from ..contracts import canonical_json
from .provider import AgentError


# Appendix A literals.
MAX_MANIFEST_BLOCKS = 2_000
MAX_MANIFEST_BYTES = 256 * 1_024
MAX_MANIFEST_FILENAME_CHARS = 255
MAX_MANIFEST_MEDIA_TYPE_CHARS = 160
MAX_MANIFEST_FIELD_CHARS = 160
MAX_MANIFEST_LOCATOR_CHARS = 500
MAX_MANIFEST_LOCATOR_ITEMS = 100
MAX_MANIFEST_LOCATOR_DEPTH = 8
MAX_MANIFEST_LOCATOR_NODES = 500
FINALIZATION_ALLOWANCE_SECONDS = 5.0
PROVIDER_TIMEOUT_SECONDS = 150.0
PROVIDER_CONCURRENCY_SLOTS = 2
MAX_ACTIVE_JOBS = 20
REPAIR_TEXT_LIMIT = 1_500
MAX_ATTEMPT_RECORDS = 256

# Per-module allowances (legacy canonical envelope ÷ 6, §12.20).
EVIDENCE_READS_PER_MODULE = 10
EVIDENCE_BYTES_PER_SIX = 5 * 1024 * 1024
EVIDENCE_BYTES_PER_MODULE = math.ceil(EVIDENCE_BYTES_PER_SIX / 6)
INPUT_TOKENS_PER_SIX = 500_000
ACTIVE_MINUTES = 15
PROVIDER_RETRIES = 1
REPAIRS = 1

DIMENSIONS = (
    "turns",
    "evidence_reads",
    "evidence_bytes",
    "input_tokens",
    "output_tokens",
    "active_minutes",
    "provider_retries",
    "repairs",
)


def route_envelope(agent_module_ids: list[str], registry: dict[str, Any]) -> dict[str, int]:
    """§12.20: the envelope is a pure function of (compiled route, registry).
    N=6 over the legacy six reproduces the legacy envelope exactly."""
    caps = [registry[module_id].max_output_tokens for module_id in agent_module_ids]
    n = len(agent_module_ids)
    evidence_reads = EVIDENCE_READS_PER_MODULE * n
    calculation_turns = sum(len(registry[module_id].calculators) for module_id in agent_module_ids)
    return {
        "turns": evidence_reads + calculation_turns + n + REPAIRS,
        "evidence_reads": evidence_reads,
        "evidence_bytes": math.ceil(EVIDENCE_BYTES_PER_SIX * n / 6),
        "input_tokens": math.ceil(INPUT_TOKENS_PER_SIX * n / 6),
        "output_tokens": sum(caps) + max(caps),
        "active_minutes": ACTIVE_MINUTES,
        "provider_retries": PROVIDER_RETRIES,
        "repairs": REPAIRS,
    }


class BudgetLedger:
    """In-memory ledger arithmetic; the store-backed run ledger mirrors it."""

    def __init__(self, limits: dict[str, int | float]) -> None:
        self._limits = {key: limits.get(key, 10**12) for key in DIMENSIONS}
        self._used: dict[str, int | float] = {key: 0 for key in DIMENSIONS}

    @classmethod
    def for_tests(cls, **limits: int | float) -> "BudgetLedger":
        return cls(limits)

    def limit(self, dimension: str) -> int | float:
        return self._limits[dimension]

    def used(self, dimension: str) -> int | float:
        return self._used[dimension]

    def note_count_tokens(self) -> None:
        """Turns charge on create only (legacy provider.py:326 vs :344)."""

    def exhaust_for_tests(self, dimension: str) -> None:
        self._used[dimension] = self._limits[dimension]

    def reserve_next_operation(self, dimension: str, amount: int | float = 1) -> None:
        if self._used[dimension] + amount > self._limits[dimension]:
            raise AgentError("AGENT_BUDGET_EXCEEDED", f"{dimension} budget exhausted")
        self._used[dimension] += amount


def locator_is_bounded(value: Any) -> bool:
    """Structural bomb guard for evidence locators (Appendix A: depth <= 8,
    <= 100 items per container, <= 500-char strings, <= 500 total nodes,
    finite floats only). Iterative worklist — no recursion to blow."""
    nodes_left = MAX_MANIFEST_LOCATOR_NODES
    pending: list[tuple[Any, int]] = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        nodes_left -= 1
        if nodes_left < 0 or depth > MAX_MANIFEST_LOCATOR_DEPTH:
            return False
        match current:
            case None | bool() | int():
                continue
            case float():
                if not math.isfinite(current):
                    return False
            case str():
                if len(current) > MAX_MANIFEST_LOCATOR_CHARS:
                    return False
            case list():
                if len(current) > MAX_MANIFEST_LOCATOR_ITEMS:
                    return False
                pending.extend((item, depth + 1) for item in current)
            case dict():
                if len(current) > MAX_MANIFEST_LOCATOR_ITEMS:
                    return False
                for key, item in current.items():
                    if not isinstance(key, str) or len(key) > MAX_MANIFEST_FIELD_CHARS:
                        return False
                    pending.append((item, depth + 1))
            case _:
                return False
    return True


def _bounded_text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and len(value) <= limit


def bound_manifest(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail closed before provider contact. Rows = sources + blocks against the
    block ceiling; the byte ceiling is the canonical-JSON measure of the block
    rows (the part that grows without bound).
    Ceilings are inclusive."""
    rows = 0
    payload_bytes = 0
    for entry in entries:
        rows += 1
        if rows > MAX_MANIFEST_BLOCKS:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
        sha = entry.get("sha256") or entry.get("digest")
        if (
            not _bounded_text(entry.get("source_id"), MAX_MANIFEST_FIELD_CHARS)
            or not _bounded_text(entry.get("filename"), MAX_MANIFEST_FILENAME_CHARS)
            or not _bounded_text(entry.get("media_type"), MAX_MANIFEST_MEDIA_TYPE_CHARS)
            or not isinstance(sha, str)
            or len(sha) != 64
        ):
            raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest field ceiling exceeded")
        for block in entry.get("blocks") or []:
            rows += 1
            if rows > MAX_MANIFEST_BLOCKS:
                raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
            if (
                not isinstance(block, dict)
                or not _bounded_text(block.get("block_id"), MAX_MANIFEST_FIELD_CHARS)
                or not locator_is_bounded(block.get("locator"))
                or not _bounded_text(str(block.get("extractor_version")), MAX_MANIFEST_FIELD_CHARS)
                or not _bounded_text(str(block.get("confidence")), MAX_MANIFEST_FIELD_CHARS)
            ):
                raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest field ceiling exceeded")
            payload_bytes += len(canonical_json(
                {key: block.get(key) for key in ("block_id", "locator", "extractor_version", "confidence")}
            ).encode("utf-8"))
            if payload_bytes > MAX_MANIFEST_BYTES:
                raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest byte ceiling exceeded")
    return entries


class AttemptRecorder:
    """§12.11 / Appendix A: scalar allowlist with truncation; non-terminal rows
    fail closed at the fixed audit ceiling; terminal rows are cap-exempt into
    the same bounded ring."""

    def __init__(self, base: dict[str, Any] | None = None) -> None:
        self.base = dict(base or {})
        self._rows: list[dict[str, Any]] = []

    @classmethod
    def for_tests(cls) -> "AttemptRecorder":
        return cls()

    def rows(self) -> list[dict[str, Any]]:
        return self._rows

    @staticmethod
    def _allow(details: dict[str, Any]) -> dict[str, Any]:
        allowed: dict[str, Any] = {}
        for key, value in details.items():
            if isinstance(value, str):
                allowed[key] = value[:200]
            elif isinstance(value, (int, float, bool)) or value is None:
                allowed[key] = value
            elif (
                isinstance(value, list)
                and len(value) <= 50
                and all(isinstance(item, str) and len(item) <= 160 for item in value)
            ):
                allowed[key] = list(value)
        return allowed

    def record(self, kind: str, **details: Any) -> None:
        row = {**self.base, "kind": kind[:40], **self._allow(details)}
        if kind == "terminal":
            self._rows.append(row)
            self._rows[:] = self._rows[-MAX_ATTEMPT_RECORDS:]
            return
        if len(self._rows) >= MAX_ATTEMPT_RECORDS:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "attempt metadata budget exhausted")
        self._rows.append(row)
