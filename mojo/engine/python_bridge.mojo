"""
Python bridge helpers — minimal Python interop for JSON parsing only.
Never called in hot simulation loops.

CORRECTNESS: py_str must call Python's str() explicitly via the builtins
module to guarantee clean Python string semantics (no encoding issues,
no repr wrappers). String(PythonObject) uses __repr__ in some Mojo
versions which adds quotes and may corrupt variable name lookups.
"""
from std.python import Python, PythonObject

# Cache builtins once per function call — not at module level (unsupported in Mojo v26)
def fast_f64(obj: PythonObject) raises -> Float64:
    """Convert PythonObject number to Float64 via Python float() → str → atof."""
    var b = Python.import_module("builtins")
    return atof(String(b.str(b.float(obj))))

def fast_int(obj: PythonObject) raises -> Int:
    """Convert PythonObject integer to Mojo Int."""
    return Int(py=obj)

def py_str(obj: PythonObject) raises -> String:
    """Convert PythonObject to Mojo String via Python str() — guaranteed clean."""
    var b = Python.import_module("builtins")
    return String(b.str(obj))
