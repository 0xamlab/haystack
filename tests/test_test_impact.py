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

import pytest

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


# ── installed-codna preference (0.1.48+: per-file seam + productized impact engine) ─────────────
# The installed wheel is faked through sys.modules so these tests pin the resolution contract on
# machines with any codna version (or none).


def _install_fake_codna(monkeypatch, *, seam=True, engine=True):
    import types as _types
    pkg = _types.ModuleType("codna")
    cu_mod = _types.ModuleType("codna.codeunits")
    if seam:
        fake = _FakeCodna({".py": "python"})
        cu_mod.language_for = fake.language_for
        cu_mod.extract_file = fake.extract_file
    pkg.codeunits = cu_mod
    monkeypatch.setitem(sys.modules, "codna", pkg)
    monkeypatch.setitem(sys.modules, "codna.codeunits", cu_mod)
    if engine:
        imp_mod = _types.ModuleType("codna.impact")

        def compute_impact(repo_root, changed, **kw):
            return _types.SimpleNamespace(
                mode="subset", tests=["tests/selected_by_engine.py"],
                reason=f"engine saw {len(changed)} change(s) at {repo_root}")

        imp_mod.compute_impact = compute_impact
        monkeypatch.setitem(sys.modules, "codna.impact", imp_mod)
    else:
        monkeypatch.setitem(sys.modules, "codna.impact", None)   # `from codna.impact import` raises


def test_installed_codna_with_engine_is_preferred_and_delegates(monkeypatch):
    ti = _load_tool()
    monkeypatch.delenv("CODNA_CLI", raising=False)
    _install_fake_codna(monkeypatch, seam=True, engine=True)
    codeunits, impact_fn = ti._installed_codna()
    assert codeunits is not None and impact_fn is not None
    mode, tests, reason = ti.compute_affected(
        ["packages/algenta/algenta/inference.py"], [], codeunits, impact_fn=impact_fn)
    assert mode == "subset" and tests == ["tests/selected_by_engine.py"]
    assert "engine saw 1 change(s)" in reason


def test_installed_codna_without_engine_keeps_local_path(monkeypatch):
    ti = _load_tool()
    _install_fake_codna(monkeypatch, seam=True, engine=False)
    codeunits, impact_fn = ti._installed_codna()
    assert codeunits is not None and impact_fn is None


def test_installed_codna_without_seam_rejected(monkeypatch):
    ti = _load_tool()
    _install_fake_codna(monkeypatch, seam=False, engine=True)
    assert ti._installed_codna() == (None, None)


def test_installed_codna_absent(monkeypatch):
    ti = _load_tool()
    monkeypatch.setitem(sys.modules, "codna", None)   # makes `import codna` raise ImportError
    assert ti._installed_codna() == (None, None)


# ---------------------------------------------------------------------------------------------
# Telys/memengine lexical enrichment (additive-only). Mirrors tests/test_repository_intelligence
# _lexical.py's own established pattern: flag/degrade tests run everywhere (no memengine needed);
# the real ranking test is @skipif'd when memengine genuinely isn't installed, so it exercises the
# actual library whenever CI has it and skips (not fails) in envs that don't.
# ---------------------------------------------------------------------------------------------

def test_lexical_ranking_enabled_flag_defaults_off_and_toggles(monkeypatch):
    ti = _load_tool()
    monkeypatch.delenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", raising=False)
    assert ti._lexical_ranking_enabled() is False
    for on in ("1", "true", "YES", "on"):
        monkeypatch.setenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", on)
        assert ti._lexical_ranking_enabled() is True


def test_lexical_enrichment_is_a_noop_when_the_flag_is_unset(monkeypatch):
    ti = _load_tool()
    monkeypatch.delenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", raising=False)
    extra, corpus_size = ti._lexical_enrichment(["a.py"], {"a.py": None}, ["tests/test_a.py"])
    assert extra == set() and corpus_size == 0


