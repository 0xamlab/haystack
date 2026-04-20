"""bench_printing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from printing import dpi_to_lpi, pixel_count, file_size_uncompressed, bleed_area, spine_width, ink_coverage, paper_weight_gsm_to_lb, sheets_per_ream, cost_per_page, imposition_pages, color_delta_e, dot_gain_apparent
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

    var _acc_dpi_to_lpi: Float64 = 0.0
    var _t0_dpi_to_lpi = perf_counter_ns()
    for _ in range(N):
        _acc_dpi_to_lpi += dpi_to_lpi(0.5, 0.5)
    var _t1_dpi_to_lpi = perf_counter_ns()
    var _ns_dpi_to_lpi = Float64(_t1_dpi_to_lpi - _t0_dpi_to_lpi) / Float64(N)
    print("MOJO_TIMING printing::dpi_to_lpi", _ns_dpi_to_lpi, _acc_dpi_to_lpi)
    var _acc_pixel_count: Float64 = 0.0
    var _t0_pixel_count = perf_counter_ns()
    for _ in range(N):
        _acc_pixel_count += pixel_count(0.5, 0.5, 0.5)
    var _t1_pixel_count = perf_counter_ns()
    var _ns_pixel_count = Float64(_t1_pixel_count - _t0_pixel_count) / Float64(N)
    print("MOJO_TIMING printing::pixel_count", _ns_pixel_count, _acc_pixel_count)
    var _acc_file_size_uncompressed: Float64 = 0.0
    var _t0_file_size_uncompressed = perf_counter_ns()
    for _ in range(N):
        _acc_file_size_uncompressed += file_size_uncompressed(0.5, 0.5, 0.5, 0.5)
    var _t1_file_size_uncompressed = perf_counter_ns()
    var _ns_file_size_uncompressed = Float64(_t1_file_size_uncompressed - _t0_file_size_uncompressed) / Float64(N)
    print("MOJO_TIMING printing::file_size_uncompressed", _ns_file_size_uncompressed, _acc_file_size_uncompressed)
    var _acc_bleed_area: Float64 = 0.0
    var _t0_bleed_area = perf_counter_ns()
    for _ in range(N):
        _acc_bleed_area += bleed_area(0.5, 0.5, 0.5)
    var _t1_bleed_area = perf_counter_ns()
    var _ns_bleed_area = Float64(_t1_bleed_area - _t0_bleed_area) / Float64(N)
    print("MOJO_TIMING printing::bleed_area", _ns_bleed_area, _acc_bleed_area)
    var _acc_spine_width: Float64 = 0.0
    var _t0_spine_width = perf_counter_ns()
    for _ in range(N):
        _acc_spine_width += spine_width(0.5, 0.5)
    var _t1_spine_width = perf_counter_ns()
    var _ns_spine_width = Float64(_t1_spine_width - _t0_spine_width) / Float64(N)
    print("MOJO_TIMING printing::spine_width", _ns_spine_width, _acc_spine_width)
    var _acc_ink_coverage: Float64 = 0.0
    var _t0_ink_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_ink_coverage += ink_coverage(0.5, 0.5, 0.5, 0.5)
    var _t1_ink_coverage = perf_counter_ns()
    var _ns_ink_coverage = Float64(_t1_ink_coverage - _t0_ink_coverage) / Float64(N)
    print("MOJO_TIMING printing::ink_coverage", _ns_ink_coverage, _acc_ink_coverage)
    var _acc_paper_weight_gsm_to_lb: Float64 = 0.0
    var _t0_paper_weight_gsm_to_lb = perf_counter_ns()
    for _ in range(N):
        _acc_paper_weight_gsm_to_lb += paper_weight_gsm_to_lb(0.5)
    var _t1_paper_weight_gsm_to_lb = perf_counter_ns()
    var _ns_paper_weight_gsm_to_lb = Float64(_t1_paper_weight_gsm_to_lb - _t0_paper_weight_gsm_to_lb) / Float64(N)
    print("MOJO_TIMING printing::paper_weight_gsm_to_lb", _ns_paper_weight_gsm_to_lb, _acc_paper_weight_gsm_to_lb)
    var _acc_sheets_per_ream: Float64 = 0.0
    var _t0_sheets_per_ream = perf_counter_ns()
    for _ in range(N):
        _acc_sheets_per_ream += Float64(sheets_per_ream())
    var _t1_sheets_per_ream = perf_counter_ns()
    var _ns_sheets_per_ream = Float64(_t1_sheets_per_ream - _t0_sheets_per_ream) / Float64(N)
    print("MOJO_TIMING printing::sheets_per_ream", _ns_sheets_per_ream, _acc_sheets_per_ream)
    var _acc_cost_per_page: Float64 = 0.0
    var _t0_cost_per_page = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_page += cost_per_page(0.5, 0.5)
    var _t1_cost_per_page = perf_counter_ns()
    var _ns_cost_per_page = Float64(_t1_cost_per_page - _t0_cost_per_page) / Float64(N)
    print("MOJO_TIMING printing::cost_per_page", _ns_cost_per_page, _acc_cost_per_page)
    var _acc_imposition_pages: Float64 = 0.0
    var _t0_imposition_pages = perf_counter_ns()
    for _ in range(N):
        _acc_imposition_pages += imposition_pages(0.5, 0.5)
    var _t1_imposition_pages = perf_counter_ns()
    var _ns_imposition_pages = Float64(_t1_imposition_pages - _t0_imposition_pages) / Float64(N)
    print("MOJO_TIMING printing::imposition_pages", _ns_imposition_pages, _acc_imposition_pages)
    var _acc_color_delta_e: Float64 = 0.0
    var _t0_color_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_color_delta_e += color_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_color_delta_e = perf_counter_ns()
    var _ns_color_delta_e = Float64(_t1_color_delta_e - _t0_color_delta_e) / Float64(N)
    print("MOJO_TIMING printing::color_delta_e", _ns_color_delta_e, _acc_color_delta_e)
    var _acc_dot_gain_apparent: Float64 = 0.0
    var _t0_dot_gain_apparent = perf_counter_ns()
    for _ in range(N):
        _acc_dot_gain_apparent += dot_gain_apparent(0.5, 0.5)
    var _t1_dot_gain_apparent = perf_counter_ns()
    var _ns_dot_gain_apparent = Float64(_t1_dot_gain_apparent - _t0_dot_gain_apparent) / Float64(N)
    print("MOJO_TIMING printing::dot_gain_apparent", _ns_dot_gain_apparent, _acc_dot_gain_apparent)
