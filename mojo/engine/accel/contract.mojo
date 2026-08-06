"""
accel.contract — status vocabulary and the backend-selection rules for the GPU plane. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_accel_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_accel.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`accel` owns **340-359**, between gemm 320-339 and attnk 360-379 (rule 4e).

No silent fallback, and the reason it needs a status code
-----------------------------------------------------------
Every entry point in this plane takes a policy: `auto`, `accel` or `cpu`. `auto` resolves once and
REPORTS what it chose. `accel` on a host that cannot serve it returns
`ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE` rather than quietly running on the CPU.

That distinction is the entire point of the code existing. A caller who asks for `auto` wants the
fastest correct answer. A caller who asks for `accel` is usually pinning a backend for a
reproducibility run or a benchmark — and silently handing them a different backend makes their result
wrong in a way no assertion catches, because the numbers are still plausible. So the two requests get
different failure behaviour, and every result carries the backend that actually ran.

Why capability detection is separate from kernel launch
---------------------------------------------------------
Measured on this toolchain: constructing a `DeviceContext` and reading its name requires NO Metal
shader compiler. Only an actual kernel launch triggers shader codegen — and a launch that is
statically reachable triggers it AT COMPILE TIME, so a build host without a shader compiler cannot
build a binary that contains one.

That is why capability queries live in `accel.device` as ordinary contract functions while every
launch entry point in `accel.launch` is private (leading underscore) and therefore never enters the
generated dispatch. A host with no shader compiler still builds, still answers "is there an
accelerator", and still refuses `accel` honestly. See `accel/__init__.mojo` for the measurements.

Public API:
  accel_status_name(code)                              — the status vocabulary
  accel_policy_known(policy)                           — auto | accel | cpu, nothing else
  accel_policy_name(policy)                            — for reporting which was requested
  accel_backend_name(backend)                          — for reporting which actually ran
  accel_resolve(policy, gpu_available)                 — the one place the choice is made
  accel_worth_offloading(cells, intensity, ...)        — a cost model, not a guess
"""

from gpu_kernels import kernel_launch_overhead_ratio, roofline_performance
from tensorx.contract import tx_finite

# ── status codes: accel owns 340-359 ──────────────────────────────────────────

comptime ACCEL_OK: Int = 340
comptime ACCEL_ERR_UNKNOWN_POLICY: Int = 341
comptime ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE: Int = 342
comptime ACCEL_ERR_NON_FINITE_SCALAR: Int = 343
comptime ACCEL_ERR_EMPTY_DIM: Int = 344
comptime ACCEL_ERR_NO_DEVICE: Int = 345
comptime ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT: Int = 346

# ── policies: what the caller asked for ───────────────────────────────────────

comptime ACCEL_POLICY_AUTO: Int = 0
comptime ACCEL_POLICY_ACCEL: Int = 1
comptime ACCEL_POLICY_CPU: Int = 2

# ── backends: what actually ran ───────────────────────────────────────────────

comptime ACCEL_BACKEND_CPU: Int = 0
comptime ACCEL_BACKEND_METAL: Int = 1
comptime ACCEL_BACKEND_CUDA: Int = 2
comptime ACCEL_BACKEND_ROCM: Int = 3
comptime ACCEL_BACKEND_NONE: Int = 4
"""`NONE` is not `CPU`. It means no backend was selected because the request was refused, and it
exists so a result carrying a refusal cannot be misread as a CPU result."""

comptime ACCEL_MIN_OFFLOAD_CELLS: Int = 1 << 16
"""Below ~65k cells, offloading is not worth the launch. Measured in the same place and for the same
reason as `gemm.blocked`'s parallel threshold: dispatch has a fixed cost, and a small kernel spends
more time being scheduled than being computed. This is the DEFAULT floor; `accel_worth_offloading`
takes a real cost model on top of it."""


