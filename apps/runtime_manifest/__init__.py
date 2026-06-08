"""Runtime manifest — public facade.

The implementation is split into _<name>.py submodules of this package
for maintainability (each well under 1000 lines). This __init__.py
re-exports the complete public API so existing imports continue to
work unchanged for all 26 downstream callers.
"""
from __future__ import annotations

from apps.runtime_manifest._constants import *  # noqa: F401, F403
from apps.runtime_manifest._base import *  # noqa: F401, F403
from apps.runtime_manifest._enums import *  # noqa: F401, F403
from apps.runtime_manifest._models_basic import *  # noqa: F401, F403
from apps.runtime_manifest._models_admin import *  # noqa: F401, F403
from apps.runtime_manifest._errors import *  # noqa: F401, F403
from apps.runtime_manifest._errors import (  # noqa: F401  (underscore re-exports)
    RuntimeManifestBuildError,
    _manifest_error_details,
    _raise_manifest_integrity_error,
    _raise_on_duplicate_values,
)
from apps.runtime_manifest._models_manifest import *  # noqa: F401, F403
from apps.runtime_manifest._internal_helpers import *  # noqa: F401, F403
from apps.runtime_manifest._internal_helpers import (  # noqa: F401
    _build_artifact_reference,
    _build_runtime_manifest_error_details,
    _canonical_json,
    _detect_mojo_version,
    _deployment_mode,
    _enum_values,
    _format_runtime_manifest_build_error_message,
    _format_runtime_manifest_validation_path,
    _format_runtime_payload_build_error_message,
    _manifest_signing_secret,
    _raise_runtime_payload_build_error,
    _raw_runtime_dict_key,
    _raw_runtime_payload,
    _read_json,
    _runtime_deployment_mode_value,
    _sha256_bytes,
    _sha256_file,
    _try_runtime_deployment_mode,
    _validated_runtime_manifest_for_surface,
)
from apps.runtime_manifest._builders import *  # noqa: F401, F403
from apps.runtime_manifest._builders import (  # noqa: F401
    _build_benchmark_discovery_lane,
    _build_compiled_artifacts,
    _build_module_entries,
    _build_kernel_promotion_criteria,
    _build_signature,
    _build_policy_snapshot,
    _build_schema_snapshot,
)
from apps.runtime_manifest._public_api import *  # noqa: F401, F403

# Module-level constants — re-bind so the facade exposes the same
# `apps.runtime_manifest._MOJO_BINARY_PATH` that tests monkeypatch.
from apps.runtime_manifest._constants import (
    _ROOT,
    _PROOF_BUNDLE_PATH,
    _PARITY_ARTIFACT_PATH,
    _COMPILED_ARTIFACT_PATH,
    _MOJO_BINARY_PATH,
)
