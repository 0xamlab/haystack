"""
columnar — typed, nullable columns. Zero Python.

What the tree has today, and why none of it fits
------------------------------------------------
* `data/dataframe.mojo` — `Column{name, data: List[Float64], n}`. Float64 only, no
  nullability, and `__copyinit__` deep-copies, so passing a column by value copies
  every element.
* `database.mojo` — `Table` as column-major `List[List[Float64]]`. Same limits, plus
  O(n²) sort and nested-loop join.
* `vector_kernels/table.mojo` — the one genuinely typed columnar layout, with 8-lane
  Float32 SIMD. It is a purpose-built candidate-ranking index (VEC_DIM=64,
  RANK_TOP_K=8) and gutting it would regress retrieval.

All three are frozen and unchanged. This is a general column store alongside them.

Nulls are the reason this exists
--------------------------------
There are no validity bitmaps anywhere in the repo, in either language. Without
them, "missing" has to be encoded as a value — and every candidate sentinel is also
a legitimate datum. NaN is a real measurement outcome; 0.0 is a real revenue; -1 is
a real temperature. The existing aggregation paths inherit exactly this confusion,
which is why an empty group there returns 0.0.

A separate validity bit per slot removes the ambiguity: a value is present or it is
not, independently of what the value is.

Modules:
  dtype    — the type tags, widths and promotion rules
  validity — the bitmap: get/set/count, word-at-a-time
  array    — typed nullable arrays over a buffer + validity
  batch    — Schema and RecordBatch, with zero-copy slicing

Invoked directly rather than through `library_execute`, so this package is excluded
from the runtime-library inventory.
"""
