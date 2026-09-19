# Algenta MCP server — container image for stdio MCP runtimes (e.g. Docker MCP Toolkit).
# Builds the published algenta-mcp package from this source tree; runtime configuration is
# ALGENTA_API_KEY (required) and ALGENTA_BASE_URL (defaults to https://api.algenta.ai).
#
# The base image is pinned to the multi-arch index digest (the tag stays for readability; Docker
# resolves the digest and ignores the tag). Dependabot's docker entry for this directory
# (.github/dependabot.yml) moves the digest when the tag is rebuilt; to refresh it by hand:
#   docker buildx imagetools inspect python:3.12-slim-bookworm --format '{{.Manifest.Digest}}'
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# pyproject.toml references README.md (readme) and LICENSE (license-files), so both are
# required for the build; algenta_mcp/ is the only package (see tool.setuptools config).
# requirements.txt and requirements-build.txt are the hash-pinned locks consumed below.
COPY pyproject.toml README.md LICENSE requirements.txt requirements-build.txt ./
COPY algenta_mcp ./algenta_mcp

# Every download is hash-checked: the runtime dependencies (requirements.txt, compiled from
# pyproject.toml's [project.dependencies]) and the PEP 517 build backend (requirements-build.txt,
# compiled from requirements-build.in). Each lock's header records its refresh command; run it
# from this directory. The package itself is then built offline (--no-index, and
# --no-build-isolation reuses the pinned backend) and installed from the resulting wheel with
# --no-deps, so pip never resolves anything the locks did not pin.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt -r requirements-build.txt \
    && pip wheel --no-cache-dir --no-index --no-deps --no-build-isolation --wheel-dir /tmp/wheels . \
    && pip install --no-cache-dir --no-index --no-deps /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels \
    && groupadd --system app \
    && useradd --system --gid app --home /app app

USER app

# stdio transport is the default; --mode http is available for remote clients.
ENTRYPOINT ["algenta-mcp"]
