# Algenta GPU probe (thyn-ai/algenta-gpu-probe): Qwen3-1.7B through the published CUDA decode
# kernels of thyn-ai/algenta-llm on a Hugging Face GPU Space, checked token by token against a
# transformers float32 CPU reference. Source of truth: apps/spaces/gpu-probe in the Algenta
# repository; the run it rebuilds is docs/hf-kernels/evidence/artifacts/gpu-probe-run12-*.json.
#
# Base: the CUDA 12.8 runtime on Ubuntu 24.04, pinned by digest (multi-arch index; the Hub builds
# amd64). Its NVIDIA_REQUIRE_CUDA driver-branch list predates driver 580 and would refuse the
# Hub's host driver at container start, so NVIDIA_DISABLE_REQUIRE=1 turns that check off — the
# probe's own driver phase applies the real floor (580) instead.
#
# Python: CPython 3.14 through uv (also pinned by digest). `algenta` and `algenta-runtime-native`
# ship CPython 3.14 wheels only; torch 2.9.1+cu128 has cp314 wheels on the PyTorch index.
#
# Assets: fetch_assets.py --bake installs the kernel snapshot (pinned revision, cuda variant,
# native manifest checked for the 6144 staging tier) and the pinned Qwen3-1.7B snapshot into
# HF_HOME as the runtime user; --verify then proves, with HF_HUB_OFFLINE=1, that both resolve
# from the cache. The runtime keeps HF_HUB_OFFLINE=1, so boot never downloads. Set the Space
# variable HF_HUB_OFFLINE=0 to let get_kernel reach the Hub instead (a host without the cache).
# The f64 conversion (about 82 s, 13.8 GB) happens at boot on the Space's disk, not in the image.
FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867

ENV NVIDIA_DISABLE_REQUIRE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_NO_CACHE=1

# libgomp1: the signed algenta native runtime links OpenMP. ca-certificates: the Hub over TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /uvx /bin/

# A managed CPython 3.14 and one virtual environment on PATH for every later step.
RUN uv python install 3.14 \
    && uv venv --python 3.14 /opt/venv
ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# Hub Spaces run the container as uid 1000; the app, the cache and the work dir belong to it.
# ubuntu:24.04 (the CUDA runtime's base) ships an `ubuntu` user at uid 1000 — the Hub build failed with
# `useradd: UID 1000 is not unique` (run 13, 2026-09-24); remove it first, then create the Space user
# at the uid the Hub expects.
RUN (userdel -r ubuntu 2>/dev/null || true) && useradd --create-home --uid 1000 --shell /bin/bash user
WORKDIR /app

# Dependencies first, so a copy edit does not reinstall torch. unsafe-best-match lets the
# `+cu128` torch pin resolve from the PyTorch index next to PyPI.
COPY requirements.txt ./
RUN uv pip install --index-strategy unsafe-best-match -r requirements.txt

COPY --chown=user:user . .
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/hf \
    PROBE_WORK_DIR=/home/user/work \
    PROBE_BUILD_FACTS=/home/user/assets/build_facts.json

# Bake: the kernel at its pinned revision (cuda variant, tier 6144 asserted, tree listing pruned)
# and the pinned Qwen3-1.7B snapshot (about 4.1 GB). Then prove both resolve with the Hub
# unreachable.
RUN python fetch_assets.py --bake
RUN HF_HUB_OFFLINE=1 python fetch_assets.py --verify

ENV HF_HUB_OFFLINE=1
EXPOSE 7860
CMD ["python", "app.py"]