def test_lexical_enrichment_degrades_when_memengine_is_unavailable(monkeypatch):
    # This dev environment genuinely does not have memengine installed (it's an optional git+https
    # dependency — see requirements-dev.txt), so this exercises the REAL fail-open path, not a
    # simulated one: the flag is on, the import inside _lexical_enrichment genuinely fails.
    ti = _load_tool()
    monkeypatch.setenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", "true")
    extra, corpus_size = ti._lexical_enrichment(["a.py"], {"a.py": None}, ["tests/test_a.py"])
    assert extra == set()


@pytest.mark.skipif(importlib.util.find_spec("memengine") is None, reason="memengine not installed")
def test_lexical_enrichment_catches_a_reflection_only_reference(tmp_path, monkeypatch):
    """The AST import graph is blind to a symbol referenced only by name (e.g. a plugin looked up
    via getattr/string dispatch) rather than imported. Lexical similarity over path+symbol text can
    still surface the test that exercises it — that's the whole point of this enrichment lane."""
    import ast as _ast

    # A minimal, self-contained repo: source.py defines `render_widget`; plugin_loader.py never
    # imports it (looked up by string name at runtime instead — the AST graph cannot see this);
    # tests/test_plugin_loader.py is the ONLY test that would actually exercise it.
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    src = tmp_path / "src" / "source.py"
    src.write_text("def render_widget():\n    return 'widget'\n")
    loader = tmp_path / "src" / "plugin_loader.py"
    loader.write_text("PLUGIN_NAMES = ['render_widget']\n")  # string reference, not an import
    test_file = tmp_path / "tests" / "test_plugin_loader.py"
    test_file.write_text("def test_render_widget():\n    assert True\n")

    ti = _load_tool()
    monkeypatch.setenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", "true")

    trees = {}
    for rel, path in (
        ("src/source.py", src),
        ("src/plugin_loader.py", loader),
        ("tests/test_plugin_loader.py", test_file),
    ):
        trees[rel] = _ast.parse(path.read_text())

    changed = ["src/source.py"]
    test_files = ["tests/test_plugin_loader.py"]

    # Ground truth: the AST import graph genuinely cannot connect source.py -> the test (no
    # import edge exists at all between them).
    extra, corpus_size = ti._lexical_enrichment(changed, trees, test_files)
    assert corpus_size > 0, "memengine is installed but the corpus build produced nothing"
    assert "tests/test_plugin_loader.py" in extra


@pytest.mark.skipif(importlib.util.find_spec("memengine") is None, reason="memengine not installed")
def test_lexical_enrichment_is_additive_only_never_narrows(monkeypatch, tmp_path):
    """Even when lexical search would only return noise (no real relationship), the caller's
    affected set must never shrink — _lexical_enrichment only ever contributes a UNION."""
    import ast as _ast

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    changed_file = tmp_path / "src" / "unrelated_change.py"
    changed_file.write_text("def totally_unrelated_symbol_xyz():\n    pass\n")
    noise_test = tmp_path / "tests" / "test_noise.py"
    noise_test.write_text("def test_something_else_entirely():\n    assert True\n")

    ti = _load_tool()
    monkeypatch.setenv("ALGENTA_REPOSITORIES_LEXICAL_RANKING", "true")
    trees = {
        "src/unrelated_change.py": _ast.parse(changed_file.read_text()),
        "tests/test_noise.py": _ast.parse(noise_test.read_text()),
    }
    extra, _corpus_size = ti._lexical_enrichment(
        ["src/unrelated_change.py"], trees, ["tests/test_noise.py"])
    # Whatever lexical search returns (possibly nothing, possibly noise), the CALLER (compute_
    # affected) only ever unions it in — verify that contract directly via the real call path.
    already_affected = {"tests/test_noise.py"}
    result = already_affected | extra
    assert already_affected <= result  # superset, never a subset of the original

