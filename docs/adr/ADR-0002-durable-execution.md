# ADR-0002: Durable execution

**Status:** Accepted

**Date:** 2026-07-24

## Context

Runs need retries, timers, cancellation, pause/resume, approvals and recovery after process failure. Implementing these guarantees inside the graph interpreter would duplicate a distributed workflow engine.

## Decision

Use Temporal as the first durable execution implementation behind a product-owned `DurableExecutionPort`.

AgentSpec does not contain Temporal vocabulary. The runtime translates stable product commands and events to workflows/activities. Temporal workflow IDs, history and retry configuration remain infrastructure metadata.

Local Preview uses the Temporal development server. Private-server deployment self-hosts Temporal. A future managed service may replace it without changing AgentSpec.

## Consequences

Local setup includes another service and deterministic workflow constraints. In return, the project does not own crash recovery, durable timers and workflow replay primitives.

## Sources

- https://docs.temporal.io/
- https://github.com/temporalio/temporal
- https://github.com/temporalio/sdk-python
