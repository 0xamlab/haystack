"""
yaml_parser.mojo — Simple YAML parser for config files. Zero Python imports.

Covers the subset of YAML used in configuration files:
  - key: value pairs
  - Nested maps (indentation-based)
  - Lists (- item syntax)
  - Scalars: strings, integers, floats, booleans (true/false), null

Public API:
  YamlNode              — tree node (scalar, map, or list)
  yaml_parse()          — parse YAML string to tree
  yaml_get_string()     — dot-notation string lookup
  yaml_get_int()        — dot-notation int lookup with default
  yaml_get_float()      — dot-notation float lookup with default
  yaml_get_bool()       — dot-notation bool lookup with default
"""


# ── Node types ───────────────────────────────────────────────────────────────

comptime _YAML_SCALAR = 0
comptime _YAML_MAP = 1
comptime _YAML_LIST = 2


# ── YamlNode struct ──────────────────────────────────────────────────────────


@fieldwise_init
struct YamlNode(Copyable, Movable):
    """A YAML tree node. Can be a scalar, map, or list."""
    var kind: Int           # _YAML_SCALAR, _YAML_MAP, _YAML_LIST
    var scalar: String      # value if scalar

    # Map: parallel lists of keys and child nodes
    var map_keys: List[String]
    var map_vals: List[Int]  # indices into a shared node pool

    # List: child node indices
    var list_vals: List[Int]  # indices into a shared node pool

    fn __init__(out self):
        self.kind = _YAML_SCALAR
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


# ── Node pool (flat list for tree storage) ────────────────────────────────────


@fieldwise_init
struct _YamlPool(Copyable, Movable):
    """Flat storage for YAML nodes. Nodes reference children by index."""
    var nodes: List[YamlNode]

    fn __init__(out self):
        self.nodes = List[YamlNode]()

    fn __copyinit__(out self, copy: Self):
        self.nodes = copy.nodes.copy()

    fn add_scalar(mut self, value: String) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_SCALAR, value))
        return idx

    fn add_map(mut self) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_MAP, String("")))
        return idx

    fn add_list(mut self) -> Int:
        var idx = len(self.nodes)
        self.nodes.append(YamlNode(_YAML_LIST, String("")))
        return idx


# ── Internal helpers ─────────────────────────────────────────────────────────


fn _count_indent(line: String) -> Int:
    """Count leading spaces in a line."""
    var bs = line.as_bytes()
    var n = len(line)
    var count = 0
    while count < n and Int(bs[count]) == 32:  # space
        count += 1
    return count


fn _strip(s: String) -> String:
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


fn _starts_with(s: String, prefix: String) -> Bool:
    """Check if s starts with prefix."""
    var sbs = s.as_bytes()
    var pbs = prefix.as_bytes()
    if len(prefix) > len(s):
        return False
    for i in range(len(prefix)):
        if sbs[i] != pbs[i]:
            return False
    return True


fn _split_lines(content: String) -> List[String]:
    """Split string by newline into lines."""
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
    # Last line (no trailing newline)
    if start <= n:
        var line = String("")
        for j in range(start, n):
            line += chr(Int(bs[j]))
        lines.append(line)
    return lines^


fn _find_colon(line: String) -> Int:
    """Find the index of the first ': ' or ':' at end in a trimmed line.
    Returns -1 if not found.
    """
    var bs = line.as_bytes()
    var n = len(line)
    for i in range(n):
        if Int(bs[i]) == 58:  # ':'
            if i + 1 >= n or Int(bs[i + 1]) == 32:
                return i
    return -1


fn _substring(s: String, start: Int, end: Int) -> String:
    """Extract substring s[start:end]."""
    var bs = s.as_bytes()
    var result = String("")
    var e = min(end, len(s))
    for i in range(start, e):
        result += chr(Int(bs[i]))
    return result


