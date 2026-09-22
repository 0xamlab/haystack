"""algenta_spaces.design — one token set, light and dark, scale, theme factory."""

from __future__ import annotations

import inspect
import re

import pytest
from _rules import _assert_four_class_selectors, _assert_stylesheet_discipline, _contrast, _midpoint
from algenta_spaces import css, design, fleet_css

PLAN_DARK = {
    "bg": "#0A0A0F",
    "surface": "#12121A",
    "surface-2": "#181824",
    "text": "#E6E6EB",
    "text-2": "#9CA3AF",
    "hairline": "rgba(255,255,255,.08)",
    "accent-from": "#7C5CFA",
    "accent-to": "#3B82F6",
    "ok": "#34D399",
    "warn": "#FBBF24",
    "err": "#F87171",
    "inc": "#475069",
}
PLAN_LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#F7F7FB",
    "surface-2": "#EEEEF5",
    "text": "#0B0B12",
    "text-2": "#5B6270",
    "hairline": "rgba(0,0,0,.08)",
    "inc": "#334155",
}


def _block(selector: str) -> str:
    match = re.search(re.escape(selector) + r" \{\n(.*?)\n\}", design.TOKENS_CSS, re.S)
    assert match, selector
    return match.group(1)


def test_dark_values_are_the_brand_values_and_light_surfaces_match_the_plan():
    for name, value in PLAN_DARK.items():
        assert design.COLOR_TOKENS[name][1] == value, name
    for name, value in PLAN_LIGHT.items():
        assert design.COLOR_TOKENS[name][0] == value, name


def test_every_color_token_is_declared_in_root_and_dark_blocks():
    root, dark = _block(":root"), _block(".dark")
    for name, (light, dark_value) in design.COLOR_TOKENS.items():
        assert f"--alg-{name}: {light};" in root
        assert f"--alg-{name}: {dark_value};" in dark
    assert design.TOKENS_CSS.count("--alg-bg:") == 2


def test_scale_tokens_fonts_and_type_scale_are_declared_once():
    assert design.SPACING == (4, 8, 12, 16, 24, 32, 48, 64)
    for value in design.SPACING:
        assert design.TOKENS_CSS.count(f"--alg-space-{value}: {value}px;") == 1
    assert "--alg-radius-card: 12px;" in design.TOKENS_CSS
    assert "--alg-radius-input: 8px;" in design.TOKENS_CSS
    assert "--alg-radius-pill: 999px;" in design.TOKENS_CSS
    assert design.TARGET_PX == 44
    assert design.TOKENS_CSS.count("--alg-target: 44px;") == 1
    assert design.TOKENS_CSS.count("--alg-shadow: 0 1px 2px rgba(0,0,0,.06);") == 1
    assert "--alg-display-size: 40px;" in design.TOKENS_CSS
    assert "--alg-display-line: 48px;" in design.TOKENS_CSS
    assert "--alg-display-tracking: -0.02em;" in design.TOKENS_CSS
    assert "--alg-display-weight: 600;" in design.TOKENS_CSS
    assert "--alg-title-size: 28px;" in design.TOKENS_CSS
    assert "--alg-title-line: 34px;" in design.TOKENS_CSS
    assert "--alg-body-size: 15px;" in design.TOKENS_CSS
    assert "--alg-body-line: 22px;" in design.TOKENS_CSS
    assert "--alg-caption-size: 12px;" in design.TOKENS_CSS
    assert "--alg-caption-line: 16px;" in design.TOKENS_CSS
    assert "--alg-mono-size: 13px;" in design.TOKENS_CSS
    assert "--alg-mono-line: 20px;" in design.TOKENS_CSS
    assert "Inter" in design.FONT_SANS and "JetBrains Mono" in design.FONT_MONO
    assert "tabular-nums" in design.BASE_CSS


def test_no_force_dark_script_anywhere():
    for name in dir(design):
        assert "FORCE" not in name and "JS" not in name
    assert "classList.add('dark')" not in fleet_css()


def test_spacing_values_in_every_stylesheet_are_on_the_scale():
    bundle = fleet_css()
    _assert_stylesheet_discipline(bundle)
    for sheet in (design.BASE_CSS,):
        _assert_four_class_selectors(sheet)
    assert bundle.startswith(":root {")


def test_token_helper():
    assert design.token("ok") == "var(--alg-ok)"
    with pytest.raises(KeyError):
        design.token("missing")


