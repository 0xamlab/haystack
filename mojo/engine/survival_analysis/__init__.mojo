# survival_analysis — censoring-aware survival and lifetime estimation.
#
# The package is named `survival_analysis` and NOT `survival` on purpose. A directory
# `mojo/engine/survival/` would SHADOW the frozen module `mojo/engine/survival.mojo`:
# a Mojo package directory wins over a same-named module file, so every
# `from survival import kaplan_meier` in the tree — including two blocks in the
# generated dispatch table — would fail to resolve and the worker would stop
# compiling. Measured:
#
#     /tmp/mojocol/foo.mojo + /tmp/mojocol/foo/bar.mojo
#     error: package 'foo' does not contain 'frozen_thing'
#
# So the frozen namespace keeps its name and the new namespace takes a new one.
