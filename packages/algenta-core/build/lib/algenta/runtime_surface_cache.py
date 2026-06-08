from __future__ import annotations

import copy
import time
from typing import Any

_API_SURFACE_CACHE_TTL_SECONDS = 5.0


class RuntimeApiSurfaceCacheMixin:
    def _api_cache_key(self, *parts: object) -> str:
        return ":".join(str(part) for part in parts)

    def _cleanup_api_surface_cache(self) -> None:
        now = time.monotonic()
        expired_keys = [
            cache_key
            for cache_key, (expires_at, _value) in self._api_surface_cache.items()
            if expires_at <= now
        ]
        for cache_key in expired_keys:
            self._api_surface_cache.pop(cache_key, None)

    def _get_api_surface_cache(self, cache_key: str) -> Any | None:
        self._cleanup_api_surface_cache()
        entry = self._api_surface_cache.get(cache_key)
        if entry is None:
            return None
        _expires_at, value = entry
        return copy.deepcopy(value)

    def _put_api_surface_cache(self, cache_key: str, value: Any) -> Any:
        stored = copy.deepcopy(value)
        self._api_surface_cache[cache_key] = (
            time.monotonic() + _API_SURFACE_CACHE_TTL_SECONDS,
            stored,
        )
        return copy.deepcopy(stored)

    def _invalidate_api_surface_cache(self, *prefixes: str) -> None:
        if not prefixes:
            self._api_surface_cache.clear()
            return
        prefixes_tuple = tuple(prefixes)
        stale_keys = [
            cache_key
            for cache_key in self._api_surface_cache
            if cache_key.startswith(prefixes_tuple)
        ]
        for cache_key in stale_keys:
            self._api_surface_cache.pop(cache_key, None)
