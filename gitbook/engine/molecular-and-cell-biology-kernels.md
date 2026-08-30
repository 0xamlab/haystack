---
icon: leaf
description: Sequence-level bioinformatics, genome-scale statistics, mass-spectrometry protein and metabolite quantification, allele-frequency population genetics, and plant secondary-metabolite assay formulas across six independent molecular-biology modules.
---

# Molecular and cell biology kernels

Six modules for the arithmetic that sits behind a wet-lab assay or a sequencing pipeline's summary
statistics, at six different scales: a single sequence read (`bioinformatics`), a whole assembled
genome (`genomics`), a digested protein run through a mass spectrometer (`proteomics`), a pool of
small-molecule metabolites profiled the same way (`metabolomics`), an allele's frequency across
generations of a population (`population_genetics`), and a plant extract characterized by
spectrophotometric assay (`phytochemistry`). Every function here is a closed-form formula lifted
from a named, citable method — Wallace-rule melting temperature, Pace's 1995 extinction-coefficient
model, Ishihama's emPAI, Lichtenthaler's 1987 chlorophyll equations, Wright's fixation index — not a
sequence aligner, a peak picker, or a statistical solver. Given the summary numbers an upstream tool
already produced, these modules turn them into the percentage, ratio, or score a paper would report.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 200M reads x 150bp over a 3 Gbp genome
runtime.execute("genomics", "coverage_depth", [200_000_000.0, 150.0, 3_000_000_000.0])["result"]
# 10.0 -- mean depth, computed from raw read count and length, not a pre-summed base total

runtime.execute("bioinformatics", "phred_quality_to_error", [30.0])["result"]
# 0.001 -- Phred Q30 is the base-caller's own "1 error in 1000 bases" convention
```

## The modules

| Module | What it does |
| --- | --- |
| `bioinformatics` | Single-sequence and single-read formulas: GC%, Wallace-rule and salt-adjusted melting temperature, ssDNA molecular weight, pairwise sequence identity, E-value significance, coverage from pre-summed base totals, a pipeline pass-through for N50, Phred quality \| error-probability conversion in both directions, and codon/amino-acid counting from a raw sequence length. |
| `genomics` | Genome-scale annotation statistics: GC content from separate G and C counts, genome size from Cot½ reassociation kinetics, coverage from read count and length, N50 estimated from an assumed-uniform contig size distribution, SNP density, indel rate, repeat fraction, gene density per Mb, read-mapping efficiency, and sequencing error rate from Phred quality. |
| `proteomics` | Protein-scale mass-spectrometry formulas: molecular weight from residue count, a simplified isoelectric-point estimate, the Pace (1995) ε₂₈₀ extinction coefficient, Beer-Lambert protein concentration, sequence coverage, monoisotopic peptide m/z, label-free peak-area quantification, protein abundance index, exponentially-modified PAI (emPAI), and target-decoy FDR. |
| `metabolomics` | Metabolite-scale profiling and pathway statistics: log2 fold change, hypergeometric-style pathway enrichment, the Tanimoto chemical-similarity coefficient, metabolic flux-branch ratio, ¹³C/²H isotope-label fraction, first-order metabolite half-life, z-score normalization, PCA variance-explained, PLS-DA VIP score, and Euclidean feature-space distance. |
| `population_genetics` | Allele-frequency dynamics across generations: Hardy-Weinberg heterozygote frequency, drift's standard deviation of Δp, a linearized selection-coefficient Δp, Wright's effective population size from sex ratio, nucleotide diversity π, a simplified Tajima's D, Wright's FST, an inbreeding coefficient, a simplified mutation-load estimate, and linkage disequilibrium D. |
| `phytochemistry` | Plant secondary-metabolite assay formulas: Folin-Ciocalteu total phenolics, AlCl₃ total flavonoids, pH-differential anthocyanin concentration, tannin content by difference, hydrodistillation essential-oil yield, gravimetric alkaloid content, Lichtenthaler (1987) chlorophyll a/b and total carotenoids, and DPPH radical-scavenging activity. |

## `bioinformatics` and `genomics`: overlapping names, genuinely different scale

The hint that motivated this page frames `bioinformatics` as "general (sequence analysis)" and
`genomics` as "DNA/genome-scale analysis," and reading both sources confirms that split rather than
finding it collapsed into one thing — but the two modules are close enough in vocabulary that the
distinction is worth spelling out function by function, because three names appear in both and mean
different things each time:

* **`gc_content`** — `bioinformatics.gc_content(gc_count, total_bases)` takes a single pre-summed
  G+C count over two arguments. `genomics.gc_content(g_count, c_count, total_bp)` takes G and C as
  *separate* counts over three arguments, only summing them inside the function. Same formula
  (`(GC / total) * 100`), different calling shape — passing a combined count where `genomics` expects
  two separate ones silently double-counts nothing but shifts every other positional argument by one.
* **`coverage_depth`** — `bioinformatics.coverage_depth(total_bases_sequenced, genome_size)` expects
  the caller to have already multiplied read count by read length. `genomics.coverage_depth(
  read_count, read_length, genome_size_bp)` does that multiplication itself from the two raw
  sequencing-run numbers. Both return the same "×" fold-coverage figure; they just start from a
  different upstream state.
* **N50** — `bioinformatics.n50_from_values(total_assembly, half_total)` is a documented
  pass-through: it accepts a *pre-computed* N50 (`half_total`) and returns it unchanged, taking
  `total_assembly` only "for context/validation" that this function's own body never uses.
  `genomics.n50_approximation(total_assembly_bp, contig_count)` instead *computes* an estimate,
  assuming every contig is the same size: `total_bp / (2 * n_contigs)`. Calling the `bioinformatics`
  version expecting it to derive N50 from a contig count gets nothing — it has no contig-count
  argument to derive from.

Everything else in `genomics` — Cot½ genome-size estimation, SNP density per kb, indel rate,
repeat fraction, gene density per Mb, read-mapping efficiency — has no `bioinformatics` counterpart
at all; those are genuinely genome-assembly-scale statistics with nothing to compare against upstream.
`sequencing_error_rate` (`genomics`) and `phred_quality_to_error` (`bioinformatics`) are the same
`10^(-Q/10)` formula under two different names in two different modules, with no cross-import between
them — a caller who only reads one module's docstring will not discover the other has the identical
function.

### A worked assembly-QC chain

```python
# 20,000 annotated genes over a 3 Gbp genome
runtime.execute("genomics", "gene_density", [20_000.0, 3_000_000_000.0])["result"]
# 6.666666666666667 genes/Mb -- close to the real human-genome figure (~20,000 genes / ~3,235 Mb)

