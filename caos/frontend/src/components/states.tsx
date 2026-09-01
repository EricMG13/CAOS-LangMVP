import Link from "next/link";
import type { ReactNode } from "react";
import { compactIdentity, humanizeCode } from "../lib/workbench";

// One home for every "nothing here / still loading / this failed / this route is
// absent" surface in the workbench. Three surfaces used to own near-duplicate
// copies of these blocks (Workspace, Model Builder, Report Studio); the classes,
// copy, and ARIA below are exactly what those surfaces already rendered, so the
// stylesheet and the browser harnesses keep matching.
//
// Severity is the tone: `neutral` states a fact, `warning` states a condition the
// analyst must resolve, `critical` states a failure. Shape is independent of
// severity: `StateBlock` is the bordered block with a <strong> heading, `StateNote`
// is the bare inline paragraph. Every server code shown to a human is humanized
// here — a raw SCREAMING_SNAKE identifier is never presented as English.

export type StateTone = "neutral" | "warning" | "critical";
// The live-region choice is per site, not per severity: a failure the analyst just
// caused is an `alert`; a condition that arrived on its own is a polite `status`.
export type StateLive = "alert" | "status";
// One action slot, two shapes a caller can supply: a route (Link) or a retry
// callback. Callers keep their own retry semantics — reload, load(), refresh().
export type StateAction = { label: string; href: string } | { label: string; onAct: () => void };

// Re-exported so a surface already importing the state idiom gets the code
// humanizer from the same place; the single definition lives in lib/workbench.ts
// because the request helper needs it too and must stay free of React.
export { humanizeCode };

export function IdentityValue({ value, className = "mono" }: { value: string; className?: string }) {
  const abbreviated = compactIdentity(value);
  return <span className={className} title={value} aria-label={abbreviated === value ? value : `${abbreviated}. Full identity: ${value}`}>{abbreviated}</span>;
}

function liveProps(live?: StateLive) {
  if (live === "alert") return { role: "alert" as const };
  if (live === "status") return { role: "status" as const, "aria-live": "polite" as const };
  return {};
}

const blockClass: Record<StateTone, string> = {
  neutral: "callout",
  warning: "callout warning",
  critical: "empty error-state",
};

const actionClass: Record<StateTone, string> = {
  neutral: "action-state",
  warning: "action-state warning",
  critical: "action-state warning",
};

const noteClass: Record<StateTone, string> = {
  neutral: "callout",
  warning: "callout warning",
  critical: "error",
};

function StateActionControl({ action }: { action: StateAction }) {
  if ("href" in action) return <Link className="button small" href={action.href}>{action.label}</Link>;
  return <button className="button small" type="button" onClick={action.onAct}>{action.label}</button>;
}

// The bordered block: heading, body, an optional caller slot, an optional action.
// `code` and `title` are alternatives for the heading — `code` is humanized.
export function StateBlock({ tone = "neutral", shape = "callout", title, code, body, action, live, children }: {
  tone?: StateTone;
  shape?: "callout" | "action";
  title?: string;
  code?: string;
  body?: ReactNode;
  action?: StateAction;
  live?: StateLive;
  children?: ReactNode;
}) {
  const heading = code ? humanizeCode(code) : title;
  return <div className={shape === "action" ? actionClass[tone] : blockClass[tone]} {...liveProps(live)}>
    {heading ? <strong>{heading}</strong> : null}
    {body === undefined || body === null || body === "" ? null : <p>{body}</p>}
    {children}
    {action ? <StateActionControl action={action} /> : null}
  </div>;
}

// The bare inline paragraph idiom: `p.error` for a failure, `p.callout` for a
// standing condition. A `code` prefix is humanized the same way.
export function StateNote({ tone = "neutral", code, live, children }: {
  tone?: StateTone;
  code?: string;
  live?: StateLive;
  children?: ReactNode;
}) {
  return <p className={noteClass[tone]} {...liveProps(live)}>{code ? `${humanizeCode(code)}: ` : null}{children}</p>;
}

export function StateSkeleton() {
  return <div className="state-skeleton" role="status" aria-live="polite" aria-label="Loading"><span /><span /><span /></div>;
}

export function EmptyBlock({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

// The route-level empty: a panel of its own, because it stands in for a whole view.
export function EmptyPanel({ text, action }: { text: string; action?: StateAction }) {
  return <div className="panel"><div className="empty"><p>{text}</p>{action ? <StateActionControl action={action} /> : null}</div></div>;
}

// Loading, failed, or empty — the three outcomes of one read, in one component.
// An absent error is empty, not a blank failure card: only a message the caller
// actually holds gets presented as a failure.
export function LoadState({ loading, error, empty, title = "Unable to load this view.", onRetry }: {
  loading: boolean;
  error?: string;
  empty?: string;
  title?: string;
  onRetry?: () => void;
}) {
  if (loading) return <StateSkeleton />;
  if (error) return <StateBlock tone="critical" live="alert" title={title} body={error} action={{ label: "Retry", onAct: onRetry || (() => window.location.reload()) }} />;
  return <EmptyBlock>{empty || "No data available."}</EmptyBlock>;
}

// The observed-404 presentation: a capability whose route this deployment does not
// serve. Same idiom as the shell's QA drawer state block (state-block unavailable).
// Deliberately no Retry — a route that is absent cannot succeed on retry.
export function Unavailable({ title, context }: { title: string; context?: string }) {
  return <div className="state-block unavailable">
    <strong>{title}</strong>
    <p>Not available in this deployment.</p>
    {context ? <p className="muted">{context}</p> : null}
  </div>;
}

export function MutationReceipt({ children }: { children: ReactNode }) {
  return <div className="mutation-receipt" role="status" aria-live="polite" aria-atomic="true">
    <span aria-hidden="true">✓</span>
    <span>{children}</span>
  </div>;
}
