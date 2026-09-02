"""Integrity-pinned execution boundary for Deploy V methodology calculators.

Only host-owned ``(module_id, calculator_id)`` pairs can select code.  Both the
calculator and its local helper module are read through no-follow file
descriptors, matched to the supplied Deploy V integrity manifest, and executed
from those verified bytes.  This keeps methodology code selection out of model
or provider output while making each calculation independently auditable.
"""

from __future__ import annotations

import copy
import hashlib
import math
import os
import stat
import sys
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType, ModuleType
from typing import Any, Callable, Mapping

from ..contracts import canonical_json, digest, validate_boundary_text

MAX_CALCULATION_INPUT_BYTES = 256 * 1024
MAX_CALCULATION_OUTPUT_BYTES = 1024 * 1024
MAX_CALCULATION_SCRIPT_BYTES = 1024 * 1024
MAX_CALCULATION_DEPTH = 16
MAX_CALCULATION_NODES = 20_000
MAX_CALCULATION_CONTAINER_ITEMS = 2_000
MAX_CALCULATION_STRING_CHARS = 32_000
MAX_CALCULATION_INTEGER_DIGITS = 100
MAX_RECOVERY_WATERFALL_WORK_UNITS = 100_000
MAX_BOND_YEARS = 100
MAX_CALL_SCHEDULE_ITEMS = 100

_SCHEMA_VERSION = "caos.methodology-calculation.v1"
_BINDING_SCHEMA_VERSION = "caos.methodology-calculator-binding.v1"
_HEX_DIGITS = frozenset("0123456789abcdef")
_LOAD_LOCK = threading.Lock()
_MISSING = object()


