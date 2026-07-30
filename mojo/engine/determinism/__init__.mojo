"""
determinism — reproducible randomness and replay identity.

Existing kernels that sample are left exactly as they are; nothing here changes
their behaviour. These modules give NEW surfaces a way to be reproducible, and give
the capability manifest something concrete to point at when it declares a function
non-deterministic.

Modules:
  counter_rng — Philox4x64-10 counter-based randomness: every draw is a pure
                function of its coordinates, so the same logical draw reproduces
                regardless of what ran before it.
  streams     — name-addressed independent streams over that counter space.

Invoked directly by callers rather than through `library_execute`, so this package
is excluded from the runtime-library inventory (`_SKIP_RUNTIME_DIRS`) — its UInt64
coordinate parameters are not FFI-marshalable anyway.
"""
