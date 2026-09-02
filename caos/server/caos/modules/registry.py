"""Module registry — the declarative seam (DECISIONS §7, §11.5, §11.7).

One entry per live catalog module, plus its separately runnable CP-PARSE
preparation stage. Semantic execution is provider-backed at both depths;
deterministic host work is reserved for typed calculations and other
input-determined operations. Superseded IDs resolve through the alias map from
the catalog's superseded_module_ids.
"""

from __future__ import annotations

from dataclasses import dataclass


CP_MODEL_INPUT_MODULES = ("CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2G")


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    mode_full: str  # "agent" | "deterministic"
    mode_screen: str = "agent"
    skill_slug: str | None = None
    reference_files: tuple[str, ...] = ()
    max_output_tokens: int = 0
    calculators: tuple[str, ...] = ()
    derived_projections: tuple[str, ...] = ()
    source_mode: str = "supplied_only"
    # A module whose substantive work waits on a digest-bound human approval of
    # the host-proposed plan (invariant 5); CP-DR only (DECISIONS §14.16).
    plan_approval: bool = False

    @property
    def authority_digest(self) -> str:
        # §12.7: the golden digest is a recorded literal — changing wrapper
        # text, reference order, or the join is a methodology change and must
        # move these constants deliberately.
        return GOLDEN_AUTHORITY_DIGESTS[self.module_id]


# digest({"authority": assemble_authority(module_id)}) over the pinned
# deploy_v build, recorded 2026-09-01.
GOLDEN_AUTHORITY_DIGESTS = {
    "CP-PARSE": "16f776ac5b39f640cbdd8840a0691e1ab5bf2b7bdce720fe9defad8395c8a38a",
    "CP-0": "2ae4abd601c40f1515645d8422bb2fc2a75da85624c0d2dceb52aed8b79dca00",
    "CP-1": "ddbf1851a2c9c3ea6967916c427eb8c3a9d755418bbf8d6ba0aa425510f4b484",
    "CP-1A": "eae3f83609f8e1c3ce9e8942063d462f845f845351f75d0aabc053c1329c2f78",
    "CP-1B": "2acc507133548c56cc0e4bd16769bced624fe32a933d4b0a580d898f436a9bf9",
    "CP-1C": "03fdf7c18893bfd87f3cb0f1bdebeec4668b6c51c75511f17cd9ad22889e1fdc",
    "CP-1D": "67dcaeac7ccb92aca32cc4a20e7082878965c5b40875e01978ff1608eaa1d057",
    "CP-2": "dddfa5e970ce0cd5a7246d7192ec21f307979a214f1ea9e404dcf4922c725272",
    "CP-2A": "80ad061d285edc132c350cf715fbfd4f0a4a82b565440c701249b1f433487704",
    "CP-2E": "9a5a23d732dece5d8d75e14bd8480f9503db37d92c57439b418d77afdf4132b1",
    "CP-2G": "41e1fc78a3a308e8dbce2cdf85c80b916e2acfffa2e4e13a5e7e77595687e355",
    "CP-2H": "0a2857897cf7922d8fa13d223f93602cd917f4f49b1690614c74d1817162727f",
    "CP-3": "32c87019d1f09e94383e8e4e2e76ef584ae7e98b4a8d38eaa7821da3dc93cfdb",
    "CP-4": "3e1acb09c88cdb5c114055d06346ae146a1943327b8d67eb71f76336dba1a039",
    "CP-4C": "fca7962748b9884d765e49e289c1c44b07bed0bc2418ef4359b176a7adf716c1",
    "CP-5": "034e0f7b00010b9ca756cbc567d629bef05809a4e5f8b059b9a3735d7a35d46f",
    "CP-6": "0c4516de061b4785684269b8783ab7555a6b170561b780466a33723d77039146",
    "CP-L10": "bf9a6248b361134ce691cbaaff5b7c1a3078c5d93705d89f04d2e2b56f323915",
    # Recorded 2026-09-02 (Task 7) over the same pinned build.
    "CP-DR": "76e990f44a773b0ca718576d96c591e83cfcce5b2aaeea03af80b4f1456c254b",
}


