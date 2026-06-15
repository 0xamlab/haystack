"""Tests for repository_intelligence_real_repo_probe: operational_seed_f.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from apps.api_server.services.repository_intelligence_adapters import (
    shaderlab_primitives as repository_shaderlab_primitives,
)
from benchmarks import (
    repository_intelligence_real_repo_probe_profile_languages_support as profile_languages_support,
)
from benchmarks import repository_intelligence_real_repo_probe_seed_plan_dispatch_support as dispatch_support
from benchmarks.repository_intelligence_real_repo_probe_profile_policy_shader_candidates_support import (
    _shaderlab_profile_hints_from_candidates,
)

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_operational_seed_plan_without_diagnostics_uses_eiffel_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "eiffel-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
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
        "inherit\n"
        "    HELPER\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        local\n"
        "            helper: HELPER\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "helper.e").write_text(
        "class HELPER\n"
        "feature\n"
        "    assist\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "application_test.e").write_text(
        "class APPLICATION_TEST\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["eiffel"]
    assert seed_plan["operational_ecosystems"] == ["eiffel"]
    assert "system.ecf" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/application.e" in seed_plan["entrypoint_files"]
    assert "src/helper.e" in seed_plan["candidate_file_paths"]
    assert "tests/application_test.e" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_prefers_eiffel_candidates_in_mixed_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "mixed-eiffel-profile-repo"
    (repo_path / "08_tex").mkdir(parents=True)
    (repo_path / "14_cuda").mkdir(parents=True)
    (repo_path / "18_eiffel" / "18a").mkdir(parents=True)
    (repo_path / "18_eiffel" / "18b").mkdir(parents=True)
    (repo_path / "08_tex" / "08a.tex").write_text(
        "\\begin{document}\\ntex\\n\\end{document}\\n",
        encoding="utf-8",
    )
    (repo_path / "14_cuda" / "14a.cu").write_text(
        "__global__ void run() {}\n",
        encoding="utf-8",
    )
    (repo_path / "18_eiffel" / "18a" / "main.e").write_text(
        "class MAIN\n"
        "inherit\n"
        "    STATE\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "18_eiffel" / "18a" / "state.e").write_text(
        "class STATE\nend\n",
        encoding="utf-8",
    )
    (repo_path / "18_eiffel" / "18b" / "main.e").write_text(
        "class MAIN\n"
        "inherit\n"
        "    STATE\n"
        "create\n"
        "    make\n"
        "feature\n"
        "    make\n"
        "        do\n"
        "        end\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "18_eiffel" / "18b" / "state.e").write_text(
        "class STATE\nend\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["operational_ecosystems"][0] == "eiffel"
    assert "18_eiffel/18a/main.e" in seed_plan["entrypoint_files"]
    assert "18_eiffel/18a" in seed_plan["support_roots"]


def test_operational_seed_plan_without_diagnostics_limits_eiffel_manifest_hint_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-many-manifests-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )
    manifest_count = dispatch_support._EIFFEL_PROFILE_HINT_MANIFEST_LIMIT + 12
    for index in range(manifest_count):
        manifest_dir = repo_path / "projects" / f"p{index:03d}" / "config"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "system.ecf").write_text(
            '<?xml version="1.0"?>\n'
            '<system name="demo">\n'
            '  <target name="demo">\n'
            '    <root class="APPLICATION" feature="make"/>\n'
            '    <cluster name="src" location="../../../src"/>\n'
            "  </target>\n"
            "</system>\n",
            encoding="utf-8",
        )

    call_count = {"value": 0}

    def _stubbed_eiffel_profile_hints(
        repo_path_arg: Path,
        candidate_path: str,
    ) -> tuple[set[str], set[str], set[str]]:
        call_count["value"] += 1
        return {"src/application.e"}, {"src"}, {candidate_path}

    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints",
        _stubbed_eiffel_profile_hints,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert seed_plan["operational_ecosystems"][0] == "eiffel"
    assert call_count["value"] == dispatch_support._EIFFEL_PROFILE_HINT_MANIFEST_LIMIT


def test_operational_seed_plan_without_diagnostics_stops_stalled_eiffel_manifest_hint_expansion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "eiffel-stalled-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "application.e").write_text(
        "class APPLICATION\ncreate make\nfeature\n    make\n        do\n        end\nend\n",
        encoding="utf-8",
    )

    manifest_count = dispatch_support._EIFFEL_PROFILE_HINT_STALL_LIMIT + 12
    for index in range(manifest_count):
        manifest_dir = repo_path / "projects" / f"p{index:03d}" / "config"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "system.ecf").write_text(
            '<?xml version="1.0"?>\n'
            '<system name="demo">\n'
            '  <target name="demo">\n'
            '    <root class="APPLICATION" feature="make"/>\n'
            '    <cluster name="src" location="../../../src"/>\n'
            "  </target>\n"
            "</system>\n",
            encoding="utf-8",
        )

    call_count = {"value": 0}

    def _stubbed_eiffel_profile_hints(
        repo_path_arg: Path,
        candidate_path: str,
    ) -> tuple[set[str], set[str], set[str]]:
        call_count["value"] += 1
        return {"src/application.e"}, {"src"}, {candidate_path}

    monkeypatch.setattr(
        probe_module,
        "_eiffel_profile_hints",
        _stubbed_eiffel_profile_hints,
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=256,
    )

    assert seed_plan["operational_ecosystems"][0] == "eiffel"
    assert call_count["value"] == dispatch_support._EIFFEL_PROFILE_HINT_STALL_LIMIT + 1


def test_dispatch_basenames_to_ecosystem_reuses_nearest_moonbit_module_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "moonbit-dispatch-reuse-repo"
    (repo_path / "app").mkdir(parents=True)
    (repo_path / "math").mkdir(parents=True)
    (repo_path / "moon.mod").write_text('name = "moonbit/core"\n', encoding="utf-8")
    (repo_path / "app" / "moon.pkg").write_text("", encoding="utf-8")
    (repo_path / "math" / "moon.pkg").write_text("", encoding="utf-8")

    seen_manifest_paths: list[str] = []

    monkeypatch.setattr(
        probe_module,
        "_moonbit_profile_candidate_paths",
        lambda repo_path, manifest_path, max_files: [manifest_path],
    )

    def _stubbed_moonbit_profile_hints_from_candidates(
        repo_path: Path,
        candidate_file_paths: list[str],
        *,
        manifest_path: str,
    ) -> tuple[set[str], set[str], set[str]]:
        seen_manifest_paths.append(manifest_path)
        return (
            {"app/app.mbt"},
            {"app", "math"},
            {"moon.mod", "app/moon.pkg", "math/moon.pkg"},
        )

    monkeypatch.setattr(
        probe_module,
        "_moonbit_profile_hints_from_candidates",
        _stubbed_moonbit_profile_hints_from_candidates,
    )

    state = probe_module._SeedPlanState(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
        discovered_config_paths=["app/moon.pkg", "math/moon.pkg", "moon.mod"],
    )

    dispatch_support.dispatch_basenames_to_ecosystem(state)

    assert seen_manifest_paths == ["moon.mod"]
    assert "moonbit" in state.detected_ecosystems
    assert state.entrypoint_candidates == {"app/app.mbt"}
    assert state.support_root_candidates == {"app", "math"}
    assert state.config_path_candidates == {"moon.mod", "app/moon.pkg", "math/moon.pkg"}


def test_operational_seed_plan_without_diagnostics_uses_puppet_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-profile-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "init.pp").write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "manifests" / "params.pp").write_text(
        "class apache::params { }\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "init.pp").write_text(
        "class apache::tests { }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["puppet"]
    assert seed_plan["operational_ecosystems"] == ["puppet"]
    assert "metadata.json" in seed_plan["config_paths"]
    assert "manifests" in seed_plan["support_roots"]
    assert "manifests/init.pp" in seed_plan["entrypoint_files"]
    assert "manifests/params.pp" in seed_plan["candidate_file_paths"]
    assert "tests/init.pp" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_puppet_profile_in_git_repo(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "puppet-profile-git-repo"
    (repo_path / "manifests").mkdir(parents=True)
    (repo_path / "plans").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "metadata.json").write_text(
        '{"name":"acme-apache","issues_url":"https://example.com/issues"}\n',
        encoding="utf-8",
    )
    (repo_path / "manifests" / "init.pp").write_text(
        "class apache {\n"
        "  include apache::params\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "plans" / "init.pp").write_text(
        "plan apache::init {\n"
        "  notify('hello')\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "init.pp").write_text(
        "class apache::tests { }\n",
        encoding="utf-8",
    )
    _init_git_repo(repo_path)

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["puppet"]
    assert "metadata.json" in seed_plan["config_paths"]
    assert "manifests/init.pp" in seed_plan["entrypoint_files"]
    assert "plans/init.pp" in seed_plan["entrypoint_files"]
    assert "tests/init.pp" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_agda_library_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-profile-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Main.agda").write_text(
        "module Tests.Main where\n\nmain : Set\nmain = Set\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["agda"]
    assert seed_plan["operational_ecosystems"] == ["agda"]
    assert "standard-library.agda-lib" in seed_plan["config_paths"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.agda" in seed_plan["entrypoint_files"]
    assert "src/Data/Helper.agda" in seed_plan["candidate_file_paths"]
    assert "tests/Main.agda" not in seed_plan["entrypoint_files"]


def test_agda_profile_hints_return_entrypoints_without_missing_deferred_probe_helper(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "agda-profile-hints-repo"
    (repo_path / "src" / "Data").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "standard-library.agda-lib").write_text(
        "name: demo\ninclude: src\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.agda").write_text(
        "module Main where\n\n"
        "open import Data.Helper using (helper)\n\n"
        "main : Set\n"
        "main = helper\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Data" / "Helper.agda").write_text(
        "module Data.Helper where\n\n"
        "helper : Set\n"
        "helper = Set\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Main.agda").write_text(
        "module Tests.Main where\n\nmain : Set\nmain = Set\n",
        encoding="utf-8",
    )

    entrypoints, support_roots, config_paths = profile_languages_support._agda_profile_hints(
        repo_path,
        "standard-library.agda-lib",
    )

    assert "standard-library.agda-lib" in config_paths
    assert "src" in support_roots
    assert "src/Main.agda" in entrypoints
    assert "tests/Main.agda" not in entrypoints


def test_operational_seed_plan_without_diagnostics_uses_idris_ipkg_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "idris-profile-repo"
    (repo_path / "src" / "Demo").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "demo.ipkg").write_text(
        "package demo\n"
        "sourcedir = src\n"
        "modules = Demo.Helper\n"
        "main = Main\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Main.idr").write_text(
        "module Main\n\n"
        "import Demo.Helper\n\n"
        "main : IO ()\n"
        "main = renderJson\n",
        encoding="utf-8",
    )
    (repo_path / "src" / "Demo" / "Helper.idr").write_text(
        "module Demo.Helper\n\n"
        "renderJson : IO ()\n"
        "renderJson = pure ()\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "Main.idr").write_text(
        "module Tests.Main\n\n"
        "testMain : IO ()\n"
        "testMain = pure ()\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["idris"]
    assert seed_plan["operational_ecosystems"] == ["idris"]
    assert seed_plan["config_paths"] == ["demo.ipkg"]
    assert "src" in seed_plan["support_roots"]
    assert "src/Main.idr" in seed_plan["entrypoint_files"]
    assert "src/Demo/Helper.idr" in seed_plan["candidate_file_paths"]
    assert "tests/Main.idr" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_raku_meta6_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "raku-profile-repo"
    (repo_path / "lib" / "Demo").mkdir(parents=True)
    (repo_path / "bin").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "META6.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "provides": {"Demo::Helper": "lib/Demo/Helper.rakumod"},
                "bin": ["demo.raku"],
            }
        ),
        encoding="utf-8",
    )
    (repo_path / "lib" / "Demo" / "Helper.rakumod").write_text(
        "unit module Demo::Helper;\n\nsub render-json() is export { \"{}\" }\n",
        encoding="utf-8",
    )
    (repo_path / "bin" / "demo.raku").write_text(
        "use Demo::Helper;\n\nsub main() {\n    Demo::Helper::render-json();\n}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "demo.raku").write_text(
        "sub test-main() { }\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["raku"]
    assert seed_plan["operational_ecosystems"] == ["raku"]
    assert seed_plan["config_paths"] == ["META6.json"]
    assert any(root in seed_plan["support_roots"] for root in {"lib", "lib/Demo"})
    assert "bin" in seed_plan["support_roots"]
    assert "bin/demo.raku" in seed_plan["entrypoint_files"]
    assert "tests/demo.raku" not in seed_plan["entrypoint_files"]
    assert "lib/Demo/Helper.rakumod" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_nushell_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "nushell-profile-repo"
    (repo_path / "modules").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "main.nu").write_text(
        "source modules/helper.nu\n\n"
        "def main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "helper.nu").write_text(
        "export def render-json [] {\n"
        "  '{}'\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main.nu").write_text(
        "def test-main [] {\n"
        "  render-json\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["nushell"]
    assert seed_plan["operational_ecosystems"] == ["nushell"]
    assert "modules" in seed_plan["support_roots"]
    assert "main.nu" in seed_plan["entrypoint_files"]
    assert "tests/main.nu" not in seed_plan["entrypoint_files"]
    assert "modules/helper.nu" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_fish_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "fish-profile-repo"
    (repo_path / "functions").mkdir(parents=True)
    (repo_path / "conf.d").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "main.fish").write_text(
        "source functions/helper.fish\n\n"
        "function main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "functions" / "helper.fish").write_text(
        "function helper\n"
        "    echo '{}'\n"
        "end\n",
        encoding="utf-8",
    )
    (repo_path / "conf.d" / "init.fish").write_text("helper\n", encoding="utf-8")
    (repo_path / "tests" / "main.fish").write_text(
        "function test_main\n"
        "    helper\n"
        "end\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["fish"]
    assert seed_plan["operational_ecosystems"] == ["fish"]
    assert "functions" in seed_plan["support_roots"]
    assert "main.fish" in seed_plan["entrypoint_files"]
    assert "conf.d/init.fish" in seed_plan["entrypoint_files"]
    assert "tests/main.fish" not in seed_plan["entrypoint_files"]
    assert "functions/helper.fish" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_rego_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "rego-profile-repo"
    (repo_path / "policy" / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "policy" / "main.rego").write_text(
        "package policy.main\n\n"
        "import data.policy.lib.helpers as helper\n\n"
        "allow if {\n"
        "    helper.render_json\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "policy" / "lib" / "helpers.rego").write_text(
        "package policy.lib.helpers\n\n"
        "render_json if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "policy_test.rego").write_text(
        "package policy.test\n\n"
        "test_allow if {\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["rego"]
    assert seed_plan["operational_ecosystems"] == ["rego"]
    assert "policy/main.rego" in seed_plan["entrypoint_files"]
    assert "policy/lib" in seed_plan["support_roots"]
    assert "policy/lib/helpers.rego" in seed_plan["candidate_file_paths"]
    assert "tests/policy_test.rego" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_yara_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "yara-profile-repo"
    (repo_path / "rules" / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "rules" / "index.yar").write_text(
        'include "./main.yar"\n'
        'include "./lib/helper.yar"\n',
        encoding="utf-8",
    )
    (repo_path / "rules" / "main.yar").write_text(
        "rule main_rule {\n"
        "  condition:\n"
        "    helper_rule\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "rules" / "lib" / "helper.yar").write_text(
        "private rule helper_rule {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "rules_test.yar").write_text(
        "rule rules_test {\n"
        "  condition:\n"
        "    true\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["yara"]
    assert seed_plan["operational_ecosystems"] == ["yara"]
    assert "rules/index.yar" in seed_plan["entrypoint_files"]
    assert "rules/lib" in seed_plan["support_roots"]
    assert "rules/lib/helper.yar" in seed_plan["candidate_file_paths"]
    assert "tests/rules_test.yar" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_glsl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "glsl-profile-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "lib").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "shaders" / "main.frag").write_text(
        '#version 300 es\n'
        '#include "../lib/noise.glsl"\n'
        "out vec4 fragColor;\n"
        "void main() {\n"
        "  fragColor = vec4(noise());\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "lib" / "noise.glsl").write_text(
        "float noise() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "noise_test.frag").write_text(
        '#version 300 es\nvoid main() {}\n',
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["glsl"]
    assert seed_plan["operational_ecosystems"] == ["glsl"]
    assert "shaders/main.frag" in seed_plan["entrypoint_files"]
    assert "lib" in seed_plan["support_roots"]
    assert "lib/noise.glsl" in seed_plan["candidate_file_paths"]
    assert "tests/noise_test.frag" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_hlsl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hlsl-profile-repo"
    (repo_path / "shaders").mkdir(parents=True)
    (repo_path / "include").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "shaders" / "main.hlsl").write_text(
        '#include "../include/noise.hlsli"\n'
        "float4 RenderMain() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "include" / "noise.hlsli").write_text(
        "float NoiseValue() {\n"
        "  return 0.5;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "noise_test.hlsl").write_text(
        "float4 TestMain() : SV_Target {\n"
        "  return float4(0.0, 0.0, 0.0, 1.0);\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["hlsl"]
    assert seed_plan["operational_ecosystems"] == ["hlsl"]
    assert "shaders/main.hlsl" in seed_plan["entrypoint_files"]
    assert "include" in seed_plan["support_roots"]
    assert "include/noise.hlsli" in seed_plan["candidate_file_paths"]
    assert "tests/noise_test.hlsl" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_shaderlab_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-profile-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    (repo_path / "Tests").mkdir(parents=True)
    (repo_path / "Shaders" / "Main.shader").write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Shaders" / "Includes" / "Common.cginc").write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "Tests" / "Preview.shader").write_text(
        'Shader "Demo/Preview" {\n'
        "SubShader { Pass { } }\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "shaderlab" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "shaderlab"
    assert "Shaders/Main.shader" in seed_plan["entrypoint_files"]
    assert "Shaders/Includes/Common.cginc" in seed_plan["candidate_file_paths"]
    assert "Tests/Preview.shader" not in seed_plan["entrypoint_files"]


def test_shaderlab_profile_hints_reuse_loaded_text_per_candidate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "shaderlab-profile-hints-cache-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    main_path = repo_path / "Shaders" / "Main.shader"
    include_path = repo_path / "Shaders" / "Includes" / "Common.cginc"
    main_path.write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    include_path.write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text
    read_counts: dict[Path, int] = {}

    def _counting_read_text(self: Path, *args, **kwargs) -> str:
        if self in {main_path, include_path}:
            read_counts[self] = read_counts.get(self, 0) + 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read_text)

    entrypoints, roots, configs = _shaderlab_profile_hints_from_candidates(
        repo_path,
        ["Shaders/Main.shader", "Shaders/Includes/Common.cginc"],
    )

    assert "Shaders/Main.shader" in entrypoints
    assert "Shaders" in roots
    assert configs == set()
    assert read_counts.get(main_path, 0) <= 1
    assert read_counts.get(include_path, 0) <= 1


def test_shaderlab_profile_hints_skip_shader_name_alias_scan_without_named_targets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "shaderlab-profile-hints-no-named-targets-repo"
    (repo_path / "Shaders" / "Includes").mkdir(parents=True)
    main_path = repo_path / "Shaders" / "Main.shader"
    include_path = repo_path / "Shaders" / "Includes" / "Common.cginc"
    main_path.write_text(
        'Shader "Demo/Main" {\n'
        "SubShader {\n"
        "Pass {\n"
        "CGPROGRAM\n"
        '#include "Includes/Common.cginc"\n'
        "float4 frag() : SV_Target {\n"
        "  return float4(NoiseValue(), 0.0, 0.0, 1.0);\n"
        "}\n"
        "ENDCG\n"
        "}\n"
        "}\n"
        "}\n",
        encoding="utf-8",
    )
    include_path.write_text(
        "float NoiseValue() {\n"
        "  return 0.25;\n"
        "}\n",
        encoding="utf-8",
    )

    def _unexpected_iter_shader_names(*args, **kwargs):
        raise AssertionError("shader name aliases should be skipped without UsePass/Fallback")

    monkeypatch.setattr(
        repository_shaderlab_primitives,
        "iter_shader_names",
        _unexpected_iter_shader_names,
    )

    entrypoints, roots, configs = _shaderlab_profile_hints_from_candidates(
        repo_path,
        ["Shaders/Main.shader", "Shaders/Includes/Common.cginc"],
    )

    assert "Shaders/Main.shader" in entrypoints
    assert "Shaders" in roots
    assert configs == set()


def test_shaderlab_profile_hints_large_fallback_skips_text_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "shaderlab-large-fallback-fast-path-repo"
    candidate_file_paths: list[str] = []
    for version in range(9):
        shader_dir = repo_path / "Shaders" / f"V{version}"
        shader_dir.mkdir(parents=True, exist_ok=True)
        for basename in ("Main.shader", "Outline.shader", "World.shader"):
            path = shader_dir / basename
            path.write_text(
                'Shader "Demo/Main" {\n'
                "SubShader { Pass { } }\n"
                "}\n",
                encoding="utf-8",
            )
            candidate_file_paths.append(str(path.relative_to(repo_path).as_posix()))
    editor_dir = repo_path / "Editor"
    editor_dir.mkdir(parents=True, exist_ok=True)
    preview_path = editor_dir / "Preview.shader"
    preview_path.write_text(
        'Shader "Demo/Preview" {\n'
        "SubShader { Pass { } }\n"
        "}\n",
        encoding="utf-8",
    )
    candidate_file_paths.append(str(preview_path.relative_to(repo_path).as_posix()))

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "shaderlab",
    )
    original_read_text = Path.read_text

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        if self.suffix.lower() == ".shader":
            raise AssertionError("large shaderlab fallback should avoid loading shader text")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    entrypoints, roots, configs = _shaderlab_profile_hints_from_candidates(
        repo_path,
        candidate_file_paths,
    )

    assert configs == set()
    assert len(entrypoints) == 8
    assert all(path.endswith("Main.shader") for path in entrypoints)
    assert all(path.startswith("Shaders/") for path in entrypoints)
    assert all(root.startswith("Shaders/") for root in roots)
    assert "Editor" not in roots


def test_operational_seed_plan_without_diagnostics_promotes_shaderlab_surface_over_editor_cs(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "shaderlab-editor-heavy-repo"
    (repo_path / "UnityPackage" / "Editor").mkdir(parents=True)
    (repo_path / "UnityPackage" / "Shaders" / "Core").mkdir(parents=True)
    for index in range(160):
        (repo_path / "UnityPackage" / "Editor" / f"EditorTool{index:03}.cs").write_text(
            "public static class EditorTool {\n}\n",
            encoding="utf-8",
        )
    (repo_path / "UnityPackage" / "Editor" / "Preview.shader").write_text(
        'Shader "Demo/Preview" {\n'
        "SubShader { Pass { } }\n"
        "}\n",
        encoding="utf-8",
    )
    for index in range(28):
        (repo_path / "UnityPackage" / "Shaders" / "Core" / f"Surface{index:03}.shader").write_text(
            f'Shader "Demo/Surface{index:03}" {{\n'
            "SubShader { Pass { } }\n"
            "}\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "shaderlab" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "shaderlab"
    assert any(path.startswith("UnityPackage/Shaders/") for path in seed_plan["entrypoint_files"])


def test_operational_seed_plan_without_diagnostics_uses_coq_project_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "coq-profile-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "_CoqProject").write_text(
        "-Q theories Demo\n"
        "theories/Main.v\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Helper.v").write_text(
        "Definition helper : nat := 0.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Lemma run : nat.\n"
        "Proof.\n"
        "  exact helper.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "MainTest.v").write_text(
        "Lemma ignored : True.\nProof.\n exact I.\nQed.\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["coq"]
    assert seed_plan["operational_ecosystems"] == ["coq"]
    assert "_CoqProject" in seed_plan["config_paths"]
    assert "theories/Main.v" in seed_plan["entrypoint_files"]
    assert "theories" in seed_plan["support_roots"]
    assert "tests/MainTest.v" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_lean_lake_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "lean-profile-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "lean-toolchain").write_text(
        "leanprover/lean4:stable\n",
        encoding="utf-8",
    )
    (repo_path / "lakefile.lean").write_text(
        "package batteries where\n\n"
        "lean_lib Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "def helper : Nat := 0\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n\n"
        "def main : Nat := Batteries.Helper.helper\n",
        encoding="utf-8",
    )
    (repo_path / "test" / "Main.lean").write_text(
        "def ignored : Nat := 1\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["lean"]
    assert seed_plan["operational_ecosystems"] == ["lean"]
    assert "lean-toolchain" in seed_plan["config_paths"]
    assert "lakefile.lean" in seed_plan["config_paths"]
    assert "Batteries/Main.lean" in seed_plan["entrypoint_files"]
    assert "Batteries" in seed_plan["support_roots"]
    assert "test/Main.lean" not in seed_plan["entrypoint_files"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_hcl_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "hcl-profile-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "main.tf").write_text(
        'module "child" {\n'
        '  source = "./modules/child"\n'
        '}\n\n'
        'variable "name" {\n'
        '  default = "demo"\n'
        '}\n\n'
        "locals {\n"
        '  prefix = "vpc-${var.name}"\n'
        "}\n\n"
        'output "full_name" {\n'
        "  value = local.prefix\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.tf").write_text(
        'output "child_id" {\n'
        '  value = "child"\n'
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["hcl"]
    assert seed_plan["operational_ecosystems"] == ["hcl"]
    assert "main.tf" in seed_plan["entrypoint_files"]
    assert "modules/child" in seed_plan["support_roots"]
    assert "modules/child/main.tf" in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_bitbake_layer_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bitbake-profile-repo"
    (repo_path / "conf").mkdir(parents=True)
    (repo_path / "classes").mkdir(parents=True)
    (repo_path / "recipes-core" / "base").mkdir(parents=True)
    (repo_path / "recipes-core" / "images").mkdir(parents=True)
    (repo_path / "recipes-devtools" / "python" / "python3-cmake").mkdir(parents=True)
    (repo_path / "conf" / "layer.conf").write_text(
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n',
        encoding="utf-8",
    )
    (repo_path / "classes" / "image.bbclass").write_text(
        "python do_rootfs() {\n"
        "    pass\n"
        "}\n",
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "base" / "base.inc").write_text(
        'BASE_NAME = "base"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-core" / "images" / "core-image-minimal.bb").write_text(
        "require ../base/base.inc\n"
        "inherit image\n"
        'IMAGE_FEATURES += "ssh-server-dropbear"\n',
        encoding="utf-8",
    )
    (repo_path / "recipes-devtools" / "python" / "python3-cmake" / "CMakeLists.txt").write_text(
        "project(python3-cmake)\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "bitbake" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "bitbake"
    assert "conf/layer.conf" in seed_plan["config_paths"]
    assert "recipes-devtools/python/python3-cmake/CMakeLists.txt" not in seed_plan["config_paths"]
    assert "classes/image.bbclass" in seed_plan["candidate_file_paths"]
    assert "recipes-core/images/core-image-minimal.bb" in seed_plan["entrypoint_files"]
    assert "classes/image.bbclass" not in seed_plan["entrypoint_files"]
    assert "classes" in seed_plan["support_roots"]
    assert "recipes-devtools/python/python3-cmake" not in seed_plan["support_roots"]
    assert "recipes-core/base/base.inc" in seed_plan["candidate_file_paths"]
    assert "recipes-devtools/python/python3-cmake/CMakeLists.txt" not in seed_plan["candidate_file_paths"]


def test_operational_seed_plan_without_diagnostics_uses_manifestless_bicep_profile(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "bicep-profile-repo"
    (repo_path / "modules" / "child").mkdir(parents=True)
    (repo_path / "tests").mkdir(parents=True)
    (repo_path / "bicepconfig.json").write_text("{}", encoding="utf-8")
    (repo_path / "main.bicep").write_text(
        "param name string = 'demo'\n\n"
        "module child './modules/child/main.bicep' = {\n"
        "  name: 'child'\n"
        "  params: {\n"
        "    name: name\n"
        "  }\n"
        "}\n\n"
        "output childName string = child.name\n",
        encoding="utf-8",
    )
    (repo_path / "modules" / "child" / "main.bicep").write_text(
        "param name string\n\n"
        "output childId string = name\n",
        encoding="utf-8",
    )
    (repo_path / "tests" / "main.test.bicep").write_text(
        "module testDeployment '../main.bicep' = {\n"
        "  name: 'test'\n"
        "}\n",
        encoding="utf-8",
    )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert seed_plan["detected_ecosystems"] == ["bicep"]
    assert seed_plan["operational_ecosystems"] == ["bicep"]
    assert "bicepconfig.json" in seed_plan["config_paths"]
    assert "main.bicep" in seed_plan["entrypoint_files"]
    assert "modules/child" in seed_plan["support_roots"]
    assert "modules/child/main.bicep" in seed_plan["candidate_file_paths"]
    assert "tests/main.test.bicep" not in seed_plan["entrypoint_files"]
