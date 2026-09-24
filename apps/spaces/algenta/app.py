"""Algenta — the flagship Space: one shell around six tabs, everything measured before launch.

What this module owns is the page, not the numbers: the shared header and footer
(`algenta_spaces.shell`), the token set and theme (`algenta_spaces.design`), the tab strip
(`tabs/<id>_tab.py`, each exposing `build(deps) -> TabSpec`), the permalink row, the boot
disclosure, and the two JSON routes beside Gradio — `/health` (the boot snapshot plus what the
page runs on) and `/api/status` (the compact record another Space's tile reads). Boot itself is
`boot_sequence.run_boot()`, which warms every Hub kernel and measures the opening card before
the server takes its first request.

Import order: the user-agent shim (`hf_ua_shim`) loads before anything that imports `kernels`.
The shared package is vendored next to this file by `tools/stage.py`; a local run finds it in
`apps/spaces/_shared` instead. The server is uvicorn over `gr.mount_gradio_app`, so the routes
and the Gradio app share one process and one port, with `mcp_server=True`, `footer_links=[]`,
the theme, the stylesheet and the boot hold (`head=`) passed at mount time (Gradio 6) and the
queue configured from `lane.gradio_hooks()` — one native call at a time.

First paint (`BOOT_HEAD`, `REVEAL_JS`): Gradio paints its own splash, then the components with
the first tab selected, then the load handler switches to the tab the permalink names and the
web fonts land — three visible layout shifts. The head fragment adds `alg-booting` to `<html>`
the moment Gradio injects it (before any component mounts) and keeps the body invisible;
`on_load` is chained with a client-side step that removes the class once the strip shows the
requested tab and `document.fonts` has settled, two frames later, so the page appears once, in
its final layout. Both paths are bounded: the reveal step gives up after `REVEAL_TIMEOUT_MS`
and the head fragment itself removes the class after `BOOT_HOLD_MAX_MS` even if the load
handler never answers.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections.abc import Collection, Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
SHARED_DIR = APP_DIR.parent / "_shared"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if not (APP_DIR / "algenta_spaces").is_dir() and (SHARED_DIR / "algenta_spaces").is_dir():
    sys.path.insert(0, str(SHARED_DIR))

import hf_ua_shim  # noqa: E402 - applied before anything that imports `kernels`

hf_ua_shim.apply()

from algenta_spaces import design, fleet_css, hubkernel, shell  # noqa: E402
from algenta_spaces.bench import STATUS_MEASURED  # noqa: E402
from algenta_spaces.cards import render_unavailable_card  # noqa: E402
from algenta_spaces.css import block, rule, stylesheet  # noqa: E402
from algenta_spaces.lane import gradio_hooks  # noqa: E402

import boot_sequence  # noqa: E402
import permalink  # noqa: E402
import webhook  # noqa: E402
from tabs import LOAD_HOOKS, TAB_GOV, TAB_IDS, TabSpec, common  # noqa: E402

log = logging.getLogger("algenta.flagship")

TITLE = "Algenta"
SUBLINE = "Mojo kernels running on this machine. Race them against Python."
LABEL_PERMALINK = "Permalink"
LABEL_BOOT = "How this booted"
LABEL_TABS = "Tabs"
HEALTH_PATH = "/health"
STATUS_PATH = "/api/status"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 7860
CODE_TAB_UNAVAILABLE = "tab_unavailable"

#: `tabs/<id>_tab.py` per tab id; a module absent from the build renders the unavailable card.
TAB_MODULES: Mapping[str, str] = {tab: f"tabs.{tab}_tab" for tab in TAB_IDS}
#: Labels for a tab whose module is absent (the modules carry their own labels otherwise).
TAB_LABELS: Mapping[str, str] = {
    "try": "Try it",
    "play": "Playground",
    "race": "Races",
    "llm": "LLM kernels",
    "gov": "Governed",
    "eco": "Ecosystem",
}
#: The optional permalink protocol a tab module may implement (see `docs/spaces/FLAGSHIP.md`):
#: the components a page load writes into, the values for them together with the tab's report
#: of what it applied, and — the third, optional function — the same report as a pure
#: function. The shell writes the link box from that report alone, so a link never promises a
#: state the tab did not restore; a tab that reports nothing gets `?tab=<id>` and nothing more.
PERMALINK_OUTPUTS = "permalink_outputs"
PERMALINK_RESTORE = "permalink_restore"
PERMALINK_APPLIED = "permalink_applied"
#: `permalink_restore` may answer with a mapping: the values (one per output) under one of
#: these keys and the report under `RESTORE_APPLIED_KEY` — `{"fn": …, "args": …}`, a
#: `(fn, args)` pair or None. A bare list of values is the older shape and reports nothing.
RESTORE_VALUES_KEYS: tuple[str, ...] = ("values", "outputs")
RESTORE_APPLIED_KEY = "applied"
#: The shell's own components, offered to every tab's `connect(gr, tabs, handles)` under this key:
#: `permalink` is the link box, so a tab that switches the strip itself (the Try tab's "Race it"
#: chip) can rewrite the link in the same event — a programmatic switch fires no strip event.
SHELL_HANDLE = "shell"
#: Text after the family count in the header pill: the count is this container's, not the Hub's.
PILL_WHERE = "this container"
PILL_FLOOR = "host below the published floor"

# ---------------------------------------------------------------------------
# First paint: hold the page until the load handler has selected the tab
# ---------------------------------------------------------------------------

#: The class on `<html>` while the page is held; the audit and the goldens wait for it to go.
BOOTING_CLASS = "alg-booting"
#: The reveal step stops waiting for the strip and the fonts after this long.
REVEAL_TIMEOUT_MS = 1500
#: The head fragment lifts the hold on its own after this long, whatever the load handler did.
BOOT_HOLD_MAX_MS = 4000
BOOT_CSS = f"html.{BOOTING_CLASS} body {{ visibility: hidden; }}"
BOOT_SCRIPT = (
    "(function () {"
    " var root = document.documentElement;"
    f" root.classList.add('{BOOTING_CLASS}');"
    f" window.setTimeout(function () {{ root.classList.remove('{BOOTING_CLASS}'); }},"
    f" {BOOT_HOLD_MAX_MS});"
    " })();"
)
#: Gradio injects this fragment into `<head>` before the components mount (`head=` at mount);
#: the shell's row marker rides along so a wrapped nav row never opens with the separator.
BOOT_HEAD = f"<style>{BOOT_CSS}</style><script>{BOOT_SCRIPT}</script>{shell.NAV_ROWS_HEAD}"
#: Chained after `on_load` on the client: reveal when the strip shows the requested tab and the
#: fonts have settled, two animation frames later (Svelte has flushed the panel by then).
REVEAL_JS = (
    "() => {"
    " const root = document.documentElement;"
    " let want = new URLSearchParams(window.location.search).get('tab');"
    " if (want !== null && document.querySelector('[role=tab][data-tab-id=\"'"
    " + CSS.escape(want) + '\"]') === null) { want = null; }"
    " const selected = () => {"
    "  const tab = document.querySelector('[role=tab][aria-selected=true]');"
    "  return want === null || (tab !== null && tab.getAttribute('data-tab-id') === want);"
    " };"
    " const started = performance.now();"
    f" const reveal = () => root.classList.remove('{BOOTING_CLASS}');"
    " const tick = () => {"
    "  const settled = selected() && document.fonts.status === 'loaded';"
    f"  if (settled || performance.now() - started > {REVEAL_TIMEOUT_MS}) {{"
    "   requestAnimationFrame(() => requestAnimationFrame(reveal));"
    "  } else { requestAnimationFrame(tick); }"
    " };"
    " tick();"
    " }"
)


# ---------------------------------------------------------------------------
# Copy computed from facts
# ---------------------------------------------------------------------------


#: One truth for every count the shell prints — `boot_sequence` computes it from what loaded in
#: this container (`functions_loaded`, `families_loaded`, `families_published`), and the Hub
#: tile and the boot card read the same record, so a lost family lowers the number everywhere.
headline = boot_sequence.headline


_TIER_RE = re.compile(r"^([a-z]\d+[a-z]?)(?:x(\d+))?(?:-(small|medium|large|largex\d+))?$")


def tier_label(tier: str) -> str:
    """The Hub hardware flavour in words: `cpu-upgrade` → `CPU upgrade`, `l4x4` → `4× L4 GPU`,
    `a10g-large` → `A10G GPU · large`, `zero-a10g` → `ZeroGPU A10G`; empty stays empty."""
    value = tier.strip().lower()
    if not value:
        return ""
    if value.startswith("cpu-"):
        return "CPU " + value[4:].replace("-", " ")
    if value.startswith("zero-"):
        return "ZeroGPU " + value[5:].upper()
    match = _TIER_RE.match(value)
    if match is None:
        return value.replace("-", " ")
    chip, count, size = match.groups()
    label = f"{count}× {chip.upper()} GPU" if count and count != "1" else f"{chip.upper()} GPU"
    if size:
        label += " · " + size.replace("largex", "large ×")
    return label


def badges(state: boot_sequence.BootState) -> list[tuple[str, str]]:
    """The header pills, in words a visitor reads: how many of the published kernel families
    are warm in this container (amber when one is missing), the hardware tier, the floor
    verdict. No build-variant string, no revision, no timing: the boot disclosure carries those
    (`shell.machine_token` is the rule; the tests hold every pill to it)."""
    pills: list[tuple[str, str]] = []
    facts = state.facts
    if facts.get("families_loaded") is not None:
        loaded = boot_sequence.families_loaded(facts)
        published = boot_sequence.families_published(facts)
        if loaded < published:
            noun = "Mojo kernel family" if published == 1 else "Mojo kernel families"
            pills.append((f"{loaded} of {published} {noun} · {PILL_WHERE}", "warn"))
        else:
            noun = "Mojo kernel family" if loaded == 1 else "Mojo kernel families"
            pills.append((f"{loaded} {noun} · {PILL_WHERE}", ""))
    tier = tier_label(state.env.get("SPACE_HARDWARE", ""))
    if tier:
        pills.append((tier, ""))
    if not state.floor_ok:
        pills.append((PILL_FLOOR, "warn"))
    return pills


def known_functions(state: boot_sequence.BootState) -> frozenset[str]:
    """Every `module.function` a loaded family serves here (excluded functions removed)."""
    names: set[str] = set()
    for loaded in state.kernels.values():
        if loaded.is_umbrella and len(state.kernels) > 1:
            continue  # its modules are the members', already counted
        try:
            described = hubkernel.describe(loaded)
        except hubkernel.HubKernelError as exc:
            log.warning("%s: contract not described (%s)", loaded.family, exc.code)
            continue
        for module_name, module in described["modules"].items():
            names.update(f"{module_name}.{fn}" for fn in module.get("functions", {}))
    return frozenset(names)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


def unavailable_spec(tab_id: str, hint: str) -> TabSpec:
    """A tab whose module is not in this build: the unavailable card with a code, no controls."""
    label = TAB_LABELS[tab_id]
    card = render_unavailable_card(title=label, error_code=CODE_TAB_UNAVAILABLE, hint=hint)

    def render(gr: Any) -> dict[str, Any]:
        return {"card": gr.HTML(card)}

    return TabSpec(tab_id, label, render, ())


def load_tab_module(tab_id: str) -> Any | None:
    """The tab's module, or None when exactly that module is absent (other errors propagate)."""
    name = TAB_MODULES[tab_id]
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise
        log.warning("%s is not part of this build", name)
        return None


