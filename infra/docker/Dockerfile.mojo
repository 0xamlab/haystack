# Builds the linux/amd64 Mojo engine binary (mojo_build/simulate) + its runtime .so's, so the
# api/worker/engine images run the REAL Mojo kernel (RUNTIME_FALLBACK_MODE=deny — no fallback).
#
# Installs the pixi/Mojo toolchain and compiles the engine. The 457-module runtime-library catalog
# (/v1/libraries/execute, reached only via the "library_execute" message) is gated OFF by default
# (runtime_library_http_api_enabled=False) and is NOT on the simulations or codna fix path — so we
# build a MINIMAL dispatch (MOJO_RUNTIME_MODULE_FILTER below). Compiling all 457 dead modules into
# one object is what OOMs a 32GB builder; the core engine alone compiles comfortably on a 16GB box.
# Built on linux/amd64, so the binary is natively linux (the local darwin/arm64 binary is irrelevant).
# Output image is consumed via `COPY --from=ghcr.io/escrypto-labs/algenta/mojo:<tag>` by the
# api/worker/engine prod Dockerfiles.
#
# Build:  docker build -f infra/docker/Dockerfile.mojo -t mojo .
FROM debian:bookworm-slim AS mojo-builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIXI_HOME=/opt/pixi \
    PATH=/opt/pixi/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH=/build
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates git clang lld build-essential python3 xz-utils file \
    && rm -rf /var/lib/apt/lists/*

# Modular's pixi package manager
RUN curl -fsSL https://pixi.sh/install.sh | bash

WORKDIR /build
# Build inputs only (keeps the cache tight). pixi.lock pins the toolchain for reproducibility.
COPY mojo_env/ /build/mojo_env/
COPY mojo/ /build/mojo/
COPY scripts/build_mojo_binary.sh scripts/generate_runtime_library_dispatch.py /build/scripts/
# The dispatch generator imports apps.runtime.mojo_inventory (stdlib-only) to enumerate the
# runtime-library modules; PYTHONPATH=/build makes it importable.
COPY apps/__init__.py /build/apps/__init__.py
COPY apps/runtime/ /build/apps/runtime/

# Resolve the Mojo toolchain from the lockfile first (separate, cacheable layer).
RUN cd /build/mojo_env && pixi install --locked

# Build only the core decision engine into the runtime-library dispatch. main.mojo's simulations
# path (_run_raw → monte_carlo/scenario/bootstrap/sensitivity/mcmc/lhs/qmc_sobol/compare/decision_tree)
# imports those engines directly and is unaffected by this filter; the filter only trims the
# library_execute catalog (API-gated-off here). Widen / clear this on a >64GB builder to ship the
# full catalog API.
ARG MOJO_RUNTIME_MODULE_FILTER=ab_testing
ENV MOJO_RUNTIME_MODULE_FILTER=${MOJO_RUNTIME_MODULE_FILTER}

# Compile + link the native binary. build_mojo_binary.sh handles the Linux clang link with the
# $ORIGIN/../mojo_env/.pixi/envs/default/lib rpath.
RUN cd /build && bash scripts/build_mojo_binary.sh && test -x /build/mojo_build/simulate \
    && file /build/mojo_build/simulate

# ── export: the binary + the exact runtime libs the rpath resolves ──────────────
FROM scratch AS export
COPY --from=mojo-builder /build/mojo_build/simulate /app/mojo_build/simulate
COPY --from=mojo-builder /build/mojo_env/.pixi/envs/default/lib /app/mojo_env/.pixi/envs/default/lib
