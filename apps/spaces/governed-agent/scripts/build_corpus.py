#!/usr/bin/env python3
"""Build the REAL retrieval corpus for the governed-agent demo (local tool).

Fetches lead extracts of real English Wikipedia articles from curated,
high-recognition categories via the public MediaWiki API, plus an explicit
must-include list (the preset targets), and writes a versioned, vendored
JSON the Space loads offline at boot. Not deployed (scripts/ is excluded
from upload); the DATA FILE it writes is the artifact.

License: Wikipedia text is CC BY-SA 4.0. Redistribution requirement is
attribution — every doc carries its title + canonical URL, and the payload
carries the license + attribution strings (surfaced in the Space UI/README).

Determinism: category members are sampled with a fixed stride after a fixed
seed shuffle, so re-running produces the same corpus for the same category
membership. Fetched-at date and article pageids are recorded for audit.

    python scripts/build_corpus.py
"""

from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
OUT = Path(__file__).resolve().parent.parent / "data" / "corpus_wiki_mini.json"

UA = "algenta-governed-agent-corpus-builder/1.0 (https://huggingface.co/spaces/thyn-ai/algenta-governed-agent)"
SEED = 20260921

# Curated, recognizable topic lanes (engineers/scientists actually ask about
# these). (category, human label, sampled target)
CATEGORIES: list[tuple[str, str, int]] = [
    ("Category:Fluid dynamics", "fluid-dynamics", 950),
    ("Category:Machine learning", "machine-learning", 1000),
    ("Category:Artificial neural networks", "neural-networks", 550),
    ("Category:Spaceflight", "spaceflight", 950),
    ("Category:Molecular biology", "molecular-biology", 800),
    ("Category:Quantum mechanics", "quantum-mechanics", 850),
    ("Category:Thermodynamics", "thermodynamics", 600),
    ("Category:World War II", "world-war-ii", 800),
    ("Category:Ancient Rome", "ancient-rome", 650),
]

# Preset targets and other guaranteed-recognition anchors, fetched directly.
MUST_INCLUDE: list[str] = [
    "Kármán vortex street",
    "Transformer (deep learning)",
    "Attention Is All You Need",
    "Bernoulli's principle",
    "Reynolds number",
    "Voyager 1",
    "Apollo 11",
    "Photosynthesis",
    "CRISPR",
    "DNA",
    "Quantum entanglement",
    "Entropy",
    "Normandy landings",
    "Roman Empire",
    "Neural network (machine learning)",
]

MIN_EXTRACT_CHARS = 500
MAX_EXTRACT_CHARS = 2500
POLITE_DELAY_S = 0.25  # ~4 req/s, well under anon guidance


