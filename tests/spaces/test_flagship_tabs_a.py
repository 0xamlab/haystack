"""Flagship tabs A — Try it, Playground, Races — and `races.py`, against fakes.

No Hub, no network, no native code: the kernels are the darwin contract fixtures behind a fake
`execute`, the incumbents are the real pure-Python packages (nltk, networkx, sympy) on seeded
workloads, the lane is the real `Lane`, the clock is fake so every rulebook cell is stable.
UI construction runs only where gradio is installed (`pytest.importorskip`).
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import bench, cards, hubkernel, lane, limits, playground, shell

REPO = Path(__file__).resolve().parents[2]
ALGENTA_DIR = REPO / "apps" / "spaces" / "algenta"
TOOLS_DIR = REPO / "apps" / "spaces" / "tools"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
if str(ALGENTA_DIR) not in sys.path:
    sys.path.insert(0, str(ALGENTA_DIR))

tabs = importlib.import_module("tabs")
common = importlib.import_module("tabs.common")
try_tab = importlib.import_module("tabs.try_tab")
play_tab = importlib.import_module("tabs.play_tab")
race_tab = importlib.import_module("tabs.race_tab")
races = importlib.import_module("races")
gpu_status = importlib.import_module("gpu_status")
copy_lint = importlib.import_module("copy_lint")
_REAL_RUN_RACE = races.run_race

HW = f"local run · test cpu · 2 vCPU · Linux x86_64 · Python 3.12.5 · rulebook v{bench.RULEBOOK_VERSION}"
OWNED = [
    ALGENTA_DIR / "races.py",
    ALGENTA_DIR / "tabs" / "__init__.py",
    ALGENTA_DIR / "tabs" / "common.py",
    ALGENTA_DIR / "tabs" / "try_tab.py",
    ALGENTA_DIR / "tabs" / "play_tab.py",
    ALGENTA_DIR / "tabs" / "race_tab.py",
]


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _z_test(successes_a: int, n_a: int, successes_b: int, n_b: int) -> list[float]:
    """The pooled two-proportion z-test the kernel computes, in pure Python."""
    p1, p2 = successes_a / n_a, successes_b / n_b
    pooled = (successes_a + successes_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p1 - p2) / se
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return [z, p]


class FakeKernel:
    """What `get_kernel` returns, reduced to the surface the tabs touch; results are computed."""

    def __init__(self, contract: dict, excluded: list[str], answer: Any = None):
        self.CONTRACT = contract
        self.excluded_functions = list(excluded)
        self.calls: list[tuple[str, str, list]] = []
        self._answer = answer

    def execute(self, module: str, function: str, args: Any = None):
        args = list(args or [])
        self.calls.append((module, function, args))
        if callable(self._answer):
            return self._answer(module, function, args)
        if module == "ab_testing" and function == "z_test_proportions":
            return _z_test(*args)
        if module == "text.fuzzy" and function == "levenshtein_distance":
            import nltk

            return nltk.edit_distance(*args)
        if module == "number_theory" and function == "is_prime":
            import sympy

            return bool(sympy.isprime(args[0]))
        return self._answer


def _loaded(family: str, kernel: FakeKernel, sha: str) -> hubkernel.LoadedKernel:
    return hubkernel.LoadedKernel(
        family=f"algenta-{family}",
        repo_id=f"thyn-ai/algenta-{family}",
        kernel=kernel,
        variant="torch25-cpu-aarch64-darwin",
        capped_v1_sha=sha,
        snapshot_sha=sha,
        backend="cpu",
        version=1,
        load_s=0.2,
    )


class FakeClock:
    """A perf counter that advances by a fixed step on every read: every sample is identical."""

    def __init__(self, step_s: float = 0.001):
        self.now = 100.0
        self.step = step_s

    def __call__(self) -> float:
        self.now += self.step
        return self.now


class JitterClock(FakeClock):
    """A perf counter whose step walks a seven-long cycle of 1, 2 and 3 ms, the way a busy shared
    host jitters samples: the harness reads the clock three times per sample (budget, start, end),
    so a cycle of three would land every sample on the same step — seven is coprime to any read
    count, every sample sees another step, median 2 ms, MAD 1 ms → robust spread 74 %."""

    STEPS = (0.001, 0.003, 0.002, 0.003, 0.001, 0.002, 0.003)

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0

    def __call__(self) -> float:
        self.reads += 1
        self.now += self.STEPS[self.reads % len(self.STEPS)]
        return self.now


def stable_cell_kwargs() -> dict[str, Any]:
    return {"clock": FakeClock(), "loadavg": lambda: 0.1, "quota": 8}


@pytest.fixture(scope="module")
def stats_record() -> dict:
    return json.loads((FIXTURES / "contract_algenta_stats.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def hero_records() -> dict:
    return json.loads((FIXTURES / "hero_contracts.json").read_text("utf-8"))


@pytest.fixture
def kernels(stats_record: dict, hero_records: dict) -> dict[str, hubkernel.LoadedKernel]:
    out = {
        "stats": _loaded(
            "stats",
            FakeKernel(stats_record["contract"], stats_record["excluded_functions"]),
            stats_record["revision"],
        )
    }
    for family, record in hero_records.items():
        out[family] = _loaded(
            family,
            FakeKernel(record["contract"], record["excluded_functions"]),
            record["revision"],
        )
    return out


@pytest.fixture
def deps(kernels) -> tabs.Deps:
    return tabs.Deps(
        kernels=kernels, lane=lane.Lane(), hardware=HW, env={}, facts={"git_sha": "abc1234"}
    )


def _drain(gen):
    return list(gen)


# ---------------------------------------------------------------------------
# The contract module
# ---------------------------------------------------------------------------


def test_tabspec_validates_id_label_and_api_names():
    spec = tabs.TabSpec("try", "Try it", lambda gr: {}, ("try_run",))
    assert spec.connect is None
    with pytest.raises(ValueError):
        tabs.TabSpec("nope", "x", lambda gr: {}, ())
    with pytest.raises(ValueError):
        tabs.TabSpec("try", " ", lambda gr: {}, ())
    with pytest.raises(ValueError):
        tabs.TabSpec("try", "Try", lambda gr: {}, ("a", "a"))


def test_deps_kernel_accepts_every_spelling_and_defaults(deps):
    for spelling in ("stats", "algenta-stats", "thyn-ai/algenta-stats"):
        assert deps.kernel(spelling) is deps.kernels["stats"]
    assert deps.kernel("quantum") is None
    assert deps.feature_on("anything") is True
    assert deps.limits is None and deps.killswitch is None and deps.hero is None


def test_parity_check_ok_and_label():
    check = tabs.ParityCheck(
        "statsmodels", "statsmodels==0.15.0", {"z": 1e-12, "p": 8.6e-9}, {"z": 1e-9, "p": 1e-7}
    )
    assert check.ok
    assert check.label() == "z Δ ≤ 1e-09 · p Δ ≤ 1e-07"
    assert not tabs.ParityCheck("x", "", {"z": 1e-3}, {"z": 1e-9}).ok


# ---------------------------------------------------------------------------
# common
# ---------------------------------------------------------------------------


def test_fetch_json_and_text_refuse_plain_http_without_touching_the_network():
    for fn in (common.fetch_json, common.fetch_text):
        out = fn("http://example.invalid/x")
        assert not out.ok and out.status == 0 and "https" in out.error


def test_chip_tile_call_card_and_empty_state_are_clean_copy():
    tile = common.render_tile(
        title="Hub kernels",
        value="6,040 functions",
        caption="19 families loaded here",
        kind="measured",
        link=shell.KERNELS_HUB_URL,
    )
    _assert_clean_copy(tile)
    assert 'data-kind="measured"' in tile and "Open" in tile
    assert '<article class="alg-stat alg-stat-ok"' in tile, "the design system's stat tile"
    assert "6,040 functions" in tile and "19 families loaded here" in tile
    with pytest.raises(ValueError):
        common.render_tile(title="x", value="y", caption="z", kind="bogus")
    band = common.render_tiles(tile, "", '<div class="alg-tile">x</div>')
    assert band.startswith('<div class="alg-tiles" data-count="2">'), "empty tiles are dropped"
    card = common.render_call_card(
        title="text.fuzzy.levenshtein_distance",
        subtitle="algenta-text@fb2cab4",
        latency_ms=0.29,
        result=3,
        hardware=HW,
        ts_utc="2026-09-22 14:02 UTC",
        parity="exact match · nltk==3.9",
    )
    _assert_clean_copy(card)
    # every ms on a card is `cards.fmt_ms` — three significant figures (0.290 ms)
    assert cards.fmt_ms(0.29) in card and "0.29 ms" not in card.replace("0.290 ms", "")
    assert "parity exact match" in card and common.TRANSPORT_NOTE in card
    _assert_clean_copy(common.render_empty("No result yet", "Choose a function and press Run."))
    assert common.render_field_message("") == ""
    assert 'role="alert"' in common.render_field_message("n_a: must be an int")
    with pytest.raises(ValueError):
        common.chip("x", "purple")


def test_tabs_css_discipline():
    _assert_stylesheet_discipline(common.TABS_CSS)
    _assert_four_class_selectors(common.TABS_CSS)
    assert "#" not in common.TABS_CSS  # tokens only, no new hex


def test_permalink_hardware_id_and_visitor_key():
    link = common.permalink("play", fn="ab_testing.z_test_proportions", args={"n_a": 1000})
    assert link.startswith("?tab=play&fn=ab_testing.z_test_proportions&args=")
    assert common.permalink("race") == "?tab=race"
    hw = common.hardware_id()
    assert re.fullmatch(r"[0-9a-f]{12}", hw)
    # the machine class is the CPU quota and the architecture — what a tier fixes — and nothing
    # from the environment: a boot whose tier lookup failed and a host migration keep the same id,
    # so `qualified.json` and the board rows stay attributed (the first qualification file was
    # stamped without the tier and qualified nothing after a restart). Codna review on #1150: the
    # `env` every caller passed was discarded, so the function takes none
    assert hw == common.hardware_id()
    with pytest.raises(TypeError):
        common.hardware_id({"SPACE_HARDWARE": "cpu-upgrade"})  # type: ignore[call-arg]
    import hashlib as _hashlib
    import platform as _platform

    expected = f"{bench.cpu_quota()} vCPU|{bench.arch_name(_platform.machine())}"
    assert hw == _hashlib.sha256(expected.encode("utf-8")).hexdigest()[:12]
    assert common.visitor_key(None) == "anonymous|-"

    class Req:
        headers = {"x-forwarded-for": "203.0.113.9, 10.0.0.1"}
        client = type("C", (), {"host": "10.0.0.2"})()
        session_hash = "abc"

    assert common.visitor_key(Req()) == "203.0.113.9|abc"


def test_lane_chip_and_error_cards():
    ln = lane.Lane()
    ticket = ln.submit(lambda: 1, budget_s=1.0, label="x")
    ticket.result()
    assert "done in" in common.done_chip(ticket)
    queued = lane.Ticket("y", 1.0, 2, 3.2, 0.0)
    assert "2 ahead" in common.lane_chip(queued) and "about 3 s" in common.lane_chip(queued)
    running = lane.Ticket("y", 1.0, 0, 0.0, 0.0)
    assert "running now" in common.lane_chip(running)
    card = common.error_card("t", lane.LaneFullError("full"), HW)
    assert "lane_full" in card
    card = common.error_card(
        "t", hubkernel.HubKernelCallError("invalid_arguments", "n is outside"), HW
    )
    assert "invalid_arguments" in card and "n is outside" in card
    card = common.error_card("t", RuntimeError("boom"))
    assert "call_failed" in card and "boom" in card
    _assert_clean_copy(card)


def test_check_limit_uses_the_native_lane_only_when_the_policy_names_it(deps):
    assert common.check_limit(deps, None) is None
    deps.limits = limits.Limits(
        limits.Policy({"native": limits.LanePolicy(burst=1, window_s=60, per_day=5, daily_cap=10)})
    )
    first = common.check_limit(deps, None)
    second = common.check_limit(deps, None)
    assert first is not None and first.allowed
    assert second is not None and not second.allowed
    card = common.limited_card("t", second, HW)
    assert common.CODE_LIMITED in card and second.reason in card


# ---------------------------------------------------------------------------
# races: the candidate table against the published contracts
# ---------------------------------------------------------------------------


def test_five_compute_bound_candidates_with_s_m_l_sizes_and_hero_families():
    """Round 7 autopsy: a race is offered only where the kernel's compute dominates the call —
    one haversine pair or one primality test sits on the C ABI's per-call floor that inlined
    Python beats, and a 20,000-token bigram count or an 8,000-edge Dijkstra moves more JSON than
    it computes. Those stay Playground parity references; the roster is compute-bound."""
    assert len(races.CANDIDATES) == 5
    ids = [c.id for c in races.CANDIDATES]
    assert ids == ["levenshtein", "betweenness", "closeness", "greeks", "primes"]
    for retired in ("dijkstra", "ngrams", "miller_rabin", "haversine"):
        assert retired not in races.CANDIDATES_BY_ID
    # the retired functions keep their Playground parity references
    for qualname in (
        "geodesy.haversine_distance",
        "number_theory.is_prime",
        "graph.weighted.shortest_path_dijkstra",
        "text.tokenizer.word_ngrams",
    ):
        assert qualname in races.REFERENCES
    greeks = races.CANDIDATES_BY_ID["greeks"]
    assert [s.params["options"] for s in greeks.sizes] == [1000, 5000, 20000], "compute dominates"
    primes = races.CANDIDATES_BY_ID["primes"]
    assert [s.params["limit"] for s in primes.sizes] == [500_000, 1_000_000, 1_500_000]
    for cand in races.CANDIDATES:
        assert cand.family in playground.FAMILIES
        assert [s.key for s in cand.sizes] == ["S", "M", "L"]
        assert f"{cand.module}.{cand.function}" in races.REFERENCES
        _assert_clean_copy(cand.title + " " + " ".join(s.label for s in cand.sizes))
    with pytest.raises(races.RaceError):
        races.candidate("quantum")
    with pytest.raises(races.RaceError):
        races.CANDIDATES_BY_ID["levenshtein"].size("XL")


@pytest.mark.parametrize("race_id", [c.id for c in races.CANDIDATES])
def test_every_size_builds_arguments_the_contract_accepts(race_id: str, hero_records: dict):
    cand = races.CANDIDATES_BY_ID[race_id]
    pytest.importorskip(cand.import_name)
    record = hero_records[cand.family]
    kernel = FakeKernel(record["contract"], record["excluded_functions"])
    form = playground.form_spec(kernel, cand.module, cand.function)
    for size in cand.sizes:
        workload = cand.build(size, races.BASE_SEED)
        values = playground.parse_inputs(form, playground.named_args(form, workload.args))
        assert values == workload.args
        assert workload.note and workload.incumbent_config
        assert "seed" in workload.note or race_id == "primes"
    again = cand.build(cand.sizes[0], races.BASE_SEED)
    assert again.args == cand.build(cand.sizes[0], races.BASE_SEED).args  # seeded


def test_primes_and_closeness_builders_are_seeded_and_gated():
    primes = races.CANDIDATES_BY_ID["primes"].build(races.Size("S", "s", {"limit": 30}), 1)
    assert primes.args == [30] and "30" in primes.note
    assert primes.gate([2, 3, 5, 7, 11, 13, 17, 19, 23, 29], [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])
    assert primes.gate([2, 3], [2, 3, 5])[0] is False
    close = races.CANDIDATES_BY_ID["closeness"].build(
        races.Size("S", "s", {"nodes": 12, "edges": 30}), 3
    )
    row_ptr, targets, weights, n_nodes, weighted = close.args
    assert n_nodes == 12 and weighted is False and len(row_ptr) == 13 and row_ptr[-1] == 30
    assert len(targets) == 30 == len(weights) and all(w == 1.0 for w in weights)
    for a in range(n_nodes):
        row = targets[row_ptr[a] : row_ptr[a + 1]]
        assert row == sorted(row), "each node's targets are sorted"
    again = races.CANDIDATES_BY_ID["closeness"].build(
        races.Size("S", "s", {"nodes": 12, "edges": 30}), 3
    )
    assert again.args == close.args, "seeded"


def test_reference_gates_agree_with_themselves_and_reject_differences():
    pytest.importorskip("networkx")
    pytest.importorskip("nltk")
    lev = races.CANDIDATES_BY_ID["levenshtein"].build(races.Size("S", "s", {"chars": 40}), 3)
    theirs = lev.incumbent()
    assert lev.gate(theirs, theirs) == (True, "exact match")
    assert lev.gate(theirs + 1, theirs)[0] is False
    bet = races.CANDIDATES_BY_ID["betweenness"].build(
        races.Size("S", "s", {"nodes": 12, "edges": 30}), 3
    )
    values = bet.incumbent()
    assert bet.gate({"values": values}, values)[0] is True
    off = list(values)
    off[0] += 1e-6
    assert bet.gate({"values": off}, values)[0] is False
    close = races.CANDIDATES_BY_ID["closeness"].build(
        races.Size("S", "s", {"nodes": 12, "edges": 20}), 3
    )
    theirs = close.incumbent()
    ours = {"scaled_values": list(theirs), "defined": [v != 0.0 for v in theirs]}
    assert close.gate(ours, theirs)[0] is True
    shifted = {"scaled_values": [v + 1e-6 for v in theirs], "defined": [True] * len(theirs)}
    assert close.gate(shifted, theirs)[0] is False
    undefined_only_here = {"scaled_values": list(theirs), "defined": [False] * len(theirs)}
    assert close.gate(undefined_only_here, theirs)[0] is (all(v == 0.0 for v in theirs))


def test_offers_name_the_missing_incumbent_or_the_missing_family():
    def versions(import_name: str, dist: str) -> str | None:
        return None if import_name == "py_vollib" else "1.0"

    out = races.offers(["stats", "graph", "text"], version_of=versions)
    by_id = {o.candidate.id: o for o in out}
    assert by_id["levenshtein"].available and by_id["levenshtein"].incumbent_pin == "nltk==1.0"
    assert not by_id["greeks"].available and "py_vollib is not installed" in by_id["greeks"].reason
    assert not by_id["primes"].available
    assert "algenta-bits-time did not load" in by_id["primes"].reason
    for offer in out:
        _assert_clean_copy(offer.reason or "ok")


def test_parse_qualified_accepts_the_three_shapes_and_drops_foreign_hardware():
    q = races.parse_qualified(["levenshtein", {"race_id": "betweenness", "size": "M"}])
    assert q.is_qualified("levenshtein", "S") and q.is_qualified("betweenness", "M")
    assert not q.is_qualified("betweenness", "L") and not q.is_qualified("dijkstra", "S")
    q = races.parse_qualified(
        {"hardware_id": "aaa", "qualified": [{"duel_id": "ngrams"}]}, hardware_id="aaa"
    )
    assert q.is_qualified("ngrams", "L") and q.file_hardware_id == "aaa"
    foreign = races.parse_qualified(
        {"hardware_id": "bbb", "qualified": ["ngrams"]}, hardware_id="aaa"
    )
    assert foreign.empty
    # round 10: the file names the Space that wrote it (`requalify.py` stamps `space_id`)
    staged = races.parse_qualified(
        {"hardware_id": "aaa", "space_id": "thyn-ai/algenta-staging", "qualified": ["ngrams"]},
        hardware_id="aaa",
    )
    assert staged.file_space_id == "thyn-ai/algenta-staging" and not staged.empty
    assert q.file_space_id == "" and races.parse_qualified(["x"]).file_space_id == ""
    loaded = races.load_qualified(
        lambda url: common.Fetched(url, 200, {"space_id": "a/b", "qualified": ["levenshtein"]}),
        env={},
    )
    assert loaded.file_space_id == "a/b" and loaded.is_qualified("levenshtein", "S")
    with pytest.raises(ValueError):
        races.parse_qualified("nope")
    with pytest.raises(ValueError):
        races.parse_qualified({"qualified": 3})


def test_load_qualified_is_empty_with_the_reason_on_any_failure():
    unauthorised = races.load_qualified(
        lambda url: common.Fetched(url, 401, error="HTTP 401"), env={}
    )
    assert unauthorised.empty and unauthorised.error == "HTTP 401"
    assert unauthorised.source == races.QUALIFIED_URL_DEFAULT
    raising = races.load_qualified(
        lambda url: (_ for _ in ()).throw(OSError("down")),
        env={races.QUALIFIED_URL_ENV: "https://x/q.json"},
    )
    assert raising.empty and "OSError" in raising.error and raising.source == "https://x/q.json"
    good = races.load_qualified(lambda url: common.Fetched(url, 200, ["levenshtein"]), env={})
    assert good.is_qualified("levenshtein", "L") and not good.error
    malformed = races.load_qualified(lambda url: common.Fetched(url, 200, "text"), env={})
    assert malformed.empty and "qualified.json" in malformed.error


def _fake_candidate(gate_ok: bool = True, ours_answer: Any = 3) -> races.Candidate:
    def build(size: races.Size, seed: int) -> races.Workload:
        def gate(ours: Any, theirs: Any) -> tuple[bool, str]:
            return (
                ours == theirs
            ) if gate_ok else False, "exact match" if gate_ok else "outputs differ"

        return races.Workload(
            [size.params["n"]],
            lambda: 3,
            gate,
            f"n {size.params['n']} · seed {seed}",
            "fake.incumbent(n)",
        )

    return races.Candidate(
        "levenshtein",
        "Levenshtein distance",
        "text",
        "text.fuzzy",
        "levenshtein_distance",
        "nltk",
        "nltk",
        (
            races.Size("S", "s", {"n": 1}),
            races.Size("M", "m", {"n": 2}),
            races.Size("L", "l", {"n": 3}),
        ),
        build,
    )


class _Call:
    def __init__(self, result: Any):
        self.result = result


def test_run_race_measured_won_and_row(kernels):
    """Both lanes tick the same fake clock, so the ratio is exactly 1.0: a qualified cell is
    then held (disclosed, never a row) and the same cell unqualified is a parity row."""
    cand = _fake_candidate()
    held = races.run_race(
        cand,
        "M",
        kernels["text"],
        qualified=True,
        incumbent_pin="nltk==3.9",
        execute=lambda k, m, f, a: _Call(3),
        **stable_cell_kwargs(),
    )
    assert held.cell.measured and held.won is (held.cell.ratio > 1.0)
    assert held.title == "Levenshtein distance · m"
    assert "fake.incumbent(n)" in held.subtitle
    assert held.held and held.row_kind is None and not held.won
    with pytest.raises(ValueError, match="held"):
        races.row_from_run(
            held, hardware=HW, hardware_id="abc", space_id="", harness_commit="", wheel_sha=""
        )
    run = races.run_race(
        cand,
        "M",
        kernels["text"],
        qualified=False,
        incumbent_pin="nltk==3.9",
        execute=lambda k, m, f, a: _Call(3),
        **stable_cell_kwargs(),
    )
    assert run.cell.measured and not run.held and run.row_kind == races.ROW_KIND_PARITY
    row = races.row_from_run(
        run,
        hardware=HW,
        hardware_id="abc",
        space_id="thyn-ai/algenta",
        harness_commit="abc1234",
        wheel_sha="f" * 40,
    )
    assert tuple(row) == races.ROW_COLUMNS and row["kind"] == races.ROW_KIND_PARITY
    assert (
        row["duel_id"] == "levenshtein"
        and row["size"] == "M"
        and row["incumbent_pin"] == "nltk==3.9"
    )
    assert races.row_kind(row) == races.ROW_KIND_PARITY
    assert races.row_kind({}) == races.ROW_KIND_RACE, "a row from before the column was a win"
    assert races.row_kind({"kind": "nope"}) == races.ROW_KIND_RACE
    # a qualified cell the kernel won is a race row
    won = dataclasses_replace_won(run)
    assert won.row_kind == races.ROW_KIND_RACE and won.won and not won.held


def dataclasses_replace_won(run: races.RaceRun) -> races.RaceRun:
    """The same run as a qualified win: the incumbent lane twice as slow."""
    import dataclasses

    ours = run.cell.lane(bench.SIDE_ALGENTA)
    theirs = run.cell.lane(bench.SIDE_INCUMBENT)
    slower = dataclasses.replace(theirs, median_ms=ours.median_ms * 2)
    cell = dataclasses.replace(run.cell, lanes=[ours, slower], ratio=2.0)
    return dataclasses.replace(run, cell=cell, qualified=True)


def test_run_race_gate_failure_is_held_without_numbers(kernels):
    cand = _fake_candidate(gate_ok=False)
    run = races.run_race(
        cand,
        "S",
        kernels["text"],
        qualified=True,
        incumbent_pin="nltk==3.9",
        execute=lambda k, m, f, a: _Call(4),
        **stable_cell_kwargs(),
    )
    assert run.cell.status == bench.STATUS_GATE_FAILED and not run.cell.lanes and not run.won
    with pytest.raises(ValueError):
        races.row_from_run(
            run, hardware=HW, hardware_id="a", space_id="", harness_commit="", wheel_sha=""
        )


def test_board_ring_jsonl_and_unwritable_path(tmp_path: Path):
    path = tmp_path / "results" / "results.jsonl"
    board = races.Board(path, capacity=3)
    assert board.writable and len(board) == 0
    row = dict.fromkeys(races.ROW_COLUMNS, "")
    row.update(ts_utc="2026-09-22 14:02 UTC", duel_id="levenshtein", size="M", ratio=3.2)
    assert board.append(row) is True
    for i in range(4):
        board.append({**row, "size": "S", "ts_utc": f"t{i}"})
    assert len(board) == 3
    assert board.rows()[0]["ts_utc"] == "t3"
    assert board.last_win("levenshtein", "S")["ts_utc"] == "t3"
    assert board.last_win("levenshtein", "M") is None  # evicted from the ring
    assert board.last_win("dijkstra") is None
    lines = path.read_text().splitlines()
    assert len(lines) == 5 and json.loads(lines[0])["ratio"] == 3.2
    reloaded = races.Board(path, capacity=10)
    assert len(reloaded) == 5
    # a parity row is a measurement, never the last win; a line without `kind` was a win
    board.append({**row, "kind": races.ROW_KIND_PARITY, "size": "L", "ts_utc": "t4"})
    assert board.last_win("levenshtein", "L") is None
    assert board.last_win("levenshtein")["ts_utc"] == "t3"
    legacy = {k: v for k, v in row.items() if k != "kind"}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({**legacy, "ts_utc": "t5"}) + "\n")
    newest = races.Board(path, capacity=10).rows()[0]
    assert newest["ts_utc"] == "t5" and races.row_kind(newest) == races.ROW_KIND_RACE
    with pytest.raises(ValueError):
        board.append({"duel_id": "x"})
    blocked = races.Board(path / "nested" / "x.jsonl")
    assert not blocked.writable and blocked.append(row) is False and len(blocked) == 1


# ---------------------------------------------------------------------------
# Try it
# ---------------------------------------------------------------------------


def _fake_reference(values: list[int]):
    return _z_test(*values), "statsmodels==0.15.0"


def test_measure_hero_validates_measures_and_checks_parity(kernels):
    ln = lane.Lane()
    hero = try_tab.measure_hero(
        kernels["stats"], ln, hardware=HW, reference=_fake_reference, **stable_cell_kwargs()
    )
    assert hero.cell.measured and hero.kernel_ms is not None and hero.kernel_ms > 0
    assert (
        hero.parity is not None and hero.parity.ok and hero.parity.version == "statsmodels==0.15.0"
    )
    assert hero.args == {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000}
    assert abs(hero.z - -1.4407932) < 1e-6 and abs(hero.p - 0.1496432) < 1e-6
    assert "vs statsmodels" in hero.cell.parity_label
    with pytest.raises(playground.ValidationError) as exc:
        try_tab.measure_hero(
            kernels["stats"],
            ln,
            hardware=HW,
            args={"successes_a": "x", "n_a": 1, "successes_b": 1, "n_b": 1},
        )
    assert exc.value.field == "successes_a"
    no_ref = try_tab.measure_hero(
        kernels["stats"], ln, hardware=HW, reference=lambda v: None, **stable_cell_kwargs()
    )
    assert no_ref.parity is None and no_ref.cell.measured


def test_measure_hero_parity_failure_is_a_gate_failure_not_a_number(kernels):
    def wrong(values):
        return [0.0, 1.0], "statsmodels==0.15.0"

    hero = try_tab.measure_hero(
        kernels["stats"], lane.Lane(), hardware=HW, reference=wrong, **stable_cell_kwargs()
    )
    assert hero.cell.status == bench.STATUS_GATE_FAILED and hero.kernel_ms is None
    card = try_tab.render_hero_card(hero)
    assert (
        "not recorded" in card
        and "differs from statsmodels" in card
        and " ms" not in card.split("alg-card-foot")[0]
    )


def test_render_hero_card_shows_ms_result_parity_bound_machine_and_stamp(kernels):
    hero = try_tab.measure_hero(
        kernels["stats"],
        lane.Lane(),
        hardware=HW,
        reference=_fake_reference,
        **stable_cell_kwargs(),
    )
    card = try_tab.render_hero_card(hero, kernel_label=kernels["stats"].label())
    _assert_clean_copy(card)
    # two chips, each short enough for a 375 px card: the verdict, then the bound checked
    assert '<span class="alg-chip alg-chip-ok">parity vs statsmodels</span>' in card
    assert '<span class="alg-chip alg-chip-neutral">z Δ ≤ 1e-09 · p Δ ≤ 1e-06</span>' in card
    assert "1e-12" not in card and "1e-07" not in card, "the bound the kernel actually meets"
    assert "z -1.440793" in card and "p 0.149643" in card
    assert HW in card and hero.cell.ts_utc in card and "n = 21" in card
    # the `n` chip prints what the harness ran: the repeats, and the inner batch when it batched
    assert f">{try_tab.repeats_label(hero.cell)}<" in card
    if try_tab.calls_per_repeat(hero.cell) > 1:
        assert f"n = 21 × {try_tab.calls_per_repeat(hero.cell)} calls" in card
    single = bench.CellResult(bench.STATUS_MEASURED, n=21)
    assert try_tab.repeats_label(single) == "n = 21" and try_tab.calls_per_repeat(single) == 1
    spec = bench.LaneSpec(try_tab.HERO_LANE, bench.SIDE_ALGENTA, lambda: None)
    batched = bench.CellResult(
        bench.STATUS_MEASURED, n=21, lanes=[bench.summarise(spec, [0.1, 0.1, 0.1], k=8)]
    )
    assert try_tab.repeats_label(batched) == "n = 21 × 8 calls"
    assert "× k calls" in try_tab.HOW_MEASURED and f"{bench.SAMPLE_MIN_MS:g} ms" in (
        try_tab.HOW_MEASURED
    ), "How this is measured states the inner batch the chip prints"
    assert f'datetime="{hero.cell.ts_utc[:10]}T{hero.cell.ts_utc[11:16]}Z"' in card, (
        "the foot stamp is a <time> element"
    )
    for chip in re.findall(r'<span class="alg-chip[^"]*"[^>]*>(.*?)</span>', card):
        text = re.sub(r"<[^>]+>", "", chip)
        if text != common.TRANSPORT_NOTE:  # the shared note wraps as the design's tag variant
            assert len(text) <= 35, f"a chip that wraps on a phone: {text!r}"
    assert "algenta-stats@" in card and common.TRANSPORT_NOTE in card
    ours = hero.cell.lane(bench.SIDE_ALGENTA)
    assert f"MAD {common.cards.fmt_ms(ours.mad_ms)}" in card
    assert f"spread {common.cards.fmt_cv(ours.spread)}" in card  # the gate's statistic (v0.5)
    # round 12: no CV chip beside the verdict — `CV 19%` next to `stable · spread 1.6% ≤ 15%`
    # read as a contradiction; the CV stays a lane-table statistic
    assert f"CV {common.cards.fmt_cv(ours.cv)}" not in card and ">CV " not in card
    head = card.split('<pre class="alg-result">')[0]
    assert '<div class="alg-card-sub">50 of 1,000 vs 65 of 1,000</div>' in head
    assert "successes_a" not in head and "ab_testing" not in head, "no identifiers in primary copy"
    assert try_tab.human_args({"successes_a": 7, "n_a": 90, "successes_b": 9, "n_b": 80}) == (
        "7 of 90 vs 9 of 80"
    )


def test_not_recorded_hero_card_says_the_cause_in_words(kernels):
    hero = try_tab.measure_hero(
        kernels["stats"],
        lane.Lane(),
        hardware=HW,
        reference=_fake_reference,
        clock=JitterClock(),
        loadavg=lambda: 0.1,
        quota=8,
    )
    assert hero.cell.status == bench.STATUS_NOISY
    card = try_tab.render_hero_card(hero, kernel_label=kernels["stats"].label())
    _assert_clean_copy(card)
    assert "spread above 15 percent" in card and "not recorded" in card
    assert f" on {try_tab.HERO_LANE}" not in card, "the lane's internal name stays out of the cause"
    reason_line = re.search(r'alg-card-reason">([^<]*)<', card)
    assert reason_line is not None and try_tab.HERO_LANE not in reason_line.group(1)
    # round 11: the cause names the gate and the lane, as the race cards do (`bench.noisy_reason`),
    # and leaves `not recorded` to the chip beside it — said once, never twice
    assert reason_line.group(1) == "spread above 15 percent on the kernel lane"
    assert try_tab.HERO_LANE_WORDS == "the kernel lane"
    assert re.sub(r"<[^>]+>", " ", card).count("not recorded") == 1, "the chip alone says it"
    assert "noisy" not in reason_line.group(1)
    assert try_tab.noisy_cause(hero.cell) == "spread above 15 percent on the kernel lane"
    ours = hero.cell.lane(bench.SIDE_ALGENTA)
    assert ours is not None and bench.noisy_reason([ours]) == (
        "noisy — not recorded — spread above 15 percent on algenta-stats"
    )
    # the boot row and the loading note keep the verdict words (`noisy — not recorded`)
    assert try_tab.human_reason("spread above 15 percent on algenta-stats") == (
        "spread above 15 percent"
    )
    # a cell stopped for another reason keeps its own words
    other = dataclasses.replace(hero.cell, status=bench.STATUS_ERROR, reason="call_failed: boom")
    assert try_tab.noisy_cause(other) == "call_failed: boom"
    assert "MAD" in try_tab.HOW_MEASURED and "spread" in try_tab.HOW_MEASURED
    # The run ran: the kernel's answer and the parity check stay on the card; only the timing
    # rows are withheld. A documented state — the quiet card the verifier reads.
    assert 'data-state="not_recorded"' in card and "alg-card-quiet" in card
    assert "alg-card-result" not in card and "alg-card-timing" in card
    assert "z -1.440793" in card and "p 0.149643" in card, "the result the visitor asked for"
    assert '<span class="alg-chip alg-chip-ok">parity vs statsmodels</span>' in card
    assert '<span class="alg-chip alg-chip-neutral">z Δ ≤ 1e-09 · p Δ ≤ 1e-06</span>' in card
    assert "statsmodels==0.15.0" in card and "algenta-stats@" in card
    assert '<div class="alg-card-sub">50 of 1,000 vs 65 of 1,000</div>' in card
    assert "alg-hero-num" not in card, "no figure where none was recorded"
    for timing in ("P95", "MAD", "stable · spread", "spread ", "n = ", "measured 20"):
        assert timing not in card.replace("spread above", "cause-above"), (
            f"a timing row on a not-recorded card: {timing}"
        )
    assert card.count("spread") == 1, "the word appears once: in the cause, never as a statistic"
    assert card.count('data-kind="unavailable"') == 1, "one neutral not-recorded chip"
    assert "alg-chip-err" not in card and "alg-chip-warn" not in card, "quiet, not red or amber"
    # the answer, then the parity chips, then the one quiet timing row with the cause
    assert card.index("<pre") < card.index("parity vs statsmodels") < card.index("alg-card-timing")
    assert card.index("alg-card-timing") < card.index("alg-card-reason")
    assert card.count("parity vs statsmodels") == 1, "the gate's label is said once"
    for chip in re.findall(r'<span class="alg-chip[^"]*"[^>]*>(.*?)</span>', card):
        text = re.sub(r"<[^>]+>", "", chip)
        if text != common.TRANSPORT_NOTE:
            assert len(text) <= 35, f"a chip that wraps on a phone: {text!r}"
    # a parity miss is a gate failure: the answer stays, the verdict chip is red, nothing timed
    failed = try_tab.measure_hero(
        kernels["stats"],
        lane.Lane(),
        hardware=HW,
        reference=lambda values: ([0.0, 0.5], "statsmodels==0.15.0"),
        **stable_cell_kwargs(),
    )
    assert failed.cell.status == bench.STATUS_GATE_FAILED
    failed_card = try_tab.render_hero_card(failed)
    assert "parity differs from statsmodels" in failed_card and "z -1.440793" in failed_card
    assert "alg-chip-err" in failed_card and 'data-state="not_recorded"' in failed_card
    # no answer at all (the kernel raised before the gate): the shared card, no result block
    broken = try_tab.measure_hero(
        kernels["stats"],
        lane.Lane(),
        hardware=HW,
        reference=_fake_reference,
        execute=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        **stable_cell_kwargs(),
    )
    assert broken.cell.status == bench.STATUS_ERROR and not try_tab.has_result(broken)
    broken_card = try_tab.render_hero_card(broken)
    assert "alg-result" not in broken_card and "not recorded" in broken_card
    with pytest.raises(ValueError):
        try_tab.render_unrecorded_hero_card(
            try_tab.measure_hero(
                kernels["stats"],
                lane.Lane(),
                hardware=HW,
                reference=_fake_reference,
                **stable_cell_kwargs(),
            )
        )


def _stable_start(monkeypatch):
    import functools

    stable = functools.partial(
        try_tab.start_hero, reference=_fake_reference, **stable_cell_kwargs()
    )
    monkeypatch.setattr(try_tab, "start_hero", stable)


def test_run_hero_flows(deps, monkeypatch):
    _stable_start(monkeypatch)
    bad = _drain(try_tab.run_hero(deps, try_tab.raw_args(50, 1000, "x", 1000)))
    assert bad == [("", None, "Successes B must be a whole number.")]
    tracker = try_tab.HeroTracker()
    ok = _drain(try_tab.run_hero(deps, try_tab.raw_args(50, 1000, 65, 1000), tracker=tracker))
    assert len(ok) == 2, "the lane chip first, then the card"
    assert ok[0][1] is None and ok[0][2] == "" and ("running" in ok[0][0] or "queued" in ok[0][0])
    assert "done in" in ok[1][0] and "alg-card-result" in ok[1][1] and ok[1][2] == ""
    assert tracker.measured is not None, "a measured run of the card example fills the opening card"
    other = _drain(try_tab.run_hero(deps, try_tab.raw_args(7, 90, 9, 80), tracker=tracker))
    assert "alg-card-result" in other[-1][1] and tracker.measured.args == dict(try_tab.HERO_ARGS)

    class Off:
        def enabled(self, feature: str) -> bool:
            return False

    deps.killswitch = Off()
    off = _drain(try_tab.run_hero(deps, try_tab.raw_args(50, 1000, 65, 1000)))
    assert common.CODE_SWITCHED_OFF in off[0][1]
    deps.killswitch = None
    deps.limits = limits.Limits(
        limits.Policy({"native": limits.LanePolicy(burst=1, window_s=60, per_day=1, daily_cap=1)})
    )
    _drain(try_tab.run_hero(deps, try_tab.raw_args(50, 1000, 65, 1000)))
    limited = _drain(try_tab.run_hero(deps, try_tab.raw_args(50, 1000, 65, 1000)))
    assert common.CODE_LIMITED in limited[0][1]
    empty = tabs.Deps(
        kernels={},
        lane=lane.Lane(),
        hardware=HW,
        env={},
        kernel_errors={"algenta-stats": hubkernel.HubKernelUnavailable("cache_missing", "offline")},
    )
    missing = _drain(try_tab.run_hero(empty, try_tab.raw_args(50, 1000, 65, 1000)))
    assert "cache_missing" in missing[0][1] and "offline" in missing[0][1]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ((2000, 1000, 65, 1000), "Successes A cannot exceed Trials A."),
        ((-5, 1000, 65, 1000), "Successes A cannot be negative."),
        ((50, 0, 65, 1000), "Trials A must be at least 1."),
        ((50, 1000, 1001, 1000), "Successes B cannot exceed Trials B."),
        ((50, 1000, 65, -1), "Trials B must be at least 1."),
        ((None, 1000, 65, 1000), "Successes A is required."),
        ((1.5, 1000, 65, 1000), "Successes A must be a whole number."),
        ((2.5, 1000, 65, 1000), "Successes A must be a whole number."),
        (
            (50, 1 << 63, 65, 1000),
            "Trials A is too large; use Reproduce.",
        ),
        (
            (50, (1 << 53) + 1, 65, 1000),
            "Trials A is too large; use Reproduce.",
        ),
        (
            (50, float(1 << 53), 65, 1000),
            "Trials A is too large; use Reproduce.",
        ),
        ((50, "9223372036854775808", 65, 1000), "Trials A is outside the 64-bit range."),
    ],
)
def test_run_hero_refuses_impossible_proportions_before_any_kernel_call(deps, raw, message):
    kernel = deps.kernels["stats"].kernel
    before = len(kernel.calls)
    outcomes = _drain(try_tab.run_hero(deps, try_tab.raw_args(*raw)))
    assert outcomes == [("", None, message)]
    assert len(kernel.calls) == before, "nothing native runs on refused input"
    assert "_" not in message and "!" not in message
    assert message.count(".") == 1 and message.endswith("."), "one sentence"
    named, text = try_tab.check_args(deps.kernels["stats"], try_tab.raw_args(*raw))
    assert named is None and text == message
    with pytest.raises(playground.ValidationError):
        try_tab.measure_hero(
            deps.kernels["stats"], deps.lane, hardware=HW, args=try_tab.raw_args(*raw)
        )


def test_install_snippet_is_exactly_three_lines_trusting_one_repository(kernels):
    text = try_tab.install_snippet(try_tab.HERO_ARGS)
    lines = text.strip("\n").split("\n")
    assert len(lines) == 3, lines
    assert lines[0] == "# pip install kernels torch"
    assert lines[1].startswith("from kernels import get_kernel; k = get_kernel(")
    assert (
        'get_kernel("thyn-ai/algenta-stats", version=1, backend="cpu", '
        'trust_remote_code=["thyn-ai/algenta-stats"])' in lines[1]
    )
    assert lines[2] == (
        "k.ab_testing.z_test_proportions(successes_a=50, n_a=1000, successes_b=65, n_b=1000)"
    )
    assert text.count("thyn-ai/") == 2, "no twenty-repository list in the short form"
    compile(text, "<install>", "exec")
    full = try_tab.reproduce_snippet(try_tab.HERO_ARGS)
    assert full.count("thyn-ai/") == len(playground.TRUST) + 1 and "TRUST = [" in full
    compile(full, "<reproduce>", "exec")
    assert try_tab.snippet_for(kernels["stats"], try_tab.raw_args(7, 90, 9, 80), "kernels") == (
        try_tab.install_snippet({"successes_a": 7, "n_a": 90, "successes_b": 9, "n_b": 80})
    )


def _noisy_then_measured(kernels, flips: int):
    """A measurement that says noisy for the first `flips` calls, measured afterwards."""
    calls = {"n": 0}

    def measure():
        calls["n"] += 1
        jitter = calls["n"] <= flips  # v0.6: noise is spread, never the load average
        return try_tab.measure_hero(
            kernels["stats"],
            lane.Lane(),
            hardware=HW,
            reference=_fake_reference,
            clock=JitterClock() if jitter else FakeClock(),
            loadavg=lambda: 0.1,
            quota=8,
        )

    return measure, calls


def test_hero_tracker_keeps_the_latest_measured_attempt_and_retries_in_the_background(kernels):
    measure, calls = _noisy_then_measured(kernels, flips=2)
    tracker = try_tab.HeroTracker(measure)
    assert tracker.pending and tracker.hero is None and tracker.snapshot()["attempts"] == 0
    first = tracker.attempt()
    assert first.cell.status == bench.STATUS_NOISY and tracker.measured is None
    assert tracker.pending and tracker.hero is first
    assert tracker.measuring is False and tracker.last_attempt_at is not None
    note = try_tab.pending_note(tracker)
    assert note == "Not measured on this host yet · attempt 1 · spread above 15 percent", note
    assert tracker.next_attempt_at() is None, "no thread, no next attempt to promise"
    assert tracker.start(0.01) is True
    at = tracker.next_attempt_at()
    assert at is not None and abs(at - (tracker.started_at + 0.01)) < 1e-6
    assert tracker.snapshot()["next_attempt_utc"] == try_tab.clock_utc(at)
    deadline = 200
    while tracker.measured is None and deadline:
        import time

        time.sleep(0.01)
        deadline -= 1
    assert tracker.measured is not None and tracker.measured.cell.measured
    assert not tracker.pending and tracker.hero is tracker.measured
    assert calls["n"] == 3, "two noisy attempts, one measured"
    tracker.stop(wait=True)
    assert tracker.start(0.01) is False, "nothing left to do once measured"
    snapshot = tracker.snapshot()
    assert (
        snapshot["measured"] is True and snapshot["attempts"] == 3 and snapshot["retry_s"] is None
    )
    later = tracker.latest
    tracker.record(first)
    assert tracker.latest is first and tracker.measured is later, "a noisy record never replaces"
    assert tracker.recorded == 1 and tracker.snapshot()["recorded"] == 1
    # the boot row: boot ended with `later`; a visitor's measured run of the card example
    # replaces the hero and the row says so — the launch review saw a visitor's figure under
    # boot's own timing with no qualifier and attempts still 1
    boot_sequence = importlib.import_module("boot_sequence")
    boot_hero = tracker.hero
    unqualified = boot_sequence.hero_detail(
        tracker, boot_attempts=tracker.attempts, boot_hero=boot_hero
    )
    assert boot_sequence.MEASURED_AFTER_BOOT not in unqualified, "boot's own figure, no qualifier"
    visitor = measure()
    assert visitor.cell.measured and visitor is not later
    tracker.record(visitor)
    assert tracker.hero is visitor and tracker.recorded == 2 and tracker.attempts == 3
    qualified = boot_sequence.hero_detail(
        tracker, boot_attempts=tracker.attempts, boot_hero=boot_hero
    )
    # the qualifier carries the measurement's own clock, so it is never read as the foot's
    # boot time (round 12): `measured after boot · 10:12 UTC`
    clause = boot_sequence.after_boot_clause(visitor.cell.ts_utc)
    assert clause == f"{boot_sequence.MEASURED_AFTER_BOOT} · {visitor.cell.ts_utc[11:16]} UTC"
    assert qualified.endswith(f"attempt 3 · {clause}"), qualified
    assert boot_sequence.after_boot_clause("not a stamp") == boot_sequence.MEASURED_AFTER_BOOT
    assert boot_sequence.bench_ms(visitor.kernel_ms) in qualified, "the visitor's figure"
    with pytest.raises(RuntimeError):
        try_tab.HeroTracker().attempt()


def test_hero_tracker_records_the_count_and_the_hero_under_one_lock(kernels):
    """Codna review on #1150: `record()` bumped `recorded` under one lock and swapped the hero
    under a second — `/health` between the two read a visitor counted with boot's hero still
    up. A probe lock sees one acquisition, released with the count and the hero both in
    place."""
    measure, _ = _noisy_then_measured(kernels, flips=0)
    tracker = try_tab.HeroTracker(measure)
    boot_hero = tracker.attempt()
    assert boot_hero.cell.measured and tracker.hero is boot_hero
    releases: list[tuple[int, Any]] = []

    class ProbeLock:
        def __init__(self, inner: Any) -> None:
            self.inner = inner

        def __enter__(self) -> Any:
            return self.inner.__enter__()

        def __exit__(self, *exc: Any) -> Any:
            releases.append((tracker.recorded, tracker.hero))
            return self.inner.__exit__(*exc)

    tracker._lock = ProbeLock(tracker._lock)
    visitor = measure()
    assert visitor.cell.measured and visitor is not boot_hero
    tracker.record(visitor)
    assert releases == [(1, visitor)], "one lock, released with the count and the hero together"
    assert tracker.snapshot()["recorded"] == 1 and tracker.hero is visitor


def test_opening_card_is_never_the_warn_card_while_a_verdict_can_still_change(deps, kernels):
    measure, _ = _noisy_then_measured(kernels, flips=1)
    tracker = try_tab.HeroTracker(measure)
    empty = try_tab.opening_card(deps, tracker)
    _assert_clean_copy(empty)
    assert 'data-state="pending"' in empty and "Not measured on this host yet" in empty
    assert "not recorded" not in empty and " ms" not in empty
    assert "aria-busy" not in empty and 'data-kind="loading"' not in empty, "nothing pulses"
    assert 'data-kind="unavailable">not measured yet<' in empty
    tracker.attempt()
    noisy = try_tab.opening_card(deps, tracker)
    assert 'data-state="pending"' in noisy and "attempt 1" in noisy
    assert "spread above 15 percent" in noisy, "the cause, not the verdict"
    assert "noisy" not in noisy and "not recorded" not in noisy and "alg-card-warn" not in noisy
    assert try_tab.card_pending(noisy) and not try_tab.card_pending("<article>")
    # the clock of the next attempt, as a <time> element, once the thread is retrying
    tracker.start(60.0)
    retrying = try_tab.opening_card(deps, tracker)
    at = tracker.next_attempt_at()
    assert at is not None and f"next attempt at {try_tab.clock_utc(at)}" in try_tab.pending_note(
        tracker
    )
    assert f'<time class="alg-time" datetime="{try_tab.clock_iso(at)}">' in retrying
    tracker.stop(wait=True)
    # while an attempt runs, and only then, the card is the pulsing skeleton
    tracker.measuring = True
    measuring = try_tab.opening_card(deps, tracker)
    assert 'data-state="loading"' in measuring and 'aria-busy="true"' in measuring
    assert "Measuring on this machine · attempt 1" in measuring
    assert "next attempt at" not in measuring and 'data-kind="loading"' in measuring
    tracker.measuring = False
    tracker.attempt()
    measured = try_tab.opening_card(deps, tracker)
    assert "alg-card-result" in measured and "alg-skeleton" not in measured

    def wrong(values):
        return [0.0, 1.0], "statsmodels==0.15.0"

    final = try_tab.HeroTracker(
        lambda: try_tab.measure_hero(
            kernels["stats"], deps.lane, hardware=HW, reference=wrong, **stable_cell_kwargs()
        )
    )
    final.attempt()
    assert not final.pending, "a gate failure is a final verdict"
    card = try_tab.opening_card(deps, final)
    assert "differs from statsmodels" in card and "not recorded" in card
    assert try_tab.hero_tracker_of(deps).hero is None
    deps.hero = tracker.measured
    assert try_tab.hero_tracker_of(deps).measured is tracker.measured


def test_loading_card_matches_the_measured_cards_geometry():
    card = common.render_loading_card(
        title="T",
        subtitle="s",
        hero_label="per kernel call · median",
        note="Measuring",
        hardware=HW,
        ts_utc="2026-09-22 14:02 UTC",
    )
    _assert_clean_copy(card)
    assert card.count("alg-skeleton-chip") == len(common.SKELETON_CHIP_WIDTHS) - 1
    assert 'data-kind="loading"' in card, "the design system's loading chip leads the row"
    assert card.count("alg-skeleton alg-skeleton-line") == 2 and 'aria-busy="true"' in card
    assert 'datetime="2026-09-22T14:02Z"' in card, "the foot stamp is a <time> element"
    settled = common.render_loading_card(
        title="T",
        subtitle="s",
        hero_label="l",
        note="Not measured on this host yet · next attempt at 14:03:07 UTC",
        note_html="Not measured on this host yet · next attempt at <time>14:03:07 UTC</time>",
        hardware=HW,
        ts_utc="now",
        settled=True,
    )
    _assert_clean_copy(settled)
    assert 'data-state="pending"' in settled and "aria-busy" not in settled
    assert 'data-kind="unavailable">not measured yet<' in settled
    assert 'data-kind="loading"' not in settled and "<time>14:03:07 UTC</time>" in settled
    assert settled.count("alg-skeleton") == card.count("alg-skeleton"), "the same geometry"
    assert "· now</div>" in settled, "a stamp that is not one prints as it came"
    css = common.TABS_CSS
    assert '[data-state="pending"] .alg-skeleton { animation: none; }' in css
    for part in (
        "alg-card-head",
        "alg-hero-num",
        "alg-hero-label",
        "alg-result",
        "alg-chips",
        "alg-card-foot",
    ):
        assert part in card, part
    with pytest.raises(ValueError):
        common.render_loading_card(
            title="T", subtitle="s", hero_label="l", note="  ", hardware=HW, ts_utc="now"
        )


def test_status_row_and_quiet_unavailable_tile():
    empty = common.render_status()
    assert 'aria-live="polite"' in empty and "alg-field-msg" not in empty
    assert empty.endswith('aria-live="polite"></div>'), "an empty row is an empty live region"
    row = common.render_status(common.chip("running"), "Trials A must be at least 1.")
    assert "running" in row and 'role="alert"' in row
    # The refusal's echo beside the action: the same sentence as a status, never a second alert.
    echoed = common.render_status(echo="n_a must be a whole number.")
    assert '<p class="alg-status-echo" role="status">n_a must be a whole number.</p>' in echoed
    assert 'role="alert"' not in echoed and common.render_status_echo("  ") == ""
    assert common.render_status().count("<p") == 0
    # The code caption in place of Gradio's block label; refuses to name nothing.
    assert (
        common.render_code_caption("MCP request") == '<p class="alg-code-caption">MCP request</p>'
    )
    with pytest.raises(ValueError):
        common.render_code_caption(" ")
    css = common.TABS_CSS
    rules = {line.split(" {")[0]: line for line in css.splitlines() if line.startswith(".alg-")}
    assert "color: var(--alg-err)" in rules[".alg-status-echo" * 4]
    assert "text-transform: uppercase" in rules[".alg-code-caption" * 4]
    assert f"margin: 0 0 -{common.CODE_CAPTION_PULL_PX}px" in rules[".alg-code-caption-row" * 4], (
        "the editor pulled up under its caption"
    )
    assert ".alg-status:not(:empty) { min-height: 32px; }" in css
    assert ":has(> div > div > .alg-status:empty) { margin-top: -16px; }" in css, (
        "an empty row pulls back the column gap around it"
    )
    assert "min-height: 32px" not in css.split(".alg-status:not(:empty)")[0].rsplit("\n", 1)[-1]

    class Ticket:
        def duration_s(self):
            return 0.00607

    done = common.done_chip(Ticket(), ts_utc="2026-09-22 14:02 UTC")
    _assert_clean_copy(done)
    assert 'data-kind="measured">done in 6.07 ms</span>' in done
    assert (
        '<span class="alg-status-meta">this container · '
        '<time class="alg-time" datetime="2026-09-22T14:02Z">2026-09-22 14:02 UTC</time></span>'
    ) in done, "unit, provenance and UTC — never the number alone"
    assert common.WHERE_RUN == "this container"
    tile = common.render_tile(
        title="GPU stage",
        value="offline",
        caption="GPU stage offline",
        kind="unavailable",
        code="gpu_status_unreachable",
    )
    _assert_clean_copy(tile)
    assert "alg-stat-unavailable" in tile and "alg-card-err" not in tile
    assert 'data-kind="unavailable">unavailable · gpu_status_unreachable<' in tile
    assert ">—<" in tile and ">offline<" not in tile, "no figure stands in for a missing one"
    with pytest.raises(ValueError):
        common.render_tile(title="x", value="y", caption="z", kind="unavailable")
    assert common.permalink("try", fn="a.b", args={"n": 1}, base="https://x.hf.space/") == (
        "https://x.hf.space/?tab=try&fn=a.b&args=%7B%22n%22%3A1%7D"
    )
    payload = common.permalink_payload("a.b", {"n": 1})
    assert common.permalink_request(payload) == ("a.b", {"n": 1})
    assert common.permalink_request("") == (None, None) and common.permalink_request("[1]") == (
        None,
        None,
    )
    assert common.permalink_request(common.permalink_payload(None, None)) == (None, None)


def test_try_permalink_restore_reads_whole_numbers_only():
    payload = common.permalink_payload(
        try_tab.HERO_QUALNAME,
        {"successes_a": 7, "n_a": 90.0, "successes_b": True, "n_b": "x", "extra": 1},
    )
    assert try_tab.restore_values(payload) == {"successes_a": 7, "n_a": 90}
    assert try_tab.restore_values(common.permalink_payload(None, {"n_a": 5})) == {"n_a": 5}
    assert try_tab.restore_values(common.permalink_payload("other.fn", {"n_a": 5})) == {}
    assert try_tab.restore_values("") == {} and try_tab.restore_values(None) == {}
    huge = common.permalink_payload(None, {"successes_a": (1 << 53) + 1, "n_a": (1 << 53) - 1})
    assert try_tab.restore_values(huge) == {"n_a": (1 << 53) - 1}, "a number box shows 2^53 wrong"
    # the shell's report hook: exactly what landed in the boxes, never more
    fn = try_tab.HERO_QUALNAME
    assert try_tab.permalink_applied(fn, {"successes_a": 12, "n_a": 345}) == (
        fn,
        {"successes_a": 12, "n_a": 345},
    )
    assert try_tab.permalink_applied(None, {"successes_a": 12.5, "n_a": 345}) == (
        None,
        {"n_a": 345},
    ), "the decimal is not promised; the whole number is"
    assert try_tab.permalink_applied(None, {"successes_a": 12.5}) is None
    assert try_tab.permalink_applied(fn, None) == (fn, None), "the hero function alone"
    assert try_tab.permalink_applied(fn, {"successes_a": 12.5}) == (fn, None)
    assert try_tab.permalink_applied("text.fuzzy.levenshtein_distance", {"n_a": 5}) is None
    assert try_tab.permalink_applied(None, None) is None
    box = object()
    assert (
        try_tab.permalink_outputs({"restore": box}) == [box] and try_tab.permalink_outputs({}) == []
    )
    assert json.loads(try_tab.permalink_restore("a.b", {"n": 1})[0]) == {
        "fn": "a.b",
        "args": {"n": 1},
    }


def test_snippets_carry_the_visitors_numbers(kernels):
    text = try_tab.snippet_for(
        kernels["stats"], try_tab.raw_args(7, 90, 9, 80), playground.MODE_KERNELS
    )
    assert "successes_a=7" in text and "n_b=80" in text and "thyn-ai/algenta-stats" in text
    compile(text, "<kernels>", "exec")
    frame = json.loads(
        try_tab.snippet_for(kernels["stats"], try_tab.raw_args(7, 90, 9, 80), playground.MODE_MCP)
    )
    assert frame["params"]["arguments"]["args"] == {
        "successes_a": 7,
        "n_a": 90,
        "successes_b": 9,
        "n_b": 80,
    }
    fallback = try_tab.snippet_for(
        kernels["stats"], try_tab.raw_args("x", 1, 1, 1), playground.MODE_KERNELS
    )
    assert "successes_a=50" in fallback


def test_kernel_counts_and_hub_tile(deps):
    families, functions, variants = try_tab.kernel_counts(deps)
    assert families == len(deps.kernels) and functions > 0
    assert variants == "torch25-cpu-aarch64-darwin"
    tile = try_tab.hub_tile(deps)
    _assert_clean_copy(tile)
    assert f"{functions:,} functions" in tile
    assert f"{families} families loaded here · counted at boot</span><time" in tile, (
        (
            "the fixtures load fewer than the published count, but the fixture record carries no "
            "families_published, so the tile says what it counted"
        )
        if False
        else tile
    )
    assert " UTC" in tile, "a counted figure carries the UTC it was counted at"
    assert variants not in tile, "build variants belong in the Reproduce disclosure"
    note = try_tab.build_note(deps)
    assert variants in note and "algenta-stats@" in note
    assert f"rulebook v{bench.RULEBOOK_VERSION}" in note
    assert try_tab.HERO_QUALNAME in note, "the dotted name lives in the disclosure"
    empty = try_tab.hub_tile(tabs.Deps(kernels={}, lane=deps.lane, hardware=HW, env={}))
    assert 'data-kind="unavailable"' in empty and "no family loaded" in empty
    assert "alg-stat-unavailable" in empty and common.CODE_NO_KERNEL in empty


def test_hub_tile_reads_the_boot_facts_as_the_one_truth(deps):
    """The tile, the headline and the boot card quote `functions_loaded` / `families_loaded`
    from the facts record when boot wrote one; the umbrella is never counted."""
    deps.facts = {
        "functions_loaded": 5683,
        "families_loaded": ["a"] * 18,
        "families_published": 19,
        "generated_utc": "2026-09-22 14:02 UTC",
    }
    assert try_tab.loaded_counts(deps) == (18, 19, 5683)
    tile = try_tab.hub_tile(deps)
    assert "5,683 functions" in tile and "18 of 19 families loaded here" in tile
    assert "counted at boot</span>" in tile and 'datetime="2026-09-22T14:02Z"' in tile
    assert "6,040" not in tile, "the catalogue count is not this container's"
    deps.facts = {**deps.facts, "functions_loaded": 6040, "families_loaded": ["a"] * 19}
    whole = try_tab.hub_tile(deps)
    assert "6,040 functions" in whole and "19 families loaded here" in whole
    assert "of 19" not in whole, "nothing is missing, so nothing says so"
    deps.facts = {}
    families, _published, functions = try_tab.loaded_counts(deps)
    assert (families, functions) == try_tab.kernel_counts(deps)[:2], "counted when no facts"
    assert try_tab.boot_stamp(deps).endswith(" UTC")


def test_mcp_tool_count_from_the_live_endpoint_or_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "algenta_mcp", None)
    monkeypatch.setitem(sys.modules, "algenta_mcp.registry", None)
    count, caption, kind = try_tab.mcp_tool_count(
        lambda url: common.Fetched(url, 200, {"tools": [{"name": "a"}, {"name": "b"}]})
    )
    assert (count, kind) == (2, "live") and caption.startswith(f"{try_tab.LIVE_HOSTED} · ")
    assert caption.endswith(" UTC") and common.cards.hostname_token(caption) is None
    # round 9: after one successful read the container keeps the count; a failed fetch reports
    # that count with its time and the code — never "not installed", never a bare dash
    count, caption, kind = try_tab.mcp_tool_count(
        lambda url: common.Fetched(url, 0, error="URLError: down")
    )
    assert (count, kind) == (2, "measured")  # it was measured, at the time the caption names
    assert caption.startswith(f"{try_tab.LAST_READ} ") and "mcp_tools_unreachable now" in caption
    stale = try_tab.hosted_tile(lambda url: common.Fetched(url, 0, error="URLError: down"))
    assert "2 MCP tools" in stale and "mcp_tools_unreachable" in stale
    # with no read behind it, a failure is the unavailable tile with the code once
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [])
    count, caption, kind = try_tab.mcp_tool_count(
        lambda url: common.Fetched(url, 0, error="URLError: down")
    )
    assert count is None and kind == "unavailable" and "mcp_tools_unreachable" in caption
    tile = try_tab.hosted_tile(lambda url: common.Fetched(url, 200, {"tools": [1, 2, 3]}))
    _assert_clean_copy(tile)
    assert "3 MCP tools" in tile
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [])
    down = try_tab.hosted_tile(lambda url: common.Fetched(url, 0, error="URLError: down"))
    assert "alg-stat-unavailable" in down and "mcp_tools_unreachable" in down
    # round 10: the reason is one code word, never the exception class and its text
    assert try_tab.REASON_UNREACHABLE in down and "URLError" not in down
    import re

    assert re.sub(r"<[^>]+>", " ", down).count("mcp_tools_unreachable") == 1, "the code once"


def test_hosted_read_reasons_are_code_words_the_try_tile_and_the_sdk_card_share(monkeypatch):
    """Round 10: the Ecosystem SDK card's unreachable state leaked `URLError: <urlopen error …>`
    from the Try tile's caption. The reason is coded at the source (`try_tab.reason_code`):
    `timeout`, `connection_refused`, `http_<status>` or `unreachable` — the same word on both
    tabs, the exception's text in the log alone."""
    import functools
    import re

    from tabs import eco_tab  # noqa: PLC0415

    fetched = common.Fetched
    refused = "URLError: <urlopen error [Errno 61] Connection refused>"
    assert try_tab.reason_code(fetched("u", 0, error="URLError: <urlopen error timed out>")) == (
        try_tab.REASON_TIMEOUT
    )
    assert try_tab.reason_code(fetched("u", 0, error="TimeoutError: timed out")) == "timeout"
    assert try_tab.reason_code(fetched("u", 0, error=refused)) == "connection_refused"
    assert try_tab.reason_code(fetched("u", 503, error="HTTP 503")) == "http_503"
    assert try_tab.reason_code(fetched("u", 401, error="HTTP 401")) == "http_401"
    assert try_tab.reason_code(fetched("u", 0, error="URLError: <urlopen error [Errno 8]>")) == (
        try_tab.REASON_UNREACHABLE
    )
    assert try_tab.reason_code(fetched("u", 200, {"no": "tools"})) == "unreachable"
    assert (
        try_tab.reason_code(fetched("u", 0, error="only https sources are read")) == "unreachable"
    )
    monkeypatch.setitem(sys.modules, "algenta_mcp", None)
    monkeypatch.setitem(sys.modules, "algenta_mcp.registry", None)
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [])
    count, caption, kind = try_tab.mcp_tool_count(lambda url: fetched(url, 0, error=refused))
    assert (count, kind) == (None, "unavailable")
    assert caption == f"unavailable · {try_tab.CODE_MCP_UNREACHABLE} · connection_refused"
    tile = try_tab.hosted_tile(lambda url: fetched(url, 0, error=refused))
    assert "connection_refused" in tile and "URLError" not in tile and "Errno" not in tile
    assert "urlopen" not in tile
    # the SDK card reads the same source, so the two tabs agree word for word
    down = functools.partial(
        try_tab.mcp_tool_count, lambda url: fetched(url, 503, error="HTTP 503")
    )
    monkeypatch.setattr(try_tab, "mcp_tool_count", down)
    tools, card_caption, card_kind = eco_tab.mcp_tool_count_with_caption()
    assert (tools, card_kind) == (None, "unavailable") and card_caption.endswith("· http_503")
    card = eco_tab.render_sdk_card({"versions": {}})
    assert "HTTP 503" not in card and eco_tab.MCP_NOT_INSTALLED_TEXT in card
    assert f"unavailable · {try_tab.CODE_MCP_UNREACHABLE}" in card
    # with an earlier live read the card keeps the count; the reason stays one word
    monkeypatch.setattr(try_tab, "_LAST_LIVE", [140, "2026-09-24 03:13 UTC"])
    tools, card_caption, card_kind = eco_tab.mcp_tool_count_with_caption()
    assert (tools, card_kind) == (140, "measured")
    assert card_caption == (
        f"{try_tab.LAST_READ} 2026-09-24 03:13 UTC · {try_tab.CODE_MCP_UNREACHABLE} now · http_503"
    )
    stale = eco_tab.render_sdk_card({"versions": {}})
    assert ">140<" in stale and "http_503" in stale and "HTTP 503" not in stale
    for text in (caption, card_caption):
        assert re.search(r"[A-Z][a-zA-Z]+Error", text) is None, text


