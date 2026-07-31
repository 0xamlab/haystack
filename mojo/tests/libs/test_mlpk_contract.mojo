"""test_mlpk_contract.mojo — status range, work budget, vocabulary check and the activation selector.

Hand-written. The non-obvious assertions:

* THE STATUS RANGE DOES NOT COLLIDE with tensorx 300-319, gemm 320-339, attnk 360-379 or normk
  380-389 (rule 4e). A code that drifts into a neighbour's block does not fail anywhere — it makes
  one package's error read as another's, which is worse than an unknown code because it looks
  answered.
* THE WORK GUARD DOES NOT WRAP. Three factors here rather than two, so there is more opportunity for
  a 64-bit product to overflow and compare as small.
* THE ACTIVATION SELECTOR HAS NO DEFAULT. An unrecognised kind must be refused. Defaulting to SwiGLU
  would be right for Llama-family models and silently wrong for every GELU one.
* THE VOCABULARY IS CHECKED SEPARATELY from the feed-forward width, because it is the one dimension
  the caller does not choose — it comes from the tokenizer, and a tokenizer/weight mismatch must be
  named as a configuration error rather than surfacing as an index.
"""
from attnk.contract import ATTN_OK
from gemm.contract import GEMM_OK
from mlpk.contract import (
    MLP_ACT_GEGLU_ERF,
    MLP_ACT_GEGLU_TANH,
    MLP_ACT_SWIGLU,
    MLP_ERR_DIM_TOO_LARGE,
    MLP_ERR_EMPTY_DIM,
    MLP_ERR_UNKNOWN_ACTIVATION,
    MLP_ERR_WORK_TOO_LARGE,
    MLP_MAX_DIM,
    MLP_MAX_TOKENS,
    MLP_MAX_VOCAB,
    MLP_MAX_WORK_CELLS,
    MLP_OK,
    mlp_activation_known,
    mlp_dims_check,
    mlp_status_name,
    mlp_tol_for,
    mlp_vocab_check,
    mlp_work_fits,
)
from normk.contract import NORM_OK
from tensorx.contract import TX_OK


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the range is exclusive ────────────────────────────────────────────────
    if MLP_OK == 390 and MLP_ERR_UNKNOWN_ACTIVATION == 397:
        passed += 1
        print("  ✅ mlpk owns 390-399 as declared")
    else:
        failed += 1
        print("  ❌ the status range moved:", MLP_OK)

    if MLP_OK != TX_OK and MLP_OK != GEMM_OK and MLP_OK != ATTN_OK and MLP_OK != NORM_OK:
        passed += 1
        print("  ✅ no collision with tensorx, gemm, attnk or normk OK codes")
    else:
        failed += 1
        print("  ❌ MLP_OK collides with a neighbouring package")

    if mlp_status_name(MLP_ERR_UNKNOWN_ACTIVATION) == String("unknown_activation"):
        passed += 1
        print("  ✅ codes name themselves")
    else:
        failed += 1
        print("  ❌ a status code named itself wrongly")

    if mlp_status_name(12345) == String("unknown_status"):
        passed += 1
        print("  ✅ an unknown code says so rather than borrowing a neighbour's meaning")
    else:
        failed += 1
        print("  ❌ an unknown code was given a name")

    # ── the work guard cannot be walked past by a wrapping product ────────────
    var huge = 1 << 30
    if not mlp_work_fits(huge, huge, huge, MLP_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a three-factor product that wraps 64 bits is still refused")
    else:
        failed += 1
        print("  ❌ a wrapping product was accepted as fitting")

    if mlp_work_fits(2048, 4096, 12288, MLP_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a real Qwen3-8B feed-forward shape fits: 2048 x 4096 x 12288")
    else:
        failed += 1
        print("  ❌ an ordinary feed-forward shape was refused")

    if mlp_dims_check(0, 8, 8) == MLP_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an empty dimension is refused")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    if mlp_dims_check(8, MLP_MAX_DIM + 1, 8) == MLP_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a width past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized width was accepted")

    # Three dimensions each inside their own ceiling whose PRODUCT is not.
    if mlp_dims_check(MLP_MAX_TOKENS, MLP_MAX_DIM, MLP_MAX_DIM) == MLP_ERR_WORK_TOO_LARGE:
        passed += 1
        print("  ✅ three legal dimensions with an illegal product are refused on the budget")
    else:
        failed += 1
        print("  ❌ the work budget did not fire on a legal-by-dimension shape")

    # ── the vocabulary is its own check ───────────────────────────────────────
    if mlp_vocab_check(1024, 151936, 4096) == MLP_OK:
        passed += 1
        print("  ✅ a real Qwen3 vocabulary passes: 151,936 x 4096")
    else:
        failed += 1
        print("  ❌ a real vocabulary was refused")

    if mlp_vocab_check(8, MLP_MAX_VOCAB + 1, 8) == MLP_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a vocabulary past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized vocabulary was accepted")

    # ── the activation selector has no default ────────────────────────────────
    if (
        mlp_activation_known(MLP_ACT_SWIGLU)
        and mlp_activation_known(MLP_ACT_GEGLU_TANH)
        and mlp_activation_known(MLP_ACT_GEGLU_ERF)
    ):
        passed += 1
        print("  ✅ all three declared activations are recognised")
    else:
        failed += 1
        print("  ❌ a declared activation was not recognised")

    if not mlp_activation_known(3) and not mlp_activation_known(-1):
        passed += 1
        print("  ✅ an unrecognised activation is refused, never defaulted")
    else:
        failed += 1
        print("  ❌ an unrecognised activation was accepted")

    if MLP_ACT_GEGLU_TANH != MLP_ACT_GEGLU_ERF:
        passed += 1
        print("  ✅ the two GELU conventions are distinct selectors, not aliases")
    else:
        failed += 1
        print("  ❌ the GELU selectors collapsed onto one value")

    # ── the tolerance scales with magnitude AND reduction width ───────────────
    if mlp_tol_for(1.0, 12288) > mlp_tol_for(1.0, 128) and mlp_tol_for(0.0, 128) > 0.0:
        passed += 1
        print("  ✅ tolerance grows with the reduction width and has a usable floor at zero")
    else:
        failed += 1
        print("  ❌ the tolerance ignores width or lacks a floor")

    print("  [mlpk.contract] Passed:", passed, "Failed:", failed)
