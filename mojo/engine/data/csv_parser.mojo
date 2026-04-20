"""
csv_parser.mojo — RFC 4180 CSV parser. Zero Python imports.
Handles: quoted fields, escaped quotes (""), commas inside quotes, newlines inside quotes.
"""


# ── CSVRow struct ─────────────────────────────────────────────────────────────


struct CSVRow(Copyable, Movable):
    """A single parsed CSV row containing a list of field strings."""
    var fields: List[String]
    var n_fields: Int

    fn __init__(out self):
        self.fields = List[String]()
        self.n_fields = 0

    fn __init__(out self, fields: List[String]):
        self.fields = fields.copy()
        self.n_fields = len(fields)

    fn __copyinit__(out self, copy: Self):
        self.fields = copy.fields.copy()
        self.n_fields = copy.n_fields


struct CSVResult(Copyable, Movable):
    """Result of parse_csv: headers + rows."""
    var headers: List[String]
    var rows: List[CSVRow]

    fn __init__(out self):
        self.headers = List[String]()
        self.rows = List[CSVRow]()

    fn __init__(out self, headers: List[String], rows: List[CSVRow]):
        self.headers = headers.copy()
        self.rows = rows.copy()

    fn __copyinit__(out self, copy: Self):
        self.headers = copy.headers.copy()
        self.rows = copy.rows.copy()


# ── Byte constants ────────────────────────────────────────────────────────────

comptime _DQUOTE = UInt8(34)
comptime _LF = UInt8(10)
comptime _CR = UInt8(13)
comptime _TAB = UInt8(9)
comptime _SPACE = UInt8(32)


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _try_parse_float(s: String) -> Float64:
    try:
        return atof(s)
    except:
        return 0.0


fn _can_parse_float(s: String) -> Bool:
    if len(s) == 0:
        return False
    var bs = s.as_bytes()
    var start = 0
    while start < len(s) and (bs[start] == _SPACE or bs[start] == _TAB):
        start += 1
    if start >= len(s):
        return False
    if bs[start] == UInt8(45) or bs[start] == UInt8(43):
        start += 1
    if start >= len(s):
        return False
    var has_digit = False
    var has_dot = False
    var i = start
    while i < len(s):
        var c = bs[i]
        if c >= UInt8(48) and c <= UInt8(57):
            has_digit = True
        elif c == UInt8(46) and not has_dot:
            has_dot = True
        elif c == UInt8(101) or c == UInt8(69):
            i += 1
            if i < len(s) and (bs[i] == UInt8(45) or bs[i] == UInt8(43)):
                i += 1
            if i >= len(s) or not (bs[i] >= UInt8(48) and bs[i] <= UInt8(57)):
                return False
            while i < len(s) and bs[i] >= UInt8(48) and bs[i] <= UInt8(57):
                i += 1
            while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
                i += 1
            return i == len(s) and has_digit
        elif c == _SPACE or c == _TAB:
            break
        else:
            return False
        i += 1
    while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
        i += 1
    return has_digit and i == len(s)


fn _try_parse_int(s: String) -> Int:
    try:
        return atol(s)
    except:
        return 0


fn _can_parse_int(s: String) -> Bool:
    if len(s) == 0:
        return False
    var bs = s.as_bytes()
    var start = 0
    while start < len(s) and (bs[start] == _SPACE or bs[start] == _TAB):
        start += 1
    if start >= len(s):
        return False
    if bs[start] == UInt8(45) or bs[start] == UInt8(43):
        start += 1
    if start >= len(s):
        return False
    var has_digit = False
    var i = start
    while i < len(s):
        var c = bs[i]
        if c >= UInt8(48) and c <= UInt8(57):
            has_digit = True
        elif c == _SPACE or c == _TAB:
            break
        else:
            return False
        i += 1
    while i < len(s) and (bs[i] == _SPACE or bs[i] == _TAB):
        i += 1
    return has_digit and i == len(s)


# ── Core CSV parsing (state machine) ─────────────────────────────────────────


fn _parse_fields(line: String, delim_byte: UInt8) -> List[String]:
    """Parse a single CSV record into fields using RFC 4180 state machine."""
    var fields = List[String]()
    var bs = line.as_bytes()
    var n = len(line)
    var current = String("")
    var state = 0  # 0=field_start, 1=unquoted, 2=quoted, 3=after_quote
    var i = 0

    while i < n:
        var c = bs[i]

        if state == 0:
            if c == _DQUOTE:
                state = 2
            elif c == delim_byte:
                fields.append(current)
                current = String("")
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(Int(c))
                state = 1
        elif state == 1:
            if c == delim_byte:
                fields.append(current)
                current = String("")
                state = 0
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(Int(c))
        elif state == 2:
            if c == _DQUOTE:
                state = 3
            else:
                current += chr(Int(c))
        elif state == 3:
            if c == _DQUOTE:
                current += chr(Int(_DQUOTE))
                state = 2
            elif c == delim_byte:
                fields.append(current)
                current = String("")
                state = 0
            elif c == _CR:
                pass
            elif c == _LF:
                break
            else:
                current += chr(Int(c))
                state = 1

        i += 1

    fields.append(current)
    return fields^


