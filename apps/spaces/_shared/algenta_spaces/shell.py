"""One header, one footer, one stylesheet for the Algenta Spaces.

Lifted from the fleet's canonical shell (`apps/spaces/_retired/shell.canonical.py`):
`render_header` / `render_footer` / `SHELL_CSS` keep the same discipline — every
selector repeats its class four times so it beats Gradio's scoped resets without
`!important`, no Gradio selectors, colours from `var(--alg-*)` tokens.

What changed for the flagship fleet: the header's nav is the three live Spaces
(`SPACES_NAV`) with a Duplicate link built from the Space id — the product's own
destinations, one line; the resources (Kernels Hub, GitHub, Docs, Pricing, Discord —
`RESOURCE_LINKS`) live in the footer beside the three Spaces (`NAV` is the union). The
owner's call, 2026-09-23: the two kinds of link do not belong together in one line. The
footer carries the canon one-liner, the licence line and the deploy stamps read from
`.git_sha` and `.shared_sha` next to the package.

The deploy stamp is `build <12 hex>` on one line (`SHORT_STAMP_CHARS`), with the
full sha as the span's `title` — a 64-hex stamp measured 546 × 20 px on the
desktop and three lines at 375 px. The `title` attribute is written *before*
`class`, so the DOM contract the verifiers read (`tools/verify_remote.SHA_STAMP_RE`
and `verify_checks.STAMP_RE`: `alg-shell-stamp">build <hex><`) still matches; both
compare the stamp as a prefix of the staged `.shared_sha`, so twelve characters
pass. `dev` (no stamp file) prints as before, without a title.

The nav and the footer links are `<ul>` lists: each item draws its own "·"
separator with a `::before` pseudo-element, so a separator can never wrap onto a
line of its own, and every link is a 44 × 44 px flex box (`min-inline-size` for
the short labels — Docs is 31 px of text). The glyph is positioned inside the
list's 16 px column gap (`SEPARATOR_GAP_PX`), so it takes no layout of its own;
`NAV_ROWS_SCRIPT` (a head fragment, `NAV_ROWS_HEAD`, the host page includes)
marks the item that opens each wrapped row with `ROW_START_ATTR` and the sheet
draws no glyph there, so a wrapped row never starts with "·". On a phone the
list wraps into two or three rows of whole items; the header tightens and the
display type steps down through the tokens' phone media block.

Copy rules are enforced at render time: a headline is at most six words, a
subline at most fourteen, no exclamation marks, no emoji, none of the banned
phrases. Stdlib only.

Header pills (`badges`) wrap honestly. A pill whose text fits is a one-line
999 px pill; one whose text needs two lines at the row's width (`0 of 19 kernel
families · this container` at 375 px, measured 279 px of text in a 278 px row)
is marked by `CHIP_WRAP_SCRIPT` with `CHIP_WRAP_ATTR` — the same rule as the
cards' chips, read from the pill's line boxes, never guessed — and the sheet
draws it as a 12 px tag, left-aligned, two full lines, instead of an ellipsis
(`…this con…` hid the fact the pill exists to state). No `title` doubles the
text: nothing is truncated, so there is nothing to reveal. Their text is human
copy — a count with its unit and when it was taken (`19 families warm in 2.0 s`),
a tier (`CPU upgrade`) — never a build-variant string
(`torch25-cpu-aarch64-darwin`), an environment variable or a snake_case
identifier; `machine_token(text)` names the first such token so the app that
composes the pills can keep them human (the flagship's `badges()` in
`app.py` owns the text).

Head fragment (`NAV_ROWS_HEAD`, appended to the flagship's `BOOT_HEAD`): five
plain-ES5 scripts with no exclamation mark (the copy lint). `NAV_ROWS_SCRIPT`
marks the item that opens each wrapped nav row (above); `DISCLOSURE_SCRIPT`
mirrors every `alg-disclosure` accordion's open state onto its header as
`aria-expanded` — Gradio sets none, the chevron in `css.CHROME_CSS` turns on it
and a screen reader hears expanded / collapsed; `TABSTRIP_SCRIPT` owns the strip
that scrolls (the phone): it centres the selected tab on load and on every
selection, marks which edges hide more tabs (`css.STRIP_EDGE_ATTR`, the fade
masks in `css.CHROME_CSS` read it) and lets one tap on a half-visible tab select
it — see the script's note; `CHIP_WRAP_SCRIPT` marks every `alg-chip` and every
header pill whose text takes more than one line (counted from its line boxes,
`Range.getClientRects`) with `cards.CHIP_WRAP_ATTR`, so `cards.CARD_CSS` and
`SHELL_CSS` can draw it as a 12 px tag at least 44 px tall (50 px for two lines),
instead of two lines inside a 999 px pill — re-run per frame on DOM, class and
style changes (a tab or accordion opening), on resize and when the web fonts
land; a chip that fits is left as the pill it is. `DROPDOWN_CLOSE_SCRIPT` closes
a Gradio 6.28 dropdown whose list was left open after focus moved away — see the
script's note for the stock behaviour it corrects.
"""

from __future__ import annotations

import html
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from .css import (
    ARRIVAL_ATTR,
    COMBOBOX,
    DISCLOSURE_CLASS,
    LISTBOX,
    STRIP_EDGE_ATTR,
    block,
    rule,
    stylesheet,
)
from .runtime import is_sha, read_stamp

CANON = "compiler-driven, self-hosted AI infrastructure"
EYEBROW = f"ALGENTA · {CANON}"
LICENCE_LINE = (
    "Space code Apache-2.0 · kernels under the Algenta Community License 1.1 "
    "— commercial plans at algenta.ai/pricing"
)

FLAGSHIP_URL = "https://huggingface.co/spaces/thyn-ai/algenta"
SPEED_ARENA_URL = "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"
GOVERNED_AGENT_URL = "https://huggingface.co/spaces/thyn-ai/algenta-governed-agent"
KERNELS_HUB_URL = "https://huggingface.co/thyn-ai"
GITHUB_URL = "https://github.com/thyn-ai/mojo-kernels"
DOCS_URL = "https://docs.algenta.ai"
PRICING_URL = "https://algenta.ai/pricing"
DISCORD_URL = "https://discord.gg/w8NDsph9an"

#: The header's nav: the three Spaces — where a visitor goes next inside the product.
#: The product's Spaces: one, the flagship (round 9, owner: "only one will be left" — the old
#: Speed Arena and Governed Agent Spaces were deleted; the deep dives return as tabs or as new
#: Spaces when they are rebuilt, and join this tuple then).
SPACES_NAV: tuple[tuple[str, str], ...] = (("Flagship", FLAGSHIP_URL),)
#: The resources: outside the product, in the footer only.
RESOURCE_LINKS: tuple[tuple[str, str], ...] = (
    ("Kernels Hub", KERNELS_HUB_URL),
    ("GitHub", GITHUB_URL),
    ("Docs", DOCS_URL),
    ("Pricing", PRICING_URL),
    ("Discord", DISCORD_URL),
)
#: Every link the shell knows, in footer order: the Spaces, then the resources.
NAV: tuple[tuple[str, str], ...] = SPACES_NAV + RESOURCE_LINKS
NAV_LABELS = frozenset(label for label, _ in NAV)

