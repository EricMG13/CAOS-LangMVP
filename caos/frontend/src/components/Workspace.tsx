"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { FormEvent, ReactNode, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import EvidenceChip from "./EvidenceChip";
import ModelBuilder from "./model/ModelBuilder";
import ReportStudio from "./report/ReportStudio";
import { EmptyBlock, EmptyPanel, IdentityValue, LoadState, MutationReceipt, StateBlock, StateNote, Unavailable } from "./states";
import { api as request, firstErrorMessage, isUnavailableRoute, type ArtifactRecord, type CaseRecord, type LoanFinding, type LoanRow, type LoanUniverseResponse, type ResearchPlan, type RunRecord, type SourceRecord } from "../lib/api";
import { displayValue, flattenValue, markdownBlocks, normalizeEvidenceRefs, type NormalizedEvidenceRef } from "../lib/artifactReader";
import { initialAuthorityState, matchesAuthority, requestContext, workspaceAuthorityReducer, type AuthorityEvent } from "../lib/workspaceAuthority";

import WorkbenchShell, { type DrawerState } from "./WorkbenchShell";
import { type Destination, type DraftHistoryTraversal, type Snapshot, type SnapshotView, acceptanceSlotSummary, acceptedAuthorityMatch, beginDraftHistoryTraversal, destinationFromSlug, destinationMeta, draftHistoryEntryId, draftHistoryNeedsRearm, finishDraftHistoryTraversal, formatBlockLocator, formatDate, humanizeCode, isSameTabPrimaryGesture, moduleLabel, nodeStatusTone, observeDraftHistoryPop, protectDirtyDraftUnload, resolveDraftDiscard, routeDestinations, selectConclusionArtifact, withQuery } from "../lib/workbench";

type WriteAccess = "yes" | "no" | "unknown";
type DraftDiscardRequest = { detail: string; confirm: () => void; cancel?: () => void };
type RequestDraftDiscard = (detail: string, confirm: () => void, cancel?: () => void) => boolean;
type DraftHistoryState = {
  caosDraftHistoryEntryId?: string;
  caosDraftHistoryPreviousId?: string;
  caosDraftHistorySentinelId?: string;
  caosDraftHistoryBaseId?: string;
  caosModelDraftGuard?: boolean;
  caosReportDraftGuard?: boolean;
  [key: string]: unknown;
};

// One sentence per blocked write, and it distinguishes the two reasons: identity
// not yet confirmed, versus confirmed and read-only.
function WriteBlocked({ access, action }: { access: WriteAccess; action: string }) {
  return <div className="empty">{access === "unknown" ? "Confirming your access…" : `Reader access: ${action} is an analyst action.`}</div>;
}

const pathways = [
  ["FULL_CREDIT", "Full Credit"],
  ["EARNINGS_UPDATE", "Earnings Update"],
  ["COVENANT_REFINANCING", "Covenant & Refinancing"],
  ["RELATIVE_VALUE", "Relative Value"],
  ["DISTRESSED_RESTRUCTURING", "Distressed & Restructuring"],
  ["DEEP_RESEARCH", "Deep Research"],
];

function queryParam(key: string) {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get(key) || "";
}

