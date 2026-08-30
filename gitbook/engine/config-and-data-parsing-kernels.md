---
icon: file-code
description: TOML and YAML config parsing with dot-notation lookups, an RFC 4180 CSV reader, a columnar DataFrame factory, and the zero-Python JSON codec that the engine's own dispatch layer decodes every runtime.execute() argument with.
---

# Config and data-parsing kernels

Six modules for getting structured text into the engine and back out again: two independent
config-file parsers (TOML, YAML) that both resolve dot-notation paths against the same flat
node-pool tree shape, an RFC 4180 CSV reader, a columnar `DataFrame` construction factory, and a
matched JSON reader/writer pair. All six are pure Mojo with zero Python imports — the same
constraint every kernel in this codebase runs under — and all six predate, and in one case
literally underlie, the JSON wire format `runtime.execute()` itself speaks. That last part is not
a metaphor: `json.parser`'s `json_get_array`/`json_array_len`/`json_array_get` are the actual
functions the generated dispatch layer calls to decode the argument list of every one of this
runtime's 643 contract modules, this family included.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

doc = runtime.execute("config.toml_parser", "toml_parse",
                      ["[server]\nport = 8080\ndebug = true"])["result"]
runtime.execute("config.toml_parser", "toml_get_int", [doc, "server.port", 0])["result"]
# 8080

row = {"__algenta_struct": "CSVRow", "v": [["Alice", "30", "95.5"], 3]}
runtime.execute("data.csv_parser", "csv_get_float", [row, 2, 0.0])["result"]
# 95.5
```

## The modules

| Module | What it does |
| --- | --- |
| `config.toml_parser` | Parses the config-file subset of TOML — `[section]`/`[section.sub]` headers, string/int/float/bool/array values, `#` comments — into a flat node-pool tree, with typed dot-notation accessors. |
| `config.yaml_parser` | Parses the config-file subset of YAML — indentation-nested maps, `- item` lists, string/int/float/bool/null scalars — into the same flat node-pool tree shape as `config.toml_parser`, with the same dot-notation accessor names. |
| `data.csv_parser` | An RFC 4180 CSV field parser (quoted fields, escaped `""`, commas and newlines inside quotes) plus typed field accessors and a CSV-to-JSON-array converter. |
| `data.dataframe` | A columnar `Column`/`DataFrame` primitive with select, filter, sort, group-by, merge, and descriptive-stats methods in the Mojo source; only its `df_from_columns` construction factory is reachable through `runtime.execute`. |
| `json.parser` | Schema-aware JSON field extraction that walks raw bytes without building a DOM — and doubles as the argument decoder the engine's own generated dispatch layer runs on. |
| `json.writer` | A functional-builder JSON serializer (`json_object_start` → chained `json_add_*` → `json_object_end`) — `json.parser`'s write-side sibling, but *not* the code path the dispatch layer's own responses are built with (see below). |

## `config.toml_parser` and `config.yaml_parser`: two parsers, one tree shape

| Function | What it does |
| --- | --- |
| `toml_parse(content)` / `yaml_parse(content)` | Parse the whole document into a `TomlDoc`/`YamlDoc`: a flat pool of scalar/map/list nodes plus a root index. |
| `toml_get_string(doc, path)` / `yaml_get_string(doc, path)` | Resolve a dot-notation path (`"server.port"`) to a scalar node's raw text. `""` if the path doesn't resolve to a scalar. |
| `toml_get_int` / `yaml_get_int` `(doc, path, default)` | `atol()` the resolved string; `default` if the path is missing or the text doesn't parse. |
| `toml_get_float` / `yaml_get_float` `(doc, path, default)` | Same, via `atof()`. |
| `toml_get_bool` / `yaml_get_bool` `(doc, path, default)` | `"true"`/`"True"` → `True`, `"false"`/`"False"` → `False`; YAML additionally accepts `yes`/`on` and `no`/`off` in either case. TOML does not. |

