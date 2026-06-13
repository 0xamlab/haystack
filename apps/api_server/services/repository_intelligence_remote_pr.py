"""Remote pull/merge-request creation for repository-apply (REMOTE_PR mode).

Extracted from repository_intelligence_execution_workflow to keep that module under the per-module
line budget. Pure move — no behavior change. The token-bearing PR/MR write to the customer's git
host goes through the egress guard (B10), so the self_hosted/air_gapped fail-closed policy + SSRF
check apply to the customer-configured api_base_url.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlparse

from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_RepoAccessToken = Callable[[dict[str, Any]], str | None]


def _config_remote_metadata(
    connector_type: str, config: dict[str, Any], repository_url: str
) -> dict[str, str]:
    parsed = urlparse(
        repository_url.replace("git@", "ssh://git@").replace(":", "/", 1)
        if repository_url.startswith("git@")
        else repository_url
    )
    path = parsed.path.removeprefix("/").removesuffix(".git")
    parts = [part for part in path.split("/") if part]
    if connector_type == "github_repo":
        if len(parts) < 2:
            raise RepositoryIntelligenceError(
                code="invalid_repository_config",
                message="GitHub repository_url must include owner and repo.",
                status_code=422,
            )
        return {"owner": parts[-2], "repo": parts[-1]}
    if connector_type == "gitlab_repo":
        return {"project_path": "/".join(parts)}
    if connector_type == "bitbucket_repo":
        if len(parts) < 2:
            raise RepositoryIntelligenceError(
                code="invalid_repository_config",
                message="Bitbucket repository_url must include workspace and repo slug.",
                status_code=422,
            )
        return {"workspace": parts[-2], "repo_slug": parts[-1]}
    raise RepositoryIntelligenceError(
        code="repository_remote_metadata_unsupported",
        message=f"Connector type '{connector_type}' does not support remote pull request creation.",
        status_code=409,
    )


async def _create_pull_request(
    *,
    connector_type: str,
    config: dict[str, Any],
    repository_url: str,
    source_branch: str,
    target_branch: str,
    title: str,
    body: str,
    repo_access_token: _RepoAccessToken,
) -> str:
    token = repo_access_token(config)
    if token is None:
        raise RepositoryIntelligenceError(
            code="repository_write_credentials_required",
            message=(
                f"{connector_type} remote PR creation requires access_token in "
                "connector config."
            ),
            status_code=409,
        )
    metadata = _config_remote_metadata(connector_type, config, repository_url)
    headers: dict[str, str]
    request_url: str
    payload: dict[str, Any]
    if connector_type == "github_repo":
        api_base = str(config.get("api_base_url") or "https://api.github.com").rstrip("/")
        request_url = f"{api_base}/repos/{metadata['owner']}/{metadata['repo']}/pulls"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        payload = {"title": title, "head": source_branch, "base": target_branch, "body": body}
    elif connector_type == "gitlab_repo":
        api_base = str(config.get("api_base_url") or "https://gitlab.com/api/v4").rstrip("/")
        request_url = (
            f"{api_base}/projects/{quote(metadata['project_path'], safe='')}/merge_requests"
        )
        headers = {"PRIVATE-TOKEN": token}
        payload = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": body,
        }
    else:
        api_base = str(config.get("api_base_url") or "https://api.bitbucket.org/2.0").rstrip("/")
        request_url = (
            f"{api_base}/repositories/{metadata['workspace']}/{metadata['repo_slug']}/pullrequests"
        )
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "title": title,
            "source": {"branch": {"name": source_branch}},
            "destination": {"branch": {"name": target_branch}},
            "description": body,
        }
    # B10: the token-bearing PR/MR write to the customer's git host goes through the egress guard so
    # the self_hosted/air_gapped fail-closed policy + SSRF check apply to the (customer-configured)
    # api_base_url. Deny raises before any socket; the existing >=400 mapping is preserved.
    from apps.api_server.services import egress_guard
    from apps.api_server.services.egress_guard import EgressPolicyDeniedError

    try:
        response = await egress_guard.async_http_request(
            method="POST",
            url=request_url,
            surface="repository_remote_pull_request",
            egress_class="customer_connector",
            explicit_configured=True,
            headers=headers,
            json=payload,
            client_kwargs={"timeout": 30.0},
        )
    except EgressPolicyDeniedError as exc:
        raise RepositoryIntelligenceError(
            code="remote_pull_request_egress_denied",
            message="Remote pull request creation was denied by the egress privacy policy.",
            status_code=502,
            details={"surface": "repository_remote_pull_request"},
        ) from exc
    if response.status_code >= 400:
        raise RepositoryIntelligenceError(
            code="remote_pull_request_failed",
            message=f"Remote pull request creation failed with status {response.status_code}.",
            status_code=502,
            details={"response": response.text},
        )
    data = response.json()
    pr_url = (
        data.get("html_url")
        or data.get("web_url")
        or data.get("links", {}).get("html", {}).get("href")
        or data.get("links", {}).get("self", {}).get("href")
    )
    if not isinstance(pr_url, str) or not pr_url:
        raise RepositoryIntelligenceError(
            code="remote_pull_request_missing_url",
            message="Provider created a pull request but did not return a browser URL.",
            status_code=502,
        )
    return pr_url
