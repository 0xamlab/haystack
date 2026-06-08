from __future__ import annotations

from typing import Any

from algenta.runtime_connector_definitions import (
    _inline_preview_cache_key,
)
from algenta.runtime_connector_model_preview import ConnectorBrowseOutput, ConnectorTestOutput
from algenta.runtime_connector_preview_cleanup import (
    cleanup_inline_preview_connectors,
    run_with_inline_preview_connector,
)
from algenta.runtime_connector_preview_errors import (
    inline_preview_error_code,
    inline_preview_error_details,
    raise_inline_preview_error,
    should_fallback_to_ephemeral_preview,
)
from algenta.runtime_connector_preview_state import (
    cleanup_inline_preview_cache,
    cleanup_inline_preview_capabilities,
    consume_inline_preview_slot,
    get_inline_preview_cache,
    get_inline_preview_capability,
    inline_preview_description,
    put_inline_preview_cache,
    put_inline_preview_capability,
)
from algenta.runtime_errors import RuntimeValidationError


class RuntimeInlinePreviewMixin:
    def _consume_inline_preview_slot(self) -> None:
        self._inline_preview_events = consume_inline_preview_slot(self._inline_preview_events)

    def _remember_inline_preview(self, connector_id: str, *, expires_at_epoch: float) -> None:
        self._inline_preview_pending_cleanup[connector_id] = expires_at_epoch

    def _inline_preview_description(
        self,
        *,
        connector_type: str,
        description: str | None,
    ) -> tuple[str, float]:
        return inline_preview_description(
            connector_type=connector_type,
            description=description,
        )

    def _cleanup_inline_preview_cache(self) -> None:
        cleanup_inline_preview_cache(self._inline_preview_cache)

    def _get_inline_preview_cache(self, cache_key: str) -> Any | None:
        return get_inline_preview_cache(self._inline_preview_cache, cache_key)

    def _put_inline_preview_cache(self, cache_key: str, value: Any) -> Any:
        return put_inline_preview_cache(self._inline_preview_cache, cache_key, value)

    def _cleanup_inline_preview_capabilities(self) -> None:
        cleanup_inline_preview_capabilities(self._inline_preview_capabilities)

    def _get_inline_preview_capability(self, *, operation: str) -> bool | None:
        return get_inline_preview_capability(
            self._inline_preview_capabilities,
            operation=operation,
        )

    def _put_inline_preview_capability(self, *, operation: str, supported: bool) -> None:
        put_inline_preview_capability(
            self._inline_preview_capabilities,
            operation=operation,
            supported=supported,
        )

    def _cleanup_inline_preview_connectors(
        self,
        *,
        force_ids: set[str] | None = None,
    ) -> None:
        cleanup_inline_preview_connectors(
            self._inline_preview_pending_cleanup,
            uses_api_transport=self._uses_api_transport(),
            client=self._client() if self._uses_api_transport() else None,
            force_ids=force_ids,
        )

    def _with_inline_preview_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any],
        operation: str,
        callback,
        enforce_rate_limit: bool = True,
    ):
        return run_with_inline_preview_connector(
            connector_type=connector_type,
            config=config,
            operation=operation,
            pending_cleanup=self._inline_preview_pending_cleanup,
            create_connector=self.create_connector,
            cleanup_connectors=self._cleanup_inline_preview_connectors,
            remember_inline_preview=self._remember_inline_preview,
            callback=callback,
            inline_preview_description=lambda inner_connector_type, inner_description: (
                self._inline_preview_description(
                    connector_type=inner_connector_type,
                    description=inner_description,
                )
            ),
            consume_inline_preview_slot=self._consume_inline_preview_slot,
            enforce_rate_limit=enforce_rate_limit,
        )

    @staticmethod
    def _inline_preview_error_code(exc: Exception) -> str | None:
        return inline_preview_error_code(exc)

    @staticmethod
    def _inline_preview_error_details(exc: Exception) -> dict[str, Any]:
        return inline_preview_error_details(exc)

    @staticmethod
    def _should_fallback_to_ephemeral_preview(exc: Exception) -> bool:
        return should_fallback_to_ephemeral_preview(exc)

    def _raise_inline_preview_error(self, exc: Exception) -> None:
        raise_inline_preview_error(exc)

    def _test_inline_preview_via_ephemeral_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any],
    ) -> ConnectorTestOutput:
        return self._with_inline_preview_connector(
            connector_type=connector_type,
            config=config,
            operation="test",
            callback=lambda preview_connector_id: ConnectorTestOutput.from_api(
                self._client().test_connector(preview_connector_id)
            ),
            enforce_rate_limit=False,
        )

    def _browse_inline_preview_via_ephemeral_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any],
    ) -> ConnectorBrowseOutput:
        def _browse_inline(preview_connector_id: str) -> ConnectorBrowseOutput:
            test_result = ConnectorTestOutput.from_api(
                self._client().test_connector(preview_connector_id)
            )
            if not test_result.success:
                raise RuntimeValidationError(
                    "connector_test_failed",
                    test_result.message,
                    test_result.to_dict(),
                )
            return ConnectorBrowseOutput.from_api(
                self._client().browse_connector(preview_connector_id)
            )

        return self._with_inline_preview_connector(
            connector_type=connector_type,
            config=config,
            operation="browse",
            callback=_browse_inline,
            enforce_rate_limit=False,
        )

    def _test_inline_preview(
        self,
        *,
        connector_type: str,
        config: dict[str, Any],
    ) -> ConnectorTestOutput:
        cache_key = _inline_preview_cache_key(
            operation="test",
            connector_type=connector_type,
            config=config,
        )
        cached = self._get_inline_preview_cache(cache_key)
        if isinstance(cached, ConnectorTestOutput):
            return cached
        self._consume_inline_preview_slot()
        capability = self._get_inline_preview_capability(operation="test")
        if capability is False:
            result = self._test_inline_preview_via_ephemeral_connector(
                connector_type=connector_type,
                config=config,
            )
            return self._put_inline_preview_cache(cache_key, result)
        try:
            result = ConnectorTestOutput.from_api(
                self._client().preview_test_connector(
                    connector_type=connector_type,
                    config=config,
                )
            )
            self._put_inline_preview_capability(operation="test", supported=True)
        except Exception as exc:
            if self._should_fallback_to_ephemeral_preview(exc):
                self._put_inline_preview_capability(operation="test", supported=False)
                result = self._test_inline_preview_via_ephemeral_connector(
                    connector_type=connector_type,
                    config=config,
                )
            else:
                self._raise_inline_preview_error(exc)
        return self._put_inline_preview_cache(cache_key, result)

    def _browse_inline_preview(
        self,
        *,
        connector_type: str,
        config: dict[str, Any],
    ) -> ConnectorBrowseOutput:
        cache_key = _inline_preview_cache_key(
            operation="browse",
            connector_type=connector_type,
            config=config,
        )
        cached = self._get_inline_preview_cache(cache_key)
        if isinstance(cached, ConnectorBrowseOutput):
            return cached
        self._consume_inline_preview_slot()
        capability = self._get_inline_preview_capability(operation="browse")
        if capability is False:
            result = self._browse_inline_preview_via_ephemeral_connector(
                connector_type=connector_type,
                config=config,
            )
            return self._put_inline_preview_cache(cache_key, result)
        try:
            result = ConnectorBrowseOutput.from_api(
                self._client().preview_browse_connector(
                    connector_type=connector_type,
                    config=config,
                )
            )
            self._put_inline_preview_capability(operation="browse", supported=True)
        except Exception as exc:
            if self._should_fallback_to_ephemeral_preview(exc):
                self._put_inline_preview_capability(operation="browse", supported=False)
                result = self._browse_inline_preview_via_ephemeral_connector(
                    connector_type=connector_type,
                    config=config,
                )
            else:
                self._raise_inline_preview_error(exc)
        return self._put_inline_preview_cache(cache_key, result)
