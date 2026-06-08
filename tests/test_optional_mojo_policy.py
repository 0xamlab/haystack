from __future__ import annotations

import pytest

from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.services import optional_mojo_policy


def test_clear_optional_mojo_engine_failure_preserves_global_circuit_state() -> None:
    failure_state: dict[str, tuple[float, str]] = {}

    optional_mojo_policy.record_optional_mojo_engine_failure(
        failure_state=failure_state,
        engine_type="field_map",
        reason=MojoEngineError(
            "Worker 2 became unhealthy during engine execution.",
            code="worker_unhealthy",
            recoverable=True,
            engine_type="field_map",
            stage="pool_dispatch",
        ),
        monotonic_fn=lambda: 10.0,
    )
    optional_mojo_policy.clear_optional_mojo_engine_failure(
        failure_state=failure_state,
        engine_type="field_map",
    )

    assert "field_map" not in failure_state
    assert optional_mojo_policy.GLOBAL_OPTIONAL_MOJO_ENGINE_KEY in failure_state


@pytest.mark.anyio
async def test_invoke_optional_mojo_engine_reports_global_circuit_scope() -> None:
    failure_state = {
        optional_mojo_policy.GLOBAL_OPTIONAL_MOJO_ENGINE_KEY: (
            10.0,
            "engine_crash: Mojo engine exited with code -5",
        )
    }

    async def _should_not_run(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("optional Mojo engine should not run while circuit is open")

    result, engine_status = await optional_mojo_policy.invoke_optional_mojo_engine(
        engine_type="join_detect",
        payload={"engine_type": "join_detect"},
        preflight_reason=None,
        timeout_s=2.0,
        max_payload_bytes=1024,
        cooldown_s=60.0,
        failure_state=failure_state,
        monotonic_fn=lambda: 20.0,
        invoke_engine=_should_not_run,
    )

    assert result is None
    assert engine_status["reason"] == "engine_circuit_open"
    assert engine_status["details"]["circuit_scope"] == "global"
    assert engine_status["details"]["cooldown_s"] == 60.0


@pytest.mark.anyio
async def test_invoke_optional_mojo_engine_reports_engine_scope_for_recoverable_error() -> None:
    failure_state: dict[str, tuple[float, str]] = {}

    async def _raise_timeout(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise MojoEngineError(
            "Mojo engine timed out after 2.0s.",
            code="timeout",
            recoverable=True,
            engine_type="field_map",
            stage="optional_exec",
        )

    result, engine_status = await optional_mojo_policy.invoke_optional_mojo_engine(
        engine_type="field_map",
        payload={"engine_type": "field_map", "data": {"revenue": [10.0, 12.0]}},
        preflight_reason=None,
        timeout_s=2.0,
        max_payload_bytes=1024,
        cooldown_s=60.0,
        failure_state=failure_state,
        monotonic_fn=lambda: 10.0,
        invoke_engine=_raise_timeout,
    )

    assert result is None
    assert engine_status["reason"] == "timeout"
    assert engine_status["details"]["circuit_scope"] == "engine"
    assert engine_status["details"]["cooldown_s"] == 60.0
    assert failure_state["field_map"][1].startswith("timeout:")
