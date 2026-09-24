# Algenta GPU probe (thyn-ai/algenta-gpu-probe): the published single-stream race, live on a
# Hugging Face GPU Space. Lane A is the CUDA engine bundled in the algenta-runtime-native wheel
# (conform_generate_cuda), lane B is llama-server from ggml-org's official prebuilt CUDA server
# image, both on Qwen3-0.6B-Base, the same 256-token prompt, gen=64; the Hub kernels' f32 parity
# path and plain transformers run beside them. Source of truth: apps/spaces/gpu-probe in the
# Algenta repository; docs/spaces/GPU-PROBE.md is the runbook.
#
# Stage 1 (llama): ggml-org's official `server-cuda` image at the versioned tag closest to and not
# below the published pin (the pages' b10210 was built from source; the Hub's builder cut that
# CUDA compile off at 62 minutes, run 15): tag server-cuda-b10223, build 10223, commit
# 11924d4c17abc27383376a1ac6a24fa3e36c1c0c, referenced by the digest of its multi-arch index (the
# Hub builds linux/amd64). It is built on the same nvidia/cuda:12.8.1-runtime-ubuntu24.04 as this
# image (cudart 12.8.90, cublas 12.8.4.1, nccl 2.25.1), with GGML_BACKEND_DL and ggml's default
# CUDA 12.8 architecture list (PTX 50/61/70/75/80/90, cubins 86/89/120a): the L4 runs an sm_89
# cubin, as the published source build did. Nothing is compiled here; the image build takes
# minutes, not an hour.
#
# Stage 2 (converter): a shallow checkout of that same commit for convert_hf_to_gguf.py, its
# conversion/ package and gguf-py, so the GGUF baked below matches the server; git lives in this
# stage only. Nothing of it but /opt/llama reaches the runtime image.
#
# Stage 3 (runtime): the CUDA 12.8 runtime on Ubuntu 24.04, pinned by digest (multi-arch index;
# the Hub builds amd64). Its NVIDIA_REQUIRE_CUDA driver-branch list predates driver 580 and
# would refuse the Hub's host driver at container start, so NVIDIA_DISABLE_REQUIRE=1 turns that
# check off — the probe's own driver phase applies the real floor (580) instead.
#
# Python: CPython 3.14 through uv (also pinned by digest). `algenta` and `algenta-runtime-native`
# ship CPython 3.14 wheels only; torch 2.9.1+cu128 has cp314 wheels on the PyTorch index.
#
# Assets: fetch_assets.py --bake installs the kernel snapshot (pinned revision, cuda variant,
# native manifest checked for the 6144 staging tier) and the pinned Qwen3-0.6B-Base snapshot
# into HF_HOME as the runtime user, inspects the engine lane A will resolve (the binary the
# ALGENTA_CUDA_ENGINE build argument names, else the wheel's signed engine) through the manifest
# beside it, checks `llama-server --version` against the pins (fail-closed,
# llama_version_mismatch; a backend refused by ggml's registry is llama_backend_load_failed),
# lists the devices and backends the registry finds beside the launcher and makes the CUDA
# backend's loader say why it will not load here (the driver, on a GPU-less builder; anything
# else fails the build), then converts the snapshot to the F16 GGUF with the converter's imports
# checked first; --verify then proves, with HF_HUB_OFFLINE=1, that everything resolves locally.
# The runtime keeps HF_HUB_OFFLINE=1, so boot never downloads. Set the Space variable
# HF_HUB_OFFLINE=0 to let get_kernel reach the Hub instead (a host without the cache). The f64
# conversion (about 4.8 GB) happens at boot on the Space's disk, not in the image.
ARG LLAMA_CPP_COMMIT=11924d4c17abc27383376a1ac6a24fa3e36c1c0c
ARG LLAMA_CPP_BUILD=10223
ARG LLAMA_IMAGE_DIGEST=sha256:11b2641870148c90fa99353f91aab7572c6f0e6c66e96aca49af88dd9c26a00b

# ghcr.io/ggml-org/llama.cpp:server-cuda-b10223 (the ARG above repeats this digest for the pin
# file; the two are asserted equal by the tests).
FROM ghcr.io/ggml-org/llama.cpp@sha256:11b2641870148c90fa99353f91aab7572c6f0e6c66e96aca49af88dd9c26a00b AS llama

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867 AS converter

ARG LLAMA_CPP_COMMIT
ARG LLAMA_CPP_BUILD
ARG LLAMA_IMAGE_DIGEST
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# A shallow fetch of exactly the commit the prebuilt server reports (tag b10223); the converter,
# its package and gguf-py are kept, the pins written beside them for the bake to check.
RUN git init -q /opt/llama.cpp \
    && cd /opt/llama.cpp \
    && git remote add origin https://github.com/ggml-org/llama.cpp.git \
    && git fetch -q --depth 1 origin "${LLAMA_CPP_COMMIT}" \
    && git checkout -q FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}" \
    && mkdir -p /opt/llama \
    && cp /opt/llama.cpp/convert_hf_to_gguf.py /opt/llama/convert_hf_to_gguf.py \
    && cp -r /opt/llama.cpp/conversion /opt/llama/conversion \
    && cp -r /opt/llama.cpp/gguf-py /opt/llama/gguf-py \
    && echo "${LLAMA_CPP_COMMIT}" > /opt/llama/COMMIT \
    && echo "${LLAMA_CPP_BUILD}" > /opt/llama/BUILD \
    && echo "${LLAMA_IMAGE_DIGEST}" > /opt/llama/IMAGE_DIGEST

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867

