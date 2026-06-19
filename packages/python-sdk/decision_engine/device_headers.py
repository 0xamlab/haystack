from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path

DEVICE_ID_HEADER = "X-Algenta-Device-Id"
PLATFORM_HEADER = "X-Algenta-Platform"
PLATFORM_VERSION_HEADER = "X-Algenta-Platform-Version"
HOSTNAME_HASH_HEADER = "X-Algenta-Hostname-Hash"
SDK_VERSION_HEADER = "X-Algenta-SDK-Version"
_DEVICE_ID_MIN_LENGTH = 16
_DEVICE_ID_MAX_LENGTH = 64
_PLATFORM_MAX_LENGTH = 50
_PLATFORM_VERSION_MAX_LENGTH = 50
_SDK_VERSION_MAX_LENGTH = 128
_SALT = "algenta-device-v1"


def _runtime_dir() -> Path:
    configured = os.environ.get("ALGENTA_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path.home() / ".algenta" / "runtime"


def _install_id_file() -> Path:
    return _runtime_dir() / "install_id"


def _validate_device_id(device_id: str, source_name: str) -> str:
    normalized = device_id.strip()
    if not (_DEVICE_ID_MIN_LENGTH <= len(normalized) <= _DEVICE_ID_MAX_LENGTH):
        raise ValueError(
            f"{source_name} must be between {_DEVICE_ID_MIN_LENGTH} and "
            f"{_DEVICE_ID_MAX_LENGTH} characters."
        )
    return normalized


def _explicit_device_id() -> str | None:
    for env_name in ("ALGENTA_DEVICE_ID", "DE_DEVICE_ID"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return _validate_device_id(value, env_name)
    return None


def _read_macos_machine_id() -> str | None:
    ioreg_path = shutil.which("ioreg")
    if not ioreg_path:
        return None
    try:
        output = subprocess.check_output(  # noqa: S603
            [ioreg_path, "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode()
    except Exception:
        return None
    for line in output.splitlines():
        if "IOPlatformUUID" not in line:
            continue
        parts = line.split("=")
        if len(parts) >= 2:
            return parts[-1].strip().strip('"')
    return None


def _read_linux_machine_id() -> str | None:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            content = Path(path).read_text().strip()
        except OSError:
            continue
        if content:
            return content
    return None


def _read_windows_machine_id() -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value)
    except Exception:
        return None


def _get_or_create_install_id() -> str:
    path = _install_id_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        content = path.read_text().strip()
        if content:
            return content
    install_id = str(uuid.uuid4())
    path.write_text(install_id)
    return install_id


def _raw_machine_id() -> str:
    system = platform.system()
    if system == "Darwin":
        value = _read_macos_machine_id()
    elif system == "Linux":
        value = _read_linux_machine_id()
    elif system == "Windows":
        value = _read_windows_machine_id()
    else:
        value = None
    return value or _get_or_create_install_id()


def _derived_device_id_from_seed(seed: str) -> str:
    return hashlib.sha256(f"{seed}:{_SALT}".encode()).hexdigest()[:32]


def _derived_device_id() -> str:
    raw_machine_id = _raw_machine_id()
    return _derived_device_id_from_seed(raw_machine_id)


def _fingerprint_hash(seed: str) -> str:
    return hashlib.sha256(f"{seed}:{_SALT}".encode()).hexdigest()


def _fingerprint_seed(device_id: str, raw_machine_id: str) -> str:
    hostname = platform.node().strip()
    if hostname:
        return hostname
    if raw_machine_id:
        return raw_machine_id
    return device_id


def build_device_headers(*, sdk_version: str, user_agent: str) -> dict[str, str]:
    headers = {
        SDK_VERSION_HEADER: sdk_version[:_SDK_VERSION_MAX_LENGTH],
    }
    explicit_device_id = _explicit_device_id()
    raw_machine_id = "" if explicit_device_id is not None else _raw_machine_id()
    device_id = explicit_device_id or _derived_device_id_from_seed(raw_machine_id)
    headers[DEVICE_ID_HEADER] = device_id

    platform_name = platform.system().strip()
    if platform_name:
        headers[PLATFORM_HEADER] = platform_name[:_PLATFORM_MAX_LENGTH]

    platform_version = platform.release().strip()
    if platform_version:
        headers[PLATFORM_VERSION_HEADER] = platform_version[:_PLATFORM_VERSION_MAX_LENGTH]

    fingerprint_seed = _fingerprint_seed(device_id, raw_machine_id or _raw_machine_id())
    if fingerprint_seed:
        headers[HOSTNAME_HASH_HEADER] = _fingerprint_hash(fingerprint_seed)

    if SDK_VERSION_HEADER not in headers and user_agent:
        headers[SDK_VERSION_HEADER] = user_agent[:_SDK_VERSION_MAX_LENGTH]
    return headers


__all__ = [
    "DEVICE_ID_HEADER",
    "HOSTNAME_HASH_HEADER",
    "PLATFORM_HEADER",
    "PLATFORM_VERSION_HEADER",
    "SDK_VERSION_HEADER",
    "build_device_headers",
]
