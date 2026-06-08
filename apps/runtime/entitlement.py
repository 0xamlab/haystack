"""
Entitlement — thin adapter over license.py for use in the gRPC server.

Entitlement = license + runtime permission checks.
License handles storage/JWT; entitlement handles per-call decisions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

_ALL_MODULES = "*"


@dataclass
class Entitlement:
    valid: bool = True
    tier: str = "dev"
    permitted_modules: list[str] = field(default_factory=lambda: [_ALL_MODULES])
    expires_at: int = 0
    message: str = "Dev mode"
    device_id: str = ""
    device_limit: int = 0


def check_entitlement() -> Entitlement:
    """Load current device license and map it to an Entitlement."""
    from apps.runtime.license import load_license

    api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
    lic = load_license(api_key)
    return Entitlement(
        valid=lic.valid,
        tier=lic.plan,
        permitted_modules=lic.permitted_modules,
        expires_at=lic.expires_at,
        message=lic.message or f"plan={lic.plan}",
        device_id=lic.device_id,
        device_limit=lic.device_limit,
    )


def is_module_permitted(module_name: str, entitlement: Entitlement) -> bool:
    if not entitlement.valid:
        return False
    if _ALL_MODULES in entitlement.permitted_modules:
        return True
    return module_name in entitlement.permitted_modules
