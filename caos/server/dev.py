"""Local development entrypoint: run.py's assembly with dev defaults — SQLite
store + checkpoints under ./.dev-data, loopback bind, no production validation,
the dev identity edge (x-caos-role trusted). Agent execution stays off unless
AGENT_EXECUTION_ENABLED=true with an ANTHROPIC_API_KEY; deterministic routes
(e.g. EARNINGS_UPDATE at screen depth) run end to end with no key at all.
"""

from __future__ import annotations

import os
from pathlib import Path

from run import build, serve, shutdown

from caos.config import Settings


def main() -> None:
    settings = Settings.from_env()
    app, engine = build(settings, Path(os.getenv("CAOS_DATA_DIR", ".dev-data")).resolve())
    try:
        serve(app, engine, host="127.0.0.1", port=settings.port)
    except BaseException:
        try:
            shutdown(engine)
        except BaseException:
            pass
        raise
    shutdown(engine)


if __name__ == "__main__":
    main()
