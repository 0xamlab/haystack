"""test_accel_contract.mojo — backend resolution, the refusal that must not become a fallback, and
the offload cost model.

Hand-written. The assertions that matter:

* `accel` FORCED ON A HOST THAT CANNOT SERVE IT IS REFUSED. This is the single most important
  behaviour in the package. A caller asking for `auto` wants the fastest correct answer; a caller
  asking for `accel` is usually pinning a backend for a reproducibility run, and silently handing
  them the CPU makes their result wrong in a way no assertion catches, because the numbers stay
  plausible.
* A REFUSAL CANNOT BE READ AS A CPU RESULT. `ACCEL_BACKEND_CPU` is zero, so `accel_resolve` returns
  refusals NEGATED. A caller doing `if backend == ACCEL_BACKEND_CPU` on a refusal would otherwise run
  the CPU path having been told the request failed.
* "DEVICE PRESENT" AND "LAUNCH USABLE" ARE DIFFERENT INPUTS. This tree hit the middle state — an
  Apple machine with a working GPU and no Metal shader compiler — and conflating them yields
  "no GPU found" on a machine that has one.
* THE OFFLOAD DECISION IS A COST MODEL, NOT A SIZE FLOOR. Two kernels with identical cell counts and
  different arithmetic intensity have very different runtimes, and it is the runtime that has to
  dwarf the launch.
"""
from accel.contract import (
    ACCEL_BACKEND_CPU,
    ACCEL_BACKEND_METAL,
    ACCEL_BACKEND_NONE,
    ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE,
    ACCEL_ERR_UNKNOWN_POLICY,
    ACCEL_MIN_OFFLOAD_CELLS,
    ACCEL_OK,
    ACCEL_POLICY_ACCEL,
    ACCEL_POLICY_AUTO,
    ACCEL_POLICY_CPU,
    accel_backend_name,
    accel_policy_known,
    accel_policy_name,
    accel_resolve,
    accel_status_name,
    accel_worth_offloading,
)
from attnk.contract import ATTN_OK
from gemm.contract import GEMM_OK
from tensorx.contract import TX_OK


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── the range is exclusive ────────────────────────────────────────────────
    if ACCEL_OK == 340 and ACCEL_ERR_UNKNOWN_POLICY == 341:
        passed += 1
        print("  ✅ accel owns 340-359 as declared")
    else:
        failed += 1
        print("  ❌ the status range moved:", ACCEL_OK)

    if ACCEL_OK != TX_OK and ACCEL_OK != GEMM_OK and ACCEL_OK != ATTN_OK:
        passed += 1
        print("  ✅ no collision with tensorx, gemm or attnk")
    else:
        failed += 1
        print("  ❌ ACCEL_OK collides with a neighbouring package")

    if accel_status_name(ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE) == String("forced_backend_unavailable"):
        passed += 1
        print("  ✅ codes name themselves")
    else:
        failed += 1
        print("  ❌ a status code named itself wrongly")

    if accel_status_name(9999) == String("unknown_status"):
        passed += 1
        print("  ✅ an unknown code says so rather than borrowing a neighbour's meaning")
    else:
        failed += 1
        print("  ❌ an unknown code was given a name")

    # ── the resolution table ──────────────────────────────────────────────────
    # cpu policy: always the CPU, regardless of what hardware exists.
    if accel_resolve(ACCEL_POLICY_CPU, ACCEL_BACKEND_METAL, True) == ACCEL_BACKEND_CPU:
        passed += 1
        print("  ✅ policy=cpu runs on the CPU even when an accelerator is available")
    else:
        failed += 1
        print("  ❌ policy=cpu did not select the CPU")

    # auto: takes the accelerator when usable, the CPU when not — and reports either way.
    if accel_resolve(ACCEL_POLICY_AUTO, ACCEL_BACKEND_METAL, True) == ACCEL_BACKEND_METAL:
        passed += 1
        print("  ✅ policy=auto takes the accelerator when it is usable")
    else:
        failed += 1
        print("  ❌ policy=auto did not take an available accelerator")

    if accel_resolve(ACCEL_POLICY_AUTO, ACCEL_BACKEND_METAL, False) == ACCEL_BACKEND_CPU:
        passed += 1
        print("  ✅ policy=auto falls back to the CPU — the ONLY policy allowed to")
    else:
        failed += 1
        print("  ❌ policy=auto did not fall back")

    # THE headline: accel forced on an unusable host is refused, not silently downgraded.
    var forced = accel_resolve(ACCEL_POLICY_ACCEL, ACCEL_BACKEND_METAL, False)
    if forced == -ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE:
        passed += 1
        print("  ✅ policy=accel on an unusable host is REFUSED, never downgraded to the CPU")
    else:
        failed += 1
        print("  ❌ a forced accel request was silently served by something else:", forced)

    # And the refusal cannot be misread as a CPU result, because CPU is zero.
    if forced < 0 and ACCEL_BACKEND_CPU == 0:
        passed += 1
        print("  ✅ a refusal is negative, so it cannot be mistaken for ACCEL_BACKEND_CPU")
    else:
        failed += 1
        print("  ❌ a refusal could be read as a CPU result")

    if accel_resolve(ACCEL_POLICY_ACCEL, ACCEL_BACKEND_METAL, True) == ACCEL_BACKEND_METAL:
        passed += 1
        print("  ✅ policy=accel on a usable host runs on the accelerator")
    else:
        failed += 1
        print("  ❌ a valid forced request was refused")

    # ── an unknown policy is refused, never defaulted ─────────────────────────
    if accel_resolve(7, ACCEL_BACKEND_METAL, True) == -ACCEL_ERR_UNKNOWN_POLICY:
        passed += 1
        print("  ✅ an unknown policy is refused rather than treated as auto")
    else:
        failed += 1
        print("  ❌ an unknown policy was defaulted")

    if accel_policy_known(ACCEL_POLICY_AUTO) and not accel_policy_known(-1):
        passed += 1
        print("  ✅ the policy vocabulary is closed")
    else:
        failed += 1
        print("  ❌ the policy vocabulary is not closed")

    # ── reporting ─────────────────────────────────────────────────────────────
    if (
        accel_policy_name(ACCEL_POLICY_ACCEL) == String("accel")
        and accel_backend_name(ACCEL_BACKEND_METAL) == String("metal")
        and accel_backend_name(ACCEL_BACKEND_NONE) == String("none")
    ):
        passed += 1
        print("  ✅ policies and backends name themselves for the device_used field")
    else:
        failed += 1
        print("  ❌ a policy or backend named itself wrongly")

    if accel_backend_name(ACCEL_BACKEND_NONE) != accel_backend_name(ACCEL_BACKEND_CPU):
        passed += 1
        print("  ✅ 'none' and 'cpu' are distinct — a refusal is not a CPU run")
    else:
        failed += 1
        print("  ❌ 'none' and 'cpu' report identically")

    # ── the offload cost model ────────────────────────────────────────────────
    # A tiny kernel is never worth a launch, whatever its intensity.
    if not accel_worth_offloading(1024, 10.0, 20.0, 0.4, 8.0):
        passed += 1
        print("  ✅ a 1024-cell kernel is not worth a launch")
    else:
        failed += 1
        print("  ❌ a tiny kernel was recommended for offload")

    # A large, compute-dense kernel is.
    if accel_worth_offloading(1 << 26, 40.0, 20.0, 0.4, 8.0):
        passed += 1
        print("  ✅ a 67M-cell compute-dense kernel is worth a launch")
    else:
        failed += 1
        print("  ❌ a large dense kernel was rejected for offload")

    # SAME cell count, different intensity: the low-intensity kernel is memory-bound, runs for half
    # as long, and the launch therefore eats a bigger share of it. This is the case a plain size floor
    # cannot see — and the size is chosen to sit exactly where the decision flips: at 20M cells the
    # dense kernel runs 100us (launch is 7.4% of the call, offload) while the sparse one runs 50us
    # (13.8%, refuse). At 65k cells BOTH refuse, correctly, because the kernel is 0.33us against an
    # 8us launch — no intensity rescues a kernel that small, which is why the floor exists too.
    var dense = accel_worth_offloading(20000000, 100.0, 20.0, 0.4, 8.0)
    var sparse = accel_worth_offloading(20000000, 0.01, 20.0, 0.4, 8.0)
    if dense and not sparse:
        passed += 1
        print("  ✅ at an identical cell count, intensity decides — a size floor could not")
    else:
        failed += 1
        print("  ❌ the cost model ignored arithmetic intensity:", dense, sparse)

    # The floor itself: even a maximally dense kernel below it is refused.
    if not accel_worth_offloading(ACCEL_MIN_OFFLOAD_CELLS - 1, 1000.0, 20.0, 0.4, 8.0):
        passed += 1
        print("  ✅ below the cell floor nothing offloads, however dense")
    else:
        failed += 1
        print("  ❌ a sub-floor kernel was recommended for offload")

    # Nonsense inputs are refused rather than producing a confident answer.
    if (
        not accel_worth_offloading(0, 10.0, 20.0, 0.4, 8.0)
        and not accel_worth_offloading(1 << 20, -1.0, 20.0, 0.4, 8.0)
        and not accel_worth_offloading(1 << 20, 10.0, 0.0, 0.4, 8.0)
    ):
        passed += 1
        print("  ✅ empty, negative and zero-capability inputs all refuse")
    else:
        failed += 1
        print("  ❌ the cost model answered on nonsense input")

    print("  [accel.contract] Passed:", passed, "Failed:", failed)
