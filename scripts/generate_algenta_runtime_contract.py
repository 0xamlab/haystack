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

from apps.runtime.mojo_count_relations import declared_count_spec  # noqa: E402
from apps.runtime.mojo_inventory import (  # noqa: E402
    RuntimeStructSpec,
    discover_engine_kernels,
    discover_runtime_library_modules,
    engine_kernels_payload,
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
            payload: dict[str, Any] = {
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
            # The declared count relations travel with the function so the local SDK can
            # refuse an over-large element count before the frame reaches the worker, where
            # reading past a List end is an uncatchable process abort. Emitted only when
            # non-empty: an absent key and an empty list mean the same thing to the loader,
            # and omitting it keeps the contract diff to the functions actually declared.
            count_spec = declared_count_spec(module.import_path, function.name)
            if count_spec is not None and count_spec.relations:
                payload["count_relations"] = count_spec.to_payload()
            functions.append(payload)
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

    # The public ENGINE-KERNEL inventory: the pointer-based CUDA/Metal kernels the engine
    # races, parsed straight from the Mojo sources. A SEPARATE top-level section on purpose:
    # `modules` is the JSON-callable surface and these kernels are not JSON-frameable (their
    # arguments are device pointers), so listing them there would fake callability. Their
    # public surface is capability declaration — what ships, per backend and model family —
    # ratcheted by scripts/audit_gap_checks.py so a kernel can never silently vanish.
    engine_kernels = engine_kernels_payload(discover_engine_kernels())

    return {
        "schema_version": 1,
        "module_count": len(payload_modules),
        "function_count": function_count,
        "modules": payload_modules,
        "engine_kernels": engine_kernels,
    }


def load_bundle_metadata(paths: list[Path]) -> list[dict[str, Any]]:
    """Load + shape-check bundle-metadata.json files from build_runtime_bundle.py."""
    entries: list[dict[str, Any]] = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SystemExit(f"bundle metadata {path} is not a JSON object")
        for field in ("version", "platform", "sha256", "url_template"):
            if not isinstance(payload.get(field), str) or not payload[field]:
                raise SystemExit(f"bundle metadata {path} missing string field {field!r}")
        entries.append(payload)
    return entries


def build_runtime_bundle_footer(
    metadata_entries: list[dict[str, Any]],
    *,
    public_key_pem: str | None = None,
) -> dict[str, Any]:
    """The runtime_bundle footer: version + per-platform URLs + sha256s (+ public key).

    This is the fragment the SQAI capability contract's runtime_bundle section is
    updated from at bundle-cut time. It is deliberately EXCLUDED from --check
    comparisons: the footer is stamped when a bundle is cut, never regenerated
    from the engine sources, so the library-surface gate must not churn on it.
    """
    versions = sorted({entry["version"] for entry in metadata_entries})
    if len(versions) != 1:
        raise SystemExit(
            f"bundle metadata files disagree on version: {', '.join(versions) or '(none)'}"
        )
    platforms: dict[str, Any] = {}
    for entry in sorted(metadata_entries, key=lambda item: str(item["platform"])):
        platform = entry["platform"]
        if platform in platforms:
            raise SystemExit(f"duplicate bundle metadata platform: {platform!r}")
        platforms[platform] = {
            "sha256": entry["sha256"],
            "url": entry["url_template"].format(version=entry["version"], platform=platform),
        }
    footer: dict[str, Any] = {"version": versions[0], "platforms": platforms}
    if public_key_pem:
        footer["public_key"] = public_key_pem
    return footer


def _strip_footer(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "runtime_bundle"}


def _encoded_contract(contract: dict[str, Any]) -> bytes:
    return (json.dumps(contract, sort_keys=True, separators=(",", ":")) + "\n").encode()


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
    parser.add_argument(
        "--bundle-metadata",
        type=Path,
        action="append",
        default=[],
        help="bundle-metadata.json from scripts/build_runtime_bundle.py (repeat per "
        "platform); stamps the runtime_bundle footer (version + per-platform URLs + "
        "sha256s). --check ignores the footer either way.",
    )
    parser.add_argument(
        "--bundle-public-key",
        type=Path,
        default=None,
        help="PEM public key used to verify bundle manifests; embedded in the footer "
        "next to the URLs/hashes (requires --bundle-metadata)",
    )
    args = parser.parse_args()

    public_key_pem: str | None = None
    if args.bundle_public_key is not None:
        if not args.bundle_metadata:
            raise SystemExit("--bundle-public-key requires --bundle-metadata")
        public_key_pem = args.bundle_public_key.read_text(encoding="utf-8").strip()
        if not public_key_pem:
            raise SystemExit(f"--bundle-public-key file is empty: {args.bundle_public_key}")

    contract = build_contract()
    footer = (
        build_runtime_bundle_footer(
            load_bundle_metadata(args.bundle_metadata), public_key_pem=public_key_pem
        )
        if args.bundle_metadata
        else None
    )

    if args.check:
        # The gate covers the library SURFACE only. The runtime_bundle footer is stamped
        # at bundle-cut time and carried verbatim in the checked-in file; it is never
        # derivable from the engine sources, so it must not affect freshness.
        if not args.output.is_file():
            raise SystemExit(f"stale generated runtime contract: {args.output}")
        checked = json.loads(args.output.read_text(encoding="utf-8"))
        if _encoded_contract(_strip_footer(checked)) != _encoded_contract(contract):
            raise SystemExit(f"stale generated runtime contract: {args.output}")
        print(f"runtime contract OK: {args.output}")
        if args.bundle_metadata:
            print(json.dumps({"runtime_bundle": footer}, indent=2, sort_keys=True))
        return 0

    if footer is None and args.output.is_file():
        # A regeneration without fresh metadata must NOT drop a stamped footer —
        # `make inventory-refresh` keeps the pinned bundle until the next cut.
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        if isinstance(existing.get("runtime_bundle"), dict):
            footer = existing["runtime_bundle"]
    if footer is not None:
        contract["runtime_bundle"] = footer
    _write_atomic(args.output, _encoded_contract(contract))
    print(f"wrote {args.output}")
    if footer is not None:
        print(json.dumps({"runtime_bundle": footer}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
