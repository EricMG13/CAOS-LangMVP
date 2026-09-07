"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiRequestError, api, firstErrorMessage, type OperatorCapabilities, type ProviderCatalog } from "../lib/api";
import { humanizeCode } from "../lib/workbench";
import { LoadState, MutationReceipt, StateNote } from "./states";

type BootstrapReceipt = { case_id: string; subject: string; role: "APPROVER"; actor: string; at: string };

export default function OperatorControls({ capabilities, initialCaseId }: { capabilities: OperatorCapabilities; initialCaseId: string }) {
  const [bootstrap, setBootstrap] = useState({ caseId: initialCaseId, subject: "", rationale: "" });
  const [receipt, setReceipt] = useState<BootstrapReceipt | null>(null);
  const [bootstrapError, setBootstrapError] = useState("");
  const [bootstrapBusy, setBootstrapBusy] = useState(false);
  const [catalog, setCatalog] = useState<ProviderCatalog | null>(null);
  const [selection, setSelection] = useState("");
  const [providerError, setProviderError] = useState("");
  const [providerReceipt, setProviderReceipt] = useState("");
  const [providerBusy, setProviderBusy] = useState(false);
  const lifetime = useRef(0);
  const loadCatalog = useCallback(async (signal?: AbortSignal) => {
    const generation = lifetime.current;
    try {
      const next = await api<ProviderCatalog>("/api/admin/providers", {}, signal);
      if (generation !== lifetime.current) return;
      setCatalog(next); setSelection(next.default_binding_id || "");
    } catch (caught) { if (!signal?.aborted && generation === lifetime.current) setProviderError(firstErrorMessage(caught, "Provider policy unavailable.")); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const timer = capabilities.can_manage_providers ? window.setTimeout(() => void loadCatalog(controller.signal), 0) : null;
    return () => { if (timer !== null) window.clearTimeout(timer); controller.abort(); lifetime.current += 1; };
  }, [capabilities.can_manage_providers, loadCatalog]);
  const grant = async () => {
    if (bootstrapBusy || !capabilities.can_bootstrap_approver) return;
    const generation = lifetime.current;
    setBootstrapBusy(true); setBootstrapError(""); setReceipt(null);
    try {
      const next = await api<BootstrapReceipt>(`/api/admin/cases/${encodeURIComponent(bootstrap.caseId.trim())}/bootstrap-approver`, { method: "POST", body: JSON.stringify({ subject: bootstrap.subject.trim(), rationale: bootstrap.rationale.trim() }) });
      if (generation === lifetime.current) setReceipt(next);
    } catch (caught) { if (generation === lifetime.current) setBootstrapError(firstErrorMessage(caught, "Unable to bootstrap the approver.")); }
    finally { if (generation === lifetime.current) setBootstrapBusy(false); }
  };
  const updateProvider = async () => {
    if (!catalog || providerBusy || !capabilities.can_manage_providers) return;
    const generation = lifetime.current;
    setProviderBusy(true); setProviderError(""); setProviderReceipt("");
    try {
      const next = await api<ProviderCatalog>("/api/admin/provider-default", { method: "POST", body: JSON.stringify({ binding_id: selection, expected_version: catalog.version }) });
      if (generation !== lifetime.current) return;
      setCatalog(next); setSelection(next.default_binding_id || "");
      const binding = next.bindings.find((item) => item.id === next.default_binding_id);
      setProviderReceipt(`Default updated to ${binding ? `${binding.provider_name} / ${binding.model}` : next.default_binding_id} · policy v${next.version}. Existing runs keep their recorded provider and model.`);
    } catch (caught) {
      if (generation !== lifetime.current) return;
      setProviderError(firstErrorMessage(caught, "Unable to change the provider default."));
      if (caught instanceof ApiRequestError && caught.status === 409) await loadCatalog();
    } finally { if (generation === lifetime.current) setProviderBusy(false); }
  };
  return <>
    {capabilities.can_bootstrap_approver ? <section className="panel" aria-labelledby="bootstrap-title"><div className="panel-header"><h2 id="bootstrap-title">First independent approver</h2><span className="panel-meta">Enterprise operator</span></div><div className="panel-body flow"><p>Enter the case ID supplied by its analyst. This one-time grant assigns an independent approver; it does not give you access to the case.</p><form className="opinion-form" data-bootstrap-form onSubmit={(event) => { event.preventDefault(); void grant(); }}>
      <div className="field"><label htmlFor="bootstrap-case">Case ID</label><input id="bootstrap-case" required maxLength={200} value={bootstrap.caseId} onChange={(event) => setBootstrap((current) => ({ ...current, caseId: event.target.value }))} disabled={bootstrapBusy} /></div>
      <div className="field"><label htmlFor="bootstrap-subject">Independent approver subject</label><input id="bootstrap-subject" required maxLength={200} value={bootstrap.subject} onChange={(event) => setBootstrap((current) => ({ ...current, subject: event.target.value }))} disabled={bootstrapBusy} /></div>
      <div className="field"><label htmlFor="bootstrap-rationale">Audit rationale</label><textarea id="bootstrap-rationale" required maxLength={2000} value={bootstrap.rationale} onChange={(event) => setBootstrap((current) => ({ ...current, rationale: event.target.value }))} disabled={bootstrapBusy} /></div>
      <button className="button primary" type="submit" disabled={bootstrapBusy || !bootstrap.caseId.trim() || !bootstrap.subject.trim() || !bootstrap.rationale.trim()}>{bootstrapBusy ? "Provisioning…" : "Provision first approver"}</button></form>
      {bootstrapError ? <StateNote tone="critical" live="alert">{bootstrapError}</StateNote> : null}{receipt ? <MutationReceipt>{receipt.subject} provisioned as {receipt.role} for <code>{receipt.case_id}</code> by {receipt.actor} · {receipt.at}.</MutationReceipt> : null}
    </div></section> : null}
    {capabilities.can_manage_providers ? <section className="panel" aria-labelledby="provider-default-title"><div className="panel-header"><h2 id="provider-default-title">Default analysis provider</h2><span className="panel-meta">{catalog ? `Policy v${catalog.version}` : "Enterprise operator"}</span></div><div className="panel-body flow"><p>The default applies to newly admitted runs. Each existing run keeps its recorded provider and model.</p>{providerError ? <StateNote tone="critical" live="alert">{providerError}</StateNote> : null}{catalog ? <form onSubmit={(event) => { event.preventDefault(); void updateProvider(); }}><div className="field"><label htmlFor="provider-binding">Qualified provider and model</label><select id="provider-binding" value={selection} onChange={(event) => setSelection(event.target.value)} disabled={providerBusy}><option value="">Select a binding</option>{catalog.bindings.map((binding) => <option key={binding.id} value={binding.id} disabled={!binding.available}>{binding.provider_name} / {binding.model}{binding.available ? "" : ` · ${humanizeCode(binding.unavailable_code || binding.status)}`}</option>)}</select></div><button className="button primary" type="submit" disabled={providerBusy || selection === catalog.default_binding_id || !catalog.bindings.some((binding) => binding.id === selection && binding.available)}>{providerBusy ? "Updating…" : "Set default for new runs"}</button><ul>{catalog.bindings.filter((binding) => !binding.available).map((binding) => <li key={binding.id}>{binding.provider_name} / {binding.model}: {humanizeCode(binding.unavailable_code || binding.status)}</li>)}</ul></form> : <LoadState loading={!providerError} error={providerError} onRetry={() => void loadCatalog()} />}{providerReceipt ? <MutationReceipt>{providerReceipt}</MutationReceipt> : null}</div></section> : null}
  </>;
}
