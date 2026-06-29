from json.parser import (
    json_array_get,
    json_array_len,
    json_get_array,
    json_get_float,
    json_get_string,
)


fn _unquote(s: String) -> String:
    var n = len(s)
    if n < 2:
        return s
    var bytes = s.as_bytes()
    if bytes[0] != UInt8(34) or bytes[n - 1] != UInt8(34):
        return s
    var result = String("")
    var i = 1
    while i < n - 1:
        if bytes[i] == UInt8(92) and i + 1 < n - 1:
            var nxt = bytes[i + 1]
            if nxt == UInt8(34):
                result += '"'
            elif nxt == UInt8(92):
                result += "\\"
            elif nxt == UInt8(110):
                result += "\n"
            elif nxt == UInt8(116):
                result += "\t"
            elif nxt == UInt8(114):
                result += "\r"
            elif nxt == UInt8(47):
                result += "/"
            else:
                result += chr(Int(nxt))
            i += 2
            continue
        result += chr(Int(bytes[i]))
        i += 1
    return result


fn _parse_string_array(obj: String, key: String) -> List[String]:
    var arr = json_get_array(obj, key)
    var count = json_array_len(arr)
    var values = List[String]()
    for index in range(count):
        var value = _unquote(json_array_get(arr, index))
        if len(value) > 0:
            values.append(value)
    return values


fn _contains(values: List[String], target: String) -> Bool:
    for index in range(len(values)):
        if values[index] == target:
            return True
    return False


fn _count_overlap(left: List[String], right: List[String]) -> Int:
    var hits = 0
    for left_index in range(len(left)):
        var token = left[left_index]
        if len(token) == 0:
            continue
        if _contains(right, token):
            hits += 1
    return hits


fn _better_candidate(
    score: Float64,
    rank: Int,
    best_score: Float64,
    best_rank: Int,
) -> Bool:
    if score > best_score:
        return True
    if score < best_score:
        return False
    return rank < best_rank


fn run_repo_classifier(raw: String) raises -> String:
    var top_k = Int(json_get_float(raw, "top_k", 4.0))
    if top_k <= 0:
        top_k = 4

    var languages_arr = json_get_array(raw, "languages")
    var files_arr = json_get_array(raw, "files")
    var n_languages = json_array_len(languages_arr)
    var n_files = json_array_len(files_arr)
    if n_languages <= 0:
        return '{"engine":"mojo","engine_type":"repo_classifier","results":[],"error":"repo_classifier requires non-empty languages"}'
    if n_files <= 0:
        return '{"engine":"mojo","engine_type":"repo_classifier","results":[]}'

    var result = String('{"engine":"mojo","engine_type":"repo_classifier","results":[')
    for file_index in range(n_files):
        if file_index > 0:
            result += ","

        var file_json = json_array_get(files_arr, file_index)
        var path = json_get_string(file_json, "path")
        var basename = json_get_string(file_json, "basename")
        var suffix = json_get_string(file_json, "suffix")
        var path_tokens = _parse_string_array(file_json, "path_tokens")
        var content_tokens = _parse_string_array(file_json, "content_tokens")

        var candidate_languages = List[String]()
        var candidate_scores = List[Float64]()
        var candidate_ranks = List[Int]()
        var candidate_suffix_matches = List[Int]()
        var candidate_basename_matches = List[Int]()
        var candidate_path_hits = List[Int]()
        var candidate_content_hits = List[Int]()

        for language_index in range(n_languages):
            var language_json = json_array_get(languages_arr, language_index)
            var language = json_get_string(language_json, "language")
            var rank = Int(json_get_float(language_json, "rank", 0.0))
            var language_suffixes = _parse_string_array(language_json, "suffixes")
            var language_basenames = _parse_string_array(language_json, "basenames")
            var language_tokens = _parse_string_array(language_json, "tokens")

            var suffix_match = False
            if len(suffix) > 0 and _contains(language_suffixes, suffix):
                suffix_match = True
            var basename_match = False
            if len(basename) > 0 and _contains(language_basenames, basename):
                basename_match = True

            var path_token_hits = _count_overlap(language_tokens, path_tokens)
            var content_token_hits = _count_overlap(language_tokens, content_tokens)

            var score: Float64 = 0.0
            if suffix_match:
                score += 20.0
            if basename_match:
                score += 16.0
            score += Float64(path_token_hits) * 4.0
            score += Float64(content_token_hits) * 2.0

            if score <= 0.0:
                continue

            candidate_languages.append(language)
            candidate_scores.append(score)
            candidate_ranks.append(rank)
            candidate_suffix_matches.append(1 if suffix_match else 0)
            candidate_basename_matches.append(1 if basename_match else 0)
            candidate_path_hits.append(path_token_hits)
            candidate_content_hits.append(content_token_hits)
        var top_languages = List[String]()
        var top_scores = List[Float64]()
        var top_suffix_matches = List[Int]()
        var top_basename_matches = List[Int]()
        var top_path_hits = List[Int]()
        var top_content_hits = List[Int]()
        var used = List[Int]()
        for index in range(len(candidate_languages)):
            used.append(0)

        var limit = top_k
        if limit > len(candidate_languages):
            limit = len(candidate_languages)
        for top_index in range(limit):
            var best_index = -1
            var best_score: Float64 = -1.0
            var best_rank = 2147483647
            for candidate_index in range(len(candidate_languages)):
                if used[candidate_index] != 0:
                    continue
                if _better_candidate(
                    candidate_scores[candidate_index],
                    candidate_ranks[candidate_index],
                    best_score,
                    best_rank,
                ):
                    best_index = candidate_index
                    best_score = candidate_scores[candidate_index]
                    best_rank = candidate_ranks[candidate_index]
            if best_index < 0:
                break
            used[best_index] = 1
            top_languages.append(candidate_languages[best_index])
            top_scores.append(candidate_scores[best_index])
            top_suffix_matches.append(candidate_suffix_matches[best_index])
            top_basename_matches.append(candidate_basename_matches[best_index])
            top_path_hits.append(candidate_path_hits[best_index])
            top_content_hits.append(candidate_content_hits[best_index])

        var primary_language = String("unknown")
        var primary_score: Float64 = 0.0
        if len(top_languages) > 0:
            primary_language = top_languages[0]
            primary_score = top_scores[0]

        result += '{"path":"'
        result += path
        result += '","primary_language":"'
        result += primary_language
        result += '","primary_score":'
        result += String(primary_score)
        result += ',"matches":['
        for match_index in range(len(top_languages)):
            if match_index > 0:
                result += ","
            result += '{"language":"'
            result += top_languages[match_index]
            result += '","score":'
            result += String(top_scores[match_index])
            result += ',"suffix_match":'
            result += "true" if top_suffix_matches[match_index] != 0 else "false"
            result += ',"basename_match":'
            result += "true" if top_basename_matches[match_index] != 0 else "false"
            result += ',"path_token_hits":'
            result += String(top_path_hits[match_index])
            result += ',"content_token_hits":'
            result += String(top_content_hits[match_index])
            result += "}"
        result += "]}"
    result += "]}"
    return result
