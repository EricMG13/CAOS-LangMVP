"""Structured JSON logs on stdout — stdlib logging, no dependency, no framework.

Three questions this exists to answer at 3am without attaching a debugger:

    which run is stuck   run/node state transitions + the gate interrupt
    what did it refuse   the typed taxonomy code, never the refused content
    what has it spent    provider token counts, budget reserve + reconcile

Those, plus startup recovery, are the only things logged. There is deliberately
no debug channel: every extra log line is another chance for document text to
escape, and the questions above are answered by a handful of lines per run.

**Nothing document-derived is ever logged.** Source text, evidence block text,
module output and compiled prompts are all attacker-controlled — every document
CAOS ingests is — and a log sink sits outside every boundary the ten invariants
defend. Call sites therefore pass host-owned scalars only (ids, typed codes,
counts) and never an exception *message* from the run path: a ValueError out of
output validation quotes the model's own text back at you.
`caos/tests/spec/test_observability_spec.py` is the enforcement, not this note.

Every string that does reach a line, including a nested mapping key, is redacted,
then truncated to MAX_STRING — the structural backstop behind the call-site
discipline, so a future slip costs a couple of hundred characters rather than a
document. Exception messages never reach this boundary; the model worker records
the exception class only.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import re
import sys
from typing import Any, Iterator

LOGGER_NAME = "caos"

_logger = logging.getLogger(LOGGER_NAME)
_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar("caos_log_context", default={})

# Long enough for a taxonomy code, an id, or an exception class; short
# enough that nothing large can ride a field that was never meant to carry it.
MAX_STRING = 200

_SECRETS: set[str] = set()
# Backstop for a secret nobody registered: provider key shapes, bearer tokens,
# and the userinfo half of any DSN.
_SECRET_PATTERN = re.compile(
    r"sk-[A-Za-z0-9._\-]{12,}"
    r"|(?i:bearer)\s+[A-Za-z0-9._\-]{12,}"
    r"|(?<=//)[^/\s:@]+:[^/\s@]+(?=@)"
)


def register_secrets(*values: str | None) -> None:
    """Exact values to strip from any logged string. Short values are ignored:
    redacting a four-character "secret" would blank out unrelated text."""
    for value in values:
        if value and len(value) >= 8:
            _SECRETS.add(value)


def redact(text: str) -> str:
    for secret in _SECRETS:
        text = text.replace(secret, "***")
    return _SECRET_PATTERN.sub("***", text)


# Redacting runs over the whole string, so a field that was never meant to be
# large would pay for its own mistake. Bound generously first, redact, bound to
# MAX_STRING: any secret beginning inside the kept prefix is redacted whole, and
# anything starting past the outer bound never reaches the line at all.
_SCAN_LIMIT = 4096


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value[:_SCAN_LIMIT])[:MAX_STRING]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if isinstance(value, dict):
        return {_clean(str(key)): _clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(item) for item in value]
    return _clean(str(value))  # one branch owns the bounds, so none can skip them


class JsonFormatter(logging.Formatter):
    """One JSON object per line.

    Exception and stack text are rendered too — a formatter that silently drops
    `exc_info` is a broken formatter — but like every other value they are
    truncated to MAX_STRING. That bound is the structural half of the no-content
    rule: call-site discipline keeps document text off the line, and this keeps
    a slip from costing more than a couple of hundred characters.
    """

    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        if record.name != LOGGER_NAME:
            line["logger"] = record.name
        line.update(getattr(record, "caos", {}))
        if record.exc_info:
            line["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            line["stack"] = record.stack_info
        return json.dumps({key: _clean(value) for key, value in line.items()}, default=str)


def log_event(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """The only emitter. `event` is a stable dotted name; fields are host-owned
    scalars merged over the ambient `run_context`. `None` fields are omitted —
    a null run_id reads as a run whose id is null."""
    merged = {**_context.get(), **fields}
    _logger.log(level, event, extra={
        "caos": {key: value for key, value in merged.items() if value is not None},
    })


@contextlib.contextmanager
def run_context(**fields: Any) -> Iterator[None]:
    """Ambient identity for everything logged underneath: the agent loop reports
    provider calls without being handed a run id. A ContextVar, so concurrent
    module nodes in one superstep never see each other's."""
    token = _context.set({**_context.get(), **{k: v for k, v in fields.items() if v is not None}})
    try:
        yield
    finally:
        _context.reset(token)


def configure_logging(settings: Any = None, *, stream: Any = None) -> None:
    """Idempotent: exactly one JSON handler on the `caos` logger, stdout by
    default. Entrypoints call this; importing the package configures nothing, so
    a library consumer (and the test suite) keeps its own handlers.

    An unparseable CAOS_LOG_LEVEL raises here rather than silently defaulting —
    a log level you think you set and did not is worse than a failed boot.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(JsonFormatter())
    _logger.handlers[:] = [handler]
    _logger.setLevel(os.getenv("CAOS_LOG_LEVEL", "INFO"))
    _logger.propagate = False
    if settings is not None:
        register_secrets(
            settings.anthropic_api_key,
            settings.openrouter_api_key,
            settings.edge_proxy_secret,
            settings.session_secret,
        )
