"""Device keypair — a per-machine Ed25519 identity for license activation binding.

The control plane binds an activation to this device's PUBLIC-key thumbprint; the private
key never leaves the machine. License renewal proves possession by signing a server nonce
(see the licensing plan). This is the cryptographic upgrade over the raw device fingerprint
in ``device.py`` — a fingerprint can be cloned, a private key cannot.

Private-key storage (best-effort, most-secure-available):
  1. OS keychain via ``keyring`` (macOS Keychain / Linux Secret Service / Windows Credential
     Manager) when the library AND a working backend are present.
  2. Encrypted file under the runtime dir otherwise (servers / CI / headless). The file is
     encrypted with a key derived from the machine's RAW id (never transmitted), so a copied
     key file will not decrypt on another machine, and is written ``0600``.

``ALGENTA_DEVICE_KEY_STORE`` = ``auto`` (default) | ``file`` | ``keyring`` forces the backend
(``file`` keeps tests hermetic and gives headless ops a deterministic path).

``keyring`` is an OPTIONAL dependency: this module degrades to the encrypted-file store when
it is absent or has no usable backend — it never hard-requires it.
"""

from __future__ import annotations

import base64
import hashlib
import os
import stat
from pathlib import Path

import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

logger = structlog.get_logger(__name__)

_KEYRING_SERVICE = "algenta-device-key"
_KEYRING_USERNAME = "ed25519-private-key-pem"
_KEY_FILENAME = "device_key.enc"
_FILE_SALT = b"algenta-device-key-v1"


def _runtime_dir() -> Path:
    base = os.environ.get("ALGENTA_RUNTIME_DIR") or str(Path.home() / ".algenta" / "runtime")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_mode() -> str:
    return (os.environ.get("ALGENTA_DEVICE_KEY_STORE") or "auto").strip().lower()


# ── keyring backend (optional) ────────────────────────────────────────────────


def _keyring():
    """Return the keyring module if importable AND a usable backend exists, else None."""
    if _store_mode() == "file":
        return None
    try:
        import keyring  # type: ignore[import-not-found]
        from keyring.backends.fail import Keyring as FailKeyring  # type: ignore[import-not-found]

        if isinstance(keyring.get_keyring(), FailKeyring):
            return None  # installed but no OS backend (headless) → fall back to file
        return keyring
    except Exception:  # noqa: BLE001 — any import/backend issue → file fallback
        if _store_mode() == "keyring":
            raise
        return None


# ── encrypted-file backend ────────────────────────────────────────────────────


def _file_cipher() -> Fernet:
    """A machine-bound Fernet cipher (key derived from the RAW machine id, never sent)."""
    from apps.runtime.device import _raw_machine_id

    seed = hashlib.sha256(_raw_machine_id().encode() + _FILE_SALT).digest()
    return Fernet(base64.urlsafe_b64encode(seed))


def _file_path() -> Path:
    return _runtime_dir() / _KEY_FILENAME


def _file_load() -> str | None:
    path = _file_path()
    if not path.exists():
        return None
    try:
        return _file_cipher().decrypt(path.read_bytes()).decode()
    except (InvalidToken, ValueError, OSError):
        # Corrupt, or copied from another machine → treat as absent (regenerate).
        logger.warning("device_key_file_unreadable", path=str(path))
        return None


def _file_save(pem: str) -> None:
    path = _file_path()
    path.write_bytes(_file_cipher().encrypt(pem.encode()))
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:  # pragma: no cover - non-POSIX
        pass


# ── private-key load / save (keyring → file) ──────────────────────────────────


def _load_private_pem() -> str | None:
    kr = _keyring()
    if kr is not None:
        try:
            pem = kr.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
            if pem:
                return pem
        except Exception:  # noqa: BLE001 — backend hiccup → try file
            logger.warning("device_key_keyring_read_failed", exc_info=True)
    return _file_load()


def _save_private_pem(pem: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, pem)
            return
        except Exception:  # noqa: BLE001 — backend hiccup → file fallback
            logger.warning("device_key_keyring_write_failed", exc_info=True)
    _file_save(pem)


def _private_pem(key: Ed25519PrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


# ── public API ────────────────────────────────────────────────────────────────


def ensure_device_keypair() -> Ed25519PrivateKey:
    """Load this device's Ed25519 private key, generating + persisting one on first use."""
    pem = _load_private_pem()
    if pem:
        try:
            loaded = serialization.load_pem_private_key(pem.encode(), password=None)
            if isinstance(loaded, Ed25519PrivateKey):
                return loaded
        except (ValueError, TypeError):
            logger.warning("device_key_corrupt_regenerating")
    key = Ed25519PrivateKey.generate()
    _save_private_pem(_private_pem(key))
    logger.info("device_keypair_generated")
    return key


def device_public_key() -> Ed25519PublicKey:
    return ensure_device_keypair().public_key()


def device_public_key_pem() -> str:
    """The device public key in PEM (SubjectPublicKeyInfo) — sent to the control plane."""
    return (
        device_public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


def _raw_public_bytes(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_thumbprint() -> str:
    """Stable, privacy-preserving id for this device's public key.

    ``ed25519:<base64url(sha256(raw_public_key))>`` — bound into the license as
    ``device_pubkey_thumbprint``. Deterministic for a given keypair; reveals nothing about
    the machine.
    """
    digest = hashlib.sha256(_raw_public_bytes(device_public_key())).digest()
    return "ed25519:" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def sign(data: bytes) -> bytes:
    """Sign bytes (e.g. a renewal nonce) with this device's private key."""
    return ensure_device_keypair().sign(data)


def verify_signature(public_pem: str, data: bytes, signature: bytes) -> bool:
    """Verify a signature against a device public key PEM (server-side proof-of-possession)."""
    try:
        loaded = serialization.load_pem_public_key(public_pem.encode())
        if not isinstance(loaded, Ed25519PublicKey):
            return False
        loaded.verify(signature, data)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def thumbprint_for_public_pem(public_pem: str) -> str | None:
    """Compute the thumbprint for a given public-key PEM (server-side binding check)."""
    try:
        loaded = serialization.load_pem_public_key(public_pem.encode())
        if not isinstance(loaded, Ed25519PublicKey):
            return None
    except (ValueError, TypeError):
        return None
    digest = hashlib.sha256(_raw_public_bytes(loaded)).digest()
    return "ed25519:" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def reset_device_keypair() -> None:
    """Delete the stored private key (rotation / tests)."""
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        except Exception:  # noqa: BLE001, S110 — nothing stored / backend issue is fine
            pass
    path = _file_path()
    if path.exists():
        path.unlink()
