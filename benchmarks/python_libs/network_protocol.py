"""Python equivalent of mojo/engine/network_protocol.mojo (auto-generated)."""
import math
import random as _rng

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def json_get_string(raw, key, default=''):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return str(v) if v is not None else default
    except Exception: return default
def json_get_float(raw, key, default=0.0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return float(v) if v is not None else default
    except Exception: return default
def json_get_int(raw, key, default=0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return int(v) if v is not None else default
    except Exception: return default
def json_get_bool(raw, key, default=False):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return bool(v) if v is not None else default
    except Exception: return default
def json_get_object(raw, key, default='{}'):
    try:
        import json as _j; v = _j.loads(raw).get(key, {})
        return _j.dumps(v) if isinstance(v, dict) else default
    except Exception: return default
def json_get_array(raw, key, default='[]'):
    try:
        import json as _j; v = _j.loads(raw).get(key, [])
        return _j.dumps(v) if isinstance(v, list) else default
    except Exception: return default
def json_array_len(arr):
    try:
        import json as _j; return len(_j.loads(arr))
    except Exception: return 0
def json_array_get(arr, index):
    try:
        import json as _j; v = _j.loads(arr)
        return _j.dumps(v[index]) if index < len(v) else ''
    except Exception: return ''
def to_lower(s): return s.lower()
def contains_keyword(text, keyword): return keyword.lower() in text.lower()
def detect_polarity(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1
    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1
    return 0
def detect_unit_hint(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'
    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'
    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'
    return ''
def infer_distribution_from_values(values): return ('normal', '{}')
def map_fields(raw): return []
def build_objective_function(mappings): return ''
def build_variables_json(mappings): return '[]'
class FieldMapping: pass
def dice_coefficient(a, b):
    if not a or not b: return 0.0
    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))
    ag, bg = _bg(a), _bg(b)
    if not ag or not bg: return 0.0
    return 2.0 * len(ag & bg) / (len(ag) + len(bg))
def edit_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    m, n = len(a), len(b); dp = list(range(n+1))
    for i in range(1, m+1):
        prev, dp[0] = dp[0], i
        for j in range(1, n+1):
            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t
    return 1.0 - dp[n] / max(m, n)
def jaccard_index(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)
def to_set(lst): return list(set(lst))
def parse_float64(s, default=0.0):
    try: return float(s)
    except Exception: return default
def parse_int(s, default=0):
    try: return int(float(s))
    except Exception: return default
DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3
DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1
def infer_from_samples(values): return DIM_UNKNOWN
def propagate(a, b, op): return DIM_UNKNOWN
def role_for_dimension(dim): return 'metric'
class Python:
    @staticmethod
    def import_module(name):
        import importlib; return importlib.import_module(name)

def _extract_substring(s, start, end):
    sb = s.encode('utf-8')
    result = str("")
    for i in range(start, end):
        result += chr(int(sb[i]))
    return result



def http_status_text(code):
    if code == 100:
        return "Continue"
    if code == 101:
        return "Switching Protocols"
    if code == 200:
        return "OK"
    if code == 201:
        return "Created"
    if code == 202:
        return "Accepted"
    if code == 204:
        return "No Content"
    if code == 301:
        return "Moved Permanently"
    if code == 302:
        return "Found"
    if code == 304:
        return "Not Modified"
    if code == 307:
        return "Temporary Redirect"
    if code == 308:
        return "Permanent Redirect"
    if code == 400:
        return "Bad Request"
    if code == 401:
        return "Unauthorized"
    if code == 403:
        return "Forbidden"
    if code == 404:
        return "Not Found"
    if code == 405:
        return "Method Not Allowed"
    if code == 408:
        return "Request Timeout"
    if code == 409:
        return "Conflict"
    if code == 413:
        return "Payload Too Large"
    if code == 415:
        return "Unsupported Media Type"
    if code == 422:
        return "Unprocessable Entity"
    if code == 429:
        return "Too Many Requests"
    if code == 500:
        return "Internal Server Error"
    if code == 501:
        return "Not Implemented"
    if code == 502:
        return "Bad Gateway"
    if code == 503:
        return "Service Unavailable"
    if code == 504:
        return "Gateway Timeout"
    return "Unknown"






def is_success(code):
    return code >= 200 and code <= 299



def is_redirect(code):
    return code >= 300 and code <= 399



def is_client_error(code):
    return code >= 400 and code <= 499



def is_server_error(code):
    return code >= 500 and code <= 599






def mime_type(extension):
    if extension == "html" or extension == "htm":
        return "text/html"
    if extension == "css":
        return "text/css"
    if extension == "csv":
        return "text/csv"
    if extension == "txt":
        return "text/plain"
    if extension == "xml":
        return "text/xml"
    if extension == "js":
        return "text/javascript"
    if extension == "md":
        return "text/markdown"
    if extension == "json":
        return "application/json"
    if extension == "pdf":
        return "application/pdf"
    if extension == "zip":
        return "application/zip"
    if extension == "gz" or extension == "gzip":
        return "application/gzip"
    if extension == "tar":
        return "application/x-tar"
    if extension == "wasm":
        return "application/wasm"
    if extension == "yaml" or extension == "yml":
        return "application/x-yaml"
    if extension == "xls" or extension == "xlsx":
        return "application/vnd.ms-excel"
    if extension == "png":
        return "image/png"
    if extension == "jpg" or extension == "jpeg":
        return "image/jpeg"
    if extension == "gif":
        return "image/gif"
    if extension == "svg":
        return "image/svg+xml"
    if extension == "webp":
        return "image/webp"
    if extension == "ico":
        return "image/x-icon"
    if extension == "mp3":
        return "audio/mpeg"
    if extension == "mp4":
        return "video/mp4"
    if extension == "wav":
        return "audio/wav"
    return "application/octet-stream"






def parse_content_type(header):
    h_bytes = header.encode('utf-8')
    n = len(h_bytes)


    semi_pos = -1
    for i in range(n):
        if int(h_bytes[i]) == ord(";"):
            semi_pos = i
            break

    end_pos = n
    if semi_pos >= 0:
        end_pos = semi_pos


    while end_pos > 0 and int(h_bytes[end_pos - 1]) == ord(" "):
        end_pos -= 1


    start_pos = 0
    while start_pos < end_pos and int(h_bytes[start_pos]) == ord(" "):
        start_pos += 1

    result = str("")
    for i in range(start_pos, end_pos):
        result += chr(int(h_bytes[i]))
    return result



def is_json_type(mime):
    if mime == "application/json":
        return True

    b = mime.encode('utf-8')
    n = len(b)
    if n >= 5:
        if (
            int(b[n - 5]) == ord("+")
            and int(b[n - 4]) == ord("j")
            and int(b[n - 3]) == ord("s")
            and int(b[n - 2]) == ord("o")
            and int(b[n - 1]) == ord("n")
        ):
            return True
    return False



def is_text_type(mime):
    b = mime.encode('utf-8')
    if len(b) < 5:
        return False
    return (
        int(b[0]) == ord("t")
        and int(b[1]) == ord("e")
        and int(b[2]) == ord("x")
        and int(b[3]) == ord("t")
        and int(b[4]) == ord("/")
    )






def build_query_string(keys, values):
    n = len(keys)
    if len(values) < n:
        n = len(values)
    result = str("")
    for i in range(n):
        if i > 0:
            result += "&"
        result += keys[i] + "=" + values[i]
    return result



def parse_query_string(query):
    result = []
    if len(query) == 0:
        return result

    q_bytes = query.encode('utf-8')
    n = len(q_bytes)


    starts = []
    ends = []
    seg_start = 0
    for i in range(n):
        if int(q_bytes[i]) == ord("&"):
            starts.append(seg_start)
            ends.append(i)
            seg_start = i + 1
    starts.append(seg_start)
    ends.append(n)


    for pi in range(len(starts)):
        ps = starts[pi]
        pe = ends[pi]

        eq_pos = -1
        for k in range(ps, pe):
            if int(q_bytes[k]) == ord("="):
                eq_pos = k
                break
        kv = []
        if eq_pos >= 0:
            kv.append(_extract_substring(query, ps, eq_pos))
            kv.append(_extract_substring(query, eq_pos + 1, pe))
        else:
            kv.append(_extract_substring(query, ps, pe))
            kv.append(str(""))
        result.append(kv)

    return result
