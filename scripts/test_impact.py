#!/usr/bin/env python3
"""Repo-aware test selection (test-impact analysis) — MVP.

Given a set of changed files (default: the diff `base...head`, default base
``origin/main``), compute which tests in ``tests/`` are (transitively) affected and
print a pytest-friendly selection. This is the local-intelligence capability Codna/Telys
expose, applied to CI: only run the tests a change can actually influence.

How it works
------------
1. Walk the repo's Python sources (``apps/``, ``packages/``, ``tests/``, ``scripts/``,
   ``integrations/``) and parse each with stdlib ``ast``. Build a module key for every file and
   record, per file, the set of module keys it imports (absolute + relative).
2. Reverse the graph: ``importers[M]`` = files that import module ``M``.
3. For each changed file, walk the reverse graph to its transitive importers. Any ``tests/``
   file in that closure is "affected". A changed file that IS itself a test is affected directly.
4. Conservative fallbacks (return the FULL suite, exit 0): a changed file we could not place in the
   graph, a changed file imported by a very large share of the graph (a shared core module — running
   "its tests" == running everything), or any non-Python change outside a safe allowlist (config,
   CI, infra can affect anything).
5. Codna-backed intelligence (preferred, degrades gracefully). Resolution order: an explicit
   ``--codna-cli <path>`` (or ``CODNA_CLI``) pins a specific codna checkout; otherwise the
   INSTALLED ``codna`` wheel is used. With codna 0.1.48+ the whole selection decision is delegated
   to the productized ``codna.impact`` engine (same conservative bias, tighter closure); with
   seam-only codna (0.1.47) changed files are classified through Codna's extractor registry: when
   EVERY changed file is source in a known non-Python language and none of them is a test in that
   language, this (Python) suite has nothing that can execute them -> select nothing instead of the
   full suite. Without codna the behavior is exactly the conservative local fallback above.
6. Telys/memengine lexical enrichment (additive-only, opt-in via ``ALGENTA_REPOSITORIES_LEXICAL_
   RANKING`` — the same flag apps/api_server/services/repository_intelligence_lexical.py already
   uses). The import graph above is precise for direct imports but blind to "soft" references —
   string-based dynamic dispatch, a symbol referenced only in a docstring/config/prompt-template.
   An on-device BM25 index (Telys' ``LexicalCodeIndex``, zero-model, no network) over every file's
   path+symbol-name text, queried with the changed files' own symbol names, can surface test files
   the import graph structurally cannot see — those hits are UNIONED into the selection, never used
   to narrow it. Degrades to a no-op whenever ``memengine`` is unavailable or the flag is unset.

Deliberate bias: when in doubt, run MORE tests, never fewer. A false "affected" costs minutes; a
false "unaffected" ships a regression.

Usage
-----
    python scripts/test_impact.py                      # origin/main...HEAD
    python scripts/test_impact.py --base origin/main --head HEAD
    python scripts/test_impact.py --changed a.py b.py  # explicit changed files
    python scripts/test_impact.py --json               # machine-readable
    python scripts/test_impact.py --codna-cli ~/dev/codna/cli   # multi-language awareness

Output (default): one test path per line (pytest args). If the whole suite is required, prints the
sentinel ``ALL`` and exits 0. ``--json`` emits ``{"mode": "subset"|"all", "tests": [...],
"reason": "..."}``.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import importlib.util
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_TEST_DIR = "tests"

# Changed paths matching any of these are treated as "affects everything" (config/CI/infra/shared).
_BROAD_GLOBS = (
    "pyproject.toml", "setup.py", "setup.cfg", "conftest.py", "**/conftest.py",
    ".github/**", "requirements*.txt", "**/requirements*.txt", "pixi.toml", "**/pixi.toml",
    "pytest.ini", "tox.ini", "scripts/**", "infra/**", ".env*",
)

# If a single changed module is imported (transitively) by more than this fraction of all test files,
# treat it as shared-core and just run everything.
_SHARED_CORE_FRACTION = 0.34

# Ignore these when walking sources (mirrors codna.codeunits._DEFAULT_IGNORE).
_IGNORE_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".codna-memory",
    "mojo_env", "mma_forge", "mojo_build", "build", "vendor", "node_modules",
}


def _iter_py_files() -> list[Path]:
    """Walk the WHOLE repo for .py files, minus ``_IGNORE_DIRS`` — no hardcoded source-dir
    allowlist. This mirrors codna.impact's own ``_iter_py_files`` so the fallback graph works on
    any repo shape (``src/``, ``lib/``, a flat layout, ...), not just this repo's ``apps/``/
    ``packages/`` convention."""
    out: list[Path] = []
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.endswith(".py"):
                out.append(Path(root) / fn)
    return out


def _rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def _module_key(rel_path: str) -> str | None:
    """Map a repo-relative .py path to a dotted module key, or None if unmappable."""
    if not rel_path.endswith(".py"):
        return None
    parts = Path(rel_path).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return None
    return ".".join(parts)


def _candidate_keys(rel_path: str) -> list[str]:
    """Every dotted name this file may be imported as. The path-based key (repo-root relative) is
    always one. Additionally, for EVERY ancestor directory that is a real package (has
    ``__init__.py`` on disk), the path from that ancestor onward is also a candidate — the form
    tests actually use (``from algenta.inference import ...``, not
    ``from packages.algenta.algenta...``). Derived from the tree (any ancestor with an
    ``__init__.py`` qualifies), not hardcoded to this repo's ``packages/<vendor>/<name>/...``
    convention specifically — a repo using ``src/``, ``libs/``, or a flat layout gets the same
    alias resolution for free."""
    keys: list[str] = []
    primary = _module_key(rel_path)
    if primary:
        keys.append(primary)
    parts = Path(rel_path).with_suffix("").parts
    for i in range(1, len(parts)):
        ancestor = Path(*parts[:i])
        if (REPO_ROOT / ancestor / "__init__.py").is_file():
            inner = parts[i - 1 :]
            if inner and inner[-1] == "__init__":
                inner = inner[:-1]
            if inner:
                alias = ".".join(inner)
                if alias not in keys:
                    keys.append(alias)
    return keys


def _import_targets(tree: ast.AST, file_rel: str) -> set[str]:
    """Collect the dotted module keys this file imports (absolute + relative). Best-effort: an
    unresolvable/relative import yields a best-guess key so the graph stays connected."""
    targets: set[str] = set()
    file_mod = _module_key(file_rel) or ""
    file_pkg_parts = file_mod.split(".")[:-1] if file_mod else []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                targets.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import: resolve against the importing file's package.
                base_parts = file_pkg_parts[: len(file_pkg_parts) - (node.level - 1)]
                base = ".".join(base_parts + ([node.module] if node.module else []))
                if base:
                    targets.add(base)
            elif node.module:
                targets.add(node.module)
    return targets


def _build_graph(py_files: list[Path]):
    """Return (file_by_module, importers, file_imports). file_by_module maps a module key to the
    file that defines it (first match wins). importers[M] = set of files importing module M."""
    file_by_module: dict[str, Path] = {}
    file_imports: dict[str, set[str]] = {}
    trees: dict[str, ast.AST] = {}
    for p in py_files:
        rel = _rel(p)
        for key in _candidate_keys(rel):
            if key not in file_by_module:
                file_by_module[key] = p
        try:
            trees[rel] = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            trees[rel] = None  # unparseable -> treat as opaque; callers fall back conservatively
    for rel, tree in trees.items():
        if tree is None:
            file_imports[rel] = set()  # opaque: handled as broad by the caller
            continue
        file_imports[rel] = _import_targets(tree, rel)
    importers: dict[str, set[str]] = defaultdict(set)
    for rel, targets in file_imports.items():
        for t in targets:
            # A target may name a module or a submodule; register it and every prefix so a change to
            # a package's __init__ or a submodule reaches importers of the parent too.
            importers[t].add(rel)
            parts = t.split(".")
            for i in range(1, len(parts)):
                importers[".".join(parts[:i])].add(rel)
    return file_by_module, importers, file_imports, trees


def _changed_from_git(base: str, head: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"git diff failed: {out.stderr.strip()}")
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def _is_test(rel: str) -> bool:
    parts = Path(rel).parts
    if not parts:
        return False
    if parts[0] != _TEST_DIR:
        return False
    name = parts[-1]
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def _is_broad(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, g) for g in _BROAD_GLOBS)


_CODNA_CACHE: dict[str, object | None] = {}
_CODNA_ALIAS: dict[str, str] = {}


def _installed_codna():
    """The installed ``codna`` wheel, if it carries the per-file seam (thyn-ai/codna#445).

    Returns ``(codeunits, impact_fn)`` — ``impact_fn`` is ``codna.impact.compute_impact`` when the
    wheel also carries the productized engine (thyn-ai/codna#446, 0.1.48+), else None. Never fatal:
    selection must run anywhere codna is absent or stale."""
    try:
        from codna import codeunits
    except Exception:  # noqa: BLE001 — any import failure just disables the codna path
        return None, None
    if not (hasattr(codeunits, "language_for") and hasattr(codeunits, "extract_file")):
        return None, None  # predates the per-file seam — stay conservative
    try:
        from codna.impact import compute_impact
    except Exception:  # noqa: BLE001 — engine-less wheels still get the multi-language fast path
        return codeunits, None
    return codeunits, compute_impact


def _load_codna(cli_path: str | None):
    """Load codna.codeunits from an explicit checkout, without disturbing this process's imports.

    Loads under a private module alias so that (a) an installed ``codna`` release — which may
    predate the per-file seam — can never shadow the requested checkout, and (b) the checkout's
    vendored siblings (e.g. its ``memengine/``) never leak onto sys.path for other importers.
    Never fatal: selection must run anywhere codna is absent."""
    path = cli_path or os.environ.get("CODNA_CLI")
    if not path:
        return None
    pkg_dir = Path(path).expanduser().resolve() / "codna"
    key = str(pkg_dir)
    if key in _CODNA_CACHE:
        return _CODNA_CACHE[key]
    if not (pkg_dir / "codeunits.py").is_file() or not (pkg_dir / "__init__.py").is_file():
        _CODNA_CACHE[key] = None
        return None
    alias = f"_test_impact_codna_{len(_CODNA_CACHE)}"
    try:
        spec = importlib.util.spec_from_file_location(
            alias, str(pkg_dir / "__init__.py"),
            submodule_search_locations=[str(pkg_dir)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[alias] = pkg
        spec.loader.exec_module(pkg)
        codeunits = importlib.import_module(f"{alias}.codeunits")
    except Exception:  # noqa: BLE001 — any import failure just disables the codna path
        sys.modules.pop(alias, None)
        _CODNA_CACHE[key] = None
        return None
    if not (hasattr(codeunits, "language_for") and hasattr(codeunits, "extract_file")):
        codeunits = None  # codna predates the per-file seam (thyn-ai/codna#445) — stay conservative
    else:
        _CODNA_ALIAS[key] = alias
    _CODNA_CACHE[key] = codeunits
    return codeunits


def _load_codna_impact(cli_path: str | None):
    """The productized impact engine (thyn-ai/codna#446) from the SAME explicit checkout loaded by
    ``_load_codna``, or None when the checkout predates it. Kept per-checkout so an explicit path
    never silently mixes with the installed wheel."""
    path = cli_path or os.environ.get("CODNA_CLI")
    if not path or _load_codna(cli_path) is None:
        return None
    alias = _CODNA_ALIAS.get(str(Path(path).expanduser().resolve() / "codna"))
    if not alias:
        return None
    try:
        impact = importlib.import_module(f"{alias}.impact")
    except Exception:  # noqa: BLE001 — pre-#446 checkout: the local graph below decides
        return None
    fn = getattr(impact, "compute_impact", None)
    return fn if callable(fn) else None


_LEXICAL_RANKING_ENV = "ALGENTA_REPOSITORIES_LEXICAL_RANKING"


def _lexical_ranking_enabled() -> bool:
    """Mirrors apps/api_server/services/repository_intelligence_lexical.py::lexical_ranking_enabled
    — same env var, same default-off. Duplicated rather than imported: this is a standalone
    script (also runnable from a bare CI checkout via run_repo_python.sh), and importing across
    the scripts/ -> apps/ boundary just to read one flag would make it depend on the whole apps
    package chain for no reason."""
    return os.environ.get(_LEXICAL_RANKING_ENV, "false").strip().lower() in {"1", "true", "yes", "on"}


def _file_symbols(tree: ast.AST) -> list[str]:
    """Function/class names defined in a parsed file — the "symbols" text the lexical index scores
    against, same shape as repository_intelligence_lexical.py's own snapshot_manifest symbols."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return names


def _path_literal_dependents(changed, test_files):
    """Tests that load a changed file BY PATH, which the AST import graph cannot see.

    Many tests here do:
        module_path = root / "benchmarks" / "algenta_connector_preview_benchmark.py"
        spec = importlib.util.spec_from_file_location("under_test", module_path)
    There is no import statement, so the module never appears in the dependency graph and the
    test is invisible to selection. 35 files in tests/ use this shape (also subprocess and
    open() against repo paths).

    This is not theoretical: on 2026-08-26 a change to the Azure CI orchestrator's own module
    broke all 4 tests in its inflight-release test file, and the PR merged GREEN because subset
    selection never picked that file. (Both files were deleted in the 2026-09-18 CI decommission
    wave, which is why the example above is a different one -- the incident is kept because it is
    the reason this lane exists, and the lane outlived the code that motivated it.) The
    telys/memengine lexical lane targets the same
    class of blind spot, but this lane deliberately keeps NO external dependency so it holds even
    where memengine is absent. (The lexical lane is no longer inert in CI: it installs offline
    from the committed vendor/wheels/ wheel and ci.yml sets the ranking flag on the selection
    step. Both lanes now run, independently.)

    Match rule: every path COMPONENT of a changed file must appear as a string literal in the
    test. `benchmarks/algenta_connector_preview_benchmark.py` -> {"benchmarks",
    "algenta_connector_preview_benchmark.py"}, both of which appear in that test. Component-wise
    (not substring) matching keeps it tight, and like every other lane here it only ever WIDENS
    the set.
    """
    changed_components = {}
    for c in changed:
        parts = [p for p in Path(c).parts if p not in (".", "..", "/")]
        if parts:
            changed_components[c] = set(parts)
    if not changed_components:
        return set()
    out = set()
    for t in test_files:
        try:
            src = (REPO_ROOT / t).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "spec_from_file_location" not in src and "subprocess" not in src and "read_text" not in src:
            continue  # cheap prefilter: only files that plausibly reach for a path
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        lits = {
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        if not lits:
            continue
        for comps in changed_components.values():
            if comps <= lits:
                out.add(t)
                break
    return out


def _lexical_enrichment(
    changed: list[str], trees: dict[str, ast.AST | None], test_files: list[str],
) -> tuple[set[str], int]:
    """Additive-only enrichment via Telys' on-device LexicalCodeIndex (same integration pattern as
    apps/api_server/services/repository_intelligence_lexical.py — BM25 over path+symbol-name text,
    on-device, zero-model). The AST import graph above is precise for direct imports but blind to
    "soft" references: string-based dynamic dispatch, a symbol referenced only by name in a
    config/docstring/prompt-template, a plugin looked up by convention rather than imported.
    Lexical similarity can catch some of what the import graph structurally cannot see.

    Returns (extra_test_files, corpus_size). extra_test_files is UNIONED into the caller's
    affected set, NEVER used to narrow it — matching this module's own stated bias (run MORE
    tests, never fewer). Returns (set(), 0) on any failure: ranking disabled, memengine not
    installed, or an empty corpus/query — behavior in every one of those cases is byte-identical
    to not calling this function at all."""
    if not _lexical_ranking_enabled():
        return set(), 0
    try:
        from memengine.lexical import LexicalCodeIndex
    except Exception:  # noqa: BLE001 — retrieval must never break selection; degrade to no-op
        return set(), 0

    ids: list[str] = []
    texts: list[str] = []
    for rel, tree in trees.items():
        if tree is None:
            continue
        symbols = " ".join(_file_symbols(tree))
        ids.append(rel)
        texts.append(f"{rel} {symbols}".strip())
    if not ids:
        return set(), 0

    query_terms: list[str] = []
    for c in changed:
        tree = trees.get(c)
        if tree is not None:
            query_terms.extend(_file_symbols(tree))
    query = " ".join(query_terms).strip()
    if not query:
        return set(), len(ids)

    try:
        index = LexicalCodeIndex().build(ids, texts)
        hits = index.search(query, k=min(10, len(ids)))
    except Exception:  # noqa: BLE001 — never let a retrieval hiccup fail selection
        return set(), len(ids)

    test_set = set(test_files)
    extra = {str(doc_id) for doc_id, _score in hits if str(doc_id) in test_set}
    return extra, len(ids)


def _language_disjoint_selection(changed: list[str], codeunits):
    """Codna-backed fast path: when every changed file is source in a known NON-Python language and
    none of them is a test in that language, no test in this (Python) suite can execute them.
    Returns (True, tests, reason) to short-circuit, or None to fall through to the Python graph.
    Any uncertainty (unknown extension, unreadable file, test unit present) falls through — the
    bias is run MORE, never fewer."""
    langs: dict[str, str | None] = {c: codeunits.language_for(c) for c in changed}
    if not all(langs.values()):
        return None  # at least one file codna cannot classify -> no disjoint claim
    if any(lang == "python" for lang in langs.values()):
        return None  # the Python import graph below decides
    for c in changed:
        try:
            source = (REPO_ROOT / c).read_text(encoding="utf-8", errors="replace")
            units = codeunits.extract_file("test-impact", c, source)
        except (OSError, SyntaxError, ValueError):
            return None  # unreadable/unparseable -> let the conservative path take over
        if any(u.symbol_type == "test" for u in units):
            return None  # a test changed in another language; this tool cannot select for it
    known = sorted(set(langs.values()))
    return (True, [],
            f"changes confined to non-Python languages ({', '.join(known)}); "
            "no test in this suite can execute them")


def lane_hits(changed: list[str], py_files: list[Path]) -> list[str]:
    """Tests the additive lanes flag for ``changed``, independent of the mode verdict.

    Exists for the ``mode == "all"`` case, which is the SAFE verdict but not the one CI can
    always afford: on a pull request the check graph runs the CURATED list for mode=all, not the
    full suite, so a BROAD change is tested LESS than a narrow one. Surfacing the lane hits lets
    the caller run curated UNION lanes and keep the cheap path without the blind spot.

    Not hypothetical. #902 changed scripts/run_js_test_suite.sh -- itself a broad glob, so
    compute_affected returned mode=all and never reached the lanes -- and the two tests that
    assert that script's contents by exact string were never run. It merged green and broke main
    (2 failed, 950 passed). The path-literal lane finds EXACTLY those two of 1019 test files, so
    this costs two test files, not a full suite.

    The path-literal lane is always on (no external dependency, no AST parse -- it only reads
    test sources). The lexical lane needs parsed trees, so it stays behind its existing flag and
    only pays for the parse when explicitly enabled."""
    test_files = sorted(_rel(p) for p in py_files if _is_test(_rel(p)))
    hits = _path_literal_dependents(changed, test_files)
    if _lexical_ranking_enabled():
        *_ignored, trees = _build_graph(py_files)
        extra, _corpus = _lexical_enrichment(changed, trees, test_files)
        hits = hits | extra
    return sorted(hits)


def _additive_lanes(
    affected: set[str], changed: list[str], trees: dict[str, ast.AST | None],
    test_files: list[str], n_tests: int, base_reason: str | None = None,
) -> tuple[str, list[str], str]:
    """Apply every additive-only enrichment lane to ``affected`` and format the subset verdict.

    Shared by BOTH selection paths — the local import graph and the codna-delegated engine — so
    neither can quietly ship without the lanes the other one gets. Runs after the callers' safety
    guards and only ever WIDENS ``affected``; it never re-triggers the shared-core guard
    retroactively, matching this module's "run more, never fewer" bias.

    ``base_reason`` (the delegated engine's own explanation) is preserved verbatim when no lane
    widened anything — that message says why the engine chose what it chose, which is strictly
    more informative than a bare count. It is replaced only once a lane actually adds a test, so
    the reason never claims a selection the lanes have since widened past.
    """
    widened = False
    # Path-literal lane (no external dependency, always on): catches tests that load a changed
    # file by PATH rather than importing it -- see _path_literal_dependents for the live
    # regression that motivated it.
    by_path = _path_literal_dependents(changed, test_files) - affected
    if by_path:
        affected = affected | by_path
        widened = True
        preview = ", ".join(sorted(by_path)[:3]) + ("..." if len(by_path) > 3 else "")
        # stderr, never stdout: stdout carries the --json contract and the newline-separated
        # test list that CI consumes.
        print(f"# path-literal lane added {len(by_path)} test(s): {preview}", file=sys.stderr)

    # Codna/Telys lexical enrichment (additive-only, opt-in): the import graph is precise for
    # direct imports but blind to "soft" references a lexical index over path+symbol text can
    # still catch.
    extra, _corpus_size = _lexical_enrichment(changed, trees, test_files)
    added = extra - affected
    if added:
        affected = affected | added
        preview = ", ".join(sorted(added)[:3]) + ("..." if len(added) > 3 else "")
        return "subset", sorted(affected), (
            f"{len(affected)}/{n_tests} tests affected "
            f"({len(added)} via lexical enrichment: {preview})"
        )
    if not widened and base_reason is not None:
        return "subset", sorted(affected), base_reason
    return "subset", sorted(affected), f"{len(affected)}/{n_tests} tests affected"


def compute_affected(changed: list[str], py_files: list[Path], codeunits=None, *, impact_fn=None):
    """Return (mode, tests, reason). mode in {"subset","all"}.

    When ``impact_fn`` (codna.impact.compute_impact) is available, the decision is delegated to the
    productized engine: same conservative bias, but its name-resolved closure keys avoid the
    importer-blowup this local graph over-selects on shared-ish modules (measured on this repo:
    inference.py change 173 -> 12 tests, package __init__ 173 -> 45 — the campaign-validated
    numbers from thyn-ai/codna#446). The local graph below remains the fallback for environments
    without a codna wheel."""
    if impact_fn is not None:
        res = impact_fn(REPO_ROOT, changed, codeunits=codeunits,
                        broad_globs=_BROAD_GLOBS,
                        shared_core_fraction=_SHARED_CORE_FRACTION,
                        ignore=tuple(_IGNORE_DIRS))
        if res.mode != "subset":
            return res.mode, res.tests, res.reason  # "all" is already maximal — nothing to widen.
        # The delegated engine replaces this module's LOCAL IMPORT GRAPH — not its additive lanes.
        # Returning `res` verbatim silently skipped both of them, which inverts the "run MORE,
        # never fewer" bias into a real coverage loss: measured on this repo, a change to
        # apps/api_server/services/repository_intelligence_lexical.py selected 1 test with codna
        # absent (found by the path-literal lane) and 0 with codna present.
        test_files = sorted(_rel(p) for p in py_files if _is_test(_rel(p)))
        # Only the lexical lane needs parsed trees, and parsing is the expensive part of
        # _build_graph — so keep the codna fast path genuinely fast whenever that lane is off.
        trees: dict[str, ast.AST | None] = {}
        if _lexical_ranking_enabled():
            *_ignored, trees = _build_graph(py_files)
        return _additive_lanes(set(res.tests), changed, trees, test_files,
                               len(test_files) or len(res.tests), res.reason)
    if not changed:
        return "all", [], "no changed files reported; running full suite to be safe"
    # Anything broad/config/CI-ish -> run everything.
    broad = [c for c in changed if _is_broad(c)]
    if broad:
        return "all", [], f"broad/config change touches: {', '.join(sorted(broad)[:5])}"

    # Codna-backed multi-language fast path (skips the Python graph entirely when it applies).
    if codeunits is not None:
        disjoint = _language_disjoint_selection(changed, codeunits)
        if disjoint is not None:
            _, tests, reason = disjoint
            return "subset", tests, reason

    file_by_module, importers, file_imports, trees = _build_graph(py_files)
    test_files = sorted(_rel(p) for p in py_files if _is_test(_rel(p)))
    n_tests = len(test_files)
    if n_tests == 0:
        return "all", [], "no test files discovered; running full suite"

    # Validate changed files; any file we can't place in the graph -> full suite.
    for c in changed:
        if not c.endswith(".py"):
            # A non-Python, non-broad change (docs, data) -> be safe, run all.
            return "all", [], f"non-Python change: {c}"
        if _module_key(c) is None:
            return "all", [], f"unmappable changed file: {c}"

    # Seed the importer-closure ONLY with non-test source modules. A changed TEST file only affects
    # itself (nothing meaningfully imports a test); propagating a test's module through the importer
    # graph blows up to a huge fraction of the suite (tests import each other / conftest heavily).
    affected: set[str] = set()
    changed_source_modules: set[str] = set()
    for c in changed:
        if _is_test(c):
            affected.add(c)
            continue
        for key in _candidate_keys(c):
            changed_source_modules.add(key)
            file_by_module.setdefault(key, REPO_ROOT / c)
    # Reverse-transitive closure over importers.
    visited: set[str] = set()
    frontier = set(changed_source_modules)
    while frontier:
        m = frontier.pop()
        if m in visited:
            continue
        visited.add(m)
        for importer_rel in importers.get(m, ()):
            if _is_test(importer_rel):
                affected.add(importer_rel)
                continue
            # Re-seed with EVERY candidate key of the importer, not just its primary path-based
            # key: an importer reached here may itself only ever be imported by one of its
            # aliases (e.g. `mypkg.util`, never `src.acme.mypkg.util`), and using only the
            # primary key silently dead-ends the walk right there — a real bug, not just a
            # genericity gap (seeding with only `_module_key` predates this fix).
            for im_key in _candidate_keys(importer_rel):
                if im_key not in visited:
                    frontier.add(im_key)
        # No unconditional climb to enclosing packages: package-hub nodes collect enormous
        # importer sets and blow straight through the shared-core guard (measured on this repo:
        # a package __init__ change went 173->45 tests before this fix, 173->12 after — matching
        # codna.impact's own campaign-validated fix for the same over-selection bug). Real
        # re-export paths are already covered by real edges: `from pkg import x` resolves to
        # pkg/__init__.py, and if that __init__ imports the changed module the chain completes
        # without any synthetic climb.

    # Shared-core guard: if the affected set covers a large share of all tests, just run all.
    if n_tests and len(affected) / n_tests >= _SHARED_CORE_FRACTION:
        return "all", [], (
            f"change reaches {len(affected)}/{n_tests} tests (>= {_SHARED_CORE_FRACTION:.0%}); "
            "treating as shared-core and running full suite"
        )
    # A changed .py file that the repo walk never reached (e.g. filtered by _IGNORE_DIRS, or
    # outside REPO_ROOT) has untracked importers -> under-count -> run the full suite to be safe.
    for c in changed:
        if c.endswith(".py") and c not in trees:
            return "all", [], f"changed file was not indexed by the repo walk: {c}"

    return _additive_lanes(affected, changed, trees, test_files, n_tests)


def main() -> int:
    ap = argparse.ArgumentParser(description="Repo-aware test selection (test-impact analysis)")
    ap.add_argument("--base", default="origin/main", help="diff base (default origin/main)")
    ap.add_argument("--head", default="HEAD", help="diff head (default HEAD)")
    ap.add_argument("--changed", nargs="*", default=None, help="explicit changed files (skips git)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--codna-cli", default=None,
                    help="codna checkout's cli/ dir (or CODNA_CLI env) for multi-language awareness")
    args = ap.parse_args()

    changed = args.changed if args.changed is not None else _changed_from_git(args.base, args.head)
    # Resolution order: an EXPLICIT checkout (--codna-cli / CODNA_CLI) always wins (that is the
    # pin-to-a-checkout escape hatch); otherwise PREFER the installed codna wheel, which since
    # 0.1.48 carries both the per-file seam (#445) and the productized impact engine (#446).
    if args.codna_cli or os.environ.get("CODNA_CLI"):
        codeunits = _load_codna(args.codna_cli)
        impact_fn = _load_codna_impact(args.codna_cli)
    else:
        codeunits, impact_fn = _installed_codna()
    py_files = _iter_py_files()
    mode, tests, reason = compute_affected(changed, py_files, codeunits, impact_fn=impact_fn)
    # `lanes` is advisory and only meaningful for mode=all: a caller that genuinely runs the FULL
    # suite can ignore it, but one that falls back to a curated list (which is what this repo's
    # check graph does on a PR) should run curated UNION lanes so a broad change is not tested
    # LESS than a narrow one. Computed only for mode=all -- in subset mode the lanes are already
    # folded into `tests` by _additive_lanes, and recomputing would double the work.
    lanes = lane_hits(changed, py_files) if mode == "all" and changed else []

    if args.json:
        print(json.dumps({"mode": mode, "tests": tests, "reason": reason, "lanes": lanes}))
    elif mode == "all":
        print("ALL")
        print(f"# reason: {reason}", file=sys.stderr)
        if lanes:
            print(f"# lanes flag {len(lanes)} test(s) a curated fallback would miss: "
                  f"{', '.join(lanes[:5])}", file=sys.stderr)
    else:
        for t in tests:
            print(t)
        print(f"# {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
