from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs" / "check_docs_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_docs_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mcp_coverage_uses_published_registry() -> None:
    coverage = _load_module()

    tools = coverage.mcp_tools()

    assert "get_contract" in tools
    assert "list_runtime_libraries" not in tools
    assert "execute_runtime_library" not in tools


def test_cli_coverage_excludes_internal_runtime_lifecycle() -> None:
    coverage = _load_module()

    commands = coverage.de_cli_commands()

    assert "de health" in commands
    assert not any(command.startswith("de runtime") for command in commands)
    assert "algenta_cli_commands" not in coverage.EXTRACTORS
