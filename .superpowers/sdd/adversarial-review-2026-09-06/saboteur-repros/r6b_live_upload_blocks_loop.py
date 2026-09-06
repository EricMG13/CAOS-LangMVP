"""Live server on :8801. Does a heavy (but admissible) XLSX upload stall the event loop?"""
import time, threading
from pathlib import Path
import httpx

BASE = "http://127.0.0.1:8801"
H = {"x-caos-role": "ANALYST"}
c = httpx.Client(base_url=BASE, headers=H, timeout=300)
cid = c.post("/api/cases", json={"name": "Heavy", "issuer": "Issuer Heavy", "sector": "S"}).json()["id"]
content = (Path(__file__).parent / "heavy_12000.xlsx").read_bytes()
outcome = {}


def upload():
    t0 = time.monotonic()
    r = c.post(f"/api/cases/{cid}/sources", files={"file": ("heavy.xlsx", content, "application/octet-stream")})
    outcome["status"] = r.status_code
    outcome["seconds"] = round(time.monotonic() - t0, 2)
    outcome["blocks"] = len(r.json().get("blocks", [])) if r.status_code == 201 else r.text[:120]


probe = httpx.Client(base_url=BASE, timeout=1.0)
latencies, timeouts = [], 0
t = threading.Thread(target=upload)
t.start()
time.sleep(0.3)   # let the request body land
while t.is_alive():
    t0 = time.monotonic()
    try:
        probe.get("/api/health")
        latencies.append(time.monotonic() - t0)
    except httpx.TimeoutException:
        timeouts += 1
        latencies.append(1.0)
    time.sleep(0.05)
t.join()
print("upload outcome:", outcome)
print(f"/api/health probes during the upload: {len(latencies)}; max latency {max(latencies):.2f}s; "
      f"probes over 0.5s: {sum(1 for l in latencies if l >= 0.5)}; probes that hit the 1s client timeout: {timeouts}")
# baseline once the loop is free
t0 = time.monotonic(); probe.get("/api/health"); print(f"/api/health after the upload: {time.monotonic() - t0:.3f}s")
