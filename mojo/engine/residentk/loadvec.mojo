"""
residentk.loadvec — LEVER #0 (micro-autopsy, 2026-08-23): restore true 16-byte vector global
loads on the hot weight/activation streaming loops.

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/packed3_gemv_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

THE MEASURED DEFECT (the "missed something")
---------------------------------------------
Every kernel-pointer parameter this backend lowers carries `.param .u64 .ptr .align 1` — NO
alignment information survives to PTX. The consequence, verified by disassembling the embedded
PTX of the shipped binaries (`strings <binary> | grep ld.global`), is that the campaign's
`load[width=4]` idiom — documented everywhere as "the ONE 128-bit load path this toolchain
streams at HBM speed" — actually lowers to FOUR scalar `ld.global.b32` instructions, not one
`ld.global.v4.b32`:

    shipped `_packed3_gemv_kernel` weight stream (BEFORE):
        ld.global.b32   %r2, [%rd53];
        ld.global.b32   %r3, [%rd53+4];
        ld.global.b32   %r4, [%rd53+8];
        ld.global.b32   %r5, [%rd53+12];
    with `load[width=4, alignment=16]` (AFTER):
        ld.global.v4.b32   {%r2, %r3, %r4, %r5}, [%rd53];

Zero `ld.global.v4` in the whole shipped packed3 binary, 75 scalar `ld.global.b32`. Four load
instructions + four address computations per 16 bytes where the hardware can take one. This is
issue-slot pressure on the exact loops that are latency/issue-bound (the packed3 GEMV streams
at ~165 GB/s of its 470-497 GB/s floor), and it is format-agnostic: it hits the f32 prefill
GEMMs and the flash-attention K/V streams the same way.

THE FIX, and why it is safe
---------------------------
`UnsafePointer.load` accepts an `alignment=` annotation; `load[width=4, alignment=16]` tells the
backend the address is a multiple of 16 bytes, which is what unlocks the single `ld.global.v4.b32`.
The annotation is a PROMISE, so it is only applied where the alignment is provable, and it was
PROVED on the A100 (align_check_probe.mojo): every fresh `DeviceBuffer` base is 256-byte aligned
(a superset of 16), and the packed3 layout pads every row stride to a multiple of 4 words and
every chunk offset is a multiple of 12 elements (=48 bytes), so `wbase + t/3` and `t` are 16-byte
aligned at every annotated site. Shared-memory staging loads (`xs`) are deliberately NOT
annotated here (different address space, separate lever).

MATH IS BIT-IDENTICAL: this changes only the load INSTRUCTION WIDTH, not the loaded bytes, the
dequant expression, or the accumulation order. The control (flag off) is byte-preserved.

Toggle: default ON (shipped config = vector loads; alignment proved at every call site by
align_check_probe). `-D ALGENTA_L0_NOALIGN` restores the scalar control for A/B.
"""

from std.origin import MutAnyOrigin
from std.sys import is_defined

comptime L0_ALIGN: Bool = not is_defined["ALGENTA_L0_NOALIGN"]()
"""LEVER #0 switch. ON (default) = `load[width=4, alignment=16]`, which lowers to a single
`ld.global.v4.b32` instead of four scalar `ld.global.b32` (the scalar path was the
micro-autopsy's root-caused miss). OFF (`-D ALGENTA_L0_NOALIGN`) = the scalar control."""

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

@always_inline
def _ld4(p: _FP, off: Int) -> SIMD[DType.float32, 4]:
    """A 16-byte global Float32 load at element offset `off` (which MUST be a multiple of 4
    elements at every call site — the module docstring's proof). With `L0_ALIGN` it carries the
    `alignment=16` annotation that lets the backend emit one `ld.global.v4.b32`; without it this
    is the shipped `load[width=4]` verbatim."""
    @parameter
    if L0_ALIGN:
        return p.load[width=4, alignment=16](off)
    else:
        return p.load[width=4](off)


@always_inline
def _st4(p: _FP, off: Int, v: SIMD[DType.float32, 4]):
    """The STORE twin of `_ld4`: a 16-byte global Float32 store at element offset `off`, which
    MUST be a multiple of 4 elements at every call site (the same proof, resting on the same
    256-byte-aligned `DeviceBuffer` bases).

    FRONT 5 needed this because `_ld4` alone only fixes half of a streaming kernel's issue-slot
    pressure: a kernel that vectorizes its loads and then writes the result back with four
    scalar `st.global.b32` still pays four store instructions and four address computations per
    16 bytes. With `L0_ALIGN` this carries the `alignment=16` annotation so the backend can emit
    one `st.global.v4.b32`; without it, it is the plain `store[width=4]` control.

    MATH IS BIT-IDENTICAL: this changes only the store INSTRUCTION WIDTH, not the bytes written,
    their order, or any arithmetic. The control (flag off) is byte-preserved."""
    @parameter
    if L0_ALIGN:
        p.store[width=4, alignment=16](off, v)
    else:
        p.store[width=4](off, v)
