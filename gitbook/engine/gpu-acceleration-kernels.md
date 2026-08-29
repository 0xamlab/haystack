---
icon: bolt
description: Backend selection contract, host device capability probing without compiling a shader, and a threadgroup-tiled GEMM kernel on the Metal GPU.
---

# GPU acceleration kernels

Three modules for the plane that decides whether a kernel runs on an accelerator or the CPU, answers
what accelerator (if any) this host actually has, and supplies one real GPU kernel reachable through
the ordinary contract dispatch. `accel.contract` owns the status vocabulary and the single function
that resolves a policy (`auto` / `accel` / `cpu`) to a backend; `accel.device` answers what this host
can do without ever triggering shader compilation; `accel.gemm_metal` is a tiled `C = A @ B` kernel
that runs on the Metal GPU in Float32. This page documents the kernel family itself — a support
matrix across backends and hardware (Metal, CUDA, ROCm) lives on [GPU support](gpu-support.md).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("accel.contract", "accel_resolve", [1, 1, False])["result"]
# -342 — policy=accel (1) forced on a host without a usable accelerator (gpu_usable=False):
# REFUSED, never silently downgraded to the CPU. 342 is ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE.

runtime.execute("accel.contract", "accel_status_name", [342])["result"]
# "forced_backend_unavailable"

runtime.execute("accel.device", "accel_has_device", [])["result"]
# True or False depending on what this binary was built for and what hardware it's running on —
# see "accel.device: three states, not two" below for what each answer commits to
```

## The modules

| Module | What it does |
| --- | --- |
| `accel.contract` | the status vocabulary (340-359), the one function that resolves a policy to a backend, and the offload cost model that decides whether a kernel is worth dispatching |
| `accel.device` | what accelerator this host has, and whether a kernel could actually run on it, answered without compiling a shader |
| `accel.gemm_metal` | a threadgroup-tiled `C = A @ B` kernel that runs on the Metal GPU in Float32, reachable through the ordinary contract dispatch alongside a launch-free build |

## `accel.contract`: one place the backend choice is made

Every entry point in this plane takes a policy — `auto`, `accel`, or `cpu` — and `accel_resolve`
is the only function that turns one into a backend:

* **`cpu`** always runs on the CPU, whatever hardware exists.
* **`auto`** takes the accelerator when `gpu_usable` is true, the CPU when it is not, and reports
  which one it picked. It is the only policy allowed to fall back.
* **`accel`** pins a backend. Asked for on a host where `gpu_usable` is false, it is **refused**
  (`-ACCEL_ERR_FORCED_BACKEND_UNAVAILABLE`, i.e. `-342`) rather than quietly served by the CPU.

That last rule is the entire reason the module exists: a caller asking for `auto` wants the fastest
correct answer, but a caller asking for `accel` is usually pinning a backend for a reproducibility
run or a benchmark, and silently handing them a different backend produces a result that is wrong in
a way no assertion catches — the numbers stay plausible. Refusals are also **negated** status codes
(`-342`, not `342`), specifically so a caller checking `backend == ACCEL_BACKEND_CPU` (which is `0`)
can never mistake a refusal for a CPU run. An unrecognized policy value is refused the same way
(`accel_resolve(7, ...)` returns `-ACCEL_ERR_UNKNOWN_POLICY`, i.e. `-341`) rather than defaulting to
`auto` — a typo in a config file must not silently pick a backend nobody asked for.

Backends are a closed, five-value set: `cpu` (0), `metal` (1), `cuda` (2), `rocm` (3), and `none`
(4) — `none` is deliberately not `cpu`. It means no backend was selected because the request was
refused, and `accel_backend_name` reports it as the distinct string `"none"` so a refusal can never
render as if the CPU had run.

`accel.contract` owns status codes **340-359** (between `gemm` at 320-339 and `attnk` at 360-379);
`accel_status_name` and `accel_policy_name`/`accel_backend_name` name codes, policies and backends
for logging, and an unrecognized code returns `"unknown_status"` rather than borrowing a
neighbour's meaning.

### The offload decision is a cost model, not a size floor

`accel_worth_offloading(cells, arithmetic_intensity, peak_tflops, peak_bandwidth_tbs,
launch_overhead_us)` decides whether a kernel of a given size and intensity is worth dispatching to
an accelerator at all, built on the frozen `gpu_kernels` roofline (`roofline_performance` for the
achievable rate, `kernel_launch_overhead_ratio` for the launch's share of the call) rather than a
fresh model. The rule: offload only when the launch overhead would stay under 10% of the call.

A plain cell-count floor cannot make this decision correctly, because two kernels with the same cell
count and different arithmetic intensity have very different runtimes, and it is the *runtime* that
has to dwarf the launch, not the element count. `test_accel_contract.mojo` picks a size where the
decision flips: at 20,000,000 cells, a dense kernel (`arithmetic_intensity=100.0`) runs for
~100 microseconds against an 8-microsecond launch (7.4%, worth it) while a sparse one
(`arithmetic_intensity=0.01`) runs for ~50 microseconds (13.8%, not worth it) — identical cell count,
opposite answer:

```python
runtime.execute("accel.contract", "accel_worth_offloading",
                [20000000, 100.0, 20.0, 0.4, 8.0])["result"]
