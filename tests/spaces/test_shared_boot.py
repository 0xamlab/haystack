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
