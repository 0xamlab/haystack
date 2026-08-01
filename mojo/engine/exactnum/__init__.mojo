"""
exactnum — error-free transformations and a double-double least-squares route.

Additive namespace. Nothing here modifies a frozen kernel; `exactnum` exists because the
tree has no *error-free transformation* at all, and therefore no way to carry more than
float64 through a factorisation.

What is genuinely missing, classified before anything was written
-----------------------------------------------------------------
* `numerical_stability.kahan_sum` (frozen) is a *compensated sum*: it returns one Float64
  and throws the compensation away at the end. `determinism.reduce_det.det_neumaier_sum`
  is the same shape with a better update rule. Neither yields the **pair** (sum, exact
  error), so neither can be composed into a higher-precision product, quotient, square
  root or triangular solve. Compensation-as-a-scalar and compensation-as-a-number-format
  are different capabilities; only the first is in the tree. `exactnum.eft` adds the
  second and does *not* reimplement either frozen sum — `exactnum.eft.eft_kahan_sum_f64`
  calls `kahan_sum` directly when a plain float64 compensated sum is what is wanted.
* `linalg_ext.mat_qr` is modified Gram-Schmidt by its own docstring, in float64.
  `sparse_numerics.factor.csr_least_squares` is normal equations plus Cholesky, which
  squares the condition number. There is no Householder QR in `mojo/engine/` at any
  precision (`grep -rin householder mojo/engine/` is empty). `exactnum.lstsq` adds one and
  leaves both frozen routes reachable and unchanged.

Modules
-------
  eft    — status codes 800-809; two_sum, fast_two_sum, two_product, dd_add/sub/mul/div/sqrt,
           Dot2, Sum2, and the runtime FMA self-check
  lstsq  — status codes 810-819; compensated Householder QR least squares, the float64
           control that uses the identical algorithm, and the polynomial-basis drivers

Status range
------------
`exactnum` owns **800-819**. Ranges already handed out elsewhere in the tree, read off the
`owns N-M` comments: 0-13, 50-99, 80-86, 130-139, 300-309, 310-329, 320-339, 330-339,
340-359, 360-379, 380-389, 390-399, 400-449, 450-489, 580-599, 700-709, 900-949. 800-819
was free (rule 4e).

Why double-double, stated as a bound and not a hope
---------------------------------------------------
A float64 return cannot carry more than ~16 decimal digits no matter how good the
internals are. The point of carrying ~106 bits *inside* the factorisation is that on an
ill-conditioned design the digits are lost in the WORKING precision, not in the return
format. That is the same published effect that makes compensated Horner beat plain Horner.

It is also not unconditional. `eft` is only error-free if the hardware has a
single-rounding fused multiply-add and the compiler neither contracts `a*b + c` into an
FMA behind your back nor reassociates additions. All three were measured on this
toolchain, at `--optimization-level 0`, at `3` (what `scripts/build_mojo_binary.sh` ships)
and under the JIT, with bit-identical results; there is no fast-math-equivalent flag
anywhere in this build. `eft.eft_selfcheck_code` re-runs the three decisive cases at
runtime so a future toolchain change fails loudly instead of silently degrading every
result in this package to plain float64.
"""
