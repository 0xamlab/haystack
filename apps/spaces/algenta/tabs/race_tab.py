"""Races — the honest races: seeded S/M/L cells, the rulebook, qualification, a leaderboard.

A candidate is offered when its incumbent package is installed and its family loaded; the tab
names what is not offered and why. Running a cell measures the Hub kernel against the incumbent
in one lane job (``races.run_race`` inside ``Lane.submit``), so the pure-Python incumbent never
shares the CPU with another native call. What the card shows depends on ``qualified.json`` from
the results Dataset: a qualified cell is a race (ratio hero, or the hold-and-disclose card when
the incumbent won this run); anything else is parity plus both latencies, its measured ratio
printed with the status `not qualified` (never as the hero).
With no qualified list the tab says so — no race has qualified on this hardware yet.

The page is the result card: the empty card before a run (naming the rows a run fills), the
loading card the instant Run race is pressed — carrying the lane position in its own text, so
no status row is reserved above the card — then the result, whose lane table carries every
rulebook statistic (median, MAD, CV, P95, min – max) and the cell's permalink pill directly
beneath it. The pill appears with a measured result and only then: a cell the rulebook did not
record, a held cell or a card with a code has nothing to link to, so no pill is drawn under it;
changing the candidate or the size returns the column to the empty card so a stale result never
sits under a new selection. The card's subtitle is words (the workload and the incumbent); the
kernel revision (``races.revision_label`` — the snapshot that loaded, never the capped sha when
they differ) and the exact calls live in the Reproduce disclosure.

The form is one line, the Try tab's row: the candidate and the size each in their own field
column, Run race on the boxes' baseline (fix round 5 — the size options used to carry the whole
workload description, which stacked them three high and left Run race bottom-aligned under
166 px of nothing). The size radio reads S · M · L; the workload each size means is the card's
title the moment a size is picked (``opening_card(cand, size)``: "Levenshtein distance · 600 ×
600 characters"), the result card's title after a run, and the Reproduce disclosure lists every
size per candidate.

The board below ("Measured on this Space") lists what this container measured: every measured
cell becomes a row with its kind — a qualified race the kernel won is a ``race`` row with its
ratio; a cell that is not qualified is a ``parity`` row (both latencies, the parity label, "not
a race" where a ratio would be); a held cell (a qualified race the incumbent won) is disclosed on
the card and never a row. One responsive table (row cards on a phone) whose ``where`` column
tells a row measured in this container from one published elsewhere (the Dataset rows arrive in
M4). While ``qualified.json`` is empty the board says so in one sentence — "No qualified race yet
· every ratio above is measured, none is qualified" — above its rows or alone; "Nothing measured
yet" is said only when nothing has been measured, never beside a measured card. The board is
re-rendered on every page load from the container's ``Board``, so a fresh visitor sees the cells
measured here since the page was built, not the first paint. Every
measured cell has a permalink — ``?tab=race&fn=<module.function>&args={"size": "M"}`` — and
the shell's permalink protocol restores the candidate and size on load, but only for a cell
this container can actually run: ``permalink_applied`` tells the shell exactly what the tab
applied (the candidate's function and the size shown — the link's when it is S, M or L, the
candidate's default otherwise; nothing when the function is not a candidate offered here), so
the box the shell writes never promises a state the page did not restore.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from algenta_spaces import bench, cards, lane
from algenta_spaces.css import PHONE_MAX_WIDTH, block, rule, stylesheet

import races
from tabs import TAB_RACE, Deps, TabSpec, common
from tabs.llm_tab import render_empty_card, render_loading_card

log = logging.getLogger(__name__)

FEATURE = "races"
API_NAMES = ("race_sizes", "race_run")
LABEL_CANDIDATE = "Race"
LABEL_SIZE = "Size"
LABEL_RUN = "Run race"
LABEL_HOW = "How this is measured"
LABEL_REPRODUCE = "Reproduce"
LABEL_BOARD = "Measured on this Space"
LABEL_LINK = "Link to this cell"
NOT_OFFERED = "Not offered here"
#: The two reasons `races.offers` records, in words a visitor reads (no distribution or
#: repository id in primary copy); `races.Offer.reason` keeps the exact package for the log.
REASON_NOT_INSTALLED = "its reference library is not installed here"
REASON_NOT_LOADED = "its kernel family did not load here"
NO_QUALIFIED = (
    "No race has qualified on this hardware yet — every cell runs as a parity check with both "
    "latencies."
)
QUALIFICATION_FILE_LABEL = "Qualification file:"
#: The lead of the qualified note: this Space's own file, or another Space's of the same
#: hardware class (round 10: staging's `qualified.json` read as "on this hardware" here).
QUALIFIED_HERE = "Qualified on this hardware"
QUALIFIED_BY = "Qualified on this hardware class by {writer}"
#: A measured cell the rulebook has not qualified: its ratio is printed as the figure it is,
#: with this status — never as the hero, never as a sentence that denies the two latencies
#: beside it (round 6: a 62× kernel win read "not a race" in the ratio column).
NOT_QUALIFIED_TEXT = "not qualified"
SLOWER_TEXT = "slower"
NO_CANDIDATES = "No race can run here"
NO_CANDIDATES_TEXT = "No incumbent package is installed beside a loaded family."
#: The board while nothing has been measured in this container (only said when it is true).
NOTHING_MEASURED = "Nothing measured yet"
NOTHING_MEASURED_TEXT = (
    "Every measured cell appears here; a qualified race the kernel wins is a race row."
)
#: The board's one sentence while `qualified.json` is empty: what its rows are and are not.
NO_QUALIFIED_BOARD = "No qualified race yet · every ratio above is measured, none is qualified"
EMPTY_TEXT = "Pick a size and press Run race; both lanes are measured on this machine."
LOADING_TEXT = f"Measuring both lanes on this machine under rulebook v{bench.RULEBOOK_VERSION}."
ROW_KEYS = ("algenta", "incumbent", "parity")
WHERE_HERE = "measured here"
WHERE_PUBLISHED = "published elsewhere"
PARAM_SIZE = "size"
BOARD_HEADERS: tuple[str, ...] = (
    "when (UTC)",
    "race",
    "size",
    "algenta",
    "incumbent",
    "ratio",
    "parity",
    "n",
    "where",
)
_NUMERIC_COLUMNS = frozenset({"algenta", "incumbent", "ratio", "n"})

#: Rulebook v0.4's inner batch in the shared card's one sentence (`cards.HOW_TIMED`), so How
#: this is measured and the card's `n = 21 × k calls` chip say the same thing on every tab.
HOW_TIMED: str = getattr(cards, "HOW_TIMED", "")
HOW_MEASURED = (
    f"Rulebook v{bench.RULEBOOK_VERSION}: a correctness gate compares both lanes on the seeded "
    f"workload before anything is timed; {bench.WARMUPS} warm-ups are discarded; "
    f"{bench.REPEATS_FAST} interleaved repeats when a warm call takes under "
    f"{bench.FAST_CALL_MS:.0f} ms, else {bench.REPEATS_SLOW}"
    + (f"; {HOW_TIMED}, k chosen per lane" if HOW_TIMED else "")
    + f". The card shows, per lane, the median, the P95 (the maximum under {bench.P95_MIN_N} "
    "samples), the min–max "
    f"range, the median absolute deviation and the coefficient of variation, and the ratio best "
    f"incumbent over algenta when the cell is a race. A spread above {bench.CV_MAX:.0%} on "
    f"either lane, or a mean more than {bench.CV_MAX:.0%} off the median, is noisy and not "
    "recorded; the foot prints the machine's 1-minute load average at the time. A cell is a "
    "race only after three recorded runs on this hardware, within five presses (a noisy press "
    "is not a run), were each won by the kernel — the qualification file's own rule and date "
    "are printed above the card; a qualified "
    "race the incumbent wins live is held and disclosed, not recorded; every other measured "
    "cell is a row of the board below, a parity row unless it is a race. Kernel timings include "
    "the JSON marshalling across the C ABI."
)


# ---------------------------------------------------------------------------
# State computed at boot
# ---------------------------------------------------------------------------


@dataclass
class RaceState:
    offers: list[races.Offer]
    qualified: races.Qualified
    board: races.Board
    hardware: str
    hardware_id: str
    space_id: str = ""
    #: family -> `LoadedKernel.label()` (`algenta-text@fb2cab4`) for the Reproduce disclosure.
    kernel_labels: Mapping[str, str] = field(default_factory=dict)

    @property
    def available(self) -> list[races.Offer]:
        return [o for o in self.offers if o.available]

    @property
    def unavailable(self) -> list[races.Offer]:
        return [o for o in self.offers if not o.available]

    def offer(self, race_id: str) -> races.Offer | None:
        return next((o for o in self.offers if o.candidate.id == race_id), None)

    def offered(self, race_id: str) -> races.Candidate | None:
        """The candidate when this container can run it, else None."""
        offer = self.offer(race_id)
        return offer.candidate if offer is not None and offer.available else None


def build_state(
    deps: Deps,
    *,
    fetch_json: Any = common.fetch_json,
    board: races.Board | None = None,
) -> RaceState:
    hardware = common.hardware_line(deps)
    hw_id = common.hardware_id()
    labels = {}
    for cand in races.CANDIDATES:
        loaded = deps.kernel(cand.family)
        if loaded is not None:
            labels[cand.family] = races.revision_label(loaded)
    return RaceState(
        offers=races.offers(deps.kernels),
        qualified=races.load_qualified(fetch_json, env=deps.env, hardware_id=hw_id),
        board=board if board is not None else races.Board(env=deps.env),
        hardware=hardware,
        hardware_id=hw_id,
        space_id=str(deps.env.get("SPACE_ID", "") or deps.facts.get("space_id", "") or ""),
        kernel_labels=labels,
    )


def candidate_choices(state: RaceState) -> list[tuple[str, str]]:
    return [(o.candidate.title, o.candidate.id) for o in state.available]


def size_choices(cand: races.Candidate) -> list[tuple[str, str]]:
    """`S · M · L` — the radio's three options, short enough to share one line with the
    candidate box and Run race; what each size means is the card's title (`opening_card`)."""
    return [(size.key, size.key) for size in cand.sizes]


