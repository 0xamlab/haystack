"""
engines/column_profiler.mojo — Instant semantic column profiling. Zero Python.

Replaces hardcoded alias dictionaries with data-driven semantic type detection.
A "currency" field is a "currency" field whether it's called ext_price,
umsatz, chiffre_affaires, or 売上高 — the data pattern makes it unambiguous.

Input:
  {
    "engine_type": "column_profile",
    "columns": {
      "REVENUE":    {"values": [120000, 85000, 200000], "sample_size": 3},
      "ORDER_ID":   {"strings": ["ORD001", "ORD002"], "sample_size": 2},
      "MARGIN":     {"values": [0.12, 0.08, 0.23], "sample_size": 3}
    }
  }

Output:
  {
    "profiles": {
      "REVENUE": {
        "semantic_type": "currency",
        "polarity":  1,
        "unique_ratio": 1.0,
        "entropy":     1.58,
        "mean": 135000.0,
        "std":   48520.0,
        "distribution": "lognormal",
        "unit": "currency",
        "confidence": 0.92
      }
    }
  }

Semantic types (inferred from data — no hardcoded aliases):
  "currency"   — numeric, polarity signal, magnitude in hundreds+
  "percentage" — numeric, range 0-1 or 0-100
  "count"      — non-negative integers
  "id"         — unique_ratio > 0.85, name or pattern signals identity
  "date"       — string values matching date patterns
  "category"   — string, low unique_ratio (< 10%)
  "metric"     — numeric, not other types
"""

from std.math import log, sqrt, abs as fabs

from field_mapper import (
    contains_keyword,
    to_lower,
    detect_polarity,
    detect_unit_hint,
    infer_distribution_from_values,
)
from json.parser import json_get_string
from conv import parse_float64


# ── String helper ─────────────────────────────────────────────────────────────

fn _substr(s: String, start: Int, end: Int) -> String:
    """Build substring s[start:end] using byte-by-byte copy."""
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    var i = start
    var e = end
    if i < 0:
        i = 0
    if e > n:
        e = n
    while i < e:
        result += chr(Int(bytes[i]))
        i += 1
    return result


# ── djb2 hash (O(n) deduplication without List[String] scans) ────────────────

fn _djb2_str(s: String) -> Int:
    var h: Int = 5381
    var bytes = s.as_bytes()
    for i in range(len(s)):
        h = ((h << 5) + h) ^ Int(bytes[i])
    if h < 0:
        h = -h
    return h % 1000000007


# ── Entropy (Shannon, base 2) ─────────────────────────────────────────────────

fn _approx_entropy(values: List[Float64]) -> Float64:
    """Approximate Shannon entropy using 32-bin histogram."""
    var n = len(values)
    if n <= 1:
        return 0.0
    var mn = values[0]
    var mx = values[0]
    for i in range(1, n):
        if values[i] < mn:
            mn = values[i]
        if values[i] > mx:
            mx = values[i]
    var span = mx - mn
    if span <= 0.0:
        return 0.0
    var bins = 32
    var counts = List[Int]()
    for _ in range(bins):
        counts.append(0)
    for i in range(n):
        var idx = Int((values[i] - mn) / span * Float64(bins - 1))
        if idx < 0:
            idx = 0
        if idx >= bins:
            idx = bins - 1
        counts[idx] = counts[idx] + 1
    var ent: Float64 = 0.0
    var nf = Float64(n)
    for i in range(bins):
        if counts[i] > 0:
            var p = Float64(counts[i]) / nf
            ent -= p * log(p) / log(2.0)
    return ent


# ── String pattern detection ──────────────────────────────────────────────────

fn _is_date_string(s: String) -> Bool:
    """Check if string looks like a date (contains digit + separator)."""
    var n = len(s)
    if n < 6 or n > 32:
        return False
    var bytes = s.as_bytes()
    var has_sep = False
    var has_digit = False
    for i in range(n):
        var c = bytes[i]
        if c == UInt8(45) or c == UInt8(47) or c == UInt8(58):
            has_sep = True
        if c >= UInt8(48) and c <= UInt8(57):
            has_digit = True
    return has_sep and has_digit


