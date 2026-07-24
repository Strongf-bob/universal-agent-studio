# Slice 2: One Spec, Two Editors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one durable AgentSpec draft edited through Simple Settings and a React Flow canvas/inspector, with validation, accessible graph editing, safe bulk diff preview and draft-snapshot test runs.

**Architecture:** PostgreSQL stores one project-scoped draft per agent using whole-document optimistic concurrency. AgentSpec remains the only semantic document while layout is stored separately; the Web owns a single editor reducer and projects it to simple, canvas, table and inspector views. Draft tests create immutable unactivated AgentVersion snapshots and reuse the existing durable runtime.

**Tech Stack:** JSON Schema 2020-12, generated Pydantic/TypeScript types, Python 3.14, FastAPI, SQLAlchemy/PostgreSQL/Alembic, Next.js 16, React 19, React Flow 12, next-intl, Vitest, Playwright, pytest and Temporal.

## Global Constraints

- `AgentSpec` is the only source of runtime semantics.
- React Flow types stop at the browser projection adapter.
- Invalid or secret-bearing AgentSpec candidates are never persisted.
- Draft writes use complete documents plus an exact `expected_revision`.
- Layout changes never change the AgentSpec digest.
- Draft test runs never change the active-version pointer.
- Browser writes require the existing owner session, Origin allowlist and CSRF token.
- Candidate AgentSpec bodies are limited to 1 MiB.
- All user-visible copy has `ru-RU` and `en-US` translation keys.
- All editing and test actions have loading, disabled, success and recoverable error states.
- The graph has a keyboard-accessible table editor; color is never the only state signal.
- Existing Slice 1 tests and the clean-checkout `pnpm dev:local` command remain green.

---

## File and responsibility map

### Canonical contracts

- `contracts/schemas/v0.1.0/agent-draft.schema.json` — canonical draft response including AgentSpec and presentation layout.
- `contracts/examples/v0.1.0/valid/agent.draft.calculator.json` — complete cross-language valid fixture.
- `contracts/examples/v0.1.0/invalid/agent.draft.dangling-layout-node.json` — semantic negative fixture.
- `contracts/examples/v0.1.0/manifest.json` — shared Python/TypeScript conformance cases.
- `libs/python/agent_kernel/src/universal_agent_kernel/contracts/validation.py` — precise AgentSpec node issues and AgentDraft layout invariants.
- `contracts/conformance/src/invariants.ts` — TypeScript equivalent of draft invariants.
- Generated Python and TypeScript files — generator output only.

### Persistence and API

- `infra/migrations/versions/0002_slice2_agent_drafts.py` — draft table and constraints.
- `libs/python/platform_store/src/universal_agent_platform_store/models.py` — `AgentDraftRecord`.
- `libs/python/platform_store/src/universal_agent_platform_store/repositories/drafts.py` — scoped create/get/CAS update.
- `apps/control-api/src/universal_agent_studio_api/agents/drafts.py` — request, response and persistence protocols.
- `apps/control-api/src/universal_agent_studio_api/agents/draft_service.py` — validation, digest, layout checks and diff behavior.
- `apps/control-api/src/universal_agent_studio_api/api/agent_drafts.py` — owner-scoped HTTP routes.
- `apps/control-api/src/universal_agent_studio_api/runs/service.py` — explicit run path for a resolved unactivated snapshot.
- `apps/control-api/src/universal_agent_studio_api/main.py` — service construction and router registration.

### Web

- `apps/studio-web/src/features/drafts/types.ts` — narrow editor types derived from generated contracts.
- `apps/studio-web/src/features/drafts/editor-state.ts` — pure reducer and immutable pointer updates.
- `apps/studio-web/src/features/drafts/projection.ts` — AgentSpec/layout to React Flow view models and run highlighting.
- `apps/studio-web/src/features/drafts/DraftWorkspace.tsx` — one state owner and orchestration.
- `SimpleSettings.tsx`, `DraftCanvas.tsx`, `DraftGraphTable.tsx`, `NodeInspector.tsx`, `BulkDiffPanel.tsx`, `DraftTestConsole.tsx` — focused projections.
- `apps/studio-web/src/app/[locale]/agents/[agentId]/build/page.tsx` — authenticated route.
- `apps/studio-web/src/lib/api/client.ts` — typed draft and test-run API functions.
- locale messages and `globals.css` — RU/EN and responsive workbench.

