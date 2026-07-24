# Universal Agent Studio — спецификация продукта

**Версия:** 0.2

**Статус:** Foundation / private product definition

**Главный первый пользователь:** владелец проекта

**Основной принцип:** простота по умолчанию, полная глубина по требованию

## 1. Краткое описание

Universal Agent Studio — web-платформа, в которой пользователь может:

1. описать задачу естественным языком;
2. получить собранного AI-агента или workflow;
3. увидеть его в визуальном редакторе;
4. при необходимости раскрыть каждый уровень до промпта, модели, параметров, кода и trace;
5. подключить модели, знания, инструменты и интеграции;
6. протестировать поведение;
7. опубликовать агента как web-приложение или API;
8. собирать обратную связь и диагностические данные;
9. создавать проверенные улучшения с помощью autoresearch-контура;
10. вернуться к предыдущей рабочей версии при регрессии.

Платформа не является «конструктором документных агентов». Документы, RAG и генерация файлов — важные capability-пакеты и контрольные сценарии, но ядро должно одинаково поддерживать помощников, автоматизации, исследовательских агентов, knowledge agents и прикладные бизнес-процессы.

## 2. Проблема

Сегодня создание агента часто распадается на несвязанные части:

- прототипирование промпта;
- программирование runtime;
- подключение инструментов;
- настройка RAG;
- выбор модели;
- визуальная оркестрация;
- публикация интерфейса;
- логи и evals;
- улучшение после запуска.

No-code-системы часто скрывают слишком много, а framework-first решения требуют слишком много кода. Пользователю нужен один продукт, в котором сложность раскрывается постепенно и не теряется возможность программного контроля.

## 3. Целевой результат

Пользователь пишет:

> Создай агента, который принимает файлы и вопросы, использует мою базу знаний, при необходимости вызывает API, формирует структурированный результат и публикуется как web-приложение.

Система:

- выбирает подходящий blueprint;
- подключает capability-пакеты;
- подбирает проверенные skills и prompts;
- назначает модельные профили;
- создаёт граф;
- формирует базовые evals;
- выполняет тестовый запуск;
- показывает понятное объяснение и полный визуальный workflow;
- позволяет вручную изменить любой уровень;
- публикует стабильную версию через Web и API.

## 4. Пользователи

### 4.1. Builder

Первичный пользователь. Хочет быстро создавать полезных агентов, но сохранять полный контроль над архитектурой и кодом.

### 4.2. End User

Пользуется опубликованным агентом через web-интерфейс и не обязан видеть внутренний граф.

### 4.3. Developer

Работает с AgentSpec, API, code nodes, интеграциями, тестами и runtime.

### 4.4. Operator

Следит за запусками, ошибками, качеством, стоимостью и версиями.

### 4.5. Organization Administrator

Позднее управляет моделями, credentials, permissions, политиками и изоляцией данных.

## 5. Продуктовые принципы

1. **Один агент — несколько уровней представления.** Простая настройка, визуальный граф и код описывают одну сущность.
2. **Visual-first, но не visual-only.** Всё существенное доступно через API и сериализуемую спецификацию.
3. **Composition over monolith.** Тонкое ядро плюс capability-пакеты и blueprints.
4. **Provider-agnostic.** Модель выбирается через профили и capability-проверки.
5. **Traceable by default.** Каждая версия, модель, tool call и изменение отслеживаются.
6. **Human-controlled improvement.** Autoresearch создаёт кандидатов, но не изменяет production без разрешения.
7. **Correctness before speed.** Первая публичная версия выпускается только после прохождения определённых критериев.
8. **Localization from day zero.**
9. **Open interfaces.** REST, webhooks, MCP/OpenAPI adapters и экспортируемые форматы.
10. **Open-source leverage without license debt.**

## 6. Уровни интерфейса

### 6.1. Published Agent App

Пользователь видит форму, чат, файлы, результат и действия. Граф и технические параметры отсутствуют.

### 6.2. Simple Configuration

Доступны назначение, инструкция, знания, инструменты, модельные профили, интерфейс и правила подтверждения.

### 6.3. Visual Studio

Полный workflow: узлы, связи, ветвления, циклы, ошибки, parallel execution, human approval, subflows и capability-пакеты.

### 6.4. Developer/Operations

Промпты, code nodes, AgentSpec, API, traces, evals, версии, расходы, diff и autoresearch-кандидаты.

## 7. Основные модули

### 7.1. Workspace

