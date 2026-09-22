# algenta_spaces

Shared code for the three Algenta Spaces on Hugging Face (`thyn-ai/algenta`,
`thyn-ai/algenta-speed-arena`, `thyn-ai/algenta-governed-agent`). One header,
one footer, one token set, one card library, one benchmark rulebook.

The package is stdlib-only at import time. `gradio` is imported lazily by
`design.theme()`; nothing else needs a third-party package, so the same code
runs on CPython 3.12 and 3.14.

| module | what it gives a Space |
|---|---|
| `shell` | `render_header`, `render_footer`, `SHELL_CSS`, nav and licence constants, copy checks |
| `design` | `--alg-*` CSS custom properties (light and dark), spacing and type scale, `theme()` |
| `cards` | `render_result_card`, `render_held_card`, `render_unavailable_card`, `status_chip`, `CARD_CSS` |
| `bench` | rulebook v0.3: `LaneSpec`, `LaneResult`, `CellResult`, `run_cell`, `hardware_footer` |
| `boot` | `BootRegistry` staged boot status, `render_boot_html`, `to_json` |
| `facts` | `compute_facts` and `write_facts` (versions, interpreter, sha, Space id and hardware) |
| `ratelimit` | `TokenBucket` per-key limiter, `key_from_request` |
| `runtime` | `utc_stamp`, `pinned_versions`, `read_stamp` |
| `css` | `rule` (class repeated four times, never `!important`), `block`, `stylesheet` |

`fleet_css()` concatenates every stylesheet in the order a Space should load it.

The package is vendored into each Space at deploy time by `tools/stage.py`,
which also writes `.shared_sha` next to it; the footer shows that stamp.

Development: `ruff check apps/spaces/_shared` and
`python3 -m pytest tests/spaces -q` from the repository root.
