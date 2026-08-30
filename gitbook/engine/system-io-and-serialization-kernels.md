---
icon: toolbox
description: Environment-variable access, pure-string path and URL parsing, weighted/stratified random sampling, MessagePack binary serialization, and the histogram/dedup pair a richer, mostly-undispatchable container module actually exposes.
---

# System I/O and serialization kernels

Six modules that don't share a numerical domain so much as a job: get a value in or out of the
process without leaning on Mojo's own standard library for it. `env` reads process environment
variables — the only module on this page that touches Python at all. `filepath.pathlib` and
`net.url` parse and reassemble filesystem paths and URLs as pure string operations, with zero
filesystem or network calls of their own. `random_utils` extends `std.random`'s single uniform
generator into the sampling primitives a Monte Carlo caller actually needs — weighted choice,
shuffle, bootstrap, stratified sampling. `serialization.msgpack` is a from-scratch MessagePack
encoder/decoder that picks the most compact wire tag for each value. And `structs.containers`,
despite its name, is mostly a module the runtime contract doesn't expose: its real Mojo source
defines a min-heap, a ring buffer, and a sorted list, but only two free functions —
`counter` and `unique` — are registered in the dispatch table `runtime.execute` actually calls
into.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("filepath.pathlib", "path_normalize", ["/usr/local/../bin"])["result"]
# "/usr/bin" -- ".." pops the preceding component; the root itself is never popped past

runtime.execute("serialization.msgpack", "msgpack_encode_int", [200])["result"]
# [204, 200] -- 200 doesn't fit a positive fixint (0-127), so it's tagged 0xcc (204) + the byte
```

## The modules

| Module | What it does |
| --- | --- |
| `env` | reads process environment variables through Python's `os.environ`, with typed `_int`/`_float`/`_bool` accessors and an existence check |
| `filepath.pathlib` | pure-string path manipulation (join, split, basename, dirname, extension, stem, absolute check, `.`/`..` normalization) with zero filesystem calls |
| `net.url` | URL parsing into a `URL` struct, reconstruction back to a string, percent-encode/decode, and query-string parse/get/build |
| `random_utils` | weighted choice, Fisher-Yates shuffle, sampling with and without replacement, a uniform random integer, a random permutation, and stratified sampling, all built on `std.random`'s one uniform generator |
| `serialization.msgpack` | a MessagePack encoder/decoder for ints, floats, strings, bools, nil, and array/map headers, each choosing the most compact wire format for its value |
| `structs.containers` | a min-heap, ring buffer, and sorted list in the Mojo source, plus the two functions the runtime contract actually exposes: `counter` (histogram binning) and `unique` (sorted dedup) |

## `env`: read-once-at-startup config, not hot-path code

The module's own docstring says as much: it is "designed for read-once-at-startup config, not
hot-path code," and it is the one module in this family that imports Python
(`Python.import_module("os")`) — every other module here runs with zero Python imports.

| Function | What it does |
| --- | --- |
| `env_get(key, default="")` | Raw string value, or `default` if the variable is unset. |
| `env_get_int(key, default=0)` | Parses the value with `conv.parse_int`; `default` if unset, empty, or unparsable. |
| `env_get_float(key, default=0.0)` | Same, via `conv.parse_float64`. |
| `env_get_bool(key, default=False)` | Case-insensitive `"true"`/`"1"`/`"yes"` → `True`; `"false"`/`"0"`/`"no"`/`""` → `False`; anything else → `default`. |
| `env_is_set(key)` | `True` if the key exists in the environment at all, regardless of its value. |

```python
runtime.execute("env", "env_get", ["PATH", ""])["result"]
# the process PATH -- non-empty on any real machine