MODULES: dict[str, ModuleSpec] = {
    "CP-PARSE": ModuleSpec(
        "CP-PARSE", "agent", skill_slug="cp-0-source-readiness",
        reference_files=("references/CP-PARSE_SCHEMA_REFERENCE.md", "references/REF_CP-PARSE_STEPS.md"),
        max_output_tokens=16_000,
    ),
    "CP-0": ModuleSpec(
        "CP-0", "agent", skill_slug="cp-0-source-readiness",
        reference_files=(
            "references/CP-0_SCHEMA_REFERENCE.md",
            "references/REF_CP-0_STEPS.md",
            "references/CP0_PROFILE_ANCHOR_CONTRACT_v1.md",
            "references/CP0_CAPACITY_RESUME_CONTRACT_v1.md",
        ),
        max_output_tokens=24_000,
    ),
    "CP-1": ModuleSpec(
        "CP-1", "agent", skill_slug="cp-1-canonical-data-foundation",
        reference_files=("references/CP-1_RUNBOOK.md", "references/CP-1_SCHEMA_REFERENCE.md", "references/REF_CP-1_STEPS.md"),
        max_output_tokens=32_000,
        calculators=("credit_metrics",),
    ),
    "CP-1A": ModuleSpec(
        "CP-1A", "agent", skill_slug="cp-1a-business-transaction-fact-pack",
        reference_files=("references/CP-1A_SCHEMA_REFERENCE.md", "references/REF_CP-1A_STEPS.md"),
        max_output_tokens=12_000,
    ),
    "CP-1B": ModuleSpec(
        "CP-1B", "agent", skill_slug="cp-1b-earnings-delta",
        reference_files=("references/CP-1B_SCHEMA_REFERENCE.md", "references/REF_CP-1B_STEPS.md"),
        max_output_tokens=12_000,
        calculators=("credit_metrics",),
    ),
    "CP-1C": ModuleSpec(
        "CP-1C", "agent", skill_slug="cp-1c-peer-benchmark",
        reference_files=("references/CP-1C_SCHEMA_REFERENCE.md", "references/REF_CP-1C_STEPS.md"),
        max_output_tokens=12_000,
        calculators=("peer_statistics",),
        source_mode="supplied_only",  # web discovery is structurally banned (invariant 1)
    ),
    "CP-1D": ModuleSpec(
        "CP-1D", "agent", skill_slug="cp-1d-earnings-quality",
        reference_files=("references/CP-1D_SCHEMA_REFERENCE.md",),
        max_output_tokens=12_000,
    ),
    "CP-2": ModuleSpec(
        "CP-2", "agent", skill_slug="cp-2-fundamental-credit-synthesizer",
        reference_files=("references/CP-2_SCHEMA_REFERENCE.md", "references/REF_CP-2_STEPS.md"),
        max_output_tokens=16_000,
    ),
    "CP-2A": ModuleSpec(
        "CP-2A", "agent", skill_slug="cp-2a-downside-pathway",
        reference_files=(
            "references/CP-2A_SCHEMA_REFERENCE.md",
            "references/REF_CP-2A_STEPS.md",
            "references/CP-2B_SCHEMA_REFERENCE.md",
            "references/REF_CP-2B_STEPS.md",
        ),
        max_output_tokens=16_000,
        derived_projections=("CP-2B",),
    ),
    "CP-2E": ModuleSpec(
        "CP-2E", "agent", skill_slug="cp-2e-macro-fx-hedging-sensitivity",
        reference_files=(
            "references/CP-2E_SCHEMA_REFERENCE.md",
            "references/REF_CP-2E_STEPS.md",
            "references/CP-2F_SCHEMA_REFERENCE.md",
            "references/REF_CP-2F_STEPS.md",
        ),
        max_output_tokens=24_000,
        calculators=("rate_fx_sensitivity",),
    ),
    "CP-2G": ModuleSpec(
        "CP-2G", "agent", skill_slug="cp-2g-forward-credit-model",
        reference_files=("references/CP-2G_ForwardCreditModel.schema.md", "references/REF_CP-2G_STEPS.md"),
        max_output_tokens=24_000,
        calculators=("credit_metrics", "liquidity_bridge"),
    ),
    "CP-2H": ModuleSpec(
        "CP-2H", "agent", skill_slug="cp-2h-ratings-migration-trigger",
        reference_files=(
            "references/CP-2H_RatingTransition.schema.md",
            "references/REF_CP-2H_STEPS.md",
            "references/CP-3D_MarketImpliedRisk.schema.md",
            "references/REF_CP-3D_STEPS.md",
        ),
        max_output_tokens=24_000,
        calculators=("bond_analytics", "covenant_headroom"),
    ),
    "CP-3": ModuleSpec(
        "CP-3", "agent", skill_slug="cp-3-relative-value-security-selection",
        reference_files=(
            "references/CP-3_SCHEMA_REFERENCE.md",
            "references/REF_CP-3_STEPS.md",
            "references/CP-3A_RUNBOOK.md",
            "references/CP-3A_SCHEMA_REFERENCE.md",
            "references/REF_CP-3A_STEPS.md",
            "references/CP-3B_RUNBOOK.md",
            "references/CP-3B_SCHEMA_REFERENCE.md",
            "references/REF_CP-3B_STEPS.md",
        ),
        max_output_tokens=32_000,
        calculators=("recovery_waterfall",),
    ),
    "CP-4": ModuleSpec(
        "CP-4", "agent", skill_slug="cp-4-legal-covenant-interpreter",
        reference_files=(
            "references/CP-4_RUNBOOK.md",
            "references/CP-4_SCHEMA_REFERENCE.md",
            "references/REF_CP-4_STEPS.md",
            "references/CP-4B_RUNBOOK.md",
            "references/CP-4B_SCHEMA_REFERENCE.md",
            "references/REF_CP-4B_STEPS.md",
            "references/CP-4D_SCHEMA_REFERENCE.md",
            "references/CP-4A_RUNBOOK.md",
            "references/CP-4A_SCHEMA_REFERENCE.md",
            "references/REF_CP-4A_STEPS.md",
        ),
        max_output_tokens=32_000,
        calculators=("covenant_headroom",),
    ),
    "CP-4C": ModuleSpec(
        "CP-4C", "agent", skill_slug="cp-4c-restructuring-fulcrum",
        reference_files=(
            "references/CP-4C_RestructuringScenario.schema.md",
            "references/REF_CP-4C_STEPS.md",
            "references/CP-3C_RUNBOOK.md",
            "references/CP-3C_SCHEMA_REFERENCE.md",
            "references/REF_CP-3C_STEPS.md",
        ),
        max_output_tokens=32_000,
        calculators=("funding_gap", "recovery_waterfall"),
    ),
    "CP-5": ModuleSpec(
        "CP-5", "agent", skill_slug="cp-5-evidence-trace-validator",
        reference_files=("references/CP-5_RUNBOOK.md", "references/CP-5_SCHEMA_REFERENCE.md", "references/REF_CP-5_STEPS.md"),
        max_output_tokens=24_000,  # §10.11: it consumes every upstream artifact; 16k plausibly truncates
    ),
    "CP-6": ModuleSpec(
        "CP-6", "agent", skill_slug="cp-6-ic-debate-challenge",
        reference_files=(
            "references/CP-6_SCHEMA_REFERENCE.md",
            "references/REF_CP-6_STEPS.md",
            "references/CP-6A_SCHEMA_REFERENCE.md",
            "references/REF_CP-6A_STEPS.md",
        ),
        max_output_tokens=24_000,
    ),
    "CP-DR": ModuleSpec(
        "CP-DR", "agent", skill_slug="cp-dr-deep-research",
        reference_files=("references/REF_CP-DR_STEPS.md", "references/CP-DR_DeepResearch.schema.md"),
        max_output_tokens=32_000,
        source_mode="supplied_only",  # invariant 1: no web, email, filesystem or network evidence
        plan_approval=True,
    ),
    "CP-L10": ModuleSpec(
        "CP-L10", "agent", skill_slug="cp-l10-financial-change-screen",
        reference_files=(
            "references/CP-L10_CP_LITE_ANALYSIS_POLICY_v1.md",
            "references/CP-L10_SCHEMA_REFERENCE.md",
            "references/REF_CP-L10_ADAPTIVE_METHOD.md",
            "references/CP-L20_SCHEMA_REFERENCE.md",
            "references/REF_CP-L20_ADAPTIVE_METHOD.md",
            "references/CP-L23_SCHEMA_REFERENCE.md",
            "references/REF_CP-L23_ADAPTIVE_METHOD.md",
            "references/CP-L30_SCHEMA_REFERENCE.md",
            "references/REF_CP-L30_ADAPTIVE_METHOD.md",
            "references/CP-L40_SCHEMA_REFERENCE.md",
            "references/REF_CP-L40_ADAPTIVE_METHOD.md",
        ),
        max_output_tokens=32_000,
    ),
}


