"""
quantfin — quantitative-finance workloads that COMPOSE the frozen pricing and sampling kernels.

Nothing in this package edits an existing kernel. `option_pricing.mojo`, `matrix_decomp.mojo`,
`regression.mojo`, `integrate.mojo` and `determinism/counter_rng.mojo` are imported and called;
the new capability lives here.

Modules:
  heston — Heston stochastic volatility by Andersen's Quadratic Exponential discretisation,
           multi-asset with Cholesky-correlated price Brownians, best-of-N early exercise by
           Longstaff-Schwartz, and the full Greeks set by finite differences on COMMON RANDOM
           NUMBERS. This is the market-risk workload STAC-A2 describes. It is UNAUDITED and
           independently implemented from the PUBLIC specification — see the module docstring;
           nothing here may be presented as a STAC-A2 result.

Invoked directly by callers rather than through `library_execute`: the entry points take
`List[HestonParams]` and a correlation matrix, neither of which is FFI-marshalable, and the
Philox coordinates are UInt64 — the same reason `determinism` is excluded from the runtime-library
inventory.
"""
