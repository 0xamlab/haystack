#!/usr/bin/env bash
# setup_vm.sh — provision a GCP Ubuntu-22.04 GPU VM for the NVIDIA race campaign.
#
# Stages (each idempotent; re-run after the stage-2 reboot):
#   1. apt basics (build tools, cmake, git, python)
#   2. NVIDIA driver via ubuntu-drivers --gpgpu + nvidia-utils (REBOOT REQUIRED)
#   3. CUDA toolkit via the NVIDIA cuda-keyring apt route (llama.cpp needs nvcc)
#   4. llama.cpp at the campaign pin (benchmarks/competitors/llama_cpp/UPSTREAM_COMMIT),
#      built with -DGGML_CUDA=ON
#   5. Qwen3-0.6B-Base from HF -> F16 GGUF (llama.cpp's own converter) + Q8_0 quant
#   6. pixi + the repo's pinned mojo_env (linux-64, mojo ==1.0.0 / max ==26.5.0)
#   7. algenta CUDA drivers (qwen3_generate_cuda + qwen3_bench_cuda gen=64/256)
#   8. /tmp/qwen3smoke manifest+blob via prepare_model_checkpoint()
#
# Usage (on the VM, from the repo root):
#   bash benchmarks/llm_smoke/nvidia_race/setup_vm.sh <sm_NN>
# where <sm_NN> is the accelerator arch for the algenta build (sm_80 A100 / sm_75 T4 / sm_89 L4).
set -euo pipefail

SM_TARGET="${1:-sm_80}"
export DEBIAN_FRONTEND=noninteractive
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LLAMA_PIN="000547513f1530346ecd163db8b3e13962949961"   # llama.cpp 10210 — the campaign pin
LLAMA_DIR="$HOME/llama.cpp"
MODELS_DIR="$HOME/models"
CKPT_DIR="$HOME/qwen3-0.6b-base"
ALGENTA_NV_DIR="$HOME/algenta_nv"

log() { echo "[setup_vm $(date -u +%H:%M:%S)] $*"; }

# ── stage 1: apt basics ──────────────────────────────────────────────────────
stage1() {
    if [[ -f /tmp/setup_vm_stage1.done ]]; then log "stage 1 cached"; return; fi
    log "stage 1: apt basics"
    sudo apt-get update -q
    sudo apt-get install -y -q build-essential cmake git wget curl python3-pip python3-venv \
        pkg-config libcurl4-openssl-dev
    touch /tmp/setup_vm_stage1.done
}

