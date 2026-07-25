import type {PublicAgentView, PublicRunView} from "@universal-agent-studio/contracts";

export const calculatorAgent: PublicAgentView = {
  schema_version: "0.1.0",
  agent_id: "calculator-agent",
  agent_version_id: "calculator-agent-v1",
  agent_version_digest: "a".repeat(64),
  localized_metadata: {
    name: {
      "ru-RU": "Агент-калькулятор",
      "en-US": "Calculator agent",
    },
    description: {
      "ru-RU": "Считает безопасно.",
      "en-US": "Calculates safely.",
    },
  },
  interface: {
    mode: "form",
    locales: ["ru-RU", "en-US"],
    default_locale: "ru-RU",
    input_fields: [
      {
        id: "expression",
        label: {"ru-RU": "Выражение", "en-US": "Expression"},
        required: true,
        schema: {type: "string", minLength: 1},
      },
      {
        id: "precision",
        label: {"ru-RU": "Точность", "en-US": "Precision"},
        required: false,
        schema: {type: "integer", minimum: 0, maximum: 8},
      },
      {
        id: "format",
        label: {"ru-RU": "Формат", "en-US": "Format"},
        required: false,
        schema: {type: "string", enum: ["decimal", "scientific"]},
      },
      {
        id: "explain",
        label: {"ru-RU": "Показать объяснение", "en-US": "Show explanation"},
        required: false,
        schema: {type: "boolean"},
      },
    ],
    result_schema: {
      type: "object",
      properties: {value: {type: "number"}},
    },
  },
};

export function publicRun(
  status: PublicRunView["status"],
  overrides: Partial<PublicRunView> = {},
): PublicRunView {
  const runId = "11111111-1111-4111-8111-111111111111";
  return {
    schema_version: "0.1.0",
    run_id: runId,
    agent_id: calculatorAgent.agent_id,
    agent_version_id: calculatorAgent.agent_version_id,
    agent_version_digest: calculatorAgent.agent_version_digest,
    status,
    locale: "en-US",
    output: status === "completed" ? {value: 437} : null,
    error_code: status === "failed" ? "invocation_unavailable" : null,
    status_url: `/public/v1/agents/calculator-agent/runs/${runId}`,
    events_url: `/public/v1/agents/calculator-agent/runs/${runId}/events`,
    run_capability: `uascap_${"A".repeat(48)}`,
    ...overrides,
  };
}
