# Frontend sources and reuse boundaries

**Reviewed:** 2026-07-24

Universal Agent Studio owns its information architecture, visual language, design tokens, node system and AgentSpec projection. External libraries may supply generic primitives, not product identity or runtime semantics.

## Approved direction

| Area | Decision | Source | License | Boundary |
|---|---|---|---|---|
| Application framework | Next.js + React | [vercel/next.js](https://github.com/vercel/next.js), [facebook/react](https://github.com/facebook/react) | MIT | Application/runtime primitives; no Vercel service dependency |
| Graph interaction | React Flow | [xyflow/xyflow](https://github.com/xyflow/xyflow) | MIT | Replaceable canvas view model; never canonical graph storage |
| Styling | First-party tokens and CSS variables | This repository | Apache-2.0 | No copied product theme |
| Localization | ICU-compatible message layer | Candidate selected before Slice 1 | Not selected | No hard-coded user-facing copy |

## Candidates requiring an implementation-time audit

| Area | Candidate | Source | Observed license | Required review |
|---|---|---|---|---|
| Accessible behavior primitives | Radix Primitives | [radix-ui/primitives](https://github.com/radix-ui/primitives) | MIT | Exact packages/version, bundle/accessibility test, upgrade owner |
| Icons | Lucide | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | ISC with inherited Feather considerations | Selected subset, notices, brand-icon exclusion |
| Prompt/schema/code editing | CodeMirror 6 packages | [codemirror.net](https://codemirror.net/) | MIT | Active package sources, mobile/a11y behavior, exact package list |

Mention in this file is not installation approval. Exact versions and integrity locks are recorded in `third_party/candidates.yaml` before a package enters a lockfile.

## Products used only as comparative research

Workflow products such as n8n, Langflow, Flowise and comparable agent studios may be examined to understand established interaction patterns:

- searchable node library;
- node inspector;
- execution highlighting;
- nested flows;
- keyboard workflows;
- trace navigation.

Their source code, icons, screenshots, copy, node designs, layouts and visual assets are not copied, vendored or forked. A substantial external frontend fork requires a new ADR, a license review and a maintenance-cost estimate.

## Projection boundary

```text
AgentSpec
  └─ first-party projection
       ├─ Simple Settings view model
       ├─ React Flow view model
       ├─ JSON/Developer view model
       └─ Published Interface view model
```

External UI types stop at the projection adapter. They do not appear in AgentSpec, API contracts, database records or runtime events.

## Adoption checklist

Before installing a frontend dependency:

1. record source URL, exact version/commit and integrity lock;
2. verify license and notices in the exact distributed package;
3. name a security owner and upgrade path;
4. document the narrow boundary it serves;
5. test keyboard, screen reader, reduced motion, RU/EN and 200% zoom;
6. reject any package that requires product contracts to depend on its internal types.
