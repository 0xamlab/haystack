# Builds the linux/amd64 Mojo engine binary (mojo_build/simulate) + its runtime .so's, so the
# api/worker/engine images run the REAL Mojo kernel (RUNTIME_FALLBACK_MODE=deny — no fallback).
#
# Heavy build: installs the pixi/Mojo toolchain and compiles ~961 .mojo files (RAM-intensive).
# Built on linux/amd64, so the binary is natively linux (the local darwin/arm64 binary is irrelevant).
# Output image is consumed via `COPY --from=ghcr.io/escrypto-labs/algenta/mojo:<tag>` by the
# api/worker/engine prod Dockerfiles.
#
# Build:  docker build -f infra/docker/Dockerfile.mojo -t mojo .
FROM debian:bookworm-slim AS mojo-builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIXI_HOME=/opt/pixi \
    PATH=/opt/pixi/bin:/usr/local/bin:/usr/bin:/bin
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git clang lld build-essential python3 xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Modular's pixi package manager
RUN curl -fsSL https://pixi.sh/install.sh | bash

WORKDIR /build
# Build inputs only (keeps the cache tight). pixi.lock pins the toolchain for reproducibility.
COPY mojo_env/ /build/mojo_env/
COPY mojo/ /build/mojo/
COPY scripts/build_mojo_binary.sh scripts/generate_runtime_library_dispatch.py /build/scripts/

# Resolve the Mojo toolchain from the lockfile first (separate, cacheable layer).
RUN cd /build/mojo_env && pixi install --locked

# Compile + link the native binary (the RAM-heavy step). build_mojo_binary.sh handles the
# Linux clang link with the $ORIGIN/../mojo_env/.pixi/envs/default/lib rpath.
RUN cd /build && bash scripts/build_mojo_binary.sh && test -x /build/mojo_build/simulate \
    && file /build/mojo_build/simulate

# ── export: the binary + the exact runtime libs the rpath resolves ──────────────
FROM scratch AS export
COPY --from=mojo-builder /build/mojo_build/simulate /app/mojo_build/simulate
COPY --from=mojo-builder /build/mojo_env/.pixi/envs/default/lib /app/mojo_env/.pixi/envs/default/lib
