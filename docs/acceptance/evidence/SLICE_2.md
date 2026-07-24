# Slice 2 verification evidence

## Candidate

- Scope: `One spec, two editors`
- Implementation head verified before documentation: `741c852`
- Environment: macOS, Docker Compose v2, Chromium, loopback-only Local Preview
- External LLM/network dependency: none
- Optional BYOK smoke: not configured and not claimed

## Local release gate

Run from a clean Git worktree on 2026-07-24:

| Command | Observed result |
|---|---|
| `pnpm check` | generated files, contracts, ESLint, TypeScript, Ruff passed; mypy: 108 source files |
| `pnpm test:contracts` | 1 file, 12 tests passed |
| `pnpm test:web` | 12 files, 32 tests passed |
| `TEST_DATABASE_URL=… uv run pytest -q` | 130 passed, 3 skipped |
| `COMPOSE_PROJECT_NAME=uas-slice2 pnpm dev:local` | all five long-running services healthy; migration exited successfully |
| `COMPOSE_PROJECT_NAME=uas-slice2 pnpm test:e2e` | 9 Chromium tests passed |
| `uv run pytest tests/security tests/integration -q` against the running stack | 32 passed |

The three full-suite skips were the explicit BYOK smoke plus the two tests
that require a running full stack. Those two stack-dependent tests then passed
in the dedicated 32-test security/integration run.

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
   identity.

The narrow scenario selects and moves a node with the keyboard and proves the
edited prompt is absent from local/session storage.

## Security and recovery proof

- A foreign project cannot read or update the owner draft.
- Stale revisions and invalid documents fail closed.
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

The real verified screenshot is
[`assets/readme/slice2-editor.png`](../../../assets/readme/slice2-editor.png).

## Explicit exclusions

No claim is made for node/edge topology editing, node library, AI Builder,
RAG, arbitrary HTTP/code nodes, multi-user collaboration, public publishing,
API keys, webhooks, eval campaigns or autoresearch.