# True

runtime.execute("accel.contract", "accel_worth_offloading",
                [20000000, 0.01, 20.0, 0.4, 8.0])["result"]
# False
```

There is also a hard floor, `ACCEL_MIN_OFFLOAD_CELLS` = `1 << 16` (65,536 cells): below it, nothing
offloads however dense — at 65k cells the kernel itself runs in ~0.33 microseconds against an
8-microsecond launch, and no intensity rescues that. Non-finite or non-positive inputs (`cells <= 0`,
negative intensity, zero peak TFLOPS, and so on) all refuse rather than answering with a guess.

## `accel.device`: three states, not two

`accel_has_device() -> Bool`, `accel_device_probe() -> DeviceProbe`, and `accel_device_name_len() ->
Int` answer what this host can do *without ever compiling a shader* — constructing a `DeviceContext`
and reading its name requires no Metal/CUDA shader compiler; only an actual kernel launch triggers
shader codegen, and `accel.device` never launches one. That is what lets these functions run as
ordinary, always-buildable contract functions while every launch entry point in `accel.launch` stays
private and out of the generated dispatch.

`DeviceProbe` carries five fields: `device_present`, `launch_verified`, `backend`, `name_length`, and
`status`. The module docstring names three real states a host can be in, and the middle one is the
one collapsing-to-two would get wrong:

| State | Meaning |
| --- | --- |
| no device | `has_accelerator()` is false — a CPU-only host |
| device present, not usable | there is an accelerator but a kernel cannot run on it |
| usable | a kernel will run |

The middle state is not hypothetical — this tree hit it: an Apple machine with a working GPU where
the Metal shader compiler was not installed, so `has_accelerator()` returned true and every launch
still failed. Reporting that as "no GPU found" would send someone hunting for hardware they already
have, so `accel_device_probe` reports device presence and launch usability as separate questions.
`launch_verified` is deliberately never set true by this module — proving a launch works means
running one, which needs the shader compiler this module exists to avoid depending on, so the field
stays `False` here and is only set by a caller that has actually launched something (`accel.launch`).

On a binary built for a target with no detectable accelerator — every release CI runner, and the
default build of this module — the probe compiles to an honest constant rather than a runtime
check: `accel_device_probe()` returns `DeviceProbe(False, False, ACCEL_BACKEND_NONE, 0,
ACCEL_ERR_NO_DEVICE)`, i.e. `(device_present=False, launch_verified=False, backend=4,
name_length=0, status=345)`. That is not a stub for CI's comfort — a binary compiled without
accelerator support genuinely cannot open a device on any host it is ever copied to, so "no device"
is the only truthful answer such a binary can give.

{% hint style="info" %}
**Why the compile-time gate exists at all.** `DeviceContext()` is parameterized on the compile-time
target accelerator architecture, and instantiating it on a target with no detectable accelerator
fails in the Mojo stdlib with `"Unknown GPU architecture detected"` — at *compile* time, before any
runtime check runs. A runtime `if not has_accelerator()` does not prevent this, because a runtime
`if` still elaborates both branches, and elaborating the dead branch is what fails; the guard has to
be `@parameter if` so the `DeviceContext` instantiation is pruned before it is type-checked. This is
the same mechanism `accel.gemm_metal` uses for its launch, applied here to the capability query
itself. Two spellings of "no accelerator" both had to be handled: a host with none detectable
compiles with `has_accelerator() == False`, and a `--target-accelerator=none` build compiles with
`has_accelerator() == True` but still fails to instantiate a device — hence `accel.device`'s gate
checks both `has_accelerator()` *and* that the architecture string is not `"none"`.
{% endhint %}

## `accel.gemm_metal`: a real GPU launch, still contract-reachable

`gemm_metal_available() -> Bool`, `gemm_metal_flat(a, b, m, n, k) -> MetalGemmResult`, and
`gemm_metal_agreement(a, b, m, n, k) -> MetalGemmAgreement` run a threadgroup-tiled `C = A @ B` on
the Metal GPU over flat, row-major Float64 buffers (narrowed to Float32 on the way in, widened back
on the way out). `MetalGemmResult` carries `c`, `rows`, `cols`, `backend_used`, and `status`;
`MetalGemmAgreement` carries `max_abs_delta`, `float32_bound`, `within_float32_precision`,
`n_compared`, and `status`.

Shader codegen follows the call graph at compile time, so a reachable kernel launch would normally
force every build host to own a shader compiler. This module's launch sits inside `@parameter if
ACCEL_GPU_BUILD` (`ACCEL_GPU_BUILD = is_defined["ALGENTA_GPU"]()`), a compile-time branch that is
elided entirely — not skipped, *removed* — before shader codegen runs when the flag is unset. That
is what lets this be an ordinary contract function reachable from `library_execute` instead of
something only a GPU-flagged benchmark binary can reach:

```python
# The default build — no -D ALGENTA_GPU, the build every CI runner and most local dev use:
runtime.execute("accel.gemm_metal", "gemm_metal_available", [])["result"]
# False

