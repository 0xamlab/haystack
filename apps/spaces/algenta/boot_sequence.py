"""Boot — everything expensive happens once, before `launch()`, and is reported stage by stage.

The flagship opens on an already-measured result, so the work that makes numbers real runs
before the server accepts its first request, in a fixed order the boot card and `/health`
report (`algenta_spaces.boot.BootRegistry`):

1. **host** — the published CPU floor (`hubkernel.host_floor_ok`); below it every native
   tab is held with the reason and nothing native runs.
2. **kernels** — `hubkernel.preload` over every published family plus the umbrella: each
   loads from the baked cache and runs its card example once, so the first visitor never
   pays the runtime initialisation. Per-family failures are kept, never raised; the tabs
   render the unavailable card with the code.
3. **hero** — `tabs.try_tab.measure_hero`: the opening z-test under the benchmark rulebook
   (`bench.RULEBOOK_VERSION`, `docs/spaces/RULEBOOK.md`) through the one native lane, gated
   against statsmodels. A noisy verdict is retried with backoff, up to `HERO_ATTEMPTS` times
   inside the boot window; if none is measured, a `HeroTracker` keeps
   re-measuring every `HERO_RETRY_S` seconds in the background and the page paints the first
   measured card when it lands — the opening promise holds by design, never by luck. The
   stage's row is live: `hero_detail` words the tracker's state as it is now, and the registry
   (`FlagshipRegistry`) reads it through a detail hook each time its snapshot is taken, so
   `/health`'s `stages[hero].detail` and the boot card rendered from that snapshot say what
   `/health`'s `hero` says — `0.12 ms per kernel call, n = 21 × 83 calls · statsmodels agrees ·
   attempt 18 · measured after boot` once a background attempt records, never a frozen promise
   to keep measuring.
4. **facts** — `facts.json`: versions, the git and shared-package stamps, and every count the
   copy may quote (families, functions, modules, MCP tools), computed from what loaded. The
   counts have one truth: `functions_loaded` and `families_loaded` are what this container
   runs (the umbrella is never a family and never counted twice); `catalogue_functions` is the
   published catalogue the umbrella describes, quoted only in the boot disclosure and the
   Reproduce notes. `headline(facts)` — `5,683 compiled Mojo kernels` — is the one sentence
   the header and the tabs derive from those counts.
5. **flags** — the kill switch starts polling `flags.json` (`KILLSWITCH_URL`, default the
   public results Dataset). Reads fail open; spend features are off until the file has been
   read once, which is the intended state until the file exists.
6. **hosted** — one `me` probe of the hosted API through `hosted_api.HostedGoverned`; without
   the `ALGENTA_API_KEY` secret the governed tab is the not-configured card. The boot row says
   it in words (`hosted_detail`: `not configured · no API key is set for this Space, so the
   governed lane is off`), never the state's identifier.

`run_boot()` never raises for a stage that can be reported: a failing stage is recorded with
its reason and boot continues, so `/health` tells the truth and the page ships smaller. The
same module is the image's cache tool: `--bake` installs the twenty capped repositories with
`kernels.install_kernel` and prunes the Hub tree listings (see `prune_tree_listings`), and
`--verify-cache`, run with `HF_HUB_OFFLINE=1`, loads every family from that cache and fails
the build if one is missing — the runtime never downloads.
"""

from __future__ import annotations

import argparse
import functools
import logging
import os
import re
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from algenta_spaces import bench, boot, hosted_api, hubkernel, shell
from algenta_spaces import facts as facts_mod
from algenta_spaces import killswitch as killswitch_mod
from algenta_spaces import lane as lane_mod
from algenta_spaces import limits as limits_mod
from algenta_spaces.runtime import is_sha, utc_stamp

import hf_ua_shim
import webhook
from tabs import NATIVE_LIMIT_KIND, Deps, HeroResult

log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent

#: The families the six tabs call directly, loaded first so the opening card is measured early.
TAB_FAMILIES: tuple[str, ...] = (
    "stats",
    "text",
    "graph",
    "geometry",
    "bits-time",
    "finance",
    "ml",
    "vision",
    "crypto",
    "llm",
)
#: The rest of the published catalogue, loaded so the Playground offers every function.
OTHER_FAMILIES: tuple[str, ...] = tuple(
    hubkernel.short_family(repo)
    for repo in hubkernel.TRUST
    if hubkernel.short_family(repo) != hubkernel.UMBRELLA_FAMILY
    and hubkernel.short_family(repo).removeprefix("algenta-") not in TAB_FAMILIES
)
FAMILIES: tuple[str, ...] = TAB_FAMILIES + OTHER_FAMILIES
#: Everything `preload` warms: the families, then the umbrella (its members are already loaded).
PRELOAD: tuple[str, ...] = FAMILIES + (hubkernel.UMBRELLA_FAMILY,)

#: `facts.mcp_tools_source` when `/health` carries this container's last live read of the
#: hosted tools list in place of an installed registry's count (`BootState.live_facts`).
MCP_TOOLS_LIVE = "live"
STAGE_HOST = "host"
STAGE_KERNELS = "kernels"
STAGE_HERO = "hero"
STAGE_FACTS = "facts"
STAGE_FLAGS = "flags"
STAGE_HOSTED = "hosted"
STAGES: tuple[tuple[str, str], ...] = (
    (STAGE_HOST, "Checking the host"),
    (STAGE_KERNELS, "Warming the Hub kernels"),
    (STAGE_HERO, "Measuring the opening card"),
    (STAGE_FACTS, "Counting what loaded"),
    (STAGE_FLAGS, "Reading the feature flags"),
    (STAGE_HOSTED, "Checking the hosted API"),
)