fn _unquote(s: String) -> String:
    """Remove surrounding quotes if present."""
    var n = len(s)
    if n < 2:
        return s
    var bs = s.as_bytes()
    var first = Int(bs[0])
    var last = Int(bs[n - 1])
    if (first == 34 and last == 34) or (first == 39 and last == 39):
        return _substring(s, 1, n - 1)
    return s


# ── Parser state ─────────────────────────────────────────────────────────────


struct _ParseState(Copyable, Movable):
    """Mutable parser state tracking line position."""
    var lines: List[String]
    var pos: Int
    var pool: _YamlPool

    fn __init__(out self, lines: List[String]):
        self.lines = lines.copy()
        self.pos = 0
        self.pool = _YamlPool()

    fn __copyinit__(out self, copy: Self):
        self.lines = copy.lines.copy()
        self.pos = copy.pos
        self.pool = copy.pool.copy()


# ── Recursive parser ─────────────────────────────────────────────────────────


fn _parse_block(mut state: _ParseState, base_indent: Int) -> Int:
    """Parse a block at the given indentation level. Returns node index."""
    var n_lines = len(state.lines)

    if state.pos >= n_lines:
        return state.pool.add_scalar(String(""))

    var first_line = state.lines[state.pos]
    var first_stripped = _strip(first_line)

    # Check if it's a list item
    if _starts_with(first_stripped, "- "):
        var list_idx = state.pool.add_list()
        while state.pos < n_lines:
            var line = state.lines[state.pos]
            var li = _count_indent(line)
            var ls = _strip(line)
            if len(ls) == 0:
                state.pos += 1
                continue
            if li < base_indent:
                break
            if li != base_indent or not _starts_with(ls, "- "):
                break
            var item_val = _strip(_substring(ls, 2, len(ls)))
            var item_idx = state.pool.add_scalar(item_val)
            state.pool.nodes[list_idx].list_vals.append(item_idx)
            state.pos += 1
        return list_idx

    # Otherwise parse as map
    var map_idx = state.pool.add_map()
    while state.pos < n_lines:
        var line = state.lines[state.pos]
        var li = _count_indent(line)
        var ls = _strip(line)

        if len(ls) == 0:
            state.pos += 1
            continue

        if li < base_indent:
            break

        if li > base_indent:
            state.pos += 1
            continue

        var colon_pos = _find_colon(ls)
        if colon_pos < 0:
            state.pos += 1
            continue

        var key = _strip(_substring(ls, 0, colon_pos))
        var val_part = String("")
        if colon_pos + 1 < len(ls):
            val_part = _strip(_substring(ls, colon_pos + 1, len(ls)))

        state.pos += 1

        if len(val_part) > 0:
            var val_idx = state.pool.add_scalar(_unquote(val_part))
            state.pool.nodes[map_idx].map_keys.append(key)
            state.pool.nodes[map_idx].map_vals.append(val_idx)
        else:
            if state.pos < n_lines:
                var next_line = state.lines[state.pos]
                var next_stripped = _strip(next_line)
                if len(next_stripped) > 0:
                    var next_indent = _count_indent(next_line)
                    if next_indent > base_indent:
                        var child_idx = _parse_block(state, next_indent)
                        state.pool.nodes[map_idx].map_keys.append(key)
                        state.pool.nodes[map_idx].map_vals.append(child_idx)
                    else:
                        var empty_idx = state.pool.add_scalar(String(""))
                        state.pool.nodes[map_idx].map_keys.append(key)
                        state.pool.nodes[map_idx].map_vals.append(empty_idx)
                else:
                    var empty_idx = state.pool.add_scalar(String(""))
                    state.pool.nodes[map_idx].map_keys.append(key)
                    state.pool.nodes[map_idx].map_vals.append(empty_idx)
            else:
                var empty_idx = state.pool.add_scalar(String(""))
                state.pool.nodes[map_idx].map_keys.append(key)
                state.pool.nodes[map_idx].map_vals.append(empty_idx)

    return map_idx


# ── YamlDoc: parsed document with node pool ──────────────────────────────────


