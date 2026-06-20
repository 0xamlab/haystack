from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_SCRIPT = ROOT / "scripts" / "self_host_persistence_proof.sh"


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

            if [ "$1" = "build" ]; then
              exit 0
            fi

            if [ "$1" = "image" ] && [ "$2" = "prune" ] && [ "$3" = "-f" ]; then
              exit 0
            fi

            if [ "$1" = "volume" ] && [ "$2" = "create" ]; then
              exit 0
            fi

            if [ "$1" = "run" ]; then
              exit 0
            fi

            if [ "$1" = "compose" ]; then
              if [[ "$*" == *" up -d"* ]]; then
                exit 0
              fi
              if [[ "$*" == *" down -v --remove-orphans" ]]; then
                exit 0
              fi
              if [[ "$*" == *" down" ]]; then
                exit 0
              fi
              if [[ "$*" == *" exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head" ]]; then
                exit 0
              fi
              if [[ "$*" == *" exec -T api python scripts/bootstrap_self_host.py" ]]; then
                printf '%s\\n' "${ALGENTA_TEST_BOOTSTRAP_OUTPUT}"
                exit 0
              fi
              if [[ "$*" == *" exec -T postgres pg_isready -U algenta -d algenta" ]]; then
                exit 0
              fi
              if [[ "$*" == *" exec -T postgres pg_dump -U algenta algenta" ]]; then
                printf '%s\\n' "-- pg_dump stub --"
                exit 0
              fi
              if [[ "$*" == *" exec -T postgres psql -U algenta -d algenta" ]]; then
                cat >/dev/null
                exit 0
              fi
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

            if [[ "$*" == *" up -d"* ]]; then
              exit 0
            fi
            if [[ "$*" == *" down -v --remove-orphans" ]]; then
              exit 0
            fi
            if [[ "$*" == *" down" ]]; then
              exit 0
            fi
            if [[ "$*" == *" exec -T api python -m alembic -c apps/api_server/alembic.ini upgrade head" ]]; then
              exit 0
            fi
            if [[ "$*" == *" exec -T api python scripts/bootstrap_self_host.py" ]]; then
              printf '%s\\n' "${ALGENTA_TEST_BOOTSTRAP_OUTPUT}"
              exit 0
            fi
            if [[ "$*" == *" exec -T postgres pg_isready -U algenta -d algenta" ]]; then
              exit 0
            fi
            if [[ "$*" == *" exec -T postgres pg_dump -U algenta algenta" ]]; then
              printf '%s\\n' "-- pg_dump stub --"
              exit 0
            fi
            if [[ "$*" == *" exec -T postgres psql -U algenta -d algenta" ]]; then
              cat >/dev/null
              exit 0
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

            method="GET"
            url=""
            while [ "$#" -gt 0 ]; do
              case "$1" in
                -X)
                  method="$2"
                  shift 2
                  ;;
                -H|-d)
                  shift 2
                  ;;
                *)
                  url="$1"
                  shift
                  ;;
              esac
            done

            if [[ "$url" == http://localhost:*"/v1/health" ]]; then
              printf '%s\\n' '{"status":"ok"}'
              exit 0
            fi

            if [ "$method" = "DELETE" ] && [[ "$url" == http://localhost:*"/v1/api-keys/"* ]]; then
              exit 0
            fi

            if [[ "$url" == http://localhost:*"/minio/health/live" ]]; then
              printf '%s\\n' "OK"
              exit 0
            fi

            echo "unexpected curl call: $url" >&2
            exit 1
            """
        ),
    )
    _write_executable(
        bin_dir / "python3",
        textwrap.dedent(
            """\
            #!/bin/bash
            set -euo pipefail

            log_file="${ALGENTA_TEST_STUB_LOG:?}"
            printf 'python3 %s\\n' "$*" >> "$log_file"
            cat >/dev/null

            case "${ALGENTA_PERSISTENCE_ACTION:-}" in
              rotate)
                printf 'ROTATED_API_KEY=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY}"
                printf 'ROTATED_API_KEY_ID=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY_ID}"
                printf 'ROTATED_API_KEY_PREFIX=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY_PREFIX}"
                printf 'ROTATED_EXPIRES_AT=%s\\n' "${ALGENTA_TEST_ROTATED_EXPIRES_AT}"
                ;;
              seed)
                printf '%s\\n' "${ALGENTA_TEST_PERSISTENCE_SEED_OUTPUT}"
                ;;
              verify)
                stage="${ALGENTA_TEST_PERSISTENCE_VERIFY_STAGE:-verify}"
                printf 'STAGE=%s\\nDATASET_ID=dataset-selfhost-001\\nRUN_ID=11111111-1111-1111-1111-111111111111\\n' "$stage"
                ;;
              verify_revoked_key)
                ;;
              *)
                echo "unexpected ALGENTA_PERSISTENCE_ACTION=${ALGENTA_PERSISTENCE_ACTION:-}" >&2
                exit 1
                ;;
            esac
            """
        ),
    )


def _run_persistence_script(
    tmp_path: Path,
    *,
    docker_info_fail: bool = False,
    skip_build: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_binaries(bin_dir)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "ALGENTA_TEST_STUB_LOG": str(tmp_path / "calls.log"),
            "ALGENTA_TEST_DOCKER_INFO_FAIL": "1" if docker_info_fail else "0",
            "ALGENTA_SELF_HOST_PERSISTENCE_SKIP_BUILD": "1" if skip_build else "0",
            "ALGENTA_SELF_HOST_PERSISTENCE_PROJECT": "algenta-selfhost-persistence-test",
            "ALGENTA_SELF_HOST_PERSISTENCE_PORT": "18030",
            "ALGENTA_SELF_HOST_PERSISTENCE_KEEP_STACK": "1",
            "ALGENTA_TEST_BOOTSTRAP_OUTPUT": "\n".join(
                [
                    "ALGENTA_BOOTSTRAP_READY=1",
                    "BOOTSTRAP_ORG_SLUG=self-hosted-org",
                    "BOOTSTRAP_USER_EMAIL=owner@selfhost.algenta.ai",
                    "BOOTSTRAP_USER_CREATED=1",
                    "BOOTSTRAP_API_KEY_ID=bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
                    "BOOTSTRAP_API_KEY_PREFIX=de_test_stub",
                    "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456",
                    "BOOTSTRAP_USER_PASSWORD=SecretPassword123",
                ]
            ),
            "ALGENTA_TEST_ROTATED_API_KEY": "de_live_rotated_persistence_key_abcdefghijklmnopqrstuvwxyz",
            "ALGENTA_TEST_ROTATED_API_KEY_ID": "66666666-7777-8888-9999-000000000000",
            "ALGENTA_TEST_ROTATED_API_KEY_PREFIX": "de_live_pers",
            "ALGENTA_TEST_ROTATED_EXPIRES_AT": "2028-05-19T00:00:00Z",
            "ALGENTA_TEST_PERSISTENCE_SEED_OUTPUT": "\n".join(
                [
                    "ORG_ID=org-selfhost-001",
                    "DATASET_ID=dataset-selfhost-001",
                    "RUN_ID=11111111-1111-1111-1111-111111111111",
                ]
            ),
        }
    )
    return subprocess.run(
        ["bash", str(PERSISTENCE_SCRIPT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_self_host_persistence_proof_happy_path_verifies_restart_and_restore(
    tmp_path: Path,
) -> None:
    proc = _run_persistence_script(tmp_path)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "==> Resetting persistence stack" in proc.stdout
    assert "==> Pruning dangling Docker images" in proc.stdout
    assert "==> Building self-hosted persistence images" in proc.stdout
    assert "==> Rotating bootstrap key" in proc.stdout
    assert "==> Revoking bootstrap key" in proc.stdout
    assert "==> Verifying revoked bootstrap key is rejected" in proc.stdout
    assert "==> Seeding persistent state" in proc.stdout
    assert "==> Restarting stack without removing volumes" in proc.stdout
    assert "==> Verifying persistence after restart" in proc.stdout
    assert "==> Backing up PostgreSQL" in proc.stdout
    assert "==> Backing up object storage" in proc.stdout
    assert "==> Backing up local source registry" in proc.stdout
    assert "==> Verifying persistence after restore" in proc.stdout
    assert "==> Self-hosted persistence proof passed" in proc.stdout
    assert "BOOTSTRAP_API_KEY=<redacted>" in proc.stdout
    assert "BOOTSTRAP_USER_PASSWORD=<redacted>" in proc.stdout
    assert "BOOTSTRAP_API_KEY=de_test_abcdefghijklmnopqrstuvwxyz123456" not in proc.stdout
    assert "SecretPassword123" not in proc.stdout
    assert "API_KEY=de_live_rotated_persistence_key_abcdefghijklmnopqrstuvwxyz" in proc.stdout
    assert "API_KEY_ID=66666666-7777-8888-9999-000000000000" in proc.stdout
    assert "API_KEY_PREFIX=de_live_pers" in proc.stdout
    assert "API_KEY_EXPIRES_AT=2028-05-19T00:00:00Z" in proc.stdout
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "docker image prune -f" in log_text
    assert "docker build -f" in log_text
    assert (
        "docker run --rm --entrypoint /bin/sh --network algenta-selfhost-persistence-test_default minio/mc:latest -c"
        in log_text
    )
    assert "docker run --rm -v algenta-selfhost-persistence-test_minio_data:/from" in log_text
    assert "docker run --rm -v algenta-selfhost-persistence-test_sources_data:/from" in log_text
    assert (
        "docker volume create --label com.docker.compose.project=algenta-selfhost-persistence-test --label com.docker.compose.volume=minio_data algenta-selfhost-persistence-test_minio_data"
        in log_text
    )
    assert (
        "docker volume create --label com.docker.compose.project=algenta-selfhost-persistence-test --label com.docker.compose.volume=sources_data algenta-selfhost-persistence-test_sources_data"
        in log_text
    )
    assert "docker compose --project-name algenta-selfhost-persistence-test -f" in log_text
    assert (
        "curl -sf -X DELETE http://localhost:18030/v1/api-keys/bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
        in log_text
    )
    assert "exec -T postgres pg_dump -U algenta algenta" in log_text
    assert "exec -T postgres psql -U algenta -d algenta" in log_text


def test_self_host_persistence_proof_fails_fast_when_docker_daemon_is_unreachable(
    tmp_path: Path,
) -> None:
    proc = _run_persistence_script(tmp_path, docker_info_fail=True)

    assert proc.returncode == 1
    assert "Docker daemon is not running or not reachable." in proc.stderr
    assert (
        "Start Docker Desktop, Colima, or your Docker daemon before running the self-host persistence proof."
        in proc.stderr
    )


def test_self_host_persistence_proof_can_reuse_existing_images(tmp_path: Path) -> None:
    proc = _run_persistence_script(tmp_path, skip_build=True)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "==> Reusing existing self-hosted release images" in proc.stdout
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "docker build -f" not in log_text
