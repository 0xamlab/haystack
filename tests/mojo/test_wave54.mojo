"""Tests for Wave 54 — Logic Circuits, Population Dynamics, Hash Chains."""

from logic_circuit import (
    gate_and,
    gate_or,
    gate_not,
    gate_xor,
    gate_nand,
    gate_nor,
    half_adder,
    full_adder,
    ripple_carry_adder,
    multiplexer_2to1,
    decoder_2to4,
    bits_to_int,
    int_to_bits,
)
from population import (
    logistic_growth,
    logistic_simulate,
    lotka_volterra_step,
    lotka_volterra_simulate,
    exponential_growth,
    carrying_capacity_estimate,
    growth_rate_estimate,
    competition_model,
    population_doubling_time,
    extinction_risk,
)
from crypto.hash_chain import (
    simple_hash,
    hash_chain_build,
    hash_chain_verify,
    merkle_root,
    merkle_proof,
    merkle_verify,
    combine_hashes,
    int_to_bytes,
    hash_single,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Logic Circuit Tests ──────────────────────────────────────────────────────


fn test_basic_gates() raises:
    print("  basic gates...")
    _assert(gate_and(1, 1) == 1, "AND(1,1)==1")                              # 1
    _assert(gate_and(1, 0) == 0, "AND(1,0)==0")                              # 2
    _assert(gate_and(0, 1) == 0, "AND(0,1)==0")                              # 3
    _assert(gate_and(0, 0) == 0, "AND(0,0)==0")                              # 4
    _assert(gate_or(0, 0) == 0, "OR(0,0)==0")                                # 5
    _assert(gate_or(0, 1) == 1, "OR(0,1)==1")                                # 6
    _assert(gate_or(1, 0) == 1, "OR(1,0)==1")                                # 7
    _assert(gate_or(1, 1) == 1, "OR(1,1)==1")                                # 8
    _assert(gate_not(0) == 1, "NOT(0)==1")                                    # 9
    _assert(gate_not(1) == 0, "NOT(1)==0")                                    # 10
    _assert(gate_xor(1, 1) == 0, "XOR(1,1)==0")                              # 11
    _assert(gate_xor(1, 0) == 1, "XOR(1,0)==1")                              # 12
    _assert(gate_xor(0, 1) == 1, "XOR(0,1)==1")                              # 13
    _assert(gate_xor(0, 0) == 0, "XOR(0,0)==0")                              # 14


fn test_compound_gates() raises:
    print("  compound gates...")
    _assert(gate_nand(1, 1) == 0, "NAND(1,1)==0")                            # 15
    _assert(gate_nand(1, 0) == 1, "NAND(1,0)==1")                            # 16
    _assert(gate_nand(0, 0) == 1, "NAND(0,0)==1")                            # 17
    _assert(gate_nor(0, 0) == 1, "NOR(0,0)==1")                              # 18
    _assert(gate_nor(1, 0) == 0, "NOR(1,0)==0")                              # 19
    _assert(gate_nor(0, 1) == 0, "NOR(0,1)==0")                              # 20


fn test_half_adder() raises:
    print("  half_adder...")
    var ha = half_adder(1, 1)
    _assert(ha[0] == 0, "HA(1,1) sum=0")                                     # 21
    _assert(ha[1] == 1, "HA(1,1) carry=1")                                   # 22
    var ha2 = half_adder(1, 0)
    _assert(ha2[0] == 1, "HA(1,0) sum=1")                                    # 23
    _assert(ha2[1] == 0, "HA(1,0) carry=0")                                  # 24


fn test_full_adder() raises:
    print("  full_adder...")
    var fa = full_adder(1, 1, 1)
    _assert(fa[0] == 1, "FA(1,1,1) sum=1")                                   # 25
    _assert(fa[1] == 1, "FA(1,1,1) carry=1")                                 # 26
    var fa2 = full_adder(1, 0, 0)
    _assert(fa2[0] == 1, "FA(1,0,0) sum=1")                                  # 27
    _assert(fa2[1] == 0, "FA(1,0,0) carry=0")                                # 28


fn test_ripple_carry_adder() raises:
    print("  ripple_carry_adder...")
    # 2 (10) + 2 (10) = 4 (100). LSB first: [0,1] + [0,1] = [0,0,1]
    var a = List[Int]()
    a.append(0)
    a.append(1)
    var b = List[Int]()
    b.append(0)
    b.append(1)
    var result = ripple_carry_adder(a, b)
    _assert(len(result) == 3, "RCA 2-bit + carry = 3 bits")                  # 29
    _assert(result[0] == 0, "RCA bit0=0")                                    # 30
    _assert(result[1] == 0, "RCA bit1=0")                                    # 31
    _assert(result[2] == 1, "RCA carry=1")                                   # 32
    # Verify: bits [0,0,1] = 4
    var sum_bits = List[Int]()
    sum_bits.append(result[0])
    sum_bits.append(result[1])
    sum_bits.append(result[2])
    _assert(bits_to_int(sum_bits) == 4, "2+2=4 via RCA")                     # 33


fn test_bit_conversion() raises:
    print("  bits_to_int / int_to_bits...")
    var bits = List[Int]()
    bits.append(1)
    bits.append(0)
    bits.append(1)
    _assert(bits_to_int(bits) == 5, "bits [1,0,1] LSB = 5")                  # 34
    var conv = int_to_bits(5, 3)
    _assert(conv[0] == 1, "5 bit0=1")                                        # 35
    _assert(conv[1] == 0, "5 bit1=0")                                        # 36
    _assert(conv[2] == 1, "5 bit2=1")                                        # 37
    # Round-trip
    _assert(bits_to_int(int_to_bits(13, 4)) == 13, "round-trip 13")          # 38


fn test_mux_decoder() raises:
    print("  multiplexer / decoder...")
    _assert(multiplexer_2to1(0, 1, 1) == 1, "MUX sel=1 → b=1")              # 39
    _assert(multiplexer_2to1(0, 1, 0) == 0, "MUX sel=0 → a=0")              # 40
    _assert(multiplexer_2to1(1, 0, 0) == 1, "MUX sel=0 → a=1")              # 41
    _assert(multiplexer_2to1(1, 0, 1) == 0, "MUX sel=1 → b=0")              # 42
    # decoder_2to4(a=1, b=0) → output 1 active → [0,1,0,0]
    var d = decoder_2to4(1, 0)
    _assert(d[0] == 0, "dec out0=0")                                         # 43
    _assert(d[1] == 1, "dec out1=1")                                         # 44
    _assert(d[2] == 0, "dec out2=0")                                         # 45
    _assert(d[3] == 0, "dec out3=0")                                         # 46


# ── Population Tests ─────────────────────────────────────────────────────────


fn test_exponential_growth() raises:
    print("  exponential_growth...")
    var result = exponential_growth(100.0, 0.1, 10.0)
    _assert_close(result, 271.828, 0.2, "100*e^1 ≈ 271.8")                   # 47


fn test_logistic_growth() raises:
    print("  logistic_growth / simulate...")
    var next_N = logistic_growth(50.0, 0.1, 100.0)
    _assert(next_N > 50.0 and next_N < 100.0, "logistic between N and K")    # 48
    var sim = logistic_simulate(10.0, 0.5, 100.0, 50)
    _assert(len(sim) == 51, "simulate returns n_steps+1 entries")             # 49
    var final_val = sim[len(sim) - 1]
    _assert(final_val > 90.0 and final_val < 110.0, "converges near K")      # 50


fn test_lotka_volterra() raises:
    print("  lotka_volterra_step / simulate...")
    # alpha=1.1, beta=0.4, delta=0.1, gamma=0.4
    var step = lotka_volterra_step(40.0, 9.0, 1.1, 0.4, 0.1, 0.4, 0.01)
    _assert(step[0] > 0.0, "prey stays positive")                            # 51
    _assert(step[1] > 0.0, "pred stays positive")                            # 52
    var sim = lotka_volterra_simulate(
        40.0, 9.0, 1.1, 0.4, 0.1, 0.4, 0.01, 10
    )
    _assert(len(sim) == 11, "LV simulate returns n_steps+1 rows")            # 53


fn test_population_utils() raises:
    print("  doubling_time / extinction_risk / competition...")
    _assert_close(
        population_doubling_time(0.693147), 1.0, 0.01, "ln2/0.693≈1"
    )                                                                         # 54
    _assert(extinction_risk(5.0, 10.0) == True, "5<10 → extinct risk")       # 55
    _assert(extinction_risk(15.0, 10.0) == False, "15>10 → safe")            # 56
    var comp = competition_model(
        50.0, 30.0, 0.1, 0.1, 100.0, 80.0, 0.5, 0.3
    )
    _assert(comp[0] > 0.0, "competition N1 > 0")                             # 57
    _assert(comp[1] > 0.0, "competition N2 > 0")                             # 58


fn test_carrying_capacity_estimate() raises:
    print("  carrying_capacity_estimate / growth_rate_estimate...")
    var pops = List[Float64]()
    pops.append(10.0)
    pops.append(50.0)
    pops.append(90.0)
    pops.append(80.0)
    var K_est = carrying_capacity_estimate(pops)
    _assert_close(K_est, 99.0, 0.1, "K est = max*1.1 = 99")                 # 59
    var r_est = growth_rate_estimate(50.0, 55.0, 100.0)
    _assert(r_est > 0.0, "growth rate positive when N increasing")           # 60


# ── Hash Chain Tests ─────────────────────────────────────────────────────────


fn test_simple_hash() raises:
    print("  simple_hash / hash_single...")
    var data1 = List[Int]()
    data1.append(1)
    data1.append(2)
    data1.append(3)
    var h1 = simple_hash(data1)
    var data2 = List[Int]()
    data2.append(1)
    data2.append(2)
    data2.append(3)
    var h2 = simple_hash(data2)
    _assert(h1 == h2, "hash deterministic")                                   # 61
    var data3 = List[Int]()
    data3.append(3)
    data3.append(2)
    data3.append(1)
    var h3 = simple_hash(data3)
    _assert(h1 != h3, "different data → different hash (usually)")            # 62
    var hs1 = hash_single(42)
    var hs2 = hash_single(42)
    _assert(hs1 == hs2, "hash_single deterministic")                          # 63
    _assert(hash_single(0) != hash_single(1), "diff ints diff hashes")        # 64


fn test_int_to_bytes() raises:
    print("  int_to_bytes...")
    var b = int_to_bytes(256)
    _assert(len(b) == 4, "4 bytes")                                           # 65
    _assert(b[0] == 0, "byte0 = 0")                                          # 66
    _assert(b[1] == 0, "byte1 = 0")                                          # 67
    _assert(b[2] == 1, "byte2 = 1")                                          # 68
    _assert(b[3] == 0, "byte3 = 0")                                          # 69


fn test_combine_hashes() raises:
    print("  combine_hashes...")
    var ca = combine_hashes(100, 200)
    var cb = combine_hashes(200, 100)
    _assert(ca != cb, "combine(a,b) != combine(b,a)")                         # 70
    var cc = combine_hashes(100, 200)
    _assert(ca == cc, "combine deterministic")                                # 71


fn test_hash_chain() raises:
    print("  hash_chain_build / verify...")
    var items = List[List[Int]]()
    var i1 = List[Int]()
    i1.append(1)
    i1.append(2)
    items.append(i1^)
    var i2 = List[Int]()
    i2.append(3)
    i2.append(4)
    items.append(i2^)
    var i3 = List[Int]()
    i3.append(5)
    i3.append(6)
    items.append(i3^)
    var chain = hash_chain_build(items)
    _assert(len(chain) == 3, "chain has 3 hashes")                            # 72
    _assert(hash_chain_verify(items, chain), "valid chain verifies")          # 73
    # Tamper with chain
    var bad_chain = List[Int]()
    bad_chain.append(chain[0])
    bad_chain.append(99999)
    bad_chain.append(chain[2])
    _assert(
        not hash_chain_verify(items, bad_chain), "tampered chain fails"
    )                                                                          # 74


fn test_merkle_tree() raises:
    print("  merkle_root / proof / verify...")
    var leaves = List[Int]()
    leaves.append(hash_single(1))
    leaves.append(hash_single(2))
    leaves.append(hash_single(3))
    leaves.append(hash_single(4))
    var root = merkle_root(leaves)
    # Deterministic
    var root2 = merkle_root(leaves)
    _assert(root == root2, "merkle root deterministic")                        # 75

    # Proof for leaf 0
    var proof0 = merkle_proof(leaves, 0)
    _assert(len(proof0) == 2, "proof depth=2 for 4 leaves")                   # 76
    _assert(
        merkle_verify(leaves[0], proof0, 0, root),
        "merkle verify leaf 0 valid",
    )                                                                          # 77

    # Proof for leaf 2
    var proof2 = merkle_proof(leaves, 2)
    _assert(
        merkle_verify(leaves[2], proof2, 2, root),
        "merkle verify leaf 2 valid",
    )                                                                          # 78

    # Wrong leaf should fail
    _assert(
        not merkle_verify(hash_single(99), proof0, 0, root),
        "wrong leaf fails merkle verify",
    )                                                                          # 79

    # Odd number of leaves
    var leaves3 = List[Int]()
    leaves3.append(hash_single(10))
    leaves3.append(hash_single(20))
    leaves3.append(hash_single(30))
    var root3 = merkle_root(leaves3)
    _assert(root3 != 0, "odd-leaf merkle root non-zero")                       # 80
    var proof3_1 = merkle_proof(leaves3, 1)
    _assert(
        merkle_verify(leaves3[1], proof3_1, 1, root3),
        "merkle verify odd leaves",
    )                                                                          # 81


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 54 Tests ===")

    # Logic Circuits
    print("Logic Circuits:")
    test_basic_gates()
    test_compound_gates()
    test_half_adder()
    test_full_adder()
    test_ripple_carry_adder()
    test_bit_conversion()
    test_mux_decoder()

    # Population Dynamics
    print("Population Dynamics:")
    test_exponential_growth()
    test_logistic_growth()
    test_lotka_volterra()
    test_population_utils()
    test_carrying_capacity_estimate()

    # Hash Chains & Merkle Trees
    print("Hash Chains & Merkle Trees:")
    test_simple_hash()
    test_int_to_bytes()
    test_combine_hashes()
    test_hash_chain()
    test_merkle_tree()

    print("All 81 assertions passed! ✓")
