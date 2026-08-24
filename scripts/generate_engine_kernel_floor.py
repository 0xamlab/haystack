#!/usr/bin/env python3
"""The engine-kernel visibility floor — the ratchet that makes kernel removal loud.

``scripts/engine_kernel_floor.json`` lists every engine kernel the public contract
publishes, with its backend and families. The audit gate
(``scripts/audit_gap_checks.py``, ``engine_kernel_visibility``) fails if a floor entry ever
disappears from live discovery or loses a backend or a family — so a kernel can never
SILENTLY vanish from the published surface.

This script is the GROW side of the ratchet and deliberately nothing more: it adds entries
that live discovery publishes but the floor does not yet list, and it never removes or edits
anything. Removing a kernel from the public surface therefore requires a MANUAL edit of the
floor file — a loud, deliberate contract change, exactly the point of the ratchet.

Modes:
    (default)   write the grown floor in place
    --check     exit non-zero when the floor is missing published kernels (CI gate)
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime.mojo_inventory import (  # noqa: E402
    discover_engine_kernels,
    engine_kernels_payload,
)

FLOOR_PATH = ROOT / "scripts" / "engine_kernel_floor.json"


def live_kernel_entries() -> list[dict[str, Any]]:
    payload = engine_kernels_payload(discover_engine_kernels())
    return [dict(kernel) for kernel in payload["kernels"]]  # type: ignore[index]


def load_floor() -> dict[str, Any]:
    if not FLOOR_PATH.is_file():
        return {"schema": 1, "kernel_count": 0, "kernels": []}
    payload = json.loads(FLOOR_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise SystemExit(f"engine kernel floor {FLOOR_PATH} has an unsupported schema")
    kernels = payload.get("kernels")
    if not isinstance(kernels, list):
        raise SystemExit(f"engine kernel floor {FLOOR_PATH} is missing its kernels list")
    return payload


def _kernel_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry.get("module", "")), str(entry.get("name", "")))


def grow_floor(floor: dict[str, Any], live: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Add floor entries for live kernels the floor does not list yet. NEVER removes."""
    existing = {_kernel_key(entry) for entry in floor["kernels"]}
    grown = list(floor["kernels"])
    added: list[str] = []
    for entry in sorted(live, key=_kernel_key):
        if _kernel_key(entry) in existing:
            continue
        grown.append(
            {
                "name": entry["name"],
                "module": entry["module"],
                "backend": entry["backend"],
                "families": list(entry["families"]),
            }
        )
        added.append(f"{entry['module']}.{entry['name']}")
    grown.sort(key=_kernel_key)
    return {"schema": 1, "kernel_count": len(grown), "kernels": grown}, added


def _write_atomic(path: Path, content: bytes) -> None:
    fd, temporary_path = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(temporary_path, path)
    finally:
        Path(temporary_path).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    floor = load_floor()
    grown, added = grow_floor(floor, live_kernel_entries())

    if args.check:
        if added:
            listing = "\n".join(f"  + {name}" for name in added[:20])
            more = f"\n  … {len(added) - 20} more" if len(added) > 20 else ""
            raise SystemExit(
                "engine kernel floor is missing published kernels; grow it with "
                f"`python3 scripts/generate_engine_kernel_floor.py`:\n{listing}{more}"
            )
        print(f"engine kernel floor OK: {floor['kernel_count']} kernels")
        return 0

    if added:
        _write_atomic(
            FLOOR_PATH,
            (json.dumps(grown, indent=1, sort_keys=True) + "\n").encode("utf-8"),
        )
        print(f"grew engine kernel floor by {len(added)} kernel(s):")
        for name in added:
            print(f"  + {name}")
    else:
        print(f"engine kernel floor already current ({floor['kernel_count']} kernels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