HEADLINE_WORDS = 6
SUBLINE_WORDS = 14
SEPARATOR = "·"
#: The column gap between two list items; the separator glyph is centred inside it.
SEPARATOR_GAP_PX = 16
#: Set by `NAV_ROWS_SCRIPT` on the item that opens a wrapped row; the sheet draws no glyph there.
ROW_START_ATTR = "data-alg-row-start"
#: Set by `CHIP_WRAP_SCRIPT` on a chip or a header pill whose text takes more than one line
#: (cards.CHIP_WRAP_ATTR).
CHIP_WRAP_ATTR = "data-alg-wrap"
#: What `CHIP_WRAP_SCRIPT` measures: the cards' chips and the header's pills.
WRAP_SELECTOR = ".alg-chip, .alg-shell-badge"
#: A tap that moves less than this is a tap, not a swipe (`TABSTRIP_SCRIPT`).
TAP_SLOP_PX = 8
#: How long after a pointer touches a tab the strip stays still for it (`TABSTRIP_SCRIPT`): the
#: browser's synthesized mousedown / click after a touch arrive well inside this.
GESTURE_MS = 700
PHONE_MAX_WIDTH = 767
#: The footer prints this many characters of the deploy sha; the full value is the `title`.
SHORT_STAMP_CHARS = 12
#: The deploy's commit is named the way `git log --oneline` does.
COMMIT_CHARS = 7
#: The footer's stamp pair (`commit … · build …`): one flex item, never split.
STAMPS_CLASS = "alg-shell-footer-stamps"
#: The footer's second link group (Kernels Hub, GitHub, Docs, Pricing, Discord), a gap away
#: from the Spaces group so the two never read as one list.
RESOURCES_CLASS = "alg-shell-footer-resources"

# Phrases that never appear in user-visible copy (positioning canon + Apple copy rules).
BANNED_PHRASES: tuple[str, ...] = (
    r"decision engine",
    r"cgroup",
    r"\bR[479]\b",
    r"wire shapes?",
    r"harness v\d",
    r"simulated",
    r"clean-room",
    r"post-open-source",
    r"defensibility",
    r"bit-faithful",
    r"@algenta\.ai",
)
_BANNED_RE = re.compile("|".join(BANNED_PHRASES), re.IGNORECASE)
_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # pictographs, emoticons, symbols
    "☀-➿"  # misc symbols and dingbats
    "⭐⭕️"
    "]"
)
_SPACE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
_BADGE_VARIANTS = ("", "ok", "warn")
#: Tokens that are machine names, not copy: a snake_case identifier, an environment
#: variable, a build variant (`torch25-cpu-aarch64-darwin`, `torch-universal`), a `@sha`.
_MACHINE_TOKEN_RE = re.compile(
    r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"  # z_test_proportions
    r"|\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"  # ALGENTA_API_KEY
    r"|\btorch\d*-[a-z0-9_.-]+\b"  # torch25-cpu-aarch64-darwin, torch-universal
    r"|\b[a-z0-9]+-(?:cpu|cuda|metal|rocm|cxx11)-[a-z0-9_.-]+\b"  # <x>-cpu-<arch>-<os>
    r"|@[0-9a-f]{7,40}\b"  # algenta-stats@ac35ffe
)


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def banned_phrase(text: str) -> str | None:
    """The first banned phrase found in `text`, or None."""
    match = _BANNED_RE.search(text)
    return match.group(0) if match else None


def has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def machine_token(text: str) -> str | None:
    """The first token in `text` that is a machine name rather than copy, or None.

    `Hub kernels · torch-universal, torch25-cpu-aarch64-darwin` -> `torch-universal`;
    `the Space secret ALGENTA_API_KEY turns it on` -> `ALGENTA_API_KEY`;
    `19 families warm in 2.0 s` -> None. Primary copy — pills, titles, hints — carries
    none; a code chip or a snippet is where such a token belongs.
    """
    match = _MACHINE_TOKEN_RE.search(text)
    return match.group(0) if match else None


def check_copy(text: str, *, max_words: int | None = None, what: str = "copy") -> str:
    """Return `text` if it obeys the copy rules, else raise ValueError naming the rule."""
    if not text.strip():
        raise ValueError(f"{what} is empty")
    if "!" in text:
        raise ValueError(f"{what} contains an exclamation mark: {text!r}")
    if has_emoji(text):
        raise ValueError(f"{what} contains emoji: {text!r}")
    hit = banned_phrase(text)
    if hit:
        raise ValueError(f"{what} contains the banned phrase {hit!r}: {text!r}")
    if max_words is not None:
        words = len(text.split())
        if words > max_words:
            raise ValueError(f"{what} has {words} words; the limit is {max_words}: {text!r}")
    return text


def duplicate_url(space_id: str) -> str:
    """The Hub's Duplicate link for a Space id such as `thyn-ai/algenta`."""
    if not _SPACE_ID_RE.match(space_id):
        raise ValueError(f"not a Space id: {space_id!r}")
    return f"https://huggingface.co/spaces/{space_id}?duplicate=true"


def space_id_from_env(env: Mapping[str, str] | None = None) -> str:
    """`SPACE_ID` as the Hub sets it in every Space container, else an empty string."""
    env = os.environ if env is None else env
    return env.get("SPACE_ID", "").strip()


def shared_sha(path: Path | str | None = None) -> str:
    """The deploy stamp `tools/stage.py` writes next to the package, or `dev`."""
    stamp = Path(__file__).resolve().parent.parent / ".shared_sha" if path is None else Path(path)
    return read_stamp(stamp)


def short_stamp(build: str) -> str:
    """`bc8e7c68957e` from a sha (`SHORT_STAMP_CHARS`); anything else (`dev`) as it came."""
    return build[:SHORT_STAMP_CHARS] if is_sha(build) else build


def git_sha(path: Path | str | None = None) -> str:
    """The deploy's commit: `GIT_SHA`/`GITHUB_SHA`, else the `.git_sha` file `tools/stage.py`
    writes next to the package (`facts.git_sha`), else `dev`."""
    from .facts import git_sha as _git_sha

    if path is None:
        return _git_sha()
    return read_stamp(Path(path))


def _stamp_html(build: str, commit: str = "") -> str:
    """`<span title="build <full>" class="alg-shell-stamp">build <12 hex></span>`, preceded by
    `<span title="commit <full>" class="alg-shell-commit">commit <7 hex></span>` when the
    deploy's git sha is known (round 5: the shared-package stamp alone let no reviewer
    correlate the page with a release).

    `title` precedes `class` on purpose: the verifiers read `alg-shell-stamp">build <hex><`."""
    text = f"build {short_stamp(build)}"
    title = f' title="build {_esc(build)}"' if is_sha(build) else ""
    stamp = f'<span{title} class="alg-shell-stamp">{_esc(text)}</span>'
    if not is_sha(commit):
        return stamp
    # one flex item, so the pair wraps as a whole and stays right-aligned when it does
    # (round 6: at 1024–1180 px `build` dropped to a new line at the far left alone)
    return (
        f'<span class="{STAMPS_CLASS}">'
        f'<span title="commit {_esc(commit)}" class="alg-shell-commit">'
        f"commit {_esc(commit[:COMMIT_CHARS])}</span>"
        f'<span class="alg-shell-stamp-sep" aria-hidden="true"> · </span>{stamp}</span>'
    )


