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

/** The server-frozen publication document (Task 10): masthead, pages of
 * canonical sections (opinion first, then the pathway's sections, then the
 * Evidence & QA Control Sheet) and disclosures. Markdown, PDF, XLSX and this
 * component all draw exactly this structure. */
export type PublicationMasthead = {
  issuer: string; case_name: string; case_id: string; report_type: string; pathway: string; deliverable_id: string;
  draft_version: number; draft_digest: string; input_fingerprint: string; as_of_date: string; run_id: string;
  accepted_snapshot_id: string; source_set: string; model_identity: string; methodology_build_id: string;
  machine_assistance: string; approval_state: string; watermark: string; opinion_owner: string; opinion_signed_at: string;
  opinion_id: string; renderer_version: string;
};
export type PublicationPage = { name: string; sections: DocumentSection[] };
export type Publication = {
  schema_version: string;
  masthead: PublicationMasthead;
  pages: PublicationPage[];
  disclosures: Record<string, unknown>;
};
export type FrozenOpinion = {
  opinion_id: string; opinion_digest: string; signed_by: string; signed_at: string; opinion: string; limitations: string;
  material_overrides: string; rationale: string; binding: Record<string, unknown>; supersedes_opinion_id: string | null;
};
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
  opinion?: FrozenOpinion | null;
  publication?: Publication | null;
  input_fingerprint: string;
  preview_digest: string;
};

const MASTHEAD_FACTS: [string, keyof PublicationMasthead][] = [
  ["As-of date", "as_of_date"],
  ["Deliverable", "deliverable_id"],
  ["Accepted run", "run_id"],
  ["Source set", "source_set"],
  ["Model identity", "model_identity"],
  ["Methodology build", "methodology_build_id"],
  ["Machine assistance", "machine_assistance"],
  ["Opinion owner", "opinion_owner"],
  ["Approval state", "approval_state"],
];

function SectionHeading({ section }: { section: DocumentSection }) {
  const authority = section.origin.kind === "ANALYST"
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
  publication,
}: {
  title: string;
  issuer: string;
  pathwayLabel: string;
  status: string;
  version?: number;
  digest?: string;
  sections: DocumentSection[];
  publication?: Publication | null;
}) {
  // A frozen or filed record draws the server-frozen publication; a draft
  // draws its canonical sections grouped by page. Never both.
  const pages: PublicationPage[] = publication ? publication.pages : groupDocumentPages(sections);
  const masthead = publication?.masthead ?? null;
  const heading = masthead ? `${masthead.issuer} — ${masthead.report_type}` : issuer || title;
  const subtitle = masthead ? `${masthead.report_type} · Draft v${masthead.draft_version} · ${masthead.deliverable_id}` : `${title}${version ? ` · Draft v${version}` : ""}`;
  const watermark = masthead?.watermark ?? null;
  return <article className="paper report-paper deliverable-document rd-paper" aria-label={`${status} Deliverable preview`}>
    {pages.length ? pages.map((page, pageIndex) => <section className="rd-page-container" aria-labelledby={`document-page-${pageIndex}`} key={page.name}>
      {watermark ? <div className="rd-wm" aria-hidden="true"><span>{watermark}</span></div> : null}
      <header className="rd-mast">
        <span className="rd-mast-brand"><span className="rd-mark" aria-hidden="true">C</span><span>CAOS · {pathwayLabel} · {page.name}</span></span>
        <span className="rd-mast-meta">{masthead ? masthead.approval_state : status} · PAGE {pageIndex + 1} OF {pages.length}</span>
      </header>
      {pageIndex === 0 ? <>
        <h2 className="rd-title" id={`document-page-${pageIndex}`}>{heading}</h2>
        <p className="rd-subtitle">{subtitle}</p>
        {masthead ? <dl className="rd-masthead-facts" aria-label="Publication masthead">{MASTHEAD_FACTS.map(([label, key]) => <div key={key}><dt>{label}</dt><dd>{String(masthead[key])}</dd></div>)}</dl> : null}
        {digest ? <p className="rd-identity mono" title={digest}>Exact identity · {digest}</p> : null}
      </> : <h2 className="visually-hidden" id={`document-page-${pageIndex}`}>{page.name}</h2>}
      {masthead ? <p className="rd-band">{page.name}</p> : null}
      <div className="rd-secs">{page.sections.map((section) => <DocumentSectionView section={section} key={section.section_id} />)}</div>
      <footer className="rd-foot"><span>Generated by CAOS · governed document{masthead ? ` · ${masthead.approval_state}` : ""}</span><span>{masthead ? "Approver recorded in the detached filing receipt" : "Internal committee use only"}</span></footer>
    </section>) : <p className="rd-empty">Complete the required analyst sections to compose the governed document.</p>}
  </article>;
}
