"""
vector_kernels/repo_ranker.mojo — repository file ranking (batched, SIMD Float32).

Entry point: run_repo_rank(raw: String) -> String   (JSON in → JSON out)

Repo-domain sibling of ranker.run_column_rank_v2: ranks ALL candidate source
files against the issue's query terms in ONE batched call, using the same
64-bucket bigram cosine + token-Jaccard fusion (no column role/source boosts).
This is the production "extend Mojo for repos" kernel for the /repositories
triage ranking lane; the Python side dispatches it once per triage.

Input JSON:
  {"query_terms": ["normalize","status"],
   "candidates": [{"path": "src/svc.py", "text": "src svc normalize_status"}, ...],
   "top_k": 25}
Output JSON:
  {"matches": [{"path": "src/svc.py", "score": 0.0..1.0}, ...]}  (descending)

Mojo 0.26 notes: String s[byte=a:b] slicing; List returns move with ^;
__copyinit__ param 'copy', __moveinit__ var param 'take'; Int(str) raises.
"""

from std.math import sqrt


comptime VEC_DIM:   Int     = 64
comptime SIMD_W:    Int     = 8
comptime MAX_CANDS: Int     = 512
comptime W_NAME:    Float32 = Float32(0.6)
comptime W_TOKEN:   Float32 = Float32(0.4)


# ── SIMD kernels (mirror vector_kernels.dot / ranker) ──────────────────────────

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


def _cosine(a: List[Float32], b: List[Float32], ni_a: Float32, ni_b: Float32) -> Float32:
    if ni_a == 0.0 or ni_b == 0.0:
        return Float32(0.0)
    var raw = _dot64(a, b) * ni_a * ni_b
    if raw > 1.0:
        return Float32(1.0)
    if raw < 0.0:
        return Float32(0.0)
    return raw


# ── String utilities ──────────────────────────────────────────────────────────

@always_inline
def _norm_byte(c: UInt8) -> UInt8:
    """Lowercase A-Z; keep a-z/0-9; map everything else (punctuation, JSON syntax,
    path separators) to space so bigrams are robust to formatting."""
    if c >= 65 and c <= 90:
        return c + 32
    if (c >= 97 and c <= 122) or (c >= 48 and c <= 57):
        return c
    return 32


def _build_vec(s: String, mut buf: List[Float32]) -> Float32:
    """Zero buf, fill with normalised bigram counts, return norm_inv."""
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


def _split_tokens(s: String) -> List[String]:
    """Lowercase alphanumeric tokens; any non-alnum byte is a separator (so a raw
    JSON array substring like '["fix","auth"]' tokenises to [fix, auth])."""
    var tokens = List[String]()
    var cur = String("")
    var b = s.as_bytes()
    for i in range(len(b)):
        var c = b[i]
        if (c >= 97 and c <= 122) or (c >= 48 and c <= 57):
            cur += chr(Int(c))
        elif c >= 65 and c <= 90:
            cur += chr(Int(c + 32))
        else:
            if cur.byte_length() > 0:
                tokens.append(cur)
                cur = String("")
    if cur.byte_length() > 0:
        tokens.append(cur)
    return tokens^


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


# ── Scored candidate + sort ─────────────────────────────────────────────────────

struct _Score(Copyable, Movable):
    var path:  String
    var score: Float32

    def __init__(out self):
        self.path  = ""
        self.score = Float32(0.0)

    def __copyinit__(out self, copy: Self):
        self.path  = copy.path
        self.score = copy.score

    def __moveinit__(out self, var take: Self):
        self.path  = take.path
        self.score = take.score


def _insertion_sort(mut results: List[_Score]):
    """Descending by score (stable enough for triage; n is the candidate count)."""
    var n = len(results)
    for i in range(1, n):
        var ks = results[i].score
        var kp = results[i].path
        var j = i - 1
        while j >= 0 and results[j].score < ks:
            var tmp = _Score()
            tmp.path  = results[j].path
            tmp.score = results[j].score
            results[j + 1] = tmp^
            j -= 1
        var ins = _Score()
        ins.path  = kp
        ins.score = ks
        results[j + 1] = ins^


