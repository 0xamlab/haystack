from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_BINARY = _REPO_ROOT / "mojo_build" / "simulate"
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