KILLSWITCH_ENV = "KILLSWITCH_URL"
DEFAULT_KILLSWITCH_URL = (
    "https://huggingface.co/datasets/thyn-ai/algenta-arena-results/resolve/main/flags.json"
)
FACTS_PATH_ENV = "ALGENTA_FACTS_PATH"
FACTS_FILE = facts_mod.FACTS_FILE
DIST_NAMES: tuple[str, ...] = (
    "gradio",
    "torch",
    "kernels",
    "huggingface_hub",
    "numpy",
    "scipy",
    "statsmodels",
    "networkx",
    "nltk",
    "sympy",
    "algenta",
    "algenta-runtime-native",
    "algenta-mcp",
)
HOST_FLOOR_CODE = "platform_unsupported"
HERO_FAMILY = "stats"
#: The hero is re-measured this many times inside boot when the rulebook says noisy …
HERO_ATTEMPTS = 6
#: … waiting this long between attempts (the last value repeats), 10.5 s in all …
HERO_BACKOFF_S: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 4.0)
#: … and then every minute in the background until one attempt is measured.
HERO_RETRY_S = 60.0

#: The native lane's visitor limits: a generous burst for a page whose calls take milliseconds,
#: a per-visitor day that a person cannot exhaust by hand, an org day that a script can.
NATIVE_POLICY = limits_mod.Policy(
    {
        **limits_mod.DEFAULT_POLICY.lanes,
        NATIVE_LIMIT_KIND: limits_mod.LanePolicy(
            burst=30, window_s=60.0, per_day=2_000, daily_cap=50_000
        ),
    }
)

Progress = Callable[[str], None]
Sleep = Callable[[float], Any]


def bare(family: str) -> str:
    """`algenta-stats` -> `stats`; the umbrella stays `algenta`."""
    return family.removeprefix("algenta-") if family != hubkernel.UMBRELLA_FAMILY else family


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class FlagshipDeps(Deps):
    """`Deps` plus the hero tracker: the Try tab paints the latest measured card from it."""

    hero_tracker: Any = None


DetailHook = Callable[[], str | None]


class FlagshipRegistry(boot.BootRegistry):
    """The boot registry plus live details for a stage whose truth keeps moving after it ended.

    A stage that hands work to the background (the hero, re-measured until it records)
    registers a hook in `detail_hooks` that words its state as it is now; `snapshot()` — and so
    `/health`, `render_html()` and the boot card built from it — reads the hook in place of the
    words frozen when the stage finished. The stage's state, clock and elapsed time are the
    boot's and stay as recorded; only the detail is live. A hook that answers nothing or raises
    leaves the frozen detail in place, so the card never loses its row.
    """

    def __init__(
        self, stages: Iterable[tuple[str, str]], *, clock: Callable[[], float] = time.time
    ) -> None:
        super().__init__(stages, clock=clock)
        self.detail_hooks: dict[str, DetailHook] = {}

    def snapshot(self) -> dict[str, Any]:
        snapshot = super().snapshot()
        for stage in snapshot["stages"]:
            hook = self.detail_hooks.get(stage["id"])
            if hook is None:
                continue
            try:
                detail = hook()
            except Exception as exc:  # the frozen words stand; the card never loses a row
                log.warning("live detail of stage %s failed: %s", stage["id"], exc)
                continue
            if isinstance(detail, str) and detail.strip():
                stage["detail"] = detail
        return snapshot


