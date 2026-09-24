"""Qualify the Races on one Space's hardware, by the rulebook, and publish ``qualified.json``.

Every candidate the Space offers is run through its ``/race_run`` endpoint until three runs were
recorded (a run the rulebook refuses as noisy does not count, and at most five attempts are
made). A (race, size) cell qualifies when three recorded runs exist and the kernel's median beat
the incumbent's in every one of them; a single recorded loss disqualifies the cell. The
document is stamped with the Space's ``hardware_id`` (from
``/health``), carries the rule it applied and the time it was written, and is uploaded as
``qualified.json`` to the results Dataset; the Space is then restarted so it reads the file at
boot. Empty means every cell renders as a parity panel, never a race.

    HF_TOKEN=… python apps/spaces/tools/requalify.py <space-url> <space-repo> [--dry-run]
        [--dataset thyn-ai/algenta-arena-results] [--runs 3] [--attempts 5] [--pause 5]

The token is read from ``HF_TOKEN`` (never from a file); ``--dry-run`` prints the document and
uploads nothing. Pure helpers (``lane_ms``, ``cell_wins``, ``qualified_document``) are unit-tested.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATASET_DEFAULT = "thyn-ai/algenta-arena-results"
SIZES: tuple[str, ...] = ("S", "M", "L")
RUNS_DEFAULT = 3
#: How many presses a cell may take to collect its recorded runs (a shared host is noisy).
ATTEMPTS_DEFAULT = 5
PAUSE_DEFAULT_S = 5.0
UNIT_MS = {"µs": 1e-3, "ms": 1.0, "s": 1e3}
NOT_RECORDED_WORDS = ("not recorded", "not measurable", "unavailable")
TAG_RE = re.compile(r"<[^>]+>")
#: What the document says about itself; the tab prints ``rule`` and ``generated_utc`` verbatim.
RULE_TEXT = (
    "a cell qualifies when {runs} recorded runs on this hardware (within {attempts} presses;"
    " a noisy press is not a run) each saw the kernel's median beat the incumbent's"
    " (rulebook v{rulebook})"
)
NOTE_TEXT = (
    "Empty means every duel renders as a parity panel (not a race). Written by"
    " apps/spaces/tools/requalify.py against the Space named above."
)


def lane_ms(board_html: str, label: str) -> float | None:
    """The newest board row's time for `label` (``algenta`` or ``incumbent``), in ms."""
    m = re.search(rf'data-label="{label}"[^>]*>([\d.,]+)\s*(µs|ms|s)<', board_html)
    if m is None:
        return None
    return float(m.group(1).replace(",", "")) * UNIT_MS[m.group(2)]


def newest_row(board_html: str) -> str:
    """The first ``<tr>`` of the board's body — the row the press just appended."""
    body = board_html.split("<tbody", 1)[1] if "<tbody" in board_html else ""
    return body.split("</tr>", 1)[0]


def cell_wins(card_html: str, board_html: str) -> dict[str, Any]:
    """One run's verdict: recorded, both medians, and whether the kernel won."""
    text = TAG_RE.sub(" ", card_html)
    recorded = not any(word in text for word in NOT_RECORDED_WORDS)
    row = newest_row(board_html)
    ours, theirs = lane_ms(row, "algenta"), lane_ms(row, "incumbent")
    win = bool(recorded and ours is not None and theirs is not None and ours < theirs)
    return {"recorded": recorded, "algenta_ms": ours, "incumbent_ms": theirs, "win": win}


def cell_qualifies(attempts: list[dict[str, Any]], runs: int) -> bool:
    """Three recorded presses, every one a kernel win; a noisy press is neither."""
    recorded = [a for a in attempts if a.get("recorded")]
    return len(recorded) >= runs and all(a["win"] for a in recorded)


