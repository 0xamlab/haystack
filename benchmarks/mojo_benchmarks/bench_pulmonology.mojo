"""bench_pulmonology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pulmonology import tidal_volume_predicted, minute_ventilation, alveolar_ventilation, fev1_fvc_ratio, peak_expiratory_flow, alveolar_oxygen, a_a_gradient, respiratory_quotient, compliance_static, airway_resistance
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_tidal_volume_predicted: Float64 = 0.0
    var _t0_tidal_volume_predicted = perf_counter_ns()
    for _ in range(N):
        _acc_tidal_volume_predicted += tidal_volume_predicted(0.5)
    var _t1_tidal_volume_predicted = perf_counter_ns()
    var _ns_tidal_volume_predicted = Float64(_t1_tidal_volume_predicted - _t0_tidal_volume_predicted) / Float64(N)
    print("MOJO_TIMING pulmonology::tidal_volume_predicted", _ns_tidal_volume_predicted, _acc_tidal_volume_predicted)
    var _acc_minute_ventilation: Float64 = 0.0
    var _t0_minute_ventilation = perf_counter_ns()
    for _ in range(N):
        _acc_minute_ventilation += minute_ventilation(0.5, 0.5)
    var _t1_minute_ventilation = perf_counter_ns()
    var _ns_minute_ventilation = Float64(_t1_minute_ventilation - _t0_minute_ventilation) / Float64(N)
    print("MOJO_TIMING pulmonology::minute_ventilation", _ns_minute_ventilation, _acc_minute_ventilation)
    var _acc_alveolar_ventilation: Float64 = 0.0
    var _t0_alveolar_ventilation = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_ventilation += alveolar_ventilation(0.5, 0.5, 0.5)
    var _t1_alveolar_ventilation = perf_counter_ns()
    var _ns_alveolar_ventilation = Float64(_t1_alveolar_ventilation - _t0_alveolar_ventilation) / Float64(N)
    print("MOJO_TIMING pulmonology::alveolar_ventilation", _ns_alveolar_ventilation, _acc_alveolar_ventilation)
    var _acc_fev1_fvc_ratio: Float64 = 0.0
    var _t0_fev1_fvc_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_fev1_fvc_ratio += fev1_fvc_ratio(0.5, 0.5)
    var _t1_fev1_fvc_ratio = perf_counter_ns()
    var _ns_fev1_fvc_ratio = Float64(_t1_fev1_fvc_ratio - _t0_fev1_fvc_ratio) / Float64(N)
    print("MOJO_TIMING pulmonology::fev1_fvc_ratio", _ns_fev1_fvc_ratio, _acc_fev1_fvc_ratio)
    var _acc_peak_expiratory_flow: Float64 = 0.0
    var _t0_peak_expiratory_flow = perf_counter_ns()
    for _ in range(N):
        _acc_peak_expiratory_flow += peak_expiratory_flow(0.5, 0.5)
    var _t1_peak_expiratory_flow = perf_counter_ns()
    var _ns_peak_expiratory_flow = Float64(_t1_peak_expiratory_flow - _t0_peak_expiratory_flow) / Float64(N)
    print("MOJO_TIMING pulmonology::peak_expiratory_flow", _ns_peak_expiratory_flow, _acc_peak_expiratory_flow)
    var _acc_alveolar_oxygen: Float64 = 0.0
    var _t0_alveolar_oxygen = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_oxygen += alveolar_oxygen(0.5, 0.5, 0.5)
    var _t1_alveolar_oxygen = perf_counter_ns()
    var _ns_alveolar_oxygen = Float64(_t1_alveolar_oxygen - _t0_alveolar_oxygen) / Float64(N)
    print("MOJO_TIMING pulmonology::alveolar_oxygen", _ns_alveolar_oxygen, _acc_alveolar_oxygen)
    var _acc_a_a_gradient: Float64 = 0.0
    var _t0_a_a_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_a_a_gradient += a_a_gradient(0.5, 0.5)
    var _t1_a_a_gradient = perf_counter_ns()
    var _ns_a_a_gradient = Float64(_t1_a_a_gradient - _t0_a_a_gradient) / Float64(N)
    print("MOJO_TIMING pulmonology::a_a_gradient", _ns_a_a_gradient, _acc_a_a_gradient)
    var _acc_respiratory_quotient: Float64 = 0.0
    var _t0_respiratory_quotient = perf_counter_ns()
    for _ in range(N):
        _acc_respiratory_quotient += respiratory_quotient(0.5, 0.5)
    var _t1_respiratory_quotient = perf_counter_ns()
    var _ns_respiratory_quotient = Float64(_t1_respiratory_quotient - _t0_respiratory_quotient) / Float64(N)
    print("MOJO_TIMING pulmonology::respiratory_quotient", _ns_respiratory_quotient, _acc_respiratory_quotient)
    var _acc_compliance_static: Float64 = 0.0
    var _t0_compliance_static = perf_counter_ns()
    for _ in range(N):
        _acc_compliance_static += compliance_static(0.5, 0.5)
    var _t1_compliance_static = perf_counter_ns()
    var _ns_compliance_static = Float64(_t1_compliance_static - _t0_compliance_static) / Float64(N)
    print("MOJO_TIMING pulmonology::compliance_static", _ns_compliance_static, _acc_compliance_static)
    var _acc_airway_resistance: Float64 = 0.0
    var _t0_airway_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_airway_resistance += airway_resistance(0.5, 0.5)
    var _t1_airway_resistance = perf_counter_ns()
    var _ns_airway_resistance = Float64(_t1_airway_resistance - _t0_airway_resistance) / Float64(N)
    print("MOJO_TIMING pulmonology::airway_resistance", _ns_airway_resistance, _acc_airway_resistance)
