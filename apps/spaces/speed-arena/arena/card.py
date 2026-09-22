"""Result card rendering — one self-contained HTML card per duel run.

Layout budget (mechanics checklist): one hero number, one bar chart, chips
for parity / config / seed / hardware, parseable in under 10 seconds. Bars
are log-scaled (ratios can be 100x+) and always labeled with real values.
"""

from __future__ import annotations

import html
import math

from arena.harness import HARNESS_URL, DuelOutcome

SPACE_URL = "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"


def _fmt_time(seconds: float) -> str:
    if seconds >= 1:
        return f"{seconds:,.2f} s"
    if seconds >= 1e-3:
        return f"{seconds * 1e3:,.2f} ms"
    return f"{seconds * 1e6:,.1f} µs"


def _chip(text: str, kind: str = "") -> str:
    return f'<span class="chip {kind}">{html.escape(text)}</span>'


def render_card(outcome: DuelOutcome, duel, divider: float = 1.0, divided_label: str = "") -> str:
    if outcome.status != "ok":
        return render_held(outcome)

    e = html.escape
    lanes = outcome.lanes
    t_max = max(t.warm_median_s for t in lanes)
    log_lo = math.log10(min(t.warm_median_s for t in lanes)) - 0.5
    log_hi = math.log10(t_max) + 0.05

    def width(t: float) -> float:
        frac = (math.log10(t) - log_lo) / (log_hi - log_lo)
        return max(4.0, min(100.0, 100.0 * frac))

    bars = []
    for t in lanes:
        cls = "alg" if t.side == "algenta" else "inc"
        bars.append(
            f'<div class="lane-row">'
            f'<div class="lane-name">{e(t.name)}</div>'
            f'<div class="lane-barwrap"><div class="lane-bar {cls}" style="width:{width(t.warm_median_s):.1f}%"></div></div>'
            f'<div class="lane-val">{_fmt_time(t.warm_median_s)}</div></div>'
        )

    rows = []
    for t in lanes:
        spread = f"{_fmt_time(t.warm_min_s)} – {_fmt_time(t.warm_max_s)}"
        per_item = f"<td>{_fmt_time(t.warm_median_s / divider)}</td>" if divider > 1.0 else ""
        rows.append(
            f"<tr><td>{e(t.name)}</td><td>{_fmt_time(t.cold_s)}</td>"
            f"<td>{_fmt_time(t.warm_median_s)}</td><td>{spread}</td>{per_item}</tr>"
        )
    per_item_head = f"<th>per {e(divided_label)}</th>" if divider > 1.0 else ""

    chips = "".join(
        [
            _chip(f"✓ parity: {outcome.parity_label}", "ok"),
            _chip(f"seeded corpus: {outcome.seed_note}"),
            _chip(f"median of {lanes[0].runs} warm + cold first call"),
            _chip(f"unit: {outcome.unit_label}"),
        ]
        + ([_chip(outcome.native_backend)] if outcome.native_backend else [])
    )
    config_html = (
        f'<div class="card-config"><b>configs (R7):</b> {e(outcome.config_note)}<br>'
        f"<b>setup:</b> {e(outcome.setup_note)}</div>"
    )
    swept_html = ""
    if outcome.swept_from:
        variant = f" · {e(duel.variant)}" if getattr(duel, "variant", "") else ""
        swept_html = f'<div class="card-config">configuration: {e(outcome.size_key)}{variant}</div>'
    lane_cfgs = "".join(f"<li><b>{e(t.name)}:</b> {e(t.config)}</li>" for t in lanes if t.config)

    return f"""
<div class="duel-card">
  <div class="duel-head">
    <div>
      <div class="duel-title">{e(outcome.duel_title)}</div>
      <div class="duel-sub">{e(outcome.size_label)} · measured live {e(outcome.timestamp)}</div>
    </div>
    <div class="hero">
      <div class="hero-num">{outcome.hero_speedup:,.2f}×</div>
      <div class="hero-label">faster — {e(outcome.hero_label.split("× ", 1)[-1])}</div>
    </div>
  </div>
  <div class="lane-chart">{"".join(bars)}</div>
  <div class="chart-note">warm median, log scale · {e(outcome.metric_label)}</div>
  <table class="lane-table">
    <tr><th>lane</th><th>cold first call</th><th>warm median</th><th>warm min–max</th>{per_item_head}</tr>
    {"".join(rows)}
  </table>
  <div class="chips">{chips}</div>
  {swept_html}
  {config_html}
  <details class="card-details"><summary>lane configs, harness and hardware (R4/R7/R9)</summary>
    <ul>{lane_cfgs}</ul>
    <div class="card-hw">{e(outcome.hardware)}<br>
    harness: <a href="{HARNESS_URL}">mojo-kernels benchmarks + this Space's arena/ source</a> ·
    ran in {outcome.elapsed_s:,.1f}s wall</div>
  </details>
</div>"""


