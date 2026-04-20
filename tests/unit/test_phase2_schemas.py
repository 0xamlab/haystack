"""Unit tests for Phase 2 schemas — recommend, score, batch, compare, auth."""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from apps.api_server.schemas.auth import (
    CreateAPIKeyRequest,
    LoginRequest,
    SignUpRequest,
)
from apps.api_server.schemas.recommend import (
    BatchRequest,
    CompareRequest,
    RecommendRequest,
    ScoreRequest,
)

AUTO_SCENARIO = {
    "mode": "auto",
    "scenario": {
        "variables": {"revenue": {"low": 80000, "high": 200000}},
        "objective": "maximize_net_value",
    },
}


class TestRecommendRequest:
    def test_valid_two_actions(self) -> None:
        req = RecommendRequest.model_validate({
            "actions": [
                {"name": "option_a", "request": AUTO_SCENARIO},
                {"name": "option_b", "request": AUTO_SCENARIO},
            ]
        })
        assert len(req.actions) == 2
        assert req.runs == 10_000  # default

    def test_minimum_two_actions_required(self) -> None:
        with pytest.raises(ValidationError):
            RecommendRequest.model_validate({
                "actions": [
                    {"name": "only_one", "request": AUTO_SCENARIO},
                ]
            })

    def test_maximum_ten_actions(self) -> None:
        with pytest.raises(ValidationError):
            RecommendRequest.model_validate({
                "actions": [
                    {"name": f"action_{i}", "request": AUTO_SCENARIO}
                    for i in range(11)
                ]
            })

    def test_custom_runs(self) -> None:
        req = RecommendRequest.model_validate({
            "actions": [
                {"name": "a", "request": AUTO_SCENARIO},
                {"name": "b", "request": AUTO_SCENARIO},
            ],
            "runs": 5000,
            "seed": 42,
        })
        assert req.runs == 5000
        assert req.seed == 42


class TestScoreRequest:
    def test_valid_score_request(self) -> None:
        req = ScoreRequest.model_validate({
            "request": AUTO_SCENARIO,
        })
        assert req.scoring_weights is None  # use defaults

    def test_custom_weights(self) -> None:
        req = ScoreRequest.model_validate({
            "request": AUTO_SCENARIO,
            "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
        })
        assert req.scoring_weights is not None
        assert req.scoring_weights["expected_value"] == 0.7

    def test_missing_request_invalid(self) -> None:
        with pytest.raises(ValidationError):
            ScoreRequest.model_validate({})


class TestBatchRequest:
    def test_valid_batch(self) -> None:
        req = BatchRequest.model_validate({
            "items": [AUTO_SCENARIO, AUTO_SCENARIO],
        })
        assert len(req.items) == 2

    def test_minimum_one_item(self) -> None:
        with pytest.raises(ValidationError):
            BatchRequest.model_validate({"items": []})

    def test_maximum_100_items(self) -> None:
        with pytest.raises(ValidationError):
            BatchRequest.model_validate({
                "items": [AUTO_SCENARIO] * 101,
            })


class TestCompareRequest:
    def test_valid_compare(self) -> None:
        req = CompareRequest.model_validate({
            "scenarios": [
                {"name": "scenario_a", "request": AUTO_SCENARIO},
                {"name": "scenario_b", "request": AUTO_SCENARIO},
            ]
        })
        assert len(req.scenarios) == 2

    def test_minimum_two_scenarios(self) -> None:
        with pytest.raises(ValidationError):
            CompareRequest.model_validate({
                "scenarios": [{"name": "only_one", "request": AUTO_SCENARIO}]
            })


class TestSignUpRequest:
    def test_valid_signup(self) -> None:
        req = SignUpRequest.model_validate({
            "email": "test@example.com",
            "password": "SecurePassword123",
            "name": "Test User",
        })
        assert str(req.email) == "test@example.com"

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            SignUpRequest.model_validate({
                "email": "not-an-email",
                "password": "SecurePassword123",
                "name": "Test User",
            })

    def test_password_too_short(self) -> None:
        with pytest.raises(ValidationError):
            SignUpRequest.model_validate({
                "email": "test@example.com",
                "password": "short",
                "name": "Test User",
            })

    def test_missing_name(self) -> None:
        with pytest.raises(ValidationError):
            SignUpRequest.model_validate({
                "email": "test@example.com",
                "password": "SecurePassword123",
            })


class TestLoginRequest:
    def test_valid_login(self) -> None:
        req = LoginRequest.model_validate({
            "email": "user@example.com",
            "password": "anypassword",
        })
        assert str(req.email) == "user@example.com"

    def test_invalid_email(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest.model_validate({
                "email": "bademail",
                "password": "anypassword",
            })


class TestCreateAPIKeyRequest:
    def test_valid_key_request(self) -> None:
        req = CreateAPIKeyRequest.model_validate({"label": "Production Key"})
        assert req.label == "Production Key"
        assert req.expires_at is None

    def test_empty_label_invalid(self) -> None:
        with pytest.raises(ValidationError):
            CreateAPIKeyRequest.model_validate({"label": ""})


class TestUserService:
    """Test password hashing utility functions."""

    def test_password_hash_and_verify(self) -> None:
        from apps.api_server.services.user_service import hash_password, verify_password
        hashed = hash_password("MySecurePassword123")
        assert hashed != "MySecurePassword123"  # not plaintext
        assert verify_password("MySecurePassword123", hashed)

    def test_wrong_password_fails(self) -> None:
        from apps.api_server.services.user_service import hash_password, verify_password
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_slug_from_email(self) -> None:
        from apps.api_server.services.user_service import _slug_from_email
        assert _slug_from_email("john.doe@example.com") == "john-doe"
        assert _slug_from_email("user123@company.io") == "user123"
        assert _slug_from_email("UPPERCASE@test.com") == "uppercase"