def build_spec(tab_id: str, state: boot_sequence.BootState, module: Any | None) -> TabSpec:
    if module is None:
        return unavailable_spec(tab_id, f"{TAB_MODULES[tab_id]} is not part of this build.")
    deps = state.deps()
    if tab_id == TAB_GOV:
        return module.build(deps, hosted=state.hosted, hook=state.hook, status=state.hosted_status)
    return module.build(deps)


def load_tabs(state: boot_sequence.BootState) -> tuple[list[TabSpec], dict[str, Any]]:
    """Every tab in strip order, plus the modules that exist (for CSS and permalink restore)."""
    specs: list[TabSpec] = []
    modules: dict[str, Any] = {}
    for tab_id in TAB_IDS:
        module = load_tab_module(tab_id)
        if module is not None:
            modules[tab_id] = module
        specs.append(build_spec(tab_id, state, module))
    return specs, modules


def module_css(module: Any) -> str:
    """Every module-level `*_CSS` string a tab module declares, in name order."""
    return "\n".join(
        str(getattr(module, name))
        for name in sorted(dir(module))
        if name.endswith("_CSS") and isinstance(getattr(module, name), str)
    )


# alg-page / alg-tabs / alg-permalink-row / alg-boot-disclosure classes only; tokens from
# design.py; 8-pt spacing. Every control's size, colour and focus ring comes from the shared
# chrome sheet (`algenta_spaces.css.CHROME_CSS`, part of `fleet_css()`), so this sheet is the
# page's width and the rhythm between the shell's blocks, nothing else. On a phone the page
# column pulls 16 px back into the 32 px Gradio pads around it (the column's used width is
# pinned by its parent, so the width is set with the margin) and drops its own 16 px padding,
# so the side gutter is the design's 16 px (`design.PHONE_GUTTER`) without a Gradio selector.
#: The header and footer `gr.HTML` blocks: Gradio pads an HTML block's container 16 px, which put
#: the shell 16 px inside the card column at every viewport (launch review round 3); the card
#: blocks already zero it (`common.TABS_CSS`), the shell blocks do the same here.
SHELL_BLOCK_CLASS = "alg-shell-block"

