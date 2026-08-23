#!/usr/bin/env bash
# The AMD ROCm COMPILE gate for the portable GPU kernel layer — the mirror of the CUDA
# compile gate (build-runtime.yml's build-linux-cuda job), executed inside the same
# amd64 ubuntu:22.04 container on the self-hosted macOS fleet (workspace mounted at /work).
#
# COMPILE-GATED lane — compile-verified, launch-UNVERIFIED: cross-compiling the portable
# kernels for AMD CDNA targets (`-D ALGENTA_GPU -D ALGENTA_ROCM --target-accelerator gfx*`)
# needs NO ROCm toolkit and NO AMD GPU — the AMDGPU LLVM backend ships inside the pinned
# mojo toolchain (`mojo build --print-supported-accelerators` lists the ROCm/HIP table),
# the same way NVPTX ships for the CUDA gate. Launching the result needs real MI300X /
# MI355X hardware with ROCm >= 6.3.3 (MI355X: ROCm 7), which the fleet does not have.
# The macOS build-host verdict this script mirrors is recorded in
# benchmarks/llm_smoke/REALRACE_RESULTS.md ("THE AMD ROCM COMPILE GATE").
set -euo pipefail
cd /work

# shellcheck source=_linux_container_bootstrap.sh
source "$(dirname "$0")/_linux_container_bootstrap.sh"

# ── Pixi + Mojo environment (mirrors build_runtime_linux_amd64.sh exactly) ──────────────────
export PIXI_HOME=/work/.pixi
export RATTLER_CACHE_DIR=/work/.cache/rattler/cache
curl -fsSL https://pixi.sh/install.sh | env PIXI_HOME="$PIXI_HOME" PIXI_BIN_DIR="$PIXI_HOME/bin" PIXI_NO_PATH_UPDATE=1 bash
export PATH="$PIXI_HOME/bin:$PATH"
pixi install --manifest-path mojo_env/pixi.toml

GATE=benchmarks/llm_smoke/amd_rocm_compile_gate.mojo
OUT=/work/mojo_build/amd-gate
mkdir -p "$OUT"

# ── The gate: one driver, every portable kernel family, per CDNA target ──────────────────────
# gfx942 = MI300X (CDNA3), gfx950 = MI355X (CDNA4). gfx90a (MI250X) rides along — it is the
# same kernel layer, and the accelerator table ships it for free.
for target in gfx942 gfx950 gfx90a; do
    echo "── AMD compile gate: --target-accelerator $target"
    pixi run --manifest-path mojo_env/pixi.toml \
        mojo build -D ALGENTA_GPU -D ALGENTA_ROCM --target-accelerator "$target" \
        -I mojo/engine "$GATE" -o "$OUT/amd_rocm_compile_gate_$target"
    # Evidence: the embedded device image must carry the requested amdgcn target.
    strings "$OUT/amd_rocm_compile_gate_$target" | grep -q "amdgcn-amd-amdhsa-unknown-$target"
    echo "OK: $target binary embeds amdgcn-amd-amdhsa-unknown-$target"
done

# The gate binary is NOT executed here: PART 0's host checks were verified on the macOS
# build host, and the device section needs the HIP runtime (Linux + ROCm) — the compile
# verdict is what this job produces. The binaries are upload-only artifacts.
OWNER="$(stat -c '%u:%g' /work/.git)"
chown -R "$OWNER" "$OUT" /work/.pixi /work/.cache 2>/dev/null || true
echo "AMD ROCm compile gate OK (gfx942 + gfx950 + gfx90a)"
