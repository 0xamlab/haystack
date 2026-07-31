"""Discovery of the Mojo kernel tree: signatures, structs, and declared capabilities.

`RuntimeFunctionSpec` / `RuntimeStructSpec` describe what a kernel's SIGNATURE says.
`RuntimeCapabilitySpec` describes what a signature CANNOT say -- determinism, state,
complexity, and above all which caller-supplied `Int` is an element count and which list
it bounds. The block grammar, the reason it exists (an uncatchable process abort) and the
argument checker all live in `apps.runtime.mojo_capability_manifest`; read that module's
docstring before writing or changing a block.

The two parses are deliberately separate passes over the same files: the capability parse
must not be able to change existing signature/struct output, and the on-disk
runtime-library cache (schema version 8) keeps its key and payload untouched. Capability
discovery has no on-disk cache -- a single `"@capability" in text` test makes a full-tree
scan roughly a fifth of the signature parse it would otherwise share.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from apps.runtime.mojo_capability_manifest import (
    CapabilityIssue,
    CapabilityParse,
    RuntimeCapabilitySpec,
    RuntimeCountRelation,
    check_count_relations,
    parse_capability_blocks,
)

__all__ = [
    "CapabilityIssue",
    "CapabilityParse",
    "MojoInventoryReport",
    "RuntimeCapabilityManifest",
    "RuntimeCapabilitySpec",
    "RuntimeCountRelation",
    "RuntimeFunctionSpec",
    "RuntimeLibraryModule",
    "RuntimeModuleCapabilities",
    "RuntimeParamSpec",
    "RuntimeStructSpec",
    "build_capability_manifest",
    "build_inventory_report",
    "check_count_relations",
    "discover_runtime_library_modules",
    "discover_source_modules",
    "is_runtime_executable_function",
    "parse_runtime_capability_specs",
    "parse_runtime_struct_specs",
]


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENGINE_DIR = _PROJECT_ROOT / "mojo" / "engine"
DEFAULT_TEST_ALL_LIBRARIES = _PROJECT_ROOT / "mojo" / "tests" / "test_all_libraries.mojo"
DEFAULT_BENCHMARK_RESULTS_DIR = _PROJECT_ROOT / "benchmarks" / "results"
DEFAULT_BENCHMARK_MOJO_DIR = _PROJECT_ROOT / "benchmarks" / "mojo_benchmarks"
DEFAULT_RUNTIME_LIBRARY_CACHE = (
    _PROJECT_ROOT / ".cache" / "algenta" / "runtime_library_inventory.json"
)
# Bump this whenever the PARSE changes shape, not only when the cached record's fields do.
# The cache fingerprint is built from source mtimes alone, so a parser fix is invisible to it:
# with a warm cache the old parse is replayed and the fix silently does nothing. That is how
# the nested-closure fix below first appeared to work while the regenerated dispatch still
# imported `band` -- the artifacts came from the cache, not the parser.
# 7 -> 8: module-level functions must start at column 0, so nested closures are no longer
# discovered (`gemm.blocked.band`, `gemm.blocked.gemv_band`, `gemm.quantized.nf4_band`).
_RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION = 8

_IMPORT_RE = re.compile(r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+", re.MULTILINE)
_FUNCTION_RE = re.compile(r"^\s*(?:fn|def)\s+([A-Za-z][A-Za-z0-9_]*)\s*\(")
_ALLOWED_IMPORT_ROOTS = {"std", "math", "memory", "mojo", "sys"}
_SKIP_PUBLIC_FUNCTIONS = {"main", "check"}
_SKIP_RUNTIME_IMPORT_PATHS = {
    "compare",
    "conv",
    "decision_tree",
    "decision_tree_parser",
    "expr",
    "field_mapper",
    "importance_sampling",
    "main",
    "math_ext",
    "net.unix_socket",
    "output",
    "python_bridge",
    "request_parser",
    "runtime_library_dispatch_generated",
    "sha256",
    "time_series",
    "types",
    "validate",
    "vector_kernels.prefilter",
}
_SKIP_RUNTIME_RELATIVE_PREFIXES = {
    ("vector_kernels", "semantic_micro"),
}
# main's expanded skip list, kept in full: the universal-substrate work in #414 added runtime dirs that
# are not part of the callable library surface.
# "hostio" is infrastructure, not a kernel, and its exclusion is security-relevant rather than
# cosmetic: sn_socket_unix() takes no arguments and returns an Int, which is a *valid* runtime
# contract signature, so without this entry any SDK caller could open sockets inside the worker.
_SKIP_RUNTIME_DIRS = {"engines", "algenta_runtime", "canonical", "columnar", "determinism",
                      "hostio", "numeric", "query"}
# Maximum source lines one function signature may span while still being parsed. This was 10, which
# silently truncated anything longer -- and a truncated signature parses as ZERO parameters, which the
# dispatch generator then emits as a zero-argument call to a multi-argument function.
# ``seq_nn.lstm_cell_backward`` (9 params across 11 lines) hit exactly that. Truncation is now also
# caught by parenthesis balance and the function skipped rather than recorded with a wrong arity, so
# the failure mode is a missing inventory entry instead of generated code that cannot compile.
_SIGNATURE_MAX_LINES = 40
_BENCHMARK_NON_RUNTIME_LIB_IDS = {
    "engines_column_ranker_table",
    "engines_column_ranker_v2",
    "engines_prefilter_vs_fullscan",
    "vector_kernels_bench_prefilter",
    "vector_kernels_token_index",
}
_SIMPLE_RUNTIME_TYPES = {
    "Bool",
    "Float32",
    "Float64",
    "Int",
    "None",
    "String",
    "UInt16",
    "UInt32",
    "UInt64",
    "UInt8",
}
_NON_STRING_RUNTIME_TYPES = {
    "Bool",
    "Float32",
    "Float64",
    "Int",
    "None",
    "UInt16",
    "UInt32",
    "UInt64",
    "UInt8",
}
# NOTE: during full-tree discovery this set is currently inert, because the call site merges
# `global_struct_specs` (every struct in the tree) into `struct_specs`, and
# `is_runtime_executable_function` reads a non-empty `struct_specs` as "strings allowed". Modules are
# still listed here when they deliberately return `String`, so the intent is recorded rather than
# resting on that emergent behaviour.
_STRING_RETURN_RUNTIME_IMPORT_PATHS = {
    "color_check",
    "column_rank",
    "crypto.base64",
    "crypto.uuid",
    "json.writer",
    "tensorx.contract",
    "tensorx.dtype",
    "text.tokenizer",
    "vector_kernels.ranker",
    "vector_kernels.repo_ranker",
}
_STRUCT_RETURN_RUNTIME_TYPES: dict[str, set[str]] = {
    "vector_kernels.table": {"CandidateTable", "RankRequest"},
}


@dataclass(frozen=True)
class SourceModule:
    import_path: str
    lib_id: str
    path: Path
    public_functions: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeParamSpec:
    name: str
    typ: str
    has_default: bool
    is_mut: bool = False


@dataclass(frozen=True)
class RuntimeFunctionSpec:
    name: str
    params: tuple[RuntimeParamSpec, ...]
    return_type: str


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
    lib_id: str
    path: Path
    functions: tuple[RuntimeFunctionSpec, ...]


@dataclass(frozen=True)
class RuntimeModuleTarget:
    path: Path
    relative_path: str
    import_path: str
    lib_id: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class MojoInventoryReport:
    source_modules: tuple[SourceModule, ...]
    artifact_import_modules: tuple[str, ...]
    artifact_benchmark_result_libs: tuple[str, ...]
    artifact_benchmark_bench_libs: tuple[str, ...]
    threshold_target: int

    @property
    def source_module_count(self) -> int:
        return len(self.source_modules)

    @property
    def source_modules_with_public_functions_count(self) -> int:
        return sum(1 for module in self.source_modules if module.public_functions)

    @property
    def source_public_function_count(self) -> int:
        return sum(len(module.public_functions) for module in self.source_modules)

    @property
    def source_import_paths(self) -> tuple[str, ...]:
        return tuple(module.import_path for module in self.source_modules)

    @property
    def source_lib_ids(self) -> tuple[str, ...]:
        return tuple(module.lib_id for module in self.source_modules)

    @property
    def test_all_missing_from_source(self) -> tuple[str, ...]:
        source_imports = set(self.source_import_paths)
        return tuple(
            module for module in self.artifact_import_modules if module not in source_imports
        )

    @property
    def benchmark_results_missing_from_source(self) -> tuple[str, ...]:
        source_lib_ids = set(self.source_lib_ids)
        return tuple(
            lib_id for lib_id in self.artifact_benchmark_result_libs if lib_id not in source_lib_ids
        )

    @property
    def benchmark_benches_missing_from_source(self) -> tuple[str, ...]:
        source_lib_ids = set(self.source_lib_ids)
        return tuple(
            lib_id for lib_id in self.artifact_benchmark_bench_libs if lib_id not in source_lib_ids
        )

    @property
    def threshold_met(self) -> bool:
        return self.source_modules_with_public_functions_count >= self.threshold_target

    @property
    def threshold_gap(self) -> int:
        return max(0, self.threshold_target - self.source_modules_with_public_functions_count)

    def to_dict(self) -> dict[str, object]:
        return {
            "threshold_target": self.threshold_target,
            "threshold_met": self.threshold_met,
            "threshold_gap": self.threshold_gap,
            "source_module_count": self.source_module_count,
            "source_modules_with_public_functions_count": (
                self.source_modules_with_public_functions_count
            ),
            "source_public_function_count": self.source_public_function_count,
            "artifact_import_module_count": len(self.artifact_import_modules),
            "artifact_benchmark_result_count": len(self.artifact_benchmark_result_libs),
            "artifact_benchmark_bench_count": len(self.artifact_benchmark_bench_libs),
            "test_all_missing_from_source_count": len(self.test_all_missing_from_source),
            "benchmark_results_missing_from_source_count": len(
                self.benchmark_results_missing_from_source
            ),
            "benchmark_benches_missing_from_source_count": len(
                self.benchmark_benches_missing_from_source
            ),
            "test_all_missing_from_source": list(self.test_all_missing_from_source),
            "benchmark_results_missing_from_source": list(
                self.benchmark_results_missing_from_source
            ),
            "benchmark_benches_missing_from_source": list(
                self.benchmark_benches_missing_from_source
            ),
            "source_modules": [
                {
                    "import_path": module.import_path,
                    "lib_id": module.lib_id,
                    "path": str(module.path),
                    "public_functions": list(module.public_functions),
                }
                for module in self.source_modules
            ],
        }


def _module_import_path(path: Path, engine_root: Path) -> str:
    relative = path.relative_to(engine_root).with_suffix("")
    return ".".join(relative.parts)


def _module_lib_id(import_path: str) -> str:
    return import_path.replace(".", "_")


def _parse_public_functions(path: Path) -> tuple[str, ...]:
    public_functions: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _FUNCTION_RE.match(line)
        if match is None:
            continue
        function_name = match.group(1)
        if function_name.startswith("_") or function_name in _SKIP_PUBLIC_FUNCTIONS:
            continue
        public_functions.append(function_name)
    return tuple(public_functions)


def _clean_type(type_name: str) -> str:
    cleaned = re.sub(r"\s+", " ", type_name.split("=", 1)[0].strip())
    cleaned = cleaned.split("#", 1)[0].strip()
    for prefix in ("owned ", "inout ", "ref ", "read ", "mut "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    return cleaned.strip()


def _parse_param_specs(raw_params: str) -> tuple[RuntimeParamSpec, ...] | None:
    parts: list[str] = []
    depth = 0
    current = ""
    for char in raw_params:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())

    parsed: list[RuntimeParamSpec] = []
    for part in parts:
        if not part:
            continue
        is_mut = bool(re.match(r"(mut|inout)\s+", part))
        match = re.match(r"(?:mut\s+|owned\s+|inout\s+)?(\w+)\s*:\s*(.+)", part)
        if match is None:
            return None
        parsed.append(
            RuntimeParamSpec(
                name=match.group(1),
                typ=_clean_type(match.group(2)),
                has_default="=" in match.group(2),
                is_mut=is_mut,
            )
        )
    return tuple(parsed)


def _parse_runtime_function_specs(path: Path) -> tuple[RuntimeFunctionSpec, ...]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    specs: list[RuntimeFunctionSpec] = []
    index = 0
    docstring_delimiter: str | None = None

    while index < len(lines):
        stripped = lines[index].strip()

        if docstring_delimiter is not None:
            if docstring_delimiter in stripped and stripped.count(docstring_delimiter) % 2 == 1:
                docstring_delimiter = None
            index += 1
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            delimiter = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(delimiter) % 2 == 1:
                docstring_delimiter = delimiter
            index += 1
            continue

        # Matching against `stripped` throws the indentation away, so a NESTED function is
        # indistinguishable from a module-level one. A module-level Mojo function starts at
        # column 0; anything indented is a struct method or a `@parameter fn ... capturing:`
        # closure inside another function's body, and neither is importable by name.
        #
        # Struct methods took `self`, which `_parse_param_specs` rejects, so they never reached
        # the contract and the missing check went unnoticed. A `parallelize` worker closure is
        # what slips through: `(tid: Int)` is fully marshalable, so the generated dispatch
        # emitted `from gemm.blocked import band` for a symbol the module does not export, which
        # does not compile. That put `make inventory-check` permanently red while
        # `make inventory-refresh`, its own documented remedy, produced the broken artifact.
        #
        # Four exist in the tree, and both spellings count -- `fn ... capturing:` and a plain
        # nested `def`:
        #   gemm/blocked.mojo:229   fn band(tid: Int) capturing:
        #   gemm/blocked.mojo:349   fn gemv_band(tid: Int) capturing:
        #   gemm/quantized.mojo:203 fn nf4_band(tid: Int) capturing:
        #   seq2_trainer.mojo:1007  def worker(tid: Int):
        # The last one has been in the shipped contract and dispatch since long before the
        # others, so the contract advertised a callable that cannot be imported. Nothing caught
        # it because CI compiles FILTERED shards, never the whole dispatch.
        if lines[index][:1].isspace():
            index += 1
            continue

        match = re.match(r"(?:fn|def)\s+([A-Za-z][A-Za-z0-9_]*)\s*\(", stripped)
        if match is None:
            index += 1
            continue

        function_name = match.group(1)
        if function_name.startswith("_") or function_name in _SKIP_PUBLIC_FUNCTIONS:
            index += 1
            continue

        signature_lines = [stripped]
        lookahead = index + 1
        while lookahead < min(index + _SIGNATURE_MAX_LINES, len(lines)):
            joined = " ".join(signature_lines)
            last = signature_lines[-1]
            balanced = joined.count("(") == joined.count(")")
            terminated = last.endswith(":") or bool(
                re.search(r"->.*:", last) and not last.endswith(",")
            )
            if balanced and terminated:
                break
            next_line = lines[lookahead].strip()
            if not next_line:
                lookahead += 1
                continue
            if re.match(r"(?:fn|def|struct|from|var|let)\s", next_line):
                break
            signature_lines.append(next_line)
            lookahead += 1

        signature = " ".join(signature_lines)
        if signature.count("(") != signature.count(")"):
            # Truncated or malformed. Skipping loses one inventory entry; recording it would set
            # arity to zero and make the dispatch generator emit an uncompilable call.
            index += 1
            continue
        params_match = re.search(r"\(([^)]*)\)", signature)
        if params_match is None:
            # Signature never closed within the lookahead window, so the parse is
            # truncated. Skip rather than emit `f()`: a wrong arity in the
            # contract is worse than an absent entry, because the dispatch table
            # would then accept a call with no arguments.
            index += 1
            continue
        params = _parse_param_specs(params_match.group(1))
        if params is None:
            index += 1
            continue

        return_type_match = re.search(r"->\s*([^\n:{]+)", signature)
        return_type = (
            re.sub(r"\s+", " ", return_type_match.group(1).strip().rstrip("{: "))
            if return_type_match
            else "None"
        )
        specs.append(
            RuntimeFunctionSpec(
                name=function_name,
                params=params,
                return_type=return_type,
            )
        )
        index = lookahead

    return tuple(specs)


def parse_runtime_struct_specs(path: Path) -> dict[str, RuntimeStructSpec]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    specs: dict[str, RuntimeStructSpec] = {}
    index = 0
    docstring_delimiter: str | None = None

    while index < len(lines):
        stripped = lines[index].strip()
        if docstring_delimiter is not None:
            if docstring_delimiter in stripped and stripped.count(docstring_delimiter) % 2 == 1:
                docstring_delimiter = None
            index += 1
            continue

        if stripped.startswith('"""') or stripped.startswith("'''"):
            delimiter = '"""' if stripped.startswith('"""') else "'''"
            if stripped.count(delimiter) % 2 == 1:
                docstring_delimiter = delimiter
            index += 1
            continue

        struct_match = re.match(r"^\s*struct\s+([A-Za-z_][A-Za-z0-9_]*)", lines[index])
        if struct_match is None:
            index += 1
            continue


        struct_name = struct_match.group(1)
        struct_indent = len(lines[index]) - len(lines[index].lstrip(" "))
        index += 1
        fields: list[RuntimeStructFieldSpec] = []
        while index < len(lines):
            raw_line = lines[index]
            stripped_line = raw_line.strip()
            current_indent = len(raw_line) - len(raw_line.lstrip(" "))
            if stripped_line and current_indent <= struct_indent:
                break
            field_match = re.match(r"^\s*var\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", raw_line)
            if field_match is not None and current_indent == struct_indent + 4:
                fields.append(
                    RuntimeStructFieldSpec(
                        name=field_match.group(1),
                        typ=_clean_type(field_match.group(2)),
                    )
                )
            index += 1

        specs[struct_name] = RuntimeStructSpec(name=struct_name, fields=tuple(fields))

    return specs


