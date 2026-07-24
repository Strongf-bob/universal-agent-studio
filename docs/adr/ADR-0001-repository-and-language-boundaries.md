# ADR-0001: Repository and language boundaries

**Status:** Accepted

**Date:** 2026-07-24

## Context

The product needs a TypeScript web experience, a Python agent/runtime ecosystem and one cross-language contract.

## Decision

Use one monorepo:

- Next.js/React/TypeScript for Studio and Published Web;
- FastAPI/Python for control API and workers;
- JSON Schema 2020-12 in `/contracts` as the canonical contract source;
- generated TypeScript and Pydantic types;
- `pnpm` for JavaScript and `uv` for Python;
- root task commands that orchestrate both ecosystems without hiding their native tooling.

Shared product behavior belongs in contracts or explicitly owned libraries. Web packages may not import worker internals; workers may not import frontend types.

## Consequences

Cross-language conformance tests are mandatory. The monorepo simplifies atomic contract changes but requires disciplined generated-code checks.
