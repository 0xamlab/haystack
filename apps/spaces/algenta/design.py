"""The Algenta flagship design system — Gradio 6 edition.

Architecture (why this survives the Svelte 5 rewrite that killed the old
hand-CSS):

1. THEME does the retheming. A `gr.themes.Glass` base plus `.set(...)` token
   pins carry the whole dark premium palette through Gradio's own variable
   system — every component (tabs, buttons, inputs, dataframes, accordions,
   toasts) is styled by Gradio itself, so no component-internal selector of
   ours can break on an upgrade. Every visible token is pinned TWICE, base
   and `_dark`, to the same value: the OS dark/light auto-flip becomes a
   no-op and the UI can never render light-on-dark.

2. CSS (≤40 lines) is the only shell stylesheet, and it selects exclusively
   through `elem_classes` hooks we place on our own components (hero
   typography, the accent-gradient headline with a solid-color @supports
   fallback, section rules, footer, small spacing polish). No
   component-internal selectors, no `!important` wars, no max-width clamps —
   full width comes from `gr.Blocks(fill_width=True)`, never from CSS.

3. COMPONENT_CSS styles only the `alg-*` / `duel-*` / `lane-*` classes that
   live INSIDE our own gr.HTML payloads (arena result cards, metric strip,
   product map, wave-3 cards, MCP category cells, verdicts). That markup is
   ours forever, so these selectors are upgrade-proof too. Layout width and
   Gradio components are never touched here.

4. JS is minimal and ours: COUNTUP_JS, an observer-based <300ms count-up for
   hero metric numbers driven by data-target attributes in our own HTML (no
   Gradio internals), plus FORCE_DARK_JS, a one-line launch hook that pins the
   `dark` class so light-mode OSes never get Gradio's light token set.

Palette: bg #0A0A0F · surface #12121A · surface-2 #181824 · hairline
rgba(255,255,255,0.06) · text #E6E6EB · secondary #9CA3AF · accent gradient
#7C5CFA → #3B82F6 · success #34D399 · warn #FBBF24.
"""

from __future__ import annotations

import gradio as gr

# ---------------------------------------------------------------------------
# 1 · Theme — Glass base, dark premium palette pinned in BOTH modes
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
# 2 · CSS — the shell stylesheet. ≤40 lines, elem_classes hooks ONLY.
# Hooks: alg-hero (gr.HTML), alg-section (gr.HTML section headers),
# alg-footer (gr.HTML). Everything Gradio renders is themed by THEME.
# ---------------------------------------------------------------------------

CSS = r"""
.alg-hero { padding: 40px 0 8px; }
.alg-hero .alg-eyebrow { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--body-text-color-subdued); margin-bottom: 14px; }
.alg-hero h1 { font-size: clamp(40px, 6vw, 64px); line-height: 1.02; letter-spacing: -0.03em; font-weight: 700; margin: 0 0 18px; }
.alg-hero .alg-lede { font-size: 20px; line-height: 1.5; color: var(--body-text-color-subdued); inline-size: min(760px, 100%); margin: 0; }
.alg-hero .alg-grad, .alg-duel .hero-num { color: #A78BFA; }
@supports ((-webkit-background-clip: text) or (background-clip: text)) {
  .alg-hero .alg-grad, .alg-duel .hero-num { background: linear-gradient(100deg, #7C5CFA, #3B82F6); -webkit-background-clip: text; background-clip: text; color: transparent; }
}
.alg-hero .alg-badge-row, .alg-gov .alg-badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 4px; }
.alg-hero .alg-badge, .alg-gov .alg-badge { font-family: var(--font-mono); font-size: 12px; color: var(--body-text-color-subdued); border: 1px solid var(--border-color-primary); border-radius: 999px; padding: 4px 12px; }
.alg-hero .alg-badge-ok, .alg-gov .alg-badge-ok { color: #34D399; border-color: rgba(52,211,153,0.35); }
.alg-hero .alg-badge-warn, .alg-gov .alg-badge-warn { color: #FBBF24; border-color: rgba(251,191,36,0.35); }
.alg-section { margin-top: 20px; }
.alg-section .alg-section-rule { width: 32px; height: 4px; border-radius: 2px; margin-bottom: 12px; background: linear-gradient(90deg, #7C5CFA, #3B82F6); }
.alg-section h2 { font-size: 26px; letter-spacing: -0.02em; font-weight: 650; margin: 0 0 6px; }
.alg-section .alg-section-sub { font-size: 14px; color: var(--body-text-color-subdued); inline-size: min(780px, 100%); margin: 0; }
.alg-footer { border-top: 1px solid var(--border-color-primary); margin-top: 48px; padding-top: 20px; font-size: 13px; color: var(--body-text-color-subdued); line-height: 1.7; }
.alg-footer a { color: var(--body-text-color); text-decoration: none; }
"""

