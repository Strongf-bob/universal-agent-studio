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

## 12. Design direction

Studio выглядит как спокойный технический workbench, а не как развлекательный AI-лендинг:

- высокая информационная плотность появляется только в canvas, traces и evals;
- рабочие поверхности нейтральные, category accents помогают читать graph;
- light и dark themes проектируются вместе, ни одна не является инверсией другой;
- декоративное свечение, glassmorphism и gradients не конкурируют с данными;
- один основной action на экран, опасные действия визуально и пространственно отделены;
- иконки берутся из одного проверенного SVG-набора, emoji не используются как UI icons;
- typography оптимизирована под кириллицу, код, табличные числа и длинные технические labels.

Начальные design tokens описываются до компонентов:

```text
spacing: 4, 8, 12, 16, 24, 32, 48
radius: 6, 10, 14
motion: 120ms, 180ms, 240ms
breakpoints: 375, 768, 1024, 1440
body text: >= 16px on narrow screens
touch target: >= 44x44 CSS px
focus ring: 2px visible outline + offset
```

Raw colors, spacing и z-index нельзя добавлять непосредственно в components. Semantic tokens должны описывать `surface`, `surface-raised`, `text`, `text-muted`, `border`, `focus`, `danger`, `warning`, `success` и graph categories.

## 13. Responsive application shells

### Studio

Studio desktop-first, потому что редактирование graph требует пространства, но основные операции остаются доступными от `320px`.

- `>= 1024px`: navigation + node library + canvas + inspector;
- `768–1023px`: canvas и один переключаемый side panel;
- `< 768px`: Library / Flow / Inspector становятся отдельными tabs;
- drag-and-drop всегда имеет keyboard и command-palette alternative;
- fixed panels не создают вложенные scroll regions без необходимости.

### Published App

Published App mobile-first:

- form, chat, files, progress, result и approval работают от `320px`;
- основные touch targets не меньше `44x44px`;
- virtual keyboard не перекрывает submit/approval actions;
- system zoom и text scaling не отключаются.

### Runs and Trace

Trace доступен как timeline, table и read-only graph. На узких экранах table/timeline являются основными, а graph — дополнительным представлением.

## 14. Required interaction states

Каждое асинхронное действие определяет:

- initial;
- loading;
- empty;
- disabled с объяснением причины;
- success;
- validation error;
- recoverable runtime error;
- terminal runtime error;
- reconnecting;
- cancelled.

Loading дольше `300ms` показывает progress/skeleton без layout shift. Error располагается рядом с причиной, содержит путь восстановления и стабильный support code, но не credentials, raw provider payload или внутренний stack trace. Toast не является единственным местом для критической ошибки.

## 15. View-model boundary

React Flow nodes и edges — ephemeral view models, полученные из AgentSpec.

В Studio layout metadata, но не в runtime semantics, хранятся:

- coordinates;
- viewport;
- selection;
- collapsed groups;
- panel sizes;
- presentation-only edge routing.

Изменение simple settings или canvas отправляет typed command к одному draft. UI не сохраняет параллельный graph document. Ошибка contract validation указывает одновременно JSON path, поле inspector и node.

## 16. Slice 1 screens

Slice 1 включает только реальный сквозной UX:

1. **Local Owner Setup** — создание первого owner без внешнего auth provider.
2. **Agent Runner** — локализованный typed input и запуск golden agent.
3. **Run Progress** — stream state, reconnect и cancel.
4. **Structured Result** — schema-driven output без debug data.
5. **Read-only Flow** — graph projection той же AgentVersion.
6. **Node Trace Inspector** — status, duration, redacted input/output и provenance.

Editable canvas, AI Builder, RAG и code editor не имитируются заглушками в Slice 1.

## 17. Accessibility acceptance

- все ключевые actions доступны с клавиатуры;
- focus order соответствует визуальному порядку;
- route change переводит focus в `main`;
- icon-only actions имеют accessible names;
- error summary ссылается на конкретные поля;
- status и graph category не кодируются только цветом;
- animations отключаются через `prefers-reduced-motion`;
- normal text проходит WCAG AA `4.5:1`, UI boundaries и large text — минимум `3:1`;
- interactive graph имеет эквивалентный list/table editor;
- RU/EN проверяются при `200%` browser zoom и длинных translations.

## 18. Frontend provenance

Источники, лицензии, допустимые границы и запрещённое копирование перечислены в [`docs/FRONTEND_SOURCES.md`](docs/FRONTEND_SOURCES.md). Ни один candidate не считается установленным или одобренным только потому, что упомянут в design document.
