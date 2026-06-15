from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_apacheconf_parser_dispatch as repository_apacheconf_parser_dispatch,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.repository_intelligence_adapters import (
    apacheconf_analysis_support as repository_apacheconf_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    apacheconf_primitives as repository_apacheconf_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "Initial commit"], check=True)


def test_repository_intelligence_apacheconf_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["apacheconf"] is (
        repository_apacheconf_parser_dispatch._parse_apacheconf_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["apacheconf"] is (
        repository_apacheconf_parser_dispatch._parse_apacheconf_dependencies_only
    )


def test_repository_intelligence_apacheconf_helpers_are_modularized() -> None:
    assert repository_service.apacheconf_adapter.strip_comments is (
        repository_apacheconf_primitives.strip_comments
    )
    assert repository_service.apacheconf_adapter.has_apacheconf_path_hints is (
        repository_apacheconf_primitives.has_apacheconf_path_hints
    )
    assert repository_service.apacheconf_adapter.is_probable_apacheconf_source is (
        repository_apacheconf_analysis_support.is_probable_apacheconf_source
    )
    assert repository_service.apacheconf_adapter.module_aliases_for_path is (
        repository_apacheconf_analysis_support.module_aliases_for_path
    )
    assert repository_service.apacheconf_adapter.parse_dependencies_only is (
        repository_apacheconf_analysis_support.parse_dependencies_only
    )
    assert repository_service.apacheconf_adapter.parse_file is (
        repository_apacheconf_analysis_support.parse_file
    )


def test_apacheconf_adapter_module_aliases_include_path_and_define_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "apacheconf-alias-repo"
    (repo_path / "apache2" / "conf-available").mkdir(parents=True)
    (repo_path / "apache2" / "conf-available" / "security.conf").write_text(
        "Define APP_ROOT /srv/www/example\n"
        "<Macro SecureHeaders>\n"
        "  Header always set X-Frame-Options SAMEORIGIN\n"
        "</Macro>\n",
        encoding="utf-8",
    )

    aliases = repository_service.apacheconf_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="apache2/conf-available/security.conf",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "apache2/conf-available/security.conf" in aliases
    assert "security.conf" in aliases
    assert "security" in aliases
    assert "APP_ROOT" in aliases
    assert "SecureHeaders" in aliases


def test_apacheconf_adapter_parse_file_extracts_include_edges_and_macro_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "apache2/apache2.conf",
            "apache2/conf-enabled/security.conf",
            "apache2/sites-enabled/000-default.conf",
        ],
        root_path=Path("/tmp/apacheconf-index"),
    )
    text = (
        "IncludeOptional conf-enabled/*.conf\n"
        "Include sites-enabled/000-default.conf\n"
        "Use SecureHeaders\n"
    )

    symbols, dependencies, references = repository_service.apacheconf_adapter.parse_file(
        "apache2/apache2.conf",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "apache2" for symbol in symbols)
    assert {dependency.target_file for dependency in dependencies} == {
        "apache2/conf-enabled/security.conf",
        "apache2/sites-enabled/000-default.conf",
    }
    assert any(
        reference.target_file == "apache2/conf-enabled/security.conf" for reference in references
    )
    assert any(reference.target_names == ("SecureHeaders",) for reference in references)


def test_apacheconf_language_detection_supports_known_paths_without_overclaiming() -> None:
    assert (
        repository_service._language_for_path(
            Path("apache2/apache2.conf"),
            text="ServerName example.test\nIncludeOptional sites-enabled/*.conf\n",
        )
        == "apacheconf"
    )
    assert (
        repository_service._language_for_path(
            Path("public/.htaccess"),
            text="RewriteEngine On\nRewriteRule ^index\\.php$ - [L]\n",
        )
        == "apacheconf"
    )
    assert (
        repository_service._language_for_path(
            Path("config/dev.conf"),
            text="server_name example.test;\nlocation / { proxy_pass http://app; }\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_apacheconf_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "apacheconf-profile-repo"
    (repo_path / "apache2" / "sites-enabled").mkdir(parents=True)
    (repo_path / "apache2" / "conf-enabled").mkdir(parents=True)
    (repo_path / "public").mkdir(parents=True)
    (repo_path / "apache2" / "apache2.conf").write_text(
        "ServerName example.test\nIncludeOptional conf-enabled/*.conf\nIncludeOptional sites-enabled/*.conf\n",
        encoding="utf-8",
    )
    for index in range(4):
        (repo_path / "apache2" / "conf-enabled" / f"security-{index}.conf").write_text(
            "Header always set X-Frame-Options SAMEORIGIN\n",
            encoding="utf-8",
        )
    for index in range(3):
        (repo_path / "apache2" / "sites-enabled" / f"site-{index}.conf").write_text(
            f"<VirtualHost *:80>\nServerName site-{index}.test\nDocumentRoot /srv/site-{index}\n</VirtualHost>\n",
            encoding="utf-8",
        )
    (repo_path / "public" / ".htaccess").write_text(
        "RewriteEngine On\nRewriteRule ^$ index.php [L]\n",
        encoding="utf-8",
    )
    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["apache2", "public"],
        max_files=128,
    )

    assert "apacheconf" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "apacheconf"


def test_repository_snapshot_graph_contains_apacheconf_include_edges(tmp_path: Path) -> None:
    initialize_pyarrow_parquet_runtime()
    repo_path = tmp_path / "apacheconf-graph-repo"
    (repo_path / "apache2" / "conf-enabled").mkdir(parents=True)
    (repo_path / "apache2" / "apache2.conf").write_text(
        "ServerName example.test\nIncludeOptional conf-enabled/*.conf\n",
        encoding="utf-8",
    )
    (repo_path / "apache2" / "conf-enabled" / "security.conf").write_text(
        "Header always set X-Frame-Options SAMEORIGIN\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)
    connector = _connector_for_repo(repo_path)

    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            focus_paths=["apache2"],
            include_patterns=[
                "apache2/**/*.conf",
                "*.conf",
            ],
            max_files=16,
        ),
    )
    graph_rows = pq.read_table(snapshot.repository_graph_artifact.storage_path).to_pylist()

    assert any(
        str(row["edge_type"]) == "includeoptional"
        and str(row["source_node"]) == "file:apache2/apache2.conf"
        and str(row["target_node"]) == "file:apache2/conf-enabled/security.conf"
        for row in graph_rows
    )
