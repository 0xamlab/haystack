"""test_sparse_numerics_csr.mojo — known-value tests for the CSR/CSC layouts.

Hand-written. The assertions target the failures that are silent rather than loud:
a duplicate coordinate that gets overwritten instead of summed, a coordinate outside
the declared shape that changes the matrix instead of being dropped, a coalesce that
is not idempotent, and a structurally broken `indptr` that reads past the end of
`values` instead of being rejected.

`sparse.SparseMatrixCOO.to_dense` is the frozen oracle for duplicate handling — it
accumulates with `+=` — so the dense image of a CSR built from a duplicate-bearing COO
is compared against it element by element rather than against a number typed here.
`sparse.sparse_matvec` is the second oracle, for the multiply.
"""
from sparse import COOEntry, SparseMatrixCOO, sparse_matvec
from sparse_numerics.csr import (
    CSR_ERR_DIMENSION_TOO_LARGE,
    MAX_CSR_DIM,
    dims_fit,
    CSCMatrix,
    CSRMatrix,
    CSRResult,
    CSRVectorResult,
    CSR_ERR_INDEX_OUT_OF_RANGE,
    CSR_ERR_INDPTR_LENGTH,
    CSR_ERR_INDPTR_NOT_MONOTONIC,
    CSR_ERR_INDPTR_START,
    CSR_ERR_INDPTR_TAIL,
    CSR_ERR_INVALID_DIMENSIONS,
    CSR_ERR_LENGTH_MISMATCH,
    CSR_ERR_SHAPE,
    CSR_LAYOUT_COL,
    CSR_LAYOUT_ROW,
    CSR_OK,
    SparseSlice,
    csc_col_slice,
    csc_col_slice_driver,
    csc_from_csr,
    csr_build_from_triplets,
    csr_coalesce,
    csr_coalesce_driver,
    csr_from_arrays,
    csr_from_coo,
    csr_from_csc,
    csr_from_dense,
    csr_from_dense_driver,
    csr_matvec,
    csr_matvec_driver,
    csr_row_counts,
    csr_row_counts_driver,
    csr_row_slice,
    csr_row_slice_driver,
    csr_sort_indices,
    csr_status_name,
    csr_to_coo,
    csr_to_dense,
    csr_to_dense_driver,
    csr_transpose,
    csr_transpose_driver,
    csr_validate,
    csr_validate_flat,
)


