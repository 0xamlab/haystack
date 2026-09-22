"""Fleet manifest loader for apps/spaces/spaces.toml.

The manifest is the single source of truth for what runs where: repo ids, SDK, source
directory, hardware, sleep policy, secret names, variables and the remote verify entry.
Loading is strict — an unknown key, a wrong type or an inconsistent combination raises
``ManifestError`` with the offending table and key, so a typo never reaches the Hub.

Live Spaces run the ``docker`` or the ``gradio`` SDK (what each Space's README frontmatter
says today; ``speed-arena`` stays ``gradio`` until its Dockerfile lands in M2). Retired Spaces
are ``static`` redirects. Every live Space carries ``shared_shell``: ``true`` once the app
renders the ``algenta_spaces`` footer with its build stamp, ``false`` until then, so
``verify_remote`` knows whether the stamp check can run or must be skipped loudly.

Runs on CPython 3.12 and 3.14 (stdlib only: ``tomllib`` + ``dataclasses``).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APPS_SPACES_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = APPS_SPACES_DIR / "spaces.toml"

SDKS = frozenset({"docker", "gradio", "static"})
LIVE_SDKS = frozenset({"docker", "gradio"})
PYTHONS = frozenset({"3.12", "3.14"})
# Flavours HF sells today (huggingface_hub.SpaceHardware, 1.26). GPU = not "cpu-*".
HARDWARE = frozenset(
    {
        "cpu-basic",
        "cpu-upgrade",
        "zero-a10g",
        "t4-small",
        "t4-medium",
        "l4x1",
        "l4x4",
        "l40sx1",
        "l40sx4",
        "l40sx8",
        "a10g-small",
        "a10g-large",
        "a10g-largex2",
        "a10g-largex4",
        "a100-large",
        "a100x4",
        "a100x8",
    }
)

POLL_TIMEOUT_CPU_S = 40 * 60
POLL_TIMEOUT_GPU_S = 60 * 60

_FLEET_KEYS = {"org": str, "shared_package": str, "budget_usd": int}
_COMMON_KEYS = {"repo_id": str, "sdk": str, "source": str, "verify": str}
_LIVE_KEYS = {
    "python": str,
    "hardware": str,
    "sleep_time": int,
    "secrets": list,
    "variables": dict,
    "api_names": list,
    "shared_shell": bool,
}
_STATIC_KEYS = {"redirect_to": str}
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_VERIFY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:[A-Za-z_][A-Za-z0-9_]*$")
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_API_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SOURCE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]*$")


class ManifestError(ValueError):
    """The manifest is malformed or inconsistent."""


@dataclass(frozen=True)
class Fleet:
    org: str
    shared_package: str
    budget_usd: int


@dataclass(frozen=True)
class Space:
    name: str
    repo_id: str
    sdk: str
    source: str
    verify: str
    python: str | None = None
    hardware: str | None = None
    sleep_time: int | None = None
    secrets: tuple[str, ...] = ()
    variables: dict[str, str] = field(default_factory=dict)
    api_names: tuple[str, ...] = ()
    shared_shell: bool = False
    redirect_to: str | None = None

    @property
    def is_live(self) -> bool:
        return self.sdk in LIVE_SDKS

    @property
    def is_docker(self) -> bool:
        return self.sdk == "docker"

    @property
    def is_gpu(self) -> bool:
        return self.hardware is not None and not self.hardware.startswith("cpu-")

    @property
    def poll_timeout_s(self) -> int:
        return POLL_TIMEOUT_GPU_S if self.is_gpu else POLL_TIMEOUT_CPU_S

    @property
    def subdomain(self) -> str:
        return self.repo_id.replace("/", "-").lower()

    @property
    def space_url(self) -> str:
        return f"https://{self.subdomain}.hf.space"

    @property
    def hub_url(self) -> str:
        return f"https://huggingface.co/spaces/{self.repo_id}"

    @property
    def verify_module(self) -> str:
        return self.verify.split(":", 1)[0]

    @property
    def verify_function(self) -> str:
        return self.verify.split(":", 1)[1]


@dataclass(frozen=True)
class Manifest:
    fleet: Fleet
    spaces: dict[str, Space]
    path: Path

    def space(self, name: str) -> Space:
        try:
            return self.spaces[name]
        except KeyError:
            known = ", ".join(sorted(self.spaces))
            raise ManifestError(f"unknown space {name!r}; known: {known}") from None

    @property
    def live(self) -> list[Space]:
        return [s for s in self.spaces.values() if s.is_live]

    @property
    def redirects(self) -> list[Space]:
        return [s for s in self.spaces.values() if not s.is_live]

    @property
    def shared_package_dir(self) -> Path:
        return self.path.parent / self.fleet.shared_package

    def source_dir(self, name: str) -> Path:
        return self.path.parent / self.space(name).source


def _check_keys(table: str, data: dict, allowed: dict[str, type]) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ManifestError(f"[{table}] unknown key(s): {', '.join(unknown)}")
    for key, typ in allowed.items():
        if key not in data:
            continue
        value = data[key]
        # bool is an int subclass: an int key refuses bools, a bool key accepts only bools.
        well_typed = isinstance(value, bool) if typ is bool else isinstance(value, typ)
        if not well_typed or (typ is not bool and isinstance(value, bool)):
            raise ManifestError(f"[{table}].{key} must be {typ.__name__}")


def _require(table: str, data: dict, keys: tuple[str, ...]) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ManifestError(f"[{table}] missing required key(s): {', '.join(missing)}")


def _parse_fleet(data: object) -> Fleet:
    if not isinstance(data, dict):
        raise ManifestError("[fleet] must be a table")
    _check_keys("fleet", data, _FLEET_KEYS)
    _require("fleet", data, ("org", "shared_package", "budget_usd"))
    if not data["org"] or "/" in data["org"]:
        raise ManifestError("[fleet].org must be a bare organisation name")
    if data["budget_usd"] <= 0:
        raise ManifestError("[fleet].budget_usd must be positive")
    if not data["shared_package"] or data["shared_package"].startswith(("/", "..")):
        raise ManifestError("[fleet].shared_package must be a relative path inside apps/spaces")
    return Fleet(
        org=data["org"], shared_package=data["shared_package"], budget_usd=data["budget_usd"]
    )


def _parse_space(name: str, data: object, org: str) -> Space:
    table = f"spaces.{name}"
    if not isinstance(data, dict):
        raise ManifestError(f"[{table}] must be a table")
    _check_keys(table, data, {**_COMMON_KEYS, **_LIVE_KEYS, **_STATIC_KEYS})
    _require(table, data, ("repo_id", "sdk", "source", "verify"))
    sdk = data["sdk"]
    if sdk not in SDKS:
        raise ManifestError(f"[{table}].sdk must be one of {sorted(SDKS)}, got {sdk!r}")
    repo_id = data["repo_id"]
    if not _REPO_ID_RE.match(repo_id):
        raise ManifestError(f"[{table}].repo_id {repo_id!r} is not owner/name")
    if repo_id.split("/", 1)[0] != org:
        raise ManifestError(f"[{table}].repo_id {repo_id!r} is not under the fleet org {org!r}")
    if not _SOURCE_RE.match(data["source"]) or ".." in data["source"]:
        raise ManifestError(f"[{table}].source {data['source']!r} must be a relative directory")
    if not _VERIFY_RE.match(data["verify"]):
        raise ManifestError(f"[{table}].verify must be module:function, got {data['verify']!r}")

    if sdk in LIVE_SDKS:
        stray = sorted(set(data) & set(_STATIC_KEYS))
        if stray:
            raise ManifestError(f"[{table}] key(s) only valid for static: {', '.join(stray)}")
        _require(table, data, ("python", "hardware", "sleep_time", "api_names", "shared_shell"))
        if data["python"] not in PYTHONS:
            raise ManifestError(f"[{table}].python must be one of {sorted(PYTHONS)}")
        if data["hardware"] not in HARDWARE:
            raise ManifestError(f"[{table}].hardware {data['hardware']!r} is not a Hub flavour")
        if data["sleep_time"] < -1:
            raise ManifestError(f"[{table}].sleep_time must be -1 (always on) or >= 0 seconds")
        secrets = tuple(data.get("secrets", ()))
        for s in secrets:
            if not isinstance(s, str) or not _ENV_NAME_RE.match(s):
                raise ManifestError(f"[{table}].secrets entry {s!r} is not an env var name")
        if len(set(secrets)) != len(secrets):
            raise ManifestError(f"[{table}].secrets has duplicates")
        variables = dict(data.get("variables", {}))
        for k, v in variables.items():
            if not _ENV_NAME_RE.match(k) or not isinstance(v, str) or not v:
                raise ManifestError(f"[{table}].variables.{k} must map an env name to a string")
        if set(variables) & set(secrets):
            raise ManifestError(f"[{table}] a name cannot be both a secret and a variable")
        api_names = tuple(data["api_names"])
        if not api_names:
            raise ManifestError(f"[{table}].api_names must list at least one endpoint")
        for a in api_names:
            if not isinstance(a, str) or not _API_NAME_RE.match(a):
                raise ManifestError(f"[{table}].api_names entry {a!r} is not a valid api_name")
        return Space(
            name=name,
            repo_id=repo_id,
            sdk=sdk,
            source=data["source"],
            verify=data["verify"],
            python=data["python"],
            hardware=data["hardware"],
            sleep_time=data["sleep_time"],
            secrets=secrets,
            variables=variables,
            api_names=api_names,
            shared_shell=data["shared_shell"],
        )

    stray = sorted(set(data) & set(_LIVE_KEYS))
    if stray:
        raise ManifestError(
            f"[{table}] key(s) only valid for a live Space (docker or gradio): {', '.join(stray)}"
        )
    _require(table, data, ("redirect_to",))
    if not data["redirect_to"].startswith("https://huggingface.co/spaces/"):
        raise ManifestError(f"[{table}].redirect_to must point at a Hub Space URL")
    return Space(
        name=name,
        repo_id=repo_id,
        sdk=sdk,
        source=data["source"],
        verify=data["verify"],
        redirect_to=data["redirect_to"],
    )


def parse_manifest(raw: dict, path: Path) -> Manifest:
    unknown = sorted(set(raw) - {"fleet", "spaces"})
    if unknown:
        raise ManifestError(f"top-level unknown key(s): {', '.join(unknown)}")
    if "fleet" not in raw or "spaces" not in raw:
        raise ManifestError("manifest needs a [fleet] table and a [spaces.*] table set")
    fleet = _parse_fleet(raw["fleet"])
    if not isinstance(raw["spaces"], dict) or not raw["spaces"]:
        raise ManifestError("[spaces] must hold at least one space table")
    spaces: dict[str, Space] = {}
    for name, data in raw["spaces"].items():
        if not re.match(r"^[a-z][a-z0-9-]*$", name):
            raise ManifestError(f"space name {name!r} must be lowercase kebab-case")
        spaces[name] = _parse_space(name, data, fleet.org)
    repo_ids = [s.repo_id for s in spaces.values()]
    if len(set(repo_ids)) != len(repo_ids):
        raise ManifestError("repo_id values must be unique across spaces")
    sources = [s.source for s in spaces.values()]
    if len(set(sources)) != len(sources):
        raise ManifestError("source directories must be unique across spaces")
    return Manifest(fleet=fleet, spaces=spaces, path=path)


def load_manifest(path: Path | str = DEFAULT_MANIFEST) -> Manifest:
    path = Path(path)
    try:
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    return parse_manifest(raw, path.resolve())
