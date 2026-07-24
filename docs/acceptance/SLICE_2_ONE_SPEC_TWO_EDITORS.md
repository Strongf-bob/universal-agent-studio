# Slice 2 acceptance contract: One spec, two editors

## Status and purpose

Status: **approved implementation contract**.

Slice 2 proves progressive disclosure over one canonical `AgentSpec` draft.
Simple Settings, the visual canvas, the node inspector and the accessible
table are projections and commands over the same server-backed document.
None of them may persist a competing graph model.

The slice extends the Local Preview from Slice 1. Publishing, arbitrary node
creation, RAG, code execution and AI-generated drafts remain outside this
contract.

## Required local environment

The clean-checkout command remains:

```bash
pnpm dev:local
```

It starts the Studio, Control API, Runtime worker, PostgreSQL and Temporal.
The deterministic acceptance path requires no external credential or network
access.

## Canonical draft and layout

For each agent and project, the control plane stores at most one mutable
`AgentDraft`:

- `agent_spec` is the only runtime-semantic document;
- `digest` is the SHA-256 digest of canonical `agent_spec` JSON;
- `revision` is a monotonically increasing optimistic-concurrency token;
- `base_version_id` records the immutable version from which the draft began;
- `layout` stores coordinates and viewport only;
- `updated_at` is server-generated.

Moving a node or changing the viewport increments the draft revision but does
not change the canonical AgentSpec digest. Changing a semantic field changes
the digest. Saving with a stale `expected_revision` returns HTTP 409 and never
overwrites the newer draft.

Invalid AgentSpec content is never persisted. Validation returns stable
`code`, `json_pointer`, `node_id` and `message_key` values. Secret-like keys
are rejected before persistence and before diff values are returned.

## Required API behavior

Authenticated owner endpoints:

```text
POST /api/v1/agents/{agent_id}/draft
GET  /api/v1/agents/{agent_id}/draft
PUT  /api/v1/agents/{agent_id}/draft
POST /api/v1/agents/{agent_id}/draft/diff
POST /api/v1/agents/{agent_id}/draft/runs
```

`POST .../draft` creates the draft from the active immutable version. Repeating
the request returns the existing draft without resetting edits.

`PUT .../draft` accepts the complete candidate AgentSpec, presentation layout
and `expected_revision`. It validates the AgentSpec, scopes the write to the
authenticated project and atomically advances the revision.

`POST .../diff` accepts a complete candidate AgentSpec and
`expected_revision`. It returns a deterministic list of `add`, `remove` and
`replace` operations sorted by JSON Pointer. It never mutates the draft.

`POST .../runs` accepts the current revision, typed input, locale,
`request_id` and idempotency key. The server:

1. verifies the revision and validation state;
2. stores or reuses an immutable, unactivated AgentVersion snapshot by digest;
3. starts the existing durable execution path against that snapshot;
4. leaves the active-version pointer unchanged.

The resulting run, events and trace use the snapshot version identifier and
digest. Existing run read, SSE resume, cancellation and trace endpoints remain
unchanged.

## Required user journey

1. The owner opens the calculator agent Build screen.
2. Studio creates or loads a draft from the active immutable version.
3. In Simple Settings, the owner changes the localized agent name.
4. On the canvas, the owner selects `planner-model`; the node inspector changes
   its localized name and prompt.
5. Dragging the node updates layout without changing the AgentSpec digest.
6. Saving advances the revision. Refresh restores the same AgentSpec and
   layout.
7. The accessible graph table can select every node and expose the same
   inspector without pointer input.
8. A deliberately invalid model reference produces a summary plus a
   node-local error for `planner-model`; the stored revision is unchanged.
9. A bulk candidate is previewed as a diff. No data changes before the
   explicit Apply action.
10. Test Console runs `What is 19 × 23?` from the current draft snapshot.
11. Canvas and table statuses progress through the persisted RunEvents.
12. The result is `{"value":437}` and links to the complete stored trace.
13. Switching RU/EN preserves the draft revision, selection, layout and run.

