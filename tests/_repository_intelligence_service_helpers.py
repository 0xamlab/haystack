"""Shared helper functions + fixtures for test_repository_intelligence_service_* sub-modules.

Extracted from tests/test_repository_intelligence_service.py during modularization.
Each split sub-file does `from tests._repository_intelligence_service_helpers import *`,
which transitively re-exports everything from _repository_intelligence_service_imports.
"""
from tests._repository_intelligence_service_imports import *  # noqa: F401,F403
from tests._repository_intelligence_service_imports import __all__ as _IMPORTS_ALL  # noqa

def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )

def _connector_for_archive(archive_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="repo_archive"),
        config_json=json.dumps({"path": str(archive_path)}),
    )

def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", "Initial commit"], check=True)

def _write_scratch_project(
    path: Path,
    payload: dict[str, Any],
    *,
    extra_assets: dict[str, bytes] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(payload, indent=2, sort_keys=True))
        for asset_path, asset_bytes in sorted((extra_assets or {}).items()):
            archive.writestr(asset_path, asset_bytes)

def _scratch_project_payload() -> dict[str, Any]:
    return {
        "extensions": [],
        "meta": {"agent": "pytest", "semver": "3.0.0", "vm": "0.2.0"},
        "monitors": [],
        "targets": [
            {
                "blocks": {
                    "stage_event": {
                        "fields": {},
                        "inputs": {},
                        "next": "stage_broadcast",
                        "opcode": "event_whenflagclicked",
                        "parent": None,
                        "topLevel": True,
                    },
                    "stage_broadcast": {
                        "fields": {},
                        "inputs": {"BROADCAST_INPUT": [1, [11, "start", "broadcast-id"]]},
                        "next": None,
                        "opcode": "event_broadcast",
                        "parent": "stage_event",
                        "topLevel": False,
                    },
                },
                "broadcasts": {"broadcast-id": "start"},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": True,
                "lists": {},
                "name": "Stage",
                "sounds": [],
                "tempo": 60,
                "variables": {},
                "videoState": "on",
                "videoTransparency": 50,
                "volume": 100,
            },
            {
                "blocks": {
                    "receive": {
                        "fields": {"BROADCAST_OPTION": ["start", "broadcast-id"]},
                        "inputs": {},
                        "next": "call",
                        "opcode": "event_whenbroadcastreceived",
                        "parent": None,
                        "topLevel": True,
                    },
                    "call": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_call",
                        "parent": "receive",
                        "topLevel": False,
                    },
                    "define": {
                        "fields": {},
                        "inputs": {"custom_block": [1, "prototype"]},
                        "next": "say",
                        "opcode": "procedures_definition",
                        "parent": None,
                        "topLevel": True,
                    },
                    "prototype": {
                        "fields": {},
                        "inputs": {},
                        "mutation": {
                            "argumentids": "[]",
                            "proccode": "init",
                            "warp": "false",
                        },
                        "next": None,
                        "opcode": "procedures_prototype",
                        "parent": "define",
                        "topLevel": False,
                    },
                    "say": {
                        "fields": {},
                        "inputs": {"MESSAGE": [1, [10, "ready"]]},
                        "next": None,
                        "opcode": "looks_say",
                        "parent": "define",
                        "topLevel": False,
                    },
                },
                "broadcasts": {},
                "comments": {},
                "costumes": [],
                "currentCostume": 0,
                "isStage": False,
                "lists": {},
                "name": "Cat",
                "size": 100,
                "sounds": [],
                "variables": {},
                "visible": True,
                "volume": 100,
                "x": 0,
                "y": 0,
            },
        ],
    }

