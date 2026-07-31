"""test_lossk_contract.mojo — the status range, the logit budget, and the target guard.

Hand-written. What is worth asserting here:

* THE LOGIT BUDGET IS A SEPARATE CHECK from the work budget, and it must be, because they answer
  different questions. Total work may legitimately be enormous — that is what chunking is for — while
  peak resident logits must stay small. A single budget could not express both.
* THE STATUS RANGE DOES NOT COLLIDE with the five packages before it (rule 4e).
* A NEGATIVE TARGET IS REFUSED rather than read as "ignore this token". Masking is a real need and
  -100 is a real convention, but accepting a magic negative means a genuine off-by-one producing -1
  is silently skipped and the loss still looks reasonable.
* THE WORK GUARD DOES NOT WRAP. Three large factors — tokens, hidden, vocabulary — is the biggest
  product anywhere in the plane.
"""
from attnk.contract import ATTN_OK
from gemm.contract import GEMM_OK
from lossk.contract import (
    LOSS_ERR_BAD_CHUNK,
    LOSS_ERR_DIM_TOO_LARGE,
    LOSS_ERR_EMPTY_DIM,
    LOSS_ERR_WORK_TOO_LARGE,
    LOSS_MAX_DIM,
    LOSS_MAX_LOGIT_CELLS,
    LOSS_MAX_TOKENS,
    LOSS_MAX_VOCAB,
    LOSS_MAX_WORK_CELLS,
    LOSS_OK,
    loss_chunk_check,
    loss_dims_check,
    loss_logit_cells,
    loss_status_name,
    loss_targets_in_range,
    loss_tol_for,
    loss_work_fits,
)
from mlpk.contract import MLP_OK
from normk.contract import NORM_OK
from tensorx.contract import TX_OK


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the range is exclusive ────────────────────────────────────────────────
    if LOSS_OK == 580 and LOSS_ERR_BAD_CHUNK == 587:
        passed += 1
        print("  ✅ lossk owns 580-599 as declared")
    else:
        failed += 1
        print("  ❌ the status range moved:", LOSS_OK)

    if (
        LOSS_OK != TX_OK and LOSS_OK != GEMM_OK and LOSS_OK != ATTN_OK
        and LOSS_OK != NORM_OK and LOSS_OK != MLP_OK
    ):
        passed += 1
        print("  ✅ no collision with the five packages before it")
    else:
        failed += 1
        print("  ❌ LOSS_OK collides with a neighbouring package")

    if loss_status_name(LOSS_ERR_BAD_CHUNK) == String("chunk_exceeds_logit_budget"):
        passed += 1
        print("  ✅ codes name themselves")
    else:
        failed += 1
        print("  ❌ a status code named itself wrongly")

    if loss_status_name(4242) == String("unknown_status"):
        passed += 1
        print("  ✅ an unknown code says so rather than borrowing a neighbour's meaning")
    else:
        failed += 1
        print("  ❌ an unknown code was given a name")

    # ── the logit budget is its own question ──────────────────────────────────
    # A Qwen3 batch: total work is huge and legal; peak logits must still be bounded.
    if loss_dims_check(2048, 4096, 151936) == LOSS_OK:
        passed += 1
        print("  ✅ a real Qwen3 training shape passes the work check")
    else:
        failed += 1
        print("  ❌ a real training shape was refused")

    if loss_chunk_check(2048, 151936) == LOSS_ERR_BAD_CHUNK:
        passed += 1
        print("  ✅ using the BATCH size as the chunk is refused — the obvious mistake, caught")
    else:
        failed += 1
        print("  ❌ an over-budget chunk was accepted")

    if loss_chunk_check(256, 151936) == LOSS_OK:
        passed += 1
        print("  ✅ a 256-token chunk against a 151,936 vocabulary is accepted")
    else:
        failed += 1
        print("  ❌ a reasonable chunk was refused")

    # The two budgets are genuinely different: this shape passes one and fails the other.
    var cells = loss_logit_cells(2048, 151936)
    if cells > Float64(LOSS_MAX_LOGIT_CELLS) and loss_work_fits(2048, 4096, 151936, LOSS_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ total work fits while peak logits do not — the two budgets are not one budget")
    else:
        failed += 1
        print("  ❌ the two budgets did not separate:", cells)

    # ── the work guard cannot be walked past by a wrapping product ────────────
    var huge = 1 << 30
    if not loss_work_fits(huge, huge, huge, LOSS_MAX_WORK_CELLS):
        passed += 1
        print("  ✅ a three-factor product that wraps 64 bits is still refused")
    else:
        failed += 1
        print("  ❌ a wrapping product was accepted as fitting")

    if loss_logit_cells(-1, 100) < 0.0 and loss_logit_cells(100, 0) < 0.0:
        passed += 1
        print("  ✅ a malformed cell count is negative, never a small positive")
    else:
        failed += 1
        print("  ❌ a malformed cell count came back usable")

    if loss_dims_check(0, 8, 8) == LOSS_ERR_EMPTY_DIM:
        passed += 1
        print("  ✅ an empty dimension is refused")
    else:
        failed += 1
        print("  ❌ an empty dimension was accepted")

    if loss_dims_check(8, 8, LOSS_MAX_VOCAB + 1) == LOSS_ERR_DIM_TOO_LARGE:
        passed += 1
        print("  ✅ a vocabulary past the ceiling is refused")
    else:
        failed += 1
        print("  ❌ an oversized vocabulary was accepted")

    if loss_dims_check(LOSS_MAX_TOKENS, LOSS_MAX_DIM, LOSS_MAX_VOCAB) == LOSS_ERR_WORK_TOO_LARGE:
        passed += 1
        print("  ✅ three legal dimensions with an illegal product are refused on the budget")
    else:
        failed += 1
        print("  ❌ the work budget did not fire on a legal-by-dimension shape")

    # ── the target guard ──────────────────────────────────────────────────────
    var good = List[Int]()
    good.append(0)
    good.append(4)
    var at_vocab = List[Int]()
    at_vocab.append(5)
    var negative = List[Int]()
    negative.append(-100)

    if loss_targets_in_range(good, 2, 5):
        passed += 1
        print("  ✅ in-range targets pass")
    else:
        failed += 1
        print("  ❌ valid targets were refused")

    if not loss_targets_in_range(at_vocab, 1, 5):
        passed += 1
        print("  ✅ a target equal to vocab is refused — the classic off-by-one")
    else:
        failed += 1
        print("  ❌ an off-by-one target was accepted")

    if not loss_targets_in_range(negative, 1, 5):
        passed += 1
        print("  ✅ -100 is refused rather than silently meaning 'ignore'")
    else:
        failed += 1
        print("  ❌ a negative target was accepted as a mask sentinel")

    # ── the tolerance scales with the reduction it judges ─────────────────────
    if loss_tol_for(1.0, 151936) > loss_tol_for(1.0, 32000) and loss_tol_for(0.0, 100) > 0.0:
        passed += 1
        print("  ✅ tolerance grows with vocabulary and has a usable floor at zero")
    else:
        failed += 1
        print("  ❌ the tolerance ignores vocabulary or lacks a floor")

    print("  [lossk.contract] Passed:", passed, "Failed:", failed)
