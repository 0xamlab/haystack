"""
field_mapper.mojo — Self-mapping adaptive field system for any industry/data.

Maps arbitrary field names to simulation variables using:
1. Keyword-based polarity detection (positive/negative/neutral)
2. Value-range-based distribution inference
3. Industry vocabulary matching
4. Automatic objective function construction

Zero Python imports — all logic is native Mojo string matching.

Public API:
  detect_polarity(field_name) -> Int              — +1=positive, -1=negative, 0=neutral
  infer_distribution(low, high) -> Tuple          — distribution name + params JSON
  infer_distribution_from_values(values) -> Tuple  — distribution from sample values
  detect_unit_hint(field_name) -> String           — "currency", "percentage", etc.
  map_fields(raw_json) -> List[FieldMapping]       — auto-map JSON fields
  build_objective_function(mappings) -> String      — construct objective expression
  build_variables_json(mappings) -> String          — build canonical variables array
  contains_keyword(text, keyword) -> Bool           — case-insensitive substring check
  to_lower(s) -> String                             — lowercase ASCII conversion
"""

from std.math import log, sqrt

from json.parser import (
    json_get_float,
    json_get_object,
    json_get_array,
    json_array_len,
    json_array_get,
    find_key,
    skip_json_value,
    skip_whitespace,
)
from conv import parse_float64


# ── ASCII byte constants ──────────────────────────────────────────────────────

comptime _QUOTE = UInt8(34)       # "
comptime _BACKSLASH = UInt8(92)   # backslash
comptime _LBRACE = UInt8(123)     # {
comptime _RBRACE = UInt8(125)     # }
comptime _LBRACKET = UInt8(91)    # [
comptime _COLON = UInt8(58)       # :
comptime _COMMA = UInt8(44)       # ,
comptime _MINUS = UInt8(45)       # -
comptime _DIGIT_0 = UInt8(48)    # 0
comptime _DIGIT_9 = UInt8(57)    # 9


# ── FieldMapping: result of mapping one field ─────────────────────────────────


struct FieldMapping(Copyable, Movable):
    """Result of mapping one input field to a simulation variable."""
    var original_name: String         # Original field name from input
    var canonical_name: String        # Cleaned name for use as variable
    var polarity: Int                 # +1=positive (revenue), -1=negative (cost), 0=neutral
    var suggested_distribution: String # "normal", "uniform", "triangular", etc.
    var distribution_params: String   # JSON params string, e.g. '{"mean":100,"std":20}'
    var unit_hint: String             # "currency", "percentage", "count", "time", ""
    var confidence: Float64           # 0.0-1.0 how confident the mapping is

    def __init__(out self, original_name: String, canonical_name: String,
                polarity: Int, suggested_distribution: String,
                distribution_params: String, unit_hint: String,
                confidence: Float64):
        self.original_name = original_name
        self.canonical_name = canonical_name
        self.polarity = polarity
        self.suggested_distribution = suggested_distribution
        self.distribution_params = distribution_params
        self.unit_hint = unit_hint
        self.confidence = confidence


# ── String helpers ────────────────────────────────────────────────────────────


def to_lower(s: String) -> String:
    """Convert string to lowercase ASCII."""
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    for i in range(n):
        var c = bytes[i]
        # A=65, Z=90 → add 32 to get lowercase
        if c >= UInt8(65) and c <= UInt8(90):
            result += chr(Int(c) + 32)
        else:
            result += chr(Int(c))
    return result


def contains_keyword(text: String, keyword: String) -> Bool:
    """Case-insensitive substring check.
    "Total_Revenue_Q4" contains "revenue" → True
    """
    var lower_text = to_lower(text)
    var lower_kw = to_lower(keyword)
    var text_len = len(lower_text)
    var kw_len = len(lower_kw)
    if kw_len == 0 or kw_len > text_len:
        return False
    var text_bytes = lower_text.as_bytes()
    var kw_bytes = lower_kw.as_bytes()
    for i in range(text_len - kw_len + 1):
        var found = True
        for j in range(kw_len):
            if text_bytes[i + j] != kw_bytes[j]:
                found = False
                break
        if found:
            return True
    return False


