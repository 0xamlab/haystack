"""
test_wave5.mojo — Tests for Wave 5 libraries: DateTime, MsgPack, YAML Parser.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave5.mojo
"""
from datetime import (
    Timestamp, now_epoch, epoch_to_iso, iso_to_epoch,
    format_duration_ms, days_between, add_days, day_of_week,
    is_leap_year, year, month, day, hour, minute, second,
)
from serialization.msgpack import (
    MsgPackIntResult, MsgPackFloatResult, MsgPackStringResult,
    msgpack_encode_int, msgpack_encode_float, msgpack_encode_string,
    msgpack_encode_bool, msgpack_encode_nil,
    msgpack_encode_array_header, msgpack_encode_map_header,
    msgpack_decode_int, msgpack_decode_float, msgpack_decode_string,
)
from config.yaml_parser import (
    YamlDoc, yaml_parse, yaml_get_string, yaml_get_int,
    yaml_get_float, yaml_get_bool,
)
from std.math import abs as fabs


def main() raises:
    print("━━━ Wave 5 test suite (DateTime, MsgPack, YAML) ━━━")
    print("")

    # ── DateTime ─────────────────────────────────────────────────────────
    # Epoch for 2026-01-01T00:00:00Z = 1767225600
    var epoch = 1767225600
    if year(epoch) != 2026:
        raise Error("year(epoch) != 2026, got " + String(year(epoch)))
    if month(epoch) != 1:
        raise Error("month(epoch) != 1, got " + String(month(epoch)))
    if day(epoch) != 1:
        raise Error("day(epoch) != 1, got " + String(day(epoch)))
    if hour(epoch) != 0:
        raise Error("hour(epoch) != 0, got " + String(hour(epoch)))
    if minute(epoch) != 0:
        raise Error("minute(epoch) != 0, got " + String(minute(epoch)))
    if second(epoch) != 0:
        raise Error("second(epoch) != 0, got " + String(second(epoch)))

    var iso = epoch_to_iso(epoch)
    if iso != "2026-01-01T00:00:00Z":
        raise Error("epoch_to_iso != '2026-01-01T00:00:00Z', got '" + iso + "'")

    var parsed = iso_to_epoch("2026-01-01T00:00:00Z")
    if parsed != epoch:
        raise Error("iso_to_epoch roundtrip failed: " + String(parsed) + " != " + String(epoch))

    # Another date: 2024-07-15T14:30:45Z
    var epoch2 = iso_to_epoch("2024-07-15T14:30:45Z")
    if year(epoch2) != 2024:
        raise Error("year(epoch2) != 2024, got " + String(year(epoch2)))
    if month(epoch2) != 7:
        raise Error("month(epoch2) != 7, got " + String(month(epoch2)))
    if day(epoch2) != 15:
        raise Error("day(epoch2) != 15, got " + String(day(epoch2)))
    if hour(epoch2) != 14:
        raise Error("hour(epoch2) != 14, got " + String(hour(epoch2)))
    if minute(epoch2) != 30:
        raise Error("minute(epoch2) != 30, got " + String(minute(epoch2)))
    if second(epoch2) != 45:
        raise Error("second(epoch2) != 45, got " + String(second(epoch2)))
    var iso2 = epoch_to_iso(epoch2)
    if iso2 != "2024-07-15T14:30:45Z":
        raise Error("epoch_to_iso(epoch2) = '" + iso2 + "'")

    # Leap year tests
    if not is_leap_year(2024):
        raise Error("2024 should be leap year")
    if is_leap_year(2026):
        raise Error("2026 should NOT be leap year")
    if not is_leap_year(2000):
        raise Error("2000 should be leap year")
    if is_leap_year(1900):
        raise Error("1900 should NOT be leap year")

    # days_between
    if days_between(epoch, epoch + 86400 * 30) != 30:
        raise Error("days_between 30 days failed")
    if days_between(epoch + 86400 * 30, epoch) != 30:
        raise Error("days_between (reverse) 30 days failed")

    # add_days
    var epoch_plus7 = add_days(epoch, 7)
    if day(epoch_plus7) != 8:
        raise Error("add_days(epoch, 7) day != 8, got " + String(day(epoch_plus7)))

    # day_of_week: 2026-01-01 is a Thursday (3)
    var dow = day_of_week(epoch)
    if dow != 3:
        raise Error("day_of_week(2026-01-01) != 3 (Thu), got " + String(dow))

    # 1970-01-01 is Thursday = 3
    if day_of_week(0) != 3:
        raise Error("day_of_week(0) != 3 (Thu), got " + String(day_of_week(0)))

    # format_duration_ms
    var dur1 = format_duration_ms(150)
    if dur1 != "150ms":
        raise Error("format_duration_ms(150) != '150ms', got '" + dur1 + "'")
    var dur2 = format_duration_ms(3750)
    if dur2 != "3.75s":
        raise Error("format_duration_ms(3750) != '3.75s', got '" + dur2 + "'")
    var dur3 = format_duration_ms(150000)
    if dur3 != "2m 30s":
        raise Error("format_duration_ms(150000) != '2m 30s', got '" + dur3 + "'")
    var dur4 = format_duration_ms(3661000)
    if dur4 != "1h 1m 1s":
        raise Error("format_duration_ms(3661000) != '1h 1m 1s', got '" + dur4 + "'")

    # now_epoch sanity (should be > 2020-01-01)
    var current = now_epoch()
    if current < 1577836800:
        raise Error("now_epoch() < 2020-01-01 epoch, got " + String(current))

    print("✅ DateTime")

    # ── MsgPack ──────────────────────────────────────────────────────────
    # Encode/decode positive fixint
    var enc_42 = msgpack_encode_int(42)
    var dec_42 = msgpack_decode_int(enc_42, 0)
    if dec_42.value != 42:
        raise Error("msgpack int 42 roundtrip: got " + String(dec_42.value))
    if dec_42.consumed != 1:
        raise Error("msgpack int 42 consumed != 1")

    # Encode/decode zero
    var enc_0 = msgpack_encode_int(0)
    var dec_0 = msgpack_decode_int(enc_0, 0)
    if dec_0.value != 0:
        raise Error("msgpack int 0 roundtrip: got " + String(dec_0.value))

    # Encode/decode negative fixint
    var enc_neg = msgpack_encode_int(-5)
    var dec_neg = msgpack_decode_int(enc_neg, 0)
    if dec_neg.value != -5:
        raise Error("msgpack int -5 roundtrip: got " + String(dec_neg.value))

    # Encode/decode uint8 (200)
    var enc_200 = msgpack_encode_int(200)
    var dec_200 = msgpack_decode_int(enc_200, 0)
    if dec_200.value != 200:
        raise Error("msgpack int 200 roundtrip: got " + String(dec_200.value))

    # Encode/decode uint16 (1000)
    var enc_1k = msgpack_encode_int(1000)
    var dec_1k = msgpack_decode_int(enc_1k, 0)
    if dec_1k.value != 1000:
        raise Error("msgpack int 1000 roundtrip: got " + String(dec_1k.value))

    # Encode/decode int8 (-100)
    var enc_n100 = msgpack_encode_int(-100)
    var dec_n100 = msgpack_decode_int(enc_n100, 0)
    if dec_n100.value != -100:
        raise Error("msgpack int -100 roundtrip: got " + String(dec_n100.value))

    # Encode/decode float64
    var enc_f = msgpack_encode_float(3.14)
    var dec_f = msgpack_decode_float(enc_f, 0)
    if fabs(dec_f.value - 3.14) > 0.001:
        raise Error("msgpack float 3.14 roundtrip: got " + String(dec_f.value))
    if dec_f.consumed != 9:
        raise Error("msgpack float consumed != 9")

    # Encode/decode float64 negative
    var enc_fn = msgpack_encode_float(-273.15)
    var dec_fn = msgpack_decode_float(enc_fn, 0)
    if fabs(dec_fn.value - (-273.15)) > 0.001:
        raise Error("msgpack float -273.15 roundtrip: got " + String(dec_fn.value))

    # Encode/decode string
    var enc_s = msgpack_encode_string("hello")
    var dec_s = msgpack_decode_string(enc_s, 0)
    if dec_s.value != "hello":
        raise Error("msgpack string 'hello' roundtrip: got '" + dec_s.value + "'")
    if dec_s.consumed != 6:  # 1 byte header + 5 bytes string
        raise Error("msgpack string consumed != 6, got " + String(dec_s.consumed))

    # Encode/decode empty string
    var enc_es = msgpack_encode_string("")
    var dec_es = msgpack_decode_string(enc_es, 0)
    if dec_es.value != "":
        raise Error("msgpack empty string roundtrip failed")

    # Encode bool
    var enc_t = msgpack_encode_bool(True)
    if enc_t[0] != 0xc3:
        raise Error("msgpack true != 0xc3")
    var enc_ff = msgpack_encode_bool(False)
    if enc_ff[0] != 0xc2:
        raise Error("msgpack false != 0xc2")

    # Encode nil
    var enc_nil = msgpack_encode_nil()
    if enc_nil[0] != 0xc0:
        raise Error("msgpack nil != 0xc0")

    # Array header
    var enc_arr = msgpack_encode_array_header(3)
    if enc_arr[0] != UInt8(0x93):
        raise Error("msgpack fixarray(3) != 0x93")

    # Map header
    var enc_map = msgpack_encode_map_header(2)
    if enc_map[0] != UInt8(0x82):
        raise Error("msgpack fixmap(2) != 0x82")

    print("✅ MsgPack")

    # ── YAML ─────────────────────────────────────────────────────────────
    var yaml_content = "name: Algenta\nversion: 1.0\nserver:\n  host: localhost\n  port: 8000\nenabled: true\nitems:\n  - alpha\n  - beta"
    var root = yaml_parse(yaml_content)

    var name_val = yaml_get_string(root, "name")
    if name_val != "Algenta":
        raise Error("yaml name != 'Algenta', got '" + name_val + "'")

    var ver = yaml_get_float(root, "version", 0.0)
    if fabs(ver - 1.0) > 0.01:
        raise Error("yaml version != 1.0, got " + String(ver))

    var host = yaml_get_string(root, "server.host")
    if host != "localhost":
        raise Error("yaml server.host != 'localhost', got '" + host + "'")

    var port = yaml_get_int(root, "server.port", 0)
    if port != 8000:
        raise Error("yaml server.port != 8000, got " + String(port))

    var enabled = yaml_get_bool(root, "enabled", False)
    if not enabled:
        raise Error("yaml enabled != true")

    # Test non-existent key defaults
    var missing_int = yaml_get_int(root, "missing.key", 42)
    if missing_int != 42:
        raise Error("yaml missing key default != 42")

    var missing_bool = yaml_get_bool(root, "missing", True)
    if not missing_bool:
        raise Error("yaml missing bool default != True")

    # Test simple YAML
    var simple = "key1: value1\nkey2: 123\nkey3: false"
    var sdoc = yaml_parse(simple)
    if yaml_get_string(sdoc, "key1") != "value1":
        raise Error("simple yaml key1 failed")
    if yaml_get_int(sdoc, "key2", 0) != 123:
        raise Error("simple yaml key2 failed")
    if yaml_get_bool(sdoc, "key3", True) != False:
        raise Error("simple yaml key3 failed")

    print("✅ YAML parser")

    print("")
    print("✅ All Wave 5 tests passed")
