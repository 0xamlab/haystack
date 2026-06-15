"""Tests for test_repository_intelligence_public_repo_matrix: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_1194c44b-086-3/tests/test_repository_intelligence_public_repo_matrix.py during modularization.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import time

from tests._test_repository_intelligence_public_repo_matrix_helpers import *  # noqa: F401,F403

from apps.api_server.services.repository_language_priority import (
    DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    ranked_real_repository_languages,
    supported_repository_languages,
)


def _checkout_context_for(repo_path: Path):
    @contextmanager
    def _context(*_args: object, **_kwargs: object):
        yield repo_path

    return _context


def test_ordered_public_repository_cases_respects_global_rank() -> None:
    cases = (
        public_repo_matrix.PublicRepositoryCase(
            language="zig",
            repository_url="https://github.com/zigtools/zls.git",
            expected_primary_ecosystem="zig",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="python",
            repository_url="https://github.com/pallets/click.git",
            expected_primary_ecosystem="python",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="dart",
            repository_url="https://github.com/dart-lang/http.git",
            expected_primary_ecosystem="dart",
        ),
    )

    ordered_cases = public_repo_matrix.ordered_public_repository_cases(cases=cases)

    assert [case.language for case in ordered_cases] == ["python", "dart", "zig"]


def test_ordered_public_repository_cases_accepts_canonical_language_aliases() -> None:
    cases = (
        public_repo_matrix.PublicRepositoryCase(
            language="common workflow language",
            repository_url="https://github.com/common-workflow-language/user_guide.git",
            expected_primary_ecosystem="common workflow language",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="python",
            repository_url="https://github.com/pallets/click.git",
            expected_primary_ecosystem="python",
        ),
    )

    hyphenated_alias_cases = public_repo_matrix.ordered_public_repository_cases(
        cases=cases,
        languages=("common-workflow-language",),
    )
    short_alias_cases = public_repo_matrix.ordered_public_repository_cases(
        cases=cases,
        languages=("cwl",),
    )

    assert [case.language for case in hyphenated_alias_cases] == [
        "common workflow language"
    ]
    assert [case.language for case in short_alias_cases] == [
        "common workflow language"
    ]


def test_run_public_repository_seed_plan_case_uses_operational_primary_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="dart",
        repository_url="https://github.com/dart-lang/http.git",
        expected_primary_ecosystem="dart",
    )
    repo_path = tmp_path / "dart-http"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        _checkout_context_for(repo_path),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **_kwargs: {
            "candidate_file_paths": ["pkgs/http/lib/http.dart"],
            "entrypoint_files": ["pkgs/http/lib/http.dart"],
            "support_roots": ["pkgs/http/lib"],
            "config_paths": ["pkgs/http/pubspec.yaml"],
            "detected_ecosystems": ["java", "cpp", "dart", "groovy"],
            "operational_ecosystems": ["dart", "java", "cpp", "groovy"],
        },
    )

    result = public_repo_matrix.run_public_repository_seed_plan_case(
        case,
        checkout_root=tmp_path,
    )

    assert result["primary_detected_ecosystem"] == "dart"
    assert result["detected_primary_match"] is True
    assert result["primary_operational_ecosystem"] == "dart"
    assert result["detection_correction_applied"] is False
    assert result["primary_ecosystem"] == "dart"
    assert result["primary_match"] is True


def test_run_public_repository_seed_plan_case_accepts_case_language_alias_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="javascript",
        repository_url="https://github.com/expressjs/express.git",
        expected_primary_ecosystem="node",
    )
    repo_path = tmp_path / "express"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        _checkout_context_for(repo_path),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **_kwargs: {
            "candidate_file_paths": ["lib/application.js", "lib/request.js"],
            "entrypoint_files": ["lib/application.js", "lib/request.js"],
            "support_roots": ["lib"],
            "config_paths": ["package.json"],
            "detected_ecosystems": ["javascript", "node"],
            "operational_ecosystems": ["javascript", "node"],
        },
    )

    result = public_repo_matrix.run_public_repository_seed_plan_case(
        case,
        checkout_root=tmp_path,
    )

    assert result["primary_detected_ecosystem"] in {"javascript", "node"}
    assert result["detected_primary_match"] is True
    assert result["primary_operational_ecosystem"] in {"javascript", "node"}
    assert result["primary_ecosystem"] in {"javascript", "node"}
    assert result["primary_match"] is True


def test_run_public_repository_seed_plan_case_refines_unscoped_expected_surface(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="meson",
        repository_url="https://github.com/frida/frida.git",
        expected_primary_ecosystem="meson",
    )
    repo_path = tmp_path / "frida"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        _checkout_context_for(repo_path),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["."],
    )

    seed_plan_calls: list[list[str]] = []

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_plan_calls.append(focus_paths)
        if focus_paths == ["src"]:
            return {
                "case": public_repo_matrix.asdict(case),
                "candidate_file_paths": ["src/meson.build", "src/main.cc"],
                "config_paths": ["src/meson.build"],
                "entrypoint_files": ["src/main.cc"],
                "support_roots": ["src"],
                "detected_ecosystems": ["c", "meson"],
                "operational_ecosystems": ["c", "meson"],
                "primary_ecosystem": "c",
                "primary_match": False,
            }
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["meson.build", "src/main.cc"],
            "config_paths": ["meson.build"],
            "entrypoint_files": [],
            "support_roots": ["."],
            "detected_ecosystems": ["c", "meson"],
            "operational_ecosystems": ["c", "meson"],
            "primary_ecosystem": "c",
            "primary_match": False,
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **_kwargs: ["src"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["src/meson.build"],
            "config_paths": ["src/meson.build"],
            "entrypoint_files": ["src/meson.build"],
            "support_roots": ["src"],
            "detected_ecosystems": ["meson"],
            "operational_ecosystems": ["meson"],
            "primary_detected_ecosystem": "meson",
            "detected_primary_match": True,
            "primary_operational_ecosystem": "meson",
            "detection_correction_applied": False,
            "primary_ecosystem": "meson",
            "primary_match": True,
            "candidate_file_count": 1,
        },
    )

    result = public_repo_matrix.run_public_repository_seed_plan_case(
        case,
        checkout_root=tmp_path,
    )

    assert seed_plan_calls == [["."]]
    assert result["primary_ecosystem"] == "meson"
    assert result["primary_match"] is True
    assert result["entrypoint_files"] == ["src/meson.build"]


def test_seed_plan_result_for_explicit_focus_case_caches_refined_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    public_repo_matrix.clear_public_repository_probe_attempt_cache()
    case = public_repo_matrix.PublicRepositoryCase(
        language="ocamllex",
        repository_url="https://github.com/let-def/ocamllex-refill.git",
        expected_primary_ecosystem="ocamllex",
        focus_paths=("lexer.mll",),
    )
    repo_path = tmp_path / "ocamllex-refill"
    repo_path.mkdir()
    seed_plan_calls = 0
    focused_calls = 0

    def fake_seed_plan(*_args, **_kwargs):
        nonlocal seed_plan_calls
        seed_plan_calls += 1
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["lexer.mll"],
            "config_paths": [],
            "entrypoint_files": ["lexer.mll"],
            "support_roots": ["."],
            "detected_ecosystems": ["ocamllex"],
            "operational_ecosystems": ["ocamllex"],
            "primary_ecosystem": "ocamllex",
            "primary_match": True,
        }

    def fake_focused_result(**_kwargs):
        nonlocal focused_calls
        focused_calls += 1
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["lexer.mll"],
            "config_paths": [],
            "entrypoint_files": ["lexer.mll"],
            "support_roots": ["."],
            "detected_ecosystems": ["ocamllex"],
            "operational_ecosystems": ["ocamllex"],
            "primary_detected_ecosystem": "ocamllex",
            "detected_primary_match": True,
            "primary_operational_ecosystem": "ocamllex",
            "detection_correction_applied": False,
            "primary_ecosystem": "ocamllex",
            "primary_match": True,
            "candidate_file_count": 1,
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        fake_focused_result,
    )

    first = public_repo_matrix._seed_plan_result_for_explicit_focus_case(
        case,
        repo_path=repo_path,
        max_files=256,
    )
    second = public_repo_matrix._seed_plan_result_for_explicit_focus_case(
        case,
        repo_path=repo_path,
        max_files=256,
    )

    assert first == second
    assert seed_plan_calls == 1
    assert focused_calls == 1


def test_seed_plan_result_for_explicit_focus_case_caches_no_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    public_repo_matrix.clear_public_repository_probe_attempt_cache()
    case = public_repo_matrix.PublicRepositoryCase(
        language="pony",
        repository_url="https://github.com/ponylang/http.git",
        expected_primary_ecosystem="pony",
        focus_paths=("examples",),
    )
    repo_path = tmp_path / "pony-http"
    repo_path.mkdir()
    seed_plan_calls = 0
    focused_calls = 0

    def fake_seed_plan(*_args, **_kwargs):
        nonlocal seed_plan_calls
        seed_plan_calls += 1
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["README.md"],
            "config_paths": [],
            "entrypoint_files": [],
            "support_roots": ["examples"],
            "detected_ecosystems": ["markdown"],
            "operational_ecosystems": ["markdown"],
            "primary_ecosystem": "markdown",
            "primary_match": False,
        }

    def fake_focused_result(**_kwargs):
        nonlocal focused_calls
        focused_calls += 1
        return None

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        fake_focused_result,
    )

    first = public_repo_matrix._seed_plan_result_for_explicit_focus_case(
        case,
        repo_path=repo_path,
        max_files=256,
    )
    second = public_repo_matrix._seed_plan_result_for_explicit_focus_case(
        case,
        repo_path=repo_path,
        max_files=256,
    )

    assert first is None
    assert second is None
    assert seed_plan_calls == 1
    assert focused_calls == 1


def test_run_public_repository_matrix_seed_plan_uses_refined_checkout_helper(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="qml",
        repository_url="https://github.com/qmlbook/qmlbook.git",
        expected_primary_ecosystem="qml",
    )
    repo_path = tmp_path / "qmlbook"
    repo_path.mkdir()
    captured: list[str] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        _checkout_context_for(repo_path),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_seed_plan_case_for_checkout",
        lambda selected_case, *, repo_path, max_files=512: (
            captured.append(str(repo_path))
            or {
                "case": public_repo_matrix.asdict(selected_case),
                "case_key": public_repo_matrix._public_repository_case_key(selected_case),
                "repo_path": str(repo_path),
                "primary_match": True,
            }
        ),
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        cases=[case],
    )

    assert captured == [str(repo_path)]
    assert result["cases"][0]["primary_match"] is True


def test_run_public_repository_probe_case_derives_focus_paths_from_seed_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    repo_path = tmp_path / "typst-packages"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    seed_plan_calls: list[int] = []
    seed_plan_focus_paths: list[object] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["packages"],
    )

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **kwargs: (
            seed_plan_calls.append(int(kwargs["max_files"]))
            or seed_plan_focus_paths.append(list(kwargs["focus_paths"]))
            or {
                "case": public_repo_matrix.asdict(case),
                "candidate_file_paths": ["packages/core/main.typ", "packages/core/typst.toml"],
                "entrypoint_files": ["packages/core/main.typ", "bundler/src/main.rs"],
                "support_roots": ["packages/core", "packages/stdlib", "."],
                "config_paths": ["packages/core/typst.toml"],
                "detected_ecosystems": ["typst", "rust"],
                "operational_ecosystems": ["typst", "rust"],
                "primary_match": True,
            }
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "typst" if path.endswith(".typ") else "rust",
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["node", "typst"],
                "operational_ecosystems": ["typst", "node"],
            },
            "snapshot": {"file_count": 12},
            "connected_map": {"connected_file_count": 6, "seed_files": ["packages/core/main.typ"]},
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["packages/core"]
    assert captured["operational_seed_plan"] == {
        "candidate_file_paths": ["packages/core/main.typ", "packages/core/typst.toml"],
        "config_paths": ["packages/core/typst.toml"],
        "detected_ecosystems": ["typst"],
        "entrypoint_files": ["packages/core/main.typ"],
        "operational_ecosystems": ["typst"],
        "support_roots": ["packages/core"],
    }
    assert seed_plan_calls
    assert seed_plan_calls == [
        public_repo_matrix._PUBLIC_REPOSITORY_PROBE_FOCUS_PREPASS_MAX_FILES
    ] * len(seed_plan_calls)
    assert seed_plan_focus_paths[0] == ["packages"]
    assert result["primary_match"] is True
    assert result["primary_operational_ecosystem"] == "typst"


def test_public_repository_probe_focus_prepass_max_files_caps_budget() -> None:
    assert public_repo_matrix._public_repository_probe_focus_prepass_max_files(8) == 8
    assert (
        public_repo_matrix._public_repository_probe_focus_prepass_max_files(512)
        == public_repo_matrix._PUBLIC_REPOSITORY_PROBE_FOCUS_PREPASS_MAX_FILES
    )


def test_run_public_repository_probe_case_derives_focus_paths_from_expected_support_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="blade",
        repository_url="https://github.com/thedevdojo/genesis.git",
        expected_primary_ecosystem="blade",
    )
    repo_path = tmp_path / "blade-genesis"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    seed_plan_focus_paths: list[list[str]] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["."],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **kwargs: (
            seed_plan_focus_paths.append(list(kwargs["focus_paths"]))
            or (
                {
                    "case": public_repo_matrix.asdict(case),
                    "candidate_file_paths": [
                        "resources/views/welcome.blade.php",
                        "resources/views/pages/index.blade.php",
                    ],
                    "entrypoint_files": [
                        "resources/views/welcome.blade.php",
                        "resources/views/pages/index.blade.php",
                    ],
                    "support_roots": ["resources/views", "resources/views/pages"],
                    "config_paths": [],
                    "detected_ecosystems": ["blade"],
                    "operational_ecosystems": ["blade"],
                    "primary_match": True,
                }
                if list(kwargs["focus_paths"]) == ["resources/views", "resources/views/pages"]
                else {
                    "case": public_repo_matrix.asdict(case),
                    "candidate_file_paths": [
                        "resources/views/welcome.blade.php",
                        "resources/views/pages/index.blade.php",
                        "app/Http/Controllers/Controller.php",
                        "public/index.php",
                        "vite.config.js",
                    ],
                    "entrypoint_files": [
                        "app/Http/Controllers/Controller.php",
                        "public/index.php",
                        "vite.config.js",
                    ],
                    "support_roots": [
                        "resources/views",
                        "resources/views/pages",
                        "app/Http/Controllers",
                        "public",
                    ],
                    "config_paths": ["composer.json", "package.json"],
                    "detected_ecosystems": ["javascript", "node", "php", "blade"],
                    "operational_ecosystems": ["blade", "php", "node", "javascript"],
                    "primary_match": True,
                }
            )
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: (
            "blade"
            if path.endswith(".blade.php")
            else "php"
            if path.endswith(".php")
            else "javascript"
        ),
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["blade"],
                "operational_ecosystems": ["blade"],
            },
            "snapshot": {"file_count": 4},
            "connected_map": {
                "connected_file_count": 2,
                "seed_files": [
                    "resources/views/welcome.blade.php",
                    "resources/views/pages/index.blade.php",
                ],
            },
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["resources/views", "resources/views/pages"]
    assert seed_plan_focus_paths
    assert seed_plan_focus_paths[0] == ["."]
    assert captured["operational_seed_plan"] == {
        "candidate_file_paths": [
            "resources/views/welcome.blade.php",
            "resources/views/pages/index.blade.php",
        ],
        "config_paths": [],
        "detected_ecosystems": ["blade"],
        "entrypoint_files": [
            "resources/views/welcome.blade.php",
            "resources/views/pages/index.blade.php",
        ],
        "operational_ecosystems": ["blade"],
        "support_roots": ["resources/views", "resources/views/pages"],
    }
    assert result["primary_match"] is True
    assert result["primary_operational_ecosystem"] == "blade"


def test_focused_seed_plan_result_falls_back_to_expected_ecosystem_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "blade-focus"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: (
            "blade"
            if path.endswith(".blade.php")
            else "php"
            if path.endswith(".php")
            else "javascript"
        ),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "resources/views/welcome.blade.php",
                "resources/views/pages/index.blade.php",
                "app/Http/Controllers/Controller.php",
            ],
            "entrypoint_files": [
                "app/Http/Controllers/Controller.php",
            ],
            "support_roots": [
                "resources/views",
                "resources/views/pages",
                "app/Http/Controllers",
            ],
            "config_paths": ["composer.json"],
        },
        repo_path=repo_path,
        focus_paths=["resources/views", "resources/views/pages"],
        expected_primary_ecosystem="blade",
    )

    assert focused == {
        "candidate_file_paths": [
            "resources/views/welcome.blade.php",
            "resources/views/pages/index.blade.php",
        ],
        "candidate_file_count": 2,
        "entrypoint_files": [
            "resources/views/welcome.blade.php",
            "resources/views/pages/index.blade.php",
        ],
        "support_roots": ["resources/views", "resources/views/pages"],
        "config_paths": [],
        "detected_ecosystems": ["blade"],
        "operational_ecosystems": ["blade"],
        "primary_detected_ecosystem": "blade",
        "detected_primary_match": True,
        "primary_operational_ecosystem": "blade",
        "detection_correction_applied": False,
        "primary_ecosystem": "blade",
        "primary_match": True,
    }


def test_focused_seed_plan_result_recovers_expected_ecosystem_from_git_inventory_within_focus(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "opencl-focus"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: [
            "samples/core/blur/CMakeLists.txt",
            "samples/core/blur/main.cpp",
            "samples/core/blur/blur.cl",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: (
            {"opencl"}
            if path.endswith(".cl")
            else {"cpp"}
            if path.endswith(".cpp")
            else {"cmake"}
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: (
            "opencl"
            if path.endswith(".cl")
            else "cpp"
            if path.endswith(".cpp")
            else "cmake"
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: path.endswith((".cl", ".cpp")),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda path, repo_path=None: path.endswith(".cl"),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "samples/core/blur/CMakeLists.txt",
                "samples/core/blur/main.cpp",
            ],
            "entrypoint_files": [
                "samples/core/blur/CMakeLists.txt",
                "samples/core/blur/main.cpp",
            ],
            "support_roots": [],
            "config_paths": ["samples/core/blur/CMakeLists.txt"],
        },
        repo_path=repo_path,
        focus_paths=["samples/core/blur"],
        expected_primary_ecosystem="opencl",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == ["samples/core/blur/blur.cl"]
    assert focused["candidate_file_paths"] == ["samples/core/blur/blur.cl"]
    assert focused["support_roots"] == ["samples/core/blur"]
    assert focused["detected_ecosystems"] == ["opencl"]
    assert focused["primary_ecosystem"] == "opencl"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_reuses_cached_tracked_inventory_before_git_focus_listing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "opencl-focus-cached"
    repo_path.mkdir()

    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=[
            "samples/core/blur/CMakeLists.txt",
            "samples/core/blur/main.cpp",
            "samples/core/blur/blur.cl",
        ],
    )

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files_for_focus_paths",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached tracked inventory should bypass focused git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cached tracked inventory should bypass broad git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: (
            {"opencl"}
            if path.endswith(".cl")
            else {"cpp"}
            if path.endswith(".cpp")
            else {"cmake"}
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: (
            "opencl"
            if path.endswith(".cl")
            else "cpp"
            if path.endswith(".cpp")
            else "cmake"
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: path.endswith((".cl", ".cpp")),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda path, repo_path=None: path.endswith(".cl"),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "samples/core/blur/CMakeLists.txt",
                "samples/core/blur/main.cpp",
            ],
            "entrypoint_files": [
                "samples/core/blur/CMakeLists.txt",
                "samples/core/blur/main.cpp",
            ],
            "support_roots": [],
            "config_paths": ["samples/core/blur/CMakeLists.txt"],
        },
        repo_path=repo_path,
        focus_paths=["samples/core/blur"],
        expected_primary_ecosystem="opencl",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == ["samples/core/blur/blur.cl"]
    assert focused["candidate_file_paths"] == ["samples/core/blur/blur.cl"]
    assert focused["support_roots"] == ["samples/core/blur"]
    assert focused["detected_ecosystems"] == ["opencl"]
    assert focused["primary_ecosystem"] == "opencl"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_prefers_hint_only_focus_recovery_before_full_inventory_classification(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "thrift-focus"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files_for_focus_paths",
        lambda _repo_path, *, focus_paths: [
            "test/CMakeLists.txt",
            "test/main.cpp",
            "test/extra_1.cpp",
            "test/extra_2.cpp",
            "test/schema.thrift",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: (_ for _ in ()).throw(
            AssertionError(
                "hint-only focus recovery should not classify non-hinted focused inventory paths"
            )
        )
        if path in {"test/extra_1.cpp", "test/extra_2.cpp"}
        else {"cpp"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "thrift" if path.endswith(".thrift") else "cpp",
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: path.endswith((".thrift", ".cpp")),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda path, repo_path=None: path.endswith(".thrift"),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "test/CMakeLists.txt",
                "test/main.cpp",
            ],
            "entrypoint_files": [
                "test/CMakeLists.txt",
                "test/main.cpp",
            ],
            "support_roots": [],
            "config_paths": ["test/CMakeLists.txt"],
        },
        repo_path=repo_path,
        focus_paths=["test"],
        expected_primary_ecosystem="thrift",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == ["test/schema.thrift"]
    assert focused["candidate_file_paths"] == ["test/schema.thrift"]
    assert focused["support_roots"] == ["test"]
    assert focused["detected_ecosystems"] == ["thrift"]
    assert focused["primary_ecosystem"] == "thrift"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_filters_non_operational_candidates_within_focus(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "python-focus"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: path in {"app/main.py", "app/worker.py"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda path, repo_path=None: path == "app/main.py",
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_supports_expected_ecosystem",
        lambda path, repo_path=None, expected_primary_ecosystem=None: path.endswith(".py"),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_primary_ecosystem",
        lambda path, repo_path=None, expected_primary_ecosystem=None: (
            "python" if path.endswith(".py") else None
        ),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "app/main.py",
                "app/worker.py",
                "app/logo.ico",
                "app/app.rc",
            ],
            "entrypoint_files": [
                "app/main.py",
                "app/logo.ico",
                "app/app.rc",
            ],
            "support_roots": ["app"],
            "config_paths": ["app/pyproject.toml"],
        },
        repo_path=repo_path,
        focus_paths=["app"],
        expected_primary_ecosystem="python",
    )

    assert focused == {
        "candidate_file_paths": ["app/main.py", "app/worker.py"],
        "candidate_file_count": 2,
        "entrypoint_files": ["app/main.py"],
        "support_roots": ["app"],
        "config_paths": ["app/pyproject.toml"],
        "detected_ecosystems": ["python"],
        "operational_ecosystems": ["python"],
        "primary_detected_ecosystem": "python",
        "detected_primary_match": True,
        "primary_operational_ecosystem": "python",
        "detection_correction_applied": False,
        "primary_ecosystem": "python",
        "primary_match": True,
    }


def test_focused_seed_plan_result_trims_non_expected_tied_entrypoint_sidecars(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "python-sidecars"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        lambda path, repo_path=None: path.endswith((".py", ".json")),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        lambda path, repo_path=None: path.endswith((".py", ".json")),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_supports_expected_ecosystem",
        lambda path, repo_path=None, expected_primary_ecosystem=None: path.endswith(".py"),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_primary_ecosystem",
        lambda path, repo_path=None, expected_primary_ecosystem=None: (
            "python" if path.endswith(".py") else "json" if path.endswith(".json") else None
        ),
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "app/main.py",
                "app/worker.py",
                "app/tooling.json",
            ],
            "entrypoint_files": [
                "app/main.py",
                "app/tooling.json",
            ],
            "support_roots": ["app"],
            "config_paths": [],
        },
        repo_path=repo_path,
        focus_paths=["app"],
        expected_primary_ecosystem="python",
    )

    assert focused == {
        "candidate_file_paths": ["app/main.py", "app/worker.py"],
        "candidate_file_count": 2,
        "entrypoint_files": ["app/main.py"],
        "support_roots": ["app"],
        "config_paths": [],
        "detected_ecosystems": ["python"],
        "operational_ecosystems": ["python"],
        "primary_detected_ecosystem": "python",
        "detected_primary_match": True,
        "primary_operational_ecosystem": "python",
        "detection_correction_applied": False,
        "primary_ecosystem": "python",
        "primary_match": True,
    }


def test_focused_seed_plan_result_reuses_path_classification_within_single_focus_pass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "classification-cache"
    repo_path.mkdir()
    call_counts = {
        "repo_profile": 0,
        "entrypoint": 0,
        "supports": 0,
        "primary": 0,
    }

    def _is_repo_profile_code_candidate(path: str, repo_path=None) -> bool:
        call_counts["repo_profile"] += 1
        return path == "app/main.v"

    def _is_operational_profile_entrypoint_candidate(path: str, repo_path=None) -> bool:
        call_counts["entrypoint"] += 1
        return path == "app/main.v"

    def _path_supports_expected_ecosystem(
        path: str,
        repo_path=None,
        expected_primary_ecosystem=None,
    ) -> bool:
        call_counts["supports"] += 1
        return path == "app/main.v"

    def _path_primary_ecosystem(
        path: str,
        repo_path=None,
        expected_primary_ecosystem=None,
    ) -> str | None:
        call_counts["primary"] += 1
        return "v" if path == "app/main.v" else None

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_repo_profile_code_candidate",
        _is_repo_profile_code_candidate,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_is_operational_profile_entrypoint_candidate",
        _is_operational_profile_entrypoint_candidate,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_supports_expected_ecosystem",
        _path_supports_expected_ecosystem,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_primary_ecosystem",
        _path_primary_ecosystem,
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": ["app/main.v", "app/main.v"],
            "entrypoint_files": ["app/main.v", "app/main.v"],
            "support_roots": ["app"],
            "config_paths": ["app/v.mod"],
        },
        repo_path=repo_path,
        focus_paths=["app"],
        expected_primary_ecosystem="v",
    )

    assert focused is not None
    assert focused["candidate_file_paths"] == ["app/main.v", "app/main.v"]
    assert focused["entrypoint_files"] == ["app/main.v", "app/main.v"]
    assert call_counts == {
        "repo_profile": 1,
        "entrypoint": 0,
        "supports": 1,
        "primary": 1,
    }


def test_path_matches_expected_ecosystem_hint_supports_keyword_only_adapters() -> None:
    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "build.gradle",
        expected_primary_ecosystem="groovy",
    )


def test_expected_ecosystem_focus_paths_collapse_versioned_package_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "registry"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "typst" if path.endswith(".typ") else "rust",
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "packages/preview/blockst/0.2.1/lib.typ",
            "packages/preview/blockst/0.2.0/package.typ",
            "packages/preview/quonom/0.1.0/src/lib.typ",
            "bundler/src/main.rs",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="typst",
    )

    assert focus_paths == [
        "packages/preview/blockst",
        "packages/preview/quonom",
    ]


def test_expected_ecosystem_focus_paths_collapse_prefixed_versioned_package_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "delphi-packages"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"delphi"} if path.endswith((".dpk", ".res")) else {"text"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "packages/RAD Studio 10.0/VSoft.DUnitXWinR.dpk",
            "packages/RAD Studio 10.1/VSoft.DUnitXWinR.dpk",
            "packages/RAD Studio 12.0/VSoft.DUnitXWinR.dpk",
            "Expert/DUnitX_IDE_Expert_2010.dpk",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="delphi",
    )

    assert focus_paths == [
        "Expert",
        "packages/RAD Studio",
    ]


def test_expected_ecosystem_focus_paths_collapse_alpha_prefixed_versioned_package_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "delphi-xe-packages"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"delphi"} if path.endswith(".dpk") else {"text"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "packages/RAD Studio XE2/VSoft.DUnitXWinR.dpk",
            "packages/RAD Studio XE3/VSoft.DUnitXWinR.dpk",
            "packages/RAD Studio XE8/VSoft.DUnitXWinR.dpk",
            "Expert/DUnitX_IDE_Expert_XE8.dpk",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="delphi",
    )

    assert focus_paths == [
        "Expert",
        "packages/RAD Studio XE",
    ]


def test_expected_ecosystem_focus_paths_short_circuits_after_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "registry"
    repo_path.mkdir()
    inspected_paths: list[str] = []
    match_limit = public_repo_matrix._PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT * 16
    relative_paths = [f"packages/pkg-{index:03d}/1.0.0/lib.typ" for index in range(512)]

    def fake_probe_language_for_path(path: str, repo_path=None) -> str:
        inspected_paths.append(path)
        return "typst"

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        fake_probe_language_for_path,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_path_matches_expected_ecosystem_hint",
        lambda *args, **kwargs: False,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=relative_paths,
        repo_path=repo_path,
        expected_primary_ecosystem="typst",
    )

    assert len(inspected_paths) == match_limit
    assert focus_paths[:3] == [
        "packages/pkg-000",
        "packages/pkg-001",
        "packages/pkg-002",
    ]


def test_expected_ecosystem_focus_paths_include_cmake_project_roots(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "cmake-examples"
    (repo_path / "01-basic" / "A-hello-cmake").mkdir(parents=True)
    (repo_path / "04-static-analysis" / "clang-format" / "cmake" / "modules").mkdir(parents=True)
    (repo_path / "01-basic" / "A-hello-cmake" / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.20)\nproject(hello LANGUAGES CXX)\n",
        encoding="utf-8",
    )
    (repo_path / "04-static-analysis" / "clang-format" / "cmake" / "modules" / "FindClangFormat.cmake").write_text(
        "find_program(CLANG_FORMAT_EXE NAMES clang-format)\n",
        encoding="utf-8",
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "01-basic/A-hello-cmake/CMakeLists.txt",
            "04-static-analysis/clang-format/cmake/modules/FindClangFormat.cmake",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="cmake",
    )

    assert "01-basic/A-hello-cmake" in focus_paths


def test_expected_ecosystem_focus_paths_match_canonical_aliases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "phoenix"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "ex" if path.endswith((".ex", ".exs")) else "javascript",
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "lib/phoenix.ex",
            "config/config.exs",
            "assets/js/phoenix/index.js",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="elixir",
    )

    assert focus_paths == ["config", "lib"]


def test_expected_ecosystem_focus_paths_match_candidate_family_ecosystems(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "express"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"javascript", "node"}
        if path.endswith(".js")
        else {"json"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "lib/application.js",
            "lib/request.js",
            "package.json",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="node",
    )

    assert focus_paths == ["lib"]


def test_expected_ecosystem_prepass_focus_paths_reuse_clone_time_focus_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="astro",
        repository_url="https://github.com/withastro/astro.build.git",
        expected_primary_ecosystem="astro",
    )
    repo_path = tmp_path / "astro-build"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_tracked_relative_files",
        lambda **_kwargs: [
            "src/pages/index.astro",
            "src/components/Hero.astro",
            "package.json",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_focus_paths_from_relative_files",
        lambda **_kwargs: ["src/pages", "src/components"],
    )

    clone_focus_paths = public_repo_matrix._public_repository_sparse_checkout_focus_paths(
        case,
        git_executable="git",
        checkout_path=repo_path,
        repository_url=case.repository_url,
    )

    def _unexpected_git_repo_relative_files(_repo_path: Path) -> list[str]:
        raise AssertionError("prepass focus paths should reuse clone-time cache")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        _unexpected_git_repo_relative_files,
    )

    prepass_focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="astro",
    )

    assert clone_focus_paths == ["src/pages", "src/components"]
    assert prepass_focus_paths == ["src/pages", "src/components"]


def test_expected_ecosystem_prepass_focus_paths_recompute_after_empty_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "opencl-sdk"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
        focus_paths=[],
    )

    assert (
        public_repo_matrix._cached_public_repository_prepass_focus_paths(
            repo_path=repo_path,
            expected_primary_ecosystem="opencl",
        )
        is None
    )

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: [
            "samples/core/binaries/Collatz.cl",
            "samples/core/binaries/CMakeLists.txt",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"opencl"} if path.endswith(".cl") else {"cmake"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
    )

    assert focus_paths == ["samples/core/binaries"]


def test_expected_ecosystem_prepass_focus_paths_use_cached_tracked_files_before_git_listing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "cached-tracked-prepass-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=[
            "src/Feature01/Action01.php",
            "src/Feature02/Action02.php",
            "docs/readme.md",
        ],
    )

    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_git_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("tracked-file cache should skip hint git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("tracked-file cache should skip full repo git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="php",
    )

    assert focus_paths == ["src/Feature01", "src/Feature02"]


def test_store_public_repository_prepass_focus_paths_preserves_more_specific_cached_focus_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-prepass-cache-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    granular_focus_paths = [
        "Package.swift",
        "Plugins/GenerateCommon",
        "Plugins/GenerateDoccReference",
        "Plugins/GenerateManual",
        "Sources/ArgumentParser/Completions",
        "Sources/ArgumentParser/Parsable Properties",
        "Sources/ArgumentParser/Parsable Types",
        "Sources/ArgumentParser/Parsing",
        "Examples/color",
        "Examples/count-lines",
        "Examples/default-as-flag",
        "Examples/math",
    ]

    cached_focus_paths = public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="swift",
        focus_paths=granular_focus_paths,
    )
    preserved_focus_paths = public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="swift",
        focus_paths=["Sources"],
    )

    assert cached_focus_paths == granular_focus_paths
    assert preserved_focus_paths == granular_focus_paths
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="swift",
    ) == granular_focus_paths


def test_store_public_repository_prepass_focus_paths_replaces_broader_cached_focus_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "narrowing-prepass-cache-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    cached_focus_paths = public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="typescript",
        focus_paths=["src"],
    )
    refined_focus_paths = public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="typescript",
        focus_paths=["src/components", "src/pages"],
    )

    assert cached_focus_paths == ["src"]
    assert refined_focus_paths == ["src/components", "src/pages"]
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="typescript",
    ) == ["src/components", "src/pages"]


def test_expected_ecosystem_prepass_focus_paths_skip_full_listing_when_hint_slice_is_sufficient(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "hint-only-prepass-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    hint_relative_paths = [f"packages/pkg{index}/src/lib.typ" for index in range(36)]
    git_commands: list[list[str]] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_hint_pathspecs",
        lambda _ecosystem: (":(glob)**/*.typ",),
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_git_command",
        lambda args, timeout=120.0: git_commands.append(list(args)) or "\n".join(hint_relative_paths),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("sufficient hint-only prepass should skip whole-repo git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="typst",
    )

    assert len(focus_paths) == public_repo_matrix._PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT
    assert git_commands[0][3] == "ls-files"
    assert focus_paths[:3] == [
        "packages/pkg0/src",
        "packages/pkg1/src",
        "packages/pkg10/src",
    ]


def test_expected_ecosystem_prepass_focus_paths_use_hint_slice_before_cached_tracked_listing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "hint-before-cached-tracked-prepass-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    hint_relative_paths = [f"styles/theme{index:02d}.less" for index in range(36)]
    tracked_relative_paths = [
        *hint_relative_paths,
        *[f"icons/{index:04d}.svg" for index in range(256)],
    ]
    git_commands: list[list[str]] = []
    ranked_relative_path_batches: list[list[str]] = []

    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=tracked_relative_paths,
    )

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_hint_pathspecs",
        lambda _ecosystem: (":(glob)**/*.less",),
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_git_command",
        lambda args, timeout=120.0: git_commands.append(list(args)) or "\n".join(hint_relative_paths),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("cached tracked-file prepass should not fall back to full repo listing")
        ),
    )

    original_ranker = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files

    def _recording_ranker(*, relative_paths, repo_path, expected_primary_ecosystem, limit=12):
        ranked_relative_path_batches.append(list(relative_paths))
        return original_ranker(
            relative_paths=relative_paths,
            repo_path=repo_path,
            expected_primary_ecosystem=expected_primary_ecosystem,
            limit=limit,
        )

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_focus_paths_from_relative_files",
        _recording_ranker,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="less",
    )

    assert focus_paths == ["styles"]
    assert git_commands[0][3] == "ls-files"
    assert ranked_relative_path_batches == [hint_relative_paths]


def test_expected_ecosystem_prepass_focus_paths_fall_back_when_hint_slice_is_too_small(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "hint-fallback-prepass-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    git_listing_calls = {"full": 0}

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_hint_pathspecs",
        lambda _ecosystem: (":(glob)**/*.cl",),
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_git_command",
        lambda args, timeout=120.0: "kernels/add.cl",
    )

    def _full_git_listing(_repo_path: Path) -> list[str]:
        git_listing_calls["full"] += 1
        return [
            "kernels/add.cl",
            "kernels/lib/math.clh",
        ]

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        _full_git_listing,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
    )

    assert focus_paths == ["kernels"]
    assert git_listing_calls["full"] == 1


def test_expected_ecosystem_hint_pathspecs_infer_static_suffixes_for_builtin_languages() -> None:
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    pathspecs = public_repo_matrix._expected_ecosystem_hint_pathspecs("php")

    assert ":(glob)*.php" in pathspecs
    assert ":(glob)**/*.php" in pathspecs


def test_expected_ecosystem_hint_metadata_skips_static_suffix_scan_when_adapter_suffixes_exist(
    monkeypatch,
) -> None:
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    class _FakeThriftAdapter:
        THRIFT_SUFFIXES = (".thrift",)

        @staticmethod
        def has_thrift_path_hints(*, path: Path) -> bool:
            return path.suffix == ".thrift"

    monkeypatch.setattr(
        public_repo_matrix.repository_compat_exports,
        "get_export",
        lambda name: _FakeThriftAdapter if name == "thrift_adapter" else (_ for _ in ()).throw(AttributeError(name)),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_static_hint_suffixes",
        lambda ecosystem: (_ for _ in ()).throw(
            AssertionError(
                "static suffix inference should be skipped when adapter suffixes already exist"
            )
        ),
    )

    metadata = public_repo_matrix._expected_ecosystem_hint_metadata("thrift")

    assert metadata[3] == frozenset({".thrift"})


def test_expected_ecosystem_prepass_focus_paths_use_static_suffix_pathspecs_for_builtin_languages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "php-static-hint-prepass-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    git_commands: list[list[str]] = []

    hint_relative_paths = [
        f"src/Feature{index:02d}/Action{index:02d}.php" for index in range(36)
    ]

    def _fake_git_command(args: list[str], timeout: float = 120.0) -> str:
        git_commands.append(list(args))
        return "\n".join(hint_relative_paths)

    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_git_command",
        _fake_git_command,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_git_repo_relative_files",
        lambda _repo_path: (_ for _ in ()).throw(
            AssertionError("builtin static suffix prepass should skip whole-repo git listing")
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    focus_paths = public_repo_matrix._expected_ecosystem_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="php",
    )

    assert len(focus_paths) == public_repo_matrix._PUBLIC_REPOSITORY_PREPASS_FOCUS_LIMIT
    assert git_commands[0][3] == "ls-files"
    assert ":(glob)*.php" in git_commands[0]
    assert ":(glob)**/*.php" in git_commands[0]


def test_run_public_repository_seed_plan_for_checkout_reuses_process_local_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="freebasic",
        repository_url="https://github.com/freebasic/fbc.git",
        expected_primary_ecosystem="freebasic",
    )
    repo_path = tmp_path / "freebasic-fbc"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    derive_calls = 0

    def _fake_derive_operational_seed_plan_without_diagnostics(**_kwargs):
        nonlocal derive_calls
        derive_calls += 1
        return {
            "candidate_file_paths": ["examples/DOS/gfxsleep.bas"],
            "entrypoint_files": ["examples/DOS/gfxsleep.bas"],
            "support_roots": ["examples/DOS"],
            "config_paths": ["makefile"],
            "detected_ecosystems": ["freebasic"],
            "operational_ecosystems": ["freebasic"],
        }

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        _fake_derive_operational_seed_plan_without_diagnostics,
    )

    first = public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )
    first["entrypoint_files"].append("mutated.bas")

    second = public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )

    assert derive_calls == 1
    assert second["entrypoint_files"] == ["examples/DOS/gfxsleep.bas"]
    assert second["support_roots"] == ["examples/DOS"]


def test_run_public_repository_seed_plan_for_checkout_seeds_tracked_relative_files_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import benchmarks.repository_intelligence_real_repo_probe_collection_support as collection_support

    class _StopSeedPlan(RuntimeError):
        pass

    case = public_repo_matrix.PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    )
    repo_path = tmp_path / "sinatra"
    repo_path.mkdir()
    seeded_calls: list[tuple[Path, list[str], bool]] = []

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=["lib/sinatra.rb", "README.md"],
    )

    monkeypatch.setattr(
        collection_support,
        "seed_git_repo_relative_files_cache",
        lambda seeded_repo_path, relative_paths, *, relative_paths_are_canonical=False: seeded_calls.append(
            (seeded_repo_path, list(relative_paths), relative_paths_are_canonical)
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **_kwargs: (_ for _ in ()).throw(_StopSeedPlan()),
    )

    with pytest.raises(_StopSeedPlan):
        public_repo_matrix._run_public_repository_seed_plan_for_checkout(
            case,
            repo_path=repo_path,
        )

    assert seeded_calls == [
        (repo_path, ["README.md", "lib/sinatra.rb"], True),
    ]


def test_run_seed_plan_case_for_checkout_applies_focused_refinement_for_explicit_focus_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="ampl",
        repository_url="https://github.com/ampl/ampl.github.io.git",
        expected_primary_ecosystem="ampl",
        focus_paths=["models"],
    )
    repo_path = tmp_path / "ampl-github-io"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda selected_case, *, repo_path, max_files=512, focus_paths=(): {
            "case": public_repo_matrix.asdict(selected_case),
            "candidate_file_paths": [
                "models/car-sequencing/README.rst",
                "models/cutting-stock-java/cut.mod",
            ],
            "entrypoint_files": [
                "models/car-sequencing/README.rst",
                "models/cutting-stock-java/cut.mod",
            ],
            "support_roots": ["models/car-sequencing", "models/cutting-stock-java"],
            "config_paths": [],
            "detected_ecosystems": ["rst", "ampl"],
            "operational_ecosystems": ["rst", "ampl"],
            "primary_ecosystem": "rst",
            "primary_match": False,
        },
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["models/cutting-stock-java/cut.mod"],
            "entrypoint_files": ["models/cutting-stock-java/cut.mod"],
            "support_roots": ["models/cutting-stock-java"],
            "config_paths": [],
            "detected_ecosystems": ["ampl"],
            "operational_ecosystems": ["ampl"],
            "primary_detected_ecosystem": "ampl",
            "detected_primary_match": True,
            "primary_operational_ecosystem": "ampl",
            "detection_correction_applied": False,
            "primary_ecosystem": "ampl",
            "primary_match": True,
            "candidate_file_count": 1,
        },
    )

    result = public_repo_matrix._run_seed_plan_case_for_checkout(
        case,
        repo_path=repo_path,
    )

    assert result["primary_ecosystem"] == "ampl"
    assert result["primary_match"] is True
    assert result["entrypoint_files"] == ["models/cutting-stock-java/cut.mod"]


def test_run_public_repository_seed_plan_for_checkout_invalidates_cache_on_fingerprint_change(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="freebasic",
        repository_url="https://github.com/freebasic/fbc.git",
        expected_primary_ecosystem="freebasic",
    )
    repo_path = tmp_path / "freebasic-fbc"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    derive_calls = 0
    fingerprint_state = {"value": "fingerprint-v1"}

    def _fake_derive_operational_seed_plan_without_diagnostics(**_kwargs):
        nonlocal derive_calls
        derive_calls += 1
        return {
            "candidate_file_paths": ["examples/DOS/gfxsleep.bas"],
            "entrypoint_files": ["examples/DOS/gfxsleep.bas"],
            "support_roots": ["examples/DOS"],
            "config_paths": ["makefile"],
            "detected_ecosystems": ["freebasic"],
            "operational_ecosystems": ["freebasic"],
        }

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        _fake_derive_operational_seed_plan_without_diagnostics,
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_cache,
        "_analysis_implementation_fingerprint",
        lambda: fingerprint_state["value"],
    )

    public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )
    public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )
    fingerprint_state["value"] = "fingerprint-v2"
    public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )

    assert derive_calls == 2


def test_clear_public_repository_prepass_focus_path_cache_clears_seed_plan_result_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="freebasic",
        repository_url="https://github.com/freebasic/fbc.git",
        expected_primary_ecosystem="freebasic",
    )
    repo_path = tmp_path / "freebasic-fbc"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    derive_calls = 0

    def _fake_derive_operational_seed_plan_without_diagnostics(**_kwargs):
        nonlocal derive_calls
        derive_calls += 1
        return {
            "candidate_file_paths": ["examples/DOS/gfxsleep.bas"],
            "entrypoint_files": ["examples/DOS/gfxsleep.bas"],
            "support_roots": ["examples/DOS"],
            "config_paths": ["makefile"],
            "detected_ecosystems": ["freebasic"],
            "operational_ecosystems": ["freebasic"],
        }

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        _fake_derive_operational_seed_plan_without_diagnostics,
    )

    public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._run_public_repository_seed_plan_for_checkout(
        case,
        repo_path=repo_path,
        max_files=128,
        focus_paths=["examples/DOS"],
    )

    assert derive_calls == 2


def test_clear_public_repository_probe_attempt_cache_preserves_prepass_focus_paths_when_requested(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "swift-prepass-focus-cache"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="swift",
        focus_paths=["Sources", "Examples"],
    )
    public_repo_matrix.clear_public_repository_probe_attempt_cache(
        preserve_prepass_focus_paths=True,
    )

    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="swift",
    ) == ["Sources", "Examples"]


def test_clear_public_repository_probe_attempt_cache_preserves_seed_plan_results_when_requested(
    tmp_path: Path,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="motoko",
        repository_url="https://github.com/dfinity/motoko-base.git",
        expected_primary_ecosystem="motoko",
    )
    repo_path = tmp_path / "motoko-base"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    expected_result = {
        "case": {
            "language": "motoko",
            "repository_url": "https://github.com/dfinity/motoko-base.git",
        },
        "candidate_file_paths": ["src/Array.mo"],
        "entrypoint_files": ["src/Array.mo"],
        "support_roots": ["src"],
        "config_paths": ["mops.toml"],
        "detected_ecosystems": ["motoko"],
        "operational_ecosystems": ["motoko"],
        "primary_ecosystem": "motoko",
        "primary_match": True,
    }
    public_repo_matrix._store_public_repository_seed_plan_result(
        case=case,
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
        result=expected_result,
    )

    public_repo_matrix.clear_public_repository_probe_attempt_cache(
        preserve_seed_plan_results=True,
    )

    assert public_repo_matrix._cached_public_repository_seed_plan_result(
        case=case,
        repo_path=repo_path,
        focus_paths=["src"],
        max_files=128,
    ) == expected_result


def test_clear_public_repository_probe_attempt_cache_preserves_refined_unscoped_probe_plan_when_requested(
    tmp_path: Path,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="motoko",
        repository_url="https://github.com/dfinity/motoko-base.git",
        expected_primary_ecosystem="motoko",
    )
    repo_path = tmp_path / "motoko-base-refined"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    expected_result = {
        "case": {
            "language": "motoko",
            "repository_url": "https://github.com/dfinity/motoko-base.git",
        },
        "candidate_file_paths": ["src/Array.mo"],
        "entrypoint_files": ["src/Array.mo"],
        "support_roots": ["src"],
        "config_paths": ["mops.toml"],
        "detected_ecosystems": ["motoko"],
        "operational_ecosystems": ["motoko"],
        "primary_ecosystem": "motoko",
        "primary_match": True,
    }
    public_repo_matrix._store_public_repository_refined_unscoped_probe_plan(
        case=case,
        repo_path=repo_path,
        max_files=128,
        seed_plan_result=expected_result,
        probe_focus_paths=["src"],
    )

    public_repo_matrix.clear_public_repository_probe_attempt_cache(
        preserve_seed_plan_results=True,
    )

    assert public_repo_matrix._cached_public_repository_refined_unscoped_probe_plan(
        case=case,
        repo_path=repo_path,
        max_files=128,
    ) == (expected_result, ["src"])


def test_clear_public_repository_probe_attempt_cache_preserves_expected_ecosystem_hints_when_requested() -> None:
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE["swift"] = (
        None,
        False,
        frozenset({"package.swift"}),
        frozenset({".swift"}),
    )
    public_repo_matrix._expected_ecosystem_static_hint_suffixes("swift")
    public_repo_matrix._expected_ecosystem_hint_pathspecs("swift")
    public_repo_matrix._path_basename_and_suffix("Sources/App/main.swift")
    public_repo_matrix._static_language_hint_for_path("main.swift")
    public_repo_matrix._path_matches_expected_ecosystem_hint_cached(
        "Sources/App/main.swift",
        "swift",
    )

    public_repo_matrix.clear_public_repository_probe_attempt_cache(
        preserve_expected_ecosystem_hints=True,
    )

    assert public_repo_matrix._EXPECTED_ECOSYSTEM_HINT_METADATA_CACHE["swift"] == (
        None,
        False,
        frozenset({"package.swift"}),
        frozenset({".swift"}),
    )
    assert public_repo_matrix._expected_ecosystem_static_hint_suffixes.cache_info().currsize > 0
    assert public_repo_matrix._expected_ecosystem_hint_pathspecs.cache_info().currsize > 0
    assert public_repo_matrix._path_basename_and_suffix.cache_info().currsize > 0
    assert public_repo_matrix._static_language_hint_for_path.cache_info().currsize > 0
    assert public_repo_matrix._path_matches_expected_ecosystem_hint_cached.cache_info().currsize > 0


def test_refine_seed_plan_result_for_unscoped_case_reuses_cached_refined_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="ml",
        repository_url="https://github.com/minoki/LunarML.git",
        expected_primary_ecosystem="ml",
    )
    repo_path = tmp_path / "lunarml"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    run_seed_plan_calls: list[list[str]] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["src"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **kwargs: (
            run_seed_plan_calls.append(list(kwargs["focus_paths"]))
            or {
                "case": public_repo_matrix.asdict(case),
                "candidate_file_paths": ["src/main.sml"],
                "entrypoint_files": ["src/main.sml"],
                "support_roots": ["src"],
                "config_paths": [],
                "detected_ecosystems": ["sml"],
                "operational_ecosystems": ["sml"],
                "primary_ecosystem": "sml",
                "primary_match": True,
            }
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **_kwargs: ["src"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: kwargs["seed_plan_result"],
    )

    first = public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
        case,
        repo_path=repo_path,
        max_files=128,
    )
    second = public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
        case,
        repo_path=repo_path,
        max_files=128,
    )

    assert run_seed_plan_calls == [["src"]]
    assert first == second
    assert second[1] == ["src"]


def test_static_language_hint_for_path_uses_direct_probe_hint_before_repository_indexing(
    monkeypatch,
) -> None:
    public_repo_matrix._static_language_hint_for_path.cache_clear()

    def _unexpected_language_for_path(*_args, **_kwargs) -> str:
        raise AssertionError("expected direct probe hint to short-circuit repository indexing")

    monkeypatch.setattr(
        public_repo_matrix.repository_indexing,
        "_language_for_path",
        _unexpected_language_for_path,
    )

    assert public_repo_matrix._static_language_hint_for_path("Package.swift") == "swift"


def test_clear_public_repository_probe_attempt_cache_preserves_path_candidate_ecosystems_when_requested(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "objectivec-candidate-ecosystem-cache"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE[
        (str(repo_path.resolve()), "AFNetworking/AFHTTPSessionManager.m")
    ] = frozenset({"objectivec"})

    public_repo_matrix.clear_public_repository_probe_attempt_cache(
        preserve_path_candidate_ecosystems=True,
    )

    assert public_repo_matrix._PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE == {
        (str(repo_path.resolve()), "AFNetworking/AFHTTPSessionManager.m"): frozenset(
            {"objectivec"}
        )
    }


def test_public_repository_cache_keys_skip_resolve_for_absolute_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "absolute-cache-key-repo"
    repo_path.mkdir()
    path_type = type(repo_path)

    monkeypatch.setattr(
        path_type,
        "resolve",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("absolute public repository cache keys should not call resolve")
        ),
    )

    assert public_repo_matrix._public_repository_tracked_relative_files_cache_key(
        repo_path
    ) == str(repo_path)
    assert public_repo_matrix._public_repository_head_revision_cache_key(repo_path) == str(
        repo_path
    )
    assert public_repo_matrix._public_repository_reusable_checkout_cache_key(
        repo_path
    ) == str(repo_path)


def test_cached_public_repository_candidate_config_focus_paths_reuses_cached_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "candidate-config-focus-repo"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    calls: list[tuple[Path, tuple[str, ...], Path, str | None]] = []

    def fake_candidate_config_focus_paths(
        *,
        repo_path: Path,
        focus_paths: list[str],
        diagnostic_base_path: Path,
        diagnostic_project_path: str | None,
    ) -> list[str]:
        calls.append(
            (
                repo_path,
                tuple(focus_paths),
                diagnostic_base_path,
                diagnostic_project_path,
            )
        )
        return ["src", "package.json"]

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_config_focus_paths",
        fake_candidate_config_focus_paths,
    )

    first = public_repo_matrix._cached_public_repository_candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["src"],
        diagnostic_base_path=repo_path,
        diagnostic_project_path=None,
    )
    assert first is None

    stored = public_repo_matrix._store_public_repository_candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["src"],
        diagnostic_base_path=repo_path,
        diagnostic_project_path=None,
        config_focus_paths=public_repo_matrix.probe_module._candidate_config_focus_paths(
            repo_path=repo_path,
            focus_paths=["src"],
            diagnostic_base_path=repo_path,
            diagnostic_project_path=None,
        ),
    )
    cached = public_repo_matrix._cached_public_repository_candidate_config_focus_paths(
        repo_path=repo_path,
        focus_paths=["src"],
        diagnostic_base_path=repo_path,
        diagnostic_project_path=None,
    )

    assert calls == [(repo_path, ("src",), repo_path, None)]
    assert stored == ["src", "package.json"]
    assert cached == ["src", "package.json"]


def test_run_public_repository_seed_plan_for_checkout_normalizes_relative_repo_path(
    monkeypatch,
) -> None:
    class _StopSeedPlan(RuntimeError):
        pass

    case = public_repo_matrix.PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    )
    relative_repo_path = Path("build/relative-seed-plan-repo")
    seen_repo_paths: list[Path] = []

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_derive_operational_seed_plan_without_diagnostics",
        lambda **kwargs: seen_repo_paths.append(kwargs["repo_path"])
        or (_ for _ in ()).throw(_StopSeedPlan()),
    )

    with pytest.raises(_StopSeedPlan):
        public_repo_matrix._run_public_repository_seed_plan_for_checkout(
            case,
            repo_path=relative_repo_path,
        )

    assert seen_repo_paths
    assert seen_repo_paths == [relative_repo_path.resolve()]


def test_clone_public_repository_case_warms_reusable_sparse_checkout_caches(
    tmp_path: Path,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    )
    checkout_path = tmp_path / public_repo_matrix._case_checkout_name(case)
    (checkout_path / ".git" / "info").mkdir(parents=True)
    (checkout_path / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n",
        encoding="utf-8",
    )
    (checkout_path / ".git" / "info" / "sparse-checkout").write_text(
        "/lib\n/lib/**\n/examples\n/examples/**\n",
        encoding="utf-8",
    )
    (checkout_path / "lib").mkdir()
    (checkout_path / "examples").mkdir()
    (checkout_path / "lib" / "sinatra.rb").write_text("module Sinatra; end\n", encoding="utf-8")
    (checkout_path / "examples" / "hello.rb").write_text("puts 'hello'\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    original_checkout_command = public_repo_matrix._run_public_repository_checkout_command

    class _CompletedProcess:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    public_repo_matrix._run_public_repository_checkout_command = lambda **kwargs: _CompletedProcess(
        "a" * 40 + "\n"
    )
    try:
        result = public_repo_matrix._clone_public_repository_case_unlocked(
            case,
            checkout_root=tmp_path,
            refresh=False,
        )
    finally:
        public_repo_matrix._run_public_repository_checkout_command = original_checkout_command

    assert result == checkout_path
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem="ruby",
    ) == ["lib", "examples"]
    assert public_repo_matrix._cached_public_repository_tracked_relative_files(
        checkout_path
    ) == ["lib/sinatra.rb", "examples/hello.rb"]
    assert public_repo_matrix._cached_public_repository_head_revision(checkout_path) == "a" * 40


def test_clone_public_repository_case_warms_reusable_full_checkout_tracked_files_cache(
    tmp_path: Path,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="c",
        repository_url="https://github.com/libcheck/check.git",
        expected_primary_ecosystem="c",
    )
    checkout_path = tmp_path / public_repo_matrix._case_checkout_name(case)
    (checkout_path / ".git").mkdir(parents=True)
    (checkout_path / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n",
        encoding="utf-8",
    )

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    original_checkout_command = public_repo_matrix._run_public_repository_checkout_command

    class _CompletedProcess:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str) -> None:
            self.stdout = stdout

    def fake_checkout_command(**kwargs):
        git_args = list(kwargs["git_args"])
        if git_args == ["rev-parse", "HEAD"]:
            return _CompletedProcess("b" * 40 + "\n")
        if git_args == ["ls-tree", "-r", "--name-only", "--full-tree", "HEAD"]:
            return _CompletedProcess(
                "src/main.c\ninclude/main.h\nREADME.md\n"
            )
        raise AssertionError(f"unexpected git args: {git_args}")

    public_repo_matrix._run_public_repository_checkout_command = fake_checkout_command
    try:
        result = public_repo_matrix._clone_public_repository_case_unlocked(
            case,
            checkout_root=tmp_path,
            refresh=False,
        )
    finally:
        public_repo_matrix._run_public_repository_checkout_command = original_checkout_command

    assert result == checkout_path
    assert (
        public_repo_matrix._cached_public_repository_prepass_focus_paths(
            repo_path=checkout_path,
            expected_primary_ecosystem="c",
        )
        == ["src", "include"]
    )
    assert public_repo_matrix._cached_public_repository_tracked_relative_files(
        checkout_path
    ) == ["README.md", "include/main.h", "src/main.c"]
    assert public_repo_matrix._cached_public_repository_head_revision(checkout_path) == "b" * 40


def test_clone_public_repository_case_refresh_invalidates_repo_scoped_caches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    )
    checkout_path = tmp_path / public_repo_matrix._case_checkout_name(case)
    (checkout_path / ".git" / "info").mkdir(parents=True)
    (checkout_path / ".git" / "info" / "sparse-checkout").write_text(
        "/lib\n/lib/**\n",
        encoding="utf-8",
    )
    (checkout_path / "lib").mkdir(parents=True)
    (checkout_path / "lib" / "old.rb").write_text("module Old; end\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem="ruby",
        focus_paths=["lib"],
    )
    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=checkout_path,
        relative_paths=["lib/old.rb"],
    )
    public_repo_matrix._store_public_repository_seed_plan_result(
        case=case,
        repo_path=checkout_path,
        focus_paths=["lib"],
        max_files=32,
        result={
            "primary_match": True,
            "entrypoint_files": ["lib/old.rb"],
            "detected_ecosystems": ["ruby"],
            "operational_ecosystems": ["ruby"],
        },
    )
    public_repo_matrix._path_candidate_ecosystems(
        "lib/old.rb",
        repo_path=checkout_path,
    )

    monkeypatch.setattr(public_repo_matrix, "_git_executable", lambda: "git")
    monkeypatch.setattr(
        public_repo_matrix,
        "_validated_public_repository_url",
        lambda repository_url: repository_url,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_clone_command",
        lambda **kwargs: ["git", "clone", "dummy"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_clone_environment",
        lambda: {},
    )

    class _CompletedProcess:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(
        public_repo_matrix.subprocess,
        "run",
        lambda *args, **kwargs: _CompletedProcess(),
    )

    def _materialize_checkout(*args, **kwargs) -> None:
        (checkout_path / ".git" / "info").mkdir(parents=True, exist_ok=True)
        (checkout_path / ".git" / "info" / "sparse-checkout").write_text(
            "/lib\n/lib/**\n",
            encoding="utf-8",
        )
        (checkout_path / "lib").mkdir(parents=True, exist_ok=True)
        (checkout_path / "lib" / "new.rb").write_text("module New; end\n", encoding="utf-8")

    monkeypatch.setattr(
        public_repo_matrix,
        "_materialize_public_repository_checkout",
        _materialize_checkout,
    )

    result = public_repo_matrix._clone_public_repository_case_unlocked(
        case,
        checkout_root=tmp_path,
        refresh=True,
    )

    assert result == checkout_path
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem="ruby",
    ) is None
    assert public_repo_matrix._cached_public_repository_tracked_relative_files(checkout_path) is None
    assert public_repo_matrix._cached_public_repository_head_revision(checkout_path) is None
    assert public_repo_matrix._cached_public_repository_seed_plan_result(
        case=case,
        repo_path=checkout_path,
        focus_paths=["lib"],
        max_files=32,
    ) is None
    assert (
        (
            str(checkout_path.resolve()),
            "lib/old.rb",
        )
        not in public_repo_matrix._PUBLIC_REPOSITORY_PATH_CANDIDATE_ECOSYSTEM_CACHE
    )


def test_reusable_public_repository_checkout_uses_positive_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    checkout_path = tmp_path / "cached-checkout"
    (checkout_path / ".git").mkdir(parents=True)
    (checkout_path / "README.md").write_text("ready\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    assert public_repo_matrix._is_reusable_public_repository_checkout(checkout_path) is True

    def _fail_rglob(self, *_args, **_kwargs):
        if self == checkout_path / ".git":
            raise AssertionError("expected reusable checkout cache hit")
        return original_rglob(self, *_args, **_kwargs)

    def _fail_iterdir(self, *_args, **_kwargs):
        if self == checkout_path:
            raise AssertionError("expected reusable checkout cache hit")
        return original_iterdir(self, *_args, **_kwargs)

    original_rglob = Path.rglob
    original_iterdir = Path.iterdir
    monkeypatch.setattr(Path, "rglob", _fail_rglob)
    monkeypatch.setattr(Path, "iterdir", _fail_iterdir)

    assert public_repo_matrix._is_reusable_public_repository_checkout(checkout_path) is True


def test_invalidate_public_repository_checkout_caches_clears_reusable_checkout_cache(
    tmp_path: Path,
) -> None:
    checkout_path = tmp_path / "cached-checkout"
    (checkout_path / ".git").mkdir(parents=True)
    (checkout_path / "README.md").write_text("ready\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    assert public_repo_matrix._is_reusable_public_repository_checkout(checkout_path) is True
    assert public_repo_matrix._cached_reusable_public_repository_checkout(checkout_path) is True

    public_repo_matrix._invalidate_public_repository_checkout_caches(checkout_path)

    assert public_repo_matrix._cached_reusable_public_repository_checkout(checkout_path) is False


def test_invalidate_public_repository_checkout_caches_clears_candidate_config_focus_path_cache(
    tmp_path: Path,
) -> None:
    checkout_path = tmp_path / "candidate-config-focus-checkout"
    checkout_path.mkdir()

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_candidate_config_focus_paths(
        repo_path=checkout_path,
        focus_paths=["src"],
        diagnostic_base_path=checkout_path,
        diagnostic_project_path=None,
        config_focus_paths=["src", "package.json"],
    )

    assert public_repo_matrix._cached_public_repository_candidate_config_focus_paths(
        repo_path=checkout_path,
        focus_paths=["src"],
        diagnostic_base_path=checkout_path,
        diagnostic_project_path=None,
    ) == ["src", "package.json"]

    public_repo_matrix._invalidate_public_repository_checkout_caches(checkout_path)

    assert public_repo_matrix._cached_public_repository_candidate_config_focus_paths(
        repo_path=checkout_path,
        focus_paths=["src"],
        diagnostic_base_path=checkout_path,
        diagnostic_project_path=None,
    ) is None


def test_warm_public_repository_reusable_checkout_caches_skips_redundant_work_when_cached(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="matlab",
        repository_url="https://github.com/matlab2tikz/matlab2tikz.git",
        expected_primary_ecosystem="matlab",
    )
    checkout_path = tmp_path / "cached-matlab-checkout"
    (checkout_path / ".git").mkdir(parents=True)
    (checkout_path / "src").mkdir(parents=True)
    (checkout_path / "src" / "main.m").write_text("function main\nend\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_head_revision(
        repo_path=checkout_path,
        resolved_revision="a" * 40,
    )
    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=checkout_path,
        relative_paths=["src/main.m"],
    )
    public_repo_matrix._store_public_repository_prepass_focus_paths(
        repo_path=checkout_path,
        expected_primary_ecosystem="matlab",
        focus_paths=["src"],
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("expected reusable checkout warm-cache fast path")

    monkeypatch.setattr(public_repo_matrix, "_git_executable", _unexpected)
    monkeypatch.setattr(
        public_repo_matrix,
        "_materialized_public_repository_focus_paths",
        _unexpected,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_tracked_relative_files",
        _unexpected,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_store_public_repository_materialized_tracked_relative_files",
        _unexpected,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_focus_paths_from_relative_files",
        _unexpected,
    )

    public_repo_matrix._warm_public_repository_reusable_checkout_caches(
        case=case,
        checkout_path=checkout_path,
    )


def test_run_public_repository_probe_case_passes_cached_resolved_revision_to_fallback_probe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    repo_path = tmp_path / "typst-packages"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    public_repo_matrix._store_public_repository_head_revision(
        repo_path=repo_path,
        resolved_revision="b" * 40,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "entrypoint_files": [],
            "support_roots": [],
            "config_paths": [],
            "primary_match": True,
        },
    )

    def fake_run_probe(**kwargs: object) -> dict[str, object]:
        captured["resolved_revision"] = kwargs["resolved_revision"]
        return {
            "planner_status": "ready",
            "operational_seed_plan": {
                "detected_ecosystems": ["typst"],
                "operational_ecosystems": ["typst"],
            },
            "snapshot": {"file_count": 1},
            "connected_map": {"connected_file_count": 1, "seed_files": ["main.typ"]},
        }

    monkeypatch.setattr(public_repo_matrix.probe_module, "run_probe", fake_run_probe)

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["resolved_revision"] == "b" * 40
    assert result["primary_match"] is True
    assert "ruby" in public_repo_matrix._path_candidate_ecosystems(
        "lib/new.rb",
        repo_path=repo_path,
    )


def test_run_public_repository_probe_for_checkout_scopes_repo_file_stat_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from benchmarks import (
        repository_intelligence_real_repo_probe_profile_path_classification_support as classification_support,
    )

    case = public_repo_matrix.PublicRepositoryCase(
        language="scheme",
        repository_url="https://github.com/ashinn/irregex.git",
        expected_primary_ecosystem="scheme",
    )
    repo_path = tmp_path / "scheme-repo"
    repo_path.mkdir()
    runtime_root = tmp_path / "runtime"
    events: list[str] = []

    monkeypatch.setattr(
        classification_support,
        "begin_repo_file_stat_cache_scope",
        lambda: events.append("begin"),
    )
    monkeypatch.setattr(
        classification_support,
        "end_repo_file_stat_cache_scope",
        lambda: events.append("end"),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_refine_seed_plan_result_for_unscoped_case",
        lambda *args, **kwargs: (
            {
                "primary_match": False,
                "entrypoint_files": [],
                "support_roots": [],
                "config_paths": [],
                "detected_ecosystems": ["scheme"],
                "operational_ecosystems": ["scheme"],
            },
            [],
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "run_probe",
        lambda **kwargs: {
            "planner_status": "ready",
            "operational_seed_plan": {
                "detected_ecosystems": ["scheme"],
                "operational_ecosystems": ["scheme"],
            },
            "snapshot": {"file_count": 1},
            "connected_map": {"connected_file_count": 1, "seed_files": ["main.scm"]},
        },
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=runtime_root,
    )

    assert result["primary_match"] is True
    assert events.count("begin") >= 1
    assert events.count("begin") == events.count("end")
    assert events[0] == "begin"
    assert events[-1] == "end"


def test_run_public_repository_probe_for_checkout_seeds_cached_tracked_relative_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import benchmarks.repository_intelligence_real_repo_probe_collection_support as collection_support

    class _StopProbe(RuntimeError):
        pass

    case = public_repo_matrix.PublicRepositoryCase(
        language="ruby",
        repository_url="https://github.com/sinatra/sinatra.git",
        expected_primary_ecosystem="ruby",
    )
    repo_path = tmp_path / "sinatra"
    repo_path.mkdir()
    runtime_root = tmp_path / "runtime"
    seeded_calls: list[tuple[Path, list[str], bool]] = []

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=["lib/sinatra.rb", "README.md"],
    )

    monkeypatch.setattr(
        collection_support,
        "seed_git_repo_relative_files_cache",
        lambda seeded_repo_path, relative_paths, *, relative_paths_are_canonical=False: seeded_calls.append(
            (seeded_repo_path, list(relative_paths), relative_paths_are_canonical)
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_refine_seed_plan_result_for_unscoped_case",
        lambda *args, **kwargs: (_ for _ in ()).throw(_StopProbe()),
    )

    with pytest.raises(_StopProbe):
        public_repo_matrix._run_public_repository_probe_for_checkout(
            case,
            repo_path=repo_path,
            runtime_root=runtime_root,
        )

    assert seeded_calls == [
        (repo_path, ["README.md", "lib/sinatra.rb"], True),
    ]


def test_store_public_repository_materialized_tracked_relative_files_caches_explicit_focus_subset(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "clarity-explicit-focus-cache"
    (repo_path / "contracts").mkdir(parents=True)
    (repo_path / "test").mkdir(parents=True)
    (repo_path / "docs").mkdir(parents=True)
    (repo_path / "contracts" / "alpha.clar").write_text("(define-constant one u1)\n", encoding="utf-8")
    (repo_path / "test" / "alpha_test.ts").write_text("export {};\n", encoding="utf-8")
    (repo_path / "docs" / "ignored.md").write_text("# ignored\n", encoding="utf-8")

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    tracked_relative_paths = public_repo_matrix._store_public_repository_materialized_tracked_relative_files(
        checkout_path=repo_path,
        focus_paths=["contracts", "test"],
    )

    assert tracked_relative_paths == [
        "contracts/alpha.clar",
        "test/alpha_test.ts",
    ]
    assert public_repo_matrix._cached_public_repository_tracked_relative_files(repo_path) == [
        "contracts/alpha.clar",
        "test/alpha_test.ts",
    ]


def test_store_public_repository_tracked_relative_files_sorts_cached_listing(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "sorted-tracked-relative-files-cache"
    repo_path.mkdir()

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    tracked_relative_paths = public_repo_matrix._store_public_repository_tracked_relative_files(
        repo_path=repo_path,
        relative_paths=[
            "src/zeta.rb",
            "src/alpha.rb",
            "src/zeta.rb",
        ],
    )

    assert tracked_relative_paths == [
        "src/alpha.rb",
        "src/zeta.rb",
    ]
    assert public_repo_matrix._cached_public_repository_tracked_relative_files(repo_path) == [
        "src/alpha.rb",
        "src/zeta.rb",
    ]


def test_derived_probe_focus_paths_from_seed_plan_keeps_seed_focus_when_root_entrypoints_exist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "prolog-examples"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_path_supports_expected_ecosystem",
        lambda path, **_kwargs: path.endswith(".pl"),
    )

    focus_paths = public_repo_matrix._derived_probe_focus_paths_from_seed_plan(
        seed_plan_result={
            "entrypoint_files": ["MonstersAndMazes.pl", "pirates/map.pl"],
            "support_roots": ["pirates"],
            "config_paths": [],
            "candidate_file_paths": ["MonstersAndMazes.pl", "pirates/map.pl"],
        },
        repo_path=repo_path,
        expected_primary_ecosystem="prolog",
    )

    assert focus_paths == []


def test_derived_probe_focus_paths_from_seed_plan_keeps_primary_support_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "vb6-suite"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix,
        "_path_supports_expected_ecosystem",
        lambda path, **_kwargs: path.endswith((".bas", ".frm")),
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_matches_focus_paths",
        lambda candidate_path, focus_paths: any(
            candidate_path == focus_path or candidate_path.startswith(f"{focus_path}/")
            for focus_path in focus_paths
        ),
    )

    focus_paths = public_repo_matrix._derived_probe_focus_paths_from_seed_plan(
        seed_plan_result={
            "entrypoint_files": [
                "ArtCorridor/Source/Main.bas",
                "91reg/main.frm",
                "ClassTemplate/ClassBuilder/Main.bas",
            ],
            "support_roots": [
                "91reg",
                "ArchReader/Core",
                "ArtCorridor/Source",
                "BlogText",
                "BookManager",
                "ClassTemplate/ClassBuilder",
            ],
            "config_paths": [],
            "candidate_file_paths": [
                "ArtCorridor/Source/Main.bas",
                "91reg/main.frm",
                "ClassTemplate/ClassBuilder/Main.bas",
                "ArchReader/Core/MDefinition.bas",
                "BlogText/BlogSave.frm",
                "BookManager/frmMain.frm",
            ],
        },
        repo_path=repo_path,
        expected_primary_ecosystem="vb6",
    )

    assert focus_paths == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "ArchReader/Core",
        "BlogText",
        "BookManager",
    ]

def test_refine_seed_plan_result_for_unscoped_case_bootstraps_scoped_reseed_when_prepass_is_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    )
    repo_path = tmp_path / "vb6-suite"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    seed_focus_calls: list[list[str]] = []

    broad_seed_plan = {
        "case": public_repo_matrix.asdict(case),
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "BlogText/BlogSave.frm",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
        ],
        "support_roots": ["ArtCorridor/Source", "91reg", "BlogText"],
        "config_paths": [],
        "detected_ecosystems": ["vb6"],
        "operational_ecosystems": ["vb6"],
        "primary_match": True,
    }
    scoped_seed_plan = {
        **broad_seed_plan,
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "BlogText/BlogSave.frm",
            "BookManager/frmMain.frm",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "BlogText/BlogSave.frm",
        ],
        "support_roots": [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "BlogText",
        ],
    }

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: [],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        return broad_seed_plan if not focus_paths else scoped_seed_plan

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )

    def fake_derived_probe_focus_paths_from_seed_plan(**kwargs):
        entrypoint_files = list(kwargs["seed_plan_result"]["entrypoint_files"])
        if entrypoint_files == list(broad_seed_plan["entrypoint_files"]):
            return ["ArtCorridor/Source", "91reg", "BlogText"]
        return ["ArtCorridor/Source", "91reg", "ClassTemplate/ClassBuilder", "BlogText"]

    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        fake_derived_probe_focus_paths_from_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: dict(kwargs["seed_plan_result"]),
    )

    seed_plan_result, probe_focus_paths = (
        public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
            case,
            repo_path=repo_path,
            max_files=256,
        )
    )

    assert seed_focus_calls == [
        [],
        ["ArtCorridor/Source", "91reg", "BlogText"],
    ]
    assert seed_plan_result["entrypoint_files"] == [
        "ArtCorridor/Source/Main.bas",
        "91reg/main.frm",
        "ClassTemplate/ClassBuilder/Main.bas",
        "BlogText/BlogSave.frm",
    ]
    assert probe_focus_paths == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "BlogText",
    ]
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="vb6",
    ) == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "BlogText",
    ]


def test_refine_seed_plan_result_for_unscoped_case_skips_broad_bootstrap_when_heuristic_prepass_is_already_diverse(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    )
    repo_path = tmp_path / "vb6-suite-diverse"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    seed_focus_calls: list[list[str]] = []
    heuristic_seed_plan = {
        "case": public_repo_matrix.asdict(case),
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "ArchReader/Core/MDefinition.bas",
            "BlogText/BlogSave.frm",
            "BookManager/frmMain.frm",
            "BinTree/Main.bas",
            "[Include]/ClassTemplate/Template.bas",
            "[Include]/Components/ssreader/Reader.bas",
            "ClassTemplate/Filters/Helper.bas",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "ArchReader/Core/MDefinition.bas",
            "BlogText/BlogSave.frm",
            "BookManager/frmMain.frm",
        ],
        "support_roots": [
            "91reg",
            "ArchReader/Core",
            "ArtCorridor/Source",
            "BinTree",
            "BlogText",
            "BookManager",
            "ClassTemplate/ClassBuilder",
            "ClassTemplate/Filters",
            "[Include]/ClassTemplate",
            "[Include]/Components/ssreader",
        ],
        "config_paths": [],
        "detected_ecosystems": ["vb6"],
        "operational_ecosystems": ["vb6"],
        "primary_match": True,
    }

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: [
            "91reg",
            "ArchReader",
            "ArtCorridor/Source",
            "BinTree",
            "BlogText",
            "BookManager",
            "CBookUrl",
            "ClassTemplate",
        ],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        return heuristic_seed_plan

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **_kwargs: [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "ArchReader/Core",
            "BlogText",
            "BookManager",
            "BinTree",
            "ClassTemplate/Filters",
            "[Include]/ClassTemplate",
            "[Include]/Components/ssreader",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: dict(kwargs["seed_plan_result"]),
    )

    seed_plan_result, probe_focus_paths = (
        public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
            case,
            repo_path=repo_path,
            max_files=256,
        )
    )

    assert seed_focus_calls == [[
        "91reg",
        "ArchReader",
        "ArtCorridor/Source",
        "BinTree",
        "BlogText",
        "BookManager",
        "CBookUrl",
        "ClassTemplate",
    ]]
    assert seed_plan_result["entrypoint_files"] == heuristic_seed_plan["entrypoint_files"]
    assert probe_focus_paths == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "ArchReader/Core",
        "BlogText",
        "BookManager",
        "BinTree",
        "ClassTemplate/Filters",
        "[Include]/ClassTemplate",
        "[Include]/Components/ssreader",
    ]
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="vb6",
    ) == probe_focus_paths


def test_refine_seed_plan_result_for_unscoped_case_skips_broad_bootstrap_when_focused_result_is_already_sufficient(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    )
    repo_path = tmp_path / "vb6-suite-focused-sufficient"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    seed_focus_calls: list[list[str]] = []
    heuristic_seed_plan = {
        "case": public_repo_matrix.asdict(case),
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "BlogText/BlogSave.frm",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "BlogText/BlogSave.frm",
        ],
        "support_roots": [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "BlogText",
        ],
        "config_paths": [],
        "detected_ecosystems": ["vb6"],
        "operational_ecosystems": ["vb6"],
        "primary_match": True,
    }

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: [
            "ArtCorridor",
            "91reg",
            "ClassTemplate",
            "BlogText",
        ],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        return heuristic_seed_plan

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **_kwargs: [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "BlogText",
        ],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: dict(kwargs["seed_plan_result"]),
    )

    seed_plan_result, probe_focus_paths = (
        public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
            case,
            repo_path=repo_path,
            max_files=256,
        )
    )

    assert seed_focus_calls == [[
        "ArtCorridor",
        "91reg",
        "ClassTemplate",
        "BlogText",
    ]]
    assert seed_plan_result["entrypoint_files"] == heuristic_seed_plan["entrypoint_files"]
    assert probe_focus_paths == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "BlogText",
    ]
    assert public_repo_matrix._cached_public_repository_prepass_focus_paths(
        repo_path=repo_path,
        expected_primary_ecosystem="vb6",
    ) == probe_focus_paths


def test_refine_seed_plan_result_for_unscoped_case_prefers_broad_bootstrap_over_uncached_heuristic_prepass(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    )
    repo_path = tmp_path / "vb6-suite-reused"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    seed_focus_calls: list[list[str]] = []

    heuristic_seed_plan = {
        "case": public_repo_matrix.asdict(case),
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "ArchReader/Core/MDefinition.bas",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "ArchReader/Core/MDefinition.bas",
        ],
        "support_roots": [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "ArchReader/Core",
        ],
        "config_paths": [],
        "detected_ecosystems": ["vb6"],
        "operational_ecosystems": ["vb6"],
        "primary_match": True,
    }
    broad_seed_plan = {
        **heuristic_seed_plan,
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "zpShower/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
            "ArchReader/Core/MDefinition.bas",
            "BlogText/BlogSave.frm",
            "BookManager/frmMain.frm",
            "CreateFolderIndex/MMAIN.bas",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "zpShower/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
        ],
        "support_roots": [
            "ArtCorridor/Source",
            "zpShower/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "ArchReader/Core",
            "BlogText",
            "BookManager",
            "CreateFolderIndex",
        ],
    }
    scoped_bootstrap_seed_plan = {
        **broad_seed_plan,
        "entrypoint_files": list(broad_seed_plan["candidate_file_paths"]),
    }

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["ArchReader", "ClassTemplate"],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        if not focus_paths:
            return broad_seed_plan
        if focus_paths == ["ArtCorridor/Source", "zpShower/Source", "91reg", "ClassTemplate/ClassBuilder"]:
            return scoped_bootstrap_seed_plan
        return heuristic_seed_plan

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )

    def fake_derived_probe_focus_paths_from_seed_plan(**kwargs):
        entrypoint_files = list(kwargs["seed_plan_result"]["entrypoint_files"])
        if entrypoint_files == list(heuristic_seed_plan["entrypoint_files"]):
            return ["ArchReader", "ClassTemplate"]
        if entrypoint_files == list(broad_seed_plan["entrypoint_files"]):
            return [
                "ArtCorridor/Source",
                "zpShower/Source",
                "91reg",
                "ClassTemplate/ClassBuilder",
            ]
        return [
            "ArtCorridor/Source",
            "zpShower/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
            "ArchReader/Core",
            "BlogText",
            "BookManager",
            "CreateFolderIndex",
        ]

    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        fake_derived_probe_focus_paths_from_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: {
            **dict(kwargs["seed_plan_result"]),
            "primary_match": False,
        },
    )

    seed_plan_result, probe_focus_paths = (
        public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
            case,
            repo_path=repo_path,
            max_files=256,
        )
    )

    assert seed_focus_calls == [
        ["ArchReader", "ClassTemplate"],
        [],
        ["ArtCorridor/Source", "zpShower/Source", "91reg", "ClassTemplate/ClassBuilder"],
    ]
    assert seed_plan_result["entrypoint_files"] == [
        "ArtCorridor/Source/Main.bas",
        "zpShower/Source/Main.bas",
        "91reg/main.frm",
        "ClassTemplate/ClassBuilder/Main.bas",
        "ArchReader/Core/MDefinition.bas",
        "BlogText/BlogSave.frm",
        "BookManager/frmMain.frm",
        "CreateFolderIndex/MMAIN.bas",
    ]
    assert probe_focus_paths == [
        "ArtCorridor/Source",
        "zpShower/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
        "ArchReader/Core",
        "BlogText",
        "BookManager",
        "CreateFolderIndex",
    ]


def test_refine_seed_plan_result_for_unscoped_case_reuses_one_collection_scope_across_nested_seed_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="vb6",
        repository_url="https://github.com/badcodes/vb6.git",
        expected_primary_ecosystem="vb6",
    )
    repo_path = tmp_path / "vb6-suite-shared-scope"
    repo_path.mkdir()
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    from apps.api_server.services import (
        repository_intelligence_repository_source as repository_source,
    )
    import benchmarks.repository_intelligence_real_repo_probe_collection_support as collection_support

    begin_calls = {"value": 0}
    end_calls = {"value": 0}

    monkeypatch.setattr(
        repository_source,
        "begin_git_command_cache_scope",
        lambda: begin_calls.__setitem__("value", begin_calls["value"] + 1),
    )
    monkeypatch.setattr(
        repository_source,
        "end_git_command_cache_scope",
        lambda: end_calls.__setitem__("value", end_calls["value"] + 1),
    )

    broad_seed_plan = {
        "case": public_repo_matrix.asdict(case),
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
        ],
        "support_roots": ["ArtCorridor/Source", "91reg"],
        "config_paths": [],
        "detected_ecosystems": ["vb6"],
        "operational_ecosystems": ["vb6"],
        "primary_match": True,
    }
    scoped_seed_plan = {
        **broad_seed_plan,
        "candidate_file_paths": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
        ],
        "entrypoint_files": [
            "ArtCorridor/Source/Main.bas",
            "91reg/main.frm",
            "ClassTemplate/ClassBuilder/Main.bas",
        ],
        "support_roots": [
            "ArtCorridor/Source",
            "91reg",
            "ClassTemplate/ClassBuilder",
        ],
    }

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: [],
    )

    def fake_seed_plan(*_args, **kwargs):
        collection_support.begin_git_repo_relative_files_cache_scope()
        try:
            focus_paths = list(kwargs["focus_paths"])
            return broad_seed_plan if not focus_paths else scoped_seed_plan
        finally:
            collection_support.end_git_repo_relative_files_cache_scope()

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )

    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **kwargs: (
            ["ArtCorridor/Source", "91reg"]
            if list(kwargs["seed_plan_result"]["entrypoint_files"])
            == list(broad_seed_plan["entrypoint_files"])
            else ["ArtCorridor/Source", "91reg", "ClassTemplate/ClassBuilder"]
        ),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **kwargs: dict(kwargs["seed_plan_result"]),
    )

    seed_plan_result, probe_focus_paths = (
        public_repo_matrix._refine_seed_plan_result_for_unscoped_case(
            case,
            repo_path=repo_path,
            max_files=256,
        )
    )

    assert seed_plan_result["entrypoint_files"] == scoped_seed_plan["entrypoint_files"]
    assert probe_focus_paths == [
        "ArtCorridor/Source",
        "91reg",
        "ClassTemplate/ClassBuilder",
    ]
    assert begin_calls["value"] == 1
    assert end_calls["value"] == 1


def test_prefer_expected_primary_ecosystem_on_tied_top_score() -> None:
    ordered = public_repo_matrix._prefer_expected_primary_ecosystem_on_tied_top_score(
        ["cpp", "cuda"],
        ecosystem_scores=Counter({"cpp": 2, "cuda": 2}),
        expected_primary_ecosystem="cuda",
    )

    assert ordered == ["cuda", "cpp"]


def test_focused_seed_plan_result_prefers_expected_primary_ecosystem_on_tied_entrypoints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "cuda-sample"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "cuda" if path.endswith(".cu") else "cpp",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "samples/main.cpp",
                "samples/kernel.cu",
                "samples/secondary.cpp",
                "samples/secondary_kernel.cu",
            ],
            "config_paths": [],
            "entrypoint_files": [
                "samples/main.cpp",
                "samples/kernel.cu",
                "samples/secondary.cpp",
                "samples/secondary_kernel.cu",
            ],
            "support_roots": ["samples"],
        },
        repo_path=repo_path,
        focus_paths=["samples"],
        expected_primary_ecosystem="cuda",
    )

    assert focused is not None
    assert focused["detected_ecosystems"] == ["cuda", "cpp"]
    assert focused["operational_ecosystems"] == ["cuda", "cpp"]
    assert focused["primary_ecosystem"] == "cuda"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_prefers_expected_primary_ecosystem_on_tied_aliases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "phoenix"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "ex"
        if path.endswith((".ex", ".exs"))
        else "javascript",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "lib/phoenix.ex",
                "config/config.exs",
                "assets/js/phoenix/index.js",
                "assets/js/phoenix/channel.js",
            ],
            "config_paths": ["config/config.exs"],
            "entrypoint_files": [
                "lib/phoenix.ex",
                "config/config.exs",
                "assets/js/phoenix/index.js",
                "assets/js/phoenix/channel.js",
            ],
            "support_roots": ["lib", "config", "assets/js/phoenix"],
        },
        repo_path=repo_path,
        focus_paths=["lib", "config", "assets/js/phoenix"],
        expected_primary_ecosystem="elixir",
    )

    assert focused is not None
    assert focused["detected_ecosystems"] == ["elixir", "javascript"]
    assert focused["primary_ecosystem"] == "elixir"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_prefers_expected_candidate_family_ecosystem(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "express"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"javascript", "node"}
        if path.endswith(".js")
        else {"json"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "javascript" if path.endswith(".js") else "json",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "lib/application.js",
                "lib/request.js",
                "lib/response.js",
            ],
            "config_paths": [],
            "entrypoint_files": [
                "lib/application.js",
                "lib/request.js",
                "lib/response.js",
            ],
            "support_roots": ["lib"],
        },
        repo_path=repo_path,
        focus_paths=["lib"],
        expected_primary_ecosystem="node",
    )

    assert focused is not None
    assert focused["detected_ecosystems"] == ["node"]
    assert focused["primary_ecosystem"] == "node"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_promotes_expected_build_ecosystem_candidates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "meson-project"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda path, repo_path=None: {"meson"}
        if path.endswith("meson.build")
        else {"c"},
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "meson" if path.endswith("meson.build") else "c",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "src/main.cc",
                "src/meson.build",
                "src/lib.cc",
                "include/meson.build",
            ],
            "config_paths": [],
            "entrypoint_files": [
                "src/main.cc",
                "src/lib.cc",
            ],
            "support_roots": ["src", "include"],
        },
        repo_path=repo_path,
        focus_paths=["src", "include"],
        expected_primary_ecosystem="meson",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == [
        "src/meson.build",
        "include/meson.build",
    ]
    assert focused["candidate_file_paths"] == [
        "src/meson.build",
        "include/meson.build",
    ]
    assert focused["detected_ecosystems"] == ["meson"]
    assert focused["primary_ecosystem"] == "meson"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_promotes_expected_candidates_over_host_sidecars(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "purescript-prelude"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "purescript"
        if path.endswith(".purs")
        else "javascript",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "src/Control/Applicative.purs",
                "src/Control/Apply.js",
                "src/Control/Apply.purs",
                "src/Data/Bounded.js",
            ],
            "config_paths": [],
            "entrypoint_files": [
                "src/Control/Apply.js",
                "src/Data/Bounded.js",
            ],
            "support_roots": ["src/Control", "src/Data"],
        },
        repo_path=repo_path,
        focus_paths=["src/Control", "src/Data"],
        expected_primary_ecosystem="purescript",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == [
        "src/Control/Applicative.purs",
        "src/Control/Apply.purs",
    ]
    assert focused["detected_ecosystems"] == ["purescript"]
    assert focused["primary_ecosystem"] == "purescript"
    assert focused["primary_match"] is True


def test_focused_seed_plan_result_promotes_expected_candidates_when_sidecars_dominate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "elm-core"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "elm" if path.endswith(".elm") else "javascript",
    )

    focused = public_repo_matrix._focused_seed_plan_result(
        seed_plan_result={
            "candidate_file_paths": [
                "src/Array.elm",
                "src/Basics.elm",
                "src/Bitwise.elm",
                "src/Elm/Kernel/Basics.js",
                "src/Elm/Kernel/Bitwise.js",
                "src/Elm/Kernel/Char.js",
            ],
            "config_paths": [],
            "entrypoint_files": [
                "src/Elm/Kernel/Basics.js",
                "src/Elm/Kernel/Bitwise.js",
                "src/Array.elm",
                "src/Elm/Kernel/Char.js",
                "src/Basics.elm",
            ],
            "support_roots": ["src"],
        },
        repo_path=repo_path,
        focus_paths=["src"],
        expected_primary_ecosystem="elm",
    )

    assert focused is not None
    assert focused["entrypoint_files"] == [
        "src/Array.elm",
        "src/Basics.elm",
        "src/Bitwise.elm",
    ]
    assert focused["detected_ecosystems"] == ["elm"]
    assert focused["primary_ecosystem"] == "elm"
    assert focused["primary_match"] is True


def test_collapse_versioned_focus_paths_keeps_latest_sibling_versions() -> None:
    assert public_repo_matrix._collapse_versioned_focus_paths(
        [
            "_PoiyomiShaders/Shaders/7.3/Pro/Shaders",
            "_PoiyomiShaders/Shaders/8.0",
            "_PoiyomiShaders/Shaders/8.1/Toon",
            "_PoiyomiShaders/Shaders/9.0/Toon",
            "_PoiyomiShaders/Shaders/9.1/Toon",
            "_PoiyomiShaders/Shaders/9.2/Toon",
            "_PoiyomiShaders/Shaders/9.3/Toon",
            "_PoiyomiShaders/Shaders/Extras",
        ]
    ) == [
        "_PoiyomiShaders/Shaders/7.3/Pro/Shaders",
        "_PoiyomiShaders/Shaders/8.0",
        "_PoiyomiShaders/Shaders/9.3/Toon",
        "_PoiyomiShaders/Shaders/Extras",
    ]


def test_collapse_versioned_focus_paths_keeps_latest_package_generation() -> None:
    assert public_repo_matrix._collapse_versioned_focus_paths(
        [
            "packages/preview/kthesis/0.1.0/src",
            "packages/preview/kthesis/0.1.1/src",
            "packages/preview/kthesis/0.1.2/src",
            "packages/preview/modern-uit-thesis/0.1.5/nix/packages",
            "packages/preview/modern-uit-thesis/0.1.6/nix/packages",
        ]
    ) == [
        "packages/preview/kthesis/0.1.2/src",
        "packages/preview/modern-uit-thesis/0.1.6/nix/packages",
    ]


def test_collapse_versioned_focus_paths_keeps_latest_alpha_prefixed_package_generation() -> None:
    assert public_repo_matrix._collapse_versioned_focus_paths(
        [
            "packages/RAD Studio XE2",
            "packages/RAD Studio XE3",
            "packages/RAD Studio XE8",
            "packages/RAD Studio 13.0",
        ]
    ) == [
        "packages/RAD Studio XE8",
        "packages/RAD Studio 13.0",
    ]


def test_run_public_repository_probe_case_falls_back_to_prepass_focus_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    repo_path = tmp_path / "typst-packages"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["packages/preview/blockst"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "entrypoint_files": [],
            "support_roots": [],
            "config_paths": [],
            "primary_match": True,
        },
    )

    def fake_run_probe(**kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["focus_paths"]
        captured["load_graph_summary"] = kwargs["load_graph_summary"]
        captured["use_seed_files_as_connected_map"] = kwargs["use_seed_files_as_connected_map"]
        return {
            "planner_status": "ready",
            "operational_seed_plan": {
                "detected_ecosystems": ["typst"],
                "operational_ecosystems": ["typst"],
            },
            "snapshot": {"file_count": 4},
            "connected_map": {
                "connected_file_count": 2,
                "seed_files": ["packages/preview/blockst/0.2.1/lib.typ"],
            },
        }

    monkeypatch.setattr(public_repo_matrix.probe_module, "run_probe", fake_run_probe)

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["packages/preview/blockst"]
    assert captured["load_graph_summary"] is False
    assert captured["use_seed_files_as_connected_map"] is True
    assert result["primary_match"] is True


def test_run_public_repository_probe_case_reseeds_on_narrowed_focus_after_primary_miss(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="abap",
        repository_url="https://github.com/abapGit/abapGit.git",
        expected_primary_ecosystem="abap",
    )
    repo_path = tmp_path / "abapgit"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    seed_focus_calls: list[list[str]] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["deps", "src/apack", "src/background", "ci"],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        if focus_paths == ["src/apack", "src/background"]:
            return {
                "case": public_repo_matrix.asdict(case),
                "candidate_file_paths": [
                    "src/apack/zcl_abapgit_apack_helper.clas.abap",
                    "src/background/zcl_abapgit_background.clas.abap",
                ],
                "entrypoint_files": [
                    "src/apack/zcl_abapgit_apack_helper.clas.abap",
                    "src/background/zcl_abapgit_background.clas.abap",
                ],
                "support_roots": ["src/apack", "src/background"],
                "config_paths": [],
                "detected_ecosystems": ["abap"],
                "operational_ecosystems": ["abap"],
                "primary_match": True,
            }
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": [
                "src/apack/zcl_abapgit_apack_helper.clas.abap",
                "src/background/zcl_abapgit_background.clas.abap",
                "ci/build-merged-build.sh",
            ],
            "entrypoint_files": [
                "src/apack/zcl_abapgit_apack_helper.clas.abap",
                "src/background/zcl_abapgit_background.clas.abap",
                "ci/build-merged-build.sh",
            ],
            "support_roots": [".", "src/apack", "ci"],
            "config_paths": [],
            "detected_ecosystems": ["node", "abap"],
            "operational_ecosystems": ["node", "abap"],
            "primary_match": False,
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "abap" if path.endswith(".abap") else "shell",
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **_kwargs: None,
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["abap"],
                "operational_ecosystems": ["abap"],
            },
            "snapshot": {"file_count": 10},
            "connected_map": {
                "connected_file_count": 4,
                "seed_files": ["src/apack/zcl_abapgit_apack_helper.clas.abap"],
            },
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert seed_focus_calls == [
        ["deps", "src/apack", "src/background", "ci"],
        ["src/apack", "src/background"],
    ]
    assert captured["focus_paths"] == ["src/apack", "src/background"]
    assert captured["operational_seed_plan"] == {
        "candidate_file_paths": [
            "src/apack/zcl_abapgit_apack_helper.clas.abap",
            "src/background/zcl_abapgit_background.clas.abap",
        ],
        "config_paths": [],
        "detected_ecosystems": ["abap"],
        "entrypoint_files": [
            "src/apack/zcl_abapgit_apack_helper.clas.abap",
            "src/background/zcl_abapgit_background.clas.abap",
        ],
        "operational_ecosystems": ["abap"],
        "support_roots": ["src/apack", "src/background"],
    }
    assert result["primary_match"] is True


def test_run_public_repository_probe_case_uses_focused_seed_before_reseeding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="cuda",
        repository_url="https://github.com/NVIDIA/cuda-samples.git",
        expected_primary_ecosystem="cuda",
    )
    repo_path = tmp_path / "cuda-samples"
    repo_path.mkdir()
    captured: dict[str, object] = {}
    seed_focus_calls: list[list[str]] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["cpp", "docs"],
    )

    def fake_seed_plan(*_args, **kwargs):
        focus_paths = list(kwargs["focus_paths"])
        seed_focus_calls.append(focus_paths)
        return {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": [
                "cpp/2_Concepts/kernel.cu",
                "cpp/2_Concepts/kernel.hpp",
                "docs/README.md",
            ],
            "entrypoint_files": [
                "cpp/2_Concepts/kernel.cu",
                "docs/README.md",
            ],
            "support_roots": ["cpp", "docs"],
            "config_paths": [],
            "detected_ecosystems": ["cpp", "cuda"],
            "operational_ecosystems": ["cpp", "cuda"],
            "primary_match": False,
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        lambda **_kwargs: ["cpp/2_Concepts"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": [
                "cpp/2_Concepts/kernel.cu",
                "cpp/2_Concepts/kernel.hpp",
            ],
            "entrypoint_files": ["cpp/2_Concepts/kernel.cu"],
            "support_roots": ["cpp/2_Concepts"],
            "config_paths": [],
            "detected_ecosystems": ["cuda", "cpp"],
            "operational_ecosystems": ["cuda", "cpp"],
            "primary_match": True,
        },
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["cuda", "cpp"],
                "operational_ecosystems": ["cuda", "cpp"],
            },
            "snapshot": {"file_count": 2},
            "connected_map": {
                "connected_file_count": 1,
                "seed_files": ["cpp/2_Concepts/kernel.cu"],
            },
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert seed_focus_calls == [["cpp", "docs"]]
    assert captured["focus_paths"] == ["cpp/2_Concepts"]
    assert captured["operational_seed_plan"] == {
        "candidate_file_paths": [
            "cpp/2_Concepts/kernel.cu",
            "cpp/2_Concepts/kernel.hpp",
        ],
        "config_paths": [],
        "detected_ecosystems": ["cuda", "cpp"],
        "entrypoint_files": ["cpp/2_Concepts/kernel.cu"],
        "operational_ecosystems": ["cuda", "cpp"],
        "support_roots": ["cpp/2_Concepts"],
    }
    assert result["primary_match"] is True


def test_run_public_repository_probe_case_recomputes_probe_focus_from_focused_seed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="opencl",
        repository_url="https://github.com/KhronosGroup/OpenCL-SDK.git",
        expected_primary_ecosystem="opencl",
    )
    repo_path = tmp_path / "opencl-sdk"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        public_repo_matrix,
        "_expected_ecosystem_prepass_focus_paths",
        lambda **_kwargs: ["samples/core", "lib"],
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": [
                "lib/include/CL/SDK/CLI.h",
                "samples/core/binaries/CMakeLists.txt",
            ],
            "entrypoint_files": [
                "lib/include/CL/SDK/CLI.h",
                "samples/core/binaries/CMakeLists.txt",
            ],
            "support_roots": ["lib", "samples/core", "samples/core/binaries"],
            "config_paths": ["samples/core/binaries/CMakeLists.txt"],
            "detected_ecosystems": ["cmake", "c"],
            "operational_ecosystems": ["cmake", "c"],
            "primary_match": False,
        },
    )

    def fake_derived_probe_focus_paths_from_seed_plan(**kwargs):
        support_roots = list(kwargs["seed_plan_result"].get("support_roots") or [])
        if support_roots == ["samples/core/binaries"]:
            return ["samples/core/binaries"]
        return ["lib", "samples/core", "samples/core/binaries"]

    monkeypatch.setattr(
        public_repo_matrix,
        "_derived_probe_focus_paths_from_seed_plan",
        fake_derived_probe_focus_paths_from_seed_plan,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_focused_seed_plan_result",
        lambda **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["samples/core/binaries/Collatz.cl"],
            "entrypoint_files": ["samples/core/binaries/Collatz.cl"],
            "support_roots": ["samples/core/binaries"],
            "config_paths": ["samples/core/binaries/CMakeLists.txt"],
            "detected_ecosystems": ["opencl"],
            "operational_ecosystems": ["opencl"],
            "primary_match": True,
        },
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["opencl"],
                "operational_ecosystems": ["opencl"],
            },
            "snapshot": {"file_count": 1},
            "connected_map": {
                "connected_file_count": 1,
                "seed_files": ["samples/core/binaries/Collatz.cl"],
            },
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["samples/core/binaries"]
    assert captured["operational_seed_plan"] == {
        "candidate_file_paths": ["samples/core/binaries/Collatz.cl"],
        "config_paths": ["samples/core/binaries/CMakeLists.txt"],
        "detected_ecosystems": ["opencl"],
        "entrypoint_files": ["samples/core/binaries/Collatz.cl"],
        "operational_ecosystems": ["opencl"],
        "support_roots": ["samples/core/binaries"],
    }
    assert result["primary_match"] is True


def test_run_public_repository_probe_case_keeps_explicit_focus_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="4d",
        repository_url="https://github.com/4d/4D-NetKit.git",
        expected_primary_ecosystem="4d",
        focus_paths=("Project/Sources",),
    )
    repo_path = tmp_path / "4d-netkit"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["Project/Sources/Main.4dm"],
            "entrypoint_files": ["Project/Sources/Main.4dm"],
            "support_roots": ["Project/Sources"],
            "config_paths": [],
            "detected_ecosystems": ["4d"],
            "operational_ecosystems": ["4d"],
            "primary_match": True,
        },
    )

    def fake_seed_plan_probe(*_args, **kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["probe_focus_paths"]
        captured["connected_file_count_mode"] = kwargs["connected_file_count_mode"]
        return {
            "planner_status": "not_attempted_no_diagnostics",
            "operational_seed_plan": {
                "detected_ecosystems": ["4d"],
                "operational_ecosystems": ["4d"],
            },
            "snapshot": {"file_count": 8},
            "connected_map": {"connected_file_count": 3, "seed_files": ["Project/Sources/Main.4dm"]},
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_from_seed_plan",
        fake_seed_plan_probe,
    )

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["Project/Sources"]
    assert captured["connected_file_count_mode"] == "snapshot"
    assert result["primary_match"] is True


def test_run_public_repository_probe_case_falls_back_for_explicit_focus_when_seed_misses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="4d",
        repository_url="https://github.com/4d/4D-NetKit.git",
        expected_primary_ecosystem="4d",
        focus_paths=("Project/Sources",),
    )
    repo_path = tmp_path / "4d-netkit"
    repo_path.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda *_args, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "candidate_file_paths": ["Project/Sources/Main.4dm", "README.md"],
            "entrypoint_files": ["README.md"],
            "support_roots": ["Project/Sources"],
            "config_paths": [],
            "detected_ecosystems": ["markdown"],
            "operational_ecosystems": ["markdown"],
            "primary_match": False,
        },
    )

    def fake_run_probe(**kwargs: object) -> dict[str, object]:
        captured["focus_paths"] = kwargs["focus_paths"]
        captured["operational_seed_plan"] = kwargs["operational_seed_plan"]
        captured["use_seed_files_as_connected_map"] = kwargs["use_seed_files_as_connected_map"]
        return {
            "planner_status": "ready",
            "operational_seed_plan": {
                "detected_ecosystems": ["4d"],
                "operational_ecosystems": ["4d"],
            },
            "snapshot": {"file_count": 8},
            "connected_map": {"connected_file_count": 3, "seed_files": ["Project/Sources/Main.4dm"]},
        }

    monkeypatch.setattr(public_repo_matrix.probe_module, "run_probe", fake_run_probe)

    result = public_repo_matrix._run_public_repository_probe_for_checkout(
        case,
        repo_path=repo_path,
        runtime_root=tmp_path,
    )

    assert captured["focus_paths"] == ["Project/Sources"]
    assert captured["operational_seed_plan"] is None
    assert captured["use_seed_files_as_connected_map"] is False
    assert result["primary_match"] is True


def test_run_public_repository_matrix_reports_real_language_progress(tmp_path: Path) -> None:
    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        limit=0,
        ranked_target_language_count=DEFAULT_REAL_LANGUAGE_RANK_TARGET,
    )

    progress = result["support_progress"]
    count = progress["supported_real_language_count"]
    available_count = len(ranked_real_repository_languages())

    # Fully dynamic: the matrix must report exactly the registry-derived count of
    # supported real languages, so wiring a new adapter updates this automatically —
    # no hardcoded total to bump every time a language lands.
    assert count == len(supported_repository_languages())
    # Regression floor only: coverage must never drop below the known-good baseline.
    # Additions always sail past it; bump it deliberately to lock in coverage gains.
    assert count >= 172

    assert result["case_count"] == 0
    assert progress["ranked_target_language_count"] == available_count
    assert progress["requested_ranked_target_language_count"] == DEFAULT_REAL_LANGUAGE_RANK_TARGET
    assert progress["available_ranked_real_language_count"] == available_count
    assert progress["target_clamped_to_available_ranked_real_languages"] is (
        DEFAULT_REAL_LANGUAGE_RANK_TARGET != available_count
    )
    # Label / fraction derived from the live count, not a literal.
    assert progress["progress_label"] == f"{count} / {available_count}"
    assert progress["progress_fraction"] == pytest.approx(count / available_count)

    public_case_progress = result["public_case_progress"]
    configured_case_languages = public_repo_matrix.configured_public_repository_case_languages()

    assert public_case_progress["configured_real_language_count"] == len(configured_case_languages)
    assert public_case_progress["ranked_target_language_count"] == available_count
    assert public_case_progress["requested_ranked_target_language_count"] == (
        DEFAULT_REAL_LANGUAGE_RANK_TARGET
    )
    assert public_case_progress["available_ranked_real_language_count"] == available_count
    assert public_case_progress["target_clamped_to_available_ranked_real_languages"] is (
        DEFAULT_REAL_LANGUAGE_RANK_TARGET != available_count
    )
    assert public_case_progress["configured_progress_label"] == (
        f"{len(configured_case_languages)} / {available_count}"
    )
    assert public_case_progress["configured_progress_fraction"] == pytest.approx(
        len(configured_case_languages) / available_count
    )
    assert public_case_progress["selected_case_count"] == 0
    assert public_case_progress["selected_case_keys"] == []
    assert public_case_progress["selected_case_language_count"] == 0
    assert public_case_progress["passing_case_count"] == 0
    assert public_case_progress["passing_case_keys"] == []
    assert public_case_progress["passing_case_language_count"] == 0
    assert public_case_progress["missing_real_languages"] == list(
        public_repo_matrix.missing_supported_public_repository_languages()
    )


def test_run_public_repository_matrix_primes_probe_runtime_once_for_probe_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    repo_path = tmp_path / "click"
    repo_path.mkdir()
    events: list[str] = []

    @contextmanager
    def fake_checkout_context(*_args: object, **_kwargs: object):
        yield repo_path

    monkeypatch.setattr(
        public_repo_matrix,
        "prime_public_repository_probe_runtime",
        lambda: events.append("warm"),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        fake_checkout_context,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_with_case_timeout",
        lambda **kwargs: kwargs["callback"](),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_probe_for_checkout",
        lambda selected_case, **kwargs: (
            events.append(f"probe:{selected_case.language}")
            or {
                "case": public_repo_matrix.asdict(selected_case),
                "case_key": public_repo_matrix._public_repository_case_key(selected_case),
                "repo_path": str(kwargs["repo_path"]),
                "primary_ecosystem": selected_case.expected_primary_ecosystem,
                "primary_match": True,
            }
        ),
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="probe",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        cases=[case],
    )

    assert events == ["warm", "probe:python"]
    assert result["cases"][0]["primary_match"] is True


def test_run_public_repository_matrix_does_not_prime_probe_runtime_for_seed_plan_mode(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    repo_path = tmp_path / "click"
    repo_path.mkdir()
    warm_calls: list[str] = []

    @contextmanager
    def fake_checkout_context(*_args: object, **_kwargs: object):
        yield repo_path

    monkeypatch.setattr(
        public_repo_matrix,
        "prime_public_repository_probe_runtime",
        lambda: warm_calls.append("warm"),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        fake_checkout_context,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_with_case_timeout",
        lambda **kwargs: kwargs["callback"](),
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda selected_case, **kwargs: {
            "case": public_repo_matrix.asdict(selected_case),
            "case_key": public_repo_matrix._public_repository_case_key(selected_case),
            "repo_path": str(kwargs["repo_path"]),
            "primary_ecosystem": selected_case.expected_primary_ecosystem,
            "primary_match": True,
        },
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        cases=[case],
    )

    assert warm_calls == []
    assert result["cases"][0]["primary_match"] is True


def test_missing_supported_public_repository_languages_uses_case_language_labels() -> None:
    cases = (
        public_repo_matrix.PublicRepositoryCase(
            language="javascript",
            repository_url="https://github.com/example/javascript.git",
            expected_primary_ecosystem="node",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="cs",
            repository_url="https://github.com/example/cs.git",
            expected_primary_ecosystem="dotnet",
        ),
        public_repo_matrix.PublicRepositoryCase(
            language="ml",
            repository_url="https://github.com/example/ml.git",
            expected_primary_ecosystem="sml",
        ),
    )

    missing = public_repo_matrix.missing_supported_public_repository_languages(cases=cases)

    assert "javascript" not in missing
    assert "cs" not in missing
    assert "ml" not in missing


def test_clone_public_repository_case_uses_repo_agnostic_shallow_clone_settings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    monkeypatch.setattr(public_repo_matrix, "_git_executable", lambda: "git")
    monkeypatch.setenv("KEEP_EXISTING_ENV", "1")
    captured_commands: list[list[str]] = []
    captured_kwargs: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object):
        captured_commands.append(command)
        captured_kwargs.append(dict(kwargs))
        if command[1] == "clone":
            checkout_path = Path(command[-1])
            checkout_path.mkdir(parents=True, exist_ok=True)
            (checkout_path / ".git").mkdir(exist_ok=True)
            return public_repo_matrix.subprocess.CompletedProcess(command, 0, "", "")
        if command[-4:] == ["ls-tree", "-r", "--name-only", "--full-tree", "HEAD"][-4:]:
            return public_repo_matrix.subprocess.CompletedProcess(
                command,
                0,
                "src/click/core.py\nREADME.md\n",
                "",
            )
        checkout_path = Path(command[2])
        if command[-3:] == ["checkout", "--force", "HEAD"]:
            (checkout_path / "README.md").write_text("# click\n", encoding="utf-8")
        return public_repo_matrix.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_language_for_path",
        lambda path, repo_path=None: "python" if path.endswith(".py") else "txt",
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_probe_collection_rank",
        lambda relative_path, repo_path=None: (relative_path,),
    )

    monkeypatch.setattr(public_repo_matrix.subprocess, "run", fake_run)

    checkout_path = public_repo_matrix.clone_public_repository_case(case, checkout_root=tmp_path)

    assert checkout_path == tmp_path / "python-pallets-click"
    assert captured_commands == [
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--single-branch",
            "--no-tags",
            "--no-checkout",
            "https://github.com/pallets/click.git",
            str(checkout_path),
        ],
        [
            "git",
            "-C",
            str(checkout_path),
            "ls-tree",
            "-r",
            "--name-only",
            "--full-tree",
            "HEAD",
        ],
        [
            "git",
            "-C",
            str(checkout_path),
            "sparse-checkout",
            "init",
            "--no-cone",
        ],
        [
            "git",
            "-C",
            str(checkout_path),
            "sparse-checkout",
            "set",
            "--no-cone",
            "/src/click",
            "/src/click/**",
        ],
        [
            "git",
            "-C",
            str(checkout_path),
            "checkout",
            "--force",
            "HEAD",
        ],
    ]
    command_kwargs = captured_kwargs[0]
    assert command_kwargs["timeout"] == 300
    assert command_kwargs["capture_output"] is True
    assert command_kwargs["check"] is False
    clone_environment = command_kwargs["env"]
    assert clone_environment["GIT_LFS_SKIP_SMUDGE"] == "1"
    assert clone_environment["GIT_TERMINAL_PROMPT"] == "0"
    assert clone_environment["KEEP_EXISTING_ENV"] == "1"


def test_public_repository_sparse_checkout_patterns_are_recursive_and_space_safe() -> None:
    assert public_repo_matrix._public_repository_sparse_checkout_patterns(
        [
            "src/click",
            "large/QAOA_3SAT_N10000 P",
            "README.md",
        ]
    ) == [
        "/src/click",
        "/src/click/**",
        "/large/QAOA_3SAT_N10000 P",
        "/large/QAOA_3SAT_N10000 P/**",
        "/README.md",
        "/README.md/**",
    ]


def test_normalized_public_repository_focus_paths_collapse_descendants() -> None:
    assert public_repo_matrix._normalized_public_repository_focus_paths(
        [
            "modules/dists",
            "modules/dists/dims",
            "modules/internal",
            "modules/internal/comm/ofi",
            "modules/layouts",
        ]
    ) == [
        "modules/dists",
        "modules/internal",
        "modules/layouts",
    ]


def test_normalized_public_repository_focus_paths_collapse_descendants_when_ancestor_arrives_late() -> None:
    assert public_repo_matrix._normalized_public_repository_focus_paths(
        [
            "test/gleam",
            "src/gleam",
            "gleam.toml",
            "test",
        ]
    ) == [
        "test",
        "src/gleam",
        "gleam.toml",
    ]


def test_compacted_public_repository_focus_path_falls_back_when_collapse_is_not_prefix() -> None:
    assert public_repo_matrix._compacted_public_repository_focus_path(
        "large/QAOA_3SAT_N10000_p1/random_QAOA_angles_k3_N10000_p1.qasm"
    ) == "large/QAOA_3SAT_N10000_p1"


def test_clone_public_repository_case_reuses_existing_checkout_without_recloning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    checkout_path = tmp_path / "python-pallets-click"
    (checkout_path / ".git").mkdir(parents=True)
    (checkout_path / "README.md").write_text("# click\n", encoding="utf-8")

    def fail_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("existing checkout should be reused without invoking git clone")

    monkeypatch.setattr(public_repo_matrix.subprocess, "run", fail_run)

    reused_path = public_repo_matrix.clone_public_repository_case(case, checkout_root=tmp_path)

    assert reused_path == checkout_path


def test_clone_public_repository_case_waits_for_checkout_lock_and_reuses_finished_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    checkout_path = tmp_path / "python-pallets-click"
    lock_path = tmp_path / "python-pallets-click.lock"
    lock_path.mkdir()
    sleep_calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        lock_path.rmdir()
        (checkout_path / ".git").mkdir(parents=True)
        (checkout_path / "README.md").write_text("# click\n", encoding="utf-8")

    def fail_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("finished checkout should be reused without invoking git clone")

    monkeypatch.setattr(public_repo_matrix.time, "sleep", fake_sleep)
    monkeypatch.setattr(public_repo_matrix.subprocess, "run", fail_run)

    reused_path = public_repo_matrix.clone_public_repository_case(case, checkout_root=tmp_path)

    assert reused_path == checkout_path
    assert sleep_calls == [
        public_repo_matrix._PUBLIC_REPOSITORY_CHECKOUT_LOCK_POLL_INTERVAL_SECONDS
    ]
    assert not lock_path.exists()


def test_clone_public_repository_case_reclones_incomplete_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    checkout_path = tmp_path / "typst-typst-packages"
    git_dir = checkout_path / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "shallow.lock").write_text("", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object):
        captured["command"] = command
        checkout_path = Path(command[-1])
        checkout_path.mkdir(parents=True, exist_ok=True)
        (checkout_path / ".git").mkdir(exist_ok=True)
        (checkout_path / "README.md").write_text("# packages\n", encoding="utf-8")
        return public_repo_matrix.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(public_repo_matrix, "_git_executable", lambda: "git")
    monkeypatch.setattr(public_repo_matrix.subprocess, "run", fake_run)
    monkeypatch.setattr(
        public_repo_matrix,
        "_materialize_public_repository_checkout",
        lambda *_args, **_kwargs: (checkout_path / "README.md").write_text(
            "# packages\n", encoding="utf-8"
        ),
    )

    reused_path = public_repo_matrix.clone_public_repository_case(case, checkout_root=tmp_path)

    assert reused_path == checkout_path
    assert captured["command"] == [
        "git",
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--single-branch",
        "--no-tags",
        "--no-checkout",
        "https://github.com/typst/packages.git",
        str(checkout_path),
    ]


def test_clone_public_repository_case_retries_after_transient_clone_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object):
        calls.append(command)
        checkout_path = Path(command[-1])
        if len(calls) == 1:
            checkout_path.mkdir(parents=True, exist_ok=True)
            (checkout_path / ".git").mkdir(exist_ok=True)
            return public_repo_matrix.subprocess.CompletedProcess(
                command,
                128,
                "",
                "fatal: fetch-pack: invalid index-pack output",
            )
        checkout_path.mkdir(parents=True, exist_ok=True)
        (checkout_path / ".git").mkdir(exist_ok=True)
        (checkout_path / "README.md").write_text("# packages\n", encoding="utf-8")
        return public_repo_matrix.subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(public_repo_matrix, "_git_executable", lambda: "git")
    monkeypatch.setattr(public_repo_matrix.subprocess, "run", fake_run)
    monkeypatch.setattr(
        public_repo_matrix,
        "_materialize_public_repository_checkout",
        lambda *_args, **_kwargs: (tmp_path / "typst-typst-packages" / "README.md").write_text(
            "# packages\n", encoding="utf-8"
        ),
    )

    checkout_path = public_repo_matrix.clone_public_repository_case(case, checkout_root=tmp_path)

    assert checkout_path == tmp_path / "typst-typst-packages"
    assert len(calls) == 2
    assert (checkout_path / "README.md").is_file()


def test_run_public_repository_matrix_continues_after_case_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    timed_case = public_repo_matrix.PublicRepositoryCase(
        language="python",
        repository_url="https://github.com/pallets/click.git",
        expected_primary_ecosystem="python",
    )
    succeeding_case = public_repo_matrix.PublicRepositoryCase(
        language="typescript",
        repository_url="https://github.com/sindresorhus/ky.git",
        expected_primary_ecosystem="typescript",
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "ordered_public_repository_cases",
        lambda **_kwargs: [timed_case, succeeding_case],
    )

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        _checkout_context_for(tmp_path / "checkouts" / "repo"),
    )

    def fake_seed_plan_case(case, **_kwargs):
        if case.language == "python":
            time.sleep(2)
        return {
            "case": public_repo_matrix.asdict(case),
            "primary_ecosystem": case.expected_primary_ecosystem,
            "primary_match": True,
        }

    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        fake_seed_plan_case,
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        case_timeout_seconds=1,
    )

    assert result["cases"][0]["case"]["language"] == "python"
    assert result["cases"][0]["error"]["code"] == "PublicRepositoryCaseTimeoutError"
    assert result["cases"][1]["case"]["language"] == "typescript"
    assert result["cases"][1]["primary_match"] is True
    assert result["public_case_progress"]["selected_case_language_count"] == 2
    assert result["public_case_progress"]["passing_case_language_count"] == 1


def test_run_public_repository_matrix_does_not_apply_case_timeout_to_checkout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    case = public_repo_matrix.PublicRepositoryCase(
        language="typst",
        repository_url="https://github.com/typst/packages.git",
        expected_primary_ecosystem="typst",
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "ordered_public_repository_cases",
        lambda **_kwargs: [case],
    )

    @contextmanager
    def fake_checkout_context(*_args: object, **_kwargs: object):
        time.sleep(2)
        checkout_path = tmp_path / "typst-typst-packages"
        checkout_path.mkdir(parents=True, exist_ok=True)
        yield checkout_path

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        fake_checkout_context,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda case, **_kwargs: {
            "case": public_repo_matrix.asdict(case),
            "primary_ecosystem": case.expected_primary_ecosystem,
            "primary_match": True,
        },
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        case_timeout_seconds=1,
    )

    assert result["cases"][0]["case"]["language"] == "typst"
    assert "error" not in result["cases"][0]
    assert result["cases"][0]["primary_match"] is True


def test_run_public_repository_matrix_supports_explicit_duplicate_language_cases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_case = public_repo_matrix.PublicRepositoryCase(
        language="rebol",
        repository_url="https://github.com/gchiu/Rebol3.git",
        expected_primary_ecosystem="rebol",
    )
    second_case = public_repo_matrix.PublicRepositoryCase(
        language="rebol",
        repository_url="https://github.com/rebolek/lest.git",
        expected_primary_ecosystem="rebol",
    )

    @contextmanager
    def duplicate_checkout_context(case, **_kwargs: object):
        checkout_path = tmp_path / public_repo_matrix._case_checkout_name(case)
        checkout_path.mkdir(parents=True, exist_ok=True)
        yield checkout_path

    monkeypatch.setattr(
        public_repo_matrix,
        "_public_repository_checkout_context",
        duplicate_checkout_context,
    )
    monkeypatch.setattr(
        public_repo_matrix,
        "_run_public_repository_seed_plan_for_checkout",
        lambda case, **kwargs: {
            "case": public_repo_matrix.asdict(case),
            "case_key": public_repo_matrix._public_repository_case_key(case),
            "repo_path": str(kwargs["repo_path"]),
            "primary_ecosystem": case.expected_primary_ecosystem,
            "primary_match": "Rebol3" in case.repository_url,
        },
    )

    result = public_repo_matrix.run_public_repository_matrix(
        mode="seed_plan",
        checkout_root=tmp_path,
        runtime_root=tmp_path,
        cases=[first_case, second_case],
    )

    assert result["case_count"] == 2
    assert [case["case_key"] for case in result["cases"]] == [
        "rebol:https://github.com/gchiu/Rebol3.git",
        "rebol:https://github.com/rebolek/lest.git",
    ]
    assert result["public_case_progress"]["selected_case_count"] == 2
    assert result["public_case_progress"]["selected_case_keys"] == [
        "rebol:https://github.com/gchiu/Rebol3.git",
        "rebol:https://github.com/rebolek/lest.git",
    ]
    assert result["public_case_progress"]["selected_case_language_count"] == 1
    assert result["public_case_progress"]["passing_case_count"] == 1
    assert result["public_case_progress"]["passing_case_keys"] == [
        "rebol:https://github.com/gchiu/Rebol3.git"
    ]
    assert result["public_case_progress"]["passing_case_language_count"] == 1


@pytest.mark.parametrize(
    ("expected_primary_ecosystem", "relative_paths", "expected_focus_paths"),
    [
        (
            "opencl",
            ["kernels/add.cl", "kernels/lib/math.clh", "docs/readme.md"],
            ["kernels", "kernels/lib"],
        ),
        (
            "qsharp",
            ["src/Main.qs", "samples/Teleport.qs", "README.md"],
            ["src", "samples"],
        ),
        (
            "vb6",
            ["vb6/Project1.vbp", "vb6/forms/Form1.frm", "docs/readme.md"],
            ["vb6", "vb6/forms"],
        ),
    ],
)
def test_expected_ecosystem_focus_paths_from_relative_files_uses_path_hints_when_probe_is_unknown(
    tmp_path: Path,
    monkeypatch,
    expected_primary_ecosystem: str,
    relative_paths: list[str],
    expected_focus_paths: list[str],
) -> None:
    repo_path = tmp_path / "no-checkout-clone"
    repo_path.mkdir()

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        lambda *_args, **_kwargs: {"unknown"},
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=relative_paths,
        repo_path=repo_path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )

    assert focus_paths == expected_focus_paths


def test_expected_ecosystem_focus_paths_from_relative_files_short_circuit_vb6_path_hints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "vb6-path-hint-short-circuit"
    repo_path.mkdir()

    def _unexpected_candidate_ecosystems(*_args, **_kwargs) -> set[str]:
        raise AssertionError("vb6 path hints should bypass candidate ecosystem probing")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        _unexpected_candidate_ecosystems,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "vb6/Project1.vbp",
            "vb6/forms/Form1.frm",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="vb6",
    )

    assert focus_paths == ["vb6", "vb6/forms"]


def test_expected_ecosystem_focus_paths_from_relative_files_short_circuit_path_hints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "path-hint-short-circuit"
    repo_path.mkdir()

    def _unexpected_candidate_ecosystems(*_args, **_kwargs) -> set[str]:
        raise AssertionError("path hints should bypass candidate ecosystem probing")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        _unexpected_candidate_ecosystems,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "kernels/add.cl",
            "kernels/lib/math.clh",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
    )

    assert focus_paths == ["kernels", "kernels/lib"]


def test_expected_ecosystem_focus_paths_from_relative_files_skips_deferred_probe_when_hints_fill_limit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "path-hint-limit-short-circuit"
    repo_path.mkdir()

    def _unexpected_candidate_ecosystems(*_args, **_kwargs) -> set[str]:
        raise AssertionError("deferred candidate probing should be skipped once hints fill the limit")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        _unexpected_candidate_ecosystems,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "kernels/add.cl",
            "kernels/lib/math.clh",
            "README.md",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
        limit=2,
    )

    assert focus_paths == ["kernels", "kernels/lib"]


def test_expected_ecosystem_focus_paths_from_relative_files_stops_after_rank_buffer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "path-hint-rank-buffer-short-circuit"
    repo_path.mkdir()

    def _guarded_hint_match(path: str, *, expected_primary_ecosystem: str) -> bool:
        if path == "sentinel/boom.cl":
            raise AssertionError("hint scan should stop once enough ranked focus roots are found")
        return expected_primary_ecosystem == "opencl" and path.endswith((".cl", ".clh"))

    def _unexpected_candidate_ecosystems(*_args, **_kwargs) -> set[str]:
        raise AssertionError("rank-buffer short circuit should bypass deferred candidate probing")

    monkeypatch.setattr(
        public_repo_matrix,
        "_path_matches_expected_ecosystem_hint",
        _guarded_hint_match,
    )
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        _unexpected_candidate_ecosystems,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "a/one.cl",
            "a/two.clh",
            "b/one.cl",
            "b/two.clh",
            "a/three.cl",
            "b/three.clh",
            "sentinel/boom.cl",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="opencl",
        limit=2,
    )

    assert focus_paths == ["a", "b"]


@pytest.mark.parametrize(
    ("path", "expected_primary_ecosystem"),
    [
        ("src/main.c", "c"),
        ("lib/http.dart", "dart"),
        ("pkg/service.go", "go"),
        ("src/app.py", "python"),
        ("src/Main.java", "java"),
    ],
)
def test_path_matches_expected_ecosystem_hint_uses_static_language_fallback(
    path: str,
    expected_primary_ecosystem: str,
) -> None:
    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        path,
        expected_primary_ecosystem=expected_primary_ecosystem,
    )


def test_expected_ecosystem_focus_paths_from_relative_files_short_circuit_static_language_hints(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "c-static-hint-short-circuit"
    repo_path.mkdir()

    def _unexpected_candidate_ecosystems(*_args, **_kwargs) -> set[str]:
        raise AssertionError("static language hints should bypass candidate ecosystem probing")

    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        _unexpected_candidate_ecosystems,
    )

    focus_paths = public_repo_matrix._expected_ecosystem_focus_paths_from_relative_files(
        relative_paths=[
            "src/main.c",
            "src/lib/helper.c",
            "include/helper.h",
            "README.md",
        ],
        repo_path=repo_path,
        expected_primary_ecosystem="c",
        limit=2,
    )

    assert focus_paths == ["src/lib", "src"]


def test_path_candidate_ecosystems_reuses_repo_scoped_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "candidate-ecosystem-cache"
    repo_path.mkdir()
    calls = {"value": 0}

    def fake_candidate_ecosystems_for_path(path: str, *, repo_path: Path) -> set[str]:
        calls["value"] += 1
        assert path == "ballerina/main.bal"
        return {"ballerina"}

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    monkeypatch.setattr(
        public_repo_matrix.probe_module,
        "_candidate_ecosystems_for_path",
        fake_candidate_ecosystems_for_path,
    )

    first = public_repo_matrix._path_candidate_ecosystems(
        "ballerina/main.bal",
        repo_path=repo_path,
    )
    second = public_repo_matrix._path_candidate_ecosystems(
        "ballerina/main.bal",
        repo_path=repo_path,
    )

    assert first == {"ballerina"}
    assert second == {"ballerina"}
    assert calls["value"] == 1


def test_prime_public_repository_probe_runtime_primes_parquet_and_analysis_fingerprint(
    monkeypatch,
) -> None:
    events: list[str] = []

    monkeypatch.setattr(
        public_repo_matrix,
        "initialize_pyarrow_parquet_runtime",
        lambda: events.append("pyarrow"),
    )
    monkeypatch.setattr(
        public_repo_matrix.runtime_internal_contracts,
        "warm_repository_snapshot_parquet_contracts",
        lambda: events.append("contracts"),
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_cache,
        "_analysis_implementation_fingerprint",
        lambda: events.append("fingerprint") or "fingerprint",
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_adapter_parser_dispatch_module",
        lambda: events.append("adapter_dispatch") or object(),
    )
    monkeypatch.setattr(
        public_repo_matrix.repository_service,
        "_analysis_workflow_module",
        lambda: events.append("analysis_workflow") or object(),
    )

    public_repo_matrix.prime_public_repository_probe_runtime()

    assert events == [
        "pyarrow",
        "contracts",
        "fingerprint",
        "adapter_dispatch",
        "analysis_workflow",
    ]


def test_expected_ecosystem_hint_metadata_cache_clears_with_prepass_cache(
    monkeypatch,
) -> None:
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    export_calls: list[str] = []

    class _FakeOpenClAdapter:
        OPENCL_SOURCE_SUFFIXES = (".cl", ".clh")

        @staticmethod
        def has_opencl_path_hints(*, path: Path) -> bool:
            return path.name == "special-opencl-kernel"

    def fake_get_export(name: str):
        export_calls.append(name)
        if name != "opencl_adapter":
            raise AttributeError(name)
        return _FakeOpenClAdapter

    monkeypatch.setattr(
        public_repo_matrix.repository_compat_exports,
        "get_export",
        fake_get_export,
    )

    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "kernels/add.cl",
        expected_primary_ecosystem="opencl",
    )
    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "kernels/lib/math.clh",
        expected_primary_ecosystem="opencl",
    )
    assert export_calls == ["opencl_adapter"]

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "special-opencl-kernel",
        expected_primary_ecosystem="opencl",
    )
    assert export_calls == ["opencl_adapter", "opencl_adapter"]


def test_expected_ecosystem_hint_result_cache_clears_with_prepass_cache(
    monkeypatch,
) -> None:
    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()
    path_hint_calls: list[str] = []

    class _FakeOpenClAdapter:
        OPENCL_SOURCE_SUFFIXES = ()

        @staticmethod
        def has_opencl_path_hints(*, path: Path) -> bool:
            path_hint_calls.append(path.as_posix())
            return path.name == "special-opencl-kernel"

    def fake_get_export(name: str):
        if name != "opencl_adapter":
            raise AttributeError(name)
        return _FakeOpenClAdapter

    monkeypatch.setattr(
        public_repo_matrix.repository_compat_exports,
        "get_export",
        fake_get_export,
    )

    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "special-opencl-kernel",
        expected_primary_ecosystem="opencl",
    )
    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "special-opencl-kernel",
        expected_primary_ecosystem="opencl",
    )
    assert path_hint_calls == ["special-opencl-kernel"]

    public_repo_matrix.clear_public_repository_prepass_focus_path_cache()

    assert public_repo_matrix._path_matches_expected_ecosystem_hint(
        "special-opencl-kernel",
        expected_primary_ecosystem="opencl",
    )
    assert path_hint_calls == ["special-opencl-kernel", "special-opencl-kernel"]