runtime.execute("env", "env_get", ["NONEXISTENT_VAR_12345", "default"])["result"]
# "default"
```

Both lines above are the literal assertions `tests/mojo/test_wave8.mojo` pins: `env_get("PATH",
"")` is checked non-empty, `env_is_set("PATH")` is `True`, `env_is_set("NONEXISTENT_VAR_12345")`
is `False`, and each `env_get_*` variant returns its supplied default for that same nonexistent
key.

{% hint style="warning" %}
**A variable set to the empty string is not treated the same way by all four accessors.**
`env_get`'s guard only falls back to `default` when the key doesn't exist at all
(`_env_has(key)` is `False`) — a variable explicitly exported as `FOO=""` makes `env_get` return
`""`, not `default`. `env_get_int` and `env_get_float` read the source differently: both return
`default` whenever the raw value has zero length, *whether or not the key exists* — so
`FOO=""` with `env_get_int("FOO", 42)` returns `42`, not `0`. `env_get_bool` differs a third way:
its early-return guard only fires for a truly-unset key, but `""` is also explicitly listed as
falsy further down, so `FOO=""` with `env_get_bool("FOO", True)` returns `False` — silently
overriding the caller's own requested default. Three functions, three different answers for the
same input shape, all read directly from `env.mojo`'s bodies rather than from any shared
"unset vs. empty" convention.
{% endhint %}

## `filepath.pathlib`: string surgery, no filesystem underneath

Every function operates on the path text alone — `path_is_absolute` never checks whether the path
exists, and `path_normalize` never resolves symlinks; it only collapses `.` and `..` lexically.
The eight functions and their real, test-pinned values (`tests/mojo/test_wave6.mojo`, on
`/usr/local/bin/mojo` and related paths):

| Function | Worked example |
| --- | --- |
| `path_basename(path)` | `path_basename("/usr/local/bin/mojo")` → `"mojo"` |
| `path_dirname(path)` | `path_dirname("/usr/local/bin/mojo")` → `"/usr/local/bin"`; `path_dirname("file.txt")` → `"."` (no directory component) |
| `path_extension(path)` | `path_extension("file.mojo")` → `".mojo"`; `path_extension("Makefile")` → `""` (no dot at all) |
| `path_stem(path)` | `path_stem("file.mojo")` → `"file"` |
| `path_is_absolute(path)` | `path_is_absolute("/usr/bin")` → `True`; `path_is_absolute("relative/path")` → `False` |
| `path_join(parts)` | `path_join(["usr", "local", "bin"])` → `"usr/local/bin"` |
| `path_split(path)` | `path_split("/usr/local/bin")` → `["/", "usr", "local", "bin"]` (4 elements; a leading `/` becomes its own element) |
| `path_normalize(path)` | `path_normalize("/usr/local/../bin")` → `"/usr/bin"`; `path_normalize("/a/b/c/../../d")` → `"/a/d"` |

Two edge cases fall out of reading the source directly rather than the pinned test, and were
hand-traced against `pathlib.mojo`'s real logic before being stated here:

- **A leading dot doesn't count as an extension marker.** `path_extension` and `path_stem` both
  guard `last_dot <= 0` — a dot at position `0` (a hidden file) is treated as "no extension," so
  `path_extension(".bashrc")` is `""` and `path_stem(".bashrc")` returns the whole name unchanged,
  `.bashrc"`, rather than splitting it into a stem and an extension.
- **`path_normalize` resolves `..` differently for absolute and relative paths.** For an absolute
  path, a `..` that would walk above the root is simply dropped — `/a/b/c/../../d` collapses to
  `/a/d`, never `/../d`. For a relative path there is no known root to walk above, so an excess
  `..` is kept literally instead of discarded: tracing the algorithm on `"a/../../b"` step by
  step — `a` pushed, the first `..` pops it back off, the second `..` finds nothing left to pop
  and is appended as-is, `b` is pushed after it — produces `"../b"`, a real upward reference the
  absolute-path case would never emit for the equivalent input.

## `net.url`: authority-form URLs, not general URIs

`URL` is a plain six-field struct (`scheme`, `host`, `port`, `path`, `query`, `fragment`); `port`
defaults to `0`, meaning "unspecified" — `url_parse` never infers `80` or `443` from the scheme,
and `url_to_string` only emits `:port` when `port > 0`, so a URL parsed without an explicit port
round-trips without one too.

```python
u = runtime.execute("net.url", "url_parse",
    ["https://api.example.com:8443/v1/simulate?mode=auto&runs=10000#results"])["result"]
u["v"]
# ["https", "api.example.com", 8443, "/v1/simulate", "mode=auto&runs=10000", "results"]

runtime.execute("net.url", "query_get", [u["v"][4], "mode"])["result"]
# "auto"

runtime.execute("net.url", "url_encode", ["hello world"])["result"]
# "hello%20world"
runtime.execute("net.url", "url_decode", ["hello%20world"])["result"]
# "hello world"
```

