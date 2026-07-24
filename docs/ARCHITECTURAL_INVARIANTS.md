# Architectural invariants

Эти правила важнее удобства конкретного framework или UI library.

## Canonical state

1. `AgentSpec` — единственный источник истины поведения агента.
2. Simple settings, canvas, JSON и AI Builder являются projections/commands над одним draft.
3. Canvas coordinates и collapsed state не влияют на runtime semantics.
4. Published version immutable и идентифицируется canonical content digest.
5. Run всегда привязан к published version или immutable draft snapshot.

## Runtime boundaries

6. Control plane не исполняет пользовательский code и long-running workflows.
7. Runtime принимает validated contracts и не импортирует frontend types.
8. Model, tool, storage, durable execution и sandbox доступны ядру через ports.
9. External framework objects не пересекают product-level boundaries.
10. Повторная доставка command/event не создаёт повторный side effect.

## Security

11. Secret values не входят в AgentSpec, event, trace, diff или browser bundle.
12. Любой внешний content и model output считаются untrusted.
13. Permissions проверяются policy layer, а не prompt.
14. Side-effecting tools имеют classification, scopes и idempotency policy.
15. Code execution не имеет network access по умолчанию.
16. Research worker не получает production write credentials.

## Provenance and quality

17. Run provenance фиксирует version digest, resolved model, parameters, prompt/assets, tool versions и redaction policy.
18. LLM non-determinism не маскируется обещанием byte-identical replay.
19. LLM-as-judge не является единственным release gate.
20. Исправление AI behavior bug добавляет regression case.
21. Asset без provenance/license не получает first-party Verified или Recommended status.

## Product surfaces

22. Web и API используют один runtime contract.
23. Published App не получает Studio/debug permissions.
24. Любое AI-generated изменение сначала представляется как validated diff.
25. Каждый пользовательский slice поддерживает RU/EN, keyboard flow и loading/empty/error/success states.