APP_CSS = stylesheet(
    rule("alg-page", "max-width: var(--alg-content-max); margin: 0 auto; padding: 0 16px 48px;"),
    rule(SHELL_BLOCK_CLASS, "padding: 0;"),
    rule(SHELL_BLOCK_CLASS, "padding: 0;", suffix=" > div"),
    rule("alg-tabs", "margin: 24px 0 0;"),
    rule("alg-permalink-row", "margin: 24px 0 0;"),
    rule("alg-boot-disclosure", "margin: 16px 0 0;"),
    block(
        f"@media (width <= {design.PHONE_MAX_WIDTH}px)",
        rule(
            "alg-page",
            f"margin: 0 -{design.PHONE_GUTTER}px; width: calc(100% + {2 * design.PHONE_GUTTER}px);"
            " padding: 0 0 48px;",
        ),
    ),
)


def page_css(modules: Mapping[str, Any]) -> str:
    """Tokens, base type, shell, cards, boot, the shared tab helpers, each tab's CSS, the page."""
    parts = [fleet_css(), common.TABS_CSS]
    parts += [module_css(module) for _, module in sorted(modules.items())]
    parts.append(APP_CSS)
    return "\n".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def _tab_from_select(value: Any, labels: Mapping[str, str]) -> str:
    """The tab id behind a select event, whose value is the label (or, on some builds, the id)."""
    text = str(value)
    if text in TAB_IDS:
        return text
    return labels.get(text, TAB_IDS[0])


