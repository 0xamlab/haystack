"""benchmarks/bench_tools.py -- the allowlist between operator env/CLI and a benchmark driver's argv.

The operator may only *select* a tool name; the executable that reaches argv[0] is one of the
mapping's literals resolved to an existing executable file (BENCH_BIN_DIR, then the driver's
literal fallbacks, then PATH). run_tool/popen_tool refuse anything this module did not resolve.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from benchmarks import bench_tools
from benchmarks.bench_tools import (
    BIN_DIR_ENV_VAR,
    SERVE_DRIVERS,
    TOOLS,
    ToolError,
    ToolNotFoundError,
    UnknownToolError,
    current_python,
    env_path,
    find_tool,
    popen_tool,
    run_tool,
    tool_from_env,
    tool_in_dir,
    tool_path,
)

A_TOOL = "qwen25_7b_p3_graph_cuda"  # any allowlisted name that is not on a developer's PATH


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """No BENCH_BIN_DIR, an empty PATH, a fresh registry -- every test states its own world."""
    monkeypatch.delenv(BIN_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(bench_tools, "_RESOLVED", set())
    yield


def _make_exe(directory: Path, name: str, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / name
    p.write_text(body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


# --------------------------------------------------------------------------- the allowlist itself


def test_tools_values_are_bare_file_names():
    for name, binary in TOOLS.items():
        assert binary, name
        assert os.sep not in binary and "/" not in binary, (name, binary)
        assert not binary.startswith("."), (name, binary)


def test_serve_drivers_are_a_subset_of_tools():
    assert SERVE_DRIVERS
    assert set(SERVE_DRIVERS) <= set(TOOLS)


@pytest.mark.parametrize("bad", ["", "sh", "../python3", "/bin/sh", "python3;", A_TOOL.upper()])
def test_unknown_name_is_refused_before_any_lookup(bad: str, tmp_path: Path):
    _make_exe(tmp_path, "sh")  # even if something by that file name exists
    with pytest.raises(UnknownToolError) as exc:
        find_tool(bad, search_dirs=(tmp_path,))
    assert "allowed names" in str(exc.value)
    assert isinstance(exc.value, ValueError)


# --------------------------------------------------------------------------- resolution order


def test_bench_bin_dir_is_searched_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    in_bin_dir = _make_exe(tmp_path / "bin", A_TOOL)
    _make_exe(tmp_path / "fallback", A_TOOL)
    on_path = _make_exe(tmp_path / "path", A_TOOL)
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "bin"))
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert tool_path(A_TOOL, search_dirs=(tmp_path / "fallback",)) == in_bin_dir


def test_search_dirs_beat_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    fallback = _make_exe(tmp_path / "fallback", A_TOOL)
    on_path = _make_exe(tmp_path / "path", A_TOOL)
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert tool_path(A_TOOL, search_dirs=(tmp_path / "fallback",)) == fallback


def test_path_is_the_last_resort(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    on_path = _make_exe(tmp_path / "path", A_TOOL)
    monkeypatch.setenv("PATH", str(on_path.parent))
    assert tool_path(A_TOOL) == on_path


def test_bench_bin_dir_takes_several_entries_and_tilde(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    second = _make_exe(tmp_path / "second", A_TOOL)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        BIN_DIR_ENV_VAR, os.pathsep.join(["", " ~/does-not-exist ", str(tmp_path / "second")])
    )
    assert bench_tools.bin_dirs() == [tmp_path / "does-not-exist", tmp_path / "second"]
    assert tool_path(A_TOOL) == second


def test_not_found_names_every_directory_searched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "bin"))
    with pytest.raises(ToolNotFoundError) as exc:
        tool_path(A_TOOL, search_dirs=(tmp_path / "fallback",))
    msg = str(exc.value)
    assert str(tmp_path / "bin") in msg and str(tmp_path / "fallback") in msg
    assert BIN_DIR_ENV_VAR in msg
    assert find_tool(A_TOOL) is None


# --------------------------------------------------------------------------- what counts as a hit


def test_non_executable_file_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    blob = tmp_path / "bin" / A_TOOL
    blob.parent.mkdir()
    blob.write_text("not a program")
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(blob.parent))
    assert find_tool(A_TOOL) is None
    assert tool_in_dir(blob.parent, A_TOOL) is None


def test_directory_named_like_the_binary_is_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    (tmp_path / "bin" / A_TOOL).mkdir(parents=True)
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "bin"))
    assert find_tool(A_TOOL) is None


def test_symlinks_are_kept_not_resolved(tmp_path: Path):
    """A venv's bin/python3 is a symlink whose location *is* the venv: resolving it would launch
    the base interpreter instead."""
    real = _make_exe(tmp_path / "real", "python3.14")
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python3").symlink_to(real)
    assert tool_in_dir(venv_bin, "python3") == venv_bin / "python3"


def test_paths_are_normalised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    exe = _make_exe(tmp_path / "bin", A_TOOL)
    monkeypatch.setenv(BIN_DIR_ENV_VAR, f"{tmp_path}/other/../bin")
    assert tool_path(A_TOOL) == exe


# --------------------------------------------------------------------------- env selection


def test_tool_from_env_selects_a_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    py = _make_exe(tmp_path / "venv", "python")
    py3 = _make_exe(tmp_path / "venv", "python3")
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "venv"))
    monkeypatch.setenv("SURV_BENCH_PYTHON", "python")
    assert tool_from_env("SURV_BENCH_PYTHON", "python3") == py
    monkeypatch.setenv("SURV_BENCH_PYTHON", "  ")
    assert tool_from_env("SURV_BENCH_PYTHON", "python3") == py3
    monkeypatch.delenv("SURV_BENCH_PYTHON")
    assert tool_from_env("SURV_BENCH_PYTHON", "python3") == py3


def test_tool_from_env_refuses_a_path_and_says_where_it_belongs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    py = _make_exe(tmp_path / "venv", "python3")
    monkeypatch.setenv("SURV_BENCH_PYTHON", str(py))
    with pytest.raises(UnknownToolError) as exc:
        tool_from_env("SURV_BENCH_PYTHON", "python3")
    assert BIN_DIR_ENV_VAR in str(exc.value)
    assert "SURV_BENCH_PYTHON" in str(exc.value)


def test_tool_from_env_refuses_an_unknown_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SURV_BENCH_PYTHON", "pypy")
    with pytest.raises(UnknownToolError):
        tool_from_env("SURV_BENCH_PYTHON", "python3")


def test_env_path_is_data_not_a_program(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SURV_DATA", "~/data/../data2")
    assert env_path("SURV_DATA", "/tmp/default") == str(tmp_path / "data2")
    monkeypatch.setenv("SURV_DATA", "   ")
    assert env_path("SURV_DATA", "/tmp/default") == "/tmp/default"
    monkeypatch.delenv("SURV_DATA")
    assert env_path("SURV_DATA", "/tmp/default") == "/tmp/default"


# --------------------------------------------------------------------------- the spawn chokepoint


def test_run_tool_refuses_anything_it_did_not_resolve(tmp_path: Path):
    stray = _make_exe(tmp_path, "stray")
    # Deliberately mixes ``Path`` and ``str``: the chokepoint has to refuse at run time whatever
    # the static type says, so the candidates are typed ``Any`` rather than narrowed to ``Path``.
    unresolved: tuple[Any, ...] = (stray, str(stray), Path(sys.executable), "python3")
    for bad in unresolved:
        with pytest.raises(ToolError, match="launch only executables resolved by bench_tools"):
            run_tool(bad, "-c", "pass")
        with pytest.raises(ToolError):
            popen_tool(bad, "-c", "pass")


def test_current_python_is_launchable_and_unresolved():
    py = current_python()
    assert py == Path(os.path.abspath(sys.executable))
    proc = run_tool(
        py,
        "-c",
        "import sys; print(sys.argv[1:])",
        "a b",
        Path("/x"),
        3,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "['a b', '/x', '3']"


def test_popen_tool_launches_a_resolved_tool():
    with popen_tool(
        current_python(), "-c", "print('ok')", stdout=bench_tools.subprocess.PIPE, text=True
    ) as proc:
        out, _ = proc.communicate(timeout=60)
    assert out.strip() == "ok" and proc.returncode == 0


def test_resolved_tool_from_bin_dir_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _make_exe(tmp_path / "bin", A_TOOL, '#!/bin/sh\necho "argv: $*"\n')
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "bin"))
    proc = run_tool(
        tool_path(A_TOOL),
        "--checkpoint",
        tmp_path / "ckpt",
        "--arm",
        "p3",
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == f"argv: --checkpoint {tmp_path / 'ckpt'} --arm p3"


def test_arguments_never_go_through_a_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _make_exe(tmp_path / "bin", A_TOOL, "#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    monkeypatch.setenv(BIN_DIR_ENV_VAR, str(tmp_path / "bin"))
    hostile = "$(touch pwned); rm -rf /; `id`"
    proc = run_tool(tool_path(A_TOOL), hostile, capture_output=True, text=True, cwd=tmp_path)
    assert proc.stdout.rstrip("\n") == hostile
    assert not (tmp_path / "pwned").exists()


# --------------------------------------------------------------------------- the drivers

DRIVE_SURVIVAL = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "external_baselines"
    / "survival_lifelines"
    / "drive_survival.py"
)


def test_drive_survival_imports_before_any_interpreter_is_resolved(monkeypatch: pytest.MonkeyPatch):
    """The lifelines interpreter is looked up on first use, never at import: a host with no python3
    in BENCH_BIN_DIR, /usr/local/bin or PATH can still import the driver and gets the allowlist's
    message from main(), not a traceback from the import line."""
    monkeypatch.syspath_prepend(str(DRIVE_SURVIVAL.parents[3] / "benchmarks"))  # as the driver does
    driver_tools = importlib.import_module("bench_tools")  # the module object the driver binds

    def no_interpreter_anywhere(*_args, **_kwargs):
        raise driver_tools.ToolNotFoundError("no interpreter on this host")

    monkeypatch.setattr(driver_tools, "tool_from_env", no_interpreter_anywhere)
    spec = importlib.util.spec_from_file_location("drive_survival_under_test", DRIVE_SURVIVAL)
    assert spec is not None and spec.loader is not None
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)  # must not touch the filesystem for an interpreter
    assert "survival_h2h" in TOOLS and driver.MOJO_TOOL == "survival_h2h"
    with pytest.raises(RuntimeError, match="no interpreter on this host"):
        driver.ref_python()