@dataclass
class BootState:
    """Everything boot produced; `deps()` is what the tabs get, `health()` what `/health` says."""

    registry: boot.BootRegistry
    lane: lane_mod.Lane
    limits: limits_mod.Limits
    killswitch: killswitch_mod.KillSwitch
    hook: webhook.Hook
    env: Mapping[str, str]
    started_utc: str
    hardware: str = ""
    floor_ok: bool = True
    floor_reason: str = ""
    preload: hubkernel.Preload | None = None
    hero_tracker: Any = None
    facts: dict[str, Any] = field(default_factory=dict)
    hosted: hosted_api.HostedGoverned | None = None
    hosted_status: hosted_api.HostedStatus | None = None

    @property
    def kernels(self) -> dict[str, hubkernel.LoadedKernel]:
        """Loaded families by bare name (`stats`, …; the umbrella is `algenta`) — the tabs' keys."""
        return {} if self.preload is None else {bare(k): v for k, v in self.preload.loaded.items()}

    @property
    def kernel_errors(self) -> dict[str, hubkernel.HubKernelError]:
        return {} if self.preload is None else {bare(k): v for k, v in self.preload.errors.items()}

    @property
    def ready(self) -> bool:
        return self.registry.ready

    @property
    def hero(self) -> HeroResult | None:
        """The opening card's data: the last measured attempt, else the last attempt."""
        return None if self.hero_tracker is None else self.hero_tracker.hero

    @hero.setter
    def hero(self, value: HeroResult | None) -> None:
        """Replace the opening card's data outright (tests); the old tracker's thread stops."""
        from tabs import try_tab

        if self.hero_tracker is not None:
            self.hero_tracker.stop()
        self.hero_tracker = None if value is None else try_tab.HeroTracker(hero=value)

    def stop(self) -> None:
        """End the background work boot started: the hero re-measurement and the flag polls."""
        if self.hero_tracker is not None:
            self.hero_tracker.stop()
        self.killswitch.stop()

    def kernel(self, family: str) -> hubkernel.LoadedKernel | None:
        return self.kernels.get(bare(hubkernel.short_family(family)))

    def summary(self) -> str:
        """`ready · host=done kernels=done …` — one line for the log."""
        snapshot = self.registry.snapshot()
        words = [f"{s['id']}={s['state']}" for s in snapshot["stages"]]
        return ("ready · " if snapshot["ready"] else "not ready · ") + " ".join(words)

    def deps(self) -> Deps:
        return FlagshipDeps(
            kernels=self.kernels,
            lane=self.lane,
            facts=self.facts,
            limits=self.limits,
            killswitch=self.killswitch,
            hero=self.hero,
            hardware=self.hardware,
            kernel_errors=self.kernel_errors,
            env=self.env,
            hero_tracker=self.hero_tracker,
        )

    def hero_summary(self) -> dict[str, Any] | None:
        """The opening card as data for `/health` and `/api/status`; None before any attempt.

        `status` is the card's: `measured` once any attempt was, else the latest verdict; the
        `attempts` count and `retry_s` say what the tracker is still doing.
        """
        hero = self.hero
        if hero is None:
            return None
        parity = None
        if hero.parity is not None:
            parity = {
                "ok": hero.parity.ok,
                "reference": hero.parity.reference,
                "version": hero.parity.version,
                "deltas": dict(hero.parity.deltas),
                "tolerances": dict(hero.parity.tolerances),
            }
        from tabs import try_tab

        return {
            "family": HERO_FAMILY,
            "qualname": try_tab.HERO_QUALNAME,
            "args": dict(hero.args),
            "result": list(hero.result),
            "status": hero.cell.status,
            "reason": hero.cell.reason,
            "n": hero.cell.n,
            # rulebook v0.4: k back-to-back calls per timed sample (None only when the lanes of a
            # cell batched differently; the hero has one lane) — the boot row and the Try card
            # print `n = 21 × k calls` from it, and `boot_row_live` reads it as the truth
            "k": hero.cell.k,
            "kernel_ms": hero.kernel_ms,
            "parity": parity,
            "ts_utc": hero.ts_utc,
            "hardware": hero.hardware,
            **(self.hero_tracker.snapshot() if self.hero_tracker is not None else {}),
        }

    def health(self) -> dict[str, Any]:
        """The boot snapshot (`ready`, `error`, `stages`, `elapsed_s`) plus what the page uses."""
        snapshot = self.registry.snapshot()
        if snapshot["ready"]:
            status = "ready"
        elif snapshot["error"]:
            status = "error"
        else:
            status = "booting"
        hosted = None
        if self.hosted_status is not None:
            hosted = {
                "state": str(self.hosted_status.state),
                "reason": self.hosted_status.reason,
                "base_url": self.hosted_status.base_url,
                "checked_utc": self.hosted_status.checked_utc,
            }
        hero = self.hero_summary()
        snapshot.update(
            {
                "status": status,
                "space_id": self.env.get("SPACE_ID", "").strip(),
                "started_utc": self.started_utc,
                "hardware": self.hardware,
                "host": {"ok": self.floor_ok, "reason": self.floor_reason},
                "families": {
                    "loaded": sorted(self.kernels),
                    "failed": {
                        name: error.code for name, error in sorted(self.kernel_errors.items())
                    },
                },
                "hero": hero,
                "facts": self.live_facts(hero),
                "killswitch": self.killswitch.snapshot(),
                "lane": self.lane.stats(),
                "hosted": hosted,
                "webhook": {"path": self.hook.path, "public": bool(self.hook.url())},
            }
        )
        return snapshot

    def live_facts(self, hero: dict[str, Any] | None) -> dict[str, Any]:
        """`facts` as `/health` serves it: the boot record (`compute_facts`, what `facts.json`
        holds) with the two entries that move after boot read now.

        `hero` is the tracker's current state — the same record the snapshot's `hero` carries
        — so `facts.hero` and `hero` never disagree once a background attempt or a visitor's
        run of the card example has recorded (the file keeps the hero as it stood when the
        facts stage ran: boot's own record, which is what it documents). `mcp_tools` stays the
        installed registry's count when there is one; with none installed the boot record
        holds null, and the pages count the hosted endpoint's tools list live
        (`try_tab.mcp_tool_count`) — so the last live read this container made rides here,
        with its source and stamp (round 11: `140 MCP tools · live` on the page beside a null
        in the facts). Empty before the facts stage."""
        facts = dict(self.facts)
        if not facts:
            return facts
        if "hero" in facts:
            facts["hero"] = hero
        if facts.get("mcp_tools") is None:
            from tabs import try_tab

            live = try_tab.last_live_mcp_read()
            if live is not None:
                count, stamp = live
                facts["mcp_tools"] = count
                facts["mcp_tools_source"] = MCP_TOOLS_LIVE
                facts["mcp_tools_read_utc"] = stamp
        return facts

    def status_tile(self) -> dict[str, Any]:
        """The compact record another Space's tile reads: what is warm here, measured when."""
        hero = self.hero_summary()
        return {
            "space_id": self.env.get("SPACE_ID", "").strip(),
            "ready": self.ready,
            "build": self.facts.get("shared_sha", ""),
            "git_sha": self.facts.get("git_sha", ""),
            "families_loaded": sum(1 for k in self.kernels.values() if not k.is_umbrella),
            "function_count": self.facts.get("function_count"),
            "functions_loaded": self.facts.get("functions_loaded"),
            "hero": hero,
            "hardware": self.hardware,
            "measured_utc": (
                hero["ts_utc"] if hero and hero["status"] == bench.STATUS_MEASURED else None
            ),
            "generated_utc": utc_stamp(),
        }


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def _below_floor(families: Iterable[str], reason: str) -> hubkernel.Preload:
    """A finished `Preload` in which every family failed with the host-floor code."""
    outcome = hubkernel.Preload()
    for family in families:
        outcome.errors[hubkernel.short_family(family)] = hubkernel.HubKernelUnavailable(
            HOST_FLOOR_CODE, reason
        )
    outcome.done.set()
    return outcome


def _mcp_tool_count() -> int | None:
    """The published MCP tool count from the installed registry, or None when not installed."""
    try:
        from algenta_mcp.registry import TOOLS
    except ImportError:
        return None
    try:
        return len(TOOLS)
    except TypeError:
        return None


def _hardware_id() -> str:
    """The twelve-hex machine class (`tabs.common.hardware_id`): CPU quota and architecture —
    the id `qualified.json` and the board rows are attributed by."""
    from tabs import common

    return common.hardware_id()


