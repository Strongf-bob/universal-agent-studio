# ADR-0005: Code sandbox

**Status:** Accepted

**Date:** 2026-07-24

## Context

User or generated code is hostile input. A development subprocess or ordinary application container is not an adequate production security boundary.

## Decision

Code execution is a separate service behind `SandboxPort`. It is excluded from Slice 1.

The production implementation must provide:

- Linux isolation stronger than a shared process;
- ephemeral filesystem and no host mounts;
- CPU, memory, wall-time and output limits;
- no network by default and explicit egress allowlists;
- explicit, scoped secret mounts;
- auditable request/result envelopes.

A feasibility/security spike will compare gVisor-backed OCI isolation and equivalent maintained alternatives before Slice 6. Development fallback must be labelled unsafe and cannot satisfy production acceptance.

## Consequences

Code nodes are delayed until the security boundary is demonstrated. The port allows local development without representing it as secure production execution.
