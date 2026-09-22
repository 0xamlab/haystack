"""apps/spaces/tools/stage.py — staging a Space with the vendored shared package."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
import stage
from manifest import Manifest, load_manifest, parse_manifest

GIT_SHA = "0123456789abcdef0123456789abcdef01234567"


def _fake_fleet(root: Path) -> Manifest:
    """A miniature apps/spaces tree: one live Space, one redirect, one shared package."""
    (root / "_shared" / "algenta_spaces").mkdir(parents=True)
    (root / "_shared" / "algenta_spaces" / "__init__.py").write_text(
        '"""shared"""\n', encoding="utf-8"
    )
    (root / "_shared" / "algenta_spaces" / "shell.py").write_text("CANON = 'x'\n", encoding="utf-8")
    (root / "_shared" / "algenta_spaces" / "__pycache__").mkdir()
    (root / "_shared" / "algenta_spaces" / "__pycache__" / "shell.cpython-314.pyc").write_bytes(
        b"\0"
    )
    live = root / "live"
    (live / "arena").mkdir(parents=True)
    (live / "tests").mkdir()
    (live / "app.py").write_text("import gradio\n", encoding="utf-8")
    (live / "README.md").write_text("---\ntitle: X\n---\n", encoding="utf-8")
    (live / "Dockerfile").write_text("FROM python:3.14-slim\n", encoding="utf-8")
    (live / "arena" / "duels.py").write_text("DUELS = []\n", encoding="utf-8")
    (live / "arena" / "leaderboard.json").write_text("[]", encoding="utf-8")
    (live / "tests" / "test_app.py").write_text("def test(): pass\n", encoding="utf-8")
    (live / "kernel.so").write_bytes(b"\x7fELF")
    (live / "wheel-0.1-py3-none-any.whl").write_bytes(b"PK")
    (live / "app.pyc").write_bytes(b"\0")
    redirect = root / "_redirects" / "old"
    redirect.mkdir(parents=True)
    (redirect / "index.html").write_text("<meta http-equiv='refresh'>", encoding="utf-8")
    (redirect / "README.md").write_text("---\nsdk: static\n---\n", encoding="utf-8")
    raw = {
        "fleet": {"org": "thyn-ai", "shared_package": "_shared/algenta_spaces", "budget_usd": 10},
        "spaces": {
            "live": {
                "repo_id": "thyn-ai/live",
                "sdk": "docker",
                "source": "live",
                "python": "3.14",
                "hardware": "cpu-upgrade",
                "sleep_time": -1,
                "verify": "verify_remote:check_algenta",
                "api_names": ["run"],
                "shared_shell": False,
            },
            "old": {
                "repo_id": "thyn-ai/old",
                "sdk": "static",
                "source": "_redirects/old",
                "redirect_to": "https://huggingface.co/spaces/thyn-ai/live",
                "verify": "verify_remote:check_redirect",
            },
        },
    }
    return parse_manifest(raw, root / "spaces.toml")


def test_stage_live_space_tree_and_stamps(tmp_path: Path) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    out = tmp_path / "out"
    result = stage.stage_space("live", out, manifest=mf, git_sha=GIT_SHA)

    assert result.staged_dir == out
    assert result.files == (
        ".git_sha",
        ".shared_sha",
        "Dockerfile",
        "README.md",
        "algenta_spaces/__init__.py",
        "algenta_spaces/shell.py",
        "app.py",
        "arena/duels.py",
    )
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == sorted(
        result.files
    )
    assert (out / ".git_sha").read_text(encoding="utf-8") == GIT_SHA + "\n"
    assert result.git_sha == GIT_SHA
    # the shared sha is reproducible from the shared package alone, in sorted order
    expected = hashlib.sha256()
    for rel in ("__init__.py", "shell.py"):
        expected.update(rel.encode() + b"\0")
        expected.update(
            (tmp_path / "apps" / "_shared" / "algenta_spaces" / rel).read_bytes() + b"\0"
        )
    assert result.shared_sha == expected.hexdigest()
    assert (out / ".shared_sha").read_text(encoding="utf-8").strip() == result.shared_sha
    # ignored things never leave the checkout
    for gone in (
        "tests",
        "kernel.so",
        "wheel-0.1-py3-none-any.whl",
        "app.pyc",
        "arena/leaderboard.json",
    ):
        assert not (out / gone).exists(), gone
    assert not (out / "algenta_spaces" / "__pycache__").exists()


def test_shared_sha_changes_when_the_shared_package_changes(tmp_path: Path) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    first = stage.stage_space("live", tmp_path / "a", manifest=mf, git_sha=GIT_SHA)
    (tmp_path / "apps" / "_shared" / "algenta_spaces" / "shell.py").write_text(
        "CANON = 'y'\n", encoding="utf-8"
    )
    second = stage.stage_space("live", tmp_path / "b", manifest=mf, git_sha=GIT_SHA)
    assert first.shared_sha != second.shared_sha
    assert first.files == second.files


def test_stage_redirect_has_no_shared_package(tmp_path: Path) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    result = stage.stage_space("old", tmp_path / "out", manifest=mf, git_sha=GIT_SHA)
    assert result.shared_sha is None
    assert result.files == (".git_sha", "README.md", "index.html")
    assert not (tmp_path / "out" / ".shared_sha").exists()


def test_refuses_files_over_500_kb_before_writing(tmp_path: Path) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    (tmp_path / "apps" / "live" / "social.png").write_bytes(b"\0" * (stage.MAX_FILE_BYTES + 1))
    out = tmp_path / "out"
    with pytest.raises(stage.StageError, match="over 500 KB refused: social.png"):
        stage.stage_space("live", out, manifest=mf, git_sha=GIT_SHA)
    assert not out.exists()


def test_refuses_non_empty_out_dir_and_missing_sources(tmp_path: Path) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale").write_text("x", encoding="utf-8")
    with pytest.raises(stage.StageError, match="must be empty"):
        stage.stage_space("live", out, manifest=mf, git_sha=GIT_SHA)
    (tmp_path / "apps" / "live" / "algenta_spaces").mkdir()
    with pytest.raises(stage.StageError, match="already holds algenta_spaces"):
        stage.stage_space("live", tmp_path / "out2", manifest=mf, git_sha=GIT_SHA)
    (tmp_path / "apps" / "live" / "algenta_spaces").rmdir()
    for f in (tmp_path / "apps" / "_shared" / "algenta_spaces").iterdir():
        if f.is_file():
            f.unlink()
    with pytest.raises(stage.StageError, match="shared package is empty"):
        stage.stage_space("live", tmp_path / "out3", manifest=mf, git_sha=GIT_SHA)
    with pytest.raises(stage.StageError, match="source directory missing"):
        stage.iter_files(tmp_path / "nowhere")


def test_is_ignored_matrix() -> None:
    assert stage.is_ignored(Path("__pycache__/x.pyc"))
    assert stage.is_ignored(Path("arena/__pycache__/x.py"))
    assert stage.is_ignored(Path("tests/test_x.py"))
    assert stage.is_ignored(Path("arena/tests/test_x.py"))
    assert stage.is_ignored(Path("leaderboard.json"))
    assert stage.is_ignored(Path("libfoo.so"))
    assert stage.is_ignored(Path("a-1.0-py3-none-any.whl"))
    assert not stage.is_ignored(Path("tests.py"))
    assert not stage.is_ignored(Path("arena/store.py"))
    assert not stage.is_ignored(Path("social.png"))


def test_git_head_reads_a_real_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "f").write_text("1", encoding="utf-8")
    subprocess.run(["git", "add", "f"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "one"],
        cwd=repo,
        check=True,
        env={**env, "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    sha = stage.git_head(repo)
    assert len(sha) == 40 and int(sha, 16) >= 0
    with pytest.raises(stage.StageError, match="git rev-parse HEAD failed"):
        stage.git_head(tmp_path / "not-a-repo")


def test_read_stamp(tmp_path: Path) -> None:
    (tmp_path / ".git_sha").write_text(GIT_SHA + "\n", encoding="utf-8")
    assert stage.read_stamp(tmp_path, ".git_sha") == GIT_SHA
    assert stage.read_stamp(tmp_path, ".shared_sha") is None


def test_cli_lists_files_and_reports_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mf = _fake_fleet(tmp_path / "apps")
    mf.path.write_text("", encoding="utf-8")  # main() re-reads a real file below
    import tomllib  # noqa: F401 - manifest.load_manifest uses tomllib; keep the CLI path real

    (tmp_path / "apps" / "spaces.toml").write_text(
        "\n".join(
            [
                "[fleet]",
                'org = "thyn-ai"',
                'shared_package = "_shared/algenta_spaces"',
                "budget_usd = 10",
                "[spaces.old]",
                'repo_id = "thyn-ai/old"',
                'sdk = "static"',
                'source = "_redirects/old"',
                'redirect_to = "https://huggingface.co/spaces/thyn-ai/live"',
                'verify = "verify_remote:check_redirect"',
            ]
        ),
        encoding="utf-8",
    )
    # main() falls back to `git rev-parse HEAD` in the manifest's directory: give it a repo
    subprocess.run(["git", "init", "-q"], cwd=tmp_path / "apps", check=True)
    (tmp_path / "apps" / "seed").write_text("1", encoding="utf-8")
    subprocess.run(["git", "add", "seed"], cwd=tmp_path / "apps", check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@x",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "seed",
        ],
        cwd=tmp_path / "apps",
        check=True,
    )
    rc = stage.main(
        [
            "--space",
            "old",
            "--out",
            str(tmp_path / "out"),
            "--manifest",
            str(tmp_path / "apps" / "spaces.toml"),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "index.html" in out and "git_sha " in out and "shared_sha" not in out
    rc = stage.main(
        [
            "--space",
            "old",
            "--out",
            str(tmp_path / "out"),
            "--manifest",
            str(tmp_path / "apps" / "spaces.toml"),
        ]
    )
    assert rc == 1
    assert "must be empty" in capsys.readouterr().out


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[2] / "apps/spaces/_shared/algenta_spaces").is_dir(),
    reason="shared package not present in this checkout",
)
def test_real_tree_stages_every_live_space(tmp_path: Path) -> None:
    mf = load_manifest()
    for space in mf.live:
        result = stage.stage_space(space.name, tmp_path / space.name, manifest=mf, git_sha=GIT_SHA)
        assert "app.py" in result.files, space.name
        assert "algenta_spaces/shell.py" in result.files, space.name
        assert result.shared_sha and len(result.shared_sha) == 64
        assert not any(
            f.endswith((".whl", ".so", ".pyc")) or f.startswith("tests/") for f in result.files
        )
    shas = {stage.read_stamp(tmp_path / s.name, ".shared_sha") for s in mf.live}
    assert len(shas) == 1, "every live Space vendors the same shared package"
