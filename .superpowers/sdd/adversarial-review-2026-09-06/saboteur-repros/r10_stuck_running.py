import asyncio, sys, shutil, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from sqlalchemy.exc import OperationalError


async def main():
    tmp = Path(__file__).parent / "data_r10"
    shutil.rmtree(tmp, ignore_errors=True)
    settings, store, engine = make(tmp)
    case, source = seed_case_with_source(store)
    engine.enable_auto_continue()
    original = engine.runs.node_running
    calls = {"n": 0}

    def flaky_node_running(run_id, module_id):
        # one transient infrastructure failure on the first module after the gate
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("UPDATE run_nodes ...", {}, Exception("database is locked"))
        return original(run_id, module_id)

    engine.runs.node_running = flaky_node_running
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    print("start_run returned:", run["status"])
    # let the scheduled continuation run and fail
    for _ in range(50):
        await asyncio.sleep(0.1)
        if not engine._continuations:
            break
    rec = engine.runs.get_run(run["id"])
    print("after the continuation died: status =", rec["status"], "| error =", rec["error"],
          "| active_admission_count =", engine.runs.active_admission_count(),
          "| nodes running =", [n["module_id"] for n in rec["nodes"] if n["status"] == "running"],
          "| latest ticket =", engine.runs.latest_ticket(run["id"]))
    # what the UI can do about it: POST /resume -> engine.resume; measure how long it takes and where it lands
    t0 = time.monotonic()
    try:
        resumed = await asyncio.wait_for(engine.resume(run["id"]), timeout=120)
        print(f"resume() returned after {time.monotonic() - t0:.1f}s with status {resumed['status']} "
              f"(the whole remaining run executed inside the HTTP request; continuations = {len(engine._continuations)})")
    except Exception as exc:
        print("resume() raised", type(exc).__name__, exc)
    await engine.aclose()
    store.close()


asyncio.run(main())
