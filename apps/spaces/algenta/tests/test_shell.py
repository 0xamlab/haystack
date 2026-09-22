"""Shell smoke tests — the Gradio 6 presentation layer of the flagship.

Pins the contract that keeps the shell unbreakable across Gradio upgrades:
the theme carries the palette (base AND `_dark` variants pinned to the same
dark values, so the OS auto-flip is a no-op), the shell CSS stays within its
≤40-line budget and touches only our own elem_classes hooks, no stylesheet
anywhere selects Gradio component internals, and the Blocks tree builds with
fill_width, all six product tabs (plus the three LLM-module subtabs) and the
full event/API surface.
"""

from __future__ import annotations

import os
import sys

import gradio as gr

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402
import design  # noqa: E402

# Selectors/patterns that couple CSS to Gradio internals — the failure mode
# that broke the previous shell when Gradio 6 rewrote the frontend.
_GRADIO_INTERNALS = (".gradio-container", ".gr-", ".tab-nav", ".tabitem", ".prose", ".svelte-")
_FORBIDDEN_TECHNIQUES = ("!important", "max-width")


def test_theme_is_glass_with_pinned_dark_palette():
    theme = design.THEME
    assert isinstance(theme, gr.themes.Glass)
    pinned_pairs = [
        "body_background_fill",
        "body_text_color",
        "body_text_color_subdued",
        "block_background_fill",
        "block_border_width",
        "border_color_primary",
        "input_background_fill",
        "input_border_color",
        "block_label_text_color",
        "block_title_text_color",
        "button_primary_background_fill",
        "button_primary_background_fill_hover",
        "button_primary_text_color",
        "button_primary_border_color",
        "button_secondary_background_fill",
        "button_secondary_background_fill_hover",
        "button_secondary_text_color",
        "button_secondary_border_color",
    ]
    for token in pinned_pairs:
        base = getattr(theme, token)
        dark = getattr(theme, f"{token}_dark")
        assert base is not None and base == dark, f"{token} not pinned identically for dark"
    assert theme.body_background_fill == "#0A0A0F"
    assert theme.block_background_fill == "#12121A"
    assert theme.input_background_fill == "#181824"
    assert theme.body_text_color == "#E6E6EB"
    assert theme.body_text_color_subdued == "#9CA3AF"
    assert theme.block_title_text_weight == "600"
    assert "linear-gradient" in theme.button_primary_background_fill
    assert "#7C5CFA" in theme.button_primary_background_fill
    assert "#3B82F6" in theme.button_primary_background_fill


def test_shell_css_budget_and_hooks_only():
    lines = [line for line in design.CSS.strip().splitlines() if line.strip()]
    assert len(lines) <= 40, f"shell CSS grew to {len(lines)} lines (budget 40)"
    for bad in (*_GRADIO_INTERNALS, *_FORBIDDEN_TECHNIQUES):
        assert bad not in design.CSS, f"shell CSS couples to {bad!r}"
    # every selector is rooted at one of our elem_classes hooks
    for hook in ("alg-hero", "alg-section", "alg-footer", "alg-duel", "alg-gov"):
        assert f".{hook}" in design.CSS, f"elem_classes hook .{hook} missing from shell CSS"


def test_component_css_payloads_only():
    for bad in (*_GRADIO_INTERNALS, *_FORBIDDEN_TECHNIQUES):
        assert bad not in design.COMPONENT_CSS, f"component CSS couples to {bad!r}"
    # the arena card markup classes must be styled (card.py is frozen)
    for cls in ("duel-card", "lane-bar", "hero-num", "chip", "card-reason"):
        assert f".{cls}" in design.COMPONENT_CSS


def test_app_builds_with_fill_width_and_all_tabs():
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    demo = app.build_app()
    assert demo.fill_width is True
    tabs = [b for b in demo.blocks.values() if isinstance(b, gr.Tab)]
    labels = [t.label for t in tabs]
    for wanted in [*app.TAB_LABELS, "Tokenize", "Mini-KB retrieval", "Attention lab"]:
        assert wanted in labels, f"tab {wanted!r} missing"


def test_event_and_api_surface_complete():
    demo = app.build_app()
    cfg = demo.get_config_file()  # builds without component errors
    api_names = {d.get("api_name") for d in cfg["dependencies"] if d.get("api_name")}
    for name in (
        "run_duel",
        "tokenize",
        "retrieve",
        "attention",
        "gov_log_decision",
        "gov_execute_decision",
        "mcp_filter",
    ):
        assert name in api_names, f"API endpoint {name!r} missing"


def test_no_emoji_in_ui_chrome():
    # zero emoji in component labels/values (share_text's ⚡ is user content, not chrome)
    demo = app.build_app()
    emoji = ("⚡", "✅", "❌", "🚀", "🔥", "✨", "📊", "🎯")
    for block in demo.blocks.values():
        label = getattr(block, "label", None)
        if isinstance(label, str):
            assert not any(e in label for e in emoji), label
    for wanted in app.TAB_LABELS:
        assert not any(e in wanted for e in emoji)
