"""REST API data source connector."""
from __future__ import annotations

from typing import Any

import httpx

from apps.api_server.services.columnar_loader import records_to_arrow_table

from .base import BaseConnector, ConnectorRegistry


@ConnectorRegistry.register
class RESTConnector(BaseConnector):
    """Fetch data from any REST API endpoint.

    Config keys:
        url:        Target URL (required).
        method:     HTTP method — ``GET`` (default) or ``POST``.
        headers:    Dict of request headers.
        params:     Dict of query-string parameters.
        body:       JSON body for POST requests.
        timeout:    Request timeout in seconds (default 30).
        data_path:  Dot-separated path to the data array in the response
                    (e.g. ``"results.items"``).
    """

    connector_type: str = "rest_api"

    async def fetch_data(self) -> list[dict[str, Any]]:
        url: str = self.config.get("url", "")
        method: str = self.config.get("method", "GET").upper()
        headers: dict[str, str] = self.config.get("headers", {})
        params: dict[str, str] = self.config.get("params", {})
        body: Any = self.config.get("body")
        timeout: int = self.config.get("timeout", 30)
        data_path: str = self.config.get("data_path", "")

        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params)
            else:
                resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data: Any = resp.json()

        # Navigate data_path (e.g. "results.items" → data["results"]["items"])
        if data_path:
            for key in data_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                elif isinstance(data, list) and key.isdigit():
                    data = data[int(key)]

        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []

    async def fetch_table(self) -> Any | None:
        records = await self.fetch_data()
        if not records:
            return None
        return records_to_arrow_table(records)

    async def validate_connection(self) -> tuple[bool, str]:
        """Attempt a fetch and report record count or error."""
        try:
            data = await self.fetch_data()
            return True, f"Connected. Retrieved {len(data)} records."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
