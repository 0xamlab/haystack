"""
accel.device — what accelerator this host has, answered without compiling a shader. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_accel_device.mojo
benchmark: benchmarks/mojo_benchmarks/bench_accel.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

This module imports `std.gpu` and is still safe to build anywhere
--------------------------------------------------------------------
Measured on this toolchain, and it is the fact the whole package layout rests on: constructing a
`DeviceContext` and reading its properties requires NO shader compiler. Only an actual kernel LAUNCH
triggers shader codegen, and a statically reachable launch triggers it at COMPILE time.

So this module can query the device from ordinary contract functions, while every launch entry point
in `accel.launch` stays private and out of the generated dispatch. A build host with no shader
compiler compiles this file, links it, and answers honestly at runtime.

...as long as the DEVICE QUERY itself sits behind a compile-time gate
------------------------------------------------------------------------
"No shader compiler" is not the only thing a build host can lack. `DeviceContext()` is parameterized
on the compile-time target accelerator architecture, and instantiating it on a target with NO
detectable accelerator fails in the stdlib with "Unknown GPU architecture detected" — at COMPILE
time, before any runtime check runs. Every release CI runner is such a target (build-runtime run
30706203629 failed on both platforms the first time a shard included this module).

A runtime `if not has_accelerator()` does NOT prevent that: `has_accelerator()` is a compile-time
target query, but a runtime `if` still ELABORATES both branches, and elaborating the dead branch is
what fails. The branch has to be `@parameter if` so the `DeviceContext` instantiation is pruned
before it is type-checked. That is the same mechanism `accel.gemm_metal` already uses for its
launch, applied here to the query.

The gate is `ACCEL_DEVICE_QUERY_COMPILED` below. When it is false the functions in this module
compile as honest constants: no device, name length zero, `ACCEL_ERR_NO_DEVICE`. That is not a
white lie for CI's benefit — a binary compiled without accelerator support genuinely cannot open a
device, on any host it is ever copied to, so "no device" is the only answer such a binary can ever
truthfully give. This follows the runtime-wide convention that an unavailable backend refuses with
a typed answer instead of disappearing from the contract.

Three states, not two
-----------------------
| State | Meaning |
|---|---|
| no device | `has_accelerator()` is false — a CPU-only host |
| device present, not usable | there IS an accelerator but a kernel cannot be run on it |
| usable | a kernel will run |

The middle state is real and this tree hit it: an Apple machine with a working GPU where the Metal
shader compiler was not installed, so `has_accelerator()` returned true and every launch failed.
Collapsing that into "no GPU found" would have sent someone hunting for hardware they already had.

`accel_device_probe` therefore reports the device separately from whether a launch would work, and
the caller sees which of the three it is.

Public API:
  accel_has_device()                 -> Bool
  accel_device_probe()               -> DeviceProbe
  accel_device_name_len()            -> Int
"""

from max.gpu.host import DeviceContext
from std.sys import has_accelerator
from std.sys.info import _accelerator_arch
from accel.contract import (
    ACCEL_BACKEND_METAL,
    ACCEL_BACKEND_NONE,
    ACCEL_ERR_NO_DEVICE,
    ACCEL_OK,
)

comptime ACCEL_DEVICE_QUERY_COMPILED: Bool = has_accelerator() and _accelerator_arch() != "none"
"""Whether this binary was compiled for a target that can instantiate `DeviceContext` at all.

Both observed "no accelerator" spellings, verified on this toolchain:
  - a host with no detectable accelerator compiles with `_accelerator_arch() == ""`, so
    `has_accelerator()` is false (this is every release CI runner);
  - `--target-accelerator=none` compiles with the arch string `"none"`, for which
    `has_accelerator()` is TRUE but `DeviceContext` still refuses to instantiate
    ("GPU architecture 'none' is not supported") — hence the explicit second clause.

Checked with `@parameter if`, never a runtime `if`: pruning must happen before the dead branch is
elaborated, because elaboration of `DeviceContext()` on a no-accelerator target is itself the
compile error."""


@fieldwise_init
struct DeviceProbe(Copyable, Movable):
    """What this host can do, and how confident the answer is.

    `launch_verified` is deliberately NOT set by this module. Proving a launch works means running
    one, which requires the shader compiler this module exists to avoid depending on — so the field
    is reported as false here and set by whichever caller has actually launched something. A probe
    that guessed would be asserting exactly the thing it cannot check."""

    var device_present: Bool
    var launch_verified: Bool
    var backend: Int
    var name_length: Int
    var status: Int


def accel_has_device() -> Bool:
    """True when the toolchain reports an accelerator on this host.

    Says nothing about whether a kernel can RUN on it — see the three states in the module docstring.
    Kept as its own function because it is the one question that is always answerable, on every host,
    with no device construction at all.

    @capability accel_has_device
    complexity: O(1)
    @endcapability
    """

    @parameter
    if not ACCEL_DEVICE_QUERY_COMPILED:
        # Gated for CONSISTENCY, not necessity: this function compiles on every target. But a
        # binary whose probe can only ever answer "no device" must not report a device here, or the
        # two functions would disagree about the same host.
        return False
    else:
        return has_accelerator()


def accel_device_name_len() -> Int:
    """Length of the accelerator's name, or 0 when there is none.

    The LENGTH rather than the name. A `String` return would be fine for the contract, but the name
    is host-identifying and this function's job is a capability answer, not a machine fingerprint —
    the length is enough to prove a device was really opened. `accel.launch` reports the full name to
    a local caller that has already chosen to open the device.

    @capability accel_device_name_len
    complexity: O(1)
    @endcapability
    """

    @parameter
    if not ACCEL_DEVICE_QUERY_COMPILED:
        # No-accelerator target: the `DeviceContext()` below must be pruned BEFORE elaboration or
        # this module does not compile at all — see the module docstring and the gate's own.
        return 0
    else:
        # Inside this branch `has_accelerator()` is compile-time true, so the old runtime
        # early-return on it would be dead code; the try/except carries the real middle state.
        try:
            var ctx = DeviceContext()
            return ctx.name().byte_length()
        except:
            # A device that is present but cannot be opened. Reported as zero rather than raised:
            # this is a capability query, and a query that throws is harder to use than one that
            # answers.
            return 0


def accel_device_probe() -> DeviceProbe:
    """The full capability answer, without compiling a shader.

    @capability accel_device_probe
    complexity: O(1)
    @endcapability
    """

    @parameter
    if not ACCEL_DEVICE_QUERY_COMPILED:
        # A binary compiled without accelerator support cannot open a device on ANY host, so this
        # is the truthful answer everywhere the binary can ever run — not a stub for CI's comfort.
        return DeviceProbe(False, False, ACCEL_BACKEND_NONE, 0, ACCEL_ERR_NO_DEVICE)
    else:
        var name_len = accel_device_name_len()
        if name_len == 0:
            # Present but not openable. Still not `ACCEL_OK`, and still not "no device".
            return DeviceProbe(True, False, ACCEL_BACKEND_NONE, 0, ACCEL_ERR_NO_DEVICE)

        # This build ships ONE accelerator backend, so the answer is Metal or nothing.
        # Discriminating CUDA from ROCm from Metal is deliberately NOT attempted here: the tree has
        # no CUDA or ROCm kernels yet, and a probe that reported `cuda` on a Linux host would be
        # claiming a backend that does not exist. The discrimination arrives with the backends, not
        # before them.
        return DeviceProbe(True, False, ACCEL_BACKEND_METAL, name_len, ACCEL_OK)
