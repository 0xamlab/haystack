"""Result cards — pure functions returning HTML for one measured (or held) cell.

Generalised from `apps/spaces/speed-arena/arena/card.py`: one hero figure, one
log-scaled bar per lane always labelled with its real value, chips for parity,
seed, n, transport share and status, the machine and the UTC stamp in the
footer. New here: a parity mode for cells that are not races, the
hold-and-disclose card, the unavailable card with an error code, and the
status chip whose kinds are the only labels a result may carry.

Every user string passes through `html.escape`. No number is rendered
without its unit.

The API the tabs build on (M2-B design system)
----------------------------------------------
* `chip(kind, text=None)` — one status pill; kinds `live`, `measured`,
  `fallback`, `unavailable`, `held`, `error`, `loading`. `chip("loading")`
  reads "measuring…" with a pulsing accent dot (still under reduced motion).
  `status_chip(kind, text)` is the same pill with the text required.

  The colour rule (one rule, `CHIP_KINDS`): a state that is not a result —
  `unavailable`, `not_configured`, `held`, not recorded — is neutral, `text-2`
  on `surface-2`, the same pill as `measured` and `n = 21`. Red (`err`) is for
  `error` alone: something failed *during a run* (a parity check that did not
  agree, a call that raised). `live` is green, `fallback` is amber. A tile or a
  card in a documented state therefore never shows red, and the same fact
  (`hosted_not_configured`, `gpu_status_unreachable`) reads the same on every
  tab. The card around such a state follows the same rule: the not-recorded and
  held cards draw the neutral hairline (`alg-card-quiet`, `data-state=
  "not_recorded"` / `"held"`) and let the chip text carry the state — colour is
  for meaning, and "the rulebook did not record this run" is a fact, not a
  warning. Only `alg-card-err` (a failure during a run) colours a hairline.
* Chips wrap honestly on a phone. A pill whose text needs two lines at 375 px
  gets `CHIP_WRAP_ATTR` (`data-alg-wrap`) from `shell.CHIP_WRAP_SCRIPT` — the
  attribute is set from the chip's measured line boxes, never guessed — and the
  variant in `CARD_CSS` turns the 999 px pill into a 12 px tag, 44 px tall or
  more, left-aligned, so no text ever sits inside a half-circle. A chip that
  fits on one line is untouched (26 px pill), and `.alg-chips` centres a row of
  mixed heights.
* Every UTC stamp a card prints is a `<time>` element. `time_stamp(utc_str)`
  renders `<time class="alg-time" datetime="2026-09-22T14:02Z">2026-09-22 14:02
  UTC</time>`; the result, held and not-recorded feet (`hardware · <time>`), the
  `measured <UTC>` chips (any chip text carrying the fleet's stamp shape), the
  held card's last-win note, the boot card's finish and the tiles' stamps all go
  through it, so what a reader sees as a stamp a machine reads as a datetime.
  Text a caller supplies as prose (`hardware`, `hint`, `reason`) is escaped and
  left alone: cards never rewrite a caller's copy.
* A tile's meta line names the provenance in words, never a host. `hostname_token
  (text)` names the first hostname or URL in a string (`api.algenta.ai`,
  `https://…`); the rule for callers is "live · hosted API", with the host in the
  Reproduce disclosure. The UTC stamp a caller leaves at the end of the meta
  (`… · 2026-09-22 14:02 UTC`) is lifted into the tile's `<time>` element.
* `normalize_code(code)` — every error code the fleet prints is lowercase
  snake_case: `HOSTED-NOT-CONFIGURED` -> `hosted_not_configured`,
  `LaneTimeout` -> `lane_timeout`. `code_chip(code)` renders it as
  `unavailable · <code>` with `data-code`, the one convention for every card;
  `code_chip(code, error=True)` is the same pill in red for a run failure.
  The DOM contract the verifier reads (`data-kind="unavailable">unavailable ·
  <code>`) is identical in both tones, so a documented state and a failure
  are told apart by colour on the page and by the code in a check.
* `unavailable(title=, error_code=, hint=, hardware=, error=False)`,
  `held(title=, algenta_ms=, …)` and `not_configured(title=, hint=, …)` are
  the cards for states that are not results; each normalises its code. The
  unavailable card is quiet (hairline, neutral chip); `error=True` draws the
  red hairline and the red chip for a failure during a run.
  (`render_unavailable_card` / `render_held_card` /
  `render_not_configured_card` are the same functions under their long names.)
* `loading(title, detail)` — the card a handler returns first, so the stock
  progress chrome (hidden by `css.CHROME_CSS`) is never missed: the title, the
  lane position or ETA as `detail`, and the loading chip. A generator handler
  yields it, then the result; a plain handler pairs it with a `.then()`.
* `tile(label, value, meta="", state="ok", code="", stamp="", stamp_kind="counted")`
  — one statistic on the page's KPI geometry: 12/16 caption label, 28/34
  tabular value, a 12 px meta line for the unit and provenance, states `ok` /
  `warn` / `unavailable` on identical geometry (an unavailable tile shows an em
  dash and the code chip in the meta line). A number that was measured or
  counted carries its UTC stamp: `stamp="2026-09-22 14:02 UTC"` renders a
  `<time>` reading `counted 2026-09-22 14:02 UTC` (or `measured`, `fetched`,
  `computed` — `STAMP_KINDS`) after the meta text. The Try tab's "Where this
  runs" row and the LLM GPU tile share it.
* `empty(title, hint)` — the quiet empty state: dashed hairline, muted text,
  no red.
* `snippet_block(code, language)` — a snippet inside a `gr.HTML` payload: a
  language caption and a `<pre>` on `surface-2` in the mono face, wrapping,
  never scrolling the page. It refuses empty code: an editor never renders
  empty. For a `gr.Code` a handler fills later, pass
  `elem_classes=[css.SNIPPET_EDITOR_CLASS]` and `css.CODE_CSS` hides the block
  until the first value lands (see `css.py`).
* `code_block(code, language, caption=, max_lines=24)` — the same snippet for a
  LONG payload (the Governed tab's engine JSON, 254 lines): the whole text is in
  the page, the `<pre>` shows `max_lines` lines and scrolls inside, and the
  region is in the tab order — `tabindex="0"`, `role="region"` with the caption
  and the line count as its name (`Engine JSON, 254 lines`), the fleet's 2 px
  accent ring drawn inside its edge on `:focus-visible` — so axe's
  `scrollable-region-focusable` stays at 0. The caption carries the line count
  (`Engine JSON · 254 lines`). No cap note is needed: nothing is cut. Beside it
  the tab offers `gr.Button(copy_label(language), elem_classes=["alg-chip-btn"])`
  (`Copy JSON`) wired to the full text, the fleet's 44 px Copy chip. A read-only
  `gr.Code` cannot be this block: CodeMirror gives a non-editable document no
  `tabindex`, so a capped `.cm-scroller` is a scrollable region outside the tab
  order (the round-3 axe finding that led to the uncapped 200-line editor).
* Copy buttons: the tabs pass `buttons=[]` to `gr.Code` / `gr.Dataframe` and
  `show_copy_button=False` to `gr.Textbox`, and offer a 44 px Copy chip
  (`gr.Button(elem_classes=["alg-chip-btn"])`); the stock 18 px icons are
  hidden by `css.CHROME_CSS` either way.
* Tables inside any `alg-card` (and `.alg-eco-table`) draw hairline row
  separators only — no vertical rules, left-aligned, tabular numerals — so
  Gradio's prose borders never show through.
* The shared table a tab draws for itself (`TABLE_CLASS`, `alg-table` on the
  `<table>`): the same hairline rows in the caption face, and **numbers read
  as numbers** — every numeric `<th>` / `<td>` carries `TABLE_NUM_CLASS`
  (`alg-table-num`): right-aligned, mono, tabular numerals, one line (round 3
  found the Ecosystem's five columns all left-aligned, `6,040 functions` under
  `82 functions` with the digits not lining up). With `TABLE_STACK_CLASS`
  (`alg-table-stack`) the table becomes one row card per row below
  `css.PHONE_MAX_WIDTH`, each cell a `label · value` line from its `data-label`,
  the row's name cell (`TABLE_LEAD_CLASS`, `alg-table-lead`) first and 44 px tall
  for its link; `TABLE_DENSE_CLASS` (`alg-table-dense`) beside it is the denser
  phone row card for a long table — no cell hairlines, no cell padding, 8 px
  around: the 44 px lead plus four 16 px value lines is 124 px, against the
  148 px card measured on the Ecosystem's twenty rows (2,960 px of page).
  Every colour is a token; `_table_rules` is the one source of the cell rule.

Rulebook v0.4 on the result card
--------------------------------
The lane table (`_table_html`) prints every statistic the rulebook records per
lane: median, MAD, spread, CV, P95 (N >= 20, else max) and min – max, each with
its unit (`fmt_ms`, `fmt_cv`), in tabular numerals with hairline separators.
Below 560 px the table becomes one row card per lane (`data-label` on every
cell). The chips carry the stability gate: `stable · spread 4.0% ≤ 15%`
(`data-gate="stability"`) when every lane is stable — its spread and its
mean/median gap both inside `bench.CV_MAX`, `LaneResult.stable` — else the amber
`spread 18% above 15%`, or `mean 22% off the median, above 15%` when the spread
cleared and the mean did not. `spread_chips(lane)` gives a tab that draws its
own card (the Try hero) the same P95 · MAD · spread · CV chips.

`fmt_ms` is adaptive: three significant figures in the unit that fits — `1.23 s`,
`189 ms`, `42.2 ms`, `2.17 ms`, `0.122 ms`, and microseconds below 0.1 ms
(`86.9 µs`, `18.0 µs`, `4.50 µs`) — so a MAD of 0.0045 ms reads `4.50 µs`, never
`0.00 ms` (the final review's finding beside a 0.09 ms hero). An exact zero is
`0 µs`. Every ms a card prints goes through it.

The n chip says how the timing was taken (rulebook v0.4, `bench.calls_per_sample`):
`n = 21` when each sample was one call, `n = 21 × 61 calls` when each of the 21
interleaved samples was 61 back-to-back calls (so a sample lasts ≥ 10 ms; the
figures are per call). When a race's lanes batched differently the chip is per
lane: `n = 21 × 16 calls · algenta-text`, `n = 21 × 1 call · nltk`.
`n_texts(cell)` / `n_chips(cell)` give a tab that draws its own card the same
words; `HOW_TIMED` is the sentence for a How-measured disclosure.

The not-recorded card keeps the result. A run whose timing did not clear the
gate still ran the kernel and the parity check — the value is not noisy, only
its timing is — so `render_not_recorded_card(cell, …, result_html=, chips=,
subtitle=)` prints the caller's result block and parity chips and replaces the
timing rows (bars, table, P95 · MAD · CV) with one quiet `alg-card-timing` row
carrying the rulebook's reason and the neutral `not recorded` chip. The parity
chip the cell's own gate produced (`cell.parity_label`) is printed by the card
itself, so the race card gets it with no wiring. Same hairline, same
`data-state="not_recorded"`, no number that was not recorded.
"""

