"""test_volcanology.mojo — auto-generated tests for volcanology library."""
from std.math import isnan, isinf
from volcanology import vei_energy_estimate, lava_flow_velocity, eruption_column_height, tephra_fallout_thickness, magma_viscosity_estimate, effusion_rate, lahar_velocity, volcanic_gas_emission_rate, recurrence_interval, alert_level, pyroclastic_flow_runout, caldera_collapse_volume

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

    var _v_vei_energy_estimate = vei_energy_estimate(0.5)
    if is_finite(_v_vei_energy_estimate): passed += 1; print("  ✅ volcanology::vei_energy_estimate =", _v_vei_energy_estimate)
    else: failed += 1; print("  ❌ volcanology::vei_energy_estimate → non-finite:", _v_vei_energy_estimate)
    var _v_lava_flow_velocity = lava_flow_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_lava_flow_velocity): passed += 1; print("  ✅ volcanology::lava_flow_velocity =", _v_lava_flow_velocity)
    else: failed += 1; print("  ❌ volcanology::lava_flow_velocity → non-finite:", _v_lava_flow_velocity)
    var _v_eruption_column_height = eruption_column_height(0.5, 0.5)
    if is_finite(_v_eruption_column_height): passed += 1; print("  ✅ volcanology::eruption_column_height =", _v_eruption_column_height)
    else: failed += 1; print("  ❌ volcanology::eruption_column_height → non-finite:", _v_eruption_column_height)
    var _v_tephra_fallout_thickness = tephra_fallout_thickness(0.5, 0.5)
    if is_finite(_v_tephra_fallout_thickness): passed += 1; print("  ✅ volcanology::tephra_fallout_thickness =", _v_tephra_fallout_thickness)
    else: failed += 1; print("  ❌ volcanology::tephra_fallout_thickness → non-finite:", _v_tephra_fallout_thickness)
    var _v_magma_viscosity_estimate = magma_viscosity_estimate(0.5)
    if is_finite(_v_magma_viscosity_estimate): passed += 1; print("  ✅ volcanology::magma_viscosity_estimate =", _v_magma_viscosity_estimate)
    else: failed += 1; print("  ❌ volcanology::magma_viscosity_estimate → non-finite:", _v_magma_viscosity_estimate)
    var _v_effusion_rate = effusion_rate(0.5, 0.5)
    if is_finite(_v_effusion_rate): passed += 1; print("  ✅ volcanology::effusion_rate =", _v_effusion_rate)
    else: failed += 1; print("  ❌ volcanology::effusion_rate → non-finite:", _v_effusion_rate)
    var _v_lahar_velocity = lahar_velocity(0.5, 0.5)
    if is_finite(_v_lahar_velocity): passed += 1; print("  ✅ volcanology::lahar_velocity =", _v_lahar_velocity)
    else: failed += 1; print("  ❌ volcanology::lahar_velocity → non-finite:", _v_lahar_velocity)
    var _v_volcanic_gas_emission_rate = volcanic_gas_emission_rate(0.5, 0.5)
    if is_finite(_v_volcanic_gas_emission_rate): passed += 1; print("  ✅ volcanology::volcanic_gas_emission_rate =", _v_volcanic_gas_emission_rate)
    else: failed += 1; print("  ❌ volcanology::volcanic_gas_emission_rate → non-finite:", _v_volcanic_gas_emission_rate)
    var _v_recurrence_interval = recurrence_interval(0.5, 0.5)
    if is_finite(_v_recurrence_interval): passed += 1; print("  ✅ volcanology::recurrence_interval =", _v_recurrence_interval)
    else: failed += 1; print("  ❌ volcanology::recurrence_interval → non-finite:", _v_recurrence_interval)
    var _v_alert_level = alert_level(0.5, 0.5, 0.5)
    if is_finite(_v_alert_level): passed += 1; print("  ✅ volcanology::alert_level =", _v_alert_level)
    else: failed += 1; print("  ❌ volcanology::alert_level → non-finite:", _v_alert_level)
    var _v_pyroclastic_flow_runout = pyroclastic_flow_runout(0.5, 0.5)
    if is_finite(_v_pyroclastic_flow_runout): passed += 1; print("  ✅ volcanology::pyroclastic_flow_runout =", _v_pyroclastic_flow_runout)
    else: failed += 1; print("  ❌ volcanology::pyroclastic_flow_runout → non-finite:", _v_pyroclastic_flow_runout)
    var _v_caldera_collapse_volume = caldera_collapse_volume(0.5, 0.5)
    if is_finite(_v_caldera_collapse_volume): passed += 1; print("  ✅ volcanology::caldera_collapse_volume =", _v_caldera_collapse_volume)
    else: failed += 1; print("  ❌ volcanology::caldera_collapse_volume → non-finite:", _v_caldera_collapse_volume)

    print("  [volcanology] Passed:", passed, "Failed:", failed)
