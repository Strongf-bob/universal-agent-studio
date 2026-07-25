from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "docker" / "compose.local.yml"
DEV_LOCAL = ROOT / "scripts" / "dev-local.mjs"
RESET_LOCAL = ROOT / "scripts" / "local-reset.mjs"


def _node() -> str:
    executable = shutil.which("node")
    assert executable is not None
    return executable


def test_compose_is_pinned_and_keeps_secrets_out_of_environment() -> None:
    document = COMPOSE.read_text(encoding="utf-8")

    assert (
        "postgres:18.4-alpine3.23@sha256:"
        "996d0920e4ff9df1fc19dacb904492f3c1ec0ec1cc338f0ad7123be7731c5f5e"
    ) in document
    assert (
        "temporalio/temporal:1.8.1@sha256:"
        "59561b9ef060eaeb1f46cb6a1842d6cbdd8a393eb3b6d315ecef5fe2f0b1d7a6"
    ) in document
    assert "uas_session_hash_key" in document
    assert "uas_execution_signing_key" in document
    assert "UAS_SESSION_HASH_KEY=" not in document
    assert "UAS_EXECUTION_SIGNING_KEY=" not in document
    assert "condition: service_completed_successfully" in document
    assert "healthcheck:" in document


def test_local_stack_contains_isolated_published_web() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    service = compose["services"]["published-web"]

    assert service["ports"] == ["127.0.0.1:${UAS_PUBLISHED_WEB_PORT:-3301}:3000"]
    assert "uas_session_hash_key" not in service.get("secrets", [])
    assert "uas_api_key_hash_key" not in service.get("secrets", [])
    assert service["environment"] == {
        "CONTROL_API_INTERNAL_URL": "http://control-api:8000"
    }


def test_compose_mounts_each_slice3_secret_only_where_needed() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = compose["services"]

    assert "uas_api_key_hash_key" in services["control-api"]["secrets"]
    assert "uas_public_capability_key" in services["control-api"]["secrets"]
    assert "uas_webhook_signing_key" in services["control-api"]["secrets"]
    assert "uas_webhook_signing_key" in services["runtime-worker"]["secrets"]
    assert "uas_session_hash_key" not in services["runtime-worker"]["secrets"]
    assert "uas_api_key_hash_key" not in services["runtime-worker"]["secrets"]
    assert "uas_public_capability_key" not in services["runtime-worker"]["secrets"]


def test_launcher_creates_distinct_owner_only_secret_files(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [_node(), str(DEV_LOCAL), "--prepare-only"],
        cwd=ROOT,
        env={**os.environ, "UAS_LOCAL_STATE_DIR": str(tmp_path)},
        check=True,
        capture_output=True,
        text=True,
    )
    session_key = tmp_path / "secrets" / "session-hash.key"
    signing_key = tmp_path / "secrets" / "execution-signing.key"
    api_key_hash_key = tmp_path / "secrets" / "api-key-hash.key"
    capability_key = tmp_path / "secrets" / "public-capability.key"
    webhook_key = tmp_path / "secrets" / "webhook-signing.key"
    marker = tmp_path / ".uas-local-state-owner"

    assert marker.read_text(encoding="utf-8") == f"{ROOT}\n"
    assert session_key.is_file()
    assert signing_key.is_file()
    generated = [
        session_key,
        signing_key,
        api_key_hash_key,
        capability_key,
        webhook_key,
    ]
    assert all(path.is_file() for path in generated)
    assert len({path.read_bytes() for path in generated}) == len(generated)
    assert stat.S_IMODE(session_key.stat().st_mode) == 0o600
    assert stat.S_IMODE(signing_key.stat().st_mode) == 0o600
    assert session_key.read_text().strip() not in result.stdout
    assert signing_key.read_text().strip() not in result.stdout
    assert all(path.read_text().strip() not in result.stdout for path in generated)


def test_launcher_reports_missing_docker_without_exposing_secrets(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [_node(), str(DEV_LOCAL), "--check"],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": str(tmp_path),
            "UAS_LOCAL_STATE_DIR": str(tmp_path / "state"),
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Docker" in result.stderr


def test_reset_requires_exact_confirmation(tmp_path: Path) -> None:
    state_directory = tmp_path / "state"
    environment = {
        **os.environ,
        "UAS_LOCAL_STATE_DIR": str(state_directory),
    }
    subprocess.run(
        [_node(), str(DEV_LOCAL), "--prepare-only"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    rejected = subprocess.run(
        [_node(), str(RESET_LOCAL), "--dry-run"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    accepted = subprocess.run(
        [
            _node(),
            str(RESET_LOCAL),
            "--dry-run",
            "--confirm",
            "RESET LOCAL DATA",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert rejected.returncode != 0
    assert accepted.returncode == 0
    assert "would remove" in accepted.stdout.lower()


def test_launcher_refuses_to_adopt_a_non_empty_unowned_directory(
    tmp_path: Path,
) -> None:
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    protected = unrelated / "keep.txt"
    protected.write_text("do not delete", encoding="utf-8")

    result = subprocess.run(
        [_node(), str(DEV_LOCAL), "--prepare-only"],
        cwd=ROOT,
        env={**os.environ, "UAS_LOCAL_STATE_DIR": str(unrelated)},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Refusing to adopt" in result.stderr
    assert protected.read_text(encoding="utf-8") == "do not delete"


def test_compose_config_is_valid_when_docker_is_available(
    tmp_path: Path,
) -> None:
    subprocess.run(
        [_node(), str(DEV_LOCAL), "--prepare-only"],
        cwd=ROOT,
        env={**os.environ, "UAS_LOCAL_STATE_DIR": str(tmp_path)},
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [_node(), str(DEV_LOCAL), "--check"],
        cwd=ROOT,
        env={**os.environ, "UAS_LOCAL_STATE_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