runtime.execute("accel.gemm_metal", "gemm_metal_flat",
                [a_flat, b_flat, 40, 33, 24])["result"]
# status == 346 (ACCEL_ERR_SHADER_TOOLCHAIN_ABSENT) — the module compiled and linked; it is
# honestly reporting that no GPU kernels were built in, not crashing or silently using the CPU
```

`test_accel_gemm_metal.mojo` runs on every host and asserts different things depending on which of
three states the build is in:

| Build flag | Accelerator | Expected status |
| --- | --- | --- |
| `-D ALGENTA_GPU` unset | either | `shader_toolchain_absent` (346) — the binary still builds |
| set | absent | `no_accelerator_present` (345) |
| set | present | a correct product |

Never a silent CPU substitution in any of the three rows: `accel.contract.accel_resolve` is the only
place a caller opts into a CPU fallback, and this kernel refuses rather than defeating that.

### The precision difference is declared, not hidden

`gemm.blocked.sgemm_flat` (the CPU path) computes in Float64; `gemm_metal_flat` computes in
**Float32**, because that is what the GPU is for — Apple silicon has no meaningful Float64
throughput, and a Float64 Metal kernel would be slower than the CPU it is trying to beat. The two
kernels therefore do not compute the same function, and `gemm_metal_agreement` reports the measured
delta against a bound scaled to the problem size (`f32_eps * k * (1 + |value|)`, with
`f32_eps = 1.1920929e-7`) rather than asserting a fixed tolerance nobody could meet — a longer inner
dimension `k` accumulates more rounding, so a fixed bound would pass at `k=16` and fail at `k=4096`
on identical code.

`test_accel_gemm_metal.mojo` proves the bound is meaningful rather than vacuous by checking it *can*
fail: on a GPU build with a device present, a 40×33 product from `k=24` (every dimension a partial
tile, chosen specifically to exercise the tiling's edge cases) agrees with the CPU kernel within the
Float32 bound, and the test separately asserts `max_abs_delta > 1e-12` — i.e. it would *fail* a
Float64 tolerance, confirming the two precisions really do differ and the Float32 bound is a
considered choice, not an unfalsifiable one.

A known-value check in the same file — identity times a matrix returns that matrix — catches a
transposed index in a way agreement-against-another-kernel alone could not:

```python
# dim = 20; ident is the 20x20 identity, mat is pseudo-random data
# On a GPU build with a Metal device present:
runtime.execute("accel.gemm_metal", "gemm_metal_flat",
                [ident_flat, mat_flat, 20, 20, 20])["result"]