# Catalog superseded_module_ids, transcribed.
_ALIASES = {
    "CP-1E": "CP-1D",
    "CP-2B": "CP-2A",
    "CP-2C": "CP-1A",
    "CP-2D": "CP-2G",
    "CP-2F": "CP-2E",
    "CP-3A": "CP-3",
    "CP-3B": "CP-3",
    "CP-3C": "CP-4C",
    "CP-3D": "CP-2H",
    "CP-4A": "CP-4",
    "CP-4B": "CP-4",
    "CP-4D": "CP-4B",
    "CP-5A": "CP-5",
    "CP-6A": "CP-6",
    "CP-L20": "CP-L10",
    "CP-L23": "CP-L10",
    "CP-L30": "CP-L10",
    "CP-L40": "CP-L10",
}


def resolve_alias(module_id: str) -> str:
    seen = set()
    while module_id in _ALIASES and module_id not in seen:
        seen.add(module_id)
        module_id = _ALIASES[module_id]
    return module_id


def cp2g_pins(latest_cp1_fiscal_year: int) -> dict[str, tuple[str, ...]]:
    """§12.27: CP-2G's staged questions are pinned from its contract defaults —
    three consecutive fiscal years after the latest CP-1 actual; CP-1-anchored
    base; BASE+DOWNSIDE — validated pre-dispatch."""
    return {
        "forecast_horizon": tuple(f"FY{latest_cp1_fiscal_year + offset}" for offset in (1, 2, 3)),
        "cases": ("BASE", "DOWNSIDE"),
    }
