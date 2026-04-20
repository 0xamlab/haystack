"""
toml_parser.mojo — Simple TOML parser for config files. Zero Python imports.

Covers the config-file subset of TOML:
  - [section] headers
  - [section.subsection] nested headers
  - key = "string value"
  - key = 42 (integers)
  - key = 3.14 (floats)
  - key = true/false (booleans)
  - key = [1, 2, 3] (simple arrays)
  - # comments

Public API:
  TomlDoc               — parsed document with node pool and root index
  toml_parse()          — parse TOML string to tree
  toml_get_string()     — dot-notation string lookup
  toml_get_int()        — dot-notation int lookup with default
  toml_get_float()      — dot-notation float lookup with default
  toml_get_bool()       — dot-notation bool lookup with default
"""


# ── Node types ───────────────────────────────────────────────────────────────

comptime _TOML_SCALAR = 0
comptime _TOML_MAP = 1
comptime _TOML_LIST = 2


# ── TomlNode struct ──────────────────────────────────────────────────────────


struct TomlNode(Copyable, Movable):
    """A TOML tree node. Can be a scalar, map, or list."""
    var kind: Int           # _TOML_SCALAR, _TOML_MAP, _TOML_LIST
    var scalar: String      # value if scalar

    # Map: parallel lists of keys and child node indices
    var map_keys: List[String]
    var map_vals: List[Int]

    # List: child node indices
    var list_vals: List[Int]

    fn __init__(out self):
        self.kind = _TOML_SCALAR
        self.scalar = String("")
        self.map_keys = List[String]()
        self.map_vals = List[Int]()
        self.list_vals = List[Int]()

    fn __init__(out self, kind: Int, scalar: String):
        self.kind = kind
        self.scalar = scalar
        self.map_keys = List[String]()
        self.map_vals = List[Int]()
        self.list_vals = List[Int]()

    fn __copyinit__(out self, copy: Self):
        self.kind = copy.kind
        self.scalar = copy.scalar
        self.map_keys = copy.map_keys.copy()
        self.map_vals = copy.map_vals.copy()
        self.list_vals = copy.list_vals.copy()


# ── Node pool ────────────────────────────────────────────────────────────────


struct _TomlPool(Copyable, Movable):
    """Flat storage for TOML nodes. Nodes reference children by index."""
    var nodes: List[TomlNode]

    fn __init__(out self):
        self.nodes = List[TomlNode]()

    fn __copyinit__(out self, copy: Self):
        self.nodes = copy.nodes.copy()

    fn add_scalar(mut self, value: String) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_SCALAR, value))
        return idx

    fn add_map(mut self) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_MAP, String("")))
        return idx

    fn add_list(mut self) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(TomlNode(_TOML_LIST, String("")))
        return idx

    fn map_set(mut self, map_idx: Int, key: String, val_idx: Int):
        """Set key in a map node. Overwrites if key already exists."""
        for i in range(len(self.nodes[map_idx].map_keys)):
            if self.nodes[map_idx].map_keys[i] == key:
                self.nodes[map_idx].map_vals[i] = val_idx
                return
        self.nodes[map_idx].map_keys.append(key)
        self.nodes[map_idx].map_vals.append(val_idx)

    fn map_get(self, map_idx: Int, key: String) -> Int:
        """Get a child index from a map node. Returns -1 if not found."""
        for i in range(len(self.nodes[map_idx].map_keys)):
            if self.nodes[map_idx].map_keys[i] == key:
                return self.nodes[map_idx].map_vals[i]
        return -1

    fn ensure_sub_map(mut self, parent_idx: Int, key: String) -> Int:
        """Get or create a sub-map under parent for the given key."""
        var existing = self.map_get(parent_idx, key)
        if existing >= 0 and self.nodes[existing].kind == _TOML_MAP:
            return existing
        var sub = self.add_map()
        self.map_set(parent_idx, key, sub)
        return sub


# ── Internal helpers ─────────────────────────────────────────────────────────


fn _toml_strip(s: String) -> String:
    """Strip leading and trailing whitespace."""
    var bs = s.as_bytes()
    var n = len(s)
    var start = 0
    while start < n:
        var c = Int(bs[start])
        if c != 32 and c != 9 and c != 10 and c != 13:
            break
        start += 1
    var end = n
    while end > start:
        var c = Int(bs[end - 1])
        if c != 32 and c != 9 and c != 10 and c != 13:
            break
        end -= 1
    var result = String("")
    for i in range(start, end):
        result += chr(Int(bs[i]))
    return result


fn _toml_substring(s: String, start: Int, end: Int) -> String:
    """Extract substring s[start:end]."""
    var bs = s.as_bytes()
    var result = String("")
    var e = min(end, len(s))
    for i in range(start, e):
        result += chr(Int(bs[i]))
    return result


