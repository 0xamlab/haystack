from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_PROOF_SCRIPT = ROOT / "scripts" / "self_host_install_proof.sh"


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
              exit 0
            fi

            if [ "$1" = "build" ]; then
              exit 0
            fi

            if [ "$1" = "image" ] && [ "$2" = "prune" ] && [ "$3" = "-f" ]; then
              exit 0
            fi

            if [ "$1" = "compose" ] && [[ "$*" == *" down -v --remove-orphans" ]]; then
              exit 0
            fi

            echo "unexpected docker call: $*" >&2
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

            if [ "$method" = "POST" ] && [[ "$url" == http://localhost:*"/v1/simulate" ]]; then
              printf '%s\\n' '{"status":"completed","recommended_action":"proceed"}'
              exit 0
            fi

            echo "unexpected curl call: $method $url" >&2
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

            if [ "${ALGENTA_INSTALL_PROOF_ACTION:-}" = "rotate_key" ]; then
              cat >/dev/null
              printf 'ROTATED_API_KEY=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY}"
              printf 'ROTATED_API_KEY_ID=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY_ID}"
              printf 'ROTATED_API_KEY_PREFIX=%s\\n' "${ALGENTA_TEST_ROTATED_API_KEY_PREFIX}"
              printf 'ROTATED_EXPIRES_AT=%s\\n' "${ALGENTA_TEST_ROTATED_EXPIRES_AT}"
              exit 0
            fi

            if [ "${ALGENTA_INSTALL_PROOF_ACTION:-}" = "verify_revoked_key" ]; then
              cat >/dev/null
              exit 0
            fi

            if [ "$#" -ge 1 ] && [[ "$1" == *"self_host_endpoint_matrix.py" ]]; then
              printf '%s\\n' "${ALGENTA_TEST_ENDPOINT_MATRIX_OUTPUT}"
              exit 0
            fi

            if [ "$#" -ge 1 ] && [ "$1" = "-" ]; then
              cat >/dev/null
              printf 'API_KEY=%s\\n' "${ALGENTA_TEST_API_KEY:-de_test_stub_key}"
              printf 'BOOTSTRAP_KEY_ID=%s\\n' "${ALGENTA_TEST_BOOTSTRAP_KEY_ID:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
              printf 'BOOTSTRAP_EMAIL=%s\\n' "${ALGENTA_TEST_BOOTSTRAP_EMAIL:-owner@selfhost.algenta.ai}"
              printf 'BOOTSTRAP_PASSWORD=%s\\n' "${ALGENTA_TEST_BOOTSTRAP_PASSWORD:-stub-password-123}"
              exit 0
            fi

            cat >/dev/null
            printf '%s\\n' "${ALGENTA_TEST_ASYNC_JOB_OUTPUT}"
            """
        ),
    )


def _make_fake_installer(path: Path) -> None:
    _write_executable(
        path,
        textwrap.dedent(
            """\
            #!/bin/bash
            set -euo pipefail

            install_dir="${ALGENTA_DIR:?}"
            mkdir -p "$install_dir"
            printf 'services:\\n  api:\\n    image: algenta-selfhost/api:smoke\\n' > "$install_dir/docker-compose.yml"
            printf 'API_PORT=%s\\n' "${ALGENTA_API_PORT:-18020}" > "$install_dir/.env"
            printf '%s\\n' "Algenta is running."
            printf '%s\\n' "API Key: ${ALGENTA_TEST_API_KEY:-de_test_stub_key}"
            printf '%s\\n' "Bootstrap key id: ${ALGENTA_TEST_BOOTSTRAP_KEY_ID:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
            printf '%s\\n' "Bootstrap key prefix: ${ALGENTA_TEST_BOOTSTRAP_KEY_PREFIX:-de_test_stub}"
            printf '%s\\n' "Bootstrap user: ${ALGENTA_TEST_BOOTSTRAP_EMAIL:-owner@selfhost.algenta.ai}"
            printf '%s\\n' "Bootstrap password: ${ALGENTA_TEST_BOOTSTRAP_PASSWORD:-stub-password-123}"
            printf '%s\\n' "curl -X POST http://localhost:${ALGENTA_API_PORT:-18020}/v1/api-keys"
            printf '%s\\n' '{"label":"mission-runtime","expires_at":"2028-05-19T00:00:00Z"}'
            printf '%s\\n' "The returned raw_key is shown once; store it with id, key_prefix, and expires_at before revoking the bootstrap key."
            """
        ),
    )


def _run_install_proof_script(
    tmp_path: Path,
    *,
    docker_info_fail: bool = False,
    skip_build: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub_binaries(bin_dir)
    fake_installer = tmp_path / "fake_installer.sh"
    _make_fake_installer(fake_installer)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "ALGENTA_TEST_STUB_LOG": str(tmp_path / "calls.log"),
            "ALGENTA_TEST_DOCKER_INFO_FAIL": "1" if docker_info_fail else "0",
            "ALGENTA_SELF_HOST_INSTALLER": str(fake_installer),
            "ALGENTA_SELF_HOST_INSTALL_PROOF_SKIP_BUILD": "1" if skip_build else "0",
            "ALGENTA_SELF_HOST_INSTALL_PROOF_KEEP_INSTALL": "0",
            "ALGENTA_TEST_API_KEY": "de_test_abcdefghijklmnopqrstuvwxyz123456",
            "ALGENTA_TEST_BOOTSTRAP_KEY_ID": "bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
            "ALGENTA_TEST_BOOTSTRAP_KEY_PREFIX": "de_test_stub",
            "ALGENTA_TEST_ROTATED_API_KEY": "de_live_rotated_install_proof_key_abcdefghijklmnopqrstuvwxyz",
            "ALGENTA_TEST_ROTATED_API_KEY_ID": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "ALGENTA_TEST_ROTATED_API_KEY_PREFIX": "de_live_inst",
            "ALGENTA_TEST_ROTATED_EXPIRES_AT": "2028-05-19T00:00:00Z",
            "ALGENTA_TEST_BOOTSTRAP_EMAIL": "owner@selfhost.algenta.ai",
            "ALGENTA_TEST_BOOTSTRAP_PASSWORD": "stub-password-123",
            "ALGENTA_TEST_ASYNC_JOB_OUTPUT": "\n".join(
                [
                    "{",
                    '  "submit_status": 202,',
                    '  "submit_body": {',
                    '    "job_id": "11111111-1111-1111-1111-111111111111",',
                    '    "status": "queued"',
                    "  }",
                    "}",
                    "{",
                    '  "final_poll_status": 200,',
                    '  "final_poll_body": {',
                    '    "job_id": "11111111-1111-1111-1111-111111111111",',
                    '    "status": "completed"',
                    "  }",
                    "}",
                    "{",
                    '  "result_status": 200,',
                    '  "result_body": {',
                    '    "status": "completed",',
                    '    "result": {',
                    '      "status": "completed"',
                    "    }",
                    "  }",
                    "}",
                ]
            ),
            "ALGENTA_TEST_ENDPOINT_MATRIX_OUTPUT": '{"total": 5, "passed": 5, "failed": 0, "skipped": 0, "checks": []}',
        }
    )
    return subprocess.run(
        ["bash", str(INSTALL_PROOF_SCRIPT)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_self_host_install_proof_script_happy_path_runs_fresh_install_validation(
    tmp_path: Path,
) -> None:
    proc = _run_install_proof_script(tmp_path)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "==> Resetting installer proof stack" in proc.stdout
    assert "==> Pruning dangling Docker images" in proc.stdout
    assert "==> Building self-hosted release images" in proc.stdout
    assert "==> Running fresh installer proof" in proc.stdout
    assert "==> Verifying bootstrap rotation guidance" in proc.stdout
    assert "==> Rotating bootstrap key" in proc.stdout
    assert "==> Revoking bootstrap key" in proc.stdout
    assert "==> Verifying revoked bootstrap key is rejected" in proc.stdout
    assert "==> Verifying health" in proc.stdout
    assert "==> Verifying first decision" in proc.stdout
    assert "==> Verifying async job lifecycle" in proc.stdout
    assert "==> Verifying endpoint matrix" in proc.stdout
    assert "==> Self-host install proof passed" in proc.stdout
    assert "API_KEY_ID=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in proc.stdout
    assert "API_KEY_PREFIX=de_live_inst" in proc.stdout
    assert "API_KEY_EXPIRES_AT=2028-05-19T00:00:00Z" in proc.stdout
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "docker image prune -f" in log_text
    assert "docker build -f" in log_text
    assert "docker compose version" in log_text
    assert "docker compose --project-name algenta-install-proof -f" in log_text
    assert "down -v --remove-orphans" in log_text
    assert "python3 " in log_text
    assert (
        "DELETE http://localhost:18020/v1/api-keys/bbbbbbbb-cccc-dddd-eeee-ffffffffffff" in log_text
    )
    assert "--api-key de_live_rotated_install_proof_key_abcdefghijklmnopqrstuvwxyz" in log_text


def test_self_host_install_proof_script_fails_fast_when_docker_daemon_is_unreachable(
    tmp_path: Path,
) -> None:
    proc = _run_install_proof_script(tmp_path, docker_info_fail=True)

    assert proc.returncode == 1
    assert "Docker daemon is not running or not reachable." in proc.stderr
    assert (
        "Start Docker Desktop, Colima, or your Docker daemon before running the self-host install proof."
        in proc.stderr
    )


def test_self_host_install_proof_script_can_reuse_existing_images(tmp_path: Path) -> None:
    proc = _run_install_proof_script(tmp_path, skip_build=True)

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "==> Reusing existing self-hosted release images" in proc.stdout
    log_text = (tmp_path / "calls.log").read_text(encoding="utf-8")
    assert "docker build -f" not in log_text
