import asyncio, time, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *


class SlowHostControl(HostControlProvider):
    def __init__(self, delay):
        super().__init__()
        self.delay = delay

    async def create_message(self, request):
        await asyncio.sleep(self.delay)
        return HostControlProvider.create_message(self, request)


async def main():
    tmp = Path(__file__).parent / "data_r1"
    shutil.rmtree(tmp, ignore_errors=True)
    settings, store, engine = make(tmp, provider=SlowHostControl(0.5))
    case, source = seed_case_with_source(store)
    # production entrypoint shape: auto-continue ON, start_run returns at the plan gate
    engine.enable_auto_continue()
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    print("after start_run:", run["status"], "nodes:", len(run["nodes"]))
    # simulate the process dying right after the gate: close engine A (cancels the continuation)
    await engine.aclose()
    print("after crash: status in store =", engine.runs.get_run(run["id"])["status"],
          "executed modules so far =", engine.runs.executed_modules(run["id"]))
    # restart: engine B over the same store + checkpoint file, exactly as run.py::serve does
    settings2, store2, engine2 = make(tmp, provider=SlowHostControl(0.5))
    engine2.enable_auto_continue()
    t0 = time.monotonic()
    await engine2.recover()          # run.py::serve awaits this BEFORE uvicorn binds the socket
    elapsed = time.monotonic() - t0
    rec = engine2.runs.get_run(run["id"])
    print(f"recover() returned after {elapsed:.1f}s; run status now = {rec['status']}; "
          f"provider calls made inside recover() = {engine2.provider.calls}; "
          f"continuations scheduled = {len(engine2._continuations)}")
    await engine2.aclose()
    store2.close()
    store.close()


asyncio.run(main())
