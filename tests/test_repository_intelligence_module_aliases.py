from __future__ import annotations

from pathlib import Path

import pytest

import apps.api_server.services.repository_intelligence_module_aliases as module_aliases


def test_root_scoped_module_alias_builders_for_file_falls_back_to_path_language(
    monkeypatch,
) -> None:
    builder = object()

    def fake_language_for_path(path: Path, *, text=None, repo_root=None) -> str:
        if text is not None:
            return "unknown"
        return "scratch"

    monkeypatch.setattr(module_aliases, "_language_for_path", fake_language_for_path)
    monkeypatch.setattr(
        module_aliases.repository_root_scoped_aliases,
        "root_scoped_module_alias_builders_for_language",
        lambda language: (builder,) if language == "scratch" else (),
    )
    monkeypatch.setattr(
        module_aliases,
        "_bind_preloaded_text_to_root_scoped_module_alias_builder",
        lambda candidate, *, text: candidate,
    )

    selected = module_aliases._root_scoped_module_alias_builders_for_file(
        root_path=Path("/tmp/repo"),
        file_path="game.sb3",
        text="not-json",
    )

    assert selected == (builder,)


def test_root_scoped_module_alias_builders_for_file_returns_empty_for_unknown_language(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        module_aliases,
        "_language_for_path",
        lambda path, *, text=None, repo_root=None: "unknown",
    )
    monkeypatch.setattr(
        module_aliases.repository_root_scoped_aliases,
        "root_scoped_module_alias_builders_for_language",
        lambda _language: (),
    )

    selected = module_aliases._root_scoped_module_alias_builders_for_file(
        root_path=Path("/tmp/repo"),
        file_path="opaque.bin",
        text="garbage",
    )

    assert selected == ()


def test_bind_preloaded_text_to_root_scoped_module_alias_builder_is_generic() -> None:
    seen_calls: list[tuple[str, str, str]] = []

    def builder(*, root_path: Path, file_path: str, text: str) -> set[str]:
        seen_calls.append((str(root_path), file_path, text))
        return {text}

    wrapped = module_aliases._bind_preloaded_text_to_root_scoped_module_alias_builder(
        builder,
        text="payload",
    )

    assert wrapped(root_path=Path("/tmp/repo"), file_path="main.txt") == {"payload"}
    assert seen_calls == [("/tmp/repo", "main.txt", "payload")]


@pytest.mark.parametrize(
    ("relative_path", "source_text", "expected_alias"),
    [
        ("src/main.m", "function y = main(x)\ny = x;\nend\n", "main"),
        ("theories/Main.v", "Module Main.\nEnd Main.\n", "Main"),
        ("src/main.v", "module sample\n\nfn greet() string {\n    return 'hi'\n}\n", "sample"),
    ],
)
def test_build_module_index_reuses_preloaded_text_for_text_capable_root_scoped_aliases(
    tmp_path: Path,
    monkeypatch,
    relative_path: str,
    source_text: str,
    expected_alias: str,
) -> None:
    repo_path = tmp_path / "module-alias-reuse-repo"
    source_path = repo_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text(source_text, encoding="utf-8")

    original_read_text = Path.read_text
    source_reads: list[str] = []

    def _tracking_read_text(self: Path, *args, **kwargs):
        if self == source_path:
            source_reads.append(str(self))
            if len(source_reads) > 1:
                raise AssertionError("expected root-scoped alias builder to reuse preloaded text")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _tracking_read_text)

    index = module_aliases._build_module_index(
        [relative_path],
        root_path=repo_path,
    )

    assert source_reads == [str(source_path)]
    assert index[expected_alias] == relative_path
