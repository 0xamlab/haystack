"""Golden screenshots of the flagship: capture, manifest, pixel diff.

Every tab is rendered at 1440x900, 1024x768 and 375x812, in light and dark, by headless
Chromium at device scale 1. The PNGs live in ``tests/spaces/golden/`` next to
``manifest.json`` (viewport, theme, tab, format, sha256, bytes per file). The test in
``test_flagship_goldens.py`` takes fresh screenshots of a running app and fails on drift.

Regenerate (the app must be running — ``apps/spaces/algenta/scripts/spaces-flagship-run.sh``)::

    <venv>/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:7860 --regenerate

Regeneration proves itself: after the goldens are written a second capture of the same app is
diffed against them, and the command fails (exit 1) naming the first differing row whenever
any golden differs — a baseline the same page cannot reproduce twice is not a baseline
(``--no-verify`` skips the proof for a quick look, never for the committed set).

Compare without pytest (exit 1 and the first differing row on any drift)::

    <venv>/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:7860

Determinism: the capture waits for the app's boot hold to lift (``verify_checks.select_tab``
blocks on ``html.alg-booting``), requires the web fonts (Inter, JetBrains Mono) to have loaded
— their faces present, the four faces the design paints with force-loaded and reported loaded
(``_wait_for_fonts``; ``document.fonts.status`` alone reads ``loaded`` while the set is still
empty), a shot with fallback glyphs is refused, not compared — and waits for two consecutive viewport
shots to be byte-identical (late layout settles), and every page is loaded in independent contexts
until two consecutive loads encode byte-identically (``_capture_agreed``: a renderer now and then
rasterises a whole load's text in another anti-aliasing, so one load proves nothing; a page that
never reproduces itself is refused); transitions and animations are switched off,
and the parts of a page a second run legitimately changes — every measured number (the hero
figure and label, every chip row of a result card, the lane charts and tables, the status rows,
the boot rows), the boot-time pill, live Hub counts and board rows, every ``<time>`` stamp and
every UTC stamp wherever a tab prints one (matched by text, so a new tab needs no registration),
the deploy stamp — are masked with the theme's own surface colour
(``design.COLOR_TOKENS["surface-2"]``), so the diff sees layout, type and colour, not the clock
or the measurement. The app's *state* is a precondition, not a mask, and the manifest records
it (``state``: ``hero_status``, ``hub_state``, ``space_id``): ``--regenerate`` reads ``/health``
and ``/config`` first and refuses (exit 2) unless the opening card is ``measured``, the
Ecosystem table carries the Hub's live counts (``hub_state: fetched`` — outside a Space nothing
is fetched at boot and the tab draws a three-column table under a ``hub_counts_not_fetched``
card, a layout the deployed Space never shows) and the app runs as the Space does
(``SPACE_ID`` set); ``--accept-hero-status`` / ``--accept-hub-state`` / ``--allow-local`` record
another state deliberately. A comparison against a manifest whose state differs from the live
app's — or that records none — is refused before any pixel is read, loudly (exit 3, the reason
printed; ``pytest.skip`` with the same reason in the gate), never failed on six Ecosystem size
diffs and never passed. The diff (Pillow) is strict on every unmasked pixel: a pixel counts as
changed when no pixel of the other image within ``AA_TOLERANCE_PX`` (one pixel, in either
direction) matches it to ``CHANNEL_TOLERANCE`` per channel — a glyph edge that moved by a
sub-pixel is tolerated, a digit that changed is not — and one changed pixel fails.

Size: each golden stays under 500 KB (the repo's pre-commit ceiling). A full-page PNG over
the limit falls back to the viewport alone, then to JPEG quality 80; the manifest records
which. Stdlib + Pillow; Playwright only inside ``capture_all``.

Helpers carry a leading underscore: pytest-relaxed, present on developer machines,
collects every public function of a non-test module as a test (the ``_rules.py`` convention).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
# ALGENTA_GOLDEN_DIR points the gate at another golden set (QA against a scratch capture).
GOLDEN_DIR = Path(os.environ.get("ALGENTA_GOLDEN_DIR") or REPO / "tests" / "spaces" / "golden")
MANIFEST_NAME = "manifest.json"
SHARED_DIR = REPO / "apps" / "spaces" / "_shared"
ALGENTA_DIR = REPO / "apps" / "spaces" / "algenta"
for _p in (SHARED_DIR, ALGENTA_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from algenta_spaces import design  # noqa: E402

VIEWPORTS: dict[str, tuple[int, int]] = {
    "desktop": (1440, 900),
    "tablet": (1024, 768),
    "phone": (375, 812),
}
THEMES: tuple[str, ...] = ("light", "dark")
MAX_BYTES = 500 * 1024
PIXEL_THRESHOLD = 0  # strict: no unmasked pixel may differ beyond the anti-aliasing tolerance
CHANNEL_TOLERANCE = 24  # per-channel difference (0-255) that counts as a changed pixel
AA_TOLERANCE_PX = 1  # a pixel may match any pixel of the other image this far away
JPEG_QUALITY = 80
SETTLE_MS = 600
PAGE_TIMEOUT_MS = 90_000
STABLE_GAP_MS = 400
STABLE_MAX_SHOTS = 8
#: Every element that prints a measured or live number is masked as a block, so a measurement
#: that changes (P95 0.20 → 0.14 ms, a chip that grows a digit and pushes its neighbours) never
#: reaches the diff, while the layout around it does.
MASK_SELECTORS: tuple[str, ...] = (
    ".alg-card-foot",
    ".alg-shell-stamp",
    ".alg-shell-badges",  # "N families warm in X s" differs on every boot
    ".alg-lane-chart",
    ".alg-lane-table tbody",  # median, MAD, CV, P95, min – max per lane
    ".alg-lane-val",
    ".alg-eco-table tbody",  # live Hub downloads and likes
    ".alg-eco-table .alg-chips",  # the head chips: repositories, functions, downloads, likes
    ".alg-board-table tbody",  # this container's race rows
    ".alg-hero-num",
    ".alg-hero-label",
    ".alg-card-result .alg-chips",  # n, P95, MAD, spread, parity, version, measured … chips
    ".alg-card-warn .alg-chips",  # the held card's stamp chip
    ".alg-chip[data-kind='measured']",
    ".alg-status",  # "done in 6.07 ms"
    "time[data-stamp-kind]",  # counted / measured / fetched / computed <UTC>
    "time.alg-time",  # every stamp a card prints (cards.time_stamp)
    ".alg-boot-elapsed",
    ".alg-boot-detail",  # "19 families warm in 1.7 s", "0.11 ms per kernel call, n = 21"
    ".alg-boot-foot",
    "[data-golden='mask']",
)
#: Every leaf element whose text carries a UTC stamp is masked too (`page.get_by_text`), so a
#: `measured …`, `fetched …` or `computed …` chip on any tab is covered without registration.
UTC_STAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")
FONT_FAMILIES: tuple[str, ...] = ("Inter", "JetBrains Mono")
HEALTH_PATH = "/health"
CONFIG_PATH = "/config"
HERO_MEASURED = "measured"
#: The Ecosystem table's Hub state: the live counts arrived (`fetched`), or the code the quiet
#: card prints (`hub_counts_not_fetched` outside a Space, `hub_counts_unreachable`, …).
HUB_FETCHED = "fetched"
HUB_UNKNOWN = "unknown"
HUB_TABLE_MARKER = "alg-eco-table"
HUB_COLUMN_MARKER = 'data-label="on the Hub"'  # eco_tab.COLUMN_HUB, present only when fetched
HUB_CODE_RE = re.compile(r"unavailable · (hub_counts_[a-z_]+)")
#: The deployed Space's identity and host, as `SPACE_ID` / `SPACE_HOST` name them; the one
#: command that regenerates the committed set runs the app with both set and the network on.
DEPLOYED_SPACE_ID = "thyn-ai/algenta"
DEPLOYED_SPACE_HOST = "thyn-ai-algenta.hf.space"
REGENERATE_COMMAND = (
    f"SPACE_ID={DEPLOYED_SPACE_ID} SPACE_HOST={DEPLOYED_SPACE_HOST} … python app.py  # network on,"
    " Hub counts fetched at boot\n"
    "<venv>/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:<port> --regenerate"
)
#: The compare path's exit code when the states differ or the manifest records none: neither a
#: pass (0) nor a pixel failure (1) — a refusal with its reason printed.
EXIT_STATE_MISMATCH = 3
# A tuple, not an inline `except (A, B):` — the repository's formatter targets 3.14 and would
# drop the parentheses (PEP 758), which CPython 3.12 (this venv) rejects.
_MANIFEST_READ_ERRORS: tuple[type[BaseException], ...] = (OSError, json.JSONDecodeError)
FREEZE_CSS = (
    "*, *::before, *::after { transition: none; animation: none; caret-color: transparent; }"
)
# Inter and JetBrains Mono arrive from Google Fonts after first paint, and Gradio injects their
# `@font-face` rules only when the app mounts (measured: `document.fonts` is EMPTY until
# ~370 ms after `domcontentloaded`, the faces read `loading` until ~700 ms). An empty
# FontFaceSet reports `status === 'loaded'` and `check()` true for every family, so a wait on
# the status alone passes inside that window and a shot taken before the swap renders the
# metric-matched fallback face: the same layout, a few glyph-edge pixels past the tolerance on
# every text row (round 4's proof capture refused 2 of 36 goldens for it, the two visual runs
# drifted on 2 then 5 others). The wait is three steps: the families' faces exist, the four
# faces the design uses are force-loaded (`document.fonts.load` — a weight no text on the page
# has asked for yet would otherwise stay `unloaded`, and `check()` answers false for it), and
# every one of them reports loaded.
FONTS_READY_JS = "document.fonts.status === 'loaded'"
FONT_FACES_JS = (
    "(families) => { const have = new Set([...document.fonts].map(f =>"
    " f.family.replace(/[\"']/g, ''))); return families.every(f => have.has(f)); }"
)
FONT_LOAD_JS = "(specs) => Promise.all(specs.map(s => document.fonts.load(s))).then(() => true)"
FONTS_LOADED_JS = (
    "(specs) => document.fonts.status === 'loaded' && specs.every(s => document.fonts.check(s))"
)
#: The faces the design paints with (`design.py`: Inter 400/600, JetBrains Mono 400/600).
FONT_SPECS: tuple[str, ...] = (
    '400 16px "Inter"',
    '600 16px "Inter"',
    '400 13px "JetBrains Mono"',
    '600 13px "JetBrains Mono"',
)
FONTS_TIMEOUT_MS = 15_000
#: A page is captured in independent loads (a fresh context each) until two in a row are
#: byte-identical; past `LOADS_MAX` the capture is refused with the reason. With the fonts gate
#: closed, round 4 still saw 2–3 of 36 loads per pass render every text row of a page in a
#: different anti-aliasing — word starts and widths identical to the pixel, glyph stems crisp in
#: one load and spread over two pixels in the other (up to 90 of 255 apart), inside the viewport
#: as much as below it — for the whole life of that load (consecutive viewport and full-page
#: shots agreed with each other and not with any other load), with no DOM signature (scroll 0,
#: visual viewport scale 1, the same fractional rects, the same loaded faces, read on every shot
#: of the tool's own loop by `probe_capture_geom.py` in the round's evidence folder) and
#: unchanged by `--disable-gpu` / `--disable-lcd-text`: a state of the renderer that loaded the
#: page, not the page. Two loads agreeing is the reproducibility the golden claims.
LOADS_TO_AGREE = 2
LOADS_MAX = 5


def _wait_for_fonts(page: Any) -> None:
    """Wait for the web fonts and refuse the shot when a family did not load: a golden rendered
    with fallback glyphs would drift every text line and is not reproducible. Three steps — the
    faces exist (Gradio adds them after first paint), the design's faces are loaded on purpose,
    every one reports loaded — because an empty or partly requested FontFaceSet says `loaded`."""
    import verify_checks

    try:
        page.wait_for_function(FONT_FACES_JS, arg=list(FONT_FAMILIES), timeout=FONTS_TIMEOUT_MS)
        page.evaluate(FONT_LOAD_JS, list(FONT_SPECS))
        page.wait_for_function(FONTS_LOADED_JS, arg=list(FONT_SPECS), timeout=FONTS_TIMEOUT_MS)
    except Exception as exc:  # noqa: BLE001 - reported below by family, not swallowed
        print(f"web fonts not ready after {FONTS_TIMEOUT_MS} ms: {exc}")
    missing = verify_checks.fonts_missing(page, FONT_FAMILIES)
    if missing:
        raise RuntimeError(
            f"web fonts not loaded: {', '.join(missing)} — the capture is refused, a golden with"
            " fallback glyphs is not reproducible"
        )


def _hero_status(base_url: str, timeout_s: float = 30.0) -> str:
    """`hero.status` from the running app's `/health` (`measured`, `noisy`, …), or `unknown`."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + HEALTH_PATH, timeout=timeout_s) as r:  # noqa: S310
            body = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"{HEALTH_PATH} not readable: {exc}")
        return "unknown"
    return _hero_status_of(body)


