"""
mlpk — feed-forward and embedding kernels: gated activations and token lookup, fwd and bwd.

Where the frozen tree already is
----------------------------------
`activations.mojo` has the per-element nonlinearities and `mlpk` calls them unchanged (rule 3):
`swiglu(x, gate) = swish(gate) * x` is exactly right, and `gelu_new` is a correct tanh GELU. What is
absent is the loop over a real buffer, every derivative, and one activation the tree does not have at
all.

The GELU finding, measured 2026-07-31
---------------------------------------
The tree holds THREE GELU spellings and none of them is exact — including `activations.gelu`, whose
docstring opens "Gaussian Error Linear Unit (exact): x x Phi(x)" above a tanh body.

| Frozen kernel | vs exact erf | vs each other |
|---|---|---|
| `activations.gelu` | 4.73e-4 | 9e-13 from `gelu_fast` — it truncates `sqrt(2/pi)` to 10 digits |
| `activations.gelu_fast` | 4.73e-4 | 2.6e-16 from `gelu_new` — a different association, not a different convention |
| `activations.gelu_new` | 4.73e-4 | 2.6e-16 from `gelu_fast` |

So this is not two conventions in the tree. It is one convention spelled three times, and the tree is
missing the other one entirely. That matters because Hugging Face treats them as different
activations: `hidden_act: "gelu"` is the erf form; `"gelu_new"` and `"gelu_pytorch_tanh"` are the tanh
form. A checkpoint trained under one and served under the other produces fluent output that is
quietly worse — a disappointing model rather than a visible bug.

`mlpk.activation.mlp_gelu_erf` supplies the erf form as its OWN contract for new surfaces, exactly
as `tensorx.dtype` does for the frozen bf16 rounding. Every frozen spelling keeps its current answer
for its current callers, `mlp_gelu_agreement` reports the gap as a number, and the caller selects
with `MLP_ACT_GEGLU_ERF` or `MLP_ACT_GEGLU_TANH`. There is deliberately no default.

Modules
-------
  contract    — status codes 390-399, feed-forward and vocabulary shape checks, the tolerance
  activation  — SwiGLU and both GEGLU variants, forward and backward, plus the exact GELU

Dependency direction is one-way: `mlpk` uses `tensorx` for finiteness and the frozen `activations`
for per-element arithmetic, never the reverse.
"""