def applied_link(
    link: permalink.Permalink,
    applied_fn: Any,
    known: Collection[str],
    *,
    module: str = "",
) -> permalink.Permalink:
    """What a tab may be handed of `link`: the tab's own answer when it implements
    `permalink_applied(fn, args) -> (fn, args) | None`, else the shell's ceiling — a function
    only when a loaded family serves it, arguments only beside such a function or without any
    (`permalink.restorable`). This bounds what reaches `permalink_restore`; what the box shows
    is the tab's report (`report_of`), never this guess."""
    if callable(applied_fn):
        answer = applied_fn(link.fn, link.args)
        if answer is None:
            return permalink.Permalink(link.tab)
        try:
            fn, args = answer
        except (TypeError, ValueError):
            raise ValueError(
                f"{module}.{PERMALINK_APPLIED} must return (fn, args) or None, got {answer!r}"
            ) from None
        return permalink.Permalink(link.tab, permalink.parse_fn(fn), dict(args) if args else None)
    return permalink.restorable(link, known_functions=known)


#: `report_of` returns this when the tab's answer carried no report at all.
NOT_REPORTED = object()


def report_of(tab: str, report: Any) -> permalink.Permalink:
    """The link a tab's report of what it applied allows: `None` (nothing), a mapping with `fn`
    and `args`, a `(fn, args)` pair or anything with `.fn` / `.args`. The function must be a
    dotted name, the arguments a non-empty mapping; anything else is dropped field by field."""
    if report is None:
        return permalink.Permalink(tab)
    if isinstance(report, Mapping):
        fn, args = report.get("fn"), report.get("args")
    elif isinstance(report, tuple | list) and len(report) == 2:
        fn, args = report
    elif hasattr(report, "fn") and hasattr(report, "args"):
        fn, args = report.fn, report.args
    else:
        raise ValueError(f"a permalink report is (fn, args), a mapping or None, got {report!r}")
    if fn is not None and not isinstance(fn, str):
        fn = None
    args = dict(args) if isinstance(args, Mapping) and args else None
    return permalink.Permalink(tab, permalink.parse_fn(fn), args)