def _hero_status_of(health: Any) -> str:
    hero = health.get("hero") if isinstance(health, dict) else None
    status = hero.get("status") if isinstance(hero, dict) else None
    return str(status) if status else "unknown"


def _manifest_hero_status(golden_dir: Path = GOLDEN_DIR) -> str | None:
    """The `hero_status` the goldens were captured under, or None for a manifest without one."""
    try:
        data = json.loads((golden_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    except _MANIFEST_READ_ERRORS:
        return None
    value = data.get("hero_status")
    return str(value) if value else None


def _fetch_json(base_url: str, path: str, timeout_s: float = 30.0) -> Any:
    """The JSON body at `path` on the running app, or None with the reason printed."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=timeout_s) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"{path} not readable: {exc}")
        return None


def _hub_state_of_html(html: str) -> str:
    """The Ecosystem table's state from its markup: the Hub code the quiet card prints, else
    `fetched` when the Hub column is drawn, else `unknown` (no table in the markup)."""
    if HUB_TABLE_MARKER not in html:
        return HUB_UNKNOWN
    m = HUB_CODE_RE.search(html)
    if m:
        return m.group(1)
    if HUB_COLUMN_MARKER in html:
        return HUB_FETCHED
    return HUB_UNKNOWN


def _hub_state_of_config(config: Any) -> str:
    """The Ecosystem table's state from Gradio's `/config` (every component's initial value)."""
    components = config.get("components") if isinstance(config, dict) else None
    for component in components or ():
        props = component.get("props") if isinstance(component, dict) else None
        value = props.get("value") if isinstance(props, dict) else None
        if isinstance(value, str) and HUB_TABLE_MARKER in value:
            return _hub_state_of_html(value)
    return HUB_UNKNOWN


def _space_id_of(health: Any) -> str:
    return str(health.get("space_id") or "").strip() if isinstance(health, dict) else ""


def _deploy_state(base_url: str) -> dict[str, str]:
    """What the running app is: the opening card's state, the Ecosystem table's Hub state and
    the Space it runs as — the three facts a golden set pictures and must be compared under."""
    health = _fetch_json(base_url, HEALTH_PATH)
    config = _fetch_json(base_url, CONFIG_PATH)
    return {
        "hero_status": _hero_status_of(health) if health is not None else HUB_UNKNOWN,
        "hub_state": _hub_state_of_config(config),
        "space_id": _space_id_of(health),
    }


def _manifest_state(golden_dir: Path = GOLDEN_DIR) -> dict[str, str] | None:
    """The state the goldens were captured under, or None for a manifest that records none."""
    try:
        data = json.loads((golden_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    except _MANIFEST_READ_ERRORS:
        return None
    state = data.get("state")
    if not isinstance(state, dict):
        return None
    return {k: str(state.get(k) or "") for k in ("hero_status", "hub_state", "space_id")}


def _state_mismatch(recorded: dict[str, str] | None, live: dict[str, str]) -> str | None:
    """Why a comparison is refused: the manifest records no state, or a fact differs. None
    when every recorded fact matches the live app."""
    if recorded is None:
        return (
            "the manifest records no state (hero_status, hub_state, space_id); regenerate in the"
            f" deployed state:\n{REGENERATE_COMMAND}"
        )
    differences = []
    for key, name in (
        ("hero_status", "opening card"),
        ("hub_state", "Ecosystem Hub state"),
        ("space_id", "Space"),
    ):
        want, have = recorded.get(key, ""), live.get(key, "")
        if want != have:
            differences.append(f"{name} {want or 'none'!r} in the goldens, {have or 'none'!r} live")
    if not differences:
        return None
    return (
        "the goldens picture another state than the app serves: "
        + "; ".join(differences)
        + " — not compared (run the app in the goldens' state, or regenerate in the deployed one)"
    )


def _page_hub_state(page: Any) -> str:
    """The Ecosystem table's state as the displayed panel renders it."""
    html = page.evaluate(
        "() => { const vis = (el) => el.getBoundingClientRect().height > 0;"
        " const panel = [...document.querySelectorAll('[role=tabpanel]')].find(vis);"
        " return panel === undefined ? '' : panel.innerHTML; }"
    )
    return _hub_state_of_html(str(html or ""))


def _tab_slugs() -> tuple[str, ...]:
    """The flagship's tab slugs, from the tabs when importable, else the frozen contract."""
    import verify_checks

    return verify_checks.tab_slugs()


def _learn_labels(browser: Any, base_url: str) -> None:
    """One wide page reads `data-tab-id -> label` from the strip, so the phone captures can find
    the tabs Gradio folds into its "More tabs" menu."""
    import verify_checks

    context = browser.new_context(viewport=verify_checks.WIDE_VIEWPORT)
    page = context.new_page()
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector(".alg-shell-stamp", state="attached")
    verify_checks.learn_tab_labels(page)
    context.close()


def _bring_to_front(page: Any, slug: str) -> None:
    """The permalink is asked for first (`?tab=`); the tab is then selected explicitly through
    the same strip or overflow menu a visitor uses, and the capture fails if it is not."""
    import verify_checks

    verify_checks.select_tab(page, slug)


def _mask_color(theme: str) -> str:
    """The theme's surface-2 token: the mask must not introduce a colour the page lacks."""
    light, dark = design.COLOR_TOKENS["surface-2"]
    return dark if theme == "dark" else light


@dataclass(frozen=True)
class Shot:
    tab: str
    viewport: str
    theme: str
    width: int
    height: int

    @property
    def stem(self) -> str:
        return f"{self.tab}-{self.viewport}-{self.theme}"

    def url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/?tab={self.tab}"


@dataclass(frozen=True)
class Entry:
    """One golden: `width` × `height` is the viewport the shot was taken at, `image_width` ×
    `image_height` the picture's own pixels (a full-page PNG is as tall as the page; 0 in a
    manifest that predates the fields)."""

    file: str
    tab: str
    viewport: str
    theme: str
    width: int
    height: int
    format: str  # png | jpeg
    full_page: bool
    sha256: str
    bytes: int
    image_width: int = 0
    image_height: int = 0


def _shots(slugs: Sequence[str] | None = None) -> tuple[Shot, ...]:
    slugs = tuple(slugs) if slugs is not None else _tab_slugs()
    return tuple(
        Shot(tab, name, theme, w, h)
        for tab in slugs
        for name, (w, h) in VIEWPORTS.items()
        for theme in THEMES
    )


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def _read_manifest(golden_dir: Path = GOLDEN_DIR) -> list[Entry]:
    data = json.loads((golden_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    return [Entry(**row) for row in data["entries"]]


def _write_manifest(
    entries: Iterable[Entry],
    golden_dir: Path = GOLDEN_DIR,
    *,
    hero_status: str | None = None,
    state: Mapping[str, str] | None = None,
) -> Path:
    rows = [asdict(e) for e in sorted(entries, key=lambda e: e.file)]
    payload: dict[str, Any] = {
        "viewports": {k: list(v) for k, v in VIEWPORTS.items()},
        "themes": list(THEMES),
        "pixel_threshold": PIXEL_THRESHOLD,
        "channel_tolerance": CHANNEL_TOLERANCE,
        "aa_tolerance_px": AA_TOLERANCE_PX,
        "max_bytes": MAX_BYTES,
        # the determinism contract the capture enforced: these fonts loaded, motion off, every
        # UTC stamp and the registered live regions masked
        "fonts": list(FONT_FAMILIES),
        "motion": "off",
        "masks": [*MASK_SELECTORS, f"text:{UTC_STAMP_RE.pattern}"],
        "entries": rows,
    }
    if state is not None:
        payload["state"] = dict(state)  # what the app was when the goldens were captured
        hero_status = hero_status or state.get("hero_status")
    if hero_status:
        payload["hero_status"] = hero_status  # the opening card's state the goldens picture
    golden_dir.mkdir(parents=True, exist_ok=True)
    target = golden_dir / MANIFEST_NAME
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _check_manifest(golden_dir: Path = GOLDEN_DIR, slugs: Sequence[str] | None = None) -> list[str]:
    """Problems with the committed goldens: missing files, size, sha, coverage."""
    problems: list[str] = []
    try:
        entries = _read_manifest(golden_dir)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return [f"manifest unreadable: {exc}"]
    wanted = {s.stem for s in _shots(slugs)}
    seen = set()
    for e in entries:
        path = golden_dir / e.file
        stem = path.stem
        seen.add(stem)
        if not path.is_file():
            problems.append(f"{e.file}: missing")
            continue
        size = path.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"{e.file}: {size // 1024} KB over {MAX_BYTES // 1024} KB")
        if size != e.bytes:
            problems.append(f"{e.file}: {size} bytes, manifest says {e.bytes}")
        if _sha256_of(path) != e.sha256:
            problems.append(f"{e.file}: sha256 differs from the manifest")
        if e.image_width and e.image_height:
            actual = _image_size(path)
            if actual != (e.image_width, e.image_height):
                problems.append(
                    f"{e.file}: {actual[0]}x{actual[1]} px, manifest says"
                    f" {e.image_width}x{e.image_height}"
                )
        if (e.viewport, e.theme) not in {(v, t) for v in VIEWPORTS for t in THEMES}:
            problems.append(f"{e.file}: unknown viewport/theme {e.viewport}/{e.theme}")
    for stem in sorted(wanted - seen):
        problems.append(f"{stem}: no golden")
    for stem in sorted(seen - wanted):
        problems.append(f"{stem}: golden for no tab")
    return problems


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _wait_until_stable(page: Any, masks: list[Any], theme_mask: str) -> int:
    """Take viewport shots `STABLE_GAP_MS` apart until two in a row are byte-identical (late
    layout such as a table filling in). Returns the number of shots taken; gives up after
    `STABLE_MAX_SHOTS` and lets the diff decide."""
    previous = b""
    for n in range(1, STABLE_MAX_SHOTS + 1):
        current = page.screenshot(
            type="png",
            full_page=False,
            mask=masks,
            mask_color=theme_mask,
            animations="disabled",
            caret="hide",
            scale="css",
        )
        if current == previous:
            return n
        previous = current
        page.wait_for_timeout(STABLE_GAP_MS)
    return STABLE_MAX_SHOTS


def _masks(page: Any) -> list[Any]:
    """The mask locators: the registered regions plus every leaf that prints a UTC stamp."""
    return [page.locator(sel) for sel in MASK_SELECTORS] + [page.get_by_text(UTC_STAMP_RE)]


def _encode(page: Any, shot: Shot, out_dir: Path, theme_mask: str) -> Entry:
    """PNG full page; over the limit, the viewport alone; still over, JPEG."""
    masks = _masks(page)
    _wait_until_stable(page, masks, theme_mask)
    attempts: list[tuple[str, bool]] = [("png", True), ("png", False), ("jpeg", False)]
    last: Entry | None = None
    for fmt, full in attempts:
        path = out_dir / f"{shot.stem}.{'png' if fmt == 'png' else 'jpg'}"
        kwargs: dict[str, Any] = {
            "path": str(path),
            "type": fmt,
            "full_page": full,
            "mask": masks,
            "mask_color": theme_mask,
            "animations": "disabled",
            "caret": "hide",
            "scale": "css",
        }
        if fmt == "jpeg":
            kwargs["quality"] = JPEG_QUALITY
        page.screenshot(**kwargs)
        size = path.stat().st_size
        image_width, image_height = _image_size(path)
        last = Entry(
            file=path.name,
            tab=shot.tab,
            viewport=shot.viewport,
            theme=shot.theme,
            width=shot.width,
            height=shot.height,
            format=fmt,
            full_page=full,
            sha256=_sha256_of(path),
            bytes=size,
            image_width=image_width,
            image_height=image_height,
        )
        if size <= MAX_BYTES:
            break
        path.unlink()
    if last is None or last.bytes > MAX_BYTES:
        raise RuntimeError(f"{shot.stem}: no encoding under {MAX_BYTES // 1024} KB")
    return last


def _capture_all(
    base_url: str,
    out_dir: Path,
    *,
    slugs: Sequence[str] | None = None,
    expect_hub_state: str | None = None,
) -> list[Entry]:
    """Screenshot every tab x viewport x theme of the running app into `out_dir`. With
    `expect_hub_state`, every Ecosystem page is read before its shot and a table in another
    state (a fetch that failed between `/config` and the capture) is refused, not captured."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    entries: list[Entry] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            _learn_labels(browser, base_url)
            for shot in _shots(slugs):
                entries.append(_capture_agreed(browser, base_url, shot, out_dir, expect_hub_state))
        finally:
            browser.close()
    return entries


def _capture_once(
    browser: Any, base_url: str, shot: Shot, out_dir: Path, expect_hub_state: str | None
) -> Entry:
    """One load of the page in a fresh context, through every wait, encoded into `out_dir`."""
    context = browser.new_context(
        viewport={"width": shot.width, "height": shot.height},
        device_scale_factor=1,
        color_scheme=shot.theme,
        reduced_motion="reduce",
    )
    try:
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        page.goto(shot.url(base_url), wait_until="domcontentloaded")
        page.wait_for_selector(".alg-shell-stamp", state="attached")
        page.add_style_tag(content=FREEZE_CSS)
        _wait_for_fonts(page)
        _bring_to_front(page, shot.tab)
        _wait_for_fonts(page)  # the mounted panel may have asked for a face anew
        page.wait_for_timeout(SETTLE_MS)
        if expect_hub_state is not None and shot.tab == "eco":
            seen = _page_hub_state(page)
            if seen != expect_hub_state:
                raise RuntimeError(
                    f"{shot.stem}: the Ecosystem table is {seen!r}, the capture expects"
                    f" {expect_hub_state!r} — refused, a golden in another state is not"
                    " the baseline"
                )
        return _encode(page, shot, out_dir, _mask_color(shot.theme))
    finally:
        context.close()


def _capture_agreed(
    browser: Any,
    base_url: str,
    shot: Shot,
    out_dir: Path,
    expect_hub_state: str | None,
    capture: Callable[..., Entry] | None = None,
) -> Entry:
    """The page loaded until two consecutive loads encode byte-identically (`LOADS_TO_AGREE`);
    the agreed file is what stays in `out_dir`. A load that rendered differently is named on
    stdout; `LOADS_MAX` loads without two agreeing refuse the capture with the reason."""
    once = capture or _capture_once
    previous: bytes | None = None
    for n in range(1, LOADS_MAX + 1):
        entry = once(browser, base_url, shot, out_dir, expect_hub_state)
        data = (out_dir / entry.file).read_bytes()
        if previous is not None and data == previous:
            if n > LOADS_TO_AGREE:
                print(f"{shot.stem}: reproduced on load {n} — an earlier load rendered differently")
            return entry
        previous = data
    raise RuntimeError(
        f"{shot.stem}: {LOADS_MAX} loads and no two in a row rendered the page identically — the"
        " capture is refused, a golden no second load reproduces is not a baseline"
    )


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Diff:
    golden_size: tuple[int, int]
    fresh_size: tuple[int, int]
    changed: int
    total: int

    @property
    def size_match(self) -> bool:
        return self.golden_size == self.fresh_size

    @property
    def ratio(self) -> float:
        return self.changed / self.total if self.total else 1.0

    @property
    def ok(self) -> bool:
        return self.size_match and self.changed <= PIXEL_THRESHOLD * self.total

    def describe(self) -> str:
        if not self.size_match:
            return f"size {self.fresh_size[0]}x{self.fresh_size[1]} vs golden {self.golden_size[0]}x{self.golden_size[1]}"
        if self.changed == 0:
            return f"identical beyond the {AA_TOLERANCE_PX}-px anti-aliasing tolerance"
        return (
            f"{self.changed} pixel{'s' if self.changed != 1 else ''} differ beyond the"
            f" {AA_TOLERANCE_PX}-px anti-aliasing tolerance ({self.ratio:.4%} of {self.total})"
        )


def _outside_neighbourhood(image: Any, reference: Any) -> Any:
    """A 1-bit mask of the pixels of `image` that no pixel of `reference` within
    `AA_TOLERANCE_PX` matches to `CHANNEL_TOLERANCE` in every channel: a glyph edge that moved
    by a sub-pixel finds its match next door, a digit that changed does not."""
    from PIL import ImageChops, ImageFilter

    size = 2 * AA_TOLERANCE_PX + 1
    low = reference.filter(ImageFilter.MinFilter(size))
    high = reference.filter(ImageFilter.MaxFilter(size))
    below = ImageChops.subtract(low, image)  # > 0 where the pixel is darker than any neighbour
    above = ImageChops.subtract(image, high)  # > 0 where it is lighter than any neighbour
    r, g, b = ImageChops.lighter(below, above).split()
    peak = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return peak.point(lambda v: 255 if v > CHANNEL_TOLERANCE else 0)


def _compare(golden: Path, fresh: Path, diff_out: Path | None = None) -> Diff:
    """Strict on every unmasked pixel: a pixel of either image counts as changed when no pixel
    of the other within `AA_TOLERANCE_PX` matches it to `CHANNEL_TOLERANCE` per channel; the
    count of such pixels must be zero. The mask of changed pixels is written to `diff_out`."""
    from PIL import Image, ImageChops

    with Image.open(golden) as g_img, Image.open(fresh) as f_img:
        g_size, f_size = g_img.size, f_img.size
        if g_size != f_size:
            return Diff(g_size, f_size, changed=g_size[0] * g_size[1], total=g_size[0] * g_size[1])
        g = g_img.convert("RGB")
        f = f_img.convert("RGB")
    mask = ImageChops.lighter(_outside_neighbourhood(f, g), _outside_neighbourhood(g, f))
    changed = mask.histogram()[255]
    total = g_size[0] * g_size[1]
    if diff_out is not None:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
        mask.save(diff_out)
    return Diff(g_size, f_size, changed=changed, total=total)


def _recapture(base_url: str, shot: Shot, out_dir: Path, expect_hub_state: str | None) -> Entry:
    """One more agreed capture of one page, in a browser of its own (the compare paths have
    closed theirs by the time a difference is read)."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            _learn_labels(browser, base_url)
            return _capture_agreed(browser, base_url, shot, out_dir, expect_hub_state)
        finally:
            browser.close()


def _shot_of(file: str) -> Shot | None:
    stem = Path(file).stem
    return next((s for s in _shots() if s.stem == stem), None)


def _compare_all(
    fresh_dir: Path,
    golden_dir: Path = GOLDEN_DIR,
    diff_dir: Path | None = None,
    *,
    base_url: str | None = None,
    expect_hub_state: str | None = None,
    retry_dir: Path | None = None,
    recapture: Callable[..., Entry] | None = None,
) -> dict[str, Diff]:
    """Every golden against its fresh shot. With `base_url`, a pixel difference must reproduce:
    the page is captured once more (`_recapture`, two agreeing loads) and only the second
    reading counts — a real drift differs on every load, the renderer's anti-aliasing state
    (see `LOADS_TO_AGREE`) does not survive a second agreed capture. Both readings are printed."""
    out: dict[str, Diff] = {}
    again = recapture or _recapture
    for entry in _read_manifest(golden_dir):
        fresh = fresh_dir / entry.file
        if not fresh.is_file():
            out[entry.file] = Diff((0, 0), (0, 0), changed=1, total=1)
            continue
        diff_out = (diff_dir / f"{Path(entry.file).stem}.diff.png") if diff_dir else None
        diff = _compare(golden_dir / entry.file, fresh, diff_out)
        shot = _shot_of(entry.file)
        if not diff.ok and diff.size_match and base_url and shot is not None:
            retry = retry_dir or fresh_dir.parent / "retry"
            second = again(base_url, shot, retry, expect_hub_state)
            retry_diff = _compare(golden_dir / entry.file, retry / second.file, diff_out)
            verdict = "reproduced" if not retry_diff.ok else "did not reproduce"
            print(
                f"  {entry.file}: {diff.describe()} on the first capture; {verdict} on a second"
                f" agreed capture ({retry_diff.describe()})"
            )
            diff = retry_diff
        out[entry.file] = diff
    return out


def _first_difference(results: dict[str, Diff]) -> str | None:
    """`try-phone-dark.png 0.4210% of pixels changed (…)` for the first golden (by name) that
    differs, or None when every golden matches — the one line a red run must print."""
    for name in sorted(results):
        diff = results[name]
        if not diff.ok:
            return f"{name} {diff.describe()}"
    return None


def _report(results: dict[str, Diff], diff_dir: Path) -> int:
    """Print one row per golden and the first differing row last; return the failure count."""
    failed = 0
    for name, diff in sorted(results.items()):
        tag = "OK" if diff.ok else "FAIL"
        failed += 0 if diff.ok else 1
        print(f"  [{tag}] {name} {diff.describe()}")
    first = _first_difference(results)
    if first is not None:
        print(f"  [FAIL] first difference: {first}; masks in {diff_dir}")
    return failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="capture or compare the flagship's goldens")
    ap.add_argument("--url", required=True, help="the running app, e.g. http://127.0.0.1:7860")
    ap.add_argument("--golden-dir", type=Path, default=GOLDEN_DIR)
    ap.add_argument("--regenerate", action="store_true", help="overwrite the goldens")
    ap.add_argument("--work", type=Path, default=None, help="where fresh shots and diffs go")
    ap.add_argument(
        "--accept-hero-status",
        default=HERO_MEASURED,
        help="the /health hero.status the goldens may picture (default: measured only)",
    )
    ap.add_argument(
        "--accept-hub-state",
        default=HUB_FETCHED,
        help="the Ecosystem table's Hub state the goldens may picture (default: fetched)",
    )
    ap.add_argument(
        "--allow-local",
        action="store_true",
        help="let --regenerate record an app that does not run as the Space (no SPACE_ID)",
    )
    ap.add_argument(
        "--no-verify",
        action="store_true",
        help="after --regenerate, skip the second capture that proves the goldens reproduce",
    )
    a = ap.parse_args(argv)
    live = _deploy_state(a.url)
    hero = live["hero_status"]
    print(
        f"state on {a.url}: hero {hero}, hub {live['hub_state']},"
        f" space {live['space_id'] or 'none (local)'}"
    )
    work = a.work or (a.golden_dir.parent / "_golden_work")
    if a.regenerate:
        refusals = []
        if hero != a.accept_hero_status:
            refusals.append(
                f"the opening card is {hero!r}, the goldens picture {a.accept_hero_status!r};"
                f" run on a quiet host, or pass --accept-hero-status {hero}"
            )
        if live["hub_state"] != a.accept_hub_state:
            refusals.append(
                f"the Ecosystem table is {live['hub_state']!r}, the goldens picture"
                f" {a.accept_hub_state!r}; run the app as the Space (SPACE_ID set, network on),"
                f" or pass --accept-hub-state {live['hub_state']}"
            )
        if not live["space_id"] and not a.allow_local:
            refusals.append(
                "the app does not run as the Space (no SPACE_ID); the deployed Space never shows"
                " a local layout — pass --allow-local to record one deliberately"
            )
        if refusals:
            for reason in refusals:
                print(f"  [FAIL] refusing to regenerate: {reason}")
            print(f"  the one command:\n{REGENERATE_COMMAND}")
            return 2
        for old in a.golden_dir.glob("*.*"):
            if old.suffix in {".png", ".jpg"}:
                old.unlink()
        entries = _capture_all(a.url, a.golden_dir, expect_hub_state=live["hub_state"])
        _write_manifest(entries, a.golden_dir, state=live)
        for e in sorted(entries, key=lambda e: e.file):
            print(
                f"  {e.file}  {e.bytes // 1024} KB  {e.format}"
                f"{'' if e.full_page else ' (viewport)'}  {e.image_width}x{e.image_height} px"
            )
        print(
            f"{len(entries)} goldens written to {a.golden_dir} (hero {hero}, hub"
            f" {live['hub_state']}, space {live['space_id'] or 'none'})"
        )
        if a.no_verify:
            print("  [SKIP] reproducibility not proven (--no-verify); do not commit this set")
            return 0
        _capture_all(a.url, work / "verify", expect_hub_state=live["hub_state"])
        results = _compare_all(
            work / "verify",
            a.golden_dir,
            work / "verify-diff",
            base_url=a.url,
            expect_hub_state=live["hub_state"],
            retry_dir=work / "verify-retry",
        )
        failed = _report(results, work / "verify-diff")
        if failed:
            print(
                f"  [FAIL] {failed} of {len(results)} goldens did not reproduce on a second"
                " capture of the same app: the set is not deterministic and must not be committed"
            )
            return 1
        print(f"verified: a second capture matches all {len(results)} goldens")
        return 0
    problems = _check_manifest(a.golden_dir)
    if problems:
        for p in problems:
            print(f"  [FAIL] {p}")
        return 1
    mismatch = _state_mismatch(_manifest_state(a.golden_dir), live)
    if mismatch is not None:
        print(f"  [SKIP] {mismatch}")
        return EXIT_STATE_MISMATCH
    _capture_all(a.url, work / "fresh", expect_hub_state=live["hub_state"])
    results = _compare_all(
        work / "fresh",
        a.golden_dir,
        work / "diff",
        base_url=a.url,
        expect_hub_state=live["hub_state"],
        retry_dir=work / "retry",
    )
    failed = _report(results, work / "diff")
    print(
        f"{len(results) - failed}/{len(results)} goldens match"
        + (f"; diffs in {work / 'diff'}" if failed else "")
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_main())
