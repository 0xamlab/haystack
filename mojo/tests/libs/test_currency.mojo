"""test_currency.mojo — auto-generated tests for currency library."""
from std.math import isnan, isinf
from currency import round_currency, compound_interest, continuous_compound, amortization_payment, amortization_schedule, present_value, present_value_annuity, future_value_annuity, effective_annual_rate, discount_factor, rule_of_72, loan_balance_after

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

    var _v_round_currency = round_currency(0.5, 5)
    if is_finite(_v_round_currency): passed += 1; print("  ✅ currency::round_currency =", _v_round_currency)
    else: failed += 1; print("  ❌ currency::round_currency → non-finite:", _v_round_currency)
    var _v_compound_interest = compound_interest(0.5, 0.5, 5)
    if is_finite(_v_compound_interest): passed += 1; print("  ✅ currency::compound_interest =", _v_compound_interest)
    else: failed += 1; print("  ❌ currency::compound_interest → non-finite:", _v_compound_interest)
    var _v_continuous_compound = continuous_compound(0.5, 0.5, 0.5)
    if is_finite(_v_continuous_compound): passed += 1; print("  ✅ currency::continuous_compound =", _v_continuous_compound)
    else: failed += 1; print("  ❌ currency::continuous_compound → non-finite:", _v_continuous_compound)
    var _v_amortization_payment = amortization_payment(0.5, 0.5, 5)
    if is_finite(_v_amortization_payment): passed += 1; print("  ✅ currency::amortization_payment =", _v_amortization_payment)
    else: failed += 1; print("  ❌ currency::amortization_payment → non-finite:", _v_amortization_payment)
    _ = amortization_schedule(0.5, 0.5, 5)
    passed += 1; print("  ✅ currency::amortization_schedule")
    var _v_present_value = present_value(0.5, 0.5, 5)
    if is_finite(_v_present_value): passed += 1; print("  ✅ currency::present_value =", _v_present_value)
    else: failed += 1; print("  ❌ currency::present_value → non-finite:", _v_present_value)
    var _v_present_value_annuity = present_value_annuity(0.5, 0.5, 5)
    if is_finite(_v_present_value_annuity): passed += 1; print("  ✅ currency::present_value_annuity =", _v_present_value_annuity)
    else: failed += 1; print("  ❌ currency::present_value_annuity → non-finite:", _v_present_value_annuity)
    var _v_future_value_annuity = future_value_annuity(0.5, 0.5, 5)
    if is_finite(_v_future_value_annuity): passed += 1; print("  ✅ currency::future_value_annuity =", _v_future_value_annuity)
    else: failed += 1; print("  ❌ currency::future_value_annuity → non-finite:", _v_future_value_annuity)
    var _v_effective_annual_rate = effective_annual_rate(0.5, 5)
    if is_finite(_v_effective_annual_rate): passed += 1; print("  ✅ currency::effective_annual_rate =", _v_effective_annual_rate)
    else: failed += 1; print("  ❌ currency::effective_annual_rate → non-finite:", _v_effective_annual_rate)
    var _v_discount_factor = discount_factor(0.5, 5)
    if is_finite(_v_discount_factor): passed += 1; print("  ✅ currency::discount_factor =", _v_discount_factor)
    else: failed += 1; print("  ❌ currency::discount_factor → non-finite:", _v_discount_factor)
    var _v_rule_of_72 = rule_of_72(0.5)
    if is_finite(_v_rule_of_72): passed += 1; print("  ✅ currency::rule_of_72 =", _v_rule_of_72)
    else: failed += 1; print("  ❌ currency::rule_of_72 → non-finite:", _v_rule_of_72)
    var _v_loan_balance_after = loan_balance_after(0.5, 0.5, 5, 5)
    if is_finite(_v_loan_balance_after): passed += 1; print("  ✅ currency::loan_balance_after =", _v_loan_balance_after)
    else: failed += 1; print("  ❌ currency::loan_balance_after → non-finite:", _v_loan_balance_after)

    print("  [currency] Passed:", passed, "Failed:", failed)