def test_mcp_tool_count_prefers_the_installed_registry(monkeypatch):
    import types

    registry = types.ModuleType("algenta_mcp.registry")
    registry.TOOLS = [object()] * 140
    package = types.ModuleType("algenta_mcp")
    package.registry = registry
    monkeypatch.setitem(sys.modules, "algenta_mcp", package)
    monkeypatch.setitem(sys.modules, "algenta_mcp.registry", registry)
    count, caption, kind = try_tab.mcp_tool_count(lambda url: pytest.fail("must not fetch"))
    assert (count, kind) == (140, "measured") and "registry" in caption
    assert "counted at boot · " in caption and caption.endswith(" UTC")


def _status(**over) -> dict:
    base = {
        "tok_per_s": 41.7,
        "measured_utc": "2026-09-22 14:02 UTC",
        "hardware": "NVIDIA L4 · sm_89",
        "model": "Qwen3-1.7B",
        "lane": "algenta-cuda",
        "online": True,
    }
    base.update(over)
    return base


def test_gpu_tile_live_offline_with_log_and_offline_without():
    live = gpu_status.Snapshot(
        gpu_status.parse_status(json.dumps(_status()).encode()), "", "2026-09-22 14:03 UTC"
    )
    tile = try_tab.gpu_tile({}, snapshot=live, fetch_text=lambda url: pytest.fail("no log needed"))
    assert "41.7 tok/s" in tile and "NVIDIA L4" in tile
    assert tile.startswith('<div class="alg-tile" data-kind="live">') and "alg-stat-ok" in tile
    held = gpu_status.Snapshot(
        gpu_status.parse_status(json.dumps(_status(online=False)).encode()),
        "",
        "2026-09-22 14:03 UTC",
    )
    tile = try_tab.gpu_tile({}, snapshot=held, fetch_text=lambda url: pytest.fail("no log needed"))
    assert "41.7 tok/s" in tile and "last measured 2026-09-22 14:02 UTC" in tile
    assert (
        'data-kind="fallback"' in tile and "GPU stage offline" in tile and "alg-stat-warn" in tile
    )
    down = gpu_status.Snapshot(None, gpu_status.CODE_UNREACHABLE, "2026-09-22 14:03 UTC")
    log_text = (
        json.dumps(_status(tok_per_s=38.2, measured_utc="2026-09-21 09:10 UTC"))
        + "\n"
        + "not json\n"
    )
    tile = try_tab.gpu_tile(
        {}, snapshot=down, fetch_text=lambda url: common.Fetched(url, 200, log_text)
    )
    _assert_clean_copy(tile)
    assert "GPU stage offline — last measured 38.2 tok/s · 2026-09-21 09:10 UTC" in tile
    assert "41.7" not in tile and gpu_status.CODE_UNREACHABLE in tile
    assert "alg-stat-unavailable" in tile and "alg-card-err" not in tile, "quiet, not red"
    assert f'data-kind="unavailable">unavailable · {gpu_status.CODE_UNREACHABLE}<' in tile
    tile = try_tab.gpu_tile(
        {}, snapshot=down, fetch_text=lambda url: common.Fetched(url, 404, error="HTTP 404")
    )
    assert "GPU stage offline" in tile and "tok/s" not in tile
    custom = try_tab.gpu_tile(
        {try_tab.GPU_LOG_URL_ENV: "https://x/log.jsonl"},
        snapshot=down,
        fetch_text=lambda url: common.Fetched(
            url, 200, "" if url != "https://x/log.jsonl" else log_text
        ),
    )
    assert "38.2 tok/s" in custom
    assert try_tab.last_logged(None) is None and try_tab.last_logged("\n\n") is None


