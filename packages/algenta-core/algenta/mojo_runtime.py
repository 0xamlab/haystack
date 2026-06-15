from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from algenta.mojo_errors import (
    MojoExecutionError,
    MojoFunctionNotRegisteredError,
    MojoModuleNotRegisteredError,
    MojoRuntimeConfigurationError,
)


def _load_runtime_class():
    try:
        from apps.runtime.sdk import Runtime as RuntimeSDK
    except ImportError as exc:  # pragma: no cover - exercised in packaged environments
        raise MojoRuntimeConfigurationError(
            "compute_runtime_unavailable",
            "The local Mojo runtime SDK is unavailable. Use the full decision-engine "
            "workspace or install the runtime components before accessing Mojo libraries.",
        ) from exc
    return RuntimeSDK


def _load_runtime_inventory():
    try:
        from apps.runtime.mojo_inventory import discover_runtime_library_modules
    except ImportError as exc:  # pragma: no cover - exercised in packaged environments
        raise MojoRuntimeConfigurationError(
            "compute_runtime_unavailable",
            "The local Mojo runtime inventory is unavailable. Use the full decision-engine "
            "workspace or install the runtime components before accessing Mojo libraries.",
        ) from exc
    return lambda: discover_runtime_library_modules(executable_only=True)


@dataclass(frozen=True)
class LibraryDescriptor:
    name: str
    engine: str
    functions: tuple[str, ...]


def _validate_runtime_config(
    *,
    mode: str,
    api_key: str,
    base_url: str,
) -> None:
    if mode != "local":
        raise MojoRuntimeConfigurationError(
            "compute_runtime_unavailable",
            "Python MojoRuntime only supports the local Codna runtime in this rollout.",
            {"mode": mode},
        )


def _runtime_inventory_error(
    message: str,
    details: dict[str, Any],
) -> MojoRuntimeConfigurationError:
    return MojoRuntimeConfigurationError(
        "compute_runtime_unavailable",
        message,
        details,
    )


def _normalize_runtime_module_name(raw_name: Any) -> str:
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise _runtime_inventory_error(
            "The local Mojo runtime inventory returned a malformed module descriptor.",
            {"module": raw_name},
        )
    return raw_name.strip()


def _normalize_runtime_engine(module_name: str, raw_engine: Any) -> str:
    if not isinstance(raw_engine, str) or not raw_engine.strip():
        raise _runtime_inventory_error(
            f"The local Mojo runtime inventory returned a malformed engine for '{module_name}'.",
            {"module": module_name, "engine": raw_engine},
        )
    return raw_engine.strip()


def _normalize_runtime_functions(module_name: str, raw_functions: Any) -> tuple[str, ...]:
    if raw_functions is None:
        raw_functions = ()
    elif isinstance(raw_functions, str):
        raise _runtime_inventory_error(
            f"The local Mojo runtime inventory returned malformed functions for '{module_name}'.",
            {"module": module_name, "functions": raw_functions},
        )
    elif not isinstance(raw_functions, tuple):
        try:
            raw_functions = tuple(raw_functions)
        except TypeError as exc:
            raise _runtime_inventory_error(
                "The local Mojo runtime inventory returned malformed functions "
                f"for '{module_name}'.",
                {"module": module_name, "functions": raw_functions},
            ) from exc
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_function in raw_functions:
        function_name = getattr(raw_function, "name", raw_function)
        if not isinstance(function_name, str) or not function_name.strip():
            raise _runtime_inventory_error(
                "The local Mojo runtime inventory returned a malformed function "
                f"for '{module_name}'.",
                {"module": module_name, "function": function_name},
            )
        normalized_name = function_name.strip()
        if normalized_name in seen:
            raise _runtime_inventory_error(
                "The local Mojo runtime inventory returned duplicate functions "
                f"for '{module_name}'.",
                {"module": module_name, "function": normalized_name},
            )
        seen.add(normalized_name)
        normalized.append(normalized_name)
    if not normalized:
        raise _runtime_inventory_error(
            "The local Mojo runtime inventory exposed "
            f"'{module_name}' without executable functions.",
            {"module": module_name},
        )
    return tuple(sorted(normalized))