def _badge_html(badge: str | tuple[str, str]) -> str:
    """One pill. `badge` is plain text (neutral) or a (text, variant) tuple.

    The whole text is always on the page: a pill that fits is one line; one that needs two
    lines at the row's width is marked by `CHIP_WRAP_SCRIPT` and drawn as a 12 px tag (see
    the module docstring). No `title` — nothing is truncated. Its text is human copy (see
    `machine_token`); the caller owns the words."""
    if isinstance(badge, tuple):
        text, variant = badge
    else:
        text, variant = badge, ""
    if variant not in _BADGE_VARIANTS:
        raise ValueError(f"unknown badge variant {variant!r}; expected one of {_BADGE_VARIANTS}")
    check_copy(text, max_words=SUBLINE_WORDS, what="badge")
    cls = "alg-shell-badge" + (f" alg-shell-badge-{variant}" if variant else "")
    return f'<span class="{cls}">{_esc(text)}</span>'


def _links_html(
    active: str | None,
    link_class: str,
    active_class: str,
    item_class: str,
    links: tuple[tuple[str, str], ...] = NAV,
) -> str:
    """`links` as list items; the active Space is text with `aria-current`, not a link."""
    items = []
    for label, url in links:
        if label == active:
            inner = f'<span class="{active_class}" aria-current="page">{_esc(label)}</span>'
        else:
            # every nav and footer link leaves the Space: a new tab, because inside the
            # Hub's Space iframe a same-frame navigation to another site renders nothing
            inner = (
                f'<a class="{link_class}" href="{url}" target="_blank" rel="noopener">'
                f"{_esc(label)}</a>"
            )
        items.append(f'<li class="{item_class}">{inner}</li>')
    return "".join(items)


def _nav_html(active: str | None, space_id: str) -> str:
    links = _links_html(
        active, "alg-shell-nav-link", "alg-shell-nav-active", "alg-shell-nav-item", SPACES_NAV
    )
    right = ""
    if space_id:
        right = (
            f'<a class="alg-shell-nav-dup" href="{duplicate_url(space_id)}"'
            ' target="_blank" rel="noopener">'
            "Duplicate this Space</a>"
        )
    return (
        '<nav class="alg-shell-nav" aria-label="Algenta">'
        f'<ul class="alg-shell-nav-list">{links}</ul>{right}</nav>'
    )


#: The count's gradient fill travels inline: Gradio's processing of the `css=` sheet dropped the
#: rule's `background` and `-webkit-background-clip` declarations (measured on the served sheet,
#: with literal stops and with a token alike) while inline styles reach the browser untouched, as
#: the card bars' widths do. Tokens only — no literal colour.
COUNT_STYLE = (
    "background: linear-gradient(90deg, var(--alg-accent-from), var(--alg-accent-to));"
    " -webkit-background-clip: text; background-clip: text; color: transparent;"
)
_LEADING_COUNT_RE = re.compile(r"^(\d{1,3}(?:,\d{3})*|\d+)\s+(.+)$")


def _title_html(title: str) -> str:
    """The headline; a leading number ("6,040 compiled Mojo kernels") becomes its own display
    line in the accent gradient above the words (owner, round 11: "6,040 is huge — must be
    visible right away", "AI-ish gradient"). Any other headline renders as plain text."""
    m = _LEADING_COUNT_RE.match(title.strip())
    if m is None:
        return _esc(title)
    return (
        f'<span class="alg-shell-count alg-accent-text" style="{COUNT_STYLE}">'
        f"{_esc(m.group(1))}</span>"
        f'<span class="alg-shell-title-text">{_esc(m.group(2))}</span>'
    )


def render_header(
    title: str,
    tagline: str,
    badges: Iterable[str | tuple[str, str]] | None = None,
    active: str | None = None,
    *,
    space_id: str | None = None,
) -> str:
    """The fleet header: eyebrow, headline, subline, optional pills, nav, Duplicate link.

    `badges` are plain strings (neutral pills) or (text, variant) tuples with
    variant "ok" or "warn". `active` is this Space's own NAV label, rendered as
    text instead of a link. `space_id` defaults to `SPACE_ID`; without one the
    Duplicate link is omitted (local runs).
    """
    if active is not None and active not in NAV_LABELS:
        raise ValueError(f"active {active!r} is not a NAV label")
    check_copy(title, max_words=HEADLINE_WORDS, what="headline")
    check_copy(tagline, max_words=SUBLINE_WORDS, what="subline")
    sid = space_id_from_env() if space_id is None else space_id
    parts = [
        '<header class="alg-shell-header">',
        f'<div class="alg-shell-eyebrow">{_esc(EYEBROW)}</div>',
        f'<h1 class="alg-shell-title">{_title_html(title)}</h1>',
        f'<p class="alg-shell-tagline">{_esc(tagline)}</p>',
    ]
    if badges:
        pills = "".join(_badge_html(b) for b in badges)
        parts.append(f'<div class="alg-shell-badges">{pills}</div>')
    parts.append(_nav_html(active, sid))
    parts.append("</header>")
    return "".join(parts)


def render_footer(
    *, active: str | None = None, stamp: str | None = None, commit: str | None = None
) -> str:
    """The fleet footer: brand and canon line, licence line, links, deploy stamps.

    The build stamp is one line — twelve hex characters of the shared-package sha with the
    full value as the span's `title` (`short_stamp`), or `dev` when no `.shared_sha` is staged;
    the deploy's commit (seven characters, full sha in `title`) precedes it when known."""
    if active is not None and active not in NAV_LABELS:
        raise ValueError(f"active {active!r} is not a NAV label")
    build = shared_sha() if stamp is None else stamp
    deploy_commit = git_sha() if commit is None else commit
    # two groups, not one line of eight: the Spaces, then the resources (owner, 2026-09-23)
    spaces = _links_html(
        active,
        "alg-shell-footer-link",
        "alg-shell-footer-active",
        "alg-shell-footer-item",
        SPACES_NAV,
    )
    resources = _links_html(
        active,
        "alg-shell-footer-link",
        "alg-shell-footer-active",
        "alg-shell-footer-item",
        RESOURCE_LINKS,
    )
    return (
        '<footer class="alg-shell-footer">'
        '<div class="alg-shell-footer-row">'
        '<span class="alg-shell-footer-brand">Algenta</span>'
        f'<span class="alg-shell-footer-canon">{_esc(CANON)}</span>'
        "</div>"
        f'<p class="alg-shell-footer-licence">{_esc(LICENCE_LINE)}</p>'
        '<div class="alg-shell-footer-row">'
        + (
            f'<ul class="alg-shell-footer-list" aria-label="Spaces">{spaces}</ul>'
            f'<ul class="alg-shell-footer-list {RESOURCES_CLASS}" aria-label="Resources">'
            if len(SPACES_NAV) > 1  # one Space: the resources stand alone (round 9)
            else '<ul class="alg-shell-footer-list" aria-label="Resources">'
        )
        + f"{resources}</ul>"
        f"{_stamp_html(build, deploy_commit)}"
        "</div>"
        "</footer>"
    )


