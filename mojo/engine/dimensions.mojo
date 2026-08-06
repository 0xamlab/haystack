"""
dimensions.mojo — Business Dimension Engine. Zero Python imports.

Dimensional algebra for tabular data.  Replaces name-based heuristics with
math-based dimensional reasoning derived from numeric distributions and
formula relations already detected by the profiler.

Dimensions (comptime Int constants):
  DIM_UNKNOWN    0   not yet classified
  DIM_COUNT      1   discrete integer quantity  [unit]
  DIM_CURRENCY   2   monetary total             [$]
  DIM_RATE       3   per-unit value             [$/unit]  (cannot be summed)
  DIM_RATIO      4   proportion 0–1 or 0–100    [%]       (cannot be summed)
  DIM_IDENTIFIER 5   key / surrogate            —         (no arithmetic)
  DIM_INVALID   -1   dimensionally inconsistent formula result

Propagation table  (op, dim_a, dim_b) → result:

  multiply
    Count    × Rate     → Currency    qty × unit_price = total
    Count    × Currency → Currency    (weighted / bulk)
    Count    × Ratio    → Count       qty × fill_rate  = effective_qty
    Currency × Ratio    → Currency    total × tax_rate = tax
    Rate     × Ratio    → Rate        price × (1−disc) = net_price
    Rate     × Rate     → INVALID     price × price is meaningless
    Currency × Currency → INVALID

  add
    Currency + Currency → Currency    line_a + line_b = total
    Rate     + Rate     → Rate        base_cost + addon = unit_cost
    Count    + Count    → Count       qty_a + qty_b   = total_qty
    Ratio    + Ratio    → Ratio       (bounded, valid component-wise)
    Currency + Rate     → INVALID     $ + $/unit is dimensionally wrong
    Currency + Ratio    → INVALID
    Rate     + Ratio    → INVALID     THIS is the "Unit Cost + Reserve%" case

  divide
    Currency / Count    → Rate        total / qty     = unit_cost
    Currency / Currency → Ratio       profit / revenue = margin
    Count    / Count    → Ratio       sold / total    = utilization
    Rate     / Rate     → Ratio       actual / std    = variance ratio

Public API:
  infer_from_samples   — initial dimension guess from numeric distribution
  propagate            — (op, dim_a, dim_b) → result dimension
  propagate_is_valid   — True if the propagation is NOT DIM_INVALID
  validate_formula     — True if dim_a op dim_b → dim_c is consistent
  can_sum              — True if SUM(col) is semantically valid
  can_avg              — True if AVG(col) is semantically valid
  role_for_dimension   — dimension → canonical role string
  dimension_name       — dimension → human-readable string
  dimension_from_role  — role string → dimension constant
"""


# ── Dimension constants ───────────────────────────────────────────────────────

comptime DIM_UNKNOWN    : Int = 0
comptime DIM_COUNT      : Int = 1   # non-negative integers   [unit]
comptime DIM_CURRENCY   : Int = 2   # monetary total          [$]
comptime DIM_RATE       : Int = 3   # per-unit value          [$/unit]
comptime DIM_RATIO      : Int = 4   # proportion 0–1 or 0–100 [%]
comptime DIM_IDENTIFIER : Int = 5   # surrogate key, no math
comptime DIM_INVALID    : Int = -1  # dimensionally inconsistent


# ── infer_from_samples ────────────────────────────────────────────────────────


def infer_from_samples(samples: List[Float64]) -> Int:
    """
    Initial dimension guess from a numeric sample (up to 200 values).

    Classifiable without formula context:
      Count  — non-negative integers, < 5% have decimal portion > 1e-4
      Ratio  — all values in [0, 1.001] with > 10% decimal density

    Not distinguishable from samples alone:
      Currency, Rate — both return DIM_UNKNOWN (need formula context)
    """
    var n = len(samples)
    if n == 0:
        return DIM_UNKNOWN

    var mn : Float64 = samples[0]
    var mx : Float64 = samples[0]
    for i in range(1, n):
        if samples[i] < mn:
            mn = samples[i]
        if samples[i] > mx:
            mx = samples[i]

    # Must be non-negative for Count or Ratio
    if mn < 0.0:
        return DIM_UNKNOWN

    # Count decimal fraction
    var non_int : Int = 0
    for i in range(n):
        var v  = samples[i]
        var rv = Float64(Int(v + 0.5))
        var diff = v - rv
        if diff < 0.0:
            diff = -diff
        if diff > 1e-4:
            non_int += 1
    var dec_frac = Float64(non_int) / Float64(n)

    # ── Count: non-negative integers ──────────────────────────────────────────
    if dec_frac < 0.05:
        return DIM_COUNT

    # ── Ratio: bounded proportion [0, 1] ─────────────────────────────────────
    if mx <= 1.001 and dec_frac > 0.10:
        return DIM_RATIO

    # ── Anything else needs formula context ───────────────────────────────────
    return DIM_UNKNOWN


# ── propagate ─────────────────────────────────────────────────────────────────


