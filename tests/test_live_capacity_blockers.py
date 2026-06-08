from __future__ import annotations

from tests.integration.live_capacity_blockers import (
    classify_simulation_capacity_blocker,
    parse_cli_error_payload,
)


def test_classify_simulation_capacity_blocker_detects_quota_payload() -> None:
    payload = {
        "error": {
            "code": "quota_exceeded",
            "message": "Monthly simulation quota exhausted (100000/100000).",
        }
    }

    assert (
        classify_simulation_capacity_blocker(status=429, payload=payload)
        == "Monthly simulation quota exhausted (100000/100000)."
    )


def test_classify_simulation_capacity_blocker_detects_rate_limit_payload() -> None:
    payload = {
        "error": {
            "code": "rate_limit_exceeded",
            "message": "Too many requests per minute.",
        }
    }

    assert (
        classify_simulation_capacity_blocker(status=429, payload=payload)
        == "Too many requests per minute."
    )


def test_classify_simulation_capacity_blocker_detects_cli_text_only() -> None:
    stderr = """
    Error 429: {
      "error": {
        "code": "quota_exceeded",
        "message": "Monthly simulation quota exhausted (100000/100000)."
      }
    }
    """

    assert (
        classify_simulation_capacity_blocker(text=stderr)
        == "simulation quota exhausted"
    )


def test_classify_simulation_capacity_blocker_ignores_unrelated_errors() -> None:
    payload = {"error": {"code": "invalid_api_key", "message": "Nope"}}

    assert classify_simulation_capacity_blocker(status=401, payload=payload) is None


def test_parse_cli_error_payload_extracts_embedded_json() -> None:
    stderr = """
    ❌ Error 429: {
      "error": {
        "code": "quota_exceeded",
        "message": "Monthly simulation quota exhausted (100000/100000)."
      }
    }
    """

    assert parse_cli_error_payload(stderr) == {
        "error": {
            "code": "quota_exceeded",
            "message": "Monthly simulation quota exhausted (100000/100000).",
        }
    }


def test_parse_cli_error_payload_extracts_runtime_error_embedded_json() -> None:
    stderr = (
        "API error 429: "
        '{"error":{"code":"quota_exceeded","message":"Monthly simulation quota exhausted."}}'
    )

    assert parse_cli_error_payload(stderr) == {
        "error": {
            "code": "quota_exceeded",
            "message": "Monthly simulation quota exhausted.",
        }
    }


def test_parse_cli_error_payload_returns_none_without_json() -> None:
    assert parse_cli_error_payload("plain text only") is None