def size_line(cand: races.Candidate) -> str:
    """`S 300 × 300 characters · M 600 × 600 characters · L 1,000 × 1,000 characters`."""
    return " · ".join(f"{size.key} {size.label}" for size in cand.sizes)


def cell_title(cand: races.Candidate, size_key: str | None) -> str:
    """`Levenshtein distance · 600 × 600 characters` — the candidate and the workload the size
    means, the same title the result card carries; the candidate alone without a size."""
    if size_key is None or size_key not in races.SIZE_KEYS:
        return cand.title
    return f"{cand.title} · {cand.size(size_key).label}"


def offer_reason(offer: races.Offer) -> str:
    """Why a candidate is not offered, in words: `races.offers` records the package or the
    family (data for the log); the page says which kind of thing is missing."""
    if offer.available:
        return ""
    return REASON_NOT_INSTALLED if not offer.incumbent_version else REASON_NOT_LOADED


def not_offered_note(state: RaceState) -> str:
    if not state.unavailable:
        return ""
    parts = [f"{o.candidate.title} ({offer_reason(o)})" for o in state.unavailable]
    return common.render_note(f"{NOT_OFFERED}: " + " · ".join(parts))


def qualified_lead(qualified: races.Qualified, space_id: str) -> str:
    """`Qualified on this hardware` when this Space wrote the file, or the file names no
    writer; `Qualified on this hardware class by <space>` when another Space did — the same
    hardware class (`hardware_id` matched, or the list would be empty), another writer."""
    writer = qualified.file_space_id
    if writer and writer != space_id:
        return QUALIFIED_BY.format(writer=writer)
    return QUALIFIED_HERE


