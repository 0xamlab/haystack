"""
tensorx — the dtype and shape substrate the LLM plane is built on. Zero Python.

What the tree already has, and why it is not enough here
---------------------------------------------------------
The kernel tree is broad and proven, but it has no dtype system. `tensor.Tensor1D` is a 1-D
`List[Float64]`; `tensor2d.Matrix2D` is a naive triple-loop matmul over `Float64`; `columnar/dtype.mojo`
describes analytics column types (`DTYPE_*` 0-4), not numeric storage formats. Across 625 files, 16
mention SIMD and none mention a GPU. There is nowhere in the tree that says what bf16 is, how wide an
int4 buffer is, or what a comparison tolerance for a given precision should be.

That gap is not a quality problem with the existing kernels — they are frozen, correct for what they
do, and reused throughout. It is that an LLM plane needs a vocabulary they never had to have: a model
in bf16 with an nf4 base weight and an f32 accumulator is three precisions in one operation, and each
one has a different epsilon, a different range and a different overflow story.

Modules
-------
  contract  — the one status vocabulary (300-319), finiteness predicate and shape check
  dtype     — dtype tags, limits, accumulation policy, round-trip, and the tolerance constructor

Read `contract.mojo` first: it explains why there is exactly one of each of those, and the one
deliberate exception (`dtx_tol_for` lives in `dtype` because it is built from `dtx_eps`).

The three things most likely to bite
-------------------------------------
1. **A tolerance built from an aggregate.** Rule 4b names four spellings of this and all four have
   shipped in this repo before, once behind 145 passing assertions. `dtx_tol_for` takes ONE quantity
   and returns its composition so a reviewer can see which term dominates.
2. **A count that is not bounded by the payload.** The generated A-Z suite calls every contract
   function with a five-element list and `5` for every `Int`, so `n <= len(v)` always holds there and
   the harness can never find the hole. Every public function here that takes a count declares the
   relation in a `@capability` block and enforces it before indexing.
3. **`Int(Float64(...))` past the integer grid.** Undefined, not truncated, and a `_finite` guard does
   not catch it because 1e300 is perfectly finite. Byte widths and strides stay integral here, which
   is why `dtx_bytes_per_1024` exists instead of a fractional bytes-per-element.
"""
