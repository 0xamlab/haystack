"""apps/spaces/tools/manifest.py — the fleet manifest loader and its validation."""

from __future__ import annotations

import copy
import importlib
import re
import sys
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
    """The fleet is the flagship alone since 2026-09-23: the two deep-dive Spaces and the three
    redirect stubs were deleted from the Hub that day and left the manifest with them."""
    mf = m.load_manifest()
    assert mf.path == (apps_spaces_dir / "spaces.toml").resolve()
    assert mf.fleet.org == "thyn-ai"
    assert mf.fleet.budget_usd == 650
    assert mf.shared_package_dir == apps_spaces_dir / "_shared" / "algenta_spaces"
    assert list(mf.spaces) == ["algenta"]
    assert [s.name for s in mf.live] == ["algenta"]
    assert mf.redirects == []
    flagship = mf.space("algenta")
    assert flagship.repo_id == "thyn-ai/algenta"
    assert flagship.sdk == "docker" and flagship.is_docker and flagship.is_live
    assert {s.sdk for s in mf.live} == {"docker"}
    assert flagship.python == "3.14"
    assert flagship.hardware == "cpu-upgrade" and not flagship.is_gpu
    assert not any(s.is_gpu for s in mf.live), "no GPU stage in the fleet"
    assert flagship.poll_timeout_s == 40 * 60
    assert flagship.sleep_time == -1
    assert mf.source_dir("algenta").is_dir()
    assert flagship.secrets == ("ALGENTA_API_KEY", "HF_TOKEN")
    assert flagship.variables == {"ALGENTA_BASE_URL": "https://api.algenta.ai"}
    assert flagship.verify == "verify_remote:check_algenta"
    # the flagship renders the shared footer since M2-B
    assert flagship.shared_shell is True


def test_flagship_api_names_are_the_tabs_api_names(apps_spaces_dir: Path) -> None:
    """The flagship row is derived: `tabs/<id>_tab.py` `API_NAMES` in strip order, nothing else.
    `verify_remote.expected_endpoints` reads the row, `verify_checks.expected_api_names` reads
    the tabs; the two must agree or a deploy passes one check and fails the other."""
    algenta_dir = str(apps_spaces_dir / "algenta")
    if algenta_dir not in sys.path:
        sys.path.insert(0, algenta_dir)
    vc = importlib.import_module("verify_checks")
    found = vc.tab_api_names()
    assert set(found) == set(vc.TAB_SLUGS), f"tab modules that imported: {sorted(found)}"
    derived = tuple(name for slug in vc.TAB_SLUGS for name in found[slug])
    row = m.load_manifest().space("algenta").api_names
    assert row == derived, (
        "apps/spaces/spaces.toml [spaces.algenta].api_names drifted from the tabs' API_NAMES:"
        f"\n  manifest {row}\n  tabs     {derived}"
    )
    assert set(row) == vc.all_expected()
    assert len(set(row)) == len(row) == 17


GPU_STATUS_SLOT_RE = re.compile(
    r"^# (?P<env>[A-Z][A-Z0-9_]*GPU_STATUS_URL) = \"https://[^\"]+/api/status\"$", re.M
)


def test_gpu_status_url_is_unset_while_the_fleet_has_no_gpu_stage(apps_spaces_dir: Path) -> None:
    """The GPU tiles poll a GPU stage's `/api/status` through the variable the app reads
    (`gpu_status.STATUS_URL_ENV`). The fleet has had no GPU stage since 2026-09-23, so that
    variable is unset on the flagship and `gpu_status.configured` is false: the tabs draw no GPU
    tile and poll nothing. The loader refuses an empty value, so unset means absent, never `""`;
    a slot documented as a comment (M3.1) must name that same variable or setting it wires
    nothing."""
    algenta_dir = str(apps_spaces_dir / "algenta")
    if algenta_dir not in sys.path:
        sys.path.insert(0, algenta_dir)
    gpu_status = importlib.import_module("gpu_status")
    env_name = gpu_status.STATUS_URL_ENV
    assert env_name.endswith("GPU_STATUS_URL"), env_name
    mf = m.load_manifest()
    assert not any(s.is_gpu for s in mf.live), "a GPU stage joined the fleet: wire its slot"
    for s in mf.live:
        assert env_name not in s.variables, f"{s.name}: set without a GPU stage to point at"
        assert gpu_status.configured(s.variables) is False, s.name
    text = (apps_spaces_dir / "spaces.toml").read_text(encoding="utf-8")
    for slot in GPU_STATUS_SLOT_RE.finditer(text):
        assert slot.group("env") == env_name, "a documented slot is not the env the app reads"


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


def test_static_spaces_are_served_from_the_static_host() -> None:
    """Static stubs live on <subdomain>.static.hf.space; app Spaces on <subdomain>.hf.space.
    Checked on the inline fleet: the real manifest carries no static Space since 2026-09-23."""
    mf = _parse(MINIMAL)
    static = [s for s in mf.spaces.values() if s.sdk == "static"]
    apps = [s for s in mf.spaces.values() if s.sdk != "static"]
    assert static and apps
    for s in static:
        assert s.space_url == f"https://{s.subdomain}.static.hf.space"
    for s in apps:
        assert s.space_url == f"https://{s.subdomain}.hf.space"
