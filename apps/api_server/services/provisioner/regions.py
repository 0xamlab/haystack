"""
Cloud region fetching — live from cloud SDKs + curated static fallback.

fetch_aws_regions()   — boto3 EC2 describe_regions()
fetch_azure_regions() — azure-mgmt-subscription list_locations()
fetch_gcp_regions()   — google-cloud-compute regions list()

All functions fall back to the static metadata tables when SDK credentials
are not available (dev environment, CI).
"""
from __future__ import annotations

import asyncio

import structlog

logger = structlog.get_logger(__name__)

# ─── AWS region metadata ──────────────────────────────────────────────────────

_AWS_REGION_META: dict[str, dict[str, str]] = {
    "us-east-1": {"label": "US East (N. Virginia)", "flag": "🇺🇸"},
    "us-east-2": {"label": "US East (Ohio)", "flag": "🇺🇸"},
    "us-west-1": {"label": "US West (N. California)", "flag": "🇺🇸"},
    "us-west-2": {"label": "US West (Oregon)", "flag": "🇺🇸"},
    "ca-central-1": {"label": "Canada (Central)", "flag": "🇨🇦"},
    "ca-west-1": {"label": "Canada West (Calgary)", "flag": "🇨🇦"},
    "eu-west-1": {"label": "Europe (Ireland)", "flag": "🇮🇪"},
    "eu-west-2": {"label": "Europe (London)", "flag": "🇬🇧"},
    "eu-west-3": {"label": "Europe (Paris)", "flag": "🇫🇷"},
    "eu-central-1": {"label": "Europe (Frankfurt)", "flag": "🇩🇪"},
    "eu-central-2": {"label": "Europe (Zurich)", "flag": "🇨🇭"},
    "eu-north-1": {"label": "Europe (Stockholm)", "flag": "🇸🇪"},
    "eu-south-1": {"label": "Europe (Milan)", "flag": "🇮🇹"},
    "eu-south-2": {"label": "Europe (Spain)", "flag": "🇪🇸"},
    "ap-southeast-1": {"label": "Asia Pacific (Singapore)", "flag": "🇸🇬"},
    "ap-southeast-2": {"label": "Asia Pacific (Sydney)", "flag": "🇦🇺"},
    "ap-southeast-3": {"label": "Asia Pacific (Jakarta)", "flag": "🇮🇩"},
    "ap-southeast-4": {"label": "Asia Pacific (Melbourne)", "flag": "🇦🇺"},
    "ap-northeast-1": {"label": "Asia Pacific (Tokyo)", "flag": "🇯🇵"},
    "ap-northeast-2": {"label": "Asia Pacific (Seoul)", "flag": "🇰🇷"},
    "ap-northeast-3": {"label": "Asia Pacific (Osaka)", "flag": "🇯🇵"},
    "ap-south-1": {"label": "Asia Pacific (Mumbai)", "flag": "🇮🇳"},
    "ap-south-2": {"label": "Asia Pacific (Hyderabad)", "flag": "🇮🇳"},
    "ap-east-1": {"label": "Asia Pacific (Hong Kong)", "flag": "🇭🇰"},
    "me-south-1": {"label": "Middle East (Bahrain)", "flag": "🇧🇭"},
    "me-central-1": {"label": "Middle East (UAE)", "flag": "🇦🇪"},
    "sa-east-1": {"label": "South America (São Paulo)", "flag": "🇧🇷"},
    "af-south-1": {"label": "Africa (Cape Town)", "flag": "🇿🇦"},
    "il-central-1": {"label": "Israel (Tel Aviv)", "flag": "🇮🇱"},
    "ap-southeast-5": {"label": "Asia Pacific (Malaysia)", "flag": "🇲🇾"},
    "mx-central-1": {"label": "Mexico (Central)", "flag": "🇲🇽"},
}


def _static_aws_regions() -> list[dict[str, str]]:
    return [{"id": k, **v} for k, v in _AWS_REGION_META.items()]


# ─── Azure region metadata ────────────────────────────────────────────────────

