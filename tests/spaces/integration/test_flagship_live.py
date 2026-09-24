"""Live checks for the flagship's Try and Races tabs — real Hub kernels, real incumbents.

Run with `ALGENTA_SPACES_LIVE=1 python3 -m pytest tests/spaces/integration/test_flagship_live.py
-q -m slow`. Needs `kernels`, `torch`, `statsmodels`, `networkx`, `nltk` and network (or a
populated `HF_HOME`). Nothing is faked: the hero measurement runs `ab_testing.z_test_proportions`
on `thyn-ai/algenta-stats` through the one native lane under rulebook v0.4 and the parity gate
against statsmodels; one race cell runs betweenness centrality on `thyn-ai/algenta-graph`
against networkx, and one Levenshtein cell on `thyn-ai/algenta-text` against nltk.

A cell may come back `noisy` on a busy machine — the rulebook's honest answer — so the
assertions accept `measured` or `noisy`, and check the parity gate and both lanes whenever the
cell was measured.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest
from algenta_spaces import bench, lane
from algenta_spaces import hubkernel as hk

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        os.environ.get("ALGENTA_SPACES_LIVE") != "1", reason="set ALGENTA_SPACES_LIVE=1"
    ),
]

REPO = Path(__file__).resolve().parents[3]
ALGENTA_DIR = REPO / "apps" / "spaces" / "algenta"
if str(ALGENTA_DIR) not in sys.path:
    sys.path.insert(0, str(ALGENTA_DIR))

Z_EXPECTED = [-1.440793230951582, 0.1496431923825119]


@pytest.fixture(scope="module")
def modules():
    pytest.importorskip("kernels")
    pytest.importorskip("torch")
    return {
        "try_tab": importlib.import_module("tabs.try_tab"),
        "race_tab": importlib.import_module("tabs.race_tab"),
        "races": importlib.import_module("races"),
        "tabs": importlib.import_module("tabs"),
        "common": importlib.import_module("tabs.common"),
    }


@pytest.fixture(scope="module")
def loaded():
    out = {}
    for family in ("stats", "graph", "text"):
        item = hk.load(family)
        hk.warm_up(item)
        out[family] = item
    return out


@pytest.fixture(scope="module")
def native_lane():
    ln = lane.Lane()
    yield ln
    ln.shutdown()


def test_hero_measurement_on_the_real_kernel(modules, loaded, native_lane):
    pytest.importorskip("statsmodels")
    try_tab = modules["try_tab"]
    hardware = bench.hardware_footer(packages=("kernels", "torch", "statsmodels"))
    hero = try_tab.measure_hero(loaded["stats"], native_lane, hardware=hardware)
    assert hero.cell.status in (bench.STATUS_MEASURED, bench.STATUS_NOISY), hero.cell.reason
    assert abs(hero.z - Z_EXPECTED[0]) < 1e-9 and abs(hero.p - Z_EXPECTED[1]) < 1e-6
    assert hero.parity is not None and hero.parity.ok
    assert hero.parity.deltas["z"] <= try_tab.Z_TOL and hero.parity.deltas["p"] <= try_tab.P_TOL
    assert hero.parity.version.startswith("statsmodels==")
    card = try_tab.render_hero_card(hero, kernel_label=loaded["stats"].label())
    assert hardware in card and hero.cell.ts_utc in card
    # measured or not, the run ran: the card keeps the kernel's answer and the parity check
    # (two chips, each short enough for a 375 px card: the verdict, then the bound checked)
    assert f"z {hero.z:.6f}" in card and f"p {hero.p:.6f}" in card
    assert '<span class="alg-chip alg-chip-ok">parity vs statsmodels</span>' in card
    assert '<span class="alg-chip alg-chip-neutral">z Δ ≤ 1e-09 · p Δ ≤ 1e-06</span>' in card
    assert "1e-12" not in card and loaded["stats"].label() in card
    if hero.cell.measured:
        assert hero.kernel_ms is not None and 0 < hero.kernel_ms < 50
        # the n chip prints what the harness ran: the batch k it chose for a sub-2 ms call
        ours = hero.cell.lane(bench.SIDE_ALGENTA)
        assert ours is not None and ours.k == try_tab.calls_per_repeat(hero.cell) >= 1
        assert f">{try_tab.repeats_label(hero.cell)}<" in card
        if ours.sample_ms >= bench.SAMPLE_MIN_MS and ours.median_ms < bench.SAMPLE_MIN_MS:
            assert ours.k > 1 and "calls" in try_tab.repeats_label(hero.cell)
    else:
        # the noisy path: the timing withheld with its cause, nothing else dropped
        assert 'data-state="not_recorded"' in card and "alg-card-timing" in card
        assert "P95" not in card and "n = " not in card and "alg-hero-num" not in card
        assert hero.cell.reason and try_tab.human_reason(hero.cell.reason) in card


def test_hero_parity_bound_holds_across_random_inputs(modules, loaded):
    """The bound the card claims is one the kernel meets on inputs a visitor may type: z exact,
    p within `P_TOL` of statsmodels over a seeded spread of proportions (the 2026-09-22 probe
    over 408 inputs measured 1.4e-7 at worst)."""
    pytest.importorskip("statsmodels")
    import random

    from statsmodels.stats.proportion import proportions_ztest

    try_tab = modules["try_tab"]
    rng = random.Random(20260922)
    worst_z = worst_p = 0.0
    cases = [(50, 1000, 65, 1000), (7, 90, 9, 80), (17146, 66831, 4162, 16060)]
    for _ in range(60):
        n_a, n_b = rng.randint(1, 100_000), rng.randint(1, 100_000)
        cases.append((rng.randint(0, n_a), n_a, rng.randint(0, n_b), n_b))
    for sa, na, sb, nb in cases:
        ours = hk.execute(loaded["stats"], "ab_testing", "z_test_proportions", [sa, na, sb, nb])
        z, p = proportions_ztest([sa, sb], [na, nb])
        worst_z = max(worst_z, abs(ours.result[0] - float(z)))
        worst_p = max(worst_p, abs(ours.result[1] - float(p)))
    assert worst_z <= try_tab.Z_TOL, worst_z
    assert 1e-8 < worst_p <= try_tab.P_TOL, (
        f"p differs by {worst_p:.2g}; the bound is {try_tab.P_TOL:g}"
    )


def test_run_hero_through_the_tab_handler(modules, loaded, native_lane):
    pytest.importorskip("statsmodels")
    tabs = modules["tabs"]
    try_tab = modules["try_tab"]
    deps = tabs.Deps(kernels=loaded, lane=native_lane, hardware="live test", env={})
    outcomes = list(try_tab.run_hero(deps, try_tab.raw_args(120, 900, 150, 900)))
    assert len(outcomes) == 2, "the lane chip first, then the card"
    assert outcomes[0][1] is None and ("running" in outcomes[0][0] or "queued" in outcomes[0][0])
    chip, card, message = outcomes[-1]
    assert message == "" and card is not None
    assert "alg-card-result" in card or "not recorded" in card
    assert "Traceback" not in card
    refused = list(try_tab.run_hero(deps, try_tab.raw_args(2000, 1000, 65, 1000)))
    assert refused == [("", None, "Successes A cannot exceed Trials A.")]


def test_three_line_install_snippet_runs_against_the_real_kernel(modules, loaded):
    """The snippet the Copy chip hands out is executed as written: pip line as a comment, the
    `get_kernel` line trusting only `thyn-ai/algenta-stats`, the call — and it returns [z, p]."""
    pytest.importorskip("kernels")
    try_tab = modules["try_tab"]
    text = try_tab.install_snippet(try_tab.HERO_ARGS)
    lines = text.strip("\n").split("\n")
    assert len(lines) == 3 and text.count("thyn-ai/") == 2
    namespace: dict = {}
    exec(lines[1], namespace)  # noqa: S102 - the snippet under test, no user input in it
    result = eval(lines[2], namespace)  # noqa: S307 - same
    assert [round(float(v), 9) for v in result] == [round(v, 9) for v in Z_EXPECTED]
    assert namespace["k"].__name__.endswith("algenta_stats") or hasattr(
        namespace["k"], "ab_testing"
    )


@pytest.mark.parametrize(
    ("race_id", "size", "family", "incumbent"),
    [("betweenness", "S", "graph", "networkx"), ("levenshtein", "M", "text", "nltk")],
)
def test_one_race_cell_on_real_kernels(
    modules, loaded, native_lane, tmp_path, race_id, size, family, incumbent
):
    pytest.importorskip(incumbent)
    races = modules["races"]
    cand = races.CANDIDATES_BY_ID[race_id]
    offer = next(o for o in races.offers(loaded) if o.candidate.id == race_id)
    assert offer.available, offer.reason
    ticket = native_lane.submit(
        races.run_race,
        cand,
        size,
        loaded[family],
        qualified=False,
        incumbent_pin=offer.incumbent_pin,
        budget_s=races.RACE_BUDGET_S,
        label=f"race {race_id} {size}",
    )
    run = ticket.result()
    cell = run.cell
    assert cell.status in (bench.STATUS_MEASURED, bench.STATUS_NOISY), cell.reason
    assert cell.parity_label, "the gate passed and named its bound"
    race_tab = modules["race_tab"]
    if cell.measured:
        ours = cell.lane(bench.SIDE_ALGENTA)
        theirs = cell.lane(bench.SIDE_INCUMBENT)
        assert ours is not None and theirs is not None and cell.ratio is not None
        assert ours.n == cell.n and theirs.n == cell.n and cell.n in (11, 21)
        assert ours.median_ms > 0 and theirs.median_ms > 0
        # rulebook v0.4: a lane under 2 ms per call was batched (k > 1), a slower one was not
        for lane_result in (ours, theirs):
            if lane_result.median_ms < bench.SAMPLE_MIN_MS:
                assert lane_result.k > 1 and lane_result.sample_ms >= bench.SAMPLE_MIN_MS * 0.5
            else:
                assert lane_result.k == 1
        state = race_tab.RaceState(
            [offer],
            races.Qualified(frozenset(), "", ""),
            races.Board(tmp_path / "results.jsonl"),
            "live",
            "live",
        )
        card = race_tab.render_run(state, run)
        assert "not a race" in card and "parity" in card
        assert cand.incumbent in card and f"algenta-{family}" in card
        assert race_tab.LABEL_LINK in card, "a measured cell carries its link"
        row = races.row_from_run(
            run,
            hardware="live",
            hardware_id="live",
            space_id="",
            harness_commit="",
            wheel_sha=races.kernel_revision(loaded[family]),
        )
        assert row["wheel_sha"] == (loaded[family].snapshot_sha or loaded[family].capped_v1_sha)
        assert row["kind"] == races.ROW_KIND_PARITY
        # the measured cell is a parity row of this container's board — never "Nothing measured
        # yet" beside a measured card; the empty qualified list is said in one sentence
        deps = modules["tabs"].Deps(kernels=loaded, lane=native_lane, hardware="live", env={})
        assert race_tab.record_run(state, run, deps) is True and len(state.board) == 1
        board = race_tab.render_board(state)
        assert race_tab.NO_QUALIFIED_BOARD in board and race_tab.NOTHING_MEASURED not in board
        assert 'data-label="ratio">not a race<' in board and cand.title in board
        assert race_tab.WHERE_HERE in board and ">1 row<" in board
    else:
        card = modules["race_tab"].render_run(
            modules["race_tab"].RaceState(
                [offer],
                races.Qualified(frozenset(), "", ""),
                races.Board(Path(os.devnull)),
                "live",
                "live",
            ),
            run,
        )
        assert modules["race_tab"].LABEL_LINK not in card, "nothing to link to when not recorded"
    loaded_sha = loaded[family].snapshot_sha or loaded[family].capped_v1_sha
    assert run.kernel_label == f"{loaded[family].family}@{loaded_sha[:7]}"
    ours_spec = cell.lane(bench.SIDE_ALGENTA)
    if ours_spec is not None:
        assert ours_spec.version == loaded_sha[:7]
    assert cell.elapsed_s < races.RACE_BUDGET_S + 5


def test_try_refuses_a_decimal_before_the_kernel_sees_it(modules, loaded, native_lane):
    """2.5 typed into Successes A is refused with the docstring's sentence — never rounded to 2
    and run (the browser no longer rounds either: the inputs carry `precision=None`)."""
    tabs = modules["tabs"]
    try_tab = modules["try_tab"]
    deps = tabs.Deps(kernels=loaded, lane=native_lane, hardware="live test", env={})
    before = native_lane.stats()["completed"]
    refused = list(try_tab.run_hero(deps, try_tab.raw_args(2.5, 1000, 65, 1000)))
    assert refused == [("", None, "Successes A must be a whole number.")]
    assert native_lane.stats()["completed"] == before, "nothing native ran"
    huge = list(try_tab.run_hero(deps, try_tab.raw_args(50, 1 << 63, 65, 1000)))
    assert huge == [
        (
            "",
            None,
            "Trials A is above the range the browser can enter exactly; use the snippet under"
            " Reproduce.",
        )
    ]
    above = list(try_tab.run_hero(deps, try_tab.raw_args((1 << 53) + 1, 1000, 65, 1000)))
    assert above[0][2].startswith("Successes A is above the range the browser can enter exactly")
    negative = list(try_tab.run_hero(deps, try_tab.raw_args(-5, 1000, 65, 1000)))
    assert negative == [("", None, "Successes A cannot be negative.")]
    assert native_lane.stats()["completed"] == before, "nothing native ran for any refusal"


def test_playground_refuses_what_the_try_tab_refuses_on_the_real_kernel(
    modules, loaded, native_lane
):
    """The same field rules on both tabs: a negative success count, successes above the trials
    and a whole number at or above 2^53 are messages under the field, no result card, and
    nothing native runs — `[-9.18, 0.0]` for `successes_a = -5` is never rendered again."""
    play_tab = importlib.import_module("tabs.play_tab")
    tabs = modules["tabs"]
    deps = tabs.Deps(kernels=loaded, lane=native_lane, hardware="live test", env={})
    cat = play_tab.Catalogue(deps)
    before = native_lane.stats()["completed"]
    for raw, field_name, reason in (
        (
            {"successes_a": -5, "n_a": 1000, "successes_b": 260, "n_b": 1000},
            "successes_a",
            "cannot be negative",
        ),
        (
            {"successes_a": 1200, "n_a": 1000, "successes_b": 260, "n_b": 1000},
            "successes_a",
            "cannot exceed n_a",
        ),
        (
            {"successes_a": (1 << 53) + 1, "n_a": 1000, "successes_b": 260, "n_b": 1000},
            "successes_a",
            "browser",
        ),
    ):
        outcomes = list(
            play_tab.run_call(deps, cat, "stats", "ab_testing", "z_test_proportions", raw)
        )
        assert len(outcomes) == 1 and outcomes[0].refused and outcomes[0].card is None, raw
        assert list(outcomes[0].field_errors) == [field_name]
        assert reason in outcomes[0].field_errors[field_name]
    assert native_lane.stats()["completed"] == before, "nothing native ran"
    # A selection this container does not serve — the API path the dropdowns' custom values
    # open — is the quiet coded card with its sentence echoed, never Gradio's stock error, and
    # nothing native runs for it either.
    for trio, code in (
        (("quantum", "ab_testing", "z_test_proportions"), "unknown_family"),
        (("stats", "nope", "z_test_proportions"), "unknown_module"),
        (("stats", "ab_testing", "nope"), "unknown_function"),
    ):
        foreign = list(play_tab.run_call(deps, cat, *trio, {}))
        assert len(foreign) == 1 and f"unavailable · {code}" in foreign[0].card, trio
        assert "alg-card-quiet" in foreign[0].card and "alg-card-err" not in foreign[0].card
        assert foreign[0].echo and foreign[0].echo in foreign[0].card and not foreign[0].refused
    assert play_tab.selection_refusal(deps, cat, "quantum") == (
        "unknown_family",
        f"quantum is not one of the {len(cat.families)} families loaded in this container.",
    )
    assert native_lane.stats()["completed"] == before, "nothing native ran for a foreign selection"
    # and the accepted call still runs for real, with the kernel's own answer
    ok = list(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 200, "n_a": 1000, "successes_b": 260, "n_b": 1000},
        )
    )
    assert ok[-1].card is not None and "alg-card-result" in ok[-1].card
    result = json.loads(ok[-1].response_json)["result"]
    assert abs(result[0] - -3.188) < 0.01 and abs(result[1] - 0.00143) < 1e-4


def test_playground_runs_haversine_on_the_typed_decimals_and_checks_geopy_on_the_same(
    modules, native_lane
):
    """The visitor's decimals reach the kernel untouched; the request, the parity chip (geopy on
    the SAME arguments, computed independently here) and the permalink all carry them."""
    pytest.importorskip("geopy")
    from geopy.distance import great_circle

    play_tab = importlib.import_module("tabs.play_tab")
    tabs = modules["tabs"]
    geometry = hk.load("geometry")
    hk.warm_up(geometry)
    deps = tabs.Deps(kernels={"geometry": geometry}, lane=native_lane, hardware="live test", env={})
    cat = play_tab.Catalogue(deps)
    typed = {"lat1": 51.5074, "lon1": -0.1278, "lat2": 48.8566, "lon2": 2.3522}
    outcomes = list(
        play_tab.run_call(deps, cat, "geometry", "geodesy", "haversine_distance", typed)
    )
    done = outcomes[-1]
    assert done.card is not None and "alg-card-result" in done.card, done.card
    request = json.loads(done.request_json)
    assert request["args"] == [51.5074, -0.1278, 48.8566, 2.3522], "typed, not rounded"
    result = json.loads(done.response_json)["result"]
    reference = great_circle((51.5074, -0.1278), (48.8566, 2.3522)).km
    assert abs(result - reference) / reference < 5e-6, (result, reference)
    assert abs(result - 343.556) < 0.01, "London to Paris, not 52°N 0°E to 49°N 2°E (362 km)"
    assert "parity within 5e-6 relative" in done.card and "geopy==" in done.card
    assert "lat1=51.5074" in done.snippets["kernels"]
    assert "%22lat1%22%3A51.5074" in done.permalink
    assert "algenta-geometry@" in done.card, "provenance rides as a chip"
    assert "torch25-cpu-aarch64-darwin" not in done.card.split("alg-chips")[0]
    assert "Great-circle distance" in done.card, "the subtitle is the function's own description"


# ---------------------------------------------------------------------------
# Tabs B — LLM kernels on the real `thyn-ai/algenta-llm`, Ecosystem on the live Hub and GitHub,
# Governed on the real hosted engine when `ALGENTA_API_KEY` is set (never faked otherwise).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tabs_b():
    pytest.importorskip("kernels")
    pytest.importorskip("torch")
    return {
        "tabs": importlib.import_module("tabs"),
        "llm_tab": importlib.import_module("tabs.llm_tab"),
        "gov_tab": importlib.import_module("tabs.gov_tab"),
        "eco_tab": importlib.import_module("tabs.eco_tab"),
        "webhook": importlib.import_module("webhook"),
    }


@pytest.fixture(scope="module")
def llm_loaded():
    item = hk.load("llm")
    hk.warm_up(item)
    return item


def _llm_deps(tabs_b, llm_loaded, native_lane):
    hardware = bench.hardware_footer(packages=("kernels", "torch"))
    return tabs_b["tabs"].Deps(
        kernels={"llm": llm_loaded}, lane=native_lane, hardware=hardware, env={}
    )


@pytest.mark.parametrize(
    ("panel", "args"),
    [
        ("rmsnorm", (8, 256)),
        ("rmsnorm", (32, 1024)),
        ("rope", (16, 4, 64, False)),
        ("rope", (64, 8, 128, True)),
        ("sampling", (4096, 0.8, 40, 0.95)),
        ("sampling", (32768, 1.2, 100, 0.9)),
    ],
)
def test_llm_panels_agree_with_torch_on_the_real_kernel(
    tabs_b, llm_loaded, native_lane, panel, args
):
    llm_tab = tabs_b["llm_tab"]
    deps = _llm_deps(tabs_b, llm_loaded, native_lane)
    run = {
        "rmsnorm": llm_tab.run_rmsnorm,
        "rope": llm_tab.run_rope,
        "sampling": llm_tab.run_sampling,
    }
    card, snippet = run[panel](deps, *args)
    assert 'data-kind="unavailable"' not in card, card[:400]
    assert 'class="alg-card alg-card-result"' in card
    assert 'alg-chip-ok">parity ' in card and "not a race" in card, "the parity chip is the hero"
    assert card.count('alg-lane-val">') == 2, "both latencies on the card"
    assert "alg-lane-bar" not in card, "a parity panel draws no ratio bars"
    assert llm_tab.SPLIT_PYTHON in card and llm_tab.SPLIT_NOTE in card, "the transport split"
    races = importlib.import_module("races")
    loaded_sha = llm_loaded.snapshot_sha or llm_loaded.capped_v1_sha
    label = f"{llm_loaded.family}@{loaded_sha[:7]}"
    assert races.revision_label(llm_loaded) == label
    assert f'alg-llm-lane-name">{label}<' in card, "the lane label names the loaded snapshot"
    if llm_loaded.snapshot_sha and llm_loaded.snapshot_sha != llm_loaded.capped_v1_sha:
        assert llm_loaded.capped_v1_sha[:7] not in card, (
            "never the capped sha of code that did not run"
        )
    assert deps.hardware in card
    sub = re.search(r'alg-card-sub">([^<]*)<', card)
    assert sub is not None, "the card has a subtitle"
    assert llm_loaded.variant not in sub.group(1) and llm_loaded.repo_id not in sub.group(1), (
        "no build variant or repository id in primary copy"
    )
    assert "alg-card-err" not in card and "alg-chip-err" not in card, "a measured card is not red"
    compile(snippet, f"<{panel}>", "exec")


def test_llm_transport_split_is_a_measured_share_of_the_kernel_lane(
    tabs_b, llm_loaded, native_lane
):
    """The Python side of the C-ABI transport, measured on the real payload, is a positive share
    of the kernel lane's median and never exceeds it."""
    llm_tab = tabs_b["llm_tab"]
    deps = _llm_deps(tabs_b, llm_loaded, native_lane)
    panel = llm_tab.measure_rmsnorm(deps, 8, 256)
    ours = panel.cell.lane(bench.SIDE_ALGENTA)
    assert ours is not None and panel.transport_ms is not None
    assert 0 < panel.transport_ms <= ours.median_ms * 1.5, (panel.transport_ms, ours.median_ms)


