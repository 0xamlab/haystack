"""Shared primitives for the modular reliability guards.

A guard is a small self-contained module under ``guards/`` that exposes a
module-level ``GUARD = Guard(...)``. The package auto-discovers them, so adding a
guard is just dropping a file — no central registry edit. See ``__init__`` for the
ratchet semantics (baselined known debt is non-fatal; any NEW violation fails).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# scripts/reliability_guards/_base.py -> parents[2] == repo root
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Violation:
    guard: str
    path: str
    snippet: str

    def key(self) -> str:
        """Identity stable across line moves: path + the matched construct."""
        return f"{self.path} :: {self.snippet.strip()}"


@dataclass(frozen=True)
class Guard:
    name: str
    description: str
    scan: Callable[[Path], "list[Violation]"]
    fix_wave: str = ""
    # ratchet: when True, violations already in the baseline are tolerated and only
    # NEW ones fail; when False (e.g. github_workflows) ANY hit fails immediately.
    baselined: bool = True


def iter_py(root: Path, rel_dir: str):
    """Yield *.py under ``root/rel_dir`` (skipping node_modules / vendored trees)."""
    base = root / rel_dir
    if not base.exists():
        return
    for p in sorted(base.rglob("*.py")):
        sp = str(p)
        if "/node_modules/" in sp or "/vendor/" in sp:
            continue
        yield p
