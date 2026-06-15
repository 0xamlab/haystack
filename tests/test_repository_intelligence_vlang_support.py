from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_adapters import (
    vlang_analysis_support as repository_vlang_analysis_support,
)
from apps.api_server.services.repository_intelligence_adapters import (
    vlang_primitives as repository_vlang_primitives,
)


def test_v_adapter_module_aliases_ignore_non_v_files(
    tmp_path: Path, monkeypatch
) -> None:
    repo_path = tmp_path / "mixed-repo"
    repo_path.mkdir()
    path_type = type(repo_path / "main.odin")

    def _fail_read_text(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("non-V files should not be parsed by the V adapter")

    monkeypatch.setattr(path_type, "read_text", _fail_read_text)

    aliases = repository_service.v_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="main.odin",
        stable_identifier=repository_service._stable_identifier,
    )

    assert aliases == set()


def test_v_adapter_module_aliases_include_v_module_and_symbol_names(tmp_path: Path) -> None:
    repo_path = tmp_path / "vlang-repo"
    (repo_path / "src").mkdir(parents=True)
    (repo_path / "src" / "main.v").write_text(
        "module sample\n\n"
        "fn greet() string {\n"
        "    return 'hi'\n"
        "}\n",
        encoding="utf-8",
    )

    aliases = repository_service.v_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.v",
        stable_identifier=repository_service._stable_identifier,
    )

    assert "src/main.v" in aliases
    assert "src/main" in aliases
    assert "src.main" in aliases
    assert "main" in aliases
    assert "sample" in aliases
    assert "greet" in aliases
    assert "sample.greet" in aliases


def test_v_adapter_module_aliases_use_provided_text_without_rereading_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "vlang-repo"
    source_path = repo_path / "src" / "main.v"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("module stale\n", encoding="utf-8")

    original_read_text = Path.read_text
    read_paths: list[str] = []

    def _tracking_read_text(self: Path, *args, **kwargs):
        if self == source_path:
            read_paths.append(str(self))
            if len(read_paths) > 1:
                raise AssertionError(
                    "module_aliases_for_path should reuse the provided V source text"
                )
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _tracking_read_text)

    source_text = "module sample\n\nfn greet() string {\n    return 'hi'\n}\n"
    aliases = repository_service.v_adapter.module_aliases_for_path(
        root_path=repo_path,
        file_path="src/main.v",
        stable_identifier=repository_service._stable_identifier,
        text=source_text,
        stripped_text=repository_vlang_primitives.strip_comments(source_text),
    )

    assert read_paths == []
    assert "sample" in aliases
    assert "sample.greet" in aliases


def test_v_adapter_detects_manifest_with_trailing_commas() -> None:
    manifest_text = (
        "Module {\n"
        "\tname: 'v2048',\n"
        "\tdescription: 'A simple 2048 game written in V.',\n"
        "\tversion: '0.0.2',\n"
        "\tdependencies: []\n"
        "}\n"
    )

    assert repository_service.v_adapter.is_probable_v_manifest(
        Path("v.mod"),
        manifest_text,
    )


def test_v_adapter_parse_file_reuses_stripped_text(monkeypatch) -> None:
    text = (
        "module sample\n\n"
        "import math\n\n"
        "fn greet() int {\n"
        "    return math.abs(-1)\n"
        "}\n"
    )
    strip_count = {"value": 0}
    original_strip_comments = repository_vlang_primitives.strip_comments

    def _counting_strip_comments(value: str) -> str:
        strip_count["value"] += 1
        return original_strip_comments(value)

    monkeypatch.setattr(repository_vlang_primitives, "strip_comments", _counting_strip_comments)
    monkeypatch.setattr(
        repository_vlang_analysis_support,
        "strip_comments",
        _counting_strip_comments,
        raising=False,
    )

    repository_vlang_analysis_support.parse_file(
        "src/main.v",
        text,
        {"math": "math.v", "math.v": "math.v"},
        stable_identifier=repository_service._stable_identifier,
        normalize_repository_relative_path=repository_service._normalize_repository_relative_path,
        resolve_suffix_match=repository_service._resolve_suffix_match,
    )

    assert strip_count["value"] == 1


def test_v_adapter_strip_comments_reuses_cached_results(monkeypatch) -> None:
    repository_vlang_primitives.clear_strip_comments_cache()
    source_text = (
        "module sample\n"
        "/* block comment */\n"
        "fn greet() {\n"
        "    // line comment\n"
        "}\n"
    )
    strip_count = {"value": 0}
    original_strip_comments_uncached = repository_vlang_primitives._strip_comments_uncached

    def _counting_strip_comments_uncached(value: str) -> str:
        strip_count["value"] += 1
        return original_strip_comments_uncached(value)

    monkeypatch.setattr(
        repository_vlang_primitives,
        "_strip_comments_uncached",
        _counting_strip_comments_uncached,
    )

    first_result = repository_vlang_primitives.strip_comments(source_text)
    first_cache_info = repository_vlang_primitives.strip_comments.cache_info()
    second_result = repository_vlang_primitives.strip_comments(source_text)
    second_cache_info = repository_vlang_primitives.strip_comments.cache_info()

    assert first_result == second_result
    assert strip_count["value"] == 1
    assert first_cache_info.misses == 1
    assert second_cache_info.hits >= 1
    assert second_cache_info.misses == 1


def test_v_adapter_probable_source_skips_comment_stripping_without_raw_v_markers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        repository_vlang_primitives,
        "strip_comments",
        lambda _text: (_ for _ in ()).throw(
            AssertionError("raw V marker fast path should skip comment stripping")
        ),
    )

    assert repository_vlang_primitives.is_probable_v_source(
        Path("theories/Main.v"),
        "Theorem id_demo : True.\nProof. exact I. Qed.\n",
    ) is False