def qualified_note(state: RaceState) -> str:
    """Which candidates are qualified here — and who qualified them, when it was another Space
    (`qualified_lead`) — then the file's own rule and date (round 5: the method text promised
    nightly wins the file never recorded — the file speaks for itself)."""
    if state.qualified.empty:
        return common.render_note(NO_QUALIFIED)
    lead = qualified_lead(state.qualified, state.space_id)
    note = common.render_note(f"{lead}: " + qualified_cells_text(state.qualified))
    return note + qualification_source_note(state.qualified)


def qualified_cells_text(qualified: races.Qualified) -> str:
    """`Betweenness centrality (M, L) · Levenshtein distance (S, L)` — every qualified cell
    by candidate, its sizes in S · M · L order; a candidate qualified at every size (the
    list-of-ids file shape) is named alone (round 6: the note named Levenshtein while the
    board called its M cell not a race — the note now says which cells)."""
    by_race: dict[str, set[str]] = {}
    for race, size in qualified.cells:
        by_race.setdefault(race, set()).add(size)
    parts = []
    for race in sorted(
        by_race, key=lambda r: races.CANDIDATES_BY_ID[r].title if r in races.CANDIDATES_BY_ID else r
    ):
        cand = races.CANDIDATES_BY_ID.get(race)
        if cand is None:
            continue
        sizes = by_race[race]
        if races.ANY_SIZE in sizes:
            parts.append(cand.title)
        else:
            ordered = [key for key in races.SIZE_KEYS if key in sizes]
            parts.append(f"{cand.title} ({', '.join(ordered)})")
    return " · ".join(parts)


def qualification_source_note(qualified: races.Qualified) -> str:
    """`Qualification file: <its rule> · written <its stamp>` — only what the file says."""
    parts = []
    if qualified.rule:
        parts.append(qualified.rule)
    if qualified.generated_utc:
        parts.append(f"written {qualified.generated_utc}")
    if not parts:
        return ""
    return common.render_note(QUALIFICATION_FILE_LABEL + " " + " · ".join(parts))


def reproduce_note(state: RaceState) -> str:
    """Machine, seed, sources — and the exact call each offered candidate races, by name."""
    lines = [
        f"machine {state.hardware}",
        f"hardware id {state.hardware_id}",
        f"seed {races.BASE_SEED}",
        f"qualified list {state.qualified.source or races.QUALIFIED_URL_DEFAULT}"
        + (f" · {state.qualified.error}" if state.qualified.error else "")
        + f" · read {state.qualified.fetched_utc}",
        f"results {state.board.path}" + ("" if state.board.writable else " · not writable here"),
    ]
    for o in state.available:
        kernel = state.kernel_labels.get(o.candidate.family, "")
        at = f" ({kernel})" if kernel else ""
        lines.append(f"{o.candidate.title}: {o.candidate.qualname}{at} vs {o.incumbent_pin}")
        lines.append(f"{o.candidate.title} sizes: {size_line(o.candidate)}")
    return "".join(common.render_note(line) for line in lines)


# ---------------------------------------------------------------------------
# The empty card, the permalink and the leaderboard
# ---------------------------------------------------------------------------


def opening_card(cand: races.Candidate | None, size_key: str | None = None) -> str:
    """The empty card before a run: the candidate and the workload the chosen size means as the
    title (`cell_title`), and the rows a run fills."""
    if cand is None:
        return render_empty_card(NO_CANDIDATES, NO_CANDIDATES_TEXT)
    return render_empty_card(cell_title(cand, size_key), EMPTY_TEXT, rows=ROW_KEYS)


def lane_text(ticket: lane.Ticket) -> str:
    """``queued · 2 ahead · about 3 s`` or ``running now`` — the lane position, as words the
    loading card carries itself (no status row is reserved above the card)."""
    if ticket.position <= 0:
        return "running now"
    ahead = "1 ahead" if ticket.position == 1 else f"{ticket.position} ahead"
    return f"queued · {ahead} · about {max(1, round(ticket.eta_s))} s"


def loading_card(cand: races.Candidate, size: races.Size, position: str = "") -> str:
    detail = f"{position} · {LOADING_TEXT}" if position else LOADING_TEXT
    return render_loading_card(f"{cand.title} · {size.label}", detail)


def candidate_for(fn: str | None) -> races.Candidate | None:
    """The candidate whose `module.function` a permalink names, or None."""
    if not fn:
        return None
    return next((c for c in races.CANDIDATES if c.qualname == fn), None)


