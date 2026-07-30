from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any

from algenta.mojo_errors import (
    MojoExecutionError,
    MojoFunctionNotRegisteredError,
    MojoModuleNotRegisteredError,
    MojoRuntimeConfigurationError,
)


def _load_runtime_class():
    return _BundledRuntime


def _load_runtime_inventory():
    from algenta.native import worker
    from algenta.runtime_library_contract import filtered_runtime_modules

    return lambda: filtered_runtime_modules(worker.runtime_module_filter())


class _BundledRuntime:
    def __init__(
        self,
        *,
        mode: str,
        api_key: str,
        timeout: float,
        auto_start_daemon: bool,
        base_url: str,
    ) -> None:
        del api_key, auto_start_daemon, base_url
        if mode != "local":
            raise ValueError("The bundled runtime supports local mode only")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self._timeout = timeout

    @staticmethod
    def _require_verified_runtime() -> bool:
        from algenta.native.loader import _fallback_mode

        return _fallback_mode() != "allow"

    def execute(self, module: str, function: str, args: Any = None) -> dict[str, Any]:
        from algenta.native import worker
        from algenta.runtime_library_contract import RuntimeLibraryContractError
        from algenta.runtime_library_transport import build_worker_request, parse_worker_response

        started = perf_counter()
        try:
            module_spec, function_spec, request = build_worker_request(module, function, args)
            response = worker.execute(
                request,
                timeout=self._timeout,
                require_verified=self._require_verified_runtime(),
            )
            result = parse_worker_response(module_spec, function_spec, response)
        except RuntimeLibraryContractError as exc:
            return {
                "result": None,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "engine_used": "none",
                "success": False,
                "error": str(exc),
                "error_code": exc.code,
            }
        except worker.NativeWorkerUnavailable as exc:
            return {
                "result": None,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "engine_used": "none",
                "success": False,
                "error": str(exc),
                "error_code": "compute_runtime_unavailable",
            }
        return {
            "result": result,
            "latency_ms": round((perf_counter() - started) * 1000, 3),
            "engine_used": "mojo",
            "success": True,
            "error": "",
        }

    def execute_batch(
        self,
        items: list[dict[str, Any]],
        *,
        partial_ok: bool = True,
    ) -> dict[str, Any]:
        from algenta.batch import execute_batch as _execute_batch

        return _execute_batch(
            items,
            timeout=self._timeout,
            partial_ok=partial_ok,
            require_verified=self._require_verified_runtime(),
        )

    def query(self, plan: Any, *, routing_module: str = "stats") -> Any:
        from algenta.query import run_query

        return run_query(
            plan,
            routing_module=routing_module,
            timeout=self._timeout,
            require_verified=self._require_verified_runtime(),
        )

    def open_dataset(self, value: Any, *, name: str = "", routing_module: str) -> str:
        from algenta.session import open_dataset

        return open_dataset(
            value,
            name=name,
            routing_module=routing_module,
            timeout=self._timeout,
            require_verified=self._require_verified_runtime(),
        )

    def close_dataset(self, handle: str, *, routing_module: str) -> bool:
        from algenta.session import close_dataset

        return close_dataset(
            handle,
            routing_module=routing_module,
            timeout=self._timeout,
            require_verified=self._require_verified_runtime(),
        )

    def list_datasets(self, *, routing_module: str) -> dict[str, Any]:
        from algenta.session import list_datasets

        return list_datasets(
            routing_module=routing_module,
            timeout=self._timeout,
            require_verified=self._require_verified_runtime(),
        )

    def stream(self, handle: str, *, routing_module: str, chunk_rows: int | None = None):
        from algenta.session import stream_chunks

        return stream_chunks(
            handle,
            routing_module=routing_module,
            timeout=self._timeout,
            require_verified=self._require_verified_runtime(),
            chunk_rows=chunk_rows,
        )

    def run_pipeline(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        from algenta.native import worker
        from algenta.pipeline import PipelineShardError

        if not nodes:
            return {
                "result": None,
                "results": [],
                "lineage": [],
                "nodes": 0,
                "ok": 0,
                "failed": 0,
                "success": True,
                "error": "",
            }

        require_verified = self._require_verified_runtime()
        # A worker only holds its own shard's modules, so the whole DAG must route
        # to one worker. Refuse rather than half-execute it.
        routes: dict[str, str] = {}
        for node in nodes:
            module = str(node.get("module", ""))
            if module in routes:
                continue
            routes[module] = str(
                worker.require_worker(
                    module_name=module, require_verified=require_verified
                ).path
            )
        distinct = sorted(set(routes.values()))
        if len(distinct) > 1:
            grouped: dict[str, list[str]] = {}
            for module, path in routes.items():
                grouped.setdefault(path, []).append(module)
            detail = "; ".join(
                f"{path.rsplit('/', 1)[-1]}: {', '.join(sorted(mods))}"
                for path, mods in sorted(grouped.items())
            )
            raise PipelineShardError(
                "Pipeline nodes span more than one runtime shard, so they cannot "
                f"execute in a single frame ({detail}). Split the plan per shard, "
                "or install a runtime filtered to these modules."
            )

        frame = {
            "type": "pipeline_execute",
            "engine_type": "pipeline_execute",
            "nodes": nodes,
        }
        started = perf_counter()
        try:
            envelope = worker.execute(
                frame,
                timeout=self._timeout,
                require_verified=require_verified,
                module_name=str(nodes[0].get("module", "")),
            )
        except worker.NativeWorkerUnavailable as exc:
            return {
                "result": None,
                "results": [],
                "lineage": [],
                "nodes": len(nodes),
                "ok": 0,
                "failed": len(nodes),
                "success": False,
                "error": str(exc),
                "error_code": "compute_runtime_unavailable",
                "latency_ms": round((perf_counter() - started) * 1000, 3),
            }

        envelope = dict(envelope)
        envelope["latency_ms"] = round((perf_counter() - started) * 1000, 3)
        envelope["success"] = not envelope.get("error_code")
        return envelope

    def health(self) -> dict[str, Any]:
        from algenta.native import worker

        try:
            worker.ensure_ready(
                timeout=self._timeout,
                require_verified=self._require_verified_runtime(),
            )
        except worker.NativeWorkerUnavailable as exc:
            return {
                "status": "error",
                "mode": "bundled-worker",
                "fallback": "denied",
                "error": str(exc),
            }
        return {
            "status": "ok",
            "mode": "bundled-worker",
            "fallback": "denied",
            "tcp_listeners": [],
        }


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
            "Python MojoRuntime only supports the local Algenta runtime in this rollout.",
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
                error_code = str(result.get("error_code") or "mojo_execution_failed")
                engine_used = result.get("engine_used")
                if engine_used == "python-fallback":
                    error_code = "python_fallback_disabled"
                elif not result.get("error_code"):
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
    """In-process facade over the automatically installed bundled runtime."""

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

    def execute_batch(
        self,
        items: list[dict[str, Any]],
        *,
        partial_ok: bool = True,
    ) -> dict[str, Any]:
        """Execute many kernel calls in as few frames as shard routing allows.

        Each entry is `{"module": ..., "function": ..., "args": ...}`. Results come
        back in the same order, each shaped like a single `execute()` envelope, so
        one failing item never sinks its neighbours. `partial_ok=False` stops a
        shard group at its first failure.
        """
        return self._ensure_runtime().execute_batch(items, partial_ok=partial_ok)

    def pipeline(self) -> Any:
        """Start a chained plan whose intermediates never leave the worker.

        Nodes run in order; `Ref(i)` / `PREV` in a node's args are replaced by an
        earlier node's output inside Mojo, so an N-step chain costs one frame.
        """
        from algenta.pipeline import Pipeline

        return Pipeline(self)

    def run_pipeline(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute an already-built node list. `pipeline()` is the usual entry."""
        return self._ensure_runtime().run_pipeline(nodes)

    def query(self, plan: Any, *, routing_module: str = "stats") -> Any:
        """Run a columnar query plan in one dispatch, entirely on this device.

        Build the plan with `algenta.Query` / `col`. Every operator is a compiled
        Mojo kernel; the plan crosses the boundary once rather than per operator, and
        the returned `plan_hash` identifies the computation rather than the data.

        Raises `algenta.QueryError` if the plan is rejected or an operator fails — a
        failed plan returns no rows, because an empty result would be
        indistinguishable from a complete answer.
        """
        return self._ensure_runtime().query(plan, routing_module=routing_module)

    def open_dataset(self, value: Any, *, name: str = "", routing_module: str) -> str:
        """Make `value` resident so later calls reference it by handle.

        Reference it from a batch item or pipeline node as `"@<handle>"`; per-call
        payload then stays O(1) in rows. `routing_module` picks the shard, so it
        must be a module the later calls also use.
        """
        return self._ensure_runtime().open_dataset(
            value, name=name, routing_module=routing_module
        )

    def close_dataset(self, handle: str, *, routing_module: str) -> bool:
        """Release a resident dataset. Handles are never reissued."""
        return self._ensure_runtime().close_dataset(handle, routing_module=routing_module)

    def list_datasets(self, *, routing_module: str) -> dict[str, Any]:
        """Resident handles and their sizes for one shard."""
        return self._ensure_runtime().list_datasets(routing_module=routing_module)

    def stream(self, handle: str, *, routing_module: str, chunk_rows: int | None = None):
        """Iterate a resident dataset in chunks, pulling only what you consume.

        A generator: breaking early leaves the remainder unencoded, and the cursor
        is closed on exit either way.
        """
        return self._ensure_runtime().stream(
            handle, routing_module=routing_module, chunk_rows=chunk_rows
        )

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
