#!/usr/bin/env bash
# packed_int8_phase0.sh — phase-0 compile battery for arithmetic-packed-int8 weights on the
# CUDA lane: 3 unsigned int8 quants packed per Float32 word (v = b0 + 256*b1 + 65536*b2,
# exact because < 2^24), streamed via the proven 128-bit float4 load path and unpacked
# on-device. The ONE open question is which unpack primitive lowers for the NVPTX target on
# the pinned toolchain (mojo 1.0.0 / MAX 26.5.0). Each probe is a minimal .mojo kernel in
# this directory, compiled EXACTLY like mma_surface_probe.sh (`mojo build <src>
# --target-accelerator <arch> -o <out>`) for sm_80 (A100) and sm_89 (L4/4090); compile
# PASS = the primitive lowers at the compiler level, compile FAIL + first error line = the
# evidence of absence. Kernels are enqueued from main so shader codegen actually lowers them
# — an unreachable kernel would compile vacuously and prove nothing.
#
# Probes (recipe -> primitive):
#   p1_r1_floor_trunc           R1 floor-recipe   std.math.floor/trunc(Float32) unpack
#   p2a_r2_scalar_int32_cast    R2 Int32-cast     scalar Int32(Float32 var) conversion
#   p2b_r2_simd_cast_int32      R2 Int32-cast     SIMD[DType.float32,4].cast[DType.int32]()
#   p3a_r3_bitcast_i32_unpack   R3 unsafe_bitcast SIMD[float32,4] -> SIMD[int32,4] (1.0.0b2 spelling)
#   p3b_r3_bitcast_u8_unpack    R3 unsafe_bitcast SIMD[float32,4] -> SIMD[uint8,16] (1.0.0b2 spelling)
#   p3a2_r3_std_bitcast_i32     R3 std.memory.bitcast[int32,4] (the mojo 1.0.0 successor) + &/>> unpack
#   p3b2_r3_std_bitcast_u8      R3 std.memory.bitcast[uint8,16] (the mojo 1.0.0 successor) byte view
#   p3c_r3_std_bitcast_f16_ctrl control: f16_vec8_probe's proven direction in the 1.0.0 spelling
#   p4_control_int32_chain      control (MUST pass): scalar Int32 &, >>, % chains
#
# Usage (works on the macOS build host — NVPTX ships in the toolchain, no GPU needed):
#   bash benchmarks/llm_smoke/nvidia_race/packed_int8_phase0.sh
set -u
ENV="${ENV:-$(pwd)/mojo_env/.pixi/envs/default}"
if [ ! -x "$ENV/bin/mojo" ]; then
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
    ENV="$REPO_ROOT/mojo_env/.pixi/envs/default"
fi
MOJO="$ENV/bin/mojo"
export MODULAR_HOME="$ENV/share/max"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$(mktemp -d /tmp/packed_int8_phase0.XXXXXX)"
ARCHS="sm_80 sm_89"
PASS=0
FAIL=0

probe() {
    local name="$1"; shift
    local src="$DIR/$name.mojo"
    if [ ! -f "$src" ]; then
        echo "  COMPILE-FAIL  $name | missing probe source $src"
        FAIL=$((FAIL + 1))
        return
    fi
    for ARCH in $ARCHS; do
        if "$MOJO" build "$src" --target-accelerator "$ARCH" -o "$OUT/${name}_${ARCH}" \
            >"$OUT/${name}_${ARCH}.log" 2>&1; then
            echo "  COMPILE-PASS  $name [$ARCH]"
            PASS=$((PASS + 1))
        else
            local err
            err="$(grep -m1 'error:' "$OUT/${name}_${ARCH}.log" | head -1)"
            echo "  COMPILE-FAIL  $name [$ARCH] | $err"
            FAIL=$((FAIL + 1))
        fi
    done
}

echo "packed_int8_phase0: mojo $("$MOJO" --version 2>/dev/null | head -1), targets: $ARCHS"

probe p1_r1_floor_trunc
probe p2a_r2_scalar_int32_cast
probe p2b_r2_simd_cast_int32
probe p3a_r3_bitcast_i32_unpack
probe p3b_r3_bitcast_u8_unpack
probe p3a2_r3_std_bitcast_i32
probe p3b2_r3_std_bitcast_u8
probe p3c_r3_std_bitcast_f16_control
probe p4_control_int32_chain

echo "packed_int8_phase0: $PASS compile-pass, $FAIL compile-fail (logs in $OUT)"
