#!/usr/bin/env python3
"""Build deterministic, module-routed Algenta native runtime workers.

The public installation remains one automatic runtime package. Sharding is a
release-build detail that keeps each Mojo compiler invocation bounded while the
Python package presents one runtime contract and one process-local API.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime.mojo_inventory import discover_runtime_library_modules  # noqa: E402

WORKER_BASENAME = "algenta-runtime-worker.exe" if os.name == "nt" else "algenta-runtime-worker"
SHARD_MAP_NAME = "runtime-shards.json"


class ShardBuildError(RuntimeError):
    """A deterministic runtime-shard build failed."""


def _worker_name(index: int) -> str:
    if index == 0:
        return WORKER_BASENAME
    if WORKER_BASENAME.endswith(".exe"):
        return f"{WORKER_BASENAME[:-4]}-{index:03d}.exe"
    return f"{WORKER_BASENAME}-{index:03d}"


def _chunks(items: tuple[str, ...], size: int) -> tuple[tuple[str, ...], ...]:
    return tuple(items[index : index + size] for index in range(0, len(items), size))


def _run_build(*, env: dict[str, str], log_path: Path, timeout: float) -> None:
    command = ["bash", str(ROOT / "scripts" / "build_mojo_binary.sh")]
    with log_path.open("wb") as log_handle:
        proc = subprocess.Popen(  # noqa: S603
            command,
            cwd=ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            raise ShardBuildError(
                f"runtime shard build exceeded {timeout:g} seconds; log: {log_path}"
            ) from exc
    if return_code != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        raise ShardBuildError(
            "runtime shard build failed\n" + "\n".join(tail) + f"\nlog: {log_path}"
        )


def build_runtime_shards(*, out_dir: Path, shard_size: int, timeout: float) -> dict[str, object]:
    if shard_size < 1:
        raise ShardBuildError("shard size must be at least 1")
    modules = tuple(
        sorted(
            module.import_path for module in discover_runtime_library_modules(executable_only=True)
        )
    )
    if not modules:
        raise ShardBuildError("runtime inventory contains no executable modules")
    if len(modules) != len(set(modules)):
        raise ShardBuildError("runtime inventory contains duplicate module names")

    out_dir = out_dir.resolve()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    module_workers: dict[str, str] = {}
    try:
        for index, shard_modules in enumerate(_chunks(modules, shard_size)):
            worker_name = _worker_name(index)
            source_dir = work_dir / "sources" / f"shard-{index:03d}"
            source_dir.mkdir(parents=True)
            shutil.copy2(ROOT / "mojo" / "engine" / "main.mojo", source_dir / "main.mojo")
            worker_path = work_dir / worker_name
            env = os.environ.copy()
            env.update(
                {
                    "BINARY_PATH": str(worker_path),
                    "OBJECT_PATH": str(work_dir / f"{worker_name}.o"),
                    "TEMP_OBJECT_PATH": str(work_dir / f"{worker_name}.o.tmp"),
                    "TEMP_BINARY_PATH": str(work_dir / f"{worker_name}.tmp"),
                    "MOJO_SRC": str(source_dir / "main.mojo"),
                    "DISPATCH_OUTPUT_PATH": str(
                        source_dir / "runtime_library_dispatch_generated.mojo"
                    ),
                    "ENGINE_INCLUDE_DIR": str(ROOT / "mojo" / "engine"),
                    "MOJO_RUNTIME_MODULE_FILTER": ",".join(shard_modules),
                }
            )
            _run_build(
                env=env,
                log_path=work_dir / f"{worker_name}.build.log",
                timeout=timeout,
            )
            if not worker_path.is_file():
                raise ShardBuildError(f"runtime shard did not produce {worker_name}")
            module_workers.update(dict.fromkeys(shard_modules, worker_name))
            print(
                f"built {worker_name}: {len(shard_modules)} modules "
                f"({shard_modules[0]} .. {shard_modules[-1]})",
                flush=True,
            )

        shard_count = len(set(module_workers.values()))
        payload: dict[str, object] = {
            "schema_version": 1,
            "module_count": len(modules),
            "shard_count": shard_count,
            "default_worker": WORKER_BASENAME,
            "module_workers": module_workers,
        }
        (work_dir / SHARD_MAP_NAME).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.rmtree(work_dir / "sources")
        for log_path in work_dir.glob("*.build.log"):
            log_path.unlink()
        if out_dir.exists():
            shutil.rmtree(out_dir)
        work_dir.replace(out_dir)
        return payload
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--shard-size", type=int, default=24)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args(argv)
    payload = build_runtime_shards(
        out_dir=args.out,
        shard_size=args.shard_size,
        timeout=args.timeout_seconds,
    )
    print(
        f"runtime shards ready: {payload['module_count']} modules, {payload['shard_count']} workers"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ShardBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
