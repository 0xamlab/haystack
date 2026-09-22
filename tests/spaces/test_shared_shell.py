"""algenta_spaces.shell — header, footer, nav, copy rules, stylesheet discipline."""

from __future__ import annotations

import re

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import design, shell

REQUIRED_LINKS = {
    "https://huggingface.co/spaces/thyn-ai/algenta",
    "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena",
    "https://huggingface.co/spaces/thyn-ai/algenta-governed-agent",
    "https://huggingface.co/thyn-ai",
    "https://github.com/thyn-ai/mojo-kernels",
    "https://docs.algenta.ai",
    "https://algenta.ai/pricing",
    "https://discord.gg/w8NDsph9an",
}


def test_nav_is_exactly_the_eight_fleet_links():
    assert [label for label, _ in shell.NAV] == [
        "Flagship",
        "Speed Arena",
        "Governed Agent",
        "Kernels Hub",
        "GitHub",
        "Docs",
        "Pricing",
        "Discord",
    ]
    assert {url for _, url in shell.NAV} == REQUIRED_LINKS


def test_header_renders_every_link_the_eyebrow_and_the_duplicate_link():
    html = shell.render_header(
        "Compiled kernels, live",
        "Race them against Python",
        [("measured here", "ok"), "Hub kernels"],
        active="Flagship",
        space_id="thyn-ai/algenta",
    )
    for url in REQUIRED_LINKS - {"https://huggingface.co/spaces/thyn-ai/algenta"}:
        assert f'href="{url}"' in html
    # the active Space is text, not a link
    assert 'href="https://huggingface.co/spaces/thyn-ai/algenta"' not in html
    assert '<span class="alg-shell-nav-active" aria-current="page">Flagship</span>' in html
    assert shell.EYEBROW in html
    assert "compiler-driven, self-hosted AI infrastructure" in html
    assert 'href="https://huggingface.co/spaces/thyn-ai/algenta?duplicate=true"' in html
    assert "Duplicate this Space" in html
    assert "alg-shell-badge-ok" in html
    _assert_clean_copy(html)


def test_header_without_space_id_omits_duplicate_link(monkeypatch):
    monkeypatch.delenv("SPACE_ID", raising=False)
    html = shell.render_header("Speed Arena", "Mojo drop-ins against the Python libraries")
    assert "duplicate=true" not in html
    monkeypatch.setenv("SPACE_ID", "thyn-ai/algenta-speed-arena")
    html = shell.render_header("Speed Arena", "Mojo drop-ins against the Python libraries")
    assert "thyn-ai/algenta-speed-arena?duplicate=true" in html


def test_header_escapes_user_text():
    html = shell.render_header("<b>Kernels</b>", 'Race "them" & win', ["<i>x</i>"])
    assert "<b>" not in html
    assert "&lt;b&gt;Kernels&lt;/b&gt;" in html
    assert "&quot;them&quot; &amp; win" in html
    assert "&lt;i&gt;x&lt;/i&gt;" in html


@pytest.mark.parametrize(
    ("title", "tagline"),
    [
        ("One two three four five six seven", "fine"),
        ("Fine", " ".join(["word"] * 15)),
        ("Fast kernels!", "fine"),
        ("Fine", "the decision engine is here"),
        ("Fine", "measured inside the cgroup"),
        ("Fine", "R7 configs printed"),
        ("Fine", "\U0001f680 launch"),
        ("", "fine"),
    ],
)
def test_header_rejects_copy_that_breaks_the_rules(title, tagline):
    with pytest.raises(ValueError):
        shell.render_header(title, tagline)


def test_header_rejects_unknown_active_and_badge_variant():
    with pytest.raises(ValueError):
        shell.render_header("Fine", "fine", active="LLM Agents lab")
    with pytest.raises(ValueError):
        shell.render_header("Fine", "fine", [("x", "danger")])


def test_footer_has_canon_licence_links_and_stamp(tmp_path):
    html = shell.render_footer(stamp="abc1234def")
    assert shell.CANON in html
    assert shell.LICENCE_LINE in html
    assert "Algenta Community License 1.1" in html
    assert "algenta.ai/pricing" in html
    for url in REQUIRED_LINKS:
        assert f'href="{url}"' in html
    assert "build abc1234def" in html
    assert "@" not in html  # never an email
    _assert_clean_copy(html)


def test_footer_stamp_reads_shared_sha_file_or_dev(tmp_path):
    missing = tmp_path / ".shared_sha"
    assert shell.shared_sha(missing) == "dev"
    missing.write_text("not a sha\n")
    assert shell.shared_sha(missing) == "dev"
    missing.write_text("0123ABCDEF0123456789abcdef0123456789abcd\n")
    assert shell.shared_sha(missing) == "0123abcdef0123456789abcdef0123456789abcd"
    # the default location is next to the package; no stamp there in the repo
    assert shell.shared_sha() == "dev"