def test_where_band_has_three_tiles(deps):
    band = try_tab.where_band(deps, "<article>gpu</article>", "<article>hosted</article>")
    assert band.count("<article") == 3 and band.startswith('<div class="alg-tiles" data-count="3">')
    two = try_tab.where_band(deps, "", "<article>hosted</article>")
    assert two.count("<article") == 2 and two.startswith('<div class="alg-tiles" data-count="2">')
    assert "GPU" not in two, "an unwired stage gets no tile"


def test_gpu_tile_is_rendered_only_when_the_stage_is_wired(deps, monkeypatch):
    assert try_tab.gpu_configured({}) is False
    assert try_tab.gpu_configured({try_tab.GPU_STATUS_URL_ENV: "  "}) is False
    wired = {try_tab.GPU_STATUS_URL_ENV: "https://stage.example/api/status"}
    assert try_tab.gpu_configured(wired) is True
    assert try_tab.gpu_url(wired) == "https://stage.example/api/status"
    calls: list[str] = []
    monkeypatch.setattr(try_tab, "hosted_tile", lambda: "<article>hosted</article>")
    monkeypatch.setattr(try_tab, "gpu_tile", lambda env, **k: calls.append("gpu") or "<a>gpu</a>")
    deps.env = {}
    try_tab.build(deps)
    assert calls == [], "no GPU fetch, no GPU tile without the Space variable"
    deps.env = wired
    try_tab.build(deps)
    assert calls == ["gpu"]