# half the genome flagged as repetitive
runtime.execute("genomics", "repeat_fraction", [1_500_000_000.0, 3_000_000_000.0])["result"]
# 0.5 -- consistent with the widely cited "~50% of the human genome is repetitive" figure

# 6 Mbp assembly in 30 equal-sized contigs
runtime.execute("genomics", "n50_approximation", [6_000_000.0, 30.0])["result"]
# 100000.0 bp -- total / (2 * contig_count), the uniform-distribution estimate

# same 30x run, quality-scored
runtime.execute("bioinformatics", "codon_count", [90])["result"]
# 30 -- 90 // 3, integer division
runtime.execute("bioinformatics", "amino_acid_count", [30])["result"]
# 29 -- codons minus the stop codon
```

These are not arbitrary inputs: `gene_density`'s ratio and `repeat_fraction`'s 0.5 both land close to
figures widely reported for the human genome, which is what the docstrings' own scale (bp, Mb) implies
these functions are sized for.

## `proteomics`: mass-spectrometry identification and quantification

```python
# Pace (1995): epsilon_280 = 5500*Trp + 1490*Tyr + 125*cystine
eps = runtime.execute("proteomics", "extinction_coefficient", [1.0, 2.0, 0.0])["result"]
eps
# 8480.0 -- one Trp, two Tyr, no disulfides

runtime.execute("proteomics", "protein_concentration_a280", [0.5, eps, 1.0])["result"]
# 5.89622641509434e-05 M -- Beer-Lambert: A / (epsilon * path_cm)

runtime.execute("proteomics", "peptide_mass_monoisotopic", [1000.0, 2.0])["result"]
# 501.00728 -- (1000 + 2 * 1.00728) / 2; 1.00728 Da is the proton mass added per charge

runtime.execute("proteomics", "fdr_target_decoy", [5.0, 95.0])["result"]
# 0.1 -- 2*decoy / (target + decoy), the conservative Elias-Gygi target-decoy estimate

