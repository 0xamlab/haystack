from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _import_from_path(package_root: Path, module_name: str):
    sys.path.insert(0, str(package_root))
    try:
        return importlib.import_module(module_name)
    finally:
        sys.path.pop(0)


def test_capability_plane_contract_inventory_stays_aligned_across_generated_surfaces() -> None:
    manifest = json.loads((ROOT / "apps" / "docs" / "integration_manifest.v1.json").read_text())
    manifest_plane = manifest["capability_plane"]

    python_contract = _import_from_path(
        ROOT / "packages" / "python-sdk",
        "decision_engine._contract",
    )
    python_plane = python_contract.CAPABILITY_PLANE_CONTRACT

    typescript_contract = (ROOT / "packages" / "ts-sdk" / "src" / "contract.ts").read_text(
        encoding="utf-8"
    )

    expected_execution_owners = ["algenta_managed", "client_managed"]
    expected_direct_methods = {
        "typescript": {
            "route_capabilities_method": "routeCapabilities",
            "execute_capability_method": "executeCapability",
        }
    }
    expected_mcp_tools = {
        "route_capabilities_tool": "route_capabilities",
        "execute_capability_tool": "execute_capability",
    }

    for plane in (manifest_plane, python_plane):
        assert plane["enums"]["execution_owners"] == expected_execution_owners
        assert plane["direct_sdk"]["typescript"]["route_capabilities_method"] == expected_direct_methods["typescript"]["route_capabilities_method"]
        assert plane["direct_sdk"]["typescript"]["execute_capability_method"] == expected_direct_methods["typescript"]["execute_capability_method"]
        assert plane["mcp"]["route_capabilities_tool"] == expected_mcp_tools["route_capabilities_tool"]
        assert plane["mcp"]["execute_capability_tool"] == expected_mcp_tools["execute_capability_tool"]

    assert '"execution_owners": [' in typescript_contract
    assert '"algenta_managed"' in typescript_contract
    assert '"client_managed"' in typescript_contract
    assert '"route_capabilities_method": "routeCapabilities"' in typescript_contract
    assert '"execute_capability_method": "executeCapability"' in typescript_contract
    assert '"route_capabilities_tool": "route_capabilities"' in typescript_contract
    assert '"execute_capability_tool": "execute_capability"' in typescript_contract
