// Align (FE-A1 D1, DECISIONS §14.23): eight destinations plus Run, the tool of
// Analysis, with one vocabulary in URL, rail, kicker, page title and tab title —
// the slug is the destination word. Every route below is a static page.
export const routeDestinations = [
  ["portfolio", "Portfolio"],
  ["credit", "Credit"],
  ["sources", "Sources"],
  ["analysis", "Analysis"],
  ["run", "Run"],
  ["market", "Market"],
  ["model", "Model"],
  ["report", "Report"],
  ["admin", "Admin"],
] as const;

// Route compatibility (FE-A1 D2): every pre-Align slug stays a static page that
// replaces history to the destination that absorbed it, query string intact, so
// deep links in retained evidence packages keep resolving. A static export cannot
// serve a redirect, so the page forwards itself (components/RouteForwarder.tsx).
export const forwardedRoutes = [
  ["cases", "portfolio"],
  ["command-center", "credit"],
  ["deep-dive", "analysis"],
  ["run-console", "run"],
  ["rv-screener", "market"],
  ["model-builder", "model"],
  ["report-studio", "report"],
  ["admin-studio", "admin"],
] as const;

// The static route set is a pure function of the two tables above:
// generateStaticParams, the rail, the palette and the accessibility sweep read
// them and nothing else.
export const routeSlugs: readonly string[] = [...routeDestinations.map(([slug]) => slug), ...forwardedRoutes.map(([from]) => from)];

export type Destination = (typeof routeDestinations)[number][1];
export type WorkflowId = "portfolio" | "credit" | "sources" | "analysis" | "market" | "model" | "report";

export type DestinationMeta = {
  kicker: string;
  title: string;
};

export const destinationMeta: Record<Destination, DestinationMeta> = {
  Portfolio: { kicker: "Portfolio / Surveillance", title: "Monitored credits" },
  Credit: { kicker: "Credit / Current state", title: "Current state and what changed" },
  Sources: { kicker: "Sources / Evidence", title: "Documents, extraction and coverage" },
  Analysis: { kicker: "Analysis / Reader", title: "Accepted analysis" },
  Run: { kicker: "Analysis / Run", title: "Run and acceptance" },
  Market: { kicker: "Market / Comparison", title: "Governed loan universe" },
  Model: { kicker: "Model / Forecast", title: "Assumptions, lineage and sign-off" },
  Report: { kicker: "Report / Publication", title: "Compose, freeze and file" },
  Admin: { kicker: "Admin / Governance", title: "Deployment capability" },
};

export type Snapshot = {
  id: string;
  run_id?: string;
  digest: string;
  accepted_at: string;
  source_set_id?: string | null;
  source_set_version?: number | null;
  artifacts: { id: string; module_id: string; digest: string }[];
};

// Current identity and stored standing both govern privileged case actions.
export function canApproveCase(role: string, subject: string, members?: Record<string, string>): boolean {
  return Boolean(subject && ["ANALYST", "APPROVER", "ADMIN"].includes(role)
    && ["APPROVER", "ADMIN"].includes(members?.[subject] ?? ""));
}

export type SnapshotDiffEntry = { module_id: string; digest: string };
export type SnapshotDiff = {
  changed: boolean;
  added: SnapshotDiffEntry[];
  removed: SnapshotDiffEntry[];
  modified: SnapshotDiffEntry[];
  source_set_changed: boolean;
};

export type SnapshotView = {
  // The server wire calls the effective visible/pinned reader lens `accepted`.
  // It may intentionally trail the acceptance ledger after an explicit pin.
  accepted: Snapshot | null;
  // Acceptance replacement, digest comparison and accepted-run identity bind to
  // the newest ledger entry, regardless of which snapshot the reader lens shows.
  latest_accepted: Snapshot | null;
  switch_required: boolean;
  diff: SnapshotDiff | null;
};

