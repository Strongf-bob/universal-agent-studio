"use client";

import type {
  AgentSpec,
  RunEvent,
  RunTrace,
} from "@universal-agent-studio/contracts";
import type {Edge} from "@xyflow/react";
import {useMemo, useState} from "react";

import {FlowTable} from "@/features/runs/FlowTable";
import {NodeTraceInspector} from "@/features/runs/NodeTraceInspector";
import {
  type FlowNodeView,
  type NodeExecutionStatus,
  ReadOnlyFlow,
} from "@/features/runs/ReadOnlyFlow";
import type {Locale} from "@/lib/i18n/routing";

type Props = {
  agentSpec: AgentSpec;
  events: RunEvent[];
  locale: Locale;
  trace: RunTrace;
};

function statusForNode(
  nodeId: string,
  events: RunEvent[],
  trace: RunTrace,
): NodeExecutionStatus {
  const execution = trace.node_executions.find(
    (item) => item.node_id === nodeId,
  );
  if (execution) {
    return execution.status;
  }
  const nodeEvents = events.filter((item) => item.node_id === nodeId);
  if (nodeEvents.some((item) => item.type === "node.failed")) {
    return "failed";
  }
  if (
    nodeEvents.some((item) =>
      ["node.completed", "model.completed", "tool.completed"].includes(
        item.type,
      ),
    )
  ) {
    return "completed";
  }
  if (nodeEvents.length > 0) {
    return "running";
  }
  return trace.status === "cancelled" ? "cancelled" : "pending";
}

export function buildFlowProjection(
  agentSpec: AgentSpec,
  events: RunEvent[],
  trace: RunTrace,
  locale: Locale,
): {nodes: FlowNodeView[]; edges: Edge[]} {
  return {
    nodes: agentSpec.nodes.map((node) => ({
      id: node.id,
      label: node.localized_metadata.name[locale],
      kind: node.kind,
      status: statusForNode(node.id, events, trace),
    })),
    edges: agentSpec.edges.map((edge) => ({
      id: edge.id,
      source: edge.source.node_id,
      target: edge.target.node_id,
      animated: false,
    })),
  };
}

export function RunTraceExplorer({
  agentSpec,
  events,
  locale,
  trace,
}: Props) {
  const projection = useMemo(
    () => buildFlowProjection(agentSpec, events, trace, locale),
    [agentSpec, events, locale, trace],
  );
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(
    projection.nodes[0]?.id ?? null,
  );
  const selectedNode =
    projection.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const execution =
    trace.node_executions.find(
      (item) => item.node_id === selectedNodeId,
    ) ?? null;

  return (
    <section className="traceExplorer">
      <div className="flowViews">
        <ReadOnlyFlow
          nodes={projection.nodes}
          edges={projection.edges}
          selectedNodeId={selectedNodeId}
          onSelect={setSelectedNodeId}
        />
        <FlowTable
          nodes={projection.nodes}
          selectedNodeId={selectedNodeId}
          onSelect={setSelectedNodeId}
        />
      </div>
      <NodeTraceInspector
        node={selectedNode}
        execution={execution}
        provenance={trace.provenance}
      />
    </section>
  );
}
