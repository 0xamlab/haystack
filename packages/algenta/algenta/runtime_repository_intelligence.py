from __future__ import annotations

import os
from importlib import import_module
from typing import Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError

_REPOSITORY_BACKEND_METHODS = (
    "get_repository_intelligence_capabilities",
    "create_repository_snapshot",
    "get_repository_snapshot",
    "triage_repository",
    "create_repository_decision_plan",
    "query_repository_graph",
    "simulate_repository",
    "apply_repository",
)
_REPOSITORY_BACKEND_ENV = "ALGENTA_RUNTIME_REPOSITORY_INTELLIGENCE_BACKEND"


def register_repository_intelligence_backend(runtime: Any, backend: Any) -> None:
    runtime._local_repository_intelligence_backend = _validate_backend_contract(backend)


def resolve_repository_intelligence_backend_spec(spec: str) -> Any:
    if not isinstance(spec, str) or ":" not in spec:
        raise RuntimeConfigurationError(
            "invalid_repository_intelligence_backend_spec",
            (
                "Repository intelligence backend specs must use the "
                "'module.submodule:attribute' format."
            ),
            {"spec": spec},
        )
    module_name, attribute_name = spec.split(":", 1)
    if not module_name.strip() or not attribute_name.strip():
        raise RuntimeConfigurationError(
            "invalid_repository_intelligence_backend_spec",
            (
                "Repository intelligence backend specs must use the "
                "'module.submodule:attribute' format."
            ),
            {"spec": spec},
        )
    try:
        module = import_module(module_name)
    except Exception as exc:
        raise RuntimeConfigurationError(
            "repository_intelligence_backend_import_failed",
            "Unable to import the configured repository intelligence backend module.",
            {"spec": spec, "module": module_name},
        ) from exc
    try:
        candidate = getattr(module, attribute_name)
    except AttributeError as exc:
        raise RuntimeConfigurationError(
            "repository_intelligence_backend_attribute_missing",
            "The configured repository intelligence backend attribute was not found.",
            {"spec": spec, "module": module_name, "attribute": attribute_name},
        ) from exc
    backend = candidate() if callable(candidate) else candidate
    return _validate_backend_contract(backend)


def require_repository_intelligence_backend(runtime: Any, method_name: str) -> Any:
    backend = getattr(runtime, "_local_repository_intelligence_backend", None)
    if backend is None:
        spec = _configured_backend_spec(runtime)
        if spec is not None:
            backend = resolve_repository_intelligence_backend_spec(spec)
            runtime._local_repository_intelligence_backend = backend
    if backend is None:
        raise RuntimeConfigurationError(
            "local_repository_intelligence_backend_required",
            (
                f"{method_name}() requires a registered repository intelligence "
                "backend for Runtime(mode='local')."
            ),
            {"method_name": method_name, "env_var": _REPOSITORY_BACKEND_ENV},
        )
    backend_method = getattr(backend, method_name, None)
    if not callable(backend_method):
        raise RuntimeConfigurationError(
            "repository_intelligence_backend_method_missing",
            (
                "The registered repository intelligence backend is missing the "
                f"required method {method_name}()."
            ),
            {"method_name": method_name},
        )
    return backend


def _configured_backend_spec(runtime: Any) -> str | None:
    configured = getattr(runtime, "_local_repository_intelligence_backend_spec", None)
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    env_spec = os.environ.get(_REPOSITORY_BACKEND_ENV)
    if isinstance(env_spec, str) and env_spec.strip():
        return env_spec.strip()
    return None


def _validate_backend_contract(backend: Any) -> Any:
    missing_methods = [
        method_name
        for method_name in _REPOSITORY_BACKEND_METHODS
        if not callable(getattr(backend, method_name, None))
    ]
    if missing_methods:
        raise RuntimeValidationError(
            "invalid_repository_intelligence_backend",
            (
                "register_repository_intelligence_backend() requires a backend "
                "implementing the full repository intelligence contract."
            ),
            {"missing_methods": missing_methods},
        )
    return backend
