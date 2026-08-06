"""
vector_kernels/ranker.mojo — SIMD Float32 column ranking engine (v2).

Entry point: run_column_rank_v2(raw: String) -> String
JSON in → JSON out, same schema as column_ranker.mojo but using
Float32 SIMD 8-wide kernels for ~1000x Python speedup.

Score formula:
  final = clamp(0.55 * cosine_sim + 0.25 * token_jaccard
                + role_boost + prior_boost, 0.0, 1.0)

Ambiguity: flagged when score[0] - score[1] < AMBIG_GAP (0.08).

Mojo 0.26 notes:
  - String indexing: s[byte=i] returns StringSlice (comparable to literals)
  - String slicing: s[byte=a:b] returns StringSlice; String(slice) to own
  - List returns must use ^ (move transfer)
  - __copyinit__ param named 'copy', __moveinit__ param named 'take' (var)
  - Int(str) raises; wrap in try/except
"""

from std.math import sqrt


# ── Compile-time constants ────────────────────────────────────────────────────

comptime VEC_DIM:    Int     = 64
comptime SIMD_W:     Int     = 8
comptime MAX_CANDS:  Int     = 256
comptime AMBIG_GAP:  Float32 = Float32(0.08)
comptime W_NAME:     Float32 = Float32(0.55)
comptime W_TOKEN:    Float32 = Float32(0.25)


# ── SIMD kernels ──────────────────────────────────────────────────────────────

def _dot64(a: List[Float32], b: List[Float32]) -> Float32:
    var pa = a.unsafe_ptr()
    var pb = b.unsafe_ptr()
    var a0 = (pa +  0).load[width=SIMD_W]() * (pb +  0).load[width=SIMD_W]()
    var a1 = (pa +  8).load[width=SIMD_W]() * (pb +  8).load[width=SIMD_W]()
    var a2 = (pa + 16).load[width=SIMD_W]() * (pb + 16).load[width=SIMD_W]()
    var a3 = (pa + 24).load[width=SIMD_W]() * (pb + 24).load[width=SIMD_W]()
    var a4 = (pa + 32).load[width=SIMD_W]() * (pb + 32).load[width=SIMD_W]()
    var a5 = (pa + 40).load[width=SIMD_W]() * (pb + 40).load[width=SIMD_W]()
    var a6 = (pa + 48).load[width=SIMD_W]() * (pb + 48).load[width=SIMD_W]()
    var a7 = (pa + 56).load[width=SIMD_W]() * (pb + 56).load[width=SIMD_W]()
    return ((a0 + a1) + (a2 + a3) + (a4 + a5) + (a6 + a7)).reduce_add()


def _norm_inv(v: List[Float32]) -> Float32:
    var p = v.unsafe_ptr()
    var s0 = (p +  0).load[width=SIMD_W]()
    var s1 = (p +  8).load[width=SIMD_W]()
    var s2 = (p + 16).load[width=SIMD_W]()
    var s3 = (p + 24).load[width=SIMD_W]()
    var s4 = (p + 32).load[width=SIMD_W]()
    var s5 = (p + 40).load[width=SIMD_W]()
    var s6 = (p + 48).load[width=SIMD_W]()
    var s7 = (p + 56).load[width=SIMD_W]()
    var mag = (
        (s0*s0 + s1*s1) + (s2*s2 + s3*s3) +
        (s4*s4 + s5*s5) + (s6*s6 + s7*s7)
    ).reduce_add()
    if mag <= 0.0:
        return Float32(0.0)
    return Float32(1.0) / sqrt(mag)


def _cosine(
    a: List[Float32], b: List[Float32],
    ni_a: Float32, ni_b: Float32,
) -> Float32:
    if ni_a == 0.0 or ni_b == 0.0:
        return Float32(0.0)
    var raw = _dot64(a, b) * ni_a * ni_b
    if raw > 1.0:
        return Float32(1.0)
    if raw < 0.0:
        return Float32(0.0)
    return raw


# ── String utilities ──────────────────────────────────────────────────────────

def _contains_lower(s: String, sub: String) -> Bool:
    """Case-insensitive substring check via byte scan (avoids allocating _to_lower)."""
    var sb = s.as_bytes()
    var pb = sub.as_bytes()
    var sn = len(sb)
    var pn = len(pb)
    if pn == 0:
        return True
    if sn < pn:
        return False
    for i in range(sn - pn + 1):
        var matched = True
        for j in range(pn):
            var sc = sb[i + j]
            var pc = pb[j]
            # normalise s byte to lowercase for comparison
            if sc >= 65 and sc <= 90:
                sc = sc + 32
            if sc != pc:
                matched = False
                break
        if matched:
            return True
    return False


