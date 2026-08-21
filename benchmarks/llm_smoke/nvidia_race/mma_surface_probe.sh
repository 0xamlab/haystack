#!/usr/bin/env bash
# mma_surface_probe.sh — the DEFINITIVE compile-level battery: does Mojo 1.0.0 / MAX 26.5 expose
# ANY tensor-core (mma/wgmma) surface, an f16/i8 SIMD arithmetic surface, or an inline-asm escape
# hatch on the NVPTX target? Each probe is a minimal .mojo file compiled with
# `--target-accelerator sm_80` (the A100 arch); compile PASS = the surface exists at the compiler
# level, compile FAIL + first error line = the evidence of absence. Runtime confirmation of any
# PASS happens on the A100 VM; a compile FAIL is already definitive for "no routeable surface".
#
# Usage (works on the macOS build host — NVPTX ships in the toolchain, no GPU needed):
#   bash benchmarks/llm_smoke/nvidia_race/mma_surface_probe.sh
set -u
ENV="${ENV:-$(pwd)/mojo_env/.pixi/envs/default}"
MOJO="$ENV/bin/mojo"
export MODULAR_HOME="$ENV/share/max"
OUT="$(mktemp -d /tmp/mma_probe.XXXXXX)"
PASS=0
FAIL=0

probe() {
    local name="$1"; shift
    local src="$OUT/$name.mojo"
    cat > "$src"
    if "$MOJO" build "$src" --target-accelerator sm_80 -o "$OUT/$name" >"$OUT/$name.log" 2>&1; then
        echo "  COMPILE-PASS  $name"
        PASS=$((PASS + 1))
    else
        local err
        err="$(grep -m1 'error:' "$OUT/$name.log" | head -1)"
        echo "  COMPILE-FAIL  $name | $err"
        FAIL=$((FAIL + 1))
    fi
}

echo "mma_surface_probe: mojo $("$MOJO" --version 2>/dev/null | head -1), target sm_80"

# ── module-level tensor-core candidates ──
probe import_std_gpu_mma <<'EOF'
import std.gpu.mma
def main(): pass
EOF

probe import_std_gpu_primitives_mma <<'EOF'
import std.gpu.primitives.mma
def main(): pass
EOF

probe import_max_gpu_mma <<'EOF'
import max.gpu.mma
def main(): pass
EOF

probe import_max_gpu_tensor_core <<'EOF'
import max.gpu.tensor_core
def main(): pass
EOF

probe import_std_tensor_core <<'EOF'
import std.tensor_core
def main(): pass
EOF

probe import_max_gpu_tma <<'EOF'
import max.gpu.tma
def main(): pass
EOF

probe import_std_gpu_tma <<'EOF'
import std.gpu.tma
def main(): pass
EOF

# ── name-level candidates inside known modules ──
probe name_max_gpu_mma <<'EOF'
from max.gpu import mma
def main(): pass
EOF

probe name_std_gpu_mma <<'EOF'
from std.gpu import mma
def main(): pass
EOF

probe name_std_gpu_mma_sync <<'EOF'
from std.gpu import mma_sync
def main(): pass
EOF

probe name_max_gpu_host_mma <<'EOF'
from max.gpu.host import mma
def main(): pass
EOF

# ── inline asm escape hatch candidates ──
probe asm_std_sys <<'EOF'
from std.sys import inline_asm
def main(): pass
EOF

probe asm_builtin_call <<'EOF'
def main():
    var x = __builtin_asm("mov.u32 $0, 0;", "", 0)
    _ = x
EOF

# ── f16 / i8 SIMD arithmetic in a GPU kernel (the f16_vec8_probe's compile-level twin).
#    The kernel is enqueued from main so shader codegen actually lowers it for sm_80 —
#    an unreachable kernel function would compile vacuously and prove nothing. ──
probe kernel_f16_simd_arith <<'EOF'
from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin

def _k(dst: UnsafePointer[Float32, origin=MutAnyOrigin]):
    var a = SIMD[DType.float16, 8](Float16(1.0))
    var b = SIMD[DType.float16, 8](Float16(2.0))
    var c = a * b + a
    var s = Float32(0.0)
    for i in range(8):
        s += Float32(c[i])
    dst[Int(thread_idx.x)] = s

def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.float32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
EOF

probe kernel_i8_simd_dot <<'EOF'
from std.gpu import thread_idx
from max.gpu.host import DeviceContext
from std.origin import MutAnyOrigin

def _k(dst: UnsafePointer[Int32, origin=MutAnyOrigin]):
    var a = SIMD[DType.int8, 16](Int8(1))
    var b = SIMD[DType.int8, 16](Int8(2))
    var s = Int32(0)
    for i in range(16):
        s += Int32(a[i]) * Int32(b[i])
    dst[Int(thread_idx.x)] = s

def main() raises:
    var ctx = DeviceContext()
    var buf = ctx.enqueue_create_buffer[DType.int32](32)
    ctx.enqueue_function[_k](buf.unsafe_ptr(), grid_dim=1, block_dim=32)
    ctx.synchronize()
EOF

echo "mma_surface_probe: $PASS compile-pass, $FAIL compile-fail (logs in $OUT)"
