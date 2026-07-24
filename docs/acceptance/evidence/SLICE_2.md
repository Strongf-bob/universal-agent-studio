# Slice 2 verification evidence

## Candidate

- Scope: `One spec, two editors`
- Implementation and review head verified before documentation: `6752549`
- Environment: macOS, Docker Compose v2, Chromium, loopback-only Local Preview
- External LLM/network dependency: none
- Optional BYOK smoke: not configured and not claimed

## Local release gate

Run from a clean Git worktree on 2026-07-24:

| Command | Observed result |
|---|---|
| `pnpm check` | generated files, contracts, ESLint, TypeScript, Ruff passed; mypy: 108 source files |
| `pnpm test:contracts` | 1 file, 12 tests passed |
| `pnpm test:web` | 12 files, 35 tests passed |
| `TEST_DATABASE_URL=… uv run pytest -q` | 134 passed, 1 explicit BYOK skip |
| `COMPOSE_PROJECT_NAME=uas-slice2 pnpm dev:local` | all five long-running services healthy; migration exited successfully |
| `COMPOSE_PROJECT_NAME=uas-slice2 pnpm test:e2e` | 10 Chromium tests passed |
| `uv run pytest tests/security tests/integration -q` against the running stack | 32 passed |

The only full-suite skip was the opt-in BYOK smoke. Stack-dependent security
tests ran against the isolated `uas-slice2` Compose project and passed.

## User-journey proof

Chromium proves:

1. create/load one draft from the active calculator version;
2. edit agent metadata in Simple Settings;
3. select, edit and move `planner-model` through the graph/table/inspector;
4. save, reload and recover the same revision, AgentSpec and layout;
5. reject a dangling model profile with field/node-local feedback;
6. preview two JSON changes without mutation, then Apply explicitly;
7. run the saved revision as an immutable snapshot;
8. retain `Running` and `Completed` node history and return `{"value":437}`;
9. open the persisted trace and switch RU/EN without changing run or draft
   identity;
10. invoke fit-to-view explicitly, persist the exact React Flow viewport and
    restore it on refresh without marking the untouched draft dirty.

The narrow scenario traverses the real responsive editor tabs with arrow keys,
selects and moves a node with the keyboard, and proves the edited prompt is
absent from local/session storage.

## Security and recovery proof

- A foreign project cannot read or update the owner draft.
- Stale revisions and invalid documents fail closed.
- Malformed nested AgentSpec values return stable `422` validation instead of
  reaching a server error.
- Draft snapshot creation shares the write-route rate limit, and dirty drafts
  cannot be run under a stale saved-revision label.
- A generated secret-like value is absent from API/diff responses, the saved
  draft, PostgreSQL draft/trace documents, Compose logs and browser assets.
- Generated local infrastructure secrets are absent from Compose
  configuration/logs and the built browser bundle.
- Restarting only `studio-web` preserves the PostgreSQL draft revision and
  digest.
- Draft test execution leaves the active version pointer unchanged and binds
  the run/trace to the saved snapshot digest.

## Visual inspection

The production Web image was inspected at desktop `1440px`, narrow `390px`
and `320px`, and at `640` CSS pixels as the layout-equivalent of 200% browser
zoom on a 1280px viewport.

- document `scrollWidth` equals `clientWidth` at all inspected widths;
- RU and EN labels remain readable;
- canvas, accessible table and inspector agree on selection and status;
- below `768px`, the decorative canvas is hidden while the keyboard table
  remains the graph editor;
- keyboard focus uses a visible solid outline;
- `prefers-reduced-motion: reduce` is honored.
- saved graph pan/zoom is authoritative on load; fit-to-view is an explicit
  localized button rather than a mount-time side effect.

The final independent code review reported no remaining Critical or Important
issues and marked the slice ready to merge.

The real verified screenshot is
[`assets/readme/slice2-editor.png`](../../../assets/readme/slice2-editor.png).

## Explicit exclusions

No claim is made for node/edge topology editing, node library, AI Builder,
RAG, arbitrary HTTP/code nodes, multi-user collaboration, public publishing,
API keys, webhooks, eval campaigns or autoresearch.