def test_try_build_without_gradio_returns_the_spec(deps, monkeypatch):
    monkeypatch.setattr(try_tab, "hosted_tile", lambda: "<article>hosted</article>")
    monkeypatch.setattr(try_tab, "gpu_tile", lambda env, **k: "<article>gpu</article>")
    spec = try_tab.build(deps)
    assert spec.id == "try" and spec.label == "Try it" and spec.api_names == try_tab.API_NAMES
    assert spec.connect is not None and len(set(spec.api_names)) == 4


def test_try_inputs_never_round_in_the_browser(deps, monkeypatch):
    gr = pytest.importorskip("gradio")
    monkeypatch.setattr(try_tab, "hosted_tile", lambda: "<article>hosted</article>")
    spec = try_tab.build(deps)
    with gr.Blocks():
        handles = spec.render(gr)
    for box in handles["inputs"]:
        assert box.precision is None, "precision=0 would turn a typed 2.5 into 2 before Run"
        assert box.postprocess(2.5) == 2.5 and box.preprocess(2.5) == 2.5
    assert handles["on_edit"]() == (common.render_status(), "", "", "", ""), "an edit clears it"
    # round 11: the status row under Run is the reserved caption line, so a refusal's echo
    # fills it and the disclosures below never move; every field slot reserves two lines at
    # every width, because four fields and Run share the row (a 163 px box even at 1440)
    assert handles["status"].elem_classes == [common.STATUS_SLOT_CLASS]
    assert len(handles["slots"]) == 4
    for slot in handles["slots"]:
        assert slot.elem_classes == [
            "alg-status-row",
            "alg-field-slot",
            common.FIELD_SLOT_NARROW_CLASS,
        ]
    band = handles["band"].value
    assert "GPU" not in band and 'data-count="2"' in band, "no Space variable, no GPU tile"