fn _ints(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


fn _ints2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


fn _ints4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


fn _same_ints(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _same_floats(a: List[Float64], b: List[Float64]) -> Bool:
    """Exact equality: every value here is a sum of small integers and halves, so a
    tolerance would hide a genuine mis-accumulation."""
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


fn _flatten(nested: List[List[Float64]]) -> List[Float64]:
    var out = List[Float64]()
    for i in range(len(nested)):
        for j in range(len(nested[i])):
            out.append(nested[i][j])
    return out^


fn _demo_coo() -> SparseMatrixCOO:
    """A 3x4 COO with two duplicate pairs and four out-of-range coordinates.

    (0,1) appears twice (2 + 3 = 5) and (1,0) twice (-1 + 1.5 = 0.5). Rows 9 and -1 and
    columns 7 and -2 do not exist in a 3x4 matrix; COO accepted them anyway, which is
    exactly the input CSR construction has to survive.
    """
    var coo = SparseMatrixCOO(3, 4)
    coo.add_entry(0, 1, 2.0)
    coo.add_entry(2, 3, 5.0)
    coo.add_entry(0, 1, 3.0)
    coo.add_entry(1, 0, -1.0)
    coo.add_entry(9, 0, 100.0)
    coo.add_entry(0, 7, 50.0)
    coo.add_entry(-1, 2, 7.0)
    coo.add_entry(1, -2, 8.0)
    coo.add_entry(1, 0, 1.5)
    return coo^


fn _oracle_coo() -> SparseMatrixCOO:
    """`_demo_coo` with only the in-range entries — the part that has a dense image."""
    var coo = SparseMatrixCOO(3, 4)
    coo.add_entry(0, 1, 2.0)
    coo.add_entry(2, 3, 5.0)
    coo.add_entry(0, 1, 3.0)
    coo.add_entry(1, 0, -1.0)
    coo.add_entry(1, 0, 1.5)
    return coo^


fn _matrix_a() -> CSRMatrix:
    """A = [[1, 0, 2], [0, 3, 0]] as a 2x3 CSR with no flags claimed."""
    var indptr = _ints(0, 2, 3)
    var indices = _ints(0, 2, 1)
    var values = List[Float64]()
    values.append(1.0)
    values.append(2.0)
    values.append(3.0)
    return csr_from_arrays(indptr, indices, values, 2, 3)


fn main() raises:
    var passed = 0
    var failed = 0

    # ── the frozen to_dense is the oracle for duplicates ──────────────────────
    # Every number below comes from the frozen kernel, not from this file: if
    # csr_from_coo kept the last duplicate instead of summing, or folded an
    # out-of-range coordinate into a real cell, these two images would differ.
    var demo = _demo_coo()
    var csr = csr_from_coo(demo)
    var oracle_flat = _flatten(_oracle_coo().to_dense())
    var csr_flat = csr_to_dense(csr)
    if len(csr_flat) == 12 and _same_floats(csr_flat, oracle_flat):
        passed += 1
        print(
            "  ✅ CSR dense image equals the frozen to_dense of the in-range COO"
        )
    else:
        failed += 1
        print("  ❌ CSR/to_dense disagree:", len(csr_flat), len(oracle_flat))

    # ── and that image is the hand-computed one ──────────────────────────────
    # [[0,5,0,0],[0.5,0,0,0],[0,0,0,5]] — 2+3 and -1+1.5, with 100, 50, 7 and 8 gone.
    var expected_dense = List[Float64]()
    expected_dense.append(0.0)
    expected_dense.append(5.0)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(0.5)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(0.0)
    expected_dense.append(5.0)
    if _same_floats(csr_flat, expected_dense):
        passed += 1
        print("  ✅ duplicates summed to 5 and 0.5; four stray coordinates dropped")
    else:
        failed += 1
        print("  ❌ dense image wrong:", csr_flat[1], csr_flat[4])

    # ── the compressed structure is canonical, and nnz counts merged cells ────
    # COO reported nnz 9 (it counts duplicates and strays); the CSR stores 3.
    var want_values = List[Float64]()
    want_values.append(5.0)
    want_values.append(0.5)
    want_values.append(5.0)
    if (
        demo.nnz() == 9
        and csr.nnz() == 3
        and csr.is_canonical()
        and _same_ints(csr.indptr, _ints4(0, 1, 2, 3))
        and _same_ints(csr.indices, _ints(1, 0, 3))
        and _same_floats(csr.values, want_values)
    ):
        passed += 1
        print("  ✅ indptr [0,1,2,3], indices [1,0,3], values [5,0.5,5]; nnz 3 not 9")
    else:
        failed += 1
        print("  ❌ CSR structure wrong: nnz", csr.nnz(), "canonical", csr.is_canonical())

    # ── the triplet driver reports what it dropped ────────────────────────────
    # Silently resizing to fit a stray coordinate, or crashing on it, are the two
    # outcomes this count exists to rule out.
    var t_rows = List[Int]()
    var t_cols = List[Int]()
    var t_vals = List[Float64]()
    for k in range(len(demo.entries)):
        ref e = demo.entries[k]
        t_rows.append(e.row)
        t_cols.append(e.col)
        t_vals.append(e.val)
    var built = csr_build_from_triplets(t_rows, t_cols, t_vals, 3, 4)
    if (
        built.status == CSR_OK
        and built.skipped == 4
        and built.nnz == 3
        and built.layout == CSR_LAYOUT_ROW
        and built.coalesced
        and built.sorted_indices
        and _same_floats(built.values, want_values)
    ):
        passed += 1
        print("  ✅ triplet driver: 4 out-of-range entries reported, 3 stored")
    else:
        failed += 1
        print("  ❌ triplet driver wrong:", built.status, built.skipped, built.nnz)

    # ── coalesce is idempotent, on input that actually needs it ───────────────
    # Row 0 = [(2,1), (0,2), (2,3)]: unsorted, with (0,2) duplicated. Canonical form is
    # indices [0,2] values [2, 4]; running it again must change nothing.
    var raw_indptr = _ints(0, 3, 3)
    var raw_indices = _ints(2, 0, 2)
    var raw_values = List[Float64]()
    raw_values.append(1.0)
    raw_values.append(2.0)
    raw_values.append(3.0)
    var once = csr_coalesce_driver(raw_indptr, raw_indices, raw_values, 2, 3)
    var twice = csr_coalesce_driver(once.indptr, once.indices, once.values, 2, 3)
    var want_coalesced = List[Float64]()
    want_coalesced.append(2.0)
    want_coalesced.append(4.0)
    var want_indices = List[Int]()
    want_indices.append(0)
    want_indices.append(2)
    if (
        once.status == CSR_OK
        and _same_ints(once.indptr, _ints(0, 2, 2))
        and _same_ints(once.indices, want_indices)
        and _same_floats(once.values, want_coalesced)
        and _same_ints(twice.indptr, once.indptr)
        and _same_ints(twice.indices, once.indices)
        and _same_floats(twice.values, once.values)
    ):
        passed += 1
        print("  ✅ coalesce sorts and sums (1+3=4), and is idempotent")
    else:
        failed += 1
        print("  ❌ coalesce wrong:", once.nnz, len(twice.values))

    # ── an explicit zero survives coalescing ─────────────────────────────────
    # 5 + (-5) leaves a stored zero. Dropping it would silently change the pattern any
    # symbolic factorisation was computed from, so nnz stays 1 while the value is 0.
    var cancel = SparseMatrixCOO(1, 1)
    cancel.add_entry(0, 0, 5.0)
    cancel.add_entry(0, 0, -5.0)
    var cancelled = csr_from_coo(cancel)
    var cancel_dense = csr_to_dense(cancelled)
    if (
        cancelled.nnz() == 1
        and cancelled.values[0] == 0.0
        and len(cancel_dense) == 1
        and cancel_dense[0] == 0.0
    ):
        passed += 1
        print("  ✅ cancelling duplicates leave a stored zero, not a dropped cell")
    else:
        failed += 1
        print("  ❌ zero handling wrong:", cancelled.nnz())

    # ── duplicates are summed in COO insertion order, not just as a set ──────
    # 1e16 + 1 rounds back to 1e16, so (1e16, 1, -1e16) sums to 0 in insertion order and
    # to 1 in any other order. to_dense adds in insertion order; a sort inside coalesce
    # that were not stable would reorder these three and land on 1.0 — a wrong answer
    # no set-level assertion can see. The row also needs sorting (column 1 before
    # column 0), so the stable path is genuinely exercised.
    var fp = SparseMatrixCOO(1, 2)
    fp.add_entry(0, 1, 1e16)
    fp.add_entry(0, 0, 7.0)
    fp.add_entry(0, 1, 1.0)
    fp.add_entry(0, 1, -1e16)
    var fp_csr = csr_from_coo(fp)
    var fp_dense = csr_to_dense(fp_csr)
    var fp_oracle = _flatten(fp.to_dense())
    if (
        fp_csr.nnz() == 2
        and _same_floats(fp_dense, fp_oracle)
        and fp_dense[0] == 7.0
        and fp_dense[1] == 0.0
    ):
        passed += 1
        print("  ✅ duplicate summation order matches to_dense exactly (0.0, not 1.0)")
    else:
        failed += 1
        print("  ❌ coalesce reordered duplicates:", fp_dense[1], fp_oracle[1])

    # ── COO -> CSR -> COO -> CSR is stable ───────────────────────────────────
    # The second CSR must be bit-identical, or the canonical form is not a fixed point
    # and no two matrices can ever be compared or cached by their arrays.
    var back_to_coo = csr_to_coo(csr)
    var csr_again = csr_from_coo(back_to_coo)
    if (
        back_to_coo.nnz() == 3
        and back_to_coo.nrows == 3
        and back_to_coo.ncols == 4
        and _same_ints(csr_again.indptr, csr.indptr)
        and _same_ints(csr_again.indices, csr.indices)
        and _same_floats(csr_again.values, csr.values)
        and csr_again.is_canonical()
    ):
        passed += 1
        print("  ✅ COO -> CSR -> COO -> CSR reaches the same arrays")
    else:
        failed += 1
        print("  ❌ round trip drifted:", back_to_coo.nnz(), csr_again.nnz())

    # ── validate: one broken matrix per defect code ──────────────────────────
    var no_ints = List[Int]()
    var no_floats = List[Float64]()
    var one_index = List[Int]()
    one_index.append(0)
    var one_value = List[Float64]()
    one_value.append(1.0)
    var three_values = List[Float64]()
    three_values.append(1.0)
    three_values.append(2.0)
    three_values.append(3.0)
    var head = List[Int]()
    head.append(0)

    # A negative dimension is not a small matrix.
    var bad_shape = csr_validate_flat(head, no_ints, no_floats, -1, 3)
    # indices and values must pair up; the shorter one would be read past its end.
    var bad_pair = csr_validate_flat(
        _ints(0, 3, 3), _ints4(0, 1, 2, 2), three_values, 2, 3
    )
    # indptr must have exactly nrows+1 slots, or row nrows-1 has no end.
    var bad_len = csr_validate_flat(
        _ints(0, 1, 1), one_index, one_value, 3, 3
    )
    # A nonzero head means values[0] belongs to no row.
    var bad_start = csr_validate_flat(_ints(1, 2, 3), _ints(0, 1, 2), three_values, 2, 3)
    # A decreasing step also means indptr[1] = 2 > nnz = 1, so row 0 would read
    # values[1] — one past the end, which is a process crash and not an exception.
    var bad_mono = csr_validate_flat(_ints(0, 2, 1), one_index, one_value, 2, 3)
    # The tail must be nnz, or values beyond it are stored but unreachable.
    var bad_tail = csr_validate_flat(_ints(0, 1, 2), _ints(0, 1, 2), three_values, 2, 3)
    # A column index outside the declared width would crash to_dense.
    var far_index = List[Int]()
    far_index.append(5)
    var bad_index = csr_validate_flat(_ints2(0, 1), far_index, one_value, 1, 2)
    var sound = csr_validate(csr)

    if (
        bad_shape == CSR_ERR_SHAPE
        and bad_pair == CSR_ERR_LENGTH_MISMATCH
        and bad_len == CSR_ERR_INDPTR_LENGTH
        and bad_start == CSR_ERR_INDPTR_START
        and bad_mono == CSR_ERR_INDPTR_NOT_MONOTONIC
        and bad_tail == CSR_ERR_INDPTR_TAIL
        and bad_index == CSR_ERR_INDEX_OUT_OF_RANGE
        and sound == CSR_OK
    ):
        passed += 1
        print("  ✅ validate returns a distinct code for each of the 7 defects, 0 for sound")
    else:
        failed += 1
        print(
            "  ❌ validate codes wrong:",
            bad_shape,
            bad_pair,
            bad_len,
            bad_start,
            bad_mono,
            bad_tail,
            bad_index,
            sound,
        )

    # ── every status code has its own name ───────────────────────────────────
    # A duplicated name in the lookup table is invisible until someone debugs the
    # wrong array, so the names are checked for collisions rather than spot-checked.
    var codes = List[Int]()
    codes.append(CSR_OK)
    codes.append(CSR_ERR_SHAPE)
    codes.append(CSR_ERR_LENGTH_MISMATCH)
    codes.append(CSR_ERR_INDPTR_LENGTH)
    codes.append(CSR_ERR_INDPTR_START)
    codes.append(CSR_ERR_INDPTR_NOT_MONOTONIC)
    codes.append(CSR_ERR_INDPTR_TAIL)
    codes.append(CSR_ERR_INDEX_OUT_OF_RANGE)
    codes.append(CSR_ERR_INVALID_DIMENSIONS)
    var names_distinct = True
    for i in range(len(codes)):
        if csr_status_name(codes[i]) == "unknown_status":
            names_distinct = False
        for j in range(i + 1, len(codes)):
            if csr_status_name(codes[i]) == csr_status_name(codes[j]):
                names_distinct = False
    if names_distinct and csr_status_name(99) == "unknown_status":
        passed += 1
        print("  ✅ all 9 status codes have distinct names; an unknown code says so")
    else:
        failed += 1
        print("  ❌ status names collide")

    # ── transpose against a hand-computed A^T ────────────────────────────────
    # A = [[1,0,2],[0,3,0]] so A^T = [[1,0],[0,3],[2,0]].
    var a = _matrix_a()
    var at = csr_transpose(a)
    var at_values = List[Float64]()
    at_values.append(1.0)
    at_values.append(3.0)
    at_values.append(2.0)
    var at_dense = List[Float64]()
    at_dense.append(1.0)
    at_dense.append(0.0)
    at_dense.append(0.0)
    at_dense.append(3.0)
    at_dense.append(2.0)
    at_dense.append(0.0)
    if (
        at.nrows == 3
        and at.ncols == 2
        and _same_ints(at.indptr, _ints4(0, 1, 2, 3))
        and _same_ints(at.indices, _ints(0, 1, 0))
        and _same_floats(at.values, at_values)
        and _same_floats(csr_to_dense(at), at_dense)
        and at.sorted_indices
    ):
        passed += 1
        print("  ✅ transpose of [[1,0,2],[0,3,0]] is [[1,0],[0,3],[2,0]]")
    else:
        failed += 1
        print("  ❌ transpose wrong:", at.nrows, at.ncols, at.nnz())

    # ── transpose twice is the identity, and it is what sorts the indices ────
    var att = csr_transpose(at)
    var sorted_a = csr_sort_indices(a)
    if (
        _same_ints(att.indptr, a.indptr)
        and _same_ints(att.indices, a.indices)
        and _same_floats(att.values, a.values)
        and _same_ints(sorted_a.indices, a.indices)
        and sorted_a.sorted_indices
    ):
        passed += 1
        print("  ✅ transpose twice restores A, and is how sort_indices is built")
    else:
        failed += 1
        print("  ❌ double transpose is not the identity")

    # ── sort_indices actually reorders an unsorted row ───────────────────────
    # Row 0 = [(2,1),(0,2)] must come back as [(0,2),(2,1)] with values moved too;
    # moving the indices and leaving the values behind is the classic silent bug.
    var two_values = List[Float64]()
    two_values.append(1.0)
    two_values.append(2.0)
    var unsorted = csr_from_arrays(_ints(0, 2, 2), _ints2(2, 0), two_values, 2, 3)
    var now_sorted = csr_sort_indices(unsorted)
    var want_sorted_values = List[Float64]()
    want_sorted_values.append(2.0)
    want_sorted_values.append(1.0)
    if (
        _same_ints(now_sorted.indices, _ints2(0, 2))
        and _same_floats(now_sorted.values, want_sorted_values)
        and _same_floats(csr_to_dense(now_sorted), csr_to_dense(unsorted))
    ):
        passed += 1
        print("  ✅ sort_indices carries the values with their indices")
    else:
        failed += 1
        print("  ❌ sort_indices lost the pairing")

    # ── CSC gives O(1) column access and round-trips ─────────────────────────
    var csc = csc_from_csr(a)
    var col1 = csc_col_slice(csc, 1)
    var back = csr_from_csc(csc)
    var want_col1 = List[Float64]()
    want_col1.append(3.0)
    if (
        csc.nrows == 2
        and csc.ncols == 3
        and _same_ints(csc.colptr, _ints4(0, 1, 2, 3))
        and csc.col_nnz(0) == 1
        and csc.col_nnz(2) == 1
        and col1.status == CSR_OK
        and col1.nnz == 1
        and col1.indices[0] == 1
        and _same_floats(col1.values, want_col1)
        and _same_ints(back.indptr, a.indptr)
        and _same_ints(back.indices, a.indices)
        and _same_floats(back.values, a.values)
    ):
        passed += 1
        print("  ✅ CSC keeps A's 2x3 shape, column 1 is (row 1, 3.0), CSR round-trips")
    else:
        failed += 1
        print("  ❌ CSC wrong:", csc.nrows, csc.ncols, col1.status)

    # ── row slice and per-row counts ─────────────────────────────────────────
    var row0 = csr_row_slice(csr, 0)
    var row2 = csr_row_slice(csr, 2)
    var counts = csr_row_counts(csr)
    if (
        row0.status == CSR_OK
        and row0.nnz == 1
        and row0.indices[0] == 1
        and row0.values[0] == 5.0
        and row2.indices[0] == 3
        and row2.values[0] == 5.0
        and _same_ints(counts, _ints(1, 1, 1))
    ):
        passed += 1
        print("  ✅ row slices return (col, value) pairs; row counts are [1,1,1]")
    else:
        failed += 1
        print("  ❌ row slice wrong:", row0.status, row0.nnz)

    # ── matvec agrees with the frozen COO multiply ───────────────────────────
    # A @ [1,2,3] = [1*1 + 2*3, 3*2] = [7, 6].
    var x = List[Float64]()
    x.append(1.0)
    x.append(2.0)
    x.append(3.0)
    var product = csr_matvec(a, x)
    var frozen_product = sparse_matvec(csr_to_coo(a), x)
    var want_product = List[Float64]()
    want_product.append(7.0)
    want_product.append(6.0)
    if (
        product.status == CSR_OK
        and product.length == 2
        and _same_floats(product.values, want_product)
        and _same_floats(product.values, frozen_product)
    ):
        passed += 1
        print("  ✅ CSR matvec [7,6] matches the frozen COO sparse_matvec")
    else:
        failed += 1
        print("  ❌ matvec wrong:", product.status, product.length)

    # ── dense round trip, and the zero-row shape that the frozen kernel loses ─
    # sparse_from_dense infers ncols from row 0, so a 0x5 dense would come back 0x0;
    # csr_from_dense re-imposes the declared shape.
    var rebuilt = csr_from_dense(expected_dense, 3, 4, 1e-15)
    var no_rows = csr_from_dense(List[Float64](), 0, 5, 1e-15)
    if (
        _same_ints(rebuilt.indptr, csr.indptr)
        and _same_ints(rebuilt.indices, csr.indices)
        and _same_floats(rebuilt.values, csr.values)
        and no_rows.nrows == 0
        and no_rows.ncols == 5
        and csr_validate(no_rows) == CSR_OK
    ):
        passed += 1
        print("  ✅ dense -> CSR reproduces the arrays; a 0x5 dense stays 0x5")
    else:
        failed += 1
        print("  ❌ from_dense wrong:", rebuilt.nnz(), no_rows.ncols)

    # ── a five-element list with every Int set to 5 must be rejected, not read ─
    # This is the shape the generated contract suite calls every exported function
    # with: indptr of length 5 for a claimed 5 rows needs 6 slots, so indexing here
    # would run off the end of values and take the worker process with it.
    var five_ints = List[Int]()
    var five_floats = List[Float64]()
    for i in range(5):
        five_ints.append(i + 1)
        five_floats.append(0.5)
    var guarded_dense = csr_to_dense_driver(five_ints, five_ints, five_floats, 5, 5)
    var guarded_transpose = csr_transpose_driver(five_ints, five_ints, five_floats, 5, 5)
    var guarded_counts = csr_row_counts_driver(
        five_ints, five_ints, five_floats, 5, 5
    )
    if (
        guarded_dense.status == CSR_ERR_INDPTR_LENGTH
        and len(guarded_dense.values) == 0
        and guarded_transpose.status == CSR_ERR_INDPTR_LENGTH
        and guarded_transpose.nrows == 0
        and len(guarded_transpose.values) == 0
        and guarded_counts.status == CSR_ERR_INDPTR_LENGTH
        and len(guarded_counts.values) == 0
    ):
        passed += 1
        print("  ✅ the 5-element / all-fives call is rejected with indptr_length")
    else:
        failed += 1
        print("  ❌ dimension guard missing:", guarded_dense.status, guarded_transpose.status)

    # ── an empty answer that is real reports OK, not a defect ────────────────
    # A 0x0 matrix genuinely has an empty dense image; the status is what separates it
    # from the rejected call above, which is why the driver carries one.
    var zero_by_zero = csr_to_dense_driver(
        head, List[Int](), List[Float64](), 0, 0
    )
    var zero_counts = csr_row_counts_driver(
        head, List[Int](), List[Float64](), 0, 0
    )
    if (
        zero_by_zero.status == CSR_OK
        and zero_by_zero.length == 0
        and zero_counts.status == CSR_OK
        and zero_counts.length == 0
    ):
        passed += 1
        print("  ✅ a 0x0 matrix's empty dense image reports ok, not a defect")
    else:
        failed += 1
        print("  ❌ real emptiness confused with rejection:", zero_by_zero.status)

    # ── absent answers stay absent across the drivers ────────────────────────
    var missing_row = csr_row_slice_driver(a.indptr, a.indices, a.values, 2, 3, 5)
    var missing_col = csc_col_slice_driver(csc.colptr, csc.row_indices, csc.values, 2, 3, 9)
    var short_x = List[Float64]()
    short_x.append(1.0)
    var bad_product = csr_matvec_driver(a.indptr, a.indices, a.values, 2, 3, short_x)
    var bad_triplets = csr_build_from_triplets(five_ints, one_index, five_floats, 5, 5)
    var bad_dense = csr_from_dense_driver(five_floats, 5, 5, 1e-15)
    if (
        missing_row.status == CSR_ERR_INVALID_DIMENSIONS
        and missing_row.nnz == 0
        and len(missing_row.values) == 0
        and missing_col.status == CSR_ERR_INVALID_DIMENSIONS
        and bad_product.status == CSR_ERR_INVALID_DIMENSIONS
        and len(bad_product.values) == 0
        and bad_triplets.status == CSR_ERR_INVALID_DIMENSIONS
        and bad_dense.status == CSR_ERR_INVALID_DIMENSIONS
    ):
        passed += 1
        print("  ✅ a row that does not exist, a mis-sized vector and a mis-declared")
        print("     shape all report invalid_dimensions with no numbers attached")
    else:
        failed += 1
        print(
            "  ❌ absent answers leaked:",
            missing_row.status,
            bad_product.status,
            bad_triplets.status,
            bad_dense.status,
        )

    # ── an invalid matrix has no transpose, no dense image and no CSC ─────────
    # Returning the 0x0 empty rather than a best-effort matrix is what keeps a broken
    # indptr from becoming a plausible-looking result two calls later.
    var broken = csr_from_arrays(_ints(0, 2, 1), one_index, one_value, 2, 3)
    var broken_t = csr_transpose(broken)
    var broken_csc = csc_from_csr(broken)
    if (
        csr_validate(broken) == CSR_ERR_INDPTR_NOT_MONOTONIC
        and broken_t.nrows == 0
        and broken_t.ncols == 0
        and broken_t.nnz() == 0
        and broken_csc.nrows == 0
        and broken_csc.ncols == 0
        and len(csr_to_dense(broken)) == 0
        and csr_to_coo(broken).nnz() == 0
        and csr_coalesce(broken).nnz() == 0
    ):
        passed += 1
        print("  ✅ a non-monotonic indptr yields no transpose, dense, COO or CSC")
    else:
        failed += 1
        print("  ❌ a broken matrix produced results:", broken_t.nrows, broken_csc.ncols)

    # ── a wrapping multiply is not a bound ────────────────────────────────────
    # `rows * cols != len(dense)` was the guard, and 3 * 6148914691236517206 == 2
    # EXACTLY in 64-bit, so it passed for a 2-element list and the loop then read
    # dense[i*cols + j] far past the end. That is an uncatchable process crash reachable
    # from the SDK through csr_from_dense_driver, so the check must not multiply.
    var two = List[Float64]()
    two.append(1.0)
    two.append(2.0)
    if not dims_fit(3, 6148914691236517206, 2):
        passed += 1
        print("  \u2705 dims_fit rejects a shape whose product WRAPS to the real length")
    else:
        failed += 1
        print("  \u274c dims_fit accepted an overflowing shape")

    if csr_from_dense_driver(two, 3, 6148914691236517206, 1e-15).status != CSR_OK:
        passed += 1
        print("  \u2705 csr_from_dense_driver rejects it instead of crashing the worker")
    else:
        failed += 1
        print("  \u274c csr_from_dense_driver accepted the overflowing shape")

    # ── and it still accepts every legitimate shape ───────────────────────────
    var six = List[Float64]()
    for i in range(6):
        six.append(Float64(i))
    if (
        dims_fit(2, 3, 6)
        and dims_fit(0, 0, 0)
        and dims_fit(0, 5, 0)
        and dims_fit(1, 6, 6)
        and not dims_fit(2, 3, 7)
        and not dims_fit(-1, 3, 6)
    ):
        passed += 1
        print("  \u2705 dims_fit still accepts real shapes and rejects mismatched ones")
    else:
        failed += 1
        print("  \u274c dims_fit is now too strict")

    var built_ok = csr_from_dense_driver(six, 2, 3, 1e-15)
    if built_ok.status == CSR_OK and built_ok.nrows == 2 and built_ok.ncols == 3:
        passed += 1
        print("  \u2705 a real 2x3 dense matrix still builds")
    else:
        failed += 1
        print("  \u274c a legitimate build regressed:", built_ok.status)

    # ── a consistent shape can still be an allocation bomb ────────────────────
    # An empty matrix declaring 10^12 columns passes EVERY structural check — the shape is
    # consistent — then asks csr_transpose for an 8 TB pointer array, because a transpose
    # allocates one entry per column regardless of nnz. Only a declared ceiling catches it.
    var lone = List[Int]()
    lone.append(0)
    var no_idx = List[Int]()
    var no_val = List[Float64]()
    var bomb = csr_transpose_driver(lone, no_idx, no_val, 0, 1000000000000)
    if bomb.status == CSR_ERR_DIMENSION_TOO_LARGE:
        passed += 1
        print("  \u2705 a 10^12-column empty matrix is refused, not allocated")
    else:
        failed += 1
        print("  \u274c allocation bomb not caught, status =", bomb.status)

    if MAX_CSR_DIM == 67108864 and not dims_fit(MAX_CSR_DIM + 1, 1, MAX_CSR_DIM + 1):
        passed += 1
        print("  \u2705 the ceiling is 2^26 and dims_fit enforces it")
    else:
        failed += 1
        print("  \u274c MAX_CSR_DIM not enforced")

    print("  [sparse_numerics.csr] Passed:", passed, "Failed:", failed)
