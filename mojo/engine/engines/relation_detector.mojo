"""
engines/relation_detector.mojo — ERP-scale derived relationship detection. Zero Python.

Detects A×B≈C and A+B≈C formulaic relationships across all numeric column triples.
The O(n³) scan is bounded by column count — not row count — so it stays tractable
even for wide ERP tables (50 numeric cols → ~19,600 triples; 100 cols → ~161,700).

At Mojo speeds this runs ~1000× faster than the Python equivalent, making
continuous re-profiling of 1000-table ERPs viable without caching.

Input:
  {
    "engine_type": "relation_detect",
    "source": "orders",
    "min_confidence": 0.70,
    "columns": {
      "UNIT_PRICE": [100.0, 200.0, 150.0, ...],
      "QUANTITY":   [5, 10, 3, ...],
      "EXT_PRICE":  [500.0, 2000.0, 450.0, ...]
    }
  }

Output:
  {
    "source": "orders",
    "relationships": [
      {
        "formula": "EXT_PRICE = UNIT_PRICE × QUANTITY",
        "field_result": "EXT_PRICE",
        "field_a": "UNIT_PRICE",
        "field_b": "QUANTITY",
        "operation": "multiply",
        "confidence": 0.998
      }
    ],
    "columns_scanned": 3,
    "triples_tested": 1
  }
"""

from std.math import sqrt, abs as fabs

from json.parser import json_get_string, json_get_float
from conv import parse_float64
from dimensions import (
    infer_from_samples, propagate, role_for_dimension,
    DIM_UNKNOWN, DIM_COUNT, DIM_CURRENCY, DIM_RATE,
    DIM_RATIO, DIM_IDENTIFIER, DIM_INVALID,
)


# ── String helper ─────────────────────────────────────────────────────────────

def _substr(s: String, start: Int, end: Int) -> String:
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    var i = start if start >= 0 else 0
    var e = end if end <= n else n
    while i < e:
        result += chr(Int(bytes[i]))
        i += 1
    return result


# ── Column vector struct ──────────────────────────────────────────────────────

struct ColVector(Copyable, Movable):
    var name: String
    var values: List[Float64]

    def __init__(out self, name: String, values: List[Float64]):
        self.name = name
        self.values = values.copy()


# ── Float array parser ────────────────────────────────────────────────────────

def _parse_float_array(arr_str: String) -> List[Float64]:
    """Parse a JSON numeric array like [1, 2.5, -3, 1e4] → List[Float64]."""
    var result = List[Float64]()
    var n = len(arr_str)
    var bytes = arr_str.as_bytes()
    var i = 0

    # Skip to [
    while i < n and bytes[i] != UInt8(91):
        i += 1
    i += 1  # skip [

    while i < n:
        # Skip whitespace and commas
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44)
                         or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(93):  # ]
            break

        # Skip null / true / false tokens
        if bytes[i] == UInt8(110) or bytes[i] == UInt8(116) or bytes[i] == UInt8(102):
            while i < n and bytes[i] != UInt8(44) and bytes[i] != UInt8(93):
                i += 1
            continue

        # Parse number (int, float, negative, scientific notation)
        var start = i
        if bytes[i] == UInt8(45):  # -
            i += 1
        while i < n and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
            i += 1
        if i < n and bytes[i] == UInt8(46):  # .
            i += 1
            while i < n and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
                i += 1
        if i < n and (bytes[i] == UInt8(101) or bytes[i] == UInt8(69)):  # e/E
            i += 1
            if i < n and (bytes[i] == UInt8(43) or bytes[i] == UInt8(45)):
                i += 1
            while i < n and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
                i += 1

        var num_str = _substr(arr_str, start, i)
        if len(num_str) > 0:
            result.append(parse_float64(num_str))

    return result^


# ── Parse columns object (field_name → float array) ──────────────────────────

