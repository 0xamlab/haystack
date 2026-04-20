"""
test_wave6.mojo — Tests for Wave 6 libraries: TOML Parser, PathLib, Compression (RLE).

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave6.mojo
"""
from config.toml_parser import (
    TomlDoc, toml_parse, toml_get_string, toml_get_int,
    toml_get_float, toml_get_bool,
)
from filepath.pathlib import (
    path_join, path_basename, path_dirname, path_extension,
    path_stem, path_is_absolute, path_normalize, path_split,
)
from compression.rle import (
    rle_encode, rle_decode,
    rle_encode_string, rle_decode_string,
    compression_ratio,
)


def main() raises:
    print("━━━ Wave 6 test suite (TOML, PathLib, RLE Compression) ━━━")
    print("")

    # ── TOML ──────────────────────────────────────────────────────────────
    var toml_content = '[server]\nhost = "localhost"\nport = 8000\n\n[database]\nurl = "postgres://localhost/db"\npool_size = 10\nenabled = true'
    var root = toml_parse(toml_content)

    var host = toml_get_string(root, "server.host")
    if host != "localhost":
        raise Error("toml server.host != 'localhost', got '" + host + "'")

    var port = toml_get_int(root, "server.port", 0)
    if port != 8000:
        raise Error("toml server.port != 8000, got " + String(port))

    var db_url = toml_get_string(root, "database.url")
    if db_url != "postgres://localhost/db":
        raise Error("toml database.url != 'postgres://localhost/db', got '" + db_url + "'")

    var pool_size = toml_get_int(root, "database.pool_size", 0)
    if pool_size != 10:
        raise Error("toml database.pool_size != 10, got " + String(pool_size))

    var enabled = toml_get_bool(root, "database.enabled", False)
    if not enabled:
        raise Error("toml database.enabled != true")

    # Test defaults for missing keys
    var missing_int = toml_get_int(root, "missing.key", 42)
    if missing_int != 42:
        raise Error("toml missing key default != 42")

    var missing_float = toml_get_float(root, "missing.key", 3.14)
    if missing_float != 3.14:
        raise Error("toml missing key float default != 3.14")

    var missing_bool = toml_get_bool(root, "missing.key", True)
    if not missing_bool:
        raise Error("toml missing key bool default != True")

    # Test TOML with subsections
    var toml2 = '[app]\nname = "MyApp"\n\n[app.logging]\nlevel = "debug"\nverbose = false'
    var doc2 = toml_parse(toml2)
    var app_name = toml_get_string(doc2, "app.name")
    if app_name != "MyApp":
        raise Error("toml app.name != 'MyApp', got '" + app_name + "'")
    var log_level = toml_get_string(doc2, "app.logging.level")
    if log_level != "debug":
        raise Error("toml app.logging.level != 'debug', got '" + log_level + "'")
    var verbose = toml_get_bool(doc2, "app.logging.verbose", True)
    if verbose:
        raise Error("toml app.logging.verbose should be false")

    # Test comments
    var toml3 = '# Top comment\n[server]\n# Comment in section\nport = 9090  # inline comment\nhost = "0.0.0.0"'
    var doc3 = toml_parse(toml3)
    var p3 = toml_get_int(doc3, "server.port", 0)
    if p3 != 9090:
        raise Error("toml with comments: port != 9090, got " + String(p3))
    var h3 = toml_get_string(doc3, "server.host")
    if h3 != "0.0.0.0":
        raise Error("toml with comments: host != '0.0.0.0', got '" + h3 + "'")

    print("✅ TOML parser")

    # ── PathLib ───────────────────────────────────────────────────────────
    var bn = path_basename("/usr/local/bin/mojo")
    if bn != "mojo":
        raise Error("path_basename != 'mojo', got '" + bn + "'")

    var dn = path_dirname("/usr/local/bin/mojo")
    if dn != "/usr/local/bin":
        raise Error("path_dirname != '/usr/local/bin', got '" + dn + "'")

    var ext = path_extension("file.mojo")
    if ext != ".mojo":
        raise Error("path_extension != '.mojo', got '" + ext + "'")

    var stem = path_stem("file.mojo")
    if stem != "file":
        raise Error("path_stem != 'file', got '" + stem + "'")

    if not path_is_absolute("/usr/bin"):
        raise Error("path_is_absolute('/usr/bin') should be True")

    if path_is_absolute("relative/path"):
        raise Error("path_is_absolute('relative/path') should be False")

    var join_parts = List[String]()
    join_parts.append("usr")
    join_parts.append("local")
    join_parts.append("bin")
    var joined = path_join(join_parts)
    if joined != "usr/local/bin":
        raise Error("path_join != 'usr/local/bin', got '" + joined + "'")

    var norm = path_normalize("/usr/local/../bin")
    if norm != "/usr/bin":
        raise Error("path_normalize('/usr/local/../bin') != '/usr/bin', got '" + norm + "'")

    # Additional path tests
    var norm2 = path_normalize("/usr/./local/./bin")
    if norm2 != "/usr/local/bin":
        raise Error("path_normalize with ./ failed, got '" + norm2 + "'")

    var norm3 = path_normalize("/a/b/c/../../d")
    if norm3 != "/a/d":
        raise Error("path_normalize multi-.. failed, got '" + norm3 + "'")

    var dn2 = path_dirname("file.txt")
    if dn2 != ".":
        raise Error("path_dirname('file.txt') != '.', got '" + dn2 + "'")

    var ext2 = path_extension("Makefile")
    if ext2 != "":
        raise Error("path_extension('Makefile') should be empty, got '" + ext2 + "'")

    var split_result = path_split("/usr/local/bin")
    if len(split_result) != 4:
        raise Error("path_split('/usr/local/bin') should have 4 parts, got " + String(len(split_result)))
    if split_result[0] != "/":
        raise Error("path_split[0] != '/', got '" + split_result[0] + "'")
    if split_result[1] != "usr":
        raise Error("path_split[1] != 'usr', got '" + split_result[1] + "'")
    if split_result[3] != "bin":
        raise Error("path_split[3] != 'bin', got '" + split_result[3] + "'")

    print("✅ PathLib")

    # ── Compression ───────────────────────────────────────────────────────
    var enc1 = rle_encode_string("AAABBC")
    if enc1 != "3A2B1C":
        raise Error("rle_encode_string('AAABBC') != '3A2B1C', got '" + enc1 + "'")

    var dec1 = rle_decode_string("3A2B1C")
    if dec1 != "AAABBC":
        raise Error("rle_decode_string('3A2B1C') != 'AAABBC', got '" + dec1 + "'")

    # Empty string
    var enc_empty = rle_encode_string("")
    if enc_empty != "":
        raise Error("rle_encode_string('') should be empty, got '" + enc_empty + "'")

    # Single character
    var enc_single = rle_encode_string("A")
    if enc_single != "1A":
        raise Error("rle_encode_string('A') != '1A', got '" + enc_single + "'")

    # Round-trip
    var original = "AAAABBBBCCDDDDDD"
    var roundtrip = rle_decode_string(rle_encode_string(original))
    if roundtrip != original:
        raise Error("rle string roundtrip failed: '" + roundtrip + "' != '" + original + "'")

    # Byte-level round-trip
    var byte_data = List[UInt8]()
    byte_data.append(UInt8(65))  # A
    byte_data.append(UInt8(65))  # A
    byte_data.append(UInt8(65))  # A
    byte_data.append(UInt8(66))  # B
    byte_data.append(UInt8(66))  # B
    var compressed = rle_encode(byte_data)
    var decompressed = rle_decode(compressed)
    if len(decompressed) != 5:
        raise Error("rle byte roundtrip length != 5, got " + String(len(decompressed)))
    if decompressed[0] != UInt8(65) or decompressed[2] != UInt8(65):
        raise Error("rle byte roundtrip first values wrong")
    if decompressed[3] != UInt8(66) or decompressed[4] != UInt8(66):
        raise Error("rle byte roundtrip last values wrong")

    # Compression ratio
    var ratio = compression_ratio(16, 8)
    if ratio != 2.0:
        raise Error("compression_ratio(16, 8) != 2.0, got " + String(ratio))

    var ratio_zero = compression_ratio(100, 0)
    if ratio_zero != 0.0:
        raise Error("compression_ratio(100, 0) != 0.0")

    # All unique characters (worst case)
    var unique_str = "ABCDEF"
    var enc_unique = rle_encode_string(unique_str)
    if enc_unique != "1A1B1C1D1E1F":
        raise Error("rle unique chars: got '" + enc_unique + "'")
    var dec_unique = rle_decode_string(enc_unique)
    if dec_unique != unique_str:
        raise Error("rle unique chars roundtrip failed")

    print("✅ Compression (RLE)")

    print("")
    print("✅ All Wave 6 tests passed")