def cell_link(cand: races.Candidate, size_key: str) -> str:
    """`?tab=race&fn=text.fuzzy.levenshtein_distance&args={"size":"M"}`."""
    if size_key not in races.SIZE_KEYS:
        raise ValueError(f"size must be one of {races.SIZE_KEYS}, got {size_key!r}")
    return common.permalink(TAB_RACE, fn=cand.qualname, args={PARAM_SIZE: size_key})


def link_html(cand: races.Candidate | None, size_key: str | None) -> str:
    """The 44 px permalink pill for one cell, in its own row under the result card; nothing when
    the cell is not restorable."""
    if cand is None or size_key not in races.SIZE_KEYS:
        return ""
    return (
        '<div class="alg-race-permalink">'
        f'<a class="alg-race-link" href="{common.esc(cell_link(cand, size_key))}">{LABEL_LINK}</a>'
        "</div>"
    )


@dataclass(frozen=True)
class Restore:
    """What a permalink restores: the candidate, its size choices, the size, the empty card."""

    race_id: str
    size_choices: list[tuple[str, str]]
    size: str
    card: str


def applied_size(cand: races.Candidate, args: Mapping[str, Any] | None) -> str:
    """The size a link restores for `cand`: the link's when it is one of S, M or L, else the
    candidate's default — what the radio will show, so what the permalink box may promise."""
    size = str((args or {}).get(PARAM_SIZE, "") or "")
    return size if size in races.SIZE_KEYS else cand.default_size


def restore_values(
    state: RaceState, fn: str | None, args: Mapping[str, Any] | None
) -> Restore | None:
    """The restorable state a link names, or None when this container cannot run that cell."""
    cand = candidate_for(fn)
    if cand is None or state.offered(cand.id) is None:
        return None
    size = applied_size(cand, args)
    return Restore(cand.id, size_choices(cand), size, opening_card(cand, size))


def row_where(row: Mapping[str, Any], space_id: str) -> str:
    """`measured here` for this container's rows, `published elsewhere` for the Dataset's."""
    origin = str(row.get("space_id", "") or "")
    return WHERE_HERE if not origin or origin == space_id else WHERE_PUBLISHED


def ratio_text(algenta_ms: float, incumbent_ms: float) -> str:
    """`64.5× · not qualified` when the kernel was faster, `15.2× slower · not qualified` when
    the incumbent was, `even · not qualified` at parity: the measured figure with its status."""
    if algenta_ms <= 0 or incumbent_ms <= 0:
        return NOT_QUALIFIED_TEXT
    ratio = incumbent_ms / algenta_ms
    if ratio > 1.0:
        return f"{cards.fmt_ratio(ratio)} · {NOT_QUALIFIED_TEXT}"
    if ratio < 1.0:
        return f"{cards.fmt_ratio(1.0 / ratio)} {SLOWER_TEXT} · {NOT_QUALIFIED_TEXT}"
    return f"even · {NOT_QUALIFIED_TEXT}"


def parity_label(cell: bench.CellResult) -> str:
    """The result card's label for an unqualified cell (`cards.render_result_card`'s
    `parity_label`): the same figure-with-status the board prints."""
    ours = cell.lane(bench.SIDE_ALGENTA)
    theirs = cell.lane(bench.SIDE_INCUMBENT)
    if ours is None or theirs is None:
        return NOT_QUALIFIED_TEXT
    return ratio_text(ours.median_ms, theirs.median_ms)


def row_ratio(row: Mapping[str, Any]) -> str:
    """The ratio column: the figure for a race row; for a parity row the measured figure with
    its status (`ratio_text`) — the two latencies beside it are facts, and the column never
    contradicts them; only the qualification is withheld."""
    if races.row_kind(row) == races.ROW_KIND_RACE:
        return cards.fmt_ratio(float(row["ratio"]))
    return ratio_text(
        float(row.get("algenta_median_ms") or 0.0), float(row.get("incumbent_median_ms") or 0.0)
    )


def board_rows(state: RaceState) -> list[list[Any]]:
    rows = []
    for row in state.board.rows():
        cand = races.CANDIDATES_BY_ID.get(str(row["duel_id"]))
        rows.append(
            [
                row["ts_utc"],
                cand.title if cand else row["duel_id"],
                row["size"],
                cards.fmt_ms(float(row["algenta_median_ms"])),
                cards.fmt_ms(float(row["incumbent_median_ms"])),
                row_ratio(row),
                row["parity"],
                int(row["n"]),
                row_where(row, state.space_id),
            ]
        )
    return rows


#: The board's table is the design system's (`cards.TABLE_CLASS`): hairline rows, numbers
#: right-aligned in tabular numerals (`TABLE_NUM_CLASS`), one row card per row on a phone
#: (`TABLE_STACK_CLASS`) with the race's name first (`TABLE_LEAD_CLASS`). Its four-class
#: rules beat Gradio's prose table borders, which the board — outside any `alg-card` — would
#: otherwise show (fix round 5 measured a dark outer border and header rule on the first row).
BOARD_TABLE_CLASSES = f"{cards.TABLE_CLASS} {cards.TABLE_STACK_CLASS} alg-board-table"

