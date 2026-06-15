"""_DeploymentsModelsMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _DeploymentsModelsMixin:
    def list_deployment_regions(self) -> Any:
        return self._sdk_client().list_deployment_regions()

    def get_deployment(self) -> Any:
        return self._sdk_client().get_deployment()

    def create_deployment(
        self,
        *,
        provider: str = "algenta_shared",
        region: str = "algenta-shared",
        config: dict[str, Any] | None = None,
        billing_markup_pct: float = 20.0,
    ) -> Any:
        return self._sdk_client().create_deployment(
            provider=provider,
            region=region,
            config=config,
            billing_markup_pct=billing_markup_pct,
        )

    def delete_deployment(self, deployment_id: str) -> Any:
        return self._sdk_client().delete_deployment(deployment_id)

    def get_deployment_cost(self, deployment_id: str) -> Any:
        return self._sdk_client().get_deployment_cost(deployment_id)

    def list_models(self) -> Any:
        return self._sdk_client().list_models()

    def resolve_artifact_bridge(
        self,
        *,
        repo_id: str,
        filename: str,
        revision: str | None = None,
        local_files_only: bool = True,
    ) -> Any:
        return self._sdk_client().resolve_artifact_bridge(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            local_files_only=local_files_only,
        )

