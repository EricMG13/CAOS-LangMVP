export type DocumentOrigin = {
  kind: "ARTIFACT" | "MODEL" | "ANALYST" | "SYSTEM";
  authority_id: string;
  block_ids: string[];
};

type DocumentSectionBase = {
  section_id: string;
  title: string;
  page: string;
  editable: boolean;
  origin: DocumentOrigin;
};

export type DocumentTextSection = DocumentSectionBase & { kind: "text"; body: string };
export type DocumentProfileSection = DocumentSectionBase & { kind: "profile"; rows: { label: string; value: string }[] };
export type DocumentTableSection = DocumentSectionBase & { kind: "table"; columns: string[]; rows: string[][]; note: string | null };
export type DocumentListSection = DocumentSectionBase & { kind: "list"; items: string[] };
export type DocumentChartSection = DocumentSectionBase & { kind: "chart"; recipe: Record<string, unknown>; accessible_columns: string[]; accessible_rows: string[][] };
export type DocumentLeafSection = DocumentTextSection | DocumentProfileSection | DocumentTableSection | DocumentListSection | DocumentChartSection;
export type DocumentColumnsSection = DocumentSectionBase & { kind: "columns"; items: DocumentLeafSection[][] };
export type DocumentSection = DocumentLeafSection | DocumentColumnsSection;

export type DocumentPage = { name: string; sections: DocumentSection[] };

export function groupDocumentPages(sections: DocumentSection[]): DocumentPage[] {
  const pages = new Map<string, DocumentSection[]>();
  for (const section of sections) {
    const page = pages.get(section.page);
    if (page) page.push(section);
    else pages.set(section.page, [section]);
  }
  return [...pages].map(([name, pageSections]) => ({ name, sections: pageSections }));
}

export function draftTextSections(
  blocks: { kind: string; block_id: string; text?: string }[],
  templateBlocks: { block_id: string; title: string }[],
): DocumentSection[] {
  const titles = new Map(templateBlocks.map((block) => [block.block_id, block.title]));
  return blocks.flatMap((block): DocumentSection[] => block.kind === "NARRATIVE" ? [{
    kind: "text",
    section_id: block.block_id,
    title: titles.get(block.block_id) || "Analyst Narrative",
    page: "Draft",
    editable: true,
    origin: { kind: "ANALYST", authority_id: block.block_id, block_ids: [] },
    body: block.text || "Not yet drafted.",
  }] : []);
}

export function canEditDocumentSection(section: DocumentLeafSection): section is DocumentTextSection {
  return section.kind === "text" && section.editable && section.origin.kind === "ANALYST";
}

export function overlayAnalystText(
  sections: DocumentSection[],
  blocks: { kind: string; block_id: string; text?: string }[],
): DocumentSection[] {
  const textByBlock = new Map<string, string>();
  for (const block of blocks) {
    if (block.kind === "NARRATIVE" && typeof block.text === "string") {
      textByBlock.set(block.block_id, block.text);
    }
  }
  const overlay = (section: DocumentLeafSection): DocumentLeafSection => {
    if (!canEditDocumentSection(section)) return section;
    const body = textByBlock.get(section.origin.authority_id);
    return body === undefined ? section : { ...section, body: body || "Not yet drafted." };
  };
  return sections.map((section) => section.kind === "columns"
    ? { ...section, items: section.items.map((column) => column.map(overlay)) }
    : overlay(section));
}
