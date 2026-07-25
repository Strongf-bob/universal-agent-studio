# Slice 3 Publishing, Versions and Public Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Application implementation stays in the primary agent session per repository policy.

**Goal:** Publish canonical drafts as immutable versions, serve the active version through a separate RU/EN Web App and scoped public API, deliver signed terminal webhooks, and roll traffic from v2 back to v1 without rewriting history.

**Architecture:** The existing `agent_active_versions` row remains the only traffic pointer. New publishing, credential and webhook modules live behind the current control plane and PostgreSQL transaction boundary; a separate Next.js application consumes sanitized public contracts only. Terminal runtime persistence writes a durable webhook outbox atomically and a bounded worker dispatcher performs allowlisted egress.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2 async, PostgreSQL 18, Temporal, Next.js 16, React 19, TypeScript 5.9, next-intl, Vitest, Playwright, Docker Compose.

## Global Constraints

- Local Preview is loopback-only; no server or Internet-readiness claim.
- Published versions, publication events and historical runs are immutable.
- New public runs always resolve the active version server-side.
- Studio sessions, API-key hashing, browser capabilities and webhook signing use distinct secrets of at least 32 bytes.
- Public responses exclude AgentSpec prompts, tools, provider data, traces, workflow identifiers, stacks and raw internal errors.
- API keys are bound to one project and agent and support only `runs:create`, `runs:read` and `events:read`.
- Webhook targets must match an exact operator-configured origin and redirects are denied.
- RU/EN, keyboard operation, visible focus, reduced motion, 44 CSS pixel touch targets and 200% zoom are release requirements.
- No new third-party runtime dependency is needed.
- Every commit has a concise title and a detailed body with verification.

## File and module map

- `contracts/schemas/v0.1.0/publication.schema.json`: owner publication, key and webhook schemas.
- `contracts/schemas/v0.1.0/public-agent.schema.json`: sanitized metadata, public run and capability schemas.
- `libs/python/platform_store/.../models.py`: four additive Slice 3 records.
- `libs/python/platform_store/.../repositories/publishing.py`: transactional publication and credential persistence.
- `libs/python/platform_store/.../repositories/webhooks.py`: subscription, outbox and delivery persistence.
- `apps/control-api/.../publishing/`: publishing service, credentials and public-principal logic.
- `apps/control-api/.../api/publishing.py`: owner endpoints.
- `apps/control-api/.../api/public.py`: safe public endpoints and SSE.
- `workers/runtime/.../webhooks/`: signing policy and delivery dispatcher.
- `apps/published-web/`: isolated public InterfaceSchema renderer.
- `apps/studio-web/src/features/publishing/`: owner Publish workspace.
- `infra/migrations/versions/0003_slice3_publishing.py`: additive schema migration.
- `infra/docker/compose.local.yml` and scripts: local secrets, second Web app and health.

---

### Task 1: Generated public and owner contracts

**Files:**
- Create: `contracts/schemas/v0.1.0/publication.schema.json`
- Create: `contracts/schemas/v0.1.0/public-agent.schema.json`
- Create: `contracts/examples/v0.1.0/valid/public-agent.calculator.json`
- Create: `contracts/examples/v0.1.0/valid/public-run.completed.json`
- Modify: `contracts/examples/v0.1.0/manifest.json`
- Modify: `scripts/generate_contracts.py`
- Modify: `scripts/generate-contracts.mjs`
- Modify: `tests/contracts/test_contract_examples.py`
- Modify: `tests/contracts/test_authoring_contracts.py`
- Create: `tests/contracts/test_publication_contracts.py`

**Interfaces:**
- Produces: generated Python/TypeScript `PublicationState`, `PublishRequest`, `RollbackRequest`, `ApiKeyCreateRequest`, `ApiKeyCreateView`, `WebhookCreateRequest`, `WebhookCreateView`, `PublicAgentView`, `PublicRunCreateRequest`, `PublicRunView` and `PublicRunEvent`.
- Consumes: existing `$defs.localizedText`, `InterfaceSchema`, locale and digest constraints.

- [ ] **Step 1: Write failing schema and code-generation tests**

```python
def test_public_agent_example_is_sanitized(schema_store):
    document = schema_store.example("valid/public-agent.calculator.json")
    schema_store.validate("public-agent.schema.json", document)
    serialized = json.dumps(document, sort_keys=True)
    for forbidden in ("prompt", "tools", "model_profile", "trace_id"):
        assert forbidden not in serialized


def test_publication_contracts_are_generated():
    from universal_agent_kernel.contracts.generated import (
        PublicAgentView,
        PublicationState,
    )
    assert PublicAgentView.model_fields
    assert PublicationState.model_fields
```

- [ ] **Step 2: Prove the new contracts are absent**

Run: `uv run pytest tests/contracts/test_publication_contracts.py -q`

Expected: FAIL because the schema and generated models do not exist.

