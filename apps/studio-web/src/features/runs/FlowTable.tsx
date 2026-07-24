"use client";

import {useTranslations} from "next-intl";

import type {FlowNodeView} from "@/features/runs/ReadOnlyFlow";

type Props = {
  nodes: FlowNodeView[];
  selectedNodeId: string | null;
  onSelect: (nodeId: string) => void;
};

export function FlowTable({nodes, selectedNodeId, onSelect}: Props) {
  const t = useTranslations("run.flow");

  return (
    <div className="flowTableWrap">
      <table className="flowTable" aria-label={t("tableLabel")}>
        <thead>
          <tr>
            <th scope="col">{t("node")}</th>
            <th scope="col">{t("kind")}</th>
            <th scope="col">{t("status")}</th>
            <th scope="col">
              <span className="visuallyHidden">{t("actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((node) => (
            <tr key={node.id}>
              <th scope="row">{node.label}</th>
              <td>{t(`kinds.${node.kind}`)}</td>
              <td>
                <span className={`nodeStatus nodeStatus--${node.status}`}>
                  {t(`statuses.${node.status}`)}
                </span>
              </td>
              <td>
                <button
                  className="buttonText"
                  type="button"
                  aria-label={t("inspect", {label: node.label})}
                  aria-pressed={selectedNodeId === node.id}
                  onClick={() => onSelect(node.id)}
                >
                  {t("details")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
