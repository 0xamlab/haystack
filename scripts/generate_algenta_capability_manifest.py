#!/usr/bin/env python3
"""Generate ``runtime_capability_manifest.json`` — the declared capability blocks the
``algenta`` package ships beside the runtime contract.

The SDK surface (``packages/algenta/algenta/capabilities.py``) reads every capability field
except ``count_relations`` from this resource. Without it the surface answered ``UNDECLARED``
for every field of every function forever, which is indistinguishable from a tree nobody has
annotated — so the declarations existed in the kernels and reached no caller. This script is
the missing half; ``make inventory-refresh`` writes it and ``make inventory-check`` proves it
is current.

What it transcribes, and what it refuses to invent
--------------------------------------------------
It is a TRANSCRIPTION, not an interpretation. Two rules follow from that, and both matter
more than the file being complete:

* **A field nobody declared is OMITTED.** Never ``false``, never ``null``, never an empty
  object. ``apps.runtime.mojo_capability_manifest.resolved_claims`` deliberately reads an
  absent ``deterministic`` as ``false`` for a scheduler that has to decide something; that
  collapse must not be baked into a shipped artifact, because a reader then cannot tell
  "the author said no" from "the author said nothing".
* **Only functions with their own ``@capability <name>`` block get an entry.** A module
  block "supplies DEFAULTS that function blocks may override", so its fields are inherited
  into function blocks (``RuntimeCapabilitySpec.inherit``) — and a function with no block
  of its own inherits nothing here. Spreading a module-scope ``deterministic: true`` across
  functions the author never annotated would manufacture a per-function claim from a
  module-scope one, which is exactly the "looks declared, is not" failure the declared-block
  mechanism exists to remove. Such a function reports ``has_block=False`` and every field
  ``UNDECLARED``, which is the honest answer.

``count_relations`` is deliberately NOT emitted. Relations travel on
``runtime_library_contract.json`` beside the signature they constrain, because the runtime
enforces them from there; shipping them twice would create two statements that can disagree.

Only functions the runtime contract actually exports are emitted. A block on a public
function that is not contract-executable cannot be described through the SDK at all, and an
entry naming a function the contract lacks would surface as
``CapabilityCatalog.orphan_declarations`` — a stale artifact rather than a declaration. Those
are counted and printed instead of being dropped in silence.
"""

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

from apps.runtime.mojo_capability_manifest import RuntimeCapabilitySpec  # noqa: E402
from apps.runtime.mojo_inventory import (  # noqa: E402
    DEFAULT_ENGINE_DIR,
    build_capability_manifest,
    discover_runtime_library_modules,
)

DEFAULT_OUTPUT = ROOT / "packages" / "algenta" / "algenta" / "runtime_capability_manifest.json"
SCHEMA_VERSION = 1

#: Declared block field -> the name the SDK surface reads. Every name here is in
#: `algenta.capabilities.CAPABILITY_FIELDS`; `count_relations` is absent on purpose (it
#: travels on the library contract) and `tests/test_algenta_capability_manifest_artifact.py`
#: asserts the two vocabularies stay in step rather than trusting this comment.
EMITTED_FIELDS: tuple[str, ...] = (
    "deterministic",
    "seed_requirements",
    "stateful",
    "batch_capable",
    "stream_capable",
    "supported_dtypes",
    "complexity",
    "backend",
    "surfaces",
    "golden_vectors",
    "benchmark",
    "docs",
    "version_introduced",
    "deprecation_state",
)


def _declared_block(spec: RuntimeCapabilitySpec) -> dict[str, Any]:
    """Only what this block actually states. `None` means "not said" and is omitted."""
    block: dict[str, Any] = {}
    for name in EMITTED_FIELDS:
        value = getattr(spec, name, None)
        if value is None:
            continue
        block[name] = list(value) if isinstance(value, tuple) else value
    return block


def build_manifest(engine_root: Path = DEFAULT_ENGINE_DIR) -> tuple[dict[str, Any], list[str]]:
    """(manifest payload, declared-but-not-contract-exported function names).

    `strict=True`: a block that does not parse or cross-validate raises rather than being
    written out as an absent declaration, because the surface cannot tell those apart.
    """
    manifest = build_capability_manifest(engine_root, strict=True)
    contract_functions = {
        module.import_path: {function.name for function in module.functions}
        for module in discover_runtime_library_modules(engine_root, executable_only=True)
    }

    modules: list[dict[str, Any]] = []
    unreachable: list[str] = []
    function_count = 0
    for module in sorted(manifest.modules, key=lambda item: item.import_path):
        exported = contract_functions.get(module.import_path)
        if exported is None:
            unreachable.extend(
                f"{module.import_path}.{spec.target}" for spec in module.functions
            )
            continue
        functions: list[dict[str, Any]] = []
        for spec in sorted(module.functions, key=lambda item: item.target):
            if spec.target not in exported:
                unreachable.append(f"{module.import_path}.{spec.target}")
                continue
            block = _declared_block(spec)
            if not block:
                # A block that states nothing this surface can carry is not a
                # declaration; `{"capability": {}}` would read as "declared, all silent".
                continue
            functions.append({"name": spec.target, "capability": block})
        if not functions:
            continue
        modules.append({"name": module.import_path, "functions": functions})
        function_count += len(functions)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "module_count": len(modules),
        "function_count": function_count,
        "modules": modules,
    }
    return payload, sorted(unreachable)


def _encoded(engine_root: Path) -> tuple[bytes, list[str]]:
    payload, unreachable = build_manifest(engine_root)
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return encoded, unreachable


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary_path, path)
    finally:
        Path(temporary_path).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, default=DEFAULT_ENGINE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    content, unreachable = _encoded(args.engine_root)
    if args.check:
        if not args.output.is_file():
            raise SystemExit(
                f"missing generated capability manifest: {args.output}. Run "
                "`make inventory-refresh`. Without it the SDK reports every declared "
                "capability field as UNDECLARED."
            )
        if args.output.read_bytes() != content:
            raise SystemExit(
                f"stale generated capability manifest: {args.output}. Run "
                "`make inventory-refresh`."
            )
        print(f"capability manifest OK: {args.output}")
        return 0
    _write_atomic(args.output, content)
    payload = json.loads(content)
    print(
        f"wrote {args.output}: {payload['function_count']} declared function(s) in "
        f"{payload['module_count']} module(s)."
    )
    if unreachable:
        print(
            f"note: {len(unreachable)} declared function(s) are not exported by the runtime "
            "contract, so the SDK cannot describe them: " + ", ".join(unreachable[:10])
            + (" ..." if len(unreachable) > 10 else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
