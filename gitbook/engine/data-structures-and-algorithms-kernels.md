---
icon: list-ol
description: Binary heaps, a priority queue and circular buffer, a byte-level trie, six sorting algorithms, and sorted-list set operations -- pure-Mojo replacements for heapq, queue, pygtrie, sort, and set.
---

# Data structures and algorithms kernels

Five modules replacing Python's own container and algorithm primitives with pure Mojo:
`heapq`'s min-heap and max-heap, `queue`'s priority queue and a fixed-capacity ring buffer,
`pygtrie`'s prefix tree, `sorted()`'s comparison and counting sorts, and `set`'s union,
intersection, and membership operations. Every function operates on plain `List[Float64]`,
`List[Int]`, or `String` -- no NumPy, no Python container types -- and three of the five
modules (`heap`, `queue_ds`, `trie`) carry a mutable struct or list that a caller builds up
across several calls, which is a genuinely different calling shape from the stateless,
one-shot arithmetic in most of this corpus's other kernel families.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# quicksort([3, 1, 4, 1, 5]) -- the real pinned case in tests/mojo/test_wave33.mojo
runtime.execute("sorting", "quicksort", [[3.0, 1.0, 4.0, 1.0, 5.0]])["result"]
# [1.0, 1.0, 3.0, 4.0, 5.0]

# set_intersection assumes both inputs are already sorted -- see "set_ops" below
runtime.execute("set_ops", "set_intersection", [[1, 3, 5], [2, 3, 4]])["result"]
# [3]
```

## The modules

| Module | What it does |
| --- | --- |
| `heap` | Binary min-heap and max-heap array operations (`heapify`, push, pop, peek), plus `k_smallest`/`k_largest` selection, a k-way sorted-list merge, and a running median -- all on plain `List[Float64]` |
| `queue_ds` | A binary-heap-backed priority queue (`PriorityQueue`) and a fixed-capacity ring buffer (`CircularBuffer`), each an explicit struct the caller pushes and pops by value |
| `trie` | A prefix tree over UTF-8 **bytes**, stored as flat parallel arrays in a first-child/next-sibling layout, for exact-word and prefix search, counting, and listing |
| `sorting` | Six named sort algorithms (quicksort, mergesort, heapsort, insertion, selection, bubble) plus counting sort, `is_sorted`, `reverse_list`, and `nth_smallest` |
| `set_ops` | Union, intersection, difference, symmetric difference, subset/superset/equality checks, the Jaccard index, and binary-search membership -- all on sorted, deduplicated `List[Int]` |

## Mutation crosses the call boundary as a returned value, not a side effect

`heap`, `queue_ds`, and `trie` each declare some parameters `mut` in the contract (`heap` in
`heap_push_min`, `pq` in `pq_push`, `t` in `trie_insert`, and so on). There is no shared
process for the caller and the kernel to alias a pointer through, so the worker reports the
mutated value back explicitly, and the SDK surfaces it under `mutated_args`, keyed by
parameter name, one level inside the outer `execute()` call's own `"result"` key.

For a function whose own return type is `None` -- `heapify_min`, `heap_push_min`, `pq_push`,
`cb_push`, `trie_insert` -- the real output **is** `mutated_args`:

```python
h = [5.0, 3.0, 8.0, 1.0, 4.0]
resp = runtime.execute("heap", "heapify_min", [h])
resp["result"]["result"]                 # None -- heapify_min returns nothing
resp["result"]["mutated_args"]["data"]   # [1.0, 3.0, 8.0, 5.0, 4.0] -- the heapified list
```

For a function that **also** returns a value while mutating -- `heap_pop_min`, `pq_pop`,
`cb_pop` -- both keys are populated, and chaining calls means always re-reading the mutated
argument back out for the next call:

```python
h2 = []
for v in [5.0, 3.0, 7.0]:
    h2 = runtime.execute("heap", "heap_push_min", [h2, v])["result"]["mutated_args"]["heap"]
runtime.execute("heap", "heap_peek_min", [h2])["result"]   # 3.0

