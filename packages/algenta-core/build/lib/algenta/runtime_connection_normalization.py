from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "normalize_api_source_payload": (
        "algenta.runtime_connection_descriptors",
        "normalize_api_source_payload",
    ),
    "normalize_local_runtime_source": (
        "algenta.runtime_connection_descriptors",
        "normalize_local_runtime_source",
    ),
    "normalize_runtime_connection": (
        "algenta.runtime_connection_descriptors",
        "normalize_runtime_connection",
    ),
    "runtime_api_source_name": ("algenta.runtime_source_naming", "runtime_api_source_name"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(
            f"module 'algenta.runtime_connection_normalization' has no attribute {name!r}"
        )
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
