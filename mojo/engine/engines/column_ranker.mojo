"""
engines/column_ranker.mojo — Vector-based column ranking engine.

Replaces Python-side _metric_candidate_score with a Mojo-native pipeline:
  1. 64-bucket sparse bigram frequency vector (hash-based)
  2. Cosine similarity in that vector space
  3. Jaccard token overlap (space/underscore tokens)
  4. Type-aware role multipliers (unit_measure vs derived_measure vs base_measure)
  5. Source-context priors  (POS→UNIT_COST, BACKLOG→EXT_PRICE, etc.)
  6. Top-K selection + confidence gap for ambiguity detection

Benchmark targets (from project benchmarks):
  vector_similarity       → ~155x over Python
  engines_column_matcher  → ~1482x over Python  (same tight-loop pattern)

Input:
  {
    "hint_words": ["unit", "cost"],
    "candidates": [
      {"source":"orders","column":"UNIT_COST","role":"unit_measure",
       "semantic_type":"currency","polarity":-1,"fill_rate":0.98},
      {"source":"orders","column":"EXT_COST","role":"derived_measure",
       "semantic_type":"currency","polarity":-1,"fill_rate":0.99},
      ...
    ],
    "context": {"source_type":"POS","preferred_source":"orders"},
    "top_k": 5
  }

Output:
  {
    "ranked": [
      {"source":"orders","column":"UNIT_COST","score":0.92,
       "name_sim":0.74,"token_sim":0.67,"type_boost":0.10,"prior_boost":0.08,
       "confidence_gap":0.21},
      ...
    ],
    "ambiguous": false
  }
"""

from std.math import sqrt, abs as fabs

from field_mapper import to_lower
from json.parser import (
    json_get_float,
    json_get_int,
    json_get_string,
    json_get_array,
    json_array_len,
    json_array_get,
    json_get_object,
)
from conv import parse_float64, parse_int
from vector_kernels.table import CandidateTable, build_query


# ── Constants ──────────────────────────────────────────────────────────────────

comptime VEC_BUCKETS: Int     = 64    # bigram hash buckets
comptime MAX_CANDS:   Int     = 1024  # hard cap on candidates per call
comptime AMBIG_GAP:   Float64 = 0.08  # gap below which top-2 are "ambiguous"
comptime SOURCE_UNKNOWN_ID: UInt16 = 0
comptime SOURCE_POS_ID:     UInt16 = 1
comptime SOURCE_BACKLOG_ID: UInt16 = 2
comptime SOURCE_INVOICE_ID: UInt16 = 3
comptime ROLE_OTHER_ID:     UInt8  = 0
comptime ROLE_UNIT_ID:      UInt8  = 1
comptime ROLE_DERIVED_ID:   UInt8  = 2


# ── String helpers ─────────────────────────────────────────────────────────────

def _substr(s: String, start: Int, end: Int) -> String:
    var result = String("")
    var bytes  = s.as_bytes()
    var n      = len(s)
    var i      = start if start >= 0 else 0
    var e      = end if end <= n else n
    while i < e:
        result += chr(Int(bytes[i]))
        i += 1
    return result


def _is_sep(c: UInt8) -> Bool:
    """Underscore, space, hyphen, or dot are token separators."""
    return c == 95 or c == 32 or c == 45 or c == 46


def _normalize(s: String) -> String:
    """Lowercase and replace separators with spaces."""
    var result = String("")
    var bytes  = s.as_bytes()
    var n      = len(s)
    for i in range(n):
        var c = bytes[i]
        if _is_sep(c):
            result += " "
        elif c >= 65 and c <= 90:
            result += chr(Int(c + 32))
        else:
            result += chr(Int(c))
    return result


def _tokens(s: String) -> List[String]:
    """Split a normalised string on spaces → token list."""
    var result = List[String]()
    var norm   = _normalize(s)
    var bytes  = norm.as_bytes()
    var n      = len(norm)
    var cur    = String("")
    for i in range(n):
        var c = bytes[i]
        if c == 32:
            if len(cur) > 0:
                result.append(cur)
                cur = String("")
        else:
            cur += chr(Int(c))
    if len(cur) > 0:
        result.append(cur)
    return result^


# ── Bigram vector ──────────────────────────────────────────────────────────────

