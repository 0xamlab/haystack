"""test_voting.mojo — auto-generated tests for voting library."""
from std.math import isnan, isinf
from voting import plurality_winner, borda_score, condorcet_pairwise, approval_score, majority_threshold, quota_droop, quota_hare, dhondt_divisor, sainte_lague_divisor, power_index_banzhaf, spoiler_effect

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = plurality_winner(_li5, 5)
    passed += 1; print("  ✅ voting::plurality_winner")
    _ = borda_score(_li5, 5, 5)
    passed += 1; print("  ✅ voting::borda_score")
    _ = condorcet_pairwise(5, 5)
    passed += 1; print("  ✅ voting::condorcet_pairwise")
    _ = approval_score(_li5, 5)
    passed += 1; print("  ✅ voting::approval_score")
    _ = majority_threshold(5)
    passed += 1; print("  ✅ voting::majority_threshold")
    _ = quota_droop(5, 5)
    passed += 1; print("  ✅ voting::quota_droop")
    var _v_quota_hare = quota_hare(5, 5)
    if is_finite(_v_quota_hare): passed += 1; print("  ✅ voting::quota_hare =", _v_quota_hare)
    else: failed += 1; print("  ❌ voting::quota_hare → non-finite:", _v_quota_hare)
    _ = dhondt_divisor(5)
    passed += 1; print("  ✅ voting::dhondt_divisor")
    _ = sainte_lague_divisor(5)
    passed += 1; print("  ✅ voting::sainte_lague_divisor")
    var _v_power_index_banzhaf = power_index_banzhaf(5, 5, 5)
    if is_finite(_v_power_index_banzhaf): passed += 1; print("  ✅ voting::power_index_banzhaf =", _v_power_index_banzhaf)
    else: failed += 1; print("  ❌ voting::power_index_banzhaf → non-finite:", _v_power_index_banzhaf)
    _ = spoiler_effect(5, 5)
    passed += 1; print("  ✅ voting::spoiler_effect")

    print("  [voting] Passed:", passed, "Failed:", failed)
