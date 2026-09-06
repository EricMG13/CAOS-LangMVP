import sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from fastapi.testclient import TestClient

tmp = Path(__file__).parent / "data_r5"
shutil.rmtree(tmp, ignore_errors=True)
settings, store, engine = make(tmp)
app = create_app(settings=settings, store=store, engine=engine)
case, source = seed_case_with_source(store)
run = engine.runs.create_run(case["id"], "FULL_CREDIT", "screen", "analyst", provider_identity=engine._provider_identity)
engine.runs.finalize_failure(run["id"], "TEST", None)
client = TestClient(app, raise_server_exceptions=False)
for cursor in ["0", "99999999999999999999", "-5", "abc", "1e3"]:
    try:
        with client.stream("GET", f"/api/runs/{run['id']}/events", headers={"last-event-id": cursor}) as r:
            body = b"".join(r.iter_bytes())
            print(f"Last-Event-ID={cursor!r}: status {r.status_code}, {len(body)} bytes, events={body.count(b'event:')}")
    except Exception as exc:
        print(f"Last-Event-ID={cursor!r}: stream raised {type(exc).__name__}: {str(exc)[:140]}")
store.close()
