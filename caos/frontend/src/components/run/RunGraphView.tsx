"use client";

import Link from "next/link";
import { useState } from "react";
import type { RunRecord } from "../../lib/api";
import { humanizeCode, moduleLabel, nodeStatusTone, withQuery } from "../../lib/workbench";
import styles from "./RunGraph.module.css";
import { runEdgePath, runGraph } from "./runGraph";

const STAGE_WIDTH = 208;
const STAGE_GAP = 56;
const STAGE_HEADER = 38;
const NODE_HEIGHT = 96;
const NODE_GAP = 16;
const EDGE_LANE_GAP = 8;
const NODE_STATUSES = new Set(["pending", "ready", "running", "succeeded", "failed", "cancelled"]);

type RunNode = RunRecord["nodes"][number];

function ModuleIdentity({ moduleId }: { moduleId: string }) {
  const name = moduleLabel(moduleId);
  return <><strong>{name}</strong>{name === moduleId ? null : <span className={styles.moduleId}>{moduleId}</span>}</>;
}

function NodeButton({ node, selected, onSelect }: { node: RunNode; selected: boolean; onSelect: () => void }) {
  const status = NODE_STATUSES.has(node.status) ? node.status : `unknown (${node.status})`;
  const dependencies = Array.isArray(node.dependencies) ? node.dependencies : null;
  return <button className={styles.node} type="button" data-run-node-id={node.id} data-module-id={node.module_id} aria-pressed={selected} onClick={onSelect}>
    <ModuleIdentity moduleId={node.module_id} />
    <span className={`status ${nodeStatusTone(node.status)}`}>{status}</span>
    <span className={styles.visuallyHidden}>Upstream dependencies: {dependencies === null ? "unavailable" : dependencies.length ? dependencies.join(", ") : "none"}.</span>
  </button>;
}

function NodeInspector({ caseId, run, node, edges }: { caseId: string; run: RunRecord; node: RunNode; edges: [string, string][] | null }) {
  const dependencies = Array.isArray(node.dependencies) ? node.dependencies : null;
  const downstream = edges?.filter(([source]) => source === node.module_id).map(([, target]) => target);
  const researchPause = run.error?.code === "PLAN_APPROVAL_REQUIRED";
  return <section className={styles.inspector} aria-labelledby="run-node-inspector-title">
    <div className={styles.inspectorHeader}>
      <h3 id="run-node-inspector-title">Node inspector</h3>
      <span className={`status ${nodeStatusTone(node.status)}`}>{node.status}</span>
    </div>
    <dl>
      <dt>Module</dt><dd><ModuleIdentity moduleId={node.module_id} /></dd>
      <dt>Stage</dt><dd className="mono">{node.stage}</dd>
      <dt>Served status</dt><dd>{node.status}</dd>
      <dt>Upstream inputs</dt><dd>{dependencies === null ? "Unavailable" : dependencies.length ? dependencies.map(moduleLabel).join(", ") : "None"}</dd>
      <dt>Downstream consumers</dt><dd>{downstream === undefined ? "Unavailable while the dependency graph is invalid" : downstream.length ? downstream.map(moduleLabel).join(", ") : "None"}</dd>
      {run.error ? <><dt>Run-level error</dt><dd><span className="mono">{humanizeCode(run.error.code)}</span>{run.error.message ? ` · ${run.error.message}` : ""}</dd></> : null}
      {researchPause ? <><dt>Research pause</dt><dd>{run.research?.phase ? humanizeCode(run.research.phase) : "Plan approval required"}</dd></> : null}
      {run.provider_identity ? <><dt>Recorded provider</dt><dd>{run.provider_identity.provider_name} / {run.provider_identity.model}</dd></> : null}
    </dl>
    {node.artifact_id ? <Link className="button small" href={withQuery("/sources/", { case: caseId, artifact: node.artifact_id })}>Open output</Link> : <p className="muted">No output is served for this node.</p>}
  </section>;
}

