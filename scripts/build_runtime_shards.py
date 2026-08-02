#!/usr/bin/env python3
"""Build deterministic, module-routed Algenta native runtime workers.

The public installation remains one automatic runtime package. Sharding is a
release-build detail that keeps each Mojo compiler invocation bounded while the
Python package presents one runtime contract and one process-local API.

Every shard is instrumented. `mojo build` is a memory-hungry process -- a single
24-module shard has been measured at 11 GiB of peak footprint -- and the release
runners are small, so the failure that matters here is the builder running the
machine out of memory. When that happens the CI runner VM is torn down and the
step reports a bare `exit code 143` with nothing else, which says nothing about
which shard was in flight. So the builder announces each shard *before* it
starts, samples the compiler's footprint while it runs, reports it afterwards,
and prints a named diagnostic if it is killed. A build that dies should say what
it was doing when it died.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.runtime.mojo_inventory import discover_runtime_library_modules  # noqa: E402

WORKER_BASENAME = "algenta-runtime-worker.exe" if os.name == "nt" else "algenta-runtime-worker"
SHARD_MAP_NAME = "runtime-shards.json"
_SAMPLE_INTERVAL_SECONDS = 0.5
_KIB_PER_MIB = 1024
_PROC = Path("/proc")


class ShardBuildError(RuntimeError):
    """A deterministic runtime-shard build failed."""


def _mib(kib: int | float) -> str:
    return f"{kib / _KIB_PER_MIB:.0f} MiB"


def _gib(kib: int | float) -> str:
    return f"{kib / _KIB_PER_MIB / 1024:.1f} GiB"


def _worker_name(index: int) -> str:
    if index == 0:
        return WORKER_BASENAME
    if WORKER_BASENAME.endswith(".exe"):
        return f"{WORKER_BASENAME[:-4]}-{index:03d}.exe"
    return f"{WORKER_BASENAME}-{index:03d}"


def _chunks(items: tuple[str, ...], size: int) -> tuple[tuple[str, ...], ...]:
    return tuple(items[index : index + size] for index in range(0, len(items), size))


def _host_memory_kib() -> dict[str, int]:
    """Total/available/swap memory in KiB, or {} when it cannot be read.

    Never raises: this is diagnostics, and a build must not fail because a
    platform spells its memory counters differently.
    """
    try:
        meminfo = (_PROC / "meminfo").read_text(encoding="utf-8")
    except OSError:
        pass
    else:
        wanted = {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}
        found: dict[str, int] = {}
        for line in meminfo.splitlines():
            key, _, rest = line.partition(":")
            if key in wanted:
                found[key] = int(rest.strip().split()[0])
        return found
    try:
        total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True))  # noqa: S603, S607
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
    return {"MemTotal": total // 1024}


def _linux_tree_footprint_kib(root_pid: int) -> tuple[int, int] | None:
    """(resident, resident+swapped) KiB for a process tree, read from /proc."""
    children: dict[int, list[int]] = {}
    try:
        pids = [int(entry.name) for entry in _PROC.iterdir() if entry.name.isdigit()]
    except OSError:
        return None
    for pid in pids:
        try:
            stat = (_PROC / str(pid) / "stat").read_text(encoding="utf-8")
        except OSError:
            continue
        # comm can contain spaces and parentheses; ppid is the field after the
        # final ')'.
        tail = stat.rpartition(")")[2].split()
        if len(tail) < 2:
            continue
        children.setdefault(int(tail[1]), []).append(pid)

    resident = 0
    committed = 0
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        pending.extend(children.get(pid, ()))
        try:
            status = (_PROC / str(pid) / "status").read_text(encoding="utf-8")
        except OSError:
            continue
        for field, value in re.findall(r"^(VmRSS|VmSwap):\s+(\d+) kB$", status, re.MULTILINE):
            if field == "VmRSS":
                resident += int(value)
            committed += int(value)
    return resident, committed


def _ps_tree_footprint_kib(root_pid: int) -> tuple[int, int] | None:
    """(resident, resident) KiB for a process tree, via ps. No swap accounting."""
    try:
        output = subprocess.check_output(  # noqa: S603
            ["ps", "-Ao", "pid=,ppid=,rss="],  # noqa: S607
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    children: dict[int, list[int]] = {}
    rss: dict[int, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        try:
            pid, ppid, resident = (int(field) for field in fields)
        except ValueError:
            continue
        children.setdefault(ppid, []).append(pid)
        rss[pid] = resident
    total = 0
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        pending.extend(children.get(pid, ()))
        total += rss.get(pid, 0)
    return total, total


def _tree_footprint_kib(root_pid: int) -> tuple[int, int] | None:
    """Resident and resident+swapped KiB for a process tree.

    On a runner that is already swapping, resident size alone *understates* the
    compiler by however much the kernel has paged out -- which is exactly the
    situation worth reporting -- so Linux reads VmRSS+VmSwap from /proc.
    """
    if _PROC.is_dir():
        return _linux_tree_footprint_kib(root_pid)
    return _ps_tree_footprint_kib(root_pid)


class _FootprintSampler:
    """Samples a build's process-tree memory footprint on a background thread."""

    def __init__(self, root_pid: int, *, limit_kib: int | None) -> None:
        self._root_pid = root_pid
        self._limit_kib = limit_kib
        self._stop = threading.Event()
        self.peak_resident_kib = 0
        self.peak_committed_kib = 0
        self.limit_exceeded = False
        self._thread = threading.Thread(target=self._run, name="shard-footprint", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            sample = _tree_footprint_kib(self._root_pid)
            if sample is not None:
                resident, committed = sample
                self.peak_resident_kib = max(self.peak_resident_kib, resident)
                self.peak_committed_kib = max(self.peak_committed_kib, committed)
                if self._limit_kib is not None and committed > self._limit_kib:
                    self.limit_exceeded = True
                    return
            self._stop.wait(_SAMPLE_INTERVAL_SECONDS)


class _ShardProgress:
    """The shard currently being compiled, for signal-time diagnostics."""

    def __init__(self) -> None:
        self.label = ""
        self.worker_name = ""
        self.modules: tuple[str, ...] = ()
        self.started_at = 0.0
        self.sampler: _FootprintSampler | None = None

    def describe(self) -> str:
        if not self.worker_name:
            return "no shard was in flight"
        elapsed = time.monotonic() - self.started_at
        detail = (
            f"{self.worker_name} ({self.label}, {len(self.modules)} modules: "
            f"{self.modules[0]} .. {self.modules[-1]}) after {elapsed:.1f}s"
        )
        sampler = self.sampler
        if sampler is not None and sampler.peak_committed_kib:
            detail += (
                f", peak footprint {_mib(sampler.peak_committed_kib)}"
                f" (resident {_mib(sampler.peak_resident_kib)})"
            )
        memory = _host_memory_kib()
        if memory:
            detail += "; host " + ", ".join(
                f"{key} {_gib(value)}" for key, value in sorted(memory.items())
            )
        return detail


_PROGRESS = _ShardProgress()


def _emit(message: str) -> None:
    """Write a diagnostic straight to fd 2 -- usable from a signal handler."""
    try:
        os.write(2, message.encode("utf-8", "replace") + b"\n")
    except OSError:
        pass


def _install_termination_diagnostics() -> None:
    """Name the in-flight shard when something outside this script kills us.

    A SIGTERM this script did not send is, on a CI runner, almost always the
    machine itself going away: the compiler exhausted memory, the runner agent
    stopped answering, and the platform tore the VM down. All the step shows for
    that is `Process completed with exit code 143`. Leave a breadcrumb instead.
    """

    def _handler(signum: int, _frame: object) -> None:
        name = signal.Signals(signum).name
        _emit(
            f"::error::runtime shard build killed by {name} while building {_PROGRESS.describe()}"
        )
        _emit(
            f"error: {name} was not sent by this script. On a CI runner that almost always "
            "means the machine ran out of memory and the host tore the VM down. Compare the "
            "peak footprint above against the host memory reported at the start of this step."
        )
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for signum in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(signum, _handler)
        except (OSError, ValueError):  # pragma: no cover - platform dependent
            pass


def _print_host_banner(
    *,
    out_dir: Path,
    modules: int,
    shards: int,
    shard_size: int,
    timeout: float,
    max_rss_mb: int | None,
) -> None:
    memory = _host_memory_kib()
    parts = [f"cpus {os.cpu_count()}"]
    if memory:
        parts.extend(f"{key} {_gib(value)}" for key, value in sorted(memory.items()))
    try:
        usage = shutil.disk_usage(out_dir.parent)
        parts.append(f"disk free {usage.free / 1024**3:.1f} GiB")
    except OSError:
        pass
    print(f"runtime shard build host: {', '.join(parts)}", flush=True)
    ceiling = "unbounded" if max_rss_mb is None else f"{max_rss_mb} MiB"
    print(
        f"runtime shard build plan: {modules} modules -> {shards} shards of <= {shard_size}, "
        f"per-shard timeout {timeout:g}s, per-shard footprint ceiling {ceiling}",
        flush=True,
    )


def _run_build(
    *,
    env: dict[str, str],
    log_path: Path,
    timeout: float,
    max_rss_kib: int | None = None,
) -> _FootprintSampler:
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
        sampler = _FootprintSampler(proc.pid, limit_kib=max_rss_kib)
        _PROGRESS.sampler = sampler
        sampler.start()
        try:
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                if sampler.limit_exceeded:
                    _kill_tree(proc)
                    raise ShardBuildError(
                        f"runtime shard build exceeded the {_mib(max_rss_kib or 0)} footprint "
                        f"ceiling while building {_PROGRESS.describe()}; log: {log_path}"
                    )
                try:
                    return_code = proc.wait(timeout=min(remaining, _SAMPLE_INTERVAL_SECONDS))
                except subprocess.TimeoutExpired:
                    continue
                break
        except subprocess.TimeoutExpired as exc:
            _kill_tree(proc)
            raise ShardBuildError(
                f"runtime shard build exceeded {timeout:g} seconds while building "
                f"{_PROGRESS.describe()}; log: {log_path}"
            ) from exc
        finally:
            sampler.stop()
    if return_code != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        raise ShardBuildError(
            f"runtime shard build failed for {_PROGRESS.describe()}\n"
            + "\n".join(tail)
            + f"\nlog: {log_path}"
        )
    return sampler


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - racy teardown
        pass


def build_runtime_shards(
    *,
    out_dir: Path,
    shard_size: int,
    timeout: float,
    max_rss_mb: int | None = None,
) -> dict[str, object]:
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
    shards = _chunks(modules, shard_size)
    _print_host_banner(
        out_dir=out_dir,
        modules=len(modules),
        shards=len(shards),
        shard_size=shard_size,
        timeout=timeout,
        max_rss_mb=max_rss_mb,
    )
    max_rss_kib = max_rss_mb * _KIB_PER_MIB if max_rss_mb else None
    work_dir = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=out_dir.parent))
    module_workers: dict[str, str] = {}
    try:
        for index, shard_modules in enumerate(shards):
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
            _PROGRESS.label = f"shard {index + 1}/{len(shards)}"
            _PROGRESS.worker_name = worker_name
            _PROGRESS.modules = shard_modules
            _PROGRESS.started_at = time.monotonic()
            # Announced before the compile, not after, so a build that is killed
            # mid-shard still identifies the shard that killed it.
            print(
                f"building {worker_name} ({_PROGRESS.label}): {len(shard_modules)} modules "
                f"({shard_modules[0]} .. {shard_modules[-1]})",
                flush=True,
            )
            sampler = _run_build(
                env=env,
                log_path=work_dir / f"{worker_name}.build.log",
                timeout=timeout,
                max_rss_kib=max_rss_kib,
            )
            if not worker_path.is_file():
                raise ShardBuildError(f"runtime shard did not produce {worker_name}")
            module_workers.update(dict.fromkeys(shard_modules, worker_name))
            print(
                f"built {worker_name}: {len(shard_modules)} modules "
                f"({shard_modules[0]} .. {shard_modules[-1]})"
                f" in {time.monotonic() - _PROGRESS.started_at:.1f}s, "
                f"peak footprint {_mib(sampler.peak_committed_kib)}",
                flush=True,
            )
            _warn_if_over_ram(sampler)

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