- [ ] **Step 3: Add strict JSON Schemas and valid examples**

Define every object with `"additionalProperties": false`. Use UUID strings,
the existing 64-character digest pattern, enum scopes, RU/EN locale enums and
the existing `interface-schema.schema.json` reference. The public run view
contains only `run_id`, `agent_id`, `agent_version_id`,
`agent_version_digest`, `status`, `locale`, safe `output`, safe `error_code`,
`status_url`, `events_url` and optional one-time `run_capability`.

- [ ] **Step 4: Register and generate both language bindings**

Run: `pnpm generate:contracts`

Expected: updated
`libs/python/agent_kernel/src/universal_agent_kernel/contracts/generated.py`
and `libs/typescript/contracts/src/generated.ts`.

- [ ] **Step 5: Verify contract conformance**

Run: `pnpm check:generated && pnpm test:contracts && uv run pytest tests/contracts -q`

Expected: all contract checks pass.

- [ ] **Step 6: Commit the contract boundary**

```bash
git add contracts scripts libs/python/agent_kernel/src/universal_agent_kernel/contracts/generated.py libs/typescript/contracts/src/generated.ts tests/contracts
git commit -m "feat: define Slice 3 public contracts" -m "Add strict owner publication and sanitized public-delivery schemas, valid fixtures, and generated Python and TypeScript bindings.\n\nVerification: pnpm check:generated; pnpm test:contracts; uv run pytest tests/contracts -q."
```

### Task 2: Additive persistence and transactional publication

**Files:**
- Modify: `libs/python/platform_store/src/universal_agent_platform_store/models.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/publishing.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/webhooks.py`
- Modify: `libs/python/platform_store/src/universal_agent_platform_store/repositories/__init__.py`
- Create: `infra/migrations/versions/0003_slice3_publishing.py`
- Create: `tests/integration/test_publishing_repository.py`
- Create: `tests/integration/test_webhook_outbox_repository.py`
- Modify: `tests/integration/test_migrations.py`

**Interfaces:**
- Produces:
  - `PublishingRepository.publish_draft(agent_key, expected_revision, expected_active_version_id) -> PublicationResult`
  - `PublishingRepository.rollback(agent_key, target_version_id, expected_active_version_id) -> PublicationResult`
  - `PublishingRepository.get_state(agent_key) -> PublishingStateRecord | None`
  - `ApiKeyRepository.create/list/revoke/verify`
  - `WebhookRepository.create/list/revoke/enqueue_terminal/claim_due/finish_attempt`
- Consumes: `RequestScope`, `AgentDraftRecord`, `AgentVersion`, `AgentActiveVersion`, `Run`, canonical digest and existing PostgreSQL session pattern.

- [ ] **Step 1: Write failing migration and transaction tests**

```python
async def test_publish_v1_v2_then_rollback_preserves_history(
    db_session, owner_scope, seeded_draft
):
    repository = PublishingRepository(db_session, owner_scope)
    v1 = await repository.publish_draft(
        agent_key="calculator",
        expected_revision=seeded_draft.revision,
        expected_active_version_id=seeded_draft.base_version_id,
    )
    await mutate_seeded_draft(db_session, revision=seeded_draft.revision + 1)
    v2 = await repository.publish_draft(
        agent_key="calculator",
        expected_revision=seeded_draft.revision + 1,
        expected_active_version_id=v1.version.id,
    )
    rollback = await repository.rollback(
        agent_key="calculator",
        target_version_id=v1.version.id,
        expected_active_version_id=v2.version.id,
    )
    assert rollback.version.id == v1.version.id
    assert await immutable_version_bytes(db_session, v1.version.id) == v1.bytes
    assert await immutable_version_bytes(db_session, v2.version.id) == v2.bytes
    assert await publication_types(db_session) == ["publish", "publish", "rollback"]
```

- [ ] **Step 2: Run the focused tests and confirm missing tables**

Run: `uv run pytest tests/integration/test_publishing_repository.py tests/integration/test_webhook_outbox_repository.py -q`

Expected: FAIL on missing models and repository modules.

- [ ] **Step 3: Add constrained SQLAlchemy records and migration**

Implement `AgentPublicationEvent`, `AgentApiKey`, `WebhookSubscription` and
`WebhookDelivery`. Include scoped foreign keys/indexes, append-only event
shape, unique agent digest reuse, unique key prefix, delivery idempotency,
bounded status/error columns and check constraints for enum-like fields.
Migration upgrade creates only the four new tables and indexes; downgrade
drops only those Slice 3 objects.

- [ ] **Step 4: Implement locked publication and rollback**

The repository acquires the existing per-agent advisory lock, selects draft
and pointer `FOR UPDATE`, compares both expected values, validates ownership,
reuses or creates the digest version, updates the pointer and appends one event
before flush. Raise typed `DraftRevisionConflict`,
`ActiveVersionConflict` and `PublicationTargetNotFound` errors.

