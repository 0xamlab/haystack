"""apps/spaces/tools/manifest.py — the fleet manifest loader and its validation."""

from __future__ import annotations

import copy
import re
import tomllib
from pathlib import Path

import manifest as m
import pytest

MINIMAL = {
    "fleet": {"org": "thyn-ai", "shared_package": "_shared/algenta_spaces", "budget_usd": 650},
    "spaces": {
        "algenta": {
            "repo_id": "thyn-ai/algenta",
            "sdk": "docker",
            "source": "algenta",
            "python": "3.14",
            "hardware": "cpu-upgrade",
            "sleep_time": -1,
            "shared_shell": False,
            "secrets": ["ALGENTA_API_KEY", "HF_TOKEN"],
            "variables": {"ALGENTA_BASE_URL": "https://api.algenta.ai"},
            "verify": "verify_remote:check_algenta",
            "api_names": ["run_duel"],
        },
        "llm-modules": {
            "repo_id": "thyn-ai/algenta-llm-modules",
            "sdk": "static",
            "source": "_redirects/llm-modules",
            "redirect_to": "https://huggingface.co/spaces/thyn-ai/algenta",
            "verify": "verify_remote:check_redirect",
        },
    },
}


def _parse(raw: dict) -> m.Manifest:
    return m.parse_manifest(raw, Path("/x/apps/spaces/spaces.toml"))


def _with(path: tuple[str, ...], value: object) -> dict:
    raw = copy.deepcopy(MINIMAL)
    node = raw
    for key in path[:-1]:
        node = node[key]
    if value is m.ManifestError:  # sentinel: delete the key
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return raw


def test_real_manifest_loads_and_matches_the_plan(apps_spaces_dir: Path) -> None:
    mf = m.load_manifest()
    assert mf.path == (apps_spaces_dir / "spaces.toml").resolve()
    assert mf.fleet.org == "thyn-ai"
    assert mf.fleet.budget_usd == 650
    assert mf.shared_package_dir == apps_spaces_dir / "_shared" / "algenta_spaces"
    assert [s.name for s in mf.live] == ["algenta", "speed-arena", "governed-agent"]
    assert [s.name for s in mf.redirects] == [
        "for-llm-agents",
        "governed-tool-calls",
        "llm-modules",
    ]
    hardware = {s.name: s.hardware for s in mf.live}
    assert hardware == {
        "algenta": "cpu-upgrade",
        "speed-arena": "cpu-upgrade",
        "governed-agent": "l4x1",
    }
    assert all(s.sleep_time == -1 for s in mf.live)
    assert mf.space("governed-agent").is_gpu and not mf.space("algenta").is_gpu
    assert mf.space("governed-agent").poll_timeout_s == 60 * 60
    assert mf.space("speed-arena").poll_timeout_s == 40 * 60
    assert mf.space("speed-arena").python == "3.12"
    assert mf.space("speed-arena").sdk == "gradio", "no Dockerfile until M2"
    assert not mf.space("speed-arena").is_docker and mf.space("speed-arena").is_live
    assert {s.sdk for s in mf.live} == {"docker", "gradio"}
    for s in mf.live:
        assert mf.source_dir(s.name).is_dir(), s.name
        assert "HF_TOKEN" in s.secrets
        assert s.shared_shell is False, f"{s.name} does not render the shared footer yet"
    for s in mf.redirects:
        assert mf.source_dir(s.name).is_dir(), s.name
        assert s.redirect_to.startswith("https://huggingface.co/spaces/thyn-ai/algenta")
        assert s.hardware is None and s.sleep_time is None and s.secrets == ()


def test_manifest_file_has_no_secret_values(apps_spaces_dir: Path) -> None:
    raw = tomllib.loads((apps_spaces_dir / "spaces.toml").read_text(encoding="utf-8"))
    for table in raw["spaces"].values():
        for secret in table.get("secrets", []):
            assert re.fullmatch(r"[A-Z][A-Z0-9_]*", secret), secret
            assert not re.search(r"hf_[A-Za-z0-9]{20,}", secret), "a token value, not a name"


