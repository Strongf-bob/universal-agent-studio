# Design and UX specification

## 1. Цель

Интерфейс должен одинаково хорошо поддерживать:

- пользователя, который хочет просто описать задачу и нажать «Создать»;
- builder-а, который хочет редактировать граф;
- разработчика, который хочет видеть prompts, JSON, code и traces.

Основной принцип: **информация не скрывается навсегда, но и не показывается раньше, чем она нужна.**

## 2. Информационная архитектура

### Глобальная навигация

- Workspace;
- Agents;
- Create;
- Blueprints;
- Integrations;
- Models;
- Assets;
- Runs;
- Research Lab;
- Settings.

### Внутри агента

- Overview;
- Build;
- Test;
- Interface;
- Knowledge;
- Models;
- Publish;
- Runs;
- Evals;
- Improvements;
- Versions.

В простом режиме часть вкладок скрывается в разделе «Advanced», но остаётся доступной.

## 3. Canvas

Базовая компоновка:

```text
┌─────────────────┬───────────────────────────┬─────────────────┐
│ Node Library    │ Canvas                    │ Inspector       │
│ Search          │                           │ Basic           │
│ Recommended     │ Trigger → Agent → Output  │ Model           │
│ AI              │             ↓             │ Prompt          │
│ Logic           │           Tool            │ Input/Output    │
│ Data            │                           │ Advanced        │
└─────────────────┴───────────────────────────┴─────────────────┘
│ Test Console / Run Trace                                      │
└───────────────────────────────────────────────────────────────┘
```

## 4. Progressive disclosure

### Уровень 0 — Published App

Только пользовательская задача и результат.

### Уровень 1 — Intent

Назначение агента, knowledge, tools, model profiles и publication.

### Уровень 2 — Flow

Основные блоки workflow.

### Уровень 3 — Pack Internals

Внутренние шаги RAG, documents, validation и automation.

### Уровень 4 — Implementation

Prompt, model parameters, schema, code и trace.

Переход между уровнями не должен создавать копии. Это разные представления одного AgentSpec.

## 5. Semantic zoom

При уменьшении масштаба узел показывает:

- иконку;
- название;
- статус.

При нормальном масштабе:

- model profile;
- inputs/outputs;
- краткое описание.

При раскрытии:

- prompt preview;
- configuration;
- recent result;
- cost/latency;
- error details.

Capability pack на верхнем уровне выглядит как один блок и раскрывается в отдельный подграф.

## 6. AI Builder

AI Builder доступен:

- при создании;
- как боковая панель;
- через command palette;
- из контекста выбранного узла.

AI всегда показывает plan/diff до применения:

```text
Добавить:
+ RAG Pack
+ Knowledge Base
+ Citation Validator

Изменить:
~ Model profile: Fast → Smart

Требуется:
! Подключить embedding provider
```

## 7. Визуальный язык

- нейтральный современный интерфейс;
- высокая плотность только там, где это оправдано;
- цвет не является единственным индикатором состояния;
- узлы имеют единый каркас и category accents;
- ошибки показываются локально на узле;
- движение данных во время test run может быть анимировано, но анимацию можно отключить;
- светлая и тёмная темы;
- дизайн-токены вместо hard-coded values.

## 8. Design system

До масштабной реализации canvas необходимо определить:

- color tokens;
- typography;
- spacing;
- radius;
- shadows;
- focus rings;
- icons;
- elevation;
- state colors;
- graph category colors;
- motion durations;
- breakpoints;
- locale-safe sizing.

Нельзя копировать чужой интерфейс пиксель в пиксель. Допустимо переиспользовать permissive компоненты после аудита и построить собственную дизайн-систему.

## 9. Accessibility

Минимальные требования:

- keyboard navigation;
- видимый focus;
- screen-reader labels;
- контраст;
- reduced motion;
- альтернативное табличное представление graph;
- доступные form controls;
- ошибки с текстовым объяснением.

## 10. L10n

- никакого текста внутри component source без translation key;
- поддержка длинных строк;
- отдельное форматирование дат/валют/чисел;
- pluralization;
- RU и EN visual regression tests;
- не использовать ширину строки как неизменяемое предположение.

## 11. Основные экраны первой версии

1. Workspace.
2. Create with AI.
3. Visual Canvas.
4. Model Hub.
5. Integration Hub.
6. Asset Library.
7. Published Web App.
8. Runs / Trace.
9. Candidate Comparison.
10. Versions / Rollback.
