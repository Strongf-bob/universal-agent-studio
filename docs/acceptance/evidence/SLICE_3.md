# Slice 3 verification evidence

## Candidate

- Scope: `Publishing and versions`
- Implementation head verified before documentation: `1873dac`
- Environment: macOS, Docker Compose v2, Chromium, loopback-only Local Preview
- External LLM/network dependency: none
- Optional BYOK smoke: not configured and not claimed

## Local release gate

Run from an isolated Git worktree on 2026-07-25:

| Command | Observed result |
|---|---|
| `pnpm check` | generated files, contracts, ESLint, TypeScript and Ruff passed; mypy: 136 source files |
| `pnpm test:contracts` | 1 file, 14 tests passed |
| `pnpm test:web` | 17 files, 45 tests passed |
| `TEST_DATABASE_URL=… uv run pytest -q` | 186 passed, 1 explicit BYOK skip |
| `pnpm test:e2e` against a clean local stack | 14 Chromium tests passed |
| `uv run pytest tests/security/test_secret_absence.py tests/security/test_slice3_secret_absence.py -q` | 3 live secret-absence tests passed |
| `uv run pytest tests/integration/test_local_stack.py -q` | 8 Compose integration tests passed |
| `pnpm --filter … build` | Studio and Published Web production builds passed |
| refreshed Compose images + `pnpm dev:local --check` | migration exited successfully; all six long-running services healthy |

The only full-suite skip was the opt-in OpenAI-compatible BYOK smoke. The
deterministic delivery path made no external model call.

An independent read-only review on `1873dac` returned `READY` with no
Critical, Important or Minor findings after four hardening passes.

## User-journey proof

Chromium proves:

1. publish the validated calculator draft as immutable v1;
2. run v1 through the separate Published Web App and receive `437`;
3. create an agent-scoped API key, display it once and revoke it;
4. save a changed draft and publish immutable v2;
5. run through the public API and retain v2 identity on the run;
6. roll traffic back to v1 without changing v1, v2 or prior runs;
7. observe exactly `publish`, `publish`, `rollback` in the publication ledger;
8. create a terminal webhook, display its signing secret once and revoke it;
9. complete the same public form journey in `en-US` and `ru-RU`;
10. resume a disconnected public SSE stream from the last observed sequence.

The browser suite also covers a `390px` mobile viewport, keyboard focus,
44-pixel controls, reduced motion and absence of owner credentials, API keys
and webhook secrets from local/session storage, cookies and rendered HTML.

## Contract and persistence proof

- Canonical JSON Schemas generate matching Python and TypeScript types for
  publication, public agent/run/event, API-key and webhook payloads.
- Publish holds the shared agent-publication lock, revalidates the current
  AgentSpec, embedded agent identity and canonical digest, compares draft and
  pointer state, then appends one immutable event transactionally.
- First publication atomically claims the globally routed public `agent_id`;
  a second project cannot make an existing public route ambiguous.
- Existing identical bytes reuse the immutable version; a changed digest gets
  a new monotonically numbered version.
- Every public run stores the selected version identifier and digest.
- Public metadata is a narrow projection of localized copy, InterfaceSchema
  and active version identity.
- Terminal trace finalization, including durable-start failure, inserts one
  idempotent webhook outbox row in the same transaction.
- Fixed-vector tests verify API-key hashing, browser capability verification,
  HMAC body signing, bounded retry and stable delivery identifiers.
- An actual loopback HTTP receiver verifies the signed POST bytes and headers;
  compare-and-set lease completion prevents a stale attempt overwriting a
  newer delivery attempt.

## Security and recovery proof

- A foreign project cannot publish, roll back, list or revoke another
  project's versions, keys or webhooks.
- An API key for one agent cannot create or read another agent's runs.
- An API key with the same agent name in another project cannot cross the
  resolved tenant boundary, and API-key expiry is future-bounded.
- A per-run browser capability cannot read a guessed or different run.
- Stale concurrent publish/rollback attempts fail closed; legacy activation
  uses the same advisory lock and cannot race the first ledger event.
- PostgreSQL rejects equal-target rollback rows and rejects update/delete
  mutations of the publication ledger.
- Webhook URL userinfo, fragments, unlisted origins and redirects are rejected
  before or during bounded egress.
- Raw API keys, webhook secrets and generated infrastructure secrets are
  absent from PostgreSQL projections, run events/traces, Compose logs,
  rendered public/Studio HTML and browser storage.
- Recreated Studio and Published Web containers preserve the PostgreSQL
  publication ledger, active pointer and version-bound run history.

## Visual inspection

The production images were inspected at desktop and mobile widths. The
Published Web App is a distinct origin and contains no Studio navigation or
debug surface; its localized result state exposes only the structured output.
The Publish workspace keeps the current draft/pointer action, version history
and immutable ledger visible before delivery credentials.

Verified screenshots:

- [`assets/readme/slice3-public.png`](../../../assets/readme/slice3-public.png)
- [`assets/readme/slice3-publish.png`](../../../assets/readme/slice3-publish.png)

## Explicit exclusions

No claim is made for Internet deployment, TLS, custom domains, multi-user
RBAC, billing, analytics, arbitrary webhook egress, webhook dashboards,
uploads, RAG, arbitrary HTTP/code nodes, OAuth apps, eval campaigns or
autoresearch.
