#!/usr/bin/env python3
"""Dump the real algenta-mcp tool metadata into lab/data/algenta_mcp_tools.json.

Reads the published PyPI package's registry (pip install algenta-mcp==1.0.17)
and writes name + description + required-args for every registered tool. The
Space vendors the result so it never downloads anything at runtime.

    python scripts/dump_mcp_tools.py            # writes lab/data/algenta_mcp_tools.json
    python scripts/dump_mcp_tools.py --check    # exits non-zero if the vendored file drifts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "lab" / "data" / "algenta_mcp_tools.json"

# Integration tool-profile contract (contracts/integration-tool-contract.json in
# thyn-ai/algenta-integrations): which of the engine's MCP tools each profile
# exposes to the model. `full` = the entire registry.
PROFILE_TOOLS = {
    "observe": ["get_contract", "query_data", "simulate", "recommend"],
    "govern": [
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
    ],
    "execute": [
        "get_contract",
        "query_data",
        "simulate",
        "recommend",
        "plan_decision",
        "log_decision",
        "execute_decision",
    ],
}


def build() -> dict:
    from importlib.metadata import version as pkg_version

    from algenta_mcp.registry import TOOLS  # type: ignore

    pkg_version = pkg_version("algenta-mcp")

    tools = []
    for name in sorted(TOOLS):
        spec = TOOLS[name]["spec"]
        desc = (spec.get("description") or "").strip().replace("\n", " ")
        schema = spec.get("inputSchema") or {}
        tools.append(
            {
                "name": name,
                "description": desc,
                "required": list(schema.get("required", [])),
                "inputSchema": schema,
            }
        )
    return {
        "provenance": (
            f"Tool metadata read from the published algenta-mcp {pkg_version} PyPI "
            "package (algenta_mcp.registry.TOOLS). The Algenta engine itself is "
            "proprietary; this JSON is only the public MCP surface's names and "
            "descriptions, vendored so the Space shows the real registry."
        ),
        "package": "algenta-mcp",
        "package_version": pkg_version,
        "registry_entry": "io.github.thyn-ai/algenta",
        "n_tools": len(tools),
        "profile_tools": PROFILE_TOOLS,
        "tools": tools,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(build(), indent=1) + "\n"
    if args.check:
        if not OUT_PATH.exists() or OUT_PATH.read_text() != payload:
            print(
                "MISMATCH: vendored tool metadata does not match the installed package",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {OUT_PATH} matches installed algenta-mcp")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(payload)
    print(f"wrote {OUT_PATH} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
