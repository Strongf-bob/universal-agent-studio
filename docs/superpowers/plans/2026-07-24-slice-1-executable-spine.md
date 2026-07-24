# Slice 1 Local Executable Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the complete local owner → immutable AgentVersion → Web/API run → Temporal worker → deterministic model → calculator → resumable events → redacted trace path defined by the Slice 1 design and acceptance contracts.

**Architecture:** A Next.js Studio talks to a modular FastAPI control plane. The API persists scoped product state in PostgreSQL and starts a product-owned `DurableExecutionPort`; its Temporal adapter drives a separate Python runtime worker whose kernel depends only on model, tool, event and trace ports. Canonical JSON Schema remains the shared source for generated Python and TypeScript contract types.

**Tech Stack:** Node.js 26.3.0, pnpm 11.7.0, Next.js 16.2.11, React 19.2.8, next-intl 4.13.4, React Flow 12.11.2, Python 3.14.6, uv 0.11.32, FastAPI 0.139.2, SQLAlchemy 2.0.51, Alembic 1.18.5, asyncpg 0.31.0, Temporal Python SDK 1.30.0, PostgreSQL 18.4, Temporal CLI/server 1.8.1, Playwright 1.61.1.

## Global Constraints

- The black-box completion contract is `docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md`.
- The approved design is `docs/superpowers/specs/2026-07-24-slice-1-executable-spine-design.md`.
- AgentSpec is the only behavior source; no canvas or UI state enters runtime semantics.
- Published AgentVersion and run snapshot content are immutable and bound to an RFC 8785 SHA-256 digest.
- Browser, API, worker and persistence boundaries accept only canonical contract payloads or product-owned domain types.
- The API never executes a run; the worker never imports API or frontend implementation.
- Secret values are forbidden in AgentSpec, browser bundles, events, traces, fixtures and logs.
- Every protected repository query requires `workspace_id` and `project_id`.
- Deterministic CI uses no external model network; OpenAI-compatible BYOK is opt-in only.
- Both `ru-RU` and `en-US`, keyboard flow, visible focus, reduced motion and all async states are required.
- No editable canvas, RAG, arbitrary HTTP/MCP/code tool, public publishing, AI Builder, eval campaign or autoresearch enters Slice 1.
- New third-party packages and container images require exact version, source, license, purpose and owner entries before installation.
- Each task follows red → green, runs its exact checks, receives inline self-review, then ends in one focused commit and push.

---

### Task 1: Establish the application workspaces and pinned toolchains

**Files:**
- Create: `tests/repository/test_slice1_layout.py`
- Modify: `pyproject.toml`
- Create: `libs/python/agent_kernel/pyproject.toml`
- Create: `libs/python/platform_store/pyproject.toml`
- Create: `apps/control-api/pyproject.toml`
- Create: `workers/runtime/pyproject.toml`
- Create: `apps/studio-web/package.json`
- Create: `apps/studio-web/tsconfig.json`
- Create: `apps/studio-web/next.config.ts`
- Create: `apps/studio-web/eslint.config.mjs`
- Modify: `package.json`
- Modify: `pnpm-workspace.yaml`
- Modify: `third_party/candidates.yaml`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Node/Python version boundaries from ADR-0001 and existing lockfiles.
- Produces: installable workspace packages named `universal-agent-kernel`, `universal-agent-platform-store`, `universal-agent-studio-api`, `universal-agent-studio-runtime`, and `@universal-agent-studio/studio-web`.

- [x] **Step 1: Write the layout test**

Create a parametrized repository test that asserts the four Python package
manifests, Web manifest, source roots and expected root scripts exist:

```python
@pytest.mark.parametrize(
    "relative_path",
    [
        "libs/python/agent_kernel/pyproject.toml",
        "libs/python/platform_store/pyproject.toml",
        "apps/control-api/pyproject.toml",
        "workers/runtime/pyproject.toml",
        "apps/studio-web/package.json",
    ],
)
def test_slice1_workspace_path_exists(relative_path: str) -> None:
    assert (ROOT / relative_path).is_file()
```

- [x] **Step 2: Verify the test is red**

Run:

```bash
uv run pytest tests/repository/test_slice1_layout.py -q
```

Expected: failures listing every missing Slice 1 package.

- [x] **Step 3: Add exact workspace manifests**

Configure `[tool.uv.workspace]` members for the four Python packages and add
root dev dependencies:

```toml
"datamodel-code-generator==0.70.0"
"mypy==2.3.0"
"pytest-asyncio==1.4.0"
"ruff==0.16.0"
"types-jsonschema==4.26.0.20260518"
```

Pin the application dependencies:

```text
fastapi[standard-no-fastapi-cloud-cli]==0.139.2
sqlalchemy[asyncio]==2.0.51
alembic==1.18.5
asyncpg==0.31.0
temporalio==1.30.0
argon2-cffi==25.1.0
httpx==0.28.1
rfc8785==0.1.4
pydantic-settings==2.14.2
```

