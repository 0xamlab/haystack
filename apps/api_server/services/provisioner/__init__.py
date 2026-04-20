"""
Provisioner package — per-provider cloud provisioning.

Public API (unchanged from provisioner_service.py):
  get_provisioner(provider)       → BaseProvisioner | None
  provision_deployment(...)       → ProvisionResult
  get_available_regions()         → dict[str, list[dict]]

Usage:
  from apps.api_server.services.provisioner import provision_deployment, get_available_regions
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog

from .base import BaseProvisioner, ProvisionResult
from .regions import REGIONS, get_available_regions

logger = structlog.get_logger(__name__)

# ─── Provider registry ────────────────────────────────────────────────────────

def _build_registry() -> dict[str, BaseProvisioner]:
    from .aws import AWSProvisioner
    from .azure import AzureProvisioner
    from .gcp import GCPProvisioner
    return {
        "aws":   AWSProvisioner(),
        "azure": AzureProvisioner(),
        "gcp":   GCPProvisioner(),
    }

_provisioners: dict[str, BaseProvisioner] | None = None

def get_provisioner(provider: str) -> BaseProvisioner | None:
    global _provisioners
    if _provisioners is None:
        _provisioners = _build_registry()
    return _provisioners.get(provider)


async def provision_deployment(
    org_id: uuid.UUID,
    deployment_id: uuid.UUID,
    provider: str,
    region: str,
    config: dict[str, Any] | None = None,
) -> ProvisionResult:
    """Top-level provisioning entry point. Called by the deployments router."""
    if provider == "algenta_shared":
        return ProvisionResult(
            success=True,
            endpoint_url=None,
            resource_ids={"type": "shared"},
        )

    provisioner = get_provisioner(provider)
    if provisioner is None:
        return ProvisionResult(False, error=f"Unknown provider: {provider}")

    return await provisioner.provision(org_id, deployment_id, region, config or {})


__all__ = [
    "BaseProvisioner",
    "ProvisionResult",
    "get_provisioner",
    "provision_deployment",
    "get_available_regions",
    "REGIONS",
]
