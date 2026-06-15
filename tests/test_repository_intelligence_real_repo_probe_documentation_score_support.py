from __future__ import annotations

from collections import Counter
from pathlib import Path

from benchmarks.repository_intelligence_real_repo_probe_documentation_score_support import (
    apply_documentation_host_ecosystem_scores,
    documentation_ecosystems_suppressed_in_finalize,
    documentation_host_ecosystem_counts,
)


def test_documentation_score_prefers_docs_when_docs_dominate() -> None:
    scores = Counter({"rst": 40, "python": 20})

    apply_documentation_host_ecosystem_scores(
        scores,
        documentation_ecosystem="rst",
        ecosystem_counts=Counter({"rst": 5, "python": 2}),
        host_ecosystems=("python",),
    )

    assert scores["rst"] == 136
    assert scores["python"] == 20


def test_documentation_score_yields_when_operational_host_matches_docs() -> None:
    scores = Counter({"rst": 74, "robotframework": 52})

    apply_documentation_host_ecosystem_scores(
        scores,
        documentation_ecosystem="rst",
        ecosystem_counts=Counter({"rst": 2, "robotframework": 2, "python": 1}),
        host_ecosystems=("python", "robotframework"),
    )

    assert scores["robotframework"] == 92
    assert scores["rst"] == 26


def test_documentation_host_ecosystem_counts_include_non_documentation_hosts(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "documentation-host-counts-repo"
    (repo_path / "course").mkdir(parents=True)
    (repo_path / "labs" / "cbl").mkdir(parents=True)
    (repo_path / "course" / "Front_Matter.tex").write_text(
        "\\chapter{Intro}\n",
        encoding="utf-8",
    )
    (repo_path / "labs" / "cbl" / "HELLO.cbl").write_text(
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. HELLO.\n"
        "       PROCEDURE DIVISION.\n"
        "           GOBACK.\n",
        encoding="utf-8",
    )

    counts = documentation_host_ecosystem_counts(
        ["course/Front_Matter.tex", "labs/cbl/HELLO.cbl"],
        repo_path=repo_path,
        documentation_ecosystem="tex",
    )

    assert counts["tex"] == 1
    assert counts["cobol"] == 1


def test_documentation_host_ecosystem_counts_skip_non_operational_host_paths(
    tmp_path: Path,
) -> None:
    repo_path = tmp_path / "documentation-host-non-operational-repo"
    (repo_path / "examples").mkdir(parents=True)
    (repo_path / "examples" / "paper.tex").write_text(
        "\\documentclass{article}\n\\begin{document}Hi\\end{document}\n",
        encoding="utf-8",
    )
    (repo_path / "examples" / "helper.py").write_text(
        "def helper() -> None:\n    return None\n",
        encoding="utf-8",
    )
    (repo_path / "Makefile").write_text("pdf:\n\tlatexmk -pdf examples/paper.tex\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# Example\n", encoding="utf-8")

    counts = documentation_host_ecosystem_counts(
        [
            "examples/paper.tex",
            "examples/helper.py",
            "Makefile",
            "README.md",
        ],
        repo_path=repo_path,
        documentation_ecosystem="tex",
    )

    assert counts["tex"] == 1
    assert counts["makefile"] == 1
    assert counts["python"] == 0


def test_documentation_ecosystems_suppressed_in_finalize_when_host_already_leads() -> None:
    suppressed = documentation_ecosystems_suppressed_in_finalize(
        {"tex", "cobol"},
        ecosystem_scores=Counter({"cobol": 56, "tex": 44}),
    )

    assert suppressed == {"tex"}
