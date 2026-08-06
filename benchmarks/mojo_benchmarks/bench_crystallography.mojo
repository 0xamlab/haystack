"""bench_crystallography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crystallography import bragg_angle, d_spacing_cubic, lattice_parameter_from_d, unit_cell_volume_cubic, unit_cell_volume_tetragonal, unit_cell_volume_orthorhombic, atomic_packing_factor_fcc, atomic_packing_factor_bcc, scherrer_crystallite_size, interplanar_angle_cubic, density_from_crystal, structure_factor_magnitude
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_bragg_angle: Float64 = 0.0
    var _t0_bragg_angle = perf_counter_ns()
    for _ in range(N):
        _acc_bragg_angle += bragg_angle(0.5, 0.5, 0.5)
    var _t1_bragg_angle = perf_counter_ns()
    var _ns_bragg_angle = Float64(_t1_bragg_angle - _t0_bragg_angle) / Float64(N)
    print("MOJO_TIMING crystallography::bragg_angle", _ns_bragg_angle, _acc_bragg_angle)
    var _result_bragg_angle = bragg_angle(0.5, 0.5, 0.5)
    var _summary_bragg_angle = _summary_float64(_result_bragg_angle)
    print("MOJO_RESULT crystallography::bragg_angle", _summary_bragg_angle)
    var _acc_d_spacing_cubic: Float64 = 0.0
    var _t0_d_spacing_cubic = perf_counter_ns()
    for _ in range(N):
        _acc_d_spacing_cubic += d_spacing_cubic(0.5, 0.5, 0.5, 0.5)
    var _t1_d_spacing_cubic = perf_counter_ns()
    var _ns_d_spacing_cubic = Float64(_t1_d_spacing_cubic - _t0_d_spacing_cubic) / Float64(N)
    print("MOJO_TIMING crystallography::d_spacing_cubic", _ns_d_spacing_cubic, _acc_d_spacing_cubic)
    var _result_d_spacing_cubic = d_spacing_cubic(0.5, 0.5, 0.5, 0.5)
    var _summary_d_spacing_cubic = _summary_float64(_result_d_spacing_cubic)
    print("MOJO_RESULT crystallography::d_spacing_cubic", _summary_d_spacing_cubic)
    var _acc_lattice_parameter_from_d: Float64 = 0.0
    var _t0_lattice_parameter_from_d = perf_counter_ns()
    for _ in range(N):
        _acc_lattice_parameter_from_d += lattice_parameter_from_d(0.5, 0.5, 0.5, 0.5)
    var _t1_lattice_parameter_from_d = perf_counter_ns()
    var _ns_lattice_parameter_from_d = Float64(_t1_lattice_parameter_from_d - _t0_lattice_parameter_from_d) / Float64(N)
    print("MOJO_TIMING crystallography::lattice_parameter_from_d", _ns_lattice_parameter_from_d, _acc_lattice_parameter_from_d)
    var _result_lattice_parameter_from_d = lattice_parameter_from_d(0.5, 0.5, 0.5, 0.5)
    var _summary_lattice_parameter_from_d = _summary_float64(_result_lattice_parameter_from_d)
    print("MOJO_RESULT crystallography::lattice_parameter_from_d", _summary_lattice_parameter_from_d)
    var _acc_unit_cell_volume_cubic: Float64 = 0.0
    var _t0_unit_cell_volume_cubic = perf_counter_ns()
    for _ in range(N):
        _acc_unit_cell_volume_cubic += unit_cell_volume_cubic(0.5)
    var _t1_unit_cell_volume_cubic = perf_counter_ns()
    var _ns_unit_cell_volume_cubic = Float64(_t1_unit_cell_volume_cubic - _t0_unit_cell_volume_cubic) / Float64(N)
    print("MOJO_TIMING crystallography::unit_cell_volume_cubic", _ns_unit_cell_volume_cubic, _acc_unit_cell_volume_cubic)
    var _result_unit_cell_volume_cubic = unit_cell_volume_cubic(0.5)
    var _summary_unit_cell_volume_cubic = _summary_float64(_result_unit_cell_volume_cubic)
    print("MOJO_RESULT crystallography::unit_cell_volume_cubic", _summary_unit_cell_volume_cubic)
    var _acc_unit_cell_volume_tetragonal: Float64 = 0.0
    var _t0_unit_cell_volume_tetragonal = perf_counter_ns()
    for _ in range(N):
        _acc_unit_cell_volume_tetragonal += unit_cell_volume_tetragonal(0.5, 0.5)
    var _t1_unit_cell_volume_tetragonal = perf_counter_ns()
    var _ns_unit_cell_volume_tetragonal = Float64(_t1_unit_cell_volume_tetragonal - _t0_unit_cell_volume_tetragonal) / Float64(N)
    print("MOJO_TIMING crystallography::unit_cell_volume_tetragonal", _ns_unit_cell_volume_tetragonal, _acc_unit_cell_volume_tetragonal)
    var _result_unit_cell_volume_tetragonal = unit_cell_volume_tetragonal(0.5, 0.5)
    var _summary_unit_cell_volume_tetragonal = _summary_float64(_result_unit_cell_volume_tetragonal)
    print("MOJO_RESULT crystallography::unit_cell_volume_tetragonal", _summary_unit_cell_volume_tetragonal)
    var _acc_unit_cell_volume_orthorhombic: Float64 = 0.0
    var _t0_unit_cell_volume_orthorhombic = perf_counter_ns()
    for _ in range(N):
        _acc_unit_cell_volume_orthorhombic += unit_cell_volume_orthorhombic(0.5, 0.5, 0.5)
    var _t1_unit_cell_volume_orthorhombic = perf_counter_ns()
    var _ns_unit_cell_volume_orthorhombic = Float64(_t1_unit_cell_volume_orthorhombic - _t0_unit_cell_volume_orthorhombic) / Float64(N)
    print("MOJO_TIMING crystallography::unit_cell_volume_orthorhombic", _ns_unit_cell_volume_orthorhombic, _acc_unit_cell_volume_orthorhombic)
    var _result_unit_cell_volume_orthorhombic = unit_cell_volume_orthorhombic(0.5, 0.5, 0.5)
    var _summary_unit_cell_volume_orthorhombic = _summary_float64(_result_unit_cell_volume_orthorhombic)
    print("MOJO_RESULT crystallography::unit_cell_volume_orthorhombic", _summary_unit_cell_volume_orthorhombic)
    var _acc_atomic_packing_factor_fcc: Float64 = 0.0
    var _t0_atomic_packing_factor_fcc = perf_counter_ns()
    for _ in range(N):
        _acc_atomic_packing_factor_fcc += atomic_packing_factor_fcc()
    var _t1_atomic_packing_factor_fcc = perf_counter_ns()
    var _ns_atomic_packing_factor_fcc = Float64(_t1_atomic_packing_factor_fcc - _t0_atomic_packing_factor_fcc) / Float64(N)
    print("MOJO_TIMING crystallography::atomic_packing_factor_fcc", _ns_atomic_packing_factor_fcc, _acc_atomic_packing_factor_fcc)
    var _result_atomic_packing_factor_fcc = atomic_packing_factor_fcc()
    var _summary_atomic_packing_factor_fcc = _summary_float64(_result_atomic_packing_factor_fcc)
    print("MOJO_RESULT crystallography::atomic_packing_factor_fcc", _summary_atomic_packing_factor_fcc)
    var _acc_atomic_packing_factor_bcc: Float64 = 0.0
    var _t0_atomic_packing_factor_bcc = perf_counter_ns()
    for _ in range(N):
        _acc_atomic_packing_factor_bcc += atomic_packing_factor_bcc()
    var _t1_atomic_packing_factor_bcc = perf_counter_ns()
    var _ns_atomic_packing_factor_bcc = Float64(_t1_atomic_packing_factor_bcc - _t0_atomic_packing_factor_bcc) / Float64(N)
    print("MOJO_TIMING crystallography::atomic_packing_factor_bcc", _ns_atomic_packing_factor_bcc, _acc_atomic_packing_factor_bcc)
    var _result_atomic_packing_factor_bcc = atomic_packing_factor_bcc()
    var _summary_atomic_packing_factor_bcc = _summary_float64(_result_atomic_packing_factor_bcc)
    print("MOJO_RESULT crystallography::atomic_packing_factor_bcc", _summary_atomic_packing_factor_bcc)
    var _acc_scherrer_crystallite_size: Float64 = 0.0
    var _t0_scherrer_crystallite_size = perf_counter_ns()
    for _ in range(N):
        _acc_scherrer_crystallite_size += scherrer_crystallite_size(0.5, 0.5, 0.5, 0.5)
    var _t1_scherrer_crystallite_size = perf_counter_ns()
    var _ns_scherrer_crystallite_size = Float64(_t1_scherrer_crystallite_size - _t0_scherrer_crystallite_size) / Float64(N)
    print("MOJO_TIMING crystallography::scherrer_crystallite_size", _ns_scherrer_crystallite_size, _acc_scherrer_crystallite_size)
    var _result_scherrer_crystallite_size = scherrer_crystallite_size(0.5, 0.5, 0.5, 0.5)
    var _summary_scherrer_crystallite_size = _summary_float64(_result_scherrer_crystallite_size)
    print("MOJO_RESULT crystallography::scherrer_crystallite_size", _summary_scherrer_crystallite_size)
    var _acc_interplanar_angle_cubic: Float64 = 0.0
    var _t0_interplanar_angle_cubic = perf_counter_ns()
    for _ in range(N):
        _acc_interplanar_angle_cubic += interplanar_angle_cubic(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_interplanar_angle_cubic = perf_counter_ns()
    var _ns_interplanar_angle_cubic = Float64(_t1_interplanar_angle_cubic - _t0_interplanar_angle_cubic) / Float64(N)
    print("MOJO_TIMING crystallography::interplanar_angle_cubic", _ns_interplanar_angle_cubic, _acc_interplanar_angle_cubic)
    var _result_interplanar_angle_cubic = interplanar_angle_cubic(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_interplanar_angle_cubic = _summary_float64(_result_interplanar_angle_cubic)
    print("MOJO_RESULT crystallography::interplanar_angle_cubic", _summary_interplanar_angle_cubic)
    var _acc_density_from_crystal: Float64 = 0.0
    var _t0_density_from_crystal = perf_counter_ns()
    for _ in range(N):
        _acc_density_from_crystal += density_from_crystal(0.5, 0.5, 0.5, 0.5)
    var _t1_density_from_crystal = perf_counter_ns()
    var _ns_density_from_crystal = Float64(_t1_density_from_crystal - _t0_density_from_crystal) / Float64(N)
    print("MOJO_TIMING crystallography::density_from_crystal", _ns_density_from_crystal, _acc_density_from_crystal)
    var _result_density_from_crystal = density_from_crystal(0.5, 0.5, 0.5, 0.5)
    var _summary_density_from_crystal = _summary_float64(_result_density_from_crystal)
    print("MOJO_RESULT crystallography::density_from_crystal", _summary_density_from_crystal)
    var _acc_structure_factor_magnitude: Float64 = 0.0
    var _t0_structure_factor_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_structure_factor_magnitude += structure_factor_magnitude(0.5, 0.5)
    var _t1_structure_factor_magnitude = perf_counter_ns()
    var _ns_structure_factor_magnitude = Float64(_t1_structure_factor_magnitude - _t0_structure_factor_magnitude) / Float64(N)
    print("MOJO_TIMING crystallography::structure_factor_magnitude", _ns_structure_factor_magnitude, _acc_structure_factor_magnitude)
    var _result_structure_factor_magnitude = structure_factor_magnitude(0.5, 0.5)
    var _summary_structure_factor_magnitude = _summary_float64(_result_structure_factor_magnitude)
    print("MOJO_RESULT crystallography::structure_factor_magnitude", _summary_structure_factor_magnitude)
