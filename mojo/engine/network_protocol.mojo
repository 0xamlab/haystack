"""
network_protocol.mojo — Network protocol helpers. Zero Python imports.

Replaces Python's http.client, mimetypes, urllib.parse with pure Mojo
implementations for the decision engine.

Public API:
  http_status_text    — Status text for HTTP code
  is_success          — 200-299
  is_redirect         — 300-399
  is_client_error     — 400-499
  is_server_error     — 500-599
  mime_type           — File extension → MIME type
  parse_content_type  — Extract MIME from Content-Type header
  is_json_type        — Check if MIME is JSON-compatible
  is_text_type        — Check if MIME starts with "text/"
  build_query_string  — Build key=val&key=val query string
  parse_query_string  — Parse query string into [[key,val], ...] pairs
"""


# ── HTTP Status Codes ─────────────────────────────────────────────────────────


fn http_status_text(code: Int) -> String:
    """Return the standard HTTP reason phrase for a status code."""
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


# ── Status Code Classification ────────────────────────────────────────────────


fn is_success(code: Int) -> Bool:
    """True if HTTP code is in 200-299 (success)."""
    return code >= 200 and code <= 299


fn is_redirect(code: Int) -> Bool:
    """True if HTTP code is in 300-399 (redirect)."""
    return code >= 300 and code <= 399


fn is_client_error(code: Int) -> Bool:
    """True if HTTP code is in 400-499 (client error)."""
    return code >= 400 and code <= 499


fn is_server_error(code: Int) -> Bool:
    """True if HTTP code is in 500-599 (server error)."""
    return code >= 500 and code <= 599


# ── MIME Types ────────────────────────────────────────────────────────────────


fn mime_type(extension: String) -> String:
    """Map a file extension (without dot) to its MIME type.

    Supports 20+ common types. Returns "application/octet-stream" for unknown.
    """
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


# ── Content-Type Parsing ──────────────────────────────────────────────────────


fn parse_content_type(header: String) -> String:
    """Extract the MIME type from a Content-Type header, stripping parameters.

    Example: "text/html; charset=utf-8" → "text/html"
    """
    var h_bytes = header.as_bytes()
    var n = len(h_bytes)

    # Find semicolon position
    var semi_pos = -1
    for i in range(n):
        if Int(h_bytes[i]) == ord(";"):
            semi_pos = i
            break

    var end_pos = n
    if semi_pos >= 0:
        end_pos = semi_pos

    # Strip trailing whitespace
    while end_pos > 0 and Int(h_bytes[end_pos - 1]) == ord(" "):
        end_pos -= 1

    # Strip leading whitespace
    var start_pos = 0
    while start_pos < end_pos and Int(h_bytes[start_pos]) == ord(" "):
        start_pos += 1

    var result = String("")
    for i in range(start_pos, end_pos):
        result += chr(Int(h_bytes[i]))
    return result^


fn is_json_type(mime: String) -> Bool:
    """Check if MIME type is JSON-compatible."""
    if mime == "application/json":
        return True
    # Check for +json suffix (e.g. application/vnd.api+json)
    var b = mime.as_bytes()
    var n = len(b)
    if n >= 5:
        if (
            Int(b[n - 5]) == ord("+")
            and Int(b[n - 4]) == ord("j")
            and Int(b[n - 3]) == ord("s")
            and Int(b[n - 2]) == ord("o")
            and Int(b[n - 1]) == ord("n")
        ):
            return True
    return False


fn is_text_type(mime: String) -> Bool:
    """Check if MIME type starts with 'text/'."""
    var b = mime.as_bytes()
    if len(b) < 5:
        return False
    return (
        Int(b[0]) == ord("t")
        and Int(b[1]) == ord("e")
        and Int(b[2]) == ord("x")
        and Int(b[3]) == ord("t")
        and Int(b[4]) == ord("/")
    )


# ── Query String ──────────────────────────────────────────────────────────────


fn build_query_string(keys: List[String], values: List[String]) -> String:
    """Build a URL query string: key1=val1&key2=val2.

    Keys and values lists must be same length.
    """
    var n = len(keys)
    if len(values) < n:
        n = len(values)
    var result = String("")
    for i in range(n):
        if i > 0:
            result += "&"
        result += keys[i] + "=" + values[i]
    return result^


fn _extract_substring(s: String, start: Int, end: Int) -> String:
    """Extract a substring from s using byte positions."""
    var sb = s.as_bytes()
    var result = String("")
    for i in range(start, end):
        result += chr(Int(sb[i]))
    return result^


fn parse_query_string(query: String) -> List[List[String]]:
    """Parse a URL query string into [[key, value], ...] pairs.

    Example: "a=1&b=2" → [["a","1"], ["b","2"]]
    """
    var result = List[List[String]]()
    if len(query) == 0:
        return result^

    var q_bytes = query.as_bytes()
    var n = len(q_bytes)

    # Split on '&' — collect start positions
    var starts = List[Int]()
    var ends = List[Int]()
    var seg_start = 0
    for i in range(n):
        if Int(q_bytes[i]) == ord("&"):
            starts.append(seg_start)
            ends.append(i)
            seg_start = i + 1
    starts.append(seg_start)
    ends.append(n)

    # Process each pair
    for pi in range(len(starts)):
        var ps = starts[pi]
        var pe = ends[pi]
        # Find '=' in this segment
        var eq_pos = -1
        for k in range(ps, pe):
            if Int(q_bytes[k]) == ord("="):
                eq_pos = k
                break
        var kv = List[String]()
        if eq_pos >= 0:
            kv.append(_extract_substring(query, ps, eq_pos))
            kv.append(_extract_substring(query, eq_pos + 1, pe))
        else:
            kv.append(_extract_substring(query, ps, pe))
            kv.append(String(""))
        result.append(kv^)

    return result^
