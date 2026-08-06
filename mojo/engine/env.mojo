"""
env.mojo — Environment variable access. Uses Python os.environ for stable access.

This module is designed for read-once-at-startup config, not hot-path code.
Python is only used for the actual getenv call; all parsing is pure Mojo.

Public API:
  env_get(key, default="") -> String
  env_get_int(key, default=0) -> Int
  env_get_float(key, default=0.0) -> Float64
  env_get_bool(key, default=False) -> Bool    — "true"/"1"/"yes" → True
  env_is_set(key) -> Bool
"""

from std.python import Python
from conv import parse_float64, parse_int


# ── Core env access ──────────────────────────────────────────────────────────


def _env_get_raw(key: String) raises -> String:
    """Get raw env var value using Python os.environ.get().

    Returns empty string if not set. Raises only on Python init failure.
    """
    var os = Python.import_module("os")
    var result = os.environ.get(key, "")
    return String(result)


def _env_has(key: String) raises -> Bool:
    """Check if env var exists using Python os.environ."""
    var os = Python.import_module("os")
    var result = os.environ.get(key)
    return result is not None


# ── Public API ───────────────────────────────────────────────────────────────


def env_get(key: String, default: String = "") raises -> String:
    """Get environment variable value, returning default if not set.

    Args:
        key: Environment variable name.
        default: Value to return if variable is not set.

    Returns:
        The environment variable value, or default.
    """
    var val = _env_get_raw(key)
    if len(val) == 0:
        # Could be empty or not set — check existence
        if not _env_has(key):
            return default
    return val


def env_get_int(key: String, default: Int = 0) raises -> Int:
    """Get environment variable as integer.

    Args:
        key: Environment variable name.
        default: Value to return if variable is not set or not parseable.

    Returns:
        The parsed integer value, or default.
    """
    var val = _env_get_raw(key)
    if len(val) == 0 and not _env_has(key):
        return default
    if len(val) == 0:
        return default
    return parse_int(val)


def env_get_float(key: String, default: Float64 = 0.0) raises -> Float64:
    """Get environment variable as Float64.

    Args:
        key: Environment variable name.
        default: Value to return if variable is not set or not parseable.

    Returns:
        The parsed float value, or default.
    """
    var val = _env_get_raw(key)
    if len(val) == 0 and not _env_has(key):
        return default
    if len(val) == 0:
        return default
    return parse_float64(val)


def env_get_bool(key: String, default: Bool = False) raises -> Bool:
    """Get environment variable as Bool.

    Truthy values (case-insensitive): "true", "1", "yes"
    Falsy values (case-insensitive): "false", "0", "no", ""
    Anything else returns default.

    Args:
        key: Environment variable name.
        default: Value to return if variable is not set.

    Returns:
        The parsed boolean value, or default.
    """
    var val = _env_get_raw(key)
    if len(val) == 0 and not _env_has(key):
        return default

    # Lowercase the value for comparison
    var lower = _to_lower(val)

    if lower == "true" or lower == "1" or lower == "yes":
        return True
    if lower == "false" or lower == "0" or lower == "no" or lower == "":
        return False
    return default


def env_is_set(key: String) raises -> Bool:
    """Check if an environment variable is set (exists in environment).

    Args:
        key: Environment variable name.

    Returns:
        True if the variable exists, False otherwise.
    """
    return _env_has(key)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _to_lower(s: String) -> String:
    """Convert ASCII string to lowercase."""
    var result = String("")
    var bytes = s.as_bytes()
    var n = len(s)
    for i in range(n):
        var c = bytes[i]
        if c >= UInt8(65) and c <= UInt8(90):  # A-Z
            result += chr(Int(c) + 32)
        else:
            result += chr(Int(c))
    return result
