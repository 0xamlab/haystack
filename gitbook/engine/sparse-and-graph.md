---
icon: diagram-project
description: Solve sparse linear systems and analyse graphs with compiled kernels on your own machine.
---

# Sparse systems & graph analytics

Two kernel families for problems where the data is mostly zeros or mostly structure: sparse
linear algebra, and graphs. Both run as compiled kernels inside the runtime that ships with
the SDK — there is nothing to start and nothing to install separately.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A 1D Laplacian in triplet form: (rows, cols, values)
rows = [0, 0, 1, 1, 1, 2, 2]
cols = [0, 1, 0, 1, 2, 1, 2]
vals = [2.0, -1.0, -1.0, 2.0, -1.0, -1.0, 2.0]

built = runtime.execute(
    "sparse_numerics.csr", "csr_build_from_triplets", [rows, cols, vals, 3, 3]
)
built["result"]["nnz"]        # 7
built["result"]["status"]     # 0 — sound
```

## Why sparse storage, and what it costs

A dense matvec over an n×n matrix touches n² cells however few are non-zero. Compressed
sparse row touches only the stored values. Measured on a tridiagonal system, cost per
non-zero stays flat as the matrix grows sixteenfold — so the work scales with your data, not
with the square of your dimension.

The same shape shows up in solving. On a 192×192 sparse system, conjugate gradient runs in
0.47 ms against 3.89 ms for a dense factorisation — about **8× faster**, and the two answers
agree to 1e-6. The gap widens with size, because the dense path is cubic in n while each CG
iteration is linear in the number of non-zeros.

## Sparse building blocks

| Module | What it does |
| --- | --- |
| `sparse_numerics.csr` | CSR and CSC, conversion to and from triplets and dense, explicit coalescing, index sorting, transpose, structural validation |
| `sparse_numerics.spmv` | matrix-vector products, transposed apply without materialising Aᵀ, sparse-sparse products, a compensated variant |
| `sparse_numerics.diagnostics` | one health report: density, norms, smallest diagonal, symmetry defect, empty rows and columns, non-finite values |
| `sparse_numerics.iterative` | conjugate gradient, CGLS for least squares, restarted GMRES, Jacobi preconditioning |
| `sparse_numerics.factor` | LU with partial pivoting, triangular solves, factor-once-solve-many, least squares |

### Duplicate coordinates sum

A triplet list may name the same `(row, col)` twice. Those values **add** — two entries of
2.0 and 3.0 at one coordinate mean 5.0, not 3.0. That is inherited from the engine's
existing sparse format rather than chosen here, so a compressed matrix always denotes the
same matrix as the triplets it came from.

Coalescing is an explicit step, not something conversion does silently:

```python
runtime.execute("sparse_numerics.csr", "csr_coalesce_driver",
                [indptr, indices, values, nrows, ncols])
```

It does not drop stored zeros. `5 + (-5)` leaves an explicit zero in the structure, because
`nnz` counts what is stored, not what is non-zero — and pruning would invalidate any
factorisation computed from the pattern.

### A coordinate outside the shape is skipped and counted

An entry at `(0, 99)` in a 3×3 matrix is not part of that matrix. It is dropped and the
count reported, rather than silently resizing the matrix or failing:

```python
built = runtime.execute("sparse_numerics.csr", "csr_build_from_triplets",
                        [[0], [99], [1.0], 3, 3])
built["result"]["skipped"]   # 1
built["result"]["nnz"]       # 0
```

### Validation tells you which array is wrong

`csr_validate` returns a distinct code per defect — a row pointer of the wrong length, a
non-monotonic pointer, a tail that disagrees with the value count, an index outside the
column range — so a rejection points at the array to look at instead of saying "invalid".

## Solving, and knowing whether you solved it

Every solver returns a status alongside its numbers, because the ways a solve can fail all
produce plausible-looking vectors:

```python
out = runtime.execute("sparse_numerics.iterative", "csr_cg_driver",
                      [indptr, indices, values, n, n, b, 1e-10, 1000])
