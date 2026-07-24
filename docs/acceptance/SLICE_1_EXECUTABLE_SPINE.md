# Slice 1 acceptance contract: Local executable spine

## Status and purpose

Status: **approved implementation contract**.

Slice 1 proves one complete path from an immutable agent version to a
redacted trace. It is not an editor or a general workflow engine. The
deterministic scenario below is the release gate for the slice.

## Required local environment

- Docker Desktop or a compatible Docker Engine with Compose v2;
- Node.js 26 and pnpm 11.7.0;
- Python 3.14 and uv 0.11.32;
- no external model credential for the deterministic acceptance run.

The implementation must provide one root command:

```bash
pnpm dev:local
```

That command must start the Studio Web app, Control API, Runtime worker,
PostgreSQL and Temporal, wait for readiness, and print the local Web and API
addresses. A clean checkout must require no manual database edits.

## Golden inputs

- Agent definition:
  `contracts/examples/v0.1.0/valid/agent.calculator.ru-en.json`
- API input:
  `contracts/examples/v0.1.0/valid/run.request.json`
- Expected trace shape:
  `contracts/examples/v0.1.0/valid/run.trace.completed.json`

The imported definition becomes an immutable `AgentVersion`. Its canonical
serialization digest is stored with the version and copied into every run
snapshot. Reimporting identical canonical content must reuse the digest
without rewriting a published version.

The fixture input is:

```json
{
  "question": "Сколько будет 19 × 23?"
}
```

The final structured output is:

```json
{
  "value": 437
}
```

It must validate against this exact interface fragment:

```json
{
  "type": "object",
  "required": ["value"],
  "properties": {
    "value": {
      "type": "number"
    }
  },
  "additionalProperties": false
}
```

## Required user journey

1. The local owner opens setup, chooses `ru-RU` or `en-US`, and completes
   local single-workspace initialization.
2. The owner imports the golden AgentSpec, promotes it as the locally active
   immutable version, and sees its validation status and digest.
3. The owner opens the runner, submits the fixture input, and receives a
   `run_id` immediately.
4. The run page streams structured progress and survives one browser refresh.
5. The deterministic fake model requests the first-party calculator tool.
6. The page displays the structured result and a read-only graph.
7. Selecting a node opens its input, output, timing, attempt and provenance.
8. The owner switches locale; user-facing labels change, while identifiers,
   stored events and semantics remain unchanged.

## Required API journey

The first implementation may refine resource names only through an ADR, but
must expose these behaviors:

```text
POST /api/v1/agent-versions/import
POST /api/v1/runs
GET  /api/v1/runs/{run_id}
GET  /api/v1/runs/{run_id}/events
GET  /api/v1/runs/{run_id}/trace
```

`POST /api/v1/runs` accepts the canonical `RunRequest`, including an
idempotency key. Repeating the same request with the same key returns the
original `run_id`. Reusing the key with a different canonical body returns
HTTP 409 and a valid `ErrorEnvelope`.

The event endpoint uses Server-Sent Events. Every SSE `id` equals the
`RunEvent.sequence`. On reconnect the browser sends `Last-Event-ID`; the
server resumes from the last acknowledged sequence. At-least-once delivery is
allowed, so clients deduplicate by `event_id`.

## Deterministic event and result expectations

The observable event types appear in this order:

```text
run.started
node.started
model.requested
model.completed
tool.requested
tool.completed
node.completed
run.completed
```

Sequences are strictly increasing within the persisted trace. Causation
identifiers reference an earlier event. A terminal run has exactly one
terminal event. The result validates against the AgentSpec output interface,
and the persisted trace validates against the current `RunTrace` schema and
semantic invariants.

CI uses only the deterministic fake model and calculator. A separate,
explicitly enabled OpenAI-compatible BYOK smoke test may verify the provider
port, but is never a required pull-request check and never records prompts,
responses or credentials as repository fixtures.

## Security acceptance

- Secret values exist only behind a `CredentialReference`.
- AgentSpec, API responses, RunEvents, RunTrace, logs, browser storage and
  browser bundles contain no credential values.
- All browser and API inputs have schema and size validation.
- The calculator is a first-party, side-effect-free tool with a typed
  manifest; arbitrary HTTP and code execution are unavailable.
- Internal execution binds the `run_id`, immutable version digest,
  workspace identity and idempotency key.
- Provider errors are converted to `ErrorEnvelope`; raw provider bodies are
  not returned to the browser.
- A clean deletion test removes the local workspace data without touching
  source fixtures or repository files.

## Failure and recovery acceptance

- Invalid AgentSpec import is rejected with stable field and node locations.
- Cancelling a queued or running execution creates a terminal cancellation
  event and leaves a readable partial trace.
- Restarting the Web process does not lose a run or its persisted events.
- Restarting the worker during the deterministic tool call resumes through
  the durable execution port without a second logical tool result.
- A browser reconnect may receive a duplicate event but never a missing
  terminal result after retry.

## Explicit exclusions

Slice 1 does not include editable canvas, draft authoring, RAG, arbitrary HTTP
tools, code nodes, MCP, publishing to the public internet, multi-tenant
administration, AI Builder, eval campaigns or autoresearch.

## Definition of done

- `pnpm dev:local` completes the Web and API journeys from a clean checkout.
- The deterministic E2E suite runs without external network access.
- Python and TypeScript validate the same stored AgentSpec, request, events
  and trace.
- RU/EN and keyboard-only checks pass for setup, runner, progress, result and
  trace inspection.
- Threat-model controls assigned to Slice 1 have automated or documented
  manual evidence.
- Dependency registry, operator instructions and README match the shipped
  implementation.