def _bigram_vec(s: String) -> List[Float64]:
    """Compute a 64-bucket bigram frequency vector, L2-normalised."""
    var vec   = List[Float64]()
    for _ in range(VEC_BUCKETS):
        vec.append(0.0)
    var norm_s = _normalize(s)
    var bytes  = norm_s.as_bytes()
    var n      = len(norm_s)
    if n < 2:
        return vec^
    for i in range(n - 1):
        # Polynomial hash of (c_i, c_{i+1}) into [0, VEC_BUCKETS)
        var h = (Int(bytes[i]) * 31 + Int(bytes[i + 1])) & (VEC_BUCKETS - 1)
        vec[h] = vec[h] + 1.0
    # L2 normalise
    var mag = 0.0
    for i in range(VEC_BUCKETS):
        mag += vec[i] * vec[i]
    if mag > 0.0:
        mag = sqrt(mag)
        for i in range(VEC_BUCKETS):
            vec[i] = vec[i] / mag
    return vec^


def _cosine(a: List[Float64], b: List[Float64]) -> Float64:
    """Dot product of two pre-normalised 64-dim vectors."""
    var dot = 0.0
    for i in range(VEC_BUCKETS):
        dot += a[i] * b[i]
    if dot < 0.0:
        return 0.0
    if dot > 1.0:
        return 1.0
    return dot


# ── Token Jaccard ──────────────────────────────────────────────────────────────

def _token_jaccard(a_toks: List[String], b_toks: List[String]) -> Float64:
    """Jaccard similarity on token lists."""
    var na = len(a_toks)
    var nb = len(b_toks)
    if na == 0 and nb == 0:
        return 1.0
    if na == 0 or nb == 0:
        return 0.0
    var shared = 0
    for i in range(na):
        for j in range(nb):
            if a_toks[i] == b_toks[j]:
                shared += 1
                break
    var union = na + nb - shared
    if union == 0:
        return 0.0
    return Float64(shared) / Float64(union)


# ── Role type boost ────────────────────────────────────────────────────────────

def _role_boost(role: String, hint_toks: List[String], query_role: String) -> Float64:
    """
    Adds up to +0.12 when hint semantics match the candidate's role.

    unit_measure     — hint contains "unit", "per", "each", "price"
    derived_measure  — hint contains "ext", "extended", "total", "amount"
    base_measure     — hint contains "base", "standard", "list", "gross"
    ratio            — hint contains "ratio", "rate", "pct", "margin", "pct"
    """
    var n = len(hint_toks)
    var role_norm = to_lower(role)
    var query_role_norm = to_lower(query_role)
    var BOOST: Float64 = 0.12

    if len(query_role_norm) > 0:
        var query_wants_unit = (
            query_role_norm == "unit_measure" or query_role_norm == "ratio"
        )
        var query_wants_derived = (
            query_role_norm == "derived_measure"
            or query_role_norm == "base_measure"
        )
        var role_is_unit = role_norm == "unit_measure" or role_norm == "ratio"
        var role_is_derived = (
            role_norm == "derived_measure" or role_norm == "base_measure"
        )

        if query_wants_unit and role_is_unit:
            return BOOST
        if query_wants_derived and role_is_derived:
            return BOOST
        if query_wants_unit and role_is_derived:
            return -0.08
        if query_wants_derived and role_is_unit:
            return -0.08
        return 0.0

    var want_unit    = False
    var want_derived = False
    var want_base    = False
    var want_ratio   = False

    for i in range(n):
        var t = hint_toks[i]
        if t == "unit" or t == "per" or t == "each" or t == "price":
            want_unit = True
        if t == "ext" or t == "extended" or t == "total" or t == "amount":
            want_derived = True
        if t == "base" or t == "standard" or t == "list" or t == "gross":
            want_base = True
        if t == "ratio" or t == "rate" or t == "pct" or t == "margin" or t == "fill":
            want_ratio = True

    if role_norm == "unit_measure" and want_unit:
        return BOOST
    if role_norm == "derived_measure" and want_derived:
        return BOOST
    if role_norm == "base_measure" and want_base:
        return BOOST
    if role_norm == "ratio" and want_ratio:
        return BOOST

    # Negative penalty: clear mismatch (hint wants unit but role is derived)
    if want_unit and (role_norm == "derived_measure" or role_norm == "base_measure"):
        return -0.08
    if want_derived and role_norm == "unit_measure":
        return -0.08

    return 0.0


