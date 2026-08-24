---
icon: shield-halved
description: Scope CI security scans with repository-intelligence blast radius — skip when the diff touches nothing in a language, scope the analysis to the change's dependency closure, and fall back to a full scan on any ambiguity.
---

# Adaptive security scanning

Adaptive security scanning makes a CI security scanner proportional to the change it checks. Instead of re-analyzing the entire repository on every pull request, the scan is scoped through the same **blast radius** the [repository-intelligence graph](repository-intelligence.md#explore-impact-optional) computes: the changed files plus everything that transitively depends on them. The reference implementation ships in this repository — `scripts/adaptive_codeql_scope.py` driven from `.github/workflows/codeql.yml` — and works with GitHub CodeQL out of the box.

## Decision model

Every scan leg (one per language) resolves to exactly one decision:

| Decision | Condition | Effect |
| --- | --- | --- |
| `skip` | The diff contains nothing the leg's language analyzes. | The leg exits early; the scanner never starts. |
| `differential` | A bounded blast-radius closure was computed. | Analysis is restricted to the closure via a generated CodeQL `paths:` config. The check fails on any alert found inside the scope. SARIF is not uploaded. |
| `full` | Push to a protected branch, weekly schedule, manual dispatch, or any ambiguity. | The whole repository is analyzed and SARIF is uploaded to code scanning, exactly like a conventional setup. |

Files the leg's extractor does not analyze — documentation, dependency manifests (`pyproject.toml`, `package.json`), and lockfiles — carry nothing scannable, so a diff confined to them **skips** the leg rather than building an empty database. Ambiguity that could hide a real change resolves to `full`: an unresolvable merge-base, an unmappable Python change, a scan-infrastructure change (the CodeQL config, the scan workflow, the scope script itself), a closure above the size guard, or an unparseable static config.

## Scope computation

1. **Change set.** Pull request: `merge-base(origin/<base_ref>, HEAD)..HEAD` with a progressive, depth-capped history fetch. Push: `event.before..event.after` (opt-in; the shipped workflow keeps push full). Schedule and manual dispatch: no diff — full scan.
2. **Blast-radius closure.** Python changes are expanded through the reverse import graph — the same engine used for repository-aware test selection — so the scope covers the changed modules and every transitive importer. JavaScript/TypeScript and GitHub Actions legs scope to the changed files of that language (`.js`/`.jsx`/`.ts`/`.tsx`/`.mjs`/`.cjs` sources, and workflow/composite-action YAML under `.github/workflows/` and `.github/actions/` respectively). Every emitted path is repository-relative and extractable by the leg; a closure with zero extractable files skips.
3. **Static-config merge.** The differential config merges the generated `paths:` with the checked-in CodeQL config's `name`, `paths-ignore`, `packs`, and `queries`, so custom query suites apply unchanged.
4. **Guards.** Deleted files are not seeds. Closure size is capped (`--max-files`, default 2000) and shared-core changes (closure ≥ 40% of indexed files) scan in full.

Bias: when in doubt, scan more, never less. A false "in scope" costs minutes; a false "out of scope" ships a vulnerability.

## GitHub Actions reference workflow

`.github/workflows/codeql.yml` runs one matrix leg per language (`actions`, `javascript-typescript`, `python`). Each leg checks out, asks the scope script for a decision, and then either exits early, runs a scoped analysis, or runs the full analysis:

```yaml
- name: Compute adaptive scope (blast radius)
  id: scope
  run: |
    python3 scripts/adaptive_codeql_scope.py \
      --language "${{ matrix.language }}" \
      --out-dir "$RUNNER_TEMP/codeql-scope"

- name: Initialize CodeQL
  if: steps.scope.outputs.decision != 'skip'
  uses: github/codeql-action/init@v4
  with:
    languages: ${{ matrix.language }}
    build-mode: none
    config-file: ${{ steps.scope.outputs.decision == 'differential' && steps.scope.outputs.config_path || '.github/codeql/codeql-config.yml' }}

- name: Perform CodeQL analysis
  if: steps.scope.outputs.decision != 'skip'
  uses: github/codeql-action/analyze@v4
  with:
    category: /language:${{ matrix.language }}
    upload: ${{ steps.scope.outputs.decision == 'full' && 'always' || 'never' }}
```

SARIF handling:

| Run type | SARIF upload | Check outcome |
| --- | --- | --- |
| Full (push, schedule, dispatch, ambiguity) | Uploaded; `category: /language:<language>` stays stable across runs. | Standard code-scanning behavior. |
| Differential (PR) | Not uploaded — partial-scope results would create alert churn. | The leg fails when any non-suppressed alert is found inside the scope. |
| Skip (PR, empty scope) | None. | The leg succeeds without starting the scanner. |

## Scope script CLI

`scripts/adaptive_codeql_scope.py` is stdlib-only — it runs on any runner with a Python 3 interpreter and a checkout, no dependencies, no credentials, no network.

```bash
python scripts/adaptive_codeql_scope.py --language python
python scripts/adaptive_codeql_scope.py --language actions --changed .github/workflows/ci.yml
python scripts/adaptive_codeql_scope.py --language python --full
```

| Flag | Meaning |
| --- | --- |
| `--language` | `python`, `javascript-typescript`, or `actions` (required). |
| `--changed <files…>` | Explicit changed-file list (skips git; for tests and local runs). |
| `--event-type` | Override `GITHUB_EVENT_NAME`. |
| `--base-ref` | PR base ref (default `GITHUB_BASE_REF`, then `main`). |
| `--full` | Force a full scan. |
| `--allow-push-diff` | Let push events scope from `event.before..event.after` instead of full. |
| `--out-dir` | Destination for the generated differential config (default `$RUNNER_TEMP/codeql-scope`). |
| `--max-files`, `--shared-core-fraction` | Closure size guards (defaults 2000 and 0.40). |

Output is one JSON object on stdout — `decision`, `language`, `scope_count`, `reason`, `config_path` — mirrored to `$GITHUB_OUTPUT` when running in Actions.

## Notes

- Full scans remain the soundness baseline: every push, the weekly schedule, manual dispatch, and every ambiguous case run the complete analysis and upload SARIF.
- A differential scan analyzes the change's blast-radius closure. Alerts outside the closure are surfaced by the next full scan, not by the PR check.
- The graph engine traces Python import edges. JavaScript/TypeScript and Actions scopes are the changed files themselves.
- Generated configs are written to the runner's temp directory; the tracked `.github/codeql/codeql-config.yml` is never modified at runtime.

## Next steps

- [Triage a repository](repository-intelligence.md) — the graph-query endpoint the offline blast radius mirrors.
- [Use Algenta in CI/CD](ci-cd.md) — gating pipelines on engine results with the CLI.
- [Prove a security finding](security-analysis.md) — reachability proofs for scanner findings against a snapshot.
