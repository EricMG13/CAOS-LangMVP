import asyncio, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from caos.contracts import digest


async def main():
    tmp = Path(__file__).parent / "data_r3"
    shutil.rmtree(tmp, ignore_errors=True)
    settings, store, engine = make(tmp)
    case, source = seed_case_with_source(store)
    run = engine.runs.create_run(case["id"], "FULL_CREDIT", "screen", "analyst", provider_identity=engine._provider_identity)
    cur = store.current_source_set(case["id"])
    snap = {"id": None, "case_id": case["id"], "run_id": run["id"], "source_set_id": cur["id"],
            "source_set_version": cur["version"], "artifacts": [],
            "provider_identity": engine._provider_identity.as_dict(), "previous_snapshot_id": None,
            "accepted_at": "2026-09-06T00:00:00+00:00"}
    pre = {k: v for k, v in snap.items() if k not in {"digest", "id"}}
    snap["id"] = "snap-test"
    snap["digest"] = digest(pre)
    engine.runs.create_snapshot(snap)
    before = store.get_case(case["id"])["visible_snapshot_id"]
    audits_before = len(store.audit_trail())

    def broken_audit(*a, **k):
        raise RuntimeError("audit insert failed (connection dropped between the two transactions)")

    store.audit_event = broken_audit
    try:
        await engine.switch_visible(case["id"], "snap-test", actor="analyst")
    except RuntimeError as exc:
        print("route answers 5xx:", exc)
    after = store.get_case(case["id"])["visible_snapshot_id"]
    print("visible_snapshot_id before:", before, "after:", after, "| audit rows added:", len(store.audit_trail()) - audits_before)
    store.close()


asyncio.run(main())
