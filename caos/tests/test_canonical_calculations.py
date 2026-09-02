from __future__ import annotations

import pytest
from pydantic import ValidationError

from caos.methodology.canonical import CalculationRef, CanonicalModuleOutput


def _calculation_ref(**changes: str) -> dict[str, str]:
    value = {
        "calculator_id": "credit_metrics",
        "script_digest": "a" * 64,
        "calculator_digest": "b" * 64,
        "input_digest": "c" * 64,
        "output_digest": "d" * 64,
    }
    return {**value, **changes}


def _canonical_output(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "markdown": "# ok",
        "evidence_refs": [{"source_id": "source-1", "block_id": "block-1"}],
        "lineage_counts": {"directly_sourced": 1},
        "fields_present": 1,
        "fields_total": 1,
        "source_gate": "pass",
    }
    return {**value, **changes}


def test_calculation_refs_are_optional_for_existing_provider_outputs():
    output = CanonicalModuleOutput.model_validate(_canonical_output())

    assert output.calculation_refs == []


def test_calculation_ref_is_strict_and_immutable():
    ref = CalculationRef.model_validate(_calculation_ref())

    with pytest.raises(ValidationError, match="Instance is frozen"):
        ref.output_digest = "e" * 64
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CalculationRef.model_validate({**_calculation_ref(), "output": {}})


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("script_digest", "a" * 63),
        ("calculator_digest", "A" * 64),
        ("input_digest", "g" * 64),
        ("output_digest", "d" * 65),
    ],
)
def test_calculation_ref_requires_exact_lowercase_sha256(field: str, invalid: str):
    with pytest.raises(ValidationError):
        CalculationRef.model_validate(_calculation_ref(**{field: invalid}))


def test_canonical_output_accepts_only_bounded_calculation_refs():
    output = CanonicalModuleOutput.model_validate(
        _canonical_output(calculation_refs=[_calculation_ref()])
    )

    assert output.calculation_refs == [CalculationRef.model_validate(_calculation_ref())]
    with pytest.raises(ValidationError):
        CanonicalModuleOutput.model_validate(
            _canonical_output(calculation_refs=[_calculation_ref()] * 201)
        )
