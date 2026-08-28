// Pure logic for the Evidence focus artifact reader.
//
// - Frontmatter stripping mirrors strip_provider_frontmatter in
//   caos/server/caos/methodology/canonical.py: the envelope markdown carries a
//   host frontmatter block (`---` … `---`) that is identity metadata, not body.
// - Evidence-ref normalization accepts both wire shapes: deterministic payloads
//   (`caos.system_analysis.v1`) cite plain source-id strings; canonical agent
//   payloads (`caos.canonical.artifact.v1`) cite `{ source_id, block_id? }`
//   objects. Both normalize to one chip per source id.
// - Markdown sectioning is the minimal safe renderer: `## ` lines become
//   section headings, everything else stays plain text paragraphs. No HTML,
//   no markdown library.

export type NormalizedEvidenceRef = { sourceId: string; blockIds: string[] };

export type MarkdownBlock = { kind: "heading" | "paragraph"; text: string };

export function stripFrontmatter(markdown: string): string {
  if (markdown.startsWith("---\n")) {
    const end = markdown.indexOf("\n---\n", 4);
    if (end !== -1) return markdown.slice(end + "\n---\n".length);
    if (markdown.trimEnd().endsWith("\n---")) return "";
  }
  return markdown;
}

export function markdownBlocks(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  const flush = () => {
    const text = paragraph.join("\n").trim();
    if (text) blocks.push({ kind: "paragraph", text });
    paragraph = [];
  };
  for (const line of stripFrontmatter(markdown).split("\n")) {
    if (line.startsWith("## ")) {
      flush();
      const heading = line.slice("## ".length).trim();
      if (heading) blocks.push({ kind: "heading", text: heading });
    } else if (!line.trim()) {
      flush();
    } else {
      paragraph.push(line);
    }
  }
  flush();
  return blocks;
}

export function normalizeEvidenceRefs(refs: unknown): NormalizedEvidenceRef[] {
  if (!Array.isArray(refs)) return [];
  const blockIdsBySource = new Map<string, string[]>();
  for (const ref of refs) {
    if (typeof ref === "string") {
      if (ref && !blockIdsBySource.has(ref)) blockIdsBySource.set(ref, []);
      continue;
    }
    if (!ref || typeof ref !== "object") continue;
    const sourceId = (ref as { source_id?: unknown }).source_id;
    if (typeof sourceId !== "string" || !sourceId) continue;
    const blockIds = blockIdsBySource.get(sourceId) ?? [];
    const blockId = (ref as { block_id?: unknown }).block_id;
    if (typeof blockId === "string" && blockId && !blockIds.includes(blockId)) blockIds.push(blockId);
    blockIdsBySource.set(sourceId, blockIds);
  }
  return [...blockIdsBySource.entries()].map(([sourceId, blockIds]) => ({ sourceId, blockIds }));
}

// Flatten/display pattern for pinned tabular inputs (CP-3 loan universe),
// following DeliverableDocument's DataTable flattening.
export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "number") return Number.isFinite(value) ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 20 }).format(value) : "Unavailable";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

export function flattenValue(value: unknown, prefix = ""): { label: string; value: unknown }[] {
  if (!value || typeof value !== "object") return [{ label: prefix || "Value", value }];
  if (Array.isArray(value)) return value.flatMap((item, index) => flattenValue(item, `${prefix || "Item"} / ${index + 1}`));
  return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) => {
    const label = prefix ? `${prefix} / ${key}` : key;
    return item && typeof item === "object" ? flattenValue(item, label) : [{ label, value: item }];
  });
}