## Editor behavior

### Simple Settings

The first simple surface edits:

- agent name and description for `ru-RU` and `en-US`;
- the default interface locale;
- the deterministic planner model temperature.

Fields are schema-derived or explicitly mapped to stable AgentSpec JSON
Pointers. Local errors help before submit; server validation remains
authoritative.

### Canvas and inspector

React Flow remains behind a product-owned projection adapter. Slice 2 supports:

- pan, zoom, fit view and node dragging;
- selected, dirty, invalid, running, completed and failed node states;
- semantic labels from AgentSpec;
- node selection by pointer, keyboard table or canvas;
- editing localized node metadata;
- editing the planner prompt, model-profile reference, timeout and retry count
  in the inspector.

Slice 2 does not add/delete nodes or edges. That keeps the first editable
surface bounded while proving the one-spec architecture.

### Accessible alternative

The graph table is not a read-only transcript. It supports node selection,
shows validation and run status in text, and exposes keyboard controls for
moving the selected node in the presentation layout. All inspector and save
actions work without using the React Flow surface.

### Bulk diff

A JSON candidate can be loaded into the bulk-change panel. Preview:

- parses and validates the candidate on the server;
- reports localized validation without mutating stored state;
- renders paths and redacted before/after values;
- requires a separate Apply action;
- rechecks the expected revision and full validation during Apply.

This is the reusable safety boundary for a later AI Builder; Slice 2 does not
call an LLM.

## Visual and responsive acceptance

- The Build screen is a calm technical workbench using existing semantic
  design tokens.
- At `>=1024px`, Simple/Flow navigation, canvas and inspector can be visible
  together.
- At `768–1023px`, canvas and one side panel are switchable.
- Below `768px`, Simple, Flow, Inspector and Test are separate tabs; the table
  is the primary graph editor.
- Focus is visible, touch targets are at least 44 CSS pixels and color is not
  the only state indicator.
- Reduced-motion users receive no animated execution path.
- RU and EN remain usable at 200% zoom.

## Security and recovery acceptance

- Every read and write is scoped from the authenticated owner, never a
  client-supplied workspace or project identifier.
- Browser writes require the existing Origin allowlist and CSRF token.
- Candidate and saved documents are bounded to 1 MiB.
- Secret values do not appear in the draft, diff, response, log, trace or
  browser storage.
- Draft state is stored in PostgreSQL, not local/session storage.
- Stale saves and stale diff application fail closed with HTTP 409.
- Refresh or Web-process restart reloads the latest committed draft.
- Draft test execution is idempotent and never activates its snapshot.

## Deterministic acceptance evidence

Automated checks must prove:

- Python and TypeScript consume the generated `AgentDraft` contract;
- layout-only saves preserve digest;
- semantic saves change digest and revision;
- invalid field and node errors have stable locations;
- concurrent stale updates cannot overwrite a newer revision;
- cross-project draft reads, writes, diffs and test runs are denied;
- bulk preview is non-mutating and secret-safe;
- draft run leaves the active version unchanged;
- Chromium completes the RU/EN keyboard journey and observes live node
  highlighting;
- existing Slice 1 golden, cancellation, reconnect and security suites remain
  green.

## Explicit exclusions

Slice 2 does not include:

- node or edge creation/deletion;
- node library or capability packs;
- JSON/CodeMirror developer editor;
- AI Builder or external model calls;
- multi-user collaboration or conflict merging;
- public publishing, API keys or webhooks;
- RAG, integrations, approvals, code nodes, evals or autoresearch.

## Definition of done

- The required user journey runs from a clean checkout with `pnpm dev:local`.
- Simple Settings and canvas/inspector persist one canonical AgentSpec draft.
- Draft save/load, validation, diff preview and Test Console pass browser E2E
  in RU and EN without external network access.
- Contract, unit, integration, security, accessibility and regression suites
  pass locally and in GitHub Actions.
- Dependency registry, threat model, operator guide, ROADMAP and README match
  the shipped Slice 2 behavior.