- [ ] **Step 5: Implement scoped key, subscription and outbox persistence**

Key rows accept only the caller-provided keyed hash, never raw material.
Subscription rows store a signing-key identifier, not a secret. Terminal
enqueue joins run → version → agent, selects active non-revoked matching
subscriptions, writes the sanitized payload and relies on the unique delivery
constraint for replay safety.

- [ ] **Step 6: Verify persistence invariants**

Run: `uv run pytest tests/integration/test_migrations.py tests/integration/test_publishing_repository.py tests/integration/test_webhook_outbox_repository.py -q`

Expected: migrations round-trip and all publication/outbox tests pass.

- [ ] **Step 7: Commit persistence**

```bash
git add libs/python/platform_store infra/migrations tests/integration
git commit -m "feat: persist immutable publication history" -m "Add the Slice 3 migration and scoped repositories for atomic publish and rollback operations, hashed API-key records, webhook subscriptions, and idempotent terminal deliveries.\n\nVerification: uv run pytest tests/integration/test_migrations.py tests/integration/test_publishing_repository.py tests/integration/test_webhook_outbox_repository.py -q."
```

### Task 3: Owner publishing service and credential lifecycle

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/__init__.py`
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/crypto.py`
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/models.py`
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/publishing.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/settings.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/main.py`
- Create: `apps/control-api/tests/test_publishing_api.py`
- Create: `apps/control-api/tests/test_api_keys.py`
- Create: `apps/control-api/tests/test_webhook_subscriptions.py`

**Interfaces:**
- Produces owner routes listed in the Slice 3 acceptance contract.
- Produces `ApiKeyAuthenticator.authenticate(raw: str, required_scope: ApiKeyScope) -> PublicPrincipal`.
- Produces `derive_webhook_secret(master_key: bytes, subscription_id: UUID) -> bytes`.
- Consumes repository interfaces from Task 2, owner `RequestScope`, existing CSRF/origin dependency and generated request/view models.

- [ ] **Step 1: Write failing crypto and API tests**

```python
def test_api_key_is_returned_once_and_persisted_as_hash(client, key_store):
    created = create_key(client, scopes=["runs:create"])
    assert created["secret"].startswith("uas_live_")
    row = key_store.only_row()
    assert created["secret"] not in row.key_hash
    listed = client.get(created["list_url"]).json()
    assert "secret" not in json.dumps(listed)


def test_stale_publish_is_atomic(owner_client, seeded_state):
    response = owner_client.post(
        "/api/v1/agents/calculator/publish",
        json={
            "expected_draft_revision": seeded_state.revision - 1,
            "expected_active_version_id": seeded_state.active_public_id,
        },
        headers=csrf_headers(owner_client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "draft_revision_conflict"
```

- [ ] **Step 2: Run focused service tests**

Run: `uv run pytest apps/control-api/tests/test_publishing_api.py apps/control-api/tests/test_api_keys.py apps/control-api/tests/test_webhook_subscriptions.py -q`

Expected: FAIL because the routes and service are absent.

- [ ] **Step 3: Implement separated cryptographic operations**

Generate 32 random secret bytes and an 8-byte visible prefix. Format API keys
as `uas_live_<prefix>_<base64url-secret>`. Hash with
`HMAC-SHA256(api_key_hash_master, raw_key)`, compare with
`hmac.compare_digest`, and update `last_used_at` only after successful scope,
expiry and revoke checks. Derive webhook secrets with an independent
HMAC-SHA256 master and domain separator `uas:webhook:v1:`.

- [ ] **Step 4: Implement publishing state and mutation service**

Map repository conflicts to stable 409 errors, validate the draft again before
publication, serialize versions and immutable ledger records, and return
absolute-path-neutral Published App/API paths. Do not reuse direct
AgentVersion import/activate routes for Publish UI.

- [ ] **Step 5: Implement key and webhook lifecycle routes**

Validate exact scopes and expiry bounds. Return raw key/signing secret only in
HTTP 201 create responses. Accept only `http`/`https` URLs with no userinfo or
fragment and an origin exactly present in `webhook_allowed_origins`. Revoke is
idempotent and owner/project/agent scoped.

- [ ] **Step 6: Wire fail-closed settings and rate limits**

Add required key-file settings for API-key hashing, browser capabilities and
webhook signing. Extend request guards to publish, key, webhook and public run
creation routes without applying Studio Origin rejection to bearer-key public
requests.

- [ ] **Step 7: Verify owner APIs and secret absence**

Run: `uv run pytest apps/control-api/tests/test_publishing_api.py apps/control-api/tests/test_api_keys.py apps/control-api/tests/test_webhook_subscriptions.py -q`

Expected: all focused tests pass.

- [ ] **Step 8: Commit owner publishing**