def _warn_if_over_ram(sampler: _FootprintSampler) -> None:
    """Say so when a shard needed more memory than the machine physically has.

    Surviving on swap is the state immediately before not surviving at all, and
    it is invisible in a passing log unless something says it out loud.
    """
    total = _host_memory_kib().get("MemTotal")
    if not total or not sampler.peak_committed_kib:
        return
    if sampler.peak_committed_kib > total:
        print(
            f"::warning::shard footprint {_mib(sampler.peak_committed_kib)} exceeded host RAM "
            f"({_mib(total)}); this shard compiled on swap and is one growth spurt away from "
            "taking the runner down",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--shard-size", type=int, default=24)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--max-rss-mb",
        type=int,
        default=0,
        help=(
            "fail a shard whose process-tree footprint exceeds this many MiB, instead of "
            "letting the host run out of memory and kill the build with no diagnostic. "
            "0 disables the ceiling."
        ),
    )
    args = parser.parse_args(argv)
    _install_termination_diagnostics()
    payload = build_runtime_shards(
        out_dir=args.out,
        shard_size=args.shard_size,
        timeout=args.timeout_seconds,
        max_rss_mb=args.max_rss_mb or None,
    )
    print(
        f"runtime shards ready: {payload['module_count']} modules, {payload['shard_count']} workers"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ShardBuildError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
