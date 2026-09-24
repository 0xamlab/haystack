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
    # the brand gradient keeps the accent for the lane bar; it never carries text
    assert design.COLOR_TOKENS["accent-from"][mode] == "#7C5CFA"
    assert design.COLOR_TOKENS["accent-to"][mode] == "#3B82F6"
    assert "background-clip: text" not in fleet_css()


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_hero_accent_text_is_the_aa_accent_not_the_gradient(mode):
    """`.alg-hero-num.alg-accent-text` measured 4.12:1 light / 4.23:1 dark painted in
    #7C5CFA; it paints `accent-text` now — the selected tab's colour — at 4.5:1 or better on
    every surface a card sits on."""
    tokens = {name: values[mode] for name, values in design.COLOR_TOKENS.items()}
    accent = design.EXTENSION_TOKENS["accent-text"][mode]
    for surface in ("bg", "surface", "surface-2"):
        assert _contrast(accent, tokens[surface]) >= 4.5, (
            surface,
            _contrast(accent, tokens[surface]),
        )
    # the selected tab measured 6.5 light / 7.26 dark on `bg`; a card sits on `surface`
    assert _contrast(accent, tokens["bg"]) >= (6.4 if mode == 0 else 7.2)
    assert _contrast(accent, tokens["surface"]) >= (6.0 if mode == 0 else 6.8)
    assert design.ACCENT_TEXT == "color: var(--alg-accent-text, var(--alg-button-from));"
    assert f"{'.alg-accent-text' * 4} {{ {design.ACCENT_TEXT} }}" in design.BASE_CSS
    assert "#7C5CFA" not in design.ACCENT_TEXT and "accent-from" not in design.ACCENT_TEXT
    # the fallback outside the page root is the same light accent
    assert design.COLOR_TOKENS["button-from"][0] == design.EXTENSION_TOKENS["accent-text"][0]
    # one accent for the hero, the tabs and the code keywords
    settings = design.theme_settings()
    assert settings["color_accent"] == design.EXTENSION_TOKENS["accent-text"][0]
    assert (
        design.theme_dark_extras()["color_accent_dark"] == design.EXTENSION_TOKENS["accent-text"][1]
    )


def test_block_padding_sits_on_the_8pt_grid():
    settings = design.theme_settings()
    assert settings["block_padding"] == design.BLOCK_PADDING == "12px 16px"
    for value in design.BLOCK_PADDING.split():
        assert int(value[:-2]) in design.SPACING


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


# ------------------------------------------------ M2-B design system: states, steps, fonts


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_extension_tokens_hold_aa_on_every_surface_and_stay_page_scoped(mode):
    tokens = {name: values[mode] for name, values in design.COLOR_TOKENS.items()}
    accent = design.EXTENSION_TOKENS["accent-text"][mode]
    for surface in ("bg", "surface", "surface-2"):
        assert _contrast(accent, tokens[surface]) >= 4.5, (
            surface,
            _contrast(accent, tokens[surface]),
        )
    hover = design.EXTENSION_TOKENS["surface-hover"][mode]
    assert _contrast(tokens["text"], hover) >= 4.5
    # the disabled look: muted text on the muted surface, no opacity
    assert _contrast(tokens["text-2"], tokens["surface-2"]) >= 4.5
    css_text = design.TOKENS_CSS
    assert f"\n.{design.PAGE_CLASS} {{\n" in css_text
    assert f"\n.dark .{design.PAGE_CLASS} {{\n" in css_text
    assert "--alg-accent-text: #5B3FE0;" in css_text and "--alg-accent-text: #A78BFA;" in css_text
    # the two :root blocks stay the frozen set the redirect stubs mirror
    root = _block(":root")
    assert "--alg-accent-text" not in root and "Fallback" not in root
    assert len(re.findall(r"^:root \{\n", css_text, re.M)) == 2
    assert design.token("accent-text") == "var(--alg-accent-text)"


@pytest.mark.parametrize("mode", [0, 1], ids=["light", "dark"])
def test_button_hover_stops_hold_aa_with_white_text(mode):
    start, end = design.BUTTON_HOVER_STOPS[mode]
    for stop in (start, end, _midpoint(start, end)):
        assert _contrast(stop, design.BUTTON_TEXT) >= 4.5, (
            stop,
            _contrast(stop, design.BUTTON_TEXT),
        )
    assert design.button_hover_gradient(mode) == f"linear-gradient(135deg, {start} 0%, {end} 100%)"
    rest = design.COLOR_TOKENS["button-from"][mode]
    assert start != rest, "hover is a different fill from rest"