h2 = runtime.execute("heap", "heap_push_min", [h2, 1.0])["result"]["mutated_args"]["heap"]
runtime.execute("heap", "heap_peek_min", [h2])["result"]   # 1.0 -- the new value is now smallest

popped = runtime.execute("heap", "heap_pop_min", [h2])
popped["result"]["result"]                # 1.0 -- the value removed
h2 = popped["result"]["mutated_args"]["heap"]   # the heap with it gone; feed this into the next pop
```

`heap_peek_min`, `pq_peek`, `pq_size`, `is_min_heap`, and every function in `sorting` and
`set_ops` take no `mut` parameter at all, so their `"result"` is the plain value directly, the
same shape used throughout the rest of this corpus. Whether a given call needs the
`mutated_args` dance is a per-function fact, not a per-module one -- it is read off the
contract's `is_mut` flag on the specific parameter, not guessed from the module name.

## `heap`: five heap primitives, and three algorithms that live here because they need one

`heapify_min`/`heapify_max` build the property in place in O(n); `heap_push_min`/`heap_push_max`
and `heap_pop_min`/`heap_pop_max` maintain it one element at a time; `heap_peek_min`/`heap_peek_max`
read the root without touching anything. Every number below is pinned in
`tests/mojo/test_wave40.mojo`:

```python
h1 = [5.0, 3.0, 8.0, 1.0, 4.0]
h1 = runtime.execute("heap", "heapify_min", [h1])["result"]["mutated_args"]["data"]
h1[0]   # 1.0 -- the minimum, now at the root
runtime.execute("heap", "is_min_heap", [h1])["result"]   # True

kl = runtime.execute("heap", "k_largest", [[5.0, 1.0, 3.0, 2.0, 4.0], 2])["result"]
kl   # [4.0, 5.0] -- a min-heap of size 2 discards everything smaller as it scans
```

An empty heap is not an error case for `heap_peek_min`/`heap_peek_max`/`heap_pop_min`/`heap_pop_max`
-- each returns the sentinel `0.0` rather than raising, so a caller cannot distinguish "the heap's
minimum is 0.0" from "the heap is empty" without checking length first.

**There is no `is_max_heap`.** `heapify_max`, `heap_push_max`, `heap_pop_max`, and `heap_peek_max`
all exist and are exercised in the same test file, but the only verifier this module (or its
contract) exposes is `is_min_heap`, which reports `False` on any non-trivial max-heap. Checking a
max-heap's own invariant means re-deriving the parent-`>=`-child comparison at the call site --
there is nothing in `heap` to call for it.

**`merge_sorted_lists` is named, and documented, as a min-heap k-way merge -- it isn't one.**
Reading the body directly: for each of the `total` output elements, it does a plain linear scan
over all `k` input lists' current front elements to find the smallest, an O(total x k) approach
with no heap anywhere in it. The three-list, six-element case pinned in `test_wave40.mojo`
(`merge_sorted_lists([[1,3,5],[2,4,6]])` -> `[1,2,3,4,5,6]`) is far too small to expose the
difference, but a caller merging many long lists gets the O(total x k) linear-scan cost, not the
O(total x log k) a real heap-based merge would deliver -- in a module whose own `k_smallest` and
`k_largest`, a few functions up, exist specifically to get that log-k behavior.

**`running_median` is honest about its own cost.** Its docstring calls out "sort-based approach
for correctness": each of the `n` output values re-sorts the entire prefix seen so far rather than
maintaining the usual two-heap running structure, so the whole call is O(n^2 log n). On
`running_median([1.0, 3.0, 2.0, 4.0])` this gives `[1.0, 2.0, 2.0, 2.5]` -- `1.0` (one element),
`(1+3)/2 = 2.0`, the median of `{1,2,3}` which is `2.0`, then `(2+3)/2 = 2.5` -- all four values
pinned in `test_wave40.mojo`.

## `queue_ds`: two structs, one of which shares a name-prefix with an unrelated module

`PriorityQueue` is a parallel-array binary min-heap keyed on `priority` (lower priority number
pops first); `CircularBuffer` is a fixed-capacity ring that overwrites its oldest element once
full rather than rejecting the push. Both are created with no arguments to mutate (`pq_create`
takes none; `cb_create` takes only `capacity`), then pushed and popped via `mutated_args` as
above. Every number below is pinned in `tests/mojo/test_wave34.mojo`:

```python
pq = runtime.execute("queue_ds", "pq_create", [])["result"]
for priority, value in [(5.0, 50), (1.0, 10), (3.0, 30)]:
    pq = runtime.execute("queue_ds", "pq_push", [pq, priority, value])["result"]["mutated_args"]["pq"]

