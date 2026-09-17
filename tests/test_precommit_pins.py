"""Config guard: ``.pre-commit-config.yaml`` must agree with the repo's real tool pins and scopes.

The hooks run on every developer machine, so they must use the SAME tool versions and cover the
SAME code that ``make lint`` / ``make format`` / ``make typecheck`` run with -- otherwise a commit
that passes the hooks fails ``make lint`` (or vice versa). Every expectation here is read from its
source of truth rather than hardcoded:

  * ``mojo_env/pixi.toml`` -- the ``ruff``, ``pydantic`` and ``types-redis`` pins;
  * ``Makefile`` -- the packages the ``lint`` / ``typecheck`` recipes pass to mypy;
  * ``pyproject.toml`` -- ``[tool.mypy] exclude`` (not honoured for files passed explicitly on the
    command line, which is how pre-commit invokes mypy, so the hook must repeat it).

mypy itself is pinned nowhere else in the repo (pixi.toml carries no mypy), so the mirrors-mypy
``rev`` is deliberately NOT derived from anything here -- bump it by hand.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_PRE_COMMIT = _ROOT / ".pre-commit-config.yaml"
_PIXI = _ROOT / "mojo_env" / "pixi.toml"
_MAKEFILE = _ROOT / "Makefile"
_PYPROJECT = _ROOT / "pyproject.toml"
_APPS = _ROOT / "apps"

_RUFF_REPO = "https://github.com/astral-sh/ruff-pre-commit"
_MYPY_REPO = "https://github.com/pre-commit/mirrors-mypy"


def _config() -> dict[str, Any]:
    loaded = yaml.safe_load(_PRE_COMMIT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), ".pre-commit-config.yaml must be a mapping"
    return loaded


def _repo(config: dict[str, Any], url: str) -> dict[str, Any]:
    matches = [r for r in config["repos"] if r.get("repo") == url]
    assert len(matches) == 1, f"expected exactly one repo entry for {url}, found {len(matches)}"
    return matches[0]


def _hook(repo: dict[str, Any], hook_id: str) -> dict[str, Any]:
    matches = [h for h in repo["hooks"] if h.get("id") == hook_id]
    assert len(matches) == 1, f"expected exactly one `{hook_id}` hook in {repo['repo']}"
    return matches[0]


def _pixi_pypi_pins() -> dict[str, str]:
    """``name -> exact version`` for every ``==``-pinned entry in ``[pypi-dependencies]``."""
    data = tomllib.loads(_PIXI.read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    for name, spec in data["pypi-dependencies"].items():
        version = spec["version"] if isinstance(spec, dict) else spec
        if isinstance(version, str) and version.startswith("=="):
            pins[name] = version[2:].strip()
    return pins


def _makefile_mypy_packages(target: str) -> list[str]:
    """The arguments of the ``mypy ...`` recipe line under ``<target>:`` in the Makefile."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    m = re.search(rf"^{re.escape(target)}:[^\n]*\n((?:\t[^\n]*\n)+)", text, re.MULTILINE)
    assert m, f"Makefile has no `{target}:` recipe"
    mypy_lines = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("mypy ")]
    assert len(mypy_lines) == 1, f"Makefile `{target}` must invoke mypy exactly once: {mypy_lines}"
    packages = [arg for arg in mypy_lines[0].split()[1:] if not arg.startswith("-")]
    assert packages, f"Makefile `{target}` mypy line names no packages"
    return packages


def test_lint_and_typecheck_type_check_the_same_packages() -> None:
    # The hook mirrors ONE scope; it can only do so if the Makefile's two mypy entry points agree.
    assert _makefile_mypy_packages("lint") == _makefile_mypy_packages("typecheck")


def test_install_hook_types_include_both_stages() -> None:
    # `pre-commit install` must wire the push-time hooks too, or `stages: [pre-push]` hooks never run.
    types = _config().get("default_install_hook_types")
    assert isinstance(types, list), "default_install_hook_types must be set explicitly"
    assert {"pre-commit", "pre-push"} <= set(types), types