_AZURE_REGION_META: dict[str, dict[str, str]] = {
    "eastus": {"label": "East US (Virginia)", "flag": "🇺🇸"},
    "eastus2": {"label": "East US 2 (Virginia)", "flag": "🇺🇸"},
    "westus": {"label": "West US (California)", "flag": "🇺🇸"},
    "westus2": {"label": "West US 2 (Washington)", "flag": "🇺🇸"},
    "westus3": {"label": "West US 3 (Arizona)", "flag": "🇺🇸"},
    "centralus": {"label": "Central US (Iowa)", "flag": "🇺🇸"},
    "northcentralus": {"label": "North Central US (Illinois)", "flag": "🇺🇸"},
    "southcentralus": {"label": "South Central US (Texas)", "flag": "🇺🇸"},
    "canadacentral": {"label": "Canada Central (Toronto)", "flag": "🇨🇦"},
    "canadaeast": {"label": "Canada East (Quebec)", "flag": "🇨🇦"},
    "northeurope": {"label": "North Europe (Ireland)", "flag": "🇮🇪"},
    "westeurope": {"label": "West Europe (Netherlands)", "flag": "🇳🇱"},
    "uksouth": {"label": "UK South (London)", "flag": "🇬🇧"},
    "ukwest": {"label": "UK West (Cardiff)", "flag": "🇬🇧"},
    "francecentral": {"label": "France Central (Paris)", "flag": "🇫🇷"},
    "germanywestcentral": {"label": "Germany West Central (Frankfurt)", "flag": "🇩🇪"},
    "switzerlandnorth": {"label": "Switzerland North (Zurich)", "flag": "🇨🇭"},
    "norwayeast": {"label": "Norway East (Oslo)", "flag": "🇳🇴"},
    "swedencentral": {"label": "Sweden Central (Gävle)", "flag": "🇸🇪"},
    "polandcentral": {"label": "Poland Central (Warsaw)", "flag": "🇵🇱"},
    "italynorth": {"label": "Italy North (Milan)", "flag": "🇮🇹"},
    "spaincentral": {"label": "Spain Central (Madrid)", "flag": "🇪🇸"},
    "israelcentral": {"label": "Israel Central (Tel Aviv)", "flag": "🇮🇱"},
    "uaenorth": {"label": "UAE North (Dubai)", "flag": "🇦🇪"},
    "qatarcentral": {"label": "Qatar Central (Doha)", "flag": "🇶🇦"},
    "southafricanorth": {"label": "South Africa North (Johannesburg)", "flag": "🇿🇦"},
    "eastasia": {"label": "East Asia (Hong Kong)", "flag": "🇭🇰"},
    "southeastasia": {"label": "Southeast Asia (Singapore)", "flag": "🇸🇬"},
    "japaneast": {"label": "Japan East (Tokyo)", "flag": "🇯🇵"},
    "japanwest": {"label": "Japan West (Osaka)", "flag": "🇯🇵"},
    "koreacentral": {"label": "Korea Central (Seoul)", "flag": "🇰🇷"},
    "australiaeast": {"label": "Australia East (NSW)", "flag": "🇦🇺"},
    "australiasoutheast": {"label": "Australia Southeast (Victoria)", "flag": "🇦🇺"},
    "centralindia": {"label": "Central India (Pune)", "flag": "🇮🇳"},
    "southindia": {"label": "South India (Chennai)", "flag": "🇮🇳"},
    "westindia": {"label": "West India (Mumbai)", "flag": "🇮🇳"},
    "brazilsouth": {"label": "Brazil South (São Paulo)", "flag": "🇧🇷"},
    "mexicocentral": {"label": "Mexico Central", "flag": "🇲🇽"},
}


def _static_azure_regions() -> list[dict[str, str]]:
    return [{"id": k, **v} for k, v in _AZURE_REGION_META.items()]


# ─── GCP region metadata ──────────────────────────────────────────────────────

_GCP_REGION_META: dict[str, dict[str, str]] = {
    "us-central1": {"label": "US Central (Iowa)", "flag": "🇺🇸"},
    "us-east1": {"label": "US East (S. Carolina)", "flag": "🇺🇸"},
    "us-east4": {"label": "US East (N. Virginia)", "flag": "🇺🇸"},
    "us-east5": {"label": "US East (Columbus)", "flag": "🇺🇸"},
    "us-south1": {"label": "US South (Dallas)", "flag": "🇺🇸"},
    "us-west1": {"label": "US West (Oregon)", "flag": "🇺🇸"},
    "us-west2": {"label": "US West (Los Angeles)", "flag": "🇺🇸"},
    "us-west3": {"label": "US West (Salt Lake City)", "flag": "🇺🇸"},
    "us-west4": {"label": "US West (Las Vegas)", "flag": "🇺🇸"},
    "northamerica-northeast1": {"label": "Canada (Montréal)", "flag": "🇨🇦"},
    "northamerica-northeast2": {"label": "Canada (Toronto)", "flag": "🇨🇦"},
    "southamerica-east1": {"label": "South America (São Paulo)", "flag": "🇧🇷"},
    "southamerica-west1": {"label": "South America (Santiago)", "flag": "🇨🇱"},
    "europe-west1": {"label": "Europe West (Belgium)", "flag": "🇧🇪"},
    "europe-west2": {"label": "Europe West (London)", "flag": "🇬🇧"},
    "europe-west3": {"label": "Europe West (Frankfurt)", "flag": "🇩🇪"},
    "europe-west4": {"label": "Europe West (Netherlands)", "flag": "🇳🇱"},
    "europe-west6": {"label": "Europe West (Zurich)", "flag": "🇨🇭"},
    "europe-west8": {"label": "Europe West (Milan)", "flag": "🇮🇹"},
    "europe-west9": {"label": "Europe West (Paris)", "flag": "🇫🇷"},
    "europe-west10": {"label": "Europe West (Berlin)", "flag": "🇩🇪"},
    "europe-west12": {"label": "Europe West (Turin)", "flag": "🇮🇹"},
    "europe-north1": {"label": "Europe North (Finland)", "flag": "🇫🇮"},
    "europe-central2": {"label": "Europe Central (Warsaw)", "flag": "🇵🇱"},
    "europe-southwest1": {"label": "Europe Southwest (Madrid)", "flag": "🇪🇸"},
    "me-central1": {"label": "Middle East Central (Doha)", "flag": "🇶🇦"},
    "me-central2": {"label": "Middle East Central (Dammam)", "flag": "🇸🇦"},
    "me-west1": {"label": "Middle East West (Tel Aviv)", "flag": "🇮🇱"},
    "africa-south1": {"label": "Africa South (Johannesburg)", "flag": "🇿🇦"},
    "asia-east1": {"label": "Asia East (Taiwan)", "flag": "🇹🇼"},
    "asia-east2": {"label": "Asia East (Hong Kong)", "flag": "🇭🇰"},
    "asia-northeast1": {"label": "Asia Northeast (Tokyo)", "flag": "🇯🇵"},
    "asia-northeast2": {"label": "Asia Northeast (Osaka)", "flag": "🇯🇵"},
    "asia-northeast3": {"label": "Asia Northeast (Seoul)", "flag": "🇰🇷"},
    "asia-south1": {"label": "Asia South (Mumbai)", "flag": "🇮🇳"},
    "asia-south2": {"label": "Asia South (Delhi)", "flag": "🇮🇳"},
    "asia-southeast1": {"label": "Asia Southeast (Singapore)", "flag": "🇸🇬"},
    "asia-southeast2": {"label": "Asia Southeast (Jakarta)", "flag": "🇮🇩"},
    "australia-southeast1": {"label": "Australia Southeast (Sydney)", "flag": "🇦🇺"},
    "australia-southeast2": {"label": "Australia Southeast (Melbourne)", "flag": "🇦🇺"},
}