Both parsers build the identical tree shape — a node is a scalar, a map (parallel `map_keys`/
`map_vals` arrays), or a list (`list_vals`) — and both accessor families walk it with the same
dot-split-and-descend logic, so the same config expressed in either format resolves the same way.
Parsing `"[server]\nport = 8080\ndebug = true"` as TOML and `"server:\n  port: 8080\n  debug:
true"` as YAML both produce a root map with one key, `"server"`, pointing at a submap holding
`port` and `debug` as scalar children — `toml_get_int(doc, "server.port", 0)` and
`yaml_get_int(doc2, "server.port", 0)` both return `8080` from their respective trees, traced by
hand against `toml_parser.mojo`'s and `yaml_parser.mojo`'s real line-splitting and section/indent
logic.

{% hint style="info" %}
**A `TomlDoc`/`YamlDoc` argument is a struct literal you build yourself, not just a value you pass
through.** The runtime's struct-marshaling convention wraps `toml_parse`'s result as
`{"__algenta_struct":"TomlDoc","v":[pool_json, root_int]}`, and that is exactly the shape
`toml_get_string` and friends expect back as their `doc` argument — so the natural pattern is
`doc = runtime.execute(...,"toml_parse",[content])["result"]` followed by
`runtime.execute(...,"toml_get_int",[doc, path, default])`, never hand-assembling the pool
yourself. Both `_toml_resolve` and `_resolve_path` (the YAML equivalent) guard every pool index
against the pool's real length before indexing, specifically because a hand-built or corrupted
document can otherwise carry a root or child index that points outside the pool — an unguarded
subscript there aborts the whole worker rather than returning "not found," per the comment left in
both functions.
{% endhint %}

## `data.csv_parser` and `data.dataframe`: rows and columns, mostly walled off from `runtime.execute`

| Function | What it does |
| --- | --- |
| `csv_get_field(row, index)` | Field at `index` from a parsed `CSVRow`. `""` if `index` is out of bounds. |
| `csv_get_float(row, index, default=0.0)` | Field as `Float64`, only if the whole field text is numeric (`_can_parse_float` requires the entire trimmed field to be a valid number, not just a numeric prefix); `default` otherwise. |
| `csv_get_int(row, index, default=0)` | Same, via `_can_parse_int`. |
| `csv_to_json_array(headers, rows)` | Renders parsed rows as a JSON array of objects, `headers[j]` (or `"col" + j` past the header count) mapped to `rows[i].fields[j]` — every value comes out as a JSON *string*, since CSV fields are raw text and this function does no type inference. |
| `df_from_columns(names, cols)` | Build a `DataFrame` from parallel `names: List[String]` and `cols: List[List[Float64]]` — the only `data.dataframe` function registered in the runtime dispatch table. |

**The CSV parser's entry points — `parse_csv` and `parse_csv_row`, which are what actually turn
CSV text into a `CSVRow`/`CSVResult` — are not in the runtime contract.** Only the four accessor
functions above are dispatchable. A caller reaching `csv_get_field` through `runtime.execute` has
to construct the `CSVRow` struct literal directly, the same way a parsed one would be serialized:
`{"__algenta_struct": "CSVRow", "v": [fields_list, n_fields]}`. The worked example at the top of
this page does exactly that — `csv_get_float(row, 2, 0.0)` on
`{"v": [["Alice", "30", "95.5"], 3]}` returns `95.5`, matching `test_csv_basic` in
`tests/mojo/test_wave2.mojo`, which parses `"name,age,score\nAlice,30,95.5\n..."` internally (in
Mojo, via `parse_csv`, not through the dispatch layer) and asserts the same field decodes to the
same float.

