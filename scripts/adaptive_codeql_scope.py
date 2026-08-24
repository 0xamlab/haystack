#!/usr/bin/env python3
"""Adaptive (differential) CodeQL scoping driven by Codna repo-intelligence blast radius.

Computes, for one CodeQL language leg, whether the next analysis should be skipped, scoped
(differential), or run in full — and, for differential runs, emits a ready-to-use CodeQL config
whose ``paths:`` list is exactly the blast-radius closure of the change.

How it works
------------
1. Changed files: PR -> ``merge-base(origin/<base_ref>, HEAD)..HEAD`` (the history fetch is
   progressive and depth-capped); push -> ``event.before..event.after``; schedule /
   workflow_dispatch / unknown -> full scan, no diff work at all.
2. Blast radius: the changed files are expanded through the SAME reverse-import graph engine that
   ``scripts/test_impact.py`` uses for CI test selection (the local form of Codna's repo
   intelligence; this script imports that module, it never rebuilds the graph logic). For Python,
   the scope is the changed files plus every file that transitively imports them. For
   JavaScript/TypeScript and GitHub Actions there are no dependency edges in that engine, so the
   scope is exactly the changed files of that language.
3. Decision: ``skip`` when nothing in the diff is analyzable by the leg's language; ``differential``
   with the generated config when a bounded closure was computed; ``full`` otherwise.

Deliberate bias (same as test selection): when in doubt scan MORE, never less. Anything broad
(build/config/scan-infra changes), unmappable, unreadable, or too large a share of the tree forces
``full``. Full scans also remain the fixed contract for push, weekly schedule, and manual dispatch,
so alert coverage over the whole repository never depends on the heuristic.

Usage
-----
    python scripts/codna_adaptive_codeql_scope.py --language python
    python scripts/codna_adaptive_codeql_scope.py --language actions --changed .github/workflows/ci.yml
    python scripts/codna_adaptive_codeql_scope.py --language python --full

Output: one JSON object on stdout (``decision``, ``language``, ``scope_count``, ``reason``,
``config_path``). In GitHub Actions the same fields are also written to ``$GITHUB_OUTPUT``. The
generated differential config is written to ``--out-dir`` (default: ``$RUNNER_TEMP/codeql-scope``,
falling back to a temp dir) and never into the tracked tree.

Stdlib only — this must run on any self-hosted runner with nothing but a Python 3 interpreter.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

LANGUAGE_PYTHON = "python"
LANGUAGE_JAVASCRIPT = "javascript-typescript"
LANGUAGE_ACTIONS = "actions"
LANGUAGES = (LANGUAGE_PYTHON, LANGUAGE_JAVASCRIPT, LANGUAGE_ACTIONS)

DECISION_SKIP = "skip"
DECISION_DIFFERENTIAL = "differential"
DECISION_FULL = "full"

# Source suffixes the javascript-typescript leg analyzes.
_JS_SUFFIXES = frozenset({".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"})
# The actions leg analyzes workflow / composite-action YAML — the files the CodeQL actions
# extractor actually extracts. Other .github YAML (dependabot, FUNDING, labeler, ...) is NOT an
# extraction target: scoping a leg at such a file would build an empty database and fail the
# analysis, so those changes skip the leg instead.
_ACTIONS_SUFFIXES = frozenset({".yml", ".yaml"})
_ACTIONS_EXTRACTABLE_PREFIXES = (".github/workflows/", ".github/actions/")

# Per-leg extractable suffixes: the files the CodeQL extractor for the leg actually turns into an
# analyzed database. A scope containing NONE of these would build an empty database and fail the
# analysis, so such a change set is a SKIP ("nothing of this language changed"), never a
# differential — and dependency manifests / lockfiles / docs are not extraction targets at all.
_EXTRACTABLE_SUFFIXES = {
    LANGUAGE_PYTHON: frozenset({".py"}),
    LANGUAGE_JAVASCRIPT: _JS_SUFFIXES,
    LANGUAGE_ACTIONS: _ACTIONS_SUFFIXES,
}

# Scan-infrastructure changes force FULL for EVERY leg: they change how the scan itself behaves.
_GLOBAL_BROAD_GLOBS = (
    ".github/codeql/**",
    ".github/workflows/codeql.yml",
    "scripts/adaptive_codeql_scope.py",
    "scripts/test_impact.py",
)

# Differential scope size guards. Beyond these the differential run saves little and the full run
# is the honest answer.
_DEFAULT_MAX_SCOPE_FILES = 2000
_DEFAULT_SHARED_CORE_FRACTION = 0.40

# Progressive fetches (flag, commits) used to locate the PR merge-base on shallow clones. Bounded
# on purpose: on a cold runner this never triggers an unbounded history download, and a branch
# deeper than the cap degrades to a FULL scan instead of hanging the fleet. Full clones are never
# fetched with --depth (that would truncate them), they resolve merge-base directly.
_FETCH_STEPS = (("--depth", "200"), ("--deepen", "1000"), ("--deepen", "5000"))

_KEY_LINE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9_-]*):(?P<rest>.*)$")
_LIST_ITEM = re.compile(r"^\s+-\s+(?P<item>.*)$")
_MAP_ITEM = re.compile(r"^\s+(?P<key>[A-Za-z][A-Za-z0-9_-]*):(?P<rest>.*)$")


def _load_test_impact():
    """The Codna blast-radius engine this repo already runs for CI test selection.

    Loaded under a private module alias (never via sys.path) so a stale or absent ``scripts/``
    import state cannot shadow it. Returns None when the engine is unavailable — callers MUST then
    fall back to a full scan."""
    path = SCRIPT_DIR / "test_impact.py"
    if not path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_codeql_scope_test_impact", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:  # noqa: BLE001 — degradation must be graceful, never crash the scan gate
        return None
    for attr in ("_build_graph", "_iter_py_files", "_candidate_keys", "_module_key", "_rel",
                 "_SOURCE_DIRS"):
        if not hasattr(mod, attr):
            return None
    return mod


def _run_git(root: Path, *args: str) -> tuple[bool, str]:
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return out.returncode == 0, (out.stdout.strip() if out.returncode == 0 else out.stderr.strip())


def _changed_files_pull_request(root: Path, base_ref: str) -> tuple[list[str] | None, str]:
    """merge-base(base, HEAD)..HEAD with a progressive, depth-capped fetch on shallow clones.

    Returns (files, reason). files=None means the diff could not be established -> FULL."""
    base = base_ref.removeprefix("refs/heads/")
    ref = f"origin/{base}"
    ok, shallow = _run_git(root, "rev-parse", "--is-shallow-repository")
    is_shallow = ok and shallow == "true"
    merge_base, found = "", False
    if not is_shallow:
        found, merge_base = _run_git(root, "merge-base", ref, "HEAD")
    if not found:
        for flag, depth in _FETCH_STEPS:
            _run_git(root, "fetch", "--no-tags", "--quiet", flag, depth, "origin", base)
            found, merge_base = _run_git(root, "merge-base", ref, "HEAD")
            if found:
                break
    if not found:
        return None, (f"merge-base with {ref} not found within the fetch-depth cap; "
                      "full scan for safety")
    ok, diff = _run_git(root, "diff", "--name-only", f"{merge_base}..HEAD")
    if not ok:
        return None, f"git diff failed: {diff}"
    return [ln for ln in diff.splitlines() if ln.strip()], (
        f"diff {merge_base[:12]}..HEAD against {ref}")


def _changed_files_push(root: Path, event_path: str | None) -> tuple[list[str] | None, str]:
    """event.before..event.after for push events."""
    if not event_path or not Path(event_path).is_file():
        return None, "push event payload unavailable; full scan for safety"
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"push event payload unreadable ({exc}); full scan for safety"
    before, after = str(event.get("before") or ""), str(event.get("after") or "")
    if not before or set(before) == {"0"}:
        return None, "branch created by this push; full scan for safety"
    if not after or set(after) == {"0"}:
        return [], "branch deleted by this push; nothing to scan"
    ok, diff = _run_git(root, "diff", "--name-only", f"{before}..{after}")
    if not ok:
        _run_git(root, "fetch", "--no-tags", "--quiet", "--depth", "200", "origin", after)
        ok, diff = _run_git(root, "diff", "--name-only", f"{before}..{after}")
    if not ok:
        return None, f"git diff {before[:12]}..{after[:12]} failed: {diff}"
    return [ln for ln in diff.splitlines() if ln.strip()], f"diff {before[:12]}..{after[:12]}"


def _matches_any(path: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def _existing(root: Path, paths: list[str]) -> list[str]:
    # Deleted files cannot gain new alerts; keep the scope honest about what is on disk.
    return [p for p in paths if (root / p).is_file()]


def _python_scope(root: Path, changed: list[str], ti, *, max_files: int,
                  shared_core_fraction: float, paths_ignore: list[str]):
    """Blast-radius closure over the reverse-import graph. Returns (decision, paths, reason)."""
    py_changed = _existing(root, [c for c in changed if c.endswith(".py")])
    if not py_changed:
        return DECISION_SKIP, [], "no Python source files changed"

    py_files = ti._iter_py_files()
    file_by_module, importers, _file_imports, trees = ti._build_graph(py_files)

    for c in py_changed:
        if ti._module_key(c) is None:
            return DECISION_FULL, [], f"unmappable changed file: {c}"
        if c not in trees:
            return DECISION_FULL, [], f"changed file outside indexed source roots: {c}"

    # Reverse-transitive closure over importers, seeded by the changed modules. Same traversal
    # semantics as test_impact.compute_affected (including the stop-at-source-root parent rule),
    # but collecting EVERY importer file, not just tests — CodeQL needs the whole affected surface.
    seed_keys: set[str] = set()
    for c in py_changed:
        seed_keys.update(ti._candidate_keys(c))
        file_by_module.setdefault(c, root / c)
    closure_files: set[str] = set()
    visited: set[str] = set()
    frontier = set(seed_keys)
    source_roots = set(ti._SOURCE_DIRS)
    while frontier:
        m = frontier.pop()
        if m in visited:
            continue
        visited.add(m)
        for importer_rel in importers.get(m, ()):
            closure_files.add(importer_rel)
            im_key = ti._module_key(importer_rel)
            if im_key and im_key not in visited:
                frontier.add(im_key)
        parts = m.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            if parent.split(".")[0] in source_roots:
                continue
            frontier.add(parent)

    scope = {c for c in py_changed} | closure_files
    scope = {p for p in scope if not _matches_any(p, tuple(paths_ignore))}
    if len(scope) > max_files:
        return DECISION_FULL, [], (
            f"closure covers {len(scope)} files (> {max_files}); full scan is the honest scope")
    indexed = len(py_files)
    if indexed and len(scope) / indexed >= shared_core_fraction:
        return DECISION_FULL, [], (
            f"closure covers {len(scope)}/{indexed} Python files "
            f"(>= {shared_core_fraction:.0%}); shared-core change, full scan")
    return DECISION_DIFFERENTIAL, sorted(scope), (
        f"blast-radius closure of {len(py_changed)} changed file(s): {len(scope)} file(s) in scope")


def _javascript_scope(root: Path, changed: list[str], paths_ignore: list[str]):
    js_changed = _existing(root, [c for c in changed if Path(c).suffix.lower() in _JS_SUFFIXES])
    if not js_changed:
        return DECISION_SKIP, [], "no JavaScript/TypeScript source files changed"
    scope = [p for p in sorted(set(js_changed)) if not _matches_any(p, tuple(paths_ignore))]
    if not scope:
        return DECISION_SKIP, [], "changed JavaScript/TypeScript files are all paths-ignored"
    return DECISION_DIFFERENTIAL, scope, (
        f"{len(scope)} changed JavaScript/TypeScript file(s) in scope")


def _actions_scope(root: Path, changed: list[str]):
    act_changed = _existing(root, [
        c for c in changed
        if c.startswith(_ACTIONS_EXTRACTABLE_PREFIXES)
        and Path(c).suffix.lower() in _ACTIONS_SUFFIXES
    ])
    if not act_changed:
        return DECISION_SKIP, [], (
            "no extractable workflow/action YAML changed under .github/ "
            "(workflows and composite actions only)")
    return DECISION_DIFFERENTIAL, sorted(set(act_changed)), (
        f"{len(set(act_changed))} workflow/action file(s) in scope")


# ── static CodeQL config merge (YAML subset parser, stdlib only) ────────────────────────────────
# The static config is small and checked-in; this parses exactly the shapes codeql-config.yml uses
# (top-level scalars, block lists of scalars, one-level nested maps) and refuses anything else,
# which callers turn into a FULL scan rather than risking a wrong merge.


def _strip_scalar(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def parse_static_config(text: str) -> dict[str, object]:
    """Parse the restricted YAML subset used by codeql configs. Raises ValueError otherwise."""
    config: dict[str, object] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[:1] in (" ", "\t", "-"):
            raise ValueError(f"unexpected indented line outside a block: {line!r}")
        match = _KEY_LINE.match(line)
        if not match:
            raise ValueError(f"unsupported YAML construct: {line!r}")
        key, rest = match.group("key"), match.group("rest").strip()
        if rest and rest.startswith("#"):
            rest = ""
        if rest:
            if rest.startswith(("[", "{")) or rest in ("|", ">", "|-", ">-"):
                raise ValueError(f"unsupported scalar/flow syntax for key {key!r}: {line!r}")
            config[key] = _strip_scalar(rest)
            i += 1
            continue
        # Block collection: list of scalars OR one-level map.
        items_list: list[str] = []
        items_map: dict[str, str] = {}
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                i += 1
                continue
            if nxt[:1] not in (" ", "\t"):
                break
            list_match = _LIST_ITEM.match(nxt)
            map_match = _MAP_ITEM.match(nxt)
            if list_match and not items_map:
                items_list.append(_strip_scalar(list_match.group("item")))
            elif map_match and not items_list:
                value = map_match.group("rest").strip()
                if not value or value.startswith(("[", "{", "-", "|", ">")):
                    raise ValueError(f"unsupported nested value under {key!r}: {nxt!r}")
                items_map[map_match.group("key")] = _strip_scalar(value)
            else:
                raise ValueError(f"unsupported block content under {key!r}: {nxt!r}")
            i += 1
        if not items_list and not items_map:
            config[key] = None
        elif items_list:
            config[key] = items_list
        else:
            config[key] = items_map
    return config


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_merged_config(static: dict[str, object], scope: list[str], language: str) -> str:
    name = static.get("name")
    name = f"{name} — differential scope ({language})" if isinstance(name, str) else (
        f"Differential scope ({language})")
    out = [
        "# Generated by scripts/adaptive_codeql_scope.py — do not edit by hand.",
        "# Differential CodeQL scope: the blast-radius closure of the change. Full scans keep",
        "# using .github/codeql/codeql-config.yml.",
        f"name: {_yaml_quote(name)}",
        "paths:",
    ]
    out.extend(f"  - {_yaml_quote(p)}" for p in scope)
    for key in ("paths-ignore", "disable-default-queries"):
        if key in static and static[key] is not None:
            out.append(f"{key}:")
            out.extend(f"  - {_yaml_quote(str(item))}" for item in static[key])  # type: ignore[union-attr]
    for key in ("packs", "queries"):
        if isinstance(static.get(key), dict):
            out.append(f"{key}:")
            out.extend(f"  {k}: {_yaml_quote(str(v))}" for k, v in static[key].items())  # type: ignore[union-attr]
        elif isinstance(static.get(key), list):
            out.append(f"{key}:")
            out.extend(f"  - {_yaml_quote(str(item))}" for item in static[key])  # type: ignore[union-attr]
    return "\n".join(out) + "\n"


# ── driver ────────────────────────────────────────────────────────────────────────────────────────


def compute_scope(*, language: str, root: Path, changed: list[str], static_config_text: str,
                  max_files: int, shared_core_fraction: float) -> tuple[str, list[str], str]:
    """Shared entry point for tests and CLI. Returns (decision, scope_paths, reason)."""
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language: {language}")
    broad_global = sorted(c for c in changed if _matches_any(c, _GLOBAL_BROAD_GLOBS))
    if broad_global:
        return DECISION_FULL, [], (
            f"scan-infrastructure change: {', '.join(broad_global[:4])}")
    try:
        static = parse_static_config(static_config_text)
    except ValueError as exc:
        return DECISION_FULL, [], f"static CodeQL config unparseable ({exc}); full scan"
    unknown = set(static) - {"name", "paths-ignore", "paths", "disable-default-queries",
                             "packs", "queries"}
    if unknown:
        return DECISION_FULL, [], (
            f"static CodeQL config carries unsupported keys ({', '.join(sorted(unknown))}); "
            "full scan")
    paths_ignore = [str(p) for p in static.get("paths-ignore") or []]

    if language == LANGUAGE_PYTHON:
        ti = _load_test_impact()
        if ti is None:
            return DECISION_FULL, [], "blast-radius engine unavailable; full scan for safety"
        original_root = ti.REPO_ROOT
        ti.REPO_ROOT = root
        try:
            decision, scope, reason = _python_scope(
                root, changed, ti, max_files=max_files,
                shared_core_fraction=shared_core_fraction, paths_ignore=paths_ignore)
        finally:
            ti.REPO_ROOT = original_root
    elif language == LANGUAGE_JAVASCRIPT:
        decision, scope, reason = _javascript_scope(root, changed, paths_ignore)
    else:
        decision, scope, reason = _actions_scope(root, changed)

    if decision != DECISION_DIFFERENTIAL:
        return decision, scope, reason
    # Hard guard before any scoped run: every emitted path must be repo-relative (CodeQL matches
    # `paths:` against repository-relative URIs) and extractable by the leg's CodeQL extractor.
    # Zero extractable files => SKIP, never a differential with an empty database.
    suffixes = _EXTRACTABLE_SUFFIXES[language]
    clean: list[str] = []
    for p in scope:
        rel = p[2:] if p.startswith("./") else p
        if rel.startswith("/") or rel.startswith(".."):
            return DECISION_FULL, [], f"non-relative scope path: {p}; full scan for safety"
        if Path(rel).suffix.lower() in suffixes:
            clean.append(rel)
    if not clean:
        return DECISION_SKIP, [], (
            f"{reason}; closure contains no files the {language} extractor analyzes")
    return DECISION_DIFFERENTIAL, clean, reason


def _write_github_output(fields: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in fields.items():
            fh.write(f"{key}={' '.join(str(value).split())}\n")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Adaptive CodeQL scoping via Codna repo-intelligence blast radius")
    ap.add_argument("--language", required=True, choices=LANGUAGES)
    ap.add_argument("--repo-root", default=None, help="repository root (default: this checkout)")
    ap.add_argument("--changed", nargs="*", default=None,
                    help="explicit changed-file list (skips git; used by tests and local runs)")
    ap.add_argument("--event-type", default=None,
                    help="override GITHUB_EVENT_NAME (pull_request|push|schedule|workflow_dispatch)")
    ap.add_argument("--base-ref", default=None, help="PR base ref (default GITHUB_BASE_REF or main)")
    ap.add_argument("--full", action="store_true", help="force a full scan")
    ap.add_argument("--allow-push-diff", action="store_true",
                    help="let push events scope from event.before..event.after instead of "
                         "running full (the shipped workflow keeps push FULL for soundness)")
    ap.add_argument("--out-dir", default=None,
                    help="where to write the generated differential config")
    ap.add_argument("--max-files", type=int, default=_DEFAULT_MAX_SCOPE_FILES)
    ap.add_argument("--shared-core-fraction", type=float, default=_DEFAULT_SHARED_CORE_FRACTION)
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else SCRIPT_DIR.parent
    config_path = root / ".github" / "codeql" / "codeql-config.yml"
    try:
        static_config_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"decision": DECISION_FULL, "language": args.language, "scope_count": 0,
                          "reason": f"static CodeQL config unreadable ({exc})", "config_path": ""}))
        _write_github_output({"decision": DECISION_FULL, "config_path": "", "scope_count": "0",
                              "reason": "static CodeQL config unreadable"})
        return 0

    event = args.event_type or os.environ.get("GITHUB_EVENT_NAME", "")
    # Push stays a FULL scan in the shipped workflow (security soundness over saved minutes);
    # --allow-push-diff is the opt-in for the event.before..after computation.
    forced = (args.full or event in ("schedule", "workflow_dispatch")
              or (event == "push" and not args.allow_push_diff))
    reason = ""
    changed: list[str] | None = None
    if args.changed is not None:
        changed = list(args.changed)
    elif forced:
        reason = "full scan: forced" if args.full else f"full scan: {event or 'unknown'} event"
    elif event in ("", "pull_request"):
        changed, diff_reason = _changed_files_pull_request(
            root, args.base_ref or os.environ.get("GITHUB_BASE_REF", "main"))
        if changed is None:
            forced, reason = True, diff_reason
        else:
            reason = diff_reason
    elif event == "push":
        changed, diff_reason = _changed_files_push(root, os.environ.get("GITHUB_EVENT_PATH"))
        if changed is None:
            forced, reason = True, diff_reason
        else:
            reason = diff_reason
    else:
        forced, reason = True, f"full scan: {event} event"

    if forced or changed is None:
        decision, scope = DECISION_FULL, []
        if not reason:
            reason = "full scan"
    else:
        decision, scope, scope_reason = compute_scope(
            language=args.language, root=root, changed=changed,
            static_config_text=static_config_text, max_files=args.max_files,
            shared_core_fraction=args.shared_core_fraction)
        reason = f"{reason}; {scope_reason}"

    out_config = ""
    if decision == DECISION_DIFFERENTIAL:
        out_dir = Path(args.out_dir) if args.out_dir else Path(
            os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()) / "codeql-scope"
        out_dir.mkdir(parents=True, exist_ok=True)
        generated = out_dir / f"codeql-differential-{args.language.replace('/', '-')}.yml"
        static = parse_static_config(static_config_text)
        generated.write_text(render_merged_config(static, scope, args.language), encoding="utf-8")
        out_config = str(generated)

    print(json.dumps({"decision": decision, "language": args.language,
                      "scope_count": len(scope), "reason": reason, "config_path": out_config},
                     indent=None))
    if scope and len(scope) <= 50:
        for p in scope:
            print(f"  scope: {p}", file=sys.stderr)
    _write_github_output({"decision": decision, "config_path": out_config,
                          "scope_count": str(len(scope)), "reason": reason})
    return 0


if __name__ == "__main__":
    sys.exit(main())