```bash
git add apps/control-api
git commit -m "feat: add owner publishing controls" -m "Expose compare-and-swap publish and rollback APIs plus one-time API-key and webhook subscription lifecycles with separated master secrets and exact origin policy.\n\nVerification: uv run pytest apps/control-api/tests/test_publishing_api.py apps/control-api/tests/test_api_keys.py apps/control-api/tests/test_webhook_subscriptions.py -q."
```

### Task 4: Sanitized public metadata, async/sync runs and resumable events

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/principals.py`
- Create: `apps/control-api/src/universal_agent_studio_api/publishing/public_service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/public.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/runs/service.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/runs/sse.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/main.py`
- Create: `apps/control-api/tests/test_public_agents.py`
- Create: `apps/control-api/tests/test_public_runs.py`
- Create: `apps/control-api/tests/test_public_sse.py`
- Create: `tests/security/test_public_isolation.py`

**Interfaces:**
- Produces the five `/public/v1` endpoints in the acceptance contract.
- Produces `issue_run_capability(run, expires_at) -> str` and
  `verify_run_capability(raw, run_id, agent_id) -> PublicPrincipal`.
- Consumes `ApiKeyAuthenticator`, `RunService`, `AgentVersionPersistence`,
  generated public models and existing sequence-based SSE formatter.

- [ ] **Step 1: Write failing sanitization, scope and resume tests**

```python
async def test_public_metadata_excludes_agent_spec_internals(public_client):
    response = await public_client.get("/public/v1/agents/calculator?locale=en-US")
    assert response.status_code == 200
    body = response.json()
    serialized = json.dumps(body, sort_keys=True)
    assert body["interface"]["mode"] == "form"
    for forbidden in ("prompt", "tools", "model_profiles", "agent_spec"):
        assert forbidden not in serialized


async def test_last_event_id_resumes_after_sequence(public_client, readable_run):
    response = await public_client.get(
        readable_run.events_url,
        headers={
            "Authorization": f"Bearer {readable_run.api_key}",
            "Last-Event-ID": "3",
        },
    )
    assert "id: 3" not in response.text
    assert "id: 4" in response.text
```

- [ ] **Step 2: Run focused public API tests**

Run: `uv run pytest apps/control-api/tests/test_public_agents.py apps/control-api/tests/test_public_runs.py apps/control-api/tests/test_public_sse.py tests/security/test_public_isolation.py -q`

Expected: FAIL because public authentication and routes are absent.

- [ ] **Step 3: Implement exact public principals**

Bearer lookup authenticates before agent/run existence is disclosed. Browser
capabilities use a versioned base64url envelope containing project, agent, run
and expiry plus HMAC-SHA256; verify structure, expiry and signature before
constructing a read-only run principal.

- [ ] **Step 4: Implement safe metadata and run projections**

Extract only localized metadata and `interface` from the active version.
Resolve active version immediately before create, validate public input, then
call the existing durable `RunService` with server-owned version identity.
Namespace idempotency by principal and agent.

- [ ] **Step 5: Implement async, bounded sync and public status**

Async create returns 202. Sync create polls the stored run until terminal or
`public_sync_wait_seconds`; terminal returns 200 and timeout returns 202 for
the same run. Public views translate internal failure data to stable safe error
codes and never include `durable_execution_id`.

- [ ] **Step 6: Reuse sequence persistence through a public sanitizer**

Parse `Last-Event-ID` as a bounded non-negative integer, list later events,
project them to allowed fields and keep existing heartbeat/terminal behavior.
Require `events:read` for API keys or the exact run capability.

- [ ] **Step 7: Verify isolation and public semantics**

Run: `uv run pytest apps/control-api/tests/test_public_agents.py apps/control-api/tests/test_public_runs.py apps/control-api/tests/test_public_sse.py tests/security/test_public_isolation.py -q`

Expected: sanitization, key scope, capability binding, idempotency, sync
continuation and reconnect tests pass.

- [ ] **Step 8: Commit public delivery APIs**

```bash
git add apps/control-api tests/security
git commit -m "feat: expose scoped public run APIs" -m "Add sanitized active-agent metadata, scoped bearer and run-capability principals, idempotent async and bounded sync invocation, and resumable public event streams.\n\nVerification: uv run pytest apps/control-api/tests/test_public_agents.py apps/control-api/tests/test_public_runs.py apps/control-api/tests/test_public_sse.py tests/security/test_public_isolation.py -q."
```

### Task 5: Signed terminal webhook outbox dispatcher

**Files:**
- Create: `workers/runtime/src/universal_agent_studio_runtime/webhooks/__init__.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/webhooks/signing.py`
- Create: `workers/runtime/src/universal_agent_studio_runtime/webhooks/dispatcher.py`
- Modify: `workers/runtime/src/universal_agent_studio_runtime/activities/events.py`
- Modify: `workers/runtime/src/universal_agent_studio_runtime/worker.py`
- Create: `workers/runtime/tests/test_webhook_signing.py`
- Create: `workers/runtime/tests/test_webhook_dispatcher.py`
- Modify: `workers/runtime/tests/test_workflow.py`
- Create: `tests/integration/test_terminal_webhook_delivery.py`

**Interfaces:**
- Produces `sign_webhook(secret, timestamp, body) -> str`.
- Produces `WebhookDispatcher.run(stop: asyncio.Event) -> None` and
  `dispatch_once() -> int`.
- Consumes Task 2 outbox methods, dedicated webhook master key, `httpx`
  already available in the workspace, and runtime terminal trace persistence.

- [ ] **Step 1: Write failing fixed-vector and retry tests**

```python
def test_webhook_signature_fixed_vector():
    signature = sign_webhook(
        b"k" * 32,
        1_753_392_000,
        b'{"delivery_id":"00000000-0000-0000-0000-000000000001"}',
    )
    assert signature == "v1=bdfe974410085c58ae53d60ff47fffed1bc06887ada3edc020e1a21af8c419b5"


