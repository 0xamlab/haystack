"""Ecosystem — the nineteen families and the umbrella with live Hub counts, the OSS kernels,
the SDK and the MCP registry, every number computed here.

* **The table.** One row per capped repository, the full page width, in the 13 px mono
  type with tabular numerals and one line per cell (a name never wraps). The facts this
  container knows come first and never depend on the network: the functions and modules
  counted from the loaded contract, and the revision the kernel runs at — the Hub
  snapshot its module was imported from (`races.kernel_revision`), followed by `pinned`
  when it is the capped v1 revision or `moved` when the cache holds a later one, so a row
  never names a sha that is not the code that ran. The Hub adds what it knows:
  `https://huggingface.co/api/kernels?author=thyn-ai` is fetched at boot and every
  fifteen minutes (a manual refresh no more than once a minute). A repository with
  downloads shows them; one without shows the date it was published, because a zero is
  a fact, not a headline; the backends the Hub lists are their own column, dropped below
  `BACKENDS_MIN_WIDTH`; up to `WRAP_MAX_WIDTH` the composite cells wrap between their ` · `
  parts (never inside one), so the table fits its block at every width and the block scrolls
  sideways only as a last resort; the two counted columns (functions, on the Hub) are
  right-aligned. On a phone the table is the shared
  table's dense row cards (`llm_tab.STACK_DENSE_CLASS`): the kernel on its first line, the
  other cells inline after it, the backends dropped as everywhere below `BACKENDS_MIN_WIDTH`
  — so twenty rows take two thirds of the page they did as five labelled lines each (130 px
  a row against 198, measured at 375 px). Below `PHONE_MAX_WIDTH` the table opens on its
  first `PHONE_ROWS` row cards and a 44 px control under it, `Show all 20 kernels`, shows the
  rest (`Show the first 6 kernels` folds them again): every row is in the DOM and in the
  `eco_refresh` answer whatever the control says — the sheet hides rows past the first six
  while the table block carries no `ALL_ATTR`, and the control's client-side click toggles
  that attribute on the block (which survives a refresh) and its own label
  (`more_js`, `aria-expanded` with it). The head chips
  lead with the computed counts — kernels and functions, with the stamp they were counted
  at — then the likes the Hub reports, then the fetch stamp. Before the Hub has been
  asked (outside a Space nothing is fetched at boot) the card is the quiet one with
  `hub_counts_not_fetched`; when a fetch the visitor pressed for fails, the card is the
  red unavailable one with its code; a failure that happened at rest (the boot poll) is
  shown quietly. Each code has its own sentence. A Refresh inside the one-minute floor
  reuses the last fetch and says so twice: the card's chip reads `fetched 20:23 UTC ·
  next refresh in 40 s`, and the button itself is disabled and counts the seconds down
  (`refresh_button_state`, ticked by a one-second timer that stops when the floor
  clears) — a pressed button never looks pressable while it would do nothing. Footers name
  the source and the fetch stamp; the endpoint addresses live in the "Where the numbers
  come from" disclosure.
* **Snippets.** One dropdown, one `get_kernel` snippet per family, built by
  `playground.snippet` from the family's own card example — the call the Hub card
  shows, in the form that compiles — with a 44 px copy chip. The dropdown sits directly
  above the snippet it drives, in the row under the table; the other column holds the two
  cards (the shell header and footer carry every Space and resource link; the tab repeats
  none of them). The row is the fleet's two-column contract (`css.LAYOUT_CSS`:
  `COLS_CLASS` on the row, `CONTROLS_CLASS` on the dropdown-and-snippet column,
  `RESULTS_CLASS` on the cards column — never `equal_height=True`, which grew every block
  of the dropdown column by 17 px: the Family form 100 → 117 px, the snippet 614 → 631 px,
  the Copy row 48.5 → 66 px) and the SDK card carries the shared stretch
  (`llm_tab.STRETCH_CLASS`) inside its column, so the cards column ends on the row's edge
  and no control ever grows into slack.
* **OSS kernels.** The `mojo-kernels` package count is the number of package
  directories the GitHub contents API lists under `kernels/`, with the latest release
  tag and date beside it and the UTC stamp of the fetch. GitHub is asked at build in a
  Space and on Refresh while no answer has arrived; until it is asked the card is the
  empty state (its rows read `not fetched yet` to a screen reader — these are fetched
  counts, not measurements), when it does not answer the card is the unavailable card —
  never a remembered number.
* **SDK and MCP.** Versions come from the facts record (`facts.py`, installed
  distributions); the MCP tool count is `len(algenta_mcp.registry.TOOLS)` from the
  installed package, or omitted.

Refresh answers at once with loading cards and then with the result, so Gradio's
progress chrome never shows (`show_progress="hidden"`). Nothing here imports gradio at
module level; `render` receives the module.
"""

from __future__ import annotations

import html
import json
import logging
import math
import threading
import time
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from algenta_spaces import cards, hubkernel, playground, shell
from algenta_spaces.css import (
    COLS_CLASS,
    CONTROLS_CLASS,
    PHONE_MAX_WIDTH,
    RESULTS_CLASS,
    block,
    rule,
    stylesheet,
)
from algenta_spaces.runtime import utc_stamp

from races import kernel_revision

from . import LOAD_HOOKS, TAB_ECO, Deps, TabSpec, common
from .llm_tab import (
    STACK_DENSE_CLASS,
    STRETCH_CLASS,
    STRETCH_COL_CLASS,
    copy_chip,
    render_empty_card,
    render_failure_card,
    render_loading_card,
    render_quiet_card,
)

log = logging.getLogger(__name__)

LABEL = "Ecosystem"
API_REFRESH = "eco_refresh"
API_SNIPPET = "eco_snippet"
API_NAMES: tuple[str, ...] = (API_REFRESH, API_SNIPPET)

HUB_API_URL = "https://huggingface.co/api/kernels?author=thyn-ai"
#: Kernel repositories live under the `kernels/` namespace; the model namespace answers 404
#: (launch review round 3: every table link was dead).
HUB_REPO_URL = "https://huggingface.co/kernels/"
GITHUB_KERNELS_API = "https://api.github.com/repos/thyn-ai/mojo-kernels/contents/kernels"
GITHUB_RELEASE_API = "https://api.github.com/repos/thyn-ai/mojo-kernels/releases/latest"
GITHUB_KERNELS_PAGE = "https://github.com/thyn-ai/mojo-kernels/tree/main/kernels"
REFRESH_S = 15 * 60.0
MIN_REFRESH_S = 60.0
TIMEOUT_S = 8.0
MAX_BODY_BYTES = 2 * 1024 * 1024

