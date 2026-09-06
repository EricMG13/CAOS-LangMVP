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

export type MarkdownBlock = { kind: "heading" | "paragraph"; text: string }
  | { kind: "table"; text: string; headers: string[]; rows: string[][] };

function tableCells(line: string): string[] | null {
  const cells: string[] = [];
  let cell = "";
  let hasPipe = false;
  for (let index = 0; index < line.length; index += 1) {
    if (line[index] === "\\" && ["|", "\\"].includes(line[index + 1])) cell += line[++index];
    else if (line[index] === "|") { cells.push(cell.trim()); cell = ""; hasPipe = true; }
    else cell += line[index];
  }
  cells.push(cell.trim());
  if (!hasPipe) return null;
  if (!cells[0]) cells.shift();
  if (!cells.at(-1)) cells.pop();
  return cells.length > 0 && cells.length <= 64 ? cells : null;
}

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
  const lines = stripFrontmatter(markdown).split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const headers = tableCells(line);
    const separator = tableCells(lines[index + 1] ?? "");
    if (headers && separator?.length === headers.length && separator.every((value) => /^:?-{3,}:?$/.test(value))) {
      let end = index + 2;
      const rows: string[][] = [];
      while (end < lines.length && lines[end].trim()) {
        const cells = tableCells(lines[end]);
        if (!cells) break;
        rows.push(cells);
        end += 1;
      }
      const text = lines.slice(index, end).join("\n");
      flush();
      if (rows.length <= 2000 && rows.every((row) => row.length === headers.length)) blocks.push({ kind: "table", text, headers, rows });
      else blocks.push({ kind: "paragraph", text });
      index = end - 1;
      continue;
    }
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
