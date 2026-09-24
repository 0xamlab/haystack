"""apps/spaces/algenta — the app shell, boot sequence, permalink, user-agent shim, image and card.

Everything here runs offline against fakes: a fake `get_kernel` that serves the stats
contract fixture and the published z-test result, a fake flag-file fetch, no hosted probe.
The Gradio page is built for real when gradio is installed (`pytest.importorskip`), and the
FastAPI routes are exercised through Starlette's test client.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _rules import (
    FAKE_WORDS,
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import bench, hubkernel, killswitch, shell

REPO = Path(__file__).resolve().parents[2]
APP_DIR = REPO / "apps" / "spaces" / "algenta"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
STATS_FIXTURE = FIXTURES / "contract_algenta_stats.json"
STATS_REPO = "thyn-ai/algenta-stats"
STATS_SHA = hubkernel.FROZEN_CAPPED_V1_SHAS[STATS_REPO]
VARIANT = "torch25-cpu-aarch64-darwin"
#: The published result of `ab_testing.z_test_proportions(50, 1000, 65, 1000)`.
Z_EXPECTED = [-1.440793230951582, 0.1496431923825119]
TABS = ("try", "play", "race", "llm", "gov", "eco")
STAMP = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

boot_sequence = importlib.import_module("boot_sequence")
permalink = importlib.import_module("permalink")
hf_ua_shim = importlib.import_module("hf_ua_shim")
app_mod = importlib.import_module("app")
tabs_pkg = importlib.import_module("tabs")


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeKernelModule(ModuleType):
    """What `get_kernel` returns, reduced to what the loader, the warm-up and the hero touch."""

    def __init__(self, repo_id: str, record: dict, sha: str) -> None:
        super().__init__(repo_id.split("/")[1].replace("-", "_"))
        folder = "kernels--" + repo_id.replace("/", "--")
        self.__file__ = f"/cache/hub/{folder}/snapshots/{sha}/build/{VARIANT}/__init__.py"
        self.CONTRACT = record["contract"]
        self.excluded_functions = list(record["excluded_functions"])
        self.calls: list[tuple[str, str, list]] = []

    def execute(self, module: str, function: str, args: Any = None) -> Any:
        self.calls.append((module, function, list(args or [])))
        if (module, function) == ("ab_testing", "z_test_proportions"):
            return list(Z_EXPECTED)
        raise ValueError(f"{module}.{function} is not served by this fake")


class Tick:
    """A clock that advances half a millisecond per read: every timed sample is equal."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        self.now += 0.0005
        return self.now


def fake_fetch(url: str, etag: str | None) -> killswitch.FetchResult:
    body = json.dumps({"flags": {"kernels": True, "provider": False, "races": True}}).encode()
    return killswitch.FetchResult(200, body, "etag-1")


def dead_fetch(url: str, etag: str | None) -> killswitch.FetchResult:
    return killswitch.FetchResult(404, None, None)


