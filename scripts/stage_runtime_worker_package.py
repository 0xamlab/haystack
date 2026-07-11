#!/usr/bin/env python3
"""Stage the Algenta runtime worker and its local dynamic-library closure.

The worker built by ``scripts/build_mojo_binary.sh`` links against runtime
libraries from the repo-local Pixi environment. Public wheels must not require
that environment, so this script copies only the linked non-system libraries into
one package directory and rewrites runtime search paths to load from that same
directory.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from collections import deque
from pathlib import Path

WORKER_BASENAME = "algenta-runtime-worker.exe" if os.name == "nt" else "algenta-runtime-worker"
SYSTEM_PREFIXES = (
    "/System/",
    "/usr/lib/",
    "/lib/",
    "/lib64/",
    "/usr/lib64/",
    "/usr/lib/x86_64-linux-gnu/",
    "/lib/x86_64-linux-gnu/",
)


class StageError(RuntimeError):
    """Runtime staging failed with an explicit, actionable reason."""


def _run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
    except FileNotFoundError as exc:
        raise StageError(f"required command not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise StageError(f"command failed: {' '.join(cmd)}\n{stderr}") from exc
    return proc.stdout


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _is_system_dependency(raw: str) -> bool:
    if (
        raw.startswith("@rpath/")
        or raw.startswith("@loader_path/")
        or raw.startswith("@executable_path/")
    ):
        return True
    return raw.startswith(SYSTEM_PREFIXES)


def _parse_otool(output: str) -> tuple[Path, ...]:
    deps: list[Path] = []
    for line in output.splitlines()[1:]:
        token = line.strip().split(" ", 1)[0]
        if token and token.startswith("/") and not _is_system_dependency(token):
            deps.append(Path(token))
    return tuple(deps)


def _parse_ldd(output: str) -> tuple[Path, ...]:
    deps: list[Path] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line or "not a dynamic executable" in line:
            continue
        if "=>" in line:
            _, right = line.split("=>", 1)
            token = right.strip().split(" ", 1)[0]
        else:
            token = line.split(" ", 1)[0]
        if token and token.startswith("/") and not _is_system_dependency(token):
            deps.append(Path(token))
    return tuple(deps)


def linked_dependencies(path: Path, platform: str) -> tuple[Path, ...]:
    if platform == "darwin":
        return _parse_otool(_run(["otool", "-L", str(path)]))
    if platform == "linux":
        return _parse_ldd(_run(["ldd", str(path)]))
    raise StageError(f"unsupported platform for runtime staging: {platform}")


def _copy_file(src: Path, dest: Path) -> None:
    real_src = src.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    shutil.copy2(real_src, dest)
    mode = dest.stat().st_mode
    if mode & stat.S_IXUSR:
        dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def collect_runtime_closure(
    worker: Path, lib_root: Path, out_dir: Path, platform: str
) -> tuple[Path, ...]:
    """Copy worker plus every linked non-system dependency from ``lib_root``.

    Dependencies outside ``lib_root`` are rejected instead of silently ignored;
    a public wheel cannot rely on mutable machine-local paths.
    """
    worker_dest = out_dir / WORKER_BASENAME
    _copy_file(worker, worker_dest)
    worker_dest.chmod(worker_dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    staged: dict[Path, Path] = {worker.resolve(): worker_dest}
    queue: deque[Path] = deque([worker.resolve()])
    while queue:
        current = queue.popleft()
        for dep in linked_dependencies(current, platform):
            resolved = dep.resolve()
            if _is_relative_to(resolved, out_dir):
                continue
            if not _is_relative_to(resolved, lib_root):
                raise StageError(
                    f"runtime dependency {resolved} is outside the expected library "
                    f"root {lib_root}. Refusing to build a wheel with an external "
                    "mutable dependency."
                )
            dest = out_dir / resolved.name
            if resolved not in staged:
                _copy_file(resolved, dest)
                staged[resolved] = dest
                queue.append(resolved)
    return tuple(staged.values())


def _linux_relink(artifacts: tuple[Path, ...]) -> None:
    if shutil.which("patchelf") is None:
        raise StageError("patchelf is required to stage the Linux runtime worker package")
    for artifact in artifacts:
        _run(["patchelf", "--set-rpath", "$ORIGIN", str(artifact)])


def _macos_relink(artifacts: tuple[Path, ...], lib_root: Path, out_dir: Path) -> None:
    if shutil.which("install_name_tool") is None:
        raise StageError("install_name_tool is required to stage the macOS runtime worker package")
    artifact_names = {artifact.name for artifact in artifacts}
    for artifact in artifacts:
        if artifact.suffix == ".dylib":
            _run(["install_name_tool", "-id", f"@loader_path/{artifact.name}", str(artifact)])
        try:
            _run(["install_name_tool", "-add_rpath", "@loader_path", str(artifact)])
        except StageError:
            pass
        for dep in linked_dependencies(artifact, "darwin"):
            resolved = dep.resolve()
            if (
                _is_relative_to(resolved, lib_root) or _is_relative_to(resolved, out_dir)
            ) and resolved.name in artifact_names:
                _run(
                    [
                        "install_name_tool",
                        "-change",
                        str(dep),
                        f"@loader_path/{resolved.name}",
                        str(artifact),
                    ]
                )


def relink_artifacts(
    artifacts: tuple[Path, ...], lib_root: Path, out_dir: Path, platform: str
) -> None:
    if platform == "darwin":
        _macos_relink(artifacts, lib_root, out_dir)
    elif platform == "linux":
        _linux_relink(artifacts)
    else:
        raise StageError(f"unsupported platform for relink: {platform}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worker", required=True, type=Path, help="Compiled runtime worker executable"
    )
    parser.add_argument(
        "--lib-root", required=True, type=Path, help="Pixi/runtime library directory"
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="Output directory staged for wheel bundling"
    )
    parser.add_argument("--platform", choices=("darwin", "linux"), default=sys.platform)
    args = parser.parse_args(argv)

    worker = args.worker.resolve()
    lib_root = args.lib_root.resolve()
    out_dir = args.out.resolve()
    if not worker.exists():
        raise StageError(f"runtime worker does not exist: {worker}")
    if not lib_root.is_dir():
        raise StageError(f"runtime library root does not exist: {lib_root}")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    artifacts = collect_runtime_closure(worker, lib_root, out_dir, args.platform)
    relink_artifacts(artifacts, lib_root, out_dir, args.platform)
    for artifact in sorted(artifacts):
        print(artifact)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