COUNTS_UNAVAILABLE = "Hub counts unavailable"
CODE_HUB_UNREACHABLE = "hub_counts_unreachable"
CODE_HUB_MALFORMED = "hub_counts_malformed"
CODE_HUB_NOT_FETCHED = "hub_counts_not_fetched"
CODE_GITHUB = "github_unreachable"
CODE_MCP_MISSING = "mcp_registry_not_installed"
HINT_HUB_NOT_FETCHED = (
    "The Hub has not been asked yet; press Refresh counts to read downloads and likes."
)
HINT_HUB_UNREACHABLE = (
    "The Hub did not answer, so downloads and likes are not shown; the rows keep what this "
    "container knows."
)
HINT_HUB_MALFORMED = (
    "The Hub answered without the kernel counts, so downloads and likes are not shown; the rows "
    "keep what this container knows."
)
HINTS_HUB: Mapping[str, str] = {
    CODE_HUB_NOT_FETCHED: HINT_HUB_NOT_FETCHED,
    CODE_HUB_UNREACHABLE: HINT_HUB_UNREACHABLE,
    CODE_HUB_MALFORMED: HINT_HUB_MALFORMED,
}
HINT_HUB = HINT_HUB_UNREACHABLE
HINT_GITHUB = "GitHub did not answer with the package list; no count is shown in its place."
SOURCE_HUB = "Hub kernels API"
SOURCE_GITHUB = "GitHub API"
NEXT_REFRESH_TEXT = "next refresh in {seconds:.0f} s"
#: The Refresh button's label while it is disabled inside the one-minute floor.
NEXT_REFRESH_BUTTON = "Next refresh in {seconds:.0f} s"
#: How often the disabled button counts down; the timer stops when the floor clears.
COOLDOWN_TICK_S = 1.0
COUNTED_TEXT = "counted {stamp}"
#: The SDK card's MCP chip when no count exists yet: the hosted API could not be read and this
#: container never read it — never "not installed" (round 9: the package is not what is counted).
MCP_NOT_INSTALLED_TEXT = "MCP tools · hosted API unreachable"
#: The hero label when the count came from the hosted endpoint, not an installed registry.
MCP_LIVE_LABEL = "MCP tools · live · hosted API"
#: The SDK card's toolchain row: what compiled the libraries every call runs through.
MOJO_ROW_LABEL = "Mojo toolchain"
MOJO_ROW_NOTE = "compiled shared libraries, in-process"
#: The revision column's word after the sha: the capped v1 revision, or a later snapshot.
REVISION_PINNED = "pinned"
REVISION_MOVED = "moved"
#: Below this width the backends column is dropped so the other four keep one line each.
#: Below this width the backends column is dropped; from here to `WRAP_MAX_WIDTH` the composite
#: cells wrap between their parts, so five columns fit a 928 px column at 1024 and four fit
#: 672 px at 900 (round 5: 1,055 px of nowrap cells were clipped at 1024 with no scroll).
BACKENDS_MIN_WIDTH = 1023
#: Up to this width a cell may wrap between its ` · ` parts; a part itself never breaks.
WRAP_MAX_WIDTH = 1279
PART_CLASS = "alg-eco-part"
#: The snippet column and the cards column under the table: equal halves that stack below this.
COLUMN_MIN_WIDTH = 320
#: The Refresh button's width when it sits alone in its row.
REFRESH_MIN_WIDTH = 240
#: On a phone the table opens on this many row cards; the control under it shows the rest.
PHONE_ROWS = 6
#: The table's block (`gr.HTML(elem_classes=[TABLE_BLOCK_CLASS])`, on the block and its prose
#: wrapper alike): with `ALL_ATTR` set every row shows on a phone, without it the first
#: `PHONE_ROWS`. The attribute lives on the block, so a refreshed table keeps the choice.
TABLE_BLOCK_CLASS = "alg-eco-tablewrap"
ALL_ATTR = "data-alg-all"
#: The 44 px control under the table on a phone (hidden wider), and its two labels.
MORE_CLASS = "alg-eco-more"
SHOW_ALL_TEXT = "Show all {n} kernels"
SHOW_FEWER_TEXT = "Show the first {n} kernels"

TITLE_HUB = "Kernels on the Hub"
TITLE_OSS = "Open-source kernels"
TITLE_SDK = "SDK and MCP"
REFRESH_TEXT = "Refresh Hub counts"
#: The Refresh button's label while the fetch is in flight: the button is disabled and says
#: what it is doing (round 11: a press showed no pending state until the table repainted).
REFRESHING_TEXT = "Refreshing…"
SNIPPET_TITLE = "Kernel snippet"
LOADING_HUB_TEXT = "Reading downloads and likes from the Hub."
LOADING_OSS_TEXT = "Reading the package list and the latest release from GitHub."
OSS_EMPTY_TEXT = "Press Refresh counts to read the package list and the latest release from GitHub."
OSS_EMPTY_ROWS = ("packages", "latest release")
#: What a screen reader hears for an empty GitHub row: a count not fetched, not measured.
NOT_FETCHED_TEXT = "not fetched yet"
NOT_LOADED = "not loaded here"
HOW_TITLE = "Where the numbers come from"
HOW_TEXT = (
    "Functions, modules and the revision are counted from the kernels loaded in this container. "
    "Downloads and likes are read from the Hub's kernels API at boot and every fifteen minutes, "
    "stamped with the fetch time; a repository without downloads shows the date it was "
    "published instead. The open-source package count is the number of package directories "
    "GitHub lists for thyn-ai/mojo-kernels; the release tag and date come from the same API. "
    "Versions are the distributions installed in this container. The MCP tool count comes from "
    "the installed algenta-mcp registry when the image has one, otherwise from the hosted API's "
    "anonymous tool list — the card's label says which. A count that could not be fetched is "
    "shown as unavailable with its code. The Refresh button asks the Hub again, at most once a "
    "minute; inside that minute the card shows the last fetch and when the next one is allowed. "
    "GitHub is read once at boot and again only while it has not answered."
)
SOURCE_LINES: tuple[str, ...] = (
    f"{SOURCE_HUB} {HUB_API_URL}",
    f"{SOURCE_GITHUB} {GITHUB_KERNELS_API}",
)
COLUMNS_STATIC: tuple[str, ...] = ("kernel", "functions", "revision")
COLUMN_HUB = "on the Hub"
COLUMN_BACKENDS = "backends"
#: The counted columns, right-aligned in the head and the body (`llm_tab.STATE_CSS`).
NUMERIC_COLUMNS: frozenset[str] = frozenset({"functions", COLUMN_HUB})