export default function Workspace({ destination, children }: { destination?: Destination; children?: ReactNode } = {}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const routeSlug = pathname.split("/").filter(Boolean)[0] || "cases";
  const routeIsKnown = destination !== undefined || routeDestinations.some(([route]) => route === routeSlug);
  const active = destination ?? destinationFromSlug(routeSlug);
  const requestedCaseId = searchParams.get("case") || "";
  const requestedRunId = searchParams.get("run") || "";
  const routeQuestion = searchParams.get("q") || "";
  const routeArtifactId = searchParams.get("artifact") || "";
  const routeSourceId = searchParams.get("source") || "";
  const routeSearch = searchParams.toString();
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [authorityState, reducerDispatch] = useReducer(workspaceAuthorityReducer, initialAuthorityState);
  const authorityRef = useRef(initialAuthorityState);
  const dispatchAuthority = useCallback((event: AuthorityEvent) => {
    const next = workspaceAuthorityReducer(authorityRef.current, event);
    authorityRef.current = next;
    reducerDispatch(event);
    return next;
  }, []);
  const caseId = authorityState.caseId || "";
  const runId = authorityState.runId || "";
  const hydrated = authorityState.hydrated;
  const authorityStatus = authorityState.status;
  const [run, setRun] = useState<RunRecord | null>(null);
  const [casesLoading, setCasesLoading] = useState(true);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState("");
  const [error, setError] = useState("");
  // The outcome of a governed write, announced politely and only to assistive tech:
  // a sighted analyst already sees the new source row, the selected case or the
  // accepted-authority line, but nothing in the DOM said so out loud (WCAG 4.1.3).
  const [notice, setNotice] = useState("");
  const [pendingAction, setPendingAction] = useState("");
  // READER until the server says otherwise, plus a `roleResolved` flag so the
  // shell can tell "still asking" from "asked, and you may not". Defaulting to a
  // writer showed a reader every write control for as long as /api/me went
  // unanswered — including permanently, since the catch below only reports the
  // failure. This default also covers Model Builder and Report Studio, which
  // compute `role !== "READER"` from this same value.
  const [role, setRole] = useState("READER");
  const [roleResolved, setRoleResolved] = useState(false);
  const [authority, setAuthority] = useState<SnapshotView | null>(null);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [acceptPrompt, setAcceptPrompt] = useState(false);
  const [discardPrompt, setDiscardPrompt] = useState<DraftDiscardRequest | null>(null);
  // Observed-404 capability memory: a resume or plan-approval POST that 404ed means the
  // route is absent on this deployment, so the control renders its unavailable block
  // instead of an action that can never succeed.
  const [resumeUnavailable, setResumeUnavailable] = useState(false);
  const [approvalUnavailable, setApprovalUnavailable] = useState(false);
  // Fallback aftermath state for a server that does not serve run.accepted_snapshot_id:
  // the snapshot the accept POST just returned, bound to the run it was accepted for.
  const [localAccepted, setLocalAccepted] = useState<{ runId: string; snapshotId: string } | null>(null);
  const casesRequest = useRef(0);
  const caseRefresh = useRef(0);
  const runRefresh = useRef(0);
  const runCreation = useRef(0);
  const routeAuthorityRef = useRef("");
  const modelDraftDirtyRef = useRef(false);
  const reportDraftDirtyRef = useRef(false);
  const discardPromptRef = useRef<DraftDiscardRequest | null>(null);
  const replayingDraftLinkRef = useRef(false);
  const pendingDraftLinkRef = useRef<string | null>(null);
  const modelHistoryGuardRef = useRef(false);
  const historyTraversalRef = useRef<DraftHistoryTraversal | null>(null);
  const historyTraversalTokenRef = useRef(0);
  const historyTraversalFenceRef = useRef<{ token: number; timer: number } | null>(null);
  const historyRearmFrameRef = useRef<number | null>(null);
  const historyEntrySequenceRef = useRef(0);
  const lastHistoryEntryRef = useRef<{ id: string; href: string } | null>(null);
  const focusedBeforeRef = useRef<HTMLElement | null>(null);
  const lastDestinationRef = useRef(active);
  const selectedCase = useMemo(() => cases.find((item) => item.id === caseId) || null, [cases, caseId]);
  const caseIsAuthorized = selectedCase !== null;

  const finishHistoryTraversal = useCallback((token: number) => {
    const result = finishDraftHistoryTraversal(historyTraversalRef.current, token);
    if (!result.completed) return null;
    historyTraversalRef.current = result.active;
    const fence = historyTraversalFenceRef.current;
    if (fence?.token === token) {
      window.clearTimeout(fence.timer);
      historyTraversalFenceRef.current = null;
    }
    return result.completed;
  }, []);

  const beginHistoryTraversal = useCallback((kind: DraftHistoryTraversal["kind"], expectedDestinationId: string, navigate: () => void, onNoEvent?: (traversal: DraftHistoryTraversal) => void) => {
    const token = historyTraversalTokenRef.current + 1;
    const result = beginDraftHistoryTraversal(historyTraversalRef.current, token, kind, expectedDestinationId);
    if (!result.started) return null;
    historyTraversalTokenRef.current = token;
    historyTraversalRef.current = result.active;
    navigate();
    const timer = window.setTimeout(() => {
      const completed = finishHistoryTraversal(token);
      if (completed) onNoEvent?.(completed);
    }, 1000);
    historyTraversalFenceRef.current = { token, timer };
    return token;
  }, [finishHistoryTraversal]);

  const newHistoryEntryId = useCallback(() => {
    historyEntrySequenceRef.current += 1;
    return typeof window.crypto?.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `caos-${Date.now()}-${historyEntrySequenceRef.current}`;
  }, []);

  const ensureCurrentHistoryEntry = useCallback(() => {
    const state = (window.history.state || {}) as DraftHistoryState;
    const existingId = draftHistoryEntryId(state);
    if (existingId) {
      lastHistoryEntryRef.current = { id: existingId, href: window.location.href };
      return { id: existingId, state };
    }
    const id = newHistoryEntryId();
    const previousId = lastHistoryEntryRef.current?.id;
    const nextState = { ...state, caosDraftHistoryEntryId: id, ...(previousId ? { caosDraftHistoryPreviousId: previousId } : {}) };
    window.history.replaceState(nextState, "", window.location.href);
    lastHistoryEntryRef.current = { id, href: window.location.href };
    return { id, state: nextState };
  }, [newHistoryEntryId]);

  const armOwnedHistoryGuard = useCallback((marker: "model" | "report") => {
    if (typeof window === "undefined") return;
    if (historyTraversalRef.current) return;
    const state = (window.history.state || {}) as DraftHistoryState;
    if (state?.caosModelDraftGuard || state?.caosReportDraftGuard) { modelHistoryGuardRef.current = true; return; }
    if (!modelHistoryGuardRef.current) {
      const base = ensureCurrentHistoryEntry();
      const sentinelId = newHistoryEntryId();
      window.history.replaceState({ ...base.state, caosDraftHistorySentinelId: sentinelId }, "", window.location.href);
      window.history.pushState({
        ...base.state,
        caosDraftHistoryEntryId: sentinelId,
        caosDraftHistoryPreviousId: base.id,
        caosDraftHistoryBaseId: base.id,
        [marker === "model" ? "caosModelDraftGuard" : "caosReportDraftGuard"]: true,
      }, "", window.location.href);
      lastHistoryEntryRef.current = { id: sentinelId, href: window.location.href };
      modelHistoryGuardRef.current = true;
    }
  }, [ensureCurrentHistoryEntry, newHistoryEntryId]);

  const retireOwnedHistoryGuard = useCallback(() => {
    if (typeof window === "undefined" || discardPromptRef.current || modelDraftDirtyRef.current || reportDraftDirtyRef.current || !modelHistoryGuardRef.current || historyTraversalRef.current) return;
    const state = (window.history.state || {}) as DraftHistoryState;
    const baseId = state.caosDraftHistoryBaseId;
    if (!baseId) { modelHistoryGuardRef.current = false; return; }
    beginHistoryTraversal("retire", baseId, () => window.history.back(), () => {
      const current = (window.history.state || {}) as DraftHistoryState;
      modelHistoryGuardRef.current = Boolean(current.caosModelDraftGuard || current.caosReportDraftGuard);
    });
  }, [beginHistoryTraversal]);

  const releaseCleanDraftGuard = useCallback(() => {
    const from = pendingDraftLinkRef.current;
    pendingDraftLinkRef.current = null;
    if (typeof window !== "undefined" && from !== null && window.location.href !== from) {
      modelHistoryGuardRef.current = false;
      return;
    }
    retireOwnedHistoryGuard();
  }, [retireOwnedHistoryGuard]);

  const onModelDraftStateChange = useCallback((dirty: boolean) => {
    modelDraftDirtyRef.current = dirty;
    if (dirty) armOwnedHistoryGuard("model");
    else if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) releaseCleanDraftGuard();
  }, [armOwnedHistoryGuard, releaseCleanDraftGuard]);

  const onReportDraftStateChange = useCallback((dirty: boolean) => {
    reportDraftDirtyRef.current = dirty;
    if (dirty) armOwnedHistoryGuard("report");
    else if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) releaseCleanDraftGuard();
  }, [armOwnedHistoryGuard, releaseCleanDraftGuard]);

  useEffect(() => {
    const href = window.location.href;
    const state = (window.history.state || {}) as DraftHistoryState;
    const entryId = draftHistoryEntryId(state);
    const previous = lastHistoryEntryRef.current;
    const copiedIntoNewRoute = Boolean(previous && previous.href !== href && entryId === previous.id);
    if (!entryId || copiedIntoNewRoute) {
      const id = newHistoryEntryId();
      const nextState = copiedIntoNewRoute || (previous && previous.href !== href)
        ? Object.fromEntries(Object.entries(state).filter(([key]) => ![
          "caosDraftHistoryEntryId",
          "caosDraftHistoryPreviousId",
          "caosDraftHistorySentinelId",
          "caosDraftHistoryBaseId",
          "caosModelDraftGuard",
          "caosReportDraftGuard",
        ].includes(key))) as DraftHistoryState
        : state;
      window.history.replaceState({
        ...nextState,
        caosDraftHistoryEntryId: id,
        ...(previous ? { caosDraftHistoryPreviousId: previous.id } : {}),
      }, "", href);
      lastHistoryEntryRef.current = { id, href };
      return;
    }
    lastHistoryEntryRef.current = { id: entryId, href };
  }, [newHistoryEntryId, pathname, routeSearch]);

  const draftDiscardDetail = useCallback((action: string) => {
    const drafts = modelDraftDirtyRef.current && reportDraftDirtyRef.current
      ? "the unsigned Model Builder Draft Revision and unsaved Report Studio changes"
      : modelDraftDirtyRef.current ? "the unsigned Model Builder Draft Revision" : "the unsaved Report Studio changes";
    return `Discard ${drafts} ${action}?`;
  }, []);

  const requestDraftDiscard = useCallback<RequestDraftDiscard>((detail, confirm, cancel) => {
    if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) { confirm(); return true; }
    if (discardPromptRef.current) { cancel?.(); return false; }
    const next = { detail, confirm, cancel };
    discardPromptRef.current = next;
    setDiscardPrompt(next);
    return false;
  }, []);

  const finishDraftDiscard = useCallback((confirmed: boolean) => {
    const prompt = discardPromptRef.current;
    if (!prompt) return;
    discardPromptRef.current = null;
    setDiscardPrompt(null);
    resolveDraftDiscard(prompt, confirmed);
    if (!confirmed && !prompt.cancel && !modelDraftDirtyRef.current && !reportDraftDirtyRef.current) releaseCleanDraftGuard();
  }, [releaseCleanDraftGuard]);

  const commitCaseSelection = useCallback((nextCaseId: string, availableCases = cases) => {
    dispatchAuthority({ type: "selectCase", caseId: nextCaseId || null });
    const nextRunId = availableCases.find((item) => item.id === nextCaseId)?.current_execution_id || "";
    if (nextRunId) dispatchAuthority({ type: "selectRun", caseId: nextCaseId, runId: nextRunId });
    setRunLoading(false);
    setPendingAction("");
    setDrawer(null);
    setAcceptPrompt(false);
    setLocalAccepted(null);
    setAuthority(null);
    setRun(null);
    setRunError("");
    setError("");
  }, [cases, dispatchAuthority]);

  const selectCase = useCallback((nextCaseId: string, availableCases = cases) => {
    const currentCaseId = authorityRef.current.caseId || "";
    if (nextCaseId === currentCaseId) return true;
    return requestDraftDiscard(draftDiscardDetail("before changing case"), () => commitCaseSelection(nextCaseId, availableCases));
  }, [cases, commitCaseSelection, draftDiscardDetail, requestDraftDiscard]);

  const refreshCases = async (signal?: AbortSignal) => {
    const requestId = ++casesRequest.current;
    const context = requestContext(authorityRef.current);
    setCasesLoading(true);
    try {
      const next = await request<CaseRecord[]>("/api/cases", {}, signal);
      if (requestId !== casesRequest.current || !matchesAuthority(authorityRef.current, context)) return;
      setCases(next);
      setCasesLoading(false);
      dispatchAuthority({ type: "requestSucceeded", context, scope: "cases" });
      const requestedCaseId = queryParam("case");
      const requestedRunId = queryParam("run");
      const requestedCase = next.find((item) => item.id === requestedCaseId);
      const currentCaseId = authorityRef.current.caseId || "";
      const resolvedCaseId = next.find((item) => item.id === currentCaseId)?.id || requestedCase?.id || next[0]?.id || "";
      if (resolvedCaseId !== currentCaseId) {
        if (requestedCaseId && !requestedCase) routeAuthorityRef.current = `${requestedCaseId}\u0000${requestedRunId}`;
        if (!selectCase(resolvedCaseId, next)) return;
        if (requestedRunId && (!requestedCaseId || requestedCase)) {
          dispatchAuthority({ type: "selectRun", caseId: resolvedCaseId, runId: requestedRunId });
        }
      }
      if (!authorityRef.current.runId && !requestedRunId) {
        const resolvedCase = next.find((item) => item.id === resolvedCaseId);
        if (resolvedCase?.current_execution_id) {
          dispatchAuthority({ type: "selectRun", caseId: resolvedCaseId, runId: resolvedCase.current_execution_id });
        }
      }
      if (authorityRef.current.caseId) dispatchAuthority({ type: "requestStarted", scope: "case" });
    } catch (caught) {
      if (requestId !== casesRequest.current || !matchesAuthority(authorityRef.current, context)) return;
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(firstErrorMessage(caught, "Unable to load cases"));
        setCasesLoading(false);
        dispatchAuthority({ type: "requestFailed", context, scope: "cases" });
      }
    }
  };

  const refreshCase = async (id = caseId, signal?: AbortSignal) => {
    const context = requestContext(authorityRef.current);
    if (!id || id !== context.caseId) return null;
    const requestId = ++caseRefresh.current;
    try {
      const [detail, snapshot] = await Promise.all([
        request<CaseRecord>(`/api/cases/${id}`, {}, signal),
        request<SnapshotView>(`/api/cases/${id}/snapshot`, {}, signal),
      ]);
      if (requestId !== caseRefresh.current || !matchesAuthority(authorityRef.current, context)) return null;
      setCases((previous) => previous.map((item) => item.id === id ? { ...item, ...detail } : item));
      setAuthority(snapshot);
      dispatchAuthority({ type: "requestSucceeded", context, scope: "case" });
      if (snapshot.accepted) dispatchAuthority({ type: "snapshotAccepted", context, snapshotId: snapshot.accepted.id });
      return snapshot;
    } catch (caught) {
      if (requestId !== caseRefresh.current || !matchesAuthority(authorityRef.current, context)) return null;
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(firstErrorMessage(caught, "Unable to load case authority"));
        dispatchAuthority({ type: "requestFailed", context, scope: "case" });
      }
      return null;
    }
  };

  const refreshRun = async (id = runId) => {
    if (!id) { setRun(null); setRunLoading(false); return; }
    const context = requestContext(authorityRef.current);
    if (id !== context.runId) return;
    const requestId = ++runRefresh.current;
    setRunLoading(true);
    setRunError("");
    try {
      const next = await request<RunRecord>(`/api/runs/${id}`);
      if (requestId !== runRefresh.current || !matchesAuthority(authorityRef.current, context)) return;
      if (next.case_id !== context.caseId) {
        setRun(null);
        setRunLoading(false);
        setRunError("Requested run does not belong to the selected case.");
        dispatchAuthority({ type: "requestFailed", context, scope: "run" });
        if (context.caseId) dispatchAuthority({ type: "invalidateRun", caseId: context.caseId, runId: id });
        return;
      }
      setRun(next);
      dispatchAuthority({ type: "requestSucceeded", context, scope: "run" });
    } catch (caught) {
      if (requestId !== runRefresh.current || !matchesAuthority(authorityRef.current, context)) return;
      const message = firstErrorMessage(caught, "Unable to refresh run");
      setRunError(message);
      setError(message);
      dispatchAuthority({ type: "requestFailed", context, scope: "run" });
    } finally {
      if (requestId !== runRefresh.current || !matchesAuthority(authorityRef.current, context)) return;
      setRunLoading(false);
    }
  };

  const settleObservedHistory = useCallback((observed: DraftHistoryTraversal) => {
    if (historyRearmFrameRef.current !== null) window.cancelAnimationFrame(historyRearmFrameRef.current);
    historyRearmFrameRef.current = window.requestAnimationFrame(() => {
      historyRearmFrameRef.current = null;
      const activeTraversal = historyTraversalRef.current;
      if (!activeTraversal || activeTraversal.token !== observed.token || activeTraversal.phase !== "observed") return;
      if (draftHistoryEntryId(window.history.state) !== activeTraversal.expectedDestinationId) return;
      const completed = finishHistoryTraversal(activeTraversal.token);
      if (!completed) return;
      const state = (window.history.state || {}) as DraftHistoryState;
      const ownsSentinel = Boolean(state.caosModelDraftGuard || state.caosReportDraftGuard);
      modelHistoryGuardRef.current = ownsSentinel;
      const dirty = modelDraftDirtyRef.current || reportDraftDirtyRef.current;
      if (!draftHistoryNeedsRearm(completed, dirty) || ownsSentinel) return;
      modelHistoryGuardRef.current = false;
      armOwnedHistoryGuard(modelDraftDirtyRef.current ? "model" : "report");
    });
  }, [armOwnedHistoryGuard, finishHistoryTraversal]);

  const reconcileHistoryWithoutPop = useCallback(() => {
    const state = (window.history.state || {}) as DraftHistoryState;
    const ownsSentinel = Boolean(state.caosModelDraftGuard || state.caosReportDraftGuard);
    modelHistoryGuardRef.current = ownsSentinel;
    if (ownsSentinel || (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current)) return;
    armOwnedHistoryGuard(modelDraftDirtyRef.current ? "model" : "report");
  }, [armOwnedHistoryGuard]);

  useEffect(() => {
    // URL-derived state is hydrated after the server render to keep the shell deterministic.
    dispatchAuthority({ type: "hydrate", caseId: requestedCaseId || null, runId: requestedRunId || null });
    const controller = new AbortController();
    const guardDraftNavigation = (event: MouseEvent) => {
      if (replayingDraftLinkRef.current) { replayingDraftLinkRef.current = false; return; }
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>("a[href]") : null;
      const href = target?.getAttribute("href") || "";
      if (!target || !href.startsWith("/") || target.getAttribute("download") !== null || !isSameTabPrimaryGesture(event, target.getAttribute("target") || "")) return;
      if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      target.closest<HTMLDialogElement>("dialog[open]")?.close();
      requestDraftDiscard(draftDiscardDetail("and leave this page"), () => {
        pendingDraftLinkRef.current = window.location.href;
        replayingDraftLinkRef.current = true;
        target.click();
        replayingDraftLinkRef.current = false;
      });
    };
    const startConfirmedHistoryTraversal = () => {
      const state = (window.history.state || {}) as DraftHistoryState;
      const previousId = state.caosDraftHistoryPreviousId;
      modelHistoryGuardRef.current = false;
      if (previousId) {
        const token = beginHistoryTraversal("confirmed", previousId, () => window.history.back(), reconcileHistoryWithoutPop);
        if (token === null && (modelDraftDirtyRef.current || reportDraftDirtyRef.current)) armOwnedHistoryGuard(modelDraftDirtyRef.current ? "model" : "report");
        return;
      }
      const navigation = (window as Window & { navigation?: { canGoBack?: boolean } }).navigation;
      if (navigation?.canGoBack === false) {
        if (modelDraftDirtyRef.current || reportDraftDirtyRef.current) armOwnedHistoryGuard(modelDraftDirtyRef.current ? "model" : "report");
        return;
      }
      // An untagged predecessor may be another document. Let its native
      // beforeunload prompt remain the last-resort protection for that boundary.
      window.history.back();
    };
    const guardBrowserHistory = (event: PopStateEvent) => {
      const eventEntryId = draftHistoryEntryId(event.state);
      if (eventEntryId) lastHistoryEntryRef.current = { id: eventEntryId, href: window.location.href };
      const activeTraversal = historyTraversalRef.current;
      if (activeTraversal) {
        const observation = observeDraftHistoryPop(activeTraversal, event.state);
        historyTraversalRef.current = observation.active;
        if (observation.matched && observation.active) settleObservedHistory(observation.active);
        return;
      }
      if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) return;
      event.stopImmediatePropagation();
      const restoreHistoryGuard = () => {
        if (!modelHistoryGuardRef.current) return;
        if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) {
          modelHistoryGuardRef.current = false;
          return;
        }
        const state = (window.history.state || {}) as DraftHistoryState;
        const sentinelId = state.caosDraftHistorySentinelId;
        if (sentinelId) {
          beginHistoryTraversal("restore", sentinelId, () => window.history.forward(), reconcileHistoryWithoutPop);
          return;
        }
        modelHistoryGuardRef.current = false;
        armOwnedHistoryGuard(modelDraftDirtyRef.current ? "model" : "report");
      };
      requestDraftDiscard(draftDiscardDetail("and use browser history"), startConfirmedHistoryTraversal, restoreHistoryGuard);
    };
    const guardUnload = (event: BeforeUnloadEvent) => {
      protectDirtyDraftUnload(event, modelDraftDirtyRef.current || reportDraftDirtyRef.current);
    };
    document.addEventListener("click", guardDraftNavigation, true);
    window.addEventListener("popstate", guardBrowserHistory, true);
    window.addEventListener("beforeunload", guardUnload);
    void request<{ role: string }>("/api/me", {}, controller.signal).then((who) => {
      setRole(["ANALYST", "APPROVER", "ADMIN"].includes(who.role) ? who.role : "READER");
      setRoleResolved(true);
    }).catch((caught) => {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setRoleResolved(true);
        setError(firstErrorMessage(caught, "Unable to load identity"));
      }
    });
    const timer = window.setTimeout(() => void refreshCases(controller.signal), 0);
    return () => { controller.abort(); window.clearTimeout(timer); if (historyTraversalFenceRef.current) window.clearTimeout(historyTraversalFenceRef.current.timer); if (historyRearmFrameRef.current !== null) window.cancelAnimationFrame(historyRearmFrameRef.current); historyTraversalRef.current = null; historyTraversalFenceRef.current = null; historyRearmFrameRef.current = null; document.removeEventListener("click", guardDraftNavigation, true); window.removeEventListener("popstate", guardBrowserHistory, true); window.removeEventListener("beforeunload", guardUnload); };
    // The selected case is intentionally not a fetch dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [armOwnedHistoryGuard, beginHistoryTraversal, draftDiscardDetail, reconcileHistoryWithoutPop, requestDraftDiscard, settleObservedHistory]);

  useEffect(() => {
    if (!hydrated) return;
    const authorizedCase = requestedCaseId ? cases.find((item) => item.id === requestedCaseId) : null;
    const routeAuthority = `${requestedCaseId}\u0000${requestedRunId}`;
    if (routeAuthorityRef.current === routeAuthority || (requestedCaseId && !authorizedCase && casesLoading)) return;
    const scheduledUnder = routeAuthorityRef.current;
    const timer = window.setTimeout(() => {
      // A local case selection acknowledges its own authority synchronously below.
      // If that happened after this route was queued, the query string it was
      // scheduled from is stale and must not be replayed over the newer selection.
      if (routeAuthorityRef.current !== scheduledUnder) return;
      if (authorizedCase && authorizedCase.id !== caseId) {
        if (!selectCase(authorizedCase.id)) {
          const url = new URL(window.location.href);
          if (caseId) url.searchParams.set("case", caseId); else url.searchParams.delete("case");
          if (runId) url.searchParams.set("run", runId); else url.searchParams.delete("run");
          window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
          return;
        }
        if (requestedRunId) {
          dispatchAuthority({ type: "selectRun", caseId: authorizedCase.id, runId: requestedRunId });
        }
        routeAuthorityRef.current = routeAuthority;
        return;
      }
      // A workflow link may omit `run`; in that case the selected case keeps its
      // current execution. An explicit run query always wins for the same case.
      if (requestedRunId && requestedRunId !== runId) {
        setRun(null);
        dispatchAuthority({ type: "selectRun", caseId, runId: requestedRunId });
      }
      routeAuthorityRef.current = routeAuthority;
    }, 0);
    return () => window.clearTimeout(timer);
  }, [caseId, cases, casesLoading, dispatchAuthority, hydrated, requestedCaseId, requestedRunId, runId, selectCase]);

  useEffect(() => {
    // Visible case authority and its drawer must clear at every reducer authority generation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAuthority(null); setDrawer(null);
    if (!caseId || !caseIsAuthorized) return;
    const controller = new AbortController();
    void refreshCase(caseId, controller.signal);
    return () => controller.abort();
    // `refreshCase` deliberately resolves the current external authority.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authorityState.generation, caseId, caseIsAuthorized]);

  useEffect(() => {
    document.title = `CAOS — ${destinationMeta[active].title}`;
  }, [active]);

  // Last element the user actually focused. Read by the repair effect below, which
  // cannot observe it itself: by the time an effect runs the element is already
  // disabled or unmounted and `document.activeElement` has fallen back to <body>.
  useEffect(() => {
    const remember = (event: FocusEvent) => {
      if (event.target instanceof HTMLElement && event.target !== document.body) focusedBeforeRef.current = event.target;
    };
    document.addEventListener("focusin", remember);
    return () => document.removeEventListener("focusin", remember);
  }, []);

  // WCAG 2.4.3. Three things in this workspace destroy the focused element: a
  // governed action disables its own control for the length of the request, a case
  // change re-keys the whole destination subtree, and a client-side route change
  // replaces it outright. Every one of them drops focus to <body>, which strands a
  // keyboard user mid-journey and throws a screen reader back to the top of the
  // document — measured at create-case, upload, compile, accept and open-artifact.
  // Repair it: a navigation lands on the main landmark, an in-place action goes back
  // to the control the analyst was on, and a control that did not survive its own
  // action falls back to the landmark rather than to nothing. A page that has never
  // held focus is left alone — <body> is the correct starting point for a fresh load.
  useEffect(() => {
    // This assignment stays ABOVE the guards on purpose. The ref tracks where the
    // workspace is, not where a repair last happened, so it must advance even on the
    // runs that decline to repair. Move it below and a route change the user made
    // with the mouse — focus never lost, so nothing to repair — leaves the ref stale,
    // and the next in-place action reads `navigated` as true and throws focus to the
    // landmark instead of returning it to the control.
    const navigated = lastDestinationRef.current !== active;
    lastDestinationRef.current = active;
    const previous = focusedBeforeRef.current;
    // Wait for the action to settle. Repairing mid-flight would land on the landmark
    // every time, because the control the analyst pressed is still disabled and
    // cannot take focus back yet.
    if (pendingAction) return;
    // Never repair underneath an open modal. Today every modal here focuses something
    // inside itself on open, so `previous` is in the dialog and the restore below
    // wins — but that is an invariant of three call sites, not a guarantee. If one
    // ever opens without taking focus, the landmark fallback would put focus on
    // inert content behind the backdrop, which is worse than the loss it repairs.
    if (document.querySelector("dialog[open]")) return;
    if (!previous || document.activeElement !== document.body) return;
    const frame = window.requestAnimationFrame(() => {
      if (document.activeElement !== document.body) return;
      // Still connected is not the same as still focusable: accept confirms from
      // inside a <dialog> that this very action closes, and `focus()` on a control
      // in a closed dialog is a silent no-op. Land on the landmark whenever the
      // restore did not take, rather than trusting it to have worked.
      if (!navigated && previous.isConnected) previous.focus();
      if (document.activeElement === document.body) document.getElementById("main-content")?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [active, caseId, runId, pendingAction, run?.status, run?.error?.code]);

  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    if (caseId) url.searchParams.set("case", caseId); else url.searchParams.delete("case");
    if (runId) url.searchParams.set("run", runId); else url.searchParams.delete("run");
    // `useSearchParams` trails this write by a render, so the route effect above can
    // still observe the previous case/run. Claim that authority here, synchronously,
    // or a case switch can be reverted by its own stale query string and the previous
    // issuer's run re-attached after the analyst has already moved on.
    routeAuthorityRef.current = `${caseId}\u0000${runId}`;
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, [hydrated, caseId, runId]);

  useEffect(() => {
    if (!runId || !caseIsAuthorized) return;
    // The initial refresh is an external synchronization boundary.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshRun(runId);
    // refreshRun only depends on the current run id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseIsAuthorized, runId]);

  // Terminal runs emit nothing further; leaving no stream open also stops the
  // EventSource reconnect loop once the server ends a fully delivered tail.
  const runSettled = !run || run.status === "succeeded" || run.status === "failed";

  useEffect(() => {
    if (!runId || !run || run.id !== runId || run.case_id !== caseId || runSettled) return;
    const source = new EventSource(`/api/runs/${runId}/events`);
    const refresh = () => void refreshRun();
    // Progress is driven by the persisted graph events: each named event triggers
    // a RunRecord refetch, and `onopen` resyncs whatever a reconnect gap missed.
    source.onopen = refresh;
    ["run.created", "run.running", "node.running", "node.succeeded", "node.failed", "run.succeeded", "run.failed", "run.paused", "research.plan_ready", "research.plan_approved", "snapshot.accepted"].forEach((name) => source.addEventListener(name, refresh));
    return () => source.close();
    // Event updates only begin after the run has passed its case authority check.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, run?.case_id, run?.id, runId, runSettled]);

  const createCase = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError(""); setNotice("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const context = requestContext(authorityRef.current);
    setPendingAction("create-case");
    try {
      const created = await request<CaseRecord>("/api/cases", { method: "POST", body: JSON.stringify({ name: form.get("name"), issuer: form.get("issuer"), sector: form.get("sector") || "Unclassified" }) });
      if (!matchesAuthority(authorityRef.current, context)) return;
      casesRequest.current += 1;
      setCases((previous) => [created, ...previous]);
      dispatchAuthority({ type: "requestSucceeded", context, scope: "create-case" });
      setPendingAction("");
      setNotice(`Case created: ${created.issuer} / ${created.name}. It is now the selected case.`);
      selectCase(created.id); formElement.reset();
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return;
      setError(firstErrorMessage(caught, "Unable to create case"));
      dispatchAuthority({ type: "requestFailed", context, scope: "create-case" });
    } finally {
      if (matchesAuthority(authorityRef.current, context)) setPendingAction("");
    }
  };

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!caseId) return; setError(""); setNotice("");
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const context = requestContext(authorityRef.current);
    setPendingAction("upload");
    try {
      await request(`/api/cases/${caseId}/sources`, { method: "POST", body: form });
      if (!matchesAuthority(authorityRef.current, context)) return;
      dispatchAuthority({ type: "requestSucceeded", context, scope: "upload" });
      await refreshCase(caseId);
      if (matchesAuthority(authorityRef.current, context)) { setNotice("Source uploaded. The case source set is versioned."); formElement.reset(); }
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return;
      setError(firstErrorMessage(caught, "Unable to upload source"));
      dispatchAuthority({ type: "requestFailed", context, scope: "upload" });
    } finally {
      if (matchesAuthority(authorityRef.current, context)) setPendingAction("");
    }
  };

  const startRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (!caseId) return; setError(""); setNotice("");
    const form = new FormData(event.currentTarget);
    const pathway = String(form.get("pathway") || "");
    const depth = String(form.get("depth") || "");
    const mustAnswer = String(form.get("must_answer") || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const exclusions = String(form.get("exclusions") || "").split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    if (pathway === "DEEP_RESEARCH" && (mustAnswer.length > 10 || exclusions.length > 10 || mustAnswer.length + exclusions.length > 10 || [...mustAnswer, ...exclusions].some((line) => line.length > 200))) {
      setError("Research brief lists allow at most 10 nonblank lines combined, and each line is limited to 200 characters.");
      return;
    }
    const researchBrief = pathway === "DEEP_RESEARCH" ? {
      research_question: String(form.get("research_question") || "").trim(),
      decision_context: String(form.get("decision_context") || "").trim(),
      as_of_date: String(form.get("as_of_date") || ""),
      time_horizon: String(form.get("time_horizon") || "").trim(),
      must_answer: mustAnswer,
      exclusions,
    } : undefined;
    const context = requestContext(authorityRef.current);
    const expectedCaseId = context.caseId;
    if (!expectedCaseId) return;
    const requestId = ++runCreation.current;
    setPendingAction("start-run");
    try {
      const created = await request<RunRecord>(`/api/cases/${expectedCaseId}/runs`, { method: "POST", body: JSON.stringify({ pathway, depth, focus_questions: [], ...(researchBrief ? { research_brief: researchBrief } : {}) }) });
      if (requestId !== runCreation.current || !matchesAuthority(authorityRef.current, context)) return;
      if (created.case_id !== expectedCaseId) {
        const message = "Started run does not belong to the selected case.";
        setRunError(message);
        setError(message);
        dispatchAuthority({ type: "requestFailed", context, scope: "start-run" });
        return;
      }
      setRun(created);
      setNotice("Route compiled. Execution started.");
      dispatchAuthority({ type: "requestSucceeded", context, scope: "start-run" });
      setPendingAction((current) => current === "start-run" ? "" : current);
      dispatchAuthority({ type: "selectRun", caseId: expectedCaseId, runId: created.id });
    } catch (caught) {
      if (requestId !== runCreation.current || !matchesAuthority(authorityRef.current, context)) return;
      setError(firstErrorMessage(caught, "Unable to start run"));
      dispatchAuthority({ type: "requestFailed", context, scope: "start-run" });
    } finally {
      if (requestId === runCreation.current && matchesAuthority(authorityRef.current, context)) setPendingAction((current) => current === "start-run" ? "" : current);
    }
  };

  // The acceptance ceremony is two steps: `acceptRun` opens the digest-bound
  // dialog, `confirmAccept` performs the governed POST it reviewed.
  const acceptRun = () => {
    if (!runId || !run || run.id !== runId || run.case_id !== caseId) {
      setRunError("Only a run bound to the selected case can be accepted.");
      return;
    }
    setAcceptPrompt(true);
  };

  const confirmAccept = async () => {
    setAcceptPrompt(false); setNotice("");
    if (!runId || !run || run.id !== runId || run.case_id !== caseId) {
      setRunError("Only a run bound to the selected case can be accepted.");
      return;
    }
    const context = requestContext(authorityRef.current);
    setPendingAction("accept-run");
    try {
      const accepted = await request<Snapshot>(`/api/runs/${runId}/accept`, { method: "POST" });
      if (!matchesAuthority(authorityRef.current, context)) return;
      dispatchAuthority({ type: "snapshotAccepted", context, snapshotId: accepted.id });
      setLocalAccepted({ runId, snapshotId: accepted.id });
      // The id itself is announced by the accepted-authority line this unblocks; naming
      // it twice makes a screen reader read twenty characters of hash for no gain.
      setNotice("Snapshot accepted as the latest authority. A pinned visible lens moves only through an explicit switch.");
      await refreshCase(caseId); await refreshRun(runId);
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return;
      setError(firstErrorMessage(caught, "Unable to accept snapshot"));
      dispatchAuthority({ type: "requestFailed", context, scope: "accept-run" });
    } finally {
      if (matchesAuthority(authorityRef.current, context)) setPendingAction("");
    }
  };

  // Resume mirrors the accept flow's mechanics: case-binding guard, request context,
  // authority match on every state write. POST /api/runs/{id}/resume takes no body and
  // may legitimately no-op, so the returned run's status is always the truth shown.
  const resumeRun = async () => {
    if (!runId || !run || run.id !== runId || run.case_id !== caseId) {
      setRunError("Only a run bound to the selected case can be resumed.");
      return;
    }
    const context = requestContext(authorityRef.current);
    setError(""); setNotice("");
    setPendingAction("resume-run");
    try {
      const resumed = await request<RunRecord>(`/api/runs/${runId}/resume`, { method: "POST" });
      if (!matchesAuthority(authorityRef.current, context)) return;
      setRun(resumed);
      setNotice(`Run resumed. Status ${humanizeCode(resumed.status)}.`);
      dispatchAuthority({ type: "requestSucceeded", context, scope: "resume-run" });
      await refreshRun(runId);
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return;
      if (isUnavailableRoute(caught)) setResumeUnavailable(true);
      else setError(firstErrorMessage(caught, "Unable to resume run"));
      dispatchAuthority({ type: "requestFailed", context, scope: "resume-run" });
    } finally {
      if (matchesAuthority(authorityRef.current, context)) setPendingAction((current) => current === "resume-run" ? "" : current);
    }
  };

  const approveResearchPlan = async (planHash: string) => {
    if (!runId || !run || run.id !== runId || run.case_id !== caseId) return;
    const context = requestContext(authorityRef.current);
    const expectedCaseId = context.caseId;
    const expectedRunId = context.runId;
    if (!expectedCaseId || !expectedRunId) return;
    setError(""); setNotice("");
    setPendingAction("approve-research-plan");
    try {
      await request(`/api/runs/${expectedRunId}/research-plan/approve`, { method: "POST", body: JSON.stringify({ plan_hash: planHash }) });
      if (!matchesAuthority(authorityRef.current, context)) return;
      setNotice("Research plan approved. Execution resumes against the approved plan hash.");
      dispatchAuthority({ type: "requestSucceeded", context, scope: "research-plan" });
      await refreshRun(expectedRunId);
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return;
      if (isUnavailableRoute(caught)) setApprovalUnavailable(true);
      else setError(firstErrorMessage(caught, "Unable to approve research plan"));
      dispatchAuthority({ type: "requestFailed", context, scope: "research-plan" });
    } finally {
      if (matchesAuthority(authorityRef.current, context)) setPendingAction((current) => current === "approve-research-plan" ? "" : current);
    }
  };

  const switchSnapshot = async (snapshotId: string) => {
    const context = requestContext(authorityRef.current);
    if (!context.caseId) return null;
    try {
      const switched = await request<Snapshot>(`/api/cases/${context.caseId}/snapshot/switch`, { method: "POST", body: JSON.stringify({ snapshot_id: snapshotId }) });
      if (!matchesAuthority(authorityRef.current, context)) return null;
      dispatchAuthority({ type: "snapshotAccepted", context, snapshotId: switched.id });
      return refreshCase(context.caseId);
    } catch (caught) {
      if (!matchesAuthority(authorityRef.current, context)) return null;
      dispatchAuthority({ type: "requestFailed", context, scope: "switch-snapshot" });
      throw caught;
    }
  };

  // Acceptance identity follows the server's newest acceptance ledger entry.
  // `authority.accepted` is deliberately different: it is the visible/pinned
  // reader lens and may trail this id until an explicit snapshot switch.
  const acceptedRunSnapshotId = run ? acceptedAuthorityMatch(run.accepted_snapshot_id, localAccepted && localAccepted.runId === run.id ? localAccepted.snapshotId : "", authority?.latest_accepted?.id) : "";

  // The rail's LIVE badge is honest only while the selected case's run is genuinely
  // executing (queued or running — paused and terminal runs are not live).
  const runIsLive = Boolean(run && run.id === runId && run.case_id === caseId && (run.status === "queued" || run.status === "running"));

  // A shared write the served role cannot perform is never offered. The shell's
  // own controls — create, upload, compile, accept, switch, workbook import — had
  // no such gate, so a READER was shown six primary actions that all answered 403.
  // Derived once here so the rule has one home rather than one per control.
  const writeAccess: WriteAccess = !roleResolved ? "unknown" : role === "READER" ? "no" : "yes";

  // The generic paused branch's resume control; READER never sees the shared write,
  // and an observed 404 (older server without the resume route) pins the block.
  const resumeSlot = resumeUnavailable
    ? <Unavailable title="Run resume" />
    : writeAccess === "yes"
      ? <button className="button small" type="button" disabled={pendingAction === "resume-run"} onClick={() => void resumeRun()}>{pendingAction === "resume-run" ? "Resuming…" : "Resume run"}</button>
      : null;

  const renderDestination = () => {
    if (!selectedCase && active !== "Cases" && active !== "Admin Studio") return <EmptyPanel text="Create or select a case before entering an analytical workspace." action={{ label: "Open Cases", href: "/cases/" }} />;
    switch (active) {
      case "Cases": return <CasesView writeAccess={writeAccess} cases={cases} casesLoading={casesLoading} selectedCase={selectedCase} caseId={caseId} createCase={createCase} pendingAction={pendingAction} />;
      case "Sources": return <SourcesView writeAccess={writeAccess} selectedCase={selectedCase} artifactId={routeArtifactId} sourceId={routeSourceId} upload={upload} pendingAction={pendingAction} onOpenEvidence={(evidenceId, source) => setDrawer({ kind: "evidence", evidenceId, source })} />;
      case "Run Console": return <RunConsole writeAccess={writeAccess} caseId={caseId} selectedCase={selectedCase} run={run} runLoading={runLoading} runError={runError} startRun={startRun} acceptRun={acceptRun} acceptedSnapshotId={acceptedRunSnapshotId} visibleSnapshotId={authority?.accepted?.id || ""} switchRequired={authority?.switch_required === true} approveResearchPlan={approveResearchPlan} approvalUnavailable={approvalUnavailable} pendingAction={pendingAction} resumeSlot={resumeSlot} />;
      case "Deep-Dive": return <DeepDive writeAccess={writeAccess} selectedCase={selectedCase} question={routeQuestion} caseId={caseId} run={run} onSwitchSnapshot={switchSnapshot} />;
      case "RV Screener": return <RVView key={caseId} writeAccess={writeAccess} caseId={caseId} />;
      case "Command Center": return <CommandView caseId={caseId} question={routeQuestion} />;
      case "Model Builder": return <ModelBuilder caseId={caseId} role={role} onDraftStateChange={onModelDraftStateChange} />;
      case "Report Studio": return <ReportStudio key={caseId} caseId={caseId} role={role} selectedCase={selectedCase} onDraftStateChange={onReportDraftStateChange} requestDraftDiscard={requestDraftDiscard} />;
      case "Admin Studio": return <AdminView />;
    }
  };

  return <>
    <WorkbenchShell
      active={active}
      authority={authority}
      authorityStatus={authorityStatus}
      cases={cases}
      casesLoading={casesLoading}
      caseId={caseId}
      drawer={drawer}
      error={error}
      onCaseChange={selectCase}
      onDrawerChange={setDrawer}
      role={role}
      runId={runId}
      runIsLive={runIsLive}
      selectedCase={selectedCase}
      unknownRoute={!routeIsKnown}
    >
      {notice ? <MutationReceipt>{notice}</MutationReceipt> : null}
      <div key={`${active}:${caseId}`}>{routeIsKnown ? <>{renderDestination()}{children}</> : children}</div>
    </WorkbenchShell>
    <AcceptDialog open={acceptPrompt} run={run} replaces={authority?.latest_accepted ?? null} pending={pendingAction === "accept-run"} onConfirm={confirmAccept} onClose={() => setAcceptPrompt(false)} />
    <DraftDiscardDialog open={discardPrompt !== null} detail={discardPrompt?.detail || ""} onConfirm={() => finishDraftDiscard(true)} onClose={() => finishDraftDiscard(false)} />
  </>;
}

function CasesView({ writeAccess, cases, casesLoading, selectedCase, caseId, createCase, pendingAction }: { writeAccess: WriteAccess; cases: CaseRecord[]; casesLoading: boolean; selectedCase: CaseRecord | null; caseId: string; createCase: (event: FormEvent<HTMLFormElement>) => void; pendingAction: string }) {
  const [search, setSearch] = useState("");
  const [snapshotFilter, setSnapshotFilter] = useState<"all" | "accepted" | "unaccepted">("all");
  const visibleCases = useMemo(() => cases.filter((item) => {
    const matchesSearch = `${item.issuer} ${item.name} ${item.sector}`.toLowerCase().includes(search.trim().toLowerCase());
    const matchesFilter = snapshotFilter === "all"
      || (snapshotFilter === "accepted" ? Boolean(item.accepted_snapshot_id) : !item.accepted_snapshot_id);
    return matchesSearch && matchesFilter;
  }), [cases, search, snapshotFilter]);
  const resetFilters = () => { setSearch(""); setSnapshotFilter("all"); };
  return <div className="grid cases-layout">
    <section className="panel cases-register"><div className="panel-header"><h2>Monitored credits</h2><span className="panel-meta">{casesLoading ? "Loading…" : `${visibleCases.length} of ${cases.length}`}</span></div><div className="worklist-toolbar"><div className="field"><label htmlFor="case-search">Search credits</label><input id="case-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Issuer, case, or sector" /></div><div className="field"><label htmlFor="case-snapshot-filter">Authority</label><select id="case-snapshot-filter" value={snapshotFilter} onChange={(event) => setSnapshotFilter(event.target.value as "all" | "accepted" | "unaccepted")}><option value="all">All credits</option><option value="accepted">Accepted authority</option><option value="unaccepted">No accepted authority</option></select></div></div><div className="panel-body table-wrap" tabIndex={0} role="region" aria-label="Monitored credit register"><table><thead><tr><th scope="col">Credit</th><th scope="col">Case</th><th scope="col">Evidence</th><th scope="col">Authority</th><th scope="col">Action</th></tr></thead><tbody>{visibleCases.map((item) => <tr aria-current={caseId === item.id ? "true" : undefined} className={caseId === item.id ? "selected-row" : undefined} key={item.id}><td><strong>{item.issuer}</strong><div className="muted">{item.sector}</div></td><td>{item.name}</td><td className="num">{item.source_count == null ? "Unavailable" : `${item.source_count} source${item.source_count === 1 ? "" : "s"}`}</td><td>{item.accepted_snapshot_id ? <span className="status success">Accepted</span> : <span className="status warning">Not accepted</span>}</td><td><Link className="button small primary" href={withQuery("/command-center", { case: item.id })}>Open credit</Link></td></tr>)}</tbody></table>{!visibleCases.length && (cases.length ? <EmptyBlock><p>No credits match this search and filter.</p><button className="button primary" type="button" onClick={resetFilters}>Reset filters</button></EmptyBlock> : <LoadState loading={casesLoading} empty="No credits yet. Create the first case to establish the context boundary." />)}</div></section>
    <section className="panel cases-create"><div className="panel-header"><h2>Create case</h2></div><div className="panel-body">{writeAccess === "yes" ? <form onSubmit={createCase}><div className="field"><label htmlFor="case-name">Case name</label><input id="case-name" name="name" autoComplete="off" required placeholder="Q3 credit review…" /></div><div className="field"><label htmlFor="issuer">Issuer</label><input id="issuer" name="issuer" autoComplete="organization" required placeholder="Issuer legal name…" /></div><div className="field"><label htmlFor="sector">Sector</label><input id="sector" name="sector" autoComplete="off" placeholder="Business services…" /></div><button className={`button ${selectedCase ? "" : "primary"}`} type="submit" disabled={pendingAction === "create-case"}>{pendingAction === "create-case" ? "Creating…" : "Create case"}</button></form> : <WriteBlocked access={writeAccess} action="case creation" />}</div></section>
    {/* Fit truth: render the served fit when the wire carries one; claim NEEDS_SOURCE
        only when the case verifiably has zero sources (the server's own rule); stay
        neutral otherwise. The case wire now serves pathway_fit, so the fallback below
        is only for a deployment whose build predates it. */}
    <section className="panel cases-fit"><div className="panel-header"><h2>Pathway fit</h2></div><div className="panel-body">{selectedCase ? selectedCase.pathway_fit ? <><span className={`status ${selectedCase.pathway_fit.fit === "READY" ? "success" : "warning"}`}>{humanizeCode(selectedCase.pathway_fit.fit)}</span><p>{selectedCase.pathway_fit.message}</p></> : selectedCase.source_count === 0 ? <><span className="status warning">NEEDS SOURCE</span><p>Upload a source to see fit.</p></> : <p className="muted">Fit unavailable. Pathway fit is not served by this deployment.</p> : <div className="empty">Select a case to inspect pathway fit.</div>}</div></section>
    <section className="context-strip portfolio-contract-notice span-12" aria-labelledby="portfolio-contract-title"><strong id="portfolio-contract-title">Portfolio ordering is not yet governed.</strong><p>The register is unranked until the server supplies threshold distance, freshness, and material-change scores.</p></section>
  </div>;
}

function SourcesView({ writeAccess, selectedCase, artifactId, sourceId, upload, pendingAction, onOpenEvidence }: { writeAccess: WriteAccess; selectedCase: CaseRecord | null; artifactId: string; sourceId: string; upload: (event: FormEvent<HTMLFormElement>) => void; pendingAction: string; onOpenEvidence: (evidenceId: string, source: SourceRecord) => void }) {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [artifact, setArtifact] = useState<ArtifactRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [readySourceCaseId, setReadySourceCaseId] = useState("");
  const [artifactError, setArtifactError] = useState("");
  const [linkedEvidenceId, setLinkedEvidenceId] = useState("");
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [selectedBlockId, setSelectedBlockId] = useState("");
  const [search, setSearch] = useState("");
  const openedSourceQuery = useRef("");
  useEffect(() => {
    if (!selectedCase) return;
    let ignore = false;
    // The fetch boundary intentionally resets its loading and error state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true); setLoadError(""); setReadySourceCaseId(""); setArtifactError(""); setArtifact(null);
    void request<SourceRecord[]>(`/api/cases/${selectedCase.id}/sources`).then((next) => { if (!ignore) { setSources(next); setReadySourceCaseId(selectedCase.id); } }).catch((caught) => { if (!ignore) setLoadError(firstErrorMessage(caught, "Unable to load source objects")); }).finally(() => { if (!ignore) setLoading(false); });
    if (artifactId) void request<ArtifactRecord>(`/api/cases/${selectedCase.id}/artifacts/${artifactId}`).then((next) => { if (!ignore) setArtifact(next); }).catch((caught) => { if (!ignore) setArtifactError(firstErrorMessage(caught, "Unable to load evidence artifact")); });
    return () => { ignore = true; };
  }, [selectedCase, artifactId]);
  const evidenceRefs = useMemo(() => normalizeEvidenceRefs(artifact?.payload?.evidence_refs), [artifact]);
  const sourceById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const activeEvidenceId = linkedEvidenceId || selectedEvidenceId;
  const openEvidence = (evidenceId: string) => {
    const source = sourceById.get(evidenceId);
    if (!source) {
      setArtifactError(`Evidence ${evidenceId} is not in the active case source set.`);
      return;
    }
    setArtifactError("");
    setSelectedEvidenceId(evidenceId);
    onOpenEvidence(evidenceId, source);
  };
  useEffect(() => {
    if (!selectedCase || !sourceId || loading || readySourceCaseId !== selectedCase.id) return;
    const queryKey = `${selectedCase.id}:${sourceId}`;
    if (openedSourceQuery.current === queryKey) return;
    openedSourceQuery.current = queryKey;
    const source = sourceById.get(sourceId);
    if (!source) {
      // The requested ID stays scoped to the active case source set.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setArtifactError(`Evidence ${sourceId} is not in the active case source set.`);
      return;
    }
    // Exact source-query hydration is an external navigation boundary.
    setSelectedEvidenceId(sourceId);
    setSelectedSourceId(sourceId);
  }, [loading, readySourceCaseId, selectedCase, sourceById, sourceId]);
  const filteredSources = useMemo(() => {
    const query = search.trim().toLowerCase();
    return sources.filter((source) => !query || `${source.filename} ${source.id} ${source.sha256}`.toLowerCase().includes(query));
  }, [search, sources]);
  const selectedSource = filteredSources.find((source) => source.id === selectedSourceId) || filteredSources[0] || null;
  const selectedBlock = selectedSource?.blocks.find((block) => block.block_id === selectedBlockId) || selectedSource?.blocks[0] || null;
  return <div className="grid">
    {artifactId && <section className="panel span-12 evidence-focus"><div className="panel-header"><h2>Evidence focus</h2><span className="panel-meta">Artifact {artifact?.module_id || artifactId}</span></div><div className="panel-body">{artifact ? <ArtifactReader artifact={artifact} evidenceRefs={evidenceRefs} activeEvidenceId={activeEvidenceId} onOpenEvidence={openEvidence} onPreview={setLinkedEvidenceId} onPreviewEnd={() => setLinkedEvidenceId("")} /> : <LoadState loading={!artifactError && loading} error={artifactError} empty="No artifact details were returned." />}</div></section>}
    <section className="panel span-12 source-toolbar"><div className="panel-body"><div className="field"><label htmlFor="source-search">Search documents</label><input id="source-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filename, source id, or digest" /></div>{writeAccess !== "yes" ? <WriteBlocked access={writeAccess} action="governed source intake" /> : selectedCase ? <form onSubmit={upload}><div className="field"><label htmlFor="source-file">Add governed source</label><input id="source-file" name="file" type="file" accept=".pdf,.xlsx,.json,.txt,.md,.csv" required /></div><button className="button primary" type="submit" disabled={pendingAction === "upload"}>{pendingAction === "upload" ? "Uploading…" : "Upload and version"}</button></form> : null}</div></section>
    <section className="source-workspace span-12" aria-label="Source workspace">
      <aside className="source-register"><div className="source-region-head"><h2>Source register</h2><span className="mono muted">{loading ? "Loading…" : `${filteredSources.length} / ${sources.length}`}</span></div>{artifactError && !artifactId ? <StateNote tone="critical" live="alert">{artifactError}</StateNote> : null}{filteredSources.map((source) => <button id={`source-${source.id}`} className={`source-register-row ${selectedSource?.id === source.id ? "is-active" : ""}`} type="button" aria-pressed={selectedSource?.id === source.id} onClick={() => { setSelectedSourceId(source.id); setSelectedBlockId(""); }} key={source.id}><strong>{source.filename}</strong><span className="mono">{source.id} · {source.blocks.length} blocks</span><span className={`status ${source.blocks.length ? "success" : "warning"}`}>{source.blocks.length ? "Extracted" : "No blocks"}</span></button>)}{!filteredSources.length ? <LoadState loading={loading} error={loadError} empty={sources.length ? "No documents match this search." : "No source objects in this credit."} /> : null}</aside>
      <section className="source-reader" aria-labelledby="source-reader-title">{selectedSource ? <><div className="meta-label">{selectedSource.id} · immutable source object</div><h2 id="source-reader-title">{selectedSource.filename}</h2><div className="source-document-blocks">{selectedSource.blocks.slice(0, 40).map((block) => <article className={selectedBlock?.block_id === block.block_id ? "source-document-block is-selected" : "source-document-block"} id={`block-${selectedSource.id}-${block.block_id}`} key={block.block_id}><button type="button" onClick={() => setSelectedBlockId(block.block_id)} aria-pressed={selectedBlock?.block_id === block.block_id}><span className="meta-label">{block.block_id} · {formatBlockLocator(block.locator)}</span><span>{block.text || "No extracted text."}</span></button></article>)}</div>{selectedSource.blocks.length > 40 ? <p className="muted">Showing the first 40 of {selectedSource.blocks.length} extracted blocks.</p> : null}</> : <LoadState loading={loading} empty={loadError ? "Source reader unavailable while the source register could not be loaded." : "Select a source document."} />}</section>
      <aside className="source-support"><div className="meta-label">Evidence support</div><h2>Selected source authority</h2>{selectedSource ? <><dl className="state-facts"><dt>Source</dt><dd className="mono">{selectedSource.id}</dd><dt>SHA-256</dt><dd><IdentityValue value={selectedSource.sha256} /></dd><dt>Blocks</dt><dd className="num">{selectedSource.blocks.length}</dd>{selectedBlock ? <><dt>Selected block</dt><dd className="mono">{selectedBlock.block_id}</dd><dt>Locator</dt><dd className="mono">{formatBlockLocator(selectedBlock.locator)}</dd></> : null}</dl><button className="button small" type="button" onClick={() => openEvidence(selectedSource.id)}>Open evidence context</button></> : <p className="muted">No source selected.</p>}<div className="source-coverage-gate"><Unavailable title="Claim coverage" context="A normalized claim-to-source map is not served by this deployment. Source blocks remain readable above." /></div></aside>
    </section>
  </div>;
}

// The artifact reader: the full module output — summary, narrative, provenance,
// lineage, and evidence citations — readable before a snapshot is accepted.
// Deterministic payloads (markdown null) render the typed narrative fields;
// agent payloads render the canonical six-section markdown, host frontmatter
// stripped, with no HTML injection surface.
function ArtifactReader({ artifact, evidenceRefs, activeEvidenceId, onOpenEvidence, onPreview, onPreviewEnd }: { artifact: ArtifactRecord; evidenceRefs: NormalizedEvidenceRef[]; activeEvidenceId: string; onOpenEvidence: (evidenceId: string) => void; onPreview: (evidenceId: string) => void; onPreviewEnd: () => void }) {
  const payload = artifact.payload || undefined;
  const blocks = useMemo(() => (artifact.markdown ? markdownBlocks(artifact.markdown) : []), [artifact.markdown]);
  const summary = payload?.summary;
  const takeaway = payload?.narrative?.takeaway;
  const exceptions = payload?.narrative?.exceptions;
  const upstreamDigests = payload?.lineage?.upstream_digests || [];
  const inputFingerprint = payload?.lineage?.input_fingerprint || artifact.input_fingerprint;
  const loanUniverse = payload?.inputs?.loan_universe;
  // The module's own name leads; the id stays beside it, because the id is what an
  // artifact, a run event and an audit row are keyed by.
  const moduleName = moduleLabel(artifact.module_id);
  return <div className="flow artifact-reader">
    <div className="artifact-provenance">
      {moduleName === artifact.module_id ? null : <span>{moduleName}</span>}
      <span className="mono">{artifact.module_id}</span>
      {payload?.status && <span className={`status ${payload.status === "COMPLETE" ? "success" : "warning"}`}>{humanizeCode(payload.status)}</span>}
      {payload?.authority && <span className="meta-label">{humanizeCode(payload.authority)}</span>}
      {payload?.confidence?.band && <span className="meta-label">Confidence {humanizeCode(payload.confidence.band)}</span>}
      {payload?.confidence?.qa_status && <span className="meta-label">QA {humanizeCode(payload.confidence.qa_status)}</span>}
    </div>
    {artifact.markdown ? <>
      <h3>Module output</h3>
      <div className="artifact-markdown">{blocks.map((block, index) => block.kind === "heading" ? <h4 key={`block:${index}`}>{block.text}</h4> : <p key={`block:${index}`}>{block.text}</p>)}</div>
    </> : <>
      <p>{summary || takeaway || "No artifact summary available."}</p>
      {takeaway && takeaway !== summary && <p>{takeaway}</p>}
      {payload?.narrative?.basis && <p className="muted">{payload.narrative.basis}</p>}
      {exceptions && <div className="callout warning"><strong>Exceptions</strong><p>{exceptions}</p></div>}
    </>}
    <h3>Lineage</h3>
    <dl className="state-facts">
      <dt>Artifact digest</dt><dd><IdentityValue value={artifact.digest} /></dd>
      {inputFingerprint && <><dt>Input fingerprint</dt><dd><IdentityValue value={inputFingerprint} /></dd></>}
      <dt>Upstream digests</dt><dd>{upstreamDigests.length ? <ul className="artifact-digest-list">{upstreamDigests.map((digest, index) => <li key={`upstream:${index}`}><IdentityValue value={digest} /></li>)}</ul> : <span className="muted">None</span>}</dd>
      {payload?.provenance?.executor && <><dt>Executor</dt><dd><IdentityValue value={payload.provenance.executor} /></dd></>}
      {payload?.provenance?.profile_id && <><dt>Profile</dt><dd><IdentityValue value={payload.provenance.profile_id} /></dd></>}
      {payload?.provenance?.selection_id && <><dt>Selection</dt><dd><IdentityValue value={payload.provenance.selection_id} /></dd></>}
    </dl>
    {loanUniverse?.rows && <><h3>Loan universe</h3><ArtifactDataTable label="Pinned loan universe" value={loanUniverse} /></>}
    <h3>Evidence</h3>
    {evidenceRefs.length ? <div className="evidence-list" aria-label="Artifact evidence">{evidenceRefs.map((ref) => <span className="evidence-ref" key={ref.sourceId}><EvidenceChip evidenceId={ref.sourceId} linkedId={activeEvidenceId} onOpen={onOpenEvidence} onPreview={onPreview} onPreviewEnd={onPreviewEnd} />{ref.blockIds.length > 0 && <span className="mono muted">{ref.blockIds.join(" · ")}</span>}</span>)}</div> : <p className="muted">No evidence citations in this artifact.</p>}
  </div>;
}

function ArtifactDataTable({ value, label, maxRows = 80 }: { value: unknown; label: string; maxRows?: number }) {
  const flattened = flattenValue(value);
  const rows = flattened.slice(0, maxRows);
  if (!rows.length) return <p className="muted">No pinned values are available.</p>;
  return <div className="table-wrap" tabIndex={0} role="region" aria-label={label}>
    <table><thead><tr><th scope="col">Field</th><th scope="col">Value</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label}><th scope="row">{row.label}</th><td className="num">{displayValue(row.value)}</td></tr>)}</tbody></table>
    {flattened.length > rows.length && <p className="muted">Showing the first {rows.length} of {flattened.length} pinned values.</p>}
  </div>;
}

// The visible chip stays one word, which is what the desk reads; the sr-only prefix
// is what stops a screen reader announcing a bare "succeeded" with no subject.
function RunStatusBadge({ run }: { run: RunRecord | null }) {
  return <span role="status" aria-live="polite" aria-atomic="true" className={run ? `status ${run.status === "succeeded" ? "success" : run.status === "failed" ? "critical" : "warning"}` : "sr-only"}>{run ? <span className="sr-only">Run status: </span> : null}{run?.error?.code === "PLAN_APPROVAL_REQUIRED" ? "Pending approval" : run?.status || ""}</span>;
}

// Module progress is what actually changes while a run executes, and it lives in the
// DAG tiles and the module list — neither of which is a live region, so a screen
// reader learned only that the DOM had changed (WCAG 4.1.3). This carries the same
// progress those tiles show, politely and without touching the visual language.
function RunProgressAnnouncer({ run }: { run: RunRecord | null }) {
  const total = run?.nodes.length ?? 0;
  const complete = run?.nodes.filter((node) => node.status === "succeeded").length ?? 0;
  const running = run?.nodes.find((node) => node.status === "running");
  return <p className="sr-only" role="status">{run ? `${complete} of ${total} ${total === 1 ? "module" : "modules"} complete.${running ? ` ${moduleLabel(running.module_id)} running.` : ""}` : ""}</p>;
}

// The acceptance ceremony: a digest-bound <dialog> stating exactly what becomes the
// case's latest accepted authority and what it replaces. Open/close follows the WorkbenchShell
// drawer pattern — capture the trigger before showModal(), rAF-focus the heading,
// restore focus on close. The primary button keeps the DAG trigger's accessible name.
function AcceptDialog({ open, run, replaces, pending, onConfirm, onClose }: { open: boolean; run: RunRecord | null; replaces: Snapshot | null; pending: boolean; onConfirm: () => void; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!open) {
      if (dialog.open) dialog.close();
      return;
    }
    if (!dialog.open) {
      triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    }
    const frame = window.requestAnimationFrame(() => headingRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);
  const close = () => {
    onClose();
    const trigger = triggerRef.current;
    window.requestAnimationFrame(() => trigger?.focus());
  };
  const pathwayLabel = run ? pathways.find(([value]) => value === run.plan.pathway)?.[1] || run.plan.pathway : "";
  const slots = acceptanceSlotSummary(run?.nodes || [], replaces?.artifacts || []);
  return <dialog ref={dialogRef} aria-labelledby="accept-dialog-title" onClose={close}>
    <div className="dialog-body">
      <div className="panel-header"><h2 id="accept-dialog-title" ref={headingRef} tabIndex={-1}>Accept analytical snapshot</h2></div>
      {run && <>
        <dl className="state-facts">
          <dt>Run</dt><dd className="mono">{run.id}</dd>
          <dt>Pathway</dt><dd>{pathwayLabel} · {run.plan.depth}</dd>
          <dt>Source set</dt><dd><span>{run.plan.source_set_version == null ? "Unavailable" : `v${run.plan.source_set_version}`}</span>{run.plan.source_set_id ? <div className="mono muted">{run.plan.source_set_id}</div> : null}{run.plan.source_set_digest ? <div className="mono muted">{run.plan.source_set_digest}</div> : null}</dd>
          <dt>New authority slots</dt><dd><strong className="num">{slots.added.length}</strong><div className="mono muted">{slots.added.join(" · ") || "None"}</div></dd>
          <dt>Existing slots replaced</dt><dd><strong className="num">{slots.replaced.length}</strong><div className="mono muted">{slots.replaced.join(" · ") || "None"}</div></dd>
          <dt>Slots removed</dt><dd><strong className="num">{slots.removed.length}</strong><div className="mono muted">{slots.removed.join(" · ") || "None"}</div></dd>
          <dt>Replaces snapshot digest</dt><dd>{replaces ? <><span className="mono">{replaces.digest}</span><div className="muted">Source set {replaces.source_set_version == null ? "Unavailable" : `v${replaces.source_set_version}`}{replaces.source_set_id ? ` · ${replaces.source_set_id}` : ""}</div></> : <span className="muted">No accepted snapshot</span>}</dd>
        </dl>
        <p>Accepting binds these module slots as the case&apos;s latest accepted authority. Artifact digests are verified by the server at acceptance. The visible lens remains separately governed; a pinned lens moves only through an explicit switch.</p>
        <div className="top-actions">
          <button className="button primary" type="button" disabled={pending} onClick={onConfirm}>Accept analytical snapshot</button>
          <button className="button small" type="button" onClick={() => dialogRef.current?.close()}>Cancel</button>
        </div>
      </>}
    </div>
  </dialog>;
}

function DraftDiscardDialog({ open, detail, onConfirm, onClose }: { open: boolean; detail: string; onConfirm: () => void; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!open) {
      if (dialog.open) dialog.close();
      return;
    }
    if (!dialog.open) {
      triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    }
    const frame = window.requestAnimationFrame(() => headingRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [open]);
  const close = () => {
    onClose();
    const trigger = triggerRef.current;
    window.requestAnimationFrame(() => trigger?.focus());
  };
  return <dialog ref={dialogRef} aria-labelledby="discard-dialog-title" onClose={close}>
    <div className="dialog-body">
      <div className="panel-header"><h2 id="discard-dialog-title" ref={headingRef} tabIndex={-1}>Discard draft changes?</h2></div>
      <p>{detail}</p>
      <p className="muted">This removes only local, uncommitted changes. Saved and signed versions remain unchanged.</p>
      <div className="top-actions">
        <button className="button primary" type="button" onClick={onConfirm}>Discard changes</button>
        <button className="button small" type="button" onClick={() => dialogRef.current?.close()}>Keep editing</button>
      </div>
    </div>
  </dialog>;
}

// A route node names its module and keeps its id: the name is what an analyst
// reads, the id is what the run event, the artifact and the audit row are keyed by.
// An id the registry carries no name for shows once, as itself.
function ModuleIdentity({ moduleId }: { moduleId: string }) {
  const name = moduleLabel(moduleId);
  return <><strong>{name}</strong>{name === moduleId ? null : <div className="mono muted">{moduleId}</div>}</>;
}

// Shared by Run Console and the inline panels on Cases and Deep-Dive. `approvalSlot`
// is how Run Console injects the full ResearchPlanView; inline surfaces route to it
// instead, since plan approval is a Run Console responsibility.
function RunStatus({ writeAccess, caseId, run, runLoading, runError, acceptRun, acceptedSnapshotId, visibleSnapshotId, switchRequired, pendingAction, approvalSlot, resumeSlot }: { writeAccess: WriteAccess; caseId: string; run: RunRecord | null; runLoading: boolean; runError: string; acceptRun: () => void; acceptedSnapshotId: string; visibleSnapshotId: string; switchRequired: boolean; pendingAction: string; approvalSlot: ReactNode; resumeSlot: ReactNode }) {
  if (!run) return <LoadState loading={runLoading} error={runError} empty="No current execution. Select a purpose and depth to create an immutable plan." />;
  const complete = run.nodes.filter((node) => node.status === "succeeded").length;
  const current = (run.status === "queued" || run.status === "running")
    ? run.nodes.find((node) => node.status === "running") || run.nodes.find((node) => node.status === "pending")
    : undefined;
  const progress = run.nodes.length ? Math.round(complete / run.nodes.length * 100) : 0;
  const progressLabel = current ? `${moduleLabel(current.module_id)} · ${current.status}` : run.status === "succeeded" ? "Execution complete" : run.status === "failed" ? "Execution stopped" : "Execution paused";
  let acceptance: ReactNode;
  if (acceptedSnapshotId) {
    acceptance = <>
      <span className="status success">Latest accepted authority</span>
      <span className="mono muted">{acceptedSnapshotId}</span>
      {switchRequired
        ? <p>Visible lens remains on <span className="mono">{visibleSnapshotId || "a different snapshot"}</span> until explicitly switched.</p>
        : <p>Visible lens matches the latest accepted authority.</p>}
    </>;
  } else if (run.status === "succeeded") {
    acceptance = <>
      <span className="status warning">Ready for acceptance</span>
      <p>Review the exact authority change, then accept this analytical snapshot.</p>
      {writeAccess === "yes"
        ? <button className="button primary" disabled={pendingAction === "accept-run"} onClick={acceptRun}>{pendingAction === "accept-run" ? "Accepting…" : "Accept analytical snapshot"}</button>
        : <p className="muted">{writeAccess === "unknown" ? "Confirming access…" : "Acceptance is an analyst action."}</p>}
    </>;
  } else if (run.status === "failed") {
    acceptance = <>
      <span className="status critical">Acceptance blocked</span>
      <p>Review the execution failure, then compile a new route.</p>
    </>;
  } else if (run.status === "paused") {
    acceptance = <>
      <span className="status warning">Acceptance blocked</span>
      {run.error?.code === "SOURCE_SET_EMPTY" ? <><p>Upload governed source material before execution can continue.</p><Link className="button small" href={withQuery("/sources/", { case: caseId })}>Open Sources</Link></>
        : run.error?.code === "PLAN_APPROVAL_REQUIRED" ? <p>Review and approve the persisted research plan below.</p>
          : <><p>Resolve the paused execution before acceptance.</p>{resumeSlot}</>}
    </>;
  } else {
    acceptance = <>
      <span className="status running">Acceptance waiting</span>
      <p>{complete} of {run.nodes.length} module slots complete. Acceptance unlocks only after the route succeeds.</p>
    </>;
  }
  // `flow` here, not on the caller: the acceptance control must never abut the
  // route it accepts, whichever panel body this block is mounted in.
  return <div className="flow">
    <RunProgressAnnouncer run={run} />
    <div className="run-progress" role="progressbar" aria-label="Execution progress" aria-valuemin={0} aria-valuemax={run.nodes.length} aria-valuenow={complete} aria-valuetext={`${complete} of ${run.nodes.length} modules complete${current ? `; ${moduleLabel(current.module_id)} ${current.status}` : ""}`}><div><span>{progressLabel}</span><span className="mono">{complete}/{run.nodes.length}</span></div><span className="run-progress-track" aria-hidden="true"><span style={{ width: `${progress}%` }} /></span></div>
    <div className="dag">{run.nodes.map((node, index) => <div className="dag-step" key={node.id}>{index > 0 && <span className="dag-edge" aria-hidden="true">→</span>}{node.artifact_id ? <Link className="dag-node" href={withQuery("/sources/", { case: caseId, artifact: node.artifact_id })}><ModuleIdentity moduleId={node.module_id} /><div className={`status ${nodeStatusTone(node.status)}`}>{node.status}</div><span className="dag-node-open">Open output</span></Link> : <div className="dag-node"><ModuleIdentity moduleId={node.module_id} /><div className={`status ${nodeStatusTone(node.status)}`}>{node.status}</div><span className="dag-node-open dag-node-placeholder" aria-hidden="true">Open output</span></div>}</div>)}</div>
    <div className="approval-panel run-acceptance" data-run-acceptance>{acceptance}</div>
    {run.status === "failed" && run.error && <StateNote tone="critical" live="alert" code={run.error.code}>{run.error.message || "Run exception"}</StateNote>}
    {run.status === "paused" && run.error?.code === "PLAN_APPROVAL_REQUIRED" && approvalSlot}
    {run.status === "paused" && !["SOURCE_SET_EMPTY", "PLAN_APPROVAL_REQUIRED"].includes(run.error?.code || "") && <StateNote tone="warning" live="status" code={run.error?.code || "RUN_PAUSED"}>{run.error?.message || "Run paused."}</StateNote>}
  </div>;
}

function RunConsole({ writeAccess, caseId, selectedCase, run, runLoading, runError, startRun, acceptRun, acceptedSnapshotId, visibleSnapshotId, switchRequired, approveResearchPlan, approvalUnavailable, pendingAction, resumeSlot }: { writeAccess: WriteAccess; caseId: string; selectedCase: CaseRecord | null; run: RunRecord | null; runLoading: boolean; runError: string; startRun: (event: FormEvent<HTMLFormElement>) => void; acceptRun: () => void; acceptedSnapshotId: string; visibleSnapshotId: string; switchRequired: boolean; approveResearchPlan: (planHash: string) => void; approvalUnavailable: boolean; pendingAction: string; resumeSlot: ReactNode }) {
  const [pathway, setPathway] = useState("EARNINGS_UPDATE");
  const [depth, setDepth] = useState("screen");
  const deepResearchAvailable = selectedCase?.deep_research_available === true;
  const deepResearchReason = selectedCase?.deep_research_unavailable_reason || "Deep Research availability is not served for this credit.";
  // The served cut, not a second copy of it. Deep Research keeps its own
  // actor-specific gate above; every other pathway is offered only when the
  // engine says it will start one. A server that serves no list (older build)
  // leaves them all selectable, which is the pre-existing behaviour.
  const cut = selectedCase?.available_pathways;
  const pathwayEnabled = (value: string) => value === "DEEP_RESEARCH" ? deepResearchAvailable : !cut || cut.includes(value);
  const outsideCut = pathways.filter(([value]) => value !== "DEEP_RESEARCH" && !pathwayEnabled(value)).map(([, label]) => label);
  const approvalPlan = run?.status === "paused" && run.error?.code === "PLAN_APPROVAL_REQUIRED" ? run.research?.proposed_plan : null;
  const approvalHash = run?.status === "paused" && run.error?.code === "PLAN_APPROVAL_REQUIRED" ? run.research?.proposed_plan_hash : null;
  return <div className="grid">
    <section className="panel span-4">
      <div className="panel-header"><h2>Compile route</h2><span className="panel-meta">Immutable plan</span></div>
      <div className="panel-body flow">
        {writeAccess === "yes" ? <form onSubmit={startRun}>
          <div className="field">
            <label htmlFor="pathway">Purpose</label>
            <select id="pathway" name="pathway" value={pathway} aria-describedby={[!deepResearchAvailable ? "deep-research-availability" : "", outsideCut.length ? "pathway-availability" : ""].filter(Boolean).join(" ") || undefined} onChange={(event) => { setPathway(event.target.value); if (event.target.value === "DEEP_RESEARCH") setDepth("full"); }}>
              {pathways.map(([value, label]) => <option value={value} disabled={!pathwayEnabled(value)} key={value}>{label}</option>)}
            </select>
          </div>
          {!deepResearchAvailable && <p className="muted" id="deep-research-availability">{deepResearchReason}</p>}
          {outsideCut.length > 0 && <p className="muted" id="pathway-availability">{`${outsideCut.join(", ")} ${outsideCut.length === 1 ? "is" : "are"} outside this deployment's cut.`}</p>}
          <div className="field">
            <label htmlFor="depth">Depth</label>
            <select id="depth" name="depth" value={depth} onChange={(event) => setDepth(event.target.value)}><option value="screen" disabled={pathway === "DEEP_RESEARCH"}>Screen</option><option value="full">Full</option></select>
          </div>
          {pathway === "DEEP_RESEARCH" && <fieldset className="research-brief">
            <legend>Bounded research brief</legend>
            <div className="field"><label htmlFor="research-question">Research question</label><textarea id="research-question" name="research_question" maxLength={400} required /></div>
            <div className="field"><label htmlFor="decision-context">Decision context</label><textarea id="decision-context" name="decision_context" maxLength={400} required /></div>
            <div className="field"><label htmlFor="as-of-date">As-of date</label><input id="as-of-date" name="as_of_date" type="date" required /></div>
            <div className="field"><label htmlFor="time-horizon">Time horizon</label><input id="time-horizon" name="time_horizon" maxLength={200} required /></div>
            <div className="field"><label htmlFor="must-answer">Must-answer lines</label><textarea id="must-answer" name="must_answer" maxLength={2009} aria-describedby="research-list-bounds" /></div>
            <div className="field"><label htmlFor="exclusions">Exclusion lines</label><textarea id="exclusions" name="exclusions" maxLength={2009} aria-describedby="research-list-bounds" /></div>
            <p className="muted" id="research-list-bounds">One item per line; 10 items combined, 200 characters per item.</p>
          </fieldset>}
          <button className="button primary" type="submit" disabled={!caseId || pendingAction === "start-run"}>{pendingAction === "start-run" ? "Compiling…" : "Compile and run"}</button>
        </form> : <WriteBlocked access={writeAccess} action="compiling a route" />}
        <div className="callout">Every route begins by parsing your sources; the readiness check then runs against that exact parse.</div>
      </div>
    </section>
    <section className="panel span-8">
      <div className="panel-header"><h2>Execution route</h2><RunStatusBadge run={run} /></div>
      <div className="panel-body flow"><RunStatus writeAccess={writeAccess} caseId={caseId} run={run} runLoading={runLoading} runError={runError} acceptRun={acceptRun} acceptedSnapshotId={acceptedSnapshotId} visibleSnapshotId={visibleSnapshotId} switchRequired={switchRequired} pendingAction={pendingAction} resumeSlot={resumeSlot} approvalSlot={approvalPlan && approvalHash ? <ResearchPlanView plan={approvalPlan} planHash={approvalHash} approving={pendingAction === "approve-research-plan"} approvalUnavailable={approvalUnavailable} onApprove={approveResearchPlan} /> : <StateBlock tone="warning" live="status" code="PLAN_APPROVAL_REQUIRED" body="The persisted approval plan is unavailable; approval remains blocked." />} /></div>
    </section>
  </div>;
}

function ResearchPlanView({ plan, planHash, approving, approvalUnavailable, onApprove }: { plan: ResearchPlan; planHash: string; approving: boolean; approvalUnavailable: boolean; onApprove: (planHash: string) => void }) {
  const scalar = (value: string | number | null | undefined) => value === "" || value == null ? <span className="muted">None</span> : value;
  return <section className="research-plan" role="region" aria-labelledby="research-plan-heading">
    <h3 id="research-plan-heading">Proposed research plan</h3>
    <p>Review the complete deterministic plan. Approval binds execution to the exact hash shown here.</p>
    <dl className="research-plan-facts">
      <dt>Plan hash</dt><dd className="mono">{planHash}</dd>
      <dt>Methodology build</dt><dd className="mono">{scalar(plan.methodology_build_id)}</dd>
      <dt>Brief digest</dt><dd className="mono">{scalar(plan.brief_digest)}</dd>
      <dt>Source set</dt><dd><span className="mono">{scalar(plan.source_set.id)}</span> · version {scalar(plan.source_set.version)}</dd>
      <dt>Upstream artifacts</dt><dd>{plan.upstream_artifacts.length ? <ul>{plan.upstream_artifacts.map((artifact, artifactIndex) => <li key={`upstream:${artifactIndex}`}><strong>{scalar(artifact.module_id)}</strong> · <span className="mono">{scalar(artifact.artifact_id)}</span> · <span className="mono">{scalar(artifact.digest)}</span></li>)}</ul> : <span className="muted">Empty</span>}</dd>
      <dt>Scope</dt><dd>Type {scalar(plan.scope.type)} · key <span className="mono">{scalar(plan.scope.key)}</span> · source mode {scalar(plan.scope.source_mode)}</dd>
    </dl>
    <h4>Workstreams</h4>
    {plan.workstreams.length ? <ol className="research-workstreams">{plan.workstreams.map((workstream, workstreamIndex) => <li key={`workstream:${workstreamIndex}`}>
      <h5>{scalar(workstream.id)} · {scalar(workstream.kind)}</h5>
      <dl className="research-plan-facts">
        <dt>ID</dt><dd className="mono">{scalar(workstream.id)}</dd>
        <dt>Kind</dt><dd>{scalar(workstream.kind)}</dd>
        <dt>Question</dt><dd>{scalar(workstream.question)}</dd>
        <dt>Assigned questions</dt><dd>{workstream.assigned_questions?.length ? <ul>{workstream.assigned_questions.map((item, index) => <li key={`assigned:${index}`}>{scalar(item)}</li>)}</ul> : <span className="muted">Empty</span>}</dd>
        <dt>Perspective</dt><dd>{scalar(workstream.perspective)}</dd>
        <dt>Hypothesis</dt><dd>{scalar(workstream.hypothesis)}</dd>
        <dt>Evidence needs</dt><dd>{workstream.evidence_needs.length ? <ul>{workstream.evidence_needs.map((item, index) => <li key={`evidence:${index}`}>{scalar(item)}</li>)}</ul> : <span className="muted">Empty</span>}</dd>
        <dt>Source classes</dt><dd>{workstream.source_classes.length ? <ul>{workstream.source_classes.map((item, index) => <li className="mono" key={`source:${index}`}>{scalar(item)}</li>)}</ul> : <span className="muted">Empty</span>}</dd>
        <dt>Disconfirming test</dt><dd>{scalar(workstream.disconfirming_test)}</dd>
        <dt>Completion test</dt><dd>{scalar(workstream.completion_test)}</dd>
        <dt>Effort cap</dt><dd>{scalar(workstream.effort_cap)}</dd>
      </dl>
    </li>)}</ol> : <p className="muted">Empty</p>}
    {approvalUnavailable
      ? <Unavailable title="Research plan approval" context="The plan above stays readable; execution remains paused on this run." />
      : <button className="button primary" type="button" disabled={approving} onClick={() => onApprove(planHash)}>{approving ? "Approving…" : "Approve research plan"}</button>}
  </section>;
}

function DeepDive({ writeAccess, selectedCase, question, caseId, run, onSwitchSnapshot }: { writeAccess: WriteAccess; selectedCase: CaseRecord | null; question: string; caseId: string; run: RunRecord | null; onSwitchSnapshot: (snapshotId: string) => Promise<SnapshotView | null> }) {
  const selectedCaseId = selectedCase?.id || "";
  const [view, setView] = useState<SnapshotView | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState("");
  const [artifactError, setArtifactError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const loadGeneration = useRef(0);
  useEffect(() => {
    const generation = ++loadGeneration.current;
    let ignore = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setView(null); setArtifacts([]); setSelectedArtifactId(""); setArtifactError(""); setMessage(""); setLoadError(""); setLoading(Boolean(selectedCaseId));

    if (selectedCaseId) {
      void (async () => {
        try {
          const next = await request<SnapshotView>(`/api/cases/${selectedCaseId}/snapshot`);
          if (ignore || generation !== loadGeneration.current) return;
          const expected = next?.accepted?.artifacts ?? [];
          const loaded = await Promise.all(expected.map(({ id }) =>
            request<ArtifactRecord>(`/api/cases/${selectedCaseId}/artifacts/${id}`).catch(() => null)
          ));
          if (ignore || generation !== loadGeneration.current) return;
          const available = loaded.filter((item): item is ArtifactRecord => item !== null);
          setView(next);
          setArtifacts(available);
          if (available.length !== expected.length) setArtifactError("Some accepted module outputs could not be loaded.");
        } catch (caught) {
          if (ignore || generation !== loadGeneration.current || caught instanceof DOMException && caught.name === "AbortError") return;
          setLoadError(firstErrorMessage(caught, "Unable to load snapshot authority"));
        } finally {
          if (!ignore && generation === loadGeneration.current) setLoading(false);
        }
      })();
    }

    return () => { ignore = true; loadGeneration.current += 1; };
  }, [selectedCaseId]);
  const switchSnapshot = async () => {
    if (!selectedCase || !view?.latest_accepted) return;
    const generation = ++loadGeneration.current;
    const selectedCaseId = selectedCase.id;
    const snapshotId = view.latest_accepted.id;
    setLoading(true); setLoadError(""); setArtifactError(""); setMessage("");

    try {
      const next = await onSwitchSnapshot(snapshotId);
      if (!next || generation !== loadGeneration.current) return;
      const expected = next.accepted?.artifacts ?? [];
      const loaded = await Promise.all(expected.map(({ id }) =>
        request<ArtifactRecord>(`/api/cases/${selectedCaseId}/artifacts/${id}`).catch(() => null)
      ));
      if (generation !== loadGeneration.current) return;
      const available = loaded.filter((item): item is ArtifactRecord => item !== null);
      setView(next);
      setArtifacts(available);
      setSelectedArtifactId("");
      if (available.length !== expected.length) setArtifactError("Some accepted module outputs could not be loaded.");
      setMessage("Visible snapshot switched.");
    } catch (caught) {
      if (generation !== loadGeneration.current || caught instanceof DOMException && caught.name === "AbortError") return;
      setArtifactError(firstErrorMessage(caught, "Unable to switch snapshot"));
    } finally {
      if (generation === loadGeneration.current) setLoading(false);
    }
  };
  const snapshot = view?.accepted;
  const selectedArtifact = artifacts.find((item) => item.id === selectedArtifactId) || artifacts.find((item) => item.module_id === "CP-2") || artifacts[0] || null;
  const selectedBlocks = selectedArtifact?.markdown ? markdownBlocks(selectedArtifact.markdown) : [];
  const selectedEvidence = normalizeEvidenceRefs(selectedArtifact?.payload?.evidence_refs);
  if (loading) return <div className="panel"><div className="panel-body"><LoadState loading /></div></div>;
  if (!snapshot) return <div className="panel"><div className="panel-body">{loading || loadError ? <LoadState loading={loading} error={loadError} /> : <StateBlock shape="action" title="Analysis unavailable" body="No accepted snapshot. Run the selected route, inspect exceptions, then accept it explicitly." action={{ label: "Open analysis run", href: withQuery("/run-console", { case: selectedCase?.id, run: run?.id }) }} />}</div></div>;
  return <div className="analysis-screen">
    {question ? <section className="context-strip"><strong>Evidence request</strong><p>{question}</p></section> : null}
    {view?.switch_required ? <div className="analysis-switch callout warning"><strong>New accepted execution available.</strong><p>This reader remains on snapshot <IdentityValue value={snapshot.id} /> until authority is switched explicitly.</p>{writeAccess === "yes" ? <button className="button small" type="button" onClick={switchSnapshot}>Switch visible snapshot</button> : null}</div> : null}
    {message ? <MutationReceipt>{message}</MutationReceipt> : null}
    {artifactError ? <StateNote tone="critical" live="alert">{artifactError}</StateNote> : null}
    <div className="analysis-reader-shell">
      <nav className="analysis-toc" aria-label="Accepted analysis modules"><div className="meta-label">Accepted modules</div>{artifacts.map((artifact) => <button type="button" aria-pressed={selectedArtifact?.id === artifact.id} className={selectedArtifact?.id === artifact.id ? "is-active" : ""} onClick={() => setSelectedArtifactId(artifact.id)} key={artifact.id}><span>{moduleLabel(artifact.module_id)}</span><span className="mono">{artifact.module_id}</span></button>)}<Link className="button small" href={withQuery("/run-console", { case: caseId, run: run?.id })}>Open selected run</Link></nav>
      <article className="analysis-reader" aria-labelledby="analysis-artifact-title">{selectedArtifact ? <><div className="meta-label">Accepted {formatDate(snapshot.accepted_at)} · Source set v{snapshot.source_set_version ?? "Unavailable"}</div><h2 id="analysis-artifact-title">{moduleLabel(selectedArtifact.module_id)}</h2><p className="analysis-lead">{selectedArtifact.payload?.narrative?.takeaway || selectedArtifact.payload?.summary || selectedBlocks.find((block) => block.kind === "paragraph")?.text || "No module summary is available."}</p>{selectedArtifact.markdown ? <div className="analysis-copy">{selectedBlocks.map((block, index) => block.kind === "heading" ? <h3 key={`${block.text}:${index}`}>{block.text}</h3> : <p key={`${block.text}:${index}`}>{block.text}</p>)}</div> : <div className="analysis-copy">{selectedArtifact.payload?.narrative?.basis ? <><h3>Basis</h3><p>{selectedArtifact.payload.narrative.basis}</p></> : null}{selectedArtifact.payload?.narrative?.exceptions ? <div className="callout warning"><strong>Exceptions</strong><p>{selectedArtifact.payload.narrative.exceptions}</p></div> : null}</div>}<dl className="analysis-provenance"><dt className="meta-label">Artifact</dt><dd><IdentityValue value={selectedArtifact.id} /></dd><dt className="meta-label">Digest</dt><dd><IdentityValue value={selectedArtifact.digest} /></dd><dt className="meta-label">Input fingerprint</dt><dd><IdentityValue value={selectedArtifact.payload?.lineage?.input_fingerprint || selectedArtifact.input_fingerprint || "Unavailable"} /></dd></dl></> : <LoadState loading={loading} error={loadError} empty="No accepted module output is available." />}</article>
      <aside className="analysis-evidence"><div className="meta-label">Evidence rail</div><h2>{selectedEvidence.length} cited source{selectedEvidence.length === 1 ? "" : "s"}</h2>{selectedEvidence.map((ref, index) => <div className="analysis-evidence-card" key={`${ref.sourceId}:${index}`}><Link href={withQuery("/sources", { case: caseId, source: ref.sourceId })}>{ref.sourceId}</Link><span className="mono muted">{ref.blockIds.length ? ref.blockIds.join(" · ") : "Source-level reference"}</span></div>)}{selectedArtifact && !selectedEvidence.length ? <Unavailable title="Evidence citations" context="This accepted module output contains no normalized evidence references." /> : null}<div className="analysis-evidence-authority"><span className="meta-label">Visible authority</span><IdentityValue value={snapshot.digest} /></div></aside>
    </div>
  </div>;
}

const loanColumns: { key: keyof LoanRow; label: string; numeric?: boolean; signed?: boolean }[] = [
  { key: "company", label: "Company" }, { key: "borrower_name", label: "Borrower" }, { key: "business_description", label: "Business description" }, { key: "sector", label: "Sector" }, { key: "sub_sector", label: "Sub-sector" }, { key: "sub_group", label: "Sub-group" }, { key: "public_private", label: "Public / private" },
  { key: "bloomberg_loan_id", label: "Bloomberg" }, { key: "figi", label: "FIGI" },
  { key: "loan_type", label: "Loan type" }, { key: "ranking", label: "Ranking" }, { key: "ratings", label: "Ratings" }, { key: "size_mn", label: "Size ($mn)", numeric: true }, { key: "margin_bps", label: "Margin (bps)", numeric: true }, { key: "maturity_date", label: "Maturity" },
  { key: "bid_points", label: "Bid (pts)", numeric: true }, { key: "ask_points", label: "Ask (pts)", numeric: true }, { key: "change_1d_points", label: "Δ 1D (pts)", numeric: true, signed: true }, { key: "change_1w_points", label: "Δ 1W (pts)", numeric: true, signed: true }, { key: "change_1m_points", label: "Δ 1M (pts)", numeric: true, signed: true }, { key: "change_3m_points", label: "Δ 3M (pts)", numeric: true, signed: true }, { key: "change_6m_points", label: "Δ 6M (pts)", numeric: true, signed: true }, { key: "change_1yr_points", label: "Δ 1YR (pts)", numeric: true, signed: true }, { key: "change_ytd_points", label: "Δ YTD (pts)", numeric: true, signed: true }, { key: "mid_ytm_pct", label: "Mid YTM (%)", numeric: true }, { key: "mid_3y_dm_bps", label: "Mid 3Y DM (bps)", numeric: true },
];
const LOAN_PAGE_SIZE = 250;

function loanCell(value: LoanRow[keyof LoanRow], signed = false) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (typeof value !== "number") return String(value);
  const formatted = new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  return signed && value > 0 ? `+${formatted}` : formatted;
}

function RVView({ writeAccess, caseId }: { writeAccess: WriteAccess; caseId: string }) {
  const [rv, setRv] = useState<LoanUniverseResponse | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [findings, setFindings] = useState<LoanFinding[]>([]);
  const [pending, setPending] = useState(false);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [rating, setRating] = useState("");
  const [ranking, setRanking] = useState("");
  const [loanType, setLoanType] = useState("");
  const [maturityFrom, setMaturityFrom] = useState("");
  const [maturityTo, setMaturityTo] = useState("");
  const [marginMin, setMarginMin] = useState("");
  const [marginMax, setMarginMax] = useState("");
  const [dmMin, setDmMin] = useState("");
  const [dmMax, setDmMax] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ key: keyof LoanRow; direction: "asc" | "desc" }>({ key: "borrower_name", direction: "asc" });
  const refresh = useCallback(async (signal?: AbortSignal) => {
    if (!caseId) return;
    setLoading(true); setLoadError("");
    try { setRv(await request<LoanUniverseResponse>(`/api/cases/${caseId}/rv/loan-universes/active`, {}, signal)); }
    catch (caught) { if (!(caught instanceof DOMException && caught.name === "AbortError")) setLoadError(firstErrorMessage(caught, "Unable to load loan universe")); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, [caseId]);
  // The active universe is case-scoped external state.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setRv(null); setMessage(""); setFindings([]); const controller = new AbortController(); void refresh(controller.signal); return () => controller.abort(); }, [refresh]);
  const filterOptions = useMemo(() => {
    const values = (key: "sector" | "ratings" | "ranking" | "loan_type") => [...new Set((rv?.rows || []).map((row) => row[key]).filter((value): value is string => Boolean(value)))].sort();
    return { sector: values("sector"), ratings: values("ratings"), ranking: values("ranking"), loan_type: values("loan_type") };
  }, [rv]);
  const filteredRows = useMemo(() => {
    const inRange = (value: number | null, minimum: string, maximum: string) => value !== null && (!minimum || value >= Number(minimum)) && (!maximum || value <= Number(maximum));
    const query = search.trim().toLowerCase();
    return (rv?.rows || []).filter((row) =>
      (!query || [row.company, row.borrower_name, row.bloomberg_loan_id, row.figi].some((value) => value?.toLowerCase().includes(query)))
      && (!sector || row.sector === sector) && (!rating || row.ratings === rating) && (!ranking || row.ranking === ranking) && (!loanType || row.loan_type === loanType)
      && (!maturityFrom || Boolean(row.maturity_date && row.maturity_date >= maturityFrom)) && (!maturityTo || Boolean(row.maturity_date && row.maturity_date <= maturityTo))
      && (!marginMin && !marginMax || inRange(row.margin_bps, marginMin, marginMax)) && (!dmMin && !dmMax || inRange(row.mid_3y_dm_bps, dmMin, dmMax))
    ).sort((left, right) => {
      const a = left[sort.key]; const b = right[sort.key];
      if (a === b) return left.instrument_key.localeCompare(right.instrument_key);
      if (a === null || a === undefined) return 1;
      if (b === null || b === undefined) return -1;
      const order = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true });
      return sort.direction === "asc" ? order : -order;
    });
  }, [rv, search, sector, rating, ranking, loanType, maturityFrom, maturityTo, marginMin, marginMax, dmMin, dmMax, sort]);
  const pageCount = Math.max(1, Math.ceil(filteredRows.length / LOAN_PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = filteredRows.slice(currentPage * LOAN_PAGE_SIZE, (currentPage + 1) * LOAN_PAGE_SIZE);
  // Filters and ordering define a new result set, so return to its first page.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setPage(0); }, [search, sector, rating, ranking, loanType, maturityFrom, maturityTo, marginMin, marginMax, dmMin, dmMax, sort]);
  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) return;
    setPending(true); setMessage("Uploading and scanning workbook…"); setFindings([]);
    try {
      const form = new FormData(); form.append("file", file);
      const source = await request<SourceRecord>(`/api/cases/${caseId}/sources`, { method: "POST", body: form });
      setMessage("Validating the fixed CP-3 workbook…");
      const response = await fetch(`/api/cases/${caseId}/rv/loan-universes`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_id: source.id }) });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = body.detail || {};
        setFindings(Array.isArray(detail.findings) ? detail.findings : []);
        throw new Error(detail.message || `Workbook import failed (${response.status})`);
      }
      setMessage(`Active loan universe v${body.version} · ${body.row_count} instruments.`); setFile(null);
      await refresh();
    } catch (caught) { setMessage(firstErrorMessage(caught, "Unable to import workbook")); }
    finally { setPending(false); }
  };
  const changeSort = (key: keyof LoanRow) => setSort((current) => ({ key, direction: current.key === key && current.direction === "asc" ? "desc" : "asc" }));
  const messageIsError = Boolean(message && !pending && !message.startsWith("Active loan universe"));
  return <div className="grid loan-rv">
    <section className="panel span-12"><div className="panel-header"><h2>Leveraged-loan universe</h2><span className="panel-meta">Source data · unanalyzed</span></div><div className="panel-body loan-upload">{writeAccess === "yes" ? <form onSubmit={upload}><div className="field"><label htmlFor="loan-workbook">Fixed CP-3 sector workbook (.xlsx)</label><input id="loan-workbook" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setFile(event.target.files?.[0] || null)} required /></div><button className="button primary" type="submit" disabled={pending || !file}>{pending ? "Importing…" : "Upload CP-3 workbook"}</button></form> : <WriteBlocked access={writeAccess} action="importing a CP-3 workbook" />}<p className="muted">All visible sector tabs are ingested. Values remain in workbook units: prices and changes in points, margin and discount margin in bps, yield in percent.</p>{message && <p className={messageIsError ? "error" : "muted"} role={messageIsError ? "alert" : "status"}>{message}</p>}{findings.length ? <ul className="loan-findings" role="alert">{findings.map((finding, index) => <li key={`${finding.code}-${index}`}><strong>{humanizeCode(finding.code)}</strong> {finding.sheet ? `${finding.sheet}${finding.row ? ` R${finding.row}` : ""}: ` : ""}{finding.detail}</li>)}</ul> : null}</div></section>
    {rv?.universe ? <section className="panel span-12"><div className="panel-header"><h2>Active authority</h2><span className="status success">ACTIVE · v{rv.universe.version}</span></div><div className="panel-body loan-authority"><dl><dt className="meta-label">Workbook date</dt><dd>{rv.universe.workbook_date || "N/A"}</dd><dt className="meta-label">Source</dt><dd><Link href={withQuery("/sources/", { case: caseId, source: rv.universe.source_id })}>{rv.universe.source_filename}</Link></dd><dt className="meta-label">Instruments</dt><dd className="num">{rv.universe.row_count}</dd><dt className="meta-label">Template</dt><dd className="mono">{rv.universe.template_version}</dd><dt className="meta-label">Digest</dt><dd className="mono">{rv.universe.universe_digest}</dd></dl></div></section> : null}
    <section className="panel span-12"><div className="panel-header"><h2>Loan screener</h2><span className="panel-meta">{filteredRows.length} / {rv?.rows.length || 0} instruments</span></div><div className="panel-body loan-filters"><div className="field"><label htmlFor="loan-search">Issuer / ID</label><input id="loan-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></div>{[["loan-sector", "Sector", sector, setSector, filterOptions.sector], ["loan-rating", "Rating", rating, setRating, filterOptions.ratings], ["loan-ranking", "Ranking", ranking, setRanking, filterOptions.ranking], ["loan-type", "Loan type", loanType, setLoanType, filterOptions.loan_type]] .map(([id, label, value, setter, values]) => <div className="field" key={id as string}><label htmlFor={id as string}>{label as string}</label><select id={id as string} value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)}><option value="">All</option>{(values as string[]).map((option) => <option key={option}>{option}</option>)}</select></div>)}<details className="loan-advanced-filters"><summary>Advanced date and numeric filters</summary><div className="loan-advanced-grid"><div className="field"><label htmlFor="loan-maturity-from">Maturity from</label><input id="loan-maturity-from" type="date" value={maturityFrom} onChange={(event) => setMaturityFrom(event.target.value)} /></div><div className="field"><label htmlFor="loan-maturity-to">Maturity to</label><input id="loan-maturity-to" type="date" value={maturityTo} onChange={(event) => setMaturityTo(event.target.value)} /></div>{[["loan-margin-min", "Min margin (bps)", marginMin, setMarginMin], ["loan-margin-max", "Max margin (bps)", marginMax, setMarginMax], ["loan-dm-min", "Min 3Y DM (bps)", dmMin, setDmMin], ["loan-dm-max", "Max 3Y DM (bps)", dmMax, setDmMax]].map(([id, label, value, setter]) => <div className="field" key={id as string}><label htmlFor={id as string}>{label as string}</label><input id={id as string} type="number" step="any" value={value as string} onChange={(event) => (setter as (value: string) => void)(event.target.value)} /></div>)}</div></details></div><div className="table-wrap loan-table-wrap" tabIndex={0} role="region" aria-label="Leveraged-loan screener; scroll horizontally to review all workbook fields">{rv?.rows.length ? <table className="loan-table"><caption className="sr-only">27 columns. Scroll horizontally to review all workbook fields; column labels state source units.</caption><thead><tr className="loan-groups"><th scope="colgroup" colSpan={7}>Issuer profile</th><th scope="colgroup" colSpan={2}>Identifiers</th><th scope="colgroup" colSpan={6}>Loan terms</th><th scope="colgroup" colSpan={11}>Market data</th><th scope="colgroup" colSpan={1}>Source</th></tr><tr>{loanColumns.map((column) => <th scope="col" key={column.key} aria-sort={sort.key === column.key ? (sort.direction === "asc" ? "ascending" : "descending") : undefined}><button className="loan-sort" type="button" onClick={() => changeSort(column.key)}>{column.label}{sort.key === column.key ? (sort.direction === "asc" ? " ↑" : " ↓") : ""}</button></th>)}<th scope="col">Locator</th></tr></thead><tbody>{pageRows.map((row) => <tr key={row.instrument_key}>{loanColumns.map((column) => { const value = row[column.key]; const change = column.signed && typeof value === "number" ? value > 0 ? "positive" : value < 0 ? "negative" : "flat" : ""; return <td key={column.key} className={`${column.numeric ? "num" : ""} ${change}`.trim()}>{loanCell(value, column.signed)}</td>; })}<td className="mono">{row.source_locators.map((locator) => `${locator.sheet} R${locator.row}`).join("; ")}</td></tr>)}</tbody></table> : <LoadState loading={loading} error={loadError} empty="Upload the fixed CP-3 workbook to activate a leveraged-loan universe." />}{rv?.rows.length && !filteredRows.length ? <div className="empty">No loans match the current filters.</div> : null}</div>{filteredRows.length > LOAN_PAGE_SIZE ? <nav className="loan-pagination" aria-label="Loan screener pages"><button className="button small" type="button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</button><span className="mono">Page {currentPage + 1} of {pageCount}</span><button className="button small" type="button" disabled={currentPage + 1 >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</button></nav> : null}</section>
    <section className="context-strip span-12"><strong>Relative percentile unavailable</strong><p>The active universe serves exact source fields and filters, but no governed relative-position score. The browser does not infer one.</p></section>
  </div>;
}