# ---------------------------------------------------------------------------
# SHELL_CSS — alg-shell-* classes only. css.rule() repeats each class four
# times so the rules beat Gradio's scoped resets without `!important`.
# Colours, type and spacing come from design.TOKENS_CSS; margins, paddings
# and gaps use only the 8-pt scale. Every interactive target is 44 px tall
# and at least 44 px wide: the mono line (20 px) plus 2 x 12 px padding, all
# on the scale, and `min-inline-size: var(--alg-target)` for short labels.
# Links are flex items, so the padding is real layout, not inline-box paint.
# Separators are `::before` pseudo-elements of the following list item, so
# they travel with their link when the list wraps; they sit absolutely in the
# column gap, so drawing or dropping one never moves an item (the row marker
# below cannot oscillate the layout). Focus rings are visible
# and follow the element's own radius (input radius for text links, the pill
# radius for the Duplicate pill).
# ---------------------------------------------------------------------------

_RING = "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
_FOCUS = f"{_RING} border-radius: var(--alg-radius-input);"
_FOCUS_PILL = f"{_RING} border-radius: var(--alg-radius-pill);"
_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_TARGET = "line-height: var(--alg-mono-line); padding: 12px 4px;"
_LINK = (
    "display: inline-flex; align-items: center; justify-content: center;"
    " min-inline-size: var(--alg-target); color: var(--alg-text); text-decoration: none;"
    f" white-space: nowrap; {_TARGET}"
)
_ACTIVE = (
    "display: inline-flex; align-items: center; justify-content: center;"
    f" min-inline-size: var(--alg-target); color: var(--alg-text-2); white-space: nowrap; {_TARGET}"
)
_ROW = (
    "display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;"
    " gap: 8px 16px;"
)
_LIST = (
    f"display: flex; flex-wrap: wrap; align-items: center; gap: 0 {SEPARATOR_GAP_PX}px;"
    " list-style: none; margin: 0; padding: 0;"
)
_ITEM = "display: inline-flex; align-items: center; margin: 0; padding: 0; position: relative;"
_SEPARATOR = (
    f'content: "{SEPARATOR}"; color: var(--alg-text-2); position: absolute;'
    f" inset: 0 100% 0 auto; width: {SEPARATOR_GAP_PX}px; display: flex; align-items: center;"
    " justify-content: center; line-height: var(--alg-mono-line);"
)
_ROW_START = "content: none;"