Pin the Web dependencies:

```text
next 16.2.11
react/react-dom 19.2.8
next-intl 4.13.4
@xyflow/react 12.11.2
lucide-react 1.26.0
@playwright/test 1.61.1
@testing-library/react 16.3.2
@testing-library/user-event 14.6.1
@testing-library/jest-dom 7.0.0
jsdom 29.1.1
eslint 9.39.5
eslint-config-next 16.2.11
json-schema-to-typescript 15.0.4
typescript 6.0.3
```

TypeScript and ESLint use the latest releases supported by the transitive
`typescript-eslint` and ESLint plugins in Next.js 16.2.11. TypeScript 7 and
ESLint 10 fail those upstream compatibility checks.

Add root scripts with these stable names:

```json
{
  "dev:local": "node scripts/dev-local.mjs",
  "local:down": "node scripts/local-down.mjs",
  "test:python": "uv run pytest -q",
  "test:web": "pnpm --filter @universal-agent-studio/studio-web test",
  "test:e2e": "pnpm --filter @universal-agent-studio/studio-web test:e2e",
  "check": "pnpm check:contracts && pnpm --filter @universal-agent-studio/studio-web check && uv run ruff check . && uv run mypy apps workers libs tests"
}
```

Record every direct dependency in `third_party/candidates.yaml`, then run
`uv lock` and `pnpm install`.

- [x] **Step 4: Verify the workspace**

Run:

```bash
uv sync --all-packages --frozen
pnpm install --frozen-lockfile
uv run pytest tests/repository/test_slice1_layout.py -q
pnpm --filter @universal-agent-studio/studio-web exec next info
```

Expected: layout tests pass, frozen installs make no lockfile changes, and
Next reports the pinned packages.

- [x] **Step 5: Commit and push**

```bash
git add pyproject.toml uv.lock package.json pnpm-workspace.yaml pnpm-lock.yaml \
  .gitignore third_party/candidates.yaml tests/repository apps/control-api \
  apps/studio-web workers/runtime libs/python/agent_kernel \
  libs/python/platform_store
git commit -m "build: establish Slice 1 workspaces"
git push
```

---

### Task 2: Generate contract types and implement canonical version hashing

**Files:**
- Create: `scripts/generate-contracts.mjs`
- Create: `scripts/generate_contracts.py`
- Create: `libs/typescript/contracts/package.json`
- Create: `libs/typescript/contracts/src/generated.ts`
- Create: `libs/typescript/contracts/src/node-spec.generated.ts`
- Create: `libs/typescript/contracts/src/index.ts`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/contracts/generated.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/contracts/schemas/bundle.schema.json`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/contracts/canonical.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/contracts/validation.py`
- Create: `libs/python/agent_kernel/tests/test_canonical_contracts.py`
- Create: `tests/fixtures/canonical/agent.calculator.sha256`
- Modify: `package.json`

**Interfaces:**
- Consumes: `contracts/schemas/v0.1.0`, fixture manifest and RFC 8785.
- Produces: `canonicalize(document) -> bytes`, `content_digest(document) -> str`, `validate_agent_spec(document) -> ValidationResult`, generated Python models and generated TypeScript interfaces.

- [x] **Step 1: Write failing canonicalization and validation tests**

Cover:

```python
def test_object_key_order_does_not_change_digest() -> None: ...
def test_numeric_spelling_has_rfc8785_digest() -> None: ...
def test_golden_agent_digest_matches_locked_vector() -> None: ...
def test_duplicate_json_key_is_rejected_before_hashing() -> None: ...
def test_invalid_agent_reports_json_pointer_and_node_id() -> None: ...
```

The locked vector contains one lowercase 64-character SHA-256 value generated
from the golden AgentSpec.

- [x] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest libs/python/agent_kernel/tests/test_canonical_contracts.py -q
```

Expected: import failure for `universal_agent_kernel.contracts.canonical`.

- [x] **Step 3: Implement generation and canonical services**

Use `rfc8785.dumps()` and `hashlib.sha256()`. Parse raw JSON with an
`object_pairs_hook` that raises `duplicate_json_key`. Reuse the existing
JSON Schema registry and semantic checks rather than creating a second
contract interpretation.

Expose:

```python
@dataclass(frozen=True)
class ValidationIssue:
    code: str
    json_pointer: str
    node_id: str | None
    message_key: str

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]
```

Generation scripts must include a header containing source schema version and
must write deterministic UTF-8/LF output. Add root scripts:

```json
{
  "generate:contracts": "uv run python scripts/generate_contracts.py && node scripts/generate-contracts.mjs",
  "check:generated": "uv run python scripts/generate_contracts.py --check && node scripts/generate-contracts.mjs --check"
}
```

- [x] **Step 4: Verify cross-language output**

Run:

```bash
pnpm generate:contracts
pnpm check:generated
uv run pytest tests/contracts libs/python/agent_kernel/tests -q
pnpm check:contracts
pnpm test:contracts
```

Expected: generated drift check passes and all old and new contract tests pass.

- [x] **Step 5: Commit and push**

```bash
git add scripts libs/python/agent_kernel libs/typescript/contracts \
  tests/fixtures/canonical package.json pnpm-lock.yaml