export default function RunGraph({ caseId, run }: { caseId: string; run: RunRecord }) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  let graph: ReturnType<typeof runGraph<RunNode>> | null = null;
  try {
    graph = runGraph(run.nodes);
  } catch {
    // The served list is still useful, but an invalid dependency contract must
    // never be repaired in the browser with invented edges.
  }
  const selected = run.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const edges = graph?.edges ?? null;

  if (!graph) return <div className={styles.layout}>
    <div className={styles.unavailable} role="status"><strong>Dependency graph unavailable.</strong> The served node list remains available; no connections were inferred.</div>
    <ol className={styles.fallback}>{run.nodes.map((node) => <li key={node.id}><NodeButton node={node} selected={node.id === selectedNodeId} onSelect={() => setSelectedNodeId(node.id)} /></li>)}</ol>
    {selected ? <NodeInspector caseId={caseId} run={run} node={selected} edges={edges} /> : null}
  </div>;

  const positions = new Map<string, { x: number; y: number }>();
  const stageIndexes = new Map<string, number>();
  graph.stages.forEach(([, nodes], stageIndex) => nodes.forEach((node) => stageIndexes.set(node.module_id, stageIndex)));
  const routedEdgeIndexes = graph.edges.flatMap(([source, target], index) => Math.abs(stageIndexes.get(target)! - stageIndexes.get(source)!) === 1 ? [] : [index]);
  const laneByEdge = new Map(routedEdgeIndexes.map((edgeIndex, laneIndex) => [edgeIndex, 8 + laneIndex * EDGE_LANE_GAP]));
  const headerOffset = routedEdgeIndexes.length ? 16 + routedEdgeIndexes.length * EDGE_LANE_GAP : 0;
  graph.stages.forEach(([, nodes], stageIndex) => nodes.forEach((node, nodeIndex) => positions.set(node.module_id, {
    x: stageIndex * (STAGE_WIDTH + STAGE_GAP),
    y: headerOffset + STAGE_HEADER + nodeIndex * (NODE_HEIGHT + NODE_GAP),
  })));
  const maxStageSize = Math.max(1, ...graph.stages.map(([, nodes]) => nodes.length));
  const width = Math.max(STAGE_WIDTH, graph.stages.length * STAGE_WIDTH + Math.max(0, graph.stages.length - 1) * STAGE_GAP);
  const height = headerOffset + STAGE_HEADER + maxStageSize * NODE_HEIGHT + Math.max(0, maxStageSize - 1) * NODE_GAP;

  return <div className={styles.layout}>
    <div className={styles.scroller} role="region" aria-label="Run dependency graph" tabIndex={0}>
      <div className={styles.canvas} style={{ width, height }}>
        <svg className={styles.edges} width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
          <defs>
            <marker id="run-edge-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 6 3 L 0 6 Z" /></marker>
            <marker id="run-edge-arrow-selected" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 6 3 L 0 6 Z" /></marker>
          </defs>
          {graph.edges.map(([source, target], index) => {
            const from = positions.get(source)!;
            const to = positions.get(target)!;
            const x1 = from.x + STAGE_WIDTH;
            const y1 = from.y + NODE_HEIGHT / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_HEIGHT / 2;
            const selectedEdge = selected?.module_id === source || selected?.module_id === target;
            return <path className={selectedEdge ? styles.edgeSelected : undefined} markerEnd={`url(#run-edge-arrow${selectedEdge ? "-selected" : ""})`} key={`${source}:${target}:${index}`} d={runEdgePath({ x: x1, y: y1 }, { x: x2, y: y2 }, stageIndexes.get(target)! - stageIndexes.get(source)!, laneByEdge.get(index) ?? 0)} />;
          })}
        </svg>
        <ol className={styles.stages} style={{ gridTemplateColumns: `repeat(${graph.stages.length}, ${STAGE_WIDTH}px)`, columnGap: STAGE_GAP }}>
          {graph.stages.map(([stage, nodes]) => <li key={stage}>
            <section aria-labelledby={`run-stage-${stage}`} style={{ paddingTop: headerOffset }}>
              <h3 id={`run-stage-${stage}`}>Stage {stage}</h3>
              <ol>{nodes.map((node) => <li key={node.id}><NodeButton node={node} selected={node.id === selectedNodeId} onSelect={() => setSelectedNodeId(node.id)} /></li>)}</ol>
            </section>
          </li>)}
        </ol>
      </div>
    </div>
    {selected ? <NodeInspector caseId={caseId} run={run} node={selected} edges={graph.edges} /> : <p className={styles.hint}>Select a node to inspect its served inputs, consumers, status and output.</p>}
  </div>;
}