**`data.dataframe`'s real surface is much larger than what `runtime.execute` can reach.** Reading
`mojo/engine/data/dataframe.mojo`, `DataFrame` has around thirty methods — `select`, `drop`,
`slice_rows`, `filter_gt`/`filter_lt`/`filter_eq`/`filter_between`, `sort_by`, `sum`/`mean_col`/
`std_col`/`min_col`/`max_col`, `groupby_agg`, `add_computed_column`, `apply_scalar`,
`merge_inner`, `to_json`, `to_csv`, `head`, `describe`, `shape` — a genuine columnar
pandas-replacement, and `tests/mojo/test_wave4.mojo` pins real numeric behavior for all of it (a
five-row frame with `age`/`score`/`dept` columns: `mean_col("age")` ≈ `28.6`,
`std_col("age")` ≈ `4.159`, `groupby_agg("dept", "score", "mean")` splits into `91.667` and
`82.5` per department). None of those methods appear in `runtime_library_dispatch_generated.mojo`'s
`_dispatch_data__dataframe` — only `df_from_columns` is registered there. Building
`df_from_columns(["x", "y"], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])` through `runtime.execute` returns
a `DataFrame` struct token (`result["v"] = [columns, n_cols, n_rows, col_names]`, so
`result["v"][1:3] == [2, 3]`) that a caller can inspect, but has no further contract-level
operation to hand it to — the rest of the DataFrame API is exercised from Mojo source that
constructs and consumes `DataFrame` values directly, not from a `runtime.execute` caller.

{% hint style="info" %}
**This is a different, lower-level thing than the `dataframe-groupby` benchmark or
`Query.group_by()`.** [Dataframe group-by](../benchmarks/dataframe-groupby.md) and
[Group data locally with Query.group_by()](../guides/local-query-groupby.md) measure and use
`algenta.Query`'s composed dense/packed/fused-radix aggregate engine — a separate system that
never imports `data.dataframe` and isn't reachable through it. `data.dataframe`'s `Column`/
`DataFrame` structs and their group-by are a standalone, single-threaded columnar primitive one
level below that; the module name and the general shape of "columns, filter, group-by" are the
only things the two share.
{% endhint %}

## `json.parser` and `json.writer`: the same grammar, read and written asymmetrically

| Function | What it does |
| --- | --- |
| `find_key(data, key)` | Scan a JSON object's top level for `key`'s value position, skipping nested objects/arrays and strings correctly. `-1` if absent. |
| `skip_json_value(data, pos)` / `skip_whitespace(data, pos)` | Advance `pos` past one complete JSON value, or past whitespace — the primitives `find_key` and the array walkers below are built from. |
| `json_get_string`/`json_get_float`/`json_get_int`/`json_get_bool`/`json_is_null` `(raw, key[, default])` | Typed field extraction by key; each calls `find_key` once and parses in place. |
| `json_get_object` / `json_get_array` `(raw, key)` | Extract a nested object or array as its raw JSON substring (not parsed further). |
| `json_array_len(arr)` / `json_array_get(arr, index)` | Count or index into a JSON array string. `json_array_get` re-scans from the start on every call. |
| `json_array_tokens(arr)` | Split a JSON array into all its element strings in one `O(n)` pass — the fix for `json_array_get`'s per-index `O(n)` rescan, which made an `n`-element array `O(n²)` to walk. |
| `json_decode_base64_bytes(s)` | Standard base64 → raw bytes, one pass. |
| `json_parse_float64_list(token)` | Parse a `List[Float64]` argument, with a `"@u8:<base64>"` fast path that decodes a token as raw `uint8` pixel bytes instead of per-element text parsing — about 13x smaller on the wire than a JSON number array for image kernels. |
| `json_object_start()` / `json_object_end(s)` | Begin (`"{"`) / close a JSON object, stripping the trailing comma the `json_add_*` chain leaves behind. |
| `json_add_string`/`json_add_int`/`json_add_float`/`json_add_bool`/`json_add_null` `(s, key, value)` | Append one typed `"key":value,` field. |
| `json_add_array_float` / `json_add_array_string` `(s, key, values)` | Append an array-valued field. |
| `json_add_raw(s, key, raw_json)` | Append a pre-built JSON fragment verbatim, unescaped. |
| `json_build_object(pairs)` | Build `{...}` directly from a `List[List[String]]` of `[key, pre-formatted-value]` pairs. |
| `json_escape_string(s)` | `\"` `\\` `\n` `\r` `\t` `\b` `\f`, plus `\u00XX` for any other control byte under `0x20`. |

