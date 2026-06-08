"""Tests for repository_intelligence_real_repo_probe: candidate_ecosystems_b.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_candidate_ecosystems_for_path_identifies_eiffel_configs_and_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-candidate-ecosystems-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "system.ecf").write_text(
        '<?xml version="1.0"?>\n'
        '<system name="demo">\n'
        '  <target name="demo">\n'
        '    <root class="APPLICATION" feature="make"/>\n'
        '    <cluster name="src" location="src"/>\n'
        "  </target>\n"
        "</system>\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("system.ecf", repo_path=repo_path) == {
        "eiffel"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "src/application.e",
        repo_path=repo_path,
    ) == {"eiffel"}


def test_candidate_ecosystems_for_path_identifies_odin_configs_and_sources(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "odin-candidate-ecosystems-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "ols.json").write_text(
        '{"profile":"default","profiles":[{"name":"default","checker_path":["src"]}]}\n',
        encoding="utf-8",
    )
    (repo_path / "src" / "main.odin").write_text(
        'package main\n\nimport "core:fmt"\n\nmain :: proc() {\n    fmt.println("ok")\n}\n',
        encoding="utf-8",
    )

    assert probe_module._candidate_ecosystems_for_path("ols.json", repo_path=repo_path) == {
        "odin"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "src/main.odin",
        repo_path=repo_path,
    ) == {"odin"}


