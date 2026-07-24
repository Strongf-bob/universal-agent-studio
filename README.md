# Universal Agent Studio

> Local-first web-платформа для визуального создания, запуска, публикации и контролируемого улучшения AI-агентов.

## Статус

Проект находится на стадии **Foundation / Slice 0 (verification)**. Production-кода пока нет: архитектурные решения и канонические контракты уже зафиксированы, а их Python/TypeScript conformance проверяется локально и в CI.

Первый deployment target — локальная single-workspace установка с BYOK. После прохождения локальных acceptance gates та же сборка переносится на частный сервер.

## Зафиксированные решения

- Основной пользовательский интерфейс — web app.
- Основной программный интерфейс — публичный API.
- Telegram не входит в первый обязательный контур, но архитектура каналов должна позволить добавить его адаптером.
- Визуальный редактор обязателен и должен напоминать по удобству современные workflow-системы.
- Пользователь видит простой интерфейс по умолчанию и может раскрыть граф, параметры, промпты, модели, код и traces по мере необходимости.
- Платформа не привязывается к одному LLM-провайдеру или agent framework.
- Корректность, воспроизводимость и качество важнее скорости разработки.
- Публичный релиз не выполняется до прохождения полного набора критериев первой версии.
- Архитектура строится вокруг переиспользуемого Agent Kernel, capability-пакетов, blueprints и assets.
- Локализация закладывается с первого дня; первые локали — `ru-RU` и `en-US`.
- Канонические контракты описываются JSON Schema и генерируют Python/TypeScript types.
- Durable execution реализуется через порт ядра; первая реализация — Temporal.
- Canvas использует React Flow как заменяемый UI-примитив и не хранит отдельную модель агента.
- Первый репозиторий публичный; базовая лицензия first-party кода — Apache-2.0.

## Порядок разработки

1. **Slice 0 — Foundation:** ADR, contracts, invariants, fixtures и acceptance criteria.
2. **Slice 1 — Executable Spine:** один agent version запускается локально через Web и API, вызывает безопасный tool и сохраняет trace.
3. **Slice 2 — Minimal Studio:** simple settings и graph projection редактируют один AgentSpec.
4. Последующие slices добавляют publishing, providers, RAG, capability packs, AI Builder, evals и autoresearch.

Полная декомпозиция и границы каждого slice описаны в [ROADMAP.md](ROADMAP.md).

## Проверка контрактов

```bash
uv sync --frozen
pnpm install --frozen-lockfile
uv run pytest tests/contracts -q
pnpm check:contracts
pnpm test:contracts
```

Обе реализации валидируют один manifest с valid и invalid fixtures из
[`contracts/examples/v0.1.0`](contracts/examples/v0.1.0/). Первый runnable
сценарий заранее определён в
[acceptance-контракте Slice 1](docs/acceptance/SLICE_1_EXECUTABLE_SPINE.md).

## Основные документы

- [PRODUCT.md](PRODUCT.md) — спецификация продукта.
- [ARCHITECTURE.md](ARCHITECTURE.md) — первоначальная архитектура.
- [DESIGN.md](DESIGN.md) — UX и визуальные принципы.
- [AGENTS.md](AGENTS.md) — инструкции для coding agents.
- [SECURITY.md](SECURITY.md) — базовая модель безопасности.
- [EVALS.md](EVALS.md) — требования к тестированию AI-поведения.
- [LOCALIZATION.md](LOCALIZATION.md) — правила i18n/L10n.
- [OPEN_SOURCE_POLICY.md](OPEN_SOURCE_POLICY.md) — политика внешних компонентов.
- [ROADMAP.md](ROADMAP.md) — внутренний порядок реализации.
- [docs/DECISIONS.md](docs/DECISIONS.md) — принятые исходные решения.
- [docs/ARCHITECTURAL_INVARIANTS.md](docs/ARCHITECTURAL_INVARIANTS.md) — правила, которые нельзя нарушать реализацией.
- [docs/CONTRACTS.md](docs/CONTRACTS.md) — стратегия канонических схем.
- [contracts/schemas/v0.1.0/](contracts/schemas/v0.1.0/) — исполняемые JSON Schema 2020-12.
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — trust boundaries, attacker stories и severity.
- [docs/FRONTEND_SOURCES.md](docs/FRONTEND_SOURCES.md) — происхождение и границы frontend-компонентов.
- [docs/adr/](docs/adr/) — architecture decision records.
- [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) — решения, которые ещё предстоит принять.
- [CODEX_KICKOFF_PROMPT.md](CODEX_KICKOFF_PROMPT.md) — стартовый запрос для Codex.

## Правило начала разработки

До написания production-кода Slice 1 необходимо:

1. Прочитать все документы выше.
2. Зафиксировать противоречия и недостающие решения.
3. Принять блокирующие ADR.
4. Согласовать минимальные схемы `AgentSpec`, `NodeSpec`, `ModelProfile`, `ToolManifest`, `RunEvent`, `RunTrace`.
5. Утвердить executable acceptance contract Slice 1.

Не следует сначала писать красивый интерфейс, а затем пытаться подогнать под него runtime. Контракт агента и контракт исполнения должны появиться раньше полнофункционального canvas.

## Участие и лицензия

Правила изменений описаны в [CONTRIBUTING.md](CONTRIBUTING.md). First-party код распространяется по [Apache License 2.0](LICENSE); выводы по коммерческой дистрибуции и сторонним компонентам требуют отдельной юридической проверки.
