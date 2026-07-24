# Slice 1 Local Executable Spine — Design Specification

**Status:** Approved

**Date:** 2026-07-24

**Scope:** Slice 1 only

## 1. Outcome

Slice 1 delivers the first real Universal Agent Studio execution path:

1. a local owner bootstraps a private workspace;
2. the owner imports the golden AgentSpec;
3. the control plane validates and activates an immutable AgentVersion;
4. Web or API creates an idempotent run;
5. a Temporal workflow drives the product-owned Agent Kernel;
6. the deterministic model requests the built-in calculator;
7. the runtime persists redacted RunEvents and RunTrace;
8. the Web app resumes the event stream after refresh and presents the
   structured result, read-only flow and node trace in Russian or English.

The slice is complete only when the scenario runs from a clean checkout with
`pnpm dev:local`, deterministic E2E requires no external model network, and
worker restart, cancellation, idempotency, reconnect and deletion behavior
have evidence.

## 2. Chosen architecture

Use a modular control plane and a separate runtime worker:

```text
Browser
  │
  ▼
Next.js Studio ───── same-origin /api proxy ─────► FastAPI Control API
                                                        │
                             ┌──────────────────────────┼──────────────┐
                             ▼                          ▼              ▼
                         PostgreSQL              DurableExecutionPort  Session/Auth
                                                        │
                                                        ▼
                                                 Temporal Adapter
                                                        │
                                                        ▼
                                                Temporal Runtime Worker
                                                        │
                                  ┌─────────────────────┼─────────────────────┐
                                  ▼                     ▼                     ▼
                            Agent Kernel         ModelGatewayPort       ToolGatewayPort
                                                       │                     │
                                                       ▼                     ▼
                                           Deterministic/OpenAI       Built-in calculator
                                             compatible adapter
```

This is not an in-process prototype: the API never executes a run. It is also
not an early microservice fleet: one FastAPI control-plane application owns
the public API and one Python worker owns execution.

### Rejected alternatives

1. **FastAPI background tasks or an in-memory queue.** Simpler initially, but
   it cannot meet durable restart, cancellation and replay requirements.
2. **Separate version, run, event and auth services.** It improves independent
   scaling before there is load evidence while multiplying local and
   transactional complexity.
3. **A Next.js-only backend.** It would contradict the accepted Python runtime
   boundary and weaken access to the agent and Temporal Python ecosystems.

## 3. Growth path

The design is deliberately expandable to the planned platform:

- FastAPI modules depend on domain interfaces, so a module can later move to a
  service without changing public contracts.
- Temporal is behind `DurableExecutionPort`; its workflow identifiers and
  retry vocabulary never enter AgentSpec.
- Provider SDK objects remain inside model adapters.
- React and React Flow consume first-party view models, not runtime objects.
- every protected row carries `workspace_id` and `project_id`, allowing later
  OIDC, RBAC and multi-workspace policy without rewriting core entities;
- append-only run events can later feed observability and eval pipelines;
- capability packs, RAG, approvals and publishing extend the kernel through
  contracts and ports rather than special cases in the UI.

Horizontal scale is not part of Slice 1, but the design does not require a
rewrite to add more API instances, Temporal workers or read consumers.

## 4. Repository structure

```text
apps/
  studio-web/
    src/app/[locale]/
    src/features/
    src/lib/
    src/messages/
    tests/
  control-api/
    src/universal_agent_studio_api/
      api/
      auth/
      agents/
      runs/
      persistence/
      settings.py
    tests/
workers/
  runtime/
    src/universal_agent_studio_runtime/
      activities/
      workflows/
      worker.py
    tests/
libs/
  python/
    agent_kernel/
      src/universal_agent_kernel/
        contracts/
        execution/
        models/
        tools/
        redaction/
        ports.py
      tests/
    platform_store/
      src/universal_agent_platform_store/
        models.py
        repositories/
        session.py
      tests/
  typescript/
    contracts/
    ui/
infra/
  docker/
    compose.local.yml
    api.Dockerfile
    web.Dockerfile
scripts/
  dev-local.mjs
  local-down.mjs
tests/
  integration/
  e2e/
```

