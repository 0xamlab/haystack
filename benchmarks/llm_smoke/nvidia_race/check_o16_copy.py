#!/usr/bin/env python3
"""check_o16_copy.py — drift check for FRONT 7's duplicated FA2 kernel.

`_fa2_causal_o16_kernel` (the f16-O twin, `-D ALGENTA_TC_SHIM_O16`) is a COPY of the shipped
`_fa2_causal_kernel`, not a second wrapper over a shared body. It is a copy because the shared-body
refactor this lever first tried was REJECTED by measurement: extracting the body into a `static
__device__ __forceinline__` template moved the SASS of all seven shipped instantiations (same 1272
instructions, same register count, four rescheduled around an out-of-lined CALL.REL), and `.text`/
`.rodata`/`.data`/`.bss` plus all 174 defined symbols stayed identical — so a host-section-only
neutrality proof would have passed a change that moved the baseline's device code. FRONT 5 measured
what a "harmless" codegen move costs here: a defaulted `__launch_bounds__` parameter moved one
instantiation from 155 to 171 registers, dropped it from 3 CTAs/SM to 2, and cost +9.8% on the
RAG-4096 FA block.

A copy buys baseline neutrality at the price of drift: someone fixes a bug in one kernel and not the
other, and the twin silently stops being the shipped kernel plus an epilogue. This script makes
that a checked invariant instead of a comment. It re-derives the twin from the shipped kernel by
applying EXACTLY the four documented differences and fails if the in-tree twin is not what the
derivation produces:

  1. name        `_fa2_causal_kernel` -> `_fa2_causal_o16_kernel`
  2. parameters  + `__half* __restrict__ og16`, + `int rev_rows`
  3. row index   `blockIdx.x` -> optionally reversed by `rev_rows` (bit-exact: each CTA computes
                 its own rows and reads no other CTA's output)
  4. epilogue    the f32 store becomes conditional (`og` is NULL in the ship arm) and an f16 twin
                 store is added at the identical rounding point

Usage: check_o16_copy.py [path/to/tc_shim.cu]     (exit 0 = in sync, 1 = drifted)
"""

from __future__ import annotations

import difflib
import sys

KSIG_SHIP = ("template <int BN, int PMMA, int DBUF>\n"
             "__global__ void __launch_bounds__(FA_NWARP * 32)\n_fa2_causal_kernel(")
KSIG_TWIN = ("template <int BN, int PMMA, int DBUF>\n"
             "__global__ void __launch_bounds__(FA_NWARP * 32)\n_fa2_causal_o16_kernel(")
O16_HEADER = "\n#ifdef ALGENTA_TC_SHIM_O16\n// \u2550"
O16_END = "#endif  // ALGENTA_TC_SHIM_O16"

SIG_OLD = """_fa2_causal_kernel(const float* __restrict__ qg, const __half* __restrict__ kg,
                   const __half* __restrict__ vg, float* __restrict__ og,
                   const float* __restrict__ scalep, int m, int n_keys, int h_q, int h_kv, int d,
                   int pos_base) {"""
SIG_NEW = """_fa2_causal_o16_kernel(const float* __restrict__ qg, const __half* __restrict__ kg,
                       const __half* __restrict__ vg, float* __restrict__ og,
                       __half* __restrict__ og16, const float* __restrict__ scalep, int m,
                       int n_keys, int h_q, int h_kv, int d, int pos_base, int rev_rows) {"""

QI_OLD = "    const int qi = blockIdx.x;\n"
QI_NEW = ("    // FRONT 7: `rev_rows` reverses the row-block dispatch order (heaviest-CTA-first).\n"
          "    // Bit-exact either way — each CTA computes its own rows and reads no other CTA's\n"
          "    // output — and it is a runtime argument, so the two orders are the SAME binary\n"
          "    // and their A/B cannot be confounded by codegen.\n"
          "    const int qi = rev_rows ? ((int)gridDim.x - 1 - (int)blockIdx.x)\n"
          "                              : (int)blockIdx.x;\n")