# ── stage 2: NVIDIA driver ───────────────────────────────────────────────────
stage2() {
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
        log "stage 2 cached: $(nvidia-smi -L | head -1)"
        return
    fi
    log "stage 2: NVIDIA driver (ubuntu-drivers --gpgpu) + nvidia-utils"
    sudo apt-get install -y -q ubuntu-drivers-common
    sudo ubuntu-drivers install --gpgpu
    # ubuntu-drivers --gpgpu on the GCP 22.04 image picks the headless server driver
    # (nvidia-headless-no-dkms-NNN-server-open) but does NOT always pull nvidia-utils,
    # which is what provides nvidia-smi. Detect the installed driver series and install
    # the matching nvidia-utils so the stage-2 cache check (nvidia-smi) can pass.
    local drv_series
    # Package-set detection, broadest first: the headless-server family installs different
    # package names per machine type (a2/A100 got libnvidia-compute-595-server; n1/T4 got
    # only nvidia-headless-no-dkms-595-server-open), so try every known spelling.
    drv_series="$(dpkg -l 2>/dev/null | grep -oE 'nvidia-kernel-source-[0-9]+' \
        | head -1 | grep -oE '[0-9]+$' || true)"
    if [[ -z "$drv_series" ]]; then
        drv_series="$(dpkg -l 2>/dev/null | grep -oE 'libnvidia-compute-[0-9]+' \
            | head -1 | grep -oE '[0-9]+$' || true)"
    fi
    if [[ -z "$drv_series" ]]; then
        drv_series="$(dpkg -l 2>/dev/null | grep -oE 'nvidia-headless-no-dkms-[0-9]+' \
            | head -1 | grep -oE '[0-9]+$' || true)"
    fi
    if [[ -z "$drv_series" ]]; then
        drv_series="$(dpkg -l 2>/dev/null | grep -oE 'linux-modules-nvidia-[0-9]+' \
            | head -1 | grep -oE '[0-9]+$' || true)"
    fi
    if [[ -n "$drv_series" ]] && ! command -v nvidia-smi >/dev/null 2>&1; then
        log "  nvidia-smi missing after driver install -> adding nvidia-utils-$drv_series"
        sudo apt-get install -y -q "nvidia-utils-$drv_series" || \
            sudo apt-get install -y -q "nvidia-utils-$drv_series-server" || true
    fi
    # g2/L4 gotcha (run-verified 2026-08-21): the prebuilt kernel module package can be left
    # config-only ("rc") by ubuntu-drivers, and the non-server userspace can conflict-remove
    # itself against the -server module version. Explicitly install BOTH halves for the
    # running kernel's series if the module or userspace is missing after the reboot.
    if ! find "/lib/modules/$(uname -r)" -name 'nvidia.ko*' 2>/dev/null | grep -q .; then
        log "  nvidia.ko missing for $(uname -r) -> installing matching module package"
        sudo apt-get install -y -q "linux-modules-nvidia-${drv_series}-server-open-$(uname -r)" || true
    fi
    log "stage 2 done — REBOOT REQUIRED; re-run this script after reboot"
}

# ── stage 3: CUDA toolkit (nvcc for the llama.cpp CUDA build) ────────────────
stage3() {
    if command -v nvcc >/dev/null 2>&1; then log "stage 3 cached: $(nvcc --version | tail -1)"; return; fi
    log "stage 3: CUDA toolkit via cuda-keyring"
    wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
        -O /tmp/cuda-keyring.deb
    sudo dpkg -i /tmp/cuda-keyring.deb
    sudo apt-get update -q
    sudo apt-get install -y -q cuda-toolkit-12-6
    echo 'export PATH=/usr/local/cuda-12.6/bin:$PATH' | sudo tee /etc/profile.d/cuda.sh >/dev/null
    log "stage 3 done"
}

# ── stage 4: llama.cpp at the campaign pin, CUDA build ───────────────────────
stage4() {
    if [[ -x "$LLAMA_DIR/build/bin/llama-bench" && -x "$LLAMA_DIR/build/bin/llama-server" ]]; then
        log "stage 4 cached"; return
    fi
    log "stage 4: llama.cpp @ $LLAMA_PIN with GGML_CUDA=ON"
    rm -rf "$LLAMA_DIR"
    # Pinned-commit source tarball (auditable: exact SHA, same pin as
    # benchmarks/competitors/llama_cpp/UPSTREAM_COMMIT) — faster than a full clone.
    wget -q "https://github.com/ggml-org/llama.cpp/archive/${LLAMA_PIN}.tar.gz" \
        -O /tmp/llama_cpp_pin.tar.gz
    mkdir -p "$LLAMA_DIR"
    tar -xzf /tmp/llama_cpp_pin.tar.gz -C "$LLAMA_DIR" --strip-components=1
    echo "$LLAMA_PIN  (source tarball)" > "$LLAMA_DIR/ALGENTA_RACE_PIN"
    export PATH=/usr/local/cuda-12.6/bin:$PATH
    # Build ONLY for this VM's GPU arch — llama.cpp's default compiles every CUDA object
    # for ~7 architectures, which costs ~7x the nvcc time (measured: all-arch build sat at
    # ~30% for 25 min on 12 cores before this pin was added). The race runs on this one
    # GPU; the arch pin is stated in the ledger entry.
    local cuda_arch="${SM_TARGET#sm_}"
    cmake -B "$LLAMA_DIR/build" -S "$LLAMA_DIR" -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CUDA_ARCHITECTURES="${cuda_arch}-real" -DLLAMA_CURL=OFF \
        >/tmp/llama_cmake.log 2>&1 || { tail -40 /tmp/llama_cmake.log; exit 1; }
    cmake --build "$LLAMA_DIR/build" --config Release -j"$(nproc)" \
        --target llama-bench llama-cli llama-completion llama-quantize llama-server \
        >/tmp/llama_build.log 2>&1 \
        || { tail -40 /tmp/llama_build.log; exit 1; }
    log "stage 4 done: $("$LLAMA_DIR/build/bin/llama-cli" --version 2>&1 | head -1)"
}

