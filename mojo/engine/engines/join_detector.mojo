"""
engines/join_detector.mojo — Instant join key detection. Zero Python.

Detects primary/foreign key relationships via:
1. Exact value overlap (Jaccard index via djb2 hash + set_ops)
2. Unique ratio analysis (high → likely key column)
3. Name similarity (same field name across sources → strong signal)
4. Cardinality classification: 1:1, 1:N, N:N

Input:
  {
    "engine_type": "join_detect",
    "source_a": "sales",
    "source_b": "orders",
    "min_confidence": 0.6,
    "columns": {
      "sales.ORDER_NUMBER":  {"values": ["SO001","SO002"], "unique_ratio": 0.98, "sample_size": 1000},
      "orders.ORDER_NUMBER": {"values": ["SO001","SO003"], "unique_ratio": 0.99, "sample_size": 500},
      "sales.CUSTOMER":      {"values": ["Acme","Baz"],   "unique_ratio": 0.45, "sample_size": 1000}
    }
  }

Output:
  {
    "join_keys": [
      {"field_a":"ORDER_NUMBER","source_a":"sales","field_b":"ORDER_NUMBER","source_b":"orders",
       "overlap":0.5,"cardinality":"1:1","fk_probability":0.86,"confidence":0.87}
    ],
    "total_candidates": 1
  }
"""

from field_mapper import to_lower
from string_distance import dice_coefficient
from set_ops import jaccard_index, to_set
from json.parser import json_get_string, json_get_float
from conv import parse_float64


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
    return result^


# ── djb2 hash ─────────────────────────────────────────────────────────────────

def _djb2(s: String) -> Int:
    var h: Int = 5381
    var bytes = s.as_bytes()
    for i in range(len(s)):
        h = ((h << 5) + h) ^ Int(bytes[i])
    if h < 0:
        h = -h
    return h % 1000000007  # keep manageable


# ── String value array extractor ──────────────────────────────────────────────

def _extract_values(col_json: String) -> List[String]:
    """Extract 'values' array from column JSON object (handles strings and numbers)."""
    var result = List[String]()
    var vpos = col_json.find('"values"')
    if vpos < 0:
        return result^
    var after = _substr(col_json, vpos + 8, len(col_json))
    var bracket = after.find("[")
    if bracket < 0:
        return result^
    var arr = _substr(after, bracket, len(after))
    var n = len(arr)
    var bytes = arr.as_bytes()
    var i = 1  # skip [

    while i < n:
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10)):
            i += 1
        if i >= n or bytes[i] == UInt8(93):
            break

        if bytes[i] == UInt8(34):  # "string"
            i += 1
            var start = i
            while i < n and bytes[i] != UInt8(34):
                i += 1
            result.append(_substr(arr, start, i))
            i += 1
        elif bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57) or bytes[i] == UInt8(45):
            # Numeric — convert to string
            var start = i
            if bytes[i] == UInt8(45):
                i += 1
            while i < n and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
                i += 1
            if i < n and bytes[i] == UInt8(46):
                i += 1
                while i < n and bytes[i] >= UInt8(48) and bytes[i] <= UInt8(57):
                    i += 1
            result.append(_substr(arr, start, i))
        elif bytes[i] == UInt8(110):  # null
            i += 4
        else:
            while i < n and bytes[i] != UInt8(44) and bytes[i] != UInt8(93):
                i += 1
    return result^


def _extract_unique_ratio(col_json: String) -> Float64:
    return json_get_float(col_json, "unique_ratio", 0.5)


# ── Overlap via hashing ───────────────────────────────────────────────────────

def _jaccard_str_lists(a: List[String], b: List[String]) -> Float64:
    """Jaccard overlap between two string value lists via djb2 hash + set_ops."""
    if len(a) == 0 or len(b) == 0:
        return 0.0
    var limit = 200
    var na = len(a) if len(a) <= limit else limit
    var nb = len(b) if len(b) <= limit else limit

    var h_a = List[Int]()
    for i in range(na):
        h_a.append(_djb2(a[i]))

    var h_b = List[Int]()
    for i in range(nb):
        h_b.append(_djb2(b[i]))

    var set_a = to_set(h_a)
    var set_b = to_set(h_b)
    return jaccard_index(set_a, set_b)


def _cardinality(ur_a: Float64, ur_b: Float64) -> String:
    var h_a = ur_a > 0.85
    var h_b = ur_b > 0.85
    if h_a and h_b:
        return "1:1"
    elif h_a and not h_b:
        return "1:N"
    elif not h_a and h_b:
        return "N:1"
    else:
        return "N:N"


