"""
algenta_runtime.stream — read a resident dataset in chunks. Zero Python.

Why
---
A session makes a large input cheap to *reference*, but a large **output** still
has to come back in one frame. Materialising a million-row result in a single
response forces the caller to hold all of it, and there is no way to stop early
once it has been sent.

A cursor inverts that: the caller asks for the next N rows when it is ready for
them. That is backpressure without any protocol machinery — the client's next call
*is* the credit. It also makes early termination free: stop calling, close the
cursor, and the untouched remainder is never encoded.

This is the only shape that works on this worker. The server loop is
single-threaded and reads frames sequentially (main.mojo `run_server_loop`), so
the worker cannot push unsolicited chunks; it can only answer a pull. Cursors are
therefore pull-based by necessity as well as by preference.

Lifetime
--------
Cursors live for the connection, like the datasets they read, and hold only a
handle plus a position — never a copy of the data. Closing the underlying dataset
leaves a cursor that fails cleanly with `dataset_not_found` on its next pull,
rather than reading freed memory.

Wire format
-----------
    {"type":"stream_open","handle":"ds_1","chunk_rows":2}
      -> {"cursor":"st_1","total":5,"remaining":5,"chunk_rows":2}

    {"type":"stream_next","cursor":"st_1"}
      -> {"chunk":[1.0,2.0],"rows":2,"position":2,"remaining":3,"done":false}

    {"type":"stream_next","cursor":"st_1","max_rows":10}   # override per pull
    {"type":"stream_close","cursor":"st_1"} -> {"closed":true}

`done` is true on the response that drains the cursor, so a caller loops until
`done` without needing a separate emptiness check.
"""
from json.parser import json_array_tokens, json_get_int, json_get_string

from algenta_runtime.session import ResidentDatasets

# Rows per pull when the caller does not say. Small enough to bound one response,
# large enough that a full scan is not dominated by frame count.
alias DEFAULT_CHUNK_ROWS = 1024

# Hard ceiling per pull, so `max_rows` cannot be used to demand the whole dataset
# in one frame and defeat the point of streaming.
alias MAX_CHUNK_ROWS = 65536


fn _stream_error(code: String, message: String) -> String:
    return (
        '{"error":"'
        + code
        + ": "
        + message
        + '","error_code":"'
        + code
        + '","error_message":"'
        + message
        + '"}'
    )


struct ResidentStreams(Copyable, Movable):
    """Connection-scoped cursors over resident datasets.

    Holds `(cursor, dataset handle, position, chunk_rows)` only — the data stays in
    the dataset registry, so a cursor costs a few bytes regardless of dataset size.
    """

    var cursors: List[String]
    var handles: List[String]
    var positions: List[Int]
    var chunk_rows: List[Int]
    var next_id: Int

    fn __init__(out self):
        self.cursors = List[String]()
        self.handles = List[String]()
        self.positions = List[Int]()
        self.chunk_rows = List[Int]()
        self.next_id = 1

    fn count(self) -> Int:
        return len(self.cursors)

    fn _index_of(self, cursor: String) -> Int:
        for i in range(len(self.cursors)):
            if self.cursors[i] == cursor:
                return i
        return -1

    fn open_from_json(mut self, raw: String, datasets: ResidentDatasets) raises -> String:
        var handle = json_get_string(raw, "handle")
        if len(handle) == 0:
            return _stream_error("invalid_arguments", "stream_open requires a handle.")
        var value = datasets.lookup(handle)
        if len(value) == 0:
            return _stream_error(
                "dataset_not_found", "no resident dataset for handle " + handle + "."
            )

        var requested = json_get_int(raw, "chunk_rows", DEFAULT_CHUNK_ROWS)
        if requested <= 0:
            requested = DEFAULT_CHUNK_ROWS
        if requested > MAX_CHUNK_ROWS:
            requested = MAX_CHUNK_ROWS

        var total = len(json_array_tokens(value))
        var cursor = "st_" + String(self.next_id)
        self.next_id += 1
        self.cursors.append(cursor)
        self.handles.append(handle)
        self.positions.append(0)
        self.chunk_rows.append(requested)

        return (
            '{"cursor":"'
            + cursor
            + '","handle":"'
            + handle
            + '","total":'
            + String(total)
            + ',"remaining":'
            + String(total)
            + ',"chunk_rows":'
            + String(requested)
            + "}"
        )

    fn next_from_json(mut self, raw: String, datasets: ResidentDatasets) raises -> String:
        var cursor = json_get_string(raw, "cursor")
        if len(cursor) == 0:
            return _stream_error("invalid_arguments", "stream_next requires a cursor.")
        var index = self._index_of(cursor)
        if index < 0:
            return _stream_error("cursor_not_found", "no open cursor " + cursor + ".")

        # Re-read the dataset each pull: closing it mid-stream must surface as a
        # clean not-found rather than a stale snapshot.
        var value = datasets.lookup(self.handles[index])
        if len(value) == 0:
            return _stream_error(
                "dataset_not_found",
                "dataset " + self.handles[index] + " was closed while streaming.",
            )

        var rows = json_array_tokens(value)
        var total = len(rows)
        var position = self.positions[index]

        var want = json_get_int(raw, "max_rows", 0)
        if want <= 0:
            want = self.chunk_rows[index]
        if want > MAX_CHUNK_ROWS:
            want = MAX_CHUNK_ROWS

        var end = position + want
        if end > total:
            end = total

        var chunk = String("[")
        for i in range(position, end):
            if i > position:
                chunk += ","
            chunk += rows[i]
        chunk += "]"

        self.positions[index] = end
        var remaining = total - end

        return (
            '{"chunk":'
            + chunk
            + ',"rows":'
            + String(end - position)
            + ',"position":'
            + String(end)
            + ',"remaining":'
            + String(remaining)
            + ',"done":'
            + ("true" if remaining == 0 else "false")
            + "}"
        )

    fn close_from_json(mut self, raw: String) -> String:
        var cursor = json_get_string(raw, "cursor")
        if len(cursor) == 0:
            return _stream_error("invalid_arguments", "stream_close requires a cursor.")
        var index = self._index_of(cursor)
        if index < 0:
            return _stream_error("cursor_not_found", "no open cursor " + cursor + ".")

        var cursors = List[String]()
        var handles = List[String]()
        var positions = List[Int]()
        var chunks = List[Int]()
        for i in range(len(self.cursors)):
            if i == index:
                continue
            cursors.append(self.cursors[i])
            handles.append(self.handles[i])
            positions.append(self.positions[i])
            chunks.append(self.chunk_rows[i])
        self.cursors = cursors^
        self.handles = handles^
        self.positions = positions^
        self.chunk_rows = chunks^

        return '{"closed":true,"count":' + String(self.count()) + "}"
