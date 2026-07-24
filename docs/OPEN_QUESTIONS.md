# Open questions

Решённые вопросы переносятся в `DECISIONS.md` и ADR. Этот файл содержит только решения, которые действительно остаются открытыми.

## Blocking Slice 1

На уровне продукта блокеров нет. До реализации должны быть утверждены:

1. точный минимальный AgentSpec schema;
2. RunEvent delivery and resume semantics;
3. canonical hashing and signing envelope;
4. acceptance examples Slice 1.

## Blocking later slices

### Slice 4

1. Какие два native provider adapter входят в Private Alpha помимо OpenAI-compatible?
2. Какой secret store используется на частном сервере?

### Slice 5

1. Какой vector index выбран после benchmark на RU/EN корпусе?
2. Какие file formats входят в первый production-quality ingestion pipeline?

### Slice 6

1. Какая Linux sandbox technology проходит feasibility/security spike?
2. Какие действия требуют mandatory approval независимо от настройки агента?

### Slice 8

1. Какая модель используется AI Builder и Researcher по умолчанию?
2. Какие поля входят в первую autoresearch mutation allowlist?
3. Как строится первый hidden holdout и кто имеет к нему доступ?
4. Как измеряется и контролируется evaluator bias?

## Non-blocking strategic questions

1. Сохранится ли название Universal Agent Studio перед публичным продуктовым запуском?
2. Когда появится managed cloud и hybrid billing?
3. Какая модель multi-user collaboration и RBAC нужна после Private Alpha?
