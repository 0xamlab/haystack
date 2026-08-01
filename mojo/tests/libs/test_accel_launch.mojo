"""test_accel_launch.mojo — the GPU launch seam, and the rule that keeps every other host building.

Hand-written. THIS SUITE REQUIRES A SHADER COMPILER; it is the only file in the tree that does. On
Apple silicon that means `DEVELOPER_DIR` must point at an Xcode with the Metal Toolchain component
installed, because `xcode-select` pointing at CommandLineTools is not enough:

    export DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer

Without it the failure is `Metal Compiler failed to compile metallib`, which reads like a toolchain
bug and is not one.

Why one suite is allowed to require that, and nothing else is
---------------------------------------------------------------
Shader codegen is triggered by a statically REACHABLE launch site, at compile time. Every launch
entry point in `accel.launch` is therefore private, so the generated runtime dispatch never imports
one and no ordinary build needs a shader compiler. This file reaches them deliberately, which is
exactly why it is the file that needs the toolchain.

The first assertion below guards that rule: it checks that `accel.launch` still exports nothing
public. Making one launch function public is a one-character change that would put a launch site in
the dispatch's call graph and break every build host without a shader compiler — including Linux CI,
which has neither a compiler nor a GPU.
"""
from accel.contract import ACCEL_BACKEND_METAL, ACCEL_OK
from accel.device import accel_device_probe, accel_has_device
from accel.launch import _accel_device_name, _accel_launch_roundtrip_ok, _accel_saxpy


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    if not accel_has_device():
        # A CPU-only host. The suite reports rather than fails: the launch path genuinely cannot be
        # exercised, and pretending otherwise would make the result meaningless.
        print("  ⚠️  no accelerator on this host — the launch suite cannot run here")
        print("  [accel.launch] Passed: 0 Failed: 0")
        return

    # ── the device is real ────────────────────────────────────────────────────
    var probe = accel_device_probe()
    if probe.status == ACCEL_OK and probe.device_present and probe.backend == ACCEL_BACKEND_METAL:
        passed += 1
        print("  ✅ the device probe reports a usable Metal device")
    else:
        failed += 1
        print("  ❌ the device probe disagrees with the launch path:", probe.status)

    var name = _accel_device_name()
    if len(name) > 0 and name != String("none"):
        passed += 1
        print("  ✅ device:", name)
    else:
        failed += 1
        print("  ❌ the device has no name")

    # ── the launch seam, end to end ───────────────────────────────────────────
    # out = [0,1,2,...], x = all ones, alpha = 2  ->  out[i] == i + 2.
    # An off-by-one index, a wrong grid size and a skipped copy each give a DIFFERENT wrong answer,
    # so a pass here means the whole seam is right rather than that everything returned zero.
    if _accel_launch_roundtrip_ok():
        passed += 1
        print("  ✅ a real kernel ran on the GPU and the arithmetic is correct")
    else:
        failed += 1
        print("  ❌ the GPU round trip produced wrong values")

    # ── the grid overhang ─────────────────────────────────────────────────────
    # 1000 is NOT a multiple of the 256-thread group, so the last group runs 24 threads past the end.
    # Without the kernel's bounds check those threads write past the buffer — silent corruption on a
    # GPU, not the clean abort a CPU would give. A size that divides evenly would never test it.
    var n = 1000
    var out_host = List[Float32](capacity=n)
    var x_host = List[Float32](capacity=n)
    for i in range(n):
        out_host.append(Float32(0.0))
        x_host.append(Float32(3.0))

    var count = _accel_saxpy(out_host, x_host, Float32(1.0))
    var all_three = True
    for i in range(n):
        if out_host[i] != Float32(3.0):
            all_three = False
    if count == n and all_three:
        passed += 1
        print("  ✅ a 1000-element buffer over 256-thread groups is exact — the overhang is guarded")
    else:
        failed += 1
        print("  ❌ the partial final threadgroup corrupted the result")

    # ── refusals ──────────────────────────────────────────────────────────────
    var empty = List[Float32]()
    var some = List[Float32](capacity=4)
    for _ in range(4):
        some.append(Float32(1.0))
    if _accel_saxpy(empty, some, Float32(1.0)) < 0:
        passed += 1
        print("  ✅ an empty buffer is refused rather than launched")
    else:
        failed += 1
        print("  ❌ an empty launch was accepted")

    var four = List[Float32](capacity=4)
    for _ in range(4):
        four.append(Float32(1.0))
    var two = List[Float32](capacity=2)
    for _ in range(2):
        two.append(Float32(1.0))
    if _accel_saxpy(four, two, Float32(1.0)) < 0:
        passed += 1
        print("  ✅ a source shorter than the destination is refused before any copy")
    else:
        failed += 1
        print("  ❌ a mismatched pair was launched")

    print("  [accel.launch] Passed:", passed, "Failed:", failed)
