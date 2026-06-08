"""Tests for Wave 33 — Physics, Sorting Algorithms, Vector Embeddings."""

from physics import (
    kinematic_distance,
    kinematic_velocity,
    kinetic_energy,
    potential_energy,
    momentum,
    gravitational_force,
    projectile_range,
    projectile_max_height,
    projectile_time,
    work,
    power,
    elastic_collision_v1,
)
from sorting import (
    quicksort,
    mergesort,
    heapsort,
    insertion_sort,
    selection_sort,
    bubble_sort,
    counting_sort_int,
    is_sorted,
    reverse_list,
    nth_smallest,
)
from embeddings import (
    dot_product,
    cosine_similarity,
    euclidean_distance,
    manhattan_distance,
    normalize_vector,
    centroid,
    nearest_neighbor,
    k_nearest_neighbors,
    cosine_similarity_matrix,
    vector_add,
    vector_scale,
    vector_magnitude,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Physics tests ────────────────────────────────────────────────────────────


fn test_physics() raises:
    print("  Testing physics...")
    var passed = 0

    # 1. kinematic_distance: free fall from rest, a=10, t=2 → d = 0 + 0.5*10*4 = 20
    _assert_close(kinematic_distance(0.0, 10.0, 2.0), 20.0, 1e-9, "kinematic_distance(0,10,2)")
    passed += 1

    # 2. kinematic_distance: v0=5, a=2, t=3 → 5*3 + 0.5*2*9 = 15+9 = 24
    _assert_close(kinematic_distance(5.0, 2.0, 3.0), 24.0, 1e-9, "kinematic_distance(5,2,3)")
    passed += 1

    # 3. kinematic_velocity: v0=0, a=10, t=5 → 50
    _assert_close(kinematic_velocity(0.0, 10.0, 5.0), 50.0, 1e-9, "kinematic_velocity(0,10,5)")
    passed += 1

    # 4. kinematic_velocity: v0=10, a=-9.81, t=0 → 10
    _assert_close(kinematic_velocity(10.0, -9.81, 0.0), 10.0, 1e-9, "kinematic_velocity at t=0")
    passed += 1

    # 5. kinetic_energy: m=2, v=3 → 0.5*2*9 = 9
    _assert_close(kinetic_energy(2.0, 3.0), 9.0, 1e-9, "kinetic_energy(2,3)")
    passed += 1

    # 6. potential_energy: m=1, h=10 → 1*9.81*10 = 98.1
    _assert_close(potential_energy(1.0, 10.0), 98.1, 0.01, "potential_energy(1,10)")
    passed += 1

    # 7. momentum: m=5, v=10 → 50
    _assert_close(momentum(5.0, 10.0), 50.0, 1e-9, "momentum(5,10)")
    passed += 1

    # 8. gravitational_force: basic sanity check
    var gf = gravitational_force(1e10, 1e10, 1.0)
    _assert_close(gf, 6.674e-11 * 1e10 * 1e10, 1e-2, "gravitational_force")
    passed += 1

    # 9. projectile_range at 45° (maximum range): R = v0²*sin(90)/g = 400/9.81
    var pr = projectile_range(20.0, 45.0)
    _assert_close(pr, 400.0 / 9.81, 0.1, "projectile_range(20,45)")
    passed += 1

    # 10. projectile_max_height at 90°: H = v0²*1/(2g) = 400/19.62 ≈ 20.387
    var pmh = projectile_max_height(20.0, 90.0)
    _assert_close(pmh, 400.0 / 19.62, 0.1, "projectile_max_height(20,90)")
    passed += 1

    # 11. projectile_time at 90°: T = 2*20*1/9.81 ≈ 4.077
    var pt = projectile_time(20.0, 90.0)
    _assert_close(pt, 40.0 / 9.81, 0.01, "projectile_time(20,90)")
    passed += 1

    # 12. work: F=10, d=5, angle=0 → 50
    _assert_close(work(10.0, 5.0, 0.0), 50.0, 1e-9, "work(10,5,0)")
    passed += 1

    # 13. work at 60°: F=10, d=5, cos(60°)=0.5 → 25
    _assert_close(work(10.0, 5.0, 60.0), 25.0, 0.01, "work(10,5,60)")
    passed += 1

    # 14. power: W=100, t=5 → 20
    _assert_close(power(100.0, 5.0), 20.0, 1e-9, "power(100,5)")
    passed += 1

    # 15. elastic_collision: equal masses → velocities swap
    # m1=m2=1, v1=5, v2=0 → v1' = ((1-1)*5 + 2*1*0)/(1+1) = 0
    _assert_close(elastic_collision_v1(1.0, 1.0, 5.0, 0.0), 0.0, 1e-9, "elastic_collision equal mass")
    passed += 1

    # 16. elastic_collision: m1=2, m2=1, v1=3, v2=0 → v1' = ((2-1)*3 + 0)/3 = 1
    _assert_close(elastic_collision_v1(2.0, 1.0, 3.0, 0.0), 1.0, 1e-9, "elastic_collision m1>m2")
    passed += 1

    # 17. projectile_range at 0° → 0 (straight horizontal gives 0 height)
    _assert_close(projectile_range(20.0, 0.0), 0.0, 1e-9, "projectile_range(20,0)")
    passed += 1

    print("    Physics: " + String(passed) + " passed")


# ── Sorting tests ────────────────────────────────────────────────────────────


fn test_sorting() raises:
    print("  Testing sorting...")
    var passed = 0

    # Build test data
    var data1 = List[Float64]()
    data1.append(3.0)
    data1.append(1.0)
    data1.append(4.0)
    data1.append(1.0)
    data1.append(5.0)

    var data2 = List[Float64]()
    data2.append(5.0)
    data2.append(4.0)
    data2.append(3.0)
    data2.append(2.0)
    data2.append(1.0)

    # 18. quicksort
    var qs = quicksort(data1)
    _assert(is_sorted(qs), "quicksort result sorted")
    passed += 1

    # 19. quicksort preserves length
    _assert(len(qs) == len(data1), "quicksort preserves length")
    passed += 1

    # 20. mergesort [5,4,3,2,1] → [1,2,3,4,5]
    var ms = mergesort(data2)
    _assert(is_sorted(ms), "mergesort result sorted")
    _assert_close(ms[0], 1.0, 1e-9, "mergesort[0]==1")
    _assert_close(ms[4], 5.0, 1e-9, "mergesort[4]==5")
    passed += 1

    # 21. mergesort preserves length
    _assert(len(ms) == len(data2), "mergesort preserves length")
    passed += 1

    # 22. heapsort
    var hs = heapsort(data1)
    _assert(is_sorted(hs), "heapsort result sorted")
    passed += 1

    # 23. heapsort preserves length
    _assert(len(hs) == len(data1), "heapsort preserves length")
    passed += 1

    # 24. insertion_sort
    var ins = insertion_sort(data1)
    _assert(is_sorted(ins), "insertion_sort result sorted")
    passed += 1

    # 25. insertion_sort preserves length
    _assert(len(ins) == len(data1), "insertion_sort preserves length")
    passed += 1

    # 26. selection_sort
    var ss = selection_sort(data1)
    _assert(is_sorted(ss), "selection_sort result sorted")
    passed += 1

    # 27. selection_sort preserves length
    _assert(len(ss) == len(data1), "selection_sort preserves length")
    passed += 1

    # 28. bubble_sort
    var bs = bubble_sort(data1)
    _assert(is_sorted(bs), "bubble_sort result sorted")
    passed += 1

    # 29. bubble_sort preserves length
    _assert(len(bs) == len(data1), "bubble_sort preserves length")
    passed += 1

    # 30. counting_sort_int: [3,1,4,1,5] → [1,1,3,4,5]
    var idata = List[Int]()
    idata.append(3)
    idata.append(1)
    idata.append(4)
    idata.append(1)
    idata.append(5)
    var cs = counting_sort_int(idata)
    _assert(cs[0] == 1, "counting_sort[0]==1")
    _assert(cs[1] == 1, "counting_sort[1]==1")
    _assert(cs[2] == 3, "counting_sort[2]==3")
    _assert(cs[3] == 4, "counting_sort[3]==4")
    _assert(cs[4] == 5, "counting_sort[4]==5")
    passed += 1

    # 31. is_sorted on sorted list
    var sorted_list = List[Float64]()
    sorted_list.append(1.0)
    sorted_list.append(2.0)
    sorted_list.append(3.0)
    _assert(is_sorted(sorted_list) == True, "is_sorted([1,2,3])==True")
    passed += 1

    # 32. is_sorted on unsorted list
    var unsorted_list = List[Float64]()
    unsorted_list.append(3.0)
    unsorted_list.append(1.0)
    unsorted_list.append(2.0)
    _assert(is_sorted(unsorted_list) == False, "is_sorted([3,1,2])==False")
    passed += 1

    # 33. reverse_list [1,2,3] → [3,2,1]
    var rev = reverse_list(sorted_list)
    _assert_close(rev[0], 3.0, 1e-9, "reverse[0]==3")
    _assert_close(rev[1], 2.0, 1e-9, "reverse[1]==2")
    _assert_close(rev[2], 1.0, 1e-9, "reverse[2]==1")
    passed += 1

    # 34. nth_smallest: [5,1,3,2,4], n=2 → 3 (0-indexed: 1,2,3,4,5 → idx 2 = 3)
    var ns_data = List[Float64]()
    ns_data.append(5.0)
    ns_data.append(1.0)
    ns_data.append(3.0)
    ns_data.append(2.0)
    ns_data.append(4.0)
    _assert_close(nth_smallest(ns_data, 2), 3.0, 1e-9, "nth_smallest([5,1,3,2,4],2)==3")
    passed += 1

    # 35. nth_smallest: 0th smallest is minimum
    _assert_close(nth_smallest(ns_data, 0), 1.0, 1e-9, "nth_smallest 0th == min")
    passed += 1

    # 36. All sorts agree on first element
    _assert_close(qs[0], ms[0], 1e-9, "quicksort[0] == mergesort[0]")
    _assert_close(hs[0], ins[0], 1e-9, "heapsort[0] == insertion[0]")
    _assert_close(ss[0], bs[0], 1e-9, "selection[0] == bubble[0]")
    passed += 1

    # 37. Empty list sort
    var empty = List[Float64]()
    var empty_sorted = quicksort(empty)
    _assert(len(empty_sorted) == 0, "quicksort empty list")
    passed += 1

    print("    Sorting: " + String(passed) + " passed")


# ── Embeddings tests ─────────────────────────────────────────────────────────


fn test_embeddings() raises:
    print("  Testing embeddings...")
    var passed = 0

    # Build test vectors
    var v10 = List[Float64]()
    v10.append(1.0)
    v10.append(0.0)

    var v01 = List[Float64]()
    v01.append(0.0)
    v01.append(1.0)

    var v123 = List[Float64]()
    v123.append(1.0)
    v123.append(2.0)
    v123.append(3.0)

    var v34 = List[Float64]()
    v34.append(3.0)
    v34.append(4.0)

    var v00 = List[Float64]()
    v00.append(0.0)
    v00.append(0.0)

    # 38. dot_product orthogonal
    _assert_close(dot_product(v10, v01), 0.0, 1e-9, "dot_product orthogonal")
    passed += 1

    # 39. dot_product self
    _assert_close(dot_product(v123, v123), 14.0, 1e-9, "dot_product([1,2,3],[1,2,3])==14")
    passed += 1

    # 40. cosine_similarity identical vectors
    _assert_close(cosine_similarity(v10, v10), 1.0, 1e-9, "cosine_similarity identical")
    passed += 1

    # 41. cosine_similarity orthogonal
    _assert_close(cosine_similarity(v10, v01), 0.0, 1e-9, "cosine_similarity orthogonal")
    passed += 1

    # 42. euclidean_distance [0,0] to [3,4] = 5
    _assert_close(euclidean_distance(v00, v34), 5.0, 1e-9, "euclidean_distance(0,0->3,4)==5")
    passed += 1

    # 43. manhattan_distance [0,0] to [3,4] = 7
    _assert_close(manhattan_distance(v00, v34), 7.0, 1e-9, "manhattan_distance(0,0->3,4)==7")
    passed += 1

    # 44. normalize_vector [3,4] → magnitude ≈ 1
    var norm34 = normalize_vector(v34)
    var norm_mag = vector_magnitude(norm34)
    _assert_close(norm_mag, 1.0, 1e-9, "normalize_vector magnitude==1")
    passed += 1

    # 45. normalize_vector preserves direction
    _assert_close(norm34[0], 0.6, 1e-9, "normalize [3,4] → [0.6,...]")
    _assert_close(norm34[1], 0.8, 1e-9, "normalize [3,4] → [...,0.8]")
    passed += 1

    # 46. centroid of [[1,0],[0,1]] ≈ [0.5, 0.5]
    var vecs = List[List[Float64]]()
    vecs.append(v10.copy())
    vecs.append(v01.copy())
    var c = centroid(vecs)
    _assert_close(c[0], 0.5, 1e-9, "centroid[0]==0.5")
    _assert_close(c[1], 0.5, 1e-9, "centroid[1]==0.5")
    passed += 1

    # 47. nearest_neighbor
    var query = List[Float64]()
    query.append(0.9)
    query.append(0.1)
    var candidates = List[List[Float64]]()
    candidates.append(v01.copy())  # idx 0
    candidates.append(v10.copy())  # idx 1
    var nn = nearest_neighbor(query, candidates)
    _assert(nn == 1, "nearest_neighbor finds [1,0] for query [0.9,0.1]")
    passed += 1

    # 48. k_nearest_neighbors returns k indices
    var knn = k_nearest_neighbors(query, candidates, 2)
    _assert(len(knn) == 2, "k_nearest_neighbors returns 2 indices")
    _assert(knn[0] == 1, "knn[0] is nearest")
    passed += 1

    # 49. cosine_similarity_matrix diagonal ≈ 1.0
    var mat_vecs = List[List[Float64]]()
    mat_vecs.append(v10.copy())
    mat_vecs.append(v01.copy())
    mat_vecs.append(v34.copy())
    var mat = cosine_similarity_matrix(mat_vecs)
    _assert_close(mat[0][0], 1.0, 1e-9, "sim_matrix diagonal [0][0]==1")
    _assert_close(mat[1][1], 1.0, 1e-9, "sim_matrix diagonal [1][1]==1")
    _assert_close(mat[2][2], 1.0, 1e-9, "sim_matrix diagonal [2][2]==1")
    passed += 1

    # 50. cosine_similarity_matrix symmetry
    _assert_close(mat[0][1], mat[1][0], 1e-9, "sim_matrix symmetric")
    passed += 1

    # 50b. zero-vector diagonal stays 0.0 (avoid false 1.0 shortcut)
    var zero = List[Float64]()
    zero.append(0.0)
    zero.append(0.0)
    var zero_mat_vecs = List[List[Float64]]()
    zero_mat_vecs.append(zero.copy())
    var zero_mat = cosine_similarity_matrix(zero_mat_vecs)
    _assert_close(zero_mat[0][0], 0.0, 1e-9, "zero-vector diagonal remains 0")
    passed += 1

    # 51. vector_magnitude [3,4] = 5
    _assert_close(vector_magnitude(v34), 5.0, 1e-9, "vector_magnitude([3,4])==5")
    passed += 1

    # 52. vector_add
    var vadd = vector_add(v10, v01)
    _assert_close(vadd[0], 1.0, 1e-9, "vector_add[0]==1")
    _assert_close(vadd[1], 1.0, 1e-9, "vector_add[1]==1")
    passed += 1

    # 53. vector_scale
    var vs = vector_scale(v34, 2.0)
    _assert_close(vs[0], 6.0, 1e-9, "vector_scale[0]==6")
    _assert_close(vs[1], 8.0, 1e-9, "vector_scale[1]==8")
    passed += 1

    # 54. euclidean_distance to self = 0
    _assert_close(euclidean_distance(v34, v34), 0.0, 1e-9, "euclidean_distance self==0")
    passed += 1

    # 55. cosine_similarity opposite direction
    var v_neg = List[Float64]()
    v_neg.append(-1.0)
    v_neg.append(0.0)
    _assert_close(cosine_similarity(v10, v_neg), -1.0, 1e-9, "cosine_similarity opposite==-1")
    passed += 1

    print("    Embeddings: " + String(passed) + " passed")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 33 tests — Physics, Sorting, Embeddings")
    test_physics()
    test_sorting()
    test_embeddings()
    print("All Wave 33 tests passed ✓")