The parse/split/encode/decode behavior above is exercised by `tests/mojo/test_wave7.mojo` (with a
neutral placeholder host substituted here for the test's own literal string), including the
round-trip check (`url_to_string(url_parse("https://example.com/path"))` reproduces the original
string exactly) and the port-omitted case (`url_parse("http://example.com/test").port == 0`).

{% hint style="info" %}
**Percent-decoding is not automatic past `url_decode` itself.** `url_parse` populates `.query`
with the raw, still-percent-encoded query substring, and `query_parse`/`query_get` split and
look up keys against that raw text with plain substring operations — neither one calls
`url_decode`. A query value containing `%20` or `%40` comes back from `query_get` exactly as
written; a caller who wants it decoded has to call `url_decode` on that specific piece
themselves. The reverse composition has its own asymmetry too: `url_decode` treats `+` as a
decoded space (the classic form-encoding convention), but `url_encode` never *produces* a `+` —
it always emits `%20` for a literal space — so `url_encode` and `url_decode` are not perfect
inverses on that one character.
{% endhint %}

`url_parse`'s own docstring is explicit that it "handles: `scheme://host[:port][/path][?query]
[#fragment]`" — an authority-form URL. Feeding it a colon-scheme URI with no `//`, like
`"mailto:foo@bar.com"`, is outside that shape and gets silently misread rather than rejected:
tracing `url_parse` on that string by hand — no `"://"` means `scheme` stays `""`; no `/`
means the whole string becomes the "authority"; the *last* colon in `"mailto:foo@bar.com"` is the
one right after `mailto`, so `host` becomes `"mailto"` and the port-parser is handed
`"foo@bar.com"`, whose leading non-digit character makes `_string_to_int` return `0` immediately.
The result is `{scheme: "", host: "mailto", port: 0, path: "", query: "", fragment: ""}` — a
parse that completes without error and is simply the wrong shape for that input, not a crash the
caller would notice.

## `random_utils`: sampling built on one uniform generator, no seed anywhere

Every function here calls `std.random.random_float64()` directly or indirectly; none of the seven
contract functions takes a seed argument, so there is no way to make two calls reproduce the same
draw through `runtime.execute` — determinism has to come from the caller re-deriving the same
random state some other way, not from this module.

| Function | What it does |
| --- | --- |
| `random_choice(weights)` | Weighted-index draw: normalizes `weights` implicitly by walking the cumulative sum against one uniform draw scaled by the total. |
| `random_shuffle(data)` | In-place Fisher-Yates shuffle. **Mutates its argument** (see below). |
| `random_sample(data, n)` | `n` items without replacement, via a partial Fisher-Yates; if `n >= len(data)`, returns a shuffled copy of everything. |
| `random_bootstrap(data, n)` | `n` items *with* replacement — classic bootstrap resampling. |
| `random_uniform_int(low, high)` | A uniform integer in `[low, high)`; returns `low` unchanged if `low >= high`. |
| `random_permutation(n)` | A random ordering of `0, 1, ..., n-1`, via Fisher-Yates on an identity list. |
| `stratified_sample(data, n_strata)` | Splits `data` into `n_strata` equal-ish contiguous strata and draws one random element from each — `data` should be pre-sorted for this to mean anything, since the strata are just slices of the list as given. |

`tests/mojo/test_wave10.mojo` pins the shape of every draw rather than a specific value, since the
values are non-deterministic by construction: `random_choice` on two weights returns `0` or `1`;
`random_permutation(5)` has length `5`; `random_sample(data, 3)` has length `3`;
`random_bootstrap(data, 10)` has length `10`; `random_uniform_int(10, 20)` lands in `[10, 20)`;
`stratified_sample(data, 3)` has length `3`.

{% hint style="warning" %}
**`random_shuffle` is the one function on this page whose result comes back through
`mutated_args`, not `result`.** Its contract signature declares `data` as a mutable parameter and
returns `None` — the dispatch layer surfaces the shuffled list as a mutation on argument `0`, the
same convention [Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md) documents
for `graph_add_edge`'s mutated graph:

```python
response = runtime.execute("random_utils", "random_shuffle", [[1.0, 2.0, 3.0, 4.0, 5.0]])["result"]
response["result"]                  # None -- the declared return type
shuffled = response["mutated_args"]["data"]   # the actual shuffled list
```

Calling `response["result"]` and expecting the shuffled list, rather than reading
`response["mutated_args"]["data"]`, silently gets `None` instead of an error.
{% endhint %}

## `serialization.msgpack`: the standard wire format, picking the smallest tag per value

Every `msgpack_encode_*` function chooses the most compact tag the MessagePack spec allows for
its value's magnitude; every `msgpack_decode_*` function reads a tag at `pos` and returns a
`{value, consumed}` result struct so a caller can walk a buffer of concatenated values without
tracking offsets by hand. `tests/mojo/test_wave5.mojo` round-trips each of the values below and
pins the encoded bytes; the bytes are also independently reproducible from the tag ranges in
`msgpack.mojo` itself:

| `msgpack_encode_int(v)` | Encoded bytes | Format |
| --- | --- | --- |
| `42` | `[42]` | positive fixint (`0`–`127` encode as the byte itself) |
| `0` | `[0]` | positive fixint |
| `-5` | `[251]` | negative fixint (`-32`–`-1` encode as `v + 256`) |
| `200` | `[204, 200]` | `uint8` (`0xcc` + the byte, for `128`–`255`) |
| `1000` | `[205, 3, 232]` | `uint16` (`0xcd` + 2 big-endian bytes) |
| `-100` | `[208, 156]` | `int8` (`0xd0` + `v + 256`, for `-128`–`-33`) |

`msgpack_encode_float(3.14)` always uses the 8-byte `float64` tag (`0xcb`) — the module has no
compact `float32` path on the *encode* side, even for a value that would round-trip cleanly as
one — so `msgpack_decode_float` reports `consumed == 9` (1 tag byte + 8 data bytes) for every
encoded float, exactly as `test_wave5.mojo` checks. `msgpack_decode_float` itself is more general
than the encoder: it also accepts an incoming `0xca` (`float32`) tag from some other encoder,
consuming 5 bytes — a decode-side capability this module's own encoder never exercises.
`msgpack_encode_string("hello")` produces a 1-byte `fixstr` header (`0xa5`) plus the 5 UTF-8 bytes,
`consumed == 6`; `msgpack_encode_bool(True)`/`(False)` are the single bytes `0xc3`/`0xc2`;
`msgpack_encode_nil()` is `0xc0`; `msgpack_encode_array_header(3)` is the single `fixarray` byte
`0x93`; `msgpack_encode_map_header(2)` is the single `fixmap` byte `0x82`.

{% hint style="info" %}
**The decode side only covers three of the seven encoded shapes.** `msgpack_decode_int`,
`msgpack_decode_float`, and `msgpack_decode_string` exist; there is no
`msgpack_decode_bool`, `msgpack_decode_nil`, `msgpack_decode_array_header`, or
`msgpack_decode_map_header` anywhere in `msgpack.mojo` — not merely absent from the runtime
contract, absent from the module entirely. A caller walking a buffer that mixes bools, nil, or
container headers has to branch on the raw tag byte itself (`data[pos]`) rather than calling a
matching decoder, since none is provided for those four shapes.

Every decode function also guards `pos < 0 or pos >= len(data)` and returns a zero-valued result
with `consumed == 0` rather than indexing out of bounds — the source comments name the reason
directly: "a negative pos would read data out of bounds — an uncatchable abort," the same class
of unrecoverable worker crash a bad count argument triggers elsewhere in this codebase. A caller
should treat `consumed == 0` as "decode failed here," not assume every call succeeds.
{% endhint %}

## `structs.containers`: three real structs the dispatch table can't reach

Reading `mojo/engine/structs/containers.mojo` directly turns up a `MinHeap` (binary min-heap:
`push`, `pop`, `peek`, `size`), a `RingBuffer` (fixed-capacity circular buffer: `push`, `get`,
`mean`, `is_full`, `size`), and a `SortedList` (binary-search insert: `insert`, `get`, `median`,
`remove`, `size`) — all three genuinely implemented, and all three exercised with real, pinned
numbers in `tests/mojo/test_wave7.mojo`. None of the three appears in
`runtime_library_dispatch_generated.mojo`'s `_dispatch_structs__containers` — only `counter` and
`unique` are registered there, matching the two entries in `runtime_library_contract.json`. This
is the same shape of gap [Config and data-parsing kernels](config-and-data-parsing-kernels.md)
documents for `data.dataframe`, whose thirty-odd `DataFrame` methods are real and tested but only
`df_from_columns` is reachable through `runtime.execute` — here it is a heap, a ring buffer, and a
sorted list playing the same role, real and tested but invisible to a caller going through the
dispatch layer.

`test_wave7.mojo`'s pinned numbers for the three structs, for reference (not reachable via
`runtime.execute`, but real): a `MinHeap` pushed `5.0, 2.0, 8.0, 1.0` peeks `1.0` and pops
`1.0` then `2.0`, leaving `size() == 2`. A `RingBuffer(3)` pushed `1.0, 2.0, 3.0` is full with
`mean() == 2.0`; pushing a fourth value `4.0` overwrites the oldest (`1.0`), leaving `mean() ==
3.0` and `get(0) == 2.0` (now-oldest), `get(2) == 4.0` (newest). A `SortedList` given `5.0, 1.0,
3.0, 2.0, 4.0` in that order reports `get(0) == 1.0`, `get(4) == 5.0`, `median() == 3.0`; removing
index `2` (the middle value, `3.0`) drops `size()` to `4` and leaves `median() == 3.0` again, the
average of the new middle pair `[2.0, 4.0]`.

The two dispatchable functions, worked by hand on the same five-value fixture
(`[0.5, 0.6, 0.7, 0.4, 0.3]`) every auto-generated smoke test in this codebase shares:

```python
data = [0.5, 0.6, 0.7, 0.4, 0.3]

runtime.execute("structs.containers", "counter", [data, 3])["result"]
# [2, 1, 2] -- 3 equal-width bins over [0.3, 0.7]: {0.4, 0.3} low, {0.5} mid, {0.6, 0.7} high

runtime.execute("structs.containers", "unique", [data])["result"]
# [0.3, 0.4, 0.5, 0.6, 0.7] -- already all-distinct, so this is just a sort
```

`counter` finds the data's own `[min, max]` range (here `[0.3, 0.7]`, span `0.4`) and divides it
into `bins` equal-width buckets; a value exactly on the top edge is clamped into the last bucket
rather than overflowing past it. `unique` sorts a copy (insertion sort) and then drops consecutive
duplicates in one pass — order comes out ascending regardless of the input order, which is why an
already-sorted, already-distinct input like the one above just comes back unchanged.

## Verification

All six `mojo/tests/libs/test_*.mojo` files behind this page (`test_env.mojo`,
`test_filepath_pathlib.mojo`, `test_net_url.mojo`, `test_random_utils.mojo`,
`test_serialization_msgpack.mojo`, `test_structs_containers.mojo`) are auto-generated coverage
smoke tests: each calls every function once against the same shared fixture values used across
the whole `tests/libs` directory and checks only that the call completes and the result is
finite, non-negative-length, or otherwise well-formed — none of them pins a specific numeric
answer. The real, hand-written pinned coverage instead lives in `tests/mojo/test_wave5.mojo`
(msgpack), `test_wave6.mojo` (pathlib), `test_wave7.mojo` (structs.containers and net.url),
`test_wave8.mojo` (env), and `test_wave10.mojo` (random_utils) — every worked value on this page
taken from a test is taken from one of those five files. The `path_normalize` relative-path
trace, the `mailto:` `url_parse` trace, and the `counter`/`unique` three-bin example are not in
any test file; they were hand-traced against the real bodies in `pathlib.mojo`, `url.mojo`, and
`containers.mojo` and are reproducible by re-running the same steps.

**Next:** see [Config and data-parsing kernels](config-and-data-parsing-kernels.md) for the other
family whose real Mojo source is larger than its dispatchable surface, or
[Exact numerics and graph kernels](exact-numerics-and-graph-kernels.md) for the `mutated_args`
calling convention `random_shuffle` shares with `graph_add_edge`.
