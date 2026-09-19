# Algenta MCP server — container image for stdio MCP runtimes (e.g. Docker MCP Toolkit).
# Builds the published algenta-mcp package from this source tree; runtime configuration is
# ALGENTA_API_KEY (required) and ALGENTA_BASE_URL (defaults to https://api.algenta.ai).
#
# The base image is pinned to the multi-arch index digest (the tag stays for readability; Docker
# resolves the digest and ignores the tag). Dependabot's docker entry for this directory
# (.github/dependabot.yml) moves the digest when the tag is rebuilt; to refresh it by hand:
#   docker buildx imagetools inspect python:3.12-slim-bookworm --format '{{.Manifest.Digest}}'
# Two stages: the build backend (setuptools, wheel) lives only in `builder`; the runtime image
# receives the finished wheel and the hash-pinned runtime dependencies, nothing that can build code.
FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /src

# pyproject.toml references README.md (readme) and LICENSE (license-files), so both are
# required for the build; algenta_mcp/ is the only package (see tool.setuptools config).
# requirements-build.txt is the hash-pinned PEP 517 backend (compiled from requirements-build.in;
# its header records the refresh command).
COPY pyproject.toml README.md LICENSE requirements-build.txt ./
COPY algenta_mcp ./algenta_mcp

# Build the package offline (--no-index; --no-build-isolation reuses the pinned backend) into
# exactly ONE wheel -- the count check turns "no wheel" or "unexpected extra wheels" into a build
# failure here instead of a confusing pip error in the runtime stage.
RUN pip install --no-cache-dir --require-hashes -r requirements-build.txt \
    && pip wheel --no-cache-dir --no-index --no-deps --no-build-isolation --wheel-dir /wheels . \
    && test "$(find /wheels -maxdepth 1 -name 'algenta_mcp-*.whl' | wc -l)" -eq 1


FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# requirements.txt is the hash-pinned runtime lock (compiled from pyproject.toml's
# [project.dependencies]; its header records the refresh command). Every download is hash-checked;
# the package itself comes from the builder stage's wheel and is installed with --no-deps, so pip
# never resolves anything the lock did not pin. No build backend is ever installed in this image.
COPY requirements.txt ./
COPY --from=builder /wheels /tmp/wheels

RUN pip install --no-cache-dir --require-hashes -r requirements.txt \
    && pip install --no-cache-dir --no-index --no-deps /tmp/wheels/algenta_mcp-*.whl \
    && rm -rf /tmp/wheels requirements.txt \
    && groupadd --system app \
    && useradd --system --gid app --home /app app

USER app

# stdio transport is the default; --mode http is available for remote clients.
ENTRYPOINT ["algenta-mcp"]
