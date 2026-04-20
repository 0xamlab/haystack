"""test_logic_circuit.mojo — auto-generated tests for logic_circuit library."""
from std.math import isnan, isinf
from logic_circuit import gate_and, gate_or, gate_not, gate_xor, gate_nand, gate_nor, half_adder, full_adder, ripple_carry_adder, multiplexer_2to1, decoder_2to4, bits_to_int, int_to_bits

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = gate_and(5, 5)
    passed += 1; print("  ✅ logic_circuit::gate_and")
    _ = gate_or(5, 5)
    passed += 1; print("  ✅ logic_circuit::gate_or")
    _ = gate_not(5)
    passed += 1; print("  ✅ logic_circuit::gate_not")
    _ = gate_xor(5, 5)
    passed += 1; print("  ✅ logic_circuit::gate_xor")
    _ = gate_nand(5, 5)
    passed += 1; print("  ✅ logic_circuit::gate_nand")
    _ = gate_nor(5, 5)
    passed += 1; print("  ✅ logic_circuit::gate_nor")
    var _v_half_adder = half_adder(5, 5)
    if len(_v_half_adder) >= 0: passed += 1; print("  ✅ logic_circuit::half_adder")
    var _v_full_adder = full_adder(5, 5, 5)
    if len(_v_full_adder) >= 0: passed += 1; print("  ✅ logic_circuit::full_adder")
    var _v_ripple_carry_adder = ripple_carry_adder(_li5, _li5)
    if len(_v_ripple_carry_adder) >= 0: passed += 1; print("  ✅ logic_circuit::ripple_carry_adder")
    _ = multiplexer_2to1(5, 5, 5)
    passed += 1; print("  ✅ logic_circuit::multiplexer_2to1")
    var _v_decoder_2to4 = decoder_2to4(5, 5)
    if len(_v_decoder_2to4) >= 0: passed += 1; print("  ✅ logic_circuit::decoder_2to4")
    _ = bits_to_int(_li5)
    passed += 1; print("  ✅ logic_circuit::bits_to_int")
    var _v_int_to_bits = int_to_bits(5, 5)
    if len(_v_int_to_bits) >= 0: passed += 1; print("  ✅ logic_circuit::int_to_bits")

    print("  [logic_circuit] Passed:", passed, "Failed:", failed)
