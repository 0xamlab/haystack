from __future__ import annotations

from pathlib import Path

from apps.api_server.services import repository_intelligence as repository_service
from benchmarks import repository_intelligence_real_repo_probe as probe_module
from benchmarks import (
    repository_intelligence_real_repo_probe_profile_path_classification_support as path_classification_support,
)


def test_language_for_path_supports_ranked_static_hints_without_text() -> None:
    expected_languages = {
        "src/view.ddls.asddls": "abapcds",
        "aidl/demo/IRemote.aidl": "aidl",
        "aiken.toml": "aiken",
        "lib/cardano/tx.ak": "aiken",
        "models/main.als": "alloy",
        "examples/showa.lp": "answer set programming",
        "apache2/httpd.conf": "apacheconf",
        "Pages/Default.aspx": "asp.net",
        "firmware/dsdt.asl": "asl",
        "impl/src/main/aspect/Trace.aj": "aspectj",
        "DATS/main.dats": "ats",
        "templates/index.ftlh": "freemarker",
        "src/ObjectModule.bsl": "1centerprise",
    }

    for relative_path, expected_language in expected_languages.items():
        assert repository_service._language_for_path(Path(relative_path)) == expected_language


def test_probe_language_for_path_detects_restored_ranked_languages(tmp_path: Path) -> None:
    repo_path = tmp_path / "ranked-language-probe-repo"
    repository_samples = {
        "src/view.ddls.asddls": (
            "define view entity Z_DEMO_ENTITY as select from Z_DEMO_SOURCE { key field_a as FieldA }\n",
            "abapcds",
        ),
        "aidl/demo/IRemote.aidl": (
            "package demo;\ninterface IRemote { void ping(); }\n",
            "aidl",
        ),
        "aiken.toml": (
            'name = "demo/project"\nversion = "0.0.1"\ncompiler = "v1.1.21"\n',
            "aiken",
        ),
        "lib/cardano/tx.ak": (
            "use aiken/math\npub fn spend(x: Int) -> Int { x }\n",
            "aiken",
        ),
        "models/main.als": (
            "module models/main\nsig Node {}\nrun {}\n",
            "alloy",
        ),
        "Scripts/Main.as": (
            "namespace Demo {\nvoid Start() {}\n}\n",
            "angelscript",
        ),
        "examples/showa.lp": (
            "{ q(X) : p(X) }.\na :- q(1).\n#show a/0.\n",
            "answer set programming",
        ),
        "apache2/apache2.conf": (
            "ServerName example.test\nIncludeOptional sites-enabled/*.conf\n",
            "apacheconf",
        ),
        "Pages/Default.aspx": (
            '<%@ Page Language="C#" Inherits="Demo.Pages.DefaultPage" %>\n',
            "asp.net",
        ),
        "firmware/dsdt.asl": (
            'DefinitionBlock ("", "DSDT", 2, "TEST", "MAIN", 0x00000000)\n'
            "{\n"
            "    Name (MODE, One)\n"
            "    Method (RUN, 0, NotSerialized)\n"
            "    {\n"
            "        Return (MODE)\n"
            "    }\n"
            "}\n",
            "asl",
        ),
        "impl/src/main/aspect/Trace.aj": (
            "public aspect TraceAspect { before(): execution(* *(..)) {} }\n",
            "aspectj",
        ),
        "DATS/main.dats": (
            '#include "share/atspre_staload.hats"\nimplement main0() = println!("Hello")\n',
            "ats",
        ),
        "schema/query.graphql": (
            "type Query {\n  viewer: User\n}\n",
            "graphql",
        ),
        "config/app.pkl": (
            'import "base.pkl"\nservice = new Service {}\n',
            "pkl",
        ),
        "templates/index.ftl": (
            '<#include "layout/base.ftl">\n${title!""}\n',
            "freemarker",
        ),
        "src/main.os": (
            "#Использовать helpers\nФункция Запустить() Экспорт\nКонецФункции\n",
            "1centerprise",
        ),
        "spec/main.wat": (
            '(module\n  (import "env" "log" (func $log))\n  (func $main call $log)\n)\n',
            "webassembly",
        ),
    }

    for relative_path, (text, _expected_language) in repository_samples.items():
        target_path = repo_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")

    for relative_path, (_text, expected_language) in repository_samples.items():
        assert probe_module._probe_language_for_path(relative_path, repo_path=repo_path) == (
            expected_language
        )


def test_probe_language_for_path_uses_direct_hints_without_repo_stat(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo_path = tmp_path / "direct-hint-probe-repo"
    sample_files = {
        "aidl/demo/IRemote.aidl": "package demo;\ninterface IRemote { void ping(); }\n",
        "cljs/src/app/core.cljs": "(ns app.core)\n(defn run [] :ok)\n",
        "logic/Main.L5X": (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<RSLogix5000Content>\n"
            '  <Controller Name="PlantController"></Controller>\n'
            "</RSLogix5000Content>\n"
        ),
        "racket/main.rkt": "#lang racket\n(define (run) 1)\n",
        "scheme/main.scm": (
            "(define-library (acme main)\n"
            "  (export run)\n"
            "  (begin\n"
            "    (define (run) 1)))\n"
        ),
        "src/Main.purs": "module Main where\n\nmain = unit\n",
    }
    for relative_path, text in sample_files.items():
        target_path = repo_path / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(text, encoding="utf-8")

    def _unexpected_repo_file_stat(repo_path: Path, normalized_path: str):
        raise AssertionError(f"direct-hint path should not stat {repo_path / normalized_path}")

    monkeypatch.setattr(
        path_classification_support,
        "_repo_file_stat",
        _unexpected_repo_file_stat,
    )
    original_read_text = Path.read_text

    def _unexpected_read_text(self: Path, *args, **kwargs):
        if self in {repo_path / relative_path for relative_path in sample_files}:
            raise AssertionError(f"direct-hint path should not read {self}")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _unexpected_read_text)

    assert probe_module._probe_language_for_path(
        "aidl/demo/IRemote.aidl",
        repo_path=repo_path,
    ) == "aidl"
    assert probe_module._probe_language_for_path(
        "cljs/src/app/core.cljs",
        repo_path=repo_path,
    ) == "clojurescript"
    assert probe_module._probe_language_for_path(
        "logic/Main.L5X",
        repo_path=repo_path,
    ) == "ladder"
    assert probe_module._probe_language_for_path(
        "racket/main.rkt",
        repo_path=repo_path,
    ) == "racket"
    assert probe_module._probe_language_for_path(
        "scheme/main.scm",
        repo_path=repo_path,
    ) == "scheme"
    assert probe_module._probe_language_for_path(
        "src/Main.purs",
        repo_path=repo_path,
    ) == "purescript"
