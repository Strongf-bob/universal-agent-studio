import type {AgentDraft, AgentSpec} from "@universal-agent-studio/contracts";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";

export function editorDraftFixture(): AgentDraft {
  const agentSpec = JSON.parse(
    readFileSync(
      resolve(
        process.cwd(),
        "../../contracts/examples/v0.1.0/valid/agent.calculator.ru-en.json",
      ),
      "utf8",
    ),
  ) as AgentSpec;
  return {
    schema_version: "0.1.0",
    draft_id: "calculator-agent-draft",
    agent_id: agentSpec.agent_id,
    revision: 1,
    base_version_id: "calculator-agent-v1",
    digest: "a".repeat(64),
    agent_spec: agentSpec,
    layout: {
      nodes: agentSpec.nodes.map((node, index) => ({
        node_id: node.id,
        x: index * 240,
        y: index % 2 === 0 ? 40 : 160,
      })),
      viewport: {x: 0, y: 0, zoom: 1},
    },
    updated_at: "2026-07-24T20:00:00Z",
  };
}

export function savedDraft(
  draft: AgentDraft,
  agentSpec = draft.agent_spec,
): AgentDraft {
  return {
    ...draft,
    revision: draft.revision + 1,
    digest: "b".repeat(64),
    agent_spec: agentSpec,
    updated_at: "2026-07-24T20:01:00Z",
  };
}
