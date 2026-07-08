from __future__ import annotations

from importlib import import_module

from algenta.mojo_errors import (
    MojoExecutionError,
    MojoFunctionNotRegisteredError,
    MojoModuleNotRegisteredError,
    MojoRuntimeConfigurationError,
    MojoRuntimeError,
)

_LAZY_EXPORTS = {
    "LibraryDescriptor": ("algenta.mojo_runtime", "LibraryDescriptor"),
    "LibraryModuleProxy": ("algenta.mojo_runtime", "LibraryModuleProxy"),
    "LibraryCatalog": ("algenta.mojo_runtime", "LibraryCatalog"),
    "MojoRuntime": ("algenta.mojo_runtime", "MojoRuntime"),
    "libraries": ("algenta.mojo_entrypoints", "libraries"),
    "_load_runtime_class": ("algenta.mojo_runtime", "_load_runtime_class"),
    "_load_runtime_inventory": ("algenta.mojo_runtime", "_load_runtime_inventory"),
    "_cached_runtime_descriptors": ("algenta.mojo_runtime", "_cached_runtime_descriptors"),
}

__all__ = [
    "MojoRuntimeError",
    "MojoRuntimeConfigurationError",
    "MojoModuleNotRegisteredError",
    "MojoFunctionNotRegisteredError",
    "MojoExecutionError",
    *list(_LAZY_EXPORTS),
]


def __getattr__(name: str):
    export = _LAZY_EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module 'algenta.mojo' has no attribute '{name}'")
    module_name, attribute_name = export
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
