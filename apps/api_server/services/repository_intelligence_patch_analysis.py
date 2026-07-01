from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_PATCH_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_TEST_PATH_SEGMENTS = ("/tests/", "/test/", "/t/", "/src/test/")
_TEST_PATH_PREFIXES = ("tests/", "test/", "t/")
_TEST_PATH_SUFFIXES = (
    "_test.py",
    "_test.go",
    "_test.rb",
    "_test.scala",
    "_test.fs",
    "_test.fsi",
    "_test.fsx",
    "_spec.rb",
    "_spec.cr",
    ".spec.cr",
    "_test.rs",
    "_test.mj",
    "_test.mojo",
    "_test.kt",
    "_test.kts",
    "_test.dart",
    "_test.d",
    "_test.vb",
    "_test.pas",
    "_test.pp",
    "_test.lpr",
    "_test.dpr",
    "_test.groovy",
    ".test.scala",
    ".spec.scala",
    ".test.groovy",
    ".spec.groovy",
    ".test.fs",
    ".spec.fs",
    ".test.fsi",
    ".spec.fsi",
    ".test.fsx",
    ".spec.fsx",
    ".test.dart",
    ".test.d",
    ".test.vb",
    ".test.pas",
    ".test.pp",
    ".test.lpr",
    ".test.dpr",
    "_test.c",
    "_test.cc",
    "_test.cpp",
    "_test.cxx",
    "_test.zig",
    "_test.hs",
    "_test.hsc",
    "_test.lhs",
    "_test.f",
    "_test.f03",
    "_test.f08",
    "_test.f90",
    "_test.f95",
    "_test.for",
    "_test.ml",
    "_test.mli",
    "_test.nim",
    "_test.pl",
    "_test.pm",
    "_test.r",
    ".test.c",
    ".test.cc",
    ".test.cpp",
    ".test.cxx",
    ".test.zig",
    ".test.hs",
    ".test.hsc",
    ".test.lhs",
    ".test.f",
    ".test.f03",
    ".test.f08",
    ".test.f90",
    ".test.f95",
    ".test.for",
    ".test.ml",
    ".test.mli",
    ".test.nim",
    ".test.pl",
    ".test.pm",
    ".test.r",
    "test.c",
    "tests.c",
    "test.cc",
    "tests.cc",
    "test.cpp",
    "tests.cpp",
    "test.cxx",
    "tests.cxx",
    "test.zig",
    "tests.zig",
    "test.hs",
    "tests.hs",
    "spec.hs",
    "suite.hs",
    "test.f",
    "tests.f",
    "spec.f",
    "suite.f",
    "test.f03",
    "tests.f03",
    "spec.f03",
    "suite.f03",
    "test.f08",
    "tests.f08",
    "spec.f08",
    "suite.f08",
    "test.f90",
    "tests.f90",
    "spec.f90",
    "suite.f90",
    "test.f95",
    "tests.f95",
    "spec.f95",
    "suite.f95",
    "test.for",
    "tests.for",
    "spec.for",
    "suite.for",
    "test.d",
    "tests.d",
    "spec.d",
    "suite.d",
    "test.vb",
    "tests.vb",
    "spec.vb",
    "suite.vb",
    "test.pas",
    "tests.pas",
    "spec.pas",
    "suite.pas",
    "test.pp",
    "tests.pp",
    "spec.pp",
    "suite.pp",
    "test.lpr",
    "tests.lpr",
    "spec.lpr",
    "suite.lpr",
    "test.dpr",
    "tests.dpr",
    "spec.dpr",
    "suite.dpr",
    "test.ml",
    "tests.ml",
    "spec.ml",
    "suite.ml",
    "test.mli",
    "tests.mli",
    "spec.mli",
    "suite.mli",
    "test.nim",
    "tests.nim",
    "spec.nim",
    "suite.nim",
    ".t",
    "test.pl",
    "tests.pl",
    "spec.pl",
    "suite.pl",
    "test.pm",
    "tests.pm",
    "spec.pm",
    "suite.pm",
    "test.r",
    "tests.r",
    "spec.r",
    "suite.r",
    "test.hsc",
    "tests.hsc",
    "spec.hsc",
    "suite.hsc",
    "test.lhs",
    "tests.lhs",
    "spec.lhs",
    "suite.lhs",
    "test.java",
    "tests.java",
    "test.scala",
    "tests.scala",
    "spec.scala",
    "suite.scala",
    "test.groovy",
    "tests.groovy",
    "spec.groovy",
    "suite.groovy",
    "test.fs",
    "tests.fs",
    "spec.fs",
    "suite.fs",
    "test.fsi",
    "tests.fsi",
    "spec.fsi",
    "suite.fsi",
    "test.fsx",
    "tests.fsx",
    "spec.fsx",
    "suite.fsx",
    "test.dart",
    "tests.dart",
    "spec.dart",
    "suite.dart",
    ".spec.ts",
    ".test.ts",
    ".spec.js",
    ".test.js",
    ".tests.ps1",
    ".test.ps1",
    ".spec.ps1",
    ".tests.psm1",
    ".test.psm1",
    ".spec.psm1",
    "_suite.erl",
    "_tests.erl",
    "suite.erl",
    "tests.erl",
)

