"""
runtime — coarse-grained execution layer over the existing kernel library.

The kernel library is reached one call at a time: `execute(module, function, args)`
is unary and synchronous, so a workflow needing N kernels pays N round trips and
re-encodes every intermediate value. These modules add coarse execution on top
WITHOUT changing any kernel: they call the existing generated dispatch table as-is.

Modules:
  batch — execute N library requests in a single frame.

Every module here is invoked through its own message type in main.mojo, never
through `library_execute`, so this package is excluded from the runtime-library
inventory (`_SKIP_RUNTIME_DIRS`). That exclusion is also required to avoid a
circular import: the dispatch table would otherwise import this package while
this package calls the dispatch table.
"""