def test_footer_active_label_is_text_and_unknown_raises():
    html = shell.render_footer(active="Docs", stamp="dev")
    assert 'href="https://docs.algenta.ai"' not in html
    assert "alg-shell-footer-active" in html
    with pytest.raises(ValueError):
        shell.render_footer(active="SDK", stamp="dev")


def test_duplicate_url_validates_space_id():
    assert (
        shell.duplicate_url("thyn-ai/algenta")
        == "https://huggingface.co/spaces/thyn-ai/algenta?duplicate=true"
    )
    for bad in ("algenta", "thyn-ai/", "/algenta", "a b/c", "thyn-ai/algenta/x"):
        with pytest.raises(ValueError):
            shell.duplicate_url(bad)


def test_check_copy_and_detectors():
    assert shell.check_copy("Compiled kernels, live", max_words=6) == "Compiled kernels, live"
    assert shell.banned_phrase("a Decision Engine") == "Decision Engine"
    assert shell.banned_phrase("bit-faithful") == "bit-faithful"
    assert shell.banned_phrase("write to sales@algenta.ai") == "@algenta.ai"
    assert shell.banned_phrase("R4X is a part number") is None
    assert shell.banned_phrase("exact match") is None
    assert shell.has_emoji("ok ✅")
    assert not shell.has_emoji("ratio 3.2× · P95 — fine")


def test_shell_css_discipline():
    css = shell.SHELL_CSS
    _assert_stylesheet_discipline(css)
    _assert_four_class_selectors(css)
    assert "var(--alg-" in css
    assert "#" not in css.replace("#", "", 0)  # colours come from tokens only


# --------------------------------------------------------------- interactive targets

INTERACTIVE = (
    "alg-shell-nav-link",
    "alg-shell-nav-active",
    "alg-shell-nav-dup",
    "alg-shell-footer-link",
    "alg-shell-footer-active",
)
_RULE_RE = re.compile(r"^((?:\.[\w-]+)+)((?::[\w-]+)*) \{ (.*) \}$")
_TOKEN_RE = re.compile(r"--(alg-[\w-]+): ([^;]+);")
_VAR_RE = re.compile(r"var\(--(alg-[\w-]+)\)")


def _rules(css: str) -> dict[tuple[str, str], dict[str, str]]:
    """{(class, pseudo): {property: value}} for every single-line rule in a stylesheet."""
    out: dict[tuple[str, str], dict[str, str]] = {}
    for line in css.splitlines():
        m = _RULE_RE.match(line.strip())
        if not m:
            continue
        cls = m.group(1).split(".")[1]
        decls = out.setdefault((cls, m.group(2)), {})
        for decl in m.group(3).split(";"):
            if decl.strip():
                prop, _, value = decl.partition(":")
                decls[prop.strip()] = value.strip()
    return out


def _px(value: str, tokens: dict[str, str]) -> float:
    """A CSS length in px, resolving `var(--alg-*)` through the token set."""
    value = _VAR_RE.sub(lambda m: tokens[m.group(1)], value).strip()
    assert value.endswith("px"), value
    return float(value[:-2])


def _vertical_padding(shorthand: str, tokens: dict[str, str]) -> float:
    parts = shorthand.split()
    assert 1 <= len(parts) <= 4, shorthand
    top = _px(parts[0], tokens)
    bottom = _px(parts[2], tokens) if len(parts) >= 3 else top
    return top + bottom


def test_every_interactive_target_is_at_least_44px_tall():
    tokens = dict(_TOKEN_RE.findall(design.TOKENS_CSS))
    rules = _rules(shell.SHELL_CSS)
    for cls in INTERACTIVE:
        decls = rules[(cls, "")]
        if "min-height" in decls:
            height = _px(decls["min-height"], tokens)
        else:
            assert "line-height" in decls, f"{cls} declares neither line-height nor min-height"
            height = _px(decls["line-height"], tokens) + _vertical_padding(
                decls.get("padding", "0"), tokens
            )
        assert height >= design.TARGET_PX, f"{cls} is {height}px tall"


def test_focus_rings_follow_the_element_radius():
    css = shell.SHELL_CSS
    assert not re.search(r"border-radius:\s*4px", css), "no 4px radius anywhere"
    rules = _rules(css)
    for cls in ("alg-shell-nav-link", "alg-shell-footer-link"):
        focus = rules[(cls, ":focus-visible")]
        assert focus["outline"] == "2px solid var(--alg-accent-to)"
        assert focus["border-radius"] == "var(--alg-radius-input)"
    pill, pill_focus = (
        rules[("alg-shell-nav-dup", "")],
        rules[("alg-shell-nav-dup", ":focus-visible")],
    )
    assert pill["border-radius"] == "var(--alg-radius-pill)"
    assert pill_focus["outline"] == "2px solid var(--alg-accent-to)"
    assert pill_focus["border-radius"] == pill["border-radius"], (
        "the pill keeps its radius on focus"
    )