def accel_status_name(code: Int) -> String:
    """Name a status code. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == ACCEL_OK:
        return String("ok")
    if code == ACCEL_ERR_UNKNOWN_POLICY:
        return String("unknown_policy")
    if code == ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE:
        return String("forced_backend_unavailable")
    if code == ACCEL_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == ACCEL_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == ACCEL_ERR_NO_DEVICE:
        return String("no_accelerator_present")
    if code == ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT:
        return String("shader_toolchain_absent")
    return String("unknown_status")


def accel_policy_name(policy: Int) -> String:
    """Name a policy, for reporting what was REQUESTED alongside what ran."""
    if policy == ACCEL_POLICY_AUTO:
        return String("auto")
    if policy == ACCEL_POLICY_ACCEL:
        return String("accel")
    if policy == ACCEL_POLICY_CPU:
        return String("cpu")
    return String("unknown_policy")


def accel_backend_name(backend: Int) -> String:
    """Name a backend, for the `device_used` field every result carries."""
    if backend == ACCEL_BACKEND_CPU:
        return String("cpu")
    if backend == ACCEL_BACKEND_METAL:
        return String("metal")
    if backend == ACCEL_BACKEND_CUDA:
        return String("cuda")
    if backend == ACCEL_BACKEND_ROCM:
        return String("rocm")
    if backend == ACCEL_BACKEND_NONE:
        return String("none")
    return String("unknown_backend")


def accel_policy_known(policy: Int) -> Bool:
    """True for a policy this plane implements.

    An unrecognised policy is refused rather than treated as `auto`. Defaulting would mean a typo in
    a config silently selects a backend the caller did not ask for — which is the failure this whole
    module exists to prevent, arriving through the front door.
    """
    return (
        policy == ACCEL_POLICY_AUTO
        or policy == ACCEL_POLICY_ACCEL
        or policy == ACCEL_POLICY_CPU
    )


def accel_resolve(policy: Int, gpu_backend: Int, gpu_usable: Bool) -> Int:
    """Resolve a policy to the backend that will run, or a negative status if it cannot.

    The ONE place the choice is made, so there is exactly one thing to test and exactly one thing to
    change when a backend is added. Returns a backend constant on success, or the NEGATED status code
    on refusal — negative so a caller cannot mistake a refusal for `ACCEL_BACKEND_CPU`, which is zero.

    `gpu_usable` is deliberately separate from "a device exists". A machine can have an accelerator
    and still be unable to run a kernel on it — no shader compiler at build time is the case this
    tree hit — and conflating the two produces the worst possible message: "no GPU found" on a
    machine with a GPU.

    @capability accel_resolve
    complexity: O(1)
    @endcapability
    """
    if not accel_policy_known(policy):
        return -ACCEL_ERR_UNKNOWN_POLICY
    if policy == ACCEL_POLICY_CPU:
        return ACCEL_BACKEND_CPU
    if policy == ACCEL_POLICY_ACCEL:
        if not gpu_usable:
            return -ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE
        return gpu_backend
    # auto: take the accelerator when it is genuinely usable, otherwise the CPU, and report it.
    if gpu_usable:
        return gpu_backend
    return ACCEL_BACKEND_CPU


def accel_worth_offloading(
    cells: Int, arithmetic_intensity: Float64, peak_tflops: Float64,
    peak_bandwidth_tbs: Float64, launch_overhead_us: Float64
) -> Bool:
    """True when a kernel of this size and intensity is worth dispatching to an accelerator.

    Built on the frozen cost model rather than a fresh one (rule 3): `roofline_performance` gives the
    achievable rate for this intensity, and `kernel_launch_overhead_ratio` gives the fraction of the
    call that would be pure dispatch. The decision is that the overhead fraction stays under 10%,
    which is the threshold `kernel_launch_overhead_ratio`'s own docstring names as acceptable.

    A size floor alone would be the wrong test. Two kernels with the same cell count and different
    arithmetic intensity have very different runtimes, and it is the RUNTIME that has to dwarf the
    launch, not the element count.

    @capability accel_worth_offloading
    complexity: O(1)
    counts:
    - dim cells <= 1073741824 [kernel_validated]
    @endcapability
    """
    if cells <= 0 or cells > (1 << 30):
        return False
    if not tx_finite(arithmetic_intensity) or not tx_finite(peak_tflops):
        return False
    if not tx_finite(peak_bandwidth_tbs) or not tx_finite(launch_overhead_us):
        return False
    if arithmetic_intensity <= 0.0 or peak_tflops <= 0.0 or peak_bandwidth_tbs <= 0.0:
        return False
    if launch_overhead_us < 0.0:
        return False
    if cells < ACCEL_MIN_OFFLOAD_CELLS:
        return False

    # Frozen kernels: achievable rate for this intensity, then the launch's share of the total.
    var tflops = roofline_performance(arithmetic_intensity, peak_tflops, peak_bandwidth_tbs)
    if tflops <= 0.0:
        return False
    # cells * intensity is a byte count; cells * (flops per cell) is the flop count. Using the
    # intensity to recover flops keeps this consistent with what the roofline was asked about.
    var flops = Float64(cells) * arithmetic_intensity
    var duration_us = flops / (tflops * 1.0e6)
    var overhead = kernel_launch_overhead_ratio(duration_us, launch_overhead_us)
    return overhead < 0.1