Python packages use one uv workspace. TypeScript packages use the existing
pnpm workspace. Imports follow accepted boundaries:

- Web may import TypeScript contract and UI libraries;
- API and worker may import Python contract/kernel libraries;
- API and worker may import the shared PostgreSQL persistence adapter;
- API may not import worker implementation;
- worker may not import API or frontend code;
- kernel may not import FastAPI, SQLAlchemy, Temporal, the persistence adapter
  or provider SDKs.

## 5. Local process model

`pnpm dev:local` invokes `scripts/dev-local.mjs`, which:

1. verifies Docker and Compose availability;
2. runs `docker compose -f infra/docker/compose.local.yml up --build --wait`;
3. fails with service-specific diagnostics if a healthcheck does not pass;
4. prints Studio, API and Temporal UI addresses;
5. leaves the healthy stack running until `pnpm local:down`.

The Compose project contains:

- `studio-web`;
- `control-api`;
- `runtime-worker`;
- `migrate`, a one-shot schema migration service;
- product PostgreSQL;
- Temporal development server and Temporal UI.

Before Compose starts, the launcher creates independent session and internal
command-signing secrets under ignored `.local/secrets` storage with owner-only
permissions. Example environment files contain names and safe defaults, never
working credentials.

Images and actions are pinned to exact versions; container image digests are
recorded before Slice 1 is declared complete. Services run as non-root where
their upstream image permits it. Product and Temporal persistence use separate
databases or schemas and separate credentials.

Compose healthchecks, `service_healthy` and `service_completed_successfully`
eliminate startup races. Named volumes preserve local data across ordinary
restarts. `pnpm local:reset` requires an explicit confirmation flag before it
removes product volumes.

## 6. Canonical versioning

AgentSpec remains the only behavior source.

### Canonical bytes and digest

Canonical bytes use RFC 8785 JSON Canonicalization Scheme. The digest is:

```text
sha256(rfc8785(agent_spec))
```

The digest covers the complete AgentSpec and excludes database identifiers,
timestamps and the AgentVersion envelope. Import validation performs:

1. payload byte-size limit;
2. JSON parsing with duplicate-key rejection;
3. JSON Schema validation;
4. semantic invariant validation;
5. canonical serialization and digest calculation.

An identical digest for the same agent reuses the existing immutable version.
An active-version operation only changes the active pointer. It never updates
the stored specification.

### Signing boundary

Slice 1 stores an unsigned version envelope with a digest. Future signing adds
a signature over the digest and selected envelope metadata. Signing keys and
signature implementation do not enter this slice or AgentSpec.

## 7. Persistence model

PostgreSQL is authoritative for control-plane and trace state. Alembic owns
migrations.

### Identity and auth

- `workspaces`: local private workspace;
- `projects`: default project within the workspace;
- `owners`: owner identity, Argon2id password hash and preferred locale;
- `sessions`: opaque token hash, CSRF secret, expiry and revocation time.

### Agents and versions

- `agents`: stable agent identity and localized metadata;
- `agent_versions`: immutable canonical AgentSpec, schema version, digest,
  creation metadata and provenance;
- `agent_active_versions`: one active version pointer per agent.

### Runs

- `run_requests`: request ID, idempotency key, canonical request digest and
  resolved run ID;
- `runs`: immutable version binding, status, locale, timestamps and terminal
  outcome;
- `run_events`: append-only event envelope with unique `(run_id, sequence)` and
  globally unique `event_id`;
- `node_executions`: node-level redacted input, output, attempts and timing;
- `run_traces`: terminal trace document and schema version;
- `tool_invocations`: logical invocation key and redacted result used to
  prevent duplicate side effects during activity retries.

Every protected table includes `workspace_id` and `project_id`. Repository
queries require an explicit scope object; a missing scope is an error, not a
global query.

JSONB stores canonical contract documents. Frequently filtered identifiers,
status, sequence, timestamps and digests use typed columns and constraints.

## 8. Public API

All endpoints are under `/api/v1`. OpenAPI is generated by FastAPI, while
AgentSpec and run payload validation remains bound to canonical schemas.

