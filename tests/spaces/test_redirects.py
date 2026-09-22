"""Static redirect stubs for the three retired Spaces.

Each stub is a ``sdk: static`` Space: README.md (frontmatter), index.html (canonical link +
a 44 px primary button + the old-tab mapping table; no timed meta refresh, which axe-core
rates critical) and a byte-identical copy of the shared style.css whose ``--alg-*`` tokens
equal design.py's. The tests here are the M0 gate for `SPACES-RETIRE-001`: destinations,
copy budgets, the positioning canon, no external requests, and the execution standard.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from _rules import _contrast, _midpoint
from algenta_spaces import design

REPO = Path(__file__).resolve().parents[2]
REDIRECTS = REPO / "apps" / "spaces" / "_redirects"
RETIRED = REPO / "apps" / "spaces" / "_retired"

FLAGSHIP = "https://huggingface.co/spaces/thyn-ai/algenta"
ARENA = "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"
AGENT = "https://huggingface.co/spaces/thyn-ai/algenta-governed-agent"
PRICING = "https://algenta.ai/pricing"
DISCORD = "https://discord.gg/w8NDsph9an"

REQUIRED_SENTENCE = "This lab moved into the Algenta flagship."
CLICK_ONLY_SENTENCE = "This page redirects only on click."

# Old tab → new destination, exactly as the plan's Target-experience section specifies.
# Arena rows link to the Speed Arena root: the arena restores no `?duel=` state yet, and a
# link must never promise a state the target cannot restore. The duel is named in the row.
EXPECTED: dict[str, dict[str, str | dict[str, str]]] = {
    "for-llm-agents": {
        "target": FLAGSHIP,
        "tabs": {
            "RAG retrieval duel": ARENA,
            "LLM output scorer": ARENA,
            "Prompt-injection governance duel": AGENT,
            "MCP playground": f"{FLAGSHIP}?tab=gov",
            "Examples library": f"{FLAGSHIP}?tab=eco",
        },
    },
    "governed-tool-calls": {
        "target": f"{FLAGSHIP}?tab=gov",
        "tabs": {
            "Approve / deny a governed tool call": f"{FLAGSHIP}?tab=gov",
            "Audit log": f"{FLAGSHIP}?tab=gov",
            "Use from smolagents": f"{FLAGSHIP}?tab=gov",
        },
    },
    "llm-modules": {
        "target": f"{FLAGSHIP}?tab=llm",
        "tabs": {
            "Live module runner": f"{FLAGSHIP}?tab=llm",
            "Tokenize": f"{FLAGSHIP}?tab=llm",
            "Mini-KB retrieval": f"{FLAGSHIP}?tab=llm",
            "Attention lab": f"{FLAGSHIP}?tab=llm",
            "Column ranker": f"{FLAGSHIP}?tab=llm",
            "Serving math": f"{FLAGSHIP}?tab=llm",
            "Sampling · eval · alignment": f"{FLAGSHIP}?tab=llm",
            "The 22 modules": f"{FLAGSHIP}?tab=llm",
            "Use it yourself": f"{FLAGSHIP}?tab=eco",
        },
    },
}
STUBS = sorted(EXPECTED)

RETIRED_URL_FRAGMENTS = (
    "algenta-for-llm-agents",
    "algenta-governed-tool-calls",
    "algenta-llm-modules",
)
ALLOWED_HREF_PREFIXES = (FLAGSHIP, ARENA, AGENT, PRICING, DISCORD)

# Positioning canon + Apple copy rules (banned in every user-visible string).
BANNED_PHRASES = (
    "decision engine",
    "@algenta.ai",
    "cgroup",
    "R4/R7/R9",
    "wire shape",
    "harness v",
    "SIMULATED",
    "simulated",
    "clean-room",
    "post-open-source",
    "defensibility",
    "bit-faithful",
    "TODO",
    "FIXME",
    "placeholder",
    "lorem",
    "coming soon",
    "mock",
)

# Emoji and pictographs (frontmatter only); arrows and the middle dot are not in these ranges.
EMOJI_RE = re.compile("[\U0001f000-\U0001faff☀-➿⬀-⯿️\U0001f1e6-\U0001f1ff]")

ALLOWED_SPACING_PX = {0, *design.SPACING}
ALLOWED_SHADOWS = {"none", design.SHADOW}
TOKEN_RE = re.compile(r"--(alg-[\w-]+):\s*([^;]+);")


class _Page(HTMLParser):
    """Collect what the assertions need: tags with attributes, text per element."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self._stack: list[str] = []
        self.h1: list[str] = []
        self.sublines: list[str] = []
        self.row_headers: list[str] = []
        self.body_text: list[str] = []
        self.anchors: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        self._stack.append(tag)
        if tag == "a":
            self._current_href = attributes.get("href") or ""
            self._anchor_text = []
        if tag == "p" and attributes.get("class") == "alg-subline":
            self._stack[-1] = "p.alg-subline"
        if tag == "th" and attributes.get("scope") == "row":
            self._stack[-1] = "th.row"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            self.anchors.append((self._current_href, "".join(self._anchor_text).strip()))
            self._current_href = None
        while self._stack:
            top = self._stack.pop()
            if top.split(".")[0] == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self._stack:
            return
        top = self._stack[-1]
        if top not in {"style", "title", "head"}:
            self.body_text.append(data)
        if top == "h1":
            self.h1.append(data)
        elif top == "p.alg-subline":
            self.sublines.append(data)
        elif top == "th.row":
            self.row_headers.append(data.strip())
        if self._current_href is not None:
            self._anchor_text.append(data)


