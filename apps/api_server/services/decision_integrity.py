"""
Decision integrity service — SHA-256 hashing of simulation outputs.

The canonical form intentionally excludes volatile or self-referential fields
such as `result_hash`, timestamps, execution timing, and transient metadata.
"""
import hashlib
import json
from typing import Any

HASH_ALGORITHM = "sha256"
HASH_VERSION = "1"


def canonical_envelope_bytes(envelope_data: dict[str, Any]) -> bytes:
    """
    Produce a deterministic canonical JSON encoding of the decision envelope
    for hashing. Creates a complete chain of custody linking input + output.
    """
    canonical: dict[str, Any] = {
        "hash_version": HASH_VERSION,
        "run_id": str(envelope_data.get("run_id", "")),
        "recommended_action": envelope_data.get("recommended_action", ""),
        "confidence": envelope_data.get("confidence", 0.0),
        "rationale": envelope_data.get("rationale", ""),
        "metrics": {
            "expected_value": envelope_data.get("metrics", {}).get("expected_value", 0.0),
            "median": envelope_data.get("metrics", {}).get("median", 0.0),
            "std_deviation": envelope_data.get("metrics", {}).get("std_deviation", 0.0),
            "variance": envelope_data.get("metrics", {}).get("variance", 0.0),
            "probability_of_loss": envelope_data.get("metrics", {}).get("probability_of_loss", 0.0),
            "var_95": envelope_data.get("metrics", {}).get("var_95"),
        },
        "percentiles": {
            "p5":  envelope_data.get("percentiles", {}).get("p5", 0.0),
            "p25": envelope_data.get("percentiles", {}).get("p25", 0.0),
            "p50": envelope_data.get("percentiles", {}).get("p50", 0.0),
            "p75": envelope_data.get("percentiles", {}).get("p75", 0.0),
            "p95": envelope_data.get("percentiles", {}).get("p95", 0.0),
        },
        "scenarios_run": envelope_data.get("scenarios_run", 0),
        "engine_version": envelope_data.get("engine_version", ""),
    }
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def hash_decision_envelope(envelope_data: dict[str, Any]) -> str:
    """
    Compute SHA-256 hash of a decision envelope.

    Returns:
        Hex string of SHA-256 digest (64 chars), e.g. "a3f4b2c1..."
    """
    canonical = canonical_envelope_bytes(envelope_data)
    return hashlib.sha256(canonical).hexdigest()


def verify_decision_hash(envelope_data: dict[str, Any], stored_hash: str) -> bool:
    """
    Verify that a decision result matches its stored hash.

    Returns:
        True if the result matches the hash (not tampered with)
        False if the hash doesn't match (tampered or corrupted)
    """
    computed = hash_decision_envelope(envelope_data)
    return computed == stored_hash


def format_result_hash_header(result_hash: str) -> str:
    """Format result hash for X-Decision-Hash response header."""
    return f"{HASH_ALGORITHM}={result_hash};v={HASH_VERSION}"


def parse_result_hash_header(header_value: str) -> tuple[str, str] | None:
    """
    Parse X-Decision-Hash header value.
    Header format: ``sha256=<64-char-hex>;v=<version>``
    """
    try:
        for part in header_value.split(";"):
            part = part.strip()
            if part.startswith("sha256="):
                hex_hash = part[7:]
                if hex_hash:
                    return "sha256", hex_hash
        return None
    except Exception:
        return None
