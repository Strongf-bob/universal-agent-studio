# Slice 3 acceptance contract: Publish, version and deliver

## Status and purpose

Status: **approved implementation contract**.

Slice 3 proves that one canonical draft can be published as immutable versions,
served through a separate public Web App and API, and rolled back by switching
one traffic pointer. It extends the loopback-only Local Preview; it is not an
Internet deployment.

## Required local environment

The clean-checkout command remains:

```bash
pnpm dev:local
```

It starts Studio, Published Web App, Control API, Runtime worker, PostgreSQL and
Temporal. The deterministic acceptance path requires no LLM credential or
external network access.

Loopback entry points:

- Studio: `http://localhost:3000`;
- Published Web App: `http://localhost:3301`;
- Control and public API: `http://localhost:8000`.

## Deterministic control journey

1. The owner opens the calculator Publish screen in Studio.
2. The current draft is saved as immutable v1 and becomes active.
3. The owner opens the separate Published Web App and submits `19 × 23`.
4. The public result is `{"value":437}`; no trace or prompt is visible.
5. An API key with `runs:create`, `runs:read` and `events:read` is shown once.
6. The async API starts a run; an SSE reconnect with `Last-Event-ID` resumes at
   the next sequence and completes without duplicated output.
7. The sync API completes within the fixture bound, or safely returns HTTP 202
   while the same durable run continues.
8. A signed webhook delivery for the terminal run matches the documented fixed
   HMAC vector and sanitized payload.
9. The owner changes the deterministic calculator draft and publishes v2.
10. New public runs resolve v2 while old runs remain bound to v1.
11. The owner rolls traffic back to v1 with a compare-and-swap operation.
12. New public runs resolve v1. The bytes and identifiers of v1, v2 and all
    prior runs are unchanged; the ledger contains publish, publish, rollback.

## Publishing and version requirements

- publish reads only the authenticated owner's project and agent;
- `expected_draft_revision` and `expected_active_version_id` are mandatory;
- stale revision or pointer returns HTTP 409 without a partial write;
- invalid drafts are not versioned or activated;
- unchanged drafts reuse an existing agent/digest version;
- published versions and publication events are immutable;
- rollback targets only a historical version of the same project and agent;
- rollback changes only the active pointer and appends one ledger event;
- every run stores the exact selected version identifier and digest.

Owner endpoints:

```text
GET  /api/v1/agents/{agent_id}/publishing
POST /api/v1/agents/{agent_id}/publish
POST /api/v1/agents/{agent_id}/rollback
POST /api/v1/agents/{agent_id}/api-keys
GET  /api/v1/agents/{agent_id}/api-keys
POST /api/v1/agents/{agent_id}/api-keys/{key_id}/revoke
POST /api/v1/agents/{agent_id}/webhooks
GET  /api/v1/agents/{agent_id}/webhooks
POST /api/v1/agents/{agent_id}/webhooks/{subscription_id}/revoke
```

## Public API requirements

```text
GET  /public/v1/agents/{agent_id}
POST /public/v1/agents/{agent_id}/runs
POST /public/v1/agents/{agent_id}/invoke
GET  /public/v1/agents/{agent_id}/runs/{run_id}
GET  /public/v1/agents/{agent_id}/runs/{run_id}/events
```

- metadata is limited to localized public copy, `InterfaceSchema` and active
  version identity;
- callers cannot choose an inactive or historical version;
- API keys are agent/project scoped and require exact endpoint scopes;
- API-key secrets are shown only in the create response and stored only as a
  keyed hash;
- revocation and expiry take effect immediately;
- `Idempotency-Key` retries return the same run for the same principal and
  reject a changed payload;
- public run reads require a scoped API key or the exact opaque browser run
  capability;
- SSE honors `Last-Event-ID` and returns monotonically increasing sequences;
- sync timeout returns HTTP 202 without cancelling or duplicating the run;
- public payloads omit prompts, tools, provider data, traces, workflow IDs,
  stack traces and raw internal errors.

## Webhook requirements

- only exact origins from the operator allowlist can be registered;
- URL userinfo, fragments and redirects are rejected;
- the signing secret is shown once and never stored as plaintext;
- terminal trace finalization atomically and idempotently creates outbox rows;
- deliveries contain only the documented sanitized terminal payload;
- HMAC-SHA256 covers `<timestamp>.<raw-json-body>`;
- delivery identifiers are stable across retries;
- transient failures retry with bounded backoff; permanent failures stop;
- revoked subscriptions are checked before every attempt;
- timeout, response bytes, attempt count and stored error text are bounded;
- signatures, API keys and master secrets never enter logs or traces.

## Published Web App requirements

- it is a separate application and origin from Studio;
- it renders the validated `InterfaceSchema`, not an internal AgentSpec;
- it works in RU and EN with localized validation and status;
- ready, running, complete and recoverable error states are explicit;
- mobile touch targets are at least 44 CSS pixels;
- keyboard focus is visible and result/status changes use a polite live region;
- it remains usable at 200% zoom and respects reduced motion;
- it contains no Studio session, CSRF value, API key or trace access;
- its run capability can read only the run for which it was issued.

## Security and isolation evidence

Automated checks must prove:

- a cross-project owner cannot publish, roll back, list or revoke another
  project's objects;
- an API key for agent A cannot create or read runs for agent B;
- a browser capability for run A cannot read run B;
- guessed UUIDs do not grant public access;
- stale concurrent publication and rollback attempts fail closed;
- public response snapshots contain none of the forbidden internal fields;
- database rows, logs, rendered HTML and browser storage contain no raw secret;
- webhook SSRF and redirect cases fail before egress;
- public create and credential-management routes are rate and size limited.

## Deterministic verification

- generated Python and TypeScript contracts agree;
- unit suites cover hashing, capability, signing and retry fixed vectors;
- PostgreSQL integration covers compare-and-swap, isolation and outbox
  atomicity;
- runtime integration proves version binding and terminal delivery creation;
- Chromium completes the v1 → v2 → v1 Studio and public journey in RU and EN;
- Chromium covers mobile, keyboard, reconnect and secret-absence behavior;
- all Slice 1 and Slice 2 acceptance and regression suites remain green;
- `docker compose config`, health checks and clean-checkout startup pass.

## Explicit exclusions

Slice 3 does not include server deployment, TLS, custom domains, multi-user
RBAC, billing, analytics, uploads, RAG, arbitrary integrations, arbitrary
webhook egress, webhook dashboards, OAuth apps or editing immutable versions.

## Definition of done

- the complete control journey runs from a clean checkout with
  `pnpm dev:local`;
- contracts, unit, integration, browser, accessibility, security and
  regression suites pass locally and in GitHub Actions;
- the threat model, architecture, operator guide, ROADMAP and root README match
  the shipped behavior;
- the implementation is merged to `main`, pushed, and the exact pushed commit
  has a green GitHub Actions run.
