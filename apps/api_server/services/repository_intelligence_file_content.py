from __future__ import annotations

import zipfile
from pathlib import Path

_SCRATCH_ARCHIVE_SUFFIXES = frozenset({".sb3"})


def repository_analysis_byte_size(path: Path) -> int:
    if path.suffix.lower() in _SCRATCH_ARCHIVE_SUFFIXES:
        try:
            with zipfile.ZipFile(path) as handle:
                return int(handle.getinfo("project.json").file_size)
        except (KeyError, OSError, ValueError, zipfile.BadZipFile):
            pass
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def read_repository_text(path: Path) -> str:
    if path.suffix.lower() in _SCRATCH_ARCHIVE_SUFFIXES:
        try:
            with zipfile.ZipFile(path) as handle:
                with handle.open("project.json") as project_file:
                    return project_file.read().decode("utf-8", errors="replace")
        except (KeyError, OSError, ValueError, zipfile.BadZipFile):
            return ""
    return path.read_text(encoding="utf-8", errors="replace")
