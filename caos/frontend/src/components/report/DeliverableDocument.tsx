import type { ReactNode } from "react";

import {
  groupDocumentPages,
  type DocumentChartSection,
  type DocumentLeafSection,
  type DocumentSection,
  type DocumentTableSection,
} from "./documentTypes";

export type EvidenceCitation = { source_id: string; block_ids: string[]; claim: string };
export type NarrativeBlock = { kind: "NARRATIVE"; block_id: string; slot_id: string; text: string; content_mode: "EVIDENCE" | "ANALYST_JUDGMENT"; citations: EvidenceCitation[] };
export type EvidenceRegisterBlock = { kind: "EVIDENCE_REGISTER"; block_id: string; slot_id: string; citations: EvidenceCitation[] };
export type LimitationsBlock = { kind: "LIMITATIONS"; block_id: string; slot_id: string; text: string; citations: EvidenceCitation[] };
export type GeneratedMetricBlock = { kind: "GENERATED_METRIC"; block_id: string; slot_id: string; metric_ids: string[] };
export type GeneratedTableBlock = { kind: "GENERATED_TABLE"; block_id: string; slot_id: string; table_id: string; field_ids: string[] };
export type GeneratedChartBlock = { kind: "GENERATED_CHART"; block_id: string; slot_id: string; recipe: Record<string, unknown> };
export type ScenarioExhibitBlock = { kind: "SCENARIO_EXHIBIT"; block_id: string; slot_id: string; title: string; shocks: Record<string, unknown>[]; scenario: Record<string, unknown>; scenario_digest: string };
export type ModelAppendixBlock = { kind: "MODEL_APPENDIX"; block_id: string; slot_id: string };
export type DeliverableBlock = NarrativeBlock | EvidenceRegisterBlock | LimitationsBlock | GeneratedMetricBlock | GeneratedTableBlock | GeneratedChartBlock | ScenarioExhibitBlock | ModelAppendixBlock;

export type TemplateBlock = { block_id: string; slot_id: string; kind: string; title: string; required: boolean; order: number };
export type FrozenPayload = {
  schema_version: string;
  case_id: string;
  pathway: string;
  draft: { id: string; version: number; digest: string };
  template: { title: string; template_id: string; template_version: string };
  authority: { accepted_snapshot_id?: string | null; accepted_snapshot_digest?: string | null; source_set_id?: string | null; source_set_digest?: string | null };
  model: Record<string, unknown> | null;
  content: {
    model_selection: Record<string, unknown> | null;
    model_identity?: Record<string, unknown> | null;
    blocks: DeliverableBlock[];
    generated_blocks: Record<string, unknown>;
    document_schema_version?: string | null;
    document_sections?: DocumentSection[] | null;
  };
  evidence: { source_id?: string; sha256?: string; block_ids?: string[]; withdrawn?: boolean }[];
  methodology: Record<string, unknown>;
  renderer: Record<string, unknown>;
  input_fingerprint: string;
  preview_digest: string;
};

function SectionHeading({ section }: { section: DocumentSection }) {
  const authority = section.editable && section.origin.kind === "ANALYST"
    ? "Analyst judgment"
    : `Locked · ${section.origin.kind.toLowerCase()}`;
  return <h3 className="rd-h">
    <span>{section.title}</span>
    <span className="rd-h-sub" title={`Authority ${section.origin.authority_id}`}>{authority}</span>
  </h3>;
}

