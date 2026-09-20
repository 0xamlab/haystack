"""Benchmark-driver executables: an allowlist of names, resolved to vetted paths, launched here.

Every benchmark driver in this repository launches the programs an operator can select -- the
reference interpreters, third-party engines and the binaries built from its Mojo sources -- through
this module. It sits between the operator's environment / command line and ``subprocess`` the way
``apps/runtime/worker_launch.py`` sits between the daemon's env vars and the worker's argv:

* :data:`TOOLS` is the literal allowlist -- tool *name* -> the literal file name of its binary. An
  operator can only ever **select** one of these names (``SURV_BENCH_PYTHON=python3``,
  ``--driver qwen3_serve_batched_cuda``); the string that ends up in ``argv[0]`` is always one of
  the mapping's own literals, resolved to an existing executable file. The operator's string never
  becomes the executable, so a value such as ``../../bin/sh`` is refused by name, not by pattern.
* :data:`BIN_DIR_ENV_VAR` (``BENCH_BIN_DIR``) is where locally built binaries live: an
  ``os.pathsep``-separated list of directories searched before ``PATH``. It replaces the
  per-driver ``--binary /some/path`` / ``--driver /some/path`` overrides -- the operator points at
  the build directory, the driver knows the binary's name.
* :func:`run_tool` / :func:`popen_tool` are the only spawn points for those executables. They
  refuse an executable this module did not resolve, so ``subprocess.run([args.binary, ...])``
  cannot come back by accident, and a binary a driver has just built is launched only once
  :func:`tool_in_dir` has admitted it. Everything after the executable is data: separate ``execve``
  argv elements, never a shell. A driver's build step (``pixi run mojo build``) and host inventory
  (``git``, ``nvidia-smi``) have a literal ``argv[0]`` and stay on ``subprocess`` directly.

Resolution order for a name: each ``BENCH_BIN_DIR`` entry, then the caller's literal
``search_dirs``, then ``PATH``. A candidate counts only if it is an existing regular file with the
executable bit; paths are normalised with :func:`os.path.abspath` but symlinks are deliberately not
followed -- a virtualenv's ``bin/python3`` is a symlink whose *location* is what makes it that venv.

Stdlib only, no engine imports: the ``nvidia_race`` drivers are copied to a GPU box and run
standalone with this file placed beside them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "BIN_DIR_ENV_VAR",
    "SERVE_DRIVERS",
    "TOOLS",
    "ToolError",
    "ToolNotFoundError",
    "UnknownToolError",
    "bin_dirs",
    "current_python",
    "env_path",
    "find_tool",
    "popen_tool",
    "run_tool",
    "tool_from_env",
    "tool_in_dir",
    "tool_path",
]

BIN_DIR_ENV_VAR = "BENCH_BIN_DIR"

# name -> literal binary file name. Keys are what operators and drivers say; values are the only
# strings that ever reach argv[0]. Binaries built from this repository's Mojo sources are named
# after their source stem; keep the two in step when a driver source is added.
TOOLS: dict[str, str] = {
    # interpreters
    "python": "python",
    "python3": "python3",
    # third-party engines
    "llama-server": "llama-server",
    # benchmarks/llm_smoke/conform_generate_cuda.mojo
    "conform_generate_cuda": "conform_generate_cuda",
    # benchmarks/external_baselines/graph_betweenness_h2h.mojo
    "graph_betweenness_h2h": "graph_betweenness_h2h",
    # benchmarks/mojo_benchmarks/measure_exactnum_strd.mojo
    "measure_exactnum_strd": "measure_exactnum_strd",
    # benchmarks/llm_smoke/nvidia_race/qwen25_7b_p3_graph_cuda.mojo, and four_way_race.py's
    # tensor-core build of the same source
    "qwen25_7b_p3_graph_cuda": "qwen25_7b_p3_graph_cuda",
    "qwen25_7b_p3_graph_cuda_tc_b1_ns": "qwen25_7b_p3_graph_cuda_tc_b1_ns",
    # benchmarks/llm_smoke/nvidia_race/qwen3_serve*.mojo -- the JSON-lines serve drivers
    "qwen3_serve_cuda": "qwen3_serve_cuda",
    "qwen3_serve_batched_cuda": "qwen3_serve_batched_cuda",
    # benchmarks/external_baselines/survival_lifelines/survival_h2h.mojo
    "survival_h2h": "survival_h2h",
}

# The subset of TOOLS that speak enterprise_bench.py's JSON-lines protocol (ttft_probe --driver).
SERVE_DRIVERS: tuple[str, ...] = ("qwen3_serve_cuda", "qwen3_serve_batched_cuda")


class ToolError(RuntimeError):
    """Base class: a benchmark executable could not be selected, found or launched."""


class UnknownToolError(ToolError, ValueError):
    """The requested name is not in :data:`TOOLS` (or was a path, which is never accepted)."""


class ToolNotFoundError(ToolError):
    """The name is allowed but no executable file for it exists in any searched directory."""


# Every Path handed out by this module. run_tool/popen_tool launch nothing else.
_RESOLVED: set[Path] = set()


def _binary_for(name: str) -> str:
    """The literal binary file name for an allowlisted *name*.

    Selection is by comparison while iterating the literal mapping: the returned string is one of
    the mapping's own values, chosen by *name*, never *name* itself or anything derived from it.
    """
    for allowed, binary in TOOLS.items():
        if allowed == name:
            return binary
    raise UnknownToolError(
        f"{name!r} is not an allowlisted benchmark tool; allowed names: {', '.join(sorted(TOOLS))}"
    )


def bin_dirs() -> list[Path]:
    """The operator's ``BENCH_BIN_DIR`` entries (``os.pathsep``-separated), blanks dropped."""
    raw = os.environ.get(BIN_DIR_ENV_VAR) or ""
    out: list[Path] = []
    for entry in raw.split(os.pathsep):
        entry = entry.strip()
        if entry:
            out.append(Path(os.path.abspath(os.path.expanduser(entry))))
    return out


