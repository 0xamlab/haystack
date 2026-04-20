"""bench_filepath_pathlib.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from filepath.pathlib import path_join, path_basename, path_dirname, path_extension, path_stem, path_is_absolute, path_split, path_normalize
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

    var _acc_path_join: Float64 = 0.0
    var _t0_path_join = perf_counter_ns()
    for _ in range(N):
        _ = path_join(["a","b","c","d","e"])
    var _t1_path_join = perf_counter_ns()
    var _ns_path_join = Float64(_t1_path_join - _t0_path_join) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_join", _ns_path_join, _acc_path_join)
    var _acc_path_basename: Float64 = 0.0
    var _t0_path_basename = perf_counter_ns()
    for _ in range(N):
        _ = path_basename("test")
    var _t1_path_basename = perf_counter_ns()
    var _ns_path_basename = Float64(_t1_path_basename - _t0_path_basename) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_basename", _ns_path_basename, _acc_path_basename)
    var _acc_path_dirname: Float64 = 0.0
    var _t0_path_dirname = perf_counter_ns()
    for _ in range(N):
        _ = path_dirname("test")
    var _t1_path_dirname = perf_counter_ns()
    var _ns_path_dirname = Float64(_t1_path_dirname - _t0_path_dirname) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_dirname", _ns_path_dirname, _acc_path_dirname)
    var _acc_path_extension: Float64 = 0.0
    var _t0_path_extension = perf_counter_ns()
    for _ in range(N):
        _ = path_extension("test")
    var _t1_path_extension = perf_counter_ns()
    var _ns_path_extension = Float64(_t1_path_extension - _t0_path_extension) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_extension", _ns_path_extension, _acc_path_extension)
    var _acc_path_stem: Float64 = 0.0
    var _t0_path_stem = perf_counter_ns()
    for _ in range(N):
        _ = path_stem("test")
    var _t1_path_stem = perf_counter_ns()
    var _ns_path_stem = Float64(_t1_path_stem - _t0_path_stem) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_stem", _ns_path_stem, _acc_path_stem)
    var _acc_path_is_absolute: Float64 = 0.0
    var _t0_path_is_absolute = perf_counter_ns()
    for _ in range(N):
        _acc_path_is_absolute += Float64(path_is_absolute("test"))
    var _t1_path_is_absolute = perf_counter_ns()
    var _ns_path_is_absolute = Float64(_t1_path_is_absolute - _t0_path_is_absolute) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_is_absolute", _ns_path_is_absolute, _acc_path_is_absolute)
    var _acc_path_split: Float64 = 0.0
    var _t0_path_split = perf_counter_ns()
    for _ in range(N):
        var _r_path_split = path_split("test")
        _acc_path_split += Float64(len(_r_path_split))
    var _t1_path_split = perf_counter_ns()
    var _ns_path_split = Float64(_t1_path_split - _t0_path_split) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_split", _ns_path_split, _acc_path_split)
    var _acc_path_normalize: Float64 = 0.0
    var _t0_path_normalize = perf_counter_ns()
    for _ in range(N):
        _ = path_normalize("test")
    var _t1_path_normalize = perf_counter_ns()
    var _ns_path_normalize = Float64(_t1_path_normalize - _t0_path_normalize) / Float64(N)
    print("MOJO_TIMING filepath_pathlib::path_normalize", _ns_path_normalize, _acc_path_normalize)
