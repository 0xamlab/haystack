---
icon: clipboard-check
description: Ask the engine what each kernel actually does — deterministic or not, seeded or not, stateful or not, what it costs — and be told plainly when a kernel has not said.
---

# Declared capabilities

A signature tells you the types a kernel takes. It cannot tell you the things you most
need to know before you depend on one: whether two identical calls give identical answers,
whether it needs a seed, whether it carries state between calls, what it costs as the
input grows, which numeric types it accepts, or which of its integer arguments is the
**number of elements to read** from which list.

Those are declared by the kernel's author and read back through the SDK:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")
capabilities = runtime.capabilities()

found = capabilities.search(module_prefix="optimization.", deterministic=True)
for record in found:
    record.module, record.function, record.complexity

record = capabilities.describe("stats", "sort_values")
record.as_dict()
```

Everything here is metadata. Nothing is computed, nothing is sent anywhere, and reading it
does not warm up or touch the compute path.

## Undeclared is not the same as "no"

Every field comes back as either a declared value or `UNDECLARED`. Those are different
answers and they have different representations:

```python
from algenta import UNDECLARED

record = capabilities.describe("stats", "sort_values")

record.deterministic is UNDECLARED     # "nobody has said"
record.deterministic is False          # "it has been said: not deterministic"
```

`UNDECLARED` refuses to be treated as a boolean at all — `if record.deterministic:` raises
a `TypeError` rather than quietly reading as "not deterministic". That is deliberate. A
default of `False` would let a kernel nobody has described masquerade as a kernel that has
been examined and found non-deterministic, and you would have no way to tell the two apart
afterwards.

The same rule shapes the search. A filter can only be judged against a kernel that
declared the field being filtered on, so a search returns **two** lists:

```python
found = capabilities.search(module="stats", deterministic=True)

list(found)          # the matches: declared, and declared True
found.undeclared     # in scope, but never said whether they are deterministic
found.total_matches  # how many matched before any limit was applied
```

Each entry in `found.undeclared` names the fields it did not declare, and whether it
carries any declaration at all. This is the useful part rather than a technicality: a
search that quietly dropped the kernels it could not judge would let you conclude a
capability does not exist in the engine when the truth is only that it has not been
described. One of those conclusions is safe to act on and the other is not.

For the same reason, a name that does not exist is an error rather than an empty result:

```python
from algenta import CapabilityError

try:
    capabilities.describe("statz", "sort_values")
except CapabilityError as error:
    error.code          # "module_not_registered"
    error.details       # {"module": "statz"}
```

A mistyped module or function raises `CapabilityError`, and so does a search scoped to one.
Zero results for a typo reads exactly like "the engine cannot do that", which is the
mistake this whole surface exists to prevent.

## What you can ask

```python
capabilities.search(
    module_prefix="stats",          # or module="stats" for one module exactly
    function="sort",                # case-insensitive substring
    deterministic=True,
    requires_seed=False,            # or seed_requirements="optional" for the exact word
    stateful=False,
    batch_capable=True,
    stream_capable=False,
    declares_count_relations=True,
    dtype="Float64",
    backend="mojo",
    complexity="O(n log n)",
    deprecation_state="active",
    limit=50,
)
```

| Field | The question it answers |
| --- | --- |
| `deterministic` | do two identical calls give byte-identical answers |
| `seed_requirements` | whether a seed is `required`, `optional`, or `none` — `requires_seed` reads it as a boolean, where `optional` counts as not required |
| `stateful` | does a call change what the next call returns |
| `batch_capable` | may it be sent as one item among many in a single batch |
| `stream_capable` | may it be driven over a resident dataset in chunks |
| `supported_dtypes` | which numeric types it accepts |
| `complexity` | what it costs as the input grows, in the author's own words |
| `backend` | what actually executes it |
| `surfaces` | which calling surfaces expose it |
| `count_relations` | which arguments are element counts, and which list each one bounds |
| `golden_vectors` | which fixed input/output pairs pin its answers |
| `benchmark` | which measurement covers it |
| `version_introduced`, `deprecation_state` | when it appeared, and whether it is still current |

Omit an argument and it does not filter. Passing `None` is the same as omitting it, which
means "do not filter on this" — not "declared nothing".

`backend`, `surface`, `seed_requirements` and `deprecation_state` draw on fixed
vocabularies, and a value outside them raises rather than matching nothing — a misspelled
backend must not come back looking like "no kernel uses that one".

## Counts, and the lists they bound

Many kernels take a list together with the number of elements to read from it, and a flat
row-major matrix arrives as one list plus its `rows` and `cols`. The relationship between
those arguments is real, it is load-bearing, and no type signature can express it: `n` and
`v` are just an integer and a list.

A declaration states the relationship, so it stops being something only the author knows:

```python
record = capabilities.describe("auction", "all_pay_revenue")

