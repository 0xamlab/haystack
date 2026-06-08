"""Tests for test_runtime_manifest_model_validation: runtime_release.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-2/tests/test_runtime_manifest_model_validation.py during modularization.
"""
from __future__ import annotations

from tests._test_runtime_manifest_model_validation_helpers import *  # noqa: F401,F403


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_duplicate_conditions(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"].append(dict(payload["conditions"][0]))

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "conditions" in str(exc_info.value)
    assert "manifest-listed" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_duplicate_condition_evidence_paths(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    if model_cls is decision_engine_manifest_models.RuntimeReleaseValidationResult:
        assert "conditions.0.evidence_paths" in str(exc_info.value)
    assert "/v1/runtime/manifest" in str(exc_info.value)
    assert "duplicate entries" in str(exc_info.value)


@pytest.mark.parametrize(
    "model_cls",
    [
        ProducerRuntimeReleaseValidationResponse,
        decision_engine_manifest_models.RuntimeReleaseValidationResult,
    ],
)
def test_runtime_release_validation_models_reject_boolean_coercion(
    model_cls: type[object],
) -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["valid_release"] = "yes"
    payload["conditions"][0]["satisfied"] = "no"

    with pytest.raises(ValidationError) as exc_info:
        model_cls.model_validate(payload)

    assert "valid_release" in str(exc_info.value)
    assert "conditions.0.satisfied" in str(exc_info.value)