def test_where_this_runs_is_three_tiles_of_one_geometry(deps):
    band = try_tab.where_band(
        deps,
        try_tab.gpu_tile({}, snapshot=gpu_status.Snapshot(None, "gpu_status_unreachable", "")),
        try_tab.hosted_tile(lambda url: common.Fetched(url, 200, {"tools": [1]})),
    )
    assert band.count('<div class="alg-tile"') == 3, "three tiles of one geometry"
    assert band.count('<article class="alg-stat') == 3, "each the design system's stat tile"


# ---------------------------------------------------------------------------
# Playground
# ---------------------------------------------------------------------------


def test_catalogue_navigation_and_default_selection(deps):
    cat = play_tab.Catalogue(deps)
    assert "stats" in cat.families and "algenta" not in cat.families
    assert cat.default_selection() == ("stats", "ab_testing", "z_test_proportions")
    assert "z_test_proportions" in cat.functions("stats", "ab_testing")
    assert cat.modules("quantum") == [] and cat.functions("stats", "nope") == []
    assert cat.total_functions() > 100
    no_stats = tabs.Deps(
        kernels={"text": deps.kernels["text"]}, lane=deps.lane, hardware=HW, env={}
    )
    family, module, function = play_tab.Catalogue(no_stats).default_selection()
    assert family == "text" and module and function
    assert play_tab.Catalogue(tabs.Deps(kernels={}, lane=deps.lane)).default_selection() == (
        "",
        "",
        "",
    )
    assert cat.locate("text.fuzzy", "levenshtein_distance") == "text"
    assert cat.locate("ab_testing", "z_test_proportions") == "stats"
    assert cat.locate("ab_testing", "nope") is None and cat.locate("", "") is None
    assert cat.form("stats", "ab_testing", "z_test_proportions") is not None
    assert cat.form("stats", "ab_testing", "nope") is None and cat.form("", "", "") is None
    assert play_tab.split_qualname("a.b.c") == ("a.b", "c") and play_tab.split_qualname("x") == (
        "",
        "",
    )


def test_slot_plans_map_kinds_and_prefill_hero_defaults(deps):
    kernel = deps.kernels["graph"]
    form = playground.form_spec(
        kernel, "graph_analytics.centrality", "graph_betweenness_from_triplets"
    )
    plans = play_tab.slot_plans(
        form,
        play_tab.hero_defaults(
            "graph", "graph_analytics.centrality", "graph_betweenness_from_triplets"
        ),
    )
    assert len(plans) == play_tab.MAX_FIELDS
    visible = [p for p in plans if p.visible]
    assert [p.label for p in visible] == [
        "src",
        "dst",
        "weight",
        "n_nodes",
        "weighted",
        "normalized",
    ]
    assert [p.component for p in visible] == ["json", "json", "json", "number", "bool", "bool"]
    assert visible[0].value == "[0, 0, 1, 1, 2, 3, 3, 4]" and visible[3].value == 6
    assert not hasattr(visible[3], "precision"), "no control rounds what the visitor typed"
    assert visible[4].value is False and visible[5].value is True
    assert not plans[6].visible
    for plan in visible:
        _assert_clean_copy(plan.info)
    assert play_tab.hero_defaults("stats", "ab_testing", "nope") is None
    assert play_tab.hero_defaults("quantum", "a", "b") is None
    assert all(not p.visible for p in play_tab.slot_plans(None, None))
    restored = play_tab.slot_plans(form, {"src": [1, 2], "n_nodes": 3, "weighted": 1})
    assert restored[0].value == "[1, 2]" and restored[3].value == 3 and restored[4].value is True
    assert play_tab.control_kwargs(restored[3], "number") == {
        "visible": True,
        "label": "n_nodes",
        "info": restored[3].info,
        "value": 3,
        "step": play_tab.INT_STEP,  # a whole-number field keeps the browser's step of 1
    }
    assert restored[3].kind == playground.KIND_INT
    assert play_tab.control_kwargs(restored[3], "bool") == {"visible": False}
    json_kwargs = play_tab.control_kwargs(restored[0], "json")
    assert json_kwargs["label"].startswith("src — ") and "info" not in json_kwargs
    assert play_tab.field_message("n_a", "is required") == "n_a is required."


def test_collect_raw_reads_each_fields_own_component(deps):
    form = playground.form_spec(deps.kernels["stats"], "ab_testing", "z_test_proportions")
    slots = [
        [50, False, "junk", "[]"],
        [1000, True, "", ""],
        [65, False, "", ""],
        [1000, False, "", ""],
    ]
    assert play_tab.collect_raw(form, slots) == {
        "successes_a": 50,
        "n_a": 1000,
        "successes_b": 65,
        "n_b": 1000,
    }
    assert play_tab.collect_raw(form, slots[:2]) == {"successes_a": 50, "n_a": 1000}


def test_run_call_validation_success_and_errors(deps, monkeypatch):
    cat = play_tab.Catalogue(deps)
    monkeypatch.setattr(races, "reference_for", lambda m, f: None)
    bad = _drain(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 50, "n_a": "x", "successes_b": 65, "n_b": 1000},
        )
    )
    assert (
        len(bad) == 1 and bad[0].field_errors == {"n_a": "must be an int"} and bad[0].card is None
    )
    decimal = _drain(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 50, "n_a": 2.5, "successes_b": 65, "n_b": 1000},
        )
    )
    assert decimal[0].field_errors == {"n_a": "must be a whole number"}
    assert play_tab.field_message("n_a", decimal[0].field_errors["n_a"]) == (
        "n_a must be a whole number."
    )
    huge = _drain(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 50, "n_a": 1 << 63, "successes_b": 65, "n_b": 1000},
        )
    )
    assert play_tab.field_message("n_a", huge[0].field_errors["n_a"]) == (
        "n_a is too large; use Reproduce."
    )
    assert huge[0].refused and huge[0].card is None
    for raw, field_name, reason in (
        (
            {"successes_a": -5, "n_a": 1000, "successes_b": 65, "n_b": 1000},
            "successes_a",
            "cannot be negative",
        ),
        (
            {"successes_a": 50, "n_a": 0, "successes_b": 65, "n_b": 1000},
            "n_a",
            "must be at least 1",
        ),
        (
            {"successes_a": 50, "n_a": 1000, "successes_b": 1001, "n_b": 1000},
            "successes_b",
            "cannot exceed n_b",
        ),
        (
            {"successes_a": (1 << 53) + 1, "n_a": 1000, "successes_b": 65, "n_b": 1000},
            "successes_a",
            playground.REASON_ABOVE_BROWSER_RANGE,
        ),
    ):
        refused = _drain(
            play_tab.run_call(deps, cat, "stats", "ab_testing", "z_test_proportions", raw)
        )
        assert len(refused) == 1 and refused[0].refused, raw
        assert refused[0].field_errors == {field_name: reason} and refused[0].card is None
    assert deps.kernels["stats"].kernel.calls == [], "nothing native ran on refused input"
    outcomes = _drain(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000},
        )
    )
    assert len(outcomes) == 2 and "queued" in outcomes[0].chip or "running" in outcomes[0].chip
    done = outcomes[1]
    assert (
        "done in" in done.chip
        and "alg-card-result" in done.card
        and "ab_testing.z_test_proportions" in done.card
    )
    _assert_clean_copy(done.card)
    assert '<div class="alg-card-sub">Two-proportion z-test.</div>' in done.card
    assert "torch25-cpu-aarch64-darwin" not in done.card, "the build variant is provenance"
    assert "algenta-stats@" in done.card, "the family and revision ride as a chip"
    assert json.loads(done.request_json)["args"] == [50, 1000, 65, 1000]
    assert "result" in json.loads(done.response_json)
    assert set(done.snippets) == {"kernels", "sdk", "mcp"}
    compile(done.snippets["kernels"], "<k>", "exec")
    compile(done.snippets["sdk"], "<s>", "exec")
    json.loads(done.snippets["mcp"])
    assert done.permalink.startswith("?tab=play&fn=ab_testing.z_test_proportions")
    # A selection this container does not serve: the quiet coded card (nothing ran, so nothing
    # is red) and the sentence for the status row; a field refusal it is not.
    unknown = _drain(play_tab.run_call(deps, cat, "stats", "ab_testing", "nope", {}))
    assert len(unknown) == 1 and "unavailable · unknown_function" in unknown[0].card
    assert "alg-card-quiet" in unknown[0].card and "alg-card-err" not in unknown[0].card
    assert unknown[0].echo == (
        f"nope is not one of the {len(cat.functions('stats', 'ab_testing'))}"
        " functions of ab_testing."
    )
    assert unknown[0].field_errors == {} and not unknown[0].refused
    _assert_clean_copy(unknown[0].card)
    missing = _drain(play_tab.run_call(deps, cat, "quantum", "a", "b", {}))
    assert "unavailable · unknown_family" in missing[0].card, "not published: unknown, not failed"
    assert missing[0].echo == (
        f"quantum is not one of the {len(cat.families)} families loaded in this container."
    )
    assert missing[0].echo in missing[0].card
    # A published family that did not load here keeps the boot card's own code and reason.
    absent = next(f for f in playground.FAMILIES if f not in deps.kernels)
    failed = tabs.Deps(
        kernels=deps.kernels,
        lane=deps.lane,
        hardware=HW,
        env={},
        kernel_errors={
            absent: hubkernel.HubKernelUnavailable(
                "variant_unavailable", "No wheel for this platform in the cache."
            )
        },
    )
    held = _drain(play_tab.run_call(failed, play_tab.Catalogue(failed), absent, "a", "b", {}))
    assert "unavailable · variant_unavailable" in held[0].card
    assert held[0].echo == (
        f"{absent} did not load in this container: no wheel for this platform in the cache."
    )
    # a container where nothing loaded leaves the dropdowns empty: a press arrives with None
    # and gets the quiet card, never a raise (round 3 measured Gradio's error toast for it)
    assert deps.kernel(None) is None and deps.kernel("") is None
    unset = _drain(play_tab.run_call(deps, cat, None, None, None, {}))
    assert common.CODE_NO_KERNEL in unset[0].card and play_tab.EMPTY_TITLE in unset[0].card
    assert "None" not in re.sub(r"<[^>]+>", " ", unset[0].card)
    assert not unset[0].refused and unset[0].field_errors == {}


def test_selection_refusal_names_the_first_thing_wrong_and_filters_are_dismissals(deps):
    cat = play_tab.Catalogue(deps)
    assert play_tab.selection_refusal(deps, cat, "stats") is None
    assert play_tab.selection_refusal(deps, cat, "stats", "ab_testing") is None
    assert (
        play_tab.selection_refusal(deps, cat, "stats", "ab_testing", "z_test_proportions") is None
    )
    families, modules = len(cat.families), len(cat.modules("stats"))
    functions = len(cat.functions("stats", "ab_testing"))
    assert play_tab.selection_refusal(deps, cat, "quantum", "ab_testing", "z_test_proportions") == (
        "unknown_family",
        f"quantum is not one of the {families} families loaded in this container.",
    )
    assert play_tab.selection_refusal(deps, cat, "stats", "nope", "z_test_proportions") == (
        "unknown_module",
        f"nope is not one of the {modules} modules of stats.",
    )
    assert play_tab.selection_refusal(deps, cat, "stats", "ab_testing", "nope") == (
        "unknown_function",
        f"nope is not one of the {functions} functions of ab_testing.",
    )
    assert play_tab.selection_refusal(deps, cat, "stats", "nope")[0] == "unknown_module"
    code, text = play_tab.selection_refusal(deps, cat, "")
    assert code == "unknown_family" and text.startswith("An empty name is not one of the")
    assert len(play_tab.selection_refusal(deps, cat, "x" * 400)[1]) < 140, "a typed name is cut"
    none_loaded = tabs.Deps(kernels={}, lane=deps.lane, hardware=HW, env={})
    assert play_tab.selection_refusal(none_loaded, play_tab.Catalogue(none_loaded), "stats") == (
        "unknown_family",
        "stats is not available here: no families loaded in this container.",
    )
    # An unfinished filter still matches part of a choice (Gradio filters by substring).
    choices = cat.functions("stats", "ab_testing")
    assert play_tab.is_filter("z_test", choices) and play_tab.is_filter("PROPORTION", choices)
    assert not play_tab.is_filter("nope", choices)
    assert not play_tab.is_filter("", choices) and not play_tab.is_filter(None, choices)
    card = play_tab.refusal_card(deps, code, text)
    _assert_clean_copy(card)
    assert 'data-state="unavailable"' in card and "alg-card-err" not in card
    assert play_tab.EMPTY_TITLE in card and text in card and HW in card


def test_editor_state_shows_the_default_call_or_nothing(deps):
    cat = play_tab.Catalogue(deps)
    known = play_tab.editor_state(cat, "stats", "ab_testing", "z_test_proportions", None)
    assert known.known
    request = json.loads(known.request_json)
    assert request == {
        "module": "ab_testing",
        "function": "z_test_proportions",
        "args": [200, 1000, 260, 1000],
    }
    assert set(known.snippets) == {"kernels", "sdk", "mcp"}
    compile(known.snippets["kernels"], "<k>", "exec")
    assert known.permalink.startswith("?tab=play&fn=ab_testing.z_test_proportions&args=")
    typed = play_tab.editor_state(
        cat,
        "geometry",
        "geodesy",
        "haversine_distance",
        {"lat1": 51.5074, "lon1": -0.1278, "lat2": 48.8566, "lon2": 2.3522},
    )
    assert json.loads(typed.request_json)["args"] == [51.5074, -0.1278, 48.8566, 2.3522]
    assert "lat1=51.5074" in typed.snippets["kernels"], "the snippet carries the typed decimals"
    unknown = play_tab.editor_state(cat, "stats", "ab_testing", "sample_size_proportion", None)
    assert not unknown.known and unknown.snippets == {} and unknown.permalink is None
    assert not play_tab.editor_state(cat, "stats", "ab_testing", "nope", None).known
    subtitle = play_tab.subtitle_for(
        cat, "stats", "ab_testing", cat.form("stats", "ab_testing", "z_test_proportions")
    )
    assert subtitle == "Two-proportion z-test."
    note = play_tab.build_note(deps, deps.kernels["stats"])
    assert "algenta-stats@" in note and "build torch25-cpu-aarch64-darwin" in note
    assert play_tab.build_note(deps, None) == ""


