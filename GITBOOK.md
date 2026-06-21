# GitBook docs system — shared golden template (Algenta)

Algenta's docs follow the **shared golden template** used across all Thyn product docs (Codna is the
reference instance). Docs live in [`gitbook/`](gitbook/) as markdown, published via **GitBook Git
Sync**, and themed entirely through the **GitBook API** (GitBook allows no custom CSS/HTML/JS). One
**shared design system + interaction architecture** is fixed across products; only **brand** varies.

- **Site:** Algenta (`site_1Ujf5`) in the `Thyn` org (`o33uJH8DVq2cATtrgKVy`). Domain: `docs.algenta.ai`.
- **Source of truth:** [`gitbook/`](gitbook/) + [`gitbook/SUMMARY.md`](gitbook/SUMMARY.md) + [`.gitbook.yaml`](.gitbook.yaml).
- **Theme + brand:** applied via [`scripts/gitbook/`](scripts/gitbook/) (API), not committed CSS.

> **Layout note (Algenta-specific).** The Codna reference keeps tooling in `gitbook/` and pages in
> `docs/`. Algenta's `docs/` already holds engineering docs (which must not be published) and its
> pages already live in `gitbook/`, so here the GitBook **pages live in `gitbook/`** (the Git Sync
> root) and the **tooling lives in `scripts/gitbook/`** (outside the sync root). The contract,
> design system, archetypes, and QA gates are identical to the shared template.

## Apply / verify / audit

```bash
# theme this site = shared design system + Algenta's brand override
GITBOOK_API_KEY=$GITBOOK_API_KEY python3 scripts/gitbook/apply-customization.py scripts/gitbook/products/algenta.json

# read the live customization back and diff against intended (lock-gate check)
GITBOOK_API_KEY=$GITBOOK_API_KEY python3 scripts/gitbook/verify-customization.py scripts/gitbook/products/algenta.json

# enforce the docs interaction contract (also runs in CI via .github/workflows/docs-audit.yml)
python3 scripts/gitbook/audit.py gitbook/
```

Connect Git Sync once (UI, the only step the API key can't do): GitBook → Algenta site → Sync with
Git → GitHub → `thyn-ai/algenta`, branch `main` (reads `.gitbook.yaml`, root `gitbook/`). Thereafter
every push re-publishes.

## Shared design system (fixed across products)

[`scripts/gitbook/shared-customization.json`](scripts/gitbook/shared-customization.json) — Hybrid
Apple/Google: `theme: clean`, accent links, rounded + subtle, **Inter** + **JetBrains Mono**, github
code themes, Google **line** sidebar, prominent search. Apple system semantic colors (success
`#34C759`, warning `#FF9500`, danger `#FF3B30`, + dark variants). The accent/primary color is the
one styling value a product may override.

## Per-product override (brand only)

[`scripts/gitbook/products/algenta.json`](scripts/gitbook/products/algenta.json) — `siteId`,
`domain`, `primaryColor`, `hero`, `headerLinks`. **Favicon + logo are UI-managed** (GitBook →
Customization → Basic): GitBook has no upload API and product repos are private, so raw URLs 404 —
upload the icon + wordmark once in the UI; `apply-customization.py` never touches favicon/logo so it
can't clobber them. **Fixed:** the visual system, interaction grammar, page archetypes, and QA
gates. **May vary where the product genuinely differs:** terminology, destinations, workflows, and
information architecture (each instantiates the same archetypes + interaction rules).

## Interaction grammar (each block has one job)

| User need | Block | Behavior |
|---|---|---|
| Where do I start? | Cards | small set of outcome-based choices |
| Which option applies? | Tabs | mutually exclusive platforms/tools/paths |
| What do I do next? | Stepper | ordered actions, each verified |
| Did it work? | Success hint | the expected state/result |
| What could go wrong? | Warning/Danger hint | BEFORE the risky action |
| How do I fix it? | Expandable (`<details>`) | troubleshooting next to the step |
| What's the difference? | Table | compare on consistent criteria |
| What do I run? | Titled code block | one copy-ready command |
| Where now? | Cards | 1 primary + ≤2 secondary next actions |
| Exact details | Reference page | outline + anchors + stable headings |

Don't add a block unless it reduces uncertainty, shortens a workflow, or improves recovery. Never
nest `<details>` or a stepper inside a stepper step.

## Page archetypes (every page is exactly one)

`landing` (router: hero + grouped outcome cards, **outline off**) · `index` (section router: cards
by intent) · `task` (outcome → prerequisites → stepper → **expected result** → troubleshooting →
**Next**) · `concept` (definition → why → example → "use this when" → Next) · `integration`
(prereqs → tabs for setup paths → verify → troubleshooting → Next) · `reference` (**outline on**,
tables, titled examples; no Next required) · `troubleshooting` (by symptom: *What you see → Likely
cause → Resolution → Verify → Still blocked?*). The map lives in
[`scripts/gitbook/archetypes.json`](scripts/gitbook/archetypes.json).

## Frontmatter contract

```yaml
---
icon: <font-awesome-id>          # required; enterprise icons, never emoji
description: <=200 chars         # required
# landing only:
cover: .gitbook/assets/brand/algenta-hero.png
layout: { cover: {visible: true, size: hero}, tableOfContents: {visible: false}, outline: {visible: false} }
---
```
One noun-based H1 per page. No emoji anywhere. Brand-atmosphere hero only (no dense text in the PNG).

## Microcopy contract

- **Card titles = concrete outcomes** ("Run your first decision"), never "Learn more / Overview / Explore".
- **Headings** specific ("Verify the result"), not "Additional information".
- **Placeholders**: one convention — `$ALGENTA_API_KEY`, `$REPOSITORY_PATH`, `$ORGANIZATION_ID` (real env vars like `$GITHUB_TOKEN` stay). No `<token>` / `YOUR_TOKEN`.
- **Code blocks** always have a language/title; show expected output when it matters.

## Zero-dead-end rule

Every non-reference page ends with a deliberate continuation (1 primary + ≤2 secondary next-action
cards). A guide never ends on a bare code block. Reference pages may rely on sidebar + outline.

## QA checklist + golden-template lock gate

The audit ([`scripts/gitbook/audit.py`](scripts/gitbook/audit.py)) enforces the repo-side rules in
CI (Error/Warning/Advisory). Beyond the audit, a site is **locked** to the golden standard only
when: API read-back matches intended; audit has **zero errors**; canonical journeys pass on mobile +
desktop; **three fresh testers** each complete a journey (first decision · self-host the engine · API
integration) without verbal guidance, finding the first action in ≤2 clicks and identifying the next
step; **accessibility** passes (alt text, heading order, descriptive links, no color-only meaning,
keyboard-operable blocks, visible focus) in light + dark. The lock artifact lives under
[`scripts/gitbook/lock/`](scripts/gitbook/lock/) (verified JSON · audit output · journey results ·
light/dark + mobile/tablet/desktop screenshots · known platform limitations).

## Clone for the next product

Add `scripts/gitbook/products/<product>.json` (brand only), instantiate the same archetypes in that
product's docs, run `apply-customization.py` + `verify-customization.py` + `audit.py`, pass the lock
gate. The reusable unit is the **decision hierarchy, archetypes, interaction grammar, navigation
model, error-recovery pattern, zero-dead-end rule, audit, and QA** — not just colors.