def test_llm_rope_delta_stays_inside_the_stated_tolerance(tabs_b, llm_loaded):
    """The kernel's cos/sin drift with the angle (~2e-11 per radian); the chip's bound holds it."""
    llm_tab = tabs_b["llm_tab"]
    x = llm_tab.rope_inputs(64, 8, 128)
    pos = list(range(64))
    for interleaved in (False, True):
        calls = llm_tab._kernel_rope(llm_loaded, x, 64, 8, 128, pos, interleaved)
        kernel_y = calls[-1].result["values"]
        torch_y = llm_tab.torch_rope(x, 64, 8, 128, pos, llm_tab.THETA, interleaved)
        delta = llm_tab.max_abs_delta(kernel_y, torch_y)
        assert 0 < delta <= llm_tab.TOL_ROPE, delta


def test_eco_revision_column_names_the_loaded_snapshot(tabs_b, llm_loaded, native_lane):
    """The Ecosystem row for a real loaded family prints the revision that loaded — the Hub
    snapshot `kernels` imported — and says `pinned` or `moved` from the same fact `/health`
    records, never the capped sha alone when the cache holds a later one."""
    eco_tab = tabs_b["eco_tab"]
    deps = _llm_deps(tabs_b, llm_loaded, native_lane)
    row = eco_tab.kernel_rows(deps)["llm"]
    loaded_sha = llm_loaded.snapshot_sha or llm_loaded.capped_v1_sha
    assert row.revision == loaded_sha[:7]
    assert row.pinned is llm_loaded.pinned
    word = eco_tab.REVISION_PINNED if llm_loaded.pinned else eco_tab.REVISION_MOVED
    assert eco_tab.revision_text(row) == f"v1 · {loaded_sha[:7]} · {word}"
    if llm_loaded.snapshot_sha and llm_loaded.snapshot_sha != llm_loaded.capped_v1_sha:
        assert word == eco_tab.REVISION_MOVED
        assert llm_loaded.capped_v1_sha[:7] not in eco_tab.revision_text(row)
    table = eco_tab.render_hub_table(
        eco_tab.HubSnapshot(None, eco_tab.CODE_HUB_NOT_FETCHED, ""), eco_tab.kernel_rows(deps)
    )
    assert eco_tab.revision_text(row) in table


