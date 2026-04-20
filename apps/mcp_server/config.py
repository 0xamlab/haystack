"""MCP server configuration — environment variables."""
import os

from apps.platform_contract_constants import API_BASE_URL

BASE_URL = (
    os.environ.get("ALGENTA_BASE_URL")
    or os.environ.get("DE_BASE_URL")
    or API_BASE_URL
).rstrip("/")
API_KEY  = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
TIMEOUT  = float(os.environ.get("ALGENTA_MCP_TIMEOUT", "60"))
PORT     = int(os.environ.get("ALGENTA_MCP_PORT", "8001"))
VERSION  = "1.0.0"
