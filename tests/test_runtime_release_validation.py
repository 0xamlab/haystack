from __future__ import annotations

import pytest

from apps.runtime_manifest import (
    ReleaseCondition,
    RuntimeManifestBuildError,
    build_runtime_release_validation,
    get_runtime_manifest,
    get_runtime_release_validation,
    validate_runtime_release_validation_payload,
)


def test_runtime_release_validation_passes_for_current_signed_manifest() -> None:
    validation = build_runtime_release_validation(get_runtime_manifest())

    assert validation.valid_release is True
    assert [entry.condition for entry in validation.conditions] == [
        ReleaseCondition.manifest_listed,
        ReleaseCondition.proof_backed,
        ReleaseCondition.policy_covered,
        ReleaseCondition.replay_tested,
        ReleaseCondition.deployment_mode_validated,
    ]
    assert all(entry.satisfied for entry in validation.conditions)
    assert validation.deployment_mode is not None
    assert validation.deployment_mode.value == "local_dev_daemon"
    assert validation.deployment_mode_raw == "local_dev_daemon"


def test_runtime_release_validation_fails_when_module_proof_artifacts_are_missing() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.modules[0].proof_artifacts = []

    validation = build_runtime_release_validation(manifest)
    proof_condition = next(
        entry
        for entry in validation.conditions
        if entry.condition is ReleaseCondition.proof_backed
    )

    assert validation.valid_release is False
    assert proof_condition.satisfied is False


def test_runtime_release_validation_fails_when_replay_failures_are_not_declared() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.external_nondeterminism.failure_codes = []

    validation = build_runtime_release_validation(manifest)
    replay_condition = next(
        entry
        for entry in validation.conditions
        if entry.condition is ReleaseCondition.replay_tested
    )

    assert validation.valid_release is False
    assert replay_condition.satisfied is False


def test_runtime_release_validation_fails_when_admin_endpoint_boundary_drifts() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.advertised_capabilities.admin_endpoints = ["/v1/admin/runtime/validation"]

    validation = build_runtime_release_validation(manifest)
    manifest_condition = next(
        entry
        for entry in validation.conditions
        if entry.condition is ReleaseCondition.manifest_listed
    )

    assert validation.valid_release is False
    assert manifest_condition.satisfied is False


def test_runtime_manifest_validator_fails_cleanly_when_admin_endpoint_boundary_drifts() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.advertised_capabilities.admin_endpoints = ["/v1/admin/runtime/validation"]

    with pytest.raises(
        RuntimeManifestBuildError,
        match="admin endpoint boundary drifted",
    ) as exc_info:
        manifest.validate_manifest()

    assert exc_info.value.code == "invalid_runtime_manifest_payload"
    assert exc_info.value.details["cause"] == "advertised_capabilities.admin_endpoints"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "advertised_capabilities.admin_endpoints"
    )


def test_runtime_release_validation_fails_when_policy_contract_is_missing() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.capability_algebra.required_fields = [
        field for field in manifest.capability_algebra.required_fields if field != "required_policy"
    ]

    validation = build_runtime_release_validation(manifest)
    policy_condition = next(
        entry
        for entry in validation.conditions
        if entry.condition is ReleaseCondition.policy_covered
    )

    assert validation.valid_release is False
    assert policy_condition.satisfied is False


def test_runtime_release_validation_fails_when_active_deployment_mode_is_unsupported() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.deployment_mode = "shadow_realm"

    validation = build_runtime_release_validation(manifest)
    deployment_condition = next(
        entry
        for entry in validation.conditions
        if entry.condition is ReleaseCondition.deployment_mode_validated
    )

    assert validation.valid_release is False
    assert deployment_condition.satisfied is False
    assert validation.deployment_mode is None
    assert validation.deployment_mode_raw == "shadow_realm"


def test_build_runtime_release_validation_fails_closed_for_invalid_internal_manifest_payload() -> None:
    manifest = get_runtime_manifest().model_copy(deep=True)
    manifest.signature.signature_hex = None

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        build_runtime_release_validation(manifest)

    assert exc_info.value.code == "invalid_runtime_release_validation_payload"
    assert exc_info.value.details["cause"] == "signature.signature_hex"
    assert exc_info.value.details["validation_errors"][0]["path"] == "signature.signature_hex"


def test_validate_runtime_release_validation_payload_fails_closed_for_duplicate_conditions() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"].append(dict(payload["conditions"][0]))

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_release_validation_payload(payload)

    assert exc_info.value.code == "invalid_runtime_release_validation_payload"
    assert exc_info.value.details["cause"] == "conditions"
    assert exc_info.value.details["validation_errors"][0]["path"] == "conditions"


def test_validate_runtime_release_validation_payload_fails_closed_for_duplicate_condition_evidence_paths() -> None:
    payload = get_runtime_release_validation().model_dump(mode="json")
    payload["conditions"][0]["evidence_paths"].append(payload["conditions"][0]["evidence_paths"][0])

    with pytest.raises(RuntimeManifestBuildError) as exc_info:
        validate_runtime_release_validation_payload(payload)

    assert exc_info.value.code == "invalid_runtime_release_validation_payload"
    assert exc_info.value.details["cause"] == "conditions.0.evidence_paths"
    assert exc_info.value.details["validation_errors"][0]["path"] == (
        "conditions.0.evidence_paths"
    )