git commit -m "feat: generate canonical contract types"
git push
```

---

### Task 3: Build the provider-independent Agent Kernel

**Files:**
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/domain.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/ports.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/execution/graph.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/execution/events.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/models/fake.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/tools/calculator.py`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/redaction/policy.py`
- Create: `libs/python/agent_kernel/tests/test_fake_model.py`
- Create: `libs/python/agent_kernel/tests/test_calculator.py`
- Create: `libs/python/agent_kernel/tests/test_graph_execution.py`
- Create: `libs/python/agent_kernel/tests/test_redaction.py`

**Interfaces:**
- Consumes: validated immutable AgentSpec and generated contract types.
- Produces: `AgentKernel.execute(ExecutionCommand, ExecutionPorts) -> RunOutcome`, `ModelGatewayPort`, `ToolGatewayPort`, `RunEventSink`, `TraceStore`, and the built-in fake/calculator adapters.

- [x] **Step 1: Write failing port and golden-flow tests**

Define the required immutable command:

```python
@dataclass(frozen=True)
class ExecutionCommand:
    run_id: UUID
    request_id: UUID
    workspace_id: UUID
    project_id: UUID
    agent_version_id: str
    agent_version_digest: str
    agent_spec: Mapping[str, object]
    input: Mapping[str, object]
    locale: str
```

Tests assert the golden event order, `{ "value": 437 }`, deterministic UUIDv5
event IDs, output-schema validation, no provider classes in domain values,
calculator rejection of unknown operations/non-finite numbers, and recursive
redaction of secret aliases.

- [x] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest libs/python/agent_kernel/tests/test_fake_model.py \
  libs/python/agent_kernel/tests/test_calculator.py \
  libs/python/agent_kernel/tests/test_graph_execution.py \
  libs/python/agent_kernel/tests/test_redaction.py -q
```

Expected: missing kernel modules.

- [x] **Step 3: Implement the narrow golden interpreter**

The interpreter accepts the four node kinds present in the golden fixture:
`input`, `model`, `tool`, `output`. It resolves references, validates every
tool input/output and final output, and fails closed on another node kind.

The fake model returns:

```python
ToolRequest(
    tool_id="builtin-calculator",
    arguments={"operation": "multiply", "left": 19, "right": 23},
)
```

The calculator implements an explicit function table:

```python
OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}
```

No expression parser, `eval`, file or network API is permitted.

- [x] **Step 4: Verify kernel behavior and import boundaries**

Run:

```bash
uv run pytest libs/python/agent_kernel/tests -q
uv run ruff check libs/python/agent_kernel
uv run mypy libs/python/agent_kernel
rg -n "fastapi|sqlalchemy|temporalio|openai" libs/python/agent_kernel/src
```

Expected: tests/type/lint pass and the boundary search returns no imports.

- [x] **Step 5: Commit and push**

```bash
git add libs/python/agent_kernel
git commit -m "feat: execute the golden AgentSpec in the kernel"
git push
```

---

### Task 4: Add scoped PostgreSQL persistence and migrations

**Files:**
- Create: `libs/python/platform_store/src/universal_agent_platform_store/models.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/session.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/scope.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/agents.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/auth.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/runs.py`
- Create: `infra/migrations/alembic.ini`
- Create: `infra/migrations/env.py`
- Create: `infra/migrations/versions/0001_slice1_spine.py`
- Create: `libs/python/platform_store/tests/test_scope.py`
- Create: `tests/integration/test_migrations.py`
- Create: `tests/integration/test_agent_repository.py`
- Create: `tests/integration/test_run_repository.py`

**Interfaces:**
- Consumes: domain IDs, canonical AgentSpec/digests and RunEvent/RunTrace documents.
- Produces: `RequestScope`, scoped auth/agent/run repositories, async session factory, and migration `0001`.

- [x] **Step 1: Write failing repository tests**

Tests use a dedicated PostgreSQL test database and assert:

```python
async def test_all_protected_queries_require_scope() -> None: ...
async def test_identical_agent_digest_reuses_immutable_version() -> None: ...
async def test_active_pointer_uses_expected_previous_version() -> None: ...
async def test_idempotency_same_body_reuses_run() -> None: ...
async def test_idempotency_different_body_conflicts() -> None: ...
async def test_duplicate_event_retry_returns_existing_event() -> None: ...
async def test_terminal_trace_finalizes_once() -> None: ...
```