- мои агенты;
- создание агента;
- blueprints и templates;
- models;
- integrations;
- assets;
- runs;
- research lab.

### 7.2. AI Builder

- принимает описание задачи;
- задаёт только действительно необходимые уточнения;
- ищет подходящие blueprints, skills и prompts;
- собирает AgentSpec;
- создаёт или изменяет граф;
- объясняет изменения;
- формирует тестовые примеры;
- не применяет рискованные изменения без подтверждения.

### 7.3. Visual Canvas

- drag-and-drop;
- поиск блоков;
- вложенные и сворачиваемые группы;
- semantic zoom;
- node inspector;
- data preview;
- live execution state;
- test console;
- undo/redo;
- keyboard navigation;
- светлая и тёмная темы.

### 7.4. Agent Kernel

Минимальное универсальное ядро:

- унифицированный ввод и вывод;
- сессии и состояние;
- model routing;
- tool execution;
- permissions и approvals;
- retries, timeouts и errors;
- structured output;
- traces;
- version binding;
- channel-independent response schema.

### 7.5. Capability Packs

Первая версия должна иметь рабочие реализации следующих пакетов:

- RAG;
- Documents;
- Human Approval;
- Automation;
- Research;
- Multimodal Input;
- Web Publishing;
- API Publishing.

Пакет можно отображать одним блоком и раскрывать до внутреннего подграфа.

### 7.6. Model Hub

- провайдеры и credentials;
- OpenAI-compatible endpoints;
- model profiles: `Fast`, `Smart`, `Vision`, `Private`, `Researcher`, `Embeddings`;
- capability matrix;
- primary/fallback;
- ограничения стоимости и контекста;
- override на уровне узла;
- сравнение моделей на eval-наборе;
- предупреждение о несовместимости.

### 7.7. Integration Hub

Способы подключения:

- MCP;
- OpenAPI;
- HTTP;
- webhook;
- database adapters;
- code node;
- integration SDK.

Первая версия должна включать небольшой качественный набор универсальных интеграций, а не сотни плохо поддерживаемых коннекторов.

### 7.8. Asset Library

Типы assets:

- system prompts;
- skills;
- agent blueprints;
- subflows;
- integration recipes;
- eval packs;
- policy packs;
- interface templates.

Каждый asset имеет:

- версию;
- происхождение;
- лицензию;
- совместимость;
- локали;
- eval-набор;
- метрики;
- статус: Experimental / Verified / Recommended / Deprecated.

### 7.9. Runtime and Runs

- durable execution;
- хранение состояния;
- pause/resume;
- retries;
- human approval;
- отмена;
- streaming events;
- изоляция code nodes;
- полные структурированные traces;
- привязка каждого запуска к версии агента.

### 7.10. Publishing

Обязательно в первой версии:

- отдельное web-приложение агента;
- REST API;
- API keys;
- streaming;
- webhooks;
- configurable interface schema.

Telegram и другие каналы подключаются позднее через channel adapter.

### 7.11. Evals and Quality

- deterministic assertions;
- datasets;
- regression suite;
- model comparison;
- tool-call validation;
- RAG citation checks;
- LLM-as-judge только как один из сигналов;
- cost и latency metrics;
- hidden holdout для autoresearch.

### 7.12. Autoresearch

Два контура:

1. **Agent Researcher** — улучшает конкретного агента по traces, feedback и evals.
2. **Platform Researcher** — улучшает blueprints, prompts, skills и общую базу практик.

Первая версия:

- обнаруживает проблему;
- создаёт кандидата;
- запускает evals;
- показывает diff и сравнение;
- позволяет вручную создать новую версию;
- не публикует изменения автоматически.

### 7.13. Localization

- `ru-RU` и `en-US`;
- все UI-строки через translation keys;
- отдельные локализованные prompts;
- независимые язык интерфейса, язык общения и язык результата;
- locale-aware даты, числа, валюты и форматы;
- UI не должен ломаться на длинных переводах.

### 7.14. Versioning

Версионируются:

- AgentSpec;
- graph;
- prompts;
- skills;
- models;
- tools;
- knowledge configuration;
- interface;
- eval configuration.

Новая публикация создаёт неизменяемую версию. Должна быть возможность вернуть трафик на предыдущую версию.

## 8. Scope Private Alpha

Private Alpha должна покрывать все ключевые архитектурные поверхности, но не обязана иметь максимальную ширину. Она достигается последовательностью end-to-end slices из `ROADMAP.md`; Local Preview начинается значительно раньше и не считается незавершённым публичным релизом.

