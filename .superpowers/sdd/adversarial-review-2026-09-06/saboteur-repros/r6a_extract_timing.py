import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from openpyxl import Workbook
from caos.sources.domain import extract_blocks
from fastapi import HTTPException

rows = int(sys.argv[1]) if len(sys.argv) > 1 else 12_000
out = Path(__file__).parent / f"heavy_{rows}.xlsx"
if not out.exists():
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("marks")
    for r in range(rows):
        ws.append([f"r{r}c{c}" for c in range(64)])
    wb.save(out)
content = out.read_bytes()
print("xlsx bytes:", len(content), "rows:", rows)
t0 = time.monotonic()
try:
    blocks = extract_blocks(out.name, content)
    print(f"extract_blocks took {time.monotonic() - t0:.1f}s on the calling thread; blocks = {len(blocks)}")
except HTTPException as exc:
    print(f"extract_blocks REFUSED after {time.monotonic() - t0:.1f}s of work on the calling thread: {exc.detail}")