- [x] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest libs/python/platform_store/tests tests/integration/test_migrations.py \
  tests/integration/test_agent_repository.py tests/integration/test_run_repository.py -q
```

Expected: missing persistence modules or missing `DATABASE_URL`.

- [x] **Step 3: Implement models, constraints and repositories**

Create all tables listed in the approved design. Enforce:

```text
unique(agent_id, digest)
unique(workspace_id, project_id, idempotency_key)
unique(run_id, sequence)
unique(event_id)
unique(run_id) on run_traces
unique(run_id, node_id, logical_invocation_key) on tool_invocations
```

Use UTC-aware timestamps, JSONB, explicit foreign keys and `ON DELETE`
behavior. Repository constructors require `RequestScope`; only bootstrap and
workspace-deletion services may use an explicit administrative scope.

- [x] **Step 4: Verify migration and repository behavior**

Run:

```bash
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run pytest libs/python/platform_store/tests tests/integration/test_migrations.py \
  tests/integration/test_agent_repository.py tests/integration/test_run_repository.py -q
uv run mypy libs/python/platform_store
```

Expected: empty-database migration and all repository tests pass.

- [x] **Step 5: Commit and push**

```bash
git add libs/python/platform_store infra/migrations tests/integration
git commit -m "feat: persist scoped versions runs and traces"
git push
```

---

### Task 5: Implement owner bootstrap, sessions, CSRF and deletion

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/main.py`
- Create: `apps/control-api/src/universal_agent_studio_api/settings.py`
- Create: `apps/control-api/src/universal_agent_studio_api/errors.py`
- Create: `apps/control-api/src/universal_agent_studio_api/auth/models.py`
- Create: `apps/control-api/src/universal_agent_studio_api/auth/service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/auth/dependencies.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/bootstrap.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/session.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/workspace.py`
- Create: `apps/control-api/tests/test_bootstrap_session.py`
- Create: `apps/control-api/tests/test_csrf.py`
- Create: `apps/control-api/tests/test_workspace_deletion.py`

**Interfaces:**
- Consumes: auth repository, RequestScope, Argon2id.
- Produces: bootstrap/session/workspace endpoints, `AuthenticatedOwner`, opaque session cookie and CSRF header contract.

- [ ] **Step 1: Write failing security API tests**

Cover one-time bootstrap, Argon2id hash shape, session rotation, `HttpOnly` and
`SameSite=Lax`, trusted Host/Origin, CSRF rejection, expiry/revocation, generic
login error, request limits and exact deletion confirmation. Hash the session
token before repository storage and assert the raw value never appears in
database/log capture.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest apps/control-api/tests/test_bootstrap_session.py \
  apps/control-api/tests/test_csrf.py \
  apps/control-api/tests/test_workspace_deletion.py -q
```

Expected: missing FastAPI application/auth modules.

- [ ] **Step 3: Implement the auth boundary**

Use JSON request bodies. The session cookie name is `uas_session`; browser
mutations require `X-CSRF-Token`. Expose CSRF only in authenticated session
responses, never in a cookie readable by arbitrary scripts.

Use the canonical safe error shape:

```json
{
  "schema_version": "0.1.0",
  "code": "authentication_failed",
  "message": "Request could not be authenticated.",
  "retryable": false,
  "details": {}
}
```

Add request correlation middleware and a redacting exception handler.

- [ ] **Step 4: Verify security behavior**

Run:

```bash
uv run pytest apps/control-api/tests/test_bootstrap_session.py \
  apps/control-api/tests/test_csrf.py \
  apps/control-api/tests/test_workspace_deletion.py -q
uv run ruff check apps/control-api
uv run mypy apps/control-api
```

Expected: all auth/security tests pass with no raw secret in captured output.

- [ ] **Step 5: Commit and push**

```bash
git add apps/control-api
git commit -m "feat: secure the local owner session"
git push
```

---

### Task 6: Implement AgentVersion import and activation API

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/agents/models.py`
- Create: `apps/control-api/src/universal_agent_studio_api/agents/service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/agent_versions.py`
- Create: `apps/control-api/tests/test_agent_versions.py`
- Create: `tests/integration/test_agent_import_activation.py`

**Interfaces:**
- Consumes: authenticated RequestScope, canonical validation/digest and AgentRepository.
- Produces: `POST /api/v1/agent-versions/import`, activation endpoint, version read endpoint and stable validation issues.

- [ ] **Step 1: Write failing import/activation tests**

Cover golden import, digest equality to locked vector, identical reimport,
invalid schema, dangling edge, secret alias, duplicate JSON key, over-size
payload, active pointer optimistic conflict and cross-project version denial.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest apps/control-api/tests/test_agent_versions.py \
  tests/integration/test_agent_import_activation.py -q