function DocumentTableBody({ columns, rows, title }: { columns: string[]; rows: string[][]; title: string }) {
  return <div className="rd-table-wrap" role="region" aria-label={`${title} table`} tabIndex={0}>
    <table className="rd-table">
      <caption className="visually-hidden">{title}</caption>
      <thead><tr>{columns.map((column, index) => <th key={`${column}:${index}`} scope="col">{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => cellIndex === 0
        ? <th key={cellIndex} scope="row">{cell}</th>
        : <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

function DocumentTable({ section }: { section: DocumentTableSection }) {
  return <section className="rd-sec" data-section-id={section.section_id}>
    <SectionHeading section={section} />
    <DocumentTableBody columns={section.columns} rows={section.rows} title={section.title} />
    {section.note ? <p className="rd-note">{section.note}</p> : null}
  </section>;
}

function DocumentChart({ section }: { section: DocumentChartSection }) {
  return <section className="rd-sec" data-section-id={section.section_id}>
    <SectionHeading section={section} />
    <p className="rd-chart-label">Chart exhibit · authoritative data table</p>
    <DocumentTableBody columns={section.accessible_columns} rows={section.accessible_rows} title={`${section.title} chart data`} />
  </section>;
}

function DocumentLeaf({ section }: { section: DocumentLeafSection }): ReactNode {
  if (section.kind === "table") return <DocumentTable section={section} />;
  if (section.kind === "chart") return <DocumentChart section={section} />;

  let body: ReactNode;
  if (section.kind === "profile") {
    body = <dl className="rd-profile">{section.rows.map((row, index) => <div className="rd-prow" key={`${row.label}:${index}`}><dt className="rd-plbl">{row.label}</dt><dd>{row.value}</dd></div>)}</dl>;
  } else if (section.kind === "list") {
    body = <ul className="rd-list">{section.items.map((item, index) => <li key={index}>{item}</li>)}</ul>;
  } else {
    body = <p className="rd-body">{section.body}</p>;
  }

  return <section className="rd-sec" data-section-id={section.section_id}>
    <SectionHeading section={section} />
    {body}
  </section>;
}

function DocumentSectionView({ section }: { section: DocumentSection }) {
  if (section.kind !== "columns") return <DocumentLeaf section={section} />;
  return <section className="rd-sec" data-section-id={section.section_id}>
    <SectionHeading section={section} />
    <div className={`rd-cols rd-cols-${section.items.length}`}>{section.items.map((column, index) => <div className="rd-col" key={index}>{column.map((item) => <DocumentLeaf section={item} key={item.section_id} />)}</div>)}</div>
  </section>;
}

export default function DeliverableDocument({
  title,
  issuer,
  pathwayLabel,
  status,
  version,
  digest,
  sections,
}: {
  title: string;
  issuer: string;
  pathwayLabel: string;
  status: string;
  version?: number;
  digest?: string;
  sections: DocumentSection[];
}) {
  const pages = groupDocumentPages(sections);
  return <article className="paper report-paper deliverable-document rd-paper" aria-label={`${status} Deliverable preview`}>
    {pages.length ? pages.map((page, pageIndex) => <section className="rd-page-container" aria-labelledby={`document-page-${pageIndex}`} key={page.name}>
      <header className="rd-mast">
        <span className="rd-mast-brand"><span className="rd-mark" aria-hidden="true">C</span><span>CAOS · {pathwayLabel} · {page.name}</span></span>
        <span className="rd-mast-meta">{status} · PAGE {pageIndex + 1} OF {pages.length}</span>
      </header>
      {pageIndex === 0 ? <><h2 className="rd-title" id={`document-page-${pageIndex}`}>{issuer || title}</h2><p className="rd-subtitle">{title}{version ? ` · Draft v${version}` : ""}</p>{digest ? <p className="rd-identity mono" title={digest}>Exact identity · {digest}</p> : null}</> : <h2 className="visually-hidden" id={`document-page-${pageIndex}`}>{page.name}</h2>}
      <div className="rd-secs">{page.sections.map((section) => <DocumentSectionView section={section} key={section.section_id} />)}</div>
      <footer className="rd-foot"><span>Generated by CAOS · governed document</span><span>Internal committee use only</span></footer>
    </section>) : <p className="rd-empty">Complete the required analyst sections to compose the governed document.</p>}
  </article>;
}