def parse_page(stub: str) -> _Page:
    page = _Page()
    page.feed((REDIRECTS / stub / "index.html").read_text(encoding="utf-8"))
    page.close()
    return page


def parse_frontmatter(path: Path) -> tuple[dict[str, str | bool | list[str]], str]:
    """Parse the simple ``key: value`` YAML block the Hub reads; return (fields, body)."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    head, _, body = text[4:].partition("\n---\n")
    fields: dict[str, str | bool | list[str]] = {}
    last_key = ""
    for line in head.splitlines():
        if line.startswith("  - "):  # YAML block list continuing the previous key
            items = fields.setdefault(last_key, [])
            assert isinstance(items, list), f"{path}: block list under a scalar {last_key!r}"
            items.append(line[4:].strip())
            continue
        key, sep, raw = line.partition(":")
        last_key = key.strip()
        assert sep, f"{path}: not a key: value line: {line!r}"
        value = raw.strip()
        if not value:
            fields[last_key] = []
        elif value in {"true", "false"}:
            fields[key.strip()] = value == "true"
        elif value.startswith("[") and value.endswith("]"):
            fields[key.strip()] = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        else:
            fields[key.strip()] = value
    return fields, body.strip()


def retired_tabs(stub: str) -> list[str]:
    """Every ``gr.Tab("...")`` label in the retired Space's app.py, in source order."""
    source = (RETIRED / stub / "app.py").read_text(encoding="utf-8")
    return re.findall(r'gr\.Tab\(\s*"([^"]+)"', source)


# --------------------------------------------------------------------------- README


@pytest.mark.parametrize("stub", STUBS)
def test_readme_frontmatter(stub: str) -> None:
    fields, body = parse_frontmatter(REDIRECTS / stub / "README.md")
    original, _ = parse_frontmatter(RETIRED / stub / "README.md")
    assert fields["title"] == "Moved to Algenta", "four cards named Algenta in search is wrong"
    assert fields["emoji"] == original["emoji"], "emoji must match the retired Space's card"
    assert fields["colorFrom"] == "purple"
    assert fields["colorTo"] == "blue"
    assert fields["sdk"] == "static"
    assert fields["pinned"] is False
    assert fields["license"] == "apache-2.0"
    assert fields["tags"] == ["deprecated", "moved"]
    assert fields["short_description"] == "Moved to thyn-ai/algenta"
    sentences = [s for s in re.split(r"(?<=[.])\s+", body) if s]
    assert len(sentences) == 2, body
    assert FLAGSHIP in body
    assert not EMOJI_RE.search(body), "emoji only in frontmatter"
    assert "!" not in body
    for phrase in BANNED_PHRASES:
        assert phrase.lower() not in body.lower(), phrase