def _build_attribute_index(
    descriptors: dict[str, LibraryDescriptor],
    ordered_names: tuple[str, ...],
) -> dict[str, LibraryDescriptor]:
    attribute_index: dict[str, LibraryDescriptor] = {}
    alias_sources: dict[str, str] = {}
    for name in ordered_names:
        descriptor = descriptors[name]
        alias = name.replace(".", "_")
        if alias != name and alias in descriptors:
            # Flat alias collides with another module's canonical name.
            # Keep the flat-name module accessible via attribute; the dotted
            # module is still listed in the catalog under its full name.
            continue
        existing_name = alias_sources.get(alias)
        if existing_name is not None and existing_name != name:
            # Two different dotted paths collapse to the same alias.
            # Prefer the first-seen mapping; subsequent ones remain catalog-only.
            continue
        alias_sources[alias] = name
        attribute_index[alias] = descriptor
    return attribute_index


@lru_cache(maxsize=1)
def _cached_runtime_descriptors() -> tuple[LibraryDescriptor, ...]:
    descriptors: list[LibraryDescriptor] = []
    seen_modules: set[str] = set()
    for module in _load_runtime_inventory()():
        module_name = _normalize_runtime_module_name(getattr(module, "import_path", None))
        if module_name in seen_modules:
            raise _runtime_inventory_error(
                "The local Mojo runtime inventory returned duplicate modules.",
                {"module": module_name},
            )
        seen_modules.add(module_name)
        descriptors.append(
            LibraryDescriptor(
                name=module_name,
                engine=_normalize_runtime_engine(
                    module_name,
                    getattr(module, "engine", "mojo"),
                ),
                functions=_normalize_runtime_functions(
                    module_name,
                    getattr(module, "functions", ()),
                ),
            )
        )
    return tuple(descriptors)


class LibraryModuleProxy:
    def __init__(self, runtime: MojoRuntime, descriptor: LibraryDescriptor) -> None:
        self._runtime = runtime
        self._descriptor = descriptor
        self._callables: dict[str, Callable[..., Any]] = {}

    @property
    def name(self) -> str:
        return self._descriptor.name

    @property
    def functions(self) -> tuple[str, ...]:
        return self._descriptor.functions

    def __getattr__(self, function_name: str):
        cached = self._callables.get(function_name)
        if cached is not None:
            return cached
        if function_name not in self._descriptor.functions:
            raise MojoFunctionNotRegisteredError(
                "function_not_registered",
                f"Module '{self._descriptor.name}' does not expose '{function_name}'.",
                {"module": self._descriptor.name, "function": function_name},
            )

        def _call(*args: Any, **kwargs: Any) -> Any:
            if args and kwargs:
                raise TypeError("Provide either positional args or keyword args, not both.")
            payload: Any
            if kwargs:
                payload = kwargs
            elif len(args) == 1:
                payload = args[0]
            else:
                payload = list(args)
            result = self._runtime.execute(self._descriptor.name, function_name, payload)
            if not result.get("success", False):
                error_message = str(result.get("error", "Runtime execution failed."))
                error_code = "python_fallback_disabled"
                engine_used = result.get("engine_used")
                if engine_used != "python-fallback":
                    error_code = (
                        "compute_runtime_unavailable"
                        if engine_used in {None, "", "none"}
                        else "mojo_execution_failed"
                    )
                raise MojoExecutionError(
                    error_code,
                    error_message,
                    {
                        "module": self._descriptor.name,
                        "function": function_name,
                        "engine_used": engine_used,
                    },
                )
            return result.get("result")

        _call.__name__ = function_name
        _call.__doc__ = (
            f"Execute {self._descriptor.name}.{function_name} through the local Mojo runtime."
        )
        self._callables[function_name] = _call
        return _call