async def test_redirect_is_permanent_failure(fake_transport, due_delivery):
    fake_transport.respond(status=302, headers={"location": "http://127.0.0.1/"})
    await dispatcher.dispatch_once()
    assert due_delivery.state == "failed"
    assert fake_transport.requests == 1
```

- [ ] **Step 2: Run focused worker tests**

Run: `uv run pytest workers/runtime/tests/test_webhook_signing.py workers/runtime/tests/test_webhook_dispatcher.py tests/integration/test_terminal_webhook_delivery.py -q`

Expected: FAIL because signing and dispatcher modules are absent.

- [ ] **Step 3: Enqueue terminal deliveries atomically**

In `SqlRuntimePersistence.finalize_trace`, use the same session and
transaction for `RunRepository.finalize_trace` and
`WebhookRepository.enqueue_terminal`. If trace replay returns the existing
identical trace, outbox unique constraints keep delivery creation idempotent.

- [ ] **Step 4: Implement canonical signing and bounded delivery**

Serialize compact sorted UTF-8 JSON once, sign
`str(timestamp).encode() + b"." + body`, set the three documented headers,
disable redirect following, use a short total timeout and read at most the
configured response byte limit. Classify 408/409/425/429/5xx and transport
errors as transient; other 3xx/4xx are permanent.

- [ ] **Step 5: Run dispatcher beside the Temporal worker**

Use `asyncio.TaskGroup` for the Temporal worker and dispatcher. Read the
dedicated master key with the existing minimum-length policy. On shutdown set
the stop event, cancel no in-flight database transaction, remove readiness and
dispose the engine.

- [ ] **Step 6: Verify terminal atomicity, signatures and retries**

Run: `uv run pytest workers/runtime/tests/test_webhook_signing.py workers/runtime/tests/test_webhook_dispatcher.py workers/runtime/tests/test_workflow.py tests/integration/test_terminal_webhook_delivery.py -q`

Expected: all focused tests pass with no network access.

- [ ] **Step 7: Commit webhook delivery**

```bash
git add workers/runtime tests/integration libs/python/platform_store
git commit -m "feat: deliver signed terminal webhooks" -m "Atomically enqueue sanitized terminal deliveries and dispatch exact-origin requests with fixed HMAC signatures, redirect denial, bounded I/O, idempotency, and retry classification.\n\nVerification: uv run pytest workers/runtime/tests/test_webhook_signing.py workers/runtime/tests/test_webhook_dispatcher.py workers/runtime/tests/test_workflow.py tests/integration/test_terminal_webhook_delivery.py -q."
```

### Task 6: Separate Published Web App

**Files:**
- Create: `apps/published-web/package.json`
- Create: `apps/published-web/next.config.ts`
- Create: `apps/published-web/tsconfig.json`
- Create: `apps/published-web/eslint.config.mjs`
- Create: `apps/published-web/vitest.config.ts`
- Create: `apps/published-web/src/app/layout.tsx`
- Create: `apps/published-web/src/app/globals.css`
- Create: `apps/published-web/src/app/[locale]/layout.tsx`
- Create: `apps/published-web/src/app/[locale]/agents/[agentId]/page.tsx`
- Create: `apps/published-web/src/components/PublicAgentApp.tsx`
- Create: `apps/published-web/src/lib/api.ts`
- Create: `apps/published-web/src/lib/i18n.ts`
- Create: `apps/published-web/src/messages/ru-RU.json`
- Create: `apps/published-web/src/messages/en-US.json`
- Create: `apps/published-web/tests/public-agent-app.test.tsx`
- Create: `apps/published-web/tests/accessibility.test.tsx`
- Create: `apps/published-web/tests/localization.test.ts`

**Interfaces:**
- Consumes Task 4 public metadata, async create, status and event routes plus generated TypeScript public contracts.
- Produces loopback route `/{locale}/agents/{agentId}` with no Studio imports, cookies or credentials.

- [ ] **Step 1: Load required UI design skills**

Read and apply `ui-ux-pro-max`, `ui-styling` and `design-system` before
defining the component and CSS changes. Keep the visual language related to
Studio while making the public product calmer and task-focused.

- [ ] **Step 2: Write failing public application tests**

```tsx
it("submits schema-derived input and announces the result", async () => {
  render(<PublicAgentApp agent={calculatorAgent} transport={transport} />);
  await user.type(screen.getByLabelText("Expression"), "19 * 23");
  await user.click(screen.getByRole("button", {name: "Run agent"}));
  expect(await screen.findByRole("status")).toHaveTextContent("437");
  expect(transport.create).toHaveBeenCalledWith({expression: "19 * 23"});
});
```

- [ ] **Step 3: Run the new app tests**

Run: `pnpm --filter @universal-agent-studio/published-web test`

Expected: FAIL because the workspace package is absent.

- [ ] **Step 4: Implement server metadata fetch and schema renderer**

Fetch only `/public/v1/agents/{agentId}` from the internal Control API. Render
form fields from `InterfaceSchema`, covering string, number, integer, boolean
and enum constraints used by the contract. Keep chat/hybrid containers
semantically correct without introducing a second behavior model.

- [ ] **Step 5: Implement public run state machine**

Use explicit `ready`, `submitting`, `running`, `completed` and `failed` states.
Store the returned capability only in component memory for the active run,
resume events using the last sequence, show sanitized errors and clear the
capability on restart/unmount.

- [ ] **Step 6: Implement responsive RU/EN visual system**

Use local CSS variables, system fonts, strong focus rings, 44-pixel controls,
single-column mobile layout, restrained technical accent, `aria-live="polite"`
status, reduced-motion media query and content that survives 200% zoom.

- [ ] **Step 7: Verify component, localization and accessibility suites**

Run: `pnpm --filter @universal-agent-studio/published-web check && pnpm --filter @universal-agent-studio/published-web test`

Expected: TypeScript, ESLint, localization and Vitest checks pass.

- [ ] **Step 8: Commit the separate public surface**

```bash
git add apps/published-web pnpm-lock.yaml
git commit -m "feat: add the Published Agent Web App" -m "Create a separate RU/EN, schema-driven public application with mobile-first accessible states and in-memory run capabilities, isolated from Studio sessions and debug surfaces.\n\nVerification: pnpm --filter @universal-agent-studio/published-web check; pnpm --filter @universal-agent-studio/published-web test."
```

### Task 7: Studio Publish workspace

**Files:**
- Create: `apps/studio-web/src/app/[locale]/agents/[agentId]/publish/page.tsx`
- Create: `apps/studio-web/src/features/publishing/PublishWorkspace.tsx`
- Create: `apps/studio-web/src/features/publishing/VersionLedger.tsx`
- Create: `apps/studio-web/src/features/publishing/CredentialPanel.tsx`
- Create: `apps/studio-web/src/features/publishing/WebhookPanel.tsx`
- Create: `apps/studio-web/src/features/publishing/types.ts`
- Modify: `apps/studio-web/src/components/AppShell.tsx`
- Modify: `apps/studio-web/src/lib/api/client.ts`
- Modify: `apps/studio-web/src/messages/ru-RU.json`
- Modify: `apps/studio-web/src/messages/en-US.json`
- Create: `apps/studio-web/tests/publish-workspace.test.tsx`
- Create: `apps/studio-web/tests/publish-accessibility.test.tsx`

**Interfaces:**
- Consumes Task 3 owner routes and generated owner publication contracts.
- Produces owner controls for v1/v2 publish, traffic rollback, one-time key and webhook secret display, and public URL/API examples.

- [ ] **Step 1: Write failing publication UI tests**

```tsx
it("publishes v2 then rolls traffic back to immutable v1", async () => {
  render(<PublishWorkspace initialState={v1State} api={api} />);
  await user.click(screen.getByRole("button", {name: "Publish revision 2"}));
  expect(await screen.findByText("Traffic: calculator-v2")).toBeVisible();
  await user.click(screen.getByRole("button", {name: "Switch traffic to calculator-v1"}));
  expect(await screen.findByText("Traffic: calculator-v1")).toBeVisible();
  expect(screen.getAllByRole("row", {name: /publish|rollback/})).toHaveLength(3);
});
```

- [ ] **Step 2: Run the focused Studio tests**

Run: `pnpm --filter @universal-agent-studio/studio-web test -- publish`

Expected: FAIL because the Publish workspace is absent.

- [ ] **Step 3: Implement publishing state and conflicts**

Load the owner state server-side and pass it to a client workspace. Mutations
send the displayed draft revision and active version. On 409, retain no
optimistic traffic change, refresh authoritative state and explain the
conflict in a focusable alert.

- [ ] **Step 4: Implement immutable history and rollback controls**

Show version number, digest prefix, created time, active badge and publication
event ledger. Rollback wording always says “switch traffic”; it never suggests
that v2 is deleted or edited.

- [ ] **Step 5: Implement one-time credential handling**

Create/list/revoke keys and subscriptions. Render the raw value only from the
immediate create response in an alert panel with copy and dismiss actions.
Never write it to URL, local storage, session storage or console.

- [ ] **Step 6: Add navigation, API examples and RU/EN copy**

Add a Publish navigation item for the current agent, an external link to port
3301 and curl examples containing `<YOUR_API_KEY>` rather than an issued
secret. Validate parity of all message keys.

- [ ] **Step 7: Verify Studio UI**

Run: `pnpm --filter @universal-agent-studio/studio-web check && pnpm --filter @universal-agent-studio/studio-web test`

Expected: existing and new Studio tests pass.

- [ ] **Step 8: Commit Studio publishing UX**

```bash
git add apps/studio-web
git commit -m "feat: add the Studio Publish workspace" -m "Add RU/EN owner controls for atomic publication, immutable version history, traffic rollback, one-time API keys, webhook subscriptions, and safe public examples.\n\nVerification: pnpm --filter @universal-agent-studio/studio-web check; pnpm --filter @universal-agent-studio/studio-web test."
```

### Task 8: Local stack, browser acceptance and security regression

**Files:**
- Modify: `infra/docker/compose.local.yml`
- Create: `infra/docker/published-web.Dockerfile`
- Modify: `infra/docker/.env.example`
- Modify: `scripts/local-common.mjs`
- Modify: `scripts/dev-local.mjs`
- Modify: `scripts/local-down.mjs`
- Modify: `scripts/local-reset.mjs`
- Modify: `package.json`
- Create: `apps/studio-web/e2e/publishing.spec.ts`
- Create: `apps/studio-web/e2e/public-agent.spec.ts`
- Create: `apps/studio-web/e2e/public-reconnect.spec.ts`
- Modify: `apps/studio-web/playwright.config.ts`
- Create: `tests/security/test_slice3_secret_absence.py`
- Modify: `tests/integration/test_local_stack.py`
- Modify: `.github/workflows/slice1.yml`

**Interfaces:**
- Produces one `pnpm dev:local` stack with healthy ports 3000, 3301 and 8000.
- Consumes all completed Slice 3 endpoints and surfaces.

- [ ] **Step 1: Write failing Compose and E2E expectations**

```python
def test_local_stack_contains_isolated_published_web(compose_config):
    service = compose_config["services"]["published-web"]
    assert service["ports"] == ["127.0.0.1:3301:3000"]
    assert "uas_session_hash_key" not in service.get("secrets", [])
    assert "uas_api_key_hash_key" not in service.get("secrets", [])
