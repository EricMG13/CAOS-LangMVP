export const routeDestinations = [
  ["cases", "Cases"],
  ["sources", "Sources"],
  ["run-console", "Run Console"],
  ["deep-dive", "Deep-Dive"],
  ["rv-screener", "RV Screener"],
  ["command-center", "Command Center"],
  ["model-builder", "Model Builder"],
  ["report-studio", "Report Studio"],
  ["admin-studio", "Admin Studio"],
] as const;

export type Destination = (typeof routeDestinations)[number][1];
export type WorkflowId = "portfolio" | "credit" | "sources" | "analysis" | "market" | "model" | "report";

export type DestinationMeta = {
  kicker: string;
  title: string;
};

export const destinationMeta: Record<Destination, DestinationMeta> = {
  Cases: { kicker: "Portfolio / Surveillance", title: "Monitored credits" },
  "Command Center": { kicker: "Credit / Current state", title: "Current state and what changed" },
  Sources: { kicker: "Sources / Evidence", title: "Documents, extraction and coverage" },
  "Run Console": { kicker: "Analysis / Execution", title: "Run and acceptance" },
  "Deep-Dive": { kicker: "Analysis / Reader", title: "Accepted analysis" },
  "RV Screener": { kicker: "Market / Comparison", title: "Governed loan universe" },
  "Model Builder": { kicker: "Model / Forecast", title: "Assumptions, lineage and sign-off" },
  "Report Studio": { kicker: "Report / Publication", title: "Compose, freeze and file" },
  "Admin Studio": { kicker: "Admin / Governance", title: "Deployment capability" },
};

export type Snapshot = {
  id: string;
  digest: string;
  accepted_at: string;
  source_set_version?: number | null;
  artifacts: { id: string; module_id: string; digest: string }[];
};

export type SnapshotView = {
  accepted: Snapshot | null;
  latest_accepted: Snapshot | null;
  switch_required: boolean;
  diff?: { changed?: boolean } | null;
};

export type CaseRecord = {
  id: string;
  name: string;
  issuer: string;
  sector: string;
  source_count?: number;
  accepted_snapshot_id?: string | null;
  pathway_fit?: { fit: string; message: string };
  current_execution_id?: string | null;
  // The pathways this deployment's engine will start. Absent on a server
  // that predates the field, which means "do not narrow the offer".
  available_pathways?: string[];
  deep_research_available?: boolean;
  deep_research_unavailable_reason?: string | null;
};

export type Workflow = {
  id: WorkflowId;
  label: string;
  href: string;
  destinations: readonly Destination[];
  tools?: readonly { label: string; href: string; destination: Destination }[];
};

// One vocabulary: a rail entry is named for the destination it opens, so the label
// in the rail, the label in the command palette, and the page title are the same
// word. Ids, hrefs, destinations and the group structure are unchanged — routes are
// pinned by workbench.test.ts and the aria-current rule keys on destinations, never
// on labels.
export const workflows: readonly Workflow[] = [
  { id: "portfolio", label: "Portfolio", href: "/cases", destinations: ["Cases"] },
  { id: "credit", label: "Credit", href: "/command-center", destinations: ["Command Center"] },
  { id: "sources", label: "Sources", href: "/sources", destinations: ["Sources"] },
  { id: "analysis", label: "Analysis", href: "/deep-dive", destinations: ["Run Console", "Deep-Dive"], tools: [{ label: "Run", href: "/run-console", destination: "Run Console" }] },
  { id: "market", label: "Market", href: "/rv-screener", destinations: ["RV Screener"] },
  { id: "model", label: "Model", href: "/model-builder", destinations: ["Model Builder"] },
  { id: "report", label: "Report", href: "/report-studio", destinations: ["Report Studio"] },
];

// Human module names beside the ids. Every name is the module's own `skill_slug`
// in caos/server/caos/modules/registry.py — the registry carries no separate label
// field — and each is corroborated by the H1 of the vendored SKILL.md that slug
// names. Nothing here is invented: an id the registry does not carry a slug for
// (CP-PARSE) or does not carry at all (CP-MODEL, CP-DR) falls back to the id, and
// superseded ids are deliberately not aliased onto their absorbers, because
// MODULE_GRANULARITY.md records several of those absorptions as naming drift.
const moduleNames: Record<string, string> = {
  "CP-0": "Source Readiness",
  "CP-1": "Canonical Data Foundation",
  "CP-1A": "Business Transaction Fact Pack",
  "CP-1B": "Earnings Delta",
  "CP-1C": "Peer Benchmark",
  "CP-1D": "Earnings Quality",
  "CP-2": "Fundamental Credit Synthesizer",
  "CP-2A": "Downside Pathway",
  "CP-2E": "Macro FX Hedging Sensitivity",
  "CP-2G": "Forward Credit Model",
  "CP-2H": "Ratings Migration Trigger",
  "CP-3": "Relative Value Security Selection",
  "CP-4": "Legal Covenant Interpreter",
  "CP-4C": "Restructuring Fulcrum",
  "CP-5": "Evidence Trace Validator",
  "CP-6": "IC Debate Challenge",
  "CP-L10": "Financial Change Screen",
};

