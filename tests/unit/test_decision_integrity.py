"""Unit tests for SHA-256 decision integrity service."""
import hashlib
import json
import uuid

from apps.api_server.services.decision_integrity import (
    HASH_VERSION,
    canonical_envelope_bytes,
    format_result_hash_header,
    hash_decision_envelope,
    parse_result_hash_header,
    verify_decision_hash,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_envelope(overrides: dict | None = None) -> dict:
    """Return a minimal valid DecisionEnvelope dict for testing."""
    run_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    base = {
        "run_id": run_id,
        "status": "completed",
        "engine_version": "0.1.0",
        "recommended_action": "proceed",
        "confidence": 0.82,
        "rationale": "Expected value is positive in 82% of scenarios.",
        "metrics": {
            "expected_value": 145000.0,
            "median": 140000.0,
            "std_deviation": 25000.0,
            "variance": 625000000.0,
            "probability_of_loss": 0.18,
            "var_95": -30000.0,
            "cvar_95": None,
        },
        "percentiles": {
            "p5": 90000.0,
            "p25": 120000.0,
            "p50": 140000.0,
            "p75": 165000.0,
            "p95": 200000.0,
        },
        "scenarios_run": 10000,
        "execution_ms": 42,
        "metadata": {"mode": "auto", "seed": None, "billing_units": 1, "engine_version": "0.1.0"},
        "result_hash": None,
        "created_at": None,
        "score": None,
        "score_breakdown": None,
        "scenario_ranking": None,
        "sensitivity_ranking": None,
    }
    if overrides:
        base.update(overrides)
    return base


# ─── canonical_envelope_bytes ──────────────────────────────────────────────────

class TestCanonicalEnvelopeBytes:
    def test_returns_bytes(self):
        envelope = _make_envelope()
        result = canonical_envelope_bytes(envelope)
        assert isinstance(result, bytes)

    def test_is_valid_json(self):
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope)
        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)

    def test_contains_hash_version(self):
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope)
        parsed = json.loads(raw.decode("utf-8"))
        assert parsed["hash_version"] == HASH_VERSION

    def test_contains_expected_keys(self):
        envelope = _make_envelope()
        parsed = json.loads(canonical_envelope_bytes(envelope).decode())
        expected_keys = {
            "hash_version", "run_id", "recommended_action", "confidence",
            "rationale", "metrics", "percentiles", "scenarios_run", "engine_version",
        }
        assert expected_keys == set(parsed.keys())

    def test_excludes_volatile_metadata(self):
        """Timestamps, billing metadata, and score must NOT be in canonical form."""
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope).decode()
        # These fields should NOT appear in canonical representation
        assert "execution_ms" not in raw
        assert "created_at" not in raw
        assert "score" not in raw
        assert "status" not in raw

    def test_run_id_serialized_as_string(self):
        run_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        envelope = _make_envelope({"run_id": run_id})
        parsed = json.loads(canonical_envelope_bytes(envelope).decode())
        assert parsed["run_id"] == str(run_id)

    def test_deterministic_for_same_input(self):
        envelope = _make_envelope()
        b1 = canonical_envelope_bytes(envelope)
        b2 = canonical_envelope_bytes(envelope)
        assert b1 == b2

    def test_compact_json_no_whitespace(self):
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope).decode()
        assert "  " not in raw  # no double spaces (no pretty-printing)
        assert ": " not in raw  # no space after colon (compact)

    def test_keys_sorted(self):
        """Canonical JSON must have sorted keys for determinism."""
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope).decode()
        parsed_dict = json.loads(raw)
        keys = list(parsed_dict.keys())
        assert keys == sorted(keys)

    def test_metrics_keys_sorted(self):
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope).decode()
        parsed_dict = json.loads(raw)
        metrics_keys = list(parsed_dict["metrics"].keys())
        assert metrics_keys == sorted(metrics_keys)

    def test_missing_fields_use_defaults(self):
        """Should not raise for missing envelope fields — use safe defaults."""
        result = canonical_envelope_bytes({})
        parsed = json.loads(result.decode())
        assert parsed["run_id"] == ""
        assert parsed["recommended_action"] == ""
        assert parsed["confidence"] == 0.0
        assert parsed["scenarios_run"] == 0