### Обязательно

- Workspace;
- AI Builder;
- Visual Canvas;
- AgentSpec;
- Agent Kernel;
- RAG Pack;
- Document Pack;
- Human Approval Pack;
- базовый Automation Pack;
- Model Hub;
- Integration Hub;
- Asset Library;
- Web App publishing;
- REST API;
- Runs и traces;
- Evals;
- Versioning;
- ручной rollback;
- Agent Researcher prototype;
- Platform Researcher prototype;
- RU/EN;
- безопасность code nodes и credentials;
- импорт/экспорт проекта.

### Допустимая ограниченная ширина

- 2–3 реально проверенных model providers плюс custom OpenAI-compatible;
- 10–20 first-party nodes;
- 5–10 универсальных интеграций;
- 3–5 blueprints;
- 10–20 prompts/skills;
- один production-quality RAG pipeline;
- один production-quality document pipeline;
- один вариант web-интерфейса агента с настраиваемой схемой.

### Не входит в Private Alpha

- Telegram;
- marketplace;
- платежи;
- мобильное приложение;
- голосовые звонки;
- сотни нативных интеграций;
- enterprise SSO и сложный RBAC;
- автоматическое изменение production;
- обучение собственной LLM;
- полная переносимость произвольного framework-specific кода;
- преобразование любого Python-кода обратно в визуальный граф.

## 9. Контрольные пользовательские сценарии

### Сценарий A. Universal Knowledge Agent

- загрузить знания;
- задать вопрос;
- выполнить RAG;
- показать ответ и источники;
- открыть trace;
- заменить модель;
- сравнить качество.

### Сценарий B. Document Agent

- принять файлы и инструкции;
- извлечь структуру;
- использовать RAG;
- создать документ;
- проверить обязательные поля;
- запросить подтверждение;
- выгрузить DOCX/PDF.

### Сценарий C. API Automation

- получить webhook;
- классифицировать данные;
- вызвать внешний API;
- применить условие;
- вернуть structured output;
- увидеть run graph и ошибки.

### Сценарий D. Agent Improvement

- собрать неудачные запуски;
- создать candidate prompt/config;
- запустить regression suite;
- сравнить результат;
- создать новую версию;
- откатиться при ухудшении.

## 10. Критерии готовности первой версии

Первая версия считается готовой, когда:

1. Все контрольные сценарии проходят end-to-end.
2. Любой опубликованный run воспроизводимо связан с AgentSpec и версией.
3. Замена модели проверяется на совместимость.
4. Ошибки видны на уровне конкретного узла.
5. Секреты не попадают в AgentSpec, traces и клиентский код.
6. Code Node работает в изоляции.
7. RU и EN проходят UI-проверки.
8. Ключевые потоки доступны с клавиатуры.
9. Evals блокируют известные регрессии.
10. Candidate от autoresearch не может попасть в production без ручного действия.
11. Есть экспорт проекта без зависимости от базы UI.
12. Все внешние компоненты прошли лицензионный аудит.

## 11. Главные риски

### 11.1. Слишком широкий продукт

Решение: полный набор архитектурных поверхностей, но ограниченная ширина каждой категории.

### 11.2. Frankenstein из open source

Решение: собственные контракты и оболочка; внешние компоненты только за адаптерами.

### 11.3. Привязка графа к одному runtime

Решение: AgentSpec независим от framework; framework-specific функции оформляются capabilities/adapters.

### 11.4. Плохой autoresearch

Решение: immutable datasets, hidden holdout, несколько типов evals, ручное применение.

### 11.5. Плохая безопасность generated code

Решение: sandbox, egress deny by default, resource limits и explicit secrets.

### 11.6. Лицензионный долг

Решение: dependency/asset registry, provenance и запрет на импорт без проверки.

### 11.7. Перегруженный UX

Решение: progressive disclosure, semantic zoom и отдельный published interface.

## 12. Foundation decisions

- рабочее название: Universal Agent Studio;
- публичный monorepo, first-party code под Apache-2.0;
- local/self-hosted first, затем частный сервер;
- BYOK;
- single private workspace с project isolation;
- Temporal за `DurableExecutionPort`;
- React Flow как заменяемый canvas primitive без fork чужого продукта;
- канонические contracts: JSON Schema 2020-12;
- подробности и последствия: `docs/DECISIONS.md` и `docs/adr/`.
