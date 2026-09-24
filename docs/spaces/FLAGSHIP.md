# The flagship Space — `thyn-ai/algenta`

Internal notes for `apps/spaces/algenta/`. Module docstrings are the reference; this page
is the runbook view. Sections are owned by the milestone that shipped them. The measurement
protocol every timed cell runs under is `docs/spaces/RULEBOOK.md` (v0.4 — batched samples,
fix round 5; `bench.RULEBOOK_VERSION` is the one constant the cards and the facts print).

## Verification

Three layers, all against the app running for real — never against fixtures:

| layer | what | where | when |
|---|---|---|---|
| endpoint + page checks | one check per `api_name`, `/health`, footer stamp, browser audit — run twice per deployment, without the tenant key and with it (`--phase keyed`, below) | `apps/spaces/algenta/verify_checks.py` | post-deploy (`tools/verify_remote.py`), pre-release, QA |
| goldens | 36 screenshots (6 tabs × 3 viewports × 2 themes), every measured number masked, diffed strictly — no unmasked pixel may differ beyond a 1-px anti-aliasing tolerance — only in the state the manifest records (`state`: opening card, Ecosystem Hub state, Space), read from the live `/health` and `/config` first; another state is a loud skip, never a comparison | `tests/spaces/visual/` + `tests/spaces/golden/` | CI on every flagship PR, against a launched app in the deployed state |
| permalink truth | ten link shapes loaded in Chromium; the box under the strip must promise only what the tab restored | `tests/spaces/visual/test_flagship_permalinks.py` (the `permalink_truth` gate's reading) | against a launched app, `-m slow` |
| unit tests | the three above against fakes, no network, no browser | `tests/spaces/test_flagship_verify.py`, `test_flagship_app.py` | `python3 -m pytest tests/spaces` |

### Launching the app locally

```sh
apps/spaces/algenta/scripts/spaces-flagship-run.sh --wait            # http://127.0.0.1:7860
apps/spaces/algenta/scripts/spaces-flagship-run.sh --port 7870       # exec app.py, no readiness wait
```

The script creates or reuses one venv (`<scratchpad>/venv-flagship`, CPython 3.12, or
`--venv DIR` / `ALGENTA_FLAGSHIP_VENV`), installs the pinned local toolchain when `gradio`
is missing (`gradio==6.28.0`, `torch==2.5.1`, `kernels>=0.17.1,<0.18`, `playwright`,
`pillow`, `axe-playwright-python`, …) and Chromium, points `HF_HOME` at a writable
directory (`<checkout>/../hf-home` by default; `~/.cache/huggingface` is a broken symlink on
the build Mac), puts `apps/spaces/_shared` on `PYTHONPATH` (the container has the package
vendored next to `app.py`, so the footer stamp reads `dev` locally) and runs `app.py`.
`--wait` polls `/health` until the boot snapshot says `ready: true` (budget
`ALGENTA_FLAGSHIP_BOOT_S`, default 600 s) and keeps the server in the foreground.

### The checks (`verify_checks.py`)

`tools/verify_remote.py` owns the registry and the runner (`register`, `run_checks`,
`VerifyError`, `VerifySkipped`); the flagship contributes its checks from its own directory
so the tool never carries Space-specific knowledge. Registration is one line once the tool
adopts the convention of importing `<source dir>/verify_checks.py` for a Space:

```python
load_space_checks("algenta").install(register, VerifyError, VerifySkipped)
```

Until then the same checks run standalone from the checkout:

```sh
python apps/spaces/algenta/verify_checks.py --url http://127.0.0.1:7860            # local
python apps/spaces/algenta/verify_checks.py --url https://thyn-ai-algenta.hf.space \
    --staged <staged dir>                                                          # live, with the .shared_sha
python apps/spaces/algenta/verify_checks.py --url … --only hero_result,health_ready
python apps/spaces/algenta/verify_checks.py --url … --staged <dir> --phase keyed             # the key is loaded into the app
```

**Two phases per deployment.** Every gate runs once against the app without the tenant key
and once with it loaded into the app's process (`--phase keyed`, or `ALGENTA_VERIFY_PHASE=keyed`
— the verifier itself never sees the key). The phase changes what the Governed gates accept: in
the keyed phase the not-configured card is a broken precondition (`governed_lane`,
`receipt_tone` and `webhook_privacy` fail on it — the tool was told a key is set), the refusal
probe must find the Governed form, `axe_serious_critical` must have audited a page with the
Governed controls on it (the open Engine responses block is the one scrollable Code block, and
round 3's keyed audits recorded its `scrollable-region-focusable` without a gate failing), and
`KEYED_REQUIRED` (`governed_lane`, `governed_profiles`, `receipt_tone`, `webhook_privacy`,
`refusal_convention`, `axe_serious_critical`, `console_clean`, `no_toasts`, `voids`) stays
selected whatever `--only` names. The report's first line says the phase and the number of checks. Every browser gate runs
in both phases; axe runs on every tab view in every context (1440 and 375 px, light and dark)
rather than the desktop alone.

The endpoint contract: every `tabs/<id>_tab.py` declares `API_NAMES`, the tuple it passes
to `api_name=` and to `TabSpec.api_names`. The verifier imports each tab module it finds
and builds the expected set from those tuples; a tab whose module is absent (or does not
import) falls back to the frozen `FALLBACK_API_NAMES` row, and a unit test fails when a
landed module's names stop matching that row. Each per-tab check finds its endpoint by the
tab-id prefix (`try_…`, `play_…`, …) and calls it by keyword through `gradio_client`,
using the app's own prefilled defaults for every parameter it does not override — the call
a visitor makes.

| check | asserts |
|---|---|
| `expected_api_names` | the live `/gradio_api/info` set equals the tabs' set — nothing missing, nothing extra |
| `hero_result` | Try returns a result card (`alg-card-result`) with the parity chip, a non-empty hardware line and a UTC stamp — or the rulebook's `not recorded` card, reported as that documented state with the card's reason (a sub-millisecond call on a loaded host is the protocol's honest answer, never a measurement) |
| `playground_levenshtein` | Playground runs `text.fuzzy.levenshtein_distance` on kitten/sitting and the result is 3 |
| `playground_decimals` | Playground runs `geodesy.haversine_distance` on London–Paris with four decimals each (51.5074, −0.1278, 48.8566, 2.3522); the Request-and-response JSON must echo exactly the numbers sent — a number box that rounded them to whole degrees echoes 52, 0, 49, 2 and a distance 19 km off — and the result must agree with the haversine formula computed in the check on the kernel's 6,371 km radius to 1e-9 relative |
| `race_cell` | a Races cell returns a result card with both lane latencies, or one of the documented states: held, not recorded, unavailable + code |
| `llm_rmsnorm_parity` | the RMSNorm call carries the parity chip — torch agreed within the printed tolerance (strict: an unavailable card fails) |
| `governed_lane` | `hosted_not_configured` without a key, `hosted_rate_limited` on a throttled demo tenant, else a receipt or a gate denial; `hosted_unavailable` fails. Codes are compared in lowercase snake_case (`verify_checks.same_code`), the fleet's one spelling: the cards print it, `hosted_api.NOT_CONFIGURED_CODE` / `RATE_LIMITED_CODE` / `UNAVAILABLE_CODE` are it |
| `governed_profiles` | with a key, the chain stops at the first tool the profile does not expose and the card says so: `/gov_run` is called once per lower profile through the form's Radio parameter (`profile_parameter`: the endpoint's one Radio — Gradio names parameters after the handler's arguments); the `observe` profile's answer is the intercept card `Not in the observe profile` with the sub-line `before the log call reached the engine`, the sentence `Logging a decision is not in this profile; the recommendation stands, nothing was logged or run.` and **no Decision row** (round 17's owner walkthrough found a decision id on it: `run_chain` logged under every profile and gated `execute_decision` alone), the `govern` profile's the intercept card with the `execute` sub-line, the `Executing a decision …` sentence and a Decision row; a receipt, a stale sub-line or a card in the wrong profile fails by name. Without a key the not-configured card is the documented state; in the keyed phase it is a broken precondition |
| `receipt_tone` | the Governed card tells the truth about the execution, read from the card `gov_tab.render_receipt` renders (`receipt_status` parses the tab's own status chip — `delivered · HTTP 200`, `webhook_failed · HTTP 502` / `no HTTP response`, `engine <status> · …` — round 3's gate expected an `engine <status>` chip the tab never paints and failed on every real receipt while its unit test passed on a hand-built card): a delivered execution is the live chip on the quiet card; a failed one (`execution_status: failed`) the red chip on the red card (`alg-card-err`) with no `webhook received` block and no "reported delivery" claim; `webhook received` is painted on a delivered receipt alone; any other engine status is the neutral chip, red only for a failure word (`FAILED_STATUS_WORDS`). A failure during the run (`webhook_url_unavailable` without a public https base, an engine or transport error) is the red card, never the quiet one. Without a key the not-configured card is the documented state; in the keyed phase it fails. The unit test renders every card through `gov_tab` (`_rendered_receipt`, a real `webhook.Hook` accepting the engine's own POST for the received block) — no hand-built card anywhere in the verifier tests |
| `webhook_privacy` | the nonce that gates the engine's webhook stays inside the process: `/health` names the route's prefix and whether it is public (`webhook: {prefix, public}`, `app.public_health`), never a `/hook/<nonce>` path (round 3 published it, and a forged POST to it was painted `webhook received · nonce verified` on a failed receipt); the Governed card prints no URL carrying the nonce (the receipt's raw `Webhook` row); a POST to `<prefix>/<guessed nonce>` answers 400 or 404 and a POST to the bare prefix 400/404/405 |
| `family_dropdown_foreign_value` | the Playground answers an API or MCP value naming a family this container did not load (`nope_family`) with a coded card (`unavailable · unknown_family`), never Gradio's stock `is not in the list of choices` error — on the run endpoint and on the family cascade endpoint (`play_modules`), which may also answer with no-op updates |
| `no_stock_code_labels` | no Code block keeps Gradio's stock block label (`[data-testid="block-label"]` with the `</>` icon and a caption) or CodeMirror's line-number gutter (`.cm-lineNumbers`); every closed disclosure of the tab is opened first so the Reproduce and Connect snippets count, then closed again; the detail counts the blocks measured |
| `voids` | at 1440 px, in every multi-column row of the displayed tab (a `.row` ≥ 700 px wide with two or more `.column` children), no gap over 240 px between consecutive visible elements of a column and no column ending more than 240 px above its row's bottom — measured at rest and again after each tab's primary action has settled (no loading chip left). Round 3 measured 469 px under the LLM controls after Run RMSNorm and 474 px under the red Governed card |
| `boot_row_live` | the boot card's hero row says what `/health` said at the moment the card was read (the audit reads both together): a measured hero prints `cards.fmt_ms(kernel_ms)` and the n chip's words — `n = <n>`, or `n = <n> × <k> calls` when `/health` carries `k` (rulebook v0.5; the row is `try_tab.repeats_label`, the Try card's own chip) — and never `not recorded`; an unmeasured one prints `not recorded` and no in-kernel figure; a container whose hero family never loaded (`/health` hero `null`) prints `<family> did not load · <code>`. Round 3 measured a row frozen at `noisy — not recorded … attempt 6` under a Try card showing 0.12 ms (attempt 18): the stage detail is written once at the stage's end. The boot disclosure now re-renders the registry on every page load (`app.py`), so a detail the boot owner updates later reaches the card a visitor opens |
| `refusal_convention` | every refusal is a field message under the offending control (`.alg-field-msg` outside `.alg-status`, within 120 px below the control's box and overlapping it horizontally) **and** an echo in the status row beside the action (`.alg-status` with text, within 160 px of the run button) — never a red card, never a toast. One refusal per tab in two contexts (1440 light, 375 dark): Try `Successes A = 5000` (`cannot exceed`), Playground `successes_a = -5` (`negative`), LLM kernels `Rows = 50` above the range (`rows`; round 10 — the sentence names the range, `Rows: 1 to 32`), Governed `Optimistic value = 1000` below the pessimistic one (`optimistic`; probed only where the form is shown — a key is set — and required in the keyed phase). Round 3 found three conventions: Try in the status row alone, the Playground under the field alone, Governed as a red `invalid_input` card |
| `ecosystem_counts` | the Hub table's live counts whenever the Hub answered — repository rows, rows the Hub column lists (a download count or a publish date), the functions, downloads and likes chips; only a Hub code (`hub_counts_*`) is a documented state, and a code on another card of the tab (GitHub, the MCP registry) is named beside the counts, never in their place. A table with rows but an empty Hub column and no code fails (a broken fetch is not a state). Without a table in the outputs the old rule holds: at least two computed integers |
| `every_endpoint_answers` | every remaining `api_name` (snippets, status tiles, RoPE, sampling, …) answers a default call with output; unavailable codes are listed. The Playground's selector cascade (`play_modules`, `play_functions`, `play_form`) answers the default selection with value-less updates — the selection already applied, kept by `play_tab`'s value guard — so such an endpoint is asked once more for a changed selection (the Levenshtein trio) and must answer that; the detail names the no-ops |
| `health_ready` | `/health` is 200, the boot snapshot says `ready: true`, and the detail prints how long the boot took (`ready, 6 stages, booted in 4.4 s`) — from the registry's two-clock snapshot (`elapsed_s` is the boot, `uptime_s` the process) or, for an older snapshot, the span from the first stage's start to the last stage's end; never the uptime (round 1 printed `in 1296 s` after a long QA session) |
| `shared_stamp` | the footer's `build <sha>` is a prefix of the staged `.shared_sha` (the tool's `footer_stamp` does the same). The shared shell prints the first twelve characters (`shell.SHORT_STAMP_CHARS`) with the full sha in the span's `title`; both regexes (`STAMP_RE`, `verify_remote.SHA_STAMP_RE`) read the literal, the `\"`-escaped and the `\u003e`-escaped spellings, tolerate attributes after the class and accept 7 to 64 hex — a 64-hex stamp wrapped to three lines at 375 px in round 2 |
| `console_clean` | zero `console.error` / page errors across the landing page and every tab, at 1440 and 375 px |
| `no_horizontal_scroll` | `scrollWidth <= clientWidth` on every tab at 375 px |
| `targets_44px` | every visible link, button, input, tab and summary is at least 44 × 44 px (half-pixel slack). A form control wrapped in its `<label>` is measured by the label (a click anywhere on it focuses or toggles the control); elements with `tabindex="-1"` are skipped (Gradio keeps a clipped, unfocusable copy of the tab strip for measuring). Every dropdown on every tab, viewport and theme is then opened (a click on its combobox), each option of the open listbox (`[role=listbox] [role=option]`) is measured as a target and Escape closes it; a dropdown that does not open or close is a failed sample, and the detail says how many listboxes were opened |
| `axe_serious_critical` | axe-core reports no serious or critical violation on any tab view in any context — 1440 and 375 px, light and dark (28 views a run) — in both phases; the detail says how many views and which phase; in the keyed phase the Governed controls must have been on the page (skipped loudly without `axe-playwright-python`) |
| `contrast_hero` | computed text/background contrast ≥ 4.5:1 on every text the design colours on its own: the headline and tagline, the header pills, the hero figure (`.alg-hero-num`, accent text on the card surface — 4.12:1 light / 4.23:1 dark in round 1, unmeasured then, measured now), every chip, the tiles' label, value and meta line (`.alg-stat-*`) and their open links (`.alg-tile-link`), card subtitles, reasons, notes and hints, lane names and values, the Ecosystem key/value rows, the boot rows, card footers, the licence line and the deploy stamp — plus the options of every opened listbox, the highlighted one included; the worst ratio leads the detail |
| `contrast_buttons` | the text on every visible button (`button`, `[role=button]`, the Duplicate pill) ≥ 4.5:1 against every stop of its fill at rest; one button per selector signature is then hovered (Playwright `hover`) and focused (`focus()`), disabled ones are measured as they are, and the selected tab's label is measured — light and dark. A gradient fill is measured at each stop; `opacity` along the chain is folded in |
| `contrast_code` | every CodeMirror token class painted in every visible Code block (`.cm-line`, its spans, the gutter) ≥ 4.5:1 against the editor's fill, light and dark; the Try tab's install chip is pressed first so its snippet has tokens; zero tokens on every tab is a failure, not a pass |
| `value_boxes_unclipped` | every visible `input[type=number]` sits inside its parent and its block (1 px slack) and its value fits its own width (canvas `measureText` in the box's font) |
| `no_stock_chrome` | on the desktop, in each theme, the Try run button and the Ecosystem refresh button are pressed and the page sampled 100, 400 and 800 ms later: no visible `.progress-text`, `.eta-bar`, `.meta-text`, `.progress-bar`, `.generating` or toast, and no painted colour in Gradio's orange band (hue 15–40°, saturation ≥ 0.6, lightness 0.35–0.78; the fleet's own tokens are resolved and exempt) |
| `nav_separators` | at 375 px, no wrapped row of the nav or footer links starts or ends with the `·` separator, and no row is a separator alone |
| `checkboxes_dark_unfilled` | in dark mode every unchecked checkbox has an unsaturated fill (saturation ≤ 0.25) |
| `no_identifiers_in_copy` | on the desktop, light theme, every element with its own visible text on the landing page and each tab is scanned — outside code blocks (`.cm-editor`, `code`, `pre`, `.alg-result`), form values (`input`, `textarea`, `select`), the open listbox, the hidden restore box, accordion bodies (the `.alg-disclosure` header button is copy, its body is not) and the chips that print an error code (`data-kind="unavailable"`, `.alg-chip-code`, `[data-code]`, or the text `unavailable · <code>` — the fleet's one lowercase snake_case convention) — for a snake_case token, an ALL_CAPS name with an underscore (an environment variable), a `torch<N>-` build-variant string or a raw `https://` URL. The one allowance is the Playground's contract labels: the parameter names in its form (`.alg-form label`, `.alg-field label`) and the function's dotted name on its result card. Hits are grouped by selector signature with the tab, the token and the sentence, so each residual names its owner |
| `cls_budget` | three fresh loads of `?tab=<id>` per tab at 1440×900 and 375×812, a `PerformanceObserver` for `layout-shift` installed before navigation, observed for 2 s after the boot hold lifts: every load ≤ 0.05; a load over budget names its largest shift with the nodes that moved |
| `permalink_truth` | ten link shapes (`PERMALINK_SHAPES`) loaded at 1440×900 light and 375×812 dark (20 loads): the box under the strip is read together with every control of the displayed form (`_JS_FORM_STATE`: comboboxes, number and text inputs, checked radios, checkboxes, JSON editors, each with its label) and `permalink_problems` names every promise the form does not keep — a `fn` the form does not show (Playground: module and function comboboxes; Races: the candidate's title; Try: the hero function), an argument no labelled control carries (a `size` is a checked radio), a tab the strip does not show, a box without a tab. Seven shapes are round 2's findings (arguments without a function, `"north"` for a number box, `12.5` for a whole number, a foreign function on Try, an unknown tab, `XL`, a non-candidate function); three are full restores the tab must apply in full and the box must keep (`play_levenshtein`, `race_levenshtein_L`, `try_ints`) |
| `dropdown_dismissal` | every dropdown of every tab is opened and dismissed three ways without choosing — a click away (on the page title), Tab, Escape — and the form snapshot before and after each must be identical (`_form_diff`: every control's value, the checked radio, the number of visible fields); the dismissed box's `aria-expanded` must be false. 15 dismissals over 5 dropdowns a run; round 2's Playground cascade on blur is what it catches |
| `no_toasts` | never a visible `.toast-body`: sampled on the landing page after the load, at 100, 400, 800 and 3,000 ms after every tab's run button is pressed (Try and Ecosystem in both themes, every other tab once — the Governed run when its key is set, recorded as `(disabled)` and not pressed otherwise), and once more after the context's last run has settled (no `data-kind="loading"` chip left, 40 s budget). The detail counts samples and presses per tab |
| `boot_card_timings` | the boot disclosure is opened and every stage row read: a row prints the time `/health` records for that stage (`finished_at − started_at`, ±0.06 s of the card's `0.0 s` rounding) and a stage that ran ≥ 0.05 s never prints `0.0 s`; the rows sum to the `booted in` foot (±0.06 s per row + 0.1 s) and the foot is the snapshot's boot (`boot_duration`). Round 2's `kernels 0.0 s` beside `warm in 1.7 s` (progress events restarting the stage clock) is what it catches |
| `footer_stamp_one_line` | at 375 px, in both themes, `.alg-shell-stamp` renders on one line (rect height ÷ line-height) and reads `build <7–64 hex | dev>`; the detail names the form (`12 hex`) and the size |
| `exact_integers` | `2^53 + 1` (`9007199254740993`) through both paths of the Playground: the API call sends it as a JSON number and the accepted answers are the exact echo in the Request JSON or the contract's refusal (`playground.REASON_ABOVE_BROWSER_RANGE` — a whole number at or above `BROWSER_EXACT_MAX` is refused because a client's JSON double cannot be told from a browser's rounded one; the exact route is the snippet under Reproduce) with nothing run; a float, a `2^53` echo or a refusal beside a request that still carries a value fails. In Chromium it is typed into the default form's `n_a` box and Run pressed — the Request JSON must carry it exactly, or a message must appear under the field; a request that silently carries `9007199254740992` fails. Round 2 measured the silent rounding |
| `srlive_no_raw_keys` | Gradio's own screen-reader status region (`div.sr-only[role="status"]`, the client's StatusTracker, re-created per request) never carries a bare i18n key: every tab is clicked and the Try tab's Run pressed at 1440 light and 375 dark, the region sampled every 100 ms for 4 s after each (`SR_SAMPLE_MS`, `SR_WINDOW_MS`) and no sample may match `BARE_KEY_RE` (`^[a-z_]+(\.[a-z_]+)+$` — round 12 heard `common.complete` after every request, a key Gradio 6.28's English catalogue lacks; the app hands the mount a catalogue entry, `app.SR_TRANSLATIONS`, so the region says `Request complete`); the Space's own `.alg-status` live region must have announced the run (`running now`, `done in …`). The detail says what both regions said |

`targets_44px` measures a radio or checkbox by its `<label>` (a click anywhere on it toggles the
control) and a text-like control — number, text, range, textarea, the dropdown's combobox — by
the bordered field around it: the input itself when it carries the border, the wrap around a
borderless inner input otherwise (the Dropdown's 39 px box is measured as 39 px, not as its 17 px
input). When targets remain under 44 px the detail lists them grouped by selector signature
(`a.alg-shell-nav-link ×84 (e.g. desktop/light/landing 'Docs' 31x44); button.reset-button ×28 …`),
so the owner of each residual is named. The open listbox is part of the same pass: round 1's
audit never opened a dropdown, so 338 × 35.6 px options on the Playground, Races and Ecosystem
tabs passed a gate that read "1034 targets, all ≥ 44 px"; the gate now opens each of the five
dropdowns in all four contexts (20 listboxes a run), measures every option and reads its text
against the option's own fill — the highlighted and the selected row included — and closes it
with Escape, so a value never changes.

The browser checks share one headless Chromium session per base URL (cached) over four contexts
— desktop and phone, light and dark — and skip with their reason when Playwright is not
installed; a skip is always printed, never silent. The CLS pass is a second cached audit of its
own (36 page loads), so the per-check budget applies to each pass separately. Every measurement
first waits for the boot hold to lift (`html.alg-booting`, below), so nothing is measured on a
page that is still being assembled.
Unavailable cards are read through their code (`data-kind="unavailable">unavailable · <code>`),
so a check tells a documented state from a broken one, and a `gradio_client` exception is a
failed check with the endpoint's name, never a crash of the run.

### Goldens (`tests/spaces/visual/`)

```sh
# the app in the DEPLOYED state: as the Space runs it — SPACE_ID and SPACE_HOST set, the network
# on so the Hub counts are fetched at boot, the baked cache for the kernels
SPACE_ID=thyn-ai/algenta SPACE_HOST=thyn-ai-algenta.hf.space \
  HF_HOME=<hf-home> HF_HUB_OFFLINE=1 GRADIO_SERVER_PORT=7860 python app.py   # from the staged dir

# capture 36 goldens from that app (intentional pixel change, same PR) — the one command
venv-flagship/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:7860 --regenerate

# compare without pytest (exit 0 match, 1 drift, 3 another state — refused, not compared)
venv-flagship/bin/python tests/spaces/visual/_goldens.py --url http://127.0.0.1:7860

# the gate itself (slow, needs a launched app)
ALGENTA_FLAGSHIP_URL=http://127.0.0.1:7860 venv-flagship/bin/python -m pytest \
    --confcutdir=tests/spaces tests/spaces/visual -m slow -q
```

Grid: `?tab=<id>` for the six tabs × `desktop` 1440×900, `tablet` 1024×768, `phone` 375×812
× `light`, `dark` (`color_scheme` emulation), device scale 1, full page. `manifest.json`
records file, tab, viewport, theme, the viewport's `width` × `height`, the picture's own
`image_width` × `image_height` (a full-page PNG is as tall as the page — round 3's manifest
labelled the viewport as the image size), format, `full_page`, sha256 and bytes for every
golden, the thresholds in force and the **state** the set pictures (`state`: `hero_status`,
`hub_state`, `space_id`; `hero_status` is kept at the top level for older readers);
`_check_manifest()` refuses a missing file, a sha, byte or pixel-size mismatch, a file over
500 KB, or a tab without a golden.

Regeneration is one command and reproducible by construction — or it refuses:

1. **State precondition — the deployed state.** `--regenerate` reads `/health` and `/config`
   first and refuses (exit 2, every reason printed, then the one command above) unless the app
   is what the Space is: `hero.status == "measured"` (the not-recorded card is a different
   layout, and a golden that pictures a loaded build host would fail on every quiet CI runner),
   the Ecosystem table carries the Hub's live counts (`hub_state: fetched` — outside a Space
   nothing is fetched at boot and the tab draws a three-column table under a quiet
   `hub_counts_not_fetched` card, a layout the deployed Space never shows; round 3's committed
   set pictured exactly that and 6 of 36 goldens failed on size against the same build 40
   minutes later) and `SPACE_ID` is set. `--accept-hero-status noisy`, `--accept-hub-state
   <code>` and `--allow-local` record another state deliberately, never by accident. The
   Ecosystem pages are read again during the capture and a table in another state than
   `/config` promised is refused, not captured. One more state the manifest cannot record:
   the Races board (`races.Board`) lives in the process's memory, so regenerate from a freshly
   booted app before any Run is pressed — round 12's first capture followed two verifier runs
   and pictured two board rows (race-phone 473 px taller than the empty board every fresh
   boot shows). **The golden state rule:** the committed set
   pictures the deployed state and nothing else; a comparison — the CLI or the pytest gate —
   first reads the live app's state and, when it differs from the manifest's or the manifest
   records none, refuses loudly with the reason (`[SKIP] the goldens picture another state than
   the app serves: Ecosystem Hub state 'fetched' in the goldens, 'hub_counts_not_fetched' live;
   Space 'thyn-ai/algenta' in the goldens, 'none' live — not compared`, exit 3; `pytest.skip`
   with the same words on the state test and on every diff) instead of failing six Ecosystem
   size diffs or passing.
2. **Fixed fonts.** The capture waits for the boot hold to lift (`verify_checks.select_tab` blocks
   on `html.alg-booting`), then for the fonts in three steps (`_wait_for_fonts`, before and after
   the tab is brought to the front): the families' `@font-face` rules exist (`FONT_FACES_JS` —
   Gradio injects them only when the app mounts, ~370 ms after `domcontentloaded`, and until then
   `document.fonts` is empty, which reads `status === "loaded"` and `check()` true for every
   family), the four faces the design paints with are force-loaded (`document.fonts.load` for
   `FONT_SPECS`: Inter 400/600, JetBrains Mono 400/600 — a weight no text has asked for yet stays
   `unloaded` and `check()` answers false for it), and every one reports loaded
   (`FONTS_LOADED_JS`); `verify_checks.fonts_missing` then refuses the shot when a family is
   still missing — 36 shots of the wrong font are not a baseline. Round 4 measured why the status
   alone was not enough: the proof capture refused 2 of 36 goldens (`llm-phone-light` 108 px,
   `race-desktop-dark` 37 px — the same counts on the next visual run, then 5 other files on the
   run after) and the odd shots were the metric-matched fallback face on every text row: the same
   layout, glyph advances off by 0.4–3.4 px per row, the display headline (already Inter 600)
   unchanged; eight reloads of one page through the tool's path were byte-identical, and the
   timeline showed the gate passing at t+6 ms with an empty `FontFaceSet`.
3. **Motion off.** `FREEZE_CSS` (transitions, animations, caret) plus `animations="disabled"`
   and `reduced_motion="reduce"`.
4. **Every measured number masked.** The regions a second run legitimately changes are painted
   with the theme's own `surface-2` token (`design.COLOR_TOKENS`) so no colour outside the token
   set appears in a golden — and they are masked as blocks, so a number that grows a digit and
   pushes its neighbours never reaches the diff either: card footers (hardware · UTC), the deploy
   stamp, the header pills (`N families warm in X s`), lane charts and lane tables (median, MAD,
   CV, P95, min – max), every `.alg-lane-val`, the Ecosystem table body and its head chips (live
   downloads and likes), the race board's rows, hero numbers and labels, **every chip row of a
   result or held card** (`.alg-card-result .alg-chips`, `.alg-card-warn .alg-chips`: n, P95, MAD,
   spread, parity, version, `measured …`), `measured` chips wherever they stand, the status rows
   (`done in 6.07 ms`), every `<time>` stamp (`time[data-stamp-kind]`, `time.alg-time`), the boot
   rows' timers, details and foot, anything tagged `data-golden="mask"`, and — matched by text,
   so a new tab needs no registration — every leaf element whose text carries a `YYYY-MM-DD
   HH:MM UTC` stamp (`page.get_by_text(UTC_STAMP_RE)`). The rule: a golden pictures layout, type
   and colour; a measurement belongs to the gates that read it as a number. Round 2 measured why:
   the committed Try goldens read `P95 0.20 ms`, the build under test `P95 0.14 ms` — 151 raw
   pixels that the old blur-and-3×3 filter reduced to 2, under the 0.1 % threshold — on chips
   that were not masked.
5. **Settled.** The capture asks for `?tab=<id>`, selects the tab itself through the strip or
   Gradio's "More tabs" overflow (`select_tab`, which also waits for the lazily mounted panel),
   then takes viewport shots 400 ms apart until two in a row are byte-identical (a table filling
   in, a snippet mounting). **Every page is then loaded again in a fresh context, and the shot
   counts only when two consecutive loads encode byte-identically** (`_capture_agreed`,
   `LOADS_TO_AGREE` = 2, up to `LOADS_MAX` = 5 loads; a page that never reproduces itself is
   refused with the reason; a load that rendered differently is named on stdout). Round 4
   measured why one load proves nothing: with the fonts gate closed, 2–3 of 36 loads per pass
   still rendered every text row of the page in another anti-aliasing — word starts and widths
   identical to the pixel, glyph stems crisp in one load and spread over two pixels in the other
   (up to 90 of 255 apart; 6,500–8,600 pixels off before the 1-px tolerance, 35–158 after it),
   inside the viewport as much as below it, for the whole life of that load (consecutive
   viewport and full-page shots of one load always agreed with each other and never with another
   load) — with no DOM signature (scroll 0, visual viewport scale 1, identical fractional rects,
   the same loaded faces, read on every shot of the tool's own loop by `probe_capture_geom.py`)
   and unchanged by `--disable-gpu` / `--disable-gpu-rasterization` / `--disable-lcd-text`
   (normal shots byte-identical with and without them): a state of the renderer that loaded the
   page. Widening the channel tolerance to absorb it would need 96 of 255, which would also pass
   a text-colour change, so the tolerance stays at 24 and the capture asks the page to reproduce
   itself across loads instead. Two odd loads can still agree with each other (the round's tenth
   visual run: five pages needed a third or fourth load and two odd pairs slipped through), so
   **a pixel difference must also reproduce**: the compare paths (`_compare_all` with the app's
   URL — the CLI, the `--regenerate` proof — and the pytest gate) capture a differing page once
   more, two agreeing loads in a browser of their own (`_recapture`), and the second reading
   decides; both readings are printed (`… on the first capture; did not reproduce on a second
   agreed capture`). A real drift differs on every load; a size change is drift without a
   retry. `test_a_golden_difference_must_reproduce_on_a_second_agreed_capture` pins the rule.
6. **Proven, or refused.** `--regenerate` does not stop at writing: it takes a second capture of
   the same app, diffs it against the goldens it just wrote and fails (exit 1) when any golden
   differs, printing every row and then `[FAIL] first difference: <file> <what changed>` on its
   own line — a baseline the same page cannot reproduce twice is not a baseline and must not be
   committed. `--no-verify` skips the proof for a quick look, never for the committed set. The
   manifest records the contract the capture enforced (`fonts`, `motion: off`, the `masks`,
   `hero_status`). The compare path prints the same first-difference line, and a manifest entry
   without a fresh shot counts as drift, never as a pass.

The committed set is regenerated by the Integrate stage with that one command against a
`measured` opening card, once every implementer of a round has landed — never mid-round.

The diff (Pillow) is strict on every unmasked pixel. A pixel of either image counts as changed
when no pixel of the other image within `AA_TOLERANCE_PX` (one pixel, in either direction —
the reference's 3×3 min and max per channel) matches it to `CHANNEL_TOLERANCE` (24 of 255) in
every channel: a glyph edge that moved by a sub-pixel finds its match next door, a digit that
changed does not. One changed pixel fails (`PIXEL_THRESHOLD = 0`), as does any size change;
there is no blur and no neighbourhood filter any more. Proven in
`tests/spaces/test_flagship_verify.py::test_diff_fails_on_a_one_digit_change_in_an_unmasked_caption`:
`P95 0.20 ms` drawn with Pillow's font against `P95 0.14 ms` at the same position fails (20
pixels differ), the same caption drawn one pixel to the right passes, two pixels to the right
fails; a committed golden against itself is identical, and against a copy of itself shifted by
one pixel is identical too. The difference mask is written next to the fresh shot
(`ALGENTA_GOLDEN_WORK`, else a pytest tmp dir); `ALGENTA_GOLDEN_DIR` points the gate at another
golden set (a scratch capture in QA). A golden over 500 KB falls back to the viewport alone,
then to JPEG q80, and the manifest says which (`pixel_threshold`, `channel_tolerance` and
`aa_tolerance_px` record the rule in force).

`--confcutdir=tests/spaces` keeps the repository's root `conftest.py` (alembic, Postgres)
out of the flagship venv; the unit suite runs with the system `python3` as every other
`tests/spaces` test does.

The pytest gate (`tests/spaces/visual/test_flagship_goldens.py`) first asserts the manifest is
consistent, then that the manifest's `hero_status` equals the live app's (skipping with a note
when the manifest predates the key), then the 36 diffs — so a state mismatch is one named
failure, not six Try-tab diffs. Measured 2026-09-22 (round 3, the strict diff): two consecutive
captures of the same running app are identical on all 36 goldens — 0 pixels beyond the 1-px
tolerance — see the round-3 QA table for the run.

The committed goldens are the previous round's baseline and predate this round's tab changes;
running the compare against them prints the first differing row and exits 1 by design until
the Integrate stage regenerates them.

## Tabs A — Try it, Playground, Races (`tabs/try_tab.py`, `tabs/play_tab.py`, `tabs/race_tab.py`, `races.py`)

### The tab contract (`tabs/__init__.py`)

Every tab module exposes `build(deps) -> TabSpec`. `TabSpec(id, label, render, api_names,
connect)`: the shell opens `gr.Tab(label, id=id)`, calls `render(gr)` inside it (the module is
passed in, so no tab imports gradio at module level and the unit tests build fakes without it)
and receives the tab's named components; once every tab exists it calls `connect(gr, tabs,
handles_by_tab_id)` for the specs that link across tabs — the Try tab's "Race it against Python"
chip selects the Races tab and preselects betweenness. `Deps` is what the shell has at boot:
`kernels` (short family → `hubkernel.LoadedKernel`), `lane` (the one `Lane`), `facts`, `limits`,
`killswitch`, `hero` (a `HeroResult` from `try_tab.measure_hero`, measured before `launch()`),
`hardware` (the rulebook footer line), `kernel_errors` (families that did not load, with their
code — rendered as the unavailable card) and `env`. `Limits` is consulted on the lane kind
`native` when the shell's policy names it; the kill-switch features are `kernels` (Try and
Playground) and `races`. `tabs/common.py` holds what the three tabs share (lane chips, the call
card, tiles, https-only fetches that never raise, `TABS_CSS` — the shell appends it to
`fleet_css()`).

**The chip colour rule** (`cards.CHIP_KINDS`, one rule): colour is meaning. A state that is
not a result — `unavailable`, `not_configured`, `held`, `not recorded`, `loading` — is neutral,
`text-2` on `surface-2`, the same pill as `measured` and `n = 21`; the unavailable card is quiet
(hairline, neutral chip, no red). Red (`err`) is for `error` alone: something failed *during a
run* — a parity check that did not hold, a call that raised, a lane that refused the visitor's
run, a fetch the visitor pressed for that did not answer — and `code_chip(code, error=True)` is
that pill, `cards.render_error_card` (`render_unavailable_card(error=True)`) the card. The call
sites are `tabs/common.error_card` (a `LaneError`, a `HubKernelError`, `call_failed`),
`llm_tab.render_failure_card` (`parity_failed`, the engine errors the Governed tab maps, a
pressed Ecosystem refresh that failed); every documented state at rest — not configured, not
loaded here, not fetched yet, held, not recorded — goes through `cards.render_unavailable_card`
/ `render_not_configured_card` (`llm_tab.render_quiet_card`) and stays quiet. The verifier reads every code through one DOM contract whatever the colour
(`data-kind="unavailable">unavailable · <code>`), so a documented state and a run failure are
told apart by the tone and never by guessing at the text.

**The open listbox and the phone tab strip** (`css.CHROME_CSS`): the dropdown's `ul[role=listbox]`
is a panel on `surface` with a hairline, the card radius and the fleet shadow, each
`li[role=option]` a 44 px row in the body face with an 8 px radius, `surface-hover` under the
pointer and `surface-2` when selected — `targets_44px` opens every listbox and measures the
options (46 px rows on 2026-09-22, 35.6 px in round 1), `contrast_hero` reads their text. Below
`PHONE_MAX_WIDTH` the tab strip no longer folds tabs into Gradio's "More tabs" menu: the tablist
is sized `max-content` inside a wrapper that scrolls horizontally with no scrollbar chrome and a
snap point on every tab, the overflow button is hidden because nothing overflows, and
`shell.TABSTRIP_SCRIPT` (in `BOOT_HEAD`) scrolls the selected tab into view on load and on every
selection, so `?tab=eco` opens with Ecosystem in view. `verify_checks.select_tab` still handles
both shapes (a tab button anywhere in the strip, or the menu when a build folds) and, on the
snapping strip, a pointer click that misses: Playwright scrolls the tab into view, the snap
moves the strip under the pointer and the click lands on a neighbour (measured at 375 px:
`race` clicked, `play` still selected, for every tab that had to scroll) — after 2.5 s without
the selection the button is scrolled into view, the snap given 300 ms to settle and clicked
through the DOM, which cannot miss. A visitor drags, then taps; the harness needed the fallback,
the page did not change.

A tab that refreshes a panel on page load (the Ecosystem table, the LLM tab's GPU tile) returns
`handles[LOAD_HOOKS] = [(fn, outputs), ...]` and the shell registers each with
`blocks.load(fn, None, outputs, api_name=False)`. A component built with a callable `value`
would register the same load event, but Gradio names that endpoint after the function
(`/lambda`, `/initial_state`) and lists it in `/gradio_api/info`; the handle keeps the API
surface equal to the tabs' `API_NAMES` (the verifier's `expected_api_names`).

### Try it (`try`)

Opens on `deps.hero`: `ab_testing.z_test_proportions(50, 1000, 65, 1000)` measured under
rulebook v0.6 (`RULEBOOK.md`) through the lane — one algenta lane, the correctness gate is the parity check
against `statsmodels.stats.proportion.proportions_ztest` (z within 1e-9, p within 1e-6 —
`try_tab.Z_TOL` / `P_TOL`; the kernel's normal CDF differs from statsmodels' by 8.6e-8 on p for
the card example and by 1.4e-7 at worst over 408 inputs, so the card never claims 1e-7 or
1e-12 for p), then 2 warm-ups and 21 interleaved samples, each k back-to-back calls lasting at least 10 ms
(`bench.SAMPLE_MIN_MS`; the per-call time is the sample over k, and the card's n chip says so:
`n = 21 × 103 calls`, `cards.n_chips` / `try_tab.repeats_label`). The card: in-kernel median as the hero, z
and p, the parity bound that was checked, `n`, P95, the transport note, `measured <UTC>`, the
machine line. Four number inputs and Run re-measure live (`try_run`, on the native queue);
validation is the contract's (`playground.parse_inputs`, `try_tab.check_args`) and a refusal is
one sentence with the field's label in front (`Successes A cannot exceed Trials A.`), printed in
the status row beside Run (`common.render_status`) and cleared by the next edit — the fleet's
convention also asks for that sentence under the offending box, which this one-row form (Run on
the boxes' baseline) does not place yet; the `refusal_convention` gate names it (open, round 4).
Chips: `try_snippet_install` / `try_snippet_mcp` render the `kernels` and MCP snippets with the
visitor's numbers into one `common.code_editor` block captioned `Install` / `MCP request`
(`render_code_caption`; the stock block label and line-number gutter are off, as on every
read-only code block of the flagship). "Where this runs" is a band of the design system's stat
tiles (`cards.tile`, the same geometry in every state) whose figures are computed, fetched or
measured and carry their `counted <UTC>` stamp — never typed: Hub kernels (the functions and
families loaded in this container, counted from the loaded contracts at boot), Hosted API + MCP
(the tool count from `algenta_mcp.registry.TOOLS` when the package is installed, else from the
live `https://api.algenta.ai/mcp/tools`, each labelled with its source in words — `counted at
boot` for the registry, `live · hosted API` (`try_tab.LIVE_HOSTED`) for the endpoint, the host
itself never in the tile's copy (`cards.hostname_token` is the check); unreachable →
`mcp_tools_unreachable`) and — only when the Space variable `ALGENTA_GPU_STATUS_URL` names the
GPU stage's https status endpoint (`gpu_status.configured`) — the GPU stage tile, refreshed by
`try_gpu_status` every 30 s; when the stage does not answer, "GPU stage offline — last measured
N tok/s · <UTC>" from the results Dataset's `gpu_status.jsonl` (`ALGENTA_GPU_LOG_URL`; each line
is one status record in the `gpu_status.parse_status` contract) or the code with no number.
Without that variable the band is the two real tiles — nothing stands in for a stage that is
not wired. Without statsmodels the hero card carries no parity chip — nothing is invented.

### Playground (`play`)

`Catalogue` describes each loaded family once (`hubkernel.describe`); family → module →
function dropdowns (`play_modules`, `play_functions`, `play_form`). The form is `MAX_FIELDS =
24` static slots (the widest published function takes 24 arguments), each with a number box
(`precision=None` for every numeric kind: the box keeps what the visitor types, decimals
included, and `parse_inputs` refuses `2.5` for a whole-number parameter with one sentence under
the field — round 1's `precision=0` rounded London–Paris to whole degrees before the call), a
checkbox, a text box and a JSON code box; `slot_plans` shows the slot of each parameter's kind
with its label and help and hides the rest; hero functions are prefilled with the plan's default
arguments, and changing the family, module or function returns the card to its empty state and
refills the Request and Reproduce editors for the new function (an editor is never shown
empty). `play_run` (native queue): `parse_inputs` →
`ValidationError` is said twice, never as a traceback — a field message under the offending
control (`common.render_field_message`, `role="alert"`) and the same sentence echoed in the status
row beside Run (`common.render_status_echo`, `role="status"`; Run sits far below a long form) —
while the card returns to its empty state and the Request-and-response disclosure hides the
request editor behind `REQUEST_REFUSED_NOTE` (never the previous run's request beside arguments
that did not run; the Reproduce editors keep the last call they showed, which is where the 2^53
refusal points) → `lane.submit(execute)` with
the position/ETA chip → the call card (a parity chip only when `races.reference_for` finds an
installed reference for the function: nltk, networkx, sympy, py_vollib, geopy), the request and
response JSON, the `kernels` / SDK / MCP snippets with the visitor's arguments, and a permalink
`?tab=play&fn=module.function&args=<json>` (restored by the shell's Permalink component). Every
dropdown allows a custom value, so an API or MCP client can name any family, module or function
and the handlers answer, not Gradio: a selection this container does not serve
(`selection_refusal` — `unknown_family`, `unknown_module`, `unknown_function`, or the family's own
load code) snaps the box back to the applied choice, echoes one sentence in the status row and
puts the quiet coded card in the card slot (`family_dropdown_foreign_value` holds it); a typed
filter blurred half-way is a dismissal that snaps back and moves nothing else. Every read-only
code block (request, response, the three snippets) is `common.code_editor` with its caption
(`render_code_caption`) — no stock block label, no line-number gutter (`no_stock_code_labels`);
the JSON *input* boxes of the form keep Gradio's label, because there it carries the parameter's
name and help.

### Races (`race`) and `races.py`

Five candidates as data (`races.CANDIDATES`), each a Hub-kernel function against the library
it replaces over seeded S/M/L workloads (`BASE_SEED = 20260922`, seed and size printed on the
card): Levenshtein/nltk, betweenness/networkx, closeness/networkx, option-chain Greeks
(1,000 · 5,000 · 20,000 options)/py_vollib, primes below N (the sieve, 500k · 1M · 1.5M — sympy's
lane must fit the 20 s cell budget on the shared host)/sympy.
**Round 7 autopsy (2026-09-23, this Mac, published packages):** a race is offered only where the
kernel's compute dominates the call. A scalar call costs 15–20 µs here — 12–13 µs of it the C
ABI round trip (parse, dispatch, serialize a 100-byte request) — and 70–90 µs on the shared
EPYC host, which inlined Python arithmetic (geopy 7.9 µs, sympy.isprime 5 µs) beats every
time; a 20,000-token bigram count spent 19 ms on 158 KB of JSON in (to_plain 2.6 + normalize
2.8 + Mojo 7.2 + json 1.2) and 256 KB out (decode 4.9) against nltk's 2.3 ms, and an 8,000-edge
Dijkstra moved 500 KB for 26 ms of Mojo parse against networkx's 8.9 ms. Dijkstra, word bigrams,
Miller-Rabin and haversine therefore left the roster and stay Playground parity references
(`races.REFERENCES`); the sieve (78,498 primes below 10^6 in 25 ms vs 329 ms) and closeness
centrality (O(V·E), 3–7× at S/M/L, `scaled_values` == networkx to 1e-16) replaced them. The
same autopsy found two costs of our own inside the timed lane — `hubkernel.execute` deep-copied
the arguments and the function spec on every call (5–20 ms on a large list) — both removed. What
remains is the published glue's per-element Python passes (`to_plain`, `normalize_arguments`,
`decode_value`: a quarter to a third of a batch call) and the Mojo side's JSON at 20–40 MB/s (the
ABI adapter's depth scan, three key lookups and the count-relation check before the frozen
dispatch parses the request again) — the next two tracks (glue republish; a single-pass adapter).
A candidate is offered
only when its incumbent is installed and its family loaded (`races.offers`); the tab names
what is not offered and why. `race_run` runs `races.run_race` inside one lane job: two
`bench.LaneSpec`s under `bench.run_cell` (gate before timing, interleaved repeats, median /
P95 / MAD / CV, noisy → not recorded, 20 s budget). The result is the shared
`cards.render_result_card`, whose one lane table carries median, MAD, CV, P95 (or max under 20
samples) and min – max per lane (row cards with their column names on a phone), the card's
subtitle is the workload and the incumbent in words (`RaceRun.caption`; the kernel revision and
the exact calls are in the Reproduce disclosure), and the cell's permalink pill appears under
the card only once there is a measured cell to link to; changing the candidate or the size
returns the column to the empty card. Parity gates and their printed bounds:
exact match (Levenshtein; the primes list), every value within 1e-9 (betweenness), every defined
value within 1e-9 with unreachable nodes agreeing (closeness: the kernel's `scaled_values` are
networkx's default Wasserman–Faust closeness on outgoing distances, so the incumbent graph is
reversed; a node that reaches nothing is `defined: false` for the kernel and 0.0 for networkx),
price and Greeks within 1e-5 after py_vollib's per-1 % vega and per-day theta are rescaled. The
retired references keep their gates for the Playground's parity chip: reachable distances within
1e-9 (Dijkstra), exact match (bigrams, primality), 5e-6 relative for haversine (geopy's mean
radius is 6371.009 km, the kernel's 6371 km).

**Round 8 (2026-09-24, build 426431e49 on staging):** the journalist found nothing fake in six
tabs; the Google reviewer shipped four; the HIG reviewer's pixel ruler rejected two claims and
found one new one, all three confirmed by the adversarial verifiers on the live Space: pill
anchors (Duplicate this Space, the Try tiles' Open) and every accordion block measured 46 px —
a 44 px control inside its own 1 px hairlines — and the Playground field card inset its boxes
24 px (16 px on the phone) right of the dropdown card above it, its own padding on top of the
blocks' 16 px. The 44 px target now includes the hairline: pills are flex-centred 20 px lines
in a 44 px border-box, the accordion button is `calc(var(--alg-target) - 2px)` inside the
bordered block, and the form surface keeps only vertical padding so the blocks' inset lines up
with the dropdown card (measured: boxes and labels at x=193 under wrappers at x=193 at 1440,
33/33 on the phone). Two claims were refuted on the live Space — the governed press that showed
nothing for 90 s (3/3 presses painted the loading card at ~150 ms and delivered in ≤ 2 s) and the
Tab-arrival flash between comboboxes (the reviewer's sampler had opened the departed list with a
JS `focus()` before the Tab); what did reproduce, a one-row filtered stub of an OPEN list fading
under the departed box for ~230 ms after a Tab away, is closed by marking that box's existing
panel on the Tab keydown and whenever a box turns expanded while unfocused. Also from this round:
card titles are `h2` under the page's `h1` (axe `heading-order` on every tab), the hero label
says `per kernel call` instead of `in-kernel` for a timing that includes the marshalling, the
races' How-measured text states the qualification file's own rule (three recorded runs within
five presses), and — at the owner's request — the Space names Mojo where a visitor looks first:
the headline (`6,040 compiled Mojo kernels`), the header pill (`19 Mojo kernel families ·
this container`), every measured card's chip (`compiled Mojo kernel over the C ABI · includes
JSON marshalling`), the Try tile (`Mojo kernels on the Hub`) and the Hub card's description and
first paragraph (`/health` proves it per family).

**Round 9 (2026-09-24, owner reviewing staging live):** three directives, all landed the same
day. (1) *Every field a visitor can act on opens with a value, never empty.* The contract names
types and length rules but no example values (16,139 of 16,335 parameters have no default), so
the Playground opened 5,980 of 6,068 functions with empty boxes — a struct parameter such as
`interval.interval_add(a: Interval, b: Interval)` showed two empty editors and "a is required".
`algenta_spaces.examples` now synthesises one argument set per function from the parameter's
name and type (a probability 0.5, a significance level 0.05, a p-value 0.03, London then Paris
for coordinates, a seed 42, a count equal to the list it bounds, an index 0, a struct field by
field) and `apps/spaces/tools/build_examples.py` runs every proposal through the Playground's own
guard and then through the compiled kernel in a watched child process (10 s per call; a hang or
a Mojo abort kills the child, which resumes from the next function and retries with the crash
gate's plain shapes). The result is `apps/spaces/algenta/examples/<family>.json` — 5,895 of 6,040
functions verified by their kernel on the first build (97.6 %) — and `play_tab.plan_defaults`
opens every function with the hero's arguments, else the verified file's, else a synthesised
set. The build also surfaced a hazard the crash gate did not: contract-valid inputs that HANG the
§9 worker (`regression_tree.predict_single` on a cyclic tree, `queue_ds.cb_*`,
`constraint.solve_n_queens`) or ABORT the process (`linalg_ext.mat_condition_number`,
`bloom_counting.cb_add` on an index past a bound). A visitor can type those into the Playground
today; the in-process lane cannot kill a native call — subprocess isolation for Playground calls
or ABI-side guards is the open item. (2) *One Space.* The org keeps the flagship only: the three
redirect stubs, `algenta-speed-arena` and `algenta-governed-agent` were deleted from the Hub
(their sources stay in `apps/spaces/` for the rebuild), `spaces.toml` names one Space so the
deploy workflow cannot recreate them, the header shows Flagship and Duplicate this Space, the
footer one Resources group. (3) The Ecosystem tab's "Everywhere Algenta runs" pill cloud —
every header and footer link again, in a ragged block off the left column — is gone. Also from
the local gate battery: the accordion button is now itself the 44 px hairlined target (a 44 px
block around a 42 px button failed the focusable-target gate).

**Launched (2026-09-24 ~03:00 UTC).** https://huggingface.co/spaces/thyn-ai/algenta serves the
flagship (deploy dispatched from the branch at c0b709822, then from main at 6915239fa after
PR #1150 merged); the production window recorded 4/4 hero presses (host load 1.8–2.2), verify_remote
3/3, 40/40 gates and the Races browser repro; the Space is pinned always-on on cpu-upgrade and is
the only Space in the organisation (`algenta-staging` deleted after the window).

Qualification is read, never decided in the Space: `qualified.json` from the results Dataset
(`ALGENTA_QUALIFIED_URL`, default
`https://huggingface.co/datasets/thyn-ai/algenta-arena-results/resolve/main/qualified.json`;
a list of race ids, a list of `{race_id, size}` records, or `{hardware_id, qualified: [...]}` —
a file stamped for another `hardware_id` qualifies nothing here). A qualified cell renders as a
race (ratio hero, or the hold-and-disclose card when the incumbent won this run — not
recorded); every other cell is parity plus both latencies with its measured ratio marked "not
qualified" (the figure is data, the status says the rulebook has not qualified it), never a ratio
hero. With no file (today the URL answers 401) the tab says "No race has qualified on this
hardware yet". Today the file is written on demand by `apps/spaces/tools/requalify.py` (every
offered candidate × size pressed through `/race_run` on the Space until three runs were recorded,
at most five presses; a cell qualifies when the kernel won all three recorded runs — a noisy press
is not a run, a recorded loss disqualifies), and it carries its own `rule` and `generated_utc`, which
the tab prints beside the qualified list so the copy can never claim more than the file. The
nightly `spaces-requalify.yml` that would rewrite it on a schedule is M4.

Leaderboard ("Measured on this Space", one responsive `alg-stack-table` — row cards on a phone —
with a `where` column reading `measured here`, or `published elsewhere` for Dataset rows once M4
lands; one quiet line while there are no rows): `races.Board` keeps this Space's winning rows
(qualified and won) in a ring of 200
and appends each as one JSON line to `ALGENTA_RESULTS_PATH` (default `/data/results.jsonl`)
when that directory is writable — columns `ts_utc, space_id, hardware_id, hardware, duel_id,
size, n, algenta_median_ms, incumbent_median_ms, p95, mad, cv, ratio, parity, harness_commit,
wheel_sha, incumbent_pin` (`hardware_id` = 12 hex of CPU quota · architecture — the machine class a tier fixes, stable across host migrations and a boot whose tier lookup failed; `wheel_sha` =
the revision that ran — `races.kernel_revision`, the Hub snapshot the module loaded from, never
the manifest's capped sha). Publishing those lines to the Dataset with
`huggingface_hub.CommitScheduler`, and the "published elsewhere" row type, arrive in M4; until
then the table is this container's and says "measured here".

Measured on the build Mac (M-series, `torch25-cpu-aarch64-darwin`, 2026-09-22, single warm
calls from the sizing probe, not rulebook cells): Levenshtein 500 × 500 characters 2.8 ms vs
110 ms nltk and 900 × 900 7.2 ms vs 410 ms; betweenness 200 nodes · 800 edges 13.4 ms vs
42.3 ms networkx and 400 · 1,600 44.9 ms vs 191 ms. Dijkstra (5,000 · 20,000: 265 ms vs 10.8 ms),
bigrams (60,000 tokens: 116 ms vs 10.1 ms), Greeks (5,000 options: 96 ms vs about 27 ms for
price and delta alone), primality and haversine (single scalar calls, 0.2–0.3 ms vs under
0.1 ms) lose to their incumbents because the JSON marshalling of large lists or a scalar call's
fixed cost dominates — they are offered as parity cells and stay "not a race" until
qualification says otherwise. Under rulebook v0.3 (one call per sample) with the Mac loaded by other work (load
average 25 on 16 vCPU) every cell, the hero included, came back "noisy — not recorded" — the
protocol's honest answer, and what the live test accepts beside `measured`. Rulebook v0.4
(fix round 5) times each sample over k back-to-back calls so a sub-millisecond cell is read
from the kernel rather than the scheduler on an idle host (`RULEBOOK.md` has the measured
sweep); a cell over the load gate (1.5 × the CPU quota) is still not recorded, and the
not-recorded card keeps the kernel's result and the parity chip (`cards.render_not_recorded_card`).

Kernel finding recorded while building the candidates: `number_theory.is_prime` on the capped
v1 `algenta-bits-time` returns False for every prime at or above 2^32 that was checked
(4294967291, 4294967311, 1099511627791, 999999000001, 281474976710677, 4503599627370449,
10^18 + 3, 2^63 − 25) while agreeing with sympy below (2147483647 is True). The Miller-Rabin
sizes stay at or below 2^31 − 1 (`races.PRIME_CEILING`), the gate still runs on every cell, and
the Playground's parity chip shows the disagreement honestly for a larger `n`. The frozen Mojo
baseline is additive-only, so the fix is a new kernel revision, not a Space change.

### Tests

`tests/spaces/test_flagship_tabs_a.py` (offline: the darwin contract fixtures behind a fake
`execute`, the real incumbents on seeded workloads, the real `Lane`, a fake clock so every
rulebook cell is stable; the UI-construction tests run only where gradio is installed) and
`tests/spaces/integration/test_flagship_live.py` (`ALGENTA_SPACES_LIVE=1`, `-m slow`: the hero
measurement on the real `algenta-stats`, a betweenness cell on `algenta-graph` vs networkx and a
Levenshtein cell on `algenta-text` vs nltk).

## Tabs B — LLM kernels, Governed, Ecosystem (`tabs/llm_tab.py`, `tabs/gov_tab.py`, `tabs/eco_tab.py`, `webhook.py`, `gpu_status.py`)

Same contract as Tabs A: `build(deps, **injected) -> TabSpec`, `render(gr)` inside the shell's
`gr.Tab`, the first `api_names` entry is the endpoint the live verifier calls (`llm_run`,
`gov_run`, `eco_refresh`). Error codes and hints are `tabs/common.py`'s (`kernel_not_loaded`,
`switched_off`, `rate_limited`) so a reviewer moving between tabs sees one vocabulary.

### LLM kernels (`llm`)

Three panels on `thyn-ai/algenta-llm` (CPU variant), each a parity check with both latencies —
labelled "not a race" because torch is C-backed: **RMSNorm** (`normk.rmsnorm.rmsnorm_fwd_flat`,
rows × cols sliders inside the contract's count relations, eps 1e-6), **RoPE**
(`attnk.rope.rope_table` + `rope_apply_flat`, tokens × heads × head_dim, rotate-half or
interleaved pairs, θ 10000) and **Sampling** (`llmk.generate.greedy_argmax_flat` over the
vocabulary, timed; plus the per-candidate `llm_sampling` formulas — `temperature_scale`,
`top_k_threshold`, `top_p_cumulative` — over the top-k candidates, whose kept set is checked
against the transformers warper order). Every reference is written in torch directly (float64,
CPU); transformers is not installed — the RoPE and sampling references are a few lines each and
live in the Reproduce accordion, which renders the visitor's shapes with the same seed as
compilable Python. Measurement: seed 20260922, 1 warm-up, 5 timed calls per lane, medians on the
`cards.render_result_card(race=False)` card; the kernel lane runs through the one native lane
(`budget_s` 20) and its time includes JSON marshalling across the C ABI. Tolerances printed on
the chip: RMSNorm 1e-9 (measured 1.8e-15), RoPE 1e-8 (the kernel's cos/sin drift ~2e-11 per
radian of angle: 2.5e-10 at 16 tokens, 1.3e-9 at 64 tokens × 128 dims — measured 2026-09-22 on
`torch25-cpu-aarch64-darwin`), greedy token id exact. A parity failure is the unavailable card
(`parity_failed`), never a result card. Measured warm latencies on an M4 Max: RMSNorm 8 × 256
9.6 ms vs torch 0.16 ms; 32 × 1024 136 ms vs 2.8 ms; RoPE 16 × 4 × 64 20 ms vs 0.29 ms;
64 × 8 × 128 ≈ 310 ms vs 8–19 ms; greedy over 32,768 logits 86 ms vs 1.5 ms. The GPU stage's live
throughput tile (below) sits under the three panels only when `ALGENTA_GPU_STATUS_URL` is set,
quiet when the stage is offline; the kernel lane is split once more into the Python side of the transport (`json.dumps` of the request
envelope, `json.loads` of a same-shape reply, measured on the same payload) and the remainder.

Layout (round 4): each panel is one stack — its controls two to a row (`CONTROL_MIN_WIDTH` each,
one under the other on a phone), the Run button under them across the panel (`RUN_VARIANT`, the
gradient primary every other tab's Run wears — round 12: three grey 240 px secondaries read as a
different control), then the result card across the panel's full width and the Reproduce disclosure — so a tall result never leaves a void
beside a short set of sliders (round 3 measured 469 px under the RMSNorm controls after a run; the
`voids` gate reads 0 gaps over 240 px now). The page at rest is taller for it on the desktop
(1,982 → 2,759 px). The two-column tabs (Governed, Ecosystem) moved to the shared two-column
contract in fix round 5 (the Ecosystem's SDK card still carries `STRETCH_CLASS` inside its column) (`css.LAYOUT_CSS`: `COLS_CLASS` on the row,
`CONTROLS_CLASS` / `RESULTS_CLASS` on the columns, `FILL_CLASS` on the card block — the controls
keep their natural height whatever the results do) after the final review measured
`equal_height=True` growing its Run button to 459 px and a slider block to 532 px under an open
Engine responses block.

### Governed (`gov`)

`HostedGoverned` (foundations) over the Space secret `ALGENTA_API_KEY`; `status()` once at
boot. `NOT_CONFIGURED` → the not-configured card (`hosted_not_configured`, "the tenant key is
not set") and every control disabled; the endpoints still answer with that card, and no other
path exists. Configured: profile radio (`observe` / `govern` / `execute` / `full`, the
integration contract's profiles mirrored as data and asserted against
`algenta-integrations/contracts/integration-tool-contract.json` when that checkout is present;
default `execute` so one click reaches the engine), action name, pessimistic / optimistic
values and a hold outcome (the two `NamedAction`s `/v1/recommend` compares, hold ± 1 %, `runs`
100 — the API minimum), the declared confidence (`Declared confidence`: the visitor's own,
`log_decision.confidence`) and the risk at the 5th percentile (`Risk (P5)`: `log_decision.risk_p5`,
the decision's pessimistic outcome — not the policy's risk floor it is compared against, which
stays the gate's name, `GATE_NAMES["risk_floor"]`), then **Run governed execution** (`gov_run`):
`recommend` → `log_decision` → `execute_decision`, stopping at the first tool the profile does
not expose (below) →
`execute_decision(webhook_url=<this Space>/hook/<nonce>)` → receipt card (engine status,
response code, integrity ids, the engine's webhook POST with its received stamp and what was
verified) or denial card ("Held by the <gate> gate", code, HTTP status, override hint). The
receipt's status chip is the engine's word in the tone of its outcome — `delivered · HTTP 200`
live on the quiet card, `webhook_failed · HTTP <code>` (or `no HTTP response`) red on the red
card with no `webhook received` block and no "reported delivery" note; the `receipt_tone` gate
reads that chip from the card the tab renders (round 2 painted `engine failed` in the live tone;
round 3's gate looked for an `engine <status>` chip the tab never paints).

**The per-tool profile gate (round 17).** The profile radio is the integration contract's four
profiles, and the chain is gated per tool, not per profile: `first_tool_outside_profile(profile,
CHAIN_TOOLS)` names the first of `recommend`, `log_decision`, `execute_decision` that the
profile's tool list (`PROFILE_TOOLS`; `*` under `full`) leaves out, and `run_chain` calls every
tool before it and none after — exactly as every algenta-* integration filters the tools outside
the profile out of the model-facing list. Under `observe` (`get_contract`, `query_data`,
`simulate`, `recommend`) the intercepted tool is `log_decision`: `recommend` runs, nothing is
logged, nothing runs, `state["decisions"]` and `last_decision_id` stay as they were, and the
audit row is `Decision log · intercepted · profile` with no decision id. Under `govern` it is
`execute_decision`: `recommend` and `log_decision` run and the audit row is `Execution ·
intercepted · profile · <id>`. `execute` and `full` run the whole chain (`EXECUTE_PROFILES` is
derived from the lists, never a second copy). The Outcome records `intercepted_profile` and
`intercepted_tool`, and `render_intercepted` tells that truth: the title `Not in the <profile>
profile`, the sub-line `before the <log|execute> call reached the engine` (the engine was called
for every step before it — the old `before the engine was called` was false under `govern`), the
sentence for the tool (`INTERCEPT_LOG_TEXT`: "Logging a decision is not in this profile; the
recommendation stands, nothing was logged or run." / `INTERCEPT_TEXT`: "Executing a decision is
not in this profile; the decision is logged and nothing ran."), and the steps list only what ran
— under `observe` the Recommendation row alone, no Decision or Chosen action row. The loading
card names the steps the profile will run (`loading_text`). **Execute again** after an observe
run has no logged decision to send and answers the quiet `no_decision_yet` card; under a lower
profile with a decision in the session, the repeat's one tool (`execute_decision`) is intercepted
by the same rule. The owner's production walkthrough found the observe card showing a decision
id and "the decision is logged and nothing ran" — `run_chain` logged under every profile and gated
`execute_decision` alone; `governed_profiles` now reads both lower profiles' cards in the keyed
phase. The same round named the two confidences apart on the card — `engine confidence 1.00`
on the Recommendation row (`Recommendation.confidence`, the engine's ranking confidence) and
`declared confidence 0.93` on the Chosen action row (`Decision.confidence`, the form's field) —
and the Chosen action row's `risk P5 0.02` (it read `risk floor`, the gate's name, for the
decision's own P5).

**The webhook verification model.** There is no signature: the engine's decision webhook sends
no header worth trusting, and `spaces.toml` sets no `ALGENTA_WEBHOOK_SECRET`. What makes a POST
the engine's is (1) the per-boot nonce in the URL, passed to the engine and printed nowhere —
`/health` names the route's prefix and whether it is public (`webhook: {prefix: "/hook",
public}`, `app.public_health`; `Hook.path` is that prefix, `Hook.url()` the absolute URL with the
nonce that only the engine receives), the receipt's `Webhook` row names the host alone
(`WEBHOOK_ROW_TEXT`: `this Space's webhook · <host> · nonce hidden`, from `Outcome.webhook_host` —
round 4's first run printed `https://unreachable.invalid/hook/<nonce>` there), and
`webhook_privacy` holds both; (2) the **session match**: before `execute_decision` the tab arms the decision id it just
logged (`hook.expect(decision_id, integrity=…, chosen_action=…, confidence=…)`), a POST naming
an unarmed, already served or settled decision is refused, and one POST is accepted per arming;
(3) the **integrity match**: the POST's `integrity` block must carry the three ids
`log_decision` returned (`policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`) and its
`decision` summary the chosen action and confidence this session sent. A refused POST answers
400 `{"received": false}` with the reason kept in the hook's ledger, never on the page; round 3
measured a forged POST to the published `/hook/<nonce>` painted `webhook received · nonce
verified` in the live tone on a failed receipt, which none of the three checks now allows.

**Execute again** (`gov_execute_again`) re-sends the session's last decision id with the
schema's operator-only `force` / `override_safety` boxes labelled as such. **The idempotency
behaviour is the engine's and differs by outcome:** after a *failed* execution the engine
executes the decision again and answers with a new receipt (a new `executed_at`; round 2 and
round 3 only ever saw this path, because every local execution had failed — this Mac has no
public https address); after a *delivered* execution the engine's policy service holds the
repeat at the idempotency gate (`already_executed and not allow_reexecution and not force` →
409 `execution_blocked_idempotency`), which the tab renders as the denial card "Held by the
idempotency gate" with the override hint, and `force` is the operator's way past it. The button
says what the engine will do with the repeat — `Execute again · a new receipt` after a failed
delivery, `Execute again · expect the idempotency gate` after a delivered one, the gate's name
after a denial (`AGAIN_NEW_RECEIPT_TEXT`, `AGAIN_EXPECT_GATE_TEXT`; `expected_gate` /
`again_label` read the session state) — and the tests
promise no more than that ("a new receipt" was true for failed executions only). Every hosted call
passes `limits.check(key, "governed")` (`hosted_rate_limited` card) and the kill switch feature
`hosted` (`switched_off`); 401 → the not-configured card, 429 → `hosted_rate_limited`, 5xx /
transport → `hosted_unavailable`, other engine errors → their own code. Bad inputs never become a
red card: `check_inputs` answers a `Refusal` naming the offending control before any call, and
the page writes one sentence under that control (`common.render_field_message`) and echoes it in
the status row beside Run — the Try/Playground convention — while the result column shows the
empty state (round 3's red `Governed lane · unavailable · invalid_input` card is gone;
`refusal_convention` holds it in the keyed phase). Anything else that raises is logged
server-side and rendered as the designed red card (`unexpected_error`), so the stock toast never
shows. The raw engine JSON of every step is in the "Engine responses" accordion, built closed and
hidden until a run has produced JSON — fix round 5: the whole JSON in the fleet's capped code
block (`cards.code_block`, 24 lines visible, an inner scroller with `tabindex="0"` and
`role="region"` so axe's `scrollable-region-focusable` stays at 0; a read-only `gr.Code` cannot
be this block, since CodeMirror gives a non-editable document no tabindex) with a 44 px
`Copy JSON` chip beside it (`alg-gov-copy`), and the disclosure sits under the two-column row at
the page's width, so an open block never stretches the controls — no `{}` block after a run
that never reached the engine; the session's audit list is `gr.State`. Layout (round 5): the
row carries `css.COLS_CLASS`, the controls column `CONTROLS_CLASS`, the results column
`RESULTS_CLASS` and the card block `FILL_CLASS`; `GOV_CSS` pins the card to its content where
the shared contract would grow a result card to the column (the review measured 680 px of
dashed void in the empty card and 894 px around 198 px of content), so a Governed card — empty,
receipt, denial or interception — is as tall as its content and the Run button stays 48.5 px
after Observe, Execute and Execute again. The receipt says each fact once: `executed_at` is the
card's sub-line as a `<time>` (`iso_stamp`), the three integrity ids are rows and are not
repeated under the POST, the decision id is the Decision row alone, and the POST's body is
summarised in words (`webhook.describe_body`) above the body in the capped block. Snippets: the remote MCP client config
(`https://api.algenta.ai/mcp`, mirrored from `algenta._contract.MCP_ENDPOINT` and asserted) and
a smolagents example using `MCPClient` with `uvx algenta-mcp` — no `trust_remote_code=True`, no
`**os.environ`.

### `webhook.py`

The engine's POST, end to end. `make_hook(env)` builds a per-boot nonce and the public base
from `SPACE_HOST` (or `ALGENTA_PUBLIC_BASE_URL` for a tunnel); `mount(app, hook)` adds
`POST /hook/{nonce}` to the FastAPI app that serves Gradio. `Hook.path` is the prefix alone
(what `/health` may say); `Hook.url()` is the absolute URL with the nonce, passed to the engine
and printed nowhere. `Hook.expect(...)` arms a decision the session just logged with its
integrity ids and summary; `Hook.accept(nonce, body, headers)` refuses, in constant time for
the nonce, a wrong nonce, a body over 256 KB, a non-JSON or non-object body, a decision that is
not armed (unknown, already served or settled), the wrong event name, an integrity block or a
summary that differs from what was armed — every refusal recorded as a `Rejection` (reason,
decision id, the body's top-level keys, never the body) and answered 400 `{"received": false}`.
`settle(decision_id)` closes the window once `execute_decision` has returned; `wait_for
(decision_id)` lets the handler show the POST that landed while the call was in flight. Without
a public https base the execute step returns `webhook_url_unavailable` — never a placeholder
URL. There is no signing secret in this model (the engine's decision webhook sends none).

### `gpu_status.py` — the GPU tile is gated on its source

One tile for the Try and LLM tabs, and it exists only where its source does. The Space variable
`ALGENTA_GPU_STATUS_URL` (`gpu_status.STATUS_URL_ENV`) names the GPU stage's `/api/status`;
`gpu_status.configured(env)` is true only when it names an https endpoint. Unset — as it is
until the GPU stage publishes that route in M3.1 — the tabs draw no GPU tile and poll nothing:
the page ships smaller, never with an "unavailable" tile for a stage that was never wired up.
`apps/spaces/spaces.toml` carries the slot on the flagship and on the GPU stage as a documented
line (`# ALGENTA_GPU_STATUS_URL = "https://…/api/status"`, set in the same PR that lands the
route; the manifest loader refuses an empty value, so an unset slot is a comment, not `""`), and
`tests/spaces/test_manifest.py` ties the slot's name to the env the app reads. Configured:
`GpuStatusPoller` fetches the endpoint every 60 s; `parse_status` accepts only a measurement
(`tok_per_s` > 0, `measured_utc`, `hardware`, `model`; optional `ttft_ms`, `lane`, `online`).
`render_tile`: the throughput with its `measured <UTC>` chip and the machine line when online,
"GPU stage offline · last measured" when `online: false`, and the quiet documented-state card
(`gpu_status_unreachable` / `gpu_status_malformed` / `gpu_status_not_fetched`) otherwise — a
failed fetch replaces the snapshot, so no remembered number survives without its stamp.

### Ecosystem (`eco`)

Family dropdown + **Refresh counts** first, then: the twenty capped repositories with live
downloads, likes and backends from `https://huggingface.co/api/kernels?author=thyn-ai`
(`HubCounts`: fetched at boot and every 15 min, a manual refresh no more than once a minute;
a failed fetch renders "counts unavailable" on every row with the code — 20 repositories, 4
likes, 0 downloads on 2026-09-22 16:48 UTC), the family's `get_kernel` snippet built by
`playground.snippet` from its card example (`eco_snippet`), the open-source kernels card (the
number of package directories the GitHub contents API lists under `thyn-ai/mojo-kernels/kernels`
— 44 on 2026-09-22 — with the latest release tag and date, source and fetch stamp; GitHub
unreachable → `github_unreachable`, never a remembered count; GitHub is asked once at build in a
Space and again on **Refresh counts** only while no answer has arrived, so a boot-time miss
recovers without a request per click), the SDK and MCP card (installed
versions from the facts record, each row labelled with the distribution's name as `pip` spells
it — `huggingface-hub`, never the import name — the MCP tool count from
`algenta_mcp.registry.TOOLS` or `mcp_registry_not_installed`), and the shell's links as 44 px
pills. Round 17 (owner walkthrough): the SDK card's `MCP endpoint` pill pointed a browser at
`https://api.algenta.ai/mcp`, a Streamable HTTP MCP server whose GET answers 200 with a
`text/event-stream` that never ends — a blank tab that never loads. The endpoint is now a row of
the card (`MCP endpoint` · `<code class="alg-eco-code">https://api.algenta.ai/mcp</code>`, plain
inline code in the row's mono type, breaking anywhere on a phone; `code` is outside
`no_identifiers_in_copy`'s primary copy) to copy into a client's configuration, and the second
pill is `MCP guide` → `https://docs.algenta.ai/sdks/mcp` (`MCP_GUIDE_URL`, `gitbook/sdk/mcp.md`;
`/sdk/mcp` answers 307 to it, the published path answers 200).

Layout (round 4): the table takes the full page width in the 13 px mono face with tabular
numerals, one line per cell; the two counted columns (functions, on the Hub) are right-aligned and
the backends column is dropped below `BACKENDS_MIN_WIDTH` (900 px) so the four that remain keep
one line each; on a phone the rows are the shared dense row cards (`llm_tab.STACK_DENSE_CLASS`:
the kernel on its first line, the other cells inline after it — 130 px a row against 198 in round
3, the page 6,105–6,359 px against 7,801 at 375 px). Under the table one row holds the family
dropdown directly above the snippet it drives and, beside it, the two cards and the links; the row
is the fleet's two-column contract (fix round 5: `css.COLS_CLASS` on the row, `CONTROLS_CLASS`
on the dropdown-and-snippet column, `RESULTS_CLASS` on the cards column — `equal_height` had grown
every block of the dropdown column by 17 px: the Family form 100 → 117 px, the snippet 614 → 631 px,
the Copy row 48.5 → 66 px; measured at 1440 px before and after) and the SDK card carries the shared stretch
(`llm_tab.STRETCH_CLASS`) inside its column (`voids`: 0 gaps over 240 px at 1440 px). On a phone
(fix round 5) the table opens on its first `PHONE_ROWS` (6) row cards with a 44 px control under
it, `Show all 20 kernels` (`Show the first 6 kernels` folds them again): every row stays in the
DOM and in the `eco_refresh` answer — the sheet hides rows past the sixth while the table block
carries no `ALL_ATTR`, and the control's client-side click toggles that attribute (which survives
a refresh), its own label and `aria-expanded` (`more_js`; the attribute is absent until the first
press, since `gr.Button` cannot carry one at load). The shared
`cards.py` table classes (`alg-table`, `alg-table-num`, `alg-table-stack`, `alg-table-dense`) are
offered for the tab to converge on; the tab ships its own dense variant today.

### Tests

`tests/spaces/test_flagship_tabs_b.py` (offline: a fake `algenta-llm` kernel implementing the
contract's functions in plain Python so the torch references are checked independently; a fake
SDK client with the engine's wire shapes that POSTs to the hook like the engine does; Hub,
GitHub and GPU status bodies in the live shapes; the FastAPI route through `TestClient`; the
UI-construction tests where gradio is installed) and the Tabs B section of
`tests/spaces/integration/test_flagship_live.py` (`ALGENTA_SPACES_LIVE=1`, `-m slow`: the six
LLM panels on the real `algenta-llm`, the RoPE drift inside its bound, live Hub and GitHub
counts, and the governed chain on `api.algenta.ai` when `ALGENTA_API_KEY` is set).

## The app shell (`app.py`)

`app.py` owns the page, not the numbers. It adds `apps/spaces/algenta` (and, for a local run
without the vendored package, `apps/spaces/_shared`) to `sys.path`, applies `hf_ua_shim`
before anything imports `kernels`, boots (`boot_sequence.run_boot()`), and builds one
`gr.Blocks`:

| part | source |
|---|---|
| header (eyebrow, headline, subline, pills, nav, Duplicate) | `shell.render_header(headline(facts), SUBLINE, badges(state), active="Flagship")`. **Counts have one truth**: `app.headline` *is* `boot_sequence.headline` — `f"{functions_loaded:,} compiled kernels, live"`, the functions that loaded in this container, never the umbrella's published catalogue (`function_count` / `catalogue_functions`, 6,040), so a container that lost a family says the smaller number in the header, on the Try tab's Hub tile and on the boot card alike (round 1 said 6,040 in the header and 5,683 on the tile of the same page). The pills are words: `19 kernel families · this container` (neutral), `18 of 19 kernel families · this container` (amber) from `boot_sequence.families_loaded` / `families_published`, the hardware tier in words (`tier_label`: `cpu-upgrade` → `CPU upgrade`, `l4x1` → `L4 GPU`), `host below the published floor` (amber). No build-variant string (`torch25-cpu-aarch64-darwin`), revision or timing anywhere in the shell — the boot disclosure carries those; `shell.machine_token` is the rule and the tests hold every pill to it |
| tab strip | `gr.Tabs(elem_id="alg-tabs", selected="try")`, one `gr.Tab(label, id=<tab id>)` per `tabs/<id>_tab.py` in `TAB_IDS` order; `spec.render(gr)` inside, then every `spec.connect` |
| permalink row | a read-only single-row `gr.Textbox` (no stock icon panel; `max_lines=1`, which Gradio 6.28 renders as a single-line `<input type="text">` that never wraps and scrolls sideways on its own — the 44 px row at 375 px too, round 12; `common.LINK_BOX_CLASS` marks the box and holds the same row for a textarea rendering) with the tabs' 44 px Copy chip (`common.COPY_JS`) on the same row: the row is the card (`APP_CSS`: surface, hairline, card radius; the form wrapper inside drops its frame), the box's label is the fleet's caption line and its input the 44 px control (`common.LINK_BOX_CLASS`), and the chip — offset by the label's line, `common.FIELD_BOX_OFFSET_PX` — sits level with the box inside the card's padding (round 12 found it detached under the card, right-aligned alone). `Blocks.load` writes **only the state the page restored** (see the protocol below): a link's `fn` and `args` reach the box when the tab applied them, else `?tab=<id>` alone. `tabs.select` (a click on the strip) rewrites it. A programmatic switch (`gr.Tabs(selected=…)` from a handler, the Try tab's "Race it against Python" chip) fires no strip event — measured live: `tabs.change` never ran, and wiring it made Gradio raise an Error toast on every page because `gr.Tabs` is not an input component — so the box is built before the tabs with `render=False`, drawn in the row afterwards, and offered to every tab's `connect(gr, tabs, handles)` as `handles["shell"]["permalink"]` (with `"base"`): the tab that switches the strip names the box as an output of the same event and writes `common.permalink(...)` — the Try tab's "Race it against Python" chip does (`try_tab.SHELL_HANDLE`), so the box reads `?tab=race` the moment the strip moves; without the handle (an older shell) the chip still switches the strip |
| boot disclosure | `gr.Accordion("How this booted")` around `BootRegistry.render_html()`, re-rendered from the registry by a private `blocks.load` on every page load — so a stage detail that changes after boot (the hero tracker recording a measurement, once the boot owner writes it back to the registry) reaches the card a visitor opens instead of the one the page was built with; `boot_row_live` holds the hero row to `/health` |
| footer | `shell.render_footer(active="Flagship", stamp=shell.shared_sha())` — the stamp is `.shared_sha` next to the vendored package, `dev` locally |

The server is uvicorn over `gr.mount_gradio_app(api, blocks, path="/", theme=design.theme(),
css=page_css(...), mcp_server=True, footer_links=[], ssr_mode=False)`; `blocks.queue()` takes
`lane.gradio_hooks()["queue"]` (`default_concurrency_limit=1, max_size=8`). The stylesheet is
`algenta_spaces.fleet_css()` + `tabs.common.TABS_CSS` + every module-level `*_CSS` string a tab
module declares + `APP_CSS`. Every control's size, colour and focus ring — the 44 px tab, run,
chip and accordion buttons, number inputs, text areas, sliders, the dropdown row, radio and
checkbox rows, the block labels, the hidden stock icon panels and progress chrome — is the shared
chrome sheet's (`algenta_spaces.css.CHROME_CSS`, part of `fleet_css()`; every tab's run button
carries `alg-run`, every `gr.Accordion` `alg-disclosure`). `APP_CSS` is only the page: its width
(`--alg-content-max`, 16 px side padding, 48 px below) and the rhythm between the shell's blocks
(`alg-tabs`, `alg-permalink-row`, `alg-boot-disclosure`); on a phone the page column pulls 16 px
back into the 32 px Gradio pads around it (`margin: 0 -16px; width: calc(100% + 32px)` below
`design.PHONE_MAX_WIDTH` — the column's used width is pinned by its parent, so the margin alone
moves it without widening it), so
the side gutter is the design's 16 px and the content column at 375 px is 343 px, not 279. The
shell's own events and the tabs' load hooks carry `api_name=False`, so `/gradio_api/info` lists
the tabs' endpoints and nothing else. `BOOT_HEAD` also carries `shell.NAV_ROWS_HEAD`: the row
marker that keeps a wrapped nav or footer row from opening with the `·` separator.

Routes beside Gradio, declared before the mount so they win:

| route | body |
|---|---|
| `GET /health` | the boot snapshot (`ready`, `error`, `elapsed_s` — the boot, from the registry's start to the last stage's finish — `uptime_s`, `boot_started_utc`, `boot_finished_utc`, `stages[]` with each stage's `started_at` / `finished_at`) plus `status` (`booting` · `ready` · `error`), `space_id`, `hardware`, `host` (floor verdict), `families` (loaded / failed with codes), `hero` (status, `kernel_ms`, parity deltas and tolerances, stamp), `facts`, `killswitch` (flags, polls, `spend_locked`), `lane` (depth, EWMA, counters), `hosted` (state, reason), `webhook` (`prefix`, `public` — `app.public_health` redacts the route to its prefix; the nonce that gates the engine's POST is never published, and `webhook_privacy` holds it). 503 while `status == "error"`. |
| `GET /api/status` | the cross-Space tile: `ready`, `build` (shared sha), `git_sha`, `families_loaded`, `function_count`, `hero`, `hardware`, `measured_utc`, `generated_utc`. `measured_utc` is the hero's stamp only while `hero.status == "measured"`; a `noisy — not recorded` card was attempted at a time, not measured at one, so the route (`app.status_tile`) sends `null` until the rulebook has recorded a cell — another Space's tile never presents an attempt as a measurement |
| `POST /hook/<nonce>` | the engine's webhook (`webhook.mount`) |

`python app.py --no-serve` boots, builds the page, prints `/health` and exits 0 when ready — the
smoke a CI step can run without a port.

### First paint — the boot hold (`BOOT_HEAD`, `REVEAL_JS`)

Measured before the hold (PerformanceObserver `layout-shift`, three fresh loads per tab at 1440
and 375 px): Gradio paints its "Loading…" splash at ~120 ms, the components at ~400 ms with the
first tab selected, `on_load`'s `gr.Tabs(selected=…)` switches to the permalink's tab at ~480 ms
(0.131 when the new panel is taller — everything below it, the boot disclosure included, moves)
and Inter / JetBrains Mono land at ~550 ms and reflow the Try panel (0.034). Worst load 0.166;
typical 0.037. The fix holds the page instead of chasing each shift:

1. `mount_gradio_app(head=BOOT_HEAD)`: a `<style>` (`html.alg-booting body { visibility:
   hidden; }`) and an inline script that adds `alg-booting` to `<html>`. Gradio injects the
   fragment from the page config before any component mounts (measured: the class is on at
   ~70 ms, the splash still up, the components not yet in the DOM), so nothing below the body
   is painted until the hold lifts; `visibility: hidden` keeps layout, so fonts are requested
   and the strip measures its overflow as usual.
2. `blocks.load(on_load, …).then(None, None, None, js=REVEAL_JS, api_name=False)`: a
   client-only step chained after `on_load`. It waits until the selected tab is the one
   `?tab=` names (an unknown id counts as none) and `document.fonts.status === 'loaded'`, then
   two animation frames (Svelte has flushed the new panel), then removes the class. The page
   appears once, in its final layout.
3. Bounded twice: the reveal step stops waiting after `REVEAL_TIMEOUT_MS` (1.5 s — a font host
   that never answers reveals with fallback glyphs, the design system's `font-display` decides
   the swap), and the head script removes the class after `BOOT_HOLD_MAX_MS` (4 s) on its own,
   so a load handler that never answers still shows the page (with the shift it would have had).

Measured after: 0.0000 on every one of the 36 loads (six tabs × two viewports × three loads),
against a budget of 0.05 (`verify_checks.cls_budget`). `verify_checks.wait_for_reveal` blocks on
the class, and `select_tab` calls it first, so the audit and the goldens (`_goldens.py` goes
through `select_tab`) never measure a held page. `tests/spaces/test_flagship_app.py` asserts the
fragment, the chained step (private, `trigger_only_on_success = False` — a failed load still
reveals) and the two bounds.

### Accessibility — live regions and the tab strip

Two screen-reader live regions speak on this page and each says only what it owns: the Space's
`.alg-status` row (`common.render_status`, `aria-live="polite"`) announces the run — `running
now`, `done in 6.07 ms · this container · <UTC>` — and Gradio's own `div.sr-only[role="status"]`
(the client's StatusTracker) announces the request's state with a sentence, never a raw key:
Gradio 6.28's English catalogue has no `common.complete`, so the client read the key aloud after
every request (round 12) until `app.SR_TRANSLATIONS` gave the mount a catalogue entry for it
(`gr.mount_gradio_app(i18n=)`; the `srlive_no_raw_keys` gate holds both regions to this). The tab
strip follows the WAI-ARIA tabs pattern through `shell.TABS_KEYBOARD_SCRIPT`: the selected tab is
the strip's one Tab stop (a roving `tabindex`), Left / Right / Home / End move and select.

### Permalink (`permalink.py`)

`?tab=<id>&fn=<module.function>&args=<json object>`, parsed field by field on `Blocks.load` from
`gr.Request.query_params`: an unknown tab, a name that is not dotted, or JSON that is not an
object of at most 4,096 characters is dropped while the rest survives. The tab is restored with
`gr.Tabs(selected=...)`; `fn` and `args` reach a tab only through the optional protocol below.
The link written back uses `ALGENTA_PUBLIC_BASE_URL`, else `https://<SPACE_HOST>` (the Hub sets
`SPACE_HOST`), else the request's forwarding headers, else a relative `?tab=...`. Gradio injects
the request and the select event data from `__annotations__`, which `app.py` sets explicitly
because `from __future__ import annotations` would leave them as unresolvable strings.

**Protocol for a tab that wants its function and arguments restored** (Try, Playground and Races
implement it; `tabs.common.permalink` builds the matching links): a tab module defines

```python
def permalink_outputs(handles: Mapping[str, Any]) -> list[Component]: ...   # from its render() handles
def permalink_restore(fn: str | None, args: Mapping | None) -> ...            # see the two shapes below
```

and reports what it applied in one of two ways — **the "applied" protocol**:

```python
# the reporting shape: the values (one per output) and the report of what the tab applied
def permalink_restore(fn, args) -> {"values": [...], "applied": {"fn": fn, "args": kept} | None}

# or the hook, a pure function of the link (module-level, or `handles["permalink_applied"]`
# when the answer needs the tab's build state — the Races tab's offers)
def permalink_applied(fn: str | None, args: Mapping | None) -> tuple[fn, args] | None: ...
```

The shell (`app.on_load`) appends the components to the load event's outputs and, when the link
names that tab and carries `fn` or `args`, hands the tab what the ceiling allows
(`app.applied_link`: the hook's answer when there is one, else `permalink.restorable` — a
function only when a loaded family serves it, `app.known_functions`; arguments only beside such
a function or alone when the link names none), calls `permalink_restore` with it and then writes
the box **only from the tab's report**: the reporting shape's `applied` (`app.restore_answer`,
`app.report_of` — `None` is nothing, a mapping or a `(fn, args)` pair is the state; a function
that is not a dotted name or an empty mapping is dropped field by field), else the hook's
answer, else `?tab=<id>` and nothing more (`NOT_REPORTED`: a tab on the older bare-list shape
still restores, but promises nothing nobody confirmed). An unknown or absent `tab` selects the
default tab and hands no tab anything: `?tab=nope&fn=…&args=…` reads `?tab=try` (round 2 read
`?fn=…&args=…` with no tab at all). Every other tab's components receive `gr.update()`.

What that means for the seven shapes round 2 found the box lying about: `?tab=play&args={"x":1}`
reads `?tab=play` (the form kept its defaults); `?tab=play&fn=geodesy.haversine_distance&args=
{"lat1":"north"}` reads the function without the argument the number box could not take;
`?tab=try&args={"successes_a":12.5,…}` reads the hero function with the three whole numbers that
were applied; a foreign function on Try, a non-candidate on Races or a size the candidate does
not offer read the tab (or the tab and the cell the radio shows — `permalink_applied` in
`race_tab` answers with the size that was applied). The Races tab reports through the hook with
`register_offers`; the Try and Playground tabs report through whichever shape their owner lands
— until they do, the shell's fallback shows the tab alone for them, honest and lossy, and the
`permalink_truth` gate's three full shapes name the loss. `tests/spaces/test_flagship_app.py`
holds the shell to the seven shapes against fake tabs in both shapes;
`tests/spaces/visual/test_flagship_permalinks.py` holds the launched app to them in Chromium.

### Provenance — the code that ran

Two revisions per family, kept apart (`hubkernel.LoadedKernel`): `capped_v1_sha` is what the
release manifest (`docs/hf-kernels/release/capabilities.json`, the frozen copy in the module)
recorded for the Hub's `v1` tag; `snapshot_sha` is the revision `kernels` actually imported —
the `snapshots/<sha>/` directory the module came from. Everything a page prints about the code
that ran derives from the snapshot: `label()` (`algenta-llm@92ef06d`), `short_sha`, the
`wheel_sha` a results row records, the Ecosystem rows' revision, the LLM lane's label. The
manifest's sha is never painted on a result it did not produce (round 2 found the capped
`a01e2b2` on cards produced by `92ef06d7`). `pinned` is true when the two agree — or when the
module was not imported from a Hub snapshot (a local build, `revision_known` false), which is
reported as pinned because nothing else names the code; when they differ `revision_note()` is
the fact a card or `facts.json` prints (`v1 moved past the recorded capped revision`), and
`provenance()` carries the four fields and the note into `/health`. The frozen shas behind the
tags for `algenta-llm` and the umbrella are therefore a documented state the page names, not a
number it hides.

## Boot (`boot_sequence.py`)

Six stages, in order, on `algenta_spaces.boot.BootRegistry`; a stage that raises is recorded
with its reason and boot continues, so `/health` tells the truth and the page ships smaller:

| stage | work | detail on the card |
|---|---|---|
| `host` | `hubkernel.host_floor_ok()`; below the floor every family is held with `platform_unsupported` | `Linux x86_64: avx2 present, glibc 2.41` |
| `kernels` | `hubkernel.preload(PRELOAD)`: the ten tab families first (`stats` first, so the hero comes early), the other nine, then the umbrella (its members are already loaded, so it costs one import); each family runs its card example once. Its progress events keep the stage's clock (round 2 printed `0.0 s` beside `warm in 1.7 s`; `boot_card_timings` holds every row to `/health`) | `20 families warm in 5.6 s` |
| `hero` | `tabs.try_tab.measure_hero` through the one lane: gate against statsmodels, then the rulebook's interleaved samples (`bench.RULEBOOK_VERSION`, v0.4). The row is live: `hero_detail` words the tracker's state as it is now, and `FlagshipRegistry.detail_hooks` makes `/health` `stages[hero].detail` and `render_html()` read it at every snapshot, so a measurement the post-boot tracker records reaches the card a visitor opens (`boot_row_live` holds the row to `/health`; round 3's row froze at the stage's end) | `0.07 ms in-kernel, n = 21 · statsmodels agrees · attempt 5`, then `… · attempt N · measured after boot` once a background attempt records; or the rulebook's verdict (`noisy — not recorded — … · measured again every 60 s until it records`) |
| `facts` | `compute_facts` → `facts.json` (`ALGENTA_FACTS_PATH`, default next to `app.py`): versions, stamps, per family the variant, warm-up and the full provenance record (`LoadedKernel.provenance()`: `capped_v1_sha`, `snapshot_sha`, `wheel_sha`, `pinned`, `revision_note`) plus the top-level `revision_notes` list, `families_loaded`, `families_failed`, `families_published`, `functions_loaded` and `modules_loaded` (what this container runs — the one truth the headline, the Hub tile and the boot card print), `catalogue_functions` / `catalogue_modules` (the umbrella's published catalogue, quoted only in the boot disclosure), `function_count` (kept for readers of `/api/status`), `mcp_tools` (from `algenta_mcp.registry` when installed, else `null`), the hero, the rulebook version | `6,040 functions in 19 families`, or `5,683 functions in 18 families · 6,040 in the published catalogue` |
| `flags` | `KillSwitch(KILLSWITCH_URL or the results Dataset's flags.json).start()` — one synchronous poll, then every 60 s | `3 flags read` or `flag file unreachable · spend features off` |
| `hosted` | `HostedGoverned(env).status()` (one `me` probe; no key → not configured, no network); `hosted_detail` puts the state in words and a probe that failed before the SDK client existed (`tabs.gov_tab.client_missing`) reads as not configured with `CLIENT_MISSING_WORDS`, never the exception's name | `not configured · no API key is set for this Space, so the governed lane is off` |

`Deps` for the tabs keys kernels and errors by bare family name (`stats`, …, umbrella `algenta`),
which is what `Deps.kernel()` and the tab modules look up. The native lane's visitor limits are
added to the plan's policy as the `native` lane (30 calls a minute, 2,000 a day per visitor,
50,000 a day for the Space); the governed/agent/generation lanes keep the plan's values.

Measured: boot 4.9–5.9 s on Apple M4 Max (20 families warm in 2.5 s; hero 0.17 ms, n = 21);
in the amd64 image under emulation, 20 families warm in 5.6 s, hero 0.07 ms in-kernel, the
whole boot including the page build 72 s. The hero is a sub-millisecond call, so on a loaded
machine the rulebook's CV gate can return `noisy — not recorded`: the card then carries the
reason and no number, and `/health` still says ready (the stage did its job).

## The image (`Dockerfile`, `requirements.lock`) and the offline cache

`python:3.14-slim` (the hosted-API client `algenta` and its native runtime are cp314-only);
`useradd --uid 1000 user` (the uid Hub Spaces run as); `pip install --require-hashes -r
requirements.lock` as root, then everything else as `user`. The lock is compiled from
`requirements.txt` with the command in that file (`uv pip compile --python-version 3.14
--python-platform x86_64-manylinux_2_35 --generate-hashes --only-binary :all:
--index-strategy unsafe-best-match --emit-index-url`); torch is `2.9.1+cpu` from the PyTorch CPU
index, which is what makes `kernels` pick `torch29-cxx11-cpu-x86_64-linux`. Every direct
dependency is `==`-pinned (`tools/pin_drift.py` is clean on the directory). Built from the tree
`tools/stage.py` produces (the shared package vendored as `algenta_spaces/`); 716 MB.

Two build steps make the runtime download nothing:

1. `RUN python boot_sequence.py --bake` — as `user`, `HF_HOME=/home/user/.cache/huggingface`:
   `kernels.install_kernel(repo, version=1, backend="cpu", trust_remote_code=TRUST)` for the
   twenty capped repositories (this platform's variant only, ~65 s), then two cache repairs
   the offline loader in `kernels` 0.17.1 needs and `install_kernel` does not perform:
   `record_version_ref` writes `refs/v1` = the commit the online resolution chose (the offline
   resolver reads only `refs/v*`), and `prune_tree_listings` removes `trees/<sha>.json`
   (`huggingface_hub` ≥ 1.x checks a cached snapshot against the whole repository tree when
   `local_files_only=True`, and a variant-only cache is judged incomplete —
   `IncompleteSnapshotError` naming every other platform's files). The same prune runs again at
   boot when `HF_HUB_OFFLINE` is set, so a listing written later by an online tool cannot break
   an offline boot.
2. `RUN HF_HUB_OFFLINE=1 python boot_sequence.py --verify-cache` — loads every family and the
   umbrella from that cache and fails the build if one is missing (`20 families, 6040
   functions` in the log). A family whose Hub `v1` tag has moved past the recorded capped
   revision is logged (`algenta-llm` → `516a8ad`, `algenta` → `b7baf6c` on 2026-09-22), not
   failed: the footer prints the loaded revision.

Runtime: `ENV HF_HUB_OFFLINE=1`. Override with the Space variable `HF_HUB_OFFLINE=0` on a host
without the baked cache; the boot card then shows the load times it paid.

Local development: `boot_sequence.py --bake` once against a writable `HF_HOME` (the build Mac's
`~/.cache/huggingface` is a broken symlink; use `<checkout>/../hf-home`), then everything runs
with `HF_HUB_OFFLINE=1`. `tests/spaces/integration/test_flagship_boot_live.py`
(`ALGENTA_SPACES_LIVE=1`, `-m slow`) boots for real against that cache.

## QA — integrate stage, fix round 4 (2026-09-23, Apple M4 Max under parallel builds, load 12–16 on 16 vCPU)

The four implementers' round-4 trees in one index, integrated by the QA owner (label `qa-run`,
port 7905). Verified against the tree `tools/stage.py --space algenta --out <scratchpad>/fix4-staged`
produced from the shared worktree (`.shared_sha ffed44c265071d25…`, `git_sha 71130282e` plus every
owner's round-4 edits; 44 files), run as the container runs it (`python app.py` from the staged dir,
`HF_HUB_OFFLINE=1`, the shared baked cache) in three phases: **A** `venv-flagship` (CPython 3.12,
torch 2.5.1, 20 families), no key, offline; **B** the same venv as the Space (`SPACE_ID=thyn-ai/algenta
SPACE_HOST=thyn-ai-algenta.hf.space`, network on — the goldens' state); **C** `venv-gov314` (CPython
3.14 + the hosted SDK, no torch → 0 families) with the scratch tenant key sourced into the app's
shell alone and `ALGENTA_PUBLIC_BASE_URL=https://unreachable.invalid` (the failed-receipt path).

Seams closed here (contract mismatches and gates, no redesign):

* **The goldens' font gate passed on an empty `FontFaceSet`.** `_goldens._wait_for_fonts` waited
  for `document.fonts.status === "loaded"` and `check()`; both are true before Gradio has injected
  the `@font-face` rules (measured on a 50 ms timeline: `document.fonts` empty and both true at
  t+6 ms; faces present and `loading` at t+374 ms; Inter 400/600 loaded at t+644 ms; JetBrains
  Mono at t+699 ms), so under load a full-page shot could precede the swap. The first
  `--regenerate` of this round wrote 36 goldens and its proof capture refused the set (2 of 36:
  `llm-phone-light` 108 px, `race-desktop-dark` 37 px); the visual suite against that set failed
  the same two files with the same counts, then 5 other files on the next run (the odd state
  moved, the pixel signature did not: glyph advances off by 0.4–3.4 px per text row, the Inter
  600 headline unchanged, 7,857 pixels off before the 1-px tolerance — the metric-matched
  fallback face). Eight reloads of one page through the tool's own path were byte-identical and
  matched every later capture, so the goldens were the odd ones. The wait is now three steps
  (`FONT_FACES_JS` → `document.fonts.load(FONT_SPECS)` → `FONTS_LOADED_JS`), run before and after
  the tab is brought to the front; `test_golden_capture_refuses_fallback_fonts_and_reads_the_hero_state`
  pins the sequence. The strictness of the diff is unchanged.
* `tabs/llm_tab.py`'s docstring said both "each panel is one stack" and "each panel is two equal
  columns"; the second sentence now describes the stack the code builds.
* This page: the Try and Playground refusal sentences, the Playground's custom-value dropdowns,
  `selection_refusal`, `REQUEST_REFUSED_NOTE` and code captions, the boot table's live hero row, the
  LLM one-stack layout, the Governed `Webhook` row, `Refusal`, Execute-again copy and
  Engine-responses block, the Ecosystem dense table and stretch — taken from the module docstrings
  the owners wrote (their files are not this owner's).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on `apps/spaces/algenta apps/spaces/_shared apps/spaces/tools tests/spaces` | `All checks passed!`, `79 files already formatted` — before the seams and after |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -q -m "not slow"` (flagship venv, every owner's suite) | `743 passed, 5 skipped, 34 deselected in 16.64s` |
| `ALGENTA_SPACES_LIVE=1 HF_HOME=<hf-home> HF_HUB_OFFLINE=1 … tests/spaces/integration -m slow` (the real Hub kernels from the baked cache) | `53 passed, 3 skipped in 22.46s` — the skips are the governed chain and the two hosted-limits tests, which need the key in that shell |
| the keyed governed test on `venv-gov314` (pytest added to the scratch venv with `uv pip install`, it has no pip) with the scratch key sourced into that pytest shell alone | no public base: `1 skipped` — the documented skip *after* real `GET /v1/me 200`, `POST /v1/recommend 200`, `POST /v1/decisions 201` (`webhook_url_unavailable`); `ALGENTA_PUBLIC_BASE_URL=https://unreachable.invalid`: `1 passed in 1.03s` — two real `POST /v1/decisions/<id>/execute 200` (the failed receipt, then Execute again), every receipt assertion held; 0 lines of key material in the log |
| `tools/stage.py --space algenta --out <scratchpad>/fix4-staged` | 44 files, `git_sha 71130282e`, `shared_sha ffed44c265071d25…` |
| A: the staged app, no key, offline | `/health`: ready in 10.2 s (kernels 1.6 s, the hero stage 8.0 s under load — measured at attempt 5, 0.12 ms n = 21), 20 families, `webhook {prefix: /hook, public: false}` |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7905 --staged <scratchpad>/fix4-staged` ×3, phase A | 3 × `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared ffed44c26507` — `all checks passed`, exit 0 |
| `verify_checks.py --url http://127.0.0.1:7905 --staged <scratchpad>/fix4-staged --budget 300 --audit-json …` (37 checks, nokey phase A) | **36 OK, 1 FAIL**: `hero_result not recorded (documented state)`, `playground_levenshtein = 3`, `playground_decimals 343.5561 km, 1.7e-16`, `family_dropdown_foreign_value unknown_family` on both endpoints, `race_cell not recorded`, `llm_rmsnorm_parity parity chip`, `governed_lane hosted_not_configured`, `webhook_privacy /health names /hook/… without the nonce; POST /hook/<guessed> → 400, POST /hook → 404`, `ecosystem_counts 20 · 20 · 6,040 · 0 downloads · 20 likes`, `health_ready booted in 10.2 s`, `shared_stamp ffed44c26507`, `console_clean 0 over 7 tab views`, `targets_44px 1352 (20 listboxes opened)`, `axe 0 serious or critical over 28 tab views`, `contrast_hero 812`, `contrast_buttons 648`, `contrast_code 84`, `no_stock_chrome 12 samples`, `no_stock_code_labels 9 Code blocks`, `no_toasts 0 in 36 samples over 7 presses`, **`dropdown_dismissal 15 dismissals (click-away, Tab, Escape) over 5 dropdowns, form unchanged`** (round 3's Tab P1 closed by the shared shell), `boot_card_timings 0.0 + 1.6 + 8.0 + 0.2 + 0.4 + 0.0 = 10.2 s, foot 10.2 s, /health 10.249 s`, **`boot_row_live hero row '0.12 ms in-kernel, n = 21 · statsmodels agrees · attempt 5' == /health … attempt 5`** (the row follows the tracker), **`voids 38 column samples at 1440 px, no gap over 240 px`**, `footer_stamp_one_line 12 hex (140x20 px)`, `nav_separators`, `checkboxes_dark_unfilled`, `no_identifiers_in_copy 608 text nodes`, `cls_budget 36 loads, worst 0.0000`, `permalink_truth 20 loads`, `exact_integers` refused both ways. **FAIL** `refusal_convention 2 of 4 probes: desktop/light/try 'Successes A'=5000: no field message under the control ('Successes A cannot exceed Trials A.' elsewhere); phone/dark/try …` — the Try residual below |
| B: the staged app as the Space (`SPACE_ID`, `SPACE_HOST`, network on) | `/health`: ready in 3.7 s, `space_id thyn-ai/algenta`, hero `measured` at attempt 1 (0.1187 ms), `webhook {prefix: /hook, public: true}` |
| `verify_remote … --staged` ×3, phase B | 3 × all checks passed (`footer_stamp shared ffed44c26507`) |
| `verify_checks … --budget 300` (37 checks, nokey phase B) | **36 OK, 1 FAIL** (the same Try refusal): `race_cell 2.27 ms vs 116 ms · Space thyn-ai/algenta`, `llm_rmsnorm_parity parity chip · Space thyn-ai/algenta`, `ecosystem_counts 20 repositories · 20 listed by the Hub · 6,040 functions · 0 downloads · 20 likes`, `health_ready booted in 3.7 s`, `targets_44px 1392`, `axe 0 over 28 views`, `contrast_hero 836`, `no_toasts 0/36`, `boot_card_timings 0.0 + 1.6 + 1.3 + 0.2 + 0.5 + 0.0 = 3.6 s, foot 3.7 s, /health 3.706 s`, `boot_row_live … attempt 1`, `voids 38 samples, none over 240 px`, `no_stock_code_labels 9`, `dropdown_dismissal 15`, `cls_budget 0.0000`, `permalink_truth 20 loads`, `exact_integers` both paths |
| six-tab live tour, phase B (`fix4-shots/qa/tour4.py` → `fix4-shots/qa/tour-B/`, 68 PNG: static, after the primary action, every disclosure open; 1440 × 900 and 375 × 812, light and dark; `measure.json`) | in all four contexts: 0 console errors, 0 page errors, 0 toasts and 0 stock chrome or orange paint at 100 / 400 / 800 ms and once settled, **0 stock code labels or line-number gutters** (with every disclosure open), **0 gaps over 240 px** in any multi-column row at rest or after the run (the gate's own JavaScript), `scrollWidth == clientWidth` at 375 px, Inter and JetBrains Mono loaded; a forged `POST /hook/<guessed nonce>` → 400, `POST /hook` → 404, and no `webhook received` block or live chip anywhere afterwards; Tab on an open Playground listbox: `aria-expanded="false"` at +100 and +300 ms, focus on the next control (Family → Module → Function → `successes_a`), 0 form changes on 8 of 12 dismissals (the other 4 were the tour's own timeouts on a box the previous Tab had focused — the gate read 15 of 15). Results, all real: Try re-measured `not recorded` under load (quiet card), Playground `z_test_proportions`, Races Levenshtein measured on desktop/light and `not recorded` in three contexts, LLM RMSNorm parity, Ecosystem `Refresh counts` (disabled with the countdown afterwards), Governed the quiet not-configured card with no run button |
| `tests/spaces/visual/_goldens.py --url http://127.0.0.1:7905 --regenerate` (the documented command, phase B: `state on …: hero measured, hub fetched, space thyn-ai/algenta`) — five runs, the tool changing between them | run 1 (the round's tool): `36 goldens written`, proof **refused** `2 of 36` (`llm-phone-light` 108 px, `race-desktop-dark` 37 px), exit 1; run 2 (fonts gate fixed): written, proof refused `2 of 36` (`eco-tablet-light` 158, `gov-desktop-light` 112); run 3 (+ `--disable-gpu --disable-gpu-compositing --disable-gpu-rasterization --disable-lcd-text`, applied — read on the browser's command line — and inert: normal shots byte-identical): refused `3 of 36`; run 4 (+ two consecutive full-page shots per load): refused `3 of 36`, 0 retries — the state lasts the load; **run 5 (two agreeing loads per page): `gov-tablet-light: reproduced on load 3 — an earlier load rendered differently`, `36 goldens written … (hero measured, hub fetched, space thyn-ai/algenta)`, `verified: a second capture matches all 36 goldens`, exit 0**. Manifest: `state {hero_status: measured, hub_state: fetched, space_id: thyn-ai/algenta}`, `pixel_threshold 0`, `channel_tolerance 24`, `aa_tolerance_px 1`, 22 masks, `fonts [Inter, JetBrains Mono]`, `motion off`; 36 PNG, 36 distinct sha256, 87 KB (`gov-phone-light`) to 249 KB (`eco-desktop-light`), none over 450 KB; every entry records the viewport and the picture's own size (`try-desktop-light` 1440×900 / 1440×1734, `eco-phone-dark` 375×812 / 375×6667, `llm-phone-light` 375×4049, `gov-tablet-light` 1024×768 / 1024×1248) |
| the visual suite against each set (`ALGENTA_FLAGSHIP_URL=http://127.0.0.1:7905 … pytest tests/spaces/visual -m slow`, 36 diffs + manifest + state + the 10 permalink shapes) | against run 1's set: `2 failed, 46 passed` (the same two files, the same 108 / 37 px — the goldens were the odd loads) then `5 failed, 43 passed` (five other files — the fresh loads were); against run 2's: `2 failed` ×2 (its two odd goldens); against run 3's: `4 failed`, `4 failed`; against run 4's: `4 failed`, `3 failed`; against run 5's (two agreeing loads on both sides): **`48 passed in 208.95s`** (two pages needed a third load: `play-tablet-dark`, `race-phone-light`), then `2 failed, 46 passed` — five pages needed a third or fourth load and on `gov-tablet-light` (112 px) and `play-phone-dark` (35 px) two odd loads had agreed with each other; hence the reproduce rule, measured in the rows below |
| the same set, the app restarted as the Space (boot 3.9 s, hero measured at attempt 2), the tool with the reproduce rule: `_goldens.py --url http://127.0.0.1:7905` (the compare path) then the visual suite twice | CLI: `state on …: hero measured, hub fetched, space thyn-ai/algenta`, `race-desktop-dark: reproduced on load 5`, `llm-phone-light: reproduced on load 3`, **`36/36 goldens match`**, exit 0; pytest: **`48 passed in 208.95s`** (odd loads discarded on `try-tablet-light`, `play-desktop-light`) and **`48 passed in 217.15s`** (`race-tablet-light`, `llm-desktop-light`, `gov-desktop-dark`, `eco-tablet-dark` — loads 3–4) — 0 unmasked pixels beyond the 1-px tolerance on every golden, twice, and no difference reached the second-capture step; the renderer's state showed on 2–4 of 36 pages in every pass and never in the result |
| C: the staged app under `venv-gov314` with the scratch key sourced into its shell alone and `ALGENTA_PUBLIC_BASE_URL=https://unreachable.invalid` | `/health`: `status error`, `ready false` (0 of 19 families, no torch on CPython 3.14 → 503), `hosted {state: ready, reason: Connected to the hosted API.}`; `verify_remote … --staged` ×3: all checks passed (`footer_stamp shared ffed44c26507`) |
| `verify_checks.py … --phase keyed --budget 300 --audit-json …` (37 checks, phase C) | **the phase's gates all OK**: `governed_lane /gov_run receipt`, `receipt_tone /gov_run receipt 'webhook_failed · no HTTP response' painted err`, **`webhook_privacy /health (HTTP 503) names /hook/… without the nonce; /gov_run prints no webhook URL; POST /hook/<guessed> → 400, POST /hook → 404`** (round 4's residual — the raw `Webhook` row — closed by the Governed owner and held live), **`refusal_convention 2 refusals on gov: field message under the control + status-row echo, no red card, no toast`**, `axe_serious_critical 0 serious or critical over 28 tab views (keyed phase, Governed controls included)`, `no_toasts 0 in 36 samples over 7 run presses (eco, gov, llm, play, try)`, `console_clean 0`, `voids 44 column samples, no gap over 240 px` (round 3's 474 px under the red Governed card is gone), `no_stock_code_labels 8 Code blocks` (the Engine responses block included), `boot_row_live 'stats did not load · variant_unavailable' == /health hero null`, `ecosystem_counts 20 · 20 · 0 downloads · 20 likes`, `family_dropdown_foreign_value kernel_not_loaded / unknown_family`, `race_cell race_not_offered (documented state)`, `every_endpoint_answers 11`, `shared_stamp`, `contrast_hero 560`, `contrast_buttons 660`, `contrast_code 84`, `value_boxes_unclipped 88`, `no_stock_chrome`, `footer_stamp_one_line`, `nav_separators`, `checkboxes_dark_unfilled 6`, `no_identifiers_in_copy 575`, `cls_budget 0.0000`. The 10 FAILs are this venv's state, not the image's (it has torch and the SDK together): `hero_result`, `playground_levenshtein`, `playground_decimals`, `llm_rmsnorm_parity` → `variant_unavailable`; `health_ready`, `boot_card_timings` → the 503 snapshot; `targets_44px`, `dropdown_dismissal` → empty dropdowns that never open ("not measured"); `permalink_truth`, `exact_integers` → no kernel to restore or refuse |
| six-tab live tour with the key, phase C (`tour4.py --keyed` → `fix4-shots/qa/tour-C/`, 1440 × 900 and 375 × 812, light and dark) | in all four contexts: 0 console errors, 0 toasts, 0 stock chrome or orange paint, 0 stock code labels or gutters (every disclosure open), 0 gaps over 240 px, no overflow at 375 px, fonts loaded. Governed: Observe → `Run governed execution` → the interception card, 0 red; Execute → the red failed receipt (`alg-card-err` + `webhook_failed · no HTTP response`, the 2 red elements on the page), then a forged `POST /hook/<guessed nonce>` → 400 and `POST /hook` → 404 with no `webhook received` block and no live chip on any card afterwards; `Execute again · a new receipt` → a second failed receipt (the button's copy is true for the failed path); 0 URLs carrying a nonce on any card in any state. The kernel tabs answer the quiet `variant_unavailable` / `kernel_not_loaded` cards and the Races button is disabled (this venv has no torch). App log: 13 × `POST /v1/decisions/<id>/execute`, 10 × `POST /hook` (5 × `webhook rejected reason=nonce_mismatch … keys=-`, the body never parsed), 0 lines of key material in the app log, the tour and the gate logs |

Open after this round, with the measurement (for their owners):

* **Try (`try_tab`) — the refusal convention.** `refusal_convention` FAIL 2 of 4 in phases A and B:
  `'Successes A'=5000` → `Successes A cannot exceed Trials A.` printed in the status row alone
  (round 4's before-measurement: y 856 inside `.alg-status`, no `.alg-field-msg` within 120 px under
  the `Successes A` box at 771–819; the same on the phone in dark). Not changed here: the form is one
  row with Run on the boxes' baseline (`alg-form-row { align-items: flex-end }`), and a message slot
  under one box either lifts that box above its neighbours or moves Run off the baseline — a layout
  decision for the Try owner (the Playground's per-field `alg-field` columns with Run below the form
  is the pattern that keeps the convention), not an integration seam. Everything else in both
  phases is green (36 of 37).
* **Races (`race_tab`) — a foreign candidate through the API.** The candidate `gr.Dropdown` has no
  `allow_custom_value`, so an API or MCP client naming a candidate this container does not offer
  receives Gradio's stock `is not in the list of choices` error before `run_cell`'s
  `race_not_offered` card can answer (the Playground's dropdowns answer with the coded card; no
  browser path can send the value). `on_candidate` already answers an unknown id with an empty size
  list and the empty card, but with a custom value allowed the typed text would stay in the box —
  the snap-back the Playground does is the owner's to add with the flag.
* **Goldens — the renderer's anti-aliasing state.** The cause of a load rendering every text row in
  another anti-aliasing (2–3 of 36 loads per pass on this Mac under parallel builds) is not found:
  it is not the fonts (gate closed and verified), not the DOM or computed styles (identical on
  every probe), not the GPU or LCD path (flags inert). The capture now loads every page until two
  consecutive loads agree, and a difference must reproduce on a second agreed capture before it
  counts — the reproducibility a golden claims — at twice the capture time (a pass of 36 pages
  takes ~3.5 min instead of ~2.2, plus one more agreed capture per page that differed). A runner
  that shows the state at this Mac's rate (up to 5 of 36 loads in one pass) would need two odd
  pairs in a row on one page to fail a diff falsely; the doubled gate time and that residual are
  the trade to record, and the root cause stays open for the shared-shell or tooling owner.

## QA — fix round 4, gates, goldens and docs (2026-09-23, Apple M4 Max under parallel builds, load 20–27 on 16 vCPU)

The app-tools-verify owner's round (label `app-tools-verify`, port 7904). Verified against the
tree `tools/stage.py --space algenta --out <scratchpad>/fix4-staged` produced from the shared
worktree at 23:08 UTC−4 (`.shared_sha 187426a69d13…`, `git_sha 71130282e` plus every owner's
uncommitted round-4 edits at that minute), run as the container runs it (`python app.py` from
the staged dir, `HF_HUB_OFFLINE=1`, the shared baked cache) — under `venv-flagship` (CPython 3.12,
20 families, boot 3.6 s, the opening card `measured` 0.12 ms n = 21) without a key, then as the
Space (`SPACE_ID=thyn-ai/algenta SPACE_HOST=thyn-ai-algenta.hf.space`, network on) for the
goldens' state, then under `venv-gov314` (CPython 3.14 + the hosted SDK, no torch → 0 families)
with the scratch tenant key sourced into the app's shell alone. The "before" is the round-3
checkpoint (`HEAD 71130282e`) run from the worktree on the same port before any edit.

What the round changed here (defects 1–6 of the app-tools-verify owner):

* **`receipt_tone` reads the card `gov_tab` renders** (`receipt_status`; `RECEIPT_CHIP_RE` for
  `delivered · HTTP 200` / `webhook_failed · …` / `engine <status> · …`): delivered → the live
  tone on the quiet card, failed → red on the red card with no `webhook received` block and no
  delivery claim, `webhook received` on a delivered receipt alone. The unit test renders every
  card through `gov_tab.render_receipt` / `render_denial` / `render_error` / `not_configured_card`
  and gets its received block from a real `webhook.Hook` accepting the engine's own POST
  (`_engine_post`: `expect` then `accept`); the hand-built `_receipt()` helper is gone.
* **Two phases** (`--phase keyed`, `ALGENTA_VERIFY_PHASE`): the not-configured card fails the
  Governed gates in the keyed phase, `KEYED_REQUIRED` cannot be dropped by `--only`, axe runs on
  every tab view in every context (28 a run) and must have seen the Governed controls when keyed,
  the report's first line names the phase.
* **Goldens picture the deployed state or refuse**: the manifest records `state` (`hero_status`,
  `hub_state` read from `/config`'s Ecosystem table, `space_id`) and the pictures' own
  `image_width` × `image_height`; `--regenerate` refuses a local app (exit 2, the one command
  printed); a comparison against another state, or a manifest recording none, is a loud skip
  (exit 3 in the CLI, `pytest.skip` on the state test and every diff). Not regenerated here — the
  Integrate stage does, with the command in the Goldens section.
* **Six new gates**: `webhook_privacy`, `family_dropdown_foreign_value`, `no_stock_code_labels`,
  `voids`, `boot_row_live`, `refusal_convention` (37 checks).
* **`app.py`**: `/health` serves `webhook: {prefix, public}` (`public_health`) — never the path
  with the nonce (before: `path: /hook/CTd0spedChhS89CmhN6tCgDyosxUDUX1`); the boot disclosure
  re-renders the registry on every page load, so the hero row the tracker updates reaches the
  card (before: the row froze at `0.12 ms · attempt 1` for the process's life; after: the row
  read `attempt 13` beside `/health attempts: 13` on the phone shot).
* **FLAGSHIP.md**: the webhook verification model, the idempotency behaviour by outcome, the
  golden state rule and the gate list above.

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on the owned files | clean |
| `python -m pytest --confcutdir=tests/spaces tests/spaces/test_flagship_verify.py tests/spaces/test_flagship_app.py tests/spaces/test_verify_remote.py tests/spaces/test_manifest.py tests/spaces/visual -q -m "not slow"` (flagship venv) | `164 passed, 3 skipped in 5.04s` |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7904 --staged <scratchpad>/fix4-staged` ×3 (the staged app, no key) | `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared 187426a69d13` — `all checks passed`, exit 0, three times |
| `verify_checks.py --url http://127.0.0.1:7904 --staged <scratchpad>/fix4-staged --budget 900 --audit-json …` (37 checks, no key, flagship venv, the staged app) | **36 OK, 1 FAIL**: `family_dropdown_foreign_value /play_run fam='nope_family' → unavailable · unknown_family; /play_modules → unavailable · unknown_family`, `webhook_privacy /health names /hook/… without the nonce; … POST /hook/<guessed> → 400, POST /hook → 404`, `health_ready ready, 6 stages, booted in 3.6 s`, `shared_stamp shared 187426a69d13`, `axe_serious_critical 0 serious or critical over 28 tab views (nokey phase)`, `no_stock_code_labels 9 Code blocks, no stock label or line-number gutter`, `dropdown_dismissal 15 dismissals (click-away, Tab, Escape) over 5 dropdowns, form unchanged` (Tab included — round 3's open P1 is closed by the shared shell), `boot_card_timings 0.0 + 1.6 + 1.4 + 0.2 + 0.4 + 0.0 = 3.6 s, foot 3.6 s, /health 3.642 s`, `boot_row_live hero row '0.12 ms in-kernel, n = 21 · statsmodels agrees' == /health hero measured 0.12 ms in-kernel, n = 21, attempt 1`, `voids 38 column samples at 1440 px, no gap over 240 px`, `targets_44px 1352`, `contrast_hero 812`, `contrast_buttons 648`, `contrast_code 84`, `no_toasts 0 in 36 samples over 7 presses`, `cls_budget 36 loads, worst 0.0000`, `permalink_truth 20 loads`, `exact_integers` refused both ways; **FAIL** `refusal_convention 2 of 4 probes: desktop/light/try 'Successes A'=5000: no field message under the control ('Successes A cannot exceed Trials A.' elsewhere); phone/dark/try …` (the Playground passes: message under `successes_a` at +28 px and the echo 16 px under Run) |
| the same 37 checks against the worktree app before staging (`verify_checks-nokey-1.log`) | 34 OK, `shared_stamp` skipped (`build dev`), **FAIL** `voids 1 void(s) over 240 px in 26 column samples: desktop/light/llm after Run RMSNorm: column 1 of 2 ends 470 px above the row's bottom` (round 3's 469 px, measured by the gate; reproduced step by step in `probe_llm_void.py`: 0 voids at rest, after the code-chrome scan and after the dismissals, 470 px after the press) and `refusal_convention` as above; the LLM owner's edit landed before staging and the staged run reads 0 voids |
| `_goldens.py --url http://127.0.0.1:7904 --golden-dir <scratch copy>` against the local staged app | `state on …: hero measured, hub hub_counts_not_fetched, space none (local)` → `[SKIP] the manifest records no state (hero_status, hub_state, space_id); regenerate in the deployed state: SPACE_ID=… --regenerate`, exit 3; `--regenerate` on the same app: `[FAIL] refusing to regenerate: the Ecosystem table is 'hub_counts_not_fetched', the goldens picture 'fetched' …` and `… the app does not run as the Space (no SPACE_ID) …`, exit 2, the scratch set untouched (37 files) |
| the staged app booted as the Space (`SPACE_ID=thyn-ai/algenta SPACE_HOST=thyn-ai-algenta.hf.space`, network on; `/health`: `space_id thyn-ai/algenta`, `webhook {prefix: /hook, public: true}`, boot 4.5 s, hero `measured`) | `state on …: hero measured, hub fetched, space thyn-ai/algenta`; `--regenerate --no-verify` into the scratch dir: `36 goldens written … (hero measured, hub fetched, space thyn-ai/algenta)`, manifest `state {hero_status: measured, hub_state: fetched, space_id: thyn-ai/algenta}`, `eco-desktop-light.png` viewport 1440×900, image 1440×2987 px, 254 KB; `eco-phone-dark.png` 375×812 / 375×6667 px; then the compare path against that set in the same state: `36/36 goldens match`, exit 0 |
| the keyed phase, no public https base (`run_keyed_7904.sh nobase`: the staged app under `venv-gov314` — CPython 3.14 + the hosted SDK, no torch → `kernels: 0 of 19 families`, `/health` 503 — with the scratch key sourced into the app's shell alone; `verify_checks.py … --phase keyed --staged …`, 37 checks) | the phase's own gates: `receipt_tone OK /gov_run webhook_url_unavailable on the red card`, `axe_serious_critical OK 0 serious or critical over 28 tab views (keyed phase, Governed controls included)` — round 3's `scrollable-region-focusable` on the Engine responses block is gone, `no_toasts OK 0 in 36 samples over 7 run presses (eco, gov, llm, play, try)`, `voids OK 44 column samples` — round 3's 474 px under the red Governed card is gone, `console_clean OK`, `no_stock_code_labels OK 8 Code blocks` (the Engine responses block included), `refusal_convention`: the Governed probe read `Optimistic value must be above the pessimistic value.` as a field message **and** a status-row echo in both contexts (the round-3 red `invalid_input` card is gone); `governed_lane FAIL webhook_url_unavailable` (this Mac has no public https address — the documented local outcome), `webhook_privacy FAIL /health answered 503` on the first run (the gate then read the body at any status — fixed and re-run below). Everything else that failed is this venv's state, not the image's: `variant_unavailable` on every kernel tab, empty dropdowns that never open (`targets_44px`, `dropdown_dismissal` "not measured"), `permalink_truth` and `exact_integers` with no kernel to restore or refuse, `health_ready` / `boot_card_timings` on the 503 snapshot. Real engine traffic in the app log: 1 × `GET /v1/me`, 3 × `POST /v1/recommend`, 3 × `POST /v1/decisions`, 0 executions (no webhook URL to hand the engine); 0 occurrences of key material in the app log |
| the keyed phase, `ALGENTA_PUBLIC_BASE_URL=https://unreachable.invalid` (the failed-receipt path; same venv) | `governed_lane OK /gov_run receipt`; **`receipt_tone OK /gov_run receipt 'webhook_failed · no HTTP response' painted err`** — the gate now reads the real receipt (round 3's read "neither the not-configured card, a receipt nor a denial" on every real one); **`webhook_privacy FAIL /gov_run prints the webhook URL with its nonce on the card`** — the receipt's raw `Webhook` row (round 3's P2), for the Governed owner; `/health` hides the nonce and `POST /hook/<guessed>` → 400, `POST /hook` → 404 held here as in the no-key staged run (the app log's ledger line: `webhook rejected reason=nonce_mismatch … keys=-`, the body never parsed); `refusal_convention OK 2 refusals on gov: field message under the control + status-row echo, no red card, no toast; not shown: … try: no refusal to read, the run answered unavailable · variant_unavailable; … play: no form to refuse (variant_unavailable)`; `axe`, `voids 44`, `no_toasts`, `console_clean`, `no_stock_code_labels 8`, `cls_budget 0.0000`, `footer_stamp_one_line 12 hex` OK; the venv-state failures as above. Real engine traffic in the app log: 1 × `GET /v1/me`, 4 × `POST /v1/recommend`, 4 × `POST /v1/decisions`, 5 × `POST /v1/decisions/<id>/execute` (the gates' four runs and the audit's press), each execution `execution_status: failed`, `response_code: null` — the red card; 0 occurrences of key material |
| shots (`<scratchpad>/fix4-shots/app-tools-verify/{before,after}`, 1440 × 900 light and 375 × 812 dark) | the open boot disclosure (before: hero row `0.12 ms in-kernel, n = 21 · statsmodels agrees`, `/health webhook.path /hook/CTd0…`; after: the row tracking the tracker's `attempt 13`, `/health webhook {prefix: /hook, public: false}`, `measure.json` holds both readings), `llm-audit-sequence.png` (the 470 px void as the audit saw it on the pre-staging tree), `try-refusal-*.png` / `play-refusal-*.png` with `findings-measure.json` (the Try message at y 856 inside `.alg-status` and none under the control at y 771–819; the Playground message at y 717 under the control at 641–689 and the echo at 1240 under Run at 1175–1224) |

Residuals for their owners, with numbers:

* **Try (`try_tab`)**: a refusal is echoed in the status row alone — `Successes A cannot exceed
  Trials A.` at y 856 inside `.alg-status`, no `.alg-field-msg` within 120 px under the
  `Successes A` box (771–819) — in both contexts (`refusal_convention` FAIL 2 of 4). The
  Playground keeps the convention (message at +28 px under the field, echo 16 px under Run).
* **Governed (`gov_tab`)**: the receipt's `Webhook` row prints the absolute webhook URL with the
  nonce (`https://unreachable.invalid/hook/<nonce>`) as primary copy — `webhook_privacy` FAIL on
  every real receipt; the row should name the host (`Hook.host`) or go. The delivered path and
  `Execute again` after a delivered execution (the idempotency denial) could not run on this
  Mac (no public https address); both were exercised on the private staging Space on
  2026-09-23 — a real `delivered · HTTP 200` receipt through the public webhook and the
  engine's real 409 rendered as "Held by the idempotency gate". Verified with the key: the
  Governed refusal convention, the keyed axe audit, the void under the red card — all closed.
* **The keyed phase's environment**: `venv-gov314` has the hosted SDK and no torch, so every
  kernel tab is `variant_unavailable` there and the Try/Playground refusal probes cannot run
  (recorded as "not shown", not failed); the image has torch and the SDK together, so the keyed
  phase on the deployed Space measures every gate.
* **Goldens (Integrate stage)**: the committed set predates the state record and the image
  dimensions; every comparison against it is a loud skip until it is regenerated in the deployed
  state with the one command (proven here on a scratch copy: 36 written, 36/36 matched).
* **Boot (`boot_sequence`)**: the hero row now follows the tracker (attempt 13 on the after
  shot) and the card re-renders on load; `boot_row_live` holds the pair.

## QA — integrate stage, fix round 3 (2026-09-22/23, Apple M4 Max under parallel builds, load 15–32 on 16 vCPU)

The four implementers' round-3 trees in one index, integrated by the QA owner (label `qa-run`,
port 7895). Verified against the tree `tools/stage.py --space algenta --out <scratchpad>/fix3-staged`
produced from the shared worktree after the seams below were closed (`.shared_sha 24ae45daec9c…`,
`git_sha 3bbc5925f` plus every owner's round-3 edits), run as the container runs it (`python app.py`
from the staged dir, `HF_HUB_OFFLINE=1`, the shared baked cache) — under `venv-flagship` (CPython
3.12) without a key, then under `venv-gov314` (CPython 3.14 with the hosted SDK, as the image has)
with the scratch tenant key loaded into the app's shell alone. On this run the opening card
measured (`hero.status: measured`, 0.13 ms in-kernel, n = 21, boot 3.5 s), so the goldens were
regenerated against the state they require.

Seams closed here (contract mismatches between owners, no redesign):

* `try_tab.mcp_tool_count` said `live from api.algenta.ai · <UTC>` on the Hosted tile — a hostname
  in primary copy; it now says `live · hosted API · <UTC>` (`try_tab.LIVE_HOSTED`) and the test
  holds `cards.hostname_token(caption) is None`.
* `boot_sequence.compute_facts` recorded only `capped_v1_sha` and `pinned` per family; it now
  spreads `LoadedKernel.provenance()` (`capped_v1_sha`, `snapshot_sha`, `wheel_sha`, `pinned`,
  `revision_note`) and adds the top-level `revision_notes` list — measured on `/health` after the
  change: `facts.kernels.llm.snapshot_sha 92ef06d7…`, `wheel_sha 92ef06d7…`, `pinned false`,
  `revision_note "algenta-llm: v1 moved past the recorded capped revision — loaded 92ef06d, capped
  a01e2b2"`, and `revision_notes` names the umbrella (`loaded 5063de8, capped b450a8a`) and
  `algenta-llm`.
* The boot disclosure's hosted row printed `unavailable · ModuleNotFoundError: No module named …`
  when the SDK client was absent (a local 3.12 venv with a key); `hosted_detail` now applies the
  Governed tab's one rule (`gov_tab.client_missing`) and prints `not configured · the hosted client
  is not installed in this container, so the governed lane is off` (`CLIENT_MISSING_WORDS`).
* `tests/spaces/fixtures/hero_contracts.json` pinned `llm.revision` at the capped `a01e2b2…`; the
  cache's `v1` is `92ef06d7…` (the same contract — only the revision differs), so the live fixture
  test failed on a fact the page already names; the fixture records the revision the contract was
  read from.
* Already closed by their owners before integration, verified here: `race_tab` records
  `wheel_sha=races.kernel_revision(kernel)` (the loaded snapshot), the cross-owner test lines for
  the 12-hex stamp and the `<time>` stamps, the Playground's handle-level `permalink_applied`
  (`test_full_links_are_restored_and_kept[play_levenshtein]` passes against the launched app).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on `apps/spaces/algenta apps/spaces/_shared apps/spaces/tools tests/spaces` | `All checks passed!`, `79 files already formatted` — before and after the seams |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -q -m "not slow"` (flagship venv, every owner's suite) | `727 passed, 4 skipped, 34 deselected in 24.22s`; re-run after the seams: the touched suites (`test_flagship_tabs_a`, `test_flagship_app`, `test_copy_lint`, `test_playground`, `test_flagship_tabs_b`) `148 passed` + `255 passed` |
| `ALGENTA_SPACES_LIVE=1 … -m slow -k "not goldens and not permalinks"` (the real Hub kernels from the baked cache) | first run `1 failed, 52 passed, 5 skipped` — `test_hero_contracts_fixture_matches_the_live_families`: `llm.revision` `a01e2b2…` committed, `92ef06d7…` live; after the fixture update `53 passed, 5 skipped in 22.76s` |
| the governed live test with the scratch key sourced into that pytest shell alone (flagship venv) | `1 skipped: the algenta SDK client is not installed in this venv` — the honest outcome on CPython 3.12 (the SDK is cp314-only); the chain is exercised in the keyed browser run below |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7895 --staged <scratchpad>/fix3-staged` | `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared 24ae45daec9c` — `algenta: all checks passed` |
| `tests/spaces/visual/_goldens.py --url http://127.0.0.1:7895 --regenerate` (the documented command, on the `measured` opening card) | `36 goldens written … (hero measured)`; the proof capture: `[OK] … identical beyond the 1-px anti-aliasing tolerance` ×36, `verified: a second capture matches all 36 goldens`, exit 0; the set is 36 PNG, largest 273 KB (`try-*` 120–126 KB), manifest `hero_status: measured`, `pixel_threshold 0`, `channel_tolerance 24`, `aa_tolerance_px 1` |
| `ALGENTA_FLAGSHIP_URL=http://127.0.0.1:7895 … pytest tests/spaces/visual -m slow` ×2 (36 golden diffs + manifest + state check + the 10 permalink shapes) | `48 passed in 132.93s`, then `48 passed in 133.29s` — 0 unmasked pixels beyond the tolerance on every golden, twice |
| `test_flagship_verify.py -k "one_digit or golden or diff or manifest"` (the planted-digit proof) | `7 passed` — the one-digit caption fails the diff as designed, the 1-px shift passes |
| `verify_checks.py --url http://127.0.0.1:7895 --staged <scratchpad>/fix3-staged --budget 300 --audit-json …` (31 checks, no key, flagship venv) | 28 OK on the first run — `hero_result /try_run not recorded (documented state — noisy — not recorded — spread above 15 percent)` (the verifier's own call, taken while the browser audits ran; the boot's hero was `measured`), `race_cell 2.31 ms vs 115 ms`, `llm_rmsnorm_parity parity chip`, `ecosystem_counts 20 repositories · 20 listed · 6,040 functions · 0 downloads · 4 likes`, `health_ready ready, 6 stages, booted in 3.5 s`, `shared_stamp 24ae45daec9c`, `console_clean 0 console errors over 7 tab views`, `targets_44px 1352 targets, all >= 44 px (20 listboxes opened)`, `axe 0 serious or critical`, `contrast_hero 812 samples`, `contrast_buttons 648`, `contrast_code 92`, `value_boxes_unclipped 84`, `no_stock_chrome 12 samples over 4 runs`, `no_toasts 0 toasts in 36 samples over 7 run presses`, `boot_card_timings 0.0 + 1.6 + 1.2 + 0.2 + 0.4 + 0.0 = 3.4 s, foot 3.5 s, /health 3.503 s`, `footer_stamp_one_line 12 hex, one line at 375 px (140x20 px)`, `no_identifiers_in_copy 608 text nodes`, `cls_budget 36 loads, worst 0.0000`, `permalink_truth 10 link shapes × 2 contexts, box == restored state (20 loads)`. Three FAIL, two of them the gate's contract against the owners' implemented one, closed here and re-run: `every_endpoint_answers /play_form returned no output` (the value guard's no-op on the default selection → now `11 further endpoints answered; … no-op on the default selection, answered on a changed one: /play_form, /play_modules`) and `exact_integers /play_run: no Request-and-response JSON` (the contract refuses a JSON whole number ≥ 2^53 → now `API path refuses 9007199254740993 as a JSON number ('is above the range the browser can enter exactly'), nothing ran; browser: 9007199254740993 refused with a message`). The third stands, see below |
| `dropdown_dismissal` | **FAIL, a page behaviour, not fixable by integration**: `5 of 15 dismissals … Tab: listbox stayed open` on every dropdown (Playground Family, Module, Function; Races candidate; Ecosystem family), 0 form changes on click-away, Tab or Escape (round 2's cascade on blur is closed). Measured directly (`fix3-shots/qa/nokey/tab-dismissal-probe.json`, 1440 × 900 light): after Tab on an open Playground Family list the same combobox keeps `aria-expanded="true"` and one listbox stays visible 1.5 s later with focus on `<body>`, and Escape then does not close it; on Races focus moves to the size radio (`S · 300 × 300 characters`) and the candidate's list stays open. Gradio 6.28's dropdown closes on a click outside and on Escape while focused, not when focus leaves it — the shared shell (a head script closing an expanded combobox on `focusout`) is the place for a fix, beside its listbox-opens-on-focus finding |
| six-tab live tour, no key (`fix3-shots/qa/tour.py` → `fix3-shots/qa/nokey/tour/`, 44 PNG: every tab static and after its run button, 1440 × 900 and 375 × 812, light and dark, `measure.json`) | in all four contexts: 0 console errors, 0 page errors, 0 toasts and 0 stock chrome or orange paint in 96 samples (100, 400, 800 ms after each press and once settled), `scrollWidth == clientWidth` (375/375) on every tab at 375 px, Inter and JetBrains Mono loaded on every page, 0 red cards or chips anywhere. Results, all real: Try re-measured `noisy — not recorded — spread above 15 percent` (load 26.7 on 16 vCPU, the quiet card, `done in 5.61 ms · this container · <UTC>`); Playground `ab_testing.z_test_proportions` `0.19–0.37 ms in-kernel, one call`, result `[-3.188063564953509, 0.0014324199056339193]`, `algenta-stats@ac35ffe`; Races Levenshtein 600 × 600 vs nltk 3.10.3 `parity · not a race` measured in three contexts (2.43–2.61 ms in-kernel), `noisy — not recorded — load 25.7` in the fourth; LLM RMSNorm 8 × 256 `parity max |Δ| 1.8e-15 ≤ 1e-09`, RoPE and Sampling on their empty cards; Governed the quiet `hosted_not_configured` card with no run button (the tour records `no run button`); Ecosystem `44 packages · latest release v0.1.4 · released 2026-09-22 14:54 UTC · fetched <UTC>` and the SDK card saying `not installed here` for this 3.12 venv. Viewed: `try-desktop-light-run.png` (the Hosted tile reads `live · hosted API · <UTC>`, the deploy stamp `build 24ae45daec9c`), `race-phone-dark-run.png`, `gov-desktop-light-static.png` |
| the keyed run: the staged app under `venv-gov314` (CPython 3.14 + the hosted SDK) with the scratch tenant key sourced into the app's shell alone (`fix3-shots/qa/run_keyed_7895.sh`), no public https base | boot `1.7 s`, `hosted: connected to the hosted API`; `kernels: 0 of 19 families loaded · variant_unavailable` on every family and `hero: stats did not load` — that venv has no torch (cp314), so the Hub kernels cannot load there and `/health` answers 503 (`health_ready` FAIL, this venv's state, not the image's: the image has torch and the SDK together). `verify_remote --staged`: `[OK]` ×3, `all checks passed`. Gates: `receipt_tone OK — /gov_run webhook_url_unavailable on the red card`; `governed_lane FAIL — the unavailable card (webhook_url_unavailable)`: the default profile is Execute and this Mac has no public https address for the engine's POST, so the run fails and is painted red — the documented local outcome, the gate stays strict for the deployed Space where `SPACE_HOST` is set; `expected_api_names 17`, `shared_stamp 24ae45daec9c`, `console_clean 0 over 7 tab views`, `footer_stamp_one_line 12 hex (140x20 px)` OK |
| Governed tab tour with the key (`fix3-shots/qa/keyed/tour/`, 12 PNG, 1440 × 900 and 375 × 812, light and dark) | Observe profile → `Run governed execution` (0.87 s, real `recommend` and `log_decision` on `api.algenta.ai`) → the amber interception card `Not in the observe profile · before the engine was called · intercepted by the integration · tool_not_in_profile · Executing a decision is not in this profile; the decision is logged and nothing ran`, 0 red; Execute profile → the red card `Governed lane unavailable · webhook_url_unavailable · This Space has no public https address, so the engine has nowhere to deliver · hosted engine · <UTC>` — the one red element on the page (`alg-card-err` + its code chip), in all four contexts; 0 console errors, 0 toasts, 0 stock chrome, no overflow at 375 px |
| `no_toasts` on the keyed app, first run | **FAIL — a real defect found by this venv's state and closed here**: `4 toast(s) … desktop/light/play Run: 'Error × NoneType' object has no attribute 'removeprefix'` (one press, sampled at 100, 400, 800 and 3,000 ms). With no family loaded the Playground's dropdowns carry nothing, a press reaches `Deps.kernel(None)` (`tabs/__init__.py`) through `play_tab.run_call` → `catalogue.kernel`, and Gradio painted the traceback as a toast. `Deps.kernel` now answers None for an unset family and `run_call` yields the quiet `kernel_not_loaded` card under the empty-state title for an unset selection (`test_play_run_call…`: `deps.kernel(None) is None`, the card carries `kernel_not_loaded` and `No result yet`, never `None`); the staged tree was rebuilt and the keyed gates re-run — see the next row |
| the keyed gates after the guard (restaged tree, the keyed app restarted) | `no_toasts OK — 0 toasts in 36 samples over 7 run presses (eco, gov, llm, play, try); not pressed, disabled: desktop/light/race Run race (disabled)` (no candidate is offered when no family loaded, so the Races button is rightly disabled), `console_clean OK 0`, `receipt_tone OK webhook_url_unavailable on the red card`, `shared_stamp OK`; `governed_lane` FAIL as above (no public https base on this Mac) |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -q -m "not slow"` after every seam and the guard | `728 passed, 4 skipped, 34 deselected in 15.73s`; `ruff check` / `ruff format --check` clean on the four trees |

Open after this round, with the measurement (for their owners):

* **Tab leaves a Gradio dropdown's listbox open** (`dropdown_dismissal`, 5 of 15 — every dropdown,
  Tab only): `aria-expanded="true"` and a visible listbox 1.5 s after Tab, focus on `<body>`
  (Playground) or the next radio (Races); Escape from there does not close it. Gradio 6.28
  closes on click-outside and on Escape while focused; a `focusout` closer in the shared shell's
  head script is the fix, beside the shared owner's listbox-opens-on-focus finding.
* **`governed_lane` cannot pass on a host without a public https address**: the default profile
  is Execute, the engine has nowhere to POST, the card is the red `webhook_url_unavailable` —
  the truthful local outcome; the gate stays strict for the Space (`SPACE_HOST`). The delivered
  receipt path (`delivered · HTTP <code>`) is therefore verified only against the fake client in
  the unit suite, as the Governed owner reported.
* **The 2^53 API rule is a design choice, recorded, not a defect**: a JSON whole number at or
  above 2^53 is refused through the API too (`playground.coerce`, option b of the Playground
  owner); the exact route is the `kernels`/SDK snippet under Reproduce. The `exact_integers` gate
  and its doc row read that contract.
* The boot card's kernels row does not yet print the `revision_notes` (`facts.json` and
  `/health` carry them; `hubkernel.Preload.revision_notes()` is ready for the row) — a copy
  decision for the boot owner, not taken here.

## QA — fix round 3, app shell, gates, goldens and docs (2026-09-22/23, Apple M4 Max under parallel builds)

Verified against the tree `tools/stage.py --space algenta` produced from the shared worktree as
it stood at staging (`.shared_sha 624b2dfe4270…`, `git_sha 3bbc5925f` plus every owner's
uncommitted round-3 edits at that minute — the Races hook, the shared shell's 12-hex stamp, the
boot clock fix and the `<time>` stamps had landed; the Playground's `permalink_applied` handle
landed after staging), run as the container runs it (`python app.py` from the staged dir,
`HF_HUB_OFFLINE=1`, the shared baked cache, port 7894, boot 15.3 s, 20 families, the opening
card `noisy — not recorded` on this loaded host — the documented state). The "before" is an
export of `HEAD` (`git archive 3bbc5925f`) run the same way on the same port.

What the round changed here (defects 1–6 of the app-shell owner):

* **The permalink box is written from the tab's report alone** (`app.on_load`,
  `restore_answer`, `report_of`, `NOT_REPORTED`; the "applied" protocol above). Measured on the
  ten link shapes in four contexts (1440 × 900 and 375 × 812, light and dark,
  `fix3-shots/app-tools-verify/{before,after}/measure.json`): before, all seven round-2 shapes
  echoed the link (`?tab=play&args={"x":1}` with the default form; `lat1="north"` with a blank
  box; `successes_a=12.5` with the field at 50; a foreign function and its numbers on Try with
  the defaults; `?fn=…&args=…` with no tab at all; `size=XL` with M selected; a non-candidate
  function with Levenshtein selected). After: `?tab=play`, `?tab=play`,
  `?tab=try&args={"n_a":345,"successes_b":67,"n_b":890}` (the three whole numbers the tab
  applied), `?tab=try`, `?tab=try`, `?tab=race&fn=text.fuzzy.levenshtein_distance&args={"size":"M"}`
  (the cell the radio shows), `?tab=race` — in all four contexts, 0 toasts. The full shapes:
  `race_levenshtein_L` and `try_ints` restored and kept in all four contexts; `play_levenshtein`
  restored (text, text.fuzzy, levenshtein_distance, kitten, sitting) but the box read `?tab=play`
  on the staged tree — the Playground reported nothing at staging time (its handle-level hook
  landed afterwards; see the residuals).
* **copy_lint exits 0 on `apps/spaces/algenta`** (`!t` → `t === null`; every `!x` in the audit
  JavaScript is `x === false`), asserted by `test_the_flagship_is_clean_through_the_cli` and by
  `test_audit_javascript_is_well_formed` (no `!` other than `!=`/`!==` in any script).
* **Goldens are strict**: every measured number masked as a block, no blur, no neighbourhood
  filter, 0 unmasked pixels beyond a 1-px tolerance; proven by the one-digit test (20 pixels on
  `P95 0.20 ms` → `0.14 ms`; a 1-px shift 0; a 2-px shift fails) and by a committed golden
  against itself and its 1-px-shifted copy (identical).
* **Eight new gates** (`receipt_tone`, `permalink_truth`, `dropdown_dismissal`, `no_toasts`,
  `boot_card_timings`, `footer_stamp_one_line`, `exact_integers`, plus `--audit-json` for the
  evidence folder), every existing gate kept (31 checks). Run against the `HEAD` export before
  any owner's fix (`gates-before.log`): `permalink_truth` **FAIL** 26 promises over 20 loads;
  `boot_card_timings` **FAIL** `6 stages: 0.0 + 0.0 + 0.5 + 0.2 + 0.5 + 0.0 = 1.2 s, foot 4.8 s,
  /health 4.756 s`; `exact_integers` **FAIL** `typed 9007199254740993, the request carries
  9007199254740992 and no message under the field` (API path exact); `dropdown_dismissal`
  **FAIL** 5 of 15 (first reading, before the gate learned to tell the next dropdown opening on
  Tab from the same one staying open); `no_toasts` OK 0 in 36 samples over 7 presses;
  `footer_stamp_one_line` OK (`dev`, 70 × 20 px); `receipt_tone` documented state (no key).
* **`verify_remote.SHA_STAMP_RE` / `verify_checks.STAMP_RE`** read the shared shell's 12-hex
  stamp with the full sha in a `title` before or after the class, in all three spellings
  (`test_footer_stamp_accepts_the_shared_shells_twelve_hex_stamp`); `no staged .shared_sha`
  still fails the tool's check and skips the flagship's.
* **FLAGSHIP.md**: the idempotency-denial claim is gone (the engine re-executes and answers with
  a new receipt), the provenance model is documented (snapshot vs capped sha, `pinned`, the
  note), the "applied" protocol, the golden masking rule and the new gates are written down,
  and the round-2 QA table now says its copy_lint row was untrue.

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on the 14 owned files | clean |
| `python -m pytest --confcutdir=tests/spaces tests/spaces/test_flagship_verify.py tests/spaces/test_flagship_app.py tests/spaces/test_copy_lint.py tests/spaces/test_verify_remote.py tests/spaces/test_manifest.py tests/spaces/visual -m "not slow"` (flagship venv) | 52 + 47 + 72 passed, 2 skipped (the four owned modules alone) |
| `tools/copy_lint.py apps/spaces/algenta` | `0 finding(s) (clean)`, exit 0 — measured, and asserted in the unit suite |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7894 --staged <dir>` ×3 | `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared 624b2dfe4270` — all checks passed, three times (the 12-hex stamp) |
| `verify_checks.py --url … --staged <dir> --budget 900 --audit-json …` (31 checks) | run started 00:01 UTC against the staged app; the report had not printed when this round's time ran out — `fix3-shots/app-tools-verify/verify_checks-after.log` / `audits-after.json` hold it once it lands. Against the `HEAD` export the same gates read: `permalink_truth` FAIL 26 promises / 20 loads, `boot_card_timings` FAIL (rows 1.2 s vs foot 4.8 s), `exact_integers` FAIL (browser 9007199254740992, API exact), `dropdown_dismissal` FAIL 5 of 15, `no_toasts` OK 0/36, `receipt_tone` documented state (no key) |
| goldens, strict diff | not re-captured against the launched app this round (the strict diff is proven on the committed `try-desktop-light.png` against itself and its 1-px-shifted copy — identical — and on the planted one-digit caption — 20 pixels, FAIL); the two-capture proof against the app is the Integrate stage's, with `_goldens.py --regenerate` on a `measured` opening card |
| `tests/spaces/visual/test_flagship_permalinks.py` (`-m slow`, 10 tests) | written (`test_flagship_permalinks.py`, 7 + 3 tests over `PERMALINK_SHAPES` in two contexts); not yet run against the launched app this round — the ten shapes were measured by `shoot.py` instead (the bullet above), and the `permalink_truth` gate reads the same state |
| Governed with the scratch tenant key (venv-gov314, key sourced into the app's shell alone) | not run this round (the launcher `fix3-shots/app-tools-verify/run_keyed.sh <label> [public base]` sources the scratch key into the app's shell alone and starts the staged app on venv-gov314; `verify_checks.py --only receipt_tone,governed_lane` then reads the `webhook_url_unavailable` path without a public base and the failed receipt with `https://unreachable.invalid`). The gate's rule is asserted on rendered cards in `test_receipt_tone_matches_the_execution_status` |
| shots (`<scratchpad>/fix3-shots/app-tools-verify/{before,after}`, 1440 × 900 and 375 × 812, light and dark) | the permalink row after each of the ten link shapes (40 + 40 PNG), the footer (`build dev` 70 × 20 before, `build 624b2dfe4270` 140 × 20 after, one line in every context) and the open boot disclosure (before: `kernels 0.0 s` beside `warm in 2.0 s`, rows summing to 1.2 s under a `booted in 4.8 s` foot; after: `0.0 + 2.3 + 12.4 + 0.2 + 0.4 + 0.0 = 15.3 s` = the foot's `15.3 s`); `measure.json` holds the box value and the form state per load, the stamp rects and the boot rows |

Residuals for their owners, with numbers:

* Playground (`play_tab`): on the staged tree the box read `?tab=play` for
  `?tab=play&fn=text.fuzzy.levenshtein_distance&args={"a":"kitten","b":"sitting"}` although the
  form restored all of it — the tab reported nothing at staging; the handle-level
  `permalink_applied` that landed afterwards closes it (the `permalink_truth` gate's
  `play_levenshtein` shape names the loss until then). Dismissing an open Family/Module/Function
  listbox by click-away or Tab must not fire the cascade (`dropdown_dismissal`, 5 of 15 on the
  `HEAD` export). 2^53 + 1 typed into a number box reaches the request as 2^53 with no message
  (`exact_integers`); the API path is exact.
* Governed (`gov_tab`): the `engine failed` chip in the live tone and the delivery note on a
  failed receipt (`receipt_tone` fails it; not exercised here without the keyed run).
* Boot (`algenta_spaces.boot`): the stage clock fix landed in the tree — after-shots read
  `0.0 + 2.3 + 12.4 + 0.2 + 0.4 + 0.0 = 15.3 s` = the foot; `boot_card_timings` holds it.
* Shared shell: the 12-hex stamp landed — `build 624b2dfe4270`, 140 × 20 px, one line in every
  context.


## QA — integrate stage, fix round 2 (2026-09-22, Apple M4 Max under parallel builds, load 15–22 on 16 vCPU)

The four implementers' trees merged in one index; the integrate stage closed the seams they
named and left the design alone. Verified against `tools/stage.py --space algenta` output run
as the container runs it (`python app.py` from the staged dir, `.shared_sha bc8e7c68957e…`,
`HF_HUB_OFFLINE=1` on the baked cache), a second instance of the pre-integration index exported
with `git checkout-index` for the before shots, and a third staged instance on the Python 3.14
venv that carries the hosted SDK with the tenant key from the repository `.env` loaded into that
process alone.

Closed at integration (each measured before and after in `<scratchpad>/fix2-shots/qa-run/`):

* `tabs/common.error_card` renders `cards.render_error_card` — a lane refusal, a kernel error or
  a raise during the visitor's run is the red card; `llm_tab.render_failure_card` is that call
  without the signature probe, `llm_tab.render_quiet_card` / `gpu_status.quiet_code_chip` /
  `gpu_status._quiet_tile` are `cards.render_unavailable_card` / `render_not_configured_card` /
  `code_chip` / `tile(state="unavailable")`; `try_tab.gpu_configured` / `gpu_url` call
  `gpu_status.configured` / `status_url` directly.
* Races: the second `lane · MAD · CV` table under the result card is gone — the shared lane table
  carries median, MAD, CV, P95 and min – max (before: 2 tables, the spread table's first row
  cards without a `data-label` on the phone; after: 1 table, every cell labelled); the race card
  keeps 16 px sides at 375 px like Try and Playground (computed padding `16px 24px` → `16px`).
* Try: "Race it against Python" writes the shell's permalink box in the same click
  (`try_tab.SHELL_HANDLE`): the box read `?tab=try` after the switch, it reads `?tab=race`.
* Ecosystem: the SDK card's row label is the distribution name `huggingface-hub` (the gate's one
  residual, `huggingface_hub`, gone — `no_identifiers_in_copy`: 560 text nodes, clean).
* `verify_checks.CONTRAST_SELECTORS` no longer lists `.alg-tile-title/-value/-caption`, classes
  nothing renders since the tiles became `cards.tile` (`.alg-stat-*`, already measured).
* `tests/spaces/integration/test_flagship_boot_live.py` reads the kernels stage as
  `boot_sequence.kernels_summary` phrases it (`19 families and the umbrella warm in …`).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on `apps/spaces/algenta apps/spaces/_shared apps/spaces/tools tests/spaces` | clean, 78 files |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -m "not slow"` (flagship venv) | 694 passed, 3 skipped, 18.5 s |
| `ALGENTA_SPACES_LIVE=1 HF_HUB_OFFLINE=1 … tests/spaces/integration -m slow` | 50 passed, 3 skipped (governed chain without a key; hosted limits without the SDK in this venv), 1 failed: `test_hero_contracts_fixture_matches_the_live_families` — the baked cache serves `algenta-llm` at `92ef06d7` while `hubkernel.FROZEN_CAPPED_V1_SHAS` and the fixture record the capped `a01e2b23` (the foundations gap listed below, not a Space change) |
| `tools/stage.py --space algenta` → `tools/verify_remote.py --staged` | `[OK] info_reachable 17`, `[OK] expected_endpoints 17`, `[OK] footer_stamp shared bc8e7c68957e` — all checks passed |
| `verify_checks.py --url … --staged <dir> --budget 300` (24 checks) | **24 OK**: `hero_result` (`not recorded`, the documented state at that minute — the tracker measured on attempt 28, 22:25 UTC), `playground_levenshtein` (= 3), `playground_decimals` (343.5561 km, formula agrees to 1.7e-16), `race_cell` (4.53 ms vs 236 ms), `llm_rmsnorm_parity`, `governed_lane` (`hosted_not_configured`), `ecosystem_counts` (20 · 6,040 · 0 · 4), `every_endpoint_answers` (11), `health_ready` (booted in 17.9 s), `shared_stamp`, `console_clean` (0 over 7 views), `no_horizontal_scroll`, `targets_44px` (1352 targets ≥ 44 px, 20 listboxes opened), `axe_serious_critical` (0), `contrast_hero` (748 samples ≥ 4.5:1), `contrast_buttons` (648), `contrast_code` (92), `value_boxes_unclipped` (84), `no_stock_chrome` (12 samples), `nav_separators` (12 rows), `checkboxes_dark_unfilled` (2), `no_identifiers_in_copy` (560 nodes), `cls_budget` (36 loads, worst 0.0000) |
| goldens | the documented command refused while the hero was `noisy` (exit 2, as designed); once the tracker measured (attempt 28) `_goldens.py --regenerate` wrote 36 PNG (hero `measured`, largest 248 KB, manifest consistent) and its own second capture matched 36/36 at 0.0000 %; `pytest tests/spaces/visual -m slow` against the same app: 38 passed twice (90 s, 88 s) |
| six-tab tour (Playwright, 1440×900 and 375×812, light and dark, primary action pressed with the prefilled inputs on every tab) | 0 stock-chrome elements and 0 stock-orange colours over 72 samples at 100 / 400 / 800 ms; `scrollWidth == clientWidth` at 375 px on every tab before and after the action; every tab reachable on the phone strip (Try, Playground, Ecosystem by pointer; Races, LLM, Governed by the DOM-click fallback the verifier also uses — the snapping strip moves under the pointer); 0 console errors from the pages themselves (4 `AbortError: BodyStreamBuffer was aborted` lines are the harness's `page.goto` cutting the previous tab's open event stream, logged at the next navigation) |
| independent values | Try hero `z −1.440793`, `p 0.149643` vs statsmodels: Δz 0, Δp 8.6e-8; Playground `z_test_proportions(200, 1000, 260, 1000)` `[-3.18806…, 0.0014324…]` vs statsmodels Δp 1.3e-7; Races Levenshtein M (600 × 600, seed 20260922) kernel 540 = nltk 540 on the very strings, card `parity exact match`, 3.39 ms vs 169 ms, CV 7.3 %; RMSNorm `x=[1,2,3,4]`, `γ=[1,0.5,2,1]`, `eps=1e-6` vs the formula: max |Δ| 0.0, card 8 × 256 `max |Δ| 1.8e-15 ≤ 1e-9`; Ecosystem chips `20 kernels · 4 likes` = the Hub's kernels listing fetched directly (20 capped repositories, 4 likes, 0 downloads); Governed with the `.env` key: `GET /v1/me` → HTTP 401 `invalid_api_key` (request `req_19071cba…`), the page shows the quiet `hosted_not_configured` card "The hosted API rejected this Space's key, so the governed lane is off." with its controls hidden — the real outcome, not a state |

Shots: `<scratchpad>/fix2-shots/qa/` (66 PNG: six tabs × desktop/phone × light/dark, static, 350 ms
after the press, settled result; `tour.json`, `independent.json`) and
`<scratchpad>/fix2-shots/qa-run/{before,after}/` (17 each: the race result, the SDK card and the
permalink row after the Try chip, per context, with `*-measure.json`).

Open after this round (owners named):

* `permalink_applied` in `race_tab`: a link to a candidate this container does not offer still
  shows its `fn`/`args` in the box when the function exists in a loaded contract; the hook the
  shell offers needs the tab's offers, which live in `build()`'s state — a design choice for the
  Races owner, not an integration.
* The footer stamp prints the full 64-hex `.shared_sha` (`build bc8e7c68…b0c57`), two lines at
  375 px; `verify_remote.footer_stamp` reads it — shortening is the shell owner's call together
  with that check.
* `cards.tile(stamp=…)` renders `<time>counted <UTC></time>`; the Try band still writes
  `counted at boot · <UTC>` as plain meta text (unit, provenance and UTC all present).
* The tenant key in the repository `.env` is rejected by `api.algenta.ai` (401); a receipt on
  the Governed tab needs a valid key or the local engine the `.env` points at.

## QA — integration run (2026-09-22, Apple M4 Max under parallel builds, load 13–16 on 16 vCPU)

The Integrate stage after the four fix-round implementers landed: contract mismatches closed,
suites green, goldens regenerated. Verified against the tree `tools/stage.py --space algenta`
produced (`.shared_sha 10aa4e0e12f4…`), run as the container runs it (`python app.py` from the
staged dir, `HF_HUB_OFFLINE=1`, the shared baked cache, port 7875).

What integration changed:

* One spelling for the hosted lane's codes: `hosted_api.NOT_CONFIGURED_CODE` /
  `RATE_LIMITED_CODE` / `UNAVAILABLE_CODE` are the lowercase snake_case the cards print
  (`cards.normalize_code`); `gov_tab` and `verify_checks` read the constants instead of spelling
  them again (the one red unit test, `test_hosted_api`, asserted the old upper-case literal).
* `APP_CSS` dropped every control rule the shared `CHROME_CSS` now owns (number inputs, text
  areas, range inputs, radio and checkbox rows, block-label colours, tab and overflow buttons,
  `alg-run` / `alg-chip-btn` / `alg-disclosure` minimums) and keeps only the page: width, block
  rhythm, and the phone pull-back (`margin: 0 -16px; width: calc(100% + 32px)` below 767 px), so
  the content column at 375 px is 343 px with a 16 px gutter (279 px behind a 48 px gutter
  before — measured on the `.alg-page` box).
* The shell's separators moved into the list's 16 px column gap (absolutely positioned, no
  layout of their own) and `shell.NAV_ROWS_SCRIPT` (in `BOOT_HEAD` through `shell.NAV_ROWS_HEAD`)
  marks the item that opens each wrapped row with `data-alg-row-start`; the sheet draws no glyph
  there. At 375 px both lists wrap to three rows and no row opens with `·` (rows 2–4 did before,
  measured through the `::before` computed `content`). The footer's 64-hex build stamp wraps
  (`overflow-wrap: anywhere`) instead of clipping at the right edge.
* The permalink row's stock Copy icon (hidden by `CHROME_CSS`, so the read-only box had no copy
  affordance at all) became the tabs' 44 px Copy chip (`common.COPY_JS`, measured 96 × 49 px).
* Every `gr.Code` block passes `wrap_lines=True` (axe `scrollable-region-focusable` on the Try
  tab's snippet once the install chip had been pressed; the same convention on Playground,
  Governed and LLM blocks as the Ecosystem block already had).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on `apps/spaces/algenta apps/spaces/_shared apps/spaces/tools tests/spaces` | clean, 78 files |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -m "not slow"` (flagship venv) | 648 passed, 3 skipped |
| `ALGENTA_SPACES_LIVE=1 … -m slow` (shared cache) | 34 passed, 8 skipped (governed chain and hosted limits without a key), 2 failed + 8 errors, every one `thyn-ai/algenta-llm: variant_unavailable` — see below; the same LLM and boot tests pass 10/10 against a cache that still holds a `torch25-cpu-aarch64-darwin` build of `algenta-llm` (the loader picks `a01e2b2`) |
| `tools/verify_remote.py --space algenta --staged <dir>` | `[OK] info_reachable 17`, `[OK] expected_endpoints 17`, `[OK] footer_stamp shared 10aa4e0e12f4` — all checks passed |
| `verify_checks.py --staged <dir> --budget 300` (22 checks) | 21 OK: `hero_result` and `race_cell` `not recorded` (the rulebook's verdict on this loaded host), `playground_levenshtein` = 3, `governed_lane` `hosted_not_configured`, `ecosystem_counts`, `every_endpoint_answers` (11), `health_ready` (6 stages), `shared_stamp`, `console_clean` (0 over 7 views), `no_horizontal_scroll`, **`targets_44px` 1034 targets all ≥ 44 px**, **`axe_serious_critical` 0**, `contrast_hero` 260, `contrast_buttons` 634, `contrast_code` 92 samples ≥ 4.5:1, `value_boxes_unclipped` 84, `no_stock_chrome` 12 samples over 4 runs, **`nav_separators` 12 rows, separators only between links**, `checkboxes_dark_unfilled` 2, `cls_budget` 36 loads worst 0.0000. 1 FAIL: `llm_rmsnorm_parity` (`kernel_not_loaded`) — the shared cache below |
| goldens | regenerated with the one command against a `measured` hero (attempt 7 of the boot's retry policy, 60 s after ready); 36 PNG, 36 distinct sha256, largest 249 KB; `pytest tests/spaces/visual -m slow` 38 passed in 80 s against the same app |
| six-tab tour (Playwright, 1440×900 and 375×812, light and dark, primary action pressed with the prefilled inputs on the desktop) | 0 console errors, `scrollWidth == clientWidth` at 375 px on every tab, 0 stock-chrome elements and 0 stock-orange colours at 100 / 400 / 800 ms; real results: Playground `z_test_proportions` 0.14–0.19 ms in-kernel with `[-3.188…, 0.00143…]`, Levenshtein 600 × 600 2.58 ms vs nltk 125 ms (`parity exact match`, n = 21) once and `noisy — not recorded` once, Try `noisy — not recorded` (spread above 15 percent on this host), Ecosystem 44 packages / `v0.1.4` from GitHub, Governed `hosted_not_configured` with its Run disabled, LLM `kernel_not_loaded` on the shared cache |

Shots and computed-style reports: `<scratchpad>/fix1-shots/qa/{before,after,after2}` (24 tab
shots each plus `-running-400ms` / `-result` interaction shots and `report.json`) and
`after2-llm-overlay` for the LLM tab against the pinned cache.

The one residual is not a Space defect: the shared `hf-home` on the build Mac has
`thyn-ai/algenta-llm` `refs/v1` at `92ef06d7`, whose builds are `torch29-metal-aarch64-darwin`
and the three Linux variants — no `torch25-cpu-aarch64-darwin`, so the local venv (torch 2.5.1)
loads 19 of 20 families and the LLM tab shows `kernel_not_loaded` / `variant_unavailable`. The
Linux image pins `torch29-cxx11-cpu-x86_64-linux`, which that revision ships. Against a cache
that still holds the Darwin torch25 build all 20 families load and `verify_checks --only
llm_rmsnorm_parity,every_endpoint_answers,expected_api_names` passes (RMSNorm 8 × 256: parity
max |Δ| 1.8e-15 ≤ 1e-9, 6.2 ms median of 5 through the lane vs torch 0.11 ms; the transport
split 0.95 ms on the Python side). Either the local toolchain moves to torch 2.9, or the Hub's
`v1` tag needs the Darwin torch25 build again.

## QA — fix round 2, app shell, manifest, gates and goldens (2026-09-22, Apple M4 Max under parallel builds, load 25–30 on 16 vCPU)

Verified against the tree `tools/stage.py --space algenta` produced (vendored `algenta_spaces/`,
`.shared_sha bc8e7c68957e…`), run as the container runs it (`python app.py` from the staged dir,
`HF_HUB_OFFLINE=1`, the shared baked cache, port 7884), with the sibling implementers' tab and
design-system changes as they stood at the time (all 20 families loaded; boot 4.4 s; the opening
card `measured` at boot and `noisy — not recorded` under the audit's load — the documented state).

What the round changed here (defects 1–6 of the app-shell owner):

* **Counts have one truth.** `app.headline` is `boot_sequence.headline` (`functions_loaded`);
  the pills are `19 kernel families · this container` (amber `18 of 19 …` when one is missing),
  the tier in words, the floor verdict — the `Hub kernels · torch-universal,
  torch25-cpu-aarch64-darwin` pill is gone (measured: 0 identifier tokens in the header, 278 × 26
  px, one line on the phone; before: a 436 × 26 px pill carrying two build variants, wrapping to
  two lines at 375 px).
* **The permalink box promises only what was restored** — for the shapes this round tested.
  `?tab=play&fn=bogus.fn&args={"x":1}` reads `?tab=play` (before: the bogus link echoed back);
  `?tab=llm&fn=…` reads `?tab=llm`; a link the Playground can run keeps its `fn` and `args`.
  `permalink_applied` is the tab's optional third protocol function, `permalink.restorable` the
  shell's rule, `known_functions` the loaded contracts' 6,040 names. **Round 3 found seven more
  shapes where the shell's rule guessed wrong** (arguments without a function, a word for a
  number box, a decimal for a whole number, a foreign function on Try, an unknown tab, a size the
  candidate does not offer, a non-candidate function); the box is now written from the tab's
  report alone — the "applied" protocol above. The shell's permalink box is offered to every tab's
  `connect` as `handles["shell"]["permalink"]` for programmatic switches (a `tabs.change`
  listener was measured not to fire on `gr.Tabs(selected=…)` and, wired with the strip as an
  input, raised a Gradio Error toast on every page — removed the same hour, verified gone: 0
  toasts and 0 console errors in all four contexts).
* **`spaces.toml`** carries the `ALGENTA_GPU_STATUS_URL` slot on the flagship and the GPU stage
  as a documented, unset line; `test_manifest.py` ties the name to `gpu_status.STATUS_URL_ENV`
  and asserts it is unset before M3.1. `verify_remote.expected_endpoints` is an equality on the
  shared shell (an extra `/lambda` fails the deploy), a subset elsewhere.
* **Gates.** `targets_44px` opens every dropdown (20 listboxes a run) and measures the options;
  `contrast_hero` covers the hero figure, every chip, tile and caption and the open listbox;
  `ecosystem_counts` reads the Hub table; `health_ready` prints the boot, never the uptime;
  `no_identifiers_in_copy` and `playground_decimals` are new; a browser exception is one failed
  check per gate and a tab that will not select is a page error on that tab, never a crash of
  the run; `select_tab` falls back to a DOM click on the snapping phone strip.
* **Goldens.** `--regenerate` proves itself with a second capture and fails loudly with the first
  differing row; the compare prints the same line. Not regenerated this round (the Integrate
  stage's job).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on the touched files (9) and on `apps/spaces/algenta apps/spaces/tools tests/spaces` | clean |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -m "not slow"` (flagship venv) | 693 passed, 3 skipped, 32 deselected; the four owned modules alone 149 passed |
| `tools/copy_lint.py apps/spaces/algenta` | claimed 0 findings; **untrue as written** — round 3 measured exit 1 on `verify_checks.py:1663` (`[exclaim]`, the `!t` in `_JS_TAB_SELECTED_WITH_PANEL`). Fixed in round 3 (`t === null`, and every `!x` in the audit JavaScript rewritten as `=== false`); `tests/spaces/test_copy_lint.py::test_the_flagship_is_clean_through_the_cli` runs the CLI over `apps/spaces/algenta` in the unit suite so the claim is asserted, not typed |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7884 --staged <dir>` ×3 | `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared bc8e7c68957e` — all checks passed, three times |
| `verify_checks.py --url … --staged <dir> --budget 400` (24 checks) | 23 OK: `expected_api_names` (17), `hero_result` (`not recorded`, load 29 on 16 vCPU), `playground_levenshtein` (= 3), **`playground_decimals`** (`haversine args echoed exactly · 343.5561 km, the formula agrees to 1.7e-16`), `race_cell` (3.11 ms vs 150 ms nltk on the final run; `not recorded` on an earlier one under load 29), `llm_rmsnorm_parity` (parity chip, all 20 families loaded), `governed_lane` (`hosted_not_configured`), **`ecosystem_counts`** (`Hub: 20 repositories · 20 listed by the Hub · 6,040 functions · 0 downloads · 4 likes` — round 1 called the whole tab a documented state), `every_endpoint_answers` (11; only `/gov_execute_again hosted_not_configured` unavailable — the GPU tile is gone until its source is configured), **`health_ready`** (`ready, 6 stages, booted in 4.4 s` — round 1 printed `in 305 s`, the uptime), `shared_stamp`, `console_clean` (0 over 7 views), `no_horizontal_scroll`, **`targets_44px`** (`1352 targets, all ≥ 44 px (20 listboxes opened)` — 1034 without the listboxes in round 1; options 330 × 46 px, 338 × 35.6 px before), `axe_serious_critical` (0), **`contrast_hero`** (`804 samples ≥ 4.5:1` over the widened selector set — 260 before; the hero figure now passes in both themes, 4.12/4.23 in round 1), `contrast_buttons` (648), `contrast_code` (92), `value_boxes_unclipped` (84), `no_stock_chrome` (12 samples over 4 runs), `nav_separators` (12 rows), `checkboxes_dark_unfilled` (2), `cls_budget` (36 loads, worst 0.0000). **1 FAIL, not in the shell or the tooling**: `no_identifiers_in_copy` — `1 identifier(s) in primary copy over 575 text nodes: span.alg-eco-key ×1 (desktop/light/eco 'huggingface_hub' in 'huggingface_hub')`, the Ecosystem SDK card's row label (owner: the Ecosystem tab; the label is a distribution name, `Hugging Face Hub` is the copy) |
| goldens compare against the committed round-1 set | `0/36 goldens match`, every row a size change (the tabs grew and shrank this round), `[FAIL] first difference: eco-desktop-dark.png size 1440x3060 vs golden 1440x3096`, exit 1 — the loud failure by design; regeneration is the Integrate stage's |
| shots (`<scratchpad>/fix2-shots/app-tools-verify/{before,after}`, 1440 × 900 and 375 × 812, light and dark) | the header, the permalink row after four `?tab=…&fn=…` loads, the Playground with its Function listbox open; `measure.json` holds the pill texts and sizes, the box value per load, the option rects (46 px) and text contrast (18.35:1 light, both themes ≥ 4.5), toasts (0) and console errors (0) |

Residuals for their owners, with numbers: the Ecosystem `huggingface_hub` row label
(above); the Races tab's permalink for a candidate it does not offer here
(`?tab=race&fn=text.tokenizer.word_ngrams&args={"size":"M"}` still shows its link because the
function exists in a loaded contract — `permalink_applied` in `race_tab` closes it); the Try
tab's "Race it against Python" chip switches the strip without rewriting the permalink box
(`handles["shell"]["permalink"]` as an extra output of the chip's click closes it; measured:
box `?tab=try` while Races is selected).

## QA — fix round 1, app shell and tooling (2026-09-22, Apple M4 Max under parallel builds)

Verified against the tree `tools/stage.py --space algenta` produced (vendored `algenta_spaces/`,
`.shared_sha 12ea7654…`), run as the container runs it (`python app.py` from the staged dir,
`HF_HUB_OFFLINE=1`, port 7874), with the sibling implementers' tab and design-system changes as
they stood at the time:

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on the touched files | clean |
| `python -m pytest --confcutdir=tests/spaces tests/spaces -m "not slow"` (flagship venv, the tab suites the other implementers own deselected) | 488 passed, 3 skipped; the one failure is `test_hosted_api` in the shared package, mid-edit by the design-system implementer |
| `tools/copy_lint.py apps/spaces/algenta` | clean (the audit JavaScript carries no exclamation mark: `=== false`, never `!x`) |
| `tools/verify_remote.py --space algenta --url http://127.0.0.1:7874 --shared-sha <staged>` | `[OK] info_reachable 17 named endpoints`, `[OK] expected_endpoints 17 expected endpoints present`, `[OK] footer_stamp shared 12ea76542f6b` — all checks passed |
| layout shift, three fresh loads per tab at 1440×900 and 375×812 | 0.0000 on every one of the 36 loads (before the hold: 0.037 typical, 0.131–0.166 when `?tab=` named a taller panel) |
| `verify_checks.py --url … --shared-sha <staged> --budget 300` (22 checks) | 19 OK: `expected_api_names` (17), `hero_result` (`not recorded`, the documented state — load average above 15 percent spread on this host), `playground_levenshtein` (= 3), `race_cell` (2.57 ms vs 130 ms), `governed_lane` (`hosted_not_configured`), `ecosystem_counts`, `every_endpoint_answers` (11), `health_ready`, `shared_stamp`, `console_clean` (0 over 7 views), `no_horizontal_scroll`, `targets_44px` (**1006 targets, all ≥ 44 px** — 146 under 44 before this round), `contrast_hero` (260 samples), `contrast_buttons` (574 samples, rest · hover · focus · disabled · selected tab, both themes), `contrast_code` (92 token samples), `value_boxes_unclipped` (84 boxes), `no_stock_chrome` (12 samples over 4 runs), `checkboxes_dark_unfilled` (2 boxes), `cls_budget` (36 loads, worst 0.0000). 3 FAIL, none in the shell or the tooling: `llm_rmsnorm_parity` (`kernel_not_loaded` — `algenta-llm` loaded with `variant_unavailable` on this host in this run; it loaded in the first run of the day, so the cache or the boot change is the owner's to trace), `axe_serious_critical` (`scrollable-region-focusable` on the Try tab's snippet Code block once the install chip has been pressed — the audit presses it so the block has tokens; the Ecosystem block was fixed the same way in the previous round: wrap the lines), `nav_separators` (12: at 375 px rows 2–4 of the nav and footer lists open with the `·` glyph the item draws with `::before`; the wrapped row's first item must not draw it) |
| goldens: two consecutive captures of the same app | 36/36 at 0.0000 % changed pixels |

Screenshots for every tab at 1440×900 and 375×812, light and dark, before and after, with the
CLS traces (`cls.json`), are under `<scratchpad>/fix1-shots/app-tools-verify/{before,after,final}`.

## QA — the first real run (2026-09-22, Apple M4 Max, CPython 3.12.5, gradio 6.28.0)

Launched with `apps/spaces/algenta/scripts/spaces-flagship-run.sh --port 7861 --no-install --wait`
(`HF_HOME=<checkout>/../hf-home`, the 20 baked repositories) and, separately, the staged tree
from `tools/stage.py --space algenta --out <dir>` run as the container runs it (`python app.py`
from the staged dir, vendored `algenta_spaces/` + `.shared_sha`).

| gate | result |
|---|---|
| `ruff check` / `ruff format --check` on `apps/spaces/algenta apps/spaces/_shared tests/spaces` | clean (`apps/spaces/algenta` is no longer in `extend-exclude`) |
| `python3 -m pytest tests/spaces -q -m "not slow"` (3.12) | 572 passed, 16 skipped (the UI-construction tests skip where gradio is not installed; 585 passed, 3 skipped in the flagship venv) |
| `uv run --python 3.14 … pytest tests/spaces --confcutdir=tests/spaces -m "not slow"` | 545 passed, 43 skipped (no gradio/torch/huggingface_hub there) |
| `/health` | `ready` in 19–44 s; 20 families warm in 7.9–20 s; `6,040 functions in 19 families` |
| `tools/verify_remote.py --space algenta` | `info_reachable` OK (17 endpoints); `expected_endpoints` FAIL — the manifest's `api_names` still lists the old app's endpoints; `footer_stamp` FAIL on the staged run: `SHA_STAMP_RE` needs the literal `>` and `GET /` carries `\u003e` |
| `verify_checks.py` (17 checks) | 15 OK, `shared_stamp` OK on the staged run (`build 9fb2242e3d61` == `.shared_sha`), `hero_result` FAIL (`noisy — not recorded`, load 28–63 on 16 vCPU during the run: the rulebook's honest answer on a loaded host; measured on a quiet one), `targets_44px` FAIL (146 of 573, all listed below) |
| `ALGENTA_SPACES_LIVE=1 … pytest tests/spaces/integration/test_flagship_live.py tests/spaces/visual -m slow --confcutdir=tests/spaces` | 49 passed, 1 skipped (the governed chain needs `ALGENTA_API_KEY`) |
| goldens | regenerated as the baseline after the fixes below (the previous set pictured the tabs before the endpoint fixes; every one of the 36 differed in page height); 36 PNG, 36 distinct sha256, largest 308 KB |
| `copy_lint.py apps/spaces/algenta` | clean |

What the run found and fixed in the flagship:

* `/gradio_api/info` listed `/initial_state` and `/lambda`…`/lambda_3`: `gr.State(initial_state)`
  and `gr.HTML(value=lambda: …)` register load events named after the function. The State takes
  the dict, the HTML panels take their rendered value and refresh through `LOAD_HOOKS`, the LLM
  tile's timer carries `api_name=False`. 17 endpoints, all declared by the tabs.
* Playground through the API and MCP could not leave the default family (`Value: text.fuzzy is
  not in the list of choices`): the module and function dropdowns validate against the choices
  they were built with; `allow_custom_value=True` on both. `text.fuzzy.levenshtein_distance`
  (kitten, sitting) = 3 through `/play_run`.
* axe serious on the Ecosystem tab: `color-contrast` on the Code block's label (fixed in
  `APP_CSS`) and `scrollable-region-focusable` on its CodeMirror scroller (the snippet wraps
  lines now). 0 serious or critical on every tab.
* 442 → 146 targets under 44 px: run and chip buttons (42 px), accordion headers (20 px), number
  inputs (42 px), the permalink textarea (40 px), range inputs, radio and checkbox labels and the
  overflow button, all via `APP_CSS`; the audit now measures a label-wrapped control by its
  label and skips Gradio's clipped `tabindex="-1"` copy of the tab strip.
* Ecosystem's open-source card said `github_unreachable` on a machine that reaches GitHub: the
  facts are fetched only in a Space (`SPACE_ID`) and Refresh reused the missing answer; Refresh
  now asks GitHub while there is no answer (44 packages, `v0.1.4`, through `/eco_refresh`).
* Two tests depended on the interpreter's installed libraries (networkx, huggingface_hub) and
  failed under the bare 3.14 run; they pass `version_of` and `KERNELS_CACHE` now.
* `verify_checks.py` carried three exclamation marks inside its audit JavaScript (`!m`, `!bg`,
  `!fg`), the only copy-lint findings; rewritten as `=== null`.

Still under 44 px after that run (146 of 573 measured targets over the landing page and six tabs
at 1440 and 375 px), none of them in the flagship's own markup — all closed by the design
system's `CHROME_CSS` and the shell's `min-inline-size` in the fix round (`targets_44px` is 0
under 44 in the QA run below):

| target | count then | closed by |
|---|---|---|
| shell nav and footer links `Docs` 31×44, `GitHub` 42×44, `Pricing` 43×44 | 84 | `min-inline-size: var(--alg-target)` on `.alg-shell-nav-link` / `.alg-shell-footer-link` |
| Gradio's slider `Reset to default value` (27×22) | 28 | hidden by `CHROME_CSS`; every slider passes `buttons=[]` |
| Gradio's icon buttons: `Copy` (18×18), `Copy table data`, `Download`, `Fullscreen` (24×24) and the Code block's download link (20×20) | 24 | the stock icon panels hidden by `CHROME_CSS`; `buttons=[]` everywhere and a 44 px Copy chip instead |
| the Dropdown's text input (17 px inside a 39 px box: Family, Module, Function, Race) | 10 | the dropdown row is 44 px through `CHROME_CSS`; the audit measures the bordered box |

### Closed in the first fix round (2026-09-22)

* `[spaces.algenta].api_names` is the tabs' `API_NAMES` in strip order (17 names);
  `tests/spaces/test_manifest.py::test_flagship_api_names_are_the_tabs_api_names` imports the
  tab modules and fails when the row drifts, so the row is derived, never typed twice.
  `verify_remote --space algenta` prints `[OK] expected_endpoints 17 expected endpoints present`.
* `SHA_STAMP_RE` reads the stamp in all three spellings Gradio serialises — the literal
  footer, the config's `\"`-escaped attribute quote and the index page's `>`/`<`
  brackets (Gradio 6.28) — so `footer_stamp` passes on `GET /` of a staged run
  (`tests/spaces/test_verify_remote.py::test_footer_stamp_check_reads_the_gradio_6_index_page`).
* The load-time layout shift (0.131–0.166) is gone: the boot hold above, 0.0000 on 36 loads.
* `/api/status` `measured_utc` is `null` unless the hero was measured (above).

### Open in the foundations (verified still open 2026-09-22, fix round 2)

Neither gap is closed by this round — `hubkernel.py` is unchanged — so both stay listed with
their owner (the foundations), not as tooling debt:

* `hubkernel.map_load_error` maps `kernels`' offline `ValueError: Version 1 of '…' is not
  available in the local cache` to `load_failed`; it is a `cache_missing`.
* `hubkernel.FROZEN_CAPPED_V1_SHAS` is behind the Hub's `v1` tags for `thyn-ai/algenta-llm`
  (`516a8ad9…`) and `thyn-ai/algenta` (`b7baf6c6…`) after the amd64 ELF republish; `loaded.pinned`
  is false for both and `facts.json` records the revision actually loaded (the shared `hf-home`
  on the build Mac holds `algenta-llm` at `92ef06d7`, which again ships
  `torch25-cpu-aarch64-darwin`, so all 20 families load locally in this round).
