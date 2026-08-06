"""test_model_selection.mojo — known-value tests for model_selection."""
from model_selection import (
    SplitIndices,
    walk_forward_splits,
    purged_walk_forward_splits,
    kfold_splits,
    stratified_kfold_splits,
    train_test_split_temporal,
)


def _range_list(lo: Int, hi: Int) -> List[Int]:
    var out = List[Int]()
    for i in range(lo, hi):
        out.append(i)
    return out^


def _lists_equal(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ model_selection::" + name)
    else:
        failed += 1
        print("  ❌ model_selection::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── walk_forward_splits: expanding, known values ─────────────────────────
    # n=10, n_splits=3, min_train=4 -> test region [4,10), 2 per window:
    #   split0: train {0,1,2,3}       test {4,5}
    #   split1: train {0,...,5}       test {6,7}
    #   split2: train {0,...,7}       test {8,9}
    var wf = walk_forward_splits(10, 3, 4, True)
    check(len(wf) == 3, "walk_forward_splits expanding n_splits", passed, failed)
    check(
        _lists_equal(wf[0].train, _range_list(0, 4))
        and _lists_equal(wf[0].test, _range_list(4, 6)),
        "walk_forward_splits expanding split0 exact",
        passed,
        failed,
    )
    check(
        _lists_equal(wf[1].train, _range_list(0, 6))
        and _lists_equal(wf[1].test, _range_list(6, 8)),
        "walk_forward_splits expanding split1 exact",
        passed,
        failed,
    )
    check(
        _lists_equal(wf[2].train, _range_list(0, 8))
        and _lists_equal(wf[2].test, _range_list(8, 10)),
        "walk_forward_splits expanding split2 exact",
        passed,
        failed,
    )

    # ── walk_forward_splits: rolling window ─────────────────────────────────
    # Same geometry, but train is a fixed 4-sample window ending at test start:
    #   split0: train {0..3}  split1: train {2..5}  split2: train {4..7}
    var wr = walk_forward_splits(10, 3, 4, False)
    check(
        len(wr) == 3
        and _lists_equal(wr[0].train, _range_list(0, 4))
        and _lists_equal(wr[1].train, _range_list(2, 6))
        and _lists_equal(wr[2].train, _range_list(4, 8))
        and _lists_equal(wr[2].test, _range_list(8, 10)),
        "walk_forward_splits rolling exact",
        passed,
        failed,
    )

    # ── walk_forward_splits: remainder to earliest windows, covers tail ─────
    # n=11, n_splits=3, min_train=4 -> region 7 = 3+2+2:
    #   tests [4,7), [7,9), [9,11)
    var wrem = walk_forward_splits(11, 3, 4, True)
    check(
        len(wrem) == 3
        and _lists_equal(wrem[0].test, _range_list(4, 7))
        and _lists_equal(wrem[1].test, _range_list(7, 9))
        and _lists_equal(wrem[2].test, _range_list(9, 11)),
        "walk_forward_splits remainder + tail coverage",
        passed,
        failed,
    )

    # ── walk_forward_splits: infeasible / empty edge cases ──────────────────
    check(
        len(walk_forward_splits(5, 3, 4, True)) == 0
        and len(walk_forward_splits(0, 3, 4, True)) == 0
        and len(walk_forward_splits(10, 0, 4, True)) == 0
        and len(walk_forward_splits(1, 1, 1, True)) == 0,
        "walk_forward_splits infeasible -> empty",
        passed,
        failed,
    )
    # n=2, min_train=1, 1 split: train {0} test {1}
    var wmin = walk_forward_splits(2, 1, 1, True)
    check(
        len(wmin) == 1
        and _lists_equal(wmin[0].train, _range_list(0, 1))
        and _lists_equal(wmin[0].test, _range_list(1, 2)),
        "walk_forward_splits minimal n=2",
        passed,
        failed,
    )

    # ── purged_walk_forward_splits: purge_gap=2, embargo=0 ──────────────────
    # n=12, n_splits=3, min_train=4, gap=2 -> test region [6,12), 2 each:
    #   split0: train {0,1,2,3} test {6,7}   (indices 4,5 purged: exact 2-gap)
    #   split1: train {0..5}    test {8,9}
    #   split2: train {0..7}    test {10,11}
    var pg = purged_walk_forward_splits(12, 3, 4, 2, 0)
    check(len(pg) == 3, "purged_walk_forward_splits n_splits", passed, failed)
    check(
        _lists_equal(pg[0].train, _range_list(0, 4))
        and _lists_equal(pg[0].test, _range_list(6, 8)),
        "purged split0 exact (2-sample purge gap)",
        passed,
        failed,
    )
    # Explicit gap assertion: last train index 3, first test index 6 -> gap {4,5}
    check(
        pg[0].train[len(pg[0].train) - 1] == 3 and pg[0].test[0] == 6,
        "purged split0 gap boundary 3|_,_|6",
        passed,
        failed,
    )
    check(
        _lists_equal(pg[1].train, _range_list(0, 6))
        and _lists_equal(pg[1].test, _range_list(8, 10))
        and _lists_equal(pg[2].train, _range_list(0, 8))
        and _lists_equal(pg[2].test, _range_list(10, 12)),
        "purged splits 1,2 exact",
        passed,
        failed,
    )

    # ── purged_walk_forward_splits: embargo excludes post-test samples ──────
    # n=15, n_splits=3, min_train=5, purge_gap=1, embargo=2
    #   tests [6,9), [9,12), [12,15)
    #   split0: train [0,5) = {0..4}
    #   split1: train [0,8) = {0..7} (embargo {9,10} outside range)
    #   split2: train [0,11) minus embargo {9,10} after test0 -> {0..8}
    var pe = purged_walk_forward_splits(15, 3, 5, 1, 2)
    check(
        len(pe) == 3
        and _lists_equal(pe[0].train, _range_list(0, 5))
        and _lists_equal(pe[0].test, _range_list(6, 9))
        and _lists_equal(pe[1].train, _range_list(0, 8))
        and _lists_equal(pe[1].test, _range_list(9, 12)),
        "purged+embargo splits 0,1 exact",
        passed,
        failed,
    )
    check(
        _lists_equal(pe[2].train, _range_list(0, 9))
        and _lists_equal(pe[2].test, _range_list(12, 15)),
        "purged+embargo split2 drops embargoed {9,10}",
        passed,
        failed,
    )

    # zero gap, zero embargo degenerates to expanding walk-forward
    var p0 = purged_walk_forward_splits(10, 3, 4, 0, 0)
    check(
        len(p0) == 3
        and _lists_equal(p0[0].train, _range_list(0, 4))
        and _lists_equal(p0[0].test, _range_list(4, 6))
        and _lists_equal(p0[2].train, _range_list(0, 8)),
        "purged gap=0 embargo=0 == expanding walk-forward",
        passed,
        failed,
    )
    check(
        len(purged_walk_forward_splits(8, 3, 4, 2, 0)) == 0
        and len(purged_walk_forward_splits(0, 3, 4, 2, 1)) == 0,
        "purged infeasible -> empty",
        passed,
        failed,
    )

    # ── kfold_splits: no shuffle, known values ───────────────────────────────
    # n=6, k=3: tests {0,1},{2,3},{4,5}
    var kf = kfold_splits(6, 3, 0, False)
    check(len(kf) == 3, "kfold_splits k folds", passed, failed)
    check(
        _lists_equal(kf[0].test, _range_list(0, 2))
        and _lists_equal(kf[0].train, _range_list(2, 6)),
        "kfold fold0 exact",
        passed,
        failed,
    )
    var kf2_train = List[Int]()
    kf2_train.append(0); kf2_train.append(1); kf2_train.append(4); kf2_train.append(5)
    check(
        _lists_equal(kf[1].test, _range_list(2, 4))
        and _lists_equal(kf[1].train, kf2_train)
        and _lists_equal(kf[2].test, _range_list(4, 6))
        and _lists_equal(kf[2].train, _range_list(0, 4)),
        "kfold folds 1,2 exact",
        passed,
        failed,
    )

    # n=7, k=3 remainder: fold sizes 3,2,2 -> tests {0,1,2},{3,4},{5,6}
    var kr = kfold_splits(7, 3, 0, False)
    check(
        len(kr) == 3
        and _lists_equal(kr[0].test, _range_list(0, 3))
        and _lists_equal(kr[1].test, _range_list(3, 5))
        and _lists_equal(kr[2].test, _range_list(5, 7)),
        "kfold remainder fold sizes 3,2,2",
        passed,
        failed,
    )

    # ── kfold_splits: shuffle determinism + exact partition ─────────────────
    var ks_a = kfold_splits(10, 3, 42, True)
    var ks_b = kfold_splits(10, 3, 42, True)
    var same = len(ks_a) == 3 and len(ks_b) == 3
    if same:
        for f in range(3):
            if not _lists_equal(ks_a[f].test, ks_b[f].test):
                same = False
            if not _lists_equal(ks_a[f].train, ks_b[f].train):
                same = False
    check(same, "kfold shuffle deterministic for seed=42", passed, failed)

    var seen = List[Int]()
    for _ in range(10):
        seen.append(0)
    var ok_part = len(ks_a) == 3
    if ok_part:
        for f in range(3):
            for i in range(len(ks_a[f].test)):
                seen[ks_a[f].test[i]] += 1
            # train ∩ test must be empty and train ∪ test = all 10 indices
            if len(ks_a[f].train) + len(ks_a[f].test) != 10:
                ok_part = False
        for i in range(10):
            if seen[i] != 1:
                ok_part = False
    check(ok_part, "kfold shuffle exact partition (each idx tested once)", passed, failed)

    check(
        len(kfold_splits(1, 2, 0, False)) == 0
        and len(kfold_splits(5, 1, 0, False)) == 0
        and len(kfold_splits(0, 3, 0, False)) == 0,
        "kfold infeasible -> empty",
        passed,
        failed,
    )

    # ── stratified_kfold_splits: labels [0,0,0,1,1,1], k=3 ──────────────────
    # Each fold's test must hold exactly one 0-label and one 1-label.
    var labels = List[Int]()
    labels.append(0); labels.append(0); labels.append(0)
    labels.append(1); labels.append(1); labels.append(1)
    var sk = stratified_kfold_splits(labels, 3, 7)
    var ok_strat = len(sk) == 3
    if ok_strat:
        for f in range(3):
            if len(sk[f].test) != 2 or len(sk[f].train) != 4:
                ok_strat = False
                continue
            var zeros = 0
            var ones = 0
            for i in range(len(sk[f].test)):
                if labels[sk[f].test[i]] == 0:
                    zeros += 1
                else:
                    ones += 1
            if zeros != 1 or ones != 1:
                ok_strat = False
    check(ok_strat, "stratified k=3 one 0-label + one 1-label per fold", passed, failed)

    # Stratified partition: every index tested exactly once; deterministic.
    var seen_s = List[Int]()
    for _ in range(6):
        seen_s.append(0)
    for f in range(len(sk)):
        for i in range(len(sk[f].test)):
            seen_s[sk[f].test[i]] += 1
    var ok_spart = True
    for i in range(6):
        if seen_s[i] != 1:
            ok_spart = False
    var sk_b = stratified_kfold_splits(labels, 3, 7)
    for f in range(3):
        if not _lists_equal(sk[f].test, sk_b[f].test):
            ok_spart = False
    check(ok_spart, "stratified exact partition + deterministic seed", passed, failed)

    # Imbalanced: labels [0,0,0,0,1,1], k=2 -> each fold test: two 0s, one 1.
    var lab2 = List[Int]()
    lab2.append(0); lab2.append(0); lab2.append(0)
    lab2.append(0); lab2.append(1); lab2.append(1)
    var sk2 = stratified_kfold_splits(lab2, 2, 3)
    var ok_imb = len(sk2) == 2
    if ok_imb:
        for f in range(2):
            var z = 0
            var o = 0
            for i in range(len(sk2[f].test)):
                if lab2[sk2[f].test[i]] == 0:
                    z += 1
                else:
                    o += 1
            if z != 2 or o != 1:
                ok_imb = False
    check(ok_imb, "stratified imbalanced 4:2 proportions per fold", passed, failed)

    var empty_labels = List[Int]()
    check(
        len(stratified_kfold_splits(empty_labels, 3, 0)) == 0
        and len(stratified_kfold_splits(labels, 1, 0)) == 0
        and len(stratified_kfold_splits(labels, 7, 0)) == 0,
        "stratified infeasible -> empty",
        passed,
        failed,
    )

    # ── train_test_split_temporal ────────────────────────────────────────────
    # n=10, 0.3 -> n_test=3: train {0..6}, test {7,8,9}
    var tt = train_test_split_temporal(10, 0.3)
    check(
        _lists_equal(tt.train, _range_list(0, 7))
        and _lists_equal(tt.test, _range_list(7, 10)),
        "train_test_split_temporal 10 @ 0.3 exact",
        passed,
        failed,
    )
    var tt2 = train_test_split_temporal(10, 0.0)
    check(
        len(tt2.test) == 0 and _lists_equal(tt2.train, _range_list(0, 10)),
        "train_test_split_temporal fraction 0 -> all train",
        passed,
        failed,
    )
    var tt3 = train_test_split_temporal(10, 1.0)
    check(
        len(tt3.train) == 0 and _lists_equal(tt3.test, _range_list(0, 10)),
        "train_test_split_temporal fraction 1 -> all test",
        passed,
        failed,
    )
    # n=1: 0.2 rounds to 0 test; 0.5 rounds half-up to 1 test.
    var tt4 = train_test_split_temporal(1, 0.2)
    var tt5 = train_test_split_temporal(1, 0.5)
    check(
        len(tt4.train) == 1 and len(tt4.test) == 0
        and len(tt5.train) == 0 and len(tt5.test) == 1,
        "train_test_split_temporal n=1 rounding",
        passed,
        failed,
    )
    var tt6 = train_test_split_temporal(0, 0.5)
    check(
        len(tt6.train) == 0 and len(tt6.test) == 0,
        "train_test_split_temporal n=0 -> empty",
        passed,
        failed,
    )

    print("  [model_selection] Passed:", passed, "Failed:", failed)
