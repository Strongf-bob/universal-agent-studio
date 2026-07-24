# Slice 1 acceptance evidence

## Evidence revision

Product, recovery and E2E implementation revision: `3a7afee`.

Branch verification:

- `Contract Conformance` run
  [30119798447](https://github.com/Strongf-bob/universal-agent-studio/actions/runs/30119798447);
- `Slice 1 Executable Spine` run
  [30119798460](https://github.com/Strongf-bob/universal-agent-studio/actions/runs/30119798460).

## Observed local results

Environment: macOS, Docker Engine 29.5.3, Docker Compose 5.1.4, Node.js 26.3.0,
pnpm 11.7.0, Python 3.14.6 and uv 0.11.32.

| Gate | Observed result |
|---|---|
| Root generated/contracts/lint/type checks | passed |
| Full Python suite | 109 passed, 1 opt-in BYOK smoke skipped |
| Web component tests | 15 passed |
| Chromium E2E | 7 passed |
| Final security + integration rerun | 23 passed |
| Local Compose services | PostgreSQL, Temporal, API, worker and Web healthy |
| API readiness | `{"status":"ready"}` |
| Normal shutdown/restart | Alembic revision `0001` preserved |
| Web endpoints | EN setup and Temporal UI returned success |

## Golden path

- canonical fixture: `agent.calculator.ru-en.json`;
- immutable version: selected, validated and activated through the visible Web
  import journey;
- input: `What is 19 × 23?`;
- structured output: `{"value":437}`;
- event sequence: `run.started`, `node.started`, `model.requested`,
  `model.completed`, `tool.requested`, `tool.completed`, `node.completed`,
  `run.completed`;
- stored trace: rendered after refresh and selectable through graph/table,
  including attempt, timestamps and model/tool provenance;
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
- the Web response enforces CSP, frame denial, no-referrer and MIME-sniffing
  denial;
- run inputs are checked against the active AgentSpec interface at both API and
  runtime boundaries;
- repository queries return no AgentVersion across a foreign project scope;
- OpenAI-compatible egress requires HTTPS or loopback plus explicit origin
  allowlisting, bounded response size, timeout and redirect denial;
- normal logs can be collected only through the literal-value redactor in
  `scripts/collect-redacted-logs.mjs`.

## Recovery evidence

- browser refresh reconstructs the page from persisted run/version state;
- SSE resume sends `Last-Event-ID` and deduplicates by `event_id`;
- worker cancellation finalizes exactly one terminal cancellation event;
- exhausted activity retries finalize a safe `run.failed` event and readable
  failed trace;
- retrying the same idempotent request repairs the post-Temporal-start
  persistence window without starting duplicate logical work;
- normal `local:down` preserves PostgreSQL and Temporal volumes;
- destructive reset requires the exact text `RESET LOCAL DATA` and a matching
  local-state ownership marker.

## Remaining boundary

This evidence covers Local Preview Slice 1 only. It does not certify the
future public publishing, multi-user, arbitrary HTTP, RAG, sandbox, eval or
autoresearch surfaces.
