"""Local development entrypoint: run.py's assembly with dev defaults — SQLite
store + checkpoints under ./.dev-data, loopback bind, no production validation,
the dev identity edge (x-caos-role trusted). Agent execution stays off unless
AGENT_EXECUTION_ENABLED=true with exactly one provider key. Fixed deterministic
placeholders are test-only, so ordinary routes typed-refuse until their
source-computed executors are available.
"""

from __future__ import annotations

import os
from pathlib import Path

from run import build, serve

from caos.config import Settings


def main() -> None:
    settings = Settings.from_env()
    if settings.environment != "development":
        raise RuntimeError("dev.py requires ENVIRONMENT=development")
    app, engine = build(settings, Path(os.getenv("CAOS_DATA_DIR", ".dev-data")).resolve())
    try:
        serve(app, engine, host="127.0.0.1", port=settings.port)
    except BaseException:
        try:
            engine.store.close()
        except BaseException:
            pass
        raise
    engine.store.close()


if __name__ == "__main__":
    main()
