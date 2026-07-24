"use client";

import {
  Background,
  ReactFlow,
  type Edge,
  type Node,
  type Viewport,
} from "@xyflow/react";
import {useTranslations} from "next-intl";

import type {DraftFlowProjection} from "@/features/drafts/projection";

type Props = {
  projection: DraftFlowProjection;
  viewport: Viewport;
  selectedNodeId: string | null;
  onMove: (nodeId: string, position: {x: number; y: number}) => void;
  onViewport: (viewport: Viewport) => void;
  onSelect: (nodeId: string) => void;
};

export function DraftCanvas({
  projection,
  viewport,
  selectedNodeId,
  onMove,
  onViewport,
  onSelect,
}: Props) {
  const t = useTranslations("draft.graph");
  const nodes: Node[] = projection.nodes.map((node) => ({
    id: node.id,
    position: node.position,
    data: {
      label: (
        <span className="draftNodeContent">
          <small>{t(`kinds.${node.kind}`)}</small>
          <strong>{node.label}</strong>
          <span>{t(`statuses.${node.status}`)}</span>
        </span>
      ),
    },
    className: [
      "draftFlowNode",
      `draftFlowNode--${node.status}`,
      node.invalid ? "draftFlowNode--invalid" : "",
    ]
      .filter(Boolean)
      .join(" "),
    selected: selectedNodeId === node.id,
  }));
  const edges: Edge[] = projection.edges.map((edge) => ({
    ...edge,
    type: "smoothstep",
  }));

  return (
    <div className="draftCanvas" aria-hidden="true">
      <ReactFlow
        edges={edges}
        edgesFocusable={false}
        elementsSelectable
        defaultViewport={viewport}
        maxZoom={1.6}
        minZoom={0.4}
        nodes={nodes}
        nodesConnectable={false}
        onNodeClick={(_, node) => onSelect(node.id)}
        onNodeDragStop={(_, node) => onMove(node.id, node.position)}
        onMoveEnd={(_, nextViewport) => onViewport(nextViewport)}
        proOptions={{hideAttribution: true}}
      >
        <Background gap={20} size={1} />
      </ReactFlow>
    </div>
  );
}