# ─── hash_decision_envelope ────────────────────────────────────────────────────

class TestHashDecisionEnvelope:
    def test_returns_64_char_hex_string(self):
        envelope = _make_envelope()
        result = hash_decision_envelope(envelope)
        assert isinstance(result, str)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_deterministic(self):
        envelope = _make_envelope()
        h1 = hash_decision_envelope(envelope)
        h2 = hash_decision_envelope(envelope)
        assert h1 == h2

    def test_different_run_id_different_hash(self):
        e1 = _make_envelope({"run_id": uuid.UUID("11111111-1111-1111-1111-111111111111")})
        e2 = _make_envelope({"run_id": uuid.UUID("22222222-2222-2222-2222-222222222222")})
        assert hash_decision_envelope(e1) != hash_decision_envelope(e2)

    def test_different_action_different_hash(self):
        e1 = _make_envelope({"recommended_action": "proceed"})
        e2 = _make_envelope({"recommended_action": "reject"})
        assert hash_decision_envelope(e1) != hash_decision_envelope(e2)

    def test_different_confidence_different_hash(self):
        e1 = _make_envelope({"confidence": 0.82})
        e2 = _make_envelope({"confidence": 0.55})
        assert hash_decision_envelope(e1) != hash_decision_envelope(e2)

    def test_different_metrics_different_hash(self):
        e1 = _make_envelope()
        e2 = _make_envelope()
        e2["metrics"]["expected_value"] = 999.0
        assert hash_decision_envelope(e1) != hash_decision_envelope(e2)

    def test_different_percentiles_different_hash(self):
        e1 = _make_envelope()
        e2 = _make_envelope()
        e2["percentiles"]["p95"] = 999999.0
        assert hash_decision_envelope(e1) != hash_decision_envelope(e2)

    def test_volatile_fields_do_not_affect_hash(self):
        """Changing execution_ms, created_at, score does NOT change the hash."""
        e1 = _make_envelope({"execution_ms": 10, "score": None})
        e2 = _make_envelope({"execution_ms": 9999, "score": 0.99})
        assert hash_decision_envelope(e1) == hash_decision_envelope(e2)

    def test_invalid_result_hash_field_does_not_affect_hash(self):
        """Invalid embedded hashes are ignored and canonical hashing still matches."""
        e1 = _make_envelope({"result_hash": None})
        e2 = _make_envelope({"result_hash": "not_a_valid_hash"})
        assert hash_decision_envelope(e1) == hash_decision_envelope(e2)

    def test_valid_result_hash_field_is_used_when_present(self):
        """A valid precomputed Mojo hash should be returned directly."""
        precomputed_hash = "deadbeef" * 8
        envelope = _make_envelope({"result_hash": precomputed_hash})
        assert hash_decision_envelope(envelope) == precomputed_hash

    def test_correct_sha256_algorithm(self):
        """Verify hash matches manual SHA-256 computation."""
        envelope = _make_envelope()
        raw = canonical_envelope_bytes(envelope)
        expected = hashlib.sha256(raw).hexdigest()
        assert hash_decision_envelope(envelope) == expected

    def test_empty_envelope_produces_hash(self):
        """Empty envelope should not raise, just hash defaults."""
        result = hash_decision_envelope({})
        assert len(result) == 64


# ─── verify_decision_hash ──────────────────────────────────────────────────────

