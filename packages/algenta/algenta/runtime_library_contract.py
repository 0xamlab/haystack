"""Strict loader for the sanitized runtime-library contract shipped in the wheel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any


class RuntimeLibraryContractError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class RuntimeParamSpec:
    name: str
    typ: str
    has_default: bool
    is_mut: bool


@dataclass(frozen=True)
class RuntimeCountRelation:
    """`product(factors) + plus` elements are required in each list named by `bounds`.

    One factor is a plain element count; two are the dimensions of a flat row-major matrix.
    `plus` is a constant added to the product, which is also how an INDEX parameter is
    expressed (`plus=1`). `scope` is `length` for the list itself or `element_length` for
    every element list of a nested list. `role` (`count` or `index`) only shapes the message.
    """

    factors: tuple[str, ...]
    bounds: tuple[str, ...]
    plus: int = 0
    scope: str = "length"
    role: str = "count"


@dataclass(frozen=True)
class RuntimeFunctionSpec:
    name: str
    params: tuple[RuntimeParamSpec, ...]
    return_type: str
    # Empty for every function whose count relations have not been published. An older
    # contract has no `count_relations` key at all and loads to the same empty tuple, so a
    # wheel built before this field existed keeps working unchanged.
    count_relations: tuple[RuntimeCountRelation, ...] = ()


@dataclass(frozen=True)
class RuntimeStructFieldSpec:
    name: str
    typ: str


@dataclass(frozen=True)
class RuntimeStructSpec:
    name: str
    fields: tuple[RuntimeStructFieldSpec, ...]


@dataclass(frozen=True)
class RuntimeLibraryModule:
    import_path: str
    engine: str
    functions: tuple[RuntimeFunctionSpec, ...]
    structs: tuple[RuntimeStructSpec, ...]


@dataclass(frozen=True)
class EngineKernelSpec:
    """One published engine kernel — the pointer-based CUDA/Metal kernels the engine races.

    These are deliberately NOT in `modules`: their arguments are device pointers, which do
    not cross a JSON frame, so the runtime contract publishes them as a capability
    declaration (what ships, per backend and model family) instead of faking callability.
    `name` is the stable, readable public entry name; `symbol` is the private Mojo symbol it
    maps to."""

    name: str
    symbol: str
    module: str
    backend: str
    families: tuple[str, ...]
    role: str
    prefix: str | None = None


@dataclass(frozen=True)
class EngineKernelModule:
    """A kernel module's published record: backend plus the evidence pointers its own
    `@capability-module` block declares (golden vectors, benchmark)."""

    name: str
    path: str
    backend: str
    kernel_count: int
    golden_vectors: str | None = None
    benchmark: str | None = None


@dataclass(frozen=True)
class EngineKernelInventory:
    modules: tuple[EngineKernelModule, ...]
    kernels: tuple[EngineKernelSpec, ...]

    @property
    def backends(self) -> tuple[str, ...]:
        return tuple(sorted({kernel.backend for kernel in self.kernels}))

    def for_backend(self, backend: str) -> tuple[EngineKernelSpec, ...]:
        return tuple(kernel for kernel in self.kernels if kernel.backend == backend)

    def for_family(self, family: str) -> tuple[EngineKernelSpec, ...]:
        return tuple(kernel for kernel in self.kernels if family in kernel.families)


def _require_object(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeLibraryContractError("invalid_runtime_contract", f"{context} must be an object")
    return value


def _require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise RuntimeLibraryContractError("invalid_runtime_contract", f"{context} must be a list")
    return value


def _require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} must be a non-empty string"
        )
    return value.strip()


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise RuntimeLibraryContractError("invalid_runtime_contract", f"{context} must be boolean")
    return value


def _parse_param(value: Any, context: str) -> RuntimeParamSpec:
    payload = _require_object(value, context)
    return RuntimeParamSpec(
        name=_require_string(payload.get("name"), f"{context}.name"),
        typ=_require_string(payload.get("type"), f"{context}.type"),
        has_default=_require_bool(payload.get("has_default"), f"{context}.has_default"),
        is_mut=_require_bool(payload.get("is_mut"), f"{context}.is_mut"),
    )


def _parse_count_relation(
    value: Any, context: str, parameter_names: set[str]
) -> RuntimeCountRelation:
    payload = _require_object(value, context)
    factors = tuple(
        _require_string(item, f"{context}.factors[{index}]")
        for index, item in enumerate(_require_list(payload.get("factors"), f"{context}.factors"))
    )
    bounds = tuple(
        _require_string(item, f"{context}.bounds[{index}]")
        for index, item in enumerate(_require_list(payload.get("bounds"), f"{context}.bounds"))
    )
    if not factors or not bounds:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} must name at least one factor and one bound"
        )
    # A relation naming a parameter the signature does not have could never be evaluated, so
    # it would silently disable itself. Refuse the contract instead: a guard that quietly
    # does nothing is the failure mode this whole mechanism exists to remove.
    unknown = sorted((set(factors) | set(bounds)) - parameter_names)
    if unknown:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract",
            f"{context} names parameters absent from the signature: {', '.join(unknown)}",
        )
    plus = payload.get("plus", 0)
    if isinstance(plus, bool) or not isinstance(plus, int) or plus < 0:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context}.plus must be a non-negative integer"
        )
    scope = _require_string(payload.get("scope", "length"), f"{context}.scope")
    if scope not in {"length", "element_length"}:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context}.scope must be length or element_length"
        )
    role = _require_string(payload.get("role", "count"), f"{context}.role")
    if role not in {"count", "index"}:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context}.role must be count or index"
        )
    return RuntimeCountRelation(
        factors=factors, bounds=bounds, plus=plus, scope=scope, role=role
    )


def _parse_function(value: Any, context: str) -> RuntimeFunctionSpec:
    payload = _require_object(value, context)
    params = tuple(
        _parse_param(item, f"{context}.params[{index}]")
        for index, item in enumerate(_require_list(payload.get("params"), f"{context}.params"))
    )
    if len({param.name for param in params}) != len(params):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} contains duplicate parameter names"
        )
    parameter_names = {param.name for param in params}
    raw_relations = payload.get("count_relations")
    count_relations = (
        tuple(
            _parse_count_relation(item, f"{context}.count_relations[{index}]", parameter_names)
            for index, item in enumerate(
                _require_list(raw_relations, f"{context}.count_relations")
            )
        )
        if raw_relations is not None
        else ()
    )
    return RuntimeFunctionSpec(
        name=_require_string(payload.get("name"), f"{context}.name"),
        params=params,
        return_type=_require_string(payload.get("return_type"), f"{context}.return_type"),
        count_relations=count_relations,
    )


def _parse_struct(value: Any, context: str) -> RuntimeStructSpec:
    payload = _require_object(value, context)
    fields = tuple(
        RuntimeStructFieldSpec(
            name=_require_string(field.get("name"), f"{context}.fields[{index}].name"),
            typ=_require_string(field.get("type"), f"{context}.fields[{index}].type"),
        )
        for index, raw_field in enumerate(
            _require_list(payload.get("fields"), f"{context}.fields")
        )
        for field in (_require_object(raw_field, f"{context}.fields[{index}]"),)
    )
    if len({field.name for field in fields}) != len(fields):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} contains duplicate field names"
        )
    return RuntimeStructSpec(
        name=_require_string(payload.get("name"), f"{context}.name"),
        fields=fields,
    )


def _parse_module(value: Any, context: str) -> RuntimeLibraryModule:
    payload = _require_object(value, context)
    functions = tuple(
        _parse_function(item, f"{context}.functions[{index}]")
        for index, item in enumerate(
            _require_list(payload.get("functions"), f"{context}.functions")
        )
    )
    structs = tuple(
        _parse_struct(item, f"{context}.structs[{index}]")
        for index, item in enumerate(_require_list(payload.get("structs"), f"{context}.structs"))
    )
    if not functions or len({function.name for function in functions}) != len(functions):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} must contain unique functions"
        )
    if len({struct.name for struct in structs}) != len(structs):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} contains duplicate structs"
        )
    return RuntimeLibraryModule(
        import_path=_require_string(payload.get("name"), f"{context}.name"),
        engine=_require_string(payload.get("engine"), f"{context}.engine"),
        functions=functions,
        structs=structs,
    )


@lru_cache(maxsize=1)
def runtime_modules() -> tuple[RuntimeLibraryModule, ...]:
    contract_path = resources.files("algenta").joinpath("runtime_library_contract.json")
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "The bundled runtime contract is unreadable"
        ) from exc
    root = _require_object(payload, "runtime contract")
    if root.get("schema_version") != 1:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "Unsupported runtime contract schema version"
        )
    modules = tuple(
        _parse_module(item, f"modules[{index}]")
        for index, item in enumerate(_require_list(root.get("modules"), "modules"))
    )
    if len({module.import_path for module in modules}) != len(modules):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "Runtime contract contains duplicate modules"
        )
    if root.get("module_count") != len(modules):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "Runtime contract module count does not match payload"
        )
    function_count = sum(len(module.functions) for module in modules)
    if root.get("function_count") != function_count:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "Runtime contract function count does not match payload"
        )
    return modules


def filtered_runtime_modules(module_filter: tuple[str, ...] | None) -> tuple[RuntimeLibraryModule, ...]:
    modules = runtime_modules()
    if not module_filter:
        return modules
    allowed = frozenset(module_filter)
    return tuple(module for module in modules if module.import_path in allowed)


def find_runtime_function(
    module_name: str,
    function_name: str,
) -> tuple[RuntimeLibraryModule, RuntimeFunctionSpec]:
    module = next((item for item in runtime_modules() if item.import_path == module_name), None)
    if module is None:
        raise RuntimeLibraryContractError(
            "module_not_registered",
            f"Unknown runtime library {module_name!r}",
            {"module": module_name},
        )
    function = next((item for item in module.functions if item.name == function_name), None)
    if function is None:
        raise RuntimeLibraryContractError(
            "function_not_registered",
            f"Runtime library {module_name!r} does not expose {function_name!r}",
            {"module": module_name, "function": function_name},
        )
    return module, function


def _optional_string(payload: dict[str, Any], key: str, context: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    return _require_string(value, f"{context}.{key}")


def _parse_engine_kernel_module(value: Any, context: str) -> EngineKernelModule:
    payload = _require_object(value, context)
    kernel_count = payload.get("kernel_count")
    if isinstance(kernel_count, bool) or not isinstance(kernel_count, int) or kernel_count < 0:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context}.kernel_count must be a non-negative integer"
        )
    return EngineKernelModule(
        name=_require_string(payload.get("name"), f"{context}.name"),
        path=_require_string(payload.get("path"), f"{context}.path"),
        backend=_require_string(payload.get("backend"), f"{context}.backend"),
        kernel_count=kernel_count,
        golden_vectors=_optional_string(payload, "golden_vectors", context),
        benchmark=_optional_string(payload, "benchmark", context),
    )


def _parse_engine_kernel(value: Any, context: str) -> EngineKernelSpec:
    payload = _require_object(value, context)
    families = tuple(
        _require_string(item, f"{context}.families[{index}]")
        for index, item in enumerate(
            _require_list(payload.get("families"), f"{context}.families")
        )
    )
    if not families:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", f"{context} must name at least one family"
        )
    prefix = payload.get("prefix")
    return EngineKernelSpec(
        name=_require_string(payload.get("name"), f"{context}.name"),
        symbol=_require_string(payload.get("symbol"), f"{context}.symbol"),
        module=_require_string(payload.get("module"), f"{context}.module"),
        backend=_require_string(payload.get("backend"), f"{context}.backend"),
        families=families,
        role=_require_string(payload.get("role"), f"{context}.role"),
        prefix=_require_string(prefix, f"{context}.prefix") if prefix is not None else None,
    )


def _load_contract_root() -> dict[str, Any]:
    contract_path = resources.files("algenta").joinpath("runtime_library_contract.json")
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "The bundled runtime contract is unreadable"
        ) from exc
    return _require_object(payload, "runtime contract")


@lru_cache(maxsize=1)
def engine_kernel_inventory() -> EngineKernelInventory:
    """The published engine-kernel inventory shipped in the runtime contract.

    The pointer-based CUDA/Metal kernels are not JSON-callable, so they are NOT in
    `runtime_modules()`; this is the surface that declares them instead — what ships, per
    backend and per model family. A contract predating the `engine_kernels` section loads
    as an EMPTY inventory: absence means "not published", never an error (the same
    convention `count_relations` uses).
    """
    root = _load_contract_root()
    raw = root.get("engine_kernels")
    if raw is None:
        return EngineKernelInventory(modules=(), kernels=())
    section = _require_object(raw, "engine_kernels")
    if section.get("schema") != 1:
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "Unsupported engine_kernels schema version"
        )
    modules = tuple(
        _parse_engine_kernel_module(item, f"engine_kernels.modules[{index}]")
        for index, item in enumerate(
            _require_list(section.get("modules"), "engine_kernels.modules")
        )
    )
    kernels = tuple(
        _parse_engine_kernel(item, f"engine_kernels.kernels[{index}]")
        for index, item in enumerate(
            _require_list(section.get("kernels"), "engine_kernels.kernels")
        )
    )
    if len({module.name for module in modules}) != len(modules):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "engine_kernels contains duplicate modules"
        )
    if len({(kernel.module, kernel.name) for kernel in kernels}) != len(kernels):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "engine_kernels contains duplicate kernels"
        )
    if section.get("module_count") != len(modules):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "engine_kernels module count does not match payload"
        )
    if section.get("kernel_count") != len(kernels):
        raise RuntimeLibraryContractError(
            "invalid_runtime_contract", "engine_kernels kernel count does not match payload"
        )
    by_module = {module.name: module for module in modules}
    kernels_per_module: dict[str, int] = {}
    for kernel in kernels:
        owner = by_module.get(kernel.module)
        if owner is None:
            raise RuntimeLibraryContractError(
                "invalid_runtime_contract",
                f"engine_kernels kernel {kernel.module}.{kernel.name} names a module "
                "absent from engine_kernels.modules",
            )
        if owner.backend != kernel.backend:
            raise RuntimeLibraryContractError(
                "invalid_runtime_contract",
                f"engine_kernels kernel {kernel.module}.{kernel.name} declares backend "
                f"{kernel.backend!r} but its module declares {owner.backend!r}",
            )
        kernels_per_module[kernel.module] = kernels_per_module.get(kernel.module, 0) + 1
    for module in modules:
        if module.kernel_count != kernels_per_module.get(module.name, 0):
            raise RuntimeLibraryContractError(
                "invalid_runtime_contract",
                f"engine_kernels module {module.name!r} declares kernel_count "
                f"{module.kernel_count} but lists {kernels_per_module.get(module.name, 0)}",
            )
    return EngineKernelInventory(modules=modules, kernels=kernels)


def engine_kernels(
    *,
    backend: str | None = None,
    family: str | None = None,
    role: str | None = None,
) -> tuple[EngineKernelSpec, ...]:
    """Query the shipped engine kernels. Filters compose (AND); no filter returns all.

    Example: `engine_kernels(backend="metal")` lists every Metal kernel that ships;
    `engine_kernels(backend="cuda", family="gemma3")` lists the Gemma 3 CUDA lane.
    """
    selected = engine_kernel_inventory().kernels
    if backend is not None:
        selected = tuple(kernel for kernel in selected if kernel.backend == backend)
    if family is not None:
        selected = tuple(kernel for kernel in selected if family in kernel.families)
    if role is not None:
        selected = tuple(kernel for kernel in selected if kernel.role == role)
    return selected


def engine_kernel_backends() -> tuple[str, ...]:
    """The backends with at least one shipped kernel, sorted."""
    return engine_kernel_inventory().backends
