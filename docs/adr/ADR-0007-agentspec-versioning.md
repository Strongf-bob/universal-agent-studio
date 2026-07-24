# ADR-0007: AgentSpec versioning and migrations

**Status:** Accepted

**Date:** 2026-07-24

## Context

Agents, packs and assets outlive individual application releases. Rewriting published specifications would destroy run provenance.

## Decision

- JSON Schema uses explicit semantic `schema_version`.
- Canonical JSON serialization and SHA-256 produce the content digest.
- Drafts are mutable; published versions and run snapshots are immutable.
- Migrations are deterministic one-version transforms.
- Opening or importing an old version creates a migrated draft; the source remains unchanged.
- Runtime declares supported schema ranges and fails clearly outside them.
- Rollback changes an active-version pointer only.
- Capability pack dependencies are version-pinned and locked at publication.

Signing is an envelope over digest and version metadata; signing keys never enter AgentSpec.

## Consequences

Storage retains historical schemas and migration code. A migration test corpus is part of compatibility support, not optional cleanup.
