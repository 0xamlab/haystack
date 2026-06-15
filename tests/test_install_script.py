from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = ROOT / "install.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_stub_binaries(bin_dir: Path) -> None:
    _write_executable(
        bin_dir / "docker",
        textwrap.dedent(
            """\
            #!/bin/bash
            set -euo pipefail

            log_file="${ALGENTA_TEST_STUB_LOG:?}"
            printf 'docker %s\\n' "$*" >> "$log_file"

            if [ "$#" -ge 1 ] && [ "$1" = "info" ]; then
              if [ "${ALGENTA_TEST_DOCKER_INFO_FAIL:-0}" = "1" ]; then
                exit 1
              fi
              exit 0
            fi

            if [ "$*" = "compose version" ]; then
              if [ "${ALGENTA_TEST_DISABLE_DOCKER_COMPOSE_PLUGIN:-0}" = "1" ]; then
                exit 1
              fi
              exit 0
            fi

            if [ "$*" = "compose pull --quiet" ]; then
              exit 0
            fi

            if [ "$*" = "compose up -d" ]; then
              exit 0
            fi

            if [ "$*" = "compose exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head" ]; then
              exit 0
            fi

            if [ "$*" = "compose exec -T api python scripts/bootstrap_self_host.py" ]; then
              if [ -n "${ALGENTA_TEST_BOOTSTRAP_OUTPUT:-}" ]; then
                printf '%s\\n' "${ALGENTA_TEST_BOOTSTRAP_OUTPUT}"
              fi
              exit "${ALGENTA_TEST_BOOTSTRAP_EXIT_CODE:-0}"
            fi

            echo "unexpected docker call: $*" >&2
            exit 1
            """
        ),
    )
    _write_executable(
        bin_dir / "docker-compose",
        textwrap.dedent(
            """\
            #!/bin/bash
            set -euo pipefail

            log_file="${ALGENTA_TEST_STUB_LOG:?}"
            printf 'docker-compose %s\\n' "$*" >> "$log_file"

            if [ "$*" = "version" ]; then
              exit 0
            fi

            if [ "$*" = "pull --quiet" ]; then
              exit 0
            fi

            if [ "$*" = "up -d" ]; then
              exit 0
            fi

            if [ "$*" = "exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head" ]; then
              exit 0
            fi

            if [ "$*" = "exec -T api python scripts/bootstrap_self_host.py" ]; then
              if [ -n "${ALGENTA_TEST_BOOTSTRAP_OUTPUT:-}" ]; then
                printf '%s\\n' "${ALGENTA_TEST_BOOTSTRAP_OUTPUT}"
              fi
              exit "${ALGENTA_TEST_BOOTSTRAP_EXIT_CODE:-0}"
            fi

            echo "unexpected docker-compose call: $*" >&2
            exit 1
            """
        ),
    )
    _write_executable(
        bin_dir / "curl",
        textwrap.dedent(
            """\
            #!/bin/bash
            set -euo pipefail

            log_file="${ALGENTA_TEST_STUB_LOG:?}"
            printf 'curl %s\\n' "$*" >> "$log_file"

            output_path=""
            url=""
            while [ "$#" -gt 0 ]; do
              case "$1" in
                -o)
                  output_path="$2"
                  shift 2
                  ;;
                *)
                  url="$1"
                  shift
                  ;;
              esac
            done

            if [[ "$url" == http://localhost:*"/v1/health" ]]; then
              if [ "${ALGENTA_TEST_HEALTH_FAIL:-0}" = "1" ]; then
                exit 22
              fi
              exit 0
            fi

            if [[ "$url" == https://api.github.com/repos/algenta/decision-engine/commits/main ]]; then
              if [ -n "${ALGENTA_TEST_COMMIT_SHA:-}" ]; then
                printf '{"sha":"%s"}\n' "${ALGENTA_TEST_COMMIT_SHA}"
                exit 0
              fi
              exit 22
            fi

            if [[ "$url" == https://raw.githubusercontent.com/*/infra/docker/docker-compose.selfhosted.yml ]]; then
              compose_text='services:
              api:
                image: ghcr.io/algenta/decision-engine/api:test
              worker:
                image: ghcr.io/algenta/decision-engine/worker:test'
              if [ -n "$output_path" ]; then
                printf '%s\\n' "$compose_text" > "$output_path"
              else
                printf '%s\\n' "$compose_text"
              fi
              exit 0
            fi

            if [ -n "${ALGENTA_TEST_COMPOSE_URL:-}" ] && [ "$url" = "${ALGENTA_TEST_COMPOSE_URL}" ]; then
              compose_text='services:
              api:
                image: algenta-selfhost/api:smoke
              worker:
                image: algenta-selfhost/worker:smoke'
              if [ -n "$output_path" ]; then
                printf '%s\\n' "$compose_text" > "$output_path"
              else
                printf '%s\\n' "$compose_text"
              fi
              exit 0
            fi

            echo "unexpected curl call: $url" >&2
            exit 1
            """
        ),
    )