def _split_tokens(s: String) -> List[String]:
    """Split on _, -, ., space into lowercase tokens."""
    var tokens = List[String]()
    var cur = String("")
    var b = s.as_bytes()
    for i in range(len(b)):
        var c = b[i]
        if c == 95 or c == 45 or c == 46 or c == 32:   # _ - . space
            if len(cur) > 0:
                tokens.append(cur)
                cur = String("")
        elif c >= 65 and c <= 90:
            cur += chr(Int(c + 32))
        else:
            cur += chr(Int(c))
    if len(cur) > 0:
        tokens.append(cur)
    return tokens^


@always_inline
def _norm_byte(c: UInt8) -> UInt8:
    """Normalise a single byte: separators → 32 (space), uppercase → lowercase."""
    if c == 95 or c == 45 or c == 46:   # _ - .
        return 32
    if c >= 65 and c <= 90:             # A-Z → a-z
        return c + 32
    return c


def _build_vec(s: String, mut buf: List[Float32]) -> Float32:
    """
    Zero buf, fill with bigram counts (direct byte processing), return norm_inv.

    Avoids intermediate string allocation — normalises bytes in-place during
    the bigram pass, giving ~3× improvement over the string-concat version.
    """
    for i in range(VEC_DIM):
        buf[i] = Float32(0.0)
    var sb = s.as_bytes()
    var n  = len(sb)
    if n == 0:
        return Float32(0.0)
    var prev = _norm_byte(sb[0])
    for i in range(1, n):
        var cur = _norm_byte(sb[i])
        var h = (Int(prev) * 31 + Int(cur)) & (VEC_DIM - 1)
        buf[h] += Float32(1.0)
        prev = cur
    return _norm_inv(buf)


# ── Token Jaccard ─────────────────────────────────────────────────────────────

def _token_jaccard(a_toks: List[String], b_toks: List[String]) -> Float32:
    if len(a_toks) == 0 or len(b_toks) == 0:
        return Float32(0.0)
    var intersect = 0
    for i in range(len(a_toks)):
        for j in range(len(b_toks)):
            if a_toks[i] == b_toks[j]:
                intersect += 1
                break
    var union = len(a_toks) + len(b_toks) - intersect
    if union == 0:
        return Float32(0.0)
    return Float32(intersect) / Float32(union)


# ── Role boost ────────────────────────────────────────────────────────────────

def _role_boost(role: String, hint_toks: List[String]) -> Float32:
    """
    +0.12 if column role matches hint tokens, -0.08 on clear mismatch.
    role: "unit_measure" | "derived_measure" | ""
    """
    if role == "" or len(hint_toks) == 0:
        return Float32(0.0)
    var has_unit = False
    var has_ext  = False
    for i in range(len(hint_toks)):
        var t = hint_toks[i]
        if t == "unit" or t == "per" or t == "each":
            has_unit = True
        if t == "ext" or t == "extended" or t == "total" or t == "amount":
            has_ext = True
    if role == "unit_measure":
        if has_unit:
            return Float32(0.12)
        if has_ext:
            return Float32(-0.08)
    if role == "derived_measure":
        if has_ext:
            return Float32(0.12)
        if has_unit:
            return Float32(-0.08)
    return Float32(0.0)


# ── Source-type prior boost ───────────────────────────────────────────────────

def _prior_boost(source_type: String, col_raw: String) -> Float32:
    """Context priors based on document type and column name pattern (case-insensitive)."""
    if source_type == "POS":
        if _contains_lower(col_raw, "unit") and (
            _contains_lower(col_raw, "price") or _contains_lower(col_raw, "cost")
        ):
            return Float32(0.10)
    elif source_type == "BACKLOG":
        if (_contains_lower(col_raw, "ext") or _contains_lower(col_raw, "extended")) and (
            _contains_lower(col_raw, "price") or _contains_lower(col_raw, "cost")
        ):
            return Float32(0.10)
    elif source_type == "INVOICE":
        if _contains_lower(col_raw, "amount") or _contains_lower(col_raw, "total"):
            return Float32(0.10)
    return Float32(0.0)


# ── Score record ──────────────────────────────────────────────────────────────