def test_ruff_hook_rev_matches_pixi_pin() -> None:
    pins = _pixi_pypi_pins()
    assert "ruff" in pins, "mojo_env/pixi.toml must pin ruff exactly (`==`)"
    ruff_repo = _repo(_config(), _RUFF_REPO)
    assert ruff_repo["rev"] == f"v{pins['ruff']}", (
        f"ruff-pre-commit rev {ruff_repo['rev']} != pixi ruff pin {pins['ruff']} -- bump together"
    )
    hook_ids = {h["id"] for h in ruff_repo["hooks"]}
    assert {"ruff", "ruff-format"} <= hook_ids, hook_ids


def test_no_black_hook() -> None:
    # ruff is the only Python formatter (Makefile `format`); a black hook would fight ruff-format.
    for repo in _config()["repos"]:
        assert "psf/black" not in repo["repo"], repo["repo"]
        assert "black" not in {h["id"] for h in repo["hooks"]}, repo["repo"]


def test_mypy_hook_covers_exactly_the_makefile_packages() -> None:
    expected = {pkg.rstrip("/") for pkg in _makefile_mypy_packages("typecheck")}
    mypy_hook = _hook(_repo(_config(), _MYPY_REPO), "mypy")
    files_re = re.compile(mypy_hook["files"])

    covered: set[str] = set()
    for pkg_dir in sorted(p for p in _APPS.iterdir() if p.is_dir()):
        rel = pkg_dir.relative_to(_ROOT).as_posix()
        if files_re.search(f"{rel}/__init__.py"):
            covered.add(rel)
    assert covered == expected, (
        f"mypy hook `files` covers {sorted(covered)} but Makefile typecheck covers {sorted(expected)}"
    )
    for pkg in expected:
        assert (_ROOT / pkg).is_dir(), f"Makefile typecheck names a missing package: {pkg}"

    # Whole-scope mypy is a multi-minute run: it must never sit on the commit stage. Allowed
    # stages are push-time or manual (manual while `make typecheck` is red).
    stages = set(mypy_hook.get("stages", []))
    assert stages and stages <= {"pre-push", "manual"}, sorted(stages)


def test_mypy_hook_repeats_pyproject_excludes_inside_its_scope() -> None:
    # pyproject's [tool.mypy] exclude only applies to directory discovery, not to paths pre-commit
    # passes explicitly; every excluded dir that exists inside the hook's scope must be excluded
    # again on the hook.
    mypy_cfg = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["tool"]["mypy"]
    mypy_hook = _hook(_repo(_config(), _MYPY_REPO), "mypy")
    files_re = re.compile(mypy_hook["files"])
    exclude_re = re.compile(mypy_hook.get("exclude", "(?!)"))

    leaked: list[str] = []
    for pattern in mypy_cfg.get("exclude", []):
        needle = pattern.strip("/")
        for path in _APPS.rglob(needle):
            if not path.is_dir() or "node_modules" in path.parts:
                continue
            probe = f"{path.relative_to(_ROOT).as_posix()}/env.py"
            if files_re.search(probe) and not exclude_re.search(probe):
                leaked.append(probe)
    assert not leaked, f"pyproject [tool.mypy] excludes not repeated on the hook: {leaked}"


def test_mypy_hook_additional_dependencies_match_pixi_pins() -> None:
    pins = _pixi_pypi_pins()
    mypy_hook = _hook(_repo(_config(), _MYPY_REPO), "mypy")
    deps = mypy_hook.get("additional_dependencies", [])
    parsed: dict[str, str] = {}
    for dep in deps:
        name, sep, version = dep.partition("==")
        assert sep, f"mypy additional_dependencies must be exact pins (`name==version`): {dep!r}"
        parsed[name.strip()] = version.strip()
    assert set(parsed) == {"pydantic", "types-redis"}, sorted(parsed)
    for name, version in parsed.items():
        assert name in pins, f"mojo_env/pixi.toml must pin {name} exactly (`==`)"
        assert version == pins[name], (
            f"mypy hook {name}=={version} != pixi pin {pins[name]} -- bump together"
        )