def test_urls_and_verify_entry_split() -> None:
    mf = _parse(MINIMAL)
    s = mf.space("algenta")
    assert s.subdomain == "thyn-ai-algenta"
    assert s.space_url == "https://thyn-ai-algenta.hf.space"
    assert s.hub_url == "https://huggingface.co/spaces/thyn-ai/algenta"
    assert (s.verify_module, s.verify_function) == ("verify_remote", "check_algenta")
    assert s.is_live and not mf.space("llm-modules").is_live


def test_unknown_space_raises_with_known_names() -> None:
    with pytest.raises(m.ManifestError, match="known: algenta, llm-modules"):
        _parse(MINIMAL).space("nope")


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("fleet", "colour"), "purple", "unknown key"),
        (("fleet", "budget_usd"), 0, "positive"),
        (("fleet", "budget_usd"), "650", "must be int"),
        (("fleet", "org"), "thyn-ai/x", "bare organisation"),
        (("fleet", "shared_package"), "/abs", "relative path"),
        (("spaces", "algenta", "hardware"), "cpu-huge", "not a Hub flavour"),
        (("spaces", "algenta", "hardware"), m.ManifestError, "missing required"),
        (("spaces", "algenta", "sdk"), "streamlit", "sdk must be one of"),
        (("spaces", "algenta", "python"), "3.13", "python must be one of"),
        (("spaces", "algenta", "sleep_time"), -2, "sleep_time"),
        (("spaces", "algenta", "sleep_time"), True, "must be int"),
        (("spaces", "algenta", "shared_shell"), "no", "shared_shell must be bool"),
        (("spaces", "algenta", "shared_shell"), 0, "shared_shell must be bool"),
        (("spaces", "algenta", "shared_shell"), m.ManifestError, "missing required"),
        (("spaces", "algenta", "secrets"), ["hf_token"], "not an env var name"),
        (("spaces", "algenta", "secrets"), ["HF_TOKEN", "HF_TOKEN"], "duplicates"),
        (("spaces", "algenta", "variables"), {"HF_TOKEN": "x"}, "both a secret and a variable"),
        (("spaces", "algenta", "variables"), {"lower": "x"}, "env name"),
        (("spaces", "algenta", "api_names"), [], "at least one endpoint"),
        (("spaces", "algenta", "api_names"), ["Run-Duel"], "not a valid api_name"),
        (("spaces", "algenta", "verify"), "verify_remote.check", "module:function"),
        (("spaces", "algenta", "repo_id"), "someone-else/algenta", "fleet org"),
        (("spaces", "algenta", "repo_id"), "algenta", "owner/name"),
        (("spaces", "algenta", "source"), "../escape", "relative directory"),
        (("spaces", "algenta", "redirect_to"), "https://x", "only valid for static"),
        (("spaces", "algenta", "typo"), 1, "unknown key"),
        (("spaces", "llm-modules", "hardware"), "cpu-basic", "only valid for a live Space"),
        (("spaces", "llm-modules", "shared_shell"), False, "only valid for a live Space"),
        (("spaces", "llm-modules", "redirect_to"), "https://example.com", "Hub Space URL"),
        (("spaces", "llm-modules", "redirect_to"), m.ManifestError, "missing required"),
    ],
)
def test_validation_rejects(path: tuple[str, ...], value: object, message: str) -> None:
    with pytest.raises(m.ManifestError, match=message):
        _parse(_with(path, value))


