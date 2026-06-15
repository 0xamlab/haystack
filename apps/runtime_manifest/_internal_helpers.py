"""Internal helpers: validation error formatters, sha256, canonical JSON, signing, validate_* entry points.

Extracted from apps/runtime_manifest.py during modularization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar, get_origin

from pydantic import (
    BaseModel,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from apps.api_server.config import get_settings
from apps.api_server.services.execution_policy_service import default_policy_payload
from apps.platform_contract import load_platform_contract_manifest
from apps.runtime.mojo_inventory import build_inventory_report
from apps.runtime_manifest._module_order import LLM_ROLLOUT_MODULE_ORDER

from apps.runtime_manifest._constants import *  # noqa: F401, F403
from apps.runtime_manifest._constants import (
    _ADMIN_ENDPOINTS,
    _COMPILED_ARTIFACT_PATH,
    _CONTROL_PLANE_SIGNATURE_KEY_ID,
    _FEATURE_FLAG_ENDPOINTS,
    _KERNEL_ISOLATION_PROOF_REF,
    _KERNEL_OWNER,
    _KERNEL_REPLAY_PROOF_REF,
    _KERNEL_SCHEMA_COMPAT_REPORT_REF,
    _LLM_CORE_MANIFEST,
    _MODULE_BENCHMARK_NAME_MAP,
    _MODULE_MANIFEST_VERSION,
    _MOJO_BINARY_PATH,
    _PARITY_ARTIFACT_PATH,
    _PROOF_BUNDLE_PATH,
    _PUBLIC_ENDPOINTS,
    _ROOT,
    _RUNTIME_VERSION,
)
from apps.runtime_manifest._base import *  # noqa: F401, F403
from apps.runtime_manifest._enums import *  # noqa: F401, F403
from apps.runtime_manifest._models_basic import *  # noqa: F401, F403
from apps.runtime_manifest._models_admin import *  # noqa: F401, F403
from apps.runtime_manifest._errors import (
    RuntimeManifestBuildError,
    _manifest_error_details,
    _raise_manifest_integrity_error,
    _raise_on_duplicate_values,
)
from apps.runtime_manifest._models_manifest import (
    RuntimeManifestResponse,
)


def _format_runtime_manifest_validation_path(location: tuple[Any, ...]) -> str:
    return ".".join(str(item) for item in location if str(item))


def _build_runtime_manifest_error_details(exc: ValidationError) -> dict[str, Any]:
    try:
        errors = exc.errors(include_url=False, include_context=True, include_input=False)
    except TypeError:  # pragma: no cover - compatibility guard
        errors = exc.errors()

    normalized_errors: list[dict[str, str]] = []
    cause: str | None = None
    for error in errors:
        ctx = error.get("ctx")
        nested_error = ctx.get("error") if isinstance(ctx, dict) else None
        if isinstance(nested_error, RuntimeManifestBuildError):
            nested_details = nested_error.details if isinstance(nested_error.details, dict) else {}
            nested_validation_errors = nested_details.get("validation_errors")
            if isinstance(nested_validation_errors, list):
                normalized_errors.extend(
                    item for item in nested_validation_errors if isinstance(item, dict)
                )
            nested_cause = nested_details.get("cause")
            if cause is None and isinstance(nested_cause, str) and nested_cause:
                cause = nested_cause
            if normalized_errors:
                continue
        path = _format_runtime_manifest_validation_path(tuple(error.get("loc") or ()))
        normalized_errors.append(
            {
                "path": path,
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
        )

    if cause is None:
        cause = next(
            (str(item.get("path")) for item in normalized_errors if item.get("path")),
            str(exc),
        )
    details: dict[str, Any] = {"cause": cause}
    if normalized_errors:
        details["validation_errors"] = normalized_errors
    return details


def _format_runtime_manifest_build_error_message(details: dict[str, Any]) -> str:
    return _format_runtime_payload_build_error_message(
        "Signed runtime manifest build produced an invalid payload.",
        details,
    )


def _format_runtime_payload_build_error_message(prefix: str, details: dict[str, Any]) -> str:
    cause = details.get("cause")
    if isinstance(cause, str) and cause:
        return f"{prefix}: {cause}"
    return prefix


def _raise_runtime_payload_build_error(
    code: str,
    prefix: str,
    exc: ValidationError,
) -> None:
    details = _build_runtime_manifest_error_details(exc)
    raise RuntimeManifestBuildError(
        code,
        _format_runtime_payload_build_error_message(prefix, details),
        details,
    ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _build_artifact_reference(path: Path, *, kind: RuntimeArtifactKind) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=str(path.relative_to(_ROOT)),
        sha256=_sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def _manifest_signing_secret() -> str:
    settings = get_settings()
    seed = settings.license_signing_secret or settings.jwt_secret
    return hashlib.sha256(f"{seed}:runtime-manifest-signing".encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _detect_mojo_version() -> str:
    candidate = os.getenv("MOJO_VERSION")
    if candidate:
        return candidate.strip()
    executable = shutil.which("mojo")
    if executable is None:
        return "unknown"
    try:
        proc = subprocess.run(  # noqa: S603
            [executable, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    output = (proc.stdout or proc.stderr).strip()
    return output or "unknown"


def _deployment_mode() -> str:
    raw_mode = os.getenv("ALGENTA_DEPLOYMENT_MODE", "").strip().lower()
    if raw_mode in {
        "saas",
        "vpc",
        "self_hosted",
        "air_gapped",
        "hybrid_provider",
        "local_dev_daemon",
    }:
        return raw_mode
    settings = get_settings()
    return "local_dev_daemon" if settings.is_development else "saas"


def _runtime_deployment_mode_value(value: object) -> str:
    if isinstance(value, RuntimeDeploymentMode):
        return value.value
    return str(value)


def _enum_values(values: list[object]) -> list[str]:
    return [item.value if isinstance(item, Enum) else str(item) for item in values]


def _raw_runtime_dict_key(value: object) -> str:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    return str(value)


def _raw_runtime_payload(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {
            field_name: _raw_runtime_payload(getattr(value, field_name))
            for field_name in value.__class__.model_fields
        }
    if isinstance(value, list):
        return [_raw_runtime_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_raw_runtime_payload(item) for item in value]
    if isinstance(value, dict):
        return {
            _raw_runtime_dict_key(key): _raw_runtime_payload(item)
            for key, item in value.items()
        }
    return value


def normalize_runtime_validation_payload(value: Any) -> Any:
    return _raw_runtime_payload(value)


RuntimePayloadModelT = TypeVar("RuntimePayloadModelT", bound=BaseModel)


def validate_runtime_payload(
    payload: Any,
    *,
    model: type[RuntimePayloadModelT],
    code: str,
    prefix: str,
) -> RuntimePayloadModelT:
    try:
        return model.model_validate(normalize_runtime_validation_payload(payload))
    except ValidationError as exc:
        _raise_runtime_payload_build_error(code, prefix, exc)


def validate_runtime_manifest_payload(payload: Any) -> RuntimeManifestResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeManifestResponse,
        code="invalid_runtime_manifest_payload",
        prefix="Signed runtime manifest build produced an invalid payload.",
    )


def validate_runtime_admin_modules_payload(payload: Any) -> RuntimeAdminModulesResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeAdminModulesResponse,
        code="invalid_runtime_admin_modules_payload",
        prefix="Signed runtime admin modules payload is invalid.",
    )


def validate_runtime_admin_benchmarks_payload(payload: Any) -> RuntimeAdminBenchmarksResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeAdminBenchmarksResponse,
        code="invalid_runtime_admin_benchmarks_payload",
        prefix="Signed runtime admin benchmarks payload is invalid.",
    )


def validate_runtime_release_validation_payload(
    payload: Any,
) -> RuntimeReleaseValidationResponse:
    return validate_runtime_payload(
        payload,
        model=RuntimeReleaseValidationResponse,
        code="invalid_runtime_release_validation_payload",
        prefix="Signed runtime release validation payload is invalid.",
    )


def _validated_runtime_manifest_for_surface(
    manifest: RuntimeManifestResponse,
    *,
    code: str,
    prefix: str,
) -> RuntimeManifestResponse:
    try:
        return validate_runtime_manifest_payload(_raw_runtime_payload(manifest))
    except RuntimeManifestBuildError as exc:
        raise RuntimeManifestBuildError(
            code,
            _format_runtime_payload_build_error_message(prefix, exc.details),
            dict(exc.details),
        ) from exc


def _try_runtime_deployment_mode(value: object) -> RuntimeDeploymentMode | None:
    try:
        return RuntimeDeploymentMode(_runtime_deployment_mode_value(value))
    except ValueError:
        return None