fn _toml_split_lines(content: String) -> List[String]:
    """Split string by newline."""
    var lines = List[String]()
    var bs = content.as_bytes()
    var n = len(content)
    var start = 0
    for i in range(n):
        if Int(bs[i]) == 10:  # \n
            var line = String("")
            for j in range(start, i):
                line += chr(Int(bs[j]))
            lines.append(line)
            start = i + 1
    if start <= n:
        var line = String("")
        for j in range(start, n):
            line += chr(Int(bs[j]))
        lines.append(line)
    return lines^


fn _toml_starts_with(s: String, prefix: String) -> Bool:
    """Check if s starts with prefix."""
    if len(prefix) > len(s):
        return False
    var sbs = s.as_bytes()
    var pbs = prefix.as_bytes()
    for i in range(len(prefix)):
        if sbs[i] != pbs[i]:
            return False
    return True


fn _toml_ends_with(s: String, suffix: String) -> Bool:
    """Check if s ends with suffix."""
    if len(suffix) > len(s):
        return False
    var sbs = s.as_bytes()
    var sufs = suffix.as_bytes()
    var offset = len(s) - len(suffix)
    for i in range(len(suffix)):
        if sbs[offset + i] != sufs[i]:
            return False
    return True


fn _toml_find_char(s: String, c: Int) -> Int:
    """Find first occurrence of character. Returns -1 if not found."""
    var bs = s.as_bytes()
    for i in range(len(s)):
        if Int(bs[i]) == c:
            return i
    return -1


fn _toml_split_dot(path: String) -> List[String]:
    """Split a dot-notation path into segments."""
    var parts = List[String]()
    var bs = path.as_bytes()
    var n = len(path)
    var start = 0
    for i in range(n):
        if Int(bs[i]) == 46:  # '.'
            parts.append(_toml_substring(path, start, i))
            start = i + 1
    parts.append(_toml_substring(path, start, n))
    return parts^


fn _toml_unquote(s: String) -> String:
    """Remove surrounding quotes if present."""
    var n = len(s)
    if n < 2:
        return s
    var bs = s.as_bytes()
    var first = Int(bs[0])
    var last = Int(bs[n - 1])
    if (first == 34 and last == 34) or (first == 39 and last == 39):
        return _toml_substring(s, 1, n - 1)
    return s


fn _toml_is_digit(c: Int) -> Bool:
    """Check if char code is a digit."""
    return c >= 48 and c <= 57


fn _toml_parse_value(mut pool: _TomlPool, raw: String) -> Int:
    """Parse a TOML value string and add to pool. Returns node index."""
    var val = _toml_strip(raw)
    var vlen = len(val)

    if vlen == 0:
        return pool.add_scalar(String(""))

    var vbs = val.as_bytes()
    var first = Int(vbs[0])

    # String: starts with " or '
    if first == 34 or first == 39:
        return pool.add_scalar(_toml_unquote(val))

    # Boolean
    if val == "true" or val == "True":
        return pool.add_scalar(String("true"))
    if val == "false" or val == "False":
        return pool.add_scalar(String("false"))

    # Array: [...]
    if first == 91:  # '['
        return _toml_parse_array(pool, val)

    # Number (int or float) — just store as scalar string
    return pool.add_scalar(val)


fn _toml_parse_array(mut pool: _TomlPool, raw: String) -> Int:
    """Parse a TOML array like [1, 2, 3] or ["a", "b"]. Returns list node index."""
    var list_idx = pool.add_list()
    # Strip surrounding brackets
    var inner = _toml_strip(_toml_substring(raw, 1, len(raw) - 1))
    if len(inner) == 0:
        return list_idx

    # Simple comma split (no nested arrays support needed for config subset)
    var bs = inner.as_bytes()
    var n = len(inner)
    var start = 0
    var in_string = False
    var quote_char = 0
    for i in range(n):
        var c = Int(bs[i])
        if in_string:
            if c == quote_char:
                in_string = False
        else:
            if c == 34 or c == 39:
                in_string = True
                quote_char = c
            elif c == 44:  # ','
                var element = _toml_strip(_toml_substring(inner, start, i))
                if len(element) > 0:
                    var el_idx = _toml_parse_value(pool, element)
                    pool.nodes[list_idx].list_vals.append(el_idx)
                start = i + 1
    # Last element
    var last = _toml_strip(_toml_substring(inner, start, n))
    if len(last) > 0:
        var el_idx = _toml_parse_value(pool, last)
        pool.nodes[list_idx].list_vals.append(el_idx)

    return list_idx


# ── TomlDoc ──────────────────────────────────────────────────────────────────


