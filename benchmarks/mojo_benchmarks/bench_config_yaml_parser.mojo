"""bench_config_yaml_parser.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from config.yaml_parser import yaml_parse, YamlDoc
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

    var _keeper_yaml_parse = List[YamlDoc]()
    _keeper_yaml_parse.append(yaml_parse("test"))
    var _acc_yaml_parse: Float64 = 0.0
    var _t0_yaml_parse = perf_counter_ns()
    for _ in range(N):
        _keeper_yaml_parse[0] = yaml_parse("test")
        _acc_yaml_parse += Float64(len(_keeper_yaml_parse))
    var _t1_yaml_parse = perf_counter_ns()
    var _ns_yaml_parse = Float64(_t1_yaml_parse - _t0_yaml_parse) / Float64(N)
    print("MOJO_TIMING config_yaml_parser::yaml_parse", _ns_yaml_parse, _acc_yaml_parse)
