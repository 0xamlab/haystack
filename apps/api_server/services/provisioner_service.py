"""
Backward-compatibility shim.

All logic has moved to apps/api_server/services/provisioner/.
This module re-exports everything so existing imports continue working.

Previous callers:
  from apps.api_server.services.provisioner_service import provision_deployment
  from apps.api_server.services.provisioner_service import get_available_regions
  from apps.api_server.services.provisioner_service import ProvisionResult
  from apps.api_server.services.provisioner_service import REGIONS

All of the above continue to work unchanged.
"""
from apps.api_server.services.provisioner import (  # noqa: F401
    REGIONS,
    BaseProvisioner,
    ProvisionResult,
    get_available_regions,
    get_provisioner,
    provision_deployment,
)
from apps.api_server.services.provisioner.aws import AWSProvisioner  # noqa: F401
from apps.api_server.services.provisioner.azure import AzureProvisioner  # noqa: F401
from apps.api_server.services.provisioner.gcp import GCPProvisioner  # noqa: F401
from apps.api_server.services.provisioner.regions import (  # noqa: F401
    fetch_aws_regions,
    fetch_azure_regions,
    fetch_gcp_regions,
)

__all__ = [
    "BaseProvisioner",
    "ProvisionResult",
    "AWSProvisioner",
    "AzureProvisioner",
    "GCPProvisioner",
    "get_provisioner",
    "provision_deployment",
    "get_available_regions",
    "fetch_aws_regions",
    "fetch_azure_regions",
    "fetch_gcp_regions",
    "REGIONS",
]
