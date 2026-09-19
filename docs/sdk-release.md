# SDK releases are automatic

A pull request that changes SDK source is the whole release. Nothing else to open.

1. Merge the pull request (Codna review + CI as usual).
2. `sdk-auto-bump.yml` sees SDK source changed on `main` and pushes one commit as the sync App:
   `chore(release): SDK X.Y.Z` — all nine lockstep version fields moved by
   `scripts/bump_sdk_version.py` (python-sdk, algenta and mcp `pyproject.toml`, the two
   `__version__` files, the MCP server's `_FALLBACK_VERSION` in `algenta_mcp/config.py`,
   `package.json`, the lockfile's root package, `server.json`).
3. `auto-tag-sdk.yml` tags that commit `sdk-vX.Y.Z` (App token, so the tag triggers workflows).
4. `release-sdks.yml` publishes `algenta-mcp`, mirrors to `thyn-ai/algenta-sdk`, signs the release
   authorization, tags the SDK repo; its `release.yml` publishes `algenta-sdk` to PyPI and npm.

| You want | Do |
|---|---|
| a patch release | nothing — every merge that touches SDK source is one |
| a minor / major release | label the pull request `release:minor` / `release:major` before merging |
| no release for this merge | label it `release:none` (tests/docs-only changes never release anyway) |
| a release with no code change | Actions → `sdk-auto-bump` → Run workflow (pick the level) |
| a hand bump anyway | edit the fields with `python3 scripts/bump_sdk_version.py --level …`; auto-tag still tags it |

Guards: the bump refuses a half-bumped tree (`tests/test_sdk_package_metadata.py` runs before the
push); a version whose `sdk-v…` tag does not exist yet is never bumped again (a release is in
flight, or auto-tag needs a re-run); the bump commit itself skips image builds and deploys in
`ci.yml` (nothing in the engine images depends on the SDK version string). The sync App
(`algenta-sdk-sync`) is a bypass actor on the `main` rulesets for exactly this push.
