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

from std.gpu.host import DeviceContext
from std.sys import has_accelerator
from accel.contract import (
    ACCEL_BACKEND_METAL,
    ACCEL_BACKEND_NONE,
    ACCEL_ERR_NO_DEVICE,
    ACCEL_OK,
)


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


fn accel_has_device() -> Bool:
    """True when the toolchain reports an accelerator on this host.

    Says nothing about whether a kernel can RUN on it — see the three states in the module docstring.
    Kept as its own function because it is the one question that is always answerable, on every host,
    with no device construction at all.

    @capability accel_has_device
    complexity: O(1)
    @endcapability
    """
    return has_accelerator()


fn accel_device_name_len() -> Int:
    """Length of the accelerator's name, or 0 when there is none.

    The LENGTH rather than the name. A `String` return would be fine for the contract, but the name
    is host-identifying and this function's job is a capability answer, not a machine fingerprint —
    the length is enough to prove a device was really opened. `accel.launch` reports the full name to
    a local caller that has already chosen to open the device.

    @capability accel_device_name_len
    complexity: O(1)
    @endcapability
    """
    if not has_accelerator():
        return 0
    try:
        var ctx = DeviceContext()
        return len(ctx.name())
    except:
        # A device that is present but cannot be opened. Reported as zero rather than raised: this
        # is a capability query, and a query that throws is harder to use than one that answers.
        return 0


fn accel_device_probe() -> DeviceProbe:
    """The full capability answer, without compiling a shader.

    @capability accel_device_probe
    complexity: O(1)
    @endcapability
    """
    if not has_accelerator():
        return DeviceProbe(False, False, ACCEL_BACKEND_NONE, 0, ACCEL_ERR_NO_DEVICE)

    var name_len = accel_device_name_len()
    if name_len == 0:
        # Present but not openable. Still not `ACCEL_OK`, and still not "no device".
        return DeviceProbe(True, False, ACCEL_BACKEND_NONE, 0, ACCEL_ERR_NO_DEVICE)

    # This build ships ONE accelerator backend, so the answer is Metal or nothing. Discriminating
    # CUDA from ROCm from Metal is deliberately NOT attempted here: the tree has no CUDA or ROCm
    # kernels yet, and a probe that reported `cuda` on a Linux host would be claiming a backend that
    # does not exist. The discrimination arrives with the backends, not before them.
    return DeviceProbe(True, False, ACCEL_BACKEND_METAL, name_len, ACCEL_OK)
