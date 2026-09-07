"""Immutable developer-owned v2 layouts. Exact bindings: ANALYST_VIEW_COVERAGE.md.

Each input is (module, selector). @ selects a canonical Markdown section without
duplicating its tables; | declares table aliases. MODEL selects validated outputs.
Missing required inputs stay visible and block publication, never draft recovery.
"""

TEMPLATE_V2 = "caos.deliverable-template.v2"

LAYOUTS_V2 = {
    "FULL_CREDIT": [
        ("credit_summary", "Credit summary", [("CP-2", "T2.7"), ("CP-2", "@Analysis")]),
        ("business", "Business / transaction", [("CP-1A", "transaction_summary|T2D.2|cp1a.cp_model_snapshot_fields"), ("CP-1A", "@Analysis")]),
        ("financials", "Financial performance and earnings quality", [("CP-1", "cp1.model_account_register|T4.15"), ("CP-1", "cp1.adjusted_ebitda_bridge|T4.17")]),
        ("capital", "Capital structure", [("CP-1", "cp1.debt_facility_register|T4.18")]),
        ("model", "Base / Downside model", [("MODEL", "outputs")]),
        ("liquidity", "Liquidity / covenants", [("CP-4", "T4C.3"), ("CP-4", "T4C.4")]),
        ("relative_value", "Relative value", [("CP-3", "T3.5"), ("CP-3", "T3.7")]),
        ("risks", "Risks / catalysts / monitoring", [("CP-2", "T2.10"), ("CP-2", "T2.12")]),
        ("qa", "Evidence / QA", [("CP-5", "T5B.3"), ("CP-5", "T5B.6")]),
    ],
    "EARNINGS_UPDATE": [
        ("context", "Period / comparator context", [("CP-1B", "T4.3"), ("CP-1B", "@Audit Summary")]),
        ("changes", "Reported-versus-prior changes", [("CP-1B", "T4.4"), ("CP-1B", "T4.12|cp1b.model_comparator_register")]),
        ("quality", "Earnings quality", [("CP-1B", "T4.6"), ("CP-1B", "T4.14|cp1b.addback_validation_register")]),
        ("model", "Accepted pathway model effects", [("MODEL", "outputs")]),
        ("liquidity", "Leverage / liquidity", [("CP-1B", "cp1b.cp_model_snapshot_fields")]),
        ("monitoring", "Implications and monitoring", [("CP-1B", "T4.10"), ("CP-1B", "T4.11")]),
    ],
    "COVENANT_REFINANCING": [
        ("debt", "Debt / maturity profile", [("CP-3", "T3D.2")]),
        ("covenants", "Covenant definitions and headroom", [("CP-4", "T4C.3"), ("CP-4", "T4C.4")]),
        ("liquidity", "Liquidity", [("CP-3", "T3D.3"), ("CP-3", "T3C.6")]),
        ("refinancing", "Refinancing / restructuring findings", [("CP-3", "T3D.6"), ("CP-3", "@Analysis")]),
        ("model", "Model effects", [("MODEL", "outputs")]),
        ("actions", "Actions and evidence", [("CP-4", "T4C.11"), ("CP-3", "T3D.9")]),
    ],
    "RELATIVE_VALUE": [
        ("universe", "Pinned instrument universe", [("CP-3", "T3B.2"), ("CP-3", "@Audit Summary")]),
        ("comparison", "Peer / issuer comparison", [("CP-3", "T3.3"), ("CP-3", "T3.6")]),
        ("structure", "Structure / seniority", [("CP-3", "T3B.4")]),
        ("compensation", "Compensation / ranking", [("CP-3", "T3.5"), ("CP-3", "T3.7")]),
        ("gates", "Catalysts, freshness and trade gates", [("CP-3", "T3B.3"), ("CP-3", "T3.9"), ("CP-3", "T3C.6")]),
    ],
    "DISTRESSED_RESTRUCTURING": [
        ("priority", "Priority stack", [("CP-4C", "T4E.2")]),
        ("liquidity", "Liquidity runway", [("CP-3", "T3D.3")]),
        ("scenarios", "Scenario / breakpoint outputs", [("CP-4C", "T4E.3"), ("MODEL", "outputs")]),
        ("recovery", "Recovery / fulcrum", [("CP-4C", "T4E.5"), ("CP-4C", "T4E.6"), ("CP-4C", "T4E.7")]),
        ("milestones", "Legal / process milestones", [("CP-4C", "T4E.4"), ("CP-4C", "T4E.9")]),
        ("recommendations", "Recommendations and limitations", [("CP-3", "T3D.6"), ("CP-4C", "T4E.10")]),
    ],
    "DEEP_RESEARCH": [
        ("scope", "Research question / scope", [("CP-DR", "scope")]),
        ("findings", "Findings", [("CP-DR", "@Analysis")]),
        ("evidence", "Evidence and counterevidence", [("CP-DR", "@Evidence Trace"), ("CP-DR", "@Source Registry")]),
        ("implications", "Implications", [("CP-DR", "@Analysis/Implications")]),
        ("questions", "Unresolved questions", [("CP-DR", "@Gaps & Conflicts")]),
    ],
}

# Explicitly optional: no pathway requires a memo or commentary. Empty is a
# deliberate choice. The omission reason survives in the composed document.
OPTIONAL_SECTIONS_V2 = [
    {"section_id": "ic_context", "title": "IC module context", "module_id": "CP-6",
     "selector": "@Analysis", "default_included": False,
     "omission_reason": "IC module context is optional; this report is composed directly from pathway modules."},
]

# Same recipe IDs and exact points as Analysis. No client chart editor.
CHARTS_V2 = {
    "financials": ("cp1.revenue.v1", "cp1.ebitda.v1", "cp1.cfo_ncfo.v1", "cp1.adjustments.v1"),
    "capital": ("cp1.debt_maturity.v1",),
}
