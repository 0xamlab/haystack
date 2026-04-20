"""test_insurance.mojo — auto-generated tests for insurance library."""
from std.math import isnan, isinf
from insurance import pure_premium, gross_premium, loss_ratio, expense_ratio, combined_ratio, expected_claim_frequency, expected_claim_severity, burning_cost, credibility_buhlmann, risk_load, aggregate_deductible_savings, retention_rate

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

    var _v_pure_premium = pure_premium(0.5, 0.5)
    if is_finite(_v_pure_premium): passed += 1; print("  ✅ insurance::pure_premium =", _v_pure_premium)
    else: failed += 1; print("  ❌ insurance::pure_premium → non-finite:", _v_pure_premium)
    var _v_gross_premium = gross_premium(100.0, 0.2, 0.1)
    if is_finite(_v_gross_premium): passed += 1; print("  ✅ insurance::gross_premium =", _v_gross_premium)
    else: failed += 1; print("  ❌ insurance::gross_premium → non-finite:", _v_gross_premium)
    var _v_loss_ratio = loss_ratio(0.5, 0.5)
    if is_finite(_v_loss_ratio): passed += 1; print("  ✅ insurance::loss_ratio =", _v_loss_ratio)
    else: failed += 1; print("  ❌ insurance::loss_ratio → non-finite:", _v_loss_ratio)
    var _v_expense_ratio = expense_ratio(0.5, 0.5)
    if is_finite(_v_expense_ratio): passed += 1; print("  ✅ insurance::expense_ratio =", _v_expense_ratio)
    else: failed += 1; print("  ❌ insurance::expense_ratio → non-finite:", _v_expense_ratio)
    var _v_combined_ratio = combined_ratio(0.5, 0.5)
    if is_finite(_v_combined_ratio): passed += 1; print("  ✅ insurance::combined_ratio =", _v_combined_ratio)
    else: failed += 1; print("  ❌ insurance::combined_ratio → non-finite:", _v_combined_ratio)
    var _v_expected_claim_frequency = expected_claim_frequency(0.5, 0.5)
    if is_finite(_v_expected_claim_frequency): passed += 1; print("  ✅ insurance::expected_claim_frequency =", _v_expected_claim_frequency)
    else: failed += 1; print("  ❌ insurance::expected_claim_frequency → non-finite:", _v_expected_claim_frequency)
    var _v_expected_claim_severity = expected_claim_severity(0.5, 0.5)
    if is_finite(_v_expected_claim_severity): passed += 1; print("  ✅ insurance::expected_claim_severity =", _v_expected_claim_severity)
    else: failed += 1; print("  ❌ insurance::expected_claim_severity → non-finite:", _v_expected_claim_severity)
    var _v_burning_cost = burning_cost(0.5, 0.5)
    if is_finite(_v_burning_cost): passed += 1; print("  ✅ insurance::burning_cost =", _v_burning_cost)
    else: failed += 1; print("  ❌ insurance::burning_cost → non-finite:", _v_burning_cost)
    var _v_credibility_buhlmann = credibility_buhlmann(0.5, 0.5)
    if is_finite(_v_credibility_buhlmann): passed += 1; print("  ✅ insurance::credibility_buhlmann =", _v_credibility_buhlmann)
    else: failed += 1; print("  ❌ insurance::credibility_buhlmann → non-finite:", _v_credibility_buhlmann)
    var _v_risk_load = risk_load(0.5, 0.5)
    if is_finite(_v_risk_load): passed += 1; print("  ✅ insurance::risk_load =", _v_risk_load)
    else: failed += 1; print("  ❌ insurance::risk_load → non-finite:", _v_risk_load)
    var _v_aggregate_deductible_savings = aggregate_deductible_savings(0.5, 0.5, 0.5)
    if is_finite(_v_aggregate_deductible_savings): passed += 1; print("  ✅ insurance::aggregate_deductible_savings =", _v_aggregate_deductible_savings)
    else: failed += 1; print("  ❌ insurance::aggregate_deductible_savings → non-finite:", _v_aggregate_deductible_savings)
    var _v_retention_rate = retention_rate(0.5, 0.5)
    if is_finite(_v_retention_rate): passed += 1; print("  ✅ insurance::retention_rate =", _v_retention_rate)
    else: failed += 1; print("  ❌ insurance::retention_rate → non-finite:", _v_retention_rate)

    print("  [insurance] Passed:", passed, "Failed:", failed)
