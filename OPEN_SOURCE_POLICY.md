# Open-source and third-party component policy

This is an internal engineering policy and must be confirmed by a proper legal/license review before commercial distribution.

## 1. Goals

- avoid rebuilding mature generic infrastructure;
- preserve the ability to offer hosted and self-hosted editions;
- prevent license contamination and attribution loss;
- make every imported component and asset traceable.

First-party repository code uses Apache-2.0 for the Foundation baseline. This choice and all third-party conclusions require a proper legal review before commercial distribution.

## 2. Required metadata

For every dependency, copied component, imported integration or asset:

- project/source URL;
- exact version or commit;
- license identifier;
- copyright notice;
- modifications;
- distribution obligations;
- whether hosted competitive use is allowed;
- security owner;
- upgrade path.

## 3. Preliminary policy

Generally easier to adopt after audit:

- MIT;
- BSD-2-Clause;
- BSD-3-Clause;
- Apache-2.0;
- ISC.

Case-by-case review:

- MPL;
- LGPL;
- copyleft components used as separate services;
- dual-licensed projects.

Do not embed into the product without explicit approval:

- AGPL;
- SSPL;
- Elastic/source-available licenses;
- sustainable-use/non-compete licenses;
- code with missing or ambiguous license;
- assets whose documentation is public but redistribution is not permitted.

## 4. UI reuse

- use permissive graph/layout primitives where possible;
- do not copy a competitor pixel-for-pixel;
- maintain an independent design system;
- preserve required notices;
- prefer isolated reusable components over a permanent fork of a large monorepo;
- any substantial frontend fork requires an ADR and maintenance estimate.

## 5. Candidate components

The following are candidates only and require a current audit before adoption:

- graph/canvas engine;
- AI-oriented workflow editor components;
- integration packages;
- agent framework adapters;
- model gateway;
- telemetry;
- eval runners;
- prompt optimizers;
- document parsers/generators.

The architecture must not assume a candidate is approved until its ADR is merged.

Candidate review records live in `third_party/candidates.yaml`. An exact dependency version and integrity lock are required before installation.

## 6. Asset provenance

Every prompt, skill, blueprint and eval pack records:

- author/source;
- license;
- version;
- modifications;
- permitted uses;
- benchmark evidence.

The AI Builder may not silently copy unverified external assets into first-party Recommended assets.