_MaterializedSnapshot = Callable[[dict[str, Any]], Any]
_GitCommand = Callable[..., str]


def _patch_header_path(raw_value: str, *, expected_prefix: str) -> str | None:
    value = raw_value.strip()
    if value == "/dev/null":
        return None
    if value.startswith(expected_prefix):
        return value[len(expected_prefix) :]
    return value


def _record_changed_line(
    changed_lines: dict[str, set[int]],
    *,
    file_path: str | None,
    line_number: int,
) -> None:
    if file_path is None or line_number < 1:
        return
    changed_lines[file_path].add(line_number)


def _compress_changed_line_sets(
    changed_lines: dict[str, set[int]],
) -> dict[str, list[tuple[int, int]]]:
    compressed: dict[str, list[tuple[int, int]]] = {}
    for file_path, line_numbers in changed_lines.items():
        if not line_numbers:
            continue
        ranges: list[tuple[int, int]] = []
        sorted_lines = sorted(line_numbers)
        start = sorted_lines[0]
        end = start
        for line_number in sorted_lines[1:]:
            if line_number == end + 1:
                end = line_number
                continue
            ranges.append((start, end))
            start = end = line_number
        ranges.append((start, end))
        compressed[file_path] = ranges
    return compressed


def _validate_patch_against_snapshot(
    *,
    snapshot_manifest: dict[str, Any],
    patch_diff: str,
    materialized_snapshot: _MaterializedSnapshot,
    git_command: _GitCommand,
) -> None:
    patch_files = sorted(_patch_changed_files(patch_diff))
    patch_hash = hashlib.sha256(patch_diff.encode("utf-8")).hexdigest()
    with materialized_snapshot(snapshot_manifest) as root_path:
        patch_path = root_path / ".algenta.patch.diff"
        patch_path.write_text(patch_diff, encoding="utf-8")
        init_command = ["git", "-C", str(root_path), "init", "-q"]
        validate_command = ["git", "-C", str(root_path), "apply", "--check", str(patch_path)]
        try:
            git_command(init_command, timeout=30.0)
            git_command(validate_command, timeout=30.0)
        except RepositoryIntelligenceError as exc:
            details = dict(exc.details or {})
            details.update(
                {
                    "snapshot_id": snapshot_manifest.get("snapshot_id"),
                    "resolved_revision": snapshot_manifest.get("resolved_revision"),
                    "source_archive_path": snapshot_manifest.get("source_archive_path"),
                    "patch_hash": patch_hash,
                    "patch_files": patch_files,
                    "validation_command": validate_command,
                }
            )
            raise RepositoryIntelligenceError(
                code="repository_patch_validation_failed",
                message=(
                    "Generated patch failed validation against the materialized snapshot baseline: "
                    f"{exc.message}"
                ),
                status_code=422,
                details=details,
            ) from exc


def _patch_changed_files(patch_diff: str) -> dict[str, list[tuple[int, int]]]:
    changed_lines: dict[str, set[int]] = defaultdict(set)
    old_file_path: str | None = None
    new_file_path: str | None = None
    old_line: int | None = None
    new_line: int | None = None
    for line in patch_diff.splitlines():
        if line.startswith("diff --git "):
            old_file_path = None
            new_file_path = None
            old_line = None
            new_line = None
            continue
        if line.startswith("--- "):
            old_file_path = _patch_header_path(line[4:], expected_prefix="a/")
            old_line = None
            new_line = None
            continue
        if line.startswith("+++ "):
            new_file_path = _patch_header_path(line[4:], expected_prefix="b/")
            old_line = None
            new_line = None
            continue
        hunk_match = _PATCH_HUNK_RE.match(line)
        if hunk_match:
            old_line = int(hunk_match.group(1))
            new_line = int(hunk_match.group(3))
            continue
        if old_line is None or new_line is None:
            continue
        if line.startswith("\\"):
            continue
        if line.startswith(" "):
            old_line += 1
            new_line += 1
            continue
        if line.startswith("-"):
            _record_changed_line(
                changed_lines,
                file_path=old_file_path or new_file_path,
                line_number=old_line,
            )
            old_line += 1
            continue
        if line.startswith("+"):
            _record_changed_line(
                changed_lines,
                file_path=new_file_path or old_file_path,
                line_number=new_line,
            )
            new_line += 1
            continue
        old_line = None
        new_line = None
    return _compress_changed_line_sets(changed_lines)


def _top_level_service(file_path: str) -> str:
    parts = Path(file_path).parts
    if not parts:
        return "repository"
    if parts[0] in {"apps", "packages", "services", "src"} and len(parts) > 1:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


@lru_cache(maxsize=16_384)
def _is_test_path(file_path: str) -> bool:
    lower = file_path.lower()
    wrapped = f"/{lower}"
    return (
        any(segment in wrapped for segment in _TEST_PATH_SEGMENTS)
        or lower.startswith(_TEST_PATH_PREFIXES)
        or lower.endswith(_TEST_PATH_SUFFIXES)
    )
