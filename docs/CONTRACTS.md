# Canonical contracts

## Source of truth

Canonical contracts хранятся как JSON Schema 2020-12 в `contracts/schemas`. Из них генерируются:

- Pydantic models для API и workers;
- TypeScript types и validators для Web;
- OpenAPI fragments;
- fixtures и compatibility tests.

Generated files не редактируются вручную. Python или TypeScript class не может самостоятельно расширить canonical contract.

## Versioning rules

- Каждый root document содержит `schema_version`.
- Совместимые additions меняют minor version.
- Удаление, переименование или semantic change требует major version.
- Migration — детерминированная pure transform `N → N+1`.
- Published version никогда не переписывается миграцией.
- Import или edit старой версии создаёт новый draft в текущей schema.
- Runtime объявляет точный диапазон поддерживаемых schema versions.

## Slices 1–3 contract set

### Authoring and versioning

- `AgentSpec`
- `NodeSpec`
- `EdgeSpec`
- `PortSpec`
- `AgentDraft`
- `AgentVersion`
- `InterfaceSchema`

### Models and tools

- `ModelProfile`
- `ModelCapabilities`
- `ToolManifest`
- `CredentialReference`
- `PolicyRef`

### Execution

- `RunRequest`
- `RunEvent`
- `RunOutcome`
- `RunTrace`
- `NodeExecution`
- `ErrorEnvelope`
- `UsageRecord`

### Publication and public delivery

- `Publication`
- `PublishRequest`
- `RollbackRequest`
- `PublicAgent`
- `PublicRunCreateRequest`
- `PublicRun`
- `PublicRunEvent`
- `ApiKeyCreateRequest`
- `ApiKeyCreateView`
- `WebhookCreateRequest`
- `WebhookCreateView`

## Required event envelope

Каждый `RunEvent` обязан содержать:

- `event_id`;
- `schema_version`;
- `run_id`;
- monotonic `sequence`;
- event `type`;
- server timestamp;
- optional `node_id`;
- redaction-safe payload;
- causation/correlation identifiers.

Delivery принимается как at-least-once. Consumers дедуплицируют `event_id`; resume использует последнюю подтверждённую `sequence`.

## Capability packs

AgentSpec хранит pack reference:

```text
pack_id
pack_version
configuration
interface
integrity_digest
```

Раскрытие pack не встраивает копию subgraph. Редактирование internal node создаёт fork с новым identity. Published version сохраняет resolved dependency lock.

## Provider extensions

Portable fields находятся в основном contract. Provider-specific настройки разрешены только в:

```text
extensions.<provider_namespace>
```

Adapter валидирует extension. Product-level modules не ветвятся по provider name.

## Contract acceptance

Для каждой schema нужны:

- минимальный valid example;
- полный valid example;
- invalid examples для обязательных invariants;
- canonical serialization fixture;
- Python/TypeScript round-trip;
- forward/backward compatibility expectation.

## Implemented Slice 0 surface

Версия `v0.1.0` находится в
[`contracts/schemas/v0.1.0`](../contracts/schemas/v0.1.0/) и включает:

- authoring: `AgentSpec`, `NodeSpec`, `ModelProfile`, `ToolManifest`,
  `InterfaceSchema`, `AgentVersion`;
- execution: `RunRequest`, `RunEvent`, `RunTrace`, `ErrorEnvelope`;
- общие identifiers, locale, digest и extension definitions.

JSON Schema проверяет структуру документа. Инварианты, которым нужна
междокументная или графовая проверка, реализованы отдельно и одинаково
проверяются Python и TypeScript:

- уникальность node/edge identifiers и отсутствие dangling edges;
- отсутствие secret-like keys вне credential references;
- строгая последовательность событий;
- корректные causation references;
- единственное терминальное событие и согласованное состояние run;
- наличие redaction policy.

Единый список примеров находится в
[`contracts/examples/v0.1.0/manifest.json`](../contracts/examples/v0.1.0/manifest.json).
Каждый consumer обязан получить ожидаемый результат для каждой записи
manifest.

## Local conformance commands

```bash
uv run pytest tests/contracts -q
pnpm check:contracts
pnpm test:contracts
```

CI выполняет те же проверки с frozen lockfiles. Новая schema или semantic
invariant не принимается без positive и negative fixture и результата в обеих
реализациях.

## Slice 2 draft contract

`AgentDraft` is now an executable generated contract, not a prospective name.
Its canonical fields are:

- `agent_spec` — the only runtime-semantic document;
- `digest` — SHA-256 of canonical AgentSpec JSON;
- `revision` — optimistic concurrency token;
- `base_version_id` — immutable source/snapshot lineage;
- `layout` — presentation-only node coordinates and viewport;
- `updated_at` — server timestamp.

Python and TypeScript types are generated from the same JSON Schema. Draft
semantic validation returns stable `code`, `json_pointer`, `node_id` and
`message_key`. A layout-only update advances `revision` while preserving the
AgentSpec digest; a semantic update advances both. Test execution resolves the
saved revision to an immutable AgentVersion snapshot before entering the
existing `RunRequest`/`RunEvent`/`RunTrace` path.

The authenticated HTTP surface is documented in
[`SLICE_2_ONE_SPEC_TWO_EDITORS.md`](acceptance/SLICE_2_ONE_SPEC_TWO_EDITORS.md).

## Slice 3 publication contracts

Publication and public delivery use narrow generated contracts over the same
immutable AgentVersion:

- `Publication` exposes the active pointer, draft revision/digest, immutable
  version summaries and append-only traffic events to the owner;
- `PublishRequest` and `RollbackRequest` carry both compare-and-swap tokens;
- `PublicAgent` projects only localized copy, validated `InterfaceSchema` and
  selected version identity;
- `PublicRun` and `PublicRunEvent` omit prompts, tool/provider configuration,
  trace data and internal workflow identifiers;
- API-key and webhook create views contain one-time secret material only in
  the create response; list responses use separate non-secret projections.

The exact endpoint, scope, idempotency, stream and webhook requirements are
documented in
[`SLICE_3_PUBLISHING_VERSIONS.md`](acceptance/SLICE_3_PUBLISHING_VERSIONS.md).

## Runtime handoff

Runtime обязан реализовать эти контракты без собственной конкурирующей модели.
Точный golden path, recovery, idempotency, streaming и security gates описаны
в
[`docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md`](acceptance/SLICE_1_EXECUTABLE_SPINE.md).