### Bootstrap and session

```text
GET    /api/v1/bootstrap/status
POST   /api/v1/bootstrap/owner
POST   /api/v1/session
GET    /api/v1/session
DELETE /api/v1/session
DELETE /api/v1/workspace
```

Bootstrap is transactional and succeeds once. Workspace deletion requires an
authenticated owner, CSRF token, current password and exact confirmation
phrase.

### Versions

```text
POST /api/v1/agent-versions/import
POST /api/v1/agents/{agent_id}/active-version
GET  /api/v1/agent-versions/{version_id}
```

Import returns validation issues with a stable code, JSON Pointer and optional
`node_id`. Activation accepts a version ID and expected previous pointer for
optimistic concurrency.

### Runs

```text
POST /api/v1/runs
GET  /api/v1/runs/{run_id}
POST /api/v1/runs/{run_id}/cancel
GET  /api/v1/runs/{run_id}/events
GET  /api/v1/runs/{run_id}/trace
```

`POST /runs` stores the request and run before starting durable execution.
Repeating the same idempotency key and canonical request returns the same
`run_id`. Reusing the key with a different request returns HTTP 409 and a
canonical `ErrorEnvelope`.

Error responses expose stable support codes and safe structured details.
Provider bodies, stack traces, SQL, credentials and internal hostnames are
never returned.

## 9. Authentication and request security

The local Studio is private even on loopback:

- owner passwords are hashed with Argon2id;
- the browser receives an opaque, `HttpOnly`, `SameSite=Lax` session cookie;
- only a session-token hash is stored in PostgreSQL;
- state-changing requests require `X-CSRF-Token`;
- bootstrap and login enforce trusted Origin and Host values;
- sessions rotate at login and bootstrap, expire and can be revoked;
- API input has endpoint-specific byte, depth and collection limits;
- rate limits protect bootstrap, login, import and run creation;
- workspace/project scope is derived from the authenticated principal, never
  trusted from arbitrary browser input.

The Web app proxies browser API calls through the same origin. Direct API
access remains available for programmatic clients through an explicitly
issued local API session in a later publishing slice; Slice 1 automation uses
the authenticated owner session.

## 10. Runtime and Temporal design

### Product-owned ports

```text
DurableExecutionPort
  start_run(command) -> durable_execution_id
  request_cancel(run_id) -> cancellation_status
  describe(run_id) -> durable_status

ModelGatewayPort
  generate(request, context) -> model_result

ToolGatewayPort
  invoke(request, context) -> tool_result

RunEventSink
  append(event) -> stored_event

TraceStore
  finalize(trace) -> stored_trace
```

Domain command and result types contain no Temporal, FastAPI, SQLAlchemy or
provider SDK objects.

API-to-worker commands use a product-owned signed envelope. The API calculates
an HMAC-SHA-256 over canonical command bytes with a local internal signing key;
the worker verifies the signature before loading the snapshot or emitting an
event. The key is generated into ignored local secret storage with restrictive
permissions and is mounted read-only into API and worker containers. The key
and signature never enter AgentSpec, RunEvent or RunTrace.

### Workflow

One Temporal workflow executes one run. Workflow ID is derived from the
product run ID. The workflow:

1. emits `run.started`;
2. resolves the validated immutable snapshot;
3. executes input, model, tool and output nodes in graph order;
4. emits the accepted event sequence;
5. validates the structured output;
6. finalizes exactly one completed, failed or cancelled trace.

Logical event IDs are deterministic UUIDv5 values derived from run ID and
sequence. Workflow time supplies stable event timestamps. Event append
activities use unique constraints and idempotent upsert semantics, so activity
retry cannot create a second logical event.

Cancellation uses a product workflow signal, allowing the workflow to append a
terminal cancellation event and partial trace. Temporal cancellation is a
fallback for an unresponsive workflow, not the normal API behavior.

### Restart behavior

Model and tool activities are independently retryable. A controlled fake-model
delay allows integration tests to stop and restart the worker. After restart,
Temporal resumes workflow history, and `tool_invocations` prevents a repeated
logical tool result.

