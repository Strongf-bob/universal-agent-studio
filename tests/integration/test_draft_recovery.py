from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "docker" / "compose.local.yml"
BASE_URL = os.getenv("UAS_E2E_BASE_URL", "http://localhost:3000")


def _stack_is_available() -> bool:
    try:
        return httpx.get(f"{BASE_URL}/api/v1/bootstrap/status", timeout=1).is_success
    except httpx.HTTPError:
        return False


def test_web_restart_preserves_postgresql_draft_revision() -> None:
    if shutil.which("docker") is None or not _stack_is_available():
        pytest.skip("The complete local stack is not running")

    with httpx.Client(
        base_url=BASE_URL,
        headers={"Origin": BASE_URL},
        timeout=10,
    ) as client:
        login = client.post(
            "/api/v1/session",
            json={
                "login_name": "slice1-owner",
                "password": "slice1-e2e-secret-437",
            },
        )
        assert login.status_code == 201
        before = client.get("/api/v1/agents/calculator-agent/draft")
        assert before.status_code == 200
        revision = before.json()["revision"]
        digest = before.json()["digest"]

        subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(COMPOSE),
                "restart",
                "studio-web",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        for _ in range(40):
            try:
                ready = client.get("/en-US/login", timeout=2)
                if ready.is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            pytest.fail("studio-web did not become ready after restart")

        after = client.get("/api/v1/agents/calculator-agent/draft")
        assert after.status_code == 200
        assert after.json()["revision"] == revision
        assert after.json()["digest"] == digest
