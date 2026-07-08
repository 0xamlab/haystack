"""`algenta runtime doctor` — the required diagnostic.

Prints the runtime source / mode / path / platform tag / ABI / license / fallback / tcp-listeners, and
returns a non-zero exit code if the bundled in-process runtime isn't healthy. It NEVER mentions Mojo,
Modular, Docker, or a daemon — the whole point is that the user never learns those exist. This is also the
target of the clean-machine CI contract, which greps this output for the invariant lines.
"""
from __future__ import annotations

import os
import time

from algenta import paths
from algenta.native import loader


def _license_state() -> str:
    lic = paths.license_path()
    if not os.path.exists(lic):
        return "not present (run `algenta login`)"
    try:
        from algenta.runtime import verify

        with open(lic, encoding="utf-8") as fh:
            token = fh.read().strip()
        claims = verify.verify_license(token, now=int(time.time()))
        prod = (claims.get("products") or {}).get("algenta", {})
        return f"valid (tier={prod.get('tier')}, exp={claims.get('exp')})"
    except Exception as exc:  # noqa: BLE001 — VerificationError, missing pubkey, unreadable token
        return f"present but NOT verified ({str(exc).splitlines()[0]})"


def run(_argv: list[str] | None = None) -> int:
    info = loader.info()
    fallback = "denied" if info["fallback"] == "deny" else info["fallback"]
    tcp = "none" if not info["tcp_listeners"] else ", ".join(map(str, info["tcp_listeners"]))

    print("algenta runtime doctor")
    print(f"  runtime source:  {info['runtime_source']}")
    print(f"  mode:            {info['mode']}")
    print(f"  path:            {info['path']}")
    print(f"  platform tag:    {info['platform_tag']}")
    print(f"  package version: {info['package_version']}")
    print(f"  abi (expected):  {info['abi_version_expected']}")
    print(f"  abi (native):    {info['abi_version_native']}")
    print(f"  loaded:          {info['loaded']}")
    print(f"  verified:        {info['verified']}")
    print(f"  fallback:        {fallback}")
    print(f"  tcp listeners:   {tcp}")
    print(f"  license:         {_license_state()}")
    if info.get("error"):
        print(f"  note:            {info['error']}")

    healthy = bool(info["loaded"] and info["verified"] and not info["tcp_listeners"])
    print("  status:          " + ("READY" if healthy else "NOT READY"))
    return 0 if healthy else 1
