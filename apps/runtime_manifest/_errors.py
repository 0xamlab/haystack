"""RuntimeManifestBuildError + manifest integrity error helpers.

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
from benchmarks.llm_compiled_runtime_benchmark import TARGET_MODULES as LLM_ROLLOUT_MODULE_ORDER

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


class RuntimeManifestBuildError(ValueError):
    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _manifest_error_details(path: str, message: str) -> dict[str, Any]:
    return {
        "cause": path,
        "validation_errors": [
            {
                "path": path,
                "message": message,
                "type": "value_error",
            }
        ],
    }


def _raise_manifest_integrity_error(path: str, message: str) -> None:
    raise RuntimeManifestBuildError(
        "invalid_runtime_manifest_payload",
        message,
        _manifest_error_details(path, message),
    )


def _raise_on_duplicate_values(
    values: list[Any],
    path: str,
    value_selector: Any,
    label: str,
) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for entry in values:
        raw_value = value_selector(entry)
        normalized = raw_value.value if isinstance(raw_value, Enum) else str(raw_value)
        if normalized in seen and normalized not in duplicates:
            duplicates.append(normalized)
        seen.add(normalized)
    if duplicates:
        duplicate_text = ", ".join(duplicates)
        _raise_manifest_integrity_error(
            path,
            f"{label} must be unique; duplicate entries: {duplicate_text}",
        )


