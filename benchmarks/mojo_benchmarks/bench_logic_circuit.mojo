"""bench_logic_circuit.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from logic_circuit import gate_and, gate_or, gate_not, gate_xor, gate_nand, gate_nor, half_adder, full_adder, ripple_carry_adder, multiplexer_2to1, decoder_2to4, bits_to_int, int_to_bits
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

    var _acc_gate_and: Float64 = 0.0
    var _t0_gate_and = perf_counter_ns()
    for _ in range(N):
        _acc_gate_and += Float64(gate_and(5, 5))
    var _t1_gate_and = perf_counter_ns()
    var _ns_gate_and = Float64(_t1_gate_and - _t0_gate_and) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_and", _ns_gate_and, _acc_gate_and)
    var _result_gate_and = gate_and(5, 5)
    var _summary_gate_and = _summary_int(_result_gate_and)
    print("MOJO_RESULT logic_circuit::gate_and", _summary_gate_and)
    var _acc_gate_or: Float64 = 0.0
    var _t0_gate_or = perf_counter_ns()
    for _ in range(N):
        _acc_gate_or += Float64(gate_or(5, 5))
    var _t1_gate_or = perf_counter_ns()
    var _ns_gate_or = Float64(_t1_gate_or - _t0_gate_or) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_or", _ns_gate_or, _acc_gate_or)
    var _result_gate_or = gate_or(5, 5)
    var _summary_gate_or = _summary_int(_result_gate_or)
    print("MOJO_RESULT logic_circuit::gate_or", _summary_gate_or)
    var _acc_gate_not: Float64 = 0.0
    var _t0_gate_not = perf_counter_ns()
    for _ in range(N):
        _acc_gate_not += Float64(gate_not(5))
    var _t1_gate_not = perf_counter_ns()
    var _ns_gate_not = Float64(_t1_gate_not - _t0_gate_not) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_not", _ns_gate_not, _acc_gate_not)
    var _result_gate_not = gate_not(5)
    var _summary_gate_not = _summary_int(_result_gate_not)
    print("MOJO_RESULT logic_circuit::gate_not", _summary_gate_not)
    var _acc_gate_xor: Float64 = 0.0
    var _t0_gate_xor = perf_counter_ns()
    for _ in range(N):
        _acc_gate_xor += Float64(gate_xor(5, 5))
    var _t1_gate_xor = perf_counter_ns()
    var _ns_gate_xor = Float64(_t1_gate_xor - _t0_gate_xor) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_xor", _ns_gate_xor, _acc_gate_xor)
    var _result_gate_xor = gate_xor(5, 5)
    var _summary_gate_xor = _summary_int(_result_gate_xor)
    print("MOJO_RESULT logic_circuit::gate_xor", _summary_gate_xor)
    var _acc_gate_nand: Float64 = 0.0
    var _t0_gate_nand = perf_counter_ns()
    for _ in range(N):
        _acc_gate_nand += Float64(gate_nand(5, 5))
    var _t1_gate_nand = perf_counter_ns()
    var _ns_gate_nand = Float64(_t1_gate_nand - _t0_gate_nand) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_nand", _ns_gate_nand, _acc_gate_nand)
    var _result_gate_nand = gate_nand(5, 5)
    var _summary_gate_nand = _summary_int(_result_gate_nand)
    print("MOJO_RESULT logic_circuit::gate_nand", _summary_gate_nand)
    var _acc_gate_nor: Float64 = 0.0
    var _t0_gate_nor = perf_counter_ns()
    for _ in range(N):
        _acc_gate_nor += Float64(gate_nor(5, 5))
    var _t1_gate_nor = perf_counter_ns()
    var _ns_gate_nor = Float64(_t1_gate_nor - _t0_gate_nor) / Float64(N)
    print("MOJO_TIMING logic_circuit::gate_nor", _ns_gate_nor, _acc_gate_nor)
    var _result_gate_nor = gate_nor(5, 5)
    var _summary_gate_nor = _summary_int(_result_gate_nor)
    print("MOJO_RESULT logic_circuit::gate_nor", _summary_gate_nor)
    var _acc_half_adder: Float64 = 0.0
    var _t0_half_adder = perf_counter_ns()
    for _ in range(N):
        var _r_half_adder = half_adder(5, 5)
        _acc_half_adder += Float64(len(_r_half_adder))
    var _t1_half_adder = perf_counter_ns()
    var _ns_half_adder = Float64(_t1_half_adder - _t0_half_adder) / Float64(N)
    print("MOJO_TIMING logic_circuit::half_adder", _ns_half_adder, _acc_half_adder)
    var _result_half_adder = half_adder(5, 5)
    var _summary_half_adder = _summary_list_int(_result_half_adder)
    print("MOJO_RESULT logic_circuit::half_adder", _summary_half_adder)
    var _acc_full_adder: Float64 = 0.0
    var _t0_full_adder = perf_counter_ns()
    for _ in range(N):
        var _r_full_adder = full_adder(5, 5, 5)
        _acc_full_adder += Float64(len(_r_full_adder))
    var _t1_full_adder = perf_counter_ns()
    var _ns_full_adder = Float64(_t1_full_adder - _t0_full_adder) / Float64(N)
    print("MOJO_TIMING logic_circuit::full_adder", _ns_full_adder, _acc_full_adder)
    var _result_full_adder = full_adder(5, 5, 5)
    var _summary_full_adder = _summary_list_int(_result_full_adder)
    print("MOJO_RESULT logic_circuit::full_adder", _summary_full_adder)
    var _acc_ripple_carry_adder: Float64 = 0.0
    var _t0_ripple_carry_adder = perf_counter_ns()
    for _ in range(N):
        var _r_ripple_carry_adder = ripple_carry_adder(_li5, _li5)
        _acc_ripple_carry_adder += Float64(len(_r_ripple_carry_adder))
    var _t1_ripple_carry_adder = perf_counter_ns()
    var _ns_ripple_carry_adder = Float64(_t1_ripple_carry_adder - _t0_ripple_carry_adder) / Float64(N)
    print("MOJO_TIMING logic_circuit::ripple_carry_adder", _ns_ripple_carry_adder, _acc_ripple_carry_adder)
    var _result_ripple_carry_adder = ripple_carry_adder(_li5, _li5)
    var _summary_ripple_carry_adder = _summary_list_int(_result_ripple_carry_adder)
    print("MOJO_RESULT logic_circuit::ripple_carry_adder", _summary_ripple_carry_adder)
    var _acc_multiplexer_2to1: Float64 = 0.0
    var _t0_multiplexer_2to1 = perf_counter_ns()
    for _ in range(N):
        _acc_multiplexer_2to1 += Float64(multiplexer_2to1(5, 5, 5))
    var _t1_multiplexer_2to1 = perf_counter_ns()
    var _ns_multiplexer_2to1 = Float64(_t1_multiplexer_2to1 - _t0_multiplexer_2to1) / Float64(N)
    print("MOJO_TIMING logic_circuit::multiplexer_2to1", _ns_multiplexer_2to1, _acc_multiplexer_2to1)
    var _result_multiplexer_2to1 = multiplexer_2to1(5, 5, 5)
    var _summary_multiplexer_2to1 = _summary_int(_result_multiplexer_2to1)
    print("MOJO_RESULT logic_circuit::multiplexer_2to1", _summary_multiplexer_2to1)
    var _acc_decoder_2to4: Float64 = 0.0
    var _t0_decoder_2to4 = perf_counter_ns()
    for _ in range(N):
        var _r_decoder_2to4 = decoder_2to4(5, 5)
        _acc_decoder_2to4 += Float64(len(_r_decoder_2to4))
    var _t1_decoder_2to4 = perf_counter_ns()
    var _ns_decoder_2to4 = Float64(_t1_decoder_2to4 - _t0_decoder_2to4) / Float64(N)
    print("MOJO_TIMING logic_circuit::decoder_2to4", _ns_decoder_2to4, _acc_decoder_2to4)
    var _result_decoder_2to4 = decoder_2to4(5, 5)
    var _summary_decoder_2to4 = _summary_list_int(_result_decoder_2to4)
    print("MOJO_RESULT logic_circuit::decoder_2to4", _summary_decoder_2to4)
    var _acc_bits_to_int: Float64 = 0.0
    var _t0_bits_to_int = perf_counter_ns()
    for _ in range(N):
        _acc_bits_to_int += Float64(bits_to_int(_li5))
    var _t1_bits_to_int = perf_counter_ns()
    var _ns_bits_to_int = Float64(_t1_bits_to_int - _t0_bits_to_int) / Float64(N)
    print("MOJO_TIMING logic_circuit::bits_to_int", _ns_bits_to_int, _acc_bits_to_int)
    var _result_bits_to_int = bits_to_int(_li5)
    var _summary_bits_to_int = _summary_int(_result_bits_to_int)
    print("MOJO_RESULT logic_circuit::bits_to_int", _summary_bits_to_int)
    var _acc_int_to_bits: Float64 = 0.0
    var _t0_int_to_bits = perf_counter_ns()
    for _ in range(N):
        var _r_int_to_bits = int_to_bits(5, 5)
        _acc_int_to_bits += Float64(len(_r_int_to_bits))
    var _t1_int_to_bits = perf_counter_ns()
    var _ns_int_to_bits = Float64(_t1_int_to_bits - _t0_int_to_bits) / Float64(N)
    print("MOJO_TIMING logic_circuit::int_to_bits", _ns_int_to_bits, _acc_int_to_bits)
    var _result_int_to_bits = int_to_bits(5, 5)
    var _summary_int_to_bits = _summary_list_int(_result_int_to_bits)
    print("MOJO_RESULT logic_circuit::int_to_bits", _summary_int_to_bits)
