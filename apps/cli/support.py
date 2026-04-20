from __future__ import annotations

import getpass
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("DE_CONFIG_DIR", Path.home() / ".de"))
CONFIG_FILE = CONFIG_DIR / "config.json"
SECRET_FILE = CONFIG_DIR / "secrets.bin"
SECRET_SERVICE = "decision-engine-cli"  # noqa: S105


def load_config() -> dict[str, str]:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_config(config: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def store_api_key_secure(config: dict[str, str], api_key: str) -> None:
    try:
        import keyring  # type: ignore[import]

        keyring.set_password(SECRET_SERVICE, "api_key", api_key)
        config.pop("api_key", None)
        config["api_key_backend"] = "keyring"
        return
    except Exception as exc:
        logger.debug("keyring_store_failed", exc_info=exc)

    try:
        from cryptography.fernet import Fernet  # type: ignore[import]

        key = config.get("api_key_encryption_key")
        if not key:
            key = Fernet.generate_key().decode()
            config["api_key_encryption_key"] = key
        token = Fernet(key.encode()).encrypt(api_key.encode())
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_bytes(token)
        config.pop("api_key", None)
        config["api_key_backend"] = "encrypted_file"
        return
    except Exception as exc:
        logger.debug("encrypted_file_store_failed", exc_info=exc)

    config["api_key"] = api_key
    config["api_key_backend"] = "config"


def load_api_key_from_storage(config: dict[str, str]) -> str:
    backend = config.get("api_key_backend", "")
    if backend == "keyring":
        try:
            import keyring  # type: ignore[import]

            secret = keyring.get_password(SECRET_SERVICE, "api_key")
            if secret:
                return secret
        except Exception as exc:
            logger.debug("keyring_load_failed", exc_info=exc)
    elif backend == "encrypted_file":
        try:
            from cryptography.fernet import Fernet  # type: ignore[import]

            key = config.get("api_key_encryption_key", "")
            if key and SECRET_FILE.exists():
                return Fernet(key.encode()).decrypt(SECRET_FILE.read_bytes()).decode()
        except Exception as exc:
            logger.debug("encrypted_file_load_failed", exc_info=exc)
    return config.get("api_key", "")


def get_api_key() -> str:
    key = os.environ.get("DE_API_KEY", "")
    if not key:
        config = load_config()
        key = load_api_key_from_storage(config)
    if not key:
        print("❌ No API key found. Run: de config set-key <your-key>", file=sys.stderr)
        sys.exit(1)
    return key


def get_base_url() -> str:
    url = os.environ.get("DE_BASE_URL", "")
    if not url:
        config = load_config()
        url = config.get("base_url", "http://localhost:8000")
    return url


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL must be an absolute http(s) URL.")
    return base_url.rstrip("/")


def api_request(method: str, path: str, body: Any = None) -> tuple[int, dict[str, Any]]:
    base_url = _validated_base_url(get_base_url())
    api_key = get_api_key()
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "decision-engine-cli/0.1.0",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except Exception:
            return exc.code, {"error": {"message": str(exc)}}


def print_result(
    data: dict[str, Any],
    format: str = "table",
    *,
    rich_enabled: bool = False,
) -> None:
    # Preserve the old helper contract for callers that still pass only
    # (data, format), and degrade to JSON until richer table rendering is
    # intentionally rebuilt in the shared helper layer.
    if format == "json" or not rich_enabled:
        print(json.dumps(data, indent=2, default=str))
        return
    print(json.dumps(data, indent=2, default=str))


def arg_value(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        return None
    return args[idx + 1]


def prompt_text(label: str, default: str | None = None, *, secret: bool = False) -> str:
    prompt = label
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    value = getpass.getpass(prompt) if secret else input(prompt)
    value = value.strip()
    if not value and default is not None:
        return default
    return value


def strip_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}
