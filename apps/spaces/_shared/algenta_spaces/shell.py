"""One header, one footer, one stylesheet for the Algenta Spaces.

Lifted from the fleet's canonical shell (`apps/spaces/_retired/shell.canonical.py`):
`render_header` / `render_footer` / `SHELL_CSS` keep the same discipline — every
selector repeats its class four times so it beats Gradio's scoped resets without
`!important`, no Gradio selectors, colours from `var(--alg-*)` tokens.

What changed for the flagship fleet: the nav is the three live Spaces plus the
Kernels Hub, GitHub, Docs, Pricing and Discord; a Duplicate link is built from
the Space id; the footer carries the canon one-liner, the licence line and the
deploy stamp read from `.shared_sha` next to the package.

Copy rules are enforced at render time: a headline is at most six words, a
subline at most fourteen, no exclamation marks, no emoji, none of the banned
phrases. Stdlib only.
"""

from __future__ import annotations

import html
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from .css import rule, stylesheet
from .runtime import read_stamp

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

NAV: tuple[tuple[str, str], ...] = (
    ("Flagship", FLAGSHIP_URL),
    ("Speed Arena", SPEED_ARENA_URL),
    ("Governed Agent", GOVERNED_AGENT_URL),
    ("Kernels Hub", KERNELS_HUB_URL),
    ("GitHub", GITHUB_URL),
    ("Docs", DOCS_URL),
    ("Pricing", PRICING_URL),
    ("Discord", DISCORD_URL),
)
NAV_LABELS = frozenset(label for label, _ in NAV)

HEADLINE_WORDS = 6
SUBLINE_WORDS = 14

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
_SEP = '<span class="alg-shell-sep">·</span>'


def _esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def banned_phrase(text: str) -> str | None:
    """The first banned phrase found in `text`, or None."""
    match = _BANNED_RE.search(text)
    return match.group(0) if match else None


def has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


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


def _badge_html(badge: str | tuple[str, str]) -> str:
    """One pill. `badge` is plain text (neutral) or a (text, variant) tuple."""
    if isinstance(badge, tuple):
        text, variant = badge
    else:
        text, variant = badge, ""
    if variant not in _BADGE_VARIANTS:
        raise ValueError(f"unknown badge variant {variant!r}; expected one of {_BADGE_VARIANTS}")
    check_copy(text, max_words=SUBLINE_WORDS, what="badge")
    cls = "alg-shell-badge" + (f" alg-shell-badge-{variant}" if variant else "")
    return f'<span class="{cls}">{_esc(text)}</span>'


def _links_html(active: str | None, link_class: str, active_class: str) -> str:
    items = []
    for label, url in NAV:
        if label == active:
            items.append(f'<span class="{active_class}" aria-current="page">{_esc(label)}</span>')
        else:
            items.append(f'<a class="{link_class}" href="{url}">{_esc(label)}</a>')
    return _SEP.join(items)


def _nav_html(active: str | None, space_id: str) -> str:
    links = _links_html(active, "alg-shell-nav-link", "alg-shell-nav-active")
    right = ""
    if space_id:
        right = (
            f'<a class="alg-shell-nav-dup" href="{duplicate_url(space_id)}" rel="noopener">'
            "Duplicate this Space</a>"
        )
    return (
        '<nav class="alg-shell-nav" aria-label="Algenta">'
        f'<span class="alg-shell-nav-links">{links}</span>{right}</nav>'
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
        f'<h1 class="alg-shell-title">{_esc(title)}</h1>',
        f'<p class="alg-shell-tagline">{_esc(tagline)}</p>',
    ]
    if badges:
        pills = "".join(_badge_html(b) for b in badges)
        parts.append(f'<div class="alg-shell-badges">{pills}</div>')
    parts.append(_nav_html(active, sid))
    parts.append("</header>")
    return "".join(parts)