def test_css_rule_builder_enforces_the_discipline():
    assert css.rule("alg-x", "margin: 0;") == ".alg-x.alg-x.alg-x.alg-x { margin: 0; }"
    assert css.rule("alg-x", " color:  red; ", suffix=":hover") == (
        ".alg-x.alg-x.alg-x.alg-x:hover { color: red; }"
    )
    with pytest.raises(ValueError):
        css.rule("alg-x", "color: red !important;")
    with pytest.raises(ValueError):
        css.rule(".alg-x", "color: red;")
    wrapped = css.block("@media (width <= 560px)", css.rule("alg-y", "flex-basis: 96px;"))
    assert wrapped.startswith("@media (width <= 560px) {\n  .alg-y")
    assert css.stylesheet("a", "b") == "a\nb\n"


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_text_and_status_colours_meet_wcag_aa_on_their_surfaces(mode):
    tokens = {name: values[mode] for name, values in design.COLOR_TOKENS.items()}
    assert _contrast(tokens["text"], tokens["bg"]) >= 4.5
    assert _contrast(tokens["text"], tokens["surface"]) >= 4.5
    assert _contrast(tokens["text-2"], tokens["surface"]) >= 4.5
    for status in ("ok", "warn", "err"):
        assert _contrast(tokens[status], tokens["surface-2"]) >= 4.5, status
        assert _contrast(tokens[status], tokens["surface"]) >= 4.5, status


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_primary_button_gradient_holds_aa_contrast_with_white_text(mode):
    """The button has its own stops: the decorative accent (#3B82F6 on white is 3.7:1) never
    sits under text. Both ends and the 50% midpoint of the gradient clear 4.5:1."""
    start, end = design.COLOR_TOKENS["button-from"][mode], design.COLOR_TOKENS["button-to"][mode]
    assert design.BUTTON_TEXT == "#FFFFFF"
    for stop in (start, end, _midpoint(start, end)):
        assert _contrast(stop, design.BUTTON_TEXT) >= 4.5, (
            stop,
            _contrast(stop, design.BUTTON_TEXT),
        )
    fill = design.button_gradient(mode)
    assert fill == f"linear-gradient(135deg, {start} 0%, {end} 100%)"
    settings = design.theme_settings()
    key = "button_primary_background_fill" + ("_dark" if mode else "")
    assert settings[key] == fill
    assert settings["button_primary_text_color" + ("_dark" if mode else "")] == design.BUTTON_TEXT
    # the header gradient keeps the brand accent; it is decorative and carries no text
    assert design.COLOR_TOKENS["accent-from"][mode] == "#7C5CFA"
    assert design.COLOR_TOKENS["accent-to"][mode] == "#3B82F6"
    assert "--alg-accent-from" in design._GRADIENT_TEXT and "button" not in design._GRADIENT_TEXT


def test_theme_settings_pin_both_modes_to_the_tokens():
    settings = design.theme_settings()
    assert settings["body_background_fill"] == "#FFFFFF"
    assert settings["body_background_fill_dark"] == "#0A0A0F"
    assert settings["body_text_color_subdued"] == "#5B6270"
    assert settings["body_text_color_subdued_dark"] == "#9CA3AF"
    assert "#5B3FE0" in settings["button_primary_background_fill"]
    assert "#1D4ED8" in settings["button_primary_background_fill_dark"]
    assert "#7C5CFA" not in settings["button_primary_background_fill"]
    assert settings["block_radius"] == "12px"
    for key in list(settings):
        if key.endswith("_dark"):
            assert key[: -len("_dark")] in settings, key


def test_theme_factory_builds_a_gradio_theme():
    gr = pytest.importorskip("gradio")
    theme = design.theme()
    assert isinstance(theme, gr.themes.Base)
    assert theme.body_background_fill_dark == "#0A0A0F"


# ------------------------------------------------------------------------ shadows

_SHADOW_PX_RE = re.compile(r"(-?\d+(?:\.\d+)?)px")
_ALPHA_RE = re.compile(r"rgba\([^)]*,\s*(\d*\.?\d+)\)")


def _assert_no_heavier_than_the_token(key: str, value: str) -> None:
    """`none`, or every offset/blur/spread length <= 2px and every rgba alpha <= .06."""
    if value == "none":
        return
    lengths = [float(n) for n in _SHADOW_PX_RE.findall(value)]
    assert lengths, f"{key}={value!r} is neither none nor a length-bearing shadow"
    assert all(abs(n) <= 2 for n in lengths), f"{key}={value!r} is heavier than {design.SHADOW}"
    for alpha in _ALPHA_RE.findall(value):
        assert float(alpha) <= 0.06, f"{key}={value!r} is darker than {design.SHADOW}"


def test_theme_settings_pin_every_gradio_shadow_variable():
    settings = design.theme_settings()
    assert len(set(design.SHADOW_KEYS)) == len(design.SHADOW_KEYS)
    for key in design.SHADOW_KEYS:
        assert key in settings, f"{key} left to Gradio's default"
        _assert_no_heavier_than_the_token(key, settings[key])
    for key in design.SHADOW_KEYS_DROP:
        assert settings[key] == design.SHADOW
    for key in design.SHADOW_KEYS_NONE:
        assert settings[key] == "none"
    # the input focus ring is the same 2 px accent ring the shell draws with `outline`
    assert settings["input_shadow_focus"] == "0 0 0 2px #3B82F6"
    assert settings["input_shadow_focus_dark"] == "0 0 0 2px #3B82F6"
    assert settings["shadow_spread"] == settings["shadow_spread_dark"] == "2px"
    # nothing else in the theme carries a shadow the key list does not know about
    for key, value in settings.items():
        if "shadow" in key:
            assert key in design.SHADOW_KEYS, key
            _assert_no_heavier_than_the_token(key, value)


def test_shadow_key_list_matches_the_installed_gradio_theme_api():
    gr = pytest.importorskip("gradio")
    params = inspect.signature(gr.themes.Base.set).parameters
    exposed = {name for name in params if "shadow" in name}
    assert exposed == set(design.SHADOW_KEYS), exposed ^ set(design.SHADOW_KEYS)
    glass = gr.themes.Glass().set(**design.theme_settings())
    assert glass.shadow_inset == "none"
    assert glass.button_primary_shadow_active == "none"
    assert glass.block_shadow == design.SHADOW


def test_heaviness_parser_rejects_gradios_own_defaults():
    with pytest.raises(AssertionError):
        _assert_no_heavier_than_the_token("shadow_inset", "rgba(0,0,0,0.05) 0px 2px 4px 0px inset")
    with pytest.raises(AssertionError):
        _assert_no_heavier_than_the_token("shadow_drop_lg", "0 1px 2px rgba(0,0,0,.2)")
    with pytest.raises(AssertionError):
        _assert_no_heavier_than_the_token("shadow_drop", "")
    _assert_no_heavier_than_the_token("shadow_drop", design.SHADOW)