# ── stage 5: model — HF checkpoint -> F16 GGUF + Q8_0 ────────────────────────
stage5() {
    mkdir -p "$MODELS_DIR"
    if [[ -f "$MODELS_DIR/qwen3-0.6b-f16.gguf" && -f "$MODELS_DIR/qwen3-0.6b-q8_0.gguf" ]]; then
        log "stage 5 cached"; return
    fi
    log "stage 5: Qwen3-0.6B-Base download + GGUF conversion"
    python3 -m pip install --quiet --user huggingface_hub numpy sentencepiece
    if [[ ! -f "$CKPT_DIR/config.json" ]]; then
        # snapshot_download API instead of the CLI module path — the -m invocation target
        # moved across huggingface_hub versions and broke on the A100 VM (2026-08-20).
        python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3-0.6B-Base', local_dir='$CKPT_DIR')
"
    fi
    if [[ ! -f "$MODELS_DIR/qwen3-0.6b-f16.gguf" ]]; then
        if ! python3 "$LLAMA_DIR/convert_hf_to_gguf.py" "$CKPT_DIR" --outtype f16 \
            --outfile "$MODELS_DIR/qwen3-0.6b-f16.gguf"; then
            # convert_hf_to_gguf.py imports torch (and for Qwen3, transformers). CPU-only
            # torch keeps the install small — conversion is a CPU data-prep step, and the
            # CUDA build of llama.cpp does NOT need torch at runtime.
            log "  converter missing deps; installing CPU torch + transformers and retrying"
            python3 -m pip install --quiet --user torch --index-url https://download.pytorch.org/whl/cpu
            python3 -m pip install --quiet --user transformers
            python3 "$LLAMA_DIR/convert_hf_to_gguf.py" "$CKPT_DIR" --outtype f16 \
                --outfile "$MODELS_DIR/qwen3-0.6b-f16.gguf"
        fi
    fi
    if [[ ! -f "$MODELS_DIR/qwen3-0.6b-q8_0.gguf" ]]; then
        "$LLAMA_DIR/build/bin/llama-quantize" "$MODELS_DIR/qwen3-0.6b-f16.gguf" \
            "$MODELS_DIR/qwen3-0.6b-q8_0.gguf" Q8_0
    fi
    log "stage 5 done"
}

# ── stage 6: pixi + pinned mojo_env ───────────────────────────────────────────
stage6() {
    if [[ -d "$REPO_ROOT/mojo_env/.pixi/envs/default" ]]; then log "stage 6 cached"; return; fi
    log "stage 6: pixi + mojo_env (linux-64, from the repo lock)"
    if ! command -v pixi >/dev/null 2>&1; then
        curl -fsSL https://pixi.sh/install.sh | bash
        export PATH="$HOME/.pixi/bin:$PATH"
    fi
    pixi install --frozen --manifest-path "$REPO_ROOT/mojo_env/pixi.toml"
    log "stage 6 done"
}

