"""services/unverified_jwt_peek.py — the explicit, key-less payload pre-read the bearer verifiers
use for routing and JWKS selection. It must read exactly what a real JWT carries, reject anything
that is not a three-segment JWS with a JSON-object payload, and never look at the signature.
"""

from __future__ import annotations

import base64
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from apps.api_server.services.unverified_jwt_peek import (
    UnverifiedJwtError,
    peek_unverified_claims,
)

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_reads_the_payload_of_a_real_rs256_token() -> None:
    claims = {"iss": "https://idp.example/realms/acme", "tid": "T1", "aud": ["a", "b"], "n": 7}
    token = jwt.encode(claims, _KEY, algorithm="RS256", headers={"kid": "k1"})
    assert peek_unverified_claims(token) == claims


def test_matches_the_raw_payload_segment_exactly() -> None:
    # Oracle: PyJWT's own base64url decoder on the second segment — the same bytes the verified
    # decode will later parse, so the pre-read and the real claims can never disagree.
    claims = {"iss": "x", "sub": "s", "exp": 1_900_000_000, "nested": {"a": [1, 2, {"b": None}]}}
    token = jwt.encode(claims, _KEY, algorithm="RS256")
    raw_payload = jwt.utils.base64url_decode(token.split(".")[1].encode())
    assert peek_unverified_claims(token) == json.loads(raw_payload) == claims


def test_signature_segment_is_never_consulted() -> None:
    # A garbage / stripped signature does not change what the payload says — this helper carries
    # no trust, so it must not even fail on a bad signature (that is the verified decode's job).
    claims = {"iss": "x", "tid": "T1"}
    token = jwt.encode(claims, _KEY, algorithm="RS256")
    header, payload, _sig = token.split(".")
    assert peek_unverified_claims(f"{header}.{payload}.AAAA") == claims
    assert peek_unverified_claims(f"{header}.{payload}.") == claims


def test_payload_without_padding_is_handled() -> None:
    # base64url per RFC 7515 strips '='; payload lengths that need 1, 2 or 0 pad chars all decode.
    for claims in ({"a": 1}, {"ab": 12}, {"abc": 123}, {"iss": "u"}):
        payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
        assert peek_unverified_claims(f"{_b64url(b'{}')}.{payload}.sig") == claims


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-jwt",
        "only.two",
        "a.b.c.d",
        f"{_b64url(b'{}')}.{_b64url(b'{}')}.sig.extra",
        f"{_b64url(b'{}')}..sig",  # empty payload segment
        f"{_b64url(b'{}')}.%%%not-base64url%%%.sig",
        f"{_b64url(b'{}')}.{_b64url(b'not json')}.sig",
        f"{_b64url(b'{}')}.{_b64url(b'[1, 2, 3]')}.sig",  # JSON but not an object
        f"{_b64url(b'{}')}.{_b64url(b'\"str\"')}.sig",
        f"{_b64url(b'{}')}.{_b64url(bytes([0xFF, 0xFE, 0x7B]))}.sig",  # not UTF-8
    ],
)
def test_rejects_anything_that_is_not_a_readable_jws(token: str) -> None:
    with pytest.raises(UnverifiedJwtError):
        peek_unverified_claims(token)


def test_error_is_a_value_error() -> None:
    # Callers that only care that "this is not a JWT" can catch the stdlib type.
    with pytest.raises(ValueError):
        peek_unverified_claims("nope")


def test_whitespace_around_the_token_is_tolerated() -> None:
    token = jwt.encode({"iss": "x"}, _KEY, algorithm="RS256")
    assert peek_unverified_claims(f"  {token}\n") == {"iss": "x"}
