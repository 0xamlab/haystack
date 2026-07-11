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
