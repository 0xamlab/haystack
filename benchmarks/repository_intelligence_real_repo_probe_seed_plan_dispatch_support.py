from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from apps.api_server.services import repository_intelligence as repository_service


def dispatch_basenames_to_ecosystem(state: Any) -> None:
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    _accumulate_detected_ecosystem_scores = probe_module._accumulate_detected_ecosystem_scores
    _actionscript_profile_hints = probe_module._actionscript_profile_hints
    _ada_profile_hints = probe_module._ada_profile_hints
    _agda_profile_hints = probe_module._agda_profile_hints
    _apex_profile_hints = probe_module._apex_profile_hints
    _bicep_profile_hints_from_candidates = probe_module._bicep_profile_hints_from_candidates
    _bitbake_profile_candidate_paths = probe_module._bitbake_profile_candidate_paths
    _bitbake_profile_hints_from_candidates = probe_module._bitbake_profile_hints_from_candidates
    _c_family_manifest_ecosystems = probe_module._c_family_manifest_ecosystems
    _cargo_profile_hints = probe_module._cargo_profile_hints
    _cfml_profile_hints = probe_module._cfml_profile_hints
    _chapel_profile_hints = probe_module._chapel_profile_hints
    _classic_visual_basic_profile_hints = probe_module._classic_visual_basic_profile_hints
    _clojure_profile_hints = probe_module._clojure_profile_hints
    _cmake_profile_hints = probe_module._cmake_profile_hints
    _coffeescript_profile_hints = probe_module._coffeescript_profile_hints
    _composer_profile_hints = probe_module._composer_profile_hints
    _coq_profile_hints = probe_module._coq_profile_hints
    _csproj_profile_hints = probe_module._csproj_profile_hints
    _cue_profile_hints_from_candidates = probe_module._cue_profile_hints_from_candidates
    _dbt_project_profile_hints = probe_module._dbt_project_profile_hints
    _delphi_profile_hints = probe_module._delphi_profile_hints
    _dhall_profile_hints_from_candidates = probe_module._dhall_profile_hints_from_candidates
    _dockerfile_profile_hints_from_candidates = probe_module._dockerfile_profile_hints_from_candidates
    _dub_profile_hints = probe_module._dub_profile_hints
    _eiffel_profile_hints = probe_module._eiffel_profile_hints
    _elm_profile_hints = probe_module._elm_profile_hints
    _emacslisp_profile_hints = probe_module._emacslisp_profile_hints
    _erlang_project_profile_hints = probe_module._erlang_project_profile_hints
    _fortran_fpm_profile_hints = probe_module._fortran_fpm_profile_hints
    _gams_profile_hints = probe_module._gams_profile_hints
    _gdscript_project_profile_hints = probe_module._gdscript_project_profile_hints
    _gemfile_profile_hints = probe_module._gemfile_profile_hints
    _gleam_profile_hints = probe_module._gleam_profile_hints
    _gml_profile_hints = probe_module._gml_profile_hints
    _go_module_profile_hints = probe_module._go_module_profile_hints
    _gradle_profile_hints = probe_module._gradle_profile_hints
    _hack_profile_hints_from_candidates = probe_module._hack_profile_hints_from_candidates
    _haskell_cabal_profile_hints = probe_module._haskell_cabal_profile_hints
    _haskell_package_yaml_profile_hints = probe_module._haskell_package_yaml_profile_hints
    _haskell_project_profile_hints = probe_module._haskell_project_profile_hints
    _haxe_profile_hints = probe_module._haxe_profile_hints
    _idris_profile_hints = probe_module._idris_profile_hints
    _is_cfml_box_config_path = probe_module._is_cfml_box_config_path
    _is_cue_module_config_path = probe_module._is_cue_module_config_path
    _is_delphi_project_config_path = probe_module._is_delphi_project_config_path
    _is_eiffel_project_config_path = probe_module._is_eiffel_project_config_path
    _is_non_operational_profile_path = probe_module._is_non_operational_profile_path
    _is_odin_ols_config_path = probe_module._is_odin_ols_config_path
    _is_puppet_metadata_config_path = probe_module._is_puppet_metadata_config_path
    _is_purescript_bower_config_path = probe_module._is_purescript_bower_config_path
    _is_qmake_project_config_path = probe_module._is_qmake_project_config_path
    _is_xpp_descriptor_config_path = probe_module._is_xpp_descriptor_config_path
    _janet_profile_hints = probe_module._janet_profile_hints
    _julia_profile_hints = probe_module._julia_profile_hints
    _labview_profile_hints = probe_module._labview_profile_hints
    _lean_profile_hints = probe_module._lean_profile_hints
    _lisp_profile_hints = probe_module._lisp_profile_hints
    _luau_profile_hints = probe_module._luau_profile_hints
    _meson_profile_hints = probe_module._meson_profile_hints
    _mix_profile_hints = probe_module._mix_profile_hints
    _ml_profile_hints = probe_module._ml_profile_hints
    _moonbit_profile_hints_from_candidates = probe_module._moonbit_profile_hints_from_candidates
    _mql5_profile_hints = probe_module._mql5_profile_hints
    _nextflow_profile_hints_from_candidates = probe_module._nextflow_profile_hints_from_candidates
    _nim_project_profile_hints = probe_module._nim_project_profile_hints
    _nix_profile_hints = probe_module._nix_profile_hints
    _ocaml_profile_hints = probe_module._ocaml_profile_hints
    _odin_profile_hints = probe_module._odin_profile_hints
    _openscad_profile_hints = probe_module._openscad_profile_hints
    _package_json_profile_hints = probe_module._package_json_profile_hints
    _pascal_project_profile_hints = probe_module._pascal_project_profile_hints
    _perl_profile_hints = probe_module._perl_profile_hints
    _podspec_profile_hints = probe_module._podspec_profile_hints
    _pom_profile_hints = probe_module._pom_profile_hints
    _powershell_profile_hints = probe_module._powershell_profile_hints
    _protobuf_profile_hints_from_candidates = probe_module._protobuf_profile_hints_from_candidates
    _pubspec_profile_hints = probe_module._pubspec_profile_hints
    _puppet_profile_hints = probe_module._puppet_profile_hints
    _purescript_profile_hints = probe_module._purescript_profile_hints
    _pyproject_profile_hints = probe_module._pyproject_profile_hints
    _qmake_profile_hints = probe_module._qmake_profile_hints
    _qsharp_profile_hints = probe_module._qsharp_profile_hints
    _r_profile_hints = probe_module._r_profile_hints
    _racket_profile_hints = probe_module._racket_profile_hints
    _raku_profile_hints = probe_module._raku_profile_hints
    _register_candidate_ecosystems = probe_module._register_candidate_ecosystems
    _repo_profile_candidate_paths = probe_module._repo_profile_candidate_paths
    _rescript_profile_hints = probe_module._rescript_profile_hints
    _rockspec_profile_hints = probe_module._rockspec_profile_hints
    _rpg_profile_hints = probe_module._rpg_profile_hints
    _scala_build_profile_hints = probe_module._scala_build_profile_hints
    _scheme_profile_hints = probe_module._scheme_profile_hints
    _seeded_repo_profile_candidate_paths = probe_module._seeded_repo_profile_candidate_paths
    _shard_profile_hints = probe_module._shard_profile_hints
    _sln_profile_hints = probe_module._sln_profile_hints
    _sln_project_paths = probe_module._sln_project_paths
    _smalltalk_profile_hints = probe_module._smalltalk_profile_hints
    _solidity_profile_hints = probe_module._solidity_profile_hints
    _starlark_profile_hints = probe_module._starlark_profile_hints
    _swift_package_profile_hints = probe_module._swift_package_profile_hints
    _systemverilog_profile_hints = probe_module._systemverilog_profile_hints
    _tcl_profile_hints = probe_module._tcl_profile_hints
    _tsconfig_profile_hints = probe_module._tsconfig_profile_hints
    _tsql_profile_hints = probe_module._tsql_profile_hints
    _v_profile_hints = probe_module._v_profile_hints
    _vbscript_profile_hints = probe_module._vbscript_profile_hints
    _vhdl_profile_hints = probe_module._vhdl_profile_hints
    _wolfram_profile_hints = probe_module._wolfram_profile_hints
    _xpp_profile_hints = probe_module._xpp_profile_hints
    _zig_build_profile_hints = probe_module._zig_build_profile_hints

    """Walks discovered config paths and dispatches each basename to its
    per-ecosystem hint helper. Mutates state.entrypoint_candidates /
    support_root_candidates / config_path_candidates / detected_ecosystems /
    detected_ecosystem_scores / entrypoint_candidate_ecosystems /
    support_root_candidate_ecosystems in place. Extracted verbatim from
    _derive_operational_seed_plan_without_diagnostics for readability;
    behavior unchanged."""

    repo_path = state.repo_path
    focus_paths = state.focus_paths
    max_files = state.max_files
    discovered_config_paths = state.discovered_config_paths
    entrypoint_candidates = state.entrypoint_candidates
    support_root_candidates = state.support_root_candidates
    config_path_candidates = state.config_path_candidates
    detected_ecosystems = state.detected_ecosystems
    detected_ecosystem_scores = state.detected_ecosystem_scores
    entrypoint_candidate_ecosystems = state.entrypoint_candidate_ecosystems
    support_root_candidate_ecosystems = state.support_root_candidate_ecosystems

    for candidate_path in sorted(discovered_config_paths):
        basename = PurePosixPath(candidate_path).name.lower()
        manifest_ecosystems: set[str]
        preferred_manifest_ecosystems: set[str] = set()
        if _is_xpp_descriptor_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"xpp"}
            entrypoints, roots, configs = _xpp_profile_hints(repo_path, candidate_path)
        elif basename == "box.json" and _is_cfml_box_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"cfml"}
            entrypoints, roots, configs = _cfml_profile_hints(repo_path, candidate_path)
        elif basename == "package.json":
            manifest_ecosystems = {"node"}
            entrypoints, roots, configs = _package_json_profile_hints(repo_path, candidate_path)
        elif basename in {"tsconfig.json", "jsconfig.json"} or (
            basename.startswith("tsconfig.") and basename.endswith(".json")
        ):
            manifest_ecosystems = {"typescript"}
            entrypoints, roots, configs = _tsconfig_profile_hints(repo_path, candidate_path)
        elif basename in {
            "build",
            "build.bazel",
            "module.bazel",
            "workspace",
            "workspace.bazel",
        }:
            manifest_ecosystems = {"starlark"}
            entrypoints, roots, configs = _starlark_profile_hints(repo_path, candidate_path)
        elif basename == "pyproject.toml":
            manifest_ecosystems = {"python"}
            entrypoints, roots, configs = _pyproject_profile_hints(repo_path, candidate_path)
        elif basename == "shadow-cljs.edn":
            manifest_ecosystems = {"clojurescript"}
            entrypoints, roots, configs = _clojure_profile_hints(repo_path, candidate_path)
        elif basename in {"project.clj", "deps.edn", "bb.edn"}:
            manifest_ecosystems = {"clojure"}
            entrypoints, roots, configs = _clojure_profile_hints(repo_path, candidate_path)
        elif basename == "pubspec.yaml":
            manifest_ecosystems = {"dart"}
            entrypoints, roots, configs = _pubspec_profile_hints(repo_path, candidate_path)
        elif basename == "alire.toml" or basename.endswith(".gpr"):
            manifest_ecosystems = {"ada"}
            entrypoints, roots, configs = _ada_profile_hints(repo_path, candidate_path)
        elif basename in {"dbt_project.yml", "dbt_project.yaml"}:
            manifest_ecosystems = {"sql"}
            entrypoints, roots, configs = _dbt_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith((".sqlproj", ".dbproj")):
            manifest_ecosystems = {"tsql"}
            entrypoints, roots, configs = _tsql_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "package.yaml":
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_package_yaml_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "fpm.toml":
            manifest_ecosystems = {"fortran"}
            entrypoints, roots, configs = _fortran_fpm_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".dproj") and _is_delphi_project_config_path(
            repo_path,
            candidate_path,
        ):
            manifest_ecosystems = {"delphi"}
            entrypoints, roots, configs = _delphi_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".ecf", ".ace")) and _is_eiffel_project_config_path(
            repo_path,
            candidate_path,
        ):
            manifest_ecosystems = {"eiffel"}
            entrypoints, roots, configs = _eiffel_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".lpi", ".lpk")):
            manifest_ecosystems = {"pascal"}
            entrypoints, roots, configs = _pascal_project_profile_hints(candidate_path)
        elif basename in {"dub.json", "dub.sdl"}:
            manifest_ecosystems = {"d"}
            entrypoints, roots, configs = _dub_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cargo.toml":
            manifest_ecosystems = {"rust"}
            entrypoints, roots, configs = _cargo_profile_hints(repo_path, candidate_path)
        elif basename == "go.mod":
            manifest_ecosystems = {"go"}
            entrypoints, roots, configs = _go_module_profile_hints(candidate_path)
        elif basename == "qsharp.json":
            manifest_ecosystems = {"qsharp"}
            entrypoints, roots, configs = _qsharp_profile_hints(candidate_path)
        elif basename.endswith(".cabal"):
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_cabal_profile_hints(repo_path, candidate_path)
        elif basename in {"stack.yaml", "cabal.project"}:
            manifest_ecosystems = {"haskell"}
            entrypoints, roots, configs = _haskell_project_profile_hints(candidate_path)
        elif basename == "pom.xml":
            manifest_ecosystems = {"java"}
            entrypoints, roots, configs = _pom_profile_hints(candidate_path)
        elif basename in {"build.gradle", "settings.gradle"}:
            manifest_ecosystems = {"groovy", "java"}
            entrypoints, roots, configs = _gradle_profile_hints(repo_path, candidate_path)
        elif basename in {"build.gradle.kts", "settings.gradle.kts"}:
            manifest_ecosystems = {"java", "kotlin"}
            entrypoints, roots, configs = _gradle_profile_hints(repo_path, candidate_path)
        elif basename in {"build.sbt", "build.sc", "build.mill"}:
            manifest_ecosystems = {"scala"}
            entrypoints, roots, configs = _scala_build_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"dune", "dune-project"} or basename.endswith(".opam"):
            manifest_ecosystems = {"ocaml"}
            entrypoints, roots, configs = _ocaml_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".mlb") or basename.endswith(".cm"):
            entrypoints, roots, configs = _ml_profile_hints(repo_path, candidate_path)
            if not configs:
                continue
            manifest_ecosystems = {"sml"}
        elif basename == "cmakelists.txt":
            manifest_ecosystems = {
                "cmake",
                *_c_family_manifest_ecosystems(
                    repo_path=repo_path,
                    manifest_path=candidate_path,
                ),
            }
            entrypoints, roots, configs = _cmake_profile_hints(repo_path, candidate_path)
        elif _is_qmake_project_config_path(repo_path, candidate_path):
            manifest_ecosystems = {
                "qmake",
                *_c_family_manifest_ecosystems(
                    repo_path=repo_path,
                    manifest_path=candidate_path,
                ),
            }
            preferred_manifest_ecosystems = {"qmake"}
            entrypoints, roots, configs = _qmake_profile_hints(repo_path, candidate_path)
        elif basename == "composer.json":
            manifest_ecosystems = {"php"}
            entrypoints, roots, configs = _composer_profile_hints(repo_path, candidate_path)
        elif basename in {"cpanfile", "dist.ini", "makefile.pl", "build.pl"}:
            manifest_ecosystems = {"perl"}
            entrypoints, roots, configs = _perl_profile_hints(repo_path, candidate_path)
        elif basename in {"description", "namespace"}:
            manifest_ecosystems = {"r"}
            entrypoints, roots, configs = _r_profile_hints(repo_path, candidate_path)
        elif basename in {"project.toml", "manifest.toml"}:
            manifest_ecosystems = {"julia"}
            entrypoints, roots, configs = _julia_profile_hints(repo_path, candidate_path)
        elif basename == "shard.yml":
            manifest_ecosystems = {"crystal"}
            entrypoints, roots, configs = _shard_profile_hints(repo_path, candidate_path)
        elif basename == "mix.exs":
            manifest_ecosystems = {"elixir"}
            entrypoints, roots, configs = _mix_profile_hints(repo_path, candidate_path)
        elif basename in {"rebar.config", "erlang.mk"} or basename.endswith(".app.src"):
            manifest_ecosystems = {"erlang"}
            entrypoints, roots, configs = _erlang_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "elm.json":
            manifest_ecosystems = {"elm"}
            entrypoints, roots, configs = _elm_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"spago.yaml", "spago.dhall"} or (
            basename == "bower.json"
            and _is_purescript_bower_config_path(repo_path, candidate_path)
        ):
            manifest_ecosystems = {"purescript"}
            entrypoints, roots, configs = _purescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"rescript.json", "bsconfig.json"}:
            manifest_ecosystems = {"rescript"}
            entrypoints, roots, configs = _rescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in repository_service.moonbit_adapter.MOONBIT_CONFIG_BASENAMES:
            manifest_ecosystems = {"moonbit"}
            moonbit_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _moonbit_profile_hints_from_candidates(
                repo_path,
                moonbit_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "gleam.toml":
            manifest_ecosystems = {"gleam"}
            entrypoints, roots, configs = _gleam_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.janet":
            manifest_ecosystems = {"janet"}
            entrypoints, roots, configs = _janet_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "nextflow.config":
            manifest_ecosystems = {"nextflow"}
            nextflow_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _nextflow_profile_hints_from_candidates(
                repo_path,
                nextflow_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "mason.toml":
            manifest_ecosystems = {"chapel"}
            entrypoints, roots, configs = _chapel_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in repository_service.bitbake_adapter.BITBAKE_CONFIG_BASENAMES:
            manifest_ecosystems = {"bitbake"}
            bitbake_candidate_paths = _bitbake_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                config_paths=[candidate_path, *discovered_config_paths],
                max_files=max_files,
            ) or _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _bitbake_profile_hints_from_candidates(
                repo_path,
                bitbake_candidate_paths,
            )
            configs = set(configs)
            configs.add(candidate_path)
        elif basename == "bicepconfig.json":
            manifest_ecosystems = {"bicep"}
            bicep_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _bicep_profile_hints_from_candidates(
                repo_path,
                bicep_candidate_paths,
            )
            configs = set(configs)
            configs.add(candidate_path)
        elif basename == "module.cue" and _is_cue_module_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"cue"}
            cue_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _cue_profile_hints_from_candidates(
                repo_path,
                cue_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "ols.json" and _is_odin_ols_config_path(repo_path, candidate_path):
            manifest_ecosystems = {"odin"}
            entrypoints, roots, configs = _odin_profile_hints(repo_path, candidate_path)
        elif basename in {".hhconfig", "hhvm.autoload", "hh_autoload.json"}:
            manifest_ecosystems = {"hack"}
            hack_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _hack_profile_hints_from_candidates(
                repo_path,
                hack_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename == "package.dhall":
            manifest_ecosystems = {"dhall"}
            dhall_candidate_paths = _seeded_repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
                entrypoint_candidates=entrypoint_candidates,
                support_root_candidates=support_root_candidates,
                config_paths=discovered_config_paths,
                detected_ecosystems=detected_ecosystems,
                detected_ecosystem_scores=detected_ecosystem_scores,
            ) or _repo_profile_candidate_paths(
                repo_path=repo_path,
                focus_paths=focus_paths,
                max_files=max_files,
            )
            entrypoints, roots, configs = _dhall_profile_hints_from_candidates(
                repo_path,
                dhall_candidate_paths,
                manifest_path=candidate_path,
            )
        elif basename in {"puppetfile", "modulefile"} or (
            basename == "metadata.json"
            and _is_puppet_metadata_config_path(repo_path, candidate_path)
        ):
            manifest_ecosystems = {"puppet"}
            entrypoints, roots, configs = _puppet_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"lean-toolchain", "lakefile.lean", "lakefile.toml"}:
            manifest_ecosystems = {"lean"}
            entrypoints, roots, configs = _lean_profile_hints(repo_path, candidate_path)
        elif basename in {"_coqproject", "_rocqproject"}:
            manifest_ecosystems = {"coq"}
            entrypoints, roots, configs = _coq_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".agda-lib"):
            manifest_ecosystems = {"agda"}
            entrypoints, roots, configs = _agda_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".ipkg"):
            manifest_ecosystems = {"idris"}
            entrypoints, roots, configs = _idris_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "meta6.json":
            manifest_ecosystems = {"raku"}
            entrypoints, roots, configs = _raku_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cask":
            manifest_ecosystems = {"emacslisp"}
            entrypoints, roots, configs = _emacslisp_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {
            ".smalltalk.ston",
            ".smalltalk.all.ston",
            ".smalltalk.release.ston",
        }:
            manifest_ecosystems = {"smalltalk"}
            entrypoints, roots, configs = _smalltalk_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "cakefile":
            manifest_ecosystems = {"coffeescript"}
            entrypoints, roots, configs = _coffeescript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.xml" or basename.endswith(".hxml"):
            manifest_ecosystems = {"haxe"}
            entrypoints, roots, configs = _haxe_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".mqproj"):
            manifest_ecosystems = {"mql5"}
            entrypoints, roots, configs = _mql5_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".gms"):
            manifest_ecosystems = {"gams"}
            entrypoints, roots, configs = _gams_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".scad"):
            manifest_ecosystems = {"openscad"}
            entrypoints, roots, configs = _openscad_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"flake.nix", "default.nix", "shell.nix"}:
            manifest_ecosystems = {"nix"}
            entrypoints, roots, configs = _nix_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "v.mod":
            manifest_ecosystems = {"v"}
            entrypoints, roots, configs = _v_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".nimble") or basename in {"config.nims", "nim.cfg"}:
            manifest_ecosystems = {"nim"}
            entrypoints, roots, configs = _nim_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "meson.build":
            manifest_ecosystems = {"meson", *_c_family_manifest_ecosystems(
                repo_path=repo_path,
                manifest_path=candidate_path,
            )}
            entrypoints, roots, configs = _meson_profile_hints(repo_path, candidate_path)
        elif basename == "build.zig":
            manifest_ecosystems = {"zig"}
            entrypoints, roots, configs = _zig_build_profile_hints(repo_path, candidate_path)
        elif basename == "package.swift":
            manifest_ecosystems = {"swift"}
            entrypoints, roots, configs = _swift_package_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".podspec"):
            manifest_ecosystems = {"objectivec"}
            entrypoints, roots, configs = _podspec_profile_hints(repo_path, candidate_path)
        elif basename in {
            "brownie-config.yaml",
            "brownie-config.yml",
            "foundry.toml",
            "hardhat.config.cjs",
            "hardhat.config.js",
            "hardhat.config.mjs",
            "hardhat.config.ts",
            "remappings.txt",
            "truffle-config.js",
            "truffle.js",
        }:
            manifest_ecosystems = {"solidity"}
            entrypoints, roots, configs = _solidity_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename in {"bender.yml", "bender.yaml"} or basename.endswith(".core"):
            manifest_ecosystems = {"systemverilog"}
            entrypoints, roots, configs = _systemverilog_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "vhdl_ls.toml":
            manifest_ecosystems = {"vhdl"}
            entrypoints, roots, configs = _vhdl_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "project.godot":
            manifest_ecosystems = {"gdscript"}
            entrypoints, roots, configs = _gdscript_project_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".yyp"):
            manifest_ecosystems = {"gml"}
            entrypoints, roots, configs = _gml_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".psd1"):
            manifest_ecosystems = {"powershell"}
            entrypoints, roots, configs = _powershell_profile_hints(repo_path, candidate_path)
        elif basename == "gemfile" or basename.endswith(".gemspec"):
            manifest_ecosystems = {"ruby"}
            entrypoints, roots, configs = _gemfile_profile_hints(repo_path, candidate_path)
        elif basename in {"default.project.json", "wally.toml"}:
            manifest_ecosystems = {"luau"}
            entrypoints, roots, configs = _luau_profile_hints(repo_path, candidate_path)
        elif basename in repository_service.typst_adapter.TYPST_CONFIG_BASENAMES:
            manifest_ecosystems = {"typst"}
            entrypoints = set()
            roots = {
                repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(candidate_path).parent)
                )
            }
            configs = {candidate_path}
        elif basename in repository_service.tex_adapter.TEX_CONFIG_BASENAMES:
            manifest_ecosystems = {"tex"}
            entrypoints = set()
            roots = {
                repository_service._normalize_repository_relative_path(
                    str(PurePosixPath(candidate_path).parent)
                )
            }
            configs = {candidate_path}
        elif basename in repository_service.protobuf_adapter.PROTOBUF_CONFIG_BASENAMES:
            manifest_ecosystems = {"protobuf"}
            entrypoints, roots, configs = _protobuf_profile_hints_from_candidates(
                repo_path,
                [candidate_path],
            )
        elif basename in repository_service.dockerfile_adapter.DOCKERFILE_BASENAMES:
            manifest_ecosystems = {"dockerfile"}
            entrypoints, roots, configs = _dockerfile_profile_hints_from_candidates(
                repo_path,
                [candidate_path],
            )
        elif basename.endswith(".rockspec"):
            manifest_ecosystems = {"lua"}
            entrypoints, roots, configs = _rockspec_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".fsproj"):
            manifest_ecosystems = {"dotnet", "fsharp"}
            preferred_manifest_ecosystems = {"fsharp"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        elif basename.endswith(".vbproj"):
            manifest_ecosystems = {"dotnet", "visualbasic"}
            preferred_manifest_ecosystems = {"visualbasic"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        elif basename == "sfdx-project.json":
            manifest_ecosystems = {"apex"}
            entrypoints, roots, configs = _apex_profile_hints(repo_path, candidate_path)
        elif basename.endswith((".lvproj", ".lvlib", ".lvclass")):
            manifest_ecosystems = {"labview"}
            entrypoints, roots, configs = _labview_profile_hints(repo_path, candidate_path)
        elif basename in {"pacletinfo.m", "pacletinfo.wl"}:
            manifest_ecosystems = {"wolfram"}
            entrypoints, roots, configs = _wolfram_profile_hints(repo_path, candidate_path)
        elif basename in {"iproj.json", ".ibmi.json"}:
            manifest_ecosystems = {"rpg"}
            entrypoints, roots, configs = _rpg_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".vbp"):
            manifest_ecosystems = {"vb6"}
            entrypoints, roots, configs = _classic_visual_basic_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "asconfig.json":
            manifest_ecosystems = {"actionscript"}
            entrypoints, roots, configs = _actionscript_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename.endswith(".wsf"):
            manifest_ecosystems = {"vbscript"}
            entrypoints, roots, configs = _vbscript_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".asd"):
            manifest_ecosystems = {"lisp"}
            entrypoints, roots, configs = _lisp_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "info.rkt":
            manifest_ecosystems = {"racket"}
            entrypoints, roots, configs = _racket_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "package.scm":
            manifest_ecosystems = {"scheme"}
            entrypoints, roots, configs = _scheme_profile_hints(
                repo_path,
                candidate_path,
            )
        elif basename == "pkgindex.tcl":
            manifest_ecosystems = {"tcl"}
            entrypoints, roots, configs = _tcl_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".sln"):
            manifest_ecosystems = {"dotnet"}
            project_paths = _sln_project_paths(repo_path, candidate_path)
            if any(project_path.lower().endswith(".fsproj") for project_path in project_paths):
                manifest_ecosystems.add("fsharp")
                preferred_manifest_ecosystems.add("fsharp")
            if any(project_path.lower().endswith(".vbproj") for project_path in project_paths):
                manifest_ecosystems.add("visualbasic")
                preferred_manifest_ecosystems.add("visualbasic")
            entrypoints, roots, configs = _sln_profile_hints(repo_path, candidate_path)
        elif basename.endswith(".csproj"):
            manifest_ecosystems = {"dotnet"}
            entrypoints, roots, configs = _csproj_profile_hints(candidate_path)
        else:
            continue
        detected_ecosystems.update(manifest_ecosystems)
        if _is_non_operational_profile_path(candidate_path):
            entrypoints = set()
            roots = set()
        # ReScript manifests are common in JS/TS host repos, so let them seed
        # candidate collection without automatically winning operational rank.
        if manifest_ecosystems not in ({"rescript"}, {"moonbit"}):
            _accumulate_detected_ecosystem_scores(
                detected_ecosystem_scores,
                ecosystems=manifest_ecosystems,
                config_path=candidate_path,
                repo_path=repo_path,
                entrypoints=entrypoints,
                roots=roots,
                configs=configs,
                preferred_ecosystems=preferred_manifest_ecosystems,
            )
        _register_candidate_ecosystems(
            entrypoint_candidate_ecosystems,
            values=entrypoints,
            ecosystems=manifest_ecosystems,
        )
        _register_candidate_ecosystems(
            support_root_candidate_ecosystems,
            values=roots,
            ecosystems=manifest_ecosystems,
        )
        entrypoint_candidates.update(entrypoints)
        support_root_candidates.update(roots)
        config_path_candidates.update(configs)