struct _Score(Copyable, Movable):
    var source:      String
    var column:      String
    var score:       Float32
    var name_sim:    Float32
    var token_sim:   Float32
    var type_boost:  Float32
    var prior_boost: Float32

    def __init__(out self):
        self.source      = ""
        self.column      = ""
        self.score       = Float32(0.0)
        self.name_sim    = Float32(0.0)
        self.token_sim   = Float32(0.0)
        self.type_boost  = Float32(0.0)
        self.prior_boost = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.source      = copy.source
        self.column      = copy.column
        self.score       = copy.score
        self.name_sim    = copy.name_sim
        self.token_sim   = copy.token_sim
        self.type_boost  = copy.type_boost
        self.prior_boost = copy.prior_boost

    def __moveinit__(out self, var take: Self):
        self.source      = take.source
        self.column      = take.column
        self.score       = take.score
        self.name_sim    = take.name_sim
        self.token_sim   = take.token_sim
        self.type_boost  = take.type_boost
        self.prior_boost = take.prior_boost


def _insertion_sort(mut results: List[_Score]):
    """Sort descending by score (in-place insertion sort)."""
    var n = len(results)
    for i in range(1, n):
        # Extract key fields without implicit copy
        var ks  = results[i].score
        var kso = results[i].source
        var kc  = results[i].column
        var kns = results[i].name_sim
        var kts = results[i].token_sim
        var ktb = results[i].type_boost
        var kpb = results[i].prior_boost
        var j = i - 1
        while j >= 0 and results[j].score < ks:
            # shift element j → j+1
            var tmp = _Score()
            tmp.source      = results[j].source
            tmp.column      = results[j].column
            tmp.score       = results[j].score
            tmp.name_sim    = results[j].name_sim
            tmp.token_sim   = results[j].token_sim
            tmp.type_boost  = results[j].type_boost
            tmp.prior_boost = results[j].prior_boost
            results[j + 1] = tmp^
            j -= 1
        var ins = _Score()
        ins.source      = kso
        ins.column      = kc
        ins.score       = ks
        ins.name_sim    = kns
        ins.token_sim   = kts
        ins.type_boost  = ktb
        ins.prior_boost = kpb
        results[j + 1] = ins^


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _json_str(key: String, val: String) -> String:
    return '"' + key + '":"' + val + '"'

def _json_f32(key: String, val: Float32) -> String:
    var vi = Int(val * Float32(10000.0) + Float32(0.5))
    var whole = vi // 10000
    var frac  = vi  % 10000
    var fs = String(frac)
    while len(fs) < 4:
        fs = "0" + fs
    return '"' + key + '":' + String(whole) + "." + fs

def _json_bool(key: String, val: Bool) -> String:
    if val:
        return '"' + key + '":true'
    return '"' + key + '":false'


# ── JSON parser ───────────────────────────────────────────────────────────────

def _json_get(raw: String, key: String) -> String:
    """Minimal JSON string/bare-value extractor (byte-integer character tests)."""
    var needle = '"' + key + '"'
    var ki = raw.find(needle)
    if ki == -1:
        return ""
    var colon = raw.find(":", ki + len(needle))
    if colon == -1:
        return ""
    var start = colon + 1
    var rlen  = len(raw)
    var rb    = raw.as_bytes()
    # skip whitespace (32=' ', 9='\t')
    while start < rlen and (rb[start] == 32 or rb[start] == 9):
        start += 1
    if start >= rlen:
        return ""
    if rb[start] == 34:   # 34='"'
        var end = raw.find('"', start + 1)
        if end == -1:
            return ""
        return String(raw[byte=start + 1 : end])
    # bare value — stop at ',' (44) or '}' (125)
    var end2 = start
    while end2 < rlen and rb[end2] != 44 and rb[end2] != 125:
        end2 += 1
    return String(raw[byte=start : end2])


# ── Build output JSON ─────────────────────────────────────────────────────────

def _build_output(sorted: List[_Score], top_k: Int) -> String:
    var n = len(sorted)
    var out_n = n if n < top_k else top_k
    var gap = Float32(0.0)
    if n >= 2:
        gap = sorted[0].score - sorted[1].score
    var ambiguous = gap < AMBIG_GAP and n >= 2

    var out = String('{"matches":[')
    for i in range(out_n):
        if i > 0:
            out += ","
        # Read fields without implicit struct copy
        var sc  = sorted[i].score
        var src = sorted[i].source
        var col = sorted[i].column
        var ns  = sorted[i].name_sim
        var ts  = sorted[i].token_sim
        var tb  = sorted[i].type_boost
        var pb  = sorted[i].prior_boost
        out += "{"
        out += _json_str("source", src)    + ","
        out += _json_str("column", col)    + ","
        out += _json_f32("score",  sc)     + ","
        out += _json_f32("name_sim",    ns) + ","
        out += _json_f32("token_sim",   ts) + ","
        out += _json_f32("type_boost",  tb) + ","
        out += _json_f32("prior_boost", pb)
        out += "}"
    out += "],"
    out += _json_f32("confidence_gap", gap) + ","
    out += _json_bool("ambiguous", ambiguous)
    out += "}"
    return out