#: The phone fold (the Ecosystem table's): on a phone the board opens on this many row cards —
#: the newest first, so the visitor's own cell is always among them — and the 44 px control
#: under it shows the rest. Every row stays in the DOM and in the API at every width; the fold
#: is the stylesheet's, keyed by `BOARD_ALL_ATTR` on the board's block
#: (`gr.HTML(elem_classes=[BOARD_BLOCK_CLASS])`), so a board re-rendered after a run keeps the
#: choice. The control exists only while the board has a row to hide (`:has`), and its label
#: carries no count, so a new row never leaves a stale number under the table.
BOARD_PHONE_ROWS = 6
BOARD_BLOCK_CLASS = "alg-race-board"
BOARD_ALL_ATTR = "data-alg-all"
BOARD_MORE_CLASS = "alg-board-more"
BOARD_SHOW_ALL = "Show all rows"
BOARD_SHOW_FEWER = f"Show the first {BOARD_PHONE_ROWS} rows"


def board_more_js() -> str:
    """The control's client-side click: toggle `BOARD_ALL_ATTR` on every element carrying
    `BOARD_BLOCK_CLASS`, mirror the state in the control's `aria-expanded`, and answer the label
    for the new state (Gradio writes it back)."""
    return (
        "() => {"
        f" const blocks = document.querySelectorAll('.{BOARD_BLOCK_CLASS}');"
        f" const on = blocks.length > 0 && !blocks[0].hasAttribute('{BOARD_ALL_ATTR}');"
        f" blocks.forEach((b) => b.toggleAttribute('{BOARD_ALL_ATTR}', on));"
        f" document.querySelectorAll('button.{BOARD_MORE_CLASS}').forEach((b) =>"
        " b.setAttribute('aria-expanded', on ? 'true' : 'false'));"
        f" return on ? {json.dumps(BOARD_SHOW_FEWER)} : {json.dumps(BOARD_SHOW_ALL)};"
        " }"
    )


def _board_cell(header: str, value: Any) -> str:
    classes = ["alg-board-cell"]
    if header in _NUMERIC_COLUMNS:
        classes.append(cards.TABLE_NUM_CLASS)
    if header == "race":
        classes.append(cards.TABLE_LEAD_CLASS)
    text = f"{value:,}" if isinstance(value, int) else common.esc(value)
    if header == "where":
        text = common.chip(str(value))
    return f'<td class="{" ".join(classes)}" data-label="{common.esc(header)}">{text}</td>'


def _board_head(header: str) -> str:
    classes = [cards.TABLE_NUM_CLASS] if header in _NUMERIC_COLUMNS else []
    attrs = f' class="{" ".join(classes)}"' if classes else ""
    return f'<th scope="col"{attrs}>{common.esc(header)}</th>'


def board_note(state: RaceState, rows: Sequence[Sequence[Any]]) -> str:
    """The board's one line, true of what it lists: while nothing is qualified, that every cell
    is a parity panel (with or without rows); with rows and a qualified list, nothing; without
    rows and with a qualified list, that nothing has been measured yet."""
    if state.qualified.empty:
        return NO_QUALIFIED_BOARD
    if not rows:
        return f"{NOTHING_MEASURED} — {NOTHING_MEASURED_TEXT}"
    return ""


def render_board(state: RaceState) -> str:
    """The board: its title, its one true line (`board_note`) and, with rows, one responsive
    table of every cell this container measured — never "Nothing measured yet" beside a
    measured card, never an empty grid."""
    rows = board_rows(state)
    note = board_note(state, rows)
    note_html = f'<p class="alg-note alg-board-note">{common.esc(note)}</p>' if note else ""
    if not rows:
        return (
            f'<section class="alg-board" aria-label="{LABEL_BOARD}">'
            f'<h3 class="alg-board-title">{LABEL_BOARD}</h3>'
            f"{note_html}"
            "</section>"
        )
    head = "".join(_board_head(h) for h in BOARD_HEADERS)
    body = "".join(
        "<tr>"
        + "".join(_board_cell(h, v) for h, v in zip(BOARD_HEADERS, row, strict=True))
        + "</tr>"
        for row in rows
    )
    count = f"{len(rows)} row" if len(rows) == 1 else f"{len(rows)} rows"
    return (
        f'<section class="alg-board" aria-label="{LABEL_BOARD}">'
        f'<div class="alg-board-head"><h3 class="alg-board-title">{LABEL_BOARD}</h3>'
        f"{common.chip(count)}</div>"
        f"{note_html}"
        f'<table class="{BOARD_TABLE_CLASSES}">'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody data-golden="mask">{body}</tbody></table>'
        "</section>"
    )


def board_html(state: RaceState) -> str:
    return render_board(state)


# ---------------------------------------------------------------------------
# Running one cell
# ---------------------------------------------------------------------------


@dataclass
class Outcome:
    card: str | None = None
    rows: list[list[Any]] | None = None
    board: str | None = None


def render_run(state: RaceState, run: races.RaceRun) -> str:
    """The card for a finished cell: race, not-a-race, held or not recorded — the shared result
    card, whose lane table carries median, MAD, CV, P95 and min – max per lane (one table, one
    place for the rulebook's spread), with the cell's permalink pill beneath the card when the
    cell was measured. A `noisy — not recorded` card has no measurement to link to, so it
    carries no pill; the held card (a qualified race the incumbent won) is measured and does.

    The card's subtitle is `RaceRun.caption` — the workload and the incumbent in words; the
    kernel revision and the exact calls (`RaceRun.subtitle`) are in the Reproduce disclosure."""
    last = state.board.last_win(run.candidate.id, run.size.key)
    card = cards.render_result_card(
        run.cell,
        title=run.title,
        hardware=state.hardware,
        subtitle=run.caption,
        race=run.qualified,
        last_win_ts=str(last["ts_utc"]) if last else "",
        parity_label=parity_label(run.cell),
    )
    if not run.cell.measured:
        return card
    return card + link_html(run.candidate, run.size.key)