# ----------------------------------------------------------------------- index.html


@pytest.mark.parametrize("stub", STUBS)
def test_redirect_targets(stub: str) -> None:
    page = parse_page(stub)
    target = EXPECTED[stub]["target"]
    # axe-core meta-refresh is critical for any 0 < delay < 72000 s, and a 0 s refresh would
    # hide the mapping table: the page redirects only on click.
    assert not [a for t, a in page.tags if t == "meta" and a.get("http-equiv")], "no meta refresh"
    html = (REDIRECTS / stub / "index.html").read_text(encoding="utf-8")
    assert "http-equiv" not in html and "refresh" not in html.lower()
    canonical = [a for t, a in page.tags if t == "link" and a.get("rel") == "canonical"]
    assert len(canonical) == 1
    assert canonical[0].get("href") == target
    primary = [
        (href, attrs)
        for (href, text), (tag, attrs) in zip(
            page.anchors, [(t, a) for t, a in page.tags if t == "a"], strict=True
        )
        if text == "Open the new home"
    ]
    assert [href for href, _ in primary] == [target]
    assert primary[0][1].get("class") == "alg-button", "the primary link is the 44 px button"
    assert CLICK_ONLY_SENTENCE in " ".join(page.body_text)
    assert "<title>Moved to Algenta</title>" in html


@pytest.mark.parametrize("stub", STUBS)
def test_arena_links_carry_no_query_string(stub: str) -> None:
    page = parse_page(stub)
    for href, text in page.anchors:
        if href.startswith(ARENA):
            assert "?" not in href and "#" not in href, href
            assert "duel" in text.lower(), "the duel is named in the row, not in the URL"


@pytest.mark.parametrize("stub", STUBS)
def test_every_old_tab_is_mapped(stub: str) -> None:
    page = parse_page(stub)
    expected_tabs = EXPECTED[stub]["tabs"]
    assert isinstance(expected_tabs, dict)
    assert retired_tabs(stub) == list(expected_tabs), "the retired app.py grew or renamed a tab"
    assert page.row_headers == list(expected_tabs)
    row_links = [
        href for href, text in page.anchors if text.startswith(("Flagship", "Speed", "Gov"))
    ]
    assert row_links == list(expected_tabs.values())


@pytest.mark.parametrize("stub", STUBS)
def test_links_point_only_at_live_destinations(stub: str) -> None:
    page = parse_page(stub)
    assert page.anchors, "no links"
    for href, text in page.anchors:
        assert href.startswith(ALLOWED_HREF_PREFIXES), href
        assert text, f"empty link text for {href}"
        for fragment in RETIRED_URL_FRAGMENTS:
            assert fragment not in href, f"{href} points at a retired Space"
    hrefs = [href for href, _ in page.anchors]
    assert PRICING in hrefs and DISCORD in hrefs
    for tag, attrs in page.tags:
        if tag == "a":
            assert attrs.get("target") == "_top", "static Spaces render in an iframe"


@pytest.mark.parametrize("stub", STUBS)
def test_no_external_requests_and_no_script(stub: str) -> None:
    page = parse_page(stub)
    for tag, attrs in page.tags:
        assert tag != "script"
        if tag == "a":
            continue
        if tag == "link" and attrs.get("rel") == "canonical":
            continue
        for name, value in attrs.items():
            assert not (value or "").startswith(("http:", "https:", "//")), (tag, name, value)
    stylesheets = [a for t, a in page.tags if t == "link" and a.get("rel") == "stylesheet"]
    assert [a.get("href") for a in stylesheets] == ["style.css"]
    html = (REDIRECTS / stub / "index.html").read_text(encoding="utf-8")
    assert "<style" not in html and "onclick" not in html and "javascript:" not in html