def test_top_level_and_uniqueness_rules() -> None:
    with pytest.raises(m.ManifestError, match="top-level unknown"):
        _parse({**MINIMAL, "extra": {}})
    with pytest.raises(m.ManifestError, match="needs a \\[fleet\\]"):
        _parse({"spaces": MINIMAL["spaces"]})
    with pytest.raises(m.ManifestError, match="kebab-case"):
        _parse({"fleet": MINIMAL["fleet"], "spaces": {"Bad_Name": MINIMAL["spaces"]["algenta"]}})
    dup = copy.deepcopy(MINIMAL)
    dup["spaces"]["twin"] = dict(dup["spaces"]["algenta"], source="twin")
    with pytest.raises(m.ManifestError, match="repo_id values must be unique"):
        _parse(dup)
    dup = copy.deepcopy(MINIMAL)
    dup["spaces"]["twin"] = dict(dup["spaces"]["algenta"], repo_id="thyn-ai/twin")
    with pytest.raises(m.ManifestError, match="source directories must be unique"):
        _parse(dup)
    with pytest.raises(m.ManifestError, match="at least one space"):
        _parse({"fleet": MINIMAL["fleet"], "spaces": {}})


def test_load_manifest_reports_toml_errors(tmp_path: Path) -> None:
    bad = tmp_path / "spaces.toml"
    bad.write_text("[fleet\norg = 1\n", encoding="utf-8")
    with pytest.raises(m.ManifestError, match="spaces.toml"):
        m.load_manifest(bad)


def test_optional_docker_keys_default_empty(tmp_path: Path) -> None:
    raw = copy.deepcopy(MINIMAL)
    del raw["spaces"]["algenta"]["secrets"]
    del raw["spaces"]["algenta"]["variables"]
    s = _parse(raw).space("algenta")
    assert s.secrets == () and s.variables == {}


def test_gradio_is_a_live_sdk_without_a_dockerfile() -> None:
    raw = _with(("spaces", "algenta", "sdk"), "gradio")
    s = _parse(raw).space("algenta")
    assert s.is_live and not s.is_docker
    assert s.shared_shell is False
    on_shell = _parse(_with(("spaces", "algenta", "shared_shell"), True)).space("algenta")
    assert on_shell.shared_shell is True


def _frontmatter(readme: Path) -> dict[str, str]:
    """Scalar ``key: value`` pairs of the Hub card frontmatter (quotes stripped)."""
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0] == "---", f"{readme} has no frontmatter"
    end = lines.index("---", 1)
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if line.startswith((" ", "\t")):  # block-list continuation, never a scalar we compare
            continue
        key, sep, raw = line.partition(":")
        assert sep, f"{readme}: {line!r}"
        fields[key.strip()] = raw.strip().strip("\"'")
    return fields


_SHARED_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+algenta_spaces\b", re.MULTILINE)


def test_live_space_sources_match_the_manifest(apps_spaces_dir: Path) -> None:
    """The manifest tells the truth today: frontmatter, Dockerfile presence and the shell flag."""
    mf = m.load_manifest()
    for space in mf.live:
        src = mf.source_dir(space.name)
        front = _frontmatter(src / "README.md")
        assert front["sdk"] == space.sdk, f"{space.name}: README says sdk {front['sdk']!r}"
        if "python_version" in front:
            assert front["python_version"] == space.python, space.name
        assert (src / "Dockerfile").is_file() is space.is_docker, (
            f"{space.name}: a Dockerfile exists iff sdk == 'docker'"
        )
        if space.is_docker:
            # the Hub routes to app_port (7860 when absent); the image must expose that port
            exposed = re.findall(r"^EXPOSE\s+(\d+)", (src / "Dockerfile").read_text("utf-8"), re.M)
            assert exposed == [front.get("app_port", "7860")], f"{space.name}: app_port vs EXPOSE"
        else:
            assert front.get("sdk_version"), f"{space.name}: the gradio SDK needs sdk_version"
        renders_shared_footer = any(
            _SHARED_IMPORT_RE.search(py.read_text(encoding="utf-8"))
            for py in src.rglob("*.py")
            if "tests" not in py.relative_to(src).parts
        )
        assert renders_shared_footer is space.shared_shell, (
            f"{space.name}: shared_shell must say whether the app imports algenta_spaces"
        )
    for space in mf.redirects:
        front = _frontmatter(mf.source_dir(space.name) / "README.md")
        assert front["sdk"] == "static" == space.sdk
        assert not (mf.source_dir(space.name) / "Dockerfile").exists()