# ── JSON helpers (mirror ranker) ────────────────────────────────────────────────

def _json_str(key: String, val: String) -> String:
    return '"' + key + '":"' + val + '"'


def _json_f32(key: String, val: Float32) -> String:
    var vi = Int(val * Float32(10000.0) + Float32(0.5))
    var whole = vi // 10000
    var frac  = vi  % 10000
    var fs = String(frac)
    while fs.byte_length() < 4:
        fs = "0" + fs
    return '"' + key + '":' + String(whole) + "." + fs


def _json_get(raw: String, key: String) -> String:
    var needle = '"' + key + '"'
    var ki = raw.find(needle)
    if ki == -1:
        return ""
    var colon = raw.find(":", ki + needle.byte_length())
    if colon == -1:
        return ""
    var start = colon + 1
    var rlen  = raw.byte_length()
    var rb    = raw.as_bytes()
    while start < rlen and (rb[start] == 32 or rb[start] == 9):
        start += 1
    if start >= rlen:
        return ""
    if rb[start] == 34:   # '"'
        var end = raw.find('"', start + 1)
        if end == -1:
            return ""
        return String(raw[byte=start + 1 : end])
    var end2 = start
    while end2 < rlen and rb[end2] != 44 and rb[end2] != 125:
        end2 += 1
    return String(raw[byte=start : end2])


def _build_output(sorted: List[_Score], top_k: Int) -> String:
    var n = len(sorted)
    var out_n = n if n < top_k else top_k
    var out = String('{"matches":[')
    for i in range(out_n):
        if i > 0:
            out += ","
        var sc = sorted[i].score
        var p  = sorted[i].path
        out += "{" + _json_str("path", p) + "," + _json_f32("score", sc) + "}"
    out += "]}"
    return out


# ── Entry point ─────────────────────────────────────────────────────────────────

def run_repo_rank(raw: String) -> String:
    # top_k
    var top_k = 25
    var top_k_s = _json_get(raw, "top_k")
    if top_k_s.byte_length() > 0:
        try:
            var parsed = Int(top_k_s)
            if parsed > 0:
                top_k = parsed
        except:
            pass

    # query_terms array → query text (the array substring; punctuation is normalised)
    var q_text = String("")
    var qt_start = raw.find('"query_terms"')
    if qt_start != -1:
        var qa_open  = raw.find("[", qt_start)
        var qa_close = raw.find("]", qa_open)
        if qa_open != -1 and qa_close != -1 and qa_close > qa_open:
            q_text = String(raw[byte=qa_open + 1 : qa_close])
    if q_text.byte_length() == 0:
        return '{"matches":[]}'

    var q_buf = List[Float32](capacity=VEC_DIM)
    var c_buf = List[Float32](capacity=VEC_DIM)
    for _ in range(VEC_DIM):
        q_buf.append(Float32(0.0))
        c_buf.append(Float32(0.0))
    var q_ni   = _build_vec(q_text, q_buf)
    var q_toks = _split_tokens(q_text)

    # candidates array
    var cands_start = raw.find('"candidates"')
    if cands_start == -1:
        return '{"matches":[]}'
    var arr_open = raw.find("[", cands_start)
    if arr_open == -1:
        return '{"matches":[]}'
    var arr_close = raw.find("]", arr_open)
    if arr_close == -1:
        return '{"matches":[]}'

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
        var c_path = _json_get(obj, "path")
        var c_text = _json_get(obj, "text")
        pos    = obj_close + 1
        count += 1
        if c_path.byte_length() == 0:
            continue
        if c_text.byte_length() == 0:
            c_text = c_path
        var c_ni  = _build_vec(c_text, c_buf)
        var nsim  = _cosine(q_buf, c_buf, q_ni, c_ni)
        var c_toks = _split_tokens(c_text)
        var tsim  = _token_jaccard(q_toks, c_toks)
        var score = W_NAME * nsim + W_TOKEN * tsim
        if score > 1.0:
            score = Float32(1.0)
        var s = _Score()
        s.path  = c_path
        s.score = score
        results.append(s^)

    _insertion_sort(results)
    return _build_output(results, top_k)
