"""
engines/column_matcher.mojo — N×M column matching engine. Zero Python.

Score formula: 0.40*name + 0.25*semantic_type + 0.20*polarity + 0.15*distribution

Input:
  {
    "engine_type": "column_match",
    "source_a": "sales",
    "source_b": "orders",
    "columns_a": [
      {"name":"EXT_PRICE","semantic_type":"currency","polarity":1,"distribution":"lognormal","mean":5000,"std":2000},
      ...
    ],
    "columns_b": [...]
    "min_confidence": 0.5
  }

Output:
  {
    "source_a": "sales",
    "source_b": "orders",
    "matches": [
      {"field_a":"EXT_PRICE","field_b":"AMOUNT","score":0.82,"name_score":0.55,
       "type_score":1.0,"polarity_score":1.0,"dist_score":0.73,"match_type":"semantic"}
    ]
  }
"""

from std.math import sqrt, abs as fabs

from field_mapper import to_lower
from string_distance import dice_coefficient, edit_similarity
from json.parser import json_get_string, json_get_float, json_get_int
from conv import parse_float64


# ── String helper ─────────────────────────────────────────────────────────────

fn _substr(s: String, start: Int, end: Int) -> String:
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    var i = start if start >= 0 else 0
    var e = end if end <= n else n
    while i < e:
        result += chr(Int(bytes[i]))
        i += 1
    return result


# ── Column profile struct ─────────────────────────────────────────────────────

struct ColProfile(Copyable, Movable):
    var name: String
    var semantic_type: String
    var polarity: Int
    var distribution: String
    var mean: Float64
    var std: Float64

    fn __init__(out self, name: String, semantic_type: String, polarity: Int,
                distribution: String, mean: Float64, std: Float64):
        self.name = name
        self.semantic_type = semantic_type
        self.polarity = polarity
        self.distribution = distribution
        self.mean = mean
        self.std = std


# ── Name normalization ────────────────────────────────────────────────────────

fn _normalize_name(s: String) -> String:
    """Lowercase, strip separators, expand abbreviations."""
    var lower = to_lower(s)
    var result = String("")
    var bytes = lower.as_bytes()
    for i in range(len(lower)):
        var c = bytes[i]
        if c != UInt8(95) and c != UInt8(32) and c != UInt8(45):
            result += chr(Int(c))

    # Abbreviation table
    if result == "qty":
        return "quantity"
    if result == "amt":
        return "amount"
    if result == "rev":
        return "revenue"
    if result == "cst":
        return "cost"
    if result == "num":
        return "number"
    if result == "dt":
        return "date"
    if result == "cust":
        return "customer"
    if result == "prc":
        return "price"
    return result


# ── Scoring components ────────────────────────────────────────────────────────

fn _name_score(a: String, b: String) -> Float64:
    var la = _normalize_name(a)
    var lb = _normalize_name(b)
    if la == lb:
        return 1.0
    var dice = dice_coefficient(la, lb)
    var edit = edit_similarity(la, lb)
    var substr_bonus: Float64 = 0.0
    if la.find(lb) >= 0 or lb.find(la) >= 0:
        substr_bonus = 0.15
    var score = dice * 0.6 + edit * 0.4 + substr_bonus
    if score > 1.0:
        score = 1.0
    return score


fn _semantic_type_score(type_a: String, type_b: String) -> Float64:
    if type_a == type_b:
        return 1.0
    if type_a == "id" or type_b == "id":
        return 0.0
    if type_a == "date" or type_b == "date":
        return 0.0
    var is_num_a = type_a == "currency" or type_a == "metric" or type_a == "count"
    var is_num_b = type_b == "currency" or type_b == "metric" or type_b == "count"
    if is_num_a and is_num_b:
        if (type_a == "currency" or type_a == "metric") and (type_b == "currency" or type_b == "metric"):
            return 0.7
        return 0.5
    if (type_a == "category" or type_a == "text") and (type_b == "category" or type_b == "text"):
        return 0.6
    return 0.0


fn _polarity_score(pol_a: Int, pol_b: Int) -> Float64:
    if pol_a == pol_b:
        return 1.0
    if pol_a == 0 or pol_b == 0:
        return 0.5
    return 0.2


fn _distribution_score(dist_a: String, dist_b: String,
                        mean_a: Float64, mean_b: Float64,
                        std_a: Float64, std_b: Float64) -> Float64:
    var base: Float64 = 0.0
    if dist_a == dist_b and len(dist_a) > 0:
        base = 0.5
    var cv_a: Float64 = 0.0
    var cv_b: Float64 = 0.0
    if fabs(mean_a) > 0.0:
        cv_a = fabs(std_a / mean_a)
    if fabs(mean_b) > 0.0:
        cv_b = fabs(std_b / mean_b)
    var cv_sim: Float64 = 0.0
    if cv_a > 0.0 and cv_b > 0.0:
        var ratio = cv_a / cv_b if cv_a >= cv_b else cv_b / cv_a
        if ratio <= 1.5:
            cv_sim = 0.5 * (1.0 - (ratio - 1.0))
            if cv_sim < 0.0:
                cv_sim = 0.0
    return base + cv_sim * 0.5


