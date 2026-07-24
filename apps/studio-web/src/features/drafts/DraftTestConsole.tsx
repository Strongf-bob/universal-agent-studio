"use client";

import type {
  AgentSpec,
  RunEvent,
  RunTrace,
} from "@universal-agent-studio/contracts";
import {ExternalLink, Play, TerminalSquare} from "lucide-react";
import Link from "next/link";
import {useTranslations} from "next-intl";
import {useEffect, useState} from "react";

import {
  type RunEventConnector,
  useRunEvents,
} from "@/features/runs/useRunEvents";
import {projectRunHistory} from "@/features/drafts/projection";
import {
  type CreatedRun,
  createDraftTestRun,
  getRunTrace,
} from "@/lib/api/client";
import {type Locale, localizedPath} from "@/lib/i18n/routing";

type Props = {
  agentId: string;
  agentSpec: AgentSpec;
  disabled?: boolean;
  locale: Locale;
  revision: number;
  runId: string | null;
  onRunStarted: (runId: string) => void;
  onStartingChange?: (starting: boolean) => void;
  onEvent: (event: RunEvent) => void;
  startRun?: typeof createDraftTestRun;
  connect?: RunEventConnector;
  loadTrace?: typeof getRunTrace;
};

export function DraftTestConsole({
  agentId,
  agentSpec,
  disabled = false,
  locale,
  revision,
  runId,
  onRunStarted,
  onStartingChange,
  onEvent,
  startRun = createDraftTestRun,
  connect,
  loadTrace = getRunTrace,
}: Props) {
  const t = useTranslations("draft.test");
  const inputField = agentSpec.interface.input_fields[0];
  const inputId = inputField?.id ?? "question";
  const inputLabel =
    inputField?.label[locale] ??
    inputField?.label["en-US"] ??
    t("inputLabel");
  const [value, setValue] = useState("");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(false);

  async function run() {
    if (!value.trim()) {
      setError(true);
      return;
    }
    setStarting(true);
    onStartingChange?.(true);
    setError(false);
    try {
      const created: CreatedRun = await startRun({
        agentId,
        expectedRevision: revision,
        runInput: {[inputId]: value.trim()},
        locale,
      });
      onRunStarted(created.run_id);
    } catch {
      setError(true);
    } finally {
      setStarting(false);
      onStartingChange?.(false);
    }
  }

  return (
    <section
      className="editorPanel testPanel"
      id="test-console"
      aria-labelledby="test-title"
    >
      <header className="editorPanelHeader editorPanelHeader--row">
        <span>
          <p className="eyebrow">{t("eyebrow")}</p>
          <h2 id="test-title">{t("title")}</h2>
          <p>{t("description")}</p>
        </span>
        <TerminalSquare aria-hidden />
      </header>
      <div className="fieldGroup">
        <label htmlFor="draft-test-input">{inputLabel}</label>
        <textarea
          id="draft-test-input"
          rows={3}
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            setError(false);
          }}
        />
      </div>
      <button
        className="primaryButton"
        disabled={disabled || starting}
        type="button"
        onClick={() => void run()}
      >
        <Play aria-hidden />
        {starting ? t("starting") : t("run")}
      </button>
      {disabled ? (
        <p className="emptyState">{t("dirty")}</p>
      ) : null}
      {error ? (
        <p className="apiError" role="alert">
          {t("error")}
        </p>
      ) : null}
      {runId ? (
        <DraftRunStream
          agentSpec={agentSpec}
          connect={connect}
          loadTrace={loadTrace}
          locale={locale}
          runId={runId}
          onEvent={onEvent}
        />
      ) : (
        <p className="emptyState">{t("empty")}</p>
      )}
    </section>
  );
}

function DraftRunStream({
  agentSpec,
  connect,
  loadTrace,
  locale,
  runId,
  onEvent,
}: {
  agentSpec: AgentSpec;
  connect?: RunEventConnector;
  loadTrace: typeof getRunTrace;
  locale: Locale;
  runId: string;
  onEvent: (event: RunEvent) => void;
}) {
  const t = useTranslations("draft.test");
  const statusT = useTranslations("draft.graph.statuses");
  const stream = useRunEvents({runId, connect});
  const [trace, setTrace] = useState<RunTrace | null>(null);
  const nodeLabels = new Map(
    agentSpec.nodes.map((node) => [
      node.id,
      node.localized_metadata.name[locale] ??
        node.localized_metadata.name["en-US"],
    ]),
  );
  const history = projectRunHistory(agentSpec, stream.events);

  useEffect(() => {
    for (const event of stream.events) {
      onEvent(event);
    }
  }, [onEvent, stream.events]);

  useEffect(() => {
    if (stream.state !== "complete") {
      return;
    }
    let active = true;
    void loadTrace(runId).then((result) => {
      if (active) {
        setTrace(result);
      }
    });
    return () => {
      active = false;
    };
  }, [loadTrace, runId, stream.state]);

  return (
    <div className="testRunResult" aria-live="polite">
      <div className="testRunMeta">
        <span className={`connectionState connectionState--${stream.state}`}>
          {t(`connection.${stream.state}`)}
        </span>
        <code>{runId}</code>
      </div>
      {history.length > 0 ? (
        <>
          <p className="metaLabel">{t("history")}</p>
          <ol
            className="testRunHistory"
            aria-label={t("historyLabel")}
            role="log"
          >
            {history.map((entry) => {
              const label = nodeLabels.get(entry.nodeId) ?? entry.nodeId;
              const status = statusT(entry.status);
              return (
                <li
                  aria-label={`${label} · ${status}`}
                  key={`${entry.sequence}-${entry.nodeId}-${entry.status}`}
                >
                  <span>{label}</span>
                  <span aria-hidden>·</span>
                  <strong>{status}</strong>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
      {trace?.output ? (
        <>
          <p className="metaLabel">{t("output")}</p>
          <code className="testCompactOutput">
            {JSON.stringify(trace.output)}
          </code>
          <pre>{JSON.stringify(trace.output, null, 2)}</pre>
          <Link href={localizedPath(locale, `/runs/${runId}`)}>
            {t("trace")}
            <ExternalLink aria-hidden />
          </Link>
        </>
      ) : null}
    </div>
  );
}
