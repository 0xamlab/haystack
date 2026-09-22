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
the brand accent #7C5CFA -> #3B82F6 is decorative only (headers, gradient text),
because white text on #3B82F6 is 3.7:1. The button stops hold at least 4.5:1
against white at both ends and at the midpoint, in both modes.

Shadows: `SHADOW` is the heaviest drop shadow the fleet draws; every Gradio
shadow variable is pinned to it, to `none`, or (focus rings) to a 2 px
zero-blur ring in the accent colour.

`theme()` builds the Gradio theme lazily so this module imports without gradio.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .css import block, rule, stylesheet

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

SPACING: tuple[int, ...] = (4, 8, 12, 16, 24, 32, 48, 64)
RADII: Mapping[str, str] = {"card": "12px", "input": "8px", "pill": "999px"}

# role -> (size px, line px, tracking, weight)
TYPE_SCALE: Mapping[str, tuple[int, int, str, int]] = {
    "display": (40, 48, "-0.02em", 600),
    "title": (28, 34, "-0.01em", 600),
    "body": (15, 22, "0", 400),
    "caption": (12, 16, "0", 400),
    "mono": (13, 20, "0", 400),
}

FONT_SANS = 'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif'
FONT_MONO = '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'
SHADOW = "0 1px 2px rgba(0,0,0,.06)"
BUTTON_TEXT = "#FFFFFF"

MAX_CONTENT_WIDTH = 1120
PHONE_GUTTER = 16
TARGET_PX = 44
MOTION_MS = 180

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
    if name not in COLOR_TOKENS:
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
    lines.append(f"  --alg-content-max: {MAX_CONTENT_WIDTH}px;")
    lines.append(f"  --alg-target: {TARGET_PX}px;")
    lines.append(f"  --alg-motion: {MOTION_MS}ms ease-out;")
    return ":root {\n" + "\n".join(lines) + "\n}"


def build_tokens_css() -> str:
    """The `:root` (light) and `.dark` blocks plus the mode-independent scale."""
    return "\n".join((_color_block(":root", 0), _color_block(".dark", 1), _scale_block()))


TOKENS_CSS = build_tokens_css()

# Type utilities for our own gr.HTML payloads. Same discipline as the shell:
# css.rule() repeats the class four times, no Gradio selectors, no `!important`.

_GRADIENT_TEXT = (
    "background: linear-gradient(100deg, var(--alg-accent-from), var(--alg-accent-to));"
    " -webkit-background-clip: text; background-clip: text; color: transparent;"
)


def _type_rule(role: str, color: str) -> str:
    return rule(
        f"alg-{role}",
        f"font-family: var(--alg-font); font-size: var(--alg-{role}-size);"
        f" line-height: var(--alg-{role}-line); letter-spacing: var(--alg-{role}-tracking);"
        f" font-weight: var(--alg-{role}-weight); color: var(--alg-{color}); margin: 0;",
    )


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
    rule("alg-accent-text", "color: var(--alg-accent-from);"),
    block(
        "@supports ((-webkit-background-clip: text) or (background-clip: text))",
        rule("alg-accent-text", _GRADIENT_TEXT),
    ),
    rule("alg-content", "max-width: var(--alg-content-max); margin: 0 auto; padding: 0 16px;"),
)


def button_gradient(mode: int = 0) -> str:
    """The primary-button fill: the `button-*` stops, white text at 4.5:1 or better."""
    start, end = COLOR_TOKENS["button-from"][mode], COLOR_TOKENS["button-to"][mode]
    return f"linear-gradient(135deg, {start} 0%, {end} 100%)"


def theme_settings() -> dict[str, str]:
    """The Gradio theme variables pinned to the token set, light and `_dark` alike."""
    light = {name: values[0] for name, values in COLOR_TOKENS.items()}
    dark = {name: values[1] for name, values in COLOR_TOKENS.items()}
    settings: dict[str, str] = {}

    def both(key: str, light_value: str, dark_value: str) -> None:
        settings[key] = light_value
        settings[f"{key}_dark"] = dark_value

    both("body_background_fill", light["bg"], dark["bg"])
    both("body_text_color", light["text"], dark["text"])
    both("body_text_color_subdued", light["text-2"], dark["text-2"])
    both("block_background_fill", light["surface"], dark["surface"])
    both("block_border_width", "1px", "1px")
    both("border_color_primary", light["hairline"], dark["hairline"])
    both("input_background_fill", light["surface-2"], dark["surface-2"])
    both("input_border_color", light["hairline"], dark["hairline"])
    both("block_label_text_color", light["text-2"], dark["text-2"])
    both("block_title_text_color", light["text"], dark["text"])
    both("button_primary_background_fill", button_gradient(0), button_gradient(1))
    both("button_primary_text_color", BUTTON_TEXT, BUTTON_TEXT)
    both("button_primary_border_color", "transparent", "transparent")
    both("button_secondary_background_fill", light["surface-2"], dark["surface-2"])
    both("button_secondary_text_color", light["text"], dark["text"])
    both("button_secondary_border_color", light["hairline"], dark["hairline"])
    for key in SHADOW_KEYS_DROP:
        settings[key] = SHADOW
    for key in SHADOW_KEYS_NONE:
        settings[key] = "none"
    ring = f"0 0 0 {FOCUS_RING_PX}px"
    settings["input_shadow_focus"] = f"{ring} {light['accent-to']}"
    settings["input_shadow_focus_dark"] = f"{ring} {dark['accent-to']}"
    settings["shadow_spread"] = f"{FOCUS_RING_PX}px"
    settings["shadow_spread_dark"] = f"{FOCUS_RING_PX}px"
    settings["block_title_text_weight"] = "600"
    settings["block_radius"] = RADII["card"]
    settings["input_radius"] = RADII["input"]
    settings["button_large_radius"] = RADII["input"]
    settings["button_small_radius"] = RADII["input"]
    return settings


def theme() -> Any:
    """The Gradio Glass theme carrying the token set in both modes (imports gradio lazily)."""
    import gradio as gr

    base = gr.themes.Glass(
        primary_hue="violet",
        secondary_hue="blue",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"],
        text_size="md",
        spacing_size="md",
        radius_size="lg",
    )
    return base.set(**theme_settings())
