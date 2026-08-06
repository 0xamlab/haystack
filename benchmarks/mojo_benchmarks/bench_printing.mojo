"""bench_printing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from printing import dpi_to_lpi, pixel_count, file_size_uncompressed, bleed_area, spine_width, ink_coverage, paper_weight_gsm_to_lb, sheets_per_ream, cost_per_page, imposition_pages, color_delta_e, dot_gain_apparent
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

    var _acc_dpi_to_lpi: Float64 = 0.0
    var _t0_dpi_to_lpi = perf_counter_ns()
    for _ in range(N):
        _acc_dpi_to_lpi += dpi_to_lpi(0.5, 0.5)
    var _t1_dpi_to_lpi = perf_counter_ns()
    var _ns_dpi_to_lpi = Float64(_t1_dpi_to_lpi - _t0_dpi_to_lpi) / Float64(N)
    print("MOJO_TIMING printing::dpi_to_lpi", _ns_dpi_to_lpi, _acc_dpi_to_lpi)
    var _result_dpi_to_lpi = dpi_to_lpi(0.5, 0.5)
    var _summary_dpi_to_lpi = _summary_float64(_result_dpi_to_lpi)
    print("MOJO_RESULT printing::dpi_to_lpi", _summary_dpi_to_lpi)
    var _acc_pixel_count: Float64 = 0.0
    var _t0_pixel_count = perf_counter_ns()
    for _ in range(N):
        _acc_pixel_count += pixel_count(0.5, 0.5, 0.5)
    var _t1_pixel_count = perf_counter_ns()
    var _ns_pixel_count = Float64(_t1_pixel_count - _t0_pixel_count) / Float64(N)
    print("MOJO_TIMING printing::pixel_count", _ns_pixel_count, _acc_pixel_count)
    var _result_pixel_count = pixel_count(0.5, 0.5, 0.5)
    var _summary_pixel_count = _summary_float64(_result_pixel_count)
    print("MOJO_RESULT printing::pixel_count", _summary_pixel_count)
    var _acc_file_size_uncompressed: Float64 = 0.0
    var _t0_file_size_uncompressed = perf_counter_ns()
    for _ in range(N):
        _acc_file_size_uncompressed += file_size_uncompressed(0.5, 0.5, 0.5, 0.5)
    var _t1_file_size_uncompressed = perf_counter_ns()
    var _ns_file_size_uncompressed = Float64(_t1_file_size_uncompressed - _t0_file_size_uncompressed) / Float64(N)
    print("MOJO_TIMING printing::file_size_uncompressed", _ns_file_size_uncompressed, _acc_file_size_uncompressed)
    var _result_file_size_uncompressed = file_size_uncompressed(0.5, 0.5, 0.5, 0.5)
    var _summary_file_size_uncompressed = _summary_float64(_result_file_size_uncompressed)
    print("MOJO_RESULT printing::file_size_uncompressed", _summary_file_size_uncompressed)
    var _acc_bleed_area: Float64 = 0.0
    var _t0_bleed_area = perf_counter_ns()
    for _ in range(N):
        _acc_bleed_area += bleed_area(0.5, 0.5, 0.5)
    var _t1_bleed_area = perf_counter_ns()
    var _ns_bleed_area = Float64(_t1_bleed_area - _t0_bleed_area) / Float64(N)
    print("MOJO_TIMING printing::bleed_area", _ns_bleed_area, _acc_bleed_area)
    var _result_bleed_area = bleed_area(0.5, 0.5, 0.5)
    var _summary_bleed_area = _summary_float64(_result_bleed_area)
    print("MOJO_RESULT printing::bleed_area", _summary_bleed_area)
    var _acc_spine_width: Float64 = 0.0
    var _t0_spine_width = perf_counter_ns()
    for _ in range(N):
        _acc_spine_width += spine_width(0.5, 0.5)
    var _t1_spine_width = perf_counter_ns()
    var _ns_spine_width = Float64(_t1_spine_width - _t0_spine_width) / Float64(N)
    print("MOJO_TIMING printing::spine_width", _ns_spine_width, _acc_spine_width)
    var _result_spine_width = spine_width(0.5, 0.5)
    var _summary_spine_width = _summary_float64(_result_spine_width)
    print("MOJO_RESULT printing::spine_width", _summary_spine_width)
    var _acc_ink_coverage: Float64 = 0.0
    var _t0_ink_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_ink_coverage += ink_coverage(0.5, 0.5, 0.5, 0.5)
    var _t1_ink_coverage = perf_counter_ns()
    var _ns_ink_coverage = Float64(_t1_ink_coverage - _t0_ink_coverage) / Float64(N)
    print("MOJO_TIMING printing::ink_coverage", _ns_ink_coverage, _acc_ink_coverage)
    var _result_ink_coverage = ink_coverage(0.5, 0.5, 0.5, 0.5)
    var _summary_ink_coverage = _summary_float64(_result_ink_coverage)
    print("MOJO_RESULT printing::ink_coverage", _summary_ink_coverage)
    var _acc_paper_weight_gsm_to_lb: Float64 = 0.0
    var _t0_paper_weight_gsm_to_lb = perf_counter_ns()
    for _ in range(N):
        _acc_paper_weight_gsm_to_lb += paper_weight_gsm_to_lb(0.5)
    var _t1_paper_weight_gsm_to_lb = perf_counter_ns()
    var _ns_paper_weight_gsm_to_lb = Float64(_t1_paper_weight_gsm_to_lb - _t0_paper_weight_gsm_to_lb) / Float64(N)
    print("MOJO_TIMING printing::paper_weight_gsm_to_lb", _ns_paper_weight_gsm_to_lb, _acc_paper_weight_gsm_to_lb)
    var _result_paper_weight_gsm_to_lb = paper_weight_gsm_to_lb(0.5)
    var _summary_paper_weight_gsm_to_lb = _summary_float64(_result_paper_weight_gsm_to_lb)
    print("MOJO_RESULT printing::paper_weight_gsm_to_lb", _summary_paper_weight_gsm_to_lb)
    var _acc_sheets_per_ream: Float64 = 0.0
    var _t0_sheets_per_ream = perf_counter_ns()
    for _ in range(N):
        _acc_sheets_per_ream += Float64(sheets_per_ream())
    var _t1_sheets_per_ream = perf_counter_ns()
    var _ns_sheets_per_ream = Float64(_t1_sheets_per_ream - _t0_sheets_per_ream) / Float64(N)
    print("MOJO_TIMING printing::sheets_per_ream", _ns_sheets_per_ream, _acc_sheets_per_ream)
    var _result_sheets_per_ream = sheets_per_ream()
    var _summary_sheets_per_ream = _summary_int(_result_sheets_per_ream)
    print("MOJO_RESULT printing::sheets_per_ream", _summary_sheets_per_ream)
    var _acc_cost_per_page: Float64 = 0.0
    var _t0_cost_per_page = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_page += cost_per_page(0.5, 0.5)
    var _t1_cost_per_page = perf_counter_ns()
    var _ns_cost_per_page = Float64(_t1_cost_per_page - _t0_cost_per_page) / Float64(N)
    print("MOJO_TIMING printing::cost_per_page", _ns_cost_per_page, _acc_cost_per_page)
    var _result_cost_per_page = cost_per_page(0.5, 0.5)
    var _summary_cost_per_page = _summary_float64(_result_cost_per_page)
    print("MOJO_RESULT printing::cost_per_page", _summary_cost_per_page)
    var _acc_imposition_pages: Float64 = 0.0
    var _t0_imposition_pages = perf_counter_ns()
    for _ in range(N):
        _acc_imposition_pages += imposition_pages(0.5, 0.5)
    var _t1_imposition_pages = perf_counter_ns()
    var _ns_imposition_pages = Float64(_t1_imposition_pages - _t0_imposition_pages) / Float64(N)
    print("MOJO_TIMING printing::imposition_pages", _ns_imposition_pages, _acc_imposition_pages)
    var _result_imposition_pages = imposition_pages(0.5, 0.5)
    var _summary_imposition_pages = _summary_float64(_result_imposition_pages)
    print("MOJO_RESULT printing::imposition_pages", _summary_imposition_pages)
    var _acc_color_delta_e: Float64 = 0.0
    var _t0_color_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_color_delta_e += color_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_color_delta_e = perf_counter_ns()
    var _ns_color_delta_e = Float64(_t1_color_delta_e - _t0_color_delta_e) / Float64(N)
    print("MOJO_TIMING printing::color_delta_e", _ns_color_delta_e, _acc_color_delta_e)
    var _result_color_delta_e = color_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_color_delta_e = _summary_float64(_result_color_delta_e)
    print("MOJO_RESULT printing::color_delta_e", _summary_color_delta_e)
    var _acc_dot_gain_apparent: Float64 = 0.0
    var _t0_dot_gain_apparent = perf_counter_ns()
    for _ in range(N):
        _acc_dot_gain_apparent += dot_gain_apparent(0.5, 0.5)
    var _t1_dot_gain_apparent = perf_counter_ns()
    var _ns_dot_gain_apparent = Float64(_t1_dot_gain_apparent - _t0_dot_gain_apparent) / Float64(N)
    print("MOJO_TIMING printing::dot_gain_apparent", _ns_dot_gain_apparent, _acc_dot_gain_apparent)
    var _result_dot_gain_apparent = dot_gain_apparent(0.5, 0.5)
    var _summary_dot_gain_apparent = _summary_float64(_result_dot_gain_apparent)
    print("MOJO_RESULT printing::dot_gain_apparent", _summary_dot_gain_apparent)
