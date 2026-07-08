"""Algenta native runtime (proprietary) — the prebuilt in-process engine + its RS256-signed manifest.

This package exists only to CARRY the per-platform native artifacts in their own import namespace:

    libalgenta_runtime.{dylib,so,dll}   # the native runtime
    manifest.json / manifest.sig        # signed integrity manifest

The `algenta` CLI locates this directory via ``importlib.resources.files("algenta_runtime_native")``, then
verifies the manifest signature + SHA-256 + ABI before dlopen'ing the lib in-process. There is no public
Python API here — do NOT import it for functionality. Ships as per-platform wheels only (no sdist).
"""

__version__ = "1.0.0"
