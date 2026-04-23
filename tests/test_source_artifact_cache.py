from __future__ import annotations

from pathlib import Path

from apps.api_server.services import source_artifact_cache as artifact_cache


def test_artifact_cache_dir_uses_single_fallback_warning_per_process(
    monkeypatch,
    tmp_path: Path,
) -> None:
    requested_path = tmp_path / "blocked-cache"
    fallback_path = tmp_path / "algenta-artifact-cache"
    warnings: list[tuple[str, dict[str, object]]] = []
    original_mkdir = Path.mkdir

    def _fake_mkdir(self: Path, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        if self == requested_path:
            raise OSError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", str(requested_path))
    monkeypatch.setattr(artifact_cache.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(Path, "mkdir", _fake_mkdir)
    monkeypatch.setattr(
        artifact_cache.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )
    artifact_cache._artifact_cache_dir.cache_clear()

    first = artifact_cache._artifact_cache_dir()
    second = artifact_cache._artifact_cache_dir()

    assert first == fallback_path
    assert second == fallback_path
    assert [event for event, _ in warnings] == ["source_artifact_cache_fallback_dir"]

    artifact_cache._artifact_cache_dir.cache_clear()


def test_artifact_cache_dir_uses_default_fallback_without_warning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    blocked_home = tmp_path / "blocked-home"
    requested_path = blocked_home / ".algenta" / "artifact_cache"
    fallback_path = tmp_path / "algenta-artifact-cache"
    warnings: list[tuple[str, dict[str, object]]] = []
    original_mkdir = Path.mkdir

    blocked_home.mkdir(parents=True, exist_ok=True)

    def _fake_mkdir(self: Path, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        if self == requested_path:
            raise OSError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.delenv("ALGENTA_SOURCE_ARTIFACT_CACHE_DIR", raising=False)
    monkeypatch.setattr(artifact_cache.Path, "home", classmethod(lambda cls: blocked_home))
    monkeypatch.setattr(artifact_cache.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(Path, "mkdir", _fake_mkdir)
    monkeypatch.setattr(
        artifact_cache.logger,
        "warning",
        lambda event, **kwargs: warnings.append((event, kwargs)),
    )
    artifact_cache._artifact_cache_dir.cache_clear()

    cache_dir = artifact_cache._artifact_cache_dir()

    assert cache_dir == fallback_path
    assert warnings == []

    artifact_cache._artifact_cache_dir.cache_clear()