def _find_keyword_position(text: String, keyword: String) -> Int:
    """Find position of keyword in text (case-insensitive). Returns -1 if not found."""
    var lower_text = to_lower(text)
    var lower_kw = to_lower(keyword)
    var text_len = len(lower_text)
    var kw_len = len(lower_kw)
    if kw_len == 0 or kw_len > text_len:
        return -1
    var text_bytes = lower_text.as_bytes()
    var kw_bytes = lower_kw.as_bytes()
    for i in range(text_len - kw_len + 1):
        var found = True
        for j in range(kw_len):
            if text_bytes[i + j] != kw_bytes[j]:
                found = False
                break
        if found:
            return i
    return -1


# ── Polarity detection ────────────────────────────────────────────────────────


def detect_polarity(field_name: String) -> Int:
    """
    Detect whether a field name represents a positive (+1), negative (-1),
    or neutral (0) variable based on keyword matching.

    Positive keywords: revenue, profit, income, sales, growth, return, gain,
                      value, benefit, upside, savings, yield, appreciation

    Negative keywords: cost, expense, loss, risk, churn, debt, liability,
                      depreciation, penalty, fee, overhead, downside, deficit

    Matching is case-insensitive and works on substrings.
    If both positive and negative keywords match, the one appearing first wins.
    """
    var sentinel = len(field_name) + 1
    var best_pos_positive = sentinel
    var best_pos_negative = sentinel

    # ── Positive keywords ──
    var pos_kw = List[String]()
    pos_kw.append("revenue")
    pos_kw.append("profit")
    pos_kw.append("income")
    pos_kw.append("sales")
    pos_kw.append("growth")
    pos_kw.append("return")
    pos_kw.append("gain")
    pos_kw.append("value")
    pos_kw.append("benefit")
    pos_kw.append("upside")
    pos_kw.append("savings")
    pos_kw.append("yield")
    pos_kw.append("appreciation")

    for i in range(len(pos_kw)):
        var p = _find_keyword_position(field_name, pos_kw[i])
        if p >= 0 and p < best_pos_positive:
            best_pos_positive = p

    # ── Negative keywords ──
    var neg_kw = List[String]()
    neg_kw.append("cost")
    neg_kw.append("expense")
    neg_kw.append("loss")
    neg_kw.append("risk")
    neg_kw.append("churn")
    neg_kw.append("debt")
    neg_kw.append("liability")
    neg_kw.append("depreciation")
    neg_kw.append("penalty")
    neg_kw.append("fee")
    neg_kw.append("overhead")
    neg_kw.append("downside")
    neg_kw.append("deficit")

    for i in range(len(neg_kw)):
        var p = _find_keyword_position(field_name, neg_kw[i])
        if p >= 0 and p < best_pos_negative:
            best_pos_negative = p

    # ── Priority: whichever keyword appears first wins ──
    var has_positive = best_pos_positive < sentinel
    var has_negative = best_pos_negative < sentinel

    if has_positive and has_negative:
        if best_pos_positive <= best_pos_negative:
            return 1
        return -1
    if has_positive:
        return 1
    if has_negative:
        return -1
    return 0


# ── Distribution inference from range ─────────────────────────────────────────


def infer_distribution(low: Float64, high: Float64) -> Tuple[String, String]:
    """
    Infer the best distribution from a value range (low, high).
    Returns (distribution_name, params_json).

    Rules:
    - If low == 0 and high == 1 → "beta" with alpha=2, beta=2
    - If low >= 0 and high <= 1 → "beta" with estimated params
    - If low > 0 and high/low > 10 → "lognormal" with estimated mean/std
    - Otherwise → "triangular" with mode at midpoint
    """
    # [0, 1] exact → beta
    if low == 0.0 and high == 1.0:
        return (String("beta"), String('{"alpha":2,"beta":2}'))

    # [0, 1] bounded → beta
    if low >= 0.0 and high <= 1.0:
        return (String("beta"), String('{"alpha":2,"beta":2}'))

    # Wide positive range (ratio > 10) → lognormal
    if low > 0.0 and high / low > 10.0:
        var mid = (low + high) / 2.0
        var ln_mid = log(mid)
        var ln_spread = (log(high) - log(low)) / 4.0
        var params = String('{"mean":') + String(ln_mid) + String(',"std":') + String(ln_spread) + String("}")
        return (String("lognormal"), params)

    # Default → triangular with mode at midpoint
    var mode = (low + high) / 2.0
    var params = String('{"low":') + String(low) + String(',"mode":') + String(mode) + String(',"high":') + String(high) + String("}")
    return (String("triangular"), params)


