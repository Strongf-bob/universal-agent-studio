# Foundation decisions

Дата фиксации: 2026-07-24.

Эти решения действуют для Foundation и меняются только через ADR.

| Область | Решение |
|---|---|
| Название | Universal Agent Studio |
| Репозиторий | Публичный monorepo |
| Лицензия first-party кода | Apache-2.0; перед коммерческой дистрибуцией требуется legal review |
| Первый deployment | Local/self-hosted, затем тот же build на частном сервере |
| Tenancy | Private single workspace; project boundary сохраняется в модели данных |
| Model billing | BYOK |
| Product surfaces | Web Studio, Published Web App и public API |
| Backend | Python + FastAPI |
| Frontend | TypeScript + React/Next.js |
| Persistence | PostgreSQL; S3-compatible storage добавляется в первом slice, где нужны artifacts |
| Contracts | JSON Schema 2020-12 — canonical source; Python и TypeScript types генерируются |
| Durable execution | Temporal за собственным `DurableExecutionPort` |
| Canvas | React Flow как заменяемый rendering/interaction primitive |
| Runtime | Собственный interpreter AgentSpec; framework integrations только через adapters |
| Versions | Published versions immutable и content-addressed |
| Capability packs | Versioned references; раскрытие — view; изменение internals создаёт fork |
| Autoresearch | Candidate-only, mutation allowlist, fixed budget, human promotion |
| Locales | `ru-RU` и `en-US` с первого пользовательского slice |
| Telegram | Channel adapter после Private Alpha, не обязательный первый контур |

## Consequences

- Local setup тяжелее простого in-process prototype, потому что включает PostgreSQL и Temporal.
- Детерминированные fake adapters обязательны: CI не зависит от внешних LLM и secrets.
- Provider-specific параметры допускаются только в namespaced extensions.
- Public Studio и Published App имеют разные security boundaries.
- Ни canvas library, ни durable engine не входят в AgentSpec vocabulary.