def restore_answer(
    tab: str, answer: Any, components: int, *, module: str = ""
) -> tuple[list[Any], permalink.Permalink | Any]:
    """`(values, report)` from what `permalink_restore` returned: a mapping carries the values
    under `values` (or `outputs`) and the report under `applied`; an object with those two
    attributes the same; a bare sequence is the older shape — the values alone, `NOT_REPORTED`.
    The values are checked against the number of components."""
    report: Any = NOT_REPORTED
    if isinstance(answer, Mapping):
        values = next((answer[k] for k in RESTORE_VALUES_KEYS if k in answer), None)
        if values is None:
            raise ValueError(
                f"{module}.{PERMALINK_RESTORE} returned a mapping without"
                f" {' or '.join(RESTORE_VALUES_KEYS)}"
            )
        if RESTORE_APPLIED_KEY in answer:
            report = report_of(tab, answer[RESTORE_APPLIED_KEY])
    elif hasattr(answer, "values") and hasattr(answer, "applied") and not isinstance(answer, str):
        values = answer.values() if callable(answer.values) else answer.values
        report = report_of(tab, answer.applied)
    else:
        values = answer
    if isinstance(values, str | bytes) or not isinstance(values, Sequence | Collection):
        raise ValueError(f"{module}.{PERMALINK_RESTORE} must return one value per component")
    values = list(values)
    if len(values) != components:
        raise ValueError(
            f"{module}.{PERMALINK_RESTORE} returned {len(values)} values"
            f" for {components} components"
        )
    return values, report


