# Algenta MCP server — container image for stdio MCP runtimes (e.g. Docker MCP Toolkit).
# Builds the published algenta-mcp package from this source tree; runtime configuration is
# ALGENTA_API_KEY (required) and ALGENTA_BASE_URL (defaults to https://api.algenta.ai).
FROM python:3.12-slim-bookworm

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# pyproject.toml references README.md (readme) and LICENSE (license-files), so both are
# required for the build; algenta_mcp/ is the only package (see tool.setuptools config).
COPY pyproject.toml README.md LICENSE ./
COPY algenta_mcp ./algenta_mcp

RUN pip install --no-cache-dir . \
    && groupadd --system app \
    && useradd --system --gid app --home /app app

USER app

# stdio transport is the default; --mode http is available for remote clients.
ENTRYPOINT ["algenta-mcp"]