class LibraryCatalog:
    def __init__(self, runtime: MojoRuntime) -> None:
        self._runtime = runtime
        self._descriptors: dict[str, LibraryDescriptor] = {}
        self._module_names: tuple[str, ...] = ()
        self._module_list: tuple[LibraryDescriptor, ...] = ()
        self._attribute_index: dict[str, LibraryDescriptor] = {}
        self._module_proxies: dict[str, LibraryModuleProxy] = {}
        self._rebuild_descriptors()

    def _load_descriptors(self, *, refresh: bool = False) -> tuple[LibraryDescriptor, ...]:
        if refresh:
            _cached_runtime_descriptors.cache_clear()
        return _cached_runtime_descriptors()

    def _rebuild_descriptors(self, *, refresh: bool = False) -> None:
        runtime_descriptors = self._load_descriptors(refresh=refresh)
        descriptors = {descriptor.name: descriptor for descriptor in runtime_descriptors}
        ordered_names = tuple(sorted(descriptors))
        self._descriptors = descriptors
        self._module_names = ordered_names
        self._module_list = tuple(descriptors[name] for name in ordered_names)
        self._attribute_index = _build_attribute_index(descriptors, ordered_names)

    def refresh(self) -> LibraryCatalog:
        self._rebuild_descriptors(refresh=True)
        self._module_proxies.clear()
        return self

    def names(self) -> tuple[str, ...]:
        return self._module_names

    def __contains__(self, module_name: object) -> bool:
        return isinstance(module_name, str) and module_name in self._descriptors

    def __iter__(self):
        return iter(self._module_list)

    def list_modules(self) -> tuple[LibraryDescriptor, ...]:
        return self._module_list

    def list_functions(self, module_name: str) -> tuple[str, ...]:
        return self[module_name].functions

    def module(self, module_name: str) -> LibraryModuleProxy:
        return self[module_name]

    def _resolve_descriptor(self, module_name: str) -> LibraryDescriptor:
        descriptor = self._descriptors.get(module_name)
        if descriptor is not None:
            return descriptor
        raise MojoModuleNotRegisteredError(
            "module_not_registered",
            f"Unknown Mojo library '{module_name}'.",
            {"module": module_name},
        )

    def _module_proxy(self, descriptor: LibraryDescriptor) -> LibraryModuleProxy:
        cached = self._module_proxies.get(descriptor.name)
        if cached is not None:
            return cached
        proxy = LibraryModuleProxy(self._runtime, descriptor)
        self._module_proxies[descriptor.name] = proxy
        return proxy

    def __getitem__(self, module_name: str) -> LibraryModuleProxy:
        return self._module_proxy(self._resolve_descriptor(module_name))

    def __getattr__(self, attribute: str) -> LibraryModuleProxy:
        descriptor = self._descriptors.get(attribute)
        if descriptor is None:
            descriptor = self._attribute_index.get(attribute)
        if descriptor is not None:
            return self._module_proxy(descriptor)
        raise MojoModuleNotRegisteredError(
            "module_not_registered",
            f"Unknown Mojo library '{attribute}'.",
            {"module": attribute},
        )


class MojoRuntime:
    """Thin package-level facade over the local decision-engine runtime SDK."""

    def __init__(
        self,
        *,
        mode: str = "local",
        api_key: str = "",
        timeout: float = 30.0,
        auto_start_daemon: bool = True,
        base_url: str = "",
    ) -> None:
        _validate_runtime_config(
            mode=mode,
            api_key=api_key,
            base_url=base_url,
        )
        self._runtime_config = {
            "mode": mode,
            "api_key": api_key,
            "timeout": timeout,
            "auto_start_daemon": auto_start_daemon,
            "base_url": base_url,
        }
        self._runtime = None
        self._catalog: LibraryCatalog | None = None

    def _ensure_runtime(self):
        if self._runtime is None:
            runtime_class = _load_runtime_class()
            self._runtime = runtime_class(**self._runtime_config)
        return self._runtime

    def execute(self, module: str, function: str, args: Any = None) -> dict[str, Any]:
        return self._ensure_runtime().execute(module, function, args)

    def health(self) -> dict[str, Any]:
        return self._ensure_runtime().health()

    def list_modules(self) -> list[dict[str, Any]]:
        return [
            {
                "name": descriptor.name,
                "engine": descriptor.engine,
                "functions": list(descriptor.functions),
            }
            for descriptor in self.libraries().list_modules()
        ]

    def list_functions(self, module_name: str) -> tuple[str, ...]:
        return self.libraries().list_functions(module_name)

    def libraries(self) -> LibraryCatalog:
        if self._catalog is None:
            self._catalog = LibraryCatalog(self)
        return self._catalog


def libraries(**kwargs: Any) -> LibraryCatalog:
    """Return the current executable Mojo library catalog."""
    return MojoRuntime(**kwargs).libraries()