def build_blocks(
    state: boot_sequence.BootState,
    *,
    space_id: str | None = None,
    stamp: str | None = None,
    specs: Sequence[TabSpec] | None = None,
    modules: Mapping[str, Any] | None = None,
) -> tuple[Any, list[TabSpec], dict[str, Any]]:
    """The Gradio Blocks: header, tab strip, permalink row, boot disclosure, footer.

    `specs` and `modules` default to `load_tabs(state)`; tests pass fakes. Returns the Blocks,
    the specs in strip order and the modules used, so the caller can build the stylesheet.
    """
    import gradio as gr

    if specs is None or modules is None:
        loaded_specs, loaded_modules = load_tabs(state)
        specs = loaded_specs if specs is None else specs
        modules = loaded_modules if modules is None else modules
    header = shell.render_header(
        headline(state.facts), SUBLINE, badges(state), active="Flagship", space_id=space_id
    )
    footer = shell.render_footer(active="Flagship", stamp=stamp)
    base = permalink.public_base(state.env)
    labels = {spec.label: spec.id for spec in specs}
    handles: dict[str, Any] = {}
    hooks = gradio_hooks()

    # No `fill_width`: Gradio 6 paints its splash in the default 1,280 px centred container and
    # adds the fill_width class only when the app config arrives (~1.6 s on the Space) — after the
    # first paint, and before the `head=` fragment (also client-injected at that moment) can hold
    # the page — so the whole page jumped 80 px at 1440 (CLS 0.0556 on every desktop load). Our
    # content is `.alg-page`, 1,120 px centred: identical geometry inside 1,280 or 1,440.
    with gr.Blocks(title=TITLE) as blocks:
        # Built first so the tabs can name it in their own events; drawn in the row below.
        link_box = gr.Textbox(
            value=permalink.build(TAB_IDS[0], base=base),
            label=LABEL_PERMALINK,
            interactive=False,
            buttons=[],
            elem_classes=["alg-permalink"],
            render=False,
        )
        handles[SHELL_HANDLE] = {"permalink": link_box, "base": base}
        with gr.Column(elem_classes=["alg-page"]):
            gr.HTML(header, elem_classes=[SHELL_BLOCK_CLASS])
            strip = gr.Tabs(elem_id="alg-tabs", elem_classes=["alg-tabs"], selected=TAB_IDS[0])
            with strip as tabs:
                for spec in specs:
                    with gr.Tab(spec.label, id=spec.id):
                        handles[spec.id] = spec.render(gr) or {}
            for spec in specs:
                if spec.connect is not None:
                    spec.connect(gr, tabs, handles)
            for spec in specs:
                for fn, outputs in handles[spec.id].get(LOAD_HOOKS, ()):
                    blocks.load(fn, None, outputs, api_name=False)
            with gr.Row(elem_classes=["alg-permalink-row"]):
                link_box.render()
            with gr.Row(elem_classes=["alg-copy-row"]):
                link_copy = gr.Button(
                    common.LABEL_COPY, variant="secondary", elem_classes=["alg-chip-btn"], scale=0
                )
            with gr.Accordion(
                LABEL_BOOT, open=False, elem_classes=["alg-disclosure", "alg-boot-disclosure"]
            ):
                boot_card = gr.HTML(state.registry.render_html())
            gr.HTML(footer, elem_classes=[SHELL_BLOCK_CLASS])
        # The boot card is re-rendered from the registry on every page load, so a stage detail
        # that changes after boot (the hero tracker recording a measurement) reaches the card a
        # visitor opens instead of the one the page was built with.
        blocks.load(state.registry.render_html, None, boot_card, api_name=False)

        # Tabs that implement the permalink protocol get their function and arguments back. The
        # report hook may live on the module or, with the tab's own build state, in its handles.
        restore_targets: list[tuple[str, Any, Any, list[Any]]] = []
        for spec in specs:
            module = modules.get(spec.id)
            tab_handles = handles.get(spec.id, {})
            outputs_fn = getattr(module, PERMALINK_OUTPUTS, None)
            restore_fn = getattr(module, PERMALINK_RESTORE, None)
            applied_fn = (
                tab_handles.get(PERMALINK_APPLIED) if isinstance(tab_handles, Mapping) else None
            )
            if not callable(applied_fn):
                applied_fn = getattr(module, PERMALINK_APPLIED, None)
            if callable(outputs_fn) and callable(restore_fn):
                components = list(outputs_fn(tab_handles))
                if components:
                    restore_targets.append((spec.id, restore_fn, applied_fn, components))
        restore_components = [c for _, _, _, comps in restore_targets for c in comps]
        known = known_functions(state) if restore_targets else frozenset()

        def on_select(evt: gr.SelectData) -> str:
            return permalink.build(_tab_from_select(evt.value, labels), base=base)

        def on_load(request: gr.Request) -> Any:
            link = permalink.from_request(request, tabs=TAB_IDS)
            tab = link.tab or TAB_IDS[0]
            if link.tab is None:
                # an unknown or absent tab: the default tab and nothing else — a function or
                # arguments meant for a tab that is not here are never handed to another one
                link = permalink.Permalink(tab)
            shown = permalink.Permalink(tab)
            restored: list[Any] = []
            for tab_id, restore_fn, applied_fn, components in restore_targets:
                if tab_id != tab or link.empty_call:
                    restored.extend(gr.update() for _ in components)
                    continue
                module_name = TAB_MODULES[tab_id]
                handed = applied_link(link, applied_fn, known, module=module_name)
                if handed.empty_call:
                    restored.extend(gr.update() for _ in components)
                    continue
                values, report = restore_answer(
                    tab, restore_fn(handed.fn, handed.args), len(components), module=module_name
                )
                restored.extend(values)
                if report is not NOT_REPORTED:
                    shown = report  # the tab's own report of what it applied
                elif callable(applied_fn):
                    shown = handed  # the tab's hook is its report
                else:
                    log.info(
                        "%s reports nothing applied; the link names the tab alone", module_name
                    )
            return (gr.Tabs(selected=tab), shown.url(base), *restored)

        # `from __future__ import annotations` leaves these annotations as strings that name a
        # function-local `gr`; Gradio resolves injected parameters from `__annotations__`, so the
        # classes are set explicitly here (a request is injected only when it is recognised).
        on_select.__annotations__ = {"evt": gr.SelectData, "return": str}
        on_load.__annotations__ = {"request": gr.Request, "return": Any}
        tabs.select(on_select, None, link_box, api_name=False)
        link_copy.click(None, [link_box], [link_copy], js=common.COPY_JS, api_name=False)
        loaded = blocks.load(on_load, None, [tabs, link_box, *restore_components], api_name=False)
        # Client-side only: lifts the boot hold once the outputs above have been applied.
        loaded.then(None, None, None, js=REVEAL_JS, api_name=False)

    blocks.queue(**hooks["queue"])
    return blocks, list(specs), dict(modules)