from __future__ import annotations

import html
import math
import re

from . import bench
from .bench import CellResult, LaneResult
from .css import (
    CODE_CAPPED_CLASS,
    CODE_LINES_DEFAULT,
    CODE_LINES_VAR,
    CODE_SCROLL_CLASS,
    PHONE_MAX_WIDTH,
    block,
    rule,
    stylesheet,
)

# kind -> tone. Neutral for every state that is not a result; red for a failure during a run.
CHIP_KINDS: dict[str, str] = {
    "live": "ok",
    "measured": "neutral",
    "fallback": "warn",
    "unavailable": "neutral",
    "held": "neutral",
    "error": "err",
    "loading": "loading",
}
CHIP_DEFAULT_TEXT: dict[str, str] = {
    "live": "live",
    "measured": "measured",
    "fallback": "fallback",
    "unavailable": "unavailable",
    "held": "held",
    "error": "error",
    "loading": "measuring…",
}
ERROR_TONE = "err"
TILE_STATES: tuple[str, ...] = ("ok", "warn", "unavailable")
#: What a tile's UTC stamp says the number is: measured, counted, fetched or computed then.
STAMP_KINDS: tuple[str, ...] = ("measured", "counted", "fetched", "computed")
#: The fleet's stamp shape (`runtime.utc_stamp`): `2026-09-22 14:02 UTC`.
UTC_STAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC$")
#: The same shape as one whole token inside a chip's text (bounded by the fleet's ` · `, a space
#: or the text's ends — the digits of a version or an id beside it never make one), so
#: `measured 2026-09-22 14:02 UTC` renders its stamp as a `<time>` element.
_UTC_STAMP_IN_TEXT_RE = re.compile(r"(?<![\w-])(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC(?![\w-])")
#: The class every `<time>` element a card prints carries (the tiles' stamp keeps its own).
TIME_CLASS = "alg-time"
#: Set by `shell.CHIP_WRAP_SCRIPT` on a chip whose text takes more than one line.
CHIP_WRAP_ATTR = "data-alg-wrap"
#: A hostname (`api.algenta.ai`, `huggingface.co`, `thyn-ai-algenta.hf.space`) or a URL in
#: copy — machine names that belong in the Reproduce disclosure, not in a tile's meta line.
_HOSTNAME_RE = re.compile(
    r"https?://\S+"
    r"|\b(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:ai|app|cloud|co|com|dev|io|net|org|space)\b",
    re.IGNORECASE,
)
#: Languages `snippet_block` labels: id -> caption.
SNIPPET_LANGUAGES: dict[str, str] = {
    "python": "Python",
    "json": "JSON",
    "bash": "Shell",
    "text": "Text",
}
#: The Copy chip's label beside a code block, per language: `Copy JSON`, `Copy Python`.
COPY_LABELS: dict[str, str] = {
    "python": "Copy Python",
    "json": "Copy JSON",
    "bash": "Copy command",
    "text": "Copy text",
}
#: Rulebook v0.4's one sentence for a How-measured disclosure, with the figures filled in.
HOW_TIMED = (
    f"each timed sample is k back-to-back calls, k chosen so that k × the warm call is at least "
    f"{bench.SAMPLE_MIN_MS:g} ms (at most {bench.CALLS_MAX}; batched calls run faster than a lone "
    f"warm call, so a sample usually lasts a few ms), the per-call time is the sample over k, "
    f"and the card says n = {bench.REPEATS_FAST} × k calls; the spread the stability gate reads "
    f"is {bench.ROBUST_SCALE} × MAD over the median, with the mean within {bench.CV_MAX:.0%} of "
    f"the median (the CV is printed beside it)"
)
#: The not-recorded card's timing row, in place of the bars and the table.
TIMING_LABEL = "timing"

