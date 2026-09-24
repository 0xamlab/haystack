"""algenta_spaces.cards — result, held, not-recorded and unavailable cards, status chips."""

from __future__ import annotations

import dataclasses

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


def test_fmt_ms_always_carries_a_unit_at_three_significant_figures():
    """The final review: `MAD 0.00 ms` beside a 0.09 ms hero — a nonzero statistic printed as
    zero. Three significant figures in the unit that fits, microseconds below 0.1 ms."""
    assert cards.fmt_ms(0.4) == "0.400 ms"
    assert cards.fmt_ms(0.1217) == "0.122 ms"
    assert cards.fmt_ms(2.17) == "2.17 ms"
    assert cards.fmt_ms(9.999) == "10.00 ms"
    assert cards.fmt_ms(42.25) == "42.2 ms"
    assert cards.fmt_ms(189.4) == "189 ms"
    assert cards.fmt_ms(999.6) == "1,000 ms"
    assert cards.fmt_ms(1234.5) == "1.23 s"
    assert cards.fmt_ms(12345.6) == "12.35 s"
    # below 0.1 ms: microseconds, still three figures — never `0.00 ms` for a nonzero MAD
    assert cards.fmt_ms(0.0869) == "86.9 µs"  # the deployed hero's median
    assert cards.fmt_ms(0.018) == "18.0 µs"
    assert cards.fmt_ms(0.0045) == "4.50 µs"  # printed `0.00 ms` before
    assert cards.fmt_ms(0.0005) == "0.500 µs"
    assert cards.fmt_ms(0.09999) == "100.0 µs"
    assert cards.fmt_ms(0.0) == "0 µs", "an exact zero is a true zero, not a rounding"
    for value in (0.0045, 0.018, 0.0869, 0.1217, 0.4, 2.17, 42.25, 189.4, 1234.5):
        text = cards.fmt_ms(value)
        digits = "".join(ch for ch in text.split(" ")[0] if ch.isdigit()).lstrip("0")
        assert len(digits) >= 3, (value, text)
        assert text.endswith((" s", " ms", " µs"))
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
    # one colour rule: a state that is not a result is neutral; red is for a run failure
    assert 'alg-chip-neutral" data-kind="unavailable"' in cards.status_chip("unavailable", "gpu")
    assert 'alg-chip-neutral" data-kind="held"' in cards.status_chip("held", "held")
    assert 'alg-chip-err" data-kind="error"' in cards.status_chip("error", "parity differs")
    assert "&lt;b&gt;" in cards.status_chip("live", "<b>")
    with pytest.raises(ValueError):
        cards.status_chip("simulated", "x")


def test_chip_colour_rule_is_one_rule():
    """Neutral for unavailable / held / not configured / measured, red only for `error`."""
    red = {kind for kind, tone in cards.CHIP_KINDS.items() if tone == "err"}
    assert red == {"error"}
    for kind in ("unavailable", "held", "measured"):
        assert cards.CHIP_KINDS[kind] == "neutral", kind
    assert cards.CHIP_KINDS["live"] == "ok" and cards.CHIP_KINDS["fallback"] == "warn"
    # the not-configured card and the unavailable tile carry the same neutral pill
    card = cards.not_configured(title="Governed", hint="The tenant key is not set")
    tile = cards.tile("GPU stage", "", state="unavailable", code="gpu_status_unreachable")
    for html in (card, tile):
        assert "alg-chip-neutral alg-chip-code" in html and "alg-chip-err" not in html


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
    # absolute ms for every lane: median, MAD, CV, P95 and min–max with units (rulebook v0.3)
    assert "12.5 ms" in html and "40.0 ms" in html
    assert "0.625 ms" in html and "2.00 ms" in html  # MAD
    assert html.count('data-label="CV">4.0%</td>') == 2  # CV
    assert "15.0 ms" in html and "48.0 ms" in html  # P95
    assert "11.2 ms – 16.2 ms" in html and "36.0 ms – 52.0 ms" in html
    assert (
        "<thead><tr><th>lane</th><th>median</th><th>MAD</th><th>spread</th><th>CV</th>"
        "<th>P95</th><th>min – max</th></tr></thead>"
    ) in html
    assert html.count('data-label="MAD">') == 2 and html.count('data-label="lane">') == 2
    # chips: parity · seed · n · stability gate · transport share · status
    assert "parity 1e-12" in html
    assert "seed 20260919" in html
    assert "n = 21" in html
    # the gate reads the robust spread (1.4826 × MAD/median = 7.4% for the fixture's MAD 5%)
    assert 'data-gate="stability">stable · spread 7.4% ≤ 15%</span>' in html
    assert "transport 38%" in html
    assert f'data-kind="measured">measured {cards.time_stamp(TS)}</span>' in html
    # footer: hardware + UTC, the stamp machine-readable
    assert f'<div class="alg-card-foot">{HW} · host load 0.4 · {cards.time_stamp(TS)}</div>' in html
    assert html.count("<time ") == 2, "the measured chip and the foot; nothing else is a stamp"
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
    assert "not a race · 0.400 ms per kernel call" in html
    assert "faster than" not in html
    assert "×" not in html
    _assert_clean_copy(html)


def test_result_card_race_with_incumbent_faster_becomes_the_held_card():
    cell = _cell(algenta_ms=50.0, incumbent_ms=30.0)
    html = cards.render_result_card(
        cell, title="Dijkstra", hardware=HW, last_win_ts="2026-09-21 09:10 UTC"
    )
    assert html.startswith('<article class="alg-card alg-card-quiet" data-state="held">')
    assert "alg-card-warn" not in html, "a held run is a documented state: neutral hairline"
    assert (
        "held: incumbent faster on this run — 50.0 ms vs 30.0 ms (networkx 3.4.2); not recorded"
        in html
    )
    assert (
        f"last recorded win on this hardware: {cards.time_stamp('2026-09-21 09:10 UTC')}</p>"
    ) in html
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
        reason="noisy — not recorded — spread above 15 percent on a",
        n=21,
        ts_utc=TS,
    )
    html = cards.render_result_card(noisy, title="BM25", hardware=HW)
    assert "noisy — not recorded" in html
    assert "12.3" not in html and "56.8" not in html and "ms" not in html.replace(HW, "")
    assert 'data-kind="unavailable">not recorded' in html
    # round 2: the card drew an amber hairline around a documented state while its chip was
    # neutral — colour is for meaning, so the hairline is the neutral one and the chip speaks
    assert html.startswith('<article class="alg-card alg-card-quiet" data-state="not_recorded">')
    assert "alg-card-warn" not in html and "alg-card-err" not in html
    assert f'<div class="alg-card-foot">{HW} · {cards.time_stamp(TS)}</div>' in html
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
    # a documented state is quiet: hairline card, neutral chip, no red anywhere
    assert html.startswith('<article class="alg-card alg-card-quiet" data-state="unavailable">')
    assert "alg-card-err" not in html and "alg-chip-err" not in html
    assert "alg-chip-neutral alg-chip-code" in html
    assert HW in html
    _assert_clean_copy(html)
    with pytest.raises(ValueError):
        cards.render_unavailable_card(title="x", error_code=" ", hint="y")


