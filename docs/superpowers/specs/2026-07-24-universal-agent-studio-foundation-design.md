# Universal Agent Studio foundation design

**Status:** Proposed for owner review

**Date:** 2026-07-24

**Scope:** Foundation and the contract for the first executable slice

## Problem

Universal Agent Studio must expose one agent as a simple configuration, visual graph, developer specification, published application and observable runtime. Starting from UI scaffolding would risk creating a canvas-specific model that later conflicts with execution, versioning and security.

## Decision

Build a local-first modular monolith control plane with isolated runtime/research/sandbox workers. Define AgentSpec and run contracts before application scaffolding. Use adapters for durable execution, models, tools, storage and canvas rendering.

The first executable slice proves the complete path:

```text
immutable AgentSpec
→ Web/API request
→ durable runtime
→ model decision
→ safe tool
→ structured result
→ streamed events
→ persisted trace
```

It deliberately excludes editable canvas, RAG, code nodes, AI Builder and autoresearch.

## Architecture

- `apps/studio-web`: authenticated builder/operator surface.
- `apps/published-web`: least-privilege end-user surface.
- `apps/control-api`: modular control plane.
- `workers/runtime`: AgentSpec interpreter hosted by Temporal activities/workflows.
- `workers/researcher`: later candidate-generation boundary.
- `workers/sandbox`: later isolated code-execution boundary.
- `contracts`: canonical schemas, examples and conformance tests.
- language-specific libraries contain ports and generated clients, not duplicate schemas.

## Core semantics

- Draft is mutable; published version and run snapshot are immutable.
- Canonical serialization produces a stable digest.
- Model profiles resolve through policy-aware adapters; actual resolution is recorded per run.
- Run events use at-least-once delivery with stable IDs and monotonic sequence.
- Side effects require idempotency and may require approval.
- Capability pack internals are viewed by reference and edited only through fork.
- Reproducibility means exact configuration/provenance, not identical LLM text.

## Slice 1 UX

The local user can open a small RU/EN runner, submit structured input, watch progress, view the result, switch to a read-only graph and inspect node-level trace. The same run can be created and inspected through REST API. This UI is intentionally thin but real; it is not a disconnected mock.

## Error handling

- Contract failures return structured field/node paths.
- Adapter failures map to stable error codes while preserving redacted diagnostics.
- Retryability is explicit.
- Stream reconnect resumes from sequence.
- Terminal run state is persisted before completion is reported.
- Policy incompatibility fails closed.

## Verification

- schema and cross-language round-trip tests;
- deterministic runtime unit tests;
- API/runtime/PostgreSQL/Temporal integration test;
- Web and API E2E against the same AgentVersion;
- duplicate-event/idempotency test;
- secret leakage and trace-redaction tests;
- RU/EN and keyboard smoke tests;
- optional external-provider smoke test excluded from CI.

## Alternatives considered

### Canvas first

Fast visual progress, but it risks a second data model and postpones runtime semantics. Rejected.

### RAG first

Useful demo, but it commits early to ingestion, embeddings and vector storage. Deferred until the executable spine is stable.

### Custom durable engine

Reduces local dependencies but transfers recovery, replay, timers and approval correctness to the project. Rejected for the initial implementation; Temporal remains behind a replaceable port.

## Approval gate

After owner approval, prepare the implementation plan for Slice 0 contracts and Slice 1. No production implementation begins before this review.
