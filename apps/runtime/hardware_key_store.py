"""Hardware-backed device keys — a NON-EXPORTABLE node identity in a security element.

Makes the L1 device-binding of ``active_node_limit`` (see ``apps/runtime/node_broker.py``) tamper-PROOF
instead of merely tamper-evident: the per-node private key physically cannot leave the security element, so
a cloned VM / copied key store cannot reproduce the node's identity, and a device-bound self-host license
cannot be activated on a second machine.

Two backends, selected by ``ALGENTA_DEVICE_KEY_STORE``:

* ``secure_enclave`` — Apple Secure Enclave (macOS, Apple Silicon / T2). A tiny CryptoKit helper
  (``SecureEnclave.P256.Signing.PrivateKey``) generates the key IN the Enclave; it never leaves — we persist
  only its opaque, Enclave-bound ``dataRepresentation``. The helper ships as a PREBUILT, code-signed +
  RS256-manifest-signed binary in the sidecar wheel (``algenta_runtime_native/se/``), resolved and VERIFIED
  (signature + SHA-256, fail-closed) before it is ever executed — no runtime compiler (the clean-machine
  contract). ``swiftc`` JIT compilation is a DEV-ONLY fallback (``ALGENTA_RUNTIME_DEV_MODE`` /
  ``ALGENTA_SE_ALLOW_JIT``); ``ALGENTA_SE_HELPER`` points at an explicit binary for debugging.
* ``tpm`` — TPM 2.0 (Linux / Windows) via ``tpm2-pytss``. Feature-detected + opt-in (``ALGENTA_TPM_ENABLE=1``
  + a resolvable TCTI); validated on TPM hardware. Degrade-safe (any error ⇒ ``available()`` False).

Both produce a NIST **P-256 (secp256r1)** key (the Secure Enclave is P-256-only; most TPMs likewise), so the
device identity uses the ``secp256r1:`` thumbprint + ECDSA-SHA256 signatures — ``device_keypair`` dispatches
on algorithm, and the control-plane verifier already recomputes both from the public PEM.

Degradation is SAFE: if the requested hardware is unavailable, ``device_keypair`` falls back to the software
Ed25519 store, whose thumbprint differs — so a license bound to a hardware ``secp256r1:`` thumbprint simply
fails closed at the node gate rather than silently running on a software key.
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)

_SE_BLOB_FILENAME = "device_se_key.b64"
_SE_HELPER_NAME = "algenta-se-helper"
_SE_MANIFEST_NAME = "manifest.json"
_SE_SIG_NAME = "manifest.sig"
_SUBPROCESS_TIMEOUT = 30


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _dev_jit_allowed() -> bool:
    """swiftc JIT compilation of the helper is DEV-ONLY. A release ships a prebuilt, signed helper in the
    sidecar wheel — the clean-machine contract forbids a runtime compiler. Opt in for local dev only."""
    return _env_truthy("ALGENTA_RUNTIME_DEV_MODE") or _env_truthy("ALGENTA_SE_ALLOW_JIT")


def _runtime_dir() -> Path:
    base = os.environ.get("ALGENTA_RUNTIME_DIR") or str(Path.home() / ".algenta" / "runtime")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


@runtime_checkable
class HardwareKeyStore(Protocol):
    """A non-exportable secp256r1 signing key in a security element."""

    algorithm: str  # always "secp256r1"

    def available(self) -> bool:
        """True iff this security element is usable on this host (cached)."""

    def public_pem(self) -> str:
        """Ensure the key exists; return its SubjectPublicKeyInfo PEM."""

    def sign(self, data: bytes) -> bytes:
        """ECDSA-SHA256 signature (DER) over ``data``, computed inside the element."""

    def reset(self) -> None:
        """Drop the persisted key handle (rotation / tests)."""


# ── Apple Secure Enclave (macOS) — real, via a CryptoKit helper ───────────────────────────────────

# The Swift helper source is a committed file (single source of truth for the release build script AND the
# dev-JIT fallback). apps/runtime/se_helper.swift: create / pubkey / sign / check against a SecureEnclave key.
_SE_HELPER_SWIFT_PATH = Path(__file__).resolve().parent / "se_helper.swift"


def _se_helper_source() -> str:
    return _SE_HELPER_SWIFT_PATH.read_text(encoding="utf-8")


def _swiftc() -> str | None:
    found = shutil.which("swiftc")
    if found:
        return found
    for cand in ("/Library/Developer/CommandLineTools/usr/bin/swiftc", "/usr/bin/swiftc"):
        if Path(cand).exists():
            return cand
    try:
        out = subprocess.run(  # noqa: S603
            ["/usr/bin/xcrun", "--find", "swiftc"], capture_output=True, text=True, timeout=10
        )
        p = out.stdout.strip()
        return p or None
    except Exception:  # noqa: BLE001
        return None


class SecureEnclaveKeyStore:
    """Secure Enclave P-256 signing key (macOS). Private key stays in the Enclave; we persist only its
    opaque Enclave-bound representation."""

    algorithm = "secp256r1"

    def __init__(self) -> None:
        self._avail: bool | None = None
        self._helper: str | None = None
        self._source: str = ""
        self._resolved: bool = False

    # -- resolution: prefer a VERIFIED prebuilt helper (in the wheel); JIT is dev-only --
    def _sidecar_se_dir(self) -> Path | None:
        """The SE helper dir inside the installed ``algenta-runtime-native`` sidecar (i.e. in the wheel)."""
        try:
            from importlib import resources

            d = Path(str(resources.files("algenta_runtime_native"))) / "se"
            return d if d.exists() else None
        except Exception:  # noqa: BLE001 — sidecar not installed (e.g. engine-only host)
            return None

    def _repo_se_dir(self) -> Path | None:
        """Engine-repo bundle location (local builds / tests): apps/runtime/_native/se/."""
        d = Path(__file__).resolve().parent / "_native" / "se"
        return d if d.exists() else None

    def _verify_bundled(self, d: Path) -> str | None:
        """Verify the prebuilt helper in ``d`` against its RS256-signed manifest + SHA-256. Returns the
        executable path when trusted, else None (fail-closed: a present-but-unverifiable helper is refused,
        never executed)."""
        binp = d / _SE_HELPER_NAME
        if not binp.exists():
            return None
        try:
            from apps.runtime import native_manifest

            native_manifest.verify_bundled_artifact(
                str(binp), str(d / _SE_MANIFEST_NAME), str(d / _SE_SIG_NAME), expected_name=_SE_HELPER_NAME
            )
        except Exception as exc:  # noqa: BLE001 — unverifiable ⇒ do NOT run it
            logger.error("se_helper_bundled_verify_failed", dir=str(d), error=str(exc))
            return None
        try:
            binp.chmod(binp.stat().st_mode | stat.S_IXUSR)
        except OSError:
            pass
        return str(binp)

    def _resolve(self) -> tuple[str, str] | None:
        # 1) explicit override (dev / debug)
        env = os.environ.get("ALGENTA_SE_HELPER")
        if env and Path(env).exists():
            return env, "env"
        # 2) prebuilt + SIGNED helper bundled in the wheel (sidecar) or the engine repo — the release path
        for d, src in ((self._sidecar_se_dir(), "sidecar"), (self._repo_se_dir(), "repo")):
            if d is not None:
                verified = self._verify_bundled(d)
                if verified:
                    return verified, src
        # 3) DEV ONLY: JIT-compile with swiftc (never in a release; clean-machine contract forbids it)
        if _dev_jit_allowed():
            binp = self._compile_helper()
            if binp:
                return binp, "jit-dev"
        return None

    # -- helper compilation (DEV ONLY; cached by source hash) --
    def _compile_helper(self) -> str | None:
        swiftc = _swiftc()
        if swiftc is None:
            return None
        rt = _runtime_dir()
        swift_src = _se_helper_source()
        src_hash = hashlib.sha256(swift_src.encode()).hexdigest()[:12]
        binary = rt / f".se_helper_{src_hash}"
        if binary.exists() and os.access(binary, os.X_OK):
            return str(binary)
        src = rt / f".se_helper_{src_hash}.swift"
        try:
            src.write_text(swift_src, encoding="utf-8")
            res = subprocess.run(  # noqa: S603
                [swiftc, "-O", str(src), "-o", str(binary)],
                capture_output=True, text=True, timeout=180,
            )
            if res.returncode != 0:
                logger.warning("se_helper_compile_failed", stderr=res.stderr[-400:])
                return None
            binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
            return str(binary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("se_helper_compile_error", error=str(exc))
            return None
        finally:
            try:
                src.unlink(missing_ok=True)
            except OSError:
                pass

    def _get_helper(self) -> str | None:
        if not self._resolved:
            resolved = self._resolve()
            self._resolved = True
            if resolved is not None:
                self._helper, self._source = resolved
        return self._helper

    def source(self) -> str:
        """Where the active helper came from (``sidecar`` | ``repo`` | ``env`` | ``jit-dev`` | ``""``),
        for ``doctor`` diagnostics."""
        self._get_helper()
        return self._source

    def _run(self, args: list[str], *, stdin: bytes | None = None) -> str | None:
        helper = self._get_helper()
        if helper is None:
            return None
        try:
            res = subprocess.run(  # noqa: S603
                [helper, *args], input=stdin, capture_output=True, timeout=_SUBPROCESS_TIMEOUT
            )
            if res.returncode != 0:
                logger.warning("se_helper_run_failed", args=args[:1], stderr=res.stderr[-300:].decode("utf-8", "replace"))
                return None
            return res.stdout.decode("utf-8").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("se_helper_run_error", error=str(exc))
            return None

    def available(self) -> bool:
        if self._avail is not None:
            return self._avail
        if sys.platform != "darwin":
            self._avail = False
            return False
        out = self._run(["check"])
        self._avail = out == "available"
        return self._avail

    def _blob_path(self) -> Path:
        return _runtime_dir() / _SE_BLOB_FILENAME

    def public_pem(self) -> str:
        blob = self._blob_path()
        if blob.exists():
            pem = self._run(["pubkey", str(blob)])
            if pem:
                return pem
            logger.warning("se_pubkey_unreadable_regenerating")
        pem = self._run(["create", str(blob)])
        if not pem:
            raise RuntimeError("Secure Enclave key creation failed")
        try:
            blob.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except OSError:
            pass
        logger.info("se_device_key_created")
        return pem

    def sign(self, data: bytes) -> bytes:
        blob = self._blob_path()
        if not blob.exists():
            self.public_pem()  # ensure the key exists
        out = self._run(["sign", str(blob)], stdin=data)
        if not out:
            raise RuntimeError("Secure Enclave signing failed")
        return base64.b64decode(out)

    def reset(self) -> None:
        try:
            self._blob_path().unlink(missing_ok=True)
        except OSError:
            pass
        self._avail = None
        self._helper = None
        self._source = ""
        self._resolved = False


# ── TPM 2.0 (Linux / Windows) — feature-detected, opt-in, degrade-safe ────────────────────────────


class TpmKeyStore:
    """TPM 2.0 P-256 signing key via ``tpm2-pytss``. Opt-in (``ALGENTA_TPM_ENABLE=1``) and feature-detected
    — validated on TPM hardware. Any error makes ``available()`` False so the caller degrades to software
    (which fails closed on a hardware-bound license). Never activates accidentally on a host without a TPM."""

    algorithm = "secp256r1"

    def __init__(self) -> None:
        self._avail: bool | None = None

    def available(self) -> bool:
        if self._avail is not None:
            return self._avail
        avail = False
        if (os.environ.get("ALGENTA_TPM_ENABLE") or "").strip().lower() in {"1", "true", "yes", "on"}:
            try:
                import tpm2_pytss  # type: ignore[import-not-found]  # noqa: F401

                # A TCTI must resolve (real /dev/tpmrm0, swtpm, or ALGENTA_TPM_TCTI). Construction of the
                # ESAPI context is the real availability probe.
                from tpm2_pytss import ESAPI  # type: ignore[import-not-found]

                tcti = os.environ.get("ALGENTA_TPM_TCTI") or None
                ctx = ESAPI(tcti)
                ctx.close()
                avail = True
            except Exception as exc:  # noqa: BLE001 — no lib / no TPM / no TCTI ⇒ unavailable
                logger.info("tpm_keystore_unavailable", error=str(exc))
                avail = False
        self._avail = avail
        return avail

    def public_pem(self) -> str:  # pragma: no cover - requires TPM hardware
        raise RuntimeError(
            "TpmKeyStore.public_pem must run on TPM hardware (tpm2-pytss). It is feature-detected + "
            "validated on a TPM; on this host it reports available()=False and the caller degrades."
        )

    def sign(self, data: bytes) -> bytes:  # pragma: no cover - requires TPM hardware
        raise RuntimeError("TpmKeyStore.sign requires TPM hardware")

    def reset(self) -> None:
        self._avail = None


# ── factory + singletons ──────────────────────────────────────────────────────────────────────────

_STORES: dict[str, HardwareKeyStore] = {}


def get_hardware_key_store(mode: str) -> HardwareKeyStore | None:
    """Return the (cached) hardware key store for ``mode`` (``secure_enclave`` | ``tpm``), or None for an
    unknown mode. Does NOT check availability — the caller does (``.available()``)."""
    mode = (mode or "").strip().lower()
    if mode not in ("secure_enclave", "tpm"):
        return None
    store = _STORES.get(mode)
    if store is None:
        store = SecureEnclaveKeyStore() if mode == "secure_enclave" else TpmKeyStore()
        _STORES[mode] = store
    return store


def reset_hardware_key_stores_for_test() -> None:
    for store in _STORES.values():
        try:
            store.reset()
        except Exception:  # noqa: BLE001, S110
            pass
    _STORES.clear()