def _is_list_type(type_name: str) -> bool:
    return type_name.startswith("List[") and type_name.endswith("]")


def _list_inner_type(type_name: str) -> str:
    return type_name[5:-1]


def _is_runtime_supported_type(
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec],
    visited_structs: set[str],
    allow_strings: bool,
) -> bool:
    if type_name in _SIMPLE_RUNTIME_TYPES:
        return True
    if type_name == "String":
        return allow_strings
    if _is_list_type(type_name):
        return _is_runtime_supported_type(
            _list_inner_type(type_name),
            struct_specs=struct_specs,
            visited_structs=visited_structs,
            allow_strings=allow_strings,
        )
    if type_name in struct_specs:
        if type_name in visited_structs:
            return False
        visited_structs.add(type_name)
        try:
            return all(
                _is_runtime_supported_type(
                    field.typ,
                    struct_specs=struct_specs,
                    visited_structs=visited_structs,
                    allow_strings=allow_strings,
                )
                for field in struct_specs[type_name].fields
            )
        finally:
            visited_structs.remove(type_name)
    return False


def is_runtime_supported_param_type(
    type_name: str,
    *,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
) -> bool:
    return _is_runtime_supported_type(
        type_name,
        struct_specs=struct_specs or {},
        visited_structs=set(),
        allow_strings=True,
    )


