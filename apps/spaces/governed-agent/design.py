"""The Algenta design system — Gradio 6 edition (Governed Agent copy).

THEME is replicated verbatim from the canonical flagship source of truth,
thyn-ai/algenta `design.py`: a `gr.themes.Glass` base plus `.set(...)` token
pins carrying the dark premium palette through Gradio's own variable system,
every visible token pinned TWICE (base and `_dark`) so the OS dark/light
auto-flip is a no-op and the UI can never render light-on-dark.

CSS here styles only the classes inside OUR OWN markdown/HTML payloads
(status badges, verdict spans, status pill, boot-sequence card, governance
receipt/denial cards, panels, footers) and the `elem_classes` hooks we place
on our own components. No component-internal selectors, no `!important`
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
# 2 · CSS — styles for OUR OWN markdown payload classes and elem_classes
# hooks only (status badges, verdict spans, panels, footers). Never a
# Gradio-internal selector.
# ---------------------------------------------------------------------------

CSS = r"""
.panel { background: #12121A; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 14px 16px; }
.badge { display: inline-block; font-size: 12px; padding: 3px 10px; border-radius: 999px; background: #181824; border: 1px solid rgba(255,255,255,0.10); color: #9CA3AF; margin: 2px 4px 2px 0; }
.badge-ok { border-color: rgba(52,211,153,0.35); color: #34D399; }
.badge-warn { border-color: rgba(251,191,36,0.35); color: #FBBF24; }
.badge-bad { border-color: rgba(248,113,113,0.5); color: #F87171; }
.muted { color: #9CA3AF; }
.small { font-size: 12px; }
.verdict-ok { color: #34D399; font-weight: 600; }
.verdict-warn { color: #FBBF24; font-weight: 600; }
.verdict-bad { color: #F87171; font-weight: 600; }
footer { border-top: 1px solid rgba(255,255,255,0.06); margin-top: 18px; padding-top: 10px; }

/* status pill — the reference-Spaces header signal (loading/ready/busy/error) */
.pill { display: inline-flex; align-items: center; gap: 8px; font-family: var(--font-mono); font-size: 12px; padding: 5px 14px; border-radius: 999px; background: #181824; border: 1px solid rgba(255,255,255,0.10); color: #9CA3AF; }
.pill-dot { width: 8px; height: 8px; border-radius: 999px; background: #9CA3AF; }
.pill-loading { border-color: rgba(251,191,36,0.35); color: #FBBF24; }
.pill-loading .pill-dot { background: #FBBF24; box-shadow: 0 0 10px rgba(251,191,36,0.5); animation: pillPulse 1.1s ease-in-out infinite; }
.pill-ready { border-color: rgba(52,211,153,0.35); color: #34D399; }
.pill-ready .pill-dot { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.5); }
.pill-busy { border-color: rgba(52,211,153,0.35); color: #34D399; }
.pill-busy .pill-dot { background: #34D399; box-shadow: 0 0 10px rgba(52,211,153,0.5); animation: pillPulse 1.1s ease-in-out infinite; }
.pill-error { border-color: rgba(248,113,113,0.5); color: #F87171; }
.pill-error .pill-dot { background: #F87171; box-shadow: 0 0 10px rgba(248,113,113,0.5); }
@keyframes pillPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }

/* boot-sequence card — explicit stage checklist + monotonic progress bar */
.boot-card { background: #12121A; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 14px 16px; margin: 10px 0; }
.boot-title { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #9CA3AF; font-family: var(--font-mono); margin-bottom: 10px; }
.boot-bar { height: 6px; border-radius: 4px; background: rgba(255,255,255,0.06); overflow: hidden; margin-bottom: 12px; }
.boot-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, #7C5CFA, #3B82F6); transition: width 0.5s ease; }
.boot-step { font-size: 13px; color: #9CA3AF; padding: 3px 0; display: flex; gap: 8px; align-items: baseline; }
.boot-icon { font-family: var(--font-mono); width: 14px; display: inline-block; text-align: center; }
.boot-done { color: #34D399; }
.boot-running { color: #FBBF24; }
.boot-error { color: #F87171; }
.boot-detail { font-size: 12px; color: #6B7280; font-family: var(--font-mono); margin-left: 6px; }

/* governance receipt / denial / preview cards (rendered inside chat payloads) */
.gov-card { border-radius: 12px; padding: 12px 14px; font-size: 13px; line-height: 1.6; background: #12121A; border: 1px solid rgba(255,255,255,0.08); }
.gov-card code { font-family: var(--font-mono); font-size: 12px; }
.gov-ok { border-color: rgba(52,211,153,0.45); color: #A7F3D0; }
.gov-deny { border-color: rgba(248,113,113,0.55); color: #FECACA; }
.gov-warn { border-color: rgba(251,191,36,0.45); color: #FDE68A; }
.gov-hint { font-size: 12px; opacity: 0.75; }
"""

# ---------------------------------------------------------------------------
# 3 · Force dark mode — the brand is dark-only; on a light-mode OS Gradio's
# `:root` (non-dark) section would otherwise keep light surface tokens while
# our text tokens stay light-on-dark. Passed as `js=` to `demo.launch(...)`.
# ---------------------------------------------------------------------------

FORCE_DARK_JS = "() => { document.documentElement.classList.add('dark'); }"