### Acceptance

- API/unit/integration/security tests close each boundary.
- `apps/studio-web/e2e/draft-editor.spec.ts` closes the visible control scenario.
- `docs/acceptance/evidence/SLICE_2.md` records exact final results only after verification.

---

### Task 1: Canonical AgentDraft contract and precise validation

**Files:**
- Create: `contracts/schemas/v0.1.0/agent-draft.schema.json`
- Create: `contracts/examples/v0.1.0/valid/agent.draft.calculator.json`
- Create: `contracts/examples/v0.1.0/invalid/agent.draft.dangling-layout-node.json`
- Modify: `contracts/examples/v0.1.0/manifest.json`
- Modify: `libs/python/agent_kernel/src/universal_agent_kernel/contracts/validation.py`
- Modify: `contracts/conformance/src/invariants.ts`
- Modify: generated contract files through `pnpm generate:contracts`
- Test: `tests/contracts/test_authoring_contracts.py`
- Test: `contracts/conformance/tests/contracts.test.ts`

**Interfaces:**
- Produces: generated `AgentDraft` type with `agent_spec`, `layout`, `revision`, `digest` and `base_version_id`.
- Produces: `validate_agent_draft(document) -> ValidationResult`.
- Produces: precise AgentSpec semantic issues with node-specific JSON Pointers.
- Consumes: existing canonical AgentSpec and common identifier/digest definitions.

- [x] **Step 1: Write failing Python and TypeScript conformance tests**

Add assertions that the valid draft passes, a layout node named
`unknown-node` produces `dangling_layout_node_reference`, and a dangling model
reference reports:

```python
assert issue.code == "dangling_model_profile_reference"
assert issue.json_pointer == "/nodes/1/model_profile_ref"
assert issue.node_id == "planner-model"
```

Run:

```bash
uv run pytest tests/contracts/test_authoring_contracts.py -q
pnpm test:contracts
```

Expected: failure because AgentDraft is not registered and semantic issues do
not yet have precise pointers.

- [x] **Step 2: Add the canonical schema**

Define:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.universal-agent.studio/v0.1.0/agent-draft.schema.json",
  "title": "AgentDraft",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "draft_id",
    "agent_id",
    "revision",
    "base_version_id",
    "digest",
    "agent_spec",
    "layout",
    "updated_at"
  ],
  "properties": {
    "schema_version": {"const": "0.1.0"},
    "draft_id": {"$ref": "common.schema.json#/$defs/identifier"},
    "agent_id": {"$ref": "common.schema.json#/$defs/identifier"},
    "revision": {"type": "integer", "minimum": 1},
    "base_version_id": {"$ref": "common.schema.json#/$defs/identifier"},
    "digest": {"$ref": "common.schema.json#/$defs/sha256"},
    "agent_spec": {"$ref": "agent-spec.schema.json"},
    "layout": {"$ref": "#/$defs/layout"},
    "updated_at": {"type": "string", "format": "date-time"}
  }
}
```

The `layout` definition permits at most 256 unique node entries with finite
JSON numbers and a viewport zoom from `0.1` through `4`.

- [x] **Step 3: Add valid and invalid fixtures**

Build the valid fixture from the calculator AgentSpec with deterministic
positions:

```json
[
  {"node_id": "user-input", "x": 0, "y": 80},
  {"node_id": "planner-model", "x": 260, "y": 80},
  {"node_id": "calculator-tool", "x": 520, "y": 80},
  {"node_id": "structured-output", "x": 780, "y": 80}
]
```

The invalid fixture copies it and replaces `structured-output` with
`unknown-node`. Add both cases to the manifest.

- [x] **Step 4: Implement cross-language semantic invariants**

Python:

```python
def validate_agent_draft(document: dict[str, Any]) -> ValidationResult:
    issues = _schema_issues(document, "agent-draft.schema.json")
    agent_spec = document.get("agent_spec")
    if isinstance(agent_spec, dict):
        issues.extend(validate_agent_spec(agent_spec).issues)
        node_ids = {
            node.get("id")
            for node in agent_spec.get("nodes", [])
            if isinstance(node, dict)
        }
        seen: set[str] = set()
        for index, item in enumerate(document.get("layout", {}).get("nodes", [])):
            node_id = item.get("node_id") if isinstance(item, dict) else None
            if node_id in seen:
                issues.append(_issue("duplicate_layout_node_id", f"/layout/nodes/{index}/node_id", node_id))
            elif isinstance(node_id, str) and node_id not in node_ids:
                issues.append(_issue("dangling_layout_node_reference", f"/layout/nodes/{index}/node_id", node_id))
            if isinstance(node_id, str):
                seen.add(node_id)
    return _ordered_result(issues)
