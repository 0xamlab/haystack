"""facts.json — every number and version a Space's copy may quote, computed, never typed.

`compute_facts` collects installed distribution versions, the interpreter, the
git sha (`GIT_SHA` / `GITHUB_SHA` or the `.git_sha` file `tools/stage.py`
writes), the shared-package stamp, and the Space id and hardware tier the Hub
sets in the container. `write_facts` stores it atomically as JSON.
"""

from __future__ import annotations

import json
import os
import platform
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .runtime import STAMP_DEFAULT, is_sha, pinned_versions, read_stamp, utc_stamp

GIT_SHA_ENV_KEYS = ("GIT_SHA", "GITHUB_SHA")
GIT_SHA_FILE = ".git_sha"
SHARED_SHA_FILE = ".shared_sha"
FACTS_FILE = "facts.json"


def package_root() -> Path:
    """The directory next to the `algenta_spaces` package (the Space root once vendored)."""
    return Path(__file__).resolve().parent.parent


def git_sha(env: Mapping[str, str] | None = None, root: Path | str | None = None) -> str:
    """The deploy's git sha from the environment, else the `.git_sha` file, else `dev`."""
    env = os.environ if env is None else env
    for key in GIT_SHA_ENV_KEYS:
        value = env.get(key, "").strip().lower()
        if is_sha(value):
            return value
    base = package_root() if root is None else Path(root)
    return read_stamp(base / GIT_SHA_FILE, STAMP_DEFAULT)


def compute_facts(
    dist_names: Iterable[str],
    *,
    env: Mapping[str, str] | None = None,
    root: Path | str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The facts record for this container, with sorted, JSON-serialisable values."""
    env = os.environ if env is None else env
    base = package_root() if root is None else Path(root)
    return {
        "generated_utc": utc_stamp(now),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": f"{platform.system()} {platform.machine()}",
        "git_sha": git_sha(env, base),
        "shared_sha": read_stamp(base / SHARED_SHA_FILE, STAMP_DEFAULT),
        "space_id": env.get("SPACE_ID", "").strip(),
        "space_hardware": env.get("SPACE_HARDWARE", "").strip(),
        "versions": dict(sorted(pinned_versions(dist_names).items())),
    }


def write_facts(path: Path | str, facts: Mapping[str, Any]) -> Path:
    """Write `facts` as indented JSON, atomically, and return the path."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


def read_facts(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a facts object")
    return data
