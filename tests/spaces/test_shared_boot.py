"""algenta_spaces.boot — staged boot registry, HTML card, JSON snapshot."""

from __future__ import annotations

import json
import threading

import pytest
from _rules import (
    _assert_clean_copy,
    _assert_four_class_selectors,
    _assert_stylesheet_discipline,
)
from algenta_spaces import boot

STAGES = [
    ("kernels", "Warming the Hub kernels"),
    ("model", "Preparing the model checkpoint"),
    ("probe", "Checking the hosted API"),
]


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_registry_transitions_with_timestamps():
    clock = Clock()
    reg = boot.BootRegistry(STAGES, clock=clock)
    snap = reg.snapshot()
    assert snap["ready"] is False and snap["error"] is None
    assert [s["state"] for s in snap["stages"]] == ["pending"] * 3
    assert snap["elapsed_s"] == 0.0

    clock.now = 101.0
    reg.start("kernels")
    clock.now = 103.5
    snap = reg.snapshot()
    kernels = snap["stages"][0]
    assert kernels["state"] == "running" and kernels["started_at"] == 101.0
    assert kernels["elapsed_s"] == 2.5 and kernels["finished_at"] is None

    reg.done("kernels", "20 families warm in 2.5 s")
    reg.start("model")
    clock.now = 110.0
    reg.done("model")
    reg.fail("probe", "401 from api.algenta.ai")
    snap = reg.snapshot()
    assert snap["ready"] is False
    assert snap["error"] == "401 from api.algenta.ai"
    assert reg.error == "401 from api.algenta.ai"
    assert snap["stages"][0]["finished_at"] == 103.5
    assert snap["stages"][0]["elapsed_s"] == 2.5
    assert snap["stages"][1]["elapsed_s"] == 6.5
    assert snap["stages"][2]["state"] == "error"
    assert snap["elapsed_s"] == 10.0

    reg.set("probe", boot.PENDING)
    reg.done("probe")
    assert reg.ready is True and reg.error is None


def test_elapsed_is_the_boot_duration_and_uptime_is_separate():
    """`/health` said `ready, 6 stages in 676 s` an hour in: `elapsed_s` was now minus start.
    The boot ends when the last stage finishes; after that `elapsed_s` stands still and
    `uptime_s` keeps counting."""
    clock = Clock()  # 100.0 = 1970-01-01 00:01:40 UTC
    reg = boot.BootRegistry(STAGES, clock=clock)
    assert reg.boot_finished_at is None
    clock.now = 101.0
    reg.start("kernels")
    clock.now = 103.5
    snap = reg.snapshot()
    assert snap["elapsed_s"] == snap["uptime_s"] == 3.5, "while a stage is open, both run"
    assert snap["boot_started_utc"] == "1970-01-01 00:01 UTC"
    assert snap["boot_finished_utc"] is None
    reg.done("kernels", "20 families warm in 2.5 s")
    reg.start("model")
    clock.now = 104.1
    reg.done("model")
    reg.start("probe")
    clock.now = 104.9
    reg.done("probe", "not configured")
    assert reg.boot_finished_at == 104.9
    clock.now = 3704.9  # an hour later
    snap = reg.snapshot()
    assert snap["ready"] is True
    assert snap["elapsed_s"] == 4.9, "the boot took 4.9 s, whatever the uptime"
    assert snap["uptime_s"] == 3604.9
    assert snap["boot_finished_utc"] == "1970-01-01 00:01 UTC"
    html = reg.render_html()
    assert (
        '<p class="alg-boot-foot">booted in 4.9 s · finished '
        '<time class="alg-time" datetime="1970-01-01T00:01Z">1970-01-01 00:01 UTC</time></p>'
    ) in html, "the finish is a <time> element, machine-readable as well as read"
    assert ".alg-boot-foot" * 4 in boot.BOOT_CSS
    _assert_clean_copy(html)
    # a stage reopened after boot clears the finish until every stage has finished again
    reg.start("probe")
    assert reg.boot_finished_at is None
    snap = reg.snapshot()
    assert snap["boot_finished_utc"] is None and snap["elapsed_s"] == snap["uptime_s"]
    assert "alg-boot-foot" not in reg.render_html()
    clock.now = 3710.0
    reg.done("probe")
    assert reg.boot_finished_at == 3710.0 and reg.snapshot()["elapsed_s"] == 3610.0
    # a failed last stage finishes the boot too: /health tells the truth with a duration
    failing = boot.BootRegistry(STAGES, clock=clock)
    for stage_id, _ in STAGES[:-1]:
        failing.done(stage_id)
    clock.now = 3712.0
    failing.fail("probe", "401")
    assert failing.boot_finished_at == 3712.0 and failing.snapshot()["elapsed_s"] == 2.0
    assert json.loads(failing.to_json())["boot_finished_utc"] == "1970-01-01 01:01 UTC"


