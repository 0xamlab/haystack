"""Tests for Wave 34 — Matrix Decompositions, Sentiment Analysis, Queue Data Structures."""

from matrix_decomp import (
    lu_decompose,
    cholesky,
    eigen_2x2,
    det_2x2,
    det_3x3,
    trace,
    is_symmetric,
    is_positive_definite,
    forward_substitution,
    back_substitution,
    solve_lu,
)
from sentiment import (
    sentiment_score,
    sentiment_label,
    word_sentiment,
    polarity,
    subjectivity,
    count_positive_words,
    count_negative_words,
    most_positive_word,
    most_negative_word,
    tokenize_lower,
)
from queue_ds import (
    PriorityQueueEntry,
    PriorityQueue,
    pq_create,
    pq_push,
    pq_pop,
    pq_peek,
    pq_size,
    pq_is_empty,
    CircularBuffer,
    cb_create,
    cb_push,
    cb_pop,
    cb_size,
    cb_is_full,
    cb_peek,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Matrix decomposition tests ───────────────────────────────────────────────


fn test_matrix_decomp() raises:
    print("  Testing matrix_decomp...")
    var passed = 0

    # 1. det_2x2 of [[1,2],[3,4]] = 1*4 - 2*3 = -2
    var m22 = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(1.0)
    r0.append(2.0)
    var r1 = List[Float64]()
    r1.append(3.0)
    r1.append(4.0)
    m22.append(r0^)
    m22.append(r1^)
    _assert_close(det_2x2(m22), -2.0, 1e-9, "det_2x2([[1,2],[3,4]])")
    passed += 1

    # 2. det_3x3 of identity == 1.0
    var id3 = List[List[Float64]]()
    for i in range(3):
        var row = List[Float64]()
        for j in range(3):
            if i == j:
                row.append(1.0)
            else:
                row.append(0.0)
        id3.append(row^)
    _assert_close(det_3x3(id3), 1.0, 1e-9, "det_3x3(identity)")
    passed += 1

    # 3. det_3x3 of known matrix [[2,1,1],[1,3,2],[1,0,0]] = 2*(0)-1*(0-2)+1*(0-3) = 0+2-3 = -1
    var m33 = List[List[Float64]]()
    var m33r0 = List[Float64]()
    m33r0.append(2.0)
    m33r0.append(1.0)
    m33r0.append(1.0)
    var m33r1 = List[Float64]()
    m33r1.append(1.0)
    m33r1.append(3.0)
    m33r1.append(2.0)
    var m33r2 = List[Float64]()
    m33r2.append(1.0)
    m33r2.append(0.0)
    m33r2.append(0.0)
    m33.append(m33r0^)
    m33.append(m33r1^)
    m33.append(m33r2^)
    _assert_close(det_3x3(m33), -1.0, 1e-9, "det_3x3 known matrix")
    passed += 1

    # 4. trace of 3×3 identity == 3.0
    _assert_close(trace(id3), 3.0, 1e-9, "trace(identity3)")
    passed += 1

    # 5. trace of [[2,1],[1,3]] == 5.0
    var tr_m = List[List[Float64]]()
    var tr0 = List[Float64]()
    tr0.append(2.0)
    tr0.append(1.0)
    var tr1 = List[Float64]()
    tr1.append(1.0)
    tr1.append(3.0)
    tr_m.append(tr0^)
    tr_m.append(tr1^)
    _assert_close(trace(tr_m), 5.0, 1e-9, "trace([[2,1],[1,3]])")
    passed += 1

    # 6. is_symmetric of symmetric matrix → True
    var sym = List[List[Float64]]()
    var s0 = List[Float64]()
    s0.append(4.0)
    s0.append(2.0)
    var s1 = List[Float64]()
    s1.append(2.0)
    s1.append(3.0)
    sym.append(s0^)
    sym.append(s1^)
    _assert(is_symmetric(sym), "is_symmetric symmetric matrix")
    passed += 1

    # 7. is_symmetric of asymmetric matrix → False
    var asym = List[List[Float64]]()
    var a0 = List[Float64]()
    a0.append(1.0)
    a0.append(2.0)
    var a1 = List[Float64]()
    a1.append(3.0)
    a1.append(4.0)
    asym.append(a0^)
    asym.append(a1^)
    _assert(not is_symmetric(asym), "is_symmetric asymmetric matrix")
    passed += 1

    # 8. cholesky of [[4,2],[2,3]] — L*L^T ≈ A
    var spd = List[List[Float64]]()
    var sp0 = List[Float64]()
    sp0.append(4.0)
    sp0.append(2.0)
    var sp1 = List[Float64]()
    sp1.append(2.0)
    sp1.append(3.0)
    spd.append(sp0^)
    spd.append(sp1^)
    var L = cholesky(spd)
    _assert(len(L) == 2, "cholesky returns 2×2")
    # Verify L*L^T ≈ A
    # (0,0): L[0][0]*L[0][0] + L[0][1]*L[0][1]
    var llt00 = L[0][0] * L[0][0] + L[0][1] * L[0][1]
    var llt01 = L[0][0] * L[1][0] + L[0][1] * L[1][1]
    var llt10 = L[1][0] * L[0][0] + L[1][1] * L[0][1]
    var llt11 = L[1][0] * L[1][0] + L[1][1] * L[1][1]
    _assert_close(llt00, 4.0, 1e-9, "cholesky LLT[0][0]")
    _assert_close(llt01, 2.0, 1e-9, "cholesky LLT[0][1]")
    _assert_close(llt10, 2.0, 1e-9, "cholesky LLT[1][0]")
    _assert_close(llt11, 3.0, 1e-9, "cholesky LLT[1][1]")
    passed += 4

    # 12. is_positive_definite of PD matrix → True
    var pd_m = List[List[Float64]]()
    var pd0 = List[Float64]()
    pd0.append(4.0)
    pd0.append(2.0)
    var pd1 = List[Float64]()
    pd1.append(2.0)
    pd1.append(3.0)
    pd_m.append(pd0^)
    pd_m.append(pd1^)
    _assert(is_positive_definite(pd_m), "is_positive_definite PD matrix")
    passed += 1

    # 13. is_positive_definite of non-PD → False
    var npd = List[List[Float64]]()
    var np0 = List[Float64]()
    np0.append(-1.0)
    np0.append(0.0)
    var np1 = List[Float64]()
    np1.append(0.0)
    np1.append(-2.0)
    npd.append(np0^)
    npd.append(np1^)
    _assert(not is_positive_definite(npd), "is_positive_definite non-PD")
    passed += 1

    # 14. lu_decompose — L*U ≈ A for [[2,1],[5,3]]
    var lu_a = List[List[Float64]]()
    var lu0 = List[Float64]()
    lu0.append(2.0)
    lu0.append(1.0)
    var lu1 = List[Float64]()
    lu1.append(5.0)
    lu1.append(3.0)
    lu_a.append(lu0^)
    lu_a.append(lu1^)
    var lu = lu_decompose(lu_a)
    var Lm = lu[0].copy()
    var Um = lu[1].copy()
    # L*U: [0][0] = L00*U00 + L01*U10
    var lu_prod00 = Lm[0][0] * Um[0][0] + Lm[0][1] * Um[1][0]
    var lu_prod01 = Lm[0][0] * Um[0][1] + Lm[0][1] * Um[1][1]
    var lu_prod10 = Lm[1][0] * Um[0][0] + Lm[1][1] * Um[1][0]
    var lu_prod11 = Lm[1][0] * Um[0][1] + Lm[1][1] * Um[1][1]
    # With pivoting, L*U = P*A, so |det(L*U)| = |det(A)| = |2*3-1*5| = 1
    var lu_det = lu_prod00 * lu_prod11 - lu_prod01 * lu_prod10
    _assert(fabs(fabs(lu_det) - 1.0) < 1e-6, "LU det preserved")
    passed += 1

    # 15. forward_substitution — L = [[1,0],[2,1]], b = [1,4] → x = [1,2]
    var fL = List[List[Float64]]()
    var fL0 = List[Float64]()
    fL0.append(1.0)
    fL0.append(0.0)
    var fL1 = List[Float64]()
    fL1.append(2.0)
    fL1.append(1.0)
    fL.append(fL0^)
    fL.append(fL1^)
    var fb = List[Float64]()
    fb.append(1.0)
    fb.append(4.0)
    var fx = forward_substitution(fL, fb)
    _assert_close(fx[0], 1.0, 1e-9, "forward_sub x[0]")
    _assert_close(fx[1], 2.0, 1e-9, "forward_sub x[1]")
    passed += 2

    # 17. back_substitution — U = [[2,1],[0,3]], b = [4,6] → x = [1,2]
    var bU = List[List[Float64]]()
    var bU0 = List[Float64]()
    bU0.append(2.0)
    bU0.append(1.0)
    var bU1 = List[Float64]()
    bU1.append(0.0)
    bU1.append(3.0)
    bU.append(bU0^)
    bU.append(bU1^)
    var bb = List[Float64]()
    bb.append(4.0)
    bb.append(6.0)
    var bx = back_substitution(bU, bb)
    _assert_close(bx[0], 1.0, 1e-9, "back_sub x[0]")
    _assert_close(bx[1], 2.0, 1e-9, "back_sub x[1]")
    passed += 2

    # 19. solve_lu on known system: [[1,2],[3,5]] x = [5,14] → x = [3,1]
    var sl_A = List[List[Float64]]()
    var sl0 = List[Float64]()
    sl0.append(1.0)
    sl0.append(2.0)
    var sl1 = List[Float64]()
    sl1.append(3.0)
    sl1.append(5.0)
    sl_A.append(sl0^)
    sl_A.append(sl1^)
    var sl_b = List[Float64]()
    sl_b.append(5.0)
    sl_b.append(14.0)
    var sl_x = solve_lu(sl_A, sl_b)
    _assert_close(sl_x[0], 3.0, 1e-6, "solve_lu x[0]")
    _assert_close(sl_x[1], 1.0, 1e-6, "solve_lu x[1]")
    passed += 2

    # 21. eigen_2x2 — eigenvalues of [[2,1],[1,2]] are 3 and 1
    var eig_m = List[List[Float64]]()
    var e0 = List[Float64]()
    e0.append(2.0)
    e0.append(1.0)
    var e1 = List[Float64]()
    e1.append(1.0)
    e1.append(2.0)
    eig_m.append(e0^)
    eig_m.append(e1^)
    var eig = eigen_2x2(eig_m)
    _assert_close(eig[0][0], 3.0, 1e-9, "eigen_2x2 λ1")
    _assert_close(eig[0][1], 1.0, 1e-9, "eigen_2x2 λ2")
    passed += 2

    # 23. eigen_2x2 eigenvectors are normalized
    var v1_mag = eig[1][0] * eig[1][0] + eig[1][1] * eig[1][1]
    _assert_close(v1_mag, 1.0, 1e-9, "eigen_2x2 v1 normalized")
    passed += 1

    print("    " + String(passed) + " matrix_decomp assertions passed ✓")


# ── Sentiment tests ──────────────────────────────────────────────────────────


fn test_sentiment() raises:
    print("  Testing sentiment...")
    var passed = 0

    # 1. sentiment_score("good") > 0
    _assert(sentiment_score("good") > 0.0, "sentiment_score('good') > 0")
    passed += 1

    # 2. sentiment_score("bad") < 0
    _assert(sentiment_score("bad") < 0.0, "sentiment_score('bad') < 0")
    passed += 1

    # 3. sentiment_score("This is great and wonderful") > 0.5
    _assert(sentiment_score("This is great and wonderful") > 0.5, "sentiment great+wonderful > 0.5")
    passed += 1

    # 4. sentiment_score("Terrible and awful") < -0.5
    _assert(sentiment_score("Terrible and awful") < -0.5, "sentiment terrible+awful < -0.5")
    passed += 1

    # 5. sentiment_label(0.5) == "positive"
    _assert(sentiment_label(0.5) == "positive", "label(0.5) positive")
    passed += 1

    # 6. sentiment_label(-0.5) == "negative"
    _assert(sentiment_label(-0.5) == "negative", "label(-0.5) negative")
    passed += 1

    # 7. sentiment_label(0.0) == "neutral"
    _assert(sentiment_label(0.0) == "neutral", "label(0.0) neutral")
    passed += 1

    # 8. sentiment_label(0.03) == "neutral" (within threshold)
    _assert(sentiment_label(0.03) == "neutral", "label(0.03) neutral")
    passed += 1

    # 9. count_positive_words("good great excellent") == 3
    _assert(count_positive_words("good great excellent") == 3, "count_positive 3")
    passed += 1

    # 10. count_negative_words("bad terrible") == 2
    _assert(count_negative_words("bad terrible") == 2, "count_negative 2")
    passed += 1

    # 11. count_negative_words("good day") == 0
    _assert(count_negative_words("good day") == 0, "count_negative good day")
    passed += 1

    # 12. subjectivity("the cat is good") between 0 and 1
    var subj = subjectivity("the cat is good")
    _assert(subj > 0.0 and subj < 1.0, "subjectivity in (0,1)")
    passed += 1

    # 13. subjectivity("good great") == 1.0 (all known)
    _assert_close(subjectivity("good great"), 1.0, 1e-9, "subjectivity all known")
    passed += 1

    # 14. most_positive_word("bad good excellent") == "excellent"
    _assert(most_positive_word("bad good excellent") == "excellent", "most_positive excellent")
    passed += 1

    # 15. most_negative_word("good terrible fine") == "terrible"
    _assert(most_negative_word("good terrible fine") == "terrible", "most_negative terrible")
    passed += 1

    # 16. word_sentiment("good") ≈ 0.7
    _assert_close(word_sentiment("good"), 0.7, 1e-9, "word_sentiment good")
    passed += 1

    # 17. word_sentiment("unknown") == 0.0
    _assert_close(word_sentiment("unknown"), 0.0, 1e-9, "word_sentiment unknown")
    passed += 1

    # 18. polarity == sentiment_score (alias)
    var p = polarity("I love this amazing product")
    var s = sentiment_score("I love this amazing product")
    _assert_close(p, s, 1e-9, "polarity == sentiment_score")
    passed += 1

    # 19. tokenize_lower handles punctuation
    var tokens = tokenize_lower("Hello, world! Great.")
    _assert(len(tokens) == 3, "tokenize_lower 3 tokens")
    _assert(tokens[0] == "hello", "tokenize_lower first=hello")
    passed += 2

    print("    " + String(passed) + " sentiment assertions passed ✓")


# ── Queue tests ──────────────────────────────────────────────────────────────


fn test_queue_ds() raises:
    print("  Testing queue_ds...")
    var passed = 0

    # 1. pq_create — empty, size 0
    var pq = pq_create()
    _assert(pq_is_empty(pq), "pq_create empty")
    _assert(pq_size(pq) == 0, "pq_create size 0")
    passed += 2

    # 3. pq_push then pq_peek returns min priority
    pq_push(pq, 5.0, 50)
    pq_push(pq, 1.0, 10)
    pq_push(pq, 3.0, 30)
    var pk = pq_peek(pq)
    _assert_close(pk.priority, 1.0, 1e-9, "pq_peek min priority")
    _assert(pk.value == 10, "pq_peek min value")
    passed += 2

    # 5. pq_size after pushes
    _assert(pq_size(pq) == 3, "pq_size 3 after pushes")
    passed += 1

    # 6. pq_is_empty false
    _assert(not pq_is_empty(pq), "pq not empty")
    passed += 1

    # 7. pq_pop returns in priority order
    var p1 = pq_pop(pq)
    _assert_close(p1.priority, 1.0, 1e-9, "pq_pop first priority=1")
    _assert(p1.value == 10, "pq_pop first value=10")
    passed += 2

    var p2 = pq_pop(pq)
    _assert_close(p2.priority, 3.0, 1e-9, "pq_pop second priority=3")
    _assert(p2.value == 30, "pq_pop second value=30")
    passed += 2

    var p3 = pq_pop(pq)
    _assert_close(p3.priority, 5.0, 1e-9, "pq_pop third priority=5")
    _assert(p3.value == 50, "pq_pop third value=50")
    passed += 2

    # 13. pq empty after all pops
    _assert(pq_is_empty(pq), "pq empty after pops")
    _assert(pq_size(pq) == 0, "pq size 0 after pops")
    passed += 2

    # ── Circular buffer tests ──

    # 15. cb_create(3) — empty, size 0
    var buf = cb_create(3)
    _assert(cb_size(buf) == 0, "cb_create size 0")
    _assert(not cb_is_full(buf), "cb not full initially")
    passed += 2

    # 17. cb_push 3 values, size == 3
    cb_push(buf, 10.0)
    cb_push(buf, 20.0)
    cb_push(buf, 30.0)
    _assert(cb_size(buf) == 3, "cb_size 3 after 3 pushes")
    passed += 1

    # 18. cb_is_full after filling to capacity
    _assert(cb_is_full(buf), "cb_is_full after 3 pushes")
    passed += 1

    # 19. cb_peek returns oldest (10.0)
    _assert_close(cb_peek(buf), 10.0, 1e-9, "cb_peek oldest=10")
    passed += 1

    # 20. cb_push 4th value overwrites oldest — size still 3
    cb_push(buf, 40.0)
    _assert(cb_size(buf) == 3, "cb_size still 3 after overwrite")
    passed += 1

    # 21. After overwrite, oldest is now 20.0
    _assert_close(cb_peek(buf), 20.0, 1e-9, "cb_peek after overwrite=20")
    passed += 1

    # 22. cb_pop returns oldest (20.0)
    var v = cb_pop(buf)
    _assert_close(v, 20.0, 1e-9, "cb_pop oldest=20")
    _assert(cb_size(buf) == 2, "cb_size 2 after pop")
    passed += 2

    # 24. cb_pop again returns 30.0
    var v2 = cb_pop(buf)
    _assert_close(v2, 30.0, 1e-9, "cb_pop next=30")
    passed += 1

    # 25. cb_pop returns 40.0
    var v3 = cb_pop(buf)
    _assert_close(v3, 40.0, 1e-9, "cb_pop next=40")
    passed += 1

    # 26. cb_pop on empty returns sentinel
    var v4 = cb_pop(buf)
    _assert_close(v4, -999999.0, 1e-9, "cb_pop empty sentinel")
    passed += 1

    print("    " + String(passed) + " queue_ds assertions passed ✓")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 34 tests — Matrix Decompositions, Sentiment Analysis, Queue DS")
    test_matrix_decomp()
    test_sentiment()
    test_queue_ds()
    print("All Wave 34 tests passed ✓")