runtime.execute("proteomics", "empa_score", [0.1])["result"]
# 0.2589254117941673 -- 10^PAI - 1 (Ishihama 2005 exponentially-modified PAI)
```

`isoelectric_point_approx` is the one formula in this module that is not a named published method —
its own docstring calls it a "Simplified model: pI ≈ (pK_pos + pK_neg) / 2," implemented as
`7.0 + 1.5 * ln(positive / (negative + 1))` rather than a real pKa-lookup Henderson-Hasselbalch
titration curve. `molecular_weight_da`'s `+ 18.0` is the standard peptide-bond-condensation water
correction (`n_residues * avg_mass + water`), the same convention used by real protein-MW
calculators — not a made-up constant.

## `metabolomics`: profiling and pathway statistics, with one dead parameter

```python
runtime.execute("metabolomics", "metabolite_fold_change", [200.0, 100.0])["result"]
# 1.0 -- log2(condition / control); a doubling is exactly log2FC = 1

runtime.execute("metabolomics", "pathway_enrichment_score", [8.0, 20.0, 500.0, 2000.0])["result"]
# 1.6 -- expected = 20*500/2000 = 5 hits by chance; 8 observed / 5 expected = over-represented

runtime.execute("metabolomics", "chemical_similarity_index", [10.0, 15.0, 12.0])["result"]
# 0.5882352941176471 -- Tanimoto: common / (bits_a + bits_b - common)
```

**`metabolic_distance`'s `n_features` argument never reaches the return value.** The docstring
frames the function as `d = sqrt(Σ(xi - yi)²)` over `n_features` dimensions, and the contract lists
`n_features` as the function's first parameter — but the body is exactly `sqrt(sum_sq_diff)`, with
`n_features` unused anywhere in it. `metabolic_distance(999.0, 25.0)` and
`metabolic_distance(3.0, 25.0)` both return `5.0`; the caller is expected to have already summed the
squared per-feature differences into `sum_sq_diff` before calling, and the feature count carried
alongside it for documentation purposes is simply never consulted. This was verified by reading the
function body directly, not inferred from behavior — `mojo/engine/metabolomics.mojo`'s
`metabolic_distance` has no reference to `n_features` past its own signature.

## `population_genetics`: allele-frequency dynamics across generations

```python
runtime.execute("population_genetics", "hardy_weinberg_freq", [0.3])["result"]
# 0.42 -- 2pq heterozygote frequency at p=0.3

runtime.execute("population_genetics", "effective_population_size", [1000.0, 200.0])["result"]
# 666.6666666666666 -- Ne = 4*Nf*Nm/(Nf+Nm); a skewed sex ratio pulls Ne well below the census 1200

runtime.execute("population_genetics", "fst_wright", [0.5, 0.3])["result"]
# 0.4 -- (HT - HS) / HT; moderate population differentiation

runtime.execute("population_genetics", "linkage_disequilibrium", [0.3, 0.5, 0.5])["result"]
# 0.05 -- D = p_AB - p_A*p_B; loci are not in linkage equilibrium
```

`tajimas_d_simplified` is explicitly named and documented as an approximation — its own comment
reads "ignores variance correction factors" — and hand-tracing it confirms that: for `n=10`,
`seg_sites=20`, `avg_pairwise_diff=5.0`, Watterson's `a1` is the harmonic sum `Σ 1/i` for
`i=1..9 ≈ 2.828968`, giving `theta_w = 20 / 2.828968 ≈ 7.0697`, and the function divides
`(5.0 - 7.0697)` by `sqrt(seg_sites * 0.05 + 0.001) ≈ 1.0005` to return `≈ -2.0687`. A real Tajima's D
normalizes by a full sampling-variance formula built from `a1`, `a2`, and the sample size; this one
substitutes a single ad hoc `sqrt(0.05*S + 0.001)` term, which is why its own name carries
"simplified."

**`mutation_load`'s formula runs opposite to the population-genetics result it is named for.**
Classical mutation-selection balance (Haldane's principle) says the equilibrium genetic load from a
recurrent deleterious mutation is *independent* of both the selection coefficient and the dominance
coefficient once the allele has any dominance at all (`L ≈ 2μ` for `h > 0`, `L ≈ μ` for a fully
recessive `h = 0`) — that is the textbook result the docstring itself invokes by name ("Haldane's
principle"). The function's own "Simplified" formula, `L = μ / (2h)` for `h > 0`, instead makes the
returned load shrink as dominance increases (`mutation_load(1e-5, 0.1) = 5e-05`,
`mutation_load(1e-5, 0.5) = 1e-05`) — the opposite direction from the constant-in-`h` result the
docstring names. This is a real, verified property of the shipped formula, not a transcription error
on this page's part: the `h = 0.0` branch returns `mutation_rate` unmodified (matching the recessive
case, `L ≈ μ`), but every `h > 0` branch diverges further from `2μ` the larger `h` gets, rather than
converging toward it. Treat this function's output as the named "simplified" proxy it documents
itself as, not as a literal reproduction of Haldane's load formula.

## `phytochemistry`: plant secondary-metabolite assay formulas

```python
# Lichtenthaler (1987), 80% acetone extract
chl_a = runtime.execute("phytochemistry", "chlorophyll_a", [0.65, 0.25])["result"]
chl_b = runtime.execute("phytochemistry", "chlorophyll_b", [0.65, 0.25])["result"]
chl_a, chl_b
# (7.234000000000001, 1.7629999999999995) -- ug/mL, from A663 and A646

