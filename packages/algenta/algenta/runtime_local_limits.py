from __future__ import annotations

from collections.abc import Callable
from typing import Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError

_HOSTED_LOCAL_RUNTIME_UNAVAILABLE_MESSAGE = (
    "Hosted local runtime limits require the full Algenta local runtime components. "
    "Use the repository runtime path or install the full runtime distribution before "
    "enabling enforce_limits."
)


def uses_hosted_local_limits(*, mode: str, enforce_limits: bool) -> bool:
    from apps.privacy_policy import policy_from_environment

    policy = policy_from_environment()
    if policy.deployment_mode in {"self_hosted", "air_gapped"}:
        return False
    return mode == "local" and enforce_limits


def ensure_local_execution_entitlement(
    *,
    enabled: bool,
    api_key: str | None,
    current_license: Any,
) -> Any:
    from apps.privacy_policy import policy_from_environment

    policy = policy_from_environment()
    require_local_license = policy.require_local_license
    # P5: the default-OFF enforce_license_validation opt-in also gates pure-local execution, so a
    # later default-flip makes Runtime() fail closed too. Default OFF → unchanged early return.
    if not enabled and not require_local_license and not policy.enforce_license_validation:
        return current_license
    if enabled and not api_key and not require_local_license:
        raise RuntimeConfigurationError(
            "api_key_required",
            "Hosted local runtime limits require an API key.",
        )
    try:
        from apps.runtime.license import load_license
    except ImportError as exc:  # pragma: no cover - exercised in packaged environments
        raise RuntimeConfigurationError(
            "hosted_local_runtime_unavailable",
            _HOSTED_LOCAL_RUNTIME_UNAVAILABLE_MESSAGE,
        ) from exc

    license_record = load_license(api_key or "")
    if require_local_license:
        if not license_record.valid:
            raise RuntimeConfigurationError(
                "license_required",
                license_record.message or "A valid local signed license is required.",
                {
                    "source": getattr(license_record, "source", "unknown"),
                    "plan": getattr(license_record, "plan", "unknown"),
                },
            )
        return license_record
    if not license_record.valid:
        raise RuntimeConfigurationError(
            "license_required",
            license_record.message or "A valid local device license is required.",
            {
                "source": getattr(license_record, "source", "unknown"),
                "plan": getattr(license_record, "plan", "unknown"),
            },
        )
    return license_record


def consume_local_credit(
    *,
    enabled: bool,
    run_sync: Callable[[Any], Any],
) -> None:
    if not enabled:
        return
    try:
        from apps.runtime.credits import consume_credit
    except ImportError as exc:  # pragma: no cover - exercised in packaged environments
        raise RuntimeConfigurationError(
            "hosted_local_runtime_unavailable",
            _HOSTED_LOCAL_RUNTIME_UNAVAILABLE_MESSAGE,
        ) from exc

    permitted = bool(run_sync(consume_credit(allow_background_refresh=False)))
    if not permitted:
        raise RuntimeValidationError(
            "quota_exhausted",
            (
                "Local execution quota exhausted. Reconnect to the control plane to "
                "refresh credits or renew the device license before continuing."
            ),
        )
