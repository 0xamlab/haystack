"""Tests for repository_intelligence_service: repository_intelligence_i.

Extracted from tests/test_repository_intelligence_service.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def test_repository_intelligence_c_family_candidate_keys_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_candidate_module_keys(
        base_path: str,
        *,
        normalize_repository_relative_path: Any,
    ) -> tuple[str, ...]:
        observed["base_path"] = base_path
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ("include/widget.hpp", "include/widget")

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "candidate_module_keys",
        _fake_candidate_module_keys,
    )

    result = repository_service._candidate_c_family_module_keys("include/widget.hpp")

    assert result == ("include/widget.hpp", "include/widget")
    assert observed["base_path"] == "include/widget.hpp"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_c_family_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "include/widget.hpp"

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "resolve_include",
        _fake_resolve_include,
    )

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._resolve_c_family_include(
        current_file="src/main.cpp",
        import_target="widget.hpp",
        module_index=module_index,
    )

    assert result == "include/widget.hpp"
    assert observed["current_file"] == "src/main.cpp"
    assert observed["import_target"] == "widget.hpp"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_c_family_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_include: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_include"] = resolve_include
        return ()

    monkeypatch.setattr(
        repository_service.c_family_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._parse_c_family_dependencies_only(
        "src/main.cpp",
        '#include "widget.hpp"\n',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.cpp"
    assert observed["text"] == '#include "widget.hpp"\n'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_include"] is repository_service._resolve_c_family_include


def test_repository_intelligence_c_family_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_include: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_include"] = resolve_include
        return (), (), ()

    monkeypatch.setattr(repository_service.c_family_adapter, "parse_file", _fake_parse_file)

    module_index = {"widget.hpp": "include/widget.hpp"}

    result = repository_service._parse_c_family_file(
        "src/main.cpp",
        "int run() { return helper(); }",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.cpp"
    assert observed["text"] == "int run() { return helper(); }"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_include"] is repository_service._resolve_c_family_include


def test_repository_intelligence_zig_helpers_are_modularized() -> None:
    assert repository_service._ZIG_IMPORT_RE is repository_service.zig_adapter.IMPORT_RE
    assert repository_service._ZIG_IMPORT_BINDING_RE is (
        repository_service.zig_adapter.IMPORT_BINDING_RE
    )
    assert repository_service._ZIG_TOP_LEVEL_CONST_RE is (
        repository_service.zig_adapter.TOP_LEVEL_CONST_RE
    )
    assert repository_service._ZIG_TOP_LEVEL_FUNCTION_RE is (
        repository_service.zig_adapter.TOP_LEVEL_FUNCTION_RE
    )
    assert repository_service._ZIG_SELECTOR_REFERENCE_RE is (
        repository_service.zig_adapter.SELECTOR_REFERENCE_RE
    )


def test_repository_intelligence_zig_candidate_keys_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_candidate_module_keys(
        current_file: str,
        import_target: str,
        *,
        normalize_repository_relative_path: Any,
    ) -> tuple[str, ...]:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return ("src/root.zig",)

    monkeypatch.setattr(
        repository_service.zig_adapter,
        "candidate_module_keys",
        _fake_candidate_module_keys,
    )

    result = repository_service._candidate_zig_module_keys("src/main.zig", "root")

    assert result == ("src/root.zig",)
    assert observed["current_file"] == "src/main.zig"
    assert observed["import_target"] == "root"
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_zig_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        return "src/root.zig"

    monkeypatch.setattr(repository_service.zig_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"root": "src/root.zig"}

    result = repository_service._resolve_zig_import(
        current_file="src/main.zig",
        import_target="root",
        module_index=module_index,
    )

    assert result == "src/root.zig"
    assert observed["current_file"] == "src/main.zig"
    assert observed["import_target"] == "root"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )


def test_repository_intelligence_zig_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.zig_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"root": "src/root.zig"}

    result = repository_service._extract_zig_import_bindings(
        "src/main.zig",
        'const root = @import("root");',
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == 'const root = @import("root");'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_zig_dependency_wrapper_delegates(
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
        repository_service.zig_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"root": "src/root.zig"}

    result = repository_service._parse_zig_dependencies_only(
        "src/main.zig",
        'const root = @import("root");',
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == 'const root = @import("root");'
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_zig_parse_wrapper_delegates(
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

    monkeypatch.setattr(repository_service.zig_adapter, "parse_file", _fake_parse_file)

    module_index = {"root": "src/root.zig"}

    result = repository_service._parse_zig_file(
        "src/main.zig",
        "pub fn main() void {}",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main.zig"
    assert observed["text"] == "pub fn main() void {}"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_zig_import


def test_repository_intelligence_mojo_helpers_are_modularized() -> None:
    assert repository_service._MOJO_IMPORT_RE is repository_service.mojo_adapter.IMPORT_RE
    assert repository_service._MOJO_FROM_IMPORT_RE is (
        repository_service.mojo_adapter.FROM_IMPORT_RE
    )
    assert repository_service._MOJO_SYMBOL_RE is repository_service.mojo_adapter.SYMBOL_RE
    assert repository_service._MOJO_SELECTOR_CALL_RE is (
        repository_service.mojo_adapter.SELECTOR_CALL_RE
    )
    assert repository_service._MOJO_CALL_RE is repository_service.mojo_adapter.CALL_RE


def test_repository_intelligence_mojo_resolve_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_import(import_target: str, module_index: dict[str, str]) -> str | None:
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        return "helper/util.mojo"

    monkeypatch.setattr(repository_service.mojo_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._resolve_mojo_import("helper.util", module_index)

    assert result == "helper/util.mojo"
    assert observed["import_target"] == "helper.util"
    assert observed["module_index"] is module_index


def test_repository_intelligence_mojo_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}

    monkeypatch.setattr(
        repository_service.mojo_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._extract_mojo_import_bindings(
        "main.mojo",
        "from helper.util import value",
        module_index,
    )

    assert result == ((), {})
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "from helper.util import value"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_mojo_dependency_wrapper_delegates(
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
        repository_service.mojo_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._parse_mojo_dependencies_only(
        "main.mojo",
        "from helper.util import value",
        module_index,
    )

    assert result == ()
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "from helper.util import value"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_mojo_parse_wrapper_delegates(
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

    monkeypatch.setattr(repository_service.mojo_adapter, "parse_file", _fake_parse_file)

    module_index = {"helper.util": "helper/util.mojo"}

    result = repository_service._parse_mojo_file(
        "main.mojo",
        "fn run():\n    value()",
        module_index,
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "main.mojo"
    assert observed["text"] == "fn run():\n    value()"
    assert observed["module_index"] is module_index
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_mojo_import


def test_repository_intelligence_jvm_helpers_are_modularized() -> None:
    assert repository_service._JVM_PACKAGE_RE is repository_service.jvm_adapter.PACKAGE_RE
    assert repository_service._JVM_IMPORT_RE is repository_service.jvm_adapter.IMPORT_RE
    assert repository_service._JVM_TYPE_DECL_RE is repository_service.jvm_adapter.TYPE_DECL_RE
    assert repository_service._JVM_TYPE_REFERENCE_RE is (
        repository_service.jvm_adapter.TYPE_REFERENCE_RE
    )
    assert repository_service._SCALA_PACKAGE_OBJECT_RE is (
        repository_service.jvm_adapter.SCALA_PACKAGE_OBJECT_RE
    )
    assert repository_service._SCALA_PACKAGE_RE is repository_service.jvm_adapter.SCALA_PACKAGE_RE
    assert repository_service._SCALA_IMPORT_RE is repository_service.jvm_adapter.SCALA_IMPORT_RE
    assert repository_service._SCALA_GROUPED_IMPORT_RE is (
        repository_service.jvm_adapter.SCALA_GROUPED_IMPORT_RE
    )
    assert repository_service._SCALA_TYPE_DECL_RE is (
        repository_service.jvm_adapter.SCALA_TYPE_DECL_RE
    )
    assert repository_service._scala_current_package is (
        repository_service.jvm_adapter.scala_current_package
    )
    assert repository_service._iter_scala_import_targets is (
        repository_service.jvm_adapter.iter_scala_import_targets
    )
    assert repository_service._scala_package_aliases_for_path is (
        repository_service.jvm_adapter.scala_package_aliases_for_path
    )
    assert repository_service._jvm_declared_type_aliases_for_path is (
        repository_service.jvm_adapter.declared_type_aliases_for_path
    )


def test_repository_intelligence_jvm_resolve_wrapper_delegates(
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
        return "src/main/java/org/example/Owner.java"

    monkeypatch.setattr(repository_service.jvm_adapter, "resolve_import", _fake_resolve_import)

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._resolve_jvm_import("org.example.Owner", module_index)

    assert result == "src/main/java/org/example/Owner.java"
    assert observed["import_target"] == "org.example.Owner"
    assert observed["module_index"] is module_index
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


def test_repository_intelligence_jvm_extract_import_bindings_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_extract_import_bindings(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        stable_identifier: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], dict[str, Any], str]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["stable_identifier"] = stable_identifier
        observed["resolve_import"] = resolve_import
        return (), {}, "org.example"

    monkeypatch.setattr(
        repository_service.jvm_adapter,
        "extract_import_bindings",
        _fake_extract_import_bindings,
    )

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._extract_jvm_import_bindings(
        "src/main/java/org/example/OwnerController.java",
        "import org.example.Owner;",
        module_index,
        language="java",
    )

    assert result == ((), {}, "org.example")
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "import org.example.Owner;"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_jvm_dependency_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_dependencies_only(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_import: Any,
    ) -> tuple[Any, ...]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_import"] = resolve_import
        return ()

    monkeypatch.setattr(
        repository_service.jvm_adapter,
        "parse_dependencies_only",
        _fake_parse_dependencies_only,
    )

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._parse_jvm_dependencies_only(
        "src/main/java/org/example/OwnerController.java",
        "import org.example.Owner;",
        module_index,
        language="java",
    )

    assert result == ()
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "import org.example.Owner;"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_jvm_import_bindings
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_jvm_parse_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_parse_file(
        file_path: str,
        text: str,
        module_index: dict[str, str],
        *,
        language: str,
        collect_type_symbol_entries: Any,
        stable_identifier: Any,
        extract_import_bindings: Any,
        resolve_import: Any,
    ) -> tuple[tuple[Any, ...], tuple[Any, ...], tuple[Any, ...]]:
        observed["file_path"] = file_path
        observed["text"] = text
        observed["module_index"] = module_index
        observed["language"] = language
        observed["collect_type_symbol_entries"] = collect_type_symbol_entries
        observed["stable_identifier"] = stable_identifier
        observed["extract_import_bindings"] = extract_import_bindings
        observed["resolve_import"] = resolve_import
        return (), (), ()

    monkeypatch.setattr(repository_service.jvm_adapter, "parse_file", _fake_parse_file)

    module_index = {"org.example.Owner": "src/main/java/org/example/Owner.java"}

    result = repository_service._parse_jvm_file(
        "src/main/java/org/example/OwnerController.java",
        "class OwnerController {}",
        module_index,
        language="java",
    )

    assert result == ((), (), ())
    assert observed["file_path"] == "src/main/java/org/example/OwnerController.java"
    assert observed["text"] == "class OwnerController {}"
    assert observed["module_index"] is module_index
    assert observed["language"] == "java"
    assert observed["collect_type_symbol_entries"] is repository_service._collect_type_symbol_entries
    assert observed["stable_identifier"] is repository_service._stable_identifier
    assert observed["extract_import_bindings"] is repository_service._extract_jvm_import_bindings
    assert observed["resolve_import"] is repository_service._resolve_jvm_import


def test_repository_intelligence_julia_helpers_are_modularized() -> None:
    assert repository_service._JULIA_INCLUDE_RE is repository_service.julia_adapter.INCLUDE_RE
    assert repository_service._julia_project_name_from_text is (
        repository_service.julia_adapter.project_name_from_text
    )
    assert repository_service._is_julia_operational_reference_name is (
        repository_service.julia_adapter.is_operational_reference_name
    )


def test_repository_intelligence_julia_resolve_include_wrapper_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def _fake_resolve_include(
        *,
        current_file: str,
        import_target: str,
        module_index: dict[str, str],
        normalize_repository_relative_path: Any,
        resolve_suffix_match: Any,
    ) -> str | None:
        observed["current_file"] = current_file
        observed["import_target"] = import_target
        observed["module_index"] = module_index
        observed["normalize_repository_relative_path"] = normalize_repository_relative_path
        observed["resolve_suffix_match"] = resolve_suffix_match
        return "src/Helper.jl"

    monkeypatch.setattr(repository_service.julia_adapter, "resolve_include", _fake_resolve_include)

    module_index = {"src/Helper.jl": "src/Helper.jl"}

    result = repository_service._resolve_julia_include(
        current_file="src/Acme.jl",
        import_target="Helper.jl",
        module_index=module_index,
    )

    assert result == "src/Helper.jl"
    assert observed["current_file"] == "src/Acme.jl"
    assert observed["import_target"] == "Helper.jl"
    assert observed["module_index"] is module_index
    assert observed["normalize_repository_relative_path"] is (
        repository_service._normalize_repository_relative_path
    )
    assert observed["resolve_suffix_match"] is repository_service._resolve_suffix_match


