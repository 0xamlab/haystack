"""algenta_spaces.cards — result, held, not-recorded and unavailable cards, status chips."""

from __future__ import annotations

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import bench, cards

HW = "Space thyn-ai/algenta · cpu-upgrade · 8 vCPU · Linux x86_64 · Python 3.14.0"
TS = "2026-09-22 14:02 UTC"


def _lane(name: str, side: str, median: float, *, n: int = 21) -> bench.LaneResult:
    return bench.LaneResult(
        name=name,
        side=side,
        n=n,
        median_ms=median,
        p95_ms=median * 1.2,
        mad_ms=median * 0.05,
        cv=0.04,
        min_ms=median * 0.9,
        max_ms=median * 1.3,
        version="1.0.0",
    )


def _cell(algenta_ms: float, incumbent_ms: float, **kw) -> bench.CellResult:
    lanes = [
        _lane("networkx 3.4.2", bench.SIDE_INCUMBENT, incumbent_ms),
        _lane("algenta-graph", bench.SIDE_ALGENTA, algenta_ms),
    ]
    return bench.CellResult(
        status=bench.STATUS_MEASURED,
        lanes=lanes,
        ratio=incumbent_ms / algenta_ms,
        parity_label="1e-12",
        n=21,
        seed=20260919,
        load_1m=0.4,
        cpu_quota=8,
        ts_utc=TS,
        **kw,
    )


def test_fmt_ms_always_carries_a_unit():
    assert cards.fmt_ms(0.4) == "0.40 ms"
    assert cards.fmt_ms(9.999) == "10.00 ms"
    assert cards.fmt_ms(42.25) == "42.2 ms"
    assert cards.fmt_ms(189.4) == "189 ms"
    assert cards.fmt_ms(1234.5) == "1.23 s"
    assert cards.fmt_ms(12345.6) == "12.35 s"
    for bad in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            cards.fmt_ms(bad)


def test_fmt_ratio():
    assert cards.fmt_ratio(3.2) == "3.20×"
    assert cards.fmt_ratio(12.345) == "12.3×"
    assert cards.fmt_ratio(1234.5) == "1,234.5×"
    with pytest.raises(ValueError):
        cards.fmt_ratio(0.0)


def test_status_chip_kinds():
    assert cards.status_chip("live", "live") == (
        '<span class="alg-chip alg-chip-ok" data-kind="live">live</span>'
    )
    assert 'alg-chip-neutral" data-kind="measured"' in cards.status_chip("measured", TS)
    assert 'alg-chip-warn" data-kind="fallback"' in cards.status_chip("fallback", "fallback lane")
    assert 'alg-chip-err" data-kind="unavailable"' in cards.status_chip("unavailable", "gpu")
    assert "&lt;b&gt;" in cards.status_chip("live", "<b>")
    with pytest.raises(ValueError):
        cards.status_chip("simulated", "x")


def test_result_card_race_has_hero_ratio_bars_table_chips_and_footer():
    cell = _cell(algenta_ms=12.5, incumbent_ms=40.0)
    html = cards.render_result_card(
        cell,
        title="Betweenness centrality",
        subtitle="graph · 2,000 nodes",
        hardware=HW,
        transport_share=0.38,
    )
    assert html.startswith('<article class="alg-card alg-card-result">')
    assert "3.20×" in html and "faster than networkx 3.4.2" in html
    assert html.count('class="alg-lane-row"') == 2
    assert "alg-lane-bar-alg" in html and "alg-lane-bar-inc" in html
    # absolute ms for every lane: median, P95 and min–max with units
    assert "12.5 ms" in html and "40.0 ms" in html
    assert "15.0 ms" in html and "48.0 ms" in html  # P95
    assert "11.2 ms – 16.2 ms" in html and "36.0 ms – 52.0 ms" in html
    assert "<th>P95</th>" in html
    # chips: parity · seed · n · transport share · status
    assert "parity 1e-12" in html
    assert "seed 20260919" in html
    assert "n = 21" in html
    assert "transport 38%" in html
    assert 'data-kind="measured">measured 2026-09-22 14:02 UTC' in html
    # footer: hardware + UTC
    assert f"{HW} · {TS}" in html
    # the widest bar is the slowest lane and every bar is at least the floor
    assert "width:100.0%" in html
    _assert_clean_copy(html)


