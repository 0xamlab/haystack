"""test_wind_energy.mojo — auto-generated tests for wind_energy library."""
from std.math import isnan, isinf
from wind_energy import wind_power_available, betz_limit, power_coefficient, tip_speed_ratio, swept_area, annual_energy_production, capacity_factor, wind_shear_power_law, weibull_mean_wind_speed, energy_density, rotor_thrust, wake_velocity

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

    var _v_wind_power_available = wind_power_available(0.5, 0.5, 0.5)
    if is_finite(_v_wind_power_available): passed += 1; print("  ✅ wind_energy::wind_power_available =", _v_wind_power_available)
    else: failed += 1; print("  ❌ wind_energy::wind_power_available → non-finite:", _v_wind_power_available)
    var _v_betz_limit = betz_limit()
    if is_finite(_v_betz_limit): passed += 1; print("  ✅ wind_energy::betz_limit =", _v_betz_limit)
    else: failed += 1; print("  ❌ wind_energy::betz_limit → non-finite:", _v_betz_limit)
    var _v_power_coefficient = power_coefficient(0.5, 0.5)
    if is_finite(_v_power_coefficient): passed += 1; print("  ✅ wind_energy::power_coefficient =", _v_power_coefficient)
    else: failed += 1; print("  ❌ wind_energy::power_coefficient → non-finite:", _v_power_coefficient)
    var _v_tip_speed_ratio = tip_speed_ratio(0.5, 0.5, 0.5)
    if is_finite(_v_tip_speed_ratio): passed += 1; print("  ✅ wind_energy::tip_speed_ratio =", _v_tip_speed_ratio)
    else: failed += 1; print("  ❌ wind_energy::tip_speed_ratio → non-finite:", _v_tip_speed_ratio)
    var _v_swept_area = swept_area(0.5)
    if is_finite(_v_swept_area): passed += 1; print("  ✅ wind_energy::swept_area =", _v_swept_area)
    else: failed += 1; print("  ❌ wind_energy::swept_area → non-finite:", _v_swept_area)
    var _v_annual_energy_production = annual_energy_production(0.5, 0.5, 0.5)
    if is_finite(_v_annual_energy_production): passed += 1; print("  ✅ wind_energy::annual_energy_production =", _v_annual_energy_production)
    else: failed += 1; print("  ❌ wind_energy::annual_energy_production → non-finite:", _v_annual_energy_production)
    var _v_capacity_factor = capacity_factor(0.5, 0.5, 0.5)
    if is_finite(_v_capacity_factor): passed += 1; print("  ✅ wind_energy::capacity_factor =", _v_capacity_factor)
    else: failed += 1; print("  ❌ wind_energy::capacity_factor → non-finite:", _v_capacity_factor)
    var _v_wind_shear_power_law = wind_shear_power_law(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_wind_shear_power_law): passed += 1; print("  ✅ wind_energy::wind_shear_power_law =", _v_wind_shear_power_law)
    else: failed += 1; print("  ❌ wind_energy::wind_shear_power_law → non-finite:", _v_wind_shear_power_law)
    var _v_weibull_mean_wind_speed = weibull_mean_wind_speed(0.5, 0.5)
    if is_finite(_v_weibull_mean_wind_speed): passed += 1; print("  ✅ wind_energy::weibull_mean_wind_speed =", _v_weibull_mean_wind_speed)
    else: failed += 1; print("  ❌ wind_energy::weibull_mean_wind_speed → non-finite:", _v_weibull_mean_wind_speed)
    var _v_energy_density = energy_density(0.5, 0.5)
    if is_finite(_v_energy_density): passed += 1; print("  ✅ wind_energy::energy_density =", _v_energy_density)
    else: failed += 1; print("  ❌ wind_energy::energy_density → non-finite:", _v_energy_density)
    var _v_rotor_thrust = rotor_thrust(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_rotor_thrust): passed += 1; print("  ✅ wind_energy::rotor_thrust =", _v_rotor_thrust)
    else: failed += 1; print("  ❌ wind_energy::rotor_thrust → non-finite:", _v_rotor_thrust)
    var _v_wake_velocity = wake_velocity(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_wake_velocity): passed += 1; print("  ✅ wind_energy::wake_velocity =", _v_wake_velocity)
    else: failed += 1; print("  ❌ wind_energy::wake_velocity → non-finite:", _v_wake_velocity)

    print("  [wind_energy] Passed:", passed, "Failed:", failed)
