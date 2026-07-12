from __future__ import annotations

import getpass
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from apps.operator_http.privacy import (
    operator_private_profile,
    resolve_operator_api_base_url,
    resolve_operator_dashboard_url,
)

CONFIG_DIR = Path(os.environ.get("DE_CONFIG_DIR", Path.home() / ".de"))
CONFIG_FILE = CONFIG_DIR / "config.json"
SECRET_FILE = CONFIG_DIR / "secrets.bin"
SECRET_SERVICE = "decision-engine-cli"  # noqa: S105
API_KEY_ENV_VARS = ("ALGENTA_API_KEY", "DE_API_KEY")
BASE_URL_ENV_VARS = ("ALGENTA_BASE_URL", "DE_BASE_URL", "ALGENTA_API_URL")
APP_BASE_URL_ENV_VARS = ("ALGENTA_APP_BASE_URL", "APP_BASE_URL", "DE_APP_BASE_URL")
_PERSISTED_CONFIG_KEYS = frozenset({"api_key_backend", "base_url"})
_LEGACY_SECRET_CONFIG_KEYS = frozenset({"api_key", "api_key_encryption_key"})


class CredentialStoreError(RuntimeError):
    """The CLI could not access a secure operating-system credential store."""


def _keyring_module():
    import keyring  # type: ignore[import]

    return keyring


def load_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        payload = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"CLI config is unreadable or malformed: {CONFIG_FILE}") from exc
    if not isinstance(payload, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in payload.items()
    ):
        raise ValueError(f"CLI config must be a string-to-string JSON object: {CONFIG_FILE}")
    return payload


def save_config(config: dict[str, str]) -> None:
    unexpected = set(config) - _PERSISTED_CONFIG_KEYS
    if unexpected:
        raise ValueError(f"CLI config contains unsupported keys: {', '.join(sorted(unexpected))}")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    fd, temporary_path = tempfile.mkstemp(dir=CONFIG_DIR, prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, CONFIG_FILE)
    finally:
        Path(temporary_path).unlink(missing_ok=True)


def store_api_key_secure(config: dict[str, str], api_key: str) -> None:
    normalized = api_key.strip()
    if not normalized:
        raise CredentialStoreError("Refusing to store an empty API key.")
    try:
        keyring = _keyring_module()
        keyring.set_password(SECRET_SERVICE, "api_key", normalized)
        if keyring.get_password(SECRET_SERVICE, "api_key") != normalized:
            raise CredentialStoreError(
                "The operating-system credential store did not verify the saved key."
            )
    except Exception as exc:
        if isinstance(exc, CredentialStoreError):
            raise
        raise CredentialStoreError(
            "No secure operating-system credential store is available. "
            "Set ALGENTA_API_KEY or DE_API_KEY in the environment instead."
        ) from exc

    for key in _LEGACY_SECRET_CONFIG_KEYS:
        config.pop(key, None)
    SECRET_FILE.unlink(missing_ok=True)
    config["api_key_backend"] = "keyring"


def load_api_key_from_storage(config: dict[str, str]) -> str:
    backend = config.get("api_key_backend", "")
    if backend != "keyring":
        return ""
    try:
        secret = _keyring_module().get_password(SECRET_SERVICE, "api_key")
        return secret.strip() if secret else ""
    except Exception as exc:
        raise CredentialStoreError(
            "The operating-system credential store is unavailable. "
            "Set ALGENTA_API_KEY or DE_API_KEY in the environment instead."
        ) from exc


def load_env_api_key() -> str:
    for env_var in API_KEY_ENV_VARS:
        key = os.environ.get(env_var, "").strip()
        if key:
            return key
    return ""


def get_api_key() -> str:
    key = load_env_api_key()
    if not key:
        config = load_config()
        try:
            key = load_api_key_from_storage(config)
        except CredentialStoreError as exc:
            print(f"Credential store error: {exc}", file=sys.stderr)
            sys.exit(1)
    if not key:
        print("❌ No API key found. Run: de config set-key <your-key>", file=sys.stderr)
        sys.exit(1)
    return key


def get_base_url() -> str:
    config = load_config()
    saved_base_url = config.get("base_url")
    if private_profile_enabled() and not _explicit_api_origin_configured(saved_base_url=saved_base_url):
        raise ValueError(
            "CLI private profiles require an explicit self-hosted API origin. "
            "Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL or save base_url in CLI config."
        )
    return resolve_operator_api_base_url(
        saved_base_url=saved_base_url,
        surface="CLI",
    )


def private_profile_enabled() -> bool:
    return operator_private_profile()


def get_dashboard_url() -> str:
    config = load_config()
    saved_base_url = config.get("base_url")
    api_origin_configured = _explicit_api_origin_configured(saved_base_url=saved_base_url)
    dashboard_origin_configured = _explicit_dashboard_origin_configured()
    if private_profile_enabled() and not api_origin_configured and not dashboard_origin_configured:
        raise ValueError(
            "CLI private profiles require an explicit self-hosted dashboard or API origin. "
            "Configure ALGENTA_APP_BASE_URL / APP_BASE_URL / DE_APP_BASE_URL or "
            "ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL."
        )
    api_base_url = (
        resolve_operator_api_base_url(
            saved_base_url=saved_base_url,
            surface="CLI",
        )
        if api_origin_configured
        else None
    )
    return resolve_operator_dashboard_url(
        fallback_api_base_url=api_base_url,
        surface="CLI dashboard",
    )


def _explicit_api_origin_configured(*, saved_base_url: str | None) -> bool:
    if saved_base_url and saved_base_url.strip():
        return True
    return any(os.environ.get(key, "").strip() for key in BASE_URL_ENV_VARS)


def _explicit_dashboard_origin_configured() -> bool:
    return any(os.environ.get(key, "").strip() for key in APP_BASE_URL_ENV_VARS)


def _validated_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Base URL must be an absolute http(s) URL.")
    return base_url.rstrip("/")


def _decode_api_json_body(body: bytes) -> Any:
    if not body or not body.strip():
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("CLI API returned a non-JSON success payload.") from exc


def api_request(method: str, path: str, body: Any = None) -> tuple[int, Any]:
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
            return resp.status, _decode_api_json_body(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, _decode_api_json_body(exc.read())
        except Exception:
            return exc.code, {"error": {"message": str(exc)}}


def api_stream_request(method: str, path: str, body: Any = None) -> Iterator[dict[str, Any]]:
    base_url = _validated_base_url(get_base_url())
    api_key = get_api_key()
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "decision-engine-cli/0.1.0",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310
            content_type = resp.headers.get("Content-Type", "")
            if "text/event-stream" not in content_type:
                raise RuntimeError("Expected text/event-stream response for streaming request.")
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    return
                try:
                    parsed = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Received invalid JSON payload from event stream.") from exc
                if not isinstance(parsed, dict):
                    raise RuntimeError("Expected JSON object payload from event stream.")
                yield parsed
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except Exception:
            data = {"error": {"message": str(exc)}}
        raise RuntimeError(json.dumps({"status": exc.code, "body": data}, default=str)) from exc


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
