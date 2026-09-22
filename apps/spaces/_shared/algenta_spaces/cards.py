"""Result cards — pure functions returning HTML for one measured (or held) cell.

Generalised from `apps/spaces/speed-arena/arena/card.py`: one hero figure, one
log-scaled bar per lane always labelled with its real value, chips for parity,
seed, n, transport share and status, the machine and the UTC stamp in the
footer. New here: a parity mode for cells that are not races, the
hold-and-disclose card, the unavailable card with an error code, and the
status chip whose four kinds are the only labels a result may carry.

Every user string passes through `html.escape`. No number is rendered
without its unit.
"""

from __future__ import annotations

import html
import math

from . import bench
from .bench import CellResult, LaneResult
from .css import block, rule, stylesheet

CHIP_KINDS: dict[str, str] = {
    "live": "ok",
    "measured": "neutral",
    "fallback": "warn",
    "unavailable": "err",
}

HELD_TEXT = "held: incumbent faster on this run"
NOT_RECORDED_TEXT = "not recorded"
NOT_A_RACE_TEXT = "not a race"
MIN_BAR_PERCENT = 4.0


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def fmt_ms(ms: float) -> str:
    """A duration in milliseconds with its unit, decimals shrinking as it grows."""
    if ms < 0 or math.isnan(ms) or math.isinf(ms):
        raise ValueError(f"not a duration: {ms!r}")
    if ms >= 1000:
        return f"{ms / 1000:,.2f} s"
    if ms >= 100:
        return f"{ms:,.0f} ms"
    if ms >= 10:
        return f"{ms:,.1f} ms"
    return f"{ms:,.2f} ms"


def fmt_ratio(ratio: float) -> str:
    """`3.20×` under ten, `12.4×` above."""
    if ratio <= 0 or math.isnan(ratio) or math.isinf(ratio):
        raise ValueError(f"not a ratio: {ratio!r}")
    return f"{ratio:,.1f}×" if ratio >= 10 else f"{ratio:,.2f}×"


def status_chip(kind: str, text: str) -> str:
    """One status pill. `kind` is live, measured, fallback or unavailable."""
    if kind not in CHIP_KINDS:
        raise ValueError(f"unknown chip kind {kind!r}; expected one of {sorted(CHIP_KINDS)}")
    return (
        f'<span class="alg-chip alg-chip-{CHIP_KINDS[kind]}" data-kind="{kind}">{_esc(text)}</span>'
    )


def chip(text: str, tone: str = "neutral") -> str:
    """A status/parity chip (public form used by the Space tabs)."""
    return _chip(text, tone)


def _chip(text: str, tone: str = "neutral") -> str:
    return f'<span class="alg-chip alg-chip-{tone}">{_esc(text)}</span>'


def _bar_widths(lanes: list[LaneResult]) -> dict[str, float]:
    medians = [lane.median_ms for lane in lanes]
    lo, hi = min(medians), max(medians)
    if lo <= 0:
        raise ValueError("medians must be positive")
    if math.isclose(lo, hi):
        return {lane.name: 100.0 for lane in lanes}
    log_lo = math.log10(lo) - 0.5
    log_hi = math.log10(hi)
    widths = {}
    for lane in lanes:
        frac = (math.log10(lane.median_ms) - log_lo) / (log_hi - log_lo)
        widths[lane.name] = max(MIN_BAR_PERCENT, min(100.0, 100.0 * frac))
    return widths


def _bars_html(lanes: list[LaneResult]) -> str:
    widths = _bar_widths(lanes)
    rows = []
    for lane in lanes:
        tone = "alg" if lane.side == bench.SIDE_ALGENTA else "inc"
        rows.append(
            '<div class="alg-lane-row">'
            f'<div class="alg-lane-name">{_esc(lane.name)}</div>'
            '<div class="alg-lane-track">'
            f'<div class="alg-lane-bar alg-lane-bar-{tone}"'
            f' style="width:{widths[lane.name]:.1f}%"></div>'
            "</div>"
            f'<div class="alg-lane-val">{fmt_ms(lane.median_ms)}</div>'
            "</div>"
        )
    label = "; ".join(f"{lane.name} median {fmt_ms(lane.median_ms)}" for lane in lanes)
    return (
        f'<div class="alg-lane-chart" role="img" aria-label="{_esc(label)}">'
        + "".join(rows)
        + "</div>"
    )