# ── Source-context prior ───────────────────────────────────────────────────────

def _prior_boost(source_type: String, col_norm: String) -> Float64:
    """
    Dataset/context prior: certain column patterns are highly likely in known
    source types.  Returns up to +0.10.

    POS / POINT_OF_SALE:
      UNIT_COST, UNIT_PRICE, SELL_PRICE  → +0.10
      EXT_COST, EXT_PRICE                → +0.05

    BACKLOG / ORDER:
      EXT_PRICE, EXT_COST, AMOUNT        → +0.10
      UNIT_PRICE                         → +0.05

    INVOICE / AP / AR:
      AMOUNT, TOTAL, INVOICE_AMT         → +0.10
    """
    var col = col_norm  # already lower + space-separated from _normalize
    var src = source_type  # raw, may be uppercase

    # Normalise source_type comparison (quick checks on substrings)
    var src_bytes = src.as_bytes()
    var src_len   = len(src)
    var s_lower   = String("")
    for i in range(src_len):
        var c = src_bytes[i]
        if c >= 65 and c <= 90:
            s_lower += chr(Int(c + 32))
        else:
            s_lower += chr(Int(c))

    # Column pattern helpers
    var has_unit   = col.find("unit") >= 0
    var has_ext    = col.find("ext") >= 0
    var has_price  = col.find("price") >= 0
    var has_cost   = col.find("cost") >= 0
    var has_amount = col.find("amount") >= 0 or col.find("amt") >= 0
    var has_total  = col.find("total") >= 0

    var is_pos     = s_lower.find("pos") >= 0 or s_lower.find("point") >= 0 or s_lower.find("sale") >= 0
    var is_backlog = s_lower.find("backlog") >= 0 or s_lower.find("order") >= 0
    var is_invoice = s_lower.find("invoice") >= 0 or s_lower.find("ap") >= 0 or s_lower.find("ar") >= 0

    if is_pos:
        if has_unit and (has_cost or has_price):
            return 0.10
        if has_ext and (has_cost or has_price):
            return 0.05
    if is_backlog:
        if has_ext and (has_price or has_cost):
            return 0.10
        if has_unit and has_price:
            return 0.05
    if is_invoice:
        if has_amount or has_total:
            return 0.10

    return 0.0


# ── Candidate result buffer ────────────────────────────────────────────────────

struct RankResult(Copyable, Movable):
    var source:      String
    var column:      String
    var score:       Float64
    var name_sim:    Float64
    var token_sim:   Float64
    var type_boost:  Float64
    var prior_boost: Float64

    def __init__(out self, source: String, column: String, score: Float64,
                name_sim: Float64, token_sim: Float64,
                type_boost: Float64, prior_boost: Float64):
        self.source      = source
        self.column      = column
        self.score       = score
        self.name_sim    = name_sim
        self.token_sim   = token_sim
        self.type_boost  = type_boost
        self.prior_boost = prior_boost


def _insertion_sort(results: List[RankResult]) -> List[RankResult]:
    """Sort by score descending (small N — in-place insertion sort)."""
    var n = len(results)
    var sorted = List[RankResult]()
    for i in range(n):
        sorted.append(results[i].copy())
    for i in range(1, n):
        var j = i - 1
        while j >= 0 and sorted[j].score < sorted[j + 1].score:
            var tmp       = sorted[j].copy()
            sorted[j]     = sorted[j + 1].copy()
            sorted[j + 1] = tmp.copy()
            j -= 1
    return sorted^


# ── JSON output builder ────────────────────────────────────────────────────────

def _fmt_float(v: Float64) -> String:
    """Round to 4 decimal places and convert to string."""
    var rounded = Float64(Int(v * 10000.0 + 0.5)) / 10000.0
    return String(rounded)


