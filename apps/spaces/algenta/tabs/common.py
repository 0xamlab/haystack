"""Helpers the Try, Playground and Races tabs share: lane chips, cards, fetches, limits.

Pure functions returning HTML or data; nothing here imports gradio. Every user string passes
through ``html.escape``; every number is rendered with its unit; every network read is https
with a timeout and returns a typed outcome instead of raising.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import platform
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

from algenta_spaces import bench, cards, hubkernel, lane
from algenta_spaces.css import PHONE_MAX_WIDTH, block, rule, stylesheet
from algenta_spaces.limits import Decision, key_from_request
from algenta_spaces.runtime import utc_stamp

from tabs import NATIVE_LIMIT_KIND, Deps

log = logging.getLogger(__name__)

USER_AGENT = "algenta-spaces-flagship"
FETCH_TIMEOUT_S = 5.0
#: Plan budgets: a single native call waits at most this long, a race cell at most RACE_BUDGET_S.
CALL_BUDGET_S = 5.0
RACE_BUDGET_S = 20.0
RESULT_CHARS = 2_000

TRANSPORT_NOTE = hubkernel.TRANSPORT_NOTE
#: Every `gr.HTML` that renders a card, a board, a note or a table carries this class: Gradio pads
#: an HTML block's container 16 px, which put those blocks 16 px inside the column the header,
#: the tab strip and the Try/Playground cards share (launch review round 4). The rules live in
#: `TABS_CSS`; the Try and Playground blocks had their own, older rules.
BLOCK_CLASS = "alg-block"
#: Where a visitor's call ran, as the header pill says it (`app.PILL_WHERE`): the provenance
#: word beside every `done in …` figure, so a duration never stands without its where and when.
WHERE_RUN = "this container"
#: The settled opening card's chip while no attempt has been measured on this host.
NOT_MEASURED_TEXT = "not measured yet"
CODE_LIMITED = "rate_limited"
CODE_SWITCHED_OFF = "switched_off"
CODE_NO_KERNEL = "kernel_not_loaded"
SWITCHED_OFF_HINT = "This lane is paused by the operator; the rest of the page keeps working."
NO_KERNEL_HINT = "The family did not load in this container; the boot card carries the reason."


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def chip(text: str, tone: str = "neutral") -> str:
    """One neutral, ok, warn or err pill (the status chip's four kinds live in cards.py)."""
    if tone not in ("neutral", "ok", "warn", "err"):
        raise ValueError(f"unknown chip tone {tone!r}")
    return f'<span class="alg-chip alg-chip-{tone}">{esc(text)}</span>'


# ---------------------------------------------------------------------------
# Fetching (https only, never raises)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fetched:
    """One GET: the status (0 when the request never completed), the parsed JSON, the error."""

    url: str
    status: int
    data: Any = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.error


def fetch_json(url: str, *, timeout_s: float = FETCH_TIMEOUT_S) -> Fetched:
    """GET a JSON document over https; every failure is a `Fetched` with `error`, not a raise."""
    if urlsplit(url).scheme != "https":
        return Fetched(url, 0, error="only https sources are read")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        return Fetched(url, exc.code, error=f"HTTP {exc.code}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Fetched(url, 0, error=f"{type(exc).__name__}: {exc}")
    try:
        return Fetched(url, status, json.loads(body.decode("utf-8")))
    except (UnicodeDecodeError, ValueError) as exc:
        return Fetched(url, status, error=f"not JSON: {exc}")


def fetch_text(url: str, *, timeout_s: float = FETCH_TIMEOUT_S) -> Fetched:
    """GET a text document over https (JSON Lines logs); `data` is the text."""
    if urlsplit(url).scheme != "https":
        return Fetched(url, 0, error="only https sources are read")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
            return Fetched(url, response.status, response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return Fetched(url, exc.code, error=f"HTTP {exc.code}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Fetched(url, 0, error=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Machine identity
# ---------------------------------------------------------------------------


def hardware_line(deps: Deps, *, packages: tuple[str, ...] = ()) -> str:
    """The shell's machine line, or the rulebook footer computed here."""
    if deps.hardware:
        return deps.hardware
    return bench.hardware_footer(deps.env, packages=packages)


def hardware_id() -> str:
    """Twelve hex characters naming this machine class — the CPU quota and the architecture,
    which is what a Hub tier fixes (cpu-upgrade: 8 vCPU x86-64). The qualification file and the
    board rows are attributed by it, so it must not move between boots of one Space: the CPU
    model changes with a host migration and the tier lookup can fail on a private boot (the
    first `qualified.json` was stamped without the tier and qualified nothing after a restart).
    The card foot still discloses the tier and the CPU model; a qualified race the incumbent
    wins live on another host is held and disclosed, never recorded. Nothing about the id comes
    from the environment, so it takes none (Codna review on #1150)."""
    text = f"{bench.cpu_quota()} vCPU|{bench.arch_name(platform.machine())}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Limits and kill switch
# ---------------------------------------------------------------------------


def visitor_key(request: Any) -> str:
    """``<ip>|<session>`` from a gr.Request-shaped object; ``anonymous|-`` without one."""
    if request is None:
        return key_from_request({})
    headers = getattr(request, "headers", None) or {}
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "")
    session = str(getattr(request, "session_hash", "") or "")
    try:
        items = dict(headers.items()) if hasattr(headers, "items") else dict(headers)
    except (TypeError, ValueError):
        items = {}
    return key_from_request(items, client_host=host, session_hash=session)


def check_limit(deps: Deps, request: Any, kind: str = NATIVE_LIMIT_KIND) -> Decision | None:
    """Check-and-take one native call for the visitor; None when the policy has no such lane."""
    if deps.limits is None or kind not in deps.limits.policy.lanes:
        return None
    return deps.limits.check(visitor_key(request), kind)


def limited_card(title: str, decision: Decision, hardware: str = "") -> str:
    return cards.render_unavailable_card(
        title=title, error_code=CODE_LIMITED, hint=decision.reason, hardware=hardware
    )


def switched_off_card(title: str, hardware: str = "") -> str:
    return cards.render_unavailable_card(
        title=title, error_code=CODE_SWITCHED_OFF, hint=SWITCHED_OFF_HINT, hardware=hardware
    )


def no_kernel_card(title: str, family: str, deps: Deps) -> str:
    error = deps.kernel_errors.get(family) or deps.kernel_errors.get(f"algenta-{family}")
    code = error.code if error is not None else CODE_NO_KERNEL
    hint = error.message if error is not None else NO_KERNEL_HINT
    return cards.render_unavailable_card(
        title=title, error_code=code, hint=hint, hardware=hardware_line(deps)
    )


def error_card(title: str, exc: BaseException, hardware: str = "") -> str:
    """The red card for a failure during a run — a lane refusal, a kernel error, a raise; the
    code is the exception's (`cards.render_error_card`: colour is meaning, and a run the
    visitor pressed for that did not complete is the one thing painted red)."""
    if isinstance(exc, lane.LaneError):
        return cards.render_error_card(title=title, hardware=hardware, **exc.card())
    if isinstance(exc, hubkernel.HubKernelError):
        return cards.render_error_card(
            title=title, error_code=exc.code, hint=exc.message, hardware=hardware
        )
    return cards.render_error_card(
        title=title,
        error_code="call_failed",
        hint=f"{type(exc).__name__}: {exc}",
        hardware=hardware,
    )


# ---------------------------------------------------------------------------
# Lane chips
# ---------------------------------------------------------------------------


def lane_chip(ticket: lane.Ticket) -> str:
    """``queued · 2 ahead · about 3 s`` or ``running`` — what the visitor sees while waiting."""
    if ticket.position <= 0:
        return cards.status_chip("loading", "running now")
    ahead = "1 ahead" if ticket.position == 1 else f"{ticket.position} ahead"
    eta = f"about {max(1, round(ticket.eta_s))} s"
    return cards.status_chip("loading", f"queued · {ahead} · {eta}")


def time_or_text(stamp: object) -> str:
    """A fleet UTC stamp as the shared `<time>` element; anything else escaped as it came, so a
    card never fails to render over a caller's malformed stamp."""
    try:
        return cards.time_stamp(stamp)
    except ValueError:
        return esc(stamp)


def run_meta(ts_utc: str | None = None) -> str:
    """`this container · <time>2026-09-22 14:02 UTC</time>` — the provenance and the stamp that
    ride beside a `done in …` chip in the status row (`alg-status-meta`, caption text, not a
    pill, so it wraps as prose on a phone instead of inside a capsule)."""
    stamp = cards.time_stamp(ts_utc or utc_stamp())
    return f'<span class="alg-status-meta">{esc(WHERE_RUN)} · {stamp}</span>'


def done_chip(ticket: lane.Ticket, *, ts_utc: str | None = None) -> str:
    """`done in 6.07 ms` as the measured pill, followed by where and when (`run_meta`): a
    duration with its unit, its provenance and its UTC stamp — never the number alone."""
    duration = ticket.duration_s()
    text = "done" if duration is None else f"done in {cards.fmt_ms(duration * 1e3)}"
    return cards.status_chip("measured", text) + run_meta(ts_utc)


def run_in_lane(
    deps: Deps,
    fn: Callable[[], Any],
    *,
    label: str,
    budget_s: float,
    on_queued: Callable[[lane.Ticket], None] | None = None,
) -> tuple[lane.Ticket, Any]:
    """Submit `fn` to the one native lane, report the ticket, wait for the result."""
    ticket = deps.lane.submit(fn, budget_s=budget_s, label=label)
    if on_queued is not None:
        on_queued(ticket)
    return ticket, ticket.result()


# ---------------------------------------------------------------------------
# Cards and tiles
# ---------------------------------------------------------------------------


def pretty_json(value: Any, *, limit: int = RESULT_CHARS) -> str:
    """Indented JSON, cut with a note when longer than `limit` characters."""
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n… {len(text) - limit:,} more characters"


def render_call_card(
    *,
    title: str,
    subtitle: str,
    latency_ms: float,
    result: Any,
    hardware: str,
    ts_utc: str,
    parity: str = "",
    kernel_label: str = "",
    extra_chips: Sequence[tuple[str, str]] = (),
    load_1m: float = bench.LOAD_UNREAD,
) -> str:
    """One executed call: the latency as the hero, the result, chips, the machine line.

    `parity` is the reference that agreed (an ok chip); `extra_chips` are `(text, tone)` pairs
    for a reference that disagreed or did not run; `kernel_label` is the provenance chip
    (`algenta-stats@ac35ffe`). The subtitle is human copy — the function's own description —
    never an identifier, a build variant or a revision.
    """
    chips = []
    if parity:
        chips.append(chip(f"parity {parity}", "ok"))
    for text, tone in extra_chips:
        chips.append(chip(text, tone))
    if kernel_label:
        chips.append(chip(kernel_label))
    chips.append(chip(TRANSPORT_NOTE))
    chips.append(cards.status_chip("measured", f"measured {ts_utc}"))
    return (
        '<article class="alg-card alg-card-result">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{esc(title)}</h2>'
        f'<div class="alg-card-sub">{esc(subtitle)}</div></div>'
        '<div class="alg-hero">'
        f'<div class="alg-hero-num alg-accent-text">{cards.fmt_ms(latency_ms)}</div>'
        '<div class="alg-hero-label">one kernel call</div>'
        "</div></div>"
        f'<pre class="alg-result">{esc(pretty_json(result))}</pre>'
        f'<div class="alg-chips">{"".join(chips)}</div>'
        f"{cards.foot_html(hardware, ts_utc, load_1m)}"
        "</article>"
    )


#: `render_tile` kinds -> `cards.tile` states: a measured or live figure is `ok`, a remembered
#: one `warn`, and a tile with no figure `unavailable` (em dash, the code chip in the meta line).
TILE_STATE_OF: Mapping[str, str] = {
    "live": "ok",
    "measured": "ok",
    "fallback": "warn",
    "unavailable": "unavailable",
}
LABEL_OPEN = "Open"


def render_tile(
    *, title: str, value: str, caption: str, kind: str, link: str = "", code: str = ""
) -> str:
    """One "Where this runs" tile: the design system's stat tile (`cards.tile`) plus one link.

    `value` carries its unit ("6,040 functions"), `caption` the provenance and the UTC stamp
    ("18 of 19 families loaded here · counted at boot · 2026-09-22 14:02 UTC"). An unavailable
    tile shows an em dash where the figure would be and `unavailable · <code>` in its meta line
    — the same geometry and vocabulary as the LLM tab's GPU tile, read through `data-kind`.
    """
    if kind not in TILE_STATE_OF:
        raise ValueError(f"unknown tile kind {kind!r}")
    if kind == "unavailable" and not code.strip():
        raise ValueError("an unavailable tile names its code")
    tile = cards.tile(title, value, meta=caption, state=TILE_STATE_OF[kind], code=code)
    action = (
        f'<a class="alg-tile-link" href="{esc(link)}" target="_blank" rel="noopener">'
        f"{LABEL_OPEN}</a>"
        if link
        else ""
    )
    return f'<div class="alg-tile" data-kind="{esc(kind)}">{tile}{action}</div>'


def render_tiles(*tiles: str) -> str:
    """The band: every non-empty tile on one grid, the column count carried by `data-count`."""
    shown = [tile for tile in tiles if tile.strip()]
    return f'<div class="alg-tiles" data-count="{len(shown)}">{"".join(shown)}</div>'


def render_field_message(text: str) -> str:
    """The inline message under one form field; empty text renders nothing."""
    if not text.strip():
        return ""
    return f'<p class="alg-field-msg" role="alert">{esc(text)}</p>'


def render_status_echo(text: str) -> str:
    """The refusal acknowledged beside the action, as `role="status"`.

    One convention for a refusal: the field message under the offending control (`role="alert"`,
    announced) carries the sentence; the status row next to the run button says `STATUS_NOT_RUN`
    — where the eye lands once the page has scrolled to it — never the same sentence twice
    (round 6). Empty text renders nothing."""
    if not text.strip():
        return ""
    return f'<p class="alg-status-echo" role="status">{esc(text)}</p>'


def render_status(chip: str = "", message: str = "", *, echo: str = "") -> str:
    """The one status row under a form: the lane chip (with its meta), a field message (only for
    a control that has no message slot of its own), the refusal's echo (`render_status_echo`,
    beside the run button — every tab's fields carry a `render_field_message` slot under
    them), or an empty live region that takes no space — `TABS_CSS` collapses the empty row
    and the column gap around it, and gives it its 32 px only once something is in it."""
    inner = chip + render_field_message(message) + render_status_echo(echo)
    return f'<div class="alg-status" aria-live="polite">{inner}</div>'


#: The `gr.HTML` wrapper of a code block's caption: no block pads, the editor pulled up under it.
CODE_CAPTION_ROW_CLASS = "alg-code-caption-row"
#: How far the caption row pulls the editor below it up, out of the column's 16 px gap.
CODE_CAPTION_PULL_PX = 8


def render_code_caption(text: str) -> str:
    """The caption above a `gr.Code` block, in place of Gradio's block label with its icon.

    The design system's snippet caption (`cards.snippet_block` draws the same for a snippet in an
    HTML payload): the mono caption face, uppercase, `text-2`. The editor under it passes
    `show_label=False` and `show_line_numbers=False` — its `label` stays, for assistive
    technology — so a code block on the page is read, not edited: no stock label, no gutter.
    Refuses empty text: a caption names its block."""
    if not str(text).strip():
        raise ValueError("a code caption names its block")
    return f'<p class="alg-code-caption">{esc(text)}</p>'


def code_editor(
    gr: Any,
    *,
    value: str,
    language: str,
    caption: str,
    lines: int,
    visible: bool = True,
    interactive: bool = False,
) -> tuple[Any, Any]:
    """``(caption, editor)``: our caption row and the read-only ``gr.Code`` under it.

    One convention for every code block the tabs show (a request, a response, a snippet): the
    caption row (`render_code_caption` in `CODE_CAPTION_ROW_CLASS`) above an editor whose stock
    block label and line-number gutter are off, wrapping lines, no stock buttons (a 44 px Copy
    chip goes beside it). Both are built with the same visibility and a handler that shows or
    hides the editor shows or hides the caption with it.
    """
    caption_html = gr.HTML(
        render_code_caption(caption), elem_classes=[CODE_CAPTION_ROW_CLASS], visible=visible
    )
    editor = gr.Code(
        value,
        language=language,
        label=caption,
        show_label=False,
        show_line_numbers=False,
        lines=lines,
        wrap_lines=True,
        buttons=[],
        interactive=interactive,
        visible=visible,
    )
    return caption_html, editor


def render_note(text: str) -> str:
    return f'<p class="alg-note">{esc(text)}</p>'


def render_empty(title: str, text: str) -> str:
    """The designed empty state (`cards.empty`): a title and one line, no number."""
    return cards.empty(title, text)


#: Skeleton chip widths (px) mirroring the measured card's chips, so the swap does not shift.
SKELETON_CHIP_WIDTHS: tuple[int, ...] = (240, 128, 152, 48, 80, 248, 192)


#: `render_loading_card` states: `loading` while an attempt is running (the pulsing skeleton and
#: the measuring chip), `pending` between attempts (the same geometry, still, with the neutral
#: `not measured yet` chip) — a card never pulses while nothing is being measured.
CARD_STATE_LOADING = "loading"
CARD_STATE_PENDING = "pending"


def render_loading_card(
    *,
    title: str,
    subtitle: str,
    hero_label: str,
    note: str,
    hardware: str,
    ts_utc: str,
    result_lines: int = 2,
    chips: int = len(SKELETON_CHIP_WIDTHS),
    settled: bool = False,
    note_html: str = "",
) -> str:
    """The card while a measurement is still pending: the measured card's geometry, no number.

    Same head, hero slot, result block, chip row and footer as the result card — skeleton blocks
    stand where the figures will land, so the measured card takes exactly this space. `note`
    says what is happening and when the next attempt is; nothing here is a value. `settled`
    is the state between attempts: `data-state="pending"`, no `aria-busy`, no pulse, and the
    neutral `not measured yet` chip instead of the measuring one — quiet, because nothing is
    being measured at that moment. `note_html` is the same note already escaped, for a caller
    that marks a clock reading inside it as a `<time>` element; `note` stays the plain text.
    """
    if not note.strip():
        raise ValueError("a loading card says what it is waiting for")
    note_markup = note_html or esc(note)
    lines = "".join(
        '<span class="alg-skeleton alg-skeleton-line'
        + (" alg-skeleton-short" if index % 2 else "")
        + '"></span>'
        for index in range(result_lines)
    )
    widths = [SKELETON_CHIP_WIDTHS[i % len(SKELETON_CHIP_WIDTHS)] for i in range(chips)]
    lead = cards.status_chip("unavailable", NOT_MEASURED_TEXT) if settled else cards.chip("loading")
    chip_row = lead + "".join(
        f'<span class="alg-skeleton alg-skeleton-chip" style="width:{w}px"></span>'
        for w in widths[1:]
    )
    state = CARD_STATE_PENDING if settled else CARD_STATE_LOADING
    busy = "" if settled else ' aria-busy="true"'
    return (
        f'<article class="alg-card alg-card-loading" data-state="{state}"{busy}>'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{esc(title)}</h2>'
        f'<div class="alg-card-sub">{esc(subtitle)}</div></div>'
        '<div class="alg-hero">'
        '<div class="alg-hero-num"><span class="alg-skeleton alg-skeleton-num"></span></div>'
        f'<div class="alg-hero-label">{esc(hero_label)}</div>'
        "</div></div>"
        f'<div class="alg-result alg-skeleton-lines" aria-hidden="true">{lines}</div>'
        f'<p class="alg-card-note alg-card-pending">{note_markup}</p>'
        f'<div class="alg-chips">{chip_row}</div>'
        f'<div class="alg-card-foot">{esc(hardware)} · {time_or_text(ts_utc)}</div>'
        "</article>"
    )


def permalink(
    tab: str, *, fn: str = "", args: Mapping[str, Any] | None = None, base: str = ""
) -> str:
    """``?tab=play&fn=module.function&args=<json>`` — restored by the shell's Permalink.

    `base` (``https://host``) makes the link absolute; without it the link is relative to the
    page it is shown on, which still works.
    """
    query: dict[str, str] = {"tab": tab}
    if fn:
        query["fn"] = fn
    if args:
        query["args"] = json.dumps(args, separators=(",", ":"), ensure_ascii=False)
    return (base.rstrip("/") + "/" if base else "") + "?" + urlencode(query)


def permalink_request(text: Any) -> tuple[str | None, dict[str, Any] | None]:
    """``(fn, args)`` from the JSON the shell feeds a tab's restore box; anything else is empty."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    try:
        data = json.loads(text)
    except ValueError:
        return None, None
    if not isinstance(data, Mapping):
        return None, None
    fn = data.get("fn")
    args = data.get("args")
    return (
        fn if isinstance(fn, str) and fn else None,
        dict(args) if isinstance(args, Mapping) and args else None,
    )


def permalink_payload(fn: str | None, args: Mapping[str, Any] | None) -> str:
    """The restore box's value: one JSON object the shell writes on page load."""
    return json.dumps({"fn": fn, "args": dict(args) if args else None}, ensure_ascii=False)


#: A read-only single-row link box (the shell's Permalink, the Try tab's Reproduce link), built
#: with `max_lines=1`: Gradio 6.28 renders that as a single-line `<input type="text">`, which
#: never wraps and scrolls sideways on its own, so the box is the 44 px row at every width
#: (round 12: the autogrowing textarea wrapped a two-line URL into 64 px at 375). The class lands
#: on the block and its wrapper alike; its `textarea` rules in `TABS_CSS` — `white-space: pre`,
#: sideways scroll with no scrollbar chrome — hold the same row for a build that still renders
#: the box as a textarea.
LINK_BOX_CLASS = "alg-link-box"
#: Below this width the Try tab's three chip buttons stack one per row, full width, one line each
#: (round 12: at 375 they folded into a 2 + 1 grid with two-line labels).
CHIP_STACK_MAX_WIDTH = 479
#: The client-side copy: writes the first input to the clipboard, relabels the chip.
COPY_JS = (
    "async (text) => { try { await navigator.clipboard.writeText(text ?? ''); return 'Copied'; }"
    " catch (error) { return 'Copy'; } }"
)
LABEL_COPY = "Copy"


def now_utc() -> str:
    return utc_stamp()


# alg-tile / alg-tiles / alg-result / alg-field-msg / alg-note / alg-status / alg-skeleton /
# alg-form classes only; tokens from design.py; 8-pt spacing. Rules that reach a Gradio element
# inside one of our layout classes do so through the class and an element or attribute selector.

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_BODY = "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
_MONO = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
_TARGET = "min-height: var(--alg-target);"
#: The type step below 560 px: titles and hero figures that fit a 375 px column on one line.
PHONE_TITLE = "font-size: 22px; line-height: 28px;"
PHONE_DISPLAY = "font-size: 32px; line-height: 40px;"
#: The status row's height once something is in it; empty, it takes no space at all.
STATUS_ROW_MIN = "min-height: 32px;"
#: The column gap Gradio puts between blocks (`--layout-gap`); an empty status row pulls itself
#: back by exactly this, so Run and the disclosure below sit one gap apart, not three.
BLOCK_GAP_PX = 16
#: A field label: one caption line (16 px) with this gap under it; the block pads 12 px above —
#: 12 + 16 + 4 = 32, on the 8-pt scale.
FIELD_LABEL_GAP_PX = 4
FIELD_LABEL_LINE_PX = 16
FIELD_BLOCK_PAD_PX = 12
#: Where a field's box starts under its row — and the Run button's offset to sit level with it.
FIELD_BOX_OFFSET_PX = FIELD_BLOCK_PAD_PX + FIELD_LABEL_LINE_PX + FIELD_LABEL_GAP_PX
#: A field's message slot always holds one caption line, so a one-line refusal moves nothing.
FIELD_SLOT_PX = 16
#: Below this width the field columns are narrow enough (163 px at 375 and 414, 163 px at
#: 1024 with four fields and Run on one row) for a one-sentence refusal to wrap, so the slot
#: holds two caption lines there (round 11: `Trials A must be a whole number.` wrapped and
#: moved the second row of boxes and Run by 16 px). The same breakpoint as the Governed
#: profile grid and the Ecosystem wrap (`gov_tab.PROFILE_GRID_MAX_WIDTH`, `eco_tab.WRAP_MAX_WIDTH`).
FIELD_SLOT_TWO_LINE_MAX_WIDTH = 1279
FIELD_SLOT_NARROW_PX = 2 * FIELD_SLOT_PX
#: A slot under a field whose column is narrow at every width — the Try form's four fields and
#: Run share one 1,088 px row, so a box is 163 px wide even at 1440 and `Successes A cannot
#: exceed Trials A.` (209 px in the caption face) wraps there too — reserves two caption lines
#: everywhere (`FIELD_SLOT_NARROW_CLASS`, beside `alg-field-slot`). The Playground's and the
#: LLM tab's fields are 456 px or wider above 1279 px, so theirs keep the one line there.
FIELD_SLOT_NARROW_CLASS = "alg-field-slot-narrow"
#: A field's box and label sit inside the block's horizontal padding (`design.BLOCK_PADDING`,
#: 16 px); the message under the box carries the same inset, so it starts at the box's left
#: edge, never at the column's (round 11: x=176 beside a box at 192).
FIELD_BLOCK_INSET_PX = 16
#: The status row of a form (Try, the Playground, LLM kernels): the block carrying this class
#: reserves one caption line under Run, so the refusal's echo fills the line and nothing under
#: the form moves — the field slots' convention, applied to the row beside the action (round
#: 11: the LLM row grew 48 px on a refusal and shifted the panels below). A row that only ever
#: shows a lane chip (Governed) keeps `alg-status-row`: 0 px while empty.
STATUS_SLOT_CLASS = "alg-status-slot"
#: The status row's one sentence beside the action when a field refused the run: distinct
#: from the field message (round 6: the same sentence printed twice, 56–72 px apart).
STATUS_NOT_RUN = "Not run · fix the marked field"

TABS_CSS = stylesheet(
    # A tile is the shared stat tile plus its link: the tile grows to the row's height so every
    # tile in the band shares one bottom edge, the link is a 44 px pill (the 20 px mono line
    # centred in the 44 px target, hairline included) on the left edge.
    rule("alg-tile", "display: flex; flex-direction: column; gap: 8px; align-items: flex-start;"),
    rule("alg-tile", "align-self: stretch; flex: 1 1 auto;", suffix=" .alg-stat"),
    rule(
        "alg-tile-link",
        f"display: inline-flex; align-items: center; justify-content: center;"
        f" font-family: var(--alg-font); {_CAPTION} color: var(--alg-text);"
        " text-decoration: none; border: 1px solid var(--alg-hairline);"
        " border-radius: var(--alg-radius-pill); padding: 0 16px; box-sizing: border-box;"
        " line-height: var(--alg-mono-line); min-inline-size: var(--alg-target);"
        " min-height: var(--alg-target); transition: border-color var(--alg-motion);",
    ),
    rule("alg-tile-link", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule(
        "alg-tile-link",
        "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;",
        suffix=":focus-visible",
    ),
    rule(
        "alg-result",
        f"{_MONO} font-size: var(--alg-mono-size); line-height: var(--alg-mono-line);"
        " background: var(--alg-surface-2); border-radius: var(--alg-radius-input);"
        " padding: 12px 16px; margin: 16px 0 0; overflow: auto; max-height: 288px;"
        " white-space: pre;",
    ),
    rule("alg-field-msg", f"{_CAPTION} color: var(--alg-err); margin: 0;"),
    # The refusal's echo in the status row: the field message's face and colour, `role=status`.
    rule("alg-status-echo", f"{_CAPTION} color: var(--alg-err); margin: 0;"),
    rule("alg-note", f"{_CAPTION} color: var(--alg-text-2); margin: 8px 0 0;"),
    # A code block's caption (`render_code_caption`): the design system's snippet caption above
    # a `gr.Code` whose block label is hidden. The row drops the HTML block's own pads and pulls
    # the editor below it up by `CODE_CAPTION_PULL_PX`, so the caption sits 8 px above its block
    # instead of one whole column gap away.
    rule("alg-code-caption-row", f"padding: 0; margin: 0 0 -{CODE_CAPTION_PULL_PX}px;"),
    rule("alg-code-caption-row", "padding: 0;", suffix=" > div"),
    rule(
        "alg-code-caption",
        f"font-family: var(--alg-font-mono); {_CAPTION} letter-spacing: 0.08em;"
        " text-transform: uppercase; color: var(--alg-text-2); margin: 0;",
    ),
    # The status row: a live region that is 0 px while empty and 32 px once a chip or a message
    # is in it. Gradio's HTML block keeps its own 12 px pads and the column its 16 px gap even
    # around nothing, so the block drops the pads and, while the row is empty, pulls itself up
    # by one gap (the selector reaches the block through its own two wrappers, so the inner
    # `.alg-status-row` on the prose element is left alone).
    rule("alg-status", "display: flex; flex-wrap: wrap; align-items: center; gap: 8px;"),
    rule("alg-status", STATUS_ROW_MIN, suffix=":not(:empty)"),
    rule("alg-status-row", "padding: 0; margin: 0; min-height: 0;"),
    rule("alg-status-row", "padding: 0;", suffix=" > div"),
    rule(
        "alg-status-row",
        f"margin-top: -{BLOCK_GAP_PX}px;",
        suffix=":has(> div > div > .alg-status:empty)",
    ),
    # A field's message slot: always one caption line, 4 px under the box, empty or not — so
    # a refusal fills the line instead of growing the column (round 6: 32–64 px shifts).
    # `elem_classes` land on the block and on its prose wrapper alike, so the pull is scoped to
    # the block (the one with a <div> child) — both pulling would lift the message over the box
    rule("alg-field-slot", f"margin-top: -{BLOCK_GAP_PX - 4}px;", suffix=":has(> div)"),
    rule("alg-field-slot", f"min-height: {FIELD_SLOT_PX}px;", suffix=" > div"),
    # the message starts where the box starts: inside the block's 16 px inset, never at the
    # column's edge (round 11 measured x=176 under a box at 192, 16 under one at 33)
    rule("alg-field-slot", f"margin: 0 {FIELD_BLOCK_INSET_PX}px;", suffix=" .alg-field-msg"),
    # narrow field columns (a phone, or four fields and Run across 1024 px): a sentence wraps
    # to two lines, so the slot reserves both and the row below stays put
    block(
        f"@media (width <= {FIELD_SLOT_TWO_LINE_MAX_WIDTH}px)",
        rule("alg-field-slot", f"min-height: {FIELD_SLOT_NARROW_PX}px;", suffix=" > div"),
    ),
    # a slot in a column that is narrow at every width (Try): two lines everywhere
    rule(FIELD_SLOT_NARROW_CLASS, f"min-height: {FIELD_SLOT_NARROW_PX}px;", suffix=" > div"),
    # A form's status row (`STATUS_SLOT_CLASS`): the reserved caption line under Run. The
    # block drops its pads, pulls itself up like a field slot (4 px under the button) and keeps
    # one 16 px line whether the row is empty or carries the refusal's echo alone; a lane chip
    # in it (a run that happened) takes the 32 px row. `elem_classes` land on the block and on
    # its prose wrapper alike and the row's payload is a <div>, so the pull is scoped to the
    # block by its three-deep chain (block > container > prose > .alg-status) — a wrapper that
    # pulled too would lift the echo 8 px into the button above.
    rule(STATUS_SLOT_CLASS, "padding: 0; margin: 0; min-height: 0;"),
    rule(STATUS_SLOT_CLASS, "padding: 0;", suffix=" > div"),
    rule(
        STATUS_SLOT_CLASS,
        f"margin-top: -{BLOCK_GAP_PX - 4}px;",
        suffix=":has(> div > div > .alg-status)",
    ),
    rule(STATUS_SLOT_CLASS, f"min-height: {FIELD_SLOT_PX}px;", suffix=" > div > div > .alg-status"),
    rule(
        "alg-status",
        f"min-height: {FIELD_SLOT_PX}px;",
        suffix=":has(> .alg-status-echo:only-child)",
    ),
    rule(
        "alg-status-meta",
        f"font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);"
        " font-variant-numeric: tabular-nums;",
    ),
    # Our HTML payloads draw their own surfaces: the wrapper block adds no padding of its own,
    # so a card meets the 16 px page gutter on a phone instead of sitting 40 px in.
    rule(BLOCK_CLASS, "padding: 0;"),
    rule(BLOCK_CLASS, "padding: 0;", suffix=" > div"),
    rule("alg-try-card", "padding: 0;"),
    rule("alg-try-card", "padding: 0;", suffix=" > div"),
    rule("alg-play-card", "padding: 0;"),
    rule("alg-play-card", "padding: 0;", suffix=" > div"),
    rule("alg-where", "padding: 0;"),
    rule("alg-where", "padding: 0;", suffix=" > div"),
    # the Playground's doc line and provenance note: Gradio pads the HTML container inside the
    # block too (round 5: the doc line sat 16 px inside the shared edge at every width)
    rule("alg-fn-doc", "padding: 0;"),
    rule("alg-fn-doc", "padding: 0;", suffix=" > div"),
    rule("alg-provenance", "padding: 0;"),
    rule("alg-provenance", "padding: 0;", suffix=" > div"),
    # The form row is top-aligned: a field whose message slot fills grows downward alone and
    # its siblings and the Run button stay where the pointer found them (round 6: flex-end
    # dragged the three other boxes and Run down by the message's height). Every field label
    # is one 16 px caption line under the block's 12 px pad with a 4 px gap, so the boxes
    # start FIELD_BOX_OFFSET_PX under the row and Run, offset by the same, sits level with them.
    rule("alg-form-row", "align-items: flex-start;"),
    rule(
        "alg-field",
        f"{_CAPTION} display: block; margin: 0 0 {FIELD_LABEL_GAP_PX}px; color: var(--alg-text-2);",
        # Gradio's block title (`BlockTitle`): a bare span in a Dropdown or Radio block, one
        # inside a <label> for a Number box — the data attribute reaches both and nothing else
        suffix=' [data-testid="block-info"]',
    ),
    rule("alg-form-row", f"margin-top: {FIELD_BOX_OFFSET_PX}px;", suffix=" > .alg-run"),
    block(
        f"@media (width <= {PHONE_MAX_WIDTH}px)",
        rule("alg-form-row", "margin-top: 0;", suffix=" > .alg-run"),
    ),
    # Buttons on the grid: 44 px, one 20 px line, no vertical padding (round 6: 48.5 px).
    rule("alg-run", f"{_TARGET} padding-top: 0; padding-bottom: 0; line-height: 20px;"),
    rule("alg-chip-btn", f"{_TARGET} padding-top: 0; padding-bottom: 0; line-height: 20px;"),
    rule(
        "alg-tiles",
        "display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px;"
        " margin: 24px 0 0;",
    ),
    rule(
        "alg-tiles", "grid-template-columns: repeat(2, minmax(0, 1fr));", suffix='[data-count="2"]'
    ),
    rule("alg-tiles", "grid-template-columns: minmax(0, 1fr);", suffix='[data-count="1"]'),
    # Skeletons: surface-2 blocks the size of the figures they stand for; a slow opacity pulse.
    "@keyframes alg-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }",
    rule(
        "alg-skeleton",
        "display: inline-block; background: var(--alg-surface-2);"
        " border-radius: var(--alg-radius-input); animation: alg-pulse 1.6s ease-in-out infinite;",
    ),
    rule("alg-skeleton-num", "width: 128px; height: var(--alg-display-line); vertical-align: top;"),
    rule("alg-skeleton-lines", "display: flex; flex-direction: column; gap: 0;"),
    rule(
        "alg-skeleton-line",
        "height: 12px; width: 40%; background: var(--alg-surface); margin: 4px 0;",
    ),
    rule("alg-skeleton-short", "width: 28%;"),
    rule(
        "alg-skeleton-chip", "height: 26px; max-width: 100%; border-radius: var(--alg-radius-pill);"
    ),
    rule("alg-card-pending", f"{_BODY} color: var(--alg-text); margin: 12px 0 0;"),
    # Between attempts nothing is being measured: the settled card keeps the geometry, still.
    rule(
        "alg-card", "animation: none;", suffix=f'[data-state="{CARD_STATE_PENDING}"] .alg-skeleton'
    ),
    block(
        "@media (prefers-reduced-motion: reduce)",
        rule("alg-skeleton", "animation: none;"),
        # the tile link's border fade: this sheet loads after the chrome sheet's reduced-motion
        # block, so the rule is repeated here where it can win the tie
        rule("alg-tile-link", "transition: none;"),
    ),
    # The Playground form: one surface, each field a row with its label, help and control. No
    # horizontal padding of its own: the fields' Gradio blocks carry the 16 px inset, so their
    # boxes and labels share one left edge with the dropdown card above (round 8).
    rule(
        "alg-form",
        "background: var(--alg-surface); border: 1px solid var(--alg-hairline);"
        " border-radius: var(--alg-radius-card); padding: 16px 0; gap: 16px;"
        " margin: 16px 0 0;",
    ),
    rule("alg-field", "gap: 4px;"),
    rule(
        "alg-field",
        "background: transparent; border: 0; box-shadow: none; padding: 0;",
        suffix=" > div",
    ),
    rule("alg-copy-row", "justify-content: flex-end; gap: 8px;"),
    rule("alg-copy-row", f"{_TARGET} min-width: 96px; flex-grow: 0;", suffix=" button"),
    # a link box is one row: the URL scrolls sideways instead of wrapping, no scrollbar chrome
    # (Gradio 6.28 renders a `max_lines=1` box as an `<input>`; these hold for a textarea)
    rule(
        LINK_BOX_CLASS,
        "white-space: pre; overflow-x: auto; overflow-y: hidden; scrollbar-width: none;",
        suffix=" textarea",
    ),
    rule(LINK_BOX_CLASS, "display: none;", suffix=" textarea::-webkit-scrollbar"),
    # the single-line input is the 44 px control every box is (measured 48: the body line inside
    # 12 px pads), and its label the caption line every field label is (`alg-field` below), so
    # the box starts FIELD_BOX_OFFSET_PX under its block and a chip beside it sits level with it
    rule(
        LINK_BOX_CLASS,
        f"{_TARGET} height: var(--alg-target); padding-top: 0; padding-bottom: 0;"
        " box-sizing: border-box; line-height: 20px;",
        suffix=' input[type="text"]',
    ),
    rule(
        LINK_BOX_CLASS,
        f"{_CAPTION} display: block; margin: 0 0 {FIELD_LABEL_GAP_PX}px; color: var(--alg-text-2);",
        suffix=' [data-testid="block-info"]',
    ),
    # the Try tab's chip row on a narrow phone: one chip per row, full width, one-line labels
    block(
        f"@media (width <= {CHIP_STACK_MAX_WIDTH}px)",
        rule("alg-chip-row", "flex-direction: column; align-items: stretch;"),
        rule(
            "alg-chip-row",
            "flex: 0 0 auto; width: 100%; min-width: 100%; white-space: nowrap;",
            suffix=" > button",
        ),
    ),
    block(
        "@media (width <= 768px)",
        rule("alg-tiles", "grid-template-columns: minmax(0, 1fr);"),
        rule("alg-tiles", "grid-template-columns: minmax(0, 1fr);", suffix='[data-count="2"]'),
    ),
    block(
        "@media (width <= 560px)",
        rule("alg-try-card", PHONE_TITLE, suffix=" .alg-card-title"),
        rule("alg-try-card", PHONE_DISPLAY, suffix=" .alg-hero-num"),
        rule("alg-play-card", PHONE_TITLE, suffix=" .alg-card-title"),
        rule("alg-play-card", PHONE_DISPLAY, suffix=" .alg-hero-num"),
        # One column below 560 px: the title keeps its line, the figure sits under it, left.
        rule(
            "alg-try-card",
            "flex-direction: column; align-items: stretch;",
            suffix=" .alg-card-head",
        ),
        rule("alg-try-card", "text-align: left;", suffix=" .alg-hero"),
        rule(
            "alg-play-card",
            "flex-direction: column; align-items: stretch;",
            suffix=" .alg-card-head",
        ),
        rule("alg-play-card", "text-align: left;", suffix=" .alg-hero"),
        rule("alg-skeleton-num", "height: 40px; width: 96px;"),
        rule("alg-form", "padding: 16px 0;"),
        rule("alg-try-card", "padding: 16px;", suffix=" .alg-card"),
        rule("alg-play-card", "padding: 16px;", suffix=" .alg-card"),
        rule("alg-tile", "padding: 16px;", suffix=" .alg-stat"),
    ),
)
