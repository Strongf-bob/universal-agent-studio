#!/usr/bin/env python3
"""Generate deterministic Python models and the bundled contract schema."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "0.1.0"
SCHEMA_DIR = ROOT / "contracts" / "schemas" / f"v{SCHEMA_VERSION}"
PYTHON_PACKAGE = (
    ROOT
    / "libs"
    / "python"
    / "agent_kernel"
    / "src"
    / "universal_agent_kernel"
    / "contracts"
)
BUNDLE_TARGET = PYTHON_PACKAGE / "schemas" / "bundle.schema.json"
PYTHON_TARGET = PYTHON_PACKAGE / "generated.py"
HEADER = (
    f"# Generated from Universal Agent Studio JSON Schema v{SCHEMA_VERSION}.\n"
    "# Do not edit manually; run `pnpm generate:contracts`.\n"
)


def _load_schemas() -> dict[str, dict[str, Any]]:
    return {
        path.name: cast(
            dict[str, Any],
            json.loads(path.read_text(encoding="utf-8")),
        )
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }


def _rewrite_refs(value: Any, current_definition: str, names: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_rewrite_refs(item, current_definition, names) for item in value]
    if not isinstance(value, dict):
        return value

    rewritten: dict[str, Any] = {}
    for key, child in value.items():
        if key == "$ref" and isinstance(child, str):
            target, marker, fragment = child.partition("#")
            definition = names[target] if target else current_definition
            suffix = f"/{fragment.lstrip('/')}" if marker and fragment else ""
            rewritten[key] = f"#/$defs/{definition}{suffix}"
        elif key not in {"$id", "$schema"}:
            rewritten[key] = _rewrite_refs(child, current_definition, names)
    return rewritten


def build_bundle() -> str:
    schemas = _load_schemas()
    names = {filename: schema["title"] for filename, schema in schemas.items()}
    definitions = {
        names[filename]: _rewrite_refs(schema, names[filename], names)
        for filename, schema in schemas.items()
    }
    properties = {
        filename.removesuffix(".schema.json").replace("-", "_"): {
            "$ref": f"#/$defs/{names[filename]}"
        }
        for filename in schemas
        if filename != "common.schema.json"
    }
    bundle = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://schemas.universal-agent.studio/"
            f"v{SCHEMA_VERSION}/contract-bundle.schema.json"
        ),
        "title": "ContractBundle",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "$defs": definitions,
    }
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def generate_python(bundle: str) -> str:
    with tempfile.TemporaryDirectory(prefix="uas-contracts-") as directory:
        temporary = Path(directory)
        source = temporary / "bundle.schema.json"
        output = temporary / "generated.py"
        source.write_text(bundle, encoding="utf-8", newline="\n")
        subprocess.run(
            [
                "datamodel-codegen",
                "--input",
                str(source),
                "--input-file-type",
                "jsonschema",
                "--output",
                str(output),
                "--output-model-type",
                "pydantic_v2.BaseModel",
                "--target-python-version",
                "3.12",
                "--use-standard-collections",
                "--use-union-operator",
                "--field-constraints",
                "--formatters",
                "builtin",
                "--disable-timestamp",
                "--use-title-as-name",
                "--custom-file-header",
                HEADER.rstrip(),
                "--custom-file-header-mode",
                "replace",
            ],
            cwd=ROOT,
            check=True,
        )
        return output.read_text(encoding="utf-8").replace("\r\n", "\n")


def _sync(target: Path, content: str, *, check: bool) -> bool:
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current == content:
        return True
    if check:
        print(f"generated contract drift: {target.relative_to(ROOT)}")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()

    bundle = build_bundle()
    generated = generate_python(bundle)
    in_sync = all(
        (
            _sync(BUNDLE_TARGET, bundle, check=arguments.check),
            _sync(PYTHON_TARGET, generated, check=arguments.check),
        )
    )
    return 0 if in_sync else 1


if __name__ == "__main__":
    raise SystemExit(main())
