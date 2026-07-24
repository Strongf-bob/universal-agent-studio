import type {
  AgentSpec,
  RunEvent,
  RunTrace,
} from "@universal-agent-studio/contracts";
import {NextIntlClientProvider} from "next-intl";
import type {ReactNode} from "react";

import enMessages from "@/messages/en-US.json";
import ruMessages from "@/messages/ru-RU.json";

export const runId = "22222222-2222-4222-8222-222222222222";

export function event(
  sequence: number,
  type: RunEvent["type"],
  nodeId?: string,
): RunEvent {
  return {
    schema_version: "0.1.0",
    event_id: `00000000-0000-4000-8000-${String(sequence).padStart(12, "0")}`,
    run_id: runId,
    sequence,
    type,
    occurred_at: `2026-07-24T12:00:00.${String(sequence).padStart(3, "0")}Z`,
    correlation_id: "11111111-1111-4111-8111-111111111111",
    causation_id:
      sequence === 1
        ? "11111111-1111-4111-8111-111111111111"
        : `00000000-0000-4000-8000-${String(sequence - 1).padStart(12, "0")}`,
    node_id: nodeId,
    redaction_policy_id: "default-redaction",
    payload: {},
  };
}

export const agentSpec = {
  schema_version: "0.1.0",
  agent_id: "calculator-agent",
  localized_metadata: {
    name: {"ru-RU": "Агент-калькулятор", "en-US": "Calculator agent"},
    description: {"ru-RU": "Описание", "en-US": "Description"},
  },
  nodes: [
    {
      id: "user-input",
      kind: "input",
      localized_metadata: {
        name: {"ru-RU": "Запрос", "en-US": "Request"},
      },
    },
    {
      id: "calculator-tool",
      kind: "tool",
      localized_metadata: {
        name: {"ru-RU": "Калькулятор", "en-US": "Calculator"},
      },
    },
  ],
  edges: [
    {
      id: "input-to-calculator",
      source: {node_id: "user-input", port_id: "request"},
      target: {node_id: "calculator-tool", port_id: "operation"},
    },
  ],
} as unknown as AgentSpec;

export const completedTrace = {
  schema_version: "0.1.0",
  run_id: runId,
  request_id: "11111111-1111-4111-8111-111111111111",
  agent_version_id: "calculator-agent-v1",
  agent_version_digest: "a".repeat(64),
  status: "completed",
  started_at: "2026-07-24T12:00:00.000Z",
  completed_at: "2026-07-24T12:00:00.280Z",
  input: {question: "What is 19 × 23?"},
  output: {value: 437},
  events: [
    event(1, "run.started"),
    event(2, "node.started", "calculator-tool"),
    event(3, "node.completed", "calculator-tool"),
    event(4, "run.completed"),
  ],
  node_executions: [
    {
      node_id: "calculator-tool",
      attempt: 1,
      status: "completed",
      started_at: "2026-07-24T12:00:00.100Z",
      completed_at: "2026-07-24T12:00:00.200Z",
      duration_ms: 100,
      input: {credential: "[REDACTED]", left: 19, right: 23},
      output: {value: 437},
    },
  ],
  provenance: {
    model_resolutions: [],
    tool_resolutions: [
      {
        tool_id: "builtin.calculator",
        version: "1.0.0",
        digest: "b".repeat(64),
      },
    ],
    redaction_policy_id: "default-redaction",
  },
  metrics: {
    duration_ms: 280,
    input_tokens: 8,
    output_tokens: 12,
    tool_calls: 1,
    cost: {amount: 0, currency: "USD"},
  },
} as RunTrace;

export function WithMessages({
  children,
  locale = "en-US",
}: {
  children: ReactNode;
  locale?: "ru-RU" | "en-US";
}) {
  return (
    <NextIntlClientProvider
      locale={locale}
      messages={locale === "ru-RU" ? ruMessages : enMessages}
    >
      {children}
    </NextIntlClientProvider>
  );
}
