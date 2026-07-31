#!/usr/bin/env python3
"""Docs audit — enforces the shared interaction contract in CI (GitBook allows no custom code, so
the repo guards quality). Run for every product docs repo.

    python3 gitbook/audit.py docs/            # exits non-zero if any ERROR

Severity: ERROR (broken link, malformed block, missing required frontmatter, bad H1) ·
WARNING (missing next action, untitled code block, oversized description, task w/o expected result,
index w/o cards) · ADVISORY (placeholder drift, duplicate headings, long paragraph, too many
equal-weight cards). Archetype per page comes from gitbook/archetypes.json (path -> archetype);
unlisted pages default to "guide".
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLACEHOLDER_OK = re.compile(r"\$[A-Z][A-Z0-9_]+")  # $ALGENTA_API_KEY convention
# real placeholder drift only — NOT HTML tags like <details>/<tr>/<a>
PLACEHOLDER_BAD = re.compile(r"YOUR_[A-Z][A-Z0-9_]*|<[a-z][a-z0-9_-]*(?:token|key|secret|id|path|url|name)>", re.I)
BLOCK_PAIRS = [("{% tabs %}", "{% endtabs %}"), ("{% stepper %}", "{% endstepper %}"),
               ("{% step %}", "{% endstep %}"), ("<details>", "</details>")]


def _strip_fences(text: str):
    """Yield (line, in_fence) so checks can ignore fenced code."""
    infence = False
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            infence = not infence
            yield ln, True
            continue
        yield ln, infence


def audit_page(path: str, archetype: str, all_paths: set) -> list:
    text = open(path).read()
    issues = []
    def err(m): issues.append(("ERROR", m))
    def warn(m): issues.append(("WARNING", m))
    def adv(m): issues.append(("ADVISORY", m))

    # frontmatter
    fm = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        block = text[4:end] if end > 0 else ""
        for line in block.splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1); fm[k.strip()] = v.strip()
    if "icon" not in fm:
        err("missing frontmatter: icon")
    if "description" not in fm:
        err("missing frontmatter: description")
    elif len(fm["description"]) > 200:
        warn(f"description >200 chars ({len(fm['description'])})")

    # one real H1 + duplicate headings
    h1 = 0; headings = []
    for ln, infence in _strip_fences(text):
        if infence:
            continue
        if re.match(r"^# ", ln):
            h1 += 1
        m = re.match(r"^(#{1,6}) (.+)", ln)
        if m:
            headings.append(m.group(2).strip().lower())
    if h1 != 1:
        err(f"expected exactly 1 H1, found {h1}")
    dupes = {h for h in headings if headings.count(h) > 1}
    if dupes:
        adv(f"duplicate headings: {sorted(dupes)}")

    # balanced GitBook blocks
    for open_t, close_t in BLOCK_PAIRS:
        o = text.count(open_t); c = text.count(close_t)
        if o != c:
            err(f"unbalanced block {open_t!r}/{close_t!r}: {o} vs {c}")
    o_tab = text.count("{% tab "); c_tab = text.count("{% endtab %}")
    if o_tab != c_tab:
        err(f"unbalanced {{% tab %}}: {o_tab} vs {c_tab}")
    o_hint = len(re.findall(r"{% hint", text)); c_hint = text.count("{% endhint %}")
    if o_hint != c_hint:
        err(f"unbalanced hint: {o_hint} vs {c_hint}")
    # no <details>/stepper nested inside a stepper step
    for m in re.finditer(r"{% stepper %}(.*?){% endstepper %}", text, re.S):
        if "<details>" in m.group(1) or "{% stepper %}" in m.group(1):
            err("expandable or nested stepper inside a stepper step")

    # internal links resolve
    base = os.path.dirname(path)
    for m in re.finditer(r"\]\((?!https?:|#|mailto:)([^)#]+\.md)(#[^)]*)?\)", text):
        target = os.path.normpath(os.path.join(base, m.group(1)))
        if target not in all_paths:
            err(f"broken internal link: {m.group(1)}")

    # untitled fenced code blocks — flag only OPENING fences with no language (track open/close)
    infence = False
    for ln in text.splitlines():
        s = ln.lstrip()
        if s.startswith("```"):
            if not infence:
                if not s[3:].strip():
                    warn("fenced code block without a language/title");
                infence = True
            else:
                infence = False

    # placeholder consistency
    if PLACEHOLDER_BAD.search(text):
        adv("placeholder drift: use the $ALGENTA_API_KEY convention, not <token>/YOUR_TOKEN")

    # too many equal-weight cards in a SINGLE grid (grouped tables are fine)
    maxrows = 0
    for tbl in re.findall(r'<table data-view="cards">(.*?)</table>', text, re.S):
        body = tbl.split("</thead>")[-1]
        maxrows = max(maxrows, body.count("<tr>"))
    if archetype == "landing" and maxrows > 6:
        adv("a single landing card grid has >6 choices; group by outcome")

    # archetype-specific
    # "See also" and "Related" are next actions too. The rule is zero-dead-end — a page must not
    # leave the reader with nowhere to go — and a heading full of onward links satisfies that whatever
    # it is called. Omitting them flagged six pages that each end in a list of links, which trains
    # authors to ignore the warning rather than fix real dead ends.
    has_next = bool(
        re.search(
            r"(?im)^#{2,3}\s*(next|next steps|where to go|what.s next|see also|related)\b", text
        )
    ) or "content-ref" in text or text.lower().count("next:") > 0
    has_cards = 'data-view="cards"' in text or "{% content-ref" in text
    outline_off = re.search(r"outline:\s*\n?\s*(visible:\s*false|\{[^}]*visible:\s*false)", text) \
        or re.search(r"outline:\s*\{?\s*visible:\s*false", text)
    if archetype == "landing":
        if not outline_off:
            warn("landing page should hide the outline (layout.outline.visible: false)")
        if not has_cards:
            warn("landing page has no navigation cards")
    elif archetype == "reference":
        if outline_off:
            warn("reference page should KEEP the outline visible")
    elif archetype == "index":
        if not has_cards:
            warn("section index has no navigation cards")
        if not has_next:
            pass
    else:  # guide / task / concept / integration / troubleshooting => zero-dead-end
        if not has_next:
            warn("non-reference page ends without a next action (zero-dead-end rule)")
        if archetype == "task" and not re.search(r"(?i)expected result|you.ll see|expected output", text):
            warn("task guide missing an 'Expected result' for its actions")
    return issues


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "docs"
    arche_path = os.path.join(HERE, "archetypes.json")
    archetypes = json.load(open(arche_path)) if os.path.exists(arche_path) else {}
    md_files = []
    for dp, _, fns in os.walk(root):
        for fn in fns:
            if fn.endswith(".md"):
                md_files.append(os.path.normpath(os.path.join(dp, fn)))
    all_paths = set(md_files)
    counts = {"ERROR": 0, "WARNING": 0, "ADVISORY": 0}
    for p in sorted(md_files):
        rel = os.path.relpath(p, root)
        if os.path.basename(p) == "SUMMARY.md":
            continue
        arche = archetypes.get(rel, archetypes.get(p, "guide"))
        for sev, msg in audit_page(p, arche, all_paths):
            counts[sev] += 1
            print(f"  [{sev}] {rel} ({arche}): {msg}")
    print(f"\naudit: {counts['ERROR']} error(s), {counts['WARNING']} warning(s), {counts['ADVISORY']} advisory(ies) "
          f"across {len(md_files)} pages")
    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
