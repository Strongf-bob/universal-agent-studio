# Universal Agent Studio

> Local-first web-платформа, в которой один AI-агент остаётся понятным
> приложением для пользователя и раскрывается до версий, графа, событий,
> trace, моделей, tools и API для инженера.

[![Slice 1–3 Local Preview](https://github.com/Strongf-bob/universal-agent-studio/actions/workflows/slice1.yml/badge.svg?branch=main)](https://github.com/Strongf-bob/universal-agent-studio/actions/workflows/slice1.yml)
[![Contract Conformance](https://github.com/Strongf-bob/universal-agent-studio/actions/workflows/contracts.yml/badge.svg?branch=main)](https://github.com/Strongf-bob/universal-agent-studio/actions/workflows/contracts.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-0b8793.svg)](LICENSE)
[![RU / EN](https://img.shields.io/badge/UI-ru--RU%20%7C%20en--US-172331.svg)](LOCALIZATION.md)

## Уже работает

Slices 1–3 — это локальная исполняемая платформа, а не макет интерфейса:

- immutable `AgentVersion` с каноническим digest;
- PostgreSQL-backed `AgentDraft` с revision и optimistic concurrency;
- Simple Settings, React Flow canvas, node inspector и keyboard table над
  одним canonical `AgentSpec`, без второй модели графа;
- save/load, field/node validation и non-mutating JSON diff preview;
- Test Console запускает immutable snapshot черновика без активации;
- Publish workspace создаёт immutable versions, ведёт append-only ledger и
  переключает traffic pointer без изменения истории;
- отдельный least-privilege Published Web App рендерит только
  `InterfaceSchema`, работает в RU/EN и не получает Studio session или trace;
- scoped API keys, sync/async public API, opaque per-run browser capability,
  resumable SSE и подписанные terminal webhooks;
- видимый Web-путь setup → JSON import → validation → activation;
- local owner, Argon2id, opaque session, CSRF и project scope;
- Web + REST API на одном контракте;
- Temporal workflow, resumable SSE и idempotent run creation;
- deterministic model → allowlisted calculator → structured output;
- persisted redacted trace с attempt/timing/provenance, read-only graph и
  keyboard table;
- `ru-RU` / `en-US`, сохранение текущего run при смене языка;
- opt-in OpenAI-compatible BYOK adapter за явным origin allowlist;
- Docker Compose с отдельными PostgreSQL и Temporal volumes.

![Published Web App выполняет опубликованную версию и показывает только структурированный результат](assets/readme/slice3-public.png)

Скриншот отдельного public origin после реального запуска `19 × 23`. Published
App не показывает AgentSpec, prompt, tool configuration или trace.

![Publish workspace с immutable v1 и v2, active traffic pointer и append-only ledger](assets/readme/slice3-publish.png)

Скриншот доказывает контрольный путь `publish v1 → publish v2 → rollback v1`;
байты обеих версий и прошлых run остаются неизменными.

![Реальный Build workspace: простые настройки, граф и инспектор одного AgentSpec](assets/readme/slice2-editor.png)

Скриншот создан из production build запущенного локального стека. Изменения
формы, canvas, inspector и JSON preview сходятся в один server-backed draft.

![Реальный завершённый запуск: события, структурированный результат и trace](assets/readme/slice1-run.png)

Скриншот создан из фактически запущенного локального стека. Golden input
`19 × 23` возвращает `{"value":437}` и сохраняет восемь упорядоченных событий.

## Запуск локально

Нужны Docker Desktop (или Docker Engine + Compose v2), Node.js 26,
pnpm 11.7.0, Python 3.14 и uv 0.11.32.

```bash
uv sync --all-packages --frozen
pnpm install --frozen-lockfile
pnpm dev:local
```

После readiness:

- Studio: <http://localhost:3000/ru-RU/setup>
- Published Web App: <http://localhost:3301/ru-RU/agents/calculator-agent>
- Control API: <http://localhost:8000/health/ready>
- Temporal UI: <http://localhost:8080>

Первый воспроизводимый walkthrough, включая setup, импорт/активацию fixture,
редактирование draft двумя представлениями, validation/diff preview, draft
snapshot run, publication v1/v2, scoped credentials, rollback, отдельный
Published Web App, public SSE resume, locale switch, trace inspection,
cancellation и login:

```bash
pnpm --filter @universal-agent-studio/studio-web exec playwright install chromium
pnpm test:e2e
```

Остановка сохраняет локальные данные:

```bash
pnpm local:down
```

Полный reset требует точной явной фразы и ownership marker; он удаляет только
Compose volumes и принадлежащую проекту `.local` state directory:

```bash
pnpm local:reset -- --confirm "RESET LOCAL DATA"
```

Подробности, порты, диагностика и BYOK smoke описаны в
[локальном operator guide](docs/operations/LOCAL_PREVIEW.md).

## Один контракт, несколько представлений

```mermaid
flowchart LR
    Spec["Canonical AgentSpec draft"] --> Simple["Simple Settings"]
    Spec --> Graph["Canvas + Inspector + Keyboard Table"]
    Simple --> Save["Validated revision + digest"]
    Graph --> Save
    Save --> Snapshot["Immutable test snapshot"]
    Snapshot --> Version["AgentVersion + digest"]
    Save --> Publish["Publish with CAS"]
    Publish --> Version
    Publish --> Ledger["Append-only publication ledger"]
    Ledger --> Pointer["Active-version pointer"]
    Version --> API["Control API"]
    API --> Temporal["Temporal workflow"]
    Temporal --> Kernel["Provider-neutral Agent Kernel"]
    Kernel --> Tool["Allowlisted calculator"]
    Kernel --> Events["Persisted RunEvents"]
    Kernel --> Trace["Redacted RunTrace"]
    Events --> Web["Web runner + SSE resume"]
    Trace --> Web
    Version --> Web
    Pointer --> PublicAPI["Scoped public API"]
    Pointer --> PublicWeb["Published Web App"]
    PublicAPI --> Temporal
    PublicWeb --> PublicAPI
    Trace --> Webhook["Sanitized signed terminal webhook"]
```

`AgentSpec` — единственный источник runtime-семантики. Canvas хранит отдельно
только layout, Web не сохраняет вторую модель графа, runtime не зависит от
конкретного LLM provider, а durable execution скрыт за портом ядра.

## Проверка

```bash
pnpm check
pnpm test:contracts
pnpm test:web
uv run pytest -q
pnpm test:e2e
uv run pytest tests/security tests/integration -q
```

Обязательный GitHub Actions gate собирает контейнеры, мигрирует чистую БД,
поднимает полный stack и выполняет Chromium E2E без внешнего LLM.
BYOK smoke запускается только явно и не входит в обязательный CI.

## Границы текущего preview

Slices 1–3 доказывают путь `draft → immutable version → published Web/API →
version-bound run → rollback`, сохраняя исходный runtime и trace-контур.
Создание/удаление topology, node library, AI Builder, RAG, arbitrary HTTP/code
nodes, MCP, multi-user administration, Internet deployment, eval campaigns и
autoresearch начинаются в последующих slices.

Порядок развития зафиксирован в [ROADMAP.md](ROADMAP.md), а точные release
gates — в acceptance-контрактах
[Slice 1](docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md),
[Slice 2](docs/acceptance/SLICE_2_ONE_SPEC_TWO_EDITORS.md) и
[Slice 3](docs/acceptance/SLICE_3_PUBLISHING_VERSIONS.md).

## Архитектурные и security-документы

- [PRODUCT.md](PRODUCT.md) — продукт и progressive disclosure.
- [ARCHITECTURE.md](ARCHITECTURE.md) — границы control plane, runtime и kernel.
- [DESIGN.md](DESIGN.md) — UX, визуальный язык и accessibility.
- [docs/CONTRACTS.md](docs/CONTRACTS.md) — JSON Schema и generated types.
- [docs/ARCHITECTURAL_INVARIANTS.md](docs/ARCHITECTURAL_INVARIANTS.md) — неизменяемые правила.
- [docs/adr/](docs/adr/) — принятые архитектурные решения.
- [SECURITY.md](SECURITY.md) и [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — policy и attacker stories.
- [EVALS.md](EVALS.md) — будущий eval/autoresearch контур.
- [OPEN_SOURCE_POLICY.md](OPEN_SOURCE_POLICY.md) и [third_party/candidates.yaml](third_party/candidates.yaml) — provenance и лицензии.

## Участие и лицензия

Правила изменений находятся в [CONTRIBUTING.md](CONTRIBUTING.md).
First-party код распространяется по [Apache License 2.0](LICENSE).
Сторонние компоненты имеют собственные лицензии и фиксируются в registry.