# ── Distribution inference from sample values ─────────────────────────────────


def infer_distribution_from_values(values: List[Float64]) -> Tuple[String, String]:
    """
    Infer distribution from a list of sample values.

    Rules:
    - All values 0 or 1 → "bernoulli"
    - All values >= 0, positive skew > 0.5 → "lognormal"
    - Bounded [0,1] → "beta"
    - Otherwise → "normal"
    """
    var n = len(values)
    if n == 0:
        return (String("normal"), String('{"mean":0,"std":1}'))

    # ── Compute statistics ──
    var sum_val: Float64 = 0.0
    var min_val = values[0]
    var max_val = values[0]
    var all_binary = True
    var all_positive = True

    for i in range(n):
        var v = values[i]
        sum_val += v
        if v < min_val:
            min_val = v
        if v > max_val:
            max_val = v
        if v != 0.0 and v != 1.0:
            all_binary = False
        if v < 0.0:
            all_positive = False

    var mean = sum_val / Float64(n)

    # ── Compute std and skewness ──
    var sum_sq: Float64 = 0.0
    var sum_cube: Float64 = 0.0
    for i in range(n):
        var diff = values[i] - mean
        sum_sq += diff * diff
        sum_cube += diff * diff * diff

    var variance = sum_sq / Float64(n)
    var std = sqrt(variance)

    # ── All binary → bernoulli ──
    if all_binary:
        var p = mean  # proportion of 1s
        var params = String('{"p":') + String(p) + String("}")
        return (String("bernoulli"), params)

    # ── Bounded [0, 1] → beta ──
    if min_val >= 0.0 and max_val <= 1.0:
        return (String("beta"), String('{"alpha":2,"beta":2}'))

    # ── Positive with positive skew → lognormal ──
    if all_positive and std > 0.0:
        var skewness = (sum_cube / Float64(n)) / (std * std * std)
        if skewness > 0.5:
            var ln_mean = log(mean)
            var ln_std = sqrt(log(1.0 + variance / (mean * mean)))
            var params = String('{"mean":') + String(ln_mean) + String(',"std":') + String(ln_std) + String("}")
            return (String("lognormal"), params)

    # ── Default → normal ──
    var params = String('{"mean":') + String(mean) + String(',"std":') + String(std) + String("}")
    return (String("normal"), params)


# ── Unit hint detection ───────────────────────────────────────────────────────


