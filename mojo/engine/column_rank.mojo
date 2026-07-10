"""
column_rank.mojo — lightweight resident ranking support for the planner.
"""
from std.python import Python, PythonObject

from field_mapper import to_lower
from python_bridge import fast_f64, fast_int, py_str
from string_distance import dice_coefficient, edit_similarity


struct ResidentColumnRankEntry(Copyable, Movable):
    var id: Int
    var source: String
    var column: String
    var source_id: Int
    var role_id: Int
    var normalized: String

    fn __init__(
        out self,
        id: Int = -1,
        source: String = "",
        column: String = "",
        source_id: Int = 0,
        role_id: Int = 0,
    ):
        self.id = id
        self.source = source
        self.column = column
        self.source_id = source_id
        self.role_id = role_id
        self.normalized = _normalize(column)

    fn copy(self) -> ResidentColumnRankEntry:
        return ResidentColumnRankEntry(self.id, self.source, self.column, self.source_id, self.role_id)


struct RankedEntry(Copyable, Movable):
    var id: Int
    var source: String
    var column: String
    var score: Float64
    var name_sim: Float64
    var type_boost: Float64
    var confidence_gap: Float64

    fn __init__(
        out self,
        id: Int = -1,
        source: String = "",
        column: String = "",
        score: Float64 = 0.0,
        name_sim: Float64 = 0.0,
        type_boost: Float64 = 0.0,
        confidence_gap: Float64 = 0.0,
    ):
        self.id = id
        self.source = source
        self.column = column
        self.score = score
        self.name_sim = name_sim
        self.type_boost = type_boost
        self.confidence_gap = confidence_gap

    fn copy(self) -> RankedEntry:
        return RankedEntry(
            self.id,
            self.source,
            self.column,
            self.score,
            self.name_sim,
            self.type_boost,
            self.confidence_gap,
        )


fn _normalize(text: String) -> String:
    var lower = to_lower(text)
    var out = String("")
    var pending_space = False
    var bytes = lower.as_bytes()
    for i in range(len(lower)):
        var c = bytes[i]
        var is_alpha = (c >= UInt8(97) and c <= UInt8(122))
        var is_digit = c >= UInt8(48) and c <= UInt8(57)
        if is_alpha or is_digit:
            if pending_space and len(out) > 0:
                out += " "
            out += chr(Int(c))
            pending_space = False
        else:
            pending_space = True
    return out


fn _token_overlap_boost(hint: String, candidate: String) -> Float64:
    var hint_norm = _normalize(hint)
    if len(hint_norm) == 0:
        return 0.0
    var bytes = hint_norm.as_bytes()
    var token = String("")
    var matched = 0
    var total = 0
    for i in range(len(hint_norm) + 1):
        if i == len(hint_norm) or bytes[i] == UInt8(32):
            if len(token) > 0:
                total += 1
                if candidate.find(token) >= 0:
                    matched += 1
                token = ""
            continue
        token += chr(Int(bytes[i]))
    if total == 0:
        return 0.0
    return 0.08 * Float64(matched) / Float64(total)


fn _role_boost(query_role_id: Int, candidate_role_id: Int) -> Float64:
    if query_role_id <= 0 or candidate_role_id <= 0:
        return 0.0
    if query_role_id == candidate_role_id:
        return 0.12
    return -0.04


fn _source_boost(query_source_id: Int, candidate_source_id: Int) -> Float64:
    if query_source_id <= 0 or candidate_source_id <= 0:
        return 0.0
    if query_source_id == candidate_source_id:
        return 0.08
    return -0.02


fn _candidate_score(
    hint: String,
    query_source_id: Int,
    query_role_id: Int,
    entry: ResidentColumnRankEntry,
) -> RankedEntry:
    var hint_norm = _normalize(hint)
    var name_sim = edit_similarity(hint_norm, entry.normalized)
    var dice = dice_coefficient(hint_norm, entry.normalized)
    if dice > name_sim:
        name_sim = dice
    var type_boost = _role_boost(query_role_id, entry.role_id) + _source_boost(query_source_id, entry.source_id)
    var score = 0.78 * name_sim + type_boost + _token_overlap_boost(hint, entry.normalized)
    if score < 0.0:
        score = 0.0
    elif score > 1.0:
        score = 1.0
    return RankedEntry(entry.id, entry.source, entry.column, score, name_sim, type_boost, 0.0)


fn _sort_ranked(mut ranked: List[RankedEntry]):
    for i in range(1, len(ranked)):
        var key = ranked[i].copy()
        var j = i - 1
        while j >= 0 and ranked[j].score < key.score:
            ranked[j + 1] = ranked[j].copy()
            j -= 1
        ranked[j + 1] = key.copy()
    if len(ranked) > 0:
        var top_gap = ranked[0].score - (ranked[1].score if len(ranked) > 1 else 0.0)
        ranked[0].confidence_gap = top_gap


