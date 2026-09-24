"""The pure half of `apps/spaces/tools/requalify.py`: how a press is judged and how the
qualification document is written (the file the Races tab prints its rule and date from)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "apps" / "spaces" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import requalify  # noqa: E402

BOARD = (
    '<table><thead><tr><th>x</th></tr></thead><tbody><tr><td data-label="algenta" class="n">'
    '2.65 ms</td><td data-label="incumbent">171 ms</td></tr><tr><td data-label="algenta">'
    '9.1 µs</td><td data-label="incumbent">4.4 µs</td></tr></tbody></table>'
)
RECORDED_CARD = '<article class="alg-card alg-card-result"><h3>Levenshtein</h3>2.65 ms</article>'
NOISY_CARD = '<article class="alg-card"><span>noisy — not recorded</span></article>'


def test_lane_ms_reads_the_newest_row_in_ms():
    row = requalify.newest_row(BOARD)
    assert requalify.lane_ms(row, "algenta") == 2.65
    assert requalify.lane_ms(row, "incumbent") == 171.0
    assert requalify.lane_ms('<td data-label="algenta">4.37 µs<', "algenta") == pytest.approx(
        4.37e-3
    )
    assert requalify.lane_ms('<td data-label="algenta">1,234 ms<', "algenta") == 1234.0
    assert requalify.lane_ms("<td>nothing</td>", "algenta") is None
    assert requalify.newest_row("<div>no table</div>") == ""


def test_cell_wins_needs_a_recorded_card_and_a_faster_kernel():
    win = requalify.cell_wins(RECORDED_CARD, BOARD)
    assert win == {"recorded": True, "algenta_ms": 2.65, "incumbent_ms": 171.0, "win": True}
    assert requalify.cell_wins(NOISY_CARD, BOARD)["win"] is False
    assert requalify.cell_wins(NOISY_CARD, BOARD)["recorded"] is False
    slower = BOARD.replace("2.65 ms", "200 ms")
    assert requalify.cell_wins(RECORDED_CARD, slower)["win"] is False
    assert requalify.cell_wins(RECORDED_CARD, "<table></table>")["win"] is False


def test_qualified_document_states_its_rule_stamp_and_only_three_of_three_wins():
    run = {"recorded": True, "algenta_ms": 1.0, "incumbent_ms": 2.0, "win": True}
    loss = {**run, "win": False}
    results = {
        ("levenshtein", "S"): [{"run": i, **run} for i in (1, 2, 3)],
        ("levenshtein", "M"): [{"run": 1, **run}, {"run": 2, **loss}, {"run": 3, **run}],
        ("dijkstra", "S"): [{"run": i, **loss} for i in (1, 2, 3)],
        ("greeks", "L"): [{"run": 1, **run}, {"run": 2, **run}],  # one run short
        # a noisy press between two wins does not count; three recorded wins qualify
        ("betweenness", "S"): [
            {"run": 1, **run},
            {"run": 2, **run, "recorded": False, "win": False},
            {"run": 3, **run},
            {"run": 4, **run},
        ],
        # a recorded loss disqualifies whatever else was recorded
        ("closeness", "M"): [
            {"run": 1, **run},
            {"run": 2, **loss},
            {"run": 3, **run},
            {"run": 4, **run},
        ],
    }
    doc = requalify.qualified_document(
        results,
        hardware_id="322b47fd6435",
        hardware="AMD EPYC 7R13 · 8 vCPU",
        space_id="thyn-ai/algenta",
        rulebook="0.6",
        runs=3,
        now=datetime(2026, 9, 23, 16, 27, tzinfo=UTC),
    )
    assert doc["qualified"] == [
        {"race_id": "levenshtein", "size": "S"},
        {"race_id": "betweenness", "size": "S"},
    ]
    assert requalify.cell_qualifies([run, run, run], 3) and not requalify.cell_qualifies(
        [run, run], 3
    )
    assert not requalify.cell_qualifies([run, loss, run, run], 3)
    assert doc["hardware_id"] == "322b47fd6435" and doc["space_id"] == "thyn-ai/algenta"
    assert doc["generated_utc"] == "2026-09-23 16:27 UTC"
    assert doc["rule"] == (
        "a cell qualifies when 3 recorded runs on this hardware (within 5 presses; a noisy press"
        " is not a run) each saw the kernel's median beat the incumbent's (rulebook v0.6)"
    )
    assert "apps/spaces/tools/requalify.py" in doc["note"], (
        "the file names the script that wrote it"
    )
    assert set(doc["runs"]) == {
        "levenshtein/S",
        "levenshtein/M",
        "dijkstra/S",
        "greeks/L",
        "betweenness/S",
        "closeness/M",
    }
    assert requalify.ATTEMPTS_DEFAULT == 5
    assert requalify.SIZES == ("S", "M", "L") and requalify.RUNS_DEFAULT == 3


def test_main_refuses_a_plain_http_url_and_a_missing_token(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="https"):
        requalify.main(["http://example.test", "thyn-ai/algenta"])
    with pytest.raises(SystemExit, match="HF_TOKEN"):
        requalify.main(["https://example.test", "thyn-ai/algenta"])
