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
        self._lifespan_context: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self) -> SyncASGIClient:
        self._loop = asyncio.new_event_loop()
        if self._manage_lifespan:
            lifespan_factory = getattr(self._app.router, "lifespan_context", None)
            if callable(lifespan_factory):
                self._lifespan_context = lifespan_factory(self._app)
                self._loop.run_until_complete(self._lifespan_context.__aenter__())
            else:
                self._loop.run_until_complete(self._app.router.startup())
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
        if self._loop is None:
            return
        try:
            if self._client is not None:
                self._loop.run_until_complete(self._client.aclose())
                self._client = None
            if self._manage_lifespan:
                if self._lifespan_context is not None:
                    self._loop.run_until_complete(
                        self._lifespan_context.__aexit__(exc_type, exc, tb)
                    )
                    self._lifespan_context = None
                else:
                    self._loop.run_until_complete(self._app.router.shutdown())
        finally:
            self._loop.close()
            self._loop = None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("SyncASGIClient must be used as a context manager.")
        if self._loop is None:
            raise RuntimeError("SyncASGIClient event loop is not initialized.")
        return self._loop.run_until_complete(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)