class TestVerifyDecisionHash:
    def test_verify_correct_hash_returns_true(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        assert verify_decision_hash(envelope, stored_hash) is True

    def test_verify_wrong_hash_returns_false(self):
        envelope = _make_envelope()
        wrong_hash = "a" * 64
        assert verify_decision_hash(envelope, wrong_hash) is False

    def test_verify_tampered_action_returns_false(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        # Tamper with the action
        envelope["recommended_action"] = "reject"
        assert verify_decision_hash(envelope, stored_hash) is False

    def test_verify_tampered_confidence_returns_false(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        envelope["confidence"] = 0.01
        assert verify_decision_hash(envelope, stored_hash) is False

    def test_verify_tampered_expected_value_returns_false(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        envelope["metrics"]["expected_value"] = -999999.0
        assert verify_decision_hash(envelope, stored_hash) is False

    def test_verify_tampered_percentile_returns_false(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        envelope["percentiles"]["p95"] = 0.0
        assert verify_decision_hash(envelope, stored_hash) is False

    def test_verify_empty_hash_returns_false(self):
        envelope = _make_envelope()
        assert verify_decision_hash(envelope, "") is False

    def test_verify_changed_run_id_returns_false(self):
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        envelope["run_id"] = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        assert verify_decision_hash(envelope, stored_hash) is False

    def test_volatile_fields_do_not_break_verification(self):
        """Verify that changing execution_ms or score does NOT break hash verification."""
        envelope = _make_envelope({"execution_ms": 42})
        stored_hash = hash_decision_envelope(envelope)
        # Simulate re-fetching envelope with different execution_ms
        envelope["execution_ms"] = 1234
        envelope["score"] = 0.88
        # Should still verify because volatile fields are excluded from hash
        assert verify_decision_hash(envelope, stored_hash) is True

    def test_verify_ignores_embedded_result_hash(self):
        """Verification must recompute the canonical hash, not trust embedded result_hash."""
        envelope = _make_envelope()
        stored_hash = hash_decision_envelope(envelope)
        tampered = {**envelope, "confidence": 0.99, "result_hash": stored_hash}
        assert verify_decision_hash(tampered, stored_hash) is False


# ─── format_result_hash_header ────────────────────────────────────────────────

class TestFormatResultHashHeader:
    def test_format_contains_algorithm(self):
        h = "a" * 64
        result = format_result_hash_header(h)
        assert "sha256=" in result

    def test_format_contains_hash(self):
        h = "b" * 64
        result = format_result_hash_header(h)
        assert h in result

    def test_format_contains_version(self):
        h = "c" * 64
        result = format_result_hash_header(h)
        assert f"v={HASH_VERSION}" in result

    def test_format_structure(self):
        h = "d" * 64
        result = format_result_hash_header(h)
        assert result == f"sha256={h};v={HASH_VERSION}"


# ─── parse_result_hash_header ─────────────────────────────────────────────────

class TestParseResultHashHeader:
    def test_parse_valid_header(self):
        h = "e" * 64
        header = format_result_hash_header(h)
        result = parse_result_hash_header(header)
        assert result is not None
        algo, hex_hash = result
        assert algo == "sha256"
        assert hex_hash == h

    def test_parse_malformed_header_returns_none(self):
        result = parse_result_hash_header("not-a-valid-header")
        assert result is None

    def test_parse_empty_string_returns_none(self):
        result = parse_result_hash_header("")
        assert result is None


# ─── Round-trip integration ───────────────────────────────────────────────────

class TestRoundTrip:
    def test_hash_then_verify_round_trip(self):
        """Full round-trip: hash at write time, verify at read time."""
        envelope = _make_envelope()
        # Step 1: Compute and store hash
        stored_hash = hash_decision_envelope(envelope)
        assert len(stored_hash) == 64
        # Step 2: Later, load from DB (same data) and verify
        assert verify_decision_hash(envelope, stored_hash) is True

    def test_header_round_trip(self):
        """Format header → parse header → get back original hash."""
        original_hash = hash_decision_envelope(_make_envelope())
        header_value = format_result_hash_header(original_hash)
        parsed = parse_result_hash_header(header_value)
        assert parsed is not None
        _, parsed_hash = parsed
        assert parsed_hash == original_hash

    def test_two_different_simulations_have_different_hashes(self):
        """Different run_ids → different hashes (tamper evident per run)."""
        e1 = _make_envelope({"run_id": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")})
        e2 = _make_envelope({"run_id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")})
        h1 = hash_decision_envelope(e1)
        h2 = hash_decision_envelope(e2)
        assert h1 != h2

    def test_identical_inputs_same_seed_same_hash(self):
        """Determinism: same inputs always produce the same hash."""
        envelope = _make_envelope()
        hashes = [hash_decision_envelope(envelope) for _ in range(10)]
        assert len(set(hashes)) == 1  # all identical