function CommandView({ caseId, question }: { caseId: string; question: string }) {
  const [lens, setLens] = useState<{ issuer: string; sector: string; accepted_snapshot_id: string | null; source_set?: { version: number } | null } | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotView | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [artifactError, setArtifactError] = useState("");
  const [lensLoading, setLensLoading] = useState(true); const [lensError, setLensError] = useState(""); const [lensUnavailable, setLensUnavailable] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(true); const [snapshotError, setSnapshotError] = useState(""); const [snapshotUnavailable, setSnapshotUnavailable] = useState(false);
  // Command-center state is synchronized from two external authorities. The two
  // requests are deliberately independent: each panel loads, fails, or degrades to
  // its unavailable block on its own, so a dead lens route never blanks the diff.
  useEffect(() => {
    if (!caseId) return;
    let ignore = false;
    // The fetch boundary intentionally resets both panels' state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLensLoading(true); setLensError(""); setLensUnavailable(false); setSnapshotLoading(true); setSnapshotError(""); setSnapshotUnavailable(false); setArtifacts([]); setArtifactError("");
    void request<typeof lens>(`/api/cases/${caseId}/lens`)
      .then((nextLens) => { if (!ignore) setLens(nextLens); })
      .catch((caught) => {
        if (ignore) return;
        if (isUnavailableRoute(caught)) setLensUnavailable(true);
        else setLensError(firstErrorMessage(caught, "Unable to load the issuer lens"));
      })
      .finally(() => { if (!ignore) setLensLoading(false); });
    void request<SnapshotView>(`/api/cases/${caseId}/snapshot`)
      .then(async (nextSnapshot) => {
        if (ignore) return;
        setSnapshot(nextSnapshot);
        const acceptedArtifacts = nextSnapshot?.accepted?.artifacts || [];
        const loaded = await Promise.all(acceptedArtifacts.map((item) => request<ArtifactRecord>(`/api/cases/${caseId}/artifacts/${item.id}`).catch(() => null)));
        if (ignore) return;
        const available = loaded.filter((item): item is ArtifactRecord => item !== null);
        setArtifacts(available);
        if (available.length !== acceptedArtifacts.length) setArtifactError("Some accepted module outputs could not be loaded. Snapshot identity remains visible.");
      })
      .catch((caught) => {
        if (ignore) return;
        if (isUnavailableRoute(caught)) setSnapshotUnavailable(true);
        else setSnapshotError(firstErrorMessage(caught, "Unable to load the snapshot diff"));
      })
      .finally(() => { if (!ignore) setSnapshotLoading(false); });
    return () => { ignore = true; };
  }, [caseId]);
  const diff = snapshot?.diff;
  const conclusion = selectConclusionArtifact(artifacts);
  const conclusionBlocks = conclusion?.markdown ? markdownBlocks(conclusion.markdown) : [];
  const conclusionText = conclusion?.payload?.narrative?.takeaway || conclusion?.payload?.summary || conclusionBlocks.find((block) => block.kind === "paragraph")?.text || "";
  const evidenceCount = artifacts.reduce((total, item) => total + normalizeEvidenceRefs(item.payload?.evidence_refs).length, 0);
  return <div className="grid credit-screen">
    {question && <section className="context-strip span-12"><strong>Evidence request</strong><p>{question}</p></section>}
    <section className="credit-main span-9">
      {snapshotUnavailable ? <Unavailable title="Credit authority" /> : snapshotLoading || snapshotError ? <LoadState loading={snapshotLoading} error={snapshotError} /> : !snapshot?.accepted ? <StateBlock shape="action" title="Credit state unavailable" body="No accepted snapshot yet. Run analysis, inspect its exact outputs, then accept the snapshot." action={{ label: "Open analysis run", href: withQuery("/run-console", { case: caseId }) }} /> : <>
        <div className="credit-authority-head"><div><span className="meta-label">{lens?.issuer || "Selected credit"} · accepted record</span><h2>Accepted conclusion and exact module authority</h2></div><span className="status success">Accepted {formatDate(snapshot.accepted.accepted_at)}</span></div>
        <div className="standing-answer"><span className="meta-label">Current conclusion · {evidenceCount} source reference{evidenceCount === 1 ? "" : "s"}</span>{conclusionText ? <><h2>{conclusionText}</h2>{conclusion?.payload?.narrative?.basis ? <p>{conclusion.payload.narrative.basis}</p> : null}<p className="mono muted">{moduleLabel(conclusion?.module_id || "")} · {conclusion ? <IdentityValue value={conclusion.digest} className="" /> : null}</p></> : <Unavailable title="Standing conclusion" context="The accepted snapshot contains no module summary that can be presented as a conclusion." />}</div>
        <div className="authority-metrics"><div><span className="meta-label">Accepted snapshot</span><strong><IdentityValue value={snapshot.accepted.id} /></strong></div><div><span className="meta-label">Source set</span><strong className="mono">v{snapshot.accepted.source_set_version ?? "Unavailable"}</strong></div><div><span className="meta-label">Module outputs</span><strong className="num">{snapshot.accepted.artifacts.length}</strong></div><div><span className="meta-label">Evidence references</span><strong className="num">{evidenceCount}</strong></div></div>
        <section className="credit-change-section"><div className="section-heading"><h3>What changed</h3><span>Snapshot diff</span></div>{diff?.changed ? <><p className="callout warning">The visible accepted snapshot differs from the latest accepted execution. Navigation does not switch authority.</p><ul className="credit-change-list">{diff.source_set_changed ? <li><strong>Source set changed</strong><span>The latest accepted execution binds a different source set.</span></li> : null}{diff.added.map((item) => <li key={`added:${item.module_id}`}><strong>{moduleLabel(item.module_id)} added</strong><IdentityValue value={item.digest} /></li>)}{diff.modified.map((item) => <li key={`modified:${item.module_id}`}><strong>{moduleLabel(item.module_id)} changed</strong><span>Latest digest <IdentityValue value={item.digest} /></span></li>)}{diff.removed.map((item) => <li key={`removed:${item.module_id}`}><strong>{moduleLabel(item.module_id)} removed</strong><IdentityValue value={item.digest} /></li>)}</ul></> : <p className="callout">No material module or source-set change is present in the served snapshot diff.</p>}</section>
        {artifactError ? <StateNote tone="critical" live="alert">{artifactError}</StateNote> : null}
        <div className="top-actions credit-actions"><Link className="button primary" href={withQuery("/deep-dive", { case: caseId })}>Read accepted analysis</Link><Link className="button" href={withQuery("/run-console", { case: caseId })}>Review latest run</Link></div>
      </>}
    </section>
    <aside className="credit-proof span-3"><div className="meta-label">Proof and gaps</div><h2>Accepted support</h2>{lensUnavailable ? <Unavailable title="Issuer lens" /> : lensLoading || lensError ? <LoadState loading={lensLoading} error={lensError} /> : <dl className="state-facts"><dt>Issuer</dt><dd>{lens?.issuer || "Unavailable"}</dd><dt>Sector</dt><dd>{lens?.sector || "Unavailable"}</dd><dt>Accepted snapshot</dt><dd><IdentityValue value={lens?.accepted_snapshot_id || "None"} /></dd><dt>Source set</dt><dd className="mono">{lens?.source_set?.version ? `v${lens.source_set.version}` : "None"}</dd></dl>}<div className="proof-register"><strong className="num">{artifacts.length}</strong><p>Accepted module outputs are directly addressable by artifact id and digest.</p></div><Unavailable title="Binding measure and claim gaps" context="The current API does not serve normalized measure, threshold, assumption and counterfactual fields. No client inference is shown." /></aside>
    <section className="context-strip span-12"><strong>Analyst boundary</strong><p>Engine output is separated from analyst judgment. Instrument recommendations remain analyst-owned and versioned in Report Studio.</p></section>
  </div>;
}