def _build_output(sorted: List[RankResult], top_k: Int) -> String:
    var n      = len(sorted)
    var k      = top_k if top_k > 0 and top_k < n else n
    var gap    = 0.0
    var ambig  = False
    if n >= 2:
        gap   = sorted[0].score - sorted[1].score
        ambig = gap < AMBIG_GAP

    var out = String('{"ranked":[')
    for i in range(k):
        if i > 0:
            out += ","
        out += '{"source":"' + sorted[i].source + '",'
        out += '"column":"'  + sorted[i].column + '",'
        out += '"score":'    + _fmt_float(sorted[i].score)       + ','
        out += '"name_sim":' + _fmt_float(sorted[i].name_sim)    + ','
        out += '"token_sim":' + _fmt_float(sorted[i].token_sim)  + ','
        out += '"type_boost":' + _fmt_float(sorted[i].type_boost) + ','
        out += '"prior_boost":' + _fmt_float(sorted[i].prior_boost) + ','
        out += '"confidence_gap":' + _fmt_float(gap if i == 0 else 0.0) + '}'
    out += '],'
    out += '"ambiguous":' + ("true" if ambig else "false") + ','
    out += '"gap":' + _fmt_float(gap) + '}'
    return out


@always_inline
def _type_boost_ids(query_role: UInt8, cand_role: UInt8) -> Float64:
    if query_role == ROLE_OTHER_ID:
        return 0.0
    if cand_role == query_role:
        return 0.15
    if cand_role != ROLE_OTHER_ID:
        return -0.08
    return 0.0


@always_inline
def _prior_boost_ids(query_src: UInt16, cand_src: UInt16, cand_role: UInt8) -> Float64:
    if query_src == SOURCE_UNKNOWN_ID:
        return 0.0
    if cand_src != SOURCE_UNKNOWN_ID and cand_src != query_src:
        return 0.0
    if query_src == SOURCE_POS_ID and cand_role == ROLE_UNIT_ID:
        return 0.10
    if query_src == SOURCE_BACKLOG_ID and cand_role == ROLE_DERIVED_ID:
        return 0.10
    if query_src == SOURCE_INVOICE_ID and cand_role == ROLE_DERIVED_ID:
        return 0.10
    return 0.0


@always_inline
def _dot64_f32(a: List[Float32], b: List[Float32]) -> Float64:
    var dot = Float64(0.0)
    for i in range(len(a)):
        dot += Float64(a[i]) * Float64(b[i])
    return dot


@always_inline
def _cosine_resident(
    qv: List[Float32],
    cv: List[Float32],
    q_ni: Float32,
    c_ni: Float32,
) -> Float64:
    if q_ni == 0.0 or c_ni == 0.0:
        return 0.0
    var raw = _dot64_f32(qv, cv) * Float64(q_ni) * Float64(c_ni)
    if raw > 1.0:
        return 1.0
    if raw < 0.0:
        return 0.0
    return raw


struct ResidentRankSlot(Copyable, Movable):
    var column_id:  UInt32
    var score:      Float64
    var name_sim:   Float64
    var type_boost: Float64

    def __init__(out self):
        self.column_id = 0
        self.score = 0.0
        self.name_sim = 0.0
        self.type_boost = 0.0

    def __copyinit__(out self, copy: Self):
        self.column_id = copy.column_id
        self.score = copy.score
        self.name_sim = copy.name_sim
        self.type_boost = copy.type_boost

    def __moveinit__(out self, var take: Self):
        self.column_id = take.column_id
        self.score = take.score
        self.name_sim = take.name_sim
        self.type_boost = take.type_boost


def _sort_resident_slots(mut slots: List[ResidentRankSlot]):
    var n = len(slots)
    for i in range(1, n):
        var ks  = slots[i].score
        var kid = slots[i].column_id
        var kns = slots[i].name_sim
        var ktb = slots[i].type_boost
        var j = i - 1
        while j >= 0 and slots[j].score < ks:
            var tmp = ResidentRankSlot()
            tmp.column_id = slots[j].column_id
            tmp.score = slots[j].score
            tmp.name_sim = slots[j].name_sim
            tmp.type_boost = slots[j].type_boost
            slots[j + 1] = tmp^
            j -= 1
        var ins = ResidentRankSlot()
        ins.column_id = kid
        ins.score = ks
        ins.name_sim = kns
        ins.type_boost = ktb
        slots[j + 1] = ins^


