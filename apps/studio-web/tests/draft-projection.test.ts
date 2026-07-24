import {existsSync, readFileSync} from "node:fs";
import {resolve} from "node:path";

import type {
  AgentDraft,
  RunEvent,
} from "@universal-agent-studio/contracts";
import {expect, test} from "vitest";

import {
  projectDraftToFlow,
  runStatusByNode,
} from "@/features/drafts/projection";

function draftFixture(): AgentDraft {
  return JSON.parse(
    readFileSync(
      resolve(
        process.cwd(),
        "../../contracts/examples/v0.1.0/valid/agent.draft.calculator.json",
      ),
      "utf8",
    ),
  ) as AgentDraft;
}

function event(
  type: RunEvent["type"],
  sequence: number,
  nodeId?: string,
): RunEvent {
  return {
    schema_version: "0.1.0",
    event_id: `11111111-1111-4111-8111-11111111111${sequence}`,
    run_id: "22222222-2222-4222-8222-222222222222",
    sequence,
    type,
    occurred_at: "2026-07-24T19:00:00Z",
    correlation_id: "33333333-3333-4333-8333-333333333333",
    causation_id: "44444444-4444-4444-8444-444444444444",
    redaction_policy_id: "default-redaction",
    payload: {},
    ...(nodeId ? {node_id: nodeId} : {}),
  };
}

test("product-owned draft projection module exists", () => {
  expect(
    existsSync(
      resolve(
        process.cwd(),
        "src/features/drafts/projection.ts",
      ),
    ),
  ).toBe(true);
});

test("projects localized AgentSpec and layout without React Flow types", () => {
  const draft = draftFixture();

  const projected = projectDraftToFlow(
    draft.agent_spec,
    draft.layout,
    "en-US",
  );

  expect(projected.nodes).toEqual([
    {
      id: "source-node",
      label: "Input",
      description: "Graph entry point.",
      kind: "input",
      position: {x: 0, y: 80},
      status: "pending",
      invalid: false,
    },
  ]);
  expect(projected.edges).toEqual([]);
  expect(
    readFileSync(
      resolve(
        process.cwd(),
        "src/features/drafts/projection.ts",
      ),
      "utf8",
    ),
  ).not.toContain("@xyflow/react");
});

test("maps persisted run events to textual node states", () => {
  const draft = draftFixture();

  const running = runStatusByNode(draft.agent_spec, [
    event("node.started", 1, "source-node"),
  ]);
  const completed = runStatusByNode(draft.agent_spec, [
    event("node.started", 1, "source-node"),
    event("node.completed", 2, "source-node"),
  ]);

  expect(running.get("source-node")).toBe("running");
  expect(completed.get("source-node")).toBe("completed");
});

test("marks validation issues on their projected node", () => {
  const draft = draftFixture();

  const projected = projectDraftToFlow(
    draft.agent_spec,
    draft.layout,
    "ru-RU",
    [
      {
        code: "schema_validation_failed",
        json_pointer: "/nodes/0/config",
        node_id: "source-node",
        message_key: "validation.schema.type",
      },
    ],
  );

  expect(projected.nodes[0]?.invalid).toBe(true);
  expect(projected.nodes[0]?.label).toBe("Вход");
});
