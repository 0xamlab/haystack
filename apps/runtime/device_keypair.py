"""Device keypair — a per-machine Ed25519 identity for license activation binding.

The control plane binds an activation to this device's PUBLIC-key thumbprint; the private
key never leaves the machine. License renewal proves possession by signing a server nonce
(see the licensing plan). This is the cryptographic upgrade over the raw device fingerprint
in ``device.py`` — a fingerprint can be cloned, a private key cannot.

Private-key storage (best-effort, most-secure-available), selected by ``ALGENTA_DEVICE_KEY_STORE``:
  * ``secure_enclave`` / ``tpm`` — a NON-EXPORTABLE key in a security element (Apple Secure Enclave /
    TPM 2.0), via ``apps/runtime/hardware_key_store.py``. secp256r1 (``secp256r1:`` thumbprint, ECDSA);
    the key physically cannot leave the element, making the L1 license device-binding tamper-PROOF. Falls
    back to the software store when the hardware is unavailable (the differing thumbprint then fails a
    hardware-bound license closed at the node gate, never silently).
  * ``keyring`` — OS keychain via ``keyring`` (macOS Keychain / Linux Secret Service / Windows Credential
    Manager) when the library AND a working backend are present. Ed25519.
  * ``file`` — encrypted file under the runtime dir (servers / CI / headless), keyed off the machine's RAW
    id (never transmitted), so a copied key file will not decrypt elsewhere; written ``0600``. Ed25519.

``ALGENTA_DEVICE_KEY_STORE`` = ``auto`` (default: keyring → file, Ed25519) | ``file`` | ``keyring`` |
``secure_enclave`` | ``tpm``. Hardware backends are OPT-IN (``auto`` never silently picks hardware, so a
device's thumbprint is stable). ``keyring`` and the hardware libs are OPTIONAL deps — this module degrades
to the encrypted-file store when they are absent, and never hard-requires them.

Identity is ALGORITHM-AGNOSTIC: the thumbprint / signature dispatch on the key type (``ed25519:`` software,
``secp256r1:`` hardware), and the control-plane verifier recomputes both from the public PEM.
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
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
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


def _raw_public_bytes(public_key: Ed25519PublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _software_public_pem() -> str:
    return (
        device_public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


# ── thumbprint / verify are ALGORITHM-AGNOSTIC (Ed25519 software, secp256r1 hardware) ─────────────
# The private key never leaves the machine (software) or the security element (TPM / Secure Enclave); the
# server only ever recomputes the thumbprint + verifies a signature from the PUBLIC pem, so both must
# dispatch on the key's algorithm. The thumbprint prefix (``ed25519:`` / ``secp256r1:``) names it.


def _thumbprint_for_public_key(loaded: object) -> str | None:
    if isinstance(loaded, Ed25519PublicKey):
        digest = hashlib.sha256(_raw_public_bytes(loaded)).digest()
        return "ed25519:" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    if isinstance(loaded, ec.EllipticCurvePublicKey) and isinstance(loaded.curve, ec.SECP256R1):
        raw = loaded.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        digest = hashlib.sha256(raw).digest()
        return "secp256r1:" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return None


def thumbprint_for_public_pem(public_pem: str) -> str | None:
    """Compute the thumbprint for a given public-key PEM (server-side binding check). Handles both the
    software Ed25519 key and a hardware (TPM / Secure Enclave) secp256r1 key."""
    try:
        loaded = serialization.load_pem_public_key(public_pem.encode())
    except (ValueError, TypeError):
        return None
    return _thumbprint_for_public_key(loaded)


def verify_signature(public_pem: str, data: bytes, signature: bytes) -> bool:
    """Verify a device signature against its public-key PEM (server-side proof-of-possession). Ed25519 is
    verified directly; a secp256r1 hardware key is ECDSA-over-SHA256 (matching CryptoKit / TPM signing)."""
    try:
        loaded = serialization.load_pem_public_key(public_pem.encode())
        if isinstance(loaded, Ed25519PublicKey):
            loaded.verify(signature, data)
            return True
        if isinstance(loaded, ec.EllipticCurvePublicKey) and isinstance(loaded.curve, ec.SECP256R1):
            loaded.verify(signature, data, ec.ECDSA(hashes.SHA256()))
            return True
        return False
    except (InvalidSignature, ValueError, TypeError):
        return False


# ── active identity: hardware (TPM / Secure Enclave) when selected + available, else software ─────


def _hardware_store():
    """The selected hardware key store when ``ALGENTA_DEVICE_KEY_STORE`` requests one AND it is available
    on this host, else None (degrade to the software Ed25519 store). Degradation is safe: the thumbprint
    then differs, so a hardware-bound license fails closed at the node gate rather than silently running."""
    mode = _store_mode()
    if mode not in ("secure_enclave", "tpm"):
        return None
    try:
        from apps.runtime.hardware_key_store import get_hardware_key_store

        store = get_hardware_key_store(mode)
        if store is not None and store.available():
            return store
    except Exception:  # noqa: BLE001 — any hardware resolution issue degrades to software
        logger.warning("device_key_hardware_resolution_failed", requested=mode, exc_info=True)
        return None
    logger.warning("device_key_hardware_unavailable_degrading", requested=mode)
    return None


def device_public_key_pem() -> str:
    """The device public key in PEM (SubjectPublicKeyInfo) — sent to the control plane. Hardware key when
    a security element is selected + available, else the software Ed25519 key."""
    hw = _hardware_store()
    if hw is not None:
        try:
            return hw.public_pem()
        except Exception:  # noqa: BLE001 — hardware hiccup degrades to software (fails closed on binding)
            logger.warning("device_key_hardware_pubkey_failed", exc_info=True)
    return _software_public_pem()


def public_key_thumbprint() -> str:
    """Stable, privacy-preserving id for this device's public key, bound into the license as
    ``device_pubkey_thumbprint``. ``ed25519:…`` (software) or ``secp256r1:…`` (hardware). Deterministic
    for a given keypair; reveals nothing about the machine."""
    return thumbprint_for_public_pem(device_public_key_pem()) or ""


def sign(data: bytes) -> bytes:
    """Sign bytes (e.g. a renewal nonce) with this device's private key — in the security element when a
    hardware store is active, else the software Ed25519 key."""
    hw = _hardware_store()
    if hw is not None:
        try:
            return hw.sign(data)
        except Exception:  # noqa: BLE001 — hardware hiccup degrades to software
            logger.warning("device_key_hardware_sign_failed", exc_info=True)
    return ensure_device_keypair().sign(data)


def active_key_store() -> str:
    """Report the active backend for diagnostics (``doctor``): ``secure_enclave`` | ``tpm`` |
    ``keyring`` | ``file``. Never raises."""
    try:
        if _hardware_store() is not None:
            return _store_mode()
        return "keyring" if _keyring() is not None else "file"
    except Exception:  # noqa: BLE001
        return "file"


def reset_device_keypair() -> None:
    """Delete the stored private key (rotation / tests) — software + any hardware store."""
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        except Exception:  # noqa: BLE001, S110 — nothing stored / backend issue is fine
            pass
    path = _file_path()
    if path.exists():
        path.unlink()
    try:
        from apps.runtime.hardware_key_store import reset_hardware_key_stores_for_test

        reset_hardware_key_stores_for_test()
    except Exception:  # noqa: BLE001, S110
        pass
