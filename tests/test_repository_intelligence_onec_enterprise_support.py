from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_onec_enterprise_parser_dispatch as repository_onec_enterprise_parser_dispatch,
)
from apps.api_server.services.repository_intelligence_adapters import (
    onec_enterprise_analysis_support as repository_onec_enterprise_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    onec_enterprise_primitives as repository_onec_enterprise_primitives,
)
from benchmarks.repository_intelligence_real_repo_probe import (
    _derive_operational_seed_plan_without_diagnostics,
)


def test_repository_intelligence_onec_enterprise_parser_dispatch_helpers_are_modularized() -> None:
    assert repository_service._REGISTERED_ADAPTER_FILE_PARSERS["1centerprise"] is (
        repository_onec_enterprise_parser_dispatch._parse_onec_enterprise_file
    )
    assert repository_service._REGISTERED_ADAPTER_DEPENDENCY_PARSERS["1centerprise"] is (
        repository_onec_enterprise_parser_dispatch._parse_onec_enterprise_dependencies_only
    )


def test_repository_intelligence_onec_enterprise_helpers_are_modularized() -> None:
    assert repository_service.onec_enterprise_adapter.has_onec_enterprise_path_hints is (
        repository_onec_enterprise_primitives.has_onec_enterprise_path_hints
    )
    assert repository_service.onec_enterprise_adapter.is_probable_onec_enterprise_source is (
        repository_onec_enterprise_analysis_support.is_probable_onec_enterprise_source
    )
    assert repository_service.onec_enterprise_adapter.module_aliases_for_path is (
        repository_onec_enterprise_analysis_support.module_aliases_for_path
    )
    assert repository_service.onec_enterprise_adapter.parse_dependencies_only is (
        repository_onec_enterprise_analysis_support.parse_dependencies_only
    )
    assert repository_service.onec_enterprise_adapter.parse_file is (
        repository_onec_enterprise_analysis_support.parse_file
    )


def test_onec_enterprise_adapter_module_aliases_include_declared_symbols(tmp_path: Path) -> None:
    repo_path = tmp_path / "onec-alias-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "helpers.os").write_text(
        "#Использовать common\n"
        "Функция ВыполнитьПомощь() Экспорт\n"
        "    Возврат Истина;\n"
        "КонецФункции\n",
        encoding="utf-8",
    )

    aliases = repository_service.onec_enterprise_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/helpers.os",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/helpers.os" in aliases
    assert "helpers" in aliases
    assert "ВыполнитьПомощь" in aliases
    assert "выполнитьпомощь" in aliases


def test_onec_enterprise_adapter_parse_file_resolves_imports_and_references() -> None:
    module_index = repository_service._build_module_index(
        [
            "src/main.os",
            "src/helpers.os",
        ],
        root_path=Path("/tmp/onec-index"),
    )
    text = (
        "#Использовать helpers\n"
        "Функция Запустить() Экспорт\n"
        "    Возврат ВыполнитьПомощь();\n"
        "КонецФункции\n"
    )

    symbols, dependencies, references = repository_service.onec_enterprise_adapter.parse_file(
        "src/main.os",
        text,
        module_index,
        stable_identifier=repository_service._stable_identifier,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert any(symbol.symbol_name == "Запустить" and symbol.symbol_kind == "function" for symbol in symbols)
    assert any(
        dependency.target_file == "src/helpers.os" and dependency.dependency_type == "imports"
        for dependency in dependencies
    )
    assert any(reference.target_names == ("helpers",) for reference in references)
    assert any(reference.target_names == ("ВыполнитьПомощь",) for reference in references)


def test_onec_enterprise_language_detection_supports_bsl_and_os_sources_without_overclaiming() -> None:
    assert ".bsl" in repository_service._TEXT_FILE_SUFFIXES
    assert ".os" in repository_service._TEXT_FILE_SUFFIXES
    assert (
        repository_service._language_for_path(
            Path("src/main.os"),
            text="#Использовать helpers\nФункция Запустить() Экспорт\nКонецФункции\n",
        )
        == "1centerprise"
    )
    assert (
        repository_service._language_for_path(
            Path("src/ObjectModule.bsl"),
            text="Процедура Выполнить() Экспорт\nКонецПроцедуры\n",
        )
        == "1centerprise"
    )
    assert (
        repository_service._language_for_path(
            Path("src/main.os"),
            text="<xml />\n",
        )
        == "unknown"
    )


def test_operational_seed_plan_without_diagnostics_promotes_onec_enterprise_when_surface_dominates(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "onec-profile-repo"
    (repo_path / "src").mkdir(parents=True)
    for index in range(8):
        (repo_path / "src" / f"module_{index}.os").write_text(
            f"Функция Выполнить{index}() Экспорт\n"
            "    Возврат Истина;\n"
            "КонецФункции\n",
            encoding="utf-8",
        )
    for index in range(2):
        (repo_path / "scripts").mkdir(parents=True, exist_ok=True)
        (repo_path / "scripts" / f"helper_{index}.py").write_text(
            "def helper():\n    return True\n",
            encoding="utf-8",
        )

    seed_plan = _derive_operational_seed_plan_without_diagnostics(
        repo_path=repo_path,
        focus_paths=["."],
        max_files=128,
    )

    assert "1centerprise" in seed_plan["detected_ecosystems"]
    assert seed_plan["operational_ecosystems"][0] == "1centerprise"