HELD_TEXT = "held: incumbent faster on this run"
HELD_CODE = "incumbent_faster"
NOT_RECORDED_TEXT = "not recorded"
NOT_A_RACE_TEXT = "not a race"
NOT_CONFIGURED_CODE = "hosted_not_configured"
UNAVAILABLE_PREFIX = "unavailable · "
STABLE_TEXT = "stable"
EMPTY_VALUE = "—"
MIN_BAR_PERCENT = 4.0
#: Below this width the lane table is one row card per lane.
TABLE_STACK_MAX_WIDTH = 560
#: The shared table (module docstring): the table, its numeric cells, the phone row cards, the
#: row's name cell and the denser row card. A tab puts them on its own markup.
TABLE_CLASS = "alg-table"
TABLE_NUM_CLASS = "alg-table-num"
TABLE_STACK_CLASS = "alg-table-stack"
TABLE_LEAD_CLASS = "alg-table-lead"
TABLE_DENSE_CLASS = "alg-table-dense"
#: Below this width `alg-table-stack` is one row card per row (the phone).
TABLE_PHONE_MAX_WIDTH = PHONE_MAX_WIDTH

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_WORD_RE = re.compile(r"[^A-Za-z0-9]+")


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _parse_stamp(stamp: object) -> tuple[str, str]:
    """`("2026-09-22", "14:02")` from the fleet's stamp, or ValueError naming the shape."""
    match = UTC_STAMP_RE.match(str(stamp).strip())
    if match is None:
        raise ValueError(f"not a UTC stamp (YYYY-MM-DD HH:MM UTC): {stamp!r}")
    day, clock = match.groups()
    return day, clock


def time_stamp(stamp: object, *, class_name: str = TIME_CLASS) -> str:
    """`<time class="alg-time" datetime="2026-09-22T14:02Z">2026-09-22 14:02 UTC</time>`.

    The one way a card prints a UTC stamp: what the reader sees is the fleet's stamp, what a
    machine reads is the datetime. Anything that is not a stamp raises ValueError."""
    day, clock = _parse_stamp(stamp)
    return f'<time class="{class_name}" datetime="{day}T{clock}Z">{day} {clock} UTC</time>'


def _time_or_text(value: object) -> str:
    """A stamp as a `<time>` element; text that is not one, escaped as it came (a foot never
    fails to render because a caller's stamp was malformed — it prints what it was given)."""
    try:
        return time_stamp(value)
    except ValueError:
        return _esc(value)


def _text_with_times(text: object) -> str:
    """Escaped text with every embedded fleet stamp rendered as a `<time>` element.

    The raw text is cut at its stamps first and every other piece is escaped, so no pattern
    runs over escaped markup and nothing a caller wrote reaches the page unescaped: the `<time>`
    element carries only the stamp's own digits (`time_stamp`), and a stamp is one whole token —
    the digits of a version or an id beside it stay text (Codna review on #1150)."""
    raw = str(text)
    parts: list[str] = []
    last = 0
    for match in _UTC_STAMP_IN_TEXT_RE.finditer(raw):
        parts.append(_esc(raw[last : match.start()]))
        parts.append(time_stamp(match.group(0)))
        last = match.end()
    parts.append(_esc(raw[last:]))
    return "".join(parts)


def split_trailing_stamp(text: str) -> tuple[str, str]:
    """`("live · hosted API", "2026-09-22 14:02 UTC")` from `live · hosted API · 2026-09-22
    14:02 UTC`; `(text, "")` when the text does not end in a stamp. The separator is the
    fleet's ` · `; a stamp standing alone gives `("", stamp)`."""
    head, sep, tail = str(text).rpartition(" · ")
    if sep and UTC_STAMP_RE.match(tail.strip()):
        return head.strip(), tail.strip()
    if UTC_STAMP_RE.match(str(text).strip()):
        return "", str(text).strip()
    return str(text), ""


def hostname_token(text: str) -> str | None:
    """The first hostname or URL in `text`, or None: `live from api.algenta.ai · …` ->
    `api.algenta.ai`. A tile's meta line and any other primary copy carries none; the host
    belongs in the Reproduce disclosure."""
    match = _HOSTNAME_RE.search(text)
    return match.group(0) if match else None


def _three_figures(value: float) -> str:
    """`value` in [0, 1000) to three significant figures: `189`, `42.2`, `2.17`, `0.500`."""
    if value >= 100:
        return f"{value:,.0f}"
    if value >= 10:
        return f"{value:.1f}"
    if value >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def fmt_ms(ms: float) -> str:
    """A duration with its unit at three significant figures: the unit that fits the figure.

    `1.23 s` from 1,000 ms; `189 ms`, `42.2 ms`, `2.17 ms`, `0.122 ms` down to 0.1 ms;
    microseconds below that (`86.9 µs`, `18.0 µs`, `4.50 µs`, `0.500 µs`), so a MAD of
    0.0045 ms is `4.50 µs`, never `0.00 ms`. An exact zero is `0 µs`. Rounding may carry a
    figure over its decade (`9.999 ms` -> `10.00 ms`): the unit is chosen first, the decimals
    from the figure as given, so a value never loses a digit it had."""
    if ms < 0 or math.isnan(ms) or math.isinf(ms):
        raise ValueError(f"not a duration: {ms!r}")
    if ms == 0:
        return "0 µs"
    if ms >= 1000:
        return f"{ms / 1000:,.2f} s"
    if ms >= 0.1:
        return f"{_three_figures(ms)} ms"
    return f"{_three_figures(ms * 1000)} µs"


def fmt_ratio(ratio: float) -> str:
    """`3.20×` under ten, `12.4×` above."""
    if ratio <= 0 or math.isnan(ratio) or math.isinf(ratio):
        raise ValueError(f"not a ratio: {ratio!r}")
    return f"{ratio:,.1f}×" if ratio >= 10 else f"{ratio:,.2f}×"


def fmt_cv(cv: float) -> str:
    """A coefficient of variation as a percentage: `4.0%`, `15%` at the gate, `128%` beyond."""
    if cv < 0 or math.isnan(cv) or math.isinf(cv):
        raise ValueError(f"not a coefficient of variation: {cv!r}")
    return f"{cv:.0%}" if cv >= 0.1 else f"{cv:.1%}"


def fmt_gate(cv_max: float = bench.CV_MAX) -> str:
    """The stability gate as printed: `15%`."""
    return f"{cv_max:.0%}"


def normalize_code(code: object) -> str:
    """The fleet's one spelling for an error code: lowercase snake_case.

    `HOSTED-NOT-CONFIGURED` -> `hosted_not_configured`, `LaneTimeout` -> `lane_timeout`,
    `gpu status unreachable` -> `gpu_status_unreachable`, `HTTP 429` -> `http_429`.
    Raises ValueError when nothing is left.
    """
    text = _CAMEL_RE.sub("_", str(code).strip())
    text = _NON_WORD_RE.sub("_", text).strip("_").lower()
    if not text:
        raise ValueError(f"error code is empty: {code!r}")
    return text


def _status_chip(kind: str, text: str, tone: str, code: str | None) -> str:
    classes = f"alg-chip alg-chip-{tone}"
    attrs = ""
    if code:
        classes += " alg-chip-code"
        attrs = f' data-code="{_esc(code)}"'
    if kind == "loading":
        attrs += ' role="status" aria-live="polite"'
    return f'<span class="{classes}"{attrs} data-kind="{kind}">{_text_with_times(text)}</span>'