struct TomlDoc(Copyable, Movable):
    """A parsed TOML document containing the node pool and root index."""
    var pool: _TomlPool
    var root: Int

    fn __init__(out self):
        self.pool = _TomlPool()
        self.root = 0

    fn __init__(out self, pool: _TomlPool, root: Int):
        self.pool = pool.copy()
        self.root = root

    fn __copyinit__(out self, copy: Self):
        self.pool = copy.pool.copy()
        self.root = copy.root


# ── Public API: toml_parse ───────────────────────────────────────────────────


fn toml_parse(content: String) -> TomlDoc:
    """Parse TOML content string into a TomlDoc tree.

    Supports: [section], [section.sub], key = value, # comments.
    """
    var pool = _TomlPool()
    var root = pool.add_map()
    var lines = _toml_split_lines(content)
    var current_section = root  # current section node index

    for li in range(len(lines)):
        var raw_line = lines[li]
        var line = _toml_strip(raw_line)

        # Skip empty lines and comments
        if len(line) == 0:
            continue
        var lbs = line.as_bytes()
        if Int(lbs[0]) == 35:  # '#'
            continue

        # Strip inline comments (# preceded by space, outside strings)
        var effective = line
        var in_str = False
        var str_char = 0
        var ebs = effective.as_bytes()
        for ci in range(len(effective)):
            var cc = Int(ebs[ci])
            if in_str:
                if cc == str_char:
                    in_str = False
            else:
                if cc == 34 or cc == 39:
                    in_str = True
                    str_char = cc
                elif cc == 35:  # '#'
                    effective = _toml_strip(_toml_substring(effective, 0, ci))
                    break

        if len(effective) == 0:
            continue

        var ebs2 = effective.as_bytes()

        # Section header: [section] or [section.sub]
        if Int(ebs2[0]) == 91 and Int(ebs2[len(effective) - 1]) == 93:  # '[' ... ']'
            var header = _toml_strip(_toml_substring(effective, 1, len(effective) - 1))
            var parts = _toml_split_dot(header)
            # Navigate/create nested sections from root
            current_section = root
            for pi in range(len(parts)):
                var part = _toml_strip(parts[pi])
                current_section = pool.ensure_sub_map(current_section, part)
            continue

        # Key = Value
        var eq_pos = -1
        var in_s2 = False
        var sc2 = 0
        for ki in range(len(effective)):
            var kc = Int(ebs2[ki])
            if in_s2:
                if kc == sc2:
                    in_s2 = False
            else:
                if kc == 34 or kc == 39:
                    in_s2 = True
                    sc2 = kc
                elif kc == 61:  # '='
                    eq_pos = ki
                    break

        if eq_pos > 0:
            var key = _toml_strip(_toml_substring(effective, 0, eq_pos))
            var val_str = _toml_strip(_toml_substring(effective, eq_pos + 1, len(effective)))
            var val_idx = _toml_parse_value(pool, val_str)
            pool.map_set(current_section, key, val_idx)

    return TomlDoc(pool, root)


# ── Public API: dot-notation accessors ────────────────────────────────────────


fn _toml_resolve(doc: TomlDoc, path: String) -> Int:
    """Resolve a dot-notation path to a node index. Returns -1 if not found."""
    var parts = _toml_split_dot(path)
    var current = doc.root
    for pi in range(len(parts)):
        var seg = _toml_strip(parts[pi])
        if doc.pool.nodes[current].kind != _TOML_MAP:
            return -1
        var found = False
        for ki in range(len(doc.pool.nodes[current].map_keys)):
            if doc.pool.nodes[current].map_keys[ki] == seg:
                current = doc.pool.nodes[current].map_vals[ki]
                found = True
                break
        if not found:
            return -1
    return current


fn toml_get_string(doc: TomlDoc, path: String) -> String:
    """Get a string value by dot-notation path. Returns '' if not found."""
    var idx = _toml_resolve(doc, path)
    if idx < 0:
        return String("")
    if doc.pool.nodes[idx].kind == _TOML_SCALAR:
        return doc.pool.nodes[idx].scalar
    return String("")


fn toml_get_int(doc: TomlDoc, path: String, default: Int) -> Int:
    """Get an integer value by dot-notation path. Returns default if not found."""
    var s = toml_get_string(doc, path)
    if len(s) == 0:
        return default
    try:
        return atol(s)
    except:
        return default


fn toml_get_float(doc: TomlDoc, path: String, default: Float64) -> Float64:
    """Get a float value by dot-notation path. Returns default if not found."""
    var s = toml_get_string(doc, path)
    if len(s) == 0:
        return default
    try:
        return atof(s)
    except:
        return default


fn toml_get_bool(doc: TomlDoc, path: String, default: Bool) -> Bool:
    """Get a boolean value by dot-notation path. Returns default if not found."""
    var s = toml_get_string(doc, path)
    if len(s) == 0:
        return default
    if s == "true" or s == "True":
        return True
    if s == "false" or s == "False":
        return False
    return default