def test_error_card_is_the_red_variant_for_a_failure_during_a_run():
    html = cards.render_unavailable_card(
        title="RMSNorm", error_code="parity_failed", hint="torch disagreed by 3e-2", error=True
    )
    assert html.startswith('<article class="alg-card alg-card-err" data-state="error">')
    assert (
        '<span class="alg-chip alg-chip-err alg-chip-code" data-code="parity_failed"'
        ' data-kind="unavailable">unavailable · parity_failed</span>'
    ) in html, "same DOM contract as the quiet chip, red tone"
    assert cards.render_error_card(
        title="RMSNorm", error_code="parity_failed", hint="torch disagreed by 3e-2"
    ) == cards.render_unavailable_card(
        title="RMSNorm", error_code="parity_failed", hint="torch disagreed by 3e-2", error=True
    )
    assert cards.error is cards.render_error_card
    _assert_clean_copy(html)


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


# ------------------------------------------- M2-B design system: codes, chips, tiles, states


def test_normalize_code_is_lowercase_snake_case():
    assert cards.normalize_code("HOSTED-NOT-CONFIGURED") == "hosted_not_configured"
    assert cards.normalize_code("gpu status unreachable") == "gpu_status_unreachable"
    assert cards.normalize_code("LaneTimeout") == "lane_timeout"
    assert cards.normalize_code("HTTP 429") == "http_429"
    assert cards.normalize_code(" parity_failed ") == "parity_failed"
    assert cards.normalize_code("rate__limited") == "rate_limited"
    assert cards.normalize_code("gpu_status_unreachable") == "gpu_status_unreachable"
    for bad in ("", " ", "---"):
        with pytest.raises(ValueError):
            cards.normalize_code(bad)


def test_code_chip_and_unavailable_card_normalise_and_keep_the_verifier_shape():
    chip = cards.code_chip("HOSTED-NOT-CONFIGURED")
    assert chip == (
        '<span class="alg-chip alg-chip-neutral alg-chip-code" data-code="hosted_not_configured"'
        ' data-kind="unavailable">unavailable · hosted_not_configured</span>'
    )
    red = cards.code_chip("HOSTED-NOT-CONFIGURED", error=True)
    assert red == chip.replace("alg-chip-neutral", "alg-chip-err"), "tone only; same contract"
    html = cards.render_unavailable_card(
        title="Governed", error_code="HOSTED-UNAVAILABLE", hint="x"
    )
    assert 'data-kind="unavailable">unavailable · hosted_unavailable<' in html
    assert "HOSTED-UNAVAILABLE" not in html
    assert cards.unavailable is cards.render_unavailable_card
    _assert_clean_copy(html)


def test_chip_kinds_and_default_texts():
    assert cards.chip("loading") == (
        '<span class="alg-chip alg-chip-loading" role="status" aria-live="polite"'
        ' data-kind="loading">measuring…</span>'
    )
    assert cards.chip("live") == cards.status_chip("live", "live")
    assert cards.chip("measured", "measured 2026-09-22 14:02 UTC").endswith(
        f"measured {cards.time_stamp('2026-09-22 14:02 UTC')}</span>"
    ), "a stamp inside a chip's text is a <time> element"
    assert 'alg-chip-neutral" data-kind="held"' in cards.chip("held")
    assert 'alg-chip-err" data-kind="error">error<' in cards.chip("error")
    assert set(cards.CHIP_DEFAULT_TEXT) == set(cards.CHIP_KINDS)
    with pytest.raises(ValueError):
        cards.chip("simulated")
    _assert_clean_copy(cards.chip("loading"))


# ------------------------------------------------ rulebook v0.3 on the card: MAD, CV, the gate


