from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    assert "Refresh the Algenta runtime artifact" in freshness.failure_message()


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


def test_inspect_mojo_binary_freshness_uses_filtered_build_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from apps.runtime import mojo_binary_freshness as freshness_module

    monkeypatch.setattr(freshness_module, "_REPO_ROOT", tmp_path.resolve())
    binary = tmp_path / "mojo_build" / "simulate"
    source = tmp_path / "mojo" / "engine" / "main.mojo"
    generated_dispatch = tmp_path / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo"
    _write(binary, "binary")
    _write(source, "source")
    _write(generated_dispatch, "newer generated full dispatch")
    binary.touch()
    generated_dispatch.touch()

    manifest = binary.with_name("simulate.manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "build_mode": "filtered",
                "module_filter": ["text.tokenizer"],
                "binary_path": "mojo_build/simulate",
                "binary_sha256": _sha256(binary),
                "source_paths": ["mojo/engine/main.mojo"],
                "source_sha256": {"mojo/engine/main.mojo": _sha256(source)},
            },
        ),
        encoding="utf-8",
    )

    inspected = freshness_module.inspect_mojo_binary_freshness(binary)

    assert inspected.exists is True
    assert inspected.is_fresh is True
    assert inspected.stale_sources == ()
    assert inspected.source_paths == (source.resolve(),)

    _write(source, "changed source")
    inspected_after_change = freshness_module.inspect_mojo_binary_freshness(binary)

    assert inspected_after_change.is_fresh is False
    assert inspected_after_change.stale_sources == (source.resolve(),)


def test_inspect_mojo_binary_freshness_rejects_mismatched_manifest_binary_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from apps.runtime import mojo_binary_freshness as freshness_module

    monkeypatch.setattr(freshness_module, "_REPO_ROOT", tmp_path.resolve())
    binary = tmp_path / "mojo_build" / "simulate"
    source = tmp_path / "mojo" / "engine" / "main.mojo"
    _write(binary, "binary")
    _write(source, "source")

    manifest = binary.with_name("simulate.manifest.json")
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "build_mode": "filtered",
                "module_filter": ["text.tokenizer"],
                "binary_path": "mojo_build/other-simulate",
                "binary_sha256": _sha256(binary),
                "source_paths": ["mojo/engine/main.mojo"],
                "source_sha256": {"mojo/engine/main.mojo": _sha256(source)},
            },
        ),
        encoding="utf-8",
    )

    inspected = freshness_module.inspect_mojo_binary_freshness(binary)

    assert inspected.exists is True
    assert inspected.is_fresh is False
    assert inspected.source_paths == (manifest,)
    assert inspected.stale_sources == (manifest,)