def render_fallback(entry: dict, rematch_note: str) -> str:
    """The most recent winning leaderboard entry for a duel, honestly labeled.

    Honesty invariant: every number shown comes from a recorded leaderboard
    entry with its real measurement timestamp and hardware — never a fresh
    loss, never a relabeled run.
    """
    e = html.escape
    hero = entry.get("hero_speedup") or 0.0
    chips = "".join(
        [
            _chip(f"✓ parity: {entry.get('parity', '')}", "ok"),
            _chip("leaderboard entry — measured, never canned"),
        ]
    )
    return f"""
<div class="duel-card fallback">
  <div class="duel-head">
    <div>
      <div class="duel-title">{e(entry.get("duel", ""))}</div>
      <div class="duel-sub">{e(entry.get("size_label", ""))} · last measured {e(entry.get("ts", ""))}</div>
    </div>
    <div class="hero">
      <div class="hero-num">{hero:,.2f}×</div>
      <div class="hero-label">faster — {e((entry.get("hero_label", "")).split("× ", 1)[-1])}</div>
    </div>
  </div>
  <div class="chips">{chips}</div>
  <div class="card-config">last measured {e(entry.get("ts", ""))} — {e(rematch_note)}</div>
  <div class="card-hw">{e(entry.get("hardware", ""))}</div>
</div>"""


def render_held(outcome: DuelOutcome) -> str:
    """Error card — shown only when a duel cannot run at all (never a loss)."""
    e = html.escape
    kind = "warn" if outcome.status == "held" else "error"
    gate = (
        f'<div class="card-config"><b>gate detail:</b> {e(outcome.gate_detail)}</div>'
        if outcome.gate_detail
        else ""
    )
    return f"""
<div class="duel-card {kind}">
  <div class="duel-title">Duel could not run: {e(outcome.duel_title)}</div>
  <div class="duel-sub">{e(outcome.size_label)} · {e(outcome.timestamp)}</div>
  <div class="card-reason">{e(outcome.held_reason)}</div>
  {gate}
  <div class="card-config">No numbers are shown for a run that could not be verified.</div>
  <div class="card-hw">{e(outcome.hardware)}</div>
</div>"""


def render_placeholder(text: str) -> str:
    return (
        f'<div class="duel-card placeholder"><div class="duel-sub">{html.escape(text)}</div></div>'
    )


def share_text(outcome: DuelOutcome) -> str:
    if outcome.status != "ok":
        return ""
    return (
        f"⚡ {outcome.duel_title}: the Algenta Mojo kernel ran {outcome.hero_speedup:,.2f}× faster "
        f"— {outcome.hero_label} — measured LIVE just now on a free HF cpu-basic Space "
        f"(parity ✓ {outcome.parity_label}; median-of-5 warm + cold; seeded corpus). "
        f"Run the same duel yourself: {SPACE_URL}"
    )
