# Repository threat model

## Overview

Universal Agent Studio is a local-first platform that will create, execute, publish and improve AI-agent workflows. The repository contains the executable Local Preview Slice 1: authenticated control API, durable runtime, deterministic tool path, persisted traces and Web UI. Later publishing, RAG, sandbox, eval and autoresearch surfaces remain prospective.

Primary protected assets:

- owner identity, sessions, API keys and credential references;
- AgentSpec drafts, immutable published versions and signing keys;
- uploaded files, knowledge sources, retrieved content and generated artifacts;
- run inputs/outputs, traces, feedback, eval datasets and hidden holdouts;
- model/tool permissions, network egress policy and approval decisions;
- control-plane, runtime, research and sandbox privileges.

Security policy is defined by `SECURITY.md`, architecture boundaries by `ARCHITECTURE.md`, and non-negotiable invariants by `docs/ARCHITECTURAL_INVARIANTS.md`.

## Threat Model, Trust Boundaries, and Assumptions

### Actors

- **Owner/Builder:** trusted to configure the workspace, but may accidentally import malicious content or unsafe assets.
- **End User:** untrusted caller of a Published App or public API.
- **Integration/Model Provider:** external service trusted only for the explicitly routed request and declared data policy.
- **Asset Author:** potentially untrusted source of prompts, skills, blueprints, schemas or code.
- **Research Model:** untrusted generator operating on redacted data with no production write credentials.
- **Network Attacker:** can probe public surfaces and attempt session, webhook or transport attacks.
- **Malicious Tenant/User:** future actor attempting cross-project access; project isolation is enforced before multi-user support exists.

### Input ownership

- Attacker-controlled: published-app/API input, files, webhooks, retrieved documents, web content, tool responses, model output, community assets and generated code.
- Operator-controlled: provider connections, credentials, network allowlists, retention, model routing and publication pointers.
- Developer-controlled: schemas, first-party nodes, migrations, deployment manifests and dependency locks.

### Trust boundaries

| Boundary | Threat | Required control | First enforced |
|---|---|---|---|
| Browser → Control API | forged identity, CSRF, XSS, oversized input | secure session, CSRF defense, CSP, size limits, schema validation | Slice 1 |
| Published App/API → Control API | abusive traffic, broken object authorization | scoped principal, rate limit, project-aware authorization | Slice 3 |
| Control API → Runtime worker | command tampering, duplicate execution | authenticated worker channel, immutable version digest, idempotency key | Slice 1 |
| Runtime → Model provider | credential or sensitive-data leakage | server-side CredentialReference, policy routing, redaction, fail-closed capability checks | Slice 1/4 |
| Runtime → Tool/integration | excessive agency, SSRF, duplicate side effect | typed manifest, scopes, egress policy, idempotency, approval | Slice 4 |
| Runtime → Trace/Object stores | secret persistence, cross-project access | project scoping, redaction policy, encryption, retention | Slice 1/5 |
| Research → Production | unauthorized mutation or data reuse | no write credentials, immutable inputs, consent, candidate-only API | Slice 8 |
| Generated code → Host/network | sandbox escape, credential theft, resource exhaustion | separate sandbox, no host mounts/network, limits, explicit mounts | Slice 6 |
| Dependency/asset → Product | supply-chain compromise or license contamination | exact pin, integrity lock, provenance, review owner | Slice 0 onward |

Assumptions:

- Local Preview is bound to loopback unless the owner explicitly enables network access.
- Private-server deployment uses TLS and an authenticated Studio.
- PostgreSQL, Temporal and object storage are private infrastructure services, not internet-facing product APIs.
- A development subprocess/container is not accepted as a production code sandbox.
- Model output and retrieved content never grant permissions.

## Attack Surface, Mitigations, and Attacker Stories

### Authentication and authorization

An attacker may steal or fixate an owner session, forge a public API key, or alter project identifiers. Every protected query and command must derive workspace/project scope from the authenticated principal, not from client-supplied scope alone. Public-agent principals cannot access Studio, raw traces, credentials or drafts.

### AgentSpec and version integrity

A malicious or corrupted draft may reference unknown nodes, insert secret values, weaken a policy or target an incompatible tool/model. Schemas reject unknown fields, publication resolves and locks dependencies, canonical hashing binds the version, and runtime revalidates before execution. Rollback changes only the active-version pointer.

### Model, RAG and prompt injection

User content, retrieved documents, web pages and tool responses may contain instructions that attempt to override policy or exfiltrate data. Runtime separates instructions from data, marks retrieved content untrusted and authorizes tool calls through policy code. A prompt statement can never widen scopes or network access.

### Tool execution and SSRF

An attacker may manipulate HTTP/OpenAPI/MCP arguments toward internal services or repeat a side effect. Tool manifests classify side effects, constrain schemas, declare egress destinations and require idempotency. Risky calls show a human-readable preview and may pause for approval.

### Trace, eval and research data

Traces may contain credentials, personal data or adversarial instructions. Redaction occurs before persistence and external model calls. Research datasets are project-scoped, consent-controlled and separated into research/validation/hidden holdout. Research workers cannot publish or mutate production.

### File and artifact processing

Uploads can be oversized, polyglot, malicious or mislabeled. Size/type checks, malware scanning, parser isolation and bounded extraction precede use. Generated artifacts are served with safe content types and download disposition.

### Code execution

Generated code may attempt host escape, fork bombs, disk exhaustion, network access or secret discovery. Production code execution is unavailable until the separate sandbox passes security tests for filesystem, process, resource, egress and secret-mount boundaries.

### Supply chain and frontend

Compromised packages or copied assets may introduce execution, tracking or license obligations. Dependencies are narrowly selected, exactly pinned, integrity-locked and recorded in `third_party/candidates.yaml`. Frontend libraries cannot define product contracts.

### Out of scope assumptions

- Physical compromise of the owner machine is not mitigated by the application.
- A malicious infrastructure administrator with unrestricted host/database access is outside the first application-level boundary.
- Model-provider internal compromise is handled through data minimization and provider policy, not prevented by this repository.
- Denial of service against an intentionally offline local installation has lower severity than compromise of a shared server, but resource bounds remain required.

## Severity Calibration

### Critical

- unauthenticated production code execution or sandbox escape to host;
- cross-project extraction of credentials or signing keys at scale;
- bypass allowing research/model output to publish production versions;
- systemic authorization failure exposing all private traces/files.

### High

- cross-project read/write access to agent data;
- durable approval bypass for side-effecting tools;
- SSRF into credentialed/private infrastructure;
- stored XSS executing in owner Studio;
- secret values persisted in broadly accessible traces.

### Medium

- scoped denial of service with bounded recovery;
- missing rate limit on a non-privileged endpoint;
- reflected information exposure without credentials or cross-project data;
- UI action confusion that requires an authenticated owner and has a clear rollback.

### Low

- verbose but non-sensitive local-only diagnostics;
- defense-in-depth header omissions with no demonstrated exploit path;
- availability issues limited to an explicitly unsafe development mode;
- metadata leakage that reveals no private content, identity or infrastructure secret.

Repository: https://github.com/Strongf-bob/universal-agent-studio
Version: Slice 1 executable spine
