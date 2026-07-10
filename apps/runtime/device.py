"""
Device fingerprinting — stable, privacy-respecting machine identity.

Goal: one API key = N licensed devices. Each device gets a unique, stable ID
so the control plane can count machines without exposing personal data.

Strategy (privacy-first):
  1. Read OS-native machine ID (no PII — just a hardware/OS UUID)
  2. Hash with a fixed salt so the raw ID never leaves the machine
  3. Fall back to a persisted install UUID if OS ID is unavailable

The device_id that reaches the server is:
  SHA-256(machine_id_raw + ALGENTA_DEVICE_SALT)[:32]

It cannot be reversed to identify the machine or user.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_SALT = "algenta-device-v1"  # version-namespaced, non-secret
_DEVICE_ID_MIN_LENGTH = 16
_DEVICE_ID_MAX_LENGTH = 64
_DEVICE_ID_ENV_VARS = ("ALGENTA_DEVICE_ID", "DE_DEVICE_ID")


def _runtime_dir() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))


def _install_id_file() -> Path:
    return _runtime_dir() / "install_id"


def _validate_explicit_device_id(device_id: str, source_name: str) -> str:
    normalized = device_id.strip()
    if not (_DEVICE_ID_MIN_LENGTH <= len(normalized) <= _DEVICE_ID_MAX_LENGTH):
        raise ValueError(
            f"{source_name} must be between {_DEVICE_ID_MIN_LENGTH} and "
            f"{_DEVICE_ID_MAX_LENGTH} characters."
        )
    return normalized


def _explicit_device_id() -> str | None:
    for env_name in _DEVICE_ID_ENV_VARS:
        value = os.environ.get(env_name, "").strip()
        if value:
            return _validate_explicit_device_id(value, env_name)
    return None


# ── OS-native machine ID readers ──────────────────────────────────────────────


def _read_macos_machine_id() -> str | None:
    """IOPlatformUUID — stable across reboots, unique per hardware."""
    ioreg_path = shutil.which("ioreg")
    if not ioreg_path:
        logger.debug("macos_machine_id_reader_missing")
        return None
    try:
        out = subprocess.check_output(  # noqa: S603
            [ioreg_path, "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode()
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                # Line looks like: "IOPlatformUUID" = "XXXX-XXXX-..."
                parts = line.split("=")
                if len(parts) >= 2:
                    return parts[-1].strip().strip('"')
    except Exception as exc:
        logger.debug("macos_machine_id_read_failed", error=str(exc))
    return None


def _read_linux_machine_id() -> str | None:
    """Standard D-Bus / systemd machine ID."""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            content = Path(path).read_text().strip()
            if content:
                return content
        except Exception as exc:
            logger.debug("linux_machine_id_read_failed", path=path, error=str(exc))
    return None


def _read_windows_machine_id() -> str | None:
    """HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid."""
    try:
        winreg = importlib.import_module("winreg")
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value)
    except Exception as exc:
        logger.debug("windows_machine_id_read_failed", error=str(exc))
    return None


def _get_or_create_install_id() -> str:
    """Persistent fallback: generate a UUID on first run and store it."""
    install_id_file = _install_id_file()
    install_id_file.parent.mkdir(parents=True, exist_ok=True)
    if install_id_file.exists():
        try:
            content = install_id_file.read_text().strip()
            if content:
                return content
        except Exception as exc:
            logger.debug("install_id_read_failed", error=str(exc))
    new_id = str(uuid.uuid4())
    install_id_file.write_text(new_id)
    return new_id


def _raw_machine_id() -> str:
    """Best-available raw machine ID, falling back gracefully."""
    system = platform.system()
    raw: str | None = None

    if system == "Darwin":
        raw = _read_macos_machine_id()
    elif system == "Linux":
        raw = _read_linux_machine_id()
    elif system == "Windows":
        raw = _read_windows_machine_id()

    if not raw:
        raw = _get_or_create_install_id()
        logger.debug("device_id_fallback_to_install_uuid")

    return raw


def get_device_id() -> str:
    """
    Return a stable, hashed device identifier.
    The same machine always produces the same ID; different machines produce different IDs.
    The raw machine ID never leaves the machine.
    """
    explicit_device_id = _explicit_device_id()
    if explicit_device_id is not None:
        return explicit_device_id
    raw = _raw_machine_id()
    hashed = hashlib.sha256(f"{raw}:{_SALT}".encode()).hexdigest()[:32]
    return hashed


def get_device_info() -> dict[str, str]:
    """Return non-sensitive device context for the license request."""
    return {
        "device_id": get_device_id(),
        "platform": platform.system(),
        "platform_version": platform.release(),
        "hostname_hash": hashlib.sha256((platform.node() + ":" + _SALT).encode()).hexdigest()[:16],
        "python_version": platform.python_version(),
        "sdk_version": "0.1.0",
    }