fn _ranked_json(ranked: List[RankedEntry], top_k: Int) raises -> String:
    var json_m = Python.import_module("json")
    var rows = Python.evaluate("[]")
    var limit = top_k
    if limit > len(ranked):
        limit = len(ranked)
    for i in range(limit):
        var row = Python.evaluate("{}")
        row["id"] = ranked[i].id
        row["source"] = ranked[i].source
        row["column"] = ranked[i].column
        row["score"] = ranked[i].score
        row["name_sim"] = ranked[i].name_sim
        row["type_boost"] = ranked[i].type_boost
        row["confidence_gap"] = ranked[i].confidence_gap
        rows.append(row)
    return py_str(json_m.dumps(rows))


struct ResidentColumnRankState(Copyable, Movable):
    var entries: List[ResidentColumnRankEntry]

    fn __init__(out self):
        self.entries = List[ResidentColumnRankEntry]()

    fn copy(self) -> ResidentColumnRankState:
        var out = ResidentColumnRankState()
        out.entries = self.entries.copy()
        return out^

    fn init_from_json(mut self, raw: String) raises -> String:
        var json_m = Python.import_module("json")
        var builtins = Python.import_module("builtins")
        var payload = json_m.loads(raw)
        var entries_py = payload.get("entries", Python.evaluate("[]"))
        self.entries = List[ResidentColumnRankEntry]()
        for i in range(fast_int(builtins.len(entries_py))):
            var entry = entries_py[i]
            self.entries.append(
                ResidentColumnRankEntry(
                    fast_int(entry.get("id", i)),
                    py_str(entry.get("source", "")),
                    py_str(entry.get("column", "")),
                    fast_int(entry.get("source_id", 0)),
                    fast_int(entry.get("role_id", 0)),
                )
            )
        return '{"status":"ok","count":' + String(len(self.entries)) + "}"

    fn _query_ranked(self, query: PythonObject) raises -> List[RankedEntry]:
        var builtins = Python.import_module("builtins")
        var candidate_ids = query.get("candidate_ids", Python.evaluate("[]"))
        var top_k = fast_int(query.get("top_k", 5))
        var use_all = fast_int(builtins.len(candidate_ids)) == 0
        var hint = py_str(query.get("hint", ""))
        var query_source_id = fast_int(query.get("source_id", 0))
        var query_role_id = fast_int(query.get("role_id", 0))
        var ranked = List[RankedEntry]()
        for i in range(len(self.entries)):
            if not use_all:
                var include_entry = False
                for j in range(fast_int(builtins.len(candidate_ids))):
                    if fast_int(candidate_ids[j]) == self.entries[i].id:
                        include_entry = True
                        break
                if not include_entry:
                    continue
            ranked.append(_candidate_score(hint, query_source_id, query_role_id, self.entries[i]))
        _sort_ranked(ranked)
        if top_k < len(ranked):
            var trimmed = List[RankedEntry]()
            for i in range(top_k):
                trimmed.append(ranked[i].copy())
            return trimmed^
        return ranked^

    fn run_query(self, raw: String) raises -> String:
        var json_m = Python.import_module("json")
        var payload = json_m.loads(raw)
        var ranked = self._query_ranked(payload)
        return '{"ranked":' + _ranked_json(ranked, len(ranked)) + ',"ambiguous":false,"gap":' + String(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"

    fn run_batch(self, raw: String) raises -> String:
        var json_m = Python.import_module("json")
        var builtins = Python.import_module("builtins")
        var payload = json_m.loads(raw)
        var requests = payload.get("requests", Python.evaluate("[]"))
        var results_json = String("[")
        for i in range(fast_int(builtins.len(requests))):
            var ranked = self._query_ranked(requests[i])
            if i > 0:
                results_json += ","
            results_json += '{"ranked":' + _ranked_json(ranked, len(ranked)) + ',"ambiguous":false,"gap":' + String(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"
        results_json += "]"
        return '{"results":' + results_json + "}"


def run_column_rank(raw: String) raises -> String:
    var json_m = Python.import_module("json")
    var builtins = Python.import_module("builtins")
    var payload = Python.evaluate("{}")
    try:
        payload = json_m.loads(raw)
    except:
        return '{"ranked":[],"ambiguous":false,"gap":0.0}'
    var hint = py_str(payload.get("hint", ""))
    if len(hint) == 0:
        var hint_words = payload.get("hint_words", Python.evaluate("[]"))
        for i in range(fast_int(builtins.len(hint_words))):
            if i > 0:
                hint += " "
            hint += py_str(hint_words[i])
    var candidates = payload.get("candidates", Python.evaluate("[]"))
    var top_k = fast_int(payload.get("top_k", 5))
    var context = payload.get("context", Python.evaluate("{}"))
    var query_source_id = 0
    var query_role_id = 0
    var ranked = List[RankedEntry]()
    for i in range(fast_int(builtins.len(candidates))):
        var candidate = candidates[i]
        var entry = ResidentColumnRankEntry(
            i,
            py_str(candidate.get("source", "")),
            py_str(candidate.get("column", "")),
            query_source_id,
            query_role_id,
        )
        ranked.append(_candidate_score(hint, query_source_id, query_role_id, entry))
    _sort_ranked(ranked)
    return '{"ranked":' + _ranked_json(ranked, top_k) + ',"ambiguous":false,"gap":' + String(ranked[0].confidence_gap if len(ranked) > 0 else 0.0) + "}"
