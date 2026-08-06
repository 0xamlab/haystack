"""test_determinism_sampling_keyed.mojo — known-value tests for keyed sampling.

Hand-written. The properties that matter: reproducibility for fixed coordinates,
divergence when any coordinate changes, that a permutation really is a permutation,
and that with/without replacement differ in the way their names promise.
"""
from determinism.sampling_keyed import (
    bootstrap_keyed,
    choice_keyed,
    permutation_keyed,
    sample_without_replacement_keyed,
    shuffle_keyed,
    uniform_int_keyed,
)


def _values(n: Int) -> List[Float64]:
    var out = List[Float64]()
    for i in range(n):
        out.append(Float64(i))
    return out^


def _same(a: List[Float64], b: List[Float64]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def main() raises:
    var passed = 0
    var failed = 0

    # ── the same coordinates always give the same draw ───────────────────────
    var w = List[Float64]()
    w.append(1.0)
    w.append(1.0)
    w.append(2.0)
    if choice_keyed(w, 42, 8, 0) == choice_keyed(w, 42, 8, 0):
        passed += 1
        print("  ✅ choice_keyed is reproducible for fixed coordinates")
    else:
        failed += 1
        print("  ❌ choice_keyed not reproducible")

    # ── every coordinate participates ────────────────────────────────────────
    var by_seed = choice_keyed(w, 42, 8, 0) != choice_keyed(w, 43, 8, 0)
    var by_stream = choice_keyed(w, 42, 8, 0) != choice_keyed(w, 42, 9, 0)
    var by_index = choice_keyed(w, 42, 8, 0) != choice_keyed(w, 42, 8, 1)
    if by_seed or by_stream or by_index:
        passed += 1
        print("  ✅ changing a coordinate can change the draw")
    else:
        failed += 1
        print("  ❌ coordinates appear inert")

    # ── weights are respected: a zero-weight index is never chosen ────────────
    var skewed = List[Float64]()
    skewed.append(0.0)
    skewed.append(1.0)
    var never_zero = True
    for i in range(200):
        if choice_keyed(skewed, 7, 8, UInt64(i)) == 0:
            never_zero = False
    if never_zero:
        passed += 1
        print("  ✅ a zero-weight index is never selected")
    else:
        failed += 1
        print("  ❌ zero-weight index selected")

    # ── degenerate input is -1, not a plausible index 0 ──────────────────────
    var empty = List[Float64]()
    var zeros = List[Float64]()
    zeros.append(0.0)
    zeros.append(0.0)
    if choice_keyed(empty, 1, 8, 0) == -1 and choice_keyed(zeros, 1, 8, 0) == -1:
        passed += 1
        print("  ✅ empty/all-zero weights return -1, not index 0")
    else:
        failed += 1
        print("  ❌ degenerate weights returned an index")

    # ── a permutation contains every index exactly once ──────────────────────
    var perm = permutation_keyed(8, 99, 8, 0)
    var seen = List[Bool]()
    for _ in range(8):
        seen.append(False)
    var valid = len(perm) == 8
    for i in range(len(perm)):
        if perm[i] < 0 or perm[i] >= 8 or seen[perm[i]]:
            valid = False
        else:
            seen[perm[i]] = True
    if valid:
        passed += 1
        print("  ✅ permutation_keyed yields each index exactly once")
    else:
        failed += 1
        print("  ❌ not a permutation")

    # ── permutations reproduce, and differ by seed ────────────────────────────
    var perm_again = permutation_keyed(8, 99, 8, 0)
    var perm_other = permutation_keyed(8, 100, 8, 0)
    var identical = len(perm) == len(perm_again)
    for i in range(len(perm)):
        if perm[i] != perm_again[i]:
            identical = False
    var differs = False
    for i in range(len(perm)):
        if perm[i] != perm_other[i]:
            differs = True
    if identical and differs:
        passed += 1
        print("  ✅ permutation reproduces for one seed and differs for another")
    else:
        failed += 1
        print("  ❌ permutation stability wrong")

    # ── n <= 1 is handled without a draw ─────────────────────────────────────
    if len(permutation_keyed(0, 1, 8, 0)) == 0 and len(permutation_keyed(1, 1, 8, 0)) == 1:
        passed += 1
        print("  ✅ permutations of 0 and 1 elements are trivial")
    else:
        failed += 1
        print("  ❌ degenerate permutation wrong")

    # ── shuffle is a reordering: same multiset, input untouched ───────────────
    var original = _values(6)
    var shuffled = shuffle_keyed(original, 5, 8, 0)
    var total_before: Float64 = 0.0
    var total_after: Float64 = 0.0
    for i in range(6):
        total_before += original[i]
        total_after += shuffled[i]
    if total_before == total_after and original[0] == 0.0 and original[5] == 5.0:
        passed += 1
        print("  ✅ shuffle preserves the multiset and leaves the input alone")
    else:
        failed += 1
        print("  ❌ shuffle mutated or lost values")

    if _same(shuffle_keyed(original, 5, 8, 0), shuffled):
        passed += 1
        print("  ✅ shuffle reproduces for the same coordinates")
    else:
        failed += 1
        print("  ❌ shuffle not reproducible")

    # ── without replacement yields distinct items ────────────────────────────
    var pick = sample_without_replacement_keyed(_values(10), 4, 3, 8, 0)
    var distinct = len(pick) == 4
    for i in range(len(pick)):
        for j in range(i + 1, len(pick)):
            if pick[i] == pick[j]:
                distinct = False
    if distinct:
        passed += 1
        print("  ✅ sampling without replacement gives distinct items")
    else:
        failed += 1
        print("  ❌ duplicate in a without-replacement sample")

    # ── k above the population returns the whole population ─────────────────
    if len(sample_without_replacement_keyed(_values(3), 10, 1, 8, 0)) == 3:
        passed += 1
        print("  ✅ k larger than the population returns all of it")
    else:
        failed += 1
        print("  ❌ oversized k wrong")

    # ── with replacement CAN repeat — that is the point of a bootstrap ────────
    var boot = bootstrap_keyed(_values(3), 30, 4, 8, 0)
    var repeated = False
    for i in range(len(boot)):
        for j in range(i + 1, len(boot)):
            if boot[i] == boot[j]:
                repeated = True
    if len(boot) == 30 and repeated:
        passed += 1
        print("  ✅ bootstrap draws 30 from 3 with repeats, as it must")
    else:
        failed += 1
        print("  ❌ bootstrap wrong:", len(boot), repeated)

    if _same(bootstrap_keyed(_values(3), 30, 4, 8, 0), boot):
        passed += 1
        print("  ✅ bootstrap reproduces for the same coordinates")
    else:
        failed += 1
        print("  ❌ bootstrap not reproducible")

    # ── an empty population bootstraps to nothing, not a crash ──────────────
    if len(bootstrap_keyed(empty, 5, 1, 8, 0)) == 0:
        passed += 1
        print("  ✅ bootstrapping an empty population yields nothing")
    else:
        failed += 1
        print("  ❌ empty bootstrap wrong")

    # ── uniform_int_keyed stays inside its inclusive bounds ──────────────────
    var in_range = True
    var saw_low = False
    var saw_high = False
    for i in range(400):
        var x = uniform_int_keyed(3, 6, 12, 8, UInt64(i))
        if x < 3 or x > 6:
            in_range = False
        if x == 3:
            saw_low = True
        if x == 6:
            saw_high = True
    if in_range and saw_low and saw_high:
        passed += 1
        print("  ✅ uniform_int_keyed covers [low, high] inclusively")
    else:
        failed += 1
        print("  ❌ integer range wrong:", in_range, saw_low, saw_high)

    if uniform_int_keyed(5, 5, 1, 8, 0) == 5 and uniform_int_keyed(9, 2, 1, 8, 0) == 9:
        passed += 1
        print("  ✅ degenerate and inverted ranges return low")
    else:
        failed += 1
        print("  ❌ degenerate range wrong")

    print("  [determinism.sampling_keyed] Passed:", passed, "Failed:", failed)
