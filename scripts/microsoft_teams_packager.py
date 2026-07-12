#!/usr/bin/env python3
"""Package the Microsoft 365 / Teams app zip for the Algenta Decision Agent.

The zip published to the org catalog (``POST /appCatalogs/teamsApps``) is an ordinary
Teams/M365 app package: ``manifest.json`` + color/outline icons + the declarative-agent
files it references (``declarativeAgent.json``, ``apiPlugin.json``). The declarative agent
surfaces in Microsoft 365 Copilot purely because ``manifest.json`` links it via
``copilotAgents.declarativeAgents`` — there is no separate Copilot publish step.

This module is imported by ``deploy_microsoft_turnkey.py`` and is also runnable standalone::

    python scripts/microsoft_teams_packager.py \
        --src integrations/microsoft/copilot-agent \
        --out build/algenta-teams-app.zip \
        --oauth-registration-id <id>

It never mutates the source tree: substitutions (the OAuth ``reference_id`` placeholder and
an optional version bump for catalog updates) are applied to in-zip copies only.
"""
from __future__ import annotations

import argparse
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Files in the source dir that are packaging inputs, not app-package members.
_EXCLUDE_NAMES = {"README.md", ".DS_Store"}
_EXCLUDE_SUFFIXES = {".zip"}

# The Teams Toolkit templating token the built apiPlugin.json carries for the plugin's
# OAuth/SSO registration id. It MUST become a real registration id for the plugin's
# authenticated actions to run in Copilot.
PLUGIN_REF_PLACEHOLDER = "${{OAUTH2_REGISTRATION_ID}}"


@dataclass
class PackageResult:
    zip_path: Path
    manifest_id: str
    version: str
    display_name: str
    # Whether the ${{OAUTH2_REGISTRATION_ID}} placeholder was replaced with a real id. Named
    # generically (not "oauth_*") so static analysis doesn't misclassify this bool as a secret.
    reference_substituted: bool
    members: list[str]


def _iter_member_files(src: Path):
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        if p.name in _EXCLUDE_NAMES or p.suffix in _EXCLUDE_SUFFIXES:
            continue
        yield p


def _bump_patch(version: str) -> str:
    """Increment the trailing numeric component of a dotted version (e.g. 0.1.0 -> 0.1.1)."""
    parts = version.split(".")
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].isdigit():
            parts[i] = str(int(parts[i]) + 1)
            return ".".join(parts)
    return version + ".1"


def build_package(
    src: Path,
    out: Path,
    *,
    oauth_registration_id: Optional[str] = None,
    version_override: Optional[str] = None,
    bump_patch: bool = False,
) -> PackageResult:
    """Build the app-package zip from ``src`` into ``out`` and return metadata.

    - ``oauth_registration_id``: if given, replaces the ``${{OAUTH2_REGISTRATION_ID}}``
      placeholder in every member (in practice apiPlugin.json).
    - ``version_override`` / ``bump_patch``: rewrite manifest.json ``version`` for a catalog
      update (Graph rejects an update whose version is not higher than the published one).
    """
    src = src.resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"source package dir not found: {src}")

    manifest_path = src / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.json missing in {src}")
    manifest = json.loads(manifest_path.read_text())
    manifest_id = manifest.get("id")
    if not manifest_id:
        raise ValueError("manifest.json has no 'id'")

    # Resolve the effective version (bump takes precedence over override if both set).
    version = manifest.get("version", "0.0.0")
    if version_override:
        version = version_override
    if bump_patch:
        version = _bump_patch(version)

    icons = manifest.get("icons", {})
    display_name = (manifest.get("name") or {}).get("short") or manifest_id

    reference_substituted = False
    members: list[str] = []
    out.parent.mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in _iter_member_files(src):
            name = p.name
            if name == "manifest.json":
                m = dict(manifest)
                m["version"] = version
                data = json.dumps(m, indent=2).encode("utf-8")
            elif p.suffix == ".json":
                text = p.read_text()
                if oauth_registration_id and PLUGIN_REF_PLACEHOLDER in text:
                    text = text.replace(PLUGIN_REF_PLACEHOLDER, oauth_registration_id)
                    reference_substituted = True
                data = text.encode("utf-8")
            else:
                data = p.read_bytes()
            zf.writestr(name, data)
            members.append(name)

    # Sanity: the icons the manifest references must be present as members.
    for kind in ("color", "outline"):
        ref = icons.get(kind)
        if ref and ref not in members:
            raise ValueError(f"manifest references {kind} icon '{ref}' but it is not in {src}")

    out.write_bytes(buf.getvalue())
    return PackageResult(
        zip_path=out,
        manifest_id=manifest_id,
        version=version,
        display_name=display_name,
        reference_substituted=reference_substituted,
        members=members,
    )


def _main() -> int:
    ap = argparse.ArgumentParser(description="Package the Algenta M365/Teams app zip.")
    ap.add_argument("--src", default="integrations/microsoft/copilot-agent", type=Path)
    ap.add_argument("--out", default="build/algenta-teams-app.zip", type=Path)
    ap.add_argument("--oauth-registration-id", default=None)
    ap.add_argument("--version", dest="version_override", default=None)
    ap.add_argument("--bump", action="store_true", help="bump the manifest patch version")
    args = ap.parse_args()

    res = build_package(
        args.src,
        args.out,
        oauth_registration_id=args.oauth_registration_id,
        version_override=args.version_override,
        bump_patch=args.bump,
    )
    print(json.dumps(
        {
            "zip": str(res.zip_path),
            "manifest_id": res.manifest_id,
            "version": res.version,
            "display_name": res.display_name,
            "reference_substituted": res.reference_substituted,
            "members": res.members,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
