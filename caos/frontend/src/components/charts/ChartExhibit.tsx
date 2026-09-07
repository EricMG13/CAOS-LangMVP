"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { withQuery } from "../../lib/workbench";
import type { NormalizedEvidenceRef } from "../../lib/artifactReader";
import type { DocumentChartSection } from "../report/documentTypes";
import { adaptChartSection, type AdaptedChart, type ChartTheme } from "./chartRecipe";
import { startChartLifecycle } from "./chartLifecycle";

function ExactChartTable({ section }: { section: DocumentChartSection }) {
  const columns = Array.isArray(section.accessible_columns) && section.accessible_columns.every((cell) => typeof cell === "string")
    ? section.accessible_columns : null;
  const rows = Array.isArray(section.accessible_rows) && section.accessible_rows.every((row) => Array.isArray(row) && row.every((cell) => typeof cell === "string"))
    ? section.accessible_rows : null;
  if (!columns || !rows) return <p className="chart-exhibit-failure" role="alert">The chart data table is malformed and cannot be displayed.</p>;
  return <div className="chart-exhibit-table" role="region" aria-label={`${section.title} exact data table`} tabIndex={0}>
    <table>
      <caption className="visually-hidden">{section.title} exact chart data</caption>
      <thead><tr>{columns.map((column, index) => <th scope="col" key={`${column}:${index}`}>{column}</th>)}</tr></thead>
      <tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => cellIndex === 0
        ? <th scope="row" key={cellIndex}>{cell}</th>
        : <td key={cellIndex}>{cell}</td>)}</tr>)}</tbody>
    </table>
  </div>;
}

function ChartCanvas({ chart }: { chart: AdaptedChart }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    return startChartLifecycle(host, chart.options as unknown as Record<string, unknown>, setStatus);
  }, [chart]);

  return <>
    <div className="chart-exhibit-canvas" data-chart-kind={chart.kind} data-recipe-id={chart.recipeId} ref={hostRef} aria-hidden="true" />
    {status === "failed" ? <p className="chart-exhibit-failure" role="status">The chart could not be rendered; the exact data table remains available.</p>
      : status === "loading" ? <p className="chart-exhibit-loading" role="status">Loading visual…</p> : null}
  </>;
}

export default function ChartExhibit({ section, theme, caseId, evidenceRefs = [] }: {
  section: DocumentChartSection;
  theme: ChartTheme;
  caseId?: string;
  evidenceRefs?: NormalizedEvidenceRef[];
}) {
  const adapted = useMemo(() => adaptChartSection(section, theme), [section, theme]);
  return <section className={`chart-exhibit chart-exhibit-${theme}`} data-section-id={section.section_id}>
    <header className="chart-exhibit-head">
      <div>
        <p className="chart-exhibit-kicker">Visual analysis · exact table retained</p>
        <h3>{section.title}</h3>
      </div>
      <span title={`Authority ${section.origin.authority_id}`}>{section.origin.kind === "ANALYST" ? "Analyst judgment" : `Locked · ${section.origin.kind.toLowerCase()}`}</span>
    </header>
    {adapted.ok ? <>
      <div className="chart-exhibit-meta"><span>{adapted.kind.replace("_", " ")}</span><span>{adapted.unit}</span><span>{adapted.data.length} point{adapted.data.length === 1 ? "" : "s"}</span></div>
      {adapted.series.length > 1 ? <ul className="chart-exhibit-legend" aria-label="Chart series">{adapted.series.map((series, index) => <li key={series}><span className={`chart-series-${index % 8}`} aria-hidden="true" />{series}</li>)}</ul> : null}
      <ChartCanvas chart={adapted} key={JSON.stringify([theme, adapted.recipeId, adapted.kind, adapted.unit, adapted.data])} />
      {caseId && adapted.sourceIds.length ? <nav className="chart-exhibit-sources" aria-label={`${section.title} chart sources`}><span>Sources</span>{adapted.sourceIds.flatMap((sourceId) => {
        const exactBlocks = evidenceRefs.find((ref) => ref.sourceId === sourceId)?.blockIds.filter((blockId) => section.origin.block_ids.includes(blockId)) ?? [];
        return exactBlocks.length ? exactBlocks.map((blockId) => <Link href={withQuery("/sources/", { case: caseId, source: sourceId, block: blockId })} key={`${sourceId}:${blockId}`}>{sourceId} · {blockId}</Link>)
          : [<Link href={withQuery("/sources/", { case: caseId, source: sourceId })} key={sourceId}>{sourceId}</Link>];
      })}</nav> : null}
    </> : <p className="chart-exhibit-failure" role="status" data-chart-fallback={adapted.reason}>{adapted.message}</p>}
    <ExactChartTable section={section} />
  </section>;
}
