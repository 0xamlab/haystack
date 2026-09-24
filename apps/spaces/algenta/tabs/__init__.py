"""The flagship's tabs — one module per tab, one contract between them and the app shell.

Every tab module exposes ``build(deps) -> TabSpec``. The shell opens a ``gr.Tab`` per spec,
calls ``spec.render(gr)`` inside it and, once every tab exists, ``spec.connect(gr, tabs,
handles)`` for the specs that link across tabs (the Try tab's "Race it" chip switches to the
Races tab with a candidate preselected). Nothing here imports gradio: ``render`` receives the
module, so the tab modules import lazily and the unit tests build fakes without it.

``Deps`` is what the shell has at boot and every tab reads: the loaded Hub kernels, the one
native lane, the facts record, the limits and kill switch, the hero measurement and the machine
line. ``HeroResult`` is the flagship's opening card, measured by ``try_tab.measure_hero`` before
``launch()`` and re-measured live from the tab.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from algenta_spaces.bench import CellResult
from algenta_spaces.hubkernel import HubKernelError, LoadedKernel
from algenta_spaces.killswitch import KillSwitch
from algenta_spaces.lane import Lane
from algenta_spaces.limits import Limits

#: ``render(gr)`` returns the tab's named components so ``connect`` can wire across tabs.
Handles = dict[str, Any]
Render = Callable[[Any], Handles]
#: ``connect(gr, tabs, handles_by_tab_id)`` runs after every tab has rendered.
Connect = Callable[[Any, Any, Mapping[str, Handles]], None]

TAB_TRY = "try"
TAB_PLAY = "play"
TAB_RACE = "race"
TAB_LLM = "llm"
TAB_GOV = "gov"
TAB_ECO = "eco"
TAB_IDS: tuple[str, ...] = (TAB_TRY, TAB_PLAY, TAB_RACE, TAB_LLM, TAB_GOV, TAB_ECO)

#: The lane kind the native tabs ask ``Limits`` about when the shell's policy names it.
NATIVE_LIMIT_KIND = "native"

#: Optional handle: ``handles[LOAD_HOOKS] = [(fn, outputs), ...]`` — the shell runs each ``fn``
#: on page load into ``outputs`` with ``api_name=False``. A component built with a callable
#: ``value`` would register the same load event, but Gradio names that endpoint after the
#: function and lists it in ``/gradio_api/info``; this keeps the API surface to ``api_names``.
LOAD_HOOKS = "load"


@dataclass(frozen=True)
class TabSpec:
    """One tab: its permalink id, its label, how to render it and which endpoints it exposes."""

    id: str
    label: str
    render: Render
    api_names: tuple[str, ...]
    connect: Connect | None = None

    def __post_init__(self) -> None:
        if self.id not in TAB_IDS:
            raise ValueError(f"tab id must be one of {TAB_IDS}, got {self.id!r}")
        if not self.label.strip():
            raise ValueError("tab label is empty")
        if len(set(self.api_names)) != len(self.api_names):
            raise ValueError(f"api_names repeat: {self.api_names}")


@dataclass(frozen=True)
class ParityCheck:
    """One reference comparison: which library, which version, how far apart, within tolerance."""

    reference: str
    version: str
    deltas: Mapping[str, float]
    tolerances: Mapping[str, float]

    @property
    def ok(self) -> bool:
        return all(self.deltas[k] <= self.tolerances[k] for k in self.deltas)

    def label(self) -> str:
        """``z Δ ≤ 1e-9 · p Δ ≤ 1e-7`` — the bound each delta was checked against."""
        return " · ".join(f"{k} Δ ≤ {self.tolerances[k]:g}" for k in self.deltas)


@dataclass(frozen=True)
class HeroResult:
    """The opening card: the z-test measured through the lane under the rulebook."""

    args: Mapping[str, int]
    result: list[float]
    cell: CellResult
    parity: ParityCheck | None
    hardware: str
    ts_utc: str

    @property
    def z(self) -> float:
        return self.result[0]

    @property
    def p(self) -> float:
        return self.result[1]

    @property
    def kernel_ms(self) -> float | None:
        """The kernel-call median, or None when the cell was not measured."""
        ours = self.cell.lane("algenta")
        return None if ours is None or not self.cell.measured else ours.median_ms


@dataclass
class Deps:
    """What the shell hands every tab at boot."""

    kernels: Mapping[str, LoadedKernel]
    lane: Lane
    facts: Mapping[str, Any] = field(default_factory=dict)
    limits: Limits | None = None
    killswitch: KillSwitch | None = None
    hero: HeroResult | None = None
    hardware: str = ""
    kernel_errors: Mapping[str, HubKernelError] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)

    def kernel(self, family: str) -> LoadedKernel | None:
        """The loaded family under any spelling (``stats``, ``algenta-stats``), or None — also
        None for an unset family (a container where nothing loaded leaves the dropdowns empty,
        and a press then reaches here with None; the tabs answer with their quiet card)."""
        if not family:
            return None
        name = family.removeprefix("thyn-ai/")
        return self.kernels.get(name) or self.kernels.get(name.removeprefix("algenta-"))

    def feature_on(self, feature: str) -> bool:
        """The kill switch's answer; on when the shell runs without one."""
        return True if self.killswitch is None else self.killswitch.enabled(feature)


__all__ = [
    "LOAD_HOOKS",
    "NATIVE_LIMIT_KIND",
    "TAB_ECO",
    "TAB_GOV",
    "TAB_IDS",
    "TAB_LLM",
    "TAB_PLAY",
    "TAB_RACE",
    "TAB_TRY",
    "Connect",
    "Deps",
    "Handles",
    "HeroResult",
    "ParityCheck",
    "Render",
    "TabSpec",
]