# ── stage 7: algenta CUDA drivers ────────────────────────────────────────────
# Plain `mojo build` first; if the pinned toolchain does not auto-link the MAX CUDA runtime,
# fall back to the documented object+link recipe from residentk_cuda_smoke.mojo's docstring:
#   mojo build ... --emit object -o prog.o
#   clang prog.o -o prog -L <max-lib> -Wl,-rpath,<max-lib> \
#       -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \
#       -lAsyncRTMojoBindings -lMGPRT libpython3.14.so -lstdc++ -ldl -lpthread -lm
# TC escape hatch (feat/tc-int): when a driver's flags carry -D ALGENTA_TC_SHIM, the nvcc
# shim object is compiled once for this SM target and linked in (plain build: -Xlinker;
# object+link fallback: on the clang line). Flag-off builds take NONE of this — their link
# line stays byte-unmodified.
tc_shim_object() {
    local obj="/tmp/tc_shim_${SM_TARGET}.o"
    local hdr_dir="/tmp/tc_shim_build_${SM_TARGET}"
    if [[ ! -f "$obj" ]]; then
        mkdir -p "$hdr_dir"
        if [[ ! -f "$hdr_dir/tc_rt_ptx.h" ]]; then
            # the shim #includes the embedded-PTX header (build_tc_probe.sh's recipe):
            # tc_rt_kernels.cu -> compute_80 PTX -> C array, driver-JIT'd per GPU at load.
            log "  nvcc tc_rt_kernels.cu -> embedded PTX header"
            /usr/local/cuda/bin/nvcc -ptx -arch=compute_80 \
                "$REPO_ROOT/benchmarks/llm_smoke/nvidia_race/tc_rt_kernels.cu" \
                -o "$hdr_dir/tc_rt_kernels.ptx"
            python3 - "$hdr_dir/tc_rt_kernels.ptx" "$hdr_dir/tc_rt_ptx.h" <<'PY'
import sys

src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
chunks = []
for i in range(0, len(data), 24):
    chunks.append(",".join(str(b) for b in data[i : i + 24]))
with open(dst, "w") as out:
    out.write("/* generated by setup_vm.sh — embedded PTX */\n")
    out.write("static const unsigned char g_tc_rt_ptx[] = {\n")
    out.write(",\n".join(chunks))
    out.write(",0};\n")
PY
        fi
        log "  nvcc tc_shim.cu -> $obj"
        /usr/local/cuda/bin/nvcc -O3 -arch="$SM_TARGET" -Xcompiler -fPIC \
            -I "$hdr_dir" \
            -c "$REPO_ROOT/benchmarks/llm_smoke/nvidia_race/tc_shim.cu" -o "$obj"
    fi
    echo "$obj"
}

build_one_driver() {
    local mojo="$1"; shift
    local out="$1"; shift
    local src="$1"; shift
    local want_tc=0
    local a
    for a in "$@"; do
        if [[ "$a" == "ALGENTA_TC_SHIM" ]]; then want_tc=1; fi
    done
    local tc_link=()
    local tc_obj=""
    if [[ "$want_tc" == "1" ]]; then
        tc_obj="$(tc_shim_object)"
        tc_link=(-Xlinker "$tc_obj" -Xlinker -lcublas -Xlinker -lcudart \
                 -Xlinker -L/usr/local/cuda/lib64)
    fi
    if "$mojo" build "$@" ${tc_link[@]+"${tc_link[@]}"} --target-accelerator "$SM_TARGET" \
        -I "$REPO_ROOT/mojo/engine" "$src" -o "$out" 2>/tmp/mojo_build_err.log; then
        log "  built $(basename "$out") (plain build)"
        return 0
    fi
    log "  plain build failed, trying object+link recipe: $(tail -3 /tmp/mojo_build_err.log | head -1)"
    local env_dir="$REPO_ROOT/mojo_env/.pixi/envs/default"
    local max_lib
    max_lib="$(dirname "$(find "$env_dir" -name 'libMGPRT.so' | head -1)")"
    local pylib="$env_dir/lib/libpython3.14.so"
    "$mojo" build "$@" --target-accelerator "$SM_TARGET" \
        -I "$REPO_ROOT/mojo/engine" "$src" --emit object -o "$out.o" \
        || { tail -30 /tmp/mojo_build_err.log; return 1; }
    local tc_clang=()
    if [[ "$want_tc" == "1" ]]; then
        tc_clang=("$tc_obj" -L/usr/local/cuda/lib64 -Wl,-rpath,/usr/local/cuda/lib64
                  -lcublas -lcudart)
    fi
    clang "$out.o" ${tc_clang[@]+"${tc_clang[@]}"} -o "$out" \
        -L "$max_lib" -Wl,-rpath,"$max_lib" \
        -lKGENCompilerRTShared -lAsyncRTRuntimeGlobals -lMSupportGlobals \
        -lAsyncRTMojoBindings -lMGPRT "$pylib" -lstdc++ -ldl -lpthread -lm \
        || return 1
    log "  built $(basename "$out") (object+link recipe)"
}