```

Expected: 404 or missing router/service.

- [ ] **Step 3: Implement transactional version operations**

The import endpoint accepts raw JSON bytes so duplicate keys and byte limits
are checked before model binding. Return:

```json
{
  "version_id": "calculator-v1",
  "agent_id": "calculator-agent",
  "schema_version": "0.1.0",
  "digest": "<64 lowercase hex>",
  "validation": {"valid": true, "issues": []},
  "reused": false
}
```

Activation accepts `version_id` and `expected_previous_version_id`.

- [ ] **Step 4: Verify contract and isolation behavior**

Run:

```bash
uv run pytest apps/control-api/tests/test_agent_versions.py \
  tests/integration/test_agent_import_activation.py -q
uv run pytest tests/contracts libs/python/agent_kernel/tests -q
```

Expected: API and canonical contract tests pass.

- [ ] **Step 5: Commit and push**

```bash
git add apps/control-api tests/integration
git commit -m "feat: import immutable AgentVersions"
git push
```

---

### Task 7: Implement Temporal durable execution and runtime worker

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/runs/durable.py`
- Create: `apps/control-api/src/universal_agent_studio_api/runs/temporal_adapter.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/activities/events.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/activities/execution.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/workflows/run.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/worker.py`
- Create: `workers/runtime/tests/test_workflow.py`
- Create: `tests/integration/test_temporal_run.py`
- Create: `tests/integration/test_worker_restart.py`
- Create: `tests/integration/test_temporal_cancellation.py`

**Interfaces:**
- Consumes: persisted run command/snapshot, AgentKernel and scoped RunRepository.
- Produces: `TemporalDurableExecutionAdapter`, signed execution envelope,
  `AgentRunWorkflow`, idempotent activities and worker entrypoint.

- [ ] **Step 1: Write failing workflow environment tests**

Use Temporal's workflow test environment for deterministic workflow tests and
a real local Temporal server for integration. Assert exact event sequence,
UUIDv5 IDs, terminal trace, signal cancellation, activity retry and controlled
worker restart with one logical calculator invocation.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest workers/runtime/tests/test_workflow.py \
  tests/integration/test_temporal_run.py \
  tests/integration/test_worker_restart.py \
  tests/integration/test_temporal_cancellation.py -q
```

Expected: missing durable adapter, workflow and worker modules.

- [ ] **Step 3: Implement the workflow and activities**

Use task queue `uas-runtime-v1` and workflow ID `uas-run-{run_id}`.
`DurableExecutionPort.request_cancel()` sends the product `request_cancel`
signal. Activity retry policies are bounded and tool invocation writes use the
logical `(run_id, node_id, invocation_key)` constraint.

The API signs RFC 8785 canonical command bytes with HMAC-SHA-256. The worker
verifies the envelope with `hmac.compare_digest()` before any repository,
model or event action. Tests cover modified payload, wrong key, missing
signature and signature absence from events/traces.

Workflow code may call only deterministic Temporal APIs. Database, model,
calculator and trace operations stay in activities.

- [ ] **Step 4: Verify replay, restart and cancellation**

Run:

```bash
uv run pytest workers/runtime/tests/test_workflow.py \
  tests/integration/test_temporal_run.py \
  tests/integration/test_worker_restart.py \
  tests/integration/test_temporal_cancellation.py -q
uv run mypy workers/runtime apps/control-api/src/universal_agent_studio_api/runs
```

Expected: completed, restarted and cancelled runs have one terminal event and
schema-valid traces.

- [ ] **Step 5: Commit and push**

```bash
git add apps/control-api/src/universal_agent_studio_api/runs workers/runtime \
  tests/integration
git commit -m "feat: execute runs durably with Temporal"
git push
```

---

### Task 8: Expose idempotent run, SSE and trace APIs

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/runs/service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/runs/sse.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/runs.py`
- Create: `apps/control-api/tests/test_runs_api.py`
- Create: `apps/control-api/tests/test_sse.py`
- Create: `tests/integration/test_run_api_temporal.py`

**Interfaces:**
- Consumes: AgentVersion service, RunRepository and DurableExecutionPort.
- Produces: required `/api/v1/runs` endpoints, SSE resume and canonical run/trace responses.

- [ ] **Step 1: Write failing run API tests**

Test immediate `run_id`, same-body idempotency, different-body 409, inactive
or digest-mismatched version rejection, cancellation, trace-before-terminal
state, terminal trace, cross-project denial, `Last-Event-ID`, heartbeat and
terminal stream closure.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest apps/control-api/tests/test_runs_api.py \
  apps/control-api/tests/test_sse.py \
  tests/integration/test_run_api_temporal.py -q
