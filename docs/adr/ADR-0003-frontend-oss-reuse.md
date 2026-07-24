# ADR-0003: Frontend open-source reuse

**Status:** Accepted

**Date:** 2026-07-24

## Context

A capable graph editor is expensive to recreate, but forking a workflow product would import its architecture, design and maintenance burden.

## Decision

Use `@xyflow/react` as a replaceable canvas rendering and interaction primitive. Do not fork an external workflow product or copy a competitor interface.

Maintain:

- product-owned graph projection between AgentSpec and canvas view models;
- product-owned node system and design tokens;
- accessible non-canvas representation;
- dependency/version/license entry before installation.

Pro examples or assets are not assumed to share the library license and require separate review.

## Consequences

React Flow accelerates interaction work without becoming a runtime model. Product-specific semantic zoom, pack navigation and node behavior remain first-party.

## Sources

- https://reactflow.dev/
- https://github.com/xyflow/xyflow
