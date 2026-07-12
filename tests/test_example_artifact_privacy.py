from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_BASE_URL = "https://your-algenta-base-url.example"
EXAMPLE_MCP_ENDPOINT = f"{EXAMPLE_BASE_URL}/mcp"


def test_request_templates_use_neutral_placeholder_base_url() -> None:
    for relative_path in (
        "examples/make/contract_request.json",
        "examples/make/openapi_contract_request.json",
        "examples/zapier/contract_request.json",
        "examples/zapier/openapi_contract_request.json",
        "examples/power-automate/contract_request.json",
        "examples/power-automate/openapi_contract_request.json",
    ):
        payload = json.loads((ROOT / relative_path).read_text())
        assert payload["url"].startswith(EXAMPLE_BASE_URL)
        assert payload["headers"]["Authorization"] == "Bearer <YOUR_ALGENTA_API_KEY>"


def test_n8n_workflows_use_placeholder_base_url_and_privacy_guidance() -> None:
    for relative_path in (
        "examples/n8n/workflow_contract.json",
        "examples/n8n/workflow_simulate.json",
        "examples/n8n/workflow_query_batch.json",
        "examples/n8n/workflow_sql_report.json",
    ):
        workflow = json.loads((ROOT / relative_path).read_text())
        http_nodes = [
            node
            for node in workflow["nodes"]
            if node.get("type") == "n8n-nodes-base.httpRequest"
        ]
        assert http_nodes
        for node in http_nodes:
            assert EXAMPLE_BASE_URL in node["parameters"]["url"]
        assert "Replace https://your-algenta-base-url.example" in workflow["_comment"]
        assert "Private profiles do not silently fall back to Algenta cloud." in workflow[
            "_comment"
        ]
        assert "Bearer <YOUR_ALGENTA_API_KEY>" in workflow["_comment"]


def test_chatgpt_actions_template_uses_placeholder_server() -> None:
    payload = yaml.safe_load((ROOT / "examples/chatgpt-actions/openapi_actions.yaml").read_text())

    assert payload["servers"][0]["url"] == EXAMPLE_BASE_URL
    assert payload["x-canonical-mcp-endpoint"] == EXAMPLE_MCP_ENDPOINT
    assert "Replace with Cloud Managed https://api.algenta.ai" in payload["servers"][0][
        "description"
    ]
    assert "Private profiles do not silently fall back to Algenta cloud." in payload["servers"][0][
        "description"
    ]


def test_power_automate_connector_uses_placeholder_host() -> None:
    payload = json.loads((ROOT / "examples/power-automate/connector_definition.json").read_text())

    assert payload["host"] == "your-algenta-base-url.example"
    assert payload["x-canonical-mcp-endpoint"] == EXAMPLE_MCP_ENDPOINT
    assert "Replace your-algenta-base-url.example with Cloud Managed https://api.algenta.ai" in payload[
        "info"
    ]["description"]
    assert "Private profiles do not silently fall back to Algenta cloud." in payload["info"][
        "description"
    ]


def test_google_colab_notebook_uses_placeholder_base_url() -> None:
    payload = json.loads((ROOT / "examples/google-colab/algenta_decision_engine.ipynb").read_text())
    notebook_text = "\n".join("".join(cell.get("source", [])) for cell in payload["cells"])

    assert 'BASE_URL = "https://your-algenta-base-url.example"' in notebook_text
    assert 'API_KEY = "<YOUR_ALGENTA_API_KEY>"' in notebook_text
    assert "Private profiles do not silently fall back to Algenta cloud." in notebook_text
    assert "Use https://app.algenta.ai/dashboard/api-keys only in Cloud Managed." in notebook_text
    assert "self-hosted operator deployment" in notebook_text
    assert "Cloud Managed only; use a self-hosted-issued key in private profiles" in notebook_text
    assert "de_live_YOUR_KEY_HERE" not in notebook_text