def is_runtime_supported_return_type(
    type_name: str,
    *,
    allow_strings: bool = False,
    allow_struct_types: set[str] | None = None,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
) -> bool:
    allowed_struct_specs = struct_specs or {}
    if (
        allow_struct_types
        and type_name in allow_struct_types
        and type_name not in allowed_struct_specs
    ):
        return True
    return _is_runtime_supported_type(
        type_name,
        struct_specs=allowed_struct_specs,
        visited_structs=set(),
        allow_strings=allow_strings,
    )


def is_runtime_executable_function(
    spec: RuntimeFunctionSpec,
    *,
    import_path: str | None = None,
    struct_specs: dict[str, RuntimeStructSpec] | None = None,
) -> bool:
    allow_strings = True if struct_specs else import_path in _STRING_RETURN_RUNTIME_IMPORT_PATHS
    resolved_struct_specs = struct_specs or {}
    allow_struct_types = _STRUCT_RETURN_RUNTIME_TYPES.get(import_path or "", set())
    for struct_name in allow_struct_types:
        if struct_name not in resolved_struct_specs:
            return False
    return all(
        is_runtime_supported_param_type(param.typ, struct_specs=resolved_struct_specs)
        for param in spec.params
    ) and (
        is_runtime_supported_return_type(
            spec.return_type,
            allow_strings=allow_strings,
            allow_struct_types=allow_struct_types,
            struct_specs=resolved_struct_specs,
        )
    )


