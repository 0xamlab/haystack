"""Algenta bundled native runtime (lazy).

Importing this package must NOT load the native library or import the engine — the loader in
``algenta.runtime.loader`` opens ``libalgenta_runtime.*`` via ctypes only on first ``execute``, after
verifying the signed manifest. Keep this module free of eager native/engine imports.
"""
