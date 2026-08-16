"""Tests for scripts/test_impact.py (repo-aware test selection / test-impact analysis).

These cover the pure selection logic (fast, no repo walk) plus one subprocess integration check
that the CLI's conservative fallbacks behave. The tool biases to running MORE tests, never fewer,
so every assertion here checks a guarantee, not a heuristic guess.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "scripts" / "test_impact.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("test_impact_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_key_strips_init_and_suffix():
    ti = _load_tool()
    assert ti._module_key("apps/api_server/routers/auth.py") == "apps.api_server.routers.auth"
    assert ti._module_key("packages/algenta/algenta/__init__.py") == "packages.algenta.algenta"
    assert ti._module_key("not_python.txt") is None


def test_candidate_keys_includes_importable_package_name():
    ti = _load_tool()
    keys = ti._candidate_keys("packages/algenta/algenta/inference.py")
    assert "packages.algenta.algenta.inference" in keys
    # The form tests actually import:
    assert "algenta.inference" in keys


def test_is_test_and_broad():
    ti = _load_tool()
    assert ti._is_test("tests/test_foo.py")
    assert ti._is_test("tests/unit/test_bar.py")
    assert not ti._is_test("apps/api_server/routers/auth.py")
    assert ti._is_broad("pyproject.toml")
    assert ti._is_broad(".github/workflows/ci.yml")
    assert not ti._is_broad("apps/api_server/routers/auth.py")


def test_cli_changed_test_file_returns_itself():
    # Single subprocess smoke test (the tool rebuilds the whole import graph per run, so this is
    # deliberately the ONLY subprocess test -- the fallbacks above are covered by the pure-logic
    # tests, which are fast).
    out = subprocess.run(
        [sys.executable, str(_TOOL), "--changed", "tests/test_test_impact.py", "--json"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["mode"] == "subset"
    assert "tests/test_test_impact.py" in data["tests"]


def test_cli_broad_change_runs_full_suite():
    out = subprocess.run(
        [sys.executable, str(_TOOL), "--changed", "pyproject.toml", "--json"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["mode"] == "all"


# ── codna-backed multi-language fast path ────────────────────────────────────────────────────────
# codna is injected as a duck-typed stand-in (language_for / extract_file), so these tests pin the
# SELECTION CONTRACT without needing a codna checkout installed.


class _Unit:
    def __init__(self, symbol_type):
        self.symbol_type = symbol_type


class _FakeCodna:
    def __init__(self, lang_by_ext, test_paths=()):
        self.lang_by_ext = lang_by_ext
        self.test_paths = set(test_paths)

    def language_for(self, rel):
        import os
        return self.lang_by_ext.get(os.path.splitext(rel)[1])

    def extract_file(self, repo_id, rel, source):
        if rel in self.test_paths:
            return [_Unit("test")]
        return [_Unit("function")]


def test_disjoint_ts_only_change_selects_nothing(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)   # the fast path reads the changed files
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "App.tsx").write_text("export const App = () => null;\n")
    (tmp_path / "apps" / "web" / "util.ts").write_text("export function f() { return 1; }\n")
    fake = _FakeCodna({".ts": "typescript", ".tsx": "tsx"})
    mode, tests, reason = ti.compute_affected(
        ["apps/web/App.tsx", "apps/web/util.ts"], [], fake)
    assert mode == "subset" and tests == []
    assert "non-Python languages" in reason


def test_disjoint_skipped_when_other_language_test_changed(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "util.test.ts").write_text("test('f', () => {});\n")
    fake = _FakeCodna({".ts": "typescript"}, test_paths={"apps/web/util.test.ts"})
    mode, _, reason = ti.compute_affected(["apps/web/util.test.ts"], [], fake)
    assert mode == "all"   # a test in another language -> we cannot select for it -> full suite


def test_disjoint_skipped_for_mixed_python_change(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "App.tsx").write_text("export const App = () => null;\n")
    fake = _FakeCodna({".ts": "typescript", ".py": "python"})
    mode, _, _ = ti.compute_affected(
        ["apps/api_server/routers/auth.py", "apps/web/App.tsx"], [], fake)
    assert mode == "all"   # Python in the diff -> graph path; TS not placeable -> conservative


def test_disjoint_skipped_for_unclassifiable_extension(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    (tmp_path / "apps" / "web").mkdir(parents=True)
    (tmp_path / "apps" / "web" / "x.ts").write_text("export const x = 1;\n")
    fake = _FakeCodna({".ts": "typescript"})   # no entry for .sql
    mode, _, _ = ti.compute_affected(["apps/web/x.ts", "migrations/0001.sql"], [], fake)
    assert mode == "all"


def test_no_codna_non_python_change_runs_all():
    ti = _load_tool()
    # one real indexed test file so the graph path reaches changed-file validation
    py_files = [ti.REPO_ROOT / "tests" / "test_test_impact.py"]
    mode, _, reason = ti.compute_affected(["apps/web/App.tsx"], py_files, None)
    assert mode == "all"
    assert "non-Python change" in reason


def test_load_codna_rejects_missing_or_old_codna(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.delenv("CODNA_CLI", raising=False)
    assert ti._load_codna(None) is None
    assert ti._load_codna(str(tmp_path / "does-not-exist")) is None
    # A checkout whose codeunits lacks the per-file seam (pre-#445) must be rejected, not used.
    pkg = tmp_path / "oldcodna" / "codna"
    pkg.mkdir(parents=True)
    (pkg / "codeunits.py").write_text("def registered_languages():\n    return ()\n")
    (tmp_path / "oldcodna" / "codna" / "__init__.py").write_text("")
    assert ti._load_codna(str(tmp_path / "oldcodna")) is None