struct YamlDoc(Copyable, Movable):
    """A parsed YAML document containing the node pool and root index."""
    var pool: _YamlPool
    var root: Int

    fn __init__(out self):
        self.pool = _YamlPool()
        self.root = 0

    fn __init__(out self, pool: _YamlPool, root: Int):
        self.pool = pool.copy()
        self.root = root

    fn __copyinit__(out self, copy: Self):
        self.pool = copy.pool.copy()
        self.root = copy.root


# ── Public API: yaml_parse ───────────────────────────────────────────────────


fn yaml_parse(content: String) -> YamlDoc:
    """Parse YAML content string into a YamlDoc tree."""
    var lines = _split_lines(content)
    var state = _ParseState(lines)
    var root = _parse_block(state, 0)
    return YamlDoc(state.pool, root)


# ── Public API: dot-notation accessors ────────────────────────────────────────


fn _split_path(path: String) -> List[String]:
    """Split a dot-notation path into segments."""
    var parts = List[String]()
    var bs = path.as_bytes()
    var n = len(path)
    var start = 0
    for i in range(n):
        if Int(bs[i]) == 46:  # '.'
            var seg = String("")
            for j in range(start, i):
                seg += chr(Int(bs[j]))
            parts.append(seg)
            start = i + 1
    var last = String("")
    for j in range(start, n):
        last += chr(Int(bs[j]))
    parts.append(last)
    return parts^


fn _resolve_path(doc: YamlDoc, path: String) -> Int:
    """Resolve a dot-notation path to a node index. Returns -1 if not found."""
    var parts = _split_path(path)
    var n_nodes = len(doc.pool.nodes)
    var current = doc.root
    # A hand-built or corrupt document can point root/edges outside the node pool; the
    # unguarded subscript aborted the worker, so treat every such document as not-found.
    if current < 0 or current >= n_nodes:
        return -1
    for pi in range(len(parts)):
        var seg = parts[pi]
        if doc.pool.nodes[current].kind != _YAML_MAP:
            return -1
        var found = False
        # map_keys and map_vals are parallel arrays; a ragged document must not let ki run
        # past the shorter one.
        var n_entries = len(doc.pool.nodes[current].map_keys)
        if len(doc.pool.nodes[current].map_vals) < n_entries:
            n_entries = len(doc.pool.nodes[current].map_vals)
        for ki in range(n_entries):
            if doc.pool.nodes[current].map_keys[ki] == seg:
                var next = doc.pool.nodes[current].map_vals[ki]
                if next < 0 or next >= n_nodes:
                    return -1
                current = next
                found = True
                break
        if not found:
            return -1
    return current


fn yaml_get_string(doc: YamlDoc, path: String) -> String:
    """Get a string value by dot-notation path. Returns '' if not found."""
    var idx = _resolve_path(doc, path)
    if idx < 0:
        return String("")
    if doc.pool.nodes[idx].kind == _YAML_SCALAR:
        return doc.pool.nodes[idx].scalar
    return String("")


fn yaml_get_int(doc: YamlDoc, path: String, default: Int) -> Int:
    """Get an integer value by dot-notation path. Returns default if not found."""
    var s = yaml_get_string(doc, path)
    if len(s) == 0:
        return default
    try:
        return atol(s)
    except:
        return default


fn yaml_get_float(doc: YamlDoc, path: String, default: Float64) -> Float64:
    """Get a float value by dot-notation path. Returns default if not found."""
    var s = yaml_get_string(doc, path)
    if len(s) == 0:
        return default
    try:
        return atof(s)
    except:
        return default


fn yaml_get_bool(doc: YamlDoc, path: String, default: Bool) -> Bool:
    """Get a boolean value by dot-notation path. Returns default if not found."""
    var s = yaml_get_string(doc, path)
    if len(s) == 0:
        return default
    if s == "true" or s == "True" or s == "yes" or s == "Yes" or s == "on" or s == "On":
        return True
    if s == "false" or s == "False" or s == "no" or s == "No" or s == "off" or s == "Off":
        return False
    return default
