"""
logic_circuit.mojo — Digital logic circuit primitives. Zero Python imports.

Replaces logisim/custom digital logic tooling.

Public API:
  def gate_and(a, b)           — AND gate
  def gate_or(a, b)            — OR gate
  def gate_not(a)              — NOT gate
  def gate_xor(a, b)           — XOR gate
  def gate_nand(a, b)          — NAND gate
  def gate_nor(a, b)           — NOR gate
  def half_adder(a, b)         — Returns [sum, carry]
  def full_adder(a, b, cin)    — Returns [sum, carry_out]
  def ripple_carry_adder(a, b) — N-bit adder, LSB first
  def multiplexer_2to1(a, b, sel) — 2:1 MUX
  def decoder_2to4(a, b)       — 2-to-4 decoder
  def bits_to_int(bits)        — Bit list (LSB first) → integer
  def int_to_bits(value, n)    — Integer → bit list (LSB first)
"""


# Ceiling on the wire-supplied bit width: bounds the allocation.
comptime MAX_BIT_WIDTH: Int = 1024


# ── Basic Gates ───────────────────────────────────────────────────────────────


def gate_and(a: Int, b: Int) -> Int:
    """AND gate: returns 1 iff both inputs are 1."""
    if a == 1 and b == 1:
        return 1
    return 0


def gate_or(a: Int, b: Int) -> Int:
    """OR gate: returns 1 if at least one input is 1."""
    if a == 1 or b == 1:
        return 1
    return 0


def gate_not(a: Int) -> Int:
    """NOT gate: inverts input (0→1, 1→0)."""
    if a == 0:
        return 1
    return 0


def gate_xor(a: Int, b: Int) -> Int:
    """XOR gate: returns 1 iff inputs differ."""
    if a != b:
        return 1
    return 0


def gate_nand(a: Int, b: Int) -> Int:
    """NAND gate: NOT(AND(a, b))."""
    return gate_not(gate_and(a, b))


def gate_nor(a: Int, b: Int) -> Int:
    """NOR gate: NOT(OR(a, b))."""
    return gate_not(gate_or(a, b))


# ── Adders ────────────────────────────────────────────────────────────────────


def half_adder(a: Int, b: Int) -> List[Int]:
    """Half adder. Returns [sum, carry]."""
    var result = List[Int]()
    result.append(gate_xor(a, b))
    result.append(gate_and(a, b))
    return result^


def full_adder(a: Int, b: Int, cin: Int) -> List[Int]:
    """Full adder. Returns [sum, carry_out]."""
    var ha1 = half_adder(a, b)
    var ha2 = half_adder(ha1[0], cin)
    var carry_out = gate_or(ha1[1], ha2[1])
    var result = List[Int]()
    result.append(ha2[0])
    result.append(carry_out)
    return result^


def ripple_carry_adder(a: List[Int], b: List[Int]) -> List[Int]:
    """N-bit ripple carry adder. Inputs and outputs are LSB first.
    Returns [sum_bits..., carry_out]."""
    var n = len(a)
    # A short b would be read past its end below (uncatchable abort).
    if len(b) < n:
        return List[Int]()
    var result = List[Int]()
    var carry = 0
    for i in range(n):
        var fa = full_adder(a[i], b[i], carry)
        result.append(fa[0])
        carry = fa[1]
    result.append(carry)
    return result^


# ── Multiplexer & Decoder ────────────────────────────────────────────────────


def multiplexer_2to1(a: Int, b: Int, sel: Int) -> Int:
    """2:1 multiplexer. sel=0 selects a, sel=1 selects b."""
    var not_sel = gate_not(sel)
    var out_a = gate_and(a, not_sel)
    var out_b = gate_and(b, sel)
    return gate_or(out_a, out_b)


def decoder_2to4(a: Int, b: Int) -> List[Int]:
    """2-to-4 decoder. a is LSB, b is MSB.
    Output index = b*2 + a is active (1), rest are 0."""
    var not_a = gate_not(a)
    var not_b = gate_not(b)
    var result = List[Int]()
    result.append(gate_and(not_a, not_b))  # o0: a=0, b=0
    result.append(gate_and(a, not_b))      # o1: a=1, b=0
    result.append(gate_and(not_a, b))      # o2: a=0, b=1
    result.append(gate_and(a, b))          # o3: a=1, b=1
    return result^


# ── Bit Conversion ────────────────────────────────────────────────────────────


def bits_to_int(bits: List[Int]) -> Int:
    """Convert bit list (LSB first) to integer."""
    var value = 0
    var power = 1
    for i in range(len(bits)):
        if bits[i] == 1:
            value += power
        power *= 2
    return value


def int_to_bits(value: Int, n_bits: Int) -> List[Int]:
    """Convert integer to bit list (LSB first) with n_bits width."""
    # n_bits drives the allocation; clamp the wire-supplied count.
    var nb = n_bits
    if nb > MAX_BIT_WIDTH:
        nb = MAX_BIT_WIDTH
    var result = List[Int]()
    var v = value
    for i in range(nb):
        result.append(v & 1)
        v >>= 1
    return result^
