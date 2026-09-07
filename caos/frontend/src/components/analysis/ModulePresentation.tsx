import Link from "next/link";
import ArtifactMarkdown from "../ArtifactMarkdown";
import ChartExhibit from "../charts/ChartExhibit";
import type { ModulePresentationResponse } from "../../lib/api";
import type { NormalizedEvidenceRef } from "../../lib/artifactReader";
import { withQuery } from "../../lib/workbench";
import type { DocumentLeafSection, DocumentSection } from "../report/documentTypes";

function PresentationTable({ title, columns, rows }: { title: string; columns: string[]; rows: string[][] }) {
  return <div className="module-presentation-table" role="region" aria-label={`${title} table`} tabIndex={0}>
    <table><caption className="visually-hidden">{title}</caption><thead><tr>{columns.map((column, index) => <th scope="col" key={`${column}:${index}`}>{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => cellIndex === 0 ? <th scope="row" key={cellIndex}>{cell}</th> : <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody></table>
  </div>;
}

function SectionSources({ section, caseId, evidenceRefs }: { section: DocumentLeafSection; caseId: string; evidenceRefs: NormalizedEvidenceRef[] }) {
  const links = evidenceRefs.flatMap((ref) => ref.blockIds
    .filter((blockId) => section.origin.block_ids.includes(blockId))
    .map((blockId) => ({ sourceId: ref.sourceId, blockId })));
  return links.length ? <nav className="module-presentation-sources" aria-label={`${section.title} sources`}><span>Sources</span>{links.map(({ sourceId, blockId }) => <Link href={withQuery("/sources/", { case: caseId, source: sourceId, block: blockId })} key={`${sourceId}:${blockId}`}>{sourceId} · {blockId}</Link>)}</nav> : null;
}

function StructuredLeaf({ section, caseId, evidenceRefs }: { section: DocumentLeafSection; caseId: string; evidenceRefs: NormalizedEvidenceRef[] }) {
  if (section.kind === "chart" || section.kind === "text") return null;
  return <section className="module-presentation-section" data-section-id={section.section_id}>
    <header><h3>{section.title}</h3><span title={`Authority ${section.origin.authority_id}`}>{section.origin.kind === "ANALYST" ? "Analyst judgment" : `Locked · ${section.origin.kind.toLowerCase()}`}</span></header>
    {section.kind === "table" ? <><PresentationTable title={section.title} columns={section.columns} rows={section.rows} />{section.note ? <p className="muted">{section.note}</p> : null}</>
      : section.kind === "profile" ? <dl>{section.rows.map((row, index) => <div key={`${row.label}:${index}`}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl>
        : <ul>{section.items.map((item, index) => <li key={index}>{item}</li>)}</ul>}
    <SectionSources section={section} caseId={caseId} evidenceRefs={evidenceRefs} />
  </section>;
}

function structuredSections(sections: DocumentSection[]) {
  return sections.flatMap((section) => section.kind === "columns"
    ? section.items.flat().filter((item) => item.kind !== "chart" && item.kind !== "text")
    : section.kind !== "chart" && section.kind !== "text" ? [section] : []);
}

function chartSections(sections: DocumentSection[]) {
  return sections.flatMap((section) => section.kind === "columns"
    ? section.items.flat().filter((item) => item.kind === "chart")
    : section.kind === "chart" ? [section] : []);
}

export default function ModulePresentation({ presentation, caseId, markdown, evidenceRefs = [] }: {
  presentation: ModulePresentationResponse;
  caseId: string;
  markdown?: string | null;
  evidenceRefs?: NormalizedEvidenceRef[];
}) {
  const charts = chartSections(presentation.sections);
  const structured = structuredSections(presentation.sections);
  const narratives = presentation.sections.flatMap((section) => section.kind === "text" ? [section] : []);
  return <div className="module-presentation" data-presentation-artifact={presentation.artifact_id}>
    {charts.length ? <section className="module-presentation-group" aria-labelledby="visual-analysis-heading"><div className="module-presentation-heading"><span>Exhibits</span><h3 id="visual-analysis-heading">Visual analysis</h3></div>{charts.map((chart) => <ChartExhibit section={chart} theme="workspace" caseId={caseId} evidenceRefs={evidenceRefs} key={chart.section_id} />)}</section> : null}
    {structured.length ? <section className="module-presentation-group" aria-labelledby="structured-analysis-heading"><div className="module-presentation-heading"><span>Accepted detail</span><h3 id="structured-analysis-heading">Structured analysis</h3></div>{structured.map((section) => <StructuredLeaf section={section} caseId={caseId} evidenceRefs={evidenceRefs} key={section.section_id} />)}</section> : null}
    {!markdown ? narratives.map((section) => <details className="module-presentation-raw" data-section-id={section.section_id} key={section.section_id}><summary>{section.title}</summary><div className="analysis-copy"><ArtifactMarkdown markdown={section.body} /></div></details>) : null}
    {markdown ? <details className="module-presentation-raw"><summary>Complete accepted module document</summary><div className="analysis-copy"><ArtifactMarkdown markdown={markdown} /></div></details> : null}
    {presentation.unavailable.length ? <details className="module-presentation-unavailable"><summary>{presentation.unavailable.length} mapped view{presentation.unavailable.length === 1 ? "" : "s"} retained as table or unavailable</summary><ul>{presentation.unavailable.map((item) => <li key={`${item.view_id}:${item.code}`}><span>{item.view_id}</span><span>{item.code.replaceAll("_", " ").toLowerCase()}</span></li>)}</ul></details> : null}
  </div>;
}
