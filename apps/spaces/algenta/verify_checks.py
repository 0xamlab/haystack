"""The flagship's own post-deploy checks — one per endpoint, plus the page audits.

`tools/verify_remote.py` keeps the registry (`register`, `CHECKS`) and the runner; this
module is the flagship's contribution to it. Nothing here is faked: every endpoint check
calls the live app through `gradio_client` with real inputs and asserts what the cards
from `algenta_spaces.cards` render for a real result — the parity chip, the two lane
latencies, the hardware line and its UTC stamp, or the unavailable card with its code.

Registration is one line in ``verify_remote.py`` once it learns the convention::

    load_space_checks("algenta").install(register, VerifyError, VerifySkipped)

where ``load_space_checks(name)`` imports ``<source dir>/verify_checks.py`` of the Space.
Until then the same checks run standalone from the checkout::

    python apps/spaces/algenta/verify_checks.py --url http://127.0.0.1:7860 --staged <dir>

The endpoint contract
---------------------
The expected `api_name` set comes from the tabs themselves: each ``tabs/<id>_tab.py`` module
declares ``API_NAMES`` (the names it passes to ``api_name=``), and ``TabSpec.api_names`` is
built from the same tuple. This module imports every tab module it finds next to it and reads
that tuple; a tab whose module is absent falls back to the frozen ``FALLBACK_API_NAMES`` row
below. Each per-tab check finds its endpoint by the tab id prefix (``try_…``, ``play_…``, …) in
``/gradio_api/info`` and calls it by keyword, using the app's own prefilled defaults for every
parameter it does not override, so the call is the one a visitor makes.

What each check asserts
-----------------------
* ``expected_api_names``  the live set equals the tabs' set — nothing missing, nothing extra
* ``hero_result``         the Try tab returns a result card with the parity chip, a non-empty
                          hardware line and a UTC stamp — or the rulebook's ``not recorded``
                          card on a loaded host, named as that documented state
* ``playground_levenshtein``  Playground runs ``text.fuzzy.levenshtein_distance`` on
                          kitten/sitting and the result is 3
* ``playground_decimals`` Playground runs ``geodesy.haversine_distance`` on four coordinates
                          with decimals; the Request-and-response JSON echoes exactly the
                          numbers sent (no box rounded them) and the distance agrees with the
                          haversine formula computed here on the kernel's 6,371 km radius
* ``race_cell``           a Races cell returns a result card with both lane latencies, or one
                          of the documented states: held, not recorded, unavailable + code
* ``llm_rmsnorm_parity``  the LLM tab's RMSNorm call carries the parity chip (torch agrees
                          within the printed tolerance)
* ``governed_lane``       the Governed tab returns the not-configured card without a key,
                          else a receipt or a gate denial
* ``ecosystem_counts``    the Ecosystem tab's Hub table carries the live counts (repository
                          rows, the Hub column, the downloads and likes chips) whenever the Hub
                          answered; only a Hub code (``hub_counts_*``) is the documented state,
                          and a code on another card (GitHub, the MCP registry) is named beside
                          the counts, never in their place
* ``every_endpoint_answers``  every remaining api_name (snippets, status tiles, the other LLM
                          kernels, …) answers a default call with output — so each api_name
                          the app exposes is exercised by exactly one check
* ``health_ready``        ``/health`` answers 200 with the boot snapshot ``ready: true`` and
                          the detail prints how long the boot took (the span of the stages),
                          not how long the process has been up
* ``shared_stamp``        the footer stamp equals the staged ``.shared_sha``
* ``console_clean``, ``no_horizontal_scroll``, ``targets_44px``, ``axe_serious_critical``,
  ``contrast_hero``       one headless Chromium session over every tab at 1440 and 375 px, in
                          light and dark (skipped loudly when Playwright is not installed);
                          ``targets_44px`` also opens every dropdown and measures each option
                          of the open listbox, ``contrast_hero`` covers the hero figure, every
                          chip, tile and card caption, and the open listbox's options
* ``contrast_buttons``    text on every button at rest, on hover, on focus and when disabled,
                          and the selected tab's label, at or above 4.5:1 in both themes
* ``contrast_code``       every CodeMirror token class in every visible Code block, both themes
* ``value_boxes_unclipped``  a number box sits inside its parent and its block; its value fits
* ``no_stock_chrome``     the Try and Ecosystem run buttons are pressed and the page sampled at
                          100, 400 and 800 ms: no Gradio status text, ETA bar, generating
                          border or stock orange while the call runs
* ``nav_separators``      at 375 px no wrapped nav or footer row starts or ends with the glyph
* ``checkboxes_dark_unfilled``  an unchecked checkbox in dark mode has no saturated fill
* ``no_identifiers_in_copy``  the visible text outside accordion bodies, code blocks and form
                          values carries no snake_case token, no ALL_CAPS environment name, no
                          ``torch<N>-`` build-variant string and no raw ``https://`` URL; the
                          lowercase codes on unavailable chips are the one convention and pass,
                          and on the Playground the kernel contract's own labels (parameter
                          names in the form, the function's dotted name on the card) are the
                          only allowed identifiers
* ``cls_budget``          three fresh loads of ``?tab=<id>`` per tab at 1440 and 375 px, each
                          observed for two seconds after the boot hold lifts, stay at or under
                          0.05 cumulative layout shift
* ``receipt_tone``        the Governed receipt as ``gov_tab`` renders it tells the truth: a
                          delivered execution is the live chip (``delivered · HTTP <code>``) on
                          the quiet card, a failed one the red chip (``webhook_failed · …``) on
                          the red card with no ``webhook received`` block and no delivery
                          claim, and ``webhook received`` is painted on a delivered receipt
                          alone; a failure during the run (``webhook_url_unavailable``) is the
                          red card; without a key the not-configured card is the documented
                          state — in the keyed phase it is a broken precondition
* ``webhook_privacy``     the webhook nonce stays in the process: ``/health`` names the route's
                          prefix, not the path; the Governed card prints no URL carrying it; a
                          POST to a guessed path answers 400 or 404
* ``family_dropdown_foreign_value``  the Playground answers an API value naming a family this
                          container did not load with a coded card (``unknown_family``), never
                          Gradio's stock "not in the list of choices" error
* ``no_stock_code_labels``  no Code block keeps Gradio's stock block label (the ``</>`` icon)
                          or CodeMirror's line-number gutter — every disclosure is opened first
* ``voids``               at 1440 px, at rest and after each tab's primary action, no column of
                          a multi-column row holds a gap over 240 px between consecutive
                          elements or below its last one
* ``boot_row_live``       the boot card's hero row says what ``/health`` said at the moment the
                          card was read (a measured hero prints its time and ``n``; an
                          unmeasured one ``not recorded``)
* ``refusal_convention``  every refusal on Try, the Playground and (with a key) Governed is a
                          field message under the offending control and an echo in the status
                          row beside the action — never a red card, never a toast
* ``permalink_truth``     ten link shapes are loaded (``PERMALINK_SHAPES``): the box under the
                          strip promises only what the tab restored — every function and
                          argument it names is visible in the form — and the three full shapes
                          are restored in full and kept in the box
* ``dropdown_dismissal``  every dropdown of every tab is opened and dismissed by a click away,
                          by Tab and by Escape without choosing; the form is unchanged after
                          each dismissal
* ``no_toasts``           no visible ``.toast-body`` anywhere: on the landing page, at 100, 400,
                          800 and 3,000 ms after every tab's run button is pressed (the
                          Governed run included when its key is set) and once every run settled
* ``boot_card_timings``   every stage row of the boot card prints the time ``/health`` records
                          for it (a stage that ran is never ``0.0 s``) and the rows sum to the
                          ``booted in`` foot, which is the snapshot's boot time
* ``footer_stamp_one_line``  the footer's build stamp is one line at 375 px in both themes
* ``native_only``         every loaded family names its compiled Mojo shared library, ABI 1,
                          toolchain and a live ctypes handle in ``/health`` — no Python substitute
* ``dropdown_reopens``    a focused combobox whose list was closed (Escape, or the shell's
                          Tab-arrival close) opens again on a click, the form unchanged
* ``eco_table_fits``      the Ecosystem's Hub table fits its block — no clipped column, no
                          sideways scroll — at 900, 1024, 1152, 1200 and 1440 px
* ``exact_integers``      2^53 + 1 typed into a Playground number box reaches the request
                          exactly or is refused with a message under the field; the API path
                          echoes it exactly

Every browser measurement waits for ``app.py``'s boot hold (``html.alg-booting``) to lift, so
nothing is measured on a page that is still being assembled. Runs on CPython 3.12 and 3.14;
stdlib at import, `gradio_client` and `playwright` lazily.

Phases
------
The same checks run twice against a deployment: without the tenant key (``--phase nokey``, the
default) and with it loaded into the app under test (``--phase keyed``, or
``ALGENTA_VERIFY_PHASE=keyed``). In the keyed phase the not-configured card fails the Governed
gates instead of passing as a documented state, the refusal probe must find the Governed
controls, axe must have audited them, and ``KEYED_REQUIRED`` stays selected whatever ``--only``
names — a keyed run never records a defect it does not fail on.
"""

from __future__ import annotations

import argparse
import html as html_lib
import importlib
import json
import logging
import math
import os
import re
import sys
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

log = logging.getLogger(__name__)

SPACE_NAME = "algenta"
HERE = Path(__file__).resolve().parent


def _ensure_shared_on_path() -> None:
    """Make `algenta_spaces` importable from the checkout (`_shared`) or the vendored copy."""
    try:
        importlib.import_module("algenta_spaces")
        return
    except ImportError:
        pass
    for candidate in (HERE, HERE.parent / "_shared"):
        if (candidate / "algenta_spaces" / "__init__.py").is_file():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return


_ensure_shared_on_path()

from algenta_spaces import (  # noqa: E402 - path set above
    bench,
    cards,
    design,
    hosted_api,
    playground,
)

# ---------------------------------------------------------------------------
# Contract: tabs, api names, markers
# ---------------------------------------------------------------------------

TAB_SLUGS: tuple[str, ...] = ("try", "play", "race", "llm", "gov", "eco")
FALLBACK_API_NAMES: Mapping[str, tuple[str, ...]] = {
    "try": ("try_run",),
    "play": ("play_run",),
    "race": ("race_run",),
    "llm": ("llm_run",),
    "gov": ("gov_run",),
    "eco": ("eco_refresh",),
}

HEALTH_PATH = "/health"
INFO_PATH = "/gradio_api/info"
TAB_QUERY = "tab"

LEVENSHTEIN_FAMILY = "text"
LEVENSHTEIN_MODULE = "text.fuzzy"
LEVENSHTEIN_FUNCTION = "levenshtein_distance"
LEVENSHTEIN_ARGS: Mapping[str, str] = {"a": "kitten", "b": "sitting"}
LEVENSHTEIN_EXPECTED = 3
# London to Paris with four decimals each: a form that rounds its number boxes to whole degrees
# echoes 52, 0, 49, 2 and a distance 19 km off; the kernel's haversine uses a 6,371 km radius.
DECIMALS_FAMILY = "geometry"
DECIMALS_MODULE = "geodesy"
DECIMALS_FUNCTION = "haversine_distance"
DECIMALS_ARGS: Mapping[str, float] = {
    "lat1": 51.5074,
    "lon1": -0.1278,
    "lat2": 48.8566,
    "lon2": 2.3522,
}
EARTH_RADIUS_KM = 6371.0
DECIMALS_REL_TOL = 1e-9

# Rendered by algenta_spaces.cards; the foundations are frozen, so these are stable.
RESULT_CARD_RE = re.compile(r'class="alg-card alg-card-result"')
# The chip is drawn only when a parity label was measured; the hero badge is always drawn.
PARITY_RE = re.compile(r'alg-chip-ok">parity\b')
#: `<div class="alg-card-foot">hardware · 2026-09-22 14:02 UTC</div>`, the stamp bare or inside
#: the `<time datetime="…">` element `cards.time_stamp` renders.
FOOT_RE = re.compile(
    r'alg-card-foot">(?P<hardware>[^<]*?)'
    r"(?: · (?:<time[^>]*>)?(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC)(?:</time>)?)?<"
)
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")
UNAVAILABLE_RE = re.compile(r'data-kind="unavailable">unavailable · (?P<code>[^<]+)<')
NOT_RECORDED_RE = re.compile(rf'data-kind="unavailable">{re.escape(cards.NOT_RECORDED_TEXT)}<')
LANE_VAL_RE = re.compile(r'alg-lane-val">([^<]+)<')
TAG_RE = re.compile(r"<[^>]+>")
INT_RE = re.compile(r"(?<![\w.,])\d{1,3}(?:,\d{3})*(?![\w.,])")
RECEIPT_RE = re.compile(r"receipt|execution_id|integrity", re.IGNORECASE)
DENIAL_RE = re.compile(r"denied|denial|gate", re.IGNORECASE)
HELD_TEXT = cards.HELD_TEXT
NOT_CONFIGURED_CODE = hosted_api.NOT_CONFIGURED_CODE
RATE_LIMITED_CODE = hosted_api.RATE_LIMITED_CODE

TARGET_PX = 44
CONTRAST_MIN = 4.5
AXE_IMPACTS = ("serious", "critical")
AUDIT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (("desktop", 1440, 900), ("phone", 375, 812))
#: Every text the design draws in a colour of its own: the hero figure (accent text on the
#: card surface), the pills and chips, the tiles' three lines, the card captions and reasons,
#: the lane labels, the boot rows and the footer — each measured against its effective fill.
CONTRAST_SELECTORS = (
    ".alg-shell-title",
    ".alg-shell-tagline",
    ".alg-shell-eyebrow",
    ".alg-shell-badge",
    ".alg-card-title",
    ".alg-card-sub",
    ".alg-card-reason",
    ".alg-card-note",
    ".alg-card-hint",
    ".alg-hero-num",
    ".alg-hero-label",
    ".alg-chip",
    ".alg-tile-link",
    ".alg-stat-label",
    ".alg-stat-value",
    ".alg-stat-meta",
    ".alg-lane-name",
    ".alg-lane-val",
    ".alg-eco-key",
    ".alg-eco-val",
    ".alg-boot-state",
    ".alg-boot-label",
    ".alg-boot-detail",
    ".alg-card-foot",
    ".alg-shell-footer-licence",
    ".alg-shell-stamp",
)
TARGET_SELECTOR = (
    "a[href], button, input:not([type=hidden]), select, textarea, summary,"
    " [role=button], [role=tab], [role=link]"
)
SETTLE_MS = 400
PAGE_TIMEOUT_MS = 90_000
FONTS_READY_JS = "document.fonts.status === 'loaded'"
FONTS_TIMEOUT_MS = 15_000
MIN_SUBSTRING_KEY = 3
# gradio validates a Dropdown value against the choices it was built with, so a cascading form
# (family -> module -> function) refuses any other family's module through the API and MCP.
CHOICES_REFUSAL = "is not in the list of choices"
CHOICES_HINT = (
    " — the dropdown validates against the default family's choices, so the API and MCP cannot"
    " select another family; cascading dropdowns need allow_custom_value=True"
)
FAMILY_PARAMS = ("fam", "family")
MODULE_PARAMS = ("mod", "module")
FUNCTION_PARAMS = ("fn", "function", "func")

# ---------------------------------------------------------------------------
# Failure signalling — rebound by install() to the tool's own classes
# ---------------------------------------------------------------------------


class CheckFailedError(AssertionError):
    """One check did not hold (standalone default; `install` swaps in `VerifyError`)."""


class CheckSkipped(Exception):  # noqa: N818 - a skip signal, not an error
    """One check cannot run here; the reason is reported on its own line."""


_SIGNALS: dict[str, type[BaseException]] = {"fail": CheckFailedError, "skip": CheckSkipped}


def fail(message: str) -> NoReturn:
    raise _SIGNALS["fail"](message)


def skip(message: str) -> NoReturn:
    raise _SIGNALS["skip"](message)


# ---------------------------------------------------------------------------
# Tabs and the expected endpoint set
# ---------------------------------------------------------------------------


TABS_PACKAGE = "tabs"
TAB_MODULE_SUFFIX = "_tab"


def tab_api_names(tabs_dir: Path | None = None) -> dict[str, tuple[str, ...]]:
    """id -> ``API_NAMES`` of every ``tabs/<id>_tab.py`` that imports; missing tabs are absent."""
    base = HERE if tabs_dir is None else Path(tabs_dir)
    package_dir = base / TABS_PACKAGE
    if not (package_dir / "__init__.py").is_file():
        return {}
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    found: dict[str, tuple[str, ...]] = {}
    for path in sorted(package_dir.glob(f"*{TAB_MODULE_SUFFIX}.py")):
        slug = path.stem[: -len(TAB_MODULE_SUFFIX)]
        try:
            module = importlib.import_module(f"{TABS_PACKAGE}.{path.stem}")
        except Exception as exc:  # noqa: BLE001 - a tab that cannot import is reported, not hidden
            log.warning("tab module %s did not import: %s", path.stem, exc)
            continue
        names = getattr(module, "API_NAMES", None)
        if isinstance(names, str):
            names = (names,)
        if names:
            found[slug] = tuple(str(n) for n in names)
    return found


def tab_labels(tabs_dir: Path | None = None) -> dict[str, str]:
    """id -> the tab's ``LABEL`` for every ``tabs/<id>_tab.py`` that imports and declares one."""
    base = HERE if tabs_dir is None else Path(tabs_dir)
    package_dir = base / TABS_PACKAGE
    if not (package_dir / "__init__.py").is_file():
        return {}
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    labels: dict[str, str] = {}
    for path in sorted(package_dir.glob(f"*{TAB_MODULE_SUFFIX}.py")):
        slug = path.stem[: -len(TAB_MODULE_SUFFIX)]
        try:
            module = importlib.import_module(f"{TABS_PACKAGE}.{path.stem}")
        except Exception as exc:  # noqa: BLE001 - a tab that cannot import has no label here
            log.debug("tab module %s did not import: %s", path.stem, exc)
            continue
        label = getattr(module, "LABEL", None)
        if isinstance(label, str) and label.strip():
            labels[slug] = label.strip()
    return labels


def expected_api_names(tabs_dir: Path | None = None) -> dict[str, tuple[str, ...]]:
    """id -> api names in tab order: the tab module's ``API_NAMES``, else the frozen fallback."""
    live = tab_api_names(tabs_dir)
    out: dict[str, tuple[str, ...]] = {}
    for slug in TAB_SLUGS:
        out[slug] = live.get(slug) or tuple(FALLBACK_API_NAMES[slug])
    for slug, names in live.items():
        out.setdefault(slug, names)
    return out


def tab_slugs(tabs_dir: Path | None = None) -> tuple[str, ...]:
    return tuple(expected_api_names(tabs_dir))


def all_expected(tabs_dir: Path | None = None) -> frozenset[str]:
    return frozenset(n for names in expected_api_names(tabs_dir).values() for n in names)


# ---------------------------------------------------------------------------
# gradio_client access
# ---------------------------------------------------------------------------


def _default_client(base_url: str) -> Any:
    from gradio_client import Client

    return Client(base_url, verbose=False)


CLIENT_FACTORY: Callable[[str], Any] = _default_client
_clients: dict[str, Any] = {}


def client_for(ctx: Any) -> Any:
    base = ctx.base_url.rstrip("/")
    if base not in _clients:
        try:
            _clients[base] = CLIENT_FACTORY(base)
        except Exception as exc:  # noqa: BLE001 - every client error is one failed check
            fail(f"gradio_client could not connect to {base}: {type(exc).__name__}: {exc}")
    return _clients[base]


def reset_clients() -> None:
    _clients.clear()
    _audits.clear()
    _cls_audits.clear()
    _audit_errors.clear()
    _cls_audit_errors.clear()
    _permalink_audits.clear()
    _permalink_audit_errors.clear()
    _exact_int_audits.clear()
    _exact_int_errors.clear()
    _refusal_audits.clear()
    _refusal_audit_errors.clear()
    _eco_table_audits.clear()
    _eco_table_errors.clear()
    _LABEL_CACHE.clear()


def live_endpoints(ctx: Any) -> dict[str, dict]:
    """`api_name -> endpoint info` from /gradio_api/info, names without the leading slash."""
    named = ctx.info().get("named_endpoints", {})
    return {name.lstrip("/"): info for name, info in named.items()}


def endpoint_for(ctx: Any, slug: str) -> tuple[str, dict]:
    """The one endpoint of a tab: the run endpoint named in ``FALLBACK_API_NAMES`` when live, then
    the tab module's own names in order, then the first slug-prefixed live name."""
    live = live_endpoints(ctx)
    preferred = tuple(FALLBACK_API_NAMES.get(slug, ())) + tuple(expected_api_names().get(slug, ()))
    for name in preferred:
        if name in live:
            return name, live[name]
    prefixed = sorted(n for n in live if n.startswith(f"{slug}_"))
    if prefixed:
        return prefixed[0], live[prefixed[0]]
    fail(f"no endpoint for tab {slug!r}; live: {', '.join(sorted(live)) or 'none'}")


def build_kwargs(info: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Keyword arguments for one call: overrides matched by parameter name (exact, then a
    substring of at least three characters), the app's own default for everything else, and
    the untouched-field value (None, False for a Checkbox) where the app declares none."""
    kwargs: dict[str, Any] = {}
    used: set[str] = set()
    for param in info.get("parameters", ()):
        name = str(param.get("parameter_name") or "")
        if not name:
            continue
        chosen = None
        for key, value in overrides.items():
            if key == name:
                chosen = (key, value)
                break
        if chosen is None:
            for key, value in overrides.items():
                if key not in used and len(key) >= MIN_SUBSTRING_KEY and key in name:
                    chosen = (key, value)
                    break
        if chosen is not None:
            used.add(chosen[0])
            kwargs[name] = chosen[1]
        elif param.get("parameter_has_default"):
            kwargs[name] = param.get("parameter_default")
        else:
            # an untouched form field: unchecked for a Checkbox, empty for anything else
            kwargs[name] = False if param.get("component") == "Checkbox" else None
    return kwargs


def call(ctx: Any, slug: str, overrides: Mapping[str, Any] | None = None) -> tuple[str, list]:
    """Call the tab's endpoint with real inputs; return `(api_name, outputs)`."""
    name, info = endpoint_for(ctx, slug)
    kwargs = build_kwargs(info, overrides or {})
    client = client_for(ctx)
    try:
        result = client.predict(api_name=f"/{name}", **kwargs)
    except Exception as exc:  # noqa: BLE001 - AppError, transport errors, timeouts
        hint = CHOICES_HINT if CHOICES_REFUSAL in str(exc) else ""
        fail(f"/{name} raised {type(exc).__name__}: {str(exc)[:200]}{hint}")
    outputs = list(result) if isinstance(result, tuple) else [result]
    return name, outputs


UPDATE_TYPE = "update"


def unwrap_update(value: Any) -> Any:
    """The value inside a Gradio `gr.update(...)` payload (`{"__type__": "update", "value": …}`),
    or `value` itself; an update without a value (visibility alone) is None."""
    if isinstance(value, dict) and value.get("__type__") == UPDATE_TYPE:
        return value.get("value")
    return value


def texts_of(outputs: Sequence[Any]) -> list[str]:
    """Every output as text: strings as they are, a `gr.update` payload as its value, other
    structured values as JSON; an update that carries no value renders nothing."""
    out: list[str] = []
    for raw in outputs:
        value = unwrap_update(raw)
        if isinstance(value, str):
            out.append(value)
        elif value is None:
            continue
        else:
            out.append(json.dumps(value, sort_keys=True, default=str))
    return out


def plain_text(markup: str) -> str:
    return html_lib.unescape(TAG_RE.sub(" ", markup))


def unavailable_code(text: str) -> str | None:
    m = UNAVAILABLE_RE.search(text)
    return html_lib.unescape(m.group("code")).strip() if m else None


def foot_of(text: str) -> tuple[str, str] | None:
    """`(hardware, utc stamp)` of the first card footer that carries both."""
    for m in FOOT_RE.finditer(text):
        hardware = html_lib.unescape(m.group("hardware")).strip()
        stamp = m.group("stamp") or ""
        if hardware and stamp:
            return hardware, stamp
    return None


def _contains_int(outputs: Sequence[Any], wanted: int) -> bool:
    for value in outputs:
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float) and value == wanted:
            return True
        if isinstance(value, dict) and _contains_int(list(value.values()), wanted):
            return True
        if isinstance(value, list | tuple) and _contains_int(value, wanted):
            return True
        if isinstance(value, str):
            tokens = plain_text(value).replace(",", " ").split()
            if str(wanted) in tokens:
                return True
    return False


