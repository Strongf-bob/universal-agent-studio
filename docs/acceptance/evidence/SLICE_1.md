# Slice 1 acceptance evidence

## Evidence revision

Product and E2E implementation revision: `8ac3786`.

Final documentation and workflow revisions are verified separately by the
`Slice 1 Executable Spine` GitHub Actions gate. This document records observed
behavior, not an assertion about unexecuted future work.

## Observed local results

Environment: macOS, Docker Engine 29.5.3, Docker Compose 5.1.4, Node.js 26.3.0,
pnpm 11.7.0, Python 3.14.6 and uv 0.11.32.

| Gate | Observed result |
|---|---|
| Root generated/contracts/lint/type checks | passed |
| Full Python suite | 100 passed, 1 opt-in BYOK smoke skipped |
| Web component tests | 14 passed |
| Chromium E2E | 7 passed |
| Security acceptance | 2 passed |
| Final security + integration rerun | 21 passed |
| Local Compose services | PostgreSQL, Temporal, API, worker and Web healthy |
| API readiness | `{"status":"ready"}` |
| Normal shutdown/restart | Alembic revision `0001` preserved |
| Web endpoints | EN setup and Temporal UI returned success |

## Golden path

- canonical fixture: `agent.calculator.ru-en.json`;
- immutable version: imported and activated through authenticated API;
- input: `What is 19 × 23?`;
- structured output: `{"value":437}`;
- event sequence: `run.started`, `node.started`, `model.requested`,
  `model.completed`, `tool.requested`, `tool.completed`, `node.completed`,
  `run.completed`;
- stored trace: rendered after refresh and selectable through graph/table;
- cancellation: terminal `run.cancelled` with readable partial trace;
- localization: same `run_id` retained across EN → RU switch.

The repository screenshot at `assets/readme/slice1-run.png` was captured from
the running stack after the golden result became terminal.

## Security evidence

- generated database, execution-signing and session-hash secrets are distinct,
  owner-only files;
- Compose config, service logs and built browser assets do not contain their
  values;
- password and session values are not stored in browser local/session storage;
- unsafe browser writes require an allowlisted Origin and CSRF token;
- repository queries return no AgentVersion across a foreign project scope;
- OpenAI-compatible egress requires HTTPS or loopback plus explicit origin
  allowlisting, bounded response size, timeout and redirect denial;
- normal logs can be collected only through the literal-value redactor in
  `scripts/collect-redacted-logs.mjs`.

## Recovery evidence

- browser refresh reconstructs the page from persisted run/version state;
- SSE resume sends `Last-Event-ID` and deduplicates by `event_id`;
- worker cancellation finalizes exactly one terminal cancellation event;
- normal `local:down` preserves PostgreSQL and Temporal volumes;
- destructive reset requires the exact text `RESET LOCAL DATA`.

## Remaining boundary

This evidence covers Local Preview Slice 1 only. It does not certify the
future public publishing, multi-user, arbitrary HTTP, RAG, sandbox, eval or
autoresearch surfaces.
