"""The Algenta design system — Gradio 6 edition (Speed Arena copy).

THEME is replicated verbatim from the canonical flagship source of truth,
thyn-ai/algenta `design.py`: a `gr.themes.Glass` base plus `.set(...)` token
pins carrying the dark premium palette through Gradio's own variable system,
every visible token pinned TWICE (base and `_dark`) so the OS dark/light
auto-flip is a no-op and the UI can never render light-on-dark.

CSS here styles only the classes inside OUR OWN gr.HTML/markdown payloads
(arena duel cards, lane charts, chips, kernel gallery, hardware badge) —
the same duel-card/lane/chip styles the flagship uses, plus the gallery
extras, all on the canonical dark palette. No component-internal selectors,
no `!important` wars. Layout width comes from `gr.Blocks(fill_width=True)`.

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
# 1b · Force dark mode — Gradio's :root (non-dark) section keeps light surface
# tokens on a light-mode OS, which would render white panels under our
# light-on-dark text. The brand is dark-only, so pin the `dark` class at load.
# ---------------------------------------------------------------------------

FORCE_DARK_JS = "() => { document.documentElement.classList.add('dark'); }"

# ---------------------------------------------------------------------------
# 2 · CSS — styles for OUR OWN HTML payloads only (the classes inside gr.HTML
# strings: duel result cards, lane charts, chips, kernel gallery, hardware
# badge). The duel/lane/chip/card block is the flagship's canonical set,
# kept verbatim; the kgrid/kcard gallery and badge-hw are mapped onto the
# same dark palette. Never a Gradio-internal selector.
# ---------------------------------------------------------------------------

CSS = r"""
/* duel result cards (rendered by arena/card.py — markup kept verbatim) */
.duel-card { border: 1px solid rgba(124,92,250,0.4); border-radius: 14px; padding: 18px 20px; background: #12121A; }
.duel-card.placeholder { background: #0D0D14; white-space: pre-wrap; font-family: var(--font-mono); font-size: 13px; border-color: rgba(255,255,255,0.06); }
.duel-card.warn { border-color: rgba(251,191,36,0.5); }
.duel-card.error { border-color: rgba(248,113,113,0.5); }
.duel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.duel-title { font-size: 20px; font-weight: 650; letter-spacing: -0.02em; }
.duel-sub { font-size: 12px; color: #9CA3AF; margin-top: 4px; font-family: var(--font-mono); }
.hero { text-align: right; }
.hero-num { font-family: var(--font-mono); font-size: 40px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; color: #A78BFA; }
@supports ((-webkit-background-clip: text) or (background-clip: text)) {
  .hero-num { background: linear-gradient(100deg, #7C5CFA, #3B82F6); -webkit-background-clip: text; background-clip: text; color: transparent; }
}
.hero-label { font-size: 12px; color: #9CA3AF; inline-size: min(260px, 100%); }
.lane-chart { margin: 16px 0 6px; display: flex; flex-direction: column; gap: 6px; }
.lane-row { display: flex; align-items: center; gap: 8px; }
.lane-name { flex: 0 0 180px; font-size: 12px; font-weight: 600; }
@media (width <= 560px) { .lane-name { flex-basis: 110px; } }
.lane-barwrap { flex: 1; background: rgba(255,255,255,0.06); border-radius: 6px; height: 18px; min-width: 40px; }
.lane-bar { height: 100%; border-radius: 6px; }
.lane-bar.inc { background: linear-gradient(90deg, #475069, #334155); }
.lane-bar.alg { background: linear-gradient(90deg, #7C5CFA, #3B82F6); }
.lane-val { flex: 0 0 96px; font-size: 12px; font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; }
.chart-note { font-size: 12px; color: #6B7280; margin-bottom: 10px; }
.lane-table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 6px 0 10px; }
.lane-table th, .lane-table td { text-align: left; padding: 4px 8px 4px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-variant-numeric: tabular-nums; font-family: var(--font-mono); }
.lane-table th { color: #9CA3AF; font-family: var(--font); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; font-family: var(--font-mono); background: #181824; border: 1px solid rgba(255,255,255,0.06); color: #9CA3AF; }
.chip.ok { color: #34D399; border-color: rgba(52,211,153,0.35); }
.card-config { font-size: 12px; color: #9CA3AF; margin: 8px 0; line-height: 1.55; }
.card-details { font-size: 12px; margin-top: 8px; color: #9CA3AF; }
.card-details a { color: #A5B4FC; }
.card-hw { font-size: 12px; color: #6B7280; margin-top: 8px; font-family: var(--font-mono); }
.card-hw a { color: #A5B4FC; }
.card-reason { font-size: 14px; font-weight: 600; margin: 10px 0; color: #FBBF24; }
.duel-card.error .card-reason { color: #F87171; }
/* kernel gallery (rendered by arena/gallery.py) */
.kgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; margin-top: 10px; }
.kcard { border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px 14px; background: #12121A; }
.kname { font-weight: 650; font-size: 14px; }
.ktarget { font-size: 12px; color: #9CA3AF; margin-top: 2px; }
.kspeed { font-family: var(--font-mono); font-size: 14px; color: #A78BFA; font-weight: 700; margin: 6px 0; font-variant-numeric: tabular-nums; }
.klinks { font-size: 12px; color: #6B7280; }
.klinks a { color: #A5B4FC; }
.kgallery-intro { font-size: 13px; color: #9CA3AF; max-width: 900px; }
.badge-hw { font-size: 12px; padding: 4px 10px; border-radius: 999px; background: #181824; border: 1px solid rgba(255,255,255,0.10); color: #9CA3AF; display: inline-block; }
"""
