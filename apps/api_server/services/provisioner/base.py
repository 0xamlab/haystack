"""Abstract base provisioner and shared result type."""

from __future__ import annotations

import abc
import uuid
from typing import Any


class ProvisionResult:
    __slots__ = ("success", "endpoint_url", "resource_ids", "error")

    def __init__(
        self,
        success: bool,
        endpoint_url: str | None = None,
        resource_ids: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.endpoint_url = endpoint_url
        self.resource_ids = resource_ids or {}
        self.error = error


class BaseProvisioner(abc.ABC):
    """Abstract base for cloud provider provisioners."""

    @abc.abstractmethod
    async def provision(
        self,
        org_id: uuid.UUID,
        deployment_id: uuid.UUID,
        region: str,
        config: dict[str, Any],
    ) -> ProvisionResult:
        """Provision a new isolated engine deployment. Returns endpoint URL when done."""
        ...

    @abc.abstractmethod
    async def deprovision(
        self,
        deployment_id: uuid.UUID,
        resource_ids: dict[str, Any],
    ) -> bool:
        """Tear down cloud resources for a deployment. Returns True on success."""
        ...

    @abc.abstractmethod
    async def get_monthly_cost_cents(
        self,
        deployment_id: uuid.UUID,
        resource_ids: dict[str, Any],
        year: int,
        month: int,
    ) -> int:
        """Return cloud cost for the given calendar month in USD cents."""
        ...