def propagate(op: String, dim_a: Int, dim_b: Int) -> Int:
    """
    Return the result dimension of (dim_a  op  dim_b).

    Returns DIM_INVALID if the combination is dimensionally inconsistent.
    Returns DIM_UNKNOWN if the result cannot be determined from context.
    """
    if dim_a == DIM_IDENTIFIER or dim_b == DIM_IDENTIFIER:
        return DIM_INVALID

    # ── Multiply ─────────────────────────────────────────────────────────────
    if op == "multiply" or op == "mul" or op == "*" or op == "x":
        # Commutative: normalise so a <= b
        var a = dim_a
        var b = dim_b
        if a > b:
            var tmp = a
            a = b
            b = tmp

        if a == DIM_COUNT and b == DIM_RATE:     return DIM_CURRENCY
        if a == DIM_COUNT and b == DIM_CURRENCY: return DIM_CURRENCY
        if a == DIM_COUNT and b == DIM_RATIO:    return DIM_COUNT
        if a == DIM_CURRENCY and b == DIM_RATIO: return DIM_CURRENCY
        if a == DIM_RATIO and b == DIM_RATE:     return DIM_RATE
        if a == DIM_RATE and b == DIM_RATE:      return DIM_INVALID
        if a == DIM_CURRENCY and b == DIM_CURRENCY: return DIM_INVALID
        if a == DIM_RATIO and b == DIM_RATIO:    return DIM_RATIO
        return DIM_UNKNOWN

    # ── Add / Subtract ───────────────────────────────────────────────────────
    if op == "add" or op == "+" or op == "subtract" or op == "-":
        if dim_a == dim_b:
            return dim_a   # same dimension always valid

        # All cross-dimension additions where both are known are INVALID
        if dim_a != DIM_UNKNOWN and dim_b != DIM_UNKNOWN:
            return DIM_INVALID

        return DIM_UNKNOWN

    # ── Divide ────────────────────────────────────────────────────────────────
    if op == "divide" or op == "/":
        if dim_a == DIM_CURRENCY and dim_b == DIM_COUNT:    return DIM_RATE
        if dim_a == DIM_CURRENCY and dim_b == DIM_CURRENCY: return DIM_RATIO
        if dim_a == DIM_COUNT    and dim_b == DIM_COUNT:    return DIM_RATIO
        if dim_a == DIM_RATE     and dim_b == DIM_RATE:     return DIM_RATIO
        if dim_a == DIM_RATE     and dim_b == DIM_COUNT:    return DIM_RATE
        return DIM_UNKNOWN

    return DIM_UNKNOWN


# ── propagate_is_valid ────────────────────────────────────────────────────────


def propagate_is_valid(op: String, dim_a: Int, dim_b: Int) -> Bool:
    """True if (dim_a op dim_b) does NOT produce DIM_INVALID."""
    return propagate(op, dim_a, dim_b) != DIM_INVALID


# ── validate_formula ──────────────────────────────────────────────────────────


def validate_formula(op: String, dim_a: Int, dim_b: Int, dim_c: Int) -> Bool:
    """
    True if C = A op B is dimensionally consistent.

    DIM_UNKNOWN on any operand means "not yet classified" — return True
    (benefit of the doubt) to avoid false negatives during initial profiling.
    """
    if dim_a == DIM_UNKNOWN or dim_b == DIM_UNKNOWN or dim_c == DIM_UNKNOWN:
        return True

    var expected = propagate(op, dim_a, dim_b)

    if expected == DIM_INVALID:
        return False
    if expected == DIM_UNKNOWN:
        return True

    return expected == dim_c


# ── Aggregation validity ──────────────────────────────────────────────────────


def can_sum(dim: Int) -> Bool:
    """
    True if SUM(col) produces a meaningful result.
    Valid for Count and Currency only.
    Rate and Ratio are per-unit/proportional — summing them is semantically wrong.
    """
    return dim == DIM_COUNT or dim == DIM_CURRENCY


def can_avg(dim: Int) -> Bool:
    """True if AVG(col) produces a meaningful result."""
    return (dim == DIM_COUNT or dim == DIM_CURRENCY
            or dim == DIM_RATE or dim == DIM_RATIO)


def aggregation_valid(agg: String, dim: Int) -> Bool:
    """True if the given aggregation is dimensionally valid for the dimension."""
    if dim == DIM_IDENTIFIER:
        return False
    if agg == "sum":
        return can_sum(dim)
    if agg == "avg":
        return can_avg(dim)
    if agg == "count" or agg == "min" or agg == "max":
        return dim != DIM_IDENTIFIER
    return False


# ── Metadata helpers ──────────────────────────────────────────────────────────


def role_for_dimension(dim: Int) -> String:
    """Map dimension → canonical role string used in schema metadata."""
    if dim == DIM_COUNT:
        return String("base_measure")
    if dim == DIM_CURRENCY:
        return String("derived_measure")
    if dim == DIM_RATE:
        return String("unit_measure")
    if dim == DIM_RATIO:
        return String("ratio")
    if dim == DIM_IDENTIFIER:
        return String("identifier")
    # DIM_UNKNOWN and DIM_INVALID both fall through to "metric"
    return String("metric")


def dimension_name(dim: Int) -> String:
    """Human-readable name for a dimension constant."""
    if dim == DIM_COUNT:
        return String("Count [unit]")
    if dim == DIM_CURRENCY:
        return String("Currency [$]")
    if dim == DIM_RATE:
        return String("Rate [$/unit]")
    if dim == DIM_RATIO:
        return String("Ratio [%]")
    if dim == DIM_IDENTIFIER:
        return String("Identifier")
    if dim == DIM_INVALID:
        return String("INVALID")
    return String("Unknown")


def dimension_from_role(role: String) -> Int:
    """Reverse map: schema role string → dimension constant."""
    if role == "base_measure":
        return DIM_COUNT
    if role == "derived_measure":
        return DIM_CURRENCY
    if role == "unit_measure":
        return DIM_RATE
    if role == "ratio":
        return DIM_RATIO
    if role == "identifier":
        return DIM_IDENTIFIER
    return DIM_UNKNOWN
