#!/usr/bin/env python3
"""Generate gitbook/configuration.md from apps/api_server/config.Settings — the source of truth.

The page lists every environment variable the server reads, with its default and aliases, so the
config reference is complete by construction and never drifts from the code.

    python3 scripts/docs/gen_config_reference.py            # write the page
    python3 scripts/docs/gen_config_reference.py --check     # CI: fail if the page is stale

The --check mode regenerates in memory and byte-compares to the committed file (a dropped, renamed,
or duplicated variable changes the output → fails). It also asserts the SOURCE inventory has no
duplicate names and meets a regression floor.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "gitbook", "configuration.md")
FLOOR = 80  # we expect ~100 settings; alert loudly if the parse collapses

# Curated one-line meanings for the operationally relevant variables. The full NAME inventory is
# always complete from the code (and CI-checked); these descriptions enrich the ones that matter.
DESCRIPTIONS = {
    "ALGENTA_API_KEY": "Client bearer credential for the API (set per request, not usually here).",
    "ALGENTA_BASE_URL": "Engine URL for self-hosted clients (absolute, e.g. http://localhost:8000).",
    "ALGENTA_API_PUBLIC_BASE_URL": "Public-facing API base URL (cloud).",
    "ALGENTA_APP_BASE_URL": "Dashboard / console base URL for self-hosted links.",
    "ALGENTA_DEPLOYMENT_MODE": "Privacy/egress profile: saas | vpc | self_hosted | air_gapped | hybrid_provider | local_dev_daemon.",
    "ALGENTA_DISABLE_CLOUD": "Opt out of any cloud integration (self-hosted).",
    "ALGENTA_DISABLE_TELEMETRY": "Disable all outbound/vendor telemetry; keep local audit.",
    "ALGENTA_TELEMETRY_MODE": "Telemetry destination: disabled | local_audit | control_plane_sync.",
    "ALGENTA_METERING_MODE": "Metering destination: disabled | local_audit | control_plane_sync.",
    "ALGENTA_SERVICE_ROLE": "Deployment role: full (default, with engine) | control_plane (engine-free).",
    "ALGENTA_ENFORCE_LICENSE_VALIDATION": "Enable fail-closed license validation on self-hosted deployments.",
    "ALGENTA_REQUIRE_LOCAL_LICENSE": "Require a valid local signed license; disable hosted/dev fallback.",
    "ALGENTA_CONTROL_PLANE_URL": "Control-plane endpoint for satellite deployments.",
    "ALGENTA_ALLOW_OUTBOUND_NETWORK": "Permit egress (default false in air-gapped).",
    "ALGENTA_EGRESS_ALLOWLIST": "Comma-separated allowlist of permitted egress destinations.",
    "ALGENTA_AGENT_CORE_URL": "Optional agent-runtime (sidecar) endpoint.",
    "ALGENTA_MANAGED_LLM": "Enable the pooled managed-LLM provider key (multi-tenant SaaS).",
    "ALGENTA_ENFORCE_STORAGE_CAP": "Enforce the per-org free-tier storage_gb quota (opt-in).",
    "ALGENTA_RUNTIME_LIBRARY_HTTP_API_ENABLED": "Expose the /v1/libraries* runtime-library routes (off by default).",
    "ALGENTA_SIMULATION_PERSIST_TRANSPORT": "Result persistence backend: auto | celery | in_process.",
    "ALGENTA_CONFIG_ENCRYPTION_KEY": "Encrypts per-tenant provider keys at rest — durable secret, never rotate without re-encrypting.",
    "ALGENTA_PRODUCT": "Edition surface to expose (e.g. codna); filters the tool set.",
    "ALGENTA_DEVICE_ID": "Pin a stable device identity for a device-capped key (16-64 chars).",
    "RUNTIME_FALLBACK_MODE": "Engine fallback policy: deny (prod) | allow | auto (dev only).",
    "MOJO_BINARY_PATH": "Path to the compiled Mojo engine binary.",
    "MOJO_POOL_SIZE": "Number of warm Mojo worker processes (default cpu_count - 1).",
    "MOJO_BUILD_MCPU": "Target CPU ISA for the build (e.g. x86-64-v3) — portable binaries, avoids SIGILL.",
    "MOJO_RUNTIME_MODULE_FILTER": "Comma-separated runtime modules to compile in (filtered, smaller build).",
    "MOJO_ALLOW_SUBPROCESS_FALLBACK": "Permit the per-request subprocess path; set false in production.",
    "MOJO_TIMEOUT_SECONDS": "Max execution time for a Mojo computation.",
    "MOJO_MAX_CONCURRENT": "Max concurrent Mojo workers.",
    "DATABASE_URL": "Async PostgreSQL connection string.",
    "DATABASE_URL_SYNC": "Sync PostgreSQL connection string (migrations).",
    "REDIS_URL": "Redis connection (cache / queue / coordination).",
    "JWT_SECRET": "Signing secret for session JWTs.",
    "STRIPE_SECRET_KEY": "Stripe API secret key (billing).",
    "STRIPE_WEBHOOK_SECRET": "Stripe webhook signing secret.",
    "METRICS_SECRET": "Bearer secret guarding the /metrics endpoint.",
}


def _cell(value: str) -> str:
    """Make a value safe inside a markdown table cell."""
    return value.replace("\n", " ").replace("|", "\\|").strip()


# External docs are for customers, not internal devs: drop description sentences that reference
# internal source files, tests, or roadmap status (these leak implementation detail to a public site).
_INTERNAL_MARKERS = ("test_", "apps/", "packages/", "scripts/", "no longer floats", "enforced by", "/ dark", "dark)")


def _sanitize(desc: str) -> str:
    if not desc:
        return ""
    parts = re.split(r"(?<=[.;])\s+", desc)
    kept = [p for p in parts if not any(m in p.lower() for m in _INTERNAL_MARKERS)]
    return " ".join(kept).strip()


# Internal-only, signer-side (license minting) settings — a customer never sets these, so they are
# excluded from the public configuration reference. Match by field-name prefix to be exhaustive.
def _is_internal(field_name: str) -> bool:
    return field_name.startswith(("license_signing", "license_signer"))


def extract() -> list[tuple[str, str, str, str]]:
    from apps.api_server.config import Settings
    from pydantic_core import PydanticUndefined

    rows: list[tuple[str, str, str, str]] = []
    for name, info in Settings.model_fields.items():
        if _is_internal(name):
            continue
        alias = getattr(info, "validation_alias", None)
        if alias is not None and getattr(alias, "choices", None):
            names = [str(c) for c in alias.choices]
        elif alias is not None:
            names = [str(alias)]
        else:
            names = [name.upper()]
        default = info.default
        if default is PydanticUndefined or default is None:
            dflt = ""
        else:
            dflt = str(default)
        if len(dflt) > 40:
            dflt = dflt[:37] + "..."
        desc = _sanitize(DESCRIPTIONS.get(names[0]) or (info.description or "").strip())
        aliases = ", ".join(f"`{a}`" for a in names[1:])
        rows.append((names[0], dflt, _cell(desc), aliases))
    rows.sort(key=lambda r: r[0])
    return rows


def render(rows: list[tuple[str, str, str, str]]) -> str:
    out = [
        "---",
        "icon: gear",
        "description: Every Algenta configuration environment variable in one place, with its default "
        "and any aliases — complete and current.",
        "---",
        "",
        "# Configuration reference",
        "",
        "Every environment variable Algenta reads, with its default and any accepted aliases. Set these "
        "in your shell, your `.env`, or your orchestrator. Names are case-insensitive.",
        "",
        "{% hint style=\"info\" %}",
        "Where a variable has accepted aliases (for example a legacy `DE_` name), they appear in the "
        "Aliases column.",
        "{% endhint %}",
        "",
        "| Variable | Default | Aliases | Description |",
        "| --- | --- | --- | --- |",
    ]
    for primary, dflt, desc, aliases in rows:
        dv = f"`{_cell(dflt)}`" if dflt != "" else "—"
        out.append(f"| `{primary}` | {dv} | {aliases or '—'} | {desc or '—'} |")
    out += [
        "",
        "## Related",
        "",
        "{% content-ref url=\"self-hosting.md\" %}",
        "[self-hosting.md](self-hosting.md)",
        "{% endcontent-ref %}",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    rows = extract()
    names = [r[0] for r in rows]
    dupes = [k for k, c in Counter(names).items() if c > 1]
    assert not dupes, f"duplicate config variables in source: {dupes}"
    assert len(names) >= FLOOR, f"only {len(names)} config vars (< floor {FLOOR}) — source parse broke"
    md = render(rows)
    if "--check" in sys.argv:
        current = open(OUT).read() if os.path.exists(OUT) else ""
        if current != md:
            print("DRIFT: gitbook/configuration.md is stale vs config.py — run `make docs-gen`")
            return 1
        print(f"configuration.md OK ({len(names)} variables)")
        return 0
    open(OUT, "w").write(md)
    print(f"wrote gitbook/configuration.md ({len(names)} variables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