UMBRELLA_FAMILY = hubkernel.UMBRELLA_FAMILY
#: The umbrella first, then the nineteen families as the capabilities file lists them.
FAMILY_ORDER: tuple[str, ...] = (UMBRELLA_FAMILY, *playground.FAMILIES)
#: The distributions the SDK card lists. algenta-mcp is not among them: its MCP pin (2.x) and
#: gradio[mcp]'s (< 2.0) cannot share one image, so the tool count is read live from the hosted
#: API and labelled so (`MCP_LIVE_LABEL`) instead of a permanent `not installed` row.
SDK_DISTS: tuple[tuple[str, str], ...] = (
    ("algenta", "algenta (SDK)"),
    ("algenta-runtime-native", "algenta-runtime-native"),
    ("kernels", "kernels"),
    ("torch", "torch"),
    ("huggingface_hub", "huggingface-hub"),
)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

Fetch = Callable[[str, float], bytes]


def https_get(url: str, timeout_s: float = TIMEOUT_S) -> bytes:
    """GET a JSON document over https; any failure raises (OSError, ValueError)."""
    if urlsplit(url).scheme != "https":
        raise ValueError("counts are fetched over https only")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, headers={"Accept": "application/json", "User-Agent": "algenta-spaces-eco"}
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310
        body = response.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise ValueError("response too large")
    return body


