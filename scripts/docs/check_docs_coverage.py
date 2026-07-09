#!/usr/bin/env python3
"""Docs coverage gate — proves gitbook/ documents 100% of Algenta's external surface.

Derives the surface FROM SOURCE (never a hardcoded list — the dynamic-count rule) and fails
when any name is absent from ``gitbook/**/*.md``:

  * MCP tools            — ``apps/mcp_server/registry.py`` TOOLS keys
  * Python SDK methods   — ``packages/python-sdk/decision_engine/client_facade/_mixin_*.py`` public defs
  * TS SDK methods       — ``packages/ts-sdk/src/_client_class_methods_*.ts`` prototype assignments
  * ``de`` CLI commands  — the usage docstring of ``apps/cli/main/__init__.py`` (``de <cmd> [<sub>]`` lines)
  * ``algenta`` CLI      — dispatch table of ``packages/algenta/algenta/cli.py`` (``cmd == "…"``)
  * Connector types      — ``apps/api_server/services/connectors/schemas.py`` VALID_TYPES
  * LLM backends         — ``llm_provider_service/_config_lookup.py`` _SUPPORTED_PROVIDER_BACKENDS
  * OpenAPI paths        — ``schemas/openapi/openapi.yaml`` top-level paths
  * Error meanings       — ``gitbook/api/errors.md`` must have no undescribed ("—") rows

Usage:  python3 scripts/docs/check_docs_coverage.py [--json] [--category NAME]
Exit 0 = full coverage; 1 = gaps (each printed as ``category: name``).
Regression floors assert extraction itself didn't silently break.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITBOOK = ROOT / "gitbook"

# Extraction must never silently collapse — floors are minimums, derived counts are the truth.
FLOORS = {
    "mcp_tools": 130,
    "python_sdk_methods": 130,
    "ts_sdk_methods": 130,
    "de_cli_commands": 90,
    "algenta_cli_commands": 8,
    "connector_types": 20,
    "llm_backends": 9,
    "openapi_paths": 90,
    "runtime_library_modules": 400,
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ── extractors (source of truth) ──────────────────────────────────────────────────────────────────


def mcp_tools() -> set[str]:
    text = _read(ROOT / "apps/mcp_server/registry.py")
    body = text.split("TOOLS", 1)[1]
    return set(re.findall(r'^    "([a-z0-9_]+)":', body, re.MULTILINE))


def python_sdk_methods() -> set[str]:
    out: set[str] = set()
    for f in sorted((ROOT / "packages/python-sdk/decision_engine/client_facade").glob("_mixin_*.py")):
        out.update(re.findall(r"^    (?:async )?def ([a-z][a-z0-9_]*)\(", _read(f), re.MULTILINE))
    return out


def ts_sdk_methods() -> set[str]:
    out: set[str] = set()
    for f in sorted((ROOT / "packages/ts-sdk/src").glob("_client_class_methods_*.ts")):
        out.update(re.findall(r"prototype\.([A-Za-z0-9_]+)\s*=", _read(f)))
    return out


def de_cli_commands() -> set[str]:
    """``de <cmd> [<sub>]`` phrases from the CLI module's usage docstring (the source-embedded spec)."""
    mod = ast.parse(_read(ROOT / "apps/cli/main/__init__.py"))
    doc = ast.get_docstring(mod) or ""
    out: set[str] = set()
    for line in doc.splitlines():
        m = re.match(r"^\s*de ([a-z][a-z0-9-]*)(?: ([a-z][a-z0-9-]*))?", line)
        if m:
            out.add(("de " + m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip())
    return out


def algenta_cli_commands() -> set[str]:
    text = _read(ROOT / "packages/algenta/algenta/cli.py")
    cmds = set(re.findall(r'cmd == "([a-z-]+)"', text))
    cmds |= set(re.findall(r'cmd in \(([^)]*)\)', text) and {
        c.strip().strip('"\'') for grp in re.findall(r'cmd in \(([^)]*)\)', text) for c in grp.split(",")
    } or set())
    return {f"algenta {c}" for c in cmds if c and c != "help"}


def connector_types() -> set[str]:
    text = _read(ROOT / "apps/api_server/services/connectors/schemas.py")
    body = text.split("VALID_TYPES", 1)[1].split("}", 1)[0]
    return set(re.findall(r'"([a-z0-9_]+)"', body))


def llm_backends() -> set[str]:
    text = _read(ROOT / "apps/api_server/services/llm_provider_service/_config_lookup.py")
    body = text.split("_SUPPORTED_PROVIDER_BACKENDS", 1)[1].split(")", 1)[0]
    return set(re.findall(r'"([a-z0-9_]+)"', body))


def runtime_library_modules() -> set[str]:
    """Every runtime-library module the engine dispatches (``as _<module>__<function>``)."""
    text = _read(ROOT / "mojo/engine/runtime_library_dispatch_generated.mojo")
    mods: set[str] = set()
    for alias in re.findall(r"as _(\w+)", text):
        if "__" in alias:
            mods.add(alias.split("__", 1)[0])
    return mods


def openapi_paths() -> set[str]:
    text = _read(ROOT / "schemas/openapi/openapi.yaml")
    # top-level path keys under `paths:` — two-space indented, starting with /
    paths = set(re.findall(r"^  (/[^\s:]+):", text, re.MULTILINE))
    return {p for p in paths if not p.startswith("/mcp")}  # /mcp* deliberately excluded from docs pages


EXTRACTORS = {
    "mcp_tools": mcp_tools,
    "python_sdk_methods": python_sdk_methods,
    "ts_sdk_methods": ts_sdk_methods,
    "de_cli_commands": de_cli_commands,
    "algenta_cli_commands": algenta_cli_commands,
    "connector_types": connector_types,
    "llm_backends": llm_backends,
    "openapi_paths": openapi_paths,
    "runtime_library_modules": runtime_library_modules,
}


# ── matching ───────────────────────────────────────────────────────────────────────────────────────


def gitbook_corpus() -> str:
    parts = []
    for f in sorted(GITBOOK.rglob("*.md")):
        parts.append(_read(f))
    return "\n".join(parts)


def missing_names(corpus: str, category: str, names: set[str]) -> list[str]:
    out = []
    for name in sorted(names):
        if category in ("de_cli_commands", "algenta_cli_commands"):
            hit = name in corpus  # exact phrase, e.g. "de data connect" / "algenta login"
        elif category == "openapi_paths":
            hit = name in corpus
        else:
            hit = re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", corpus) is not None
        if not hit:
            out.append(name)
    return out


def undescribed_error_rows() -> list[str]:
    """Rows in the generated error table whose meaning is still the '—' placeholder."""
    errors_md = GITBOOK / "api" / "errors.md"
    if not errors_md.exists():
        return ["<gitbook/api/errors.md missing>"]
    out = []
    for line in _read(errors_md).splitlines():
        m = re.match(r"^\| `([a-z0-9_]+)` \| (—|-) \|", line)
        if m:
            out.append(m.group(1))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="dump extracted names per category")
    ap.add_argument("--category", help="limit to one category")
    args = ap.parse_args()

    extracted = {name: fn() for name, fn in EXTRACTORS.items()}

    if args.json:
        print(json.dumps({k: sorted(v) for k, v in extracted.items()}, indent=2))
        return 0

    failures = 0
    for cat, names in extracted.items():
        if args.category and cat != args.category:
            continue
        floor = FLOORS.get(cat, 1)
        if len(names) < floor:
            print(f"EXTRACTION BROKEN {cat}: found {len(names)} < floor {floor}")
            failures += 1
            continue
        corpus = gitbook_corpus()
        miss = missing_names(corpus, cat, names)
        status = "OK" if not miss else "MISSING"
        print(f"{cat}: {len(names) - len(miss)}/{len(names)} {status}")
        for name in miss:
            print(f"  {cat}: {name}")
        failures += len(miss)

    if not args.category:
        dash = undescribed_error_rows()
        print(f"error_meanings: {'OK' if not dash else f'{len(dash)} undescribed'}")
        for code in dash:
            print(f"  error_meanings: {code}")
        failures += len(dash)

    if failures:
        print(f"\nDOCS COVERAGE GAPS: {failures}")
        return 1
    print("\nDOCS COVERAGE: 100%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
