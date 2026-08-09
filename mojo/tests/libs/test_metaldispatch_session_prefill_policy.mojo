"""test_metaldispatch_session_prefill_policy.mojo — dedicated libs suite for
`metaldispatch.session_prefill_policy` (the resolved session execution plan: attention path + GEMM
tier + the derived KV-cache contract + decode routing), hand-written, not generated. Pure host logic,
no GPU, no `-D ALGENTA_GPU` gate — the module under test is plain Int constants + pure resolution
functions.

WHAT THIS CHECKS
----------------
1. The four `*_name` human-readable mappers return the exact documented string for every named
   constant and a stable `unknown(<n>)` for anything else.
2. `resolve_prefill_execution_plan`'s graceful-degrade rule: an explicit request for a path whose
   blobs are available is always honored; the same request degrades to the documented fallback when
   the blobs are absent (never a hard error, never silently overridden by another path's default).
3. Round-5 contract: `kv_contract`/`decode` are always derived from the RESOLVED attention value —
   a `PF_ATTN_GROUPED_FA_NO_MIRROR` request that degrades to `PF_ATTN_OFF` gets the OFF contract,
   not the no-mirror one.
4. `is_resolved()` accepts every genuinely-resolved plan and rejects `PF_UNRESOLVED` and a
   `kv_contract`/`decode` that disagrees with `attention`.
"""

from metaldispatch.session_prefill_policy import (
    PF_ATTN_OFF,
    PF_ATTN_GROUPED_FA_WITH_MIRROR,
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_ORIGINAL,
    PF_GEMM_BM64,
    PF_GEMM_VECLOAD4_ALL_ROLES,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    PF_UNRESOLVED,
    KV_CONTRACT_NATURAL_F32,
    KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16,
    KV_CONTRACT_PACKED_F16_NATIVE,
    DECODE_PATH_LEGACY_NATURAL_KV,
    DECODE_PATH_NATIVE_PACKED_KV,
    UnresolvedPrefillConfig,
    ResolvedSessionExecutionPlan,
    pf_attn_path_name,
    pf_gemm_path_name,
    kv_contract_name,
    decode_path_name,
    resolve_prefill_execution_plan,
)


def _check(mut passed: Int, mut failed: Int, name: String, got: Int, want: Int) -> None:
    if got == want:
        passed += 1
        print("  ✅", name, "=", got)
    else:
        failed += 1
        print("  ❌", name, "=", got, "expected", want)


def _check_str(mut passed: Int, mut failed: Int, name: String, got: String, want: String) -> None:
    if got == want:
        passed += 1
        print("  ✅", name, "=", got)
    else:
        failed += 1
        print("  ❌", name, "=", got, "expected", want)


def _check_true(mut passed: Int, mut failed: Int, name: String, cond: Bool) -> None:
    if cond:
        passed += 1
        print("  ✅", name)
    else:
        failed += 1
        print("  ❌", name)