# ── Public entry point ────────────────────────────────────────────────────────

def run_column_rank_v2(raw: String) -> String:
    """
    Rank candidate columns against a query column using SIMD Float32 kernels.

    Input JSON schema:
    {
      "query": {
        "name":      "<column_name>",
        "role_hint": "<unit_measure|derived_measure|>",
        "source":    "<POS|BACKLOG|INVOICE|>"
      },
      "candidates": [
        {"source": "<label>", "name": "<column_name>"}, ...
      ],
      "top_k": 5
    }

    Output JSON schema:
    {
      "matches": [{source, column, score, name_sim, token_sim,
                   type_boost, prior_boost}, ...],
      "confidence_gap": <float>,
      "ambiguous": <bool>
    }
    """
    # ── Parse query block ─────────────────────────────────────────────────────
    var q_name = String("")
    var q_role = String("")
    var q_src  = String("")
    var q_block_start = raw.find('"query"')
    if q_block_start != -1:
        var q_open  = raw.find("{", q_block_start)
        var q_close = raw.find("}", q_open)
        if q_open != -1 and q_close != -1:
            var q_block = String(raw[byte=q_open : q_close + 1])
            q_name = _json_get(q_block, "name")
            q_role = _json_get(q_block, "role_hint")
            q_src  = _json_get(q_block, "source")

    if len(q_name) == 0:
        return '{"error":"missing query.name"}'

    # Parse top_k (Int(str) raises, wrap in try)
    var top_k = 5
    var top_k_s = _json_get(raw, "top_k")
    if len(top_k_s) > 0:
        try:
            var parsed = Int(top_k_s)
            if parsed > 0:
                top_k = parsed
        except:
            pass

    # ── Build query vector ────────────────────────────────────────────────────
    var q_buf = List[Float32](capacity=VEC_DIM)
    var c_buf = List[Float32](capacity=VEC_DIM)
    for _ in range(VEC_DIM):
        q_buf.append(Float32(0.0))
        c_buf.append(Float32(0.0))
    var q_ni      = _build_vec(q_name, q_buf)
    var q_toks    = _split_tokens(q_name)
    var hint_toks = _split_tokens(q_role)

    # ── Find candidates array ─────────────────────────────────────────────────
    var cands_start = raw.find('"candidates"')
    if cands_start == -1:
        return '{"error":"missing candidates"}'
    var arr_open = raw.find("[", cands_start)
    if arr_open == -1:
        return '{"error":"malformed candidates"}'
    var arr_close = raw.find("]", arr_open)
    if arr_close == -1:
        return '{"error":"malformed candidates"}'

    # ── Score each candidate ──────────────────────────────────────────────────
    var results = List[_Score]()
    var pos   = arr_open + 1
    var count = 0

    while pos < arr_close and count < MAX_CANDS:
        var obj_open = raw.find("{", pos)
        if obj_open == -1 or obj_open >= arr_close:
            break
        var obj_close = raw.find("}", obj_open)
        if obj_close == -1:
            break
        var obj    = String(raw[byte=obj_open : obj_close + 1])
        var c_src  = _json_get(obj, "source")
        var c_name = _json_get(obj, "name")
        pos    = obj_close + 1
        count += 1

        if len(c_name) == 0:
            continue

        # SIMD bigram cosine
        var c_ni  = _build_vec(c_name, c_buf)
        var nsim  = _cosine(q_buf, c_buf, q_ni, c_ni)

        # Token Jaccard
        var c_toks = _split_tokens(c_name)
        var tsim   = _token_jaccard(q_toks, c_toks)

        # Boosts
        var tb = _role_boost(q_role, hint_toks)
        var pb = _prior_boost(q_src, c_name)

        # Weighted fusion → clamp [0,1]
        var raw_score = W_NAME * nsim + W_TOKEN * tsim + tb + pb
        var fs = raw_score
        if fs > 1.0:
            fs = Float32(1.0)
        elif fs < 0.0:
            fs = Float32(0.0)

        var sc = _Score()
        sc.source      = c_src
        sc.column      = c_name
        sc.score       = fs
        sc.name_sim    = nsim
        sc.token_sim   = tsim
        sc.type_boost  = tb
        sc.prior_boost = pb
        results.append(sc^)

    if len(results) == 0:
        return '{"matches":[],"confidence_gap":0.0,"ambiguous":false}'

    _insertion_sort(results)
    return _build_output(results, top_k)