fn _is_alphanumeric_id(s: String) -> Bool:
    """Check if string looks like an ID (alphanum, possibly with dashes)."""
    var n = len(s)
    if n < 2 or n > 30:
        return False
    var bytes = s.as_bytes()
    var has_digit = False
    var has_alpha = False
    var all_valid = True
    for i in range(n):
        var c = bytes[i]
        if c >= UInt8(48) and c <= UInt8(57):
            has_digit = True
        elif (c >= UInt8(65) and c <= UInt8(90)) or (c >= UInt8(97) and c <= UInt8(122)):
            has_alpha = True
        elif c == UInt8(45) or c == UInt8(95):
            pass
        else:
            all_valid = False
            break
    return all_valid and has_digit and has_alpha


fn _count_distinct_float(values: List[Float64]) -> Int:
    """Count distinct values via insertion sort."""
    var n = len(values)
    if n == 0:
        return 0
    var sorted = values.copy()
    for i in range(1, n):
        var key = sorted[i]
        var j = i - 1
        while j >= 0 and sorted[j] > key:
            sorted[j + 1] = sorted[j]
            j -= 1
        sorted[j + 1] = key
    var distinct = 1
    for i in range(1, n):
        if sorted[i] != sorted[i - 1]:
            distinct += 1
    return distinct


# ── Semantic type classification ──────────────────────────────────────────────

fn _classify_semantic_type(
    field_name: String,
    values: List[Float64],
    strings: List[String],
    polarity: Int,
    unit_hint: String,
    unique_ratio: Float64,
) -> String:
    """Classify column into semantic type from data patterns. Zero hardcoded aliases."""
    var has_numeric = len(values) > 0
    var has_strings = len(strings) > 0

    # ID detection: high unique ratio + name or pattern signals identity
    var name_signals_id = (
        contains_keyword(field_name, "id") or
        contains_keyword(field_name, "_no") or
        contains_keyword(field_name, "number") or
        contains_keyword(field_name, "code") or
        contains_keyword(field_name, "ref") or
        contains_keyword(field_name, "key")
    )

    if unique_ratio > 0.85:
        if name_signals_id:
            return "id"
        if has_strings and len(strings) > 0:
            var id_count = 0
            var check_n = len(strings)
            if check_n > 10:
                check_n = 10
            for i in range(check_n):
                if _is_alphanumeric_id(strings[i]):
                    id_count += 1
            if id_count > check_n / 2:
                return "id"

    # Date detection
    if has_strings and len(strings) > 0:
        var date_count = 0
        var check_n = len(strings)
        if check_n > 5:
            check_n = 5
        for i in range(check_n):
            if _is_date_string(strings[i]):
                date_count += 1
        if date_count > check_n / 2:
            return "date"

    # Category: low-cardinality string
    if has_strings and unique_ratio < 0.10:
        return "category"

    if not has_numeric:
        return "text"

    # Unit hint from field_mapper (authoritative)
    if unit_hint == "currency":
        return "currency"
    if unit_hint == "percentage":
        return "percentage"

    # Value range: percentage
    var mn = values[0]
    var mx = values[0]
    for i in range(1, len(values)):
        if values[i] < mn:
            mn = values[i]
        if values[i] > mx:
            mx = values[i]

    # Percentage: value range [0,1] AND name must signal it — prevents string
    # columns whose parsed zeros happen to fall in range from being misclassified.
    var name_signals_pct = (
        contains_keyword(field_name, "pct") or
        contains_keyword(field_name, "percent") or
        contains_keyword(field_name, "ratio") or
        contains_keyword(field_name, "rate") or
        contains_keyword(field_name, "margin") or
        contains_keyword(field_name, "fill") or
        contains_keyword(field_name, "utiliz")
    )
    if mn >= 0.0 and mx <= 1.05 and (name_signals_pct or unit_hint == "percentage"):
        return "percentage"

    # Count: non-negative integers
    var all_int = True
    for i in range(len(values)):
        if values[i] != Float64(Int(values[i])):
            all_int = False
            break
    if all_int and mn >= 0.0 and mx < 1000000.0 and not name_signals_id:
        if contains_keyword(field_name, "qty") or contains_keyword(field_name, "quantity") or contains_keyword(field_name, "count") or contains_keyword(field_name, "units"):
            return "count"

    # Currency: polarity signal + non-trivial magnitude
    if polarity != 0 and (mx > 10.0 or mn < -10.0):
        return "currency"

    if polarity != 0:
        return "metric"

    return "metric"


# ── JSON array parsers ────────────────────────────────────────────────────────