def create_app(
    state: boot_sequence.BootState,
    *,
    space_id: str | None = None,
    stamp: str | None = None,
    specs: Sequence[TabSpec] | None = None,
    modules: Mapping[str, Any] | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Any:
    """The FastAPI app: `/health`, `/api/status`, the engine's webhook route, then Gradio at `/`."""
    import gradio as gr
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    blocks, _, used_modules = build_blocks(
        state, space_id=space_id, stamp=stamp, specs=specs, modules=modules
    )
    api = FastAPI(title=TITLE, docs_url=None, redoc_url=None, openapi_url=None)

    @api.get(HEALTH_PATH)
    def health() -> JSONResponse:
        body = public_health(state.health())
        return JSONResponse(body, status_code=503 if body["status"] == "error" else 200)

    @api.get(STATUS_PATH)
    def status() -> JSONResponse:
        return JSONResponse(status_tile(state))

    webhook.mount(api, state.hook)
    return gr.mount_gradio_app(
        api,
        blocks,
        path="/",
        server_name=host,
        server_port=port,
        footer_links=[],
        mcp_server=True,
        ssr_mode=False,
        theme=design.theme(),
        css=page_css(used_modules),
        head=BOOT_HEAD,
    )


def public_health(body: Mapping[str, Any]) -> dict[str, Any]:
    """The `/health` body as the route serves it: the boot snapshot with the webhook's nonce
    removed. `webhook` carries the route's prefix (`/hook`) and whether it is public, never
    the path — the nonce is the one thing that gates the engine's POST without a signing
    secret, and a route that publishes it invites a forged POST onto the receipt card."""
    out = dict(body)
    hook = out.get("webhook")
    if isinstance(hook, Mapping):
        path = str(hook.get("path") or hook.get("prefix") or "").strip()
        prefix = path.rsplit("/", 1)[0] if path.count("/") >= 2 else path
        out["webhook"] = {
            "prefix": prefix or webhook.hosted_api.HOOK_PREFIX,
            "public": bool(hook.get("public")),
        }
    return out


def status_tile(state: boot_sequence.BootState) -> dict[str, Any]:
    """The `/api/status` body: `measured_utc` is the hero's stamp only when the hero was measured.

    A `noisy — not recorded` opening card still carries the time it was attempted; another
    Space's tile must not present that as a measurement, so the stamp is null until the
    rulebook has recorded one.
    """
    body = state.status_tile()
    hero = body.get("hero") or {}
    if hero.get("status") != STATUS_MEASURED:
        body["measured_utc"] = None
    return body


def serve(app: Any, *, host: str, port: int) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="the Algenta flagship Space")
    parser.add_argument(
        "--no-serve", action="store_true", help="boot, build the page, print /health, exit"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    hf_ua_shim.apply()
    host = os.environ.get("GRADIO_SERVER_NAME", "").strip() or DEFAULT_HOST
    port = int(os.environ.get("GRADIO_SERVER_PORT", "").strip() or DEFAULT_PORT)

    state = boot_sequence.run_boot()
    app = create_app(state, space_id=shell.space_id_from_env() or None, host=host, port=port)
    if args.no_serve:
        sys.stdout.write(json.dumps(state.health(), indent=2, sort_keys=True, default=str) + "\n")
        return 0 if state.ready else 1
    log.info("serving on http://%s:%d (%s)", host, port, state.summary())
    serve(app, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