# ---------------------------------------------------------------------------
# Endpoint checks
# ---------------------------------------------------------------------------


def expected_api_names_check(ctx: Any) -> str:
    live = set(live_endpoints(ctx))
    expected = set(all_expected())
    if not expected:
        fail("the tabs declare no api names")
    missing = sorted(expected - live)
    extra = sorted(live - expected)
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected {', '.join(extra)}")
        fail("; ".join(parts))
    return f"{len(expected)} endpoints, all declared by the tabs"


expected_api_names_check.__name__ = "expected_api_names"


def hero_result(ctx: Any) -> str:
    """The Try tab's card for a visitor's run: a result card with the parity chip, the hardware
    line and the stamp — or the rulebook's `not recorded` card, the honest answer on a host too
    loaded to time a sub-millisecond call, reported as that documented state and never as a
    measurement."""
    name, outputs = call(ctx, "try")
    joined = "\n".join(texts_of(outputs))
    if NOT_RECORDED_RE.search(joined):
        reason = ""
        m = re.search(r'alg-card-reason">([^<]+)<', joined)
        if m:
            reason = " — " + html_lib.unescape(m.group(1)).strip()
        return f"/{name} not recorded (documented state{reason})"
    code = unavailable_code(joined)
    if code:
        fail(f"/{name} returned the unavailable card ({code})")
    if not RESULT_CARD_RE.search(joined):
        fail(f"/{name} returned no result card")
    if not PARITY_RE.search(joined):
        fail(f"/{name}: no parity chip on the hero card")
    foot = foot_of(joined)
    if foot is None:
        fail(f"/{name}: hero card has no hardware line with a UTC stamp")
    hardware, stamp = foot
    return f"/{name} parity chip · {hardware} · {stamp}"


def _family_choice(param: Mapping[str, Any], family: str = LEVENSHTEIN_FAMILY) -> str:
    """The family dropdown's own spelling of `family` (`algenta-text`, `thyn-ai/…` or `text`)."""
    choices = (param.get("type") or {}).get("enum")
    if isinstance(choices, list):
        for choice in choices:
            if str(choice).removeprefix("thyn-ai/").removeprefix("algenta-") == family:
                return str(choice)
    return family


def _form_overrides(
    info: Mapping[str, Any],
    *,
    family: str,
    module: str,
    function: str,
    args: Mapping[str, Any],
    component: str,
) -> dict[str, Any]:
    """The visitor's Playground inputs for one call: the family, module and function selectors
    by name, then the arguments — by their own names when the form declares them, into an
    `args` JSON control when the form is one JSON field, else into the first `component`
    fields (Textbox for strings, Number for numbers) after the function selector, in order.
    Everything else keeps the app's default."""
    overrides: dict[str, Any] = {}
    values = list(args.values())
    seen_function = False
    for param in info.get("parameters", ()):
        name = str(param.get("parameter_name") or "")
        kind = str(param.get("component") or "")
        lower = name.lower()
        if lower in FAMILY_PARAMS:
            overrides[name] = _family_choice(param, family)
        elif lower in MODULE_PARAMS:
            overrides[name] = module
        elif lower in FUNCTION_PARAMS:
            overrides[name] = function
            seen_function = True
        elif lower in args:
            overrides[name] = args[lower]
        elif "args" in lower or "json" in lower:
            overrides[name] = json.dumps(dict(args))
        elif seen_function and kind == component and values:
            overrides[name] = values.pop(0)
    return overrides


def playground_overrides(info: Mapping[str, Any]) -> dict[str, Any]:
    """The kitten/sitting call: two strings into the first two Textbox fields."""
    return _form_overrides(
        info,
        family=LEVENSHTEIN_FAMILY,
        module=LEVENSHTEIN_MODULE,
        function=LEVENSHTEIN_FUNCTION,
        args=LEVENSHTEIN_ARGS,
        component="Textbox",
    )