def _get(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — retry with backoff, then raise
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _category_page(category: str, limit: str, cont: dict[str, str], cmtype: str = "page") -> dict:
    return _get(
        {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmnamespace": "0" if cmtype == "page" else "14",
            "cmtype": cmtype,
            "cmlimit": limit,
            **cont,
        }
    )


def category_members(category: str, cap: int) -> list[str]:
    """Article titles in a category (namespace 0), 'List of …' pages skipped.

    Thin categories (mostly subcategories — e.g. Category:World War II) are
    backfilled from their subcategories, one level deep, in deterministic
    alphabetical order, until `cap` titles are gathered.
    """
    titles: list[str] = []
    subcats: list[str] = []
    cont: dict[str, str] = {}
    while len(titles) < cap:
        data = _category_page(category, "500", cont)
        for member in data.get("query", {}).get("categorymembers", []):
            title = member["title"]
            if title.startswith("List of ") or title.startswith("Lists of "):
                continue
            titles.append(title)
        if "continue" not in data:
            break
        cont = data["continue"]
        time.sleep(POLITE_DELAY_S)
    if len(titles) < cap:
        # gather subcategories (namespace 14) and backfill from them
        scont: dict[str, str] = {}
        while True:
            data = _get(
                {
                    "action": "query",
                    "list": "categorymembers",
                    "cmtitle": category,
                    "cmnamespace": "14",
                    "cmtype": "subcat",
                    "cmlimit": "500",
                    **scont,
                }
            )
            subcats.extend(m["title"] for m in data.get("query", {}).get("categorymembers", []))
            if "continue" not in data:
                break
            scont = data["continue"]
            time.sleep(POLITE_DELAY_S)
        for subcat in sorted(subcats):
            if len(titles) >= cap:
                break
            scont2: dict[str, str] = {}
            while len(titles) < cap:
                data = _category_page(subcat, "500", scont2)
                for member in data.get("query", {}).get("categorymembers", []):
                    title = member["title"]
                    if title.startswith("List of ") or title.startswith("Lists of "):
                        continue
                    titles.append(title)
                if "continue" not in data:
                    break
                scont2 = data["continue"]
                time.sleep(POLITE_DELAY_S)
    # dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:cap]


def fetch_extracts(titles: list[str]) -> dict[str, dict]:
    """pageid -> {title, extract, url} for the given titles (batches of 20)."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), 20):
        batch = titles[i : i + 20]
        data = _get(
            {
                "action": "query",
                "prop": "extracts|info",
                "exintro": "1",
                "explaintext": "1",
                "exlimit": "20",
                "inprop": "url",
                "titles": "|".join(batch),
                "redirects": "1",
            }
        )
        for page in data.get("query", {}).get("pages", []):
            extract = (page.get("extract") or "").strip()
            if len(extract) < MIN_EXTRACT_CHARS:
                continue
            out[str(page["pageid"])] = {
                "title": page["title"],
                "extract": extract[:MAX_EXTRACT_CHARS],
                "url": page.get("fullurl", ""),
            }
        time.sleep(POLITE_DELAY_S)
    return out


def main() -> int:
    rng = random.Random(SEED)
    docs: list[dict] = []
    seen: set[str] = set()

    for category, label, target in CATEGORIES:
        print(f"[{label}] listing {category} (cap {target * 2})…", flush=True)
        members = category_members(category, cap=target * 2)
        rng.shuffle(members)
        chosen = members[:target]
        print(f"[{label}] fetching extracts for {len(chosen)} articles…", flush=True)
        extracts = fetch_extracts(chosen)
        kept = 0
        for pageid, info in extracts.items():
            if pageid in seen:
                continue
            seen.add(pageid)
            docs.append(
                {
                    "id": f"W{pageid}",
                    "topic": label,
                    "title": info["title"],
                    "text": info["extract"],
                    "url": info["url"],
                }
            )
            kept += 1
        print(f"[{label}] kept {kept} (corpus now {len(docs)})", flush=True)

    print(f"[must-include] fetching {len(MUST_INCLUDE)} anchor articles…", flush=True)
    anchors = fetch_extracts(MUST_INCLUDE)
    for pageid, info in anchors.items():
        if pageid in seen:
            # already present via a category — still fine (deduped)
            continue
        seen.add(pageid)
        docs.append(
            {
                "id": f"W{pageid}",
                "topic": "anchor",
                "title": info["title"],
                "text": info["extract"],
                "url": info["url"],
            }
        )
    missing = [t for t in MUST_INCLUDE if not any(d["title"] == t for d in docs)]
    if missing:
        print("WARNING — anchor titles not resolved exactly:", missing)

    payload = {
        "provenance": (
            f"{len(docs)} REAL English Wikipedia lead-extract passages, fetched from the public "
            "MediaWiki API on 2026-09-21 from curated categories (fluid dynamics, machine learning, "
            "neural networks, spaceflight, molecular biology, quantum mechanics, thermodynamics, "
            "World War II, ancient Rome) plus anchor articles; deterministic stride sampling "
            f"(seed {SEED}); every passage carries its article title and canonical URL."
        ),
        "license": "CC BY-SA 4.0 — Wikipedia text; attribution required and provided per passage (title + URL)",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Wikipedia contributors (en.wikipedia.org), via the MediaWiki API",
        "fetched_at": "2026-09-21",
        "sampling_seed": SEED,
        "docs": docs,
        "queries": [
            {"text": "What is a Kármán vortex street?"},
            {"text": "What did the Transformer paper introduce?"},
            {"text": "How does photosynthesis work?"},
            {"text": "What was the Apollo 11 mission?"},
            {"text": "What is quantum entanglement?"},
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False))
    size_mb = OUT.stat().st_size / 1e6
    print(f"WROTE {OUT} — {len(docs)} docs, {size_mb:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
