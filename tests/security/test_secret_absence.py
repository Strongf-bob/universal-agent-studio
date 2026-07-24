from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "docker" / "compose.local.yml"
SECRETS = ROOT / ".local" / "secrets"


def _docker_compose(*arguments: str) -> str:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    completed = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout + completed.stderr


def test_generated_secrets_are_absent_from_compose_logs_and_browser_bundle() -> None:
    secret_files = sorted(SECRETS.glob("*"))
    if not secret_files:
        pytest.skip("Local stack secrets have not been generated")
    secret_values = [path.read_text(encoding="utf-8").strip() for path in secret_files]
    assert all(len(value) >= 32 for value in secret_values)

    observed = _docker_compose("config") + _docker_compose("logs", "--no-color")
    static_root = ROOT / "apps" / "studio-web" / ".next" / "static"
    if static_root.exists():
        observed += "".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in static_root.rglob("*")
            if path.is_file()
        )

    for secret in secret_values:
        assert secret not in observed