def test_play_permalink_protocol_restores_family_module_function_and_args(deps):
    cat = play_tab.Catalogue(deps)
    box = object()
    assert play_tab.permalink_outputs({"restore": box}) == [box]
    assert play_tab.permalink_outputs({}) == []
    payload = play_tab.permalink_restore(
        "text.fuzzy.levenshtein_distance", {"a": "kitten", "b": "sitting"}
    )
    assert len(payload) == 1 and json.loads(payload[0])["fn"] == "text.fuzzy.levenshtein_distance"
    assert play_tab.restore_target(cat, payload[0]) == (
        "text",
        "text.fuzzy",
        "levenshtein_distance",
        {"a": "kitten", "b": "sitting"},
    )
    assert (
        play_tab.restore_target(cat, play_tab.permalink_restore("ab_testing.nope", None)[0]) is None
    )
    assert play_tab.restore_target(cat, play_tab.permalink_restore(None, {"n": 1})[0]) is None
    assert play_tab.restore_target(cat, "") is None and play_tab.restore_target(cat, "{bad") is None
    # the report: the function this container serves, and only the values the fields can show
    z = "ab_testing.z_test_proportions"
    assert play_tab.applied_call(cat, z, {"successes_a": 12.5, "n_a": 345, "x": 1}) == (
        z,
        {"n_a": 345},
    ), "a decimal for a whole number and an unknown key apply nothing"
    assert play_tab.applied_call(cat, z, {"successes_a": 12.0}) == (z, {"successes_a": 12})
    assert play_tab.applied_call(cat, z, {"successes_a": (1 << 53) + 1}) == (z, None)
    assert play_tab.applied_call(cat, z, None) == (z, None)
    assert play_tab.applied_call(cat, "bogus.fn", {"x": 1}) is None
    assert play_tab.applied_call(cat, None, {"x": 1}) is None
    h = "geodesy.haversine_distance"
    assert play_tab.applied_call(cat, h, {"lat1": "north", "lon1": -0.1278}) == (
        h,
        {"lon1": -0.1278},
    )
    assert play_tab.applied_call(cat, h, {"lat1": 10}) == (h, {"lat1": 10}), "10 stays 10"
    assert play_tab.applied_call(cat, h, {"lat1": True}) == (h, None), "a bool is not a number"
    lev = "text.fuzzy.levenshtein_distance"
    assert play_tab.applied_call(cat, lev, {"a": "kitten", "b": 3}) == (lev, {"a": "kitten"})
    filtered = play_tab.restore_target(
        cat, play_tab.permalink_restore(z, {"successes_a": 12.5, "n_a": 345})[0]
    )
    assert filtered == ("stats", "ab_testing", "z_test_proportions", {"n_a": 345})
    assert play_tab.restore_target(
        cat, play_tab.permalink_restore(z, {"successes_a": 12.5})[0]
    ) == (
        "stats",
        "ab_testing",
        "z_test_proportions",
        None,
    )
    link = common.permalink(
        "play", fn="ab_testing.z_test_proportions", args={"n_a": 1}, base="https://s.hf.space"
    )
    assert link.startswith("https://s.hf.space/?tab=play&fn=ab_testing.z_test_proportions&args=")


