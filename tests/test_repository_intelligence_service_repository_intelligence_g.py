"""Tests for repository_intelligence_service: repository_intelligence_g.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_erlang_resolve_module_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/cowboy.erl"

    monkeypatch.setattr(repository_service.erlang_adapter, "resolve_module", _fake_resolve_module)

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._resolve_erlang_module("cowboy", module_index)

    assert result == "src/cowboy.erl"
    assert observed["import_target"] == "cowboy"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_erlang_resolve_include_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        is_lib: bool,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["is_lib"] = is_lib
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "include/cowboy.hrl"

    monkeypatch.setattr(repository_service.erlang_adapter, "resolve_include", _fake_resolve_include)

    module_index = {"include/cowboy.hrl": "include/cowboy.hrl"}

    result = repository_service._resolve_erlang_include(
        current_file="src/main.erl",
        import_target="cowboy.hrl",
        is_lib=False,
        module_index=module_index,
    )

    assert result == "include/cowboy.hrl"
    assert observed["current_file"] == "src/main.erl"
    assert observed["import_target"] == "cowboy.hrl"
    assert observed["is_lib"] is False
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_erlang_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
        resolve_include: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        observed["resolve_include"] = resolve_include
        return ()

    monkeypatch.setattr(
        repository_service.erlang_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._parse_erlang_dependencies_only(
        "src/main.erl",
        "-import(cowboy, [start/0]).",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.erl"
    assert observed["text"] == "-import(cowboy, [start/0])."
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_erlang_module
    assert observed["resolve_include"] is repository_service._resolve_erlang_include


def test_repository_intelligence_erlang_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_module: Any,
        resolve_include: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_module"] = resolve_module
        observed["resolve_include"] = resolve_include
        return (), (), ()

    monkeypatch.setattr(repository_service.erlang_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/cowboy.erl": "src/cowboy.erl"}

    result = repository_service._parse_erlang_file(
        "src/main.erl",
        "-import(cowboy, [start/0]).",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.erl"
    assert observed["text"] == "-import(cowboy, [start/0])."
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_module"] is repository_service._resolve_erlang_module
    assert observed["resolve_include"] is repository_service._resolve_erlang_include


def test_repository_intelligence_swift_helpers_are_modularized() -> None:
    assert repository_service._SWIFT_IMPORT_RE is repository_service.swift_adapter.IMPORT_RE
    assert repository_service._SWIFT_TYPE_DECL_RE is repository_service.swift_adapter.TYPE_DECL_RE
    assert repository_service._SWIFT_TYPE_REFERENCE_RE is (
        repository_service.swift_adapter.TYPE_REFERENCE_RE
    )


def test_repository_intelligence_swift_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "Sources/Acme/Command.swift"

    monkeypatch.setattr(repository_service.swift_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._resolve_swift_import("ArgumentParser", module_index)

    assert result == "Sources/Acme/Command.swift"
    assert observed["import_target"] == "ArgumentParser"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_swift_same_target_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_same_target_reference(
        *,
        current_file: str,
        type_name: str,
        module_index: dict[str, str],
        module_index_values: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["type_name"] = type_name
        observed["module_index"] = module_index
        observed["module_index_values"] = module_index_values
        return "Sources/Acme/CommandConfiguration.swift"

    monkeypatch.setattr(
        repository_service.swift_adapter,
        "resolve_same_target_reference",
        _fake_resolve_same_target_reference,
    )

    module_index = {
        "Sources/Acme/CommandConfiguration.swift": "Sources/Acme/CommandConfiguration.swift"
    }

    result = repository_service._resolve_swift_same_target_reference(
        current_file="Sources/Acme/ParsableCommand.swift",
        type_name="CommandConfiguration",
        module_index=module_index,
    )

    assert result == "Sources/Acme/CommandConfiguration.swift"
    assert observed["current_file"] == "Sources/Acme/ParsableCommand.swift"
    assert observed["type_name"] == "CommandConfiguration"
    assert observed["module_index"] is module_index
    assert observed["module_index_values"] is repository_service._module_index_values


def test_repository_intelligence_swift_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
        resolve_same_target_reference: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        observed["resolve_same_target_reference"] = resolve_same_target_reference
        return ()

    monkeypatch.setattr(
        repository_service.swift_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._parse_swift_dependencies_only(
        "Sources/Acme/App.swift",
        "import ArgumentParser",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "Sources/Acme/App.swift"
    assert observed["text"] == "import ArgumentParser"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_swift_import
    assert observed["resolve_same_target_reference"] is (
        repository_service._resolve_swift_same_target_reference
    )


def test_repository_intelligence_swift_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        resolve_import: Any,
        resolve_same_target_reference: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        observed["resolve_same_target_reference"] = resolve_same_target_reference
        return (), (), ()

    monkeypatch.setattr(repository_service.swift_adapter, "parse_file", _fake_parse_file)

    module_index = {"Sources/Acme/Command.swift": "Sources/Acme/Command.swift"}

    result = repository_service._parse_swift_file(
        "Sources/Acme/App.swift",
        "struct App {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "Sources/Acme/App.swift"
    assert observed["text"] == "struct App {}"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_swift_import
    assert observed["resolve_same_target_reference"] is (
        repository_service._resolve_swift_same_target_reference
    )


def test_repository_intelligence_swift_parse_file_caches_same_target_resolution() -> None:
    calls: list[str] = []

    def _fake_collect_type_symbol_entries(
        _text: str,
        *,
        file_path: str,
        regex: Any,
    ) -> list[dict[str, Any]]:
        del regex
        return [
            {
                "symbol_id": "sym:ParsableCommand",
                "symbol_name": "ParsableCommand",
                "symbol_kind": "protocol",
                "start_line": 1,
                "end_line": 4,
                "signature": f"protocol@{file_path}",
            }
        ]

    def _fake_resolve_same_target_reference(
        *,
        current_file: str,
        type_name: str,
        module_index: dict[str, str],
    ) -> str | None:
        del current_file, module_index
        calls.append(type_name)
        return "Sources/Acme/CommandConfiguration.swift"

    module_index = {
        "Sources/Acme/CommandConfiguration.swift": "Sources/Acme/CommandConfiguration.swift"
    }
    text = (
        "protocol ParsableCommand {\n"
        "  static var configuration: CommandConfiguration { get }\n"
        "  static var fallback: CommandConfiguration { get }\n"
        "}\n"
    )

    _symbols, dependencies, references = repository_service.swift_adapter.parse_file(
        "Sources/Acme/ParsableCommand.swift",
        text,
        module_index,
        collect_type_symbol_entries=_fake_collect_type_symbol_entries,
        stable_identifier=repository_service._stable_identifier,
        resolve_import=repository_service._resolve_swift_import,
        resolve_same_target_reference=_fake_resolve_same_target_reference,
    )

    assert calls == ["CommandConfiguration"]
    assert {dependency.target_file for dependency in dependencies} == {
        "Sources/Acme/CommandConfiguration.swift"
    }
    assert {reference.target_file for reference in references} == {
        "Sources/Acme/CommandConfiguration.swift"
    }


def test_repository_intelligence_csharp_helpers_are_modularized() -> None:
    assert repository_service._CSHARP_USING_RE is repository_service.csharp_adapter.USING_RE
    assert repository_service._CSHARP_NAMESPACE_RE is repository_service.csharp_adapter.NAMESPACE_RE
    assert repository_service._CSHARP_TYPE_DECL_RE is repository_service.csharp_adapter.TYPE_DECL_RE
    assert repository_service._CSHARP_TYPE_REFERENCE_RE is (
        repository_service.csharp_adapter.TYPE_REFERENCE_RE
    )


def test_repository_intelligence_csharp_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        import_target: str,
        module_index: dict[str, str],
        *,
        resolve_suffix_match: Any,
        resolve_directory_prefix_match: Any,
    ) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_suffix_match"] = resolve_suffix_match
        observed["resolve_directory_prefix_match"] = resolve_directory_prefix_match
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(repository_service.csharp_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_import("Acme.Widget", module_index)

    assert result == "src/Acme/Widget.cs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match
    assert observed["resolve_directory_prefix_match"] is (
        repository_service._resolve_directory_prefix_match
    )


def test_repository_intelligence_csharp_resolve_for_file_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import_for_file(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        resolve_import: Any,
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["resolve_import"] = resolve_import
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "resolve_import_for_file",
        _fake_resolve_import_for_file,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_import_for_file(
        current_file="src/Acme/App.cs",
        import_target="Acme.Widget",
        module_index=module_index,
    )

    assert result == "src/Acme/Widget.cs"
    assert observed["current_file"] == "src/Acme/App.cs"
    assert observed["import_target"] == "Acme.Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_import"] is repository_service._resolve_csharp_import
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_csharp_same_namespace_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_same_namespace_reference(
        *,
        current_file: str,
        current_namespace: str,
        type_name: str,
        module_index: dict[str, str],
        resolve_import: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["current_namespace"] = current_namespace
        observed["type_name"] = type_name
        observed["module_index"] = module_index
        observed["resolve_import"] = resolve_import
        return "src/Acme/Widget.cs"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "resolve_same_namespace_reference",
        _fake_resolve_same_namespace_reference,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._resolve_csharp_same_namespace_reference(
        current_file="src/Acme/App.cs",
        current_namespace="Acme",
        type_name="Widget",
        module_index=module_index,
    )

    assert result == "src/Acme/Widget.cs"
    assert observed["current_file"] == "src/Acme/App.cs"
    assert observed["current_namespace"] == "Acme"
    assert observed["type_name"] == "Widget"
    assert observed["module_index"] is module_index
    assert observed["resolve_import"] is repository_service._resolve_csharp_import


def test_repository_intelligence_csharp_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import_for_file: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any], str]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import_for_file"] = resolve_import_for_file
        return (), {}, "Acme"

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._extract_csharp_import_bindings(
        "src/Acme/App.cs",
        "using Acme.Widget;",
        module_index,
    )

    assert result == ((), {}, "Acme")
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "using Acme.Widget;"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import_for_file"] is repository_service._resolve_csharp_import_for_file


def test_repository_intelligence_csharp_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_same_namespace_reference: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_same_namespace_reference"] = resolve_same_namespace_reference
        return ()

    monkeypatch.setattr(
        repository_service.csharp_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._parse_csharp_dependencies_only(
        "src/Acme/App.cs",
        "using Acme.Widget;",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "using Acme.Widget;"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_csharp_import_bindings
    assert observed["resolve_same_namespace_reference"] is (
        repository_service._resolve_csharp_same_namespace_reference
    )


def test_repository_intelligence_csharp_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_same_namespace_reference: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_same_namespace_reference"] = resolve_same_namespace_reference
        return (), (), ()

    monkeypatch.setattr(repository_service.csharp_adapter, "parse_file", _fake_parse_file)

    module_index = {"src/Acme/Widget.cs": "src/Acme/Widget.cs"}

    result = repository_service._parse_csharp_file(
        "src/Acme/App.cs",
        "namespace Acme;",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/Acme/App.cs"
    assert observed["text"] == "namespace Acme;"
    assert observed["module_index"] is module_index
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_csharp_import_bindings
    assert observed["resolve_same_namespace_reference"] is (
        repository_service._resolve_csharp_same_namespace_reference
    )


def test_repository_intelligence_python_helpers_are_modularized() -> None:
    assert repository_service.python_adapter.ast_to_module_parts("src/app/main.py") == (
        "src",
        "app",
    )
    assert not hasattr(repository_service, "ast")


def test_repository_intelligence_python_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        module: str | None,
        level: int,
        name: str | None,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module"] = module
        observed["level"] = level
        observed["name"] = name
        observed["module_index"] = module_index
        return "src/app/helpers.py"

    monkeypatch.setattr(repository_service.python_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._resolve_python_import(
        current_file="src/app/api.py",
        module="app",
        level=0,
        name="helpers",
        module_index=module_index,
    )

    assert result == "src/app/helpers.py"
    assert observed["current_file"] == "src/app/api.py"
    assert observed["module"] == "app"
    assert observed["level"] == 0
    assert observed["name"] == "helpers"
    assert observed["module_index"] is module_index


def test_repository_intelligence_python_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.python_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._parse_python_dependencies_only(
        "src/app/api.py",
        "from app import helpers",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/app/api.py"
    assert observed["text"] == "from app import helpers"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_python_import


def test_repository_intelligence_python_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.python_adapter, "parse_file", _fake_parse_file)

    module_index = {"app.helpers": "src/app/helpers.py"}

    result = repository_service._parse_python_file(
        "src/app/api.py",
        "def handler():\n    return helpers.run()",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/app/api.py"
    assert observed["text"] == "def handler():\n    return helpers.run()"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_python_import


def test_repository_intelligence_rust_helpers_are_modularized() -> None:
    assert repository_service._RUST_USE_RE is repository_service.rust_adapter.USE_RE
    assert repository_service._RUST_MOD_RE is repository_service.rust_adapter.MOD_RE
    assert repository_service._RUST_SYMBOL_LINE_RE is repository_service.rust_adapter.SYMBOL_LINE_RE
    assert repository_service._RUST_CALL_RE is repository_service.rust_adapter.CALL_RE


def test_repository_intelligence_rust_resolve_module_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_module_path(
        *,
        current_file: str,
        module_path: str,
        module_index: dict[str, str],
    ) -> str | None:
        observed["current_file"] = current_file
        observed["module_path"] = module_path
        observed["module_index"] = module_index
        return "src/lib.rs"

    monkeypatch.setattr(
        repository_service.rust_adapter,
        "resolve_module_path",
        _fake_resolve_module_path,
    )

    module_index = {"crate": "src/lib.rs"}

    result = repository_service._resolve_rust_module_path(
        current_file="src/main.rs",
        module_path="crate::util",
        module_index=module_index,
    )

    assert result == "src/lib.rs"
    assert observed["current_file"] == "src/main.rs"
    assert observed["module_path"] == "crate::util"
    assert observed["module_index"] is module_index
