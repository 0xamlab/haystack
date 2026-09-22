#!/usr/bin/env python3
"""Generate the vendored mini-corpus for the RAG retrieval duel, deterministically.

The corpus is BEIR-scifact-STYLE but fully synthetic: 20 scientific topics, each
with templated study abstracts (population / method / intervention / outcome slots
filled from a seeded RNG). No real papers, no downloaded data — the bytes in
lab/data/corpus_scifact_mini.json are reproduced exactly by re-running this script:

    python scripts/gen_corpus.py            # writes lab/data/corpus_scifact_mini.json
    python scripts/gen_corpus.py --check    # exits non-zero if the vendored file drifts

Seed: 20260920 (printed inside the JSON, and asserted by the test suite).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

SEED = 20260920
DOCS_PER_TOPIC = 16
OUT_PATH = Path(__file__).resolve().parent.parent / "lab" / "data" / "corpus_scifact_mini.json"

# ---------------------------------------------------------------------------
# Topic model: 20 scifact-style topics. Each entry feeds the template slots.
# Everything here is invented terminology in plain scientific English.
# ---------------------------------------------------------------------------

TOPICS = [
    {
        "slug": "vitamin-d-fractures",
        "field": "nutritional epidemiology",
        "agent": "vitamin D3 supplementation",
        "agent_terms": ["vitamin d", "cholecalciferol", "25-hydroxyvitamin d", "supplementation"],
        "outcome": "fracture risk",
        "outcome_terms": ["fracture", "bone mineral density", "hip fracture", "falls"],
        "population": ["elderly adults", "postmenopausal women", "care home residents"],
        "organism": "human",
    },
    {
        "slug": "crispr-off-target",
        "field": "genome editing",
        "agent": "CRISPR-Cas9 editing",
        "agent_terms": ["crispr", "cas9", "guide rna", "genome editing"],
        "outcome": "off-target mutation rate",
        "outcome_terms": ["off-target", "indel", "specificity", "on-target activity"],
        "population": ["human cell lines", "primary T cells", "mouse embryos"],
        "organism": "human",
    },
    {
        "slug": "microplastics-phytoplankton",
        "field": "marine ecology",
        "agent": "microplastic exposure",
        "agent_terms": ["microplastics", "polystyrene particles", "nanoplastics"],
        "outcome": "phytoplankton growth",
        "outcome_terms": ["chlorophyll-a", "photosynthetic yield", "growth rate", "biomass"],
        "population": ["marine phytoplankton cultures", "coastal water samples"],
        "organism": "phytoplankton",
    },
    {
        "slug": "rem-sleep-memory",
        "field": "sleep neuroscience",
        "agent": "REM sleep deprivation",
        "agent_terms": ["rem sleep", "sleep deprivation", "slow wave sleep"],
        "outcome": "memory consolidation",
        "outcome_terms": [
            "hippocampal replay",
            "recall accuracy",
            "declarative memory",
            "spindle density",
        ],
        "population": ["healthy volunteers", "undergraduate students", "older adults"],
        "organism": "human",
    },
    {
        "slug": "probiotics-antibiotic-diarrhea",
        "field": "clinical microbiology",
        "agent": "probiotic co-administration",
        "agent_terms": ["probiotics", "lactobacillus", "saccharomyces boulardii"],
        "outcome": "antibiotic-associated diarrhea",
        "outcome_terms": [
            "clostridioides difficile",
            "gut microbiota",
            "diarrhea incidence",
            "dysbiosis",
        ],
        "population": ["hospitalized adults", "pediatric patients", "outpatients on antibiotics"],
        "organism": "human",
    },
    {
        "slug": "caffeine-endurance",
        "field": "exercise physiology",
        "agent": "caffeine ingestion",
        "agent_terms": ["caffeine", "coffee", "anhydrous caffeine"],
        "outcome": "endurance performance",
        "outcome_terms": ["time trial", "vo2 max", "time to exhaustion", "power output"],
        "population": ["trained cyclists", "recreational runners", "elite triathletes"],
        "organism": "human",
    },
    {
        "slug": "drought-maize-yield",
        "field": "agronomy",
        "agent": "drought stress",
        "agent_terms": ["drought", "water deficit", "soil moisture"],
        "outcome": "maize grain yield",
        "outcome_terms": [
            "grain yield",
            "kernel number",
            "anthesis-silking interval",
            "harvest index",
        ],
        "population": ["field trial plots", "greenhouse-grown maize", "hybrid cultivars"],
        "organism": "maize",
    },
    {
        "slug": "metformin-lifespan",
        "field": "geroscience",
        "agent": "metformin treatment",
        "agent_terms": ["metformin", "biguanide", "ampk activation"],
        "outcome": "healthspan markers",
        "outcome_terms": [
            "lifespan",
            "insulin sensitivity",
            "inflammaging",
            "mitochondrial function",
        ],
        "population": ["middle-aged mice", "c. elegans cohorts", "prediabetic adults"],
        "organism": "mouse",
    },
    {
        "slug": "ocean-acidification-coral",
        "field": "ocean biogeochemistry",
        "agent": "ocean acidification",
        "agent_terms": ["ocean acidification", "aragonite saturation", "pCO2"],
        "outcome": "coral calcification",
        "outcome_terms": [
            "calcification rate",
            "skeletal density",
            "reef accretion",
            "bleaching threshold",
        ],
        "population": ["reef-building corals", "mesocosm communities", "larval recruits"],
        "organism": "coral",
    },
    {
        "slug": "hand-hygiene-mrsa",
        "field": "infection control",
        "agent": "alcohol-based hand hygiene",
        "agent_terms": ["hand hygiene", "alcohol rub", "handwashing compliance"],
        "outcome": "MRSA transmission",
        "outcome_terms": [
            "mrsa",
            "nosocomial infection",
            "cross-transmission",
            "colonization pressure",
        ],
        "population": ["ICU patients", "surgical wards", "healthcare workers"],
        "organism": "human",
    },
    {
        "slug": "forest-fire-soil-carbon",
        "field": "soil science",
        "agent": "wildfire severity",
        "agent_terms": ["wildfire", "burn severity", "pyrogenic carbon"],
        "outcome": "soil organic carbon",
        "outcome_terms": [
            "soil carbon",
            "microbial biomass",
            "charcoal fraction",
            "respiration rate",
        ],
        "population": ["boreal forest stands", "Mediterranean shrubland", "pine plantations"],
        "organism": "soil",
    },
    {
        "slug": "ssri-adolescent-depression",
        "field": "psychiatry",
        "agent": "SSRI pharmacotherapy",
        "agent_terms": ["ssri", "fluoxetine", "sertraline", "antidepressant"],
        "outcome": "adolescent depression scores",
        "outcome_terms": [
            "depression rating",
            "remission rate",
            "suicidal ideation",
            "response rate",
        ],
        "population": [
            "adolescents with major depression",
            "outpatient youth",
            "school-referred patients",
        ],
        "organism": "human",
    },
    {
        "slug": "led-light-algae-biofuel",
        "field": "bioprocess engineering",
        "agent": "LED spectral tuning",
        "agent_terms": ["led illumination", "red light spectrum", "photobioreactor"],
        "outcome": "algal lipid productivity",
        "outcome_terms": [
            "lipid content",
            "biomass productivity",
            "fatty acid profile",
            "biofuel yield",
        ],
        "population": ["chlorella vulgaris cultures", "nannochloropsis strains"],
        "organism": "microalgae",
    },
    {
        "slug": "vaccine-cold-chain",
        "field": "public health logistics",
        "agent": "cold-chain interruptions",
        "agent_terms": ["cold chain", "vaccine potency", "temperature excursion"],
        "outcome": "vaccine effectiveness",
        "outcome_terms": ["seroconversion", "antibody titer", "potency loss", "coverage"],
        "population": ["rural immunization programs", "district health facilities"],
        "organism": "human",
    },
    {
        "slug": "neonicotinoid-bees",
        "field": "entomology",
        "agent": "neonicotinoid exposure",
        "agent_terms": ["neonicotinoids", "imidacloprid", "clothianidin"],
        "outcome": "honeybee foraging",
        "outcome_terms": ["foraging success", "colony weight", "queen production", "navigation"],
        "population": ["honeybee colonies", "bumblebee microcolonies"],
        "organism": "bee",
    },
    {
        "slug": "hiit-blood-pressure",
        "field": "cardiovascular prevention",
        "agent": "high-intensity interval training",
        "agent_terms": ["hiit", "interval training", "aerobic exercise"],
        "outcome": "systolic blood pressure",
        "outcome_terms": [
            "blood pressure",
            "arterial stiffness",
            "resting heart rate",
            "endothelial function",
        ],
        "population": ["hypertensive adults", "sedentary office workers", "older women"],
        "organism": "human",
    },
    {
        "slug": "permafrost-methane",
        "field": "cryosphere science",
        "agent": "permafrost thaw",
        "agent_terms": ["permafrost", "thermokarst", "active layer deepening"],
        "outcome": "methane flux",
        "outcome_terms": [
            "methane emissions",
            "ebullition",
            "soil temperature",
            "carbon dioxide flux",
        ],
        "population": ["Arctic tundra sites", "peat plateaus", "thermokarst lakes"],
        "organism": "soil",
    },
    {
        "slug": "omega3-triglycerides",
        "field": "lipidology",
        "agent": "omega-3 fatty acid supplementation",
        "agent_terms": ["omega-3", "epa", "dha", "fish oil"],
        "outcome": "triglyceride levels",
        "outcome_terms": [
            "triglycerides",
            "hdl cholesterol",
            "ldl particle size",
            "apolipoprotein b",
        ],
        "population": [
            "hypertriglyceridemic patients",
            "statin-treated adults",
            "metabolic syndrome cohorts",
        ],
        "organism": "human",
    },
    {
        "slug": "urban-trees-air-pollution",
        "field": "urban ecology",
        "agent": "urban tree cover",
        "agent_terms": ["urban trees", "green infrastructure", "canopy cover"],
        "outcome": "street-level air pollution",
        "outcome_terms": [
            "pm2.5",
            "nitrogen dioxide",
            "deposition velocity",
            "ultrafine particles",
        ],
        "population": ["city street canyons", "residential neighborhoods"],
        "organism": "tree",
    },
    {
        "slug": "zinc-common-cold",
        "field": "respiratory medicine",
        "agent": "zinc lozenge administration",
        "agent_terms": ["zinc", "zinc acetate", "lozenges"],
        "outcome": "common cold duration",
        "outcome_terms": [
            "cold duration",
            "symptom severity",
            "rhinovirus shedding",
            "recovery time",
        ],
        "population": ["adults with natural colds", "challenge-study volunteers"],
        "organism": "human",
    },
]

METHODS = [
    "randomized controlled trial",
    "double-blind crossover study",
    "prospective cohort study",
    "systematic review and meta-analysis",
    "controlled laboratory experiment",
    "multi-site field study",
]

EFFECT_DIRECTIONS = [
    ("significantly reduced", "reduction"),
    ("significantly increased", "increase"),
    ("did not significantly alter", "null"),
    ("modestly reduced", "reduction"),
    ("modestly increased", "increase"),
]

SENT_TEMPLATES = [
    "A {method} enrolled {n} {population} and found that {agent} {verb} {outcome} by {pct}% (95% CI {lo} to {hi}).",
    "In {population}, {agent} {verb} {outcome_term} relative to controls over {weeks} weeks of follow-up.",
    "We report a {method} in the field of {field} examining {agent_term} and its effect on {outcome_term}.",
    "Compared with placebo, {agent} {verb} {outcome} in {population} (n = {n}), with no serious adverse events recorded.",
    "Subgroup analysis suggested the effect of {agent_term} on {outcome_term} was strongest in {population}.",
    "Mechanistically, {agent_term} appeared to act through changes in {outcome_term}, consistent with prior work in {field}.",
    "These findings indicate that {agent} may {maybe} influence {outcome} in {population}, warranting further {method}s.",
    "Baseline {outcome_term} predicted the response to {agent} (r = {corr}), independent of age and sex.",
]

#: Claim-style sample queries, one per topic, written the way a scifact user
#: phrases a claim to verify against the corpus.
SAMPLE_QUERIES = {
    "vitamin-d-fractures": "vitamin d supplementation reduces fracture risk in elderly adults",
    "crispr-off-target": "crispr cas9 guide rna off-target mutation rate human cells",
    "microplastics-phytoplankton": "microplastic exposure reduces phytoplankton photosynthetic growth",
    "rem-sleep-memory": "rem sleep deprivation impairs memory consolidation",
    "probiotics-antibiotic-diarrhea": "probiotics prevent antibiotic associated diarrhea in hospitalized adults",
    "caffeine-endurance": "caffeine improves endurance time trial performance in trained cyclists",
    "drought-maize-yield": "drought stress reduces maize grain yield",
    "metformin-lifespan": "metformin extends healthspan and lifespan in mice",
    "ocean-acidification-coral": "ocean acidification reduces coral calcification rate",
    "hand-hygiene-mrsa": "alcohol hand hygiene reduces mrsa transmission in icu patients",
    "forest-fire-soil-carbon": "wildfire reduces soil organic carbon in boreal forests",
    "ssri-adolescent-depression": "ssri treatment reduces depression scores in adolescents",
    "led-light-algae-biofuel": "led red light increases algal lipid productivity for biofuel",
    "vaccine-cold-chain": "cold chain temperature excursions reduce vaccine potency",
    "neonicotinoid-bees": "neonicotinoid exposure impairs honeybee foraging success",
    "hiit-blood-pressure": "high intensity interval training lowers systolic blood pressure",
    "permafrost-methane": "permafrost thaw increases methane emissions from arctic tundra",
    "omega3-triglycerides": "omega 3 supplementation lowers triglyceride levels",
    "urban-trees-air-pollution": "urban trees reduce street level pm2.5 air pollution",
    "zinc-common-cold": "zinc lozenges shorten common cold duration",
}


def _fill(rng: random.Random, template: str, topic: dict) -> str:
    verb, _kind = EFFECT_DIRECTIONS[rng.randrange(len(EFFECT_DIRECTIONS))]
    pct = rng.randint(3, 68)
    lo = max(1, pct - rng.randint(2, 14))
    hi = pct + rng.randint(2, 18)
    return template.format(
        method=rng.choice(METHODS),
        n=rng.choice([24, 36, 48, 60, 96, 120, 240, 412, 1030]),
        population=rng.choice(topic["population"]),
        agent=topic["agent"],
        agent_term=rng.choice(topic["agent_terms"]),
        outcome=topic["outcome"],
        outcome_term=rng.choice(topic["outcome_terms"]),
        verb=verb,
        pct=pct,
        lo=lo,
        hi=hi,
        weeks=rng.choice([4, 8, 12, 24, 52]),
        field=topic["field"],
        maybe=rng.choice(["", "partially", "indirectly"]),
        corr=round(rng.uniform(0.18, 0.72), 2),
    )


def generate() -> dict:
    rng = random.Random(SEED)
    docs = []
    serial = 0
    for topic in TOPICS:
        for j in range(DOCS_PER_TOPIC):
            serial += 1
            n_sent = rng.randint(4, 6)
            # Sample distinct templates per abstract; always lead with the
            # findings-style first template for title coherence.
            first = SENT_TEMPLATES[0]
            rest = rng.sample(SENT_TEMPLATES[1:], k=n_sent - 1)
            sentences = [_fill(rng, first, topic)] + [_fill(rng, t, topic) for t in rest]
            title = (
                f"{topic['agent'].capitalize()} and {topic['outcome']} in "
                f"{topic['population'][j % len(topic['population'])]}: a {rng.choice(METHODS)}"
            )
            docs.append(
                {
                    "id": f"D{serial:03d}",
                    "topic": topic["slug"],
                    "title": title,
                    "text": title + ". " + " ".join(sentences),
                }
            )
    # Shuffle doc order deterministically so topic blocks are not adjacent.
    rng.shuffle(docs)
    queries = [
        {"id": f"Q{i + 1:02d}", "topic": slug, "text": text}
        for i, (slug, text) in enumerate(SAMPLE_QUERIES.items())
    ]
    return {
        "provenance": (
            "Fully synthetic BEIR-scifact-STYLE mini-corpus: 320 invented study "
            "abstracts across 20 scientific topics, generated deterministically by "
            "scripts/gen_corpus.py (seed 20260920) for the Algenta for LLM Agents "
            "Space. These are NOT real papers and make NO real scientific claims."
        ),
        "seed": SEED,
        "n_docs": len(docs),
        "docs": docs,
        "queries": queries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify the vendored file matches")
    args = parser.parse_args()
    payload = json.dumps(generate(), indent=1, sort_keys=False) + "\n"
    if args.check:
        if not OUT_PATH.exists() or OUT_PATH.read_text() != payload:
            print("MISMATCH: vendored corpus does not match generator output", file=sys.stderr)
            return 1
        print(f"OK: {OUT_PATH} matches generator output ({SEED=})")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(payload)
    print(f"wrote {OUT_PATH} ({len(payload)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
