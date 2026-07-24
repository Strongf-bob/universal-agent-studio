"use client";

import type {
  RunEvent,
  RunTrace,
} from "@universal-agent-studio/contracts";
import {Fingerprint} from "lucide-react";
import {useTranslations} from "next-intl";
import {useEffect, useState} from "react";

import {RunResult} from "@/features/runs/RunResult";
import {RunTimeline} from "@/features/runs/RunTimeline";
import {RunTraceExplorer} from "@/features/runs/RunTraceExplorer";
import {
  type RunEventConnector,
  useRunEvents,
} from "@/features/runs/useRunEvents";
import {
  type AgentVersionSummary,
  cancelRun,
  getRunTrace,
  type RunSummary,
} from "@/lib/api/client";
import type {Locale} from "@/lib/i18n/routing";

type Props = {
  initialRun: RunSummary;
  version: AgentVersionSummary;
  locale: Locale;
  initialEvents?: RunEvent[];
  connect?: RunEventConnector;
  loadTrace?: typeof getRunTrace;
  requestCancel?: typeof cancelRun;
};

const TERMINAL_STATUSES = new Set([
  "completed",
  "failed",
  "cancelled",
]);

export function RunWorkspace({
  initialRun,
  version,
  locale,
  initialEvents = [],
  connect,
  loadTrace = getRunTrace,
  requestCancel = cancelRun,
}: Props) {
  const t = useTranslations("run");
  const stream = useRunEvents({
    runId: initialRun.run_id,
    initialEvents,
    connect,
  });
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(false);
  const lastEvent = stream.events.at(-1);
  const terminal =
    stream.state === "complete" ||
    TERMINAL_STATUSES.has(initialRun.status);

  useEffect(() => {
    if (!terminal) {
      return;
    }
    let active = true;
    async function hydrateTrace() {
      await Promise.resolve();
      if (!active) {
        return;
      }
      setTraceLoading(true);
      setTraceError(false);
      try {
        const document = await loadTrace(initialRun.run_id);
        if (active) {
          setTrace(document);
        }
      } catch {
        if (active) {
          setTraceError(true);
        }
      } finally {
        if (active) {
          setTraceLoading(false);
        }
      }
    }
    void hydrateTrace();
    return () => {
      active = false;
    };
  }, [initialRun.run_id, loadTrace, terminal]);

  async function handleCancel() {
    setCancelling(true);
    setCancelError(false);
    try {
      await requestCancel(initialRun.run_id);
    } catch {
      setCancelError(true);
    } finally {
      setCancelling(false);
    }
  }

  if (!version.agent_spec) {
    return <p role="alert">{t("versionUnavailable")}</p>;
  }

  const status =
    lastEvent?.type === "run.completed"
      ? "completed"
      : lastEvent?.type === "run.failed"
        ? "failed"
        : lastEvent?.type === "run.cancelled"
          ? "cancelled"
          : initialRun.status;

  return (
    <div className="runWorkspace">
      <header className="runHero">
        <div>
          <p className="eyebrow">{t("eyebrow")}</p>
          <h1>{t("title")}</h1>
          <p className="sectionDescription">{t("description")}</p>
        </div>
        <div className="runIdentity">
          <Fingerprint aria-hidden />
          <span>
            <span className="metaLabel">{t("runId")}</span>
            <code>{initialRun.run_id}</code>
          </span>
          <span className={`runStatus runStatus--${status}`}>
            {t(`statuses.${status}`)}
          </span>
        </div>
      </header>

      <div className="runOverview">
        <div className="runProgressColumn">
          <RunTimeline
            events={stream.events}
            connectionState={stream.state}
            canCancel={!terminal && !initialRun.cancel_requested}
            cancelling={cancelling}
            onCancel={() => void handleCancel()}
          />
          {cancelError ? (
            <p className="apiError" role="alert">
              {t("cancelError")}
            </p>
          ) : null}
        </div>
        <RunResult
          trace={trace}
          loading={traceLoading}
          error={traceError}
        />
      </div>

      {trace ? (
        <section className="traceSection" aria-labelledby="trace-title">
          <header className="sectionHeader">
            <p className="eyebrow">{t("trace.eyebrow")}</p>
            <h2 id="trace-title">{t("trace.title")}</h2>
            <p className="sectionDescription">{t("trace.description")}</p>
          </header>
          <RunTraceExplorer
            agentSpec={version.agent_spec}
            events={stream.events}
            locale={locale}
            trace={trace}
          />
        </section>
      ) : null}
    </div>
  );
}
