from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

_PATCH_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_PATCH_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
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


def _validate_patch_against_snapshot(
    *,
    snapshot_manifest: dict[str, Any],
    patch_diff: str,
    materialized_snapshot: _MaterializedSnapshot,
    git_command: _GitCommand,
) -> None:
    with materialized_snapshot(snapshot_manifest) as root_path:
        git_command(["git", "-C", str(root_path), "init", "-q"], timeout=30.0)
        patch_path = root_path / ".algenta.patch.diff"
        patch_path.write_text(patch_diff, encoding="utf-8")
        git_command(
            ["git", "-C", str(root_path), "apply", "--check", str(patch_path)],
            timeout=30.0,
        )


def _patch_changed_files(patch_diff: str) -> dict[str, list[tuple[int, int]]]:
    changed_files: dict[str, list[tuple[int, int]]] = defaultdict(list)
    current_file: str | None = None
    for line in patch_diff.splitlines():
        file_match = _PATCH_FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(1)
            continue
        hunk_match = _PATCH_HUNK_RE.match(line)
        if hunk_match and current_file is not None:
            start_line = int(hunk_match.group(1))
            line_count = int(hunk_match.group(2) or "1")
            changed_files[current_file].append(
                (start_line, start_line + max(line_count, 1) - 1)
            )
    return dict(changed_files)


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
