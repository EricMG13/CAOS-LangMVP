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
# deploy_v build; host profile/canonical-contract revision recorded 2026-09-07 (§14.25).
GOLDEN_AUTHORITY_DIGESTS = {
    "CP-PARSE": "b846913b3640a617eed311bf0708e84565278183e7219b715c39a2d86f1c324b",
    "CP-0": "f43ee24a2758c11bd9e9f7d34f1b0e8a6dbcdcbf02321e3e357a81f1945e824d",
    "CP-1": "895acfd0eb8c0198da030238c20b50283566f46b9dd9f5854aa5e5afe59f1412",
    "CP-1A": "f88796c7e7b1b9090507fce95890bea2a33c482bf9f710a1e1c5dc928e55f33b",
    "CP-1B": "5e6315da919d29af6cadc875fac5630ba7ffe4872e05e22092cdc715b5409ccc",
    "CP-1C": "114a4552d449dc46745ad245a3b2ead10b77b8801b26cfeeb762b1896f191f63",
    "CP-1D": "cde0623f13fb1279dddb0ae4a477ecbb8732d29a418cd9aaabd5a997c3749608",
    "CP-2": "cc0068491793ab4aca64c791d29e2093b1d28eece1d63c1db704711d14b28eca",
    "CP-2A": "2dec1b2c82b7b182de03c9d8faa89ef77b15112241a1437ad46e63a4e113b344",
    "CP-2E": "e950b4192a4cea729aa56d752b7913b32c532b643854bce69637234b4c983044",
    "CP-2G": "2128377f11e56436312972f4125b7cce8301717944061dcef8126856488c56a8",
    "CP-2H": "348648e482d762a26c046dcc397df80fa74f613f1a2c8d1d21ddc416b6cde985",
    "CP-3": "b0ac09a537e6c0419fb7392b6c85d92262668bf5719b652b255434931efa60ef",
    "CP-4": "9f6b466a7947e9897ff2c54a286989b14bebc3a217e95987f1a6cd3e60bf7618",
    "CP-4C": "a78c8c631a167312bd5041777e06617ae96c4d78aaccb11185f04e6bb2e47e16",
    "CP-5": "c9f258b2fae4fc34b51833d92cdfdbf12f3b992372134a07093a032c452fbc89",
    "CP-6": "e25429822d3406eb23efde3fb97faf224a025f5d2682f844e9af94773508a2f1",
    "CP-L10": "7c960f93973fd23ffc994c0f12a9561193c609c036516416a4cadb4276396ccf",
    # Recorded 2026-09-02 (Task 7) over the same pinned build.
    "CP-DR": "d3ba46d4f62131c2e95b380f0dbb6c49be23dbeba851a28941db6041124d20ac",
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
