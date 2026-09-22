"""Local A-Z tests for the Algenta Speed Arena harness.

Run with the arena venv active:
    python -m pytest tests/test_arena.py -v

These tests exercise the duel registry end to end through the SAME
run_protocol/run_sweep the Gradio app calls: workload generation, correctness
gates, the timing protocol (cold + median-of-5 warm, interleaved), hero
computation, sweep-to-win selection, the timestamped leaderboard fallback,
card rendering, share text, leaderboard persistence and the app factory.

Native vs fallback: whichever backend the installed wheels provide in this
environment is what gets tested — on macOS CI wheels the native path runs;
on machines without a native wheel the cell reports held_kind="native"
(kernel unavailable) and the tests assert that honest behavior instead. The
linux native path is validated separately in the docker run of
scripts/run_duel.py.
"""

from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("ARENA_DISABLE_BOOT", "1")  # no async boot writes into test boards
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arena.harness as harness  # noqa: E402
from arena import store  # noqa: E402
from arena.card import render_card, render_fallback, render_held, share_text  # noqa: E402
from arena.duels import DUELS, DUELS_BY_ID  # noqa: E402
from arena.gallery import GALLERY  # noqa: E402
from arena.harness import (  # noqa: E402
    WARM_RUNS,
    DuelOutcome,
    LaneTiming,
    hardware_footer,
    run_protocol,
    run_sweep,
)

ALL_DUEL_IDS = [d.duel_id for d in DUELS]

# User-facing strings must never carry held/rule-speak (the "weird messages"
# the owner banned). Checked against every renderable surface.
FORBIDDEN_COPY = (
    "held",
    "publish-wins",
    "never shown as a loss",
    "never a loss",
    "losing",
    " a loss",
)


def test_registry_is_complete():
    assert len(DUELS) >= 12
    for d in DUELS:
        assert set(d.sizes) == {"S", "M", "L"}, d.duel_id
        assert d.title and d.blurb and d.metric_label and d.unit_label
        assert d.config_note
        for key in d.sizes:
            assert d.size_label(key)


def test_gallery_has_35_kernels_with_links():
    assert len(GALLERY) == 35
    for pkg, target, speedup, path in GALLERY:
        assert pkg and target and speedup and path.startswith(("python/", "typescript/"))


def test_hardware_footer_discloses_machine():
    footer = hardware_footer()
    assert "vCPU" in footer and "Python" in footer and "GB RAM" in footer


