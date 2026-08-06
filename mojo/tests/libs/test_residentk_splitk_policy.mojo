"""test_residentk_splitk_policy.mojo — the GENUINELY DYNAMIC split-K depth policy
(`residentk.contract.residentk_splitk_policy`/`residentk_splitk_should_split`/
`residentk_splitk_max_n_splits`), hand-written, not generated (following `test_residentk_attn_
splitk_kernel.mojo`'s own convention of a dedicated suite alongside the auto-generated smoke test in
`test_residentk_contract.mojo`).

Pure host arithmetic, no GPU, no `-D ALGENTA_GPU` gate needed — same reasoning
`residentk.contract`'s own module docstring gives for why this whole file imports no `std.gpu`.

WHAT THIS CHECKS, AND WHY EACH CASE EXISTS
--------------------------------------------
1. The two calibration ANCHORS the formula is built to pass through exactly (`n_keys=128 ->
   n_splits=40`, `n_keys=1000 -> n_splits=80`, at this model's `h_q=16` on this machine's `n_cores=
   40`) — if either drifts, the formula's own derivation (see `residentk.contract`'s module-level
   comment) no longer holds.
2. Monotonicity: `n_splits` must never DECREASE as `n_keys` increases, for a fixed `(n_cores, h_q)` —
   a policy that dips back down at some depth would contradict the whole "wider splits help more at
   depth, up to a ceiling" premise this design rests on.
3. The occupancy CEILING: far past the high anchor (`n_keys=100000`), `n_splits` must equal
   `residentk_splitk_max_n_splits`'s own return exactly — going wider than the ceiling never won at
   any tested depth (see the calibration account), so the formula must saturate, not keep climbing.
4. The FALLBACK reproduces `_ATTN_SPLITK_N_SPLITS_NATIVE` (80): a caller that could not detect a real
   core count (`n_cores <= 0`) must land on PR #523's own last-known-good fixed value, never
   something worse or unbounded.
5. Generalization to a DIFFERENT hardware shape (fewer cores, more heads than this Apple M4 Max/
   Qwen3-0.6B pair) — the whole point of tying the formula to `n_cores`/`h_q` instead of a hardcoded
   80.
6. `residentk_splitk_should_split`'s own gate, at and around its measured boundary (`n_keys=16` a
   wash, `n_keys=32` a clear win — see `RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS`'s own docstring).
7. Edge cases the task itself calls out: `n_keys=0`, negative `n_keys`, `h_q=0` — every one of these
   must return a SANE positive `Int` (never zero, negative, or a crash), since a caller could feed
   any of these into a GPU dispatch's grid width with no further validation.
"""

from residentk.contract import (
    residentk_splitk_should_split,
    residentk_splitk_policy,
    residentk_splitk_max_n_splits,
    RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS,
    RESIDENT_SPLITK_ANCHOR_LO_KEYS,
    RESIDENT_SPLITK_ANCHOR_HI_KEYS,
    RESIDENT_SPLITK_FALLBACK_N_CORES,
)


