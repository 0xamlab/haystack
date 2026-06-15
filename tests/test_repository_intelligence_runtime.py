from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence_runtime as runtime


def _reset_runtime_cache() -> None:
    runtime._RUNTIME_FALLBACK_CACHE = None
    runtime._SHARED_RUNTIME_CACHE = None


def test_repository_intelligence_shared_runtime_dir_defaults_to_runtime_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("ALGENTA_REPOSITORY_INTELLIGENCE_SHARED_RUNTIME_DIR", raising=False)
    _reset_runtime_cache()

    assert runtime._shared_repository_intelligence_dir() == (
        runtime_dir.resolve() / "repository_intelligence_shared"
    )
    assert runtime._file_analysis_cache_dir() == (
        runtime_dir.resolve() / "repository_intelligence_shared" / "file_analysis_cache"
    )


def test_repository_intelligence_shared_runtime_dir_honors_explicit_shared_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "runtime"
    shared_runtime_dir = tmp_path / "shared-runtime"
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv(
        "ALGENTA_REPOSITORY_INTELLIGENCE_SHARED_RUNTIME_DIR",
        str(shared_runtime_dir),
    )
    _reset_runtime_cache()

    assert runtime._repo_root_dir("org", "repo") == (
        runtime_dir.resolve() / "repository_intelligence" / "org" / "repo"
    )
    assert runtime._shared_repository_intelligence_dir() == (
        shared_runtime_dir.resolve() / "repository_intelligence_shared"
    )
    assert runtime._file_analysis_cache_dir() == (
        shared_runtime_dir.resolve() / "repository_intelligence_shared" / "file_analysis_cache"
    )


def test_repository_intelligence_shared_runtime_dir_reuses_explicit_shared_root_cache(
    monkeypatch,
    tmp_path: Path,
) -> None:
    shared_runtime_dir = tmp_path / "shared-runtime"
    monkeypatch.delenv("ALGENTA_RUNTIME_DIR", raising=False)
    monkeypatch.setenv(
        "ALGENTA_REPOSITORY_INTELLIGENCE_SHARED_RUNTIME_DIR",
        str(shared_runtime_dir),
    )
    _reset_runtime_cache()

    calls: list[Path] = []
    original_runtime_dir_writable = runtime._runtime_dir_writable

    def tracked_runtime_dir_writable(path: Path) -> bool:
        calls.append(path)
        return original_runtime_dir_writable(path)

    monkeypatch.setattr(
        runtime,
        "_runtime_dir_writable",
        tracked_runtime_dir_writable,
    )

    first = runtime._shared_runtime_dir()
    second = runtime._shared_runtime_dir()

    assert first == shared_runtime_dir.resolve()
    assert second == shared_runtime_dir.resolve()
    assert calls == [shared_runtime_dir.resolve()]
