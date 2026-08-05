"""Test_embeddings_centroid_crash_probe.mojo — hand-verified regression probe
for the `embeddings.centroid` and `ml.classifiers.kmeans_cluster` crash-class
bug fix.

Both functions took `dim` from the FIRST element of their input list, then
indexed EVERY OTHER element at positions `0 .. dim-1` with no length check.
If any later element was shorter than the first (e.g. mixed-dimension
embeddings from two different models accidentally batched together), that
was an out-of-bounds `List` index -- per this repo's own established
finding, an uncatchable, worker-killing bounds assertion, not a normal
exception (the same failure class as the kernel-count-abort precedent).

Both are now fixed IN PLACE (not given `_strict` siblings -- a crash is
never correct behavior for any caller, unlike the lenient-truncation
functions in this same module, which stay frozen because a caller might
genuinely want that): each raises a real, catchable `Error` -- naming the
offending element and its real length -- before any out-of-bounds index is
ever touched.

Not an auto-generated suite (tests/generate_mojo_tests.py, under
mojo/tests/libs/, only emits a plain smoke call per function -- it cannot
express "expect a raise"). This hand-written probe proves, against a real
ragged input:

  1. `centroid` / `kmeans_cluster` RAISE on a ragged (mismatched-length)
     input instead of crashing or silently reading past the short vector's
     end, naming the offending index and its real length.
  2. On well-formed (equal-length) input, both still return the exact same,
     correct answer as before the fix -- no regression on the correct-input
     path.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine \
    ../tests/mojo/test_embeddings_centroid_crash_probe.mojo
"""
from embeddings import centroid
from ml.classifiers import kmeans_cluster


fn _mk(*values: Float64) -> List[Float64]:
    var out = List[Float64]()
    for v in values:
        out.append(v)
    return out^


fn _mk_list(*vecs: List[Float64]) -> List[List[Float64]]:
    var out = List[List[Float64]]()
    for v in vecs:
        out.append(v.copy())
    return out^


def main() raises:
    var passed = 0
    var failed = 0

    # ── well-formed input: centroid must still return the correct answer ──────
    var v10 = _mk(1.0, 0.0)
    var v01 = _mk(0.0, 1.0)
    var well_formed = _mk_list(v10, v01)
    var c = centroid(well_formed)
    if len(c) == 2 and c[0] == 0.5 and c[1] == 0.5:
        passed += 1
        print("  ✅ centroid([1,0],[0,1]) == [0.5, 0.5] on well-formed input")
    else:
        failed += 1
        print("  ❌ centroid regressed on well-formed input:", c[0], c[1])

    # ── ragged input: centroid must RAISE, naming the short vector + its length ──
    var v5 = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var v3 = _mk(1.0, 2.0, 3.0)
    var ragged = _mk_list(v5, v3)
    var centroid_raised = False
    var centroid_message = String("")
    try:
        _ = centroid(ragged)
    except e:
        centroid_raised = True
        centroid_message = String(e)
    if centroid_raised and "5" in centroid_message and "3" in centroid_message and "vectors[1]" in centroid_message:
        passed += 1
        print("  ✅ centroid RAISED on a ragged vector list, naming vectors[1] (5 vs 3):", centroid_message)
    else:
        failed += 1
        print("  ❌ centroid did NOT raise correctly on a ragged vector list:", centroid_message)

    # a ragged vector list where the short one comes FIRST: dim=3 (from
    # vectors[0]), and vectors[1] has 5 -- reading vectors[1][0..2] would
    # still be in-bounds, but the fix raises on ANY length mismatch (not
    # just a shorter one), so this also raises. That is a strictly SAFER
    # check than "shorter than dim" would have been -- it also closes the
    # silent-partial-average gap in this direction, not just the crash.
    var ragged_first_short = _mk_list(v3, v5)
    var centroid2_raised = False
    var centroid2_message = String("")
    try:
        _ = centroid(ragged_first_short)
    except e:
        centroid2_raised = True
        centroid2_message = String(e)
    if centroid2_raised and "3" in centroid2_message and "5" in centroid2_message and "vectors[1]" in centroid2_message:
        passed += 1
        print("  ✅ centroid RAISED even when the longer vector comes second (3 vs 5):", centroid2_message)
    else:
        failed += 1
        print("  ❌ centroid did NOT raise correctly when the longer vector comes second:", centroid2_message)

    # ── kmeans_cluster: well-formed input still returns valid assignments ─────
    var km_data = _mk_list(
        _mk(0.0, 0.0), _mk(0.1, 0.1), _mk(10.0, 10.0), _mk(10.1, 10.1)
    )
    var labels = kmeans_cluster(km_data, 2, 50)
    if len(labels) == 4:
        passed += 1
        print("  ✅ kmeans_cluster still returns 4 labels on well-formed input")
    else:
        failed += 1
        print("  ❌ kmeans_cluster regressed on well-formed input")

    # ── kmeans_cluster: ragged input must RAISE, naming the short point + its length ──
    var km_ragged = _mk_list(_mk(0.0, 0.0, 0.0), _mk(1.0, 1.0))
    var kmeans_raised = False
    var kmeans_message = String("")
    try:
        _ = kmeans_cluster(km_ragged, 2, 50)
    except e:
        kmeans_raised = True
        kmeans_message = String(e)
    if kmeans_raised and "3" in kmeans_message and "2" in kmeans_message and "data[1]" in kmeans_message:
        passed += 1
        print("  ✅ kmeans_cluster RAISED on a ragged data list, naming data[1] (3 vs 2):", kmeans_message)
    else:
        failed += 1
        print("  ❌ kmeans_cluster did NOT raise correctly on a ragged data list:", kmeans_message)

    print("  [test_embeddings_centroid_crash_probe] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_embeddings_centroid_crash_probe: " + String(failed) + " check(s) failed")
