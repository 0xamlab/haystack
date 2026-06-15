"""Module-level constants: paths, versions, endpoint tuples, kernel refs.

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



_ROOT = Path(__file__).resolve().parents[2]
_PROOF_BUNDLE_PATH = _ROOT / "build" / "llm_rollout_proof_bundle.json"
_PARITY_ARTIFACT_PATH = _ROOT / "build" / "llm_rollout_parity_benchmark.json"
_COMPILED_ARTIFACT_PATH = _ROOT / "build" / "llm_compiled_runtime_benchmark.json"
_MOJO_BINARY_PATH = _ROOT / "mojo_build" / "simulate"

_RUNTIME_VERSION = "2026.05.0"
_LLM_CORE_MANIFEST = "llm-core-v1"
_MODULE_MANIFEST_VERSION = "runtime-manifest-v1"
_CONTROL_PLANE_SIGNATURE_KEY_ID = "runtime-manifest-signing-v1"
_PUBLIC_ENDPOINTS = (
    "/v1/meta/contract",
    "/v1/runtime/manifest",
)
_ADMIN_ENDPOINTS = (
    "/v1/admin/runtime/modules",
    "/v1/admin/runtime/benchmarks",
    "/v1/admin/runtime/validation",
)
_FEATURE_FLAG_ENDPOINTS = (
    "/v1/libraries",
    "/v1/libraries/health",
    "/v1/libraries/execute",
)
_KERNEL_SCHEMA_COMPAT_REPORT_REF = "tests/test_runtime_schema_surface.py"
_KERNEL_ISOLATION_PROOF_REF = "tests/test_runtime_manifest.py"
_KERNEL_REPLAY_PROOF_REF = "tests/test_runtime_release_validation.py"
_KERNEL_OWNER = "algenta-runtime-core"
_MODULE_BENCHMARK_NAME_MAP = {
    "text.tokenizer": "text_tokenizer",
    "vector_kernels.ranker": "vector_kernels_ranker",
    "vector_kernels.table": "vector_kernels_table",
}