def status_chip(kind: str, text: str, *, code: str | None = None) -> str:
    """One status pill. `kind` is live, measured, fallback, unavailable, held, error or loading.

    The tone follows `CHIP_KINDS`: neutral for every state that is not a result, red for
    `error` alone. `code` adds `data-code` and the `alg-chip-code` class; `data-kind` stays
    the last attribute so `data-kind="unavailable">unavailable · <code>` reads the code back.
    A fleet stamp in the text (`measured 2026-09-22 14:02 UTC`) renders as a `<time>`.
    """
    if kind not in CHIP_KINDS:
        raise ValueError(f"unknown chip kind {kind!r}; expected one of {sorted(CHIP_KINDS)}")
    return _status_chip(kind, text, CHIP_KINDS[kind], code)


def chip(kind: str, text: str | None = None) -> str:
    """`status_chip` with the kind's default text: `chip("loading")` reads "measuring…"."""
    if kind not in CHIP_KINDS:
        raise ValueError(f"unknown chip kind {kind!r}; expected one of {sorted(CHIP_KINDS)}")
    return status_chip(kind, CHIP_DEFAULT_TEXT[kind] if text is None else text)


def code_chip(code: object, *, error: bool = False) -> str:
    """The chip carrying a normalised code: `unavailable · gpu_status_unreachable`.

    Neutral for a documented state; `error=True` paints the same pill red for a failure
    during a run. The text and `data-kind="unavailable"` are identical in both tones — the
    one DOM contract the verifier and the goldens read.
    """
    normalised = normalize_code(code)
    tone = ERROR_TONE if error else CHIP_KINDS["unavailable"]
    return _status_chip("unavailable", f"{UNAVAILABLE_PREFIX}{normalised}", tone, normalised)


def _chip(text: str, tone: str = "neutral", *, attrs: str = "") -> str:
    return f'<span class="alg-chip alg-chip-{tone}"{attrs}>{_text_with_times(text)}</span>'


def stamp_chip(kind: str, stamp: str) -> str:
    """`measured 2026-09-22 14:02 UTC` as a neutral chip whose stamp is a `<time>`: the chip a
    tab draws for what was measured, counted, fetched or computed and when (`STAMP_KINDS`)."""
    if kind not in STAMP_KINDS:
        raise ValueError(f"unknown stamp kind {kind!r}; expected one of {STAMP_KINDS}")
    return (
        f'<span class="alg-chip alg-chip-neutral" data-stamp-kind="{kind}">'
        f"{kind} {time_stamp(stamp)}</span>"
    )


def stability_chip(lanes: list[LaneResult], cv_max: float = bench.CV_MAX) -> str:
    """The rulebook's stability gate as one chip: `stable · spread 4.0% ≤ 15%` when every lane
    is stable — `LaneResult.stable`: its spread and its mean/median gap both inside the gate —
    else the amber chip naming what failed: `spread 18% above 15%`, or `mean 22% off the
    median, above 15%` when the spread cleared and the mean did not (a 50/50 alternation has
    MAD 0; Codna review on #1150 caught the chip reading the spread alone). A cell that should
    not have been recorded — the card still tells the truth."""
    if not lanes:
        raise ValueError("the stability gate needs at least one lane")
    worst_spread = max(lane.spread for lane in lanes)
    worst_skew = max(lane.skew for lane in lanes)
    attrs = ' data-gate="stability"'
    if worst_spread <= cv_max and worst_skew <= cv_max:
        return _chip(
            f"{STABLE_TEXT} · spread {fmt_cv(worst_spread)} ≤ {fmt_gate(cv_max)}", attrs=attrs
        )
    if worst_spread > cv_max:
        return _chip(f"spread {fmt_cv(worst_spread)} above {fmt_gate(cv_max)}", "warn", attrs=attrs)
    return _chip(
        f"mean {fmt_cv(worst_skew)} off the median, above {fmt_gate(cv_max)}", "warn", attrs=attrs
    )


def calls_text(n: int, k: int = 1) -> str:
    """`n = 21` for one call per sample; `n = 21 × 61 calls` for k back-to-back calls per sample
    (rulebook v0.4 batches: the figures are per call; k is sized from the warm call so that
    k × warm call ≥ 10 ms, and a batched sample usually lasts a few ms)."""
    if n < 1 or k < 1:
        raise ValueError("n and k are at least 1")
    if k == 1:
        return f"n = {n}"
    return f"n = {n} × {k} calls"


def n_texts(cell: CellResult) -> list[str]:
    """The n chip's words for a cell: one text when every lane shares k (`n = 21`, `n = 21 ×
    16 calls`), else one per lane with the lane's name (`n = 21 × 16 calls · algenta-text`,
    `n = 21 × 1 call · nltk`), so a race whose lanes batched differently says so per lane."""
    if cell.n < 1:
        raise ValueError("a cell that was timed has n ≥ 1")
    k = cell.k
    if k is not None:
        return [calls_text(cell.n, k)]
    texts = []
    for lane in cell.lanes:
        calls = f"{lane.k} calls" if lane.k != 1 else "1 call"
        texts.append(f"n = {cell.n} × {calls} · {lane.name}")
    return texts


def n_chips(cell: CellResult) -> list[str]:
    """`n_texts(cell)` as neutral chips, each carrying `data-n` and `data-k`."""
    if cell.k is not None:
        return [_chip(n_texts(cell)[0], attrs=f' data-n="{cell.n}" data-k="{cell.k}"')]
    return [
        _chip(text, attrs=f' data-n="{cell.n}" data-k="{lane.k}"')
        for text, lane in zip(n_texts(cell), cell.lanes, strict=True)
    ]


def spread_chips(lane: LaneResult) -> list[str]:
    """P95 (or max under 20 samples), MAD and CV of one lane as neutral chips, each with its
    unit — for a tab that draws its own card around a lane."""
    tail = "P95" if lane.n >= bench.P95_MIN_N else "max"
    tail_ms = lane.p95_ms if lane.n >= bench.P95_MIN_N else lane.max_ms
    return [
        _chip(f"{tail} {fmt_ms(tail_ms)}"),
        _chip(f"MAD {fmt_ms(lane.mad_ms)}"),
        _chip(f"spread {fmt_cv(lane.spread)}"),
        _chip(f"CV {fmt_cv(lane.cv)}"),
    ]


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
    """Every rulebook statistic per lane: median, MAD, CV, P95 (or max), min – max.

    Each cell carries `data-label` so the phone layout (one row card per lane, below
    `TABLE_STACK_MAX_WIDTH`) can print the column name beside the value."""
    p95_head = "P95" if all(lane.n >= bench.P95_MIN_N for lane in lanes) else "max"
    heads = ("lane", "median", "MAD", "spread", "CV", p95_head, "min – max")

    def row(lane: LaneResult) -> str:
        values = (
            _esc(lane.name),
            fmt_ms(lane.median_ms),
            fmt_ms(lane.mad_ms),
            fmt_cv(lane.spread),
            fmt_cv(lane.cv),
            fmt_ms(lane.p95_ms),
            f"{fmt_ms(lane.min_ms)} – {fmt_ms(lane.max_ms)}",
        )
        cells = "".join(
            f'<td data-label="{head}">{value}</td>'
            for head, value in zip(heads, values, strict=True)
        )
        return f"<tr>{cells}</tr>"

    head_cells = "".join(f"<th>{head}</th>" for head in heads)
    return (
        '<table class="alg-lane-table">'
        f"<thead><tr>{head_cells}</tr></thead>"
        f"<tbody>{''.join(row(lane) for lane in lanes)}</tbody></table>"
    )