EPI_OLD = """#pragma unroll
    for (int nt = 0; nt < FA_D / 8; nt++) {
        const int c = nt * 8 + chi;
        if (w0) *reinterpret_cast<float2*>(og + (size_t)r0g * qld + h * d + c) =
                    make_float2(oacc[nt][0] * inv0, oacc[nt][1] * inv0);
        if (w1) *reinterpret_cast<float2*>(og + (size_t)r1g * qld + h * d + c) =
                    make_float2(oacc[nt][2] * inv1, oacc[nt][3] * inv1);
    }
}
"""
EPI_NEW = """#pragma unroll
    for (int nt = 0; nt < FA_D / 8; nt++) {
        const int c = nt * 8 + chi;
        // ── THE ONLY NUMERIC DIFFERENCE FROM `_fa2_causal_kernel`, and it is not a numeric
        //    difference at all: the same two f32 accumulator products, rounded to nearest-even
        //    halves by `__floats2half2_rn` — the identical operation `__float2half` performs, so
        //    the twin holds bit-for-bit what `_f32_to_f16_kernel` would have produced from the
        //    f32 this kernel would otherwise have stored. `og` is NULL in the ship arm (the 58.7
        //    MB/layer f32 write existed only to feed that convert) and non-NULL in the verify
        //    arm, which is what gives `tc_shim_verify_o16` something to compare against.
        //    The twin's row stride in HALVES is `qld` (= h_q*d = n_q): the identical
        //    position-major layout the convert wrote into `tc_a16`, so `_tc_gemm_f16_32c_pre`
        //    consumes it unchanged. The half2 store is 4-byte aligned because `c = nt*8 + chi`
        //    is even and `h*d` is a multiple of 128. ──
        if (og != nullptr) {
            if (w0) *reinterpret_cast<float2*>(og + (size_t)r0g * qld + h * d + c) =
                        make_float2(oacc[nt][0] * inv0, oacc[nt][1] * inv0);
            if (w1) *reinterpret_cast<float2*>(og + (size_t)r1g * qld + h * d + c) =
                        make_float2(oacc[nt][2] * inv1, oacc[nt][3] * inv1);
        }
        if (w0) *reinterpret_cast<__half2*>(og16 + (size_t)r0g * qld + h * d + c) =
                    __floats2half2_rn(oacc[nt][0] * inv0, oacc[nt][1] * inv0);
        if (w1) *reinterpret_cast<__half2*>(og16 + (size_t)r1g * qld + h * d + c) =
                    __floats2half2_rn(oacc[nt][2] * inv1, oacc[nt][3] * inv1);
    }
}
"""


def derive(shipped: str) -> str:
    out = shipped
    for old, new, what in ((SIG_OLD, SIG_NEW, "signature"),
                           (QI_OLD, QI_NEW, "row-block index"),
                           (EPI_OLD, EPI_NEW, "epilogue")):
        if old not in out:
            raise SystemExit(f"O16_COPY_DRIFT FAIL — the shipped kernel's {what} text moved; "
                             "this script's expectation is stale, re-derive the twin by hand "
                             "and update it (do NOT hand-edit the twin alone)")
        out = out.replace(old, new, 1)
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "benchmarks/llm_smoke/nvidia_race/tc_shim.cu"
    src = open(path, encoding="utf-8").read()
    if KSIG_TWIN not in src:
        print("O16_COPY_DRIFT FAIL — no _fa2_causal_o16_kernel in", path)
        return 1
    i = src.index(KSIG_SHIP)
    j = src.index(O16_HEADER, i)
    shipped = src[i:j].rstrip("\n") + "\n"
    k = src.index(KSIG_TWIN)
    e = src.index(O16_END, k)
    twin = src[k:e].rstrip("\n") + "\n"
    want = derive(shipped)
    if want == twin:
        print(f"O16_COPY_DRIFT PASS — the {len(twin.splitlines())}-line twin is exactly the "
              f"{len(shipped.splitlines())}-line shipped kernel plus the four documented "
              "differences (name, og16/rev_rows parameters, qi expression, epilogue)")
        return 0
    d = list(difflib.unified_diff(want.splitlines(), twin.splitlines(),
                                  "re-derived from the shipped kernel", "in tree",
                                  lineterm="", n=1))
    print(f"O16_COPY_DRIFT FAIL — {len(d)} diff lines; the twin has drifted from the shipped "
          "kernel beyond the four documented differences:")
    print("\n".join(d[:80]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
