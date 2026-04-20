"""
test_wave8.mojo — Tests for Wave 8 libraries: JSON Writer, Logger, Env Vars.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave8.mojo
"""
from json.writer import (
    json_object_start,
    json_object_end,
    json_add_string,
    json_add_int,
    json_add_float,
    json_add_bool,
    json_add_null,
    json_add_array_float,
    json_add_array_string,
    json_add_raw,
    json_escape_string,
    json_build_object,
)
from logging.logger import Logger, get_logger, LOG_DEBUG, LOG_INFO
from env import env_get, env_get_int, env_get_float, env_get_bool, env_is_set


def main() raises:
    print("━━━ Wave 8 test suite (JSON Writer, Logger, Env Vars) ━━━")
    print("")

    # ── JSON Writer ──────────────────────────────────────────────────────
    var s = json_object_start()
    s = json_add_string(s, "name", "Algenta")
    s = json_add_int(s, "version", 1)
    s = json_add_float(s, "score", 0.95)
    s = json_add_bool(s, "active", True)
    s = json_add_null(s, "error")
    var vals = List[Float64]()
    vals.append(1.0)
    vals.append(2.0)
    vals.append(3.0)
    s = json_add_array_float(s, "values", vals)
    s = json_object_end(s)
    # Should be valid JSON
    if len(s) <= 10:
        raise Error("JSON writer: output too short, got: " + s)
    # Verify it starts with { and ends with }
    var sb = s.as_bytes()
    if sb[0] != UInt8(123):  # '{'
        raise Error("JSON writer: doesn't start with {, got: " + s)
    if sb[len(s) - 1] != UInt8(125):  # '}'
        raise Error("JSON writer: doesn't end with }, got: " + s)
    print("  Built JSON: " + s)
    print("✅ JSON writer")

    # ── JSON add_array_string ────────────────────────────────────────────
    var s2 = json_object_start()
    var tags = List[String]()
    tags.append("a")
    tags.append("b")
    tags.append("c")
    s2 = json_add_array_string(s2, "tags", tags)
    s2 = json_object_end(s2)
    var s2b = s2.as_bytes()
    if s2b[0] != UInt8(123):
        raise Error("JSON array_string: doesn't start with {")
    if s2b[len(s2) - 1] != UInt8(125):
        raise Error("JSON array_string: doesn't end with }")
    print("  Array string JSON: " + s2)
    print("✅ JSON array string")

    # ── JSON add_raw ─────────────────────────────────────────────────────
    var s3 = json_object_start()
    s3 = json_add_raw(s3, "nested", '{"x":1}')
    s3 = json_object_end(s3)
    var s3b = s3.as_bytes()
    if s3b[0] != UInt8(123):
        raise Error("JSON add_raw: doesn't start with {")
    print("  Raw nested JSON: " + s3)
    print("✅ JSON add_raw")

    # ── JSON escape ──────────────────────────────────────────────────────
    var esc1 = json_escape_string('hello "world"')
    if esc1 != 'hello \\"world\\"':
        raise Error("JSON escape quotes failed, got: " + esc1)

    var esc2 = json_escape_string("line1\nline2")
    if esc2 != "line1\\nline2":
        raise Error("JSON escape newline failed, got: " + esc2)

    var esc3 = json_escape_string("tab\there")
    if esc3 != "tab\\there":
        raise Error("JSON escape tab failed, got: " + esc3)

    var esc4 = json_escape_string("back\\slash")
    if esc4 != "back\\\\slash":
        raise Error("JSON escape backslash failed, got: " + esc4)
    print("✅ JSON escape")

    # ── JSON build_object ────────────────────────────────────────────────
    var pairs = List[List[String]]()
    var p1 = List[String]()
    p1.append("name")
    p1.append('"Algenta"')
    pairs.append(p1^)
    var p2 = List[String]()
    p2.append("ver")
    p2.append("2")
    pairs.append(p2^)
    var built = json_build_object(pairs)
    var bb = built.as_bytes()
    if bb[0] != UInt8(123):
        raise Error("json_build_object doesn't start with {")
    if bb[len(built) - 1] != UInt8(125):
        raise Error("json_build_object doesn't end with }")
    print("  Built object: " + built)
    print("✅ JSON build_object")

    # ── Logger ───────────────────────────────────────────────────────────
    var log = Logger("test", 1)  # INFO level
    log.info("test_started", "key=value")
    log.debug("should_not_print")  # below INFO level — should be silent
    log.warning("test_warning")
    log.error("test_error", "code=500")

    # get_logger factory
    var log2 = get_logger("factory")
    log2.info("factory_created")

    # Debug logger should print debug
    var debug_log = Logger("debug_test", LOG_DEBUG)
    debug_log.debug("debug_visible")
    print("✅ Logger")

    # ── Env vars ─────────────────────────────────────────────────────────
    # PATH should always be set
    var path = env_get("PATH", "")
    if len(path) == 0:
        raise Error("env_get PATH should not be empty")

    if not env_is_set("PATH"):
        raise Error("env_is_set PATH should be True")

    if env_is_set("NONEXISTENT_VAR_12345"):
        raise Error("env_is_set NONEXISTENT_VAR_12345 should be False")

    var default_val = env_get("NONEXISTENT_VAR_12345", "default")
    if default_val != "default":
        raise Error("env_get default != 'default', got: " + default_val)

    var default_int = env_get_int("NONEXISTENT_VAR_12345", 42)
    if default_int != 42:
        raise Error("env_get_int default != 42, got: " + String(default_int))

    var default_bool = env_get_bool("NONEXISTENT_VAR_12345", False)
    if default_bool != False:
        raise Error("env_get_bool default should be False")

    var default_float = env_get_float("NONEXISTENT_VAR_12345", 3.14)
    if default_float != 3.14:
        raise Error("env_get_float default != 3.14")

    print("✅ Env vars")

    print("")
    print("✅ All Wave 8 tests passed")