def _chips_html(cell: CellResult, *, transport_share: float | None, status: tuple[str, str]) -> str:
    chips = []
    if cell.parity_label:
        chips.append(_chip(f"parity {cell.parity_label}", "ok"))
    if cell.seed is not None:
        chips.append(_chip(f"seed {cell.seed}"))
    chips.extend(n_chips(cell))
    if cell.lanes:
        chips.append(stability_chip(cell.lanes))
    # rule 10: a kernel timing includes the JSON marshalling across the C ABI — said on the card,
    # the parity cards included (launch review round 4: a 67 µs "in-kernel" parity time lost to a
    # 4.5 µs pure-Python call with no word about transport)
    chips.append(_chip(bench.TRANSPORT_NOTE))
    if transport_share is not None:
        if not 0.0 <= transport_share <= 1.0:
            raise ValueError("transport_share is a fraction between 0 and 1")
        chips.append(_chip(f"transport {transport_share:.0%}"))
    chips.append(status_chip(*status))
    return f'<div class="alg-chips">{"".join(chips)}</div>'


def foot_html(hardware: str, ts_utc: str, load_1m: float = bench.LOAD_UNREAD) -> str:
    """`hardware · host load 14.1 · <time>stamp</time>`: the machine line as given, the machine's
    1-minute load average when the cell ran (rulebook v0.6: disclosed, never a gate — an idle
    host's 0.0 included; omitted only when the harness did not read one, `bench.LOAD_UNREAD`,
    Codna review on #1150), the stamp machine-readable."""
    parts = [_esc(hardware)]
    if load_1m >= 0:
        parts.append(f"host load {load_1m:.1f}")
    parts.append(_time_or_text(ts_utc))
    return f'<div class="alg-card-foot">{" · ".join(parts)}</div>'


_foot_html = foot_html  # the private name a few callers used


def render_result_card(
    cell: CellResult,
    *,
    title: str,
    hardware: str,
    subtitle: str = "",
    race: bool = True,
    transport_share: float | None = None,
    last_win_ts: str = "",
    parity_label: str = NOT_A_RACE_TEXT,
) -> str:
    """The card for one cell.

    `race=True` shows the ratio as the hero and falls back to the held card when
    the incumbent was faster; `race=False` shows a parity badge and both
    latencies, labelled `parity_label` — "not a race" by default (a torch panel has no
    ratio to speak of), or the Races tab's measured figure with its status (round 6: a
    62× kernel win read "not a race" beside its two latencies). Cells that were not
    measured render the not-recorded card, which carries no number.
    """
    if not cell.measured:
        return render_not_recorded_card(cell, title=title, hardware=hardware, subtitle=subtitle)
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
            f'<div class="alg-hero-label">{_esc(parity_label)} · '
            f"{fmt_ms(ours.median_ms)} per kernel call</div>"
        )

    sub = f'<div class="alg-card-sub">{_esc(subtitle)}</div>' if subtitle else ""
    chips = _chips_html(
        cell, transport_share=transport_share, status=("measured", f"measured {cell.ts_utc}")
    )
    return (
        '<article class="alg-card alg-card-result">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{_esc(title)}</h2>{sub}</div>'
        f'<div class="alg-hero">{hero}</div>'
        "</div>"
        f"{_bars_html(cell.lanes)}"
        f"{_table_html(cell.lanes)}"
        f"{chips}"
        f"{foot_html(hardware, cell.ts_utc, cell.load_1m)}"
        "</article>"
    )


