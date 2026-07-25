# ADR-0009: Publishing principals, public surface and traffic pointer

**Status:** Accepted

**Date:** 2026-07-25

## Context

The Local Preview already has immutable AgentVersions, a mutable draft and an
active-version pointer. Publishing must serve untrusted visitors and API
clients without giving them Studio privileges, exposing AgentSpec internals or
changing the version to which an existing run is bound. Webhook delivery also
introduces outbound network and secret-handling risk.

## Decision

Use a separate Published Web App as the untrusted browser surface while
keeping publishing policy in a modular control-plane boundary. Public metadata
contains only localized presentation data and `InterfaceSchema`; it never
contains the canonical AgentSpec.

Treat `agent_active_versions` as the sole traffic pointer for new public runs.
Publishing atomically creates or reuses an immutable version, compare-and-swaps
the pointer, and appends an immutable publication event. Rollback
compare-and-swaps only the pointer to an owned historical version and appends
another event. Existing versions and runs are never rewritten.

Represent public access as explicit least-privilege principals:

- one-time API-key secrets, stored only as keyed hashes, are bound to one
  project and agent and have enumerated run/event scopes;
- Published Web App runs receive an opaque, expiring capability bound to one
  project, agent and run.

Resolve the active version server-side when creating every public run. Public
callers cannot select a historical version. Return sanitized public run and
event representations rather than reusing Studio trace schemas.

Create terminal webhook deliveries with the terminal trace transaction in a
durable outbox. A runtime-side dispatcher sends only sanitized payloads to
exact operator-allowlisted origins. Signing secrets are derived from a
dedicated master secret and subscription identifier; plaintext is not stored.
API-key hashing, run capabilities, webhooks and Studio sessions use distinct
master secrets.

## Rejected alternatives

### Reuse Studio routes and session cookies

Rejected because a future Studio authorization or debug-surface mistake would
cross directly into the public product.

### Let public clients select a version

Rejected because the active pointer would no longer define traffic, rollback
would be misleading and inactive draft-test versions could become reachable.

### Store raw API and webhook secrets

Rejected because database disclosure would immediately become credential
disclosure. Key verification uses a keyed hash; webhook signing material is
derived when needed.

### Send webhooks inline from the API or workflow

Rejected because receiver latency and failure would couple public execution to
external egress and could lose deliveries around process failure.

### Create a separate publishing microservice now

Rejected for the loopback Local Preview because it adds distributed
transactions and deployment complexity without strengthening the selected
contract. The module and schema boundaries preserve future extraction.

## Consequences

- Studio and Published Web App have separate origins and privilege surfaces.
- Publishing and rollback need explicit compare-and-swap conflict UX.
- Public schemas intentionally duplicate a small safe subset of runtime data.
- Key and capability authentication must be checked before revealing object
  existence.
- Webhook delivery becomes eventually consistent and requires retry state.
- Exact egress allowlisting limits Local Preview integrations but prevents the
  first webhook feature from becoming arbitrary SSRF.
- A future production gateway can consume these public contracts without
  changing version or run semantics.