def _parse_columns(raw: String) -> List[ColVector]:
    """Walk 'columns' JSON object: each key → float array."""
    var result = List[ColVector]()

    var cols_key = '"columns"'
    var cols_pos = raw.find(cols_key)
    if cols_pos < 0:
        return result^

    var after_cols = _substr(raw, cols_pos + len(cols_key), len(raw))
    var outer_brace = after_cols.find("{")
    if outer_brace < 0:
        return result^

    var cols_json = _substr(after_cols, outer_brace, len(after_cols))
    var n = len(cols_json)
    var bytes = cols_json.as_bytes()
    var i = 1  # skip {

    while i < n:
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44)
                         or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(125):  # }
            break
        if bytes[i] != UInt8(34):
            break

        # Parse field name
        i += 1
        var name_start = i
        while i < n and bytes[i] != UInt8(34):
            i += 1
        var field_name = _substr(cols_json, name_start, i)
        i += 1

        # Skip ":"
        while i < n and bytes[i] != UInt8(58):
            i += 1
        i += 1
        while i < n and bytes[i] == UInt8(32):
            i += 1

        # Expect array [
        if i >= n or bytes[i] != UInt8(91):
            while i < n and bytes[i] != UInt8(44) and bytes[i] != UInt8(125):
                i += 1
            continue

        # Find matching ]
        var arr_start = i
        var depth = 0
        var j = i
        while j < n:
            var c = bytes[j]
            if c == UInt8(91):
                depth += 1
            elif c == UInt8(93):
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1

        var arr_str = _substr(cols_json, arr_start, j)
        i = j

        var values = _parse_float_array(arr_str)
        if len(field_name) > 0 and len(values) > 0:
            result.append(ColVector(field_name, values))

    return result^


# ── Statistical helpers ────────────────────────────────────────────────────────

def _pearson_r(a: List[Float64], b: List[Float64], n: Int) -> Float64:
    var mean_a: Float64 = 0.0
    var mean_b: Float64 = 0.0
    for i in range(n):
        mean_a += a[i]
        mean_b += b[i]
    mean_a /= Float64(n)
    mean_b /= Float64(n)

    var num: Float64 = 0.0
    var sq_a: Float64 = 0.0
    var sq_b: Float64 = 0.0
    for i in range(n):
        var da = a[i] - mean_a
        var db = b[i] - mean_b
        num += da * db
        sq_a += da * da
        sq_b += db * db

    var den = sqrt(sq_a * sq_b)
    if den < 1e-10:
        return 0.0
    return num / den


def _check_approx(predicted: List[Float64], actual: List[Float64], n: Int) -> Bool:
    """≥85% of non-zero rows within 5% relative error."""
    var valid = 0
    var matches = 0
    for i in range(n):
        var av = actual[i]
        if fabs(av) < 1e-9:
            continue
        valid += 1
        if fabs(predicted[i] - av) / fabs(av) <= 0.05:
            matches += 1
    if valid < 3:
        return False
    return Float64(matches) / Float64(valid) >= 0.85


# ── Main entry point ──────────────────────────────────────────────────────────

def _mean(v: List[Float64], n: Int) -> Float64:
    var s: Float64 = 0.0
    for i in range(n):
        s += v[i]
    return s / Float64(n)


