"""bench_biomedical.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biomedical import cardiac_output, mean_arterial_pressure, body_surface_area_dubois, glomerular_filtration_rate, oxygen_delivery, alveolar_gas_equation, bmi, drug_clearance, anion_gap, corrected_qt_bazett, fick_cardiac_output, pulse_pressure
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

    var _acc_cardiac_output: Float64 = 0.0
    var _t0_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_cardiac_output += cardiac_output(0.5, 0.5)
    var _t1_cardiac_output = perf_counter_ns()
    var _ns_cardiac_output = Float64(_t1_cardiac_output - _t0_cardiac_output) / Float64(N)
    print("MOJO_TIMING biomedical::cardiac_output", _ns_cardiac_output, _acc_cardiac_output)
    var _acc_mean_arterial_pressure: Float64 = 0.0
    var _t0_mean_arterial_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_mean_arterial_pressure += mean_arterial_pressure(0.5, 0.5)
    var _t1_mean_arterial_pressure = perf_counter_ns()
    var _ns_mean_arterial_pressure = Float64(_t1_mean_arterial_pressure - _t0_mean_arterial_pressure) / Float64(N)
    print("MOJO_TIMING biomedical::mean_arterial_pressure", _ns_mean_arterial_pressure, _acc_mean_arterial_pressure)
    var _acc_body_surface_area_dubois: Float64 = 0.0
    var _t0_body_surface_area_dubois = perf_counter_ns()
    for _ in range(N):
        _acc_body_surface_area_dubois += body_surface_area_dubois(0.5, 0.5)
    var _t1_body_surface_area_dubois = perf_counter_ns()
    var _ns_body_surface_area_dubois = Float64(_t1_body_surface_area_dubois - _t0_body_surface_area_dubois) / Float64(N)
    print("MOJO_TIMING biomedical::body_surface_area_dubois", _ns_body_surface_area_dubois, _acc_body_surface_area_dubois)
    var _acc_glomerular_filtration_rate: Float64 = 0.0
    var _t0_glomerular_filtration_rate = perf_counter_ns()
    for _ in range(N):
        _acc_glomerular_filtration_rate += glomerular_filtration_rate(0.5, 0.5, 0.5, True)
    var _t1_glomerular_filtration_rate = perf_counter_ns()
    var _ns_glomerular_filtration_rate = Float64(_t1_glomerular_filtration_rate - _t0_glomerular_filtration_rate) / Float64(N)
    print("MOJO_TIMING biomedical::glomerular_filtration_rate", _ns_glomerular_filtration_rate, _acc_glomerular_filtration_rate)
    var _acc_oxygen_delivery: Float64 = 0.0
    var _t0_oxygen_delivery = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_delivery += oxygen_delivery(0.5, 0.5, 0.5)
    var _t1_oxygen_delivery = perf_counter_ns()
    var _ns_oxygen_delivery = Float64(_t1_oxygen_delivery - _t0_oxygen_delivery) / Float64(N)
    print("MOJO_TIMING biomedical::oxygen_delivery", _ns_oxygen_delivery, _acc_oxygen_delivery)
    var _acc_alveolar_gas_equation: Float64 = 0.0
    var _t0_alveolar_gas_equation = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_gas_equation += alveolar_gas_equation(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_alveolar_gas_equation = perf_counter_ns()
    var _ns_alveolar_gas_equation = Float64(_t1_alveolar_gas_equation - _t0_alveolar_gas_equation) / Float64(N)
    print("MOJO_TIMING biomedical::alveolar_gas_equation", _ns_alveolar_gas_equation, _acc_alveolar_gas_equation)
    var _acc_bmi: Float64 = 0.0
    var _t0_bmi = perf_counter_ns()
    for _ in range(N):
        _acc_bmi += bmi(0.5, 0.5)
    var _t1_bmi = perf_counter_ns()
    var _ns_bmi = Float64(_t1_bmi - _t0_bmi) / Float64(N)
    print("MOJO_TIMING biomedical::bmi", _ns_bmi, _acc_bmi)
    var _acc_drug_clearance: Float64 = 0.0
    var _t0_drug_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_drug_clearance += drug_clearance(0.5, 0.5)
    var _t1_drug_clearance = perf_counter_ns()
    var _ns_drug_clearance = Float64(_t1_drug_clearance - _t0_drug_clearance) / Float64(N)
    print("MOJO_TIMING biomedical::drug_clearance", _ns_drug_clearance, _acc_drug_clearance)
    var _acc_anion_gap: Float64 = 0.0
    var _t0_anion_gap = perf_counter_ns()
    for _ in range(N):
        _acc_anion_gap += anion_gap(0.5, 0.5, 0.5)
    var _t1_anion_gap = perf_counter_ns()
    var _ns_anion_gap = Float64(_t1_anion_gap - _t0_anion_gap) / Float64(N)
    print("MOJO_TIMING biomedical::anion_gap", _ns_anion_gap, _acc_anion_gap)
    var _acc_corrected_qt_bazett: Float64 = 0.0
    var _t0_corrected_qt_bazett = perf_counter_ns()
    for _ in range(N):
        _acc_corrected_qt_bazett += corrected_qt_bazett(0.5, 0.5)
    var _t1_corrected_qt_bazett = perf_counter_ns()
    var _ns_corrected_qt_bazett = Float64(_t1_corrected_qt_bazett - _t0_corrected_qt_bazett) / Float64(N)
    print("MOJO_TIMING biomedical::corrected_qt_bazett", _ns_corrected_qt_bazett, _acc_corrected_qt_bazett)
    var _acc_fick_cardiac_output: Float64 = 0.0
    var _t0_fick_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_fick_cardiac_output += fick_cardiac_output(0.5, 0.5, 0.5)
    var _t1_fick_cardiac_output = perf_counter_ns()
    var _ns_fick_cardiac_output = Float64(_t1_fick_cardiac_output - _t0_fick_cardiac_output) / Float64(N)
    print("MOJO_TIMING biomedical::fick_cardiac_output", _ns_fick_cardiac_output, _acc_fick_cardiac_output)
    var _acc_pulse_pressure: Float64 = 0.0
    var _t0_pulse_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_pressure += pulse_pressure(0.5, 0.5)
    var _t1_pulse_pressure = perf_counter_ns()
    var _ns_pulse_pressure = Float64(_t1_pulse_pressure - _t0_pulse_pressure) / Float64(N)
    print("MOJO_TIMING biomedical::pulse_pressure", _ns_pulse_pressure, _acc_pulse_pressure)