```

- [ ] **Step 2: Run repository and local-stack tests**

Run: `uv run pytest tests/repository tests/integration/test_local_stack.py -q`

Expected: FAIL because Published Web App and new secrets are not wired.

- [ ] **Step 3: Wire local secrets and services**

Generate separate ignored development key files, mount each only into the
process that needs it, allow both loopback Web origins where required, add the
Published Web App health check and add
`host.docker.internal:host-gateway` for the runtime worker. No service receives
the Studio session key unless it verifies Studio sessions.

- [ ] **Step 4: Expand root checks and CI**

Run both Web packages in `test:web` and `check`; build the second Docker image;
rename the workflow display name to Slice 1–3 Local Preview; keep deterministic
credentials and no external model/network dependency.

- [ ] **Step 5: Implement deterministic browser control journey**

Create v1, run `19 * 23` in the Published App, create/revoke a scoped key,
publish a changed v2, start a v2 run, switch traffic to v1 and assert old run
version identity plus three immutable ledger events. Repeat essential public
flow in both locales and at mobile viewport.

- [ ] **Step 6: Add reconnect, keyboard and secret scans**

Interrupt the public event request after sequence N and reconnect with
`Last-Event-ID`; assert no duplicate. Traverse the public form and Publish
screen by keyboard. Inspect local/session storage, rendered HTML, API snapshots,
database text columns and redacted logs for seeded raw secrets.

- [ ] **Step 7: Run full local verification**

Run:

```bash
pnpm check
pnpm test:contracts
pnpm test:web
pnpm test:python
pnpm test:e2e
docker compose --env-file infra/docker/.env.example -f infra/docker/compose.local.yml config --quiet
```

Expected: every command exits 0.

- [ ] **Step 8: Commit local acceptance**

```bash
git add infra scripts package.json pnpm-lock.yaml apps/studio-web/e2e apps/studio-web/playwright.config.ts tests .github/workflows/slice1.yml
git commit -m "test: prove Slice 3 end to end" -m "Wire the isolated Published Web App and separated local secrets, extend CI, and cover the deterministic publish-run-v2-rollback journey, reconnect, keyboard access, isolation, and secret absence.\n\nVerification: pnpm check; pnpm test:contracts; pnpm test:web; pnpm test:python; pnpm test:e2e; docker compose config --quiet."
```

### Task 9: Documentation, visual evidence and release gate

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `DESIGN.md`
- Modify: `SECURITY.md`
- Modify: `LOCALIZATION.md`
- Modify: `ROADMAP.md`
- Modify: `docs/ARCHITECTURAL_INVARIANTS.md`
- Modify: `docs/CONTRACTS.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/operations/LOCAL_PREVIEW.md`
- Create: `docs/acceptance/evidence/SLICE_3.md`
- Modify: `README.md` only if the README audit finds shipped setup, architecture or proof changes.
- Create or modify: `assets/readme/slice3-publish.png` only when a deterministic shipped-state screenshot improves README proof.

**Interfaces:**
- Consumes fresh acceptance outputs and exact commands from Tasks 1–8.
- Produces source-grounded operator and contributor documentation.

- [ ] **Step 1: Run the mandatory README audit skill**

Read and apply `beautify-github-readme` in audit mode against the finished
branch. Update the README only for facts changed by Slice 3; do not claim
Internet readiness.

- [ ] **Step 2: Update architecture, security and operations**

Document the public/Studio privilege split, active traffic pointer, separate
secret files, key rotation/revocation, webhook allowlist and retry behavior,
ports, reset/recovery and exact local verification commands.

- [ ] **Step 3: Record fresh acceptance evidence**

Capture exact test counts, clean startup health, v1/v2 identifiers and digests,
post-rollback pointer, immutable row fingerprints, ledger sequence and
secret-scan result. Link commands and evidence without embedding credentials.

- [ ] **Step 4: Validate docs and repository**

Run:

```bash
git diff --check
pnpm check
pnpm test:contracts
pnpm test:web
pnpm test:python
pnpm test:e2e
```

Expected: clean diff formatting and all suites pass from the finished branch.

- [ ] **Step 5: Commit documentation and proof**

```bash
git add ARCHITECTURE.md DESIGN.md SECURITY.md LOCALIZATION.md ROADMAP.md docs README.md assets/readme
git commit -m "docs: document Slice 3 public delivery" -m "Align architecture, threat model, local operations, roadmap, README, and fresh acceptance evidence with the shipped immutable publishing and public-delivery behavior.\n\nVerification: git diff --check; pnpm check; pnpm test:contracts; pnpm test:web; pnpm test:python; pnpm test:e2e."
```

### Task 10: Independent review, merge and exact-SHA CI

**Files:**
- Modify: only files required to remediate validated review findings.

**Interfaces:**
- Consumes the complete Slice 3 branch and its acceptance evidence.
- Produces a reviewed `main` commit with a green exact-SHA GitHub Actions run.

- [ ] **Step 1: Request independent code review**

Use `requesting-code-review`. A narrow review subagent may inspect correctness,
architecture, security, tenancy, webhook egress, UX/accessibility, tests and
documentation, but the primary agent performs all remediation.

- [ ] **Step 2: Triage and remediate findings**

Use `receiving-code-review`; reproduce each actionable issue with a focused
failing test, implement the smallest fix, run the focused and affected
regression suites, and commit with a detailed message.

- [ ] **Step 3: Run verification-before-completion**

From a clean branch state run the full Task 9 release commands plus
`git status --short`, migration round-trip and `docker compose config --quiet`.
Record fresh outputs rather than relying on earlier runs.

- [ ] **Step 4: Merge and push**

Use `finishing-a-development-branch`. Fast-forward or merge the reviewed
branch into `main` without rewriting unrelated user work, push `main`, and
record the exact pushed SHA.

- [ ] **Step 5: Verify GitHub Actions for the exact SHA**

Inspect the workflow run attached to that SHA until terminal. If it fails, use
`github:gh-fix-ci`, reproduce the failure locally, fix on a fresh branch,
repeat the complete affected verification and push the corrected `main`.

- [ ] **Step 6: Clean up and close the persistent goal**

Remove only the finished Slice 3 worktree/branch after merge and exact-SHA CI
success. Mark the goal complete only when every completion-contract item has
fresh evidence and report final goal token/time usage.

## Self-review result

- Spec coverage: every goal, exclusion, public principal, publishing
  transaction, public route, webhook rule, UI requirement, security check and
  release boundary maps to Tasks 1–10.
- Placeholder scan: no incomplete implementation marker or unspecified error
  handling remains.
- Type consistency: public/owner generated type names, repository method names,
  scope enums, capability binding and endpoint paths are consistent across
  producer and consumer tasks.
- Scope check: contracts/persistence, owner API, public API, webhook worker,
  Published Web App, Studio UX and local acceptance are distinct reviewer
  gates but together form one inseparable v1 → v2 → v1 vertical slice.