def compute_facts(state: BootState, *, root: Path | str | None = None) -> dict[str, Any]:
    """`facts.json` for this container: versions, stamps, every count from what loaded."""
    record = facts_mod.compute_facts(DIST_NAMES, env=state.env, root=root or APP_DIR)
    kernels: dict[str, Any] = {}
    functions_loaded = 0
    modules_loaded = 0
    catalogue: int | None = None
    catalogue_modules: int | None = None
    for family, loaded in sorted(state.kernels.items()):
        described = hubkernel.describe(loaded)
        # what executes a call: the compiled Mojo library, read from the package and the live
        # ctypes handle (`hubkernel.native_proof`); the verifier fails a family without it
        proofs = hubkernel.native_proofs(loaded)  # keyed by the package family name
        native = next(iter(proofs.values()), None) if len(proofs) == 1 else None
        kernels[family] = {
            "repo_id": loaded.repo_id,
            "variant": loaded.variant,
            "native": native if not loaded.is_umbrella else dict(proofs),
            **loaded.provenance(),
            "load_s": round(loaded.load_s, 3),
            "warmup_ms": None if loaded.warmup_ms is None else round(loaded.warmup_ms, 3),
            "functions": described["function_count"],
            "modules": len(described["modules"]),
            "excluded": len(described["excluded"]),
        }
        if loaded.is_umbrella:
            catalogue = described["function_count"]
            catalogue_modules = len(described["modules"])
        else:
            functions_loaded += described["function_count"]
            modules_loaded += len(described["modules"])
    mojo_versions = sorted(
        {
            str(k["native"].get("mojo_version"))
            for k in kernels.values()
            if isinstance(k.get("native"), dict) and k["native"].get("mojo_version")
        }
    )
    record.update(
        {
            "kernels": kernels,
            "mojo_version": mojo_versions[0]
            if len(mojo_versions) == 1
            else " / ".join(mojo_versions),
            "families_loaded": sorted(f for f, k in state.kernels.items() if not k.is_umbrella),
            "families_failed": {
                name: error.code for name, error in sorted(state.kernel_errors.items())
            },
            "families_published": len(hubkernel.TRUST) - 1,
            "trust_repos": len(hubkernel.TRUST),
            "functions_loaded": functions_loaded,
            "modules_loaded": modules_loaded,
            "catalogue_functions": catalogue,
            "catalogue_modules": catalogue_modules,
            "function_count": catalogue if catalogue is not None else functions_loaded,
            "module_count": catalogue_modules if catalogue_modules is not None else modules_loaded,
            "umbrella_loaded": catalogue is not None,
            "variants": sorted({k.variant for k in state.kernels.values()}),
            "revision_notes": [
                k.revision_note() for _, k in sorted(state.kernels.items()) if not k.pinned
            ],
            "mcp_tools": _mcp_tool_count(),
            "hero": state.hero_summary(),
            "hardware": state.hardware,
            "hardware_id": _hardware_id(),
            "host_floor": {"ok": state.floor_ok, "reason": state.floor_reason},
            "rulebook": bench.RULEBOOK_VERSION,
            "killswitch_url": state.killswitch.url,
        }
    )
    return record


def functions_loaded(facts: Mapping[str, Any]) -> int:
    """The functions this container runs, from the facts record; 0 before the facts stage."""
    count = facts.get("functions_loaded")
    return count if isinstance(count, int) and not isinstance(count, bool) and count > 0 else 0


def families_loaded(facts: Mapping[str, Any]) -> int:
    """The families this container runs (never the umbrella), from the facts record."""
    loaded = facts.get("families_loaded")
    return len(loaded) if isinstance(loaded, list | tuple) else 0


def families_published(facts: Mapping[str, Any]) -> int:
    published = facts.get("families_published")
    if isinstance(published, int) and not isinstance(published, bool) and published > 0:
        return published
    return len(hubkernel.TRUST) - 1


def headline(facts: Mapping[str, Any]) -> str:
    """`5,683 compiled Mojo kernels` — the functions loaded here, never the catalogue's count.

    The header, the Hub tile and the boot card read this one number, so a container that lost
    a family says the smaller truth everywhere; `Compiled Mojo kernels` before anything
    loaded.
    """
    count = functions_loaded(facts)
    # Apple states the fact and stops (owner, round 11): no ", live" appended — the subline
    # says "Running on this machine."
    text = f"{count:,} compiled Mojo kernels" if count else "Compiled Mojo kernels"
    return shell.check_copy(text, max_words=shell.HEADLINE_WORDS, what="headline")


def families_summary(facts: Mapping[str, Any]) -> str:
    """`18 of 19 families loaded` when one is missing, `19 families loaded` when none is."""
    loaded, published = families_loaded(facts), families_published(facts)
    noun = "family" if loaded == 1 else "families"
    if loaded < published:
        return f"{loaded} of {published} families loaded"
    return f"{loaded} {noun} loaded"


def kernels_summary(outcome: hubkernel.Preload) -> str:
    """The kernels stage in one line: families first, the umbrella named once, failures by code.

    `19 families and the umbrella warm in 2.5 s`, or `18 of 19 families and the umbrella loaded
    in 5.6 s; llm: variant_unavailable` — the umbrella is never counted as a family.
    """
    families = [k for k in outcome.loaded.values() if not k.is_umbrella]
    umbrella_loaded = any(k.is_umbrella for k in outcome.loaded.values())
    failed = {
        bare(name): error
        for name, error in outcome.errors.items()
        if hubkernel.short_family(name) != hubkernel.UMBRELLA_FAMILY
    }
    total = len(families) + len(failed)
    noun = "family" if total == 1 else "families"
    if failed:
        head = f"{len(families)} of {total} {noun}"
    else:
        head = f"{total} {noun}"
    with_umbrella = " and the umbrella" if umbrella_loaded else ""
    warm = bool(families) and all(k.warm for k in families) and not failed
    state = "warm" if warm else "loaded"
    text = f"{head}{with_umbrella} {state} in {outcome.elapsed_s:.1f} s"
    if outcome.errors:
        codes = ", ".join(
            f"{bare(name)}: {error.code}" for name, error in sorted(outcome.errors.items())
        )
        text += f"; {codes}"
    return text


