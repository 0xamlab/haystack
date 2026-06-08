from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _cleanup_module():
    return importlib.import_module("algenta.runtime_connector_preview_cleanup")


def _errors_module():
    return importlib.import_module("algenta.runtime_connector_preview_errors")


def _runtime_errors_module():
    return importlib.import_module("algenta.runtime_errors")


class _PreviewUnavailableError(Exception):
    status_code = 404


class _InlinePreviewRateLimitError(Exception):
    error_code = "inline_preview_rate_limited"
    details = {"limit": 20}


def test_cleanup_inline_preview_connectors_deletes_forced_and_expired_entries() -> None:
    cleanup_connectors = _cleanup_module().cleanup_inline_preview_connectors
    pending_cleanup = {
        "future": 200.0,
        "expired": 90.0,
        "forced": 200.0,
    }
    deleted_ids: list[str] = []

    class _FakeClient:
        def delete_connector(self, connector_id: str) -> None:
            deleted_ids.append(connector_id)

    cleanup_connectors(
        pending_cleanup,
        uses_api_transport=True,
        client=_FakeClient(),
        force_ids={"forced"},
        now_epoch=lambda: 100.0,
    )

    assert deleted_ids == ["expired", "forced"]
    assert pending_cleanup == {"future": 200.0}


def test_run_with_inline_preview_connector_cleans_up_temporary_connector() -> None:
    run_with_inline_preview_connector = _cleanup_module().run_with_inline_preview_connector
    pending_cleanup: dict[str, float] = {}
    seen_callbacks: list[str] = []
    seen_force_ids: list[set[str] | None] = []
    rate_limit_calls: list[str] = []

    def _cleanup_connectors(*, force_ids: set[str] | None = None) -> None:
        seen_force_ids.append(force_ids)
        if force_ids:
            for connector_id in force_ids:
                pending_cleanup.pop(connector_id, None)

    result = run_with_inline_preview_connector(
        connector_type="redis",
        config={"url": "redis://localhost:6379"},
        operation="browse",
        pending_cleanup=pending_cleanup,
        create_connector=lambda **kwargs: SimpleNamespace(id="preview_123", kwargs=kwargs),
        cleanup_connectors=_cleanup_connectors,
        remember_inline_preview=lambda connector_id, expires_at_epoch: pending_cleanup.__setitem__(
            connector_id, expires_at_epoch
        ),
        callback=lambda connector_id: seen_callbacks.append(connector_id) or {"status": "ok"},
        inline_preview_description=lambda connector_type, description: (
            f"{connector_type}:{description}",
            200.0,
        ),
        consume_inline_preview_slot=lambda: rate_limit_calls.append("slot"),
        enforce_rate_limit=True,
        now_epoch=lambda: 100.0,
    )

    assert result == {"status": "ok"}
    assert seen_callbacks == ["preview_123"]
    assert rate_limit_calls == ["slot"]
    assert seen_force_ids == [None, {"preview_123"}]
    assert pending_cleanup == {}


def test_run_with_inline_preview_connector_raises_when_cleanup_fails() -> None:
    run_with_inline_preview_connector = _cleanup_module().run_with_inline_preview_connector
    runtime_validation_error = _runtime_errors_module().RuntimeValidationError
    pending_cleanup: dict[str, float] = {}

    with pytest.raises(runtime_validation_error) as exc_info:
        run_with_inline_preview_connector(
            connector_type="redis",
            config={"url": "redis://localhost:6379"},
            operation="test",
            pending_cleanup=pending_cleanup,
            create_connector=lambda **kwargs: SimpleNamespace(id="preview_456", kwargs=kwargs),
            cleanup_connectors=lambda *, force_ids=None: None,
            remember_inline_preview=lambda connector_id, expires_at_epoch: (
                pending_cleanup.__setitem__(connector_id, expires_at_epoch)
            ),
            callback=lambda connector_id: {"connector_id": connector_id},
            inline_preview_description=lambda connector_type, description: (
                f"{connector_type}:{description}",
                200.0,
            ),
            now_epoch=lambda: 100.0,
        )

    assert exc_info.value.code == "inline_preview_cleanup_failed"
    assert exc_info.value.details == {"connector_id": "preview_456"}


def test_inline_preview_error_helpers_map_structured_runtime_validation_errors() -> None:
    errors = _errors_module()
    runtime_validation_error = _runtime_errors_module().RuntimeValidationError

    exc = _InlinePreviewRateLimitError("Slow down")

    assert errors.inline_preview_error_code(exc) == "inline_preview_rate_limited"
    assert errors.inline_preview_error_details(exc) == {"limit": 20}

    with pytest.raises(runtime_validation_error) as exc_info:
        errors.raise_inline_preview_error(exc)

    assert exc_info.value.code == "inline_preview_rate_limited"
    assert exc_info.value.details == {"limit": 20}


def test_inline_preview_error_helpers_preserve_non_retryable_errors() -> None:
    errors = _errors_module()
    exc = _PreviewUnavailableError("Not found")

    assert errors.should_fallback_to_ephemeral_preview(exc) is True

    with pytest.raises(_PreviewUnavailableError):
        errors.raise_inline_preview_error(exc)
