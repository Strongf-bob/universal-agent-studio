"use client";

import type {NodeExecution} from "@universal-agent-studio/contracts";
import {Braces, Clock3} from "lucide-react";
import {useTranslations} from "next-intl";

import type {FlowNodeView} from "@/features/runs/ReadOnlyFlow";

type Props = {
  node: FlowNodeView | null;
  execution: NodeExecution | null;
};

function TraceValues({
  values,
}: {
  values: Record<string, unknown>;
}) {
  return (
    <dl className="traceValues">
      {Object.entries(values).map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>
            {typeof value === "string" || typeof value === "number"
              ? String(value)
              : JSON.stringify(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function NodeTraceInspector({node, execution}: Props) {
  const t = useTranslations("run.inspector");
  if (!node) {
    return (
      <aside className="traceInspector traceInspector--empty">
        <p>{t("selectNode")}</p>
      </aside>
    );
  }

  return (
    <aside className="traceInspector" aria-labelledby="trace-node-title">
      <header className="traceInspectorHeader">
        <span className="traceIcon">
          <Braces aria-hidden />
        </span>
        <div>
          <p className="metaLabel">{t("eyebrow")}</p>
          <h3 id="trace-node-title">{node.label}</h3>
        </div>
      </header>
      <div className="traceMeta">
        <span className={`nodeStatus nodeStatus--${node.status}`}>
          {t(`statuses.${node.status}`)}
        </span>
        {execution ? (
          <span>
            <Clock3 aria-hidden />
            {t("duration", {duration: execution.duration_ms})}
          </span>
        ) : null}
      </div>
      {execution ? (
        <>
          <section>
            <h4>{t("input")}</h4>
            <TraceValues values={execution.input} />
          </section>
          <section>
            <h4>{t("output")}</h4>
            <TraceValues values={execution.output} />
          </section>
          <p className="redactionNote">{t("redactionNote")}</p>
        </>
      ) : (
        <p className="emptyState">{t("notExecuted")}</p>
      )}
    </aside>
  );
}
