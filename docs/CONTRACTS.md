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

## Slice 1 contract set

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