export type CaseRecord = {
  id: string;
  name: string;
  issuer: string;
  sector: string;
  source_count?: number;
  // Stored case standing per subject (ANALYST | APPROVER | ADMIN | READER):
  // Report Studio reads it to decide whether the viewer may provision an
  // approver (Task 10); the server enforces the same rule.
  members?: Record<string, string>;
  accepted_snapshot_id?: string | null;
  pathway_fit?: { fit: string; message: string };
  current_execution_id?: string | null;
  // The pathways this deployment's engine will start. Absent on a server
  // that predates the field, which means "do not narrow the offer".
  available_pathways?: string[];
  deep_research_available?: boolean;
  deep_research_unavailable_reason?: string | null;
  // The case's latest document-first intake; the Portfolio page reads the record
  // only when this names one, never by probing for a 404.
  latest_intake_id?: string | null;
};

export type Workflow = {
  id: WorkflowId;
  label: string;
  href: string;
  destinations: readonly Destination[];
  tools?: readonly { label: string; href: string; destination: Destination }[];
};

// One vocabulary: a rail entry is named for the destination it opens, so the word
// in the URL, the rail, the command palette, the kicker and the tab title is the
// same. Every href is derived from the destination table (`routeFor`), never a
// second literal; the route table is pinned by workbench.test.ts and the
// aria-current rule keys on destinations. Admin is the governance entry the shell
// draws outside this list, at `routeFor("Admin")`.
export const workflows: readonly Workflow[] = [
  { id: "portfolio", label: "Portfolio", href: routeFor("Portfolio"), destinations: ["Portfolio"] },
  { id: "credit", label: "Credit", href: routeFor("Credit"), destinations: ["Credit"] },
  { id: "sources", label: "Sources", href: routeFor("Sources"), destinations: ["Sources"] },
  { id: "analysis", label: "Analysis", href: routeFor("Analysis"), destinations: ["Analysis", "Run"], tools: [{ label: "Run", href: routeFor("Run"), destination: "Run" }] },
  { id: "market", label: "Market", href: routeFor("Market"), destinations: ["Market"] },
  { id: "model", label: "Model", href: routeFor("Model"), destinations: ["Model"] },
  { id: "report", label: "Report", href: routeFor("Report"), destinations: ["Report"] },
];

