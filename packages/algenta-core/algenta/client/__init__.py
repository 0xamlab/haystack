"""
algenta.client — Cloud API client for the Algenta platform.

The upgrade path from local to cloud. When your workload grows beyond
local processing, switch to the hosted API with one line change.

Usage:

  import os

  # Local (default — no API key)
  from algenta import simulate
  result = simulate.risk(revenue=100000, cost=70000)

  # Cloud — same API, infinite scale
  from algenta import AlgentaClient
  api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
  if not api_key:
      raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
  client = AlgentaClient(api_key=api_key)
  result = client.simulate.risk(revenue=100000, cost=70000, runs=1_000_000)

The cloud example above is the Cloud Managed path. In `self_hosted` and
`air_gapped`, pass an explicit self-hosted `base_url` and use the API key
provisioned by your self-hosted operator deployment instead. Private profiles
fail closed and do not silently fall back to Codna cloud.
"""

from __future__ import annotations

import inspect
import os
from importlib import import_module
from typing import Any

from algenta.privacy_profile import api_key_help_text, resolve_cloud_base_url


from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401
from algenta.client._account_billing import _AccountBillingMixin  # noqa: E402
from algenta.client._decisions import _DecisionsMixin  # noqa: E402
from algenta.client._products_jobs_triggers import _ProductsJobsTriggersMixin  # noqa: E402
from algenta.client._capabilities_skills import _CapabilitiesSkillsMixin  # noqa: E402
from algenta.client._query_resolve import _QueryResolveMixin  # noqa: E402
from algenta.client._connectors_datasets_repository import _ConnectorsDatasetsRepositoryMixin  # noqa: E402
from algenta.client._deployments_models import _DeploymentsModelsMixin  # noqa: E402
from algenta.client._llm import _LLMMixin  # noqa: E402
from algenta.client._agent_runs import _AgentRunsMixin  # noqa: E402


class AlgentaClient(_AccountBillingMixin, _DecisionsMixin, _ProductsJobsTriggersMixin, _CapabilitiesSkillsMixin, _QueryResolveMixin, _ConnectorsDatasetsRepositoryMixin, _DeploymentsModelsMixin, _LLMMixin, _AgentRunsMixin):
    """
    Codna cloud API client.

    Wraps all local algenta functions with cloud execution.
    All methods have the same signature as their local equivalents,
    except they scale to millions of runs and return results faster.

    Example:
        import os

        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        if not api_key:
            raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")
        client = AlgentaClient(api_key=api_key)
        result = client.simulate.risk(revenue=100000, cost=70000, runs=500000)
        print(result.expected_value, result.probability_of_loss)

    That example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
    pass an explicit self-hosted `base_url` and use the API key provisioned by
    your self-hosted operator deployment instead.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        self.base_url = resolve_cloud_base_url(
            explicit_base_url=base_url,
            component="AlgentaClient",
        )

        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key explicitly or set ALGENTA_API_KEY / DE_API_KEY environment variables.\n"
                + api_key_help_text(
                    component="AlgentaClient",
                    fallback_base_url=self.base_url,
                )
            )

        self.simulate = _BoundModule("simulate", self.api_key, self.base_url)
        self.decision = _BoundModule("decision", self.api_key, self.base_url)
        self.optimize = _BoundModule("optimize", self.api_key, self.base_url)
        self.forecast = _BoundModule("forecast", self.api_key, self.base_url)
        self._decision_engine_client: Any | None = None

    def _sdk_client(self) -> Any:
        client = self._decision_engine_client
        if client is not None:
            return client
        try:
            decision_engine = import_module("decision_engine")
        except ImportError as exc:
            raise ImportError(
                "Plan-aligned cloud routes require the decision-engine SDK package. "
                "Install algenta-core with cloud/runtime dependencies."
            ) from exc
        client = decision_engine.DecisionEngineClient(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=0,
        )
        self._decision_engine_client = client
        return client


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
        signature = inspect.signature(fn)
        accepted_kwargs = set(signature.parameters)
        api_key = self._api_key
        base_url = self._base_url

        def _bound(*args: Any, **kwargs: Any) -> Any:
            if "mode" in accepted_kwargs:
                kwargs.setdefault("mode", "cloud")
            if "api_key" in accepted_kwargs:
                kwargs.setdefault("api_key", api_key)
            if "base_url" in accepted_kwargs:
                kwargs.setdefault("base_url", base_url)
            return fn(*args, **kwargs)

        return _bound


CodnaClient = AlgentaClient  # back-compat alias