def record_run(state: RaceState, run: races.RaceRun, deps: Deps) -> bool:
    """Every measured cell becomes a row of its kind (`races.RaceRun.row_kind`): a qualified
    win a race row, an unqualified cell a parity row. A held cell (a qualified race the
    incumbent won) and a cell the rulebook did not record become no row."""
    if run.row_kind is None:
        return False
    kernel = deps.kernel(run.candidate.family)
    row = races.row_from_run(
        run,
        hardware=state.hardware,
        hardware_id=state.hardware_id,
        space_id=state.space_id,
        harness_commit=str(deps.facts.get("git_sha", "") or ""),
        wheel_sha=races.kernel_revision(kernel) if kernel is not None else "",
    )
    state.board.append(row)
    return True


def run_cell(
    deps: Deps, state: RaceState, race_id: str, size_key: str, request: Any = None
) -> Iterator[Outcome]:
    offer = state.offer(race_id)
    if offer is None or not offer.available:
        title = offer.candidate.title if offer else race_id
        hint = offer.reason if offer else f"no race candidate {race_id!r}"
        yield Outcome(
            card=cards.render_unavailable_card(
                title=title, error_code="race_not_offered", hint=hint, hardware=state.hardware
            )
        )
        return
    cand = offer.candidate
    title = cand.title
    if size_key not in races.SIZE_KEYS:
        yield Outcome(
            card=cards.render_unavailable_card(
                title=title,
                error_code="unknown_size",
                hint=f"size must be one of {', '.join(races.SIZE_KEYS)}",
                hardware=state.hardware,
            )
        )
        return
    kernel = deps.kernel(cand.family)
    if kernel is None:
        yield Outcome(card=common.no_kernel_card(title, cand.family, deps))
        return
    if not deps.feature_on(FEATURE):
        yield Outcome(card=common.switched_off_card(title, state.hardware))
        return
    decision = common.check_limit(deps, request)
    if decision is not None and not decision.allowed:
        yield Outcome(card=common.limited_card(title, decision, state.hardware))
        return
    qualified = state.qualified.is_qualified(cand.id, size_key)
    try:
        ticket = deps.lane.submit(
            races.run_race,
            cand,
            size_key,
            kernel,
            qualified=qualified,
            incumbent_pin=offer.incumbent_pin,
            budget_s=common.RACE_BUDGET_S,
            label=f"race {cand.id} {size_key}",
        )
        yield Outcome(card=loading_card(cand, cand.size(size_key), lane_text(ticket)))
        run = ticket.result()
    except Exception as exc:  # lane refusals and build errors are cards with a code
        log.warning("race %s %s failed: %s", cand.id, size_key, exc)
        code_exc = exc
        if isinstance(exc, races.RaceError):
            code_exc = _as_hub_error(exc)
        yield Outcome(card=common.error_card(title, code_exc, state.hardware))
        return
    recorded = record_run(state, run, deps)
    yield Outcome(
        card=render_run(state, run),
        rows=board_rows(state) if recorded else None,
        board=render_board(state) if recorded else None,
    )


def _as_hub_error(exc: races.RaceError) -> Exception:
    from algenta_spaces.hubkernel import HubKernelCallError

    return HubKernelCallError(exc.code, exc.message)


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"

# alg-board-*, alg-race-card, alg-race-link and alg-race-permalink only; the board's table is
# the design system's alg-table (cards.CARD_CSS), the result card is cards' alg-card.
RACE_CSS = stylesheet(
    rule("alg-board", "margin: 24px 0 0;"),
    rule(
        "alg-board-head",
        "display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 16px;",
    ),
    rule(
        "alg-board-title",
        f"{_CAPTION} font-family: var(--alg-font-mono); letter-spacing: 0.08em;"
        " text-transform: uppercase; color: var(--alg-text-2); margin: 0;",
    ),
    rule("alg-board-cell", "color: var(--alg-text);"),
    # The board's one line sits under its head and, with rows, 8 px above the table.
    rule("alg-board-note", "margin: 8px 0 0;"),
    # The phone fold: the board's block hides every row past the first BOARD_PHONE_ROWS until
    # the control under it sets BOARD_ALL_ATTR; the control itself exists only on a phone and
    # only while the board has a row to hide, a 44 px secondary button across the column.
    rule(BOARD_MORE_CLASS, "display: none;"),
    block(
        f"@media (width <= {PHONE_MAX_WIDTH}px)",
        rule(
            BOARD_BLOCK_CLASS,
            "display: none;",
            suffix=(
                f":not([{BOARD_ALL_ATTR}]) .alg-board-table tbody"
                f" tr:nth-child(n + {BOARD_PHONE_ROWS + 1})"
            ),
        ),
        rule(
            BOARD_BLOCK_CLASS,
            "display: flex; width: 100%; min-height: var(--alg-target);",
            suffix=(
                f":has(.alg-board-table tbody tr:nth-child({BOARD_PHONE_ROWS + 1}))"
                f" ~ .{BOARD_MORE_CLASS}"
            ),
        ),
    ),
    rule("alg-race-permalink", "margin: 16px 0 0; display: flex;"),
    rule(
        "alg-race-link",
        "display: inline-block; font-family: var(--alg-font); font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line); color: var(--alg-text); text-decoration: none;"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-pill);"
        " padding: 12px 16px;",
    ),
    rule("alg-race-link", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule(
        "alg-race-link",
        "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
        " border-radius: var(--alg-radius-pill);",
        suffix=":focus-visible",
    ),
    block("@media (width <= 768px)", rule("alg-board", "margin-top: 16px;")),
    # The same phone card as Try and Playground: 16 px sides, one column, the figure under
    # the title (common.TABS_CSS does this for alg-try-card and alg-play-card).
    block(
        "@media (width <= 560px)",
        rule("alg-race-card", common.PHONE_TITLE, suffix=" .alg-card-title"),
        rule("alg-race-card", common.PHONE_DISPLAY, suffix=" .alg-hero-num"),
        rule(
            "alg-race-card",
            "flex-direction: column; align-items: stretch;",
            suffix=" .alg-card-head",
        ),
        rule("alg-race-card", "text-align: left;", suffix=" .alg-hero"),
        rule("alg-race-card", "padding: 16px;", suffix=" .alg-card"),
    ),
)


