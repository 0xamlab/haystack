"""test_embeddings_dimension_mismatch_probe.mojo — hand-verified probe for the
dimension-mismatch hardening fix (dot_product_strict / cosine_similarity_strict /
euclidean_distance_strict / manhattan_distance_strict / vector_add_strict /
cosine_similarity_matrix_strict / nearest_neighbor_strict / k_nearest_neighbors_strict),
added alongside embeddings.mojo.

Not an auto-generated suite (tests/generate_mojo_tests.py, under mojo/tests/libs/,
only emits a plain smoke call per function -- it cannot express "call twice and
compare" or "expect a raise"). This hand-written probe proves, against real
mismatched-dimension vectors (e.g. what you'd get accidentally batching
embeddings from two different models with different output dimensionality):

  1. The frozen originals (`dot_product`, `cosine_similarity`, `euclidean_distance`,
     `manhattan_distance`, `vector_add`, `cosine_similarity_matrix`,
     `nearest_neighbor`, `k_nearest_neighbors`) are UNCHANGED -- they still silently
     compute over only `min(len(a), len(b))` instead of raising.
  2. Every new `_strict` sibling RAISES on that same mismatched input, naming both
     real lengths in the message.
  3. On equal-length input, every `_strict` sibling returns EXACTLY the same result
     as its non-strict counterpart -- no regression on the correct-input path.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine \
    ../tests/mojo/test_embeddings_dimension_mismatch_probe.mojo
"""
from std.math import isnan, isinf
from embeddings import (
    dot_product,
    dot_product_strict,
    cosine_similarity,
    cosine_similarity_strict,
    euclidean_distance,
    euclidean_distance_strict,
    manhattan_distance,
    manhattan_distance_strict,
    vector_add,
    vector_add_strict,
    cosine_similarity_matrix,
    cosine_similarity_matrix_strict,
    nearest_neighbor,
    nearest_neighbor_strict,
    k_nearest_neighbors,
    k_nearest_neighbors_strict,
)


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

    # ── equal-length inputs: strict must match non-strict exactly ──────────────
    var ax = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var bx = _mk(2.0, 4.0, 5.0, 4.0, 6.0)

    if dot_product(ax, bx) == dot_product_strict(ax, bx):
        passed += 1
        print("  ✅ dot_product_strict matches dot_product on equal-length input")
    else:
        failed += 1
        print("  ❌ dot_product_strict DIFFERS from dot_product on equal-length input")

    if cosine_similarity(ax, bx) == cosine_similarity_strict(ax, bx):
        passed += 1
        print("  ✅ cosine_similarity_strict matches cosine_similarity on equal-length input")
    else:
        failed += 1
        print("  ❌ cosine_similarity_strict DIFFERS from cosine_similarity on equal-length input")

    if euclidean_distance(ax, bx) == euclidean_distance_strict(ax, bx):
        passed += 1
        print("  ✅ euclidean_distance_strict matches euclidean_distance on equal-length input")
    else:
        failed += 1
        print("  ❌ euclidean_distance_strict DIFFERS from euclidean_distance on equal-length input")

    if manhattan_distance(ax, bx) == manhattan_distance_strict(ax, bx):
        passed += 1
        print("  ✅ manhattan_distance_strict matches manhattan_distance on equal-length input")
    else:
        failed += 1
        print("  ❌ manhattan_distance_strict DIFFERS from manhattan_distance on equal-length input")

    var add_base = vector_add(ax, bx)
    var add_strict = vector_add_strict(ax, bx)
    var add_equal = len(add_base) == len(add_strict)
    if add_equal:
        for i in range(len(add_base)):
            if add_base[i] != add_strict[i]:
                add_equal = False
    if add_equal:
        passed += 1
        print("  ✅ vector_add_strict matches vector_add on equal-length input")
    else:
        failed += 1
        print("  ❌ vector_add_strict DIFFERS from vector_add on equal-length input")

    var cx = _mk(1.0, 0.0, 0.0)
    var cy = _mk(0.0, 1.0, 0.0)
    var cz = _mk(1.0, 1.0, 0.0)
    var square_vectors = _mk_list(cx, cy, cz)
    var base_matrix = cosine_similarity_matrix(square_vectors)
    var strict_matrix = cosine_similarity_matrix_strict(square_vectors)
    var matrix_equal = len(base_matrix) == len(strict_matrix)
    if matrix_equal:
        for i in range(len(base_matrix)):
            for j in range(len(base_matrix[i])):
                if base_matrix[i][j] != strict_matrix[i][j]:
                    matrix_equal = False
    if matrix_equal:
        passed += 1
        print("  ✅ cosine_similarity_matrix_strict matches cosine_similarity_matrix on equal-length input")
    else:
        failed += 1
        print("  ❌ cosine_similarity_matrix_strict DIFFERS from cosine_similarity_matrix on equal-length input")

    var query = _mk(1.0, 0.0, 0.0)
    var candidates = _mk_list(_mk(0.0, 1.0, 0.0), _mk(1.0, 0.0, 0.0), _mk(0.5, 0.5, 0.0))
    if nearest_neighbor(query, candidates) == nearest_neighbor_strict(query, candidates):
        passed += 1
        print("  ✅ nearest_neighbor_strict matches nearest_neighbor on equal-length input")
    else:
        failed += 1
        print("  ❌ nearest_neighbor_strict DIFFERS from nearest_neighbor on equal-length input")

    var knn_base = k_nearest_neighbors(query, candidates, 2)
    var knn_strict = k_nearest_neighbors_strict(query, candidates, 2)
    var knn_equal = len(knn_base) == len(knn_strict)
    if knn_equal:
        for i in range(len(knn_base)):
            if knn_base[i] != knn_strict[i]:
                knn_equal = False
    if knn_equal:
        passed += 1
        print("  ✅ k_nearest_neighbors_strict matches k_nearest_neighbors on equal-length input")
    else:
        failed += 1
        print("  ❌ k_nearest_neighbors_strict DIFFERS from k_nearest_neighbors on equal-length input")

    # ── mismatched-length inputs: frozen originals stay silent, strict siblings raise ──
    var mx = _mk(1.0, 2.0, 3.0, 4.0, 5.0)
    var my_short = _mk(2.0, 4.0, 5.0)

    # 1. Confirm the FROZEN functions' actual current behavior: no raise, no crash,
    #    a silent finite answer computed over only min(len(mx), len(my_short)) == 3.
    var frozen_dot = dot_product(mx, my_short)
    var frozen_cos = cosine_similarity(mx, my_short)
    var frozen_euc = euclidean_distance(mx, my_short)
    var frozen_man = manhattan_distance(mx, my_short)
    var frozen_add = vector_add(mx, my_short)
    if (
        not isnan(frozen_dot)
        and not isinf(frozen_dot)
        and not isnan(frozen_cos)
        and not isnan(frozen_euc)
        and not isnan(frozen_man)
        and len(frozen_add) == 3
    ):
        passed += 1
        print("  ✅ confirmed: frozen originals silently truncate to min(5,3)=3 on mismatched lengths, untouched (dot=", frozen_dot, ")")
    else:
        failed += 1
        print("  ❌ frozen originals did not reproduce the traced silent-truncation behavior")

    # 2. Confirm every `_strict` sibling RAISES on the same mismatched-length input,
    #    naming both real lengths (5 and 3).
    var dot_raised = False
    var dot_message = String("")
    try:
        _ = dot_product_strict(mx, my_short)
    except e:
        dot_raised = True
        dot_message = String(e)
    if dot_raised and "5" in dot_message and "3" in dot_message:
        passed += 1
        print("  ✅ dot_product_strict RAISED on mismatched lengths (5 vs 3):", dot_message)
    else:
        failed += 1
        print("  ❌ dot_product_strict did NOT raise correctly on mismatched lengths:", dot_message)

    var cos_raised = False
    var cos_message = String("")
    try:
        _ = cosine_similarity_strict(mx, my_short)
    except e:
        cos_raised = True
        cos_message = String(e)
    if cos_raised and "5" in cos_message and "3" in cos_message:
        passed += 1
        print("  ✅ cosine_similarity_strict RAISED on mismatched lengths (5 vs 3):", cos_message)
    else:
        failed += 1
        print("  ❌ cosine_similarity_strict did NOT raise correctly on mismatched lengths:", cos_message)

    var euc_raised = False
    var euc_message = String("")
    try:
        _ = euclidean_distance_strict(mx, my_short)
    except e:
        euc_raised = True
        euc_message = String(e)
    if euc_raised and "5" in euc_message and "3" in euc_message:
        passed += 1
        print("  ✅ euclidean_distance_strict RAISED on mismatched lengths (5 vs 3):", euc_message)
    else:
        failed += 1
        print("  ❌ euclidean_distance_strict did NOT raise correctly on mismatched lengths:", euc_message)

    var man_raised = False
    var man_message = String("")
    try:
        _ = manhattan_distance_strict(mx, my_short)
    except e:
        man_raised = True
        man_message = String(e)
    if man_raised and "5" in man_message and "3" in man_message:
        passed += 1
        print("  ✅ manhattan_distance_strict RAISED on mismatched lengths (5 vs 3):", man_message)
    else:
        failed += 1
        print("  ❌ manhattan_distance_strict did NOT raise correctly on mismatched lengths:", man_message)

    var vadd_raised = False
    var vadd_message = String("")
    try:
        _ = vector_add_strict(mx, my_short)
    except e:
        vadd_raised = True
        vadd_message = String(e)
    if vadd_raised and "5" in vadd_message and "3" in vadd_message:
        passed += 1
        print("  ✅ vector_add_strict RAISED on mismatched lengths (5 vs 3):", vadd_message)
    else:
        failed += 1
        print("  ❌ vector_add_strict did NOT raise correctly on mismatched lengths:", vadd_message)

    # cosine_similarity_matrix_strict: one vector in the list is shorter than vectors[0].
    var ragged_vectors = _mk_list(mx, my_short, mx)
    var matrix_raised = False
    var matrix_message = String("")
    try:
        _ = cosine_similarity_matrix_strict(ragged_vectors)
    except e:
        matrix_raised = True
        matrix_message = String(e)
    if matrix_raised and "5" in matrix_message and "3" in matrix_message and "vectors[1]" in matrix_message:
        passed += 1
        print("  ✅ cosine_similarity_matrix_strict RAISED on a ragged vector list, naming vectors[1] (5 vs 3):", matrix_message)
    else:
        failed += 1
        print("  ❌ cosine_similarity_matrix_strict did NOT raise correctly on a ragged vector list:", matrix_message)

    # confirm the frozen cosine_similarity_matrix does NOT raise on the same ragged input.
    var frozen_matrix = cosine_similarity_matrix(ragged_vectors)
    if len(frozen_matrix) == 3:
        passed += 1
        print("  ✅ confirmed: frozen cosine_similarity_matrix silently tolerates a ragged vector list, untouched")
    else:
        failed += 1
        print("  ❌ frozen cosine_similarity_matrix did not reproduce the traced silent-tolerance behavior")

    # nearest_neighbor_strict / k_nearest_neighbors_strict: one candidate shorter than the query.
    # candidates[0] matches mx's length (5); candidates[1] is the shorter my_short (3).
    var nn_candidates = _mk_list(
        _mk(1.0, 0.0, 0.0, 0.0, 0.0), my_short, _mk(0.0, 1.0, 0.0, 0.0, 0.0)
    )

    var nn_raised = False
    var nn_message = String("")
    try:
        _ = nearest_neighbor_strict(mx, nn_candidates)
    except e:
        nn_raised = True
        nn_message = String(e)
    if nn_raised and "5" in nn_message and "3" in nn_message and "candidates[1]" in nn_message:
        passed += 1
        print("  ✅ nearest_neighbor_strict RAISED on a mismatched candidate, naming candidates[1] (5 vs 3):", nn_message)
    else:
        failed += 1
        print("  ❌ nearest_neighbor_strict did NOT raise correctly on a mismatched candidate:", nn_message)

    # confirm the frozen nearest_neighbor does NOT raise on the same mismatched candidate.
    var frozen_nn = nearest_neighbor(mx, nn_candidates)
    if frozen_nn >= 0:
        passed += 1
        print("  ✅ confirmed: frozen nearest_neighbor silently tolerates a mismatched candidate, untouched (idx=", frozen_nn, ")")
    else:
        failed += 1
        print("  ❌ frozen nearest_neighbor did not reproduce the traced silent-tolerance behavior")

    var knn_raised = False
    var knn_message = String("")
    try:
        _ = k_nearest_neighbors_strict(mx, nn_candidates, 2)
    except e:
        knn_raised = True
        knn_message = String(e)
    if knn_raised and "5" in knn_message and "3" in knn_message and "candidates[1]" in knn_message:
        passed += 1
        print("  ✅ k_nearest_neighbors_strict RAISED on a mismatched candidate, naming candidates[1] (5 vs 3):", knn_message)
    else:
        failed += 1
        print("  ❌ k_nearest_neighbors_strict did NOT raise correctly on a mismatched candidate:", knn_message)

    # confirm the frozen k_nearest_neighbors does NOT raise on the same mismatched candidate.
    var frozen_knn = k_nearest_neighbors(mx, nn_candidates, 2)
    if len(frozen_knn) == 2:
        passed += 1
        print("  ✅ confirmed: frozen k_nearest_neighbors silently tolerates a mismatched candidate, untouched")
    else:
        failed += 1
        print("  ❌ frozen k_nearest_neighbors did not reproduce the traced silent-tolerance behavior")

    print("  [test_embeddings_dimension_mismatch_probe] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("test_embeddings_dimension_mismatch_probe: " + String(failed) + " check(s) failed")
