"""Reliability CI guardrails — Wave A0 of the enterprise-hardening roadmap.

Ratchet-style static guards that make later-wave regressions impossible WITHOUT
blocking on the pre-existing debt those later waves fix. Each guard collects
violations; a violation already recorded in ``baseline.json`` is KNOWN debt
(reported, non-fatal), while any NEW violation fails the build. As waves land and
remove debt, delete its baseline entries — the ratchet only ever tightens. (This
is the staged public-boundary import firewall from the plan: A0 warns on existing
internal imports but fails on new ones; later waves shrink the baseline to zero so
any remaining becomes fatal.)

Guards live in ``guards/`` and are auto-discovered (drop a file to add one). Run:
``python3 -m scripts.reliability_guards``. Import: ``from scripts.reliability_guards
import run_guards``.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path

from ._base import Guard, Violation, ROOT

BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"


def _discover() -> dict[str, Guard]:
    from . import guards as _pkg

    registry: dict[str, Guard] = {}
    for info in pkgutil.iter_modules(_pkg.__path__):
        module = importlib.import_module(f"{_pkg.__name__}.{info.name}")
        guard = getattr(module, "GUARD", None)
        if isinstance(guard, Guard):
            registry[guard.name] = guard
    return dict(sorted(registry.items()))


#: name -> Guard, populated by auto-discovery at import time.
GUARDS: dict[str, Guard] = _discover()


def load_baseline() -> dict[str, set[str]]:
    if not BASELINE_PATH.exists():
        return {name: set() for name in GUARDS}
    raw = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {name: set(raw.get(name, [])) for name in GUARDS}


def run_guards(root: Path | None = None, guards: list[str] | None = None) -> dict[str, dict[str, list[str]]]:
    """Return ``{guard: {"new": [...keys], "known": [...keys]}}``. Any ``new`` ⇒ fail."""
    root = root or ROOT
    baseline = load_baseline()
    selected = guards or list(GUARDS)
    result: dict[str, dict[str, list[str]]] = {}
    for name in selected:
        guard = GUARDS[name]
        keys = {v.key() for v in guard.scan(root)}
        base = baseline.get(name, set()) if guard.baselined else set()
        result[name] = {"new": sorted(keys - base), "known": sorted(keys & base)}
    return result


def update_baseline(root: Path | None = None) -> int:
    """Record current violations of baselined guards; return the total count."""
    root = root or ROOT
    data: dict[str, list[str]] = {}
    for name, guard in GUARDS.items():
        if guard.baselined:
            data[name] = sorted({v.key() for v in guard.scan(root)})
    BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sum(len(v) for v in data.values())


__all__ = [
    "Guard",
    "Violation",
    "GUARDS",
    "BASELINE_PATH",
    "ROOT",
    "run_guards",
    "load_baseline",
    "update_baseline",
]