def decimals_overrides(info: Mapping[str, Any]) -> dict[str, Any]:
    """The London–Paris call: four floats with decimals into the first four Number fields."""
    return _form_overrides(
        info,
        family=DECIMALS_FAMILY,
        module=DECIMALS_MODULE,
        function=DECIMALS_FUNCTION,
        args=DECIMALS_ARGS,
        component="Number",
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """The great-circle distance on a sphere of `EARTH_RADIUS_KM`, computed here in float64 —
    the independent reference the Playground's echo is compared with."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def json_documents(outputs: Sequence[Any]) -> list[dict[str, Any]]:
    """Every output that is a JSON object: a string that parses, a dict as it is, or either one
    inside a `gr.update` payload (a Code block refreshed with `gr.update(value=…)`)."""
    documents: list[dict[str, Any]] = []
    for raw in outputs:
        value = unwrap_update(raw)
        if isinstance(value, dict):
            documents.append(value)
            continue
        if not isinstance(value, str) or not value.lstrip().startswith("{"):
            continue
        try:
            parsed = json.loads(value)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            documents.append(parsed)
    return documents


def playground_levenshtein(ctx: Any) -> str:
    name, info = endpoint_for(ctx, "play")
    _, outputs = call(ctx, "play", playground_overrides(info))
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if code:
        fail(f"/{name} returned the unavailable card ({code})")
    if not _contains_int(outputs, LEVENSHTEIN_EXPECTED):
        fail(
            f"/{name}: {LEVENSHTEIN_MODULE}.{LEVENSHTEIN_FUNCTION}(kitten, sitting) did not"
            f" return {LEVENSHTEIN_EXPECTED}"
        )
    return f"/{name} levenshtein(kitten, sitting) = {LEVENSHTEIN_EXPECTED}"


def playground_decimals(ctx: Any) -> str:
    """Decimals survive the form: the Request-and-response JSON echoes the four coordinates as
    sent, and the distance agrees with the haversine formula on the kernel's radius."""
    name, info = endpoint_for(ctx, "play")
    _, outputs = call(ctx, "play", decimals_overrides(info))
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if code:
        fail(f"/{name} returned the unavailable card ({code})")
    request = next(
        (d for d in json_documents(outputs) if isinstance(d.get("args"), list | dict)), None
    )
    if request is None:
        fail(f"/{name}: no Request-and-response JSON with the call's args in the outputs")
    sent = list(DECIMALS_ARGS.values())
    echoed = request["args"]
    if isinstance(echoed, dict):  # a request that names its arguments
        echoed = [echoed.get(key) for key in DECIMALS_ARGS]
    if echoed != sent:
        fail(
            f"/{name}: {DECIMALS_MODULE}.{DECIMALS_FUNCTION} echoed args {echoed}, sent {sent}"
            " — a number box rounded the decimals away"
        )
    response = next((d for d in json_documents(outputs) if "result" in d), None)
    result = response.get("result") if response is not None else None
    if not isinstance(result, int | float) or isinstance(result, bool):
        fail(f"/{name}: the response JSON carries no numeric result")
    expected = haversine_km(*sent)
    rel = abs(float(result) - expected) / expected
    if rel > DECIMALS_REL_TOL:
        fail(
            f"/{name}: haversine returned {result!r}, the formula gives {expected!r}"
            f" (relative difference {rel:.2e} > {DECIMALS_REL_TOL:g})"
        )
    return (
        f"/{name} haversine args echoed exactly · {float(result):.4f} km,"
        f" the formula agrees to {rel:.1e}"
    )


def race_cell(ctx: Any) -> str:
    name, outputs = call(ctx, "race")
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if code:
        return f"/{name} unavailable · {code} (documented state)"
    if HELD_TEXT in plain_text(joined):
        return f"/{name} held: incumbent faster on this run (documented state)"
    if NOT_RECORDED_RE.search(joined):
        return f"/{name} not recorded (documented state)"
    if not RESULT_CARD_RE.search(joined):
        fail(f"/{name} returned neither a result card nor a documented state")
    lanes = [html_lib.unescape(v).strip() for v in LANE_VAL_RE.findall(joined)]
    if len(lanes) < 2:
        fail(f"/{name}: result card shows {len(lanes)} lane latency, needs both")
    foot = foot_of(joined)
    if foot is None:
        fail(f"/{name}: result card has no hardware line with a UTC stamp")
    return f"/{name} {lanes[0]} vs {lanes[1]} · {foot[0]}"


def llm_rmsnorm_parity(ctx: Any) -> str:
    name, outputs = call(ctx, "llm")
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if code:
        fail(f"/{name} returned the unavailable card ({code})")
    if not PARITY_RE.search(joined):
        fail(f"/{name}: no parity chip — torch did not agree within tolerance, or none printed")
    foot = foot_of(joined)
    where = f" · {foot[0]}" if foot else ""
    return f"/{name} parity chip{where}"


def same_code(code: str | None, expected: str) -> bool:
    """`hosted_not_configured` and `HOSTED-NOT-CONFIGURED` are one code: the cards print the
    lowercase snake_case form, the hosted-API constants the upper-case hyphenated one."""
    if code is None:
        return False
    return code.strip().lower().replace("-", "_") == expected.strip().lower().replace("-", "_")


def _not_configured_in_a_keyed_run(name: str, code: str) -> None:
    """In the keyed phase the not-configured card is a broken precondition, not a state: the
    tool was told a key is loaded, so the gate must exercise what the key unlocks."""
    if keyed():
        fail(
            f"/{name} answers {code} in the keyed phase: the key the run was given did not"
            " reach the app (or the hosted client is not installed in this container)"
        )


def governed_lane(ctx: Any) -> str:
    name, outputs = call(ctx, "gov")
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if same_code(code, NOT_CONFIGURED_CODE):
        _not_configured_in_a_keyed_run(name, code)
        return f"/{name} {code} (no key on this Space)"
    if same_code(code, RATE_LIMITED_CODE):
        return f"/{name} {code} (shared demo tenant throttled)"
    if code:
        fail(f"/{name} returned the unavailable card ({code})")
    text = plain_text(joined)
    if RECEIPT_RE.search(text):
        return f"/{name} receipt"
    if DENIAL_RE.search(text):
        return f"/{name} gate denial"
    fail(f"/{name} returned neither the not-configured card, a receipt nor a denial")


def receipt_status(card: str) -> tuple[str, str, str] | None:
    """`(status, tone, chip text)` read from the receipt's status chip exactly as
    `gov_tab.receipt_status_chip` renders it — `delivered · HTTP 200` (the live tone),
    `webhook_failed · HTTP 502` / `no HTTP response` (red, the engine's POST failed), or
    `engine <status> · …` for any other status — or None when the card is not a receipt."""
    if RECEIPT_TITLE not in card:
        return None
    m = RECEIPT_CHIP_RE.search(card)
    if m is None:
        return None
    text = html_lib.unescape(TAG_RE.sub("", m.group("text"))).strip()
    head = text.split(" · ", 1)[0].strip()
    if head == STATUS_DELIVERED:
        status = STATUS_DELIVERED
    elif head == CODE_WEBHOOK_FAILED:
        status = STATUS_FAILED
    else:
        status = head.removeprefix("engine ").strip()
    return status, m.group("tone"), text


def receipt_tone(ctx: Any) -> str:
    """The Governed card tells the truth about the execution, read from the card `gov_tab`
    renders: a delivered receipt carries the live chip (`delivered · HTTP <code>`) on the quiet
    card; a failed one (`webhook_failed · …`) the red chip on the red card, no `webhook received`
    block and no delivery claim; `webhook received` is painted on a delivered receipt alone. A
    failure during the run (no public https base, an engine or transport error) is the red
    card. Without a key the not-configured card is the documented state — except in the keyed
    phase, where it is a broken precondition."""
    name, outputs = call(ctx, "gov")
    texts = texts_of(outputs)
    joined = "\n".join(texts)
    card = next((t for t in texts if "alg-card" in t), joined)
    code = unavailable_code(card)
    if same_code(code, NOT_CONFIGURED_CODE):
        _not_configured_in_a_keyed_run(name, code)
        return f"/{name} {code}: no key on this Space, the receipt tone is not exercised"
    if same_code(code, RATE_LIMITED_CODE):
        return f"/{name} {code}: demo tenant throttled, the receipt tone is not exercised"
    if code:
        red = ERROR_CARD_CLASS in card
        if not red:
            fail(f"/{name} {code}: a failure during the run on a quiet card, not the red one")
        return f"/{name} {code} on the red card"
    text = plain_text(card)
    parsed = receipt_status(card)
    if parsed is None:
        if DENIAL_RE.search(text):
            return f"/{name} gate denial (held), no receipt to tone"
        if RECEIPT_TITLE in card:
            fail(f"/{name} receipt carries no status chip")
        fail(f"/{name} returned neither the not-configured card, a receipt nor a denial")
    status, tone, chip = parsed
    received = WEBHOOK_RECEIVED_TEXT in text
    red_card = ERROR_CARD_CLASS in card
    problems: list[str] = []
    if status == STATUS_DELIVERED:
        if tone != RECEIPT_OK_TONE:
            problems.append(f"painted {tone}; a delivered execution is the live tone")
        if red_card:
            problems.append("a delivered receipt on the red card")
    elif status == STATUS_FAILED:
        if tone != cards.ERROR_TONE:
            problems.append(f"painted {tone}; a failed execution is red")
        if not red_card:
            problems.append("a failed receipt on the quiet card, not the red one")
        if received:
            problems.append(f"'{WEBHOOK_RECEIVED_TEXT}' painted on a failed receipt")
        if DELIVERY_CLAIM in text:
            problems.append("the card claims the engine reported delivery")
    else:
        failed_word = any(word in status.lower() for word in FAILED_STATUS_WORDS)
        if failed_word and tone != cards.ERROR_TONE:
            problems.append(f"painted {tone}; a failed execution is red")
        if not failed_word and tone == cards.ERROR_TONE:
            problems.append("painted red for a status that is not a failure")
        if received:
            problems.append(
                f"'{WEBHOOK_RECEIVED_TEXT}' painted on a receipt the engine reports {status}"
            )
    if problems:
        fail(f"/{name} receipt '{chip}': {'; '.join(problems)}")
    tail = f", {WEBHOOK_RECEIVED_TEXT}" if received else ""
    return f"/{name} receipt '{chip}' painted {tone}{tail}"


def _urllib_post_json(url: str, body: Mapping[str, Any], timeout: float) -> tuple[int, str]:
    """POST a JSON body; `(status, text)` — an HTTP error is a status, never an exception."""
    import urllib.error
    import urllib.request

    data = json.dumps(dict(body)).encode()
    request = urllib.request.Request(  # noqa: S310 - the base URL is the operator's argument
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


post_json: Callable[[str, Mapping[str, Any], float], tuple[int, str]] = _urllib_post_json


def _hook_prefix(health: Any) -> str:
    """The webhook route's prefix as `/health` names it (`webhook.prefix`, or the directory of
    an older snapshot's `webhook.path`), else the foundations' `/hook`."""
    hook = health.get("webhook") if isinstance(health, dict) else None
    if isinstance(hook, Mapping):
        prefix = str(hook.get("prefix") or "").strip()
        if prefix:
            return "/" + prefix.strip("/")
        path = str(hook.get("path") or "").strip()
        if path.count("/") >= 2:
            return path.rsplit("/", 1)[0]
        if path:
            return "/" + path.strip("/")
    return hosted_api.HOOK_PREFIX


def webhook_privacy(ctx: Any) -> str:
    """The nonce that gates the engine's webhook stays inside the process: `/health` names the
    route's prefix and whether it is public, never the path a forged POST could hit; the
    Governed card prints no URL carrying it; and a POST to a guessed path is refused (400 or
    404) — the verification model the Governed runbook describes (no signature without the
    secret; the nonce hidden; the POST matched to the session's decision and its integrity ids
    on the page)."""
    status_code, body = ctx.get(HEALTH_PATH)
    try:  # the body is read at any status: a 503 snapshot must hide the nonce just the same
        health = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{HEALTH_PATH} answered {status_code} and is not JSON: {exc}")
    problems: list[str] = []
    leaked = HOOK_NONCE_RE.search(body)
    if leaked:
        problems.append(
            f"{HEALTH_PATH} publishes the webhook path with its nonce ({leaked.group(0)[:12]}…)"
        )
    prefix = _hook_prefix(health)
    name, outputs = call(ctx, "gov")
    joined = "\n".join(texts_of(outputs))
    card_text = plain_text(joined)
    code = unavailable_code(joined)
    if same_code(code, NOT_CONFIGURED_CODE):
        _not_configured_in_a_keyed_run(name, code)
        card = f"/{name} {code}, no receipt to print a URL"
    elif HOOK_URL_RE.search(card_text) or HOOK_NONCE_RE.search(card_text):
        problems.append(f"/{name} prints the webhook URL with its nonce on the card")
        card = f"/{name} leaks the URL"
    else:
        card = f"/{name} prints no webhook URL"
    base = ctx.base_url.rstrip("/")
    forged = {"decision_id": "dec_guessed", "event": "execution.delivered", "forged_by": "verify"}
    guessed, _ = post_json(f"{base}{prefix}/{GUESSED_NONCE}", forged, ctx.budget_s)
    if guessed not in REFUSED_POST_STATUSES:
        problems.append(f"POST {prefix}/<guessed nonce> answered {guessed}, not 400 or 404")
    bare, _ = post_json(f"{base}{prefix}", forged, ctx.budget_s)
    if bare not in REFUSED_POST_STATUSES:
        problems.append(f"POST {prefix} answered {bare}, not 400/404/405")
    if problems:
        fail("; ".join(problems))
    status = f" (HTTP {status_code})" if status_code != 200 else ""
    return (
        f"{HEALTH_PATH}{status} names {prefix}/… without the nonce; {card};"
        f" POST {prefix}/<guessed> → {guessed}, POST {prefix} → {bare}"
    )


def family_dropdown_foreign_value(ctx: Any) -> str:
    """An API or MCP client that names a family this container did not load gets a coded card
    (`unknown_family`), never Gradio's stock `is not in the list of choices` error: the
    Playground's run endpoint is called with `FOREIGN_FAMILY`, and so is the family cascade
    endpoint when the app exposes one (it may answer with no-op updates — nothing to cascade
    to — but never with an exception)."""
    name, info = endpoint_for(ctx, "play")
    family_param = next(
        (
            str(p.get("parameter_name"))
            for p in info.get("parameters", ())
            if str(p.get("parameter_name") or "").lower() in FAMILY_PARAMS
        ),
        None,
    )
    if family_param is None:
        fail(f"/{name} declares no family parameter ({', '.join(FAMILY_PARAMS)})")
    client = client_for(ctx)
    kwargs = build_kwargs(info, {family_param: FOREIGN_FAMILY})
    try:
        result = client.predict(api_name=f"/{name}", **kwargs)
    except Exception as exc:  # noqa: BLE001 - the stock refusal is the finding
        if CHOICES_REFUSAL in str(exc):
            fail(
                f"/{name} {family_param}={FOREIGN_FAMILY!r} raised Gradio's stock error"
                f" ({CHOICES_REFUSAL}): the Family dropdown validates API values against its"
                " list instead of answering with a coded card"
            )
        fail(f"/{name} {family_param}={FOREIGN_FAMILY!r} raised {type(exc).__name__}: {exc!s:.160}")
    outputs = list(result) if isinstance(result, tuple) else [result]
    joined = "\n".join(texts_of(outputs))
    code = unavailable_code(joined)
    if code is None:
        if RESULT_CARD_RE.search(joined):
            fail(f"/{name} ran a call for {FOREIGN_FAMILY!r}, a family this container never loaded")
        fail(
            f"/{name} {family_param}={FOREIGN_FAMILY!r} answered with neither a coded card nor"
            " a result"
        )
    detail = f"/{name} {family_param}={FOREIGN_FAMILY!r} → unavailable · {code}"
    cascade = next(
        (n for n in sorted(live_endpoints(ctx)) if n.startswith("play_") and n.endswith("modules")),
        None,
    )
    if cascade is None:
        return f"{detail}; no family cascade endpoint to probe"
    cascade_kwargs = build_kwargs(live_endpoints(ctx)[cascade], {family_param: FOREIGN_FAMILY})
    try:
        answer = client.predict(api_name=f"/{cascade}", **cascade_kwargs)
    except Exception as exc:  # noqa: BLE001 - the stock refusal is the finding
        hint = f" ({CHOICES_REFUSAL})" if CHOICES_REFUSAL in str(exc) else ""
        fail(f"{detail}; /{cascade} raised {type(exc).__name__}{hint}: {exc!s:.160}")
    cascade_outputs = list(answer) if isinstance(answer, tuple) else [answer]
    cascade_code = unavailable_code("\n".join(texts_of(cascade_outputs)))
    how = f"unavailable · {cascade_code}" if cascade_code else "no-op (nothing to cascade to)"
    return f"{detail}; /{cascade} → {how}"


TABLE_MARKER = "<table"
TBODY_RE = re.compile(r"<tbody>(.*?)</tbody>", re.DOTALL)
ROW_RE = re.compile(r"<tr\b")
FUNCTIONS_CHIP_RE = re.compile(r"(\d[\d,]*) functions\b")
DOWNLOADS_RE = re.compile(r"(\d[\d,]*) downloads\b")
LIKES_RE = re.compile(r"(\d[\d,]*) likes?\b")
LISTED_RE = re.compile(r"published \d{4}-\d{2}-\d{2}|\d[\d,]* downloads\b")


def _int_of(match: re.Match[str] | None) -> int | None:
    return int(match.group(1).replace(",", "")) if match else None


def hub_counts(table_html: str) -> dict[str, int | None]:
    """What the Ecosystem's Hub table says: repository rows, rows the Hub column lists (a
    download count or a publish date), and the head chips' functions, downloads and likes."""
    body = TBODY_RE.search(table_html)
    rows = body.group(1) if body else ""
    head = plain_text(TBODY_RE.sub(" ", table_html))  # the chips, never a row's own cells
    return {
        "rows": len(ROW_RE.findall(rows)),
        "listed": len(LISTED_RE.findall(plain_text(rows))),
        "functions": _int_of(FUNCTIONS_CHIP_RE.search(head)),
        "downloads": _int_of(DOWNLOADS_RE.search(head)),
        "likes": _int_of(LIKES_RE.search(head)),
    }


def ecosystem_counts(ctx: Any) -> str:
    """The Hub counts are checked whenever the Hub answered; a code on another card of the tab
    (GitHub, the MCP registry) is named beside them and never turns the check into a
    documented state. Without a table in the outputs (another build of the tab) any two
    computed integers count."""
    name, outputs = call(ctx, "eco")
    texts = [t for t in texts_of(outputs) if t.strip()]
    if not texts:
        fail(f"/{name} returned no output")
    table = next((t for t in texts if TABLE_MARKER in t), None)
    if table is None:
        joined = "\n".join(texts)
        code = unavailable_code(joined)
        if code:
            return f"/{name} unavailable · {code} (documented state)"
        text = UTC_RE.sub(" ", plain_text(joined))
        counts = [int(m.group(0).replace(",", "")) for m in INT_RE.finditer(text)]
        counts = [c for c in counts if c >= 1]
        if len(counts) < 2:
            fail(f"/{name} returned no computed counts")
        return f"/{name} {len(counts)} counts, largest {max(counts):,}"
    other_codes = [c for c in (unavailable_code(t) for t in texts if t is not table) if c]
    also = f"; also unavailable: {', '.join(other_codes)}" if other_codes else ""
    hub_code = unavailable_code(table)
    if hub_code:
        return f"/{name} Hub counts unavailable · {hub_code} (documented state){also}"
    counts = hub_counts(table)
    if not counts["rows"]:
        fail(f"/{name}: the Hub table has no repository rows")
    if not counts["listed"]:
        fail(f"/{name}: the Hub answered but no row carries a download count or a publish date")
    parts = [f"{counts['rows']} repositories", f"{counts['listed']} listed by the Hub"]
    if counts["functions"] is not None:
        parts.append(f"{counts['functions']:,} functions")
    parts.append(f"{counts['downloads'] or 0:,} downloads")
    parts.append(f"{counts['likes'] or 0:,} likes")
    return f"/{name} Hub: {' · '.join(parts)}{also}"


#: The Races candidate selector's parameter names, and the candidate the gate asks for when the
#: default answered a value guard's no-op (a candidate this container does not offer snaps the
#: box back to the first one — with values, so the endpoint still answers).
RACE_PARAMS: tuple[str, ...] = ("race_id", "race", "candidate")
RACE_ALTERNATE = "betweenness"
SELECTOR_PARAMS: tuple[str, ...] = FAMILY_PARAMS + MODULE_PARAMS + FUNCTION_PARAMS + RACE_PARAMS


def is_noop(outputs: Sequence[Any]) -> bool:
    """True when every output is a `gr.update` that carries no value — the shape a cascade
    endpoint answers when the selection it was given is the one already applied
    (`play_tab`'s value guard keeps the visitor's typed values on a repeated selection)."""
    return bool(outputs) and all(
        isinstance(raw, dict) and raw.get("__type__") == UPDATE_TYPE and unwrap_update(raw) is None
        for raw in outputs
    )


def changed_selection(info: Mapping[str, Any]) -> dict[str, Any]:
    """Overrides that move a selector cascade off the app's defaults: the Playground's family,
    module or function parameters to the Levenshtein trio, the Races candidate parameter to
    `RACE_ALTERNATE`; empty for an endpoint that declares neither."""
    params = list(info.get("parameters", ()))
    names = {str(p.get("parameter_name") or "").lower() for p in params}
    overrides: dict[str, Any] = {}
    if names & set(FAMILY_PARAMS + MODULE_PARAMS + FUNCTION_PARAMS):
        overrides.update(
            _form_overrides(
                info,
                family=LEVENSHTEIN_FAMILY,
                module=LEVENSHTEIN_MODULE,
                function=LEVENSHTEIN_FUNCTION,
                args={},
                component="Number",
            )
        )
    for param in params:
        name = str(param.get("parameter_name") or "")
        if name.lower() in RACE_PARAMS:
            overrides[name] = RACE_ALTERNATE
    return overrides


def _call_named(
    ctx: Any, name: str, info: Mapping[str, Any], overrides: Mapping[str, Any] | None = None
) -> list:
    kwargs = build_kwargs(info, overrides or {})
    client = client_for(ctx)
    try:
        result = client.predict(api_name=f"/{name}", **kwargs)
    except Exception as exc:  # noqa: BLE001 - reported per endpoint
        fail(f"/{name} raised {type(exc).__name__}: {str(exc)[:200]}")
    return list(result) if isinstance(result, tuple) else [result]


def every_endpoint_answers(ctx: Any) -> str:
    """Every live api_name the per-tab checks did not exercise answers a default call with
    non-empty output; unavailable cards are allowed here and named in the detail. A selector
    cascade (the Playground's `play_modules`, `play_functions`, `play_form`; the Races
    `race_sizes`) answers the default selection with value-less updates — it is the selection
    already applied, and the value guard keeps the form — so such an endpoint is asked once
    more for a changed selection and must answer that; the detail names the no-ops."""
    live = live_endpoints(ctx)
    covered = {endpoint_for(ctx, slug)[0] for slug in TAB_SLUGS if slug in expected_api_names()}
    rest = sorted(n for n in live if n not in covered)
    unavailable: list[str] = []
    noops: list[str] = []
    for name in rest:
        info = live[name]
        outputs = _call_named(ctx, name, info)
        texts = [t for t in texts_of(outputs) if t.strip()]
        if not texts and is_noop(outputs):
            overrides = changed_selection(info)
            if overrides:
                outputs = _call_named(ctx, name, info, overrides)
                texts = [t for t in texts_of(outputs) if t.strip()]
                noops.append(f"/{name}")
        if not texts:
            fail(f"/{name} returned no output")
        code = unavailable_code("\n".join(texts))
        if code:
            unavailable.append(f"/{name} {code}")
    tail = f"; unavailable: {', '.join(unavailable)}" if unavailable else ""
    if noops:
        tail += f"; no-op on the default selection, answered on a changed one: {', '.join(noops)}"
    return f"{len(rest)} further endpoints answered{tail}"


# ---------------------------------------------------------------------------
# Page-level checks
# ---------------------------------------------------------------------------


#: `algenta_spaces.boot` writes two clocks: `elapsed_s` is the boot (start to the last stage's
#: finish) and `uptime_s` start to now. An older snapshot has `elapsed_s` alone, and there it is
#: the uptime — so the boot is read from the stages' own start and finish times instead.
UPTIME_KEY = "uptime_s"
BOOT_KEY = "elapsed_s"


def boot_duration(snapshot: Mapping[str, Any]) -> float | None:
    """How long the boot took, in seconds — never how long the process has been up: the
    snapshot's `elapsed_s` when it also carries `uptime_s` (the two-clock snapshot), else the
    span from the first stage's start to the last stage's end, else None."""
    if UPTIME_KEY in snapshot:
        value = snapshot.get(BOOT_KEY)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    starts = []
    ends = []
    for stage in snapshot.get("stages") or []:
        if not isinstance(stage, Mapping):
            continue
        started, finished = stage.get("started_at"), stage.get("finished_at")
        if isinstance(started, int | float) and isinstance(finished, int | float):
            starts.append(float(started))
            ends.append(float(finished))
    if not starts:
        return None
    return max(0.0, max(ends) - min(starts))


def health_ready(ctx: Any) -> str:
    status_code, body = ctx.get(HEALTH_PATH)
    if status_code != 200:
        fail(f"{HEALTH_PATH} answered {status_code}")
    try:
        snapshot = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{HEALTH_PATH} is not JSON: {exc}")
    if not isinstance(snapshot, dict):
        fail(f"{HEALTH_PATH} is not the boot snapshot")
    ready = snapshot.get("ready")
    stage = str(snapshot.get("stage") or snapshot.get("status") or "").lower()
    if ready is not True and stage != "ready":
        error = snapshot.get("error")
        fail(f"{HEALTH_PATH} not ready" + (f": {error}" if error else ""))
    stages = snapshot.get("stages") or []
    boot_s = boot_duration(snapshot)
    tail = f", booted in {boot_s:.1f} s" if boot_s is not None else ""
    return f"ready, {len(stages)} stages{tail}"


# Gradio 6.28 inlines `window.gradio_config` with `>` and `<` as \u003e / \u003c; older builds
# and the /config route keep the literal characters. Both spellings are the same stamp; `dev`
# is what a local run without a staged .shared_sha prints. The shared shell prints the first
# twelve characters of the sha (the full one in the span's `title`, which may follow the class);
# the check compares the stamp as a prefix of the staged sha, so 12 and 64 hex both pass.
STAMP_RE = re.compile(
    r'alg-shell-stamp\\?"[^<>]{0,240}?(?:>|\\u003e)\s*build ([0-9a-f]{7,64}|dev)\s*(?:<|\\u003c)'
)


NATIVE_SUFFIXES = (".so", ".dylib")


def native_only(ctx: Any) -> str:
    """Every loaded family executes through its compiled Mojo shared library and nothing else:
    `/health` names, per family, the library (`.so` / `.dylib`), its ABI version, the Mojo
    toolchain and `loaded: true` read from the live ctypes handle (`hubkernel.native_proof`);
    a family without that proof, or with a Python-side substitute, fails."""
    status_code, body = ctx.get(HEALTH_PATH)
    if status_code != 200:
        fail(f"{HEALTH_PATH} answered {status_code}")
    try:
        snapshot = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{HEALTH_PATH} is not JSON: {exc}")
    facts = snapshot.get("facts") if isinstance(snapshot, dict) else None
    if not isinstance(facts, dict):
        fail(f"{HEALTH_PATH} carries no facts")
    families = list(facts.get("families_loaded") or [])
    kernels = facts.get("kernels") or {}
    if not families:
        fail("no family is loaded")
    problems: list[str] = []
    failing: set[str] = set()
    toolchains: set[str] = set()
    for family in families:
        native = (kernels.get(family) or {}).get("native")
        if not isinstance(native, dict):
            problems.append(f"{family}: no native proof")
            failing.add(family)
            continue
        library = str(native.get("library") or "")
        if not library.endswith(NATIVE_SUFFIXES):
            problems.append(f"{family}: library {library!r} is not a shared library")
        if native.get("loaded") is not True:
            problems.append(f"{family}: library not loaded ({native.get('error') or 'no handle'})")
        if native.get("abi_version") != 1:
            problems.append(f"{family}: ABI version {native.get('abi_version')!r}")
        mojo = str(native.get("mojo_version") or "")
        if not mojo.startswith("Mojo"):
            problems.append(f"{family}: toolchain {mojo!r}")
        toolchains.add(mojo)
        if any(item.startswith(f"{family}: ") for item in problems):
            failing.add(family)
    if problems:
        fail(f"{len(failing)} of {len(families)} families: {'; '.join(problems[:4])}")
    return (
        f"{len(families)} families execute through their compiled Mojo libraries"
        f" ({', '.join(sorted(toolchains))}), ABI 1, ctypes handles live"
    )


def shared_stamp(ctx: Any) -> str:
    expected = getattr(ctx, "expected_shared_sha", None)
    if not expected:
        skip("no staged .shared_sha given (local run); a deploy always passes one")
    status_code, page = ctx.get("/")
    if status_code != 200:
        fail(f"/ answered {status_code}")
    m = STAMP_RE.search(page)
    if m is None:
        fail("page has no build stamp in the footer")
    if not expected.startswith(m.group(1)):
        fail(f"stamp {m.group(1)[:12]} != staged {expected[:12]}")
    return f"shared {m.group(1)[:12]}"


# ---------------------------------------------------------------------------
# Browser audit — one Chromium session, cached per base URL
# ---------------------------------------------------------------------------

#: The class `app.py` keeps on `<html>` until the load handler has selected the tab; every
#: browser measurement waits for it to go, so nothing is measured on the held page.
BOOTING_CLASS = "alg-booting"
REVEAL_TIMEOUT_MS = 15_000
AUDIT_THEMES: tuple[str, ...] = ("light", "dark")
#: Layout shift budget per page load (Core Web Vitals "good" is 0.1; the flagship holds 0.05).
CLS_MAX = 0.05
CLS_LOADS = 3
CLS_OBSERVE_MS = 2_000
#: When the stock-chrome samples are taken after a run button is pressed.
CHROME_SAMPLE_MS: tuple[int, ...] = (100, 400, 800)
BUTTON_SELECTOR = "button, [role=button], a.alg-shell-nav-dup"
BUTTON_STATES: tuple[str, ...] = ("default", "hover", "focus", "disabled")
SELECTED_TAB_SELECTOR = "[role=tab][aria-selected=true]"
CODE_EDITOR_SELECTOR = ".cm-editor"
VALUE_BOX_SELECTOR = "input[type=number]"
CHECKBOX_SELECTOR = "input[type=checkbox]"
#: The nav and footer link rows: the `<ul>` lists (separators are `::before` glyphs on the items)
#: and the earlier inline spans (separators were their own `.alg-shell-sep` elements).
NAV_LINK_ROWS = (
    ".alg-shell-nav-list",
    ".alg-shell-footer-list",
    ".alg-shell-nav-links",
    ".alg-shell-footer-links",
)
NAV_SEPARATOR_CLASS = "alg-shell-sep"
#: Gradio's own status chrome: the "processing | 0.1s" line, the ETA bar, the generating border,
#: the toast; none of it may be visible while a run is in flight.
STOCK_CHROME_SELECTOR = (
    ".progress-text, .eta-bar, .meta-text, .meta-text-center, .progress-bar, .progress-level,"
    " .generating, .toast-body, .status .loading"
)
#: Chromium reports `visibility: hidden` and `display: none` nodes as unpainted, so the audit
#: keeps to what a visitor sees.
RUN_BUTTON_SELECTOR = "[role=tabpanel] .alg-run"
#: The dropdown's text input; a click opens its listbox, Escape closes it without a change.
COMBOBOX_SELECTOR = "input[role=combobox]"
LISTBOX_SELECTOR = "[role=listbox]"
OPTION_SELECTOR = "[role=listbox] [role=option]"
LISTBOX_TIMEOUT_MS = 3_000
#: Primary copy is every visible text node except: code and result blocks, form values,
#: the open listbox, the hidden restore box, and the chips that print an error code (the
#: fleet's one lowercase snake_case convention, `unavailable · <code>`).
COPY_EXCLUDE_SELECTOR = (
    ".cm-editor, code, pre, textarea, input, select, [role=listbox], .alg-restore,"
    " .alg-result, [data-kind=unavailable], .alg-chip-code, [data-code]"
)
#: An accordion: its header button is primary copy, its body is not.
ACCORDION_SELECTOR = ".alg-disclosure"
#: On the Playground the kernel contract's own labels are the copy: the parameter names in
#: the form and the function's dotted name on the result card. Nowhere else.
COPY_ALLOW_PLAY_SELECTOR = ".alg-form label, .alg-field label, .alg-play-card .alg-card-title"
COPY_ALLOW_PLAY_TAB = "play"
#: What may not appear in primary copy: a snake_case token, an ALL_CAPS name with an
#: underscore (an environment variable), a `torch<N>-` build-variant string, a raw URL.
IDENTIFIER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("snake_case", r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
    ("env_name", r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"),
    ("variant", r"\btorch\d+-[a-z0-9-]+"),
    ("url", r"https?://[^\s<>\"']+"),
)
CODE_CHIP_RE = re.compile(r"^unavailable · [a-z][a-z0-9_]*$")
#: The link box under the strip (a read-only Textbox) and the restore boxes the shell writes.
PERMALINK_BOX_SELECTOR = ".alg-permalink textarea, .alg-permalink input"
#: How long a restored form gets to settle after the boot hold lifts (the restore box's change
#: event runs after the load event that wrote it).
RESTORE_SETTLE_MS = 1200
#: The link shapes the permalink gate loads. `restored_in_full` marks the three controls: the
#: tab must restore every field the link names and the box must keep them; the other seven are
#: the shapes where the box once promised what the tab had not restored (an argument the form
#: does not carry, a foreign function, an unknown tab, a size the candidate does not offer).
PERMALINK_SHAPES: tuple[tuple[str, str, bool], ...] = (
    ("play_args_only", '?tab=play&args={"x":1}', False),
    ("play_bad_arg", '?tab=play&fn=geodesy.haversine_distance&args={"lat1":"north"}', False),
    (
        "try_decimal_arg",
        '?tab=try&args={"successes_a":12.5,"n_a":345,"successes_b":67,"n_b":890}',
        False,
    ),
    (
        "try_foreign_fn",
        "?tab=try&fn=text.fuzzy.levenshtein_distance"
        '&args={"successes_a":12,"n_a":345,"successes_b":67,"n_b":890}',
        False,
    ),
    ("unknown_tab", '?tab=nope&fn=text.fuzzy.levenshtein_distance&args={"a":"x"}', False),
    ("race_bad_size", '?tab=race&fn=text.fuzzy.levenshtein_distance&args={"size":"XL"}', False),
    ("race_non_candidate", '?tab=race&fn=ab_testing.z_test_proportions&args={"size":"M"}', False),
    (
        "play_levenshtein",
        '?tab=play&fn=text.fuzzy.levenshtein_distance&args={"a":"kitten","b":"sitting"}',
        True,
    ),
    ("race_levenshtein_L", '?tab=race&fn=text.fuzzy.levenshtein_distance&args={"size":"L"}', True),
    (
        "try_ints",
        "?tab=try&fn=ab_testing.z_test_proportions"
        '&args={"successes_a":12,"n_a":345,"successes_b":67,"n_b":890}',
        True,
    ),
)
PERMALINK_CONTEXTS: tuple[tuple[str, int, int, str], ...] = (
    ("desktop", 1440, 900, "light"),
    ("phone", 375, 812, "dark"),
)
#: The Races tab's one argument and the Try tab's hero, as the tabs spell them.
RACE_SIZE_PARAM = "size"
TRY_HERO_FALLBACK = "ab_testing.z_test_proportions"
#: How an open listbox may be dismissed without choosing; none may change the form.
DISMISSALS: tuple[str, ...] = ("click-away", "Tab", "Escape")
#: How long the form gets after a dismissal before it is read again (a cascade that fires by
#: mistake takes a server round trip to land; the gate must see it, not race it).
DISMISSAL_SETTLE_MS = 1500
#: The largest vertical gap a column may hold at 1440 px — between two consecutive elements,
#: or between a column's last element and the bottom of the row it shares with a taller one.
VOID_MAX_PX = 240
#: One refusal per tab: the control (its accessible name), the value that must be refused and a
#: word the message must carry. The Governed probe runs only where its controls are shown (a
#: key is set); the slider's number box is the control a visitor types into.
REFUSAL_PROBES: tuple[tuple[str, str, str, str], ...] = (
    ("try", "Successes A", "5000", "exceed"),
    ("play", "successes_a", "-5", "negative"),
    ("gov", "number input for Optimistic value", "1000", "optimistic"),
)
REFUSAL_CONTEXTS: tuple[tuple[str, int, int, str], ...] = (
    ("desktop", 1440, 900, "light"),
    ("phone", 375, 812, "dark"),
)
#: A field message counts as "under the control" within this many px below the control's box.
FIELD_MESSAGE_REACH_PX = 120
#: The status row's echo counts as "beside the action" within this many px of the run button.
STATUS_ECHO_REACH_PX = 160
REFUSAL_SETTLE_MS = 1500
#: Gradio's toast; never visible on this page.
TOAST_SELECTOR = ".toast-body"
#: The last toast sample after a run press, once the call has had time to answer.
LATE_SAMPLE_MS = 3000
#: How long a context waits for its last run to settle before the final toast sample.
IDLE_TIMEOUT_MS = 40_000
LOADING_CHIP_SELECTOR = "[data-kind=loading]"
#: The boot card under the "How this booted" disclosure.
BOOT_DISCLOSURE_SELECTOR = ".alg-boot-disclosure button"
BOOT_ROW_SELECTOR = ".alg-boot-row"
BOOT_TOLERANCE_S = 0.06  # one rounding step of the card's `0.0 s` format, plus slack
STAMP_SELECTOR = ".alg-shell-stamp"
STAMP_TEXT_RE = re.compile(r"^build ([0-9a-f]{7,64}|dev)$")
#: The first integer a double cannot hold: typed into a number box it must reach the request
#: exactly or be refused with a message, never silently become 2^53.
EXACT_INT = 2**53 + 1
EXACT_INT_FIELD = "n_a"
EXACT_INT_FAMILY = "stats"
EXACT_INT_MODULE = "ab_testing"
EXACT_INT_FUNCTION = "z_test_proportions"
EXACT_INT_ARGS: Mapping[str, int] = {"successes_a": 200, EXACT_INT_FIELD: EXACT_INT}
#: The refusal the contract prints for a JSON whole number at or above 2^53, in the detail.
REFUSAL_WORDS = playground.REASON_ABOVE_BROWSER_RANGE.split(";")[0]
FIELD_MESSAGE_SELECTOR = ".alg-field-msg, .alg-field-messages"
RESULT_TIMEOUT_MS = 40_000
#: What the receipt chip says about the engine: any of these words is a failed execution.
FAILED_STATUS_WORDS: tuple[str, ...] = (
    "fail",
    "error",
    "reject",
    "timeout",
    "timed_out",
    "undeliver",
    "denied",
)
#: The Governed receipt as `tabs.gov_tab` renders it (mirrored here so the verifier reads the
#: card without importing gradio): the card's title, the two statuses the chip spells out and
#: the words the webhook block paints only when the engine's POST landed.
RECEIPT_TITLE = "Execution receipt"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
CODE_WEBHOOK_FAILED = "webhook_failed"
WEBHOOK_RECEIVED_TEXT = "webhook received"
#: `delivered · HTTP 200`, `webhook_failed · HTTP 502`, `webhook_failed · no HTTP response`,
#: `engine <status> · …` — the status chip's text, with its tone class read from the span.
RECEIPT_CHIP_RE = re.compile(
    r'alg-chip alg-chip-(?P<tone>[a-z]+)"[^>]*>'
    r"(?P<text>(?:delivered|webhook_failed|engine [^<·]+?) · [^<]+)<"
)
RECEIPT_OK_TONE = cards.CHIP_KINDS["live"]
ERROR_CARD_CLASS = "alg-card-err"
DELIVERY_CLAIM = "reported delivery"
#: A webhook path that carries a nonce (`/hook/<24 url-safe bytes>`), anywhere it must not be.
HOOK_NONCE_RE = re.compile(r"/hook/[A-Za-z0-9_-]{16,}")
HOOK_URL_RE = re.compile(r"https?://[^\s<>\"']*/hook/[A-Za-z0-9_-]{16,}")
GUESSED_NONCE = "guessed-nonce-" + "0" * 18
REFUSED_POST_STATUSES: frozenset[int] = frozenset({400, 404, 405})
#: A family no container loads; the Playground must answer it with a coded card.
FOREIGN_FAMILY = "nope_family"
#: How the boot card's hero row spells a hero whose family never loaded (`/health` hero null).
NO_HERO_WORDS = "did not load"

# ---------------------------------------------------------------------------
# The run's phase: with or without the tenant key loaded into the app
# ---------------------------------------------------------------------------

PHASE_ENV = "ALGENTA_VERIFY_PHASE"
PHASE_NOKEY = "nokey"
PHASE_KEYED = "keyed"
PHASES: tuple[str, ...] = (PHASE_NOKEY, PHASE_KEYED)
_PHASE: dict[str, str] = {"value": PHASE_NOKEY}
#: What a keyed run measures that a no-key run cannot: these gates stay selected whatever
#: `--only` says, so a keyed phase never records a defect without failing on it (round 3's
#: keyed audits recorded axe's `scrollable-region-focusable` on the Engine responses block
#: with the gate left out of the run).
KEYED_REQUIRED: tuple[str, ...] = (
    "governed_lane",
    "receipt_tone",
    "webhook_privacy",
    "refusal_convention",
    "axe_serious_critical",
    "console_clean",
    "no_toasts",
    "voids",
)


def phase() -> str:
    return _PHASE["value"]


def set_phase(value: str) -> str:
    """Record the run's phase; an unknown name is refused."""
    if value not in PHASES:
        raise ValueError(f"phase must be one of {PHASES}, not {value!r}")
    _PHASE["value"] = value
    return value


def keyed() -> bool:
    return _PHASE["value"] == PHASE_KEYED


def select_checks(
    wanted: Collection[str], checks: Sequence[tuple[str, Callable[[Any], str]]] | None = None
) -> list[tuple[str, Callable[[Any], str]]]:
    """The checks a run performs: every check when `wanted` is empty, else the named ones —
    plus, in the keyed phase, every `KEYED_REQUIRED` gate whatever `wanted` left out."""
    checks = checks_for() if checks is None else list(checks)
    names = set(wanted)
    if names and keyed():
        names |= set(KEYED_REQUIRED)
    return [(n, fn) for n, fn in checks if not names or n in names]


@dataclass
class Audit:
    tabs: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    overflow: list[str] = field(default_factory=list)  # "phone/dark/try 412>375"
    small_targets: list[str] = field(default_factory=list)  # "phone/dark/try button.x 'Run' 88x36"
    targets_checked: int = 0
    axe_violations: list[str] = field(default_factory=list)
    axe_ran: bool = False
    axe_reason: str = ""
    contrast_failures: list[str] = field(default_factory=list)
    contrast_samples: int = 0
    button_contrast_failures: list[str] = field(default_factory=list)
    button_contrast_samples: int = 0
    button_sample_errors: list[str] = field(default_factory=list)  # a state that could not be read
    code_contrast_failures: list[str] = field(default_factory=list)
    code_contrast_samples: int = 0
    clipped_values: list[str] = field(default_factory=list)
    value_boxes_checked: int = 0
    stock_chrome: list[str] = field(default_factory=list)
    chrome_runs: list[str] = field(default_factory=list)  # "desktop/dark/try Run"
    chrome_samples: int = 0
    nav_separator_failures: list[str] = field(default_factory=list)
    nav_rows_checked: int = 0
    filled_checkboxes: list[str] = field(default_factory=list)
    checkboxes_checked: int = 0
    listboxes_opened: int = 0
    listbox_errors: list[str] = field(default_factory=list)  # a dropdown that would not open
    identifier_hits: list[str] = field(default_factory=list)  # "desktop/light/try .alg-card-sub …"
    copy_nodes: int = 0
    toasts: list[str] = field(default_factory=list)  # "desktop/light/gov Run +400 ms 'Error …'"
    toast_samples: int = 0
    run_presses: list[str] = field(default_factory=list)  # "desktop/light/play Run"
    dismissals: int = 0
    dismissal_failures: list[str] = field(default_factory=list)
    dismissal_errors: list[str] = field(default_factory=list)  # a listbox that would not open
    reopens: int = 0  # a click on the focused, closed box opened its list, form unchanged (round 5)
    reopen_failures: list[str] = field(default_factory=list)
    reopen_errors: list[str] = field(default_factory=list)
    boot_rows: list[dict[str, str]] = field(default_factory=list)  # stage, elapsed, detail
    boot_foot: str = ""
    boot_hero: dict[str, Any] | None = None  # /health's hero, read as the boot card was
    stamp_samples: list[dict[str, Any]] = field(default_factory=list)  # where, text, w, h, lines
    axe_views: int = 0  # how many tab views axe ran on
    code_blocks: int = 0  # visible Code blocks measured for stock chrome
    stock_code_chrome: list[str] = field(default_factory=list)  # "desktop/light/eco stock label …"
    void_samples: int = 0  # columns measured for voids
    voids: list[str] = field(default_factory=list)  # "desktop/light/llm after Run RMSNorm: …"


@dataclass
class RefusalAudit:
    """One refusal per tab and context: `probes` records what was typed and what the page
    answered, `failures` every place the convention was not kept, `skipped` a tab whose form
    was not shown (the Governed tab without a key)."""

    probes: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class PermalinkAudit:
    """One load per link shape and context: `loads` records the box and the selected tab,
    `failures` every promise the form did not keep."""

    loads: list[str] = field(default_factory=list)  # "desktop/light play_args_only ?tab=play"
    failures: list[str] = field(default_factory=list)


#: The viewports the Ecosystem table must fit at: the review's clipped widths and the desktop.
ECO_TABLE_WIDTHS: tuple[int, ...] = (900, 1024, 1152, 1200, 1440)


@dataclass
class EcoTableAudit:
    """The Hub table against its block at each `ECO_TABLE_WIDTHS` width: `samples` records
    what was measured, `failures` every width where the table outgrew or clipped."""

    samples: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


@dataclass
class ExactIntAudit:
    """What became of 2^53 + 1 typed into a Playground number box."""

    typed: str = ""
    request: str = ""  # the value the Request JSON carries, as text
    message: str = ""  # the field message, when the form refused it
    detail: str = ""


@dataclass
class ClsAudit:
    """Layout shift per page load: `loads` holds every measurement, `failures` those over budget."""

    edge_retries: int = 0

    loads: list[str] = field(default_factory=list)  # "desktop/try #1 0.0021"
    failures: list[str] = field(default_factory=list)  # "desktop/try #2 0.1313 (div.block, …)"
    worst: float = 0.0


_audits: dict[str, Audit] = {}
_cls_audits: dict[str, ClsAudit] = {}
_permalink_audits: dict[str, PermalinkAudit] = {}
_exact_int_audits: dict[str, ExactIntAudit] = {}
_refusal_audits: dict[str, RefusalAudit] = {}
_refusal_audit_errors: dict[str, str] = {}

# Shared colour arithmetic for the contrast gates: sRGB parsing, WCAG relative luminance,
# alpha blending, the effective background of an element (its own fill or the first opaque
# ancestor's, both blended, with the chain's `opacity` folded in) and the stops of a gradient
# fill. Every gate reports the smallest ratio it saw, never an average.
_JS_COLOR_LIB = """
  const parse = (s) => {
    const m = String(s || '').match(/rgba?\\(([^)]+)\\)/);
    if (m === null) return null;
    const p = m[1].split(/[\\s,\\/]+/).filter(x => x !== '').map(x => parseFloat(x));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const stops = (image) => {
    if (image === undefined || image === null || image === 'none') return [];
    if (image.indexOf('gradient') < 0) return [];
    const found = image.match(/rgba?\\([^)]*\\)/g) || [];
    return found.map(parse).filter(c => c !== null);
  };
  const lum = (c) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const blend = (top, under) => ({
    r: top.r * top.a + under.r * (1 - top.a),
    g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a), a: 1});
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  const opacityOf = (el) => {
    let o = 1;
    for (let n = el; n; n = n.parentElement) o *= parseFloat(getComputedStyle(n).opacity || '1');
    return o;
  };
  const bodyBg = () => parse(getComputedStyle(document.body).backgroundColor)
    || {r: 255, g: 255, b: 255, a: 1};
  const backgroundBehind = (el) => {
    let acc = null;
    for (let n = el.parentElement; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      const g = stops(cs.backgroundImage);
      const bg = g.length ? g[0] : parse(cs.backgroundColor);
      if (bg === null || bg.a === 0) continue;
      acc = acc ? blend(acc, bg) : bg;
      if (bg.a >= 1) return acc;
    }
    const body = bodyBg();
    return acc ? blend(acc, body) : body;
  };
  const fills = (el) => {
    const cs = getComputedStyle(el);
    const behind = backgroundBehind(el);
    const own = stops(cs.backgroundImage);
    const solid = parse(cs.backgroundColor);
    const layers = own.length ? own : (solid !== null && solid.a > 0 ? [solid] : []);
    const op = opacityOf(el);
    if (layers.length === 0) return [behind];
    return layers.map(c => blend({r: c.r, g: c.g, b: c.b, a: c.a * op}, behind));
  };
  const textOn = (el, fillsOf) => {
    const cs = getComputedStyle(el);
    const fill = cs.webkitTextFillColor;
    const fg = parse(fill && fill !== 'rgba(0, 0, 0, 0)' ? fill : cs.color);
    if (fg === null) return null;
    const op = opacityOf(el);
    let worst = Infinity;
    for (const f of fillsOf) {
      const eff = blend({r: fg.r, g: fg.g, b: fg.b, a: fg.a * op}, f);
      worst = Math.min(worst, ratio(eff, f));
    }
    return worst;
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const describe = (el) => (el.getAttribute('aria-label') || el.textContent || el.value || '')
    .trim().replace(/\\s+/g, ' ').slice(0, 40);
  const selectorOf = (el) => {
    const own = [...el.classList].filter(c => /^alg-/.test(c));
    const other = [...el.classList]
      .filter(c => /^svelte-/.test(c) === false && /^alg-/.test(c) === false);
    let sig = el.tagName.toLowerCase();
    if (own.length) sig += '.' + own[0]; else if (other.length) sig += '.' + other[0];
    const role = el.getAttribute('role');
    if (role) sig += '[role=' + role + ']';
    const aria = el.getAttribute('aria-label');
    if (aria) sig += '[aria-label="' + aria.slice(0, 24) + '"]';
    else if (el.tagName === 'INPUT' && el.type) sig += '[type=' + el.type + ']';
    return sig;
  };
"""

# What counts as the target: the element itself, except a form control. A radio or checkbox
# toggles from anywhere on its <label>, so the label is the pointer target; a text-like control
# (number, text, range, textarea, the dropdown's combobox) is the bordered field around it — the
# input itself when it carries the border, the wrap around a borderless inner input otherwise.
# Skipped: elements with tabindex="-1" (Gradio keeps a visually clipped, unfocusable copy of the
# tab strip for measuring, 1 px tall) and anything hidden or without a box.
_JS_TARGETS = (
    """
(sel) => {"""
    + _JS_COLOR_LIB
    + """
  const transparent = (c) => c === 'rgba(0, 0, 0, 0)' || c === 'transparent';
  const boxOf = (el) => {
    if (el.matches('input[type=radio], input[type=checkbox]')) return el.closest('label') || el;
    if (el.matches('input, textarea, select, [role=combobox]')) {
      let n = el;
      for (let depth = 0; n && depth < 6; n = n.parentElement, depth += 1) {
        const cs = getComputedStyle(n);
        const painted = transparent(cs.backgroundColor) === false;
        if (parseFloat(cs.borderTopWidth) > 0 || painted) return n;
        if (n.tagName === 'LABEL') break;
      }
      return el.closest('label') || el;
    }
    return el;
  };
  const out = [];
  let checked = 0;
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.getAttribute('tabindex') === '-1') continue;
    const r = boxOf(el).getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    checked += 1;
    if (r.width < 43.5 || r.height < 43.5) {
      const size = Math.round(r.width) + 'x' + Math.round(r.height);
      out.push(selectorOf(el) + " '" + describe(el) + "' " + size);
    }
  }
  return {checked, small: out};
}
"""
)

_JS_CONTRAST = (
    """
(selectors) => {"""
    + _JS_COLOR_LIB
    + """
  const failures = [];
  let samples = 0;
  for (const sel of selectors) {
    for (const el of document.querySelectorAll(sel)) {
      if (visible(el) === false) continue;
      const worst = textOn(el, fills(el));
      if (worst === null) continue;
      samples += 1;
      if (worst < 4.5) failures.push(sel + ' ' + worst.toFixed(2) + ':1');
    }
  }
  return {samples, failures};
}
"""
)

# One button in its current state: the text against every stop of its fill (a gradient hover
# fill is measured at each stop, so a pale end cannot hide behind a dark one).
_JS_BUTTON_STYLE = (
    """
(el) => {"""
    + _JS_COLOR_LIB
    + """
  const worst = textOn(el, fills(el));
  return {selector: selectorOf(el), label: describe(el), ratio: worst,
          disabled: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
          fills: fills(el).length};
}
"""
)

# Every token class CodeMirror painted inside each visible editor, light or dark: the first
# span of each class against the editor's fill, plus the plain line text and the gutter.
_JS_CODE_CONTRAST = (
    """
(editorSelector) => {"""
    + _JS_COLOR_LIB
    + """
  const failures = [];
  let samples = 0;
  for (const editor of document.querySelectorAll(editorSelector)) {
    if (visible(editor) === false) continue;
    const surface = fills(editor.querySelector('.cm-content') || editor);
    const seen = new Set();
    const nodes = [...editor.querySelectorAll('.cm-line, .cm-line *, .cm-gutterElement')];
    for (const node of nodes) {
      if (visible(node) === false || node.textContent.trim() === '') continue;
      const key = node.tagName + '.' + (node.className || 'plain');
      if (seen.has(key)) continue;
      seen.add(key);
      const worst = textOn(node, surface);
      if (worst === null) continue;
      samples += 1;
      if (worst < 4.5) {
        failures.push('.cm-editor ' + key.toLowerCase() + " '" + describe(node).slice(0, 16)
          + "' " + worst.toFixed(2) + ':1');
      }
    }
  }
  return {samples, failures};
}
"""
)

# A value box (the number input beside a slider, a form number) must sit inside its parent and
# its block, and its value must fit its own width — the slider head clipped the value once.
_JS_VALUE_BOXES = (
    """
(sel) => {"""
    + _JS_COLOR_LIB
    + """
  const inside = (inner, outer, slack) => inner.left >= outer.left - slack
    && inner.right <= outer.right + slack && inner.top >= outer.top - slack
    && inner.bottom <= outer.bottom + slack;
  const canvas = document.createElement('canvas').getContext('2d');
  const failures = [];
  let checked = 0;
  for (const el of document.querySelectorAll(sel)) {
    if (visible(el) === false) continue;
    checked += 1;
    const r = el.getBoundingClientRect();
    const owner = el.closest('label');
    const title = el.getAttribute('aria-label')
      || (owner ? owner.textContent.trim().split('\\n')[0] : '') || String(el.value);
    const name = selectorOf(el) + " '" + title.slice(0, 24) + "'";
    const parent = el.parentElement.getBoundingClientRect();
    if (inside(r, parent, 1) === false) {
      failures.push(name + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)
        + ' overflows its parent ' + Math.round(parent.width) + 'x' + Math.round(parent.height));
      continue;
    }
    const block = el.closest('.block, .row, .column, form');
    if (block !== null && inside(r, block.getBoundingClientRect(), 1) === false) {
      failures.push(name + ' overflows its block');
      continue;
    }
    const cs = getComputedStyle(el);
    canvas.font = cs.font;
    const text = canvas.measureText(String(el.value)).width;
    const room = el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    if (text > room + 0.5) {
      failures.push(name + " value '" + el.value + "' needs " + Math.round(text)
        + ' px, has ' + Math.round(room));
    }
  }
  return {checked, failures};
}
"""
)

# An unchecked checkbox in dark mode is an empty box: a saturated fill means the selected-state
# colour leaked into the resting state.
_JS_CHECKBOX_FILL = (
    """
(sel) => {"""
    + _JS_COLOR_LIB
    + """
  const saturation = (c) => {
    const r = c.r / 255, g = c.g / 255, b = c.b / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    if (max === min) return 0;
    const d = max - min;
    return l > 0.5 ? d / (2 - max - min) : d / (max + min);
  };
  const failures = [];
  let checked = 0;
  for (const el of document.querySelectorAll(sel)) {
    if (visible(el) === false || el.checked) continue;
    checked += 1;
    const fill = fills(el)[0];
    const label = describe(el.closest('label') || el);
    if (saturation(fill) > 0.25) {
      failures.push("input[type=checkbox] '" + label + "' fill rgb(" + Math.round(fill.r)
        + ', ' + Math.round(fill.g) + ', ' + Math.round(fill.b) + ')');
    }
  }
  return {checked, failures};
}
"""
)

# The nav wraps at 375 px: a separator glyph may sit between two links on one row, never at
# the start or the end of a row, never alone. A separator is either its own element
# (`.alg-shell-sep`) or a `::before` / `::after` glyph an item draws — an item that opens a
# wrapped row must not draw its leading glyph.
_JS_NAV_SEPARATORS = """
([rowSelectors, sepClass]) => {
  const failures = [];
  let rows = 0;
  const painted = (el, pseudo) => {
    const cs = getComputedStyle(el, pseudo);
    const text = cs.content;
    if (text === 'none' || text === 'normal' || text === '""' || text === "''") return '';
    if (cs.display === 'none' || cs.visibility === 'hidden') return '';
    if (parseFloat(cs.opacity) === 0 || parseFloat(cs.fontSize) === 0) return '';
    return text.replace(/^["']|["']$/g, '');
  };
  for (const rowSel of rowSelectors) {
    for (const container of document.querySelectorAll(rowSel)) {
      const items = [...container.children].filter(el => {
        const cs = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
      });
      const byRow = new Map();
      for (const el of items) {
        const top = Math.round(el.getBoundingClientRect().top);
        if (byRow.has(top) === false) byRow.set(top, []);
        byRow.get(top).push(el);
      }
      let index = 0;
      for (const [, row] of [...byRow.entries()].sort((a, b) => a[0] - b[0])) {
        rows += 1;
        index += 1;
        const first = row[0], last = row[row.length - 1];
        const at = rowSel + ' row ' + index;
        const sep = (el) => el.classList.contains(sepClass);
        const label = (el) => el.textContent.trim().slice(0, 24);
        if (row.length === 1 && sep(first)) failures.push(at + ' is a separator alone');
        else if (sep(first)) failures.push(at + " starts with '" + label(first) + "'");
        else if (painted(first, '::before') !== '') {
          failures.push(at + " starts with the glyph '" + painted(first, '::before')
            + "' before '" + label(first) + "'");
        }
        if (row.length > 1 && sep(last)) {
          failures.push(at + " ends with '" + label(last) + "'");
        } else if (row.length > 1 && painted(last, '::after') !== '') {
          failures.push(at + " ends with the glyph '" + painted(last, '::after')
            + "' after '" + label(last) + "'");
        }
      }
    }
  }
  return {rows, failures};
}
"""

# Stock Gradio chrome and stock colours while a run is in flight: the status text, ETA bar and
# generating border must stay hidden, and no painted colour may fall in Gradio's orange band
# (hue 15-40, saturated, mid-light) — the fleet's own tokens are resolved and exempt.
_JS_STOCK_CHROME = (
    """
([chromeSelector, tokenNames]) => {"""
    + _JS_COLOR_LIB
    + """
  const hsl = (c) => {
    const r = c.r / 255, g = c.g / 255, b = c.b / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b), l = (max + min) / 2;
    if (max === min) return {h: 0, s: 0, l};
    const d = max - min;
    const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    let h;
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) * 60;
    else if (max === g) h = ((b - r) / d + 2) * 60;
    else h = ((r - g) / d + 4) * 60;
    return {h, s, l};
  };
  const probe = document.createElement('span');
  document.body.appendChild(probe);
  const tokens = new Set();
  const rootStyle = getComputedStyle(document.documentElement);
  for (const name of tokenNames) {
    probe.style.color = rootStyle.getPropertyValue('--alg-' + name).trim();
    const c = parse(getComputedStyle(probe).color);
    if (c !== null) tokens.add([Math.round(c.r), Math.round(c.g), Math.round(c.b)].join(','));
  }
  probe.remove();
  const orange = (c) => {
    if (c === null || c.a === 0) return false;
    if (tokens.has([Math.round(c.r), Math.round(c.g), Math.round(c.b)].join(','))) return false;
    const x = hsl(c);
    return x.h >= 15 && x.h <= 40 && x.s >= 0.6 && x.l >= 0.35 && x.l <= 0.78;
  };
  const chrome = [];
  for (const el of document.querySelectorAll(chromeSelector)) {
    if (visible(el) === false) continue;
    chrome.push(selectorOf(el) + " '" + describe(el).slice(0, 24) + "'");
  }
  const oranges = [];
  let scanned = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (scanned > 6000) break;
    if (visible(el) === false) continue;
    scanned += 1;
    const cs = getComputedStyle(el);
    const colours = [cs.color, cs.backgroundColor, cs.borderTopColor, cs.borderBottomColor,
      cs.outlineColor].map(parse);
    for (const c of stops(cs.backgroundImage)) colours.push(c);
    for (const c of colours) {
      if (orange(c)) {
        oranges.push(selectorOf(el) + ' rgb(' + Math.round(c.r) + ', ' + Math.round(c.g)
          + ', ' + Math.round(c.b) + ')');
        break;
      }
    }
    if (oranges.length >= 5) break;
  }
  return {chrome, orange: oranges, scanned};
}
"""
)

# The open listbox: every option is a pointer target (44 px in both directions) and its text
# is read against the option's own fill — the highlighted or selected row included.
_JS_LISTBOX = (
    """
(sel) => {"""
    + _JS_COLOR_LIB
    + """
  const small = [];
  const failures = [];
  let checked = 0;
  let samples = 0;
  for (const el of document.querySelectorAll(sel)) {
    if (visible(el) === false) continue;
    const r = el.getBoundingClientRect();
    checked += 1;
    const label = describe(el).replace(/^✓\\s*/, '');
    const state = el.getAttribute('aria-selected') === 'true' ? ' selected' : '';
    if (r.width < 43.5 || r.height < 43.5) {
      small.push(selectorOf(el) + " '" + label + "'" + state + ' '
        + Math.round(r.width) + 'x' + Math.round(r.height * 10) / 10);
    }
    const worst = textOn(el, fills(el));
    if (worst === null) continue;
    samples += 1;
    if (worst < 4.5) failures.push(selectorOf(el) + " '" + label + "'" + state + ' '
      + worst.toFixed(2) + ':1');
  }
  return {checked, small, samples, failures};
}
"""
)

# Primary copy: every element with its own text, outside the excluded blocks and accordion
# bodies, scanned for the identifier patterns; the Playground's contract labels are allowed.
_JS_IDENTIFIERS = (
    """
([exclude, accordion, allow, allowTab, tab, patterns, codeChip]) => {"""
    + _JS_COLOR_LIB
    + """
  const regexes = patterns.map(([name, source]) => [name, new RegExp(source, 'g')]);
  const codeChipRe = new RegExp(codeChip);
  const headerOf = (acc) => acc.querySelector('button');
  const hits = [];
  let nodes = 0;
  for (const el of document.querySelectorAll('body *')) {
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(' ')
      .replace(/\\s+/g, ' ').trim();
    if (own === '') continue;
    if (visible(el) === false) continue;
    if (el.closest(exclude) !== null) continue;
    const acc = el.closest(accordion);
    if (acc !== null) {
      const header = headerOf(acc);
      if (header === null || header.contains(el) === false) continue;
    }
    if (codeChipRe.test(own)) continue;
    if (tab === allowTab && el.closest(allow) !== null) continue;
    nodes += 1;
    const found = [];
    for (const [name, re] of regexes) {
      for (const m of own.matchAll(re)) found.push(name + ':' + m[0]);
    }
    if (found.length) {
      hits.push({selector: selectorOf(el), text: own.slice(0, 80), tokens: found.slice(0, 6)});
    }
  }
  return {nodes, hits};
}
"""
)

_JS_OVERFLOW = """
() => ({scroll: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
        client: document.documentElement.clientWidth})
"""

# Installed before navigation: every layout shift without recent input, with the nodes that
# moved (removed nodes read `removed`), so a shift over budget names its cause.
_JS_CLS_INIT = """
window.__algShifts = [];
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (e.hadRecentInput) continue;
    window.__algShifts.push({v: e.value, t: Math.round(e.startTime),
      src: (e.sources || []).map(s => s.node
        ? (s.node.tagName.toLowerCase() + '.' + String(s.node.className || '').split(/\\s+/)
            .filter(c => c && /^svelte-/.test(c) === false).slice(0, 2).join('.'))
        : 'removed').slice(0, 3)});
  }
}).observe({type: 'layout-shift', buffered: true});
"""
_JS_CLS_READ = "() => window.__algShifts || []"
_JS_REVEALED = f"() => document.documentElement.classList.contains('{BOOTING_CLASS}') === false"

# The form of the displayed tab panel, control by control, with each control's label (the
# block's label text; `aria-label` when there is none): the dropdowns' comboboxes, the number
# and text inputs, the checked radios, the checkboxes and the JSON editors — plus the strip's
# selected tab and the link box. One snapshot serves the dismissal gate (before and after) and
# the permalink gate (what the tab restored).
_JS_FORM_STATE = """
() => {
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const labelOf = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    const own = el.closest('label');
    const block = el.closest('.alg-field, .block, .form') || own;
    const info = (own && own.querySelector('span[data-testid="block-info"]'))
      || (block && block.querySelector('span[data-testid="block-info"], label span, label'));
    const text = info ? info.textContent : (own ? own.textContent : '');
    return text.trim().split('\\n')[0].trim();
  };
  const panel = [...document.querySelectorAll('[role=tabpanel]')]
    .find(p => getComputedStyle(p).display !== 'none');
  const tab = document.querySelector('[role=tab][aria-selected=true]');
  const box = document.querySelector('.alg-permalink textarea, .alg-permalink input');
  const out = {selected: tab === null ? '' : (tab.getAttribute('data-tab-id') || ''),
               box: box === null ? '' : String(box.value),
               combos: [], nums: [], texts: [], radios: [], checks: [], jsons: [], fields: 0};
  if (panel === undefined) return out;
  for (const el of panel.querySelectorAll('input[role=combobox]')) {
    if (visible(el)) out.combos.push([labelOf(el), String(el.value)]);
  }
  for (const el of panel.querySelectorAll('input[type=number]')) {
    if (visible(el)) out.nums.push([labelOf(el), String(el.value)]);
  }
  for (const el of panel.querySelectorAll('input[type=text]:not([role=combobox]), textarea')) {
    if (visible(el) && el.closest('.alg-restore, .alg-permalink') === null) {
      out.texts.push([labelOf(el), String(el.value)]);
    }
  }
  for (const el of panel.querySelectorAll('input[type=radio]')) {
    if (el.checked) out.radios.push((el.closest('label') || el).textContent.trim());
  }
  for (const el of panel.querySelectorAll('input[type=checkbox]')) {
    if (visible(el)) out.checks.push([labelOf(el), el.checked]);
  }
  for (const el of panel.querySelectorAll('.alg-field .cm-content')) {
    if (visible(el)) out.jsons.push([labelOf(el), el.textContent]);
  }
  out.fields = [...panel.querySelectorAll('.alg-field')].filter(visible).length;
  return out;
}
"""
_JS_TOASTS = """
(sel) => [...document.querySelectorAll(sel)].filter(el => {
  const cs = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return cs.visibility !== 'hidden' && cs.display !== 'none' && r.width > 0 && r.height > 0;
}).map(el => el.textContent.trim().replace(/\\s+/g, ' ').slice(0, 80))
"""
_JS_BOOT_ROWS = """
(sel) => ({
  rows: [...document.querySelectorAll(sel)].map(r => ({
    stage: r.getAttribute('data-stage') || '',
    elapsed: (r.querySelector('.alg-boot-elapsed') || {textContent: ''}).textContent.trim(),
    detail: (r.querySelector('.alg-boot-detail') || {textContent: ''}).textContent.trim()})),
  foot: (document.querySelector('.alg-boot-foot') || {textContent: ''}).textContent.trim()})
"""
_JS_STAMP = """
(sel) => {
  const el = document.querySelector(sel);
  if (el === null) return null;
  const r = el.getBoundingClientRect();
  const line = parseFloat(getComputedStyle(el).lineHeight) || 20;
  return {text: el.textContent.trim(), w: Math.round(r.width), h: Math.round(r.height),
          lines: Math.max(1, Math.round(r.height / line))};
}
"""
_JS_RUN_DISABLED = "(el) => el.disabled === true || el.getAttribute('aria-disabled') === 'true'"
_JS_IDLE = f"() => document.querySelectorAll('{LOADING_CHIP_SELECTOR}').length === 0"
#: Every visible Code block: Gradio's stock block label (the `</>` icon and a caption above the
#: editor) and CodeMirror's line-number gutter are stock chrome the design replaces.
_JS_CODE_CHROME = """
(sel) => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const out = {blocks: 0, hits: []};
  for (const ed of document.querySelectorAll(sel)) {
    if (vis(ed) === false) continue;
    out.blocks += 1;
    const block = ed.closest('.block');
    const label = block === null ? null : block.querySelector('[data-testid="block-label"]');
    if (label !== null && vis(label)) {
      const icon = label.querySelector('svg');
      const text = label.textContent.trim().replace(/\\s+/g, ' ').slice(0, 32);
      out.hits.push((icon === null ? 'stock block label' : 'stock block label with the </> icon')
        + " '" + text + "'");
    }
    const numbers = ed.querySelector('.cm-lineNumbers');
    if (numbers !== null && vis(numbers)) {
      const lines = numbers.querySelectorAll('.cm-gutterElement').length;
      out.hits.push('line-number gutter (' + lines + ' lines)');
    }
  }
  return out;
}
"""
#: Every multi-column row of the displayed tab panel: the gap between consecutive visible
#: children of each column, and how far above the row's bottom the column's content ends.
_JS_VOIDS = """
(maxGap) => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const panel = [...document.querySelectorAll('[role=tabpanel]')].find(vis);
  const out = {columns: 0, voids: []};
  if (panel === undefined) return out;
  const rows = [...panel.querySelectorAll('.row')].filter(vis)
    .filter(r => r.getBoundingClientRect().width >= 700);
  for (const row of rows) {
    const cols = [...row.children].filter(vis).filter(c => c.classList.contains('column'));
    if (cols.length < 2) continue;
    const rowBottom = row.getBoundingClientRect().bottom;
    cols.forEach((col, i) => {
      out.columns += 1;
      const rects = [...col.children].filter(vis).map(k => k.getBoundingClientRect());
      for (let j = 1; j < rects.length; j++) {
        const gap = rects[j].top - rects[j - 1].bottom;
        if (gap > maxGap) {
          out.voids.push('column ' + (i + 1) + ' of ' + cols.length + ': ' + Math.round(gap)
            + ' px between elements ' + j + ' and ' + (j + 1));
        }
      }
      const bottoms = [...col.querySelectorAll('*')].filter(vis)
        .map(k => k.getBoundingClientRect().bottom);
      const content = bottoms.length ? Math.max(...bottoms) : col.getBoundingClientRect().top;
      const trailing = rowBottom - content;
      if (trailing > maxGap) {
        out.voids.push('column ' + (i + 1) + ' of ' + cols.length + ' ends ' + Math.round(trailing)
          + " px above the row's bottom");
      }
    });
  }
  return out;
}
"""
#: After a refused run: every visible field message (where it sits, whether it is the status
#: row's echo), the offending control's box, the run button's box, the status row's text, the
#: red cards and the toasts on the page.
_JS_REFUSAL = """
(controlName) => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const box = (el) => { const r = el.getBoundingClientRect();
    return {top: Math.round(r.top + scrollY), bottom: Math.round(r.bottom + scrollY),
            left: Math.round(r.left), right: Math.round(r.right)}; };
  const panel = [...document.querySelectorAll('[role=tabpanel]')].find(vis);
  if (panel === undefined) return null;
  const control = [...panel.querySelectorAll('input, textarea')].filter(vis)
    .find(el => el.getAttribute('aria-label') === controlName);
  const run = [...panel.querySelectorAll('.alg-run')].find(vis);
  const messages = [...panel.querySelectorAll('.alg-field-msg')].filter(vis).map(m => ({
    text: m.textContent.trim().replace(/\\s+/g, ' ').slice(0, 120),
    inStatus: m.closest('.alg-status') !== null, ...box(m)}));
  const status = [...panel.querySelectorAll('.alg-status')].filter(vis)
    .map(s => ({text: s.textContent.trim().replace(/\\s+/g, ' ').slice(0, 120), ...box(s)}));
  const codes = [...panel.querySelectorAll('[data-kind=unavailable]')].filter(vis)
    .map(c => c.textContent.trim().replace(/\\s+/g, ' ').slice(0, 60));
  return {control: control === undefined ? null : box(control),
          run: run === undefined ? null : box(run), messages, status, codes,
          redCards: [...panel.querySelectorAll('.alg-card-err')].filter(vis).length,
          toasts: [...document.querySelectorAll('.toast-body')].filter(vis).length};
}
"""


def _axe_source() -> tuple[str | None, str]:
    """axe.min.js from the `axe-playwright-python` package, or the reason it is absent."""
    try:
        pkg = importlib.import_module("axe_playwright_python")
    except ImportError:
        return None, "axe-playwright-python not installed"
    path = Path(pkg.__file__).resolve().parent / "axe.min.js"
    if not path.is_file():
        return None, f"{path} missing"
    return path.read_text(encoding="utf-8"), ""


TAB_SELECTED = "[role=tab][aria-selected=true]"
MORE_TABS_LABEL = "More tabs"
SELECT_TIMEOUT_MS = 10_000
#: How long a pointer click on a tab gets before the DOM click takes over (below).
SELECT_FIRST_TRY_MS = 2_500
#: The phone strip snaps its scroll: after the pointer click has scrolled a tab into view the
#: snap can move the strip under the pointer and the click lands on a neighbour (measured:
#: `race` clicked, `play` still selected). A DOM `click()` on the button cannot miss.
SNAP_SETTLE_MS = 300
WIDE_VIEWPORT = {"width": 1440, "height": 900}
_LABEL_CACHE: dict[str, str] = {}


def wait_for_reveal(page: Any, timeout_ms: int = REVEAL_TIMEOUT_MS) -> None:
    """Block until `app.py` has lifted the boot hold (`html.alg-booting` gone); a page built
    without the hold passes at once. Raises after `timeout_ms` — a held page is never measured."""
    page.wait_for_function(_JS_REVEALED, timeout=timeout_ms)


def fonts_missing(page: Any, families: Sequence[str] = ("Inter", "JetBrains Mono")) -> list[str]:
    """The web-font families the page has not loaded (a golden or audit taken with fallback
    glyphs is not reproducible, so the caller decides whether that is a failure)."""
    return [
        family
        for family in families
        if not page.evaluate("(f) => document.fonts.check('16px ' + JSON.stringify(f))", family)
    ]


def learn_tab_labels(page: Any) -> dict[str, str]:
    """Read the strip on the current page and remember the labels for narrow viewports."""
    _LABEL_CACHE.update(read_tab_labels(page))
    return dict(_LABEL_CACHE)


# Gradio 6 mounts a tab's panel on its first selection and keeps visited panels in the DOM,
# hidden; the signature is the panel that is displayed now, empty while none is.
_JS_PANEL_SIGNATURE = (
    "() => { const p = [...document.querySelectorAll('[role=tabpanel]')]"
    ".find(el => getComputedStyle(el).display !== 'none');"
    " return p && p.innerHTML.length > 100"
    " ? (p.innerHTML.length + ':' + p.innerHTML.slice(0, 300)) : ''; }"
)


def selected_tab(page: Any) -> str:
    """The `data-tab-id` (the tab id) of the selected tab, or its text when the id is absent."""
    return page.evaluate(
        "() => { const t = document.querySelector('[role=tab][aria-selected=true]');"
        " return t ? (t.getAttribute('data-tab-id') || t.textContent.trim()) : ''; }"
    )


def read_tab_labels(page: Any) -> dict[str, str]:
    """`data-tab-id -> label` of every tab button in the strip; complete on a wide viewport."""
    pairs = page.evaluate(
        "() => [...document.querySelectorAll('[role=tab][data-tab-id]')]"
        ".map(t => [t.getAttribute('data-tab-id'), t.textContent.trim()])"
    )
    return {slug: text for slug, text in pairs if slug and text}


def select_tab(page: Any, slug: str, label: str = "") -> None:
    """Bring the tab `slug` to the front: its own `[role=tab][data-tab-id]` button when it is in
    the strip, else through Gradio's "More tabs" overflow menu by label (given, or read from the
    strip at a wide viewport, or the tab module's LABEL). Waits for the boot hold to lift first.
    Raises RuntimeError when the tab is not selected afterwards — a capture or audit of the
    wrong tab is never silent."""
    wait_for_reveal(page)
    if selected_tab(page) == slug:
        return
    if not label:
        label = _LABEL_CACHE.get(slug) or tab_labels().get(slug, "")
    before = page.evaluate(_JS_PANEL_SIGNATURE)
    button = page.locator(f'[role=tab][data-tab-id="{slug}"]')
    if button.count() and button.first.is_visible():
        button.first.click()
    else:
        more = page.get_by_role("button", name=MORE_TABS_LABEL)
        if not more.count():
            raise RuntimeError(
                f"tab {slug!r} is neither in the strip nor behind {MORE_TABS_LABEL!r}"
            )
        more.first.click()
        item = page.locator(f'button[data-tab-id="{slug}"]:visible')
        if not item.count() and label:
            item = page.get_by_role("button", name=label, exact=True).filter(visible=True)
        if not item.count():
            raise RuntimeError(
                f"tab {slug!r} ({label!r}) not found in the {MORE_TABS_LABEL!r} menu"
            )
        item.first.click()
    _await_selected(page, slug, before, button if button.count() else None)


_JS_TAB_SELECTED_WITH_PANEL = (
    "([slug, before, sig]) => {"
    " const t = document.querySelector('[role=tab][aria-selected=true]');"
    " if (t === null || t.getAttribute('data-tab-id') !== slug) return false;"
    " const now = eval(sig)(); return now !== '' && now !== before; }"
)


def _await_selected(page: Any, slug: str, before: str, button: Any | None) -> None:
    """Wait until the strip shows `slug` and its panel is displayed and differs from the one
    before (the button flips before the panel mounts, so the button alone races the content).
    When a pointer click did not take — a scroll-snapping strip moved under it — the button is
    scrolled into view, the snap given time to settle, and clicked through the DOM instead."""
    arg = [slug, before, _JS_PANEL_SIGNATURE]
    try:
        page.wait_for_function(_JS_TAB_SELECTED_WITH_PANEL, arg=arg, timeout=SELECT_FIRST_TRY_MS)
        return
    except Exception:  # noqa: BLE001 - the pointer click missed; try the DOM click below
        if button is None:
            raise
    log.info("tab %r: pointer click did not select it; clicking through the DOM", slug)
    button.first.scroll_into_view_if_needed()
    page.wait_for_timeout(SNAP_SETTLE_MS)
    button.first.evaluate("el => el.click()")
    page.wait_for_function(_JS_TAB_SELECTED_WITH_PANEL, arg=arg, timeout=SELECT_TIMEOUT_MS)


def _tab_buttons(page: Any) -> list[Any]:
    buttons = page.locator("[role=tab]")
    return [buttons.nth(i) for i in range(buttons.count())]


def _open_page(context: Any, base_url: str, audit: Audit | None, url_suffix: str = "") -> Any:
    """A page on the app with the console captured, the boot hold lifted and the fonts landed."""
    page = context.new_page()
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    if audit is not None:
        page.on(
            "console",
            lambda msg: (
                audit.console_errors.append(f"{msg.type}: {msg.text[:200]}")
                if msg.type == "error"
                else None
            ),
        )
        page.on("pageerror", lambda err: audit.page_errors.append(str(err)[:200]))
    page.goto(base_url + url_suffix, wait_until="domcontentloaded")
    page.wait_for_selector(".alg-shell-stamp", state="attached")
    wait_for_reveal(page)
    try:  # web fonts change glyph metrics, hence target sizes; wait for them
        page.wait_for_function(FONTS_READY_JS, timeout=FONTS_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001 - a slow font host is not a failed audit
        log.warning("web fonts not ready after %d ms: %s", FONTS_TIMEOUT_MS, exc)
    page.wait_for_timeout(SETTLE_MS)
    return page


# Gradio keeps a clipped, unfocusable copy of the tab strip (tabindex="-1", 1 px tall) for
# measuring; it is never a pointer target.
_JS_BUTTON_MEASURABLE = (
    "(el) => el.getAttribute('tabindex') !== '-1' && el.closest('.visually-hidden') === null"
)


def _sample_buttons(page: Any, where: str, audit: Audit) -> None:
    """Contrast of every visible button's text in its resting state, then one button per
    selector signature in its hover and focus states (the pointer and the keyboard reach one
    of each kind — the others share its stylesheet), the disabled ones as they are, and the
    selected tab's label. Hover is the pointer moved to the button's centre (`page.mouse`), so
    a button another element overlaps is sampled where it stands rather than skipped."""
    handles = [h for h in page.query_selector_all(BUTTON_SELECTOR) if h.is_visible()]
    seen_states: set[tuple[str, str]] = set()
    for handle in handles:
        try:
            if not handle.evaluate(_JS_BUTTON_MEASURABLE):
                continue
            info = handle.evaluate(_JS_BUTTON_STYLE)
        except Exception as exc:  # noqa: BLE001 - a detached node is not a failed audit
            log.debug("button sample skipped: %s", exc)
            continue
        if info["ratio"] is None:
            continue
        state = "disabled" if info["disabled"] else "default"
        _record_button(audit, where, state, info)
        if info["disabled"]:
            continue
        for state in ("hover", "focus"):
            key = (info["selector"], state)
            if key in seen_states:
                continue
            seen_states.add(key)
            try:
                if state == "hover":
                    box = handle.bounding_box()
                    if box is None:
                        continue
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                else:
                    handle.focus()
                page.wait_for_timeout(260)  # motion is 150-200 ms; the end state is what counts
                styled = handle.evaluate(_JS_BUTTON_STYLE)
            except Exception as exc:  # noqa: BLE001 - reported as a failed sample, not a crash
                first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
                audit.button_sample_errors.append(
                    f"{where} {info['selector']} {state}: {first_line[:120]}"
                )
                continue
            if styled["ratio"] is not None:
                _record_button(audit, where, state, styled)
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")
    page.mouse.move(0, 0)
    tab = page.query_selector(SELECTED_TAB_SELECTOR)
    if tab is not None and tab.is_visible():
        info = tab.evaluate(_JS_BUTTON_STYLE)
        if info["ratio"] is not None:
            _record_button(audit, where, "selected", info)


def _record_button(audit: Audit, where: str, state: str, info: Mapping[str, Any]) -> None:
    audit.button_contrast_samples += 1
    if info["ratio"] < CONTRAST_MIN:
        audit.button_contrast_failures.append(
            f"{where} {info['selector']} '{info['label']}' {state} {info['ratio']:.2f}:1"
        )


def _run_button(page: Any) -> Any | None:
    """The visible run button of the displayed tab panel, or None."""
    button = page.locator(RUN_BUTTON_SELECTOR).filter(visible=True)
    return button.first if button.count() else None


def _sample_toasts(page: Any, where: str, audit: Audit) -> None:
    """One look for a visible toast, recorded with where and when it was taken."""
    audit.toast_samples += 1
    for text in page.evaluate(_JS_TOASTS, TOAST_SELECTOR):
        audit.toasts.append(f"{where} '{text}'")


def _press_run(page: Any, where: str, audit: Audit, *, chrome: bool) -> str:
    """Press the displayed tab's run button and sample the page at each sample time: toasts
    always, Gradio's stock chrome and colours when `chrome` is set (the Try and Ecosystem
    presses the stock-chrome gate counts). A disabled run button (the Governed tab without a
    key) is recorded as such and not pressed. Returns the button's label when it was pressed,
    else an empty string."""
    button = _run_button(page)
    if button is None:
        return ""
    name = (button.inner_text() or "run").strip()
    if button.evaluate(_JS_RUN_DISABLED):
        audit.run_presses.append(f"{where} {name} (disabled)")
        return ""
    button.click()
    audit.run_presses.append(f"{where} {name}")
    if chrome:
        audit.chrome_runs.append(f"{where} {name}")
    elapsed = 0
    for at in (*CHROME_SAMPLE_MS, LATE_SAMPLE_MS):
        page.wait_for_timeout(max(at - elapsed, 0))
        elapsed = at
        _sample_toasts(page, f"{where} {name} +{at} ms", audit)
        if chrome and at in CHROME_SAMPLE_MS:
            sample = page.evaluate(_JS_STOCK_CHROME, [STOCK_CHROME_SELECTOR, list(_TOKEN_NAMES)])
            audit.chrome_samples += 1
            for item in sample["chrome"]:
                audit.stock_chrome.append(f"{where} {name} +{at} ms {item}")
            for item in sample["orange"]:
                audit.stock_chrome.append(f"{where} {name} +{at} ms orange {item}")
    return name


def _sample_run_chrome(page: Any, where: str, audit: Audit) -> str:
    """Press the tab's run button and look for stock chrome (and toasts) at each sample time."""
    return _press_run(page, where, audit, chrome=True)


def _measure_voids(page: Any, where: str, audit: Audit) -> None:
    """Every multi-column row of the displayed panel at 1440 px: no gap over `VOID_MAX_PX`
    between consecutive elements of a column, and no column ending that far above its row."""
    result = page.evaluate(_JS_VOIDS, VOID_MAX_PX)
    audit.void_samples += int(result["columns"])
    audit.voids += [f"{where}: {item}" for item in result["voids"]]


def _scan_code_chrome(page: Any, where: str, audit: Audit) -> None:
    """Open every closed disclosure of the displayed panel so its Code blocks are visible, read
    the stock chrome on each (block label, line numbers), close the disclosures again."""
    headers = page.locator(f"[role=tabpanel] {ACCORDION_SELECTOR} button").filter(visible=True)
    opened: list[Any] = []
    for index in range(headers.count()):
        header = headers.nth(index)
        if header.get_attribute("aria-expanded") == "false":
            header.click()
            opened.append(header)
    if opened:
        page.wait_for_timeout(SNAP_SETTLE_MS)
    result = page.evaluate(_JS_CODE_CHROME, CODE_EDITOR_SELECTOR)
    audit.code_blocks += int(result["blocks"])
    audit.stock_code_chrome += [f"{where} {hit}" for hit in result["hits"]]
    for header in reversed(opened):
        header.click()
    if opened:
        page.wait_for_timeout(SNAP_SETTLE_MS)


def _wait_idle(page: Any, timeout_ms: int = IDLE_TIMEOUT_MS) -> bool:
    """Wait until no loading chip is left on the page (every pressed run has answered)."""
    try:
        page.wait_for_function(_JS_IDLE, timeout=timeout_ms)
    except Exception:  # noqa: BLE001 - a run still in flight is reported by the caller
        return False
    return True


def _form_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """What changed between two form snapshots, control by control, in words."""
    changes: list[str] = []
    for key in ("combos", "nums", "texts", "checks", "jsons"):
        was = {label or f"{key}{i}": value for i, (label, value) in enumerate(before.get(key, []))}
        now = {label or f"{key}{i}": value for i, (label, value) in enumerate(after.get(key, []))}
        for label in sorted(set(was) | set(now)):
            if was.get(label) != now.get(label):
                changes.append(f"{label} {was.get(label, '—')!r} -> {now.get(label, '—')!r}")
    if before.get("radios") != after.get("radios"):
        changes.append(f"radio {before.get('radios')} -> {after.get('radios')}")
    if before.get("fields") != after.get("fields"):
        changes.append(f"{before.get('fields')} fields -> {after.get('fields')}")
    return changes


def _dismiss_listboxes(page: Any, where: str, audit: Audit) -> None:
    """Open every visible dropdown of the displayed tab and dismiss it three ways without
    choosing — a click away from it, Tab, Escape — comparing the form before and after each:
    a dismissal that changes any control, or the number of fields, is a failure."""
    boxes = page.locator(f"{COMBOBOX_SELECTOR}:visible")
    for index in range(boxes.count()):
        box = boxes.nth(index)
        name = box.get_attribute("aria-label") or box.input_value() or f"dropdown {index + 1}"
        for how in DISMISSALS:
            before = page.evaluate(_JS_FORM_STATE)
            try:
                box.click()
                page.wait_for_selector(
                    LISTBOX_SELECTOR, state="visible", timeout=LISTBOX_TIMEOUT_MS
                )
                page.wait_for_timeout(200)
                if how == "click-away":
                    page.locator(".alg-shell-title").first.click()
                else:
                    page.keyboard.press(how)
                page.wait_for_timeout(DISMISSAL_SETTLE_MS)  # a cascade, if one fires, lands
                still_open = box.get_attribute("aria-expanded") == "true"
                if page.locator(LISTBOX_SELECTOR).filter(visible=True).count():
                    page.keyboard.press("Escape")  # Tab may have opened the next dropdown
                    page.wait_for_timeout(200)
            except Exception as exc:  # noqa: BLE001 - reported as a sample that could not be read
                first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
                audit.dismissal_errors.append(
                    f"{where} '{name.strip()[:24]}' {how}: {first_line[:120]}"
                )
                page.keyboard.press("Escape")
                continue
            audit.dismissals += 1
            after = page.evaluate(_JS_FORM_STATE)
            changes = _form_diff(before, after)
            if still_open:
                changes.insert(0, "listbox stayed open")
            if changes:
                audit.dismissal_failures.append(
                    f"{where} '{name.strip()[:24]}' {how}: {'; '.join(changes[:3])}"
                )
            if how == "Escape":
                # the box keeps focus with its list closed: the mouse must reopen it (round 5)
                _probe_reopen(page, box, name, where, audit, "click after Escape")
                _probe_reopen_after_tab(page, box, name, where, audit)
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")


#: When the Tab-arrival probe looks for a painted listbox: at once, then across the first frames.
ARRIVAL_SAMPLE_MS: tuple[int, ...] = (0, 40, 80, 120)
#: A listbox counts as painted when it is in the DOM and its panel is displayed (not `none`).
_JS_LISTBOX_PAINTED = """
() => [...document.querySelectorAll('[role=listbox]')].filter(el => {
  const panel = el.closest('div.options') || el;
  const style = getComputedStyle(panel);
  const shown = style.display !== 'none' && style.visibility !== 'hidden';
  return shown && el.getClientRects().length > 0;
}).length
"""


def _probe_reopen(page: Any, box: Any, name: str, where: str, audit: Audit, label: str) -> None:
    """Click the focused, closed box: its list must show without the form changing; Escape
    closes it again so the box is left as it was found (focused, closed)."""
    before = page.evaluate(_JS_FORM_STATE)
    try:
        if (
            box.get_attribute("aria-expanded") == "true"
            or page.locator(LISTBOX_SELECTOR).filter(visible=True).count()
        ):
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
        box.click()
        try:
            page.wait_for_selector(LISTBOX_SELECTOR, state="visible", timeout=LISTBOX_TIMEOUT_MS)
        except Exception:  # noqa: BLE001 - the timeout is the finding
            audit.reopen_failures.append(
                f"{where} '{name.strip()[:24]}' {label}: no listbox within {LISTBOX_TIMEOUT_MS} ms"
            )
            return
        page.wait_for_timeout(200)
        after = page.evaluate(_JS_FORM_STATE)
        changes = _form_diff(before, after)
        # a click is a reopen or a failure, never both: `reopens + len(reopen_failures)` is the
        # click count the gate reports (Codna review on #1150 found a changed form counted twice)
        if changes:
            audit.reopen_failures.append(
                f"{where} '{name.strip()[:24]}' {label}: {'; '.join(changes[:3])}"
            )
        else:
            audit.reopens += 1
    except Exception as exc:  # noqa: BLE001 - reported as a probe that could not be read
        audit.reopen_errors.append(
            f"{where} '{name.strip()[:24]}' {label}: {_first_line_of(exc)[:120]}"
        )
    finally:
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)


def _probe_reopen_after_tab(page: Any, box: Any, name: str, where: str, audit: Audit) -> None:
    """Leave the box with Shift+Tab, come back with Tab (the shell closes the list Gradio opens
    on arrival), then click it: the list must show."""
    try:
        page.keyboard.press("Shift+Tab")
        page.wait_for_timeout(200)
        page.keyboard.press("Tab")
        # the list must never paint on arrival (round 6: a ghost for one to four frames) —
        # sample right away and across the first frames
        painted = []
        for delay in ARRIVAL_SAMPLE_MS:
            page.wait_for_timeout(delay)
            painted.append(int(page.evaluate(_JS_LISTBOX_PAINTED)))
        if any(painted):
            audit.reopen_failures.append(
                f"{where} '{name.strip()[:24]}' Tab-arrival: a listbox painted"
                f" (samples {painted} at +{'/'.join(str(d) for d in ARRIVAL_SAMPLE_MS)} ms)"
            )
        page.wait_for_timeout(300)
        focused = page.evaluate(
            "() => document.activeElement && document.activeElement.getAttribute('role')"
        )
        if focused != "combobox":
            audit.reopen_errors.append(
                f"{where} '{name.strip()[:24]}' Tab-arrival: focus landed on {focused!r}"
            )
            return
    except Exception as exc:  # noqa: BLE001 - reported as a probe that could not be read
        audit.reopen_errors.append(
            f"{where} '{name.strip()[:24]}' Tab-arrival: {_first_line_of(exc)[:120]}"
        )
        return
    _probe_reopen(page, box, name, where, audit, "click after Tab-arrival")


def _read_boot_card(page: Any, audit: Audit, base_url: str = "") -> None:
    """Open the boot disclosure, read every stage row and the foot, close it again — and read
    `/health`'s hero at the same moment, so the hero row can be held to what the page knew."""
    header = page.locator(BOOT_DISCLOSURE_SELECTOR).first
    if not header.count():
        return
    header.click()
    page.wait_for_selector(BOOT_ROW_SELECTOR, state="visible", timeout=LISTBOX_TIMEOUT_MS)
    page.wait_for_timeout(260)
    result = page.evaluate(_JS_BOOT_ROWS, BOOT_ROW_SELECTOR)
    audit.boot_rows = [dict(row) for row in result["rows"]]
    audit.boot_foot = str(result["foot"])
    if base_url:
        try:  # the body at any status: a 503 snapshot still carries the hero
            body = page.request.get(base_url.rstrip("/") + HEALTH_PATH, timeout=PAGE_TIMEOUT_MS)
            health = json.loads(body.text())
        except Exception as exc:  # noqa: BLE001 - the gate names a hero that was not read
            log.warning("%s not read beside the boot card: %s", HEALTH_PATH, exc)
            health = None
        hero = health.get("hero") if isinstance(health, dict) else None
        audit.boot_hero = dict(hero) if isinstance(hero, dict) else None
    header.click()
    page.wait_for_timeout(260)


def _read_stamp(page: Any, where: str, audit: Audit) -> None:
    """The footer stamp's text and rendered line count in this context."""
    sample = page.evaluate(_JS_STAMP, STAMP_SELECTOR)
    if sample is not None:
        audit.stamp_samples.append({"where": where, **sample})


def _fill_snippet(page: Any) -> None:
    """On the Try tab, press the install chip so its Code block has tokens to measure."""
    try:
        module = importlib.import_module(f"{TABS_PACKAGE}.try{TAB_MODULE_SUFFIX}")
        label = str(getattr(module, "LABEL_INSTALL", "")).strip()
    except Exception:  # noqa: BLE001 - the tab may not be part of this build
        return
    if not label:
        return
    chip = page.get_by_role("button", name=label, exact=True).filter(visible=True)
    if chip.count():
        chip.first.click()
        page.wait_for_selector(f"{CODE_EDITOR_SELECTOR} .cm-line", state="visible", timeout=10_000)
        page.wait_for_timeout(SETTLE_MS)


def _open_listboxes(page: Any, where: str, audit: Audit) -> None:
    """Open every visible dropdown in turn, measure its options as targets and their text
    contrast, close it with Escape. A dropdown that does not open is a failed sample."""
    boxes = page.locator(f"{COMBOBOX_SELECTOR}:visible")
    for index in range(boxes.count()):
        box = boxes.nth(index)
        name = box.get_attribute("aria-label") or box.input_value() or f"dropdown {index + 1}"
        try:
            box.click()
            page.wait_for_selector(LISTBOX_SELECTOR, state="visible", timeout=LISTBOX_TIMEOUT_MS)
            page.wait_for_timeout(200)  # motion is 150-200 ms; the end state is what counts
            result = page.evaluate(_JS_LISTBOX, OPTION_SELECTOR)
        except Exception as exc:  # noqa: BLE001 - reported as a sample that could not be read
            first_line = str(exc).strip().splitlines()[0] if str(exc).strip() else repr(exc)
            audit.listbox_errors.append(f"{where} '{name.strip()[:24]}': {first_line[:120]}")
            page.keyboard.press("Escape")
            continue
        audit.listboxes_opened += 1
        audit.targets_checked += int(result["checked"])
        audit.small_targets += [f"{where} {t}" for t in result["small"]]
        audit.contrast_samples += int(result["samples"])
        audit.contrast_failures += [f"{where} {c}" for c in result["failures"]]
        page.keyboard.press("Escape")
        try:
            page.wait_for_selector(LISTBOX_SELECTOR, state="hidden", timeout=LISTBOX_TIMEOUT_MS)
        except Exception as exc:  # noqa: BLE001 - a listbox that stays open is named, not fatal
            audit.listbox_errors.append(f"{where} '{name.strip()[:24]}' did not close: {exc!s:.80}")
    page.evaluate("() => { if (document.activeElement) document.activeElement.blur(); }")


def _scan_identifiers(page: Any, where: str, tab_name: str, audit: Audit) -> None:
    """Every identifier-like token in the tab's primary copy, by selector signature."""
    result = page.evaluate(
        _JS_IDENTIFIERS,
        [
            COPY_EXCLUDE_SELECTOR,
            ACCORDION_SELECTOR,
            COPY_ALLOW_PLAY_SELECTOR,
            COPY_ALLOW_PLAY_TAB,
            tab_name,
            [list(p) for p in IDENTIFIER_PATTERNS],
            CODE_CHIP_RE.pattern,
        ],
    )
    audit.copy_nodes += int(result["nodes"])
    for hit in result["hits"]:
        tokens = ", ".join(str(t).split(":", 1)[1] for t in hit["tokens"])
        audit.identifier_hits.append(f"{where} {hit['selector']} '{tokens}' in '{hit['text']}'")


def _measure_step(
    page: Any, where: str, label: str, theme: str, tab_name: str, audit: Audit, axe_js: str | None
) -> None:
    overflow = page.evaluate(_JS_OVERFLOW)
    if overflow["scroll"] > overflow["client"]:
        audit.overflow.append(f"{where} {overflow['scroll']}>{overflow['client']}")
    targets = page.evaluate(_JS_TARGETS, TARGET_SELECTOR)
    audit.targets_checked += int(targets["checked"])
    audit.small_targets += [f"{where} {t}" for t in targets["small"]]
    contrast = page.evaluate(_JS_CONTRAST, list(CONTRAST_SELECTORS))
    audit.contrast_samples += int(contrast["samples"])
    audit.contrast_failures += [f"{where} {c}" for c in contrast["failures"]]
    code = page.evaluate(_JS_CODE_CONTRAST, CODE_EDITOR_SELECTOR)
    audit.code_contrast_samples += int(code["samples"])
    audit.code_contrast_failures += [f"{where} {c}" for c in code["failures"]]
    boxes = page.evaluate(_JS_VALUE_BOXES, VALUE_BOX_SELECTOR)
    audit.value_boxes_checked += int(boxes["checked"])
    audit.clipped_values += [f"{where} {c}" for c in boxes["failures"]]
    if theme == "dark":
        fill = page.evaluate(_JS_CHECKBOX_FILL, CHECKBOX_SELECTOR)
        audit.checkboxes_checked += int(fill["checked"])
        audit.filled_checkboxes += [f"{where} {c}" for c in fill["failures"]]
    if label == "phone" and tab_name == "landing":
        nav = page.evaluate(_JS_NAV_SEPARATORS, [list(NAV_LINK_ROWS), NAV_SEPARATOR_CLASS])
        audit.nav_rows_checked += int(nav["rows"])
        audit.nav_separator_failures += [f"{where} {c}" for c in nav["failures"]]
    _sample_buttons(page, where, audit)
    if axe_js:  # every tab view, every viewport, every theme, every phase
        page.evaluate(axe_js)
        result = page.evaluate("async () => await axe.run(document, {resultTypes: ['violations']})")
        audit.axe_ran = True
        audit.axe_views += 1
        for violation in result.get("violations", []):
            if violation.get("impact") in AXE_IMPACTS:
                nodes = violation.get("nodes", [])
                first = ", ".join(nodes[0].get("target", [])) if nodes else ""
                audit.axe_violations.append(
                    f"{where} {violation['id']} ({violation['impact']},"
                    f" {len(nodes)} node{'s' if len(nodes) != 1 else ''}"
                    f"{': ' + first if first else ''})"
                )
    if label == "desktop" and theme == AUDIT_THEMES[0]:
        _scan_identifiers(page, where, tab_name, audit)  # the copy is the same in every theme
    _open_listboxes(page, where, audit)


_TOKEN_NAMES: tuple[str, ...] = tuple(design.COLOR_TOKENS)


def run_audit(base_url: str, slugs: Sequence[str] | None = None) -> Audit:
    """Load the app at each audit viewport in light and dark, bring every tab (`slugs`, default
    the contract's) to the front in turn and collect the page facts; on the desktop the Try and
    Ecosystem run buttons are pressed once per theme and the page sampled while the call runs."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    audit = Audit()
    slugs = tuple(tab_slugs()) if slugs is None else tuple(slugs)
    axe_js, axe_reason = _axe_source()
    audit.axe_reason = axe_reason
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for label, width, height in AUDIT_VIEWPORTS:
                for theme in AUDIT_THEMES:
                    context = browser.new_context(
                        viewport={"width": width, "height": height}, color_scheme=theme
                    )
                    page = _open_page(context, base_url, audit)
                    steps: list[tuple[str, Callable[[], None] | None]] = [("landing", None)]
                    labels = {**tab_labels(), **learn_tab_labels(page)}
                    if slugs:
                        for slug in slugs:
                            steps.append(
                                (
                                    slug,
                                    lambda s=slug, pg=page, lb=labels: select_tab(
                                        pg, s, lb.get(s, "")
                                    ),
                                )
                            )
                    else:
                        for i, button in enumerate(_tab_buttons(page)):
                            text = (button.inner_text() or f"tab{i}").strip()
                            steps.append((text, button.click))
                    first_context = label == "desktop" and theme == AUDIT_THEMES[0]
                    for tab_name, go in steps:
                        where = f"{label}/{theme}/{tab_name}"
                        if go is not None:
                            try:
                                go()
                            except Exception as exc:  # noqa: BLE001 - a strip that will not switch
                                first = (
                                    str(exc).strip().splitlines()[0]
                                    if str(exc).strip()
                                    else repr(exc)
                                )
                                audit.page_errors.append(
                                    f"{where}: the tab did not select ({first[:160]}); not measured"
                                )
                                continue
                            page.wait_for_timeout(SETTLE_MS)
                        if first_context:
                            audit.tabs.append(tab_name)
                        if tab_name == "landing":
                            _sample_toasts(page, f"{where} loaded", audit)
                            if first_context:
                                _read_boot_card(page, audit, base_url)
                            if label == "phone":
                                _read_stamp(page, where, audit)
                        if tab_name == "try":
                            _fill_snippet(page)
                        _measure_step(page, where, label, theme, tab_name, audit, axe_js)
                        if first_context and tab_name != "landing":
                            _scan_code_chrome(page, where, audit)
                            _dismiss_listboxes(page, where, audit)
                        if label == "desktop" and tab_name != "landing":
                            _measure_voids(page, f"{where} at rest", audit)
                        pressed = ""
                        if label == "desktop" and tab_name in ("try", "eco"):
                            pressed = _sample_run_chrome(page, where, audit)
                        elif first_context and tab_name != "landing":
                            pressed = _press_run(page, where, audit, chrome=False)
                        if pressed and _wait_idle(page):
                            _measure_voids(page, f"{where} after {pressed}", audit)
                    settled = _wait_idle(page)
                    _sample_toasts(
                        page, f"{label}/{theme} {'settled' if settled else 'still running'}", audit
                    )
                    context.close()
        finally:
            browser.close()
    return audit


#: The Hub's edge answers a burst of fresh-context loads of one Space with its own holding page
#: (HTTP 429, sometimes 200 after a redirect; the Hub's title, no `gradio-app` element, no stamp).
#: The audit waits these out instead of timing out on the stamp, and paces its loads.
EDGE_LIMIT_STATUS = 429
EDGE_LIMIT_BACKOFF_S: tuple[float, ...] = (5.0, 10.0, 20.0, 40.0)
EDGE_APP_WAIT_MS = 20_000
LOAD_PACING_MS = 1_000
_JS_APP_MOUNTED = "() => document.querySelector('gradio-app') !== null"


def holding_page(page: Any, response: Any) -> bool:
    """True when the edge served its holding page instead of the Space: a 429, or a document that
    never mounts `gradio-app` within `EDGE_APP_WAIT_MS`."""
    if response is not None and response.status == EDGE_LIMIT_STATUS:
        return True
    try:
        page.wait_for_function(_JS_APP_MOUNTED, timeout=EDGE_APP_WAIT_MS)
    except Exception:  # noqa: BLE001 - the app did not mount: the holding page
        return True
    return False


def goto_past_edge_limits(page: Any, url: str) -> int:
    """`page.goto(url)` until the edge serves the app, backing off between tries; returns how many
    holding pages it waited out. Raises after the last backoff."""
    for attempt, pause in enumerate((*EDGE_LIMIT_BACKOFF_S, None)):
        response = page.goto(url, wait_until="domcontentloaded")
        if not holding_page(page, response):
            return attempt
        if pause is None:
            break
        page.wait_for_timeout(int(pause * 1000))
    tries = len(EDGE_LIMIT_BACKOFF_S) + 1
    raise CheckFailedError(f"the edge served its holding page on {tries} loads of {url}")


#: How long one load may take to show the shell's footer stamp before it counts as a broken
#: shell (the edge let the document through but limited the app's own requests).
SHELL_WAIT_MS = 30_000


def load_until_the_shell_shows(page: Any, url: str) -> int:
    """Load `url` until the app's own shell (the footer stamp) is in the document: the edge's
    holding page and a shell whose config/assets the edge limited both count as one more wait
    on the backoff ladder. Returns how many waits it took."""
    waited = 0
    for attempt, pause in enumerate((*EDGE_LIMIT_BACKOFF_S, None)):
        waited += goto_past_edge_limits(page, url)
        try:
            page.wait_for_selector(".alg-shell-stamp", state="attached", timeout=SHELL_WAIT_MS)
            return waited + attempt
        except Exception:  # noqa: BLE001 - the shell never showed: back off and load again
            if pause is None:
                break
            page.wait_for_timeout(int(pause * 1000))
    tries = len(EDGE_LIMIT_BACKOFF_S) + 1
    raise CheckFailedError(f"the shell's stamp never showed on {tries} loads of {url}")


def run_cls_audit(base_url: str, slugs: Sequence[str] | None = None) -> ClsAudit:
    """`CLS_LOADS` fresh loads of `?tab=<id>` per tab at each audit viewport, each observed for
    `CLS_OBSERVE_MS` after the boot hold lifts; the worst load per page must stay at `CLS_MAX`."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    result = ClsAudit()
    slugs = tuple(tab_slugs()) if slugs is None else tuple(slugs)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for label, width, height in AUDIT_VIEWPORTS:
                # One context per viewport: fresh pages (a fresh document and observer per load)
                # over one HTTP cache, so 36 loads do not re-fetch the app's assets 36 times — the
                # Hub's edge answers that burst with its holding page and a broken app shell.
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    color_scheme=AUDIT_THEMES[-1],
                )
                for slug in slugs:
                    for n in range(1, CLS_LOADS + 1):
                        page = context.new_page()
                        page.set_default_timeout(PAGE_TIMEOUT_MS)
                        page.add_init_script(_JS_CLS_INIT)
                        result.edge_retries += load_until_the_shell_shows(
                            page, f"{base_url}/?{TAB_QUERY}={slug}"
                        )
                        wait_for_reveal(page)
                        page.wait_for_timeout(CLS_OBSERVE_MS)
                        page.wait_for_timeout(LOAD_PACING_MS)  # one load a second, not a burst
                        shifts = page.evaluate(_JS_CLS_READ)
                        total = sum(float(s["v"]) for s in shifts)
                        where = f"{label}/{slug} #{n}"
                        result.loads.append(f"{where} {total:.4f}")
                        result.worst = max(result.worst, total)
                        if total > CLS_MAX:
                            biggest = max(shifts, key=lambda s: s["v"])
                            result.failures.append(
                                f"{where} {total:.4f} at {biggest['t']} ms"
                                f" ({', '.join(biggest['src']) or 'no source'})"
                            )
                        page.close()
                context.close()
        finally:
            browser.close()
    return result


def _parse_link(text: str) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """`(tab, fn, args)` of a `?tab=…&fn=…&args=<json>` link or URL, field by field."""
    from urllib.parse import parse_qs, urlsplit

    params = parse_qs(urlsplit(str(text or "")).query)
    tab = (params.get(TAB_QUERY) or [None])[0] or None
    fn = (params.get("fn") or [None])[0] or None
    args: dict[str, Any] | None = None
    raw = (params.get("args") or [None])[0]
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict) and parsed:
            args = parsed
    return tab, fn, args


def _permalink_helpers() -> dict[str, Any]:
    """What the tabs know that the gate needs: the Try tab's hero function and field labels, the
    Races candidates' titles by function; the frozen fallbacks when a module is not here."""
    helpers: dict[str, Any] = {"try_hero": TRY_HERO_FALLBACK, "try_labels": {}, "race_titles": {}}
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    try:
        try_tab = importlib.import_module(f"{TABS_PACKAGE}.try{TAB_MODULE_SUFFIX}")
        helpers["try_hero"] = str(getattr(try_tab, "HERO_QUALNAME", TRY_HERO_FALLBACK))
        helpers["try_labels"] = dict(getattr(try_tab, "LABELS", {}))
    except Exception as exc:  # noqa: BLE001 - the fallback spelling is used
        log.debug("try tab not importable for the permalink gate: %s", exc)
    try:
        races = importlib.import_module("races")
        helpers["race_titles"] = {c.qualname: c.title for c in races.CANDIDATES}
    except Exception as exc:  # noqa: BLE001 - a race function cannot be verified by title
        log.debug("races not importable for the permalink gate: %s", exc)
    return helpers


def _same_value(shown: str, wanted: Any) -> bool:
    if isinstance(wanted, bool):
        return shown.strip().lower() == str(wanted).lower()
    if isinstance(wanted, int | float):
        try:
            return float(shown) == float(wanted)
        except ValueError:
            return False
    return shown.strip() == str(wanted).strip()


def _shown_controls(state: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for kind in ("nums", "texts", "combos"):
        out += [(kind, str(label), str(value)) for label, value in state.get(kind, [])]
    for label, text in state.get("jsons", []):
        out.append(("jsons", str(label), str(text)))
    return out


def _fn_shown(
    tab: str | None, fn: str, state: Mapping[str, Any], helpers: Mapping[str, Any]
) -> bool:
    """Whether the displayed form shows `fn` as its function."""
    combos = {str(label): str(value) for label, value in state.get("combos", [])}
    if tab == "play":
        module, _, function = fn.rpartition(".")
        values = list(combos.values())
        return module in values and function in values
    if tab == "race":
        title = helpers.get("race_titles", {}).get(fn)
        return title is not None and title in combos.values()
    if tab == "try":
        return fn == helpers.get("try_hero")
    return False


def _arg_shown(
    tab: str | None, name: str, value: Any, state: Mapping[str, Any], helpers: Mapping[str, Any]
) -> tuple[bool, str]:
    """`(shown, actual)`: whether a control carries `value` for `name`, and what it shows."""
    if tab == "race" and name == RACE_SIZE_PARAM:
        radios = [str(r) for r in state.get("radios", [])]
        hit = any(r == str(value) or r.startswith(f"{value} ·") for r in radios)
        return hit, ", ".join(radios) or "no size"
    label = name
    if tab == "try":
        label = str(helpers.get("try_labels", {}).get(name, name))
    controls = _shown_controls(state)
    labelled = [(kind, shown) for kind, lbl, shown in controls if lbl == label]
    if labelled:
        for kind, shown in labelled:
            if kind == "jsons":
                try:
                    if json.loads(shown) == value:
                        return True, shown
                except ValueError:
                    pass
            elif _same_value(shown, value):
                return True, shown
        return False, labelled[0][1]
    # no control by that label: a value match on any control is the fallback (a label map
    # that could not be imported), nothing shown is the answer otherwise
    for kind, _lbl, shown in controls:
        if kind != "jsons" and _same_value(shown, value):
            return True, shown
    return False, "no control"


def permalink_problems(
    query: str,
    restored_in_full: bool,
    state: Mapping[str, Any],
    helpers: Mapping[str, Any] | None = None,
) -> list[str]:
    """Every promise the box makes that the form does not keep, in words — and, for a shape
    the tab must restore in full, every field of the link the form or the box lost."""
    helpers = _permalink_helpers() if helpers is None else helpers
    box = str(state.get("box") or "")
    selected = str(state.get("selected") or "")
    problems: list[str] = []
    if not box:
        return ["the link box is empty"]
    tab, fn, args = _parse_link(box)
    if tab is None:
        problems.append(f"box {box!r} names no tab")
    elif tab != selected:
        problems.append(f"box names tab {tab!r}, the strip shows {selected!r}")
    if fn and not _fn_shown(tab, fn, state, helpers):
        combos = ", ".join(str(v) for _, v in state.get("combos", [])) or "no function control"
        problems.append(f"box promises fn {fn}, the form shows {combos}")
    for name, value in (args or {}).items():
        shown, actual = _arg_shown(tab, name, value, state, helpers)
        if not shown:
            problems.append(f"box promises {name}={value!r}, the form shows {actual!r}")
    if restored_in_full:
        want_tab, want_fn, want_args = _parse_link(query)
        if want_fn and not _fn_shown(want_tab, want_fn, state, helpers):
            problems.append(f"the tab did not restore fn {want_fn}")
        elif want_fn and fn != want_fn:
            problems.append(f"box lost fn {want_fn} the tab restored (box {box!r})")
        for name, value in (want_args or {}).items():
            shown, actual = _arg_shown(want_tab, name, value, state, helpers)
            if not shown:
                problems.append(f"the tab did not restore {name}={value!r} (form shows {actual!r})")
            elif (args or {}).get(name) != value:
                problems.append(f"box lost {name}={value!r} the tab restored (box {box!r})")
    return problems


def _open_link(context: Any, base_url: str, query: str) -> Any:
    """A page on `base_url/<query>` with the boot hold lifted and the restore settled."""
    from urllib.parse import quote

    parts = []
    for part in query.lstrip("?").split("&"):
        key, _, value = part.partition("=")
        parts.append(f"{key}={quote(value, safe='')}")
    page = context.new_page()
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    page.goto(f"{base_url}/?{'&'.join(parts)}", wait_until="domcontentloaded")
    page.wait_for_selector(".alg-shell-stamp", state="attached")
    wait_for_reveal(page)
    try:
        page.wait_for_function(FONTS_READY_JS, timeout=FONTS_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001 - glyph metrics do not matter here
        log.debug("fonts not ready: %s", exc)
    page.wait_for_timeout(RESTORE_SETTLE_MS)
    return page


def run_permalink_audit(base_url: str) -> PermalinkAudit:
    """Load every `PERMALINK_SHAPES` link in every `PERMALINK_CONTEXTS` context, read the box
    and the form the tab restored, and record every promise the form does not keep."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    result = PermalinkAudit()
    helpers = _permalink_helpers()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for label, width, height, theme in PERMALINK_CONTEXTS:
                context = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=theme
                )
                for name, query, full in PERMALINK_SHAPES:
                    where = f"{label}/{theme} {name}"
                    page = _open_link(context, base_url, query)
                    state = page.evaluate(_JS_FORM_STATE)
                    page.close()
                    result.loads.append(f"{where} box {state.get('box')!r}")
                    for problem in permalink_problems(query, full, state, helpers):
                        result.failures.append(f"{where}: {problem}")
                context.close()
        finally:
            browser.close()
    return result


_JS_ECO_TABLE = """
() => {
  const table = document.querySelector('table.alg-eco-table');
  if (table === null) return null;
  const wrap = table.closest('.alg-eco-tablewrap') || table.parentElement;
  const w = wrap.getBoundingClientRect(), t = table.getBoundingClientRect();
  const head = table.querySelector('th[data-col="backends"]');
  const backends = head !== null && getComputedStyle(head).display !== 'none';
  return {wrapLeft: w.left, wrapRight: w.right, tableLeft: t.left, tableRight: t.right,
          scrollWidth: wrap.scrollWidth, clientWidth: wrap.clientWidth,
          docScroll: document.documentElement.scrollWidth, inner: window.innerWidth,
          backends: backends, rows: table.querySelectorAll('tbody tr').length};
}
"""


def eco_table_problems(width: int, m: Mapping[str, Any]) -> list[str]:
    """Why the table does not fit at `width`: it outgrows its block, scrolls inside it, or the
    page scrolls sideways; at the desktop width the backends column must be there."""
    problems: list[str] = []
    if float(m["tableRight"]) > float(m["wrapRight"]) + 0.5:
        problems.append(
            f"table right {float(m['tableRight']):.0f} > block right {float(m['wrapRight']):.0f}"
        )
    if int(m["scrollWidth"]) > int(m["clientWidth"]) + 1:
        problems.append(f"block scrolls {int(m['scrollWidth'])} in {int(m['clientWidth'])} px")
    if int(m["docScroll"]) > int(m["inner"]):
        problems.append(f"page scrolls sideways ({int(m['docScroll'])} > {int(m['inner'])})")
    if width >= 1440 and not m.get("backends"):
        problems.append("backends column missing at the desktop width")
    return problems


def run_eco_table_audit(base_url: str) -> EcoTableAudit:
    """Load the Ecosystem tab at every `ECO_TABLE_WIDTHS` width and measure the Hub table
    against its block."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    result = EcoTableAudit()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for width in ECO_TABLE_WIDTHS:
                context = browser.new_context(
                    viewport={"width": width, "height": 900}, color_scheme=AUDIT_THEMES[0]
                )
                page = _open_link(context, base_url, f"?{TAB_QUERY}=eco")
                page.wait_for_selector("table.alg-eco-table", state="attached")
                page.wait_for_timeout(SETTLE_MS)
                measured = page.evaluate(_JS_ECO_TABLE)
                context.close()
                if measured is None:
                    result.failures.append(f"{width} px: no Hub table on the page")
                    continue
                shown = "shown" if measured.get("backends") else "dropped"
                result.samples.append(
                    f"{width} px: table {float(measured['tableLeft']):.0f}–"
                    f"{float(measured['tableRight']):.0f} in block"
                    f" {float(measured['wrapLeft']):.0f}–{float(measured['wrapRight']):.0f},"
                    f" backends {shown}"
                )
                for problem in eco_table_problems(width, measured):
                    result.failures.append(f"{width} px: {problem}")
        finally:
            browser.close()
    return result


def run_exact_int_audit(base_url: str) -> ExactIntAudit:
    """Type 2^53 + 1 into the Playground's `n_a` box, press Run and read what the Request JSON
    carries — or the message the form answered with."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    result = ExactIntAudit(typed=str(EXACT_INT))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(viewport=WIDE_VIEWPORT, color_scheme=AUDIT_THEMES[0])
            page = _open_link(context, base_url, f"?{TAB_QUERY}=play")
            field = page.locator(
                f"[role=tabpanel] .alg-field:has(label:has-text('{EXACT_INT_FIELD}'))"
                " input[type=number]"
            ).filter(visible=True)
            if not field.count():
                field = (
                    page.locator("[role=tabpanel] input[type=number]").filter(visible=True).nth(1)
                )
            field.first.fill(str(EXACT_INT))
            field.first.dispatch_event("input")
            page.wait_for_timeout(200)
            button = _run_button(page)
            if button is None:
                raise RuntimeError("the Playground has no run button")
            button.click()
            page.wait_for_selector(
                ".alg-play-card .alg-card-result, .alg-play-card .alg-card-err,"
                f" {FIELD_MESSAGE_SELECTOR}:visible",
                state="visible",
                timeout=RESULT_TIMEOUT_MS,
            )
            page.wait_for_timeout(SETTLE_MS)
            messages = page.locator(FIELD_MESSAGE_SELECTOR).filter(visible=True)
            if messages.count():
                result.message = " ".join(
                    (messages.nth(i).inner_text() or "").strip() for i in range(messages.count())
                ).strip()
            request_header = page.get_by_role("button", name="Request and response").filter(
                visible=True
            )
            if request_header.count():
                request_header.first.click()
                page.wait_for_timeout(400)
            editors = page.locator("[role=tabpanel] .alg-disclosure .cm-content").filter(
                visible=True
            )
            request_text = editors.first.inner_text() if editors.count() else ""
            result.request = _int_in_request(request_text)
            context.close()
        finally:
            browser.close()
    return result


def _overlaps(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Two boxes share some horizontal extent."""
    return a["left"] < b["right"] and a["right"] > b["left"]


def refusal_not_exercisable(state: Mapping[str, Any] | None) -> str | None:
    """The unavailable code the panel shows instead of a refusal — a tab whose kernel is not in
    this container answers a run with its coded card before any input rule is checked (the
    torch-less keyed venv) — or None when the page answered with messages or nothing."""
    if state is None:
        return None
    if state.get("messages") or any(s.get("text") for s in state.get("status", ())):
        return None
    codes = [str(c) for c in state.get("codes", ()) if str(c).strip()]
    return codes[0] if codes else None


def refusal_problems(
    where: str, control: str, value: str, word: str, state: Mapping[str, Any] | None
) -> list[str]:
    """Everything the refusal convention asks for that the page did not do: a field message
    under the offending control, an echo in the status row beside the action, the expected
    words in it, no red card (a refusal is not a failure during a run), no toast."""
    lead = f"{where} '{control}'={value}"
    if state is None:
        return [f"{lead}: the tab panel was not found"]
    if state.get("control") is None:
        return [f"{lead}: no visible control named {control!r}"]
    box = state["control"]
    messages = list(state.get("messages", ()))
    under = [
        m
        for m in messages
        if not m["inStatus"]
        and box["bottom"] - 2 <= m["top"] <= box["bottom"] + FIELD_MESSAGE_REACH_PX
        and _overlaps(m, box)
    ]
    run = state.get("run")
    echoes = [
        s
        for s in state.get("status", ())
        if s["text"]
        and (
            run is None
            or run["top"] - STATUS_ECHO_REACH_PX <= s["top"] <= run["bottom"] + STATUS_ECHO_REACH_PX
        )
    ]
    problems: list[str] = []
    texts = list(dict.fromkeys([m["text"] for m in messages] + [s["text"] for s in echoes]))
    if not messages and not echoes:
        problems.append(f"{lead}: no message anywhere — the run was not refused, or silently")
    else:
        if not under:
            elsewhere = "; ".join(f"'{t}'" for t in texts[:2])
            problems.append(f"{lead}: no field message under the control ({elsewhere} elsewhere)")
        if not echoes:
            problems.append(f"{lead}: no echo in the status row beside the action")
        if word and not any(word in t.lower() for t in texts):
            problems.append(f"{lead}: no message carries {word!r} ({'; '.join(texts[:2])})")
    if state.get("redCards"):
        problems.append(f"{lead}: {state['redCards']} red card(s) for a refusal")
    if state.get("toasts"):
        problems.append(f"{lead}: {state['toasts']} toast(s)")
    return problems


def run_refusal_audit(base_url: str) -> RefusalAudit:
    """Type one refused value per tab (`REFUSAL_PROBES`) in each `REFUSAL_CONTEXTS` context,
    press Run, and read where the page said no."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        skip("playwright not installed")
    result = RefusalAudit()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for label, width, height, theme in REFUSAL_CONTEXTS:
                context = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=theme
                )
                for slug, control, value, word in REFUSAL_PROBES:
                    where = f"{label}/{theme}/{slug}"
                    page = _open_link(context, base_url, f"?{TAB_QUERY}={slug}")
                    try:
                        field = page.locator(
                            f"[role=tabpanel] input[aria-label='{control}']"
                        ).filter(visible=True)
                        button = _run_button(page)
                        if not field.count() or button is None:
                            code = unavailable_code(page.content()) or "no controls"
                            result.skipped.append(f"{where}: no form to refuse ({code})")
                            continue
                        field.first.fill(value)
                        field.first.dispatch_event("input")
                        field.first.dispatch_event("change")
                        page.wait_for_timeout(200)
                        button.click()
                        page.wait_for_timeout(REFUSAL_SETTLE_MS)
                        _wait_idle(page)
                        state = page.evaluate(_JS_REFUSAL, control)
                    finally:
                        page.close()
                    code = refusal_not_exercisable(state)
                    if code is not None:
                        result.skipped.append(
                            f"{where}: no refusal to read, the run answered {code}"
                        )
                        continue
                    problems = refusal_problems(where, control, value, word, state)
                    texts = [m["text"] for m in (state or {}).get("messages", ())]
                    result.probes.append(
                        f"{where} '{control}'={value}: {len(texts)} message(s)"
                        f"{' — ' + texts[0] if texts else ''}"
                    )
                    result.failures.extend(problems)
                context.close()
        finally:
            browser.close()
    return result


def _int_in_request(text: str) -> str:
    """The `n_a` value the Request JSON carries, as text (exact digits), or ''."""
    try:
        document = json.loads(text)
    except ValueError:
        m = re.search(rf'"{EXACT_INT_FIELD}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        return m.group(1) if m else ""
    args = document.get("args") if isinstance(document, dict) else None
    if isinstance(args, dict) and EXACT_INT_FIELD in args:
        return str(args[EXACT_INT_FIELD])
    if isinstance(args, list) and len(args) >= 2:
        return str(args[1])
    return ""


_audit_errors: dict[str, str] = {}
_cls_audit_errors: dict[str, str] = {}


def _first_line_of(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else repr(exc)


def audit_for(ctx: Any) -> Audit:
    """The one browser audit per base URL. An audit that raises (a browser that will not launch,
    a page that never reveals) is one failed check per gate with the same reason, never a crash
    of the run — and it is not retried for every gate."""
    base = ctx.base_url.rstrip("/")
    if base in _audit_errors:
        fail(_audit_errors[base])
    if base not in _audits:
        try:
            _audits[base] = run_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _audit_errors[base] = (
                f"the browser audit did not complete: {type(exc).__name__}: {_first_line_of(exc)}"
            )
            fail(_audit_errors[base])
    return _audits[base]


def cls_audit_for(ctx: Any) -> ClsAudit:
    base = ctx.base_url.rstrip("/")
    if base in _cls_audit_errors:
        fail(_cls_audit_errors[base])
    if base not in _cls_audits:
        try:
            _cls_audits[base] = run_cls_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _cls_audit_errors[base] = (
                f"the layout-shift audit did not complete: {type(exc).__name__}:"
                f" {_first_line_of(exc)}"
            )
            fail(_cls_audit_errors[base])
    return _cls_audits[base]


_permalink_audit_errors: dict[str, str] = {}
_exact_int_errors: dict[str, str] = {}


_eco_table_audits: dict[str, EcoTableAudit] = {}
_eco_table_errors: dict[str, str] = {}


def eco_table_audit_for(ctx: Any) -> EcoTableAudit:
    base = ctx.base_url.rstrip("/")
    if base in _eco_table_errors:
        fail(_eco_table_errors[base])
    if base not in _eco_table_audits:
        try:
            _eco_table_audits[base] = run_eco_table_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _eco_table_errors[base] = (
                f"the table audit did not complete: {type(exc).__name__}: {_first_line_of(exc)}"
            )
            fail(_eco_table_errors[base])
    return _eco_table_audits[base]


def permalink_audit_for(ctx: Any) -> PermalinkAudit:
    base = ctx.base_url.rstrip("/")
    if base in _permalink_audit_errors:
        fail(_permalink_audit_errors[base])
    if base not in _permalink_audits:
        try:
            _permalink_audits[base] = run_permalink_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _permalink_audit_errors[base] = (
                f"the permalink audit did not complete: {type(exc).__name__}: {_first_line_of(exc)}"
            )
            fail(_permalink_audit_errors[base])
    return _permalink_audits[base]


def exact_int_audit_for(ctx: Any) -> ExactIntAudit:
    base = ctx.base_url.rstrip("/")
    if base in _exact_int_errors:
        fail(_exact_int_errors[base])
    if base not in _exact_int_audits:
        try:
            _exact_int_audits[base] = run_exact_int_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _exact_int_errors[base] = (
                f"the exact-integer probe did not complete: {type(exc).__name__}:"
                f" {_first_line_of(exc)}"
            )
            fail(_exact_int_errors[base])
    return _exact_int_audits[base]


def refusal_audit_for(ctx: Any) -> RefusalAudit:
    base = ctx.base_url.rstrip("/")
    if base in _refusal_audit_errors:
        fail(_refusal_audit_errors[base])
    if base not in _refusal_audits:
        try:
            _refusal_audits[base] = run_refusal_audit(base)
        except _SIGNALS["skip"]:
            raise
        except Exception as exc:  # noqa: BLE001 - reported as the gate's failure
            _refusal_audit_errors[base] = (
                f"the refusal probe did not complete: {type(exc).__name__}: {_first_line_of(exc)}"
            )
            fail(_refusal_audit_errors[base])
    return _refusal_audits[base]


def small_target_summary(items: Sequence[str]) -> str:
    """`a.alg-shell-nav-link ×84 (e.g. desktop/light/landing 'Docs' 31x44); …` — the residual
    list grouped by the selector signature, largest group first."""
    groups: dict[str, list[str]] = {}
    for item in items:
        where, _, rest = item.partition(" ")
        selector, _, detail = rest.partition(" ")
        groups.setdefault(selector, []).append(f"{where} {detail}".strip())
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return "; ".join(f"{sel} ×{len(ex)} (e.g. {ex[0]})" for sel, ex in ordered)


def console_clean(ctx: Any) -> str:
    audit = audit_for(ctx)
    problems = audit.page_errors + audit.console_errors
    if problems:
        fail(f"{len(problems)} console error(s): {problems[0]}")
    return f"0 console errors over {len(audit.tabs)} tab views"


def no_horizontal_scroll(ctx: Any) -> str:
    audit = audit_for(ctx)
    phone = [o for o in audit.overflow if o.startswith("phone/")]
    if phone:
        fail(f"horizontal scroll at 375 px: {', '.join(phone[:3])}")
    return "no horizontal scroll at 375 px"


def targets_44px(ctx: Any) -> str:
    """Every pointer target, the options of every opened dropdown included, at 44 px."""
    audit = audit_for(ctx)
    opened = f" ({audit.listboxes_opened} listboxes opened)"
    if audit.small_targets or audit.listbox_errors:
        parts = []
        if audit.small_targets:
            parts.append(
                f"{len(audit.small_targets)} of {audit.targets_checked} target(s) under"
                f" {TARGET_PX} px{opened}: {small_target_summary(audit.small_targets)}"
            )
        if audit.listbox_errors:
            parts.append(
                f"{len(audit.listbox_errors)} dropdown(s) not measured:"
                f" {'; '.join(audit.listbox_errors[:2])}"
            )
        fail(" — ".join(parts))
    return f"{audit.targets_checked} targets, all >= {TARGET_PX} px{opened}"


def _governed_controls_audited(audit: Audit) -> bool:
    """Whether the browser audit saw the Governed tab with its controls (a run button that was
    pressed, not the not-configured card without one)."""
    return any(
        p.split(" ", 1)[0].endswith("/gov") and not p.endswith("(disabled)")
        for p in audit.run_presses
    )


def axe_serious_critical(ctx: Any) -> str:
    """axe-core on every tab view in every context of this phase: no serious or critical
    violation. In the keyed phase the Governed controls (the open Engine responses block among
    them) must have been on the page the audit read, or the phase measured nothing new."""
    audit = audit_for(ctx)
    if not audit.axe_ran:
        skip(audit.axe_reason or "axe did not run")
    if audit.axe_violations:
        fail(f"axe: {'; '.join(audit.axe_violations[:3])}")
    if keyed() and not _governed_controls_audited(audit):
        fail(
            f"axe: 0 serious or critical over {audit.axe_views} views, but the keyed phase never"
            " saw the Governed controls (no run button on the Governed tab)"
        )
    tail = ", Governed controls included" if _governed_controls_audited(audit) else ""
    return f"axe: 0 serious or critical over {audit.axe_views} tab views ({phase()} phase{tail})"


def no_stock_code_labels(ctx: Any) -> str:
    """No Code block keeps Gradio's stock block label (the `</>` icon and its caption) or
    CodeMirror's line-number gutter; every disclosure is opened so hidden blocks count too."""
    audit = audit_for(ctx)
    if audit.code_blocks == 0:
        fail("no Code block was measured")
    if audit.stock_code_chrome:
        fail(
            f"{len(audit.stock_code_chrome)} stock element(s) on {audit.code_blocks} Code"
            f" blocks: {'; '.join(audit.stock_code_chrome[:4])}"
        )
    return f"{audit.code_blocks} Code blocks, no stock label or line-number gutter"


def voids(ctx: Any) -> str:
    """At 1440 px, at rest and after each tab's primary action, no column of a multi-column
    row holds a gap over `VOID_MAX_PX` between consecutive elements or below its last one."""
    audit = audit_for(ctx)
    if audit.void_samples == 0:
        fail("no multi-column row was measured at 1440 px")
    if audit.voids:
        fail(
            f"{len(audit.voids)} void(s) over {VOID_MAX_PX} px in {audit.void_samples} column"
            f" samples: {'; '.join(audit.voids[:4])}"
        )
    return f"{audit.void_samples} column samples at 1440 px, no gap over {VOID_MAX_PX} px"


def boot_row_live(ctx: Any) -> str:
    """The boot card's hero row says what `/health` said at the same moment: a measured hero
    prints its per kernel call time and the n chip's words (`n = 21`, or `n = 21 × k calls` when
    `/health` says each sample was k back-to-back calls — rulebook v0.4, the Try card's own
    chip), an unmeasured one prints `not recorded` — a row that froze at the stage's end while
    the tracker recorded later is what this catches."""
    audit = audit_for(ctx)
    row = next((r for r in audit.boot_rows if r.get("stage") == "hero"), None)
    if row is None:
        fail("the boot card has no hero row")
    hero = audit.boot_hero
    detail = str(row.get("detail", ""))
    if not isinstance(hero, Mapping):
        # no hero at all: the stage failed (the family did not load here) and the row says so
        if NO_HERO_WORDS in detail and "per kernel call" not in detail:
            return f"hero row {detail!r} == {HEALTH_PATH} hero null (the hero family did not load)"
        fail(
            f"{HEALTH_PATH} carried no hero when the boot card was read, yet the row reads"
            f" {detail!r}"
        )
    status = str(hero.get("status") or "")
    kernel_ms = hero.get("kernel_ms")
    n = hero.get("n")
    k = hero.get("k")
    attempts = hero.get("attempts")
    tries = f", attempt {attempts}" if attempts else ""
    n_text = (
        cards.calls_text(int(n), int(k))
        if isinstance(n, int) and isinstance(k, int) and n >= 1 and k >= 1
        else f"n = {n}"
    )
    if status == bench.STATUS_MEASURED and isinstance(kernel_ms, int | float):
        truth = f"measured {cards.fmt_ms(float(kernel_ms))} per kernel call, {n_text}{tries}"
        wanted = (cards.fmt_ms(float(kernel_ms)), n_text)
        if cards.NOT_RECORDED_TEXT in detail or any(w not in detail for w in wanted):
            fail(
                f"the boot card's hero row reads {detail!r} while {HEALTH_PATH} says {truth}:"
                " the row froze at the stage's end"
            )
    else:
        truth = f"{status or 'unknown'}{tries}"
        if "per kernel call" in detail or cards.NOT_RECORDED_TEXT not in detail:
            fail(
                f"the boot card's hero row reads {detail!r} while {HEALTH_PATH} says the hero is"
                f" {truth}"
            )
    return f"hero row {detail!r} == {HEALTH_PATH} hero {truth}"


def refusal_convention(ctx: Any) -> str:
    """Every refusal is a field message under the offending control and an echo in the status
    row beside the action — on Try, the Playground and, with a key, Governed — never a red
    card, never a toast."""
    result = refusal_audit_for(ctx)
    if not result.probes and not result.skipped:
        fail("no refusal was provoked")
    problems = list(result.failures)
    if keyed():
        problems += [f"{s} in the keyed phase" for s in result.skipped if "/gov" in s]
    if problems:
        fail(f"{len(problems)} of {len(result.probes)} probes: {'; '.join(problems[:4])}")
    tabs = sorted({p.split(" ", 1)[0].rsplit("/", 1)[-1] for p in result.probes})
    skipped = f"; not shown: {'; '.join(result.skipped[:2])}" if result.skipped else ""
    return (
        f"{len(result.probes)} refusals on {', '.join(tabs)}: field message under the control"
        f" + status-row echo, no red card, no toast{skipped}"
    )


def contrast_hero(ctx: Any) -> str:
    """The hero figure, every chip, tile and caption, and the open listbox's options, each at
    or above 4.5:1 against its effective fill in both themes; the worst ratio leads."""
    audit = audit_for(ctx)
    if audit.contrast_failures:
        worst = sorted(audit.contrast_failures, key=_ratio_of)
        fail(
            f"{len(worst)} of {audit.contrast_samples} samples under {CONTRAST_MIN}:1:"
            f" {'; '.join(worst[:4])}"
        )
    return f"{audit.contrast_samples} samples >= {CONTRAST_MIN}:1"


def no_identifiers_in_copy(ctx: Any) -> str:
    """No snake_case token, environment name, build-variant string or raw URL in the primary
    copy of any tab; the Playground's contract labels are the one allowance."""
    audit = audit_for(ctx)
    if audit.copy_nodes == 0:
        fail("no primary copy was scanned")
    if audit.identifier_hits:
        fail(
            f"{len(audit.identifier_hits)} identifier(s) in primary copy over {audit.copy_nodes}"
            f" text nodes: {small_target_summary(audit.identifier_hits)}"
        )
    return f"{audit.copy_nodes} text nodes, no identifiers in primary copy"


def contrast_buttons(ctx: Any) -> str:
    """Text on every button at rest, on hover, on focus and when disabled, plus the selected
    tab's label, at or above 4.5:1 in both themes."""
    audit = audit_for(ctx)
    if audit.button_contrast_failures or audit.button_sample_errors:
        worst = sorted(audit.button_contrast_failures, key=_ratio_of)
        parts = []
        if worst:
            parts.append(
                f"{len(worst)} of {audit.button_contrast_samples} button samples under"
                f" {CONTRAST_MIN}:1: {'; '.join(worst[:6])}"
            )
        if audit.button_sample_errors:
            parts.append(
                f"{len(audit.button_sample_errors)} state(s) not readable:"
                f" {'; '.join(audit.button_sample_errors[:2])}"
            )
        fail(" — ".join(parts))
    return f"{audit.button_contrast_samples} button samples >= {CONTRAST_MIN}:1"


def contrast_code(ctx: Any) -> str:
    """Every CodeMirror token class in every visible Code block, light and dark."""
    audit = audit_for(ctx)
    if audit.code_contrast_samples == 0:
        fail("no code tokens were painted on any tab")
    if audit.code_contrast_failures:
        worst = sorted(audit.code_contrast_failures, key=_ratio_of)
        fail(
            f"{len(worst)} of {audit.code_contrast_samples} token samples under"
            f" {CONTRAST_MIN}:1: {'; '.join(worst[:4])}"
        )
    return f"{audit.code_contrast_samples} token samples >= {CONTRAST_MIN}:1"


def cls_budget(ctx: Any) -> str:
    """Cumulative layout shift of every fresh load at or under `CLS_MAX`."""
    result = cls_audit_for(ctx)
    if not result.loads:
        fail("no page load was measured")
    if result.failures:
        fail(
            f"{len(result.failures)} of {len(result.loads)} loads over {CLS_MAX}"
            f" (worst {result.worst:.4f}): {'; '.join(result.failures[:3])}"
        )
    waited = f", {result.edge_retries} edge 429 answer(s) waited out" if result.edge_retries else ""
    return f"{len(result.loads)} loads, worst {result.worst:.4f} <= {CLS_MAX}{waited}"


def value_boxes_unclipped(ctx: Any) -> str:
    """Every number box sits inside its parent and its block, and its value fits."""
    audit = audit_for(ctx)
    if audit.clipped_values:
        fail(
            f"{len(audit.clipped_values)} of {audit.value_boxes_checked} value boxes clipped:"
            f" {'; '.join(audit.clipped_values[:3])}"
        )
    return f"{audit.value_boxes_checked} value boxes inside their boxes, values visible"


def no_stock_chrome(ctx: Any) -> str:
    """No Gradio status text, ETA bar, generating border or stock orange while a run runs."""
    audit = audit_for(ctx)
    if not audit.chrome_runs:
        fail("no run button was pressed on the Try or Ecosystem tab")
    if audit.stock_chrome:
        fail(
            f"stock chrome in {len(audit.stock_chrome)} of {audit.chrome_samples} samples:"
            f" {'; '.join(audit.stock_chrome[:3])}"
        )
    return (
        f"{audit.chrome_samples} samples over {len(audit.chrome_runs)} runs,"
        " no stock chrome or stock colour"
    )


def nav_separators(ctx: Any) -> str:
    """At 375 px no wrapped nav or footer row starts or ends with the separator glyph."""
    audit = audit_for(ctx)
    if audit.nav_rows_checked == 0:
        fail("no nav rows were measured at 375 px")
    if audit.nav_separator_failures:
        fail(
            f"{len(audit.nav_separator_failures)} separator(s) at a row edge:"
            f" {'; '.join(audit.nav_separator_failures[:3])}"
        )
    return f"{audit.nav_rows_checked} nav rows, separators only between links"


def checkboxes_dark_unfilled(ctx: Any) -> str:
    """An unchecked checkbox in dark mode has no saturated fill."""
    audit = audit_for(ctx)
    if audit.filled_checkboxes:
        fail(
            f"{len(audit.filled_checkboxes)} of {audit.checkboxes_checked} unchecked boxes"
            f" filled in dark mode: {'; '.join(audit.filled_checkboxes[:3])}"
        )
    return f"{audit.checkboxes_checked} unchecked boxes empty in dark mode"


def no_toasts(ctx: Any) -> str:
    """Never a visible toast: after the landing page loads, at every sample after every run
    press (the Governed run included), and once every run has settled."""
    audit = audit_for(ctx)
    if audit.toast_samples == 0:
        fail("no toast sample was taken")
    pressed = [p for p in audit.run_presses if not p.endswith("(disabled)")]
    disabled = [p for p in audit.run_presses if p.endswith("(disabled)")]
    if audit.toasts:
        fail(
            f"{len(audit.toasts)} toast(s) in {audit.toast_samples} samples over {len(pressed)}"
            f" run presses: {'; '.join(audit.toasts[:3])}"
        )
    tabs = sorted({p.split(" ", 1)[0].rsplit("/", 1)[-1] for p in pressed})
    tail = f"; not pressed, disabled: {', '.join(disabled)}" if disabled else ""
    return (
        f"0 toasts in {audit.toast_samples} samples over {len(pressed)} run presses"
        f" ({', '.join(tabs) or 'no tab'}){tail}"
    )


def dropdown_dismissal(ctx: Any) -> str:
    """Dismissing an open listbox — a click away, Tab, Escape — never changes the form."""
    audit = audit_for(ctx)
    if audit.dismissals == 0 and not audit.dismissal_errors:
        fail("no dropdown was opened and dismissed")
    if audit.dismissal_failures or audit.dismissal_errors:
        parts = []
        if audit.dismissal_failures:
            parts.append(
                f"{len(audit.dismissal_failures)} of {audit.dismissals} dismissals changed the"
                f" form: {'; '.join(audit.dismissal_failures[:3])}"
            )
        if audit.dismissal_errors:
            parts.append(
                f"{len(audit.dismissal_errors)} dismissal(s) not measured:"
                f" {'; '.join(audit.dismissal_errors[:2])}"
            )
        fail(" — ".join(parts))
    boxes = audit.dismissals // len(DISMISSALS)
    return (
        f"{audit.dismissals} dismissals ({', '.join(DISMISSALS)}) over {boxes} dropdowns,"
        " form unchanged"
    )


def dropdown_reopens(ctx: Any) -> str:
    """A focused combobox whose list was closed — by Escape, or by the shell on Tab-arrival —
    opens again on a click, the form unchanged (round 5: the click was eaten until focus left);
    and Tab-arrival itself paints no listbox at any sampled moment (round 6)."""
    audit = audit_for(ctx)
    if audit.reopens == 0 and not audit.reopen_failures and not audit.reopen_errors:
        fail("no focused dropdown was clicked")
    if audit.reopen_failures or audit.reopen_errors:
        parts = []
        if audit.reopen_failures:
            parts.append(
                f"{len(audit.reopen_failures)} of"
                f" {audit.reopens + len(audit.reopen_failures)} clicks opened nothing or changed"
                f" the form: {'; '.join(audit.reopen_failures[:3])}"
            )
        if audit.reopen_errors:
            errors = "; ".join(audit.reopen_errors[:2])
            parts.append(f"{len(audit.reopen_errors)} probe(s) not measured: {errors}")
        fail(" — ".join(parts))
    return f"{audit.reopens} clicks on a focused, closed dropdown reopened its list, form unchanged"


def eco_table_fits(ctx: Any) -> str:
    """The Ecosystem's Hub table never outgrows its block or clips a column at any
    `ECO_TABLE_WIDTHS` width (round 5: `backends` read `cpu, cuda, me` at 1024)."""
    result = eco_table_audit_for(ctx)
    if not result.samples and not result.failures:
        fail("the Hub table was not measured")
    if result.failures:
        fail(f"{len(result.failures)} width(s) do not fit: {'; '.join(result.failures[:4])}")
    widths = ", ".join(str(w) for w in ECO_TABLE_WIDTHS)
    return f"the Hub table fits its block at {widths} px ({len(result.samples)} loads)"


def _seconds_of(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*s\b", text)
    return float(m.group(1)) if m else None


def _stage_durations(snapshot: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for stage in snapshot.get("stages") or []:
        if not isinstance(stage, Mapping):
            continue
        started, finished = stage.get("started_at"), stage.get("finished_at")
        if isinstance(started, int | float) and isinstance(finished, int | float):
            out[str(stage.get("id"))] = max(0.0, float(finished) - float(started))
    return out


def boot_card_timings(ctx: Any) -> str:
    """Every stage row prints the time `/health` records for that stage — a stage that ran is
    never `0.0 s` — and the rows sum to the `booted in` foot, which is the snapshot's boot."""
    audit = audit_for(ctx)
    if not audit.boot_rows:
        fail("the boot card had no stage rows")
    status_code, body = ctx.get(HEALTH_PATH)
    if status_code != 200:
        fail(f"{HEALTH_PATH} answered {status_code}")
    try:
        snapshot = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{HEALTH_PATH} is not JSON: {exc}")
    truth = _stage_durations(snapshot)
    boot_s = boot_duration(snapshot)
    problems: list[str] = []
    printed: list[float] = []
    for row in audit.boot_rows:
        stage, text = row.get("stage", ""), row.get("elapsed", "")
        card = _seconds_of(text)
        if card is None:
            problems.append(f"{stage} prints no time ({text!r})")
            continue
        printed.append(card)
        ran = truth.get(stage)
        if ran is None:
            continue
        if card == 0.0 and ran >= 0.05:
            problems.append(f"{stage} prints 0.0 s but ran {ran:.2f} s")
        elif abs(card - ran) > BOOT_TOLERANCE_S:
            problems.append(f"{stage} prints {card:.1f} s, {HEALTH_PATH} says {ran:.2f} s")
    total = sum(printed)
    foot_s = _seconds_of(audit.boot_foot) if audit.boot_foot else None
    if foot_s is None:
        problems.append(f"the foot prints no boot time ({audit.boot_foot!r})")
    else:
        if abs(total - foot_s) > BOOT_TOLERANCE_S * max(1, len(printed)) + 0.1:
            problems.append(f"the rows sum to {total:.1f} s, the foot says {foot_s:.1f} s")
        if boot_s is not None and abs(foot_s - boot_s) > BOOT_TOLERANCE_S + 0.05:
            problems.append(f"the foot says {foot_s:.1f} s, {HEALTH_PATH} booted in {boot_s:.2f} s")
    summary = (
        f"{len(printed)} stages: {' + '.join(f'{v:.1f}' for v in printed)} = {total:.1f} s,"
        f" foot {foot_s if foot_s is not None else '—'} s,"
        f" {HEALTH_PATH} {boot_s if boot_s is not None else '—'} s"
    )
    if problems:
        fail(f"{summary}; {'; '.join(problems[:4])}")
    return summary


def footer_stamp_one_line(ctx: Any) -> str:
    """The footer's build stamp is one line at 375 px in both themes and reads `build <sha>`."""
    audit = audit_for(ctx)
    if not audit.stamp_samples:
        fail("the footer stamp was not measured at 375 px")
    problems: list[str] = []
    forms: list[str] = []
    for sample in audit.stamp_samples:
        text = str(sample.get("text", ""))
        where = sample.get("where", "")
        size = f"{sample.get('w')}x{sample.get('h')} px"
        m = STAMP_TEXT_RE.match(text)
        if m is None:
            problems.append(f"{where} stamp reads {text!r}, not 'build <sha>'")
        else:
            forms.append("dev" if m.group(1) == "dev" else f"{len(m.group(1))} hex")
        if int(sample.get("lines", 1)) > 1:
            problems.append(f"{where} {text!r} {size}, {sample.get('lines')} lines")
    if problems:
        fail("; ".join(problems[:3]))
    first = audit.stamp_samples[0]
    return (
        f"stamp {sorted(set(forms))[0] if forms else '?'}, one line at 375 px in"
        f" {len(audit.stamp_samples)} contexts ({first.get('w')}x{first.get('h')} px)"
    )


def permalink_truth(ctx: Any) -> str:
    """The box under the strip promises only what the tab restored, for every link shape."""
    result = permalink_audit_for(ctx)
    if not result.loads:
        fail("no link was loaded")
    if result.failures:
        fail(
            f"{len(result.failures)} promise(s) the form did not keep over {len(result.loads)}"
            f" loads: {'; '.join(result.failures[:4])}"
        )
    return (
        f"{len(PERMALINK_SHAPES)} link shapes × {len(PERMALINK_CONTEXTS)} contexts,"
        f" box == restored state ({len(result.loads)} loads)"
    )


def exact_integers(ctx: Any) -> str:
    """2^53 + 1 never silently becomes 2^53, through the API or the browser's number box.

    The API path sends it as a JSON number: the contract (`playground.coerce`) refuses a whole
    number at or above `BROWSER_EXACT_MAX` with `REASON_ABOVE_BROWSER_RANGE` — a client's JSON
    double cannot be told from a browser's rounded one — so the accepted answers are the exact
    echo in the Request JSON or that refusal with nothing run; a rounded echo, a float, or a
    refusal beside a request that still carries a value fails. The browser path types it into
    the number box: the request carries it exactly or a message appears under the field."""
    name, info = endpoint_for(ctx, "play")
    overrides = _form_overrides(
        info,
        family=EXACT_INT_FAMILY,
        module=EXACT_INT_MODULE,
        function=EXACT_INT_FUNCTION,
        args=EXACT_INT_ARGS,
        component="Number",
    )
    _, outputs = call(ctx, "play", overrides)
    request = next(
        (d for d in json_documents(outputs) if isinstance(d.get("args"), list | dict)), None
    )
    refused = playground.REASON_ABOVE_BROWSER_RANGE in plain_text("\n".join(texts_of(outputs)))
    echoed: Any = None
    if request is not None:
        echoed = request["args"]
        if isinstance(echoed, dict):
            echoed = echoed.get(EXACT_INT_FIELD)
        elif isinstance(echoed, list) and len(echoed) >= 2:
            echoed = echoed[1]
    if request is not None and echoed == EXACT_INT and not isinstance(echoed, float):
        api = f"API path echoes {EXACT_INT} exactly"
    elif refused and request is None:
        api = f"API path refuses {EXACT_INT} as a JSON number ({REFUSAL_WORDS!r}), nothing ran"
    elif refused:
        fail(f"/{name}: refused {EXACT_INT_FIELD}={EXACT_INT} yet the request carries {echoed!r}")
    elif request is None:
        fail(
            f"/{name}: neither a Request-and-response JSON with the call's args nor the"
            f" browser-range refusal in the outputs"
        )
    else:
        fail(f"/{name}: sent {EXACT_INT_FIELD}={EXACT_INT}, the request carries {echoed!r}")
    probe = exact_int_audit_for(ctx)
    if probe.message:
        return f"{api}; browser: {probe.typed} refused with a message ({probe.message[:60]!r})"
    if probe.request == str(EXACT_INT):
        return f"{api}; browser: typed {probe.typed}, request {probe.request}"
    fail(
        f"{api}; browser: typed {probe.typed}, the request carries"
        f" {probe.request or 'nothing'} and no message under the field"
    )


_RATIO_RE = re.compile(r"(\d+(?:\.\d+)?):1")


def _ratio_of(item: str) -> float:
    m = _RATIO_RE.search(item)
    return float(m.group(1)) if m else float("inf")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ENDPOINT_CHECKS: tuple[Callable[[Any], str], ...] = (
    expected_api_names_check,
    hero_result,
    playground_levenshtein,
    playground_decimals,
    family_dropdown_foreign_value,
    race_cell,
    llm_rmsnorm_parity,
    governed_lane,
    receipt_tone,
    webhook_privacy,
    ecosystem_counts,
    every_endpoint_answers,
)
PAGE_CHECKS: tuple[Callable[[Any], str], ...] = (health_ready, shared_stamp, native_only)
BROWSER_CHECKS: tuple[Callable[[Any], str], ...] = (
    console_clean,
    no_horizontal_scroll,
    targets_44px,
    axe_serious_critical,
    contrast_hero,
    contrast_buttons,
    contrast_code,
    value_boxes_unclipped,
    no_stock_chrome,
    no_stock_code_labels,
    no_toasts,
    dropdown_dismissal,
    dropdown_reopens,
    boot_card_timings,
    boot_row_live,
    voids,
    footer_stamp_one_line,
    nav_separators,
    checkboxes_dark_unfilled,
    no_identifiers_in_copy,
    cls_budget,
    permalink_truth,
    exact_integers,
    refusal_convention,
    eco_table_fits,
)
CHECKS: tuple[Callable[[Any], str], ...] = ENDPOINT_CHECKS + PAGE_CHECKS + BROWSER_CHECKS


def checks_for(space_name: str = SPACE_NAME) -> list[tuple[str, Callable[[Any], str]]]:
    """`(name, check)` pairs in run order, the shape `verify_remote.run_checks` takes."""
    if space_name != SPACE_NAME:
        raise ValueError(f"these checks belong to {SPACE_NAME!r}, not {space_name!r}")
    return [(fn.__name__, fn) for fn in CHECKS]


def install(
    register: Callable[..., Callable],
    error: type[BaseException] | None = None,
    skipped: type[BaseException] | None = None,
) -> list[str]:
    """Register every check under the flagship's name and adopt the tool's signal classes."""
    if error is not None:
        _SIGNALS["fail"] = error
    if skipped is not None:
        _SIGNALS["skip"] = skipped
    names = []
    for _name, fn in checks_for():
        register(SPACE_NAME)(fn)
        names.append(fn.__name__)
    return names


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------


def _tools_module() -> Any:
    tools = HERE.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    return importlib.import_module("verify_remote")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="run the flagship's checks against a live URL")
    ap.add_argument("--url", required=True, help="http://127.0.0.1:7860 or the Space URL")
    ap.add_argument("--staged", type=Path, default=None, help="staged dir holding .shared_sha")
    ap.add_argument("--shared-sha", default=None, help="expected shared sha (overrides --staged)")
    ap.add_argument("--budget", type=float, default=120.0, help="seconds per check")
    ap.add_argument("--only", default="", help="comma-separated check names (default: every check)")
    ap.add_argument(
        "--audit-json",
        type=Path,
        default=None,
        help="write every browser audit this run took (the page facts behind the gates) here",
    )
    ap.add_argument(
        "--phase",
        choices=PHASES,
        default=None,
        help=(
            f"'{PHASE_KEYED}' when the tenant key is loaded into the app under test: the"
            f" not-configured card then fails, and {', '.join(KEYED_REQUIRED)} run whatever"
            f" --only says (default: ${PHASE_ENV}, else {PHASE_NOKEY})"
        ),
    )
    a = ap.parse_args(argv)
    try:
        set_phase(a.phase or os.environ.get(PHASE_ENV, "").strip() or PHASE_NOKEY)
    except ValueError as exc:
        print(str(exc))  # noqa: T201
        return 2
    try:
        vr = _tools_module()
    except ImportError as exc:
        print(f"apps/spaces/tools is not importable ({exc}); run from the checkout")  # noqa: T201
        return 2
    expected = a.shared_sha
    if expected is None and a.staged is not None:
        stamp = a.staged / ".shared_sha"
        expected = stamp.read_text(encoding="utf-8").strip() if stamp.is_file() else None
    _SIGNALS["fail"] = vr.VerifyError
    _SIGNALS["skip"] = vr.VerifySkipped
    from manifest import load_manifest

    space = load_manifest().space(SPACE_NAME)
    ctx = vr.VerifyContext(
        space=space,
        fetch=vr.urllib_fetch,
        base_url=a.url,
        expected_shared_sha=expected,
        budget_s=a.budget,
    )
    wanted = {n.strip() for n in a.only.split(",") if n.strip()}
    selected = select_checks(wanted)
    print(f"{SPACE_NAME}: {phase()} phase, {len(selected)} checks against {a.url}")  # noqa: T201
    report = vr.run_checks(ctx, selected)
    for line in report.lines():
        print(line)  # noqa: T201 - the CLI's output
    if a.audit_json is not None:
        a.audit_json.parent.mkdir(parents=True, exist_ok=True)
        a.audit_json.write_text(json.dumps(audits_as_json(), indent=1, default=str) + "\n")
    return 0 if report.ok else 1


def audits_as_json() -> dict[str, Any]:
    """Every cached browser audit as plain data, keyed by base URL and kind, with the phase."""
    from dataclasses import asdict

    out: dict[str, Any] = {"phase": phase()}
    for kind, store in (
        ("audit", _audits),
        ("cls", _cls_audits),
        ("permalinks", _permalink_audits),
        ("exact_int", _exact_int_audits),
        ("refusals", _refusal_audits),
    ):
        for base, value in store.items():
            out.setdefault(base, {})[kind] = asdict(value)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
