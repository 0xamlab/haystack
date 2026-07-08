"""algenta login — one-command onboarding for external users.

`algenta login` authenticates via the shared accounts portal (OAuth 2.0 device grant, RFC 8628), creates a
free Algenta API key (products/algenta/onboard), registers this device, and receives a platform-signed
offline license. After that, Algenta runs fully offline — the native runtime is ALREADY bundled in the
installed wheel, so unlike telys there is NO runtime download step; the loader just verifies + loads it.

Two secrets, distinct roles:
  - API key   — rotatable; control-plane auth for device registration / license renewal.
  - license   — RS256, product-scoped (products.algenta) + device-scoped; lets the bundled runtime run offline.

Hosts are env-overridable (ALGENTA_ACCOUNTS_URL / ALGENTA_API_URL) so the whole flow is testable against a
local mock. Stdlib urllib only (no new deps); cryptography (already a dep via the SDK) for the device keypair.
Mirrors telys-sdk telys/login.py.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from algenta import paths

_CLIENT_ID = "algenta-cli"
_MAX_RESP_BYTES = 1 << 20  # control-plane JSON is tiny; cap defensively


class LoginError(RuntimeError):
    """A step of the login/onboarding flow failed."""


# ── device identity: a stable id + an Ed25519 keypair whose thumbprint binds the license to this machine ──
def device_id() -> str:
    p = paths.device_id_path()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            existing = fh.read().strip()
        if existing:
            return existing
    value = uuid.uuid4().hex
    _cache(p, value)
    return value


def _load_or_make_device_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    p = paths.device_key_path()
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return serialization.load_pem_private_key(fh.read(), password=None)
    key = ed25519.Ed25519PrivateKey.generate()
    os.makedirs(paths.algenta_home(), exist_ok=True)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with open(p, "wb") as fh:
        fh.write(pem)
    os.chmod(p, 0o600)
    return key


def device_thumbprint() -> str:
    """``ed25519:<b64url(sha256(raw_pub))>`` — matches the control plane's device-binding format."""
    from cryptography.hazmat.primitives import serialization

    raw = _load_or_make_device_key().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return "ed25519:" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()


def _hostname_hash() -> str:
    import socket

    return hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()


def _cache(path: str, value: str) -> None:
    os.makedirs(paths.algenta_home(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(value.strip() + "\n")
    os.chmod(path, 0o600)


# ── HTTP (stdlib; small JSON; Bearer) ─────────────────────────────────────────────────────────────────
def _request(method: str, url: str, *, bearer: str | None = None, body: dict | None = None,
             timeout: float = 30.0) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310 (https only below)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(_MAX_RESP_BYTES + 1)
            status = resp.status
    except urllib.error.HTTPError as e:  # 4xx/5xx — device-flow signals errors here
        raw = b""
        try:
            raw = e.read(_MAX_RESP_BYTES + 1)
        except Exception:  # noqa: BLE001
            pass
        status = e.code
    except urllib.error.URLError as e:
        raise LoginError(f"{method} {url}: {e.reason}") from e
    if len(raw) > _MAX_RESP_BYTES:
        raise LoginError(f"{url}: response too large")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    return status, (payload if isinstance(payload, dict) else {})


# ── OAuth 2.0 device authorization grant (RFC 8628) ─────────────────────────────────────────────────────
def device_authorize(*, accounts: str, open_browser: bool = True, max_wait: float = 300.0) -> str:
    _, start = _request("POST", f"{accounts}/oauth/device/code",
                        body={"client_id": _CLIENT_ID, "scope": "algenta"})
    device_code = start.get("device_code")
    user_code = start.get("user_code")
    verify = start.get("verification_uri_complete") or start.get("verification_uri")
    interval = float(start.get("interval") or 5)
    if not (device_code and user_code and verify):
        raise LoginError("accounts device-code response missing fields")
    print(f"\n  Open {verify}\n  and enter code:  {user_code}\n")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(verify)
        except Exception:  # noqa: BLE001 — headless boxes have no browser; the code is printed above
            pass
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(interval)
        status, tok = _request("POST", f"{accounts}/oauth/device/token",
                               body={"client_id": _CLIENT_ID, "device_code": device_code,
                                     "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        access = tok.get("access_token")
        if access:
            return access
        error = tok.get("error")
        if error in ("authorization_pending", "slow_down") or status in (400, 428):
            continue
        raise LoginError(f"device authorization failed: {error or f'HTTP {status}'}")
    raise LoginError("timed out waiting for device authorization")


# ── control-plane calls (match the engine: POST /v1/products/algenta/onboard, POST /v1/device/register) ──
def create_api_key(*, api: str, access_token: str) -> str:
    # Supabase-JWT entry point: the generic product-onboard route resolves-or-creates the org on the free
    # algenta_free tier (so the device license carries products.algenta) AND mints the first API key.
    # (POST /v1/api-keys does NOT accept a Supabase JWT — it needs an existing key — hence a dedicated route.)
    status, resp = _request("POST", f"{api}/v1/products/algenta/onboard", bearer=access_token,
                            body={"name": "algenta-cli"})
    key = resp.get("raw_key") or resp.get("key") or resp.get("api_key")
    if status >= 400 or not key:
        raise LoginError(f"could not create API key (HTTP {status})")
    return key


def register_device(*, api: str, api_key: str) -> str:
    status, resp = _request("POST", f"{api}/v1/device/register", bearer=api_key,
                            body={"device": {"device_id": device_id(),
                                             "device_pubkey_thumbprint": device_thumbprint(),
                                             "platform": paths.platform_tag(),
                                             "hostname_hash": _hostname_hash()}})
    license_token = resp.get("license_token") or resp.get("license")
    if status >= 400 or not license_token:
        detail = (resp.get("error") or {}).get("message") if isinstance(resp, dict) else None
        raise LoginError(f"device registration failed (HTTP {status})" + (f": {detail}" if detail else ""))
    return license_token


# ── orchestration: the whole `algenta login` in one call ────────────────────────────────────────────────
def login(*, access_token: str | None = None, open_browser: bool = True) -> dict:
    """Authenticate + provision. The native runtime is already bundled in the wheel, so there is NO download
    step — after login the local runtime just verifies + loads. Returns a small summary."""
    accounts, api = paths.accounts_url(), paths.api_url()
    token = access_token or os.environ.get("ALGENTA_TOKEN")
    if token:
        print("using supplied token (headless)")
    else:
        print(f"authenticating via {accounts} …")
        token = device_authorize(accounts=accounts, open_browser=open_browser)
    _cache(paths.token_path(), token)

    print("creating your Algenta API key …")
    api_key = create_api_key(api=api, access_token=token)
    _cache(paths.api_key_path(), api_key)

    print("registering this device …")
    license_token = register_device(api=api, api_key=api_key)
    _cache(paths.license_path(), license_token)

    print("\n  ✓ algenta login complete — Algenta now runs fully offline (no network at run time).\n")
    return {
        "device_id": device_id(),
        "api_key_prefix": (api_key.split("_", 1)[0] + "_…") if "_" in api_key else api_key[:6] + "…",
        "license_path": paths.license_path(),
    }