def test_progress_events_keep_the_first_start_so_stage_times_add_up_to_the_boot():
    """Round 2: the kernels row read `0.0 s` beside `warm in 1.7 s` because every progress event
    (`set(stage, RUNNING, "family: event · detail")`) reset `started_at`; the stage sum was
    2.0 s against `booted in 3.7 s`. The first `running` starts the clock; progress keeps it."""
    clock = Clock()
    reg = boot.BootRegistry(STAGES, clock=clock)
    clock.now = 101.0
    reg.start("kernels")
    for offset, family in ((0.4, "stats"), (0.9, "text"), (1.5, "graph")):
        clock.now = 101.0 + offset
        reg.set("kernels", boot.RUNNING, f"{family}: warm · 0.3 ms")
    snap = reg.snapshot()
    kernels = snap["stages"][0]
    assert kernels["started_at"] == 101.0, "a progress event never restarts the clock"
    assert kernels["detail"] == "graph: warm · 0.3 ms", "but it does update the detail"
    assert kernels["elapsed_s"] == 1.5
    clock.now = 103.0
    reg.done("kernels", "3 families warm in 2.0 s")
    reg.start("model")
    clock.now = 104.0
    reg.done("model")
    reg.start("probe")
    clock.now = 104.5
    reg.done("probe", "not configured")
    snap = reg.snapshot()
    elapsed = [s["elapsed_s"] for s in snap["stages"]]
    assert elapsed == [2.0, 1.0, 0.5], "each stage's real duration"
    assert snap["stages_s"] == 3.5, "the stages' durations, added up"
    assert snap["elapsed_s"] == 4.5, "the boot: registry creation (100.0) to the last finish"
    assert snap["elapsed_s"] - snap["stages_s"] == pytest.approx(1.0), "only the gap before start"
    assert "2.0 s</span>" in reg.render_html(), "the card prints the stage's duration"
    # a stage that finished and runs again starts a new clock (a re-measure, not a progress event)
    clock.now = 200.0
    reg.start("probe")
    assert reg.snapshot()["stages"][2]["started_at"] == 200.0
    # ... and so does one that was set back to pending first
    reg.set("model", boot.PENDING)
    clock.now = 201.0
    reg.set("model", boot.RUNNING, "again")
    assert reg.snapshot()["stages"][1]["started_at"] == 201.0
    assert boot.to_json(reg.snapshot()).count('"stages_s"') == 1


def test_registry_validation():
    with pytest.raises(ValueError):
        boot.BootRegistry([])
    with pytest.raises(ValueError):
        boot.BootRegistry([("a", "x"), ("a", "y")])
    with pytest.raises(ValueError):
        boot.BootRegistry([("a", "Warming kernels!")])
    with pytest.raises(ValueError):
        boot.BootRegistry([("a", " ".join(["word"] * 15))])
    reg = boot.BootRegistry(STAGES)
    with pytest.raises(KeyError):
        reg.start("nope")
    with pytest.raises(ValueError):
        reg.set("kernels", "flying")


def test_registry_is_thread_safe_under_concurrent_updates():
    reg = boot.BootRegistry([(f"s{i}", f"Stage {i}") for i in range(50)])

    def worker(i: int) -> None:
        reg.start(f"s{i}")
        reg.done(f"s{i}", f"finished {i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert reg.ready
    snap = reg.snapshot()
    assert {s["detail"] for s in snap["stages"]} == {f"finished {i}" for i in range(50)}


def test_json_snapshot_round_trips():
    reg = boot.BootRegistry(STAGES, clock=Clock())
    reg.start("kernels")
    data = json.loads(reg.to_json())
    assert data["ready"] is False
    assert data["stages"][0]["id"] == "kernels"
    assert data["stages"][0]["state"] == "running"
    assert boot.to_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_render_boot_html_states_details_and_escaping():
    clock = Clock()
    reg = boot.BootRegistry(STAGES, clock=clock)
    reg.start("kernels")
    clock.now = 101.25
    reg.done("kernels", "20 families in 1.2 s")
    reg.start("model")
    clock.now = 103.0
    reg.fail("probe", "<401> unauthorised")
    html = reg.render_html()
    assert '<h2 class="alg-boot-title">Starting up</h2>' in html
    assert 'data-stage="kernels"' in html
    assert (
        ">ready<" in html and ">running<" in html and ">failed<" in html and ">waiting<" not in html
    )
    assert "20 families in 1.2 s" in html
    assert "1.2 s</span>" in html  # elapsed for a finished stage
    assert "1.8 s</span>" in html  # elapsed for the running stage
    assert "&lt;401&gt; unauthorised" in html and "<401>" not in html
    assert 'class="alg-boot-fail"' in html
    assert 'aria-live="polite"' in html
    _assert_clean_copy(html)


def test_render_boot_html_ready_and_pending_rows():
    reg = boot.BootRegistry(STAGES, clock=Clock())
    html = reg.render_html()
    assert html.count(">waiting<") == 3
    assert 'alg-boot-elapsed"></span>' in html  # no elapsed before a stage starts
    for stage_id, _ in STAGES:
        reg.done(stage_id)
    html = reg.render_html()
    assert '<h2 class="alg-boot-title">Ready</h2>' in html
    assert html.count(">ready<") == 3
    with pytest.raises(ValueError):
        boot.render_boot_html({"stages": [{"id": "x", "label": "y", "state": "odd"}]})


def test_boot_css_discipline():
    _assert_stylesheet_discipline(boot.BOOT_CSS)
    _assert_four_class_selectors(boot.BOOT_CSS)
