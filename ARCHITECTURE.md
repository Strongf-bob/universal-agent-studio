# Первоначальная архитектура

## 1. Архитектурный стиль

Рекомендуемый старт: **модульный монолит для control plane + отдельные изолированные workers для исполнения и autoresearch**.

Причина:

- не создавать преждевременную микросервисную сложность;
- сохранить чёткие границы модулей;
- вынести потенциально опасное и ресурсоёмкое выполнение из web/API процесса;
- позволить позднее разделить сервисы без изменения внешних контрактов.

## 2. Верхнеуровневая схема

```text
┌───────────────────────────────────────────────────────┐
│ Web Application                                      │
│ Workspace │ Canvas │ AI Builder │ Runs │ Research    │
└───────────────────────┬───────────────────────────────┘
                        │ REST / streaming events
                        ▼
┌───────────────────────────────────────────────────────┐
│ Control Plane API                                    │
│ Projects │ Agents │ Assets │ Models │ Tools          │
│ Versions │ Publishing │ Evals │ Auth │ Audit         │
└───────┬──────────────┬──────────────┬────────────────┘
        │              │              │
        ▼              ▼              ▼
 Execution Queue   Model Gateway   Integration Gateway
        │              │              │
        ▼              ▼              ▼
 Runtime Workers   Model Providers   MCP/OpenAPI/HTTP
        │
        ├──────────────► Trace/Event Store
        │
        └──────────────► Object Storage

 Research Queue
        │
        ▼
 Research Workers ─────► Evals / Candidate Versions
```

## 3. Канонические контракты

До активной разработки UI необходимо определить JSON Schema/Pydantic/TypeScript-типы:

- `AgentSpec`;
- `NodeSpec`;
- `EdgeSpec`;
- `CapabilityPackManifest`;
- `BlueprintManifest`;
- `ModelProfile`;
- `ModelCapabilities`;
- `ToolManifest`;
- `CredentialReference`;
- `InterfaceSchema`;
- `AssetManifest`;
- `EvalPack`;
- `RunRequest`;
- `RunEvent`;
- `RunTrace`;
- `AgentVersion`;
- `CandidateVersion`;
- `ApprovalRequest`.

Контракты хранятся в отдельном versioned package и являются источником истины для frontend, API и workers.

## 4. Структура репозитория

```text
/
├── apps/
│   ├── studio-web/             # authenticated builder/operator surface
│   ├── published-web/          # least-privilege end-user surface
│   └── control-api/            # FastAPI/Python control plane
├── workers/
│   ├── runtime/                # исполнение AgentSpec
│   ├── researcher/             # candidate generation
│   └── sandbox/                # isolated code execution
├── contracts/
│   ├── schemas/                # canonical JSON Schema
│   ├── examples/               # valid/invalid fixtures
│   └── conformance/            # cross-language contract tests
├── libs/
│   ├── python/                 # kernel, gateways, generated models
│   └── typescript/             # API client, UI, canvas, localization
├── blueprints/
├── capabilities/
├── assets/
│   ├── prompts/
│   ├── skills/
│   ├── eval-packs/
│   └── policies/
├── docs/
│   ├── adr/
│   ├── superpowers/specs/
│   └── diagrams/
├── infra/
│   ├── docker/
│   └── migrations/
└── tests/
    ├── integration/
    ├── e2e/
    └── fixtures/
```

Используется монорепозиторий с `pnpm` для TypeScript и `uv`/`pyproject.toml` для Python. JSON Schema 2020-12 является canonical source; генерация типов между языками автоматизирована.

## 5. Рекомендуемый технологический baseline

### Frontend

- React / Next.js / TypeScript;
- React Flow за product-owned projection/adapter;
- собственная design system поверх доступной component library;
- i18n framework с ICU message format;
- streaming run events;
- code editor для prompts/config/code nodes.

### Backend

- FastAPI/Python;
- PostgreSQL;
- object storage с S3 API;
- Redis только для transient cache/queue при необходимости;
- `DurableExecutionPort` с Temporal как первой реализацией;
- OpenTelemetry;
- background workers.

### Agent runtime

- собственный интерпретатор `AgentSpec`;
- framework adapters для agent nodes;
- typed inputs/outputs;
- explicit state;
- tool gateway;
- model gateway;
- sandboxed code nodes.

Runtime не должен напрямую зависеть от структуры frontend canvas.

### Model gateway

- единый внутренний интерфейс;
- provider adapters;
- capability discovery;
- fallback;
- budgets;
- rate limits;
- usage accounting;
- BYOK support.

### Integration gateway

- MCP;
- OpenAPI;
- generic HTTP;
- webhooks;
- database adapters;
- first-party integrations;
- credentials references.

## 6. Execution model

Каждый run:

1. фиксирует `agent_version_id`;
2. валидирует AgentSpec;
3. разрешает model profiles и tool references;
4. создаёт durable execution;
5. публикует структурированные события;
6. хранит node inputs/outputs с redaction;
7. поддерживает pause/resume;
8. завершает run с итоговым outcome и metrics.

События должны быть пригодны и для UI, и для observability:

```text
run.started
node.started
model.requested
model.completed
tool.requested
approval.required
approval.resolved
node.failed
node.completed
run.completed
run.failed
```

## 7. Версионирование

Draft агента может изменяться. Published version неизменяема.

```text
Agent
├── Draft
├── Version 1
├── Version 2
└── Version 3
```

Run всегда связан с конкретной published version или snapshot draft.

Rollback — смена активной published version без изменения исторических данных.

## 8. Capability packs

Capability pack — versioned subgraph с публичными входами, выходами и настройками.

```text
RAG Pack
├── public inputs
├── public outputs
├── simple settings
├── advanced settings
└── internal subgraph
```

Пользователь может:

- использовать pack как один узел;
- раскрыть внутренний граф;
- fork-нуть pack;
- обновить версию;
- сравнить изменения.

## 9. Publishing

### Web App

Runtime и UI разделены. Published app получает `InterfaceSchema` и отображает:

- form;
- chat;
- files;
- progress;
- result;
- actions;
- approval.

### API

- sync для коротких операций;
- async run API;
- streaming events;
- webhook completion;
- idempotency keys;
- API keys/scopes;
- generated OpenAPI schema.

## 10. Autoresearch

Research worker не имеет production credentials и не изменяет published version напрямую.

Он получает:

- immutable agent snapshot;
- redacted traces;
- datasets;
- mutation contract;
- budget;
- eval policy.

Результат:

- candidate version;
- diff;
- eval report;
- risk report;
- provenance;
- human-readable rationale.

## 11. Решения, требующие ADR

До реализации необходимо создать минимум:

- ADR-0001: repository and language boundaries;
- ADR-0002: durable execution engine;
- ADR-0003: frontend OSS reuse strategy;
- ADR-0004: model gateway implementation;
- ADR-0005: code sandbox;
- ADR-0006: authentication and tenancy;
- ADR-0007: AgentSpec versioning and migrations.
