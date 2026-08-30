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
export type WorkflowId = "overview" | "sources" | "analyse" | "compare" | "model" | "publish";

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
  { id: "overview", label: "Command Center", href: "/command-center", destinations: ["Cases", "Command Center"], tools: [{ label: "Cases", href: "/cases", destination: "Cases" }] },
  { id: "sources", label: "Sources", href: "/sources", destinations: ["Sources"] },
  { id: "analyse", label: "Deep-Dive", href: "/deep-dive", destinations: ["Run Console", "Deep-Dive"], tools: [{ label: "Run Console", href: "/run-console", destination: "Run Console" }, { label: "Deep-Dive", href: "/deep-dive", destination: "Deep-Dive" }] },
  { id: "compare", label: "RV Screener", href: "/rv-screener", destinations: ["RV Screener"] },
  { id: "model", label: "Model Builder", href: "/model-builder", destinations: ["Model Builder"] },
  { id: "publish", label: "Report Studio", href: "/report-studio", destinations: ["Report Studio"] },
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

// Source-block locators arrive as small JSON objects; today's ingestion emits
// `{"line": n}` only. The two positional shapes read as English; every other shape
// keeps the compact JSON, so an unrecognised locator is shown, never dropped.
export function formatBlockLocator(locator: unknown): string {
  const json = JSON.stringify(locator) ?? "";
  if (!locator || typeof locator !== "object" || Array.isArray(locator)) return json;
  const entries = Object.entries(locator as Record<string, unknown>);
  if (entries.length !== 1) return json;
  const [key, value] = entries[0];
  const name = key.toLowerCase();
  const readable = name === "line" || name === "page";
  const positional = typeof value === "number" ? Number.isFinite(value) : typeof value === "string" && value.trim() !== "";
  return readable && positional ? `${name} ${value}` : json;
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