def run_relation_detect(raw: String) raises -> String:
    """
    Detect A×B≈C and A+B≈C across all numeric column triples.

    Three-level pre-filter (all O(1) per triple after O(N²) setup):
      1. Correlation gate  — pre-computed Pearson matrix; skip triples where
                             max(|r(A,C)|, |r(B,C)|) < 0.25 (no linear signal).
      2. Magnitude gate    — |mean_a × mean_b| / |mean_c| outside [0.04, 25]
                             or |mean_a + mean_b| / |mean_c| outside [0.15, 7].
      3. Row-by-row check  — _check_approx (O(n)) only for surviving triples.

    Result: 90k+ triples → ~3-8k evaluated, ~3-10× faster than brute force.
    """
    var source = json_get_string(raw, "source")
    var min_conf: Float64 = json_get_float(raw, "min_confidence", 0.70)

    var cols = _parse_columns(raw)
    var nc = len(cols)

    if nc < 3:
        return ('{"source":"' + source
                + '","relationships":[],"columns_scanned":' + String(nc)
                + ',"triples_tested":0,"triples_evaluated":0}')

    # ── Phase 1: Pre-compute means (O(N·n)) ───────────────────────────────────
    var means = List[Float64]()
    for k in range(nc):
        var cv = cols[k].copy()
        var n = len(cv.values)
        means.append(_mean(cv.values, n) if n > 0 else 0.0)

    # ── Phase 1b: Pre-compute coefficient of variation (std/|mean|) ──────────
    # Columns with CV < 0.05 are near-constant — they can't be meaningful formula
    # components (e.g. Division=1, CURRENT_FLG=0/1 cause spurious A+const≈C hits).
    var stds = List[Float64]()
    var cvs  = List[Float64]()
    for k in range(nc):
        var cv_col = cols[k].copy()
        var n_c = len(cv_col.values)
        var mk  = means[k]
        var sq: Float64 = 0.0
        for idx in range(n_c):
            var d = cv_col.values[idx] - mk
            sq += d * d
        var sd = sqrt(sq / Float64(n_c)) if n_c > 1 else 0.0
        stds.append(sd)
        var cv_ratio = sd / fabs(mk) if fabs(mk) > 1e-9 else 0.0
        cvs.append(cv_ratio)

    # ── Phase 2: Pre-compute pairwise Pearson matrix (O(N²·n)) ───────────────
    # Stored as a flat List of size nc*nc; corr[i*nc+j] == corr[j*nc+i].
    var corr = List[Float64]()
    for _ in range(nc * nc):
        corr.append(0.0)

    for i in range(nc):
        var ci = cols[i].copy()
        var ni = len(ci.values)
        for j in range(i + 1, nc):
            var cj = cols[j].copy()
            var nj = len(cj.values)
            var n_ij = ni if ni <= nj else nj
            if n_ij < 3:
                continue
            var r = _pearson_r(ci.values, cj.values, n_ij)
            corr[i * nc + j] = r
            corr[j * nc + i] = r

    # CV threshold: columns with less than 5% relative variation are near-constant.
    # A formula component that barely varies adds no explanatory power.
    var CV_THRESH: Float64 = 0.05
    var CORR_THRESH: Float64 = 0.25

    var output = String('{"source":"')
    output += source
    output += '","relationships":['

    var total_triples = 0
    var triples_evaluated = 0
    var found = 0

    # ── Phase 3: Triple scan with three-level pre-filter ─────────────────────
    for k in range(nc):
        var cv = cols[k].copy()
        var n = len(cv.values)
        if n < 3:
            continue

        var mk = means[k]
        var abs_mk = fabs(mk)
        if abs_mk < 1e-9:
            continue  # all-zero result column — skip

        for i in range(nc):
            if i == k:
                continue
            var av = cols[i].copy()
            if len(av.values) < n:
                continue

            var mi = means[i]
            var r_ik = fabs(corr[i * nc + k])

            for j in range(i + 1, nc):
                if j == k:
                    continue
                var bv = cols[j].copy()
                if len(bv.values) < n:
                    continue

                total_triples += 1

                # ── Gate 1: Correlation ───────────────────────────────────
                # At least one of (A,C) or (B,C) must show linear signal.
                var r_jk = fabs(corr[j * nc + k])
                if r_ik < CORR_THRESH and r_jk < CORR_THRESH:
                    continue

                # ── Gate 1b: Variance — reject near-constant components ───
                # If A or B barely varies (CV < 5%), any A×B≈C or A+B≈C hit
                # is coincidental (constant offset/scale, not a real formula).
                if cvs[i] < CV_THRESH or cvs[j] < CV_THRESH:
                    continue

                # ── Gate 2: Magnitude ─────────────────────────────────────
                var mj = means[j]
                var do_multiply = True
                var do_add = True

                var mul_scale = fabs(mi * mj) / abs_mk
                if mul_scale < 0.04 or mul_scale > 25.0:
                    do_multiply = False

                var add_scale = fabs(mi + mj) / abs_mk
                if add_scale < 0.15 or add_scale > 7.0:
                    do_add = False

                if not do_multiply and not do_add:
                    continue

                # ── Gate 3: Row-by-row check (O(n)) ──────────────────────
                triples_evaluated += 1

                var products = List[Float64]()
                var sums = List[Float64]()
                if do_multiply:
                    for m in range(n):
                        products.append(av.values[m] * bv.values[m])
                if do_add:
                    for m in range(n):
                        sums.append(av.values[m] + bv.values[m])

                if do_multiply and _check_approx(products, cv.values, n):
                    var conf = _pearson_r(products, cv.values, n)
                    if conf < 0.0:
                        conf = -conf
                    if conf >= min_conf:
                        # Dimensional algebra — multiply path
                        var _da_m = infer_from_samples(av.values)
                        var _db_m = infer_from_samples(bv.values)
                        var dim_a_m: Int
                        var dim_b_m: Int
                        if _da_m == DIM_COUNT and _db_m != DIM_COUNT:
                            dim_a_m = DIM_COUNT
                            dim_b_m = DIM_RATE
                        elif _db_m == DIM_COUNT and _da_m != DIM_COUNT:
                            dim_a_m = DIM_RATE
                            dim_b_m = DIM_COUNT
                        elif mi <= mj:
                            dim_a_m = DIM_COUNT
                            dim_b_m = DIM_RATE
                        else:
                            dim_a_m = DIM_RATE
                            dim_b_m = DIM_COUNT
                        var dim_r_m = propagate("multiply", dim_a_m, dim_b_m)
                        var role_m  = role_for_dimension(dim_r_m)

                        if found > 0:
                            output += ","
                        output += '{"formula":"' + cv.name + ' = ' + av.name + ' x ' + bv.name + '",'
                        output += '"field_result":"' + cv.name + '",'
                        output += '"field_a":"' + av.name + '",'
                        output += '"field_b":"' + bv.name + '",'
                        output += '"operation":"multiply",'
                        output += '"dim_a":' + String(dim_a_m) + ','
                        output += '"dim_b":' + String(dim_b_m) + ','
                        output += '"dim_result":' + String(dim_r_m) + ','
                        output += '"role_result":"' + role_m + '",'
                        output += '"confidence":' + String(conf) + '}'
                        found += 1

                if do_add and _check_approx(sums, cv.values, n):
                    var conf = _pearson_r(sums, cv.values, n)
                    if conf < 0.0:
                        conf = -conf
                    if conf >= min_conf:
                        # Dimensional algebra — add path
                        var dim_a_a = infer_from_samples(av.values)
                        var dim_b_a = infer_from_samples(bv.values)
                        var dim_r_a = propagate("add", dim_a_a, dim_b_a)
                        # Fallback: if both operands are UNKNOWN (not count, not ratio),
                        # they're continuous values — result is also continuous (Rate).
                        if dim_r_a == DIM_UNKNOWN and dim_a_a == DIM_UNKNOWN and dim_b_a == DIM_UNKNOWN:
                            dim_r_a = DIM_RATE
                        var role_a = role_for_dimension(dim_r_a)

                        if found > 0:
                            output += ","
                        output += '{"formula":"' + cv.name + ' = ' + av.name + ' + ' + bv.name + '",'
                        output += '"field_result":"' + cv.name + '",'
                        output += '"field_a":"' + av.name + '",'
                        output += '"field_b":"' + bv.name + '",'
                        output += '"operation":"add",'
                        output += '"dim_a":' + String(dim_a_a) + ','
                        output += '"dim_b":' + String(dim_b_a) + ','
                        output += '"dim_result":' + String(dim_r_a) + ','
                        output += '"role_result":"' + role_a + '",'
                        output += '"confidence":' + String(conf) + '}'
                        found += 1

    output += '],"columns_scanned":' + String(nc)
    output += ',"triples_tested":' + String(total_triples)
    output += ',"triples_evaluated":' + String(triples_evaluated) + '}'
    return output
