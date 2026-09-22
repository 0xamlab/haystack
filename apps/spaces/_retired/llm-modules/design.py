"""The Algenta design system — Gradio 6 edition (LLM Modules copy).

THEME is replicated verbatim from the canonical flagship source of truth,
thyn-ai/algenta `design.py`: a `gr.themes.Glass` base plus `.set(...)` token
pins carrying the dark premium palette through Gradio's own variable system,
every visible token pinned TWICE (base and `_dark`) so the OS dark/light
auto-flip is a no-op and the UI can never render light-on-dark.

This Space's UI is entirely stock Gradio components (tabs, buttons, code
panels, dataframes, accordions), so THEME alone carries the whole look —
no custom CSS is needed. Layout width comes from
`gr.Blocks(fill_width=True)`. FORCE_DARK_JS adds the `dark` class on load
so Gradio's `_dark` token set applies even on a light-mode OS (tokens we
do not pin, e.g. `--background-fill-primary`, would otherwise stay light
while our text tokens are light-on-dark).

Palette: bg #0A0A0F · surface #12121A · surface-2 #181824 · hairline
rgba(255,255,255,0.06) · text #E6E6EB · secondary #9CA3AF · accent gradient
#7C5CFA → #3B82F6 · success #34D399 · warn #FBBF24.
"""

from __future__ import annotations

import gradio as gr

# ---------------------------------------------------------------------------
# Theme — Glass base, dark premium palette pinned in BOTH modes
#    (verbatim copy of the canonical flagship THEME — keep in sync)
# ---------------------------------------------------------------------------

_BG = "#0A0A0F"
_SURFACE = "#12121A"
_SURFACE_2 = "#181824"
_SURFACE_2_HOVER = "#1E1E2C"
_HAIRLINE = "rgba(255,255,255,0.06)"
_HAIRLINE_STRONG = "rgba(255,255,255,0.10)"
_TEXT = "#E6E6EB"
_TEXT_2 = "#9CA3AF"
_ACCENT_FROM = "#7C5CFA"
_ACCENT_TO = "#3B82F6"

THEME = gr.themes.Glass(
    primary_hue="violet",
    secondary_hue="blue",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter")],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono")],
    text_size="md",
    spacing_size="md",
    radius_size="lg",
).set(
    # --- page + text: dark unconditionally (base == _dark, no OS flip) ---
    body_background_fill=_BG,
    body_background_fill_dark=_BG,
    body_text_color=_TEXT,
    body_text_color_dark=_TEXT,
    body_text_color_subdued=_TEXT_2,
    body_text_color_subdued_dark=_TEXT_2,
    # --- surfaces + hairlines ---
    block_background_fill=_SURFACE,
    block_background_fill_dark=_SURFACE,
    block_border_width="1px",
    block_border_width_dark="1px",
    border_color_primary=_HAIRLINE,
    border_color_primary_dark=_HAIRLINE,
    # --- inputs on surface-2 ---
    input_background_fill=_SURFACE_2,
    input_background_fill_dark=_SURFACE_2,
    input_border_color=_HAIRLINE_STRONG,
    input_border_color_dark=_HAIRLINE_STRONG,
    # --- labels + titles readable on the dark surfaces ---
    block_label_text_color=_TEXT_2,
    block_label_text_color_dark=_TEXT_2,
    block_title_text_color=_TEXT,
    block_title_text_color_dark=_TEXT,
    block_title_text_weight="600",
    # --- one gradient primary button; quiet secondary ---
    button_primary_background_fill=f"linear-gradient(135deg, {_ACCENT_FROM} 0%, {_ACCENT_TO} 100%)",
    button_primary_background_fill_dark=f"linear-gradient(135deg, {_ACCENT_FROM} 0%, {_ACCENT_TO} 100%)",
    button_primary_background_fill_hover="linear-gradient(135deg, #8A6CFF 0%, #4C8DFF 100%)",
    button_primary_background_fill_hover_dark="linear-gradient(135deg, #8A6CFF 0%, #4C8DFF 100%)",
    button_primary_text_color="#FFFFFF",
    button_primary_text_color_dark="#FFFFFF",
    button_primary_border_color="transparent",
    button_primary_border_color_dark="transparent",
    button_secondary_background_fill=_SURFACE_2,
    button_secondary_background_fill_dark=_SURFACE_2,
    button_secondary_background_fill_hover=_SURFACE_2_HOVER,
    button_secondary_background_fill_hover_dark=_SURFACE_2_HOVER,
    button_secondary_text_color=_TEXT,
    button_secondary_text_color_dark=_TEXT,
    button_secondary_border_color=_HAIRLINE,
    button_secondary_border_color_dark=_HAIRLINE,
)

# Force dark mode on load: our brand is dark-only, and on a light-mode OS
# Gradio's unpinned light tokens would render white panels with invisible
# light text. Passed as `js=FORCE_DARK_JS` to `launch(...)`.
FORCE_DARK_JS = "() => { document.documentElement.classList.add('dark'); }"
