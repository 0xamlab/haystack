# algenta-runtime-native

The **proprietary** native runtime for [`algenta`](https://pypi.org/project/algenta/) — a per-platform wheel
that carries the prebuilt in-process engine and its RS256-signed manifest.

You don't install this directly; `pip install algenta` pulls the matching per-platform build automatically
(it's a hard-pinned dependency). It has no public API and no command — the `algenta` CLI loads it in-process
via `importlib.resources`, verifying the signed manifest + SHA-256 + ABI before use.

Wheels-only, per-platform (macOS arm64 + Linux x86_64 first). Built + signed by the `build-runtime` CI.
