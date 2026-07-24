import type {
  AgentSpec,
  Layout,
  RunEvent,
} from "@universal-agent-studio/contracts";

import type {
  DraftRunStatus,
  DraftValidationIssue,
} from "@/features/drafts/types";

export type DraftFlowNode = {
  id: string;
  label: string;
  description: string;
  kind: string;
  position: {x: number; y: number};
  status: DraftRunStatus;
  invalid: boolean;
};

export type DraftFlowEdge = {
  id: string;
  source: string;
  target: string;
};

export type DraftFlowProjection = {
  nodes: DraftFlowNode[];
  edges: DraftFlowEdge[];
};

export function runStatusByNode(
  agentSpec: AgentSpec,
  events: RunEvent[],
): Map<string, DraftRunStatus> {
  const statuses = new Map<string, DraftRunStatus>(
    agentSpec.nodes.map((node) => [node.id, "pending" as const]),
  );
  for (const event of [...events].sort(
    (left, right) => left.sequence - right.sequence,
  )) {
    if (event.node_id) {
      if (event.type === "node.started") {
        statuses.set(event.node_id, "running");
      } else if (event.type === "node.completed") {
        statuses.set(event.node_id, "completed");
      } else if (event.type === "node.failed") {
        statuses.set(event.node_id, "failed");
      }
    }
    if (event.type === "run.cancelled") {
      for (const [nodeId, status] of statuses) {
        if (status === "running") {
          statuses.set(nodeId, "cancelled");
        }
      }
    } else if (event.type === "run.failed") {
      for (const [nodeId, status] of statuses) {
        if (status === "running") {
          statuses.set(nodeId, "failed");
        }
      }
    }
  }
  return statuses;
}

export function projectDraftToFlow(
  agentSpec: AgentSpec,
  layout: Layout,
  locale: "ru-RU" | "en-US",
  issues: DraftValidationIssue[] = [],
  events: RunEvent[] = [],
): DraftFlowProjection {
  const positions = new Map(
    layout.nodes.map((position) => [
      position.node_id,
      {x: position.x, y: position.y},
    ]),
  );
  const invalidNodes = new Set(
    issues.flatMap((issue) =>
      issue.node_id === null ? [] : [issue.node_id],
    ),
  );
  const statuses = runStatusByNode(agentSpec, events);
  return {
    nodes: agentSpec.nodes.map((node, index) => ({
      id: node.id,
      label:
        node.localized_metadata.name[locale] ??
        node.localized_metadata.name["en-US"],
      description:
        node.localized_metadata.description[locale] ??
        node.localized_metadata.description["en-US"],
      kind: node.kind,
      position: positions.get(node.id) ?? {
        x: index * 260,
        y: index % 2 === 0 ? 80 : 200,
      },
      status: statuses.get(node.id) ?? "pending",
      invalid: invalidNodes.has(node.id),
    })),
    edges: agentSpec.edges.map((edge) => ({
      id: edge.id,
      source: edge.source.node_id,
      target: edge.target.node_id,
    })),
  };
}