def _iter_runtime_module_targets(engine_root: Path) -> Iterable[tuple[Path, str, str]]:
    for path in sorted(engine_root.rglob("*.mojo")):
        relative = path.relative_to(engine_root)
        if path.name == "__init__.mojo":
            continue
        if any(
            relative.parts[: len(prefix)] == prefix for prefix in _SKIP_RUNTIME_RELATIVE_PREFIXES
        ):
            continue
        if relative.parts and relative.parts[0] in _SKIP_RUNTIME_DIRS:
            continue
        import_path = _module_import_path(path, engine_root)
        if import_path in _SKIP_RUNTIME_IMPORT_PATHS:
            continue
        yield path, import_path, _module_lib_id(import_path)


def _runtime_cache_path(engine_root: Path, cache_path: Path | None) -> Path | None:
    if cache_path is not None:
        return cache_path
    if engine_root == DEFAULT_ENGINE_DIR:
        return DEFAULT_RUNTIME_LIBRARY_CACHE
    return None


def _runtime_module_targets_snapshot(
    engine_root: Path,
) -> tuple[tuple[RuntimeModuleTarget, ...], str]:
    hasher = hashlib.sha256()
    snapshots: list[RuntimeModuleTarget] = []
    for path, import_path, lib_id in _iter_runtime_module_targets(engine_root):
        stat = path.stat()
        relative_path = path.relative_to(engine_root).as_posix()
        hasher.update(relative_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(str(stat.st_size).encode("ascii"))
        hasher.update(b"\0")
        hasher.update(str(stat.st_mtime_ns).encode("ascii"))
        hasher.update(b"\0")
        snapshots.append(
            RuntimeModuleTarget(
                path=path,
                relative_path=relative_path,
                import_path=import_path,
                lib_id=lib_id,
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return tuple(snapshots), hasher.hexdigest()


def _runtime_param_spec_to_dict(spec: RuntimeParamSpec) -> dict[str, object]:
    return {
        "name": spec.name,
        "typ": spec.typ,
        "has_default": spec.has_default,
        "is_mut": spec.is_mut,
    }


def _runtime_param_spec_from_dict(payload: dict[str, object]) -> RuntimeParamSpec:
    return RuntimeParamSpec(
        name=str(payload["name"]),
        typ=str(payload["typ"]),
        has_default=bool(payload["has_default"]),
        is_mut=bool(payload.get("is_mut", False)),
    )


def _runtime_function_spec_to_dict(spec: RuntimeFunctionSpec) -> dict[str, object]:
    return {
        "name": spec.name,
        "params": [_runtime_param_spec_to_dict(param) for param in spec.params],
        "return_type": spec.return_type,
    }


def _runtime_function_spec_from_dict(payload: dict[str, object]) -> RuntimeFunctionSpec:
    params_payload = payload.get("params")
    params = (
        tuple(cast(dict[str, object], param) for param in params_payload if isinstance(param, dict))
        if isinstance(params_payload, list)
        else ()
    )
    return RuntimeFunctionSpec(
        name=str(payload["name"]),
        params=tuple(_runtime_param_spec_from_dict(param) for param in params),
        return_type=str(payload["return_type"]),
    )


def _runtime_module_to_dict(module: RuntimeLibraryModule, engine_root: Path) -> dict[str, object]:
    return {
        "relative_path": module.path.relative_to(engine_root).as_posix(),
        "import_path": module.import_path,
        "lib_id": module.lib_id,
        "functions": [_runtime_function_spec_to_dict(spec) for spec in module.functions],
    }


def _runtime_module_from_dict(
    payload: dict[str, object],
    engine_root: Path,
) -> RuntimeLibraryModule:
    functions_payload = payload.get("functions")
    functions = (
        tuple(cast(dict[str, object], spec) for spec in functions_payload if isinstance(spec, dict))
        if isinstance(functions_payload, list)
        else ()
    )
    return RuntimeLibraryModule(
        import_path=str(payload["import_path"]),
        lib_id=str(payload["lib_id"]),
        path=engine_root / str(payload["relative_path"]),
        functions=tuple(_runtime_function_spec_from_dict(spec) for spec in functions),
    )


def _load_runtime_library_manifest(
    *,
    engine_root: Path,
    cache_path: Path,
    fingerprint: str,
    executable_only: bool,
) -> tuple[RuntimeLibraryModule, ...] | None:
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("fingerprint") != fingerprint:
        return None
    if payload.get("schema_version") != _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION:
        return None
    if bool(payload.get("executable_only", True)) != executable_only:
        return None
    if payload.get("engine_root") != str(engine_root):
        return None
    modules = payload.get("modules")
    if not isinstance(modules, list):
        return None
    try:
        return tuple(_runtime_module_from_dict(dict(module), engine_root) for module in modules)
    except (KeyError, TypeError, ValueError):
        return None


def _write_runtime_library_manifest(
    *,
    engine_root: Path,
    cache_path: Path,
    fingerprint: str,
    executable_only: bool,
    modules: tuple[RuntimeLibraryModule, ...],
) -> None:
    payload = {
        "schema_version": _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION,
        "engine_root": str(engine_root),
        "fingerprint": fingerprint,
        "executable_only": executable_only,
        "module_count": len(modules),
        "modules": [_runtime_module_to_dict(module, engine_root) for module in modules],
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return


def discover_runtime_library_modules(
    engine_root: Path = DEFAULT_ENGINE_DIR,
    *,
    executable_only: bool = True,
    cache_path: Path | None = None,
) -> tuple[RuntimeLibraryModule, ...]:
    resolved_cache_path = _runtime_cache_path(engine_root, cache_path)
    targets, fingerprint = _runtime_module_targets_snapshot(engine_root)
    if resolved_cache_path is not None:
        cached = _load_runtime_library_manifest(
            engine_root=engine_root,
            cache_path=resolved_cache_path,
            fingerprint=fingerprint,
            executable_only=executable_only,
        )
        if cached is not None:
            return cached

    modules: list[RuntimeLibraryModule] = []
    module_struct_specs: dict[str, dict[str, RuntimeStructSpec]] = {}
    global_struct_specs: dict[str, RuntimeStructSpec] = {}
    for target in targets:
        specs = parse_runtime_struct_specs(target.path)
        module_struct_specs[target.import_path] = specs
        for struct_name, struct_spec in specs.items():
            global_struct_specs.setdefault(struct_name, struct_spec)

    for target in targets:
        functions = _parse_runtime_function_specs(target.path)
        struct_specs = {
            **global_struct_specs,
            **module_struct_specs.get(target.import_path, {}),
        }
        if executable_only:
            functions = tuple(
                spec
                for spec in functions
                if is_runtime_executable_function(
                    spec,
                    import_path=target.import_path,
                    struct_specs=struct_specs,
                )
            )
        if not functions:
            continue
        modules.append(
            RuntimeLibraryModule(
                import_path=target.import_path,
                lib_id=target.lib_id,
                path=target.path,
                functions=functions,
            )
        )
    result = tuple(modules)
    if resolved_cache_path is not None:
        _write_runtime_library_manifest(
            engine_root=engine_root,
            cache_path=resolved_cache_path,
            fingerprint=fingerprint,
            executable_only=executable_only,
            modules=result,
        )
    return result


def discover_source_modules(engine_root: Path = DEFAULT_ENGINE_DIR) -> tuple[SourceModule, ...]:
    modules: list[SourceModule] = []
    for path in sorted(engine_root.rglob("*.mojo")):
        if path.name == "__init__.mojo":
            continue
        import_path = _module_import_path(path, engine_root)
        modules.append(
            SourceModule(
                import_path=import_path,
                lib_id=_module_lib_id(import_path),
                path=path,
                public_functions=_parse_public_functions(path),
            )
        )
    return tuple(modules)


def parse_test_all_import_modules(
    test_all_path: Path = DEFAULT_TEST_ALL_LIBRARIES,
) -> tuple[str, ...]:
    if not test_all_path.exists():
        return ()
    modules = {
        match
        for match in _IMPORT_RE.findall(test_all_path.read_text(encoding="utf-8", errors="replace"))
        if match.split(".", 1)[0] not in _ALLOWED_IMPORT_ROOTS
    }
    return tuple(sorted(modules))


def discover_benchmark_result_libs(
    results_dir: Path = DEFAULT_BENCHMARK_RESULTS_DIR,
) -> tuple[str, ...]:
    if not results_dir.exists():
        return ()
    return tuple(
        sorted(
            path.stem
            for path in results_dir.glob("*.json")
            if path.stem not in _BENCHMARK_NON_RUNTIME_LIB_IDS
        )
    )


def discover_benchmark_bench_libs(bench_dir: Path = DEFAULT_BENCHMARK_MOJO_DIR) -> tuple[str, ...]:
    if not bench_dir.exists():
        return ()
    return tuple(
        sorted(
            lib_id
            for path in bench_dir.glob("bench_*.mojo")
            for lib_id in [path.stem.removeprefix("bench_")]
            if lib_id not in _BENCHMARK_NON_RUNTIME_LIB_IDS
        )
    )


def build_inventory_report(
    *,
    engine_root: Path = DEFAULT_ENGINE_DIR,
    test_all_path: Path = DEFAULT_TEST_ALL_LIBRARIES,
    benchmark_results_dir: Path = DEFAULT_BENCHMARK_RESULTS_DIR,
    benchmark_mojo_dir: Path = DEFAULT_BENCHMARK_MOJO_DIR,
    threshold_target: int = 400,
) -> MojoInventoryReport:
    return MojoInventoryReport(
        source_modules=discover_source_modules(engine_root),
        artifact_import_modules=parse_test_all_import_modules(test_all_path),
        artifact_benchmark_result_libs=discover_benchmark_result_libs(benchmark_results_dir),
        artifact_benchmark_bench_libs=discover_benchmark_bench_libs(benchmark_mojo_dir),
        threshold_target=threshold_target,
    )


# ── declared capabilities ─────────────────────────────────────────────────────
#
# A second, independent pass. It reads the same files but writes nothing into the
# signature/struct output above and does not touch the runtime-library cache, so the
# contract and the dispatch table are bit-identical with and without this section.


class CapabilityManifestError(RuntimeError):
    """A declared block is unusable. Never downgraded to "nothing was declared"."""

    def __init__(self, issues: tuple[CapabilityIssue, ...]) -> None:
        self.issues = issues
        rendered = "\n".join(issue.render() for issue in issues[:20])
        super().__init__(
            f"{len(issues)} capability declaration issue(s):\n{rendered}"
            + ("\n..." if len(issues) > 20 else "")
        )


@dataclass(frozen=True)
class RuntimeModuleCapabilities:
    import_path: str
    lib_id: str
    path: Path
    module: RuntimeCapabilitySpec | None
    functions: tuple[RuntimeCapabilitySpec, ...]
    issues: tuple[CapabilityIssue, ...]
    #: Contract functions taking at least one `List` and at least one `Int` -- the shape in
    #: which a count/length relation can exist at all, declared or not.
    count_pair_functions: tuple[str, ...]

    @property
    def by_name(self) -> dict[str, RuntimeCapabilitySpec]:
        return {spec.target: spec for spec in self.functions}

    @property
    def declared_count_functions(self) -> tuple[str, ...]:
        declared = self.by_name
        return tuple(
            name
            for name in self.count_pair_functions
            if name in declared and declared[name].declares_counts
        )

    @property
    def undeclared_count_pair_functions(self) -> tuple[str, ...]:
        declared = set(self.declared_count_functions)
        return tuple(name for name in self.count_pair_functions if name not in declared)

    @property
    def is_fully_declared(self) -> bool:
        """A module block plus a `counts:` decision on every count-pair function."""
        return self.module is not None and not self.undeclared_count_pair_functions


@dataclass(frozen=True)
class RuntimeCapabilityManifest:
    modules: tuple[RuntimeModuleCapabilities, ...]

    @property
    def issues(self) -> tuple[CapabilityIssue, ...]:
        return tuple(issue for module in self.modules for issue in module.issues)

    @property
    def by_import_path(self) -> dict[str, RuntimeModuleCapabilities]:
        return {module.import_path: module for module in self.modules}

    def function_capability(
        self,
        import_path: str,
        function_name: str,
    ) -> RuntimeCapabilitySpec | None:
        module = self.by_import_path.get(import_path)
        if module is None:
            return None
        return module.by_name.get(function_name)

    @property
    def undeclared_count_pair_function_count(self) -> int:
        return sum(len(module.undeclared_count_pair_functions) for module in self.modules)

    @property
    def declared_module_count(self) -> int:
        return sum(1 for module in self.modules if module.is_fully_declared)


def _count_pair_function_names(functions: Iterable[RuntimeFunctionSpec]) -> tuple[str, ...]:
    names: list[str] = []
    for spec in functions:
        has_list = any(_is_list_type(param.typ) for param in spec.params)
        has_int = any(param.typ == "Int" for param in spec.params)
        if has_list and has_int:
            names.append(spec.name)
    return tuple(names)


def _cross_validate_capabilities(
    parse: CapabilityParse,
    functions: tuple[RuntimeFunctionSpec, ...],
) -> tuple[CapabilityIssue, ...]:
    """Check every name a block mentions against the signature actually in the file.

    This is what stops a declaration from drifting into fiction: a renamed parameter, a
    count that is not an `Int`, or a bounded argument that is not a `List` all become
    issues instead of a relation the checker would quietly never evaluate.
    """
    issues: list[CapabilityIssue] = []
    by_name = {spec.name: spec for spec in functions}
    for spec in parse.functions:
        signature = by_name.get(spec.target)
        if signature is None:
            issues.append(
                CapabilityIssue(
                    path=parse.path,
                    line=spec.line,
                    code="unknown_function",
                    message=(
                        f"capability block declares {spec.target!r}, which is not a public "
                        "function parsed from this file"
                    ),
                )
            )
            continue
        params = {param.name: param for param in signature.params}
        for relation in spec.count_relations or ():
            for name in relation.counts:
                param = params.get(name)
                if param is None:
                    issues.append(
                        CapabilityIssue(
                            path=parse.path,
                            line=relation.line,
                            code="relation_unknown_parameter",
                            message=(
                                f"{spec.target}: {name!r} in {relation.raw!r} is not a "
                                f"parameter of {spec.target}"
                            ),
                        )
                    )
                elif param.typ != "Int":
                    issues.append(
                        CapabilityIssue(
                            path=parse.path,
                            line=relation.line,
                            code="count_parameter_not_int",
                            message=(
                                f"{spec.target}: count {name!r} is declared {param.typ}, not Int"
                            ),
                        )
                    )
            for name in relation.bounded_lists:
                param = params.get(name)
                if param is None:
                    issues.append(
                        CapabilityIssue(
                            path=parse.path,
                            line=relation.line,
                            code="relation_unknown_parameter",
                            message=(
                                f"{spec.target}: {name!r} in {relation.raw!r} is not a "
                                f"parameter of {spec.target}"
                            ),
                        )
                    )
                elif not _is_list_type(param.typ):
                    issues.append(
                        CapabilityIssue(
                            path=parse.path,
                            line=relation.line,
                            code="bounded_parameter_not_a_list",
                            message=(
                                f"{spec.target}: len({name}) is declared {param.typ}, which has no "
                                "length"
                            ),
                        )
                    )
    return tuple(issues)


def parse_runtime_capability_specs(path: Path) -> CapabilityParse:
    """Declared capability blocks in one `.mojo` file, cross-checked against its signatures.

    Mirrors `parse_runtime_struct_specs`: one file, no caching, no side effects. Issues are
    returned, never raised and never swallowed -- see `build_capability_manifest` for the
    fail-loud aggregation.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    parse = parse_capability_blocks(text, path=path.as_posix())
    if parse.module is None and not parse.functions:
        return parse
    functions = _parse_runtime_function_specs(path)
    inherited = tuple(spec.inherit(parse.module) for spec in parse.functions)
    return CapabilityParse(
        path=parse.path,
        module=parse.module,
        functions=inherited,
        issues=parse.issues + _cross_validate_capabilities(parse, functions),
    )


def build_capability_manifest(
    engine_root: Path = DEFAULT_ENGINE_DIR,
    *,
    strict: bool = True,
) -> RuntimeCapabilityManifest:
    """Declared capabilities for every module in the runtime contract.

    `strict=True` (the default, and what every runtime caller must use) raises
    `CapabilityManifestError` when any block anywhere failed to parse or cross-validate.
    Returning a partial manifest would present a broken declaration as an absent one, and
    an absent declaration disables the pre-call guard -- exactly the silent-skip failure
    this phase exists to remove. The gate passes `strict=False` so it can print every
    issue at once instead of the first twenty.
    """
    modules: list[RuntimeModuleCapabilities] = []
    library_modules = {
        module.import_path: module
        for module in discover_runtime_library_modules(engine_root, executable_only=True)
    }
    for path, import_path, lib_id in _iter_runtime_module_targets(engine_root):
        parse = parse_runtime_capability_specs(path)
        library_module = library_modules.get(import_path)
        contract_functions = library_module.functions if library_module is not None else ()
        modules.append(
            RuntimeModuleCapabilities(
                import_path=import_path,
                lib_id=lib_id,
                path=path,
                module=parse.module,
                functions=parse.functions,
                issues=parse.issues,
                count_pair_functions=_count_pair_function_names(contract_functions),
            )
        )
    manifest = RuntimeCapabilityManifest(modules=tuple(modules))
    if strict and manifest.issues:
        raise CapabilityManifestError(manifest.issues)
    return manifest
