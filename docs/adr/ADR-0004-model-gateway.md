# ADR-0004: Model gateway

**Status:** Accepted

**Date:** 2026-07-24

## Context

The product must switch providers without provider conditionals spreading through AgentSpec, runtime and UI.

## Decision

Define a first-party `ModelGatewayPort`, `ModelProfile` and capability contract. Implement a deterministic fake adapter first, then a generic OpenAI-compatible BYOK adapter. Native provider adapters are added only when they provide verified capabilities or policy behavior that the generic adapter cannot express.

Do not adopt a third-party multi-provider gateway in the core until a separate benchmark and license/operational ADR proves an advantage.

Portable parameters are canonical. Provider-specific parameters live under namespaced extensions and are validated by the adapter.

## Consequences

The initial provider surface is intentionally narrow. The product owns routing policy and provenance but avoids coupling its public model to a gateway vendor.