def _check(mut passed: Int, mut failed: Int, name: String, got: Int, want: Int) -> None:
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
        print("  ❌", name, "-- condition was False")


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    comptime N_CORES: Int = 40  # this machine's own measured Apple M4 Max GPU core count
    comptime H_Q: Int = 16      # Qwen3-0.6B-Base's own num_attention_heads

    # 1. The two calibration anchors, exactly -- see the module docstring and
    # `residentk.contract`'s own derivation comment.
    _check(
        passed, failed, "policy(anchor_lo=128, 40, 16) == 40",
        residentk_splitk_policy(RESIDENT_SPLITK_ANCHOR_LO_KEYS, N_CORES, H_Q), 40,
    )
    _check(
        passed, failed, "policy(anchor_hi=1000, 40, 16) == 80",
        residentk_splitk_policy(RESIDENT_SPLITK_ANCHOR_HI_KEYS, N_CORES, H_Q), 80,
    )
    _check(
        passed, failed, "max_n_splits(40, 16) reproduces _ATTN_SPLITK_N_SPLITS_NATIVE (80)",
        residentk_splitk_max_n_splits(N_CORES, H_Q), 80,
    )

    # 2. Monotonicity across the whole depth range a real generation actually passes through.
    var depths = List[Int]()
    depths.append(1); depths.append(16); depths.append(32); depths.append(64)
    depths.append(128); depths.append(200); depths.append(256); depths.append(400)
    depths.append(500); depths.append(750); depths.append(1000); depths.append(2000)
    depths.append(4000); depths.append(8000); depths.append(16000); depths.append(100000)

    var prev = 0
    var monotonic = True
    for i in range(len(depths)):
        var n_splits = residentk_splitk_policy(depths[i], N_CORES, H_Q)
        if n_splits < prev:
            monotonic = False
            print("     regression at n_keys=", depths[i], ": n_splits=", n_splits, "< previous", prev)
        prev = n_splits
    _check_true(passed, failed, "policy(n_keys, 40, 16) is non-decreasing across the whole depth sweep", monotonic)

    # 3. The occupancy ceiling: far past the high anchor, the formula must SATURATE, not keep climbing.
    _check(
        passed, failed, "policy(100000, 40, 16) saturates at the ceiling",
        residentk_splitk_policy(100000, N_CORES, H_Q), residentk_splitk_max_n_splits(N_CORES, H_Q),
    )
    _check(
        passed, failed, "policy(8000, 40, 16) already at the ceiling (PR #523's own deepest tested point)",
        residentk_splitk_policy(8000, N_CORES, H_Q), 80,
    )

    # 4. Fallback core count reproduces PR #523's own fixed value exactly, on EITHER kind of failed probe.
    _check(
        passed, failed, "policy(4000, 0, 16) [probe returned 0] == policy(4000, 40, 16)",
        residentk_splitk_policy(4000, 0, H_Q), residentk_splitk_policy(4000, N_CORES, H_Q),
    )
    _check(
        passed, failed, "policy(4000, -1, 16) [probe returned -1] == policy(4000, 40, 16)",
        residentk_splitk_policy(4000, -1, H_Q), residentk_splitk_policy(4000, N_CORES, H_Q),
    )
    _check(
        passed, failed, "RESIDENT_SPLITK_FALLBACK_N_CORES itself reproduces 80 at h_q=16",
        residentk_splitk_max_n_splits(RESIDENT_SPLITK_FALLBACK_N_CORES, H_Q), 80,
    )

    # 5. A genuinely different hardware shape: fewer cores, more heads than this Apple M4 Max / Qwen3
    # pair -- the formula must still produce a SANE, bounded, nonzero answer tied to THAT shape, not
    # silently reuse this machine's own numbers.
    _check(
        passed, failed, "max_n_splits(8, 32) for a smaller/differently-shaped GPU",
        residentk_splitk_max_n_splits(8, 32), 8,
    )
    _check_true(
        passed, failed, "policy(4000, 8, 32) never exceeds that shape's own ceiling",
        residentk_splitk_policy(4000, 8, 32) <= residentk_splitk_max_n_splits(8, 32),
    )
    _check_true(
        passed, failed, "policy(4000, 8, 32) is still positive",
        residentk_splitk_policy(4000, 8, 32) >= 1,
    )

    # 6. `residentk_splitk_should_split`'s own gate, at its measured boundary.
    _check_true(passed, failed, "should_split(16) == False (measured wash)", not residentk_splitk_should_split(16))
    _check_true(
        passed, failed, "should_split(RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS - 1) == False",
        not residentk_splitk_should_split(RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS - 1),
    )
    _check_true(
        passed, failed, "should_split(RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS) == True (measured win)",
        residentk_splitk_should_split(RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS),
    )
    _check_true(passed, failed, "should_split(4000) == True", residentk_splitk_should_split(4000))
    _check_true(passed, failed, "should_split(0) == False", not residentk_splitk_should_split(0))

    # 7. Edge cases: every one of these must return a SANE positive Int, never zero/negative/crash.
    _check(passed, failed, "policy(0, 40, 16) == 1 (smallest meaningful split count)", residentk_splitk_policy(0, N_CORES, H_Q), 1)
    _check(passed, failed, "policy(-5, 40, 16) == 1", residentk_splitk_policy(-5, N_CORES, H_Q), 1)
    _check(passed, failed, "policy(4000, 40, 0) == 1 (h_q < 1 refused)", residentk_splitk_policy(4000, N_CORES, 0), 1)
    _check_true(passed, failed, "policy(1, 40, 16) >= 1", residentk_splitk_policy(1, N_CORES, H_Q) >= 1)
    _check_true(
        passed, failed, "max_n_splits never returns < 1 even for a degenerate (n_cores, h_q)",
        residentk_splitk_max_n_splits(0, 0) >= 1,
    )

    print("  [residentk.contract splitk-policy] Passed:", passed, "Failed:", failed)
