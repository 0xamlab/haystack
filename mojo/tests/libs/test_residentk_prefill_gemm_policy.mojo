"""test_residentk_prefill_gemm_policy.mojo — the weight-stationary-tiled-GEMM tile-config policy
(`residentk.contract.residentk_prefill_gemm_use_narrow_tile`), hand-written, mirroring
`test_residentk_splitk_policy.mojo`'s own structure and discipline.

Pure host arithmetic, no GPU, no `-D ALGENTA_GPU` gate needed — the policy itself is a single
threshold comparison; the two real anchor measurements it is derived from (`m_rows=5` and
`m_rows=256`, real Qwen3-0.6B-Base checkpoint runs) live in `residentk_prefill_gemm_use_narrow_
tile`'s own docstring, not repeated here as executable assertions (there is no GPU in this file to
re-run them against).

WHAT THIS CHECKS
------------------
1. Both real measured anchor points resolve to the config that measured best there: `m_rows=5`
   (well below the threshold) selects narrow; `m_rows=256` (well above it) selects wide.
2. The threshold boundary itself: `m_rows = RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M - 1` selects
   narrow, `m_rows = RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M` selects wide (a strict `<`, matching
   this arm's own real race points of 8/128/512 never landing exactly on 32 anyway, but the boundary
   itself must still be exact and not an off-by-one).
3. Edge cases: `m_rows = 0` and negative `m_rows` are both below the threshold (narrow) — sane, not
   a crash, even though a real caller refuses these before ever reaching this policy
   (`_MBQwen3I8AllSimd7Prefill.prefill_batch`'s own `MB_ERR_UPLOAD_LENGTH` check).
4. `m_rows = 1` (a real, tested Gate-0 shape) selects narrow.
"""

from residentk.contract import (
    residentk_prefill_gemm_use_narrow_tile,
    RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M,
)


def _check_true(mut passed: Int, mut failed: Int, name: String, cond: Bool) -> None:
    if cond:
        passed += 1
        print("  ✅", name)
    else:
        failed += 1
        print("  ❌", name, "FAILED")


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    _check_true(
        passed, failed, "m_rows=5 (real anchor, narrow measured best) selects narrow",
        residentk_prefill_gemm_use_narrow_tile(5),
    )
    _check_true(
        passed, failed, "m_rows=256 (real anchor, wide measured best) selects wide",
        not residentk_prefill_gemm_use_narrow_tile(256),
    )
    _check_true(
        passed, failed, "m_rows=8 (a real race point) selects narrow",
        residentk_prefill_gemm_use_narrow_tile(8),
    )
    _check_true(
        passed, failed, "m_rows=128 (a real race point) selects wide",
        not residentk_prefill_gemm_use_narrow_tile(128),
    )
    _check_true(
        passed, failed, "m_rows=512 (a real race point) selects wide",
        not residentk_prefill_gemm_use_narrow_tile(512),
    )
    _check_true(
        passed, failed, "threshold - 1 selects narrow",
        residentk_prefill_gemm_use_narrow_tile(RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M - 1),
    )
    _check_true(
        passed, failed, "threshold itself selects wide",
        not residentk_prefill_gemm_use_narrow_tile(RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M),
    )
    _check_true(
        passed, failed, "m_rows=1 selects narrow",
        residentk_prefill_gemm_use_narrow_tile(1),
    )
    _check_true(
        passed, failed, "m_rows=0 is sane (narrow), not a crash",
        residentk_prefill_gemm_use_narrow_tile(0),
    )
    _check_true(
        passed, failed, "negative m_rows is sane (narrow), not a crash",
        residentk_prefill_gemm_use_narrow_tile(-5),
    )

    print("  [residentk.contract prefill-gemm-policy] Passed:", passed, "Failed:", failed)
