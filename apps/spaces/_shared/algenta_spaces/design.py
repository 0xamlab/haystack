"""One token set for the three Spaces, as CSS custom properties with light and dark values.

Lifted from `apps/spaces/algenta/design.py` (Glass base theme, Inter + JetBrains
Mono, the purple-to-blue accent, `elem_classes`-only shell CSS) and reduced to a
single source of truth: every colour is a `--alg-*` custom property declared
once for light (`:root`) and once for dark (`.dark`, the class Gradio toggles
with the system preference). There is no force-dark script; both modes are
first-class.

Light-mode status colours are darker than their dark-mode partners so chip
text keeps a contrast ratio of at least 4.5:1 on the light surfaces
(#34D399 on white is about 1.9:1). The dark values are the brand values.

The primary button carries its own gradient stops (`button-from`, `button-to`):
the brand accent #7C5CFA -> #3B82F6 is decorative only (the algenta lane bar),
because white text on #3B82F6 is 3.7:1 and #7C5CFA on `surface` is 4.1:1. The
button stops hold at least 4.5:1 against white at both ends and at the
midpoint, in both modes; the hover gradient (`BUTTON_HOVER_STOPS`, darker in
light mode, lighter in dark mode) holds the same bound. Every button state
Gradio exposes (rest, hover, focus, disabled; primary and secondary) is pinned
in `theme_settings()`; the disabled look is a muted surface with muted text,
drawn by `css.CHROME_CSS`, never an opacity trick.

Page-scoped extension tokens
----------------------------
`accent-text` is the one accent that carries text: the hero figure
(`alg-accent-text`), the selected tab (`color_accent`), links and code
keywords all paint it — #5B3FE0 (6.5:1 on the light surface) and #A78BFA
(7.3:1 on the dark one), never the decorative gradient, which measured 4.12:1
light and 4.23:1 dark on the 40 px hero. `surface-hover` is the
secondary-button, option and tab hover fill. Both are declared on `.alg-page`
and `.dark .alg-page` rather than on `:root`: the redirect stubs freeze the
`:root` token set and are compared against it in the test suite, so extensions
live on the page root every Space already wraps its content in
(`css.PAGE_CLASS`); the accent gradient carries text in one place only, the header's
count numeral (`shell` `alg-shell-count`, 64 px / 48 px on the phone: WCAG large text, both
stops ≥ 3:1 on both page backgrounds); `alg-accent-text` falls back to `button-from` (the same
#5B3FE0) outside the page root. The same block re-declares `--alg-font` and
`--alg-font-mono` with the metric-matched fallback faces (`FONT_FALLBACKS`,
emitted as `@font-face`), so the web-font swap moves nothing: the fallback is
the visitor's local Arial or Courier New scaled to Inter's and JetBrains
Mono's advance widths and vertical metrics.

Block padding: Gradio's default is `10px 12px`; the theme pins `BLOCK_PADDING`
(`12px 16px`) so every bordered block — number and text inputs, the permalink
box, code blocks — sits on the 8-pt grid. Accordions (`alg-disclosure`) drop
the vertical padding altogether in `css.CHROME_CSS`, so their header is one
44 px row.

Type steps: below `PHONE_MAX_WIDTH` the display role steps 40/48 -> 28/34 and
the title role 28/34 -> 22/28 (`TYPE_SCALE_PHONE`), so a headline that fits on
one line at 1440 px takes two lines on a phone, not three.

Shadows: `SHADOW` is the heaviest drop shadow the fleet draws; every Gradio
shadow variable is pinned to it, to `none`, or (focus rings) to a 2 px
zero-blur ring in the accent colour.

`theme()` builds the Gradio theme lazily so this module imports without gradio.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

from .css import CHROME_CSS, CODE_CSS, LAYOUT_CSS, PAGE_CLASS, PHONE_MAX_WIDTH, rule, stylesheet

# name -> (light, dark)
COLOR_TOKENS: Mapping[str, tuple[str, str]] = {
    "bg": ("#FFFFFF", "#0A0A0F"),
    "surface": ("#F7F7FB", "#12121A"),
    "surface-2": ("#EEEEF5", "#181824"),
    "text": ("#0B0B12", "#E6E6EB"),
    "text-2": ("#5B6270", "#9CA3AF"),
    "hairline": ("rgba(0,0,0,.08)", "rgba(255,255,255,.08)"),
    "accent-from": ("#7C5CFA", "#7C5CFA"),
    "accent-to": ("#3B82F6", "#3B82F6"),
    "button-from": ("#5B3FE0", "#5B3FE0"),
    "button-to": ("#1D4ED8", "#1D4ED8"),
    "ok": ("#047857", "#34D399"),
    "warn": ("#92400E", "#FBBF24"),
    "err": ("#B91C1C", "#F87171"),
    "inc": ("#334155", "#475069"),
}

# Page-scoped extensions (see the module docstring): name -> (light, dark).
EXTENSION_TOKENS: Mapping[str, tuple[str, str]] = {
    "accent-text": ("#5B3FE0", "#A78BFA"),
    "surface-hover": ("#E4E4EE", "#1F1F2E"),
}

# The primary button's hover gradient: mode -> (from, to). Darker than the rest
# stops in light mode, lighter in dark mode; white text holds 4.5:1 or better.
BUTTON_HOVER_STOPS: Mapping[int, tuple[str, str]] = {
    0: ("#4B31C4", "#1A44BE"),
    1: ("#6D52F5", "#2A66DE"),
}

SPACING: tuple[int, ...] = (4, 8, 12, 16, 24, 32, 48, 64)
RADII: Mapping[str, str] = {"card": "12px", "input": "8px", "pill": "999px"}

#: The brand gradient, one token (`--alg-accent-gradient`) the rules reference by name: Gradio's
#: scoper drops a declaration whose function holds `var()` (measured: `background:
#: linear-gradient(90deg, var(--alg-accent-from), var(--alg-accent-to))` never reached the
#: browser) and the sheets carry no literal colours, so the literal stops live here, in the
#: tokens block, the same in both modes.
ACCENT_GRADIENT = (
    f"linear-gradient(90deg, {COLOR_TOKENS['accent-from'][0]}, {COLOR_TOKENS['accent-to'][0]})"
)

# role -> (size px, line px, tracking, weight)
TYPE_SCALE: Mapping[str, tuple[int, int, str, int]] = {
    "count": (64, 64, "-0.03em", 600),  # the header's one number (round 11: "6,040 is huge")
    "display": (40, 48, "-0.02em", 600),
    "title": (28, 34, "-0.01em", 600),
    "body": (15, 22, "0", 400),
    "caption": (12, 16, "0", 400),
    "mono": (13, 20, "0", 400),
}
# role -> (size px, line px) below PHONE_MAX_WIDTH (767, shared with css.py)
TYPE_SCALE_PHONE: Mapping[str, tuple[int, int]] = {
    "count": (48, 48),
    "display": (28, 34),
    "title": (22, 28),
}
#: Every bordered Gradio block's padding, on the 8-pt grid (Gradio's own is 10px 12px).
BLOCK_PADDING = "12px 16px"

FONT_SANS = 'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
FONT_MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'
SANS_FALLBACK_FAMILY = "Inter Fallback"
MONO_FALLBACK_FAMILY = "JetBrains Mono Fallback"
FONT_SANS_PAGE = (
    f'Inter, "{SANS_FALLBACK_FAMILY}", ui-sans-serif, system-ui, -apple-system,'
    ' "Segoe UI", sans-serif'
)
FONT_MONO_PAGE = (
    f'"JetBrains Mono", "{MONO_FALLBACK_FAMILY}", ui-monospace, SFMono-Regular, Menlo, monospace'
)
SHADOW = "0 1px 2px rgba(0,0,0,.06)"
BUTTON_TEXT = "#FFFFFF"

MAX_CONTENT_WIDTH = 1120
PHONE_GUTTER = 16
TARGET_PX = 44
MOTION_MS = 180


class FontFallback(NamedTuple):
    """A local face scaled to a web font's metrics so the swap is shift-free.

    `size_adjust` is the ratio of the web font's advance width to the local face's,
    measured on English body copy in Chromium; `ascent` and `descent` are the web
    font's hhea ascender and descender as a share of the em, divided by the size
    adjustment (the override applies to the adjusted size). Inter: ascender 1984,
    descender 494, em 2048, 5.5 % wider than Arial. JetBrains Mono: ascender 1020,
    descender 300, em 1000, the same 0.6 em advance as Courier New and Menlo.
    """

    family: str
    local: tuple[str, ...]
    size_adjust: str
    ascent: str
    descent: str
    line_gap: str = "0%"

    def css(self) -> str:
        src = ", ".join(f'local("{name}")' for name in self.local)
        return (
            "@font-face {\n"
            f'  font-family: "{self.family}";\n'
            f"  src: {src};\n"
            f"  size-adjust: {self.size_adjust};\n"
            f"  ascent-override: {self.ascent};\n"
            f"  descent-override: {self.descent};\n"
            f"  line-gap-override: {self.line_gap};\n"
            "}"
        )


FONT_FALLBACKS: tuple[FontFallback, ...] = (
    FontFallback(
        SANS_FALLBACK_FAMILY,
        ("Arial", "Liberation Sans", "Helvetica Neue"),
        size_adjust="105.5%",
        ascent="91.8%",
        descent="22.9%",
    ),
    FontFallback(
        MONO_FALLBACK_FAMILY,
        ("Courier New", "Liberation Mono", "Menlo"),
        size_adjust="100%",
        ascent="102%",
        descent="30%",
    ),
)

# Every shadow variable Gradio's Base/Glass theme exposes (gradio 6.28 `Base.set`).
# Missing one means Gradio's own default (up to 0 2px 4px) leaks onto the page.
SHADOW_KEYS_DROP: tuple[str, ...] = (
    "shadow_drop",
    "shadow_drop_lg",
    "block_shadow",
    "block_shadow_dark",
    "block_label_shadow",
    "button_primary_shadow",
    "button_primary_shadow_hover",
    "button_primary_shadow_dark",
    "button_primary_shadow_hover_dark",
    "button_secondary_shadow",
    "button_secondary_shadow_hover",
    "button_secondary_shadow_dark",
    "button_secondary_shadow_hover_dark",
    "button_cancel_shadow",
    "button_cancel_shadow_hover",
    "button_cancel_shadow_dark",
    "button_cancel_shadow_hover_dark",
    "checkbox_label_shadow",
    "checkbox_label_shadow_hover",
    "checkbox_label_shadow_dark",
    "checkbox_label_shadow_hover_dark",
)
SHADOW_KEYS_NONE: tuple[str, ...] = (
    "shadow_inset",
    "button_primary_shadow_active",
    "button_primary_shadow_active_dark",
    "button_secondary_shadow_active",
    "button_secondary_shadow_active_dark",
    "button_cancel_shadow_active",
    "button_cancel_shadow_active_dark",
    "checkbox_shadow",
    "checkbox_label_shadow_active",
    "checkbox_label_shadow_active_dark",
    "input_shadow",
    "input_shadow_dark",
)
SHADOW_KEYS_FOCUS: tuple[str, ...] = ("input_shadow_focus", "input_shadow_focus_dark")
SHADOW_KEYS_SPREAD: tuple[str, ...] = ("shadow_spread", "shadow_spread_dark")
SHADOW_KEYS: tuple[str, ...] = (
    SHADOW_KEYS_DROP + SHADOW_KEYS_NONE + SHADOW_KEYS_FOCUS + SHADOW_KEYS_SPREAD
)
FOCUS_RING_PX = 2


def token(name: str) -> str:
    """`var(--alg-<name>)` for use inside CSS strings."""
    if name not in COLOR_TOKENS and name not in EXTENSION_TOKENS:
        raise KeyError(name)
    return f"var(--alg-{name})"


def _color_block(selector: str, index: int) -> str:
    lines = [f"  --alg-{name}: {values[index]};" for name, values in COLOR_TOKENS.items()]
    return f"{selector} {{\n" + "\n".join(lines) + "\n}"


def _scale_block() -> str:
    lines = [f"  --alg-font: {FONT_SANS};", f"  --alg-font-mono: {FONT_MONO};"]
    lines += [f"  --alg-space-{value}: {value}px;" for value in SPACING]
    lines += [f"  --alg-radius-{name}: {value};" for name, value in RADII.items()]
    for role, (size, line, tracking, weight) in TYPE_SCALE.items():
        lines.append(f"  --alg-{role}-size: {size}px;")
        lines.append(f"  --alg-{role}-line: {line}px;")
        lines.append(f"  --alg-{role}-tracking: {tracking};")
        lines.append(f"  --alg-{role}-weight: {weight};")
    lines.append(f"  --alg-shadow: {SHADOW};")
    lines.append(f"  --alg-accent-gradient: {ACCENT_GRADIENT};")
    lines.append(f"  --alg-content-max: {MAX_CONTENT_WIDTH}px;")
    lines.append(f"  --alg-target: {TARGET_PX}px;")
    lines.append(f"  --alg-motion: {MOTION_MS}ms ease-out;")
    return ":root {\n" + "\n".join(lines) + "\n}"


def _extension_block(index: int) -> str:
    selector = f".{PAGE_CLASS}" if index == 0 else f".dark .{PAGE_CLASS}"
    lines = [f"  --alg-{name}: {values[index]};" for name, values in EXTENSION_TOKENS.items()]
    if index == 0:
        lines.append(f"  --alg-font: {FONT_SANS_PAGE};")
        lines.append(f"  --alg-font-mono: {FONT_MONO_PAGE};")
    return f"{selector} {{\n" + "\n".join(lines) + "\n}"


def _phone_scale_block() -> str:
    lines = []
    for role, (size, line) in TYPE_SCALE_PHONE.items():
        lines.append(f"    --alg-{role}-size: {size}px;")
        lines.append(f"    --alg-{role}-line: {line}px;")
    inner = f"  .{PAGE_CLASS} {{\n" + "\n".join(lines) + "\n  }"
    return f"@media (width <= {PHONE_MAX_WIDTH}px) {{\n{inner}\n}}"


def build_tokens_css() -> str:
    """The `:root` (light) and `.dark` blocks, the mode-independent scale, then the
    page-scoped extensions, the phone type steps and the fallback `@font-face` rules."""
    return "\n".join(
        (
            _color_block(":root", 0),
            _color_block(".dark", 1),
            _scale_block(),
            _extension_block(0),
            _extension_block(1),
            _phone_scale_block(),
            *(fallback.css() for fallback in FONT_FALLBACKS),
        )
    )


TOKENS_CSS = build_tokens_css()

# Type utilities for our own gr.HTML payloads. Same discipline as the shell:
# css.rule() repeats the class four times, no Gradio selectors, no `!important`.

#: The one accent that carries text (hero figure, chips, tabs): 6.5:1 light, 7.3:1 dark.
#: The fallback is the same #5B3FE0 for markup rendered outside the page root.
ACCENT_TEXT = "color: var(--alg-accent-text, var(--alg-button-from));"


def _type_rule(role: str, color: str) -> str:
    return rule(
        f"alg-{role}",
        f"font-family: var(--alg-font); font-size: var(--alg-{role}-size);"
        f" line-height: var(--alg-{role}-line); letter-spacing: var(--alg-{role}-tracking);"
        f" font-weight: var(--alg-{role}-weight); color: var(--alg-{color}); margin: 0;",
    )


# BASE_CSS carries the type utilities and, after them, the Gradio chrome sheet, the
# CodeMirror sheet and the two-column layout rule from css.py, so `fleet_css()` ships
# every shared rule.
BASE_CSS = stylesheet(
    _type_rule("display", "text"),
    _type_rule("title", "text"),
    _type_rule("body", "text"),
    _type_rule("caption", "text-2"),
    rule(
        "alg-mono",
        "font-family: var(--alg-font-mono); font-size: var(--alg-mono-size);"
        " line-height: var(--alg-mono-line); font-variant-numeric: tabular-nums;",
    ),
    rule("alg-num", "font-variant-numeric: tabular-nums;"),
    rule("alg-accent-text", ACCENT_TEXT),
    rule("alg-content", "max-width: var(--alg-content-max); margin: 0 auto; padding: 0 16px;"),
    CHROME_CSS.rstrip("\n"),
    CODE_CSS.rstrip("\n"),
    LAYOUT_CSS.rstrip("\n"),
)


def button_gradient(mode: int = 0) -> str:
    """The primary-button fill: the `button-*` stops, white text at 4.5:1 or better."""
    start, end = COLOR_TOKENS["button-from"][mode], COLOR_TOKENS["button-to"][mode]
    return f"linear-gradient(135deg, {start} 0%, {end} 100%)"


def button_hover_gradient(mode: int = 0) -> str:
    """The primary-button hover fill: `BUTTON_HOVER_STOPS`, white text at 4.5:1 or better."""
    start, end = BUTTON_HOVER_STOPS[mode]
    return f"linear-gradient(135deg, {start} 0%, {end} 100%)"


def theme_settings() -> dict[str, str]:
    """The Gradio theme variables pinned to the token set, light and `_dark` alike.

    Every state Gradio's stylesheet reads from a variable is pinned here: button rest
    and hover (primary, secondary, cancel), tab selected colour and hover fill
    (`color_accent`, `background_fill_secondary`), input rest, hover and focus, the
    checkbox and radio box in every state, the option-label pills, the block label, the
    error banner, tables, the slider fill and the loader. Padding variables put the
    text inputs, option labels and buttons on the 44 px target and every block on the
    8-pt grid (`BLOCK_PADDING`); `css.CHROME_CSS` adds the explicit minimums.
    """
    light = {name: values[0] for name, values in COLOR_TOKENS.items()}
    dark = {name: values[1] for name, values in COLOR_TOKENS.items()}
    light.update({name: values[0] for name, values in EXTENSION_TOKENS.items()})
    dark.update({name: values[1] for name, values in EXTENSION_TOKENS.items()})
    settings: dict[str, str] = {}

    def both(key: str, light_value: str, dark_value: str) -> None:
        settings[key] = light_value
        settings[f"{key}_dark"] = dark_value

    def same(key: str, name: str) -> None:
        both(key, light[name], dark[name])

    # page and blocks
    same("body_background_fill", "bg")
    same("body_text_color", "text")
    same("body_text_color_subdued", "text-2")
    same("background_fill_primary", "surface")
    same("background_fill_secondary", "surface-2")
    same("block_background_fill", "surface")
    both("block_border_width", "1px", "1px")
    same("block_border_color", "hairline")
    same("border_color_primary", "hairline")
    same("border_color_accent", "accent-to")
    same("border_color_accent_subdued", "hairline")
    # `color_accent` has no `_dark` twin in Base.set(); theme() sets the dark value
    # through THEME_DARK_EXTRAS so the selected tab reads 4.5:1 in both modes.
    settings["color_accent"] = light["accent-text"]
    same("color_accent_soft", "surface-2")
    same("panel_background_fill", "surface")
    same("panel_border_color", "hairline")
    settings["block_padding"] = BLOCK_PADDING
    same("block_title_text_color", "text")
    same("block_info_text_color", "text-2")
    same("accordion_text_color", "text")
    same("block_label_text_color", "text-2")
    same("block_label_background_fill", "surface-2")
    same("block_label_border_color", "hairline")
    settings["block_label_text_size"] = f"{TYPE_SCALE['caption'][0]}px"
    settings["block_label_text_weight"] = "500"
    settings["block_label_padding"] = "4px 12px"
    settings["block_info_text_size"] = f"{TYPE_SCALE['caption'][0]}px"
    settings["block_title_text_weight"] = "600"
    settings["section_header_text_size"] = f"{TYPE_SCALE['body'][0]}px"
    settings["section_header_text_weight"] = "500"
    same("link_text_color", "accent-text")
    same("link_text_color_hover", "accent-text")
    same("link_text_color_active", "accent-text")
    same("link_text_color_visited", "accent-text")
    # inputs
    same("input_background_fill", "surface-2")
    same("input_background_fill_hover", "surface-2")
    same("input_background_fill_focus", "surface-2")
    same("input_border_color", "hairline")
    same("input_border_color_hover", "text-2")
    same("input_border_color_focus", "accent-to")
    same("input_placeholder_color", "text-2")
    settings["input_padding"] = "12px 16px"
    settings["input_text_size"] = f"{TYPE_SCALE['body'][0]}px"
    same("slider_color", "accent-to")
    same("loader_color", "accent-to")
    same("stat_background_fill", "accent-to")
    same("code_background_fill", "surface-2")
    # checkbox and radio boxes: unchecked = surface + a visible hairline, checked = accent
    both("checkbox_background_color", light["surface"], dark["surface-2"])
    both("checkbox_background_color_hover", light["surface"], dark["surface-2"])
    both("checkbox_background_color_focus", light["surface"], dark["surface-2"])
    same("checkbox_background_color_selected", "button-to")
    same("checkbox_border_color", "text-2")
    same("checkbox_border_color_hover", "text")
    same("checkbox_border_color_focus", "accent-to")
    same("checkbox_border_color_selected", "button-to")
    both("checkbox_border_width", "1px", "1px")
    # half the input radius: a 20 px box with an 8 px radius reads as a circle, i.e. a radio
    settings["checkbox_border_radius"] = f"calc({RADII['input']} / 2)"
    # option-label pills (Radio, CheckboxGroup) and the dropdown's inner row
    same("checkbox_label_background_fill", "surface-2")
    same("checkbox_label_background_fill_hover", "surface-hover")
    same("checkbox_label_background_fill_selected", "surface-2")
    same("checkbox_label_border_color", "hairline")
    same("checkbox_label_border_color_hover", "text-2")
    same("checkbox_label_border_color_selected", "accent-to")
    both("checkbox_label_border_width", "1px", "1px")
    same("checkbox_label_text_color", "text")
    same("checkbox_label_text_color_selected", "text")
    settings["checkbox_label_padding"] = "12px 16px"
    settings["checkbox_label_gap"] = "8px"
    settings["checkbox_label_text_size"] = f"{TYPE_SCALE['body'][0]}px"
    settings["checkbox_label_text_weight"] = "400"
    # buttons
    both("button_primary_background_fill", button_gradient(0), button_gradient(1))
    both(
        "button_primary_background_fill_hover",
        button_hover_gradient(0),
        button_hover_gradient(1),
    )
    both("button_primary_text_color", BUTTON_TEXT, BUTTON_TEXT)
    both("button_primary_text_color_hover", BUTTON_TEXT, BUTTON_TEXT)
    both("button_primary_border_color", "transparent", "transparent")
    both("button_primary_border_color_hover", "transparent", "transparent")
    same("button_secondary_background_fill", "surface-2")
    same("button_secondary_background_fill_hover", "surface-hover")
    same("button_secondary_text_color", "text")
    same("button_secondary_text_color_hover", "text")
    same("button_secondary_border_color", "hairline")
    same("button_secondary_border_color_hover", "text-2")
    same("button_cancel_background_fill", "surface-2")
    same("button_cancel_background_fill_hover", "surface-hover")
    same("button_cancel_text_color", "err")
    same("button_cancel_text_color_hover", "err")
    same("button_cancel_border_color", "err")
    same("button_cancel_border_color_hover", "err")
    both("button_border_width", "1px", "1px")
    settings["button_transform_hover"] = "none"
    settings["button_transform_active"] = "none"
    settings["button_transition"] = (
        f"background-color {MOTION_MS}ms ease-out, border-color {MOTION_MS}ms ease-out,"
        f" color {MOTION_MS}ms ease-out"
    )
    settings["button_large_padding"] = "12px 24px"
    settings["button_medium_padding"] = "12px 16px"
    settings["button_small_padding"] = "8px 16px"
    settings["button_large_text_size"] = f"{TYPE_SCALE['body'][0]}px"
    settings["button_medium_text_size"] = f"{TYPE_SCALE['body'][0]}px"
    settings["button_small_text_size"] = f"{TYPE_SCALE['mono'][0]}px"
    settings["button_large_text_weight"] = "600"
    settings["button_medium_text_weight"] = "600"
    settings["button_small_text_weight"] = "500"
    # tables and errors
    same("table_border_color", "hairline")
    same("table_even_background_fill", "surface")
    same("table_odd_background_fill", "surface-2")
    same("table_row_focus", "surface-2")
    same("table_text_color", "text")
    same("error_background_fill", "surface")
    same("error_border_color", "err")
    same("error_text_color", "err")
    same("error_icon_color", "err")
    both("error_border_width", "1px", "1px")
    # shadows and focus
    for key in SHADOW_KEYS_DROP:
        settings[key] = SHADOW
    for key in SHADOW_KEYS_NONE:
        settings[key] = "none"
    ring = f"0 0 0 {FOCUS_RING_PX}px"
    settings["input_shadow_focus"] = f"{ring} {light['accent-to']}"
    settings["input_shadow_focus_dark"] = f"{ring} {dark['accent-to']}"
    settings["shadow_spread"] = f"{FOCUS_RING_PX}px"
    settings["shadow_spread_dark"] = f"{FOCUS_RING_PX}px"
    settings["block_radius"] = RADII["card"]
    settings["input_radius"] = RADII["input"]
    settings["button_large_radius"] = RADII["input"]
    settings["button_medium_radius"] = RADII["input"]
    settings["button_small_radius"] = RADII["input"]
    settings["block_label_radius"] = RADII["input"]
    settings["block_label_right_radius"] = RADII["input"]
    settings["container_radius"] = RADII["input"]
    settings["embed_radius"] = RADII["card"]
    return settings


def theme_dark_extras() -> dict[str, str]:
    """Dark-mode values for variables `Base.set()` exposes without a `_dark` parameter.

    Gradio's theme CSS is emitted from the theme's attributes, dark ones by their `_dark`
    suffix, so setting these as attributes puts them in the `.dark` block: `color_accent`
    drives the selected tab text and underline, the slider fill and the generating border.
    """
    return {"color_accent_dark": EXTENSION_TOKENS["accent-text"][1]}


def theme() -> Any:
    """The Gradio Glass theme carrying the token set in both modes (imports gradio lazily).

    The font stacks name the metric-matched fallback faces right after the web fonts,
    so Gradio's own `--font` and `--font-mono` swap without a layout shift too.
    """
    import gradio as gr

    base = gr.themes.Glass(
        primary_hue="violet",
        secondary_hue="blue",
        neutral_hue="slate",
        font=[
            gr.themes.GoogleFont("Inter"),
            gr.themes.Font(SANS_FALLBACK_FAMILY),
            "ui-sans-serif",
            "system-ui",
            "sans-serif",
        ],
        font_mono=[
            gr.themes.GoogleFont("JetBrains Mono"),
            gr.themes.Font(MONO_FALLBACK_FAMILY),
            "ui-monospace",
            "monospace",
        ],
        text_size="md",
        spacing_size="md",
        radius_size="lg",
    )
    themed = base.set(**theme_settings())
    for name, value in theme_dark_extras().items():
        setattr(themed, name, value)
    return themed