def _sample_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "customer-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def handle_request(user):\n    return user.name\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_service.py").write_text(
        "from src.service import handle_request\n\n\ndef test_handle_request_user():\n    assert handle_request(type('User', (), {'name': 'Ada'})()) == 'Ada'\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path

def _sample_archive(tmp_path: Path) -> Path:
    source_path = tmp_path / "archive-source"
    (source_path / "src").mkdir(parents=True)
    (source_path / "src" / "service.py").write_text(
        "def handle_request(user):\n    return user.name\n",
        encoding="utf-8",
    )
    archive_path = tmp_path / "customer-repo.zip"
    with zipfile.ZipFile(archive_path, "w") as handle:
        handle.write(
            source_path / "src" / "service.py",
            arcname="src/service.py",
        )
    return archive_path

def _graph_neighbor_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "graph-neighbor-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "worker.py").write_text(
        "def fragile_helper(value: str) -> str:\n"
        "    return value.strip()\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "main.py").write_text(
        "from src.worker import fragile_helper\n\n"
        "def orchestrate(value: str) -> str:\n"
        "    return fragile_helper(value)\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path

def _literal_mismatch_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "literal-mismatch-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "src" / "service.py").write_text(
        "def normalize_status(status: str) -> str:\n"
        "    lowered = status.strip().lower()\n"
        '    if lowered == "open":\n'
        '        return "closed"\n'
        "    return lowered\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "test_service.py").write_text(
        "from src.service import normalize_status\n\n\n"
        "def test_normalize_status_open() -> None:\n"
        '    assert normalize_status("OPEN") == "open"\n',
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path

def _typescript_rootdir_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "ts-rootdir-repo"
    (repo_path / "services" / "app" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "src").mkdir(parents=True)
    (repo_path / "packages" / "common" / "package.json").write_text(
        '{"name":"@acme/common"}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "src" / "index.ts").write_text(
        "import { shared } from '@acme/common/shared';\n"
        "export const run = (): string => shared();\n",
        encoding="utf-8",
    )
    (repo_path / "packages" / "common" / "src" / "shared.ts").write_text(
        "export function shared(): string {\n"
        "  return 'shared';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.json").write_text(
        '{\n'
        '  "compilerOptions": { "outDir": "dist", "rootDir": "../.." },\n'
        '  "include": ["src"]\n'
        '}\n',
        encoding="utf-8",
    )
    (repo_path / "services" / "app" / "tsconfig.test.json").write_text(
        '{\n'
        '  "extends": "./tsconfig.json",\n'
        '  "compilerOptions": {\n'
        '    "noEmit": true,\n'
        '    "rootDir": ".",\n'
        '    "baseUrl": ".",\n'
        '    "paths": {\n'
        '      "@acme/common": ["../../packages/common/src/index.ts"],\n'
        '      "@acme/common/*": ["../../packages/common/src/*"]\n'
        "    }\n"
        "  },\n"
        '  "include": ["src"]\n'
        "}\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path

def _typescript_barrel_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "ts-barrel-repo"
    (repo_path / "src" / "common").mkdir(parents=True)
    (repo_path / "src" / "app").mkdir(parents=True)
    (repo_path / "src" / "common" / "shared.ts").write_text(
        "export function usefulHelper(): string {\n"
        "  return 'ok';\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "common" / "index.ts").write_text(
        "export { usefulHelper } from './shared';\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "app" / "main.ts").write_text(
        "import { usefulHelper } from '../common';\n"
        "export const run = (): string => usefulHelper();\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    return repo_path

def _decision_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id=uuid.uuid4(),
        engine_version="2026.05.0",
        recommended_action="apply_patch",
        confidence=0.91,
        rationale="Patch simulation satisfies the current execution policy.",
        metrics=MetricsSummary(
            expected_value=84.0,
            median=82.0,
            std_deviation=9.0,
            variance=81.0,
            probability_of_loss=0.08,
            var_95=12.0,
            cvar_95=15.0,
        ),
        percentiles=PercentileSummary(
            p5=-12.0,
            p25=60.0,
            p50=82.0,
            p75=95.0,
            p95=110.0,
        ),
        scenarios_run=5_000,
        execution_ms=11,
        metadata=RunMetadata(
            mode="expert",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


__all__ = list(_IMPORTS_ALL) + [
    "_connector_for_archive",
    "_connector_for_repo",
    "_decision_envelope",
    "_graph_neighbor_repo",
    "_init_git_repo",
    "_literal_mismatch_repo",
    "_sample_archive",
    "_sample_repo",
    "_scratch_project_payload",
    "_typescript_barrel_repo",
    "_typescript_rootdir_repo",
    "_write_scratch_project",
]