def _name_sim(a: String, b: String) -> Float64:
    var la = to_lower(a)
    var lb = to_lower(b)
    if la == lb:
        return 1.0
    return dice_coefficient(la, lb)


# ── Column entry struct ───────────────────────────────────────────────────────

struct ColEntry(Copyable, Movable):
    var full_name: String
    var source: String
    var field: String
    var values: List[String]
    var unique_ratio: Float64

    def __init__(out self, full_name: String, source: String, field: String,
                values: List[String], unique_ratio: Float64):
        self.full_name = full_name
        self.source = source
        self.field = field
        self.values = values.copy()
        self.unique_ratio = unique_ratio


def _split_dot(full: String) -> List[String]:
    """Split "source.FIELD" → ["source", "FIELD"]. No dot → ["", full]."""
    var dot = full.find(".")
    var result = List[String]()
    if dot < 0:
        result.append("")
        result.append(full)
    else:
        result.append(_substr(full, 0, dot))
        result.append(_substr(full, dot + 1, len(full)))
    return result^


# ── Parse columns object ──────────────────────────────────────────────────────

def _parse_columns(raw: String) -> List[ColEntry]:
    """Walk the 'columns' JSON object and parse each entry."""
    var result = List[ColEntry]()

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
        while i < n and (bytes[i] == UInt8(32) or bytes[i] == UInt8(44) or bytes[i] == UInt8(10) or bytes[i] == UInt8(13)):
            i += 1
        if i >= n or bytes[i] == UInt8(125):
            break
        if bytes[i] != UInt8(34):
            break

        # Parse column key
        i += 1
        var name_start = i
        while i < n and bytes[i] != UInt8(34):
            i += 1
        var full_name = _substr(cols_json, name_start, i)
        i += 1

        # Skip ":"
        while i < n and bytes[i] != UInt8(58):
            i += 1
        i += 1
        while i < n and bytes[i] == UInt8(32):
            i += 1

        # Find matching } for col object
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

        var sf = _split_dot(full_name)
        var source = sf[0]
        var field = sf[1]
        var values = _extract_values(col_obj)
        var ur = _extract_unique_ratio(col_obj)

        result.append(ColEntry(full_name, source, field, values, ur))

    return result^


# ── Main entry point ──────────────────────────────────────────────────────────

def run_join_detect(raw: String) raises -> String:
    """Detect join key relationships between columns from different sources."""
    var min_conf: Float64 = json_get_float(raw, "min_confidence", 0.5)

    var cols = _parse_columns(raw)
    var nc = len(cols)

    if nc < 2:
        return '{"join_keys":[],"error":"need at least 2 columns from different sources"}'

    var output = String('{"join_keys":[')
    var total_found = 0

    for i in range(nc):
        for j in range(i + 1, nc):
            var a = cols[i].copy()
            var b = cols[j].copy()

            # Only cross-source pairs
            if a.source == b.source and len(a.source) > 0:
                continue

            # Need values to compare
            if len(a.values) == 0 or len(b.values) == 0:
                continue

            # Jaccard value overlap
            var overlap = _jaccard_str_lists(a.values, b.values)

            # Name similarity
            var name_sim = _name_sim(a.field, b.field)

            # Unique ratio match signal
            var ur_a = a.unique_ratio
            var ur_b = b.unique_ratio
            var ur_signal: Float64 = 0.0
            if ur_a > 0.80 or ur_b > 0.80:
                ur_signal = 0.5 + 0.5 * (ur_a + ur_b) / 2.0

            var confidence = overlap * 0.50 + name_sim * 0.30 + ur_signal * 0.20
            var fk_prob = overlap * 0.6 + ur_signal * 0.4

            if confidence < min_conf:
                continue

            var cardinality = _cardinality(ur_a, ur_b)

            if total_found > 0:
                output += ","
            output += '{"field_a":"' + a.field + '",'
            output += '"source_a":"' + a.source + '",'
            output += '"field_b":"' + b.field + '",'
            output += '"source_b":"' + b.source + '",'
            output += '"overlap":' + String(overlap) + ','
            output += '"name_similarity":' + String(name_sim) + ','
            output += '"cardinality":"' + cardinality + '",'
            output += '"fk_probability":' + String(fk_prob) + ','
            output += '"confidence":' + String(confidence) + '}'
            total_found += 1

    output += '],"total_candidates":' + String(total_found) + '}'
    return output
