"""canonical fleet shell — copied verbatim into every thyn-ai Space; change = change all six.

One header, one footer, one stylesheet for the whole Algenta fleet on
Hugging Face. Every Space renders the SAME chrome from this module:

* render_header(title, tagline, badges=None, active=None) — eyebrow, H1,
  tagline, optional badge pills, and the sister-nav (identical link set
  everywhere, rendered once from SISTER_NAV; the current Space's own entry
  is dimmed text, not a link, via `active`).
* render_footer() — hairline top rule, brand left, fleet links right.
* SHELL_CSS — styles the `alg-shell-*` classes ONLY: payload CSS for our
  own gr.HTML markup. No Gradio selectors, no `!important`; colors come
  from var() theme tokens (plus the pinned fleet accents #A78BFA / #34D399
  / #FBBF24) so the chrome stays correct if THEME changes.

Stdlib only — this file must never import a Space-specific module.
"""

from __future__ import annotations

import html

# ---------------------------------------------------------------------------
# Fleet link constants — the same for every Space, forever.
# ---------------------------------------------------------------------------

SISTER_NAV = [
    ("Speed Arena", "https://huggingface.co/spaces/thyn-ai/algenta-speed-arena"),
    ("LLM Agents lab", "https://huggingface.co/spaces/thyn-ai/algenta-for-llm-agents"),
    ("LLM modules live", "https://huggingface.co/spaces/thyn-ai/algenta-llm-modules"),
    ("Governed tool calls", "https://huggingface.co/spaces/thyn-ai/algenta-governed-tool-calls"),
    ("Governed agent", "https://huggingface.co/spaces/thyn-ai/algenta-governed-agent"),
    ("kernels", "https://github.com/thyn-ai/mojo-kernels"),
    ("SDK", "https://github.com/thyn-ai/algenta-sdk"),
]

FOOTER_LINKS = [
    ("algenta.ai", "https://algenta.ai"),
    ("docs.algenta.ai", "https://docs.algenta.ai"),
    ("github.com/thyn-ai", "https://github.com/thyn-ai"),
    ("Hugging Face", "https://huggingface.co/thyn-ai"),
]

_BADGE_VARIANTS = ("", "ok", "warn")
_SEP = '<span class="alg-shell-sep">·</span>'


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def _badge_html(badge) -> str:
    """One pill. `badge` is plain text (neutral) or a (text, variant) tuple."""
    if isinstance(badge, tuple):
        text, variant = badge
    else:
        text, variant = badge, ""
    if variant not in _BADGE_VARIANTS:
        raise ValueError(f"unknown badge variant {variant!r}; expected one of {_BADGE_VARIANTS}")
    cls = "alg-shell-badge" + (f" alg-shell-badge-{variant}" if variant else "")
    return f'<span class="{cls}">{_esc(text)}</span>'


def _nav_html(active: str | None) -> str:
    items = []
    for label, url in SISTER_NAV:
        if label == active:
            items.append(f'<span class="alg-shell-nav-active">{_esc(label)}</span>')
        else:
            items.append(f'<a class="alg-shell-nav-link" href="{url}">{_esc(label)}</a>')
    return (
        '<nav class="alg-shell-nav">'
        f'<span class="alg-shell-nav-links">{_SEP.join(items)}</span>'
        '<span class="alg-shell-attribution">attribution: Algenta</span>'
        "</nav>"
    )


def render_header(title, tagline, badges=None, active=None) -> str:
    """The canonical fleet header, identical on every Space except the text.

    badges: iterable of plain strings (neutral pills) or (text, variant)
    tuples with variant "ok" (live/verified claims) or "warn" (simulated or
    otherwise qualified claims). active: this Space's own SISTER_NAV label,
    rendered as dimmed text instead of a link; None on the flagship.
    """
    if active is not None and active not in {label for label, _ in SISTER_NAV}:
        raise ValueError(f"active {active!r} is not a SISTER_NAV label")
    parts = [
        '<header class="alg-shell-header">',
        '<div class="alg-shell-eyebrow">ALGENTA</div>',
        f'<h1 class="alg-shell-title">{_esc(title)}</h1>',
        f'<p class="alg-shell-tagline">{_esc(tagline)}</p>',
    ]
    if badges:
        pills = "".join(_badge_html(b) for b in badges)
        parts.append(f'<div class="alg-shell-badges">{pills}</div>')
    parts.append(_nav_html(active))
    parts.append("</header>")
    return "".join(parts)


def render_footer() -> str:
    """The canonical fleet footer — identical on every Space, no parameters."""
    links = _SEP.join(
        f'<a class="alg-shell-footer-link" href="{url}">{_esc(label)}</a>'
        for label, url in FOOTER_LINKS
    )
    return (
        '<footer class="alg-shell-footer">'
        '<span class="alg-shell-footer-brand">Algenta</span>'
        f'<span class="alg-shell-footer-links">{links}</span>'
        "</footer>"
    )


