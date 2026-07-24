# ADR-0006: Authentication and tenancy

**Status:** Accepted

**Date:** 2026-07-24

## Context

The first user is the owner and the first deployment is local, but server deployment, credentials and public agent apps require explicit identities and authorization boundaries.

## Decision

Start with one private workspace and one bootstrap owner account. Preserve `workspace_id` and `project_id` on protected records from the first schema.

- Studio uses server-managed secure sessions.
- Bootstrap owner setup is one-time and stores an Argon2id password hash.
- Published App and public API use separate principals and scopes.
- Credential references are scoped to project and integration.
- Server Preview requires TLS and authentication; “local-first” never means “no auth”.
- OIDC and multi-user roles are later adapters, not Slice 1 requirements.

## Consequences

The initial UX stays simple while storage and policy boundaries remain compatible with future collaboration. Authorization tests must cover project isolation even in a single-workspace deployment.
