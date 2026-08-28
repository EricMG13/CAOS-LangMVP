import assert from "node:assert/strict";
import test from "node:test";
import { flattenValue, markdownBlocks, normalizeEvidenceRefs, stripFrontmatter } from "./artifactReader.ts";

const canonicalMarkdown = [
  "---",
  "module_id: CP-1",
  'run_id: "run_1"',
  'issuer_id: "iss_1"',
  'reporting_period: "FY2025"',
  "---",
  "",
  "## Audit Summary",
  "",
  "Leverage remains within covenant headroom.",
  "Liquidity is adequate through FY2026.",
  "",
  "## Analysis",
  "",
  "### Sub-heading stays body text",
  "Line one.",
  "",
  "Line two.",
  "",
].join("\n");

test("stripFrontmatter removes the host frontmatter block and keeps the body", () => {
  const body = stripFrontmatter(canonicalMarkdown);
  assert.ok(body.startsWith("\n## Audit Summary"));
  assert.ok(!body.includes("module_id: CP-1"));
});

test("stripFrontmatter returns empty for an unterminated frontmatter-only document", () => {
  assert.equal(stripFrontmatter("---\nmodule_id: CP-1\n---"), "");
});

test("stripFrontmatter passes through markdown without frontmatter", () => {
  assert.equal(stripFrontmatter("## Audit Summary\n\nBody."), "## Audit Summary\n\nBody.");
  assert.equal(stripFrontmatter("---\nno terminator, keeps everything"), "---\nno terminator, keeps everything");
});

test("markdownBlocks splits ## sections into headings and paragraphs", () => {
  const blocks = markdownBlocks(canonicalMarkdown);
  assert.deepEqual(blocks, [
    { kind: "heading", text: "Audit Summary" },
    { kind: "paragraph", text: "Leverage remains within covenant headroom.\nLiquidity is adequate through FY2026." },
    { kind: "heading", text: "Analysis" },
    { kind: "paragraph", text: "### Sub-heading stays body text\nLine one." },
    { kind: "paragraph", text: "Line two." },
  ]);
});

test("normalizeEvidenceRefs passes string refs through and dedupes", () => {
  assert.deepEqual(normalizeEvidenceRefs(["src-1", "src-2", "src-1", ""]), [
    { sourceId: "src-1", blockIds: [] },
    { sourceId: "src-2", blockIds: [] },
  ]);
});

test("normalizeEvidenceRefs maps object refs to source ids, deduping and collecting block ids", () => {
  assert.deepEqual(normalizeEvidenceRefs([
    { source_id: "src-1", block_id: "b1" },
    { source_id: "src-1", block_id: "b2" },
    { source_id: "src-1", block_id: "b1" },
    { source_id: "src-2" },
    { source_id: "", block_id: "b9" },
    { block_id: "orphan" },
  ]), [
    { sourceId: "src-1", blockIds: ["b1", "b2"] },
    { sourceId: "src-2", blockIds: [] },
  ]);
});

test("normalizeEvidenceRefs is safe on empty and missing payloads", () => {
  assert.deepEqual(normalizeEvidenceRefs(undefined), []);
  assert.deepEqual(normalizeEvidenceRefs(null), []);
  assert.deepEqual(normalizeEvidenceRefs("src-1"), []);
  assert.deepEqual(normalizeEvidenceRefs([]), []);
});

test("flattenValue flattens the pinned loan-universe shape into labeled rows", () => {
  const rows = flattenValue({
    identity: { id: "lu_1", universe_digest: "sha256:abc" },
    rows: [{ company: "Acme", margin_bps: 425 }],
  });
  assert.deepEqual(rows, [
    { label: "identity / id", value: "lu_1" },
    { label: "identity / universe_digest", value: "sha256:abc" },
    { label: "rows / 1 / company", value: "Acme" },
    { label: "rows / 1 / margin_bps", value: 425 },
  ]);
});
