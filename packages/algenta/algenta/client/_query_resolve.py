"""_QueryResolveMixin for the AlgentaClient class.

Extracted from packages/algenta/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _QueryResolveMixin:
    def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().resolve(request, **kwargs)

    def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().query(request, **kwargs)

    def query_with_metadata(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._sdk_client().query_with_metadata(request, **kwargs)

    def query_batch(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_batch(request)

    def query_sql_report(self, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_sql_report(request)

    def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        return self._sdk_client().verify(request, **kwargs)

