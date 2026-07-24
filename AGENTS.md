# Instructions for coding agents

## Mission

Build Universal Agent Studio according to the repository product, architecture, design, security, evaluation and localization documents.

## Before writing code

1. Read `README.md`, `PRODUCT.md`, `ARCHITECTURE.md`, `DESIGN.md`, `SECURITY.md`, `EVALS.md`, `LOCALIZATION.md`, `OPEN_SOURCE_POLICY.md`, `ROADMAP.md`, `docs/DECISIONS.md`, `docs/ARCHITECTURAL_INVARIANTS.md`, and `docs/CONTRACTS.md`.
2. Summarize the intended product and current task.
3. Identify contradictions, missing contracts, and risky assumptions.
4. Do not start a broad implementation until the relevant ADR and acceptance criteria exist.
5. Prefer a small complete vertical slice over disconnected scaffolding.
6. Follow the slice boundaries and exit gates in `ROADMAP.md`.
7. Treat `docs/ARCHITECTURAL_INVARIANTS.md` as mandatory constraints.

## Source of truth

- `AgentSpec` and related schemas are the source of truth for agent behavior.
- The canvas is an editor/view of the specification, not an independent data model.
- Published versions are immutable.
- Secrets must never be stored inside AgentSpec.
- External components and assets require provenance and license metadata.

## Engineering rules

- Keep the control plane modular.
- Put dangerous or long-running execution in workers.
- Use typed contracts at boundaries.
- Avoid hidden global state.
- No provider-specific logic in product-level modules.
- No framework-specific logic in AgentSpec core.
- Add an adapter rather than leaking an external library across the codebase.
- JSON Schema in `contracts/schemas` is canonical; generated language types are not hand-edited.
- Do not introduce a dependency without documenting why it is needed and how it is licensed.
- Do not fork a large external repository unless an ADR explicitly approves the maintenance cost.
- Prefer generated clients/types from shared schemas.
- Every background operation must be idempotent or explicitly document why it cannot be.

## UI rules

- No hard-coded user-visible strings.
- Support `ru-RU` and `en-US`.
- Every new interaction must define loading, empty, error, disabled and success states.
- Preserve keyboard access.
- The simple and advanced views must edit the same underlying data.
- AI-generated changes must be previewed as a diff before application.

## AI and evaluation rules

- Do not treat LLM output as trusted.
- Validate structured outputs.
- Record model, parameters, prompt version and tool calls in run provenance.
- Add regression evals for every fixed AI behavior bug.
- LLM-as-judge may not be the sole release gate.
- Autoresearch may create candidate versions but may not publish them automatically.
- Never use private production traces in platform-wide research without explicit consent.

## Security rules

- Redact secrets and sensitive data from logs.
- Credentials are references resolved server-side.
- Code nodes run in isolation with explicit limits.
- Network access is denied by default in generated-code sandboxes.
- Side-effecting tools require idempotency and, where configured, human approval.
- Treat user content, retrieved documents and traces as untrusted input.

## Testing

Each meaningful change should include the relevant subset of:

- unit tests;
- schema/contract tests;
- integration tests;
- end-to-end tests;
- visual tests;
- localization tests;
- security tests;
- AI evals.

## Completion report

At the end of a task, report:

- what changed;
- why;
- files touched;
- tests run and results;
- known limitations;
- follow-up decisions;
- any license or security concern.
