"""Copy and stylesheet rules every user-visible string in the fleet must obey.

Helpers carry a leading underscore: pytest-relaxed, when present on a developer
machine, collects every public function of a non-`test_` module as a test.
"""

from __future__ import annotations

import re

from algenta_spaces import design, shell

# What the no-fake lint and the copy lint will grep for later; asserted here first.
FAKE_WORDS = re.compile(
    r"TODO|FIXME|XXX|placeholder|lorem|coming soon|\bmock|\bDemo|Simulated|NotImplementedError",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")
PX_RE = re.compile(r"(-?\d+(?:\.\d+)?)px")
SPACING_DECL_RE = re.compile(r"(?:^|[;{]\s*)(?:margin|padding|gap)(?:-[a-z]+)?\s*:\s*([^;}]+)")


def _text_of(html: str) -> str:
    return TAG_RE.sub(" ", html)


def _assert_clean_copy(html: str) -> None:
    """No banned phrase, no emoji, no exclamation mark, no fake-word in rendered text."""
    text = _text_of(html)
    assert shell.banned_phrase(text) is None, shell.banned_phrase(text)
    assert not shell.has_emoji(text), "emoji in chrome"
    assert "!" not in text, "exclamation mark in copy"
    assert FAKE_WORDS.search(text) is None, FAKE_WORDS.search(text)


def _assert_stylesheet_discipline(css: str) -> None:
    """No !important, no Gradio selectors, spacing on the 8-pt scale only."""
    assert "!important" not in css
    assert ".gradio-container" not in css
    assert ".prose" not in css
    allowed = {0, *design.SPACING}
    for match in SPACING_DECL_RE.finditer(css):
        for value in PX_RE.findall(match.group(1)):
            assert float(value) in allowed, f"{value}px is off the 8-pt scale in {match.group(0)!r}"


def _luminance(hex_color: str) -> float:
    """WCAG relative luminance of a `#RRGGBB` colour."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio between two `#RRGGBB` colours."""
    lf, lb = _luminance(fg), _luminance(bg)
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)


def _midpoint(a: str, b: str) -> str:
    """The sRGB midpoint of two `#RRGGBB` colours (where a two-stop gradient is at 50%)."""
    return "#" + "".join(
        f"{(int(a[i : i + 2], 16) + int(b[i : i + 2], 16)) // 2:02X}" for i in (1, 3, 5)
    )


def _assert_four_class_selectors(css: str) -> None:
    """Every class selector outside at-rule headers repeats its class four times."""
    for line in css.splitlines():
        line = line.strip()
        if not line or line.startswith("@") or line == "}":
            continue
        selector = line.split("{", 1)[0].strip()
        first = selector.split(".")[1].split(":")[0].split(" ")[0]
        assert selector.startswith(f".{first}" * 4), selector