```

Expected: run routes return 404.

- [ ] **Step 3: Implement run orchestration and streaming**

Persist request/run before calling `start_run`. If durable start fails,
finalize a safe failed run. SSE queries `sequence > Last-Event-ID`, emits:

```text
id: 4
event: tool.requested
data: <canonical RunEvent JSON>
```

Send `: heartbeat` comments while waiting and close after terminal delivery.
Bound polling and disconnect checks prevent unbounded tasks.

- [ ] **Step 4: Verify Web/API contract equivalence**

Run:

```bash
uv run pytest apps/control-api/tests tests/integration/test_run_api_temporal.py -q
uv run python -c 'from universal_agent_studio_api.main import create_app; app=create_app(); assert "/api/v1/runs" in app.openapi()["paths"]'
```

Expected: run API tests pass and OpenAPI contains all required paths.

- [ ] **Step 5: Commit and push**

```bash
git add apps/control-api tests/integration
git commit -m "feat: stream idempotent runs and traces"
git push
```

---

### Task 9: Build the localized owner setup and agent runner

**Files:**
- Create: `apps/studio-web/src/app/[locale]/layout.tsx`
- Create: `apps/studio-web/src/app/[locale]/setup/page.tsx`
- Create: `apps/studio-web/src/app/[locale]/login/page.tsx`
- Create: `apps/studio-web/src/app/[locale]/agents/[agentId]/page.tsx`
- Create: `apps/studio-web/src/app/globals.css`
- Create: `apps/studio-web/src/features/auth/OwnerSetupForm.tsx`
- Create: `apps/studio-web/src/features/auth/LoginForm.tsx`
- Create: `apps/studio-web/src/features/agents/AgentRunner.tsx`
- Create: `apps/studio-web/src/lib/api/client.ts`
- Create: `apps/studio-web/src/lib/i18n/routing.ts`
- Create: `apps/studio-web/src/messages/ru-RU.json`
- Create: `apps/studio-web/src/messages/en-US.json`
- Create: `apps/studio-web/tests/owner-setup.test.tsx`
- Create: `apps/studio-web/tests/agent-runner.test.tsx`

**Interfaces:**
- Consumes: bootstrap/session/version/run APIs and TypeScript contract package.
- Produces: owner setup/login/runner routes, semantic design tokens and locale routing.

- [ ] **Step 1: Write failing component and interaction tests**

Test visible labels, password errors, disabled/loading/success states, focus on
the first invalid field, locale copy, active version digest, golden question,
single primary Run action and safe translated API errors.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
pnpm --filter @universal-agent-studio/studio-web test -- \
  owner-setup.test.tsx agent-runner.test.tsx
```

Expected: missing pages/components.

- [ ] **Step 3: Implement the workbench shell and forms**

Define semantic CSS tokens for both themes and the approved spacing/radius/
motion/focus scales. Use Server Components for route data and Client
Components only for forms and run interaction. No user-facing literal may
appear outside message files.

API client sends credentials, CSRF and correlation headers and maps stable
error codes to localized recovery copy.

- [ ] **Step 4: Verify UI quality**

Run:

```bash
pnpm --filter @universal-agent-studio/studio-web test
pnpm --filter @universal-agent-studio/studio-web check
pnpm --filter @universal-agent-studio/studio-web build
```

Expected: component tests, lint, typecheck and production build pass.

- [ ] **Step 5: Commit and push**

```bash
git add apps/studio-web libs/typescript/contracts package.json pnpm-lock.yaml
git commit -m "feat: add localized owner setup and runner"
git push
```

---

### Task 10: Build resumable progress, read-only flow and trace inspection

**Files:**
- Create: `apps/studio-web/src/app/[locale]/runs/[runId]/page.tsx`
- Create: `apps/studio-web/src/features/runs/useRunEvents.ts`
- Create: `apps/studio-web/src/features/runs/RunTimeline.tsx`
- Create: `apps/studio-web/src/features/runs/RunResult.tsx`
- Create: `apps/studio-web/src/features/runs/ReadOnlyFlow.tsx`
- Create: `apps/studio-web/src/features/runs/FlowTable.tsx`
- Create: `apps/studio-web/src/features/runs/NodeTraceInspector.tsx`
- Create: `apps/studio-web/tests/run-events.test.tsx`
- Create: `apps/studio-web/tests/run-trace.test.tsx`
- Create: `apps/studio-web/tests/accessibility.test.tsx`

**Interfaces:**
- Consumes: RunEvent SSE, AgentVersion and RunTrace.
- Produces: deduplicating/resuming event hook, progress/cancel/result UI, React Flow projection and keyboard table alternative.

- [ ] **Step 1: Write failing streaming and accessibility tests**

Test duplicate `event_id` removal, reconnect from last sequence, refresh
hydration, reconnect banner, cancellation, terminal result, selected node
trace, redacted values, accessible graph table, live region, focus order,
reduced motion and both locale message sets.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
pnpm --filter @universal-agent-studio/studio-web test -- \
  run-events.test.tsx run-trace.test.tsx accessibility.test.tsx
