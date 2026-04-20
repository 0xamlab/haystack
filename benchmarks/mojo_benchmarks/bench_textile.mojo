"""bench_textile.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from textile import tex_to_denier, denier_to_tex, yarn_count_ne, tex_from_diameter_density, twist_per_meter, twist_multiplier, fabric_gsm, fabric_cover_factor, pilling_resistance_score, moisture_regain, shrinkage_percentage, breaking_tenacity
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

    var _acc_tex_to_denier: Float64 = 0.0
    var _t0_tex_to_denier = perf_counter_ns()
    for _ in range(N):
        _acc_tex_to_denier += tex_to_denier(0.5)
    var _t1_tex_to_denier = perf_counter_ns()
    var _ns_tex_to_denier = Float64(_t1_tex_to_denier - _t0_tex_to_denier) / Float64(N)
    print("MOJO_TIMING textile::tex_to_denier", _ns_tex_to_denier, _acc_tex_to_denier)
    var _acc_denier_to_tex: Float64 = 0.0
    var _t0_denier_to_tex = perf_counter_ns()
    for _ in range(N):
        _acc_denier_to_tex += denier_to_tex(0.5)
    var _t1_denier_to_tex = perf_counter_ns()
    var _ns_denier_to_tex = Float64(_t1_denier_to_tex - _t0_denier_to_tex) / Float64(N)
    print("MOJO_TIMING textile::denier_to_tex", _ns_denier_to_tex, _acc_denier_to_tex)
    var _acc_yarn_count_ne: Float64 = 0.0
    var _t0_yarn_count_ne = perf_counter_ns()
    for _ in range(N):
        _acc_yarn_count_ne += yarn_count_ne(0.5, 0.5)
    var _t1_yarn_count_ne = perf_counter_ns()
    var _ns_yarn_count_ne = Float64(_t1_yarn_count_ne - _t0_yarn_count_ne) / Float64(N)
    print("MOJO_TIMING textile::yarn_count_ne", _ns_yarn_count_ne, _acc_yarn_count_ne)
    var _acc_tex_from_diameter_density: Float64 = 0.0
    var _t0_tex_from_diameter_density = perf_counter_ns()
    for _ in range(N):
        _acc_tex_from_diameter_density += tex_from_diameter_density(0.5, 0.5)
    var _t1_tex_from_diameter_density = perf_counter_ns()
    var _ns_tex_from_diameter_density = Float64(_t1_tex_from_diameter_density - _t0_tex_from_diameter_density) / Float64(N)
    print("MOJO_TIMING textile::tex_from_diameter_density", _ns_tex_from_diameter_density, _acc_tex_from_diameter_density)
    var _acc_twist_per_meter: Float64 = 0.0
    var _t0_twist_per_meter = perf_counter_ns()
    for _ in range(N):
        _acc_twist_per_meter += twist_per_meter(0.5)
    var _t1_twist_per_meter = perf_counter_ns()
    var _ns_twist_per_meter = Float64(_t1_twist_per_meter - _t0_twist_per_meter) / Float64(N)
    print("MOJO_TIMING textile::twist_per_meter", _ns_twist_per_meter, _acc_twist_per_meter)
    var _acc_twist_multiplier: Float64 = 0.0
    var _t0_twist_multiplier = perf_counter_ns()
    for _ in range(N):
        _acc_twist_multiplier += twist_multiplier(0.5, 0.5)
    var _t1_twist_multiplier = perf_counter_ns()
    var _ns_twist_multiplier = Float64(_t1_twist_multiplier - _t0_twist_multiplier) / Float64(N)
    print("MOJO_TIMING textile::twist_multiplier", _ns_twist_multiplier, _acc_twist_multiplier)
    var _acc_fabric_gsm: Float64 = 0.0
    var _t0_fabric_gsm = perf_counter_ns()
    for _ in range(N):
        _acc_fabric_gsm += fabric_gsm(0.5, 0.5)
    var _t1_fabric_gsm = perf_counter_ns()
    var _ns_fabric_gsm = Float64(_t1_fabric_gsm - _t0_fabric_gsm) / Float64(N)
    print("MOJO_TIMING textile::fabric_gsm", _ns_fabric_gsm, _acc_fabric_gsm)
    var _acc_fabric_cover_factor: Float64 = 0.0
    var _t0_fabric_cover_factor = perf_counter_ns()
    for _ in range(N):
        _acc_fabric_cover_factor += fabric_cover_factor(0.5, 0.5)
    var _t1_fabric_cover_factor = perf_counter_ns()
    var _ns_fabric_cover_factor = Float64(_t1_fabric_cover_factor - _t0_fabric_cover_factor) / Float64(N)
    print("MOJO_TIMING textile::fabric_cover_factor", _ns_fabric_cover_factor, _acc_fabric_cover_factor)
    var _acc_pilling_resistance_score: Float64 = 0.0
    var _t0_pilling_resistance_score = perf_counter_ns()
    for _ in range(N):
        _acc_pilling_resistance_score += pilling_resistance_score(5, 0.5)
    var _t1_pilling_resistance_score = perf_counter_ns()
    var _ns_pilling_resistance_score = Float64(_t1_pilling_resistance_score - _t0_pilling_resistance_score) / Float64(N)
    print("MOJO_TIMING textile::pilling_resistance_score", _ns_pilling_resistance_score, _acc_pilling_resistance_score)
    var _acc_moisture_regain: Float64 = 0.0
    var _t0_moisture_regain = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_regain += moisture_regain(0.5, 0.5)
    var _t1_moisture_regain = perf_counter_ns()
    var _ns_moisture_regain = Float64(_t1_moisture_regain - _t0_moisture_regain) / Float64(N)
    print("MOJO_TIMING textile::moisture_regain", _ns_moisture_regain, _acc_moisture_regain)
    var _acc_shrinkage_percentage: Float64 = 0.0
    var _t0_shrinkage_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_shrinkage_percentage += shrinkage_percentage(0.5, 0.5)
    var _t1_shrinkage_percentage = perf_counter_ns()
    var _ns_shrinkage_percentage = Float64(_t1_shrinkage_percentage - _t0_shrinkage_percentage) / Float64(N)
    print("MOJO_TIMING textile::shrinkage_percentage", _ns_shrinkage_percentage, _acc_shrinkage_percentage)
    var _acc_breaking_tenacity: Float64 = 0.0
    var _t0_breaking_tenacity = perf_counter_ns()
    for _ in range(N):
        _acc_breaking_tenacity += breaking_tenacity(0.5, 0.5)
    var _t1_breaking_tenacity = perf_counter_ns()
    var _ns_breaking_tenacity = Float64(_t1_breaking_tenacity - _t0_breaking_tenacity) / Float64(N)
    print("MOJO_TIMING textile::breaking_tenacity", _ns_breaking_tenacity, _acc_breaking_tenacity)