@pytest.mark.parametrize("stub", STUBS)
def test_copy_budgets_and_canon(stub: str) -> None:
    page = parse_page(stub)
    headline = " ".join("".join(page.h1).split())
    assert headline, "no headline"
    assert len(headline.split()) <= 6, headline
    subline = " ".join("".join(page.sublines).split())
    assert subline.startswith(REQUIRED_SENTENCE), subline
    assert len(subline.split()) <= 14, subline
    body = " ".join(page.body_text)
    assert "!" not in body, "no exclamation marks"
    assert not EMOJI_RE.search(body), "no emoji in the app chrome"
    assert "compiler-driven, self-hosted AI infrastructure" in body
    for phrase in BANNED_PHRASES:
        assert phrase.lower() not in body.lower(), phrase
    html = (REDIRECTS / stub / "index.html").read_text(encoding="utf-8")
    assert html.startswith('<!doctype html>\n<html lang="en">')
    for landmark in ("<main", "<article", "<header", "<section", "<footer", "<table", "<caption"):
        assert landmark in html, landmark
    assert 'scope="col"' in html and 'scope="row"' in html


# ------------------------------------------------------------------------ style.css


def _css() -> str:
    return (REDIRECTS / STUBS[0] / "style.css").read_text(encoding="utf-8")


def test_stylesheets_are_byte_identical() -> None:
    blobs = [(REDIRECTS / stub / "style.css").read_bytes() for stub in STUBS]
    assert len(blobs) == 3
    assert blobs[0] == blobs[1] == blobs[2]
    assert len(blobs[0]) < 500 * 1024


def _tokens(block: str) -> dict[str, str]:
    return {name: value.strip() for name, value in TOKEN_RE.findall(block)}


def _stub_token_blocks(css: str) -> tuple[str, str]:
    """(light `:root` block, dark `:root` block inside the prefers-color-scheme media query)."""
    light = re.search(r"^:root \{\n(.*?)\n\}", css, re.S | re.M)
    dark = re.search(
        r"@media \(prefers-color-scheme: dark\) \{\n\s+:root \{\n(.*?)\n\s+\}\n\}", css, re.S
    )
    assert light and dark, "style.css must declare :root and a dark :root under the media query"
    return light.group(1), dark.group(1)


def _design_token_blocks() -> tuple[str, str]:
    """(every design.py `:root` block joined, the `.dark` block)."""
    roots = re.findall(r"^:root \{\n(.*?)\n\}", design.TOKENS_CSS, re.S | re.M)
    dark = re.search(r"^\.dark \{\n(.*?)\n\}", design.TOKENS_CSS, re.S | re.M)
    assert len(roots) == 2 and dark
    return "\n".join(roots), dark.group(1)


def test_css_tokens_equal_design_py_in_both_modes() -> None:
    css = _css()
    assert "color-scheme: light dark" in css
    stub_light, stub_dark = _stub_token_blocks(css)
    design_light, design_dark = _design_token_blocks()
    assert _tokens(stub_light) == _tokens(design_light), "light tokens drifted from design.py"
    assert _tokens(stub_dark) == _tokens(design_dark), "dark tokens drifted from design.py"
    # no token is declared anywhere else in the sheet, so the two blocks are the whole set
    declared = TOKEN_RE.findall(css)
    assert len(declared) == len(_tokens(stub_light)) + len(_tokens(stub_dark))
    for name in ("alg-radius-chip", "alg-focus"):
        assert f"--{name}" not in css, f"--{name} is not a design.py token"
    for name in ("alg-bg", "alg-surface", "alg-text", "alg-text-2", "alg-hairline"):
        assert css.count(f"--{name}:") == 2, f"--{name} must be set for light and dark"
    assert f"--alg-text-2: {design.COLOR_TOKENS['text-2'][0]};" in stub_light
    assert f"--alg-font: {design.FONT_SANS};" in stub_light
    assert f"--alg-font-mono: {design.FONT_MONO};" in stub_light
    # every var() the rules use is a declared token
    for name in re.findall(r"var\(--(alg-[\w-]+)\)", css):
        assert name in _tokens(stub_light), name


