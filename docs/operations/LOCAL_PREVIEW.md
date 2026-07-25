# Local Preview operator guide

## Supported baseline

The tested Slices 1–3 toolchain is:

| Component | Version |
|---|---:|
| Node.js | 26 |
| pnpm | 11.7.0 |
| Python | 3.14 |
| uv | 0.11.32 |
| PostgreSQL image | 18.4-alpine3.23, digest-pinned |
| Temporal CLI image | 1.8.1, digest-pinned |

Docker Desktop or Docker Engine with Compose v2 must be running. All public
ports bind to loopback by default.

## Install and start

From the repository root:

```bash
uv sync --all-packages --frozen
pnpm install --frozen-lockfile
pnpm dev:local
```

The launcher:

1. verifies Docker availability;
2. creates six distinct random secrets under `.local/secrets`;
3. enforces mode `0600` on each secret file;
4. builds the pinned API, worker, Studio and Published Web images;
5. starts PostgreSQL and Temporal with independent named volumes;
6. runs Alembic before API and worker startup;
7. waits for every long-running service to become healthy.

Successful output includes:

```text
Web: http://localhost:3000/ru-RU/setup
Published Web App: http://localhost:3301/ru-RU/agents/calculator-agent
API: http://localhost:8000/health/ready
Temporal UI: http://localhost:8080
```

No secret value is written to `.env.example`, Compose environment output or
normal service logs.

## First deterministic walkthrough

Install the matching Chromium once:

```bash
pnpm --filter @universal-agent-studio/studio-web exec playwright install chromium
```

Run:

```bash
pnpm test:e2e
```

On a clean stack the bootstrap project creates a local test owner through the
Web setup form, selects the canonical calculator JSON in the visible import
screen, inspects its validation status and digest, activates it through the
Web UI, and stores only an opaque session cookie. The remaining tests prove:

- immutable version and digest visibility;
- `19 × 23 → {"value":437}`;
- ordered live events and persisted trace;
- browser refresh and SSE resume;
- read-only graph and keyboard table;
- RU/EN route preservation;
- cancellation with a readable partial trace;
- logout/login and absence of the test password from browser storage.
- draft creation from the active immutable version;
- one canonical AgentSpec edited through Simple Settings, canvas/inspector and
  the keyboard graph table;
- PostgreSQL save/reload of semantics and layout with revision advancement;
- node-local invalid-reference feedback and non-mutating bulk diff preview;
- immutable, unactivated draft snapshot run with node event history and
  `{"value":437}`;
- draft identity preservation through trace navigation and RU/EN switching.
- first publication of v1, publication of changed v2 and rollback of traffic
  to the byte-identical v1 through the Studio Publish workspace;
- a version-bound public run through the separate RU/EN Published Web App;
- one-time API-key and webhook-secret display followed by revocation without
  browser, database, rendered HTML or log disclosure;
- public SSE resume from `Last-Event-ID` without duplicate output.

The credentials in `apps/studio-web/e2e/constants.ts` are local test data only.
Do not reuse them outside an isolated preview.

## Ports and environment

Copy `infra/docker/.env.example` only when default ports conflict:

| Variable | Default | Purpose |
|---|---:|---|
| `UAS_WEB_PORT` | 3000 | Studio Web |
| `UAS_PUBLISHED_WEB_PORT` | 3301 | Published Web App |
| `UAS_API_PORT` | 8000 | Control API |
| `UAS_TEMPORAL_UI_PORT` | 8080 | Temporal UI |
| `UAS_DETERMINISTIC_DELAY_MS` | 2000 | Cancellation-observable fake run delay |

The delay applies only to the deterministic local worker and exists to make
cancellation acceptance reproducible.

## Stop, restart and reset

Normal shutdown preserves both named volumes, generated secrets, drafts and
run traces:

```bash
pnpm local:down
pnpm dev:local
```

The active Alembic revision, persisted runs, publication ledger, active
traffic pointer and latest committed draft revision/digest remain available
after restart.

After importing and activating the calculator fixture, the Build workspace is:

```text
http://localhost:3000/en-US/agents/calculator-agent/build
```

After publishing, the owner controls immutable versions and delivery
credentials at:

```text
http://localhost:3000/en-US/agents/calculator-agent/publish
```

The least-privilege end-user surface is a separate origin:

```text
http://localhost:3301/en-US/agents/calculator-agent
```

Every unsafe API call, including direct operator scripts, must send an allowed
`Origin` and the session CSRF token. The browser does this automatically.

Destructive reset is intentionally guarded:

```bash
pnpm local:reset -- --confirm "RESET LOCAL DATA"
```

It removes only the `universal-agent-studio` Compose resources, their two named
volumes and the ignored `.local` state directory after verifying its
repository-specific ownership marker. Non-empty unowned directories and any
directory containing the repository are rejected. Source fixtures and tracked
repository files are never reset targets.

## Health and diagnostics

```bash
curl --fail http://localhost:8000/health/ready
curl --fail http://localhost:3000/en-US/setup
curl --fail http://localhost:3301/health
curl --fail http://localhost:8080
docker compose -f infra/docker/compose.local.yml ps
node scripts/collect-redacted-logs.mjs
```

`/health/live` proves process liveness. `/health/ready` becomes successful only
after application startup dependencies have been initialized. The worker
healthcheck uses an owner-only readiness file created after Temporal and
PostgreSQL connectivity succeeds.

If `pnpm dev:local` reports that Docker is unavailable, start Docker Desktop
and retry. If a port is occupied, override only that port in an untracked
`.env` or in the invoking shell.

## Optional OpenAI-compatible BYOK smoke

The mandatory path never calls an external model. An explicit smoke may run
against an HTTPS endpoint or a loopback endpoint:

```bash
UAS_BYOK_SMOKE_BASE_URL=https://provider.example/v1 \
UAS_BYOK_SMOKE_MODEL=model-name \
UAS_BYOK_SMOKE_API_KEY=replace-in-invoking-shell \
uv run pytest libs/python/agent_kernel/tests/test_openai_compatible.py \
  -q -k opt_in_byok_smoke
```

The adapter resolves the key through a `CredentialReference`, requires an
explicit origin allowlist, disables redirects, bounds time and response size,
and converts provider failures to safe error codes. The test is skipped unless
all three dedicated variables are present.
