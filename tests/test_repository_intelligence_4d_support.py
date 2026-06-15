from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_four_d_parser_dispatch as repository_four_d_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    four_d_analysis_support as repository_four_d_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    four_d_primitives as repository_four_d_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_4d_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["4d"] is (
        repository_four_d_parser_dispatch._parse_four_d_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["4d"] is (
        repository_four_d_parser_dispatch._parse_four_d_dependencies_only
    )


def test_repository_intelligence_4d_helpers_are_modularized() -> None:
    assert repository_service.four_d_adapter.has_4d_path_hints is (
        repository_four_d_primitives.has_4d_path_hints
    )
    assert repository_service.four_d_adapter.is_probable_4d_source is (
        repository_four_d_analysis_support.is_probable_4d_source
    )
    assert repository_service.four_d_adapter.module_aliases_for_path is (
        repository_four_d_analysis_support.module_aliases_for_path
    )
    assert repository_service.four_d_adapter.parse_dependencies_only is (
        repository_four_d_analysis_support.parse_dependencies_only
    )
    assert repository_service.four_d_adapter.parse_file is (
        repository_four_d_analysis_support.parse_file
    )


def test_4d_adapter_module_aliases_include_class_and_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "4d-alias-repo"
    class_dir = repo_path / "Project" / "Sources" / "Classes"
    class_dir.mkdir(parents=True)
    (class_dir / "OAuth2Provider.4dm").write_text(
        "Class extends _BaseClass\n"
        "property clientId : Text\n"
        "Function getToken() : Object\n"
        "    return This.clientId\n"
        "End function\n",
        encoding="utf-8",
    )

    aliases = repository_service.four_d_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Project/Sources/Classes/OAuth2Provider.4dm",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "Project/Sources/Classes/OAuth2Provider.4dm" in aliases
    assert "OAuth2Provider" in aliases
    assert "cs.OAuth2Provider" in aliases
    assert "clientId" in aliases
    assert "getToken" in aliases


def test_4d_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "4d-inline-text-repo"
    class_dir = repo_path / "Project" / "Sources" / "Classes"
    class_dir.mkdir(parents=True)
    source_text = (
        "Class extends _BaseClass\n"
        "property clientId : Text\n"
        "Function getToken() : Object\n"
        "    return This.clientId\n"
        "End function\n"
    )
    file_path = class_dir / "OAuth2Provider.4dm"
    file_path.write_text(source_text, encoding="utf-8")

    def _unexpected_read_text(self: Path, *args, **kwargs) -> str:
        raise AssertionError(f"module_aliases_for_path should not reread {self}")

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    aliases = repository_service.four_d_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="Project/Sources/Classes/OAuth2Provider.4dm",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
    )

    assert "OAuth2Provider" in aliases
    assert "clientId" in aliases
    assert "getToken" in aliases
    assert "cs.OAuth2Provider" in aliases


def test_4d_adapter_parse_file_resolves_class_dependencies_and_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "Project/Sources/Classes/_BaseClass.4dm",
            "Project/Sources/Classes/OAuth2Provider.4dm",
            "Project/Sources/Methods/New OAuth2 provider.4dm",
        ],
        root_path=Path("/tmp/4d-index"),
    )
    text = (
        '#DECLARE($inParameters : Object) : cs.OAuth2Provider\n'
        "var $provider : cs.OAuth2Provider\n"
        "return cs.OAuth2Provider.new($inParameters)\n"
    )

    symbols, dependencies, references = repository_service.four_d_adapter.parse_file(
        "Project/Sources/Methods/New OAuth2 provider.4dm",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "New OAuth2 provider" for symbol in symbols)
    assert any(
        dependency.target_file == "Project/Sources/Classes/OAuth2Provider.4dm"
        and dependency.dependency_type == "uses"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("OAuth2Provider",) for reference in references)


def test_4d_language_detection_supports_4dm_sources_without_overclaiming() -> None:
    assert ".4dm" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("Project/Sources/Classes/OAuth2Provider.4dm"),
            text="Class extends _BaseClass\nFunction getToken() : Object\nEnd function\n",
        )
        == "4d"
    )
    assert (
        repository_service._language_for_path(
            Path("Project/Sources/Methods/New OAuth2 provider.4dm"),
            text='#DECLARE($inParameters : Object) : cs.OAuth2Provider\nreturn cs.OAuth2Provider.new($inParameters)\n',
        )
        == "4d"
    )
    assert (
        repository_service._language_for_path(
            Path("notes/example.4dm"),
            text="<xml />\n",
        )
        == "unknown"
    )


def test_candidate_ecosystems_for_path_detects_4d_with_repo_context(tmp_path: Path) -> None:
    repo_path = tmp_path / "4d-candidate-repo"
    class_dir = repo_path / "Project" / "Sources" / "Classes"
    class_dir.mkdir(parents=True)
    (class_dir / "OAuth2Provider.4dm").write_text(
        "Class extends _BaseClass\nFunction getToken() : Object\nEnd function\n",
        encoding="utf-8",
    )

    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    assert probe_module._candidate_ecosystems_for_path(
        "Project/Sources/Classes/OAuth2Provider.4dm",
        repo_path=repo_path,
    ) == {"4d"}


def test_operational_seed_plan_without_diagnostics_promotes_4d_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "4d-profile-repo"
    class_dir = repo_path / "Project" / "Sources" / "Classes"
    method_dir = repo_path / "Project" / "Sources" / "Methods"
    class_dir.mkdir(parents=True)
    method_dir.mkdir(parents=True)
    (repo_path / "Project" / "4D NetKit.4DProject").write_text("{}", encoding="utf-8")
    (repo_path / "Project" / "Sources" / "settings.4DSettings").write_text("{}", encoding="utf-8")
    for index in range(4):
        (class_dir / f"Provider{index}.4dm").write_text(
            "Class extends _BaseClass\n"
            "property clientId : Text\n"
            "Function getToken() : Object\n"
            "    return This.clientId\n"
            "End function\n",
            encoding="utf-8",
        )
    for index in range(4):
        (method_dir / f"New Provider {index}.4dm").write_text(
            f"#DECLARE($inParameters : Object) : cs.Provider{index}\n"
            f"return cs.Provider{index}.new($inParameters)\n",
            encoding="utf-8",
        )
    (repo_path / "scripts").mkdir(parents=True)
    for index in range(2):
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper() -> int:\n    return 1\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "4d" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "4d"
    assert any(path.endswith(".4dm") for path in seed_plan["entrypoint_files"])


def test_4d_comment_stripping_cache_reuses_identical_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_four_d_primitives.clear_strip_comments_cache()
    text = (
        "Class extends _BaseClass\n"
        "property clientId : Text\n"
        "Function getToken() : Object\n"
        "    return This.clientId // keep this cached\n"
        "End function\n"
    )
    call_count = 0
    original = repository_four_d_primitives._strip_comments_uncached

    def _counting_strip_comments_uncached(source_text: str) -> str:
        nonlocal call_count
        call_count += 1
        return original(source_text)

    monkeypatch.setattr(
        repository_four_d_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments_uncached,
    )

    repository_service.four_d_adapter.parse_file(
        "Project/Sources/Classes/OAuth2Provider.4dm",
        text,
        {},
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert call_count == 1
