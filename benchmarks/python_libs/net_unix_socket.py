"""Python equivalent of mojo/engine/net.unix_socket.mojo (auto-generated)."""
import math
import random as _rng

try:
    from memory import UnsafePointer
except Exception:
    pass
try:
    from memory import memset
except Exception:
    pass
try:
    from std.python import Python
except Exception:
    pass
try:
    from std.python import PythonObject
except Exception:
    pass

AF_UNIX = 1
SOCK_STREAM = 1

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

def _get_registry():
    builtins = Python.import_module("builtins")
    if not Bool(builtins.hasattr(builtins, "_mojo_sock_registry")):
        builtins._mojo_sock_registry = Python.evaluate("dict()")
    return builtins._mojo_sock_registry



def _store_py_socket(fd, sock):
    reg = _get_registry()
    reg[fd] = sock



def _get_py_socket(fd):
    reg = _get_registry()
    return reg[fd]



def _py_int(obj):
    return int(py=obj)



def _py_len(obj):
    b = Python.import_module("builtins")
    return int(py=b.len(obj))



def encode_u32_be(value):
    result = []
    result.append(int((value >> 24) & 0xFF))
    result.append(int((value >> 16) & 0xFF))
    result.append(int((value >> 8) & 0xFF))
    result.append(int(value & 0xFF))
    return result



def decode_u32_be(data):
    return (
        (int(data[0]) << 24)
        | (int(data[1]) << 16)
        | (int(data[2]) << 8)
        | int(data[3])
    )



def encode_frame(payload):
    payload_bytes = payload.encode('utf-8')
    payload_len = len(payload_bytes)

    if payload_len > 0 and payload_bytes[payload_len - 1] == 0:
        payload_len -= 1

    header = encode_u32_be(payload_len)
    frame = []
    for i in range(4):
        frame.append(header[i])
    for i in range(payload_len):
        frame.append(payload_bytes[i])
    return frame



def decode_frame_length(header):
    return decode_u32_be(header)













def libc_socket_unix():
    try:
        sock_m = Python.import_module("socket")
        sock = sock_m.socket(sock_m.AF_UNIX, sock_m.SOCK_STREAM)
        fd = _py_int(sock.fileno())
        _store_py_socket(fd, sock)
        return fd
    except:
        return -1



def libc_bind_unix(fd, path):
    sock = _get_py_socket(fd)
    sock.bind(path)



def libc_listen(fd, backlog):
    sock = _get_py_socket(fd)
    sock.listen(backlog)



def libc_accept(fd):
    try:
        sock = _get_py_socket(fd)
        result = sock.accept()
        conn = result[0]
        new_fd = _py_int(conn.fileno())
        _store_py_socket(new_fd, conn)
        return new_fd
    except:
        return -1



def libc_close(fd):
    try:
        sock = _get_py_socket(fd)
        sock.close()
    except:
        pass



def libc_unlink(path):
    try:
        os_m = Python.import_module("os")
        os_m.unlink(path)
    except:
        pass



def libc_path_exists(path):
    try:
        os_path = Python.import_module("os.path")
        return Bool(os_path.exists(path))
    except:
        return False



def recv_exact(fd, n):
    result = []
    try:
        sock = _get_py_socket(fd)
        total_read = 0
        while total_read < n:
            data = sock.recv(n - total_read)
            chunk_len = _py_len(data)
            if chunk_len <= 0:
                return []
            for i in range(chunk_len):
                result.append(int(_py_int(data[i])))
            total_read += chunk_len
    except:
        return []
    return result



def recv_frame(fd):

    header = recv_exact(fd, 4)
    if len(header) < 4:
        return str("")

    payload_len = decode_u32_be(header)
    if payload_len == 0:
        return str("")


    payload_bytes = recv_exact(fd, payload_len)
    if len(payload_bytes) < payload_len:
        return str("")


    chars = []
    for i in range(payload_len):
        chars.append(payload_bytes[i])
    chars.append(0)  # null terminator
    return str(chars)



def send_frame(fd, payload):
    frame = encode_frame(payload)
    frame_len = len(frame)
    sock = _get_py_socket(fd)


    ba = Python.import_module("builtins").bytearray(frame_len)
    for i in range(frame_len):
        ba[i] = int(frame[i])

    total_sent = 0
    frame_bytes = Python.import_module("builtins").bytes(ba)
    while total_sent < frame_len:
        sent = _py_int(sock.send(frame_bytes[total_sent:]))
        if sent <= 0:
            raise Error("send_frame: send() failed")
        total_sent += sent