# c == mat to within 1e-6 (worst_ident < 1.0e-6 in the test) — indices are not transposed
```

Further shapes in the same suite push on different edges: a 100×70 product from `k=50` spans
several threadgroups so the shared-memory tile is reloaded and the second `barrier()` is
load-bearing (agreement holds); a 17×9 product from `k=65` has three distinct dimensions, so a
kernel that confused two of them would produce a wrong shape or wrong values instead of accidentally
still working (it matches the CPU kernel to `< 1e-4`).

### Refusals that hold before any GPU is involved

`gemm_metal_flat` validates shape before the compile-time gate is even checked, so these refusals
fire in *every* build:

* `m <= 0`, `n <= 0`, or `k <= 0` — refused with `ACCEL_ERR_EMPTY_DIM` (344).
* Any edge past `ACCEL_GEMM_MAX_DIM` (`1 << 14` = 16,384) — refused with `ACCEL_ERR_EMPTY_DIM`
  before any buffer is allocated. The ceiling exists because 16384² in Float32 is 1 GiB per operand,
  and refusing up front is a far more legible failure than a device out-of-memory error mid-launch.
* `len(a) < m * k` or `len(b) < k * n` — also `ACCEL_ERR_EMPTY_DIM`. `test_accel_gemm_metal.mojo`
  exercises this with what it calls "the A-Z call shape" — 5-element `a`/`b` lists against
  `m=n=k=5` (which needs 25 elements) — and asserts the call is refused with a non-`ACCEL_OK` status
  rather than aborting the worker.

### The tile sizes were measured, and they contradict the frozen cost model

Each threadgroup computes a `BM x BN` block of `C` (`BM=BN=32`), stepping `K` in `BK=16`-wide
chunks; each *thread* within a group owns a `TM x TN` (`2x2`) register tile rather than a single
output, which is the whole optimization — a single-output-per-thread kernel does two shared-memory
loads per multiply-add and is bandwidth-bound, while a register tile reuses each loaded value `TM`
(or `TN`) times. Measured hot at a 2048-cube on an M4 Max, the one-output-per-thread version reached
268 GFLOP/s and this tiling reaches 2018 GFLOP/s — 7.5x from the same arithmetic in a different
order.

The specific tile sizes were chosen by measurement, not by scoring candidates through the frozen
`gpu_kernels` roofline — and the two orderings disagree:

| Config | Predicted score (roofline) | Measured hot GFLOP/s |
| --- | --- | --- |
| 32×32, 2×2 | 0.55 (last) | **2018** |
| 64×64, 4×4 | 1.09 | 706 |
| 64×128, 4×8 | 1.46 | 855 |
| 128×128, 8×8 | 2.19 (first) | 620 |

The roofline model ranks by arithmetic intensity, which rewards bigger tiles; what it does not
capture is that a bigger tile means fewer threadgroups, and this GPU hides latency with many small
groups in flight rather than a few large ones — the roofline was written for a machine with a
handful of large SMs, and Apple silicon is not that machine. The measurement is recorded as a
comment in `gemm_metal.mojo` rather than fed back into the cost model: the frozen `gpu_kernels`
kernel keeps its existing behavior and callers, but a reader reaching for `roofline_performance` to
pick a tile size on Apple silicon should know it points the wrong way here.

## Verification

* `mojo/tests/libs/test_accel_contract.mojo` — every row of the `accel_resolve` table above, the
  negated-refusal property, the closed policy vocabulary, and the offload cost model's dense/sparse
  split at 20,000,000 cells and its floor at `ACCEL_MIN_OFFLOAD_CELLS`.
* `mojo/tests/libs/test_accel_device.mojo` — calls all three functions on whatever host the test
  actually runs on (the module's answers are host-dependent by design, so this suite asserts the
  calls succeed rather than pinning a specific `DeviceProbe`).
* `mojo/tests/libs/test_accel_gemm_metal.mojo` — the three-row build/device matrix, the identity,
  multi-threadgroup (100×70), and non-square (17×9×65) correctness checks, and the Float32-vs-Float64
  precision-boundary assertion, all against `gemm.blocked.sgemm_flat` as the CPU oracle.

**Next:** see [GPU support](gpu-support.md) for the backend/hardware verification matrix these
kernels run under, or browse the [engine catalog](catalog.md).
