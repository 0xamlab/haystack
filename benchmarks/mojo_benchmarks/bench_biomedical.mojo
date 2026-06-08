"""bench_biomedical.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biomedical import cardiac_output, mean_arterial_pressure, body_surface_area_dubois, glomerular_filtration_rate, oxygen_delivery, alveolar_gas_equation, bmi, drug_clearance, anion_gap, corrected_qt_bazett, fick_cardiac_output, pulse_pressure
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_cardiac_output = cardiac_output(0.5, 0.5)
    var _summary_cardiac_output = _summary_float64(_result_cardiac_output)
    print("MOJO_RESULT biomedical::cardiac_output", _summary_cardiac_output)
    var _acc_mean_arterial_pressure: Float64 = 0.0
    var _t0_mean_arterial_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_mean_arterial_pressure += mean_arterial_pressure(0.5, 0.5)
    var _t1_mean_arterial_pressure = perf_counter_ns()
    var _ns_mean_arterial_pressure = Float64(_t1_mean_arterial_pressure - _t0_mean_arterial_pressure) / Float64(N)
    print("MOJO_TIMING biomedical::mean_arterial_pressure", _ns_mean_arterial_pressure, _acc_mean_arterial_pressure)
    var _result_mean_arterial_pressure = mean_arterial_pressure(0.5, 0.5)
    var _summary_mean_arterial_pressure = _summary_float64(_result_mean_arterial_pressure)
    print("MOJO_RESULT biomedical::mean_arterial_pressure", _summary_mean_arterial_pressure)
    var _acc_body_surface_area_dubois: Float64 = 0.0
    var _t0_body_surface_area_dubois = perf_counter_ns()
    for _ in range(N):
        _acc_body_surface_area_dubois += body_surface_area_dubois(0.5, 0.5)
    var _t1_body_surface_area_dubois = perf_counter_ns()
    var _ns_body_surface_area_dubois = Float64(_t1_body_surface_area_dubois - _t0_body_surface_area_dubois) / Float64(N)
    print("MOJO_TIMING biomedical::body_surface_area_dubois", _ns_body_surface_area_dubois, _acc_body_surface_area_dubois)
    var _result_body_surface_area_dubois = body_surface_area_dubois(0.5, 0.5)
    var _summary_body_surface_area_dubois = _summary_float64(_result_body_surface_area_dubois)
    print("MOJO_RESULT biomedical::body_surface_area_dubois", _summary_body_surface_area_dubois)
    var _acc_glomerular_filtration_rate: Float64 = 0.0
    var _t0_glomerular_filtration_rate = perf_counter_ns()
    for _ in range(N):
        _acc_glomerular_filtration_rate += glomerular_filtration_rate(0.5, 0.5, 0.5, True)
    var _t1_glomerular_filtration_rate = perf_counter_ns()
    var _ns_glomerular_filtration_rate = Float64(_t1_glomerular_filtration_rate - _t0_glomerular_filtration_rate) / Float64(N)
    print("MOJO_TIMING biomedical::glomerular_filtration_rate", _ns_glomerular_filtration_rate, _acc_glomerular_filtration_rate)
    var _result_glomerular_filtration_rate = glomerular_filtration_rate(0.5, 0.5, 0.5, True)
    var _summary_glomerular_filtration_rate = _summary_float64(_result_glomerular_filtration_rate)
    print("MOJO_RESULT biomedical::glomerular_filtration_rate", _summary_glomerular_filtration_rate)
    var _acc_oxygen_delivery: Float64 = 0.0
    var _t0_oxygen_delivery = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_delivery += oxygen_delivery(0.5, 0.5, 0.5)
    var _t1_oxygen_delivery = perf_counter_ns()
    var _ns_oxygen_delivery = Float64(_t1_oxygen_delivery - _t0_oxygen_delivery) / Float64(N)
    print("MOJO_TIMING biomedical::oxygen_delivery", _ns_oxygen_delivery, _acc_oxygen_delivery)
    var _result_oxygen_delivery = oxygen_delivery(0.5, 0.5, 0.5)
    var _summary_oxygen_delivery = _summary_float64(_result_oxygen_delivery)
    print("MOJO_RESULT biomedical::oxygen_delivery", _summary_oxygen_delivery)
    var _acc_alveolar_gas_equation: Float64 = 0.0
    var _t0_alveolar_gas_equation = perf_counter_ns()
    for _ in range(N):
        _acc_alveolar_gas_equation += alveolar_gas_equation(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_alveolar_gas_equation = perf_counter_ns()
    var _ns_alveolar_gas_equation = Float64(_t1_alveolar_gas_equation - _t0_alveolar_gas_equation) / Float64(N)
    print("MOJO_TIMING biomedical::alveolar_gas_equation", _ns_alveolar_gas_equation, _acc_alveolar_gas_equation)
    var _result_alveolar_gas_equation = alveolar_gas_equation(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_alveolar_gas_equation = _summary_float64(_result_alveolar_gas_equation)
    print("MOJO_RESULT biomedical::alveolar_gas_equation", _summary_alveolar_gas_equation)
    var _acc_bmi: Float64 = 0.0
    var _t0_bmi = perf_counter_ns()
    for _ in range(N):
        _acc_bmi += bmi(0.5, 0.5)
    var _t1_bmi = perf_counter_ns()
    var _ns_bmi = Float64(_t1_bmi - _t0_bmi) / Float64(N)
    print("MOJO_TIMING biomedical::bmi", _ns_bmi, _acc_bmi)
    var _result_bmi = bmi(0.5, 0.5)
    var _summary_bmi = _summary_float64(_result_bmi)
    print("MOJO_RESULT biomedical::bmi", _summary_bmi)
    var _acc_drug_clearance: Float64 = 0.0
    var _t0_drug_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_drug_clearance += drug_clearance(0.5, 0.5)
    var _t1_drug_clearance = perf_counter_ns()
    var _ns_drug_clearance = Float64(_t1_drug_clearance - _t0_drug_clearance) / Float64(N)
    print("MOJO_TIMING biomedical::drug_clearance", _ns_drug_clearance, _acc_drug_clearance)
    var _result_drug_clearance = drug_clearance(0.5, 0.5)
    var _summary_drug_clearance = _summary_float64(_result_drug_clearance)
    print("MOJO_RESULT biomedical::drug_clearance", _summary_drug_clearance)
    var _acc_anion_gap: Float64 = 0.0
    var _t0_anion_gap = perf_counter_ns()
    for _ in range(N):
        _acc_anion_gap += anion_gap(0.5, 0.5, 0.5)
    var _t1_anion_gap = perf_counter_ns()
    var _ns_anion_gap = Float64(_t1_anion_gap - _t0_anion_gap) / Float64(N)
    print("MOJO_TIMING biomedical::anion_gap", _ns_anion_gap, _acc_anion_gap)
    var _result_anion_gap = anion_gap(0.5, 0.5, 0.5)
    var _summary_anion_gap = _summary_float64(_result_anion_gap)
    print("MOJO_RESULT biomedical::anion_gap", _summary_anion_gap)
    var _acc_corrected_qt_bazett: Float64 = 0.0
    var _t0_corrected_qt_bazett = perf_counter_ns()
    for _ in range(N):
        _acc_corrected_qt_bazett += corrected_qt_bazett(0.5, 0.5)
    var _t1_corrected_qt_bazett = perf_counter_ns()
    var _ns_corrected_qt_bazett = Float64(_t1_corrected_qt_bazett - _t0_corrected_qt_bazett) / Float64(N)
    print("MOJO_TIMING biomedical::corrected_qt_bazett", _ns_corrected_qt_bazett, _acc_corrected_qt_bazett)
    var _result_corrected_qt_bazett = corrected_qt_bazett(0.5, 0.5)
    var _summary_corrected_qt_bazett = _summary_float64(_result_corrected_qt_bazett)
    print("MOJO_RESULT biomedical::corrected_qt_bazett", _summary_corrected_qt_bazett)
    var _acc_fick_cardiac_output: Float64 = 0.0
    var _t0_fick_cardiac_output = perf_counter_ns()
    for _ in range(N):
        _acc_fick_cardiac_output += fick_cardiac_output(0.5, 0.5, 0.5)
    var _t1_fick_cardiac_output = perf_counter_ns()
    var _ns_fick_cardiac_output = Float64(_t1_fick_cardiac_output - _t0_fick_cardiac_output) / Float64(N)
    print("MOJO_TIMING biomedical::fick_cardiac_output", _ns_fick_cardiac_output, _acc_fick_cardiac_output)
    var _result_fick_cardiac_output = fick_cardiac_output(0.5, 0.5, 0.5)
    var _summary_fick_cardiac_output = _summary_float64(_result_fick_cardiac_output)
    print("MOJO_RESULT biomedical::fick_cardiac_output", _summary_fick_cardiac_output)
    var _acc_pulse_pressure: Float64 = 0.0
    var _t0_pulse_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pulse_pressure += pulse_pressure(0.5, 0.5)
    var _t1_pulse_pressure = perf_counter_ns()
    var _ns_pulse_pressure = Float64(_t1_pulse_pressure - _t0_pulse_pressure) / Float64(N)
    print("MOJO_TIMING biomedical::pulse_pressure", _ns_pulse_pressure, _acc_pulse_pressure)
    var _result_pulse_pressure = pulse_pressure(0.5, 0.5)
    var _summary_pulse_pressure = _summary_float64(_result_pulse_pressure)
    print("MOJO_RESULT biomedical::pulse_pressure", _summary_pulse_pressure)