def facts_path(env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    configured = env.get(FACTS_PATH_ENV, "").strip()
    return Path(configured) if configured else APP_DIR / FACTS_FILE


def _stage_kernels(
    state: BootState,
    families: Iterable[str],
    *,
    get_kernel: Callable[..., Any] | None,
    warm: bool,
    clock: Callable[[], float],
) -> None:
    registry = state.registry
    if not state.floor_ok:
        state.preload = _below_floor(families, state.floor_reason)
        registry.fail(STAGE_KERNELS, f"held: {state.floor_reason}")
        return

    def progress(family: str, event: str, detail: str) -> None:
        registry.set(STAGE_KERNELS, boot.RUNNING, f"{family}: {event} · {detail}")

    if hub_offline(state.env):
        pruned = prune_tree_listings()
        if pruned:
            log.info("offline boot: %d cached tree listings pruned", len(pruned))
    outcome = hubkernel.preload(
        families,
        before_launch=True,
        warm=warm,
        progress=progress,
        get_kernel=get_kernel,
        clock=clock,
    )
    state.preload = outcome
    if not outcome.loaded:
        registry.fail(STAGE_KERNELS, kernels_summary(outcome))
    else:
        registry.done(STAGE_KERNELS, kernels_summary(outcome))


def _stage_hero(
    state: BootState,
    hero_kwargs: Mapping[str, Any],
    *,
    attempts: int = HERO_ATTEMPTS,
    backoff_s: tuple[float, ...] = HERO_BACKOFF_S,
    retry_s: float = HERO_RETRY_S,
    sleep: Sleep = time.sleep,
) -> None:
    """Measure the hero; retry a noisy verdict with backoff, then hand over to the tracker."""
    registry = state.registry
    kernel = state.kernel(HERO_FAMILY)
    if kernel is None:
        error = state.kernel_errors.get(HERO_FAMILY)
        code = error.code if error is not None else "kernel_not_loaded"
        registry.fail(STAGE_HERO, f"{HERO_FAMILY} did not load · {code}")
        return
    from tabs import try_tab

    def measure() -> HeroResult:
        return try_tab.measure_hero(kernel, state.lane, hardware=state.hardware, **hero_kwargs)

    tracker = try_tab.HeroTracker(measure)
    state.hero_tracker = tracker
    rounds = max(1, int(attempts))
    for index in range(rounds):
        hero = tracker.attempt()
        if hero.cell.status not in try_tab.TRANSIENT_STATUSES or index + 1 >= rounds:
            break
        delay = backoff_s[min(index, len(backoff_s) - 1)] if backoff_s else 0.0
        registry.set(
            STAGE_HERO,
            boot.RUNNING,
            f"attempt {index + 1}: {hero.cell.reason or hero.cell.status} · again in {delay:g} s",
        )
        if delay > 0:
            sleep(delay)
    boot_attempts = tracker.attempts
    boot_hero = tracker.hero
    tracker.start(retry_s)  # nothing to do once measured, or with no interval
    registry.done(
        STAGE_HERO, hero_detail(tracker, boot_attempts=boot_attempts, boot_hero=boot_hero)
    )
    if isinstance(registry, FlagshipRegistry):
        # the row stays true after boot: a background attempt that records, or a visitor's run
        # of the card example, replaces the frozen verdict in every later snapshot (/health, the
        # boot card) — and says it was measured after boot
        registry.detail_hooks[STAGE_HERO] = lambda: hero_detail(
            tracker, boot_attempts=boot_attempts, boot_hero=boot_hero
        )


#: The hero row's clause once a background attempt, not boot, recorded the measurement. It is
#: followed by the measurement's own clock (`after_boot_clause`: `measured after boot ·
#: 10:12 UTC`), so the row's time and the foot's `finished <boot stamp>` cannot be read as one
#: moment (launch review round 12).
MEASURED_AFTER_BOOT = "measured after boot"
#: The hero row before any attempt has run (a tracker built with none).
HERO_NOT_ATTEMPTED = "no attempt has run"


#: The clock inside a fleet stamp (`2026-09-24 10:12 UTC` → `10:12`).
_CLOCK_RE = re.compile(r"\b\d{4}-\d{2}-\d{2} (\d{2}:\d{2}) UTC\b")


def after_boot_clause(ts_utc: str) -> str:
    """`measured after boot · 10:12 UTC` — the qualifier with the measurement's own clock, read
    from the cell's fleet stamp (`YYYY-MM-DD HH:MM UTC`); a stamp that is not one leaves the
    qualifier alone, so the row never prints a clock it did not read."""
    clock = _CLOCK_RE.search(ts_utc or "")
    if clock is None:
        return MEASURED_AFTER_BOOT
    return f"{MEASURED_AFTER_BOOT} · {clock.group(1)} UTC"


def hero_detail(tracker: Any, *, boot_attempts: int | None = None, boot_hero: Any = None) -> str:
    """The hero row in words, from the tracker as it is now — the same sentence at the stage's
    end and every time `/health` or the boot card is read later.

    Measured: `0.12 ms per kernel call, n = 21 × 83 calls · statsmodels agrees · attempt 6` — the n
    chip in the Try card's own words (`try_tab.repeats_label`: `n = 21` when each sample was one
    call, `n = 21 × k calls` under rulebook v0.4) — plus
    `· measured after boot · 10:12 UTC` (`after_boot_clause`, the measurement's own clock) when
    the figure is not boot's own: more attempts have run than boot's (`boot_attempts`), or a
    visitor's run of the card example was recorded since and the hero is no longer the one boot
    ended with (`boot_hero`). Not
    measured: the rulebook's verdict in human words and the attempt count, plus `· measured
    again every 60 s until it records` only while the background thread is still trying; once
    it has stopped without recording (a final verdict), the verdict alone.
    """
    from tabs import try_tab

    hero = tracker.hero
    if hero is None:
        return HERO_NOT_ATTEMPTED
    cell = hero.cell
    tries = "" if tracker.attempts == 1 else f" · attempt {tracker.attempts}"
    if cell.measured and hero.kernel_ms is not None:
        parity = "" if hero.parity is None else f" · {hero.parity.reference} agrees"
        later_attempt = boot_attempts is not None and tracker.attempts > boot_attempts
        replaced = boot_hero is not None and hero is not boot_hero
        after = f" · {after_boot_clause(cell.ts_utc)}" if later_attempt or replaced else ""
        return (
            f"{bench_ms(hero.kernel_ms)} per kernel call, {try_tab.repeats_label(cell)}"
            f"{parity}{tries}{after}"
        )
    detail = f"{try_tab.human_reason(cell.reason or cell.status)}{tries}"
    if tracker.running and tracker.pending and tracker.retry_s > 0:
        detail += f" · measured again every {tracker.retry_s:g} s until it records"
    return detail


def bench_ms(ms: float) -> str:
    """`0.41 ms` — the card formatter, so the boot card and the hero agree to the digit."""
    from algenta_spaces.cards import fmt_ms

    return fmt_ms(ms)


def _stage_facts(state: BootState, *, root: Path | str | None, write: bool) -> None:
    record = compute_facts(state, root=root)
    if write:
        target = facts_path(state.env)
        try:
            facts_mod.write_facts(target, record)
            record["facts_path"] = str(target)
        except OSError as exc:
            log.warning("facts.json not written to %s: %s", target, exc)
            record["facts_path"] = None
    state.facts = record
    families = len(record["families_loaded"])
    noun = "family" if families == 1 else "families"
    detail = f"{record['functions_loaded']:,} functions in {families} {noun}"
    catalogue = record.get("catalogue_functions")
    if isinstance(catalogue, int) and catalogue != record["functions_loaded"]:
        detail += f" · {catalogue:,} in the published catalogue"
    state.registry.done(STAGE_FACTS, detail)


def _stage_flags(state: BootState) -> None:
    state.killswitch.start()
    snapshot = state.killswitch.snapshot()
    if snapshot["missed"]:
        detail = "flag file unreachable · spend features off"
    else:
        count = len(snapshot["flags"])
        detail = f"{count} {'flag' if count == 1 else 'flags'} read"
    state.registry.done(STAGE_FLAGS, detail)


#: The hosted lane's states in words, for the boot row (the code stays on the Governed card).
HOSTED_STATE_WORDS: Mapping[str, str] = {
    str(hosted_api.ConfigState.READY): "connected",
    str(hosted_api.ConfigState.NOT_CONFIGURED): "not configured",
    str(hosted_api.ConfigState.UNAVAILABLE): "unavailable",
    str(hosted_api.ConfigState.RATE_LIMITED): "rate limited",
}


#: The boot row's clause when the SDK client is not installed (`tabs.gov_tab.client_missing`).
CLIENT_MISSING_WORDS = (
    "the hosted client is not installed in this container, so the governed lane is off"
)


def client_missing(status: hosted_api.HostedStatus) -> bool:
    """`tabs.gov_tab.client_missing` — the one rule for a probe that failed before the SDK
    client existed, imported lazily as the hero row imports `try_tab`."""
    from tabs import gov_tab

    return gov_tab.client_missing(status)


def hosted_detail(status: hosted_api.HostedStatus) -> str:
    """The hosted row in words: `not configured · no API key is set for this Space, so the
    governed lane is off` — the state as a phrase, then the reason as a clause (its first letter
    lowered unless it opens an initialism, its final period dropped); a connected lane says
    the reason alone, since `connected · connected …` would say it twice."""
    words = HOSTED_STATE_WORDS.get(str(status.state), str(status.state).replace("_", " "))
    reason = " ".join(str(status.reason or "").split()).rstrip(".")
    if client_missing(status):
        # the probe failed before the SDK client existed: the Governed tab's quiet card and
        # this row say the same thing, in words, never the exception's name
        words = HOSTED_STATE_WORDS[str(hosted_api.ConfigState.NOT_CONFIGURED)]
        reason = CLIENT_MISSING_WORDS
    if reason and not (len(reason) > 1 and reason[1].isupper()):
        reason = reason[0].lower() + reason[1:]
    if not reason:
        return words
    if status.state is hosted_api.ConfigState.READY:
        return reason
    return f"{words} · {reason}"


def _stage_hosted(state: BootState, *, probe: bool) -> None:
    hosted = hosted_api.HostedGoverned(env=state.env)
    state.hosted = hosted
    if probe or not hosted.configured:
        try:
            status = hosted.status()
        except Exception as exc:  # the lane normalises SDK errors; anything else is reported
            status = hosted_api.HostedStatus(
                hosted_api.ConfigState.UNAVAILABLE,
                f"{type(exc).__name__}: {_first_line(exc)}",
                hosted.base_url,
                "",
                utc_stamp(),
            )
    else:
        status = hosted_api.HostedStatus(
            hosted_api.ConfigState.UNAVAILABLE,
            "The hosted API was not probed at boot.",
            hosted.base_url,
            "",
            utc_stamp(),
        )
    state.hosted_status = status
    state.registry.done(STAGE_HOSTED, hosted_detail(status))


def run_boot(
    *,
    env: Mapping[str, str] | None = None,
    families: Iterable[str] = PRELOAD,
    get_kernel: Callable[..., Any] | None = None,
    warm: bool = True,
    fetch: killswitch_mod.Fetch | None = None,
    killswitch_url: str | None = None,
    hero_kwargs: Mapping[str, Any] | None = None,
    hero_attempts: int = HERO_ATTEMPTS,
    hero_backoff_s: tuple[float, ...] = HERO_BACKOFF_S,
    hero_retry_s: float = HERO_RETRY_S,
    sleep: Sleep = time.sleep,
    probe_hosted: bool = True,
    write_facts: bool = True,
    facts_root: Path | str | None = None,
    hardware: str | None = None,
    floor: tuple[bool, str] | None = None,
    lane: lane_mod.Lane | None = None,
    clock: Callable[[], float] = time.perf_counter,
    registry_clock: Callable[[], float] = time.time,
    space_runtime: SpaceRuntime | None = None,
) -> BootState:
    """Run every stage in order and return the state; a failing stage is recorded, not raised.

    Every external dependency is injectable: `get_kernel` (the Hub loader), `fetch` (the flag
    file), `hero_kwargs` (forwarded to `try_tab.measure_hero`, e.g. `reference`, `clock`,
    `loadavg`, `quota`, `repeats`), `hero_attempts` / `hero_backoff_s` / `hero_retry_s` /
    `sleep` (the noisy-hero retry policy; `hero_retry_s=0` keeps no background thread),
    `probe_hosted` (skip the network probe), `floor` (the host verdict), `space_runtime` (the
    Hub's answer for the Space's hardware tier). The defaults are the real ones.
    """
    hf_ua_shim.apply()
    from_process = env is None
    # the boot's own copy: the host stage may add the Space tier the Hub reports (`space_tier`)
    env = dict(os.environ if env is None else env)
    registry = FlagshipRegistry(STAGES, clock=registry_clock)
    url = (killswitch_url or env.get(KILLSWITCH_ENV, "").strip()) or DEFAULT_KILLSWITCH_URL
    switch = killswitch_mod.KillSwitch(
        url, fetch=killswitch_mod.urllib_fetch if fetch is None else fetch
    )
    state = BootState(
        registry=registry,
        lane=lane_mod.Lane() if lane is None else lane,
        limits=limits_mod.Limits(NATIVE_POLICY),
        killswitch=switch,
        hook=webhook.make_hook(env),
        env=env,
        started_utc=utc_stamp(),
    )

    registry.start(STAGE_HOST)
    ok, reason = hubkernel.host_floor_ok() if floor is None else floor
    state.floor_ok, state.floor_reason = ok, reason
    tier = space_tier(env, runtime=space_runtime)
    if tier:
        env["SPACE_HARDWARE"] = tier
        if from_process:
            # every later reader of the process environment (the rulebook footer's default)
            # sees the same tier the boot state carries
            os.environ["SPACE_HARDWARE"] = tier
    # the machine line every card prints, after the tier is known
    state.hardware = bench.hardware_footer(env) if hardware is None else hardware
    (registry.done if ok else registry.fail)(STAGE_HOST, reason)

    steps: tuple[tuple[str, Callable[[], None]], ...] = (
        (
            STAGE_KERNELS,
            lambda: _stage_kernels(state, families, get_kernel=get_kernel, warm=warm, clock=clock),
        ),
        (
            STAGE_HERO,
            lambda: _stage_hero(
                state,
                dict(hero_kwargs or {}),
                attempts=hero_attempts,
                backoff_s=tuple(hero_backoff_s),
                retry_s=hero_retry_s,
                sleep=sleep,
            ),
        ),
        (STAGE_FACTS, lambda: _stage_facts(state, root=facts_root, write=write_facts)),
        (STAGE_FLAGS, lambda: _stage_flags(state)),
        (STAGE_HOSTED, lambda: _stage_hosted(state, probe=probe_hosted)),
    )
    for stage_id, step in steps:
        registry.start(stage_id)
        try:
            step()
        except Exception as exc:  # reported on the card and in /health, never swallowed
            log.exception("boot stage %s failed", stage_id)
            registry.fail(stage_id, f"{type(exc).__name__}: {_first_line(exc)}")
    log.info("boot finished in %.1f s: %s", registry.snapshot()["elapsed_s"], state.summary())
    return state


# ---------------------------------------------------------------------------
# The image's cache tool: bake online, verify offline
# ---------------------------------------------------------------------------


#: `(space_id, token) -> tier` — the Hub's answer for a Space's current hardware.
SpaceRuntime = Callable[[str, str | None], str]
#: One call at boot; the host stage waits this long for the Hub at most.
TIER_TIMEOUT_S = 5.0
#: The Hub, when the environment names no other (`HF_ENDPOINT`: a mirror, a proxy).
HF_ENDPOINT_DEFAULT = "https://huggingface.co"


def hub_endpoint(env: Mapping[str, str]) -> str:
    """`HF_ENDPOINT` from `env`, else `HF_ENDPOINT_DEFAULT`; no trailing slash."""
    return (env.get("HF_ENDPOINT", "").strip() or HF_ENDPOINT_DEFAULT).rstrip("/")


def hub_space_hardware(
    space_id: str, token: str | None = None, *, endpoint: str = HF_ENDPOINT_DEFAULT
) -> str:
    """The tier the Hub runs `space_id` on right now (`cpu-upgrade`, `l4x1`), from the Space
    runtime endpoint — the current hardware, else the requested one while it changes; "" when
    the Hub does not say. A private Space answers only with its token. `endpoint` is the Hub
    the caller read from its own environment (`hub_endpoint`), never `os.environ` here: the
    token goes to the Hub the injected environment names (Codna review on #1150)."""
    import json
    import urllib.request
    from urllib.parse import quote, urlsplit

    url = f"{endpoint.rstrip('/')}/api/spaces/{quote(space_id, safe='/')}/runtime"
    if urlsplit(url).scheme != "https":
        raise ValueError("the Hub endpoint must be https")
    headers = {"Accept": "application/json", "User-Agent": "algenta-spaces-boot"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # S310: the scheme is checked above, so only https ever reaches urlopen.
    request = urllib.request.Request(url, headers=headers, method="GET")  # noqa: S310
    with urllib.request.urlopen(request, timeout=TIER_TIMEOUT_S) as response:  # noqa: S310
        body = json.loads(response.read().decode("utf-8"))
    hardware = body.get("hardware") if isinstance(body, dict) else None
    if not isinstance(hardware, dict):
        return ""
    return str(hardware.get("current") or hardware.get("requested") or "").strip()


def space_tier(env: Mapping[str, str], *, runtime: SpaceRuntime | None = None) -> str:
    """The Space's hardware tier for every card foot (rulebook rule 9): `SPACE_HARDWARE` when
    the environment states it (a local run may), else the Hub's own answer for `SPACE_ID` —
    never a tier typed into the code. "" outside a Space or when the Hub does not answer in
    `TIER_TIMEOUT_S`; the foot then names no tier. `HF_HUB_OFFLINE` (the image's runtime
    default, for the baked kernel cache) does not apply: the Space runtime endpoint is not the
    file cache, and the Ecosystem tab reads the Hub live under the same flag."""
    tier = env.get("SPACE_HARDWARE", "").strip()
    if tier:
        return tier
    space_id = env.get("SPACE_ID", "").strip()
    if not space_id:
        return ""
    ask = (
        functools.partial(hub_space_hardware, endpoint=hub_endpoint(env))
        if runtime is None
        else runtime
    )
    try:
        tier = ask(space_id, env.get("HF_TOKEN", "").strip() or None).strip()
    except Exception as exc:  # the foot names no tier rather than a guessed one
        log.warning("space tier: the Hub did not answer for %s: %s", space_id, _first_line(exc))
        return ""
    log.info("space tier from the Hub: %s", tier or "(none)")
    return tier


def hub_offline(env: Mapping[str, str] | None = None) -> bool:
    """True when `HF_HUB_OFFLINE` is set to a truthy value (the image's runtime default)."""
    env = os.environ if env is None else env
    return env.get("HF_HUB_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def cache_dir(env: Mapping[str, str] | None = None) -> Path:
    """Where `kernels` keeps snapshots: `KERNELS_CACHE`, else huggingface_hub's cache."""
    env = os.environ if env is None else env
    configured = env.get("KERNELS_CACHE", "").strip()
    if configured:
        return Path(configured)
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def repo_folder(repo_id: str) -> str:
    """`kernels--thyn-ai--algenta-stats`: the cache folder of a kernel repository."""
    return "kernels--" + repo_id.replace("/", "--")


def prune_tree_listings(
    repos: Iterable[str] = hubkernel.TRUST, *, root: Path | str | None = None
) -> list[Path]:
    """Remove the cached Hub tree listings of the baked repositories; returns what was removed.

    `kernels` 0.17.1 resolves an offline load with `snapshot_download(local_files_only=True)`
    and only its bytecode ignore patterns, so `huggingface_hub` checks the cached snapshot
    against the repository's whole tree listing and refuses a variant-only cache as
    incomplete (`IncompleteSnapshotError`, hundreds of other platforms' files "missing").
    Without a cached listing the same call returns the snapshot folder, which holds exactly
    the variant this image runs. The listing is a cache index, nothing the kernels read;
    `--verify-cache` proves every family still loads offline after the prune.
    """
    base = cache_dir() if root is None else Path(root)
    removed: list[Path] = []
    for repo in repos:
        trees = base / repo_folder(repo) / "trees"
        if not trees.is_dir():
            continue
        for listing in sorted(trees.glob("*.json")):
            listing.unlink()
            removed.append(listing)
    return removed


def record_version_ref(variant_path: Path | str, version: int) -> Path:
    """Write `refs/v<version>` = the snapshot commit `variant_path` sits in; returns the ref file.

    `install_kernel` resolves `version=1` through the Hub API and downloads the commit, but
    writes no tag file; the offline resolver only reads `refs/v*`. Recording the commit the
    online resolution chose is what lets `HF_HUB_OFFLINE=1` answer the same `version=1`.
    """
    path = Path(variant_path)
    parts = path.resolve().parts
    try:
        snapshots = len(parts) - 1 - parts[::-1].index("snapshots")
    except ValueError:
        raise ValueError(f"not a cache snapshot path: {path}") from None
    commit = parts[snapshots + 1]
    if not is_sha(commit):
        raise ValueError(f"no commit hash in {path}")
    ref = Path(*parts[:snapshots]) / "refs" / f"v{version}"
    ref.parent.mkdir(parents=True, exist_ok=True)
    if ref.is_file() and ref.read_text(encoding="utf-8").strip() == commit:
        return ref
    ref.write_text(commit, encoding="utf-8")
    return ref


def bake_cache(
    repos: Iterable[str] = hubkernel.TRUST,
    *,
    install: Callable[..., Any] | None = None,
    backend: str = hubkernel.DEFAULT_BACKEND,
    version: int = hubkernel.DEFAULT_VERSION,
    progress: Progress = log.info,
) -> list[Path]:
    """`kernels.install_kernel` for every repository, record `refs/v1`, prune the tree listings."""
    hf_ua_shim.apply()
    if install is None:
        from kernels import install_kernel

        install = install_kernel
    trusted = list(hubkernel.TRUST)
    paths: list[Path] = []
    t0 = time.perf_counter()
    for repo in repos:
        t1 = time.perf_counter()
        path = Path(install(repo, version=version, backend=backend, trust_remote_code=trusted))
        ref = record_version_ref(path, version)
        paths.append(path)
        progress(
            f"{repo}: {path.name} @ {ref.read_text(encoding='utf-8')[:7]}"
            f" in {time.perf_counter() - t1:.1f} s"
        )
    pruned = prune_tree_listings(repos)
    progress(
        f"{len(paths)} repositories baked in {time.perf_counter() - t0:.1f} s; "
        f"{len(pruned)} tree listings pruned"
    )
    return paths


def verify_cache(
    families: Iterable[str] = PRELOAD,
    *,
    get_kernel: Callable[..., Any] | None = None,
    progress: Progress = log.info,
) -> dict[str, Any]:
    """Load every family from the cache and count the catalogue; raises when one cannot load.

    Run with `HF_HUB_OFFLINE=1` this is the proof that the image never downloads at boot.
    """
    hf_ua_shim.apply()
    outcome = hubkernel.preload(families, before_launch=True, warm=False, get_kernel=get_kernel)
    for family, loaded in sorted(outcome.loaded.items()):
        pinned = "pinned" if loaded.pinned else f"revision {loaded.snapshot_sha[:7]} (not capped)"
        progress(f"{family}: {loaded.variant} · {pinned} · {loaded.load_s:.2f} s")
    if outcome.errors:
        failed = "; ".join(
            f"{f}: {e.code} — {e.message}" for f, e in sorted(outcome.errors.items())
        )
        raise RuntimeError(f"{len(outcome.errors)} families did not load from the cache: {failed}")
    unpinned = sorted(f for f, k in outcome.loaded.items() if not k.pinned)
    if unpinned:
        # `version=1` follows the Hub's v1 tag; a family republished since the capabilities file
        # was written loads a newer revision. The footer prints the loaded one, so this is a note.
        log.warning("v1 resolves past the recorded capped revision for: %s", ", ".join(unpinned))
    umbrella = outcome.loaded.get(hubkernel.UMBRELLA_FAMILY)
    catalogue = hubkernel.describe(umbrella)["function_count"] if umbrella else None
    summary = {
        "families": sorted(outcome.loaded),
        "variants": sorted({k.variant for k in outcome.loaded.values()}),
        "function_count": catalogue,
        "unpinned": unpinned,
        "elapsed_s": round(outcome.elapsed_s, 2),
    }
    progress(f"cache verified: {len(outcome.loaded)} families, {catalogue} functions")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the flagship's boot and image-cache tool")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--bake", action="store_true", help="install the twenty repositories")
    action.add_argument(
        "--verify-cache", action="store_true", help="load every family from the cache"
    )
    action.add_argument("--health", action="store_true", help="run boot and print /health")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.bake:
        bake_cache()
        return 0
    if args.verify_cache:
        verify_cache()
        return 0
    import json

    state = run_boot()
    sys.stdout.write(json.dumps(state.health(), indent=2, sort_keys=True, default=str) + "\n")
    return 0 if state.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