def _static_gcp_regions() -> list[dict[str, str]]:
    return [{"id": k, **v} for k, v in _GCP_REGION_META.items()]


# ─── Live fetchers ────────────────────────────────────────────────────────────

async def fetch_aws_regions() -> list[dict[str, str]]:
    """Fetch live AWS regions via boto3. Falls back to static list."""
    try:
        import boto3
        loop = asyncio.get_event_loop()

        def _fetch():
            ec2 = boto3.client("ec2", region_name="us-east-1")
            resp = ec2.describe_regions(AllRegions=False)
            regions = []
            for r in resp.get("Regions", []):
                rid = r["RegionName"]
                meta = _AWS_REGION_META.get(rid, {"label": rid, "flag": "🌐"})
                regions.append({"id": rid, **meta})
            return regions

        return await loop.run_in_executor(None, _fetch)
    except Exception as exc:
        logger.debug("aws_regions_fallback", error=str(exc))
        return _static_aws_regions()


async def fetch_azure_regions() -> list[dict[str, str]]:
    """Fetch live Azure regions. Falls back to static list."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.subscription import SubscriptionClient

        loop = asyncio.get_event_loop()

        def _fetch():
            cred   = DefaultAzureCredential()
            client = SubscriptionClient(cred)
            subs   = list(client.subscriptions.list())
            if not subs:
                raise RuntimeError("No Azure subscriptions found")
            sub_id = subs[0].subscription_id
            locs   = list(client.subscriptions.list_locations(sub_id))
            regions = []
            for loc in locs:
                rid  = loc.name
                meta = _AZURE_REGION_META.get(rid, {"label": loc.display_name or rid, "flag": "🌐"})
                regions.append({"id": rid, **meta})
            return regions

        return await loop.run_in_executor(None, _fetch)
    except Exception as exc:
        logger.debug("azure_regions_fallback", error=str(exc))
        return _static_azure_regions()


async def fetch_gcp_regions() -> list[dict[str, str]]:
    """Fetch live GCP regions. Falls back to static list."""
    try:
        from google.cloud import compute_v1

        loop = asyncio.get_event_loop()

        def _fetch():
            client  = compute_v1.RegionsClient()
            project = "algenta-prod"
            regions = []
            for r in client.list(project=project):
                rid  = r.name
                meta = _GCP_REGION_META.get(rid, {"label": rid, "flag": "🌐"})
                regions.append({"id": rid, **meta})
            return regions

        return await loop.run_in_executor(None, _fetch)
    except Exception as exc:
        logger.debug("gcp_regions_fallback", error=str(exc))
        return _static_gcp_regions()


async def get_available_regions() -> dict[str, list[dict[str, str]]]:
    """Fetch live regions from all three cloud providers concurrently."""
    aws_regions, azure_regions, gcp_regions = await asyncio.gather(
        fetch_aws_regions(),
        fetch_azure_regions(),
        fetch_gcp_regions(),
    )
    return {
        "aws":   aws_regions,
        "azure": azure_regions,
        "gcp":   gcp_regions,
    }


# Synchronous static snapshot for callers that don't need live data
REGIONS: dict[str, list[dict[str, str]]] = {
    "algenta_shared": [
        {
            "id": "algenta-shared",
            "label": "Algenta Managed (Multi-tenant)",
            "flag": "🌐",
        }
    ],
    "aws":   _static_aws_regions(),
    "azure": _static_azure_regions(),
    "gcp":   _static_gcp_regions(),
}
