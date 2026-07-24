"use client";

import type {
  NodeExecution,
  RunTrace,
} from "@universal-agent-studio/contracts";
import {Braces, Clock3} from "lucide-react";
import {useTranslations} from "next-intl";

import type {FlowNodeView} from "@/features/runs/ReadOnlyFlow";

type Props = {
  node: FlowNodeView | null;
  execution: NodeExecution | null;
  provenance: RunTrace["provenance"];
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

export function NodeTraceInspector({node, execution, provenance}: Props) {
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
            <h4>{t("execution")}</h4>
            <TraceValues
              values={{
                attempt: execution.attempt,
                started_at: execution.started_at,
                completed_at: execution.completed_at,
              }}
            />
          </section>
          <section>
            <h4>{t("input")}</h4>
            <TraceValues values={execution.input} />
          </section>
          <section>
            <h4>{t("output")}</h4>
            <TraceValues values={execution.output} />
          </section>
          <section>
            <h4>{t("provenance")}</h4>
            <TraceValues
              values={{
                redaction_policy_id: provenance.redaction_policy_id,
                resolutions:
                  node.kind === "model"
                    ? provenance.model_resolutions
                    : node.kind === "tool"
                      ? provenance.tool_resolutions
                      : [],
              }}
            />
          </section>
          <p className="redactionNote">{t("redactionNote")}</p>
        </>
      ) : (
        <p className="emptyState">{t("notExecuted")}</p>
      )}
    </aside>
  );
}
