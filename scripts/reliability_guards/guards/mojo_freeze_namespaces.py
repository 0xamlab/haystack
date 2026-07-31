"""Every namespace under ``mojo/engine/`` is either frozen or exempted — never neither.

The freeze gate is two ``git diff`` commands over ``mojo/engine/`` with a ``grep -v`` alternation
listing the additive namespaces. It has a failure mode that points the wrong way: **git diff does not
see untracked files**, so a brand-new package directory passes the gate trivially right up until it is
``git add``ed. During exactly the window when a new package is being written — when it most needs
checking — the gate reads as green because it is looking at nothing.

Found live on 2026-07-31: ``graph_analytics/``, ``optimization/`` and ``retrieval/`` were all
untracked, so none of them were covered, and the gate reported clean.

This guard closes that. It enumerates the directories that exist under ``mojo/engine/`` today and
requires each one to be accounted for in exactly one of two ways:

* it existed at the frozen baseline (``FROZEN_PACKAGES`` below), or
* its name appears in the freeze-gate alternation in ``docs/mojo/new-kernel-package-rules.md``.

A directory in neither is a new package whose author has not yet extended the alternation, which
means the next ``git add`` turns the gate red for everyone. Failing here, at authoring time, is the
cheap moment to catch it.

Not baselined: a missing namespace is always fatal. There is no legitimate steady state in which a
package under ``mojo/engine/`` is unaccounted for, so tolerating "known debt" would just be tolerating
a gate that has quietly stopped protecting the tree.
"""

from __future__ import annotations

import re
from pathlib import Path

from .._base import Guard, Violation

#: Sub-packages present at the frozen baseline commit ``eea8e045``. These are the things the freeze
#: gate protects, so they are deliberately NOT in the exemption alternation — listing one there would
#: silently stop protecting it. Snapshotted rather than read from git so the guard works in the
#: shallow clones CI uses.
FROZEN_PACKAGES = frozenset(
    {
        "automata",
        "compression",
        "config",
        "crypto",
        "data",
        "engines",
        "filepath",
        "graph",
        "json",
        "logging",
        "ml",
        "net",
        "serialization",
        "signal",
        "structs",
        "text",
        "vector_kernels",
    }
)

_RULES_DOC = Path("docs/mojo/new-kernel-package-rules.md")
_ENGINE_DIR = Path("mojo/engine")

#: Pulls the namespace names out of the ``grep -v -E '...'`` alternation in the rules doc, so the
#: guard reads the same string the gate does. Deriving it beats a second hardcoded list that could
#: drift from the one that actually runs.
_ALTERNATION = re.compile(r"grep -v -E '([^']+)'")


def _exempted_namespaces(root: Path) -> set[str]:
    doc = root / _RULES_DOC
    if not doc.exists():
        return set()
    text = doc.read_text(encoding="utf-8", errors="ignore")
    names: set[str] = set()
    for match in _ALTERNATION.finditer(text):
        for part in match.group(1).split("|"):
            part = part.strip()
            if part.endswith("/"):
                names.add(part[:-1])
    return names


def _scan(root: Path) -> list[Violation]:
    engine = root / _ENGINE_DIR
    if not engine.is_dir():
        return []

    exempt = _exempted_namespaces(root)
    out: list[Violation] = []

    for entry in sorted(engine.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "__")):
            continue
        name = entry.name
        if name in FROZEN_PACKAGES or name in exempt:
            continue
        out.append(
            Violation(
                "mojo_freeze_namespaces",
                (_ENGINE_DIR / name).as_posix(),
                (
                    f"namespace '{name}/' is neither frozen nor in the freeze-gate alternation in "
                    f"{_RULES_DOC.as_posix()} — add it there in the same commit that adds the package"
                ),
            )
        )
    return out


GUARD = Guard(
    name="mojo_freeze_namespaces",
    description="a mojo/engine namespace is missing from the freeze-gate alternation",
    scan=_scan,
    fix_wave="A0",
    baselined=False,  # a gate that silently stops protecting the tree is never acceptable debt
)
