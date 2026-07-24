"use client";

import {
  Background,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";

export type NodeExecutionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type FlowNodeView = {
  id: string;
  label: string;
  kind: string;
  status: NodeExecutionStatus;
};

type Props = {
  nodes: FlowNodeView[];
  edges: Edge[];
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
};

export function ReadOnlyFlow({
  nodes,
  edges,
  selectedNodeId,
  onSelect,
}: Props) {
  const flowNodes: Node[] = nodes.map((node, index) => ({
    id: node.id,
    position: {x: index * 220, y: index % 2 === 0 ? 24 : 140},
    data: {
      label: node.label,
      kind: node.kind,
      status: node.status,
    },
    className: `flowNode flowNode--${node.status}`,
    selected: selectedNodeId === node.id,
    draggable: false,
  }));

  return (
    <div className="flowCanvas" aria-hidden="true">
      <ReactFlow
        nodes={flowNodes}
        edges={edges}
        nodesDraggable={false}
        nodesConnectable={false}
        nodesFocusable={false}
        edgesFocusable={false}
        elementsSelectable
        fitView
        minZoom={0.55}
        maxZoom={1.5}
        onNodeClick={(_, node) => onSelect(node.id)}
        proOptions={{hideAttribution: true}}
      >
        <Background gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