def test_result_card_log_bars_and_max_column_for_small_n():
    cell = _cell(algenta_ms=1.0, incumbent_ms=1000.0)
    for lane in cell.lanes:
        lane.n = 11
    cell.n = 11
    html = cards.render_result_card(cell, title="Levenshtein", hardware=HW)
    assert "<th>max</th>" in html
    assert "1,000.0×" in html
    # the fast lane is short, not invisible
    assert "width:4.0%" not in html or "width:100.0%" in html
    widths = [float(w) for w in _widths(html)]
    assert max(widths) == 100.0 and min(widths) >= cards.MIN_BAR_PERCENT
    assert widths[1] < widths[0]  # algenta bar shorter than the incumbent's


def _widths(html: str) -> list[str]:
    import re

    return re.findall(r"width:(\d+\.\d)%", html)


def test_result_card_parity_mode_shows_badge_and_not_a_race():
    cell = _cell(algenta_ms=0.4, incumbent_ms=0.5)
    html = cards.render_result_card(cell, title="z-test proportions", hardware=HW, race=False)
    assert 'class="alg-hero-badge">parity</div>' in html
    assert "not a race · 0.40 ms in-kernel" in html
    assert "faster than" not in html
    assert "×" not in html
    _assert_clean_copy(html)


def test_result_card_race_with_incumbent_faster_becomes_the_held_card():
    cell = _cell(algenta_ms=50.0, incumbent_ms=30.0)
    html = cards.render_result_card(
        cell, title="Dijkstra", hardware=HW, last_win_ts="2026-09-21 09:10 UTC"
    )
    assert "alg-card-warn" in html
    assert (
        "held: incumbent faster on this run — 50.0 ms vs 30.0 ms (networkx 3.4.2); not recorded"
        in html
    )
    assert "last recorded win on this hardware: 2026-09-21 09:10 UTC" in html
    assert "×" not in html
    _assert_clean_copy(html)


def test_held_card_rejects_a_run_we_won():
    with pytest.raises(ValueError):
        cards.render_held_card(
            title="x", algenta_ms=1.0, incumbent_ms=2.0, incumbent_name="y", hardware=HW, ts_utc=TS
        )


def test_not_recorded_card_carries_the_reason_and_no_number():
    noisy = bench.CellResult(
        status=bench.STATUS_NOISY,
        lanes=[_lane("a", bench.SIDE_ALGENTA, 12.34), _lane("b", bench.SIDE_INCUMBENT, 56.78)],
        reason="noisy — not recorded — load 4.1 on 2 vCPU",
        n=21,
        ts_utc=TS,
    )
    html = cards.render_result_card(noisy, title="BM25", hardware=HW)
    assert "noisy — not recorded" in html
    assert "12.3" not in html and "56.8" not in html and "ms" not in html.replace(HW, "")
    assert 'data-kind="unavailable">not recorded' in html
    _assert_clean_copy(html)
    with pytest.raises(ValueError):
        cards.render_not_recorded_card(_cell(1.0, 2.0), title="x", hardware=HW)


def test_unavailable_card_has_code_and_hint_and_escapes():
    html = cards.render_unavailable_card(
        title="Algenta CUDA lane",
        error_code="gpu_build_required",
        hint="This lane needs the CUDA build; the <fallback> lane answers meanwhile",
        hardware=HW,
    )
    assert "unavailable · gpu_build_required" in html
    assert "&lt;fallback&gt;" in html
    assert "alg-card-err" in html
    assert HW in html
    _assert_clean_copy(html)
    with pytest.raises(ValueError):
        cards.render_unavailable_card(title="x", error_code=" ", hint="y")


def test_result_card_validation():
    cell = _cell(1.0, 2.0)
    with pytest.raises(ValueError):
        cards.render_result_card(cell, title="x", hardware=HW, transport_share=1.5)
    only_ours = bench.CellResult(
        status=bench.STATUS_MEASURED,
        lanes=[_lane("ours", bench.SIDE_ALGENTA, 1.0)],
        n=21,
        ts_utc=TS,
    )
    with pytest.raises(ValueError):
        cards.render_result_card(only_ours, title="x", hardware=HW)
    html = cards.render_result_card(only_ours, title="x", hardware=HW, race=False)
    assert "parity</div>" in html


def test_card_css_discipline():
    _assert_stylesheet_discipline(cards.CARD_CSS)
    _assert_four_class_selectors(cards.CARD_CSS)
    assert "var(--alg-inc)" in cards.CARD_CSS
