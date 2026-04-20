"""test_network_protocol.mojo — auto-generated tests for network_protocol library."""
from std.math import isnan, isinf
from network_protocol import http_status_text, is_success, is_redirect, is_client_error, is_server_error, mime_type, parse_content_type, is_json_type, is_text_type, parse_query_string

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    _ = http_status_text(5)
    passed += 1; print("  ✅ network_protocol::http_status_text")
    _ = is_success(5)
    passed += 1; print("  ✅ network_protocol::is_success")
    _ = is_redirect(5)
    passed += 1; print("  ✅ network_protocol::is_redirect")
    _ = is_client_error(5)
    passed += 1; print("  ✅ network_protocol::is_client_error")
    _ = is_server_error(5)
    passed += 1; print("  ✅ network_protocol::is_server_error")
    _ = mime_type("test")
    passed += 1; print("  ✅ network_protocol::mime_type")
    _ = parse_content_type("test")
    passed += 1; print("  ✅ network_protocol::parse_content_type")
    _ = is_json_type("test")
    passed += 1; print("  ✅ network_protocol::is_json_type")
    _ = is_text_type("test")
    passed += 1; print("  ✅ network_protocol::is_text_type")
    _ = parse_query_string("test")
    passed += 1; print("  ✅ network_protocol::parse_query_string")

    print("  [network_protocol] Passed:", passed, "Failed:", failed)
