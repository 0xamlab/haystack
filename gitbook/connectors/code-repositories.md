---
icon: code-branch
description: Create a repository connector for GitHub, GitLab, Bitbucket, a local checkout, or an archive, test that the source is reachable, and browse its files to feed repository intelligence.
---

# Connect a code repository

By the end of this page you will have a saved repository connector that reaches your source code, a confirmed reachability test, and a browse listing of the files and directories it exposes — ready to feed [repository intelligence](../guides/repository-intelligence.md). Algenta supports five repository source types through one connector API: `github_repo`, `gitlab_repo`, `bitbucket_repo`, `local_repo`, and `repo_archive`.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and access to the source — a clone URL (with a token for private repositories), a filesystem path, or an archive path. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
Repository connectors take these `config` fields. For `github_repo`, `gitlab_repo`, and `bitbucket_repo`: `repository_url` (aliases `clone_url`, `url`) — an `http(s)` clone URL — plus an optional `access_token` (aliases `token`, `api_token`) for private repositories. For `local_repo`: `path` — a filesystem path to a git working tree or directory the engine can read. For `repo_archive`: `path` — a filesystem path to a `.tar`, `.tar.gz`, or `.zip` archive, which the engine extracts and reads. These are the only fields the engine reads.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment. For a private hosted repository, keep the access token in its own variable so it never appears in shell history inline.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export GITHUB_TOKEN="$GITHUB_TOKEN"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

**Expected result:** `key present` and your base URL print without error. A token is only needed for private repositories.
{% endstep %}

{% step %}
### Confirm the engine accepts repository types

Ask the engine which connector types it supports and confirm your repository type is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes the repository types, for example `{"types": ["github_repo", "gitlab_repo", "bitbucket_repo", "local_repo", "repo_archive", ...]}`. If your type is present, the next step's `config` shape is accepted.
{% endstep %}

{% step %}
### Create the repository connector

`POST /v1/connectors` stores the connector and returns it with `status: "untested"`. Pick the tab that matches where your code lives.

{% tabs %}
{% tab title="GitHub" %}
Use type `github_repo` with an `http(s)` `repository_url`. For a private repository, add an `access_token` — the engine uses it as the `x-access-token` clone credential.

```bash title="Create a github_repo connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"payments-service\",
    \"connector_type\": \"github_repo\",
    \"config\": {
      \"repository_url\": \"https://github.com/acme/payments-service.git\",
      \"access_token\": \"$GITHUB_TOKEN\"
    }
  }"
```
{% endtab %}

{% tab title="GitLab" %}
Use type `gitlab_repo` with an `http(s)` `repository_url`. For a private project, add an `access_token` — the engine uses it as the `oauth2` clone credential.

```bash title="Create a gitlab_repo connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"billing-lib\",
    \"connector_type\": \"gitlab_repo\",
    \"config\": {
      \"repository_url\": \"https://gitlab.com/acme/billing-lib.git\",
      \"access_token\": \"$GITLAB_TOKEN\"
    }
  }"
```
{% endtab %}

{% tab title="Bitbucket" %}
Use type `bitbucket_repo` with an `http(s)` `repository_url`. For a private repository, add an `access_token` — the engine uses it as the `x-token-auth` clone credential.

```bash title="Create a bitbucket_repo connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"web-app\",
    \"connector_type\": \"bitbucket_repo\",
    \"config\": {
      \"repository_url\": \"https://bitbucket.org/acme/web-app.git\",
      \"access_token\": \"$BITBUCKET_TOKEN\"
    }
  }"
```
{% endtab %}

{% tab title="Local checkout" %}
Use type `local_repo` with a `path` to a checkout the engine can read. A git working tree lets the engine resolve a revision; a plain directory is read as-is.

```bash title="Create a local_repo connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "monorepo-local",
    "connector_type": "local_repo",
    "config": {
      "path": "/srv/repos/monorepo"
    }
  }'
```
{% endtab %}

{% tab title="Archive" %}
Use type `repo_archive` with a `path` to a `.tar`, `.tar.gz`, or `.zip` archive. The engine extracts it and reads the contents.

```bash title="Create a repo_archive connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "release-snapshot",
    "connector_type": "repo_archive",
    "config": {
      "path": "/srv/archives/release-1.4.0.tar.gz"
    }
  }'
```
{% endtab %}
{% endtabs %}

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, your `connector_type`, and `"status": "untested"`. Any `access_token` is encrypted at rest — the connector object never returns your `config` back to you.

{% hint style="warning" %}
Hosted repository URLs must be `http(s)` clone URLs — SSH URLs (`git@...`) are rejected with `Repository URL must be a http(s) clone URL`. Convert to the HTTPS form and supply an `access_token` for private repositories.
{% endhint %}
{% endstep %}

{% step %}
### Test that the source is reachable

`POST /v1/connectors/{id}/test` resolves the source for real — it shallow-clones a hosted repository, opens a local checkout, or extracts an archive — and reports the source and how many entries it found. On success the connector flips to `live`; on failure it flips to `error`.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "message": "Repository source reachable: https://github.com/acme/payments-service.git (4213 entries)."}`, and the connector's stored `status` is now `live`. On failure, `success` is `false`; `error_type` (for example `auth`, `not_found`, or `permission`) plus `recoverable` tell you what to fix.
{% endstep %}

{% step %}
### Browse the repository entries

`GET /v1/connectors/{id}/browse` lists the files and directories at the top of the source (up to 100 entries), so you can confirm the right code is reachable. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response whose `items` array holds repository entries (each with `id`, `label`, a `kind` of `file` or `directory`, a `selection` of `{"path": "<relative path>"}`, and — for files — a detected `language` and `size`), a `total`, and a message such as `Found 42 repository entries`.
{% endstep %}
{% endstepper %}

## Expected result

{% hint style="success" %}
You have a saved repository connector with `status: "live"`, a test that reports the source and its entry count, and a browse listing of its files and directories. The connector is now ready to drive [repository intelligence](../guides/repository-intelligence.md) — snapshots, triage, and governed decisions over your code.
{% endhint %}

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Repository connect flow with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID         # resolve and reach the source
de connectors browse $CONNECTOR_ID       # list the repository entries
```

```python title="Connect a repository with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="payments-service",
    connector_type="github_repo",
    config={
        "repository_url": "https://github.com/acme/payments-service.git",
        "access_token": os.environ["GITHUB_TOKEN"],
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "repository entries")
```

## Troubleshooting

{% hint style="warning" %}
**Test fails with `error_type: "auth"`.** The `access_token` is missing, expired, or lacks read access to a private repository. Refresh the token and confirm it can read the target repository.
{% endhint %}

{% hint style="warning" %}
**`Repository URL must be a http(s) clone URL`.** The `repository_url` is an SSH URL or uses an unsupported scheme. Use the HTTPS clone URL and add an `access_token` for private access.
{% endhint %}

{% hint style="warning" %}
**`repository source not found` for `local_repo` or `repo_archive`.** The `path` does not exist where the engine runs. On a self-hosted deployment, mount the checkout or archive so the engine process can read it.
{% endhint %}

{% hint style="info" %}
**Test fails with a privacy-policy or `error_type: "permission"` message.** The git host is outside your deployment's egress allowlist. Confirm the host and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.
{% endhint %}

## Next

{% content-ref url="../guides/repository-intelligence.md" %}
[repository-intelligence.md](../guides/repository-intelligence.md)
{% endcontent-ref %}

{% content-ref url="overview.md" %}
[overview.md](overview.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