# ── JSON column array parser ──────────────────────────────────────────────────

fn _parse_col_profiles(arr_str: String) -> List[ColProfile]:
    """Parse JSON array of column profile objects into List[ColProfile]."""
    var result = List[ColProfile]()
    var n = len(arr_str)
    var bytes = arr_str.as_bytes()
    var i = 0

    # Skip to [
    while i < n and bytes[i] != UInt8(91):
        i += 1
    i += 1

    while i < n:
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(93):
            break
        if bytes[i] != UInt8(123):
            i += 1
            continue

        # Find matching }
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
        var obj = _substr(arr_str, obj_start, j)
        i = j

        var name = json_get_string(obj, "name")
        var sem_type = json_get_string(obj, "semantic_type")
        var dist = json_get_string(obj, "distribution")
        var polarity = json_get_int(obj, "polarity", 0)
        var mean_val: Float64 = json_get_float(obj, "mean", 0.0)
        var std_val: Float64 = json_get_float(obj, "std", 0.0)

        if len(name) > 0:
            result.append(ColProfile(name, sem_type, polarity, dist, mean_val, std_val))

    return result^


# ── Main entry point ──────────────────────────────────────────────────────────

fn run_column_match(raw: String) raises -> String:
    """Score every N×M column pair between two sources. Returns ranked matches."""
    var source_a = json_get_string(raw, "source_a")
    var source_b = json_get_string(raw, "source_b")
    var min_conf: Float64 = json_get_float(raw, "min_confidence", 0.5)
    if len(source_a) == 0:
        source_a = "source_a"
    if len(source_b) == 0:
        source_b = "source_b"

    # Extract columns_a and columns_b arrays
    var cols_a_key = '"columns_a"'
    var cols_b_key = '"columns_b"'
    var cols_a_pos = raw.find(cols_a_key)
    var cols_b_pos = raw.find(cols_b_key)
    if cols_a_pos < 0 or cols_b_pos < 0:
        return '{"error":"column_match requires columns_a and columns_b arrays"}'

    var after_a = _substr(raw, cols_a_pos + len(cols_a_key), len(raw))
    var bracket_a = after_a.find("[")
    if bracket_a < 0:
        return '{"error":"columns_a must be a JSON array"}'
    var cols_a = _parse_col_profiles(_substr(after_a, bracket_a, len(after_a)))

    var after_b = _substr(raw, cols_b_pos + len(cols_b_key), len(raw))
    var bracket_b = after_b.find("[")
    if bracket_b < 0:
        return '{"error":"columns_b must be a JSON array"}'
    var cols_b = _parse_col_profiles(_substr(after_b, bracket_b, len(after_b)))

    var na = len(cols_a)
    var nb = len(cols_b)
    if na == 0 or nb == 0:
        return '{"matches":[],"total_pairs":0}'

    var output = String('{"source_a":"')
    output += source_a
    output += '","source_b":"'
    output += source_b
    output += '","matches":['

    var total_matches = 0
    for i in range(na):
        for j in range(nb):
            var a = cols_a[i].copy()
            var b = cols_b[j].copy()

            var t_score = _semantic_type_score(a.semantic_type, b.semantic_type)
            # Hard veto for ID↔non-ID and date↔non-date
            if t_score == 0.0:
                continue

            var n_score = _name_score(a.name, b.name)
            var p_score = _polarity_score(a.polarity, b.polarity)
            var d_score = _distribution_score(
                a.distribution, b.distribution,
                a.mean, b.mean, a.std, b.std,
            )

            var combined = n_score * 0.40 + t_score * 0.25 + p_score * 0.20 + d_score * 0.15
            if combined < min_conf:
                continue

            var match_type = String("semantic")
            if n_score >= 0.99:
                match_type = "exact"
            elif n_score >= 0.80:
                match_type = "name_similar"
            elif t_score >= 0.9 and d_score >= 0.5:
                match_type = "statistical"

            if total_matches > 0:
                output += ","
            output += '{"field_a":"' + a.name + '",'
            output += '"field_b":"' + b.name + '",'
            output += '"score":' + String(combined) + ','
            output += '"name_score":' + String(n_score) + ','
            output += '"type_score":' + String(t_score) + ','
            output += '"polarity_score":' + String(p_score) + ','
            output += '"dist_score":' + String(d_score) + ','
            output += '"match_type":"' + match_type + '"}'
            total_matches += 1

    output += '],"total_pairs":' + String(na * nb) + '}'
    return output