@pytest.fixture(scope="module")
def stats_record() -> dict:
    return json.loads(STATS_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fake_get_kernel(stats_record: dict):
    served: dict[str, FakeKernelModule] = {}

    def get_kernel(repo_id: str, *, version: int, backend: str, trust_remote_code: Any):
        assert version == 1 and backend == "cpu"
        assert STATS_REPO in trust_remote_code and len(trust_remote_code) == len(hubkernel.TRUST)
        if repo_id == STATS_REPO:
            served.setdefault(repo_id, FakeKernelModule(repo_id, stats_record, STATS_SHA))
            return served[repo_id]
        raise FileNotFoundError(f"Cannot find a local snapshot for {repo_id}")

    return get_kernel


def _env(tmp: Path, **extra: str) -> dict[str, str]:
    env = {"ALGENTA_FACTS_PATH": str(tmp / "facts.json")}
    env.update(extra)
    return env


def _boot(tmp: Path, get_kernel: Any, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "env": _env(tmp),
        "families": ("stats", "text"),
        "get_kernel": get_kernel,
        "fetch": fake_fetch,
        "hero_kwargs": {"repeats": 5, "loadavg": lambda: 0.0, "quota": 4, "clock": Tick()},
        "probe_hosted": False,
        "facts_root": tmp,
        "hardware": f"test machine · 4 vCPU · rulebook v{bench.RULEBOOK_VERSION}",
        "floor": (True, "test host at the floor"),
    }
    kwargs.update(overrides)
    return boot_sequence.run_boot(**kwargs)


def test_boot_reads_the_space_tier_from_the_hub_never_from_the_code(
    tmp_path: Path, fake_get_kernel: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rulebook rule 9: every foot names the tier — the Hub's answer for this Space at boot,
    read once in the host stage before the machine line is built; the launch review found the
    foot silent because nothing on the Space sets `SPACE_HARDWARE`."""
    monkeypatch.delenv("SPACE_HARDWARE", raising=False)
    asked: list[tuple[str, str | None]] = []

    def runtime(space_id: str, token: str | None) -> str:
        asked.append((space_id, token))
        return "cpu-upgrade"

    st = _boot(
        tmp_path,
        fake_get_kernel,
        env=_env(tmp_path, SPACE_ID="thyn-ai/algenta", HF_TOKEN="hf_test"),
        hardware=None,
        space_runtime=runtime,
    )
    assert asked == [("thyn-ai/algenta", "hf_test")], "one call, with the Space's own token"
    assert st.env["SPACE_HARDWARE"] == "cpu-upgrade"
    assert st.hardware.startswith("Space thyn-ai/algenta · cpu-upgrade · "), st.hardware
    assert st.facts["space_hardware"] == "cpu-upgrade", "the facts stage runs after the host"
    assert "SPACE_HARDWARE" not in os.environ, "an injected environment leaves the process alone"
    host = next(s for s in st.registry.snapshot()["stages"] if s["id"] == "host")
    assert host["state"] == "done"

    # the Hub silent or slow: the foot names no tier — never a guessed one
    def slow(space_id: str, token: str | None) -> str:
        raise TimeoutError("the Hub did not answer")

    quiet = _boot(
        tmp_path,
        fake_get_kernel,
        env=_env(tmp_path, SPACE_ID="thyn-ai/algenta"),
        hardware=None,
        space_runtime=slow,
    )
    assert quiet.hardware.split(" · ")[0] == "Space thyn-ai/algenta" and not quiet.env.get(
        "SPACE_HARDWARE"
    )
    # `space_tier` alone: a stated tier wins without a call; outside a Space nothing is asked;
    # the image's `HF_HUB_OFFLINE=1` (the baked kernel cache) does not silence the lookup — the
    # first staging deploy of this code booted with no tier for exactly that reason

    def boom(space_id: str, token: str | None) -> str:
        raise AssertionError("no call expected")

    assert boot_sequence.space_tier(
        {"SPACE_HARDWARE": " l4x1 ", "SPACE_ID": "x"}, runtime=boom
    ) == ("l4x1")
    assert boot_sequence.space_tier({}, runtime=boom) == ""
    assert boot_sequence.space_tier(
        {"SPACE_ID": "x", "HF_HUB_OFFLINE": "1"}, runtime=lambda s, t: "cpu-upgrade"
    ) == ("cpu-upgrade")
    assert boot_sequence.space_tier({"SPACE_ID": "x"}, runtime=lambda s, t: " t4-small\n") == (
        "t4-small"
    )


def test_hub_space_hardware_reads_the_runtime_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Space runtime endpoint's shape as the Hub serves it (read 2026-09-23):
    `{"stage": "RUNNING", "hardware": {"current": "cpu-basic", "requested": "cpu-basic"}}` —
    the current tier, else the requested one while it changes, "" without either."""
    import urllib.request

    seen: list[Any] = []

    class Response:
        def __init__(self, body: dict[str, Any]) -> None:
            self._body = json.dumps(body).encode("utf-8")

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

    bodies = iter(
        [
            {
                "stage": "RUNNING",
                "hardware": {"current": "cpu-upgrade", "requested": "cpu-upgrade"},
            },
            {"stage": "RUNNING_BUILDING", "hardware": {"current": None, "requested": "l4x1"}},
            {"stage": "STOPPED"},
        ]
    )

    def urlopen(request: Any, timeout: float) -> Response:
        seen.append((request.full_url, dict(request.header_items()), timeout))
        return Response(next(bodies))

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    # Codna review on #1150: the Hub is the caller's `endpoint` (read from the environment it
    # was given), never the process's `HF_ENDPOINT` — the token goes where that environment says
    monkeypatch.setenv("HF_ENDPOINT", "https://process.invalid")
    assert boot_sequence.hub_space_hardware("thyn-ai/algenta-staging", "hf_token") == "cpu-upgrade"
    assert boot_sequence.hub_space_hardware("thyn-ai/algenta") == "l4x1"
    assert boot_sequence.hub_space_hardware("thyn-ai/algenta") == ""
    url, headers, timeout = seen[0]
    assert url == "https://huggingface.co/api/spaces/thyn-ai/algenta-staging/runtime"
    assert headers["Authorization"] == "Bearer hf_token" and timeout == boot_sequence.TIER_TIMEOUT_S
    assert "Authorization" not in seen[1][1], "no token, no header"
    with pytest.raises(ValueError):
        boot_sequence.hub_space_hardware("thyn-ai/algenta", endpoint="http://hub.local")
    assert len(seen) == 3, "a non-https endpoint never reaches urlopen"
    # `space_tier` asks the Hub the injected environment names, with that environment's token
    bodies = iter([{"stage": "RUNNING", "hardware": {"current": "t4-small"}}])
    env = {
        "SPACE_ID": "thyn-ai/algenta",
        "HF_TOKEN": "hf_env",
        "HF_ENDPOINT": "https://hub.mirror/",
    }
    assert boot_sequence.space_tier(env) == "t4-small"
    url, headers, _ = seen[3]
    assert url == "https://hub.mirror/api/spaces/thyn-ai/algenta/runtime"
    assert headers["Authorization"] == "Bearer hf_env"
    assert boot_sequence.hub_endpoint({}) == boot_sequence.HF_ENDPOINT_DEFAULT
    assert (
        boot_sequence.hub_endpoint({"HF_ENDPOINT": " https://hub.mirror/ "}) == "https://hub.mirror"
    )


@pytest.fixture(scope="module")
def state(tmp_path_factory: pytest.TempPathFactory, fake_get_kernel: Any) -> Any:
    tmp = tmp_path_factory.mktemp("flagship")
    booted = _boot(tmp, fake_get_kernel)
    yield booted
    booted.stop()
    booted.lane.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Boot sequence
# ---------------------------------------------------------------------------


def test_boot_runs_every_stage_offline_and_is_ready(state: Any) -> None:
    snapshot = state.registry.snapshot()
    assert [s["id"] for s in snapshot["stages"]] == [sid for sid, _ in boot_sequence.STAGES]
    assert [s["state"] for s in snapshot["stages"]] == ["done"] * 6, snapshot
    assert state.ready and snapshot["error"] is None
    assert set(state.kernels) == {"stats"}
    assert state.kernel_errors["text"].code == "cache_missing"
    assert state.kernels["stats"].warm and state.kernels["stats"].pinned
    assert state.summary().startswith("ready · host=done kernels=done hero=done")


def test_hero_is_measured_through_the_lane_and_checked_against_statsmodels(state: Any) -> None:
    hero = state.hero
    assert hero is not None and hero.cell.measured
    assert hero.result == Z_EXPECTED
    assert hero.kernel_ms is not None and hero.kernel_ms > 0
    assert hero.cell.n == 5 and hero.cell.lanes[0].name == "algenta-stats"
    assert hero.args == {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000}
    assert state.lane.stats()["completed"] >= 1, "the hero cell ran on the native lane"
    if hero.parity is not None:  # statsmodels installed
        assert hero.parity.ok and hero.parity.reference == "statsmodels"
        assert hero.parity.version.startswith("statsmodels==")
    detail = state.registry.snapshot()["stages"][2]["detail"]
    assert "per kernel call" in detail and "n = 5" in detail and "attempt" not in detail
    tracker = state.hero_tracker
    assert tracker.attempts == 1 and tracker.measured is hero and not tracker.running
    assert state.deps().hero_tracker is tracker, "the Try tab reads the tracker from its deps"


class Noisy:
    """A hero measurement that is noisy for the first `noisy` cells and quiet afterwards (v0.6:
    noise is the samples' spread, never the load average). `clock` jitters 1, 2, 3 ms per read
    while a noisy cell runs and ticks evenly afterwards; `tick` is the harness's one load read
    per cell (its end), so it counts the cells."""

    def __init__(self, noisy: int) -> None:
        self.noisy = noisy
        self.cells = 0
        self.reads = 0
        self.now = 1000.0

    STEPS = (
        0.001,
        0.003,
        0.002,
        0.003,
        0.001,
        0.002,
        0.003,
    )  # seven: coprime to the reads per sample

    def clock(self) -> float:
        self.reads += 1
        jitter = self.cells < self.noisy
        self.now += self.STEPS[self.reads % len(self.STEPS)] if jitter else 0.0005
        return self.now

    def tick(self) -> float:
        self.cells += 1
        return 0.0


def _boot_noisy(tmp: Path, get_kernel: Any, noisy: int, **overrides: Any) -> tuple[Any, list]:
    sleeps: list[float] = []
    jitter = Noisy(noisy)
    kwargs: dict[str, Any] = {
        "hero_kwargs": {"repeats": 5, "loadavg": jitter.tick, "quota": 4, "clock": jitter.clock},
        "hero_retry_s": 0.0,
        "sleep": sleeps.append,
    }
    kwargs.update(overrides)
    return _boot(tmp, get_kernel, **kwargs), sleeps


def test_noisy_hero_is_remeasured_with_backoff_inside_boot(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    booted, sleeps = _boot_noisy(tmp_path, fake_get_kernel, noisy=2)
    try:
        hero = booted.hero
        assert hero is not None and hero.cell.measured, "the third attempt was quiet"
        assert booted.hero_tracker.attempts == 3 and booted.hero_tracker.latest is hero
        assert sleeps == list(boot_sequence.HERO_BACKOFF_S[:2]), "backoff between attempts"
        detail = booted.registry.snapshot()["stages"][2]["detail"]
        assert "per kernel call" in detail and detail.endswith("attempt 3")
        assert booted.health()["hero"]["status"] == "measured"
        assert booted.health()["hero"]["attempts"] == 3
        assert booted.status_tile()["measured_utc"] == hero.ts_utc
    finally:
        booted.stop()
        booted.lane.shutdown(wait=False)


def test_hero_still_noisy_after_boot_keeps_no_number_and_a_null_measured_stamp(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    booted, sleeps = _boot_noisy(tmp_path, fake_get_kernel, noisy=99, hero_attempts=3)
    try:
        assert booted.ready, "a noisy hero is the rulebook's answer, not a boot failure"
        hero = booted.hero
        assert hero is not None and hero.cell.status == "noisy" and hero.kernel_ms is None
        assert booted.hero_tracker.attempts == 3 and booted.hero_tracker.pending
        assert sleeps == list(boot_sequence.HERO_BACKOFF_S[:2])
        detail = booted.registry.snapshot()["stages"][2]["detail"]
        assert detail.startswith("noisy — not recorded") and "attempt 3" in detail
        assert "again" not in detail, "hero_retry_s=0 starts no background thread"
        summary = booted.health()["hero"]
        assert summary["status"] == "noisy" and summary["measured"] is False
        assert summary["pending"] is True and summary["retry_s"] is None
        assert booted.status_tile()["measured_utc"] is None, "a noisy stamp is not a measurement"
        assert booted.facts["hero"]["status"] == "noisy"
    finally:
        booted.stop()
        booted.lane.shutdown(wait=False)


def test_hero_keeps_remeasuring_in_the_background_until_it_records(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    import time

    booted, _ = _boot_noisy(tmp_path, fake_get_kernel, noisy=3, hero_attempts=2, hero_retry_s=0.02)
    try:
        tracker = booted.hero_tracker
        detail = booted.registry.snapshot()["stages"][2]["detail"]
        assert "measured again every 0.02 s" in detail
        assert booted.health()["hero"]["retry_s"] == 0.02
        deadline = time.monotonic() + 5.0
        while tracker.measured is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert tracker.measured is not None, "the fourth attempt measured"
        assert booted.hero is tracker.measured and booted.status_tile()["measured_utc"]
        assert booted.health()["hero"]["status"] == "measured"
        tracker.stop(wait=True)
        assert not tracker.running and booted.health()["hero"]["retry_s"] is None
    finally:
        booted.stop()
        booted.lane.shutdown(wait=False)


def test_facts_are_computed_from_the_loaded_contracts_and_written(state: Any) -> None:
    facts = state.facts
    described = hubkernel.describe(state.kernels["stats"])
    assert facts["function_count"] == described["function_count"] > 100
    assert facts["functions_loaded"] == facts["function_count"]
    assert facts["module_count"] == len(described["modules"])
    assert facts["families_loaded"] == ["stats"]
    assert facts["families_failed"] == {"text": "cache_missing"}
    assert facts["families_published"] == 19 and facts["trust_repos"] == 20
    assert facts["variants"] == [VARIANT]
    assert facts["kernels"]["stats"]["capped_v1_sha"] == STATS_SHA
    assert facts["kernels"]["stats"]["warmup_ms"] > 0
    assert facts["hero"]["qualname"] == "ab_testing.z_test_proportions"
    assert facts["rulebook"] == bench.RULEBOOK_VERSION and facts["umbrella_loaded"] is False
    assert "mcp_tools" in facts and "versions" in facts and "generated_utc" in facts
    written = json.loads(Path(facts["facts_path"]).read_text(encoding="utf-8"))
    assert written["function_count"] == facts["function_count"]
    assert written["families_loaded"] == ["stats"]
    detail = state.registry.snapshot()["stages"][3]["detail"]
    assert detail == f"{facts['function_count']:,} functions in 1 family"


def test_health_facts_carry_the_live_hero_and_the_last_live_mcp_read(
    state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 11: `/health facts.hero` froze at the facts stage while `hero` and the boot card's
    row moved on, and `facts.mcp_tools` was null while the pages printed the hosted API's live
    count. `/health` serves the facts with both read now; the file keeps boot's own record."""
    from tabs import try_tab

    health = state.health()
    assert health["facts"]["hero"] == health["hero"], "the same record, never two"
    assert health["facts"]["hero"]["status"] == "measured"
    written = json.loads(Path(state.facts["facts_path"]).read_text(encoding="utf-8"))
    assert written["hero"]["qualname"] == health["hero"]["qualname"]
    assert "attempts" in written["hero"], "the file keeps the hero as the facts stage saw it"
    # no registry installed here and no live read yet: the boot record's null stands
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [])
    monkeypatch.setitem(state.facts, "mcp_tools", None)
    facts = state.health()["facts"]
    assert facts["mcp_tools"] is None and "mcp_tools_source" not in facts
    assert try_tab.last_live_mcp_read() is None
    # after the Try tile read the hosted endpoint: the count, its source and its stamp
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [140, "2026-09-24 08:28 UTC"])
    assert try_tab.last_live_mcp_read() == (140, "2026-09-24 08:28 UTC")
    facts = state.health()["facts"]
    assert facts["mcp_tools"] == 140 and facts["mcp_tools_source"] == boot_sequence.MCP_TOOLS_LIVE
    assert facts["mcp_tools_read_utc"] == "2026-09-24 08:28 UTC"
    assert state.facts["mcp_tools"] is None, "the boot record itself is not rewritten"
    # an installed registry's count is the boot record's and stays
    monkeypatch.setitem(state.facts, "mcp_tools", 137)
    facts = state.health()["facts"]
    assert facts["mcp_tools"] == 137 and "mcp_tools_source" not in facts
    assert state.live_facts(None) == {**state.facts, "hero": None}
    assert boot_sequence.BootState.live_facts(type("S", (), {"facts": {}})(), None) == {}


def test_health_and_status_tile_shapes(state: Any) -> None:
    health = state.health()
    assert health["ready"] is True and health["status"] == "ready"
    assert len(health["stages"]) == 6 and health["elapsed_s"] >= 0
    assert health["families"] == {"loaded": ["stats"], "failed": {"text": "cache_missing"}}
    assert health["hero"]["status"] == "measured" and health["hero"]["result"] == Z_EXPECTED
    # rulebook v0.4: the snapshot carries k beside n, so the boot row's `n = 21 × k calls` can
    # be checked against /health by the verifier (`boot_row_live`)
    assert health["hero"]["n"] == state.hero.cell.n and health["hero"]["k"] == state.hero.cell.k
    assert isinstance(health["hero"]["k"], int) and health["hero"]["k"] >= 1
    assert health["killswitch"]["flags"] == {"kernels": True, "provider": False, "races": True}
    assert health["killswitch"]["missed"] == 0 and health["killswitch"]["running"] is True
    assert health["lane"]["name"] == "native" and health["lane"]["max_depth"] == 8
    assert health["hosted"]["state"] == "not_configured"
    assert health["webhook"]["path"].startswith("/hook")
    assert state.hook.nonce not in json.dumps(health), "the snapshot never carries the nonce"
    assert health["host"] == {"ok": True, "reason": "test host at the floor"}
    json.dumps(health)  # every value is plain data

    tile = state.status_tile()
    assert tile["ready"] is True and tile["families_loaded"] == 1
    assert tile["function_count"] == state.facts["function_count"]
    assert tile["hero"]["kernel_ms"] == state.hero.kernel_ms
    assert tile["hero"]["status"] == "measured" and tile["measured_utc"] == state.hero.ts_utc
    json.dumps(tile)


def test_deps_carry_kernels_limits_and_the_kill_switch(state: Any) -> None:
    deps = state.deps()
    assert deps.kernel("stats") is state.kernels["stats"]
    assert (
        deps.kernel("thyn-ai/algenta-stats") is deps.kernel("algenta-stats") is deps.kernel("stats")
    )
    assert deps.kernel("text") is None and deps.kernel_errors["text"].code == "cache_missing"
    assert deps.feature_on("kernels") is True
    assert deps.feature_on("provider") is False, "the flag file says so"
    assert deps.feature_on("gpu") is True, "read once, on unless the file says otherwise"
    assert deps.lane is state.lane and deps.hero is state.hero
    assert deps.limits is not None
    assert deps.limits.caps(tabs_pkg.NATIVE_LIMIT_KIND).burst == 30
    assert deps.limits.caps("governed").daily_cap == 2_000, "the plan's launch values stay"
    assert deps.hardware == state.hardware


def test_spend_features_stay_off_while_the_flag_file_is_missing(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    booted = _boot(tmp_path, fake_get_kernel, fetch=dead_fetch, killswitch_url="https://x/f.json")
    try:
        assert booted.ready, booted.summary()
        assert booted.killswitch.url == "https://x/f.json"
        assert booted.deps().feature_on("provider") is False
        assert booted.deps().feature_on("kernels") is True
        stage = booted.registry.snapshot()["stages"][4]
        assert stage["state"] == "done" and "spend features off" in stage["detail"]
    finally:
        booted.killswitch.stop()
        booted.lane.shutdown(wait=False)


def test_killswitch_url_comes_from_the_environment_or_the_default(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    booted = _boot(
        tmp_path,
        fake_get_kernel,
        env=_env(tmp_path, KILLSWITCH_URL="https://example.org/flags.json"),
        fetch=dead_fetch,
    )
    try:
        assert booted.killswitch.url == "https://example.org/flags.json"
    finally:
        booted.killswitch.stop()
        booted.lane.shutdown(wait=False)
    assert boot_sequence.DEFAULT_KILLSWITCH_URL.startswith(
        "https://huggingface.co/datasets/thyn-ai/algenta-arena-results/"
    )


def test_below_the_host_floor_holds_every_family_with_the_reason(
    tmp_path: Path, fake_get_kernel: Any
) -> None:
    booted = _boot(
        tmp_path, fake_get_kernel, floor=(False, "Linux x86_64: glibc 2.31 is below 2.35")
    )
    try:
        assert not booted.ready and booted.kernels == {}
        assert {e.code for e in booted.kernel_errors.values()} == {"platform_unsupported"}
        assert set(booted.kernel_errors) == {"stats", "text"}
        stages = {s["id"]: s for s in booted.registry.snapshot()["stages"]}
        assert stages["host"]["state"] == "error"
        assert stages["kernels"]["state"] == "error" and "glibc 2.31" in stages["kernels"]["detail"]
        assert (
            stages["hero"]["state"] == "error"
            and "platform_unsupported" in stages["hero"]["detail"]
        )
        assert stages["facts"]["state"] == "done"
        health = booted.health()
        assert health["status"] == "error" and health["facts"]["function_count"] == 0
        assert booted.deps().kernel("stats") is None
    finally:
        booted.killswitch.stop()
        booted.lane.shutdown(wait=False)


def test_a_stage_that_raises_is_reported_not_raised(tmp_path: Path, fake_get_kernel: Any) -> None:
    def broken_get_kernel(repo_id: str, **kwargs: Any) -> Any:
        raise RuntimeError("loader exploded")

    booted = _boot(tmp_path, broken_get_kernel)
    try:
        stages = {s["id"]: s for s in booted.registry.snapshot()["stages"]}
        assert stages["kernels"]["state"] == "error"
        assert "load_failed" in stages["kernels"]["detail"]
        assert stages["hero"]["state"] == "error"
        assert booted.health()["status"] == "error"
    finally:
        booted.killswitch.stop()
        booted.lane.shutdown(wait=False)


def test_families_cover_the_published_catalogue_in_tab_order() -> None:
    assert boot_sequence.TAB_FAMILIES[0] == "stats", "the hero family loads first"
    published = {hubkernel.short_family(r) for r in hubkernel.TRUST} - {"algenta"}
    assert {hubkernel.short_family(f) for f in boot_sequence.FAMILIES} == published
    assert boot_sequence.PRELOAD[-1] == "algenta", "the umbrella last, after its members"
    assert len(boot_sequence.PRELOAD) == 20
    for _, label in boot_sequence.STAGES:
        shell.check_copy(label, max_words=shell.SUBLINE_WORDS)


def test_prune_tree_listings_removes_only_our_repositories(tmp_path: Path) -> None:
    ours = tmp_path / boot_sequence.repo_folder(STATS_REPO) / "trees"
    ours.mkdir(parents=True)
    (ours / f"{STATS_SHA}.json").write_text("{}")
    other = tmp_path / "kernels--someone--else" / "trees"
    other.mkdir(parents=True)
    (other / "abc.json").write_text("{}")
    removed = boot_sequence.prune_tree_listings(root=tmp_path)
    assert removed == [ours / f"{STATS_SHA}.json"]
    assert not (ours / f"{STATS_SHA}.json").exists() and (other / "abc.json").exists()
    assert boot_sequence.prune_tree_listings(root=tmp_path) == []


def test_bake_installs_every_trusted_repository_then_prunes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # KERNELS_CACHE is read before huggingface_hub's default, so the prune works on this tmp dir
    # (and the test needs no huggingface_hub, as under the bare 3.14 run).
    monkeypatch.setenv("KERNELS_CACHE", str(tmp_path))
    installed: list[tuple[str, dict]] = []

    def install(repo_id: str, **kwargs: Any) -> Path:
        installed.append((repo_id, kwargs))
        sha = hubkernel.FROZEN_CAPPED_V1_SHAS[repo_id]
        folder = tmp_path / boot_sequence.repo_folder(repo_id)
        (folder / "trees").mkdir(parents=True, exist_ok=True)
        (folder / "trees" / f"{sha}.json").write_text("{}")
        variant = folder / "snapshots" / sha / "build" / VARIANT
        variant.mkdir(parents=True, exist_ok=True)
        return variant

    lines: list[str] = []
    paths = boot_sequence.bake_cache(install=install, progress=lines.append)
    assert [r for r, _ in installed] == list(hubkernel.TRUST)
    assert all(k["version"] == 1 and k["backend"] == "cpu" for _, k in installed)
    assert all(list(k["trust_remote_code"]) == list(hubkernel.TRUST) for _, k in installed)
    assert len(paths) == 20 and lines[-1].startswith("20 repositories baked")
    stats_folder = tmp_path / boot_sequence.repo_folder(STATS_REPO)
    assert (stats_folder / "refs" / "v1").read_text() == STATS_SHA, "the offline resolver's tag"
    umbrella_sha = hubkernel.FROZEN_CAPPED_V1_SHAS["thyn-ai/algenta"][:7]
    assert lines[0].startswith(f"thyn-ai/algenta: torch25-cpu-aarch64-darwin @ {umbrella_sha}")
    assert lines[-1].endswith("20 tree listings pruned")
    assert all(
        not list((tmp_path / boot_sequence.repo_folder(r) / "trees").glob("*.json"))
        for r in hubkernel.TRUST
    ), "every cached tree listing is removed so the offline resolver accepts the variant-only cache"
    assert all(
        (tmp_path / boot_sequence.repo_folder(r) / "refs" / "v1").is_file() for r in hubkernel.TRUST
    )


def test_record_version_ref_reads_the_commit_from_the_snapshot_path(tmp_path: Path) -> None:
    variant = (
        tmp_path / "kernels--thyn-ai--algenta-stats" / "snapshots" / STATS_SHA / "build" / VARIANT
    )
    variant.mkdir(parents=True)
    ref = boot_sequence.record_version_ref(variant, 1)
    assert ref == tmp_path / "kernels--thyn-ai--algenta-stats" / "refs" / "v1"
    assert ref.read_text() == STATS_SHA
    assert boot_sequence.record_version_ref(variant, 1) == ref, "idempotent"
    with pytest.raises(ValueError, match="not a cache snapshot path"):
        boot_sequence.record_version_ref(tmp_path / "elsewhere" / "build" / VARIANT, 1)
    with pytest.raises(ValueError, match="no commit hash"):
        boot_sequence.record_version_ref(
            tmp_path / "r" / "snapshots" / "not-a-sha" / "build" / VARIANT, 1
        )


def test_verify_cache_reports_the_catalogue_and_refuses_a_missing_family(
    fake_get_kernel: Any,
) -> None:
    lines: list[str] = []
    summary = boot_sequence.verify_cache(
        ("stats",), get_kernel=fake_get_kernel, progress=lines.append
    )
    assert summary["families"] == ["algenta-stats"] and summary["variants"] == [VARIANT]
    assert summary["unpinned"] == [] and summary["function_count"] is None
    with pytest.raises(RuntimeError, match="algenta-text: cache_missing"):
        boot_sequence.verify_cache(("stats", "text"), get_kernel=fake_get_kernel)


def test_hub_offline_reads_the_variable() -> None:
    assert boot_sequence.hub_offline({"HF_HUB_OFFLINE": "1"}) is True
    assert boot_sequence.hub_offline({"HF_HUB_OFFLINE": "0"}) is False
    assert boot_sequence.hub_offline({}) is False


# ---------------------------------------------------------------------------
# Permalink
# ---------------------------------------------------------------------------


def test_permalink_round_trip() -> None:
    args = {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000}
    url = permalink.build(
        "try",
        fn="ab_testing.z_test_proportions",
        args=args,
        base="https://thyn-ai-algenta.hf.space",
        tabs=TABS,
    )
    assert url.startswith(
        "https://thyn-ai-algenta.hf.space/?tab=try&fn=ab_testing.z_test_proportions&args="
    )
    from urllib.parse import parse_qs, urlsplit

    query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    link = permalink.parse(query, tabs=TABS)
    assert link == permalink.Permalink("try", "ab_testing.z_test_proportions", args)
    assert link.url("https://thyn-ai-algenta.hf.space/") == url
    assert permalink.build("play") == "?tab=play"
    assert permalink.Permalink().query() == "" and permalink.Permalink().empty


def test_permalink_drops_what_it_cannot_restore_field_by_field() -> None:
    link = permalink.parse({"tab": "nope", "fn": "text.fuzzy.levenshtein_distance"}, tabs=TABS)
    assert link.tab is None and link.fn == "text.fuzzy.levenshtein_distance"
    assert permalink.parse({"tab": "play", "fn": "no-dots"}, tabs=TABS).fn is None
    assert permalink.parse({"tab": "play", "fn": "a.b; import os"}, tabs=TABS).fn is None
    assert permalink.parse({"tab": "play", "args": "{not json"}, tabs=TABS) == permalink.Permalink(
        "play"
    )
    assert permalink.parse({"tab": "play", "args": "[1, 2]"}, tabs=TABS).args is None
    assert permalink.parse({"tab": "play", "args": "{}"}, tabs=TABS).args is None
    huge = json.dumps({"x": "y" * permalink.MAX_ARGS_CHARS})
    assert permalink.parse({"tab": "play", "args": huge}, tabs=TABS).args is None
    assert permalink.parse({"tab": ["race", "play"]}, tabs=TABS).tab == "race"
    assert permalink.parse(None, tabs=TABS).empty
    with pytest.raises(ValueError, match="unknown tab"):
        permalink.build("nope", tabs=TABS)


def test_permalink_reads_a_request_and_the_public_base() -> None:
    class Request:
        query_params = {
            "tab": "llm",
            "fn": "normk.rmsnorm.rmsnorm_fwd_flat",
            "args": '{"n_rows": 2}',
        }
        headers = {"X-Forwarded-Host": "thyn-ai-algenta.hf.space", "X-Forwarded-Proto": "https"}
        url = "http://10.0.0.5:7860/?tab=llm"

    link = permalink.from_request(Request(), tabs=TABS)
    assert link == permalink.Permalink("llm", "normk.rmsnorm.rmsnorm_fwd_flat", {"n_rows": 2})
    assert permalink.from_request(None, tabs=TABS).empty
    assert permalink.public_base({"ALGENTA_PUBLIC_BASE_URL": "https://demo.algenta.ai/"}) == (
        "https://demo.algenta.ai"
    )
    assert permalink.public_base({"SPACE_HOST": "thyn-ai-algenta.hf.space"}) == (
        "https://thyn-ai-algenta.hf.space"
    )
    assert permalink.public_base({}, Request()) == "https://thyn-ai-algenta.hf.space"

    class Bare:
        headers: dict[str, str] = {}
        url = "http://127.0.0.1:7860/"

    assert permalink.public_base({}, Bare()) == "http://127.0.0.1:7860"
    assert permalink.public_base({}, None) == ""
    assert permalink.public_base({"SPACE_HOST": "bad host!"}, None) == ""


def test_permalink_restorable_never_promises_a_call_the_page_did_not_restore() -> None:
    """The shell's rule for a tab without `permalink_applied`: the function only when a loaded
    family serves it, the arguments only beside such a function or without any function."""
    known = {"text.fuzzy.levenshtein_distance", "ab_testing.z_test_proportions"}
    full = permalink.Permalink("play", "text.fuzzy.levenshtein_distance", {"a": "kitten"})
    assert permalink.restorable(full, known_functions=known) == full
    bogus = permalink.Permalink("play", "bogus.fn", {"x": 1})
    assert permalink.restorable(bogus, known_functions=known) == permalink.Permalink("play")
    numbers = permalink.Permalink("try", None, {"successes_a": 50})
    assert permalink.restorable(numbers, known_functions=known) == numbers
    assert permalink.restorable(bogus, known_functions=None) == bogus, "no contracts, no rule"
    assert permalink.Permalink("play").empty_call and not full.empty_call
    # the link the page last showed, absolute or relative, parsed back for the tab strip
    assert permalink.parse_query("https://x.hf.space/?tab=race&fn=a.b&args=%7B%22s%22%3A1%7D") == (
        permalink.Permalink("race", "a.b", {"s": 1})
    )
    assert permalink.parse_query("?tab=play").tab == "play"
    assert permalink.parse_query("").empty and permalink.parse_query("?tab=nope", tabs=TABS).empty


# ---------------------------------------------------------------------------
# User-agent shim
# ---------------------------------------------------------------------------


def test_shim_strips_the_trailing_separator_and_is_idempotent() -> None:
    assert hf_ua_shim.clean_user_agent("kernels/0.17.1; hf_hub/1.26.1; ") == (
        "kernels/0.17.1; hf_hub/1.26.1"
    )
    assert (
        hf_ua_shim.clean_user_agent("unknown/None; hf_hub/1.26.1") == "unknown/None; hf_hub/1.26.1"
    )

    def original(*, library_name=None, library_version=None, user_agent=None) -> str:
        tail = f"; {user_agent}" if isinstance(user_agent, str) else ""
        return f"{library_name}/{library_version}{tail}"

    patched = hf_ua_shim.wrap(original)
    assert (
        patched(library_name="kernels", library_version="0.17.1", user_agent="") == "kernels/0.17.1"
    )
    assert patched(library_name="k", library_version="1", user_agent="x/1") == "k/1; x/1"
    assert hf_ua_shim.wrap(patched) is patched, "wrapping twice keeps one wrapper"


def test_shim_is_applied_to_huggingface_hub_when_installed() -> None:
    headers = pytest.importorskip("huggingface_hub.utils._headers")
    assert hf_ua_shim.apply() is True and hf_ua_shim.applied()
    composed = headers._http_user_agent(
        library_name="kernels", library_version="0.17.1", user_agent=""
    )
    assert not composed.endswith(("; ", ";", " ")), composed
    assert hf_ua_shim.apply() is True, "a second apply is a no-op"


# ---------------------------------------------------------------------------
# The page (needs gradio)
# ---------------------------------------------------------------------------


def _fake_spec(tab_id: str, label: str, api_name: str | None = None) -> Any:
    def render(gr: Any) -> dict[str, Any]:
        box = gr.Textbox(value="", label=label)
        run = gr.Button("Run")
        if api_name:
            run.click(lambda text: text.upper(), box, box, api_name=api_name)
        return {"box": box, "run": run}

    return tabs_pkg.TabSpec(tab_id, label, render, (api_name,) if api_name else ())


SEEN_SHELL_HANDLES: list[dict[str, Any]] = []


def _switching_spec(tab_id: str, label: str, target: str) -> Any:
    """A tab whose chip selects another tab and rewrites the shell's permalink box in the same
    event — what the Try tab's "Race it against Python" chip does with the shell handle."""

    def render(gr: Any) -> dict[str, Any]:
        return {"chip": gr.Button("Race it")}

    def connect(gr: Any, tabs: Any, handles: Any) -> None:
        shell_handles = handles[app_mod.SHELL_HANDLE]
        SEEN_SHELL_HANDLES.append(dict(shell_handles))
        handles[tab_id]["chip"].click(
            lambda: (gr.Tabs(selected=target), permalink.build(target, base=shell_handles["base"])),
            None,
            [tabs, shell_handles["permalink"]],
            api_name=False,
        )

    return tabs_pkg.TabSpec(tab_id, label, render, (), connect)


class FakePlayModule(ModuleType):
    """A tab module on the older restore shape — a bare list of values, no report of what it
    applied: the shell hands it the link and promises the tab alone."""

    def __init__(self) -> None:
        super().__init__("tabs.fake_play")
        self.FAKE_CSS = ".alg-fake.alg-fake.alg-fake.alg-fake { margin: 8px 0 0; }"

    @staticmethod
    def permalink_outputs(handles: dict[str, Any]) -> list[Any]:
        return [handles["box"]]

    @staticmethod
    def permalink_restore(fn: str | None, args: dict | None) -> list[Any]:
        return [f"{fn}:{json.dumps(args, sort_keys=True)}"]


class FakeReportingModule(FakePlayModule):
    """A tab module on the reporting shape: `permalink_restore` answers with the values and
    the report of what it applied — a function it knows with the arguments it could keep (the
    Playground keeps a number for a number box, drops a word), nothing for an unknown one."""

    KNOWN = {
        "geodesy.haversine_distance": ("lat1", "lon1", "lat2", "lon2"),
        "text.fuzzy.levenshtein_distance": ("a", "b"),
    }

    def __init__(self) -> None:
        super().__init__()
        self.__name__ = "tabs.fake_reporting"

    @classmethod
    def permalink_restore(cls, fn: str | None, args: dict | None) -> dict[str, Any]:
        payload = [f"{fn}:{json.dumps(args, sort_keys=True)}"]
        names = cls.KNOWN.get(fn or "")
        if names is None:
            return {"values": payload, "applied": None}
        numeric = fn == "geodesy.haversine_distance"
        kept = {
            k: v
            for k, v in (args or {}).items()
            if k in names and (isinstance(v, int | float) if numeric else isinstance(v, str))
        }
        return {"values": payload, "applied": {"fn": fn, "args": kept or None}}


class FakeTryModule(FakePlayModule):
    """A tab module that reports through the hook: the hero function with whole-number
    arguments, nothing for a foreign function."""

    HERO = "ab_testing.z_test_proportions"

    def __init__(self) -> None:
        super().__init__()
        self.__name__ = "tabs.fake_try"

    @classmethod
    def permalink_applied(cls, fn: str | None, args: dict | None) -> tuple | None:
        if fn not in (None, cls.HERO):
            return None
        kept = {
            k: v
            for k, v in (args or {}).items()
            if isinstance(v, int) or (isinstance(v, float) and v.is_integer())
        }
        kept = {k: int(v) for k, v in kept.items()}
        return (cls.HERO if (fn or kept) else None, kept or None)


class Request:
    """A `gr.Request` as `on_load` reads it: the page's query string and no forwarding."""

    headers: dict[str, str] = {}

    def __init__(self, **params: str) -> None:
        self.query_params = params


@pytest.fixture(scope="module")
def page(state: Any) -> Any:
    pytest.importorskip("gradio")
    specs = [_fake_spec("try", "Try it", "try_run"), _fake_spec("play", "Playground")] + [
        app_mod.unavailable_spec(tab, "not in this test build") for tab in TABS[2:]
    ]
    modules = {"play": FakePlayModule()}
    app = app_mod.create_app(
        state, space_id="thyn-ai/algenta", stamp=STAMP, specs=specs, modules=modules
    )
    return app


@pytest.fixture(scope="module")
def client(page: Any) -> Any:
    from starlette.testclient import TestClient

    with TestClient(page) as client:
        yield client


def test_health_route_returns_the_boot_snapshot(client: Any, state: Any) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True and body["status"] == "ready"
    assert [s["id"] for s in body["stages"]] == [sid for sid, _ in boot_sequence.STAGES]
    assert body["hero"]["result"] == Z_EXPECTED and body["facts"]["families_loaded"] == ["stats"]
    assert body["killswitch"]["flags"]["provider"] is False


def test_health_route_never_publishes_the_webhook_nonce(client: Any, state: Any) -> None:
    """The nonce is the one thing that gates the engine's POST without a signing secret; the
    route names the webhook's prefix and whether it is public, never the path — a snapshot
    that carries the path (an older `boot_sequence`) is redacted at the route."""
    body = client.get("/health").json()
    assert body["webhook"] == {"prefix": "/hook", "public": False}
    assert "path" not in body["webhook"]
    assert not re.search(r"/hook/[A-Za-z0-9_-]{16,}", json.dumps(body))
    assert state.hook.nonce not in json.dumps(body)
    with_path = {
        "status": "ready",
        "webhook": {"path": "/hook/CTd0spedChhS89CmhN6tCgDyosxUDUX1", "public": True},
    }
    assert app_mod.public_health(with_path) == {
        "status": "ready",
        "webhook": {"prefix": "/hook", "public": True},
    }
    assert app_mod.public_health({"webhook": {"path": "/hook", "public": False}})["webhook"] == {
        "prefix": "/hook",
        "public": False,
    }
    assert app_mod.public_health({"webhook": {"prefix": "/engine-hook", "public": True}})[
        "webhook"
    ] == {"prefix": "/engine-hook", "public": True}
    assert app_mod.public_health({"webhook": {}})["webhook"] == {"prefix": "/hook", "public": False}
    assert app_mod.public_health({"status": "ready"}) == {"status": "ready"}
    original = {"webhook": {"path": "/hook/abc"}}
    app_mod.public_health(original)
    assert original == {"webhook": {"path": "/hook/abc"}}, "the snapshot itself is untouched"


def test_status_route_is_the_cross_space_tile(client: Any, state: Any) -> None:
    body = client.get("/api/status").json()
    assert body["ready"] is True and body["function_count"] == state.facts["function_count"]
    assert body["hero"]["qualname"] == "ab_testing.z_test_proportions"
    assert body["hero"]["status"] == "measured"
    assert body["measured_utc"] == state.hero.ts_utc and body["build"] == state.facts["shared_sha"]


def test_status_tile_carries_no_stamp_for_an_unmeasured_hero(
    client: Any, state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `noisy — not recorded` opening card is attempted at a time, not measured at one: the
    cross-Space tile says `measured_utc: null` until the rulebook has recorded a cell."""
    from algenta_spaces import bench

    measured = state.hero_summary()
    assert measured["status"] == bench.STATUS_MEASURED
    noisy = {
        **measured,
        "status": bench.STATUS_NOISY,
        "kernel_ms": None,
        "reason": "noisy — not recorded — spread above 15 percent on algenta-stats",
    }
    monkeypatch.setattr(type(state), "hero_summary", lambda self: dict(noisy))
    tile = app_mod.status_tile(state)
    assert tile["hero"]["status"] == "noisy" and tile["hero"]["kernel_ms"] is None
    assert tile["measured_utc"] is None
    assert tile["hero"]["ts_utc"] == measured["ts_utc"], "the attempt's stamp stays on the hero"
    body = client.get("/api/status").json()
    assert body["measured_utc"] is None and body["ready"] is True
    monkeypatch.setattr(type(state), "hero_summary", lambda self: None)
    assert app_mod.status_tile(state)["measured_utc"] is None
    assert app_mod.status_tile(state)["hero"] is None
    monkeypatch.undo()
    assert client.get("/api/status").json()["measured_utc"] == measured["ts_utc"]


def test_page_holds_first_paint_until_the_requested_tab_is_selected(client: Any) -> None:
    """The head fragment adds `alg-booting` before any component mounts and a client-side step
    chained after `on_load` removes it once the strip shows the requested tab; both are bounded."""
    config = client.get("/config").json()
    head = config.get("head") or ""
    assert head == app_mod.BOOT_HEAD
    assert head.startswith("<style>") and "<script>" in head
    assert f"html.{app_mod.BOOTING_CLASS} body {{ visibility: hidden; }}" in head
    assert f"classList.add('{app_mod.BOOTING_CLASS}')" in head
    assert f"{app_mod.BOOT_HOLD_MAX_MS})" in head, "the head fragment lifts the hold on its own"
    assert head.endswith(shell.NAV_ROWS_HEAD), "the shell's row marker rides in the head"
    assert "!important" not in head and ".gradio-container" not in head
    reveal = [d for d in config["dependencies"] if app_mod.BOOTING_CLASS in (d.get("js") or "")]
    assert len(reveal) == 1, "one client-side reveal step"
    step = reveal[0]
    assert step["js"] == app_mod.REVEAL_JS
    assert step["api_visibility"] == "private", "never an endpoint"
    assert step["targets"] and all(trigger == "then" for _, trigger in step["targets"])
    load = [d for d in config["dependencies"] if any(t == "load" for _, t in d["targets"])]
    assert step["trigger_after"] in {d["id"] for d in load}, "chained after on_load"
    assert step["trigger_only_on_success"] is False, "a failed load still reveals the page"
    assert "aria-selected=true" in app_mod.REVEAL_JS and "data-tab-id" in app_mod.REVEAL_JS
    assert "document.fonts.status === 'loaded'" in app_mod.REVEAL_JS
    assert "requestAnimationFrame(() => requestAnimationFrame(reveal))" in app_mod.REVEAL_JS
    assert str(app_mod.REVEAL_TIMEOUT_MS) in app_mod.REVEAL_JS
    assert app_mod.REVEAL_TIMEOUT_MS < app_mod.BOOT_HOLD_MAX_MS
    assert FAKE_WORDS.search(app_mod.BOOT_HEAD + app_mod.REVEAL_JS) is None
    index = client.get("/").text
    assert app_mod.BOOTING_CLASS in index, "the fragment travels with the page config"


def test_mcp_schema_answers_and_the_gradio_footer_is_off(client: Any) -> None:
    """`mcp_server=True` is what the Hub's MCP badge and `algenta-mcp` clients read;
    `footer_links=[]` keeps Gradio's own footer (API · Built with Gradio · Settings) off the page,
    so the shared footer with the Duplicate link and the stamp is the only footer."""
    schema = client.get("/gradio_api/mcp/schema")
    assert schema.status_code == 200
    tools = schema.json()
    assert isinstance(tools, list) and len(tools) >= 1
    assert all("name" in tool for tool in tools)
    config = client.get("/config").json()
    assert config["footer_links"] == []
    text = config["components"]
    footers = [
        c
        for c in text
        if isinstance(c.get("props", {}).get("value"), str)
        and "alg-shell-footer" in c["props"]["value"]
    ]
    assert len(footers) == 1, "exactly one footer: the shared one"
    assert "Duplicate this Space" in footers[0]["props"]["value"] or any(
        "Duplicate this Space" in str(c.get("props", {}).get("value", "")) for c in text
    )
    assert "Built with Gradio" not in json.dumps(text)


def test_page_carries_the_shared_footer_stamp_and_only_the_tabs_endpoints(client: Any) -> None:
    import verify_remote as vr

    response = client.get("/")
    assert response.status_code == 200
    # the shared shell prints the first twelve characters of the sha (one line at 375 px) with
    # the full sha in the span's title; both tools read the stamp as a prefix of the staged sha
    short = shell.short_stamp(STAMP)
    assert len(short) == shell.SHORT_STAMP_CHARS and STAMP.startswith(short)
    assert f"build {short}" in response.text, "the footer stamp is embedded in the index page"
    assert f"build {STAMP}" in response.text, "the full sha rides in the span's title"
    assert vr.footer_stamp_of(response.text) == short, "read from the escaped index page too"
    config_json = client.get("/config").text
    assert vr.footer_stamp_of(config_json) == short and STAMP.startswith(short)
    assert "Duplicate this Space" in config_json and "https://algenta.ai/pricing" in config_json
    assert "https://discord.gg/w8NDsph9an" in config_json
    info = client.get("/gradio_api/info").json()
    assert set(info["named_endpoints"]) == {"/try_run"}, "select/load carry api_name=False"


def test_blocks_wire_the_permalink_protocol_and_the_tab_strip(state: Any) -> None:
    gr = pytest.importorskip("gradio")
    specs = [_fake_spec("try", "Try it"), _fake_spec("play", "Playground")] + [
        app_mod.unavailable_spec(tab, "not in this test build") for tab in TABS[2:]
    ]
    blocks, built, modules = app_mod.build_blocks(
        state, space_id=None, stamp=STAMP, specs=specs, modules={"play": FakePlayModule()}
    )
    assert [s.id for s in built] == list(TABS) and modules.keys() == {"play"}
    tab_ids = sorted(b.id for b in blocks.blocks.values() if isinstance(b, gr.Tab))
    assert len(tab_ids) == 6
    load_deps = [
        fn for fn in blocks.fns.values() if any(trigger == "load" for _, trigger in fn.targets)
    ]
    assert len(load_deps) == 2, "the shell's on_load plus the boot card's re-render"
    on_load = next(fn for fn in load_deps if len(fn.outputs) == 3)
    assert len(on_load.outputs) == 3, "tabs + permalink box + the play tab's one component"
    assert on_load.api_visibility == "private", "api_name=False hides it from /info"
    boot_refresh = next(fn for fn in load_deps if len(fn.outputs) == 1)
    assert boot_refresh.api_visibility == "private"
    assert boot_refresh.outputs[0].__class__ is gr.HTML
    assert boot_refresh.fn == state.registry.render_html, "the boot card re-renders the registry"
    assert boot_refresh.fn() == state.registry.render_html()
    boot_card = boot_refresh.outputs[0]
    assert boot_card.value == state.registry.render_html()
    node = boot_card.parent
    while node is not None and not isinstance(node, gr.Accordion):
        node = node.parent
    assert node is not None and "alg-boot-disclosure" in (node.elem_classes or [])
    from gradio import utils as gradio_utils

    hints = gradio_utils.get_type_hints(on_load.fn)
    assert hints.get("request") is gr.Request, "the page request is injected into on_load"
    select_deps = [
        fn for fn in blocks.fns.values() if any(trigger == "select" for _, trigger in fn.targets)
    ]
    assert select_deps and all(fn.api_visibility == "private" for fn in select_deps)
    shell_select = [fn for fn in select_deps if fn.fn is not None and fn.fn.__name__ == "on_select"]
    assert shell_select and gradio_utils.get_type_hints(shell_select[0].fn)["evt"] is gr.SelectData
    assert blocks._queue.max_size == 8 and blocks._queue.default_concurrency_limit == 1
    # the permalink box is built before the tabs (so a tab's own event can name it) and drawn
    # in the permalink row under the strip, after the tabs and their load hooks
    box = next(b for b in blocks.blocks.values() if "alg-permalink" in (b.elem_classes or []))
    ancestors = []
    node = box.parent
    while node is not None and len(ancestors) < 4:  # Gradio wraps a Textbox in its own Form
        ancestors.append(node)
        node = node.parent
    row = next((a for a in ancestors if "alg-permalink-row" in (a.elem_classes or [])), None)
    assert row is not None, "drawn in the permalink row"
    strip = next(b for b in blocks.blocks.values() if isinstance(b, gr.Tabs))
    assert row._id > strip._id, "the row is laid out below the strip"


def _on_load_of(state: Any, modules: dict[str, Any]) -> Any:
    specs = [_fake_spec("try", "Try it"), _fake_spec("play", "Playground")] + [
        app_mod.unavailable_spec(tab, "not in this test build") for tab in TABS[2:]
    ]
    blocks, _, _ = app_mod.build_blocks(
        state, space_id=None, stamp=STAMP, specs=specs, modules=modules
    )
    return next(
        fn.fn
        for fn in blocks.fns.values()
        if any(trigger == "load" for _, trigger in fn.targets)
        and fn.fn is not None
        and getattr(fn.fn, "__name__", "") == "on_load"
    )


def test_on_load_writes_only_what_the_tab_reports_applied(
    state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The permalink box is written from the tab's report alone: the reporting shape's
    `applied`, else the `permalink_applied` hook's answer, else the tab and nothing more — a
    tab on the older list shape gets its values but promises nothing it did not confirm."""
    gr = pytest.importorskip("gradio")
    known = app_mod.known_functions(state)
    assert "ab_testing.z_test_proportions" in known and len(known) > 100
    assert not any(name.endswith(".execute") or "." not in name for name in known)
    # the test state serves the stats family alone; the shapes name text and geometry
    # functions, so the ceiling is widened to what the real container serves
    served = known | {"geodesy.haversine_distance", "text.fuzzy.levenshtein_distance"}
    monkeypatch.setattr(app_mod, "known_functions", lambda s: served)
    on_load = _on_load_of(state, {"try": FakeTryModule(), "play": FakeReportingModule()})

    def load(**params: str) -> tuple:
        out = on_load(Request(**params))
        assert len(out) == 4, "tabs, link, try's box, play's box"
        return out

    lev = "text.fuzzy.levenshtein_distance"
    hav = "geodesy.haversine_distance"
    hero = "ab_testing.z_test_proportions"
    # the seven shapes of round 2, on the reporting Playground and the hook-reporting Try tab
    out = load(tab="play", args='{"x": 1}')  # 1 arguments without a function
    assert out[1] == "?tab=play", "the form kept its defaults, so the box names the tab alone"
    out = load(tab="play", fn=hav, args='{"lat1": "north"}')  # 2 a word for a number box
    assert permalink.parse_query(out[1]) == permalink.Permalink("play", hav)
    assert out[3] == f"{hav}:" + json.dumps({"lat1": "north"}), "the tab still saw the link"
    out = load(tab="try", args='{"successes_a": 12.5, "n_a": 345, "successes_b": 67, "n_b": 890}')
    assert permalink.parse_query(out[1]) == permalink.Permalink(  # 3 a decimal for a whole
        "try", hero, {"n_a": 345, "successes_b": 67, "n_b": 890}
    )
    out = load(tab="try", fn=lev, args='{"successes_a": 12, "n_a": 345}')  # 4 a foreign function
    assert out[1] == "?tab=try"
    out = load(tab="nope", fn=lev, args='{"a": "x"}')  # 5 an unknown tab: the default, nothing else
    assert out[1] == "?tab=try" and isinstance(out[0], gr.Tabs)
    assert not isinstance(out[2], str) and not isinstance(out[3], str), "no tab was handed the call"
    # 6 and 7 are the Races tab's (a size it does not offer, a non-candidate): the same hook
    # protocol as the Try tab — its declined answer is `?tab=race`, its kept answer the cell
    assert app_mod.report_of("race", None) == permalink.Permalink("race")
    assert app_mod.report_of("race", (lev, {"size": "M"})) == permalink.Permalink(
        "race", lev, {"size": "M"}
    )
    # the full shapes: what the tab reports is what the box promises
    out = load(tab="play", fn=lev, args='{"a": "kitten", "b": "sitting"}')
    assert permalink.parse_query(out[1]) == permalink.Permalink(
        "play", lev, {"a": "kitten", "b": "sitting"}
    )
    assert out[3] == f"{lev}:" + json.dumps({"a": "kitten", "b": "sitting"}, sort_keys=True)
    out = load(
        tab="try", fn=hero, args='{"successes_a": 12, "n_a": 345, "successes_b": 67, "n_b": 890}'
    )
    assert permalink.parse_query(out[1]) == permalink.Permalink(
        "try", hero, {"successes_a": 12, "n_a": 345, "successes_b": 67, "n_b": 890}
    )
    # a function no loaded family serves never reaches the tab: the ceiling, then the report
    out = load(tab="play", fn="bogus.fn", args='{"x": 1}')
    assert out[1] == "?tab=play" and not isinstance(out[3], str)
    # a tab without the protocol keeps its tab only, whatever the link names
    out = load(tab="llm", fn="normk.rmsnorm.rmsnorm_fwd_flat", args='{"n_rows": 2}')
    assert out[1] == "?tab=llm"
    # no query at all: the first tab, nothing restored
    out = load()
    assert out[1] == "?tab=try" and isinstance(out[0], gr.Tabs)


def test_on_load_promises_the_tab_alone_for_a_tab_that_reports_nothing(state: Any) -> None:
    """The older restore shape (a bare list of values) still restores — the tab gets the link
    the shell's ceiling allows — but the box cannot promise what nobody confirmed."""
    pytest.importorskip("gradio")
    on_load = _on_load_of(state, {"play": FakePlayModule()})
    fn = "ab_testing.z_test_proportions"
    args = json.dumps({"successes_a": 50, "n_a": 1000})
    out = on_load(Request(tab="play", fn=fn, args=args))
    assert len(out) == 3, "tabs, link, play's box"
    assert out[1] == "?tab=play", "a tab that reports nothing gets the tab alone"
    assert out[2] == f"{fn}:{json.dumps(json.loads(args), sort_keys=True)}", "yet restores"
    out = on_load(Request(tab="play", fn="text.fuzzy.levenshtein_distance", args='{"a": "k"}'))
    assert out[1] == "?tab=play" and not isinstance(out[2], str), "the ceiling: not served here"


def test_permalink_report_shapes() -> None:
    """`report_of` and `restore_answer`: every accepted shape, every refused one."""
    known = frozenset({"a.b"})
    link = permalink.Permalink("play", "bogus.fn", {"x": 1})
    assert app_mod.applied_link(link, None, known) == permalink.Permalink("play")
    assert app_mod.applied_link(link, lambda fn, args: ("a.b", {"k": 1}), known) == (
        permalink.Permalink("play", "a.b", {"k": 1})
    )
    with pytest.raises(ValueError, match="permalink_applied must return"):
        app_mod.applied_link(link, lambda fn, args: 42, known, module="tabs.x")
    # reports: None, a mapping, a pair, an object; a bad function or empty arguments dropped
    assert app_mod.report_of("play", None) == permalink.Permalink("play")
    assert app_mod.report_of("play", {"fn": "a.b", "args": {"k": 1}}) == (
        permalink.Permalink("play", "a.b", {"k": 1})
    )
    assert app_mod.report_of("play", ("a.b", None)) == permalink.Permalink("play", "a.b")
    assert app_mod.report_of("play", permalink.Permalink("x", "a.b", {"k": 1})) == (
        permalink.Permalink("play", "a.b", {"k": 1})
    )
    assert app_mod.report_of("play", {"fn": "no-dots", "args": {}}) == permalink.Permalink("play")
    assert app_mod.report_of("play", {"fn": 7, "args": [1, 2]}) == permalink.Permalink("play")
    with pytest.raises(ValueError, match="a permalink report is"):
        app_mod.report_of("play", 42)
    # answers: the list shape reports nothing; the mapping shape carries the report
    values, report = app_mod.restore_answer("play", ["v"], 1)
    assert values == ["v"] and report is app_mod.NOT_REPORTED
    values, report = app_mod.restore_answer(
        "play", {"values": ["v"], "applied": {"fn": "a.b", "args": None}}, 1
    )
    assert values == ["v"] and report == permalink.Permalink("play", "a.b")
    values, report = app_mod.restore_answer("play", {"outputs": ("v", "w")}, 2)
    assert values == ["v", "w"] and report is app_mod.NOT_REPORTED
    values, report = app_mod.restore_answer("play", {"values": ["v"], "applied": None}, 1)
    assert report == permalink.Permalink("play")
    with pytest.raises(ValueError, match="without values or outputs"):
        app_mod.restore_answer("play", {"applied": None}, 1, module="tabs.x")
    with pytest.raises(ValueError, match="returned 2 values for 1 components"):
        app_mod.restore_answer("play", ["v", "w"], 1, module="tabs.x")
    with pytest.raises(ValueError, match="one value per component"):
        app_mod.restore_answer("play", "v", 1, module="tabs.x")


def _load_hook_spec(tab_id: str, label: str) -> Any:
    """A tab that refreshes one panel on page load through the LOAD_HOOKS handle."""

    def render(gr: Any) -> dict[str, Any]:
        panel = gr.HTML("<p>boot</p>")
        return {"panel": panel, tabs_pkg.LOAD_HOOKS: [(lambda: "<p>loaded</p>", panel)]}

    return tabs_pkg.TabSpec(tab_id, label, render, ())


def test_shell_handle_lets_a_tab_rewrite_the_permalink_on_a_programmatic_switch(state: Any) -> None:
    """`tabs.change` does not fire for `gr.Tabs(selected=…)` from a handler (measured live), so
    the shell offers its permalink box to every tab's `connect` under `SHELL_HANDLE`; a tab that
    switches the strip names the box as an output and the link follows in the same event."""
    gr = pytest.importorskip("gradio")
    SEEN_SHELL_HANDLES.clear()
    specs = [_switching_spec("try", "Try it", "race"), _fake_spec("play", "Playground")] + [
        app_mod.unavailable_spec(tab, "not in this test build") for tab in TABS[2:]
    ]
    blocks, _, _ = app_mod.build_blocks(state, space_id=None, stamp=STAMP, specs=specs, modules={})
    assert len(SEEN_SHELL_HANDLES) == 1
    handle = SEEN_SHELL_HANDLES[0]
    assert set(handle) == {"permalink", "base"} and handle["base"] == ""
    box = handle["permalink"]
    assert box.__class__ is gr.Textbox and "alg-permalink" in box.elem_classes
    chip_click = next(
        fn for fn in blocks.fns.values() if any(trigger == "click" for _, trigger in fn.targets)
    )
    assert box in chip_click.outputs and chip_click.api_visibility == "private"
    tabs_update, link = chip_click.fn()
    assert isinstance(tabs_update, gr.Tabs) and link == "?tab=race"


def test_load_hooks_run_on_page_load_and_stay_off_the_api(state: Any) -> None:
    """A component with a callable value would expose /lambda in /gradio_api/info; the handle
    protocol registers the same page-load refresh with api_name=False."""
    gr = pytest.importorskip("gradio")
    specs = [_fake_spec("try", "Try it", "try_run"), _load_hook_spec("play", "Playground")] + [
        app_mod.unavailable_spec(tab, "not in this test build") for tab in TABS[2:]
    ]
    blocks, _, _ = app_mod.build_blocks(state, space_id=None, stamp=STAMP, specs=specs, modules={})
    load_deps = [
        fn for fn in blocks.fns.values() if any(trigger == "load" for _, trigger in fn.targets)
    ]
    assert len(load_deps) == 3, "the shell's on_load, the boot card's re-render, the tab's hook"
    assert all(fn.api_visibility == "private" for fn in load_deps)
    hook = [fn for fn in load_deps if len(fn.outputs) == 1 and fn.fn() == "<p>loaded</p>"]
    assert len(hook) == 1 and hook[0].outputs[0].__class__ is gr.HTML
    visible = [fn for fn in blocks.fns.values() if fn.api_visibility != "private" and fn.api_name]
    assert sorted(fn.api_name for fn in visible) == ["try_run"]


def test_load_tab_module_tolerates_only_a_missing_tab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(app_mod.TAB_MODULES, "race", "tabs.no_such_tab")
    assert app_mod.load_tab_module("race") is None
    spec = app_mod.unavailable_spec("race", "tabs.no_such_tab is not part of this build.")
    assert spec.id == "race" and spec.label == "Races" and spec.api_names == ()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("tabs.definitely_missing_dependency_probe")


def test_every_real_tab_builds_from_the_boot_state(
    state: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def offline(*args: Any, **kwargs: Any) -> Any:
        raise urllib.error.URLError("offline in tests")

    monkeypatch.setattr("urllib.request.urlopen", offline)
    specs, modules = app_mod.load_tabs(state)
    assert [s.id for s in specs] == list(TABS)
    assert set(modules) == set(TABS), "all six tab modules are part of this build"
    for spec in specs:
        shell.check_copy(spec.label, max_words=shell.HEADLINE_WORDS, what=f"{spec.id} label")
        assert spec.api_names and all(n.startswith(f"{spec.id}_") for n in spec.api_names), spec
    css = app_mod.page_css(modules)
    assert "!important" not in css
    assert ".alg-tabs.alg-tabs.alg-tabs.alg-tabs" in css and ".alg-card.alg-card" in css


IDENTIFIER_RE = re.compile(r"[a-z0-9]_[a-z0-9]|[A-Z]_[A-Z]|torch\d+-|https?://")


def test_headline_counts_what_loaded_never_the_catalogue(state: Any) -> None:
    """One truth for the header: the functions that loaded here (`functions_loaded`), not the
    umbrella's published catalogue (`function_count`), so a failed family lowers the number
    the way it lowers the Try tab's Hub tile — `app.headline` is `boot_sequence.headline`."""
    facts = state.facts
    text = app_mod.headline(facts)
    assert text == f"{facts['functions_loaded']:,} compiled Mojo kernels"
    assert len(text.split()) <= shell.HEADLINE_WORDS
    assert app_mod.headline({}) == "Compiled Mojo kernels"
    assert app_mod.headline is boot_sequence.headline
    # the umbrella loaded and one family did not: the catalogue says 6,040, the page 5,683
    partial = {
        "function_count": 6040,
        "functions_loaded": 5683,
        "families_loaded": ["stats", "text"],
        "families_failed": {"llm": "variant_unavailable"},
    }
    assert app_mod.headline(partial) == "5,683 compiled Mojo kernels"


def test_badges_are_words_with_no_variant_string(state: Any) -> None:
    pills = app_mod.badges(state)
    assert ("1 of 19 Mojo kernel families · this container", "warn") in pills, pills
    for text, variant in pills:
        assert shell.machine_token(text) is None, text
        assert not IDENTIFIER_RE.search(text), text
        assert "torch" not in text and "Hub kernels" not in text, text
        assert variant in ("", "ok", "warn")
    complete = boot_sequence.BootState(
        registry=state.registry,
        lane=state.lane,
        limits=state.limits,
        killswitch=state.killswitch,
        hook=state.hook,
        env={"SPACE_HARDWARE": "cpu-upgrade"},
        started_utc=state.started_utc,
        facts={"functions_loaded": 6040, "families_loaded": [f"f{i}" for i in range(19)]},
    )
    assert app_mod.badges(complete) == [
        ("19 Mojo kernel families · this container", ""),
        ("CPU upgrade", ""),
    ]
    complete.floor_ok = False
    assert app_mod.badges(complete)[-1] == (app_mod.PILL_FLOOR, "warn")
    complete.floor_ok = True
    complete.facts = {"families_loaded": ["stats"], "families_published": 1}
    complete.env = {}
    assert app_mod.badges(complete) == [("1 Mojo kernel family · this container", "")]
    complete.facts = {}
    assert app_mod.badges(complete) == [], "no facts, no count pill"


def test_tier_label_reads_the_hub_flavour_in_words() -> None:
    cases = {
        "": "",
        "cpu-basic": "CPU basic",
        "cpu-upgrade": "CPU upgrade",
        "l4x1": "L4 GPU",
        "l4x4": "4× L4 GPU",
        "l40sx8": "8× L40S GPU",
        "t4-small": "T4 GPU · small",
        "a10g-largex2": "A10G GPU · large ×2",
        "a100-large": "A100 GPU · large",
        "zero-a10g": "ZeroGPU A10G",
        "something-new": "something new",
    }
    for tier, label in cases.items():
        assert app_mod.tier_label(tier) == label, tier
        assert not IDENTIFIER_RE.search(label), label


def test_headline_badges_and_css_obey_the_rules(state: Any) -> None:
    text = app_mod.headline(state.facts)
    assert len(app_mod.SUBLINE.split()) <= shell.SUBLINE_WORDS
    pills = app_mod.badges(state)
    header = shell.render_header(
        text, app_mod.SUBLINE, pills, active="Flagship", space_id="thyn-ai/algenta"
    )
    _assert_clean_copy(header)
    _assert_stylesheet_discipline(app_mod.APP_CSS)
    _assert_four_class_selectors(app_mod.APP_CSS)
    # the shell blocks drop Gradio's 16 px container padding and the phone page column drops its
    # own, so header, tabs, cards and footer share one edge (16 px on a phone) — round 3's P1
    assert f".{app_mod.SHELL_BLOCK_CLASS}" * 4 + " { padding: 0; }" in app_mod.APP_CSS
    assert f".{app_mod.SHELL_BLOCK_CLASS}" * 4 + " > div { padding: 0; }" in app_mod.APP_CSS
    phone = app_mod.APP_CSS[app_mod.APP_CSS.index("@media") :]
    assert "margin: 0 -16px; width: calc(100% + 32px); padding: 0 0 48px;" in phone
    for label in (app_mod.LABEL_PERMALINK, app_mod.LABEL_BOOT, *app_mod.TAB_LABELS.values()):
        shell.check_copy(label, max_words=shell.HEADLINE_WORDS)


# ---------------------------------------------------------------------------
# Card, image, pins, lint
# ---------------------------------------------------------------------------


def _frontmatter() -> dict[str, str]:
    lines = (APP_DIR / "README.md").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    out: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"')
    out["tags"] = " ".join(
        line.strip()[2:] for line in lines[1:end] if line.strip().startswith("- ")
    )
    return out


def test_readme_frontmatter_is_the_plans_card() -> None:
    front = _frontmatter()
    assert front["title"] == "Algenta" and front["emoji"] == "⚡"
    assert (front["colorFrom"], front["colorTo"]) == ("purple", "blue")
    assert front["sdk"] == "docker" and front["app_port"] == "7860"
    assert front["pinned"] == "true" and front["license"] == "apache-2.0"
    assert front["short_description"] == "6,000+ compiled Mojo kernels. Race them against Python."
    assert set(front["tags"].split()) >= {"kernels", "mojo", "benchmark", "llm", "mcp", "agents"}
    body = (APP_DIR / "README.md").read_text(encoding="utf-8")
    assert "decision engine" not in body.lower() and "@algenta.ai" not in body
    assert "https://algenta.ai/pricing" in body and "https://discord.gg/w8NDsph9an" in body
    assert FAKE_WORDS.search(body.split("---", 2)[2]) is None


def test_dockerfile_invariants() -> None:
    text = (APP_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert text.startswith("# Algenta") and "\nFROM python:3.14-slim\n" in text
    assert re.search(r"^RUN useradd .*--uid 1000 .*user", text, re.M), "non-root uid 1000"
    assert "\nUSER user\n" in text and text.index("USER user") < text.index(
        "boot_sequence.py --bake"
    )
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in text
    assert "HF_HOME=/home/user/.cache/huggingface" in text
    assert "RUN python boot_sequence.py --bake" in text, "the baked cache step"
    assert "RUN HF_HUB_OFFLINE=1 python boot_sequence.py --verify-cache" in text
    assert "\nENV HF_HUB_OFFLINE=1\n" in text and text.index("ENV HF_HUB_OFFLINE=1") > text.index(
        "--bake"
    )
    assert re.findall(r"^EXPOSE\s+(\d+)", text, re.M) == ["7860"]
    assert text.rstrip().endswith('CMD ["python", "app.py"]')
    ignore = (APP_DIR / ".dockerignore").read_text(encoding="utf-8").split()
    assert {"tests/", "__pycache__/", "*.pyc", "*.whl", "*.so", "facts.json"} <= set(ignore)


def test_requirements_lock_is_hash_pinned_for_cp314_linux() -> None:
    lock = (APP_DIR / "requirements.lock").read_text(encoding="utf-8")
    pins = dict(re.findall(r"^([a-z0-9_.\[\]-]+)==([^\s\\]+)", lock, re.M))
    assert pins["gradio"] == "6.28.0" and pins["torch"] == "2.9.1+cpu"
    assert pins["huggingface-hub"] == "1.26.1" and pins["kernels"] == "0.17.1"
    assert pins["algenta"] == "1.0.24" and pins["algenta-runtime-native"] == "1.0.7"
    assert {"mcp", "statsmodels", "scipy", "networkx", "nltk", "sympy", "numpy", "uvicorn"} <= set(
        pins
    )
    assert "--extra-index-url https://download.pytorch.org/whl/cpu" in lock
    hashed = len(re.findall(r"^\s+--hash=sha256:[0-9a-f]{64}", lock, re.M))
    assert hashed >= len(pins), "every pin carries at least one hash"
    assert not re.search(r"==\d[\w.+]*?(?:dev|rc|a\d|b\d|alpha|beta)", lock, re.I), "no pre-release"
    direct = (APP_DIR / "requirements.txt").read_text(encoding="utf-8")
    for line in direct.splitlines():
        if line and not line.startswith(("#", "--")):
            assert "==" in line, f"direct dependency not pinned: {line}"


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff is not on PATH")
def test_flagship_is_ruff_clean() -> None:
    files = [
        str(APP_DIR / name)
        for name in ("app.py", "boot_sequence.py", "permalink.py", "hf_ua_shim.py")
    ]
    result = subprocess.run(
        ["ruff", "check", "--no-cache", *files],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(
        ["ruff", "format", "--check", "--no-cache", *files],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_fake_words_in_the_shipped_modules() -> None:
    for name in ("app.py", "boot_sequence.py", "permalink.py", "hf_ua_shim.py"):
        text = (APP_DIR / name).read_text(encoding="utf-8")
        hits = [m.group(0) for m in FAKE_WORDS.finditer(text)]
        assert hits == [], f"{name}: {hits}"
        assert "decision engine" not in text.lower() and "@algenta.ai" not in text