def _table_html(lanes: list[LaneResult]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{_esc(lane.name)}</td>"
        f"<td>{fmt_ms(lane.median_ms)}</td>"
        f"<td>{fmt_ms(lane.p95_ms)}</td>"
        f"<td>{fmt_ms(lane.min_ms)} – {fmt_ms(lane.max_ms)}</td>"
        "</tr>"
        for lane in lanes
    )
    p95_head = "P95" if all(lane.n >= bench.P95_MIN_N for lane in lanes) else "max"
    return (
        '<table class="alg-lane-table">'
        f"<thead><tr><th>lane</th><th>median</th><th>{p95_head}</th><th>min – max</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _chips_html(cell: CellResult, *, transport_share: float | None, status: tuple[str, str]) -> str:
    chips = []
    if cell.parity_label:
        chips.append(_chip(f"parity {cell.parity_label}", "ok"))
    if cell.seed is not None:
        chips.append(_chip(f"seed {cell.seed}"))
    chips.append(_chip(f"n = {cell.n}"))
    if transport_share is not None:
        if not 0.0 <= transport_share <= 1.0:
            raise ValueError("transport_share is a fraction between 0 and 1")
        chips.append(_chip(f"transport {transport_share:.0%}"))
    chips.append(status_chip(*status))
    return f'<div class="alg-chips">{"".join(chips)}</div>'


def _foot_html(hardware: str, ts_utc: str) -> str:
    return f'<div class="alg-card-foot">{_esc(hardware)} · {_esc(ts_utc)}</div>'


def render_result_card(
    cell: CellResult,
    *,
    title: str,
    hardware: str,
    subtitle: str = "",
    race: bool = True,
    transport_share: float | None = None,
    last_win_ts: str = "",
) -> str:
    """The card for one cell.

    `race=True` shows the ratio as the hero and falls back to the held card when
    the incumbent was faster; `race=False` shows a parity badge and both
    latencies, labelled "not a race". Cells that were not measured render the
    not-recorded card, which carries no number.
    """
    if not cell.measured:
        return render_not_recorded_card(cell, title=title, hardware=hardware)
    if not cell.lanes:
        raise ValueError("a measured cell has lanes")
    ours = cell.lane(bench.SIDE_ALGENTA)
    theirs = cell.lane(bench.SIDE_INCUMBENT)
    if ours is None:
        raise ValueError("a cell needs an algenta lane")

    if race:
        if theirs is None or cell.ratio is None:
            raise ValueError("a race needs an incumbent lane")
        if cell.ratio <= 1.0:
            return render_held_card(
                title=title,
                algenta_ms=ours.median_ms,
                incumbent_ms=theirs.median_ms,
                incumbent_name=theirs.name,
                hardware=hardware,
                ts_utc=cell.ts_utc,
                last_win_ts=last_win_ts,
            )
        hero = (
            f'<div class="alg-hero-num alg-accent-text">{fmt_ratio(cell.ratio)}</div>'
            f'<div class="alg-hero-label">faster than {_esc(theirs.name)}</div>'
        )
    else:
        hero = (
            '<div class="alg-hero-badge">parity</div>'
            f'<div class="alg-hero-label">{NOT_A_RACE_TEXT} · '
            f"{fmt_ms(ours.median_ms)} in-kernel</div>"
        )

    sub = f'<div class="alg-card-sub">{_esc(subtitle)}</div>' if subtitle else ""
    chips = _chips_html(
        cell, transport_share=transport_share, status=("measured", f"measured {cell.ts_utc}")
    )
    return (
        '<article class="alg-card alg-card-result">'
        '<div class="alg-card-head">'
        f'<div><h3 class="alg-card-title">{_esc(title)}</h3>{sub}</div>'
        f'<div class="alg-hero">{hero}</div>'
        "</div>"
        f"{_bars_html(cell.lanes)}"
        f"{_table_html(cell.lanes)}"
        f"{chips}"
        f"{_foot_html(hardware, cell.ts_utc)}"
        "</article>"
    )


def render_not_recorded_card(cell: CellResult, *, title: str, hardware: str) -> str:
    """A cell that did not clear the rulebook: the reason, never a number."""
    if cell.measured:
        raise ValueError("measured cells render the result card")
    return (
        '<article class="alg-card alg-card-warn">'
        f'<h3 class="alg-card-title">{_esc(title)}</h3>'
        f'<p class="alg-card-reason">{_esc(cell.reason or NOT_RECORDED_TEXT)}</p>'
        f'<div class="alg-chips">{status_chip("unavailable", NOT_RECORDED_TEXT)}</div>'
        f"{_foot_html(hardware, cell.ts_utc)}"
        "</article>"
    )


def render_held_card(
    *,
    title: str,
    algenta_ms: float,
    incumbent_ms: float,
    incumbent_name: str,
    hardware: str,
    ts_utc: str,
    last_win_ts: str = "",
) -> str:
    """Hold and disclose: the incumbent won this run; both times shown, nothing recorded."""
    if algenta_ms < incumbent_ms:
        raise ValueError("held cards are for runs the incumbent won")
    last = (
        f'<p class="alg-card-note">last recorded win on this hardware: {_esc(last_win_ts)}</p>'
        if last_win_ts
        else ""
    )
    return (
        '<article class="alg-card alg-card-warn">'
        f'<h3 class="alg-card-title">{_esc(title)}</h3>'
        f'<p class="alg-card-reason">{HELD_TEXT} — {fmt_ms(algenta_ms)} vs '
        f"{fmt_ms(incumbent_ms)} ({_esc(incumbent_name)}); {NOT_RECORDED_TEXT}</p>"
        f"{last}"
        f'<div class="alg-chips">{status_chip("measured", f"measured {ts_utc}")}</div>'
        f"{_foot_html(hardware, ts_utc)}"
        "</article>"
    )


def render_unavailable_card(*, title: str, error_code: str, hint: str, hardware: str = "") -> str:
    """A lane or feature that cannot run here: a code the runbook indexes and one hint."""
    if not error_code.strip():
        raise ValueError("error_code is empty")
    foot = f'<div class="alg-card-foot">{_esc(hardware)}</div>' if hardware else ""
    return (
        '<article class="alg-card alg-card-err">'
        f'<h3 class="alg-card-title">{_esc(title)}</h3>'
        f'<div class="alg-chips">{status_chip("unavailable", f"unavailable · {error_code}")}</div>'
        f'<p class="alg-card-reason">{_esc(hint)}</p>'
        f"{foot}"
        "</article>"
    )


# alg-card / alg-lane / alg-chip classes only, each repeated four times by
# css.rule(), tokens from design.TOKENS_CSS, spacing on the 8-pt scale.

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_BODY = "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
_MONO_NUM = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
_CELL = "text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid var(--alg-hairline);"

CARD_CSS = stylesheet(
    rule(
        "alg-card",
        "font-family: var(--alg-font); color: var(--alg-text); background: var(--alg-surface);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-card);"
        " padding: 16px 24px; box-shadow: var(--alg-shadow);",
    ),
    rule("alg-card-warn", "border-color: var(--alg-warn);"),
    rule("alg-card-err", "border-color: var(--alg-err);"),
    rule(
        "alg-card-head",
        "display: flex; justify-content: space-between; align-items: flex-start;"
        " flex-wrap: wrap; gap: 12px 24px;",
    ),
    rule(
        "alg-card-title",
        "font-size: var(--alg-title-size); line-height: var(--alg-title-line);"
        " letter-spacing: var(--alg-title-tracking); font-weight: var(--alg-title-weight);"
        " margin: 0;",
    ),
    rule("alg-card-sub", f"{_CAPTION} color: var(--alg-text-2); margin: 4px 0 0;"),
    rule("alg-hero", "text-align: right;"),
    rule(
        "alg-hero-num",
        f"{_MONO_NUM} font-size: var(--alg-display-size); line-height: var(--alg-display-line);"
        " font-weight: 600;",
    ),
    rule(
        "alg-hero-badge",
        f"display: inline-block; {_BODY} font-weight: 600; color: var(--alg-ok);"
        " border: 1px solid var(--alg-ok); border-radius: var(--alg-radius-pill);"
        " padding: 4px 16px;",
    ),
    rule("alg-hero-label", f"{_CAPTION} color: var(--alg-text-2); margin: 4px 0 0;"),
    rule("alg-lane-chart", "display: flex; flex-direction: column; gap: 8px; margin: 16px 0 8px;"),
    rule("alg-lane-row", "display: flex; align-items: center; gap: 8px;"),
    rule("alg-lane-name", f"flex: 0 0 160px; {_CAPTION} font-weight: 600;"),
    block("@media (width <= 560px)", rule("alg-lane-name", "flex-basis: 96px;")),
    rule(
        "alg-lane-track",
        "flex: 1; background: var(--alg-surface-2); border-radius: var(--alg-radius-input);"
        " height: 16px; min-width: 48px;",
    ),
    rule(
        "alg-lane-bar",
        "height: 100%; border-radius: var(--alg-radius-input);"
        " transition: width var(--alg-motion);",
    ),
    rule("alg-lane-bar-inc", "background: var(--alg-inc);"),
    rule(
        "alg-lane-bar-alg",
        "background: linear-gradient(90deg, var(--alg-accent-from), var(--alg-accent-to));",
    ),
    rule("alg-lane-val", f"flex: 0 0 96px; {_MONO_NUM} {_CAPTION} text-align: right;"),
    rule("alg-lane-table", f"width: 100%; border-collapse: collapse; {_CAPTION} margin: 8px 0;"),
    rule("alg-lane-table", f"{_CELL} color: var(--alg-text-2); font-weight: 500;", suffix=" th"),
    rule("alg-lane-table", f"{_CELL} {_MONO_NUM}", suffix=" td"),
    rule("alg-chips", "display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0;"),
    rule(
        "alg-chip",
        f"font-family: var(--alg-font-mono); {_CAPTION} padding: 4px 12px;"
        " border-radius: var(--alg-radius-pill); background: var(--alg-surface-2);"
        " border: 1px solid var(--alg-hairline); color: var(--alg-text-2);",
    ),
    rule("alg-chip-ok", "color: var(--alg-ok);"),
    rule("alg-chip-warn", "color: var(--alg-warn);"),
    rule("alg-chip-err", "color: var(--alg-err);"),
    rule("alg-card-reason", f"{_BODY} font-weight: 600; margin: 12px 0 0;"),
    rule("alg-card-note", f"{_CAPTION} color: var(--alg-text-2); margin: 4px 0 0;"),
    rule(
        "alg-card-foot",
        f"font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);"
        " margin: 12px 0 0;",
    ),
)