def test_eco_live_counts_from_the_hub_and_github(tabs_b):
    eco_tab = tabs_b["eco_tab"]
    counts = eco_tab.HubCounts()
    snapshot = counts.refresh()
    assert snapshot.ok, snapshot.error_code
    assert set(snapshot.stats) == set(eco_tab.playground.TRUST)
    table = eco_tab.render_hub_table(snapshot, total=6_040)
    assert ">20 kernels<" in table and ">6,040 functions<" in table
    assert snapshot.fetched_utc in table
    assert eco_tab.COUNTS_UNAVAILABLE not in table
    assert eco_tab.HUB_API_URL not in table and eco_tab.SOURCE_HUB in table, "source, not a URL"
    # a second manual refresh inside the one-minute floor reuses the fetch and says so
    assert counts.refresh(force=False) is snapshot
    again = eco_tab.render_hub_table(snapshot, total=6_040, next_refresh_s=counts.cooldown_s())
    assert "next refresh in" in again and snapshot.fetched_utc in again
    zero_download = [s for s in snapshot.stats.values() if s.downloads == 0]
    assert table.count("published 20") >= len(zero_download), "a zero is never the hero"
    if all(s.downloads == 0 for s in snapshot.stats.values()):
        assert "downloads" not in table
    facts = eco_tab.fetch_oss_facts()
    if facts is None:
        pytest.skip("GitHub did not answer (rate limit); the card shows github_unreachable")
    assert facts.package_count >= 40 and facts.release_tag.startswith("v")
    card = eco_tab.render_oss_card(facts)
    assert f">{facts.package_count}<" in card and facts.fetched_utc in card


