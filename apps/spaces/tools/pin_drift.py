"""Pin discipline for the Spaces' requirements files.

Reads every ``*requirements*.txt`` under each Space directory and reports

* ``prerelease``  a version token such as ``.dev1``, ``rc2``, ``a1``, ``b3`` (also inside a
  direct wheel URL);
* ``unpinned``    a requirement without a single ``==`` clause;
* ``unhashed``    a pinned requirement without ``--hash`` when ``--require-hashes`` is on;
* ``drift``       the same package pinned to different versions across the given Spaces.

Direct wheel URLs count as pinned (the file name carries the exact version). Options lines
(``-r``, ``--index-url`` ...) and comments are skipped. Exit status is non-zero on findings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PRERELEASE_RE = re.compile(
    r"(?:^|[.\-_]|\d)(dev\d*|rc\d*|a\d+|b\d+|alpha\d*|beta\d*)(?=$|[.+\-_])", re.I
)
WHEEL_RE = re.compile(r"/(?P<name>[A-Za-z0-9_.]+?)-(?P<version>\d[A-Za-z0-9.+!]*)-[^/]*\.whl$")
SPEC_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*(?P<clauses>(?:[<>=!~]=?=?\s*[^,;\s]+\s*,?\s*)*)"
)
_SKIP_DIRS = frozenset({"tests", "__pycache__"})


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class Requirement:
    name: str
    version: str | None
    pinned: bool
    hashed: bool
    file: Path
    line: int
    raw: str

    @property
    def prerelease(self) -> bool:
        return bool(self.version and PRERELEASE_RE.search(self.version))


@dataclass(frozen=True)
class Finding:
    file: Path
    line: int
    code: str
    message: str

    def format(self, root: Path | None = None) -> str:
        shown = self.file
        if root is not None:
            try:
                shown = self.file.relative_to(root)
            except ValueError:
                shown = self.file
        return f"{shown}:{self.line}: [{self.code}] {self.message}"


def _logical_lines(text: str) -> list[tuple[int, str]]:
    """Join backslash continuations; returns (first physical line, joined text)."""
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    start = 0
    for i, physical in enumerate(text.splitlines(), start=1):
        stripped = physical.split(" #", 1)[0] if not physical.lstrip().startswith("#") else ""
        if not buf:
            start = i
        if stripped.rstrip().endswith("\\"):
            buf.append(stripped.rstrip()[:-1])
            continue
        buf.append(stripped)
        joined = " ".join(part.strip() for part in buf).strip()
        buf = []
        if joined:
            out.append((start, joined))
    if buf:
        joined = " ".join(part.strip() for part in buf).strip()
        if joined:
            out.append((start, joined))
    return out


def parse_line(file: Path, lineno: int, line: str) -> Requirement | None:
    if line.startswith("#"):
        return None
    tokens = line.split()
    hashed = any(t.startswith("--hash") for t in tokens)
    body = " ".join(t for t in tokens if not t.startswith("--hash") and not t.startswith("sha256:"))
    if body.startswith("-"):
        return None  # options: -r, -c, -e, -f, --index-url, --extra-index-url ...
    body = body.split(";", 1)[0].strip()
    if body.startswith(("http://", "https://", "file:")):
        m = WHEEL_RE.search(body)
        if not m:
            return Requirement(body, None, False, hashed, file, lineno, line)
        return Requirement(normalize(m["name"]), m["version"], True, hashed, file, lineno, line)
    if "@" in body:
        name = body.split("@", 1)[0].strip()
        return Requirement(normalize(name), None, False, hashed, file, lineno, line)
    m = SPEC_RE.match(body)
    if not m:
        return Requirement(body, None, False, hashed, file, lineno, line)
    clauses = [c.strip() for c in m["clauses"].split(",") if c.strip()]
    version = None
    pinned = False
    if len(clauses) == 1 and clauses[0].startswith("==") and not clauses[0].startswith("==="):
        version = clauses[0][2:].strip()
        pinned = not version.endswith(".*")
    elif len(clauses) == 1 and clauses[0].startswith("==="):
        version = clauses[0][3:].strip()
        pinned = True
    return Requirement(normalize(m["name"]), version, pinned, hashed, file, lineno, line)


def parse_requirements(path: Path) -> list[Requirement]:
    reqs: list[Requirement] = []
    for lineno, line in _logical_lines(path.read_text(encoding="utf-8")):
        req = parse_line(path, lineno, line)
        if req is not None:
            reqs.append(req)
    return reqs


def requirement_files(space_dir: Path) -> list[Path]:
    files = []
    for p in sorted(Path(space_dir).rglob("*requirements*.txt")):
        rel = p.relative_to(space_dir)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        files.append(p)
    return files


def check_requirements(reqs: list[Requirement], *, require_hashes: bool) -> list[Finding]:
    out: list[Finding] = []
    for r in reqs:
        if r.prerelease:
            out.append(
                Finding(r.file, r.line, "prerelease", f"{r.name} {r.version} is a pre-release")
            )
        if not r.pinned:
            out.append(Finding(r.file, r.line, "unpinned", f"{r.name}: no exact == pin ({r.raw})"))
        elif require_hashes and not r.hashed:
            out.append(Finding(r.file, r.line, "unhashed", f"{r.name}=={r.version} lacks --hash"))
    return out


def drift(reqs: list[Requirement]) -> list[Finding]:
    by_name: dict[str, dict[str, list[Requirement]]] = {}
    for r in reqs:
        if r.pinned and r.version:
            by_name.setdefault(r.name, {}).setdefault(r.version, []).append(r)
    out: list[Finding] = []
    for name, versions in sorted(by_name.items()):
        if len(versions) < 2:
            continue
        summary = " vs ".join(
            f"{v} ({', '.join(str(x.file.name) for x in xs)})" for v, xs in sorted(versions.items())
        )
        for _, xs in sorted(versions.items()):
            for r in xs:
                out.append(Finding(r.file, r.line, "drift", f"{name}: {summary}"))
    return out


def check_spaces(space_dirs: list[Path], *, require_hashes: bool = False) -> list[Finding]:
    all_reqs: list[Requirement] = []
    findings: list[Finding] = []
    for d in space_dirs:
        for f in requirement_files(Path(d)):
            reqs = parse_requirements(f)
            all_reqs.extend(reqs)
            findings.extend(check_requirements(reqs, require_hashes=require_hashes))
    findings.extend(drift(all_reqs))
    return sorted(set(findings), key=lambda f: (str(f.file), f.line, f.code, f.message))


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="check requirement pins across Space directories")
    ap.add_argument("dirs", nargs="+", type=Path)
    ap.add_argument("--require-hashes", action="store_true", help="every pin needs --hash")
    a = ap.parse_args(argv)
    findings = check_spaces(a.dirs, require_hashes=a.require_hashes)
    for f in findings:
        print(f.format(Path.cwd()))
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.code] = counts.get(f.code, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "clean"
    print(f"{len(findings)} finding(s) ({summary})")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
