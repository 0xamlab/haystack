#!/usr/bin/env python3
"""Generate the sanitized runtime-library contract shipped by ``algenta``."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime.mojo_inventory import (  # noqa: E402
    RuntimeStructSpec,
    discover_runtime_library_modules,
    parse_runtime_struct_specs,
)

DEFAULT_OUTPUT = ROOT / "packages" / "algenta" / "algenta" / "runtime_library_contract.json"
_SCALAR_TYPES = {
    "Bool",
    "Float32",
    "Float64",
    "Int",
    "None",
    "String",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
}


def _inner_type(type_name: str) -> str:
    resolved = type_name
    while resolved.startswith("List[") and resolved.endswith("]"):
        resolved = resolved[5:-1]
    return resolved


def _reachable_structs(
    type_names: set[str],
    struct_specs: dict[str, RuntimeStructSpec],
) -> list[dict[str, Any]]:
    pending = sorted({_inner_type(type_name) for type_name in type_names} - _SCALAR_TYPES)
    resolved: dict[str, RuntimeStructSpec] = {}
    while pending:
        struct_name = pending.pop()
        if struct_name in resolved:
            continue
        spec = struct_specs.get(struct_name)
        if spec is None:
            raise RuntimeError(f"Runtime contract references unknown type {struct_name!r}")
        resolved[struct_name] = spec
        for field in spec.fields:
            nested = _inner_type(field.typ)
            if nested not in _SCALAR_TYPES and nested not in resolved:
                pending.append(nested)
    return [
        {
            "name": name,
            "fields": [{"name": field.name, "type": field.typ} for field in resolved[name].fields],
        }
        for name in sorted(resolved)
    ]


def build_contract() -> dict[str, Any]:
    modules = discover_runtime_library_modules(executable_only=True)
    global_structs: dict[str, RuntimeStructSpec] = {}
    module_structs: dict[str, dict[str, RuntimeStructSpec]] = {}
    for module in modules:
        local_specs = parse_runtime_struct_specs(module.path)
        module_structs[module.import_path] = local_specs
        for name, spec in local_specs.items():
            global_structs.setdefault(name, spec)

    payload_modules: list[dict[str, Any]] = []
    function_count = 0
    for module in sorted(modules, key=lambda item: item.import_path):
        functions: list[dict[str, Any]] = []
        referenced_types: set[str] = set()
        for function in sorted(module.functions, key=lambda item: item.name):
            referenced_types.add(function.return_type)
            referenced_types.update(param.typ for param in function.params)
            functions.append(
                {
                    "name": function.name,
                    "params": [
                        {
                            "name": param.name,
                            "type": param.typ,
                            "has_default": param.has_default,
                            "is_mut": param.is_mut,
                        }
                        for param in function.params
                    ],
                    "return_type": function.return_type,
                }
            )
        resolved_structs = {**global_structs, **module_structs[module.import_path]}
        payload_modules.append(
            {
                "name": module.import_path,
                "engine": "mojo",
                "functions": functions,
                "structs": _reachable_structs(referenced_types, resolved_structs),
            }
        )
        function_count += len(functions)

    return {
        "schema_version": 1,
        "module_count": len(payload_modules),
        "function_count": function_count,
        "modules": payload_modules,
    }


def _encoded_contract() -> bytes:
    return (json.dumps(build_contract(), sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary_path, path)
    finally:
        Path(temporary_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = _encoded_contract()
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != content:
            raise SystemExit(f"stale generated runtime contract: {args.output}")
        print(f"runtime contract OK: {args.output}")
        return 0
    _write_atomic(args.output, content)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
