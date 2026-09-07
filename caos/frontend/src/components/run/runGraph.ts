export type GraphInput = { module_id: string; stage: number; dependencies: string[] };
export type GraphPoint = { x: number; y: number };

export function runGraph<T extends GraphInput>(nodes: T[]) {
  const ids = new Set<string>();
  for (const node of nodes) {
    if (ids.has(node.module_id)) throw new Error("RUN_GRAPH_INVALID");
    ids.add(node.module_id);
  }
  const stages = new Map<number, T[]>();
  const edges: [string, string][] = [];
  for (const node of nodes) {
    if (!Number.isInteger(node.stage) || node.stage < 0) throw new Error("RUN_GRAPH_INVALID");
    const stage = stages.get(node.stage);
    if (stage) stage.push(node);
    else stages.set(node.stage, [node]);
    for (const dependency of node.dependencies) {
      if (!ids.has(dependency) || dependency === node.module_id) throw new Error("RUN_GRAPH_INVALID");
      edges.push([dependency, node.module_id]);
    }
  }
  return { stages: [...stages.entries()].sort(([a], [b]) => a - b), edges };
}

export function runEdgePath(from: GraphPoint, to: GraphPoint, stageDistance: number, laneY: number) {
  if (Math.abs(stageDistance) === 1) {
    const midpoint = from.x + (to.x - from.x) / 2;
    return `M ${from.x} ${from.y} C ${midpoint} ${from.y}, ${midpoint} ${to.y}, ${to.x} ${to.y}`;
  }
  const departure = from.x + Math.sign(to.x - from.x || 1) * 12;
  const approach = to.x - Math.sign(to.x - from.x || 1) * 12;
  return `M ${from.x} ${from.y} H ${departure} V ${laneY} H ${approach} V ${to.y} H ${to.x}`;
}
