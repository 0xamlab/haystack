from __future__ import annotations

import importlib
import sys

import pytest


def _reload_trusted_time_module():
    module_name = "apps.runtime.trusted_time"
    if module_name in sys.modules:
        return importlib.reload(sys.modules[module_name])
    return importlib.import_module(module_name)


def test_trusted_now_uses_monotonic_elapsed_when_wall_clock_stalls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    trusted_time = _reload_trusted_time_module()

    wall_now = 1_800_000_000.0
    monotonic_now = 10.0
    monkeypatch.setattr(trusted_time.time, "time", lambda: wall_now)
    monkeypatch.setattr(trusted_time.time, "monotonic", lambda: monotonic_now)

    assert trusted_time.observe_time(wall_now, source="control-plane-register") == pytest.approx(
        wall_now
    )

    monotonic_now = 85.0
    trusted_epoch = trusted_time.trusted_now_epoch()
    assert trusted_epoch == pytest.approx(wall_now + 75.0)

    state = trusted_time._read_state()
    assert state is not None
    assert state.trusted_epoch == pytest.approx(wall_now + 75.0)
    assert state.source == "local"


def test_trusted_now_never_moves_backward_when_wall_clock_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    trusted_time = _reload_trusted_time_module()

    wall_now = 1_900_000_000.0
    monotonic_now = 10.0
    monkeypatch.setattr(trusted_time.time, "time", lambda: wall_now)
    monkeypatch.setattr(trusted_time.time, "monotonic", lambda: monotonic_now)

    floor = wall_now + 300.0
    trusted_time.observe_time(floor, source="control-plane-register")

    wall_now -= 86_400.0
    assert trusted_time.trusted_now_epoch() == pytest.approx(floor)