def render_footer(*, active: str | None = None, stamp: str | None = None) -> str:
    """The fleet footer: brand and canon line, licence line, links, deploy stamp."""
    if active is not None and active not in NAV_LABELS:
        raise ValueError(f"active {active!r} is not a NAV label")
    build = shared_sha() if stamp is None else stamp
    links = _links_html(active, "alg-shell-footer-link", "alg-shell-footer-active")
    return (
        '<footer class="alg-shell-footer">'
        '<div class="alg-shell-footer-row">'
        '<span class="alg-shell-footer-brand">Algenta</span>'
        f'<span class="alg-shell-footer-canon">{_esc(CANON)}</span>'
        "</div>"
        f'<p class="alg-shell-footer-licence">{_esc(LICENCE_LINE)}</p>'
        '<div class="alg-shell-footer-row">'
        f'<span class="alg-shell-footer-links">{links}</span>'
        f'<span class="alg-shell-stamp">build {_esc(build)}</span>'
        "</div>"
        "</footer>"
    )


# ---------------------------------------------------------------------------
# SHELL_CSS — alg-shell-* classes only. css.rule() repeats each class four
# times so the rules beat Gradio's scoped resets without `!important`.
# Colours, type and spacing come from design.TOKENS_CSS; margins, paddings
# and gaps use only the 8-pt scale. Every interactive target is 44 px tall:
# the mono line (20 px) plus 2 x 12 px padding, all on the scale. Links are
# flex items, so the padding is real layout, not inline-box paint. Focus rings
# are visible and follow the element's own radius (input radius for text
# links, the pill radius for the Duplicate pill).
# ---------------------------------------------------------------------------

_RING = "outline: 2px solid var(--alg-accent-to); outline-offset: 2px;"
_FOCUS = f"{_RING} border-radius: var(--alg-radius-input);"
_FOCUS_PILL = f"{_RING} border-radius: var(--alg-radius-pill);"
_CAPTION = "font-size: var(--alg-caption-size); line-height: var(--alg-caption-line);"
_TARGET = "line-height: var(--alg-mono-line); padding: 12px 0;"
_LINK = f"color: var(--alg-text); text-decoration: none; {_TARGET}"
_ROW = (
    "display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline;"
    " gap: 8px 16px;"
)
_LINKS = "display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px;"

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
        " color: var(--alg-text); margin: 0 0 8px;",
    ),
    rule(
        "alg-shell-tagline",
        "font-size: var(--alg-body-size); line-height: var(--alg-body-line);"
        " color: var(--alg-text-2); inline-size: min(64ch, 100%); margin: 0;",
    ),
    rule("alg-shell-badges", "display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0;"),
    rule(
        "alg-shell-badge",
        f"font-family: var(--alg-font-mono); {_CAPTION} color: var(--alg-text-2);"
        " border: 1px solid var(--alg-hairline); border-radius: var(--alg-radius-pill);"
        " padding: 4px 12px;",
    ),
    rule("alg-shell-badge-ok", "color: var(--alg-ok);"),
    rule("alg-shell-badge-warn", "color: var(--alg-warn);"),
    rule(
        "alg-shell-nav",
        "display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;"
        " gap: 4px 16px; margin: 12px 0 0; font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line);",
    ),
    rule("alg-shell-nav-links", _LINKS),
    rule("alg-shell-nav-link", _LINK),
    rule("alg-shell-nav-link", "text-decoration: underline;", suffix=":hover"),
    rule("alg-shell-nav-link", _FOCUS, suffix=":focus-visible"),
    rule("alg-shell-nav-active", f"color: var(--alg-text-2); {_TARGET}"),
    rule(
        "alg-shell-nav-dup",
        "color: var(--alg-text); text-decoration: none; border: 1px solid var(--alg-hairline);"
        " border-radius: var(--alg-radius-pill); line-height: var(--alg-mono-line);"
        " padding: 12px 16px;",
    ),
    rule("alg-shell-nav-dup", "border-color: var(--alg-text-2);", suffix=":hover"),
    rule("alg-shell-nav-dup", _FOCUS_PILL, suffix=":focus-visible"),
    rule("alg-shell-sep", "color: var(--alg-text-2);"),
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
    rule("alg-shell-footer-links", _LINKS),
    rule("alg-shell-footer-link", _LINK),
    rule("alg-shell-footer-link", "text-decoration: underline;", suffix=":hover"),
    rule("alg-shell-footer-link", _FOCUS, suffix=":focus-visible"),
    rule("alg-shell-footer-active", f"color: var(--alg-text-2); {_TARGET}"),
    rule(
        "alg-shell-stamp",
        "font-family: var(--alg-font-mono); font-variant-numeric: tabular-nums;"
        " color: var(--alg-text-2);",
    ),
)