def _run_install_script(
    tmp_path: Path,
    *,
    bootstrap_output: str = "",
    bootstrap_exit_code: int = 0,
    docker_info_fail: bool = False,
    health_fail: bool = False,
    release_ref: str | None = "test-release",
    image_tag: str | None = "git-test123",
    commit_sha: str | None = None,
    disable_compose_plugin: bool = False,
    compose_url: str | None = None,
    skip_image_pull: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_binaries(bin_dir)

    log_file = tmp_path / "calls.log"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "ALGENTA_DIR": str(tmp_path / "install"),
            "ALGENTA_DOCS_URL": "https://docs.algenta.test/self-hosting",
            "ALGENTA_HEALTH_WAIT_SECONDS": "1",
            "ALGENTA_TEST_STUB_LOG": str(log_file),
            "ALGENTA_TEST_BOOTSTRAP_OUTPUT": bootstrap_output,
            "ALGENTA_TEST_BOOTSTRAP_EXIT_CODE": str(bootstrap_exit_code),
            "ALGENTA_TEST_DOCKER_INFO_FAIL": "1" if docker_info_fail else "0",
            "ALGENTA_TEST_HEALTH_FAIL": "1" if health_fail else "0",
            "ALGENTA_TEST_COMMIT_SHA": commit_sha or "",
            "ALGENTA_TEST_DISABLE_DOCKER_COMPOSE_PLUGIN": "1" if disable_compose_plugin else "0",
            "ALGENTA_TEST_COMPOSE_URL": compose_url or "",
            "HOME": str(tmp_path / "home"),
        }
    )
    if release_ref is not None:
        env["ALGENTA_VERSION"] = release_ref
    if image_tag is not None:
        env["ALGENTA_IMAGE_TAG"] = image_tag
    if compose_url is not None:
        env["ALGENTA_COMPOSE_URL"] = compose_url
    if skip_image_pull:
        env["ALGENTA_SKIP_IMAGE_PULL"] = "1"
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_install_script_runs_service_first_happy_path_and_prints_key_once(tmp_path: Path) -> None:
    api_key = "de_test_abcdefghijklmnopqrstuvwxyz123456"
    engine_key = "de_live_enginecallbackkeyABCDEFGHIJKLMNOP"
    proc = _run_install_script(
        tmp_path,
        bootstrap_output="\n".join(
            [
                "ALGENTA_BOOTSTRAP_READY=1",
                "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                "BOOTSTRAP_USER_EMAIL=owner@selfhost.codna.ai",
                "BOOTSTRAP_USER_CREATED=1",
                "BOOTSTRAP_API_KEY_ID=11111111-2222-3333-4444-555555555555",
                "BOOTSTRAP_API_KEY_PREFIX=de_test_abcd",
                f"BOOTSTRAP_API_KEY={api_key}",
                f"BOOTSTRAP_ENGINE_API_KEY={engine_key}",
                "BOOTSTRAP_USER_PASSWORD=SecretPassword123",
            ]
        ),
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Codna is running." in proc.stdout
    assert "Authorization: Bearer ${ALGENTA_API_KEY}" in proc.stdout
    assert "Set temporarily:" in proc.stdout
    assert "export ALGENTA_API_KEY='<paste the bootstrap key above>'" in proc.stdout
    assert "Rotate the bootstrap key:" in proc.stdout
    assert "curl -X POST http://localhost:8000/v1/api-keys" in proc.stdout
    assert '"expires_at":"2028-05-19T00:00:00Z"' in proc.stdout
    assert (
        "The returned raw_key is shown once; store it with id, key_prefix, and expires_at before revoking the bootstrap key."
        in proc.stdout
    )
    assert "Bootstrap key id:" in proc.stdout
    assert "Bootstrap key prefix:" in proc.stdout
    assert "Replace it:" in proc.stdout
    assert "export ALGENTA_API_KEY='<paste the replacement key returned above>'" in proc.stdout
    assert "No SDK or Python install is required to use Codna." in proc.stdout
    assert proc.stdout.count(api_key) == 1
    assert "BOOTSTRAP_API_KEY=" not in proc.stdout
    assert "Next steps:" in proc.stdout
    assert "Rotate the bootstrap key with POST /v1/api-keys and a bounded expires_at" in proc.stdout

    install_dir = tmp_path / "install"
    env_text = (install_dir / ".env").read_text(encoding="utf-8")
    compose_text = (install_dir / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ALGENTA_IMAGE_TAG=git-test123" in env_text
    assert "DATABASE_URL_SYNC=postgresql://algenta:algenta_secret@postgres:5432/algenta" in env_text
    assert "RUNTIME_FALLBACK_MODE=allow" in env_text
    assert "ALGENTA_DEPLOYMENT_MODE=self_hosted" in env_text
    assert "ALGENTA_DISABLE_CLOUD=1" in env_text
    assert "ALGENTA_DISABLE_TELEMETRY=1" in env_text
    assert "ALGENTA_TELEMETRY_MODE=local_audit" in env_text
    assert "ALGENTA_METERING_MODE=local_audit" in env_text
    assert "ALGENTA_ALLOW_OUTBOUND_NETWORK=0" in env_text
    assert "ALGENTA_EGRESS_ALLOWLIST=minio:9000" in env_text
    assert "ALGENTA_API_PUBLIC_BASE_URL=http://localhost:8000" in env_text
    assert "ALGENTA_APP_BASE_URL=" in env_text
    assert "RESULT_STORAGE_ENABLED=true" in env_text
    assert "ghcr.io/algenta/decision-engine/api:test" in compose_text

    # ── Restart-durability fixes ────────────────────────────────────────────────
    # The engine-callback key is wired into .env (persists across restart) but never printed.
    assert f"ALGENTA_ENGINE_API_KEY={engine_key}" in env_text
    assert engine_key not in proc.stdout
    assert "Engine-callback key wired into .env" in proc.stdout
    # A stable 64-hex config-encryption key (KEK) is generated + persisted, not left to the operator.
    kek = next(
        line.split("=", 1)[1]
        for line in env_text.splitlines()
        if line.startswith("ALGENTA_CONFIG_ENCRYPTION_KEY=")
    )
    assert len(kek) == 64 and all(c in "0123456789abcdef" for c in kek)
    # A generated sidecar service token + enforced auth (no more open-by-default, shell-only token).
    agent_token = next(
        line.split("=", 1)[1]
        for line in env_text.splitlines()
        if line.startswith("AGENT_CORE_AUTH_TOKEN=")
    )
    assert len(agent_token) >= 24
    assert "AGENT_CORE_REQUIRE_AUTH=1" in env_text
    assert "ALGENTA_AGENT_CORE_URL=http://sidecar:8787" in env_text
    # The engine-callback key is only consumed when ALGENTA_ENGINE_URL is set (docker-network DNS).
    assert "ALGENTA_ENGINE_URL=http://api:8000" in env_text
    assert "ANTHROPIC_API_KEY=" in env_text


def test_install_script_fails_fast_when_docker_daemon_is_unreachable(tmp_path: Path) -> None:
    proc = _run_install_script(tmp_path, docker_info_fail=True)

    assert proc.returncode == 1
    assert "Docker daemon is not running or not reachable." in proc.stdout
    assert (
        "Start Docker Desktop, Colima, or your Docker daemon before running the installer."
        in proc.stdout
    )


def test_install_script_aborts_when_health_check_never_becomes_ready(tmp_path: Path) -> None:
    proc = _run_install_script(tmp_path, health_fail=True)

    assert proc.returncode == 1
    assert "Self-hosted install failed because the API did not become ready." in proc.stdout
    assert "Next steps:" not in proc.stdout

    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert (
        "docker compose exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head"
        not in log_text
    )
    assert "docker compose exec -T api python scripts/bootstrap_self_host.py" not in log_text


def test_install_script_aborts_when_bootstrap_does_not_return_an_api_key(tmp_path: Path) -> None:
    proc = _run_install_script(
        tmp_path,
        bootstrap_output="\n".join(
            [
                "ALGENTA_BOOTSTRAP_READY=1",
                "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                "BOOTSTRAP_USER_EMAIL=owner@selfhost.codna.ai",
            ]
        ),
    )

    assert proc.returncode == 1
    assert "Bootstrap completed without a printable API key." in proc.stdout
    assert "Self-hosted install failed during bootstrap initialization." in proc.stdout
    assert "Next steps:" not in proc.stdout


def test_install_script_fails_if_no_pinned_release_can_be_resolved(tmp_path: Path) -> None:
    proc = _run_install_script(
        tmp_path,
        release_ref=None,
        image_tag=None,
        commit_sha=None,
    )

    assert proc.returncode == 1
    assert "Could not resolve a pinned release ref from GitHub." in proc.stdout
    assert (
        "Set ALGENTA_VERSION and, if needed, ALGENTA_IMAGE_TAG explicitly before retrying."
        in proc.stdout
    )
    assert "Downloading Codna Decision Engine..." not in proc.stdout


def test_install_script_normalizes_git_sha_release_refs_to_pinned_image_tags(
    tmp_path: Path,
) -> None:
    proc = _run_install_script(
        tmp_path,
        bootstrap_output="\n".join(
            [
                "ALGENTA_BOOTSTRAP_READY=1",
                "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                "BOOTSTRAP_USER_EMAIL=owner@selfhost.codna.ai",
                "BOOTSTRAP_USER_CREATED=0",
                "BOOTSTRAP_API_KEY_ID=11111111-2222-3333-4444-555555555555",
                "BOOTSTRAP_API_KEY_PREFIX=de_test_abcd",
                "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456",
            ]
        ),
        release_ref="abcdef1234567890abcdef1234567890abcdef12",
        image_tag=None,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    env_text = (tmp_path / "install" / ".env").read_text(encoding="utf-8")
    assert "ALGENTA_IMAGE_TAG=git-abcdef1" in env_text


def test_install_script_falls_back_to_standalone_docker_compose_when_plugin_missing(
    tmp_path: Path,
) -> None:
    proc = _run_install_script(
        tmp_path,
        bootstrap_output="\n".join(
            [
                "ALGENTA_BOOTSTRAP_READY=1",
                "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                "BOOTSTRAP_USER_EMAIL=owner@selfhost.codna.ai",
                "BOOTSTRAP_USER_CREATED=0",
                "BOOTSTRAP_API_KEY_ID=11111111-2222-3333-4444-555555555555",
                "BOOTSTRAP_API_KEY_PREFIX=de_test_abcd",
                "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456",
            ]
        ),
        disable_compose_plugin=True,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Docker and Docker Compose found (docker-compose)" in proc.stdout
    assert "cd " in proc.stdout and "docker-compose ps" in proc.stdout
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "docker compose version" in log_text
    assert "docker-compose version" in log_text
    assert "docker-compose pull --quiet" in log_text


def test_install_script_supports_local_compose_bundle_override_and_skip_pull(
    tmp_path: Path,
) -> None:
    compose_url = "https://fixtures.algenta.test/docker-compose.selfhosted.yml"
    proc = _run_install_script(
        tmp_path,
        bootstrap_output="\n".join(
            [
                "ALGENTA_BOOTSTRAP_READY=1",
                "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                "BOOTSTRAP_USER_EMAIL=owner@selfhost.codna.ai",
                "BOOTSTRAP_USER_CREATED=0",
                "BOOTSTRAP_API_KEY_ID=11111111-2222-3333-4444-555555555555",
                "BOOTSTRAP_API_KEY_PREFIX=de_test_abcd",
                "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456",
            ]
        ),
        compose_url=compose_url,
        skip_image_pull=True,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "Skipping image pull because ALGENTA_SKIP_IMAGE_PULL=1" in proc.stdout
    compose_text = (tmp_path / "install" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "algenta-selfhost/api:smoke" in compose_text
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert compose_url in log_text
    assert "compose pull --quiet" not in log_text
