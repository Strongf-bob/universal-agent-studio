# Security baseline

This document is an engineering baseline, not legal or compliance advice.

Repository-scoped attacker stories, trust boundaries and severity calibration are maintained in [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md). `SECURITY.md` defines mandatory policy; the threat model explains how it applies to product surfaces.

## 1. Trust boundaries

Untrusted by default:

- user messages;
- uploaded files;
- retrieved documents;
- web content;
- integration responses;
- model outputs;
- traces used by researcher models;
- community assets;
- generated code.

Trusted only after verification:

- signed published AgentSpec versions;
- approved first-party assets;
- validated model/tool manifests;
- server-side credential references.

## 2. Credentials

- never store secret values in AgentSpec;
- store only `credential_ref`;
- resolve secrets server-side;
- support rotation;
- redact from logs and errors;
- scope each credential to an integration and project;
- prevent transmission to unauthorized model providers.

## 3. Code execution

Generated or user-provided code must run in a separate sandbox with:

- CPU, memory and time limits;
- temporary filesystem;
- no host mounts;
- no network by default;
- allowlisted egress when required;
- explicit secret mounts;
- process isolation;
- output size limits;
- audit events.

## 4. Tool execution

- typed schemas;
- permission scopes;
- side-effect classification;
- idempotency keys;
- timeout/retry policy;
- human approval for risky actions;
- clear preview before irreversible actions.

## 5. Prompt injection and untrusted context

- separate instructions from data;
- mark retrieved content as untrusted;
- do not allow retrieved text to change permissions;
- filter tool calls through policy, not prompt wording;
- researcher models must not treat log text as instructions;
- test known injection patterns in eval packs.

## 6. Data handling

- project-level isolation;
- configurable retention;
- redaction before external model calls;
- `data_classification` metadata on stored and transmitted content;
- versioned `redaction_policy_id`;
- explicit `retention_policy_id`;
- named `security_owner` for integrations, providers and privileged assets;
- audit access to traces;
- explicit consent for cross-project/platform research;
- deletion workflow.

## 7. Model routing

Model profiles include data policy:

```text
external_allowed
local_only
sensitive_data_allowed
retention_policy
region
```

Routing must fail closed when a selected provider violates the policy.

## 8. Publishing and API

- scoped API keys;
- rate limits;
- idempotency;
- signed webhooks;
- input size limits;
- malware/file-type checks;
- tenant-aware authorization;
- no debug data in public responses.

## 9. Autoresearch

- isolated worker;
- no production write credentials;
- immutable source snapshot;
- explicit mutation allowlist;
- fixed budget;
- hidden holdout;
- human approval;
- candidate provenance.

## 10. Required security tests

- secret leakage;
- cross-project access;
- prompt injection;
- unauthorized tool call;
- code sandbox breakout attempts;
- SSRF;
- webhook forgery;
- unsafe file upload;
- model routing policy bypass;
- trace redaction.

## 11. Security ownership and review gates

- every public endpoint has an authentication/authorization decision;
- every new external data flow updates `docs/THREAT_MODEL.md`;
- every privileged dependency has a security owner and upgrade path;
- every side-effecting tool declares scopes, idempotency and approval policy;
- every schema change is checked for secret-bearing fields and unsafe free-form payloads;
- every release records unresolved security risks and their accepted owner;
- no Local Preview shortcut may be described as a production security boundary.

## 12. Severity escalation

Critical issues include unauthenticated production code execution, cross-project credential access, bypass of manual publication, or extraction of model/tool secrets at scale. High severity includes project-level data access, durable approval bypass, SSRF into privileged networks, or stored XSS in Studio/Published App. Detailed calibration lives in the threat model.

## 13. Slices 1–3 implemented controls

The Local Preview executable spine currently enforces:

- Argon2id owner password hashing and keyed hashes for opaque session/CSRF values;
- `HttpOnly`, `SameSite=Lax` session cookies and CSRF validation on unsafe routes;
- strict host/origin checks, request-size bounds and narrow rate limits;
- browser CSP, frame denial, no-referrer policy and MIME-sniffing denial;
- active AgentSpec input-schema validation at API and runtime boundaries;
- workspace/project scope derived from the authenticated owner;
- immutable AgentVersion digests and signed execution envelopes;
- first-party calculator allowlisting with no arbitrary HTTP or code execution;
- redaction before persisted events/traces;
- file-mounted random local secrets with owner-only permissions;
- marker-bound destructive reset that refuses unowned or broad directories;
- loopback-only public Compose ports and isolated product/Temporal volumes;
- provider URL allowlisting, HTTPS/loopback policy, timeout, redirect denial and response-size bounds.
- mutable drafts scoped only from the authenticated owner workspace/project;
- CSRF and Origin enforcement on create, update, diff and draft-run routes;
- 1 MiB document bounds, generated contract validation and fail-closed
  rejection of dangling references and secret-like keys;
- monotonic revision checks that reject stale save or stale diff application
  without overwriting the committed draft;
- non-mutating, deterministic and redacted diff preview before Apply;
- immutable snapshot binding for draft test runs without changing the active
  version pointer;
- PostgreSQL persistence with restart recovery and no AgentSpec/secret
  persistence in local/session storage.
- publish and rollback compare both draft revision and active-version pointer,
  reject stale writes, and append immutable publication events;
- public metadata exposes only localized copy, InterfaceSchema and active
  version identity, never draft, prompt, tool, provider or trace data;
- API keys are agent/project scoped, stored as keyed hashes, shown once and
  checked for exact scopes, revocation and expiry on every request;
- Published Web App uses an opaque, single-run capability instead of owner
  cookies, CSRF tokens or public API keys;
- webhook destinations are restricted to exact HTTPS allowlisted origins,
  deny userinfo/fragments/redirects and are rechecked before bounded egress;
- terminal webhook payloads are sanitized and HMAC-signed over exact bytes;
  signing material is derived from a file-mounted master key and never logged;
- credential-management and public create routes enforce request-size and rate
  bounds, while guessed identifiers grant no access.

Automated evidence lives in `tests/security`, the Chromium E2E suite and
[`docs/acceptance/evidence/SLICE_1.md`](docs/acceptance/evidence/SLICE_1.md)
[`docs/acceptance/evidence/SLICE_2.md`](docs/acceptance/evidence/SLICE_2.md)
and [`docs/acceptance/evidence/SLICE_3.md`](docs/acceptance/evidence/SLICE_3.md).
These controls are a Local Preview boundary, not a production deployment
certification.
