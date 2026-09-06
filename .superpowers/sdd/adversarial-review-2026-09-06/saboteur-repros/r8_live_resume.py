"""Live server on :8801 (host_control). resume() on a RUNNING run; double accept; SSE cursor."""
import time, threading, json
import httpx

BASE = "http://127.0.0.1:8801"
H = {"x-caos-role": "ANALYST"}
c = httpx.Client(base_url=BASE, headers=H, timeout=300)
case = c.post("/api/cases", json={"name": "Live", "issuer": "Issuer Live", "sector": "S"}).json()
cid = case["id"]
r = c.post(f"/api/cases/{cid}/sources", files={"file": ("doc.txt", b"Issuer Live annual report. Revenue 1000. EBITDA 200.\n" * 20, "text/plain")})
print("upload:", r.status_code)
t_start = time.monotonic()
run = c.post(f"/api/cases/{cid}/runs", json={"pathway": "FULL_CREDIT", "depth": "screen", "focus_questions": []}).json()
rid = run["id"]
print(f"start_run returned status={run['status']} after {time.monotonic() - t_start:.2f}s")

observed = []


def watch():
    for _ in range(200):
        s = c.get(f"/api/runs/{rid}").json()["status"]
        observed.append((round(time.monotonic() - t_start, 2), s))
        if s in ("succeeded", "failed"):
            return
        time.sleep(0.25)


w = threading.Thread(target=watch)
w.start()
t0 = time.monotonic()
resumed = c.post(f"/api/runs/{rid}/resume")
t_resume = time.monotonic() - t0
w.join()
print(f"POST /resume on the running run answered {resumed.status_code} after {t_resume:.2f}s with status={resumed.json().get('status')}")
print("run status observed by a second client while /resume was in flight:", observed[:3], "...", observed[-2:])
terminal_at = next((t for t, s in observed if s in ("succeeded", "failed")), None)
print(f"run reached terminal at t={terminal_at}s after start; /resume returned at t={round(t0 - t_start + t_resume, 2)}s")

# two concurrent accepts of the same succeeded run
results = []


def accept():
    rr = c.post(f"/api/runs/{rid}/accept")
    results.append((rr.status_code, rr.json().get("id") or rr.json()))


ts = [threading.Thread(target=accept) for _ in range(2)]
[t.start() for t in ts]
[t.join() for t in ts]
print("two concurrent accepts:", results)
snap = c.get(f"/api/cases/{cid}/snapshot").json()
print("case snapshot view: accepted =", (snap.get("accepted") or {}).get("id"), "latest =", (snap.get("latest_accepted") or {}).get("id"))

# SSE tail of the terminal run with a Last-Event-ID beyond the SQLite integer range
with c.stream("GET", f"/api/runs/{rid}/events", headers={"last-event-id": "99999999999999999999"}) as s:
    body = b""
    try:
        for chunk in s.iter_bytes():
            body += chunk
        print("SSE with huge Last-Event-ID:", s.status_code, "body:", body[:80])
    except Exception as exc:
        print("SSE with huge Last-Event-ID: status", s.status_code, "then transport error", type(exc).__name__, str(exc)[:100])
with c.stream("GET", f"/api/runs/{rid}/events", headers={"last-event-id": "10000"}) as s:
    body = b"".join(s.iter_bytes())
    print("SSE with Last-Event-ID beyond head on a terminal run:", s.status_code, "bytes:", len(body), "(stream closed immediately; a browser EventSource reconnects every ~3s forever unless the client closes it)")
json.dump({"case": cid, "run": rid}, open("/private/tmp/claude-501/-Users-ericguei-Claude-Projects-CAOS-LangMVP--claude-worktrees-target-consolidation-checklist-b86b72/e6eec946-1e0b-477f-892b-7be9e9ab5e8c/scratchpad/agents/saboteur/live_ids.json", "w"))
