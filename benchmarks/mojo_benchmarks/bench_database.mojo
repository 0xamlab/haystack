"""bench_database.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from database import table_create, Table
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

    var _keeper_table_create = List[Table]()
    _keeper_table_create.append(table_create(["a","b","c","d","e"], 5))
    var _acc_table_create: Float64 = 0.0
    var _t0_table_create = perf_counter_ns()
    for _ in range(N):
        _keeper_table_create[0] = table_create(["a","b","c","d","e"], 5)
        _acc_table_create += Float64(len(_keeper_table_create))
    var _t1_table_create = perf_counter_ns()
    var _ns_table_create = Float64(_t1_table_create - _t0_table_create) / Float64(N)
    print("MOJO_TIMING database::table_create", _ns_table_create, _acc_table_create)