# ---------------------------------------------------------------------------
# SHELL_CSS — alg-shell-* classes only. Payload CSS for our own gr.HTML
# markup: no Gradio selectors, no !important. Theme colors come from var()
# tokens so the chrome tracks THEME; #A78BFA / #34D399 / #FBBF24 are the
# pinned fleet accents (same values as every Space's payload CSS).
# Layout metrics are part of the fleet contract: header padding 28px 0 12px,
# nav margin 12px 0 0, footer margin-top 40px / padding-top 16px.
#
# Specificity: every selector repeats its class 4× (0,4,0). Gradio 6 scopes
# its resets and prose typography under `.gradio-container-<version>` (up to
# (0,3,1), e.g. `.gradio-container-6-28-0 .prose h1`), which silently beats
# single-class payload rules on frontends that serve the launch css verbatim
# (the HF gradio-SDK runner; the docker frontend auto-prefixes custom css and
# is unaffected either way). The 4× chain wins on every frontend using only
# our own classes — no !important, no version-coupled selectors.
# ---------------------------------------------------------------------------

SHELL_CSS = r"""
.alg-shell-header.alg-shell-header.alg-shell-header.alg-shell-header { padding: 28px 0 12px; }
.alg-shell-eyebrow.alg-shell-eyebrow.alg-shell-eyebrow.alg-shell-eyebrow { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #A78BFA; margin: 0 0 10px; }
.alg-shell-title.alg-shell-title.alg-shell-title.alg-shell-title { font-size: 30px; line-height: 1.2; letter-spacing: -0.02em; font-weight: 700; color: var(--body-text-color); margin: 0 0 8px; }
.alg-shell-tagline.alg-shell-tagline.alg-shell-tagline.alg-shell-tagline { font-size: 15px; line-height: 1.5; color: var(--body-text-color-subdued); inline-size: min(78ch, 100%); margin: 0; }
.alg-shell-badges.alg-shell-badges.alg-shell-badges.alg-shell-badges { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0 0; }
.alg-shell-badge.alg-shell-badge.alg-shell-badge.alg-shell-badge { font-family: var(--font-mono); font-size: 12px; color: var(--body-text-color-subdued); border: 1px solid var(--border-color-primary); border-radius: 999px; padding: 4px 12px; }
.alg-shell-badge-ok.alg-shell-badge-ok.alg-shell-badge-ok.alg-shell-badge-ok { color: #34D399; border-color: rgba(52,211,153,0.35); }
.alg-shell-badge-warn.alg-shell-badge-warn.alg-shell-badge-warn.alg-shell-badge-warn { color: #FBBF24; border-color: rgba(251,191,36,0.35); }
.alg-shell-nav.alg-shell-nav.alg-shell-nav.alg-shell-nav { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 6px 16px; margin: 12px 0 0; font-size: 13px; }
.alg-shell-nav-links.alg-shell-nav-links.alg-shell-nav-links.alg-shell-nav-links { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; }
.alg-shell-nav-link.alg-shell-nav-link.alg-shell-nav-link.alg-shell-nav-link { color: var(--body-text-color); text-decoration: none; padding: 0; }
.alg-shell-nav-link.alg-shell-nav-link.alg-shell-nav-link.alg-shell-nav-link:hover { text-decoration: underline; }
.alg-shell-nav-active.alg-shell-nav-active.alg-shell-nav-active.alg-shell-nav-active { color: var(--body-text-color-subdued); }
.alg-shell-sep.alg-shell-sep.alg-shell-sep.alg-shell-sep { color: var(--body-text-color-subdued); }
.alg-shell-attribution.alg-shell-attribution.alg-shell-attribution.alg-shell-attribution { color: var(--body-text-color-subdued); }
.alg-shell-footer.alg-shell-footer.alg-shell-footer.alg-shell-footer { border-top: 1px solid var(--border-color-primary); margin-top: 40px; padding-top: 16px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 6px 16px; font-size: 13px; color: var(--body-text-color-subdued); }
.alg-shell-footer-brand.alg-shell-footer-brand.alg-shell-footer-brand.alg-shell-footer-brand { font-weight: 600; color: var(--body-text-color); }
.alg-shell-footer-links.alg-shell-footer-links.alg-shell-footer-links.alg-shell-footer-links { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; }
.alg-shell-footer .alg-shell-footer-link.alg-shell-footer-link.alg-shell-footer-link.alg-shell-footer-link { color: var(--body-text-color); text-decoration: none; padding: 0; }
.alg-shell-footer .alg-shell-footer-link.alg-shell-footer-link.alg-shell-footer-link.alg-shell-footer-link:hover { text-decoration: underline; }
"""