runtime.execute("queue_ds", "pq_peek", [pq])["result"]
# {'priority': 1.0, 'value': 10} -- the lowest priority NUMBER, not the highest value

buf = runtime.execute("queue_ds", "cb_create", [3])["result"]
for v in [10.0, 20.0, 30.0]:
    buf = runtime.execute("queue_ds", "cb_push", [buf, v])["result"]["mutated_args"]["buf"]
runtime.execute("queue_ds", "cb_is_full", [buf])["result"]   # True

buf = runtime.execute("queue_ds", "cb_push", [buf, 40.0])["result"]["mutated_args"]["buf"]
runtime.execute("queue_ds", "cb_peek", [buf])["result"]   # 20.0 -- the 10.0 was overwritten
```

An empty `PriorityQueue` returns the sentinel entry `{"priority": -999999.0, "value": -1}` from
`pq_peek`/`pq_pop` rather than raising; an empty `CircularBuffer` returns the sentinel `-999999.0`
from `cb_peek`/`cb_pop`. Both are the same "return an out-of-band number instead of erroring"
convention `heap` uses, with a different sentinel value.

**`cb_` names two unrelated things in this codebase.** `queue_ds.cb_create` builds a
`CircularBuffer` and takes one argument (`capacity`); a completely different module,
`bloom_counting`, exports its own `cb_create` for a `CountingBloom` filter that takes two
arguments (`size`, `n_hashes`) and an entirely different function set (`cb_add`, `cb_remove`,
`cb_contains`, `cb_hash`, ...). The two are registered as separate runtime modules
(`queue_ds.cb_create` vs. `bloom_counting.cb_create`), so `runtime.execute` never confuses them,
but a reader grepping the codebase for `cb_` or pattern-matching a snippet out of context can.

## `trie`: a byte-level prefix tree with no constructor in the runtime's callable surface

`Trie` stores its nodes as five parallel `List[Int]` arrays (`nodes_char`, `nodes_parent`,
`nodes_end`, `nodes_first_child`, `nodes_next_sibling`) linked first-child/next-sibling instead
of nesting lists. `trie_insert` walks `word.as_bytes()`, one node per UTF-8 **byte** -- for ASCII
input a byte and a Unicode code point are the same number, so this is invisible until a
multi-byte character shows up (below).

**`trie_create` is not reachable through `runtime.execute` at all.** It exists in
`mojo/engine/trie.mojo` and is used directly by `tests/mojo/test_wave41.mojo`, but it is absent
from both the runtime library contract's function list for `trie` and from
`runtime_library_dispatch_generated.mojo`'s `_dispatch_trie` -- there is no `if function_name ==
"trie_create"` anywhere in it. Building a `Trie` value through the SDK means constructing the
one-node root `trie_create()` itself would build, by hand, as the same field-name-keyed dict every
struct in this family decodes to elsewhere on this page (`pq_peek`'s `{"priority": ..., "value":
...}` above is the same shape):

```python
t = {
    "nodes_char": [0], "nodes_parent": [-1], "nodes_end": [0],
    "nodes_first_child": [-1], "nodes_next_sibling": [-1],
}   # one root node, char=0, no parent, not end-of-word, no children

for word in ["hello", "help", "heap"]:
    t = runtime.execute("trie", "trie_insert", [t, word])["result"]["mutated_args"]["t"]

