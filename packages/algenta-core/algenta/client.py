"""
algenta.client — Cloud API client for the Algenta platform.

The upgrade path from local to cloud. When your workload grows beyond
local processing, switch to the hosted API with one line change.

Usage:

  # Local (default — no API key)
  from algenta import simulate
  result = simulate.risk(revenue=100000, cost=70000)

  # Cloud — same API, infinite scale
  from algenta import AlgentaClient
  client = AlgentaClient(api_key="de_live_...")
  result = client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)
"""
from __future__ import annotations

import os
from typing import Any

from algenta._contract import DEFAULT_BASE_URL


class AlgentaClient:
    """
    Algenta cloud API client.

    Wraps all local algenta functions with cloud execution.
    All methods have the same signature as their local equivalents,
    except they scale to millions of runs and return results faster.

    Example:
        client = AlgentaClient(api_key="de_live_...")
        result = client.simulate.risk(revenue=100000, cost=70000, runs=500000)
        print(result.expected_value, result.probability_of_loss)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.api_key = api_key or os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        self.base_url = base_url

        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key='de_live_...' or set ALGENTA_API_KEY env var.\n"
                "Get a key at: https://algenta.ai/dashboard/api-keys"
            )

        self.simulate  = _BoundModule("simulate",  self.api_key, self.base_url)
        self.decision  = _BoundModule("decision",  self.api_key, self.base_url)
        self.optimize  = _BoundModule("optimize",  self.api_key, self.base_url)
        self.forecast  = _BoundModule("forecast",  self.api_key, self.base_url)

    def health(self) -> dict[str, Any]:
        return _cloud_get("/v1/health", self.api_key, self.base_url)

    def usage(self) -> dict[str, Any]:
        return _cloud_get("/v1/account/usage", self.api_key, self.base_url)


class _BoundModule:
    """Proxy that calls local module functions with mode='cloud'."""

    def __init__(self, module_name: str, api_key: str, base_url: str) -> None:
        self._module_name = module_name
        self._api_key = api_key
        self._base_url = base_url

    def __getattr__(self, name: str):  # type: ignore[override]
        import importlib
        mod = importlib.import_module(f"algenta.{self._module_name}")
        fn = getattr(mod, name)
        api_key = self._api_key
        base_url = self._base_url

        def _bound(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("mode", "cloud")
            kwargs.setdefault("api_key", api_key)
            kwargs.setdefault("base_url", base_url)
            return fn(*args, **kwargs)

        return _bound


def _cloud_get(path: str, api_key: str, base_url: str) -> dict[str, Any]:
    try:
        import httpx
    except ImportError:
        raise ImportError("Cloud mode requires: pip install algenta-core[cloud]") from None
    resp = httpx.get(
        f"{base_url}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