def render_not_recorded_card(
    cell: CellResult,
    *,
    title: str,
    hardware: str,
    subtitle: str = "",
    result_html: str = "",
    chips: list[str] | tuple[str, ...] = (),
) -> str:
    """A cell whose timing did not clear the rulebook: the result stays, the timing does not.

    The kernel ran and its result passed the gate — the value is not noisy, only its timing
    is — so the card prints `result_html` (the caller's own markup for the answer, e.g. the
    Try tab's `<pre class="alg-result">z …</pre>`; escaped nothing, it is trusted card
    markup like the chips) and the parity chips: the cell's own gate label
    (`parity exact match`, as the result card prints it) and any `chips` the caller adds
    (the Try tab's `parity vs statsmodels` pair). Where the result card draws the bars and
    the lane table, this card draws one quiet timing row (`alg-card-timing`,
    `data-state="not_recorded"`): the label, the rulebook's reason, the neutral
    `not recorded` chip. A documented state, so the card is quiet — the neutral hairline
    carries it; amber would paint the protocol's honest answer as a warning. No number
    that was not recorded appears; the reason names the gate that held it."""
    if cell.measured:
        raise ValueError("measured cells render the result card")
    sub = f'<div class="alg-card-sub">{_esc(subtitle)}</div>' if subtitle else ""
    parity = [_chip(f"parity {cell.parity_label}", "ok")] if cell.parity_label else []
    parity.extend(chips)
    parity_html = f'<div class="alg-chips">{"".join(parity)}</div>' if parity else ""
    timing = (
        f'<div class="alg-card-timing" data-state="not_recorded">'
        f'<span class="alg-card-timing-label">{TIMING_LABEL}</span>'
        f'<p class="alg-card-reason">{_esc(cell.reason or NOT_RECORDED_TEXT)}</p>'
        f'<div class="alg-chips">{status_chip("unavailable", NOT_RECORDED_TEXT)}</div>'
        "</div>"
    )
    return (
        '<article class="alg-card alg-card-quiet" data-state="not_recorded">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>{sub}'
        f"{result_html}"
        f"{parity_html}"
        f"{timing}"
        f"{foot_html(hardware, cell.ts_utc, cell.load_1m)}"
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
    """Hold and disclose: the incumbent won this run; both times shown, nothing recorded.

    The chips carry the held code (`held · incumbent_faster`) and the measurement stamp. A
    held run is a documented state (`CHIP_KINDS["held"]` is neutral), so the card draws the
    neutral hairline too.
    """
    if algenta_ms < incumbent_ms:
        raise ValueError("held cards are for runs the incumbent won")
    last = (
        '<p class="alg-card-note">last recorded win on this hardware: '
        f"{_time_or_text(last_win_ts)}</p>"
        if last_win_ts
        else ""
    )
    held = status_chip("held", f"held · {HELD_CODE}", code=HELD_CODE)
    return (
        '<article class="alg-card alg-card-quiet" data-state="held">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>'
        f'<p class="alg-card-reason">{HELD_TEXT} — {fmt_ms(algenta_ms)} vs '
        f"{fmt_ms(incumbent_ms)} ({_esc(incumbent_name)}); {NOT_RECORDED_TEXT}</p>"
        f"{last}"
        f'<div class="alg-chips">{held}{status_chip("measured", f"measured {ts_utc}")}</div>'
        f"{foot_html(hardware, ts_utc)}"
        "</article>"
    )


def render_unavailable_card(
    *, title: str, error_code: str, hint: str, hardware: str = "", error: bool = False
) -> str:
    """A lane or feature that cannot run here: a code the runbook indexes and one hint.

    Quiet by default — hairline border, neutral chip — because a documented state is not a
    failure. `error=True` is for a failure during a run (a parity check that did not agree,
    a call that raised): red hairline, red chip, the same code convention. The code is
    normalised to lowercase snake_case (`normalize_code`)."""
    if not str(error_code).strip():
        raise ValueError("error_code is empty")
    foot = f'<div class="alg-card-foot">{_esc(hardware)}</div>' if hardware else ""
    tone, state = ("err", "error") if error else ("quiet", "unavailable")
    return (
        f'<article class="alg-card alg-card-{tone}" data-state="{state}">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>'
        f'<div class="alg-chips">{code_chip(error_code, error=error)}</div>'
        f'<p class="alg-card-reason">{_esc(hint)}</p>'
        f"{foot}"
        "</article>"
    )


def render_error_card(*, title: str, error_code: str, hint: str, hardware: str = "") -> str:
    """`render_unavailable_card(error=True)`: the red card for a failure during a run."""
    return render_unavailable_card(
        title=title, error_code=error_code, hint=hint, hardware=hardware, error=True
    )


def render_not_configured_card(
    *, title: str, hint: str, error_code: str = NOT_CONFIGURED_CODE, hardware: str = ""
) -> str:
    """A designed, quiet state: a hosted lane whose key is not set. Hairline border, no red.

    The chip is the fleet's unavailable chip with the normalised code, so a reader of the
    page and the verifier see one convention; the card itself is not an error."""
    foot = f'<div class="alg-card-foot">{_esc(hardware)}</div>' if hardware else ""
    return (
        '<article class="alg-card alg-card-quiet" data-state="not_configured">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>'
        f'<div class="alg-chips">{code_chip(error_code)}</div>'
        f'<p class="alg-card-reason">{_esc(hint)}</p>'
        f"{foot}"
        "</article>"
    )


def loading(title: str, detail: str = "") -> str:
    """The card a handler returns while it measures: title, lane detail, the loading chip.

    `detail` is the lane position or ETA ("queued · 2 ahead · 1.2 s", "running now")."""
    reason = f'<p class="alg-card-reason">{_esc(detail)}</p>' if detail else ""
    return (
        '<article class="alg-card alg-card-loading" aria-busy="true">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>'
        f"{reason}"
        f'<div class="alg-chips">{chip("loading")}</div>'
        "</article>"
    )


STAT_STAMP_CLASS = "alg-stat-stamp"


def stamp_html(stamp: str, kind: str = "counted", *, class_name: str = STAT_STAMP_CLASS) -> str:
    """`<time datetime="2026-09-22T14:02Z">counted 2026-09-22 14:02 UTC</time>` — the rule that a
    measured or counted number carries what was done to it and when, in UTC."""
    if kind not in STAMP_KINDS:
        raise ValueError(f"unknown stamp kind {kind!r}; expected one of {STAMP_KINDS}")
    day, clock = _parse_stamp(stamp)
    return (
        f'<time class="{class_name}" datetime="{day}T{clock}Z" data-stamp-kind="{kind}">'
        f"{kind} {day} {clock} UTC</time>"
    )


def tile(
    label: str,
    value: str,
    meta: str = "",
    state: str = "ok",
    *,
    code: str = "",
    stamp: str = "",
    stamp_kind: str = "counted",
) -> str:
    """One statistic tile: caption label, tabular value, meta line; identical geometry per state.

    `state` is `ok`, `warn` or `unavailable`. An unavailable tile takes the code (`code`
    or `value`), shows an em dash where the number would be and the code chip in the
    meta line; `meta` still renders after the chip when given. `value` carries its own
    unit ("6,040 functions", "412 tok/s"); `meta` carries the provenance ("18 families
    loaded here"). A number that was measured or counted also carries its UTC stamp:
    `stamp="2026-09-22 14:02 UTC"` (`stamp_kind` one of `STAMP_KINDS`, default
    `counted`) renders a `<time>` reading `counted 2026-09-22 14:02 UTC` after the meta
    text, so no figure stands without its when. A stamp the caller left at the end of
    `meta` (`… · 2026-09-22 14:02 UTC`) is lifted into a `<time>` element the same way,
    without a kind word, so the meta line reads as written and the stamp is machine-readable.
    `meta` names the provenance in words; `hostname_token(meta)` is the caller's check that
    no host or URL rides in it."""
    if state not in TILE_STATES:
        raise ValueError(f"unknown tile state {state!r}; expected one of {TILE_STATES}")
    if not str(label).strip():
        raise ValueError("a tile needs a label")
    meta_text, lifted = (meta, "") if stamp else split_trailing_stamp(meta)
    if state == "unavailable":
        shown = EMPTY_VALUE
        meta_html = code_chip(code or value)
        if meta_text:
            meta_html += f"<span>{_esc(meta_text)}</span>"
    else:
        if not str(value).strip():
            raise ValueError("a tile needs a value with its unit")
        shown = _esc(value)
        meta_html = f"<span>{_esc(meta_text)}</span>" if meta_text else ""
    if stamp:
        meta_html += stamp_html(stamp, stamp_kind)
    elif lifted:
        meta_html += time_stamp(lifted, class_name=STAT_STAMP_CLASS)
    return (
        f'<article class="alg-stat alg-stat-{state}" data-state="{state}">'
        f'<div class="alg-stat-label">{_esc(label)}</div>'
        f'<div class="alg-stat-value">{shown}</div>'
        f'<div class="alg-stat-meta">{meta_html}</div>'
        "</article>"
    )


def empty(title: str, hint: str) -> str:
    """The quiet empty state: dashed hairline, muted text, no colour."""
    if not str(title).strip():
        raise ValueError("an empty state needs a title")
    return (
        '<article class="alg-card alg-card-empty">'
        f'<h2 class="alg-card-title">{_esc(title)}</h2>'
        f'<p class="alg-card-hint">{_esc(hint)}</p>'
        "</article>"
    )


def snippet_block(code: str, language: str = "python", *, caption: str = "") -> str:
    """A snippet for a `gr.HTML` payload: language caption, `<pre>` on `surface-2`, wrapping.

    Refuses empty code — an editor never renders empty — and a language outside
    `SNIPPET_LANGUAGES`. `caption` replaces the language name ("Install", "MCP request")."""
    if not str(code).strip():
        raise ValueError("a snippet never renders empty: pass the code, or render nothing")
    if language not in SNIPPET_LANGUAGES:
        raise ValueError(
            f"unknown snippet language {language!r}; expected one of {sorted(SNIPPET_LANGUAGES)}"
        )
    label = caption.strip() or SNIPPET_LANGUAGES[language]
    body = _esc(str(code).strip("\n"))
    return (
        f'<figure class="alg-snippet" data-language="{language}">'
        f'<figcaption class="alg-snippet-caption">{_esc(label)}</figcaption>'
        f'<pre class="alg-snippet-code"><code>{body}</code></pre>'
        "</figure>"
    )


def copy_label(language: str = "json") -> str:
    """The Copy chip's label for a code block: `Copy JSON`, `Copy Python`, `Copy command`."""
    if language not in COPY_LABELS:
        raise ValueError(
            f"unknown snippet language {language!r}; expected one of {sorted(COPY_LABELS)}"
        )
    return COPY_LABELS[language]


def code_block(
    code: str, language: str = "json", *, caption: str = "", max_lines: int = CODE_LINES_DEFAULT
) -> str:
    """A long snippet as a capped, scrolling, keyboard-focusable region (module docstring).

    The whole text is in the page; the `<pre>` shows `max_lines` lines (`--alg-code-lines`,
    read by `CARD_CSS`) and scrolls inside. `tabindex="0"` puts the region in the tab order,
    `role="region"` names it from the caption and the line count (`Engine JSON, 254 lines`),
    and the caption reads `Engine JSON · 254 lines`. A text within the cap is still this
    block (no scroller appears; the ring and the name still hold). Refuses empty code like
    `snippet_block`. The tab offers `copy_label(language)` as a 44 px `alg-chip-btn` beside
    it, wired to the same full text."""
    if not str(code).strip():
        raise ValueError("a code block never renders empty: pass the code, or render nothing")
    if language not in SNIPPET_LANGUAGES:
        raise ValueError(
            f"unknown snippet language {language!r}; expected one of {sorted(SNIPPET_LANGUAGES)}"
        )
    if max_lines < 1:
        raise ValueError("a code block shows at least one line")
    text = str(code).strip("\n")
    lines = text.count("\n") + 1
    label = caption.strip() or SNIPPET_LANGUAGES[language]
    count = f"{lines:,} line" + ("s" if lines != 1 else "")
    return (
        f'<figure class="alg-snippet {CODE_CAPPED_CLASS}" data-language="{language}"'
        f' data-lines="{lines}" style="{CODE_LINES_VAR}: {max_lines}">'
        f'<figcaption class="alg-snippet-caption">{_esc(label)} · {count}</figcaption>'
        f'<pre class="alg-snippet-code {CODE_SCROLL_CLASS}" tabindex="0" role="region"'
        f' aria-label="{_esc(label)}, {count}"><code>{_esc(text)}</code></pre>'
        "</figure>"
    )


# Short names the tabs call.
unavailable = render_unavailable_card
error = render_error_card
held = render_held_card
not_configured = render_not_configured_card


# alg-card / alg-lane / alg-chip / alg-stat classes only, each repeated four times
# by css.rule(), tokens from design.TOKENS_CSS, spacing on the 8-pt scale.

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_BODY = "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
_MONO_NUM = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
_CELL = (
    "text-align: left; vertical-align: baseline; padding: 4px 8px 4px 0; border: 0;"
    " border-bottom: 1px solid var(--alg-hairline); font-variant-numeric: tabular-nums;"
    " background: transparent;"
)
_TABLE = f"width: 100%; border-collapse: collapse; border: 0; {_CAPTION} margin: 8px 0;"
_HEAD_CELL = f"{_CELL} color: var(--alg-text-2); font-weight: 500;"
_PULSE = "@keyframes alg-chip-pulse { 0%, 100% { opacity: 0.35; } 50% { opacity: 1; } }"


def _table_rules(class_name: str, *, table_suffix: str, cell_extra: str = "") -> tuple[str, ...]:
    """Hairline row separators only for the table `table_suffix` selects under `class_name`."""
    return (
        rule(class_name, _TABLE, suffix=table_suffix),
        rule(class_name, "border: 0; background: transparent;", suffix=f"{table_suffix} tr"),
        rule(class_name, _HEAD_CELL, suffix=f"{table_suffix} th"),
        rule(class_name, f"{_CELL} {cell_extra}", suffix=f"{table_suffix} td"),
    )


CARD_CSS = stylesheet(
    rule(
        "alg-card",
        "font-family: var(--alg-font); color: var(--alg-text); background: var(--alg-surface);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-card);"
        " padding: 16px 24px; box-shadow: var(--alg-shadow);",
    ),
    rule("alg-card-warn", "border-color: var(--alg-warn);"),
    rule("alg-card-err", "border-color: var(--alg-err);"),
    rule("alg-card-quiet", "border-color: var(--alg-hairline);"),
    rule("alg-card-loading", "border-color: var(--alg-hairline);"),
    rule(
        "alg-card-empty",
        "border-style: dashed; border-color: var(--alg-hairline); box-shadow: none;"
        " background: transparent; color: var(--alg-text-2);",
    ),
    rule("alg-card-empty", "color: var(--alg-text-2);", suffix=" .alg-card-title"),
    rule("alg-card-hint", f"{_BODY} color: var(--alg-text-2); margin: 8px 0 0;"),
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
    # tables: hairline row separators only, in every card and in the Ecosystem table
    *_table_rules("alg-card", table_suffix=" table"),
    *_table_rules("alg-lane-table", table_suffix="", cell_extra=_MONO_NUM),
    rule("alg-lane-table", "white-space: nowrap;", suffix=" th"),
    rule("alg-lane-table", "white-space: nowrap;", suffix=" td"),
    *_table_rules("alg-eco-table", table_suffix=""),
    # the shared table: hairline rows; numbers right-aligned, mono, tabular, one line — the
    # cell class sits under the table class, so it outranks the table's own `td` rule
    *_table_rules(TABLE_CLASS, table_suffix=""),
    rule(TABLE_CLASS, "border-bottom: 0;", suffix=" tbody tr:last-child td"),
    rule(
        TABLE_CLASS,
        f"{_MONO_NUM} text-align: right; white-space: nowrap;",
        suffix=f" .{TABLE_NUM_CLASS}",
    ),
    rule(TABLE_CLASS, "content: none;", suffix=" td::before"),
    # on a phone: one row card per row — the name cell first and 44 px tall for its link, every
    # other cell a `label · value` line from its data-label; the dense variant drops the cell
    # hairlines and padding for a long table (44 + 4 x 16 + 16 = 124 px)
    block(
        f"@media (width <= {TABLE_PHONE_MAX_WIDTH}px)",
        rule(TABLE_STACK_CLASS, "display: block;"),
        rule(TABLE_STACK_CLASS, "display: none;", suffix=" thead"),
        rule(TABLE_STACK_CLASS, "display: block;", suffix=" tbody"),
        rule(
            TABLE_STACK_CLASS,
            "display: flex; flex-direction: column; border: 1px solid var(--alg-hairline);"
            " border-radius: var(--alg-radius-card); padding: 8px 16px; margin: 0 0 8px;"
            " background: var(--alg-surface);",
            suffix=" tbody tr",
        ),
        rule(
            TABLE_STACK_CLASS,
            "display: flex; justify-content: space-between; align-items: baseline; gap: 16px;"
            " padding: 4px 0; white-space: normal; text-align: right;"
            " border-bottom: 1px solid var(--alg-hairline);",
            suffix=" td",
        ),
        rule(TABLE_STACK_CLASS, "border-bottom: 0;", suffix=" td:last-child"),
        rule(
            TABLE_STACK_CLASS,
            "display: inline; content: attr(data-label); flex: 0 0 auto;"
            " font-family: var(--alg-font); font-weight: 400; color: var(--alg-text-2);"
            " text-align: left;",
            suffix=" td::before",
        ),
        rule(
            TABLE_STACK_CLASS,
            "order: -1; font-weight: 600; min-height: var(--alg-target); align-items: center;"
            " justify-content: flex-start; text-align: left;",
            suffix=f" .{TABLE_LEAD_CLASS}",
        ),
        rule(TABLE_STACK_CLASS, "content: none;", suffix=f" .{TABLE_LEAD_CLASS}::before"),
        rule(TABLE_DENSE_CLASS, "padding: 8px 12px;", suffix=" tbody tr"),
        rule(TABLE_DENSE_CLASS, "padding: 0; border-bottom: 0; gap: 8px;", suffix=" td"),
    ),
    # the lane table on a phone: one row card per lane, the column name beside each value
    block(
        f"@media (width <= {TABLE_STACK_MAX_WIDTH}px)",
        rule("alg-lane-table", "display: block;"),
        rule("alg-lane-table", "display: none;", suffix=" thead"),
        rule("alg-lane-table", "display: block;", suffix=" tbody"),
        rule(
            "alg-lane-table",
            "display: flex; flex-direction: column; border: 1px solid var(--alg-hairline);"
            " border-radius: var(--alg-radius-input); padding: 8px 12px; margin: 0 0 8px;"
            " background: var(--alg-surface-2);",
            suffix=" tbody tr",
        ),
        rule(
            "alg-lane-table",
            "display: flex; justify-content: space-between; align-items: baseline; gap: 16px;"
            " padding: 4px 0; white-space: normal; text-align: right;",
            suffix=" td",
        ),
        rule("alg-lane-table", "border-bottom: 0;", suffix=" td:last-child"),
        rule(
            "alg-lane-table",
            "content: attr(data-label); flex: 0 0 auto; font-family: var(--alg-font);"
            " font-weight: 400; color: var(--alg-text-2); text-align: left;",
            suffix=" td::before",
        ),
        rule("alg-lane-table", "font-weight: 600;", suffix=" td:first-child"),
        # every card: 16 px sides on a phone (round 4 measured 24 px on LLM, Governed, Ecosystem)
        rule("alg-card", "padding: 16px;"),
    ),
    # a row of chips centres mixed heights (a wrapped tag beside one-line pills)
    rule(
        "alg-chips",
        "display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 12px 0 0;",
    ),
    # one inline formatting context, not a flex box: as flex items, the text run `measured `
    # and the <time> beside it lost the space between them (measured live: "measured2026-…")
    rule(
        "alg-chip",
        f"display: inline-block; vertical-align: middle; font-family: var(--alg-font-mono);"
        f" {_CAPTION} padding: 4px 12px; border-radius: var(--alg-radius-pill);"
        " background: var(--alg-surface-2); border: 1px solid var(--alg-hairline);"
        " color: var(--alg-text-2); font-variant-numeric: tabular-nums;"
        " max-width: 100%; box-sizing: border-box; overflow-wrap: anywhere;",
    ),
    # the wrapping variant: a chip whose text takes two lines is a 12 px tag, 44 px or taller
    # (2 x 16 px lines + 2 x 8 px on the grid + the hairlines = 50 px), left-aligned — never
    # text inside a half-circle (set by shell.CHIP_WRAP_SCRIPT)
    rule(
        "alg-chip",
        "border-radius: var(--alg-radius-card); min-height: var(--alg-target);"
        " padding: 8px 12px; text-align: left;",
        suffix=f"[{CHIP_WRAP_ATTR}]",
    ),
    # a <time> takes the tone of the chip or foot it sits in: Gradio's prose reset paints every
    # descendant `body-text-color` (measured: rgb(11,11,18) inside a text-2 chip), so inherit
    rule(TIME_CLASS, "color: inherit; font: inherit; font-variant-numeric: tabular-nums;"),
    rule("alg-chip-ok", "color: var(--alg-ok);"),
    rule("alg-chip-warn", "color: var(--alg-warn);"),
    rule("alg-chip-err", "color: var(--alg-err);"),
    rule("alg-chip-loading", "color: var(--alg-text-2); position: relative; padding-left: 24px;"),
    rule(
        "alg-chip-loading",
        'content: ""; position: absolute; left: 12px; top: 50%; width: 6px; height: 6px;'
        " transform: translateY(-50%); border-radius: var(--alg-radius-pill);"
        " background: var(--alg-accent-to); animation: alg-chip-pulse 1.2s ease-in-out infinite;",
        suffix="::before",
    ),
    _PULSE,
    block(
        "@media (prefers-reduced-motion: reduce)",
        rule("alg-chip-loading", "animation: none;", suffix="::before"),
    ),
    # the reason line is body copy (15/22, regular): a state is stated, not shouted
    rule("alg-card-reason", f"{_BODY} font-weight: 400; margin: 12px 0 0;"),
    # the not-recorded card's timing row, where the result card draws bars and a table: a
    # caption label above the reason, hairline above, on the grid
    rule(
        "alg-card-timing",
        "margin: 16px 0 0; padding: 12px 0 0; border-top: 1px solid var(--alg-hairline);",
    ),
    rule(
        "alg-card-timing-label",
        f"display: block; font-family: var(--alg-font-mono); {_CAPTION} letter-spacing: 0.08em;"
        " text-transform: uppercase; color: var(--alg-text-2);",
    ),
    rule("alg-card-timing", "margin: 4px 0 0;", suffix=" > .alg-card-reason"),
    rule("alg-card-note", f"{_CAPTION} color: var(--alg-text-2); margin: 4px 0 0;"),
    rule(
        "alg-card-foot",
        f"font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);"
        " margin: 12px 0 0;",
    ),
    # stat tiles: one geometry for every state
    rule(
        "alg-stat",
        "font-family: var(--alg-font); color: var(--alg-text); background: var(--alg-surface);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-card);"
        " padding: 16px 24px; box-shadow: var(--alg-shadow); display: flex;"
        " flex-direction: column; gap: 4px; min-height: 120px; text-align: left;"
        " box-sizing: border-box;",
    ),
    rule("alg-stat-label", f"{_CAPTION} color: var(--alg-text-2); margin: 0;"),
    rule(
        "alg-stat-value",
        f"{_MONO_NUM} font-size: var(--alg-title-size); line-height: var(--alg-title-line);"
        " letter-spacing: var(--alg-title-tracking); font-weight: 600; margin: 0;"
        " overflow-wrap: anywhere;",
    ),
    rule(
        "alg-stat-meta",
        f"{_CAPTION} color: var(--alg-text-2); min-height: 24px; display: flex;"
        " flex-wrap: wrap; align-items: center; gap: 8px; margin: 0;",
    ),
    rule("alg-stat-warn", "color: var(--alg-warn);", suffix=" .alg-stat-value"),
    rule("alg-stat-unavailable", "color: var(--alg-text-2);", suffix=" .alg-stat-value"),
    rule(
        "alg-stat-stamp",
        f"font-family: var(--alg-font-mono); {_CAPTION} font-variant-numeric: tabular-nums;"
        " color: var(--alg-text-2);",
    ),
    # snippets in HTML payloads: caption, wrapping <pre> on surface-2, never a page scroll
    rule(
        "alg-snippet",
        "margin: 12px 0 0; background: var(--alg-surface-2); border: 1px solid var(--alg-hairline);"
        " border-radius: var(--alg-radius-input); overflow: hidden;",
    ),
    rule(
        "alg-snippet-caption",
        f"font-family: var(--alg-font-mono); {_CAPTION} letter-spacing: 0.08em;"
        " text-transform: uppercase; color: var(--alg-text-2); padding: 8px 12px 0;",
    ),
    rule(
        "alg-snippet-code",
        "font-family: var(--alg-font-mono); font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line); font-variant-numeric: tabular-nums;"
        " color: var(--alg-text); margin: 0; padding: 8px 12px 12px; white-space: pre-wrap;"
        " overflow-wrap: anywhere; tab-size: 4; background: transparent; border: 0;",
    ),
    # the capped code block (`code_block`): the <pre> shows --alg-code-lines lines (24) plus its
    # 8 + 12 px of padding and scrolls inside; the focus ring is the fleet's 2 px accent ring,
    # drawn inside the edge because the figure clips its rounded corners
    rule(
        CODE_SCROLL_CLASS,
        f"max-height: calc(var({CODE_LINES_VAR}, {CODE_LINES_DEFAULT}) * var(--alg-mono-line)"
        " + 20px); overflow: auto; box-sizing: border-box; scrollbar-width: thin;"
        " scrollbar-color: var(--alg-text-2) transparent;",
    ),
    rule(
        CODE_SCROLL_CLASS,
        "outline: 2px solid var(--alg-accent-to); outline-offset: -2px;"
        " border-radius: var(--alg-radius-input);",
        suffix=":focus-visible",
    ),
)