## 11. Deterministic model and calculator

### Deterministic model adapter

The fake adapter supports only the declared `calculator-planner-v1` profile.
For the golden question it returns a typed request:

```json
{
  "tool_id": "builtin-calculator",
  "arguments": {
    "operation": "multiply",
    "left": 19,
    "right": 23
  }
}
```

Unsupported inputs fail with a stable model error. The adapter never calls the
network and can expose a test-only controlled delay through worker
configuration, not AgentSpec.

### Calculator

The calculator accepts the manifest-declared operation and finite numeric
operands. It implements an explicit operation allowlist; it does not use
`eval`, execute expressions, read files, access the network or resolve
credentials. Results are validated against ToolManifest output schema.

### OpenAI-compatible BYOK

An optional adapter proves the provider boundary without entering deterministic
CI. It:

- uses a namespaced model route and `CredentialReference`;
- resolves the credential from server-side environment-backed storage;
- supports configurable base URL with an explicit HTTPS/loopback policy;
- enforces timeouts, response limits and structured-output parsing;
- maps provider errors to `ErrorEnvelope`;
- never logs or persists authorization headers or raw credential values.

The smoke test is opt-in and skipped when its dedicated environment variables
are absent.

## 12. Events, SSE and trace

RunEvents are persisted before delivery. The SSE endpoint:

- sets SSE `id` to the decimal event sequence;
- reads `Last-Event-ID` and validates it as a non-negative integer;
- emits stored events with sequence greater than the acknowledged value;
- sends a comment heartbeat while the run is non-terminal;
- closes after the terminal event has been delivered;
- permits reconnect and consumer deduplication by `event_id`.

PostgreSQL is the initial event store. Slice 1 may use bounded polling for
notification latency; event correctness never depends on an in-memory broker.

RunTrace contains the immutable version digest, events, node executions, model
and tool resolutions, redaction policy and metrics. Terminal trace persistence
and terminal run status occur through an idempotent finalization transaction.

## 13. Web experience

### Routes

```text
/{locale}/setup
/{locale}/login
/{locale}/agents/{agent_id}
/{locale}/runs/{run_id}
```

Supported locales are `ru-RU` and `en-US`. Locale is visible in the URL,
persisted as owner preference and changeable without changing run semantics.
API errors contain stable codes and interpolation parameters; the UI owns
translated user copy.

### Screens

1. **Owner setup:** locale, owner name, password and confirmation.
2. **Agent runner:** active version, digest, localized question input and one
   primary Run action.
3. **Run progress:** event timeline, reconnect state and Cancel action.
4. **Structured result:** schema-driven value without debug payload.
5. **Read-only flow:** React Flow projection from AgentSpec.
6. **Node trace inspector:** status, attempts, timing, redacted I/O and
   provenance.

The flow always has a keyboard-reachable table/list alternative. On narrow
screens the timeline and list are primary; graph inspection is secondary.

### Visual system

The UI is a calm technical workbench:

- first-party semantic CSS variables for light and dark themes;
- restrained neutral surfaces and one cyan/blue action accent;
- node category accents supplement text and icon labels;
- 4/8-based spacing, 6/10/14 radii and visible two-pixel focus rings;
- minimum 44-by-44 CSS pixel targets;
- no emoji icons, copied competitor assets, decorative glass or data-obscuring
  gradients;
- skeleton, empty, validation, runtime error, reconnect, cancelled and success
  states reserve layout space and include recovery actions.

All interactive behavior works by keyboard. Route changes focus the main
heading, live run status uses an appropriate polite live region, and reduced
motion disables nonessential transitions.

## 14. Contract type generation

JSON Schema remains canonical.

- Python generated contract models live under
  `libs/python/agent_kernel/.../contracts/generated`.
- TypeScript generated types and validators live under
  `libs/typescript/contracts`.
- generation is deterministic and checked in CI;
- generated files contain provenance headers and are never edited manually;
- schema validation remains available at trust boundaries even when generated
  types are used internally.

Generation tooling is selected and pinned during implementation only after its
output is tested against the existing cross-language fixture manifest.

## 15. Testing strategy

