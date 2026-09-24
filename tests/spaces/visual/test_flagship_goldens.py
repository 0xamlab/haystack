"""Golden-screenshot gate for the flagship — fresh Chromium shots against tests/spaces/golden.

Run against an app launched for real, in the state the goldens record::

    SPACE_ID=thyn-ai/algenta SPACE_HOST=thyn-ai-algenta.hf.space … python app.py   # network on
    ALGENTA_FLAGSHIP_URL=http://127.0.0.1:7860 <venv>/bin/python -m pytest \
        --confcutdir=tests/spaces tests/spaces/visual -m slow -q

Every tab x {1440x900, 1024x768, 375x812} x {light, dark} is captured once per session (each
page in two agreeing loads, `_goldens._capture_agreed`), then each golden is compared with the
strict diff from `_goldens.py`: one unmasked pixel that no pixel of the golden within 1 px
matches, or a size change, fails and the difference mask is written next to the fresh shot
(`ALGENTA_GOLDEN_WORK`, default a pytest tmp dir). A pixel difference must reproduce on a second
agreed capture of that page before it fails the gate (round 4: a renderer now and then rasterises
a whole load's text in another anti-aliasing; a real drift differs on every load).

The state rule comes first: the manifest records the state the goldens picture (`state`:
`hero_status`, `hub_state`, `space_id`) and the live app's is read from `/health` and
`/config`. When they differ — or the manifest records none — nothing is compared: the state test
and every diff skip loudly with the reason, because six Ecosystem size failures against a
local app that never fetched the Hub would name the runner's state, not a defect.

Regenerate intentionally, in the same PR as the change that moved pixels, in the deployed
state (the one command is `_goldens.REGENERATE_COMMAND`)::

    <venv>/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:7860 --regenerate
"""

from __future__ import annotations

import os
from pathlib import Path

import _goldens as goldens
import pytest

pytestmark = [pytest.mark.slow]

URL = os.environ.get("ALGENTA_FLAGSHIP_URL", "").strip()
if not URL:
    pytest.skip(
        "set ALGENTA_FLAGSHIP_URL to a running flagship (scripts/spaces-flagship-run.sh)",
        allow_module_level=True,
    )
pytest.importorskip("playwright")
pytest.importorskip("PIL")

MANIFEST_PROBLEMS = goldens._check_manifest()
ENTRIES = [] if MANIFEST_PROBLEMS else goldens._read_manifest()


@pytest.fixture(scope="session")
def work_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    override = os.environ.get("ALGENTA_GOLDEN_WORK", "").strip()
    return Path(override) if override else tmp_path_factory.mktemp("golden")


@pytest.fixture(scope="session")
def live_state() -> dict[str, str]:
    state = goldens._deploy_state(URL)
    assert state["hero_status"] != "unknown", f"{URL}/health did not report the hero state"
    return state


@pytest.fixture(scope="session")
def state_gate(live_state: dict[str, str]) -> dict[str, str]:
    """The comparison runs only in the goldens' own state; otherwise every dependent skips
    with the reason — a refusal, never six Ecosystem size diffs."""
    mismatch = goldens._state_mismatch(goldens._manifest_state(), live_state)
    if mismatch is not None:
        pytest.skip(mismatch)
    return live_state


@pytest.fixture(scope="session")
def fresh_dir(work_dir: Path, state_gate: dict[str, str]) -> Path:
    out = work_dir / "fresh"
    goldens._capture_all(URL, out, expect_hub_state=state_gate["hub_state"])
    return out


def test_goldens_committed_and_consistent() -> None:
    assert not MANIFEST_PROBLEMS, "\n".join(MANIFEST_PROBLEMS) + (
        "\n-> <venv>/bin/python tests/spaces/visual/_goldens.py --url <app> --regenerate"
    )
    assert len(ENTRIES) == len(goldens._shots()), "one golden per tab x viewport x theme"


def test_goldens_picture_the_state_the_app_serves(live_state: dict[str, str]) -> None:
    """The manifest's state (opening card, Ecosystem Hub state, Space) equals the live app's;
    a manifest that records no state, or another one, is a loud skip — the goldens are
    regenerated in the deployed state, never compared across states."""
    recorded = goldens._manifest_state()
    mismatch = goldens._state_mismatch(recorded, live_state)
    if mismatch is not None:
        pytest.skip(mismatch)
    assert recorded == live_state


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: Path(e.file).stem)
def test_golden_matches(
    entry: goldens.Entry, fresh_dir: Path, work_dir: Path, state_gate: dict[str, str]
) -> None:
    """A pixel difference must reproduce: the page is captured once more (two agreeing loads)
    and the second reading decides — a real drift differs on every load, the renderer's
    anti-aliasing state (`_goldens.LOADS_TO_AGREE`) does not survive a second agreed capture."""
    fresh = fresh_dir / entry.file
    assert fresh.is_file(), f"no fresh shot for {entry.file}"
    diff_out = work_dir / "diff" / f"{Path(entry.file).stem}.diff.png"
    diff = goldens._compare(goldens.GOLDEN_DIR / entry.file, fresh, diff_out)
    first = diff.describe()
    if not diff.ok and diff.size_match:
        shot = goldens._shot_of(entry.file)
        assert shot is not None, f"{entry.file}: no tab x viewport x theme for this golden"
        retry = work_dir / "retry"
        second = goldens._recapture(URL, shot, retry, state_gate["hub_state"])
        diff = goldens._compare(goldens.GOLDEN_DIR / entry.file, retry / second.file, diff_out)
        print(
            f"{entry.file}: {first} on the first capture;"
            f" {'reproduced' if not diff.ok else 'did not reproduce'} on a second agreed capture"
            f" ({diff.describe()})"
        )
    assert diff.ok, (
        f"{entry.file}: {diff.describe()} (first capture: {first});"
        f" mask at {diff_out}; regenerate with _goldens.py --regenerate if intended"
    )