r = out["result"]
r["converged"]        # False if it ran out of iterations
r["status"]           # which outcome
r["iterations"]
r["residual_norm"]
r["relative_residual"]
```

`converged` is separate from `status` on purpose. A solver that hits its iteration cap has
**not** solved your system, and the iterate it holds is not an answer. The statuses
distinguish converged, iteration limit, a non-symmetric matrix given to CG, a curvature
breakdown (which means the matrix was not positive definite), a non-finite value, a
structurally invalid matrix, a shape mismatch, and a zero right-hand side.

The direct solver reports singularity as a fact rather than as a vector:

```python
out = runtime.execute("sparse_numerics.factor", "csr_solve_driver", [...])
out["result"]["singular"]        # True — there is no solution
out["result"]["residual_norm"]   # ||Ax - b||, so you can see a bad answer
```

Every solve reports its residual, which is the cheapest way to catch a wrong answer that
came back with a healthy status.

## Graphs

| Module | What it does |
| --- | --- |
| `graph_analytics.adjacency` | compressed adjacency built once, Dijkstra, BFS levels, shortest path, reverse graph, degree sequences, symmetry |
| `graph_analytics.centrality` | betweenness (Brandes), closeness, degree, eigenvector, PageRank |
| `graph_analytics.community` | Louvain communities across levels, label propagation, modularity scoring |
| `graph_analytics.temporal` | time-respecting reachability, earliest-arrival and fastest paths, time-window extraction, activity summary |

### Build once, query many times

```python
src    = [0, 1, 2, 3]
dst    = [1, 2, 3, 0]
weight = [1.0, 2.0, 1.0, 4.0]

out = runtime.execute("graph_analytics.adjacency", "graph_csr_dijkstra_driver",
                      [row_ptr, targets, weights, 4, 0])
d = out["result"]
d["distance"]     # per node
d["reached"]      # per node — the authority on reachability
```

Building the adjacency once and running eight shortest-path queries against it takes 0.57 ms
where eight independent calls take 2.97 ms — about **5× faster**, with identical distances.
The difference is that a compressed adjacency is built once and a priority queue replaces a
scan over all vertices.

### Unreachable is reported, not encoded as a number

`reached` is the authority. A node you cannot get to has `reached = False` and a distance of
`-1.0`, which a real shortest-path answer can never produce because negative weights are
refused. A large sentinel like `1e18` would be indistinguishable from a genuinely long path.

### Negative weights are refused, not mis-solved

Dijkstra is not valid with negative edge weights, so it declines rather than returning a
confident wrong answer:

```python
out["result"]["status"]    # negative_weight_use_bellman_ford
```

This is not conservatism. On the graph `0→1 (1)`, `0→2 (5)`, `2→1 (−10)`, `1→3 (1)`, a
Dijkstra-shaped algorithm reports distance 2.0 for node 3 while the correct answer is
**−4.0**. Use `graph.weighted.bellman_ford` for graphs with negative weights.

### Betweenness scales with edges, not vertices cubed

Betweenness is computed by Brandes' algorithm, so cost grows with vertices × edges rather
than vertices cubed. Measured across a fourfold increase in graph size, cost per
(vertex × edge) stays flat.

```python
out = runtime.execute("graph_analytics.centrality", "graph_betweenness_unweighted",
                      [row_ptr, targets, weights, n, True])
```

Closeness has a decision worth knowing: in a disconnected graph the sum of distances to
unreachable nodes is not finite, so closeness is reported per reachable component with the
reached count alongside, rather than silently treating unreachable as distance zero.

### Communities are reproducible

Louvain visits nodes in an order that affects the result, so the order is seeded. The same
seed gives the same communities every run — a community detector whose output changes
between runs cannot be used in a decision that has to be explained.

Connected components are **not** communities. A single connected graph can hold two obvious
communities, and `graph.algorithms.connected_components` would report one group.

### Time-respecting paths are not ordinary paths

A temporal path is only valid if its edge times do not go backwards. This matters because
temporal reachability is **not transitive**: if A→B happens at t=5 and B→C at t=3, then C is
**not** reachable from A, even though the static graph says it is.

```python
out = runtime.execute("graph_analytics.temporal", "temporal_earliest_arrival_driver",
                      [src, dst, weight, time, n_nodes, source, start_time])
```

Running a static algorithm over temporal data gives a confidently wrong answer, which is the
reason these are separate functions rather than an option on the others.

## Shapes are checked before anything is read

Every function validates its dimensions against the actual list lengths before indexing, and
returns a status rather than reading past the end. Declared sizes are also capped: a matrix
or graph that claims 10¹² columns is refused, because a transpose or an adjacency allocates
one slot per column regardless of how few values there are.

A dimension mismatch gives you an empty result and a status, never a plausible short vector.

## See also

* [Batched and chained execution](coarse-execution.md) — many kernel calls in one frame
* [Columnar queries](columnar-queries.md) — filter, group, sort and rank tabular data
* [Runtime library catalog](runtime-library-catalog.md) — every module and function
