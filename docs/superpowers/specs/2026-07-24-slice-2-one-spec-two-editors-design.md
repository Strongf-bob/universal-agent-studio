# Slice 2: One Spec, Two Editors — Design

## Outcome

Slice 2 turns the existing calculator AgentSpec into a real, durable editing
workspace. A local owner changes the same draft through Simple Settings and a
React Flow canvas/node inspector, saves and reloads it, previews bulk changes,
runs the unpublished draft and sees live node status.

The acceptance source is
[`docs/acceptance/SLICE_2_ONE_SPEC_TWO_EDITORS.md`](../../acceptance/SLICE_2_ONE_SPEC_TWO_EDITORS.md).
ADR-0008 fixes persistence, concurrency and test-snapshot semantics.

## Scope

The slice proves the architecture with the existing four-node graph. It does
not introduce a node library, topology editing, AI generation, publishing or
additional runtime node kinds. This is deliberate: the risk being retired is
state divergence between progressive-disclosure views, not graph-authoring
breadth.

## Architecture

```text
                         typed edit commands
Simple Settings ─┐
Canvas selection ├──► Draft editor state ──► PUT complete candidate
Node Inspector ──┤             │                      │
Graph Table ─────┘             │                      ▼
                               │             Control API validation
                               │                      │
                               ▼                      ▼
                         AgentSpec digest      PostgreSQL AgentDraft
                         + view projection     + separate layout
                                                      │
                       immutable snapshot ◄────────────┘
                               │
                               ▼
                       existing RunService
                               │
                               ▼
                    Temporal → events → trace
```

The browser has one `DraftEditorState` containing the canonical AgentSpec,
layout, revision, digest, dirty state, selected node and validation issues.
Simple and advanced components receive narrow selectors and typed callbacks;
they never own persisted copies.

The server is authoritative for schema/semantic validation, digest calculation
and revision changes. Client validation exists only for immediate, localized
feedback.

## Canonical contract

Add `agent-draft.schema.json` to the existing v0.1.0 contract family. It wraps:

- `schema_version`;
- `draft_id`;
- `agent_id`;
- `revision`;
- `base_version_id`;
- `digest`;
- `agent_spec` by reference;
- `layout.nodes[]` with node id and finite x/y coordinates;
- `layout.viewport` with finite x/y and bounded zoom;
- `updated_at`.

The generator produces Python and TypeScript types. A valid fixture and invalid
layout fixture join the cross-language manifest. Semantic conformance verifies
unique layout node ids and that every layout node references an AgentSpec node.

Diff operations are API view models rather than runtime contracts. They use
`op`, `json_pointer`, `before` and `after`; sorting by pointer and operation
makes the response deterministic.

## Persistence and transactions

Migration `0002_slice2_agent_drafts.py` creates `agent_drafts` with:

- UUID primary key;
- workspace, project and agent foreign keys;
- unique agent id;
- positive revision;
- base AgentVersion foreign key;
- 64-character digest;
- JSONB AgentSpec and layout;
- owner and timestamps.

Repository methods always require `RequestScope`.

Creation locks the agent row and copies its active version only if no draft
exists. Update locks the draft row, compares `expected_revision`, validates the
candidate before calling persistence, calculates the canonical digest and
increments revision once. A layout-only update is still a meaningful draft
revision but preserves digest.

## API services

Create `agents/drafts.py` for models/protocols and
`agents/draft_service.py` for application behavior. Keep immutable version
logic in its existing files.

Routes:

- create/load draft;
- update a valid draft;
- preview a valid candidate diff;
- create a draft test run.

The draft test service checks the current revision, imports the current
AgentSpec as an immutable unactivated version with draft provenance, and calls
the existing RunService through an explicit internal method that permits a
resolved version. The public `/api/v1/runs` path continues to require an active
version.

API errors:

| Condition | HTTP | Code |
|---|---:|---|
| Active version missing during draft creation | 404 | `agent_version_not_active` |
| Draft missing | 404 | `agent_draft_not_found` |
| Stale revision | 409 | `agent_draft_revision_conflict` |
| Candidate invalid | 422 | `agent_spec_invalid` |
| Layout invalid | 422 | `agent_draft_layout_invalid` |
| Candidate too large | 413 | `request_too_large` |
| Draft snapshot cannot start | 503 | existing durable error |

All write routes use the existing owner, Origin and CSRF boundary.

## Browser state and projections

`DraftWorkspace` owns a reducer:

