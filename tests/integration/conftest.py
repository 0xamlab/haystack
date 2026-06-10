"""Integration-test env gating.

Several live integration tests require infrastructure that may be absent in a bare
dev/CI environment — a repository planner model / simulation capacity, or a compiled
Mojo worker pool on the API server. The suite already signals "blocked infra" two
ways: by raising ``EnvironmentBlockedError`` (test_openapi) and by surfacing the
server's ``compute_runtime_unavailable`` error. Convert both to a pytest *skip* (not
a failure) at the call phase, so a run without that live infra is green while the
same tests still execute fully in CI where the infra is present.
"""
from __future__ import annotations

import pytest

_BLOCKED_INFRA_MARKERS = ("compute_runtime_unavailable",)


def _is_blocked_infra(exc: BaseException) -> bool:
    if type(exc).__name__ == "EnvironmentBlockedError":
        return True
    message = str(exc)
    return any(marker in message for marker in _BLOCKED_INFRA_MARKERS)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):  # noqa: ANN001, ANN201
    outcome = yield
    try:
        outcome.get_result()
    except BaseException as exc:  # noqa: BLE001 — inspect, only convert blocked-infra
        if _is_blocked_infra(exc):
            outcome.force_exception(pytest.skip.Exception(str(exc)))
        # otherwise leave the original result/exception untouched (real failure)
