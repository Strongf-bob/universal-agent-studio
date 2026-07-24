# Delivery roadmap

Разработка идёт сквозными slices. Каждый slice заканчивается работающим пользовательским сценарием, проверками и демонстрацией. Поздняя фаза может расширять механизм, но не вводить задним числом базовые требования security, localization, provenance или evals.

## Термины релизов

- **Foundation:** документация и контракты; production runtime отсутствует.
- **Local Preview:** slices запускаются локально владельцем проекта.
- **Server Preview:** та же версия развёрнута на частном сервере.
- **Private Alpha:** все обязательные архитектурные поверхности доступны с ограниченной шириной.
- **Public Release:** выполнены все release gates из `PRODUCT.md`.

## Slice 0 — Foundation and contracts

**Цель:** сделать начало реализации однозначным.

**Статус:** complete — contracts и fixtures реализованы; локальные и
GitHub Actions gates пройдены.

- архитектурные invariants и trust boundaries;
- ADR-0001…ADR-0007;
- каноническая стратегия JSON Schema;
- минимальное семейство AgentSpec/Run contracts;
- valid и invalid fixtures;
- cross-language conformance plan;
- dependency/license registry format;
- acceptance contract Slice 1.

**Выход:** владелец одобрил design spec; блокирующие ADR приняты; схемы и
acceptance examples не содержат незакрытых placeholders. Точный исполняемый
сценарий закреплён в
[`docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md`](docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md).

## Slice 1 — Local executable spine

**Цель:** доказать путь от immutable AgentSpec до результата и trace.

- импорт одного golden AgentSpec;
- validation и immutable AgentVersion с digest;
- локальный Web runner и REST API;
- deterministic fake model для CI;
- opt-in OpenAI-compatible BYOK adapter;
- безопасный first-party calculator tool;
- structured output;
- Temporal workflow через `DurableExecutionPort`;
- resumable stream структурированных RunEvents;
- persisted redacted RunTrace;
- read-only graph/trace projection;
- RU/EN для пользовательского потока.

**Control scenario:** input → model → tool → structured output → trace.

**Не входит:** editable canvas, RAG, code nodes, AI Builder, autoresearch.

**Выход:** deterministic E2E проходит без внешней сети; ручной BYOK smoke test проходит отдельно; секрет отсутствует в AgentSpec, events, trace и browser bundle.

## Slice 2 — One spec, two editors

**Цель:** доказать progressive disclosure без второй модели данных.

- simple settings;
- React Flow canvas;
- node inspector;
- save/load draft;
- generated contract types;
- validation errors на поле и узле;
- keyboard-accessible graph alternative;
- test console и run highlighting;
- preview diff перед AI-generated или bulk changes.

**Control scenario:** изменить один draft через simple form и canvas, получить один и тот же canonical AgentSpec, запустить и увидеть результат.

## Slice 3 — Publishing and versions

- published Web App;
- sync/async REST API;
- API keys и scopes;
- streaming resume;
- signed webhooks;
- immutable versions;
- active-version pointer;
- rollback без изменения истории.

**Control scenario:** publish v1 → publish v2 → переключить traffic обратно на v1.

## Slice 4 — Models and integrations

- Model Hub и capability matrix;
- provider adapters, fallback и budgets;
- CredentialReference lifecycle;
- HTTP, OpenAPI и MCP tool adapters;
- side-effect classification;
- approval и idempotency policies.

**Control scenario:** заменить provider без изменения graph; несовместимая или запрещённая модель блокируется fail-closed.

## Slice 5 — Knowledge and RAG

- ingestion pipeline;
- object storage;
- chunk and embedding provenance;
- retriever contract;
- production-quality citation path;
- RAG eval pack;
- RAG capability pack как versioned subgraph.

**Control scenario:** загрузить источник → задать вопрос → получить grounded answer → открыть точную citation provenance.

## Slice 6 — Approvals, automation and documents

- durable human approval;
- webhook trigger;
- conditions, retries и compensation policy;
- Document Pack;
- export artifacts;
- isolated sandbox contract and implementation for code nodes.

**Control scenario:** принять файл → выполнить workflow → остановиться на approval → возобновиться → выдать проверенный artifact.

## Slice 7 — AI Builder and assets

- blueprint selection;
- asset manifests и provenance;
- natural-language draft generation;
- plan/diff preview;
- compatibility checks;
- controlled application to draft.

**Control scenario:** natural-language request → reviewed diff → editable and runnable agent.

## Slice 8 — Evals and controlled autoresearch

- datasets, regression runner и hidden holdout;
- candidate versions;
- mutation allowlist и budget;
- Agent Researcher;
- Platform Researcher;
- comparison UI;
- manual promotion only.

**Control scenario:** failure → candidate → eval → human promotion → publish → rollback.

## Slice 9 — Server deployment and hardening

- reproducible private-server deployment;
- backup/restore;
- migration and disaster-recovery tests;
- retention and deletion;
- sandbox hardening;
- performance budgets;
- RU/EN completeness;
- accessibility and visual regression;
- import/export;
- operator documentation.

## Private Alpha gate

- slices 1–9 pass their acceptance contracts;
- all runs bind to immutable version or snapshot digest;
- no critical security findings;
- license registry is complete;
- migrations and rollback are tested;
- no user flow requires manual database changes.