```text
load → edit semantic/layout → validate/save → preview/apply → test/run events
```

Pure helpers:

- `projectDraftToFlow(agentSpec, layout, locale)`;
- `updateAtPointer(agentSpec, pointer, value)`;
- `validationByField(issues)`;
- `validationByNode(issues)`;
- `runStatusByNode(events)`.

React Flow receives ephemeral `Node` and `Edge` values. Node drag updates only
layout. Selecting a node opens the product-owned inspector. The table consumes
the same projected nodes and can adjust layout by fixed keyboard-safe steps.

## Screen design

Route: `/{locale}/agents/{agentId}/build`.

Desktop layout:

```text
┌──────────────────────────────── toolbar ────────────────────────────────┐
│ Agent / Build        revision · validation · Save · Test                │
├───────────────┬─────────────────────────────┬───────────────────────────┤
│ View rail     │ Canvas                      │ Inspector                 │
│ Simple        │ input → planner → tool → out│ localized metadata       │
│ Flow          │ selected/invalid/run states │ prompt/runtime controls  │
│ Bulk diff     │                             │                           │
├───────────────┴─────────────────────────────┴───────────────────────────┤
│ Test Console: input · events · result · trace link                      │
└─────────────────────────────────────────────────────────────────────────┘
```

The visual direction remains a quiet technical workbench. Existing tokens are
extended for editor surfaces, not replaced. Invalid and run states always
include text/icon treatment. Motion is limited to optional status transitions
and disabled under reduced motion.

On tablets, the side rail selects one panel. On phones, Simple, Flow,
Inspector, Bulk and Test are tabs; Flow defaults to the accessible table.

## Validation flow

Client fields map to JSON Pointers. On save:

1. local required/type checks update field messages;
2. the full document goes to the server;
3. server issues are grouped by pointer and node;
4. the summary links to the first invalid field or node;
5. canvas and table mark invalid nodes;
6. focus moves to the summary;
7. the prior stored revision remains loaded and a retry is possible.

Semantic graph validation is upgraded to return precise node pointers for
dangling model/tool references and edge endpoint pointers.

## Bulk diff flow

The owner opens Bulk Change, pastes a complete JSON candidate and selects
Preview. The API parses, size-checks and validates before computing a recursive
object/array diff. Valid values are redacted through the existing redaction
policy before response. Preview is stored only in component memory.

Apply sends the candidate through the ordinary save endpoint with the same
expected revision. A stale revision forces a new preview; the UI never silently
rebases.

## Test Console flow

The console uses the AgentSpec interface field and submits the current
revision. The API snapshots the draft, returns a `run_id`, and existing SSE
events drive status maps for canvas and table. Completion shows schema-driven
output plus a link to the existing full Run Trace route.

Draft changes are disabled while the snapshot request is being created, then
reenabled; the run remains bound to the exact prior digest even if editing
continues.

## Security

- Do not persist invalid documents.
- Run forbidden-secret-key validation before persistence and before diff.
- Never store drafts or candidate JSON in browser storage.
- Bound candidate bodies and layout collection sizes.
- Derive scope only from the authenticated session.
- Redact diff values and keep logs structural.
- Keep React Flow and candidate JSON outside runtime and database type
  boundaries.
- Verify draft test snapshots are never activated.

## Testing

### Contracts

- valid AgentDraft fixture passes Python and TypeScript;
- duplicate/dangling layout nodes fail with the same semantic code;
- generated types remain in sync.

### Unit

- digest behavior for semantic versus layout edits;
- stable diff ordering and redaction;
- precise field/node validation mapping;
- projection and reducer behavior;
- accessible table commands;
- run-event highlighting.

### Integration and security

- migration from Slice 1 and clean migration;
- create/get/update with optimistic concurrency;
- refresh/restart persistence;
- cross-project denial;
- secret candidate rejection;
- draft snapshot reuse and active-pointer preservation;
- idempotent test runs.

### Browser E2E

- Simple Settings edit;
- canvas selection and inspector edit;
- drag/save/refresh;
- invalid node recovery;
- bulk preview then explicit Apply;
- test run, live highlighting and result;
- RU/EN and keyboard-only path;
- narrow viewport/table path.

Existing Slice 1 suites remain required regression gates.

## Rollout and documentation

Slice 2 remains Local Preview. The Compose stack and root command do not
change. Update ROADMAP, README, operator guide, threat model, dependency
registry and acceptance evidence after the implementation passes the complete
gate.

