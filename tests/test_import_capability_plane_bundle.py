from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "import_capability_plane_bundle.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("capability_plane_import_script_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("capability_plane_import_script_test", module)
    spec.loader.exec_module(module)
    return module


def _payload(org_id: str) -> dict[str, object]:
    binding_id = str(uuid4())
    snapshot_id = str(uuid4())
    outcome_id = str(uuid4())
    return {
        "providers": [
            {
                "provider_id": "provider.skill_pack.import_script",
                "provider_type": "skill_pack",
                "name": "Imported Skill Script Pack",
                "supported_execution_owners": ["client_managed"],
                "profiles": [
                    {
                        "profile_id": "profile.skill_pack.import_script",
                        "provider_id": "provider.skill_pack.import_script",
                        "name": "Imported Script Skills",
                        "default_execution_owner": "client_managed",
                        "binding_scope_default": "user",
                        "supported_binding_scopes": ["user"],
                    }
                ],
            }
        ],
        "bindings": [
            {
                "binding_id": binding_id,
                "org_id": org_id,
                "provider_id": "provider.skill_pack.import_script",
                "profile_id": "profile.skill_pack.import_script",
                "binding_name": "Import Script Binding",
                "scope": "user",
                "scope_ref": "user-script",
                "status": "ready",
                "execution_owner": "client_managed",
                "config": {
                    "manifest": {
                        "capabilities": [
                            {
                                "capability_id": "cap.skill.import_script",
                                "name": "Import Script Skill",
                                "kind": "skill",
                            }
                        ]
                    }
                },
            }
        ],
        "snapshots": [
            {
                "snapshot_id": snapshot_id,
                "binding_id": binding_id,
                "org_id": org_id,
                "manifest_hash": "script-manifest-hash",
                "content_hash": "script-content-hash",
                "manifest": {"capabilities": [{"capability_id": "cap.skill.import_script"}]},
                "discovered_at": "2026-05-29T12:00:00Z",
            }
        ],
        "routing_outcomes": [
            {
                "outcome_id": outcome_id,
                "org_id": org_id,
                "provider_id": "provider.skill_pack.import_script",
                "binding_id": binding_id,
                "capability_id": "cap.skill.import_script",
                "route_request": {"objective": "Use import script skill"},
                "route_plan": {"selected_capability_id": "cap.skill.import_script"},
                "result_status": "completed",
                "success": True,
                "confidence": 0.88,
                "created_at": "2026-05-29T12:00:01Z",
                "updated_at": "2026-05-29T12:00:02Z",
            }
        ],
    }


def test_import_capability_plane_bundle_helpers_parse_and_render() -> None:
    module = _load_module()
    payload_text = '{"providers":[],"bindings":[],"snapshots":[],"routing_outcomes":[]}'

    parsed = module._parse_payload_text(payload_text)
    rendered = module._render_summary(
        module.CapabilityPlaneImportSummary(
            dry_run=True,
            providers_upserted=1,
            profiles_upserted=2,
            bindings_upserted=3,
            snapshots_inserted=4,
            routing_outcomes_inserted=5,
        ),
        output_format="env",
    )

    assert parsed["providers"] == []
    assert "ALGENTA_CAPABILITY_IMPORT_READY=1" in rendered
    assert "CAPABILITY_IMPORT_DRY_RUN=1" in rendered
    assert "CAPABILITY_IMPORT_ROUTING_OUTCOMES_INSERTED=5" in rendered


def test_import_capability_plane_bundle_helpers_reject_invalid_input() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="valid JSON"):
        module._parse_payload_text("{not json}")

    with pytest.raises(ValueError, match="JSON object"):
        module._parse_payload_text("[]")

    with pytest.raises(ValueError, match="payload is empty"):
        module._read_payload_text(None, stdin_text="   ")


@pytest.mark.anyio
async def test_import_capability_plane_bundle_executes_dry_run_with_real_service() -> None:
    module = _load_module()
    from tests.test_capability_plane_importer import _seed_org

    org_id = await _seed_org()
    summary = await module._import_payload(_payload(org_id), dry_run=True)

    assert summary.dry_run is True
    assert summary.providers_upserted == 1
    assert summary.profiles_upserted == 1
    assert summary.bindings_upserted == 1
    assert summary.snapshots_inserted == 1
    assert summary.routing_outcomes_inserted == 1
