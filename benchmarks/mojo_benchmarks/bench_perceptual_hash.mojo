"""bench_perceptual_hash.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from perceptual_hash import ahash, dhash, phash, hamming_distance, is_duplicate, ahash_flat, dhash_flat, phash_flat
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

def _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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

    var _acc_ahash: Float64 = 0.0
    var _t0_ahash = perf_counter_ns()
    for _ in range(N):
        _acc_ahash += Float64(ahash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_ahash = perf_counter_ns()
    var _ns_ahash = Float64(_t1_ahash - _t0_ahash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::ahash", _ns_ahash, _acc_ahash)
    var _result_ahash = ahash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_ahash = _summary_uint64(_result_ahash)
    print("MOJO_RESULT perceptual_hash::ahash", _summary_ahash)
    var _acc_dhash: Float64 = 0.0
    var _t0_dhash = perf_counter_ns()
    for _ in range(N):
        _acc_dhash += Float64(dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_dhash = perf_counter_ns()
    var _ns_dhash = Float64(_t1_dhash - _t0_dhash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::dhash", _ns_dhash, _acc_dhash)
    var _result_dhash = dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_dhash = _summary_uint64(_result_dhash)
    print("MOJO_RESULT perceptual_hash::dhash", _summary_dhash)
    var _acc_phash: Float64 = 0.0
    var _t0_phash = perf_counter_ns()
    for _ in range(N):
        _acc_phash += Float64(phash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_phash = perf_counter_ns()
    var _ns_phash = Float64(_t1_phash - _t0_phash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::phash", _ns_phash, _acc_phash)
    var _result_phash = phash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_phash = _summary_uint64(_result_phash)
    print("MOJO_RESULT perceptual_hash::phash", _summary_phash)
    var _acc_hamming_distance: Float64 = 0.0
    var _t0_hamming_distance = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance += Float64(hamming_distance(UInt64(1), UInt64(1)))
    var _t1_hamming_distance = perf_counter_ns()
    var _ns_hamming_distance = Float64(_t1_hamming_distance - _t0_hamming_distance) / Float64(N)
    print("MOJO_TIMING perceptual_hash::hamming_distance", _ns_hamming_distance, _acc_hamming_distance)
    var _result_hamming_distance = hamming_distance(UInt64(1), UInt64(1))
    var _summary_hamming_distance = _summary_int(_result_hamming_distance)
    print("MOJO_RESULT perceptual_hash::hamming_distance", _summary_hamming_distance)
    var _acc_is_duplicate: Float64 = 0.0
    var _t0_is_duplicate = perf_counter_ns()
    for _ in range(N):
        _acc_is_duplicate += Float64(is_duplicate(UInt64(1), UInt64(1), 5))
    var _t1_is_duplicate = perf_counter_ns()
    var _ns_is_duplicate = Float64(_t1_is_duplicate - _t0_is_duplicate) / Float64(N)
    print("MOJO_TIMING perceptual_hash::is_duplicate", _ns_is_duplicate, _acc_is_duplicate)
    var _result_is_duplicate = is_duplicate(UInt64(1), UInt64(1), 5)
    var _summary_is_duplicate = _summary_bool(_result_is_duplicate)
    print("MOJO_RESULT perceptual_hash::is_duplicate", _summary_is_duplicate)
    var _acc_ahash_flat: Float64 = 0.0
    var _t0_ahash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_ahash_flat += Float64(ahash_flat(_lf5, 5, 5))
    var _t1_ahash_flat = perf_counter_ns()
    var _ns_ahash_flat = Float64(_t1_ahash_flat - _t0_ahash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::ahash_flat", _ns_ahash_flat, _acc_ahash_flat)
    var _result_ahash_flat = ahash_flat(_lf5, 5, 5)
    var _summary_ahash_flat = _summary_uint64(_result_ahash_flat)
    print("MOJO_RESULT perceptual_hash::ahash_flat", _summary_ahash_flat)
    var _acc_dhash_flat: Float64 = 0.0
    var _t0_dhash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_dhash_flat += Float64(dhash_flat(_lf5, 5, 5))
    var _t1_dhash_flat = perf_counter_ns()
    var _ns_dhash_flat = Float64(_t1_dhash_flat - _t0_dhash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::dhash_flat", _ns_dhash_flat, _acc_dhash_flat)
    var _result_dhash_flat = dhash_flat(_lf5, 5, 5)
    var _summary_dhash_flat = _summary_uint64(_result_dhash_flat)
    print("MOJO_RESULT perceptual_hash::dhash_flat", _summary_dhash_flat)
    var _acc_phash_flat: Float64 = 0.0
    var _t0_phash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_phash_flat += Float64(phash_flat(_lf5, 5, 5))
    var _t1_phash_flat = perf_counter_ns()
    var _ns_phash_flat = Float64(_t1_phash_flat - _t0_phash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::phash_flat", _ns_phash_flat, _acc_phash_flat)
    var _result_phash_flat = phash_flat(_lf5, 5, 5)
    var _summary_phash_flat = _summary_uint64(_result_phash_flat)
    print("MOJO_RESULT perceptual_hash::phash_flat", _summary_phash_flat)