runtime.execute("phytochemistry", "carotenoid_content", [0.3, chl_a, chl_b])["result"]
# 0.4060821834061139 -- (1000*A470 - 3.27*Chl_a - 104*Chl_b) / 229

runtime.execute("phytochemistry", "dpph_radical_scavenging", [0.8, 0.2])["result"]
# 75.00000000000001 -- % inhibition relative to the DPPH control absorbance

runtime.execute("phytochemistry", "essential_oil_yield", [2.5, 100.0])["result"]
# 2.5 -- % v/w, in the range typically reported for hydrodistilled mint-family oils
```

`phenolic_content_folin` and `flavonoid_content` share one calibration-curve shape —
`(absorbance - intercept) / slope * dilution` — differing only in which standard (gallic acid vs.
quercetin equivalents) and which absorbance wavelength (765 nm vs. 510 nm) the calibration was built
from; the function itself is agnostic to which assay it is being used for; that information lives
entirely in the slope/intercept the caller supplies. `anthocyanin_concentration` is the one function
in this module built from six arguments instead of two to four, because the pH-differential method
it implements (`ΔA × MW / (ε × l) × dilution`) genuinely needs a molar mass, an extinction
coefficient, a path length, and both pH-1.0 and pH-4.5 absorbances to produce a concentration in
mg/L, unlike the single-wavelength assays around it.

## Verification

Only `bioinformatics` has a real, hand-pinned numeric test suite: `tests/mojo/test_wave88.mojo`
(shared with `refrigeration` and `cartography`) checks 30 assertions against worked values —
`gc_content(40.0, 100.0) == 40.0`, `tm_salt_adjusted(60.0, 50.0)` between `38.0` and `39.0`,
`phred_quality_to_error(30.0)` within `1e-3` of `0.001`, `codon_count(90) == 30`,
`amino_acid_count(30) == 29`, and more — every one independently reproducible from the formulas in
`mojo/engine/bioinformatics.mojo`.

The other five modules — `genomics`, `proteomics`, `metabolomics`, `population_genetics`,
`phytochemistry` — have only auto-generated coverage smoke tests
(`mojo/tests/libs/test_<module>.mojo`, plus a shared pass in `mojo/tests/test_all_libraries.mojo`):
each calls every function once with a literal `0.5` (or `10.0` in the all-libraries pass) per
argument and asserts only that the result is finite, never pinning a specific numeric output. Every
worked number on this page for those five modules was hand-traced against the real formula bodies in
`mojo/engine/genomics.mojo`, `proteomics.mojo`, `metabolomics.mojo`, `population_genetics.mojo`, and
`phytochemistry.mojo`, and cross-checked independently in plain Python (`log`, `sqrt`, `exp`, no
library) rather than assumed from the docstrings alone — the `metabolic_distance` dead parameter and
the `mutation_load` direction were both found this way, by reading the function bodies rather than
trusting their comments.

**Next:** see [Immunology, hematology, and virology kernels](immunology-hematology-and-virology-kernels.md)
for the adjacent clinical and cell-biology lab-science formulas, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