runtime.execute("trie", "trie_count_words", [t])["result"]         # 3
runtime.execute("trie", "trie_prefix_count", [t, "hel"])["result"]  # 2 -- "hello" and "help"
runtime.execute("trie", "trie_prefix_count", [t, "he"])["result"]   # 3 -- all of them
```

Both counts above are pinned in `test_wave41.mojo` for this exact three-word trie.
`trie_word_list` is not pinned to an exact order there (only its length is checked), so the order
below is traced by hand against `trie.mojo`'s DFS, which visits each node's `first_child` before
its `next_sibling`, and `_add_child` always **prepends** a new child rather than appending:

```python
runtime.execute("trie", "trie_word_list", [t])["result"]
# ['heap', 'help', 'hello']
```

That order is the reverse of insertion order at every branch point (`heap` was inserted last but
shares only "he" with the others, so its branch was prepended last and visited first; `help`
similarly prepended after `hello` at the "hel" branch), not alphabetical and not insertion order
-- a caller expecting either would see something else.

**`trie_word_list` reassembles bytes as if each one were its own character, which breaks on
non-ASCII words.** `_build_word` -- the helper `trie_word_list` calls once per stored word --
walks a word's end-node back to the root and concatenates `chr(byte)` for every byte on the path.
Inserting the single word `"café"` stores `é` (U+00E9) as its two-byte UTF-8 encoding, bytes `195`
and `169`, as two separate trie nodes; reconstructing it calls `chr(195) + chr(169)`, giving
`"Ã©"`, not `"café"`. `trie_search`, `trie_starts_with`, and `trie_prefix_count` are unaffected by
this, because they walk the same bytes on lookup that were walked on insert and only ever compare
byte-for-byte -- only the reconstruction path in `trie_word_list` reads stored bytes back out as
characters.

## `sorting`: six sorted-copy algorithms, and the one function this whole family guards by contract

`quicksort` (Lomuto partition), `mergesort` (top-down recursive), `heapsort`, `insertion_sort`,
`selection_sort`, and `bubble_sort` (with early-exit on an already-sorted pass) all take a copy of
`data`, sort the copy, and return it -- none of them mutate their argument, unlike `heap` and
`queue_ds` above. `tests/mojo/test_wave33.mojo` pins `quicksort`, `heapsort`, `insertion_sort`,
`selection_sort`, and `bubble_sort` on `[3.0, 1.0, 4.0, 1.0, 5.0]`, and every one returns
`[1.0, 1.0, 3.0, 4.0, 5.0]`; it pins `mergesort` separately on `[5.0, 4.0, 3.0, 2.0, 1.0]`, which
returns `[1.0, 2.0, 3.0, 4.0, 5.0]` -- the same algorithm run on the first list would return the
same multiset as the other five, `[1.0, 1.0, 3.0, 4.0, 5.0]`, since all six are correct sorts of
the same input. `counting_sort_int([3, 1, 4, 1, 5])` returns the integer version, `[1, 1, 3, 4, 5]`.
`reverse_list([1.0, 2.0, 3.0])` returns `[3.0, 2.0, 1.0]`; `is_sorted` reports `True`/`False`
without sorting anything.

`nth_smallest(data, n)` full-sorts a copy via `quicksort` and indexes it -- it is the one function
in this whole five-module family whose contract entry carries a `count_relations` guard, and
reading `nth_smallest`'s own body shows why: `return sorted_data[n]` has no bounds check at all.
`nth_smallest([5.0, 1.0, 3.0, 2.0, 4.0], 2)` returns `3.0` (`0,1,2,3,4` sorted is `1,2,3,4,5`, index
`2` is `3.0`; pinned in `test_wave33.mojo`), but a raw index past the end of `data` inside the
Mojo worker is an uncatchable process abort, not a Python exception -- so the SDK's own
`enforce_count_relations` check refuses `n >= len(data)` (and any negative `n`) before the call
ever leaves the client, using the declared relation `n + 1 <= len(data)`. Every other function in
this page carries no such relation, either because its own body already clamps its index
(`k_smallest`/`k_largest` clamp `k` to `min(k, len(data))`) or because it takes no index argument
at all.

`counting_sort_int` protects itself the same way `nth_smallest` needs the SDK's help for, but
inside its own body: it refuses to run at all -- returning `[]` -- if any element is negative or
if the maximum element exceeds `10,000,000`, rather than allocating a bucket array sized to
whatever value it's handed. The source comment explains the cap is not arbitrary: an audit sweep
once sent this function values approaching plus-or-minus 2^62, which would otherwise have tried to
allocate a multi-gigabyte bucket array from a single adversarial input.

## `set_ops`: sorted, deduplicated `List[Int]`, not a general-purpose set

Every function here assumes both of its inputs are already sorted ascending and free of
duplicates -- `to_set(data)` is the one function that produces that shape from raw input (sort,
then drop adjacent duplicates), and every other function trusts the caller to have run it first
rather than re-validating. The four set-algebra results below are pinned in
`tests/mojo/test_wave35.mojo`, on `a = [1, 3, 5]` and `b = [2, 3, 4]`; `jaccard_index(a, b)` is
not one of that file's pinned cases (it pins a different pair for `jaccard_index`) but follows
from the same union and intersection computed a line above:

```python
runtime.execute("set_ops", "set_union", [a, b])["result"]                  # [1, 2, 3, 4, 5]
runtime.execute("set_ops", "set_intersection", [a, b])["result"]           # [3]
runtime.execute("set_ops", "set_difference", [a, b])["result"]             # [1, 5]
runtime.execute("set_ops", "set_symmetric_difference", [a, b])["result"]   # [1, 2, 4, 5]
runtime.execute("set_ops", "jaccard_index", [a, b])["result"]              # 0.2 -- |{3}| / |{1,2,3,4,5}|
```

`is_subset`/`is_superset`/`set_equals` are single merge-style passes over both sorted lists;
`power_set_size(n)` returns `1 << n`, except it returns the sentinel `-1` for `n >= 63` (Mojo's
`Int` is 64-bit signed, so `2**63` cannot be represented) and `0` for `n < 0`. `jaccard_index`
returns `1.0` for two empty sets by convention (`0/0` would otherwise be undefined), and `0.0` for
two disjoint sets.

**Passing an unsorted list into `set_contains` doesn't raise -- it can silently answer wrong.**
`set_contains` is a plain binary search, and binary search's correctness depends entirely on its
input being sorted. Tracing `set_contains([5, 1, 3, 2, 4], 1)` by hand: `lo=0, hi=4`, midpoint `2`
holds `3`, and `3 > 1` sends the search left to `hi=1`; midpoint `0` holds `5`, and `5 > 1` sends
`hi=-1`; the loop ends with `lo > hi` and the function returns `False` -- even though `1` is
present, at index `1`, in the list handed to it. Every other function in this module has the same
sorted-input assumption; `set_contains` is simply the one where violating it produces a
definite-looking wrong answer rather than a list in the wrong order.

## Verification

`mojo/tests/libs/test_heap.mojo`, `test_queue_ds.mojo`, `test_sorting.mojo`, and `test_set_ops.mojo`
are auto-generated coverage smoke tests -- each calls every function once with fixed literal
arguments and checks only that the result is finite or type-correct, not that it matches a
specific expected value. There is no `mojo/tests/libs/test_trie.mojo` at all; `trie` has zero
auto-generated coverage. Every specific number in this page instead traces to one of five
hand-written suites in `tests/mojo/`: `test_wave33.mojo` (`sorting`), `test_wave34.mojo`
(`queue_ds`), `test_wave35.mojo` (`set_ops`), `test_wave40.mojo` (`heap`), and `test_wave41.mojo`
(`trie`) -- or, where noted above (`trie_word_list`'s DFS order, the `merge_sorted_lists`
docstring mismatch, `counting_sort_int`'s allocation cap, `set_contains` on unsorted input), was
traced or computed by hand directly against the Mojo source in `mojo/engine/`.

**Next:** see [Discrete-event simulation & queueing](discrete-event-simulation.md), whose event
calendar implements its own independent binary min-heap rather than calling into `heap`, or
browse the [Runtime library catalog](catalog.md) for every module and function.
