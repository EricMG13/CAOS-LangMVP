import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from harness import *
from caos.sources.domain import pack_blocks, MAX_SOURCE_TEXT, MAX_BLOCK_CHARS
from caos.engine.budget import MAX_MANIFEST_BLOCKS, bound_manifest
from caos.engine.provider import AgentError

# 12 MB document whose lines are 10,001 chars (just over half of MAX_BLOCK_CHARS)
line = "x" * 10_001
text = "\n".join([line] * (MAX_SOURCE_TEXT // (len(line) + 1)))
print("text chars:", len(text), "<= MAX_SOURCE_TEXT:", len(text) <= MAX_SOURCE_TEXT)
blocks = pack_blocks(text)
print("blocks for one 12 MB document:", len(blocks), "(docstring: at most", MAX_SOURCE_TEXT // MAX_BLOCK_CHARS, "for any shape)")
# a natural shape: 1.3 MB with 2,100-char paragraphs on single lines
para = "y" * 2_100
text2 = "\n".join([para] * 620)
b2 = pack_blocks(text2)
print("blocks for a 1.3 MB document of 2,100-char lines:", len(b2), "(MAX_BLOCKS_PER_SOURCE switch point = 320)")


def manifest_for(n):
    return [{"source_id": f"src-{i}", "sha256": "0" * 64, "filename": "ca.txt", "media_type": "text/plain",
             "blocks": [{"block_id": b["block_id"], "locator": b["locator"], "extractor_version": b["extractor_version"],
                         "confidence": b["confidence"]} for b in blocks]} for i in range(n)]


for n in (3, 2):
    try:
        bound_manifest(manifest_for(n))
        print(f"bound_manifest accepted {n} such 12 MB documents")
    except AgentError as exc:
        print(f"bound_manifest refused {n} such 12 MB documents: {exc.code} | rows = {n * (1 + len(blocks))} > MAX_MANIFEST_BLOCKS = {MAX_MANIFEST_BLOCKS}")
