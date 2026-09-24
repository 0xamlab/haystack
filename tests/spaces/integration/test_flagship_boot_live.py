"""Live boot of the flagship — real Hub kernels from the baked cache, the real opening card.

Run with

    HF_HOME=<baked cache> HF_HUB_OFFLINE=1 ALGENTA_SPACES_LIVE=1 \\
        <venv>/bin/python -m pytest --confcutdir=tests/spaces tests/spaces/integration -q -m slow \\
        -k flagship_boot

Needs `kernels`, `torch` and a cache prepared by `python apps/spaces/algenta/boot_sequence.py
--bake` (online, once). What is proven: every published family and the umbrella load offline,
the opening z-test is measured under the rulebook (`bench.RULEBOOK_VERSION`) through the one
native lane and agrees with
statsmodels within the printed tolerance, `facts.json` counts the catalogue from the loaded
contracts, and — when gradio is installed — the whole page builds and `/health` says ready.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path

import pytest
from algenta_spaces import bench, hubkernel, killswitch

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("ALGENTA_SPACES_LIVE") != "1", reason="set ALGENTA_SPACES_LIVE=1"
    ),
]

REPO = Path(__file__).resolve().parents[3]
APP_DIR = REPO / "apps" / "spaces" / "algenta"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

HERO_MS_MAX = 50.0  # measured 0.17 ms on Apple M4 Max; single-digit ms on cpu-upgrade


def _no_flags(url: str, etag: str | None) -> killswitch.FetchResult:
    return killswitch.FetchResult(404, None, None)


@pytest.fixture(scope="module")
def state(tmp_path_factory: pytest.TempPathFactory):
    pytest.importorskip("kernels")
    pytest.importorskip("torch")
    boot_sequence = importlib.import_module("boot_sequence")
    env = dict(os.environ)
    env["ALGENTA_FACTS_PATH"] = str(tmp_path_factory.mktemp("facts") / "facts.json")
    booted = boot_sequence.run_boot(env=env, fetch=_no_flags, probe_hosted=False)
    yield booted
    booted.killswitch.stop()
    booted.lane.shutdown(wait=False)


def test_every_family_and_the_umbrella_load_and_warm(state) -> None:
    assert state.ready, state.summary()
    published = {hubkernel.short_family(r).removeprefix("algenta-") for r in hubkernel.TRUST}
    assert set(state.kernels) == published, state.kernel_errors
    assert all(k.warm for k in state.kernels.values())
    umbrella = state.kernels["algenta"]
    assert umbrella.is_umbrella and umbrella.variant == "torch-universal"
    variants = {k.variant for k in state.kernels.values() if not k.is_umbrella}
    assert len(variants) == 1, variants
    stage = state.registry.snapshot()["stages"][1]
    # `boot_sequence.kernels_summary`: the families first, the umbrella named once, never
    # counted as a family (`19 families and the umbrella warm in 2.5 s`).
    assert stage["state"] == "done", stage
    assert re.match(r"19 families and the umbrella warm in \d", stage["detail"]), stage["detail"]
    boot_sequence = importlib.import_module("boot_sequence")  # on sys.path since the fixture ran
    assert stage["detail"] == boot_sequence.kernels_summary(state.preload), stage["detail"]


def test_the_opening_card_is_measured_and_agrees_with_statsmodels(state) -> None:
    """The gate and the parity always hold; the timing is recorded only when the rulebook's
    stability gate passes (a loaded build machine legitimately yields "noisy — not recorded")."""
    pytest.importorskip("statsmodels")
    hero = state.hero
    assert hero is not None, "no hero"
    assert hero.parity is not None and hero.parity.ok, hero.parity
    assert hero.parity.deltas["z"] <= 1e-9 and hero.parity.deltas["p"] <= 1e-7
    assert hero.result[0] == pytest.approx(-1.440793230951582, abs=1e-9)
    assert hero.cell.n in (11, 21) and hero.cell.rulebook == bench.RULEBOOK_VERSION
    assert hero.cell.status in ("measured", "noisy"), hero.cell.reason
    if hero.cell.measured:
        assert hero.kernel_ms is not None and 0 < hero.kernel_ms < HERO_MS_MAX
    else:
        assert hero.cell.reason.startswith("noisy — not recorded"), hero.cell.reason
        assert hero.kernel_ms is None, "a noisy cell carries no number"
    assert hero.cell.lanes and 0 < hero.cell.lanes[0].median_ms < HERO_MS_MAX
    assert state.lane.stats()["completed"] >= 1


def test_facts_count_the_catalogue_from_the_contracts(state) -> None:
    facts = state.facts
    assert facts["umbrella_loaded"] is True
    assert facts["function_count"] >= 6_000, facts["function_count"]
    assert facts["function_count"] == facts["functions_loaded"], "the umbrella is the union"
    assert len(facts["families_loaded"]) == 19 and facts["families_failed"] == {}
    assert facts["kernels"]["stats"]["pinned"] is True
    assert Path(facts["facts_path"]).is_file()
    health = state.health()
    assert health["ready"] is True and health["hero"]["status"] in ("measured", "noisy")


def test_the_page_builds_and_health_reports_ready(state) -> None:
    pytest.importorskip("gradio")
    from starlette.testclient import TestClient

    app_mod = importlib.import_module("app")
    api = app_mod.create_app(state, stamp="0123456789abcdef")
    with TestClient(api) as client:
        health = client.get("/health").json()
        assert health["ready"] is True and health["facts"]["function_count"] >= 6_000
        info = client.get("/gradio_api/info").json()
        names = set(info["named_endpoints"])
        assert {"/try_run", "/play_run", "/race_run"} <= names, names
        assert "0123456789abcdef" in client.get("/config").text