def test_run_call_kernel_error_is_a_card_with_the_kernels_code(deps, stats_record):
    def boom(module, function, args):
        exc = RuntimeError("n is outside the 64-bit int range")
        exc.code = "invalid_arguments"
        raise exc

    deps.kernels["stats"].kernel = FakeKernel(
        stats_record["contract"], stats_record["excluded_functions"], answer=boom
    )
    cat = play_tab.Catalogue(deps)
    outcomes = _drain(
        play_tab.run_call(
            deps,
            cat,
            "stats",
            "ab_testing",
            "z_test_proportions",
            {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": 1000},
        )
    )
    assert "invalid_arguments" in outcomes[-1].card and "Traceback" not in outcomes[-1].card


def test_parity_chip_only_with_an_installed_reference(deps, monkeypatch):
    pytest.importorskip("nltk")
    label, tone = play_tab.parity_chip(
        "text.fuzzy", "levenshtein_distance", ["kitten", "sitting"], 3
    )
    assert tone == "ok" and label.startswith("exact match · nltk==")
    label, tone = play_tab.parity_chip(
        "text.fuzzy", "levenshtein_distance", ["kitten", "sitting"], 4
    )
    assert tone == "err" and label.startswith("differs from nltk==")
    assert play_tab.parity_chip(
        "ab_testing", "z_test_proportions", [50, 1000, 65, 1000], [0, 0]
    ) == ("", "")
    monkeypatch.setattr(
        races,
        "reference_for",
        lambda m, f: (races.Reference(lambda a: 1 / 0, lambda o, t: (True, ""), "x"), "x==1"),
    )
    label, tone = play_tab.parity_chip("a", "b", [], 1)
    assert tone == "warn" and "did not run" in label


def test_run_call_puts_the_parity_chip_on_the_card(deps):
    pytest.importorskip("nltk")
    cat = play_tab.Catalogue(deps)
    outcomes = _drain(
        play_tab.run_call(
            deps, cat, "text", "text.fuzzy", "levenshtein_distance", {"a": "kitten", "b": "sitting"}
        )
    )
    assert "parity exact match · nltk==" in outcomes[-1].card


# ---------------------------------------------------------------------------
# Races tab
# ---------------------------------------------------------------------------


def _state(deps, tmp_path: Path, qualified: Any = None, version_of=None) -> race_tab.RaceState:
    def fetched(url: str) -> common.Fetched:
        if qualified is None:
            return common.Fetched(url, 401, error="HTTP 401")
        return common.Fetched(url, 200, qualified)

    board = races.Board(tmp_path / "results.jsonl")
    state = race_tab.build_state(deps, fetch_json=fetched, board=board)
    if version_of is not None:
        state.offers = races.offers(deps.kernels, version_of=version_of)
    return state


def test_build_state_notes_say_what_is_qualified_and_what_is_not_offered(deps, tmp_path):
    state = _state(
        deps, tmp_path, version_of=lambda i, d: None if i in ("py_vollib", "geopy") else "1.0"
    )
    assert state.qualified.empty and state.qualified.error == "HTTP 401"
    note = race_tab.qualified_note(state)
    assert "No race has qualified on this hardware yet" in note
    _assert_clean_copy(note)
    offered = race_tab.not_offered_note(state)
    assert "Option chain Greeks" in offered and "Haversine" not in offered, "no longer a race"
    assert [c for _, c in race_tab.candidate_choices(state)] == [
        "levenshtein",
        "betweenness",
        "closeness",
        "primes",
    ]
    lev = races.CANDIDATES_BY_ID["levenshtein"]
    # the size radio is S · M · L on one line; the workload each means is the card's title
    assert race_tab.size_choices(lev) == [("S", "S"), ("M", "M"), ("L", "L")]
    assert race_tab.cell_title(lev, "M") == "Levenshtein distance · 600 × 600 characters"
    assert (
        race_tab.cell_title(lev, None) == lev.title and race_tab.cell_title(lev, "XL") == lev.title
    )
    assert race_tab.size_line(lev) == (
        "S 300 × 300 characters · M 600 × 600 characters · L 1,000 × 1,000 characters"
    )
    repro = race_tab.reproduce_note(state)
    assert "seed 20260922" in repro and "HTTP 401" in repro and str(state.board.path) in repro
    assert f"Levenshtein distance sizes: {race_tab.size_line(lev)}" in repro
    # the board under an empty qualified list says what its rows are, never "Nothing measured"
    board = race_tab.board_html(state)
    assert race_tab.NO_QUALIFIED_BOARD in board and race_tab.board_rows(state) == []
    assert race_tab.NOTHING_MEASURED not in board and "<table" not in board
    _assert_clean_copy(race_tab.HOW_MEASURED)
    assert "× k calls" in race_tab.HOW_MEASURED and "parity row" in race_tab.HOW_MEASURED
    qualified = _state(deps, tmp_path, qualified=["levenshtein"])
    assert "Qualified on this hardware: Levenshtein distance" in race_tab.qualified_note(qualified)
    board = race_tab.board_html(qualified)
    assert race_tab.NOTHING_MEASURED in board and race_tab.NO_QUALIFIED_BOARD not in board
    # round 10: a file another Space of this hardware class wrote names its writer; this
    # Space's own file (or one that names no writer) reads as before
    file = {
        "space_id": "thyn-ai/algenta-staging",
        "qualified": ["levenshtein"],
        "rule": "a cell qualifies when 3 of 3 runs were recorded and won",
        "generated_utc": "2026-09-23 16:27 UTC",
    }
    written = _state(deps, tmp_path, qualified=file)
    written.space_id = "thyn-ai/algenta"
    note = race_tab.qualified_note(written)
    assert (
        "Qualified on this hardware class by thyn-ai/algenta-staging: Levenshtein distance" in note
    )
    assert "Qualified on this hardware:" not in note and "written 2026-09-23 16:27 UTC" in note
    _assert_clean_copy(note)
    assert race_tab.qualified_lead(written.qualified, "") == race_tab.QUALIFIED_BY.format(
        writer="thyn-ai/algenta-staging"
    )
    written.space_id = "thyn-ai/algenta-staging"
    own = race_tab.qualified_note(written)
    assert "Qualified on this hardware: Levenshtein distance" in own and "by thyn-ai" not in own
    assert race_tab.qualified_lead(qualified.qualified, "thyn-ai/algenta") == (
        race_tab.QUALIFIED_HERE
    ), "a file that names no writer"


def _patch_fast_cells(monkeypatch):
    def fast(*args, **kwargs):
        kwargs.setdefault("execute", lambda k, m, f, a: _Call(k.kernel.execute(m, f, a)))
        return _REAL_RUN_RACE(*args, **{**kwargs, **stable_cell_kwargs()})

    monkeypatch.setattr(race_tab.races, "run_race", fast)


def test_run_cell_unqualified_is_parity_not_a_race(deps, tmp_path, monkeypatch):
    pytest.importorskip("nltk")
    _patch_fast_cells(monkeypatch)
    state = _state(deps, tmp_path)
    outcomes = _drain(race_tab.run_cell(deps, state, "levenshtein", "S"))
    assert len(outcomes) == 2
    card = outcomes[1].card
    _assert_clean_copy(card)
    # round 6: the unqualified cell prints its measured figure with its status, never a
    # sentence that denies the two latencies beside it; the hero stays the parity badge
    assert race_tab.NOT_QUALIFIED_TEXT in card and "not a race" not in card
    assert "parity" in card and "algenta-text" in card and "nltk" in card
    assert "faster than" not in card and "alg-hero-num" not in card  # never a ratio hero
    assert "alg-hero-badge" in card
    # the measured cell is a parity row of the board: both latencies, the parity label, "not a
    # race" where a ratio would be — never "Nothing measured yet" beside a measured card
    assert len(state.board) == 1 and outcomes[1].rows is not None and outcomes[1].board
    row = state.board.rows()[0]
    assert row["kind"] == races.ROW_KIND_PARITY and row["duel_id"] == "levenshtein"
    shown = race_tab.board_rows(state)[0]
    assert shown[5].endswith(f"· {race_tab.NOT_QUALIFIED_TEXT}")  # `even`, or a figure with ×
    assert shown[6] == "exact match" and shown[-1] == "measured here"
    board = outcomes[1].board
    assert race_tab.NO_QUALIFIED_BOARD in board and race_tab.NOTHING_MEASURED not in board
    assert ">1 row<" in board and f"· {race_tab.NOT_QUALIFIED_TEXT}<" in board
    assert "not a race" not in board.split("<tbody")[1]
    _assert_clean_copy(board)
    assert state.board.last_win("levenshtein", "S") is None, "a parity row is not a win"
    assert (tmp_path / "results.jsonl").read_text().count("\n") == 1


def test_run_cell_qualified_win_is_recorded_and_loss_is_held(deps, tmp_path, monkeypatch):
    pytest.importorskip("nltk")
    _patch_fast_cells(monkeypatch)
    state = _state(deps, tmp_path, qualified=["levenshtein"])
    slow_kernel = deps.kernels["text"]

    def slow_execute(k, m, f, a):
        return _Call(k.kernel.execute(m, f, a))

    # Both lanes see the same fake clock, so the ratio is 1.0 exactly: a qualified race the
    # kernel did not win → held and disclosed, nothing recorded.
    outcomes = _drain(race_tab.run_cell(deps, state, "levenshtein", "S"))
    held = outcomes[1].card
    assert "held: incumbent faster on this run" in held and "not recorded" in held
    assert len(state.board) == 0 and outcomes[1].rows is None and outcomes[1].board is None

    # A run the kernel wins: make the incumbent take two clock steps per call.
    def winning(*args, **kwargs):
        clock = FakeClock()
        cand = args[0]
        build = cand.build

        def slow_build(size, seed):
            workload = build(size, seed)
            incumbent = workload.incumbent

            def slower():
                clock()
                return incumbent()

            workload.incumbent = slower
            return workload

        patched = races.Candidate(
            cand.id,
            cand.title,
            cand.family,
            cand.module,
            cand.function,
            cand.incumbent,
            cand.import_name,
            cand.sizes,
            slow_build,
        )
        kwargs.update(execute=slow_execute, clock=clock, loadavg=lambda: 0.1, quota=8)
        return _REAL_RUN_RACE(patched, *args[1:], **kwargs)

    monkeypatch.setattr(race_tab.races, "run_race", winning)
    outcomes = _drain(race_tab.run_cell(deps, state, "levenshtein", "S"))
    card = outcomes[1].card
    assert "faster than nltk" in card and "held" not in card
    assert len(state.board) == 1 and outcomes[1].rows is not None
    row = state.board.rows()[0]
    assert (
        row["duel_id"] == "levenshtein"
        and row["harness_commit"] == "abc1234"
        and row["wheel_sha"] == slow_kernel.capped_v1_sha
    )
    rows = race_tab.board_rows(state)
    assert (
        rows[0][1] == "Levenshtein distance"
        and rows[0][-1] == "measured here"
        and rows[0][5].endswith("×")
    )
    assert row["kind"] == races.ROW_KIND_RACE
    assert state.board.last_win("levenshtein", "S") is row or (
        state.board.last_win("levenshtein", "S")["ts_utc"] == row["ts_utc"]
    )
    board = outcomes[1].board
    assert race_tab.NO_QUALIFIED_BOARD not in board and race_tab.NOTHING_MEASURED not in board
    assert (tmp_path / "results.jsonl").read_text().count("\n") == 1


def test_run_cell_refusals(deps, tmp_path, monkeypatch):
    state = _state(deps, tmp_path, version_of=lambda i, d: None if i == "nltk" else "1.0")
    not_offered = _drain(race_tab.run_cell(deps, state, "levenshtein", "S"))
    assert (
        "race_not_offered" in not_offered[0].card and "nltk is not installed" in not_offered[0].card
    )
    unknown = _drain(race_tab.run_cell(deps, state, "quantum", "S"))
    assert "race_not_offered" in unknown[0].card
    # every incumbent "installed", so the refusals below are about size, switch and lane, not
    # about which libraries this interpreter happens to have
    state = _state(deps, tmp_path, version_of=lambda i, d: "1.0")
    bad_size = _drain(race_tab.run_cell(deps, state, "betweenness", "XL"))
    assert "unknown_size" in bad_size[0].card

    class Off:
        def enabled(self, feature):
            return feature != race_tab.FEATURE

    deps.killswitch = Off()
    off = _drain(race_tab.run_cell(deps, state, "betweenness", "S"))
    assert common.CODE_SWITCHED_OFF in off[0].card
    deps.killswitch = None
    deps.lane.shutdown()
    closed = _drain(race_tab.run_cell(deps, state, "betweenness", "S"))
    assert "lane_closed" in closed[-1].card


def test_run_cell_size_out_of_range_is_a_card_with_the_code(deps, tmp_path, monkeypatch):
    state = _state(deps, tmp_path)
    monkeypatch.setitem(
        races.CANDIDATES_BY_ID,
        "miller_rabin",
        races.Candidate(
            "miller_rabin",
            "Miller-Rabin primality",
            "bits-time",
            "number_theory",
            "sieve_of_eratosthenes",
            "sympy",
            "sympy",
            (
                races.Size("S", "s", {"limit": 30}),
                races.Size("M", "m", {"limit": 100}),
                races.Size("L", "l", {"limit": races.PRIMES_LIMIT_CEILING + 1}),
            ),
            races.build_primes,
        ),
    )
    state.offers = races.offers(
        deps.kernels,
        candidates=tuple(races.CANDIDATES_BY_ID.values()),
        version_of=lambda i, d: "1.0",
    )
    out = _drain(race_tab.run_cell(deps, state, "miller_rabin", "L"))
    assert "size_out_of_range" in out[-1].card


# ---------------------------------------------------------------------------
# Boot facts: one truth for every count the page quotes
# ---------------------------------------------------------------------------


def test_boot_headline_and_family_summary_read_the_loaded_counts_never_the_catalogue():
    boot_sequence = importlib.import_module("boot_sequence")
    degraded = {
        "functions_loaded": 5683,
        "function_count": 6040,
        "catalogue_functions": 6040,
        "families_loaded": ["a"] * 18,
        "families_published": 19,
    }
    assert boot_sequence.headline(degraded) == "5,683 compiled Mojo kernels"
    assert boot_sequence.families_summary(degraded) == "18 of 19 families loaded"
    whole = {**degraded, "functions_loaded": 6040, "families_loaded": ["a"] * 19}
    assert boot_sequence.headline(whole) == "6,040 compiled Mojo kernels"
    assert boot_sequence.families_summary(whole) == "19 families loaded"
    assert boot_sequence.headline({}) == "Compiled Mojo kernels"
    assert boot_sequence.functions_loaded({"functions_loaded": True}) == 0, "a bool is not a count"
    assert boot_sequence.families_published({}) == len(hubkernel.TRUST) - 1


def test_boot_hosted_row_is_words_not_the_state_identifier():
    boot_sequence = importlib.import_module("boot_sequence")
    hosted_api = importlib.import_module("algenta_spaces.hosted_api")
    status = hosted_api.HostedStatus(
        hosted_api.ConfigState.NOT_CONFIGURED,
        hosted_api.NOT_CONFIGURED_REASON,
        hosted_api.DEFAULT_BASE_URL,
        "",
        "2026-09-22 14:02 UTC",
    )
    text = boot_sequence.hosted_detail(status)
    assert text == "not configured · no API key is set for this Space, so the governed lane is off"
    assert "_" not in text and "." not in text
    _assert_clean_copy(text)
    ready = hosted_api.HostedStatus(
        hosted_api.ConfigState.READY,
        "Connected to the hosted API.",
        hosted_api.DEFAULT_BASE_URL,
        "org",
        "2026-09-22 14:02 UTC",
    )
    assert boot_sequence.hosted_detail(ready) == "connected to the hosted API"
    limited = hosted_api.HostedStatus(
        hosted_api.ConfigState.RATE_LIMITED,
        "The hosted API is rate limited; retry in 30 s.",
        hosted_api.DEFAULT_BASE_URL,
        "",
        "2026-09-22 14:02 UTC",
    )
    assert boot_sequence.hosted_detail(limited) == (
        "rate limited · the hosted API is rate limited; retry in 30 s"
    )
    down = hosted_api.HostedStatus(
        hosted_api.ConfigState.UNAVAILABLE, "", hosted_api.DEFAULT_BASE_URL, "", "x"
    )
    assert boot_sequence.hosted_detail(down) == "unavailable"
    gov_tab = importlib.import_module("tabs.gov_tab")
    missing = hosted_api.HostedStatus(
        hosted_api.ConfigState.UNAVAILABLE,
        "ModuleNotFoundError: No module named 'algenta'",
        hosted_api.DEFAULT_BASE_URL,
        "",
        "x",
    )
    assert gov_tab.client_missing(missing)
    text = boot_sequence.hosted_detail(missing)
    assert text == f"not configured · {boot_sequence.CLIENT_MISSING_WORDS}"
    assert "ModuleNotFoundError" not in text and "_" not in text
    _assert_clean_copy(text)


class _HeroStageState:
    """What `boot_sequence._stage_hero` touches of a `BootState`: the registry, the lane, the
    machine line, the hero family and the tracker slot it fills."""

    def __init__(self, registry: Any, kernel: hubkernel.LoadedKernel) -> None:
        self.registry = registry
        self.lane = lane.Lane()
        self.hardware = HW
        self.kernel_errors: dict[str, Any] = {}
        self.hero_tracker: Any = None
        self._kernel = kernel

    def kernel(self, family: str) -> hubkernel.LoadedKernel | None:
        return self._kernel if family == "stats" else None


def test_boot_hero_row_is_live_after_a_background_attempt_records(kernels):
    """Round 3 measured the boot card's hero row frozen at the stage's end ('… measured again
    every 60 s until it records') while the tracker had recorded and the Try card showed 0.12 ms.
    The row now reads the tracker through the registry's detail hook: the same snapshot feeds
    /health and the boot card, so neither can contradict /health's hero."""
    import threading
    import time

    boot_sequence = importlib.import_module("boot_sequence")
    boot_mod = importlib.import_module("algenta_spaces.boot")
    registry = boot_sequence.FlagshipRegistry(boot_sequence.STAGES)
    assert isinstance(registry, boot_mod.BootRegistry) and registry.detail_hooks == {}
    quiet = threading.Event()

    class SwitchClock(FakeClock):
        """Jitters like a busy host until `quiet` is set, then ticks evenly (v0.6: noise is the
        samples' spread, never the load average)."""

        reads = 0

        def __call__(self) -> float:
            self.reads += 1
            step = (
                0.001 if quiet.is_set() else JitterClock.STEPS[self.reads % len(JitterClock.STEPS)]
            )
            self.now += step
            return self.now

    hero_kwargs = {
        "reference": _fake_reference,
        "clock": SwitchClock(),
        "loadavg": lambda: 0.1,
        "quota": 8,
    }
    state = _HeroStageState(registry, kernels["stats"])
    registry.start(boot_sequence.STAGE_HERO)
    boot_sequence._stage_hero(
        state, hero_kwargs, attempts=2, backoff_s=(0.0,), retry_s=0.05, sleep=lambda s: None
    )
    tracker = state.hero_tracker
    try:
        assert tracker.attempts == 2 and tracker.measured is None and tracker.running
        stage = next(s for s in registry.snapshot()["stages"] if s["id"] == "hero")
        assert stage["state"] == "done"
        assert stage["detail"].startswith("noisy — not recorded") and "attempt 2" in stage["detail"]
        assert stage["detail"].endswith("measured again every 0.05 s until it records")
        assert stage["detail"] == boot_sequence.hero_detail(tracker, boot_attempts=2)
        frozen = registry._stages["hero"].detail
        assert frozen == stage["detail"], "the stage's own words are the same, for now"
        finished, elapsed = stage["finished_at"], stage["elapsed_s"]
        # the machine goes quiet; the background thread records
        quiet.set()
        deadline = time.monotonic() + 5.0
        while tracker.measured is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert tracker.measured is not None, "a background attempt measured"
        tracker.stop(wait=True)
        live = next(s for s in registry.snapshot()["stages"] if s["id"] == "hero")
        assert live["state"] == "done" and live["finished_at"] == finished
        assert live["elapsed_s"] == elapsed, "the stage's clock stays boot's; only the words move"
        assert "per kernel call, n = " in live["detail"] and "statsmodels agrees" in live["detail"]
        assert try_tab.repeats_label(tracker.measured.cell) in live["detail"], (
            "the row prints the Try card's own n chip (n = 21 × k calls under rulebook v0.4)"
        )
        assert live["detail"].endswith(
            f"attempt {tracker.attempts} ·"
            f" {boot_sequence.after_boot_clause(tracker.measured.cell.ts_utc)}"
        )
        assert live["detail"].endswith(" UTC"), "the after-boot clause carries its own clock"
        assert tracker.attempts > 2 and "again" not in live["detail"], "no promise once it recorded"
        _assert_clean_copy(live["detail"])
        assert registry._stages["hero"].detail == frozen, (
            "what a plain registry would still print — the round-3 finding — stays frozen"
        )
        html = registry.render_html()
        assert boot_sequence.MEASURED_AFTER_BOOT in html and "until it records" not in html
        # the row agrees with the hero summary the same way /health does
        kernel_ms = tracker.measured.kernel_ms
        assert boot_sequence.bench_ms(kernel_ms) in live["detail"]
        # a hook that answers nothing or raises leaves the frozen words in place
        registry.detail_hooks[boot_sequence.STAGE_HOST] = lambda: None
        registry.detail_hooks[boot_sequence.STAGE_KERNELS] = lambda: 1 / 0
        registry.done(boot_sequence.STAGE_HOST, "host words")
        registry.done(boot_sequence.STAGE_KERNELS, "kernel words")
        stages = {s["id"]: s for s in registry.snapshot()["stages"]}
        assert stages["host"]["detail"] == "host words"
        assert stages["kernels"]["detail"] == "kernel words"
    finally:
        tracker.stop(wait=True)
        state.lane.shutdown(wait=False)
    # `hero_detail` alone: before any attempt, and a verdict with no thread behind it
    idle = try_tab.HeroTracker()
    assert boot_sequence.hero_detail(idle) == boot_sequence.HERO_NOT_ATTEMPTED
    measure, _calls = _noisy_then_measured(kernels, flips=99)
    noisy = try_tab.HeroTracker(measure)
    noisy.attempt()
    detail = boot_sequence.hero_detail(noisy, boot_attempts=1)
    assert detail.startswith("noisy — not recorded") and "attempt" not in detail
    assert "again" not in detail, "no thread, no promise"
    assert "algenta-stats" not in detail, "the lane's internal name never reaches the row"


def test_boot_kernels_summary_names_the_umbrella_once_and_never_as_a_family(kernels):
    boot_sequence = importlib.import_module("boot_sequence")
    outcome = hubkernel.Preload(elapsed_s=2.34)
    for family, loaded in kernels.items():
        outcome.loaded[f"algenta-{family}"] = loaded
    umbrella = hubkernel.LoadedKernel(
        family=hubkernel.UMBRELLA_FAMILY,
        repo_id="thyn-ai/algenta",
        kernel=kernels["stats"].kernel,
        variant="torch25-cpu-aarch64-darwin",
        capped_v1_sha="f" * 40,
        snapshot_sha="f" * 40,
        backend="cpu",
        version=1,
        load_s=0.1,
    )
    outcome.loaded[hubkernel.UMBRELLA_FAMILY] = umbrella
    n = len(kernels)
    assert (
        boot_sequence.kernels_summary(outcome) == f"{n} families and the umbrella loaded in 2.3 s"
    )
    for loaded in outcome.loaded.values():
        loaded.warmup_ms = 1.0
    assert boot_sequence.kernels_summary(outcome) == f"{n} families and the umbrella warm in 2.3 s"
    outcome.errors["algenta-llm"] = hubkernel.HubKernelUnavailable(
        "variant_unavailable", "no build"
    )
    assert boot_sequence.kernels_summary(outcome) == (
        f"{n} of {n + 1} families and the umbrella loaded in 2.3 s; llm: variant_unavailable"
    )
    del outcome.loaded[hubkernel.UMBRELLA_FAMILY]
    outcome.errors[hubkernel.UMBRELLA_FAMILY] = hubkernel.HubKernelUnavailable(
        "cache_missing", "offline"
    )
    text = boot_sequence.kernels_summary(outcome)
    assert text.startswith(f"{n} of {n + 1} families loaded in 2.3 s; ")
    assert "algenta: cache_missing" in text and "llm: variant_unavailable" in text
    assert "and the umbrella" not in text
    _assert_clean_copy(text)


# ---------------------------------------------------------------------------
# Copy rules over the owned modules, and the api_name contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", OWNED, ids=lambda p: p.name)
def test_owned_modules_pass_the_copy_lint_and_carry_no_fake_words(path: Path):
    findings = copy_lint.lint_python(path)
    assert findings == [], [f.format(REPO) for f in findings]
    source = path.read_text(encoding="utf-8")
    import re

    fake = re.compile(
        r"TODO|FIXME|XXX|placeholder|lorem|coming soon|\bmock|\bDemo|Simulated|NotImplementedError",
        re.IGNORECASE,
    )
    assert fake.search(source) is None, fake.search(source)
    assert "!important" not in source and "#" not in common.TABS_CSS


def test_api_names_are_the_ones_each_module_passes_to_gradio():
    import re

    for module, path in ((try_tab, OWNED[3]), (play_tab, OWNED[4]), (race_tab, OWNED[5])):
        source = path.read_text(encoding="utf-8")
        used = set(re.findall(r"api_name=API_NAMES\[(\d+)\]", source))
        assert {module.API_NAMES[int(i)] for i in used} == set(module.API_NAMES)
        for name in module.API_NAMES:
            assert name.startswith(f"{module.__name__.split('.')[-1].split('_')[0]}_")


# ---------------------------------------------------------------------------
# UI construction (gradio only)
# ---------------------------------------------------------------------------


def demo_fns(handles: dict) -> list[Any]:
    """The event functions of the Blocks the handles' components belong to."""
    import gradio as gr

    root = handles["family"].parent
    while root is not None and not isinstance(root, gr.Blocks):
        root = root.parent
    return list(root.fns.values()) if root is not None else []


def _events(blocks) -> list[dict]:
    return [
        {"api_name": fn.api_name, "concurrency_id": fn.concurrency_id, "fn": fn.fn}
        for fn in blocks.fns.values()
    ]


def test_tabs_render_and_connect_inside_gradio(deps, tmp_path, monkeypatch):
    gr = pytest.importorskip("gradio")
    monkeypatch.setattr(try_tab, "hosted_tile", lambda: "<article>hosted</article>")
    monkeypatch.setattr(try_tab, "gpu_tile", lambda env, **k: "<article>gpu</article>")
    state = _state(deps, tmp_path)
    specs = [try_tab.build(deps), play_tab.build(deps), race_tab.build(deps, state=state)]
    handles: dict[str, dict] = {}
    with gr.Blocks() as demo:
        with gr.Tabs() as tab_bar:
            for spec in specs:
                with gr.Tab(spec.label, id=spec.id):
                    handles[spec.id] = spec.render(gr)
        for spec in specs:
            if spec.connect is not None:
                spec.connect(gr, tab_bar, handles)
    events = _events(demo)
    names = {e["api_name"] for e in events if e["api_name"]}
    for spec in specs:
        assert set(spec.api_names) <= names, spec.id
    native = {e["api_name"] for e in events if e["concurrency_id"] == lane.NATIVE_CONCURRENCY_ID}
    assert {"try_run", "play_run", "race_run"} <= native
    assert (
        handles["race"]["candidate"].value in {c for _, c in race_tab.candidate_choices(state)}
        or handles["race"]["candidate"].value is None
    )
    assert len(handles["play"]["slots"]) == play_tab.MAX_FIELDS
    # The Try tab's code blocks: our caption, no stock block label, no line-number gutter; the
    # install and MCP chips show the one snippet block under its own caption.
    tried = handles["try"]
    for editor in (tried["snippet"], tried["full"]):
        assert editor.show_label is False and editor.show_line_numbers is False
    assert tried["snippet"].visible is False and tried["snippet_caption"].visible is False
    chip_events = {
        name: next(
            fn
            for fn in demo.fns.values()
            if (tried[name]._id, "click") in fn.targets and len(fn.outputs) == 4
        )
        for name in ("install_chip", "mcp_chip")
    }
    for event in chip_events.values():
        assert (
            event.outputs[0] is tried["snippet"] and event.outputs[-1] is tried["snippet_caption"]
        )
    shown = chip_events["install_chip"].fn(50, 1000, 65, 1000)
    assert shown[0]["language"] == "python" and shown[0]["visible"] is True
    assert "trust_remote_code" in shown[0]["value"] and shown[1]["visible"] is True
    assert shown[3]["visible"] is True and f">{try_tab.CAPTION_INSTALL}<" in shown[3]["value"]
    shown = chip_events["mcp_chip"].fn(50, 1000, 65, 1000)
    assert shown[0]["language"] == "json" and f">{try_tab.CAPTION_MCP}<" in shown[3]["value"]
    json.loads(shown[0]["value"])
    for block in demo.blocks.values():
        label = getattr(block, "label", None)
        if isinstance(label, str) and label:
            assert (
                shell.banned_phrase(label) is None
                and "!" not in label
                and not shell.has_emoji(label)
            ), label
    config = json.dumps(demo.get_config_file(), default=str)
    assert "1e-12" not in config


def test_try_race_chip_writes_the_shell_permalink_box_when_offered(deps, tmp_path, monkeypatch):
    """`gr.Tabs(selected=…)` from a handler fires no strip event, so the shell offers its
    permalink box under `try_tab.SHELL_HANDLE`; the chip names it as one more output and writes
    `?tab=race` in the same click. Without the handle (an older shell) the chip still works."""
    gr = pytest.importorskip("gradio")
    monkeypatch.setattr(try_tab, "hosted_tile", lambda: "<article>hosted</article>")
    monkeypatch.setattr(try_tab, "gpu_tile", lambda env, **k: "<article>gpu</article>")
    state = _state(deps, tmp_path)
    specs = [try_tab.build(deps), race_tab.build(deps, state=state)]
    for offered in (True, False):
        handles: dict[str, dict] = {}
        with gr.Blocks() as demo:
            box = gr.Textbox("?tab=try", interactive=False)
            if offered:
                handles[try_tab.SHELL_HANDLE] = {"permalink": box, "base": "https://x.hf.space"}
            with gr.Tabs() as tab_bar:
                for spec in specs:
                    with gr.Tab(spec.label, id=spec.id):
                        handles[spec.id] = spec.render(gr)
            for spec in specs:
                if spec.connect is not None:
                    spec.connect(gr, tab_bar, handles)
        chip_click = next(
            fn
            for fn in demo.fns.values()
            if (handles["try"]["race_chip"]._id, "click") in fn.targets
        )
        assert chip_click.api_name is False or chip_click.api_visibility == "private"
        assert (box in chip_click.outputs) is offered
        # round 5: `.input` never fires for a programmatic value, so the chip drives the
        # Races cascade itself — the size radio, the opening card and the applied id
        race = handles["race"]
        for name in ("candidate", "size", "card", "applied_id"):
            assert race[name] in chip_click.outputs, name
        values = chip_click.fn()
        assert isinstance(values[0], gr.Tabs)
        assert values[1]["value"] == try_tab.RACE_PRESELECT
        cand = races.CANDIDATES_BY_ID[try_tab.RACE_PRESELECT]
        assert values[2]["value"] == cand.default_size
        assert [v for _, v in values[2]["choices"]] == [size.key for size in cand.sizes]
        assert race_tab.cell_title(cand, cand.default_size) in values[3], "the card names it"
        assert values[4] == try_tab.RACE_PRESELECT, "the applied id follows the box"
        if offered:
            assert len(values) == 6 and values[5] == "https://x.hf.space/?tab=race"
        else:
            assert len(values) == 5


def test_play_function_change_and_run_handlers_through_gradio(deps, monkeypatch):
    gr = pytest.importorskip("gradio")
    monkeypatch.setattr(races, "reference_for", lambda m, f: None)
    spec = play_tab.build(deps)
    with gr.Blocks() as blocks:
        handles = spec.render(gr)
    per_slot = len(play_tab.SLOT_OUTPUTS)
    # The default function's form exists at construction: four visible int slots, prefilled.
    slots = handles["slots"]
    assert [s["column"].visible for s in slots] == [True] * 4 + [False] * (play_tab.MAX_FIELDS - 4)
    assert slots[0]["number"].visible and slots[0]["number"].label == "successes_a"
    assert slots[0]["number"].value == 200 and slots[0]["number"].precision is None
    assert slots[0]["number"].postprocess(51.5074) == 51.5074, "the browser shows what was set"
    assert not slots[0]["bool"].visible and not slots[0]["json"].visible
    # round 7: the message slot is always present (one reserved caption line), like Try's
    assert slots[0]["message"].visible and handles["surface"].visible and handles["doc"].visible
    assert "alg-field-slot" in slots[0]["message"].elem_classes
    # The editors open on the default call, never empty; the response waits for a response.
    assert handles["request_json"].visible and handles["request_json"].value.startswith("{")
    assert json.loads(handles["request_json"].value)["args"] == [200, 1000, 260, 1000]
    assert not handles["response_json"].visible and not handles["request_note"].visible
    assert all(box.visible and box.value for box in handles["snippets"].values())
    assert handles["permalink"].visible and handles["permalink"].value.startswith("?tab=play")
    assert not handles["reproduce_note"].visible and "algenta-stats@" in handles["provenance"].value
    # Every box takes a custom value (the API path), the handlers judge it, never Gradio.
    assert all(handles[b].allow_custom_value for b in ("family", "module", "function"))
    # Every read-only editor: our caption shown with it, no block label, no gutter.
    for name, caption in handles["captions"].items():
        editor = handles["snippets"].get(name) or handles[name]
        assert editor.show_label is False and editor.show_line_numbers is False, name
        assert caption.visible == editor.visible and "alg-code-caption" in caption.value, name
    assert set(handles["captions"]) == {"request_json", "response_json", "kernels", "sdk", "mcp"}
    form_len = 2 + play_tab.MAX_FIELDS * per_slot
    copies = sum(
        1
        for name in play_tab.EDITOR_OUTPUTS
        if name not in ("request_note", "reproduce_note", "provenance")
    )
    captions = len(handles["editor_captions"])
    default = ("stats", "ab_testing", "z_test_proportions")
    assert handles["selection"].value == default, "the guard holds the trio the form shows"
    # The same function again (a blur fires `input` with the value unchanged): every output is
    # untouched, so a typed value survives; the box update comes first, the state last.
    same = handles["on_function"](*default, default)
    assert len(same) == 1 + len(handles["change_outputs"]) + 1
    assert same[-1] == default and all(u == {"__type__": "update"} for u in same[:-1])
    assert handles["on_module"]("stats", "ab_testing", default)[-1] == default
    assert all(
        u == {"__type__": "update"}
        for u in handles["on_module"]("stats", "ab_testing", default)[:-1]
    )
    assert all(u == {"__type__": "update"} for u in handles["on_family"]("stats", default)[:-1])
    status_i, card_i = form_len, form_len + 1  # in `change_outputs`

    def refused(out: list, boxes: int, code: str, sentence: str) -> None:
        """The boxes snapped back, one echo and the quiet coded card written, nothing else
        moved, the guard as it was."""
        changes = out[boxes:-1]
        assert len(changes) == len(handles["change_outputs"]) and out[-1] == default
        status, card = changes[status_i]["value"], changes[card_i]["value"]
        # round 6: the status row acknowledges the refusal, it does not repeat the sentence
        assert 'class="alg-status-echo" role="status"' in status
        assert common.STATUS_NOT_RUN in status and sentence not in status
        assert 'role="alert"' not in status, "the echo is a status, never a second alert"
        assert f"unavailable · {code}" in card and "alg-card-quiet" in card and sentence in card
        _assert_clean_copy(status)
        _assert_clean_copy(card)
        rest = [u for i, u in enumerate(changes) if i not in (status_i, card_i)]
        assert all(u == {"__type__": "update"} for u in rest)

    # An unfinished filter (part of a choice) that a blur left in the box is a dismissal: the
    # box snaps back and nothing else moves.
    filtered = handles["on_function"]("stats", "ab_testing", "z_test", default)
    assert filtered[0] == {"__type__": "update", "value": "z_test_proportions"}
    assert all(u == {"__type__": "update"} for u in filtered[1:-1]) and filtered[-1] == default
    partial = handles["on_module"]("stats", "ab_", default)
    assert partial[0] == {"__type__": "update", "value": "ab_testing"}
    assert all(u == {"__type__": "update"} for u in partial[1:-1])
    sta = handles["on_family"]("sta", default)
    assert sta[0] == {"__type__": "update", "value": "stats"} and sta[-1] == default
    assert all(u == {"__type__": "update"} for u in sta[1:-1])
    # A typed name that matches nothing asks for something this container does not serve: the
    # box snaps back, the status row echoes one sentence and the card carries the code.
    snapped = handles["on_function"]("stats", "ab_testing", "z_test_proportionszzz", default)
    assert snapped[0] == {"__type__": "update", "value": "z_test_proportions"}
    refused(snapped, 1, "unknown_function", "z_test_proportionszzz is not one of the")
    snapped_module = handles["on_module"]("stats", "ab_testingzzz", default)
    assert snapped_module[0] == {"__type__": "update", "value": "ab_testing"}
    refused(snapped_module, 1, "unknown_module", "ab_testingzzz is not one of the")
    foreign = handles["on_family"]("quantum", default)
    assert foreign[0] == {"__type__": "update", "value": "stats"}, "the family box snaps back"
    assert foreign[1] == foreign[2] == {"__type__": "update"}
    refused(foreign, 3, "unknown_family", "quantum is not one of the")
    # A real change cascades and moves the guard.
    changed = handles["on_function"](
        "stats", "ab_testing", "confidence_interval_proportion", default
    )
    assert changed[-1] == ("stats", "ab_testing", "confidence_interval_proportion")
    assert changed[0] == {"__type__": "update"}, "the box already shows the picked function"
    updates = changed[1:-1]
    assert len(updates) == form_len + 2 + len(play_tab.EDITOR_OUTPUTS) + copies + captions
    assert len(handles["change_outputs"]) == len(updates)
    assert updates[1]["visible"] is True, "the form surface"
    assert updates[2]["visible"] is True, "field 0's column"
    assert updates[3]["label"] == "successes", "the picked function's first field"
    back = handles["on_function"](
        *default, ("stats", "ab_testing", "confidence_interval_proportion")
    )
    assert back[-1] == default
    updates = back[1:-1]
    first_number = updates[3]
    assert first_number["visible"] is True and first_number["label"] == "successes_a"
    assert "precision" not in first_number, "no update may round the visitor's decimals"
    assert updates[4]["visible"] is False  # the bool slot of field 0
    assert updates[2 + per_slot - 1] == {"__type__": "update", "value": ""}, "cleared, not hidden"
    assert updates[2 + 4 * per_slot]["visible"] is False, "field 4 does not exist: its column hides"
    # … then the reset: a blank status row, the empty card, the editors on the default call.
    reset = updates[form_len:]
    assert reset[0]["value"] == common.render_status()
    assert "alg-card-empty" in reset[1]["value"] and play_tab.EMPTY_TITLE in reset[1]["value"]
    editors = dict(zip(play_tab.EDITOR_OUTPUTS, reset[2:], strict=False))
    assert editors["request_json"]["visible"] is True
    assert json.loads(editors["request_json"]["value"])["args"] == [200, 1000, 260, 1000]
    assert editors["response_json"] == {"__type__": "update", "value": "", "visible": False}
    assert editors["request_note"]["visible"] is False
    assert (
        editors["kernels"]["visible"] is True and "successes_a=200" in editors["kernels"]["value"]
    )
    assert editors["permalink"]["visible"] is True and editors["reproduce_note"]["visible"] is False
    # A function with no known argument set hides the editors behind the notes, never empty.
    optional = handles["on_function"]("stats", "ab_testing", "sample_size_proportion", default)[
        1:-1
    ]
    editors = dict(zip(play_tab.EDITOR_OUTPUTS, optional[form_len + 2 :], strict=False))
    assert editors["request_json"]["visible"] is False and editors["request_note"]["visible"]
    assert editors["kernels"]["visible"] is False and editors["reproduce_note"]["visible"]
    assert all(
        u["visible"] is False for u in optional[form_len + 2 + len(play_tab.EDITOR_OUTPUTS) :]
    )
    # The API path: a function another family does not publish is the same refusal (the form
    # is never cleared into nothing) …
    foreign_fn = handles["on_function"]("text", "text.fuzzy", "nope", default)
    assert foreign_fn[0] == {"__type__": "update", "value": "z_test_proportions"}
    refused(foreign_fn, 1, "unknown_function", "nope is not one of the")
    # … and one it does publish cascades into that function's form, the guard moving with it.
    api_fn = handles["on_function"]("text", "text.fuzzy", "levenshtein_distance", default)
    assert api_fn[-1] == ("text", "text.fuzzy", "levenshtein_distance")
    api_str0 = api_fn[1 + 2 + play_tab.SLOT_OUTPUTS.index("str")]
    assert api_str0["visible"] is True and api_str0["label"] == "a"
    # The cascade from a family choice carries the module, the function and the whole form;
    # the family box itself is left as the visitor set it.
    family_updates = handles["on_family"]("text", default)
    assert len(family_updates) == 3 + len(updates) + 1
    assert family_updates[0] == {"__type__": "update"}, "the box already shows the picked family"
    assert (
        family_updates[1]["choices"]
        and family_updates[1]["value"] == family_updates[1]["choices"][0]
    )
    assert family_updates[-1][0] == "text" and family_updates[-1][1] == family_updates[1]["value"]
    module_updates = handles["on_module"]("text", "text.fuzzy", default)
    assert (
        len(module_updates) == 1 + len(updates) + 1
        and "levenshtein_distance" in module_updates[0]["choices"]
    )
    assert module_updates[-1][:2] == ("text", "text.fuzzy")
    # A permalink restores the trio and the arguments; an unknown one changes nothing.
    restored = handles["on_restore"](
        play_tab.permalink_restore(
            "text.fuzzy.levenshtein_distance", {"a": "kitten", "b": "sitting"}
        )[0],
        default,
    )
    assert len(restored) == 3 + len(updates) + 1
    assert restored[0]["value"] == "text" and restored[1]["value"] == "text.fuzzy"
    assert restored[2]["value"] == "levenshtein_distance"
    assert restored[-1] == ("text", "text.fuzzy", "levenshtein_distance")
    str_slot0 = restored[3 + 2 + play_tab.SLOT_OUTPUTS.index("str")]
    assert (
        str_slot0["visible"] is True
        and str_slot0["value"] == "kitten"
        and str_slot0["label"] == "a"
    )
    untouched = handles["on_restore"](play_tab.permalink_restore("nope.nope", None)[0], default)
    assert all(u == {"__type__": "update"} for u in untouched[:-1]) and untouched[-1] == default
    # The events: `input` on the three boxes with the guard state as the last input and output.
    for box in ("family", "module", "function"):
        event = next(fn for fn in demo_fns(handles) if (handles[box]._id, "input") in fn.targets)
        assert (
            event.inputs[-1] is handles["selection"] and event.outputs[-1] is handles["selection"]
        )
        # every handler writes the box it may snap back: the family its own, the others the
        # box whose typed value they judge (the module handler cascades into the function box)
        snapped_box = handles["family"] if box == "family" else handles["function"]
        assert event.outputs[0] is snapped_box, box
        assert handles[box] in event.outputs or box == "module", box
        assert not any((handles[box]._id, "change") in fn.targets for fn in demo_fns(handles))
    assert callable(handles["permalink_applied"])
    assert handles["permalink_applied"]("bogus.fn", {"x": 1}) is None
    assert handles["permalink_applied"]("text.fuzzy.levenshtein_distance", {"a": "k", "b": 1}) == (
        "text.fuzzy.levenshtein_distance",
        {"a": "k"},
    )
    # A refused Run: the message under the field, the card back to its empty state, the
    # response hidden — never a card beside arguments that did not run.
    slot_values: list[Any] = []
    for _index in range(play_tab.MAX_FIELDS):
        slot_values.extend([None, False, "", ""])
    slot_values[0:4] = [-5, False, "", ""]
    slot_values[4:8] = [1000, False, "", ""]
    slot_values[8:12] = [65, False, "", ""]
    slot_values[12:16] = [1000, False, "", ""]
    outs = list(handles["on_run"](*default, *slot_values))
    assert len(outs) == 1, "a refusal is one step"
    out = outs[0]
    n_editors, n_copies = len(play_tab.EDITOR_OUTPUTS), len(handles["copies"])
    assert len(out) == 2 + n_editors + play_tab.MAX_FIELDS + n_copies + copies + captions
    # … said twice, one convention: under the field (alert) and beside Run (status).
    sentence = "successes_a cannot be negative."
    assert f'<p class="alg-status-echo" role="status">{common.STATUS_NOT_RUN}</p>' in out[0]
    assert sentence not in out[0], "the sentence lives under the field, once"
    assert 'role="alert"' not in out[0] and "alg-chip" not in out[0]
    assert "alg-card-empty" in out[1] and play_tab.EMPTY_TITLE in out[1]
    editors = dict(zip(play_tab.EDITOR_OUTPUTS, out[2:], strict=False))
    assert editors["response_json"] == {"__type__": "update", "value": "", "visible": False}
    # No call was made: the request editor never keeps an earlier run's request; the note says
    # so; the Reproduce editors keep their snippet (the 2^53 refusal points the visitor there).
    assert editors["request_json"] == {"__type__": "update", "value": "", "visible": False}
    assert editors["request_note"]["visible"] is True
    assert play_tab.REQUEST_REFUSED_NOTE in editors["request_note"]["value"]
    _assert_clean_copy(editors["request_note"]["value"])
    for name in ("kernels", "sdk", "mcp", "permalink", "provenance", "reproduce_note"):
        assert editors[name] == {"__type__": "update"}, name
    messages = out[2 + n_editors : 2 + n_editors + 4]
    # round 7: the slots are always present; a refusal fills one line, the others are cleared
    assert sentence in messages[0]["value"] and "visible" not in messages[0]
    assert 'role="alert"' in messages[0]["value"]
    assert all(m == {"__type__": "update", "value": ""} for m in messages[1:])
    # The Copy chips and the captions follow their editors: request and response hidden.
    tail = list(out[2 + n_editors + play_tab.MAX_FIELDS + n_copies :])
    copy_rows, caption_rows = tail[:copies], tail[copies:]
    hidden = {"__type__": "update", "visible": False}
    assert copy_rows[:2] == [hidden, hidden] and caption_rows[:2] == [hidden, hidden]
    assert all(u == {"__type__": "update"} for u in copy_rows[2:] + caption_rows[2:])
    # round 11: editing any generated control clears the refusal — the alert under the field
    # and the echo beside Run — as Try's and the LLM tab's boxes do (`.input`, never `.change`)
    cleared = handles["on_edit"]()
    assert cleared[0] == common.render_status() and "alg-status-echo" not in cleared[0]
    assert len(cleared) == 1 + play_tab.MAX_FIELDS
    assert all(u == {"__type__": "update", "value": ""} for u in cleared[1:])
    assert handles["status"].elem_classes == [common.STATUS_SLOT_CLASS]
    edit_fns = [
        fn
        for fn in blocks.fns.values()
        if fn.fn is handles["on_edit"] and {event for _, event in fn.targets} == {"input"}
    ]
    controls = {slot[name]._id for slot in handles["slots"] for name in play_tab.SLOT_COMPONENTS}
    assert {block_id for fn in edit_fns for block_id, _ in fn.targets} == controls, (
        "every number, checkbox, text and JSON control clears the refusal on input"
    )
    for fn in edit_fns:
        assert [o._id for o in fn.outputs] == [
            handles["status"]._id,
            *(slot["message"]._id for slot in handles["slots"]),
        ]
        assert str(fn.api_name).startswith("false"), "no endpoint: a client-side convenience"
    # A run that then succeeds shows the request again, with its caption and Copy chip.
    slot_values[0:4] = [50, False, "", ""]
    ran = list(handles["on_run"](*default, *slot_values))[-1]
    ran_editors = dict(zip(play_tab.EDITOR_OUTPUTS, ran[2:], strict=False))
    assert ran_editors["request_json"]["visible"] is True
    assert json.loads(ran_editors["request_json"]["value"])["args"] == [50, 1000, 65, 1000]
    assert ran_editors["request_note"] == {"__type__": "update", "visible": False}
    ran_tail = ran[2 + n_editors + play_tab.MAX_FIELDS + n_copies :]
    assert ran_tail[0] == ran_tail[copies] == {"__type__": "update", "visible": True}
    assert "alg-status-echo" not in ran[0] and "done in" in ran[0]
