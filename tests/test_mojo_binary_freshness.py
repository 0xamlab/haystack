from __future__ import annotations

from pathlib import Path

from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_inspect_mojo_binary_freshness_reports_missing_binary(tmp_path: Path) -> None:
    source = tmp_path / "mojo" / "engine" / "main.mojo"
    _write(source, '"""source"""')

    freshness = inspect_mojo_binary_freshness(
        tmp_path / "mojo_build" / "simulate",
        source_paths=(source,),
    )

    assert freshness.exists is False
    assert freshness.is_fresh is False
    assert freshness.stale_sources == ()
    assert "not found" in freshness.failure_message()


def test_inspect_mojo_binary_freshness_reports_stale_sources(tmp_path: Path) -> None:
    binary = tmp_path / "mojo_build" / "simulate"
    source = tmp_path / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo"
    _write(binary, "binary")
    _write(source, "source")
    binary.touch()
    source.touch()

    freshness = inspect_mojo_binary_freshness(binary, source_paths=(source,))

    assert freshness.exists is True
    assert freshness.is_fresh is False
    assert freshness.stale_sources == (source,)
    assert "make build-mojo" in freshness.failure_message()


def test_inspect_mojo_binary_freshness_accepts_fresh_binary(tmp_path: Path) -> None:
    binary = tmp_path / "mojo_build" / "simulate"
    source = tmp_path / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo"
    _write(source, "source")
    _write(binary, "binary")
    source.touch()
    binary.touch()

    freshness = inspect_mojo_binary_freshness(binary, source_paths=(source,))

    assert freshness.exists is True
    assert freshness.is_fresh is True
    assert freshness.stale_sources == ()