def test_theme_pins_every_button_tab_input_checkbox_and_label_state():
    s = design.theme_settings()
    # buttons: hover pinned to the design's own stops, secondary hover to surface-hover
    assert s["button_primary_background_fill_hover"] == design.button_hover_gradient(0)
    assert s["button_primary_background_fill_hover_dark"] == design.button_hover_gradient(1)
    assert (
        s["button_primary_text_color_hover"]
        == s["button_primary_text_color_hover_dark"]
        == "#FFFFFF"
    )
    assert s["button_secondary_background_fill_hover"] == "#E4E4EE"
    assert s["button_secondary_background_fill_hover_dark"] == "#1F1F2E"
    assert s["button_secondary_text_color_hover"] == "#0B0B12"
    assert s["button_secondary_text_color_hover_dark"] == "#E6E6EB"
    assert s["button_transform_hover"] == s["button_transform_active"] == "none"
    assert 150 <= design.MOTION_MS <= 200
    assert s["button_transition"].count(f"{design.MOTION_MS}ms") == 3
    # tabs: selected text is the accent shade that reads 4.5:1, hover fill is surface-2
    assert s["color_accent"] == "#5B3FE0"
    assert design.theme_dark_extras() == {"color_accent_dark": "#A78BFA"}
    assert s["background_fill_secondary"] == "#EEEEF5"
    assert s["background_fill_secondary_dark"] == "#181824"
    # focus: 2 px accent ring and accent border on inputs, both modes
    assert s["input_border_color_focus"] == s["input_border_color_focus_dark"] == "#3B82F6"
    assert s["input_shadow_focus"] == "0 0 0 2px #3B82F6"
    # checkbox and radio: unchecked = surface + visible border, checked = accent with AA check
    assert s["checkbox_background_color"] == "#F7F7FB"
    assert s["checkbox_background_color_dark"] == "#181824"
    assert s["checkbox_border_color_dark"] == "#9CA3AF"
    assert s["checkbox_border_width"] == "1px"
    assert s["checkbox_border_radius"] == "calc(8px / 2)"
    selected = s["checkbox_background_color_selected"]
    assert selected == s["checkbox_background_color_selected_dark"] == "#1D4ED8"
    assert _contrast("#FFFFFF", selected) >= 4.5
    # the block label (Code / Textbox) sits on surface-2 in text-2 in both modes
    assert (
        s["block_label_background_fill"] == "#EEEEF5" and s["block_label_text_color"] == "#5B6270"
    )
    assert s["block_label_background_fill_dark"] == "#181824"
    assert s["block_label_text_color_dark"] == "#9CA3AF"
    # 44 px through padding: inputs, option labels and buttons
    assert s["input_padding"] == "12px 16px"
    assert s["checkbox_label_padding"] == "12px 16px"
    assert s["button_large_padding"] == "12px 24px"
    # no Gradio palette reference survives anywhere in the theme
    for key, value in s.items():
        assert "*" not in value, key


def test_theme_factory_carries_the_dark_accent_and_the_fallback_faces():
    gr = pytest.importorskip("gradio")
    theme = design.theme()
    assert isinstance(theme, gr.themes.Base)
    assert theme.color_accent == "#5B3FE0" and theme.color_accent_dark == "#A78BFA"
    theme_css = theme._get_theme_css()
    light, dark = theme_css.split(":root.dark", 1)
    assert "--color-accent: #5B3FE0;" in light and "--color-accent: #A78BFA;" in dark
    assert "'Inter Fallback'" in theme.font and "'JetBrains Mono Fallback'" in theme.font_mono
    assert theme.font.index("'Inter'") < theme.font.index("'Inter Fallback'")


def test_phone_type_steps_and_fallback_font_faces_are_declared():
    css_text = design.TOKENS_CSS
    assert design.PHONE_MAX_WIDTH == 767
    assert f"@media (width <= {design.PHONE_MAX_WIDTH}px) {{\n  .{design.PAGE_CLASS} {{" in css_text
    assert design.TYPE_SCALE_PHONE == {"display": (28, 34), "title": (22, 28)}
    for decl in (
        "--alg-display-size: 28px;",
        "--alg-display-line: 34px;",
        "--alg-title-size: 22px;",
        "--alg-title-line: 28px;",
    ):
        assert decl in css_text
    assert css_text.count("--alg-display-size:") == 2  # the root value and the phone step
    faces = re.findall(r"@font-face \{\n(.*?)\n\}", css_text, re.S)
    assert len(faces) == len(design.FONT_FALLBACKS) == 2
    for face, fallback in zip(faces, design.FONT_FALLBACKS, strict=True):
        assert f'font-family: "{fallback.family}";' in face
        for name in fallback.local:
            assert f'local("{name}")' in face
        for prop in ("size-adjust", "ascent-override", "descent-override", "line-gap-override"):
            assert f"  {prop}: " in face
        assert "url(" not in face  # local faces only: nothing is downloaded
    # the page stacks name the fallback right after the web font; the frozen :root stacks stay
    assert design.FONT_SANS_PAGE.startswith('Inter, "Inter Fallback", ')
    assert design.FONT_MONO_PAGE.startswith('"JetBrains Mono", "JetBrains Mono Fallback", ')
    assert css_text.count(f"--alg-font: {design.FONT_SANS};") == 1
    assert css_text.count(f"--alg-font: {design.FONT_SANS_PAGE};") == 1
    assert css_text.count(f"--alg-font-mono: {design.FONT_MONO_PAGE};") == 1
    assert "Fallback" not in design.FONT_SANS and "Fallback" not in design.FONT_MONO


def test_base_css_ships_the_chrome_and_code_sheets():
    assert css.CHROME_CSS.strip() in design.BASE_CSS
    assert css.CODE_CSS.strip() in design.BASE_CSS
    bundle = fleet_css()
    assert '[data-testid="status-tracker"] { display: none; }' in bundle
    assert bundle.index(design.TOKENS_CSS) < bundle.index(css.CHROME_CSS.strip())
