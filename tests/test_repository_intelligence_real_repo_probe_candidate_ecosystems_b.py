"""Tests for repository_intelligence_real_repo_probe: candidate_ecosystems_b.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

import benchmarks.repository_intelligence_real_repo_probe_collection_support as collection_support
import benchmarks.repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support
import benchmarks.repository_intelligence_real_repo_probe_repo_hint_support as repo_hint_support

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


def test_candidate_ecosystems_for_path_identifies_meson_build_files(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "meson-candidate-ecosystems-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "meson.build").write_text("project('demo', 'cpp')\nsubdir('src')\n", encoding="utf-8")
    (repo_path / "src" / "meson.build").write_text("executable('demo', 'main.cc')\n", encoding="utf-8")
    (repo_path / "src" / "main.cc").write_text("int main() { return 0; }\n", encoding="utf-8")

    assert probe_module._candidate_ecosystems_for_path("meson.build", repo_path=repo_path) == {
        "meson"
    }
    assert probe_module._candidate_ecosystems_for_path(
        "src/meson.build",
        repo_path=repo_path,
    ) == {"meson"}
    assert probe_module._candidate_ecosystems_for_path(
        "src/main.cc",
        repo_path=repo_path,
    ) == {"cpp"}


def test_delphi_project_config_path_prefers_sibling_entrypoint_without_repo_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "delphi-fast-path-repo"
    (repo_path / "App").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpk</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpk").write_text(
        "package AcmeApp;\n"
        "contains\n"
        "  MainForm in 'MainForm.pas';\n"
        "end.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(AssertionError("git file scan not expected")),
    )

    assert probe_module._is_delphi_project_config_path(
        repo_path,
        "App/AcmeApp.dproj",
    ) is True


def test_delphi_project_config_path_bypasses_generic_language_probe_for_sibling_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "delphi-sibling-fast-path-repo"
    (repo_path / "App").mkdir(parents=True)
    (repo_path / "App" / "AcmeApp.dproj").write_text(
        "<Project>\n"
        "  <MainSource>AcmeApp.dpk</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )
    (repo_path / "App" / "AcmeApp.dpk").write_text(
        "package AcmeApp;\n"
        "contains\n"
        "  MainForm in 'MainForm.pas';\n"
        "end.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic delphi language probing should be bypassed")
        ),
    )
    classification_support.clear_delphi_project_config_path_cache()

    assert probe_module._is_delphi_project_config_path(
        repo_path,
        "App/AcmeApp.dproj",
    ) is True


def test_delphi_project_config_path_skips_non_operational_project_files_without_reading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "delphi-test-project-fast-reject-repo"
    (repo_path / "Tests").mkdir(parents=True)
    project_path = repo_path / "Tests" / "AcmeTests.dproj"
    project_path.write_text(
        "<Project>\n"
        "  <MainSource>AcmeTests.dpr</MainSource>\n"
        "</Project>\n",
        encoding="utf-8",
    )

    original_read_text = Path.read_text

    def _guarded_read_text(self: Path, *args, **kwargs) -> str:
        if self == project_path:
            raise AssertionError("non-operational delphi project files should fast-reject")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _guarded_read_text)
    classification_support.clear_delphi_project_config_path_cache()

    assert probe_module._is_delphi_project_config_path(
        repo_path,
        "Tests/AcmeTests.dproj",
    ) is False


def test_coq_profile_hints_bypass_generic_language_probe_for_manifest_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-profile-fast-path-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_coqproject").write_text("theories/Main.v\n", encoding="utf-8")
    (repo_path / "theories" / "Main.v").write_text(
        "From Coq Require Import Arith.\n"
        "Theorem main_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  reflexivity.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic coq language probing should be bypassed")
        ),
    )
    classification_support.clear_coq_source_path_cache()

    entrypoints, support_roots, config_paths = probe_module._coq_profile_hints(
        repo_path,
        "_coqproject",
    )

    assert "theories/Main.v" in entrypoints
    assert "theories" in support_roots
    assert config_paths == {"_coqproject"}


def test_coq_profile_hints_bypass_generic_entrypoint_probe_for_fallback_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-profile-fallback-fast-path-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_coqproject").write_text("theories\n", encoding="utf-8")
    (repo_path / "theories" / "Helper.v").write_text(
        "Lemma helper_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  reflexivity.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Theorem main_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  apply helper_id.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic coq entrypoint probing should be bypassed")
        ),
    )
    classification_support.clear_coq_source_path_cache()

    entrypoints, support_roots, config_paths = probe_module._coq_profile_hints(
        repo_path,
        "_coqproject",
    )

    assert "theories/Main.v" in entrypoints
    assert "theories" in support_roots
    assert config_paths == {"_coqproject"}


def test_coq_profile_hints_use_tracked_files_without_support_root_rglob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-profile-tracked-files-fast-path-repo"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_coqproject").write_text("theories\n", encoding="utf-8")
    (repo_path / "theories" / "Helper.v").write_text(
        "Lemma helper_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  reflexivity.\n"
        "Qed.\n",
        encoding="utf-8",
    )
    (repo_path / "theories" / "Main.v").write_text(
        "Require Import Helper.\n"
        "Theorem main_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  apply helper_id.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    original_rglob = Path.rglob

    def _guarded_rglob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        if self == repo_path / "theories" and pattern == "*.v":
            raise AssertionError("tracked Coq files should bypass support-root rglob scanning")
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _guarded_rglob)
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: ["_coqproject", "theories/Helper.v", "theories/Main.v"],
    )
    classification_support.clear_coq_source_path_cache()

    entrypoints, support_roots, config_paths = probe_module._coq_profile_hints(
        repo_path,
        "_coqproject",
    )

    assert "theories/Main.v" in entrypoints
    assert "theories" in support_roots
    assert config_paths == {"_coqproject"}


def test_lean_profile_hints_use_tracked_files_without_support_root_rglob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "lean-profile-tracked-files-fast-path-repo"
    (repo_path / "Batteries").mkdir(parents=True)
    (repo_path / "lakefile.lean").write_text('package batteries\n', encoding="utf-8")
    (repo_path / "Batteries" / "Helper.lean").write_text(
        "namespace Batteries\n"
        "def helper : Nat := 0\n"
        "end Batteries\n",
        encoding="utf-8",
    )
    (repo_path / "Batteries" / "Main.lean").write_text(
        "import Batteries.Helper\n"
        "def main : Nat := Batteries.helper\n",
        encoding="utf-8",
    )

    original_rglob = Path.rglob

    def _guarded_rglob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        if self == repo_path / "Batteries" and pattern == "*.lean":
            raise AssertionError("tracked Lean files should bypass support-root rglob scanning")
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _guarded_rglob)
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: [
            "lakefile.lean",
            "Batteries/Helper.lean",
            "Batteries/Main.lean",
        ],
    )

    entrypoints, support_roots, config_paths = probe_module._lean_profile_hints(
        repo_path,
        "lakefile.lean",
    )

    assert "Batteries/Main.lean" in entrypoints
    assert "Batteries" in support_roots
    assert config_paths == {"lakefile.lean"}


def test_v_profile_hints_use_tracked_files_without_support_root_rglob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "v-profile-tracked-files-fast-path-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "v.mod").write_text("Module { name: 'demo' }\n", encoding="utf-8")
    (repo_path / "src" / "main.v").write_text("module main\n\nfn main() {}\n", encoding="utf-8")

    original_rglob = Path.rglob
    original_probe_language_for_path = probe_module._probe_language_for_path

    def _guarded_rglob(self: Path, pattern: str):  # type: ignore[no-untyped-def]
        if self == repo_path / "src" and pattern == "*.v":
            raise AssertionError("tracked V files should bypass support-root rglob scanning")
        return original_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", _guarded_rglob)
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: ["v.mod", "src/main.v"],
    )
    monkeypatch.setattr(
        probe_module,
        "_probe_language_for_path",
        lambda relative_path, **_kwargs: "v"
        if relative_path in {"v.mod", "src/main.v"}
        else original_probe_language_for_path(relative_path, **_kwargs),
    )

    entrypoints, support_roots, config_paths = probe_module._v_profile_hints(
        repo_path,
        "v.mod",
    )

    assert "src/main.v" in entrypoints
    assert "src" in support_roots
    assert config_paths == {"v.mod"}


def test_probe_ambiguous_v_repo_hint_language_uses_tracked_paths_for_coq_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "coq-repo-hint-fast-path"
    (repo_path / "theories").mkdir(parents=True)
    (repo_path / "_coqproject").write_text("theories/Main.v\n", encoding="utf-8")
    (repo_path / "theories" / "Main.v").write_text(
        "Theorem main_id : forall n, n = n.\n"
        "Proof.\n"
        "  intros n.\n"
        "  reflexivity.\n"
        "Qed.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repo_hint_support._probe_module().repository_service,
        "_ambiguous_v_repo_hint_language",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("filesystem-wide ambiguous .v scan should be bypassed")
        ),
    )
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: ["_coqproject", "theories/Main.v"],
    )
    repo_hint_support.clear_ambiguous_v_repo_hint_cache()

    assert repo_hint_support.probe_ambiguous_v_repo_hint_language(repo_path) == "coq"


def test_probe_ambiguous_v_repo_hint_language_uses_tracked_paths_for_systemverilog_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "systemverilog-repo-hint-fast-path"
    (repo_path / "rtl").mkdir(parents=True)
    (repo_path / "rtl" / "Top.sv").write_text("module Top; endmodule\n", encoding="utf-8")

    monkeypatch.setattr(
        repo_hint_support._probe_module().repository_service,
        "_ambiguous_v_repo_hint_language",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("filesystem-wide ambiguous .v scan should be bypassed")
        ),
    )
    monkeypatch.setattr(
        collection_support,
        "_git_repo_relative_files",
        lambda _repo_path: ["rtl/Top.sv"],
    )
    repo_hint_support.clear_ambiguous_v_repo_hint_cache()

    assert repo_hint_support.probe_ambiguous_v_repo_hint_language(repo_path) == "systemverilog"