def test_css_type_scale_and_grid() -> None:
    css = _css()
    assert "font-size: 40px;\n  line-height: 48px;" in css
    assert "font-size: 28px;\n  line-height: 34px;" in css
    assert "font-size: 15px;\n  line-height: 22px;" in css
    assert "font-size: 12px;\n  line-height: 16px;" in css
    assert "font-variant-numeric: tabular-nums" in css
    assert "letter-spacing: -0.02em" in css
    for prop in ("margin", "padding", "gap"):
        for match in re.finditer(rf"\b{prop}(?:-\w+)?:\s*([^;]+);", css):
            for token in match.group(1).split():
                if token.endswith("px"):
                    assert int(token[:-2]) in ALLOWED_SPACING_PX, match.group(0)
    assert "--alg-radius-card: 12px" in css
    assert "--alg-radius-input: 8px" in css
    assert "--alg-radius-pill: 999px" in css
    assert "--alg-content-max: 1120px" in css


def test_css_shadows_targets_focus_fonts() -> None:
    css = _css()
    for match in re.finditer(r"(?:box-shadow|--alg-shadow):\s*([^;]+);", css):
        value = match.group(1).strip()
        if value.startswith("var("):
            continue
        assert value in ALLOWED_SHADOWS, value
    assert f"--alg-target: {design.TARGET_PX}px" in css
    assert css.count("min-height: var(--alg-target)") >= 3
    assert ":focus-visible" in css and "outline: 2px solid var(--alg-accent-to)" in css
    assert "border-radius: 4px" not in css
    assert "@import" not in css and "url(" not in css, "no external font requests"
    assert "ui-sans-serif" in css and "JetBrains Mono" in css
    motion = re.search(r"--alg-motion: (\d+)ms ease-out;", css)
    assert motion and 150 <= int(motion.group(1)) <= 200, "motion is 150-200 ms ease-out"
    assert "transition: opacity var(--alg-motion);" in css
    assert "prefers-reduced-motion" in css


def _rule(css: str, selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r" \{\n(.*?)\n\}", css, re.S)
    assert match, selector
    decls = {}
    for line in match.group(1).splitlines():
        prop, _, value = line.strip().partition(":")
        decls[prop.strip()] = value.strip().rstrip(";")
    return decls


def test_primary_button_is_44px_pill_with_aa_contrast_and_keeps_its_radius_on_focus() -> None:
    css = _css()
    button = _rule(css, ".alg-button")
    assert button["min-height"] == "var(--alg-target)"
    assert button["border-radius"] == "var(--alg-radius-pill)"
    assert button["background"] == (
        "linear-gradient(135deg, var(--alg-button-from), var(--alg-button-to))"
    )
    assert button["color"] == design.BUTTON_TEXT
    assert button["box-shadow"] == "var(--alg-shadow)"
    for mode in (0, 1):
        start, end = (
            design.COLOR_TOKENS["button-from"][mode],
            design.COLOR_TOKENS["button-to"][mode],
        )
        for stop in (start, end, _midpoint(start, end)):
            assert _contrast(stop, design.BUTTON_TEXT) >= 4.5, stop
    # text links take the input radius on focus; the pill keeps the pill radius
    assert _rule(css, "a:focus-visible")["border-radius"] == "var(--alg-radius-input)"
    assert _rule(css, ".alg-button:focus-visible")["border-radius"] == "var(--alg-radius-pill)"