def permalink_outputs(handles: Mapping[str, Any]) -> list[Any]:
    """The shell's permalink protocol: one hidden box the shell writes on page load; its change
    event restores the candidate, the size and the empty card (the Playground's pattern, so the
    restore runs with the tab's own state and no module-level memory)."""
    box = handles.get("restore")
    return [box] if box is not None else []


def permalink_restore(fn: str | None, args: Mapping[str, Any] | None) -> list[Any]:
    return [common.permalink_payload(fn, args)]


#: The handle the shell reads a tab's report hook from (`app.PERMALINK_APPLIED`): the same
#: function as the module-level `permalink_applied`, bound to this build's offers.
PERMALINK_APPLIED_HANDLE = "permalink_applied"


def applied_for(
    state: RaceState | None, fn: str | None, args: Mapping[str, Any] | None
) -> tuple[str, dict[str, Any]] | None:
    """Exactly what this tab restores for a link — the report the permalink box may promise.

    A candidate offered here restores its function with the size the radio shows (`applied_size`:
    the link's when it is S, M or L, the candidate's default otherwise) — so the box reads the
    cell on the page, `?tab=race&fn=…&args={"size":"M"}`, even when the link named `XL` or no
    size at all. A function that is not a candidate, or a candidate this container does not
    offer (`state.offered`), restores nothing beyond the tab: None, and the box reads
    `?tab=race`. Without a state (no build) the candidate list alone answers."""
    cand = candidate_for(fn)
    if cand is None:
        return None
    if state is not None and state.offered(cand.id) is None:
        return None
    return cand.qualname, {PARAM_SIZE: applied_size(cand, args)}


def permalink_applied(
    fn: str | None, args: Mapping[str, Any] | None
) -> tuple[str, dict[str, Any]] | None:
    """The shell's third protocol function on the module: `applied_for` without the build's
    offers (a shell that reads the hook from the tab's handles gets the bound one)."""
    return applied_for(None, fn, args)


def restore_from_payload(state: RaceState, text: Any) -> Restore | None:
    """`restore_values` over the JSON the shell wrote into the restore box."""
    fn, args = common.permalink_request(text)
    return restore_values(state, fn, args)


