# Contributing

Universal Agent Studio is in Foundation. Discuss contract or architecture changes before implementation.

## Before changing code

1. Read `AGENTS.md`, `ROADMAP.md` and the relevant product/security documents.
2. Identify the active slice and its acceptance contract.
3. Add or update an ADR when a boundary, dependency or durable behavior changes.
4. Change canonical JSON Schema before generated language types.
5. Add provenance and license metadata before introducing a dependency or asset.

## Pull requests

- keep one coherent outcome per pull request;
- describe the affected slice and architectural invariants;
- include relevant contract, unit, integration, E2E, security, localization or eval evidence;
- do not commit secrets, local traces or private datasets;
- do not publish autoresearch candidates automatically.

The exact developer setup will be added with Slice 1 scaffolding.