stage7() {
    log "stage 7: algenta CUDA drivers for $SM_TARGET"
    export PATH="$HOME/.pixi/bin:$PATH"
    local env_dir="$REPO_ROOT/mojo_env/.pixi/envs/default"
    export MODULAR_HOME="$env_dir/share/max"
    local mojo="$env_dir/bin/mojo"
    mkdir -p "$ALGENTA_NV_DIR"
    # LEVER L-H3 (H100 autopsy, 2026-08-23): the batch-1 prefill gets the serve driver's
    # L1/L2 twins — flash-style M-parallel attention + one-pass M-parallel GEMM grids
    # (session_cuda's CUDA_PREFILL_ONEPASS_B1/CUDA_PREFILL_FLASH_B1). Measured on H100:
    # fixture prefill 50.96 -> 29.43 ms = 1.73x (5023 -> 8698 tok/s), 16/16 oracle PASS,
    # full-sequence token identity PASS vs the flag-off path. LEVER L-H4 adds the
    # latency-pipelined flash twin (bit-identical, 1.16-1.36x on the attention kernel).
    # Flag-off builds stay the A/B control (the flags are comptime-removed when absent).
    local B1_PF_FLAGS=(-D ALGENTA_PF_ONEPASS_B1 -D ALGENTA_PF_ATTN_FLASH_B1 \
        -D ALGENTA_PF_ATTN_FLASH2_B1)
    build_one_driver "$mojo" "$ALGENTA_NV_DIR/qwen3_bench_cuda_gen64" \
        "$REPO_ROOT/benchmarks/llm_smoke/qwen3_bench_cuda.mojo" -D ALGENTA_GPU -D ALGENTA_CUDA \
        "${B1_PF_FLAGS[@]}"
    build_one_driver "$mojo" "$ALGENTA_NV_DIR/qwen3_bench_cuda_gen256" \
        "$REPO_ROOT/benchmarks/llm_smoke/qwen3_bench_cuda.mojo" \
        -D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_GEN_256 "${B1_PF_FLAGS[@]}"
    build_one_driver "$mojo" "$ALGENTA_NV_DIR/qwen3_generate_cuda" \
        "$REPO_ROOT/benchmarks/llm_smoke/qwen3_generate_cuda.mojo" -D ALGENTA_GPU -D ALGENTA_CUDA \
        "${B1_PF_FLAGS[@]}"
    log "stage 7 done"
}

# ── stage 8: /tmp/qwen3smoke manifest + blob ─────────────────────────────────
stage8() {
    if [[ -f /tmp/qwen3smoke/manifest.json && -f /tmp/qwen3smoke/weights.blob ]]; then
        log "stage 8 cached"; return
    fi
    log "stage 8: prepare_model_checkpoint -> /tmp/qwen3smoke"
    export PATH="$HOME/.pixi/bin:$PATH"
    "$REPO_ROOT/mojo_env/.pixi/envs/default/bin/python" \
        "$REPO_ROOT/benchmarks/llm_smoke/nvidia_race/prepare_smoke_checkpoint.py" "$CKPT_DIR"
    log "stage 8 done"
}

stage1
stage2
if ! nvidia-smi -L >/dev/null 2>&1; then
    log "nvidia-smi not live yet — reboot now if the driver was just installed"
    exit 0
fi
stage3
stage4
stage5
stage6
stage7
stage8
log "ALL STAGES DONE for $SM_TARGET"
