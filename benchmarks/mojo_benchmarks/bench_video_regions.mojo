"""bench_video_regions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from video_regions import frame_diff_mask_flat, motion_boxes_between_frames, largest_motion_box_between_frames, temporal_motion_area_series, peak_motion_box_flat, temporal_union_motion_box_flat, motion_coverage_ratio_flat
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

fn _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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
    var _lf12_colorcheck2x2 = List[Float64]()
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)
    var _lf48_video3x4x4 = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4.append(10.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4.append(200.0)
        else:
            _lf48_video3x4x4.append(10.0)
    for _ in range(16):
        _lf48_video3x4x4.append(200.0)
    var _lf48_video3x4x4_alt = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4_alt.append(12.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4_alt.append(188.0)
        else:
            _lf48_video3x4x4_alt.append(12.0)
    for _ in range(16):
        _lf48_video3x4x4_alt.append(192.0)
    var _lf25_block5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                _lf25_block5x5.append(255.0)
            else:
                _lf25_block5x5.append(0.0)
    var _lf25_ring5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                _lf25_ring5x5.append(255.0)
            else:
                _lf25_ring5x5.append(0.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _lf64_doc8x8 = List[Float64]()
    var _lf64_doc8x8_alt = List[Float64]()
    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8.append(20.0)
                _lf64_doc8x8_alt.append(60.0)
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_doc8x8.append(240.0)
                _lf64_doc8x8_alt.append(235.0)
                _lf64_docmask8x8.append(0.0)
    var _lf36_adaptive_doc6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                _lf36_adaptive_doc6x6.append(40.0)
            elif x < 3:
                _lf36_adaptive_doc6x6.append(220.0)
            else:
                _lf36_adaptive_doc6x6.append(245.0)
    var _lf36_skewmask6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                _lf36_skewmask6x6.append(255.0)
            else:
                _lf36_skewmask6x6.append(0.0)
    var _lf64_blobdoc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):
                _lf64_blobdoc8x8.append(20.0)
            else:
                _lf64_blobdoc8x8.append(235.0)
    var _lf64_doccolumns8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                _lf64_doccolumns8x8.append(255.0)
            else:
                _lf64_doccolumns8x8.append(0.0)
    var _lf81_doctable9x9 = List[Float64]()
    for y in range(9):
        for x in range(9):
            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):
                _lf81_doctable9x9.append(255.0)
            else:
                _lf81_doctable9x9.append(0.0)
    var _lf256_texture16x16 = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                _lf256_texture16x16.append(64.0)
    var _lf75_video_motion3x5x5 = List[Float64]()
    for _ in range(25):
        _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 2 and x >= 1 and x <= 2:
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    var _lf16_grid4x4 = List[Float64]()
    for i in range(16):
        _lf16_grid4x4.append(Float64(i))
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _li4_box_a = List[Int]()
    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)
    var _li4_box_b = List[Int]()
    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)
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
    var _llf3_imageops = List[List[Float64]]()
    _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]())
    _llf3_imageops[0].append(0.5); _llf3_imageops[0].append(0.6); _llf3_imageops[0].append(0.7)
    _llf3_imageops[1].append(0.4); _llf3_imageops[1].append(0.3); _llf3_imageops[1].append(0.2)
    _llf3_imageops[2].append(0.1); _llf3_imageops[2].append(0.2); _llf3_imageops[2].append(0.3)
    var N: Int = 5000

    var _acc_frame_diff_mask_flat: Float64 = 0.0
    var _t0_frame_diff_mask_flat = perf_counter_ns()
    for _ in range(N):
        var _r_frame_diff_mask_flat = frame_diff_mask_flat(_lf75_video_motion3x5x5, 5, 5, 1, 0, 1, 50.0)
        _acc_frame_diff_mask_flat += Float64(len(_r_frame_diff_mask_flat))
    var _t1_frame_diff_mask_flat = perf_counter_ns()
    var _ns_frame_diff_mask_flat = Float64(_t1_frame_diff_mask_flat - _t0_frame_diff_mask_flat) / Float64(N)
    print("MOJO_TIMING video_regions::frame_diff_mask_flat", _ns_frame_diff_mask_flat, _acc_frame_diff_mask_flat)
    var _result_frame_diff_mask_flat = frame_diff_mask_flat(_lf75_video_motion3x5x5, 5, 5, 1, 0, 1, 50.0)
    var _summary_frame_diff_mask_flat = _summary_list_float64(_result_frame_diff_mask_flat)
    print("MOJO_RESULT video_regions::frame_diff_mask_flat", _summary_frame_diff_mask_flat)
    var _acc_motion_boxes_between_frames: Float64 = 0.0
    var _t0_motion_boxes_between_frames = perf_counter_ns()
    for _ in range(N):
        var _r_motion_boxes_between_frames = motion_boxes_between_frames(_lf75_video_motion3x5x5, 5, 5, 1, 0, 1, 50.0, 4)
        _acc_motion_boxes_between_frames += Float64(len(_r_motion_boxes_between_frames))
    var _t1_motion_boxes_between_frames = perf_counter_ns()
    var _ns_motion_boxes_between_frames = Float64(_t1_motion_boxes_between_frames - _t0_motion_boxes_between_frames) / Float64(N)
    print("MOJO_TIMING video_regions::motion_boxes_between_frames", _ns_motion_boxes_between_frames, _acc_motion_boxes_between_frames)
    var _result_motion_boxes_between_frames = motion_boxes_between_frames(_lf75_video_motion3x5x5, 5, 5, 1, 0, 1, 50.0, 4)
    var _summary_motion_boxes_between_frames = _summary_list_int(_result_motion_boxes_between_frames)
    print("MOJO_RESULT video_regions::motion_boxes_between_frames", _summary_motion_boxes_between_frames)
    var _acc_largest_motion_box_between_frames: Float64 = 0.0
    var _t0_largest_motion_box_between_frames = perf_counter_ns()
    for _ in range(N):
        var _r_largest_motion_box_between_frames = largest_motion_box_between_frames(_lf75_video_motion3x5x5, 5, 5, 1, 1, 2, 50.0)
        _acc_largest_motion_box_between_frames += Float64(len(_r_largest_motion_box_between_frames))
    var _t1_largest_motion_box_between_frames = perf_counter_ns()
    var _ns_largest_motion_box_between_frames = Float64(_t1_largest_motion_box_between_frames - _t0_largest_motion_box_between_frames) / Float64(N)
    print("MOJO_TIMING video_regions::largest_motion_box_between_frames", _ns_largest_motion_box_between_frames, _acc_largest_motion_box_between_frames)
    var _result_largest_motion_box_between_frames = largest_motion_box_between_frames(_lf75_video_motion3x5x5, 5, 5, 1, 1, 2, 50.0)
    var _summary_largest_motion_box_between_frames = _summary_list_int(_result_largest_motion_box_between_frames)
    print("MOJO_RESULT video_regions::largest_motion_box_between_frames", _summary_largest_motion_box_between_frames)
    var _acc_temporal_motion_area_series: Float64 = 0.0
    var _t0_temporal_motion_area_series = perf_counter_ns()
    for _ in range(N):
        var _r_temporal_motion_area_series = temporal_motion_area_series(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
        _acc_temporal_motion_area_series += Float64(len(_r_temporal_motion_area_series))
    var _t1_temporal_motion_area_series = perf_counter_ns()
    var _ns_temporal_motion_area_series = Float64(_t1_temporal_motion_area_series - _t0_temporal_motion_area_series) / Float64(N)
    print("MOJO_TIMING video_regions::temporal_motion_area_series", _ns_temporal_motion_area_series, _acc_temporal_motion_area_series)
    var _result_temporal_motion_area_series = temporal_motion_area_series(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
    var _summary_temporal_motion_area_series = _summary_list_float64(_result_temporal_motion_area_series)
    print("MOJO_RESULT video_regions::temporal_motion_area_series", _summary_temporal_motion_area_series)
    var _acc_peak_motion_box_flat: Float64 = 0.0
    var _t0_peak_motion_box_flat = perf_counter_ns()
    for _ in range(N):
        var _r_peak_motion_box_flat = peak_motion_box_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
        _acc_peak_motion_box_flat += Float64(len(_r_peak_motion_box_flat))
    var _t1_peak_motion_box_flat = perf_counter_ns()
    var _ns_peak_motion_box_flat = Float64(_t1_peak_motion_box_flat - _t0_peak_motion_box_flat) / Float64(N)
    print("MOJO_TIMING video_regions::peak_motion_box_flat", _ns_peak_motion_box_flat, _acc_peak_motion_box_flat)
    var _result_peak_motion_box_flat = peak_motion_box_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
    var _summary_peak_motion_box_flat = _summary_list_int(_result_peak_motion_box_flat)
    print("MOJO_RESULT video_regions::peak_motion_box_flat", _summary_peak_motion_box_flat)
    var _acc_temporal_union_motion_box_flat: Float64 = 0.0
    var _t0_temporal_union_motion_box_flat = perf_counter_ns()
    for _ in range(N):
        var _r_temporal_union_motion_box_flat = temporal_union_motion_box_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
        _acc_temporal_union_motion_box_flat += Float64(len(_r_temporal_union_motion_box_flat))
    var _t1_temporal_union_motion_box_flat = perf_counter_ns()
    var _ns_temporal_union_motion_box_flat = Float64(_t1_temporal_union_motion_box_flat - _t0_temporal_union_motion_box_flat) / Float64(N)
    print("MOJO_TIMING video_regions::temporal_union_motion_box_flat", _ns_temporal_union_motion_box_flat, _acc_temporal_union_motion_box_flat)
    var _result_temporal_union_motion_box_flat = temporal_union_motion_box_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
    var _summary_temporal_union_motion_box_flat = _summary_list_int(_result_temporal_union_motion_box_flat)
    print("MOJO_RESULT video_regions::temporal_union_motion_box_flat", _summary_temporal_union_motion_box_flat)
    var _acc_motion_coverage_ratio_flat: Float64 = 0.0
    var _t0_motion_coverage_ratio_flat = perf_counter_ns()
    for _ in range(N):
        _acc_motion_coverage_ratio_flat += motion_coverage_ratio_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
    var _t1_motion_coverage_ratio_flat = perf_counter_ns()
    var _ns_motion_coverage_ratio_flat = Float64(_t1_motion_coverage_ratio_flat - _t0_motion_coverage_ratio_flat) / Float64(N)
    print("MOJO_TIMING video_regions::motion_coverage_ratio_flat", _ns_motion_coverage_ratio_flat, _acc_motion_coverage_ratio_flat)
    var _result_motion_coverage_ratio_flat = motion_coverage_ratio_flat(_lf75_video_motion3x5x5, 5, 5, 1, 50.0)
    var _summary_motion_coverage_ratio_flat = _summary_float64(_result_motion_coverage_ratio_flat)
    print("MOJO_RESULT video_regions::motion_coverage_ratio_flat", _summary_motion_coverage_ratio_flat)