# ---------------------------------------------------------------------------
# 3 · COMPONENT_CSS — styles for OUR OWN HTML payloads only (the classes
# inside gr.HTML strings: arena duel cards, metric strip, product map,
# wave-3 cards, MCP category cells, verdicts). Never a Gradio selector.
# ---------------------------------------------------------------------------

COMPONENT_CSS = r"""
/* metric strip (Overview) */
.alg-metrics { display: grid; gap: 12px; margin: 20px 0 4px; grid-template-columns: repeat(5, minmax(0, 1fr)); }
@media (width <= 1020px) { .alg-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (width <= 640px) { .alg-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.alg-metric { background: #12121A; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 16px; }
.alg-metric .alg-metric-value { font-family: var(--font-mono); font-size: 36px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.05; text-align: right; font-variant-numeric: tabular-nums; }
.alg-metric .alg-metric-value.alg-grad { color: #A78BFA; }
@supports ((-webkit-background-clip: text) or (background-clip: text)) {
  .alg-metric .alg-metric-value.alg-grad { background: linear-gradient(100deg, #7C5CFA, #3B82F6); -webkit-background-clip: text; background-clip: text; color: transparent; }
}
.alg-metric .alg-metric-label { font-size: 12px; color: #9CA3AF; margin-top: 8px; line-height: 1.45; text-align: right; }
/* product map (Overview) */
.alg-map { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 16px; }
@media (width <= 900px) { .alg-map { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (width <= 520px) { .alg-map { grid-template-columns: 1fr; } }
.alg-map-node { background: #12121A; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 16px; }
.alg-map-step { font-family: var(--font-mono); font-size: 12px; color: #6B7280; margin-bottom: 8px; }
.alg-map-name { font-size: 16px; font-weight: 650; letter-spacing: -0.01em; margin-bottom: 6px; }
.alg-map-desc { font-size: 12px; color: #9CA3AF; line-height: 1.55; }
/* generic payload cards (wave-3, MCP categories) */
.alg-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (width <= 720px) { .alg-grid { grid-template-columns: 1fr; } }
.alg-grid-3 { display: grid; gap: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
@media (width <= 940px) { .alg-grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (width <= 640px) { .alg-grid-3 { grid-template-columns: 1fr; } }
.alg-card { background: #12121A; border: 1px solid rgba(255,255,255,0.06); border-radius: 14px; padding: 16px; }
.alg-pkg-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.alg-pkg-name { font-size: 16px; font-weight: 650; letter-spacing: -0.01em; }
.alg-kernel-speed { font-family: var(--font-mono); font-size: 20px; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; }
.alg-card .alg-grad { color: #A78BFA; }
@supports ((-webkit-background-clip: text) or (background-clip: text)) {
  .alg-card .alg-grad { background: linear-gradient(100deg, #7C5CFA, #3B82F6); -webkit-background-clip: text; background-clip: text; color: transparent; }
}
.alg-kernel-target { font-size: 12px; color: #9CA3AF; margin-top: 6px; }
.alg-status { font-family: var(--font-mono); font-size: 11px; border-radius: 999px; padding: 2px 8px; border: 1px solid rgba(255,255,255,0.06); color: #9CA3AF; }
.alg-status-wave { color: #FBBF24; border-color: rgba(251,191,36,0.35); }
.alg-cat { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px 14px; }
.alg-cat-name { font-size: 14px; font-weight: 600; }
.alg-cat-count { font-family: var(--font-mono); font-size: 14px; color: #9CA3AF; font-variant-numeric: tabular-nums; }
/* duel result cards (rendered by arena/card.py — markup kept verbatim) */
.duel-card { border: 1px solid rgba(124,92,250,0.4); border-radius: 14px; padding: 18px 20px; background: #12121A; }
.duel-card.placeholder { background: #0D0D14; white-space: pre-wrap; font-family: var(--font-mono); font-size: 13px; border-color: rgba(255,255,255,0.06); }
.duel-card.warn { border-color: rgba(251,191,36,0.5); }
.duel-card.error { border-color: rgba(248,113,113,0.5); }
.duel-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.duel-title { font-size: 20px; font-weight: 650; letter-spacing: -0.02em; }
.duel-sub { font-size: 12px; color: #9CA3AF; margin-top: 4px; font-family: var(--font-mono); }
.hero { text-align: right; }
.hero-num { font-family: var(--font-mono); font-size: 40px; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
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
.card-reason { font-size: 14px; font-weight: 600; margin: 10px 0; color: #FBBF24; }
.duel-card.error .card-reason { color: #F87171; }
/* governed verdicts + small payload utilities */
.alg-verdict { font-size: 14px; font-weight: 600; padding: 12px 16px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.06); background: #12121A; }
.alg-verdict.ok { color: #34D399; border-color: rgba(52,211,153,0.35); }
.alg-verdict.deny { color: #FBBF24; border-color: rgba(251,191,36,0.35); }
.alg-mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.alg-section-sub { font-size: 14px; color: #9CA3AF; inline-size: min(780px, 100%); }
.alg-section-sub a { color: #A5B4FC; }
"""


