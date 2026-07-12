"""Secure credential access for ``algenta login`` and runtime control-plane calls."""

from __future__ import annotations

import hmac
import os
from pathlib import Path

from algenta import paths

_SERVICE = "ai.algenta.cli"
_API_KEY_ACCOUNT = "api-key"
_LICENSE_ACCOUNT = "device-license"


class CredentialStoreError(RuntimeError):
    """A secret could not be persisted in the operating-system credential store."""


def _keyring_module():
    import keyring

    return keyring


def _store_secret(account: str, value: str) -> None:
    normalized = value.strip()
    if not normalized:
        raise CredentialStoreError(f"Refusing to store an empty {account}.")
    try:
        keyring = _keyring_module()
        keyring.set_password(_SERVICE, account, normalized)
        stored = keyring.get_password(_SERVICE, account)
    except Exception as exc:
        raise CredentialStoreError(
            "No secure operating-system credential store is available. "
            "Configure ALGENTA_API_KEY for non-interactive API access."
        ) from exc
    if not stored or not hmac.compare_digest(stored, normalized):
        raise CredentialStoreError(
            "The operating-system credential store did not verify the saved secret."
        )


def _read_secret(account: str) -> str | None:
    try:
        value = _keyring_module().get_password(_SERVICE, account)
    except Exception as exc:
        raise CredentialStoreError(
            "The operating-system credential store is unavailable. "
            "Set ALGENTA_API_KEY for non-interactive API access."
        ) from exc
    return value.strip() if value and value.strip() else None


def _delete_secret(account: str) -> None:
    _keyring_module().delete_password(_SERVICE, account)


def _restore_secret(account: str, previous: str | None) -> None:
    if previous is None:
        _delete_secret(account)
        return
    _store_secret(account, previous)


def _remove_legacy_file(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def _read_and_migrate_legacy_file(account: str, path: str) -> str | None:
    legacy_path = Path(path)
    if not legacy_path.is_file():
        return None
    value = legacy_path.read_text(encoding="utf-8").strip()
    if not value:
        legacy_path.unlink(missing_ok=True)
        return None
    _store_secret(account, value)
    legacy_path.unlink()
    return value


def store_api_key(api_key: str) -> None:
    _store_secret(_API_KEY_ACCOUNT, api_key)
    _remove_legacy_file(paths.api_key_path())
    _remove_legacy_file(paths.token_path())


def store_license(license_token: str) -> None:
    _store_secret(_LICENSE_ACCOUNT, license_token)
    _remove_legacy_file(paths.license_path())


def store_login_credentials(api_key: str, license_token: str) -> None:
    previous = {
        _API_KEY_ACCOUNT: _read_secret(_API_KEY_ACCOUNT),
        _LICENSE_ACCOUNT: _read_secret(_LICENSE_ACCOUNT),
    }
    changed_accounts: list[str] = []
    try:
        changed_accounts.append(_API_KEY_ACCOUNT)
        _store_secret(_API_KEY_ACCOUNT, api_key)
        changed_accounts.append(_LICENSE_ACCOUNT)
        _store_secret(_LICENSE_ACCOUNT, license_token)
    except CredentialStoreError as exc:
        rollback_errors: list[str] = []
        for account in reversed(changed_accounts):
            try:
                _restore_secret(account, previous[account])
            except Exception:
                rollback_errors.append(account)
        if rollback_errors:
            raise CredentialStoreError(
                "Credential persistence failed and keyring rollback was incomplete for: "
                + ", ".join(rollback_errors)
            ) from exc
        raise
    _remove_legacy_file(paths.api_key_path())
    _remove_legacy_file(paths.token_path())
    _remove_legacy_file(paths.license_path())


def read_api_key() -> str | None:
    """Return the environment key, OS-keyring key, or securely migrated legacy key."""
    configured = (os.environ.get("ALGENTA_API_KEY") or "").strip()
    if configured:
        return configured
    return _read_secret(_API_KEY_ACCOUNT) or _read_and_migrate_legacy_file(
        _API_KEY_ACCOUNT,
        paths.api_key_path(),
    )


def read_license() -> str | None:
    configured = (os.environ.get("ALGENTA_LICENSE_JWT") or "").strip()
    if configured:
        return configured
    return _read_secret(_LICENSE_ACCOUNT) or _read_and_migrate_legacy_file(
        _LICENSE_ACCOUNT,
        paths.license_path(),
    )


def read_token() -> str | None:
    """Use an explicit control-plane token, otherwise use the API key."""
    return (os.environ.get("ALGENTA_TOKEN") or "").strip() or read_api_key()


def is_logged_in() -> bool:
    return bool(read_api_key())