### Unit

- canonical JSON and digest vectors;
- secret detection and redaction;
- calculator operation and numeric edge cases;
- deterministic model requests;
- graph execution and structured-output validation;
- session, CSRF and authorization policy;
- localized UI components and reducers.

### Contract and API

- existing Python/TypeScript fixture manifest;
- generated type drift;
- OpenAPI response and `ErrorEnvelope` conformance;
- invalid import paths and size limits;
- same/different-body idempotency;
- cross-project access denial.

### Integration

- migrations on empty PostgreSQL;
- import and activation transaction;
- run/event/trace persistence;
- Temporal workflow completion;
- cancellation and partial trace;
- worker stop/restart during a delayed activity;
- duplicate activity/event delivery;
- SSE reconnect from `Last-Event-ID`;
- workspace deletion without fixture deletion.

### Browser E2E

Playwright verifies both locales and keyboard-only critical paths:

1. bootstrap owner;
2. import and activate golden AgentSpec;
3. run the golden question;
4. refresh during progress;
5. observe `{ "value": 437 }`;
6. inspect flow and node trace;
7. switch locale;
8. cancel a controlled delayed run;
9. log out and log in again.

The deterministic suite blocks external network except loopback/container
services. A dedicated accessibility pass checks names, focus, live status,
zoom and reduced-motion behavior.

## 16. CI and release gates

Required checks:

- Python formatting, lint, type checking and tests;
- TypeScript formatting, lint, type checking and tests;
- JSON Schema and generated-contract conformance;
- container builds;
- migration smoke test;
- deterministic PostgreSQL/Temporal integration;
- Playwright Chromium E2E in `ru-RU` and `en-US`;
- dependency/license registry validation;
- secret-pattern scan;
- README audit when the documented story changes.

The optional OpenAI-compatible smoke test is manual or explicitly enabled and
never blocks pull requests without credentials.

## 17. Failure handling

- Validation failures never create a version.
- Durable-start failure leaves a persisted run in a safe failed state with a
  canonical error.
- Activity retry is bounded and visible in node execution attempts.
- Invalid model or tool output fails closed before the next node.
- SSE disconnect does not affect execution.
- API or Web restart does not affect durable execution.
- Worker restart is recovered by Temporal.
- Finalization retry cannot produce two terminal events or two traces.
- Unexpected exceptions are logged with a correlation ID after redaction and
  returned only as stable internal error codes.

## 18. Explicit exclusions

Slice 1 does not implement:

- editable canvas or drafts;
- public Published App;
- public API keys, webhooks or anonymous principals;
- RAG, files or object storage;
- arbitrary HTTP, OpenAPI or MCP tools;
- code nodes or sandbox;
- capability-pack expansion;
- AI Builder;
- eval campaigns or autoresearch;
- multi-user roles or OIDC;
- production server deployment.

Interfaces may reserve these extensions, but the UI does not display
nonfunctional placeholders for them.

## 19. Acceptance evidence

The authoritative black-box contract remains
`docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md`. Completion requires:

- clean-checkout `pnpm dev:local` evidence;
- golden Web and API runs;
- persisted version, events and trace validated against canonical schemas;
- reconnect, cancellation, idempotency and worker-restart tests;
- security tests for auth, CSRF, isolation, limits, redaction and deletion;
- RU/EN keyboard E2E;
- clean dependency and license registry;
- successful GitHub Actions on the published `main` commit.

No narrower demo, mocked browser-only flow or in-process substitute satisfies
Slice 1.

## 20. Implementation sources

- Next.js deployment and system requirements:
  https://nextjs.org/docs/app/getting-started/installation
- Docker Compose healthchecks and startup ordering:
  https://docs.docker.com/compose/how-tos/startup-order/
- Temporal documentation and Python SDK:
  https://docs.temporal.io/
  and https://github.com/temporalio/sdk-python
- Temporal server samples:
  https://github.com/temporalio/samples-server
- FastAPI version pinning:
  https://fastapi.tiangolo.com/deployment/versions/
- Playwright browser and test-runner guidance:
  https://playwright.dev/docs/browsers
