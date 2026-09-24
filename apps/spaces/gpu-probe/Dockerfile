# Algenta GPU probe (thyn-ai/algenta-gpu-probe): the published single-stream race, live on a
# Hugging Face GPU Space. Lane A is the CUDA engine bundled in the algenta-runtime-native wheel
# (conform_generate_cuda), lane B is llama.cpp built here with GGML_CUDA at the benchmark pages'
# pinned commit, both on Qwen3-0.6B-Base, the same 256-token prompt, gen=64; the Hub kernels'
# f32 parity path and plain transformers run beside them. Source of truth: apps/spaces/gpu-probe
# in the Algenta repository; docs/spaces/GPU-PROBE.md is the runbook.
#
# Stage 1 (llama-build): the CUDA 12.8 devel image, pinned by digest, compiles llama-server for
# sm_89 (the L4) from the pinned commit, statically linked against its own ggml/llama libraries
# (dynamically against cudart/cublas, which the runtime image provides); the GGUF converter and
# its gguf-py package are carried along for the bake. Nothing of the toolchain reaches the
# runtime image.
#
# Stage 2 (runtime): the CUDA 12.8 runtime on Ubuntu 24.04, pinned by digest (multi-arch index;
# the Hub builds amd64). Its NVIDIA_REQUIRE_CUDA driver-branch list predates driver 580 and
# would refuse the Hub's host driver at container start, so NVIDIA_DISABLE_REQUIRE=1 turns that
# check off — the probe's own driver phase applies the real floor (580) instead.
#
# Python: CPython 3.14 through uv (also pinned by digest). `algenta` and `algenta-runtime-native`
# ship CPython 3.14 wheels only; torch 2.9.1+cu128 has cp314 wheels on the PyTorch index.
#
# Assets: fetch_assets.py --bake installs the kernel snapshot (pinned revision, cuda variant,
# native manifest checked for the 6144 staging tier) and the pinned Qwen3-0.6B-Base snapshot
# into HF_HOME as the runtime user, reads the wheel's signed engine manifest, and converts the
# snapshot to the F16 GGUF; --verify then proves, with HF_HUB_OFFLINE=1, that everything
# resolves locally. The runtime keeps HF_HUB_OFFLINE=1, so boot never downloads. Set the Space
# variable HF_HUB_OFFLINE=0 to let get_kernel reach the Hub instead (a host without the cache).
# The f64 conversion (about 4.8 GB) happens at boot on the Space's disk, not in the image.
ARG LLAMA_CPP_COMMIT=000547513f1530346ecd163db8b3e13962949961
ARG LLAMA_CUDA_ARCHITECTURES=89

FROM nvidia/cuda:12.8.1-devel-ubuntu24.04@sha256:520292dbb4f755fd360766059e62956e9379485d9e073bbd2f6e3c20c270ed66 AS llama-build

ARG LLAMA_CPP_COMMIT
ARG LLAMA_CUDA_ARCHITECTURES
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends git cmake ninja-build build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# A shallow fetch of exactly the pinned commit (the tag b10210 the serving page names).
RUN git init -q /opt/llama.cpp \
    && cd /opt/llama.cpp \
    && git remote add origin https://github.com/ggml-org/llama.cpp.git \
    && git fetch -q --depth 1 origin "${LLAMA_CPP_COMMIT}" \
    && git checkout -q FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}"

# GGML_CUDA for the requested architecture only; no native CPU tuning (the builder's CPU is not
# the Space's); no shared ggml/llama libraries to carry; no tests, examples or HTTPS client.
RUN cmake -S /opt/llama.cpp -B /opt/llama.cpp/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES="${LLAMA_CUDA_ARCHITECTURES}" \
        -DGGML_NATIVE=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DLLAMA_OPENSSL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        -DLLAMA_BUILD_TOOLS=ON \
        -DLLAMA_BUILD_SERVER=ON \
    && cmake --build /opt/llama.cpp/build --target llama-server -j"$(nproc)" \
    && mkdir -p /opt/llama/bin \
    && cp /opt/llama.cpp/build/bin/llama-server /opt/llama/bin/llama-server \
    && cp /opt/llama.cpp/convert_hf_to_gguf.py /opt/llama/convert_hf_to_gguf.py \
    && cp -r /opt/llama.cpp/conversion /opt/llama/conversion \
    && cp -r /opt/llama.cpp/gguf-py /opt/llama/gguf-py \
    && echo "${LLAMA_CPP_COMMIT}" > /opt/llama/COMMIT \
    && echo "${LLAMA_CUDA_ARCHITECTURES}" > /opt/llama/CUDA_ARCHITECTURES

FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04@sha256:ebef3c171eeef0298e4eb2e4be843105edf3b8b0ac45e0b43acee358e8046867

ENV NVIDIA_DISABLE_REQUIRE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_NO_CACHE=1

# libgomp1: the signed algenta native runtime and ggml link OpenMP. ca-certificates: the Hub
# over TLS. The CUDA runtime image provides libcublas.so.12 / libcublasLt.so.12, the host
# libraries the bundled engine and llama-server link; libcudart.so.12 ships in the wheel beside
# the engine and in the image for llama-server.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc /uv /uvx /bin/

# The opponent, built above: the server binary, the converter and its package.
COPY --from=llama-build /opt/llama /opt/llama

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
RUN if [ -d /app/engine ]; then ln -sfn /app/engine /home/user/engine; fi
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/hf \
    PROBE_WORK_DIR=/home/user/work \
    PROBE_ASSETS_DIR=/home/user/assets \
    PROBE_BUILD_FACTS=/home/user/assets/build_facts.json

# Bake: the kernel at its pinned revision (cuda variant, tier 6144 asserted, tree listing pruned),
# the pinned Qwen3-0.6B-Base snapshot (about 1.2 GB), the wheel's engine facts, and the F16 GGUF
# converted from that snapshot. Then prove everything resolves with the Hub unreachable.
RUN python fetch_assets.py --bake
RUN HF_HUB_OFFLINE=1 python fetch_assets.py --verify

ENV HF_HUB_OFFLINE=1
EXPOSE 7860
CMD ["python", "app.py"]
