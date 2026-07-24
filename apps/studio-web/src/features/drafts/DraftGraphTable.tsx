"use client";

import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  MousePointer2,
} from "lucide-react";
import {useTranslations} from "next-intl";

import type {DraftFlowNode} from "@/features/drafts/projection";
import type {Locale} from "@/lib/i18n/routing";

type Props = {
  locale: Locale;
  nodes: DraftFlowNode[];
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
  onMove: (nodeId: string, delta: {x: number; y: number}) => void;
};

export function DraftGraphTable({
  nodes,
  selectedNodeId,
  onSelect,
  onMove,
}: Props) {
  const t = useTranslations("draft.graph");
  return (
    <div className="draftTableWrap">
      <table aria-label={t("tableLabel")} className="draftGraphTable">
        <thead>
          <tr>
            <th scope="col">{t("node")}</th>
            <th scope="col">{t("kind")}</th>
            <th scope="col">{t("position")}</th>
            <th scope="col">{t("status")}</th>
            <th scope="col">{t("actions")}</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((node) => (
            <tr
              className={selectedNodeId === node.id ? "isSelected" : undefined}
              id={`node-${node.id}`}
              key={node.id}
            >
              <th scope="row">
                <span>{node.label}</span>
                {node.invalid ? (
                  <small className="invalidLabel">{t("invalid")}</small>
                ) : null}
              </th>
              <td>{t(`kinds.${node.kind}`)}</td>
              <td className="positionCell">
                {node.position.x}, {node.position.y}
              </td>
              <td>
                <span className={`nodeStatus nodeStatus--${node.status}`}>
                  {t(`statuses.${node.status}`)}
                </span>
              </td>
              <td>
                <div className="tableActions">
                  <ActionButton
                    label={t("select", {label: node.label})}
                    pressed={selectedNodeId === node.id}
                    onClick={() => onSelect(node.id)}
                  >
                    <MousePointer2 aria-hidden />
                  </ActionButton>
                  <ActionButton
                    label={t("moveLeft", {label: node.label})}
                    onClick={() => onMove(node.id, {x: -24, y: 0})}
                  >
                    <ArrowLeft aria-hidden />
                  </ActionButton>
                  <ActionButton
                    label={t("moveRight", {label: node.label})}
                    onClick={() => onMove(node.id, {x: 24, y: 0})}
                  >
                    <ArrowRight aria-hidden />
                  </ActionButton>
                  <ActionButton
                    label={t("moveUp", {label: node.label})}
                    onClick={() => onMove(node.id, {x: 0, y: -24})}
                  >
                    <ArrowUp aria-hidden />
                  </ActionButton>
                  <ActionButton
                    label={t("moveDown", {label: node.label})}
                    onClick={() => onMove(node.id, {x: 0, y: 24})}
                  >
                    <ArrowDown aria-hidden />
                  </ActionButton>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionButton({
  children,
  label,
  onClick,
  pressed,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={pressed}
      className="iconButton"
      title={label}
      type="button"
      onClick={onClick}
    >
      {children}
    </button>
  );
}