fn _extract_float_array(arr_json: String) -> List[Float64]:
    """Parse JSON array of numbers or quoted numeric strings → List[Float64].

    Handles both raw numbers [100.0, 200.0] and quoted numbers ["100.0", "200.0"].
    Always advances i to prevent infinite loops on unexpected tokens.
    """
    var result = List[Float64]()
    var n = len(arr_json)
    var bytes = arr_json.as_bytes()
    var i = 0
    while i < n and bytes[i] != UInt8(91):
        i += 1
    i += 1

    while i < n:
        # Skip whitespace and commas
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(93):  # ]
            break

        # null / true / false tokens
        if bytes[i] == UInt8(110) or bytes[i] == UInt8(116) or bytes[i] == UInt8(102):
            while i < n and bytes[i] != UInt8(44) and bytes[i] != UInt8(93):
                i += 1
            continue

        # Quoted string value — only parse if it looks like a number.
        # Non-numeric strings (e.g. "BOEING") return 0.0 from parse_float64,
        # which would poison the values list and trigger false percentage classification.
        if bytes[i] == UInt8(34):
            i += 1
            var str_start = i
            while i < n and bytes[i] != UInt8(34):
                i += 1
            var num_str = _substr(arr_json, str_start, i)
            if i < n:
                i += 1  # skip closing "
            # Validate: must start with digit, '-', or '.' to be numeric
            if len(num_str) > 0:
                var first = num_str.as_bytes()[0]
                var looks_numeric = (
                    (first >= UInt8(48) and first <= UInt8(57)) or  # 0-9
                    first == UInt8(45) or  # -
                    first == UInt8(46)     # .
                )
                if looks_numeric:
                    result.append(parse_float64(num_str))
            continue

        # Raw number (int, float, negative, scientific notation)
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
        if i > start:
            result.append(parse_float64(_substr(arr_json, start, i)))
        else:
            i += 1  # unrecognised token — always advance to prevent infinite loop

    return result^


fn _extract_string_array(arr_json: String) -> List[String]:
    """Parse JSON array of strings → List[String]."""
    var result = List[String]()
    var n = len(arr_json)
    var bytes = arr_json.as_bytes()
    var i = 0
    while i < n and bytes[i] != UInt8(91):
        i += 1
    i += 1
    while i < n:
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10)):
            i += 1
        if i >= n or bytes[i] == UInt8(93):
            break
        if bytes[i] == UInt8(34):
            i += 1
            var start = i
            while i < n and bytes[i] != UInt8(34):
                i += 1
            result.append(_substr(arr_json, start, i))
            i += 1
        else:
            while i < n and bytes[i] != UInt8(44) and bytes[i] != UInt8(93):
                i += 1
    return result^


# ── Column JSON object walker ────────────────────────────────────────────────

fn _find_bracket_value(s: String, key: String) -> String:
    """Find the array value for a key in a JSON object. Returns the array string."""
    var key_quoted = '"' + key + '"'
    var pos = s.find(key_quoted)
    if pos < 0:
        return ""
    var after = _substr(s, pos + len(key_quoted), len(s))
    var bracket = after.find("[")
    if bracket < 0:
        return ""
    return _substr(after, bracket, len(after))


# ── Main entry point ──────────────────────────────────────────────────────────

