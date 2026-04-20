"""test_pneumatics.mojo — auto-generated tests for pneumatics library."""
from std.math import isnan, isinf
from pneumatics import ideal_gas_volume, flow_rate_orifice, compressor_power, pressure_drop_pipe, air_consumption, cylinder_force, bore_area, piston_speed, receiver_volume, free_air_delivery, specific_power, dew_point_pressure

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

    var _v_ideal_gas_volume = ideal_gas_volume(0.5, 0.5, 0.5)
    if is_finite(_v_ideal_gas_volume): passed += 1; print("  ✅ pneumatics::ideal_gas_volume =", _v_ideal_gas_volume)
    else: failed += 1; print("  ❌ pneumatics::ideal_gas_volume → non-finite:", _v_ideal_gas_volume)
    var _v_flow_rate_orifice = flow_rate_orifice(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_flow_rate_orifice): passed += 1; print("  ✅ pneumatics::flow_rate_orifice =", _v_flow_rate_orifice)
    else: failed += 1; print("  ❌ pneumatics::flow_rate_orifice → non-finite:", _v_flow_rate_orifice)
    var _v_compressor_power = compressor_power(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_compressor_power): passed += 1; print("  ✅ pneumatics::compressor_power =", _v_compressor_power)
    else: failed += 1; print("  ❌ pneumatics::compressor_power → non-finite:", _v_compressor_power)
    var _v_pressure_drop_pipe = pressure_drop_pipe(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_pressure_drop_pipe): passed += 1; print("  ✅ pneumatics::pressure_drop_pipe =", _v_pressure_drop_pipe)
    else: failed += 1; print("  ❌ pneumatics::pressure_drop_pipe → non-finite:", _v_pressure_drop_pipe)
    var _v_air_consumption = air_consumption(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_air_consumption): passed += 1; print("  ✅ pneumatics::air_consumption =", _v_air_consumption)
    else: failed += 1; print("  ❌ pneumatics::air_consumption → non-finite:", _v_air_consumption)
    var _v_cylinder_force = cylinder_force(0.5, 0.5)
    if is_finite(_v_cylinder_force): passed += 1; print("  ✅ pneumatics::cylinder_force =", _v_cylinder_force)
    else: failed += 1; print("  ❌ pneumatics::cylinder_force → non-finite:", _v_cylinder_force)
    var _v_bore_area = bore_area(0.5)
    if is_finite(_v_bore_area): passed += 1; print("  ✅ pneumatics::bore_area =", _v_bore_area)
    else: failed += 1; print("  ❌ pneumatics::bore_area → non-finite:", _v_bore_area)
    var _v_piston_speed = piston_speed(0.5, 0.5)
    if is_finite(_v_piston_speed): passed += 1; print("  ✅ pneumatics::piston_speed =", _v_piston_speed)
    else: failed += 1; print("  ❌ pneumatics::piston_speed → non-finite:", _v_piston_speed)
    var _v_receiver_volume = receiver_volume(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_receiver_volume): passed += 1; print("  ✅ pneumatics::receiver_volume =", _v_receiver_volume)
    else: failed += 1; print("  ❌ pneumatics::receiver_volume → non-finite:", _v_receiver_volume)
    var _v_free_air_delivery = free_air_delivery(0.5, 0.5, 0.5)
    if is_finite(_v_free_air_delivery): passed += 1; print("  ✅ pneumatics::free_air_delivery =", _v_free_air_delivery)
    else: failed += 1; print("  ❌ pneumatics::free_air_delivery → non-finite:", _v_free_air_delivery)
    var _v_specific_power = specific_power(0.5, 0.5)
    if is_finite(_v_specific_power): passed += 1; print("  ✅ pneumatics::specific_power =", _v_specific_power)
    else: failed += 1; print("  ❌ pneumatics::specific_power → non-finite:", _v_specific_power)
    var _v_dew_point_pressure = dew_point_pressure(0.5, 0.5)
    if is_finite(_v_dew_point_pressure): passed += 1; print("  ✅ pneumatics::dew_point_pressure =", _v_dew_point_pressure)
    else: failed += 1; print("  ❌ pneumatics::dew_point_pressure → non-finite:", _v_dew_point_pressure)

    print("  [pneumatics] Passed:", passed, "Failed:", failed)