def detect_unit_hint(field_name: String) -> String:
    """
    Detect likely unit type from field name keywords.
    Returns one of: "currency", "percentage", "count", "time", "rate", "weight", ""
    """
    # ── Currency keywords ──
    var currency_kw = List[String]()
    currency_kw.append("price")
    currency_kw.append("cost")
    currency_kw.append("revenue")
    currency_kw.append("profit")
    currency_kw.append("salary")
    currency_kw.append("budget")
    currency_kw.append("amount")
    currency_kw.append("fee")
    currency_kw.append("value")
    currency_kw.append("income")
    for i in range(len(currency_kw)):
        if contains_keyword(field_name, currency_kw[i]):
            return String("currency")

    # ── Percentage keywords (check specific ones before "rate") ──
    var pct_kw = List[String]()
    pct_kw.append("ratio")
    pct_kw.append("probability")
    pct_kw.append("chance")
    pct_kw.append("percent")
    pct_kw.append("pct")
    pct_kw.append("margin")
    for i in range(len(pct_kw)):
        if contains_keyword(field_name, pct_kw[i]):
            return String("percentage")

    # ── Count keywords ──
    var count_kw = List[String]()
    count_kw.append("count")
    count_kw.append("number")
    count_kw.append("quantity")
    count_kw.append("units")
    count_kw.append("items")
    count_kw.append("users")
    count_kw.append("customers")
    for i in range(len(count_kw)):
        if contains_keyword(field_name, count_kw[i]):
            return String("count")

    # ── Time keywords ──
    var time_kw = List[String]()
    time_kw.append("days")
    time_kw.append("hours")
    time_kw.append("minutes")
    time_kw.append("duration")
    time_kw.append("period")
    time_kw.append("horizon")
    for i in range(len(time_kw)):
        if contains_keyword(field_name, time_kw[i]):
            return String("time")

    # ── Rate / yield → percentage ──
    if contains_keyword(field_name, "rate"):
        return String("percentage")
    if contains_keyword(field_name, "yield"):
        return String("percentage")

    # ── Speed / throughput / frequency / velocity → rate ──
    var rate_kw = List[String]()
    rate_kw.append("speed")
    rate_kw.append("throughput")
    rate_kw.append("frequency")
    rate_kw.append("velocity")
    for i in range(len(rate_kw)):
        if contains_keyword(field_name, rate_kw[i]):
            return String("rate")

    # ── Weight keywords ──
    var weight_kw = List[String]()
    weight_kw.append("weight")
    weight_kw.append("mass")
    weight_kw.append("kg")
    weight_kw.append("lb")
    for i in range(len(weight_kw)):
        if contains_keyword(field_name, weight_kw[i]):
            return String("weight")

    return String("")


# ── Internal: JSON object key extraction ──────────────────────────────────────


def _json_object_keys(data: String) -> List[String]:
    """Extract all top-level keys from a JSON object string.
    Scans byte-by-byte using the same approach as json/parser.mojo.
    """
    var keys = List[String]()
    var bytes = data.as_bytes()
    var n = len(data)

    # Find opening brace
    var p = skip_whitespace(data, 0)
    if p >= n or bytes[p] != _LBRACE:
        return keys^
    p += 1

    while p < n:
        p = skip_whitespace(data, p)
        if p >= n or bytes[p] == _RBRACE:
            break

        # Skip comma between entries
        if bytes[p] == _COMMA:
            p += 1
            p = skip_whitespace(data, p)

        # Expect a quoted string key
        if p >= n or bytes[p] != _QUOTE:
            break

        # Read key string
        p += 1  # skip opening "
        var key_start = p
        while p < n:
            if bytes[p] == _BACKSLASH:
                p += 2
                continue
            if bytes[p] == _QUOTE:
                break
            p += 1
        # Extract key characters
        var key = String("")
        for i in range(key_start, p):
            key += chr(Int(bytes[i]))
        keys.append(key)
        p += 1  # skip closing "

        # Skip whitespace + colon + whitespace
        p = skip_whitespace(data, p)
        if p < n and bytes[p] == _COLON:
            p += 1

        # Skip the value
        p = skip_json_value(data, p)

    return keys^


def _value_type_at(data: String, key: String) -> Int:
    """Return value type at key position: 1=object, 2=array, 3=number, 0=other."""
    var pos = find_key(data, key)
    if pos < 0:
        return 0
    var bytes = data.as_bytes()
    var n = len(data)
    if pos >= n:
        return 0
    var ch = bytes[pos]
    if ch == _LBRACE:
        return 1  # object
    if ch == _LBRACKET:
        return 2  # array
    if ch == _MINUS or (ch >= _DIGIT_0 and ch <= _DIGIT_9):
        return 3  # number
    return 0


# ── Full field mapping ────────────────────────────────────────────────────────