```

Implement the same two codes in `invariants.ts`. Refactor AgentSpec graph
validation to emit `ValidationIssue` objects for model, tool, node and port
references rather than a pointerless set of codes.

- [x] **Step 5: Regenerate and prove parity**

Run:

```bash
pnpm generate:contracts
pnpm check:generated
uv run pytest tests/contracts -q
pnpm test:contracts
```

Expected: all contract tests pass and generated files are clean.

- [x] **Step 6: Commit**

```bash
git add contracts libs/python/agent_kernel contracts/conformance tests/contracts
git commit -m "feat: define canonical agent drafts"
```

---

### Task 2: Project-scoped optimistic draft persistence

**Files:**
- Create: `infra/migrations/versions/0002_slice2_agent_drafts.py`
- Create: `libs/python/platform_store/src/universal_agent_platform_store/repositories/drafts.py`
- Modify: `libs/python/platform_store/src/universal_agent_platform_store/models.py`
- Modify: `libs/python/platform_store/src/universal_agent_platform_store/repositories/__init__.py`
- Test: `tests/integration/test_draft_repository.py`
- Test: `tests/integration/test_migrations.py`

**Interfaces:**
- Produces: `DraftRepository.create_from_active(agent_key, layout)`.
- Produces: `DraftRepository.get(agent_key)`.
- Produces: `DraftRepository.update(agent_key, expected_revision, agent_spec, digest, layout)`.
- Produces: `DraftRevisionConflict` and `DraftNotFound`.
- Consumes: `RequestScope`, `Agent`, `AgentVersion`, `AgentActiveVersion`.

- [x] **Step 1: Write failing repository integration tests**

Cover:

```python
draft, created = await repository.create_from_active("calculator-agent", layout)
assert created is True
assert draft.revision == 1
assert draft.agent_spec == active.agent_spec

same, created = await repository.create_from_active("calculator-agent", layout)
assert created is False
assert same.id == draft.id

updated = await repository.update(
    "calculator-agent",
    expected_revision=1,
    agent_spec=changed_spec,
    digest=content_digest(changed_spec),
    layout=layout,
)
assert updated.revision == 2

with pytest.raises(DraftRevisionConflict):
    await repository.update(
        "calculator-agent",
        expected_revision=1,
        agent_spec=changed_spec,
        digest=content_digest(changed_spec),
        layout=layout,
    )