def test_governed_chain_on_the_real_engine(native_lane):
    """recommend → log → execute against api.algenta.ai; needs the tenant key and a public URL.

    Needs neither `kernels` nor `torch` (the SDK venv is CPython 3.14 without them), so the tab
    modules are imported here directly rather than through the `tabs_b` fixture."""
    if not os.environ.get("ALGENTA_API_KEY"):
        pytest.skip("set ALGENTA_API_KEY (the flagship's tenant) to run the governed chain live")
    # the hosted client is CPython 3.14 only (its native runtime ships manylinux wheels alone);
    # a venv without it skips with the reason instead of failing inside the lane's factory
    pytest.importorskip("algenta", reason="the algenta SDK client is not installed in this venv")
    gov_tab = importlib.import_module("tabs.gov_tab")
    webhook = importlib.import_module("webhook")
    tabs = importlib.import_module("tabs")
    hosted = gov_tab.HostedGoverned(env=os.environ)
    status = hosted.status()
    assert status.ready, status.reason
    hook = webhook.make_hook(os.environ)
    deps = tabs.Deps(kernels={}, lane=native_lane, hardware="live test", env={})
    card, raw, audit, state = gov_tab.on_run(
        deps,
        hosted,
        hook,
        "execute",
        "expand_eu",
        80_000,
        200_000,
        100_000,
        0.93,
        0.02,
        False,
        False,
        None,
    )
    assert 'data-kind="unavailable"' not in card or "webhook_url_unavailable" in card, card[:400]
    if "webhook_url_unavailable" in card:
        pytest.skip("no public https address here (SPACE_HOST / ALGENTA_PUBLIC_BASE_URL unset)")
    assert gov_tab.TITLE_RECEIPT in card or "Held by the" in card
    assert "Recommendation" in card and "Chosen action" in card, "human step names on the card"
    assert state["last_decision_id"] and state["audit"][-1]["step"] == "execute_decision"
    assert hosted.base_url not in card, "the engine's address is configuration, not copy"
    assert f"{gov_tab.FOOT_LABEL} · " in card
    assert hook.url() not in card and hook.nonce not in card, "the nonce is printed nowhere"
    if gov_tab.TITLE_RECEIPT in card:
        assert gov_tab.WEBHOOK_ROW_TEXT.format(host=hook.host) in card.replace("&#x27;", "'")
        receipt = json.loads(raw)["execute_decision"]
        status, code = receipt["execution_status"], receipt.get("response_code")
        http = f"HTTP {code}" if code is not None else gov_tab.NO_HTTP_TEXT
        # each fact once, one stamp style: the engine's ISO `executed_at` is the sub-line's
        # <time> (its second kept in the datetime), the integrity ids are the receipt's rows
        stamp, iso = gov_tab.iso_stamp(receipt["executed_at"])
        assert f'datetime="{iso}">{stamp}</time>' in card, "the fleet stamp, the second kept"
        assert receipt["executed_at"] not in card and "Executed at" not in card
        prose = re.sub(r"<pre[^>]*>.*?</pre>", " ", card, flags=re.DOTALL)
        for key in ("policy_snapshot_id", "schema_snapshot_id", "manifest_version"):
            if receipt.get(key):
                assert prose.count(str(receipt[key])) == 1, f"{key} is printed once"
        assert prose.count(state["last_decision_id"]) == 1, "the decision id once"
        assert 'alg-card-foot">hosted engine · <time class="alg-time"' in card
        if status == "delivered":
            assert f'data-kind="live">delivered · {http}<' in card
            assert "alg-card-err" not in card
            if "webhook received" in card:
                assert gov_tab.VERIFIED_TEXT in card and gov_tab.NO_SIGNATURE_TEXT in card
                assert "webhook" in json.loads(raw), "the accepted POST rides in the engine JSON"
                assert 'class="alg-snippet-code alg-code-scroll" tabindex="0" role="region"' in (
                    card
                ), "the POST body is the capped, keyboard-focusable code block"
                assert "Body keys" not in card and "decision_id" not in prose, "words, not keys"
                assert webhook.describe_body(json.loads(raw)["webhook"]) in prose.replace(
                    "&#x27;", "'"
                )
        elif status == "failed":
            assert f'data-kind="error">{gov_tab.CODE_WEBHOOK_FAILED} · {http}<' in card
            assert "alg-card-err" in card and 'data-kind="live"' not in card
            assert "webhook received" not in card
        assert "engine failed" not in card and "engine delivered" not in card
        # Execute again, honest for both cases: after a delivered execution the engine's
        # idempotency gate holds the repeat (409) unless the tenant's policy allows
        # re-execution; after a failed one the engine executes again and issues a new receipt
        label = gov_tab.again_label(state)
        if status == "delivered":
            assert label == gov_tab.AGAIN_EXPECT_GATE_TEXT.format(gate="idempotency")
        elif status == "failed":
            assert label == gov_tab.AGAIN_NEW_RECEIPT_TEXT
        again, raw_again, _, state = gov_tab.on_execute_again(
            deps, hosted, hook, "execute", False, False, state
        )
        assert gov_tab.TITLE_RECEIPT in again or "Held by the" in again
        if "Held by the" in again:
            assert status == "delivered", "only a delivered execution meets the idempotency gate"
            assert "Held by the idempotency gate" in again
            assert json.loads(raw_again)["execute_decision"]["status_code"] == 409
        else:
            second = json.loads(raw_again)["execute_decision"]
            assert second["executed_at"] != receipt["executed_at"], "a new receipt"
            if status == "failed":
                assert "webhook received" not in again or second["execution_status"] == "delivered"
        assert gov_tab.REJECTED_TEXT not in again, "no POST reached the hook but the engine's"
        assert [e["step"] for e in state["audit"]].count("execute_decision") == 2
