# IP schedule generator

Produces the Schedule of Intellectual Property that accompanies a financing or
diligence request: a dated, reproducible snapshot of what the company owns, where it
lives, who wrote it, and under which terms it is licensed in and out.

    make ip-schedule                      # writes ~/Documents/thyn-ip-inventory/<date>/
    IP_OUT=/somewhere make ip-schedule    # elsewhere

Three steps, one JSON in between:

1. `collect.py` measures every repository in `config.toml` at `origin/<default>` after a
   fetch (never the working tree), reads the packaged runtime contract for function and
   module counts, parses dependency manifests and looks their licenses up, pulls the newest
   CI SBOM artifacts where a repository publishes them, and records PyPI/npm and WHOIS
   facts. It writes `snapshot.json`.
2. `render.py` turns the snapshot into `Thyn_IP_Schedule_<date>.xlsx` (one tab per
   schedule), a Markdown twin, `Valuation_support_internal_<date>.md` (a measured-rate
   replacement-cost floor plus market comparables; never uploaded), and `derived.json` (headline totals plus the inputs of the internal
   valuation note).
3. `narrative.py` writes `Thyn_IP_Narrative_<date>.md` — the "Intellectual Property"
   subsection in offering-memorandum form (Form C exhibit), its Form 1-A Item 7 variant,
   draft risk factors, and a pointer to the internal valuation note — plus
   `narrative_numbers.json`, the list of every figure the prose used. Convert the Markdown
   to .docx for delivery; the numbers stay traceable to the snapshot either way.

Facts that cannot be measured — the owning entity, which domains and marks belong to the
schedule, trade-secret categories, license positions, the contributor identity map — live in
`config.toml`. Everything else is measured; change a number by re-running, not by editing.

`tests/test_ip_schedule_generator.py` runs the collector offline at the local HEAD and
checks that its tracked-Mojo figure equals `scripts/count_mojo_loc.sh` line for line, that the
contract counts match the packaged JSON, that every human commit collapses to one identity,
and that the workbook renders with a uniform owner column.

`make ip-schedule-pdf` (optional; needs a Python with `reportlab` and `openpyxl`, set
`IP_PDF_PYTHON=...` if that is not `python3`) renders the workbook and the two Markdown
documents to PDF with nothing clipped: narrow tabs as wrapped landscape tables with repeated
headers, wide tabs as one field/value card per row.