def build(deps: Deps, *, state: RaceState | None = None) -> TabSpec:
    race_state = build_state(deps) if state is None else state
    choices = candidate_choices(race_state)
    first = choices[0][1] if choices else None
    first_cand = races.CANDIDATES_BY_ID[first] if first else None
    first_size = first_cand.default_size if first_cand else None

    def render(gr: Any) -> dict[str, Any]:
        hooks = {**_event_hooks(), "show_progress": "hidden"}
        quiet = {"api_name": False, "show_progress": "hidden"}
        with gr.Row(elem_classes=["alg-form-row"]):
            # The Try tab's row: each control in its own field column (the label above its
            # box), Run race beside them on the boxes' baseline (`alg-form-row` aligns the
            # row to flex-end). The size radio is S · M · L on one line; the workload each
            # means is the card's title the moment it is picked. On a phone the row wraps and
            # the three stack full-width. min_width 240 keeps the longest candidate title on
            # one line in its box; 288 keeps the three size pills (each a 20 px radio, its
            # letter and 16 px pads, ~72 px, 8 px apart) on one line inside the field's 16 px
            # pads (fix round 5 measured them wrapping at 252 px: the column grew to 157 px
            # and Run race sat under 108 px of nothing again).
            # allow_custom_value: an API/MCP client naming a candidate this container does not
            # offer gets `on_candidate`'s answer (snap back to the first offered one), never
            # Gradio's stock "is not in the list of choices" error.
            with gr.Column(elem_classes=["alg-field"], min_width=240, scale=2):
                candidate = gr.Dropdown(
                    choices,
                    value=first,
                    label=LABEL_CANDIDATE,
                    interactive=True,
                    allow_custom_value=True,
                )
            with gr.Column(elem_classes=["alg-field"], min_width=288, scale=1):
                size = gr.Radio(
                    size_choices(first_cand) if first_cand else [],
                    value=first_size,
                    label=LABEL_SIZE,
                    interactive=True,
                )
            run = gr.Button(
                LABEL_RUN,
                variant="primary",
                interactive=bool(choices),
                elem_classes=["alg-run"],
                min_width=200,
                scale=1,
            )
        notes = gr.HTML(
            qualified_note(race_state) + not_offered_note(race_state),
            elem_classes=[common.BLOCK_CLASS],
        )
        card = gr.HTML(
            opening_card(first_cand, first_size), elem_classes=["alg-race-card", common.BLOCK_CLASS]
        )
        restore = gr.Textbox("", visible=False, elem_classes=["alg-restore"])
        with gr.Accordion(LABEL_HOW, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(common.render_note(HOW_MEASURED))
        with gr.Accordion(LABEL_REPRODUCE, open=False, elem_classes=["alg-disclosure"]):
            gr.HTML(reproduce_note(race_state))
        board = gr.HTML(
            render_board(race_state), elem_classes=[BOARD_BLOCK_CLASS, common.BLOCK_CLASS]
        )
        more = gr.Button(BOARD_SHOW_ALL, variant="secondary", elem_classes=[BOARD_MORE_CLASS])
        more.click(None, None, [more], js=board_more_js(), api_name=False, show_progress="hidden")
        # The value guard (the Playground's): Gradio's dropdown fires `input` when the box is
        # left by Tab, a click away or a re-pick of the same option, with the value unchanged —
        # without the guard that re-ran the cascade and silently reset the Size to the default
        # (a visitor who picked S ran M). The id the form was last built for rides as state.
        applied_id = gr.State(first)

        def on_candidate(race_id: str | None, last: str | None) -> Any:
            """The size choices and the empty card for the chosen candidate; an id this
            container does not offer snaps the box back to the first offered candidate (or
            empties everything when none is offered); the id the form already shows answers
            value-less updates — a no-op that leaves the picked Size and the card alone."""
            if (race_id or None) == (last or None):
                # value-less updates, the Playground's shape: nothing moves in the browser, and
                # an API caller asking for the applied candidate gets an answer (not silence)
                return gr.update(), gr.update(), gr.update(), last
            cand = race_state.offered(race_id or "")
            if cand is None and first_cand is not None:
                cand = first_cand
            if cand is None:
                return (
                    gr.update(value=None),
                    gr.update(choices=[], value=None),
                    opening_card(None),
                    None,
                )
            return (
                gr.update(value=cand.id),
                gr.update(choices=size_choices(cand), value=cand.default_size),
                opening_card(cand, cand.default_size),
                cand.id,
            )

        def on_size(race_id: str | None, size_key: str | None = None) -> str:
            """A new size returns the column to the empty card, titled with the workload the
            size means: no stale result under it, and the choice spelled out before a run."""
            return opening_card(race_state.offered(race_id or ""), size_key)

        def on_run(race_id: str | None, size_key: str | None, request: gr.Request | None = None):
            for outcome in run_cell(deps, race_state, race_id or "", size_key or "", request):
                yield (
                    gr.skip() if outcome.card is None else outcome.card,
                    gr.skip() if outcome.board is None else outcome.board,
                )

        def on_restore(text: Any) -> Any:
            values = restore_from_payload(race_state, text)
            if values is None:
                return gr.skip(), gr.skip(), gr.skip(), gr.skip()
            return (
                gr.update(value=values.race_id),
                gr.update(choices=values.size_choices, value=values.size),
                values.card,
                values.race_id,
            )

        def on_load() -> str:
            """The board as this container's `Board` stands now: the page was built once, and
            cells measured since (this visitor's or another's) are rows a fresh page must show
            — the board lists what was measured here, never a stale first paint."""
            return render_board(race_state)

        def applied(fn: str | None, args: Mapping[str, Any] | None) -> Any:
            return applied_for(race_state, fn, args)

        # `.input`, not `.change`: the cascade follows the visitor, so a restored choice stays.
        candidate.input(
            on_candidate,
            [candidate, applied_id],
            [candidate, size, card, applied_id],
            api_name=API_NAMES[0],
            show_progress="hidden",
        )
        size.input(on_size, [candidate, size], card, **quiet)
        run.click(on_run, [candidate, size], [card, board], api_name=API_NAMES[1], **hooks)
        restore.change(on_restore, restore, [candidate, size, card, applied_id], **quiet)
        gr.on(None, on_load, None, [board], **quiet)
        return {
            "candidate": candidate,
            "applied_id": applied_id,
            "more": more,
            "size": size,
            "run": run,
            "notes": notes,
            "card": card,
            "board": board,
            "restore": restore,
            "on_candidate": on_candidate,
            "on_size": on_size,
            "on_restore": on_restore,
            "on_load": on_load,
            PERMALINK_APPLIED_HANDLE: applied,
            "state": race_state,
        }

    return TabSpec(TAB_RACE, "Races", render, API_NAMES)


def _event_hooks() -> dict[str, Any]:
    from algenta_spaces.lane import gradio_hooks

    return gradio_hooks()["event"]


__all__ = [
    "API_NAMES",
    "BOARD_HEADERS",
    "Outcome",
    "RaceState",
    "Restore",
    "applied_for",
    "applied_size",
    "board_html",
    "board_note",
    "board_rows",
    "build",
    "build_state",
    "candidate_choices",
    "candidate_for",
    "cell_link",
    "cell_title",
    "link_html",
    "lane_text",
    "not_offered_note",
    "offer_reason",
    "opening_card",
    "permalink_applied",
    "permalink_outputs",
    "permalink_restore",
    "qualified_note",
    "record_run",
    "render_board",
    "render_run",
    "restore_from_payload",
    "restore_values",
    "row_ratio",
    "row_where",
    "run_cell",
    "size_choices",
    "size_line",
]