def main() raises:
    var passed = 0
    var failed = 0

    # 1. Name mappers — every named constant + an out-of-range value.
    _check_str(passed, failed, "pf_attn_path_name(OFF)", pf_attn_path_name(PF_ATTN_OFF), "off")
    _check_str(
        passed, failed, "pf_attn_path_name(WITH_MIRROR)",
        pf_attn_path_name(PF_ATTN_GROUPED_FA_WITH_MIRROR), "grouped_fa_with_mirror",
    )
    _check_str(
        passed, failed, "pf_attn_path_name(NO_MIRROR)",
        pf_attn_path_name(PF_ATTN_GROUPED_FA_NO_MIRROR), "grouped_fa_no_mirror",
    )
    _check_str(passed, failed, "pf_attn_path_name(99) unknown", pf_attn_path_name(99), "unknown(99)")

    _check_str(passed, failed, "pf_gemm_path_name(ORIGINAL)", pf_gemm_path_name(PF_GEMM_ORIGINAL), "original")
    _check_str(passed, failed, "pf_gemm_path_name(BM64)", pf_gemm_path_name(PF_GEMM_BM64), "bm64")
    _check_str(
        passed, failed, "pf_gemm_path_name(VECLOAD4)",
        pf_gemm_path_name(PF_GEMM_VECLOAD4_ALL_ROLES), "vecload4_all_roles",
    )
    _check_str(
        passed, failed, "pf_gemm_path_name(MSL_PARITY)",
        pf_gemm_path_name(PF_GEMM_MSL_PARITY_ALL_ROLES), "msl_parity_all_roles",
    )
    _check_str(passed, failed, "pf_gemm_path_name(99) unknown", pf_gemm_path_name(99), "unknown(99)")

    _check_str(passed, failed, "kv_contract_name(NATURAL_F32)", kv_contract_name(KV_CONTRACT_NATURAL_F32), "natural_f32")
    _check_str(
        passed, failed, "kv_contract_name(MIRRORED)",
        kv_contract_name(KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16),
        "mirrored_natural_f32_and_packed_f16",
    )
    _check_str(
        passed, failed, "kv_contract_name(PACKED_F16_NATIVE)",
        kv_contract_name(KV_CONTRACT_PACKED_F16_NATIVE), "packed_f16_native",
    )
    _check_str(passed, failed, "kv_contract_name(99) unknown", kv_contract_name(99), "unknown(99)")

    _check_str(
        passed, failed, "decode_path_name(LEGACY)",
        decode_path_name(DECODE_PATH_LEGACY_NATURAL_KV), "legacy_natural_kv",
    )
    _check_str(
        passed, failed, "decode_path_name(NATIVE_PACKED)",
        decode_path_name(DECODE_PATH_NATIVE_PACKED_KV), "native_packed_kv",
    )
    _check_str(passed, failed, "decode_path_name(99) unknown", decode_path_name(99), "unknown(99)")

    # 2. Resolution with NO optional blobs linked — everything degrades to the safe defaults.
    var p_off = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL), False, False, False, False, False,
    )
    _check(passed, failed, "off/no-blobs attention", p_off.attention, PF_ATTN_OFF)
    _check(passed, failed, "off/no-blobs gemm", p_off.gemm, PF_GEMM_ORIGINAL)
    _check(passed, failed, "off/no-blobs kv_contract", p_off.kv_contract, KV_CONTRACT_NATURAL_F32)
    _check(passed, failed, "off/no-blobs decode", p_off.decode, DECODE_PATH_LEGACY_NATURAL_KV)
    _check_true(passed, failed, "off/no-blobs is_resolved", p_off.is_resolved())

    # 3. NO_MIRROR honored when AF blobs available -> packed-F16 contract + native decode path.
    var p_nm = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_ORIGINAL),
        True, False, False, False, False,
    )
    _check(passed, failed, "no_mirror/af attention", p_nm.attention, PF_ATTN_GROUPED_FA_NO_MIRROR)
    _check(passed, failed, "no_mirror/af kv_contract", p_nm.kv_contract, KV_CONTRACT_PACKED_F16_NATIVE)
    _check(passed, failed, "no_mirror/af decode", p_nm.decode, DECODE_PATH_NATIVE_PACKED_KV)
    _check_true(passed, failed, "no_mirror/af is_resolved", p_nm.is_resolved())

    # 4. NO_MIRROR requested but AF blobs ABSENT -> degrades to OFF + OFF contract (round-5 rule).
    var p_nm_deg = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_ORIGINAL),
        False, False, False, False, False,
    )
    _check(passed, failed, "no_mirror/no-af degrades attention", p_nm_deg.attention, PF_ATTN_OFF)
    _check(passed, failed, "no_mirror/no-af degrades kv_contract", p_nm_deg.kv_contract, KV_CONTRACT_NATURAL_F32)
    _check(passed, failed, "no_mirror/no-af degrades decode", p_nm_deg.decode, DECODE_PATH_LEGACY_NATURAL_KV)
    _check_true(passed, failed, "no_mirror/no-af is_resolved", p_nm_deg.is_resolved())

    # 5. WITH_MIRROR honored -> mirrored contract, but decode still legacy (ck/cv populated).
    var p_wm = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_GROUPED_FA_WITH_MIRROR, PF_GEMM_ORIGINAL),
        True, False, False, False, False,
    )
    _check(passed, failed, "with_mirror/af attention", p_wm.attention, PF_ATTN_GROUPED_FA_WITH_MIRROR)
    _check(
        passed, failed, "with_mirror/af kv_contract", p_wm.kv_contract,
        KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16,
    )
    _check(passed, failed, "with_mirror/af decode", p_wm.decode, DECODE_PATH_LEGACY_NATURAL_KV)

    # 6. GEMM-tier graceful degrade chain.
    var g_msl_no = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_MSL_PARITY_ALL_ROLES), False, False, False, False, False,
    )
    _check(passed, failed, "msl request/no blobs -> ORIGINAL", g_msl_no.gemm, PF_GEMM_ORIGINAL)
    var g_msl_vec = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_MSL_PARITY_ALL_ROLES),
        False, False, True, False, False,
    )
    _check(passed, failed, "msl request/vecload4 available -> VECLOAD4", g_msl_vec.gemm, PF_GEMM_VECLOAD4_ALL_ROLES)
    var g_msl_yes = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_MSL_PARITY_ALL_ROLES),
        False, False, False, False, False, True, False, False,
    )
    _check(passed, failed, "msl request/msl available -> MSL_PARITY", g_msl_yes.gemm, PF_GEMM_MSL_PARITY_ALL_ROLES)
    var g_vec_bm = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_VECLOAD4_ALL_ROLES), False, True, False, False, False,
    )
    _check(passed, failed, "vecload4 request/only bm64 -> BM64", g_vec_bm.gemm, PF_GEMM_BM64)
    var g_bm_no = resolve_prefill_execution_plan(
        UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_BM64), False, False, False, False, False,
    )
    _check(passed, failed, "bm64 request/no blobs -> ORIGINAL", g_bm_no.gemm, PF_GEMM_ORIGINAL)

    # 7. is_resolved() rejects sentinel and inconsistent derived fields.
    var bad_sentinel = ResolvedSessionExecutionPlan(
        PF_UNRESOLVED, PF_GEMM_ORIGINAL, KV_CONTRACT_NATURAL_F32, DECODE_PATH_LEGACY_NATURAL_KV,
    )
    _check_true(passed, failed, "PF_UNRESOLVED attention -> not resolved", not bad_sentinel.is_resolved())
    var bad_pairing = ResolvedSessionExecutionPlan(
        PF_ATTN_GROUPED_FA_NO_MIRROR, PF_GEMM_ORIGINAL,
        KV_CONTRACT_NATURAL_F32, DECODE_PATH_LEGACY_NATURAL_KV,
    )
    _check_true(passed, failed, "no_mirror attention w/ legacy contract -> not resolved", not bad_pairing.is_resolved())

    print("  [metaldispatch.session_prefill_policy] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_metaldispatch_session_prefill_policy: " + String(failed) + " check(s) failed")
