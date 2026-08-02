from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shard_builder_is_deterministic_and_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shard_builder = _load_script("build_runtime_shards")
    modules = tuple(
        SimpleNamespace(import_path=name) for name in ("zeta", "alpha", "middle", "beta")
    )
    monkeypatch.setattr(
        shard_builder, "discover_runtime_library_modules", lambda executable_only: modules
    )

    def fake_build(
        *, env: dict[str, str], log_path: Path, timeout: float, max_rss_kib: int | None = None
    ):
        assert timeout == 30.0
        worker = Path(env["BINARY_PATH"])
        worker.write_text("worker", encoding="utf-8")
        worker.chmod(0o755)
        worker.with_name(f"{worker.name}.manifest.json").write_text("{}", encoding="utf-8")
        log_path.write_text("ok", encoding="utf-8")
        return SimpleNamespace(peak_committed_kib=1024, peak_resident_kib=1024)

    monkeypatch.setattr(shard_builder, "_run_build", fake_build)
    out_dir = tmp_path / "runtime-shards"

    payload = shard_builder.build_runtime_shards(out_dir=out_dir, shard_size=2, timeout=30.0)

    assert payload["module_workers"] == {
        "alpha": "algenta-runtime-worker",
        "beta": "algenta-runtime-worker",
        "middle": "algenta-runtime-worker-001",
        "zeta": "algenta-runtime-worker-001",
    }
    assert payload["module_count"] == 4
    assert payload["shard_count"] == 2
    assert json.loads((out_dir / "runtime-shards.json").read_text(encoding="utf-8")) == payload
    assert not (out_dir / "sources").exists()


def test_shard_builder_announces_each_shard_before_compiling_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A build killed mid-shard must still say which shard it was on.

    The release job died five times in a row reporting nothing but `exit code
    143`, because the only per-shard output was printed *after* a shard finished.
    The last line of a killed build named the last shard that succeeded, not the
    one that was running.
    """
    shard_builder = _load_script("build_runtime_shards")
    modules = tuple(SimpleNamespace(import_path=name) for name in ("alpha", "beta", "gamma"))
    monkeypatch.setattr(
        shard_builder, "discover_runtime_library_modules", lambda executable_only: modules
    )

    def exploding_build(*, env: dict[str, str], log_path: Path, timeout: float, max_rss_kib=None):
        if "gamma" in env["MOJO_RUNTIME_MODULE_FILTER"]:
            raise shard_builder.ShardBuildError("boom")
        worker = Path(env["BINARY_PATH"])
        worker.write_text("worker", encoding="utf-8")
        log_path.write_text("ok", encoding="utf-8")
        return SimpleNamespace(peak_committed_kib=2048, peak_resident_kib=2048)

    monkeypatch.setattr(shard_builder, "_run_build", exploding_build)

    with pytest.raises(shard_builder.ShardBuildError):
        shard_builder.build_runtime_shards(
            out_dir=tmp_path / "runtime-shards", shard_size=2, timeout=30.0
        )

    out = capsys.readouterr().out
    assert "building algenta-runtime-worker-001 (shard 2/2): 1 modules (gamma .. gamma)" in out
    # and the shard that did finish reports what it cost, so a creeping footprint
    # is visible in a passing log rather than only in the crash that follows it.
    assert "peak footprint" in out


def test_shard_builder_names_the_in_flight_shard_when_killed() -> None:
    shard_builder = _load_script("build_runtime_shards")
    progress = shard_builder._PROGRESS
    progress.label = "shard 17/27"
    progress.worker_name = "algenta-runtime-worker-016"
    progress.modules = ("optimization.assignment", "paleomagnetism")
    progress.started_at = time.monotonic()

    described = progress.describe()

    assert "algenta-runtime-worker-016" in described
    assert "shard 17/27" in described
    assert "optimization.assignment .. paleomagnetism" in described


def test_footprint_sampler_reports_a_real_process_tree() -> None:
    """The ceiling is only as good as the measurement behind it."""
    shard_builder = _load_script("build_runtime_shards")
    footprint = shard_builder._tree_footprint_kib(os.getpid())
    assert footprint is not None
    resident, committed = footprint
    assert resident > 0
    assert committed >= resident


def test_stage_rejects_incomplete_shard_map(tmp_path: Path) -> None:
    staging = _load_script("stage_runtime_worker_package")
    worker = tmp_path / "algenta-runtime-worker"
    worker.write_text("worker", encoding="utf-8")
    shard_map = tmp_path / "runtime-shards.json"
    shard_map.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "module_count": 1,
                "shard_count": 2,
                "default_worker": worker.name,
                "module_workers": {"alpha": worker.name},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(staging.StageError, match="shard_count"):
        staging._load_shard_map(shard_map, (worker,))


def test_stage_resolves_macos_rpath_dependencies(tmp_path: Path) -> None:
    staging = _load_script("stage_runtime_worker_package")
    lib_root = tmp_path / "lib"
    lib_root.mkdir()
    runtime_lib = lib_root / "libRuntime.dylib"
    runtime_lib.write_bytes(b"runtime")
    output = "\n".join(
        (
            "worker:",
            "\t@rpath/libRuntime.dylib (compatibility version 0.0.0)",
            "\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)",
        )
    )

    assert staging._parse_otool(output, (lib_root,)) == (runtime_lib,)


def test_stage_linux_ldd_uses_only_approved_search_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    staging = _load_script("stage_runtime_worker_package")
    worker = tmp_path / "worker"
    worker.write_bytes(b"worker")
    lib_root = tmp_path / "pixi" / "lib"
    out_dir = tmp_path / "staged"
    lib_root.mkdir(parents=True)
    out_dir.mkdir()
    runtime_lib = lib_root / "libpython3.14.so.1.0"
    runtime_lib.write_bytes(b"runtime")
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], *, env: dict[str, str] | None = None) -> str:
        captured["cmd"] = cmd
        captured["env"] = env
        return f"libpython3.14.so.1.0 => {runtime_lib} (0x0)\n"

    monkeypatch.setattr(staging, "_run", fake_run)

    dependencies = staging.linked_dependencies(
        worker,
        "linux",
        search_roots=(worker.parent, lib_root, out_dir),
    )

    assert dependencies == (runtime_lib,)
    assert captured["cmd"] == ["ldd", str(worker)]
    assert captured["env"]["LD_LIBRARY_PATH"] == os.pathsep.join(
        str(path.resolve()) for path in (worker.parent, lib_root, out_dir)
    )