def _register(path: Path) -> Path:
    _RESOLVED.add(path)
    return path


def _executable_at(directory: str | os.PathLike[str], binary: str) -> Path | None:
    candidate = Path(os.path.abspath(os.path.join(os.path.expanduser(directory), binary)))
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def tool_in_dir(directory: str | os.PathLike[str], name: str) -> Path | None:
    """The allowlisted tool *name* if (and only if) it is an executable file in *directory*."""
    found = _executable_at(directory, _binary_for(name))
    return _register(found) if found is not None else None


def find_tool(name: str, *, search_dirs: Iterable[str | os.PathLike[str]] = ()) -> Path | None:
    """Resolve an allowlisted *name* to an executable path, or ``None`` when nothing matches.

    Order: ``BENCH_BIN_DIR`` entries, then *search_dirs* (literal, driver-specific fallbacks),
    then ``PATH``. Raises :class:`UnknownToolError` for a name outside :data:`TOOLS`.
    """
    binary = _binary_for(name)
    for directory in (*bin_dirs(), *search_dirs):
        found = _executable_at(directory, binary)
        if found is not None:
            return _register(found)
    on_path = shutil.which(binary)
    if on_path:
        return _register(Path(os.path.abspath(on_path)))
    return None


def tool_path(name: str, *, search_dirs: Iterable[str | os.PathLike[str]] = ()) -> Path:
    """:func:`find_tool`, but a miss raises :class:`ToolNotFoundError` naming every searched dir."""
    dirs = list(search_dirs)
    found = find_tool(name, search_dirs=dirs)
    if found is None:
        searched = [str(d) for d in (*bin_dirs(), *dirs)]
        where = f" in {', '.join(searched)} or" if searched else " on"
        raise ToolNotFoundError(
            f"no executable {_binary_for(name)!r} for tool {name!r}{where} PATH; build it into a "
            f"directory listed in {BIN_DIR_ENV_VAR}"
        )
    return found


def tool_from_env(
    var: str, default: str, *, search_dirs: Iterable[str | os.PathLike[str]] = ()
) -> Path:
    """Resolve the tool whose allowlisted *name* is in env var *var* (blank/unset -> *default*).

    The variable selects a name; it does not carry a path. A value with a path separator gets a
    message that says where the directory belongs instead of a bare allowlist rejection.
    """
    raw = (os.environ.get(var) or "").strip()
    name = raw or default
    if os.sep in name or (os.altsep and os.altsep in name):
        raise UnknownToolError(
            f"{var} selects a tool name from the allowlist ({', '.join(sorted(TOOLS))}), not a "
            f"path: {raw!r}. Put the directory that holds the binary in {BIN_DIR_ENV_VAR} instead."
        )
    return tool_path(name, search_dirs=search_dirs)


def current_python() -> Path:
    """The running interpreter as a launchable tool (the one program no allowlist needs to name)."""
    return _register(Path(os.path.abspath(sys.executable)))


def env_path(var: str, default: str) -> str:
    """An operator-supplied *data* path from env var *var*: expanded, absolute; blank -> *default*.

    For files and directories a driver reads or writes (datasets, dump roots, build outputs).
    Never for the program to run -- that is :func:`tool_from_env`.
    """
    raw = (os.environ.get(var) or "").strip() or default
    return os.path.abspath(os.path.expanduser(raw))


def _argv(tool: Path, args: tuple[object, ...]) -> list[str]:
    if not isinstance(tool, Path) or tool not in _RESOLVED:
        raise ToolError(
            "run_tool/popen_tool launch only executables resolved by bench_tools "
            f"(tool_path, tool_from_env, find_tool, tool_in_dir, current_python): {tool!r}"
        )
    return [str(tool), *(os.fspath(a) if isinstance(a, os.PathLike) else str(a) for a in args)]


def run_tool(tool: Path, *args: object, **kwargs: object) -> subprocess.CompletedProcess:
    """``subprocess.run`` of an executable this module resolved; *args* are data argv elements."""
    return subprocess.run(_argv(tool, args), **kwargs)


def popen_tool(tool: Path, *args: object, **kwargs: object) -> subprocess.Popen:
    """``subprocess.Popen`` of an executable this module resolved; *args* are data argv elements."""
    return subprocess.Popen(_argv(tool, args), **kwargs)
