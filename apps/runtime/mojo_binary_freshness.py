from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BINARY = _REPO_ROOT / "mojo_build" / "simulate"
_MANIFEST_SCHEMA_VERSION = 1
_DEFAULT_SOURCES = (
    _REPO_ROOT / "mojo" / "engine" / "main.mojo",
    _REPO_ROOT / "mojo" / "engine" / "runtime_library_dispatch_generated.mojo",
)


@dataclass(frozen=True)
class MojoBinaryFreshness:
    binary_path: Path
    source_paths: tuple[Path, ...]
    stale_sources: tuple[Path, ...]

    @property
    def exists(self) -> bool:
        return self.binary_path.exists()

    @property
    def is_fresh(self) -> bool:
        return self.exists and not self.stale_sources

    def failure_message(self) -> str:
        if not self.exists:
            return f"Compiled Mojo binary not found at {self.binary_path}."
        stale_list = ", ".join(str(path) for path in self.stale_sources)
        return (
            f"Compiled Mojo binary at {self.binary_path} is stale relative to: {stale_list}. "
            "Rebuild with `make build-mojo` before starting the runtime kernel."
        )


def _manifest_path_for(binary_path: Path) -> Path:
    return binary_path.with_name(f"{binary_path.name}.manifest.json")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_manifest_source_path(raw_path: object) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    candidate = Path(raw_path)
    if candidate.is_absolute():
        return None

    resolved = (_REPO_ROOT / candidate).resolve()
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError:
        return None

    return resolved


def _manifest_freshness(binary_path: Path) -> tuple[tuple[Path, ...], tuple[Path, ...]] | None:
    manifest_path = _manifest_path_for(binary_path)
    if not manifest_path.exists():
        return None

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (manifest_path,), (manifest_path,)

    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _MANIFEST_SCHEMA_VERSION
    ):
        return (manifest_path,), (manifest_path,)

    manifest_binary_path = _resolve_manifest_source_path(payload.get("binary_path"))
    if manifest_binary_path is None or manifest_binary_path != binary_path.resolve():
        return (manifest_path,), (manifest_path,)

    expected_binary_sha256 = payload.get("binary_sha256")
    if not isinstance(expected_binary_sha256, str) or not expected_binary_sha256:
        return (manifest_path,), (manifest_path,)

    source_paths_raw = payload.get("source_paths")
    source_hashes = payload.get("source_sha256")
    if (
        not isinstance(source_paths_raw, list)
        or not source_paths_raw
        or not isinstance(source_hashes, dict)
    ):
        return (manifest_path,), (manifest_path,)

    stale_paths: list[Path] = []
    if _sha256_file(binary_path) != expected_binary_sha256:
        stale_paths.append(manifest_path)

    source_paths: list[Path] = []
    seen: set[Path] = set()
    for raw_source_path in source_paths_raw:
        source_path = _resolve_manifest_source_path(raw_source_path)
        if source_path is None or source_path in seen:
            stale_paths.append(manifest_path)
            continue

        seen.add(source_path)
        source_paths.append(source_path)
        expected_source_sha256 = source_hashes.get(raw_source_path)
        if not isinstance(expected_source_sha256, str) or not source_path.exists():
            stale_paths.append(source_path)
            continue
        if _sha256_file(source_path) != expected_source_sha256:
            stale_paths.append(source_path)

    return tuple(source_paths), tuple(dict.fromkeys(stale_paths))


def inspect_mojo_binary_freshness(
    binary_path: Path = _DEFAULT_BINARY,
    *,
    source_paths: tuple[Path, ...] = _DEFAULT_SOURCES,
) -> MojoBinaryFreshness:
    if not binary_path.exists():
        return MojoBinaryFreshness(
            binary_path=binary_path,
            source_paths=tuple(path for path in source_paths if path.exists()),
            stale_sources=(),
        )

    if source_paths == _DEFAULT_SOURCES:
        manifest_result = _manifest_freshness(binary_path)
        if manifest_result is not None:
            manifest_source_paths, manifest_stale_sources = manifest_result
            return MojoBinaryFreshness(
                binary_path=binary_path,
                source_paths=manifest_source_paths,
                stale_sources=manifest_stale_sources,
            )

    binary_mtime_ns = binary_path.stat().st_mtime_ns
    stale_sources = tuple(
        path
        for path in source_paths
        if path.exists() and path.stat().st_mtime_ns > binary_mtime_ns
    )
    return MojoBinaryFreshness(
        binary_path=binary_path,
        source_paths=tuple(path for path in source_paths if path.exists()),
        stale_sources=stale_sources,
    )
