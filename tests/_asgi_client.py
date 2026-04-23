from __future__ import annotations

import asyncio
from typing import Any

import httpx


class SyncASGIClient:
    """Minimal sync wrapper over httpx.AsyncClient with explicit ASGI transport."""

    def __init__(
        self,
        app: Any,
        *,
        base_url: str = "http://testserver",
        headers: dict[str, str] | None = None,
        manage_lifespan: bool = False,
        raise_app_exceptions: bool = True,
    ) -> None:
        self._app = app
        self._base_url = base_url
        self._headers = headers
        self._manage_lifespan = manage_lifespan
        self._raise_app_exceptions = raise_app_exceptions
        self._client: httpx.AsyncClient | None = None

    def __enter__(self) -> SyncASGIClient:
        if self._manage_lifespan:
            asyncio.run(self._app.router.startup())
        transport = httpx.ASGITransport(
            app=self._app,
            raise_app_exceptions=self._raise_app_exceptions,
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            transport=transport,
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self._client is not None:
            asyncio.run(self._client.aclose())
            self._client = None
        if self._manage_lifespan:
            asyncio.run(self._app.router.shutdown())

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("SyncASGIClient must be used as a context manager.")
        return asyncio.run(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