ARG LLAMA_CPP_BUILD
ENV NVIDIA_DISABLE_REQUIRE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_NO_CACHE=1

# libgomp1: the signed algenta native runtime and ggml link OpenMP. libssl3t64: llama-server's
# HTTP server links OpenSSL (in the base already; named so the need is visible). ca-certificates:
# the Hub over TLS. The CUDA runtime image provides libcublas.so.12 / libcublasLt.so.12,
# libcudart.so.12 and libnccl.so.2, the host libraries the bundled engine and the prebuilt
# libggml-cuda.so link (the same versions ggml-org's image was built on); the wheel ships its
# own libcudart.so.12 beside the engine.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 libssl3t64 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /uvx /bin/

# The opponent: the official image's /app as one directory — the llama-server launcher, the
# libllama* / libggml* closure it links, and the ggml backends it dlopens (libggml-cuda.so, the
# libggml-cpu-* variants). Those files carry RUNPATH `/app/build/bin:` (the build tree, then an
# empty element, the working directory), so outside that image the closure loads only with
# LD_LIBRARY_PATH led by this directory; the probe launches lane B that way. The backends need
# no variable: ggml's registry searches the launcher's own directory. GGML_BACKEND_PATH names
# ONE extra backend library, loaded out loud — set to this directory it printed `load_backend:
# failed to load /opt/llama/bin: ... Is a directory` on every start (run 16), so no launch sets
# it; the bake points it at libggml-cuda.so once, to hear why that backend does not load on a
# GPU-less builder. Then the converter, its package and the pin files from the same commit.
COPY --from=llama /app/ /opt/llama/bin/
COPY --from=converter /opt/llama /opt/llama

# Fail fast, before torch and the model: the prebuilt server must report the pinned build and
# ggml's registry must refuse no backend on the way (the bake repeats both checks in Python with
# the commit and the digest file, codes llama_version_mismatch and llama_backend_load_failed).
RUN LD_LIBRARY_PATH="/opt/llama/bin:${LD_LIBRARY_PATH}" \
    /opt/llama/bin/llama-server --version 2>&1 | tee /opt/llama/VERSION \
    && grep -qE "^version: ${LLAMA_CPP_BUILD} \(" /opt/llama/VERSION \
    && ! grep -qE "load_backend: failed|ggml_backend_load_best: failed" /opt/llama/VERSION

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

# The packed-int8 captured-graph engine for the L4: `engine/` (the sm_89 build of
# qwen3_p3_graph_cuda with its runtime closure and manifest.json) is copied into this folder at
# deploy time only (DEPLOY.md; it is git-ignored, never committed) and lands with the app above.
# When present it is exposed at /home/user/engine, the path the Space variable
# ALGENTA_CUDA_ENGINE=/home/user/engine/qwen3_p3_graph_cuda names; absent, the resolver falls
# back to the wheel's engine and lane A keeps its sm_90a gate. A symlink, not a second copy.
# Files uploaded through the Hub arrive without their mode bits (run 17: the engine was present
# but `engine_selected_missing: … is not an executable file`), so the mode is set here, as root.
RUN if [ -d /app/engine ]; then chmod -R u=rwX,go=rX /app/engine \
    && chmod 0755 /app/engine/qwen3_p3_graph_cuda \
    && chown -R user:user /app/engine \
    && ln -sfn /app/engine /home/user/engine; fi
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/hf \
    PROBE_WORK_DIR=/home/user/work \
    PROBE_ASSETS_DIR=/home/user/assets \
    PROBE_BUILD_FACTS=/home/user/assets/build_facts.json

# Hugging Face exposes a Space variable to the build only when the Dockerfile declares it as a
# build argument: without this line the bake of run 16 described the wheel's sm_90a engine while
# the variable named the sm_89 driver above. Declared here — after the symlink exists and as the
# runtime user, the way the bake will resolve it — and kept as ENV so a container that gets no
# variable injected resolves the binary the bake recorded (the Space injects its own value at
# start; empty means unset and the wheel's engine is the default).
ARG ALGENTA_CUDA_ENGINE
ENV ALGENTA_CUDA_ENGINE=${ALGENTA_CUDA_ENGINE}

# Bake: the kernel at its pinned revision (cuda variant, tier 6144 asserted, tree listing pruned),
# the pinned Qwen3-0.6B-Base snapshot (about 1.2 GB), the facts of the engine selected above (or
# the wheel's), the prebuilt server's version against the pins, the backends and devices its
# registry finds, the converter's imports, and the F16 GGUF converted from that snapshot. Then
# prove everything resolves with the Hub unreachable.
RUN python fetch_assets.py --bake
RUN HF_HUB_OFFLINE=1 python fetch_assets.py --verify

ENV HF_HUB_OFFLINE=1
EXPOSE 7860
CMD ["python", "app.py"]