def _count(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{what} is not a count")
    return value


@dataclass(frozen=True)
class HubKernelStat:
    repo_id: str
    downloads: int
    likes: int
    backends: tuple[str, ...]
    created: str = ""


def parse_kernels(
    body: bytes, trust: tuple[str, ...] = playground.TRUST
) -> dict[str, HubKernelStat]:
    """The Hub's list → `{repo_id: stat}` for the capped repositories; ValueError when malformed."""
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("the kernels listing is not a list")
    stats: dict[str, HubKernelStat] = {}
    for item in data:
        if not isinstance(item, Mapping):
            raise ValueError("a kernels entry is not an object")
        repo = str(item.get("id", ""))
        if repo not in trust:
            continue
        drivers = item.get("supportedDriverFamilies") or []
        if not isinstance(drivers, list):
            raise ValueError(f"{repo}: backends is not a list")
        stats[repo] = HubKernelStat(
            repo_id=repo,
            downloads=_count(item.get("downloads"), f"{repo} downloads"),
            likes=_count(item.get("likes"), f"{repo} likes"),
            backends=tuple(sorted(str(d) for d in drivers)),
            created=str(item.get("createdAt", "") or ""),
        )
    if not stats:
        raise ValueError("the kernels listing holds none of the capped repositories")
    return stats


@dataclass(frozen=True)
class HubSnapshot:
    stats: dict[str, HubKernelStat] | None
    error_code: str
    fetched_utc: str

    @property
    def ok(self) -> bool:
        return self.stats is not None


class HubCounts:
    """The Hub counts, refreshed every `refresh_s` seconds; a failed fetch replaces the numbers."""

    def __init__(
        self,
        url: str = HUB_API_URL,
        *,
        fetch: Fetch = https_get,
        refresh_s: float = REFRESH_S,
        min_refresh_s: float = MIN_REFRESH_S,
        clock: Callable[[], float] = time.time,
    ):
        if refresh_s <= 0 or min_refresh_s < 0:
            raise ValueError("refresh intervals must be positive")
        self.url = url
        self.refresh_s = float(refresh_s)
        self.min_refresh_s = float(min_refresh_s)
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._snapshot = HubSnapshot(None, CODE_HUB_NOT_FETCHED, "")
        self._last_attempt: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def refresh(self, *, force: bool = True) -> HubSnapshot:
        """Fetch now. With `force=False` a fetch younger than `min_refresh_s` is reused."""
        now = self._clock()
        with self._lock:
            if (
                not force
                and self._last_attempt is not None
                and now - self._last_attempt < self.min_refresh_s
            ):
                return self._snapshot
            self._last_attempt = now
        stamp = utc_stamp(datetime.fromtimestamp(now, UTC))
        try:
            body = self._fetch(self.url, TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001 - every transport failure is one code
            log.warning("hub counts fetch failed: %s: %s", type(exc).__name__, exc)
            snapshot = HubSnapshot(None, CODE_HUB_UNREACHABLE, stamp)
        else:
            try:
                snapshot = HubSnapshot(parse_kernels(body), "", stamp)
            except (ValueError, UnicodeDecodeError) as exc:
                log.warning("hub counts malformed: %s", exc)
                snapshot = HubSnapshot(None, CODE_HUB_MALFORMED, stamp)
        with self._lock:
            self._snapshot = snapshot
        return snapshot

    def latest(self) -> HubSnapshot:
        with self._lock:
            return self._snapshot

    def cooldown_s(self, now: float | None = None) -> float:
        """Seconds until a manual refresh (`force=False`) fetches again; 0 when it would now."""
        now = self._clock() if now is None else now
        with self._lock:
            last = self._last_attempt
        if last is None:
            return 0.0
        return max(0.0, self.min_refresh_s - (now - last))

    def _loop(self) -> None:
        while not self._stop.wait(self.refresh_s):
            self.refresh()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
        self.refresh()
        thread = threading.Thread(target=self._loop, name="algenta-hub-counts", daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        self._stop.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout_s)


@dataclass(frozen=True)
class OssFacts:
    package_count: int
    release_tag: str
    released_utc: str
    fetched_utc: str
    source: str = GITHUB_KERNELS_PAGE


@dataclass
class OssState:
    """What the tab knows about GitHub: the facts, or whether it has been asked at all."""

    facts: OssFacts | None = None
    asked: bool = False


def parse_package_count(body: bytes) -> int:
    """The number of package directories in a GitHub contents listing."""
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError("the contents listing is not a list")
    count = 0
    for item in data:
        if not isinstance(item, Mapping):
            raise ValueError("a contents entry is not an object")
        if item.get("type") == "dir":
            count += 1
    if count == 0:
        raise ValueError("the contents listing holds no package directories")
    return count


def parse_release(body: bytes) -> tuple[str, str]:
    """`(tag_name, published UTC stamp)` of a GitHub release object."""
    data = json.loads(body.decode("utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("the release is not an object")
    tag = str(data.get("tag_name") or "").strip()
    published = str(data.get("published_at") or "").strip()
    if not tag or not published:
        raise ValueError("the release has no tag or date")
    moment = datetime.fromisoformat(published.replace("Z", "+00:00"))
    return tag, utc_stamp(moment)


def fetch_oss_facts(fetch: Fetch = https_get, *, now: datetime | None = None) -> OssFacts | None:
    """Both GitHub reads at boot; None (logged) when either does not answer with data."""
    try:
        count = parse_package_count(fetch(GITHUB_KERNELS_API, TIMEOUT_S))
        tag, released = parse_release(fetch(GITHUB_RELEASE_API, TIMEOUT_S))
    except Exception as exc:  # noqa: BLE001 - the card shows the code, the log the cause
        log.warning("github facts unavailable: %s: %s", type(exc).__name__, exc)
        return None
    return OssFacts(count, tag, released, utc_stamp(now))


def mcp_tool_count_with_caption() -> tuple[int | None, str, str]:
    """`(count, caption, kind)`: the installed registry, else the live hosted endpoint the Try
    tile reads (`try_tab.mcp_tool_count`, which keeps this container's last successful read
    and reports it with its time when the API is unreachable). One source for both tabs: the
    launch review saw the Try tile say 140 while this card said the package was absent."""
    try:
        from algenta_mcp.registry import TOOLS
    except Exception:  # noqa: BLE001 - not installed, or a 3.14-only import on 3.12
        from tabs import try_tab

        return try_tab.mcp_tool_count()
    return len(TOOLS), "installed registry", "registry"


def mcp_tool_count() -> int | None:
    return mcp_tool_count_with_caption()[0]


def try_tab_code() -> str:
    from tabs import try_tab

    return try_tab.CODE_MCP_UNREACHABLE


def snippet_for(family: str) -> str:
    """The family's card-example call as a compilable `get_kernel` snippet."""
    if family not in FAMILY_ORDER:
        raise ValueError(f"unknown family {family!r}")
    example = hubkernel.card_example(family)
    return playground.snippet(
        family, example.module, example.function, list(example.args), mode=playground.MODE_KERNELS
    )


# ---------------------------------------------------------------------------
# What this container knows about each repository
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KernelRow:
    """The static facts of one repository, counted from the loaded kernel (None: not loaded)."""

    family: str
    repo_id: str
    functions: int | None
    modules: int | None
    revision: str
    version: int | None
    #: True when the loaded snapshot is the capped v1 revision, False when the cache holds a
    #: later one (`LoadedKernel.pinned`); None for a family that did not load.
    pinned: bool | None = None


def kernel_rows(deps: Deps) -> dict[str, KernelRow]:
    """One `KernelRow` per capped repository, from `deps.kernels`; unloaded families carry None.
    The revision is the loaded snapshot's (`kernel_revision`), never the capped sha alone."""
    rows: dict[str, KernelRow] = {}
    for family in FAMILY_ORDER:
        loaded = deps.kernel(family)
        if loaded is None:
            rows[family] = KernelRow(family, _repo(family), None, None, "", None)
            continue
        described = hubkernel.describe(loaded)
        rows[family] = KernelRow(
            family,
            loaded.repo_id,
            int(described["function_count"]),
            len(described["modules"]),
            kernel_revision(loaded)[:7],
            loaded.version,
            loaded.pinned,
        )
    return rows


def function_total(deps: Deps, rows: Mapping[str, KernelRow]) -> int | None:
    """The catalogue size: the facts record's count, else the umbrella's, else the families' sum."""
    recorded = deps.facts.get("function_count")
    if isinstance(recorded, int) and not isinstance(recorded, bool) and recorded > 0:
        return recorded
    umbrella = rows.get(UMBRELLA_FAMILY)
    if umbrella is not None and umbrella.functions:
        return umbrella.functions
    counted = [r.functions for f, r in rows.items() if f != UMBRELLA_FAMILY and r.functions]
    return sum(counted) if counted else None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def _chip(text: str, tone: str = "neutral") -> str:
    return f'<span class="alg-chip alg-chip-{tone}">{_esc(text)}</span>'


def _repo(family: str) -> str:
    return playground.repo_id(family)


def _num(value: int) -> str:
    return f"{value:,}"


def published_on(created: str) -> str:
    """`2026-09-21` from the Hub's `createdAt` ISO stamp; empty when absent or malformed."""
    if not created:
        return ""
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return ""


def hub_cell(stat: HubKernelStat) -> str:
    """What the Hub knows, worth a line: downloads when there are any, else the publish date,
    then the likes; the backends are their own column (`backends_cell`)."""
    parts = []
    if stat.downloads > 0:
        parts.append(f"{_num(stat.downloads)} downloads")
    else:
        date = published_on(stat.created)
        parts.append(f"published {date}" if date else "published")
    if stat.likes > 0:
        parts.append(f"{stat.likes} like" if stat.likes == 1 else f"{stat.likes} likes")
    return " · ".join(parts)


def backends_cell(stat: HubKernelStat) -> str:
    """`cpu, cuda, metal` — the driver families the Hub lists for the repository."""
    return ", ".join(stat.backends)


def revision_text(row: KernelRow) -> str:
    """`v1 · 92ef06d · moved` — the version, the loaded snapshot's sha and whether it is the
    capped revision (`pinned`) or a later one the cache holds (`moved`)."""
    if not row.revision:
        return f"v{row.version}"
    text = f"v{row.version} · {row.revision}"
    if row.pinned is True:
        return f"{text} · {REVISION_PINNED}"
    if row.pinned is False:
        return f"{text} · {REVISION_MOVED}"
    return text


def parts_html(text: str) -> str:
    """`<span class="alg-eco-part">1,234 functions</span> · <span …>12 modules</span>`: each
    ` · `-separated part in a no-wrap span, so a narrow column breaks the cell between parts
    and never inside a number or a name."""
    return " · ".join(
        f'<span class="{PART_CLASS}">{_esc(part)}</span>' for part in text.split(" · ")
    )


def _static_cells(row: KernelRow | None) -> str:
    if row is None or row.functions is None:
        functions = NOT_LOADED
        revision = "–"
    else:
        modules = f"{row.modules} module" if row.modules == 1 else f"{row.modules} modules"
        functions = f"{_num(row.functions)} functions · {modules}"
        revision = revision_text(row)
    return (
        f'<td data-label="functions" class="alg-stack-num">{parts_html(functions)}</td>'
        f'<td data-label="revision" class="alg-eco-mono">{parts_html(revision)}</td>'
    )


def _table(rows: str, *, hub_column: bool) -> str:
    columns = (*COLUMNS_STATIC, COLUMN_HUB, COLUMN_BACKENDS) if hub_column else COLUMNS_STATIC
    head = "".join(f'<th scope="col"{_col_attr(c)}{_num_attr(c)}>{_esc(c)}</th>' for c in columns)
    return (
        f'<table class="alg-stack-table {STACK_DENSE_CLASS} alg-eco-table">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _num_attr(column: str) -> str:
    """The counted columns carry the shared numeric class, so the head aligns with the cells."""
    return ' class="alg-stack-num"' if column in NUMERIC_COLUMNS else ""


def _col_attr(column: str) -> str:
    """The backends column is marked so the sheet can drop it below `BACKENDS_MIN_WIDTH`."""
    return f' data-col="{COLUMN_BACKENDS}"' if column == COLUMN_BACKENDS else ""


def _head_chips(total: int | None, extra: list[str], counted_utc: str = "") -> str:
    chips = [_chip(f"{len(FAMILY_ORDER)} kernels")]
    if total:
        chips.append(_chip(f"{_num(total)} functions"))
    if counted_utc:
        chips.append(cards.status_chip("measured", COUNTED_TEXT.format(stamp=counted_utc)))
    chips.extend(extra)
    # data-golden="mask": the downloads and likes are the Hub's live counts (they moved the day
    # the Hub started reporting downloads), so the goldens paint over this row
    return f'<div class="alg-chips" data-golden="mask">{"".join(chips)}</div>'


def hub_hint(code: str) -> str:
    """One sentence per code; an unknown code reads as unreachable."""
    return HINTS_HUB.get(code, HINT_HUB_UNREACHABLE)


def fetched_text(snapshot: HubSnapshot, next_refresh_s: float = 0.0) -> str:
    """`fetched 2026-09-22 20:23 UTC`, plus `· next refresh in 40 s` while a manual refresh
    would reuse this fetch — the card acknowledges the press instead of staying silent."""
    text = f"fetched {snapshot.fetched_utc}"
    if next_refresh_s > 0:
        text += f" · {NEXT_REFRESH_TEXT.format(seconds=max(1.0, next_refresh_s))}"
    return text


def render_hub_table(
    snapshot: HubSnapshot,
    rows: Mapping[str, KernelRow] | None = None,
    *,
    total: int | None = None,
    counted_utc: str = "",
    next_refresh_s: float = 0.0,
    failed_now: bool = False,
) -> str:
    """The head, the table and — when the Hub has not answered — the one card that says so.

    `failed_now` marks a fetch the visitor just pressed for that failed: that card is the red
    unavailable one. At rest (not fetched yet, or a boot poll that failed) the card is quiet.
    `next_refresh_s` > 0 means this press reused the last fetch; the stamp chip says when the
    next one is allowed."""
    rows = rows or {}
    body = []
    stats = snapshot.stats
    for family in FAMILY_ORDER:
        repo = _repo(family)
        row = rows.get(family)
        stat = stats.get(repo) if stats is not None else None
        hub = ""
        if stats is not None:
            text = hub_cell(stat) if stat is not None else "not listed by the Hub"
            backends = backends_cell(stat) if stat is not None else "–"
            hub = (
                f'<td data-label="{COLUMN_HUB}" class="alg-stack-num">{parts_html(text)}</td>'
                f'<td data-label="{COLUMN_BACKENDS}"{_col_attr(COLUMN_BACKENDS)}>'
                f"{_esc(backends)}</td>"
            )
        body.append(
            "<tr>"
            f'<td data-label="kernel" class="alg-stack-lead">'
            f'<a class="alg-eco-link" href="{HUB_REPO_URL}{_esc(repo)}" target="_blank"'
            f' rel="noopener">{_esc(repo)}</a></td>'
            f"{_static_cells(row)}{hub}</tr>"
        )
    if stats is None:
        code = snapshot.error_code or CODE_HUB_NOT_FETCHED
        foot = SOURCE_HUB
        if snapshot.fetched_utc:
            foot = f"{SOURCE_HUB} · asked {snapshot.fetched_utc}"
        if failed_now and code != CODE_HUB_NOT_FETCHED:
            card = render_failure_card(COUNTS_UNAVAILABLE, code, hub_hint(code), hardware=foot)
        else:
            card = render_quiet_card(COUNTS_UNAVAILABLE, code, hub_hint(code), hardware=foot)
        chips = _head_chips(total, [], counted_utc)
        head = f'<div class="alg-eco-head"><h2 class="alg-card-title">{TITLE_HUB}</h2>{chips}</div>'
        return card + head + _table("".join(body), hub_column=False)
    downloads = sum(s.downloads for s in stats.values())
    likes = sum(s.likes for s in stats.values())
    extra = []
    if downloads:
        extra.append(_chip(f"{_num(downloads)} downloads"))
    if likes:
        extra.append(_chip(f"{likes} like" if likes == 1 else f"{likes} likes"))
    extra.append(cards.status_chip("measured", fetched_text(snapshot, next_refresh_s)))
    chips = _head_chips(total, extra, counted_utc)
    head = f'<div class="alg-eco-head"><h2 class="alg-card-title">{TITLE_HUB}</h2>{chips}</div>'
    stamp = _esc(snapshot.fetched_utc)
    foot = f'<div class="alg-card-foot">{_esc(SOURCE_HUB)} · fetched {stamp}</div>'
    return head + _table("".join(body), hub_column=True) + foot


def render_oss_card(state: OssFacts | OssState | None, *, failed_now: bool = False) -> str:
    """The GitHub card: empty until asked, unavailable when GitHub did not answer (red only when
    the visitor's own Refresh asked; quiet for a boot-time miss), else facts."""
    if isinstance(state, OssState):
        if state.facts is None and not state.asked:
            return render_empty_card(
                TITLE_OSS, OSS_EMPTY_TEXT, rows=OSS_EMPTY_ROWS, pending_text=NOT_FETCHED_TEXT
            )
        facts = state.facts
    else:
        facts = state
    if facts is None:
        if failed_now:
            return render_failure_card(TITLE_OSS, CODE_GITHUB, HINT_GITHUB, hardware=SOURCE_GITHUB)
        return render_quiet_card(TITLE_OSS, CODE_GITHUB, HINT_GITHUB, hardware=SOURCE_GITHUB)
    return (
        '<article class="alg-card alg-eco-card">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{TITLE_OSS}</h2>'
        '<div class="alg-card-sub">thyn-ai/mojo-kernels · Apache-2.0</div></div>'
        '<div class="alg-hero">'
        f'<div class="alg-hero-num">{_num(facts.package_count)}</div>'
        '<div class="alg-hero-label">packages</div></div></div>'
        f'<div class="alg-chips">{_chip(f"latest release {facts.release_tag}")}'
        f"{_chip(f'released {facts.released_utc}')}"
        f"{cards.status_chip('measured', f'fetched {facts.fetched_utc}')}</div>"
        '<div class="alg-eco-actions">'
        f'<a class="alg-eco-pill" href="{_esc(facts.source)}" target="_blank" rel="noopener">'
        "Browse the packages</a>"
        f'<a class="alg-eco-pill" href="{shell.GITHUB_URL}" target="_blank" rel="noopener">'
        "GitHub</a>"
        "</div>"
        f'<div class="alg-card-foot">{_esc(f"{SOURCE_GITHUB} · fetched {facts.fetched_utc}")}</div>'
        "</article>"
    )


def sdk_facts(facts: Mapping[str, Any]) -> dict[str, Any]:
    """Versions and the MCP tool count as data: `facts.json` first, the registry second."""
    versions = facts.get("versions") if isinstance(facts.get("versions"), Mapping) else {}
    tools = facts.get("mcp_tools")
    source = "registry"
    caption = ""
    if not isinstance(tools, int) or isinstance(tools, bool) or tools < 1:
        tools, caption, kind = mcp_tool_count_with_caption()
        source = "live" if kind == "live" else ("stale" if isinstance(tools, int) else "")
        if kind == "registry":
            source = "registry"
    return {
        "versions": {name: versions.get(name) for name, _ in SDK_DISTS},
        "mcp_tools": tools,
        "mcp_source": source,
        "mcp_caption": caption if source == "stale" else "",
        # the toolchain that compiled every loaded family's shared library (`/health`
        # facts.mojo_version, read from the packages' own manifests — never typed)
        "mojo_version": str(facts.get("mojo_version") or ""),
        "generated_utc": str(facts.get("generated_utc") or ""),
        "python": str(facts.get("python") or ""),
    }


def render_sdk_card(facts: Mapping[str, Any]) -> str:
    data = sdk_facts(facts)
    rows = []
    for name, label in SDK_DISTS:
        version = data["versions"].get(name)
        value = _esc(version) if version else "not installed"
        rows.append(
            f'<div class="alg-eco-row"><span class="alg-eco-key">{_esc(label)}</span>'
            f'<span class="alg-eco-val">{value}</span></div>'
        )
    if data["mojo_version"]:
        rows.append(
            f'<div class="alg-eco-row"><span class="alg-eco-key">{_esc(MOJO_ROW_LABEL)}</span>'
            f'<span class="alg-eco-val">{_esc(data["mojo_version"])} · {_esc(MOJO_ROW_NOTE)}'
            "</span></div>"
        )
    tools = data["mcp_tools"]
    if tools is None:
        # No count in this process yet and the hosted API unreachable now: say so, with the code;
        # a neutral chip without the unavailable marker, so the verifier's count check on this
        # tab is never short-circuited.
        hero = _chip(MCP_NOT_INSTALLED_TEXT)
        label = f"unavailable · {try_tab_code()}"
    else:
        hero = f'<div class="alg-hero-num">{_num(tools)}</div>'
        label = (
            MCP_LIVE_LABEL
            if data.get("mcp_source") == "live"
            else data.get("mcp_caption") or "MCP tools in the installed registry"
        )
    stamp = data["generated_utc"]
    chips = [_chip(f"Python {data['python']}")] if data["python"] else []
    if stamp:
        chips.append(cards.status_chip("measured", f"computed {stamp}"))
    return (
        '<article class="alg-card alg-eco-card">'
        '<div class="alg-card-head">'
        f'<div><h2 class="alg-card-title">{TITLE_SDK}</h2>'
        '<div class="alg-card-sub">installed in this container</div></div>'
        f'<div class="alg-hero">{hero}<div class="alg-hero-label">{label}</div></div></div>'
        f'<div class="alg-eco-rows">{"".join(rows)}</div>'
        f'<div class="alg-chips">{"".join(chips)}</div>'
        '<div class="alg-eco-actions">'
        f'<a class="alg-eco-pill" href="{shell.DOCS_URL}" target="_blank" rel="noopener">Docs</a>'
        f'<a class="alg-eco-pill" href="{gov_mcp_endpoint()}" target="_blank" rel="noopener">'
        "MCP endpoint</a>"
        "</div>"
        "</article>"
    )


def gov_mcp_endpoint() -> str:
    from .gov_tab import MCP_ENDPOINT

    return MCP_ENDPOINT


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def counted_utc(facts: Mapping[str, Any]) -> str:
    """The stamp the facts record was computed at — when the kernel counts were counted."""
    return str(facts.get("generated_utc") or "")


def more_labels(total: int = len(FAMILY_ORDER), first: int = PHONE_ROWS) -> tuple[str, str]:
    """`("Show all 20 kernels", "Show the first 6 kernels")` — the control's label while the
    table is folded and once it is open."""
    return SHOW_ALL_TEXT.format(n=total), SHOW_FEWER_TEXT.format(n=first)


def more_js(total: int = len(FAMILY_ORDER), first: int = PHONE_ROWS) -> str:
    """The control's client-side click: toggle `ALL_ATTR` on every element carrying
    `TABLE_BLOCK_CLASS` (the block and its prose wrapper), mirror the state in the control's
    `aria-expanded`, and answer the label for the new state (Gradio writes it back)."""
    show_all, show_fewer = more_labels(total, first)
    return (
        "() => {"
        f" const blocks = document.querySelectorAll('.{TABLE_BLOCK_CLASS}');"
        f" const on = blocks.length > 0 && !blocks[0].hasAttribute('{ALL_ATTR}');"
        f" blocks.forEach((b) => b.toggleAttribute('{ALL_ATTR}', on));"
        f" document.querySelectorAll('button.{MORE_CLASS}').forEach((b) =>"
        " b.setAttribute('aria-expanded', on ? 'true' : 'false'));"
        f" return on ? {json.dumps(show_fewer)} : {json.dumps(show_all)};"
        " }"
    )


def refresh_button_state(cooldown_s: float) -> tuple[bool, str]:
    """`(interactive, label)` for the Refresh button: disabled and counting down (`Next refresh
    in 42 s`) while a press would only reuse the last fetch, else enabled and `Refresh counts`."""
    if cooldown_s > 0:
        return False, NEXT_REFRESH_BUTTON.format(seconds=max(1.0, math.ceil(cooldown_s)))
    return True, REFRESH_TEXT


def refresh_outputs(
    counts: HubCounts,
    oss: OssFacts | OssState | None,
    facts: Mapping[str, Any],
    *,
    rows: Mapping[str, KernelRow] | None = None,
    total: int | None = None,
    force: bool = False,
    oss_failed_now: bool = False,
) -> tuple[str, str, str]:
    """The three refreshed panels. A press inside the one-minute floor reuses the last fetch and
    the table says when the next one is allowed; a fetch that failed on this press is red."""
    before = counts.latest()
    snapshot = counts.refresh(force=force)
    reused = snapshot is before and before.fetched_utc != ""
    return (
        render_hub_table(
            snapshot,
            rows,
            total=total,
            counted_utc=counted_utc(facts),
            next_refresh_s=counts.cooldown_s() if reused else 0.0,
            failed_now=not reused and not snapshot.ok,
        ),
        render_oss_card(oss, failed_now=oss_failed_now),
        render_sdk_card(facts),
    )


def on_snippet(family: str) -> str:
    try:
        return snippet_for(str(family))
    except (ValueError, hubkernel.HubKernelError) as exc:
        return f"# {exc}\n"


#: Sentinel a staged handler yields for an output it leaves as it is.
KEEP = object()


def staged_refresh(
    counts: HubCounts,
    oss: OssState,
    facts: Mapping[str, Any],
    *,
    fetch: Fetch,
    rows: Mapping[str, KernelRow] | None,
    total: int | None,
) -> Iterator[tuple[Any, Any, Any]]:
    """Loading cards at once, then the refreshed table, GitHub card and SDK card.

    GitHub is asked at build (in a Space) and again here only while no answer has arrived, so a
    boot-time miss recovers without a request per click.
    """
    ask_github = oss.facts is None
    yield (
        render_loading_card(TITLE_HUB, LOADING_HUB_TEXT),
        render_loading_card(TITLE_OSS, LOADING_OSS_TEXT) if ask_github else KEEP,
        KEEP,
    )
    if ask_github:
        oss.facts = fetch_oss_facts(fetch)
        oss.asked = True
    yield refresh_outputs(
        counts,
        oss,
        facts,
        rows=rows,
        total=total,
        force=False,
        oss_failed_now=ask_github and oss.facts is None,
    )


# ---------------------------------------------------------------------------
# The tab
# ---------------------------------------------------------------------------

_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_MONO = "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
#: A 44 px pill with the hairline inside the target (round 10: 12 px pads around a 20 px line
#: plus two 1 px borders measured 46) — a flex-centred line in a 44 px border-box.
_PILL = (
    "display: inline-flex; align-items: center; font-family: var(--alg-font);"
    " font-size: var(--alg-mono-size); line-height: var(--alg-mono-line);"
    " color: var(--alg-text); text-decoration: none; border: 1px solid var(--alg-hairline);"
    " border-radius: var(--alg-radius-pill); min-height: var(--alg-target);"
    " box-sizing: border-box; padding: 0 16px;"
)

# alg-eco-* classes only; the table shape is llm_tab.STATE_CSS's alg-stack-table. The table's
# cells are the 13 px mono type with tabular numerals, one line each (a name never wraps), and the
# backends column is dropped below BACKENDS_MIN_WIDTH so the four that remain keep one line. A row
# is exactly the kernel link's 44 px target: the cells centre on it and the link's own cell carries
# no vertical padding, so twenty rows take 900 px, not 1,220.
ECO_CSS = stylesheet(
    rule("alg-eco-head", "margin: 0 0 8px;"),
    rule("alg-eco-table", "margin: 8px 0 0;"),
    rule(
        "alg-eco-table",
        f"{_MONO} font-size: var(--alg-mono-size); line-height: var(--alg-mono-line);"
        " white-space: nowrap; vertical-align: middle;",
        suffix=" td",
    ),
    rule("alg-eco-table", "padding-top: 0; padding-bottom: 0;", suffix=" td:first-child"),
    rule(
        "alg-eco-table",
        "font-size: var(--alg-mono-size); line-height: var(--alg-mono-line); white-space: nowrap;",
        suffix=" th",
    ),
    rule("alg-eco-table", "white-space: nowrap;", suffix=" .alg-eco-link"),
    rule(PART_CLASS, "white-space: nowrap;"),
    # the table never outgrows its block: up to WRAP_MAX_WIDTH the composite cells wrap between
    # their parts (the link and each part stay whole); the block scrolls sideways as a last
    # resort instead of the page clipping a column (round 5: `backends` cut to `cpu, cuda, me`)
    rule(TABLE_BLOCK_CLASS, "overflow-x: auto;"),
    block(
        f"@media (width <= {WRAP_MAX_WIDTH}px)",
        rule("alg-eco-table", "white-space: normal;", suffix=" td"),
        rule("alg-eco-table", "white-space: normal;", suffix=" th"),
        rule("alg-eco-table", "white-space: normal;", suffix=" td.alg-stack-num"),
        rule("alg-eco-table", "white-space: normal;", suffix=" td.alg-eco-mono"),
    ),
    block(
        f"@media (width <= {BACKENDS_MIN_WIDTH}px)",
        rule("alg-eco-table", "display: none;", suffix=f' [data-col="{COLUMN_BACKENDS}"]'),
    ),
    block(
        "@media (width <= 768px)",
        rule("alg-eco-table", "white-space: normal;", suffix=" td"),
        rule("alg-eco-table", "padding-top: 4px; padding-bottom: 4px;", suffix=" td:first-child"),
    ),
    rule("alg-eco-mono", f"{_MONO} white-space: nowrap;"),
    rule("alg-eco-source", f"{_MONO} overflow-wrap: anywhere;"),
    # the kernel link: a 44 px target whose padding is on the grid (Gradio's prose gives a table
    # link 2px 8px — the final review's only off-grid declarations); border-box, so 44 px holds
    rule(
        "alg-eco-link",
        "color: var(--alg-text); text-decoration: none; display: inline-flex;"
        " align-items: center; min-height: var(--alg-target); padding: 4px 8px;"
        " box-sizing: border-box;",
    ),
    rule("alg-eco-link", "text-decoration: underline;", suffix=":hover"),
    rule(
        "alg-eco-link",
        "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
        " border-radius: var(--alg-radius-input);",
        suffix=":focus-visible",
    ),
    rule("alg-eco-rows", "display: flex; flex-direction: column; gap: 4px; margin: 12px 0 0;"),
    rule("alg-eco-row", f"display: flex; flex-wrap: wrap; gap: 4px 16px; {_CAPTION}"),
    rule("alg-eco-key", "flex: 0 0 160px; color: var(--alg-text-2);"),
    rule("alg-eco-val", f"flex: 1 1 160px; {_MONO}"),
    rule("alg-eco-actions", "display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0 0;"),
    rule("alg-eco-pill", _PILL),
    rule("alg-eco-pill", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule(
        "alg-eco-pill",
        "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
        " border-radius: var(--alg-radius-pill);",
        suffix=":focus-visible",
    ),
    # the phone fold: the table's block hides every row past the first PHONE_ROWS until the
    # control under it sets ALL_ATTR; the control itself exists only on a phone, a 44 px
    # secondary button across the column (the rows stay in the DOM and in the API at every width)
    rule(MORE_CLASS, "display: none;"),
    block(
        f"@media (width <= {PHONE_MAX_WIDTH}px)",
        rule(
            TABLE_BLOCK_CLASS,
            "display: none;",
            suffix=f":not([{ALL_ATTR}]) .alg-eco-table tbody tr:nth-child(n + {PHONE_ROWS + 1})",
        ),
        rule(MORE_CLASS, "display: flex; width: 100%; min-height: var(--alg-target);"),
    ),
    # the stretched SDK card: its pills sit on the bottom edge, one gap under the chips
    rule(
        STRETCH_CLASS,
        "margin-top: auto; padding-top: 12px;",
        suffix=" .alg-card > .alg-eco-actions",
    ),
    block("@media (width <= 560px)", rule("alg-eco-key", "flex-basis: 96px;")),
)


def build(
    deps: Deps,
    *,
    counts: HubCounts | None = None,
    oss: OssFacts | None = None,
    fetch: Fetch = https_get,
) -> TabSpec:
    """The tab spec. In a Space (`SPACE_ID` set) the Hub counts poller starts and the GitHub
    facts are fetched at render; tests pass `counts` and `oss` and an empty env."""
    hub = HubCounts(fetch=fetch) if counts is None else counts
    in_space = bool(deps.env.get("SPACE_ID", "").strip())
    oss_state = OssState(facts=oss, asked=oss is not None)
    if oss_state.facts is None and in_space:
        oss_state.facts = fetch_oss_facts(fetch)
        oss_state.asked = True
    rows = kernel_rows(deps)
    total = function_total(deps, rows)

    def render(gr: Any) -> dict[str, Any]:
        """The page: Refresh, the table across the full width, then two equal columns that stack
        on a phone — the family dropdown over the snippet it drives, and the two cards, the
        SDK card grown to the column — so no column runs empty beside a
        twenty-row table and the two end on one edge."""
        if in_space:
            hub.start()
        facts = deps.facts
        with gr.Row():
            refresh = gr.Button(
                REFRESH_TEXT,
                variant="secondary",
                size="lg",
                scale=0,
                min_width=REFRESH_MIN_WIDTH,
                elem_classes=["alg-run"],
            )
        cooldown = gr.Timer(COOLDOWN_TICK_S, active=False)
        stamp = counted_utc(facts)
        table = gr.HTML(
            value=render_hub_table(hub.latest(), rows, total=total, counted_utc=stamp),
            elem_classes=[TABLE_BLOCK_CLASS, common.BLOCK_CLASS],
        )
        show_all, _ = more_labels()
        more = gr.Button(show_all, variant="secondary", elem_classes=[MORE_CLASS])
        more.click(None, None, [more], js=more_js(), api_name=False, show_progress="hidden")
        # the fleet's two-column contract (`css.LAYOUT_CSS`), never `equal_height=True`: the
        # dropdown-and-snippet column keeps its natural height (fix round 5 measured `equal_height`
        # growing each of its blocks by 17 px — the Family form 100 → 117 px, the snippet
        # 614 → 631 px, the Copy row 48.5 → 66 px), the cards column stretches to the row and the
        # SDK card fills it
        with gr.Row(elem_classes=[COLS_CLASS]):
            with gr.Column(scale=1, min_width=COLUMN_MIN_WIDTH, elem_classes=[CONTROLS_CLASS]):
                family = gr.Dropdown(choices=list(FAMILY_ORDER), value="stats", label="Family")
                snippet = gr.Code(
                    value=snippet_for("stats"),
                    language="python",
                    label=SNIPPET_TITLE,
                    wrap_lines=True,
                    buttons=[],
                    interactive=False,
                )
                copy_chip(gr, snippet)
            with gr.Column(
                scale=1,
                min_width=COLUMN_MIN_WIDTH,
                elem_classes=[RESULTS_CLASS, STRETCH_COL_CLASS],
            ) as cards_column:
                oss_card = gr.HTML(render_oss_card(oss_state), elem_classes=[common.BLOCK_CLASS])
                sdk_card = gr.HTML(
                    value=render_sdk_card(facts), elem_classes=[STRETCH_CLASS, common.BLOCK_CLASS]
                )
        with gr.Accordion(HOW_TITLE, open=False, elem_classes=["alg-disclosure"]):
            sources = "".join(
                f'<p class="alg-note alg-eco-source">{_esc(line)}</p>' for line in SOURCE_LINES
            )
            gr.HTML(f'<p class="alg-note">{_esc(HOW_TEXT)}</p>{sources}')

        def _button() -> tuple[Any, Any]:
            """The Refresh button and its timer for the floor now: disabled and counting down
            while a press would reuse the last fetch, the timer running only meanwhile."""
            interactive, label = refresh_button_state(hub.cooldown_s())
            return gr.update(interactive=interactive, value=label), gr.Timer(active=not interactive)

        def _refresh():
            stages = staged_refresh(hub, oss_state, facts, fetch=fetch, rows=rows, total=total)
            first = next(stages)
            # the pending state at once: the loading cards, the button disabled and saying
            # `Refreshing…`; the floor's label and timer come back with the result
            yield (
                *(gr.skip() if v is KEEP else v for v in first),
                gr.update(interactive=False, value=REFRESHING_TEXT),
                gr.skip(),
            )
            for values in stages:
                yield (*(gr.skip() if v is KEEP else v for v in values), *_button())

        def _tick():
            return _button()

        refresh.click(
            _refresh,
            None,
            [table, oss_card, sdk_card, refresh, cooldown],
            api_name=API_REFRESH,
            concurrency_id="counts",
            concurrency_limit=1,
            show_progress="hidden",
        )
        cooldown.tick(_tick, None, [refresh, cooldown], api_name=False, show_progress="hidden")
        family.change(on_snippet, family, snippet, api_name=API_SNIPPET, show_progress="hidden")
        return {
            "family": family,
            "refresh": refresh,
            "cooldown": cooldown,
            "button_state": _button,
            "on_refresh": _refresh,
            "table": table,
            "more": more,
            "snippet": snippet,
            "oss_card": oss_card,
            "sdk_card": sdk_card,
            "cards_column": cards_column,
            "counts": hub,
            "oss": oss_state,
            "rows": rows,
            LOAD_HOOKS: [
                (
                    lambda: render_hub_table(hub.latest(), rows, total=total, counted_utc=stamp),
                    table,
                ),
                (lambda: render_sdk_card(facts), sdk_card),
            ],
        }

    return TabSpec(id=TAB_ECO, label=LABEL, render=render, api_names=API_NAMES)