```

Expected: missing run features.

- [ ] **Step 3: Implement run state and projections**

`useRunEvents` seeds from stored events, opens EventSource-compatible fetch
stream with credentials, stores last sequence in component state, and
deduplicates by `event_id`. Reconnect uses bounded exponential backoff and
shows an explicit state.

React Flow receives only:

```ts
type FlowNodeView = {
  id: string;
  label: string;
  kind: string;
  status: NodeExecutionStatus;
};
```

The table renders the same projection and is the primary narrow-screen view.

- [ ] **Step 4: Verify run UI and production build**

Run:

```bash
pnpm --filter @universal-agent-studio/studio-web test
pnpm --filter @universal-agent-studio/studio-web check
pnpm --filter @universal-agent-studio/studio-web build
```

Expected: all Web tests and build pass.

- [ ] **Step 5: Commit and push**

```bash
git add apps/studio-web
git commit -m "feat: inspect live runs and traces"
git push
```

---

### Task 11: Add the local Compose stack and optional BYOK adapter

**Files:**
- Create: `infra/docker/compose.local.yml`
- Create: `infra/docker/api.Dockerfile`
- Create: `infra/docker/web.Dockerfile`
- Create: `infra/docker/.env.example`
- Create: `scripts/dev-local.mjs`
- Create: `scripts/local-down.mjs`
- Create: `scripts/local-reset.mjs`
- Create: `libs/python/agent_kernel/src/universal_agent_kernel/models/openai_compatible.py`
- Create: `libs/python/agent_kernel/tests/test_openai_compatible.py`
- Create: `tests/integration/test_local_stack.py`
- Modify: `package.json`
- Modify: `third_party/candidates.yaml`

**Interfaces:**
- Consumes: all app entrypoints, migrations, health endpoints and ModelGatewayPort.
- Produces: `pnpm dev:local`, `pnpm local:down`, guarded `pnpm local:reset`, healthy containers and opt-in OpenAI-compatible adapter.

- [ ] **Step 1: Write failing launcher and adapter tests**

Test missing-Docker diagnostics, Compose config validation, confirmation guard
for reset, URL allowlist, HTTPS/loopback enforcement, authorization redaction,
timeouts, response-size limit, structured tool-call parsing and provider error
mapping. Also test that the launcher creates separate session and internal
signing secrets with owner-only permissions and never writes them to Compose
config output.

- [ ] **Step 2: Verify the tests are red**

Run:

```bash
uv run pytest libs/python/agent_kernel/tests/test_openai_compatible.py \
  tests/integration/test_local_stack.py -q
node scripts/dev-local.mjs --check
```

Expected: missing adapter/scripts/Compose file.

- [ ] **Step 3: Implement images, Compose and BYOK**

Pin:

```text
node:26.3.0-bookworm-slim@sha256:3fe807a03a4436e7bc76b7e84e6861899cd75c9028ae99bc00581940141ae150
python:3.14.6-slim-bookworm@sha256:86f975aca15cf04a40b399eebede9aea7c82eae084d1f1a0a6ef6bcaae871a30
postgres:18.4-alpine3.23@sha256:996d0920e4ff9df1fc19dacb904492f3c1ec0ec1cc338f0ad7123be7731c5f5e
temporalio/temporal:1.8.1@sha256:59561b9ef060eaeb1f46cb6a1842d6cbdd8a393eb3b6d315ecef5fe2f0b1d7a6
```

Temporal runs `server start-dev` with a named SQLite volume, gRPC on 7233 and
UI on 8080. Product PostgreSQL is independent. Migrations must complete before
API and worker start; all long-running services expose healthchecks.

`dev-local.mjs` creates random session and command-signing keys in ignored
`.local/secrets` files with mode `0600`; Compose mounts only the required key
into each service and never places a real secret in `.env.example`.

The BYOK adapter uses `CredentialReference` to resolve environment-backed
credentials and `httpx.AsyncClient` with explicit timeout/limits. The smoke
test is marked and skipped without its dedicated environment variables.

- [ ] **Step 4: Verify the complete local stack**

Start Docker Desktop, then run:

```bash
docker compose -f infra/docker/compose.local.yml config -q
pnpm dev:local
curl --fail http://localhost:8000/health/ready
curl --fail http://localhost:3000/en-US/setup
curl --fail http://localhost:8080
uv run pytest tests/integration/test_local_stack.py -q
pnpm local:down
```

Expected: all three endpoints answer, integration test passes and normal
shutdown preserves named volumes.

- [ ] **Step 5: Commit and push**

```bash
git add infra/docker scripts package.json third_party/candidates.yaml \
  libs/python/agent_kernel
