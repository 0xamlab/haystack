from __future__ import annotations

from pathlib import Path

import pytest

from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.services import (
    repository_intelligence_mojo_repo_classifier as mojo_repo_classifier,
)
from benchmarks import (
    repository_intelligence_real_repo_probe_seed_plan_support as seed_plan_support,
)


def test_repository_mojo_repo_classifier_catalog_derives_ranked_language_metadata() -> None:
    catalog = mojo_repo_classifier.build_repository_mojo_repo_classifier_language_catalog()
    catalog_by_language = {entry.language: entry for entry in catalog}

    assert "python" in catalog_by_language
    assert ".py" in catalog_by_language["python"].suffixes
    assert "python" in catalog_by_language["python"].tokens

    assert "shell" in catalog_by_language
    assert ".bashrc" in catalog_by_language["shell"].basenames

    assert "qsharp" in catalog_by_language
    assert (
        ".qs" in catalog_by_language["qsharp"].suffixes
        or "qsharp.json" in catalog_by_language["qsharp"].basenames
    )
    assert "css" in catalog_by_language
    assert ".css" in catalog_by_language["css"].suffixes
    assert "markdown" in catalog_by_language
    assert ".md" in catalog_by_language["markdown"].suffixes
    assert "unknown" not in catalog_by_language


def test_classify_repository_paths_with_mojo_batches_file_hints(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")

    monkeypatch.setattr(
        mojo_repo_classifier,
        "build_repository_mojo_repo_classifier_language_catalog",
        lambda: (
            mojo_repo_classifier.RepositoryMojoRepoClassifierLanguage(
                language="python",
                rank=0,
                aliases=("python",),
                route_families=("python_language",),
                suffixes=(".py",),
                basenames=(),
                tokens=("python", "py", "def"),
            ),
            mojo_repo_classifier.RepositoryMojoRepoClassifierLanguage(
                language="dockerfile",
                rank=1,
                aliases=("dockerfile",),
                route_families=("dockerfile",),
                suffixes=(".dockerfile",),
                basenames=("dockerfile",),
                tokens=("dockerfile", "from"),
            ),
        ),
    )

    seen_payloads: list[dict[str, object]] = []

    def fake_invoke_engine_sync(payload: dict[str, object], *, timeout: float | None = None) -> dict[str, object]:
        seen_payloads.append(payload)
        assert payload["engine_type"] == "repo_classifier"
        assert timeout == 11.0
        files = payload["files"]
        assert isinstance(files, list)
        assert len(files) == 1
        only_file = files[0]
        assert isinstance(only_file, dict)
        assert only_file["content_tokens"]
        if only_file["path"] == "src/main.py":
            return {
                "engine": "mojo",
                "engine_type": "repo_classifier",
                "results": [
                    {
                        "path": "src/main.py",
                        "primary_language": "python",
                        "primary_score": 28.0,
                        "matches": [
                            {
                                "language": "python",
                                "score": 28.0,
                                "suffix_match": True,
                                "basename_match": False,
                                "path_token_hits": 1,
                                "content_token_hits": 2,
                            }
                        ],
                    }
                ],
            }
        return {
            "engine": "mojo",
            "engine_type": "repo_classifier",
            "results": [
                {
                    "path": "Dockerfile",
                    "primary_language": "dockerfile",
                    "primary_score": 22.0,
                    "matches": [
                        {
                            "language": "dockerfile",
                            "score": 22.0,
                            "suffix_match": False,
                            "basename_match": True,
                            "path_token_hits": 1,
                            "content_token_hits": 1,
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(mojo_repo_classifier, "invoke_engine_sync", fake_invoke_engine_sync)

    results = mojo_repo_classifier.classify_repository_paths_with_mojo(
        ["src/main.py", "Dockerfile"],
        repo_path=tmp_path,
        batch_size=1,
        timeout=11.0,
    )

    assert len(seen_payloads) == 2
    assert results["src/main.py"].primary_language == "python"
    assert results["Dockerfile"].primary_language == "dockerfile"


def test_classify_repository_paths_with_mojo_propagates_mojo_failure(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")

    monkeypatch.setattr(
        mojo_repo_classifier,
        "invoke_engine_sync",
        lambda payload, *, timeout=None: (_ for _ in ()).throw(
            MojoEngineError(
                "repo_classifier failed",
                code="engine_failed",
                engine_type="repo_classifier",
                stage="subprocess_exec",
            )
        ),
    )

    with pytest.raises(MojoEngineError, match="repo_classifier failed"):
        mojo_repo_classifier.classify_repository_paths_with_mojo(
            ["src/main.py"],
            repo_path=tmp_path,
        )


def test_candidate_ecosystem_counts_uses_mojo_classifier_without_per_file_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    seed_plan_support.clear_candidate_ecosystem_count_cache()
    monkeypatch.setattr(
        seed_plan_support,
        "candidate_ecosystems_for_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("per-file fallback should not run")
        ),
    )
    monkeypatch.setattr(
        seed_plan_support,
        "classify_repository_paths_with_mojo",
        lambda candidate_file_paths, *, repo_path: {
            "src/app.ts": mojo_repo_classifier.RepositoryMojoRepoClassifierResult(
                path="src/app.ts",
                primary_language="javascript",
                primary_score=21.0,
                matches=(),
            ),
            "src/view.tsx": mojo_repo_classifier.RepositoryMojoRepoClassifierResult(
                path="src/view.tsx",
                primary_language="typescript",
                primary_score=23.0,
                matches=(),
            ),
            "src/tool.cs": mojo_repo_classifier.RepositoryMojoRepoClassifierResult(
                path="src/tool.cs",
                primary_language="cs",
                primary_score=25.0,
                matches=(),
            ),
        },
    )

    counts = seed_plan_support.candidate_ecosystem_counts(
        ["src/app.ts", "src/view.tsx", "src/tool.cs"],
        repo_path=tmp_path,
        ecosystems={"node", "dotnet", "python"},
    )

    assert counts["node"] == 2
    assert counts["dotnet"] == 1
    assert "python" not in counts