SHELL_CSS = stylesheet(
    rule(
        "alg-shell-header",
        "padding: 32px 0 12px; font-family: var(--alg-font); color: var(--alg-text);",
    ),
    rule(
        "alg-shell-eyebrow",
        f"font-family: var(--alg-font-mono); {_CAPTION} letter-spacing: 0.08em;"
        " text-transform: uppercase; color: var(--alg-text-2); margin: 0 0 8px;",
    ),
    rule(
        "alg-shell-title",
        "font-size: var(--alg-display-size); line-height: var(--alg-display-line);"
        " letter-spacing: var(--alg-display-tracking); font-weight: 600;"
        " color: var(--alg-text); margin: 0 0 8px; overflow-wrap: anywhere;",
    ),
    rule(
        "alg-shell-count",
        "display: block; font-size: var(--alg-count-size); line-height: var(--alg-count-line);"
        " letter-spacing: var(--alg-count-tracking); font-weight: var(--alg-count-weight);"
        " font-variant-numeric: tabular-nums; margin: 0 0 4px;",
    ),
    rule("alg-shell-title-text", "display: block;"),
    rule(
        "alg-shell-tagline",
        "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
        " color: var(--alg-text-2); inline-size: min(64ch, 100%); margin: 0;",
    ),
    # a row of pills centres mixed heights (a two-line tag beside one-line pills)
    rule(
        "alg-shell-badges",
        "display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 16px 0 0;",
    ),
    # the whole text, always: one line in a pill, or (marked by CHIP_WRAP_SCRIPT) two lines in
    # a 12 px tag — never an ellipsis, never text inside a half-circle
    rule(
        "alg-shell-badge",
        f"display: inline-block; max-width: 100%; box-sizing: border-box;"
        f" font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-pill);"
        " padding: 4px 12px; overflow-wrap: anywhere; vertical-align: middle;",
    ),
    rule(
        "alg-shell-badge",
        "border-radius: var(--alg-radius-card); padding: 8px 12px; text-align: left;",
        suffix=f"[{CHIP_WRAP_ATTR}]",
    ),
    rule("alg-shell-badge-ok", "color: var(--alg-ok);"),
    rule("alg-shell-badge-warn", "color: var(--alg-warn);"),
    rule(
        "alg-shell-nav",
        "display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;"
        " gap: 4px 16px; margin: 12px 0 0; font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line);",
    ),
    rule("alg-shell-nav-list", _LIST),
    rule("alg-shell-nav-item", _ITEM),
    rule("alg-shell-nav-item", _SEPARATOR, suffix=" + .alg-shell-nav-item::before"),
    rule("alg-shell-nav-item", _ROW_START, suffix=f"[{ROW_START_ATTR}]::before"),
    rule("alg-shell-nav-link", _LINK),
    rule("alg-shell-nav-link", "text-decoration: underline;", suffix=":hover"),
    rule("alg-shell-nav-link", _FOCUS, suffix=":focus-visible"),
    rule("alg-shell-nav-active", _ACTIVE),
    rule(
        "alg-shell-nav-dup",
        "color: var(--alg-text); text-decoration: none; border: 1px solid var(--alg-hairline);"
        " border-radius: var(--alg-radius-pill); line-height: var(--alg-mono-line);"
        " display: inline-flex; align-items: center; min-height: var(--alg-target);"
        " box-sizing: border-box; padding: 0 16px; white-space: nowrap;",
    ),
    rule("alg-shell-nav-dup", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule("alg-shell-nav-dup", _FOCUS_PILL, suffix=":focus-visible"),
    rule(
        "alg-shell-footer",
        "border-top: 1px solid var(--alg-hairline); margin-top: 48px; padding-top: 16px;"
        " display: flex; flex-direction: column; gap: 8px; font-family: var(--alg-font);"
        " font-size: var(--alg-mono-size); line-height: var(--alg-mono-line);"
        " color: var(--alg-text-2);",
    ),
    rule("alg-shell-footer-row", _ROW),
    rule("alg-shell-footer-brand", "font-weight: 600; color: var(--alg-text);"),
    rule("alg-shell-footer-canon", "color: var(--alg-text-2);"),
    rule("alg-shell-footer-licence", "margin: 0; color: var(--alg-text-2);"),
    rule("alg-shell-footer-list", _LIST),
    rule(RESOURCES_CLASS, "margin-left: 16px;"),
    rule("alg-shell-footer-item", _ITEM),
    rule("alg-shell-footer-item", _SEPARATOR, suffix=" + .alg-shell-footer-item::before"),
    rule("alg-shell-footer-item", _ROW_START, suffix=f"[{ROW_START_ATTR}]::before"),
    rule("alg-shell-footer-link", _LINK),
    rule("alg-shell-footer-link", "text-decoration: underline;", suffix=":hover"),
    rule("alg-shell-footer-link", _FOCUS, suffix=":focus-visible"),
    rule("alg-shell-footer-active", _ACTIVE),
    # one line each: twelve hex characters never need to wrap; the full sha is the title
    rule(
        "alg-shell-stamp",
        "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
        " color: var(--alg-text-2); white-space: nowrap;",
    ),
    rule(
        "alg-shell-commit",
        "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
        " color: var(--alg-text-2); white-space: nowrap;",
    ),
    rule(
        STAMPS_CLASS,
        "display: inline-flex; align-items: center; white-space: nowrap; margin-left: auto;"
        " font-family: var(--alg-font-mono); color: var(--alg-text-2);",
    ),
    rule("alg-shell-stamp-sep", "white-space: pre; color: var(--alg-text-2);"),
    block(
        f"@media (width <= {PHONE_MAX_WIDTH}px)",
        rule("alg-shell-header", "padding: 24px 0 8px;"),
        rule("alg-shell-nav", "gap: 8px 16px; margin: 8px 0 0;"),
        rule("alg-shell-nav-dup", "flex: 1 1 100%; justify-content: center;"),
        rule("alg-shell-footer", "margin-top: 32px;"),
        # each footer group on its own line, from the gutter, in caption type: the five
        # resources fit one line at 375 px instead of orphaning the last one
        rule(RESOURCES_CLASS, "margin-left: 0;"),
        rule("alg-shell-footer-list", "flex: 1 1 100%;"),
        rule("alg-shell-footer-link", "font-size: var(--alg-caption-size);"),
        rule("alg-shell-footer-active", "font-size: var(--alg-caption-size);"),
    ),
)

#: Marks the item that opens each wrapped row of the nav and footer lists with `ROW_START_ATTR`
#: (the sheet draws no separator there). Runs as soon as a list is in the DOM, again whenever a
#: list or one of its items changes size (fonts landing, the viewport turning) and on resize.
#: The glyph is out of the layout flow, so a mark never moves an item and the pass converges
#: in one step. Plain ES5 with no exclamation mark, for the copy lint.
NAV_ROWS_SCRIPT = (
    "(function () {"
    f" var ATTR = '{ROW_START_ATTR}';"
    " var LISTS = '.alg-shell-nav-list, .alg-shell-footer-list';"
    " var mark = function (list) {"
    "  var top = null;"
    "  for (var i = 0; i < list.children.length; i += 1) {"
    "   var item = list.children[i]; var box = item.getBoundingClientRect();"
    "   if (box.width === 0 && box.height === 0) { continue; }"
    "   var row = Math.round(box.top);"
    "   if (top === null || row !== top) { item.setAttribute(ATTR, ''); top = row; }"
    "   else { item.removeAttribute(ATTR); }"
    "  }"
    " };"
    " var markAll = function () {"
    "  var lists = document.querySelectorAll(LISTS);"
    "  for (var i = 0; i < lists.length; i += 1) { mark(lists[i]); }"
    " };"
    " var seen = [];"
    " var sizes = ('ResizeObserver' in window) ? new ResizeObserver(markAll) : null;"
    " var scan = function () {"
    "  var lists = document.querySelectorAll(LISTS);"
    "  for (var i = 0; i < lists.length; i += 1) {"
    "   var list = lists[i];"
    "   if (seen.indexOf(list) !== -1) { continue; }"
    "   seen.push(list); mark(list);"
    "   if (sizes !== null) {"
    "    sizes.observe(list);"
    "    for (var j = 0; j < list.children.length; j += 1) { sizes.observe(list.children[j]); }"
    "   }"
    "  }"
    " };"
    " var start = function () {"
    "  scan();"
    "  new MutationObserver(scan).observe(document.documentElement,"
    "   {childList: true, subtree: true});"
    "  window.addEventListener('resize', markAll);"
    " };"
    " if (document.readyState === 'loading') {"
    "  document.addEventListener('DOMContentLoaded', start);"
    " } else { start(); }"
    " })();"
)

#: The accordion state Gradio does not expose: every `alg-disclosure` header gets
#: `aria-expanded` from whether its content (`[data-testid="accordion-content"]`) is displayed.
#: Re-run on every DOM or inline-style change (that is how Gradio shows and hides the content);
#: setting the attribute itself is not a `style` mutation, so the observer never loops.
DISCLOSURE_SCRIPT = (
    "(function () {"
    f" var HEADERS = '.{DISCLOSURE_CLASS} > button';"
    " var CONTENT = '[data-testid=\"accordion-content\"]';"
    " var mark = function (button) {"
    "  var block = button.parentElement;"
    "  var content = block === null ? null : block.querySelector(CONTENT);"
    "  var open = content !== null && getComputedStyle(content).display !== 'none';"
    "  var value = open ? 'true' : 'false';"
    "  if (button.getAttribute('aria-expanded') !== value) {"
    "   button.setAttribute('aria-expanded', value);"
    "  }"
    " };"
    " var markAll = function () {"
    "  var buttons = document.querySelectorAll(HEADERS);"
    "  for (var i = 0; i < buttons.length; i += 1) { mark(buttons[i]); }"
    " };"
    " var start = function () {"
    "  markAll();"
    "  new MutationObserver(markAll).observe(document.documentElement,"
    "   {childList: true, subtree: true, attributes: true, attributeFilter: ['style']});"
    " };"
    " if (document.readyState === 'loading') {"
    "  document.addEventListener('DOMContentLoaded', start);"
    " } else { start(); }"
    " })();"
)

#: A strip that scrolls (the phone) keeps the selected tab in view: centred on load, on every
#: selection (`aria-selected` flips), when a tab takes keyboard focus and when a strip is added;
#: a strip that fits is untouched. Two more duties, both measured at 375 px:
#:
#: * **Edges.** The wrapper carries `css.STRIP_EDGE_ATTR` = `start` / `middle` / `end` / `none`
#:   from where the first and the last visible tab sit against its box (not from `scrollLeft`:
#:   the snap points park the strip at the wrapper's 4 px padding, and the tablist's 16 px end
#:   padding keeps `scrollLeft` short of its maximum with the last tab fully in view), re-read
#:   on every scroll (a listener on each wrapper as it appears — `scroll` does not bubble), on
#:   resize and on every mutation; `css.CHROME_CSS` fades the edge that hides more tabs with a
#:   mask, so a clipped
#:   strip never looks like the last tab is "LLM ke", and the first tab at rest is never faded.
#: * **One tap.** Round 3: a tap on the half-visible tab at the right edge scrolled the strip
#:   (scrollLeft 4 → 184) and selected nothing — this script's own `focusin` reveal moved the
#:   tab out from under the finger between the press and the release, so the click landed on the
#:   tablist. Now a pointer that touches a tab in a strip that scrolls holds the reveal for
#:   `GESTURE_MS` (the browser's synthesized mousedown / click after a touch arrive inside it;
#:   the selection's own `aria-selected` reveal still centres the tab afterwards). A release
#:   within `TAP_SLOP_PX` of the press is a tap, not a swipe, and arms the tab: when the click
#:   that follows lands on it, Gradio selects as usual; when it lands anywhere else (the strip
#:   moved anyway), or never arrives, the tab is selected by `click()` — the page behaves as if
#:   the tap had landed. A swipe that starts on a tab never selects it.
TABSTRIP_SCRIPT = (
    "(function () {"
    ' var TABS = \'[role="tab"][aria-selected="true"]\';'
    " var LISTS = '[role=\"tablist\"]';"
    f" var EDGE = '{STRIP_EDGE_ATTR}';"
    f" var SLOP = {TAP_SLOP_PX};"
    f" var GESTURE_MS = {GESTURE_MS};"
    " var tabOf = function (node) {"
    "  if (node === null || node.closest === undefined) { return null; }"
    "  return node.closest('[role=\"tab\"]');"
    " };"
    " var wrapOf = function (tab) {"
    "  var list = tab.closest(LISTS);"
    "  return list === null ? null : list.parentElement;"
    " };"
    " var scrolls = function (wrap) {"
    "  return wrap !== null && wrap.scrollWidth > wrap.clientWidth + 1;"
    " };"
    " var reveal = function (tab) {"
    "  var wrap = wrapOf(tab);"
    "  if (scrolls(wrap) === false) { return; }"
    "  var left = tab.offsetLeft + tab.offsetWidth / 2 - wrap.clientWidth / 2;"
    "  wrap.scrollLeft = Math.max(0, left);"
    " };"
    " var revealSelected = function () {"
    "  var tabs = document.querySelectorAll(TABS);"
    "  for (var i = 0; i < tabs.length; i += 1) { reveal(tabs[i]); }"
    " };"
    " var shownTabs = function (wrap) {"
    "  var tabs = wrap.querySelectorAll('[role=\"tab\"]'); var shown = [];"
    "  for (var i = 0; i < tabs.length; i += 1) {"
    "   if (tabs[i].getBoundingClientRect().width > 0) { shown.push(tabs[i]); }"
    "  }"
    "  return shown;"
    " };"
    " var markEdge = function (wrap) {"
    "  var value = 'none';"
    "  var shown = shownTabs(wrap);"
    "  if (shown.length > 0 && scrolls(wrap)) {"
    "   var box = wrap.getBoundingClientRect();"
    "   var hiddenBefore = shown[0].getBoundingClientRect().left < box.left - 1;"
    "   var hiddenAfter = shown[shown.length - 1].getBoundingClientRect().right > box.right + 1;"
    "   if (hiddenBefore && hiddenAfter) { value = 'middle'; }"
    "   else if (hiddenBefore) { value = 'end'; }"
    "   else if (hiddenAfter) { value = 'start'; }"
    "  }"
    "  if (wrap.getAttribute(EDGE) !== value) { wrap.setAttribute(EDGE, value); }"
    " };"
    " var wired = [];"
    " var wire = function (wrap) {"
    "  if (wired.indexOf(wrap) !== -1) { return; }"
    "  wired.push(wrap);"
    "  wrap.addEventListener('scroll', function () { markEdge(wrap); }, {passive: true});"
    " };"
    " var markEdges = function () {"
    "  var lists = document.querySelectorAll(LISTS);"
    "  for (var i = 0; i < lists.length; i += 1) {"
    "   var wrap = lists[i].parentElement;"
    "   if (wrap !== null) { wire(wrap); markEdge(wrap); }"
    "  }"
    " };"
    " var select = function (tab) {"
    "  if (tab.getAttribute('aria-selected') !== 'true') { tab.click(); }"
    " };"
    " var gestureUntil = 0; var down = null; var armed = null;"
    " var arm = function (tab) {"
    "  armed = {tab: tab};"
    "  window.setTimeout(function () {"
    "   if (armed !== null && armed.tab === tab) { armed = null; select(tab); }"
    "  }, GESTURE_MS);"
    " };"
    " var known = 0;"
    " var onChange = function (records) {"
    "  for (var i = 0; i < records.length; i += 1) {"
    "   var record = records[i];"
    "   if (record.type === 'attributes') {"
    "    if (record.target.getAttribute('aria-selected') === 'true') { reveal(record.target); }"
    "   } else {"
    "    var count = document.querySelectorAll(LISTS).length;"
    "    if (count !== known) { known = count; revealSelected(); }"
    "   }"
    "  }"
    "  markEdges();"
    " };"
    " var start = function () {"
    "  known = document.querySelectorAll(LISTS).length;"
    "  revealSelected();"
    "  markEdges();"
    "  new MutationObserver(onChange).observe(document.documentElement,"
    "   {childList: true, subtree: true, attributes: true, attributeFilter: ['aria-selected']});"
    "  window.addEventListener('resize', function () { revealSelected(); markEdges(); });"
    "  document.addEventListener('focusin', function (event) {"
    "   var tab = tabOf(event.target);"
    "   if (tab !== null && Date.now() >= gestureUntil) { reveal(tab); }"
    "  });"
    "  document.addEventListener('pointerdown', function (event) {"
    "   var tab = tabOf(event.target);"
    "   if (tab === null || scrolls(wrapOf(tab)) === false) { down = null; return; }"
    "   gestureUntil = Date.now() + GESTURE_MS;"
    "   down = {tab: tab, x: event.clientX, y: event.clientY};"
    "  }, true);"
    "  document.addEventListener('pointerup', function (event) {"
    "   if (down === null) { return; }"
    "   var gesture = down; down = null;"
    "   var moved = Math.abs(event.clientX - gesture.x) > SLOP"
    "    || Math.abs(event.clientY - gesture.y) > SLOP;"
    "   if (moved === false) { arm(gesture.tab); }"
    "  }, true);"
    "  document.addEventListener('pointercancel', function () { down = null; }, true);"
    "  document.addEventListener('click', function (event) {"
    "   if (armed === null || event.isTrusted === false) { return; }"
    "   var tab = armed.tab; armed = null;"
    "   if (tabOf(event.target) === tab) { return; }"
    "   event.stopImmediatePropagation(); event.preventDefault();"
    "   select(tab);"
    "  }, true);"
    " };"
    " if (document.readyState === 'loading') {"
    "  document.addEventListener('DOMContentLoaded', start);"
    " } else { start(); }"
    " })();"
)

#: Gradio 6.28's dropdown (`@gradio/dropdown`, read from the 6.28.0 bundle): the input's
#: `keydown` handler awaits a tick and then sets `show_options` from the key — `false` for Escape,
#: `true` for every other key, Tab included. So Tab moves focus (the `blur` handler closes the
#: list), and the awaited continuation reopens it with focus gone: `aria-expanded="true"`, the
#: listbox on the page, and Escape from wherever focus landed reaches nothing — measured 20/20
#: on the five dropdowns, Tab and Shift+Tab, light and dark (round 3, `extra/dismiss.json`).
#: This script closes what Gradio left open, the way Gradio itself closes it: a synthetic Escape
#: `keydown` on the input runs the same handler, which sets `show_options = false` and changes
#: no value (the value is written only by Enter and by a click on an option). It runs when
#: focus leaves a combobox (`focusout`), whenever a combobox turns `aria-expanded="true"` while
#: it is not the active element (the reopen after Tab), and on a real Escape anywhere on the
#: page, for every open list that has no focus. A list open under the focused input — the stock
#: open-on-focus — is left to Gradio.
#:
#: Keyboard arrival (launch review round 3): Gradio opens the list on `focus`, so tabbing
#: across a form pops a listbox at every stop and the Function list drew upward over the
#: headline. A combobox reached by Tab (a trusted Tab `keydown` within the last 400 ms) gets the
#: same synthetic Escape once Gradio has opened it: the value is untouched, the list stays shut
#: until a click, a typed character or an arrow key asks for it. And a list Gradio placed above
#: the field while the viewport had room below it is moved below (`reposition`): Gradio
#: compares the space above with the space below the field and takes the larger, even when the
#: list would fit under the field; the shell prefers below whenever the list fits there.
#:
#: Where Tab went: measured, `focusout` from the input named the listbox `<ul>` itself as the
#: next element — a scrolling container with no focusable children is keyboard-focusable in
#: Chromium — and the list is destroyed when it closes, so focus fell to `<body>` (round 3:
#: "focus on BODY"). Every `ul[role="listbox"]` therefore gets `tabindex="-1"` as it appears
#: (a popup steered by `aria-activedescendant` is not a tab stop), and Tab lands on the next
#: control: the Module box after Family, the first number after Function.
#:
#: The mouse on a box that already has focus (round 5): Gradio's single-select input binds
#: keydown/keyup/blur/focus only, so once a list is closed with Escape (or by the arrival
#: close above) a click on the focused box does nothing until focus leaves it, and the
#: chevron is `pointer-events: none`. A capture-phase `mousedown` on the focused box sends a
#: synthetic ArrowDown when the list is closed — Gradio opens it and highlights the next
#: option, the value untouched (its handler checks no `isTrusted`) — and Escape when it is
#: open, so a click toggles the list the way a pop-up button does. The arrival close also
#: fires at once (Gradio's focus handler has already run, so the list never paints) and again
#: after 40 ms, and the panel Gradio adds for the arriving box is hidden the moment it lands
#: (`hideArrivalPanel` marks it with `css.ARRIVAL_ATTR`, which the chrome sheet displays as
#: none, in the childList observer — a microtask, before any paint), so the 200 ms fly-in/out
#: never shows (round 6: a ghost of the list for 1–4 frames on every Tab). The mark is keyed
#: on the trusted Tab keydown, not on `focusin`: Svelte inserts the panel inside Gradio's
#: `focus` handler and the observer's microtask runs before `focusin` is even dispatched.
#: Round 8: a list that is OPEN when the visitor Tabs away is re-expanded by Gradio's keydown
#: continuation (a one-row list filtered to its own value) and fades out for ~230 ms under the
#: departed box — the node is reused, so the childList mark never sees it. `markPanelOf` hides
#: the departed box's existing panel on the Tab keydown itself and again whenever a box turns
#: expanded while it is not the active element.
#: The mark clears on the visitor's next intent: a trusted non-Tab key or the mouse. An upward
#: panel moves below the field whenever `MIN_LIST_PX` remain; with less room the page scrolls
#: by the shortfall first (a phone at its landing position has ~135 px under the Race box),
#: then the list opens below capped to the room, never over the header and the tab strip.
#: Gradio re-positions the panel on every scroll (`bottom` comes back); the placed panel is
#: watched for style changes and placed again, at most eight times per opening.
MIN_LIST_PX = 176
#: The least room a list is placed below the field with (two 44 px rows and a pad); with less,
#: the page is scrolled first so `MIN_LIST_PX` fit, and the list opens below capped to the room.
MIN_ROWS_PX = 104
DROPDOWN_CLOSE_SCRIPT = (
    "(function () {"
    f" var BOX = '{COMBOBOX}';"
    f" var LIST = '{LISTBOX}';"
    " var OPEN = BOX + '[aria-expanded=\"true\"]';"
    " var escape = function (box) {"
    "  box.dispatchEvent(new KeyboardEvent('keydown',"
    "   {key: 'Escape', code: 'Escape', bubbles: true, cancelable: true}));"
    " };"
    " var arrow = function (box) {"
    "  box.dispatchEvent(new KeyboardEvent('keydown',"
    "   {key: 'ArrowDown', code: 'ArrowDown', bubbles: true, cancelable: true}));"
    " };"
    " var unfocusable = function () {"
    "  var lists = document.querySelectorAll(LIST);"
    "  for (var i = 0; i < lists.length; i += 1) {"
    "   if (lists[i].getAttribute('tabindex') !== '-1') {"
    " lists[i].setAttribute('tabindex', '-1'); }"
    "  }"
    " };"
    " var closeUnfocused = function () {"
    "  var boxes = document.querySelectorAll(OPEN);"
    "  for (var i = 0; i < boxes.length; i += 1) {"
    "   if (boxes[i] !== document.activeElement) { escape(boxes[i]); }"
    "  }"
    " };"
    " var queued = false;"
    " var schedule = function () {"
    "  if (queued) { return; }"
    "  queued = true;"
    "  window.setTimeout(function () { queued = false; closeUnfocused(); }, 0);"
    " };"
    " var isBox = function (node) {"
    "  return node !== null && node.matches !== undefined && node.matches(BOX);"
    " };"
    " var tabbedAt = 0;"
    " var arrivalCleared = false;"
    " var arriving = function () {"
    "  return arrivalCleared === false && Date.now() - tabbedAt <= 400"
    "   && isBox(document.activeElement);"
    " };"
    " var closeIfTabbedInto = function (box) {"
    "  if (Date.now() - tabbedAt > 400) { return; }"
    "  escape(box);"
    "  window.setTimeout(function () {"
    "   if (box === document.activeElement"
    "    && box.getAttribute('aria-expanded') === 'true') { escape(box); }"
    "  }, 40);"
    " };"
    f" var ARRIVAL_ATTR = '{ARRIVAL_ATTR}';"
    " var hideArrivalPanel = function (panel) {"
    "  if (arriving() === false) { return false; }"
    "  panel.setAttribute(ARRIVAL_ATTR, '');"
    "  return true;"
    " };"
    " var LIST_PANEL = 'div.options';"
    " var markPanelOf = function (box) {"
    "  var wrap = box.closest('.wrap');"
    "  var panel = wrap === null ? null : wrap.querySelector(LIST_PANEL);"
    "  if (panel !== null) { panel.setAttribute(ARRIVAL_ATTR, ''); }"
    " };"
    f" var MIN_LIST_PX = {MIN_LIST_PX};"
    f" var MIN_ROWS_PX = {MIN_ROWS_PX};"
    " var placed = null;"
    " var placedBox = null;"
    " var placements = 0;"
    " var placeBelow = function (panel, box) {"
    "  var rect = box.getBoundingClientRect();"
    "  var room = window.innerHeight - rect.bottom - 16;"
    "  if (room < MIN_ROWS_PX) { return false; }"
    "  if (placed !== panel) { placed = panel; placedBox = box; placements = 0; }"
    "  placements += 1;"
    "  panel.style.bottom = '';"
    "  panel.style.top = rect.bottom + 'px';"
    "  panel.style.maxHeight = Math.min(room, 400) + 'px';"
    "  return true;"
    " };"
    " var keepPlaced = function (record) {"
    "  if (placed === null || record.target !== placed) { return; }"
    "  if (placed.isConnected === false) { placed = null; placedBox = null; return; }"
    "  if (placed.style.bottom !== '' && placements < 8) { placeBelow(placed, placedBox); }"
    " };"
    " var reposition = function (panel) {"
    "  var box = document.querySelector(OPEN);"
    "  if (box === null || panel.style.bottom === '') { return; }"
    "  var rect = box.getBoundingClientRect();"
    "  var room = window.innerHeight - rect.bottom - 16;"
    "  if (room >= MIN_LIST_PX) { placeBelow(panel, box); return; }"
    "  var want = Math.min(panel.scrollHeight || MIN_LIST_PX, 400);"
    "  var shortfall = Math.min(want, MIN_LIST_PX) - room;"
    "  var before = window.scrollY;"
    "  window.scrollBy(0, shortfall);"
    "  if (window.scrollY === before) { placeBelow(panel, box); return; }"
    "  window.requestAnimationFrame(function () { placeBelow(panel, box); });"
    " };"
    " var later = function (panel) {"
    "  window.requestAnimationFrame(function () { reposition(panel); });"
    " };"
    " var repositionAdded = function (record) {"
    "  for (var i = 0; i < record.addedNodes.length; i += 1) {"
    "   var node = record.addedNodes[i];"
    "   if (node.nodeType === 1) {"
    "    var panel = node.matches(LIST_PANEL) ? node : node.querySelector(LIST_PANEL);"
    "    if (panel !== null && hideArrivalPanel(panel) === false) { later(panel); }"
    "   }"
    "  }"
    " };"
    " var start = function () {"
    "  unfocusable();"
    "  document.addEventListener('keydown', function (event) {"
    "   if (event.isTrusted === false) { return; }"
    "   if (event.key === 'Tab') {"
    "    tabbedAt = Date.now(); arrivalCleared = false;"
    "    if (isBox(event.target) && event.target.getAttribute('aria-expanded') === 'true') {"
    "     markPanelOf(event.target); }"
    "   }"
    "   else if (event.key !== 'Shift') { arrivalCleared = true; }"
    "  }, true);"
    "  document.addEventListener('focusin', function (event) {"
    "   if (isBox(event.target)) { closeIfTabbedInto(event.target); }"
    "  });"
    "  document.addEventListener('mousedown', function (event) {"
    "   arrivalCleared = true;"
    "   var box = event.target;"
    "   if (isBox(box) === false || box !== document.activeElement) { return; }"
    "   var open = box.getAttribute('aria-expanded') === 'true';"
    "   window.setTimeout(function () {"
    "    if (box !== document.activeElement) { return; }"
    "    if (open) { escape(box); }"
    "    else if (box.getAttribute('aria-expanded') !== 'true') { arrow(box); }"
    "   }, 0);"
    "  }, true);"
    "  document.addEventListener('focusout', function (event) {"
    "   if (isBox(event.target)) { schedule(); }"
    "  });"
    "  document.addEventListener('keydown', function (event) {"
    "   if (event.key === 'Escape' && event.isTrusted) { closeUnfocused(); }"
    "  }, true);"
    "  new MutationObserver(function (records) {"
    "   var added = false;"
    "   for (var i = 0; i < records.length; i += 1) {"
    "    var record = records[i];"
    "    if (record.type === 'childList') {"
    " added = added || record.addedNodes.length > 0; repositionAdded(record); continue; }"
    "    if (record.attributeName === 'style') { keepPlaced(record); continue; }"
    "    var box = record.target;"
    "    if (isBox(box) && box.getAttribute('aria-expanded') === 'true'"
    "     && box !== document.activeElement) { markPanelOf(box); schedule(); }"
    "   }"
    "   if (added) { unfocusable(); }"
    "  }).observe(document.documentElement,"
    "   {childList: true, subtree: true, attributes: true,"
    "    attributeFilter: ['aria-expanded', 'style']});"
    " };"
    " if (document.readyState === 'loading') {"
    "  document.addEventListener('DOMContentLoaded', start);"
    " } else { start(); }"
    " })();"
)

#: A chip or a header pill whose text takes more than one line is marked with `CHIP_WRAP_ATTR`,
#: so the card sheet and the shell sheet draw it as a 12 px tag (44 px or taller) instead of two
#: lines inside a 999 px pill. The line count comes from the element's line boxes
#: (`Range.getClientRects`, distinct row tops), which the attribute does not change, so every
#: pass is idempotent: chips hidden with their tab or accordion (`offsetParent === null`) are
#: skipped and measured when they show. One pass per animation frame on DOM, `class`, `style`
#: and `aria-selected` changes, on resize and once the web fonts land; the attribute itself is
#: not observed, so a pass never schedules another.
CHIP_WRAP_SCRIPT = (
    "(function () {"
    f" var ATTR = '{CHIP_WRAP_ATTR}';"
    f" var CHIPS = '{WRAP_SELECTOR}';"
    " var lines = function (chip) {"
    "  var range = document.createRange(); range.selectNodeContents(chip);"
    "  var rects = range.getClientRects(); var tops = [];"
    "  for (var i = 0; i < rects.length; i += 1) {"
    "   var rect = rects[i];"
    "   if (rect.width === 0 || rect.height === 0) { continue; }"
    "   var top = Math.round(rect.top);"
    "   if (tops.indexOf(top) === -1) { tops.push(top); }"
    "  }"
    "  return tops.length;"
    " };"
    " var markAll = function () {"
    "  var chips = document.querySelectorAll(CHIPS);"
    "  for (var i = 0; i < chips.length; i += 1) {"
    "   var chip = chips[i];"
    "   if (chip.offsetParent === null) { continue; }"
    "   var wrapped = lines(chip) > 1;"
    "   if (wrapped && chip.hasAttribute(ATTR) === false) { chip.setAttribute(ATTR, ''); }"
    "   else if (wrapped === false && chip.hasAttribute(ATTR)) { chip.removeAttribute(ATTR); }"
    "  }"
    " };"
    " var queued = false;"
    " var schedule = function () {"
    "  if (queued) { return; }"
    "  queued = true;"
    "  window.requestAnimationFrame(function () { queued = false; markAll(); });"
    " };"
    " var start = function () {"
    "  markAll();"
    "  new MutationObserver(schedule).observe(document.documentElement,"
    "   {childList: true, subtree: true, attributes: true,"
    "    attributeFilter: ['style', 'class', 'aria-selected']});"
    "  window.addEventListener('resize', schedule);"
    "  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(schedule); }"
    " };"
    " if (document.readyState === 'loading') {"
    "  document.addEventListener('DOMContentLoaded', start);"
    " } else { start(); }"
    " })();"
)

HEAD_SCRIPTS: tuple[str, ...] = (
    NAV_ROWS_SCRIPT,
    DISCLOSURE_SCRIPT,
    TABSTRIP_SCRIPT,
    CHIP_WRAP_SCRIPT,
    DROPDOWN_CLOSE_SCRIPT,
)
#: The fragment a host page puts in `<head>` (the flagship's `app.py` appends it to its own):
#: the five head scripts. `SHELL_HEAD` is the same fragment under the name that says so.
NAV_ROWS_HEAD = "".join(f"<script>{script}</script>" for script in HEAD_SCRIPTS)
SHELL_HEAD = NAV_ROWS_HEAD