def map_fields(raw_json: String) -> List[FieldMapping]:
    """
    Auto-map fields from an arbitrary JSON object to simulation variables.

    Input: A JSON object like:
        {"revenue": {"low": 80000, "high": 200000},
         "cost": {"low": 40000, "high": 90000},
         "churn_risk": {"low": 0.05, "high": 0.25}}

    OR: A JSON object with scalar values:
        {"revenue": 100000, "cost": 50000, "growth_rate": 0.15}

    OR: A JSON object with arrays:
        {"revenue": [80000, 95000, 102000, ...], "cost": [40000, 45000, ...]}

    Returns a list of FieldMapping structs with detected polarities,
    distributions, and unit hints.
    """
    var mappings = List[FieldMapping]()
    var keys = _json_object_keys(raw_json)

    for i in range(len(keys)):
        var key = keys[i]
        var vtype = _value_type_at(raw_json, key)

        var polarity = detect_polarity(key)
        var unit = detect_unit_hint(key)
        var dist_name = String("normal")
        var dist_params = String('{"mean":0,"std":1}')
        var confidence: Float64 = 0.5

        if vtype == 1:
            # ── Object with "low"/"high" fields ──
            var obj = json_get_object(raw_json, key)
            var low = json_get_float(obj, "low", 0.0)
            var high = json_get_float(obj, "high", 0.0)
            var result = infer_distribution(low, high)
            dist_name = result[0]
            dist_params = result[1]
            confidence = 0.8
        elif vtype == 2:
            # ── Array of sample values ──
            var arr = json_get_array(raw_json, key)
            var arr_len = json_array_len(arr)
            var values = List[Float64]()
            for j in range(arr_len):
                var elem_str = json_array_get(arr, j)
                values.append(parse_float64(elem_str))
            var result = infer_distribution_from_values(values)
            dist_name = result[0]
            dist_params = result[1]
            confidence = 0.7
        elif vtype == 3:
            # ── Scalar number → normal centered on value ──
            var val = json_get_float(raw_json, key, 0.0)
            var std_est: Float64 = 1.0
            if val != 0.0:
                std_est = val * 0.1
            if std_est < 0.0:
                std_est = -std_est
            dist_name = String("normal")
            dist_params = String('{"mean":') + String(val) + String(',"std":') + String(std_est) + String("}")
            confidence = 0.6

        # Boost confidence if polarity was detected
        if polarity != 0:
            confidence += 0.1
            if confidence > 1.0:
                confidence = 1.0

        var canonical = to_lower(key)
        mappings.append(FieldMapping(
            key, canonical, polarity, dist_name, dist_params, unit, confidence
        ))

    return mappings^


# ── Objective function construction ───────────────────────────────────────────


def build_objective_function(mappings: List[FieldMapping]) -> String:
    """
    Build an objective function expression from mapped fields.

    Combines positive polarity fields (add) and negative polarity fields (subtract).
    Example: if revenue(+1) and cost(-1) → "revenue - cost"
    If only positive fields → join with " + "
    If no positive fields → use first field name
    """
    var positive = List[String]()
    var negative = List[String]()

    for i in range(len(mappings)):
        if mappings[i].polarity == 1:
            positive.append(mappings[i].canonical_name)
        elif mappings[i].polarity == -1:
            negative.append(mappings[i].canonical_name)

    # No polarity detected → use first field name
    if len(positive) == 0 and len(negative) == 0:
        if len(mappings) > 0:
            return mappings[0].canonical_name
        return String("")

    # Only negative fields → use first field name as fallback
    if len(positive) == 0 and len(negative) > 0:
        if len(mappings) > 0:
            return mappings[0].canonical_name
        return String("")

    # Build expression: positive fields joined with +, negative subtracted
    var result = String("")
    for i in range(len(positive)):
        if i > 0:
            result += " + "
        result += positive[i]

    for i in range(len(negative)):
        result += " - "
        result += negative[i]

    return result


# ── Variables JSON construction ───────────────────────────────────────────────


def build_variables_json(mappings: List[FieldMapping]) -> String:
    """
    Build a JSON variables array from mapped fields, suitable for the
    engine's canonical schema.

    Output format:
    [{"name":"revenue","distribution":"triangular","params":{"low":80000,...}}, ...]
    """
    var result = String("[")
    for i in range(len(mappings)):
        if i > 0:
            result += ","
        result += String('{"name":"')
        result += mappings[i].canonical_name
        result += String('","distribution":"')
        result += mappings[i].suggested_distribution
        result += String('","params":')
        result += mappings[i].distribution_params
        result += String("}")
    result += String("]")
    return result
