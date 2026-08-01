"""
accel — the GPU backend: capability detection, backend policy, and the kernel launch seam.

This is the ONLY package in the tree that imports `std.gpu`. Confining it to one place is not tidiness;
it is what makes the rest of the plane buildable on a host with no shader compiler.

The measurement the whole layout rests on
-------------------------------------------
Verified 2026-07-31 by building the same module three ways on a host with no Metal shader compiler:

| What the caller reaches | Result |
|---|---|
| calls a function that LAUNCHES a kernel | `Metal Compiler failed to compile metallib` — build fails |
| imports only a CPU function from the SAME module that imports `std.gpu` and defines a kernel | **builds** |
| constructs a `DeviceContext` and reads `.name()`, never launching | **builds and runs** |

So shader codegen is triggered per **statically reachable launch site**, not per module and not per
import. A module may import `std.gpu`, define kernels, and export ordinary CPU functions; nothing is
compiled for the GPU until a launch is actually reachable from an entry point.

What that buys, and the rule it imposes
-----------------------------------------
`accel.contract` and `accel.device` are ordinary contract modules — a caller on any host can ask
"is there an accelerator", "which backend", "should this shape be offloaded", and get an honest
answer. `accel` therefore does NOT need to join `_SKIP_RUNTIME_DIRS`.

The rule that makes that safe: **every launch entry point in `accel.launch` is private** (leading
underscore), so the inventory parser skips it and the generated dispatch never imports it. If one
were made public it would enter the runtime contract, the generated dispatch would call it, and the
Linux build would begin requiring a shader compiler it does not have. That is a one-character
mistake with a whole-CI consequence, so it is stated here, in `launch.mojo`, and asserted by a test.

Three device states, not two
------------------------------
A host can have an accelerator and still be unable to run a kernel on it — exactly what happened here
before the Metal toolchain was installed: `has_accelerator()` returned true and every launch failed.
`accel.device` reports device presence separately from launch usability, because collapsing them
gives "no GPU found" on a machine that has one.

No silent fallback
--------------------
`accel_resolve` is the single place a backend is chosen. `auto` picks and REPORTS; `accel` on a host
that cannot serve it is refused rather than quietly run on the CPU, because a caller pinning a
backend is usually pinning it for a reproducibility run, and silently substituting produces numbers
that are wrong and plausible at the same time.

Modules
-------
  contract  — status codes 340-359, policies, backends, the offload cost model
  device    — capability detection that needs no shader compiler
  launch    — GPU kernels and their private launch entry points

Dependency direction is one-way: `accel` uses `tensorx` for finiteness and the frozen `gpu_kernels`
cost model, never the reverse.
"""