# Count-up for hero metric numbers.
# Elements: <span class="alg-count" data-target="643">. When the element
# appears (or data-target changes), animate to the target in <300ms.
# Respects prefers-reduced-motion. Runs from <head>, observer-based so it
# works with Gradio's async rendering and later value updates.
COUNTUP_JS = r"""
<script>
(function () {
  var REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DURATION = 280;

  function fmt(n) {
    try { return n.toLocaleString("en-US"); } catch (e) { return String(n); }
  }

  function animate(el) {
    var target = parseFloat(el.getAttribute("data-target"));
    if (!isFinite(target)) return;
    if (el.getAttribute("data-counted") === String(target)) return;
    el.setAttribute("data-counted", String(target));
    if (REDUCED) { el.textContent = fmt(target); return; }
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / DURATION);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(Math.round(target * eased));
      if (p < 1) window.requestAnimationFrame(step);
      else el.textContent = fmt(target);
    }
    window.requestAnimationFrame(step);
  }

  function scan(root) {
    var els = (root || document).querySelectorAll
      ? (root || document).querySelectorAll(".alg-count[data-target]")
      : [];
    for (var i = 0; i < els.length; i++) animate(els[i]);
  }

  function boot() {
    scan(document);
    var obs = new MutationObserver(function (muts) {
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === "attributes" && m.target && m.target.classList &&
            m.target.classList.contains("alg-count")) { animate(m.target); }
        for (var j = 0; j < m.addedNodes.length; j++) {
          var n = m.addedNodes[j];
          if (n && n.nodeType === 1) {
            if (n.classList && n.classList.contains("alg-count")) animate(n);
            scan(n);
          }
        }
      }
    });
    obs.observe(document.body, { childList: true, subtree: true,
                                 attributes: true, attributeFilter: ["data-target"] });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else { boot(); }
})();
</script>
"""


# Force dark mode. On a light-mode OS Gradio's :root keeps light surface
# tokens while our text tokens are light-on-dark, yielding white panels with
# invisible text; the brand is dark-only, so pin the `dark` class at boot.
# Passed to launch(js=...), which Gradio 6 runs on page load.
FORCE_DARK_JS = "() => { document.documentElement.classList.add('dark'); }"