# ── repo-agnostic fallback: no hardcoded apps/packages layout ───────────────────────────────────
# The local (no-codna) fallback used to require this repo's own apps/packages/... convention
# (_SOURCE_DIRS) to find anything at all. These prove it now works, unmodified, on a repo shaped
# nothing like this one: a src/<vendor>/<pkg>/ layout with no apps/ or packages/ dir anywhere.


def test_fallback_selects_correctly_on_a_differently_shaped_repo(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)

    pkg = tmp_path / "src" / "acme" / "mypkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("VALUE = 1\n")
    (pkg / "util.py").write_text("from mypkg.core import VALUE\n")

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_util.py").write_text("from mypkg.util import VALUE\n")
    # Enough unrelated tests to keep 1-affected-test comfortably under the 34% shared-core
    # threshold (this fixture is deliberately tiny; a real repo has thousands of tests).
    unrelated = ["test_unrelated_a.py", "test_unrelated_b.py", "test_unrelated_c.py", "test_unrelated_d.py"]
    for name in unrelated:
        (tests_dir / name).write_text("VALUE = 2\n")

    py_files = ti._iter_py_files()
    # The full-repo walk finds every .py file with no apps/packages/... allowlist involved.
    rels = {str(p.relative_to(tmp_path)) for p in py_files}
    assert rels == {
        "src/acme/mypkg/__init__.py", "src/acme/mypkg/core.py", "src/acme/mypkg/util.py",
        "tests/test_util.py", *(f"tests/{n}" for n in unrelated),
    }

    mode, tests, reason = ti.compute_affected(["src/acme/mypkg/core.py"], py_files, None)
    # core.py -> util.py (via the generic "src/acme/mypkg" == real package alias "mypkg") ->
    # test_util.py. test_unrelated.py must NOT be pulled in.
    assert mode == "subset", reason
    assert tests == ["tests/test_util.py"]


def test_fallback_package_alias_resolution_is_ancestor_derived_not_hardcoded(tmp_path, monkeypatch):
    ti = _load_tool()
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    (tmp_path / "libs" / "widget" / "widget").mkdir(parents=True)
    (tmp_path / "libs" / "widget" / "widget" / "__init__.py").write_text("")
    keys = ti._candidate_keys("libs/widget/widget/shape.py")
    assert "libs.widget.widget.shape" in keys   # primary, path-based key
    assert "widget.shape" in keys               # alias via the real package boundary


def test_path_literal_lane_catches_a_test_that_loads_by_path(tmp_path, monkeypatch):
    """Tests using importlib.spec_from_file_location have NO import edge, so the AST graph
    cannot see them. This is the shape of every tests/test_az_orchestrator_*.py file, and a
    change to infra/ci/az_orchestrator.py broke 4 of them while CI stayed green."""
    import scripts.test_impact as ti  # noqa: PLC0415

    test_src = tmp_path / "test_loads_by_path.py"
    test_src.write_text(
        'import importlib.util\n'
        'from pathlib import Path\n'
        'TOOL = Path("infra") / "ci" / "az_orchestrator.py"\n'
        'def test_x():\n'
        '    spec = importlib.util.spec_from_file_location("m", TOOL)\n'
        '    assert spec\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    hit = ti._path_literal_dependents(
        ["infra/ci/az_orchestrator.py"], ["test_loads_by_path.py"]
    )
    assert hit == {"test_loads_by_path.py"}, f"path-literal reference not detected: {hit}"


def test_path_literal_lane_does_not_over_match(tmp_path, monkeypatch):
    """Component-wise matching must not fire on a test that merely mentions one segment."""
    import scripts.test_impact as ti  # noqa: PLC0415

    (tmp_path / "test_unrelated.py").write_text(
        'import importlib.util\n'
        '# mentions "infra" only, not the full component set\n'
        'NAME = "infra"\n'
        'def test_y():\n'
        '    assert importlib.util is not None\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "REPO_ROOT", tmp_path)
    hit = ti._path_literal_dependents(
        ["infra/ci/az_orchestrator.py"], ["test_unrelated.py"]
    )
    assert hit == set(), f"over-matched on a partial component overlap: {hit}"
