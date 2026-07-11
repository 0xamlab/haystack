# algenta-runtime-native

Internal runtime artifact package for [`algenta`](https://pypi.org/project/algenta/).

Users do not install this package directly. `pip install algenta` resolves the
matching platform runtime automatically. The wheel carries the prebuilt Algenta
runtime worker, signed manifest, and release public key needed for offline
integrity verification.

Wheels-only, per-platform (macOS arm64 + Linux x86_64 first). Built and signed by
the `build-runtime` workflow.
