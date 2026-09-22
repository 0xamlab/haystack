"""Stage one Space for upload: Space directory + vendored shared package + build stamps.

``stage_space(name, out_dir)`` produces the exact tree that ``deploy.py`` uploads with
``upload_folder``:

    out_dir/                      the Space's own files (app.py, README.md, Dockerfile, ...)
    out_dir/algenta_spaces/       the shared package, vendored at deploy time (plan D2)
    out_dir/.shared_sha           sha256 over the shared package files (sorted paths + bytes)
    out_dir/.git_sha              `git rev-parse HEAD` of the source checkout

Redirect Spaces (``sdk = "static"``) receive no shared package and no ``.shared_sha``.
Files matching ``IGNORE`` never leave the checkout and a file over ``MAX_FILE_BYTES``
(the pre-commit ceiling) aborts the stage before anything is written.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from manifest import APPS_SPACES_DIR, Manifest, Space, load_manifest

log = logging.getLogger(__name__)
__all__ = [
    "APPS_SPACES_DIR",
    "MAX_FILE_BYTES",
    "SHARED_DIRNAME",
    "UPLOAD_IGNORE_PATTERNS",
    "StageError",
    "StageResult",
    "check_sizes",
    "git_head",
    "is_ignored",
    "iter_files",
    "read_stamp",
    "stage_space",
    "tree_sha256",
]


SHARED_DIRNAME = "algenta_spaces"
MAX_FILE_BYTES = 500 * 1024
# Directory names (matched on any path segment) and glob patterns (matched on the file name).
IGNORE_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".ruff_cache"})
IGNORE_GLOBS = ("*.pyc", "*.whl", "*.so", "*.dylib", "leaderboard.json")
# The same list in Hub `upload_folder` syntax, so what stage refuses is also what the Hub
# would drop if a stray file appeared in the staged tree.
UPLOAD_IGNORE_PATTERNS = (
    "**/__pycache__/**",
    "*.pyc",
    "tests/**",
    "**/tests/**",
    "*.whl",
    "*.so",
    "*.dylib",
    "leaderboard.json",
)


class StageError(RuntimeError):
    """The Space cannot be staged as-is."""


@dataclass(frozen=True)
class StageResult:
    name: str
    staged_dir: Path
    files: tuple[str, ...]  # relative paths inside staged_dir, sorted
    shared_sha: str | None
    git_sha: str


def is_ignored(rel: Path) -> bool:
    if any(part in IGNORE_DIRS for part in rel.parts[:-1]):
        return True
    return any(fnmatch.fnmatch(rel.name, pat) for pat in IGNORE_GLOBS)


def iter_files(root: Path) -> list[Path]:
    """Files under ``root`` that survive the ignore list, as sorted relative paths."""
    if not root.is_dir():
        raise StageError(f"source directory missing: {root}")
    out = [p.relative_to(root) for p in root.rglob("*") if p.is_file()]
    return sorted(rel for rel in out if not is_ignored(rel))


def check_sizes(root: Path, rels: list[Path]) -> None:
    too_big = [
        (rel, (root / rel).stat().st_size)
        for rel in rels
        if (root / rel).stat().st_size > MAX_FILE_BYTES
    ]
    if too_big:
        listing = ", ".join(f"{rel} ({size // 1024} KB)" for rel, size in too_big)
        raise StageError(f"file(s) over {MAX_FILE_BYTES // 1024} KB refused: {listing}")


def tree_sha256(root: Path, rels: list[Path]) -> str:
    """Deterministic digest of a file tree: for each sorted path, its posix path, NUL, bytes."""
    digest = hashlib.sha256()
    for rel in rels:
        digest.update(rel.as_posix().encode())
        digest.update(b"\0")
        digest.update((root / rel).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_head(repo_dir: Path) -> str:
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv, no user input
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - git resolved from PATH on purpose
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StageError(f"git rev-parse HEAD failed in {repo_dir}: {exc}") from exc
    sha = out.stdout.strip()
    if len(sha) != 40:
        raise StageError(f"unexpected git sha {sha!r}")
    return sha


def _copy_tree(src: Path, dst: Path, rels: list[Path]) -> None:
    for rel in rels:
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target)


def stage_space(
    name: str,
    out_dir: Path | str,
    *,
    manifest: Manifest | None = None,
    git_sha: str | None = None,
) -> StageResult:
    manifest = manifest or load_manifest()
    space: Space = manifest.space(name)
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise StageError(f"out_dir must be empty: {out_dir}")
    if SHARED_DIRNAME in {p.name for p in manifest.source_dir(name).glob("*")}:
        raise StageError(f"{space.source} already holds {SHARED_DIRNAME}/; it is vendored by stage")

    src = manifest.source_dir(name)
    space_files = iter_files(src)
    check_sizes(src, space_files)

    shared_sha: str | None = None
    shared_files: list[Path] = []
    shared_dir = manifest.shared_package_dir
    if space.is_live:
        shared_files = iter_files(shared_dir)
        if not shared_files:
            raise StageError(f"shared package is empty: {shared_dir}")
        check_sizes(shared_dir, shared_files)
        shared_sha = tree_sha256(shared_dir, shared_files)

    sha = git_sha or git_head(manifest.path.parent)

    out_dir.mkdir(parents=True, exist_ok=True)
    _copy_tree(src, out_dir, space_files)
    files = [rel.as_posix() for rel in space_files]
    if space.is_live:
        _copy_tree(shared_dir, out_dir / SHARED_DIRNAME, shared_files)
        files += [(Path(SHARED_DIRNAME) / rel).as_posix() for rel in shared_files]
        (out_dir / ".shared_sha").write_text(f"{shared_sha}\n", encoding="utf-8")
        files.append(".shared_sha")
    (out_dir / ".git_sha").write_text(f"{sha}\n", encoding="utf-8")
    files.append(".git_sha")
    files.sort()
    log.info("staged %s: %d files -> %s", name, len(files), out_dir)
    return StageResult(
        name=name, staged_dir=out_dir, files=tuple(files), shared_sha=shared_sha, git_sha=sha
    )


def read_stamp(staged_dir: Path, stamp: str) -> str | None:
    path = staged_dir / stamp
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="stage one Space into a directory")
    ap.add_argument("--space", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--manifest", type=Path, default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    manifest = load_manifest(a.manifest) if a.manifest else load_manifest()
    try:
        result = stage_space(a.space, a.out, manifest=manifest)
    except StageError as exc:
        print(f"stage failed: {exc}")
        return 1
    for rel in result.files:
        print(rel)
    print(f"git_sha {result.git_sha}")
    if result.shared_sha:
        print(f"shared_sha {result.shared_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
