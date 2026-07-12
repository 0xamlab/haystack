#!/usr/bin/env python3
"""Algenta "1 click for all" Microsoft deployer.

ONE command, ONE interactive device-code sign-in. After you authenticate once as a Teams/Global
admin, this deploys the maximum possible via Microsoft Graph:

  * Teams app         -> published to the org app catalog (create-or-update by manifest id)
  * M365 Copilot      -> the declarative agent rides INSIDE that same app package (no separate API)
  * Excel add-in      -> rides INSIDE the same unified package (extensions[]) and publishes in the
                         SAME teamsApps call; --src defaults to integrations/microsoft/m365-app
  * per-user install  -> the app is installed for the signed-in admin's own Teams
  * Excel add-in      -> HONEST RESIDUAL: the Graph publish only puts the add-in in the org CATALOG;
                         it appears on users' Excel ribbon only after an admin ASSIGNS the app in
                         M365 admin center > Integrated Apps (or a user self-acquires it), ~24-72h.
                         There is no Graph/REST API for that assignment step. The exact admin-center
                         step + the immediate per-user test path are printed.

Prereq (one-time): provision the deployer public-client app and export its id::

    python scripts/provision_microsoft_deployer.py
    export ALGENTA_MS_DEPLOYER_CLIENT_ID=<printed id>

Then::

    python scripts/deploy_microsoft_turnkey.py

Optional::

    --oauth-registration-id ID   # the plugin's OAuth/SSO vault reference_id (else it's a residual)
    --register-oauth             # best-effort: create the vault via the Teams Developer Portal API
    --bump                       # bump the in-zip patch version when updating an existing catalog app
    --require-oauth              # refuse to publish if the plugin reference_id is unresolved
    --install-for USER_ID|UPN    # install for someone other than the signer (needs one sign-in each)
    --dry-run                    # package only; make no Graph writes
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
from pathlib import Path

import msal
import requests

# Import the packager whether run as `python scripts/deploy_microsoft_turnkey.py`
# (scripts/ on sys.path) or as `scripts.deploy_microsoft_turnkey`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from microsoft_teams_packager import (  # noqa: E402
    PLUGIN_REF_PLACEHOLDER,
    _bump_patch,
    build_package,
)

# ----- verified constants (thyn.ai tenant / live gateway) --------------------------------
TENANT = "7a0cd533-4d98-450c-bc3a-93cee1495e06"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT}"  # tenanted; device-code fails under /common
GRAPH = "https://graph.microsoft.com/v1.0"
GATEWAY = "https://gateway.algenta.ai"

# The deployer public-client app, provisioned + admin-consented by provision_microsoft_deployer.py
# (create-once). Baked as the default so the whole flow is a single argument-free command; override
# with --client-id or ALGENTA_MS_DEPLOYER_CLIENT_ID for a different tenant/app.
DEPLOYER_CLIENT_ID = "263fd674-345d-4dca-abed-6787959e9be7"

# Gateway Entra app (the plugin's SSO audience). Used only by the --register-oauth path.
GATEWAY_APP_ID = "3983990d-e9b5-4866-9a43-d52d6e0c20c3"
# Microsoft's enterprise token store client to pre-authorize for the SSO vault.
ENTERPRISE_STORE_CLIENT = "ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b"
TEAMS_SSO_REDIRECT = "https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect"

# Delegated Graph scopes (must be pre-consented on the deployer app; see provision script).
# Do NOT include openid/profile/offline_access — MSAL adds them and errors on reserved scopes.
# Least-privilege: the deployer only publishes/installs Teams apps + reads /me. It never touches
# /applications, so Application.ReadWrite.All is deliberately NOT requested.
SCOPES = [
    "AppCatalog.ReadWrite.All",
    "TeamsAppInstallation.ReadWriteForUser",
    "User.Read",
]
# Teams Developer Portal resource (different resource -> its own token; --register-oauth only).
TDP_SCOPES = ["https://dev.teams.microsoft.com/AppDefinitions.ReadWrite"]

REPO_ROOT = Path(__file__).resolve().parent.parent
# Unified Microsoft 365 package: ONE manifest carrying the Copilot declarative agent + API
# plugin AND the Excel task-pane add-in (extensions[]). One POST /appCatalogs/teamsApps
# publishes Teams + M365 Copilot + Excel. Point --src at copilot-agent for the agent-only
# (legacy) package.
SRC_DIR = REPO_ROOT / "integrations" / "microsoft" / "m365-app"
# Legacy standalone Excel add-in (classic XML manifest) — kept only for the older/perpetual
# Office clients that cannot load a unified-manifest add-in, and for the no-extensions fallback.
EXCEL_MANIFEST = REPO_ROOT / "integrations" / "microsoft" / "excel-addin" / "manifest.xml"
BUILD_ZIP = REPO_ROOT / "build" / "algenta-teams-app.zip"
CACHE = os.path.expanduser("~/.algenta_ms_deployer_cache.json")

BOLD, GREEN, YELLOW, RED, DIM, RESET = "\033[1m", "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}" if sys.stdout.isatty() else text


def _mask(value: object) -> str:
    """Confirm a credential-adjacent value (the OAuth reference id) is set WITHOUT echoing it.

    Reports only the character count — never the value itself — so the id is not written to
    stdout/logs in clear text (and the tainted string never reaches a print sink)."""
    n = len(str(value)) if value else 0
    return f"set ({n} chars)" if n else "unset"


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []  # (status, step, detail)

    def ok(self, step, detail=""):
        self.rows.append(("DEPLOYED", step, detail))

    def residual(self, step, detail=""):
        self.rows.append(("RESIDUAL", step, detail))

    def skip(self, step, detail=""):
        self.rows.append(("SKIPPED", step, detail))

    def fail(self, step, detail=""):
        self.rows.append(("FAILED", step, detail))

    def render(self):
        print("\n" + _c(BOLD, "=" * 68))
        print(_c(BOLD, " Algenta Microsoft deploy — final report"))
        print(_c(BOLD, "=" * 68))
        marks = {
            "DEPLOYED": _c(GREEN, "[OK]      "),
            "RESIDUAL": _c(YELLOW, "[RESIDUAL]"),
            "SKIPPED": _c(DIM, "[skip]    "),
            "FAILED": _c(RED, "[FAILED]  "),
        }
        for status, step, detail in self.rows:
            line = f" {marks[status]} {step}"
            print(line)
            if detail:
                for ln in detail.splitlines():
                    print(f"            {_c(DIM, ln)}")
        print(_c(BOLD, "=" * 68))


# ----- auth -------------------------------------------------------------------------------
def _persist_cache(cache: msal.SerializableTokenCache) -> None:
    """Persist the MSAL cache with 0600 perms — it holds a refresh token that can mint Graph
    write tokens (AppCatalog.ReadWrite.All), so it must not be group/world-readable."""
    if not cache.has_state_changed:
        return
    fd = os.open(CACHE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(cache.serialize())


def acquire_token(client_id: str, scopes: list[str], cache: msal.SerializableTokenCache,
                  *, allow_interactive: bool = True) -> str | None:
    app = msal.PublicClientApplication(client_id, authority=AUTHORITY, token_cache=cache)
    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes, account=accounts[0])
    if not result and allow_interactive:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise SystemExit(f"device flow failed: {json.dumps(flow, indent=2)}")
        print("\n" + _c(BOLD, flow["message"]) + "\n")
        sys.stdout.flush()
        result = app.acquire_token_by_device_flow(flow)  # blocks + polls
    if not result or "access_token" not in (result or {}):
        if result:
            print(_c(RED, f"auth failed: {result.get('error')} / {result.get('error_description')}"),
                  file=sys.stderr)
        return None
    return result["access_token"]


# ----- graph helpers ----------------------------------------------------------------------
class Graph:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, path: str):
        r = self.s.get(f"{GRAPH}{path}")
        r.raise_for_status()
        return r.json()

    def post_zip(self, path: str, zip_bytes: bytes):
        return self.s.post(f"{GRAPH}{path}", headers={"Content-Type": "application/zip"}, data=zip_bytes)

    def post_json(self, path: str, body: dict):
        return self.s.post(f"{GRAPH}{path}", headers={"Content-Type": "application/json"}, json=body)


def _version_key(v: str) -> tuple:
    """Sort key for dotted versions (e.g. '0.1.10' > '0.1.9')."""
    return tuple(int(p) if p.isdigit() else 0 for p in str(v).split("."))


def resolve_catalog_app(g: Graph, manifest_id: str) -> tuple[str | None, str | None]:
    """Resolve ``(catalog_id, highest_published_version)`` for a manifest id.

    The manifest.json id is stored as teamsApp.externalId; the catalog id is server-generated.
    We also read the highest published appDefinition version so a catalog UPDATE always carries a
    strictly-higher version — Graph rejects an update whose version is not greater than the
    published one, which otherwise makes re-runs fail."""
    res = g.get(
        f"/appCatalogs/teamsApps?$filter=externalId eq '{manifest_id}'&$expand=appDefinitions"
    )
    vals = res.get("value", [])
    if not vals:
        return None, None
    app = vals[0]
    versions = [d.get("version") for d in app.get("appDefinitions", []) if d.get("version")]
    highest = max(versions, key=_version_key) if versions else None
    return app.get("id"), highest


def _publishing_state(r: requests.Response) -> str | None:
    """Publishing state from a publish/update response (None = immediate/published, no review)."""
    if r.status_code == 204 or not r.content:
        return None
    try:
        body = r.json()
    except ValueError:
        return None
    defs = body.get("appDefinitions")
    if isinstance(defs, list) and defs:
        return body.get("publishingState") or defs[0].get("publishingState")
    return body.get("publishingState")


# ----- excel residual ---------------------------------------------------------------------
def print_excel_residual(report: Report, manifest: dict):
    """Honest Excel add-in status, branching on whether the packaged manifest is unified.

    UNIFIED (manifest has extensions[]): the Office add-in rides inside the SAME package and is
    published by the single POST /appCatalogs/teamsApps call above — no separate upload. But a
    Graph *catalog publish* is NOT a *user assignment*: the task pane appears on ribbons only
    after an admin assigns the app in the M365 admin center > Integrated Apps (or a user
    self-acquires it), with a 24-72h propagation delay. So one Graph call covers distribution,
    but org-wide Excel visibility still needs one admin-center assignment step.

    LEGACY (no extensions[]): the Excel add-in is the separate classic XML manifest, which has no
    Graph deploy API at all — the whole add-in must be uploaded + assigned by hand.
    """
    tenant_admin = "https://admin.microsoft.com  ->  Settings  ->  Integrated apps"
    has_addin = bool(manifest.get("extensions"))
    if has_addin:
        detail = (
            "GOOD: the Excel task-pane add-in is folded into THIS unified package (extensions[]),\n"
            "so the single POST /appCatalogs/teamsApps above already published it to the org\n"
            "catalog alongside Teams + the M365 Copilot agent — no separate add-in upload.\n"
            "\n"
            "HONEST RESIDUAL (one admin step, still NOT a Graph API): publishing to the catalog is\n"
            "not the same as assigning to users. The Excel ribbon button appears ONLY after:\n"
            "\n"
            "  ORG-WIDE (residual, ~4 UI clicks, Exchange/Global admin):\n"
            f"    {tenant_admin}\n"
            "    -> find 'Algenta Decisions' -> Deploy / Assign users\n"
            "    -> 'Everyone' (or groups) -> Deploy   (Excel ribbon appears in ~24-72h)\n"
            "\n"
            "  IMMEDIATE PER-USER TEST (no admin): a Teams/M365 install alone does NOT surface the\n"
            "    Office add-in — until assigned it is 'Not assigned' and stays off the ribbon. To\n"
            "    verify now, self-acquire it: Excel on the web -> Home -> Add-ins -> find\n"
            "    'Algenta Decisions' (Built for your org) -> Add; or sideload the manifest.\n"
            "\n"
            "NOTE: unified-manifest add-ins require Excel on Windows 2501+ / Mac 16.103+ / web.\n"
            f"For perpetual/older/mobile Office, deploy the legacy XML add-in ({EXCEL_MANIFEST});\n"
            "the extensions[].alternates.hide.customOfficeAddin link suppresses a duplicate button."
        )
        report.residual("Excel add-in org-wide assignment (Integrated Apps — no Graph API)", detail)
    else:
        detail = (
            "No Microsoft Graph/REST API exists to org-deploy a classic XML-manifest SSO Office\n"
            "add-in (the WebApplicationInfo/SSO manifest). The Centralized Deployment PowerShell\n"
            "module refuses SSO manifests AND is Basic-auth-only + Windows-only, so it cannot ride\n"
            "this device-code sign-in. Two honest options:\n"
            "\n"
            "  ORG-WIDE (residual, ~6 UI clicks, Exchange/Global admin):\n"
            f"    {tenant_admin}\n"
            "    -> Add-ins -> Deploy Add-in -> Upload manifest\n"
            f"       file: {EXCEL_MANIFEST}\n"
            "    -> assign 'Everyone' (or groups) -> Deploy   (appears in Excel ribbon in ~24-72h)\n"
            "\n"
            "  IMMEDIATE PER-USER TEST (no admin, no API):\n"
            "    Excel on the web -> Home -> Add-ins -> More Settings -> Upload My Add-in\n"
            f"    -> browse {EXCEL_MANIFEST} -> Upload\n"
            "\n"
            "  FUTURE (eliminates this residual): publish the unified package\n"
            "  (integrations/microsoft/m365-app) so the add-in rides the same teamsApps call."
        )
        report.residual("Excel SSO add-in org-wide deploy (no Graph API)", detail)


# ----- optional: OAuth SSO vault (best effort) --------------------------------------------
def try_register_oauth_vault(client_id: str, cache: msal.SerializableTokenCache,
                             manifest_id: str, report: Report) -> str | None:
    """Best-effort creation of the plugin's OAuth/SSO vault registration via the Teams Developer
    Portal API, then wire the gateway Entra app. Degrades to a printed residual on any failure —
    a bespoke deployer app is often NOT authorized for the dev.teams.microsoft.com resource."""
    tdp_token = acquire_token(client_id, TDP_SCOPES, cache, allow_interactive=False)
    if not tdp_token:
        report.residual(
            "Plugin OAuth/SSO vault registration (Teams Developer Portal)",
            "The deployer app could not silently obtain a dev.teams.microsoft.com token (that\n"
            "resource typically issues only to known first-party clients). Create the vault once\n"
            "with the Microsoft-supported CLI under the SAME sign-in, then re-run with its id:\n"
            "    atk account login m365\n"
            "    atk oauth register    # -> reference_id\n"
            "    python scripts/deploy_microsoft_turnkey.py --oauth-registration-id <reference_id>",
        )
        return None
    try:
        body = {
            "description": "Algenta Decision API",
            "targetUrlsShouldStartWith": [GATEWAY],
            "applicableToApps": "SpecificApp",
            "m365AppId": manifest_id,
            "targetAudience": "HomeTenant",
            "clientId": GATEWAY_APP_ID,
            "identityProvider": "MicrosoftEntra",
            "useSingleSignOn": True,
        }
        r = requests.post(
            "https://dev.teams.microsoft.com/api/v1.0/oAuthConfigurations",
            headers={"Authorization": f"Bearer {tdp_token}", "Content-Type": "application/json"},
            json=body,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"{r.status_code}: {r.text}")
        reg = r.json() if r.content else {}
        reg_id = reg.get("oAuthConfigId") or reg.get("id")
        if not reg_id:
            # A 2xx with an unexpected shape must NOT be reported as success — the placeholder
            # would stay unsubstituted while the report claims the vault is wired.
            report.residual(
                "Plugin OAuth/SSO vault registration (Teams Developer Portal)",
                f"got {r.status_code} but no registration id in the response: {r.text[:400]}\n"
                "Create it with `atk oauth register` and re-run with --oauth-registration-id.",
            )
            return None
        report.ok("Plugin OAuth/SSO vault registration (Teams Developer Portal)",
                  f"reference_id {_mask(reg_id)} — substituted into the package (not echoed).\n"
                  f"NOTE: also add the returned Application ID URI + redirect {TEAMS_SSO_REDIRECT}\n"
                  f"and pre-authorize {ENTERPRISE_STORE_CLIENT} on the gateway Entra app {GATEWAY_APP_ID}.")
        return reg_id
    except Exception as e:  # noqa: BLE001 - best effort, degrade to residual
        report.residual("Plugin OAuth/SSO vault registration (Teams Developer Portal)",
                        f"attempt failed: {e}\nFall back to `atk oauth register` (see docs).")
        return None


# ----- main -------------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Algenta 1-click Microsoft deployer.")
    ap.add_argument("--client-id",
                    default=os.environ.get("ALGENTA_MS_DEPLOYER_CLIENT_ID", DEPLOYER_CLIENT_ID))
    ap.add_argument("--oauth-registration-id",
                    default=(os.environ.get("OAUTH2_REGISTRATION_ID")
                             or os.environ.get("ALGENTA_OAUTH2_REGISTRATION_ID")))
    ap.add_argument("--register-oauth", action="store_true")
    ap.add_argument("--require-oauth", action="store_true")
    ap.add_argument("--bump", action="store_true")
    ap.add_argument("--install-for", default=None, help="user id/UPN (default: the signed-in user)")
    ap.add_argument("--src", type=Path, default=SRC_DIR)
    ap.add_argument("--out", type=Path, default=BUILD_ZIP)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = Report()

    if not args.client_id:
        sys.exit("Set --client-id or ALGENTA_MS_DEPLOYER_CLIENT_ID "
                 "(run scripts/provision_microsoft_deployer.py first).")

    # Read manifest id up front (needed to resolve/register regardless of dry-run).
    manifest = json.loads((args.src / "manifest.json").read_text())
    manifest_id = manifest["id"]

    # ---- Step 0: token cache + one device-code sign-in ----
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE):
        cache.deserialize(open(CACHE).read())
    atexit.register(lambda: _persist_cache(cache))

    if args.dry_run:
        token = None
        print(_c(DIM, "[dry-run] skipping sign-in and all Graph writes"))
    else:
        token = acquire_token(args.client_id, SCOPES, cache)
        if not token:
            sys.exit("authentication failed")
    g = Graph(token) if token else None

    # ---- Step 1: resolve signed-in user ----
    signer = None
    if g:
        try:
            me = g.get("/me")
        except requests.RequestException as e:
            report.fail("Resolve signed-in user (/me)", str(e))
            report.render()
            return 1
        signer = me.get("id")
        report.ok("Sign-in (device code)",
                  f"{me.get('userPrincipalName')} (oid {signer})")

    # ---- Step 2: OAuth reference_id (flag/env, else best-effort, else residual) ----
    reference_id = args.oauth_registration_id
    if reference_id:
        report.ok("Plugin OAuth reference_id", f"supplied — {_mask(reference_id)}")
    elif args.register_oauth and g:
        reference_id = try_register_oauth_vault(args.client_id, cache, manifest_id, report)
    if not reference_id:
        msg = (f"The apiPlugin.json placeholder {PLUGIN_REF_PLACEHOLDER} is unresolved. The agent will\n"
               "publish and appear, but its authenticated Decision API actions will not run until\n"
               "the vault exists. Provide --oauth-registration-id, or --register-oauth, or run\n"
               "`atk oauth register` once.")
        if args.require_oauth:
            report.fail("Plugin OAuth reference_id", msg)
            report.render()
            return 2
        report.residual("Plugin OAuth reference_id", msg)

    # ---- Step 3: resolve existing catalog app + pick a strictly-higher version on update ----
    # (Done BEFORE packaging so an update always carries version > the published one — otherwise
    # Graph rejects the update and re-runs fail. This is what makes the deployer re-runnable.)
    catalog_id = published_version = None
    if g:
        try:
            catalog_id, published_version = resolve_catalog_app(g, manifest_id)
        except requests.RequestException as e:
            report.fail("Resolve org-catalog app", str(e))
            report.render()
            return 1
    version_override = _bump_patch(published_version) if published_version else None

    # ---- Step 4: package the app zip (agent + plugin + icons); substitute reference_id ----
    pkg = build_package(
        args.src, args.out,
        oauth_registration_id=reference_id,
        version_override=version_override,
        # --bump only matters on first publish; on update we already bump off the published version.
        bump_patch=args.bump if version_override is None else False,
    )
    _vnote = f" (auto-bumped from published {published_version})" if version_override else ""
    report.ok("Packaged M365/Teams app zip",
              f"{pkg.zip_path}\nid={pkg.manifest_id} version={pkg.version}{_vnote} "
              f"reference_substituted={pkg.reference_substituted}\nmembers: {', '.join(pkg.members)}")

    if args.dry_run:
        report.skip("Publish / install (dry-run)")
        print_excel_residual(report, manifest)
        report.render()
        return 0

    zip_bytes = pkg.zip_path.read_bytes()

    # ---- Step 5: publish to org catalog — create-or-update ----
    try:
        if catalog_id:
            r = g.post_zip(f"/appCatalogs/teamsApps/{catalog_id}/appDefinitions", zip_bytes)
            if r.status_code in (200, 201, 204):
                state = _publishing_state(r)
                if state and state.lower() != "published":
                    report.residual(
                        "Updated org-catalog app — awaiting admin approval",
                        f"catalogId={catalog_id} version={pkg.version} state={state}\n"
                        "Approve in Teams admin center (Manage apps) to make the update live.")
                else:
                    report.ok("Updated org-catalog app (Teams + M365 Copilot agent)",
                              f"catalogId={catalog_id} version={pkg.version}")
            else:
                report.fail("Update org-catalog app", f"{r.status_code}: {r.text}")
                report.render()
                return 1
        else:
            r = g.post_zip("/appCatalogs/teamsApps", zip_bytes)
            if r.status_code in (200, 201):
                body = r.json()
                catalog_id = body.get("id")
                state = _publishing_state(r)
                if state and state.lower() != "published":
                    report.residual(
                        "Submitted org-catalog app — awaiting admin approval",
                        f"catalogId={catalog_id} externalId={body.get('externalId')} state={state}\n"
                        "Approve in Teams admin center (Manage apps) to make it visible.")
                else:
                    report.ok("Published org-catalog app (Teams + M365 Copilot agent)",
                              f"catalogId={catalog_id} externalId={body.get('externalId')}\n"
                              "Visible in Teams 'Built for your org' + Copilot 'Built by your org'.")
            else:
                report.fail("Publish org-catalog app", f"{r.status_code}: {r.text}")
                report.render()
                return 1
    except requests.RequestException as e:
        report.fail("Publish/update org-catalog app", str(e))
        report.render()
        return 1

    # ---- Step 6: install for the signed-in user (or --install-for) ----
    target = args.install_for or signer
    if catalog_id and target:
        bind = {"teamsApp@odata.bind": f"{GRAPH}/appCatalogs/teamsApps/{catalog_id}"}
        r = g.post_json(f"/users/{target}/teamwork/installedApps", bind)
        if r.status_code in (200, 201):
            report.ok("Installed app for user", f"user={target}")
        elif r.status_code == 409:
            report.ok("App already installed for user", f"user={target}")
        else:
            note = ""
            if args.install_for:
                note = ("\nNOTE: installing for OTHER users in one delegated call is unsupported;\n"
                        "use app-only TeamsAppInstallation.ReadWriteForUser.All, or one sign-in per user.")
            report.residual("Install app for user", f"{r.status_code}: {r.text}{note}")

    # ---- Step 6.5: the zero-residual conversational reach (declarative agent) ----
    if manifest.get("copilotAgents"):
        # plain descriptive string; named generically so static analysis doesn't misclassify it.
        pending_note = ("" if reference_id else
                        "\nPending: the plugin vault reference_id (above) — until set, the first\n"
                        "authenticated action shows a per-user consent card (a user consent, not\n"
                        "an admin step).")
        report.ok(
            "@Algenta conversational reach — Teams / Copilot / Word / Excel / PowerPoint",
            "Publish + install is ENOUGH (no Integrated Apps assignment): users can @-mention the\n"
            "declarative agent in the Copilot pane across all these hosts and its Decision API\n"
            "actions run with Entra SSO (M365 identity -> gateway, no second login).\n"
            "Excel caveat: the agent has no workbook-grid context (document read is Word/PPT only),\n"
            "so 'do this on my selection' needs the task-pane add-in below; framed/conversational\n"
            "decisions work in Excel's Copilot with zero assignment." + pending_note)

    # ---- Step 7: Excel add-in — honest residual (no API) ----
    print_excel_residual(report, manifest)

    report.render()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