class MethodologyCalculationError(ValueError):
    """A public-safe refusal code with no vendor or filesystem details."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _CalculatorSpec:
    folder_slug: str
    relative_path: str
    dependency_files: tuple[str, ...] = ("scripts/cp_tables.py",)


@dataclass(frozen=True)
class _PinnedFile:
    size: int
    sha256: str


_CALCULATORS: Mapping[tuple[str, str], _CalculatorSpec] = MappingProxyType({
    ("CP-1", "credit_metrics"): _CalculatorSpec(
        "cp-1-canonical-data-foundation", "scripts/credit_metrics.py"
    ),
    ("CP-1B", "credit_metrics"): _CalculatorSpec(
        "cp-1b-earnings-delta", "scripts/credit_metrics.py"
    ),
    ("CP-1C", "peer_statistics"): _CalculatorSpec(
        "cp-1c-peer-benchmark", "scripts/peer_statistics.py"
    ),
    ("CP-2E", "rate_fx_sensitivity"): _CalculatorSpec(
        "cp-2e-macro-fx-hedging-sensitivity", "scripts/rate_fx_sensitivity.py"
    ),
    ("CP-2G", "credit_metrics"): _CalculatorSpec(
        "cp-2g-forward-credit-model", "scripts/credit_metrics.py"
    ),
    ("CP-2G", "liquidity_bridge"): _CalculatorSpec(
        "cp-2g-forward-credit-model", "scripts/liquidity_bridge.py"
    ),
    ("CP-2H", "bond_analytics"): _CalculatorSpec(
        "cp-2h-ratings-migration-trigger", "scripts/bond_analytics.py"
    ),
    ("CP-2H", "covenant_headroom"): _CalculatorSpec(
        "cp-2h-ratings-migration-trigger", "scripts/covenant_headroom.py"
    ),
    ("CP-3", "recovery_waterfall"): _CalculatorSpec(
        "cp-3-relative-value-security-selection", "scripts/recovery_waterfall.py"
    ),
    ("CP-4", "covenant_headroom"): _CalculatorSpec(
        "cp-4-legal-covenant-interpreter", "scripts/covenant_headroom.py"
    ),
    ("CP-4C", "funding_gap"): _CalculatorSpec(
        "cp-4c-restructuring-fulcrum", "scripts/funding_gap.py"
    ),
    ("CP-4C", "recovery_waterfall"): _CalculatorSpec(
        "cp-4c-restructuring-fulcrum", "scripts/recovery_waterfall.py"
    ),
})


def _fail(code: str) -> MethodologyCalculationError:
    return MethodologyCalculationError(code)


def _valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX_DIGITS for character in value)
    )


def _relative_parts(value: str) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
    candidate = PurePosixPath(value)
    parts = candidate.parts
    if candidate.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
    return parts


def _normalise_json(value: Any, *, error_code: str, byte_limit: int) -> Any:
    nodes = 0
    encoded_size = 0

    def charge(size: int) -> None:
        nonlocal encoded_size
        encoded_size += size
        if encoded_size > byte_limit:
            raise _fail(error_code)

    def visit(item: Any, depth: int) -> Any:
        nonlocal nodes
        nodes += 1
        if depth > MAX_CALCULATION_DEPTH or nodes > MAX_CALCULATION_NODES:
            raise _fail(error_code)

        item_type = type(item)
        if item is None or item_type is bool:
            charge(len(canonical_json(item)))
            return item
        if item_type is int:
            if abs(item) >= 10**MAX_CALCULATION_INTEGER_DIGITS:
                raise _fail(error_code)
            charge(len(str(item)))
            return item
        if item_type is float:
            if not math.isfinite(item):
                raise _fail(error_code)
            charge(len(canonical_json(item)))
            return item
        if item_type is str:
            try:
                normalised_string = validate_boundary_text(item)
            except ValueError:
                raise _fail(error_code) from None
            if len(normalised_string) > MAX_CALCULATION_STRING_CHARS:
                raise _fail(error_code)
            charge(len(canonical_json(normalised_string).encode("utf-8")))
            return normalised_string
        if item_type is list:
            if len(item) > MAX_CALCULATION_CONTAINER_ITEMS:
                raise _fail(error_code)
            charge(2 + max(0, len(item) - 1))
            return [visit(child, depth + 1) for child in item]
        if item_type is dict:
            if len(item) > MAX_CALCULATION_CONTAINER_ITEMS:
                raise _fail(error_code)
            charge(2 + max(0, len(item) - 1))
            result: dict[str, Any] = {}
            for key, child in item.items():
                if type(key) is not str:
                    raise _fail(error_code)
                try:
                    normalised_key = validate_boundary_text(key)
                except ValueError:
                    raise _fail(error_code) from None
                if len(normalised_key) > MAX_CALCULATION_STRING_CHARS:
                    raise _fail(error_code)
                if normalised_key in result:
                    raise _fail(error_code)
                charge(len(canonical_json(normalised_key).encode("utf-8")) + 1)
                result[normalised_key] = visit(child, depth + 1)
            return result
        raise _fail(error_code)

    normalised = visit(value, 0)
    try:
        encoded = canonical_json(normalised).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise _fail(error_code) from None
    if len(encoded) > byte_limit:
        raise _fail(error_code)
    return normalised


def _enforce_work_factor(calculator_id: str, inputs: dict[str, Any]) -> None:
    """Host-owned work-factor bounds (DECISIONS §14.8): the vendored scripts
    carry their own guards as defence in depth, but the host refuses first so a
    looser vendor script can never widen what model-authored inputs may cost."""
    if calculator_id == "bond_analytics":
        years = inputs.get("years_to_maturity")
        schedule = inputs.get("call_schedule")
        if (
            (type(years) in {int, float} and not 0 <= years <= MAX_BOND_YEARS)
            or (type(schedule) is list and len(schedule) > MAX_CALL_SCHEDULE_ITEMS)
        ):
            raise _fail("METHODOLOGY_INPUT_INVALID")
        return
    if calculator_id != "recovery_waterfall":
        return
    claims = inputs.get("claims")
    costs = inputs.get("costs")
    ev_cases = inputs.get("ev_cases")
    claim_count = len(claims) if type(claims) is list else 0
    cost_count = len(costs) if type(costs) is list else 0
    case_count = (1 if inputs.get("enterprise_value") is not None else 0) + (
        len(ev_cases) if type(ev_cases) is list else 0
    )
    if case_count * (1 + 2 * claim_count + cost_count) > MAX_RECOVERY_WATERFALL_WORK_UNITS:
        raise _fail("METHODOLOGY_INPUT_INVALID")


def calculation_output_complete(
    module_id: str,
    calculator_id: str,
    output: Any,
) -> bool:
    """Minimum usable deterministic result required for a successful module."""
    if not isinstance(output, dict):
        return False
    if calculator_id == "credit_metrics" and module_id in {"CP-1", "CP-1B", "CP-2G"}:
        periods = output.get("periods")
        return (
            isinstance(periods, dict)
            and bool(periods)
            and all(
                isinstance(period, dict)
                and isinstance(period.get("kpis"), dict)
                and any(
                    type(value) in {int, float} and math.isfinite(value)
                    for value in period["kpis"].values()
                )
                for period in periods.values()
            )
        )
    if (module_id, calculator_id) == ("CP-1C", "peer_statistics"):
        statistics = output.get("statistics_including_outliers")
        return (
            isinstance(statistics, dict)
            and statistics.get("status") == "calculated"
            and type(statistics.get("n")) is int
            and statistics["n"] >= 2
        )
    if (module_id, calculator_id) == ("CP-2E", "rate_fx_sensitivity"):
        return (
            output.get("status") == "complete"
            and type(output.get("cash_interest_impact_plus_100bps")) in {int, float}
            and math.isfinite(output["cash_interest_impact_plus_100bps"])
            and type(output.get("combined_adverse_annual_impact")) in {int, float}
            and math.isfinite(output["combined_adverse_annual_impact"])
        )
    if (module_id, calculator_id) == ("CP-2G", "liquidity_bridge"):
        components = output.get("components")
        return (
            output.get("status") == "complete"
            and isinstance(components, list)
            and bool(components)
            and all(
                isinstance(component, dict)
                and type(component.get("value")) in {int, float}
                and math.isfinite(component["value"])
                for component in components
            )
            and type(output.get("ending_accessible_liquidity")) in {int, float}
            and math.isfinite(output["ending_accessible_liquidity"])
            and output.get("null_components") == []
        )
    if (module_id, calculator_id) == ("CP-2H", "bond_analytics"):
        return (
            output.get("status") == "complete"
            and type(output.get("yield_to_worst")) in {int, float}
            and math.isfinite(output["yield_to_worst"])
        )
    if calculator_id == "covenant_headroom" and module_id in {"CP-2H", "CP-4"}:
        headroom = output.get("headroom")
        baskets = output.get("basket_capacity")
        if not isinstance(headroom, list) or not isinstance(baskets, list):
            return False
        rows = [*headroom, *baskets]
        return (
            output.get("status") == "complete"
            and bool(rows)
            and output.get("tests_with_missing_inputs") == []
            and any(
                isinstance(row, dict)
                and any(
                    type(row.get(field)) in {int, float} and math.isfinite(row[field])
                    for field in ("headroom", "remaining_capacity", "value", "total_capacity")
                )
                for row in rows
            )
        )
    if (module_id, calculator_id) == ("CP-3", "recovery_waterfall"):
        checks: list[bool] = []
        if "base" in output:
            base = output.get("base")
            claims = base.get("claims") if isinstance(base, dict) else None
            checks.append(
                isinstance(base, dict)
                and base.get("status") == "complete"
                and isinstance(claims, list)
                and bool(claims)
                and all(
                    isinstance(claim, dict)
                    and claim.get("status") != "Not Calculable"
                    for claim in claims
                )
                and any(
                    type(claim.get("recovery_pct")) in {int, float}
                    and math.isfinite(claim["recovery_pct"])
                    for claim in claims
                )
            )
        if "sensitivity" in output:
            sensitivity = output.get("sensitivity")
            cases = sensitivity.get("cases") if isinstance(sensitivity, dict) else None
            checks.append(
                isinstance(sensitivity, dict)
                and sensitivity.get("status") == "complete"
                and isinstance(cases, list)
                and bool(cases)
                and sensitivity.get("cases_computed") == len(cases)
            )
        return bool(checks) and all(checks)
    if (module_id, calculator_id) == ("CP-4C", "funding_gap"):
        views = [
            output.get("as_of_balance_sheet_date"),
            *(
                [output.get("pro_forma_for_subsequent_events")]
                if "pro_forma_for_subsequent_events" in output else []
            ),
        ]
        return bool(views) and all(
            isinstance(view, dict)
            and all(
                isinstance(view.get(section), dict)
                and view[section].get("status") == "complete"
                for section in ("maturity_wall", "liquidity", "gap")
            )
            and type(view["gap"].get("funding_gap")) in {int, float}
            for view in views
        )
    if (module_id, calculator_id) == ("CP-4C", "recovery_waterfall"):
        base = output.get("base")
        sensitivity = output.get("sensitivity")
        claims = base.get("claims") if isinstance(base, dict) else None
        return (
            isinstance(base, dict)
            and base.get("status") == "complete"
            and isinstance(claims, list)
            and bool(claims)
            and any(
                isinstance(claim, dict)
                and type(claim.get("recovery_pct")) in {int, float}
                for claim in claims
            )
            and (
                sensitivity is None
                or isinstance(sensitivity, dict)
                and sensitivity.get("status") == "complete"
            )
        )
    return False


def _module_from_bytes(name: str, source: bytes, display_path: Path) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(display_path)
    module.__package__ = ""
    code = compile(source, str(display_path), "exec")
    exec(code, module.__dict__)
    return module


class MethodologyCalculationRuntime:
    """Run the finite set of pure Deploy V calculation functions."""

    def __init__(self, root: Path, pinned_manifest: Mapping[str, Any]) -> None:
        self._root = Path(os.path.abspath(os.fspath(root)))
        self._build_id, self._pinned = self._parse_manifest(pinned_manifest)

    @staticmethod
    def _parse_manifest(
        pinned_manifest: Mapping[str, Any],
    ) -> tuple[str, dict[tuple[str, str], _PinnedFile]]:
        try:
            build_id = pinned_manifest["build_id"]
            skills = pinned_manifest["skills"]
        except (KeyError, TypeError):
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH") from None
        if not _valid_digest(build_id) or type(skills) is not list:
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")

        by_folder: dict[str, list[Mapping[str, Any]]] = {}
        for skill in skills:
            if not isinstance(skill, Mapping):
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            folder_slug = skill.get("folder_slug")
            if isinstance(folder_slug, str):
                by_folder.setdefault(folder_slug, []).append(skill)

        pinned: dict[tuple[str, str], _PinnedFile] = {}
        for spec in _CALCULATORS.values():
            matches = by_folder.get(spec.folder_slug, [])
            if len(matches) != 1:
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            hashes = matches[0].get("relative_file_hashes")
            if not isinstance(hashes, Mapping):
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            for relative in (spec.relative_path, *spec.dependency_files):
                _relative_parts(relative)
                record = hashes.get(relative)
                if not isinstance(record, Mapping):
                    raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
                size = record.get("bytes")
                sha256 = record.get("sha256")
                if (
                    type(size) is not int
                    or not 0 < size <= MAX_CALCULATION_SCRIPT_BYTES
                    or not _valid_digest(sha256)
                ):
                    raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
                key = (spec.folder_slug, relative)
                pin = _PinnedFile(size=size, sha256=sha256)
                previous = pinned.setdefault(key, pin)
                if previous != pin:
                    raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
        return build_id, pinned

    def calculator_ids(self, module_id: str) -> tuple[str, ...]:
        return tuple(sorted(calculator for module, calculator in _CALCULATORS if module == module_id))

    def _read_verified(self, folder_slug: str, relative: str) -> tuple[bytes, _PinnedFile]:
        folder_parts = _relative_parts(folder_slug)
        relative_parts = _relative_parts(relative)
        try:
            expected = self._pinned[(folder_slug, relative)]
        except KeyError:
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH") from None

        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if no_follow is None or os.open not in os.supports_dir_fd:
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
        descriptors: list[int] = []
        try:
            root_parts = self._root.parts
            if not self._root.anchor or not root_parts:
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            current = os.open(self._root.anchor, directory_flags | no_follow)
            descriptors.append(current)
            for part in (
                *root_parts[1:],
                "skills",
                *folder_parts,
                *relative_parts[:-1],
            ):
                current = os.open(part, directory_flags | no_follow, dir_fd=current)
                descriptors.append(current)
            file_descriptor = os.open(
                relative_parts[-1], os.O_RDONLY | no_follow, dir_fd=current
            )
            descriptors.append(file_descriptor)
            before = os.fstat(file_descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected.size:
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            chunks: list[bytes] = []
            remaining = expected.size + 1
            while remaining:
                chunk = os.read(file_descriptor, min(remaining, 64 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            after = os.fstat(file_descriptor)
            if (
                len(data) != expected.size
                or hashlib.sha256(data).hexdigest() != expected.sha256
                or (before.st_dev, before.st_ino, before.st_size)
                != (after.st_dev, after.st_ino, after.st_size)
            ):
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
            return data, expected
        except MethodologyCalculationError:
            raise
        except (OSError, ValueError):
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH") from None
        finally:
            for descriptor in reversed(descriptors):
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def _verified_files(
        self, module_id: str, calculator_id: str, spec: _CalculatorSpec
    ) -> tuple[dict[str, bytes], dict[str, Any]]:
        relative_files = (spec.relative_path, *spec.dependency_files)
        verified: dict[str, bytes] = {}
        pins: dict[str, _PinnedFile] = {}
        for relative in relative_files:
            source, pin = self._read_verified(spec.folder_slug, relative)
            verified[relative] = source
            pins[relative] = pin

        dependencies = {
            relative: pins[relative].sha256 for relative in spec.dependency_files
        }
        binding_authority = {
            "schema_version": _BINDING_SCHEMA_VERSION,
            "methodology_build_id": self._build_id,
            "module_id": module_id,
            "calculator_id": calculator_id,
            "folder_slug": spec.folder_slug,
            "script": {
                "relative_path": spec.relative_path,
                "bytes": pins[spec.relative_path].size,
                "sha256": pins[spec.relative_path].sha256,
            },
            "dependencies": [
                {
                    "relative_path": relative,
                    "bytes": pins[relative].size,
                    "sha256": pins[relative].sha256,
                }
                for relative in spec.dependency_files
            ],
        }
        binding = {
            "methodology_build_id": self._build_id,
            "module_id": module_id,
            "calculator_id": calculator_id,
            "script_digest": pins[spec.relative_path].sha256,
            "script_bytes": pins[spec.relative_path].size,
            "dependency_digests": dependencies,
            "calculator_digest": digest(binding_authority),
        }
        return verified, binding

    def _load_compute(
        self, spec: _CalculatorSpec
    ) -> tuple[Callable[[dict[str, Any]], Any], dict[str, Any]]:
        try:
            module_id, calculator_id = next(
                identity for identity, candidate in _CALCULATORS.items() if candidate is spec
            )
        except StopIteration:
            raise _fail("METHODOLOGY_CALCULATOR_NOT_ALLOWED") from None

        verified, binding = self._verified_files(module_id, calculator_id, spec)
        dependency = spec.dependency_files[0]
        display_root = self._root / "skills" / spec.folder_slug
        module_suffix = binding["calculator_digest"][:16]
        with _LOAD_LOCK:
            prior_alias = sys.modules.get("cp_tables", _MISSING)
            prior_path = list(sys.path)
            prior_dont_write_bytecode = sys.dont_write_bytecode
            try:
                tables = _module_from_bytes(
                    f"caos_methodology_cp_tables_{module_suffix}",
                    verified[dependency],
                    display_root / dependency,
                )
                sys.modules["cp_tables"] = tables
                module = _module_from_bytes(
                    f"caos_methodology_calculator_{module_suffix}",
                    verified[spec.relative_path],
                    display_root / spec.relative_path,
                )
            except Exception:
                raise _fail("METHODOLOGY_AUTHORITY_MISMATCH") from None
            finally:
                sys.path[:] = prior_path
                sys.dont_write_bytecode = prior_dont_write_bytecode
                if prior_alias is _MISSING:
                    sys.modules.pop("cp_tables", None)
                else:
                    sys.modules["cp_tables"] = prior_alias
        compute = getattr(module, "compute", None)
        if not callable(compute):
            raise _fail("METHODOLOGY_AUTHORITY_MISMATCH")
        return compute, binding

    def binding_manifest(self) -> list[dict[str, Any]]:
        bindings = []
        for (module_id, calculator_id), spec in sorted(_CALCULATORS.items()):
            _, binding = self._verified_files(module_id, calculator_id, spec)
            bindings.append(binding)
        return bindings

    def execute(
        self, module_id: str, calculator_id: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            spec = _CALCULATORS[(module_id, calculator_id)]
        except KeyError:
            raise _fail("METHODOLOGY_CALCULATOR_NOT_ALLOWED") from None
        if type(inputs) is not dict:
            raise _fail("METHODOLOGY_INPUT_INVALID")
        normalised_input = _normalise_json(
            inputs,
            error_code="METHODOLOGY_INPUT_INVALID",
            byte_limit=MAX_CALCULATION_INPUT_BYTES,
        )
        _enforce_work_factor(calculator_id, normalised_input)
        canonical_input = copy.deepcopy(normalised_input)
        input_digest = digest(canonical_input)
        compute, binding = self._load_compute(spec)
        try:
            output = compute(normalised_input)
        except Exception:
            raise _fail("METHODOLOGY_CALCULATION_FAILED") from None
        normalised_output = _normalise_json(
            output,
            error_code="METHODOLOGY_OUTPUT_INVALID",
            byte_limit=MAX_CALCULATION_OUTPUT_BYTES,
        )
        return {
            "schema_version": _SCHEMA_VERSION,
            **binding,
            "canonical_input": canonical_input,
            "input_digest": input_digest,
            "output_digest": digest(normalised_output),
            "canonical_output": normalised_output,
        }
