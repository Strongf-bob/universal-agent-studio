# Local Preview operator guide

## Supported baseline

The tested Slice 1 toolchain is:

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
2. creates three distinct random secrets under `.local/secrets`;
3. enforces mode `0600` on each secret file;
4. builds the pinned API, worker and Web images;
5. starts PostgreSQL and Temporal with independent named volumes;
6. runs Alembic before API and worker startup;
7. waits for every long-running service to become healthy.

Successful output includes:

```text
Web: http://localhost:3000/ru-RU/setup
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

The credentials in `apps/studio-web/e2e/constants.ts` are local test data only.
Do not reuse them outside an isolated preview.

## Ports and environment

Copy `infra/docker/.env.example` only when default ports conflict:

| Variable | Default | Purpose |
|---|---:|---|
| `UAS_WEB_PORT` | 3000 | Studio Web |
| `UAS_API_PORT` | 8000 | Control API |
| `UAS_TEMPORAL_UI_PORT` | 8080 | Temporal UI |
| `UAS_DETERMINISTIC_DELAY_MS` | 2000 | Cancellation-observable fake run delay |

The delay applies only to the deterministic local worker and exists to make
cancellation acceptance reproducible.

## Stop, restart and reset

Normal shutdown preserves both named volumes and generated secrets:

```bash
pnpm local:down
pnpm dev:local
```

The active Alembic revision and persisted runs remain available after restart.

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