if record.count_relations is not UNDECLARED:
    for relation in record.count_relations:
        relation.expression   # "n <= len(bids)" — the bound, as a reader would say it
        relation.factors      # the count argument(s) multiplied into the bound
        relation.bounds       # the list argument(s) that must be at least that long
        relation.plus         # a constant added to the product
        relation.role         # "count", or "index" when the argument is an offset
```

The `is not UNDECLARED` guard is not ceremony. A kernel that has not described its counts
has `UNDECLARED` there, and iterating it raises rather than looping zero times — because
"no relations" and "no statement about relations" would otherwise be the same empty loop.

The shape covers the cases that actually occur. Two factors multiply, so a flat row-major
matrix reads `rows * cols <= len(dense)`. One count can bound several parallel lists at
once, which is how a sparse triple is written. The added constant covers a pointer array
holding one entry more than it has rows, and it is also how an INDEX argument is declared:
reading `adjacency[node]` needs `node + 1` elements, so an index is a bound too.

The payoff is at call time. When a kernel has declared the relationship, a request whose
count exceeds the list it counts is refused with an error naming the count and the list it
disagrees with, before any of the numbers are read — and in a batch, one item is refused
instead of the whole frame. Without the declaration, the same request is simply a request:
the arguments are individually valid, and only the kernel author ever knew they contradict
each other.

```python
counted = capabilities.search(declares_count_relations=True)
len(counted)             # kernels whose count arguments are described
counted.undeclared       # kernels that have not described theirs
```

Reading `counted.undeclared` is the point of that call. It is the honest list of places
where the check cannot be made for you yet, and it is a list that shortens over time.

## Describing one kernel in full

```python
record = capabilities.describe("optimization.linear", "lp_solve_default")

record.has_block             # False when no declaration block was written for it
record.declared_fields()     # what it has stated
record.undeclared_fields()   # what it has not
record.as_dict()             # JSON-ready
```

`declared_fields()` is the field-level truth and the one to trust: a kernel with no
declaration block can still have its counts described, so it will report `has_block` as
False while `count_relations` is a real answer.

`as_dict()` **omits** undeclared fields rather than serializing them as `null` or `false`,
and lists their names under `undeclared_fields`. A consumer downstream should never be
handed a value the kernel never claimed; a null in a JSON payload gets defaulted by
somebody, and once it has been defaulted the absence is gone.

## Why a declaration and not a measurement

A declaration is a statement by the person who wrote the kernel, checked by the tests and
fixed inputs that ship alongside it. It is not inferred from a sample of runs, because
running a kernel twice and getting the same answer does not make it deterministic — it
makes it deterministic on that input, on that machine, that afternoon.

So the reporting is deliberately conservative in one direction only. A declared capability
is a commitment. An undeclared one is reported as undeclared, and never as a safe default,
because a default that happens to be right most of the time is indistinguishable from one
that happens to be wrong here.

## See also

* [Runtime libraries](runtime-libraries.md) — calling a kernel by module and function
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Optimization & decision programs](optimization.md) — kernels that report when no answer exists
* [LLM tool-calling uplift](../benchmarks/llm-tool-calling-uplift.md) — this catalog searched and called by an LLM instead of application code