export function moduleLabel(moduleId: string): string {
  return moduleNames[moduleId.trim().toUpperCase()] || moduleId;
}

// One vocabulary for server codes too: a SCREAMING_SNAKE identifier is never
// presented to an analyst as English. Shared by the state components, the request
// helper, and every surface that shows a typed refusal beside its detail.
export function humanizeCode(code: string) {
  return code.replaceAll("_", " ");
}

// One date formatter for every surface — the topbar authority strip, the artifact
// and audit tables, the model build history — so a timestamp reads the same way
// wherever it appears.
export function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

// Source-block locators arrive as small JSON objects. Ingestion emits two shapes:
// `{"line": n}` while a document is small (`builtin-v1`) and `{"lines": [first,
// last]}` once `pack_blocks` groups lines to hold the manifest's block count down
// (`builtin-v2`) — which is every annual report and credit agreement of real size,
// so the range form is the common case, not the exotic one. Both read as English;
// every other shape keeps the compact JSON, so an unrecognised locator is shown,
// never dropped.
export function formatBlockLocator(locator: unknown): string {
  const json = JSON.stringify(locator) ?? "";
  if (!locator || typeof locator !== "object" || Array.isArray(locator)) return json;
  const entries = Object.entries(locator as Record<string, unknown>);
  if (entries.length !== 1) return json;
  const [key, value] = entries[0];
  const name = key.toLowerCase();
  const positional = (candidate: unknown) => typeof candidate === "number"
    ? Number.isFinite(candidate)
    : typeof candidate === "string" && candidate.trim() !== "";
  if ((name === "line" || name === "page") && positional(value)) return `${name} ${value}`;
  if ((name === "lines" || name === "pages") && Array.isArray(value) && value.length === 2 && value.every(positional)) {
    const [first, last] = value;
    return String(first) === String(last) ? `${name.slice(0, -1)} ${first}` : `${name} ${first}\u2013${last}`;
  }
  return json;
}

export function destinationFromSlug(slug: string): Destination {
  return routeDestinations.find(([route]) => route === slug)?.[1] ?? "Cases";
}

export function workflowFor(destination: Destination): Workflow {
  return workflows.find((workflow) => workflow.destinations.includes(destination)) ?? workflows[0];
}

export function withQuery(path: string, values: Record<string, string | undefined>) {
  const [route, rawQuery] = path.split("?");
  // `trailingSlash: true` + `output: "export"` writes each route's client payload to
  // `<route>/index.txt`. The router only requests that file when the pathname it holds
  // ends in a slash; otherwise it requests `<route>.txt`, gets a 404, and degrades the
  // transition into a full document load after it has already pushed the history entry.
  const pathname = `${route.replace(/\/$/, "")}/`;
  const query = new URLSearchParams(rawQuery);
  for (const [key, value] of Object.entries(values)) {
    if (value) query.set(key, value);
    else query.delete(key);
  }
  return `${pathname}${query.size ? `?${query}` : ""}`;
}

// Acceptance aftermath: a run's snapshot reads as the case's standing authority only
// when the id the run carries (or, on a server that does not serve it, the id its
// acceptance just returned locally) matches the authority strip's accepted snapshot.
// Returns the matched snapshot id, or "" while the accept action must stay live.
export function acceptedAuthorityMatch(
  runSnapshotId: string | null | undefined,
  localSnapshotId: string | null | undefined,
  authoritySnapshotId: string | null | undefined,
): string {
  const candidate = runSnapshotId || localSnapshotId || "";
  return candidate && candidate === authoritySnapshotId ? candidate : "";
}

export function evidenceKind(value: string): "source" | "artifact" | null {
  const id = value.trim();
  // This store issues hyphenated ids (src-…, art-…); the legacy underscore form
  // stays accepted so pasted references from ported material still resolve.
  // The tail may itself be hyphenated: a promoted analyst note is `src-note-<hex>`.
  if (/^src[-_][a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(id)) return "source";
  if (/^art[-_][a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(id)) return "artifact";
  return null;
}