struct ResidentColumnRankState(Movable):
    var initialized: Bool
    var table: CandidateTable
    var source_names: List[String]
    var column_names: List[String]

    def __init__(out self):
        self.initialized = False
        self.table = CandidateTable()
        self.source_names = List[String]()
        self.column_names = List[String]()

    def _reset(mut self):
        self.initialized = False
        self.table = CandidateTable()
        self.source_names = List[String]()
        self.column_names = List[String]()

    def init_from_json(mut self, raw: String) -> String:
        self._reset()
        var entries_arr = json_get_array(raw, "entries")
        var n_entries = json_array_len(entries_arr)
        if n_entries == 0:
            return '{"status":"error","error":"no entries"}'

        for idx in range(n_entries):
            var entry_json = json_array_get(entries_arr, idx)
            var source_name = json_get_string(entry_json, "source")
            var column_name = json_get_string(entry_json, "column")
            var source_id = json_get_int(entry_json, "source_id", 0)
            var role_id = json_get_int(entry_json, "role_id", 0)
            if len(column_name) == 0:
                continue
            self.table.add_column(
                UInt32(idx),
                UInt16(source_id),
                UInt8(role_id),
                column_name,
            )
            self.source_names.append(source_name)
            self.column_names.append(column_name)
        if self.table.size() == 0:
            return '{"status":"error","error":"no usable entries"}'
        self.initialized = True
        return '{"status":"ok","count":' + String(self.table.size()) + '}'

    def _rank_subset(
        self,
        hint: String,
        query_src: UInt16,
        query_role: UInt8,
        top_k: Int,
        candidate_ids_arr: String,
    ) -> String:
        if not self.initialized:
            return '{"error":"resident column rank not initialized"}'

        var req = build_query(
            hint,
            query_src,
            query_role,
            UInt8(top_k if top_k > 0 and top_k < 255 else 5),
        )
        var ids_len = json_array_len(candidate_ids_arr)
        if ids_len == 0:
            return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"no candidates"}'

        var slots = List[ResidentRankSlot]()
        for i in range(ids_len):
            var raw_id = json_array_get(candidate_ids_arr, i)
            var col_idx = parse_int(raw_id)
            if col_idx < 0 or col_idx >= self.table.size():
                continue

            var c_id = self.table.entries[col_idx].column_id
            var c_src = self.table.entries[col_idx].source_id
            var c_rol = self.table.entries[col_idx].role_id
            var c_ni = self.table.entries[col_idx].norm_inv

            var nsim = _cosine_resident(
                req.query_vec.data,
                self.table.entries[col_idx].vec.data,
                req.query_norm_inv,
                c_ni,
            )
            var tb = _type_boost_ids(query_role, c_rol)
            var pb = _prior_boost_ids(query_src, c_src, c_rol)

            var fs = 0.55 * nsim + tb + pb
            if fs > 1.0:
                fs = 1.0
            elif fs < 0.0:
                fs = 0.0

            var slot = ResidentRankSlot()
            slot.column_id = c_id
            slot.score = fs
            slot.name_sim = nsim
            slot.type_boost = tb + pb
            slots.append(slot^)
        if len(slots) == 0:
            return '{"ranked":[],"ambiguous":false,"gap":0.0}'

        _sort_resident_slots(slots)
        var n = len(slots)
        var k = top_k if top_k > 0 and top_k < n else n
        var gap = 0.0
        var ambig = False
        if n >= 2:
            gap = slots[0].score - slots[1].score
            ambig = gap < AMBIG_GAP

        var out = String('{"ranked":[')
        for i in range(k):
            if i > 0:
                out += ","
            var col_idx = Int(slots[i].column_id)
            out += '{"id":' + String(col_idx) + ','
            out += '"score":' + _fmt_float(slots[i].score) + ','
            out += '"name_sim":' + _fmt_float(slots[i].name_sim) + ','
            out += '"type_boost":' + _fmt_float(slots[i].type_boost) + ','
            out += '"confidence_gap":' + _fmt_float(gap if i == 0 else 0.0) + '}'
        out += '],'
        out += '"ambiguous":' + ("true" if ambig else "false") + ','
        out += '"gap":' + _fmt_float(gap) + '}'
        return out

    def run_query(self, raw: String) -> String:
        var hint = json_get_string(raw, "hint")
        var query_src = json_get_int(raw, "source_id", 0)
        var query_role = json_get_int(raw, "role_id", 0)
        var top_k = json_get_int(raw, "top_k", 5)
        var candidate_ids_arr = json_get_array(raw, "candidate_ids")
        return self._rank_subset(
            hint,
            UInt16(query_src),
            UInt8(query_role),
            top_k,
            candidate_ids_arr,
        )

    def run_batch(self, raw: String) -> String:
        var requests_arr = json_get_array(raw, "requests")
        var n_requests = json_array_len(requests_arr)
        var out = String('{"results":[')
        for i in range(n_requests):
            if i > 0:
                out += ","
            var request_json = json_array_get(requests_arr, i)
            var hint = json_get_string(request_json, "hint")
            var query_src = json_get_int(request_json, "source_id", 0)
            var query_role = json_get_int(request_json, "role_id", 0)
            var top_k = json_get_int(request_json, "top_k", 5)
            var candidate_ids_arr = json_get_array(request_json, "candidate_ids")
            out += self._rank_subset(
                hint,
                UInt16(query_src),
                UInt8(query_role),
                top_k,
                candidate_ids_arr,
            )
        out += ']}'
        return out