```python
raw = ('{"scoring":{"expected_value":0.6,"downside_risk":0.4},'
       '"variables":[{"name":"x"},{"name":"y"}]}')
runtime.execute("json.parser", "json_get_object", [raw, "scoring"])["result"]
# '{"expected_value":0.6,"downside_risk":0.4}'
runtime.execute("json.parser", "json_array_len",
                [runtime.execute("json.parser", "json_get_array", [raw, "variables"])["result"]])["result"]
# 2
```

That shape — a `scoring` object with `expected_value`/`downside_risk`, plus a `variables` array —
isn't invented for this page; it's the literal structure and field names
`request_parser.mojo` pulls out of an incoming decision-engine request with this same sequence
(`json_get_object(raw, "scoring")` then `json_get_float(scoring_str, "expected_value", 0.6)` and
`json_get_float(scoring_str, "downside_risk", 0.4)`; `json_get_array(raw, "variables")` then
`json_array_len`/`json_array_get` over it).

**`json.parser` really is the engine's own argument decoder, and `json.writer` is *not* its
response encoder — an asymmetry worth being precise about.**
`runtime_library_dispatch_generated.mojo` imports `json_get_array`, `json_array_len`,
`json_array_get`, `json_get_string`, `json_array_tokens`, and `json_parse_float64_list` from
`json.parser` unaliased at the top of the file, and every one of that file's `_parse_*_token`
struct-decoding helpers — `_parse_tomldoc_token`, `_parse_csvrow_token`, and hundreds more, one per
contract struct — is built from them; `json_array_get` alone has over 17,000 call sites in that
generated file, one for each positional argument of each dispatchable function across all 643
contract modules. `json.writer`'s functions are imported too, but only inside the `json.writer`
module's *own* dispatch case (`_dispatch_json__writer`) — the code that actually serializes every
function's *result* (`_success_json`, `_to_json_string`, `_to_json_tomldoc`, and one `_to_json_*`
per struct) is a separate, independently hand-written string-concatenation path with its own
`_escape_json_string` helper, and never calls `json_object_start` or `json_add_string`. Both sides
speak the same JSON grammar, and `json.parser` can read what either path writes, but only the
reader half is shared engine machinery — the writer half most callers see (results coming back
from `runtime.execute`) is a different, parallel implementation from `json.writer`.

**The bare-word tokenizer inside `skip_json_value` exists because of a real production bug.** A
comment in `json/parser.mojo` documents it: an older version skipped alphabetic tokens a
fixed number of characters at a time with a one-character fallback, which shredded `"Infinity"`
(from a lenient serializer emitting a non-finite float) into eight separate one-character
elements, corrupting downstream list lengths — measured as `risk.beta` aborting inside its own
covariance computation on a request carrying `[1.0, NaN, Infinity, -Infinity, 0.0]`. The fix scans
the whole alphabetic run as one token before deciding what to do with it, and a `-` immediately
followed by letters (`-Infinity`) is likewise kept as one token rather than split into a bare minus
and a word.

## Verification

`config.toml_parser`, `config.yaml_parser`, `json.parser`, and `json.writer`'s tests in
`mojo/tests/libs/` are auto-generated coverage smoke tests: each calls every function once with the
literal string `"test"` (or a fixed numeric default for typed arguments) and checks only that
`toml_parse`/`yaml_parse` don't raise, or that a numeric result is finite — none of the four pins a
specific parsed value. `data.csv_parser` and `data.dataframe` are the exception: they have no file
under `mojo/tests/libs/`, and instead get real, hand-verified numeric coverage from
`tests/mojo/test_wave2.mojo` (quoted fields, escaped `""`, out-of-bounds defaults, no-header mode)
and `tests/mojo/test_wave4.mojo` (aggregate, filter, sort, group-by, merge, and the
`df_from_columns` factory all checked against worked-by-hand numbers). Every TOML/YAML/JSON
worked example above was hand-traced against the real parsing logic in `toml_parser.mojo`,
`yaml_parser.mojo`, `json/parser.mojo`, and `json/writer.mojo`, and each one is reproducible by
re-running the same steps.

**Next:** see [Data quality](data-quality.md) for what runs on the numeric data these parsers feed
in, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and
function.
