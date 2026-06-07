"""Unit tests for connector config_json envelope encryption (Phase 1b)."""

import uuid

import pytest

from apps.api_server.services import config_crypto as cc

ORG = uuid.uuid4()
DSN = '{"connection_string": "postgres://app:s3cr3t@db/x"}'


def test_disabled_is_passthrough(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)
    assert cc.is_config_encryption_enabled() is False
    assert cc.encrypt_config_json(DSN, org_id=ORG) == DSN  # plaintext stored
    assert cc.decrypt_config_json(DSN, org_id=ORG) == DSN  # plaintext read


def test_round_trip_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "a" * 64)
    assert cc.is_config_encryption_enabled() is True
    enc = cc.encrypt_config_json(DSN, org_id=ORG)
    assert enc != DSN
    assert cc.is_encrypted(enc)
    assert "s3cr3t" not in enc  # encrypted at rest
    assert cc.decrypt_config_json(enc, org_id=ORG) == DSN


def test_legacy_plaintext_still_readable_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "b" * 64)
    # a pre-encryption row (plaintext, no prefix) must pass through unchanged
    assert cc.decrypt_config_json(DSN, org_id=ORG) == DSN


def test_aad_binds_org(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "c" * 64)
    enc = cc.encrypt_config_json(DSN, org_id=ORG)
    with pytest.raises(Exception):
        cc.decrypt_config_json(enc, org_id=uuid.uuid4())  # different org → auth fail


def test_encrypted_value_without_key_raises(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "d" * 64)
    enc = cc.encrypt_config_json(DSN, org_id=ORG)
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError):
        cc.decrypt_config_json(enc, org_id=ORG)


def test_dict_envelope_disabled_passthrough(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)
    d = {"token": "secret-tok", "url": "https://x"}
    assert cc.encrypt_config_dict(d, org_id=ORG) == d
    assert cc.decrypt_config_dict(d, org_id=ORG) == d


def test_dict_envelope_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "f" * 64)
    d = {"token": "secret-tok", "nested": {"k": "v"}}
    enc = cc.encrypt_config_dict(d, org_id=ORG)
    assert enc is not None and "__enc__" in enc
    assert "secret-tok" not in str(enc)  # encrypted at rest
    assert cc.decrypt_config_dict(enc, org_id=ORG) == d


def test_dict_envelope_legacy_plain_dict_passthrough(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "9" * 64)
    plain = {"token": "legacy"}  # no __enc__ key → legacy plaintext
    assert cc.decrypt_config_dict(plain, org_id=ORG) == plain


def test_dict_envelope_empty_and_none(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "8" * 64)
    assert cc.encrypt_config_dict(None, org_id=ORG) is None
    assert cc.encrypt_config_dict({}, org_id=ORG) == {}  # nothing to encrypt
    assert cc.decrypt_config_dict(None, org_id=ORG) is None


def test_fingerprint_is_deterministic_and_key_independent(monkeypatch) -> None:
    cfg = {"b": 2, "a": 1}
    monkeypatch.delenv("ALGENTA_CONFIG_ENCRYPTION_KEY", raising=False)
    fp_no_key = cc.config_fingerprint(cfg)
    monkeypatch.setenv("ALGENTA_CONFIG_ENCRYPTION_KEY", "e" * 64)
    fp_key = cc.config_fingerprint(cfg)
    # stable across key state AND key ordering (canonical JSON)
    assert fp_no_key == fp_key
    assert cc.config_fingerprint({"a": 1, "b": 2}) == fp_no_key
    assert cc.config_fingerprint({"a": 1}) != fp_no_key
