"""
pathlib.mojo — Path manipulation via pure string operations. Zero Python imports.

Replaces Python's pathlib for path string handling. No actual filesystem calls.

Public API:
  path_join()         — join path components with /
  path_basename()     — last component
  path_dirname()      — parent directory
  path_extension()    — file extension including dot
  path_stem()         — filename without extension
  path_is_absolute()  — starts with /
  path_normalize()    — resolve ../ and ./
  path_split()        — split into components
"""


# ── Internal helpers ─────────────────────────────────────────────────────────


def _path_substring(s: String, start: Int, end: Int) -> String:
    """Extract substring s[start:end]."""
    var bs = s.as_bytes()
    var result = String("")
    var e = min(end, len(s))
    for i in range(start, e):
        result += chr(Int(bs[i]))
    return result


def _path_char_at(s: String, idx: Int) -> Int:
    """Get character code at index."""
    return Int(s.as_bytes()[idx])


# ── Public API ───────────────────────────────────────────────────────────────


def path_join(parts: List[String]) -> String:
    """Join path components with /. Skips empty parts."""
    var result = String("")
    for i in range(len(parts)):
        var part = parts[i]
        if len(part) == 0:
            continue
        if len(result) > 0:
            # Check if result already ends with /
            if _path_char_at(result, len(result) - 1) != 47:  # '/'
                result += "/"
        result += part
    return result


def path_basename(path: String) -> String:
    """Return the last component of a path (filename)."""
    if len(path) == 0:
        return String("")
    var bs = path.as_bytes()
    var n = len(path)
    # Strip trailing slashes
    var end = n
    while end > 0 and Int(bs[end - 1]) == 47:  # '/'
        end -= 1
    if end == 0:
        return String("/")
    # Find last slash before end
    var last_slash = -1
    for i in range(end):
        if Int(bs[i]) == 47:
            last_slash = i
    return _path_substring(path, last_slash + 1, end)


def path_dirname(path: String) -> String:
    """Return the parent directory of a path."""
    if len(path) == 0:
        return String(".")
    var bs = path.as_bytes()
    var n = len(path)
    # Strip trailing slashes (unless it's just "/")
    var end = n
    while end > 1 and Int(bs[end - 1]) == 47:
        end -= 1
    # Find last slash
    var last_slash = -1
    for i in range(end):
        if Int(bs[i]) == 47:
            last_slash = i
    if last_slash < 0:
        return String(".")
    if last_slash == 0:
        return String("/")
    return _path_substring(path, 0, last_slash)


def path_extension(path: String) -> String:
    """Return the file extension including the dot. Returns '' if none."""
    var base = path_basename(path)
    if len(base) == 0:
        return String("")
    var bs = base.as_bytes()
    var n = len(base)
    # Find last dot
    var last_dot = -1
    for i in range(n):
        if Int(bs[i]) == 46:  # '.'
            last_dot = i
    if last_dot <= 0:  # no dot, or dot at start (hidden file)
        return String("")
    return _path_substring(base, last_dot, n)


def path_stem(path: String) -> String:
    """Return the filename without extension."""
    var base = path_basename(path)
    if len(base) == 0:
        return String("")
    var bs = base.as_bytes()
    var n = len(base)
    # Find last dot
    var last_dot = -1
    for i in range(n):
        if Int(bs[i]) == 46:  # '.'
            last_dot = i
    if last_dot <= 0:
        return base
    return _path_substring(base, 0, last_dot)


def path_is_absolute(path: String) -> Bool:
    """Check if path is absolute (starts with /)."""
    if len(path) == 0:
        return False
    return Int(path.as_bytes()[0]) == 47  # '/'


def path_split(path: String) -> List[String]:
    """Split a path into its components. Leading / becomes empty first element."""
    var parts = List[String]()
    if len(path) == 0:
        return parts^
    var bs = path.as_bytes()
    var n = len(path)
    var start = 0

    # Handle leading /
    if Int(bs[0]) == 47:
        parts.append(String("/"))
        start = 1
        # Skip consecutive slashes
        while start < n and Int(bs[start]) == 47:
            start += 1

    var seg_start = start
    for i in range(start, n):
        if Int(bs[i]) == 47:
            if i > seg_start:
                parts.append(_path_substring(path, seg_start, i))
            seg_start = i + 1
    if seg_start < n:
        parts.append(_path_substring(path, seg_start, n))

    return parts^


def path_normalize(path: String) -> String:
    """Normalize a path: resolve . and .. components, collapse multiple slashes."""
    if len(path) == 0:
        return String(".")

    var is_abs = path_is_absolute(path)
    var components = path_split(path)
    var result = List[String]()

    var start_idx = 0
    if is_abs and len(components) > 0:
        # Skip the "/" root component
        start_idx = 1

    for i in range(start_idx, len(components)):
        var comp = components[i]
        if comp == ".":
            continue
        elif comp == "..":
            if len(result) > 0 and result[len(result) - 1] != "..":
                _ = result.pop()
            elif not is_abs:
                result.append(comp)
            # If absolute, just ignore .. at root
        else:
            result.append(comp)

    if len(result) == 0:
        if is_abs:
            return String("/")
        return String(".")

    var out = String("")
    if is_abs:
        out = "/"
    for i in range(len(result)):
        if i > 0:
            out += "/"
        out += result[i]
    return out
