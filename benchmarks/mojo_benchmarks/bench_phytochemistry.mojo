"""bench_phytochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from phytochemistry import phenolic_content_folin, flavonoid_content, anthocyanin_concentration, tannin_content, essential_oil_yield, alkaloid_gravimetric, chlorophyll_a, chlorophyll_b, carotenoid_content, dpph_radical_scavenging
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

    var _acc_phenolic_content_folin: Float64 = 0.0
    var _t0_phenolic_content_folin = perf_counter_ns()
    for _ in range(N):
        _acc_phenolic_content_folin += phenolic_content_folin(0.5, 0.5, 0.5, 0.5)
    var _t1_phenolic_content_folin = perf_counter_ns()
    var _ns_phenolic_content_folin = Float64(_t1_phenolic_content_folin - _t0_phenolic_content_folin) / Float64(N)
    print("MOJO_TIMING phytochemistry::phenolic_content_folin", _ns_phenolic_content_folin, _acc_phenolic_content_folin)
    var _acc_flavonoid_content: Float64 = 0.0
    var _t0_flavonoid_content = perf_counter_ns()
    for _ in range(N):
        _acc_flavonoid_content += flavonoid_content(0.5, 0.5, 0.5, 0.5)
    var _t1_flavonoid_content = perf_counter_ns()
    var _ns_flavonoid_content = Float64(_t1_flavonoid_content - _t0_flavonoid_content) / Float64(N)
    print("MOJO_TIMING phytochemistry::flavonoid_content", _ns_flavonoid_content, _acc_flavonoid_content)
    var _acc_anthocyanin_concentration: Float64 = 0.0
    var _t0_anthocyanin_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_anthocyanin_concentration += anthocyanin_concentration(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_anthocyanin_concentration = perf_counter_ns()
    var _ns_anthocyanin_concentration = Float64(_t1_anthocyanin_concentration - _t0_anthocyanin_concentration) / Float64(N)
    print("MOJO_TIMING phytochemistry::anthocyanin_concentration", _ns_anthocyanin_concentration, _acc_anthocyanin_concentration)
    var _acc_tannin_content: Float64 = 0.0
    var _t0_tannin_content = perf_counter_ns()
    for _ in range(N):
        _acc_tannin_content += tannin_content(0.5, 0.5)
    var _t1_tannin_content = perf_counter_ns()
    var _ns_tannin_content = Float64(_t1_tannin_content - _t0_tannin_content) / Float64(N)
    print("MOJO_TIMING phytochemistry::tannin_content", _ns_tannin_content, _acc_tannin_content)
    var _acc_essential_oil_yield: Float64 = 0.0
    var _t0_essential_oil_yield = perf_counter_ns()
    for _ in range(N):
        _acc_essential_oil_yield += essential_oil_yield(0.5, 0.5)
    var _t1_essential_oil_yield = perf_counter_ns()
    var _ns_essential_oil_yield = Float64(_t1_essential_oil_yield - _t0_essential_oil_yield) / Float64(N)
    print("MOJO_TIMING phytochemistry::essential_oil_yield", _ns_essential_oil_yield, _acc_essential_oil_yield)
    var _acc_alkaloid_gravimetric: Float64 = 0.0
    var _t0_alkaloid_gravimetric = perf_counter_ns()
    for _ in range(N):
        _acc_alkaloid_gravimetric += alkaloid_gravimetric(0.5, 0.5)
    var _t1_alkaloid_gravimetric = perf_counter_ns()
    var _ns_alkaloid_gravimetric = Float64(_t1_alkaloid_gravimetric - _t0_alkaloid_gravimetric) / Float64(N)
    print("MOJO_TIMING phytochemistry::alkaloid_gravimetric", _ns_alkaloid_gravimetric, _acc_alkaloid_gravimetric)
    var _acc_chlorophyll_a: Float64 = 0.0
    var _t0_chlorophyll_a = perf_counter_ns()
    for _ in range(N):
        _acc_chlorophyll_a += chlorophyll_a(0.5, 0.5)
    var _t1_chlorophyll_a = perf_counter_ns()
    var _ns_chlorophyll_a = Float64(_t1_chlorophyll_a - _t0_chlorophyll_a) / Float64(N)
    print("MOJO_TIMING phytochemistry::chlorophyll_a", _ns_chlorophyll_a, _acc_chlorophyll_a)
    var _acc_chlorophyll_b: Float64 = 0.0
    var _t0_chlorophyll_b = perf_counter_ns()
    for _ in range(N):
        _acc_chlorophyll_b += chlorophyll_b(0.5, 0.5)
    var _t1_chlorophyll_b = perf_counter_ns()
    var _ns_chlorophyll_b = Float64(_t1_chlorophyll_b - _t0_chlorophyll_b) / Float64(N)
    print("MOJO_TIMING phytochemistry::chlorophyll_b", _ns_chlorophyll_b, _acc_chlorophyll_b)
    var _acc_carotenoid_content: Float64 = 0.0
    var _t0_carotenoid_content = perf_counter_ns()
    for _ in range(N):
        _acc_carotenoid_content += carotenoid_content(0.5, 0.5, 0.5)
    var _t1_carotenoid_content = perf_counter_ns()
    var _ns_carotenoid_content = Float64(_t1_carotenoid_content - _t0_carotenoid_content) / Float64(N)
    print("MOJO_TIMING phytochemistry::carotenoid_content", _ns_carotenoid_content, _acc_carotenoid_content)
    var _acc_dpph_radical_scavenging: Float64 = 0.0
    var _t0_dpph_radical_scavenging = perf_counter_ns()
    for _ in range(N):
        _acc_dpph_radical_scavenging += dpph_radical_scavenging(0.5, 0.5)
    var _t1_dpph_radical_scavenging = perf_counter_ns()
    var _ns_dpph_radical_scavenging = Float64(_t1_dpph_radical_scavenging - _t0_dpph_radical_scavenging) / Float64(N)
    print("MOJO_TIMING phytochemistry::dpph_radical_scavenging", _ns_dpph_radical_scavenging, _acc_dpph_radical_scavenging)
