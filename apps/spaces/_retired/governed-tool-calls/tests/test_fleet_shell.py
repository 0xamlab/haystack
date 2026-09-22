"""Fleet shell contract tests — shell.py is copied verbatim into every Space.

These tests are stdlib-only on purpose: they pin the canonical chrome
(eyebrow, H1, tagline, badge pills, sister-nav, footer) and the SHELL_CSS
rules (alg-shell-* classes only, no Gradio selectors, no !important) without
importing gradio, so they run in any interpreter. If shell.py changes, it
must change in all six Spaces at once — this file is the guard.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shell  # noqa: E402

NAV_LABELS = [
    "Speed Arena",
    "LLM Agents lab",
    "LLM modules live",
    "Governed tool calls",
    "Governed agent",
    "kernels",
    "SDK",
]
NAV_URLS = {
    "Speed Arena": "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena",
    "LLM Agents lab": "https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents",
    "LLM modules live": "https://huggingface.co/spaces/thyn-ai/algenta-llm-modules",
    "Governed tool calls": "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls",
    "Governed agent": "https://huggingface.co/spaces/thyn-ai/algenta-governed-agent",
    "kernels": "https://github.com/thyn-ai/mojo-kernels",
    "SDK": "https://github.com/thyn-ai/algenta-sdk",
}


def test_header_renders_eyebrow_title_tagline_in_order():
    html = shell.render_header("Algenta", "the tagline")
    eyebrow = html.index('alg-shell-eyebrow">ALGENTA<')
    title = html.index('alg-shell-title">Algenta<')
    tagline = html.index('alg-shell-tagline">the tagline<')
    assert eyebrow < title < tagline


def test_header_badges_render_through_one_pill_component():
    html = shell.render_header(
        "t", "x", badges=[("live claim", "ok"), "neutral", ("qualified claim", "warn")]
    )
    assert '<span class="alg-shell-badge alg-shell-badge-ok">live claim</span>' in html
    assert '<span class="alg-shell-badge">neutral</span>' in html
    assert '<span class="alg-shell-badge alg-shell-badge-warn">qualified claim</span>' in html


def test_header_without_badges_has_no_badge_row():
    assert "alg-shell-badges" not in shell.render_header("t", "x")


def test_sister_nav_is_the_canonical_seven_in_order():
    html = shell.render_header("t", "x")
    pos = -1
    for label in NAV_LABELS:
        new_pos = html.index(f">{label}<")
        assert new_pos > pos, f"{label} out of order"
        pos = new_pos
    for label, url in NAV_URLS.items():
        assert f'<a class="alg-shell-nav-link" href="{url}">{label}</a>' in html
    assert '<span class="alg-shell-attribution">attribution: Algenta</span>' in html


def test_active_entry_is_dimmed_text_not_a_link():
    html = shell.render_header("t", "x", active="LLM Agents lab")
    assert '<span class="alg-shell-nav-active">LLM Agents lab</span>' in html
    assert f'href="{NAV_URLS["LLM Agents lab"]}"' not in html
    # every other entry stays a link
    for label, url in NAV_URLS.items():
        if label != "LLM Agents lab":
            assert f'href="{url}"' in html


def test_active_must_be_a_nav_label():
    with pytest.raises(ValueError, match="SISTER_NAV"):
        shell.render_header("t", "x", active="not a space")


def test_badge_variant_validation():
    with pytest.raises(ValueError, match="variant"):
        shell.render_header("t", "x", badges=[("b", "bogus")])


def test_user_text_is_escaped():
    html = shell.render_header('<script>"x"</script>', "<b>bold</b>", badges=["<i>x</i>"])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "&lt;i&gt;x&lt;/i&gt;" in html


def test_footer_is_fixed_and_complete():
    html = shell.render_footer()
    assert "alg-shell-footer" in html
    assert '<span class="alg-shell-footer-brand">Algenta</span>' in html
    for label, url in [
        ("algenta.ai", "https://algenta.ai"),
        ("docs.algenta.ai", "https://docs.algenta.ai"),
        ("github.com/thyn-ai", "https://github.com/thyn-ai"),
        ("Hugging Face", "https://huggingface.co/thyn-ai"),
    ]:
        assert f'<a class="alg-shell-footer-link" href="{url}">{label}</a>' in html


def _unchained(selector: str) -> str:
    """Collapse the 4x specificity chain (.x.x.x.x -> .x) for readability checks."""
    return re.sub(r"(\.alg-shell-[a-z-]+)(?:\1)+", r"\1", selector)


def test_shell_css_only_styles_alg_shell_classes():
    selectors = re.findall(r"([^{}]+)\{", shell.SHELL_CSS)
    for sel in selectors:
        for token in sel.split():
            if token.startswith("."):
                assert token.startswith(".alg-shell-"), f"foreign selector {token!r}"
    for bad in ("!important", ".gradio-container", ".gr-", ".prose", ".svelte-", "max-width"):
        assert bad not in shell.SHELL_CSS, f"SHELL_CSS couples to {bad!r}"


def test_every_selector_carries_the_4x_specificity_chain():
    # Gradio 6 scopes resets/prose under .gradio-container-<version> (up to
    # (0,3,1)); the 4x class chain (0,4,0) is what lets these payload rules
    # win on every frontend without !important. Pin the contract.
    selectors = [s for s in re.findall(r"([^{}]+)\{", shell.SHELL_CSS) if s.strip()]
    assert selectors, "SHELL_CSS is empty"
    for sel in selectors:
        last = sel.split()[-1].replace(":hover", "")
        m = re.search(r"(\.alg-shell-[a-z-]+)$", last)
        assert m, f"selector {sel!r} does not end in an alg-shell class"
        cls = m.group(1)
        assert last.count(cls) >= 4, f"selector {sel!r} lost the 4x chain"


def test_shell_css_layout_metrics_are_the_fleet_contract():
    css = _unchained(shell.SHELL_CSS)
    assert ".alg-shell-header { padding: 28px 0 12px; }" in css
    assert re.search(r"\.alg-shell-nav \{[^}]*margin: 12px 0 0;", css)
    assert re.search(r"\.alg-shell-footer \{[^}]*margin-top: 40px; padding-top: 16px;", css)
    # theme colors come from var() tokens, not hardcoded hex
    assert "color: var(--body-text-color);" in css
    assert "color: var(--body-text-color-subdued);" in css
    assert "border-top: 1px solid var(--border-color-primary);" in css