fn _split_csv_records(content: String) -> List[String]:
    """Split CSV content into records, respecting quoted fields with embedded newlines."""
    var records = List[String]()
    var bs = content.as_bytes()
    var n = len(content)
    var current = String("")
    var in_quotes = False
    var i = 0

    while i < n:
        var c = bs[i]

        if c == _DQUOTE:
            in_quotes = not in_quotes
            current += chr(Int(c))
        elif c == _LF and not in_quotes:
            if len(current) > 0:
                records.append(current)
            current = String("")
        elif c == _CR and not in_quotes:
            pass
        else:
            current += chr(Int(c))

        i += 1

    if len(current) > 0:
        records.append(current)

    return records^


# ── Public API ────────────────────────────────────────────────────────────────


fn parse_csv(content: String, delimiter: String = ",", has_header: Bool = True) -> CSVResult:
    """Parse CSV content into CSVResult with .headers and .rows."""
    var delim_byte = UInt8(ord(","))
    if len(delimiter) > 0:
        delim_byte = delimiter.as_bytes()[0]

    var records = _split_csv_records(content)
    var result = CSVResult()

    if len(records) == 0:
        return result^

    var start_idx = 0

    if has_header:
        var header_fields = _parse_fields(records[0], delim_byte)
        for j in range(len(header_fields)):
            result.headers.append(header_fields[j])
        start_idx = 1

    for i in range(start_idx, len(records)):
        var fields = _parse_fields(records[i], delim_byte)
        result.rows.append(CSVRow(fields))

    return result^


fn parse_csv_row(line: String, delimiter: String = ",") -> CSVRow:
    """Parse a single CSV line into fields."""
    var delim_byte = UInt8(ord(","))
    if len(delimiter) > 0:
        delim_byte = delimiter.as_bytes()[0]
    var fields = _parse_fields(line, delim_byte)
    return CSVRow(fields)


fn csv_get_field(row: CSVRow, index: Int) -> String:
    """Get field at index from a parsed row. Returns "" if out of bounds."""
    if index < 0 or index >= row.n_fields:
        return String("")
    return row.fields[index]


fn csv_get_float(row: CSVRow, index: Int, default: Float64 = 0.0) -> Float64:
    """Get field as Float64. Returns default if not numeric or out of bounds."""
    if index < 0 or index >= row.n_fields:
        return default
    var s = row.fields[index]
    if not _can_parse_float(s):
        return default
    return _try_parse_float(s)


fn csv_get_int(row: CSVRow, index: Int, default: Int = 0) -> Int:
    """Get field as Int. Returns default if not numeric or out of bounds."""
    if index < 0 or index >= row.n_fields:
        return default
    var s = row.fields[index]
    if not _can_parse_int(s):
        return default
    return _try_parse_int(s)


fn _escape_json_string(s: String) -> String:
    """Escape a string for JSON output."""
    var result = String("")
    var bs = s.as_bytes()
    for i in range(len(s)):
        var c = bs[i]
        if c == UInt8(34):
            result += "\\\""
        elif c == UInt8(92):
            result += "\\\\"
        elif c == UInt8(10):
            result += "\\n"
        elif c == UInt8(13):
            result += "\\r"
        elif c == UInt8(9):
            result += "\\t"
        else:
            result += chr(Int(c))
    return result


fn csv_to_json_array(headers: List[String], rows: List[CSVRow]) -> String:
    """Convert parsed CSV to JSON array of objects."""
    var result = String("[")
    var n_headers = len(headers)

    for i in range(len(rows)):
        if i > 0:
            result += ","
        result += "{"
        var n_cols = rows[i].n_fields
        if n_cols > n_headers and n_headers > 0:
            n_cols = n_headers

        for j in range(n_cols):
            if j > 0:
                result += ","
            result += "\""
            if j < n_headers:
                result += _escape_json_string(headers[j])
            else:
                result += "col" + String(j)
            result += "\":"
            result += "\""
            result += _escape_json_string(rows[i].fields[j])
            result += "\""

        result += "}"

    result += "]"
    return result
