from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs" / "check_engine_domain_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_engine_domain_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_real_modules_loads_the_live_contract() -> None:
    coverage = _load_module()

    modules = coverage.real_modules()

    assert len(modules) >= 600
    assert "optimization.linear" in modules


def test_module_table_credits_only_the_first_cell() -> None:
    coverage = _load_module()

    # `crc32_combine` is a function belonging to `crypto.crc32`, named in the description
    # column -- it must NOT be read as a second module claim (the bug this guard was fixed for).
    text = (
        "| Module | What it does |\n"
        "| --- | --- |\n"
        "| `crypto.crc32` | checksums, plus `crc32_combine` for two pieces hashed separately |\n"
    )

    tokens = coverage._module_table_first_cells(text)

    assert tokens == {"crypto.crc32"}


def test_non_module_tables_are_ignored() -> None:
    coverage = _load_module()

    # Same shape of content (module-like backtick tokens on table rows) but under headers this
    # corpus actually uses for non-module tables -- must contribute nothing.
    text = (
        "| Status | Name | What it means |\n"
        "| --- | --- | --- |\n"
        "| 360 | `ok` | the result is present |\n"
        "\n"
        "| Entry point | Use when | Cost |\n"
        "| --- | --- | --- |\n"
        "| `execute_batch` | many independent calls | one frame per shard |\n"
    )

    tokens = coverage._module_table_first_cells(text)

    assert tokens == set()


def test_check_flags_a_fabricated_module_reference(tmp_path, monkeypatch) -> None:
    coverage = _load_module()

    gitbook_engine = tmp_path / "gitbook" / "engine"
    gitbook_engine.mkdir(parents=True)
    (gitbook_engine / "example.md").write_text(
        "| Module | What it does |\n"
        "| --- | --- |\n"
        "| `crypto.crc32` | real |\n"
        "| `crypto.does_not_exist_anymore` | fabricated |\n",
        encoding="utf-8",
    )
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"modules": [{"name": "crypto.crc32"}]}), encoding="utf-8")

    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    monkeypatch.setattr(coverage, "GITBOOK_ENGINE", gitbook_engine)
    monkeypatch.setattr(coverage, "CONTRACT", contract)

    result = coverage.check()

    assert result["stale_references"] == {"gitbook/engine/example.md": ["crypto.does_not_exist_anymore"]}


def test_check_passes_clean_when_every_reference_is_real(tmp_path, monkeypatch) -> None:
    coverage = _load_module()

    gitbook_engine = tmp_path / "gitbook" / "engine"
    gitbook_engine.mkdir(parents=True)
    (gitbook_engine / "example.md").write_text(
        "| Module | What it does |\n| --- | --- |\n| `crypto.crc32` | real |\n",
        encoding="utf-8",
    )
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"modules": [{"name": "crypto.crc32"}]}), encoding="utf-8")

    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    monkeypatch.setattr(coverage, "GITBOOK_ENGINE", gitbook_engine)
    monkeypatch.setattr(coverage, "CONTRACT", contract)

    result = coverage.check()

    assert result["stale_references"] == {}
    assert result["narrative_documented_count"] == 1


def test_non_narrative_pages_are_excluded_even_with_real_module_names(tmp_path, monkeypatch) -> None:
    coverage = _load_module()

    gitbook_engine = tmp_path / "gitbook" / "engine"
    gitbook_engine.mkdir(parents=True)
    # A generated catalog page listing a module with zero narrative prose around it.
    (gitbook_engine / "runtime-library-catalog.md").write_text(
        "| Module | What it does |\n| --- | --- |\n| `crypto.crc32` | auto-generated row |\n",
        encoding="utf-8",
    )
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"modules": [{"name": "crypto.crc32"}]}), encoding="utf-8")

    monkeypatch.setattr(coverage, "ROOT", tmp_path)
    monkeypatch.setattr(coverage, "GITBOOK_ENGINE", gitbook_engine)
    monkeypatch.setattr(coverage, "CONTRACT", contract)

    result = coverage.check()

    assert result["narrative_documented_count"] == 0
    assert result["undocumented_by_narrative"] == ["crypto.crc32"]