def test_fmt_cv_and_gate():
    assert cards.fmt_cv(0.04) == "4.0%"
    assert cards.fmt_cv(0.0) == "0.0%"
    assert cards.fmt_cv(0.15) == "15%"
    assert cards.fmt_cv(1.28) == "128%"
    assert cards.fmt_gate() == "15%" and bench.CV_MAX == 0.15
    for bad in (-0.1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            cards.fmt_cv(bad)


def test_stability_chip_reads_the_worst_lane_against_the_gate():
    lanes = [_lane("a", bench.SIDE_ALGENTA, 1.0), _lane("b", bench.SIDE_INCUMBENT, 2.0)]
    lanes[1].mad_ms = lanes[1].median_ms * 0.121 / bench.ROBUST_SCALE  # spread 12.1%
    stable = cards.stability_chip(lanes)
    assert stable == (
        '<span class="alg-chip alg-chip-neutral" data-gate="stability">'
        "stable · spread 12% ≤ 15%</span>"
    )
    lanes[1].mad_ms = lanes[1].median_ms * 0.18 / bench.ROBUST_SCALE  # spread 18%
    unstable = cards.stability_chip(lanes)
    assert 'alg-chip-warn" data-gate="stability">spread 18% above 15%</span>' in unstable
    # Codna review on #1150: the chip reads the lane's whole gate. A 50/50 alternation has MAD 0
    # (spread 0) but a mean 95 % off its median — `lane.stable` is False and the chip names what
    # failed, never `stable · spread 0.0%`; when both fail, the spread is named
    lanes[1].median_ms, lanes[1].mad_ms = 1.0, 0.0
    lanes[1].samples_ms = [1.0, 3.0] * 10 + [1.0]  # median 1.0, mean 1.952
    assert lanes[1].spread == 0.0 and lanes[1].skew > bench.CV_MAX and not lanes[1].stable
    skewed = cards.stability_chip(lanes)
    assert cards.STABLE_TEXT not in skewed
    assert (
        'alg-chip-warn" data-gate="stability">mean 95% off the median, above 15%</span>' in skewed
    )
    lanes[1].mad_ms = 0.18 / bench.ROBUST_SCALE  # spread 18% and the mean still off
    assert "spread 18% above 15%" in cards.stability_chip(lanes)
    with pytest.raises(ValueError):
        cards.stability_chip([])
    _assert_clean_copy(stable)
    _assert_clean_copy(skewed)


def test_stability_chip_and_the_noisy_reason_name_the_same_gate():
    """Codna review on #1150: `bench.run_cell` worded every noisy verdict "spread above 15
    percent" while the chip could name the mean. The reason names the gate that failed
    (`bench.noisy_reason`) and the two never disagree: a chip that says `spread` comes with a
    reason that says spread; a chip that says `mean` with one that says the mean, never the
    spread."""
    lanes = [_lane("a", bench.SIDE_ALGENTA, 1.0), _lane("b", bench.SIDE_INCUMBENT, 2.0)]
    lanes[1].mad_ms = lanes[1].median_ms * 0.18 / bench.ROBUST_SCALE  # spread 18%
    assert "spread 18% above 15%" in cards.stability_chip(lanes)
    assert bench.noisy_reason(lanes) == "noisy — not recorded — spread above 15 percent on b"
    lanes[1].mad_ms = 0.0
    lanes[1].samples_ms = [2.0, 6.0] * 10 + [
        2.0
    ]  # median 2.0, mean 3.905: the mean, not the spread
    assert "mean 95% off the median, above 15%" in cards.stability_chip(lanes)
    reason = bench.noisy_reason(lanes)
    assert reason == "noisy — not recorded — mean more than 15 percent off the median on b"
    assert "spread above" not in reason
    # both lanes noisy on different gates: the chip names the spread, the reason lists it first
    lanes[0].mad_ms = lanes[0].median_ms * 0.2 / bench.ROBUST_SCALE
    assert "spread 20% above 15%" in cards.stability_chip(lanes)
    assert bench.noisy_reason(lanes) == (
        "noisy — not recorded — spread above 15 percent on a; "
        "mean more than 15 percent off the median on b"
    )
    for lane in lanes:
        lane.mad_ms, lane.samples_ms = 0.0, []
    assert cards.STABLE_TEXT in cards.stability_chip(lanes)
    with pytest.raises(ValueError):
        bench.noisy_reason(lanes)


def test_spread_chips_carry_p95_mad_and_cv_with_units():
    lane = _lane("algenta-stats", bench.SIDE_ALGENTA, 0.13)
    chips = cards.spread_chips(lane)
    assert [c[c.index(">") + 1 : c.index("</")] for c in chips] == [
        "P95 0.156 ms",
        "MAD 6.50 µs",
        "spread 7.4%",
        "CV 4.0%",
    ]
    lane.n = 11
    assert cards.spread_chips(lane)[0].endswith(">max 0.169 ms</span>")
    for chip in chips:
        assert chip.startswith('<span class="alg-chip alg-chip-neutral">')


def test_parity_card_carries_the_table_columns_and_the_gate_too():
    cell = _cell(algenta_ms=0.4, incumbent_ms=0.5)
    html = cards.render_result_card(cell, title="z-test proportions", hardware=HW, race=False)
    assert "<th>MAD</th><th>spread</th><th>CV</th>" in html
    assert 'data-gate="stability"' in html
    assert 'data-label="min – max">0.360 ms – 0.520 ms</td>' in html


# ------------------------------------------------ rulebook v0.4 on the card: n = 21 × k calls


def test_n_chip_says_how_the_timing_was_taken():
    """`n = 21` for one call per sample; `n = 21 × 16 calls` when each sample batched 16 calls;
    per lane when a race's lanes batched differently (`n = 21 × 16 calls · algenta-text`)."""
    assert cards.calls_text(21) == "n = 21" and cards.calls_text(21, 1) == "n = 21"
    assert cards.calls_text(21, 16) == "n = 21 × 16 calls"
    assert cards.calls_text(11, 2) == "n = 11 × 2 calls"
    with pytest.raises(ValueError):
        cards.calls_text(0)
    plain = _cell(12.5, 40.0)
    assert cards.n_texts(plain) == ["n = 21"] and plain.k == 1
    assert cards.n_chips(plain) == [
        '<span class="alg-chip alg-chip-neutral" data-n="21" data-k="1">n = 21</span>'
    ]
    shared = _cell(0.09, 0.5)
    for lane in shared.lanes:
        lane.k = 23
    assert cards.n_texts(shared) == ["n = 21 × 23 calls"] and shared.k == 23
    assert cards.n_chips(shared) == [
        '<span class="alg-chip alg-chip-neutral" data-n="21" data-k="23">n = 21 × 23 calls</span>'
    ]
    mixed = _cell(0.6, 25.0)
    mixed.lanes[1].k = 4  # the algenta lane batched, nltk did not
    assert mixed.k is None
    assert cards.n_texts(mixed) == [
        "n = 21 × 1 call · networkx 3.4.2",
        "n = 21 × 4 calls · algenta-graph",
    ]
    chips = cards.n_chips(mixed)
    assert len(chips) == 2 and 'data-n="21" data-k="4">n = 21 × 4 calls · algenta-graph' in chips[1]
    # the result card prints the chip(s) in place of the old `n = 21`
    html = cards.render_result_card(shared, title="z-test", hardware=HW, race=False)
    assert "n = 21 × 23 calls" in html and html.count('data-k="23"') == 1
    assert ">n = 21<" not in html
    html = cards.render_result_card(mixed, title="Levenshtein", hardware=HW)
    assert "n = 21 × 4 calls · algenta-graph" in html and "n = 21 × 1 call · networkx" in html
    assert cards.render_result_card(plain, title="x", hardware=HW).count(">n = 21<") == 1
    for chip in chips:
        _assert_clean_copy(chip)
    # the sentence a How-measured disclosure prints, with the rulebook's figures in it
    assert cards.HOW_TIMED == (
        "each timed sample is k back-to-back calls, k chosen so that k × the warm call is at"
        " least 10 ms (at most 200; batched calls run faster than a lone warm call, so a sample"
        " usually lasts a few ms), the per-call time is the sample over k, and the card says"
        " n = 21 × k calls; the spread the stability gate reads is 1.4826 × MAD over the median,"
        " with the mean within 15% of the median (the CV is printed beside it)"
    )
    assert (
        f"{bench.SAMPLE_MIN_MS:g} ms" in cards.HOW_TIMED and str(bench.CALLS_MAX) in cards.HOW_TIMED
    )


def test_not_recorded_card_keeps_the_result_and_the_parity_chip():
    """Defect: a noisy timing dropped the z / p the visitor asked for. The value is not noisy
    — only its timing is — so the card prints the caller's result block and parity chips and
    replaces the timing rows with one quiet `not recorded` row that names the cause."""
    noisy = bench.CellResult(
        status=bench.STATUS_NOISY,
        lanes=[_lane("algenta-stats", bench.SIDE_ALGENTA, 0.0869)],
        parity_label="",
        reason="noisy — not recorded — spread above 15 percent",
        n=21,
        ts_utc=TS,
    )
    result = '<pre class="alg-result">z -1.440793230951582\np 0.1496431923825119</pre>'
    parity = [
        cards._chip("parity vs statsmodels", "ok"),
        cards._chip("z Δ ≤ 1e-09 · p Δ ≤ 1e-06"),
    ]
    html = cards.render_not_recorded_card(
        noisy,
        title="Two-proportion z-test",
        hardware=HW,
        subtitle="50 of 1,000 against 65 of 1,000",
        result_html=result,
        chips=parity,
    )
    assert html.startswith('<article class="alg-card alg-card-quiet" data-state="not_recorded">')
    assert '<div class="alg-card-sub">50 of 1,000 against 65 of 1,000</div>' in html
    assert result in html, "the kernel's answer stays on the card"
    assert "parity vs statsmodels" in html and "z Δ ≤ 1e-09" in html
    # the timing rows are one quiet row: label, the rulebook's reason, the neutral chip
    timing = html[html.index('<div class="alg-card-timing"') :]
    assert timing.startswith(
        '<div class="alg-card-timing" data-state="not_recorded">'
        '<span class="alg-card-timing-label">timing</span>'
        '<p class="alg-card-reason">noisy — not recorded — spread above 15 percent</p>'
        '<div class="alg-chips">'
    )
    assert 'data-kind="unavailable">not recorded</span></div></div>' in timing
    assert "alg-lane-table" not in html and "alg-lane-chart" not in html
    assert "0.0869" not in html and "86.9" not in html, "no timing number that was not recorded"
    assert "alg-card-warn" not in html and "alg-card-err" not in html
    assert f'<div class="alg-card-foot">{HW} · {cards.time_stamp(TS)}</div>' in html
    _assert_clean_copy(html)
    # the cell's own gate label is printed by the card itself: the race card gets it unwired
    race = bench.CellResult(
        status=bench.STATUS_NOISY,
        lanes=[
            _lane("algenta-text", bench.SIDE_ALGENTA, 0.6),
            _lane("nltk", bench.SIDE_INCUMBENT, 25),
        ],
        parity_label="exact match",
        reason="noisy — not recorded — spread above 15 percent on algenta-text",
        n=21,
        ts_utc=TS,
    )
    via_result = cards.render_result_card(
        race, title="Levenshtein distance · S", hardware=HW, subtitle="two seeded strings"
    )
    assert '<span class="alg-chip alg-chip-ok">parity exact match</span>' in via_result
    assert "two seeded strings" in via_result and "0.6" not in via_result.replace(HW, "")
    assert via_result.count("alg-chips") == 2, "the parity row and the timing row"
    # without a result or a parity label the card is the reason and the chip, as before
    bare = cards.render_not_recorded_card(noisy, title="x", hardware=HW)
    assert "alg-card-sub" not in bare and bare.count('class="alg-chips"') == 1
    # CSS: the timing row sits under a hairline on the grid, its label in the caption face
    css = cards.CARD_CSS
    row = next(ln for ln in css.splitlines() if ln.startswith(".alg-card-timing" * 4 + " {"))
    assert "border-top: 1px solid var(--alg-hairline)" in row and "margin: 16px 0 0" in row
    label = next(ln for ln in css.splitlines() if ln.startswith(".alg-card-timing-label" * 4))
    assert "var(--alg-caption-size)" in label and "color: var(--alg-text-2)" in label


def test_code_block_is_a_capped_scrolling_region_in_the_tab_order():
    """Defect 6: a 254-line engine JSON grew a 4,386 px editor because a capped CodeMirror
    scroller is outside the tab order (axe scrollable-region-focusable). The HTML block shows
    ~24 lines, scrolls inside, and is focusable with the fleet's ring."""
    lines = [f'  "key_{i}": {i},' for i in range(254)]
    code = "{\n" + "\n".join(lines) + "\n}"
    html = cards.code_block(code, "json", caption="Engine JSON")
    assert html.startswith(
        '<figure class="alg-snippet alg-code-capped" data-language="json" data-lines="256"'
        ' style="--alg-code-lines: 24">'
    )
    assert '<figcaption class="alg-snippet-caption">Engine JSON · 256 lines</figcaption>' in html
    assert (
        '<pre class="alg-snippet-code alg-code-scroll" tabindex="0" role="region"'
        ' aria-label="Engine JSON, 256 lines"><code>{\n  &quot;key_0&quot;: 0,' in html
    )
    assert html.endswith("</code></pre></figure>")
    assert html.count("key_253") == 1, "the whole text is in the page: nothing is cut"
    assert "Showing the first" not in html
    assert cards.code_block("[]", "json", max_lines=40).count("--alg-code-lines: 40") == 1
    assert 'data-lines="1"' in cards.code_block(
        "x = 1", "python"
    ) and "· 1 line<" in cards.code_block("x = 1", "python")
    assert "<b>" not in cards.code_block("<b>", "text") and "&lt;b&gt;" in cards.code_block(
        "<b>", "text"
    )
    for empty in ("", "  ", "\n"):
        with pytest.raises(ValueError):
            cards.code_block(empty, "json")
    with pytest.raises(ValueError):
        cards.code_block("x", "mojo")
    with pytest.raises(ValueError):
        cards.code_block("x", "json", max_lines=0)
    # the Copy chip's label the tab offers beside it
    assert cards.copy_label("json") == "Copy JSON" and cards.copy_label("python") == "Copy Python"
    assert cards.copy_label("bash") == "Copy command" and cards.copy_label("text") == "Copy text"
    with pytest.raises(ValueError):
        cards.copy_label("mojo")
    assert set(cards.COPY_LABELS) == set(cards.SNIPPET_LANGUAGES)
    # CSS: the <pre> is capped to --alg-code-lines mono lines plus its 8 + 12 px padding,
    # scrolls inside, and draws the 2 px accent ring inside its edge on :focus-visible
    css = cards.CARD_CSS
    scroll = next(ln for ln in css.splitlines() if ln.startswith(".alg-code-scroll" * 4 + " {"))
    assert "max-height: calc(var(--alg-code-lines, 24) * var(--alg-mono-line) + 20px)" in scroll
    assert "overflow: auto" in scroll and "box-sizing: border-box" in scroll
    ring = next(
        ln for ln in css.splitlines() if ln.startswith(".alg-code-scroll" * 4 + ":focus-visible {")
    )
    assert "outline: 2px solid var(--alg-accent-to)" in ring and "outline-offset: -2px" in ring
    assert "24 * " not in scroll.replace("var(--alg-code-lines, 24)", ""), (
        "the count is the variable"
    )
    _assert_clean_copy(html)


def test_lane_table_stacks_into_row_cards_on_a_phone():
    css = cards.CARD_CSS
    sel = ".alg-lane-table" * 4
    assert cards.TABLE_STACK_MAX_WIDTH == 560
    start = css.index(
        f"@media (width <= {cards.TABLE_STACK_MAX_WIDTH}px) {{\n  {sel} {{ display: block; }}"
    )
    phone = css[start : css.index("\n}", start)]
    assert f"{sel} thead {{ display: none; }}" in phone
    assert f"{sel} td::before {{ content: attr(data-label);" in phone
    assert "flex-direction: column" in phone and "border-radius: var(--alg-radius-input)" in phone
    assert f"{sel} td:last-child {{ border-bottom: 0; }}" in phone
    # desktop: tabular numerals in the mono face, no wrapping inside a cell
    assert f"{sel} td {{ white-space: nowrap; }}" in css
    td = next(line for line in css.splitlines() if line.startswith(f"{sel} td {{ text-align"))
    assert "tabular-nums" in td and "var(--alg-font-mono)" in td


# ------------------------------------------------------- tiles with a stamp, snippet blocks


def test_tile_stamp_is_a_time_element_with_what_and_when():
    html = cards.tile(
        "Hub kernels", "6,040 functions", "18 families loaded here", stamp="2026-09-22 14:02 UTC"
    )
    assert (
        '<div class="alg-stat-meta"><span>18 families loaded here</span>'
        '<time class="alg-stat-stamp" datetime="2026-09-22T14:02Z" data-stamp-kind="counted">'
        "counted 2026-09-22 14:02 UTC</time></div>"
    ) in html
    measured = cards.tile("GPU stage", "412 tok/s", stamp=TS, stamp_kind="measured")
    assert ">measured 2026-09-22 14:02 UTC</time>" in measured
    unavailable = cards.tile("GPU stage", "", state="unavailable", code="gpu_status_unreachable")
    assert "<time" not in unavailable, "an unavailable tile has no number, so no stamp"
    for bad in ("2026-09-22 14:02", "2026-09-22T14:02Z", "yesterday", "14:02 UTC"):
        with pytest.raises(ValueError):
            cards.tile("x", "1 ms", stamp=bad)
    with pytest.raises(ValueError):
        cards.tile("x", "1 ms", stamp=TS, stamp_kind="guessed")
    assert cards.STAMP_KINDS == ("measured", "counted", "fetched", "computed")
    assert ".alg-stat-stamp" * 4 in cards.CARD_CSS
    _assert_clean_copy(html)


def test_snippet_block_never_renders_empty_and_escapes():
    html = cards.snippet_block('from algenta import libraries\nprint("<ok>")\n', "python")
    assert html.startswith('<figure class="alg-snippet" data-language="python">')
    assert '<figcaption class="alg-snippet-caption">Python</figcaption>' in html
    assert '<pre class="alg-snippet-code"><code>from algenta import libraries\n' in html
    assert "&lt;ok&gt;" in html and "<ok>" not in html
    assert html.endswith("</code></pre></figure>")
    assert cards.snippet_block("{}", "json", caption="MCP request").count(">MCP request<") == 1
    for empty in ("", "   ", "\n\n"):
        with pytest.raises(ValueError):
            cards.snippet_block(empty, "python")
    with pytest.raises(ValueError):
        cards.snippet_block("x = 1", "mojo")
    css = cards.CARD_CSS
    for cls in ("alg-snippet", "alg-snippet-caption", "alg-snippet-code"):
        assert f".{cls}" * 4 in css, cls
    code = next(line for line in css.splitlines() if line.startswith(".alg-snippet-code" * 4))
    assert "white-space: pre-wrap" in code and "overflow-wrap: anywhere" in code
    assert "var(--alg-font-mono)" in code
    _assert_clean_copy(html)


def test_loading_card_is_the_designed_alternative_to_the_progress_chrome():
    html = cards.loading("Two-proportion z-test", "queued · 2 ahead · 1.2 s")
    assert html.startswith('<article class="alg-card alg-card-loading" aria-busy="true">')
    assert '<h2 class="alg-card-title">Two-proportion z-test</h2>' in html
    assert '<p class="alg-card-reason">queued · 2 ahead · 1.2 s</p>' in html
    assert 'data-kind="loading">measuring…</span>' in html
    assert "alg-card-reason" not in cards.loading("x")
    assert "&lt;b&gt;" in cards.loading("<b>")
    _assert_clean_copy(html)


def test_not_configured_card_is_quiet_and_normalised():
    html = cards.render_not_configured_card(
        title="Governed execution",
        hint="The tenant key is not set",
        error_code="HOSTED-NOT-CONFIGURED",
        hardware="api.algenta.ai",
    )
    assert html.startswith('<article class="alg-card alg-card-quiet" data-state="not_configured">')
    assert "unavailable · hosted_not_configured" in html
    assert "alg-card-err" not in html
    assert '<div class="alg-card-foot">api.algenta.ai</div>' in html
    assert "hosted_not_configured" in cards.not_configured(title="x", hint="y")
    assert cards.not_configured is cards.render_not_configured_card
    _assert_clean_copy(html)


def test_held_card_carries_the_held_code_chip():
    html = cards.render_held_card(
        title="Dijkstra",
        algenta_ms=50.0,
        incumbent_ms=30.0,
        incumbent_name="networkx",
        hardware=HW,
        ts_utc=TS,
    )
    assert 'data-code="incumbent_faster" data-kind="held">held · incumbent_faster</span>' in html
    assert f'data-kind="measured">measured {cards.time_stamp(TS)}</span>' in html
    assert cards.held is cards.render_held_card
    _assert_clean_copy(html)


def test_tile_states_share_one_geometry():
    ok = cards.tile("Hub kernels", "6,040 functions", "counted at boot · 2026-09-22 14:02 UTC")
    assert ok == (
        '<article class="alg-stat alg-stat-ok" data-state="ok">'
        '<div class="alg-stat-label">Hub kernels</div>'
        '<div class="alg-stat-value">6,040 functions</div>'
        '<div class="alg-stat-meta"><span>counted at boot</span>'
        '<time class="alg-stat-stamp" datetime="2026-09-22T14:02Z">2026-09-22 14:02 UTC</time>'
        "</div></article>"
    ), "the stamp a caller leaves at the end of the meta line is lifted into a <time>"
    warn = cards.tile("GPU stage", "412 tok/s", "last measured 2026-09-22 13:50 UTC", "warn")
    assert 'class="alg-stat alg-stat-warn" data-state="warn"' in warn
    unavailable = cards.tile("GPU stage", "", state="unavailable", code="gpu_status_unreachable")
    assert '<div class="alg-stat-value">—</div>' in unavailable
    assert 'data-kind="unavailable">unavailable · gpu_status_unreachable</span>' in unavailable
    with_meta = cards.tile(
        "GPU stage", "GPU-Status Unreachable", "governed-agent.hf.space", "unavailable"
    )
    assert "unavailable · gpu_status_unreachable" in with_meta
    assert "</span><span>governed-agent.hf.space</span></div>" in with_meta
    for html in (ok, warn, unavailable, with_meta):
        for part in ("alg-stat-label", "alg-stat-value", "alg-stat-meta"):
            assert html.count(f'class="{part}"') == 1, part
        _assert_clean_copy(html)
    assert cards.tile("", "1 ms", state="ok") if False else True
    with pytest.raises(ValueError):
        cards.tile("x", "1 ms", state="neutral")
    with pytest.raises(ValueError):
        cards.tile("", "1 ms")
    with pytest.raises(ValueError):
        cards.tile("x", "")
    assert "&lt;b&gt;" in cards.tile("<b>", "1 ms")


def test_time_stamp_is_the_one_way_a_card_prints_a_utc_stamp():
    assert cards.time_stamp(TS) == (
        '<time class="alg-time" datetime="2026-09-22T14:02Z">2026-09-22 14:02 UTC</time>'
    )
    assert cards.time_stamp(" 2026-09-22 14:02 UTC ") == cards.time_stamp(TS)
    assert cards.time_stamp(TS, class_name="alg-stat-stamp").startswith(
        '<time class="alg-stat-stamp" datetime="2026-09-22T14:02Z">'
    )
    for bad in ("2026-09-22 14:02", "2026-09-22T14:02Z", "yesterday", "", "<b>x</b>"):
        with pytest.raises(ValueError):
            cards.time_stamp(bad)
    assert cards.TIME_CLASS == "alg-time" and ".alg-time" * 4 in cards.CARD_CSS
    time_rule = next(
        ln for ln in cards.CARD_CSS.splitlines() if ln.startswith(".alg-time" * 4 + " {")
    )
    # Gradio's `.prose *` paints every descendant in the body colour; a stamp takes its
    # chip's or foot's tone instead (measured live: rgb(11,11,18) inside a text-2 chip)
    assert "color: inherit" in time_rule and "font: inherit" in time_rule
    assert "tabular-nums" in time_rule
    # `stamp_html` is the same parser with the kind word in front (the tiles' `stamp=` form)
    assert cards.stamp_html(TS, "measured") == (
        '<time class="alg-stat-stamp" datetime="2026-09-22T14:02Z" data-stamp-kind="measured">'
        "measured 2026-09-22 14:02 UTC</time>"
    )
    # the chip a tab draws for what was done and when
    chip = cards.stamp_chip("fetched", TS)
    assert chip == (
        '<span class="alg-chip alg-chip-neutral" data-stamp-kind="fetched">fetched '
        f"{cards.time_stamp(TS)}</span>"
    )
    with pytest.raises(ValueError):
        cards.stamp_chip("guessed", TS)
    # every chip whose text carries the fleet's stamp shape renders it as a <time>; other text
    # is escaped and left alone
    plain = cards.status_chip("live", "live <since> 2026-09-22 14:02 UTC")
    assert plain.endswith(f"live &lt;since&gt; {cards.time_stamp(TS)}</span>")
    assert cards.status_chip("live", "live").endswith('data-kind="live">live</span>')
    assert cards.split_trailing_stamp("live · hosted API · 2026-09-22 14:02 UTC") == (
        "live · hosted API",
        TS,
    )
    assert cards.split_trailing_stamp(TS) == ("", TS)
    assert cards.split_trailing_stamp("18 families loaded here") == (
        "18 families loaded here",
        "",
    )
    _assert_clean_copy(chip)


def test_text_with_times_escapes_everything_but_the_stamp_it_renders():
    """Codna review on #1150: the helper ran a pattern over escaped text and spliced raw markup
    into it. It now cuts the raw text at its stamps and escapes every other piece: a caller's
    markup never reaches the page, the `<time>` carries only the stamp's digits, and a stamp is
    one whole token — a version's or an id's digits beside it stay text."""
    stamp = cards.time_stamp(TS)
    assert cards._text_with_times(f"measured {TS}") == f"measured {stamp}"
    assert cards._text_with_times(f"live · hosted API · {TS}") == f"live · hosted API · {stamp}"
    assert cards._text_with_times(f"({TS})") == f"({stamp})"
    hostile = f'<b onmouseover="x()">{TS}</b> & "{TS}"'
    rendered = cards._text_with_times(hostile)
    assert rendered == (
        f"&lt;b onmouseover=&quot;x()&quot;&gt;{stamp}&lt;/b&gt; &amp; &quot;{stamp}&quot;"
    )
    assert rendered.count("<") == 4 == rendered.count(">"), "two <time> elements, nothing else"
    assert cards._text_with_times("") == ""
    assert cards._text_with_times("no stamp <i>") == "no stamp &lt;i&gt;"
    for glued in (f"v{TS}", f"{TS}z", f"build-{TS}", f"{TS}-1", f"1{TS}"):
        assert "<time" not in cards._text_with_times(glued), glued
        assert cards._text_with_times(glued) == cards._esc(glued)
    assert cards._chip(f"measured {TS}") == (
        f'<span class="alg-chip alg-chip-neutral">measured {stamp}</span>'
    )


def test_feet_carry_the_stamp_as_time_and_never_rewrite_the_hardware_line():
    """`hardware · <time>stamp</time>` on every card foot the cards emit; the hardware text is
    the caller's copy, escaped as it came — a stamp embedded there is not reinterpreted."""
    measured = cards.render_result_card(_cell(12.5, 40.0), title="x", hardware="Apple M3 · 8 vCPU")
    assert (  # v0.6: the machine's load average when the cell ran sits between the line and the stamp
        f'<div class="alg-card-foot">Apple M3 · 8 vCPU · host load 0.4 · {cards.time_stamp(TS)}</div>'
        in measured
    )
    unread = cards.render_result_card(
        dataclasses.replace(_cell(12.5, 40.0), load_1m=bench.LOAD_UNREAD),
        title="x",
        hardware="M3",
    )
    assert f'<div class="alg-card-foot">M3 · {cards.time_stamp(TS)}</div>' in unread, (
        "no load read, no load"
    )
    # Codna review on #1150: an idle host's 0.0 is a reading, and rulebook v0.6 discloses it;
    # only the sentinel (`bench.LOAD_UNREAD`, never a real load) leaves the foot silent
    idle = cards.render_result_card(
        dataclasses.replace(_cell(12.5, 40.0), load_1m=0.0), title="x", hardware="M3"
    )
    assert f'<div class="alg-card-foot">M3 · host load 0.0 · {cards.time_stamp(TS)}</div>' in idle
    assert bench.CellResult(status=bench.STATUS_ERROR).load_1m == bench.LOAD_UNREAD < 0
    assert cards.foot_html("M3", TS) == cards.foot_html("M3", TS, bench.LOAD_UNREAD)
    held = cards.render_held_card(
        title="x", algenta_ms=5.0, incumbent_ms=4.0, incumbent_name="y", hardware="M3", ts_utc=TS
    )
    assert f'<div class="alg-card-foot">M3 · {cards.time_stamp(TS)}</div>' in held
    # a caller's own stamp inside `hardware` stays text (the quiet cards print hardware alone)
    quiet = cards.render_not_configured_card(title="x", hint="y", hardware=f"hosted engine · {TS}")
    assert f'<div class="alg-card-foot">hosted engine · {TS}</div>' in quiet
    # a foot never fails to render over a malformed stamp: it prints what it was given
    odd = cards.render_held_card(
        title="x",
        algenta_ms=5.0,
        incumbent_ms=4.0,
        incumbent_name="y",
        hardware="M3",
        ts_utc="just now",
    )
    assert (
        '<div class="alg-card-foot">M3 · just now</div>' in odd
        and "<time" not in odd.split("alg-card-foot")[1]
    )


def test_reason_lines_are_body_copy_and_quiet_cards_share_the_hairline():
    css = cards.CARD_CSS
    reason = next(ln for ln in css.splitlines() if ln.startswith(".alg-card-reason" * 4 + " {"))
    assert "font-weight: 400" in reason and "font-weight: 600" not in reason
    assert "var(--alg-body-size)" in reason and "var(--alg-body-line)" in reason
    quiet = next(ln for ln in css.splitlines() if ln.startswith(".alg-card-quiet" * 4 + " {"))
    assert "border-color: var(--alg-hairline)" in quiet
    # `alg-card-warn` stays declared for a warning during a run, but no documented state uses it
    for html in (
        cards.render_not_recorded_card(
            bench.CellResult(status=bench.STATUS_NOISY, lanes=[], reason="noisy", n=21, ts_utc=TS),
            title="x",
            hardware=HW,
        ),
        cards.render_held_card(
            title="x", algenta_ms=5.0, incumbent_ms=4.0, incumbent_name="y", hardware=HW, ts_utc=TS
        ),
        cards.render_not_configured_card(title="x", hint="y"),
        cards.render_unavailable_card(title="x", error_code="lane_timeout", hint="y"),
    ):
        assert (
            "alg-card-quiet" in html and "alg-card-warn" not in html and "alg-card-err" not in html
        )
    assert "alg-card-err" in cards.render_error_card(
        title="x", error_code="parity_failed", hint="y"
    )


def test_chips_that_wrap_become_tags_and_a_row_centres_mixed_heights():
    """Round 2 at 375 px: `parity vs statsmodels: …` 277 × 42 px and `unavailable ·
    hosted_not_configured` 229 × 42 px — two lines inside a 999 px pill. The variant the
    head script sets (`cards.CHIP_WRAP_ATTR`) is a 12 px tag at least 44 px tall."""
    css = cards.CARD_CSS
    lines = css.splitlines()
    base = next(ln for ln in lines if ln.startswith(".alg-chip" * 4 + " {"))
    assert "border-radius: var(--alg-radius-pill)" in base
    assert "max-width: 100%" in base and "overflow-wrap: anywhere" in base, "never past the card"
    # one inline formatting context: as a flex box the chip dropped the space between the
    # text run `measured ` and the <time> beside it (rendered "measured2026-09-22 …")
    assert "display: inline-block" in base and "inline-flex" not in base
    wrap = next(
        ln for ln in lines if ln.startswith(".alg-chip" * 4 + f"[{cards.CHIP_WRAP_ATTR}] {{")
    )
    assert "border-radius: var(--alg-radius-card)" in wrap
    assert "min-height: var(--alg-target)" in wrap and "text-align: left" in wrap
    assert "padding: 8px 12px" in wrap, "two 16 px lines + 16 px on the grid + hairlines = 50 px"
    chips = next(ln for ln in lines if ln.startswith(".alg-chips" * 4 + " {"))
    assert "align-items: center" in chips and "flex-wrap: wrap" in chips
    assert cards.CHIP_WRAP_ATTR == "data-alg-wrap"


def test_hostname_token_names_a_host_or_url_in_copy():
    assert cards.hostname_token("live from api.algenta.ai · 2026-09-22 14:02 UTC") == (
        "api.algenta.ai"
    )
    assert cards.hostname_token("fetched from https://huggingface.co/api/kernels") == (
        "https://huggingface.co/api/kernels"
    )
    assert cards.hostname_token("thyn-ai-algenta.hf.space answered") == "thyn-ai-algenta.hf.space"
    for human in (
        "live · hosted API",
        "18 families loaded here · counted at boot",
        "text.fuzzy.levenshtein_distance",
        "net.url.url_encode · 0.3 ms",
        "rulebook v0.3",
    ):
        assert cards.hostname_token(human) is None, human
    # the tile lifts the trailing stamp whatever the words before it say; the words are the
    # caller's, and the caller's check is `hostname_token`
    tile = cards.tile("Hosted API + MCP", "140 MCP tools", "live · hosted API · " + TS, "ok")
    assert (
        '<div class="alg-stat-meta"><span>live · hosted API</span>'
        f"{cards.time_stamp(TS, class_name='alg-stat-stamp')}</div>"
    ) in tile
    assert cards.hostname_token("live · hosted API") is None
    # an explicit `stamp=` wins over the lift, and a meta that is only a stamp lifts whole
    both = cards.tile("x", "1 ms", "counted at boot · " + TS, stamp=TS)
    assert both.count("<time ") == 1 and "counted at boot · 2026-09-22 14:02 UTC</span>" in both
    alone = cards.tile("x", "1 ms", TS)
    assert "<span>" not in alone and alone.count("<time ") == 1
    unavailable = cards.tile("x", "", "governed-agent.hf.space · " + TS, "unavailable", code="c")
    assert (
        "<span>governed-agent.hf.space</span>" in unavailable and unavailable.count("<time ") == 1
    )


def test_empty_state_is_quiet():
    html = cards.empty(
        "No race has qualified on this hardware yet", "Every cell runs as a parity check."
    )
    assert html.startswith('<article class="alg-card alg-card-empty">')
    assert '<p class="alg-card-hint">Every cell runs as a parity check.</p>' in html
    with pytest.raises(ValueError):
        cards.empty("", "x")
    _assert_clean_copy(html)


def test_shared_table_right_aligns_numbers_and_stacks_into_dense_row_cards():
    """Round 3: the Ecosystem's five columns all left-aligned (`6,040 functions` over
    `82 functions`, digits not lining up) and 20 phone row cards of 148 px. The shared classes:
    `alg-table-num` cells right-aligned in tabular mono at a specificity above the table's own
    `td` rule; `alg-table-stack` row cards below the phone width with the lead cell first and
    44 px tall; `alg-table-dense` at 44 + 4 x 16 + 16 = 124 px for four values."""
    css = cards.CARD_CSS
    lines = css.splitlines()
    assert (cards.TABLE_CLASS, cards.TABLE_NUM_CLASS) == ("alg-table", "alg-table-num")
    assert (cards.TABLE_STACK_CLASS, cards.TABLE_LEAD_CLASS, cards.TABLE_DENSE_CLASS) == (
        "alg-table-stack",
        "alg-table-lead",
        "alg-table-dense",
    )
    table = ".alg-table" * 4
    td = next(ln for ln in lines if ln.startswith(f"{table} td {{"))
    assert "text-align: left" in td and "border-bottom: 1px solid var(--alg-hairline)" in td
    num = next(ln for ln in lines if ln.startswith(f"{table} .alg-table-num {{"))
    assert "text-align: right" in num and "tabular-nums" in num
    assert "font-family: var(--alg-font-mono)" in num and "white-space: nowrap" in num
    # (0,5,0) beats the table's `td` rule at (0,4,1) and the stack's `td` rule alike
    assert num.split(" {")[0].count(".") == 5 and td.split(" {")[0].count(".") == 4
    assert f"{table} tbody tr:last-child td {{ border-bottom: 0; }}" in css
    assert f"{table} td::before {{ content: none; }}" in css, "no label on the desktop"
    assert cards.TABLE_PHONE_MAX_WIDTH == 767
    phone = css[css.index(f"@media (width <= {cards.TABLE_PHONE_MAX_WIDTH}px) {{") :]
    phone = phone[: phone.index("\n}")]
    stack = ".alg-table-stack" * 4
    assert (
        f"{stack} {{ display: block; }}" in phone and f"{stack} thead {{ display: none; }}" in phone
    )
    row = next(ln for ln in phone.splitlines() if f"{stack} tbody tr {{" in ln)
    assert "border-radius: var(--alg-radius-card)" in row and "padding: 8px 16px" in row
    assert "background: var(--alg-surface)" in row and "margin: 0 0 8px" in row
    cell = next(ln for ln in phone.splitlines() if f"{stack} td {{" in ln)
    assert "justify-content: space-between" in cell and "text-align: right" in cell
    assert "padding: 4px 0" in cell and "border-bottom: 1px solid var(--alg-hairline)" in cell
    label = next(ln for ln in phone.splitlines() if f"{stack} td::before {{" in ln)
    assert "content: attr(data-label)" in label and "color: var(--alg-text-2)" in label
    lead = next(ln for ln in phone.splitlines() if f"{stack} .alg-table-lead {{" in ln)
    assert "order: -1" in lead and "min-height: var(--alg-target)" in lead
    assert "font-weight: 600" in lead and "text-align: left" in lead
    assert f"{stack} .alg-table-lead::before {{ content: none; }}" in phone
    dense = ".alg-table-dense" * 4
    assert f"{dense} tbody tr {{ padding: 8px 12px; }}" in phone
    assert f"{dense} td {{ padding: 0; border-bottom: 0; gap: 8px; }}" in phone
    # the dense row card: 2 x 8 px + the 44 px lead + four 16 px caption lines
    caption_line = 16
    assert 8 + 44 + 4 * caption_line + 8 == 124 < 148
    _assert_stylesheet_discipline(css)


def test_card_css_resets_prose_tables_and_declares_the_new_components():
    css = cards.CARD_CSS
    lines = css.splitlines()
    for cls, table_suffix in (
        ("alg-card", " table"),
        ("alg-lane-table", ""),
        ("alg-eco-table", ""),
        ("alg-table", ""),
    ):
        sel = f".{cls}" * 4
        table = next(line for line in lines if line.startswith(f"{sel}{table_suffix} {{"))
        assert "border: 0;" in table and "border-collapse: collapse" in table
        td = next(line for line in lines if line.startswith(f"{sel}{table_suffix} td {{"))
        assert "border: 0;" in td and "border-bottom: 1px solid var(--alg-hairline)" in td
        assert "text-align: left" in td and "tabular-nums" in td
        th = next(line for line in lines if line.startswith(f"{sel}{table_suffix} th {{"))
        assert "border: 0;" in th and "color: var(--alg-text-2)" in th
    # the card itself is never styled as a table
    card = next(line for line in lines if line.startswith(".alg-card.alg-card.alg-card.alg-card {"))
    assert "border-collapse" not in card
    assert "@keyframes alg-chip-pulse" in css and "prefers-reduced-motion: reduce" in css
    for cls in (
        "alg-stat",
        "alg-stat-label",
        "alg-stat-value",
        "alg-stat-meta",
        "alg-card-empty",
        "alg-card-hint",
        "alg-card-loading",
        "alg-card-quiet",
        "alg-chip-loading",
    ):
        assert f".{cls}" * 4 in css, cls
    stat = next(line for line in lines if line.startswith(".alg-stat.alg-stat.alg-stat.alg-stat {"))
    assert "min-height: 120px" in stat and "text-align: left" in stat
    value = next(line for line in lines if line.startswith(".alg-stat-value" * 4 + " {"))
    assert "var(--alg-title-size)" in value and "tabular-nums" in value
    _assert_stylesheet_discipline(css)
    _assert_four_class_selectors(css)