// Human module names beside the ids. Every name is the module's own `skill_slug`
// in caos/server/caos/modules/registry.py — the registry carries no separate label
// field — and each is corroborated by the H1 of the vendored SKILL.md that slug
// names. Nothing here is invented. CP-PARSE's entry names CP-0's skill
// (`cp-0-source-readiness`), whose H1 and profile gate name the two runnable
// profiles "CP-PARSE DataPreparation" and "CP-0 SourceReadiness", so CP-PARSE
// takes the skill's own name for its profile rather than CP-0's; CP-DR's entry is
// `cp-dr-deep-research`. An id the registry does not carry at all (CP-MODEL) falls
// back to the id, and superseded ids are deliberately not aliased onto their
// absorbers, because MODULE_GRANULARITY.md records several of those absorptions
// as naming drift.
const moduleNames: Record<string, string> = {
  "CP-PARSE": "Data Preparation",
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
  "CP-DR": "Deep Research",
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

// The typed failure of a run or of its blamed node (RunErrorResponse in
// caos/server/caos/responses.py): the refusal code, the module it names (null for
// a run-level refusal) and, for the one paused state that carries prose
// (PLAN_APPROVAL_REQUIRED), a host-owned sentence — never document text.
export type RunError = { code: string; module_id?: string | null; message?: string | null };

// The sentence Run shows beside a typed failure. StateNote already prefixes the
// humanized code, so this names the blamed module by its registry name and repeats
// the host's sentence only when the server sent one — never a client-invented
// "Run exception" for a code the server typed.
export function runErrorDetail(error: RunError): string {
  const moduleId = error.module_id?.trim() || "";
  const name = moduleId ? moduleLabel(moduleId) : "";
  const blame = !moduleId
    ? "Run-level refusal; no module is blamed."
    : name === moduleId ? `Refused by ${moduleId}.` : `Refused by ${name} (${moduleId}).`;
  const message = error.message?.trim() || "";
  return message ? `${blame} ${message}` : blame;
}

// The Deep Research brief's bounds, mirrored from ResearchBrief in
// caos/server/caos/contracts.py, which is the source of truth: ten list items
// combined (each list is also capped at ten, which the combined cap implies), 200
// characters per item, 400 for the question and the decision context, 200 for the
// time horizon. The server bounds NFC code points, so the client counts the same —
// never UTF-16 units, which would refuse a legal line of astral or decomposed
// characters the server admits.
export const BRIEF_LIMITS = { listItems: 10, itemChars: 200, textChars: 400, horizonChars: 200 } as const;

function codePointLength(value: string): number {
  return [...value.normalize("NFC")].length;
}

export function researchBriefListsWithinBounds(mustAnswer: readonly string[], exclusions: readonly string[]): boolean {
  return mustAnswer.length + exclusions.length <= BRIEF_LIMITS.listItems
    && [...mustAnswer, ...exclusions].every((line) => codePointLength(line) <= BRIEF_LIMITS.itemChars);
}

// The evidence drawer shows every block the citation named and caps only the
// uncited remainder: a citation naming more blocks than the cap never loses one
// silently, and the sentence beneath the list says exactly what is shown. Cited
// blocks keep their source order ahead of the rest.
export const UNCITED_BLOCK_PREVIEW = 20;

export function evidenceBlockPreview<T extends { block_id: string }>(
  blocks: readonly T[],
  citedIds: readonly string[],
  uncitedLimit = UNCITED_BLOCK_PREVIEW,
): { blocks: T[]; citedCount: number; remaining: number; note: string | null } {
  const cited = blocks.filter((block) => citedIds.includes(block.block_id));
  const uncited = blocks.filter((block) => !citedIds.includes(block.block_id));
  const remaining = Math.max(0, uncited.length - uncitedLimit);
  const shown = cited.length
    ? `Showing the ${cited.length} cited block${cited.length === 1 ? "" : "s"} and the first ${uncitedLimit} others.`
    : `Showing the first ${uncitedLimit} blocks.`;
  return {
    blocks: [...cited, ...uncited.slice(0, uncitedLimit)],
    citedCount: cited.length,
    remaining,
    note: remaining ? `${shown} Open the full source for the remaining ${remaining} block${remaining === 1 ? "" : "s"}.` : null,
  };
}

export function compactIdentity(value: string, leading = 12, trailing = 4) {
  leading = Math.max(0, leading);
  trailing = Math.max(0, trailing);
  return value.length <= leading + trailing ? value : `${value.slice(0, leading)}…${trailing ? value.slice(-trailing) : ""}`;
}

export type DraftLinkGesture = Pick<MouseEvent, "button" | "metaKey" | "ctrlKey" | "shiftKey" | "altKey">;

export function isSameTabPrimaryGesture(event: DraftLinkGesture, target = "") {
  return event.button === 0
    && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
    && (!target || target.toLowerCase() === "_self");
}

export function resolveDraftDiscard(request: { confirm: () => void; cancel?: () => void }, confirmed: boolean) {
  if (confirmed) request.confirm();
  else request.cancel?.();
}

export function historyStateForExternalReplace(state: unknown) {
  if (!state || typeof state !== "object" || Array.isArray(state)) return {};
  const externalState = { ...(state as Record<string, unknown>) };
  delete externalState.__NA;
  delete externalState._N;
  return externalState;
}

export type DraftHistoryTraversal = {
  token: number;
  kind: "confirmed" | "retire" | "restore";
  expectedDestinationId: string;
  phase: "pending" | "observed";
};

export function beginDraftHistoryTraversal(active: DraftHistoryTraversal | null, token: number, kind: DraftHistoryTraversal["kind"], expectedDestinationId: string) {
  if (active) return { active, started: false };
  return { active: { token, kind, expectedDestinationId, phase: "pending" as const }, started: true };
}

export function finishDraftHistoryTraversal(active: DraftHistoryTraversal | null, token: number) {
  if (!active || active.token !== token) return { active, completed: null };
  return { active: null, completed: active };
}

export function draftHistoryNeedsRearm(completed: DraftHistoryTraversal, dirty: boolean) {
  return completed.kind !== "restore" && dirty;
}

export function draftHistoryEntryId(state: unknown) {
  if (!state || typeof state !== "object") return null;
  const entryId = (state as { caosDraftHistoryEntryId?: unknown }).caosDraftHistoryEntryId;
  return typeof entryId === "string" && entryId ? entryId : null;
}

export function observeDraftHistoryPop(active: DraftHistoryTraversal | null, state: unknown) {
  if (!active || active.phase !== "pending" || draftHistoryEntryId(state) !== active.expectedDestinationId) {
    return { active, matched: false };
  }
  return { active: { ...active, phase: "observed" as const }, matched: true };
}

export function protectDirtyDraftUnload(event: Pick<BeforeUnloadEvent, "preventDefault" | "returnValue">, dirty: boolean) {
  if (!dirty) return false;
  event.preventDefault();
  event.returnValue = "";
  return true;
}

type ConclusionArtifact = {
  module_id: string;
  markdown?: string | null;
  payload?: { summary?: string; narrative?: { takeaway?: string } } | null;
};

export function selectConclusionArtifact<T extends ConclusionArtifact>(artifacts: readonly T[]): T | null {
  const substantive = (artifact: T) => Boolean(artifact.payload?.narrative?.takeaway?.trim() || artifact.payload?.summary?.trim() || artifact.markdown?.trim());
  return artifacts.find((artifact) => artifact.module_id === "CP-2" && substantive(artifact))
    ?? artifacts.find((artifact) => artifact.module_id !== "CP-PARSE" && artifact.module_id !== "CP-0" && substantive(artifact))
    ?? artifacts.find((artifact) => artifact.module_id === "CP-PARSE" && substantive(artifact))
    ?? null;
}

export function nodeStatusTone(status: string) {
  switch (status) {
    case "pending": case "ready": return "idle";
    case "running": return "running";
    case "blocked": case "cancelled": return "warning";
    case "failed": return "critical";
    case "succeeded": return "success";
    default: return "warning";
  }
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

// The route of a destination: `/${slug}`, without the trailing slash `withQuery`
// restores, so callers compose it exactly as they composed the old literals.
export function routeFor(destination: Destination): string {
  return `/${routeDestinations.find(([, name]) => name === destination)![0]}`;
}

// The destination slug a pre-Align slug forwards to, or null for a live route.
export function forwardedSlug(slug: string): string | null {
  return forwardedRoutes.find(([from]) => from === slug)?.[1] ?? null;
}

// A forwarded slug resolves to the destination that absorbed it, so the shell
// renders that surface while the forwarder replaces the address; an unknown slug
// is null, and the caller — not this table — decides what an unknown route shows.
export function destinationFromSlug(slug: string): Destination | null {
  const resolved = forwardedSlug(slug) ?? slug;
  return routeDestinations.find(([route]) => route === resolved)?.[1] ?? null;
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

// Acceptance aftermath: a run's snapshot reads as the case's latest accepted authority only
// when the id the run carries (or, on a server that does not serve it, the id its
// acceptance just returned locally) matches the newest accepted ledger entry.
// Returns the matched snapshot id, or "" while the accept action must stay live.
export function acceptedAuthorityMatch(
  runSnapshotId: string | null | undefined,
  localSnapshotId: string | null | undefined,
  authoritySnapshotId: string | null | undefined,
): string {
  const candidate = runSnapshotId || localSnapshotId || "";
  return candidate && candidate === authoritySnapshotId ? candidate : "";
}

// A run that was accepted and then superseded by a later acceptance (FE-A1 F-14;
// D9): its own snapshot id when the case's latest accepted id is known and is a
// different snapshot, else "". The run surface renders that as "accepted,
// superseded" and never re-offers acceptance. Unknown authority claims nothing.
export function supersededAcceptance(
  runSnapshotId: string | null | undefined,
  authoritySnapshotId: string | null | undefined,
): string {
  return runSnapshotId && authoritySnapshotId && runSnapshotId !== authoritySnapshotId ? runSnapshotId : "";
}

export function acceptanceSlotSummary(
  runNodes: readonly { module_id: string }[],
  replacedArtifacts: readonly { module_id: string }[],
) {
  const next = [...new Set(runNodes.map((node) => node.module_id))];
  const previous = [...new Set(replacedArtifacts.map((artifact) => artifact.module_id))];
  const nextSet = new Set(next);
  const previousSet = new Set(previous);
  return {
    added: next.filter((moduleId) => !previousSet.has(moduleId)),
    replaced: next.filter((moduleId) => previousSet.has(moduleId)),
    removed: previous.filter((moduleId) => !nextSet.has(moduleId)),
  };
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
