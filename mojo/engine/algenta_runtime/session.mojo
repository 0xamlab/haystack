"""
algenta_runtime.session — keep a dataset resident in the worker. Zero Python.

Why
---
Batching removes per-call frame cost; pipelines keep intermediates inside the
worker. Neither helps when the *input* is large: every call that needs a dataset
re-ships it, so a 100k-row array sent to twenty kernels crosses the boundary twenty
times and is re-parsed twenty times.

A session breaks that. Send the dataset once, get a handle, then address it by
handle. Per-call payload becomes O(1) in the number of rows rather than O(rows),
which is a bigger effect than anything batching can achieve — and unlike a
zero-copy pointer scheme it needs no FFI, no shared-library ABI, and no change to
the frame protocol.

The pattern already exists here: main.mojo holds `ResidentColumnRankState` across
the whole connection loop, with `column_rank_init` / `_query` / `_batch` as its
message trio. This generalises it to arbitrary named JSON values so any kernel can
use it.

Lifetime
--------
State lives for the connection, not the process: the registry is created inside
`run_server_loop` and dropped when the loop exits. Handles are opaque strings and
never reused within a registry, so a stale handle from a previous connection fails
cleanly with `dataset_not_found` instead of silently reading someone else's data.

A byte cap bounds total residency. `dataset_open` past the cap fails with
`dataset_capacity_exceeded` rather than evicting: silent eviction would turn a
handle the caller still holds into a confusing not-found later, at a point far from
the cause.

Wire format
-----------
    {"type":"dataset_open","name":"sales","value":[1.0,2.0,3.0]}
      -> {"handle":"ds_1","name":"sales","bytes":13,"count":1}

    {"type":"dataset_close","handle":"ds_1"}  -> {"closed":true,"count":0}
    {"type":"dataset_list"}                   -> {"datasets":[...],"count":1,"bytes":13}

A resident value is referenced from a batch or pipeline argument as `"@ds_1"`,
mirroring the pipeline's `"$0"` node reference.
"""
from json.parser import json_get_array, json_get_object, json_get_string

# Total resident bytes per connection. Generous for real datasets while still
# bounding a single connection's memory.
alias MAX_RESIDENT_BYTES = 512 * 1024 * 1024


fn _session_error(code: String, message: String) -> String:
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


fn _extract_value_json(raw: String) -> String:
    """The `value` field's raw JSON, whichever container it uses.

    Tried as array then object then string, so a dataset can be a list of rows, a
    record, or an opaque blob without the caller declaring which.
    """
    var as_array = json_get_array(raw, "value")
    if len(as_array) > 0:
        return as_array
    var as_object = json_get_object(raw, "value")
    if len(as_object) > 0:
        return as_object
    var as_string = json_get_string(raw, "value")
    if len(as_string) > 0:
        return '"' + as_string + '"'
    return ""


struct ResidentDatasets(Copyable, Movable):
    """Connection-scoped registry of named JSON values addressed by handle."""

    var handles: List[String]
    var names: List[String]
    var values: List[String]
    var next_id: Int
    var total_bytes: Int

    fn __init__(out self):
        self.handles = List[String]()
        self.names = List[String]()
        self.values = List[String]()
        self.next_id = 1
        self.total_bytes = 0

    fn count(self) -> Int:
        return len(self.handles)

    fn _index_of(self, handle: String) -> Int:
        for i in range(len(self.handles)):
            if self.handles[i] == handle:
                return i
        return -1

    fn lookup(self, handle: String) -> String:
        """Resident JSON for `handle`, or "" when absent."""
        var index = self._index_of(handle)
        if index < 0:
            return ""
        return self.values[index]

    fn open_from_json(mut self, raw: String) -> String:
        var value = _extract_value_json(raw)
        if len(value) == 0:
            return _session_error(
                "invalid_arguments", "dataset_open requires a non-empty value."
            )
        if self.total_bytes + len(value) > MAX_RESIDENT_BYTES:
            return _session_error(
                "dataset_capacity_exceeded",
                "resident datasets would exceed "
                + String(MAX_RESIDENT_BYTES)
                + " bytes; close a handle first.",
            )

        var name = json_get_string(raw, "name")
        var handle = "ds_" + String(self.next_id)
        self.next_id += 1
        self.handles.append(handle)
        self.names.append(name)
        self.total_bytes += len(value)
        self.values.append(value)

        return (
            '{"handle":"'
            + handle
            + '","name":"'
            + name
            + '","bytes":'
            + String(len(self.values[len(self.values) - 1]))
            + ',"count":'
            + String(self.count())
            + "}"
        )

    fn close_from_json(mut self, raw: String) -> String:
        var handle = json_get_string(raw, "handle")
        if len(handle) == 0:
            return _session_error("invalid_arguments", "dataset_close requires a handle.")
        var index = self._index_of(handle)
        if index < 0:
            return _session_error(
                "dataset_not_found", "no resident dataset for handle " + handle + "."
            )

        self.total_bytes -= len(self.values[index])
        # Rebuild without the closed entry: handles are never reused, so the gap
        # cannot be filled by a later open.
        var handles = List[String]()
        var names = List[String]()
        var values = List[String]()
        for i in range(len(self.handles)):
            if i == index:
                continue
            handles.append(self.handles[i])
            names.append(self.names[i])
            values.append(self.values[i])
        self.handles = handles^
        self.names = names^
        self.values = values^

        return '{"closed":true,"count":' + String(self.count()) + "}"

    fn list_json(self) -> String:
        var out = String('{"datasets":[')
        for i in range(len(self.handles)):
            if i > 0:
                out += ","
            out += (
                '{"handle":"'
                + self.handles[i]
                + '","name":"'
                + self.names[i]
                + '","bytes":'
                + String(len(self.values[i]))
                + "}"
            )
        out += (
            '],"count":'
            + String(self.count())
            + ',"bytes":'
            + String(self.total_bytes)
            + "}"
        )
        return out


fn is_dataset_reference(token: String) -> Bool:
    """True for a `"@handle"` argument token."""
    if len(token) < 4:
        return False
    var bytes = token.as_bytes()
    # 34 = '"', 64 = '@'
    if bytes[0] != 34 or bytes[len(token) - 1] != 34:
        return False
    return bytes[1] == 64


fn dataset_reference_handle(token: String) -> String:
    """The handle inside a validated `"@handle"` token."""
    var bytes = token.as_bytes()
    var handle = String("")
    for i in range(2, len(token) - 1):
        handle += chr(Int(bytes[i]))
    return handle
