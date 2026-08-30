"""Second seeding stage: cases carrying the canonical CP-MODEL inputs.

Model Builder and Report Studio only light up behind an *accepted FULL_CREDIT
run at full depth*, and full depth is agent execution — a provider key and real
spend. `Engine.run_scripted_for_tests` is the seam the spec suite already uses
to produce those exact canonical module outputs deterministically, so QA reuses
it rather than inventing a second fixture path or paying for tokens.

Run with the app stopped: it drives the engine directly against the same
Postgres store and checkpoint file the app uses.

    python qa/seed_model.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent / "caos" / "server"
sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.engine.runtime import Engine  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402

ANALYST = "analyst.qa@caos.invalid"
MODEL_READY_CASES = int(os.getenv("QA_MODEL_CASES", "3"))


async def main() -> None:
    settings = Settings.from_env()
    # Scripted runs take the agent branch's place, but the branch is only
    # reachable when execution is enabled at all.
    settings = type(settings)(**{**settings.__dict__, "agent_execution_enabled": True})
    data = Path(os.environ["CAOS_DATA_DIR"]).resolve()
    store = DomainStore.from_url(settings.database_url)
    engine = Engine.create(settings=settings, store=store,
                           checkpoint_path=data / "checkpoints.db", provider=None)

    cases = [case for case in store.list_cases(ANALYST) if store.list_sources(case["id"])]
    cases.sort(key=lambda case: case["id"])
    for case in cases[:MODEL_READY_CASES]:
        run = await engine.run_scripted_for_tests(case["id"])
        snapshot = await engine.accept(run["id"], actor=ANALYST)
        print(f"model-ready {case['issuer']:<26} run={run['id']} snapshot={snapshot['id']}")


if __name__ == "__main__":
    asyncio.run(main())
