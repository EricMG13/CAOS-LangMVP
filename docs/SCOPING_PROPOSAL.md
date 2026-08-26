# Scoping Proposal — sent before building (2026-08-26)

> Amended same day by the red-team pass (docs/DECISIONS.md §10): notes (incl. promotion) and assumptions move back INTO the MVP — promotion mints evidence sources and carries invariant-1 guarantees with no other asserting surface. The report-era cut narrows to thesis, recommendation matrix, and legacy report freeze/approve/export. Fifteen objections adopted in total; .agent-reviews/redteam.md has the list.

Full rationale in docs/DECISIONS.md; granularity detail in MODULE_GRANULARITY.md. This is the summary you asked for before execution begins.

## The MVP cut

**In:** four pathways at both depths — Full Credit, Earnings Update, Covenant & Refinancing, Relative Value. Source ingestion with the full fail-closed posture; snapshots; the complete Model Builder chain (builds, previews, scenarios, sensitivities, revisions, Sign-Off, verified exports); the Deliverables pipeline with approval-gated filing; RV loan universes; audit; the ported frontend.

**Out:** Deep Research / CP-DR (per brief); Distressed & Restructuring plus the internal Portfolio Decision and Decision Ledger pathways (their terminal modules CP-6/CP-8 never had real execution in legacy); the legacy report era (thesis/recommendations/notes/assumptions/report freeze-approve — superseded by Deliverables, uncalled by the current frontend); methodology draft editing (bundle verify and audit stay). Each excluded contractual test gets a one-line justification in the reconciliation table.

## Graph decomposition

Eight static LangGraph graphs — one per (pathway, depth) — compiled at startup from the verified Deploy V catalog routes, CP-PARSE at stage 0, node = live catalog module, edges = catalog dependencies, fan-out where the DAG allows. No dynamic routing exists: the run's path is fixed at start (invariant 10 is structural). Thread = run; durable checkpointer (Postgres prod, SQLite dev/test); a restarted worker resumes unfinished threads from their last checkpoint. Interrupts: source-set-empty entry gate, and the deliverable freeze→file approval gate (its own small graph, thread per frozen deliverable). Model Sign-Off stays a store CAS — it is the author's self-release per CONTEXT.md; no human wait exists to suspend.

**Module execution:** real agent execution for nine modules — the canonical six plus three newly wired that legacy could never reach: **CP-1C PeerBenchmark, CP-1D EarningsQuality, CP-5 EvidenceTraceValidator** (chosen for pathway value: CP-5 makes Earnings Update and Covenant & Refinancing end with a real QA gate). All other route modules run as the deterministic host modules they already were in legacy. Adding or upgrading a module is one entry in a declarative registry; the three new wirings will land as isolated registry-only commits to prove it.

**State & persistence:** graph state carries pinned identity (source set id+version+digest, plan digest, methodology build_id, model) plus artifact refs/digests and node statuses; artifact payloads, the append-only event log, audit, and all domain entities live in a single SQLAlchemy-Core store (SQLite dev / Postgres prod). The budget ledger (reserve→reconcile, inflight digest, active-time, evidence ceilings) is store-backed and fail-closed — host-enforced, never model-reported — because parallel nodes must contend on one ledger and a crash must fail closed on an unresolved inflight reservation. The Anthropic loop is langchain-anthropic with `max_retries=0`, `read_evidence` as a strict bound tool that cannot leave the pinned source set, structured output, one host-owned retry + one repair turn, all legacy strictness rules kept as validation.

## Module granularity call

Register at live-module granularity; **split none of the 19 absorbed IDs**; every superseded ID is an alias to its parent node. No absorbed phase passes the test (a named graph property AND a stated contract): the routes already expose the catalog's parallelism, no phase has its own human gate, and where ancestors exist (9 of 19) their contracts conflict with Deploy V naming — Deploy V wins, and the catalog states artifact contracts only per live module. CP-PARSE keeps its own stage-0 node (already how routes compile — preservation, not a split); CP-2B stays CP-2A's digest-chained derived projection exactly as legacy emits it. The registry is structured so any later split is a registry change, not a graph change.

## Blocking questions

None. Two flags, neither blocking:
1. Tests use scripted providers throughout (as legacy's do), so the build needs no ANTHROPIC_API_KEY; a live end-to-end smoke run at the finish does. If a key is available in the environment then, I will run one; otherwise the live smoke is listed as not exercised.
2. No branch was named for the work, so per the one-branch-per-phase rule I am using `phase-1-design` … `phase-6-ship`, each merged to main at its gate.

Building begins now with phase 2 (foundation) unless you redirect.
