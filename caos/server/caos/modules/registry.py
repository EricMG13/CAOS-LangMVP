"""Module registry — the declarative seam (DECISIONS §7, §11.5, §11.7).

One entry per live catalog module. Execution mode is per (module, profile):
SCREEN routes are deterministic end to end (recorded MVP choice). Adding or
upgrading a module touches this file alone. Superseded IDs resolve through the
alias map from the catalog's superseded_module_ids, with the CP-PARSE carve-out
(MODULE_GRANULARITY.md): CP-PARSE addresses its own stage-0 node, never CP-0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    mode_full: str  # "agent" | "deterministic"
    mode_screen: str = "deterministic"
    skill_slug: str | None = None
    reference_files: tuple[str, ...] = ()
    max_output_tokens: int = 0
    derived_projections: tuple[str, ...] = ()
    source_mode: str = "supplied_only"

    @property
    def authority_digest(self) -> str:
        # §12.7: the golden digest is a recorded literal — changing wrapper
        # text, reference order, or the join is a methodology change and must
        # move these constants deliberately.
        return GOLDEN_AUTHORITY_DIGESTS[self.module_id]


# digest({"authority": assemble_authority(module_id)}) over the pinned
# deploy_v build, recorded 2026-08-26.
GOLDEN_AUTHORITY_DIGESTS = {
    "CP-1": "71dd70efc79410edd80af7648572782cd694f05aa754d1abd03b6dcb93885cd6",
    "CP-1A": "9157ed912eb73e21cd51479abe8fc446f895949da673a3e366df8f7c76a9eede",
    "CP-1B": "1d2757874da74caa48ac88d2474d1d5b4ff48982414bb53ba785296f3e684bc1",
    "CP-1C": "01f2787934b06e900125cd3119324621c8436e51683b7a5644db7b77dc75342c",
    "CP-1D": "0d2841369e275c430434d0c5287ef223dd2ec3c0d404ac1660efc8f028697939",
    "CP-2": "5fb286e7d673de8f621df805948409062da8dd469930bc8df83a92044e440e41",
    "CP-2A": "842663c8c017297102b9abd8569e782103f982d8b62cfafe52a2e9f8c3b390ef",
    "CP-2G": "86d9b25b264c1f1f94690fa61bdd9944acd0201264f287aa41049225bb84931c",
}


MODULES: dict[str, ModuleSpec] = {
    "CP-PARSE": ModuleSpec("CP-PARSE", "deterministic"),
    "CP-0": ModuleSpec("CP-0", "deterministic", skill_slug="cp-0-source-readiness"),
    "CP-1": ModuleSpec(
        "CP-1", "agent", skill_slug="cp-1-canonical-data-foundation",
        reference_files=("references/CP-1_RUNBOOK.md", "references/CP-1_SCHEMA_REFERENCE.md", "references/REF_CP-1_STEPS.md"),
        max_output_tokens=32_000,
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
    ),
    "CP-1C": ModuleSpec(
        "CP-1C", "agent", skill_slug="cp-1c-peer-benchmark",
        reference_files=("references/CP-1C_SCHEMA_REFERENCE.md", "references/REF_CP-1C_STEPS.md"),
        max_output_tokens=12_000,
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
    "CP-2E": ModuleSpec("CP-2E", "deterministic", skill_slug="cp-2e-macro-fx-hedging-sensitivity"),
    "CP-2G": ModuleSpec(
        "CP-2G", "agent", skill_slug="cp-2g-forward-credit-model",
        reference_files=("references/CP-2G_ForwardCreditModel.schema.md", "references/REF_CP-2G_STEPS.md"),
        max_output_tokens=24_000,
    ),
    "CP-2H": ModuleSpec("CP-2H", "deterministic", skill_slug="cp-2h-ratings-migration-trigger"),
    "CP-3": ModuleSpec("CP-3", "deterministic", skill_slug="cp-3-relative-value-security-selection"),
    "CP-4": ModuleSpec("CP-4", "deterministic", skill_slug="cp-4-legal-covenant-interpreter"),
    "CP-4C": ModuleSpec("CP-4C", "deterministic", skill_slug="cp-4c-restructuring-fulcrum"),
    "CP-5": ModuleSpec("CP-5", "deterministic", skill_slug="cp-5-evidence-trace-validator"),
    "CP-6": ModuleSpec("CP-6", "deterministic", skill_slug="cp-6-ic-debate-challenge"),
    "CP-L10": ModuleSpec("CP-L10", "deterministic", skill_slug="cp-l10-financial-change-screen"),
}


# Catalog superseded_module_ids, transcribed; CP-PARSE carve-out applied.
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
    # CP-PARSE carve-out: the catalog says absorbed_by CP-0, but compile() emits
    # CP-PARSE as its own stage-0 node — it resolves to itself, never CP-0.
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