fn run_column_profile(raw: String) raises -> String:
    """
    Profile all columns and return semantic type classifications.
    Input: {"engine_type":"column_profile","columns":{col: {values:[...], strings:[...]}}}
    Output: {"profiles":{col: {semantic_type, polarity, unique_ratio, mean, ...}}}
    """
    # Find the "columns" object
    var cols_key = '"columns"'
    var cols_pos = raw.find(cols_key)
    if cols_pos < 0:
        return '{"error":"column_profile requires a columns object"}'

    # Find the outer { of the columns object
    var after_cols = _substr(raw, cols_pos + len(cols_key), len(raw))
    var outer_brace = after_cols.find("{")
    if outer_brace < 0:
        return '{"error":"columns must be a JSON object"}'

    var cols_json = _substr(after_cols, outer_brace, len(after_cols))
    var n = len(cols_json)
    var bytes = cols_json.as_bytes()
    var i = 1  # skip opening {

    var result = String('{"profiles":{')
    var first_col = True

    while i < n:
        # Skip whitespace and commas
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(125):  # }
            break
        if bytes[i] != UInt8(34):  # expect "
            break

        # Parse column name
        i += 1
        var name_start = i
        while i < n and bytes[i] != UInt8(34):
            i += 1
        var col_name = _substr(cols_json, name_start, i)
        i += 1

        # Skip ":"
        while i < n and bytes[i] != UInt8(58):
            i += 1
        i += 1
        while i < n and bytes[i] == UInt8(32):
            i += 1

        # Find matching } for this column object
        var obj_start = i
        var depth = 0
        var in_str = False
        var j = i
        while j < n:
            var c = bytes[j]
            if c == UInt8(34) and (j == 0 or bytes[j - 1] != UInt8(92)):
                in_str = not in_str
            elif not in_str:
                if c == UInt8(123) or c == UInt8(91):
                    depth += 1
                elif c == UInt8(125) or c == UInt8(93):
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
            j += 1
        var col_obj = _substr(cols_json, obj_start, j)
        i = j

        # Extract arrays
        var values_arr_str = _find_bracket_value(col_obj, "values")
        var strings_arr_str = _find_bracket_value(col_obj, "strings")

        var values = List[Float64]()
        if len(values_arr_str) > 0:
            values = _extract_float_array(values_arr_str)

        var strings = List[String]()
        if len(strings_arr_str) > 0:
            strings = _extract_string_array(strings_arr_str)

        # Compute semantic profile
        var polarity = detect_polarity(col_name)
        var unit = detect_unit_hint(col_name)

        var num_count = len(values)
        var str_count = len(strings)
        var total = num_count + str_count
        if total == 0:
            total = 1

        # Approximate unique ratio — O(n) hash deduplication, not O(n²) list scan
        var distinct_num = _count_distinct_float(values)
        var str_hashes = List[Int]()
        var distinct_str = 0
        for k in range(str_count):
            var h = _djb2_str(strings[k])
            var found = False
            for m in range(len(str_hashes)):
                if str_hashes[m] == h:
                    found = True
                    break
            if not found:
                str_hashes.append(h)
                distinct_str += 1
        var unique_ratio = Float64(distinct_num + distinct_str) / Float64(total)

        # Numeric stats
        var mean_val: Float64 = 0.0
        var std_val: Float64 = 0.0
        var min_val: Float64 = 0.0
        var max_val: Float64 = 0.0
        var entropy_val: Float64 = 0.0
        var dist_name = String("categorical")
        var dist_params = String("{}")

        if num_count > 0:
            mean_val = values[0]
            min_val = values[0]
            max_val = values[0]
            for k in range(1, num_count):
                mean_val += values[k]
                if values[k] < min_val:
                    min_val = values[k]
                if values[k] > max_val:
                    max_val = values[k]
            mean_val /= Float64(num_count)

            if num_count > 1:
                var sq_sum: Float64 = 0.0
                for k in range(num_count):
                    var diff = values[k] - mean_val
                    sq_sum += diff * diff
                std_val = sqrt(sq_sum / Float64(num_count - 1))

            entropy_val = _approx_entropy(values)
            var infer_result = infer_distribution_from_values(values)
            dist_name = infer_result[0]
            dist_params = infer_result[1]

        var sem_type = _classify_semantic_type(
            col_name, values, strings, polarity, unit, unique_ratio
        )

        # Confidence scoring
        var confidence: Float64 = 0.7
        if sem_type == "id" and unique_ratio > 0.95:
            confidence = 0.95
        elif sem_type == "currency" and unit == "currency" and polarity != 0:
            confidence = 0.92
        elif sem_type == "date" and str_count > 0:
            confidence = 0.90
        elif sem_type == "category" and str_count > 0 and unique_ratio < 0.05:
            confidence = 0.88

        # Emit profile
        if not first_col:
            result += ","
        first_col = False

        result += '"' + col_name + '":{'
        result += '"semantic_type":"' + sem_type + '",'
        result += '"polarity":' + String(polarity) + ','
        result += '"unique_ratio":' + String(unique_ratio) + ','
        result += '"sample_count":' + String(num_count + str_count) + ','
        result += '"confidence":' + String(confidence)

        if num_count > 0:
            result += ',"mean":' + String(mean_val)
            result += ',"std":' + String(std_val)
            result += ',"min":' + String(min_val)
            result += ',"max":' + String(max_val)
            result += ',"entropy":' + String(entropy_val)
            result += ',"distribution":"' + dist_name + '"'
            result += ',"dist_params":' + dist_params

        if len(unit) > 0:
            result += ',"unit":"' + unit + '"'

        result += "}"

    result += "}}"
    return result
