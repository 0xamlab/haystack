"""Device-header rebrand (X-Codna-* -> X-Algenta-*): the server reads the canonical
X-Algenta-* names but still ACCEPTS the legacy X-Codna-* names so deployed raw-HTTP
callers / older SDK builds keep working."""

from __future__ import annotations

from starlette.requests import Request

from apps.api_server.services.device_service import (
    HOSTED_DEVICE_ID_HEADER,
    LEGACY_HOSTED_DEVICE_ID_HEADER,
    _device_header,
)


def _req(headers: dict[str, str]) -> Request:
    return Request(
        {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    )


def test_canonical_headers_are_x_algenta() -> None:
    assert HOSTED_DEVICE_ID_HEADER == "X-Algenta-Device-Id"
    assert LEGACY_HOSTED_DEVICE_ID_HEADER == "X-Codna-Device-Id"


def test_device_header_prefers_algenta_then_falls_back_to_legacy_codna() -> None:
    # canonical present -> used
    assert (
        _device_header(_req({"X-Algenta-Device-Id": "dev-new"}), HOSTED_DEVICE_ID_HEADER, LEGACY_HOSTED_DEVICE_ID_HEADER)
        == "dev-new"
    )
    # only legacy present -> falls back (deployed old clients keep working)
    assert (
        _device_header(_req({"X-Codna-Device-Id": "dev-legacy"}), HOSTED_DEVICE_ID_HEADER, LEGACY_HOSTED_DEVICE_ID_HEADER)
        == "dev-legacy"
    )
    # both present -> canonical wins
    assert (
        _device_header(
            _req({"X-Algenta-Device-Id": "new", "X-Codna-Device-Id": "old"}),
            HOSTED_DEVICE_ID_HEADER,
            LEGACY_HOSTED_DEVICE_ID_HEADER,
        )
        == "new"
    )
    # neither -> default
    assert _device_header(_req({}), HOSTED_DEVICE_ID_HEADER, LEGACY_HOSTED_DEVICE_ID_HEADER, "fallback") == "fallback"