```

Add a foreign-project assertion returning no row.

Run with the isolated PostgreSQL command used by existing integration tests.
Expected: import/table failures.

- [x] **Step 2: Add the migration and model**

Create `agent_drafts` with:

```python
sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
sa.Column("base_version_id", postgresql.UUID(as_uuid=True), nullable=False),
sa.Column("revision", sa.Integer(), nullable=False),
sa.Column("digest", sa.String(length=64), nullable=False),
sa.Column("agent_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
sa.Column("updated_by_owner_id", postgresql.UUID(as_uuid=True), nullable=True),
sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
```

Add workspace/project indexes, scoped foreign keys, a positive-revision check
and a 64-character digest check. Upgrade from `0001` and clean upgrade must
both reach `0002`; downgrade drops only `agent_drafts`.

- [x] **Step 3: Implement repository locking and CAS**

Creation acquires the same scoped agent advisory lock used by version import,
loads the active version and inserts only when absent. Update locks the scoped
row with SQLAlchemy's `with_for_update()`, compares the exact revision and sets:

```python
record.agent_spec = agent_spec
record.digest = digest
record.layout = layout
record.revision += 1
record.updated_by_owner_id = self.scope.owner_id
record.updated_at = utc_now()
```

Every query includes workspace and project predicates.

- [x] **Step 4: Run persistence gates**

```bash
uv run pytest tests/integration/test_draft_repository.py tests/integration/test_migrations.py -q
uv run ruff check libs/python/platform_store tests/integration
uv run mypy libs/python/platform_store tests/integration
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add infra/migrations libs/python/platform_store tests/integration
git commit -m "feat: persist optimistic agent drafts"
```

---

### Task 3: Draft validation, save and non-mutating diff API

**Files:**
- Create: `apps/control-api/src/universal_agent_studio_api/agents/drafts.py`
- Create: `apps/control-api/src/universal_agent_studio_api/agents/draft_service.py`
- Create: `apps/control-api/src/universal_agent_studio_api/api/agent_drafts.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/main.py`
- Test: `apps/control-api/tests/test_agent_drafts.py`
- Test: `tests/integration/test_agent_draft_api.py`
- Test: `tests/security/test_draft_isolation.py`

**Interfaces:**
- Produces: `AgentDraftView`, `UpdateAgentDraftRequest`, `DraftDiffRequest`, `DraftDiffView`.
- Produces: `DraftService.create`, `get`, `update`, `preview_diff`.
- Consumes: generated AgentDraft, `validate_agent_spec`, canonical digest, redaction policy and `DraftRepository`.

- [x] **Step 1: Write failing service/API tests**

Test:

- create is 201, repeat is 200 without reset;
- get returns the same revision/digest/layout;
- semantic update changes digest and revision;
- layout-only update changes revision but not digest;
- invalid candidate returns `agent_spec_invalid` with field/node locations;
- stale update returns `agent_draft_revision_conflict`;
- preview is sorted, non-mutating and redacted;
- secret candidate returns no candidate/diff value;
- all writes require CSRF.

Run:

```bash
uv run pytest apps/control-api/tests/test_agent_drafts.py -q
```

Expected: route/module failures.

- [x] **Step 2: Define request and response models**

Use strict Pydantic models:

```python
class UpdateAgentDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    agent_spec: dict[str, Any]
    layout: DraftLayoutView

class DraftDiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    candidate_agent_spec: dict[str, Any]

class DraftDiffOperationView(BaseModel):
    op: Literal["add", "remove", "replace"]
    json_pointer: str
    before: Any | None = None
    after: Any | None = None
```

Reject layout node duplicates, missing AgentSpec nodes, non-finite coordinates
and more than 256 nodes.

- [x] **Step 3: Implement application validation and deterministic diff**

Before persistence:

```python
validation = validate_agent_spec(candidate)
if not validation.valid:
    raise ApiError(
        422,
        "agent_spec_invalid",
        details={"validation": validation_view(validation)},
    )
digest = content_digest(candidate)
```

Recursive diff rules:

- dictionaries compare sorted union of keys;
- arrays are replaced as a whole when unequal;
- scalars use `replace`;
- added/removed values use `add`/`remove`;
- escape `~` and `/` in pointers;
- pass values through `DefaultRedactionPolicy`;
- sort by `(json_pointer, op)`.

Check `expected_revision` before calculating or returning the diff so a stale
preview cannot be applied as if current.

- [x] **Step 4: Register authenticated routes**

All POST/PUT routes depend on `csrf_authenticated_owner`; GET depends on
`authenticated_owner`. Derive `RequestScope` from `AuthenticatedOwner`.
Map create response to 201 only on first creation.

- [x] **Step 5: Prove API and security boundaries**

```bash
uv run pytest apps/control-api/tests/test_agent_drafts.py tests/integration/test_agent_draft_api.py tests/security/test_draft_isolation.py -q
pnpm check
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add apps/control-api tests/integration tests/security
git commit -m "feat: expose safe agent draft editing"
```

---

### Task 4: Immutable draft snapshots and durable Test Console runs

**Files:**
- Modify: `apps/control-api/src/universal_agent_studio_api/agents/models.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/agents/service.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/agents/draft_service.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/api/agent_drafts.py`
- Modify: `apps/control-api/src/universal_agent_studio_api/runs/service.py`
- Modify: `libs/python/platform_store/src/universal_agent_platform_store/repositories/agents.py`
- Test: `apps/control-api/tests/test_draft_runs.py`
- Test: `tests/integration/test_draft_run_temporal.py`
- Test: `tests/security/test_draft_isolation.py`

**Interfaces:**
- Produces: provenance-aware `import_version(agent_spec, digest, provenance)`.
- Produces: `RunService.create_resolved_run(request, scope, version)`.
- Produces: `DraftService.create_test_run(agent_id, request, scope)`.
- Consumes: current draft revision, existing idempotent run persistence and Temporal adapter.

- [x] **Step 1: Write failing snapshot-run tests**

Arrange active v1 and draft revision 2, then:

```python
before = await versions.get_active_for_agent(
    scope=scope,
    agent_id="calculator-agent",
)
created = await drafts.create_test_run(
    agent_id="calculator-agent",
    request=DraftTestRunRequest(
        expected_revision=2,
        request_id=request_id,
        idempotency_key="draft-test-00000001",
        input={"question": "What is 19 × 23?"},
        locale="en-US",
    ),
    scope=scope,
)
after = await versions.get_active_for_agent(
    scope=scope,
    agent_id="calculator-agent",
)
assert before == after
assert created.status == "queued"
```

Await the trace and assert its version digest equals the draft digest. Repeat
the request and assert the same run id.

- [x] **Step 2: Make version import provenance-aware**

Extend persistence protocols with:

```python
provenance: dict[str, Any] | None = None
```

Pass it through to `AgentRepository.import_version`. For draft tests use:

```python
{
    "kind": "draft-test-snapshot",
    "draft_id": draft.public_id,
    "draft_revision": draft.revision,
    "draft_digest": draft.digest,
}
```

Existing import behavior passes `{}` and remains unchanged.

- [x] **Step 3: Refactor RunService without weakening the public route**

Keep `create_run()` active-only. Extract:

```python
async def create_resolved_run(
    self,
    request: CreateRunRequest,
    scope: RequestScope,
    version: StoredAgentVersion,
) -> CreateRunView:
    return await self._create_validated_run(request, scope, version)
```

It verifies identifier/digest against the supplied version, validates input,
persists idempotently and starts the durable execution exactly as before.
`create_run()` resolves an active version then delegates.

- [x] **Step 4: Add the draft run endpoint**

`POST /api/v1/agents/{agent_id}/draft/runs`:

- requires CSRF;
- verifies expected revision;
- imports/reuses the current spec without activation;
- builds canonical `CreateRunRequest` from the snapshot id/digest;
- calls `create_resolved_run`;
- returns the existing `CreateRunView`.

- [x] **Step 5: Run durable regression gates**

```bash
uv run pytest apps/control-api/tests/test_draft_runs.py tests/integration/test_draft_run_temporal.py tests/integration/test_run_api_temporal.py workers/runtime/tests -q
uv run pytest apps/control-api/tests/test_runs_api.py -q
pnpm check
```

Expected: draft and active run paths pass.

- [x] **Step 6: Commit**

```bash
git add apps/control-api libs/python/platform_store tests workers/runtime
git commit -m "feat: run immutable draft snapshots"
```

---

### Task 5: Single browser editor state and product-owned projections

**Files:**
- Create: `apps/studio-web/src/features/drafts/types.ts`
- Create: `apps/studio-web/src/features/drafts/editor-state.ts`
- Create: `apps/studio-web/src/features/drafts/projection.ts`
- Modify: `apps/studio-web/src/lib/api/client.ts`
- Test: `apps/studio-web/tests/draft-editor-state.test.ts`
- Test: `apps/studio-web/tests/draft-projection.test.ts`
- Test: `apps/studio-web/tests/draft-api.test.ts`

**Interfaces:**
- Produces: `DraftEditorState` and `DraftEditorAction`.
- Produces: `draftEditorReducer`, `replaceAtPointer`, `issuesByNode`, `issuesByPointer`.
- Produces: `projectDraftToFlow`, `statusByNode`.
- Produces: typed API functions for create/get/update/diff/test-run.
- Consumes: generated AgentDraft and existing RunEvent/Run types.

- [ ] **Step 1: Write failing pure-state tests**

Prove:

```ts
const renamed = replaceAtPointer(spec, "/localized_metadata/name/en-US", "Math Agent");
expect(renamed).not.toBe(spec);
expect(spec.localized_metadata.name["en-US"]).toBe("Calculator Agent");

const selected = draftEditorReducer(loaded, {type: "select-node", nodeId: "planner-model"});
expect(selected.agentSpec).toBe(loaded.agentSpec);
expect(selected.selectedNodeId).toBe("planner-model");
```

Also test layout movement leaves the AgentSpec object unchanged, save success
replaces server state, validation grouping, and run status precedence.

- [ ] **Step 2: Implement reducer and immutable pointer helper**

Reducer actions:

```ts
type DraftEditorAction =
  | {type: "semantic-edit"; pointer: string; value: unknown}
  | {type: "move-node"; nodeId: string; position: {x: number; y: number}}
  | {type: "set-viewport"; viewport: DraftViewport}
  | {type: "select-node"; nodeId: string}
  | {type: "save-started"}
  | {type: "save-succeeded"; draft: AgentDraft}
  | {type: "save-failed"; issues: ValidationIssue[]; code: string}
  | {type: "run-event"; event: RunEvent}
  | {type: "run-reset"};
```

Never use local/session storage.

- [ ] **Step 3: Implement the projection boundary**

`projectDraftToFlow` returns first-party `DraftFlowNode`/`DraftFlowEdge`
objects. Only `DraftCanvas.tsx` will convert them to React Flow types. Fallback
positions use stable horizontal spacing. Labels come from the selected locale
with default-locale fallback.

`statusByNode` maps `node.started` to running, terminal node events to their
status and untouched nodes to pending.

- [ ] **Step 4: Add typed API functions**

Add:

```ts
createAgentDraft(agentId, csrfToken)
getAgentDraft(agentId, cookie?)
updateAgentDraft(agentId, request, csrfToken)
previewAgentDraftDiff(agentId, request, csrfToken)
createDraftTestRun(agentId, request, csrfToken)
```

All browser writes use `credentials: "same-origin"` and the existing CSRF
header helper. API errors retain code, request id and validation details.

- [ ] **Step 5: Run Web unit gates**

```bash
pnpm --filter @universal-agent-studio/studio-web test -- draft-editor-state draft-projection draft-api
pnpm --filter @universal-agent-studio/studio-web check
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/studio-web/src/features/drafts apps/studio-web/src/lib/api/client.ts apps/studio-web/tests
git commit -m "feat: add canonical draft editor state"
```

---

### Task 6: Responsive Simple Settings, canvas, inspector, table and bulk diff

**Files:**
- Create: `apps/studio-web/src/app/[locale]/agents/[agentId]/build/page.tsx`
- Create: `apps/studio-web/src/features/drafts/DraftWorkspace.tsx`
- Create: `apps/studio-web/src/features/drafts/SimpleSettings.tsx`
- Create: `apps/studio-web/src/features/drafts/DraftCanvas.tsx`
- Create: `apps/studio-web/src/features/drafts/DraftGraphTable.tsx`
- Create: `apps/studio-web/src/features/drafts/NodeInspector.tsx`
- Create: `apps/studio-web/src/features/drafts/BulkDiffPanel.tsx`
- Create: `apps/studio-web/src/features/drafts/DraftTestConsole.tsx`
- Modify: `apps/studio-web/src/components/AppShell.tsx`
- Modify: `apps/studio-web/src/app/globals.css`
- Modify: `apps/studio-web/src/messages/en-US.json`
- Modify: `apps/studio-web/src/messages/ru-RU.json`
- Test: `apps/studio-web/tests/draft-workspace.test.tsx`
- Test: `apps/studio-web/tests/draft-accessibility.test.tsx`
- Test: `apps/studio-web/tests/localization.test.ts`

**Interfaces:**
- Produces: visible `/{locale}/agents/{agentId}/build` user journey.
- Consumes: one reducer state, pure projections and typed API calls from Task 5.
- Consumes: existing SSE/run client behavior without duplicating persistence.

- [ ] **Step 1: Load UI design skills before implementation**

Read and apply `ui-ux-pro-max`, `ui-styling` and `design-system`. Extend the
existing semantic tokens; do not redesign the established Slice 1 shell or
copy an external editor.

- [ ] **Step 2: Write failing component and accessibility tests**

Test:

- Simple Settings and Inspector display values from the same draft;
- edits mark the shared toolbar dirty;
- selecting `planner-model` in the table opens the same inspector as canvas;
- arrow controls move a layout node by 24 px;
- validation summary links to a field/node;
- preview shows changes but Apply is a separate button;
- loading, conflict, error and saved states are announced;
- every tab/button/input has an accessible name in both locales.

Run:

```bash
pnpm --filter @universal-agent-studio/studio-web test -- draft-workspace draft-accessibility localization
```

Expected: component modules are missing.

- [ ] **Step 3: Implement the route and single state owner**

The server page authenticates by fetching the draft; if absent it renders a
client workspace that creates it once. Redirect authentication errors to
login and missing active versions to import.

`DraftWorkspace` owns:

```tsx
const [state, dispatch] = useReducer(draftEditorReducer, initialDraftState(draft));
```

Children receive values and callbacks only. Save sends the whole candidate and
layout with `expectedRevision`.

- [ ] **Step 4: Implement Simple Settings and Inspector**

Simple Settings maps exact pointers for two locale names/descriptions, default
locale and model temperature.

Inspector locates the selected node by id and maps exact pointers for
localized metadata, planner prompt, model-profile reference, timeout and
retry count. Render node-specific issues adjacent to the appropriate field and
in a summary.

- [ ] **Step 5: Implement React Flow and accessible table**

`DraftCanvas` converts first-party projection values to React Flow nodes and
edges at the component boundary. It supports selection, drag, pan, zoom and
fit; it does not connect/delete nodes.

`DraftGraphTable` lists node, kind, validation and run status and provides:

```text
Select · Move left · Move right · Move up · Move down
```

Each movement is 24 px and updates the same layout state.

- [ ] **Step 6: Implement safe bulk preview and apply**

Use a labelled native textarea for complete JSON. Preview calls the API and
renders a table with operation, pointer, before and after. Apply parses the
same candidate and calls ordinary save using the previewed revision. On
conflict clear preview and require a new one.

- [ ] **Step 7: Implement Test Console and run highlighting**

Input comes from `agentSpec.interface.input_fields`. On submit, create the
draft run and connect to the existing SSE endpoint. Dispatch each event to the
editor reducer; show terminal structured output and a localized trace link.
Do not write run/draft state to browser storage.

- [ ] **Step 8: Implement responsive styles and RU/EN**

Add semantic editor tokens and media queries:

- desktop three-column workbench at 1024 px;
- switchable panel at 768–1023 px;
- tabbed single-column mode below 768 px;
- 44 px controls, visible focus and no nested inaccessible scrolling;
- table primary and canvas optional below 768 px;
- `prefers-reduced-motion` disables status transitions.

Add matching keys to both locale files and a test that their recursive key
sets are equal.

- [ ] **Step 9: Run Web checks**

```bash
pnpm test:web
pnpm --filter @universal-agent-studio/studio-web check
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add apps/studio-web
git commit -m "feat: build the dual-view draft workspace"
```

---

### Task 7: Browser, recovery and security acceptance

**Files:**
- Create: `apps/studio-web/e2e/draft-editor.spec.ts`
- Modify: `apps/studio-web/e2e/setup.fixture.ts`
- Modify: `apps/studio-web/e2e/helpers.ts`
- Create: `tests/integration/test_draft_recovery.py`
- Modify: `tests/security/test_secret_absence.py`
- Modify: `.github/workflows/slice1.yml`

**Interfaces:**
- Produces: deterministic visible Slice 2 release gate.
- Consumes: clean local stack, golden calculator fixture and existing setup owner.

- [ ] **Step 1: Write the failing browser control scenario**

The E2E:

1. completes owner setup/import when needed;
2. opens Build and creates the draft;
3. changes EN agent name in Simple Settings;
4. selects planner through the table and changes prompt;
5. moves the node and saves;
6. reloads and proves fields/layout/revision;
7. enters a dangling model reference, observes node-local error, then repairs;
8. previews a two-field bulk candidate and proves no mutation before Apply;
9. applies and saves;
10. starts the deterministic run;
11. observes running/completed textual node states and `{"value":437}`;
12. opens the stored trace;
13. switches locale without changing revision/run identity.

Add a keyboard-only narrow-viewport variant for table selection and movement.

- [ ] **Step 2: Add recovery and secret tests**

Integration test stops/restarts only the Web process and proves GET returns the
same PostgreSQL revision. Security tests scan:

- API response/diff;
- Compose logs;
- built browser assets;
- local/session storage;
- draft rows and trace;

for generated secret literals.

- [ ] **Step 3: Extend CI gate**

Rename the workflow display name to `Slice 1–2 Local Preview` while keeping the
file stable. Its existing `pnpm check`, unit, image build, stack, E2E and
security/integration commands automatically include Slice 2. Increase timeout
only if observed runtime exceeds 80% of the current bound.

- [ ] **Step 4: Run focused acceptance**

```bash
pnpm dev:local
pnpm test:e2e
uv run pytest tests/security tests/integration -q
pnpm local:down
```

Expected: all pass; shutdown preserves volumes.

- [ ] **Step 5: Commit**

```bash
git add apps/studio-web/e2e tests .github/workflows/slice1.yml
git commit -m "test: prove Slice 2 editing acceptance"
```

---

### Task 8: Documentation, full verification, review and publication

**Files:**
- Create: `docs/acceptance/evidence/SLICE_2.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `DESIGN.md`
- Modify: `SECURITY.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/CONTRACTS.md`
- Modify: `docs/operations/LOCAL_PREVIEW.md`
- Modify: `third_party/candidates.yaml` only if installed dependencies changed
- Modify: `docs/superpowers/plans/2026-07-24-slice-2-one-spec-two-editors.md`
- Add: real editor screenshot under `assets/readme/` if captured from the running implementation

**Interfaces:**
- Produces: source-grounded operator and GitHub handoff.
- Consumes: exact observed commands, counts, SHA and Actions URLs.

- [ ] **Step 1: Run the complete local release gate**

From a clean state:

```bash
pnpm check
pnpm test:contracts
pnpm test:web
uv run pytest -q
pnpm dev:local
pnpm test:e2e
uv run pytest tests/security tests/integration -q
pnpm local:down
```

Record exact counts. Do not claim optional BYOK coverage when skipped.

- [ ] **Step 2: Inspect the real UI**

Open desktop and narrow Build screens from the running stack. Verify:

- no overflow at 320 px and 200% zoom;
- RU/EN labels and long strings;
- visible keyboard focus;
- table/canvas/inspector consistency;
- validation, conflict, saving and run states;
- reduced motion.

Fix defects and rerun affected tests before documentation.

- [ ] **Step 3: Update source-grounded documentation**

Set ROADMAP Slice 2 to complete only after gates pass. Document exact API,
commands, exclusions and security behavior. Capture a README screenshot only
from the verified running stack and never depict an unshipped capability.

- [ ] **Step 4: Run README audit**

Invoke `beautify-github-readme` in audit mode because the default branch will
change. Validate links and every referenced asset. Update only content changed
by Slice 2.

- [ ] **Step 5: Commit verification evidence**

```bash
git add README.md ROADMAP.md DESIGN.md SECURITY.md docs third_party assets/readme
git commit -m "docs: record Slice 2 verification evidence"
```

- [ ] **Step 6: Perform final review**

Invoke `requesting-code-review`. Resolve every Critical and Important finding,
then rerun the complete release gate on the final commit.

- [ ] **Step 7: Publish and verify**

Push the feature branch, wait for both contract and Local Preview Actions to
pass on the exact head SHA, fast-forward merge into `main`, push `main`, and
wait for both main runs to pass on the same SHA. Verify local `main`,
`origin/main` and GitHub head equality.

- [ ] **Step 8: Finish**

Remove the clean merged local worktree and local branch, leave the remote
feature branch recoverable, mark every plan checkbox complete and close the
persistent goal only after main CI is green.
