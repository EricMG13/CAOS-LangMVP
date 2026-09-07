"""Local development entrypoint: run.py's assembly with dev defaults — SQLite
store + checkpoints under ./.dev-data, loopback bind, no production validation,
the dev identity edge (x-caos-role trusted). Agent execution stays off unless
AGENT_EXECUTION_ENABLED=true with an explicit provider or unambiguous key. Fixed deterministic
placeholders are test-only, so ordinary routes typed-refuse until their
source-computed executors are available.
"""

from __future__ import annotations

import os
from pathlib import Path

from run import run_app

from caos.config import Settings


def main() -> None:
    settings = Settings.from_env()
    if settings.environment != "development":
        raise RuntimeError("dev.py requires ENVIRONMENT=development")
    run_app(settings, Path(os.getenv("CAOS_DATA_DIR", ".dev-data")).resolve(), host="127.0.0.1")


if __name__ == "__main__":
    main()
