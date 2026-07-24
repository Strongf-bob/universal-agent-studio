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
