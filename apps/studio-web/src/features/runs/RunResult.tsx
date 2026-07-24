"use client";

import type {RunTrace} from "@universal-agent-studio/contracts";
import {CircleCheck, CircleX, OctagonX} from "lucide-react";
import {useTranslations} from "next-intl";

type Props = {
  trace: RunTrace | null;
  loading: boolean;
  error: boolean;
};

export function RunResult({trace, loading, error}: Props) {
  const t = useTranslations("run.result");
  if (loading) {
    return (
      <section className="resultCard" aria-busy="true">
        <p>{t("loading")}</p>
      </section>
    );
  }
  if (error) {
    return (
      <section className="resultCard resultCard--error" role="alert">
        <OctagonX aria-hidden />
        <p>{t("unavailable")}</p>
      </section>
    );
  }
  if (!trace) {
    return (
      <section className="resultCard resultCard--pending">
        <p>{t("pending")}</p>
      </section>
    );
  }

  const StatusIcon =
    trace.status === "completed" ? CircleCheck : CircleX;
  return (
    <section
      className={`resultCard resultCard--${trace.status}`}
      aria-labelledby="result-title"
    >
      <header>
        <StatusIcon aria-hidden />
        <div>
          <p className="metaLabel">{t("eyebrow")}</p>
          <h2 id="result-title">{t(`statuses.${trace.status}`)}</h2>
        </div>
      </header>
      <div className="resultValue">
        <span>{t("output")}</span>
        <code>{JSON.stringify(trace.output)}</code>
      </div>
      <dl className="resultMetrics">
        <div>
          <dt>{t("duration")}</dt>
          <dd>{t("durationValue", {duration: trace.metrics.duration_ms})}</dd>
        </div>
        <div>
          <dt>{t("toolCalls")}</dt>
          <dd>{trace.metrics.tool_calls}</dd>
        </div>
        <div>
          <dt>{t("cost")}</dt>
          <dd>
            {trace.metrics.cost.amount} {trace.metrics.cost.currency}
          </dd>
        </div>
      </dl>
    </section>
  );
}
