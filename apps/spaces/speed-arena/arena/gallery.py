"""Kernel gallery — all 35 public Mojo kernel packages.

Speedup claims are quoted from each package's own README in
thyn-ai/mojo-kernels (measured on the repo's Apple M4 Max bench machine,
median-of-5, correctness-gated — reproduce with the repo's benchmarks/).
Near-parity entries are shown honestly as such; the arena tab only races
duels with a decisive win.
"""

REPO = "https://github.com/thyn-ai/mojo-kernels"

# (package, accelerates, honest speedup per its README, source path)
GALLERY = [
    (
        "bm25-mojo",
        "rank_bm25 / bm25s (Python)",
        "149×–13,137× vs rank_bm25; 1.10×–1.95× vs bm25s",
        "python/bm25_mojo",
    ),
    ("cclib-mojo", "cclib electron-density grids", "72×–7,033×", "python/cclib_mojo"),
    ("pykalman-mojo", "pykalman Kalman filter", "182×–827×", "python/pykalman_mojo"),
    (
        "vol-mojo",
        "volatility3 hive walk + pool scan",
        "2,607× hive walk; 26× pool scan",
        "python/vol_mojo",
    ),
    ("pefile-mojo", "pefile checksum + imports", "300×–460×", "python/pefile_mojo"),
    ("oletools-mojo", "oletools VBA decompression", "up to 90× warm", "python/oletools_mojo"),
    (
        "pydicom-mojo",
        "pydicom RLE codec",
        "3.7–16.3× decode; 12.2–46.5× encode",
        "python/pydicom_mojo",
    ),
    ("motmetrics-mojo", "py-motmetrics", "37–48×", "python/motmetrics_mojo"),
    (
        "nuscenes-eval-mojo",
        "nuscenes-devkit DetectionEval",
        "6.2–7.0× warm; 13.8–68.5× cold",
        "python/nuscenes_eval_mojo",
    ),
    ("croniter-mojo", "croniter", "15–46×", "python/croniter_mojo"),
    ("ruptures-mojo", "ruptures", "2×–50×", "python/ruptures_mojo"),
    ("obspy-mojo", "ObsPy Konno-Ohmachi", "3.9–6.7× steady-state; up to 45×", "python/obspy_mojo"),
    ("elephant-mojo", "elephant surrogates", "218×–342×", "python/elephant_mojo"),
    ("metpy-mojo", "MetPy CAPE/CIN", "78× column; 156.6× on grids", "python/metpy_mojo"),
    (
        "uproot-branches-mojo",
        "uproot branch reads",
        "172.6× on the branch-read path",
        "python/uproot-branches_mojo",
    ),
    ("dynesty-mojo", "dynesty nested sampling", "4.3×–4.5×", "python/dynesty_mojo"),
    ("jsonschema-mojo", "jsonschema validation", "2.1×–23.6×", "python/jsonschema_mojo"),
    ("jsonpath-mojo", "jsonpath-ng", "28×–49×", "python/jsonpath_mojo"),
    ("sacrebleu-mojo", "sacrebleu BLEU", "~20× n-gram statistics", "python/sacrebleu_mojo"),
    ("langdetect-mojo", "langdetect", "~7×", "python/langdetect_mojo"),
    ("ta-mojo", "pandas-ta indicators", "1.8×–93×", "python/ta_mojo"),
    ("spatialmath-mojo", "spatialmath-python poses", "7.7×–843×", "python/spatialmath_mojo"),
    ("ase-mojo", "ASE neighbor lists", "~10×", "python/ase_mojo"),
    ("capa-mojo", "capa rule matching", "6×–8× match passes", "python/capa_mojo"),
    ("pymavlink-mojo", "pymavlink tlog decode", "3×–6×", "python/pymavlink_mojo"),
    ("pypdf-filters-mojo", "pypdf image filters", "12×–15×", "python/pypdf_filters_mojo"),
    ("vader-mojo", "vaderSentiment", "4.1×", "python/vader_mojo"),
    ("bio-mojo", "Biopython SeqIO", "1.4×–2.3×", "python/bio_mojo"),
    ("toml-mojo", "stdlib tomllib", "~1.8×", "python/toml_mojo"),
    (
        "nx-mojo",
        "networkx betweenness",
        "1.2×–2.1× per call (20×–40× kernel-side)",
        "python/nx_mojo",
    ),
    ("jmespath-mojo", "jmespath", "up to 1.1× (parity-class workloads)", "python/jmespath_mojo"),
    (
        "fuse-mojo",
        "Fuse.js fuzzy search (TypeScript)",
        "8.8×–38.7× warm; 13× cold; bit-identical",
        "typescript/fuse-mojo",
    ),
    (
        "natural-mojo",
        "natural string distance (TypeScript)",
        "3.7×–7.6×",
        "typescript/natural-mojo",
    ),
    ("ckmeans-mojo", "ckmeans (TypeScript)", "1.6×–2.8×", "typescript/ckmeans-mojo"),
    (
        "minisearch-fuzzy-mojo",
        "MiniSearch fuzzy (TypeScript)",
        "parity-class, profile-driven drop-in",
        "typescript/minisearch_fuzzy_mojo",
    ),
]


def gallery_html() -> str:
    cards = []
    for pkg, target, speedup, path in GALLERY:
        src = f"{REPO}/tree/main/{path}"
        cards.append(
            f'<div class="kcard"><div class="kname">{pkg}</div>'
            f'<div class="ktarget">accelerates {target}</div>'
            f'<div class="kspeed">{speedup}</div>'
            f'<div class="klinks"><a href="{src}">source</a> · '
            f'<a href="{REPO}">mojo-kernels</a></div></div>'
        )
    return (
        '<div class="kgallery-intro">The largest public showcase of '
        "post-open-source Mojo kernels: 35 clean-room accelerators, same API / same "
        "results as the libraries they drop into, prebuilt wheels with pure-language "
        "fallbacks everywhere. Speedups are each package README&rsquo;s own measured "
        "claim (Apple M4 Max, median-of-5, correctness-gated).</div>"
        f'<div class="kgrid">{"".join(cards)}</div>'
    )
