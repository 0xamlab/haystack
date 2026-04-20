"""
test_wave7.mojo — Tests for Wave 7 libraries: Collections, String Utils, URL Parser.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave7.mojo
"""
from structs.containers import (
    MinHeap, RingBuffer, SortedList, counter, unique,
)
from text.string_utils import (
    str_split, str_join, str_replace,
    str_startswith, str_endswith, str_contains,
    str_repeat, str_pad_left, str_pad_right,
    str_upper, str_lower, str_trim,
    str_count, str_reverse, str_truncate, str_center,
)
from net.url import (
    URL, url_parse, url_to_string,
    url_encode, url_decode,
    query_parse, query_get, query_build,
)


fn _abs(v: Float64) -> Float64:
    if v < 0.0:
        return -v
    return v


def main() raises:
    print("━━━ Wave 7 test suite (Collections, String Utils, URL Parser) ━━━")
    print("")

    # ── Collections: MinHeap ─────────────────────────────────────────────
    var heap = MinHeap()
    heap.push(5.0)
    heap.push(2.0)
    heap.push(8.0)
    heap.push(1.0)
    if heap.peek() != 1.0:
        raise Error("MinHeap peek != 1.0, got " + String(heap.peek()))
    var p1 = heap.pop()
    if p1 != 1.0:
        raise Error("MinHeap pop #1 != 1.0, got " + String(p1))
    var p2 = heap.pop()
    if p2 != 2.0:
        raise Error("MinHeap pop #2 != 2.0, got " + String(p2))
    if heap.size() != 2:
        raise Error("MinHeap size != 2, got " + String(heap.size()))
    print("✅ MinHeap")

    # ── Collections: RingBuffer ──────────────────────────────────────────
    var rb = RingBuffer(3)
    rb.push(1.0)
    rb.push(2.0)
    rb.push(3.0)
    if not rb.is_full():
        raise Error("RingBuffer should be full")
    if _abs(rb.mean() - 2.0) >= 0.001:
        raise Error("RingBuffer mean != 2.0, got " + String(rb.mean()))
    rb.push(4.0)  # overwrites 1.0
    if _abs(rb.mean() - 3.0) >= 0.001:
        raise Error("RingBuffer mean after push != 3.0, got " + String(rb.mean()))
    # Check get (oldest first): 2.0, 3.0, 4.0
    if rb.get(0) != 2.0:
        raise Error("RingBuffer get(0) != 2.0, got " + String(rb.get(0)))
    if rb.get(2) != 4.0:
        raise Error("RingBuffer get(2) != 4.0, got " + String(rb.get(2)))
    print("✅ RingBuffer")

    # ── Collections: SortedList ──────────────────────────────────────────
    var sl = SortedList()
    sl.insert(5.0)
    sl.insert(1.0)
    sl.insert(3.0)
    sl.insert(2.0)
    sl.insert(4.0)
    if sl.get(0) != 1.0:
        raise Error("SortedList get(0) != 1.0, got " + String(sl.get(0)))
    if sl.get(4) != 5.0:
        raise Error("SortedList get(4) != 5.0, got " + String(sl.get(4)))
    if sl.median() != 3.0:
        raise Error("SortedList median != 3.0, got " + String(sl.median()))
    sl.remove(2)  # remove 3.0
    if sl.size() != 4:
        raise Error("SortedList size after remove != 4, got " + String(sl.size()))
    # Median of [1,2,4,5] = 3.0
    if _abs(sl.median() - 3.0) >= 0.001:
        raise Error("SortedList median after remove != 3.0, got " + String(sl.median()))
    print("✅ SortedList")

    # ── Collections: counter ─────────────────────────────────────────────
    var data = List[Float64]()
    data.append(0.0)
    data.append(0.5)
    data.append(1.0)
    data.append(1.5)
    data.append(2.0)
    var bins = counter(data, 2)
    # bin 0: [0, 1) = {0.0, 0.5} = 2
    # bin 1: [1, 2] = {1.0, 1.5, 2.0} = 3
    if len(bins) != 2:
        raise Error("counter bins count != 2")
    if bins[0] + bins[1] != 5:
        raise Error("counter total != 5")
    print("✅ counter")

    # ── Collections: unique ──────────────────────────────────────────────
    var dup_data = List[Float64]()
    dup_data.append(3.0)
    dup_data.append(1.0)
    dup_data.append(2.0)
    dup_data.append(1.0)
    dup_data.append(3.0)
    var uniq = unique(dup_data)
    if len(uniq) != 3:
        raise Error("unique count != 3, got " + String(len(uniq)))
    if uniq[0] != 1.0 or uniq[1] != 2.0 or uniq[2] != 3.0:
        raise Error("unique order wrong")
    print("✅ unique")

    # ── String Utils ─────────────────────────────────────────────────────
    var parts = str_split("a,b,c", ",")
    if len(parts) != 3:
        raise Error("str_split len != 3, got " + String(len(parts)))
    if parts[0] != "a":
        raise Error("str_split parts[0] != 'a', got '" + parts[0] + "'")
    if parts[1] != "b":
        raise Error("str_split parts[1] != 'b'")
    if parts[2] != "c":
        raise Error("str_split parts[2] != 'c'")

    var joined = str_join(parts, "-")
    if joined != "a-b-c":
        raise Error("str_join != 'a-b-c', got '" + joined + "'")

    var replaced = str_replace("hello world", "world", "mojo")
    if replaced != "hello mojo":
        raise Error("str_replace != 'hello mojo', got '" + replaced + "'")

    if not str_startswith("hello", "hel"):
        raise Error("str_startswith failed")
    if str_startswith("hello", "xyz"):
        raise Error("str_startswith false positive")

    if not str_endswith("hello", "llo"):
        raise Error("str_endswith failed")
    if str_endswith("hello", "xyz"):
        raise Error("str_endswith false positive")

    if not str_contains("hello world", "world"):
        raise Error("str_contains failed")
    if str_contains("hello world", "xyz"):
        raise Error("str_contains false positive")

    var upper = str_upper("hello")
    if upper != "HELLO":
        raise Error("str_upper != 'HELLO', got '" + upper + "'")

    var lower = str_lower("HELLO")
    if lower != "hello":
        raise Error("str_lower != 'hello', got '" + lower + "'")

    var trimmed = str_trim("  hello  ")
    if trimmed != "hello":
        raise Error("str_trim != 'hello', got '" + trimmed + "'")

    var cnt = str_count("abcabc", "abc")
    if cnt != 2:
        raise Error("str_count != 2, got " + String(cnt))

    var rev = str_reverse("hello")
    if rev != "olleh":
        raise Error("str_reverse != 'olleh', got '" + rev + "'")

    var padded = str_pad_left("42", 5, "0")
    if padded != "00042":
        raise Error("str_pad_left != '00042', got '" + padded + "'")

    var pad_r = str_pad_right("42", 5, " ")
    if pad_r != "42   ":
        raise Error("str_pad_right != '42   ', got '" + pad_r + "'")

    var repeated = str_repeat("ab", 3)
    if repeated != "ababab":
        raise Error("str_repeat != 'ababab', got '" + repeated + "'")

    var truncated = str_truncate("hello world", 8, "...")
    if truncated != "hello...":
        raise Error("str_truncate != 'hello...', got '" + truncated + "'")

    var centered = str_center("hi", 6, "-")
    if centered != "--hi--":
        raise Error("str_center != '--hi--', got '" + centered + "'")

    print("✅ String utils")

    # ── URL Parser ───────────────────────────────────────────────────────
    var u = url_parse("https://api.algenta.ai:8443/v1/simulate?mode=auto&runs=10000#results")
    if u.scheme != "https":
        raise Error("url scheme != 'https', got '" + u.scheme + "'")
    if u.host != "api.algenta.ai":
        raise Error("url host != 'api.algenta.ai', got '" + u.host + "'")
    if u.port != 8443:
        raise Error("url port != 8443, got " + String(u.port))
    if u.path != "/v1/simulate":
        raise Error("url path != '/v1/simulate', got '" + u.path + "'")
    if u.fragment != "results":
        raise Error("url fragment != 'results', got '" + u.fragment + "'")

    var mode_val = query_get(u.query, "mode")
    if mode_val != "auto":
        raise Error("query_get mode != 'auto', got '" + mode_val + "'")
    var runs_val = query_get(u.query, "runs")
    if runs_val != "10000":
        raise Error("query_get runs != '10000', got '" + runs_val + "'")

    # URL encode/decode
    var encoded = url_encode("hello world")
    if encoded != "hello%20world":
        raise Error("url_encode != 'hello%20world', got '" + encoded + "'")
    var decoded = url_decode("hello%20world")
    if decoded != "hello world":
        raise Error("url_decode != 'hello world', got '" + decoded + "'")

    # Round-trip
    var rt = url_to_string(url_parse("https://example.com/path"))
    if rt != "https://example.com/path":
        raise Error("url round-trip failed, got '" + rt + "'")

    # URL without port
    var u2 = url_parse("http://example.com/test")
    if u2.scheme != "http":
        raise Error("u2 scheme wrong")
    if u2.host != "example.com":
        raise Error("u2 host wrong, got '" + u2.host + "'")
    if u2.port != 0:
        raise Error("u2 port should be 0")
    if u2.path != "/test":
        raise Error("u2 path wrong, got '" + u2.path + "'")

    # Query parse/build
    var pairs = query_parse("key1=val1&key2=val2")
    if len(pairs) != 2:
        raise Error("query_parse len != 2")
    if pairs[0][0] != "key1" or pairs[0][1] != "val1":
        raise Error("query_parse pair 0 wrong")
    if pairs[1][0] != "key2" or pairs[1][1] != "val2":
        raise Error("query_parse pair 1 wrong")

    var built = query_build(pairs)
    if built != "key1=val1&key2=val2":
        raise Error("query_build != 'key1=val1&key2=val2', got '" + built + "'")

    # URL encode special chars
    var enc2 = url_encode("foo@bar.com")
    if not str_contains(enc2, "%40"):
        raise Error("url_encode @ should be %40, got '" + enc2 + "'")

    # Decode +
    var dec_plus = url_decode("hello+world")
    if dec_plus != "hello world":
        raise Error("url_decode + != 'hello world', got '" + dec_plus + "'")

    print("✅ URL parser")

    print("")
    print("✅ All Wave 7 tests passed")
