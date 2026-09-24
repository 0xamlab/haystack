"""Permalink truth against a launched flagship — the box under the strip promises only what the
tab restored.

Run against an app launched for real::

    ALGENTA_FLAGSHIP_URL=http://127.0.0.1:7860 <venv>/bin/python -m pytest \
        --confcutdir=tests/spaces tests/spaces/visual/test_flagship_permalinks.py -m slow -q

One test per link shape (`verify_checks.PERMALINK_SHAPES`): the seven shapes where round 2's
box promised a state the tab had not restored — arguments without a function, a word for a
number box, a decimal for a whole number, a foreign function, an unknown tab, a size the
candidate does not offer, a function that is no candidate — and the three full shapes the tab
must restore in full and the box must keep. Each loads the link in headless Chromium at
1440x900 (light) and 375x812 (dark), waits for the boot hold and the restore to settle, reads
the box and every control of the displayed form, and asserts with `permalink_problems` that
every function and argument the box names is visible in the form (and, for a full shape, that
nothing the tab restored was lost). The same reading is the `permalink_truth` gate of
`verify_checks.py`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.slow]

URL = os.environ.get("ALGENTA_FLAGSHIP_URL", "").strip()
if not URL:
    pytest.skip(
        "set ALGENTA_FLAGSHIP_URL to a running flagship (scripts/spaces-flagship-run.sh)",
        allow_module_level=True,
    )
pytest.importorskip("playwright")

REPO = Path(__file__).resolve().parents[3]
for _p in (REPO / "apps" / "spaces" / "_shared", REPO / "apps" / "spaces" / "algenta"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import verify_checks as vc  # noqa: E402

SHAPES = {name: (query, full) for name, query, full in vc.PERMALINK_SHAPES}
BROKEN_IN_ROUND_2 = tuple(name for name, _q, full in vc.PERMALINK_SHAPES if not full)
RESTORED_IN_FULL = tuple(name for name, _q, full in vc.PERMALINK_SHAPES if full)


@pytest.fixture(scope="module")
def browser() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        chromium = pw.chromium.launch()
        try:
            yield chromium
        finally:
            chromium.close()


@pytest.fixture(scope="module")
def helpers() -> dict[str, Any]:
    return vc._permalink_helpers()


def _states(browser: Any, query: str) -> list[tuple[str, dict[str, Any]]]:
    """The box and the form after loading `query` in every permalink context."""
    out: list[tuple[str, dict[str, Any]]] = []
    for label, width, height, theme in vc.PERMALINK_CONTEXTS:
        context = browser.new_context(
            viewport={"width": width, "height": height}, color_scheme=theme
        )
        try:
            page = vc._open_link(context, URL.rstrip("/"), query)
            out.append((f"{label}/{theme}", page.evaluate(vc._JS_FORM_STATE)))
        finally:
            context.close()
    return out


@pytest.mark.parametrize("name", BROKEN_IN_ROUND_2)
def test_box_promises_only_what_the_tab_restored(
    browser: Any, helpers: dict[str, Any], name: str
) -> None:
    query, full = SHAPES[name]
    assert not full
    for where, state in _states(browser, query):
        problems = vc.permalink_problems(query, full, state, helpers)
        assert problems == [], (
            f"{name} at {where}: {query} -> box {state.get('box')!r}, tab {state.get('selected')!r},"
            f" form {state}: {problems}"
        )
        assert state["box"], f"{name} at {where}: the box is empty"
        tab, _fn, _args = vc._parse_link(state["box"])
        assert tab == state["selected"], f"{name} at {where}: the box names another tab"


@pytest.mark.parametrize("name", RESTORED_IN_FULL)
def test_full_links_are_restored_and_kept(browser: Any, helpers: dict[str, Any], name: str) -> None:
    query, full = SHAPES[name]
    assert full
    for where, state in _states(browser, query):
        problems = vc.permalink_problems(query, full, state, helpers)
        assert problems == [], f"{name} at {where}: box {state.get('box')!r}: {problems}"