function AdminView() {
  const contracts = [
    ["Bundle integrity", "Signed build manifest and file verification"],
    ["Audit trail", "Immutable, exportable actor and action events"],
    ["Membership", "Identity-to-case role assignments"],
    ["Step-up", "Server-verified privileged-session state"],
  ];
  return <div className="admin-capability">
    <section className="admin-intro"><span className="flag">UNAVAILABLE</span><div><div className="meta-label">Deployment capability</div><h2>Administrative authority is not served by this application build.</h2><p>No token prompt or simulated audit record is shown. Identity role and case role remain separate server-owned concepts.</p></div></section>
    <section className="panel"><div className="panel-header"><h2>Required contracts</h2><span className="panel-meta">Server-owned</span></div><div className="panel-body table-wrap" tabIndex={0} role="region" aria-label="Required administrative contracts"><table><thead><tr><th scope="col">Capability</th><th scope="col">Required response</th><th scope="col">State</th></tr></thead><tbody>{contracts.map(([capability, response]) => <tr key={capability}><th scope="row">{capability}</th><td>{response}</td><td><span className="status warning">Not served</span></td></tr>)}</tbody></table></div></section>
    <section className="context-strip"><strong>Authorization boundary</strong><p>Adding these screens requires authenticated backend routes and auditable policy enforcement. Client-only controls would not create administrative authority.</p></section>
  </div>;
}
