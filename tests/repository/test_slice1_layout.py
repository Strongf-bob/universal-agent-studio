from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    "relative_path",
    [
        "libs/python/agent_kernel/pyproject.toml",
        "libs/python/agent_kernel/src/universal_agent_kernel/__init__.py",
        "libs/python/platform_store/pyproject.toml",
        "libs/python/platform_store/src/universal_agent_platform_store/__init__.py",
        "apps/control-api/pyproject.toml",
        "apps/control-api/src/universal_agent_studio_api/__init__.py",
        "workers/runtime/pyproject.toml",
        "workers/runtime/src/universal_agent_studio_runtime/__init__.py",
        "apps/studio-web/package.json",
        "apps/studio-web/tsconfig.json",
        "apps/studio-web/next.config.ts",
        "apps/studio-web/eslint.config.mjs",
    ],
)
def test_slice1_workspace_path_exists(relative_path: str) -> None:
    assert (ROOT / relative_path).is_file()


def test_root_scripts_expose_slice1_quality_commands() -> None:
    package_json = (ROOT / "package.json").read_text(encoding="utf-8")

    for script_name in (
        '"dev:local"',
        '"local:down"',
        '"test:python"',
        '"test:web"',
        '"test:e2e"',
        '"check"',
    ):
        assert script_name in package_json