# ── Public entry point ─────────────────────────────────────────────────────────

def run_column_rank(raw: String) raises -> String:
    """
    Rank candidate columns against a natural-language hint using vector scoring.

    Returns JSON with top_k ranked candidates, score components, and ambiguity flag.
    """

    # Parse hint words
    var hint_arr  = json_get_array(raw, "hint_words")
    var n_hints   = json_array_len(hint_arr)
    if n_hints == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"no hint_words"}'

    # Build combined hint string and token list
    var hint_joined = String("")
    var hint_toks   = List[String]()
    for i in range(n_hints):
        var hw = to_lower(json_array_get(hint_arr, i))
        # Strip surrounding quotes if the JSON extractor includes them
        var hw_bytes = hw.as_bytes()
        var hw_n     = len(hw)
        var hs = 0
        var he = hw_n
        if hw_n >= 2 and hw_bytes[0] == 34 and hw_bytes[hw_n - 1] == 34:
            hs = 1; he = hw_n - 1
        var clean = _substr(hw, hs, he)
        var toks  = _tokens(clean)
        for j in range(len(toks)):
            hint_toks.append(toks[j])
        if i > 0:
            hint_joined += " "
        hint_joined += clean

    if len(hint_toks) == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"empty hint"}'

    # Pre-compute hint vector once
    var hint_vec = _bigram_vec(hint_joined)

    # Parse context
    var ctx_json    = json_get_object(raw, "context")
    var source_type = json_get_string(ctx_json, "source_type")
    var query_role  = json_get_string(ctx_json, "query_role")

    # Parse candidates
    var cands_arr = json_get_array(raw, "candidates")
    var n_cands   = json_array_len(cands_arr)
    if n_cands == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0,"error":"no candidates"}'

    # Cap candidates
    var n = n_cands if n_cands <= MAX_CANDS else MAX_CANDS

    var top_k = json_get_int(raw, "top_k", 5)

    # Score all candidates
    var results = List[RankResult]()

    for ci in range(n):
        var cand_json  = json_array_get(cands_arr, ci)
        var col_raw    = json_get_string(cand_json, "column")
        var source     = json_get_string(cand_json, "source")
        var role       = json_get_string(cand_json, "role")
        var fill_rate  = json_get_float(cand_json, "fill_rate", 1.0)

        # Skip columns with negligible fill rate
        if fill_rate < 0.02:
            continue

        # Compute scores
        var col_vec   = _bigram_vec(col_raw)
        var name_sim  = _cosine(hint_vec, col_vec)

        var col_toks  = _tokens(col_raw)
        var token_sim = _token_jaccard(hint_toks, col_toks)

        var tb = _role_boost(role, hint_toks, query_role)
        var pb = _prior_boost(source_type, _normalize(col_raw))

        # Weighted combination: 55% vector name sim + 25% token sim + boosts
        var base  = 0.55 * name_sim + 0.25 * token_sim
        var score = base + tb + pb
        if score > 1.0:
            score = 1.0
        if score < 0.0:
            score = 0.0

        results.append(RankResult(
            source      = source,
            column      = col_raw,
            score       = score,
            name_sim    = name_sim,
            token_sim   = token_sim,
            type_boost  = tb,
            prior_boost = pb,
        ))

    if len(results) == 0:
        return '{"ranked":[],"ambiguous":false,"gap":0.0}'

    var sorted = _insertion_sort(results)
    return _build_output(sorted, top_k)
