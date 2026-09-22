"""The Algenta design system — Gradio 6 edition (LLM Agents lab copy).

THEME is replicated verbatim from the canonical flagship source of truth,
thyn-ai/algenta `design.py`: a `gr.themes.Glass` base plus `.set(...)` token
pins carrying the dark premium palette through Gradio's own variable system,
every visible token pinned TWICE (base and `_dark`) so the OS dark/light
auto-flip is a no-op and the UI can never render light-on-dark.

CSS here styles only the classes inside OUR OWN markdown/HTML payloads
(examples-library cards, lane tables, hardware/simulated badges) on the
canonical dark palette. No component-internal selectors, no `!important`
wars. Layout width comes from `gr.Blocks(fill_width=True)`.

Palette: bg #0A0A0F · surface #12121A · surface-2 #181824 · hairline
rgba(255,255,255,0.06) · text #E6E6EB · secondary #9CA3AF · accent gradient
#7C5CFA → #3B82F6 · success #34D399 · warn #FBBF24.
"""

from __future__ import annotations

import gradio as gr

# ---------------------------------------------------------------------------
# 1 · Theme — Glass base, dark premium palette pinned in BOTH modes
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

# ---------------------------------------------------------------------------
# 2 · CSS — styles for OUR OWN HTML payloads only (the classes inside markdown
# and gr.HTML strings: examples-library cards, lane tables, hardware and
# simulated-engine badges). Never a Gradio-internal selector.
# ---------------------------------------------------------------------------

CSS = r"""
.kgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; margin-top: 10px; }
.kcard { border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 14px; background: #12121A; }
.kname { font-weight: 650; font-size: 14px; }
.klinks { font-size: 12px; color: #6B7280; }
.klinks a { color: #A5B4FC; }
.lane-table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 6px 0 10px; }
.lane-table th, .lane-table td { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid rgba(255,255,255,0.06); vertical-align: top; font-variant-numeric: tabular-nums; font-family: var(--font-mono); }
.lane-table th { color: #9CA3AF; font-family: var(--font); }
.card-hw { font-size: 12px; color: #6B7280; margin-top: 8px; font-family: var(--font-mono); }
.card-hw a { color: #A5B4FC; }
.badge-sim { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: #181824; border: 1px solid rgba(251,191,36,0.35); color: #FBBF24; display: inline-block; }
"""

# ---------------------------------------------------------------------------
# 3 · Force dark mode — the brand is dark-only. On a light-mode OS, Gradio's
# non-dark `:root` section would otherwise keep light surface tokens while our
# text tokens stay light-on-dark. Passed as `js=` to `demo.launch(...)`.
# ---------------------------------------------------------------------------

FORCE_DARK_JS = "() => { document.documentElement.classList.add('dark'); }"
