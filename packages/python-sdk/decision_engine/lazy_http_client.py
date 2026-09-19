# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class LazySyncHttpClient:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._instance: Any | None = None

    def _ensure_instance(self) -> Any:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        return self._ensure_instance().request(method, path, **kwargs)

    def close(self) -> None:
        if self._instance is not None:
            self._instance.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure_instance(), name)


class LazyAsyncHttpClient:
    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._instance: Any | None = None

    def _ensure_instance(self) -> Any:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        return await self._ensure_instance().request(method, path, **kwargs)

    async def aclose(self) -> None:
        if self._instance is not None:
            await self._instance.aclose()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ensure_instance(), name)


__all__ = ["LazyAsyncHttpClient", "LazySyncHttpClient"]
