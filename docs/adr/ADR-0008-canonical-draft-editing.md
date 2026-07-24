# ADR-0008: Canonical draft editing and test snapshots

**Status:** Accepted

**Date:** 2026-07-24

## Context

Slice 2 introduces multiple editing views. Persisting separate form and canvas
documents would create synchronization bugs and violate the invariant that
AgentSpec is the only source of runtime semantics. Draft editing also needs a
safe concurrency rule and a way to test unpublished changes without changing
the active version.

## Decision

Store one project-scoped mutable draft per agent. The draft contains:

- a complete canonical AgentSpec;
- its canonical SHA-256 digest;
- an integer optimistic revision;
- the immutable base-version identifier;
- presentation-only layout metadata.

Every semantic editor submits a complete candidate AgentSpec with
`expected_revision`. The control plane validates it and performs an atomic
compare-and-swap. Invalid or stale candidates are not persisted. Layout is
validated and stored beside, but outside, AgentSpec; layout-only changes do not
change the digest.

React Flow types terminate at a first-party projection adapter. Simple
Settings, canvas selection, the node inspector, the accessible table and later
AI Builder all produce commands over the same in-memory AgentSpec document.

Bulk or generated candidates use a server-side, non-mutating diff preview.
The candidate is revalidated and the expected revision is checked again when
the owner applies it.

Testing a draft creates or reuses an immutable, unactivated AgentVersion
snapshot with provenance identifying the draft revision. The existing
durable runtime executes that version. The active-version pointer is never
changed by a draft test.

## Rejected alternatives

### Separate simple and canvas persistence

Rejected because synchronization and precedence rules would form a second
behavior model and eventually diverge from runtime AgentSpec.

### Event-sourced edit command log

Rejected for the Local Preview because it adds replay, compaction and schema
evolution complexity before multi-user collaboration exists. Commands remain
typed at the UI boundary, but persistence uses a full document plus revision.

### Activating every test draft

Rejected because a test must not alter the currently active agent. It would
also make rollback and future publishing semantics ambiguous.

## Consequences

- Concurrent stale tabs fail with a visible conflict instead of silently
  merging.
- Invalid intermediate values can remain in component state but are not
  durable until valid.
- Large documents are rewritten on save; the 1 MiB Slice 2 limit keeps this
  acceptable.
- A future collaboration slice may replace compare-and-swap with a richer
  merge protocol without changing AgentSpec or runtime.
- Unactivated AgentVersions may represent imported or draft-test snapshots;
  provenance distinguishes their origin.