# ---------------------------------------------------------------------------
# Full protocol per duel at size S (smallest cell)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duel_id", ALL_DUEL_IDS)
def test_duel_protocol_size_s(duel_id, tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_PATH", str(tmp_path / "board.json"))
    duel = DUELS_BY_ID[duel_id]
    outcome = run_protocol(duel, "S")

    assert outcome.status in {"ok", "held"}, f"{duel_id}: error — {outcome.held_reason}"
    if outcome.status == "held":
        # Only legitimate hold: native kernel unavailable in this environment.
        assert "native" in outcome.held_reason.lower(), f"{duel_id}: {outcome.held_reason}"
        return

    # R1: gate ran and passed
    assert outcome.gate_ok and outcome.gate_detail
    assert outcome.parity_label

    # R5/R6: every lane has a cold time and exactly WARM_RUNS warm samples
    assert len(outcome.lanes) >= 2
    for lane in outcome.lanes:
        assert lane.cold_s >= 0
        assert lane.runs == WARM_RUNS
        assert lane.warm_min_s <= lane.warm_median_s <= lane.warm_max_s

    # Owner rule: the published hero is always a win
    assert outcome.hero_speedup > 1.0, f"{duel_id}: would have shipped a loss"
    sides = {t.side for t in outcome.lanes}
    assert sides == {"incumbent", "algenta"}

    # Card + share text render with the real numbers
    card = render_card(outcome, duel, duel.divisor("S"), duel.divided_label)
    assert f"{outcome.hero_speedup:,.2f}×" in card
    assert "parity" in card and outcome.hardware.split("·")[0].strip() in card or "vCPU" in card
    text = share_text(outcome)
    assert f"{outcome.hero_speedup:,.2f}×" in text
    assert "algenta-speed-arena" in text

    # Leaderboard round-trip
    store.record(outcome)
    latest = store.latest_per_duel()
    assert latest and latest[0]["duel_id"] == duel_id
    assert latest[0]["hero_speedup"] == round(outcome.hero_speedup, 3)


def test_gate_failure_holds_duel(monkeypatch):
    """A gate failure must stop the cell and show no timing numbers."""
    duel = DUELS_BY_ID["croniter"]

    def bad_gate(outputs):
        return False, "synthetic mismatch for the test", ""

    monkeypatch.setattr(duel, "gate", bad_gate)
    outcome = run_protocol(duel, "S")
    assert outcome.status == "held"
    assert outcome.held_kind == "gate"
    assert not outcome.lanes  # no timings published
    card = render_held(outcome)
    assert "could not run" in card
    assert "median" not in card


def test_loss_is_dropped_not_shown(monkeypatch):
    """A cell the incumbent wins is marked internally and dropped — never rendered."""
    duel = DUELS_BY_ID["croniter"]
    monkeypatch.setattr(duel, "hero", lambda lanes: (0.5, "0.50× vs croniter"))
    outcome = run_protocol(duel, "S")
    assert outcome.status == "held"
    assert outcome.held_kind == "loss"
    # The internal reason carries no rule-speak and is never user-facing.
    assert "publish-wins" not in outcome.held_reason
    assert "held" not in outcome.held_reason


def test_app_factory_builds():
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    import app as arena_app

    demo = arena_app.build_app()
    assert demo is not None
    # The boot duel targets a real duel (the boot thread itself is disabled
    # in tests via ARENA_DISABLE_BOOT so it cannot write into test boards).
    assert arena_app.DEFAULT_DUEL in DUELS_BY_ID


def test_outcome_defaults():
    o = DuelOutcome(duel_id="x", duel_title="t", size_key="S", size_label="s", status="error")
    assert o.hero_speedup == 0.0


# ---------------------------------------------------------------------------
# Sweep-to-win: the harness continues through configurations and shows the
# best one the kernel wins — real numbers, this run — or falls back to the
# duel's latest timestamped leaderboard win. Never a loss, never held-copy.
# ---------------------------------------------------------------------------


def _fake_outcome(
    duel, size_key: str, hero: float, status: str = "ok", held_kind: str = ""
) -> DuelOutcome:
    """A fully-populated outcome for sweep/render tests (no timing is faked
    into any store — these objects only exercise selection and rendering)."""
    out = DuelOutcome(
        duel_id=duel.duel_id,
        duel_title=duel.title,
        size_key=size_key,
        size_label=duel.size_label(size_key),
        status=status,
        held_kind=held_kind,
        gate_ok=status == "ok",
        gate_detail="synthetic gate detail" if status == "ok" else "",
        parity_label="synthetic parity" if status == "ok" else "",
        hero_speedup=hero if status == "ok" else 0.0,
        hero_label=f"{hero:,.2f}× vs incumbent (warm, median of 5)" if status == "ok" else "",
        metric_label=duel.metric_label,
        unit_label=duel.unit_label,
        config_note=duel.config_note,
        seed_note=duel.seed_note(size_key),
        setup_note="synthetic setup",
        hardware="test rig · 2 vCPU",
        timestamp="2026-09-21 12:00:00 UTC",
    )
    if status == "ok":
        out.lanes = [
            LaneTiming("incumbent X", "incumbent", 1.0, 0.900, 0.880, 0.920, WARM_RUNS, "cfg"),
            LaneTiming(
                "algenta-mojo (Algenta)",
                "algenta",
                0.4,
                0.900 / hero,
                0.900 / hero,
                0.900 / hero,
                WARM_RUNS,
                "cfg",
            ),
        ]
    else:
        out.held_reason = "synthetic non-win"
    return out


def test_sweep_requested_win_returned_directly(monkeypatch):
    """A win on the requested cell is shown as-is — no sweep, no note."""
    duel = DUELS_BY_ID["bm25"]
    win = _fake_outcome(duel, "S", 1.43)
    monkeypatch.setattr(harness, "run_protocol", lambda d, k, progress=None: win)
    result = run_sweep(duel, "S")
    assert result.outcome is win
    assert result.outcome.swept_from == ""
    assert len(result.attempts) == 1
    card = render_card(result.outcome, duel, duel.divisor("S"), duel.divided_label)
    assert "configuration:" not in card  # no swept note for the requested cell


def test_sweep_picks_best_winning_configuration(monkeypatch):
    """Requested cell loses → the sweep shows the best configuration that WINS
    on this run, with real fields and zero held-copy."""
    duel = DUELS_BY_ID["bm25"]
    outcomes = {
        "M": _fake_outcome(duel, "M", 0.0, status="held", held_kind="loss"),
        "S": _fake_outcome(duel, "S", 3.0),
        "L": _fake_outcome(duel, "L", 2.0),
    }
    monkeypatch.setattr(harness, "run_protocol", lambda d, k, progress=None: outcomes[k])
    result = run_sweep(duel, "M")

    assert len(result.attempts) == 3  # the full sweep ran
    assert result.outcome is outcomes["S"]  # the best win, not the first win
    assert result.outcome.swept_from == "M"

    card = render_card(result.outcome, duel, duel.divisor("S"), duel.divided_label)
    # Real fields from the winning cell, this run
    assert "3.00×" in card
    assert "configuration: S · batched" in card
    assert "lane-table" in card and "warm median" in card
    assert "test rig · 2 vCPU" in card
    assert "measured live 2026-09-21 12:00:00 UTC" in card
    for bad in FORBIDDEN_COPY:
        assert bad not in card.lower(), f"held-copy leaked into swept card: {bad!r}"


def test_sweep_native_unavailable_stops_early(monkeypatch):
    """A missing native kernel fails identically at every size — one attempt."""
    duel = DUELS_BY_ID["croniter"]
    native = _fake_outcome(duel, "S", 0.0, status="held", held_kind="native")
    monkeypatch.setattr(harness, "run_protocol", lambda d, k, progress=None: native)
    result = run_sweep(duel, "S")
    assert result.outcome is None
    assert len(result.attempts) == 1


def test_full_sweep_loss_falls_back_to_timestamped_leaderboard(monkeypatch, tmp_path):
    """Every configuration loses → the duel's latest WINNING leaderboard entry
    is shown with its real timestamp — never a loss, never a weird message."""
    monkeypatch.setattr(store, "_PATH", str(tmp_path / "board.json"))
    duel = DUELS_BY_ID["croniter"]

    def lose(d, k, progress=None):
        return _fake_outcome(d, k, 0.0, status="held", held_kind="loss")

    monkeypatch.setattr(harness, "run_protocol", lose)
    result = run_sweep(duel, "M")
    assert result.outcome is None
    assert len(result.attempts) == 3

    # No win ever recorded → an honest retry card, with zero loss-speak.
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    import app as arena_app

    empty_card = arena_app._fallback_card(duel, result)
    assert "no verified winning configuration to show yet" in empty_card
    assert "incumbent" not in empty_card.lower()
    for bad in FORBIDDEN_COPY:
        assert bad not in empty_card.lower()

    # A prior winning measurement exists on the board (real timestamp required)
    store.record(_fake_outcome(duel, "S", 16.4))
    entry = store.latest_win(duel.duel_id)
    assert entry is not None and entry["ts"] == "2026-09-21 12:00:00 UTC"
    assert entry["hero_speedup"] == 16.4

    card = render_fallback(entry, "press RUN DUEL for a live rematch")
    assert "16.40×" in card
    assert "last measured 2026-09-21 12:00:00 UTC" in card
    assert "live rematch" in card
    assert "lane-table" not in card  # no fabricated per-lane numbers
    for bad in FORBIDDEN_COPY:
        assert bad not in card.lower(), f"held-copy leaked into fallback card: {bad!r}"


def test_record_drops_non_wins(tmp_path, monkeypatch):
    """The leaderboard keeps winning rows only — losses are never written."""
    monkeypatch.setattr(store, "_PATH", str(tmp_path / "board.json"))
    duel = DUELS_BY_ID["croniter"]
    store.record(_fake_outcome(duel, "S", 0.0, status="held", held_kind="loss"))
    store.record(_fake_outcome(duel, "S", 0.0, status="held", held_kind="gate"))
    sneaky = _fake_outcome(duel, "S", 0.9)  # status ok but not a win
    store.record(sneaky)
    assert store.all_records() == []
    assert store.latest_per_duel() == []
    store.record(_fake_outcome(duel, "S", 10.2))
    assert len(store.all_records()) == 1
    assert store.latest_per_duel()[0]["hero_speedup"] == 10.2


def test_default_duel_is_the_reliable_big_winner():
    """The landing/boot duel is the wide-margin cpu-basic winner; BM25 stays
    selectable with its historically winning configuration preselected."""
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    import app as arena_app

    assert arena_app.DEFAULT_DUEL == "vol-hive"
    assert DUELS_BY_ID["vol-hive"].default_size == "S"
    assert "bm25" in DUELS_BY_ID  # still selectable
    # L · batched is bm25's reliable winning cell on cpu-basic (live evidence:
    # L wins directly; S/M flip on the shared 2-vCPU and engage the sweep).
    assert DUELS_BY_ID["bm25"].default_size == "L"
    assert DUELS_BY_ID["bm25"].variant == "batched"
    for d in DUELS:
        assert d.default_size in d.sizes, d.duel_id


def test_copy_audit_served_strings(monkeypatch):
    """Grep the served UI strings for held/rule-speak — it must be absent."""
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    import app as arena_app

    duel = DUELS_BY_ID["bm25"]
    surfaces = [
        arena_app.HEADER_HTML,
        arena_app.METHODOLOGY_MD,
        render_held(_fake_outcome(duel, "S", 0.0, status="error")),
        render_fallback(
            {
                "duel": duel.title,
                "size_label": duel.size_label("S"),
                "ts": "2026-09-21 12:00:00 UTC",
                "hero_speedup": 1.43,
                "hero_label": "1.43× vs bm25s (warm)",
                "parity": "p",
                "hardware": "hw",
            },
            "live rematch runs at next boot",
        ),
        render_card(_fake_outcome(duel, "S", 1.43), duel, duel.divisor("S"), duel.divided_label),
        share_text(_fake_outcome(duel, "S", 1.43)),
    ]
    for text in surfaces:
        low = text.lower()
        for bad in FORBIDDEN_COPY:
            assert bad not in low, f"held-copy {bad!r} found in served string: {text[:120]}"


def test_honesty_invariant_numbers_traceable(monkeypatch):
    """Every rendered number is either (a) measured this run (lane timings on
    the winning outcome) or (b) a leaderboard entry with a real timestamp."""
    duel = DUELS_BY_ID["croniter"]

    # (a) this-run win: the card's numbers come from the outcome's own lanes
    win = _fake_outcome(duel, "S", 10.24)
    card = render_card(win, duel, duel.divisor("S"), duel.divided_label)
    assert f"{win.hero_speedup:,.2f}×" in card
    for lane in win.lanes:
        assert f"{lane.warm_median_s * 1e3:,.2f} ms" in card
    assert win.timestamp in card

    # (b) fallback: only the entry's fields, with its timestamp — nothing else
    entry = {
        "duel": duel.title,
        "size_label": duel.size_label("S"),
        "ts": "2026-09-20 20:08:06 UTC",
        "hero_speedup": 10.239,
        "hero_label": "10.24× vs croniter 6.2.4 (warm, median of 5)",
        "parity": "exact datetime equality on every fire time",
        "hardware": "hw",
    }
    card = render_fallback(entry, "live rematch runs at next boot")
    assert "10.24×" in card and entry["ts"] in card
    assert "lane-table" not in card and "warm median</th>" not in card
