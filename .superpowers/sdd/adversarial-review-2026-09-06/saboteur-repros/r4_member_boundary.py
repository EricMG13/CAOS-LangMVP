import sys, shutil, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from fastapi.testclient import TestClient

tmp = Path(__file__).parent / "data_r4"
shutil.rmtree(tmp, ignore_errors=True)
settings, store, engine = make(tmp)
app = create_app(settings=settings, store=store, engine=engine)
client = TestClient(app)
case = client.post("/api/cases", json={"name": "C", "issuer": "I", "sector": "S"}, headers={"x-caos-role": "ANALYST"}).json()
store.add_member(case["id"], "analyst", "analyst", "APPROVER", actor_role="ADMIN")
probes = [
    ("control byte NUL", "mallory\x00x"),
    ("bidi override RLO", "mallory‮gnip"),
    ("NFD (decomposed e-acute)", "Amélie"),
]
for label, subject in probes:
    r = client.post(f"/api/cases/{case['id']}/members", json={"subject": subject, "role": "READER"},
                    headers={"x-caos-role": "APPROVER"})
    body = r.json()
    print(label, "->", r.status_code,
          "stored members:" if r.status_code == 201 else "detail:",
          [repr(m) for m in body.get("members", {})] if r.status_code == 201 else body)
# raw lone-surrogate escape (httpx cannot encode the raw character; send bytes)
r = client.post(f"/api/cases/{case['id']}/members", content=b'{"subject": "\\ud800mallory", "role": "READER"}',
                headers={"x-caos-role": "APPROVER", "content-type": "application/json"})
print("lone surrogate ->", r.status_code, r.text[:200])
ev = [e for e in store.audit_trail() if e["action"] == "case.member_added"]
print("audit rows for case.member_added carry member =", [repr(e["member"]) for e in ev])
print("audit chain findings:", store.verify_audit_chain())
# the same bare-str field on the case wire: does the case list serve the control byte back?
r = client.get(f"/api/cases/{case['id']}", headers={"x-caos-role": "ANALYST"})
print("GET case members served:", [repr(m) for m in r.json()["members"]])
store.close()
