"""Structural validation of the Microsoft client artifacts (Build order 8).

No M365 toolchain here, so this asserts the manifests are well-formed and carry the fields that
wire them to the Decision API + Entra — enough to catch a broken/renamed field in CI. Live
sideload/validation (office-addin-manifest, Teams admin center) is the owner-gated Phase-0 step.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "integrations" / "microsoft"
EXCEL = ROOT / "excel-addin"
COPILOT = ROOT / "copilot-agent"
M365 = ROOT / "m365-app"

# The shared Entra app used for SSO by both the Copilot API plugin and the Excel add-in.
ENTRA_APP_ID = "3983990d-e9b5-4866-9a43-d52d6e0c20c3"
# The legacy classic-XML Excel add-in id — the unified package must suppress its duplicate button.
LEGACY_EXCEL_ADDIN_ID = "f445f3f1-20ef-469a-a532-056b3f1ab393"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_excel_manifest_is_well_formed_and_sso_wired() -> None:
    tree = ET.parse(EXCEL / "manifest.xml")  # raises on malformed XML
    root = tree.getroot()
    assert root.tag.endswith("OfficeApp")
    xml = (EXCEL / "manifest.xml").read_text(encoding="utf-8")
    # SSO block + task pane source must be present.
    assert "<WebApplicationInfo>" in xml
    assert "access_as_user" in xml
    assert "taskpane.html" in xml


def test_excel_taskpane_targets_the_decision_api() -> None:
    js = (EXCEL / "taskpane.js").read_text(encoding="utf-8")
    for needed in (
        "/v1/decision-cases",
        "/analysis-runs/",
        "/action-plans",
        "/approve",
        "Office.auth.getAccessToken",  # Entra SSO
        "getSelectedRange",  # selection-only
    ):
        assert needed in js, f"taskpane.js missing {needed!r}"
    # never re-expose approval material or overwrite sheets silently
    assert "worksheets" in js


def test_declarative_agent_is_valid_and_safe() -> None:
    da = _load(COPILOT / "declarativeAgent.json")
    assert da["name"] and da["instructions"]
    assert any(a.get("file") == "apiPlugin.json" for a in da["actions"])
    instr = da["instructions"].lower()
    # the governance guardrails must be stated in the agent instructions
    assert "never invent numbers" in instr or "never invent" in instr
    assert "approve" in instr and ("never" in instr)


def test_api_plugin_exposes_only_coarse_ops_not_approval() -> None:
    plug = _load(COPILOT / "apiPlugin.json")
    fns = {f["name"] for f in plug["functions"]}
    assert {"run_decision_analysis", "create_or_update_decision", "get_decision_result"} <= fns
    # approval/execution must NOT be model-callable tools
    assert "approve_decision" not in fns
    assert "execute_approved_plan" not in fns
    assert not any("approve" in n or "execute" in n for n in fns)
    assert plug["runtimes"][0]["type"] == "OpenApi"


def test_teams_manifest_embeds_the_declarative_agent() -> None:
    m = _load(COPILOT / "manifest.json")
    agents = m["copilotAgents"]["declarativeAgents"]
    assert any(a.get("file") == "declarativeAgent.json" for a in agents)
    assert m["manifestVersion"]
    assert "validDomains" in m


# ---- unified M365 package (the one the deployer publishes by default) --------------------
def test_unified_manifest_carries_all_three_surfaces() -> None:
    """The unified package must carry the Copilot agent AND the Excel add-in in one manifest, so a
    single teamsApps publish distributes Teams + Copilot + Excel."""
    m = _load(M365 / "manifest.json")
    # Copilot declarative agent (conversational @Algenta) ...
    agents = m["copilotAgents"]["declarativeAgents"]
    assert any(a.get("file") == "declarativeAgent.json" for a in agents)
    # ... AND the Excel task-pane add-in as an extension, in the SAME manifest.
    exts = m["extensions"]
    assert exts and "workbook" in exts[0]["requirements"]["scopes"]
    assert any(
        rt["code"]["page"] == "https://addin.algenta.ai/taskpane.html"
        for rt in exts[0]["runtimes"]
    )


def test_unified_manifest_sso_uses_shared_entra_app() -> None:
    m = _load(M365 / "manifest.json")
    wai = m["webApplicationInfo"]
    assert wai["id"] == ENTRA_APP_ID
    assert wai["resource"] == f"api://{ENTRA_APP_ID}"


def test_unified_manifest_reuses_the_copilot_app_id() -> None:
    """Same app id as copilot-agent so the deployer's create-or-update updates ONE catalog app
    in place (not a second, competing app)."""
    assert _load(M365 / "manifest.json")["id"] == _load(COPILOT / "manifest.json")["id"]


def test_unified_ribbon_action_is_wired_and_valid_domains() -> None:
    m = _load(M365 / "manifest.json")
    ext = m["extensions"][0]
    runtime_action_ids = {a["id"] for rt in ext["runtimes"] for a in rt["actions"]}
    controls = [
        c
        for rib in ext["ribbons"]
        for tab in rib["tabs"]
        for grp in tab["groups"]
        for c in grp["controls"]
    ]
    assert controls, "unified manifest has no ribbon controls"
    # every button's actionId must resolve to a declared runtime action
    for c in controls:
        assert c["actionId"] in runtime_action_ids, f"dangling actionId {c['actionId']!r}"
    assert {"gateway.algenta.ai", "addin.algenta.ai"} <= set(m["validDomains"])


def test_unified_manifest_suppresses_legacy_xml_duplicate() -> None:
    """alternates.hide must point at the classic-XML add-in id so users don't get two buttons."""
    ext = _load(M365 / "manifest.json")["extensions"][0]
    hidden = [
        alt["hide"]["customOfficeAddin"]["officeAddinId"]
        for alt in ext.get("alternates", [])
        if alt.get("hide", {}).get("customOfficeAddin")
    ]
    assert LEGACY_EXCEL_ADDIN_ID in hidden
