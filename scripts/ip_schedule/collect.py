#!/usr/bin/env python3
"""Collect the facts behind Thyn's Schedule of Intellectual Property into one snapshot.

The schedule that accompanies a securities filing has to be reproducible: every number in
it must come from a named commit, a named registry response, or a named WHOIS record on a
stated date. This script gathers all of them into ``snapshot.json`` so that the workbook and
the narrative (``render.py``) cannot disagree with each other or with the repositories.

What is measured (per repository listed in ``config.toml``):

* git at ``origin/<default branch>`` after a fetch (never the working tree, which may be a
  feature branch or weeks behind): commit SHA and date, first and last commit, commit count,
  contributors collapsed through the identity map into one human plus bots;
* lines of code by language from ``git ls-tree`` + ``git cat-file --batch`` (no checkout),
  with generated and third-party paths excluded from the *authored* totals and reported
  separately, and — for the engine — the same all-tracked-``.mojo``-by-top-level-directory
  table that ``scripts/count_mojo_loc.sh`` prints, so the deck slide can be corrected from it;
* the ``function_count`` / ``module_count`` of the packaged runtime contract;
* the ``mojo/engine/`` subpackage families (file and line counts) for the trade-secret tab;
* direct dependencies from ``pyproject.toml`` / ``package.json`` / ``requirements.txt`` /
  ``pixi.toml`` at that commit, with registry license lookups bucketed by copyleft risk;
* the newest CI SBOM artifacts, when the repository publishes them;
* GitHub repository metadata (visibility, created, pushed, size).

Plus, outside repositories: PyPI/npm package records and WHOIS for each domain.

``--offline`` skips every network call (no fetch, no gh, no registries, no whois) and
``--ref head`` counts the local HEAD instead of ``origin/<default>``; the test suite uses both
so it runs anywhere. Use ``make ip-schedule`` for the real, dated run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_CONFIG = HERE / "config.toml"
GIT = shutil.which("git") or "git"
GH = shutil.which("gh") or "gh"
WHOIS = shutil.which("whois") or "whois"
USER_AGENT = "thyn-ip-schedule/1 (+https://thyn.ai)"
HTTP_TIMEOUT = 30
BATCH = 400  # paths per `git cat-file --batch` invocation


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------


def log(msg: str) -> None:
    sys.stderr.write(f"[ip-schedule] {msg}\n")


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
    timeout: int = 900,
) -> bytes:
    proc = subprocess.run(  # noqa: S603 - fixed argv lists built from config, never a shell
        args,
        cwd=cwd,
        input=input_bytes,
        capture_output=True,
        check=False,
        timeout=timeout,
        stdin=None if input_bytes is not None else subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"{' '.join(args[:4])} … failed ({proc.returncode}): {tail}")
    return proc.stdout


def git(repo: Path, *args: str, **kw: Any) -> str:
    return run([GIT, "-C", str(repo), *args], **kw).decode("utf-8", "replace")


def http_json(url: str) -> Any:
    req = urllib.request.Request(  # noqa: S310 - https only, fixed hosts
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:  # noqa: S310
        return json.load(resp)


def gh_json(endpoint: str, *extra: str) -> Any:
    return json.loads(run([GH, "api", endpoint, *extra]).decode("utf-8"))


def today() -> str:
    return dt.date.today().isoformat()


# --------------------------------------------------------------------------------------
# License bucketing
# --------------------------------------------------------------------------------------

STRONG = re.compile(r"\b(AGPL|GPL)\b", re.I)
WEAK = re.compile(r"\b(LGPL|MPL|EPL|CDDL|EUPL|OSL|CPAL)\b", re.I)
PERMISSIVE = re.compile(
    r"\b(MIT|BSD|Apache|ISC|PSF|Python Software Foundation|Unlicense|Zlib|BlueOak|0BSD|CC0|"
    r"WTFPL|Artistic|HPND|Boost|LLVM|MIT-0|Public Domain|CC-BY(?!-SA|-NC))\b",
    re.I,
)
PROPRIETARY = re.compile(r"\b(Proprietary|Commercial|All Rights Reserved)\b", re.I)


ORDER = ["permissive", "weak-copyleft", "strong-copyleft", "proprietary", "unknown"]


def bucket_license(text: str | None) -> str:
    """Bucket an SPDX-ish license string; ``A OR B`` takes the most permissive alternative,
    ``A AND B`` the most restrictive conjunct."""
    if not text:
        return "unknown"
    t = text.strip().strip("()")
    if re.search(r"\s+OR\s+", t, re.I):
        parts = [_bucket_one(x) for x in re.split(r"\s+OR\s+", t, flags=re.I)]
        return min(parts, key=ORDER.index)
    if re.search(r"\s+AND\s+", t, re.I):
        parts = [_bucket_one(x) for x in re.split(r"\s+AND\s+", t, flags=re.I)]
        return max(parts, key=ORDER.index)
    return _bucket_one(t)


def _bucket_one(text: str) -> str:
    t = text.strip().strip("()")
    if len(t) > 200:  # a pasted license body rather than an identifier
        t = t[:200]
    if WEAK.search(t) and not STRONG.search(t.replace("LGPL", "")):
        return "weak-copyleft"
    if STRONG.search(t.replace("LGPL", "")):
        return "strong-copyleft"
    if WEAK.search(t):
        return "weak-copyleft"
    if PERMISSIVE.search(t):
        return "permissive"
    if PROPRIETARY.search(t):
        return "proprietary"
    return "unknown"


def pypi_license(info: dict[str, Any]) -> str | None:
    expr = info.get("license_expression") or info.get("license")
    if expr and len(expr) < 120:
        return expr
    classifiers = [c for c in info.get("classifiers", []) if c.startswith("License ::")]
    if classifiers:
        return "; ".join(c.split("::")[-1].strip() for c in classifiers)
    return expr[:120] if expr else None


# --------------------------------------------------------------------------------------
# Repository measurement
# --------------------------------------------------------------------------------------


class Repo:
    def __init__(
        self,
        cfg: dict[str, Any],
        global_cfg: dict[str, Any],
        *,
        offline: bool,
        ref_mode: str,
        clone_root: Path,
        prefer_self: bool = False,
    ) -> None:
        self.cfg = cfg
        self.prefer_self = prefer_self
        self.key: str = cfg["key"]
        self.org_repo: str = cfg["org_repo"]
        self.role: str = cfg.get("role", "core")
        self.offline = offline
        self.ref_mode = ref_mode
        self.clone_root = clone_root
        self.languages: dict[str, str] = global_cfg["counting"]["languages"]
        self.exclude_dirs: set[str] = set(global_cfg["counting"]["exclude"]["dirs"])
        self.exclude_prefixes: list[str] = list(cfg.get("exclude_prefixes", []))
        self.third_party_prefixes: list[str] = list(cfg.get("third_party_prefixes", []))
        self.non_product_dirs: set[str] = set(
            (global_cfg.get("valuation") or {}).get("non_product_dirs", [])
        )
        self.identity = global_cfg["identity"]
        self.bot_patterns = [re.compile(p) for p in self.identity["bot_patterns"]]
        self.path: Path | None = None
        self.notes: list[str] = []

    # -- location -----------------------------------------------------------------------

    def locate(self) -> bool:
        # --self: the checkout this script lives in wins for its own repository (hermetic
        # tests and CI runners), regardless of any configured local path.
        if self.prefer_self and self.checkout_is(ROOT):
            self.path = ROOT
            return True
        local = self.cfg.get("local_path")
        if local:
            p = Path(os.path.expanduser(local))
            if (p / ".git").exists() or (p / ".git").is_file():
                self.path = p
                return True
            self.notes.append(f"configured local_path {local} is not a git checkout")
        # The checkout this script lives in (a CI runner, a worktree, another machine) counts
        # for its own repository even when the configured path is absent.
        if self.checkout_is(ROOT):
            self.path = ROOT
            return True
        if self.offline:
            self.notes.append("no local checkout and --offline: repository not measured")
            return False
        dest = self.clone_root / self.key
        if not dest.exists():
            log(f"{self.key}: cloning {self.org_repo} into {dest}")
            run([GIT, "clone", "--quiet", f"https://github.com/{self.org_repo}.git", str(dest)])
        self.path = dest
        return True

    def checkout_is(self, path: Path) -> bool:
        """True when ``path`` is a git checkout whose origin is this repository."""
        if not ((path / ".git").exists() or (path / ".git").is_file()):
            return False
        try:
            url = git(path, "remote", "get-url", "origin").strip()
        except RuntimeError:
            return False
        # require a path-segment match ("/thyn-ai/algenta" or ":thyn-ai/algenta"), so a remote
        # such as evil.example/prefix-thyn-ai/algenta cannot pass as this repository
        normalized = url.rstrip("/").removesuffix(".git").lower()
        target = self.org_repo.lower()
        return normalized.endswith("/" + target) or normalized.endswith(":" + target)

    def default_branch(self) -> str:
        assert self.path is not None
        try:
            ref = git(self.path, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
            if ref:
                return ref.rsplit("/", 1)[-1]
        except RuntimeError:
            pass
        if not self.offline:
            try:
                return (
                    gh_json(f"repos/{self.org_repo}", "--jq", ".default_branch").strip().strip('"')
                )
            except RuntimeError:
                pass
        return "main"

    def resolve_ref(self) -> str:
        assert self.path is not None
        if self.ref_mode == "head":
            return "HEAD"
        branch = self.default_branch()
        if not self.offline:
            # A concurrent fetch in the same checkout can lose the ref lock; one retry
            # covers that, and a failure after the retry still leaves a usable (if
            # possibly stale) origin/<branch>, which is recorded in the notes.
            for attempt in (1, 2):
                try:
                    git(self.path, "fetch", "--quiet", "origin", branch)
                    break
                except RuntimeError as exc:
                    if attempt == 2:
                        self.notes.append(
                            f"fetch of origin/{branch} failed; counted the "
                            f"previously fetched ref: {exc}"[:300]
                        )
        return f"origin/{branch}"

    # -- git facts ----------------------------------------------------------------------

    def is_human(self, name: str, email: str) -> bool:
        if any(p.search(name) or p.search(email) for p in self.bot_patterns):
            return False
        return name in self.identity["human_names"] or email in self.identity["human_emails"]

    def history(self, ref: str) -> dict[str, Any]:
        assert self.path is not None
        sha = git(self.path, "rev-parse", ref).strip()
        sha_date = git(self.path, "log", "-1", "--format=%cs", ref).strip()
        shallow = git(self.path, "rev-parse", "--is-shallow-repository").strip() == "true"
        dates = git(self.path, "log", "--format=%as", "--reverse", ref).split()
        count = int(git(self.path, "rev-list", "--count", ref).strip())
        humans: Counter[str] = Counter()
        bots: Counter[str] = Counter()
        unknown: Counter[str] = Counter()
        for line in git(self.path, "shortlog", "-sne", "--no-merges", ref).splitlines():
            m = re.match(r"\s*(\d+)\s+(.*?)\s+<([^>]*)>", line)
            if not m:
                continue
            n, name, email = int(m.group(1)), m.group(2), m.group(3)
            if any(p.search(name) or p.search(email) for p in self.bot_patterns):
                bots[name] += n
            elif self.is_human(name, email):
                humans[self.identity["human"]] += n
            else:
                unknown[f"{name} <{email}>"] += n
        return {
            "sha": sha,
            "sha_short": sha[:8],
            "sha_date": sha_date,
            "first_commit": dates[0] if dates else None,
            "last_commit": dates[-1] if dates else None,
            "commit_count": count,
            "history_complete": not shallow,
            "contributors": {
                "humans": [{"name": k, "commits": v} for k, v in humans.most_common()],
                "bots": [{"name": k, "commits": v} for k, v in bots.most_common()],
                "unmapped": [{"name": k, "commits": v} for k, v in unknown.most_common()],
            },
        }

    # -- line counting ------------------------------------------------------------------

    def language_of(self, path: str) -> str | None:
        return self.languages.get(os.path.splitext(path)[1])

    def excluded_reason(self, path: str) -> str | None:
        for pre in self.third_party_prefixes:
            if path.startswith(pre):
                return f"third-party:{pre}"
        for pre in self.exclude_prefixes:
            if path.startswith(pre):
                return f"generated:{pre}"
        parts = path.split("/")[:-1]
        for part in parts:
            if part in self.exclude_dirs:
                return f"dir:{part}"
        return None

    def area_of(self, path: str) -> str:
        """product | tests | benchmarks | other — by directory name, for the cost basis."""
        comps = path.split("/")[:-1]
        if any(c in ("tests", "test") for c in comps):
            return "tests"
        if any(c in ("benchmarks", "bench") for c in comps):
            return "benchmarks"
        if any(c in self.non_product_dirs for c in comps):
            return "other"
        return "product"

    def tree(self, ref: str) -> list[str]:
        assert self.path is not None
        out = run([GIT, "-C", str(self.path), "ls-tree", "-r", "-z", "--name-only", ref])
        return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]

    def count_lines(self, ref: str, paths: list[str]) -> dict[str, int]:
        """Newline counts per path at ``ref`` (the same definition as ``wc -l``)."""
        assert self.path is not None
        counts: dict[str, int] = {}
        for i in range(0, len(paths), BATCH):
            chunk = paths[i : i + BATCH]
            spec = "".join(f"{ref}:{p}\n" for p in chunk).encode("utf-8", "surrogateescape")
            out = run([GIT, "-C", str(self.path), "cat-file", "--batch"], input_bytes=spec)
            pos = 0
            for p in chunk:
                nl = out.index(b"\n", pos)
                header = out[pos:nl].decode("utf-8", "replace")
                pos = nl + 1
                if header.endswith(" missing") or header.endswith(" ambiguous"):
                    counts[p] = 0
                    continue
                size = int(header.rsplit(" ", 1)[1])
                body = out[pos : pos + size]
                counts[p] = body.count(b"\n")
                pos += size + 1
        return counts

    def measure_code(self, ref: str) -> dict[str, Any]:
        files = self.tree(ref)
        code = [(p, lang) for p in files if (lang := self.language_of(p))]
        lines = self.count_lines(ref, [p for p, _ in code])
        authored: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        by_area: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        product_by_lang: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        excluded: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        excluded_by_lang: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        third_party: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
        for p, lang in code:
            reason = self.excluded_reason(p)
            if reason is None:
                authored[lang]["lines"] += lines[p]
                authored[lang]["files"] += 1
                area = self.area_of(p)
                by_area[area]["lines"] += lines[p]
                by_area[area]["files"] += 1
                if area == "product":
                    product_by_lang[lang]["lines"] += lines[p]
                    product_by_lang[lang]["files"] += 1
                continue
            excluded[reason]["lines"] += lines[p]
            excluded[reason]["files"] += 1
            excluded_by_lang[lang]["lines"] += lines[p]
            excluded_by_lang[lang]["files"] += 1
            if reason.startswith("third-party:"):
                third_party[reason.split(":", 1)[1]]["lines"] += lines[p]
                third_party[reason.split(":", 1)[1]]["files"] += 1
        result: dict[str, Any] = {
            "tracked_files_total": len(files),
            "authored": dict(sorted(authored.items(), key=lambda kv: -kv[1]["lines"])),
            "authored_lines": sum(v["lines"] for v in authored.values()),
            "authored_files": sum(v["files"] for v in authored.values()),
            "excluded": dict(excluded),
            "excluded_by_language": dict(excluded_by_lang),
            "authored_by_area": dict(by_area),
            "product_by_language": dict(
                sorted(product_by_lang.items(), key=lambda kv: -kv[1]["lines"])
            ),
            "product_lines": sum(v["lines"] for v in product_by_lang.values()),
            "third_party_code": dict(third_party),
        }
        mojo_paths = [p for p, lang in code if lang == "Mojo"]
        if self.cfg.get("mojo_by_dir"):
            by_dir: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
            for p in mojo_paths:
                top = p.split("/", 1)[0] if "/" in p else "(repo root)"
                by_dir[top]["lines"] += lines[p]
                by_dir[top]["files"] += 1
            result["mojo_tracked"] = {
                "lines": sum(lines[p] for p in mojo_paths),
                "files": len(mojo_paths),
                "definition": "every tracked .mojo file at the snapshot commit, no exclusions "
                "(identical to scripts/count_mojo_loc.sh)",
            }
            result["mojo_by_dir"] = dict(sorted(by_dir.items(), key=lambda kv: -kv[1]["lines"]))
        fam_prefix = self.cfg.get("engine_families_prefix")
        if fam_prefix:
            fams: dict[str, dict[str, int]] = defaultdict(lambda: {"lines": 0, "files": 0})
            for p in mojo_paths:
                if not p.startswith(fam_prefix):
                    continue
                rest = p[len(fam_prefix) :]
                fam = rest.split("/", 1)[0] if "/" in rest else "(top-level modules)"
                fams[fam]["lines"] += lines[p]
                fams[fam]["files"] += 1
            result["engine_families"] = dict(sorted(fams.items(), key=lambda kv: -kv[1]["lines"]))
        return result

    # -- contract, manifests, sbom, github -----------------------------------------------

    def show(self, ref: str, path: str) -> str | None:
        assert self.path is not None
        try:
            return run([GIT, "-C", str(self.path), "show", f"{ref}:{path}"]).decode(
                "utf-8", "replace"
            )
        except RuntimeError:
            return None

    def contract_counts(self, ref: str) -> dict[str, Any] | None:
        rel = self.cfg.get("contract_json")
        if not rel:
            return None
        text = self.show(ref, rel)
        if text is None:
            self.notes.append(f"{rel} not present at {ref}")
            return None
        data = json.loads(text)
        gpu = data.get("engine_kernels") or {}
        kernels = gpu.get("kernels") or []
        roles: Counter[str] = Counter(k.get("role") or "other" for k in kernels)
        families: Counter[str] = Counter(f for k in kernels for f in (k.get("families") or []))
        modules = [
            {
                "name": m.get("name"),
                "backend": m.get("backend"),
                "kernel_count": m.get("kernel_count"),
                "path": m.get("path"),
            }
            for m in (gpu.get("modules") or [])
        ]
        return {
            "source": rel,
            "function_count": data.get("function_count"),
            "module_count": data.get("module_count"),
            "schema_version": data.get("schema_version"),
            "gpu_kernels": {
                "kernel_count": gpu.get("kernel_count", len(kernels)),
                "backend_counts": dict(
                    gpu.get("backend_counts") or Counter(k.get("backend") for k in kernels)
                ),
                "module_count": gpu.get("module_count", len(modules)),
                "roles": dict(roles.most_common()),
                "model_families": dict(families.most_common()),
                "modules": modules,
                "definition": "pointer-based CUDA and Metal kernels declared in the packaged "
                "runtime contract (engine_kernels); capability declaration, not callable "
                "runtime functions",
            },
        }

    def manifests(self, ref: str, files: list[str]) -> dict[str, Any]:
        py: set[str] = set()
        js: set[str] = set()
        env: set[str] = set()
        read: list[str] = []
        name_re = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
        for p in files:
            if self.excluded_reason(p):
                continue
            base = p.rsplit("/", 1)[-1]
            if base == "pyproject.toml":
                text = self.show(ref, p)
                if not text:
                    continue
                try:
                    data = tomllib.loads(text)
                except tomllib.TOMLDecodeError:
                    continue
                proj = data.get("project", {})
                deps = list(proj.get("dependencies", []))
                for spec in deps:
                    m = name_re.match(spec)
                    if m:
                        py.add(m.group(1).lower())
                read.append(p)
            elif base == "package.json" and "node_modules" not in p:
                text = self.show(ref, p)
                if not text:
                    continue
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                for name in data.get("dependencies") or {}:
                    js.add(name)
                read.append(p)
            elif base == "requirements.txt" and "lock" not in p:
                text = self.show(ref, p) or ""
                names = [
                    name_re.match(line)
                    for line in text.splitlines()
                    if line.strip() and not line.startswith(("#", "-"))
                ]
                if len(names) > 120:  # a pinned transitive lockfile, not a direct list
                    continue
                for m in names:
                    if m:
                        py.add(m.group(1).lower())
                read.append(p)
            elif base == "pixi.toml":
                text = self.show(ref, p)
                if not text:
                    continue
                try:
                    data = tomllib.loads(text)
                except tomllib.TOMLDecodeError:
                    continue
                for section in ("dependencies", "pypi-dependencies"):
                    env.update(k.lower() for k in (data.get(section) or {}))
                read.append(p)
        # the company's own packages are not third-party dependencies
        own_prefixes = (
            "algenta",
            "codna",
            "@codna/",
            "telys",
            "sqai",
            "@thyn-ai/",
            "memengine",
            "cohenta",
        )

        def is_own(name: str) -> bool:
            return name.lower().startswith(own_prefixes)

        py = {x for x in py if not is_own(x)}
        js = {x for x in js if not is_own(x)}
        env = {x for x in env if not is_own(x)}
        return {
            "manifests_read": sorted(read),
            "python_direct": sorted(py),
            "javascript_direct": sorted(js),
            "environment_only": sorted(env),
        }

    def sbom(self) -> dict[str, Any] | None:
        prefixes = self.cfg.get("sbom_artifact_prefixes") or []
        if not prefixes or self.offline:
            return None
        try:
            arts = gh_json(f"repos/{self.org_repo}/actions/artifacts?per_page=100")["artifacts"]
        except RuntimeError as exc:
            self.notes.append(f"sbom: artifact listing failed: {exc}")
            return None
        result: dict[str, Any] = {}
        for prefix in prefixes:
            matches = [a for a in arts if a["name"].startswith(prefix) and not a["expired"]]
            if not matches:
                result[prefix] = {"status": "no unexpired artifact"}
                continue
            art = max(matches, key=lambda a: a["created_at"])
            try:
                blob = run([GH, "api", f"repos/{self.org_repo}/actions/artifacts/{art['id']}/zip"])
            except RuntimeError as exc:
                result[prefix] = {"status": f"download failed: {exc}"[:200]}
                continue
            buckets: Counter[str] = Counter()
            copyleft: list[dict[str, Any]] = []
            components = 0
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                for name in zf.namelist():
                    if not name.endswith(".json") or "spdx" not in name.lower():
                        continue
                    data = json.loads(zf.read(name))
                    for pkg in data.get("packages", []):
                        lic = next(
                            (
                                v
                                for v in (pkg.get("licenseConcluded"), pkg.get("licenseDeclared"))
                                if v and v not in ("NOASSERTION", "NONE")
                            ),
                            None,
                        )
                        b = bucket_license(lic)
                        buckets[b] += 1
                        components += 1
                        if b in ("strong-copyleft", "weak-copyleft"):
                            copyleft.append(
                                {
                                    "name": pkg.get("name"),
                                    "version": pkg.get("versionInfo"),
                                    "license": lic,
                                }
                            )
            result[prefix] = {
                "artifact": art["name"],
                "created_at": art["created_at"],
                "components": components,
                "license_buckets": dict(buckets),
                "copyleft_components": copyleft,
                "note": "SBOM of the built container image: includes the base image's operating-"
                "system packages, which are not linked into the Company's code",
            }
        return result

    def github(self) -> dict[str, Any] | None:
        if self.offline:
            return None
        try:
            d = gh_json(f"repos/{self.org_repo}")
        except RuntimeError as exc:
            self.notes.append(f"gh api failed: {exc}"[:200])
            return None
        return {
            "private": d.get("private"),
            "visibility": d.get("visibility"),
            "created_at": (d.get("created_at") or "")[:10],
            "pushed_at": (d.get("pushed_at") or "")[:10],
            "default_branch": d.get("default_branch"),
            "size_kb": d.get("size"),
            "license_spdx": (d.get("license") or {}).get("spdx_id"),
            "description": d.get("description"),
        }

    # -- assemble -----------------------------------------------------------------------

    def collect(self, owner: str) -> dict[str, Any]:
        row: dict[str, Any] = {
            "key": self.key,
            "product": self.cfg["product"],
            "role": self.role,
            "org_repo": self.org_repo,
            "asset": self.cfg.get("asset"),
            "copyright_owner": owner,
            "license": self.cfg.get("license"),
            "description": self.cfg.get("description"),
            "third_party": list(self.cfg.get("third_party", [])),
            "generated_note": self.cfg.get("generated_note"),
        }
        row["github"] = self.github()
        if self.role == "mention":
            row["notes"] = self.notes
            return row
        if not self.locate():
            row["measured"] = False
            row["notes"] = self.notes
            return row
        assert self.path is not None
        ref = self.resolve_ref()
        log(f"{self.key}: measuring {ref} in {self.path}")
        row["measured"] = True
        row["ref"] = ref
        row["local_path"] = str(self.path)
        row.update(self.history(ref))
        row["code"] = self.measure_code(ref)
        row["contract"] = self.contract_counts(ref)
        row["dependencies"] = self.manifests(ref, self.tree(ref))
        row["sbom"] = self.sbom()
        row["notes"] = self.notes
        return row


# --------------------------------------------------------------------------------------
# Registries and domains
# --------------------------------------------------------------------------------------


def package_record(pkg: dict[str, Any]) -> dict[str, Any]:
    row = dict(pkg)
    try:
        if pkg["registry"] == "pypi":
            d = http_json(f"https://pypi.org/pypi/{pkg['name']}/json")
            info = d["info"]
            uploads = [
                f["upload_time_iso_8601"][:10] for files in d["releases"].values() for f in files
            ]
            row.update(
                {
                    "latest": info.get("version"),
                    "license": pypi_license(info),
                    "first_published": min(uploads) if uploads else None,
                    "releases": sum(1 for files in d["releases"].values() if files),
                    "url": f"https://pypi.org/project/{pkg['name']}/",
                }
            )
        elif pkg["registry"] == "npm":
            d = http_json(f"https://registry.npmjs.org/{pkg['name']}")
            times = d.get("time", {})
            row.update(
                {
                    "latest": (d.get("dist-tags") or {}).get("latest"),
                    "license": d.get("license"),
                    "first_published": (times.get("created") or "")[:10] or None,
                    "releases": len(d.get("versions") or {}),
                    "url": f"https://www.npmjs.com/package/{pkg['name']}",
                }
            )
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        row["error"] = str(exc)[:200]
    return row


WHOIS_FIELDS = {
    # "Creation Date" is the registry record; the whois client's IANA preamble carries a
    # lower-case "created:" line for the TLD itself, which must never be matched.
    "created": re.compile(r"^\s*(?:Creation Date|Registered On):\s*(\S+)", re.M),
    "expires": re.compile(
        r"^\s*(?:Registry Expiry Date|Registrar Registration Expiration Date|Expiry Date):"
        r"\s*(\S+)",
        re.I | re.M,
    ),
    "registrar": re.compile(r"^\s*Registrar:\s*(.+?)\s*$", re.I | re.M),
    "registrant": re.compile(r"^\s*Registrant (?:Organization|Name):\s*(.+?)\s*$", re.I | re.M),
}


def domain_record(dom: dict[str, Any]) -> dict[str, Any]:
    row = dict(dom)
    try:
        text = run([WHOIS, dom["name"]], timeout=60).decode("utf-8", "replace")
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        row["error"] = str(exc)[:200]
        return row
    for field, rx in WHOIS_FIELDS.items():
        m = rx.search(text)
        if m:
            value = m.group(1)
            row[field] = value[:10] if field in ("created", "expires") else value
    statuses = re.findall(r"^\s*Domain Status:\s*(\S+)", text, re.I | re.M)
    if statuses:
        row["status"] = sorted(set(statuses))
    row["whois_checked"] = today()
    return row


def mark_evidence(
    mark: dict[str, Any],
    domains: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    repos: list[dict[str, Any]],
) -> dict[str, Any]:
    row = dict(mark)
    evidence: list[dict[str, str]] = []
    for d in domains:
        if d["name"] in mark.get("domains", []) and d.get("created") and not d.get("acquired"):
            # an acquired domain's creation date belongs to the prior holder, not to the mark
            evidence.append({"kind": "domain registered", "what": d["name"], "date": d["created"]})
    for p in packages:
        if p["name"] in mark.get("packages", []) and p.get("first_published"):
            evidence.append(
                {
                    "kind": f"{p['registry']} first release",
                    "what": p["name"],
                    "date": p["first_published"],
                }
            )
    for r in repos:
        if r["key"] in mark.get("repos", []):
            if r.get("first_commit"):
                evidence.append(
                    {"kind": "first commit", "what": r["org_repo"], "date": r["first_commit"]}
                )
            gh = r.get("github") or {}
            if gh.get("created_at"):
                evidence.append(
                    {"kind": "repository created", "what": r["org_repo"], "date": gh["created_at"]}
                )
    evidence.sort(key=lambda e: e["date"])
    row["evidence"] = evidence
    row["first_use_evidence"] = evidence[0]["date"] if evidence else None
    row["status"] = (
        "unregistered; common-law use" if mark.get("scope") == "core" else "unregistered; reserved"
    )
    return row


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--out", type=Path, required=True, help="where to write snapshot.json")
    ap.add_argument(
        "--offline", action="store_true", help="no network: no fetch, gh, registries, whois"
    )
    ap.add_argument(
        "--ref",
        choices=("origin", "head"),
        default="origin",
        help="count origin/<default> after a fetch (default) or the local HEAD",
    )
    ap.add_argument("--only", help="comma-separated repo keys to measure (others become mentions)")
    ap.add_argument(
        "--self",
        action="store_true",
        help="measure the checkout this script lives in for its own repository, ignoring "
        "the configured local path (hermetic tests, CI)",
    )
    args = ap.parse_args(argv)

    cfg = tomllib.loads(args.config.read_text(encoding="utf-8"))
    owner = cfg["issuer"]["owner"]
    only = set(args.only.split(",")) if args.only else None
    args.out.parent.mkdir(parents=True, exist_ok=True)
    clone_root = args.out.parent / ".clones"

    repos: list[dict[str, Any]] = []
    for rc in cfg["repos"]:
        if only is not None and rc["key"] not in only:
            continue
        repo = Repo(
            rc,
            cfg,
            offline=args.offline,
            ref_mode=args.ref,
            clone_root=clone_root,
            prefer_self=args.self,
        )
        repos.append(repo.collect(owner))

    packages = [] if args.offline else [package_record(p) for p in cfg.get("packages", [])]
    domains = [] if args.offline else [domain_record(d) for d in cfg.get("domains", [])]
    marks = [mark_evidence(m, domains, packages, repos) for m in cfg.get("marks", [])]

    # license lookups for direct dependencies (once per name)
    dep_licenses: dict[str, dict[str, str | None]] = {"pypi": {}, "npm": {}}
    if not args.offline:
        for r in repos:
            deps = r.get("dependencies") or {}
            for name in deps.get("python_direct", []):
                if name not in dep_licenses["pypi"]:
                    try:
                        dep_licenses["pypi"][name] = pypi_license(
                            http_json(f"https://pypi.org/pypi/{name}/json")["info"]
                        )
                    except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
                        dep_licenses["pypi"][name] = None
            for name in deps.get("javascript_direct", []):
                if name not in dep_licenses["npm"]:
                    try:
                        d = http_json(f"https://registry.npmjs.org/{name}")
                        lic = d.get("license")
                        dep_licenses["npm"][name] = (
                            lic if isinstance(lic, str) else (lic or {}).get("type")
                        )
                    except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
                        dep_licenses["npm"][name] = None
    for r in repos:
        deps = r.get("dependencies")
        if not deps:
            continue
        buckets: Counter[str] = Counter()
        flagged: list[dict[str, str | None]] = []
        for eco, key in (("pypi", "python_direct"), ("npm", "javascript_direct")):
            for name in deps[key]:
                if args.offline:
                    buckets["not looked up (offline)"] += 1
                    continue
                lic = dep_licenses[eco].get(name)
                b = bucket_license(lic)
                buckets[b] += 1
                if b in ("strong-copyleft", "weak-copyleft", "proprietary"):
                    flagged.append({"ecosystem": eco, "name": name, "license": lic, "bucket": b})
        deps["license_lookup"] = (
            "skipped: --offline (buckets and flags are not meaningful)"
            if args.offline
            else "PyPI JSON / npm registry at snapshot time"
        )
        deps["direct_count"] = len(deps["python_direct"]) + len(deps["javascript_direct"])
        deps["license_buckets"] = dict(buckets)
        deps["flagged"] = flagged
        deps["licenses"] = (
            {}
            if args.offline
            else {
                "pypi": {n: dep_licenses["pypi"].get(n) for n in deps["python_direct"]},
                "npm": {n: dep_licenses["npm"].get(n) for n in deps["javascript_direct"]},
            }
        )

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "generated_on": today(),
        "mode": {"offline": args.offline, "ref": args.ref, "only": sorted(only) if only else None},
        "issuer": cfg["issuer"],
        "identity": {"human": cfg["identity"]["human"]},
        "repos": repos,
        "packages": packages,
        "distributions": cfg.get("distributions", []),
        "domains": domains,
        "marks": marks,
        "trade_secrets": cfg.get("trade_secrets", []),
        "protection_measures": cfg.get("protection_measures", []),
        "inbound_licenses": cfg.get("inbound_licenses", []),
        "outbound_licenses": cfg.get("outbound_licenses", []),
        "cleanup_items": cfg.get("cleanup_items", []),
        "valuation_inputs": cfg.get("valuation", {}),
        "method": {
            "git": git(ROOT, "--version").strip(),
            "counting": "git ls-tree -r <ref> | git cat-file --batch; a line is a newline (wc -l); "
            "languages by extension per config; authored totals exclude generated and "
            "third-party prefixes and the global excluded directory names",
            "excluded_dirs": sorted(cfg["counting"]["exclude"]["dirs"]),
            "languages": cfg["counting"]["languages"],
            "mojo_tracked": "all tracked .mojo files at the commit, by top-level directory; equals "
            "scripts/count_mojo_loc.sh",
            "contributors": "git shortlog -sne --no-merges at the commit, mapped through "
            "config.identity",
            "registries": "PyPI JSON API, npm registry JSON, WHOIS via the system whois client",
        },
    }
    args.out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"wrote {args.out} ({len(repos)} repos, {len(packages)} packages, {len(domains)} domains)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