def qualified_document(
    results: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    hardware_id: str,
    hardware: str,
    space_id: str | None,
    rulebook: str,
    runs: int,
    attempts: int = ATTEMPTS_DEFAULT,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The ``qualified.json`` document for `results` (cell -> its presses)."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    qualified = [
        {"race_id": race, "size": size}
        for (race, size), presses in results.items()
        if cell_qualifies(presses, runs)
    ]
    return {
        "hardware_id": hardware_id,
        "hardware": hardware,
        "space_id": space_id,
        "generated_utc": stamp,
        "rule": RULE_TEXT.format(runs=runs, attempts=attempts, rulebook=rulebook),
        "qualified": qualified,
        "runs": {f"{race}/{size}": wins for (race, size), wins in results.items()},
        "note": NOTE_TEXT,
    }


def _get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - https Space URL
        return json.load(response)


def _candidates(config: dict[str, Any]) -> list[str]:
    for component in config.get("components", []):
        props = component.get("props", {})
        if component.get("type") == "dropdown" and props.get("label") == "Race":
            return [value for _, value in props.get("choices", [])]
    raise SystemExit("the Space's /config has no Race dropdown")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url", help="the Space URL, e.g. https://thyn-ai-algenta.hf.space")
    ap.add_argument("repo", help="the Space repo id to restart, e.g. thyn-ai/algenta")
    ap.add_argument("--dataset", default=DATASET_DEFAULT)
    ap.add_argument("--runs", type=int, default=RUNS_DEFAULT, help="recorded runs a cell needs")
    ap.add_argument(
        "--attempts", type=int, default=ATTEMPTS_DEFAULT, help="presses allowed per cell"
    )
    ap.add_argument("--pause", type=float, default=PAUSE_DEFAULT_S, help="seconds between runs")
    ap.add_argument("--dry-run", action="store_true", help="print the document, upload nothing")
    a = ap.parse_args(argv)
    url = a.url.rstrip("/")
    if not url.startswith("https://"):
        raise SystemExit("the Space URL must be https")
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token and not a.dry_run:
        raise SystemExit("set HF_TOKEN (a write token for the Dataset and the Space)")

    from gradio_client import Client
    from huggingface_hub import HfApi

    health = _get_json(f"{url}/health")
    facts = health.get("facts") or {}
    hardware_id = str(facts.get("hardware_id") or "")
    hardware = str(facts.get("hardware") or health.get("hardware") or "")
    if not hardware_id:
        raise SystemExit("/health carries no facts.hardware_id")
    candidates = _candidates(_get_json(f"{url}/config"))
    print(f"hardware_id {hardware_id} | {hardware[:80]} | candidates {candidates}")

    client = Client(url, verbose=False)
    results: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for race in candidates:
        for size in SIZES:
            presses: list[dict[str, Any]] = []
            for press in range(a.attempts):
                card, board = client.predict(race, size, api_name="/race_run")[:2]
                verdict = cell_wins(str(card), str(board))
                presses.append({"run": press + 1, **verdict})
                state = "RECORDED" if verdict["recorded"] else "not recorded"
                print(
                    f"  {race:14s} {size} press {press + 1}: {state}"
                    f" algenta={verdict['algenta_ms']}"
                    f" incumbent={verdict['incumbent_ms']} {'WIN' if verdict['win'] else '-'}"
                )
                time.sleep(a.pause)
                recorded = [x for x in presses if x["recorded"]]
                if len(recorded) >= a.runs or any(not x["win"] for x in recorded):
                    break  # three recorded runs, or a recorded loss that no further press undoes
            results[(race, size)] = presses
    doc = qualified_document(
        results,
        hardware_id=hardware_id,
        hardware=hardware,
        space_id=health.get("space_id"),
        rulebook=str(facts.get("rulebook") or "?"),
        runs=a.runs,
        attempts=a.attempts,
    )
    print(f"qualified: {[(q['race_id'], q['size']) for q in doc['qualified']]}")
    if a.dry_run:
        print(json.dumps(doc, indent=1, ensure_ascii=False)[:2000])
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "qualified.json"
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        api = HfApi(token=token)
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo="qualified.json",
            repo_id=a.dataset,
            repo_type="dataset",
            commit_message=(
                f"qualified.json for {health.get('space_id')} ({hardware_id}):"
                f" {len(doc['qualified'])} cells"
            ),
        )
    print("uploaded qualified.json to", a.dataset)
    api.restart_space(a.repo)
    print("restart requested for", a.repo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