git commit -m "feat: launch the complete local spine"
git push
```

---

### Task 12: Prove E2E, recovery, security and continuous delivery

**Files:**
- Create: `apps/studio-web/playwright.config.ts`
- Create: `apps/studio-web/e2e/golden-run.spec.ts`
- Create: `apps/studio-web/e2e/reconnect-cancel.spec.ts`
- Create: `apps/studio-web/e2e/locales-keyboard.spec.ts`
- Create: `tests/security/test_secret_absence.py`
- Create: `tests/security/test_cross_project_isolation.py`
- Create: `.github/workflows/slice1.yml`
- Create: `docs/operations/LOCAL_PREVIEW.md`
- Create: `docs/acceptance/evidence/SLICE_1.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `docs/OPEN_QUESTIONS.md`
- Modify: `third_party/candidates.yaml`

**Interfaces:**
- Consumes: complete local stack and all Slice 1 acceptance requirements.
- Produces: deterministic browser/API evidence, security evidence, operator guide and required GitHub Actions gate.

- [ ] **Step 1: Write failing browser and security acceptance tests**

The Playwright suite performs setup, fixture import/activation, run, refresh,
result/flow/trace inspection, locale switch, keyboard navigation, delayed-run
cancellation and logout/login. Security tests scan response/log/trace/browser
artifacts for seeded sentinel secrets and verify cross-project denial.

- [ ] **Step 2: Run the acceptance suite before CI wiring**

Run:

```bash
pnpm test:e2e
uv run pytest tests/security -q
```

Expected: failures identify missing E2E fixtures, orchestration or security
evidence.

- [ ] **Step 3: Complete deterministic orchestration, CI and docs**

Add a GitHub Actions workflow with immutable action SHAs that:

1. installs pinned uv/pnpm/Node;
2. runs frozen installs;
3. checks generated contracts, lint and types;
4. runs Python, TypeScript and contract unit tests;
5. builds application containers;
6. starts the local Compose stack;
7. runs migration, Temporal integration and Chromium E2E;
8. collects redacted service logs on failure;
9. always shuts the stack down.

Update README with the real local command, screenshots only if generated from
the actual app, exact tested versions and current Slice status. Remove resolved
Slice 1 questions from `docs/OPEN_QUESTIONS.md`.

- [ ] **Step 4: Run the full completion audit locally**

Run:

```bash
git diff --check
uv sync --all-packages --frozen
pnpm install --frozen-lockfile
pnpm check:generated
pnpm check
pnpm test:contracts
uv run pytest -q
pnpm test:web
docker compose -f infra/docker/compose.local.yml build
pnpm dev:local
pnpm test:e2e
uv run pytest tests/security tests/integration -q
python3 /Users/strongf/.codex/skills/beautify-github-readme/scripts/audit_readme.py README.md
pnpm local:down
git status --short
```

Expected: every command exits zero, no untracked generated/runtime files
remain, and acceptance evidence names the exact commit and observed results.

- [ ] **Step 5: Commit, push and verify the branch**

```bash
git add .github/workflows/slice1.yml apps/studio-web tests/security \
  docs/operations docs/acceptance/evidence README.md ROADMAP.md \
  docs/OPEN_QUESTIONS.md third_party/candidates.yaml
git commit -m "test: prove the Slice 1 executable spine"
git push
gh run list --workflow slice1.yml --branch agent/slice-1-executable-spine --limit 1
```

Expected: the branch workflow succeeds for the final commit.

---

## Publication and goal completion

After all task checkboxes are complete:

1. use `verification-before-completion` for a requirement-by-requirement audit
   against the acceptance contract and active goal;
2. perform a main-agent code/security/UX review because higher-priority
   instructions prohibit delegated implementation/review;
3. use `beautify-github-readme` in audit mode on the finished branch;
4. use `finishing-a-development-branch` and merge only to the already
   authorized `main` boundary;
5. rerun the complete suite on merged `main`;
6. push `main`, wait for GitHub Actions success and inspect the public README;
7. call `update_goal(status="complete")` only if every acceptance item has
   fresh authoritative evidence.

## Self-review

- **Spec coverage:** Tasks 2–8 cover canonical versions, API, Temporal, model,
  tool, idempotency, events and traces; Tasks 9–10 cover all six Web screens,
  RU/EN and accessibility; Tasks 11–12 cover one-command local operation,
  BYOK, recovery, E2E, security, CI and documentation.
- **Scope:** No excluded Slice 2+ product surface is introduced.
- **Type consistency:** `ExecutionCommand`, `RequestScope`, run/event/trace IDs,
  digest and port names are defined before dependent tasks use them.
- **Security:** Auth, CSRF, scope, input limits, redaction, secret scan,
  deletion and provider isolation each have named tests.
- **Recovery:** Durable restart, cancellation, event/activity deduplication and
  SSE resume each have a real integration or E2E check.
